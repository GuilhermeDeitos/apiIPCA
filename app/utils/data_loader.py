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
    Agora organizando dados por ano ao invés de por mês.
    
    Args:
        data_inicio: Data inicial no formato "MM/YYYY"
        data_fim: Data final no formato "MM/YYYY"
    
    Returns:
        Dados do Portal da Transparência com correção monetária organizados por ano
    """
    try:
        mes_inicio, ano_inicio = data_inicio.split('/')
        mes_fim, ano_fim = data_fim.split('/')
        
        ano_inicio_int = int(ano_inicio)
        ano_fim_int = int(ano_fim)
        
        # Obtém uma data recente para correção (não usa data futura)
        data_atual = datetime.now()
        if data_atual.month > 2:
            mes_correcao = str(data_atual.month - 2).zfill(2)
            ano_correcao = data_atual.year
        else:
            mes_correcao = str(data_atual.month + 10).zfill(2)
            ano_correcao = data_atual.year - 1
        
        logger.info(f"Carregando dados por ano de {mes_inicio}/{ano_inicio} até {mes_fim}/{ano_fim}. Correção para {mes_correcao}/{ano_correcao}")
        
        # Sempre usar consulta organizada por anos
        return await _consulta_organizada_por_anos(
            data_inicio, data_fim, ano_inicio_int, ano_fim_int,
            mes_inicio, mes_fim, mes_correcao, ano_correcao
        )
            
    except Exception as e:
        logger.error(f"Erro ao consultar Portal da Transparência: {e}")
        raise Exception(f"Erro ao consultar Portal da Transparência: {e}")

async def _consulta_organizada_por_anos(
    data_inicio: str, data_fim: str, ano_inicio: int, ano_fim: int,
    mes_inicio: str, mes_fim: str, mes_correcao: str, ano_correcao: int
) -> Dict[str, Any]:
    """Consulta organizada por anos com correção monetária baseada em média anual do IPCA"""
    async with aiohttp.ClientSession() as session:
        payload = {
            "data_inicio": data_inicio,
            "data_fim": data_fim
        }
        
        # Fazer consulta na API_crawler
        async with session.post(f"{API_CRAWLER_URL}/consultar", json=payload) as response:
            if response.status == 200:
                # Resposta síncrona (um único ano)
                dados = await response.json()
                
                # Verificar se já vem organizado por ano
                if "dados_por_ano" in dados:
                    dados_por_ano = dados["dados_por_ano"]
                else:
                    # Organizar dados por ano se não vieram assim
                    dados_originais = dados.get("dados", [])
                    dados_por_ano = {
                        str(ano_inicio): {
                            "dados": dados_originais,
                            "total_registros": len(dados_originais),
                            "mes_inicio": int(mes_inicio),
                            "mes_fim": int(mes_fim),
                            "processado_em": datetime.now().isoformat()
                        }
                    }
                
                # Aplicar correção monetária por ano usando média anual
                dados_corrigidos = _aplicar_correcao_monetaria_por_ano_com_media(
                    dados_por_ano, 
                    ano_inicio, ano_fim,
                    ano_correcao
                )
                
                return {
                    "dados_por_ano": dados_corrigidos,
                    "dados": dados.get("dados", []),  # Mantém compatibilidade
                    "total_registros": sum(dados_ano.get("total_registros", 0) for dados_ano in dados_corrigidos.values()),
                    "anos_processados": [ano_inicio],
                    "correcao_aplicada": True,
                    "periodo_correcao": f"Anos {ano_inicio}-{ano_fim} -> {ano_correcao} (média anual)",
                    "status": "concluido",
                    "organizacao": "por_ano"
                }
                
            elif response.status == 202:
                # Processamento assíncrono (múltiplos anos)
                resultado = await response.json()
                id_consulta = resultado["id_consulta"]
                
                # Aguardar conclusão
                dados_finais = await _aguardar_consulta_por_anos(
                    session, id_consulta, list(range(ano_inicio, ano_fim + 1))
                )
                
                # Aplicar correção monetária por ano usando média anual
                if "dados_por_ano" in dados_finais and dados_finais["dados_por_ano"]:
                    dados_corrigidos = _aplicar_correcao_monetaria_por_ano_com_media(
                        dados_finais["dados_por_ano"],
                        ano_inicio, ano_fim,
                        ano_correcao
                    )
                    
                    return {
                        "dados_por_ano": dados_corrigidos,
                        "total_registros": dados_finais.get("total_registros", 0),
                        "anos_processados": dados_finais.get("anos_processados", []),
                        "resumo_por_ano": dados_finais.get("resumo_por_ano", {}),
                        "resumo_consolidado": dados_finais.get("resumo_consolidado", {}),
                        "status_coleta": dados_finais.get("status", "concluido"),
                        "correcao_aplicada": True,
                        "periodo_correcao": f"Anos {ano_inicio}-{ano_fim} -> {ano_correcao} (média anual)",
                        "organizacao": "por_ano"
                    }
                else:
                    return {
                        "dados_por_ano": {},
                        "total_registros": 0,
                        "anos_processados": [],
                        "status_coleta": "erro",
                        "correcao_aplicada": False,
                        "mensagem": "Nenhum dado encontrado",
                        "organizacao": "por_ano"
                    }
            else:
                error_text = await response.text()
                raise Exception(f"Erro na API_crawler: {response.status} - {error_text}")

def _aplicar_correcao_monetaria_por_ano_com_media(
    dados_por_ano: Dict[str, Dict], 
    ano_inicio: int, ano_fim: int,
    ano_correcao: int
) -> Dict[str, Dict]:
    """
    Aplica correção monetária organizando por ano usando média anual do IPCA.
    
    Args:
        dados_por_ano: Dados organizados por ano
        ano_inicio: Ano inicial da consulta
        ano_fim: Ano final da consulta
        ano_correcao: Ano para correção
    
    Returns:
        Dados corrigidos organizados por ano
    """
    dados_corrigidos_por_ano = {}
    
    # Carregar médias anuais do IPCA uma única vez
    medias_ipca = _calcular_medias_anuais_ipca()
    
    for ano_str, info_ano in dados_por_ano.items():
        ano_int = int(ano_str)
        
        # Extrair dados do ano
        if isinstance(info_ano, dict):
            dados_ano = info_ano.get("dados", [])
            mes_inicio_ano = info_ano.get("mes_inicio")
            mes_fim_ano = info_ano.get("mes_fim")
            total_registros = info_ano.get("total_registros", 0)
            processado_em = info_ano.get("processado_em")
        else:
            # Fallback para formato antigo
            dados_ano = info_ano if isinstance(info_ano, list) else []
            mes_inicio_ano = None
            mes_fim_ano = None
            total_registros = len(dados_ano)
            processado_em = None
        
        # Aplicar correção usando média anual
        dados_corrigidos, fator_correcao, media_ano_base, media_ano_correcao = _aplicar_correcao_monetaria_com_media_anual(
            dados_ano, 
            ano_int,
            ano_correcao,
            medias_ipca
        )
        
        # Manter estrutura completa do ano
        dados_corrigidos_por_ano[ano_str] = {
            "dados": dados_corrigidos,
            "dados_originais": dados_ano,  # Mantém dados originais para referência
            "total_registros": len(dados_corrigidos),
            "total_registros_original": total_registros,
            "fator_correcao_ipca": fator_correcao,
            "media_ipca_ano_base": media_ano_base,
            "media_ipca_ano_correcao": media_ano_correcao,
            "correcao_aplicada": True,
            "mes_inicio": mes_inicio_ano,
            "mes_fim": mes_fim_ano,
            "processado_em": processado_em,
            "corrigido_em": datetime.now().isoformat(),
            "metodo_correcao": "media_anual_ipca",
            "periodo_correcao": f"Ano {ano_int} -> Ano {ano_correcao} (média anual)"
        }
        
        logger.info(f"Correção aplicada para ano {ano_str}: {len(dados_corrigidos)} registros (fator: {fator_correcao:.4f})")
    
    return dados_corrigidos_por_ano

def _calcular_medias_anuais_ipca() -> Dict[int, float]:
    """
    Calcula médias anuais do IPCA (índices médios por ano).
    
    Returns:
        Dicionário com ano -> índice médio anual do IPCA
    """
    try:
        from app.services.ipca_service import ipca_service
        dados_ipca = ipca_service.obter_todos_dados()
        
        if not dados_ipca or "data" not in dados_ipca:
            logger.error("Dados IPCA não disponíveis para calcular médias anuais")
            return {}
        
        medias_por_ano = {}
        dados_por_data = dados_ipca["data"]
        
        # Organizar dados por ano
        dados_por_ano = {}
        for data_str, valor in dados_por_data.items():
            try:
                mes, ano = data_str.split('/')
                ano_int = int(ano)
                mes_int = int(mes)
                
                if ano_int not in dados_por_ano:
                    dados_por_ano[ano_int] = {}
                
                # Verificar se o valor é um índice ou porcentagem
                valor_float = float(valor)
                
                # Log para debug - verificar formato dos dados
                if ano_int >= 2019 and len(dados_por_ano[ano_int]) < 3:  # Apenas os primeiros meses para debug
                    logger.info(f"IPCA {mes}/{ano}: {valor_float} (valor bruto)")
                
                dados_por_ano[ano_int][mes_int] = valor_float
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Erro ao processar data {data_str} com valor {valor}: {e}")
                continue
        
        # Calcular médias anuais
        for ano, meses_dados in dados_por_ano.items():
            # Verificar se temos pelo menos 6 meses de dados para calcular média confiável
            if len(meses_dados) >= 6:
                valores_meses = list(meses_dados.values())
                media_anual = sum(valores_meses) / len(valores_meses)
                medias_por_ano[ano] = media_anual
                
                # Log detalhado para anos recentes para debug
                if ano >= 2019:
                    logger.info(f"Média IPCA {ano}: {media_anual:.4f} (baseada em {len(valores_meses)} meses)")
                    logger.info(f"  Valores mensais {ano}: {[f'{v:.2f}' for v in valores_meses[:3]]}..." if len(valores_meses) > 3 else f"  Valores mensais {ano}: {[f'{v:.2f}' for v in valores_meses]}")
            else:
                logger.warning(f"Ano {ano} tem apenas {len(meses_dados)} meses de dados IPCA - média não calculada")
        
        logger.info(f"Médias anuais IPCA calculadas para {len(medias_por_ano)} anos")
        
        # Log das médias para verificação
        for ano in sorted(medias_por_ano.keys())[-5:]:  # Últimos 5 anos
            logger.info(f"Média final {ano}: {medias_por_ano[ano]:.4f}")
        
        return medias_por_ano
        
    except Exception as e:
        logger.error(f"Erro ao calcular médias anuais do IPCA: {e}")
        return {}

def _aplicar_correcao_monetaria_com_media_anual(
    dados: List[Dict], 
    ano_base: int,
    ano_correcao: int,
    medias_ipca: Dict[int, float]
) -> Tuple[List[Dict], float, float, float]:
    """
    Aplica correção monetária usando médias anuais do IPCA.
    Fórmula: valor_corrigido = valor * (indice_ipca_final / indice_ipca_inicial)
    
    Args:
        dados: Lista de registros para corrigir
        ano_base: Ano dos dados originais
        ano_correcao: Ano para o qual corrigir
        medias_ipca: Dicionário com médias anuais do IPCA
    
    Returns:
        Tupla com (dados_corrigidos, fator_correcao, media_ano_base, media_ano_correcao)
    """
    # Verifica se há dados para processar
    if not dados:
        return [], 1.0, 0.0, 0.0
    
    # Verificar se temos dados IPCA para os anos necessários
    if ano_base not in medias_ipca:
        logger.warning(f"Média IPCA não disponível para ano base {ano_base}")
        return _copiar_dados_sem_correcao(dados, ano_base, ano_correcao, "Média IPCA ano base indisponível")
    
    if ano_correcao not in medias_ipca:
        logger.warning(f"Média IPCA não disponível para ano de correção {ano_correcao}")
        return _copiar_dados_sem_correcao(dados, ano_base, ano_correcao, "Média IPCA ano correção indisponível")
    
    indice_ipca_inicial = medias_ipca[ano_base]
    indice_ipca_final = medias_ipca[ano_correcao]
    
    # CORREÇÃO: Usar a fórmula correta de correção monetária
    # valor_corrigido = valor * (indice_ipca_final / indice_ipca_inicial)
    if indice_ipca_inicial <= 0:
        logger.warning(f"Índice IPCA inválido para ano base {ano_base}: {indice_ipca_inicial}")
        return _copiar_dados_sem_correcao(dados, ano_base, ano_correcao, "Índice IPCA ano base inválido")
    
    # Calcular fator de correção usando a fórmula correta
    fator_correcao = indice_ipca_final / indice_ipca_inicial
    percentual_correcao = (fator_correcao - 1) * 100
    
    # VERIFICAÇÃO: Se o fator de correção é muito alto, há algo errado
    if fator_correcao > 100:  # Mais de 10000% de inflação é suspeito
        logger.error(f"Fator de correção suspeito {ano_base}->{ano_correcao}: {fator_correcao:.4f} ({percentual_correcao:+.2f}%)")
        logger.error(f"Índice inicial ({ano_base}): {indice_ipca_inicial}, Índice final ({ano_correcao}): {indice_ipca_final}")
        return _copiar_dados_sem_correcao(dados, ano_base, ano_correcao, f"Fator de correção suspeito: {fator_correcao:.2f}")
    
    logger.info(f"Fator de correção {ano_base}->{ano_correcao}: {fator_correcao:.4f} ({percentual_correcao:+.2f}%)")
    logger.info(f"Índice IPCA inicial ({ano_base}): {indice_ipca_inicial:.4f}, final ({ano_correcao}): {indice_ipca_final:.4f}")
    
    # Aplicar correção nos dados
    dados_corrigidos = []
    campos_corrigidos_total = 0
    registros_com_correcao = 0
    
    for registro in dados:
        registro_corrigido = registro.copy()
        campos_monetarios = _identificar_campos_monetarios(registro)
        campos_corrigidos_registro = []
        
        # Metadados da correção
        metadata_correcao = {
            "ano_base": ano_base,
            "ano_correcao": ano_correcao,
            "fator_correcao": fator_correcao,
            "percentual_correcao": percentual_correcao,
            "indice_ipca_inicial": indice_ipca_inicial,
            "indice_ipca_final": indice_ipca_final,
            "metodo": "indice_ipca_medio_anual",
            "campos_identificados": campos_monetarios,
            "campos_corrigidos": [],
            "aplicado_em": datetime.now().isoformat()
        }
        
        # Aplicar correção nos campos monetários
        for campo in campos_monetarios:
            valor_original = _extrair_valor_numerico(registro[campo])
            
            if valor_original > 0:  # Só corrige valores positivos
                # APLICAR A FÓRMULA CORRETA
                valor_corrigido = valor_original * fator_correcao
                
                # Adicionar campos corrigidos
                registro_corrigido[f"{campo}_corrigido"] = round(valor_corrigido, 2)
                registro_corrigido[f"{campo}_original"] = valor_original
                registro_corrigido[f"{campo}_fator_correcao"] = fator_correcao
                registro_corrigido[f"{campo}_percentual_correcao"] = percentual_correcao
                
                campos_corrigidos_registro.append(campo)
                campos_corrigidos_total += 1
            else:
                # Para valores zero ou negativos, manter original
                registro_corrigido[f"{campo}_corrigido"] = valor_original
                registro_corrigido[f"{campo}_original"] = valor_original
                registro_corrigido[f"{campo}_fator_correcao"] = fator_correcao
                registro_corrigido[f"{campo}_percentual_correcao"] = 0.0
                registro_corrigido[f"{campo}_observacao"] = "Valor zero ou negativo - correção não aplicada"
        
        # Atualizar metadados com campos realmente corrigidos
        metadata_correcao["campos_corrigidos"] = campos_corrigidos_registro
        registro_corrigido["_metadata_correcao"] = metadata_correcao
        
        if campos_corrigidos_registro:
            registros_com_correcao += 1
        
        dados_corrigidos.append(registro_corrigido)
    
    logger.info(f"Correção monetária ano {ano_base}->{ano_correcao}: {campos_corrigidos_total}/{len(campos_monetarios) * len(dados) if dados else 0} campos corrigidos em {registros_com_correcao}/{len(dados)} registros")
    
    return dados_corrigidos, fator_correcao, indice_ipca_inicial, indice_ipca_final

def _copiar_dados_sem_correcao(
    dados: List[Dict], 
    ano_base: int, 
    ano_correcao: int, 
    motivo: str
) -> Tuple[List[Dict], float, float, float]:
    """
    Copia dados sem aplicar correção quando não é possível corrigir.
    """
    dados_sem_correcao = []
    
    for registro in dados:
        registro_copiado = registro.copy()
        campos_monetarios = _identificar_campos_monetarios(registro)
        
        # Adiciona metadados indicando que não foi corrigido
        registro_copiado["_metadata_correcao"] = {
            "ano_base": ano_base,
            "ano_correcao": ano_correcao,
            "fator_correcao": 1.0,
            "percentual_correcao": 0.0,
            "metodo": "sem_correcao",
            "motivo": motivo,
            "campos_identificados": campos_monetarios,
            "campos_corrigidos": [],
            "aplicado_em": datetime.now().isoformat()
        }
        
        # Copia campos monetários sem correção
        for campo in campos_monetarios:
            valor_original = _extrair_valor_numerico(registro[campo])
            registro_copiado[f"{campo}_corrigido"] = valor_original
            registro_copiado[f"{campo}_original"] = valor_original
            registro_copiado[f"{campo}_fator_correcao"] = 1.0
            registro_copiado[f"{campo}_percentual_correcao"] = 0.0
            registro_copiado[f"{campo}_observacao"] = motivo
        
        dados_sem_correcao.append(registro_copiado)
    
    logger.warning(f"Dados copiados sem correção: {motivo}")
    return dados_sem_correcao, 1.0, 0.0, 0.0

async def _aguardar_consulta_por_anos(session: aiohttp.ClientSession, id_consulta: str, anos_necessarios: List[int], timeout: int = 900) -> Dict:
    """
    Aguarda consulta com foco em anos ao invés de meses.
    Timeout maior para processar anos completos.
    Usa apenas endpoints que existem na API_crawler.
    """
    tempo_inicio = asyncio.get_event_loop().time()
    anos_processados = set()
    dados_coletados = {}
    
    logger.info(f"Aguardando consulta {id_consulta} para anos: {anos_necessarios}")
    
    while True:
        try:
            # Verificar status da consulta (endpoint que existe)
            async with session.get(f"{API_CRAWLER_URL}/status-consulta/{id_consulta}") as response:
                if response.status == 200:
                    status = await response.json()
                    
                    if status["status"] == "erro":
                        erro_msg = status.get('mensagem', 'Erro desconhecido')
                        logger.error(f"Erro na consulta {id_consulta}: {erro_msg}")
                        raise Exception(f"Erro na consulta: {erro_msg}")
                    
                    # Verificar se a consulta foi concluída
                    if status["status"] == "concluido":
                        logger.info(f"Consulta {id_consulta} concluída")
                        
                        # Quando concluída, usar apenas os dados do status que já contém tudo
                        # Não tentar acessar endpoints que não existem
                        return {
                            "dados_por_ano": status.get("dados_por_ano", {}),
                            "total_registros": status.get("total_registros", 0),
                            "anos_processados": status.get("anos_concluidos", []),
                            "resumo_por_ano": status.get("resumo_por_ano", {}),
                            "resumo_consolidado": status.get("resumo_consolidado", {}),
                            "status": "concluido",
                            "organizacao": "por_ano"
                        }
                    
                    # Verificar novos anos processados
                    anos_concluidos_agora = set(status.get("anos_concluidos", []))
                    novos_anos = anos_concluidos_agora - anos_processados
                    
                    # Coletar dados dos novos anos usando endpoint correto que existe
                    for ano in novos_anos:
                        try:
                            # Usar endpoint que existe: /consulta/{id_consulta}/ano/{ano}
                            async with session.get(f"{API_CRAWLER_URL}/consulta/{id_consulta}/ano/{ano}") as ano_response:
                                if ano_response.status == 200:
                                    dados_ano = await ano_response.json()
                                    dados_coletados[str(ano)] = {
                                        "dados": dados_ano.get("dados", []),
                                        "total_registros": dados_ano.get("total_registros", 0),
                                        "mes_inicio": dados_ano.get("mes_inicio"),
                                        "mes_fim": dados_ano.get("mes_fim"),
                                        "processado_em": dados_ano.get("processado_em")
                                    }
                                    logger.info(f"Dados coletados para ano {ano}: {dados_ano.get('total_registros', 0)} registros")
                                elif ano_response.status == 202:
                                    logger.info(f"Ano {ano} ainda está sendo processado")
                                else:
                                    logger.warning(f"Erro ao obter dados do ano {ano}: {ano_response.status}")
                        except Exception as e:
                            logger.warning(f"Erro ao coletar dados do ano {ano}: {e}")
                    
                    anos_processados = anos_concluidos_agora
                    
                    # Verificar se todos os anos foram processados
                    if set(anos_necessarios).issubset(anos_processados):
                        logger.info(f"Todos os anos necessários foram processados: {anos_processados}")
                        
                        # Retornar dados coletados (não tentar acessar endpoint inexistente)
                        return {
                            "dados_por_ano": dados_coletados,
                            "total_registros": sum(dados.get("total_registros", 0) for dados in dados_coletados.values()),
                            "anos_processados": list(anos_processados),
                            "status": "concluido",
                            "organizacao": "por_ano"
                        }
                    
                    # Log de progresso
                    total_anos = len(anos_necessarios)
                    anos_completos = len(anos_processados)
                    percentual = (anos_completos / total_anos * 100) if total_anos > 0 else 0
                    logger.info(f"Progresso: {anos_completos}/{total_anos} anos processados ({percentual:.1f}%)")
                    
                    # Verificar timeout
                    tempo_decorrido = asyncio.get_event_loop().time() - tempo_inicio
                    if tempo_decorrido > timeout:
                        logger.error(f"Timeout de {timeout}s atingido para consulta {id_consulta}")
                        raise Exception(f"Timeout de {timeout}s atingido na consulta")
                    
                    await asyncio.sleep(5)  # Verifica a cada 5 segundos
                else:
                    logger.error(f"Erro ao verificar status da consulta {id_consulta}: {response.status}")
                    raise Exception(f"Erro ao verificar status: {response.status}")
                    
        except asyncio.TimeoutError:
            raise Exception(f"Timeout de rede ao verificar status da consulta {id_consulta}")
        except Exception as e:
            logger.error(f"Erro durante aguardo da consulta {id_consulta}: {e}")
            raise

def _identificar_campos_monetarios(registro: Dict) -> List[str]:
    """Identifica campos que contêm valores monetários baseado nos nomes dos campos"""
    campos_monetarios = []
    
    # Campos específicos que sabemos que são monetários
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
    
    # Termos que indicam campos monetários
    termos_monetarios = [
        'orçament', 'empenhado', 'liquidado', 'pago', 'valor', 'total', 
        'disponibil', 'receita', 'despesa', 'crédito', 'débito',
        'r$', 'real', 'reais', 'monetário', 'financeiro', 'loa'
    ]
    
    for campo, valor in registro.items():
        # Pula campos de metadados
        if campo.startswith('_'):
            continue
            
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
            
            # Se string vazia, retorna 0
            if not valor_clean:
                return 0.0
            
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