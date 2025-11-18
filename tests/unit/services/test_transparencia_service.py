import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.services.transparencia_service import TransparenciaService, transparencia_service


class TestTransparenciaServiceConsultarDadosCorrigidos:
    """Testes para consulta de dados com correção monetária."""
    
    @pytest.fixture
    def transparencia_service_instance(self):
        """Instância do serviço para testes."""
        return TransparenciaService()
    
    @pytest.mark.asyncio
    async def test_consultar_dados_corrigidos_sucesso(self, transparencia_service_instance, mocker):
        """Testa consulta bem-sucedida com correção monetária."""
        # Arrange
        mock_resultado = {
            "dados_por_ano": {
                "2020": {
                    "dados": [{"UNIDADE_ORCAMENTARIA": "UEL", "ORCAMENTO_INICIAL_LOA": "1.200,00"}],
                    "total_registros": 1
                }
            },
            "total_registros": 1,
            "tipo_correcao": "mensal"
        }
        
        mock_carregar = mocker.patch(
            "app.services.transparencia_service.carregar_dados_portal_transparencia",
            new_callable=AsyncMock,
            return_value=mock_resultado
        )
        
        # Act
        resultado = await transparencia_service_instance.consultar_dados_corrigidos(
            data_inicio="01/2020",
            data_fim="12/2020",
            tipo_correcao="mensal",
            ipca_referencia="12/2023"
        )
        
        # Assert
        assert resultado == mock_resultado
        mock_carregar.assert_called_once_with("01/2020", "12/2020", "mensal", "12/2023")
    
    @pytest.mark.asyncio
    async def test_consultar_dados_corrigidos_sem_ipca_referencia(self, transparencia_service_instance, mocker):
        """Testa consulta sem especificar IPCA de referência (usa padrão)."""
        # Arrange
        mock_resultado = {"total_registros": 0}
        mock_carregar = mocker.patch(
            "app.services.transparencia_service.carregar_dados_portal_transparencia",
            new_callable=AsyncMock,
            return_value=mock_resultado
        )
        
        # Act
        resultado = await transparencia_service_instance.consultar_dados_corrigidos(
            data_inicio="01/2020",
            data_fim="12/2020"
        )
        
        # Assert
        mock_carregar.assert_called_once_with("01/2020", "12/2020", "mensal", None)
    
    @pytest.mark.asyncio
    async def test_consultar_dados_corrigidos_erro_na_consulta(self, transparencia_service_instance, mocker):
        """Testa tratamento de erro durante consulta."""
        # Arrange
        mocker.patch(
            "app.services.transparencia_service.carregar_dados_portal_transparencia",
            new_callable=AsyncMock,
            side_effect=Exception("Erro de conexão")
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Erro ao processar dados do Portal da Transparência"):
            await transparencia_service_instance.consultar_dados_corrigidos("01/2020", "12/2020")
    
    @pytest.mark.asyncio
    async def test_consultar_dados_corrigidos_tipo_correcao_anual(self, transparencia_service_instance, mocker):
        """Testa consulta com correção anual."""
        # Arrange
        mock_resultado = {"total_registros": 5, "tipo_correcao": "anual"}
        mock_carregar = mocker.patch(
            "app.services.transparencia_service.carregar_dados_portal_transparencia",
            new_callable=AsyncMock,
            return_value=mock_resultado
        )
        
        # Act
        resultado = await transparencia_service_instance.consultar_dados_corrigidos(
            data_inicio="01/2020",
            data_fim="12/2020",
            tipo_correcao="anual"
        )
        
        # Assert
        assert resultado["tipo_correcao"] == "anual"
        mock_carregar.assert_called_once_with("01/2020", "12/2020", "anual", None)


@pytest.mark.asyncio
class TestTransparenciaServiceConsultarDadosStreaming:
    """Testes para consulta com streaming."""
    
    @pytest.fixture
    def transparencia_service_instance(self):
        """Instância do serviço para testes."""
        return TransparenciaService()
    
    async def test_consultar_dados_streaming_sucesso(self, transparencia_service_instance, mocker):
        """Testa consulta streaming bem-sucedida."""
        # Arrange
        async def mock_generator():
            yield {"status": "processando", "progresso": 50}
            yield {"status": "completo", "total_registros": 10}
        
        mocker.patch(
            "app.services.transparencia_service.consultar_transparencia_streaming",
            return_value=mock_generator()
        )
        
        # Act
        chunks = []
        async for chunk in transparencia_service_instance.consultar_dados_streaming("01/2020", "12/2020"):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 2
        assert chunks[0]["status"] == "processando"
        assert chunks[1]["status"] == "completo"
    
    async def test_consultar_dados_streaming_com_cancelamento(self, transparencia_service_instance, mocker):
        """Testa cancelamento da consulta streaming."""
        # Arrange
        cancel_event = asyncio.Event()
        cancel_event.set()  # Já cancelado
        
        async def mock_generator():
            yield {"status": "cancelado"}
        
        mocker.patch(
            "app.services.transparencia_service.consultar_transparencia_streaming",
            return_value=mock_generator()
        )
        
        # Act
        chunks = []
        async for chunk in transparencia_service_instance.consultar_dados_streaming(
            "01/2020", "12/2020", cancel_event=cancel_event
        ):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 1
        assert chunks[0]["status"] == "cancelado"
    
    async def test_consultar_dados_streaming_erro(self, transparencia_service_instance, mocker):
        """Testa tratamento de erro no streaming."""
        # Arrange
        async def mock_generator():
            raise Exception("Erro na consulta")
            # yield nunca é executado, mas precisa estar aqui para ser um generator
            yield  # pragma: no cover
        
        mocker.patch(
            "app.services.transparencia_service.consultar_transparencia_streaming",
            return_value=mock_generator()
        )
        
        # Act
        chunks = []
        try:
            async for chunk in transparencia_service_instance.consultar_dados_streaming("01/2020", "12/2020"):
                chunks.append(chunk)
        except Exception:
            # Se a exceção não for tratada internamente, capturar aqui
            pass
        
        # Assert
        # Verificar que o serviço trata o erro e retorna um chunk de erro
        assert len(chunks) >= 1
        if chunks:
            assert chunks[-1]["status"] == "erro"
            assert "erro" in chunks[-1] or "Erro na consulta" in str(chunks[-1])
    
    async def test_consultar_dados_streaming_cancelamento_durante_processamento(self, transparencia_service_instance, mocker):
        """Testa cancelamento durante o processamento."""
        # Arrange
        cancel_event = asyncio.Event()
        
        async def mock_generator():
            yield {"status": "processando", "progresso": 30}
            cancel_event.set()  # Simular cancelamento
            yield {"status": "cancelado"}
        
        mocker.patch(
            "app.services.transparencia_service.consultar_transparencia_streaming",
            return_value=mock_generator()
        )
        
        # Act
        chunks = []
        async for chunk in transparencia_service_instance.consultar_dados_streaming(
            "01/2020", "12/2020", cancel_event=cancel_event
        ):
            chunks.append(chunk)
        
        # Assert
        assert any(c["status"] == "cancelado" for c in chunks)


class TestTransparenciaServiceInstanciaGlobal:
    """Testes para a instância global transparencia_service."""
    
    def test_instancia_global_existe(self):
        """Testa se a instância global foi criada."""
        # Assert
        assert transparencia_service is not None
        assert isinstance(transparencia_service, TransparenciaService)
        
class TestTransparenciaServiceParametrosInvalidos:
    """Testes com parâmetros inválidos."""
    
    @pytest.fixture
    def transparencia_service_instance(self):
        """Instância do serviço para testes."""
        return TransparenciaService()
    
    @pytest.mark.asyncio
    async def test_consultar_dados_corrigidos_data_inicio_invalida(self, transparencia_service_instance, mocker):
        """Testa com data de início inválida."""
        # Arrange
        mocker.patch(
            "app.services.transparencia_service.carregar_dados_portal_transparencia",
            new_callable=AsyncMock,
            side_effect=ValueError("Data inválida")
        )
        
        # Act & Assert
        with pytest.raises(Exception):
            await transparencia_service_instance.consultar_dados_corrigidos("13/2020", "12/2020")
    
    @pytest.mark.asyncio
    async def test_consultar_dados_corrigidos_tipo_correcao_invalido(self, transparencia_service_instance, mocker):
        """Testa com tipo de correção inválido."""
        # Arrange
        mocker.patch(
            "app.services.transparencia_service.carregar_dados_portal_transparencia",
            new_callable=AsyncMock,
            side_effect=ValueError("Tipo de correção inválido")
        )
        
        # Act & Assert
        with pytest.raises(Exception):
            await transparencia_service_instance.consultar_dados_corrigidos(
                "01/2020", "12/2020", tipo_correcao="invalido"
            )
    
    @pytest.mark.asyncio
    async def test_consultar_dados_streaming_eventos_vazios(self, transparencia_service_instance, mocker):
        """Testa quando o streaming não retorna eventos."""
        # Arrange
        async def mock_generator():
            # Generator vazio - nenhum evento emitido
            return
            yield  # pragma: no cover
        
        mocker.patch(
            "app.services.transparencia_service.consultar_transparencia_streaming",
            return_value=mock_generator()
        )
        
        # Act
        chunks = []
        async for chunk in transparencia_service_instance.consultar_dados_streaming("01/2020", "12/2020"):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 0


class TestTransparenciaServicePerformance:
    """Testes relacionados a performance."""
    
    @pytest.fixture
    def transparencia_service_instance(self):
        """Instância do serviço para testes."""
        return TransparenciaService()
    
    @pytest.mark.asyncio
    async def test_consultar_dados_streaming_muitos_eventos(self, transparencia_service_instance, mocker):
        """Testa streaming com grande volume de eventos."""
        # Arrange
        async def mock_generator():
            for i in range(100):
                yield {"status": "processando", "progresso": i}
            yield {"status": "completo", "total_registros": 10000}
        
        mocker.patch(
            "app.services.transparencia_service.consultar_transparencia_streaming",
            return_value=mock_generator()
        )
        
        # Act
        chunks = []
        async for chunk in transparencia_service_instance.consultar_dados_streaming("01/2020", "12/2020"):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 101  # 100 progressos + 1 completo
        assert chunks[-1]["status"] == "completo"
        assert chunks[-1]["total_registros"] == 10000