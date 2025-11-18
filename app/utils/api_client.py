"""
Cliente HTTP para comunicação com a API Crawler.
Responsabilidade única: Gerenciar requisições e respostas HTTP.
"""

import os
import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

API_CRAWLER_URL = os.environ.get('API_CRAWLER_URL', 'http://localhost:8001')


class ApiCrawlerClient:
    """Cliente para comunicação com a API Crawler."""
    
    def __init__(self, base_url: str = API_CRAWLER_URL):
        self.base_url = base_url
    
    async def iniciar_consulta(self, data_inicio: str, data_fim: str) -> Dict[str, Any]:
        """
        Inicia uma consulta na API Crawler.
        
        Args:
            data_inicio: Data de início (MM/AAAA)
            data_fim: Data de fim (MM/AAAA)
            
        Returns:
            Resposta da API com tipo de processamento e dados/ID
        """
        payload = {
            "data_inicio": data_inicio,
            "data_fim": data_fim
        }
        
        timeout = aiohttp.ClientTimeout(total=60)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/consultar",
                    json=payload,
                    timeout=timeout
                ) as response:
                    if response.status not in [200, 202]:
                        error_text = await response.text()
                        raise Exception(f"Erro na API crawler: Status {response.status} - {error_text}")
                    
                    result = await response.json()
                    logger.debug(f"Resposta da API: {result.get('processamento', 'desconhecido')}")
                    return result
                    
        except aiohttp.ClientError as e:
            logger.error(f"Erro de conexão com API crawler: {e}")
            raise Exception(f"Erro ao conectar com API de coleta de dados: {str(e)}")
    
    async def verificar_status_consulta(self, id_consulta: str) -> Dict[str, Any]:
        """
        Verifica o status de uma consulta em andamento.
        
        Args:
            id_consulta: ID da consulta
            
        Returns:
            Status atual da consulta com dados parciais
        """
        timeout = aiohttp.ClientTimeout(total=15)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/status-consulta/{id_consulta}",
                timeout=timeout
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Erro ao verificar status: {error_text}")
                
                return await response.json()
    
    async def verificar_status_api(self) -> Dict[str, Any]:
        """
        Verifica se a API Crawler está disponível.
        
        Returns:
            Status da API (disponível ou não)
        """
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/status",
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        dados = await response.json()
                        return {
                            "status": "ok",
                            "disponivel": True,
                            **dados
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "status": "erro",
                            "disponivel": False,
                            "erro": f"Status {response.status}: {error_text}"
                        }
        except aiohttp.ClientConnectionError as e:
            logger.warning(f"API Crawler não está acessível: {e}")
            return {
                "status": "erro",
                "disponivel": False,
                "erro": f"Não foi possível conectar: {str(e)}"
            }
        except asyncio.TimeoutError:
            logger.warning("Timeout ao verificar status da API Crawler")
            return {
                "status": "erro",
                "disponivel": False,
                "erro": "Timeout ao verificar status"
            }
        except Exception as e:
            logger.error(f"Erro inesperado ao verificar status: {e}")
            return {
                "status": "erro",
                "disponivel": False,
                "erro": str(e)
            }
    
    async def cancelar_consulta(self, id_consulta: str) -> Dict[str, Any]:
        """
        Cancela uma consulta em andamento.
        
        Args:
            id_consulta: ID da consulta a ser cancelada
            
        Returns:
            Resultado do cancelamento
        """
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/cancelar-consulta/{id_consulta}",
                    timeout=timeout
                ) as response:
                    if response.status == 200:
                        resultado = await response.json()
                        logger.info(f"Consulta {id_consulta} cancelada com sucesso")
                        return {
                            "cancelado": True,
                            **resultado
                        }
                    elif response.status == 404:
                        error_text = await response.text()
                        raise Exception(f"Consulta não encontrada: {error_text}")
                    else:
                        error_text = await response.text()
                        raise Exception(f"Erro ao cancelar consulta (status {response.status}): {error_text}")
        except aiohttp.ClientError as e:
            logger.error(f"Erro de conexão ao cancelar consulta {id_consulta}: {e}")
            raise Exception(f"Erro de conexão ao cancelar consulta: {str(e)}")
        except asyncio.TimeoutError:
            logger.error(f"Timeout ao cancelar consulta {id_consulta}")
            raise Exception("Timeout ao tentar cancelar a consulta")
        except Exception as e:
            logger.error(f"Erro ao cancelar consulta {id_consulta}: {e}")
            raise