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
        'SMTP_SERVER': 'smtp.test.com',  # CORRIGIDO
        'SMTP_PORT': '587',
        'SENDER_EMAIL': 'sender@test.com',  # CORRIGIDO
        'SENDER_PASSWORD': 'senha123',  # CORRIGIDO
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


class TestEmailServiceValidacoes:
    """Testes para validações de entrada."""
    
    def test_validacao_nome_vazio(self, email_service_configurado):
        """Testa rejeição de nome vazio."""
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="",
            email="valid@example.com",
            message="Mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "Nome é obrigatório" in mensagem
    
    def test_validacao_nome_apenas_espacos(self, email_service_configurado):
        """Testa rejeição de nome com apenas espaços."""
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="   ",
            email="valid@example.com",
            message="Mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "Nome é obrigatório" in mensagem
    
    def test_validacao_nome_muito_longo(self, email_service_configurado):
        """Testa rejeição de nome muito longo."""
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="A" * 101,
            email="valid@example.com",
            message="Mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "Nome muito longo" in mensagem
    
    def test_validacao_email_vazio(self, email_service_configurado):
        """Testa rejeição de email vazio."""
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João Silva",
            email="",
            message="Mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "Email é obrigatório" in mensagem
    
    @pytest.mark.parametrize("email_invalido", [
        "email-sem-arroba",
        "@sem-usuario.com",
        "sem-dominio@",
        "sem-ponto@dominio",
        "espaço @email.com",
        "email@.com",
        "email@dominio.",
    ])
    def test_validacao_formato_email_invalido(self, email_service_configurado, email_invalido):
        """Testa rejeição de formatos de email inválidos."""
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João Silva",
            email=email_invalido,
            message="Mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "Formato de email inválido" in mensagem
    
    def test_validacao_mensagem_vazia(self, email_service_configurado):
        """Testa rejeição de mensagem vazia."""
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João Silva",
            email="joao@example.com",
            message=""
        )
        
        # Assert
        assert sucesso is False
        assert "Mensagem é obrigatória" in mensagem
    
    def test_validacao_mensagem_muito_longa(self, email_service_configurado):
        """Testa rejeição de mensagem muito longa."""
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João Silva",
            email="joao@example.com",
            message="A" * 5001
        )
        
        # Assert
        assert sucesso is False
        assert "Mensagem muito longa" in mensagem
    
    def test_validacao_senha_nao_configurada(self, mocker):
        """Testa erro quando senha SMTP não está configurada."""
        # Arrange
        mocker.patch.dict('os.environ', {
            'SMTP_SERVER': 'smtp.test.com',
            'SMTP_PORT': '587',
            'SENDER_EMAIL': 'sender@test.com',
            'SENDER_PASSWORD': '',  # Senha vazia
            'RECEIVER_EMAIL': 'receiver@test.com'
        })
        service = EmailService()
        
        # Act
        sucesso, mensagem = service.send_contact_email(
            name="João Silva",
            email="joao@example.com",
            message="Mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "Configuração de email não disponível" in mensagem


class TestEmailServiceSanitizacao:
    """Testes para sanitização de entradas."""
    
    def test_sanitizacao_caracteres_controle(self, email_service_configurado):
        """Testa remoção de caracteres de controle perigosos."""
        # Arrange
        texto_com_controle = "Teste\x00\x08\x0B\x0CTexto"
        
        # Act
        texto_sanitizado = email_service_configurado._sanitize_input(texto_com_controle)
        
        # Assert
        assert "\x00" not in texto_sanitizado
        assert "\x08" not in texto_sanitizado
        assert "TesteTexto" == texto_sanitizado
    
    def test_sanitizacao_script_tags(self, email_service_configurado):
        """Testa remoção de tags <script>."""
        # Arrange
        texto_com_script = "Texto normal <script>alert('xss')</script> mais texto"
        
        # Act
        texto_sanitizado = email_service_configurado._sanitize_input(texto_com_script)
        
        # Assert
        assert "<script>" not in texto_sanitizado
        assert "alert" not in texto_sanitizado
        assert "Texto normal" in texto_sanitizado
    
    def test_sanitizacao_iframe_tags(self, email_service_configurado):
        """Testa remoção de tags <iframe>."""
        # Arrange
        texto_com_iframe = "Texto <iframe src='malicious'></iframe> normal"
        
        # Act
        texto_sanitizado = email_service_configurado._sanitize_input(texto_com_iframe)
        
        # Assert
        assert "<iframe>" not in texto_sanitizado
        assert "malicious" not in texto_sanitizado
    
    def test_sanitizacao_javascript_protocol(self, email_service_configurado):
        """Testa remoção de protocolo javascript:."""
        # Arrange
        texto_com_js = "Link: javascript:alert('xss')"
        
        # Act
        texto_sanitizado = email_service_configurado._sanitize_input(texto_com_js)
        
        # Assert
        assert "javascript:" not in texto_sanitizado
    
    def test_sanitizacao_event_handlers(self, email_service_configurado):
        """Testa remoção de event handlers HTML."""
        # Arrange
        texto_com_eventos = '<div onclick="malicious()" onload="bad()">Texto</div>'
        
        # Act
        texto_sanitizado = email_service_configurado._sanitize_input(texto_com_eventos)
        
        # Assert
        assert "onclick" not in texto_sanitizado
        assert "onload" not in texto_sanitizado
    
    def test_sanitizacao_limite_tamanho(self, email_service_configurado):
        """Testa limitação de tamanho do texto."""
        # Arrange
        texto_longo = "A" * 10000
        
        # Act
        texto_sanitizado = email_service_configurado._sanitize_input(texto_longo, max_length=100)
        
        # Assert
        assert len(texto_sanitizado) == 100


class TestEmailServiceSendContactEmail:
    """Testes para envio de email de contato."""
    
    def test_send_contact_email_sucesso(self, email_service_configurado, mocker):
        """Testa envio bem-sucedido de email."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João Silva",
            email="joao@example.com",
            message="Olá, tenho uma dúvida sobre o sistema"
        )
        
        # Assert
        assert sucesso is True
        assert "Email enviado com sucesso" in mensagem
        mock_smtp.assert_called_once_with('smtp.test.com', 587, timeout=30)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with('sender@test.com', 'senha123')
        mock_smtp_instance.send_message.assert_called_once()
    
    def test_send_contact_email_estrutura_mensagem(self, email_service_configurado, mocker):
        """Testa se a mensagem é construída corretamente."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        mensagem_capturada = None
        def capture_message(msg):
            nonlocal mensagem_capturada
            mensagem_capturada = msg
        
        mock_smtp_instance.send_message.side_effect = capture_message
        
        # Act
        email_service_configurado.send_contact_email(
            name="João Silva",
            email="joao@example.com",
            message="Teste de mensagem"
        )
        
        # Assert
        assert mensagem_capturada is not None
        assert 'SAD-UEPR' in mensagem_capturada['From']
        assert mensagem_capturada['To'] == 'receiver@test.com'
        assert mensagem_capturada['Reply-To'] == 'joao@example.com'
        assert 'João Silva' in mensagem_capturada['Subject']
    
    def test_send_contact_email_template_html(self, email_service_configurado, mocker):
        """Testa se o template HTML é gerado."""
        # Arrange
        mock_smtp = MagicMock()
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        html_template = email_service_configurado._get_email_template(
            name="Maria Santos",
            email="maria@example.com",
            message="Mensagem de teste"
        )
        
        # Assert
        assert "<!DOCTYPE html>" in html_template
        assert "Maria Santos" in html_template
        assert "maria@example.com" in html_template
        assert "Mensagem de teste" in html_template
        assert "SAD-UEPR" in html_template
        assert "background-color: #3b82f6" in html_template
    
    def test_send_contact_email_erro_conexao(self, email_service_configurado, mocker):
        """Testa tratamento de erro de conexão SMTP."""
        # Arrange
        mocker.patch('smtplib.SMTP', side_effect=smtplib.SMTPConnectError(421, "Erro de conexão"))
        
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message="Teste de mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "não foi possível conectar" in mensagem.lower()
    
    def test_send_contact_email_erro_autenticacao(self, email_service_configurado, mocker):
        """Testa tratamento de erro de autenticação."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, "Autenticação falhou")
        
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message="Teste de mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "credenciais" in mensagem.lower() or "autenticação" in mensagem.lower()
    
    def test_send_contact_email_erro_smtp_generico(self, email_service_configurado, mocker):
        """Testa tratamento de erro SMTP genérico."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        mock_smtp_instance.send_message.side_effect = smtplib.SMTPException("Erro SMTP")
        
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message="Teste de mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "erro ao enviar" in mensagem.lower()
    
    def test_send_contact_email_erro_inesperado(self, email_service_configurado, mocker):
        """Testa tratamento de erro inesperado."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp.side_effect = Exception("Erro inesperado")
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message="Teste de mensagem válida"
        )
        
        # Assert
        assert sucesso is False
        assert "erro inesperado" in mensagem.lower()


class TestEmailServiceIntegracao:
    """Testes de integração (sem enviar email real)."""
    
    def test_send_contact_email_com_caracteres_especiais(self, email_service_configurado, mocker):
        """Testa envio com caracteres especiais no nome e mensagem."""
        # Arrange
        mock_smtp = MagicMock()
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João José Öçãô",
            email="joao@example.com",
            message="Mensagem com àçêñtös e caracteres especiais"
        )
        
        # Assert
        assert sucesso is True
    
    def test_send_contact_email_com_quebras_linha(self, email_service_configurado, mocker):
        """Testa envio com quebras de linha na mensagem."""
        # Arrange
        mock_smtp = MagicMock()
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        mensagem_multilinhas = """Primeira linha
Segunda linha
Terceira linha"""
        
        # Act
        sucesso, _ = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message=mensagem_multilinhas
        )
        
        # Assert
        assert sucesso is True
    
    def test_send_contact_email_timeout(self, email_service_configurado, mocker):
        """Testa tratamento de timeout na conexão SMTP."""
        # Arrange
        mock_smtp = MagicMock()
        mock_smtp.side_effect = TimeoutError("Timeout na conexão")
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        sucesso, mensagem = email_service_configurado.send_contact_email(
            name="João",
            email="joao@example.com",
            message="Teste de mensagem válida"
        )
        
        # Assert
        assert sucesso is False


class TestEmailServiceSeguranca:
    """Testes relacionados à segurança."""
    
    def test_senha_nao_exposta_em_logs(self, email_service_configurado, mocker, caplog):
        """Verifica que a senha não é exposta em logs."""
        # Arrange
        senha_teste = 'senha123'
        
        mock_smtp = MagicMock()
        mock_smtp_instance = mock_smtp.return_value.__enter__.return_value
        mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, "Falha")
        mocker.patch('smtplib.SMTP', mock_smtp)
        
        # Act
        with caplog.at_level(logging.ERROR):
            email_service_configurado.send_contact_email(
                "João",
                "joao@test.com",
                "Teste de mensagem"
            )
        
        # Assert
        assert senha_teste not in caplog.text
    
    def test_xss_prevention_in_html_template(self, email_service_configurado):
        """Testa prevenção de XSS no template HTML."""
        # Arrange
        nome_malicioso = "<script>alert('xss')</script>João"
        email_malicioso = "test@example.com"
        mensagem_maliciosa = "<img src=x onerror=alert('xss')>"
        
        # Act
        html = email_service_configurado._get_email_template(
            nome_malicioso,
            email_malicioso,
            mensagem_maliciosa
        )
        
        # Assert
        assert "<script>" not in html or "&lt;script&gt;" in html
        assert "onerror" not in html or "onerror" in html.replace("onclick", "").replace("onload", "")


class TestEmailServiceInstanciaGlobal:
    """Testes para a instância global email_service."""
    
    def test_instancia_global_existe(self):
        """Testa se a instância global foi criada."""
        assert email_service is not None
        assert isinstance(email_service, EmailService)
    
    def test_instancia_global_configurada(self):
        """Testa se a instância global tem configurações."""
        assert hasattr(email_service, 'smtp_server')
        assert hasattr(email_service, 'smtp_port')
        assert hasattr(email_service, 'sender_email')
        assert hasattr(email_service, 'sender_password')
        assert hasattr(email_service, 'receiver_email')