# Campus Automation Backend - Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Dashboard)                           │
│                  (Future: React/Vue.js Application)                      │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           │ HTTP Requests
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND                                 │
│                    (127.0.0.1:8000)                                      │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              ROUTE LAYER (API Endpoints)                         │   │
│  │  ┌─────────────┐ ┌──────────────┐ ┌────────────┐ ┌───────────┐ │   │
│  │  │  /students  │ │ /attendance  │ │/complaints│ │/schedules │ │   │
│  │  └─────────────┘ └──────────────┘ └────────────┘ └───────────┘ │   │
│  │  ┌───────────────┐ ┌────────────┐ ┌──────────────────────────┐  │   │
│  │  │  /risk-logs   │ │  /health   │ │   /dashboard/*           │  │   │
│  │  │               │ │            │ │ (risks, complaints,      │  │   │
│  │  │               │ │            │ │  conflicts, summary)     │  │   │
│  │  └───────────────┘ └────────────┘ └──────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           │                                              │
│                           ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              SCHEMA LAYER (Validation)                           │   │
│  │  Pydantic models validate all requests/responses                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                           │                                              │
│                           ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              DATABASE LAYER                                      │   │
│  │                                                                   │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │   │
│  │  │   Student    │ │  Attendance  │ │  Complaint   │            │   │
│  │  │    Model     │ │    Model     │ │   Model      │            │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘            │   │
│  │                                                                   │   │
│  │  ┌──────────────┐ ┌──────────────┐                              │   │
│  │  │  Schedule    │ │    Risk      │                              │   │
│  │  │  Model       │ │   Log Model  │                              │   │
│  │  └──────────────┘ └──────────────┘                              │   │
│  │                      ▲                                            │   │
│  │                      │                                            │   │
│  │              SQLAlchemy ORM ↔ SQLite DB                         │   │
│  │                      (test.db)                                   │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              EVENT-DRIVEN ARCHITECTURE                           │   │
│  │                                                                   │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │           EVENT BUS (Pub/Sub Pattern)                    │  │   │
│  │  │                                                           │  │   │
│  │  │  Events:                                                 │  │   │
│  │  │  • ATTENDANCE_MARKED                                     │  │   │
│  │  │  • COMPLAINT_FILED                                       │  │   │
│  │  │  • SCHEDULE_UPDATED                                      │  │   │
│  │  │  • COMPLAINT_UPDATED                                     │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                      ▲                                            │   │
│  │                      │ Publish Events                             │   │
│  │  ┌──────────────────┴──────────────────────────────────────┐  │   │
│  │  │            AGENT LAYER (Rule-Based)                     │  │   │
│  │  │                                                          │  │   │
│  │  │  ┌──────────────────────────────────────────────────┐  │  │   │
│  │  │  │  AttendanceRiskAgent                             │  │  │   │
│  │  │  │  • Monitors attendance patterns (75% threshold)  │  │  │   │
│  │  │  │  • Creates risk logs for low attendance          │  │  │   │
│  │  │  │  • Calculates severity (High/Medium)             │  │  │   │
│  │  │  └──────────────────────────────────────────────────┘  │  │   │
│  │  │                                                          │  │   │
│  │  │  ┌──────────────────────────────────────────────────┐  │  │   │
│  │  │  │  ComplaintTriageAgent                            │  │  │   │
│  │  │  │  • Auto-categorizes complaints                   │  │  │   │
│  │  │  │  • Assigns priority (Low/Medium/High/Urgent)     │  │  │   │
│  │  │  │  • Uses keyword analysis                         │  │  │   │
│  │  │  └──────────────────────────────────────────────────┘  │  │   │
│  │  │                                                          │  │   │
│  │  │  ┌──────────────────────────────────────────────────┐  │  │   │
│  │  │  │  SchedulerConflictAgent                          │  │  │   │
│  │  │  │  • Detects schedule time overlaps                │  │  │   │
│  │  │  │  • Identifies room conflicts                     │  │  │   │
│  │  │  │  • Creates conflict risk logs                    │  │  │   │
│  │  │  └──────────────────────────────────────────────────┘  │  │   │
│  │  │                                                          │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                      │                                            │   │
│  │                      ▼                                            │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │     Database Updated with Insights                       │  │   │
│  │  │     (Risk Logs, Updated Priorities, Conflict Logs)       │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              DASHBOARD API LAYER                                │   │
│  │                                                                   │   │
│  │  GET /dashboard/risks/students                                  │   │
│  │  ├─ Students at risk with risk counts and severity             │   │
│  │  ├─ Aggregated by student for dashboard view                   │   │
│  │  └─ Supports risk management workflows                         │   │
│  │                                                                   │   │
│  │  GET /dashboard/complaints/priority                             │   │
│  │  ├─ Breakdown by priority (Low/Medium/High/Urgent)             │   │
│  │  ├─ Breakdown by status (Pending/Resolved)                     │   │
│  │  └─ Used for complaint management dashboard                    │   │
│  │                                                                   │   │
│  │  GET /dashboard/schedule/conflicts                              │   │
│  │  ├─ Total conflicts and affected schedules                     │   │
│  │  ├─ Top 10 recent conflicts with details                       │   │
│  │  └─ Used for schedule management view                          │   │
│  │                                                                   │   │
│  │  GET /dashboard/attendance/low-attendance                        │   │
│  │  ├─ Students below attendance threshold                        │   │
│  │  ├─ Attendance percentage and details                          │   │
│  │  └─ Used for attendance tracking                               │   │
│  │                                                                   │   │
│  │  GET /dashboard/summary                                         │   │
│  │  ├─ Total students, at-risk count                              │   │
│  │  ├─ Pending complaints, active schedules                       │   │
│  │  └─ Overall health snapshot                                    │   │
│  │                                                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
USER ACTION                    API ENDPOINT               BUSINESS LOGIC
─────────────────────────────────────────────────────────────────────────

Record Attendance  →  POST /attendance/      →  Save to DB
                      ↓                         ↓
                    Validate Input          Commit Transaction
                      ↓                         ↓
                    Return Response         Publish Event: ATTENDANCE_MARKED
                                                ↓
                                           Event Bus Distributes
                                                ↓
                                           AttendanceRiskAgent
                                                ↓
                                           Check: attendance < 75%?
                                                ├─ YES: Create Risk Log
                                                └─ NO: Do nothing
                                                ↓
                                           Risk Log Saved


File Complaint     →  POST /complaints/     →  Save to DB
                      ↓                         ↓
                    Validate Input          Commit Transaction
                      ↓                         ↓
                    Return Response         Publish Event: COMPLAINT_FILED
                                                ↓
                                           Event Bus Distributes
                                                ↓
                                           ComplaintTriageAgent
                                                ↓
                                           Analyze Keywords
                                                ├─ Detect Priority
                                                ├─ Auto-Categorize
                                                └─ Update Complaint
                                                ↓
                                           Complaint Updated in DB


Create Schedule    →  POST /schedules/      →  Save to DB
                      ↓                         ↓
                    Validate Input          Commit Transaction
                      ↓                         ↓
                    Return Response         Publish Event: SCHEDULE_UPDATED
                                                ↓
                                           Event Bus Distributes
                                                ↓
                                           SchedulerConflictAgent
                                                ↓
                                           Find Overlapping Schedules
                                                ├─ Query same location
                                                ├─ Check time overlap
                                                └─ Find conflicts
                                                ↓
                                           If Conflicts Found:
                                                └─ Create Risk Logs
                                                ↓
                                           Risk Logs Saved


Frontend Request   →  GET /dashboard/*      →  Query Database
                      ↓                         ↓
                    Aggregate Data          Aggregate Results
                      ↓                         ↓
                    Return JSON             Return Dashboard Data
```

## Component Interactions

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Frontend Dashboard                                              │
│  (Consumes JSON APIs)                                            │
│                                                                  │
│  Views:                                                          │
│  • Student Management        → /students/*                      │
│  • Attendance Tracking       → /attendance/* + /dashboard/      │
│  • Complaint Management      → /complaints/* + /dashboard/      │
│  • Schedule Management       → /schedules/* + /dashboard/       │
│  • Risk Analytics Dashboard  → /dashboard/risks/*               │
│  • Overall Statistics        → /dashboard/summary               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Backend Services                                                │
│                                                                  │
│  • CRUD Operations    → Full RESTful API                        │
│  • Event Publishing   → On every data change                    │
│  • Agent Processing   → Real-time rule execution                │
│  • Data Aggregation   → Dashboard API endpoints                 │
│  • Error Handling     → Global exception handlers               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  Database                                                        │
│                                                                  │
│  Tables:                                                         │
│  • students                                                      │
│  • attendance                                                    │
│  • complaints                                                    │
│  • schedules                                                     │
│  • risk_logs                                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

```
Language:        Python 3.14+
Web Framework:   FastAPI (async/await)
ORM:            SQLAlchemy 2.0
Database:       SQLite (dev) / PostgreSQL (production)
Validation:     Pydantic v2
Server:         Uvicorn (ASGI)
Architecture:   Event-Driven + Rule-Based Agents
```

## Deployment Ready ✅

- ✅ Event-driven architecture
- ✅ Scalable agent system
- ✅ Dashboard APIs for frontend
- ✅ Comprehensive error handling
- ✅ Database agnostic (SQLite/PostgreSQL)
- ✅ Environment-based configuration
- ✅ API documentation (Swagger)
- ✅ Production-ready code structure
