from fastapi import APIRouter, HTTPException
from app.services.transparencia_service import transparencia_service
from app.models.transparencia_model import TransparenciaConsultaParams, TransparenciaResposta
import aiohttp
from app.utils.data_loader import API_CRAWLER_URL
        

router = APIRouter(prefix="/transparencia", tags=["Portal da Transparência"])

@router.post("/consultar", response_model=TransparenciaResposta)
async def consultar_transparencia(params: TransparenciaConsultaParams):
    """
    Consulta dados do Portal da Transparência com correção monetária pelo IPCA.
    
    Para consultas de um único ano:
    - Aplica correção do ano consultado para o ano atual
    
    Para consultas de múltiplos anos:
    - Cada ano é corrigido separadamente para o ano atual
    - Exemplo: dados de 2020 são corrigidos de 2020 para 2025
    - Dados de 2021 são corrigidos de 2021 para 2025
    
    Args:
        params: Parâmetros da consulta (data_inicio, data_fim)
        
    Returns:
        Dados com correção monetária aplicada
    """
    return await transparencia_service.consultar_dados_corrigidos(
        params.data_inicio, 
        params.data_fim
    )

@router.get("/status")
async def status_transparencia():
    """Verifica se a integração com a API_crawler está funcionando"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_CRAWLER_URL}/") as response:
                if response.status == 200:
                    return {
                        "status": "ok",
                        "api_crawler_disponivel": True,
                        "url_crawler": API_CRAWLER_URL
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