import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.utils.data_loader import (
    consultar_transparencia_streaming,
    carregar_dados_portal_transparencia,
    processar_correcao_dados,
    reorganizar_dados_por_ano,
    verificar_status_api_crawler,
    cancelar_consulta_transparencia
)


@pytest.mark.asyncio
class TestConsultarTransparenciaStreaming:
    """Testes de integração do orquestrador principal."""
    
    async def test_consultar_streaming_processamento_sincrono(self, mocker):
        """Testa orquestração completa com processamento síncrono."""
        # Arrange - Mock do ApiCrawlerClient
        mock_api_client = MagicMock()
        mock_api_client.iniciar_consulta = AsyncMock(return_value={
            "processamento": "sincrono",
            "dados_por_ano": {
                "2020": {
                    "dados": [
                        {
                            "UNIDADE_ORCAMENTARIA": "UEL",
                            "MES": 1,
                            "ANO": 2020,
                            "_ano_validado": 2020,
                            "ORCAMENTO_INICIAL_LOA": "1000000"
                        }
                    ]
                }
            }
        })
        
        mocker.patch("app.utils.data_loader.ApiCrawlerClient", return_value=mock_api_client)
        
        # Mock do ipca_service
        with patch("app.services.ipca_service.ipca_service") as mock_ipca_service:
            mock_ipca_service.obter_ipca_por_periodo.return_value = 100.0
            mock_ipca_service.calcular_media_anual.return_value = 110.0
            mock_ipca_service.converter_valor_monetario_string.side_effect = lambda v: float(str(v).replace(".", "").replace(",", "."))
            mock_ipca_service.formatar_valor_brasileiro.side_effect = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            # Act
            eventos = []
            async for evento in consultar_transparencia_streaming("01/2020", "12/2020", "mensal"):
                eventos.append(evento)
            
            # Assert
            assert len(eventos) >= 2  # Parcial + completo
            assert eventos[-1]["status"] == "completo"
            assert "total_registros" in eventos[-1]
    
    async def test_consultar_streaming_cancelamento(self, mocker):
        """Testa cancelamento da operação."""
        # Arrange
        cancel_event = asyncio.Event()
        cancel_event.set()  # Já cancelado
        
        # Act
        eventos = []
        async for evento in consultar_transparencia_streaming(
            "01/2020",
            "12/2020",
            "mensal",
            cancel_event=cancel_event
        ):
            eventos.append(evento)
        
        # Assert
        assert len(eventos) == 0  # Nenhum evento emitido


@pytest.mark.asyncio
class TestFuncoesPublicas:
    """Testes das funções públicas da interface legada."""
    
    async def test_carregar_dados_portal_transparencia(self, mocker):
        """Testa função legada de carregamento."""
        # Arrange
        async def mock_generator():
            # Evento parcial com TODOS os campos esperados
            yield {
                "status": "parcial",
                "ano_processado": 2020,
                "total_registros_ano": 5,  # ✅ Campo obrigatório
                "total_nao_processados_ano": 0,  # ✅ Campo obrigatório
                "dados": []
            }
            # Evento completo
            yield {
                "status": "completo",
                "total_registros": 10,
                "total_nao_processados": 0,
                "dados": [],
                "dados_por_ano": {},
                "periodo_base_ipca": "12/2023",
                "ipca_referencia": 120.0,
                "tipo_correcao": "mensal"
            }
        
        mocker.patch(
            "app.utils.data_loader.consultar_transparencia_streaming",
            return_value=mock_generator()
        )
        
        # Act
        resultado = await carregar_dados_portal_transparencia("01/2020", "12/2020")
        
        # Assert
        assert resultado["status"] == "completo"
        assert "total_registros" in resultado
        assert resultado["total_registros"] == 10
    
    async def test_carregar_dados_portal_transparencia_apenas_completo(self, mocker):
        """Testa quando recebe apenas o evento completo (sem parciais)."""
        # Arrange
        async def mock_generator():
            # Apenas evento completo (sem parciais)
            yield {
                "status": "completo",
                "total_registros": 100,
                "total_nao_processados": 5,
                "dados": [],
                "dados_por_ano": {"2020": {"dados": [], "total_registros": 100}},
                "periodo_base_ipca": "12/2023",
                "ipca_referencia": 120.0,
                "tipo_correcao": "mensal"
            }
        
        mocker.patch(
            "app.utils.data_loader.consultar_transparencia_streaming",
            return_value=mock_generator()
        )
        
        # Act
        resultado = await carregar_dados_portal_transparencia("01/2020", "12/2020")
        
        # Assert
        assert resultado["status"] == "completo"
        assert resultado["total_registros"] == 100
    
    async def test_verificar_status_api_crawler(self, mocker):
        """Testa verificação de status da API."""
        # Arrange
        mock_api_client = MagicMock()
        mock_api_client.verificar_status_api = AsyncMock(return_value={
            "status": "ok",
            "disponivel": True
        })
        
        mocker.patch("app.utils.data_loader.ApiCrawlerClient", return_value=mock_api_client)
        
        # Act
        resultado = await verificar_status_api_crawler()
        
        # Assert
        assert resultado["status"] == "ok"
        assert resultado["disponivel"] is True
    
    async def test_cancelar_consulta_transparencia(self, mocker):
        """Testa cancelamento de consulta."""
        # Arrange
        mock_api_client = MagicMock()
        mock_api_client.cancelar_consulta = AsyncMock(return_value={
            "cancelado": True
        })
        
        mocker.patch("app.utils.data_loader.ApiCrawlerClient", return_value=mock_api_client)
        
        # Act
        resultado = await cancelar_consulta_transparencia("abc-123")
        
        # Assert
        assert resultado["cancelado"] is True


class TestFuncoesLegacySincronas:
    """Testes de funções síncronas legadas."""
    
    def test_processar_correcao_dados_interface_legada(self):
        """Testa interface legada de processar_correcao_dados."""
        # Arrange
        ipca_service_mock = MagicMock()
        ipca_service_mock.obter_ipca_por_periodo.return_value = 100.0
        ipca_service_mock.converter_valor_monetario_string.side_effect = lambda v: float(str(v).replace(".", "").replace(",", "."))
        ipca_service_mock.formatar_valor_brasileiro.side_effect = lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        dados = [
            {
                "ANO": "2020",
                "MES": "1",
                "ORCAMENTO_INICIAL_LOA": "1000000"
            }
        ]
        
        # Act
        dados_corrigidos, dados_nao_processados = processar_correcao_dados(
            dados,
            ipca_base=120.0,
            periodo_base="12/2023",
            ipca_service=ipca_service_mock,
            tipo_correcao="mensal",
            ano_contexto=2020
        )
        
        # Assert
        assert len(dados_corrigidos) == 1
        assert "_correcao_aplicada" in dados_corrigidos[0]
    
    def test_reorganizar_dados_por_ano_interface_legada(self):
        """Testa interface legada de reorganizar_dados_por_ano."""
        # Arrange
        dados = [
            {"_ano_validado": 2020, "VALOR": "100"},
            {"_ano_validado": 2021, "VALOR": "200"}
        ]
        
        # Act
        resultado = reorganizar_dados_por_ano(dados)
        
        # Assert
        assert "2020" in resultado
        assert "2021" in resultado
        assert resultado["2020"]["total_registros"] == 1