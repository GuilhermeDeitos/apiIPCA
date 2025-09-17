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
    
class IPCACorrecao(BaseModel):
    """Modelo para resposta de correção pelo IPCA"""
    valor_inicial: float = Field(..., example=100.0)
    data_inicial: str = Field(..., example="01/2020")
    data_final: str = Field(..., example="12/2023")
    indice_ipca_inicial: float = Field(..., example=100.0)
    indice_ipca_final: float = Field(..., example=120.0)
    valor_corrigido: float = Field(..., example=120.0)
    percentual_correcao: float = Field(..., example=20.0)

class IPCAMediaAnual(BaseModel):
    """Modelo para média anual do IPCA"""
    ano: str = Field(..., example="2023")
    media_ipca: float = Field(..., example=5.67)
    total_meses: int = Field(..., example=12)
    meses_disponiveis: List[str] = Field(..., example=["01", "02", "03"])
    valores_mensais: Dict[str, float] = Field(..., example={"01": 5.0, "02": 5.5, "03": 6.0})