import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException
from app.services.ipca_service import IPCAService, ipca_service


class TestIPCAServiceInicializacao:
    """Testes para inicialização do serviço IPCA."""
    
    def test_inicializacao_carrega_dados(self, mocker):
        """Testa se o serviço carrega dados do IPCA na inicialização."""
        # Arrange
        mock_dados = {
            "01/2020": 100.0,
            "02/2020": 101.5,
            "12/2023": 120.0
        }
        mock_info = "Dados do IPCA carregados com sucesso (2020-2023)"
        
        mock_carregar = mocker.patch(
            "app.services.ipca_service.carregar_dados_ipca",
            return_value=(mock_dados, mock_info)
        )
        
        # Act
        service = IPCAService()
        
        # Assert
        mock_carregar.assert_called_once()
        assert service._ipca_dict == mock_dados
        assert service._ipca_info == mock_info
    
    def test_inicializacao_com_erro_na_carga(self, mocker):
        """Testa comportamento quando falha ao carregar dados do IPCA."""
        # Arrange
        mocker.patch(
            "app.services.ipca_service.carregar_dados_ipca",
            side_effect=Exception("Erro ao conectar com IPEA")
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Erro ao conectar com IPEA"):
            IPCAService()


class TestIPCAServiceObterTodosDados:
    """Testes para obtenção de todos os dados IPCA."""
    
    def test_obter_todos_dados_sucesso(self, ipca_service_mock):
        """Testa obtenção de todos os dados do IPCA."""
        # Arrange
        service = ipca_service_mock
        service._ipca_dict = {"01/2020": 100.0, "02/2020": 101.5}
        service._ipca_info = "Dados carregados"
        
        # Act
        resultado = service.obter_todos_dados()
        
        # Assert
        assert "info" in resultado
        assert "data" in resultado
        assert resultado["info"] == "Dados carregados"
        assert resultado["data"] == {"01/2020": 100.0, "02/2020": 101.5}
    
    def test_obter_todos_dados_estrutura_correta(self, ipca_service_mock):
        """Testa se a estrutura de retorno está correta."""
        # Act
        resultado = ipca_service_mock.obter_todos_dados()
        
        # Assert
        assert isinstance(resultado, dict)
        assert isinstance(resultado["data"], dict)
        assert isinstance(resultado["info"], str)


class TestIPCAServiceObterValorPorData:
    """Testes para obtenção de valor IPCA por data específica."""
    
    def test_obter_valor_por_data_sucesso(self, ipca_service_mock):
        """Testa obtenção de valor IPCA para data válida."""
        # Arrange
        ipca_service_mock._ipca_dict = {"01/2020": 100.0}
        
        # Act
        resultado = ipca_service_mock.obter_valor_por_data("01", "2020")
        
        # Assert
        assert resultado["data"] == "01/2020"
        assert resultado["valor"] == 100.0
    
    def test_obter_valor_por_data_nao_encontrada(self, ipca_service_mock):
        """Testa erro quando data não existe."""
        # Arrange
        ipca_service_mock._ipca_dict = {"01/2020": 100.0}
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            ipca_service_mock.obter_valor_por_data("13", "2020")
        
        assert exc_info.value.status_code == 404
        assert "Data não encontrada" in str(exc_info.value.detail)
    
    def test_obter_valor_por_data_formata_mes_corretamente(self, ipca_service_mock):
        """Testa se o método formata o mês com zero à esquerda."""
        # Arrange
        ipca_service_mock._ipca_dict = {"01/2020": 100.0}
        
        # Act
        resultado = ipca_service_mock.obter_valor_por_data("01", "2020")
        
        # Assert
        assert resultado["data"] == "01/2020"  # Deve manter o formato


class TestIPCAServiceObterIPCAPeriodo:
    """Testes para obtenção de IPCA por período (uso interno)."""
    
    def test_obter_ipca_periodo_sucesso(self, ipca_service_mock):
        """Testa obtenção de valor IPCA para período válido."""
        # Arrange
        ipca_service_mock._ipca_dict = {"01/2020": 100.0}
        
        # Act
        resultado = ipca_service_mock.obter_ipca_periodo("01/2020")
        
        # Assert
        assert resultado == 100.0
    
    def test_obter_ipca_periodo_nao_encontrado(self, ipca_service_mock):
        """Testa erro quando período não existe."""
        # Arrange
        ipca_service_mock._ipca_dict = {"01/2020": 100.0}
        
        # Act & Assert
        with pytest.raises(ValueError, match="IPCA não encontrado para 12/2050"):
            ipca_service_mock.obter_ipca_periodo("12/2050")


class TestIPCAServiceCalcularMediaAnual:
    """Testes para cálculo de média anual do IPCA."""
    
    def test_calcular_media_anual_ano_completo(self, ipca_service_mock):
        """Testa cálculo de média para ano com todos os meses."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            f"{mes:02d}/2020": 100.0 + mes for mes in range(1, 13)
        }
        
        # Act
        resultado = ipca_service_mock.calcular_media_anual("2020")
        
        # Assert
        # Média de 101, 102, ..., 112 = (101+112)*12/2 / 12 = 106.5
        assert resultado == pytest.approx(106.5, abs=0.01)
    
    def test_calcular_media_anual_meses_especificos(self, ipca_service_mock):
        """Testa cálculo de média para meses específicos."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "02/2020": 102.0,
            "03/2020": 104.0
        }
        
        # Act
        resultado = ipca_service_mock.calcular_media_anual("2020", meses=[1, 2, 3])
        
        # Assert
        assert resultado == pytest.approx(102.0, abs=0.01)
    
    def test_calcular_media_anual_sem_dados(self, ipca_service_mock):
        """Testa erro quando não há dados para o ano."""
        # Arrange
        ipca_service_mock._ipca_dict = {"01/2020": 100.0}
        
        # Act & Assert
        with pytest.raises(ValueError, match="Nenhum valor IPCA encontrado para 2050"):
            ipca_service_mock.calcular_media_anual("2050")
    
    def test_calcular_media_anual_ano_parcial(self, ipca_service_mock):
        """Testa cálculo quando nem todos os meses estão disponíveis."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "02/2020": 102.0
            # Apenas 2 meses de 12
        }
        
        # Act
        resultado = ipca_service_mock.calcular_media_anual("2020")
        
        # Assert
        assert resultado == pytest.approx(101.0, abs=0.01)


class TestIPCAServiceObterMediaAnual:
    """Testes para obter média anual (retorno completo com metadados)."""
    
    def test_obter_media_anual_estrutura_completa(self, ipca_service_mock):
        """Testa se o retorno contém todos os metadados esperados."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "02/2020": 102.0,
            "03/2020": 104.0
        }
        
        # Act
        resultado = ipca_service_mock.obter_media_anual("2020")
        
        # Assert
        assert "ano" in resultado
        assert "media_ipca" in resultado
        assert "total_meses" in resultado
        assert "meses_disponiveis" in resultado
        assert "valores_mensais" in resultado
        assert resultado["ano"] == "2020"
        assert resultado["total_meses"] == 3
        assert len(resultado["meses_disponiveis"]) == 3
    
    def test_obter_media_anual_meses_invalidos(self, ipca_service_mock):
        """Testa erro quando fornecidos meses inválidos."""
        # Arrange
        ipca_service_mock._ipca_dict = {"01/2020": 100.0}
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            ipca_service_mock.obter_media_anual("2020", meses=[13])
        
        assert exc_info.value.status_code == 400
        assert "Mês inválido" in str(exc_info.value.detail)


class TestIPCAServiceCorrigirValor:
    """Testes para correção de valores monetários pelo IPCA."""
    
    def test_corrigir_valor_sucesso(self, ipca_service_mock):
        """Testa correção monetária com dados válidos."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "12/2023": 120.0
        }
        
        # Act
        resultado = ipca_service_mock.corrigir_valor(
            valor=1000.0,
            mes_inicial="01",
            ano_inicial="2020",
            mes_final="12",
            ano_final="2023"
        )
        
        # Assert
        assert resultado["valor_inicial"] == 1000.0
        assert resultado["valor_corrigido"] == 1200.0  # 1000 * (120/100)
        assert resultado["indice_ipca_inicial"] == 100.0
        assert resultado["indice_ipca_final"] == 120.0
        assert resultado["percentual_correcao"] == pytest.approx(20.0, abs=0.01)
    
    def test_corrigir_valor_negativo(self, ipca_service_mock):
        """Testa erro ao tentar corrigir valor negativo."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "12/2023": 120.0
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            ipca_service_mock.corrigir_valor(
                valor=-1000.0,
                mes_inicial="01",
                ano_inicial="2020",
                mes_final="12",
                ano_final="2023"
            )
        
        assert exc_info.value.status_code == 400
        assert "não pode ser negativo" in str(exc_info.value.detail)
    
    def test_corrigir_valor_data_inicial_nao_encontrada(self, ipca_service_mock):
        """Testa erro quando data inicial não existe."""
        # Arrange
        ipca_service_mock._ipca_dict = {"12/2023": 120.0}
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            ipca_service_mock.corrigir_valor(
                valor=1000.0,
                mes_inicial="13",
                ano_inicial="2020",
                mes_final="12",
                ano_final="2023"
            )
        
        assert exc_info.value.status_code == 404
    
    def test_corrigir_valor_arredondamento_correto(self, ipca_service_mock):
        """Testa se o arredondamento para 2 casas decimais está correto."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "12/2023": 123.456
        }
        
        # Act
        resultado = ipca_service_mock.corrigir_valor(
            valor=1000.0,
            mes_inicial="01",
            ano_inicial="2020",
            mes_final="12",
            ano_final="2023"
        )
        
        # Assert
        assert isinstance(resultado["valor_corrigido"], float)
        # Verificar que tem no máximo 2 casas decimais
        assert len(str(resultado["valor_corrigido"]).split('.')[-1]) <= 2


class TestIPCAServiceObterMediasMultiplosAnos:
    """Testes para obter médias de múltiplos anos."""
    
    def test_obter_medias_multiplos_anos_sucesso(self, ipca_service_mock):
        """Testa obtenção de médias para múltiplos anos."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "02/2020": 102.0,
            "01/2021": 110.0,
            "02/2021": 112.0
        }
        
        # Act
        resultado = ipca_service_mock.obter_medias_multiplos_anos(["2020", "2021"])
        
        # Assert
        assert "2020" in resultado
        assert "2021" in resultado
        assert resultado["2020"]["media_ipca"] == pytest.approx(101.0, abs=0.01)
        assert resultado["2021"]["media_ipca"] == pytest.approx(111.0, abs=0.01)
    
    def test_obter_medias_multiplos_anos_com_falha_parcial(self, ipca_service_mock):
        """Testa quando alguns anos têm dados e outros não."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "02/2020": 102.0
        }
        
        # Act
        resultado = ipca_service_mock.obter_medias_multiplos_anos(["2020", "2050"])
        
        # Assert
        assert "2020" in resultado
        assert "2050" in resultado
        assert "media_ipca" in resultado["2020"]
        assert "erro" in resultado["2050"]


@pytest.fixture
def ipca_service_mock():
    """Fixture que retorna uma instância mockada do IPCAService."""
    with patch("app.services.ipca_service.carregar_dados_ipca") as mock_carregar:
        mock_carregar.return_value = (
            {
                "01/2020": 100.0,
                "02/2020": 101.5,
                "12/2023": 120.0
            },
            "Dados do IPCA carregados"
        )
        service = IPCAService()
        return service
    
class TestIPCAServiceValidacoes:
    """Testes para validações de entrada."""
    
    def test_obter_valor_por_data_mes_invalido(self, ipca_service_mock):
        """Testa erro com mês inválido (fora do range 1-12)."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            ipca_service_mock.obter_valor_por_data("13", "2020")
        
        assert exc_info.value.status_code == 404
    
    def test_obter_valor_por_data_ano_invalido(self, ipca_service_mock):
        """Testa erro com ano inválido."""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            ipca_service_mock.obter_valor_por_data("01", "abc")
        
        assert exc_info.value.status_code in [400, 404]
    
    def test_corrigir_valor_periodo_final_antes_inicial(self, ipca_service_mock):
        """Testa comportamento quando período final é antes do inicial."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "12/2019": 95.0
        }
        
        # Act
        resultado = ipca_service_mock.corrigir_valor(
            valor=1000.0,
            mes_inicial="01",
            ano_inicial="2020",
            mes_final="12",
            ano_final="2019"
        )
        
        # Assert
        # Deve funcionar mesmo com períodos invertidos (deflação)
        assert resultado["valor_corrigido"] < resultado["valor_inicial"]
        assert resultado["percentual_correcao"] < 0
    
    def test_obter_ipca_periodo_com_formato_alternativo(self, ipca_service_mock):
        """Testa obtenção de IPCA com formato separado (mês, ano)."""
        # Arrange
        ipca_service_mock._ipca_dict = {"01/2020": 100.0}
        
        # Act
        resultado = ipca_service_mock.obter_ipca_por_periodo("01", "2020")
        
        # Assert
        assert resultado == 100.0

class TestIPCAServiceEdgeCases:
    """Testes para casos extremos."""
    
    def test_calcular_media_anual_com_valores_muito_altos(self, ipca_service_mock):
        """Testa cálculo com valores de IPCA muito altos (hiperinflação)."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            f"{mes:02d}/2020": 1000000.0 + mes for mes in range(1, 13)
        }
        
        # Act
        resultado = ipca_service_mock.calcular_media_anual("2020")
        
        # Assert
        assert resultado > 1000000.0
        assert isinstance(resultado, float)
    
    def test_calcular_media_anual_com_valores_muito_baixos(self, ipca_service_mock):
        """Testa cálculo com valores de IPCA muito baixos (deflação extrema)."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            f"{mes:02d}/2020": 0.0001 * mes for mes in range(1, 13)
        }
        
        # Act
        resultado = ipca_service_mock.calcular_media_anual("2020")
        
        # Assert
        assert resultado > 0
        assert resultado < 1
    
    def test_corrigir_valor_com_ipca_inicial_zero(self, ipca_service_mock):
        """Testa tratamento quando IPCA inicial é zero."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 0.0,  # IPCA zero (caso impossível na prática)
            "12/2023": 120.0
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            ipca_service_mock.corrigir_valor(
                valor=1000.0,
                mes_inicial="01",
                ano_inicial="2020",
                mes_final="12",
                ano_final="2023"
            )
        
        assert exc_info.value.status_code == 400
        assert "IPCA inicial inválido" in str(exc_info.value.detail)
    
    def test_corrigir_valor_com_ipca_final_zero(self, ipca_service_mock):
        """Testa tratamento quando IPCA final é zero."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": 100.0,
            "12/2023": 0.0  # IPCA zero
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            ipca_service_mock.corrigir_valor(
                valor=1000.0,
                mes_inicial="01",
                ano_inicial="2020",
                mes_final="12",
                ano_final="2023"
            )
        
        assert exc_info.value.status_code == 400
        assert "IPCA final inválido" in str(exc_info.value.detail)
    
    def test_corrigir_valor_com_ipca_negativo(self, ipca_service_mock):
        """Testa tratamento quando IPCA é negativo."""
        # Arrange
        ipca_service_mock._ipca_dict = {
            "01/2020": -10.0,  # IPCA negativo (impossível)
            "12/2023": 120.0
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            ipca_service_mock.corrigir_valor(
                valor=1000.0,
                mes_inicial="01",
                ano_inicial="2020",
                mes_final="12",
                ano_final="2023"
            )
        
        assert exc_info.value.status_code == 400
        assert "inválido" in str(exc_info.value.detail).lower()