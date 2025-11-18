from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, EmailStr
from ..services.email_service import email_service

router = APIRouter(prefix="/email", tags=["email"])

class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    message: str

@router.post("/contact")
async def send_contact_email(contact: ContactRequest = Body(...)):
    """Endpoint para enviar um email de contato"""
    
    success = email_service.send_contact_email(
        name=contact.name,
        email=contact.email,
        message=contact.message
    )
    
    if not success:
        raise HTTPException(
            status_code=500, 
            detail="Não foi possível enviar o email. Tente novamente mais tarde."
        )
    
    return {"message": "Email enviado com sucesso!"}