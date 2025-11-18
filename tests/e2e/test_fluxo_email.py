import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)


class TestFluxoCompletoEmail:
    """Testes E2E para fluxo de envio de email."""
    
    def test_fluxo_envio_email_contato(self, mocker):
        """
        Testa fluxo completo de envio de email de contato.
        """
        # Arrange
        mock_send = mocker.patch(
            'app.services.email_service.email_service.send_contact_email',
            return_value=True
        )
        
        # Step 1: Preparar dados do formulário
        payload = {
            "name": "Maria Silva",
            "email": "maria@example.com",
            "message": "Gostaria de informações sobre a API de correção monetária."
        }
        
        # Step 2: Enviar email
        response = client.post("/email/contact", json=payload)
        
        # Step 3: Verificar sucesso
        assert response.status_code == 200
        assert response.json()["message"] == "Email enviado com sucesso!"
        mock_send.assert_called_once()
    
    def test_fluxo_tentativa_reenvio_apos_falha(self, mocker):
        """
        Testa fluxo:
        1. Primeira tentativa falha
        2. Segunda tentativa com sucesso
        """
        # Step 1: Primeira tentativa (falha)
        mocker.patch(
            'app.services.email_service.email_service.send_contact_email',
            return_value=False
        )
        
        payload = {
            "name": "João",
            "email": "joao@example.com",
            "message": "Teste"
        }
        
        response = client.post("/email/contact", json=payload)
        assert response.status_code == 500
        
        # Step 2: Segunda tentativa (sucesso)
        mocker.patch(
            'app.services.email_service.email_service.send_contact_email',
            return_value=True
        )
        
        response = client.post("/email/contact", json=payload)
        assert response.status_code == 200