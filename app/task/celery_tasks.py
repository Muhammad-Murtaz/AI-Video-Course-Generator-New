"""
celery_tasks.py
─────────────────────────────────────────────────────────────────────────────
All background tasks for the AI Course Generator.
Re-exports `celery_app` so FastAPI can import a single symbol.
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import time
from typing import Dict, Any

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger

from app.task.celery_app import celery_app

logger = get_task_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Base Task class with shared retry / error logic
# ─────────────────────────────────────────────────────────────────────────────


class BaseTask(Task):
    """
    Shared base for all tasks.
    - Structured logging
    - Automatic retry on transient errors
    - Database session lifecycle (if needed)
    """

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "Task %s[%s] failed: %s",
            self.name,
            task_id,
            exc,
            exc_info=einfo,
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "Task %s[%s] retrying due to: %s",
            self.name,
            task_id,
            exc,
        )

    def on_success(self, retval, task_id, args, kwargs):
        logger.info("Task %s[%s] succeeded", self.name, task_id)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Async Chapter Video Generation
# ─────────────────────────────────────────────────────────────────────────────


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.task.celery_tasks.generate_chapter_video_async",
    queue="ai_generation",
    max_retries=3,
    default_retry_delay=10,  # 10 s between retries
    rate_limit="10/m",  # Max 10 tasks/minute on this queue
    acks_late=True,
)
def generate_chapter_video_async(self, chapter: Dict[str, Any], course_id: str) -> Dict:
    """
    Generates video content for a single chapter.
    Retries up to 3 times on transient failures.
    """
    task_id = self.request.id
    logger.info(
        "Generating video | task=%s course=%s chapter=%s",
        task_id,
        course_id,
        chapter.get("chapterName"),
    )

    try:
        # ── Progress update helpers ───────────────────────────────────────
        self.update_state(state="PROGRESS", meta={"step": "starting", "progress": 0})

        # ── Import DB + service lazily to avoid circular imports ──────────
        from app.db.database import SessionLocal
        from app.services.course_service import course_service

        db = SessionLocal()
        try:
            self.update_state(
                state="PROGRESS", meta={"step": "generating", "progress": 30}
            )
            video_content = course_service.generate_video_content(
                db, chapter=chapter, course_id=course_id
            )
            self.update_state(state="PROGRESS", meta={"step": "saving", "progress": 80})
        finally:
            db.close()

        self.update_state(state="PROGRESS", meta={"step": "done", "progress": 100})
        logger.info("Video generated | task=%s course=%s", task_id, course_id)
        return {
            "status": "success",
            "courseId": course_id,
            "videoContent": video_content,
        }

    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded | task=%s", task_id)
        raise

    except Exception as exc:
        logger.error("Video generation failed | task=%s error=%s", task_id, exc)
        raise self.retry(exc=exc, countdown=2**self.request.retries * 5)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Async Course Intro Generation
# ─────────────────────────────────────────────────────────────────────────────


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
    """Generates course intro/overview content asynchronously."""
    task_id = self.request.id
    logger.info("Generating course intro | task=%s course=%s", task_id, course_id)

    try:
        self.update_state(state="PROGRESS", meta={"step": "starting", "progress": 0})

        from app.db.database import SessionLocal
        from app.services.course_service import course_service

        db = SessionLocal()
        try:
            self.update_state(
                state="PROGRESS", meta={"step": "generating", "progress": 40}
            )
            result = course_service.generate_course_introduction(
                db=db, course_id=course_id, course_layout=course_layout
            )
        finally:
            db.close()

        return {"status": "success", "courseId": course_id, "result": result}

    except SoftTimeLimitExceeded:
        raise

    except Exception as exc:
        logger.error("Course intro generation failed | task=%s error=%s", task_id, exc)
        raise self.retry(exc=exc, countdown=2**self.request.retries * 5)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Video Processing Pipeline (post-generation)
# ─────────────────────────────────────────────────────────────────────────────


@celery_app.task(
    base=BaseTask,
    bind=True,
    name="app.task.celery_tasks.process_video_content",
    queue="video_proc",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def process_video_content(
    self, course_id: str, chapter_id: str, raw_content: Dict
) -> Dict:
    """
    Post-processing pipeline:
    • Validate generated content
    • Store to persistent layer
    • Invalidate related cache
    """
    task_id = self.request.id
    logger.info(
        "Processing video | task=%s course=%s chapter=%s",
        task_id,
        course_id,
        chapter_id,
    )
    try:
        self.update_state(state="PROGRESS", meta={"step": "validating", "progress": 20})
        # ── Validation placeholder ────────────────────────────────────────
        if not raw_content:
            raise ValueError("Empty raw content received")

        self.update_state(state="PROGRESS", meta={"step": "storing", "progress": 60})

        # ── Cache invalidation ────────────────────────────────────────────
        from app.core.cache import cache_manager

        cache_manager.invalidate(pattern=f"course:{course_id}")
        logger.info("Cache invalidated for course %s", course_id)

        self.update_state(state="PROGRESS", meta={"step": "done", "progress": 100})
        return {"status": "success", "courseId": course_id, "chapterId": chapter_id}

    except Exception as exc:
        logger.error("Video processing failed | task=%s error=%s", task_id, exc)
        raise self.retry(exc=exc, countdown=30)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Maintenance — Cache Warm-up
# ─────────────────────────────────────────────────────────────────────────────


@celery_app.task(
    base=BaseTask,
    name="app.task.celery_tasks.warm_cache_task",
    queue="maintenance",
    max_retries=1,
    ignore_result=True,
)
def warm_cache_task() -> None:
    """
    Pre-populates cache with most-accessed course data.
    Runs daily via Celery Beat.
    """
    logger.info("Starting cache warm-up")
    try:
        from app.db.database import SessionLocal
        from app.services.course_service import course_service
        from app.core.cache import cache_manager

        db = SessionLocal()
        try:
            popular_courses = course_service.get_popular_courses(db, limit=50)
            warmed = 0
            for course in popular_courses:
                key = f"course:{course.course_id}"
                cache_manager.set(
                    query=key,
                    response=course.__dict__,
                    ttl=86400,
                    metadata={"warmed": True, "source": "beat"},
                )
                warmed += 1
        finally:
            db.close()

        logger.info("Cache warm-up completed | %d courses cached", warmed)

    except Exception as exc:
        logger.error("Cache warm-up failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Maintenance — Cleanup expired Celery results
# ─────────────────────────────────────────────────────────────────────────────


@celery_app.task(
    base=BaseTask,
    name="app.task.celery_tasks.cleanup_expired_tasks",
    queue="maintenance",
    ignore_result=True,
)
def cleanup_expired_tasks() -> None:
    """Purges expired task results from the Redis backend."""
    logger.info("Running Celery result cleanup")
    try:
        celery_app.backend.cleanup()
        logger.info("Celery result cleanup done")
    except Exception as exc:
        logger.error("Cleanup failed: %s", exc)
