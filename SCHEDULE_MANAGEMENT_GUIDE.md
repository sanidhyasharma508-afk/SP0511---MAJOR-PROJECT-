# Schedule Management System - Complete Guide

## 🎯 Overview

A comprehensive schedule management system that allows students to report timing conflicts, suggest better time slots, and receive automated notifications. Faculty can post announcements directly to all students.

---

## ✨ Key Features

### 1. **Student Feedback Form**
Students can report issues through an intuitive form:
- **Class Timing Clash** - When two classes overlap
- **Mess Timing Issue** - Food service conflicts with classes
- **Suggesting Better Time Slots** - Propose alternative timings
- **Difficulty Attending Sessions** - Report accessibility problems
- **Other Issues** - Any other scheduling concerns

### 2. **Automated Notifications**
When a student submits feedback, the system automatically generates:

#### WhatsApp Message Format
```
📢 *Schedule Feedback Alert*

🔴 *Issue Type:* Class Timing Clash
👤 *Reported By:* Rahul Sharma (21BCS101)
⏰ *Preferred Timing:* 2:00 PM - 4:00 PM on Wednesdays

💬 *Comments:*
Thursday's project session clashes with mess schedule

📅 *Reported On:* 07 February 2026, 08:30 PM

_Please review and take necessary action. Thank you!_
```

#### Telegram Message Format
```
🔔 <b>Schedule Feedback Notification</b>

<b>Issue:</b> Class Timing Clash
<b>Student:</b> Rahul Sharma (21BCS101)
<b>Preferred Timing:</b> 2:00 PM - 4:00 PM on Wednesdays

<b>Additional Details:</b>
Thursday's project session clashes with mess schedule

<i>Reported: 07 February 2026 at 08:30 PM</i>

Action required: Please review and coordinate with the team.
```

#### Email Format
**Subject:** Schedule Issue Report: Class Timing Clash - 21BCS101

**Body:**
```
Dear Team,

A new schedule-related issue has been reported by a student. Please find the details below:

ISSUE DETAILS
═══════════════════════════════════════════
Issue Type: Class Timing Clash
Student Name: Rahul Sharma
Roll Number: 21BCS101
Preferred Timing: 2:00 PM - 4:00 PM on Wednesdays

ADDITIONAL COMMENTS
═══════════════════════════════════════════
Thursday's project session clashes with mess schedule

SUBMISSION DETAILS
═══════════════════════════════════════════
Reported On: 07 February 2026 at 08:30 PM
Status: PENDING

RECOMMENDED ACTIONS
═══════════════════════════════════════════
1. Review the reported timing conflict
2. Coordinate with relevant faculty members
3. Communicate alternative timings to students
4. Update the master schedule if necessary

Please acknowledge receipt of this notification and provide updates on resolution progress.

Best regards,
MBM University Schedule Management System
```

### 3. **Faculty Announcements**
Faculty members can post direct announcements to students with:
- **Priority Levels:** Urgent, High, Normal, Low
- **Target Audience:** All students, specific year, specific branch
- **Expiration Dates:** Auto-hide after specified date
- **Professional Formatting:** Clear, respectful tone

### 4. **Weekly Schedule Calendar**
Beautiful calendar-like theme displaying:
- Daily class schedule
- Lab sessions
- Tutorial timings
- Seminar schedules
- Color-coded by activity type

### 5. **Feedback Statistics Dashboard**
Real-time statistics showing:
- Total feedback received
- Pending issues
- Issues in progress
- Resolved issues
- Resolution rate percentage

---

## 🚀 API Endpoints

### Student Feedback Routes

#### Submit Feedback
```http
POST /api/schedule-management/feedback
Content-Type: application/json

{
  "name": "Rahul Sharma",
  "roll_number": "21BCS101",
  "issue_type": "Class Timing Clash",
  "preferred_timing": "2:00 PM - 4:00 PM on Wednesdays",
  "additional_comments": "Thursday's project session clashes with mess schedule"
}
```

**Response:**
```json
{
  "message": "Feedback submitted successfully! ID: 1",
  "whatsapp_message": "📢 *Schedule Feedback Alert*...",
  "telegram_message": "🔔 <b>Schedule Feedback Notification</b>...",
  "email_subject": "Schedule Issue Report: Class Timing Clash - 21BCS101",
  "email_body": "Dear Team,..."
}
```

#### Get All Feedback
```http
GET /api/schedule-management/feedback?status_filter=pending&skip=0&limit=100
```

#### Get Feedback by ID
```http
GET /api/schedule-management/feedback/{feedback_id}
```

#### Update Feedback Status
```http
PATCH /api/schedule-management/feedback/{feedback_id}
Content-Type: application/json

{
  "status": "resolved"
}
```

#### Get Feedback Statistics
```http
GET /api/schedule-management/feedback/stats/summary
```

**Response:**
```json
{
  "total_feedback": 45,
  "pending": 8,
  "resolved": 32,
  "in_progress": 5,
  "resolution_rate": 71.11
}
```

### Announcement Routes

#### Create Announcement
```http
POST /api/schedule-management/announcements
Content-Type: application/json

{
  "title": "Lab Session Rescheduled",
  "content": "The Data Structures lab scheduled for tomorrow has been moved to Friday 2:00 PM due to faculty unavailability.",
  "author": "Dr. Amit Verma",
  "priority": "high",
  "target_audience": "CS 3rd Year",
  "expires_at": "2026-02-15T23:59:59Z"
}
```

#### Get All Announcements
```http
GET /api/schedule-management/announcements?active_only=true&priority=high
```

#### Get Announcement by ID
```http
GET /api/schedule-management/announcements/{announcement_id}
```

#### Update Announcement
```http
PATCH /api/schedule-management/announcements/{announcement_id}
Content-Type: application/json

{
  "is_active": 0
}
```

#### Delete Announcement (Soft Delete)
```http
DELETE /api/schedule-management/announcements/{announcement_id}
```

---

## 📋 Form Structure

### Student Feedback Form Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Name | Text | Yes | Student's full name |
| Roll Number | Text | Yes | Student ID (e.g., 21BCS101) |
| Issue Type | Dropdown | Yes | Type of scheduling issue |
| Preferred Timing | Text | No | Suggested alternative timing |
| Additional Comments | Textarea | No | Detailed explanation |

### Issue Types Available
1. **Class Timing Clash** - Two or more classes scheduled at the same time
2. **Mess Timing Issue** - Meal times conflict with classes
3. **Suggesting Better Time Slots** - Student suggestions for improvement
4. **Difficulty Attending Sessions** - Physical or logistical barriers
5. **Other Issue** - Any other scheduling concern

---

## 🎨 Weekly Schedule Format

The calendar displays classes in a grid format:

```
Monday          Tuesday         Wednesday       Thursday        Friday
─────────────────────────────────────────────────────────────────────
09:00 AM        10:00 AM        09:00 AM        10:00 AM        09:00 AM
Data Structures Operating Sys   Software Eng    Web Tech        ML
Room 304        Room 305        Room 304        Room 203        Room 305

11:00 AM        01:00 PM        03:00 PM        02:00 PM        11:00 AM
Database Sys    Networks        Project Disc    Lab Session     Seminar
Room 202        Room 201        Room 401        Lab 2           Auditorium

02:00 PM
Lab Session
Lab 1
```

**Color Coding:**
- 🟦 **Lecture** - Blue border
- 🟧 **Lab** - Orange border
- 🟩 **Tutorial** - Green border
- 🟪 **Seminar** - Purple border

---

## ✅ Best Practices to Avoid Timing Conflicts

### 1. **Check Schedule Early**
- Review your weekly schedule at the start of each week
- Mark important sessions in your personal calendar
- Set reminders 15 minutes before each session

### 2. **Coordinate with Team**
- Discuss timing preferences with project team members
- Find common available slots for group meetings
- Communicate changes promptly

### 3. **Communicate Issues Immediately**
- Report conflicts as soon as you notice them
- Provide alternative timing suggestions
- Be specific about the nature of the conflict

### 4. **Set Reminders**
- Use calendar apps (Google Calendar, Outlook)
- Enable push notifications
- Sync across all your devices

### 5. **Plan Ahead**
- Book labs and meeting rooms in advance
- Check for holidays and special events
- Account for travel time between venues

---

## 🔔 Notification Best Practices

### For Team Communication

#### WhatsApp Groups
- Keep messages concise and clear
- Use emojis for quick visual reference
- Tag relevant members when needed
- Follow up within 24 hours

#### Telegram Groups
- Use formatting (bold, italic) for emphasis
- Pin important messages
- Create topic-specific channels
- Archive resolved issues

#### Email
- Use clear subject lines
- Include all relevant details
- CC appropriate stakeholders
- Follow up if no response within 48 hours

### Professional Tone Guidelines

✅ **Do:**
- Be respectful and courteous
- Use formal language
- Provide complete information
- Suggest solutions, not just problems
- Thank recipients for their attention

❌ **Don't:**
- Use aggressive language
- Send without proofreading
- Leave out important details
- Use all caps (seems like shouting)
- Send duplicate messages

---

## 🎯 Sample Announcement Templates

### Template 1: Class Rescheduling
```
📅 Class Rescheduled

Dear Students,

The Operating Systems lecture scheduled for Wednesday, 10th February at 10:00 AM has been rescheduled to Friday, 12th February at 2:00 PM in Room 305.

Please update your calendars accordingly.

Dr. Rajesh Kumar
Department of Computer Science
```

### Template 2: Lab Session Update
```
🔬 Lab Session Update

Students of CS 3rd Year,

Tomorrow's Database Lab (11th Feb) will focus on Advanced SQL Queries. Please ensure you have:
- Completed the prerequisite reading (Chapter 5)
- Brought your laptops with MySQL installed
- Downloaded the sample database from the course portal

Lab timing remains 2:00 PM - 5:00 PM in Lab 2.

Prof. Sneha Patel
```

### Template 3: Urgent Notification
```
⚠️ URGENT: Venue Change

IMMEDIATE ATTENTION REQUIRED

The seminar scheduled for today at 11:00 AM has been moved from the Auditorium to Conference Hall B due to technical issues.

Time remains the same: 11:00 AM
New venue: Conference Hall B, Administrative Block

Please arrive 5 minutes early for seating arrangements.

Admin Office
MBM University
```

---

## 🛠️ Technical Implementation

### Backend (FastAPI)
- **Models:** `ScheduleFeedback`, `Announcement`
- **Schemas:** Pydantic validation
- **Routes:** RESTful API endpoints
- **Database:** SQLAlchemy ORM

### Frontend (HTML/CSS/JavaScript)
- **Responsive design** with mobile support
- **Real-time updates** via async/await
- **Modal dialogs** for notifications
- **Copy-to-clipboard** functionality
- **Form validation** on submit

### Features
- ✅ Form validation
- ✅ Error handling
- ✅ Success notifications
- ✅ Loading states
- ✅ Responsive layout
- ✅ Accessibility support

---

## 📱 User Workflow

### Student Submits Feedback
1. Navigate to "Schedule Management" section
2. Fill out the feedback form
3. Click "Submit Feedback"
4. View success modal with generated notifications
5. Copy message to share with team

### Faculty Posts Announcement
1. Access faculty portal
2. Fill announcement form
3. Set priority and audience
4. Submit announcement
5. Students see it immediately

### Tracking Resolution
1. View feedback statistics
2. Monitor pending issues
3. Update status as resolved
4. Track resolution rates

---

## 🎓 Benefits

### For Students
- ✅ Easy reporting mechanism
- ✅ Transparent communication
- ✅ Quick resolution tracking
- ✅ Better schedule visibility

### For Faculty
- ✅ Centralized feedback collection
- ✅ Direct announcement channel
- ✅ Analytics and insights
- ✅ Improved coordination

### For Administration
- ✅ Data-driven decisions
- ✅ Conflict prevention
- ✅ Better resource allocation
- ✅ Enhanced student satisfaction

---

## 📞 Support

For technical issues or questions:
- **Email:** support@mbm.edu
- **Portal:** Schedule Management section
- **Help Desk:** Available 9 AM - 5 PM
- **Emergency:** Contact admin office

---

## 🚀 Getting Started

1. **Access the Portal:** Navigate to Schedule Management section
2. **View Schedule:** Check the weekly calendar
3. **Report Issues:** Use the feedback form
4. **Check Announcements:** Stay updated with faculty notifications
5. **Track Progress:** Monitor feedback statistics

---

*Last Updated: February 7, 2026*  
*Version: 1.0*  
*MBM University Student Portal*
