import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import logging

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        """Inicializa o serviço de email com as configurações do servidor SMTP."""
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.sender_email = os.getenv("SENDER_EMAIL", "seu-email@gmail.com")
        self.sender_password = os.getenv("SENDER_PASSWORD", "")
        self.receiver_email = os.getenv("RECEIVER_EMAIL", "")  # Email fixo para receber dúvidas
    
    def send_contact_email(self, name, email, message):
      """
      Envia um email de contato para o endereço configurado.
      """
      try:
          # Criar mensagem
          msg = MIMEMultipart()
          msg['From'] = self.sender_email
          msg['To'] = self.receiver_email
          msg['Reply-To'] = email  # Configura o Reply-To como o email da pessoa
          msg['Subject'] = f"Contato SAD-UEPR - {name} ({email})"
          
          # Corpo do email
          body = f"""
          Nova mensagem de contato do SAD-UEPR:
          
          Nome: {name}
          Email: {email}
          
          Mensagem:
          {message}
          """
          
          msg.attach(MIMEText(body, 'plain'))
          
          # Conectar ao servidor SMTP
          with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
              server.starttls()
              server.login(self.sender_email, self.sender_password)
              server.send_message(msg)
          
          logger.info(f"Email enviado com sucesso para {self.receiver_email}")
          return True
          
      except Exception as e:
          logger.error(f"Erro ao enviar email: {str(e)}")
          return False

# Instância para uso direto
email_service = EmailService()