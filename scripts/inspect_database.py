#!/usr/bin/env python3
"""
Database Inspection & Verification Script
ConsultBae AI Automation Assignment

Inspects database/consultbae.db to verify table row counts, distributions,
and known edge-case entity resolution accuracy.
"""

import os
import sqlite3
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "consultbae.db")

def inspect_database():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file '{DB_PATH}' does not exist.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=========================================================")
    print("DATABASE INSPECTION & VERIFICATION REPORT")
    print("=========================================================\n")

    # 1. Total Persons
    cursor.execute("SELECT COUNT(*) FROM PERSONS;")
    total_persons = cursor.fetchone()[0]

    # 2. Total Source Records
    cursor.execute("SELECT COUNT(*) FROM SOURCE_RECORDS;")
    total_source_records = cursor.fetchone()[0]

    # 3. Persons with Multiple Source Records
    cursor.execute("""
        SELECT person_id, COUNT(*) as cnt 
        FROM SOURCE_RECORDS 
        GROUP BY person_id 
        HAVING cnt > 1;
    """)
    multi_source_persons = cursor.fetchall()

    # 4. Ambiguous Persons
    cursor.execute("SELECT COUNT(*) FROM PERSONS WHERE is_ambiguous = 1;")
    ambiguous_persons = cursor.fetchone()[0]

    # 5. Source Distribution
    cursor.execute("""
        SELECT source_system, COUNT(*) as cnt 
        FROM SOURCE_RECORDS 
        GROUP BY source_system;
    """)
    source_dist = cursor.fetchall()

    # 6. Match-Rule Distribution
    cursor.execute("""
        SELECT match_rule, COUNT(*) as cnt 
        FROM SOURCE_RECORDS 
        GROUP BY match_rule;
    """)
    rule_dist = cursor.fetchall()

    print(f"Total Persons (Golden Entities): {total_persons}")
    print(f"Total Source Records Preserved:  {total_source_records}")
    print(f"Persons with Multiple Records:   {len(multi_source_persons)}")
    print(f"Ambiguous Persons (Flagged):     {ambiguous_persons}\n")

    print("--- Source System Distribution ---")
    for row in source_dist:
        print(f"  • {row['source_system']:<15}: {row['cnt']} records")

    print("\n--- Match-Rule Distribution ---")
    for row in rule_dist:
        print(f"  • {row['match_rule']:<30}: {row['cnt']} records")

    # 7. Verification of Known Edge Cases
    print("\n=========================================================")
    print("VERIFICATION OF KNOWN EDGE CASES")
    print("=========================================================\n")

    # Case A: Deepak Nair
    cursor.execute("SELECT id, canonical_name, primary_email, primary_phone, canonical_city FROM PERSONS WHERE canonical_name = 'Deepak Nair';")
    deepak_rows = cursor.fetchall()
    print(f"1. Deepak Nair Check: Found {len(deepak_rows)} distinct person profiles")
    for r in deepak_rows:
        cursor.execute("SELECT source_system, source_record_id FROM SOURCE_RECORDS WHERE person_id = ?;", (r["id"],))
        s_recs = [f"{sr['source_system']}:{sr['source_record_id']}" for sr in cursor.fetchall()]
        print(f"   - Person ID {r['id']}: Email={r['primary_email']}, Phone={r['primary_phone']}, City={r['canonical_city']} -> Sources: {s_recs}")

    # Case B: Arjun Mehta
    cursor.execute("SELECT id, canonical_name, primary_email, primary_phone, canonical_city, is_ambiguous FROM PERSONS WHERE canonical_name = 'Arjun Mehta';")
    arjun_rows = cursor.fetchall()
    print(f"\n2. Arjun Mehta Check: Found {len(arjun_rows)} distinct person profiles")
    for r in arjun_rows:
        cursor.execute("SELECT source_system, source_record_id, match_rule FROM SOURCE_RECORDS WHERE person_id = ?;", (r["id"],))
        s_recs = [f"{sr['source_system']}:{sr['source_record_id']} ({sr['match_rule']})" for sr in cursor.fetchall()]
        print(f"   - Person ID {r['id']}: Email={r['primary_email']}, Phone={r['primary_phone']}, City={r['canonical_city']}, Ambiguous={r['is_ambiguous']} -> Sources: {s_recs}")

    # Case C: Nikhil Chopra
    cursor.execute("SELECT id, canonical_name, primary_email, secondary_email, primary_phone FROM PERSONS WHERE canonical_name = 'Nikhil Chopra';")
    nikhil_rows = cursor.fetchall()
    print(f"\n3. Nikhil Chopra Check: Found {len(nikhil_rows)} person profile(s)")
    for r in nikhil_rows:
        cursor.execute("SELECT source_system, source_record_id FROM SOURCE_RECORDS WHERE person_id = ?;", (r["id"],))
        s_recs = [f"{sr['source_system']}:{sr['source_record_id']}" for sr in cursor.fetchall()]
        print(f"   - Person ID {r['id']}: PrimaryEmail={r['primary_email']}, SecondaryEmail={r['secondary_email']}, Phone={r['primary_phone']} -> Sources: {s_recs}")

    # Case D: Rohit Verma / R. Verma
    cursor.execute("SELECT id, canonical_name, primary_email, primary_phone FROM PERSONS WHERE canonical_name LIKE '%Verma%';")
    rohit_rows = cursor.fetchall()
    print(f"\n4. Rohit Verma / R. Verma Check: Found {len(rohit_rows)} person profile(s)")
    for r in rohit_rows:
        cursor.execute("SELECT source_system, source_record_id FROM SOURCE_RECORDS WHERE person_id = ?;", (r["id"],))
        s_recs = [f"{sr['source_system']}:{sr['source_record_id']}" for sr in cursor.fetchall()]
        print(f"   - Person ID {r['id']}: CanonicalName='{r['canonical_name']}', Email={r['primary_email']}, Phone={r['primary_phone']} -> Sources: {s_recs}")

    # 8. Sample Table Rows
    print("\n=========================================================")
    print("SAMPLE TABLE ROWS")
    print("=========================================================\n")

    print("--- Sample PERSONS Rows (First 3) ---")
    cursor.execute("SELECT * FROM PERSONS LIMIT 3;")
    for r in cursor.fetchall():
        print(dict(r))

    print("\n--- Sample SOURCE_RECORDS Rows (First 3) ---")
    cursor.execute("SELECT * FROM SOURCE_RECORDS LIMIT 3;")
    for r in cursor.fetchall():
        row_dict = dict(r)
        print(row_dict)

    conn.close()
    print("\nInspection completed successfully.")

if __name__ == "__main__":
    inspect_database()
