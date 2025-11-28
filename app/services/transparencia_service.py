import asyncio
from app.utils.data_loader import carregar_dados_portal_transparencia, consultar_transparencia_streaming
from typing import Dict, Any, AsyncGenerator, Optional
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class TransparenciaService:
    """Serviço para gerenciar operações do Portal da Transparência com correção IPCA"""
    
    async def consultar_dados_corrigidos(self, data_inicio: str, data_fim: str, 
                                       tipo_correcao: str = "mensal", 
                                       ipca_referencia: str = None) -> Dict[str, Any]:
        """
        Consulta dados do Portal da Transparência e aplica correção monetária.
        
        Args:
            data_inicio: Data inicial no formato "MM/YYYY"
            data_fim: Data final no formato "MM/YYYY"
            tipo_correcao: Tipo de correção ("mensal" ou "anual")
            ipca_referencia: Período de referência para o IPCA
            
        Returns:
            Dados com correção monetária aplicada
        """
        try:
            logger.info(f"Iniciando consulta ao Portal da Transparência: {data_inicio} a {data_fim}")
            resultado = await carregar_dados_portal_transparencia(
                data_inicio, 
                data_fim,
                tipo_correcao,
                ipca_referencia
            )
            logger.info(f"Consulta concluída. Total de registros: {resultado.get('total_registros', 0)}")
            return resultado
        except Exception as e:
            logger.error(f"Erro ao consultar dados: {e}")
            raise Exception(f"Erro ao processar dados do Portal da Transparência: {str(e)}")
    
    async def consultar_dados_streaming(self, data_inicio: str, data_fim: str,
                                      tipo_correcao: str = "mensal",
                                      ipca_referencia: str = None, 
                                    cancel_event: Optional[asyncio.Event] = None

                                      ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Consulta dados com suporte a streaming para respostas parciais.
        
        Args:
            data_inicio: Data inicial no formato "MM/YYYY"
            data_fim: Data final no formato "MM/YYYY"
            tipo_correcao: Tipo de correção ("mensal" ou "anual")
            ipca_referencia: Período de referência para o IPCA
            cancel_event: Evento assíncrono para controlar cancelamento

        Yields:
            Chunks de dados conforme disponíveis
        """
        try:
            logger.info(f"Iniciando consulta streaming: {data_inicio} a {data_fim}")
            
            # Verificar cancelamento antes de iniciar
            if cancel_event and cancel_event.is_set():
                logger.info("Consulta cancelada antes de iniciar")
                yield {
                    "status": "cancelado",
                    "mensagem": "Consulta cancelada pelo cliente"
                }
                return
                
            async for chunk in consultar_transparencia_streaming(
                data_inicio, 
                data_fim,
                tipo_correcao,
                ipca_referencia,
                cancel_event  # Propagar o evento de cancelamento
            ):
                # Verificar cancelamento antes de cada yield
                if cancel_event and cancel_event.is_set():
                    logger.info("Consulta cancelada durante streaming")
                    yield {
                        "status": "cancelado",
                        "mensagem": "Consulta cancelada pelo cliente"
                    }
                    return
                    
                yield chunk
                
        except Exception as e:
            if cancel_event and cancel_event.is_set():
                logger.info("Consulta cancelada durante exceção")
                yield {
                    "status": "cancelado",
                    "mensagem": "Consulta cancelada pelo cliente"
                }
            else:
                logger.error(f"Erro no streaming: {e}")
                yield {
                    "status": "erro",
                    "erro": str(e)
                }

# Instância do serviço
transparencia_service = TransparenciaService()