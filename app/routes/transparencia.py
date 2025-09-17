from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.services.transparencia_service import transparencia_service
from app.models.transparencia_model import TransparenciaConsultaParams, TransparenciaResposta
import aiohttp
from app.utils.data_loader import API_CRAWLER_URL
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
async def consultar_transparencia_streaming(params: TransparenciaConsultaParams):
    """
    Consulta dados com suporte a streaming (Server-Sent Events).
    Retorna dados parciais conforme disponíveis.
    """
    async def generate():
        try:
            async for chunk in transparencia_service.consultar_dados_streaming(
                params.data_inicio,
                params.data_fim,
                params.tipo_correcao,
                params.ipca_referencia
            ):
                # Garantir que o JSON seja válido e compacto (sem indentação)
                json_data = json.dumps(chunk, ensure_ascii=False)
                # Formato Server-Sent Events correto
                yield f"data: {json_data}\n\n"
        except Exception as e:
            error_chunk = {
                "status": "erro",
                "erro": str(e)
            }
            yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",  # Tipo correto para SSE
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
            "Access-Control-Allow-Origin": "*",  # Permitir CORS
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