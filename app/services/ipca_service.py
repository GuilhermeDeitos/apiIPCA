from app.utils.data_loader import carregar_dados_ipca
from typing import Dict, Optional, Tuple
from fastapi import HTTPException

class IPCAService:
    """Serviço para gerenciar operações relacionadas ao IPCA"""
    
    def __init__(self):
        """Inicializa o serviço carregando os dados do IPCA"""
        self._ipca_dict, self._ipca_info = carregar_dados_ipca()
    
    def obter_todos_dados(self) -> Dict:
        """Retorna todos os dados do IPCA"""
        return {
            "info": self._ipca_info,
            "data": self._ipca_dict
        }
    
    def obter_valor_por_data(self, mes: str, ano: str) -> Dict:
        """
        Obtém o valor do IPCA para uma data específica.
        
        Args:
            mes: Mês com dois dígitos (01-12)
            ano: Ano (ex: 2023)
            
        Returns:
            Dicionário com data e valor do IPCA
            
        Raises:
            HTTPException: Se a data não for encontrada
        """
        data_key = f"{mes}/{ano}"
        if data_key in self._ipca_dict:
            return {"data": data_key, "valor": self._ipca_dict[data_key]}
        else:
            raise HTTPException(status_code=404, detail="Data não encontrada")
    
    def corrigir_valor(self, valor: float, mes_inicial: str, ano_inicial: str, 
                      mes_final: str, ano_final: str) -> Dict:
        """
        Corrige um valor monetário pelo IPCA.
        
        Args:
            valor: Valor a ser corrigido
            mes_inicial: Mês inicial com dois dígitos (01-12)
            ano_inicial: Ano inicial
            mes_final: Mês final com dois dígitos (01-12)
            ano_final: Ano final
            
        Returns:
            Dicionário com valores e índices
            
        Raises:
            HTTPException: Se os índices não forem encontrados
        """
        data_inicial = f"{mes_inicial}/{ano_inicial}"
        data_final = f"{mes_final}/{ano_final}"

        if data_inicial not in self._ipca_dict or data_final not in self._ipca_dict:
            raise HTTPException(
                status_code=404, 
                detail="IPCA para data inicial ou final não encontrado"
            )
        
        if valor < 0:
          raise HTTPException(
              status_code=400, 
              detail="O valor a ser corrigido não pode ser negativo"
          )

        indice_ipca_inicial = self._ipca_dict[data_inicial]
        indice_ipca_final = self._ipca_dict[data_final]

        # Cálculo da correção
        valor_corrigido = valor * (indice_ipca_final / indice_ipca_inicial)
        valor_corrigido = round(valor_corrigido, 2)

        return {
            "valor_inicial": valor,
            "indice_ipca_inicial": indice_ipca_inicial,
            "indice_ipca_final": indice_ipca_final,
            "valor_corrigido": valor_corrigido
        }

# Instância do serviço para uso nos endpoints
ipca_service = IPCAService()