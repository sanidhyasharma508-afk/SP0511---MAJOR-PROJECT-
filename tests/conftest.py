import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import timedelta

from backend.database import Base, get_db
from backend.main import app
from backend.core.auth import create_access_token
from backend.models.user import User
from backend.models.student import Student


@pytest.fixture
async def test_client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed basic users and students for tests
    db = TestSessionLocal()
    student = Student(id=1, name="Alice", roll_no="21CS001", department="CSE", semester=4, section="A")
    db.add(student)
    db.commit()

    staff_user = User(
        id=1,
        username="staff_user",
        email="staff@campus.edu",
        hashed_password="hashed_pw_test",
        full_name="Staff Member",
        role="staff",
        is_active=True,
    )
    student_user = User(
        id=2,
        username="21CS001",
        email="student@campus.edu",
        hashed_password="hashed_pw_test",
        full_name="Alice",
        role="student",
        linked_student_id=1,
        is_active=True,
    )
    faculty_user = User(
        id=3,
        username="faculty_user",
        email="faculty@campus.edu",
        hashed_password="hashed_pw_test",
        full_name="Faculty Member",
        role="faculty",
        is_active=True,
    )
    admin_user = User(
        id=4,
        username="admin_user",
        email="admin@campus.edu",
        hashed_password="hashed_pw_test",
        full_name="Admin User",
        role="admin",
        is_active=True,
    )
    db.add_all([staff_user, student_user, faculty_user, admin_user])
    db.commit()
    db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture
def staff_headers():
    token = create_access_token(user_id=1, username="staff_user", role="staff")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers():
    token = create_access_token(user_id=2, username="21CS001", role="student", linked_student_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def faculty_headers():
    token = create_access_token(user_id=3, username="faculty_user", role="faculty")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    token = create_access_token(user_id=4, username="admin_user", role="admin")
    return {"Authorization": f"Bearer {token}"}
