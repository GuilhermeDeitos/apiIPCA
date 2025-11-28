import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.services.transparencia_service import transparencia_service
from app.models.transparencia_model import TransparenciaConsultaParams, TransparenciaResposta
import aiohttp
from app.utils.api_client import API_CRAWLER_URL 
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transparencia", tags=["Portal da Transparência"])

@router.post("/consultar", response_model=TransparenciaResposta)
async def consultar_transparencia(params: TransparenciaConsultaParams):
    """
    Consulta dados do Portal da Transparência com correção monetária pelo IPCA.
    
    Para consultas de um único ano:
    - Aplica correção do ano consultado para o período base atual ou especificado
    
    Para consultas de múltiplos anos:
    - Cada ano é corrigido separadamente para o período base atual ou especificado
    
    Args:
        params: Parâmetros da consulta (data_inicio, data_fim, tipo_correcao, ipca_referencia)
        
    Returns:
        Dados com correção monetária aplicada
    """
    try:
        return await transparencia_service.consultar_dados_corrigidos(
            params.data_inicio, 
            params.data_fim,
            params.tipo_correcao,
            params.ipca_referencia
        )
    except Exception as e:
        error_message = f"Erro ao consultar dados do Portal da Transparência para o período {params.data_inicio} a {params.data_fim}"
        
        logger.error(f"Erro na consulta: {str(e)}")
        
        raise HTTPException(
            status_code=500, 
            detail={
                "error": error_message,
                "periodo": f"{params.data_inicio} a {params.data_fim}",
                "codigo": "ERRO_CONSULTA_TRANSPARENCIA"
            }
        )

@router.post("/consultar-streaming")
async def consultar_transparencia_streaming(request: Request, params: TransparenciaConsultaParams):
    """
    Consulta dados com suporte a streaming (Server-Sent Events) e cancelamento.
    """
    # Criar um evento de cancelamento para comunicação entre threads
    cancel_event = asyncio.Event()
    
    # Armazenar ID da consulta quando disponível para poder cancelar depois
    consulta_id = None
    
    # Tarefa em background para verificar se o cliente desconectou
    async def check_client_disconnected():
        while not cancel_event.is_set():
            if await request.is_disconnected():
                logger.info("Cliente desconectado, cancelando consulta streaming")
                cancel_event.set()
                
                # Se temos ID de consulta, cancelar explicitamente também
                if consulta_id:
                    try:
                        async with aiohttp.ClientSession() as session:
                            logger.info(f"Tentando cancelar consulta {consulta_id} após desconexão")
                            await session.post(f"{API_CRAWLER_URL}/cancelar-consulta/{consulta_id}")
                    except Exception as e:
                        logger.error(f"Erro ao cancelar consulta após desconexão: {e}")
                break
            await asyncio.sleep(0.5)
    
    # Iniciar a verificação de desconexão em background
    disconnect_task = asyncio.create_task(check_client_disconnected())
    
    async def generate():
        nonlocal consulta_id
        try:
            # Passar o evento de cancelamento para o serviço
            async for chunk in transparencia_service.consultar_dados_streaming(
                params.data_inicio,
                params.data_fim,
                params.tipo_correcao,
                params.ipca_referencia,
                cancel_event  # Novo parâmetro para controle de cancelamento
            ):
                # Armazenar ID da consulta quando disponível
                if 'id_consulta' in chunk and not consulta_id:
                    consulta_id = chunk['id_consulta']
                    logger.info(f"Consulta iniciada com ID: {consulta_id}")
                # Verificar se foi cancelado antes de enviar cada chunk
                if cancel_event.is_set():
                    logger.info("Cancelamento detectado durante processamento de chunk")
                    break
                
                # Garantir que o JSON seja válido e compacto
                json_data = json.dumps(chunk, ensure_ascii=False)
                # Formato Server-Sent Events
                yield f"data: {json_data}\n\n"
                
        except Exception as e:
            if isinstance(e, asyncio.CancelledError) or cancel_event.is_set():
                logger.info("Streaming cancelado pelo cliente")
                error_chunk = {
                    "status": "cancelado",
                    "mensagem": "Consulta cancelada pelo cliente"
                }
            else:
                logger.error(f"Erro durante streaming: {str(e)}")
                error_chunk = {
                    "status": "erro",
                    "erro": str(e)
                }
            
            yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
        finally:
            # Garantir que a tarefa de verificação seja cancelada
            disconnect_task.cancel()
            try:
                await disconnect_task
            except asyncio.CancelledError:
                pass
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "*",
        }
    )

@router.get("/status")
async def status_transparencia():
    """Verifica se a integração com a API_crawler está funcionando"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_CRAWLER_URL}/system-status") as response:
                if response.status == 200:
                    status_data = await response.json()
                    return {
                        "status": "ok",
                        "api_crawler_disponivel": True,
                        "url_crawler": API_CRAWLER_URL,
                        "detalhes_crawler": {
                            "slots_disponiveis": status_data.get("slots_disponiveis", 0),
                            "slots_ocupados": status_data.get("slots_ocupados", 0),
                            "max_concurrent_scrapers": status_data.get("max_concurrent_scrapers", 0)
                        }
                    }
                elif response.status == 503:
                    return {
                        "status": "erro",
                        "api_crawler_disponivel": False,
                        "erro": "API_crawler indisponível no momento"
                    }
                else:
                    return {
                        "status": "erro",
                        "api_crawler_disponivel": False,
                        "erro": f"API_crawler retornou status {response.status}"
                    }
    except Exception as e:
        return {
            "status": "erro",
            "api_crawler_disponivel": False,
            "erro": str(e)
        }
        
@router.post("/cancelar/{id_consulta}")
async def cancelar_consulta(id_consulta: str):
    """Cancela uma consulta em andamento no Portal da Transparência"""
    try:
        # Tentar cancelar na API de crawler
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_CRAWLER_URL}/cancelar-consulta/{id_consulta}") as response:
                if response.status == 200:
                    resultado = await response.json()
                    logger.info(f"Consulta {id_consulta} cancelada com sucesso")
                    return {
                        "status": "cancelado",
                        "mensagem": "Consulta cancelada com sucesso",
                        "detalhes": resultado
                    }
                else:
                    error_text = await response.text()
                    logger.warning(f"Erro ao cancelar consulta {id_consulta}: {response.status} - {error_text}")
                    return {
                        "status": "erro",
                        "mensagem": f"Erro ao cancelar consulta: {response.status}",
                        "erro_detalhes": error_text
                    }
    except Exception as e:
        logger.error(f"Erro ao cancelar consulta {id_consulta}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao cancelar consulta: {str(e)}"
        )