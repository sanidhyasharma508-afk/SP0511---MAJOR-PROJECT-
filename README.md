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

## 🚀 Quick Start Guide

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

> **Note on Security:** For local development, safe default values are provided. For production deployment, set `ENV=production` and generate a cryptographically strong `SECRET_KEY` (minimum 32 characters) using:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

### 4. Database Initialization & Seeding

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

### 6. Frontend Setup & Startup

In a separate terminal:

```bash
cd frontend
npm install
npm start
```

- **Frontend Portal:** [http://localhost:3000](http://localhost:3000)

---

## 🧪 Running Automated Tests

### Backend Test Suite (Pytest)

Run all 145 backend security, API, and authorization tests:

```bash
# Run tests with summary
python -m pytest tests/ -v

# Run tests in quiet mode
python -m pytest tests/ -q
```

### Frontend Test Suite (Node.js Test Runner)

Run all 16 frontend security, token management, and DOM sanitation tests:

```bash
cd frontend
npm test
```

---

## 👥 Default Development & Test Accounts

When running in development or testing mode, `backend/seed_data.py` provisions the following development accounts:

| Role | Username | Password | Linked Student / Identity | Scope & Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `admin123` | System Administrator | Full administrative privileges, user creation, risk audit, complaint resolution |
| **Faculty / Staff** | `staff1` | `staff123` | Staff Member (ID: 2) | Generate QR attendance sessions, manage clubs & events, record subject attendance |
| **Faculty / Staff** | `staff2` | `staff123` | Second Faculty (ID: 4) | Scoped to own sessions and subjects |
| **Student** | `student1` | `student123` | Alex Johnson (`21BCS101`, ID: 1) | Student dashboard, mark own QR attendance, study tasks, submit complaints, view schedule |

---

## 🛡️ Security Architecture & Hardening Highlights

1. **Role-Based Access Control (RBAC):** Backend routes verify user role and linked entity ownership via FastAPI dependencies (`get_current_user`, `require_role`).
2. **Anti-Impersonation Student Isolation:** Students can only read and mutate their own attendance, risk scores, study tasks, and complaints. Attempts to supply mismatched `student_id` or `roll_number` result in `403 Forbidden`.
3. **Cryptographic QR Attendance Hardening:**
   - Every QR code generates a session-specific cryptographic hash tied to a geofence and expiration window.
   - Placeholder verification values (`hash_placeholder`, `manual_entry`, `demo_scan`) and empty hashes are rejected.
   - Duplicate attendance scans are rejected at both application and database constraint levels.
4. **JWT Security & Token Invalidation:**
   - Strict algorithm (`HS256`) and signature validation.
   - Secret key complexity enforcement (minimum 32 characters in production).
   - In-memory and persistent token blacklist for immediate logout invalidation.
   - CORS origin enforcement prevents wildcard origins with credentials in production.
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
│   ├── index.html          # Single-page application entrypoint
│   └── server.js           # Express.js frontend gateway & proxy
├── tests/                  # Pytest test suite (145 tests covering all domains)
├── .env.example            # Environment configuration template
├── pyproject.toml          # Project metadata & test configuration
├── pytest.ini              # Pytest settings
├── requirements.txt        # Python dependency manifest
└── README.md               # Documentation
```
