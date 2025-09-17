import json
import os
from typing import Dict, Tuple, Any, Optional, AsyncGenerator
import aiohttp
import asyncio
import logging
from datetime import datetime
from collections import defaultdict

# Configurações
BASE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
IPCA_FILE_PATH = os.path.join(BASE_PATH, "data", "ipca.json")
API_CRAWLER_URL = os.environ.get('API_CRAWLER_URL', 'http://localhost:8001')

logger = logging.getLogger(__name__)

async def consultar_transparencia_streaming(data_inicio: str, data_fim: str, tipo_correcao: str = "mensal", ipca_referencia: str = None) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Consulta dados do Portal da Transparência com suporte a streaming.
    Envia dados parciais conforme disponíveis.
    """
    # Importar o serviço IPCA aqui para evitar importação circular
    from app.services.ipca_service import ipca_service
    
    # Determinar período base do IPCA
    if ipca_referencia:
        # Se foi fornecido um período específico
        periodo_base = ipca_referencia
    else:
        # Usar mês/ano atual como período base
        hoje = datetime.now()
        if tipo_correcao == "anual":
            # Para correção anual, usar apenas o ano
            periodo_base = str(hoje.year)
        else:
            # Para correção mensal, usar mês/ano
            periodo_base = f"{hoje.month:02d}/{hoje.year}"
    
    # Obter IPCA base (referência)
    try:
        if tipo_correcao == "anual":
            # Para correção anual, verificar se é só ano ou ano com mês
            if "/" in periodo_base:
                # Se tem mês/ano, extrair apenas o ano
                _, ano_base = periodo_base.split('/')
                periodo_base = ano_base
            else:
                # Já é apenas o ano
                ano_base = periodo_base
            
            # Calcular IPCA médio anual para o ano de referência
            ipca_base = ipca_service.calcular_media_anual(ano_base)
            logger.info(f"IPCA médio anual de referência ({ano_base}): {ipca_base}")
        else:
            # Para correção mensal, usar período completo
            if "/" not in periodo_base:
                # Se passou apenas ano para correção mensal, usar dezembro como padrão
                periodo_base = f"12/{periodo_base}"
                logger.info(f"Período base ajustado para: {periodo_base}")
            
            mes_base, ano_base = periodo_base.split('/')
            ipca_base = ipca_service.obter_ipca_por_periodo(mes_base, ano_base)
            logger.info(f"IPCA de referência ({periodo_base}): {ipca_base}")
            
    except Exception as e:
        logger.error(f"Erro ao obter IPCA de referência para {periodo_base}: {e}")
        raise Exception(f"Não foi possível obter o IPCA de referência para {periodo_base}")

    # Contadores globais para estatísticas
    total_dados_nao_processados = []
    
    async with aiohttp.ClientSession() as session:
        # Fazer a requisição inicial
        payload = {
            "data_inicio": data_inicio,
            "data_fim": data_fim
        }
        
        try:
            logger.debug(f"Fazendo requisição inicial para {API_CRAWLER_URL}/consultar")
            async with session.post(f"{API_CRAWLER_URL}/consultar", json=payload) as response:
                if response.status != 200 and response.status != 202:
                    error_text = await response.text()
                    raise Exception(f"Erro na API crawler: Status {response.status} - {error_text}")
                
                result = await response.json()
                logger.debug(f"Resposta inicial: {result}")
                
                # Se é processamento síncrono (um único ano)
                if result.get("processamento") == "sincrono":
                    logger.info("Processamento síncrono detectado (ano único)")
                    
                    # Para processamento síncrono, os dados vêm organizados por ano
                    if "dados_por_ano" in result:
                        dados_por_ano = result["dados_por_ano"]
                        todos_dados = []
                        
                        for ano_str, info_ano in dados_por_ano.items():
                            # Verificar se é um objeto com estrutura ou lista direta
                            if isinstance(info_ano, dict) and "dados" in info_ano:
                                dados_ano = info_ano["dados"]
                                total_registros_ano = info_ano.get("total_registros", len(dados_ano))
                            elif isinstance(info_ano, list):
                                dados_ano = info_ano
                                total_registros_ano = len(dados_ano)
                            else:
                                logger.warning(f"Estrutura desconhecida para ano {ano_str}")
                                dados_ano = []
                                total_registros_ano = 0
                            
                            logger.info(f"Processando dados do ano {ano_str}: {total_registros_ano} registros")
                            
                            # Processar dados com correção IPCA
                            dados_corrigidos, dados_nao_processados = processar_correcao_dados(
                                dados_ano, 
                                ipca_base, 
                                periodo_base, 
                                ipca_service, 
                                tipo_correcao,
                                ano_contexto=int(ano_str)
                            )
                            
                            todos_dados.extend(dados_corrigidos)
                            total_dados_nao_processados.extend(dados_nao_processados)
                            
                            # Enviar dados parciais
                            yield {
                                "status": "parcial",
                                "ano_processado": int(ano_str),
                                "total_registros_ano": len(dados_corrigidos),
                                "total_nao_processados_ano": len(dados_nao_processados),
                                "dados": dados_corrigidos
                            }
                        
                        # Enviar resposta final
                        yield {
                            "status": "completo",
                            "total_registros": len(todos_dados),
                            "total_nao_processados": len(total_dados_nao_processados),
                            "dados": todos_dados,
                            "dados_nao_processados": total_dados_nao_processados,
                            "periodo_base_ipca": periodo_base,
                            "ipca_referencia": ipca_base,
                            "tipo_correcao": tipo_correcao,
                            "dados_por_ano": reorganizar_dados_por_ano(todos_dados)
                        }
                    else:
                        logger.error("Resposta síncrona sem dados_por_ano")
                        yield {
                            "status": "erro",
                            "erro": "Formato de resposta inválido"
                        }
                
                # Se é processamento assíncrono (múltiplos anos)
                elif "id_consulta" in result:
                    logger.info(f"Processamento assíncrono iniciado. ID: {result['id_consulta']}")
                    id_consulta = result["id_consulta"]
                    anos_ja_processados = set()
                    todos_dados = []
                    tentativas_sem_mudanca = 0
                    max_tentativas_sem_mudanca = 30  # Aumentar timeout para 60 segundos
                    
                    while True:
                        await asyncio.sleep(2)  # Aguardar 2 segundos entre verificações
                        
                        # Verificar status da consulta
                        async with session.get(f"{API_CRAWLER_URL}/status-consulta/{id_consulta}") as status_response:
                            if status_response.status != 200:
                                error_text = await status_response.text()
                                raise Exception(f"Erro ao verificar status: {error_text}")
                            
                            status_data = await status_response.json()
                            logger.debug(f"Status da consulta: {status_data.get('status', 'desconhecido')}")
                            
                            # Verificar se há dados disponíveis em diferentes estruturas possíveis
                            dados_disponiveis = False
                            
                            # Tentar dados_por_ano primeiro
                            if "dados_por_ano" in status_data:
                                dados_por_ano = status_data["dados_por_ano"]
                                dados_disponiveis = True
                            # Se não, tentar dados_parciais_por_ano
                            elif "dados_parciais_por_ano" in status_data:
                                dados_por_ano = status_data["dados_parciais_por_ano"]
                                dados_disponiveis = True
                                logger.debug("Usando dados_parciais_por_ano")
                            else:
                                dados_por_ano = {}
                            
                            if dados_disponiveis and dados_por_ano:
                                novos_anos_processados = False
                                
                                for ano_str, info_ano in dados_por_ano.items():
                                    # Verificar se já processamos esse ano
                                    if ano_str in anos_ja_processados:
                                        continue
                                    
                                    # Extrair dados do ano dependendo da estrutura
                                    dados_ano = None
                                    
                                    if isinstance(info_ano, dict):
                                        # Estrutura com metadados
                                        if "dados" in info_ano and info_ano["dados"]:
                                            dados_ano = info_ano["dados"]
                                            total_registros = info_ano.get("total_registros", len(dados_ano))
                                            logger.debug(f"Ano {ano_str} tem estrutura com metadados: {total_registros} registros")
                                        else:
                                            logger.debug(f"Ano {ano_str} tem estrutura mas sem dados")
                                            continue
                                    elif isinstance(info_ano, list) and info_ano:
                                        # Lista direta de dados
                                        dados_ano = info_ano
                                        total_registros = len(dados_ano)
                                        logger.debug(f"Ano {ano_str} é lista direta: {total_registros} registros")
                                    else:
                                        logger.debug(f"Ano {ano_str} tem formato inesperado: {type(info_ano)}")
                                        continue
                                    
                                    # Se temos dados, processar
                                    if dados_ano:
                                        logger.info(f"Processando dados do ano {ano_str}: {len(dados_ano)} registros")
                                        anos_ja_processados.add(ano_str)
                                        novos_anos_processados = True
                                        
                                        # Processar dados com correção IPCA
                                        dados_corrigidos, dados_nao_processados = processar_correcao_dados(
                                            dados_ano, 
                                            ipca_base, 
                                            periodo_base, 
                                            ipca_service, 
                                            tipo_correcao,
                                            ano_contexto=int(ano_str)
                                        )
                                        
                                        todos_dados.extend(dados_corrigidos)
                                        total_dados_nao_processados.extend(dados_nao_processados)
                                        
                                        # Enviar dados parciais
                                        yield {
                                            "status": "parcial",
                                            "ano_processado": int(ano_str),
                                            "total_registros_ano": len(dados_corrigidos),
                                            "total_nao_processados_ano": len(dados_nao_processados),
                                            "dados": dados_corrigidos
                                        }
                                
                                if not novos_anos_processados:
                                    tentativas_sem_mudanca += 1
                                    logger.debug(f"Sem novos dados. Tentativa {tentativas_sem_mudanca}/{max_tentativas_sem_mudanca}")
                                else:
                                    tentativas_sem_mudanca = 0
                            else:
                                tentativas_sem_mudanca += 1
                                logger.debug(f"Sem dados disponíveis. Tentativa {tentativas_sem_mudanca}/{max_tentativas_sem_mudanca}")
                            
                            # Verificar se todos os anos foram processados
                            if status_data.get("status") == "concluido":
                                logger.info("Consulta marcada como concluída")
                                
                                # Processar quaisquer dados restantes (verificar ambas estruturas)
                                for key in ["dados_por_ano", "dados_parciais_por_ano"]:
                                    if key in status_data:
                                        dados_por_ano = status_data[key]
                                        for ano_str, info_ano in dados_por_ano.items():
                                            if ano_str not in anos_ja_processados:
                                                # Extrair dados
                                                dados_ano = None
                                                if isinstance(info_ano, dict) and "dados" in info_ano and info_ano["dados"]:
                                                    dados_ano = info_ano["dados"]
                                                elif isinstance(info_ano, list) and info_ano:
                                                    dados_ano = info_ano
                                                
                                                if dados_ano:
                                                    logger.info(f"Processando dados finais do ano {ano_str}: {len(dados_ano)} registros")
                                                    
                                                    # Processar dados com correção IPCA
                                                    dados_corrigidos, dados_nao_processados = processar_correcao_dados(
                                                        dados_ano, 
                                                        ipca_base, 
                                                        periodo_base, 
                                                        ipca_service, 
                                                        tipo_correcao,
                                                        ano_contexto=int(ano_str)
                                                    )
                                                    
                                                    todos_dados.extend(dados_corrigidos)
                                                    total_dados_nao_processados.extend(dados_nao_processados)
                                                    
                                                    # Enviar dados parciais finais
                                                    yield {
                                                        "status": "parcial",
                                                        "ano_processado": int(ano_str),
                                                        "total_registros_ano": len(dados_corrigidos),
                                                        "total_nao_processados_ano": len(dados_nao_processados),
                                                        "dados": dados_corrigidos
                                                    }
                                
                                # Enviar resposta final
                                yield {
                                    "status": "completo",
                                    "total_registros": len(todos_dados),
                                    "total_nao_processados": len(total_dados_nao_processados),
                                    "dados": todos_dados,
                                    "dados_nao_processados": total_dados_nao_processados,
                                    "periodo_base_ipca": periodo_base,
                                    "ipca_referencia": ipca_base,
                                    "tipo_correcao": tipo_correcao,
                                    "dados_por_ano": reorganizar_dados_por_ano(todos_dados)
                                }
                                break
                            
                            # Log de progresso
                            if len(anos_ja_processados) > 0:
                                logger.info(f"Processando - Anos concluídos: {sorted([int(a) for a in anos_ja_processados])}")
                            
                            # Se passou muito tempo sem mudanças e não está concluído
                            if tentativas_sem_mudanca >= max_tentativas_sem_mudanca:
                                logger.warning(f"Timeout esperando por novos dados após {tentativas_sem_mudanca * 2} segundos")
                                
                                # Se temos dados, retornar o que foi coletado
                                if todos_dados:
                                    yield {
                                        "status": "completo",
                                        "total_registros": len(todos_dados),
                                        "total_nao_processados": len(total_dados_nao_processados),
                                        "dados": todos_dados,
                                        "dados_nao_processados": total_dados_nao_processados,
                                        "periodo_base_ipca": periodo_base,
                                        "ipca_referencia": ipca_base,
                                        "tipo_correcao": tipo_correcao,
                                        "observacao": "Processamento parcial - timeout"
                                    }
                                else:
                                    yield {
                                        "status": "erro",
                                        "erro": "Timeout sem dados processados"
                                    }
                                break
                
                else:
                    # Formato não reconhecido
                    raise Exception(f"Formato de resposta não reconhecido: {result}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"Erro de conexão com API crawler: {e}")
            raise Exception(f"Erro ao conectar com API de coleta de dados: {str(e)}")
        except Exception as e:
            logger.error(f"Erro no processamento: {e}")
            raise
        
def processar_correcao_dados(dados: list, ipca_base: float, periodo_base: str, 
                            ipca_service: Any, tipo_correcao: str = "mensal", 
                            ano_contexto: int = None) -> Tuple[list, list]:
    """
    Processa correção monetária dos dados mantendo a estrutura original.
    
    Args:
        dados: Lista de dados a serem corrigidos
        ipca_base: Valor do IPCA de referência (destino)
        periodo_base: Período de referência (MM/AAAA)
        ipca_service: Serviço do IPCA
        tipo_correcao: "mensal" ou "anual"
        ano_contexto: Ano dos dados sendo processados
        
    Returns:
        Tupla contendo (dados_corrigidos, dados_nao_processados)
    """
    dados_corrigidos = []
    dados_nao_processados = []
    
    # Se temos ano_contexto, todos os dados são desse ano
    if ano_contexto:
        logger.info(f"Processando dados do ano {ano_contexto}")
    
    # Verificar estrutura dos dados para debug
    if dados and len(dados) > 0:
        logger.debug(f"Exemplo de estrutura dos dados: {list(dados[0].keys())}")
    
    # Coletar todos os períodos únicos nos dados para calcular médias
    periodos_por_ano = defaultdict(set)
    
    # Se temos ano_contexto, usar ele diretamente
    if ano_contexto:
        # Para correção anual com ano_contexto, considerar o ano todo
        if tipo_correcao == "anual":
            periodos_por_ano[str(ano_contexto)] = set(range(1, 13))
        else:
            # Para correção mensal, ainda precisamos identificar os meses nos dados
            for item in dados:
                mes_dado = None
                if "MES" in item:
                    mes_dado = str(item["MES"])
                elif "mes" in item:
                    mes_dado = str(item["mes"])
                
                if mes_dado and mes_dado.isdigit():
                    periodos_por_ano[str(ano_contexto)].add(int(mes_dado))
                else:
                    # Se não tem mês, usar todos os meses
                    periodos_por_ano[str(ano_contexto)] = set(range(1, 13))
                    break
    else:
        # Sem ano_contexto, tentar extrair dos dados
        for item in dados:
            ano_dado = None
            mes_dado = None
            
            # Extrair ano dos dados
            if "ANO" in item:
                ano_dado = str(item["ANO"])
            elif "ano" in item:
                ano_dado = str(item["ano"])
            elif "_ano_validado" in item:
                ano_dado = str(item["_ano_validado"])
            
            # Extrair mês
            if "MES" in item:
                mes_dado = str(item["MES"])
            elif "mes" in item:
                mes_dado = str(item["mes"])
            
            if ano_dado and ano_dado.isdigit():
                if mes_dado and mes_dado.isdigit():
                    periodos_por_ano[ano_dado].add(int(mes_dado))
                else:
                    periodos_por_ano[ano_dado] = set(range(1, 13))
    
    # Calcular IPCAs médios anuais quando necessário
    ipca_medios_anuais = {}
    if tipo_correcao == "anual":
        for ano, meses in periodos_por_ano.items():
            if meses:
                meses_lista = sorted(list(meses))
                ipca_medio = ipca_service.calcular_media_anual(ano, meses_lista)
                if ipca_medio:
                    ipca_medios_anuais[ano] = ipca_medio
                    logger.info(f"IPCA médio anual para {ano}: {ipca_medio}")

    # Lista de campos monetários que devem ser corrigidos
    campos_monetarios = [
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

    for item in dados:
        motivo_nao_processado = None
        
        try:
            # Criar cópia do item original
            item_corrigido = item.copy()
            
            # Determinar ano do dado
            ano_dado = None
            
            # IMPORTANTE: Se temos ano_contexto, usar ele SEMPRE
            if ano_contexto:
                ano_dado = str(ano_contexto)
                logger.debug(f"Usando ano_contexto: {ano_dado}")
            else:
                # Só tentar extrair ano dos dados se não temos ano_contexto
                if "ANO" in item:
                    ano_dado = str(item["ANO"])
                elif "ano" in item:
                    ano_dado = str(item["ano"])
                elif "_ano_validado" in item:
                    ano_dado = str(item["_ano_validado"])
                
                # Validar ano
                if not ano_dado or not ano_dado.isdigit():
                    motivo_nao_processado = f"Ano inválido: {ano_dado}"
                    logger.warning(f"Ano inválido para o item: {item}")
                    dados_nao_processados.append({
                        "item_original": item,
                        "motivo": motivo_nao_processado
                    })
                    continue
            
            # Extrair mês se disponível
            mes_dado = None
            if "MES" in item:
                mes_dado = str(item["MES"])
            elif "mes" in item:
                mes_dado = str(item["mes"])
            
            # Para dados sem mês específico, usar dezembro como padrão
            if not mes_dado or not mes_dado.isdigit():
                mes_dado = "12"  # Usar dezembro como padrão para dados anuais
                logger.debug(f"Mês não encontrado, usando dezembro como padrão")
            
            # Determinar o IPCA do período do dado
            ipca_periodo = None
            
            if tipo_correcao == "mensal":
                # Correção mensal: usar IPCA do mês específico
                periodo_dado = f"{mes_dado.zfill(2)}/{ano_dado}"
                try:
                    ipca_periodo = ipca_service.obter_ipca_por_periodo(mes_dado.zfill(2), ano_dado)
                    logger.debug(f"IPCA mensal para {periodo_dado}: {ipca_periodo}")
                except:
                    motivo_nao_processado = f"IPCA não encontrado para {periodo_dado}"
                    logger.warning(f"IPCA não encontrado para {periodo_dado}, pulando item")
                    dados_nao_processados.append({
                        "item_original": item,
                        "motivo": motivo_nao_processado
                    })
                    continue
            elif tipo_correcao == "anual":
                # Correção anual: usar IPCA médio do ano (já calculado)
                ipca_periodo = ipca_medios_anuais.get(ano_dado)
                if not ipca_periodo:
                    motivo_nao_processado = f"IPCA médio anual não encontrado para {ano_dado}"
                    logger.warning(f"IPCA médio anual não encontrado para {ano_dado}, pulando item")
                    dados_nao_processados.append({
                        "item_original": item,
                        "motivo": motivo_nao_processado
                    })
                    continue
                logger.debug(f"Usando IPCA médio anual para {ano_dado}: {ipca_periodo}")
            
            # Calcular fator de correção
            fator_correcao = ipca_base / ipca_periodo
            
            # Aplicar correção em todos os campos monetários
            algum_valor_corrigido = False
            for campo in campos_monetarios:
                if campo in item_corrigido and item_corrigido[campo]:
                    try:
                        # Converter valor string para float
                        valor_str = str(item_corrigido[campo])
                        
                        # Remover formatação de moeda brasileira
                        valor_str = valor_str.replace(".", "").replace(",", ".")
                        
                        # Tratar valores negativos
                        is_negative = valor_str.startswith("-")
                        if is_negative:
                            valor_str = valor_str[1:]
                        
                        valor = float(valor_str)
                        
                        # Aplicar correção
                        valor_corrigido = valor * fator_correcao
                        
                        # Reaplica o sinal negativo se necessário
                        if is_negative:
                            valor_corrigido = -valor_corrigido
                        
                        # Formatar o valor de volta para string no formato brasileiro
                        valor_corrigido_str = f"{valor_corrigido:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        
                        # Atualizar o campo com o valor corrigido
                        item_corrigido[campo] = valor_corrigido_str
                        algum_valor_corrigido = True
                        
                        logger.debug(f"Campo {campo}: {item[campo]} -> {valor_corrigido_str} (fator: {fator_correcao})")
                        
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Não foi possível converter {campo}: {item_corrigido[campo]} - {e}")
                        continue
            
            # Se nenhum valor foi corrigido, adicionar aos não processados
            if not algum_valor_corrigido:
                motivo_nao_processado = "Nenhum campo monetário válido encontrado"
                dados_nao_processados.append({
                    "item_original": item,
                    "motivo": motivo_nao_processado
                })
                continue
            
            # Adicionar metadados de correção ao item
            item_corrigido["_correcao_aplicada"] = {
                "fator_correcao": fator_correcao,
                "ipca_periodo": ipca_periodo,
                "ipca_referencia": ipca_base,
                "periodo_referencia": periodo_base,
                "tipo_correcao": tipo_correcao
            }
            
            dados_corrigidos.append(item_corrigido)
            
        except Exception as e:
            logger.error(f"Erro ao processar item: {e}")
            logger.error(f"Item problemático: {item}")
            dados_nao_processados.append({
                "item_original": item,
                "motivo": f"Erro no processamento: {str(e)}"
            })
            continue
    
    logger.info(f"Processados {len(dados_corrigidos)} de {len(dados)} itens")
    if len(dados_nao_processados) > 0:
        logger.warning(f"{len(dados_nao_processados)} itens não foram processados")
    
    # IMPORTANTE: Sempre retornar uma tupla com dois valores
    return dados_corrigidos, dados_nao_processados                            

async def carregar_dados_portal_transparencia(data_inicio: str, data_fim: str, 
                                            tipo_correcao: str = "mensal", 
                                            ipca_referencia: str = None) -> Dict[str, Any]:
    """
    Carrega dados do Portal da Transparência com correção monetária.
    Versão simplificada que aguarda todos os dados.
    """
    todos_dados = []
    resultado_final = {}
    
    async for chunk in consultar_transparencia_streaming(data_inicio, data_fim, tipo_correcao, ipca_referencia):
        if chunk["status"] == "completo":
            resultado_final = chunk
            break
        elif chunk["status"] == "parcial":
            # Opcionalmente processar dados parciais
            logger.info(f"Recebido ano {chunk['ano_processado']} com {chunk['total_registros_ano']} registros")
    
    return resultado_final

async def carregar_dados_portal_transparencia(data_inicio: str, data_fim: str, 
                                            tipo_correcao: str = "mensal", 
                                            ipca_referencia: str = None) -> Dict[str, Any]:
    """
    Carrega dados do Portal da Transparência com correção monetária.
    Versão simplificada que aguarda todos os dados.
    """
    todos_dados = []
    resultado_final = {}
    
    async for chunk in consultar_transparencia_streaming(data_inicio, data_fim, tipo_correcao, ipca_referencia):
        if chunk["status"] == "completo":
            resultado_final = chunk
            break
        elif chunk["status"] == "parcial":
            # Opcionalmente processar dados parciais
            logger.info(f"Recebido ano {chunk['ano_processado']} com {chunk['total_registros_ano']} registros")
    
    return resultado_final

def reorganizar_dados_por_ano(dados: list) -> Dict[str, Any]:
    """
    Reorganiza os dados por ano, extraindo metadados de correção.
    
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
        # Determinar o ano do item
        ano = None
        if "_ano_validado" in item:
            ano = str(item["_ano_validado"])
        elif "ANO" in item:
            ano = str(item["ANO"])
        elif "ano" in item:
            ano = str(item["ano"])
        
        if not ano:
            continue
        
        # Extrair metadados de correção se existirem
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
            
            # Criar cópia do item sem os metadados internos
            item_limpo = {k: v for k, v in item.items() if k != "_correcao_aplicada"}
            dados_por_ano[ano]["dados"].append(item_limpo)
        else:
            dados_por_ano[ano]["dados"].append(item)
        
        dados_por_ano[ano]["total_registros"] += 1
    
    return dict(dados_por_ano)