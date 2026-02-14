from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime


class ChapterBase(BaseModel):
    chapter_id: str
    chapter_title: str
    sub_content: List[str]


class CourseLayoutBase(BaseModel):
    course_name: str
    course_description: str
    course_id: str
    level: str
    total_chapters: int
    chapters: List[ChapterBase]


class CourseCreate(BaseModel):
    user_input: str
    course_id: str
    type: str


class CourseResponse(BaseModel):
    id: int
    course_id: str
    course_name: Optional[str]
    user_id: str
    user_input: Optional[str]
    type: Optional[str]
    course_layout: Optional[Any]
    create_at: datetime

    class Config:
        from_attributes = True


class VideoContentSlide(BaseModel):
    slide_id: str
    slide_index: int
    audio_file_name: str
    narration: dict
    html: str
    reveal_data: dict


class GenerateVideoContentRequest(BaseModel):
    chapter: dict
    course_id: str


class CourseIntroRequest(BaseModel):
    courseId: str
    courseLayout: Dict


    