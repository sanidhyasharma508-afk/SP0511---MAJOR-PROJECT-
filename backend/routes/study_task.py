from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from backend.database import get_db
from backend.models.study_task import StudyTask
from backend.schemas.study_task import StudyTaskCreate, StudyTaskUpdate, StudyTaskOut
from backend.core.rbac import get_current_user
from backend.core.auth import TokenData
from backend.core.logging import get_logger

router = APIRouter(tags=["Study Tasks"])
logger = get_logger("study_tasks")


@router.get("", response_model=List[StudyTaskOut], status_code=status.HTTP_200_OK)
@router.get("/", response_model=List[StudyTaskOut], status_code=status.HTTP_200_OK)
def list_tasks(
    completed: Optional[bool] = Query(None, description="Filter by completion status"),
    user_id: Optional[int] = Query(None, description="Staff/Admin filter by user_id"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List study tasks for current user.
    Students can ONLY see their own study tasks.
    Staff and Admin can inspect tasks for any user.
    """
    query = db.query(StudyTask)

    if current_user.role.lower() == "student":
        # Hard isolation: students only see their own tasks
        if user_id is not None and user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only access their own study tasks",
            )
        query = query.filter(StudyTask.user_id == current_user.user_id)
    else:
        # Staff/Admin
        if user_id is not None:
            query = query.filter(StudyTask.user_id == user_id)
        else:
            query = query.filter(StudyTask.user_id == current_user.user_id)

    if completed is not None:
        query = query.filter(StudyTask.is_completed == completed)

    tasks = query.order_by(StudyTask.created_at.desc()).offset(offset).limit(limit).all()
    return tasks


@router.post("", response_model=StudyTaskOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=StudyTaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    task_in: StudyTaskCreate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new study task.
    The task is always tied to the authenticated user's ID.
    """
    remaining = task_in.remaining_seconds
    if (remaining is None or remaining == 0) and task_in.duration_minutes and task_in.duration_minutes > 0:
        remaining = task_in.duration_minutes * 60

    new_task = StudyTask(
        user_id=current_user.user_id,
        title=task_in.title.strip(),
        description=task_in.description.strip() if task_in.description else None,
        duration_minutes=task_in.duration_minutes or 0,
        remaining_seconds=remaining or 0,
        is_completed=bool(task_in.is_completed),
        due_date=task_in.due_date,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    logger.log_event(
        "study_task_created",
        level="INFO",
        task_id=new_task.id,
        user_id=current_user.user_id,
        title=new_task.title,
    )

    return new_task


@router.get("/{task_id}", response_model=StudyTaskOut, status_code=status.HTTP_200_OK)
def get_task(
    task_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific study task by ID.
    Enforces ownership: students can only retrieve their own tasks.
    """
    task = db.query(StudyTask).filter(StudyTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study task not found",
        )

    if current_user.role.lower() == "student" and task.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot view another student's study tasks",
        )

    return task


@router.put("/{task_id}", response_model=StudyTaskOut, status_code=status.HTTP_200_OK)
def update_task(
    task_id: int,
    task_update: StudyTaskUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a study task.
    Enforces ownership: students can only modify their own tasks.
    """
    task = db.query(StudyTask).filter(StudyTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study task not found",
        )

    if current_user.role.lower() == "student" and task.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot modify another student's study tasks",
        )

    if task_update.title is not None:
        task.title = task_update.title.strip()
    if task_update.description is not None:
        task.description = task_update.description.strip()
    if task_update.duration_minutes is not None:
        task.duration_minutes = task_update.duration_minutes
    if task_update.remaining_seconds is not None:
        task.remaining_seconds = task_update.remaining_seconds
    if task_update.is_completed is not None:
        task.is_completed = task_update.is_completed
    if task_update.due_date is not None:
        task.due_date = task_update.due_date

    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    logger.log_event(
        "study_task_updated",
        level="INFO",
        task_id=task.id,
        user_id=current_user.user_id,
    )

    return task


@router.patch("/{task_id}/complete", response_model=StudyTaskOut, status_code=status.HTTP_200_OK)
def toggle_task_complete(
    task_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Toggle task completion status.
    Enforces ownership: students can only toggle their own tasks.
    """
    task = db.query(StudyTask).filter(StudyTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study task not found",
        )

    if current_user.role.lower() == "student" and task.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot modify another student's study tasks",
        )

    task.is_completed = not task.is_completed
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a study task.
    Enforces ownership: students can only delete their own tasks.
    """
    task = db.query(StudyTask).filter(StudyTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study task not found",
        )

    if current_user.role.lower() == "student" and task.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You cannot delete another student's study tasks",
        )

    db.delete(task)
    db.commit()

    logger.log_event(
        "study_task_deleted",
        level="INFO",
        task_id=task_id,
        user_id=current_user.user_id,
    )

    return None
