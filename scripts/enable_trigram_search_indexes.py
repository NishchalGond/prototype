"""DEPRECATED - kept only for one-off manual use.

These indexes are now created by the Alembic migration
`7ba9686c4678_dedup_lookup_index`, which runs automatically on deploy. Relying
on someone remembering to run this script by hand meant production search could
silently be missing its indexes. Prefer:

    alembic upgrade head

This remains safe to run (every statement is IF NOT EXISTS) but is redundant.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

import psycopg2

def enable_trigram_search_indexes():
    db_url = os.getenv("DATABASE_URL")
    if not db_url or "sqlite" in db_url.lower():
        print("SQLite detected; skipping PostgreSQL GIN trigram index creation.")
        return

    print("Connecting to PostgreSQL database...")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # 1. Enable pg_trgm extension
        print("Enabling pg_trgm extension in PostgreSQL...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        print("[OK] pg_trgm extension enabled.")

        # 2. Create GIN Trigram Indexes for sub-second search
        indexes = [
            ("idx_records_name_trgm", "CREATE INDEX IF NOT EXISTS idx_records_name_trgm ON records USING gin (name gin_trgm_ops);"),
            ("idx_records_community_trgm", "CREATE INDEX IF NOT EXISTS idx_records_community_trgm ON records USING gin (community gin_trgm_ops);"),
            ("idx_records_bldg_trgm", "CREATE INDEX IF NOT EXISTS idx_records_bldg_trgm ON records USING gin (building_cluster gin_trgm_ops);"),
            ("idx_records_developer_trgm", "CREATE INDEX IF NOT EXISTS idx_records_developer_trgm ON records USING gin (developer gin_trgm_ops);"),
            ("idx_records_project_trgm", "CREATE INDEX IF NOT EXISTS idx_records_project_trgm ON records USING gin (project gin_trgm_ops);"),
            ("idx_records_mobile_trgm", "CREATE INDEX IF NOT EXISTS idx_records_mobile_trgm ON records USING gin (mobile_1 gin_trgm_ops);"),
            ("idx_records_status_community_dev", "CREATE INDEX IF NOT EXISTS idx_records_status_community_dev ON records (status, community, developer);"),
        ]

        for name, sql in indexes:
            print(f"Creating index '{name}'...")
            cur.execute(sql)
            print(f"[OK] Index '{name}' ready.")

        print("\nAll GIN Trigram Search Indexes successfully created and active in PostgreSQL!")

    except Exception as exc:
        print(f"Error creating indexes: {exc}")
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    enable_trigram_search_indexes()
