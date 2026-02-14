from fastapi import APIRouter, Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import get_db
from app.services.user_service import UserService
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserCreateClerk
from app.schemas.course import (
    CourseCreate,
    CourseIntroRequest,
    GenerateVideoContentRequest,
)
from app.services.course_service import course_service
from typing import Optional


app = FastAPI(
    title="AI Video Course Generator API",
    description="Generate educational video courses with AI",
    version="1.0.0",
)

# Create API router with prefix
api_router = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "AI Video Course Generator API", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Dependency to get user email from header
async def get_user_email_from_header(x_user_email: Optional[str] = Header(None)) -> str:
    if not x_user_email:
        raise HTTPException(
            status_code=401, detail="Unauthorized: No user email provided"
        )
    return x_user_email


# Traditional email/password signup
@api_router.post("/signup")
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    user = UserService.create_user(db=db, user_data=user_data)
    return {"message": "User created successfully", "user_id": user.id}


# Clerk OAuth signup
@api_router.post("/signup-clerk")
def signup_clerk(user_data: UserCreateClerk, db: Session = Depends(get_db)):
    user = UserService.create_clerk_user(db=db, user_data=user_data)
    return {"message": "User created successfully", "data": user}


# Generate course layout endpoint
@api_router.post("/generate-course-layout")
async def generate_course_layout(
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_user_email_from_header),
):
    try:
        course = course_service.create_course(db, course_data, user_email)
        return {
            "courseId": course.course_id,
            "courseName": course.course_name,
            "courseLayout": course.course_layout,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@api_router.get("/courses/{course_id}")
async def get_course(
    course_id: str,
    db: Session = Depends(get_db),
):

    try:
        course = course_service.get_course_by_id(db, course_id)
        if not course:
            raise HTTPException(status_code=404, detail={"message": "Course not found"})
        return {"course": course}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"message": f"Internal server error: {str(e)}"}
        )


@api_router.get("/courses")
async def get_all_courses(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_user_email_from_header),
):
    try:

        courses = course_service.get_user_courses(db, user_email=user_email)
        return courses
    except Exception as e:
        return HTTPException(
            status_code=500, detail={"message": f"Internal server error: {str(e)}"}
        )


@api_router.post("/generate-course-intro")
async def generate_course_intro(
    request: CourseIntroRequest, db: Session = Depends(get_db)
):
    """
    Generate introduction/overview content for the course
    """
    try:
        result = course_service.generate_course_introduction(
            db=db, course_id=request.courseId, course_layout=request.courseLayout
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/generate-video-content")
async def generate_video_content(
    video_request: GenerateVideoContentRequest,
    db: Session = Depends(get_db),
):
    try:
        video_content = course_service.generate_video_content(
            db, chapter=video_request.chapter, course_id=video_request.course_id
        )
        return video_content
    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"message": f"Internal server error: {str(e)}"}
        )


# Include the API router in the app
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=600)
