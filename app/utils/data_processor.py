"""
Processador de dados do Portal da Transparência.
Responsabilidade única: Extrair, validar e organizar dados brutos.
"""

import logging
from typing import Dict, List, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class DataExtractor:
    """Extrai informações estruturadas dos dados brutos."""
    
    @staticmethod
    def extrair_ano(item: Dict[str, Any], ano_contexto: int = None) -> str:
        """
        Extrai o ano de um item de dados.
        
        Args:
            item: Item com dados
            ano_contexto: Ano fornecido externamente (tem prioridade)
            
        Returns:
            Ano como string ou None
        """
        if ano_contexto:
            return str(ano_contexto)
        
        # Tentar diferentes campos
        for campo in ["ANO", "ano", "_ano_validado"]:
            if campo in item and item[campo]:
                ano = str(item[campo])
                if ano.isdigit():
                    return ano
        
        return None
    
    @staticmethod
    def extrair_mes(item: Dict[str, Any]) -> str:
        """
        Extrai o mês de um item de dados.
        
        Args:
            item: Item com dados
            
        Returns:
            Mês como string (01-12) ou "12" como padrão
        """
        for campo in ["MES", "mes"]:
            if campo in item and item[campo]:
                mes = str(item[campo])
                if mes.isdigit():
                    return mes.zfill(2)
        
        return "12"  # Padrão: dezembro
    
    @staticmethod
    def extrair_dados_de_resposta(resposta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai dados da resposta da API, independente da estrutura.
        
        Args:
            resposta: Resposta da API
            
        Returns:
            Dicionário com dados por ano extraídos
        """
        # Tentar dados_por_ano primeiro
        if "dados_por_ano" in resposta:
            return resposta["dados_por_ano"]
        
        # Tentar dados_parciais_por_ano
        if "dados_parciais_por_ano" in resposta:
            logger.debug("Usando dados_parciais_por_ano")
            return resposta["dados_parciais_por_ano"]
        
        return {}


class DataOrganizer:
    """Organiza dados processados em estruturas adequadas."""
    
    @staticmethod
    def reorganizar_por_ano(dados: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Reorganiza lista de dados em estrutura por ano.
        
        Args:
            dados: Lista de dados processados
            
        Returns:
            Dicionário organizado por ano com metadados
        """
        dados_por_ano = defaultdict(lambda: {
            "dados": [],
            "total_registros": 0,
            "fator_correcao": None,
            "ipca_periodo": None,
            "ipca_referencia": None,
            "periodo_referencia": None,
            "tipo_correcao": None
        })
        
        for item in dados:
            # Extrair ano
            ano = DataExtractor.extrair_ano(item)
            
            if not ano or ano == "None":
                continue
            
            # Extrair metadados de correção
            if "_correcao_aplicada" in item:
                correcao = item["_correcao_aplicada"]
                
                # Atualizar metadados do ano (apenas uma vez)
                if dados_por_ano[ano]["fator_correcao"] is None:
                    dados_por_ano[ano].update({
                        "fator_correcao": correcao.get("fator_correcao"),
                        "ipca_periodo": correcao.get("ipca_periodo"),
                        "ipca_referencia": correcao.get("ipca_referencia"),
                        "periodo_referencia": correcao.get("periodo_referencia"),
                        "tipo_correcao": correcao.get("tipo_correcao")
                    })
                
                # Criar cópia sem metadados internos
                item_limpo = {k: v for k, v in item.items() if k != "_correcao_aplicada"}
                dados_por_ano[ano]["dados"].append(item_limpo)
            else:
                dados_por_ano[ano]["dados"].append(item)
            
            dados_por_ano[ano]["total_registros"] += 1
        
        return dict(dados_por_ano)