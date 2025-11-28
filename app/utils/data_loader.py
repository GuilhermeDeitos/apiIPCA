"""
Orquestrador principal para carregamento e processamento de dados do Portal da Transparência.
Mantém a interface pública original para compatibilidade.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator, Tuple, List
from datetime import datetime

from app.utils.api_client import ApiCrawlerClient
from app.utils.data_processor import DataExtractor, DataOrganizer
from app.utils.ipca_calculator import IPCACalculator, MonetaryCorrector

logger = logging.getLogger(__name__)


async def consultar_transparencia_streaming(
    data_inicio: str,
    data_fim: str,
    tipo_correcao: str = "mensal",
    ipca_referencia: str = None,
    cancel_event: Optional[asyncio.Event] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Consulta dados do Portal da Transparência com suporte a streaming.
    
    Args:
        data_inicio: Data de início (MM/AAAA)
        data_fim: Data de fim (MM/AAAA)
        tipo_correcao: "mensal" ou "anual"
        ipca_referencia: Período de referência IPCA (opcional)
        cancel_event: Evento para cancelamento da operação
        
    Yields:
        Dicionários com dados parciais e finais
    """
    #  MUDANÇA: Importar função ao invés de instância
    from app.services.ipca_service import get_ipca_service
    
    # Verificar cancelamento inicial
    if cancel_event and cancel_event.is_set():
        logger.info("Operação cancelada antes de iniciar")
        return
    
    #  MUDANÇA: Obter instância do serviço
    ipca_service = get_ipca_service()
    
    # Inicializar componentes
    api_client = ApiCrawlerClient()
    ipca_calc = IPCACalculator(ipca_service)
    corrector = MonetaryCorrector(ipca_calc)
    
    # ... resto do código permanece igual
    
    # Determinar período base e obter IPCA de referência
    periodo_base = ipca_calc.determinar_periodo_base(ipca_referencia, tipo_correcao)
    
    try:
        ipca_base = ipca_calc.obter_ipca_base(periodo_base, tipo_correcao)
    except Exception as e:
        logger.error(f"Erro ao obter IPCA base: {e}")
        raise
    
    # Iniciar consulta na API
    try:
        resposta_inicial = await api_client.iniciar_consulta(data_inicio, data_fim)
    except Exception as e:
        logger.error(f"Erro ao iniciar consulta: {e}")
        raise
    
    # Verificar cancelamento após requisição
    if cancel_event and cancel_event.is_set():
        logger.info("Operação cancelada após requisição inicial")
        return
    
    # Processar resposta
    if resposta_inicial.get("processamento") == "sincrono":
        async for evento in _processar_sincrono(
            resposta_inicial,
            ipca_base,
            periodo_base,
            tipo_correcao,
            corrector,
            cancel_event
        ):
            yield evento
    
    elif "id_consulta" in resposta_inicial:
        async for evento in _processar_assincrono(
            resposta_inicial["id_consulta"],
            api_client,
            ipca_base,
            periodo_base,
            tipo_correcao,
            corrector,
            cancel_event
        ):
            yield evento
    
    else:
        raise Exception(f"Formato de resposta não reconhecido: {resposta_inicial}")


async def _processar_sincrono(
    resposta: Dict[str, Any],
    ipca_base: float,
    periodo_base: str,
    tipo_correcao: str,
    corrector: MonetaryCorrector,
    cancel_event: Optional[asyncio.Event]
) -> AsyncGenerator[Dict[str, Any], None]:
    """Processa resposta síncrona (ano único)."""
    logger.info("Processamento síncrono detectado (ano único)")
    
    dados_por_ano = DataExtractor.extrair_dados_de_resposta(resposta)
    todos_dados = []
    total_dados_nao_processados = []
    
    for ano_str, info_ano in dados_por_ano.items():
        if cancel_event and cancel_event.is_set():
            logger.info("Cancelamento durante processamento síncrono")
            return
        
        dados_ano = _extrair_dados_ano(info_ano)
        if not dados_ano:
            continue
        
        logger.info(f"Processando dados do ano {ano_str}: {len(dados_ano)} registros")
        
        dados_corrigidos, dados_nao_processados = corrector.processar_correcao_dados(
            dados_ano,
            ipca_base,
            periodo_base,
            tipo_correcao,
            ano_contexto=int(ano_str)
        )
        
        todos_dados.extend(dados_corrigidos)
        total_dados_nao_processados.extend(dados_nao_processados)
        
        yield {
            "status": "parcial",
            "ano_processado": int(ano_str),
            "total_registros_ano": len(dados_corrigidos),
            "total_nao_processados_ano": len(dados_nao_processados),
            "dados": dados_corrigidos
        }
    
    yield {
        "status": "completo",
        "total_registros": len(todos_dados),
        "total_nao_processados": len(total_dados_nao_processados),
        "dados": [],
        "dados_nao_processados": total_dados_nao_processados,
        "periodo_base_ipca": periodo_base,
        "ipca_referencia": ipca_base,
        "tipo_correcao": tipo_correcao,
        "dados_por_ano": DataOrganizer.reorganizar_por_ano(todos_dados)
    }


async def _processar_assincrono(
    id_consulta: str,
    api_client: ApiCrawlerClient,
    ipca_base: float,
    periodo_base: str,
    tipo_correcao: str,
    corrector: MonetaryCorrector,
    cancel_event: Optional[asyncio.Event]
) -> AsyncGenerator[Dict[str, Any], None]:
    """Processa resposta assíncrona (múltiplos anos)."""
    logger.info(f"Processamento assíncrono iniciado. ID: {id_consulta}")
    
    yield {
        "status": "iniciando",
        "id_consulta": id_consulta,
        "mensagem": "Consulta iniciada em processamento assíncrono"
    }
    
    anos_ja_processados = set()
    todos_dados = []
    total_dados_nao_processados = []
    tentativas_sem_mudanca = 0
    max_tentativas = 60
    
    # Armazenar anos esperados
    anos_esperados = None
    
    # Flag para controlar se backend já disse que está completo
    backend_disse_completo = False
    
    while True:
        if cancel_event and cancel_event.is_set():
            logger.info("Cancelamento durante processamento assíncrono")
            return
        
        await asyncio.sleep(2)
        
        try:
            status_data = await api_client.verificar_status_consulta(id_consulta)
        except Exception as e:
            logger.error(f"Erro ao verificar status: {e}")
            break
        
        # Verificar status do backend PRIMEIRO
        if status_data.get("status") == "concluido":
            backend_disse_completo = True
            logger.info("Backend marcou como concluído")
        
        # Capturar total de anos esperados na primeira consulta
        if anos_esperados is None:
            anos_concluidos_resp = status_data.get("anos_concluidos", [])
            anos_pendentes_resp = status_data.get("anos_pendentes", [])
            
            # Também verificar dados_parciais_por_ano
            dados_parciais = status_data.get("dados_parciais_por_ano", {})
            if dados_parciais:
                anos_com_dados = {int(ano) for ano in dados_parciais.keys()}
                anos_esperados = anos_com_dados | set(anos_concluidos_resp) | set(anos_pendentes_resp)
            elif anos_concluidos_resp or anos_pendentes_resp:
                anos_esperados = set(anos_concluidos_resp) | set(anos_pendentes_resp)
            
            if anos_esperados:
                logger.info(f"Total de anos esperados: {len(anos_esperados)} - {sorted(anos_esperados)}")
        
        dados_por_ano = DataExtractor.extrair_dados_de_resposta(status_data)
        
        if dados_por_ano:
            novos_anos = False
            
            for ano_str, info_ano in dados_por_ano.items():
                ano_int = int(ano_str)
                
                if ano_int in anos_ja_processados:
                    continue
                
                dados_ano = _extrair_dados_ano(info_ano)
                if not dados_ano:
                    # Mesmo sem dados, marcar ano como processado
                    logger.warning(f"Ano {ano_str}: SEM DADOS, mas marcando como processado")
                    anos_ja_processados.add(ano_int)
                    
                    # Enviar evento parcial mesmo sem dados
                    yield {
                        "status": "parcial",
                        "ano_processado": ano_int,
                        "total_registros_ano": 0,
                        "total_nao_processados_ano": 0,
                        "dados": [],
                        "observacao": "Ano sem dados disponíveis"
                    }
                    novos_anos = True
                    continue
                
                logger.info(f"Processando ano {ano_str}: {len(dados_ano)} registros")
                anos_ja_processados.add(ano_int)
                novos_anos = True
                
                dados_corrigidos, dados_nao_processados = corrector.processar_correcao_dados(
                    dados_ano,
                    ipca_base,
                    periodo_base,
                    tipo_correcao,
                    ano_contexto=ano_int
                )
                
                todos_dados.extend(dados_corrigidos)
                total_dados_nao_processados.extend(dados_nao_processados)
                
                yield {
                    "status": "parcial",
                    "ano_processado": ano_int,
                    "total_registros_ano": len(dados_corrigidos),
                    "total_nao_processados_ano": len(dados_nao_processados),
                    "dados": dados_corrigidos
                }
            
            tentativas_sem_mudanca = 0 if novos_anos else tentativas_sem_mudanca + 1
        else:
            tentativas_sem_mudanca += 1
        
        # Verificação mais robusta para finalizar
        # Condição 1: Temos anos esperados E processamos todos
        todos_anos_processados = anos_esperados and len(anos_ja_processados) >= len(anos_esperados)
        
        # Condição 2: Backend disse completo E (temos anos processados OU passou tempo suficiente)
        backend_completo_com_dados = backend_disse_completo and (
            len(anos_ja_processados) > 0 or tentativas_sem_mudanca >= 3
        )
        
        if todos_anos_processados or backend_completo_com_dados:
            motivo = "todos os anos processados" if todos_anos_processados else "backend confirmou conclusão"
            logger.info(
                f"Finalizando consulta - {motivo}. "
                f"Anos processados: {len(anos_ja_processados)}/{len(anos_esperados) if anos_esperados else '?'}"
            )
            
            # Aguardar um pouco para garantir que todos os eventos foram enviados
            await asyncio.sleep(1)
            
            # Enviar evento completo
            yield {
                "status": "completo",
                "total_registros": len(todos_dados),
                "total_nao_processados": len(total_dados_nao_processados),
                "dados": [],
                "dados_nao_processados": total_dados_nao_processados,
                "periodo_base_ipca": periodo_base,
                "ipca_referencia": ipca_base,
                "tipo_correcao": tipo_correcao,
                "dados_por_ano": DataOrganizer.reorganizar_por_ano(todos_dados),
                "mensagem": f"Processamento concluído: {len(anos_ja_processados)} anos"
            }
            break
        
        # Timeout (fallback)
        if tentativas_sem_mudanca >= max_tentativas:
            logger.warning(f"Timeout após {tentativas_sem_mudanca * 2}s")
            yield _criar_resposta_final(
                todos_dados,
                total_dados_nao_processados,
                periodo_base,
                ipca_base,
                tipo_correcao,
                observacao=f"Processamento parcial - timeout. Processados {len(anos_ja_processados)} anos"
            )
            break

def _extrair_dados_ano(info_ano: Any) -> List[Dict]:
    """Extrai lista de dados de um ano (lida com diferentes estruturas)."""
    if isinstance(info_ano, dict) and "dados" in info_ano and info_ano["dados"]:
        return info_ano["dados"]
    elif isinstance(info_ano, list) and info_ano:
        return info_ano
    return []


def _criar_resposta_final(
    todos_dados: List[Dict],
    dados_nao_processados: List[Dict],
    periodo_base: str,
    ipca_base: float,
    tipo_correcao: str,
    observacao: str = None
) -> Dict[str, Any]:
    """Cria a resposta final padronizada."""
    resposta = {
        "status": "completo",
        "total_registros": len(todos_dados),
        "total_nao_processados": len(dados_nao_processados),
        "dados": [],
        "dados_nao_processados": dados_nao_processados,
        "periodo_base_ipca": periodo_base,
        "ipca_referencia": ipca_base,
        "tipo_correcao": tipo_correcao,
        "dados_por_ano": DataOrganizer.reorganizar_por_ano(todos_dados)
    }
    
    if observacao:
        resposta["observacao"] = observacao
    
    return resposta


# ============= FUNÇÕES PÚBLICAS (Interface Original) =============

async def carregar_dados_portal_transparencia(
    data_inicio: str,
    data_fim: str,
    tipo_correcao: str = "mensal",
    ipca_referencia: str = None
) -> Dict[str, Any]:
    """
    Carrega dados do Portal da Transparência com correção monetária.
    Versão simplificada que aguarda todos os dados.
    """
    resultado_final = {}
    
    async for chunk in consultar_transparencia_streaming(
        data_inicio,
        data_fim,
        tipo_correcao,
        ipca_referencia
    ):
        if chunk["status"] == "completo":
            resultado_final = chunk
            break
        elif chunk["status"] == "parcial":
            logger.info(f"Recebido ano {chunk['ano_processado']} com {chunk['total_registros_ano']} registros")
    
    return resultado_final


def processar_correcao_dados(
    dados: list,
    ipca_base: float,
    periodo_base: str,
    ipca_service: Any,
    tipo_correcao: str = "mensal",
    ano_contexto: int = None
) -> Tuple[list, list]:
    """Interface legada para processar correção de dados."""
    ipca_calc = IPCACalculator(ipca_service)
    corrector = MonetaryCorrector(ipca_calc)
    
    return corrector.processar_correcao_dados(
        dados,
        ipca_base,
        periodo_base,
        tipo_correcao,
        ano_contexto
    )


def reorganizar_dados_por_ano(dados: list) -> Dict[str, Any]:
    """Interface legada para reorganizar dados por ano."""
    return DataOrganizer.reorganizar_por_ano(dados)


async def verificar_status_api_crawler() -> Dict[str, Any]:
    """Verifica o status da API Crawler."""
    api_client = ApiCrawlerClient()
    return await api_client.verificar_status_api()


async def cancelar_consulta_transparencia(id_consulta: str) -> Dict[str, Any]:
    """Cancela uma consulta em andamento."""
    api_client = ApiCrawlerClient()
    return await api_client.cancelar_consulta(id_consulta)