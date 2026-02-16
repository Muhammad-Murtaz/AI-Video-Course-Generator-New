"""
rate_limiter.py
Redis sliding-window rate limiter with graceful degradation.
If Redis is unavailable, requests are ALLOWED (fail-open) rather than crashing.
"""

from __future__ import annotations

import time
import os
from typing import Optional, Callable

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.config import settings

# ── Redis pool ────────────────────────────────────────────────────────────────
_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    """Returns Redis client, or None if unavailable."""
    global _redis_pool
    if _redis_pool is None:
        try:
            _redis_pool = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
                socket_connect_timeout=1,  # fast fail
                socket_timeout=1,
            )
        except Exception:
            return None
    return _redis_pool


# ── Sliding-window LUA script ─────────────────────────────────────────────────
_SLIDING_WINDOW_SCRIPT = """
local key        = KEYS[1]
local window_ms  = tonumber(ARGV[1]) * 1000
local limit      = tonumber(ARGV[2])
local now        = tonumber(ARGV[3])
local window_start = now - window_ms
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, tonumber(ARGV[1]) + 1)
    return {0, limit - count - 1}
else
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local reset_at = window_start
    if #oldest > 0 then reset_at = tonumber(oldest[2]) end
    return {1, reset_at}
end
"""

# ── Limit presets ─────────────────────────────────────────────────────────────
IS_DEV = os.getenv("APP_ENV", "production") == "development"

LIMIT_PRESETS: dict[str, dict] = {
    "general": {"requests": 120 if IS_DEV else 60, "window": 60},
    "course_gen": {"requests": 20 if IS_DEV else 5, "window": 60},
    "video_gen": {"requests": 30 if IS_DEV else 10, "window": 60},
    "auth": {"requests": 20 if IS_DEV else 10, "window": 60},
    "read": {"requests": 500 if IS_DEV else 200, "window": 60},
}


# ── Core check ────────────────────────────────────────────────────────────────
async def _check_rate_limit(
    request: Request,
    preset: str,
    identifier: Optional[str] = None,
) -> None:
    """
    Enforces rate limit. If Redis is down, silently allows the request
    (fail-open) rather than returning a 500 or 422.
    """
    redis = await get_redis()
    if redis is None:
        # Redis unavailable — fail open (don't block legitimate requests)
        return

    cfg = LIMIT_PRESETS.get(preset, LIMIT_PRESETS["general"])
    limit = cfg["requests"]
    window = cfg["window"]

    ident = (
        identifier
        or request.headers.get("x-user-email")
        or request.headers.get("x-forwarded-for")
        or (request.client.host if request.client else None)
        or "anonymous"
    )
    endpoint = request.url.path.replace("/", "_")
    redis_key = f"rl:{preset}:{endpoint}:{ident}"
    now_ms = int(time.time() * 1000)

    try:
        result = await redis.eval(
            _SLIDING_WINDOW_SCRIPT,
            1,
            redis_key,
            window,
            limit,
            now_ms,
        )
    except Exception:
        # Redis eval failed (connection dropped, etc.) — fail open
        return

    blocked = int(result[0])
    extra = int(result[1])

    if blocked:
        reset_at_ms = extra
        retry_after = max(1, int((reset_at_ms + window * 1000 - now_ms) / 1000))
        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Too many requests. Try again in {retry_after}s.",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


# ── Dependency factory ────────────────────────────────────────────────────────
def RateLimitDep(preset: str = "general") -> Callable:
    async def _dep(request: Request) -> None:
        await _check_rate_limit(request, preset)

    return _dep


# ── Global middleware ─────────────────────────────────────────────────────────
class RateLimitMiddleware:
    WHITELIST = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/api/cache/stats"}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path not in self.WHITELIST:
                request = Request(scope, receive)
                try:
                    await _check_rate_limit(request, "general")
                except HTTPException as exc:
                    from starlette.responses import JSONResponse

                    response = JSONResponse(
                        status_code=exc.status_code,
                        content=exc.detail,
                        headers=exc.headers or {},
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)
