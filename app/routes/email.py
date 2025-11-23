from fastapi import APIRouter, HTTPException, Body, status, Request
from pydantic import BaseModel, EmailStr, Field, validator
from ..services.email_service import email_service
import re
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])

class ContactRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Nome do remetente")
    email: EmailStr = Field(..., description="Email do remetente")
    message: str = Field(..., min_length=10, max_length=5000, description="Mensagem")
    
    @validator('name')
    def validate_name(cls, v):
        """Valida nome"""
        logger.info(f"Validando nome: {v}")
        
        if not v or not v.strip():
            raise ValueError('Nome não pode estar vazio')
        
        # Remover espaços extras
        v = ' '.join(v.split())
        
        # Permitir apenas letras, espaços, hífens e apóstrofos
        if not re.match(r"^[a-zA-ZÀ-ÿ\s'-]+$", v):
            logger.error(f"Nome com caracteres inválidos: {v}")
            raise ValueError('Nome contém caracteres inválidos')
        
        if len(v) < 2:
            raise ValueError('Nome muito curto (mínimo 2 caracteres)')
        
        if len(v) > 100:
            raise ValueError('Nome muito longo (máximo 100 caracteres)')
        
        logger.info(f"Nome validado com sucesso: {v}")
        return v
    
    @validator('message')
    def validate_message(cls, v):
        """Valida mensagem"""
        logger.info(f"Validando mensagem (tamanho: {len(v) if v else 0})")
        
        if not v or not v.strip():
            raise ValueError('Mensagem não pode estar vazia')
        
        # Remover espaços extras
        v = '\n'.join(line.strip() for line in v.split('\n'))
        v = re.sub(r'\n{3,}', '\n\n', v)  # Máximo 2 quebras de linha seguidas
        
        if len(v) < 10:
            raise ValueError('Mensagem muito curta (mínimo 10 caracteres)')
        
        if len(v) > 5000:
            raise ValueError('Mensagem muito longa (máximo 5000 caracteres)')
        
        # Verificar se não é spam (muitos links)
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', v)
        if len(urls) > 3:
            logger.error(f"Mensagem com muitos links ({len(urls)})")
            raise ValueError('Mensagem contém muitos links. Máximo de 3 links permitidos.')
        
        logger.info(f"Mensagem validada com sucesso (tamanho final: {len(v)})")
        return v

@router.post(
    "/contact",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Email enviado com sucesso"},
        400: {"description": "Dados inválidos"},
        422: {"description": "Erro de validação"},
        500: {"description": "Erro no servidor de email"},
        503: {"description": "Serviço de email temporariamente indisponível"}
    }
)
async def send_contact_email(request: Request, contact: ContactRequest = Body(...)):
    """
    Envia um email de contato para o endereço configurado.
    
    Validações aplicadas:
    - Nome: 2-100 caracteres, apenas letras e espaços
    - Email: formato válido
    - Mensagem: 10-5000 caracteres, máximo 3 links
    """
    
    # Log da requisição recebida
    logger.info(f"Requisição de contato recebida de IP: {request.client.host}")
    logger.info(f"Nome: {contact.name}, Email: {contact.email}")
    
    success, message = email_service.send_contact_email(
        name=contact.name,
        email=contact.email,
        message=contact.message
    )
    
    if not success:
        logger.error(f"Falha ao enviar email: {message}")
        # Determinar código de erro apropriado
        if "configuração" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=message
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=message
            )
    
    logger.info("Email enviado com sucesso!")
    return {
        "success": True,
        "message": message
    }

@router.get("/health")
async def email_health():
    """Verifica se o serviço de email está configurado"""
    is_configured = bool(email_service.sender_password)
    
    return {
        "status": "configured" if is_configured else "not_configured",
        "smtp_host": email_service.smtp_server,
        "smtp_port": email_service.smtp_port,
        "sender_email": email_service.sender_email if is_configured else "not_configured"
    }