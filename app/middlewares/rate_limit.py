from fastapi import Request, HTTPException
from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict


class RateLimiter:
    """
    Middleware de rate limiting sem dependências externas.
    Usa memória para rastrear requisições por IP.
    """
    
    def __init__(self, requests_per_minute: int = 60):
        """
        Inicializa o rate limiter.
        
        Args:
            requests_per_minute: Número máximo de requisições por minuto
        """
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
        self._cleanup_interval = 60  # Limpar cache a cada 60 segundos
        self._cleanup_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    def _ensure_cleanup_task(self):
        """
        Garante que a tarefa de limpeza está rodando.
        Só inicia quando há um event loop ativo (lazy initialization).
        """
        if self._initialized:
            return
        
        try:
            # Tentar obter o event loop atual
            loop = asyncio.get_running_loop()
            
            # Se conseguiu, criar a tarefa
            if not self._cleanup_task or self._cleanup_task.done():
                self._cleanup_task = loop.create_task(self._cleanup_old_requests())
                self._initialized = True
        except RuntimeError:
            # Não há event loop rodando ainda (ex: durante importação em testes)
            # A tarefa será criada na primeira requisição
            pass
    
    async def _cleanup_old_requests(self):
        """Remove requisições antigas do cache periodicamente."""
        try:
            while True:
                await asyncio.sleep(self._cleanup_interval)
                current_time = datetime.now()
                
                # Remover IPs com requisições antigas
                for ip in list(self.requests.keys()):
                    self.requests[ip] = [
                        timestamp for timestamp in self.requests[ip]
                        if current_time - timestamp < timedelta(minutes=1)
                    ]
                    
                    # Remover IP se não tem requisições recentes
                    if not self.requests[ip]:
                        del self.requests[ip]
        except asyncio.CancelledError:
            # Tarefa foi cancelada, limpar e sair
            pass
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Obtém o IP real do cliente, considerando proxies.
        
        Args:
            request: Objeto Request do FastAPI
            
        Returns:
            Endereço IP do cliente
        """
        # Verificar headers de proxy
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback para IP direto
        return request.client.host if request.client else "unknown"
    
    async def check_rate_limit(self, request: Request) -> None:
        """
        Verifica se o cliente excedeu o limite de requisições.
        
        Args:
            request: Objeto Request do FastAPI
            
        Raises:
            HTTPException: Se limite excedido
        """
        # Garantir que a tarefa de limpeza está rodando
        self._ensure_cleanup_task()
        
        client_ip = self._get_client_ip(request)
        current_time = datetime.now()
        
        # Obter requisições do último minuto
        recent_requests = [
            timestamp for timestamp in self.requests[client_ip]
            if current_time - timestamp < timedelta(minutes=1)
        ]
        
        # Verificar limite
        if len(recent_requests) >= self.requests_per_minute:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Máximo de {self.requests_per_minute} requisições por minuto",
                    "retry_after": "60 segundos"
                },
                headers={"Retry-After": "60"}
            )
        
        # Adicionar requisição atual
        self.requests[client_ip].append(current_time)
    
    def reset(self):
        """
        Reseta o rate limiter (útil para testes).
        """
        self.requests.clear()
        self._initialized = False
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            self._cleanup_task = None


# Instância global do rate limiter
rate_limiter = RateLimiter(requests_per_minute=60)