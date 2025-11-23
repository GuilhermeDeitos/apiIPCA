import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestFluxoCompletoEmail:
    """Testes E2E para fluxo de envio de email."""
    
    def test_fluxo_envio_email_contato_completo(self, mocker):
        """Testa fluxo completo de envio de email de contato."""
        # Arrange
        mock_send = mocker.patch(
            'app.services.email_service.email_service.send_contact_email',
            return_value=(True, "Email enviado com sucesso!")
        )
        
        # Step 1: Preparar dados do formulário
        payload = {
            "name": "Maria Silva",
            "email": "maria@example.com",
            "message": "Gostaria de informações sobre a API de correção monetária do sistema."
        }
        
        # Step 2: Enviar email
        response = client.post("/email/contact", json=payload)
        
        # Step 3: Verificar sucesso
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "sucesso" in response.json()["message"].lower()
        mock_send.assert_called_once()
    
    def test_fluxo_validacao_campos_obrigatorios(self):
        """Testa fluxo de validação de campos obrigatórios."""
        # Step 1: Tentar enviar sem nome
        response = client.post("/email/contact", json={
            "email": "maria@example.com",
            "message": "Mensagem válida"
        })
        assert response.status_code == 422
        
        # Step 2: Tentar enviar sem email
        response = client.post("/email/contact", json={
            "name": "Maria Silva",
            "message": "Mensagem válida"
        })
        assert response.status_code == 422
        
        # Step 3: Tentar enviar sem mensagem
        response = client.post("/email/contact", json={
            "name": "Maria Silva",
            "email": "maria@example.com"
        })
        assert response.status_code == 422
    
    def test_fluxo_tentativa_reenvio_apos_falha(self, mocker):
        """Testa fluxo de reenvio após falha."""
        # Step 1: Primeira tentativa (falha)
        mocker.patch(
            'app.services.email_service.email_service.send_contact_email',
            return_value=(False, "Erro ao conectar ao servidor de email")
        )
        
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Mensagem de teste válida com mais de 10 caracteres"
        }
        
        response = client.post("/email/contact", json=payload)
        assert response.status_code == 500
        
        # Step 2: Segunda tentativa (sucesso)
        mocker.patch(
            'app.services.email_service.email_service.send_contact_email',
            return_value=(True, "Email enviado com sucesso!")
        )
        
        response = client.post("/email/contact", json=payload)
        assert response.status_code == 200
    
    def test_fluxo_correcao_email_invalido(self, mocker):
        """Testa fluxo de correção de email inválido."""
        # Step 1: Enviar com email inválido
        response = client.post("/email/contact", json={
            "name": "João Silva",
            "email": "email-sem-arroba",
            "message": "Mensagem válida com mais de 10 caracteres"
        })
        assert response.status_code == 422
        
        # Step 2: Mockar para sucesso
        mocker.patch(
            'app.services.email_service.email_service.send_contact_email',
            return_value=(True, "Email enviado com sucesso!")
        )
        
        # Step 3: Corrigir e reenviar
        response = client.post("/email/contact", json={
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Mensagem válida com mais de 10 caracteres"
        })
        
        # Deve retornar 200 com mock ativo
        assert response.status_code == 200
        assert response.json()["success"] is True