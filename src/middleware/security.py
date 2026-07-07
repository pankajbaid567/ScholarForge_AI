"""
Security middleware for ScholarForge_AI.

Provides:
  - Redis-backed rate limiting (fixed window)
  - API key verification (optional — only enforced if SCHOLARFORGE_API_KEY is set)
"""
import logging

import redis
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import get_settings

logger = logging.getLogger("scholarforge.middleware.security")
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Fixed-window rate limiter backed by Redis.
    Fails open (allows requests) if Redis is unavailable.
    """

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        try:
            self.redis_client = redis.from_url(settings.REDIS_URL)
            # Test connection
            self.redis_client.ping()
            logger.info(
                "Rate limiter initialized: %d requests per %ds window",
                max_requests,
                window_seconds,
            )
        except Exception as e:
            logger.warning("Redis not available for rate limiting: %s", e)
            self.redis_client = None

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and status polling endpoints
        if request.url.path == "/health" or "status" in request.url.path:
            return await call_next(request)

        if not self.redis_client:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_ip}"

        try:
            current = self.redis_client.get(key)
            if current and int(current) > self.max_requests:
                logger.warning("Rate limit exceeded for IP %s", client_ip)
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later.",
                )

            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.window_seconds)
            pipe.execute()
        except HTTPException:
            raise  # Re-raise the 429
        except redis.RedisError as e:
            logger.warning("Redis error in rate limiter (failing open): %s", e)
        except Exception as e:
            logger.warning("Unexpected error in rate limiter (failing open): %s", e)

        response = await call_next(request)
        return response


async def verify_api_key(request: Request):
    """
    Optional API key verification.
    Only enforced if SCHOLARFORGE_API_KEY is set to a non-default value.
    """
    expected_key = settings.SCHOLARFORGE_API_KEY

    # Skip verification if no key is configured or if using the placeholder
    if not expected_key or expected_key == "your_scholarforge_api_key_here":
        return

    api_key = request.headers.get("X-API-Key")
    if api_key != expected_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API key. Provide X-API-Key header.",
        )
