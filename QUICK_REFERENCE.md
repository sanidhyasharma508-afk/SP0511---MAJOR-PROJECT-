# 🚀 Quick Reference - Campus Automation Backend

## Server Status
```
✅ RUNNING on http://127.0.0.1:8000
✅ Swagger UI: http://127.0.0.1:8000/docs
✅ All 3 Agents REGISTERED
✅ Event Bus ACTIVE
```

---

## 📍 API Endpoints by Category

### Students
```
POST   /students/              Create student
GET    /students/              List all
GET    /students/{id}          Get one
PUT    /students/{id}          Update
DELETE /students/{id}          Delete
```

### Attendance (Triggers Risk Agent)
```
POST   /attendance/            Record attendance ⚡ Event Published
GET    /attendance/            List all
GET    /attendance/student/{id} Get student's attendance
GET    /attendance/{id}        Get specific record
PUT    /attendance/{id}        Update
DELETE /attendance/{id}        Delete
```

### Complaints (Triggers Triage Agent)
```
POST   /complaints/            File complaint ⚡ Event Published
GET    /complaints/            List all
GET    /complaints/student/{id} Get student's complaints
GET    /complaints/{id}        Get specific complaint
PUT    /complaints/{id}        Update
DELETE /complaints/{id}        Delete
```

### Schedules (Triggers Conflict Agent)
```
POST   /schedules/             Create schedule ⚡ Event Published
GET    /schedules/             List all
GET    /schedules/active       List active only
GET    /schedules/{id}         Get specific schedule
PUT    /schedules/{id}         Update
DELETE /schedules/{id}         Delete
```

### Risk Logs
```
POST   /risk-logs/             Create risk log
GET    /risk-logs/             List all
GET    /risk-logs/unresolved   List unresolved
GET    /risk-logs/student/{id} Get student's risks
GET    /risk-logs/{id}         Get specific log
PUT    /risk-logs/{id}         Update
DELETE /risk-logs/{id}         Delete
```

### Dashboard Analytics
```
GET    /dashboard/risks/students           Students at risk
GET    /dashboard/complaints/priority      Complaint breakdown
GET    /dashboard/schedule/conflicts       Schedule conflicts
GET    /dashboard/attendance/low-attendance Low attendance list
GET    /dashboard/summary                  Overall statistics
```

### Utilities
```
GET    /health                 Health check
GET    /agents/                List agents
POST   /agents/execute         Execute agent
GET    /agents/{name}          Get agent info
GET    /                       Home/API info
```

---

## 🤖 What Agents Do

### 1️⃣ AttendanceRiskAgent
**Triggers**: When attendance is recorded
**Does**: Checks if attendance < 75% in last 30 days
**Action**: Creates risk log (High/Medium severity)
**Stored**: Risk log with reason and timestamp

### 2️⃣ ComplaintTriageAgent
**Triggers**: When complaint is filed
**Does**: Analyzes keywords in title/description
**Action**: Auto-categorizes & assigns priority
**Stored**: Complaint updated with category/priority

### 3️⃣ SchedulerConflictAgent
**Triggers**: When schedule is created
**Does**: Checks for overlapping schedules in same location
**Action**: Creates risk log for conflicts
**Stored**: Risk log with conflict details

---

## 📊 Quick Test Workflow

### 1. Create Student
```
POST /students/
{
  "name": "John Doe",
  "roll_no": "CS001",
  "department": "Computer Science",
  "semester": 4
}
```
Save the student `id` (e.g., 1)

### 2. Trigger Attendance Risk Agent
```
POST /attendance/
{
  "student_id": 1,
  "status": "Absent",
  "remarks": "Medical"
}
```
✨ Agent checks attendance → Creates risk log if low

### 3. Trigger Complaint Triage Agent
```
POST /complaints/
{
  "student_id": 1,
  "title": "Urgent: Grade issue",
  "description": "My exam grade seems incorrectly calculated. Critical for GPA.",
  "category": "Academic"
}
```
✨ Agent analyzes keywords → Sets priority to "Urgent"

### 4. Trigger Schedule Conflict Agent
```
POST /schedules/
{
  "title": "Math Class",
  "event_type": "Class",
  "start_date": "2026-01-22T09:00:00",
  "end_date": "2026-01-22T10:30:00",
  "location": "Room 101"
}

Then create overlapping:
{
  "title": "Physics Exam",
  "event_type": "Exam",
  "start_date": "2026-01-22T10:00:00",
  "end_date": "2026-01-22T11:30:00",
  "location": "Room 101"
}
```
✨ Agent detects overlap → Creates conflict risk log

### 5. View Dashboard Data
```
GET /dashboard/risks/students
GET /dashboard/complaints/priority
GET /dashboard/schedule/conflicts
GET /dashboard/summary
```

---

## 🛠️ Configuration

### .env File
```
# Database
DATABASE_URL=sqlite:///./test.db
SQL_ECHO=False

# CORS
ALLOWED_ORIGINS=http://localhost:3000

# API
DEBUG=False
LOG_LEVEL=INFO
```

### To Use PostgreSQL
```
DATABASE_URL=postgresql://user:password@localhost/campus_db
```

---

## 📁 Important Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app, routing, startup |
| `backend/core/event_bus.py` | Event system |
| `backend/core/agents.py` | All 3 agents |
| `backend/core/event_handlers.py` | Agent registration |
| `backend/models/` | Database models |
| `backend/schemas/` | Validation schemas |
| `backend/routes/` | API endpoints |
| `backend/routes/dashboard.py` | Analytics endpoints |

---

## 🔍 Debug Tips

### View Live Logs
Watch terminal where server runs - see events publishing, agents triggering

### Check Database
```
sqlite3 test.db
SELECT * FROM risk_logs;
SELECT * FROM complaints;
```

### Test via Swagger
1. Open http://127.0.0.1:8000/docs
2. Click endpoint
3. Click "Try it out"
4. Fill request body
5. Click "Execute"
6. See response immediately

---

## 📚 Documentation Files

- **BACKEND_SUMMARY.md** - Complete overview
- **TESTING_GUIDE.md** - Step-by-step tests
- **ARCHITECTURE.md** - Design diagrams
- **COMPLETION_REPORT.md** - Status report

---

## 🎯 Frontend Integration

Frontend can consume:

```javascript
// Get students
GET /students/

// Record attendance
POST /attendance/

// File complaint
POST /complaints/

// Dashboard analytics
GET /dashboard/risks/students
GET /dashboard/complaints/priority
GET /dashboard/schedule/conflicts
GET /dashboard/summary
```

All responses are JSON with proper schema.

---

## ✅ Verification Checklist

- [ ] Server running on 127.0.0.1:8000
- [ ] Swagger UI accessible at /docs
- [ ] Can create student
- [ ] Can record attendance
- [ ] Can file complaint (priority auto-assigned)
- [ ] Can create schedule
- [ ] Conflict detection works
- [ ] Dashboard APIs return data
- [ ] Error handling works

---

## 🚨 Common Issues

| Issue | Solution |
|-------|----------|
| Port 8000 in use | Kill process: `taskkill /PID <pid> /F` |
| Import errors | Delete `__pycache__`, restart server |
| Database locked | Delete `test.db`, restart server |
| Agent not triggering | Check agent logs in terminal |

---

## 📞 Quick Help

**Server won't start?**
1. Clear `__pycache__`: `Remove-Item -Recurse backend/__pycache__`
2. Restart: `python -m uvicorn backend.main:app`

**Agents not working?**
1. Check terminal for error logs
2. Verify event is published (check logs)
3. Restart server

**API not responding?**
1. Health check: GET /health
2. Check Swagger: /docs
3. Verify database exists

---

**Everything is ready! 🎉**
Backend running, agents active, dashboard ready for frontend!
