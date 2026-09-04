"""Universal and robust migration script from local.db (SQLite) to PostgreSQL (datalink)."""
import sqlite3
import psycopg2
from psycopg2.extras import execute_values, Json
import json
import time

def sync_table(sq_cur, pg_con, pg_cur, table_name, batch_size=5000, skip_pg_cols=None):
    if skip_pg_cols is None:
        skip_pg_cols = set()
        
    print(f"Syncing table {table_name}...", flush=True)
    # Get columns in SQLite
    sq_cols = [c[1] for c in sq_cur.execute(f"PRAGMA table_info({table_name});").fetchall()]
    
    # Get columns and types in PostgreSQL
    pg_cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table_name}';
    """)
    pg_meta = {row[0]: row[1] for row in pg_cur.fetchall()}
    
    # Matching columns to copy
    common_cols = [c for c in sq_cols if c in pg_meta and c not in skip_pg_cols]
    if not common_cols:
        print(f"  No common columns found for {table_name}. Skipping.", flush=True)
        return 0
        
    col_str = ", ".join(f'"{c}"' for c in common_cols)
    
    sq_cur.execute(f"SELECT {col_str} FROM {table_name};")
    total_rows = 0
    
    while True:
        rows = sq_cur.fetchmany(batch_size)
        if not rows:
            break
            
        cleaned_batch = []
        for r in rows:
            row_vals = []
            for col, val in zip(common_cols, r):
                col_type = pg_meta[col].lower()
                if val is not None:
                    if col_type == 'boolean':
                        val = bool(val)
                    elif col_type in ('json', 'jsonb'):
                        if isinstance(val, str):
                            try:
                                val = Json(json.loads(val))
                            except Exception:
                                val = Json({})
                        elif isinstance(val, (dict, list)):
                            val = Json(val)
                row_vals.append(val)
            cleaned_batch.append(tuple(row_vals))
            
        execute_values(pg_cur, f"INSERT INTO {table_name} ({col_str}) VALUES %s ON CONFLICT DO NOTHING;", cleaned_batch)
        pg_con.commit()
        total_rows += len(cleaned_batch)
        print(f"  {table_name}: {total_rows:,} rows committed...", flush=True)
        
    # Reset primary key sequence if exists
    try:
        pg_cur.execute(f"SELECT setval('{table_name}_id_seq', (SELECT COALESCE(MAX(id), 1) FROM {table_name}));")
        pg_con.commit()
    except Exception:
        pass
        
    print(f"Finished {table_name}: {total_rows:,} total rows synced.", flush=True)
    return total_rows

def main():
    start_time = time.time()
    sq_con = sqlite3.connect('local.db')
    sq_cur = sq_con.cursor()
    
    db_url = os.getenv("DATABASE_URL")
    if db_url and "postgresql" in db_url:
        pg_con = psycopg2.connect(db_url)
    else:
        pg_con = psycopg2.connect(
            dbname=os.getenv("PGDATABASE", "datalink"),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", "postgres"),
            host=os.getenv("PGHOST", "localhost"),
            port=int(os.getenv("PGPORT", 5432))
        )
    pg_cur = pg_con.cursor()
    
    # 1. Users
    sync_table(sq_cur, pg_con, pg_cur, 'users')
    
    # 2. Source Files
    sync_table(sq_cur, pg_con, pg_cur, 'source_files')
    
    # 3. Processing Jobs
    sync_table(sq_cur, pg_con, pg_cur, 'processing_jobs')
    
    # 4. Records (skip stored generated columns)
    skip_pg_records = {'search_text', 'property_key', 'mobile_digits', 'has_valid_mobile'}
    sync_table(sq_cur, pg_con, pg_cur, 'records', batch_size=10000, skip_pg_cols=skip_pg_records)
    
    # 5. Leads
    sync_table(sq_cur, pg_con, pg_cur, 'leads')
    
    # 6. Lead Activities
    sync_table(sq_cur, pg_con, pg_cur, 'lead_activities')
    
    elapsed = time.time() - start_time
    print(f"\n=======================================================", flush=True)
    print(f"ALL DATA MIGRATED TO POSTGRESQL IN {elapsed:.1f} SECONDS!", flush=True)
    print(f"=======================================================", flush=True)
    
    sq_con.close()
    pg_con.close()

if __name__ == '__main__':
    main()
