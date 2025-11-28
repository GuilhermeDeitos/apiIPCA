import json
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)

# Caminho do arquivo de cache
CACHE_DIR = Path("data")
CACHE_FILE = CACHE_DIR / "series_ipca.json"

# Lock para operações thread-safe
cache_lock = Lock()


class IPCACache:
    """Gerenciador de cache para séries IPCA."""
    
    def __init__(self, cache_path: Path = CACHE_FILE):
        self.cache_path = cache_path
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Garante que o diretório de cache existe."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _carregar_cache_sem_lock(self) -> Optional[Dict]:
        """
        Carrega cache sem lock (uso interno).
        
        Returns:
            Dicionário com cache ou None
        """
        try:
            if not self.cache_path.exists():
                logger.info(f"Arquivo de cache não encontrado: {self.cache_path}")
                return None
            
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            logger.info(
                f"Cache carregado: {cache_data.get('total_registros', 0)} registros, "
                f"última atualização: {cache_data.get('ultima_atualizacao')}"
            )
            
            return cache_data
        
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar cache JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro ao carregar cache: {e}")
            return None
    
    def carregar_cache(self) -> Optional[Dict]:
        """
        Carrega o cache do arquivo JSON (thread-safe).
        
        Returns:
            Dicionário com cache ou None se não existir/inválido
        """
        with cache_lock:
            return self._carregar_cache_sem_lock()
    
    def salvar_cache(
        self, 
        ipca_dict: Dict[str, float], 
        info: str,
        forcar: bool = False
    ) -> bool:
        """
        Salva os dados IPCA no cache.
        
        Args:
            ipca_dict: Dicionário com séries IPCA
            info: Informação sobre os dados
            forcar: Se True, salva mesmo se não houver mudanças
            
        Returns:
            True se salvou com sucesso, False caso contrário
        """
        with cache_lock:
            try:
                # Verificar se há dados para salvar
                if not ipca_dict:
                    logger.warning("Tentativa de salvar cache vazio - ignorando")
                    return False
                
                # Verificar se precisa atualizar
                if not forcar:
                    # Usar método sem lock para evitar deadlock
                    cache_existente = self._carregar_cache_sem_lock()
                    if cache_existente:
                        dados_existentes = cache_existente.get("dados", {})
                        
                        # Se os dados são idênticos, não precisa salvar
                        if dados_existentes == ipca_dict:
                            logger.info("Cache já está atualizado - não salvando")
                            return True
                
                # Extrair metadados
                anos = set()
                ultimo_periodo = None
                
                for periodo in ipca_dict.keys():
                    try:
                        mes, ano = periodo.split('/')
                        anos.add(int(ano))
                        
                        # Encontrar o último período
                        if ultimo_periodo is None:
                            ultimo_periodo = periodo
                        else:
                            ultimo_mes, ultimo_ano = ultimo_periodo.split('/')
                            if int(ano) > int(ultimo_ano) or (
                                int(ano) == int(ultimo_ano) and int(mes) > int(ultimo_mes)
                            ):
                                ultimo_periodo = periodo
                    except ValueError:
                        continue
                
                # Preparar estrutura do cache
                cache_data = {
                    "ultima_atualizacao": datetime.now().isoformat(),
                    "total_registros": len(ipca_dict),
                    "anos_disponiveis": sorted(list(anos)),
                    "periodo_inicio": f"{min(anos)}" if anos else "N/A",
                    "periodo_fim": f"{max(anos)}" if anos else "N/A",
                    "ultimo_periodo": ultimo_periodo,
                    "info": info,
                    "dados": ipca_dict
                }
                
                # Salvar no arquivo
                with open(self.cache_path, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
                logger.info(
                    f"Cache salvo com sucesso: {len(ipca_dict)} registros, "
                    f"último período: {ultimo_periodo}"
                )
                
                return True
            
            except Exception as e:
                logger.error(f"Erro ao salvar cache: {e}")
                return False
    
    def verificar_atualizacao_necessaria(self) -> Tuple[bool, Optional[str]]:
        """
        Verifica se o cache precisa ser atualizado.
        
        Returns:
            Tuple (precisa_atualizar, motivo)
        """
        # Usar método COM lock (público)
        cache_data = self.carregar_cache()
        
        if not cache_data:
            return True, "Cache não existe"
        
        # Verificar se tem dados
        if not cache_data.get("dados"):
            return True, "Cache vazio"
        
        # Verificar última atualização
        try:
            ultima_atualizacao = datetime.fromisoformat(
                cache_data.get("ultima_atualizacao", "")
            )
            
            # Se última atualização foi há mais de 30 dias, atualizar
            dias_desde_atualizacao = (datetime.now() - ultima_atualizacao).days
            
            if dias_desde_atualizacao > 30:
                return True, f"Cache desatualizado ({dias_desde_atualizacao} dias)"
            
            # Verificar se estamos no início do mês (primeiros 5 dias)
            # Neste caso, sempre tentar atualizar para pegar novos dados
            hoje = datetime.now()
            if hoje.day <= 5:
                # Verificar se já atualizou neste mês
                if ultima_atualizacao.month != hoje.month or \
                   ultima_atualizacao.year != hoje.year:
                    return True, "Início do mês - verificar novos dados"
            
            return False, "Cache atualizado"
        
        except (ValueError, KeyError) as e:
            logger.warning(f"Erro ao verificar atualização: {e}")
            return True, "Erro ao verificar data"
    
    def obter_ultimo_periodo(self) -> Optional[str]:
        """
        Retorna o último período disponível no cache.
        
        Returns:
            String no formato MM/AAAA ou None
        """
        cache_data = self.carregar_cache()
        if cache_data:
            return cache_data.get("ultimo_periodo")
        return None
    
    def limpar_cache(self) -> bool:
        """
        Remove o arquivo de cache.
        
        Returns:
            True se removeu com sucesso
        """
        with cache_lock:
            try:
                if self.cache_path.exists():
                    self.cache_path.unlink()
                    logger.info("Cache limpo com sucesso")
                    return True
                return False
            except Exception as e:
                logger.error(f"Erro ao limpar cache: {e}")
                return False
    
    def obter_estatisticas(self) -> Dict:
        """
        Retorna estatísticas sobre o cache.
        
        Returns:
            Dicionário com estatísticas
        """
        cache_data = self.carregar_cache()
        
        if not cache_data:
            return {
                "existe": False,
                "total_registros": 0,
                "ultima_atualizacao": None,
                "tamanho_arquivo": 0
            }
        
        tamanho = 0
        if self.cache_path.exists():
            tamanho = self.cache_path.stat().st_size
        
        return {
            "existe": True,
            "total_registros": cache_data.get("total_registros", 0),
            "anos_disponiveis": cache_data.get("anos_disponiveis", []),
            "periodo": f"{cache_data.get('periodo_inicio', 'N/A')}-{cache_data.get('periodo_fim', 'N/A')}",
            "ultimo_periodo": cache_data.get("ultimo_periodo"),
            "ultima_atualizacao": cache_data.get("ultima_atualizacao"),
            "tamanho_arquivo_kb": round(tamanho / 1024, 2),
            "caminho": str(self.cache_path)
        }


# Instância global do cache
ipca_cache = IPCACache()