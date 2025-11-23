from fastapi import Request, HTTPException
from typing import Dict, Tuple
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
        
        # Iniciar tarefa de limpeza
        asyncio.create_task(self._cleanup_old_requests())
    
    async def _cleanup_old_requests(self):
        """Remove requisições antigas do cache periodicamente."""
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
                }
            )
        
        # Adicionar requisição atual
        self.requests[client_ip].append(current_time)


# Instância global do rate limiter
rate_limiter = RateLimiter(requests_per_minute=60)