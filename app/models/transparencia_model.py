from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any

class TransparenciaConsultaParams(BaseModel):
    """Parâmetros para consulta ao Portal da Transparência"""
    data_inicio: str = Field(..., example="01/2023", description="Data inicial no formato MM/YYYY")
    data_fim: str = Field(..., example="12/2023", description="Data final no formato MM/YYYY")
    tipo_correcao: str = Field(default="mensal", description="Tipo de correção: 'mensal' ou 'anual'")
    ipca_referencia: Optional[str] = Field(None, example="12/2023", description="Período de referência do IPCA (MM/YYYY para mensal ou YYYY para anual)")
    
    @validator('ipca_referencia')
    def validar_ipca_referencia(cls, v, values):
        if v is None:
            return v
            
        tipo_correcao = values.get('tipo_correcao', 'mensal')
        
        if tipo_correcao == 'anual':
            # Para correção anual, aceitar tanto "YYYY" quanto "MM/YYYY"
            if "/" in v:
                # Extrair apenas o ano
                parts = v.split('/')
                if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
                    return parts[1]  # Retorna apenas o ano
                else:
                    raise ValueError("Formato inválido. Use YYYY ou MM/YYYY")
            elif v.isdigit() and len(v) == 4:
                return v
            else:
                raise ValueError("Para correção anual, use formato YYYY ou MM/YYYY")
        else:
            # Para correção mensal, exigir formato MM/YYYY
            if "/" not in v:
                raise ValueError("Para correção mensal, use formato MM/YYYY")
            parts = v.split('/')
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                raise ValueError("Formato inválido para correção mensal. Use MM/YYYY")
            if len(parts[0]) != 2 or len(parts[1]) != 4:
                raise ValueError("Formato inválido. Mês deve ter 2 dígitos e ano 4 dígitos")
        
        return v

class DadoNaoProcessado(BaseModel):
    """Modelo para dados que não foram processados"""
    item_original: Dict[str, Any] = Field(..., description="Item original que não foi processado")
    motivo: str = Field(..., description="Motivo pelo qual o item não foi processado")

class TransparenciaResposta(BaseModel):
    """Resposta da consulta ao Portal da Transparência"""
    status: str = Field(..., description="Status da resposta: 'completo', 'parcial', 'erro'")
    total_registros: int = Field(..., description="Total de registros processados")
    total_nao_processados: int = Field(0, description="Total de registros não processados")
    dados: List[Dict[str, Any]] = Field(..., description="Dados processados com correção IPCA")
    dados_nao_processados: List[DadoNaoProcessado] = Field(default_factory=list, description="Dados que não foram processados")
    periodo_base_ipca: str = Field(..., description="Período base usado para correção IPCA")
    ipca_referencia: float = Field(..., description="Valor do IPCA de referência")
    tipo_correcao: str = Field(..., description="Tipo de correção aplicada")
    observacao: Optional[str] = Field(None, description="Observações adicionais")
    
    class Config:
        json_encoders = {
            float: lambda v: round(v, 4) if v is not None else None
        }