# Campus Automation - Club Management System

## 📚 Overview

The Club Management System allows the institution to manage college clubs, their activities, events, and member participation. This system tracks club information, organizes club-sponsored events, and maintains membership records.

---

## 🎯 Core Features

### 1. Club Management
- Create, read, update, and delete clubs
- Track club information (name, category, advisor, president)
- Monitor club membership counts
- View detailed club information with members and activities

### 2. Club Activities & Events
- Plan and schedule club events and activities
- Track event types (workshops, competitions, meetings, etc.)
- Manage participant expectations and actual attendance
- Update event status (Planned, Ongoing, Completed, Cancelled)

### 3. Club Membership
- Add students as club members
- Assign roles/positions (President, VP, Treasurer, etc.)
- Track membership status (active/inactive)
- View member join dates

### 4. Analytics & Dashboard
- Club statistics (members, activities, participation)
- Upcoming events calendar
- Activity breakdown by club category
- System-wide club summary

---

## 📊 Data Models

### Club Model
```python
{
  "id": Integer (primary key),
  "name": String (unique),
  "description": String (optional),
  "category": String,  # Technical, Cultural, Sports, etc.
  "advisor": String,   # Faculty advisor name
  "president": String, # Student president name (optional)
  "member_count": Integer,
  "is_active": Boolean,
  "created_at": DateTime,
  "updated_at": DateTime
}
```

**Categories Supported:**
- Technical (Programming, Robotics, AI/ML clubs)
- Cultural (Arts, Music, Drama clubs)
- Sports (Cricket, Football, Badminton clubs)
- Academic (STEM, Debate, Science clubs)
- Service (Social Service, Environmental clubs)
- Professional (Marketing, Business clubs)

### ClubActivity Model
```python
{
  "id": Integer (primary key),
  "club_id": Integer (foreign key),
  "title": String,
  "description": String (optional),
  "activity_type": String,  # Event, Workshop, Competition, Meeting
  "start_date": DateTime,
  "end_date": DateTime (optional),
  "location": String (optional),
  "expected_participants": Integer,
  "actual_participants": Integer,
  "status": String,  # Planned, Ongoing, Completed, Cancelled
  "remarks": String (optional),
  "created_at": DateTime,
  "updated_at": DateTime
}
```

**Activity Types:**
- Event (General event)
- Workshop (Training/skill-building)
- Competition (Contest/challenge)
- Meeting (Regular/internal meeting)
- Seminar (Educational session)
- Social (Social gathering)

### ClubMember Model
```python
{
  "id": Integer (primary key),
  "club_id": Integer (foreign key),
  "student_id": Integer (foreign key),
  "position": String (optional),  # President, VP, Treasurer, Member
  "join_date": DateTime,
  "is_active": Boolean
}
```

---

## 🔌 API Endpoints

### Club Endpoints

#### Create Club
```http
POST /clubs/
Content-Type: application/json

{
  "name": "Programming Club",
  "description": "For coding enthusiasts",
  "category": "Technical",
  "advisor": "Dr. John Doe",
  "president": "Alice Smith"
}
```
**Response**: `201 Created` with club details

#### List Clubs
```http
GET /clubs/?skip=0&limit=100
```
**Response**: Array of clubs

#### Get Club Details
```http
GET /clubs/{club_id}
```
**Response**: Club with activities and members

#### Update Club
```http
PUT /clubs/{club_id}
Content-Type: application/json

{
  "president": "New President Name",
  "is_active": true
}
```
**Response**: Updated club details

#### Delete Club
```http
DELETE /clubs/{club_id}
```
**Response**: `204 No Content`

#### Get Club Statistics
```http
GET /clubs/{club_id}/statistics
```
**Response Example**:
```json
{
  "club_id": 1,
  "club_name": "Programming Club",
  "total_members": 45,
  "active_members": 42,
  "total_activities": 12,
  "completed_activities": 8,
  "upcoming_activities": 2,
  "total_participants_engaged": 150,
  "average_participation": 18.75
}
```

---

### Club Activity Endpoints

#### Create Activity
```http
POST /clubs/{club_id}/activities
Content-Type: application/json

{
  "club_id": 1,
  "title": "Hackathon 2026",
  "description": "48-hour coding competition",
  "activity_type": "Competition",
  "start_date": "2026-02-15T09:00:00",
  "end_date": "2026-02-17T17:00:00",
  "location": "Computer Lab A",
  "expected_participants": 50
}
```
**Response**: `201 Created` with activity details

#### List Club Activities
```http
GET /clubs/{club_id}/activities?skip=0&limit=100
```
**Response**: Array of activities for the club

#### Get Activity Details
```http
GET /clubs/activities/{activity_id}
```
**Response**: Activity details with club information

#### Update Activity
```http
PUT /clubs/{club_id}/activities/{activity_id}
Content-Type: application/json

{
  "status": "Completed",
  "actual_participants": 48,
  "remarks": "Excellent participation and results"
}
```
**Response**: Updated activity details

#### Delete Activity
```http
DELETE /clubs/{club_id}/activities/{activity_id}
```
**Response**: `204 No Content`

---

### Club Member Endpoints

#### Add Member to Club
```http
POST /clubs/{club_id}/members
Content-Type: application/json

{
  "club_id": 1,
  "student_id": 5,
  "position": "Vice President"
}
```
**Response**: `201 Created` with member details

#### List Club Members
```http
GET /clubs/{club_id}/members?skip=0&limit=100
```
**Response**: Array of club members

#### Update Member
```http
PUT /clubs/{club_id}/members/{member_id}
Content-Type: application/json

{
  "position": "Treasurer",
  "is_active": true
}
```
**Response**: Updated member details

#### Remove Member
```http
DELETE /clubs/{club_id}/members/{member_id}
```
**Response**: `204 No Content`

---

### Dashboard & Analytics Endpoints

#### All Clubs Summary
```http
GET /clubs/dashboard/all-clubs-summary
```
**Response Example**:
```json
{
  "total_clubs": 8,
  "total_members": 180,
  "total_activities": 35,
  "activities_by_type": {
    "Event": 15,
    "Workshop": 12,
    "Competition": 8
  },
  "clubs_by_category": {
    "Technical": 3,
    "Cultural": 2,
    "Sports": 2,
    "Academic": 1
  },
  "club_details": [
    {
      "id": 1,
      "name": "Programming Club",
      "category": "Technical",
      "member_count": 45,
      "activity_count": 5,
      "president": "Alice Smith"
    }
  ]
}
```

#### Upcoming Events
```http
GET /clubs/dashboard/upcoming-events?days=30
```
**Response Example**:
```json
{
  "period_days": 30,
  "total_upcoming_events": 4,
  "events": [
    {
      "activity_id": 1,
      "club_name": "Programming Club",
      "club_id": 1,
      "title": "Hackathon 2026",
      "activity_type": "Competition",
      "start_date": "2026-02-15T09:00:00",
      "end_date": "2026-02-17T17:00:00",
      "location": "Computer Lab A",
      "expected_participants": 50,
      "status": "Planned"
    }
  ]
}
```

#### Activities by Category
```http
GET /clubs/dashboard/club-activities-by-category
```
**Response Example**:
```json
{
  "total_categories": 4,
  "breakdown": {
    "Technical": {
      "club_count": 3,
      "member_count": 100,
      "activity_count": 15,
      "clubs": [
        {
          "id": 1,
          "name": "Programming Club",
          "members": 45,
          "activities": 5
        }
      ]
    },
    "Cultural": {
      "club_count": 2,
      "member_count": 60,
      "activity_count": 8,
      "clubs": []
    }
  }
}
```

---

## 💡 Usage Examples

### Example 1: Create and Manage a New Club

**Step 1: Create the club**
```bash
curl -X POST http://127.0.0.1:8000/clubs/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Robotics Club",
    "description": "Building robots and competing in competitions",
    "category": "Technical",
    "advisor": "Dr. Sarah Johnson",
    "president": "Bob Wilson"
  }'
```

**Step 2: Add members to the club**
```bash
curl -X POST http://127.0.0.1:8000/clubs/2/members \
  -H "Content-Type: application/json" \
  -d '{
    "club_id": 2,
    "student_id": 3,
    "position": "President"
  }'
```

**Step 3: Create an activity/event**
```bash
curl -X POST http://127.0.0.1:8000/clubs/2/activities \
  -H "Content-Type: application/json" \
  -d '{
    "club_id": 2,
    "title": "Robot Design Workshop",
    "description": "Learn robot design principles",
    "activity_type": "Workshop",
    "start_date": "2026-02-20T14:00:00",
    "end_date": "2026-02-20T17:00:00",
    "location": "Engineering Lab",
    "expected_participants": 30
  }'
```

**Step 4: Update activity status after completion**
```bash
curl -X PUT http://127.0.0.1:8000/clubs/2/activities/1 \
  -H "Content-Type: application/json" \
  -d '{
    "status": "Completed",
    "actual_participants": 28,
    "remarks": "Great workshop, students learned a lot"
  }'
```

---

### Example 2: Monitor Club Activity

**Check overall club statistics**
```bash
curl http://127.0.0.1:8000/clubs/1/statistics
```

**View all upcoming events in next 30 days**
```bash
curl http://127.0.0.1:8000/clubs/dashboard/upcoming-events?days=30
```

**Get activity breakdown by category**
```bash
curl http://127.0.0.1:8000/clubs/dashboard/club-activities-by-category
```

---

## 📈 Analytics & Insights

### Key Metrics Tracked
1. **Club Engagement**: Member count per club
2. **Activity Frequency**: Events organized per club
3. **Participation Rate**: Expected vs actual participants
4. **Activity Distribution**: Events by type and category
5. **Club Health**: Active vs inactive members

### Dashboard Insights
- **Total Clubs**: System-wide club count
- **Member Engagement**: Total members across all clubs
- **Activity Volume**: Total events organized
- **Popular Categories**: Which club types are most active
- **Upcoming Events**: Calendar of planned activities

---

## 🔒 Data Integrity Rules

1. **Club Name Uniqueness**: Club names must be unique across the system
2. **Member Uniqueness**: A student can join a club only once
3. **Activity Cascading**: Deleting a club deletes all its activities and members
4. **Date Validation**: End date should be >= start date for activities
5. **Status Transitions**: Valid statuses are: Planned → Ongoing → Completed (or Cancelled)

---

## 🚀 Integration with Other Modules

### With Student Management
- Club members are linked to students
- Student can be part of multiple clubs
- Track club participation in student records

### With Attendance
- Club events can be tracked for attendance
- Integration possible for club-related attendance marking

### With Analytics
- Dashboard shows club activity trends
- Integration with campus analytics for participation insights
- Can generate reports on club performance

---

## 📋 Implementation Checklist

- ✅ Club model with full CRUD
- ✅ ClubActivity model with event management
- ✅ ClubMember model with membership tracking
- ✅ Club routes (7 endpoints)
- ✅ Club Activity routes (5 endpoints)
- ✅ Club Member routes (5 endpoints)
- ✅ Dashboard & Analytics routes (3 endpoints)
- ✅ Comprehensive schemas and validation
- ✅ Error handling and validation
- ✅ Statistics and summary endpoints
- ✅ Server integration and testing

---

## 🎉 Status: COMPLETE ✅

Club Management System is fully functional with 20 endpoints for managing clubs, activities, and members!

**Total Endpoints Added**: 20
- Club endpoints: 7
- Club Activity endpoints: 5
- Club Member endpoints: 5
- Dashboard/Analytics endpoints: 3
