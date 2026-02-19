# Frontend Integration - Quick Reference

## 🎯 What Was Done

Your Marvel frontend has been successfully integrated with the Campus Automation backend:

1. ✅ Frontend cloned to `/frontend` folder
2. ✅ Express.js server configured for API proxy
3. ✅ CORS enabled between frontend and backend
4. ✅ API client created (`config.js`)
5. ✅ Environment configuration set up
6. ✅ Complete documentation provided

---

## 🚀 Start Here

### Step 1: Install Frontend Dependencies
```bash
cd frontend
npm install
```

### Step 2: Run Backend (in one terminal)
```bash
cd backend
python -m uvicorn backend.main:app --reload --port 8000
```

### Step 3: Run Frontend (in another terminal)
```bash
cd frontend
npm start
```

### Step 4: Open Browser
```
Frontend: http://localhost:3000
Backend API: http://localhost:8000
API Docs: http://localhost:8000/docs
```

---

## 📡 Using the API in Frontend

### Option 1: Using the Built-in API Client

```html
<!-- In your HTML file -->
<script src="config.js"></script>

<script>
// Login
api.login('user@example.com', 'password')
  .then(response => console.log('Success!'))
  .catch(error => console.error('Error:', error.message));

// Get students
api.getStudents()
  .then(response => {
    console.log('Students:', response.data);
  })
  .catch(error => console.error('Error:', error.message));

// Record attendance
api.post('/attendance', {
  student_id: 1,
  date: '2024-01-22',
  status: 'present'
})
  .then(response => console.log('Attendance recorded'))
  .catch(error => console.error('Error:', error.message));
</script>
```

### Option 2: Using Fetch Directly

```javascript
// Login
fetch('http://localhost:3000/api/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'password'
  })
})
.then(res => res.json())
.then(data => {
  localStorage.setItem('auth_token', data.data.token);
  console.log('Logged in!');
})
.catch(error => console.error('Error:', error));

// Get students (with auth)
fetch('http://localhost:3000/api/students', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
  }
})
.then(res => res.json())
.then(data => console.log('Students:', data.data))
.catch(error => console.error('Error:', error));
```

---

## 📋 Available API Endpoints

### Authentication
```
POST   /api/auth/login          - Login
POST   /api/auth/logout         - Logout
GET    /api/auth/me             - Current user
```

### Students
```
GET    /api/students            - List all
GET    /api/students/{id}       - Get one
POST   /api/students            - Create
PUT    /api/students/{id}       - Update
DELETE /api/students/{id}       - Delete
```

### Attendance
```
GET    /api/attendance          - List all
GET    /api/attendance/{id}     - Get one
POST   /api/attendance          - Record
PUT    /api/attendance/{id}     - Update
DELETE /api/attendance/{id}     - Delete
GET    /api/attendance/reports  - Reports
```

### Clubs
```
GET    /api/clubs               - List all
GET    /api/clubs/{id}          - Get one
POST   /api/clubs               - Create
PUT    /api/clubs/{id}          - Update
DELETE /api/clubs/{id}          - Delete
```

### Dashboard & Analytics
```
GET    /api/dashboard/summary   - Dashboard
GET    /api/analytics/reports   - Analytics
```

---

## 🔑 Key Files

| File | Purpose |
|------|---------|
| `frontend/server.js` | Express server with proxy |
| `frontend/config.js` | API client configuration |
| `frontend/package.json` | Dependencies |
| `frontend/.env` | Environment variables |
| `INTEGRATION_SETUP_GUIDE.md` | Full setup instructions |
| `FRONTEND_INTEGRATION_COMPLETE.md` | Integration summary |

---

## 🛠️ Common Tasks

### Test API Connection
```bash
# From your browser or using curl
curl http://localhost:8000/api/health
curl http://localhost:3000/health
```

### View API Documentation
```
Open: http://localhost:8000/docs
(Interactive Swagger UI)
```

### Clear Authentication
```javascript
localStorage.removeItem('auth_token');
localStorage.removeItem('refresh_token');
```

### Enable Debug Mode
Edit `frontend/.env`:
```
DEBUG=true
```

---

## 🆘 Troubleshooting

### "Cannot connect to API"
- ✓ Backend running on port 8000?
- ✓ Frontend running on port 3000?
- ✓ Check `.env` files have correct URLs

### "CORS Error"
- ✓ Ensure `http://localhost:3000` is in `ALLOWED_ORIGINS` in backend `.env`
- ✓ Clear browser cache
- ✓ Try incognito/private window

### "401 Unauthorized"
- ✓ User not logged in
- ✓ Token expired or invalid
- ✓ Check `Authorization` header format

### Port Already in Use
```bash
# Windows - kill process on port
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

---

## 📚 Frontend Sections

- **Homepage** - `/` 
- **Attendance** - `/attendance`
- **Dashboard** - `/dashboard`
- **Clubs** - `/clubs`
- **Events** - `/events`
- **Timetable** - `/timetable`

---

## 🔐 Authentication Flow

1. User enters credentials on login page
2. Frontend sends to `/api/auth/login`
3. Backend returns JWT token
4. Frontend stores token in `localStorage`
5. All subsequent requests include token in header: `Authorization: Bearer <token>`
6. Backend validates token on each request

---

## 📖 Full Documentation

For detailed information, see:
- `INTEGRATION_SETUP_GUIDE.md` - Complete setup guide
- `FRONTEND_INTEGRATION.md` - API documentation
- `FRONTEND_INTEGRATION_COMPLETE.md` - Integration summary

---

## ✨ Next Steps

1. ✅ Install dependencies: `npm install`
2. ✅ Start both servers
3. ✅ Test login flow
4. ✅ Update HTML pages to call APIs
5. ✅ Add form validation
6. ✅ Deploy to production

---

**Status**: Integration Complete ✅  
**Date**: January 22, 2026  
**Environment**: Ready for Development
