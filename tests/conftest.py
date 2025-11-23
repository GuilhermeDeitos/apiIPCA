import pytest
from unittest.mock import Mock


@pytest.fixture
def ipca_service_mock():
    """Mock padrão do serviço IPCA."""
    mock = Mock()
    mock.obter_ipca_por_periodo.return_value = 100.0
    mock.calcular_media_anual.return_value = 110.0
    mock.ipca_dict = {
        "01/2020": 100.0,
        "02/2020": 101.5,
        "12/2023": 120.0
    }
    return mock


@pytest.fixture
def dados_transparencia_mock():
    """Dados de exemplo do Portal da Transparência."""
    return [
        {
            "UNIDADE_ORCAMENTARIA": "UNIVERSIDADE ESTADUAL DE LONDRINA",
            "MES": 1,
            "ANO": 2020,
            "ORCAMENTO_INICIAL_LOA": "1000000",
            "EMPENHADO_ATE_MES": "500000"
        },
        {
            "UNIDADE_ORCAMENTARIA": "UNIVERSIDADE ESTADUAL DE MARINGÁ",
            "MES": 2,
            "ANO": 2020,
            "ORCAMENTO_INICIAL_LOA": "2000000",
            "EMPENHADO_ATE_MES": "1000000"
        }
    ]


@pytest.fixture(scope="session")
def test_app():
    """Instância da aplicação FastAPI para testes."""
    from app.main import app
    return app


@pytest.fixture
def client(test_app):
    """Cliente de teste HTTP."""
    from fastapi.testclient import TestClient
    return TestClient(test_app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """
    Reseta o rate limiter antes de cada teste.
    Evita que testes falhem por atingir o limite.
    """
    from app.middlewares.rate_limit import rate_limiter
    
    # Reset antes do teste
    rate_limiter.reset()
    
    yield
    
    # Reset depois do teste
    rate_limiter.reset()


@pytest.fixture(scope="session")
def event_loop():
    """
    Cria um event loop para toda a sessão de testes.
    Necessário para testes assíncronos.
    """
    import asyncio
    
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    
    yield loop
    
    loop.close()