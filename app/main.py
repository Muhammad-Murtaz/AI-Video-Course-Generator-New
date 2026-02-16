from contextlib import asynccontextmanager
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.schemas.user import UserCreate, UserCreateClerk
from app.schemas.course import (
    CourseCreate,
    CourseIntroRequest,
    GenerateVideoContentRequest,
)
from app.db.database import get_db, SessionLocal
from sqlalchemy.orm import Session
from app.services.user_service import UserService
from app.services.course_service import course_service
from app.services.cache import get_cache_manager
from app.services.rate_limiter import RateLimitDep, RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = get_cache_manager(
        redis_host=settings.REDIS_HOST,
        redis_port=settings.REDIS_PORT,
        redis_password=settings.REDIS_PASSWORD or None,
        l1_max_size=256,
        enable_semantic=True,
    )
    app.state.cache = cache

    try:
        from app.task.celery_tasks import warm_cache_task

        warm_cache_task.apply_async(countdown=10, queue="maintenance")
    except Exception:
        pass

    yield


app = FastAPI(
    title="AI Video Course Generator API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

api_router = APIRouter(prefix="/api")


async def get_user_email(x_user_email: Optional[str] = Header(None)) -> str:
    if not x_user_email:
        raise HTTPException(
            status_code=401, detail="Unauthorized: No user email provided"
        )
    return x_user_email


@app.get("/")
async def root():
    return {
        "message": "AI Video Course Generator API",
        "status": "running",
        "version": "2.0.0",
    }


@app.get("/health")
async def health_check():
    cache = getattr(app.state, "cache", None)
    return {
        "status": "healthy",
        "cache": cache.health() if cache else {"status": "not_initialised"},
    }


# ── Auth ──────────────────────────────────────────────────────────────────────


@api_router.post("/signup", dependencies=[Depends(RateLimitDep("auth"))])
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    user = UserService.create_user(db=db, user_data=user_data)
    return {"message": "User created successfully", "user_id": user.id}


@api_router.post("/signup-clerk", dependencies=[Depends(RateLimitDep("auth"))])
def signup_clerk(user_data: UserCreateClerk, db: Session = Depends(get_db)):
    user = UserService.create_clerk_user(db=db, user_data=user_data)
    return {"message": "User created successfully", "data": user}


# ── Course Layout ──────────────────────────────────────────────────────────────


@api_router.post(
    "/generate-course-layout", dependencies=[Depends(RateLimitDep("course_gen"))]
)
async def generate_course_layout(
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_user_email),
):
    try:
        course = course_service.create_course(db, course_data, user_email)

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
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail={"message": f"Internal error: {exc}"}
        )


# ── Course Read ────────────────────────────────────────────────────────────────
@api_router.get("/courses/{course_id}", dependencies=[Depends(RateLimitDep("read"))])
async def get_course(course_id: str, db: Session = Depends(get_db)):
    cache = getattr(app.state, "cache", None)

    if cache:
        # Use get_by_key — skips semantic L3, does exact L1/L2 only
        cache_key = cache._make_key(f"course:{course_id}")
        cached = cache.get_by_key(cache_key)
        if cached:
            return {"course": cached["response"], "cached": True}

    course_dict = course_service.get_course_by_id(db, course_id)
    if not course_dict:
        raise HTTPException(status_code=404, detail={"message": "Course not found"})

    if cache:
        cache.set(
            f"course:{course_id}",
            course_dict,
            ttl=3600,
            metadata={"course_id": course_id},
        )

    return {"course": course_dict, "cached": False}


@api_router.get("/courses", dependencies=[Depends(RateLimitDep("read"))])
async def get_all_courses(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_user_email),
):
    cache = getattr(app.state, "cache", None)

    if cache:
        cache_key = cache._make_key(f"courses:{user_email}")
        cached = cache.get_by_key(cache_key)
        if cached:
            return {"courses": cached["response"], "cached": True}

    courses = course_service.get_user_courses(db, user_email=user_email)

    if cache and courses:
        cache.set(
            f"courses:{user_email}",
            courses,
            ttl=300,
            metadata={"user_email": user_email},
        )

    return {"courses": courses, "cached": False}


# ── Course Intro ───────────────────────────────────────────────────────────────


@api_router.post(
    "/generate-course-intro", dependencies=[Depends(RateLimitDep("course_gen"))]
)
async def generate_course_intro(
    request: CourseIntroRequest,
    db: Session = Depends(get_db),
):
    try:
        result = course_service.generate_course_introduction(
            db=db, course_id=request.courseId, course_layout=request.courseLayout
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Video Content ──────────────────────────────────────────────────────────────


@api_router.post(
    "/generate-video-content", dependencies=[Depends(RateLimitDep("video_gen"))]
)
async def generate_video_content(
    video_request: GenerateVideoContentRequest,
    db: Session = Depends(get_db),
):
    try:
        return course_service.generate_video_content(
            db, chapter=video_request.chapter, course_id=video_request.course_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail={"message": f"Internal error: {exc}"}
        )


# ── Async Variants (Celery) ────────────────────────────────────────────────────


@api_router.post(
    "/generate-video-content-async", dependencies=[Depends(RateLimitDep("video_gen"))]
)
async def generate_video_content_async(video_request: GenerateVideoContentRequest):
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


@api_router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    from app.task.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)
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
        "result": result.result if result.ready() and not result.failed() else None,
        "error": str(result.result) if result.failed() else None,
    }


app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=4, log_level="info")
