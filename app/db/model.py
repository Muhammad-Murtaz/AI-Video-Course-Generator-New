from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text, func
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=False, unique=True, index=True)
    clerk_id = Column(String, unique=True, nullable=True)  # Add this
    credits = Column(Integer, default=10)
    hashed_password = Column(String, nullable=True)  # Make nullable for OAuth users


class  Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String, unique=True, nullable=False, index=True)
    course_name = Column(String)
    user_id = Column(
        String,
        ForeignKey("users.email"),
        nullable=False,
    )
    user_input = Column(String)
    type = Column(String)
    course_layout = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Chapter(Base):
    __tablename__ = "chapter"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String, nullable=False, index=True)
    chapter_id = Column(String, nullable=False, index=True)
    video_content = Column(JSON)
    caption = Column(JSON)
    audio_file_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ChapterContentSlide(Base):
    __tablename__ = "chapter_content_slides"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String, nullable=False, index=True)
    chapter_id = Column(String, nullable=False, index=True)
    slide_id = Column(String, nullable=False)
    slide_index = Column(Integer, nullable=False)
    audio_file_name = Column(String, nullable=False)
    narration = Column(JSON, nullable=False)
    html = Column(Text, nullable=False)
    reveal_data = Column(JSON, nullable=False)
    audio_file_url = Column(String, nullable=True)
    caption = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CourseIntroSlide(Base):
    __tablename__ = "course_intro_slides"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(String, nullable=False, index=True)
    slide_id = Column(String, nullable=False)
    slide_index = Column(Integer, nullable=False)
    audio_file_name = Column(String, nullable=False)
    narration = Column(JSON, nullable=False)
    html = Column(Text, nullable=False)
    reveal_data = Column(JSON, nullable=False)
    audio_file_url = Column(String, nullable=True)
    caption = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())