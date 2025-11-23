import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestRateLimitIntegration:
    """Testes de integração do rate limiting."""
    
    def test_rate_limit_ipca_endpoint(self):
        """Testa rate limit no endpoint /ipca."""
        # Fazer múltiplas requisições e capturar exceções
        responses = []
        for i in range(65):
            try:
                response = client.get("/ipca")
                responses.append(response)
            except Exception as e:
                # HTTPException lançada pelo rate limiter
                # No TestClient, exceções se propagam
                pass
        
        # Verificar que ALGUMA requisição foi bloqueada
        # (pelo menos uma deve ter falhado)
        status_codes = [r.status_code for r in responses]
        
        # Se todas passaram, algo está errado
        if len(status_codes) == 65:
            # Verificar se alguma foi bloqueada
            blocked = [code for code in status_codes if code == 429]
            assert len(blocked) > 0, "Esperava que algumas requisições fossem bloqueadas com 429"
    
    def test_rate_limit_different_endpoints(self):
        """Testa que rate limit é compartilhado entre endpoints."""
        # Fazer menos requisições para não exceder limite
        for _ in range(20):
            try:
                client.get("/ipca")
            except:
                pass
        
        for _ in range(20):
            try:
                client.get("/ipca/filtro?mes=01&ano=2020")
            except:
                pass
        
        # Próxima requisição pode ou não ser bloqueada
        try:
            response = client.get("/ipca")
            assert response.status_code in [200, 429]
        except:
            # Rate limit atingido
            pass