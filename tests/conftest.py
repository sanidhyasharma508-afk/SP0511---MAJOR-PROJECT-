import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app
from backend.core.auth import create_access_token
from backend.seed_data import seed_default_users


@pytest.fixture
async def test_client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    # Seed initial test users (admin, staff1, student1, staff2)
    seed_db = TestSessionLocal()
    seed_default_users(seed_db)
    seed_db.close()

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture
def admin_headers():
    token = create_access_token(user_id=1, username="admin", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def staff_headers():
    token = create_access_token(user_id=2, username="staff1", role="staff")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def faculty_headers():
    token = create_access_token(user_id=2, username="staff1", role="staff")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def student_headers():
    token = create_access_token(user_id=3, username="student1", role="student", linked_student_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_faculty_headers():
    token = create_access_token(user_id=4, username="staff2", role="staff")
    return {"Authorization": f"Bearer {token}"}
