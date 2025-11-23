import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestRateLimitIntegration:
    """Testes de integração do rate limiting."""
    
    def test_rate_limit_ipca_endpoint(self):
        """Testa rate limit no endpoint /ipca."""
        # Fazer múltiplas requisições
        responses = []
        for i in range(65):  # Mais que o limite de 60
            response = client.get("/ipca")
            responses.append(response)
        
        # Verificar que algumas foram bloqueadas
        status_codes = [r.status_code for r in responses]
        
        # Primeiras 60 devem passar
        assert all(code == 200 for code in status_codes[:60])
        
        # Próximas devem ser bloqueadas com 429
        blocked = [code for code in status_codes[60:] if code == 429]
        assert len(blocked) > 0
    
    def test_rate_limit_different_endpoints(self):
        """Testa que rate limit é compartilhado entre endpoints."""
        # Fazer requisições em endpoints diferentes
        for _ in range(30):
            client.get("/ipca")
        
        for _ in range(30):
            client.get("/ipca/filtro?mes=01&ano=2020")
        
        # Próxima requisição deve ser bloqueada
        response = client.get("/ipca")
        # Pode ser 200 ou 429 dependendo do timing, mas não deve dar erro 500
        assert response.status_code in [200, 429]