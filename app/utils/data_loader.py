import ipeadatapy as ip
import pandas as pd
from typing import Dict, Tuple

def carregar_dados_ipca() -> Tuple[Dict[str, float], str]:
    """
    Carrega os dados do IPCA do IPEA.
    
    Returns:
        Tuple contendo:
        - Dicionário com datas como chaves e valores IPCA como valores
        - String com informação sobre o IPCA
    """
    try:
        # Carregar dados IPCA
        df = ip.timeseries("PRECOS12_IPCA12")
        df = df[["MONTH", "YEAR", "VALUE (-)"]]
        df = df.rename(columns={"VALUE (-)": "IPCA"})
        
        # Formatar datas
        df['MONTH'] = df['MONTH'].apply(lambda x: f"{x:02d}")  # Mês com dois dígitos
        df['Data'] = df['MONTH'].astype(str) + '/' + df['YEAR'].astype(str)
        
        # Criar dicionário
        ipca_dict = df.set_index('Data')['IPCA'].to_dict()
        
        # Informação sobre o IPCA
        ipca_info = "IPCA - geral - índice (dez. 1993 = 100)"
        
        return ipca_dict, ipca_info
        
    except Exception as e:
        print(f"Erro ao carregar dados IPCA: {e}")
        # Retornar dicionário vazio em caso de erro
        return {}, "Erro ao carregar dados IPCA"