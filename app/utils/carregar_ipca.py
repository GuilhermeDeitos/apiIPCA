import ipeadatapy as ip
import logging
import time
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta

# : Importar o cache
from app.utils.ipca_cache import ipca_cache

logger = logging.getLogger(__name__)

# Configuração de timeout e retry
TIMEOUT_SEGUNDOS = 10
MAX_TENTATIVAS = 3
INTERVALO_RETRY = 2


class CircuitBreaker:
    """Circuit Breaker para evitar requisições repetidas a serviço indisponível."""
    
    def __init__(self, max_failures: int = 3, timeout_seconds: int = 300):
        self.max_failures = max_failures
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def is_open(self) -> bool:
        """Verifica se o circuit breaker está aberto."""
        if self.state == "OPEN":
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.timeout_seconds:
                    logger.info(f"Circuit Breaker: Mudando para HALF_OPEN após {elapsed}s")
                    self.state = "HALF_OPEN"
                    return False
            return True
        return False
    
    def record_success(self):
        """Registra sucesso e reseta contadores."""
        if self.state in ["HALF_OPEN", "OPEN"]:
            logger.info("Circuit Breaker: Serviço recuperado, mudando para CLOSED")
        self.failures = 0
        self.state = "CLOSED"
        self.last_failure_time = None
    
    def record_failure(self):
        """Registra falha e abre circuit se necessário."""
        self.failures += 1
        self.last_failure_time = datetime.now()
        
        if self.failures >= self.max_failures:
            if self.state != "OPEN":
                logger.warning(
                    f"Circuit Breaker: Abrindo após {self.failures} falhas. "
                    f"Próxima tentativa em {self.timeout_seconds}s"
                )
            self.state = "OPEN"
    
    def get_status(self) -> Dict:
        """Retorna status atual do circuit breaker."""
        return {
            "state": self.state,
            "failures": self.failures,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "next_attempt_in": (
                max(0, self.timeout_seconds - (datetime.now() - self.last_failure_time).total_seconds())
                if self.last_failure_time and self.state == "OPEN"
                else 0
            )
        }


circuit_breaker = CircuitBreaker(max_failures=3, timeout_seconds=300)


def carregar_dados_ipca_da_api() -> Tuple[Dict[str, float], str]:
    """
    Carrega os dados do IPCA diretamente da API do IPEA.
    
    Returns:
        Tuple (ipca_dict, info_msg)
    """
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            logger.info(f"Tentativa {tentativa}/{MAX_TENTATIVAS} de carregar dados IPCA da API...")
            
            import socket
            socket.setdefaulttimeout(TIMEOUT_SEGUNDOS)
            
            df = ip.timeseries("PRECOS12_IPCA12")
            df = df[["MONTH", "YEAR", "VALUE (-)"]]
            df = df.rename(columns={"VALUE (-)": "IPCA"})
            
            df["data"] = df["MONTH"].astype(str).str.zfill(2) + "/" + df["YEAR"].astype(str)
            ipca_dict = df.set_index("data")["IPCA"].to_dict()
            
            info_ipca = (
                f"Dados do IPCA carregados da API IPEA. "
                f"Período: {df['YEAR'].min()}-{df['YEAR'].max()}, "
                f"Total de registros: {len(ipca_dict)}, "
                f"Carregado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            logger.info(info_ipca)
            circuit_breaker.record_success()
            
            return ipca_dict, info_ipca
            
        except Exception as e:
            logger.warning(f"Tentativa {tentativa}/{MAX_TENTATIVAS} falhou: {e}")
            circuit_breaker.record_failure()
            
            if tentativa < MAX_TENTATIVAS:
                time.sleep(INTERVALO_RETRY)
            else:
                erro_msg = f"Erro ao carregar IPCA após {MAX_TENTATIVAS} tentativas: {str(e)}"
                return {}, erro_msg
        
        finally:
            import socket
            socket.setdefaulttimeout(None)


def carregar_dados_ipca_com_retry(forcar_atualizacao: bool = False) -> Tuple[Dict[str, float], str]:
    """
    Carrega os dados do IPCA com sistema de cache.
    
    Args:
        forcar_atualizacao: Se True, força atualização mesmo com cache válido
    
    Returns:
        Tuple contendo:
        - Dicionário com datas como chaves e valores IPCA como valores
        - String com informação sobre o IPCA
    """
    # 1. Tentar carregar do cache primeiro
    if not forcar_atualizacao:
        cache_data = ipca_cache.carregar_cache()
        
        if cache_data and cache_data.get("dados"):
            # Verificar se precisa atualizar
            precisa_atualizar, motivo = ipca_cache.verificar_atualizacao_necessaria()
            
            if not precisa_atualizar:
                logger.info("Usando dados IPCA do cache (atualizado)")
                return cache_data["dados"], cache_data.get("info", "Carregado do cache")
            else:
                logger.info(f"Cache necessita atualização: {motivo}")
    
    # 2. Verificar circuit breaker antes de tentar API
    if circuit_breaker.is_open():
        logger.warning("Circuit Breaker OPEN - Tentando usar cache desatualizado")
        
        # Tentar usar cache mesmo desatualizado
        cache_data = ipca_cache.carregar_cache()
        if cache_data and cache_data.get("dados"):
            logger.info("Usando cache desatualizado devido a circuit breaker")
            return (
                cache_data["dados"], 
                f"Cache desatualizado (Circuit Breaker ativo). {cache_data.get('info', '')}"
            )
        
        erro_msg = (
            f"Serviço IPCA temporariamente indisponível. "
            f"Circuit Breaker: {circuit_breaker.get_status()['state']}"
        )
        return {}, erro_msg
    
    # 3. Carregar da API
    ipca_dict, info_msg = carregar_dados_ipca_da_api()
    
    # 4. Se conseguiu carregar da API, atualizar cache
    if ipca_dict:
        ipca_cache.salvar_cache(ipca_dict, info_msg, forcar=forcar_atualizacao)
        return ipca_dict, info_msg + " [Cache atualizado]"
    
    # 5. Se falhou, tentar usar cache como fallback
    logger.warning("Falha ao carregar da API - tentando usar cache como fallback")
    cache_data = ipca_cache.carregar_cache()
    
    if cache_data and cache_data.get("dados"):
        logger.info("Usando cache como fallback após falha na API")
        return (
            cache_data["dados"],
            f"Cache (fallback após erro). {cache_data.get('info', '')}"
        )
    
    # 6. Sem cache e sem API - retornar vazio
    return {}, info_msg


def carregar_dados_ipca() -> Tuple[Dict[str, float], str]:
    """
    Função principal para carregar dados IPCA (mantida para compatibilidade).
    """
    return carregar_dados_ipca_com_retry(forcar_atualizacao=False)


def forcar_atualizacao_cache() -> Tuple[bool, str]:
    """
    Força atualização do cache com dados mais recentes da API.
    
    Returns:
        Tuple (sucesso, mensagem)
    """
    logger.info("Forçando atualização do cache IPCA...")
    
    ipca_dict, info_msg = carregar_dados_ipca_da_api()
    
    if ipca_dict:
        sucesso = ipca_cache.salvar_cache(ipca_dict, info_msg, forcar=True)
        if sucesso:
            return True, f"Cache atualizado com sucesso: {len(ipca_dict)} registros"
        else:
            return False, "Erro ao salvar cache atualizado"
    else:
        return False, f"Erro ao carregar dados da API: {info_msg}"


def verificar_dados_ipca_disponiveis(ipca_dict: Dict[str, float]) -> bool:
    """Verifica se os dados do IPCA foram carregados com sucesso."""
    return len(ipca_dict) > 0


def obter_status_carregamento_ipca(ipca_dict: Dict[str, float], info: str) -> Dict[str, any]:
    """
    Retorna informações sobre o status do carregamento do IPCA.
    
    Args:
        ipca_dict: Dicionário com dados do IPCA
        info: Mensagem informativa
        
    Returns:
        Dicionário com status do carregamento
    """
    tem_dados = verificar_dados_ipca_disponiveis(ipca_dict)
    cb_status = circuit_breaker.get_status()
    
    # : Adicionar informações do cache
    cache_stats = ipca_cache.obter_estatisticas()
    
    if tem_dados:
        anos = set()
        for data in ipca_dict.keys():
            try:
                mes, ano = data.split('/')
                anos.add(int(ano))
            except:
                pass
        
        return {
            "status": "sucesso",
            "dados_disponiveis": True,
            "total_registros": len(ipca_dict),
            "anos_disponiveis": sorted(list(anos)) if anos else [],
            "periodo": f"{min(anos)}-{max(anos)}" if anos else "N/A",
            "mensagem": info,
            "circuit_breaker": cb_status,
            "cache": cache_stats  # 
        }
    else:
        return {
            "status": "erro",
            "dados_disponiveis": False,
            "total_registros": 0,
            "anos_disponiveis": [],
            "periodo": "N/A",
            "mensagem": info,
            "aviso": "Serviço funcionando com capacidade limitada",
            "circuit_breaker": cb_status,
            "cache": cache_stats  # 
        }


def obter_status_circuit_breaker() -> Dict:
    """Retorna status atual do circuit breaker."""
    return circuit_breaker.get_status()


def resetar_circuit_breaker():
    """Reseta o circuit breaker (útil para testes e manutenção)."""
    circuit_breaker.record_success()
    logger.info("Circuit Breaker resetado manualmente")


def obter_estatisticas_cache() -> Dict:
    """Retorna estatísticas do cache IPCA."""
    return ipca_cache.obter_estatisticas()


def limpar_cache_ipca() -> bool:
    """Limpa o cache IPCA."""
    return ipca_cache.limpar_cache()