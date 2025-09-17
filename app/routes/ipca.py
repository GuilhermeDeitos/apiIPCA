from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from app.services.ipca_service import ipca_service
from app.models.ipca_model import IPCAInfo, IPCAValor, IPCACorrecao, IPCAMediaAnual
from typing import Dict, List

router = APIRouter(prefix="", tags=["IPCA"])

@router.get("/ipca", response_model=IPCAInfo)
async def get_ipca():
    """
    Retorna todos os dados do IPCA.
    
    Returns:
        Dicionário com informações e dados completos do IPCA
    """
    return ipca_service.obter_todos_dados()

@router.get("/ipca/filtro", response_model=IPCAValor)
async def get_ipca_mes_ano(
    mes: str = Query(..., example="12", description="Mês com dois dígitos (01-12)"),
    ano: str = Query(..., example="2023", description="Ano (ex: 2023)")
):
    """
    Consulta o valor do IPCA para um mês e ano específicos.
    
    Args:
        mes: Mês com dois dígitos (01-12)
        ano: Ano (ex: 2023)
        
    Returns:
        Objeto com a data e o valor do IPCA
    """
    return ipca_service.obter_valor_por_data(mes, ano)

@router.get("/ipca/media-anual/{ano}", response_model=IPCAMediaAnual)
async def get_ipca_media_anual(ano: str):
    """
    Calcula a média anual do IPCA para um ano específico.
    
    Args:
        ano: Ano para calcular a média (ex: 2023)
        
    Returns:
        Objeto com a média anual e detalhes dos meses
    """
    return ipca_service.obter_media_anual(ano)

@router.get("/ipca/medias-anuais")
async def get_ipca_medias_multiplos_anos(
    anos: List[str] = Query(..., description="Lista de anos para calcular médias")
):
    """
    Calcula médias anuais do IPCA para múltiplos anos.
    
    Args:
        anos: Lista de anos (ex: [2021, 2022, 2023])
        
    Returns:
        Dicionário com médias por ano
    """
    return ipca_service.obter_medias_multiplos_anos(anos)

@router.get("/ipca/corrigir", response_model=IPCACorrecao)
async def corrigir_valor_ipca(
    valor: float = Query(..., description="Valor a ser corrigido"),
    mes_inicial: str = Query(..., example="01", description="Mês inicial com dois dígitos (01-12)"),
    ano_inicial: str = Query(..., example="2020", description="Ano inicial"),
    mes_final: str = Query(..., example="12", description="Mês final com dois dígitos (01-12)"),
    ano_final: str = Query(..., example="2023", description="Ano final")
):
    """
    Corrige um valor monetário pela variação do IPCA entre duas datas.
    
    Args:
        valor: Valor a ser corrigido
        mes_inicial: Mês inicial com dois dígitos (01-12)
        ano_inicial: Ano inicial
        mes_final: Mês final com dois dígitos (01-12)
        ano_final: Ano final
        
    Returns:
        Objeto com valor inicial, índices e valor corrigido
    """
    return ipca_service.corrigir_valor(valor, mes_inicial, ano_inicial, mes_final, ano_final)