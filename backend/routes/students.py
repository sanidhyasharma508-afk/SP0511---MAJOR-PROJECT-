from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas.student import StudentCreate, StudentOut
from backend.models.student import Student
from backend.core.rbac import get_current_user, require_staff, require_admin, require_faculty, Role
from backend.core.auth import TokenData

router = APIRouter(prefix="/students", tags=["Students"])


@router.post("/", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def add_student(
    student: StudentCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_staff),
):
    """Create a new student (Staff or Admin required)"""
    existing = db.query(Student).filter(Student.roll_no == student.roll_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="Roll number already exists")

    new_student = Student(
        name=student.name,
        roll_no=student.roll_no,
        department=student.department,
        semester=student.semester,
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return new_student


@router.get("/", response_model=list[StudentOut])
def get_all_students(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_faculty),
):
    """Get all students (Faculty, Staff, and Admin only)"""
    return db.query(Student).all()


@router.get("/{student_id}", response_model=StudentOut)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Get a specific student by ID.
    Enforces ownership: students may only view their own student record.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user.role.lower() == "student":
        # Check ownership via linked_student_id or roll number
        is_owner = False
        if current_user.linked_student_id is not None and current_user.linked_student_id == student_id:
            is_owner = True
        elif current_user.sub == student.roll_no:
            is_owner = True

        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students can only view their own private student record",
            )

    return student


@router.put("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: int,
    student: StudentCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
):
    """
    Update a student.
    Staff and Admin can update any student.
    Students can only update their own record.
    """
    db_student = db.query(Student).filter(Student.id == student_id).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user.role.lower() == "student":
        is_owner = False
        if current_user.linked_student_id is not None and current_user.linked_student_id == student_id:
            is_owner = True
        elif current_user.sub == db_student.roll_no:
            is_owner = True

        if not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Students cannot modify another student's record",
            )

        if student.roll_no != db_student.roll_no:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students cannot change their roll number",
            )

    db_student.name = student.name
    db_student.roll_no = student.roll_no
    db_student.department = student.department
    db_student.semester = student.semester
    if hasattr(student, "section") and student.section is not None:
        db_student.section = student.section
    db.commit()
    db.refresh(db_student)
    return db_student


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(require_admin),
):
    """Delete a student (Admin only)"""
    db_student = db.query(Student).filter(Student.id == student_id).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(db_student)
    db.commit()
    return None
