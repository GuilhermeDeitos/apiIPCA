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
        
        # Obtém a última data IPCA disponível (não usa data futura)
        data_atual = datetime.now()
        # Para correção, usar uma data recente que provavelmente existe no IPCA
        # Por exemplo, 2 meses atrás para garantir que os dados já foram publicados
        if data_atual.month > 2:
            mes_correcao = str(data_atual.month - 2).zfill(2)
            ano_correcao = data_atual.year
        else:
            mes_correcao = str(data_atual.month + 10).zfill(2)  # 10, 11 ou 12 do ano anterior
            ano_correcao = data_atual.year - 1
        
        logger.info(f"Usando data de correção: {mes_correcao}/{ano_correcao}")
        
        if ano_inicio_int == ano_fim_int:
            # Consulta síncrona para um único ano
            return await _consulta_ano_unico(
                data_inicio, data_fim, ano_inicio_int, 
                mes_inicio, mes_fim, mes_correcao, ano_correcao
            )
        else:
            # Consulta assíncrona para múltiplos anos
            return await _consulta_multiplos_anos(
                data_inicio, data_fim, ano_inicio_int, ano_fim_int,
                mes_inicio, mes_fim, mes_correcao, ano_correcao
            )
            
    except Exception as e:
        logger.error(f"Erro ao consultar Portal da Transparência: {e}")
        raise Exception(f"Erro ao consultar Portal da Transparência: {e}")

async def _consulta_ano_unico(
    data_inicio: str, data_fim: str, ano: int, 
    mes_inicio: str, mes_fim: str, mes_correcao: str, ano_correcao: int
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
                    mes_correcao, str(ano_correcao)
                )
                
                return {
                    "dados": dados_corrigidos,
                    "total_registros": len(dados_corrigidos),
                    "anos_processados": [ano],
                    "correcao_aplicada": True,
                    "periodo_correcao": f"{mes_inicio}/{ano} -> {mes_correcao}/{ano_correcao}"
                }
            else:
                error_text = await response.text()
                raise Exception(f"Erro na API_crawler: {response.status} - {error_text}")

async def _consulta_multiplos_anos(
    data_inicio: str, data_fim: str, ano_inicio: int, ano_fim: int,
    mes_inicio: str, mes_fim: str, mes_correcao: str, ano_correcao: int
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
                
                # Processa a resposta de acordo com o novo formato
                if "dados_por_ano" in dados_finais and dados_finais["dados_por_ano"]:
                    # Aplica correção monetária aos dados coletados por ano
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
                        
                        # Extrai os dados corretamente baseado na estrutura
                        dados_para_corrigir = dados_ano.get("dados", []) if isinstance(dados_ano, dict) else dados_ano
                        
                        dados_corrigidos_por_ano[ano_str] = _aplicar_correcao_monetaria(
                            dados_para_corrigir, 
                            mes_ref, ano_str,
                            mes_correcao, str(ano_correcao)
                        )
                    
                    return {
                        "dados_por_ano": dados_corrigidos_por_ano,
                        "total_registros": dados_finais.get("total_registros", 0),
                        "anos_processados": dados_finais.get("anos_processados", []),
                        "periodos_processados": dados_finais.get("periodos_processados", []),
                        "resumo_por_ano": dados_finais.get("resumo_por_ano", {}),
                        "resumo_por_periodo": dados_finais.get("resumo_por_periodo", {}),
                        "status_coleta": dados_finais.get("status", "concluido"),
                        "correcao_aplicada": True,
                        "periodo_correcao": f"Meses específicos por ano -> {mes_correcao}/{ano_correcao}"
                    }
                else:
                    # Fallback para quando não há dados por ano estruturados
                    return {
                        "dados_por_ano": {},
                        "total_registros": dados_finais.get("total_registros", 0),
                        "anos_processados": dados_finais.get("anos_processados", []),
                        "periodos_processados": dados_finais.get("periodos_processados", []),
                        "status_coleta": dados_finais.get("status", "erro"),
                        "correcao_aplicada": False,
                        "mensagem": "Dados não disponíveis no formato esperado"
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
                    raise Exception(f"Erro na consulta: {status.get('mensagem', 'Erro desconhecido')}")
                
                # Verificar se a consulta foi concluída
                if status["status"] == "concluido":
                    # Retorna dados completos do status
                    return {
                        "status": "concluido",
                        "dados_por_ano": status.get("dados_por_ano", {}),
                        "anos_processados": status.get("anos_processados", []),
                        "periodos_processados": status.get("periodos_processados", []),
                        "resumo_por_ano": status.get("resumo_por_ano", {}),
                        "resumo_por_periodo": status.get("resumo_por_periodo", {}),
                        "total_registros": status.get("total_registros", 0)
                    }
                
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
                                    dados_coletados[str(ano)] = {
                                        "dados": dados_ano.get("dados", []),
                                        "total_registros": dados_ano.get("total_registros", 0),
                                        "ano": dados_ano.get("ano", ano),
                                        "processado_em": dados_ano.get("processado_em"),
                                        "periodos_processados": dados_ano.get("periodos_processados", [])
                                    }
                                    logger.info(f"Dados do ano {ano} coletados: {dados_ano.get('total_registros', 0)} registros")
                        except Exception as e:
                            logger.warning(f"Erro ao coletar dados do ano {ano}: {e}")
                
                anos_processados = anos_concluidos_agora
                
                # Verificar se todos os anos necessários foram processados
                anos_necessarios_processados = set(anos_necessarios).intersection(anos_processados)
                if len(anos_necessarios_processados) == len(anos_necessarios):
                    # Todos os anos foram processados
                    return {
                        "status": "parcial_completo",
                        "dados_por_ano": dados_coletados,
                        "anos_processados": list(anos_processados),
                        "anos_solicitados": anos_necessarios,
                        "total_registros": sum(dados.get("total_registros", 0) for dados in dados_coletados.values()),
                        "periodos_processados": status.get("periodos_processados", []),
                        "resumo_por_ano": status.get("resumo_por_ano", {}),
                        "resumo_por_periodo": status.get("resumo_por_periodo", {})
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
                            "periodos_processados": status.get("periodos_processados", []),
                            "resumo_por_ano": status.get("resumo_por_ano", {}),
                            "resumo_por_periodo": status.get("resumo_por_periodo", {}),
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
    
    # Log de debug das datas que serão usadas
    mes_inicial_formatado = mes_inicial.zfill(2)
    mes_final_formatado = mes_final.zfill(2)
    logger.info(f"Aplicando correção monetária: {mes_inicial_formatado}/{ano_inicial} -> {mes_final_formatado}/{ano_final}")
    
    # Verificar se as datas IPCA existem antes de processar
    datas_validas = True
    if ipca_disponivel:
        try:
            # Testar se as datas existem
            ipca_service.obter_valor_por_data(mes_inicial_formatado, ano_inicial)
            ipca_service.obter_valor_por_data(mes_final_formatado, ano_final)
        except Exception as e:
            logger.warning(f"Datas IPCA inválidas: {e}. Não será aplicada correção.")
            datas_validas = False
    
    campos_corrigidos_sucesso = 0
    total_campos_tentativas = 0
    
    for registro in dados:
        registro_corrigido = registro.copy()
        
        # Identifica campos monetários para correção
        campos_monetarios = _identificar_campos_monetarios(registro)
        
        # Adiciona metadados da tentativa de correção
        registro_corrigido["_metadata_correcao"] = {
            "data_base": f"{mes_inicial_formatado}/{ano_inicial}",
            "data_corrigida": f"{mes_final_formatado}/{ano_final}",
            "campos_identificados": campos_monetarios,
            "ipca_disponivel": ipca_disponivel,
            "datas_validas": datas_validas,
            "campos_corrigidos": []
        }
        
        if ipca_disponivel and datas_validas and campos_monetarios:
            for campo in campos_monetarios:
                valor_original = _extrair_valor_numerico(registro[campo])
                total_campos_tentativas += 1
                
                # Só processa valores maiores que zero
                if valor_original > 0:
                    try:
                        # Usar datas específicas para correção
                        correcao = ipca_service.corrigir_valor(
                            valor_original,
                            mes_inicial_formatado,
                            ano_inicial,
                            mes_final_formatado,
                            ano_final
                        )
                        
                        registro_corrigido[f"{campo}_corrigido"] = correcao["valor_corrigido"]
                        registro_corrigido[f"{campo}_original"] = valor_original
                        registro_corrigido[f"{campo}_percentual_correcao"] = correcao["percentual_correcao"]
                        registro_corrigido[f"{campo}_indice_inicial"] = correcao["indice_ipca_inicial"]
                        registro_corrigido[f"{campo}_indice_final"] = correcao["indice_ipca_final"]
                        
                        # Adiciona à lista de campos corrigidos com sucesso
                        registro_corrigido["_metadata_correcao"]["campos_corrigidos"].append(campo)
                        campos_corrigidos_sucesso += 1
                        
                        logger.debug(f"Campo {campo} corrigido: {valor_original} -> {correcao['valor_corrigido']} ({correcao['percentual_correcao']:.2f}%)")
                        
                    except Exception as e:
                        logger.warning(f"Erro ao corrigir campo {campo} (valor: {valor_original}) de {mes_inicial_formatado}/{ano_inicial} para {mes_final_formatado}/{ano_final}: {e}")
                        # Mantém valor original se não conseguir corrigir
                        registro_corrigido[f"{campo}_corrigido"] = valor_original
                        registro_corrigido[f"{campo}_original"] = valor_original
                        registro_corrigido[f"{campo}_percentual_correcao"] = 0.0
                        registro_corrigido[f"{campo}_erro_correcao"] = str(e)
                else:
                    # Para valores zero ou negativos, apenas copia o valor original sem tentar corrigir
                    registro_corrigido[f"{campo}_corrigido"] = valor_original
                    registro_corrigido[f"{campo}_original"] = valor_original
                    registro_corrigido[f"{campo}_percentual_correcao"] = 0.0
                    if valor_original == 0:
                        registro_corrigido[f"{campo}_observacao"] = "Valor zero - correção não aplicada"
                    else:
                        registro_corrigido[f"{campo}_observacao"] = "Valor negativo - correção não aplicada"
        else:
            # Se IPCA não estiver disponível ou datas inválidas, apenas copia os valores originais
            for campo in campos_monetarios:
                valor_original = _extrair_valor_numerico(registro[campo])
                registro_corrigido[f"{campo}_corrigido"] = valor_original
                registro_corrigido[f"{campo}_original"] = valor_original
                registro_corrigido[f"{campo}_percentual_correcao"] = 0.0
                if not ipca_disponivel:
                    registro_corrigido[f"{campo}_observacao"] = "Serviço IPCA indisponível"
                elif not datas_validas:
                    registro_corrigido[f"{campo}_observacao"] = "Datas IPCA inválidas"
        
        dados_corrigidos.append(registro_corrigido)
    
    # Log estatísticas de correção
    total_registros = len(dados_corrigidos)
    registros_com_correcao = sum(1 for r in dados_corrigidos 
                                if r.get("_metadata_correcao", {}).get("campos_corrigidos", []))
    
    logger.info(f"Correção monetária de {mes_inicial_formatado}/{ano_inicial} para {mes_final_formatado}/{ano_final}: {campos_corrigidos_sucesso}/{total_campos_tentativas} campos corrigidos em {registros_com_correcao}/{total_registros} registros")
    
    return dados_corrigidos

def _identificar_campos_monetarios(registro: Dict) -> List[str]:
    """Identifica campos que contêm valores monetários baseado nos nomes dos campos da nova estrutura"""
    campos_monetarios = []
    
    # Campos específicos que sabemos que são monetários baseados no exemplo
    campos_conhecidos_monetarios = [
        'ORÇAMENTO_INICIAL___LOA_(R$)',
        'TOTAL_ORÇAMENTÁRIO_(R$)_ATE_MES',
        'TOTAL_ORÇAMENTÁRIO_(R$)_NO_MES',
        'DISPONIBILIDADE_ORÇAMENTÁRIA_(R$)_ATE_MES',
        'DISPONIBILIDADE_ORÇAMENTÁRIA_(R$)_NO_MES',
        'EMPENHADO_(R$)_ATE_MES',
        'EMPENHADO_(R$)_NO_MES',
        'LIQUIDADO_(R$)_ATE_MES',
        'LIQUIDADO_(R$)_NO_MES',
        'PAGO_(R$)_ATE_MES',
        'PAGO_(R$)_NO_MES'
    ]
    
    # Termos específicos baseados na estrutura de dados mostrada
    termos_monetarios = [
        'orçament', 'empenhado', 'liquidado', 'pago', 'valor', 'total', 
        'disponibil', 'receita', 'despesa', 'crédito', 'débito',
        'r$', 'real', 'reais', 'monetário', 'financeiro', 'loa'
    ]
    
    for campo, valor in registro.items():
        # Primeiro verifica se é um campo conhecido
        if campo in campos_conhecidos_monetarios:
            # Verifica se tem valor numérico válido (incluindo zero)
            valor_numerico = _extrair_valor_numerico(valor)
            if valor_numerico >= 0:  # Aceita zero também para campos orçamentários
                campos_monetarios.append(campo)
            continue
        
        # Depois verifica por termos
        campo_lower = campo.lower()
        if any(termo in campo_lower for termo in termos_monetarios):
            # Verifica se o valor é numérico ou string numérica
            if isinstance(valor, (int, float)) or (isinstance(valor, str) and _is_numeric_string(valor)):
                # Só adiciona se o valor for não negativo (aceita zero)
                valor_numerico = _extrair_valor_numerico(valor)
                if valor_numerico >= 0:
                    campos_monetarios.append(campo)
    
    return campos_monetarios

def _is_numeric_string(s: str) -> bool:
    """Verifica se uma string representa um número, considerando formato brasileiro"""
    if not isinstance(s, str) or not s.strip():
        return False
    
    try:
        # Remove separadores de milhares (ponto), vírgulas decimais e símbolos monetários
        s_clean = s.replace('R$', '').replace('$', '').strip()
        
        # Formato brasileiro: pontos como separador de milhares, vírgula como decimal
        # Ex: "1.234.567,89" -> "1234567.89"
        if ',' in s_clean:
            # Se tem vírgula, assumimos formato brasileiro
            partes = s_clean.split(',')
            if len(partes) == 2:
                # Parte inteira e decimal
                parte_inteira = partes[0].replace('.', '')  # Remove pontos dos milhares
                parte_decimal = partes[1]
                s_clean = f"{parte_inteira}.{parte_decimal}"
            else:
                return False
        else:
            # Se não tem vírgula, remove apenas pontos (assumindo que são separadores de milhares)
            # Exceto se for o último ponto com exatamente 2 dígitos após ele (decimal)
            pontos = s_clean.count('.')
            if pontos > 0:
                ultima_parte = s_clean.split('.')[-1]
                if len(ultima_parte) == 2 and pontos == 1:
                    # Provavelmente é decimal (ex: "123.45")
                    pass  # Mantém como está
                else:
                    # Remove todos os pontos (separadores de milhares)
                    s_clean = s_clean.replace('.', '')
        
        # Remove espaços e outros caracteres não numéricos
        s_clean = ''.join(c for c in s_clean if c.isdigit() or c == '.' or c == '-')
        
        if not s_clean:
            return False
            
        float(s_clean)
        return True
    except (ValueError, AttributeError):
        return False

def _extrair_valor_numerico(valor) -> float:
    """Extrai valor numérico de diferentes formatos, considerando formato brasileiro"""
    if isinstance(valor, (int, float)):
        return float(valor)
    elif isinstance(valor, str):
        try:
            # Remove separadores e símbolos monetários
            valor_clean = valor.replace('R$', '').replace('$', '').strip()
            
            # Formato brasileiro: pontos como separador de milhares, vírgula como decimal
            if ',' in valor_clean:
                # Se tem vírgula, assumimos formato brasileiro
                partes = valor_clean.split(',')
                if len(partes) == 2:
                    # Parte inteira e decimal
                    parte_inteira = partes[0].replace('.', '')  # Remove pontos dos milhares
                    parte_decimal = partes[1]
                    valor_clean = f"{parte_inteira}.{parte_decimal}"
                else:
                    return 0.0
            else:
                # Se não tem vírgula, remove apenas pontos (assumindo que são separadores de milhares)
                # Exceto se for o último ponto com exatamente 2 dígitos após ele (decimal)
                pontos = valor_clean.count('.')
                if pontos > 0:
                    ultima_parte = valor_clean.split('.')[-1]
                    if len(ultima_parte) == 2 and pontos == 1:
                        # Provavelmente é decimal (ex: "123.45")
                        pass  # Mantém como está
                    else:
                        # Remove todos os pontos (separadores de milhares)
                        valor_clean = valor_clean.replace('.', '')
            
            # Remove espaços e outros caracteres não numéricos (exceto ponto e hífen)
            valor_clean = ''.join(c for c in valor_clean if c.isdigit() or c == '.' or c == '-')
            
            if not valor_clean:
                return 0.0
                
            return float(valor_clean)
        except (ValueError, AttributeError):
            return 0.0
    return 0.0