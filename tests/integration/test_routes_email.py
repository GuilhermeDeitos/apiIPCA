import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.services.email_service import email_service

client = TestClient(app)


class TestEmailRoutesIntegracao:
    """Testes de integração para o endpoint de email."""
    
    def test_send_contact_email_sucesso(self, mocker):
        """Testa envio bem-sucedido de email de contato."""
        # Arrange
        mock_send = mocker.patch.object(email_service, 'send_contact_email', return_value=True)
        
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Olá, gostaria de mais informações."
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 200
        assert response.json()["message"] == "Email enviado com sucesso!"
        mock_send.assert_called_once_with(
            name="João Silva",
            email="joao@example.com",
            message="Olá, gostaria de mais informações."
        )
    
    def test_send_contact_email_falha_envio(self, mocker):
        """Testa falha no envio de email."""
        # Arrange
        mocker.patch.object(email_service, 'send_contact_email', return_value=False)
        
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Teste"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 500
        assert "Não foi possível enviar o email" in response.json()["detail"]
    
    def test_send_contact_email_email_invalido(self):
        """Testa validação de email inválido."""
        # Arrange
        payload = {
            "name": "João Silva",
            "email": "email-invalido",  # Email sem @
            "message": "Teste"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422  # Validation error
        assert "email" in response.json()["detail"][0]["loc"]
    
    @pytest.mark.parametrize("campo_faltante", ["name", "email", "message"])
    def test_send_contact_email_campos_obrigatorios(self, campo_faltante):
        """Testa que todos os campos são obrigatórios."""
        # Arrange
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Teste"
        }
        del payload[campo_faltante]
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422
        assert campo_faltante in response.json()["detail"][0]["loc"]
    
    def test_send_contact_email_com_caracteres_especiais(self, mocker):
        """Testa envio com caracteres especiais no nome e mensagem."""
        # Arrange
        mocker.patch.object(email_service, 'send_contact_email', return_value=True)
        
        payload = {
            "name": "José Ñoño Öçãô",
            "email": "jose@example.com",
            "message": "Mensagem com àçêñtös e émojis 🚀"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 200
    
    def test_send_contact_email_payload_vazio(self):
        """Testa envio com payload vazio."""
        # Act
        response = client.post("/email/contact", json={})
        
        # Assert
        assert response.status_code == 422


class TestEmailRoutesSeguranca:
    """Testes de segurança para o endpoint de email."""
    
    def test_send_contact_email_protecao_xss(self, mocker):
        """Testa se a API aceita (mas não executa) conteúdo potencialmente malicioso."""
        # Arrange
        mocker.patch.object(email_service, 'send_contact_email', return_value=True)
        
        payload = {
            "name": "<script>alert('XSS')</script>",
            "email": "test@example.com",
            "message": "<img src=x onerror=alert('XSS')>"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        # A API deve aceitar o payload (responsabilidade do frontend sanitizar)
        assert response.status_code == 200
        # Mas o serviço de email deve ser chamado (sanitização ocorre lá se necessário)
    
    def test_send_contact_email_tamanho_maximo_mensagem(self, mocker):
        """Testa se a API aceita mensagens muito longas."""
        # Arrange
        mocker.patch.object(email_service, 'send_contact_email', return_value=True)
        
        payload = {
            "name": "João",
            "email": "joao@example.com",
            "message": "A" * 10000  # Mensagem de 10KB
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        # Verificar se há limite de tamanho (pode depender da sua configuração)
        assert response.status_code in [200, 413, 422]