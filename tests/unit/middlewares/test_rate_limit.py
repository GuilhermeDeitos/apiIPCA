import pytest
from app.middlewares.rate_limit import RateLimiter
from fastapi import Request, HTTPException
from unittest.mock import MagicMock
import asyncio


class TestRateLimiter:
    """Testes para o middleware de rate limiting."""
    
    @pytest.fixture
    def rate_limiter_test(self):
        """Fixture com rate limiter configurado para testes."""
        limiter = RateLimiter(requests_per_minute=5)
        yield limiter
        # Cleanup
        limiter.reset()
    
    @pytest.fixture
    def mock_request(self):
        """Fixture com request mockado."""
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None
        return request
    
    def test_get_client_ip_direct(self, rate_limiter_test, mock_request):
        """Testa obtenção de IP direto."""
        ip = rate_limiter_test._get_client_ip(mock_request)
        assert ip == "127.0.0.1"
    
    def test_get_client_ip_x_forwarded_for(self, rate_limiter_test, mock_request):
        """Testa obtenção de IP via X-Forwarded-For."""
        mock_request.headers.get.side_effect = lambda key: "192.168.1.1, 10.0.0.1" if key == "X-Forwarded-For" else None
        
        ip = rate_limiter_test._get_client_ip(mock_request)
        assert ip == "192.168.1.1"
    
    def test_get_client_ip_x_real_ip(self, rate_limiter_test, mock_request):
        """Testa obtenção de IP via X-Real-IP."""
        def get_header(key):
            if key == "X-Forwarded-For":
                return None
            if key == "X-Real-IP":
                return "192.168.1.2"
            return None
        
        mock_request.headers.get.side_effect = get_header
        
        ip = rate_limiter_test._get_client_ip(mock_request)
        assert ip == "192.168.1.2"
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_below_limit(self, rate_limiter_test, mock_request):
        """Testa que requisições abaixo do limite passam."""
        # Fazer 4 requisições (limite é 5)
        for _ in range(4):
            await rate_limiter_test.check_rate_limit(mock_request)
        
        # Não deve lançar exceção
        assert True
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeds(self, rate_limiter_test, mock_request):
        """Testa que exceção é lançada ao exceder limite."""
        # Fazer 5 requisições (limite é 5)
        for _ in range(5):
            await rate_limiter_test.check_rate_limit(mock_request)
        
        # 6ª requisição deve falhar
        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter_test.check_rate_limit(mock_request)
        
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_different_ips(self, rate_limiter_test):
        """Testa que IPs diferentes têm limites independentes."""
        # Criar requests de IPs diferentes
        request1 = MagicMock(spec=Request)
        request1.client.host = "127.0.0.1"
        request1.headers.get.return_value = None
        
        request2 = MagicMock(spec=Request)
        request2.client.host = "192.168.1.1"
        request2.headers.get.return_value = None
        
        # Fazer 5 requisições de cada IP
        for _ in range(5):
            await rate_limiter_test.check_rate_limit(request1)
            await rate_limiter_test.check_rate_limit(request2)
        
        # Ambos devem ter atingido o limite
        with pytest.raises(HTTPException):
            await rate_limiter_test.check_rate_limit(request1)
        
        with pytest.raises(HTTPException):
            await rate_limiter_test.check_rate_limit(request2)
    
    @pytest.mark.asyncio
    async def test_cleanup_task_initialization(self, rate_limiter_test, mock_request):
        """Testa que a tarefa de limpeza é inicializada na primeira requisição."""
        assert not rate_limiter_test._initialized
        
        # Primeira requisição deve inicializar a tarefa
        await rate_limiter_test.check_rate_limit(mock_request)
        
        # Aguardar um pouco para a tarefa ser criada
        await asyncio.sleep(0.1)
        
        assert rate_limiter_test._initialized
        assert rate_limiter_test._cleanup_task is not None
    
    def test_reset(self, rate_limiter_test, mock_request):
        """Testa que o reset limpa todas as requisições."""
        # Simular algumas requisições
        rate_limiter_test.requests["127.0.0.1"].append(pytest.approx(0))
        rate_limiter_test.requests["192.168.1.1"].append(pytest.approx(0))
        
        assert len(rate_limiter_test.requests) == 2
        
        # Reset
        rate_limiter_test.reset()
        
        assert len(rate_limiter_test.requests) == 0
        assert not rate_limiter_test._initialized