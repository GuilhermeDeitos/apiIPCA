import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.services.transparencia_service import transparencia_service

client = TestClient(app)


class TestTransparenciaRoutesIntegracao:
    """Testes de integração para os endpoints do Portal da Transparência."""
    
    def test_consultar_transparencia_sucesso(self, mocker):
        """Testa endpoint POST /transparencia/consultar com sucesso."""
        # Arrange - Mock com estrutura CORRETA conforme TransparenciaResposta
        mock_resultado = {
            "status": "completo",
            "total_registros": 1,
            "total_nao_processados": 0,
            "dados": [
                {
                    "UNIDADE_ORCAMENTARIA": "UEL",
                    "ORCAMENTO_INICIAL_LOA": "1.200,00",
                    "ANO": 2020,
                    "MES": 1
                }
            ],
            "dados_nao_processados": [],
            "periodo_base_ipca": "12/2023",
            "ipca_referencia": 120.0,
            "tipo_correcao": "mensal",
            "observacao": None
        }
        
        mocker.patch.object(
            transparencia_service,
            'consultar_dados_corrigidos',
            new_callable=AsyncMock,
            return_value=mock_resultado
        )
        
        payload = {
            "data_inicio": "01/2020",
            "data_fim": "12/2020",
            "tipo_correcao": "mensal",
            "ipca_referencia": "12/2023"
        }
        
        # Act
        response = client.post("/transparencia/consultar", json=payload)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completo"
        assert data["total_registros"] == 1
        assert "dados" in data
        assert len(data["dados"]) == 1
    
    def test_consultar_transparencia_erro_interno(self, mocker):
        """Testa tratamento de erro no endpoint /transparencia/consultar."""
        # Arrange
        mocker.patch.object(
            transparencia_service,
            'consultar_dados_corrigidos',
            new_callable=AsyncMock,
            side_effect=Exception("Erro de conexão")
        )
        
        payload = {
            "data_inicio": "01/2020",
            "data_fim": "12/2020"
        }
        
        # Act
        response = client.post("/transparencia/consultar", json=payload)
        
        # Assert
        assert response.status_code == 500
        assert "error" in response.json()["detail"]
    
    def test_consultar_transparencia_validacao_payload(self):
        """Testa validação do payload do endpoint /transparencia/consultar."""
        # Arrange - Payload sem campos obrigatórios
        payload = {}
        
        # Act
        response = client.post("/transparencia/consultar", json=payload)
        
        # Assert
        assert response.status_code == 422
    
    def test_consultar_transparencia_streaming_sucesso(self, mocker):
        """Testa endpoint POST /transparencia/consultar-streaming."""
        # Arrange
        async def mock_generator():
            yield {"status": "processando", "progresso": 50}
            yield {"status": "completo", "total_registros": 10}
        
        mocker.patch.object(
            transparencia_service,
            'consultar_dados_streaming',
            return_value=mock_generator()
        )
        
        payload = {
            "data_inicio": "01/2020",
            "data_fim": "12/2020"
        }
        
        # Act
        with client.stream("POST", "/transparencia/consultar-streaming", json=payload) as response:
            # Assert
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            
            # Ler os eventos do stream
            eventos = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    import json
                    eventos.append(json.loads(line[6:]))  # Remove "data: "
            
            assert len(eventos) == 2
            assert eventos[0]["status"] == "processando"
            assert eventos[1]["status"] == "completo"
    
    def test_status_transparencia_sucesso(self, mocker):
        """Testa endpoint GET /transparencia/status."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "slots_disponiveis": 5,
            "slots_ocupados": 0,
            "max_concurrent_scrapers": 5
        })
        
        mock_session = MagicMock()
        mock_get_context = AsyncMock()
        mock_get_context.__aenter__.return_value = mock_response
        mock_get_context.__aexit__.return_value = None
        mock_session.get.return_value = mock_get_context
        
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.return_value = mock_session
        mock_session_context.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_context)
        
        # Act
        response = client.get("/transparencia/status")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["api_crawler_disponivel"] is True
        assert "detalhes_crawler" in data
    
    def test_status_transparencia_api_indisponivel(self, mocker):
        """Testa endpoint /transparencia/status quando API_crawler está offline."""
        # Arrange
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.side_effect = Exception("Connection refused")
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_context)
        
        # Act
        response = client.get("/transparencia/status")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "erro"
        assert data["api_crawler_disponivel"] is False
    
    def test_cancelar_consulta_sucesso(self, mocker):
        """Testa endpoint POST /transparencia/cancelar/{id_consulta}."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"cancelado": True})
        
        mock_post_context = AsyncMock()
        mock_post_context.__aenter__.return_value = mock_response
        mock_post_context.__aexit__.return_value = None
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_context
        
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.return_value = mock_session
        mock_session_context.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_context)
        
        # Act
        response = client.post("/transparencia/cancelar/consulta-123")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelado"
    
    def test_cancelar_consulta_erro(self, mocker):
        """Testa endpoint /transparencia/cancelar com erro."""
        # Arrange
        mock_session_context = AsyncMock()
        mock_session_context.__aenter__.side_effect = Exception("Erro de conexão")
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_context)
        
        # Act
        response = client.post("/transparencia/cancelar/consulta-123")
        
        # Assert
        assert response.status_code == 500


class TestTransparenciaRoutesValidacao:
    """Testes de validação para endpoints de transparência."""
    
    @pytest.mark.parametrize("tipo_correcao", ["mensal", "anual"])
    def test_consultar_transparencia_tipos_correcao(self, mocker, tipo_correcao):
        """Testa diferentes tipos de correção monetária."""
        # Arrange - Mock com estrutura COMPLETA
        mock_resultado = {
            "status": "completo",
            "total_registros": 0,
            "total_nao_processados": 0,
            "dados": [],
            "dados_nao_processados": [],
            "periodo_base_ipca": "12/2023" if tipo_correcao == "mensal" else "2023",
            "ipca_referencia": 120.0,
            "tipo_correcao": tipo_correcao,
            "observacao": None
        }
        
        mocker.patch.object(
            transparencia_service,
            'consultar_dados_corrigidos',
            new_callable=AsyncMock,
            return_value=mock_resultado
        )
        
        payload = {
            "data_inicio": "01/2020",
            "data_fim": "12/2020",
            "tipo_correcao": tipo_correcao
        }
        
        # Act
        response = client.post("/transparencia/consultar", json=payload)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["tipo_correcao"] == tipo_correcao
        assert data["status"] == "completo"
        assert "dados" in data
        assert "periodo_base_ipca" in data