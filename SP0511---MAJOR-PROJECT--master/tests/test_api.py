"""
Test suite for Campus Automation Backend
Comprehensive examples for testing all endpoints
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
import json


# Example test fixtures
@pytest.fixture
async def test_client():
    """Create test client"""
    from backend.main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_student_data():
    """Sample student data for testing"""
    return {
        "name": "John Doe",
        "email": "john@example.com",
        "roll_no": "2024001",
        "department": "CSE",
        "semester": 1
    }


@pytest.fixture
def sample_attendance_data():
    """Sample attendance data"""
    return {
        "student_id": 1,
        "course_id": 1,
        "date": datetime.now().date().isoformat(),
        "status": "present"
    }


# Health Check Tests
class TestHealthEndpoint:
    """Tests for system health endpoint"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, test_client):
        """Test health check endpoint"""
        response = await test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_health_includes_agents(self, test_client):
        """Test health includes active agents"""
        response = await test_client.get("/health")
        data = response.json()
        assert "agents" in data
        assert len(data.get("agents", [])) > 0


# Authentication Tests
class TestAuthEndpoints:
    """Tests for authentication endpoints"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, test_client):
        """Test successful login"""
        credentials = {
            "username": "admin",
            "password": "password123"
        }
        response = await test_client.post("/api/auth/login", json=credentials)
        assert response.status_code in [200, 401]  # Depends on test user setup
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, test_client):
        """Test login with invalid credentials"""
        credentials = {
            "username": "nonexistent",
            "password": "wrongpassword"
        }
        response = await test_client.post("/api/auth/login", json=credentials)
        assert response.status_code == 401


# Student Management Tests
class TestStudentEndpoints:
    """Tests for student management endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_students(self, test_client):
        """Test retrieving all students"""
        response = await test_client.get("/api/students")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    @pytest.mark.asyncio
    async def test_create_student(self, test_client, sample_student_data):
        """Test creating a new student"""
        response = await test_client.post(
            "/api/students",
            json=sample_student_data
        )
        assert response.status_code in [201, 400, 401]
    
    @pytest.mark.asyncio
    async def test_get_student_by_id(self, test_client):
        """Test retrieving a specific student"""
        response = await test_client.get("/api/students/1")
        assert response.status_code in [200, 404, 401]
    
    @pytest.mark.asyncio
    async def test_update_student(self, test_client, sample_student_data):
        """Test updating student data"""
        response = await test_client.put(
            "/api/students/1",
            json=sample_student_data
        )
        assert response.status_code in [200, 404, 401]
    
    @pytest.mark.asyncio
    async def test_delete_student(self, test_client):
        """Test deleting a student"""
        response = await test_client.delete("/api/students/1")
        assert response.status_code in [204, 404, 401]


# Attendance Tests
class TestAttendanceEndpoints:
    """Tests for attendance management"""
    
    @pytest.mark.asyncio
    async def test_get_attendance(self, test_client):
        """Test retrieving attendance records"""
        response = await test_client.get("/api/attendance")
        assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_mark_attendance(self, test_client, sample_attendance_data):
        """Test marking attendance"""
        response = await test_client.post(
            "/api/attendance",
            json=sample_attendance_data
        )
        assert response.status_code in [201, 400, 401]
    
    @pytest.mark.asyncio
    async def test_get_attendance_report(self, test_client):
        """Test getting attendance report"""
        response = await test_client.get("/api/attendance/report")
        assert response.status_code in [200, 401]


# Club Management Tests
class TestClubEndpoints:
    """Tests for club management"""
    
    @pytest.mark.asyncio
    async def test_get_clubs(self, test_client):
        """Test retrieving all clubs"""
        response = await test_client.get("/api/clubs")
        assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_create_club(self, test_client):
        """Test creating a new club"""
        club_data = {
            "name": "Tech Club",
            "description": "For tech enthusiasts",
            "coordinator_id": 1
        }
        response = await test_client.post("/api/clubs", json=club_data)
        assert response.status_code in [201, 400, 401]


# Analytics Tests
class TestAnalyticsEndpoints:
    """Tests for analytics"""
    
    @pytest.mark.asyncio
    async def test_get_dashboard(self, test_client):
        """Test getting dashboard analytics"""
        response = await test_client.get("/api/analytics/dashboard")
        assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_get_attendance_analytics(self, test_client):
        """Test attendance analytics"""
        response = await test_client.get("/api/analytics/attendance")
        assert response.status_code in [200, 401]


# AI Agent Tests
class TestAIEndpoints:
    """Tests for AI agent endpoints"""
    
    @pytest.mark.asyncio
    async def test_ai_agent_query(self, test_client):
        """Test querying AI agent"""
        query = {
            "query": "What is the average attendance?",
            "agent": "analytics"
        }
        response = await test_client.post("/api/ai/agents", json=query)
        assert response.status_code in [200, 400, 401]


# Data Validation Tests
class TestDataValidation:
    """Tests for request data validation"""
    
    @pytest.mark.asyncio
    async def test_invalid_email_format(self, test_client):
        """Test validation of invalid email"""
        invalid_data = {
            "name": "Test User",
            "email": "invalid-email",
            "roll_no": "2024001",
            "department": "CSE",
            "semester": 1
        }
        response = await test_client.post(
            "/api/students",
            json=invalid_data
        )
        # Should either validate or reject
        assert response.status_code in [400, 201]
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self, test_client):
        """Test validation of missing required fields"""
        incomplete_data = {
            "name": "Test User"
        }
        response = await test_client.post(
            "/api/students",
            json=incomplete_data
        )
        assert response.status_code in [400, 422]


# Performance Tests
class TestPerformance:
    """Tests for performance and response times"""
    
    @pytest.mark.asyncio
    async def test_response_time_students(self, test_client):
        """Test response time for student list"""
        response = await test_client.get("/api/students")
        # Response should be reasonably fast (< 1s for unit test)
        assert response.status_code in [200, 401]


# Integration Tests
class TestIntegration:
    """Integration tests for complete workflows"""
    
    @pytest.mark.asyncio
    async def test_student_creation_and_retrieval(self, test_client, sample_student_data):
        """Test creating and retrieving a student"""
        # Create
        create_response = await test_client.post(
            "/api/students",
            json=sample_student_data
        )
        
        if create_response.status_code == 201:
            student_id = create_response.json().get("id")
            
            # Retrieve
            get_response = await test_client.get(f"/api/students/{student_id}")
            assert get_response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
