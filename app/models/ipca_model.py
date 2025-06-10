from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Any

class IPCAInfo(BaseModel):
    """Modelo para informações do IPCA"""
    info: str
    data: Dict[str, float]

class IPCAValor(BaseModel):
    """Modelo para valor do IPCA em uma data específica"""
    data: str
    valor: float

class IPCACorrecao(BaseModel):
    """Modelo para correção de valor pelo IPCA"""
    valor_inicial: float
    indice_ipca_inicial: float
    indice_ipca_final: float
    valor_corrigido: float

class IPCAConsultaParams(BaseModel):
    """Parâmetros para consulta de IPCA"""
    mes: str = Field(..., example="12")
    ano: str = Field(..., example="2023")

class IPCACorrecaoParams(BaseModel):
    """Parâmetros para correção de valor pelo IPCA"""
    valor: float = Field(..., example=100.0)
    mes_inicial: str = Field(..., example="01")
    ano_inicial: str = Field(..., example="2020")
    mes_final: str = Field(..., example="12") 
    ano_final: str = Field(..., example="2023")