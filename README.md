# Campus Automation System (MARVEL)

The Campus Automation System (MARVEL) is a full-stack campus management platform designed for universities and colleges. It integrates role-based authentication, student profiles, timetable and schedule management, academic risk analysis, complaint handling, club and event lifecycles, and cryptographic QR-based attendance tracking with anti-impersonation safeguards.

---

## 🏗️ Tech Stack

- **Backend:** Python 3.10+ (tested on Python 3.13), FastAPI, SQLAlchemy ORM, SQLite (PostgreSQL compatible)
- **Security:** JWT authentication (HS256), bcrypt password hashing, role-based access control (RBAC), anti-tampering QR tokens
- **Frontend Gateway:** Node.js (v18+), Express.js reverse proxy
- **Frontend Client:** HTML5, CSS3, vanilla modern JavaScript (ES6+), DOMPurify / DOMUtils XSS sanitization
- **Testing:** Pytest, pytest-asyncio, HTTPX (backend) & Node.js native test runner (frontend)

---

## 📋 Prerequisites

Before setting up the project, ensure you have the following installed:

1. **Python 3.10 to 3.13** (`python --version`)
2. **Node.js v18 or later** (`node --version`) and **npm** (`npm --version`)
3. **Git** (`git --version`)

---

## 🚀 Quick Start Guide (Development)

### 1. Clone the Repository

```bash
git clone https://github.com/sanidhyasharma508-afk/SP0511---MAJOR-PROJECT-.git
cd SP0511---MAJOR-PROJECT-
```

### 2. Backend Setup & Virtual Environment

#### Windows PowerShell:
```powershell
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install all Python dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### macOS / Linux / Git Bash:
```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Upgrade pip and install all Python dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the example environment configuration:

#### Windows PowerShell:
```powershell
Copy-Item .env.example .env
```

#### macOS / Linux:
```bash
cp .env.example .env
```

### 4. Database Initialization & Seeding (Development Only)

Initialize database tables and seed test accounts and sample campus data:

```bash
python backend/seed_data.py
```

### 5. Running the Backend Server

Start the FastAPI application with Uvicorn:

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

- **Interactive API Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative API Docs (ReDoc):** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 6. Frontend Gateway & Client Startup

In a separate terminal:

```bash
cd frontend
npm install
npm start
```

- **Frontend Portal:** [http://localhost:3000](http://localhost:3000)

---

## 🏭 Production Deployment Guide

When deploying the Campus Automation System to a production or staging server, adhere to the following configuration guidelines to ensure strict fail-closed security.

### 1. Production Environment Variables

Create a dedicated `.env` file containing explicit production values:

```ini
# Environment mode: MUST be set to production
ENV=production

# Application Debugging: Guaranteed False in production
DEBUG=False

# Cryptographic Secret Key (HS256)
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
# Must be at least 32 characters long. All placeholder secrets are rejected.
SECRET_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

# CORS Configuration
# Must explicitly list frontend origins. Wildcard '*' is rejected in production.
ALLOWED_ORIGINS=https://campus.yourinstitution.edu,https://admin.yourinstitution.edu

# Database Connection URL
# For production scale and concurrency, PostgreSQL is strongly recommended:
DATABASE_URL=postgresql://dbuser:StrongPassword@db-host:5432/campus_automation

# Gateway Proxy Configuration (for Express frontend gateway)
PORT=3000
BACKEND_URL=http://127.0.0.1:8000
```

### 2. Provisioning Initial Administrator Accounts

In production, automatic development seeding (`seed_data.py` and `seed_default_users`) is **completely disabled**. The application will **never** create default demo credentials (`admin123`, `staff123`, `student123`).

To provision initial administrator accounts safely without echoing passwords to terminal logs or command history:

#### Interactive Provisioning (Masked Password Prompt):
```bash
python backend/scripts/create_admin.py --username sysadmin --email sysadmin@institution.edu
# Prompts securely: Enter admin password: (hidden)
```

#### Automated / CI Provisioning via Environment Variables:
```bash
ADMIN_USERNAME=sysadmin ADMIN_EMAIL=sysadmin@institution.edu ADMIN_PASSWORD=StrongSecretPassword123! python backend/scripts/create_admin.py
```

- Enforces minimum 8-character password length.
- Hashes password using bcrypt.
- Detects and rejects duplicate usernames or emails.

### 3. Database Architecture & Engine Considerations

- **SQLite (Default / Local / Single-Worker):**
  - Stored in `campus_automation.db` with foreign key enforcement (`PRAGMA foreign_keys=ON`).
  - Relative paths (`sqlite:///./campus_automation.db`) are automatically resolved to absolute paths relative to the repository root.
  - **Limitation:** SQLite uses database-level file locks on writes. It is **not** suitable for multi-worker ASGI processes (e.g., `gunicorn -w 4`) or multi-instance load-balanced containers due to `sqlite3.OperationalError: database is locked`.
- **PostgreSQL (Recommended for Production):**
  - Set `DATABASE_URL=postgresql://user:password@host:port/database_name`.
  - Supports high concurrency, connection pooling, and multi-instance scaling.
  - Legacy `postgres://` connection strings are automatically normalized to `postgresql://`.
- **Schema Migrations:**
  - `backend/seed_data.py` provides `ensure_schema()` which creates tables and performs non-destructive column/index migrations automatically upon startup.

### 4. Running Production ASGI Server (Gunicorn + Uvicorn Workers)

For Linux / containerized production environments:

```bash
gunicorn backend.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log
```

---

## 🧪 Running Automated Tests

### Backend Test Suite (Pytest)

Run all 177 backend security, API, authorization, and production-readiness tests:

```bash
# Run full suite
python -m pytest tests/ -v

# Run with concise output
python -m pytest tests/ -q
```

### Frontend Test Suite (Node.js Test Runner)

Run all 16 frontend security, token management, and DOM sanitation tests:

```bash
cd frontend
npm test
```

---

## 👥 Default Development & Test Accounts (Development Mode Only)

When running strictly in development or testing mode (`ENV=development`), `backend/seed_data.py` provisions initial development accounts for testing:

| Role | Username | Password | Linked Student / Identity | Scope & Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | System Administrator | Full administrative privileges, user creation, risk audit, complaint resolution |
| **Faculty / Staff** | `staff1` | `staff123` | Staff Member (ID: 2) | Generate QR attendance sessions, manage clubs & events, record subject attendance |
| **Faculty / Staff** | `staff2` | `staff123` | Second Faculty (ID: 4) | Scoped to own sessions and subjects |
| **Student** | `student1` | `student123` | Alex Johnson (`21BCS101`, ID: 1) | Student dashboard, mark own QR attendance, study tasks, submit complaints, view schedule |

> ⚠️ **Notice:** These accounts are only seeded in development. Production environments require provisioning via `create_admin.py`.

---

## 🛡️ Security Architecture & Hardening Highlights

1. **Production Configuration Validation:**
   - Startup fails closed if `SECRET_KEY` is missing, short (<32 chars), or matches known placeholder strings.
   - Startup fails closed if `ALLOWED_ORIGINS` contains wildcard `*` while credentials are enabled.
   - `DEBUG` mode is strictly forced to `False` in production.
2. **Role-Based Access Control (RBAC):** Backend routes verify user role and linked entity ownership via FastAPI dependencies (`get_current_user`, `require_role`).
3. **Anti-Impersonation Student Isolation:** Students can only read and mutate their own attendance, risk scores, study tasks, and complaints. Attempts to supply mismatched `student_id` or `roll_number` result in `403 Forbidden`.
4. **Cryptographic QR Attendance Hardening:**
   - Every QR code generates a session-specific cryptographic hash tied to a geofence and expiration window.
   - Placeholder verification values (`hash_placeholder`, `manual_entry`, `demo_scan`) and empty hashes are strictly rejected.
   - Duplicate attendance scans are rejected at both application and database constraint levels.
5. **Frontend XSS Prevention:**
   - Input sanitization via `DOMUtils.escapeHtml` across all dynamic views (dashboard analytics, schedules, announcements, club rosters).
   - Safe URL sanitization prevents `javascript:` URI injection.
   - Tokens stored in `localStorage` without exposing them in query parameters or console logs.

---

## 📁 Repository Structure

```
├── backend/
│   ├── ai/                 # AI agents & RAG pipelines
│   ├── core/               # Auth, security, config, RBAC, logging, event bus
│   ├── models/             # SQLAlchemy ORM models (User, Student, Attendance, etc.)
│   ├── routes/             # FastAPI APIRouters (auth, students, attendance, risk, etc.)
│   ├── schemas/            # Pydantic request & response schemas
│   ├── scripts/            # Admin creation and maintenance scripts
│   ├── main.py             # FastAPI entrypoint and middleware assembly
│   ├── database.py         # SQLAlchemy engine & session dependency
│   └── seed_data.py        # Database schema migrations & development seeder
├── frontend/
│   ├── js/                 # Vanilla JavaScript client modules (auth, dashboard, qr)
│   ├── styles/             # Application stylesheets
│   ├── test/               # Node.js frontend tests
│   ├── index.html          # Single-Page Application entrypoint
│   └── server.js           # Express.js frontend gateway & proxy
├── tests/                  # Pytest test suite (177 tests covering all domains)
│   ├── test_production_readiness.py  # Production configuration & deployment tests
│   └── ...
├── .env.example            # Environment configuration template
├── pyproject.toml          # Project metadata & test configuration
├── pytest.ini              # Pytest settings
├── requirements.txt        # Python dependency manifest
└── README.md               # Documentation
```
