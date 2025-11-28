import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app

client = TestClient(app)


class TestFluxoCompletoTransparencia:
    """Testes E2E para fluxo completo do Portal da Transparência."""
    
    def test_fluxo_verificar_status_e_consultar(self, mocker):
        """
        Testa fluxo completo:
        1. Verificar status da API Crawler
        2. Realizar consulta se disponível
        """
        # Step 1: Mock da verificação de status (endpoint HTTP)
        async def mock_status_http(*args, **kwargs):
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "slots_disponiveis": 5,
                "slots_ocupados": 2,
                "max_concurrent_scrapers": 10
            })
            
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            return mock_ctx
        
        # Mock do ClientSession.get
        mock_session = MagicMock()
        mock_session.get = mock_status_http
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mocker.patch('aiohttp.ClientSession', return_value=mock_session_ctx)
        
        response = client.get("/transparencia/status")
        assert response.status_code == 200
        status = response.json()
        
        # Step 2: Se disponível, fazer consulta
        if status.get("api_crawler_disponivel"):
            mock_consulta = AsyncMock(return_value={
                "status": "completo",
                "total_registros": 10,
                "total_nao_processados": 0,
                "dados": [],
                "dados_nao_processados": [],
                "periodo_base_ipca": "12/2023",
                "ipca_referencia": 120.0,
                "tipo_correcao": "mensal",
                "observacao": None
            })
            mocker.patch(
                'app.services.transparencia_service.transparencia_service.consultar_dados_corrigidos',
                mock_consulta
            )
            
            payload = {
                "data_inicio": "01/2020",
                "data_fim": "12/2020"
            }
            
            response = client.post("/transparencia/consultar", json=payload)
            assert response.status_code == 200
            resultado = response.json()
            assert "status" in resultado
    
    def test_fluxo_consulta_streaming_com_cancelamento(self, mocker):
        """
        Testa fluxo:
        1. Iniciar consulta com streaming
        2. Receber eventos de progresso
        3. Cancelar consulta
        """
        # Step 1: Mock do streaming
        async def mock_stream(*args, **kwargs):
            yield {"status": "processando", "progresso": 25, "id_consulta": "teste-123"}
            yield {"status": "processando", "progresso": 50, "id_consulta": "teste-123"}
        
        mocker.patch(
            'app.services.transparencia_service.transparencia_service.consultar_dados_streaming',
            return_value=mock_stream()
        )
        
        payload = {"data_inicio": "01/2020", "data_fim": "12/2020"}
        
        # Step 2: Iniciar streaming e capturar ID
        with client.stream("POST", "/transparencia/consultar-streaming", json=payload) as response:
            assert response.status_code == 200
            id_consulta = "teste-123"
        
        # Step 3: Mock CORRETO da requisição HTTP de cancelamento
        # Criar mock da resposta
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "mensagem": "Consulta cancelada com sucesso"
        })
        
        # Criar mock do context manager da requisição
        mock_post_context = MagicMock()
        mock_post_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_context.__aexit__ = AsyncMock(return_value=None)
        
        # Criar mock da sessão
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_context)
        
        # Criar mock do context manager da sessão
        mock_session_context = MagicMock()
        mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_context.__aexit__ = AsyncMock(return_value=None)
        
        # Aplicar o patch
        mocker.patch('aiohttp.ClientSession', return_value=mock_session_context)
        
        # Step 4: Cancelar consulta
        response = client.post(f"/transparencia/cancelar/{id_consulta}")
        assert response.status_code == 200
        resultado = response.json()
        assert resultado["status"] == "cancelado"


class TestFluxoIntegradoIPCAETransparencia:
    """Testes E2E integrando IPCA e Transparência."""
    
    def test_fluxo_obter_ipca_referencia_e_consultar_transparencia(self, mocker):
        """
        Testa fluxo completo:
        1. Consultar IPCA mais recente
        2. Usar como referência para consulta de transparência
        """
        # Step 1: Obter dados IPCA
        response = client.get("/ipca")
        assert response.status_code == 200
        dados_ipca = response.json()
        
        # Step 2: Obter data mais recente
        datas = list(dados_ipca["data"].keys())
        if datas:
            data_mais_recente = max(datas, key=lambda d: (d.split("/")[1], d.split("/")[0]))
            
            # Step 3: Usar como referência para consulta de transparência
            mock_consulta = AsyncMock(return_value={
                "status": "completo",
                "total_registros": 0,
                "total_nao_processados": 0,
                "dados": [],
                "dados_nao_processados": [],
                "periodo_base_ipca": data_mais_recente,
                "ipca_referencia": dados_ipca["data"][data_mais_recente],
                "tipo_correcao": "mensal",
                "observacao": None
            })
            mocker.patch(
                'app.services.transparencia_service.transparencia_service.consultar_dados_corrigidos',
                mock_consulta
            )
            
            payload = {
                "data_inicio": "01/2020",
                "data_fim": "12/2020",
                "ipca_referencia": data_mais_recente
            }
            
            response = client.post("/transparencia/consultar", json=payload)
            assert response.status_code == 200
            resultado = response.json()
            assert resultado["periodo_base_ipca"] == data_mais_recente