from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from app.services.ipca_service import ipca_service
from app.models.ipca_model import IPCAInfo, IPCAValor, IPCACorrecao
from typing import Dict

router = APIRouter(prefix="", tags=["IPCA"])

@router.get("/", response_class=HTMLResponse)
async def home():
    """Página inicial da API"""
    return """
    <html>
        <head>
            <title>API IPCA</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #333; }
                ul { line-height: 1.6; }
                code { background-color: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>API IPCA - Documentação</h1>
            <p>Esta API fornece dados e funcionalidades relacionadas ao IPCA (Índice de Preços ao Consumidor Amplo).</p>
            <h2>Endpoints disponíveis:</h2>
            <ul>
                <li><code>GET /ipca</code> - Retorna todos os dados do IPCA</li>
                <li><code>GET /ipca/filtro?mes=MM&ano=YYYY</code> - Retorna o IPCA para um mês/ano específico</li>
                <li><code>GET /ipca/corrigir?valor=X&mes_inicial=MM&ano_inicial=YYYY&mes_final=MM&ano_final=YYYY</code> - Corrige um valor pelo IPCA</li>
            </ul>
            <p>Para documentação completa, acesse: <a href="/docs">/docs</a></p>
        </body>
    </html>
    """

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