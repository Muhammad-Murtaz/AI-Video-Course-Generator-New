"""
main.py  — AI Video Course Generator API  (production)
─────────────────────────────────────────────────────────────────────────────
Changes vs original:
  1. Rate limiter   → Redis sliding-window (replaces in-process pyrate-limiter)
  2. Cache          → AdvancedCacheManager integrated on GET /courses endpoints
  3. Celery         → async task submission + polling endpoint
  4. Load balancer  → AI provider router wired through course_service
  5. Lifespan       → proper startup/shutdown hooks (replaces @app.on_event)
  6. Health check   → extended to include Redis + cache stats
─────────────────────────────────────────────────────────────────────────────
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Schemas ──────────────────────────────────────────────────────────────────
from app.schemas.user import UserCreate, UserCreateClerk
from app.schemas.course import (
    CourseCreate,
    CourseIntroRequest,
    GenerateVideoContentRequest,
)

# ─── DB ───────────────────────────────────────────────────────────────────────
from app.db.database import get_db, SessionLocal
from sqlalchemy.orm import Session

# ─── Services ─────────────────────────────────────────────────────────────────
from app.services.user_service import UserService
from app.services.course_service import course_service

# ─── Infrastructure ───────────────────────────────────────────────────────────
from app.services.cache import get_cache_manager
from app.services.rate_limiter import RateLimitDep, RateLimitMiddleware
from app.services.loader_balancer import get_load_balancer

# ─────────────────────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at startup and once at shutdown.
    Replaces deprecated @app.on_event("startup").
    """
    logger.info("🚀 Starting AI Course Generator API")

    # ── Initialise cache ─────────────────────────────────────────────────────
    cache = get_cache_manager(
        redis_host=settings.REDIS_HOST,
        redis_port=settings.REDIS_PORT,
        redis_password=settings.REDIS_PASSWORD or None,
        l1_max_size=256,
        enable_semantic=True,
    )
    app.state.cache = cache
    logger.info("✅ Cache manager ready | %s", cache.health())

    # ── Initialise AI provider load balancer ─────────────────────────────────
    lb = get_load_balancer()
    app.state.lb = lb
    logger.info("✅ Load balancer ready | %d providers", len(lb._providers))

    # ── Warm cache on startup ────────────────────────────────────────────────
    try:
        from app.task.celery_tasks import warm_cache_task

        warm_cache_task.apply_async(countdown=10, queue="maintenance")
        logger.info("✅ Cache warm-up task enqueued")
    except Exception as exc:
        logger.warning("Cache warm-up skipped (Celery unavailable): %s", exc)

    yield  # ── App runs ──────────────────────────────────────────────────────

    logger.info("🛑 Shutting down API")


# ─────────────────────────────────────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Video Course Generator API",
    description="Generate educational video courses with AI",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Redis rate limiter (60 req/min per IP by default) ─────────────────
app.add_middleware(RateLimitMiddleware)

# ── API Router ────────────────────────────────────────────────────────────────
api_router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / Dependencies
# ─────────────────────────────────────────────────────────────────────────────


async def get_user_email(x_user_email: Optional[str] = Header(None)) -> str:
    if not x_user_email:
        raise HTTPException(
            status_code=401, detail="Unauthorized: No user email provided"
        )
    return x_user_email


# ─────────────────────────────────────────────────────────────────────────────
# Root / Health
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {
        "message": "AI Video Course Generator API",
        "status": "running",
        "version": "2.0.0",
    }


@app.get("/health")
async def health_check():
    """Extended health check including Redis and cache status."""
    cache: Optional[object] = getattr(app.state, "cache", None)
    cache_health = cache.health() if cache else {"status": "not_initialised"}
    return {
        "status": "healthy",
        "cache": cache_health,
        "lb_stats": app.state.lb.get_stats() if hasattr(app.state, "lb") else None,
    }


@app.get("/api/cache/stats")
async def cache_stats():
    """Expose cache hit-rate stats (admin use)."""
    cache = getattr(app.state, "cache", None)
    if not cache:
        raise HTTPException(status_code=503, detail="Cache not initialised")
    return cache.get_stats()


# ─────────────────────────────────────────────────────────────────────────────
# Auth Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@api_router.post("/signup", dependencies=[Depends(RateLimitDep("auth"))])
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    user = UserService.create_user(db=db, user_data=user_data)
    return {"message": "User created successfully", "user_id": user.id}


@api_router.post("/signup-clerk", dependencies=[Depends(RateLimitDep("auth"))])
def signup_clerk(user_data: UserCreateClerk, db: Session = Depends(get_db)):
    user = UserService.create_clerk_user(db=db, user_data=user_data)
    return {"message": "User created successfully", "data": user}


# ─────────────────────────────────────────────────────────────────────────────
# Course Generation  (Sync — retained for compatibility)
# ─────────────────────────────────────────────────────────────────────────────


@api_router.post(
    "/generate-course-layout",
    dependencies=[Depends(RateLimitDep("course_gen"))],
)
async def generate_course_layout(
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_user_email),
):
    logger.info("📵 /generate-course-layout | user=%s", user_email)
    try:
        course = course_service.create_course(db, course_data, user_email)
        logger.info("✅ Course created: %s", course.course_id)

        cache = getattr(app.state, "cache", None)
        if cache:
            cache.invalidate(pattern=f"courses:{user_email}")

        return {
            "courseId": course.course_id,
            "courseName": course.course_name,
            "courseLayout": course.course_layout,
        }
    except ValueError as exc:
        if str(exc) == "max-limit":
            raise HTTPException(status_code=403, detail={"message": "max-limit"})
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("❌ generate_course_layout: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500, detail={"message": f"Internal error: {exc}"}
        )


# ─────────────────────────────────────────────────────────────────────────────
# Course Read Endpoints  (with semantic caching)
# ─────────────────────────────────────────────────────────────────────────────
@api_router.get(
    "/courses/{course_id}",
    dependencies=[Depends(RateLimitDep("read"))],
)
async def get_course(course_id: str, db: Session = Depends(get_db)):
    cache = getattr(app.state, "cache", None)
    cache_query = f"course:{course_id}"

    # ── Cache hit ────────────────────────────────────────────────────────────
    if cache:
        cached = cache.get(cache_query)
        if cached:
            logger.info("Cache %s for course %s", cached["cache_level"], course_id)
            return {
                "course": cached["response"],
                "cached": True,
                "cache_level": cached["cache_level"],
            }

    # ── DB fetch ─────────────────────────────────────────────────────────────
    try:
        course_dict = course_service.get_course_by_id(db, course_id)
        if not course_dict:
            raise HTTPException(status_code=404, detail={"message": "Course not found"})

        # ── Cache miss → store ───────────────────────────────────────────────
        if cache:
            cache.set(
                cache_query, course_dict, ttl=3600, metadata={"course_id": course_id}
            )

        return {"course": course_dict, "cached": False}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("❌ get_course: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500, detail={"message": f"Internal error: {exc}"}
        )


@api_router.get(
    "/courses",
    dependencies=[Depends(RateLimitDep("read"))],
)
async def get_all_courses(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_user_email),
):
    cache = getattr(app.state, "cache", None)
    cache_query = f"courses:{user_email}"

    if cache:
        cached = cache.get(cache_query)
        if cached:
            return {"courses": cached["response"], "cached": True}

    try:
        courses = course_service.get_user_courses(db, user_email=user_email)
        if cache and courses:
            # Shorter TTL — user list changes frequently
            cache.set(
                cache_query, courses, ttl=300, metadata={"user_email": user_email}
            )
        return {"courses": courses, "cached": False}
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail={"message": f"Internal error: {exc}"}
        )


# ─────────────────────────────────────────────────────────────────────────────
# Course Intro Generation
# ─────────────────────────────────────────────────────────────────────────────


@api_router.post(
    "/generate-course-intro",
    dependencies=[Depends(RateLimitDep("course_gen"))],
)
async def generate_course_intro(
    request: CourseIntroRequest,
    db: Session = Depends(get_db),
):
    """Sync course intro generation (use -async variant for large courses)."""
    try:
        result = course_service.generate_course_introduction(
            db=db, course_id=request.courseId, course_layout=request.courseLayout
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@api_router.post(
    "/generate-course-intro-async",
    dependencies=[Depends(RateLimitDep("course_gen"))],
)
async def generate_course_intro_async_endpoint(
    request: CourseIntroRequest,
):
    """Enqueue course intro generation as a Celery task."""
    from app.task.celery_tasks import generate_course_intro_async

    try:
        task = generate_course_intro_async.delay(request.courseId, request.courseLayout)
        return {"taskId": task.id, "status": "queued"}
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail={"message": f"Failed to submit: {exc}"}
        )


# ─────────────────────────────────────────────────────────────────────────────
# Video Content Generation
# ─────────────────────────────────────────────────────────────────────────────


@api_router.post(
    "/generate-video-content",
    dependencies=[Depends(RateLimitDep("video_gen"))],
)
async def generate_video_content(
    video_request: GenerateVideoContentRequest,
    db: Session = Depends(get_db),
):
    """Sync video generation (short chapters only)."""
    try:
        return course_service.generate_video_content(
            db, chapter=video_request.chapter, course_id=video_request.course_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail={"message": f"Internal error: {exc}"}
        )


@api_router.post(
    "/generate-video-content-async",
    dependencies=[Depends(RateLimitDep("video_gen"))],
)
async def generate_video_content_async(
    video_request: GenerateVideoContentRequest,
):
    """
    Enqueue video generation as a Celery background task.
    Poll /api/tasks/{taskId} for status.
    """
    from app.task.celery_tasks import generate_chapter_video_async

    try:
        task = generate_chapter_video_async.delay(
            video_request.chapter, video_request.course_id
        )
        return {
            "taskId": task.id,
            "status": "queued",
            "pollUrl": f"/api/tasks/{task.id}",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail={"message": f"Failed to submit: {exc}"}
        )


# ─────────────────────────────────────────────────────────────────────────────
# Task Status Polling
# ─────────────────────────────────────────────────────────────────────────────


@api_router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Poll Celery task status. Frontend should poll every 2–3 seconds."""
    from app.task.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)

    # Normalise state for frontend
    state_map = {
        "PENDING": "queued",
        "STARTED": "processing",
        "PROGRESS": "processing",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "REVOKED": "cancelled",
    }

    return {
        "taskId": task_id,
        "status": state_map.get(result.state, result.state.lower()),
        "progress": (
            result.info.get("progress") if isinstance(result.info, dict) else None
        ),
        "step": result.info.get("step") if isinstance(result.info, dict) else None,
        "result": result.result if result.ready() and not result.failed() else None,
        "error": str(result.result) if result.failed() else None,
    }


# ─── Include router ───────────────────────────────────────────────────────────
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,  # Match CPU cores; use Gunicorn in prod
        loop="uvloop",
        http="httptools",
        log_level="info",
    )
