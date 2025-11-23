import logging
from app.utils.html_content import html_content
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes import ipca as ipca_router
from app.routes import transparencia as transparencia_router
from app.routes import email as email_router
from app.core.config import settings
from pyngrok import ngrok
import uvicorn

# Inicializar a aplicação FastAPI
app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Para console
    ]
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
app.include_router(transparencia_router.router)
app.include_router(email_router.router)
    
@app.get("/", response_class=HTMLResponse, status_code=200)
async def root():
    return html_content
    
if __name__ == "__main__":

    # Iniciar servidor
    uvicorn.run(
        "app.main:app", 
        host=settings.APP_HOST, 
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )