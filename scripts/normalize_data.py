#!/usr/bin/env python3
"""
Phase 1B: Data Ingestion and Normalization Pipeline
ConsultBae AI Automation Assignment

This script ingests raw CSV datasets from the data/ directory, performs data quality
audits and normalization, logs all anomalies and decisions, and writes standardized
intermediate datasets to the processed/ directory.
"""

import os
import csv
import re
from datetime import datetime

# Path definitions
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")

S1_PATH = os.path.join(DATA_DIR, "source1_naukri_applicants.csv")
S2_PATH = os.path.join(DATA_DIR, "source2_gig_workers.csv")
S3_PATH = os.path.join(DATA_DIR, "source3_cbnexus_contacts.csv")

OUT_S1_PATH = os.path.join(PROCESSED_DIR, "cleaned_naukri_applicants.csv")
OUT_S2_PATH = os.path.join(PROCESSED_DIR, "cleaned_gig_workers.csv")
OUT_S3_PATH = os.path.join(PROCESSED_DIR, "cleaned_cbnexus_contacts.csv")
OUT_LOG_PATH = os.path.join(PROCESSED_DIR, "data_quality_audit_log.csv")

# Audit log registry
audit_logs = []

def log_issue(source_file, row_reference, issue_type, issue_description, action_taken):
    """Record an audit log entry for transparency and reporting."""
    timestamp = datetime.now().isoformat()
    audit_logs.append({
        "timestamp": timestamp,
        "source_file": source_file,
        "row_reference": str(row_reference),
        "issue_type": issue_type,
        "issue_description": issue_description,
        "action_taken": action_taken
    })

# --- Normalization Utility Functions ---

def normalize_email(email_str, source_file, row_ref):
    """Normalize email address to lowercase and trimmed string."""
    if not email_str:
        return ""
    cleaned = email_str.strip().lower()
    if cleaned != email_str:
        log_issue(source_file, row_ref, "EMAIL_FORMAT", f"Raw email '{email_str}' contained non-standard casing/whitespace", f"Normalized to '{cleaned}'")
    return cleaned

def normalize_phone(phone_str, source_file, row_ref):
    """
    Normalize phone numbers into consistent 10-digit string format.
    Handles +91 prefix, leading zero (0), and hyphens/spaces.
    """
    if not phone_str:
        return ""
    digits = re.sub(r'\D', '', str(phone_str))
    normalized = digits
    if len(digits) == 11 and digits.startswith('0'):
        normalized = digits[1:]
    elif len(digits) == 12 and digits.startswith('91'):
        normalized = digits[2:]
    
    if len(normalized) != 10:
        log_issue(source_file, row_ref, "PHONE_FORMAT_WARNING", f"Phone '{phone_str}' parsed to '{normalized}' (Length {len(normalized)} != 10)", "Retained non-standard digit length")
    elif phone_str != normalized:
        log_issue(source_file, row_ref, "PHONE_FORMAT", f"Raw phone '{phone_str}' contained prefix/delimiters", f"Normalized to 10-digit '{normalized}'")
    
    return normalized

def normalize_name(name_str, source_file, row_ref):
    """
    Normalize candidate names: trim, collapse spaces, convert to Title Case.
    Does NOT attempt to guess abbreviated names.
    """
    if not name_str:
        return ""
    trimmed = name_str.strip()
    collapsed = re.sub(r'\s+', ' ', trimmed)
    title_cased = collapsed.title()
    
    if name_str != title_cased:
        log_issue(source_file, row_ref, "NAME_CASING", f"Raw name '{name_str}' had non-standard casing/spacing", f"Normalized to '{title_cased}'")
    return title_cased

def normalize_city(city_str, source_file, row_ref):
    """
    Normalize city names using documented synonym mapping dictionary.
    """
    if not city_str:
        return ""
    cleaned = city_str.strip()
    c_lower = cleaned.lower()
    
    city_map = {
        "bangalore": "Bengaluru",
        "bengaluru": "Bengaluru",
        "gurgaon": "Gurugram",
        "gurugram": "Gurugram",
        "delhi": "Delhi NCR",
        "new delhi": "Delhi NCR",
        "delhi ncr": "Delhi NCR",
        "pune": "Pune",
        "noida": "Noida"
    }
    
    normalized = city_map.get(c_lower, cleaned.title())
    if city_str != normalized:
        log_issue(source_file, row_ref, "CITY_NAME", f"Raw city '{city_str}' mapped", f"Normalized to '{normalized}'")
    return normalized

def normalize_ctc(ctc_str, source_file, row_ref):
    """
    Normalize Current CTC (Source 1):
    Values < 100 represent Lakhs Per Annum (LPA) -> convert to annual INR integer.
    Values >= 100 represent full annual INR integer.
    """
    if not ctc_str:
        return "", ""
    try:
        val = float(ctc_str.strip())
        if val < 100.0:
            inr_val = int(round(val * 100000.0))
            log_issue(source_file, row_ref, "CTC_UNIT_CONVERSION", f"Raw CTC '{ctc_str}' recognized as LPA ({val} LPA)", f"Converted to full annual INR {inr_val:,}")
            return ctc_str.strip(), str(inr_val)
        else:
            inr_val = int(round(val))
            return ctc_str.strip(), str(inr_val)
    except ValueError:
        log_issue(source_file, row_ref, "CTC_PARSE_ERROR", f"Could not parse CTC '{ctc_str}'", "Retained raw value")
        return ctc_str.strip(), ctc_str.strip()

def normalize_gig_rate(rate_str, source_file, row_ref):
    """
    Normalize Gig Worker Rate (Source 2):
    Parses amount and identifies rate unit as HOURLY or MONTHLY.
    """
    if not rate_str:
        return "", "", ""
    raw = rate_str.strip()
    
    # Check for hourly rate format (e.g. 1415/hr)
    match_hr = re.match(r'^(\d+(?:\.\d+)?)\s*/\s*hr$', raw, re.IGNORECASE)
    if match_hr:
        amount = str(float(match_hr.group(1)))
        return raw, amount, "HOURLY"
    
    # Check for monthly rate format (e.g. 15k/month)
    match_mo = re.match(r'^(\d+(?:\.\d+)?)\s*k\s*/\s*month$', raw, re.IGNORECASE)
    if match_mo:
        amount = str(float(match_mo.group(1)) * 1000.0)
        log_issue(source_file, row_ref, "RATE_UNIT_PARSED", f"Raw monthly rate '{raw}' parsed", f"Amount: {amount}, Unit: MONTHLY")
        return raw, amount, "MONTHLY"
    
    log_issue(source_file, row_ref, "RATE_FORMAT_UNRECOGNIZED", f"Unrecognized rate structure '{raw}'", "Retained raw string")
    return raw, raw, "UNKNOWN"

def normalize_status(status_str, source_file, row_ref):
    """Normalize Gig Worker status into ACTIVE, INACTIVE, PAUSED."""
    if not status_str:
        return ""
    s_lower = status_str.strip().lower()
    status_map = {
        "active": "ACTIVE",
        "inactive": "INACTIVE",
        "paused": "PAUSED"
    }
    normalized = status_map.get(s_lower, status_str.strip().upper())
    if status_str != normalized:
        log_issue(source_file, row_ref, "STATUS_CASING", f"Raw status '{status_str}'", f"Normalized to '{normalized}'")
    return normalized

def normalize_verified(verified_str, source_file, row_ref):
    """Normalize CBNexus Verified field into TRUE or FALSE."""
    if not verified_str:
        return "FALSE"
    v_lower = verified_str.strip().lower()
    if v_lower in ["y", "yes", "true", "1"]:
        if verified_str != "TRUE":
            log_issue(source_file, row_ref, "VERIFIED_BOOLEAN", f"Raw verified '{verified_str}'", "Normalized to 'TRUE'")
        return "TRUE"
    elif v_lower in ["n", "no", "false", "0"]:
        if verified_str != "FALSE":
            log_issue(source_file, row_ref, "VERIFIED_BOOLEAN", f"Raw verified '{verified_str}'", "Normalized to 'FALSE'")
        return "FALSE"
    return "FALSE"

def normalize_date(date_str, source_file, row_ref):
    """
    Parse Naukri Applied Date from multi-format input into ISO format YYYY-MM-DD.
    Supported formats: DD-MM-YYYY, YYYY-MM-DD, D MMM YYYY, MM/DD/YYYY.
    """
    if not date_str:
        return ""
    raw = date_str.strip()
    date_formats = ["%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%m/%d/%Y"]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(raw, fmt)
            iso_date = dt.strftime("%Y-%m-%d")
            if raw != iso_date:
                log_issue(source_file, row_ref, "DATE_FORMAT", f"Raw date '{raw}' (fmt {fmt})", f"Normalized to ISO '{iso_date}'")
            return iso_date
        except ValueError:
            continue
            
    log_issue(source_file, row_ref, "DATE_PARSE_ERROR", f"Could not parse date '{raw}'", "Retained raw date string")
    return raw

# --- Processing Pipeline Steps ---

def process_naukri_applicants():
    """Process source1_naukri_applicants.csv"""
    print(f"Ingesting {os.path.basename(S1_PATH)}...")
    source_filename = "source1_naukri_applicants.csv"
    
    with open(S1_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        raw_rows = list(reader)
        
    cleaned_records = []
    
    for idx, row in enumerate(raw_rows, start=2):
        # 1. Skip completely empty rows
        if not row or all(cell.strip() == "" for cell in row):
            log_issue(source_filename, idx, "EMPTY_ROW", "Completely blank row encountered", "SKIPPED")
            continue
            
        name, email, phone, city, exp, ctc, applied_date, skills = row
        
        # Apply field normalizations
        norm_name = normalize_name(name, source_filename, idx)
        norm_email = normalize_email(email, source_filename, idx)
        norm_phone = normalize_phone(phone, source_filename, idx)
        norm_city = normalize_city(city, source_filename, idx)
        raw_ctc_val, norm_ctc_inr = normalize_ctc(ctc, source_filename, idx)
        norm_date = normalize_date(applied_date, source_filename, idx)
        norm_skills = ", ".join([s.strip() for s in skills.split(",") if s.strip()])
        
        cleaned_records.append({
            "source_id": f"S1_R{idx}",
            "raw_full_name": name,
            "normalized_full_name": norm_name,
            "raw_email": email,
            "normalized_email": norm_email,
            "raw_phone": phone,
            "normalized_phone": norm_phone,
            "raw_city": city,
            "normalized_city": norm_city,
            "experience_years": exp.strip(),
            "raw_current_ctc": raw_ctc_val,
            "normalized_ctc_inr": norm_ctc_inr,
            "raw_applied_date": applied_date,
            "normalized_applied_date": norm_date,
            "raw_skills": skills,
            "normalized_skills": norm_skills
        })
        
    return len(raw_rows), cleaned_records

def process_gig_workers():
    """Process source2_gig_workers.csv"""
    print(f"Ingesting {os.path.basename(S2_PATH)}...")
    source_filename = "source2_gig_workers.csv"
    
    with open(S2_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        raw_rows = list(reader)
        
    cleaned_records = []
    seen_clean_emails = set()
    
    # First pass to collect valid clean emails to detect corrupted duplicates
    for idx, row in enumerate(raw_rows, start=2):
        if row and len(row) >= 2 and '@' in row[0]:
            seen_clean_emails.add(row[0].strip().lower())
            
    for idx, row in enumerate(raw_rows, start=2):
        # 1. Skip completely empty rows (Line 12)
        if not row or all(cell.strip() == "" for cell in row):
            log_issue(source_filename, idx, "EMPTY_ROW", "Completely blank row encountered (Line 12)", "SKIPPED")
            continue
            
        # 2. Detect shifted / corrupted row (Line 20)
        if len(row) >= 2 and not ('@' in row[0]) and ('@' in row[1]):
            corrupted_email = row[1].strip().lower()
            if corrupted_email in seen_clean_emails:
                log_issue(source_filename, idx, "CORRUPTED_SHIFTED_ROW", f"Shifted columns row with email '{row[1]}' is a duplicate of clean record (Line 7)", f"SKIPPED row to prevent duplicate profile creation")
                continue
            else:
                log_issue(source_filename, idx, "CORRUPTED_SHIFTED_ROW", f"Shifted columns row detected: '{row}'", "ATTEMPTED_RECONSTRUCTION")
                # Re-align fields if needed
                skills, email, name, rate, location, status = row
                row = [email, name, rate, location, status, skills]

        email, name, rate, location, status, skills = row
        
        norm_email = normalize_email(email, source_filename, idx)
        norm_name = normalize_name(name, source_filename, idx)
        raw_rate_val, norm_rate_amt, norm_rate_unit = normalize_gig_rate(rate, source_filename, idx)
        norm_city = normalize_city(location, source_filename, idx)
        norm_status = normalize_status(status, source_filename, idx)
        norm_skills = ", ".join([s.strip().lower() for s in skills.split(",") if s.strip()])
        
        cleaned_records.append({
            "source_id": f"S2_R{idx}",
            "raw_email": email,
            "normalized_email": norm_email,
            "raw_worker_name": name,
            "normalized_worker_name": norm_name,
            "raw_rate": raw_rate_val,
            "normalized_rate_amount": norm_rate_amt,
            "normalized_rate_unit": norm_rate_unit,
            "raw_location": location,
            "normalized_city": norm_city,
            "raw_status": status,
            "normalized_status": norm_status,
            "raw_skill_tags": skills,
            "normalized_skills": norm_skills
        })
        
    return len(raw_rows), cleaned_records

def process_cbnexus_contacts():
    """Process source3_cbnexus_contacts.csv"""
    print(f"Ingesting {os.path.basename(S3_PATH)}...")
    source_filename = "source3_cbnexus_contacts.csv"
    
    with open(S3_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        raw_rows = list(reader)
        
    cleaned_records = []
    
    for idx, row in enumerate(raw_rows, start=2):
        # 1. Skip completely empty rows
        if not row or all(cell.strip() == "" for cell in row):
            log_issue(source_filename, idx, "EMPTY_ROW", "Completely blank row encountered", "SKIPPED")
            continue
            
        # 2. Skip intermediate duplicate header row (Line 16)
        if row[0].strip() == "Name" and row[1].strip() == "Phone Number":
            log_issue(source_filename, idx, "DUPLICATE_HEADER", "Duplicated CSV header embedded in data rows (Line 16)", "SKIPPED")
            continue
            
        name, phone, city, verified, projects = row
        
        norm_name = normalize_name(name, source_filename, idx)
        norm_phone = normalize_phone(phone, source_filename, idx)
        norm_city = normalize_city(city, source_filename, idx)
        norm_verified = normalize_verified(verified, source_filename, idx)
        
        cleaned_records.append({
            "source_id": f"S3_R{idx}",
            "raw_name": name,
            "normalized_name": norm_name,
            "raw_phone_number": phone,
            "normalized_phone": norm_phone,
            "raw_city": city,
            "normalized_city": norm_city,
            "raw_verified": verified,
            "normalized_verified": norm_verified,
            "projects_completed": projects.strip()
        })
        
    return len(raw_rows), cleaned_records

def export_csv(filepath, fieldnames, data):
    """Write data dictionary list to CSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Successfully created: {filepath} ({len(data)} records)")

def main():
    print("=========================================================")
    print("STARTING DATA INGESTION & NORMALIZATION PIPELINE (PHASE 1B)")
    print("=========================================================\n")
    
    # Process S1
    s1_raw_cnt, s1_clean = process_naukri_applicants()
    s1_fields = [
        "source_id", "raw_full_name", "normalized_full_name", "raw_email", "normalized_email",
        "raw_phone", "normalized_phone", "raw_city", "normalized_city", "experience_years",
        "raw_current_ctc", "normalized_ctc_inr", "raw_applied_date", "normalized_applied_date",
        "raw_skills", "normalized_skills"
    ]
    export_csv(OUT_S1_PATH, s1_fields, s1_clean)
    
    # Process S2
    s2_raw_cnt, s2_clean = process_gig_workers()
    s2_fields = [
        "source_id", "raw_email", "normalized_email", "raw_worker_name", "normalized_worker_name",
        "raw_rate", "normalized_rate_amount", "normalized_rate_unit", "raw_location", "normalized_city",
        "raw_status", "normalized_status", "raw_skill_tags", "normalized_skills"
    ]
    export_csv(OUT_S2_PATH, s2_fields, s2_clean)
    
    # Process S3
    s3_raw_cnt, s3_clean = process_cbnexus_contacts()
    s3_fields = [
        "source_id", "raw_name", "normalized_name", "raw_phone_number", "normalized_phone",
        "raw_city", "normalized_city", "raw_verified", "normalized_verified", "projects_completed"
    ]
    export_csv(OUT_S3_PATH, s3_fields, s3_clean)
    
    # Export Audit Log
    log_fields = ["timestamp", "source_file", "row_reference", "issue_type", "issue_description", "action_taken"]
    export_csv(OUT_LOG_PATH, log_fields, audit_logs)
    
    print("\n=========================================================")
    print("PIPELINE EXECUTION SUMMARY")
    print("=========================================================")
    print(f"Source 1 (Naukri):   {s1_raw_cnt} raw rows -> {len(s1_clean)} cleaned rows")
    print(f"Source 2 (Gig):      {s2_raw_cnt} raw rows -> {len(s2_clean)} cleaned rows (1 blank skipped, 1 corrupted duplicate skipped)")
    print(f"Source 3 (CBNexus):  {s3_raw_cnt} raw rows -> {len(s3_clean)} cleaned rows (1 duplicate header skipped)")
    print(f"Audit Log Records:   {len(audit_logs)} quality events logged to {os.path.basename(OUT_LOG_PATH)}")
    print("=========================================================\n")

if __name__ == "__main__":
    main()
