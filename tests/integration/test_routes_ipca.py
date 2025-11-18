import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from app.main import app
from app.services.ipca_service import ipca_service

client = TestClient(app)


class TestIPCARoutesIntegracao:
    """Testes de integração para os endpoints de IPCA."""
    
    @pytest.fixture(autouse=True)
    def setup_ipca_service(self, mocker):
        """Mock do serviço IPCA para todos os testes desta classe."""
        mock_dados = {
            "01/2020": 100.0,
            "02/2020": 101.5,
            "12/2023": 120.0
        }
        mock_dados.update({f"{mes:02d}/2023": 115.0 + mes for mes in range(1, 13)})
        
        # Mockar diretamente os atributos da instância existente
        mocker.patch.object(ipca_service, '_ipca_dict', mock_dados)
        mocker.patch.object(ipca_service, '_ipca_info', "Dados mockados")
        
    
    def test_get_ipca_todos_dados_sucesso(self):
        """Testa endpoint GET /ipca para obter todos os dados."""
        # Act
        response = client.get("/ipca")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "info" in data
        assert "data" in data
        assert isinstance(data["data"], dict)
        assert len(data["data"]) > 0
    
    def test_get_ipca_filtro_data_valida(self):
        """Testa endpoint GET /ipca/filtro com mês e ano válidos."""
        # Act
        response = client.get("/ipca/filtro?mes=01&ano=2020")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == "01/2020"
        assert data["valor"] == 100.0
    
    def test_get_ipca_filtro_data_nao_encontrada(self):
        """Testa endpoint GET /ipca/filtro com data inexistente."""
        # Act
        response = client.get("/ipca/filtro?mes=13&ano=2020")
        
        # Assert
        assert response.status_code == 404
        assert "Data não encontrada" in response.json()["detail"]
    
    def test_get_ipca_filtro_parametros_faltando(self):
        """Testa endpoint GET /ipca/filtro sem parâmetros obrigatórios."""
        # Act
        response = client.get("/ipca/filtro")
        
        # Assert
        assert response.status_code == 422  # Validation error
    
    def test_get_ipca_media_anual_sucesso(self):
        """Testa endpoint GET /ipca/media-anual/{ano}."""
        # Act
        response = client.get("/ipca/media-anual/2023")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "ano" in data
        assert "media_ipca" in data
        assert "total_meses" in data
        assert "meses_disponiveis" in data
        assert data["ano"] == "2023"
        assert data["total_meses"] == 12
    
    def test_get_ipca_media_anual_ano_sem_dados(self):
        """Testa endpoint GET /ipca/media-anual/{ano} para ano sem dados."""
        # Act
        response = client.get("/ipca/media-anual/2050")
        
        # Assert
        assert response.status_code == 404
    
    def test_get_ipca_medias_multiplos_anos_sucesso(self):
        """Testa endpoint GET /ipca/medias-anuais."""
        # Act
        response = client.get("/ipca/medias-anuais?anos=2020&anos=2023")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "2020" in data or "2023" in data
        assert isinstance(data, dict)
    
    def test_get_ipca_corrigir_valor_sucesso(self):
        """Testa endpoint GET /ipca/corrigir com parâmetros válidos."""
        # Act
        response = client.get(
            "/ipca/corrigir?valor=1000&mes_inicial=01&ano_inicial=2020&mes_final=12&ano_final=2023"
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "valor_inicial" in data
        assert "valor_corrigido" in data
        assert "percentual_correcao" in data
        assert data["valor_inicial"] == 1000.0
        assert data["valor_corrigido"] > data["valor_inicial"]
    
    def test_get_ipca_corrigir_valor_negativo(self):
        """Testa endpoint GET /ipca/corrigir com valor negativo."""
        # Act
        response = client.get(
            "/ipca/corrigir?valor=-1000&mes_inicial=01&ano_inicial=2020&mes_final=12&ano_final=2023"
        )
        
        # Assert
        assert response.status_code == 400
        assert "não pode ser negativo" in response.json()["detail"]
    
    def test_get_ipca_corrigir_data_inicial_invalida(self):
        """Testa endpoint GET /ipca/corrigir com data inicial inválida."""
        # Act
        response = client.get(
            "/ipca/corrigir?valor=1000&mes_inicial=13&ano_inicial=2020&mes_final=12&ano_final=2023"
        )
        
        # Assert
        assert response.status_code == 404


class TestIPCARoutesValidacao:
    """Testes de validação de entrada para endpoints IPCA."""
    
    @pytest.fixture(autouse=True)
    def setup_ipca_service(self, mocker):
        """Mock do serviço IPCA."""
        mock_dados = {
            "01/2020": 100.0,
            "02/2020": 101.5
        }
        mocker.patch.object(ipca_service, '_ipca_dict', mock_dados)
        mocker.patch.object(ipca_service, '_ipca_info', "Dados mockados")
    
    @pytest.mark.parametrize("mes,ano,esperado_status,esperado_detail", [
        ("00", "2020", 404, "Data não encontrada"),  # Mês inválido resulta em 404
        ("13", "2020", 404, "Data não encontrada"),  # Mês inválido resulta em 404
        ("01", "abc", 404, "Data não encontrada"),   # Ano não numérico resulta em busca "01/abc" -> 404
        ("a", "2020", 404, "Data não encontrada"),   # Mês não numérico resulta em busca "a/2020" -> 404
    ])
    def test_get_ipca_filtro_validacao_entrada(self, mes, ano, esperado_status, esperado_detail):
        """Testa validação de entrada do endpoint /ipca/filtro."""
        # Act
        response = client.get(f"/ipca/filtro?mes={mes}&ano={ano}")
        
        # Assert
        assert response.status_code == esperado_status
        if esperado_status == 404:
            assert esperado_detail in response.json()["detail"]


class TestIPCARoutesPerformance:
    """Testes de performance para endpoints IPCA."""
    
    @pytest.fixture(autouse=True)
    def setup_ipca_service(self, mocker):
        """Mock com grande volume de dados."""
        mock_dados = {
            f"{mes:02d}/{ano}": 100.0 + mes + (ano - 2000)
            for ano in range(2000, 2024)
            for mes in range(1, 13)
        }
        
        mocker.patch.object(ipca_service, '_ipca_dict', mock_dados)
        mocker.patch.object(ipca_service, '_ipca_info', "Dados mockados")
    
    def test_get_ipca_todos_dados_com_grande_volume(self):
        """Testa se o endpoint /ipca lida com grande volume de dados."""
        # Act
        response = client.get("/ipca")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) > 200  # Deve ter muitos registros
        # Tempo de resposta deve ser razoável (pytest mede automaticamente)
    
    def test_get_ipca_medias_multiplos_anos_muitos_anos(self):
        """Testa endpoint com muitos anos simultâneos."""
        # Arrange
        anos_query = "&".join([f"anos={ano}" for ano in range(2010, 2024)])
        
        # Act
        response = client.get(f"/ipca/medias-anuais?{anos_query}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 10