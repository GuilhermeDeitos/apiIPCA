from datetime import datetime
import logging
import os
from app.utils.html_content import html_content
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.routes import ipca as ipca_router
from app.routes import transparencia as transparencia_router
from app.routes import email as email_router
from app.core.config import settings
from app.middlewares.rate_limit import rate_limiter

# Obter root_path de variável de ambiente (padrão vazio para desenvolvimento)
ROOT_PATH = os.getenv("ROOT_PATH", "")

# Inicializar a aplicação FastAPI com root_path para proxy reverso
app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    root_path=ROOT_PATH,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

# Log do root_path configurado
logging.info(f"API configurada com root_path: '{ROOT_PATH}'")
logger = logging.getLogger(__name__)

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

# Handler global para erros de validação
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handler personalizado para erros de validação do Pydantic.
    Loga detalhes e retorna mensagem amigável.
    """
    errors = exc.errors()
    
    # Log detalhado do erro
    logger.error(f"Erro de validação na rota {request.url.path}")
    logger.error(f"Método: {request.method}")
    logger.error(f"Client: {request.client.host if request.client else 'unknown'}")
    
    # Processar erros para garantir serialização JSON
    processed_errors = []
    for error in errors:
        field = " -> ".join(str(loc) for loc in error["loc"])
        logger.error(f"  Campo: {field}")
        logger.error(f"  Tipo: {error['type']}")
        logger.error(f"  Mensagem: {error['msg']}")
        
        # Criar erro processado garantindo que tudo é serializável
        processed_error = {
            "loc": error["loc"],
            "msg": str(error["msg"]),  # Converter para string garantindo serialização
            "type": error["type"]
        }
        
        # Adicionar contexto se existir e for serializável
        if "ctx" in error:
            try:
                logger.error(f"  Contexto: {error['ctx']}")
                processed_error["ctx"] = {
                    k: str(v) for k, v in error["ctx"].items()
                }
            except Exception as e:
                logger.warning(f"Não foi possível processar contexto: {e}")
        
        processed_errors.append(processed_error)
    
    # Tentar logar body da requisição (cuidado com dados sensíveis)
    try:
        body = await request.body()
        body_str = body.decode('utf-8')
        if len(body_str) > 500:
            logger.debug(f"Body recebido (primeiros 500 chars): {body_str[:500]}...")
        else:
            logger.debug(f"Body recebido: {body_str}")
    except Exception as e:
        logger.debug(f"Não foi possível ler o body da requisição: {e}")
    
    # Retornar resposta amigável com erros processados
    return JSONResponse(
        status_code=422,
        content={
            "detail": processed_errors,
            "message": "Dados inválidos. Verifique os campos e tente novamente."
        }
    )


# Incluir rotas
app.include_router(ipca_router.router)
app.include_router(transparencia_router.router)
app.include_router(email_router.router)

@app.get("/", response_class=HTMLResponse, status_code=200)
async def root():
    """Página inicial da API."""
    return html_content

@app.get("/health")
async def health_check():
    """Health check para monitoramento."""
    from app.services.ipca_service import get_ipca_service
    
    try:
        # Obter instância do serviço
        ipca_service = get_ipca_service()
        
        # Verificar status do IPCA
        status_ipca = ipca_service.obter_status_servico()
        
        # API está "healthy" mesmo sem IPCA (funcionalidade limitada)
        health_status = {
            "status": "healthy",
            "service": "API IPCA",
            "version": settings.APP_VERSION,
            "root_path": ROOT_PATH,
            "timestamp": datetime.now().isoformat(),
            "ipca_service": status_ipca
        }
        
        # Se não há dados IPCA, incluir aviso mas não falhar o health check
        if not status_ipca.get("dados_disponiveis"):
            health_status["aviso"] = "Serviço funcionando com capacidade limitada (sem dados IPCA)"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=200,  # Manter 200 para não derrubar o container
            content={
                "status": "degraded",
                "service": "API IPCA",
                "error": str(e),
                "aviso": "Serviço parcialmente funcional"
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )