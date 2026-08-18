#!/usr/bin/env python3
"""
Task 3: Audio Collection Web Application Server (FastAPI)
ConsultBae AI Automation Assignment

Provides REST API endpoints for candidate lookup, browser audio recording submission,
file upload fallback, audio metadata extraction (Duration, Sample Rate, Bitrate, LUFS Loudness),
and submission list reporting connected to SQLite database/consultbae.db.
"""

import os
import re
import io
import time
import json
import sqlite3
import tempfile
import numpy as np
import soundfile as sf
import pyloudnorm as pysn
from datetime import datetime
from pydub import AudioSegment

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Path definitions
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "consultbae.db")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "app", "static")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="ConsultBae Audio Collection App", version="1.0.0")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_phone(phone_str):
    if not phone_str:
        return ""
    digits = re.sub(r'\D', '', str(phone_str))
    if len(digits) == 11 and digits.startswith('0'):
        return digits[1:]
    elif len(digits) == 12 and digits.startswith('91'):
        return digits[2:]
    return digits

def calculate_audio_metadata(file_bytes, filename):
    """
    Extract audio metadata:
    - duration_seconds (float)
    - sample_rate_hz (int)
    - bitrate_kbps (float)
    - loudness_lufs (float via pyloudnorm EBU R128 integrated loudness)
    """
    file_size_bytes = len(file_bytes)
    ext = os.path.splitext(filename)[1].lower().replace('.', '')
    
    data = None
    rate = None
    
    # Try reading directly with soundfile
    try:
        data, rate = sf.read(io.BytesIO(file_bytes))
    except Exception:
        # Fallback to pydub for conversion to WAV PCM
        try:
            segment = AudioSegment.from_file(io.BytesIO(file_bytes))
            wav_io = io.BytesIO()
            segment.export(wav_io, format="wav")
            wav_io.seek(0)
            data, rate = sf.read(wav_io)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not extract reliable audio metadata from file '{filename}'. Format unsupported or corrupt."
            )
            
    if data is None or rate is None or rate <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Audio file '{filename}' contains invalid sample rate or empty signal data."
        )
        
    # Calculate duration
    if len(data.shape) > 1:
        num_frames = data.shape[0]
    else:
        num_frames = len(data)
        
    duration_seconds = round(float(num_frames) / float(rate), 2)
    if duration_seconds <= 0:
        raise HTTPException(status_code=400, detail="Audio duration must be greater than 0 seconds.")
        
    # Calculate bitrate (kbps)
    bitrate_kbps = round((file_size_bytes * 8.0) / (duration_seconds * 1000.0), 2)
    
    # Calculate integrated loudness in LUFS using pyloudnorm
    try:
        meter = pysn.Meter(rate) # create BS.1770 meter
        loudness_lufs = float(meter.integrated_loudness(data))
        if np.isinf(loudness_lufs) or np.isnan(loudness_lufs):
            loudness_lufs = -70.0 # Standard floor for silence
        else:
            loudness_lufs = round(loudness_lufs, 2)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not extract reliable LUFS loudness metadata from audio file: {str(e)}"
        )
        
    return {
        "duration_seconds": duration_seconds,
        "sample_rate_hz": int(rate),
        "bitrate_kbps": bitrate_kbps,
        "loudness_lufs": loudness_lufs,
        "file_size_bytes": file_size_bytes
    }

# --- REST API Endpoints ---

@app.get("/api/candidates")
def get_candidates():
    """Return existing Golden Persons for autocomplete dropdown."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, canonical_name, primary_email, primary_phone, canonical_city, is_ambiguous
        FROM PERSONS
        ORDER BY canonical_name ASC;
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(r) for r in rows]

@app.post("/api/audio/upload")
async def upload_audio(
    person_id: str = Form(None),
    name: str = Form(None),
    phone: str = Form(None),
    file: UploadFile = File(...)
):
    """
    Validate candidate identity against PERSONS table, extract audio metadata,
    save file to uploads/, and record submission in AUDIO_SUBMISSIONS.
    DOES NOT CREATE NEW PERSONS RECORDS.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    matched_person = None
    
    # 1. Look up candidate in PERSONS table
    if person_id and person_id.strip():
        cursor.execute("SELECT * FROM PERSONS WHERE id = ?;", (person_id.strip(),))
        matched_person = cursor.fetchone()
        
    if not matched_person and phone and phone.strip():
        norm_ph = normalize_phone(phone)
        if norm_ph:
            cursor.execute("SELECT * FROM PERSONS WHERE primary_phone = ?;", (norm_ph,))
            matched_person = cursor.fetchone()
            
    if not matched_person and name and name.strip():
        c_name = name.strip().lower()
        cursor.execute("SELECT * FROM PERSONS WHERE LOWER(canonical_name) = ?;", (c_name,))
        matched_person = cursor.fetchone()
        
    # Reject if candidate does not exist in PERSONS (Rule 1: Do not create new PERSONS)
    if not matched_person:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="Candidate not found in verified PERSONS database. Audio submissions must be linked to an existing candidate."
        )
        
    target_person_id = matched_person["id"]
    canonical_name = matched_person["canonical_name"]
    
    # 2. Read file bytes and calculate metadata
    contents = await file.read()
    if not contents or len(contents) == 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        
    meta = calculate_audio_metadata(contents, file.filename)
    
    # 3. Save raw file to uploads/
    timestamp_str = str(int(time.time()))
    orig_ext = os.path.splitext(file.filename)[1].lower()
    if not orig_ext:
        orig_ext = ".webm" if "webm" in (file.content_type or "") else ".wav"
        
    saved_filename = f"aud_{target_person_id}_{timestamp_str}{orig_ext}"
    saved_filepath = os.path.join(UPLOADS_DIR, saved_filename)
    rel_filepath = f"uploads/{saved_filename}"
    
    with open(saved_filepath, "wb") as f_out:
        f_out.write(contents)
        
    # 4. Generate submission ID and insert into AUDIO_SUBMISSIONS
    cursor.execute("SELECT COUNT(*) FROM AUDIO_SUBMISSIONS;")
    sub_count = cursor.fetchone()[0] + 1
    sub_id = f"AUD_{sub_count:03d}"
    now_iso = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO AUDIO_SUBMISSIONS (
            id, person_id, file_name, file_path, duration_seconds,
            sample_rate_hz, bitrate_kbps, loudness_lufs, file_size_bytes,
            mime_type, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        sub_id, target_person_id, saved_filename, rel_filepath,
        meta["duration_seconds"], meta["sample_rate_hz"], meta["bitrate_kbps"],
        meta["loudness_lufs"], meta["file_size_bytes"],
        file.content_type or "audio/wav", now_iso
    ))
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": f"Audio submission successfully linked to candidate '{canonical_name}' ({target_person_id})",
        "submission": {
            "id": sub_id,
            "person_id": target_person_id,
            "canonical_name": canonical_name,
            "file_name": saved_filename,
            "file_path": rel_filepath,
            "duration_seconds": meta["duration_seconds"],
            "sample_rate_hz": meta["sample_rate_hz"],
            "bitrate_kbps": meta["bitrate_kbps"],
            "loudness_lufs": meta["loudness_lufs"],
            "created_at": now_iso
        }
    }

@app.get("/api/audio/submissions")
def get_submissions():
    """Return all audio submissions joined with candidate profile details."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            a.id as submission_id,
            a.person_id,
            p.canonical_name,
            p.primary_phone,
            p.canonical_city,
            a.file_name,
            a.file_path,
            a.duration_seconds,
            a.sample_rate_hz,
            a.bitrate_kbps,
            a.loudness_lufs,
            a.file_size_bytes,
            a.created_at
        FROM AUDIO_SUBMISSIONS a
        JOIN PERSONS p ON a.person_id = p.id
        ORDER BY a.created_at DESC;
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(r) for r in rows]

# Static File Routes
@app.get("/uploads/{filename}")
def serve_upload(filename: str):
    file_path = os.path.join(UPLOADS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(file_path)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
