"""
Secure Admin Account Provisioning Script
Usage:
    python -m backend.scripts.create_admin --username <user> --email <email> --password <pwd>
Or set environment variables:
    ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD
"""

import sys
from pathlib import Path

# Ensure repository root is on sys.path when executed directly as a script
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


import argparse
import os
import sys
from backend.database import SessionLocal, engine, Base
from backend.models.user import User
from backend.core.auth import hash_password


def create_admin(username: str, email: str, password: str, full_name: str = "System Administrator"):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing:
            print(f"[ERROR] User with username '{username}' or email '{email}' already exists.")
            return False

        admin_user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role="admin",
            is_active=True,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"[SUCCESS] Admin user '{username}' successfully created with ID {admin_user.id}.")
        return True
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Provision an initial administrator account.")
    parser.add_argument("--username", default=os.getenv("ADMIN_USERNAME"), help="Admin username")
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL"), help="Admin email")
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD"), help="Admin password")
    parser.add_argument("--full-name", default=os.getenv("ADMIN_FULL_NAME", "System Administrator"), help="Full name")

    args = parser.parse_args()

    username = args.username or input("Enter admin username: ").strip()
    email = args.email or input("Enter admin email: ").strip()
    password = args.password or input("Enter admin password: ").strip()

    if not username or not email or not password:
        print("[ERROR] Username, email, and password are all required.")
        sys.exit(1)

    if len(password) < 8:
        print("[ERROR] Password must be at least 8 characters.")
        sys.exit(1)

    success = create_admin(username, email, password, args.full_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
