from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import ipca as ipca_router
from app.core.config import settings
from pyngrok import ngrok
import uvicorn

# Inicializar a aplicação FastAPI
app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rotas
app.include_router(ipca_router.router)

def configure_ngrok():
    """Configura e inicia o túnel ngrok"""
    if settings.NGROK_AUTH_TOKEN:
        ngrok.set_auth_token(settings.NGROK_AUTH_TOKEN)
        try:
            # Encerra túneis existentes
            ngrok.kill()
            # Cria novo túnel
            public_url = ngrok.connect(settings.APP_PORT)
            print(f"Ngrok Tunnel URL: {public_url}")
            return public_url
        except Exception as e:
            print(f"Erro ao iniciar ngrok: {e}")
            return None
    else:
        print("AVISO: Token do Ngrok não configurado.")
        return None

if __name__ == "__main__":
    # Configurar ngrok em ambiente de desenvolvimento
    if settings.ENVIRONMENT == "development":
        configure_ngrok()
    
    # Iniciar servidor
    uvicorn.run(
        "app.main:app", 
        host=settings.APP_HOST, 
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )