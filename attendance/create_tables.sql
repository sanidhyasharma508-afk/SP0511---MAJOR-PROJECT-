-- SQL schema for QR-based attendance system
-- Run this in your MySQL (localhost) to create the database/tables

CREATE DATABASE IF NOT EXISTS campus_automation CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE campus_automation;

-- Students table
CREATE TABLE IF NOT EXISTS students (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(191) NOT NULL,
  roll_no VARCHAR(64) NOT NULL UNIQUE
);

-- Sessions table stores the token with expiry
CREATE TABLE IF NOT EXISTS attendance_sessions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  token VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL
);

-- Attendance records
CREATE TABLE IF NOT EXISTS attendance_records (
  id INT AUTO_INCREMENT PRIMARY KEY,
  student_id INT NOT NULL,
  session_id INT NOT NULL,
  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
  UNIQUE KEY uniq_student_session (student_id, session_id)
);

-- Example: insert some students (optional)
INSERT IGNORE INTO students (name, roll_no) VALUES
('Alice Example', 'R001'),
('Bob Example', 'R002');
