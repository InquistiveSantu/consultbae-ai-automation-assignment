#!/usr/bin/env python3
"""
Database Schema Migration Helper for Task 3 Audio Submissions
ConsultBae AI Automation Assignment

Adds the AUDIO_SUBMISSIONS table to database/consultbae.db without altering
or recreating existing PERSONS or SOURCE_RECORDS tables.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "consultbae.db")

def init_audio_db():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database file not found at '{DB_PATH}'. Please run Phase 2 entity matching first.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Checking database schema for AUDIO_SUBMISSIONS table...")

    # Create AUDIO_SUBMISSIONS table if not exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS AUDIO_SUBMISSIONS (
        id TEXT PRIMARY KEY,
        person_id TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        duration_seconds REAL NOT NULL,
        sample_rate_hz INTEGER NOT NULL,
        bitrate_kbps REAL NOT NULL,
        loudness_lufs REAL NOT NULL,
        file_size_bytes INTEGER NOT NULL,
        mime_type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (person_id) REFERENCES PERSONS(id) ON DELETE CASCADE
    );
    """)

    # Create index for person_id lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audio_person ON AUDIO_SUBMISSIONS(person_id);")

    conn.commit()
    conn.close()
    print("AUDIO_SUBMISSIONS table verified/created successfully.")

if __name__ == "__main__":
    init_audio_db()
