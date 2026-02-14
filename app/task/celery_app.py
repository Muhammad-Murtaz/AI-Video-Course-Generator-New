"""
celery_app.py
─────────────────────────────────────────────────────────────────────────────
Celery application instance and configuration.
This module ONLY configures the Celery app. All task definitions are in celery_tasks.py.
─────────────────────────────────────────────────────────────────────────────
"""
from celery import Celery
from app.core.config import settings

# ─────────────────────────────────────────────────────────────────────────────
# Celery App Instance
# ─────────────────────────────────────────────────────────────────────────────

celery_app = Celery(
    "ai_video_course",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Results
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },
    
    # Worker
    worker_prefetch_multiplier=1,  # Disable prefetching for long-running tasks
    worker_max_tasks_per_child=1000,  # Restart workers after 1000 tasks
    
    # Rate limiting
    task_default_rate_limit="100/m",
    
    # Routing
    task_routes={
        "app.task.celery_tasks.generate_chapter_video_async": {"queue": "ai_generation"},
        "app.task.celery_tasks.generate_course_intro_async": {"queue": "ai_generation"},
        "app.task.celery_tasks.process_video_content": {"queue": "video_proc"},
        "app.task.celery_tasks.warm_cache_task": {"queue": "maintenance"},
        "app.task.celery_tasks.cleanup_expired_tasks": {"queue": "maintenance"},
    },
    
    # Beat schedule (periodic tasks)
    beat_schedule={
        "warm-cache-daily": {
            "task": "app.task.celery_tasks.warm_cache_task",
            "schedule": 86400.0,  # Every 24 hours
        },
        "cleanup-expired-hourly": {
            "task": "app.task.celery_tasks.cleanup_expired_tasks",
            "schedule": 3600.0,  # Every hour
        },
    },
)

# ─────────────────────────────────────────────────────────────────────────────
# Task Discovery
# ─────────────────────────────────────────────────────────────────────────────

# Celery will auto-discover tasks from these modules
celery_app.autodiscover_tasks(["app.task"])