# app/services/course_service.py
from typing import List
from fastapi import HTTPException, status
from app.schemas.course import CourseCreate
from app.services.langchain_service import langchain_generator
from app.services.caption_service import caption_service
from app.services.audio_service import audio_service
from app.db.model import ChapterContentSlide, CourseIntroSlide, User, Course
from sqlalchemy.orm import Session


class CourseService:

    def create_course(
        self, db: Session, course_data: CourseCreate, user_email: str
    ) -> Course:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="User not found"
            )

        user_courses = db.query(Course).filter(Course.user_id == user_email).all()
        if len(user_courses) >= 4:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Course creation limit reached",
            )

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

    def generate_course_introduction(
        self, db: Session, course_id: str, course_layout: dict
    ):
        existing_intro = (
            db.query(CourseIntroSlide)
            .filter(CourseIntroSlide.course_id == course_id)
            .first()
        )

        if existing_intro:
            return {"message": "Introduction already exists", "skipped": True}

        # Generate 5-6 intro slides for ~2-3 minute introduction
        intro_content = langchain_generator.generate_course_introduction(course_layout)

        audio_file_urls = []
        caption_array = []

        for i, slide in enumerate(intro_content):
            narration = slide["narration"]["fullText"]
            audio_buffer = audio_service.generate_audio(narration)
            audio_url = audio_service.save_audio_to_storage(
                audio_buffer=audio_buffer, file_name=slide["audioFileName"]
            )
            audio_file_urls.append(audio_url)

            caption = caption_service.generate_captions(audio_url)
            caption_array.append(caption)

            slide_record = CourseIntroSlide(
                course_id=course_id,
                slide_id=slide["slideId"],
                slide_index=slide["slideIndex"],
                audio_file_name=slide["audioFileName"],
                narration=slide["narration"],
                html=slide["html"],
                reveal_data=slide["revealData"],
                audio_file_url=audio_url,
                caption=caption,
            )

            db.add(slide_record)
            db.commit()

        return {
            "introContent": intro_content,
            "audioUrls": audio_file_urls,
            "captions": caption_array,
        }

    def get_course_by_id(self, db: Session, course_id: str):
        course = db.query(Course).filter(Course.course_id == course_id).first()
        if course:
            slides = (
                db.query(ChapterContentSlide)
                .filter(ChapterContentSlide.course_id == course_id)
                .all()
            )
            intro_slides = (
                db.query(CourseIntroSlide)
                .filter(CourseIntroSlide.course_id == course_id)
                .all()
            )
            course_dict = {
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
                        "id": slide.id,
                        "courseId": slide.course_id,
                        "slideId": slide.slide_id,
                        "slideIndex": slide.slide_index,
                        "audioFileName": slide.audio_file_name,
                        "narration": slide.narration,
                        "html": slide.html,
                        "revealData": slide.reveal_data,
                        "audioFileUrl": slide.audio_file_url,
                        "caption": slide.caption,
                    }
                    for slide in intro_slides
                ],
                "chapterContentSlide": [
                    {
                        "id": slide.id,
                        "courseId": slide.course_id,
                        "chapterId": slide.chapter_id,
                        "slideId": slide.slide_id,
                        "slideIndex": slide.slide_index,
                        "audioFileName": slide.audio_file_name,
                        "narration": slide.narration,
                        "html": slide.html,
                        "revealData": slide.reveal_data,
                        "audioFileUrl": slide.audio_file_url,
                        "caption": slide.caption,
                    }
                    for slide in slides
                ],
            }
            return course_dict
        return None

    def get_user_courses(self, db: Session, user_email: str) -> List[Course]:
        courses = (
            db.query(Course)
            .filter(Course.user_id == user_email)
            .order_by(Course.id.desc())
            .all()
        )
        return courses

    def generate_video_content(self, db: Session, chapter: dict, course_id: str):
        existing_slide = (
            db.query(ChapterContentSlide)
            .filter(
                ChapterContentSlide.course_id == course_id,
                ChapterContentSlide.chapter_id == chapter["chapterId"],
            )
            .first()
        )

        if existing_slide:
            return {"message": "Content already exists", "skipped": True}

        video_content = langchain_generator.generate_video_content(chapter)

        audio_file_urls = []
        caption_array = []

        for i, slide in enumerate(video_content):
            # if i > 0:
            #     break

            narration = slide["narration"]["fullText"]
            audio_buffer = audio_service.generate_audio(narration)
            audio_url = audio_service.save_audio_to_storage(
                audio_buffer=audio_buffer, file_name=slide["audioFileName"]
            )
            audio_file_urls.append(audio_url)

            caption = caption_service.generate_captions(audio_url)
            caption_array.append(caption)

            slide_record = ChapterContentSlide(
                course_id=course_id,
                chapter_id=chapter["chapterId"],
                slide_id=slide["slideId"],
                slide_index=slide["slideIndex"],
                audio_file_name=slide["audioFileName"],
                narration=slide["narration"],
                html=slide["html"],
                reveal_data=slide["revealData"],
                audio_file_url=audio_url,
                caption=caption,
            )

            db.add(slide_record)
            db.commit()

        return {
            "videoContent": video_content,
            "audioUrls": audio_file_urls,
            "captions": caption_array,
        }


course_service = CourseService()
