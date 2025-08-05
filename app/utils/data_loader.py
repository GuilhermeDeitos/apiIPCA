import ipeadatapy as ip
import pandas as pd
import requests
import asyncio
import aiohttp
import logging
from typing import Dict, Tuple, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

API_CRAWLER_URL = "http://localhost:8001"  # URL da API_crawler

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

async def carregar_dados_portal_transparencia(data_inicio: str, data_fim: str) -> Dict[str, Any]:
    """
    Faz uma requisição para a API que contém o scrapper do Portal da Transparência.
    
    Args:
        data_inicio: Data inicial no formato "MM/YYYY"
        data_fim: Data final no formato "MM/YYYY"
    
    Returns:
        Dados do Portal da Transparência com correção monetária por período
    """
    try:
        mes_inicio, ano_inicio = data_inicio.split('/')
        mes_fim, ano_fim = data_fim.split('/')
        
        ano_inicio_int = int(ano_inicio)
        ano_fim_int = int(ano_fim)
        
        # Obtém a data atual para correção
        data_atual = datetime.now()
        mes_atual = data_atual.strftime("%m")
        ano_atual = data_atual.year
        
        if ano_inicio_int == ano_fim_int:
            # Consulta síncrona para um único ano
            return await _consulta_ano_unico(
                data_inicio, data_fim, ano_inicio_int, 
                mes_inicio, mes_fim, mes_atual, ano_atual
            )
        else:
            # Consulta assíncrona para múltiplos anos
            return await _consulta_multiplos_anos(
                data_inicio, data_fim, ano_inicio_int, ano_fim_int,
                mes_inicio, mes_fim, mes_atual, ano_atual
            )
            
    except Exception as e:
        logger.error(f"Erro ao consultar Portal da Transparência: {e}")
        raise Exception(f"Erro ao consultar Portal da Transparência: {e}")

async def _consulta_ano_unico(
    data_inicio: str, data_fim: str, ano: int, 
    mes_inicio: str, mes_fim: str, mes_atual: str, ano_atual: int
) -> Dict[str, Any]:
    """Consulta síncrona para um único ano"""
    async with aiohttp.ClientSession() as session:
        payload = {
            "data_inicio": data_inicio,
            "data_fim": data_fim
        }
        
        async with session.post(f"{API_CRAWLER_URL}/consultar", json=payload) as response:
            if response.status == 200:
                dados = await response.json()
                
                # Aplica correção monetária com dados mensais específicos
                dados_corrigidos = _aplicar_correcao_monetaria(
                    dados["dados"], 
                    mes_inicio, str(ano), 
                    mes_atual, str(ano_atual)
                )
                
                return {
                    "dados": dados_corrigidos,
                    "total_registros": len(dados_corrigidos),
                    "anos_processados": [ano],
                    "correcao_aplicada": True,
                    "periodo_correcao": f"{mes_inicio}/{ano} -> {mes_atual}/{ano_atual}"
                }
            else:
                error_text = await response.text()
                raise Exception(f"Erro na API_crawler: {response.status} - {error_text}")

async def _consulta_multiplos_anos(
    data_inicio: str, data_fim: str, ano_inicio: int, ano_fim: int,
    mes_inicio: str, mes_fim: str, mes_atual: str, ano_atual: int
) -> Dict[str, Any]:
    """Consulta assíncrona para múltiplos anos"""
    async with aiohttp.ClientSession() as session:
        payload = {
            "data_inicio": data_inicio,
            "data_fim": data_fim
        }
        
        # Inicia consulta assíncrona
        async with session.post(f"{API_CRAWLER_URL}/consultar", json=payload) as response:
            if response.status == 202:  # Processamento em background
                resultado = await response.json()
                id_consulta = resultado["id_consulta"]
                
                # Aguarda dados parciais ou completos
                dados_finais = await _aguardar_consulta_com_dados_parciais(
                    session, id_consulta, list(range(ano_inicio, ano_fim + 1))
                )
                
                # Aplica correção monetária aos dados coletados
                # Cada ano é corrigido com seu respectivo mês de referência
                dados_corrigidos_por_ano = {}
                for ano_str, dados_ano in dados_finais["dados_por_ano"].items():
                    ano_int = int(ano_str)
                    
                    # Determina o mês de referência para cada ano
                    if ano_int == ano_inicio:
                        mes_ref = mes_inicio
                    elif ano_int == ano_fim:
                        mes_ref = mes_fim
                    else:
                        mes_ref = "12"  # Dezembro para anos intermediários
                    
                    dados_corrigidos_por_ano[ano_str] = _aplicar_correcao_monetaria(
                        dados_ano["dados"], 
                        mes_ref, ano_str,
                        mes_atual, str(ano_atual)
                    )
                
                return {
                    "dados_por_ano": dados_corrigidos_por_ano,
                    "total_registros": dados_finais["total_registros"],
                    "anos_processados": dados_finais["anos_processados"],
                    "status_coleta": dados_finais["status"],
                    "correcao_aplicada": True,
                    "periodo_correcao": f"Meses específicos por ano -> {mes_atual}/{ano_atual}"
                }
            else:
                error_text = await response.text()
                raise Exception(f"Erro na API_crawler: {response.status} - {error_text}")

async def _aguardar_consulta_com_dados_parciais(session: aiohttp.ClientSession, id_consulta: str, anos_necessarios: List[int], timeout: int = 300) -> Dict:
    """
    Aguarda que pelo menos alguns anos sejam processados ou a consulta seja concluída
    """
    tempo_inicio = asyncio.get_event_loop().time()
    anos_processados = set()
    dados_coletados = {}
    
    while True:
        async with session.get(f"{API_CRAWLER_URL}/status-consulta/{id_consulta}") as response:
            if response.status == 200:
                status = await response.json()
                
                if status["status"] == "erro":
                    raise Exception(f"Erro na consulta: {status['mensagem']}")
                
                # Verificar se temos novos anos processados
                anos_concluidos_agora = set(status.get("anos_concluidos", []))
                novos_anos = anos_concluidos_agora - anos_processados
                
                # Coletar dados dos novos anos processados
                for ano in novos_anos:
                    if ano in anos_necessarios:
                        try:
                            async with session.get(f"{API_CRAWLER_URL}/consulta/{id_consulta}/ano/{ano}") as ano_response:
                                if ano_response.status == 200:
                                    dados_ano = await ano_response.json()
                                    dados_coletados[str(ano)] = dados_ano
                                    logger.info(f"Dados do ano {ano} coletados: {dados_ano['total_registros']} registros")
                        except Exception as e:
                            logger.warning(f"Erro ao coletar dados do ano {ano}: {e}")
                
                anos_processados = anos_concluidos_agora
                
                # Verificar se todos os anos necessários foram processados ou se a consulta foi concluída
                anos_necessarios_processados = set(anos_necessarios).intersection(anos_processados)
                if (len(anos_necessarios_processados) == len(anos_necessarios) or 
                    status["status"] == "concluido"):
                    
                    # Se a consulta foi concluída, buscar dados de todos os anos
                    if status["status"] == "concluido":
                        dados_coletados = {}
                        for ano in anos_necessarios:
                            if str(ano) in status.get("dados_por_ano", {}):
                                dados_coletados[str(ano)] = {
                                    "dados": status["dados_por_ano"][str(ano)]["dados"],
                                    "total_registros": status["dados_por_ano"][str(ano)]["total_registros"]
                                }
                    
                    # Retornar dados organizados
                    return {
                        "status": "concluido" if status["status"] == "concluido" else "parcial",
                        "dados_por_ano": dados_coletados,
                        "anos_processados": list(anos_processados),
                        "anos_solicitados": anos_necessarios,
                        "total_registros": sum(dados.get("total_registros", 0) for dados in dados_coletados.values())
                    }
                
                # Verificar timeout
                if asyncio.get_event_loop().time() - tempo_inicio > timeout:
                    if dados_coletados:
                        # Retornar dados parciais se temos algo
                        return {
                            "status": "timeout_parcial",
                            "dados_por_ano": dados_coletados,
                            "anos_processados": list(anos_processados),
                            "anos_solicitados": anos_necessarios,
                            "total_registros": sum(dados.get("total_registros", 0) for dados in dados_coletados.values()),
                            "mensagem": "Timeout atingido, retornando dados parciais disponíveis"
                        }
                    else:
                        raise Exception("Timeout: Nenhum dado foi processado no tempo esperado")
                
                await asyncio.sleep(3)  # Verifica a cada 3 segundos
            else:
                raise Exception(f"Erro ao verificar status: {response.status}")

def _aplicar_correcao_monetaria(
    dados: List[Dict], 
    mes_inicial: str, ano_inicial: str, 
    mes_final: str, ano_final: str
) -> List[Dict]:
    """Aplica correção monetária aos valores dos dados usando datas específicas"""
    # Verifica se há dados para processar
    if not dados:
        return []
    
    dados_corrigidos = []
    
    # Importa o serviço apenas quando necessário para evitar problemas circulares
    try:
        from app.services.ipca_service import ipca_service
        ipca_disponivel = True
    except ImportError:
        logger.warning("Serviço IPCA não disponível. Valores não serão corrigidos.")
        ipca_disponivel = False
    
    for registro in dados:
        registro_corrigido = registro.copy()
        
        # Identifica campos monetários para correção
        campos_monetarios = _identificar_campos_monetarios(registro)
        
        # Adiciona metadados da tentativa de correção
        registro_corrigido["_metadata_correcao"] = {
            "data_base": f"{mes_inicial}/{ano_inicial}",
            "data_corrigida": f"{mes_final}/{ano_final}",
            "campos_identificados": campos_monetarios,
            "ipca_disponivel": ipca_disponivel,
            "campos_corrigidos": []
        }
        
        if ipca_disponivel and campos_monetarios:
            for campo in campos_monetarios:
                valor_original = _extrair_valor_numerico(registro[campo])
                if valor_original and valor_original > 0:
                    try:
                        # Usar datas específicas para correção
                        correcao = ipca_service.corrigir_valor(
                            valor_original,
                            mes_inicial,
                            ano_inicial,
                            mes_final,
                            ano_final
                        )
                        
                        registro_corrigido[f"{campo}_corrigido"] = correcao["valor_corrigido"]
                        registro_corrigido[f"{campo}_original"] = valor_original
                        registro_corrigido[f"{campo}_percentual_correcao"] = correcao["percentual_correcao"]
                        
                        # Adiciona à lista de campos corrigidos com sucesso
                        registro_corrigido["_metadata_correcao"]["campos_corrigidos"].append(campo)
                        
                    except Exception as e:
                        logger.debug(f"Erro ao corrigir campo {campo} (valor: {valor_original}) de {mes_inicial}/{ano_inicial} para {mes_final}/{ano_final}: {e}")
                        # Mantém valor original se não conseguir corrigir
                        registro_corrigido[f"{campo}_corrigido"] = valor_original
                        registro_corrigido[f"{campo}_original"] = valor_original
                        registro_corrigido[f"{campo}_percentual_correcao"] = 0.0
                        registro_corrigido[f"{campo}_erro_correcao"] = str(e)
        else:
            # Se IPCA não estiver disponível, apenas copia os valores originais
            for campo in campos_monetarios:
                valor_original = _extrair_valor_numerico(registro[campo])
                registro_corrigido[f"{campo}_corrigido"] = valor_original
                registro_corrigido[f"{campo}_original"] = valor_original
                registro_corrigido[f"{campo}_percentual_correcao"] = 0.0
        
        dados_corrigidos.append(registro_corrigido)
    
    # Log estatísticas de correção
    total_registros = len(dados_corrigidos)
    registros_com_correcao = sum(1 for r in dados_corrigidos 
                                if r.get("_metadata_correcao", {}).get("campos_corrigidos", []))
    
    logger.info(f"Correção monetária aplicada de {mes_inicial}/{ano_inicial} para {mes_final}/{ano_final}: {registros_com_correcao}/{total_registros} registros corrigidos")
    
    return dados_corrigidos

def _identificar_campos_monetarios(registro: Dict) -> List[str]:
    """Identifica campos que contêm valores monetários"""
    campos_monetarios = []
    
    # Termos que indicam valores monetários
    termos_monetarios = [
        'orçament', 'empenhado', 'liquidado', 'pago', 'valor', 'total', 
        'disponibil', 'receita', 'despesa', 'crédito', 'débito',
        'r$', 'real', 'reais', 'monetário', 'financeiro'
    ]
    
    for campo, valor in registro.items():
        campo_lower = campo.lower()
        
        # Busca por campos que parecem conter valores monetários
        if any(termo in campo_lower for termo in termos_monetarios):
            # Verifica se o valor é numérico ou string numérica
            if isinstance(valor, (int, float)) or (isinstance(valor, str) and _is_numeric_string(valor)):
                # Só adiciona se o valor for positivo
                valor_numerico = _extrair_valor_numerico(valor)
                if valor_numerico > 0:
                    campos_monetarios.append(campo)
    
    return campos_monetarios

def _is_numeric_string(s: str) -> bool:
    """Verifica se uma string representa um número"""
    if not isinstance(s, str) or not s.strip():
        return False
    
    try:
        # Remove separadores de milhares, vírgulas e símbolos monetários
        s_clean = s.replace('.', '').replace(',', '.').replace('R$', '').replace('$', '').strip()
        
        # Remove espaços e outros caracteres não numéricos
        s_clean = ''.join(c for c in s_clean if c.isdigit() or c == '.' or c == '-')
        
        if not s_clean:
            return False
            
        float(s_clean)
        return True
    except (ValueError, AttributeError):
        return False

def _extrair_valor_numerico(valor) -> float:
    """Extrai valor numérico de diferentes formatos"""
    if isinstance(valor, (int, float)):
        return float(valor)
    elif isinstance(valor, str):
        try:
            # Remove separadores e símbolos monetários
            valor_clean = valor.replace('.', '').replace(',', '.').replace('R$', '').replace('$', '').strip()
            
            # Remove espaços e outros caracteres não numéricos (exceto ponto e hífen)
            valor_clean = ''.join(c for c in valor_clean if c.isdigit() or c == '.' or c == '-')
            
            if not valor_clean:
                return 0.0
                
            return float(valor_clean)
        except (ValueError, AttributeError):
            return 0.0
    return 0.0