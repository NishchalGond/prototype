"""Fast SQL-based database reclassification and phone cleaning script.

Performs direct PostgreSQL updates to:
1. Nullify invalid/truncated phone numbers (e.g. +55240883, 055240883, 55240883).
2. Standardize UAE mobile numbers (e.g. 0501234567 -> +971501234567, 501234567 -> +971501234567).
3. Set status = 'INCOMPLETE' for all records with missing, invalid, or N/A contact info (mobile_1 is NULL and email_address is NULL) or missing name or missing property details.
4. Set status = 'VALID' only for records that have verified name, verified valid standard contact, and valid property details.
5. Check and recover bedrooms from extras if present.
"""
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from sqlalchemy import text
from backend.app.database.session import SessionLocal

def run_fast_sql_cleanup():
    db = SessionLocal()
    try:
        print("Connecting to database...", flush=True)

        # 1. Clean invalid / truncated phone numbers in mobile_1, mobile_2, mobile_3
        print("1. Nullifying invalid / truncated phone numbers...", flush=True)
        # Numbers like +55240883 or 055240883 or +97155240883 (less than 12 digits for +9715x, or starting with 5x / 05x with wrong length)
        for col in ("mobile_1", "mobile_2", "mobile_3"):
            # Nullify any string containing N/A, null, unknown
            db.execute(text(f"""
                UPDATE records
                SET {col} = NULL
                WHERE {col} IS NOT NULL
                  AND (
                    LOWER(TRIM({col})) IN ('', '-', '--', 'n/a', 'na', 'null', 'none', '0', 'unknown')
                    OR {col} ~* '^[+]?5[024568][0-9]{{1,6}}$'
                    OR {col} ~* '^05[024568][0-9]{{1,6}}$'
                    OR {col} ~* '^[+]?9715[024568][0-9]{{1,7}}$'
                    OR LENGTH(REGEXP_REPLACE({col}, '\\D', '', 'g')) < 8
                  );
            """))
            db.commit()

        # 2. Standardize valid UAE mobile numbers to E.164 (+9715X...)
        print("2. Standardizing valid UAE mobile numbers to E.164...", flush=True)
        for col in ("mobile_1", "mobile_2", "mobile_3"):
            # 0501234567 (10 digits) -> +971501234567
            db.execute(text(f"""
                UPDATE records
                SET {col} = '+971' || SUBSTRING(REGEXP_REPLACE({col}, '\\D', '', 'g') FROM 2)
                WHERE {col} IS NOT NULL
                  AND REGEXP_REPLACE({col}, '\\D', '', 'g') ~ '^05[024568][0-9]{{7}}$';
            """))
            db.commit()

            # 501234567 (9 digits) -> +971501234567
            db.execute(text(f"""
                UPDATE records
                SET {col} = '+971' || REGEXP_REPLACE({col}, '\\D', '', 'g')
                WHERE {col} IS NOT NULL
                  AND REGEXP_REPLACE({col}, '\\D', '', 'g') ~ '^5[024568][0-9]{{7}}$';
            """))
            db.commit()

            # 971501234567 (12 digits) -> +971501234567
            db.execute(text(f"""
                UPDATE records
                SET {col} = '+' || REGEXP_REPLACE({col}, '\\D', '', 'g')
                WHERE {col} IS NOT NULL
                  AND REGEXP_REPLACE({col}, '\\D', '', 'g') ~ '^9715[024568][0-9]{{7}}$'
                  AND NOT {col} LIKE '+%';
            """))
            db.commit()

        # 3. Clean Unit numbers ending in .0
        print("3. Cleaning float .0 on unit_number and plot_number...", flush=True)
        db.execute(text("""
            UPDATE records
            SET unit_number = REGEXP_REPLACE(unit_number, '\\.0+$', '')
            WHERE unit_number IS NOT NULL AND unit_number ~ '^[0-9]+\\.0+$';
        """))
        db.execute(text("""
            UPDATE records
            SET plot_number = REGEXP_REPLACE(plot_number, '\\.0+$', '')
            WHERE plot_number IS NOT NULL AND plot_number ~ '^[0-9]+\\.0+$';
        """))
        db.commit()

        # 4. If mobile_1 is NULL but mobile_2 has a valid number, promote mobile_2 to mobile_1
        print("4. Consolidating mobile phone slots...", flush=True)
        db.execute(text("""
            UPDATE records
            SET mobile_1 = mobile_2, mobile_2 = NULL
            WHERE mobile_1 IS NULL AND mobile_2 IS NOT NULL;
        """))
        db.execute(text("""
            UPDATE records
            SET mobile_2 = mobile_3, mobile_3 = NULL
            WHERE mobile_2 IS NULL AND mobile_3 IS NOT NULL;
        """))
        db.commit()

        # 5. Extract / normalize bedrooms from extras if bedroom is NULL
        print("5. Recovering bedroom values where available in extras...", flush=True)
        db.execute(text("""
            UPDATE records
            SET bedroom = CASE
                WHEN extras->>'BEDROOM' ~* 'studio' THEN 'Studio'
                WHEN extras->>'BEDROOM' ~* '([0-9]+)' THEN (REGEXP_MATCH(extras->>'BEDROOM', '([0-9]+)'))[1] || ' BR'
                WHEN extras->>'NO. OF BEDS' ~* '([0-9]+)' THEN (REGEXP_MATCH(extras->>'NO. OF BEDS', '([0-9]+)'))[1] || ' BR'
                WHEN extras->>'BEDS' ~* '([0-9]+)' THEN (REGEXP_MATCH(extras->>'BEDS', '([0-9]+)'))[1] || ' BR'
                ELSE bedroom
            END
            WHERE (bedroom IS NULL OR bedroom = '' OR bedroom = 'N/A')
              AND extras IS NOT NULL
              AND (extras ? 'BEDROOM' OR extras ? 'NO. OF BEDS' OR extras ? 'BEDS');
        """))
        db.commit()

        # 6. Reclassify status: Any record without a valid phone and without email MUST BE 'INCOMPLETE'
        print("6. Reclassifying records to INCOMPLETE / VALID...", flush=True)
        # Mark INCOMPLETE where contact info is missing
        res_inc = db.execute(text("""
            UPDATE records
            SET status = 'INCOMPLETE'
            WHERE (mobile_1 IS NULL OR mobile_1 = '' OR LOWER(mobile_1) IN ('n/a', 'na', 'null', 'none'))
              AND (email_address IS NULL OR email_address = '' OR LOWER(email_address) IN ('n/a', 'na', 'null', 'none'))
              AND status = 'VALID';
        """))
        db.commit()
        print(f"Updated {res_inc.rowcount:,} records with missing contact to INCOMPLETE.", flush=True)

        # Mark INCOMPLETE where name is missing or placeholder
        res_name = db.execute(text("""
            UPDATE records
            SET status = 'INCOMPLETE'
            WHERE (name IS NULL OR TRIM(name) = '' OR LOWER(TRIM(name)) IN ('owner', 'owners data', 'name', 'n/a', 'na', 'null', 'none'))
              AND status = 'VALID';
        """))
        db.commit()
        print(f"Updated {res_name.rowcount:,} records with missing name to INCOMPLETE.", flush=True)

        # Mark INCOMPLETE where property location is missing
        res_prop = db.execute(text("""
            UPDATE records
            SET status = 'INCOMPLETE'
            WHERE (unit_number IS NULL OR TRIM(unit_number) = '' OR LOWER(TRIM(unit_number)) IN ('n/a', 'na', 'null', 'none'))
              AND (plot_number IS NULL OR TRIM(plot_number) = '' OR LOWER(TRIM(plot_number)) IN ('n/a', 'na', 'null', 'none'))
              AND (pi_number IS NULL OR TRIM(pi_number) = '' OR LOWER(TRIM(pi_number)) IN ('n/a', 'na', 'null', 'none'))
              AND (building_cluster IS NULL OR TRIM(building_cluster) = '')
              AND (community IS NULL OR TRIM(community) = '' OR LOWER(TRIM(community)) LIKE '%owner detail%' OR LOWER(TRIM(community)) LIKE '%total owner%')
              AND status = 'VALID';
        """))
        db.commit()
        print(f"Updated {res_prop.rowcount:,} records with missing property context to INCOMPLETE.", flush=True)

        # Summary counts
        print("\n--- Current Database Summary by Status ---", flush=True)
        counts = db.execute(text("SELECT status, count(*) FROM records GROUP BY status ORDER BY count(*) DESC;")).fetchall()
        for st, cnt in counts:
            print(f"  {st}: {cnt:,}", flush=True)

        print("\n--- Current Bedroom Distribution ---", flush=True)
        bed_counts = db.execute(text("SELECT COALESCE(bedroom, 'N/A') as bed, count(*) FROM records GROUP BY bedroom ORDER BY count(*) DESC LIMIT 15;")).fetchall()
        for b, cnt in bed_counts:
            print(f"  {b}: {cnt:,}", flush=True)

        print("\nDatabase cleanup and reclassification finished successfully!", flush=True)

    finally:
        db.close()

if __name__ == "__main__":
    run_fast_sql_cleanup()
