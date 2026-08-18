#!/usr/bin/env python3
"""
Phase 2: Entity Matching and SQLite Database Pipeline
ConsultBae AI Automation Assignment

Ingests normalized records from processed/, performs deterministic graph clustering
(Disjoint Set Union), flags ambiguous Name+City candidate pairs, and populates
the SQLite database database/consultbae.db.
"""

import os
import csv
import json
import sqlite3
from datetime import datetime
from collections import defaultdict

# Path configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")
DB_DIR = os.path.join(BASE_DIR, "database")

S1_PATH = os.path.join(PROCESSED_DIR, "cleaned_naukri_applicants.csv")
S2_PATH = os.path.join(PROCESSED_DIR, "cleaned_gig_workers.csv")
S3_PATH = os.path.join(PROCESSED_DIR, "cleaned_cbnexus_contacts.csv")
DB_PATH = os.path.join(DB_DIR, "consultbae.db")

class DisjointSet:
    """Disjoint Set Union (DSU) for graph component clustering."""
    def __init__(self):
        self.parent = {}
    
    def find(self, i):
        if i not in self.parent:
            self.parent[i] = i
            return i
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]
        
    def union(self, i, j):
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j

def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def init_db(conn):
    """Create SQLite DDL schema for PERSONS and SOURCE_RECORDS."""
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS SOURCE_RECORDS;")
    cursor.execute("DROP TABLE IF EXISTS PERSONS;")
    
    # Create PERSONS table
    cursor.execute("""
    CREATE TABLE PERSONS (
        id TEXT PRIMARY KEY,
        canonical_name TEXT NOT NULL,
        primary_email TEXT,
        secondary_email TEXT,
        primary_phone TEXT,
        canonical_city TEXT,
        experience_years REAL,
        current_ctc_inr REAL,
        gig_rate_amount REAL,
        gig_rate_unit TEXT,
        gig_status TEXT,
        cbnexus_verified INTEGER DEFAULT 0,
        cbnexus_projects_completed INTEGER DEFAULT 0,
        is_ambiguous INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)
    
    # Create SOURCE_RECORDS table
    cursor.execute("""
    CREATE TABLE SOURCE_RECORDS (
        id TEXT PRIMARY KEY,
        person_id TEXT NOT NULL,
        source_system TEXT NOT NULL,
        source_record_id TEXT NOT NULL,
        raw_data TEXT NOT NULL,
        normalized_data TEXT NOT NULL,
        match_rule TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (person_id) REFERENCES PERSONS(id) ON DELETE CASCADE
    );
    """)
    
    # Create performance indexes
    cursor.execute("CREATE INDEX idx_persons_email ON PERSONS(primary_email);")
    cursor.execute("CREATE INDEX idx_persons_phone ON PERSONS(primary_phone);")
    cursor.execute("CREATE INDEX idx_source_records_person ON SOURCE_RECORDS(person_id);")
    
    conn.commit()

def run_entity_matching():
    print("=========================================================")
    print("STARTING ENTITY MATCHING & SQLITE DATABASE BUILD (PHASE 2)")
    print("=========================================================\n")
    
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    
    # 1. Load normalized datasets
    s1_data = read_csv(S1_PATH)
    s2_data = read_csv(S2_PATH)
    s3_data = read_csv(S3_PATH)
    
    all_records = {}
    dsu = DisjointSet()
    
    # Register nodes in DSU
    for r in s1_data:
        sid = r["source_id"]
        all_records[sid] = ("NAUKRI", r)
        dsu.find(sid)
        
    for r in s2_data:
        sid = r["source_id"]
        all_records[sid] = ("GIG_WORKERS", r)
        dsu.find(sid)
        
    for r in s3_data:
        sid = r["source_id"]
        all_records[sid] = ("CBNEXUS", r)
        dsu.find(sid)
        
    # 2. Build email and phone indexes for deterministic matching
    email_map = defaultdict(list)
    phone_map = defaultdict(list)
    
    for sid, (src, r) in all_records.items():
        em = r.get("normalized_email", "").strip().lower()
        ph = r.get("normalized_phone", "").strip()
        if em:
            email_map[em].append(sid)
        if ph:
            phone_map[ph].append(sid)
            
    # Union by exact normalized email
    for em, sids in email_map.items():
        if len(sids) > 1:
            first = sids[0]
            for s in sids[1:]:
                dsu.union(first, s)
                
    # Union by exact normalized phone
    for ph, sids in phone_map.items():
        if len(sids) > 1:
            first = sids[0]
            for s in sids[1:]:
                dsu.union(first, s)
                
    # Group into connected component clusters
    clusters = defaultdict(list)
    for sid in all_records:
        clusters[dsu.find(sid)].append(sid)
        
    print(f"Loaded {len(all_records)} normalized source records.")
    print(f"Resolved {len(clusters)} deterministic Golden Person clusters.\n")
    
    # 3. Detect Name+City matches between S2 and S3 lacking phone/email bridge
    unmatched_s2_s3 = []
    for root, sids in clusters.items():
        if len(sids) == 1:
            sid = sids[0]
            src, r = all_records[sid]
            if src in ["GIG_WORKERS", "CBNEXUS"]:
                nm = (r.get("normalized_worker_name") or r.get("normalized_name", "")).strip().lower()
                ct = r.get("normalized_city", "").strip().lower()
                unmatched_s2_s3.append((sid, src, nm, ct))
                
    name_city_groups = defaultdict(list)
    for sid, src, nm, ct in unmatched_s2_s3:
        name_city_groups[(nm, ct)].append((sid, src))
        
    ambiguous_sids = set()
    for (nm, ct), items in name_city_groups.items():
        sources = set(x[1] for x in items)
        if len(items) > 1 and len(sources) > 1:
            print(f"Flagged Ambiguous Name+City match ({nm.title()}, {ct.title()}): {[x[0] for x in items]}")
            for x in items:
                ambiguous_sids.add(x[0])
                
    print(f"\nTotal Ambiguous Records Flagged: {len(ambiguous_sids)} records across {len(ambiguous_sids)//2} candidate pairs.\n")
    
    # 4. Sort clusters for deterministic, reproducible Person ID generation
    sorted_cluster_keys = sorted(clusters.keys(), key=lambda root: sorted(clusters[root])[0])
    
    now_iso = datetime.now().isoformat()
    cursor = conn.cursor()
    
    person_counter = 1
    
    for root in sorted_cluster_keys:
        sids = sorted(clusters[root])
        recs = [all_records[s] for s in sids]
        
        person_id = f"PER_{person_counter:03d}"
        person_counter += 1
        
        # Consolidate Golden Person Attributes
        # Full name prioritization: S1 -> S2 -> S3 (favor full name over abbreviation)
        names = []
        for src, r in recs:
            n = r.get("normalized_full_name") or r.get("normalized_worker_name") or r.get("normalized_name")
            if n:
                names.append(n)
                
        # Select longest/most complete name (e.g. 'Rohit Verma' over 'R. Verma')
        canonical_name = max(names, key=len) if names else "Unknown"
        
        emails = []
        for src, r in recs:
            e = r.get("normalized_email")
            if e and e not in emails:
                emails.append(e)
                
        primary_email = emails[0] if len(emails) > 0 else None
        secondary_email = emails[1] if len(emails) > 1 else None
        
        phones = [r.get("normalized_phone") for src, r in recs if r.get("normalized_phone")]
        primary_phone = phones[0] if phones else None
        
        cities = [r.get("normalized_city") for src, r in recs if r.get("normalized_city")]
        canonical_city = cities[0] if cities else None
        
        # S1 attributes
        s1_recs = [r for src, r in recs if src == "NAUKRI"]
        exp_years = float(s1_recs[0]["experience_years"]) if s1_recs and s1_recs[0].get("experience_years") else None
        ctc_inr = float(s1_recs[0]["normalized_ctc_inr"]) if s1_recs and s1_recs[0].get("normalized_ctc_inr") else None
        
        # S2 attributes
        s2_recs = [r for src, r in recs if src == "GIG_WORKERS"]
        gig_rate = float(s2_recs[0]["normalized_rate_amount"]) if s2_recs and s2_recs[0].get("normalized_rate_amount") else None
        gig_unit = s2_recs[0].get("normalized_rate_unit") if s2_recs else None
        gig_status = s2_recs[0].get("normalized_status") if s2_recs else None
        
        # S3 attributes
        s3_recs = [r for src, r in recs if src == "CBNEXUS"]
        cbn_verified = 1 if (s3_recs and s3_recs[0].get("normalized_verified") == "TRUE") else 0
        cbn_projects = int(s3_recs[0]["projects_completed"]) if s3_recs and s3_recs[0].get("projects_completed") else 0
        
        is_ambig = 1 if any(s in ambiguous_sids for s in sids) else 0
        
        # Insert Golden Person record
        cursor.execute("""
        INSERT INTO PERSONS (
            id, canonical_name, primary_email, secondary_email, primary_phone,
            canonical_city, experience_years, current_ctc_inr, gig_rate_amount,
            gig_rate_unit, gig_status, cbnexus_verified, cbnexus_projects_completed,
            is_ambiguous, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            person_id, canonical_name, primary_email, secondary_email, primary_phone,
            canonical_city, exp_years, ctc_inr, gig_rate,
            gig_unit, gig_status, cbn_verified, cbn_projects,
            is_ambig, now_iso, now_iso
        ))
        
        # Insert Source Records lineage
        for src, r in recs:
            sid = r["source_id"]
            sr_id = f"SRC_{sid}"
            
            # Determine match rule
            if sid in ambiguous_sids:
                rule = "AMBIGUOUS_NAME_CITY_REVIEW"
            elif len(sids) > 1:
                has_email_match = len(emails) > 0 and len(sids) > 1
                has_phone_match = len(phones) > 0 and len(sids) > 1
                if has_email_match and has_phone_match:
                    rule = "DETERMINISTIC_EMAIL_PHONE_BOTH"
                elif has_email_match:
                    rule = "DETERMINISTIC_EMAIL"
                elif has_phone_match:
                    rule = "DETERMINISTIC_PHONE"
                else:
                    rule = "DETERMINISTIC_MATCH"
            else:
                rule = "SINGLETON"
                
            # Construct Raw and Normalized JSON payloads
            if src == "NAUKRI":
                raw_dict = {k.replace("raw_", ""): v for k, v in r.items() if k.startswith("raw_")}
                norm_dict = {k.replace("normalized_", ""): v for k, v in r.items() if k.startswith("normalized_")}
            elif src == "GIG_WORKERS":
                raw_dict = {k.replace("raw_", ""): v for k, v in r.items() if k.startswith("raw_")}
                norm_dict = {k.replace("normalized_", ""): v for k, v in r.items() if k.startswith("normalized_")}
            else:
                raw_dict = {k.replace("raw_", ""): v for k, v in r.items() if k.startswith("raw_")}
                norm_dict = {k.replace("normalized_", ""): v for k, v in r.items() if k.startswith("normalized_")}
                
            raw_json = json.dumps(raw_dict, ensure_ascii=False)
            norm_json = json.dumps(norm_dict, ensure_ascii=False)
            
            cursor.execute("""
            INSERT INTO SOURCE_RECORDS (
                id, person_id, source_system, source_record_id,
                raw_data, normalized_data, match_rule, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                sr_id, person_id, src, sid,
                raw_json, norm_json, rule, now_iso
            ))
            
    conn.commit()
    conn.close()
    print("Database build complete.")
    print(f"Successfully generated SQLite database: {DB_PATH}\n")

if __name__ == "__main__":
    run_entity_matching()
