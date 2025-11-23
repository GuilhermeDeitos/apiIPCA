import logging
from app.utils.html_content import html_content
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes import ipca as ipca_router
from app.routes import transparencia as transparencia_router
from app.routes import email as email_router
from app.core.config import settings
from app.middleware.rate_limit import rate_limiter

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
        logging.StreamHandler(),
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

# Middleware de rate limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware que aplica rate limiting em todas as requisições.
    
    Args:
        request: Requisição HTTP
        call_next: Próxima função na cadeia
        
    Returns:
        Response da aplicação ou erro 429
    """
    # Aplicar rate limit apenas em rotas da API (não em arquivos estáticos)
    if request.url.path.startswith("/ipca") or \
       request.url.path.startswith("/transparencia") or \
       request.url.path.startswith("/email"):
        await rate_limiter.check_rate_limit(request)
    
    response = await call_next(request)
    return response

# Incluir rotas
app.include_router(ipca_router.router)
app.include_router(transparencia_router.router)
app.include_router(email_router.router)

@app.get("/", response_class=HTMLResponse, status_code=200)
async def root():
    """Página inicial da API."""
    return html_content

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )