from celery import Celery
from app.core.config import settings
from app.db.database import SessionLocal
from app.services.course_service import course_service

celery_app = Celery(
    "ai_video_course", broker=settings.REDIS_URL, backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="generate_chapter_video_async")
def generate_chapter_video_async(chapter: dict, course_id: str):
    db = SessionLocal()
    try:
        result = course_service.generate_video_content(db, chapter, course_id)
        return result
    finally:
        db.close()


@celery_app.task(name="generate_full_course_async")
def generate_full_course_async(course_id: str):
    db = SessionLocal()
    try:
        course = course_service.get_course_by_id(db, course_id)
        if not course:
            return {"error": "Course not found"}

        chapters = course["courseLayout"]["chapters"]
        results = []

        for chapter in chapters:
            result = course_service.generate_video_content(db, chapter, course_id)
            results.append(result)

        return {"status": "completed", "results": results}
    finally:
        db.close()
