from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        db.execute("SELECT 1")
        return {
            "status": "healthy",
            "message": "Campus Automation Backend is running",
            "database": "connected",
        }
    except Exception as e:
        return {"status": "unhealthy", "message": str(e), "database": "disconnected"}
