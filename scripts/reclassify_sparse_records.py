import os
import sys
from dotenv import load_dotenv

load_dotenv()

from backend.app.database.session import engine
from sqlalchemy import text

def reclassify_sparse_records():
    print("Connecting to database...")
    with engine.begin() as conn:
        # Check current status breakdown
        rows_before = conn.execute(text("SELECT status, COUNT(*) FROM records GROUP BY status;")).fetchall()
        print("Before reclassification:", dict(rows_before))

        # Query to update records currently marked VALID that have no property information
        query = text("""
            UPDATE records
            SET status = 'INCOMPLETE'
            WHERE status = 'VALID'
              AND (unit_number IS NULL OR TRIM(unit_number) = '')
              AND (plot_number IS NULL OR TRIM(plot_number) = '')
              AND (building_cluster IS NULL OR TRIM(building_cluster) = '')
              AND (pi_number IS NULL OR TRIM(pi_number) = '')
              AND (developer IS NULL OR TRIM(developer) = '')
              AND (project IS NULL OR TRIM(project) = '')
              AND (
                  community IS NULL 
                  OR TRIM(community) = '' 
                  OR UPPER(TRIM(community)) IN ('TOTAL OWNER DETAILS', 'N/A', 'NONE', 'NULL', 'UNKNOWN')
              );
        """)

        res = conn.execute(query)
        print(f"Updated {res.rowcount:,} records from VALID to INCOMPLETE due to missing property info.")

        rows_after = conn.execute(text("SELECT status, COUNT(*) FROM records GROUP BY status;")).fetchall()
        print("After reclassification:", dict(rows_after))

if __name__ == '__main__':
    reclassify_sparse_records()
