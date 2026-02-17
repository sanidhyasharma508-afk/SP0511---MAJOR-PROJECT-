# Phase 5: Scaling, Security & Optimization 🚀

## Overview

Phase 5 completes the Campus Automation Backend with enterprise-grade security, optimization, and scalability features. The system now includes:

- **JWT Authentication** with token lifecycle management
- **Role-Based Access Control (RBAC)** with 4 role levels and 18 permissions
- **Comprehensive Logging** with structured JSON logs
- **Caching Layer** with Redis support
- **Background Task Queue** for async operations
- **Task Scheduler** for periodic tasks
- **Environment-Aware Configuration** for dev/test/prod
- **Performance Monitoring** with metrics collection

## New Components Added

### 1. Authentication Module (`backend/core/auth.py`)

**Features:**
- JWT token creation (access + refresh tokens)
- Password hashing with bcrypt
- Token validation and error handling
- Token blacklisting for logout
- Configurable token expiry times

**Usage:**
```python
from backend.core.auth import create_tokens, decode_token

# Create tokens
tokens = create_tokens(user_id=1, username="student1", role=Role.STUDENT)
# Result: {"access_token": "...", "refresh_token": "...", "expires_in": 1800}

# Decode token
token_data = decode_token(access_token)
# Result: TokenData(sub="student1", user_id=1, role="student", ...)
```

### 2. Authorization Module (`backend/core/rbac.py`)

**Role Hierarchy:**
- **Admin** (Level 3) - Full access to all resources
- **Staff** (Level 2) - Create/update most resources
- **Student** (Level 1) - Read own resources, file complaints
- **Guest** (Level 0) - View reports only

**Permissions (18 total):**
- VIEW_STUDENT, CREATE_STUDENT, UPDATE_STUDENT, DELETE_STUDENT
- MARK_ATTENDANCE, VIEW_ATTENDANCE, EDIT_ATTENDANCE
- FILE_COMPLAINT, VIEW_COMPLAINT, RESOLVE_COMPLAINT
- SCHEDULE_MANAGEMENT, RISK_ASSESSMENT
- VIEW_ANALYTICS, EXPORT_ANALYTICS
- MANAGE_AGENTS, VIEW_AGENTS
- CREATE_CLUB, MANAGE_CLUBS, VIEW_REPORTS

**Usage:**
```python
from fastapi import Depends
from backend.core.rbac import require_admin, require_role, has_permission, Role

# Require admin role
@router.get("/admin-data", dependencies=[Depends(require_admin)])
def admin_only():
    return {"data": "admin"}

# Require specific role
@router.post("/create", dependencies=[Depends(require_role(Role.STAFF))])
def create_item(item: Item):
    return item

# Permission-based
from backend.core.rbac import has_permission, Permission

@router.post("/file-complaint", dependencies=[Depends(has_permission(Permission.FILE_COMPLAINT))])
def file_complaint(complaint: Complaint):
    return complaint
```

### 3. Configuration Module (`backend/core/config.py`)

**Features:**
- Pydantic BaseSettings for type-safe config
- Environment variable support with .env files
- Environment-specific settings (dev/test/prod)
- Production validation
- 40+ configurable options

**Usage:**
```python
from backend.core.config import settings

print(settings.DEBUG)  # True in dev, False in prod
print(settings.DATABASE_URL)  # Loaded from .env
print(settings.is_production)  # True if ENV=production

# Access nested config
settings.CORS_ORIGINS  # List of allowed origins
settings.ACCESS_TOKEN_EXPIRE_MINUTES  # JWT expiry
```

### 4. Logging Module (`backend/core/logging.py`)

**Features:**
- Structured JSON logging to files
- Console logging with formatting
- Log rotation (10MB max, keeps 10 backups)
- Request logging middleware
- Performance monitoring
- Audit trail for security events

**Usage:**
```python
from backend.core.logging import get_logger

logger = get_logger("module_name")

# Log events
logger.log_event("user_login", level="INFO", user_id=123, username="john")

# Log errors
logger.log_error("operation_failed", exception, operation="delete_student")

# Log requests
logger.log_request("GET", "/api/v1/students", 200, user_id=123)

# Log performance
logger.log_performance("database_query", duration=0.234, query="SELECT ...")

# Use decorator
from backend.core.logging import monitor_operation

@monitor_operation("expensive_computation")
async def compute_analytics():
    # Operation timing automatically logged
    return analytics_data
```

### 5. Caching Module (`backend/core/caching.py`)

**Features:**
- Pluggable cache backend (in-memory or Redis)
- Automatic TTL expiration
- JSON and pickle serialization
- Function result caching decorator
- Cache invalidation decorator

**Usage:**
```python
from backend.core.caching import cached, cache_manager

# Cache function results
@cached(prefix="user_profile", ttl=600)
async def get_user_profile(user_id: int):
    return await db.get_user(user_id)

# Manual cache operations
await cache_manager.set("key", value, ttl=300)
value = await cache_manager.get("key")
await cache_manager.delete("key")

# Clear specific pattern
await cache_manager.clear()
```

### 6. Background Tasks Module (`backend/core/background_tasks.py`)

**Features:**
- Async task queue with worker pool
- Task status tracking
- Periodic task scheduling
- Task history with retention
- Background task decorator

**Usage:**
```python
from backend.core.background_tasks import submit_background_task, background_task, task_queue

# Submit background task
task_id = await submit_background_task("send_email", send_email_func, user_id=123)

# Check task status
status = task_queue.get_task_status(task_id)

# Use decorator
@background_task(name="generate_report")
async def generate_report(student_id: int):
    # Runs in background
    return report_data

# Schedule periodic tasks
from backend.core.background_tasks import scheduler

scheduler.schedule(
    "cleanup_old_logs",
    cleanup_logs,
    interval=3600,  # Every hour
    description="Clean up logs older than 30 days"
)
```

## Authentication Endpoints

### POST `/api/v1/auth/login`
```json
{
  "username": "student1",
  "password": "password123"
}
```
Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "expires_in": 1800,
  "token_type": "bearer",
  "user_id": 3,
  "role": "student"
}
```

### POST `/api/v1/auth/register`
```json
{
  "username": "newstudent",
  "email": "student@campus.edu",
  "password": "SecurePass123",
  "full_name": "New Student",
  "role": "student"
}
```

### POST `/api/v1/auth/refresh`
```json
{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### POST `/api/v1/auth/logout`
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### POST `/api/v1/auth/change-password`
```json
{
  "old_password": "OldPass123",
  "new_password": "NewSecurePass456",
  "confirm_password": "NewSecurePass456"
}
```

### GET `/api/v1/auth/profile`
Returns current user profile.

### GET `/api/v1/auth/verify`
Verifies if token is valid.

## Test Accounts

| Username | Password | Role | Email |
|----------|----------|------|-------|
| admin | admin123 | admin | admin@campus.edu |
| staff1 | staff123 | staff | staff1@campus.edu |
| student1 | student123 | student | student1@campus.edu |

## Configuration

### Setup Development Environment

1. **Copy .env template:**
```bash
cp .env.template .env
```

2. **Configure for development:**
```env
ENV=development
DEBUG=True
SECRET_KEY=dev-secret-key-not-for-production
ENABLE_CACHING=True
ENABLE_BACKGROUND_TASKS=True
```

3. **Setup Redis (optional but recommended):**
```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or install locally
# Ubuntu/Debian: sudo apt-get install redis-server
# macOS: brew install redis
```

4. **Run the server:**
```bash
python -m uvicorn backend.main:app --reload
```

### Production Configuration

1. **Set environment variables:**
```env
ENV=production
DEBUG=False
SECRET_KEY=your-long-random-production-key
DATABASE_URL=postgresql://user:password@prod-db:5432/campus_automation
REDIS_URL=redis://prod-redis:6379/0
```

2. **Validate configuration:**
```bash
python -c "from backend.core.config import settings; settings.validate_production_settings()"
```

3. **Run with Gunicorn:**
```bash
gunicorn backend.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Security Best Practices

### 1. Secret Management
- **Never commit secrets** to version control
- Use `.env.template` for defaults
- Use `.gitignore` to exclude `.env`
- Rotate SECRET_KEY regularly

### 2. Password Security
- Minimum 6 characters for login
- Minimum 8 characters for registration
- Always hashed with bcrypt
- Change password endpoint available

### 3. Token Management
- Access tokens expire after 30 minutes
- Refresh tokens expire after 7 days
- Tokens can be blacklisted for logout
- Token validation on every protected endpoint

### 4. Role-Based Access
- Always use decorators for authorization
- Audit logging for sensitive operations
- Permission-based access for fine-grained control
- Default to deny (whitelist approach)

### 5. Database Security
- Use environment-specific credentials
- PostgreSQL recommended for production
- Connection pooling enabled
- SQL injection protected (via SQLAlchemy ORM)

## Monitoring & Observability

### Request Logging
All HTTP requests are logged with:
- Method, path, status code
- Duration (for slow requests > 1s)
- User ID if authenticated
- Timestamp

### Performance Monitoring
Operations > 1 second duration are logged:
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "INFO",
  "operation": "generate_analytics_report",
  "duration_ms": 1234,
  "status": "success"
}
```

### Health Check
**GET `/health/full`**
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "status": "healthy",
  "version": "5.0.0",
  "environment": "development",
  "components": {
    "api": "running",
    "database": "running",
    "cache": {
      "enabled": true,
      "backend": "InMemoryCacheBackend"
    },
    "background_tasks": {
      "enabled": true,
      "queue_size": 0,
      "workers": 5,
      "pending": 0,
      "running": 0,
      "completed": 15
    },
    "scheduler": {
      "running": true,
      "tasks_count": 3
    }
  }
}
```

## Logging Output

### File Logging (JSON format)
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "INFO",
  "logger": "auth_routes",
  "message": "login_successful",
  "module": "auth",
  "function": "login",
  "line": 145,
  "user_id": 3,
  "username": "student1",
  "role": "student"
}
```

### Console Logging
```
2024-01-15 10:30:45,123 - auth_routes - INFO - login_successful
```

## Integration with Existing Endpoints

### Protecting Routes

**Before (Phase 4):**
```python
@router.get("/api/v1/students")
def get_students():
    return students
```

**After (Phase 5):**
```python
from backend.core.rbac import require_role, Role

@router.get("/api/v1/students")
def get_students(current_user: AuthContext = Depends(require_role(Role.STAFF, Role.ADMIN))):
    return students
```

### Adding Audit Logging

**Before (Phase 4):**
```python
@router.post("/api/v1/students")
def create_student(student: Student):
    db.add(student)
    return student
```

**After (Phase 5):**
```python
from backend.core.logging import get_logger

logger = get_logger("students")

@router.post("/api/v1/students")
def create_student(
    student: Student,
    current_user: AuthContext = Depends(require_role(Role.STAFF))
):
    db.add(student)
    logger.log_event(
        "student_created",
        level="INFO",
        created_by=current_user.user_id,
        student_id=student.id
    )
    return student
```

## Docker Support (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "backend.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENV=production
      - DATABASE_URL=postgresql://user:password@postgres:5432/campus_automation
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=campus_automation
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## Performance Tuning

### Database Optimization
- Connection pooling: `POOL_SIZE=5`
- Max overflow: `POOL_MAX_OVERFLOW=10`
- Use indexes on frequently queried columns
- Monitor with `DATABASE_ECHO=False` in production

### Caching Strategy
- Cache user profiles (TTL: 600s)
- Cache analytics reports (TTL: 3600s)
- Cache role permissions (TTL: 86400s)
- Invalidate on write operations

### Background Tasks
- Set worker count based on CPU cores
- Use periodic cleanup for old tasks
- Monitor queue depth for bottlenecks

## Troubleshooting

### Authentication Issues
1. **"Invalid username or password"**
   - Check credentials against test accounts
   - Verify password hashing

2. **"Token has expired"**
   - Use refresh token endpoint to get new access token
   - Check system clock synchronization

3. **"Insufficient permissions"**
   - Verify user role assignment
   - Check permission mapping for endpoint

### Performance Issues
1. Check slow queries in logs
2. Monitor cache hit rates
3. Verify background task queue depth
4. Profile database connections

### Logging Issues
1. Ensure logs directory exists: `mkdir -p logs/`
2. Check file permissions: `chmod 755 logs/`
3. Verify LOG_FILE path in .env

## Next Steps

Phase 5 is complete. The system now has:
✅ Complete authentication system
✅ Role-based access control
✅ Security logging and auditing
✅ Performance monitoring
✅ Caching infrastructure
✅ Background task support
✅ Production-ready configuration

### Future Enhancements
- [ ] API rate limiting
- [ ] Request signing for webhooks
- [ ] Advanced audit logging
- [ ] Machine learning model integration
- [ ] Real-time notifications (WebSockets)
- [ ] Advanced analytics dashboard
- [ ] Mobile app support
- [ ] Multi-tenant support

---

**Campus Automation Backend - Phase 5 Complete** 🎉
