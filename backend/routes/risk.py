from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from backend.database import get_db
from backend.schemas.risk import (
    RiskLogCreate,
    RiskLogOut,
    RiskLogUpdate,
    AcademicRiskEvaluation,
)
from backend.models.risk import RiskLog
from backend.models.student import Student
from backend.models.user import User
from backend.core.rbac import get_current_user, require_staff, require_admin, require_faculty
from backend.core.auth import TokenData
from backend.core.academic_risk import (
    calculate_student_academic_risk,
    check_faculty_student_scope,
)

# Router for legacy risk logs
router = APIRouter(prefix="/risk-logs", tags=["Risk & Logs"])

# Dedicated router for calculated Academic Risk evaluation
academic_risk_router = APIRouter(prefix="/risk", tags=["Academic Risk"])
academic_risk_alias_router = APIRouter(prefix="/academic-risk", tags=["Academic Risk"])


# --- Academic Risk Evaluation Endpoints ---

def _resolve_authenticated_student(current_user: TokenData, db: Session) -> Optional[Student]:
    """Helper to resolve the student entity for the authenticated user"""
    student = None
    if current_user.linked_student_id is not None:
        student = db.query(Student).filter(Student.id == current_user.linked_student_id).first()
    if not student and current_user.sub:
        student = db.query(Student).filter(Student.roll_no == current_user.sub).first()
    return student


@academic_risk_router.get("/my-risk", response_model=AcademicRiskEvaluation)
def get_my_academic_risk(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get the authenticated student's academic risk evaluation.
    Evaluates real attendance, study tasks, and advisory notes without inventing data.
    """
    student = _resolve_authenticated_student(current_user, db)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student record linked to the current authenticated account.",
        )
    return calculate_student_academic_risk(student.id, db)


@academic_risk_router.get("/student/{student_id}", response_model=AcademicRiskEvaluation)
def get_student_academic_risk(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get academic risk evaluation for a specific student.
    - Students: Can only view their own record (403 otherwise).
    - Faculty: Can only view students within their authorized academic scope (403 otherwise).
    - Staff / Admin: Authorized institutional access.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student with ID {student_id} not found",
        )

    role = (current_user.role or "").lower()
    if role == "student":
        resolved_student = _resolve_authenticated_student(current_user, db)
        if not resolved_student or resolved_student.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own academic risk evaluation",
            )
    elif role == "faculty":
        faculty_user = db.query(User).filter(User.id == current_user.user_id).first()
        if not faculty_user or not check_faculty_student_scope(faculty_user, student, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Faculty can only access academic risk for students within their authorized academic scope",
            )
    elif role not in ("admin", "staff"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Unauthorized role for student risk evaluation",
        )

    return calculate_student_academic_risk(student.id, db)


# Also register the risk endpoints under /academic-risk and /risk-logs for backward compatibility
@academic_risk_alias_router.get("/my-risk", response_model=AcademicRiskEvaluation)
def get_my_academic_risk_alias_direct(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return get_my_academic_risk(db=db, current_user=current_user)


@academic_risk_alias_router.get("/student/{student_id}", response_model=AcademicRiskEvaluation)
def get_student_academic_risk_alias_direct(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return get_student_academic_risk(student_id=student_id, db=db, current_user=current_user)


@router.get("/academic-risk/my-risk", response_model=AcademicRiskEvaluation)
def get_my_academic_risk_alias(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return get_my_academic_risk(db=db, current_user=current_user)


@router.get("/academic-risk/student/{student_id}", response_model=AcademicRiskEvaluation)
def get_student_academic_risk_alias(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    return get_student_academic_risk(student_id=student_id, db=db, current_user=current_user)


# --- Risk Log CRUD Endpoints (Legacy / Administrative) ---

@router.post("/", response_model=RiskLogOut, status_code=status.HTTP_201_CREATED)
def create_risk_log(
    risk: RiskLogCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """Create a new risk log entry (Staff/Admin required)"""
    valid_types = ["Academic", "Behavioral", "Health", "Attendance", "Other"]
    if risk.risk_type not in valid_types:
        raise HTTPException(
            status_code=400, detail=f"Invalid risk type. Must be one of {valid_types}"
        )

    valid_severities = ["Low", "Medium", "High", "Critical"]
    if risk.severity not in valid_severities:
        raise HTTPException(
            status_code=400, detail=f"Invalid severity. Must be one of {valid_severities}"
        )

    new_risk = RiskLog(
        student_id=risk.student_id,
        risk_type=risk.risk_type,
        severity=risk.severity,
        description=risk.description,
        action_taken=risk.action_taken,
    )
    db.add(new_risk)
    db.commit()
    db.refresh(new_risk)
    return new_risk


@router.get("/", response_model=list[RiskLogOut])
def get_all_risk_logs(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """Get all risk logs (Staff/Admin required)"""
    return db.query(RiskLog).all()


@router.get("/unresolved", response_model=list[RiskLogOut])
def get_unresolved_risks(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """Get all unresolved risk logs (Staff/Admin required)"""
    return db.query(RiskLog).filter(RiskLog.resolved == 0).all()


@router.get("/student/{student_id}", response_model=list[RiskLogOut])
def get_student_risk_logs(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get risk logs for a specific student.
    Students can only view their own advisory records.
    """
    if current_user.role.lower() == "student":
        resolved_student = _resolve_authenticated_student(current_user, db)
        if not resolved_student or resolved_student.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own risk advisory logs",
            )

    logs = db.query(RiskLog).filter(RiskLog.student_id == student_id).all()
    if not logs:
        raise HTTPException(status_code=404, detail="No risk logs found")
    return logs


@router.get("/{risk_id}", response_model=RiskLogOut)
def get_risk_log(
    risk_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """Get a specific risk log (Staff/Admin required)"""
    risk = db.query(RiskLog).filter(RiskLog.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk log not found")
    return risk


@router.put("/{risk_id}", response_model=RiskLogOut)
def update_risk_log(
    risk_id: int,
    risk: RiskLogUpdate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """Update a risk log (Staff/Admin required)"""
    db_risk = db.query(RiskLog).filter(RiskLog.id == risk_id).first()
    if not db_risk:
        raise HTTPException(status_code=404, detail="Risk log not found")

    if risk.risk_type:
        db_risk.risk_type = risk.risk_type
    if risk.severity:
        db_risk.severity = risk.severity
    if risk.description:
        db_risk.description = risk.description
    if risk.action_taken is not None:
        db_risk.action_taken = risk.action_taken
    if risk.resolved is not None:
        db_risk.resolved = risk.resolved

    db_risk.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_risk)
    return db_risk


@router.delete("/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_risk_log(
    risk_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_admin),
):
    """Delete a risk log (Admin required)"""
    risk = db.query(RiskLog).filter(RiskLog.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk log not found")
    db.delete(risk)
    db.commit()
    return None
