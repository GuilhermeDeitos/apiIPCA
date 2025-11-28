from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

class Settings(BaseSettings):
    # Informações da aplicação
    APP_TITLE: str = "API IPCA"
    APP_DESCRIPTION: str = "Consulta e correção de valores com base no IPCA."
    APP_VERSION: str = "1.0.0"
    
    # Configurações do servidor
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    
    # Ambiente (development, staging, production)
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "")
    
    # Configuração do Ngrok
    NGROK_AUTH_TOKEN: str = os.getenv("NGROK_AUTH_TOKEN", "")

settings = Settings()