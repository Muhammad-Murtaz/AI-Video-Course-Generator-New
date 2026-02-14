"""
rate_limiter.py
─────────────────────────────────────────────────────────────────────────────
Redis-backed sliding-window rate limiter for FastAPI.

Why replace pyrate-limiter?
  - pyrate-limiter uses in-process state → doesn't scale across workers/pods
  - This implementation uses Redis atomic LUA scripts → consistent across
    all Uvicorn workers, Kubernetes pods, and Celery workers
  - Supports per-user, per-IP, and per-endpoint limits simultaneously
  - Adds Retry-After header so clients back off gracefully

Usage:
    from app.middleware.rate_limiter import RateLimitDep

    @router.post("/generate-course", dependencies=[Depends(RateLimitDep("course_gen"))])
    async def generate():
        ...
─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import time
from typing import Optional, Callable

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.config import settings


# ─── Redis connection pool (shared across all requests) ──────────────────────
_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


# ─── Sliding-window LUA script (atomic, no race conditions) ──────────────────
# KEYS[1] = rate-limit key
# ARGV[1] = window size in seconds
# ARGV[2] = max allowed requests in window
# ARGV[3] = current timestamp (milliseconds)
_SLIDING_WINDOW_SCRIPT = """
local key        = KEYS[1]
local window_ms  = tonumber(ARGV[1]) * 1000
local limit      = tonumber(ARGV[2])
local now        = tonumber(ARGV[3])
local window_start = now - window_ms

-- Remove timestamps outside the current window
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count remaining requests
local count = redis.call('ZCARD', key)

if count < limit then
    -- Add current timestamp and refresh TTL
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, tonumber(ARGV[1]) + 1)
    return {0, limit - count - 1}   -- {allowed=0, remaining}
else
    -- Return oldest timestamp so client knows when window resets
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local reset_at = window_start
    if #oldest > 0 then reset_at = tonumber(oldest[2]) end
    return {1, reset_at}            -- {blocked=1, reset_at_ms}
end
"""


# ─── Named limit presets ─────────────────────────────────────────────────────
LIMIT_PRESETS: dict[str, dict] = {
    "general":     {"requests": 60,  "window": 60},   # 60 req/min
    "course_gen":  {"requests": 5,   "window": 60},   # 5 req/min  (heavy AI)
    "video_gen":   {"requests": 10,  "window": 60},   # 10 req/min
    "auth":        {"requests": 10,  "window": 60},   # 10 req/min (signups)
    "read":        {"requests": 200, "window": 60},   # 200 req/min (GET)
}


# ─── Core rate-limit check ────────────────────────────────────────────────────

async def _check_rate_limit(
    request: Request,
    preset: str,
    identifier: Optional[str] = None,
) -> None:
    """
    Raises HTTP 429 if the rate limit is exceeded.
    Identifier priority: user email header → IP address
    """
    redis = await get_redis()
    cfg = LIMIT_PRESETS.get(preset, LIMIT_PRESETS["general"])
    limit   = cfg["requests"]
    window  = cfg["window"]

    # Build a key that is unique per endpoint + identifier
    ident = (
        identifier
        or request.headers.get("x-user-email")
        or request.headers.get("x-forwarded-for")
        or request.client.host
        or "anonymous"
    )
    endpoint = request.url.path.replace("/", "_")
    redis_key = f"rl:{preset}:{endpoint}:{ident}"

    now_ms = int(time.time() * 1000)

    result = await redis.eval(
        _SLIDING_WINDOW_SCRIPT,
        1,         # numkeys
        redis_key,
        window,
        limit,
        now_ms,
    )

    blocked    = int(result[0])
    extra      = int(result[1])

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


# ─── FastAPI Dependency factories ─────────────────────────────────────────────

def RateLimitDep(preset: str = "general") -> Callable:
    """
    Returns a FastAPI dependency for the given preset.

    Example:
        @router.post("/foo", dependencies=[Depends(RateLimitDep("course_gen"))])
    """
    async def _dep(request: Request) -> None:
        await _check_rate_limit(request, preset)
    return _dep


# ─── Global middleware variant (all routes) ───────────────────────────────────

class RateLimitMiddleware:
    """
    Starlette middleware that applies 'general' rate limiting to every route.
    Certain paths are whitelisted (health checks, docs).

    Add to app:
        app.add_middleware(RateLimitMiddleware)
    """
    WHITELIST = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

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