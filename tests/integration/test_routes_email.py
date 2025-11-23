import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.email_service import email_service

client = TestClient(app)


class TestEmailRoutesIntegracao:
    """Testes de integração para o endpoint de email."""
    
    def test_send_contact_email_sucesso(self, mocker):
        """Testa envio bem-sucedido de email de contato."""
        # Arrange
        mock_send = mocker.patch.object(
            email_service,
            'send_contact_email',
            return_value=(True, "Email enviado com sucesso!")
        )
        
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Olá, gostaria de mais informações sobre o sistema."
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "sucesso" in response.json()["message"].lower()
        mock_send.assert_called_once_with(
            name="João Silva",
            email="joao@example.com",
            message="Olá, gostaria de mais informações sobre o sistema."
        )
    
    def test_send_contact_email_falha_envio(self, mocker):
        """Testa falha no envio de email."""
        # Arrange
        mocker.patch.object(
            email_service,
            'send_contact_email',
            return_value=(False, "Erro ao conectar ao servidor de email")
        )
        
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Mensagem de teste válida com mais de 10 caracteres"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 500
        assert "erro" in response.json()["detail"].lower()
    
    def test_send_contact_email_email_invalido(self):
        """Testa validação de email inválido."""
        # Arrange
        payload = {
            "name": "João Silva",
            "email": "email-invalido",
            "message": "Mensagem válida com mais de 10 caracteres"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("email" in str(error["loc"]) for error in errors)
    
    @pytest.mark.parametrize("campo_faltante", ["name", "email", "message"])
    def test_send_contact_email_campos_obrigatorios(self, campo_faltante):
        """Testa que todos os campos são obrigatórios."""
        # Arrange
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Mensagem válida com mais de 10 caracteres"
        }
        del payload[campo_faltante]
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any(campo_faltante in str(error["loc"]) for error in errors)
    
    def test_send_contact_email_nome_muito_curto(self):
        """Testa validação de nome muito curto."""
        # Arrange
        payload = {
            "name": "J",
            "email": "joao@example.com",
            "message": "Mensagem válida com mais de 10 caracteres"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422
    
    def test_send_contact_email_nome_muito_longo(self):
        """Testa validação de nome muito longo."""
        # Arrange
        payload = {
            "name": "A" * 101,
            "email": "joao@example.com",
            "message": "Mensagem válida com mais de 10 caracteres"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422
    
    def test_send_contact_email_mensagem_muito_curta(self):
        """Testa validação de mensagem muito curta."""
        # Arrange
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Curta"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422
    
    def test_send_contact_email_mensagem_muito_longa(self):
        """Testa validação de mensagem muito longa."""
        # Arrange
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "A" * 5001
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422
    
    def test_send_contact_email_com_caracteres_especiais(self, mocker):
        """Testa envio com caracteres especiais no nome e mensagem."""
        # Arrange
        mocker.patch.object(
            email_service,
            'send_contact_email',
            return_value=(True, "Email enviado com sucesso!")
        )
        
        payload = {
            "name": "José Ñoño Öçãô",
            "email": "jose@example.com",
            "message": "Mensagem com àçêñtös e caracteres especiais válida"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 200
    
    def test_send_contact_email_muitos_links(self):
        """Testa validação de mensagem com muitos links."""
        # Arrange
        payload = {
            "name": "João Silva",
            "email": "joao@example.com",
            "message": "Link1: http://site1.com Link2: http://site2.com Link3: http://site3.com Link4: http://site4.com"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422
    
    def test_send_contact_email_payload_vazio(self):
        """Testa envio com payload vazio."""
        # Act
        response = client.post("/email/contact", json={})
        
        # Assert
        assert response.status_code == 422
    
    def test_send_contact_email_nome_com_caracteres_invalidos(self):
        """Testa validação de nome com caracteres inválidos."""
        # Arrange
        payload = {
            "name": "João123@#$",
            "email": "joao@example.com",
            "message": "Mensagem válida com mais de 10 caracteres"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 422


class TestEmailRoutesSeguranca:
    """Testes de segurança para o endpoint de email."""
    
    def test_send_contact_email_protecao_xss(self, mocker):
        """Testa se a API aceita e sanitiza conteúdo potencialmente malicioso."""
        # Arrange
        mocker.patch.object(
            email_service,
            'send_contact_email',
            return_value=(True, "Email enviado com sucesso!")
        )
        
        payload = {
            "name": "João Silva Normal",
            "email": "test@example.com",
            "message": "Mensagem normal sem código malicioso apenas texto"
        }
        
        # Act
        response = client.post("/email/contact", json=payload)
        
        # Assert
        assert response.status_code == 200


class TestEmailHealth:
    """Testes para o endpoint de health check do email."""
    
    def test_email_health_configurado(self, mocker):
        """Testa health check quando serviço está configurado."""
        # Arrange
        mocker.patch.object(email_service, 'sender_password', 'senha123')
        
        # Act
        response = client.get("/email/health")
        
        # Assert
        assert response.status_code == 200
        assert response.json()["status"] == "configured"
    
    def test_email_health_nao_configurado(self, mocker):
        """Testa health check quando serviço não está configurado."""
        # Arrange
        mocker.patch.object(email_service, 'sender_password', '')
        
        # Act
        response = client.get("/email/health")
        
        # Assert
        assert response.status_code == 200
        assert response.json()["status"] == "not_configured"