"""Backfill developer from the UAE builders reference for all records
where developer is currently NULL.

Reads Community / Sub-Community / Project / Building-Cluster from each
record, matches against the reference workbook, and writes the developer
back.  Safe to run multiple times — only touches records with NULL developer.
"""
import json, os, sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.reference import load_reference, enrich, canon

# ── load reference ──────────────────────────────────────────────────────
ref = load_reference(str(ROOT / "Builders data" / "UAE_Development_Builders.xlsx"))
print(f"Reference loaded: {len(ref)} developments")

# ── connect to Supabase ────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

DB_URL = os.getenv("DATABASE_URL", "")
if "supabase" not in DB_URL and "neon" not in DB_URL:
    print("ERROR: DATABASE_URL does not look like Supabase. Aborting.")
    sys.exit(1)

import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(DB_URL)
conn.autocommit = False

# ── fetch records missing developer ────────────────────────────────────
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
    SELECT id, community, sub_community, building_cluster, project, developer,
           enriched_fields
    FROM records
    WHERE developer IS NULL OR TRIM(developer) = ''
""")
rows = cur.fetchall()
print(f"Records missing developer: {len(rows)}")

# ── enrich each record ────────────────────────────────────────────────
updated = 0
batch = []
for row in rows:
    fields = {
        "Community": row.get("community") or "",
        "Sub-Community": row.get("sub_community") or "",
        "Building/Cluster": row.get("building_cluster") or "",
        "Project": row.get("project") or "",
        "Developer": "",
    }
    enriched = enrich(fields, ref)
    if "developer" in enriched and fields.get("Developer"):
        # Merge enriched_fields
        existing = row.get("enriched_fields") or []
        if isinstance(existing, str):
            try:
                existing = json.loads(existing)
            except Exception:
                existing = []
        merged = list(set(existing + enriched))

        batch.append((fields["Developer"], json.dumps(merged), row["id"]))
        updated += 1

print(f"Records to enrich: {updated}")

# ── batch update ───────────────────────────────────────────────────────
BATCH_SIZE = 500
for i in range(0, len(batch), BATCH_SIZE):
    chunk = batch[i:i + BATCH_SIZE]
    cur2 = conn.cursor()
    for dev, ef, rid in chunk:
        cur2.execute(
            "UPDATE records SET developer = %s, enriched_fields = %s WHERE id = %s",
            (dev, ef, rid),
        )
    conn.commit()
    print(f"  committed batch {i // BATCH_SIZE + 1}  ({len(chunk)} rows)")

cur.close()
conn.close()
print(f"\nDone. Enriched {updated} records with developer from reference.")
