from backend.app.database.session import engine
from sqlalchemy import text

def run_fix():
    with engine.begin() as conn:
        # Check record 19300
        r19300 = conn.execute(text("SELECT id, name, mobile_1, email_address, status FROM records WHERE id = 19300;")).fetchone()
        print(f"Record 19300 before: {r19300}")

        # 1. Update all records missing phone & email OR missing name to INCOMPLETE
        q1 = text("""
            UPDATE records
            SET status = 'INCOMPLETE'
            WHERE name IS NULL 
               OR TRIM(name) = ''
               OR (
                    (mobile_1 IS NULL OR TRIM(mobile_1) = '')
                AND (mobile_2 IS NULL OR TRIM(mobile_2) = '')
                AND (mobile_3 IS NULL OR TRIM(mobile_3) = '')
                AND (email_address IS NULL OR TRIM(email_address) = '')
               );
        """)
        res1 = conn.execute(q1)
        print(f"Moved {res1.rowcount} records to INCOMPLETE")

        # 2. Update records with BOTH name AND contact to VALID
        q2 = text("""
            UPDATE records
            SET status = 'VALID'
            WHERE name IS NOT NULL 
              AND TRIM(name) != ''
              AND (
                    (mobile_1 IS NOT NULL AND TRIM(mobile_1) != '')
                 OR (mobile_2 IS NOT NULL AND TRIM(mobile_2) != '')
                 OR (mobile_3 IS NOT NULL AND TRIM(mobile_3) != '')
                 OR (email_address IS NOT NULL AND TRIM(email_address) != '')
              );
        """)
        res2 = conn.execute(q2)
        print(f"Set {res2.rowcount} records to VALID")

        # Check record 19300 after
        r19300_after = conn.execute(text("SELECT id, name, mobile_1, email_address, status FROM records WHERE id = 19300;")).fetchone()
        print(f"Record 19300 after: {r19300_after}")

        # Summary
        breakdown = conn.execute(text("SELECT status, COUNT(*) FROM records GROUP BY status;")).fetchall()
        print(f"Final DB Breakdown: {breakdown}")

if __name__ == '__main__':
    run_fix()
