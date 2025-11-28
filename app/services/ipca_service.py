from app.utils.carregar_ipca import (
    carregar_dados_ipca, 
    verificar_dados_ipca_disponiveis,
    obter_status_carregamento_ipca
)
from typing import Dict, Optional, Tuple, List
from fastapi import HTTPException
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class IPCAService:
    """Serviço para gerenciar operações relacionadas ao IPCA"""
    
    _instance: Optional['IPCAService'] = None
    _initialized: bool = False
    
    def __new__(cls):
        """Implementa Singleton para garantir uma única instância."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Inicializa o serviço carregando os dados do IPCA (apenas uma vez)"""
        if not IPCAService._initialized:
            self._ipca_dict, self._ipca_info = carregar_dados_ipca()
            self._dados_disponiveis = verificar_dados_ipca_disponiveis(self._ipca_dict)
            
            if not self._dados_disponiveis:
                logger.error("ATENÇÃO: API iniciada SEM dados do IPCA! Funcionalidade limitada.")
            else:
                logger.info(f"Serviço IPCA inicializado com sucesso: {self._ipca_info}")
            
            IPCAService._initialized = True
    
    @classmethod
    def reset_instance(cls):
        """Reset da instância (útil para testes)"""
        cls._instance = None
        cls._initialized = False
        
    def verificar_disponibilidade(self) -> None:
        """
        Verifica se os dados do IPCA estão disponíveis.
        Lança exceção se não estiverem.
        
        Raises:
            HTTPException: Se dados não disponíveis
        """
        if not self._dados_disponiveis:
            raise HTTPException(
                status_code=503,
                detail={
                    "erro": "Serviço IPCA temporariamente indisponível",
                    "mensagem": "Não foi possível carregar dados do IPEA. Tente novamente mais tarde.",
                    "info": self._ipca_info
                }
            )
    
    def obter_status_servico(self) -> Dict:
        """
        Retorna informações sobre o status do serviço IPCA.
        
        Returns:
            Dicionário com status do serviço
        """
        return obter_status_carregamento_ipca(self._ipca_dict, self._ipca_info)
    
    def obter_todos_dados(self) -> Dict:
        """Retorna todos os dados do IPCA"""
        self.verificar_disponibilidade()
        
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
            HTTPException: Se a data não for encontrada ou serviço indisponível
        """
        self.verificar_disponibilidade()
        
        data_key = f"{mes}/{ano}"
        if data_key in self._ipca_dict:
            return {"data": data_key, "valor": self._ipca_dict[data_key]}
        else:
            raise HTTPException(status_code=404, detail="Data não encontrada")
    
    def obter_ipca_periodo(self, periodo: str) -> float:
        """
        Obtém o valor do IPCA para um período no formato MM/AAAA.
        
        Args:
            periodo: Período no formato MM/AAAA
            
        Returns:
            Valor do IPCA para o período
            
        Raises:
            ValueError: Se o período não for encontrado ou serviço indisponível
        """
        if not self._dados_disponiveis:
            raise ValueError("Serviço IPCA temporariamente indisponível")
        
        if periodo in self._ipca_dict:
            return self._ipca_dict[periodo]
        else:
            raise ValueError(f"IPCA não encontrado para {periodo}")
    
    # ... resto dos métodos mantendo a estrutura, mas adicionando 
    # self.verificar_disponibilidade() no início de cada um
    
    def obter_ipca_por_periodo(self, mes: str, ano: str) -> float:
        """Obtém o valor do IPCA para um período específico."""
        self.verificar_disponibilidade()
        
        data_key = f"{mes}/{ano}"
        if data_key in self._ipca_dict:
            return self._ipca_dict[data_key]
        else:
            raise ValueError(f"IPCA não encontrado para {data_key}")
    
    def obter_media_anual(self, ano: str, meses: List[int] = None) -> Dict:
        """Calcula a média do IPCA para um ano específico."""
        self.verificar_disponibilidade()
        
        if meses is None:
            meses = list(range(1, 13))
        else:
            for mes in meses:
                if mes < 1 or mes > 12:
                    raise HTTPException(status_code=400, detail=f"Mês inválido: {mes}")

        valores = []
        valores_mensais = {}
        meses_disponiveis = []
        
        for mes in meses:
            periodo = f"{mes:02d}/{ano}"
            if periodo in self._ipca_dict:
                valor = self._ipca_dict[periodo]
                valores.append(valor)
                valores_mensais[f"{mes:02d}"] = valor
                meses_disponiveis.append(f"{mes:02d}")
        
        if not valores:
            raise HTTPException(
                status_code=404, 
                detail=f"Nenhum valor IPCA encontrado para o ano {ano}"
            )
        
        media = sum(valores) / len(valores)
        
        return {
            "ano": ano,
            "media_ipca": round(media, 4),
            "total_meses": len(valores),
            "meses_disponiveis": meses_disponiveis,
            "valores_mensais": valores_mensais
        }

    def calcular_media_anual(self, ano: str, meses: List[int] = None) -> float:
        """Calcula a média do IPCA para um ano específico (retorna apenas o valor)."""
        self.verificar_disponibilidade()
        
        if meses is None:
            meses = list(range(1, 13))
        
        valores = []
        for mes in meses:
            periodo = f"{mes:02d}/{ano}"
            if periodo in self._ipca_dict:
                valores.append(self._ipca_dict[periodo])
        
        if not valores:
            raise ValueError(f"Nenhum valor IPCA encontrado para {ano}")
        
        return sum(valores) / len(valores)

    def obter_medias_multiplos_anos(self, anos: List[str], meses: List[int] = None) -> Dict:
        """Calcula médias do IPCA para múltiplos anos."""
        self.verificar_disponibilidade()
        
        resultado = {}
        for ano in anos:
            try:
                resultado[ano] = self.obter_media_anual(ano, meses)
            except HTTPException:
                resultado[ano] = {"erro": f"Dados não disponíveis para {ano}"}
        
        return resultado
    
    def corrigir_valor(self, valor: float, mes_inicial: str, ano_inicial: str, 
                      mes_final: str, ano_final: str) -> Dict:
        """Corrige um valor monetário pelo IPCA."""
        self.verificar_disponibilidade()
        
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

        if indice_ipca_inicial <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"IPCA inicial inválido ({indice_ipca_inicial}). Deve ser maior que zero."
            )
        
        if indice_ipca_final <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"IPCA final inválido ({indice_ipca_final}). Deve ser maior que zero."
            )

        valor_corrigido = valor * (indice_ipca_final / indice_ipca_inicial)
        valor_corrigido = round(valor_corrigido, 2)
        percentual_correcao = round(((indice_ipca_final / indice_ipca_inicial) - 1) * 100, 4)

        return {
            "valor_inicial": valor,
            "data_inicial": data_inicial,
            "data_final": data_final,
            "indice_ipca_inicial": indice_ipca_inicial,
            "indice_ipca_final": indice_ipca_final,
            "valor_corrigido": valor_corrigido,
            "percentual_correcao": percentual_correcao
        }
    
    @staticmethod
    def converter_valor_monetario_string(valor_str: str) -> float:
        """Converte um valor monetário em formato string brasileiro para float."""
        valor_str = str(valor_str).replace(".", "").replace(",", ".")
        is_negative = valor_str.startswith("-")
        if is_negative:
            valor_str = valor_str[1:]
        valor = float(valor_str)
        return -valor if is_negative else valor
    
    @staticmethod
    def formatar_valor_brasileiro(valor: float) -> str:
        """Formata um valor float para o padrão monetário brasileiro."""
        formatted = f"{valor:,.2f}"
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

# Instância do serviço para uso nos endpoints
def get_ipca_service() -> IPCAService:
    """
    Retorna a instância singleton do IPCAService.
    Usar esta função ao invés de importar ipca_service diretamente.
    """
    return IPCAService()