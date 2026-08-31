# Verifies 5-field core completeness rule
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from backend.app.database.session import engine
from sqlalchemy import text

def enforce_5_field_completeness():
    print("Connecting to PostgreSQL database...")

    # 1. Nullify invalid community 'Total Owner Details' and related header noise
    print("Step 1: Clearing invalid community entries ('Total Owner Details', etc.)...")
    total_cleared = 0
    while True:
        with engine.begin() as conn:
            query = text("""
                WITH target AS (
                    SELECT id FROM records
                    WHERE community IS NOT NULL
                      AND (
                          UPPER(TRIM(community)) IN ('TOTAL OWNER DETAILS', 'OWNER DETAILS', 'OWNERS DATA', 'TOTAL OWNERS', 'OWNER DETAIL')
                          OR UPPER(TRIM(community)) LIKE 'TOTAL OWNER%'
                          OR UPPER(TRIM(community)) LIKE 'OWNER DETAILS%'
                      )
                    LIMIT 20000
                )
                UPDATE records r
                SET community = NULL
                FROM target
                WHERE r.id = target.id;
            """)
            res = conn.execute(query)
            count = res.rowcount
            total_cleared += count
            print(f"Cleared batch of {count:,} rows. Total cleared: {total_cleared:,}")
            if count == 0:
                break

    # 2. Reclassify VALID records that have fewer than 5 populated fields to INCOMPLETE
    print("Step 2: Reclassifying VALID records with fewer than 5 populated fields to INCOMPLETE...")
    total_reclassified = 0
    while True:
        with engine.begin() as conn:
            query = text("""
                WITH target AS (
                    SELECT id FROM records
                    WHERE status = 'VALID'
                      AND (
                        (CASE WHEN name IS NOT NULL AND TRIM(name) != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN mobile_1 IS NOT NULL AND TRIM(mobile_1) != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN email_address IS NOT NULL AND TRIM(email_address) != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN community IS NOT NULL AND TRIM(community) != '' AND UPPER(TRIM(community)) NOT IN ('TOTAL OWNER DETAILS', 'N/A') THEN 1 ELSE 0 END) +
                        (CASE WHEN sub_community IS NOT NULL AND TRIM(sub_community) != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN building_cluster IS NOT NULL AND TRIM(building_cluster) != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN unit_number IS NOT NULL AND TRIM(unit_number) != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN bedroom IS NOT NULL AND TRIM(bedroom) != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN procedure_value IS NOT NULL THEN 1 ELSE 0 END) +
                        (CASE WHEN developer IS NOT NULL AND TRIM(developer) != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN project IS NOT NULL AND TRIM(project) != '' THEN 1 ELSE 0 END) +
                        (CASE WHEN property_type IS NOT NULL AND TRIM(property_type) != '' THEN 1 ELSE 0 END)
                      ) < 5
                    LIMIT 20000
                )
                UPDATE records r
                SET status = 'INCOMPLETE'
                FROM target
                WHERE r.id = target.id;
            """)
            res = conn.execute(query)
            count = res.rowcount
            total_reclassified += count
            print(f"Reclassified batch of {count:,} rows. Total reclassified: {total_reclassified:,}")
            if count == 0:
                break

    # Print final status breakdown
    with engine.begin() as conn:
        rows_after = conn.execute(text("SELECT status, COUNT(*) FROM records GROUP BY status;")).fetchall()
        print("\nFinal Updated Database Status Breakdown:", dict(rows_after))

        comm_count = conn.execute(text("SELECT COUNT(*) FROM records WHERE community = 'Total Owner Details';")).scalar()
        print("Remaining 'Total Owner Details' records in DB:", comm_count)

if __name__ == '__main__':
    enforce_5_field_completeness()
