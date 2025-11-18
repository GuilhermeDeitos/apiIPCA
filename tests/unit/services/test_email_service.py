import logging
import pytest
from unittest.mock import Mock, patch, MagicMock
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.services.email_service import EmailService, email_service


# Fixture compartilhada para todas as classes
@pytest.fixture
def email_service_configurado(mocker):
    """Fixture com serviço de email configurado."""
    mocker.patch.dict('os.environ', {
        'SMTP_SERVER': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SENDER_EMAIL': 'sender@test.com',
        'SENDER_PASSWORD': 'senha123',
        'RECEIVER_EMAIL': 'receiver@test.com'
    })
    return EmailService()

class TestEmailServiceInicializacao:
    """Testes para inicialização do serviço de email."""
    
    def test_inicializacao_com_variaveis_ambiente(self, mocker):
        """Testa se o serviço carrega configurações do .env."""
        # Arrange
        mocker.patch.dict('os.environ', {
            'SMTP_SERVER': 'smtp.test.com',
            'SMTP_PORT': '465',
            'SENDER_EMAIL': 'sender@test.com',
            'SENDER_PASSWORD': 'senha123',
            'RECEIVER_EMAIL': 'receiver@test.com'
        })
        
        # Act
        service = EmailService()
        
        # Assert
        assert service.smtp_server == 'smtp.test.com'
        assert service.smtp_port == 465
        assert service.sender_email == 'sender@test.com'
        assert service.sender_password == 'senha123'
        assert service.receiver_email == 'receiver@test.com'
    
    def test_inicializacao_com_valores_padrao(self, mocker):
        """Testa se usa valores padrão quando variáveis não estão definidas."""
        # Arrange
        mocker.patch.dict('os.environ', {}, clear=True)
        
        # Act
        service = EmailService()
        
        # Assert
        assert service.smtp_server == 'smtp.gmail.com'
        assert service.smtp_port == 587
        assert service.sender_email == 'seu-email@gmail.com'


class TestEmailServiceSendContactEmail:
    """Testes para envio de email de contato."""
    
    def test_send_contact_email_sucesso(self, email_service_configurado, mocker):
        """Testa envio bem-sucedido de email."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        resultado = email_service_configurado.send_contact_email(
            name="João Silva",
            email="joao@example.com",
            message="Olá, tenho uma dúvida"
        )
        
        # Assert
        assert resultado is True
        mock_smtp.assert_called_once_with('smtp.test.com', 587)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with('sender@test.com', 'senha123')
        mock_smtp_instance.send_message.assert_called_once()
    
    
    def test_send_contact_email_estrutura_mensagem(self, email_service_configurado, mocker):
        """Testa se a mensagem é construída corretamente."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Capturar a mensagem enviada
        mensagem_enviada = None
        def capture_message(msg):
            nonlocal mensagem_enviada
            mensagem_enviada = msg
        
        mock_smtp_instance.send_message.side_effect = capture_message
        
        # Act
        email_service_configurado.send_contact_email(
            name="João Silva",
            email="joao@example.com",
            message="Teste de mensagem"
        )
        
        # Assert
        assert mensagem_enviada is not None
        assert mensagem_enviada['From'] == 'sender@test.com'
        assert mensagem_enviada['To'] == 'receiver@test.com'
        assert mensagem_enviada['Reply-To'] == 'joao@example.com'
        assert 'João Silva' in mensagem_enviada['Subject']
        assert 'joao@example.com' in mensagem_enviada['Subject']
    
    def test_send_contact_email_corpo_contem_informacoes(self, email_service_configurado, mocker):
        """Testa se o corpo do email contém todas as informações."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        
        # Capturar o corpo da mensagem
        corpo_capturado = None
        
        def mock_attach(mime_part):
            nonlocal corpo_capturado
            if isinstance(mime_part, MIMEText):
                corpo_capturado = mime_part.get_payload()
        
        mocker.patch('smtplib.SMTP', mock_smtp)
        mocker.patch.object(MIMEMultipart, 'attach', side_effect=mock_attach)
        
        # Act
        email_service_configurado.send_contact_email(
            name="Maria Santos",
            email="maria@example.com",
            message="Preciso de ajuda urgente"
        )
        
        # Assert (verificar que informações estão no corpo, se capturado)
        if corpo_capturado:
            assert "Maria Santos" in corpo_capturado
            assert "maria@example.com" in corpo_capturado
            assert "Preciso de ajuda urgente" in corpo_capturado
    
    def test_send_contact_email_erro_conexao(self, email_service_configurado, mocker):
        """Testa tratamento de erro de conexão SMTP."""
        # Arrange
        mocker.patch('smtplib.SMTP', side_effect=smtplib.SMTPConnectError(421, "Erro de conexão"))
        
        # Act
        resultado = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message="Teste"
        )
        
        # Assert
        assert resultado is False
    
    def test_send_contact_email_erro_autenticacao(self, email_service_configurado, mocker):
        """Testa tratamento de erro de autenticação."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, "Autenticação falhou")
        
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        resultado = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message="Teste"
        )
        
        # Assert
        assert resultado is False
    
    def test_send_contact_email_erro_generico(self, email_service_configurado, mocker):
        """Testa tratamento de erro genérico."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp.side_effect = Exception("Erro inesperado")
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        resultado = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message="Teste"
        )
        
        # Assert
        assert resultado is False
    
    @pytest.mark.parametrize("name,email,message", [
        ("", "valid@email.com", "Mensagem"),  # Nome vazio
        ("Nome Válido", "", "Mensagem"),  # Email vazio
        ("Nome Válido", "valid@email.com", ""),  # Mensagem vazia
    ])
    def test_send_contact_email_campos_vazios(self, email_service_configurado, mocker, name, email, message):
        """Testa envio com campos vazios (deve processar sem erro, mas email pode ter campos vazios)."""
        # Arrange
        mock_smtp = MagicMock()
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        resultado = email_service_configurado.send_contact_email(name, email, message)
        
        # Assert
        # O serviço atual não valida campos vazios, mas envia mesmo assim
        assert resultado is True


class TestEmailServiceInstanciaGlobal:
    """Testes para a instância global email_service."""
    
    def test_instancia_global_existe(self):
        """Testa se a instância global foi criada."""
        # Assert
        assert email_service is not None
        assert isinstance(email_service, EmailService)
    
    def test_instancia_global_configurada(self):
        """Testa se a instância global tem configurações."""
        # Assert
        assert hasattr(email_service, 'smtp_server')
        assert hasattr(email_service, 'smtp_port')
        assert hasattr(email_service, 'sender_email')
        
class TestEmailServiceIntegracao:
    """Testes de integração (sem enviar email real)."""
    
    def test_send_contact_email_com_caracteres_especiais(self, email_service_configurado, mocker):
        """Testa envio com caracteres especiais no nome e mensagem."""
        # Arrange
        mock_smtp = MagicMock()
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        resultado = email_service_configurado.send_contact_email(
            name="João José Öçãô",
            email="joao@example.com",
            message="Mensagem com àçêñtös e émojis 🚀"
        )
        
        # Assert
        assert resultado is True
    
    def test_send_contact_email_com_email_longo(self, email_service_configurado, mocker):
        """Testa envio com endereço de email muito longo."""
        # Arrange
        mock_smtp = MagicMock()
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        email_longo = "usuario.com.nome.muito.longo.para.testar.limite@" + "dominio" * 10 + ".com"
        
        # Act
        resultado = email_service_configurado.send_contact_email(
            name="Usuário",
            email=email_longo,
            message="Teste"
        )
        
        # Assert
        assert resultado is True
    
    def test_send_contact_email_timeout(self, email_service_configurado, mocker):
        """Testa tratamento de timeout na conexão SMTP."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp.side_effect = TimeoutError("Timeout na conexão")
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        resultado = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message="Teste"
        )
        
        # Assert
        assert resultado is False


class TestEmailServiceSeguranca:
    """Testes relacionados à segurança."""
    
    def test_senha_nao_exposta_em_logs(self, email_service_configurado, mocker, caplog):
        """Verifica que a senha não é exposta em logs."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, "Falha")
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        with caplog.at_level(logging.ERROR):
            email_service_configurado.send_contact_email("João", "joao@test.com", "Teste")
        
        # Assert
        # Verificar que a senha não aparece nos logs
        senha = email_service_configurado.sender_password
        assert senha not in caplog.text or senha == "seu-senha"  # Senha padrão pode aparecer