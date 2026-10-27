import pytest
from httpx import AsyncClient
from backend.core.auth import create_access_token


@pytest.mark.asyncio
async def test_01_profile_read_requires_auth(test_client: AsyncClient):
    """Profile read must reject unauthenticated requests with 401 Unauthorized"""
    response = await test_client.get("/api/v1/auth/profile")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_02_student_can_read_own_profile(test_client: AsyncClient, student_headers: dict):
    """Student can read their own profile including linked student fields"""
    response = await test_client.get("/api/v1/auth/profile", headers=student_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "student1"
    assert data["role"] == "student"
    assert data["full_name"] == "Alex Johnson"
    assert data["roll_no"] == "21BCS101"
    assert data["department"] == "Computer Science Engineering"
    assert data["semester"] == 4
    assert data["section"] == "A"


@pytest.mark.asyncio
async def test_03_student_update_permitted_profile_fields(test_client: AsyncClient, student_headers: dict):
    """Student can update permitted profile fields (full_name, email, avatar, department, section)"""
    update_payload = {
        "full_name": "Alexander Johnson",
        "email": "alex.updated@campus.edu",
        "avatar": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "department": "Computer Science & Engineering",
        "section": "B",
    }
    response = await test_client.put("/api/v1/auth/profile", headers=student_headers, json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Alexander Johnson"
    assert data["email"] == "alex.updated@campus.edu"
    assert data["department"] == "Computer Science & Engineering"
    assert data["section"] == "B"
    assert data["avatar"].startswith("data:image/png")

    # Read back to verify persistence
    get_res = await test_client.get("/api/v1/auth/profile", headers=student_headers)
    assert get_res.status_code == 200
    persisted = get_res.json()
    assert persisted["full_name"] == "Alexander Johnson"
    assert persisted["email"] == "alex.updated@campus.edu"
    assert persisted["department"] == "Computer Science & Engineering"
    assert persisted["section"] == "B"


@pytest.mark.asyncio
async def test_04_student_cannot_update_privileged_fields(test_client: AsyncClient, student_headers: dict):
    """Students attempting to update privileged fields (role, roll_no, is_active, linked_student_id) are rejected with 403"""
    # 1. Attempt role escalation
    res1 = await test_client.put(
        "/api/v1/auth/profile",
        headers=student_headers,
        json={"role": "admin"},
    )
    assert res1.status_code == 403
    assert "role" in res1.json()["detail"].lower()

    # 2. Attempt account status tampering
    res2 = await test_client.put(
        "/api/v1/auth/profile",
        headers=student_headers,
        json={"is_active": False},
    )
    assert res2.status_code == 403

    # 3. Attempt linked student ID manipulation
    res3 = await test_client.put(
        "/api/v1/auth/profile",
        headers=student_headers,
        json={"linked_student_id": 99},
    )
    assert res3.status_code == 403

    # 4. Attempt roll number modification via profile
    res4 = await test_client.put(
        "/api/v1/auth/profile",
        headers=student_headers,
        json={"roll_no": "21BCS999"},
    )
    assert res4.status_code == 403
    assert "roll" in res4.json()["detail"].lower()

    # 5. Attempt roll number modification via /students/{id}
    res5 = await test_client.put(
        "/students/1",
        headers=student_headers,
        json={
            "name": "Alex Johnson",
            "roll_no": "21BCS999",
            "department": "Computer Science Engineering",
            "semester": 4,
            "section": "A",
        },
    )
    assert res5.status_code == 403


@pytest.mark.asyncio
async def test_05_profile_sync_across_user_and_student_records(test_client: AsyncClient, student_headers: dict):
    """Profile updates sync consistently between User record and linked Student record"""
    update_payload = {
        "full_name": "Alex J. Senior",
        "department": "Information Technology",
        "section": "C",
    }
    response = await test_client.put("/api/v1/auth/profile", headers=student_headers, json=update_payload)
    assert response.status_code == 200

    # Verify student endpoint returns the synchronized fields
    student_res = await test_client.get("/students/1", headers=student_headers)
    assert student_res.status_code == 200
    student_data = student_res.json()
    assert student_data["name"] == "Alex J. Senior"
    assert student_data["department"] == "Information Technology"
    assert student_data["section"] == "C"


@pytest.mark.asyncio
async def test_06_study_tasks_require_auth(test_client: AsyncClient):
    """Study task endpoints reject unauthenticated requests with 401 Unauthorized"""
    res1 = await test_client.get("/api/v1/study-tasks")
    assert res1.status_code == 401

    res2 = await test_client.post("/api/v1/study-tasks", json={"title": "Unauthorized Task"})
    assert res2.status_code == 401

    res3 = await test_client.get("/study-tasks")
    assert res3.status_code == 401


@pytest.mark.asyncio
async def test_07_student_can_create_study_task(test_client: AsyncClient, student_headers: dict):
    """Student can create a study task tied to their authenticated identity"""
    task_payload = {
        "title": "Study Computer Networks Chapter 4",
        "description": "Read subnetting and CIDR notation examples",
        "duration_minutes": 45,
        "remaining_seconds": 2700,
        "is_completed": False,
    }
    response = await test_client.post("/api/v1/study-tasks", headers=student_headers, json=task_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Study Computer Networks Chapter 4"
    assert data["description"] == "Read subnetting and CIDR notation examples"
    assert data["duration_minutes"] == 45
    assert data["remaining_seconds"] == 2700
    assert data["is_completed"] is False
    assert data["user_id"] == 3  # student1 user_id


@pytest.mark.asyncio
async def test_08_student_tasks_data_isolation(test_client: AsyncClient, student_headers: dict, admin_headers: dict):
    """A student can only retrieve their own study tasks, ensuring tenant isolation"""
    # Create task for student1 (user_id=3)
    t1 = await test_client.post(
        "/api/v1/study-tasks",
        headers=student_headers,
        json={"title": "Student1 Task", "duration_minutes": 30},
    )
    assert t1.status_code == 201

    # Create another student user and token
    register_res = await test_client.post(
        "/api/v1/auth/register",
        json={
            "username": "student2",
            "email": "student2@campus.edu",
            "password": "Password123!",
            "full_name": "Riya Mehta",
            "role": "student",
        },
    )
    assert register_res.status_code == 201
    s2_user_id = register_res.json()["user_id"]
    token2 = create_access_token(user_id=s2_user_id, username="student2", role="student")
    s2_headers = {"Authorization": f"Bearer {token2}"}

    # Create task for student2
    t2 = await test_client.post(
        "/api/v1/study-tasks",
        headers=s2_headers,
        json={"title": "Student2 Task", "duration_minutes": 20},
    )
    assert t2.status_code == 201
    s2_task_id = t2.json()["id"]

    # Student 1 lists tasks: must only see student1 tasks
    list1 = await test_client.get("/api/v1/study-tasks", headers=student_headers)
    assert list1.status_code == 200
    tasks1 = list1.json()
    titles1 = [t["title"] for t in tasks1]
    assert "Student1 Task" in titles1
    assert "Student2 Task" not in titles1

    # Student 2 lists tasks: must only see student2 tasks
    list2 = await test_client.get("/api/v1/study-tasks", headers=s2_headers)
    assert list2.status_code == 200
    tasks2 = list2.json()
    titles2 = [t["title"] for t in tasks2]
    assert "Student2 Task" in titles2
    assert "Student1 Task" not in titles2

    # Student 1 attempts to list with ?user_id of student 2: rejected with 403
    forbidden_list = await test_client.get(f"/api/v1/study-tasks?user_id={s2_user_id}", headers=student_headers)
    assert forbidden_list.status_code == 403


@pytest.mark.asyncio
async def test_09_student_update_and_delete_own_study_task(test_client: AsyncClient, student_headers: dict):
    """Student can update, complete, and delete their own study tasks"""
    # Create task
    create_res = await test_client.post(
        "/api/v1/study-tasks",
        headers=student_headers,
        json={"title": "Task to edit and delete", "duration_minutes": 15},
    )
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    # Update task details
    update_res = await test_client.put(
        f"/api/v1/study-tasks/{task_id}",
        headers=student_headers,
        json={"title": "Task updated title", "is_completed": True},
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Task updated title"
    assert update_res.json()["is_completed"] is True

    # Toggle completion status via PATCH
    toggle_res = await test_client.patch(
        f"/api/v1/study-tasks/{task_id}/complete",
        headers=student_headers,
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_completed"] is False

    # Delete task
    del_res = await test_client.delete(f"/api/v1/study-tasks/{task_id}", headers=student_headers)
    assert del_res.status_code == 204

    # Verify task no longer exists
    get_res = await test_client.get(f"/api/v1/study-tasks/{task_id}", headers=student_headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_10_student_cannot_modify_or_delete_other_students_tasks(test_client: AsyncClient, student_headers: dict):
    """Student cannot view, update, toggle, or delete another student's study tasks"""
    # Create second student
    register_res = await test_client.post(
        "/api/v1/auth/register",
        json={
            "username": "student_victim",
            "email": "victim@campus.edu",
            "password": "Password123!",
            "full_name": "Victim Student",
            "role": "student",
        },
    )
    assert register_res.status_code == 201
    v_user_id = register_res.json()["user_id"]
    token_v = create_access_token(user_id=v_user_id, username="student_victim", role="student")
    v_headers = {"Authorization": f"Bearer {token_v}"}

    # Victim creates a task
    create_res = await test_client.post(
        "/api/v1/study-tasks",
        headers=v_headers,
        json={"title": "Private Victim Task", "duration_minutes": 60},
    )
    assert create_res.status_code == 201
    victim_task_id = create_res.json()["id"]

    # Student 1 attempts to read victim's task: 403 Forbidden
    read_res = await test_client.get(f"/api/v1/study-tasks/{victim_task_id}", headers=student_headers)
    assert read_res.status_code == 403

    # Student 1 attempts to update victim's task: 403 Forbidden
    update_res = await test_client.put(
        f"/api/v1/study-tasks/{victim_task_id}",
        headers=student_headers,
        json={"title": "Hacked Title"},
    )
    assert update_res.status_code == 403

    # Student 1 attempts to toggle victim's task: 403 Forbidden
    patch_res = await test_client.patch(f"/api/v1/study-tasks/{victim_task_id}/complete", headers=student_headers)
    assert patch_res.status_code == 403

    # Student 1 attempts to delete victim's task: 403 Forbidden
    delete_res = await test_client.delete(f"/api/v1/study-tasks/{victim_task_id}", headers=student_headers)
    assert delete_res.status_code == 403

    # Verify task was NOT deleted or altered
    verify_res = await test_client.get(f"/api/v1/study-tasks/{victim_task_id}", headers=v_headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["title"] == "Private Victim Task"
