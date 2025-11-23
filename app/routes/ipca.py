from fastapi import APIRouter, Query, HTTPException, Request
from app.services.ipca_service import ipca_service
from app.models.ipca_model import IPCAInfo, IPCAValor, IPCACorrecao, IPCAMediaAnual
from typing import List
import re

router = APIRouter(prefix="", tags=["IPCA"])


def sanitizar_input(texto: str, max_length: int = 100) -> str:
    """
    Sanitiza input removendo caracteres perigosos.
    
    Args:
        texto: Texto a ser sanitizado
        max_length: Tamanho máximo permitido
        
    Returns:
        Texto sanitizado
    """
    if not texto:
        return ""
    
    # Remover caracteres de controle perigosos
    texto = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', texto)
    
    # Remover scripts e tags HTML perigosas
    texto = re.sub(r'<script[^>]*>.*?</script>', '', texto, flags=re.IGNORECASE | re.DOTALL)
    texto = re.sub(r'<iframe[^>]*>.*?</iframe>', '', texto, flags=re.IGNORECASE | re.DOTALL)
    texto = re.sub(r'javascript:', '', texto, flags=re.IGNORECASE)
    
    # Remover event handlers
    texto = re.sub(r'on\w+\s*=', '', texto, flags=re.IGNORECASE)
    
    # Limitar tamanho
    return texto[:max_length]


def validar_mes(mes: str) -> str:
    """
    Valida e sanitiza valor de mês.
    
    Args:
        mes: Mês a validar (deve ser 01-12)
        
    Returns:
        Mês validado
        
    Raises:
        HTTPException: Se mês inválido
    """
    # Verificar formato antes de sanitizar/truncar
    if not isinstance(mes, str) or not re.fullmatch(r'\d{1,2}', mes):
        raise HTTPException(status_code=400, detail="Formato de mês inválido. Use 01-12")
    
    mes_int = int(mes)
    if mes_int < 1 or mes_int > 12:
        raise HTTPException(status_code=400, detail="Mês deve estar entre 01 e 12")
    
    # Opcional: sanitizar para remover caracteres de controle, sem truncar
    mes_sanitizado = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', f"{mes_int:02d}")
    return mes_sanitizado


def validar_ano(ano: str) -> str:
    """
    Valida e sanitiza valor de ano.
    
    Args:
        ano: Ano a validar
        
    Returns:
        Ano validado
        
    Raises:
        HTTPException: Se ano inválido
    """
    ano = sanitizar_input(ano, 4)
    
    # Verificar formato
    if not re.match(r'^\d{4}$', ano):
        raise HTTPException(status_code=400, detail="Formato de ano inválido. Use AAAA")
    
    ano_int = int(ano)
    if ano_int < 1900 or ano_int > 2100:
        raise HTTPException(status_code=400, detail="Ano deve estar entre 1900 e 2100")
    
    return ano


def validar_valor(valor: float) -> float:
    """
    Valida valor monetário.
    
    Args:
        valor: Valor a validar
        
    Returns:
        Valor validado
        
    Raises:
        HTTPException: Se valor inválido
    """
    if valor < 0:
        raise HTTPException(status_code=400, detail="Valor não pode ser negativo")
    
    if valor > 999999999999:  # 999 bilhões
        raise HTTPException(status_code=400, detail="Valor muito grande. Máximo: 999.999.999.999")
    
    return round(valor, 2)


@router.get("/ipca", response_model=IPCAInfo)
async def get_ipca(request: Request):
    """
    Retorna todos os dados do IPCA.
    
    **Rate Limit**: 60 requisições por minuto (aplicado globalmente)
    
    Returns:
        Dicionário com informações e dados completos do IPCA
    """
    return ipca_service.obter_todos_dados()


@router.get("/ipca/filtro", response_model=IPCAValor)
async def get_ipca_mes_ano(
    request: Request,
    mes: str = Query(..., examples=["12"], description="Mês com dois dígitos (01-12)"),
    ano: str = Query(..., examples=["2023"], description="Ano (ex: 2023)")
):
    """
    Consulta o valor do IPCA para um mês e ano específicos.
    
    **Rate Limit**: 60 requisições por minuto (aplicado globalmente)
    
    **Validações**:
    - Mês: 01-12
    - Ano: 1900-2100
    
    Args:
        mes: Mês com dois dígitos (01-12)
        ano: Ano (ex: 2023)
        
    Returns:
        Objeto com a data e o valor do IPCA
    """
    # Validar e sanitizar inputs
    mes = validar_mes(mes)
    ano = validar_ano(ano)
    
    return ipca_service.obter_valor_por_data(mes, ano)


@router.get("/ipca/media-anual/{ano}", response_model=IPCAMediaAnual)
async def get_ipca_media_anual(request: Request, ano: str):
    """
    Calcula a média anual do IPCA para um ano específico.
    
    **Rate Limit**: 60 requisições por minuto (aplicado globalmente)
    
    Args:
        ano: Ano para calcular a média (ex: 2023)
        
    Returns:
        Objeto com a média anual e detalhes dos meses
    """
    ano = validar_ano(ano)
    return ipca_service.obter_media_anual(ano)


@router.get("/ipca/medias-anuais")
async def get_ipca_medias_multiplos_anos(
    request: Request,
    anos: List[str] = Query(..., description="Lista de anos para calcular médias")
):
    """
    Calcula médias anuais do IPCA para múltiplos anos.
    
    **Rate Limit**: 60 requisições por minuto (aplicado globalmente)
    
    Args:
        anos: Lista de anos (ex: [2021, 2022, 2023])
        
    Returns:
        Dicionário com médias por ano
    """
    # Limitar quantidade de anos para evitar abuso
    if len(anos) > 50:
        raise HTTPException(status_code=400, detail="Máximo de 50 anos por requisição")
    
    # Validar cada ano
    anos_validados = [validar_ano(ano) for ano in anos]
    
    return ipca_service.obter_medias_multiplos_anos(anos_validados)


@router.get("/ipca/corrigir", response_model=IPCACorrecao)
async def corrigir_valor_ipca(
    request: Request,
    valor: float = Query(..., description="Valor a ser corrigido"),
    mes_inicial: str = Query(..., examples=["01"], description="Mês inicial com dois dígitos (01-12)"),
    ano_inicial: str = Query(..., examples=["2020"], description="Ano inicial"),
    mes_final: str = Query(..., examples=["12"], description="Mês final com dois dígitos (01-12)"),
    ano_final: str = Query(..., examples=["2023"], description="Ano final")
):
    """
    Corrige um valor monetário pela variação do IPCA entre duas datas.
    
    **Rate Limit**: 60 requisições por minuto (aplicado globalmente)
    
    **Validações**:
    - Valor: >= 0 e <= 999.999.999.999
    - Mês: 01-12
    - Ano: 1900-2100
    
    Args:
        valor: Valor a ser corrigido
        mes_inicial: Mês inicial com dois dígitos (01-12)
        ano_inicial: Ano inicial
        mes_final: Mês final com dois dígitos (01-12)
        ano_final: Ano final
        
    Returns:
        Objeto com valor inicial, índices e valor corrigido
    """
    # Validar inputs
    valor = validar_valor(valor)
    mes_inicial = validar_mes(mes_inicial)
    ano_inicial = validar_ano(ano_inicial)
    mes_final = validar_mes(mes_final)
    ano_final = validar_ano(ano_final)
    
    return ipca_service.corrigir_valor(valor, mes_inicial, ano_inicial, mes_final, ano_final)