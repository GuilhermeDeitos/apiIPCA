from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional

class TransparenciaConsultaParams(BaseModel):
    """Parâmetros para consulta do Portal da Transparência"""
    data_inicio: str = Field(..., example="01/2020", description="Data inicial no formato MM/YYYY")
    data_fim: str = Field(..., example="12/2023", description="Data final no formato MM/YYYY")

class TransparenciaResposta(BaseModel):
    """Resposta da consulta ao Portal da Transparência"""
    dados: Optional[List[Dict[str, Any]]] = None
    dados_por_ano: Optional[Dict[str, List[Dict[str, Any]]]] = None
    total_registros: int
    anos_processados: List[int]
    correcao_aplicada: bool
    periodo_correcao: str
    status: str = "concluido"
    
    class Config:
        json_encoders = {
            # Permite serialização de tipos complexos
            dict: lambda v: v
        }