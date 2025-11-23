import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import logging
import re
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        """Inicializa o serviço de email com as configurações do servidor SMTP."""
        self.smtp_server = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SMTP_USER", "seu-email@gmail.com")
        self.sender_password = os.getenv("SMTP_PASSWORD", "")
        self.receiver_email = os.getenv("RECEIVER_EMAIL", os.getenv("SMTP_USER", ""))
        
        # Log de inicialização (sem mostrar senha)
        logger.info(f"Email service initialized - SMTP: {self.smtp_server}:{self.smtp_port}")
        logger.info(f"Sender: {self.sender_email}")
        logger.info(f"Receiver: {self.receiver_email}")
    
    def _sanitize_input(self, text: str, max_length: int = 5000) -> str:
        """
        Sanitiza entrada removendo caracteres perigosos e limitando tamanho.
        
        Args:
            text: Texto a ser sanitizado
            max_length: Comprimento máximo permitido
            
        Returns:
            Texto sanitizado
        """
        if not text:
            return ""
        
        # Limitar tamanho
        text = text[:max_length]
        
        # Remover caracteres de controle perigosos
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Remover tags HTML/script potencialmente perigosas
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<iframe[^>]*>.*?</iframe>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
        text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _validate_email_format(self, email: str) -> bool:
        """Valida formato básico de email."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _get_email_template(self, name: str, email: str, message: str) -> str:
        """
        Gera template HTML do email seguindo identidade visual do SAD-UEPR.
        
        Args:
            name: Nome do remetente
            email: Email do remetente
            message: Mensagem
            
        Returns:
            HTML formatado
        """
        timestamp = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        
        # Escapar HTML para prevenir XSS
        name_escaped = self._sanitize_input(name, 100)
        email_escaped = self._sanitize_input(email, 100)
        message_escaped = self._sanitize_input(message, 5000).replace('\n', '<br>')
        
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contato SAD-UEPR</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4;">
    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #f4f4f4; padding: 40px 0;">
        <tr>
            <td align="center">
                <table cellpadding="0" cellspacing="0" border="0" width="600" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600; letter-spacing: 1px;">SAD-UEPR</h1>
                            <p style="margin: 10px 0 0 0; color: #ffffff; font-size: 14px; opacity: 0.9;">Sistema Automático de Dúvidas - Universidade Estadual do Paraná</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 30px 40px 20px 40px; border-bottom: 3px solid #667eea;">
                            <h2 style="margin: 0; color: #2c3e50; font-size: 20px; font-weight: 600;">Nova Mensagem de Contato</h2>
                            <p style="margin: 8px 0 0 0; color: #7f8c8d; font-size: 13px;">Recebida em {timestamp}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 30px 40px;">
                            <table cellpadding="0" cellspacing="0" border="0" width="100%">
                                <tr>
                                    <td style="padding-bottom: 20px;">
                                        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #f8f9fa; border-radius: 6px; padding: 20px;">
                                            <tr>
                                                <td width="120" style="vertical-align: top;">
                                                    <strong style="color: #495057; font-size: 14px;">Nome:</strong>
                                                </td>
                                                <td style="vertical-align: top;">
                                                    <span style="color: #212529; font-size: 14px;">{name_escaped}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td colspan="2" style="height: 15px;"></td>
                                            </tr>
                                            <tr>
                                                <td width="120" style="vertical-align: top;">
                                                    <strong style="color: #495057; font-size: 14px;">Email:</strong>
                                                </td>
                                                <td style="vertical-align: top;">
                                                    <a href="mailto:{email_escaped}" style="color: #667eea; text-decoration: none; font-size: 14px;">{email_escaped}</a>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 0 40px 30px 40px;">
                            <div style="background-color: #ffffff; border-left: 4px solid #667eea; padding: 20px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                                <strong style="color: #495057; font-size: 14px; display: block; margin-bottom: 12px;">Mensagem:</strong>
                                <div style="color: #212529; font-size: 14px; line-height: 1.6;">{message_escaped}</div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 0 40px 30px 40px; text-align: center;">
                            <a href="mailto:{email_escaped}?subject=Re: Contato SAD-UEPR" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-size: 14px; font-weight: 600; box-shadow: 0 4px 6px rgba(102, 126, 234, 0.3);">Responder Email</a>
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color: #f8f9fa; padding: 20px 40px; text-align: center; border-top: 1px solid #e9ecef;">
                            <p style="margin: 0 0 8px 0; color: #6c757d; font-size: 12px;">Este email foi enviado automaticamente pelo sistema SAD-UEPR</p>
                            <p style="margin: 0; color: #6c757d; font-size: 12px;">Para responder, clique no botão acima ou responda diretamente este email</p>
                            <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #dee2e6;">
                                <p style="margin: 0; color: #adb5bd; font-size: 11px;">&copy; {datetime.now().year} Universidade Estadual do Paraná - Todos os direitos reservados</p>
                            </div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
    
    def send_contact_email(self, name: str, email: str, message: str) -> tuple[bool, str]:
        """
        Envia um email de contato para o endereço configurado.
        
        Args:
            name: Nome da pessoa que está entrando em contato
            email: Email da pessoa (será usado no Reply-To)
            message: Mensagem enviada
            
        Returns:
            tuple[bool, str]: (sucesso, mensagem_erro_ou_sucesso)
        """
        try:
            # Validações de entrada
            if not name or not name.strip():
                return False, "Nome é obrigatório"
            
            if len(name) > 100:
                return False, "Nome muito longo (máximo 100 caracteres)"
            
            if not email or not email.strip():
                return False, "Email é obrigatório"
            
            if not self._validate_email_format(email):
                return False, "Formato de email inválido"
            
            if not message or not message.strip():
                return False, "Mensagem é obrigatória"
            
            if len(message) > 5000:
                return False, "Mensagem muito longa (máximo 5000 caracteres)"
            
            # Validar se as credenciais estão configuradas
            if not self.sender_password:
                logger.error("SMTP_PASSWORD não configurado!")
                return False, "Configuração de email não disponível. Contate o administrador."
            
            # Sanitizar entradas
            name_clean = self._sanitize_input(name, 100)
            email_clean = self._sanitize_input(email, 100)
            message_clean = self._sanitize_input(message, 5000)
            
            # Criar mensagem multipart
            msg = MIMEMultipart('alternative')
            msg['From'] = f"SAD-UEPR <{self.sender_email}>"
            msg['To'] = self.receiver_email
            msg['Reply-To'] = email_clean
            msg['Subject'] = f"[SAD-UEPR] Contato de {name_clean}"
            
            # Versão texto plano (fallback)
            text_body = f"""NOVA MENSAGEM DE CONTATO - SAD-UEPR
=====================================

Informações do Remetente:
Nome:  {name_clean}
Email: {email_clean}

Mensagem:
{message_clean}

-------------------------------------
Para responder, use o botão "Responder" - o destinatário será automaticamente {email_clean}

Sistema Automático de Dúvidas - UEPR
"""
            
            # Versão HTML
            html_body = self._get_email_template(name_clean, email_clean, message_clean)
            
            # IMPORTANTE: Anexar texto plano PRIMEIRO, depois HTML
            # O cliente de email vai preferir renderizar o último formato anexado
            part_text = MIMEText(text_body, 'plain', 'utf-8')
            part_html = MIMEText(html_body, 'html', 'utf-8')
            
            msg.attach(part_text)
            msg.attach(part_html)
            
            # Conectar ao servidor SMTP
            logger.info(f"Conectando ao SMTP {self.smtp_server}:{self.smtp_port}...")
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                # Remover debug level em produção
                # server.set_debuglevel(1)
                
                logger.info("Iniciando STARTTLS...")
                server.starttls()
                
                logger.info("Autenticando...")
                server.login(self.sender_email, self.sender_password)
                
                logger.info("Enviando mensagem...")
                server.send_message(msg)
                
            logger.info(f"Email enviado com sucesso de {name_clean} ({email_clean})")
            return True, "Email enviado com sucesso!"
                
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Erro de autenticação SMTP: {str(e)}")
            return False, "Credenciais de email inválidas. Contate o administrador."
        
        except smtplib.SMTPConnectError as e:
            logger.error(f"Erro ao conectar ao SMTP: {str(e)}")
            return False, "Não foi possível conectar ao servidor de email."
        
        except smtplib.SMTPException as e:
            logger.error(f"Erro SMTP: {str(e)}")
            return False, "Erro ao enviar email. Tente novamente mais tarde."
            
        except Exception as e:
            logger.error(f"Erro inesperado: {str(e)}")
            logger.exception("Traceback completo:")
            return False, "Erro inesperado. Tente novamente mais tarde."

# Instância singleton
email_service = EmailService()