import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import time
from datetime import datetime, timedelta
from app.utils.carregar_ipca import (
    carregar_dados_ipca,
    carregar_dados_ipca_com_retry,
    carregar_dados_ipca_da_api,
    forcar_atualizacao_cache,
    obter_estatisticas_cache,
    limpar_cache_ipca,
    verificar_dados_ipca_disponiveis,
    obter_status_carregamento_ipca,
    obter_status_circuit_breaker,
    resetar_circuit_breaker,
    circuit_breaker,
)


@pytest.fixture(autouse=True)
def reset_circuit_breaker_fixture():
    """Reseta o circuit breaker ANTES e DEPOIS de cada teste."""
    resetar_circuit_breaker()
    yield
    resetar_circuit_breaker()


@pytest.fixture(autouse=True)
def mock_cache_global(mocker):
    """Mock global do cache para todos os testes."""
    # ✅ CRÍTICO: Mockar cache por padrão para evitar loops infinitos
    mocker.patch("app.utils.carregar_ipca.ipca_cache.carregar_cache", return_value=None)
    mocker.patch("app.utils.carregar_ipca.ipca_cache.salvar_cache", return_value=True)
    mocker.patch("app.utils.carregar_ipca.ipca_cache.verificar_atualizacao_necessaria", return_value=(True, "Teste"))
    mocker.patch("app.utils.carregar_ipca.ipca_cache.obter_estatisticas", return_value={
        "existe": False, "total_registros": 0
    })


class TestCarregarDadosIPCAComCircuitBreaker:
    """Testes de integração com Circuit Breaker."""
    
    def test_carregar_dados_circuit_breaker_fechado_sucesso(self, mocker):
        """Testa carregamento quando circuit breaker está fechado."""
        # Arrange
        df_mock = pd.DataFrame({
            "MONTH": [1],
            "YEAR": [2020],
            "VALUE (-)": [0.21]
        })
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        mocker.patch("socket.setdefaulttimeout")
        
        # Assert estado inicial
        assert circuit_breaker.state == "CLOSED"
        
        # Act
        ipca_dict, info = carregar_dados_ipca_com_retry()
        
        # Assert
        assert len(ipca_dict) == 1
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failures == 0
    
    def test_carregar_dados_circuit_breaker_abre_apos_falhas(self, mocker):
        """Testa que circuit breaker abre após múltiplas falhas."""
        # Arrange
        mocker.patch(
            "app.utils.carregar_ipca.ip.timeseries",
            side_effect=ConnectionError("Timeout")
        )
        mocker.patch("time.sleep")
        mocker.patch("socket.setdefaulttimeout")
        
        # Verificar estado inicial
        assert circuit_breaker.state == "CLOSED"
        
        # Act
        ipca_dict, info = carregar_dados_ipca_com_retry()
        
        # Assert
        assert ipca_dict == {}
        assert "Erro ao carregar IPCA" in info or "indisponível" in info
        assert circuit_breaker.state == "OPEN"
        assert circuit_breaker.failures == 3
    
    def test_carregar_dados_bloqueado_circuit_breaker_aberto(self, mocker):
        """Testa que requisições são bloqueadas quando circuit breaker está aberto."""
        # ✅ MUDANÇA: Sobrescrever mock global com dados de cache
        mock_cache_data = {
            "dados": {"01/2020": 100.0},
            "info": "Cache antigo"
        }
        mocker.patch("app.utils.carregar_ipca.ipca_cache.carregar_cache", return_value=mock_cache_data)
        
        # Arrange
        mock_timeseries = mocker.patch("app.utils.carregar_ipca.ip.timeseries")
        
        # Abrir circuit breaker manualmente
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.state == "OPEN"
        
        # Act
        ipca_dict, info = carregar_dados_ipca_com_retry()
        
        # Assert
        assert len(ipca_dict) == 1
        assert "circuit breaker" in info.lower() or "cache" in info.lower()
        mock_timeseries.assert_not_called()
    
    def test_carregar_dados_circuit_breaker_recuperacao(self, mocker):
        """Testa recuperação após circuit breaker abrir."""
        # Arrange
        df_mock = pd.DataFrame({
            "MONTH": [1],
            "YEAR": [2020],
            "VALUE (-)": [0.21]
        })
        
        # Primeira chamada: forçar falha e abrir circuit breaker
        mocker.patch(
            "app.utils.carregar_ipca.ip.timeseries",
            side_effect=ConnectionError("Timeout")
        )
        mocker.patch("time.sleep")
        mocker.patch("socket.setdefaulttimeout")
        
        ipca_dict, info = carregar_dados_ipca_com_retry()
        assert circuit_breaker.state == "OPEN"
        
        # Simular passagem de tempo (transition para HALF_OPEN)
        circuit_breaker.last_failure_time = datetime.now() - timedelta(seconds=301)
        
        # Segunda chamada: sucesso
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        
        # Act
        ipca_dict, info = carregar_dados_ipca_com_retry()
        
        # Assert
        assert len(ipca_dict) == 1
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failures == 0


class TestCarregarDadosIPCA:
    """Testes para a função de carregamento de dados IPCA do IPEA."""
    
    def test_carregar_dados_ipca_sucesso(self, mocker):
        """Testa carregamento bem-sucedido de dados IPCA."""
        # Arrange
        df_mock = pd.DataFrame({
            "MONTH": [1, 2, 3],
            "YEAR": [2020, 2020, 2020],
            "VALUE (-)": [0.21, 0.25, 0.07]
        })
        
        mock_timeseries = mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        mocker.patch("socket.setdefaulttimeout")
        
        # Act
        ipca_dict, info_ipca = carregar_dados_ipca()
        
        # Assert
        assert ipca_dict is not None
        assert isinstance(ipca_dict, dict)
        assert len(ipca_dict) == 3
        assert "01/2020" in ipca_dict
        assert ipca_dict["01/2020"] == 0.21
        assert "02/2020" in ipca_dict
        assert ipca_dict["02/2020"] == 0.25
        assert "Dados do IPCA carregados" in info_ipca
        assert "2020" in info_ipca
        mock_timeseries.assert_called_once_with("PRECOS12_IPCA12")
    
    def test_carregar_dados_ipca_com_retry_segunda_tentativa_sucesso(self, mocker):
        """Testa retry quando segunda tentativa é bem-sucedida."""
        # Arrange
        df_mock = pd.DataFrame({
            "MONTH": [1],
            "YEAR": [2020],
            "VALUE (-)": [0.21]
        })
        
        # Primeira chamada falha, segunda sucede
        mock_timeseries = mocker.patch(
            "app.utils.carregar_ipca.ip.timeseries",
            side_effect=[ConnectionError("Timeout"), df_mock]
        )
        
        mock_sleep = mocker.patch("time.sleep")
        mocker.patch("socket.setdefaulttimeout")
        
        # Act
        ipca_dict, info_ipca = carregar_dados_ipca_com_retry()
        
        # Assert
        assert len(ipca_dict) == 1
        assert mock_timeseries.call_count == 2
        mock_sleep.assert_called()
        assert circuit_breaker.state == "CLOSED"
    
    def test_carregar_dados_ipca_todas_tentativas_falharam(self, mocker):
        """Testa quando todas as tentativas falham."""
        # Arrange
        mocker.patch(
            "app.utils.carregar_ipca.ip.timeseries",
            side_effect=ConnectionError("Erro de conexão")
        )
        mock_sleep = mocker.patch("time.sleep")
        mocker.patch("socket.setdefaulttimeout")
        
        # Verificar estado inicial
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failures == 0
        
        # Act
        ipca_dict, info_ipca = carregar_dados_ipca_com_retry()
        
        # Assert
        assert ipca_dict == {}
        assert "Erro ao carregar IPCA" in info_ipca
        assert "tentativas" in info_ipca.lower()
        assert mock_sleep.call_count == 2
        assert circuit_breaker.state == "OPEN"
        assert circuit_breaker.failures == 3
    
    def test_carregar_dados_ipca_erro_estrutura_dados(self, mocker):
        """Testa tratamento de erro quando API retorna estrutura inesperada."""
        # Arrange
        df_mock = pd.DataFrame({
            "COLUNA_ERRADA": [1, 2, 3]
        })
        
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        mocker.patch("time.sleep")
        mocker.patch("socket.setdefaulttimeout")
        
        # Act
        ipca_dict, info_ipca = carregar_dados_ipca()
        
        # Assert
        assert ipca_dict == {}
        assert "Erro ao carregar IPCA" in info_ipca


class TestVerificarDadosIPCADisponiveis:
    """Testes para verificação de disponibilidade dos dados."""
    
    def test_verificar_dados_disponiveis_com_dados(self):
        """Testa verificação quando há dados disponíveis."""
        ipca_dict = {"01/2020": 100.0, "02/2020": 101.0}
        disponivel = verificar_dados_ipca_disponiveis(ipca_dict)
        assert disponivel is True
    
    def test_verificar_dados_disponiveis_sem_dados(self):
        """Testa verificação quando não há dados."""
        ipca_dict = {}
        disponivel = verificar_dados_ipca_disponiveis(ipca_dict)
        assert disponivel is False


class TestObterStatusCarregamentoIPCA:
    """Testes para obtenção de status do carregamento."""
    
    def test_obter_status_com_dados_sucesso(self):
        """Testa status quando dados foram carregados com sucesso."""
        ipca_dict = {
            "01/2020": 100.0,
            "02/2020": 101.0,
            "01/2021": 110.0
        }
        info = "Dados carregados com sucesso"
        
        status = obter_status_carregamento_ipca(ipca_dict, info)
        
        assert status["status"] == "sucesso"
        assert status["dados_disponiveis"] is True
        assert status["total_registros"] == 3
        assert 2020 in status["anos_disponiveis"]
        assert 2021 in status["anos_disponiveis"]
        assert "2020-2021" in status["periodo"]
        assert status["mensagem"] == info
        assert "circuit_breaker" in status
    
    def test_obter_status_sem_dados_erro(self):
        """Testa status quando carregamento falhou."""
        ipca_dict = {}
        info = "Erro ao carregar após 3 tentativas"
        
        status = obter_status_carregamento_ipca(ipca_dict, info)
        
        assert status["status"] == "erro"
        assert status["dados_disponiveis"] is False
        assert status["total_registros"] == 0
        assert status["anos_disponiveis"] == []
        assert status["periodo"] == "N/A"
        assert "aviso" in status
        assert "circuit_breaker" in status
    
    def test_obter_status_extrai_anos_corretamente(self):
        """Testa extração de anos dos dados."""
        ipca_dict = {
            "01/2018": 100.0,
            "06/2019": 105.0,
            "12/2020": 110.0,
            "03/2021": 115.0
        }
        info = "Dados OK"
        
        status = obter_status_carregamento_ipca(ipca_dict, info)
        
        assert len(status["anos_disponiveis"]) == 4
        assert status["anos_disponiveis"] == [2018, 2019, 2020, 2021]
        assert "2018-2021" in status["periodo"]


class TestCarregarDadosIPCATimeout:
    """Testes para verificar comportamento de timeout."""
    
    def test_timeout_configurado_durante_requisicao(self, mocker):
        """Testa se timeout é configurado e restaurado."""
        df_mock = pd.DataFrame({
            "MONTH": [1],
            "YEAR": [2020],
            "VALUE (-)": [0.21]
        })
        
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        mock_socket = mocker.patch("socket.setdefaulttimeout")
        
        carregar_dados_ipca_com_retry()
        
        assert mock_socket.call_count >= 2
        calls = [call[0][0] for call in mock_socket.call_args_list]
        assert 10 in calls
        assert None in calls


class TestFuncoesGlobaisCircuitBreaker:
    """Testes para funções globais do circuit breaker."""
    
    def test_obter_status_circuit_breaker(self):
        """Testa função de obter status do circuit breaker global."""
        status = obter_status_circuit_breaker()
        
        assert "state" in status
        assert "failures" in status
        assert "last_failure" in status
        assert "next_attempt_in" in status
    
    def test_resetar_circuit_breaker(self):
        """Testa função de resetar circuit breaker global."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.failures > 0
        
        resetar_circuit_breaker()
        
        assert circuit_breaker.state == "CLOSED"
        assert circuit_breaker.failures == 0
        assert circuit_breaker.last_failure_time is None


class TestCarregarDadosIPCAIntegracao:
    """Testes de integração (marcados para execução condicional)."""
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Teste de integração real - executar manualmente")
    def test_carregar_dados_ipca_api_real(self):
        """Testa carregamento real da API do IPEA."""
        ipca_dict, info_ipca = carregar_dados_ipca()
        
        assert ipca_dict is not None
        assert len(ipca_dict) > 0
        assert isinstance(list(ipca_dict.keys())[0], str)
        assert isinstance(list(ipca_dict.values())[0], (int, float))
        assert "Dados do IPCA carregados" in info_ipca


class TestCarregarDadosIPCAComCache:
    """Testes para carregamento com sistema de cache."""
    
    def test_carregar_usa_cache_quando_disponivel(self, mocker):
        """Testa que usa cache quando disponível e atualizado."""
        # ✅ MUDANÇA: Sobrescrever mock global
        mock_dados = {"01/2020": 100.0, "02/2020": 101.0}
        mock_cache_data = {
            "dados": mock_dados,
            "info": "Cache válido",
            "ultima_atualizacao": datetime.now().isoformat()
        }
        
        mocker.patch("app.utils.carregar_ipca.ipca_cache.carregar_cache", return_value=mock_cache_data)
        mocker.patch("app.utils.carregar_ipca.ipca_cache.verificar_atualizacao_necessaria", return_value=(False, "Cache atualizado"))
        
        mock_api = mocker.patch("app.utils.carregar_ipca.ip.timeseries")
        mocker.patch("socket.setdefaulttimeout")
        
        ipca_dict, info = carregar_dados_ipca_com_retry()
        
        assert ipca_dict == mock_dados
        assert "cache" in info.lower()
        mock_api.assert_not_called()
    
    def test_carregar_atualiza_cache_quando_desatualizado(self, mocker):
        """Testa atualização quando cache desatualizado."""
        df_mock = pd.DataFrame({
            "MONTH": [1], "YEAR": [2020], "VALUE (-)": [100.0]
        })
        
        # ✅ Cache desatualizado
        mocker.patch("app.utils.carregar_ipca.ipca_cache.carregar_cache", return_value={"dados": {}, "info": "Velho"})
        mocker.patch("app.utils.carregar_ipca.ipca_cache.verificar_atualizacao_necessaria", return_value=(True, "Desatualizado"))
        mock_salvar = mocker.patch("app.utils.carregar_ipca.ipca_cache.salvar_cache", return_value=True)
        
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        mocker.patch("socket.setdefaulttimeout")
        
        ipca_dict, info = carregar_dados_ipca_com_retry()
        
        assert len(ipca_dict) == 1
        mock_salvar.assert_called_once()
        assert "cache atualizado" in info.lower()
    
    def test_carregar_usa_cache_como_fallback_circuit_breaker_open(self, mocker):
        """Testa uso de cache como fallback quando circuit breaker está aberto."""
        # Abrir circuit breaker
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.state == "OPEN"
        
        mock_dados_cache = {"01/2020": 100.0}
        mocker.patch("app.utils.carregar_ipca.ipca_cache.carregar_cache", return_value={
            "dados": mock_dados_cache,
            "info": "Cache antigo"
        })
        
        mock_api = mocker.patch("app.utils.carregar_ipca.ip.timeseries")
        
        ipca_dict, info = carregar_dados_ipca_com_retry()
        
        assert ipca_dict == mock_dados_cache
        assert "circuit breaker" in info.lower()
        mock_api.assert_not_called()
    
    def test_forcar_atualizacao_cache_sucesso(self, mocker):
        """Testa forçar atualização do cache."""
        df_mock = pd.DataFrame({
            "MONTH": [1], "YEAR": [2020], "VALUE (-)": [100.0]
        })
        
        mock_salvar = mocker.patch("app.utils.carregar_ipca.ipca_cache.salvar_cache", return_value=True)
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        mocker.patch("socket.setdefaulttimeout")
        
        sucesso, mensagem = forcar_atualizacao_cache()
        
        assert sucesso is True
        assert "sucesso" in mensagem.lower()
        mock_salvar.assert_called_once()
    
    def test_forcar_atualizacao_cache_falha_api(self, mocker):
        """Testa falha ao forçar atualização."""
        mocker.patch(
            "app.utils.carregar_ipca.ip.timeseries",
            side_effect=ConnectionError("Erro")
        )
        mocker.patch("time.sleep")
        mocker.patch("socket.setdefaulttimeout")
        
        sucesso, mensagem = forcar_atualizacao_cache()
        
        assert sucesso is False
        assert "erro" in mensagem.lower()
    
    def test_obter_estatisticas_cache(self, mocker):
        """Testa obtenção de estatísticas do cache."""
        mock_stats = {
            "existe": True,
            "total_registros": 100,
            "anos_disponiveis": [2020, 2021]
        }
        
        mocker.patch("app.utils.carregar_ipca.ipca_cache.obter_estatisticas", return_value=mock_stats)
        
        stats = obter_estatisticas_cache()
        
        assert stats == mock_stats
    
    def test_limpar_cache_ipca(self, mocker):
        """Testa limpeza do cache."""
        mock_limpar = mocker.patch("app.utils.carregar_ipca.ipca_cache.limpar_cache", return_value=True)
        
        resultado = limpar_cache_ipca()
        
        assert resultado is True
        mock_limpar.assert_called_once()
    
    def test_status_carregamento_inclui_cache(self, mocker):
        """Testa que status de carregamento inclui informações do cache."""
        mock_stats = {"existe": True, "total_registros": 50}
        mocker.patch("app.utils.carregar_ipca.ipca_cache.obter_estatisticas", return_value=mock_stats)
        
        ipca_dict = {"01/2020": 100.0}
        info = "Dados OK"
        
        status = obter_status_carregamento_ipca(ipca_dict, info)
        
        assert "cache" in status
        assert status["cache"] == mock_stats