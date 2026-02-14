# AI Video Course Generator - Python Backend

Complete Python backend with LangChain, FastAPI, PostgreSQL, Redis, and Celery for asynchronous task processing.

## Architecture

```
├── app/
│   ├── main.py                 # FastAPI application
│   ├── core/
│   │   └── config.py          # Settings and configuration
│   ├── db/
│   │   ├── database.py        # Database connection
│   │   └── models.py          # SQLAlchemy models
│   ├── api/
│   │   └── routes.py          # API endpoints
│   ├── schemas/
│   │   └── course.py          # Pydantic schemas
│   ├── services/
│   │   ├── langchain_service.py    # LangChain AI generation
│   │   ├── langchain_rag.py        # RAG for content enhancement
│   │   ├── langchain_agents.py     # LangChain agents
│   │   ├── audio_service.py        # Audio generation
│   │   └── caption_service.py      # Caption generation
│   └── tasks/
│       └── celery_tasks.py    # Background tasks
├── alembic/                   # Database migrations
├── docker-compose.yml         # Docker setup
└── requirements.txt           # Python dependencies
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Create `.env` file with all required variables (see `.env` example above)

### 3. Database Setup

```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

### 4. Run with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### 5. Run Locally

```bash
# Run FastAPI server
uvicorn app.main:app --reload --port 8000

# Run Celery worker (separate terminal)
celery -A app.tasks.celery_tasks worker --loglevel=info

# Run Celery beat (separate terminal)
celery -A app.tasks.celery_tasks beat --loglevel=info
```

## API Endpoints

### User Management
- `POST /api/user` - Create or get user

### Course Generation
- `POST /api/generate-course-layout` - Generate course structure
- `GET /api/course?course_id={id}` - Get course by ID
- `GET /api/course` - Get all user courses
- `POST /api/generate-video-content` - Generate video content for chapter

## LangChain Features

### 1. Course Layout Generation
Uses Azure OpenAI with structured prompts to generate comprehensive course outlines.

### 2. RAG (Retrieval Augmented Generation)
- Enhances course content with existing knowledge base
- Uses FAISS vector store for semantic search
- Generates contextually relevant content

### 3. Agent-Based Generation
- Multi-step course creation using LangChain agents
- Tools for outline generation, slide creation, and narration
- Conversational memory for context retention

### 4. Quiz Generation
Automatically generates quiz questions from chapter content

## Background Tasks (Celery)

### Async Video Generation
```python
from app.tasks.celery_tasks import generate_chapter_video_async

# Queue task
task = generate_chapter_video_async.delay(chapter_data, course_id)

# Check status
result = task.get()
```

### Full Course Generation
```python
from app.tasks.celery_tasks import generate_full_course_async

task = generate_full_course_async.delay(course_id)
```

## Database Models

### User
- email (unique)
- name
- credits (default: 2)

### Course
- course_id (unique)
- course_name
- user_id (FK to User)
- course_layout (JSON)
- type (full-course/quick-explain)

### ChapterContentSlide
- course_id
- chapter_id
- slide_id
- html (slide content)
- narration (JSON)
- reveal_data (animation timing)
- audio_file_url
- caption (JSON)

## Integration with Next.js Frontend

The Python backend provides REST APIs that the Next.js frontend consumes:

```typescript
// Example Next.js API call
const response = await axios.post('http://localhost:8000/api/generate-course-layout', {
  userInput: "Python basics",
  courseId: uuid(),
  type: "full-course"
});
```

## Production Deployment

### Using Docker
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Using Gunicorn
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Monitoring

- FastAPI auto-generates OpenAPI docs at `/docs`
- Celery Flower for task monitoring: `celery -A app.tasks.celery_tasks flower`

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

## Performance Optimization

1. **Caching**: Redis caching for repeated queries
2. **Connection Pooling**: SQLAlchemy connection pool
3. **Async Processing**: Celery for long-running tasks
4. **Vector Store**: FAISS for fast similarity search

## Security

- JWT authentication with Clerk
- Environment variable protection
- SQL injection prevention (SQLAlchemy ORM)
- Rate limiting (implement with FastAPI middleware)

## License

MIT