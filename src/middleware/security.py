from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import redis
import os
import time

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        
        # Connect to Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.redis_client = redis.from_url(redis_url)
        except Exception as e:
            print(f"Warning: Redis not connected for Rate Limiting: {e}")
            self.redis_client = None

    async def dispatch(self, request: Request, call_next):
        if not self.redis_client:
            return await call_next(request)
            
        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"
        
        try:
            # Simple fixed window rate limiting
            current = self.redis_client.get(key)
            if current and int(current) > self.max_requests:
                raise HTTPException(status_code=429, detail="Too Many Requests")
                
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.window_seconds)
            pipe.execute()
        except redis.RedisError:
            pass # Fail open if Redis drops
            
        response = await call_next(request)
        return response

async def verify_api_key(request: Request):
    api_key = request.headers.get("X-API-Key")
    expected_key = os.getenv("SCHOLARFORGE_API_KEY")
    
    if expected_key and api_key != expected_key:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
