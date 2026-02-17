from typing import List, Optional
from fastapi import HTTPException, status
from concurrent.futures import ThreadPoolExecutor
from app.schemas.course import CourseCreate
from app.services.langchain_service import langchain_generator
from app.services.caption_service import caption_service
from app.services.audio_service import audio_service
from app.db.model import ChapterContentSlide, CourseIntroSlide, User, Course
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

MAX_FREE_COURSES = 4


class CourseService:

    def create_course(
        self, db: Session, course_data: CourseCreate, user_email: str
    ) -> Course:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="User not found"
            )

        user_courses = db.query(Course).filter(Course.user_id == user_email).count()
        if user_courses >= MAX_FREE_COURSES:
            raise ValueError("max-limit")

        course_layout = langchain_generator.generate_course_layout(
            user_input=course_data.user_input, type=course_data.type
        )
        if isinstance(course_layout, list):
            course_layout = course_layout[0] if course_layout else {}

        course = Course(
            course_id=course_data.course_id,
            course_name=course_layout.get("courseName"),
            user_id=user_email,
            user_input=course_data.user_input,
            type=course_data.type,
            course_layout=course_layout,
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        return course

    def _process_slide(self, slide: dict):
        audio_buffer = audio_service.generate_audio(slide["narration"]["fullText"])
        audio_url = audio_service.save_audio_to_storage(
            audio_buffer, slide["audioFileName"]
        )
        caption = caption_service.generate_captions(audio_url)
        return {"slide": slide, "audio_url": audio_url, "caption": caption}

    def _invalidate_course_cache(self, cache, course_id: str) -> None:
        """
        Bust every cache tier that references this course.

        We must remove:
          • course:{course_id}   — the per-course detail key  (L1 + L2 + L3)
          • Any pattern-matched variants (handles context-keyed entries)
        """
        if cache is None:
            return
        try:
            # 1. Exact key invalidation (covers L1, L2, and L3 semantic map)
            exact_key = cache._make_key(f"course:{course_id}")
            cache.invalidate(key=exact_key)

            # 2. Pattern invalidation catches any variant keys that include
            #    the course_id (e.g. context-aware or versioned keys).
            cache.invalidate(pattern=f"course:{course_id}")

            logger.info("Cache invalidated for course_id=%s", course_id)
        except Exception as exc:
            # Cache errors must never break the main flow.
            logger.warning(
                "Cache invalidation failed for course_id=%s: %s", course_id, exc
            )

    def generate_course_introduction(
        self,
        db: Session,
        course_id: str,
        course_layout: dict,
        cache=None,  # ← injected from the route handler
    ):
        existing = (
            db.query(CourseIntroSlide)
            .filter(CourseIntroSlide.course_id == course_id)
            .first()
        )
        if existing:
            return {"message": "Introduction already exists", "skipped": True}

        intro_content = langchain_generator.generate_course_introduction(course_layout)

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(self._process_slide, intro_content))

        audio_urls, captions = [], []
        for r in results:
            slide = r["slide"]
            audio_urls.append(r["audio_url"])
            captions.append(r["caption"])
            db.add(
                CourseIntroSlide(
                    course_id=course_id,
                    slide_id=slide["slideId"],
                    slide_index=slide["slideIndex"],
                    audio_file_name=slide["audioFileName"],
                    narration=slide["narration"],
                    html=slide["html"],
                    reveal_data=slide["revealData"],
                    audio_file_url=r["audio_url"],
                    caption=r["caption"],
                )
            )

        db.commit()

        # ── CACHE FIX: bust stale course snapshot after writing new slides ──
        self._invalidate_course_cache(cache, course_id)

        return {
            "introContent": intro_content,
            "audioUrls": audio_urls,
            "captions": captions,
        }

    def get_course_by_id(self, db: Session, course_id: str):
        course = db.query(Course).filter(Course.course_id == course_id).first()
        if not course:
            return None

        slides = (
            db.query(ChapterContentSlide)
            .filter(ChapterContentSlide.course_id == course_id)
            .order_by(ChapterContentSlide.slide_index)
            .all()
        )

        intro_slides = (
            db.query(CourseIntroSlide)
            .filter(CourseIntroSlide.course_id == course_id)
            .order_by(CourseIntroSlide.slide_index)
            .all()
        )

        return {
            "id": course.id,
            "courseId": course.course_id,
            "courseName": course.course_name,
            "userId": course.user_id,
            "userInput": course.user_input,
            "type": course.type,
            "courseLayout": course.course_layout,
            "createdAt": course.created_at.isoformat(),
            "courseIntroSlides": [
                {
                    "id": s.id,
                    "courseId": s.course_id,
                    "slideId": s.slide_id,
                    "slideIndex": s.slide_index,
                    "audioFileName": s.audio_file_name,
                    "narration": s.narration,
                    "html": s.html,
                    "revealData": s.reveal_data,
                    "audioFileUrl": s.audio_file_url,
                    "caption": s.caption,
                }
                for s in intro_slides
            ],
            "chapterContentSlide": [
                {
                    "id": s.id,
                    "courseId": s.course_id,
                    "chapterId": s.chapter_id,
                    "slideId": s.slide_id,
                    "slideIndex": s.slide_index,
                    "audioFileName": s.audio_file_name,
                    "narration": s.narration,
                    "html": s.html,
                    "revealData": s.reveal_data,
                    "audioFileUrl": s.audio_file_url,
                    "caption": s.caption,
                }
                for s in slides
            ],
        }

    def get_user_courses(self, db: Session, user_email: str) -> List[Course]:
        return (
            db.query(Course)
            .filter(Course.user_id == user_email)
            .order_by(Course.id.desc())
            .all()
        )

    def generate_video_content(
        self,
        db: Session,
        chapter: dict,
        course_id: str,
        cache=None,  # ← injected from the route handler
    ):
        existing = (
            db.query(ChapterContentSlide)
            .filter(
                ChapterContentSlide.course_id == course_id,
                ChapterContentSlide.chapter_id == chapter["chapterId"],
            )
            .first()
        )
        if existing:
            return {"message": "Content already exists", "skipped": True}

        video_content = langchain_generator.generate_video_content(chapter)
        logger.info(
            "Generated %d slides for chapter %s",
            len(video_content),
            chapter["chapterId"],
        )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._process_slide, slide): slide
                for slide in video_content
            }
            results = []
            for future, slide in futures.items():
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(
                        "Slide processing failed for slideId=%s: %s",
                        slide.get("slideId", "unknown"),
                        e,
                        exc_info=True,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to process slide {slide.get('slideId', 'unknown')}: {str(e)}",
                    )

        audio_urls, captions = [], []
        for r in results:
            slide = r["slide"]
            audio_urls.append(r["audio_url"])
            captions.append(r["caption"])
            db.add(
                ChapterContentSlide(
                    course_id=course_id,
                    chapter_id=chapter["chapterId"],
                    slide_id=slide["slideId"],
                    slide_index=slide["slideIndex"],
                    audio_file_name=slide["audioFileName"],
                    narration=slide["narration"],
                    html=slide["html"],
                    reveal_data=slide["revealData"],
                    audio_file_url=r["audio_url"],
                    caption=r["caption"],
                )
            )

        db.commit()

        # ── CACHE FIX: bust stale course snapshot after writing new slides ──
        self._invalidate_course_cache(cache, course_id)

        return {
            "videoContent": video_content,
            "audioUrls": audio_urls,
            "captions": captions,
        }


course_service = CourseService()
