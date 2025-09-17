import ipeadatapy as ip
import logging
from typing import Dict, Tuple, List, Any

logger = logging.getLogger(__name__)

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
        df["data"] = df["MONTH"].astype(str).str.zfill(2) + "/" + df["YEAR"].astype(str)
        ipca_dict = df.set_index("data")["IPCA"].to_dict()
        
        info_ipca = f"Dados do IPCA carregados. Período: {df['YEAR'].min()}-{df['YEAR'].max()}"
        
        return ipca_dict, info_ipca
        
    except Exception as e:
        logger.error(f"Erro ao carregar dados IPCA: {e}")
        return {}, f"Erro ao carregar IPCA: {str(e)}"