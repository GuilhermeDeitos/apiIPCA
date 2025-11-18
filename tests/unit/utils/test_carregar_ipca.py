import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from app.utils.carregar_ipca import carregar_dados_ipca


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
    
    def test_carregar_dados_ipca_formata_datas_corretamente(self, mocker):
        """Testa se as datas são formatadas com zero à esquerda."""
        # Arrange
        df_mock = pd.DataFrame({
            "MONTH": [1, 12],  # Mês com 1 dígito e com 2 dígitos
            "YEAR": [2019, 2019],
            "VALUE (-)": [0.32, 0.15]
        })
        
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        
        # Act
        ipca_dict, _ = carregar_dados_ipca()
        
        # Assert
        assert "01/2019" in ipca_dict  # Mês deve ter zero à esquerda
        assert "12/2019" in ipca_dict
        assert "1/2019" not in ipca_dict  # Não deve ter formato sem zero
    
    def test_carregar_dados_ipca_multiplos_anos(self, mocker):
        """Testa carregamento de dados com múltiplos anos."""
        # Arrange
        df_mock = pd.DataFrame({
            "MONTH": [12, 1, 6],
            "YEAR": [2018, 2019, 2020],
            "VALUE (-)": [0.15, 0.32, 0.26]
        })
        
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        
        # Act
        ipca_dict, info_ipca = carregar_dados_ipca()
        
        # Assert
        assert len(ipca_dict) == 3
        assert "12/2018" in ipca_dict
        assert "01/2019" in ipca_dict
        assert "06/2020" in ipca_dict
        assert "2018-2020" in info_ipca or ("2018" in info_ipca and "2020" in info_ipca)
    
    def test_carregar_dados_ipca_erro_conexao_ipea(self, mocker):
        """Testa tratamento de erro ao conectar com API do IPEA."""
        # Arrange
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", side_effect=ConnectionError("Erro de conexão"))
        
        # Act
        ipca_dict, info_ipca = carregar_dados_ipca()
        
        # Assert
        assert ipca_dict == {}
        assert "Erro ao carregar IPCA" in info_ipca
        assert "Erro de conexão" in info_ipca
    
    def test_carregar_dados_ipca_erro_estrutura_dados(self, mocker):
        """Testa tratamento de erro quando API retorna estrutura inesperada."""
        # Arrange
        df_mock = pd.DataFrame({
            "COLUNA_ERRADA": [1, 2, 3]
        })
        
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        
        # Act
        ipca_dict, info_ipca = carregar_dados_ipca()
        
        # Assert
        assert ipca_dict == {}
        assert "Erro ao carregar IPCA" in info_ipca
    
    def test_carregar_dados_ipca_valores_decimais_precisos(self, mocker):
        """Testa se valores decimais do IPCA são preservados corretamente."""
        # Arrange
        df_mock = pd.DataFrame({
            "MONTH": [1, 2],
            "YEAR": [2021, 2021],
            "VALUE (-)": [0.254321, 0.860543]  # Valores com alta precisão
        })
        
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        
        # Act
        ipca_dict, _ = carregar_dados_ipca()
        
        # Assert
        assert ipca_dict["01/2021"] == pytest.approx(0.254321, abs=1e-6)
        assert ipca_dict["02/2021"] == pytest.approx(0.860543, abs=1e-6)
    
    def test_carregar_dados_ipca_dataframe_vazio(self, mocker):
        """Testa comportamento quando API retorna DataFrame vazio."""
        # Arrange
        df_mock = pd.DataFrame({
            "MONTH": [],
            "YEAR": [],
            "VALUE (-)": []
        })
        
        mocker.patch("app.utils.carregar_ipca.ip.timeseries", return_value=df_mock)
        
        # Act
        ipca_dict, info_ipca = carregar_dados_ipca()
        
        # Assert
        # Pode retornar vazio ou um erro - ambos são válidos
        assert ipca_dict == {} or len(ipca_dict) == 0


class TestCarregarDadosIPCAIntegracao:
    """Testes de integração (marcados para execução condicional)."""
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Teste de integração real - executar manualmente")
    def test_carregar_dados_ipca_api_real(self):
        """
        Testa carregamento real da API do IPEA.
        ATENÇÃO: Este teste faz uma chamada real à API externa.
        """
        # Act
        ipca_dict, info_ipca = carregar_dados_ipca()
        
        # Assert
        assert ipca_dict is not None
        assert len(ipca_dict) > 0
        assert isinstance(list(ipca_dict.keys())[0], str)  # Chaves são strings
        assert isinstance(list(ipca_dict.values())[0], (int, float))  # Valores são numéricos
        assert "Dados do IPCA carregados" in info_ipca