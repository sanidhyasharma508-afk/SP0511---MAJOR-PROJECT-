# Campus Automation - Frontend & Backend Integration Setup

## Quick Start Guide

### Prerequisites
- Node.js (v14+) for frontend
- Python 3.8+ for backend
- npm or yarn

### Directory Structure
```
campus automation/
├── backend/                      # FastAPI Backend (Port 8000)
│   ├── main.py
│   ├── requirements.txt
│   ├── core/
│   ├── models/
│   ├── routes/
│   └── schemas/
├── frontend/                     # Marvel Frontend (Port 3000)
│   ├── server.js
│   ├── package.json
│   ├── config.js
│   ├── .env
│   └── stitch_student_attendance/
│       ├── homepage/
│       ├── student_attendance/
│       ├── student_performance_dashboard/
│       ├── club_information/
│       ├── events_hub/
│       └── timetable_&_holidays/
└── .env.template               # Backend environment template
```

## Backend Setup

### 1. Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env` from `.env.template`:
```bash
cp .env.template .env
```

Update `.env` with your settings:
```
ENV=development
DEBUG=True
DATABASE_URL=sqlite:///./test.db
SECRET_KEY=your-secret-key-here
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 3. Initialize Database
```bash
python -c "from backend.database import engine; from backend.models import student, attendance, club, complaint, schedule, risk; student.Base.metadata.create_all(bind=engine)"
```

### 4. Run Backend
```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Backend will be available at: `http://localhost:8000`
API documentation at: `http://localhost:8000/docs`

## Frontend Setup

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Configure Environment
Update `frontend/.env`:
```
PORT=3000
NODE_ENV=development
API_BASE_URL=http://localhost:8000/api
```

### 3. Start Frontend Server
```bash
npm start
```

Frontend will be available at: `http://localhost:3000`

## Running Both Servers

### Option 1: Separate Terminals
**Terminal 1:**
```bash
cd backend
python -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2:**
```bash
cd frontend
npm start
```

### Option 2: Using npm Scripts
From root directory:
```bash
npm run dev  # Requires concurrently package
```

## API Integration

### Authentication Flow

1. **Login**
   ```javascript
   const response = await api.login('user@example.com', 'password');
   // Token automatically stored in localStorage
   ```

2. **Access Protected Routes**
   ```javascript
   const students = await api.getStudents();
   const attendance = await api.getAttendance();
   ```

3. **Logout**
   ```javascript
   await api.logout();
   // Token automatically cleared
   ```

### Using API Client in Frontend

Include in your HTML:
```html
<script src="config.js"></script>
```

Usage in JavaScript:
```javascript
// Get all students
api.getStudents({ limit: 10, skip: 0 })
  .then(response => console.log(response.data))
  .catch(error => console.error(error));

// Get specific student
api.get('/students/1')
  .then(response => console.log(response.data))
  .catch(error => console.error(error));

// Create new record
api.post('/attendance', {
  student_id: 1,
  date: '2024-01-22',
  status: 'present'
})
  .then(response => console.log('Success', response))
  .catch(error => console.error('Error', error));
```

## Available Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `GET /api/auth/me` - Current user profile

### Students
- `GET /api/students` - List all students
- `GET /api/students/{id}` - Get student details
- `POST /api/students` - Create student
- `PUT /api/students/{id}` - Update student
- `DELETE /api/students/{id}` - Delete student

### Attendance
- `GET /api/attendance` - Get attendance records
- `POST /api/attendance` - Record attendance
- `GET /api/attendance/{id}` - Get specific record
- `PUT /api/attendance/{id}` - Update attendance
- `DELETE /api/attendance/{id}` - Delete attendance
- `GET /api/attendance/reports` - Attendance reports

### Clubs
- `GET /api/clubs` - List all clubs
- `GET /api/clubs/{id}` - Get club details
- `POST /api/clubs` - Create club
- `PUT /api/clubs/{id}` - Update club
- `DELETE /api/clubs/{id}` - Delete club

### Dashboard & Analytics
- `GET /api/dashboard/summary` - Dashboard summary
- `GET /api/analytics/reports` - Analytics data
- `POST /api/ai/agents` - AI agent operations

## Frontend Routes

- `/` - Homepage
- `/attendance` - Student Attendance
- `/dashboard` - Performance Dashboard
- `/clubs` - Club Information
- `/events` - Events Hub
- `/timetable` - Timetable & Holidays

## CORS Configuration

Frontend and Backend are configured for cross-origin requests:

**Backend (main.py):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)
```

**Frontend (server.js):**
```javascript
app.use(cors({
    origin: ['http://localhost:3000', 'http://localhost:8000'],
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization']
}));
```

## Troubleshooting

### CORS Errors
- Ensure both `ALLOWED_ORIGINS` in backend `.env` and frontend `server.js` include `http://localhost:3000`
- Check browser console for specific error messages
- Verify both servers are running on correct ports

### Token/Auth Issues
- Clear localStorage: `localStorage.clear()`
- Check that token is properly stored after login
- Verify token format in Authorization header: `Bearer {token}`

### API Not Responding
- Verify backend is running: `http://localhost:8000/health`
- Verify frontend is running: `http://localhost:3000/health`
- Check frontend `.env` has correct `API_BASE_URL`
- Check backend logs for errors

### Port Already in Use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Kill process on port 3000
lsof -ti:3000 | xargs kill -9
```

## Production Deployment

### Backend
1. Create production `.env`:
   ```
   ENV=production
   DEBUG=False
   DATABASE_URL=postgresql://...
   SECRET_KEY=<strong-random-key>
   ALLOWED_ORIGINS=https://yourdomain.com
   ```

2. Run with production server:
   ```bash
   gunicorn backend.main:app --workers 4 --bind 0.0.0.0:8000
   ```

### Frontend
1. Build for production:
   ```bash
   npm run build
   ```

2. Deploy to static host or use production server:
   ```bash
   npm start
   ```

## Development Tips

### Hot Reload
- Backend: `--reload` flag automatically reloads on code changes
- Frontend: Use `nodemon` for auto-restart:
  ```bash
  npm run dev
  ```

### API Testing
- Backend docs: `http://localhost:8000/docs`
- Use REST client (VS Code REST Client extension)

### Database
- View SQLite database:
  ```bash
  sqlite3 test.db
  ```

- Reset database:
  ```bash
  rm test.db
  # Restart backend to recreate
  ```

## Support

For issues or questions:
1. Check application logs in `logs/` directory
2. Enable debug mode in `.env`
3. Check API documentation at `/docs` endpoint
4. Review error messages in browser console

## Next Steps

1. Customize frontend pages in `stitch_student_attendance/`
2. Add authentication UI
3. Implement data binding with API responses
4. Add form validation
5. Deploy to production
