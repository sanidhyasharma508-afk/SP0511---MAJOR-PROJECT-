import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

c.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT,
    username TEXT,
    password TEXT
)
""")

c.execute("""
CREATE TABLE sessions (
    session_id TEXT,
    teacher_id TEXT,
    lat REAL,
    lon REAL,
    radius INTEGER,
    expiry INTEGER,
    active INTEGER
)
""")

c.execute("""
CREATE TABLE attendance (
    student_id TEXT,
    session_id TEXT,
    time DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Sample users
c.execute("INSERT INTO users VALUES (NULL,'teacher','T101','1234')")
c.execute("INSERT INTO users VALUES (NULL,'student','S201','1234')")

conn.commit()
conn.close()

print("Database created successfully")