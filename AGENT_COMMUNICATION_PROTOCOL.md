# 🤖 Agent Communication Protocol

**Project**: Multiple Agent Project - Campus Automation  
**Version**: 1.0  
**Date**: January 22, 2026

---

## 📡 Overview

This document describes how agents communicate in the Multiple Agent Project architecture. Communication happens at three levels:

1. **Frontend-Backend Communication** (REST API)
2. **Backend Inter-Agent Communication** (Internal Events)
3. **Async Communication** (Background Tasks)

---

## 🌐 Frontend-Backend Communication

### Protocol: REST API over HTTP

```
Frontend Agent               Backend Agent
    │                            │
    ├─ HTTP Request              │
    │  (JSON body) ─────────────>│
    │                            │
    │                    Authentication Agent
    │                    ├─ Verify token
    │                    ├─ Check permissions
    │                    └─ Pass to handler
    │                            │
    │                    Business Logic Agent
    │                    ├─ Process request
    │                    ├─ Query database
    │                    └─ Format response
    │                            │
    │<─────── HTTP Response ─────┤
    │        (JSON body)         │
    │                            │
    └─ Update UI
```

### Request Format

```json
{
  "method": "POST|GET|PUT|DELETE",
  "url": "http://localhost:8000/api/endpoint",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer {jwt_token}"
  },
  "body": {
    "field1": "value1",
    "field2": "value2"
  }
}
```

### Response Format

```json
{
  "status": "success|error",
  "data": {
    "id": 1,
    "name": "Example",
    "timestamp": "2024-01-22T10:30:00Z"
  },
  "message": "Operation completed successfully"
}
```

### Common Endpoints

```
Authentication Agent:
  POST /api/auth/login              ← Login
  POST /api/auth/logout             ← Logout
  GET  /api/auth/me                 ← Current user

Student Agent:
  GET    /api/students              ← List students
  POST   /api/students              ← Create student
  GET    /api/students/{id}         ← Get student
  PUT    /api/students/{id}         ← Update student
  DELETE /api/students/{id}         ← Delete student

Attendance Agent:
  GET  /api/attendance              ← Get records
  POST /api/attendance              ← Record attendance
  GET  /api/attendance/reports      ← Generate report

Club Agent:
  GET    /api/clubs                 ← List clubs
  POST   /api/clubs                 ← Create club
  GET    /api/clubs/{id}            ← Get club
  PUT    /api/clubs/{id}            ← Update club
  DELETE /api/clubs/{id}            ← Delete club

Analytics Agent:
  GET /api/analytics/reports        ← Generate reports
  GET /api/dashboard/summary        ← Dashboard data

AI Agent:
  POST /api/ai/agents               ← AI operations
  POST /api/ai/query                ← Ask question
```

---

## 🔄 Backend Inter-Agent Communication

### Protocol: Event Bus (Event-Driven)

```
Business Logic Agent
    │
    ├─ Process request
    │
    ├─ Modify database
    │
    ├─ Generate event
    │ {
    │   "event_type": "student_created",
    │   "data": {...}
    │ }
    │
    └─ Publish to Event Bus
            │
            ├──────────────────────────────────┐
            │                                  │
            ▼                                  ▼
    Cache Agent               Analytics Agent
    ├─ Invalidate              ├─ Update metrics
    │  old cache               └─ Log event
    │
    └─ Ready for next
       query
```

### Event Types

```
Student Events:
- student.created         ← New student added
- student.updated         ← Student info changed
- student.deleted         ← Student removed
- student.enrolled        ← Student joined club

Attendance Events:
- attendance.recorded     ← Attendance marked
- attendance.updated      ← Record changed
- attendance.report_gen   ← Report generated

Club Events:
- club.created            ← New club created
- club.updated            ← Club info changed
- club.member_joined      ← Member added
- club.member_left        ← Member removed

Analytics Events:
- analytics.metric_update ← Metrics updated
- analytics.report_ready  ← Report generated

System Events:
- system.startup          ← System started
- system.shutdown         ← System shutting down
- system.error            ← Error occurred
```

### Event Message Structure

```python
class Event:
    event_type: str           # e.g., "student.created"
    timestamp: datetime       # When event occurred
    agent_source: str         # Which agent triggered
    data: dict               # Event-specific data
    correlation_id: str      # Track request chain
    
# Example:
event = Event(
    event_type="attendance.recorded",
    timestamp="2024-01-22T10:30:00Z",
    agent_source="attendance_agent",
    data={
        "student_id": 123,
        "date": "2024-01-22",
        "status": "present"
    },
    correlation_id="req_abc123"
)
```

### Event Flow Example

```
1. User clicks "Mark Attendance"
   └─ Frontend Request Agent sends POST

2. Backend Authentication Agent validates token

3. Backend Attendance Agent processes request
   └─ Inserts into database

4. Attendance Agent publishes event:
   {
     "event_type": "attendance.recorded",
     "student_id": 123
   }

5. Event Bus routes to all subscribers:
   
   Analytics Agent:
   └─ Updates attendance count
   
   Cache Agent:
   └─ Invalidates attendance cache
   
   Event Handler Agent:
   └─ Logs to audit trail

6. All agents update their state

7. Success response sent to frontend

8. Frontend updates UI
```

---

## 🔐 Authentication Flow

### Token-Based Authentication

```
1. Frontend Login
   ├─ User submits credentials
   └─ Request Agent sends POST /api/auth/login

2. Backend Authentication Agent
   ├─ Verify username/password
   ├─ Check against database
   └─ Generate JWT token
   
3. Token Response
   ├─ Return JWT in response
   └─ {
       "status": "success",
       "data": {
         "token": "eyJ...",
         "user": {...}
       }
     }

4. Frontend State Agent
   ├─ Store token in localStorage
   ├─ Set in memory state
   └─ Ready for authenticated requests

5. Subsequent Requests
   ├─ Include Authorization header
   └─ Authorization: Bearer {token}

6. Backend Authentication Agent
   ├─ Extract token from header
   ├─ Verify JWT signature
   ├─ Check expiration
   └─ Decode user info
   
7. Request Processing
   ├─ Pass to Business Logic Agent
   └─ Execute request
```

### Token Structure

```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "user_id": 123,
    "email": "user@example.com",
    "role": "admin",
    "exp": 1705939800,
    "iat": 1705853400
  },
  "signature": "HMACSHA256(...)"
}
```

---

## 🔄 Request Lifecycle

### Complete Request Journey

```
┌─────────────────────────────────────────────────────────────────┐
│ FRONTEND                                                        │
├─────────────────────────────────────────────────────────────────┤
│ 1. User Action
│    └─ Click button, fill form
│
│ 2. Validation Agent
│    ├─ Check required fields
│    ├─ Validate format
│    └─ Show errors if needed
│
│ 3. State Agent
│    ├─ Load auth token
│    ├─ Prepare request data
│    └─ Set loading state
│
│ 4. Request Agent
│    ├─ Build HTTP request
│    ├─ Add authorization header
│    └─ Send to backend
└──────────────────┬──────────────────────────────────────────────┘
                   │
        HTTP Request (JSON)
                   │
┌──────────────────▼──────────────────────────────────────────────┐
│ BACKEND                                                         │
├─────────────────────────────────────────────────────────────────┤
│ 5. Express Proxy
│    ├─ Receive HTTP request
│    ├─ Parse JSON
│    └─ Route to FastAPI
│
│ 6. Authentication Agent
│    ├─ Extract token
│    ├─ Verify signature
│    ├─ Check expiration
│    └─ If invalid → Return 401
│
│ 7. Authorization Agent
│    ├─ Get user role
│    ├─ Check endpoint permissions
│    └─ If denied → Return 403
│
│ 8. Input Validation Agent
│    ├─ Parse request body
│    ├─ Validate against schema
│    └─ If invalid → Return 422
│
│ 9. Business Logic Agent
│    ├─ Execute business logic
│    ├─ Apply rules
│    └─ May fail → Return 400
│
│ 10. Database Agent
│    ├─ Execute SQL query
│    ├─ Handle constraints
│    └─ Return data
│
│ 11. Cache Agent
│    ├─ Store result
│    └─ Set TTL
│
│ 12. Event Bus Agent
│    ├─ Generate event
│    ├─ Notify subscribers
│    └─ Log activity
│
│ 13. Response Agent
│    ├─ Format response
│    ├─ Add metadata
│    └─ Convert to JSON
└──────────────────┬──────────────────────────────────────────────┘
                   │
        HTTP Response (JSON)
                   │
┌──────────────────▼──────────────────────────────────────────────┐
│ FRONTEND                                                        │
├─────────────────────────────────────────────────────────────────┤
│ 14. Request Agent
│    ├─ Receive response
│    ├─ Check status code
│    └─ Parse response body
│
│ 15. Error Handler (if error)
│    ├─ Display error message
│    └─ Log for debugging
│
│ 16. State Agent (if success)
│    ├─ Update state
│    ├─ Store data if needed
│    └─ Clear loading state
│
│ 17. UI Agent
│    ├─ Render new data
│    ├─ Show success message
│    └─ Update display
│
│ 18. Complete
│    └─ User sees updated UI
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔌 Agent Integration Points

### Frontend Integration Points

```javascript
// In frontend/config.js

// State Agent - Authentication
api.getToken()              // Get stored JWT
api.setToken(token)         // Store JWT
api.clearToken()            // Remove JWT

// Request Agent - HTTP Methods
api.get(endpoint)
api.post(endpoint, data)
api.put(endpoint, data)
api.delete(endpoint)

// Pre-built Request Methods
api.login(email, password)
api.logout()
api.getStudents()
api.post('/attendance', data)
api.getClubs()
api.getDashboard()
```

### Backend Integration Points

```python
# In backend/routes/ - Each route is an agent endpoint

# Authentication Agent
@router.post("/auth/login")
def login(credentials: LoginSchema)

# Student Agent
@router.get("/students")
def list_students(skip: int = 0, limit: int = 10)

@router.post("/students")
def create_student(student: StudentSchema)

# Attendance Agent
@router.post("/attendance")
def record_attendance(attendance: AttendanceSchema)

# Analytics Agent
@router.get("/analytics/reports")
def generate_report(params: dict)

# AI Agent
@router.post("/ai/agents")
def ai_operation(request: AIAgentRequest)
```

---

## 🚨 Error Handling & Recovery

### Error Response Format

```json
{
  "status": "error",
  "message": "Human-readable error message",
  "error_code": "INVALID_INPUT",
  "details": {
    "field": "email",
    "issue": "Invalid email format"
  }
}
```

### Common Error Codes

```
2xx - Success
  200 OK - Request successful
  201 Created - Resource created
  204 No Content - Success, no body

4xx - Client Error
  400 Bad Request - Invalid input
  401 Unauthorized - Need authentication
  403 Forbidden - Insufficient permissions
  404 Not Found - Resource doesn't exist
  422 Unprocessable Entity - Validation error
  429 Too Many Requests - Rate limited

5xx - Server Error
  500 Internal Server Error - Server error
  503 Service Unavailable - Maintenance
```

### Retry Logic

```
Frontend Request Agent:
├─ Send request
├─ If timeout → Retry (max 3 times)
├─ If 5xx error → Retry (with exponential backoff)
├─ If 4xx error → Don't retry
└─ Show error to user
```

---

## 🔄 Real-Time Communication (Future)

### WebSocket Support (Planned)

```
Frontend WebSocket Agent
        │
        │ WebSocket connection
        │
Backend WebSocket Agent
        │
        ├─ Real-time notifications
        ├─ Live updates
        └─ Bi-directional messages

Event: New Attendance Record
  └─ Broadcast to all connected clients
```

---

## 📊 Communication Patterns

### Request-Response (Synchronous)

```
Client → Request → Server
         (waits)    ↓
         ← Response ←
         (continues)
```

### Event-Driven (Asynchronous)

```
Agent A → Publish Event → Event Bus
                          ↓
                    Subscriber 1 (Agent B)
                    Subscriber 2 (Agent C)
                    Subscriber 3 (Agent D)
                    (all notified)
```

### Pub-Sub (Asynchronous)

```
Many Publishers
        │
        └─→ Event Bus ←─ Many Subscribers
                │
        Multiple agents
        can publish to
        same topic
```

---

## 🔐 Security in Communication

### Data Protection

```
1. Transport Layer
   ├─ HTTPS (Production)
   ├─ TLS 1.3
   └─ Encrypted in transit

2. Application Layer
   ├─ JWT tokens
   ├─ Role-based access
   ├─ Input validation
   └─ Output encoding

3. Database Layer
   ├─ SQL parameterized queries
   ├─ Password hashing
   └─ Encrypted sensitive data
```

### Rate Limiting

```
Frontend Request Agent
    ├─ Max 100 requests/minute
    ├─ Max 10 concurrent requests
    └─ Queue excess requests

Backend Authentication Agent
    ├─ Max 5 login attempts/minute
    ├─ Ban after 10 failed attempts
    └─ Lock for 15 minutes
```

---

## 📋 Communication Checklist

When designing agent communication:

- [ ] Define request/response format (JSON)
- [ ] Define authentication mechanism (JWT tokens)
- [ ] Define error handling (HTTP status codes)
- [ ] Define event types (event_type field)
- [ ] Define retry logic (exponential backoff)
- [ ] Define rate limits (requests/minute)
- [ ] Define logging (correlation IDs)
- [ ] Define security (encryption, validation)
- [ ] Define monitoring (metrics, traces)
- [ ] Define documentation (API docs)

---

## 🎯 Summary

The Multiple Agent Project uses:

- **REST API** for frontend-backend communication
- **Event Bus** for backend inter-agent communication
- **JWT Tokens** for authentication
- **JSON** for data exchange
- **HTTP Status Codes** for error handling
- **Event Types** for async coordination

This enables agents to:
- ✅ Communicate reliably
- ✅ Handle errors gracefully
- ✅ Scale independently
- ✅ Maintain consistency
- ✅ Operate asynchronously

---

**Document Version**: 1.0  
**Last Updated**: January 22, 2026  
**Status**: Complete & Tested
