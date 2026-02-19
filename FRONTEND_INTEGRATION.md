# Frontend Integration Guide

## Overview
This document provides instructions for integrating the Marvel frontend with the Campus Automation backend.

## Architecture

### Backend (FastAPI)
- **Port:** 8000
- **Framework:** FastAPI with SQLAlchemy ORM
- **Features:** Authentication, RBAC, AI agents, analytics, real-time events
- **API:** RESTful endpoints organized by routes

### Frontend (Node.js/HTML)
- **Port:** 3000
- **Structure:** Static HTML + CSS + JavaScript
- **Components:**
  - Homepage
  - Student Attendance
  - Student Performance Dashboard
  - Club Information
  - Events Hub
  - Timetable & Holidays

## Integration Steps

### 1. Update CORS Configuration
The backend already has CORS enabled for frontend communication.

### 2. API Endpoints Available

#### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Current user info

#### Students
- `GET /api/students` - List all students
- `POST /api/students` - Create new student
- `GET /api/students/{id}` - Get student details
- `PUT /api/students/{id}` - Update student

#### Attendance
- `GET /api/attendance` - Get attendance records
- `POST /api/attendance` - Record attendance
- `GET /api/attendance/reports` - Attendance reports

#### Clubs
- `GET /api/clubs` - List all clubs
- `POST /api/clubs` - Create club
- `GET /api/clubs/{id}` - Get club details

#### Dashboard
- `GET /api/dashboard/summary` - Dashboard summary
- `GET /api/dashboard/analytics` - Analytics data

#### AI & Analytics
- `POST /api/ai/agents` - AI agent endpoints
- `GET /api/analytics/reports` - Analytics reports

### 3. Frontend Configuration

Update `frontend/server.js` to:
- Proxy requests to backend
- Serve static files
- Handle CORS

Update frontend HTML files to:
- Point to correct API endpoints
- Use authentication tokens
- Handle API responses

### 4. Environment Setup

**Backend (.env)**
```
DATABASE_URL=sqlite:///./test.db
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your-secret-key
```

**Frontend (frontend/config.js)**
```javascript
const API_BASE_URL = 'http://localhost:8000/api';
const AUTH_TOKEN_KEY = 'auth_token';
```

### 5. Running Both Servers

**Terminal 1 - Backend:**
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
node server.js
```

Access frontend at: `http://localhost:3000`
Backend API at: `http://localhost:8000`

## API Response Format

All endpoints return JSON:
```json
{
  "status": "success|error",
  "data": {},
  "message": "Optional message"
}
```

## Authentication Flow

1. User logs in via frontend
2. Backend returns JWT token
3. Frontend stores token in localStorage
4. Include token in Authorization header: `Bearer {token}`
5. Backend validates token for protected endpoints

## Real-time Features

- Event bus for real-time updates
- WebSocket support for live notifications
- Background tasks for scheduled operations

## File Structure
```
campus automation/
├── backend/          # FastAPI application
├── frontend/         # Marvel frontend
│   ├── server.js     # Express/Node server
│   └── stitch_student_attendance/
│       ├── homepage/
│       ├── student_attendance/
│       ├── student_performance_dashboard/
│       ├── club_information/
│       ├── events_hub/
│       └── timetable_&_holidays/
└── docs/            # Documentation
```

## Troubleshooting

### CORS Issues
- Ensure backend CORS middleware includes frontend origin
- Check browser console for specific CORS errors

### Token Issues
- Verify token is correctly stored after login
- Check token expiration
- Ensure Authorization header format is correct

### API Not Responding
- Verify both servers are running
- Check ports 8000 and 3000 are available
- Review backend logs for errors

## Next Steps

1. Create frontend config file for API endpoints
2. Update frontend HTML to use API routes
3. Implement authentication UI
4. Test end-to-end flow
5. Set up deployment configuration
