from app.utils.data_loader import carregar_dados_portal_transparencia
from typing import Dict, Any
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class TransparenciaService:
    """Serviço para gerenciar operações do Portal da Transparência com correção IPCA"""
    
    async def consultar_dados_corrigidos(self, data_inicio: str, data_fim: str) -> Dict[str, Any]:
        """
        Consulta dados do Portal da Transparência e aplica correção monetária.
        
        Args:
            data_inicio: Data inicial no formato "MM/YYYY"
            data_fim: Data final no formato "MM/YYYY"
            
        Returns:
            Dados com correção monetária aplicada
        """
        try:
            logger.info(f"Iniciando consulta ao Portal da Transparência: {data_inicio} a {data_fim}")
            resultado = await carregar_dados_portal_transparencia(data_inicio, data_fim)
            logger.info(f"Consulta concluída. Total de registros: {resultado.get('total_registros', 0)}")
            return resultado
        except Exception as e:
            # Log do erro apenas para desenvolvedores
            logger.error(f"Erro ao consultar dados: {e}")
            raise Exception(f"Erro ao processar dados do Portal da Transparência: {str(e)}")

# Instância do serviço
transparencia_service = TransparenciaService()