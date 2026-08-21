from backend.app.database.session import engine
from sqlalchemy import text

def reclassify():
    with engine.begin() as conn:
        # Check total records first
        total = conn.execute(text("SELECT COUNT(*) FROM records;")).scalar()
        print(f"Total records in DB: {total}")

        # Incomplete: Missing valid name OR missing all contact details (mobile_1, mobile_2, mobile_3, email_address)
        q_incomplete = text("""
            UPDATE records 
            SET status = 'INCOMPLETE'
            WHERE (
                name IS NULL OR TRIM(name) = ''
                OR (
                    (mobile_1 IS NULL OR TRIM(mobile_1) = '')
                    AND (mobile_2 IS NULL OR TRIM(mobile_2) = '')
                    AND (mobile_3 IS NULL OR TRIM(mobile_3) = '')
                    AND (email_address IS NULL OR TRIM(email_address) = '')
                )
            );
        """)
        res_inc = conn.execute(q_incomplete)
        print(f"Updated {res_inc.rowcount} records to INCOMPLETE")

        # Valid: Must have BOTH a valid name AND at least one contact detail
        q_valid = text("""
            UPDATE records 
            SET status = 'VALID'
            WHERE (name IS NOT NULL AND TRIM(name) != '')
              AND (
                    (mobile_1 IS NOT NULL AND TRIM(mobile_1) != '')
                 OR (mobile_2 IS NOT NULL AND TRIM(mobile_2) != '')
                 OR (mobile_3 IS NOT NULL AND TRIM(mobile_3) != '')
                 OR (email_address IS NOT NULL AND TRIM(email_address) != '')
              );
        """)
        res_val = conn.execute(q_valid)
        print(f"Updated {res_val.rowcount} records to VALID")

        rows = conn.execute(text("SELECT status, COUNT(*) FROM records GROUP BY status;")).fetchall()
        print("Current DB status breakdown:", rows)

if __name__ == '__main__':
    reclassify()
