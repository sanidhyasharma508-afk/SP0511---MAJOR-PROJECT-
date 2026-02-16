# Backend Testing & Usage Guide

## 🚀 Server Status

**Current Status**: ✅ RUNNING
**URL**: http://127.0.0.1:8000
**Documentation**: http://127.0.0.1:8000/docs
**Port**: 8000

## 📋 Test Workflow

### Step 1: Health Check
```
GET http://127.0.0.1:8000/health
```
Expected: `{"status": "healthy", "database": "connected"}`

### Step 2: Create a Student (Required for tests)
```
POST http://127.0.0.1:8000/students/
Body:
{
  "name": "John Doe",
  "roll_no": "CS001",
  "department": "Computer Science",
  "semester": 4
}
```
Save the returned `id` (e.g., 1)

### Step 3: Test Attendance Risk Agent
```
POST http://127.0.0.1:8000/attendance/
Body:
{
  "student_id": 1,
  "status": "Absent",
  "remarks": "Medical emergency"
}
```
✨ **Agent Triggered**: AttendanceRiskAgent checks if attendance < 75%

Check risk logs:
```
GET http://127.0.0.1:8000/risk-logs/unresolved
```

### Step 4: Test Complaint Triage Agent
```
POST http://127.0.0.1:8000/complaints/
Body:
{
  "student_id": 1,
  "title": "Urgent: Grade calculation error",
  "description": "My exam grade seems incorrectly calculated. This is critical for my GPA.",
  "category": "Academic"
}
```
✨ **Agent Triggered**: ComplaintTriageAgent auto-categorizes and assigns priority

Get the complaint:
```
GET http://127.0.0.1:8000/complaints/
```
Notice: Priority should be "Urgent" (detected from keywords)

### Step 5: Test Schedule Conflict Agent
```
POST http://127.0.0.1:8000/schedules/
Body:
{
  "title": "Math Class",
  "event_type": "Class",
  "start_date": "2026-01-22T09:00:00",
  "end_date": "2026-01-22T10:30:00",
  "location": "Room 101"
}
```

Create overlapping schedule:
```
POST http://127.0.0.1:8000/schedules/
Body:
{
  "title": "Physics Exam",
  "event_type": "Exam",
  "start_date": "2026-01-22T10:00:00",
  "end_date": "2026-01-22T11:30:00",
  "location": "Room 101"
}
```
✨ **Agent Triggered**: SchedulerConflictAgent detects overlap

Check conflicts:
```
GET http://127.0.0.1:8000/dashboard/schedule/conflicts
```

### Step 6: Test Dashboard APIs

#### Students at Risk
```
GET http://127.0.0.1:8000/dashboard/risks/students
```
Returns: Students with active risk flags, risk counts, latest risk

#### Complaint Analytics
```
GET http://127.0.0.1:8000/dashboard/complaints/priority
```
Returns: Breakdown by priority and status

#### Schedule Conflicts
```
GET http://127.0.0.1:8000/dashboard/schedule/conflicts
```
Returns: Total conflicts, affected schedules, conflict details

#### Overall Summary
```
GET http://127.0.0.1:8000/dashboard/summary
```
Returns: Total students, at-risk count, pending complaints, active schedules

#### Low Attendance Report
```
GET http://127.0.0.1:8000/dashboard/attendance/low-attendance?threshold=0.75
```
Returns: Students with attendance below threshold

## 🧪 Swagger UI Testing

1. Open: http://127.0.0.1:8000/docs
2. All endpoints are listed with "Try it out" buttons
3. Fill in request body
4. Click "Execute"
5. See response immediately

## 📊 Expected Test Results

### Attendance Risk Detection
- Record 5-10 attendance records with mix of "Absent", "Late"
- Should create risk log when attendance drops below 75%
- Risk severity auto-calculated

### Complaint Priority Assignment
- File complaint with keywords: "urgent", "critical", "emergency"
- Should auto-assign High or Urgent priority
- Keywords in description also considered

### Schedule Conflict Detection
- Create two schedules in same location with overlapping times
- Should detect conflict and create High severity risk log
- Conflict details stored in risk log description

### Dashboard Aggregation
- All dashboard endpoints pull real data from database
- Risks aggregated by student with severity breakdown
- Complaints summarized by priority and status
- Conflicts listed with full details

## 🔍 Debugging

### View Server Logs
Check terminal where server is running for:
- Event publications
- Agent triggers
- Any errors

### Common Issues
1. **Port already in use**: Kill process on 8000 or change port
2. **Import errors**: Clear `__pycache__` and restart
3. **Database locked**: Delete `test.db` if stuck

## 🎯 Next Steps for Frontend

Frontend can consume these endpoints:

1. **Student Management**
   - POST /students/ - Add student
   - GET /students/ - List students
   - PUT /students/{id} - Update

2. **Attendance Tracking**
   - POST /attendance/ - Record attendance
   - GET /attendance/student/{id} - Get history

3. **Complaint System**
   - POST /complaints/ - File complaint
   - GET /complaints/ - List complaints
   - PUT /complaints/{id} - Update status

4. **Schedule Management**
   - POST /schedules/ - Create event
   - GET /schedules/active - Active events
   - PUT /schedules/{id} - Update

5. **Dashboard Analytics**
   - GET /dashboard/risks/students - Risk view
   - GET /dashboard/complaints/priority - Complaint analytics
   - GET /dashboard/schedule/conflicts - Conflict view
   - GET /dashboard/summary - Overview

## ✅ Verification Checklist

- [ ] Server starts on 127.0.0.1:8000
- [ ] /health returns healthy status
- [ ] /docs shows Swagger UI
- [ ] Can create student
- [ ] Can record attendance
- [ ] Can file complaint
- [ ] Can create schedule
- [ ] Risk agent creates logs
- [ ] Complaint agent updates priority
- [ ] Conflict agent detects overlaps
- [ ] Dashboard APIs return data
- [ ] Error handling works (test invalid data)

**All components ready for frontend integration! 🚀**
