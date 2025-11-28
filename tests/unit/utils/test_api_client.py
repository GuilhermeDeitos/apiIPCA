import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from app.utils.api_client import ApiCrawlerClient


class TestApiCrawlerClientIniciarConsulta:
    """Testes para iniciar consulta na API Crawler."""
    
    @pytest.mark.asyncio
    async def test_iniciar_consulta_sucesso_sincrono(self, mocker):
        """Testa início de consulta com processamento síncrono."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "processamento": "sincrono",
            "dados_por_ano": {"2020": {"dados": [], "total_registros": 0}}
        })
        
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act
        client = ApiCrawlerClient()
        resultado = await client.iniciar_consulta("01/2020", "12/2020")
        
        # Assert
        assert resultado["processamento"] == "sincrono"
        assert "dados_por_ano" in resultado
    
    @pytest.mark.asyncio
    async def test_iniciar_consulta_sucesso_assincrono(self, mocker):
        """Testa início de consulta com processamento assíncrono."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 202
        mock_response.json = AsyncMock(return_value={
            "processamento": "assincrono",
            "id_consulta": "abc-123"
        })
        
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act
        client = ApiCrawlerClient()
        resultado = await client.iniciar_consulta("01/2020", "12/2023")
        
        # Assert
        assert resultado["processamento"] == "assincrono"
        assert "id_consulta" in resultado
    
    @pytest.mark.asyncio
    async def test_iniciar_consulta_erro_servidor(self, mocker):
        """Testa erro quando servidor retorna status 500."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")
        
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act & Assert
        client = ApiCrawlerClient()
        with pytest.raises(Exception, match="Erro na API crawler"):
            await client.iniciar_consulta("01/2020", "12/2020")
    
    @pytest.mark.asyncio
    async def test_iniciar_consulta_erro_conexao(self, mocker):
        """Testa erro de conexão com a API."""
        # Arrange
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.side_effect = aiohttp.ClientError("Connection refused")
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act & Assert
        client = ApiCrawlerClient()
        with pytest.raises(Exception, match="Erro ao conectar com API de coleta de dados"):
            await client.iniciar_consulta("01/2020", "12/2020")


class TestApiCrawlerClientVerificarStatus:
    """Testes para verificar status de consulta."""
    
    @pytest.mark.asyncio
    async def test_verificar_status_consulta_processando(self, mocker):
        """Testa verificação de status durante processamento."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "processando",
            "progresso": 50,
            "dados_parciais_por_ano": {}
        })
        
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_get_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act
        client = ApiCrawlerClient()
        resultado = await client.verificar_status_consulta("abc-123")
        
        # Assert
        assert resultado["status"] == "processando"
        assert resultado["progresso"] == 50
    
    @pytest.mark.asyncio
    async def test_verificar_status_consulta_concluida(self, mocker):
        """Testa verificação de status quando concluída."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "status": "concluido",
            "dados_por_ano": {"2020": {"dados": [], "total_registros": 100}}
        })
        
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_get_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act
        client = ApiCrawlerClient()
        resultado = await client.verificar_status_consulta("abc-123")
        
        # Assert
        assert resultado["status"] == "concluido"
        assert "dados_por_ano" in resultado


class TestApiCrawlerClientVerificarStatusApi:
    """Testes para verificar se API está disponível."""
    
    @pytest.mark.asyncio
    async def test_verificar_status_api_disponivel(self, mocker):
        """Testa quando API está disponível."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "slots_disponiveis": 5,
            "consultas_ativas": 2
        })
        
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_get_ctx.__aexit__.return_value = None
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_get_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act
        client = ApiCrawlerClient()
        resultado = await client.verificar_status_api()
        
        # Assert
        assert resultado["status"] == "ok"
        assert resultado["disponivel"] is True
        assert "slots_disponiveis" in resultado
    
    @pytest.mark.asyncio
    async def test_verificar_status_api_indisponivel(self, mocker):
        """Testa quando API está offline."""
        # Arrange
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.side_effect = aiohttp.ClientConnectionError("Connection refused")
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_get_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act
        client = ApiCrawlerClient()
        resultado = await client.verificar_status_api()
        
        # Assert
        assert resultado["status"] == "erro"
        assert resultado["disponivel"] is False
        assert "erro" in resultado
    
    @pytest.mark.asyncio
    async def test_verificar_status_api_timeout(self, mocker):
        """Testa timeout ao verificar status."""
        # Arrange
        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.side_effect = asyncio.TimeoutError()
        
        mock_session = MagicMock()
        mock_session.get.return_value = mock_get_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act
        client = ApiCrawlerClient()
        resultado = await client.verificar_status_api()
        
        # Assert
        assert resultado["status"] == "erro"
        assert "Timeout" in resultado["erro"]


class TestApiCrawlerClientCancelarConsulta:
    """Testes para cancelamento de consultas."""
    
    @pytest.mark.asyncio
    async def test_cancelar_consulta_sucesso(self, mocker):
        """Testa cancelamento bem-sucedido."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"mensagem": "Consulta cancelada"})
        
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act
        client = ApiCrawlerClient()
        resultado = await client.cancelar_consulta("abc-123")
        
        # Assert
        assert resultado["cancelado"] is True
    
    @pytest.mark.asyncio
    async def test_cancelar_consulta_nao_encontrada(self, mocker):
        """Testa cancelamento de consulta inexistente."""
        # Arrange
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Consulta não encontrada")
        
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__.return_value = mock_response
        mock_post_ctx.__aexit__.return_value = None
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_ctx
        
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None
        
        mocker.patch("aiohttp.ClientSession", return_value=mock_session_ctx)
        
        # Act & Assert
        client = ApiCrawlerClient()
        with pytest.raises(Exception, match="Consulta não encontrada"):
            await client.cancelar_consulta("abc-999")