#!/usr/bin/env python3
"""
Application Launcher Script for Task 3 Audio Collection App
ConsultBae AI Automation Assignment

Verifies database schema and launches Uvicorn ASGI web server on http://localhost:8000
"""

import os
import sys
import uvicorn

# Dynamically locate project root (parent directory of scripts/)
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from init_audio_db import init_audio_db

def main():
    print("=========================================================")
    print("LAUNCHING CONSULTBAE AUDIO COLLECTION WEB APPLICATION")
    print("=========================================================")
    
    # 1. Initialize AUDIO_SUBMISSIONS table in database/consultbae.db
    init_audio_db()
    
    print("\nStarting Uvicorn web server...")
    print("-> Web App URL:   http://127.0.0.1:8000")
    print("-> OpenAPI Docs:  http://127.0.0.1:8000/docs")
    print("Press Ctrl+C to stop the server.\n")
    
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, app_dir=PROJECT_ROOT)

if __name__ == "__main__":
    main()

