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
    task_id = self.request.id
    try:
        self.update_state(state="PROGRESS", meta={"step": "starting", "progress": 0})

        from app.db.database import SessionLocal
        from app.services.course_service import course_service

        db = SessionLocal()
        try:
            self.update_state(
                state="PROGRESS", meta={"step": "generating", "progress": 30}
            )
            result = course_service.generate_video_content(
                db, chapter=chapter, course_id=course_id
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
        raise self.retry(exc=exc, countdown=2**self.request.retries * 5)


@celery_app.task(
    base=BaseTask,
    name="app.task.celery_tasks.warm_cache_task",
    queue="maintenance",
    max_retries=1,
    ignore_result=True,
)
def warm_cache_task() -> None:
    try:
        from app.db.database import SessionLocal
        from app.services.course_service import course_service
        from app.services.cache import get_cache_manager

        cache = get_cache_manager()
        db = SessionLocal()
        try:
            courses = (
                db.query(__import__("app.db.model", fromlist=["Course"]).Course)
                .limit(50)
                .all()
            )
            for course in courses:
                cache.set(
                    query=f"course:{course.course_id}",
                    response={
                        "courseId": course.course_id,
                        "courseName": course.course_name,
                    },
                    ttl=86400,
                    metadata={"warmed": True},
                )
        finally:
            db.close()
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
