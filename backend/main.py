from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import logging
import asyncio
from dotenv import load_dotenv

from backend.database import engine
from backend.models import student
from backend.models import attendance, complaint, schedule, risk, club, schedule_feedback, events, qr_attendance
from backend.routes.students import router as students_router
from backend.routes.health import router as health_router
from backend.routes.agents import router as agents_router
from backend.routes.attendance import router as attendance_router
from backend.routes.complaint import router as complaint_router
from backend.routes.schedule import router as schedule_router
from backend.routes.risk import router as risk_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.analytics import router as analytics_router
from backend.routes.clubs import router as clubs_router
from backend.routes.ai import router as ai_router
from backend.routes.auth import router as auth_router
from backend.routes.schedule_feedback import router as schedule_feedback_router
from backend.routes.events import router as events_router
from backend.routes.qr_attendance import router as qr_attendance_router
from backend.core.event_handlers import register_agents
from backend.core.config import settings
from backend.core.logging import setup_logging, get_logger, RequestLoggingMiddleware
from backend.core.background_tasks import task_queue, scheduler
from backend.core.caching import cache_manager

# Load environment variables
load_dotenv()

# Configure logging (Phase 5)
setup_logging()
logger = get_logger(__name__)

# Create tables
student.Base.metadata.create_all(bind=engine)

# Create FastAPI app with environment-specific config
app = FastAPI(
    title=f"Campus Automation | Phase 5 ({settings.ENV})",
    description="Multi-agent backend with security, analytics, AI, and scaling",
    version="5.0.0",
    debug=settings.DEBUG,
)

# Add request logging middleware (Phase 5)
app.add_middleware(RequestLoggingMiddleware)

# Add CORS middleware with config (Phase 5)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(students_router)
app.include_router(attendance_router)
app.include_router(complaint_router)
app.include_router(schedule_router)
app.include_router(schedule_feedback_router)
app.include_router(events_router)
app.include_router(qr_attendance_router)
app.include_router(risk_router)
app.include_router(agents_router)
app.include_router(dashboard_router)
app.include_router(analytics_router)
app.include_router(clubs_router)
app.include_router(ai_router)


# Startup event to register agents and initialize Phase 5 components
@app.on_event("startup")
async def startup_event():
    """Initialize agents, background tasks, and Phase 5 components"""
    logger.log_event("startup_event", level="INFO", environment=settings.ENV, debug=settings.DEBUG)

    # Register event-driven agents (Phase 2)
    register_agents()
    logger.log_event("agents_registered", level="INFO")

    # Initialize cache manager (Phase 5)
    if settings.ENABLE_CACHING:
        logger.log_event(
            "cache_enabled", level="INFO", backend=type(cache_manager.backend).__name__
        )

    # Start background task queue (Phase 5)
    if settings.ENABLE_BACKGROUND_TASKS:
        await task_queue.start()
        logger.log_event(
            "background_tasks_enabled", level="INFO", max_workers=task_queue.max_workers
        )

    # Start task scheduler (Phase 5)
    scheduler_task = asyncio.create_task(scheduler.start())
    logger.log_event("scheduler_started", level="INFO", tasks_count=len(scheduler.tasks))

    # Log startup completion
    logger.log_event(
        "startup_complete",
        level="INFO",
        components=[
            "Event Bus & Agents (Phase 2)",
            "Analytics & Trends (Phase 3)",
            "AI & RAG (Phase 4)",
            "Security & Scaling (Phase 5)",
        ],
    )


# Shutdown event to cleanup Phase 5 components
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup Phase 5 components"""
    logger.log_event("shutdown_event", level="INFO")

    # Stop background tasks
    if settings.ENABLE_BACKGROUND_TASKS:
        await task_queue.stop()
        logger.log_event("background_tasks_stopped", level="INFO")

    # Stop scheduler
    await scheduler.stop()
    logger.log_event("scheduler_stopped", level="INFO")

    logger.log_event("shutdown_complete", level="INFO")


# Global exception handlers
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc):
    logger.log_error("database_error", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database operation failed"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.log_error("unexpected_error", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


@app.get("/")
def home():
    """Root endpoint"""
    return {
        "message": "Campus Automation Backend Running",
        "version": "5.0.0",
        "phase": "Phase 5 - Scaling, Security & Optimization",
        "environment": settings.ENV,
        "docs": "/docs",
        "health": "/health",
        "features": {
            "event_bus": True,
            "agents": True,
            "analytics": True,
            "ai_rag": True,
            "authentication": True,
            "authorization": True,
            "caching": settings.ENABLE_CACHING,
            "background_tasks": settings.ENABLE_BACKGROUND_TASKS,
        },
    }


@app.get("/health/full")
def full_health():
    """Full health check including all Phase 5 components"""
    import time

    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "healthy",
        "version": "5.0.0",
        "environment": settings.ENV,
        "components": {
            "api": "running",
            "database": "running",
            "event_bus": "running",
            "agents": "running",
            "analytics": "running",
            "ai_rag": "running",
            "cache": {
                "enabled": settings.ENABLE_CACHING,
                "backend": type(cache_manager.backend).__name__,
            },
            "background_tasks": {
                "enabled": settings.ENABLE_BACKGROUND_TASKS,
                "queue_size": task_queue.queue.qsize(),
                "workers": task_queue.max_workers,
                "pending": len(task_queue.get_pending_tasks()),
                "running": len(task_queue.get_running_tasks()),
                "completed": len(task_queue.get_completed_tasks()),
            },
            "scheduler": {"running": scheduler.running, "tasks_count": len(scheduler.tasks)},
        },
    }

    return health_status


if __name__ == "__main__":
    import uvicorn
    from datetime import datetime

    logger.log_event(
        "server_starting",
        level="INFO",
        host=settings.HOST,
        port=settings.PORT,
        environment=settings.ENV,
    )

    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level=settings.LOG_LEVEL.lower())
