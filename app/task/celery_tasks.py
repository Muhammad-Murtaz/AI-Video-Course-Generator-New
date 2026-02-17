import logging
from typing import Dict, Any

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger

from app.task.celery_app import celery_app

logger = get_task_logger(__name__)


class BaseTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("Task %s[%s] failed: %s", self.name, task_id, exc)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning("Task %s[%s] retrying: %s", self.name, task_id, exc)

    def on_success(self, retval, task_id, args, kwargs):
        logger.info("Task %s[%s] succeeded", self.name, task_id)


# ── Helper: get cache inside a Celery worker process ─────────────────────────


def _get_cache():
    """
    Workers don't have access to app.state, so we grab the singleton
    directly from the cache module. This is the same instance that was
    initialised during FastAPI lifespan (same Redis connection params),
    so invalidations here propagate to L2/L3 immediately.
    """
    try:
        from app.services.cache import get_cache_manager

        return get_cache_manager()
    except Exception as exc:
        logger.warning("Could not acquire cache manager in worker: %s", exc)
        return None


# ── Tasks ─────────────────────────────────────────────────────────────────────


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.task.celery_tasks.generate_chapter_video_async",
    queue="ai_generation",
    max_retries=3,
    default_retry_delay=10,
    rate_limit="10/m",
    acks_late=True,
)
def generate_chapter_video_async(self, chapter: Dict[str, Any], course_id: str) -> Dict:
    try:
        self.update_state(state="PROGRESS", meta={"step": "starting", "progress": 0})

        from app.db.database import SessionLocal
        from app.services.course_service import course_service

        # FIX: acquire the cache singleton so invalidation reaches L1+L2+L3
        cache = _get_cache()

        db = SessionLocal()
        try:
            self.update_state(
                state="PROGRESS", meta={"step": "generating", "progress": 30}
            )
            result = course_service.generate_video_content(
                db,
                chapter=chapter,
                course_id=course_id,
                cache=cache,  # ← was missing; stale cache never cleared
            )
            self.update_state(state="PROGRESS", meta={"step": "done", "progress": 100})
        finally:
            db.close()

        return {"status": "success", "courseId": course_id, "videoContent": result}

    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries * 5)


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.task.celery_tasks.generate_course_intro_async",
    queue="ai_generation",
    max_retries=3,
    default_retry_delay=15,
    rate_limit="5/m",
    acks_late=True,
)
def generate_course_intro_async(self, course_id: str, course_layout: Dict) -> Dict:
    try:
        self.update_state(state="PROGRESS", meta={"step": "starting", "progress": 0})

        from app.db.database import SessionLocal
        from app.services.course_service import course_service

        # FIX: same as above — must pass cache so intro generation busts the
        # stale course snapshot that was cached before slides existed.
        cache = _get_cache()

        db = SessionLocal()
        try:
            self.update_state(
                state="PROGRESS", meta={"step": "generating", "progress": 40}
            )
            result = course_service.generate_course_introduction(
                db=db,
                course_id=course_id,
                course_layout=course_layout,
                cache=cache,  # ← was missing
            )
        finally:
            db.close()

        return {"status": "success", "courseId": course_id, "result": result}

    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries * 5)


@celery_app.task(
    base=BaseTask,
    name="app.task.celery_tasks.warm_cache_task",
    queue="maintenance",
    max_retries=1,
    ignore_result=True,
)
def warm_cache_task() -> None:
    """
    Pre-populate L1/L2 with full course data for the 50 most recent courses.

    FIX: the original version warmed with only {courseId, courseName} — a
    partial payload. Any subsequent GET /courses/{id} cache-hit would return
    that stub instead of the real course object (missing slides, layout, etc.).
    Now we call get_course_by_id() to warm with the identical shape that the
    live route would cache, so cache hits are always safe to serve.
    """
    try:
        from app.db.database import SessionLocal
        from app.services.course_service import course_service
        from app.services.cache import get_cache_manager
        from app.db.model import Course

        cache = get_cache_manager()
        db = SessionLocal()
        warmed = 0
        try:
            courses = db.query(Course).order_by(Course.id.desc()).limit(50).all()
            for course in courses:
                try:
                    # get_course_by_id returns the same dict shape the API
                    # route caches — slides, intro slides, layout, everything.
                    full_course = course_service.get_course_by_id(db, course.course_id)
                    if full_course:
                        cache.set(
                            query=f"course:{course.course_id}",
                            response=full_course,
                            ttl=86400,
                            metadata={"warmed": True, "course_id": course.course_id},
                        )
                        warmed += 1
                except Exception as exc:
                    # One bad course must not abort the whole warm-up run.
                    logger.warning(
                        "Skipping course %s during warm-up: %s",
                        course.course_id,
                        exc,
                    )
        finally:
            db.close()

        logger.info("Cache warm-up complete: %d courses warmed", warmed)

    except Exception as exc:
        logger.error("Cache warm-up failed: %s", exc)


@celery_app.task(
    base=BaseTask,
    name="app.task.celery_tasks.cleanup_expired_tasks",
    queue="maintenance",
    ignore_result=True,
)
def cleanup_expired_tasks() -> None:
    try:
        celery_app.backend.cleanup()
    except Exception as exc:
        logger.error("Cleanup failed: %s", exc)
