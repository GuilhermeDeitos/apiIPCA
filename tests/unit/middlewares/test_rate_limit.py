import pytest
from app.middleware.rate_limit import RateLimiter
from fastapi import Request, HTTPException
from unittest.mock import MagicMock


class TestRateLimiter:
    """Testes para o middleware de rate limiting."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Fixture com rate limiter configurado."""
        return RateLimiter(requests_per_minute=5)
    
    @pytest.fixture
    def mock_request(self):
        """Fixture com request mockado."""
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.headers.get.return_value = None
        return request
    
    def test_get_client_ip_direct(self, rate_limiter, mock_request):
        """Testa obtenção de IP direto."""
        ip = rate_limiter._get_client_ip(mock_request)
        assert ip == "127.0.0.1"
    
    def test_get_client_ip_x_forwarded_for(self, rate_limiter, mock_request):
        """Testa obtenção de IP via X-Forwarded-For."""
        mock_request.headers.get.side_effect = lambda key: "192.168.1.1, 10.0.0.1" if key == "X-Forwarded-For" else None
        
        ip = rate_limiter._get_client_ip(mock_request)
        assert ip == "192.168.1.1"
    
    def test_get_client_ip_x_real_ip(self, rate_limiter, mock_request):
        """Testa obtenção de IP via X-Real-IP."""
        def get_header(key):
            if key == "X-Forwarded-For":
                return None
            if key == "X-Real-IP":
                return "192.168.1.2"
            return None
        
        mock_request.headers.get.side_effect = get_header
        
        ip = rate_limiter._get_client_ip(mock_request)
        assert ip == "192.168.1.2"
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_below_limit(self, rate_limiter, mock_request):
        """Testa que requisições abaixo do limite passam."""
        # Fazer 4 requisições (limite é 5)
        for _ in range(4):
            await rate_limiter.check_rate_limit(mock_request)
        
        # Não deve lançar exceção
        assert True
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeds(self, rate_limiter, mock_request):
        """Testa que exceção é lançada ao exceder limite."""
        # Fazer 5 requisições (limite é 5)
        for _ in range(5):
            await rate_limiter.check_rate_limit(mock_request)
        
        # 6ª requisição deve falhar
        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter.check_rate_limit(mock_request)
        
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_different_ips(self, rate_limiter):
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
            await rate_limiter.check_rate_limit(request1)
            await rate_limiter.check_rate_limit(request2)
        
        # Ambos devem ter atingido o limite
        with pytest.raises(HTTPException):
            await rate_limiter.check_rate_limit(request1)
        
        with pytest.raises(HTTPException):
            await rate_limiter.check_rate_limit(request2)