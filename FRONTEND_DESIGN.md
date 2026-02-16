# Frontend Design Guide

## 📐 Architecture Overview

**Technology Stack** (Recommended):
- Framework: React.js / Vue.js / Angular
- State Management: Redux / Pinia / NgRx
- UI Library: Material-UI / Tailwind CSS / Bootstrap
- API Client: Axios / Fetch API
- Charts: Chart.js / Recharts / ApexCharts

## 🏗️ Page Structure

### 1. **Dashboard (Home Page)**
**Route**: `/dashboard`

**Components**:
- **Summary Card Widget**
  - Total Students
  - Students at Risk
  - Pending Complaints
  - Active Schedule Events
  
- **Risk Alert Banner**
  - Display high-severity risks
  - Link to detailed risk view
  
- **Quick Stats Section**
  - Attendance overview chart
  - Complaint status pie chart
  - Schedule conflict counter

**API Calls**:
```
GET /dashboard/summary
GET /dashboard/risks/students
GET /dashboard/complaints/priority
GET /dashboard/schedule/conflicts
GET /dashboard/attendance/low-attendance?threshold=0.75
```

---

### 2. **Student Management Page**
**Route**: `/students`

**Components**:
- **Student Table**
  - Columns: ID, Name, Roll No, Department, Semester, Actions
  - Sorting & Pagination
  - Search/Filter by department
  
- **Add Student Modal**
  - Form: Name, Roll No, Department, Semester
  - Validation before submit
  
- **Student Detail View**
  - Basic info
  - Recent attendance records
  - Active complaints
  - Risk history

**API Calls**:
```
GET /students/
POST /students/
GET /students/{id}
PUT /students/{id}
```

---

### 3. **Attendance Management Page**
**Route**: `/attendance`

**Components**:
- **Attendance Record Form**
  - Student selector (dropdown)
  - Status: Present / Absent / Late
  - Remarks (optional text)
  - Submit button
  
- **Attendance History Table**
  - Student name, Date, Status, Remarks
  - Filter by date range
  - Filter by status
  
- **Risk Indicator**
  - Show warning if student attendance < 75%
  - Link to risk details

**API Calls**:
```
POST /attendance/
GET /attendance/student/{id}
GET /risk-logs/unresolved
```

---

### 4. **Complaint Management Page**
**Route**: `/complaints`

**Components**:
- **Complaint Form (File New)**
  - Student selector
  - Title (text input)
  - Description (textarea)
  - Category dropdown
  - Auto-priority badge (shown after submit)
  
- **Complaint List Table**
  - Columns: ID, Student, Title, Category, Priority (color-coded), Status
  - Filter by priority
  - Filter by status
  - Sort by date
  
- **Complaint Detail Modal**
  - Full description
  - Priority badge
  - Status dropdown (to update)
  - Auto-detected keywords display
  
- **Priority Legend**
  - Red: Urgent
  - Orange: High
  - Yellow: Medium
  - Gray: Low

**API Calls**:
```
POST /complaints/
GET /complaints/
PUT /complaints/{id}
GET /dashboard/complaints/priority
```

---

### 5. **Schedule Management Page**
**Route**: `/schedules`

**Components**:
- **Create Schedule Form**
  - Title
  - Event type selector (Class/Exam/Meeting)
  - Start date & time picker
  - End date & time picker
  - Location
  - Conflict warning (if overlap detected)
  
- **Schedule Calendar View**
  - Month/Week view
  - Color-coded by event type
  - Click to view details
  - Highlight conflicts in red
  
- **Active Events List**
  - Table format
  - Upcoming events first
  - Location column
  - Conflict badge if applicable
  
- **Conflict Alert Section**
  - Display detected conflicts
  - Shows overlapping events
  - Time range display

**API Calls**:
```
POST /schedules/
GET /schedules/active
PUT /schedules/{id}
GET /dashboard/schedule/conflicts
```

---

### 6. **Risk Management Page**
**Route**: `/risks`

**Components**:
- **Risk Summary Card**
  - Total active risks
  - By severity breakdown
  
- **Risk Log Table**
  - Columns: Student, Risk Type, Severity, Date Created, Status
  - Filter by severity
  - Filter by risk type
  - Filter by status (Unresolved/Resolved)
  
- **Risk Detail Modal**
  - Student info
  - Risk description
  - Severity level
  - Detection timestamp
  - Resolution notes (text area)
  - Mark as resolved button
  
- **Severity Legend**
  - Red: Critical
  - Orange: High
  - Yellow: Medium
  - Green: Low

**API Calls**:
```
GET /risk-logs/unresolved
GET /risk-logs/
GET /dashboard/risks/students
```

---

### 7. **Reports & Analytics Page**
**Route**: `/analytics`

**Components**:
- **Low Attendance Report**
  - Bar chart: Students vs Attendance %
  - Threshold slider (default 75%)
  - Export CSV button
  
- **Complaint Analytics**
  - Pie chart: Priority breakdown
  - Line chart: Complaints over time
  - Status distribution
  
- **Risk Trends**
  - Line chart: Risk count over time
  - Severity breakdown
  
- **Schedule Utilization**
  - Room/location usage statistics
  - Peak hours analysis

**API Calls**:
```
GET /dashboard/attendance/low-attendance?threshold={value}
GET /dashboard/complaints/priority
GET /dashboard/risks/students
GET /dashboard/schedule/conflicts
```

---

## 🎨 UI Components Library

### Reusable Components
```
- DataTable (with sorting, filtering, pagination)
- StatusBadge (color-coded)
- SeverityBadge (Critical/High/Medium/Low)
- PriorityBadge (Urgent/High/Medium/Low)
- Modal/Dialog
- Toast Notifications
- Loading Spinner
- Error Alert
- Success Alert
- Confirmation Dialog
- Date/Time Picker
- Dropdown Selector
- Form Input with Validation
- Chart Component
```

---

## 🔄 Data Flow Diagram

```
User Action
    ↓
Component State Update
    ↓
API Call (Axios/Fetch)
    ↓
Backend Processing + Agent Trigger
    ↓
Response with updated data
    ↓
UI Re-render with new data
    ↓
Show Toast/Alert to user
```

---

## 🎯 Navigation Structure

```
Dashboard (/)
├── Students (/students)
│   └── Student Detail (/students/:id)
├── Attendance (/attendance)
├── Complaints (/complaints)
│   └── Complaint Detail (/complaints/:id)
├── Schedules (/schedules)
│   └── Schedule Detail (/schedules/:id)
├── Risks (/risks)
│   └── Risk Detail (/risks/:id)
├── Analytics (/analytics)
└── Settings (/settings)
```

---

## 📱 Responsive Design

- **Desktop**: Full sidebar navigation + main content
- **Tablet**: Collapsible sidebar + responsive tables
- **Mobile**: Bottom navigation + stacked layout

---

## 🔐 Authentication Flow (Future)

1. Login page (/login)
2. Token storage (localStorage/sessionStorage)
3. Protected routes (require authentication)
4. Logout functionality
5. Session expiry handling

---

## 🚀 Deployment & Build

```bash
# Development
npm start / yarn start

# Production build
npm run build / yarn build

# Environment variables
REACT_APP_API_URL=http://127.0.0.1:8000
REACT_APP_ENV=production
```

---

## ✅ Frontend Checklist

- [ ] Dashboard displays all summary data
- [ ] Student CRUD operations working
- [ ] Attendance recording + risk detection
- [ ] Complaint filing + priority display
- [ ] Schedule creation + conflict detection
- [ ] Risk log management + resolution
- [ ] Analytics charts displaying correctly
- [ ] Responsive design tested
- [ ] Error handling & validation
- [ ] Loading states implemented
- [ ] Toast notifications working
- [ ] Form validation on client side

**Ready to start development! 🚀**
