"""
Calculadora de correção monetária pelo IPCA.
Responsabilidade única: Coordenar cálculos complexos de correção usando o IPCAService.
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

# Campos monetários que devem ser corrigidos
CAMPOS_MONETARIOS = [
    "ORCAMENTO_INICIAL_LOA",
    "TOTAL_ORCAMENTARIO_ATE_MES",
    "TOTAL_ORCAMENTARIO_NO_MES",
    "DISPONIBILIDADE_ORCAMENTARIA_ATE_MES",
    "DISPONIBILIDADE_ORCAMENTARIA_NO_MES",
    "EMPENHADO_ATE_MES",
    "EMPENHADO_NO_MES",
    "LIQUIDADO_ATE_MES",
    "LIQUIDADO_NO_MES",
    "PAGO_ATE_MES",
    "PAGO_NO_MES",
    "VALOR_TOTAL",
    "VALOR"
]


class IPCACalculator:
    """
    Calculadora de correção monetária pelo IPCA.
    Usa o IPCAService como fonte de dados e cálculos básicos.
    """
    
    def __init__(self, ipca_service: Any):
        self.ipca_service = ipca_service
    
    def determinar_periodo_base(self, ipca_referencia: str, tipo_correcao: str) -> str:
        """
        Determina o período base para correção.
        
        Args:
            ipca_referencia: Período fornecido ou None
            tipo_correcao: "mensal" ou "anual"
            
        Returns:
            Período base formatado
        """
        if ipca_referencia:
            return ipca_referencia
        
        hoje = datetime.now()
        
        if tipo_correcao == "anual":
            return str(hoje.year)
        else:
            return f"{hoje.month:02d}/{hoje.year}"
    
    def obter_ipca_base(self, periodo_base: str, tipo_correcao: str) -> float:
        """
        Obtém o IPCA de referência (base) usando o IPCAService.
        
        Args:
            periodo_base: Período de referência
            tipo_correcao: "mensal" ou "anual"
            
        Returns:
            Valor do IPCA base
        """
        try:
            if tipo_correcao == "anual":
                # Extrair apenas ano
                if "/" in periodo_base:
                    _, ano_base = periodo_base.split('/')
                else:
                    ano_base = periodo_base
                
                # Usar método do serviço
                ipca_base = self.ipca_service.calcular_media_anual(ano_base)
                logger.info(f"IPCA médio anual de referência ({ano_base}): {ipca_base}")
            else:
                # Garantir formato MM/AAAA
                if "/" not in periodo_base:
                    periodo_base = f"12/{periodo_base}"
                    logger.info(f"Período base ajustado para: {periodo_base}")
                
                mes_base, ano_base = periodo_base.split('/')
                
                # Usar método do serviço
                ipca_base = self.ipca_service.obter_ipca_por_periodo(mes_base, ano_base)
                logger.info(f"IPCA de referência ({periodo_base}): {ipca_base}")
            
            return ipca_base
            
        except Exception as e:
            logger.error(f"Erro ao obter IPCA de referência para {periodo_base}: {e}")
            raise Exception(f"Não foi possível obter o IPCA de referência para {periodo_base}")
    
    def calcular_ipcas_anuais(self, periodos_por_ano: Dict[str, set]) -> Dict[str, float]:
        """
        Calcula IPCAs médios anuais para todos os anos necessários usando o IPCAService.
        
        Args:
            periodos_por_ano: Dicionário {ano: set(meses)}
            
        Returns:
            Dicionário {ano: ipca_medio}
        """
        ipca_medios = {}
        
        for ano, meses in periodos_por_ano.items():
            if meses:
                meses_lista = sorted(list(meses))
                
                # Usar método do serviço
                ipca_medio = self.ipca_service.calcular_media_anual(ano, meses_lista)
                
                if ipca_medio:
                    ipca_medios[ano] = ipca_medio
                    logger.info(f"IPCA médio anual para {ano}: {ipca_medio}")
        
        return ipca_medios


class MonetaryCorrector:
    """Aplica correção monetária em dados usando IPCACalculator."""
    
    def __init__(self, ipca_calculator: IPCACalculator):
        self.calculator = ipca_calculator
    
    def processar_correcao_dados(
        self,
        dados: List[Dict[str, Any]],
        ipca_base: float,
        periodo_base: str,
        tipo_correcao: str = "mensal",
        ano_contexto: int = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Processa correção monetária dos dados mantendo a estrutura original.
        
        Args:
            dados: Lista de dados a serem corrigidos
            ipca_base: Valor do IPCA de referência
            periodo_base: Período de referência (MM/AAAA)
            tipo_correcao: "mensal" ou "anual"
            ano_contexto: Ano dos dados sendo processados
            
        Returns:
            Tupla (dados_corrigidos, dados_nao_processados)
        """
        from app.utils.data_processor import DataExtractor
        
        dados_corrigidos = []
        dados_nao_processados = []
        
        if ano_contexto:
            logger.info(f"Processando dados do ano {ano_contexto}")
        
        # Coletar períodos para cálculo de médias anuais
        periodos_por_ano = self._coletar_periodos(dados, ano_contexto)
        
        # Calcular IPCAs médios anuais se necessário
        ipca_medios_anuais = {}
        if tipo_correcao == "anual":
            ipca_medios_anuais = self.calculator.calcular_ipcas_anuais(periodos_por_ano)
        
        # Processar cada item
        for item in dados:
            try:
                item_corrigido, motivo_erro = self._processar_item(
                    item,
                    ipca_base,
                    periodo_base,
                    tipo_correcao,
                    ano_contexto,
                    ipca_medios_anuais
                )
                
                if item_corrigido:
                    dados_corrigidos.append(item_corrigido)
                else:
                    dados_nao_processados.append({
                        "item_original": item,
                        "motivo": motivo_erro
                    })
                    
            except Exception as e:
                logger.error(f"Erro ao processar item: {e}")
                dados_nao_processados.append({
                    "item_original": item,
                    "motivo": f"Erro no processamento: {str(e)}"
                })
        
        logger.info(f"Processados {len(dados_corrigidos)} de {len(dados)} itens")
        if dados_nao_processados:
            logger.warning(f"{len(dados_nao_processados)} itens não foram processados")
        
        return dados_corrigidos, dados_nao_processados
    
    def _coletar_periodos(self, dados: List[Dict], ano_contexto: int) -> Dict[str, set]:
        """Coleta períodos únicos nos dados para cálculo de médias."""
        from app.utils.data_processor import DataExtractor
        
        periodos_por_ano = defaultdict(set)
        
        if ano_contexto:
            periodos_por_ano[str(ano_contexto)] = set(range(1, 13))
        else:
            for item in dados:
                ano = DataExtractor.extrair_ano(item)
                mes = DataExtractor.extrair_mes(item)
                
                if ano and ano.isdigit():
                    if mes and mes.isdigit():
                        periodos_por_ano[ano].add(int(mes))
                    else:
                        periodos_por_ano[ano] = set(range(1, 13))
        
        return periodos_por_ano
    
    def _processar_item(
        self,
        item: Dict,
        ipca_base: float,
        periodo_base: str,
        tipo_correcao: str,
        ano_contexto: int,
        ipca_medios_anuais: Dict[str, float]
    ) -> Tuple[Dict, str]:
        """Processa um único item de dados."""
        from app.utils.data_processor import DataExtractor
        
        # Criar cópia do item
        item_corrigido = item.copy()
        
        # Extrair ano e mês
        ano_dado = DataExtractor.extrair_ano(item, ano_contexto)
        mes_dado = DataExtractor.extrair_mes(item)
        
        if not ano_dado or not ano_dado.isdigit():
            return None, f"Ano inválido: {ano_dado}"
        
        # Determinar IPCA do período
        ipca_periodo = self._obter_ipca_periodo(
            ano_dado,
            mes_dado,
            tipo_correcao,
            ipca_medios_anuais
        )
        
        if not ipca_periodo:
            return None, f"IPCA não encontrado para {mes_dado}/{ano_dado}"
        
        # Calcular fator de correção
        fator_correcao = ipca_base / ipca_periodo
        
        # Aplicar correção nos campos monetários
        algum_valor_corrigido = self._aplicar_correcao_campos(
            item_corrigido,
            fator_correcao
        )
        
        if not algum_valor_corrigido:
            return None, "Nenhum campo monetário válido encontrado"
        
        # Adicionar metadados
        item_corrigido["_correcao_aplicada"] = {
            "fator_correcao": fator_correcao,
            "ipca_periodo": ipca_periodo,
            "ipca_referencia": ipca_base,
            "periodo_referencia": periodo_base,
            "tipo_correcao": tipo_correcao
        }
        
        return item_corrigido, None
    
    def _obter_ipca_periodo(
        self,
        ano: str,
        mes: str,
        tipo_correcao: str,
        ipca_medios_anuais: Dict[str, float]
    ) -> float:
        """Obtém o IPCA do período do dado usando o IPCAService."""
        if tipo_correcao == "mensal":
            try:
                # Usar método do serviço
                return self.calculator.ipca_service.obter_ipca_por_periodo(mes, ano)
            except:
                return None
        else:  # anual
            return ipca_medios_anuais.get(ano)
    
    def _aplicar_correcao_campos(self, item: Dict, fator_correcao: float) -> bool:
        """Aplica correção em todos os campos monetários do item usando métodos do IPCAService."""
        algum_valor_corrigido = False
        
        for campo in CAMPOS_MONETARIOS:
            if campo in item and item[campo]:
                try:
                    # Usar método estático do serviço para conversão
                    valor = self.calculator.ipca_service.converter_valor_monetario_string(item[campo])
                    valor_corrigido = valor * fator_correcao
                    
                    # Usar método estático do serviço para formatação
                    item[campo] = self.calculator.ipca_service.formatar_valor_brasileiro(valor_corrigido)
                    algum_valor_corrigido = True
                except (ValueError, TypeError) as e:
                    logger.debug(f"Não foi possível converter {campo}: {item[campo]} - {e}")
                    continue
        
        return algum_valor_corrigido