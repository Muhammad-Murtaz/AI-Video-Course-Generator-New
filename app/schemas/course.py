from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    user_input: str
    course_id: str
    type: str


class GenerateVideoContentRequest(BaseModel):
    """
    Accepts course_id (snake_case from our Next.js route).
    The chapter dict is passed through as-is to langchain_service.
    """

    chapter: Dict[str, Any]
    course_id: str = Field(..., description="UUID of the course")


class CourseIntroRequest(BaseModel):
    courseId: str
    courseLayout: Dict[str, Any]
