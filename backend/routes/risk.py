from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas.risk import RiskLogCreate, RiskLogOut, RiskLogUpdate
from backend.models.risk import RiskLog
from datetime import datetime

router = APIRouter(prefix="/risk-logs", tags=["Risk & Logs"])


@router.post("/", response_model=RiskLogOut, status_code=status.HTTP_201_CREATED)
def create_risk_log(risk: RiskLogCreate, db: Session = Depends(get_db)):
    """Create a new risk log entry"""
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
def get_all_risk_logs(db: Session = Depends(get_db)):
    """Get all risk logs"""
    return db.query(RiskLog).all()


@router.get("/unresolved", response_model=list[RiskLogOut])
def get_unresolved_risks(db: Session = Depends(get_db)):
    """Get all unresolved risk logs"""
    return db.query(RiskLog).filter(RiskLog.resolved == 0).all()


@router.get("/student/{student_id}", response_model=list[RiskLogOut])
def get_student_risk_logs(student_id: int, db: Session = Depends(get_db)):
    """Get risk logs for a specific student"""
    logs = db.query(RiskLog).filter(RiskLog.student_id == student_id).all()
    if not logs:
        raise HTTPException(status_code=404, detail="No risk logs found")
    return logs


@router.get("/{risk_id}", response_model=RiskLogOut)
def get_risk_log(risk_id: int, db: Session = Depends(get_db)):
    """Get a specific risk log"""
    risk = db.query(RiskLog).filter(RiskLog.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk log not found")
    return risk


@router.put("/{risk_id}", response_model=RiskLogOut)
def update_risk_log(risk_id: int, risk: RiskLogUpdate, db: Session = Depends(get_db)):
    """Update a risk log"""
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
def delete_risk_log(risk_id: int, db: Session = Depends(get_db)):
    """Delete a risk log"""
    risk = db.query(RiskLog).filter(RiskLog.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk log not found")
    db.delete(risk)
    db.commit()
    return None
