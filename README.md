# ConsultBae — AI Automation Take-Home Assignment

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey.svg)](https://www.sqlite.org/)
[![n8n](https://img.shields.io/badge/Automation-n8n%20v2.x-orange.svg)](https://n8n.io/)

A production-grade implementation of the **ConsultBae AI Automation Assignment** covering multi-source candidate data ingestion, deterministic Disjoint Set Union (DSU) entity resolution, an n8n webhook candidate automation workflow, an interactive audio collection web application with EBU R128 integrated loudness metadata extraction, and a 5,000-worker architecture scaling analysis.

---

## Overview

This project implements an end-to-end AI automation pipeline for candidate data management and audio collection:

1. **Multi-Source Data Integration & Entity Resolution**: Ingests, normalizes, and deduplicates applicant data across 3 disparate CSV sources into a unified SQLite relational database schema (`PERSONS` and `SOURCE_RECORDS`).
2. **n8n Candidate Duplicate Detection & Automation**: An automated n8n webhook workflow that ingests candidate applications, queries the candidate database API, evaluates duplicate status, applies alert metadata, and returns unified status responses.
3. **Audio Collection & Metadata Analytics Web Portal**: A FastAPI web application allowing candidates to submit audio recordings (via live browser recording or file upload), automatically calculating audio metadata (duration, sample rate, bitrate, EBU R128 LUFS loudness), and displaying an interactive submissions dashboard.
4. **Data Quality Audit & Engineering Log**: Comprehensive audit trail logging 260 data hygiene issues and documenting key technical decisions and edge case resolutions.
5. **Scale Architecture Analysis**: Technical blueprint for scaling audio ingestion to 5,000 concurrent gig workers.

---

## Project Structure

```
consultbae-ai-automation-assignment/
│
├── data/                                # Raw immutable source datasets
│   ├── source1_naukri_applicants.csv    # Naukri applicant export
│   ├── source2_gig_workers.csv          # Gig worker database export
│   └── source3_cbnexus_contacts.csv     # CBNexus contacts dump
│
├── processed/                           # Normalized cleaned datasets & audit log
│   ├── cleaned_naukri_applicants.csv   # Normalized Naukri dataset
│   ├── cleaned_gig_workers.csv         # Normalized Gig Workers dataset
│   ├── cleaned_cbnexus_contacts.csv    # Normalized CBNexus dataset
│   └── data_quality_audit_log.csv      # Detailed audit log (260 issue entries)
│
├── database/                            # SQLite Relational Store
│   └── consultbae.db                    # Relational store (PERSONS, SOURCE_RECORDS, AUDIO_SUBMISSIONS)
│
├── scripts/                             # Automation & execution scripts
│   ├── normalize_data.py                # Ingestion, cleaning & standardization pipeline
│   ├── entity_matching.py               # Disjoint Set Union (DSU) graph clustering entity resolution
│   ├── inspect_database.py              # Database diagnostics & Golden Entity reporting script
│   ├── init_audio_db.py                 # AUDIO_SUBMISSIONS table schema initializer
│   └── run_app.py                       # FastAPI web application launcher
│
├── app/                                 # Task 3 FastAPI Web Application
│   ├── main.py                          # REST API & audio metadata calculation engine
│   └── static/                          # Web portal frontend (index.html, style.css, app.js)
│
├── uploads/                             # Physical storage directory for raw audio files
│   └── .gitkeep                         # Placeholder preserving upload folder structure
│
├── n8n/                                 # Task 2 Workflow Automation
│   └── candidate_automation_workflow.json # Exported n8n candidate automation workflow JSON
│
└── README.md                            # Project documentation, setup guide & audit report
```

---

## Task 1 — Data Integration & Entity Matching

### 1. Ingestion & Normalization (`scripts/normalize_data.py`)
Processes 3 raw source files containing 102 total records:
- **`data/source1_naukri_applicants.csv`** (35 records)
- **`data/source2_gig_workers.csv`** (35 records)
- **`data/source3_cbnexus_contacts.csv`** (32 records)

#### Data Cleaning & Standardization Rules:
- **Phone Numbers**: Stripped non-digit characters and removed `+91`, `91`, or leading `0` prefixes to standardize to 10-digit Indian mobile format.
- **Emails**: Trimmed whitespace and converted to lowercase.
- **Names**: Standardized casing (`titlecase`) and removed extra spacing.
- **Dates**: Converted 4 distinct incoming date formats (`DD-MM-YYYY`, `YYYY-MM-DD`, `D MMM YYYY`, `MM/DD/YYYY`) into ISO `YYYY-MM-DD`.
- **Financial CTC**: Normalized mixed CTC values (Lakhs LPA vs full INR amounts) into `normalized_ctc_inr` by multiplying values $< 100$ by $100,000$.
- **Gig Rates**: Separated mixed rate formats (e.g. `1415/hr` vs `15k/month`) into numeric rate values and categorical units (`HOURLY` vs `MONTHLY`).

### 2. Entity Matching & Disjoint Set Union (DSU) Clustering (`scripts/entity_matching.py`)
Uses deterministic graph clustering via Disjoint Set Union (DSU) to resolve candidate identities. Records sharing an exact normalized email or phone number are merged into a single **Golden Person** profile.

#### Database Architecture (`database/consultbae.db`):
- **`PERSONS` Table** (60 Canonical Golden Entities):
  - **Total Resolved Golden Persons**: 60 entities (`PER_001` through `PER_060`).
  - **Multi-Source Linked Entities**: 27 persons were linked across 2 or 3 source files.
  - **Ambiguous Records**: 10 records (5 ambiguous pairs) sharing identical Name + City without verified email/phone matches were flagged with `is_ambiguous = 1` for manual review.
- **`SOURCE_RECORDS` Table** (102 Lineage Audit Entries):
  - Preserves full lineage linking raw source rows to their assigned Golden Person (`person_id`), storing raw JSON, normalized JSON, and exact match criteria.

### Verified Matching Edge Cases Handled:
- **Deepak Nair**: Correctly resolved into **2 distinct persons** (`PER_025` in Bengaluru with 3-way phone match vs `PER_054` in Delhi NCR). Name + City matching alone would have incorrectly merged these distinct candidates.
- **Arjun Mehta**: Resolved into **3 distinct person profiles** (`PER_012` for canonical Arjun Mehta, with `PER_041` & `PER_056` flagged for manual review due to missing contact overlap).
- **Nikhil Chopra**: Merged intra-source alternate email (`alt.nikhil.chopra70@example.com`) with `nikhil.chopra70@example.com` into single profile `PER_019`.
- **Rohit Verma**: Merged `R. Verma` (Line 25) with `Rohit Verma` (Line 31) into `PER_017` via phone match (`9000000117`).

---

## Task 2 — n8n Duplicate Detection Automation

The final verified n8n workflow automates candidate duplicate detection and alert generation.

### Workflow Architecture & Node Flow

```
[ Webhook (POST) ]
       │
       ▼
[ Code in JavaScript ] (Normalize Input)
       │
       ▼
[ HTTP Request ] (GET http://127.0.0.1:8000/api/candidates)
       │
       ▼
[ Code in JavaScript1 ] (Entity Matching / Cross-Check)
       │
       ▼
[ IF Node ] (isDuplicate === true)
       ├── TRUE ──► [ Edit Fields ]  (DUPLICATE_FOUND_ALERT) ──┐
       └── FALSE ─► [ Edit Fields1 ] (NEW_CANDIDATE_RECORD)  ──┴─► [ Merge ] ──► [ Respond to Webhook ]
```

### Execution Behavior

1. **Webhook (POST)**: Receives candidate application payload on path `/candidate-application`.
2. **Code in JavaScript**: Normalizes name, email, phone, city, skills, and experience years.
3. **HTTP Request**: Performs `GET http://127.0.0.1:8000/api/candidates` to fetch existing database candidates.
4. **Code in JavaScript1**: Receives both normalized incoming attributes and database candidate records, performing exact email and phone matching.
5. **IF Node**: Evaluates `isDuplicate === true`.
6. **Duplicate Candidate Path (TRUE)**:
   - Routes to `Edit Fields` (Set node).
   - Assigns `alert_type = "DUPLICATE_FOUND_ALERT"`.
   - Generates warning message linking candidate to existing Golden Entity ID (e.g. `PER_011`).
   - Assigns `action_required = "Merge source details into existing record PER_011"`.
7. **New Candidate Path (FALSE)**:
   - Routes to `Edit Fields1` (Set node).
   - Assigns `alert_type = "NEW_CANDIDATE_RECORD"`.
   - Generates message confirming candidate uniqueness.
   - Assigns `action_required = "Create new Golden Person profile"`.
8. **Merge**: Merges branch outputs back into a single pipeline.
9. **Respond to Webhook**: Returns the final JSON payload with HTTP status 200.

### Exported Workflow Artifact
- Exported JSON location: [`n8n/candidate_automation_workflow.json`](n8n/candidate_automation_workflow.json)

### Verified Test Results

#### 1. Duplicate Candidate Test Payload (`Tanvi Gupta`)
**POST Payload**:
```json
{
  "full_name": "Tanvi Gupta",
  "email": "tanvi.gupta31@example.com",
  "phone": "9000000254",
  "city": "Bengaluru",
  "skills": ["n8n", "LangChain", "REST APIs", "Python"],
  "experience_years": 4.2
}
```

**HTTP 200 OK Response**:
```json
{
  "alert_type": "DUPLICATE_FOUND_ALERT",
  "alert_message": "⚠️ DUPLICATE ALERT: Candidate Tanvi Gupta already exists in database as Golden Entity PER_011 (Tanvi Gupta) via Exact Email Match (tanvi.gupta31@example.com).",
  "action_required": "Merge source details into existing record PER_011"
}
```

#### 2. New Candidate Test Payload (`Rohan Sharma`)
**POST Payload**:
```json
{
  "full_name": "Rohan Sharma",
  "email": "rohan.sharma999@unique-domain-test.com",
  "phone": "9999999999",
  "city": "Mumbai",
  "skills": ["Python", "FastAPI"],
  "experience_years": 3.0
}
```

**HTTP 200 OK Response**:
```json
{
  "alert_type": "NEW_CANDIDATE_RECORD",
  "alert_message": "✅ NEW CANDIDATE: Candidate Rohan Sharma (rohan.sharma999@unique-domain-test.com) is unique and ready for ingestion.",
  "action_required": "Create new Golden Person profile"
}
```

---

## Task 3 — Audio Collection Application

The Task 3 web application (`app/main.py`) provides an interactive interface for candidate audio submission and metadata reporting.

### Features Implemented:

1. **Candidate Selection**: Autocomplete dropdown connected to `GET /api/candidates` populated from the 60 Golden Persons database records.
2. **Browser Audio Recording**: In-browser recording via HTML5 `MediaRecorder` API with live timer and real-time audio visualizer.
3. **File Upload Fallback**: Drag-and-drop file upload supporting `.wav`, `.webm`, `.mp3`, and `.m4a`.
4. **Audio Storage**: Submissions are saved to `uploads/` with unique filenames (`aud_{person_id}_{timestamp}.wav/.webm`) and recorded in `AUDIO_SUBMISSIONS` database table.
5. **Metadata Extraction Engine**:
   - **Duration (`duration_seconds`)**: Extracted from total audio signal frames divided by sample rate.
   - **Sample Rate (`sample_rate_hz`)**: Extracted directly from signal header.
   - **Bitrate (`bitrate_kbps`)**: Calculated as $\frac{\text{file\_size\_bytes} \times 8}{\text{duration\_seconds} \times 1000}$.
   - **Loudness (`loudness_lufs`)**: Integrated loudness calculated via `pyloudnorm` adhering to **ITU-R BS.1770-4 / EBU R128** standard.
6. **Submissions Dashboard & Playback**: View 2 displays submission records joined with `PERSONS` canonical profile info, featuring inline HTML5 audio playback controls and summary metrics (Total Submissions, Average Duration, Average LUFS Loudness).
7. **Candidate Validation Rule**: Rejects submissions for candidates not in `PERSONS` database with an HTTP 400 error (**Does NOT create new `PERSONS` rows**).

---

## Task 4 — Data Quality Report

Data quality findings are logged in `processed/data_quality_audit_log.csv` (260 audit entries).

### Summary of Audit Issue Categories Found:

| Issue Category | Description | Count | Resolution / Action Taken |
| :--- | :--- | :---: | :--- |
| **`PHONE_FORMAT`** | Phone numbers with prefixes (`+91`, `91`, `0`), hyphens, or spaces. | 72 | Stripped non-digits and leading zero/91 prefixes; normalized to 10 digits. |
| **`EMAIL_FORMAT`** | Mixed casing or un-trimmed whitespace. | 65 | Converted to lowercase and trimmed whitespace. |
| **`NAME_CASING`** | Irregular name casing (e.g. `gaurav mehta`, `R. Verma`). | 45 | Standardized to Title Case (`Gaurav Mehta`). |
| **`DATE_FORMAT`** | 4 distinct date formats (`DD-MM-YYYY`, `YYYY-MM-DD`, `D MMM YYYY`, `MM/DD/YYYY`). | 28 | Parsed multi-format strings into standard ISO `YYYY-MM-DD`. |
| **`CITY_NAME`** | Obsolete or non-standard city names (e.g. `GURGAON`, `BANGALORE`). | 22 | Mapped to canonical city names (`Gurugram`, `Bengaluru`). |
| **`CTC_UNIT_CONVERSION`** | CTC values mixed between Lakhs LPA (`4.2`) and full INR (`417964`). | 14 | Values $< 100$ multiplied by $100,000$ to compute `normalized_ctc_inr`. |
| **`RATE_UNIT_PARSED`** | Gig rates mixed between hourly (`1415/hr`) and monthly (`15k/month`). | 8 | Split numeric rate and set `gig_rate_unit` to `HOURLY` vs `MONTHLY`. |
| **`CORRUPTED_SHIFTED_ROW`**| Line 20 in `source2_gig_workers.csv` shifted right by 1 column. | 1 | Detected as shifted duplicate of clean Line 7; skipped during ingestion. |
| **`EMPTY_ROW`** | Line 12 in `source2_gig_workers.csv` completely blank. | 1 | Detected and skipped. |
| **`DUPLICATE_HEADER`** | Line 16 in `source3_cbnexus_contacts.csv` contained intermediate CSV header. | 1 | Filtered out header row inside body. |
| **`STATUS_CASING`** | Mixed casing in employment status strings. | 2 | Normalized to uppercase (`ACTIVE`, `INACTIVE`). |
| **`VERIFIED_BOOLEAN`** | Variant boolean representations (`TRUE`, `1`, `yes`). | 1 | Standardized to integer boolean (`1` or `0`). |

---

## Task 5 — Stretch Goal: 5,000 Worker Scale Architecture Analysis

### 1. Scaling Bottlenecks at 5,000 Workers / Weekend

- **Concurrent File Upload I/O**: 5,000 audio uploads (avg. $2\text{ MB}$ each) over 48 hours equals $\sim 10\text{ GB}$ of uncompressed audio data. Peak surges (e.g., 500 workers submitting simultaneously) will block single-threaded FastAPI Uvicorn processes during CPU-bound audio metadata processing (`pyloudnorm` FFT signal filtering).
- **SQLite Database Lock Contention**: SQLite relies on file-level write locks (`database/consultbae.db`). Concurrent write transactions from hundreds of active worker threads trigger `sqlite3.OperationalError: database is locked`.
- **Local Disk Storage Exhaustion**: Storing raw audio on local server disk (`uploads/`) risks storage exhaustion, lacks redundancy, and prevents horizontal scaling across stateless app containers.

### 2. Proposed Production Blueprint

```
[Gig Worker Client] ──► [CDN / API Gateway] ──► [Stateless FastAPI Web Nodes]
                                                        │
                                                        ├──► [AWS S3 (Presigned Uploads)]
                                                        │
                                                        └──► [Redis Task Queue]
                                                                   │
                                                                   ▼
                                                         [Celery Worker Cluster]
                                                        (pyloudnorm FFT / LUFS)
                                                                   │
                                                                   ▼
                                                     [Amazon Aurora PostgreSQL]
```

#### Blueprint Enhancements:
1. **S3 Presigned Direct Uploads**: Client requests presigned upload URL from `/api/audio/presign-upload` and uploads directly to AWS S3, bypassing web app server I/O entirely.
2. **Asynchronous Background Processing Queue**: Decouple audio metadata calculation using **Celery + Redis**. S3 upload events trigger background workers to calculate LUFS loudness asynchronously.
3. **Amazon Aurora PostgreSQL**: Replace SQLite with managed PostgreSQL and `pgBouncer` connection pooling to handle concurrent write transactions seamlessly.
4. **Lifecycle & Cost Policies**: S3 lifecycle rules automatically transition raw audio files to S3 Glacier Instant Retrieval after 30 days, cutting storage costs by $\sim 70\%$.

---

## How to Run Locally

### Prerequisites
- Python 3.10+
- Node.js v18+ (for running n8n locally)

### 1. Run Data Normalization Pipeline (Task 1 Phase 1B)
```bash
python scripts/normalize_data.py
```
*Ingests raw CSVs from `data/`, standardizes fields, and writes cleaned CSVs and `data_quality_audit_log.csv` to `processed/`.*

### 2. Run Entity Matching & Database Construction (Task 1 Phase 2)
```bash
python scripts/entity_matching.py
```
*Executes Disjoint Set Union (DSU) graph clustering and builds `database/consultbae.db` with `PERSONS` and `SOURCE_RECORDS` tables.*

### 3. Inspect Database Metrics & Resolved Entities
```bash
python scripts/inspect_database.py
```
*Prints total Golden Persons (60), linked entities (27), ambiguous records (10), and source lineage counts.*

### 4. Launch FastAPI Audio Web Application (Task 3)
```bash
python scripts/run_app.py
```
*Launches web application on **`http://localhost:8000`**.*
- **Audio Application Portal**: `http://localhost:8000`
- **Interactive OpenAPI Documentation**: `http://localhost:8000/docs`

### 5. Launch n8n Server (Task 2)
```bash
npx n8n start
```
*Launches local n8n instance on **`http://localhost:5678`**.*

---

## n8n Testing

> [!IMPORTANT]
> **Do NOT attempt to test the POST webhook by pasting `http://localhost:5678/webhook/candidate-application` into a browser address bar.**
> Web browsers send HTTP `GET` requests by default, which will return `404 Not Found`. Webhook endpoints must be tested using HTTP `POST` requests.

### Testing Method 1: Using Python `requests` (Recommended)

Run the following test script in terminal:

```python
import requests
import json

url = "http://127.0.0.1:5678/webhook/candidate-application"
payload = {
  "full_name": "Tanvi Gupta",
  "email": "tanvi.gupta31@example.com",
  "phone": "9000000254",
  "city": "Bengaluru",
  "skills": ["n8n", "LangChain", "REST APIs", "Python"],
  "experience_years": 4.2
}

response = requests.post(url, json=payload)
print("Status Code:", response.status_code)
print("Response JSON:", json.dumps(response.json(), indent=2))
```

### Testing Method 2: Using cURL

```bash
curl -X POST http://127.0.0.1:5678/webhook/candidate-application \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Tanvi Gupta",
    "email": "tanvi.gupta31@example.com",
    "phone": "9000000254",
    "city": "Bengaluru",
    "skills": ["n8n", "LangChain", "REST APIs", "Python"],
    "experience_years": 4.2
  }'
```

---

## Data Quality & Engineering Decisions

1. **Deterministic Matching over Aggressive Fuzzy Matching**:
   - Identity resolution matches candidates *only* on exact normalized email or phone. Name + City alone is never used to auto-merge candidates, preventing false positive merges of distinct individuals sharing common Indian names.
2. **Ambiguous Profile Isolation**:
   - Candidates matching Name + City without contact overlap are preserved as distinct `PERSONS` rows and flagged with `is_ambiguous = 1` for human review.
3. **EBU R128 Integrated Loudness Compliance**:
   - Loudness is calculated using `pyloudnorm` (ITU-R BS.1770-4 / EBU R128 standard in LUFS) rather than treating raw peak dBFS as loudness.
4. **Strict Verification Guard on Audio Upload**:
   - Audio submissions must link to an existing verified Golden Person profile. Unrecognized candidate lookups return HTTP 400 errors to prevent unverified DB insertion.
5. **Unified Path in n8n Workflow**:
   - Standardized TRUE and FALSE branches through a `Merge` node, ensuring single response path to `Respond to Webhook`.

---

## Stuck Log

### 1. Challenge: CTC Unit Discrepancies & Phone Format Variance
- **Where I Got Stuck**: Source 1 contained numeric CTC values like `4.2` alongside `417964`. Sorting or min/max operations broke when comparing Lakhs vs full INR. Additionally, phone numbers contained mixed country prefixes (`+91-`, `91`, `0`).
- **What I Searched & Asked AI**: *"How to normalize Indian mobile numbers and differentiate LPA vs full INR salary in Python"*
- **Suggestions Rejected**:
  - *Rejected*: Using regex string pattern matching alone for salary units.
  - *Rejected*: Truncating phone numbers to rightmost 10 digits without verifying country code prefixes.
- **How I Got Unstuck**: Wrote explicit validation functions in `scripts/normalize_data.py`. For CTC, values $< 100$ were recognized as Lakhs ($LPA$) and multiplied by $100,000$. For phones, cleaned non-digits, removed leading zero or `91` prefixes, and validated exact 10-digit length.

### 2. Challenge: Entity Resolution & Avoiding False Merges
- **Where I Got Stuck**: Candidates like `Deepak Nair` appeared in multiple files in different cities (`Bengaluru` vs `Delhi NCR`), while `Arjun Mehta` appeared 3 times with overlapping names but conflicting emails/phones. Naive fuzzy string matching on names would accidentally merge distinct real-world individuals with common Indian names.
- **What I Searched & Asked AI**: *"Deterministic entity resolution graph clustering Python Disjoint Set Union"*
- **Suggestions Rejected**:
  - *Rejected*: Auto-merging candidates based on Name + City alone.
  - *Rejected*: Using aggressive Levenshtein edit distance thresholds on candidate names.
- **How I Got Unstuck**: Implemented a **Disjoint Set Union (DSU) graph clustering engine** in `scripts/entity_matching.py`. Records were merged *only* when connected by exact normalized email or phone. Candidates sharing Name + City without contact overlap were flagged in `PERSONS` as `is_ambiguous = 1` for manual review, isolating `Deepak Nair` into 2 separate profiles.

### 3. Challenge: Audio Loudness Standard (LUFS vs dBFS) & Python 3.13 Compatibility
- **Where I Got Stuck**: `pydub`'s `.dBFS` property calculates raw peak RMS ratio, which does not equal standard EBU R128 integrated loudness in LUFS. Additionally, running on Python 3.13 triggered `ModuleNotFoundError: No module named 'audioop'` because Python 3.13 removed built-in `audioop`.
- **What I Searched & Asked AI**: *"EBU R128 integrated loudness Python pyloudnorm soundfile Python 3.13 audioop removal"*
- **Suggestions Rejected**:
  - *Rejected*: Treating `pydub.dBFS` directly as LUFS loudness.
  - *Rejected*: Downgrading Python interpreter version.
- **How I Got Unstuck**: Installed `pyloudnorm` and `audioop-lts` (C-extension compatibility library for Python 3.13). Used `pyloudnorm.Meter(sample_rate).integrated_loudness(signal)` to compute actual ITU-R BS.1770-4 / EBU R128 integrated loudness in LUFS. For non-WAV formats (WebM/MP3), used `soundfile` with an in-memory WAV PCM buffer fallback.

---

## Verification / Test Results

### Verified Components (Tested & Passing Live):
- **Database Construction**: Verified 60 Golden Persons and 102 SOURCE_RECORDS generated in `database/consultbae.db`.
- **Data Quality Audit**: Verified 260 audit entries logged in `processed/data_quality_audit_log.csv`.
- **FastAPI Web Server**: Operational on port 8000 (`/api/candidates`, `/api/audio/upload`, `/api/audio/submissions`).
- **Audio Metadata Extraction**: Duration, Sample Rate, Bitrate, and EBU R128 LUFS Loudness calculation verified.
- **n8n Webhook Automation**: Active and verified on port 5678. Tested with POST payloads returning HTTP 200 OK for Duplicate (`PER_011`) and New Candidate paths.
- **Workflow Export**: `n8n/candidate_automation_workflow.json` validated and confirmed matching active workflow.

### Unverified / Out-of-Scope Items:
- **S3 Presigned Direct Uploads**: Design proposal presented in Task 5 scaling architecture analysis only; local filesystem storage (`uploads/`) is implemented.
- **Automated CI/CD Deployment**: Not requested in assignment scope.

---

## Submission Checklist

- [x] **GitHub Repository**: Complete codebase committed.
- [x] **README.md**: Technical documentation, setup guide & data quality report.
- [x] **Exported n8n Workflow JSON**: Saved at `n8n/candidate_automation_workflow.json`.
- [x] **Data-Quality Audit Report**: Saved at `processed/data_quality_audit_log.csv`.
- [x] **Stuck Log**: Included in README.
- [ ] **Screen Recording**: Video demo (max 6 minutes) to be recorded by candidate.
