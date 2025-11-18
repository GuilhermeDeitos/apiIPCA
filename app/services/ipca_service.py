from app.utils.carregar_ipca import carregar_dados_ipca
from typing import Dict, Optional, Tuple, List
from fastapi import HTTPException
from collections import defaultdict

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
    
    def obter_ipca_periodo(self, periodo: str) -> float:
        """
        Obtém o valor do IPCA para um período no formato MM/AAAA.
        
        Args:
            periodo: Período no formato MM/AAAA
            
        Returns:
            Valor do IPCA para o período
            
        Raises:
            ValueError: Se o período não for encontrado
        """
        if periodo in self._ipca_dict:
            return self._ipca_dict[periodo]
        else:
            raise ValueError(f"IPCA não encontrado para {periodo}")
    
    def obter_ipca_por_periodo(self, mes: str, ano: str) -> float:
        """
        Obtém o valor do IPCA para um período específico (mes/ano separados).
        Método auxiliar para uso interno.
        
        Args:
            mes: Mês (01-12)
            ano: Ano (ex: 2023)
            
        Returns:
            Valor do IPCA
            
        Raises:
            ValueError: Se não encontrado
        """
        data_key = f"{mes}/{ano}"
        if data_key in self._ipca_dict:
            return self._ipca_dict[data_key]
        else:
            raise ValueError(f"IPCA não encontrado para {data_key}")
    
    def obter_media_anual(self, ano: str, meses: List[int] = None) -> Dict:
        """
        Calcula a média do IPCA para um ano específico.
        
        Args:
            ano: Ano para calcular a média (ex: 2023)
            meses: Lista de meses específicos (opcional). Se não fornecido, usa todos os meses disponíveis.

        Returns:
            Dicionário com ano, média e meses disponíveis
        """
        # Se meses não foi fornecido, usar todos os meses do ano
        if meses is None:
            meses = list(range(1, 13))
        else:
            # Validar meses fornecidos
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
        """
        Calcula a média do IPCA para um ano específico (retorna apenas o valor).
        
        Args:
            ano: Ano para calcular a média
            meses: Lista de meses específicos (opcional). Se não fornecido, usa todos os meses disponíveis.
            
        Returns:
            Média do IPCA para o ano/meses especificados
        """
        # Se meses não foi fornecido, usar todos os meses do ano
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
        """
        Calcula médias do IPCA para múltiplos anos.
        
        Args:
            anos: Lista de anos
            meses: Lista de meses específicos (opcional). Se não fornecido, usa todos os meses disponíveis.
            
        Returns:
            Dicionário com médias por ano
        """
        resultado = {}
        
        for ano in anos:
            try:
                resultado[ano] = self.obter_media_anual(ano, meses)
            except HTTPException:
                resultado[ano] = {"erro": f"Dados não disponíveis para {ano}"}
        
        return resultado
    
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
            HTTPException: Se os índices não forem encontrados ou inválidos
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

        # Validar índices IPCA
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

        # Cálculo da correção
        valor_corrigido = valor * (indice_ipca_final / indice_ipca_inicial)
        valor_corrigido = round(valor_corrigido, 2)
        
        # Calcular percentual de correção
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
    
    # ========== NOVOS MÉTODOS UTILITÁRIOS ==========
    
    @staticmethod
    def converter_valor_monetario_string(valor_str: str) -> float:
        """
        Converte um valor monetário em formato string brasileiro para float.
        
        Args:
            valor_str: Valor no formato brasileiro (ex: "1.200,00" ou "-1.200,00")
            
        Returns:
            Valor como float
            
        Examples:
            >>> IPCAService.converter_valor_monetario_string("1.200,00")
            1200.0
            >>> IPCAService.converter_valor_monetario_string("-500,50")
            -500.5
        """
        # Remover formatação brasileira (pontos de milhar e vírgula decimal)
        valor_str = str(valor_str).replace(".", "").replace(",", ".")
        
        # Tratar valores negativos
        is_negative = valor_str.startswith("-")
        if is_negative:
            valor_str = valor_str[1:]
        
        valor = float(valor_str)
        
        return -valor if is_negative else valor
    
    @staticmethod
    def formatar_valor_brasileiro(valor: float) -> str:
        """
        Formata um valor float para o padrão monetário brasileiro.
        
        Args:
            valor: Valor numérico
            
        Returns:
            String formatada no padrão BR (ex: "1.200,00")
            
        Examples:
            >>> IPCAService.formatar_valor_brasileiro(1200.0)
            "1.200,00"
            >>> IPCAService.formatar_valor_brasileiro(-500.5)
            "-500,50"
        """
        # Formatar com 2 casas decimais e separadores
        formatted = f"{valor:,.2f}"
        
        # Trocar separadores (inglês -> português)
        # 1,200.00 -> 1.200,00
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

# Instância do serviço para uso nos endpoints
ipca_service = IPCAService()