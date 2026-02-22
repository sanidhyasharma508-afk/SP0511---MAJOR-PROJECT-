from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# 1. Database URL fetch karna
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# 2. Render/Postgres Fix: SQLAlchemy 1.4+ ko "postgresql://" chahiye hota hai 
# Jabki Render "postgres://" provide karta hai.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. SQLite-specific arguments
connect_args = {}
if "sqlite" in DATABASE_URL:
    connect_args = {"check_same_thread": False}

# 4. Engine create karna
engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args, 
    echo=os.getenv("SQL_ECHO", "False").lower() == "true"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()