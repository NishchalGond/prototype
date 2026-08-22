import os
import sys
from dotenv import load_dotenv

load_dotenv()

from backend.app.database.session import engine
from sqlalchemy import text

def fix_total_owner_details():
    print("Connecting to database...")

    # 1. Clear 'Total Owner Details' using indexed lookup
    print("Clearing 'Total Owner Details' community entries...")
    total_cleared = 0
    while True:
        with engine.begin() as conn:
            query = text("""
                WITH target AS (
                    SELECT id FROM records
                    WHERE community = 'Total Owner Details'
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
            print(f"Batch cleared {count:,} rows. Total cleared: {total_cleared:,}")
            if count == 0:
                break

    # Also clear any remaining variation like 'Owner Details', 'Owners Data'
    print("Clearing remaining header noise variations...")
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE records
            SET community = NULL
            WHERE community IN ('Owner Details', 'Owners Data', 'Total Owners', 'Owner Detail');
        """))

    # 2. Reclassify records marked VALID that lack complete property details
    print("Reclassifying VALID records lacking complete property details to INCOMPLETE...")
    total_reclassified = 0
    while True:
        with engine.begin() as conn:
            query = text("""
                WITH target AS (
                    SELECT id FROM records
                    WHERE status = 'VALID'
                      AND (unit_number IS NULL OR TRIM(unit_number) = '')
                      AND (plot_number IS NULL OR TRIM(plot_number) = '')
                      AND (pi_number IS NULL OR TRIM(pi_number) = '')
                      AND (
                          building_cluster IS NULL 
                          OR TRIM(building_cluster) = '' 
                          OR community IS NULL 
                          OR TRIM(community) = ''
                      )
                      AND (
                          developer IS NULL 
                          OR TRIM(developer) = '' 
                          OR project IS NULL 
                          OR TRIM(project) = ''
                      )
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
            print(f"Batch reclassified {count:,} rows. Total reclassified: {total_reclassified:,}")
            if count == 0:
                break

    # Print final breakdown
    with engine.begin() as conn:
        rows_after = conn.execute(text("SELECT status, COUNT(*) FROM records GROUP BY status;")).fetchall()
        print("Final Updated Database Status Breakdown:", dict(rows_after))

        comm_count = conn.execute(text("SELECT COUNT(*) FROM records WHERE community = 'Total Owner Details';")).scalar()
        print("Remaining 'Total Owner Details' records in DB:", comm_count)

if __name__ == '__main__':
    fix_total_owner_details()
