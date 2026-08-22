import os
import sys
from dotenv import load_dotenv

load_dotenv()

from backend.app.database.session import engine
from sqlalchemy import text

def reclassify_by_builder_registry():
    print("Connecting to PostgreSQL database...")

    # 1. Nullify any remaining 'Total Owner Details' or header noise in community
    print("Step 1: Ensuring all 'Total Owner Details' entries are cleared...")
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE records
            SET community = NULL
            WHERE community IS NOT NULL
              AND (
                  UPPER(TRIM(community)) IN ('TOTAL OWNER DETAILS', 'OWNER DETAILS', 'OWNERS DATA', 'TOTAL OWNERS', 'OWNER DETAIL')
                  OR UPPER(TRIM(community)) LIKE 'TOTAL OWNER%'
                  OR UPPER(TRIM(community)) LIKE 'OWNER DETAILS%'
              );
        """))

    # 2. Reclassify records missing real estate context (Name + Contact + (Unit/Plot OR (Developer AND Community) OR (Building AND Community)))
    print("Step 2: Reclassifying records lacking property context to INCOMPLETE...")
    total_reclassified = 0
    while True:
        with engine.begin() as conn:
            query = text("""
                WITH target AS (
                    SELECT id FROM records
                    WHERE status = 'VALID'
                      AND NOT (
                          (name IS NOT NULL AND TRIM(name) != '') AND 
                          (mobile_1 IS NOT NULL AND TRIM(mobile_1) != '' OR email_address IS NOT NULL AND TRIM(email_address) != '') AND 
                          (
                              (unit_number IS NOT NULL AND TRIM(unit_number) != '') OR
                              (plot_number IS NOT NULL AND TRIM(plot_number) != '') OR
                              (pi_number IS NOT NULL AND TRIM(pi_number) != '') OR
                              (developer IS NOT NULL AND TRIM(developer) != '' AND community IS NOT NULL AND TRIM(community) != '') OR
                              (building_cluster IS NOT NULL AND TRIM(building_cluster) != '' AND community IS NOT NULL AND TRIM(community) != '') OR
                              (developer IS NOT NULL AND TRIM(developer) != '' AND project IS NOT NULL AND TRIM(project) != '')
                          )
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
            print(f"Reclassified batch of {count:,} rows. Total reclassified: {total_reclassified:,}")
            if count == 0:
                break

    # Print final status breakdown
    with engine.begin() as conn:
        rows_after = conn.execute(text("SELECT status, COUNT(*) FROM records GROUP BY status;")).fetchall()
        print("\nFinal Updated Database Status Breakdown:", dict(rows_after))

if __name__ == '__main__':
    reclassify_by_builder_registry()
