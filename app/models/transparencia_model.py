from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime

class TransparenciaConsultaParams(BaseModel):
    data_inicio: str = Field(..., description="Data inicial no formato MM/YYYY")
    data_fim: str = Field(..., description="Data final no formato MM/YYYY")

class MetadataCorrecao(BaseModel):
    ano_base: int
    ano_correcao: int
    fator_correcao: float
    percentual_correcao: float
    media_ipca_ano_base: float
    media_ipca_ano_correcao: float
    metodo: str
    campos_identificados: List[str]
    campos_corrigidos: List[str]
    aplicado_em: str

class DadosAno(BaseModel):
    dados: List[Dict[str, Any]]
    dados_originais: Optional[List[Dict[str, Any]]] = None
    total_registros: int
    total_registros_original: Optional[int] = None
    fator_correcao_ipca: float
    media_ipca_ano_base: float
    media_ipca_ano_correcao: float
    correcao_aplicada: bool
    mes_inicio: Optional[int] = None
    mes_fim: Optional[int] = None
    processado_em: Optional[str] = None
    corrigido_em: str
    metodo_correcao: str
    periodo_correcao: str

class TransparenciaResposta(BaseModel):
    dados_por_ano: Dict[str, DadosAno]
    dados: Optional[List[Dict[str, Any]]] = None  # Compatibilidade
    total_registros: int
    anos_processados: Optional[List[int]] = None
    resumo_por_ano: Optional[Dict[str, Any]] = None
    resumo_consolidado: Optional[Dict[str, Any]] = None
    status_coleta: Optional[str] = None
    correcao_aplicada: bool
    periodo_correcao: str
    organizacao: str
    
    class Config:
        # Permitir campos extras para flexibilidade
        extra = "allow"
        # Usar enum values
        use_enum_values = True
        # Validação flexível para dados dinâmicos
        arbitrary_types_allowed = True