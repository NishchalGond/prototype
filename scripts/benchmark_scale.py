"""Seed a PostgreSQL database to N million records and time the real queries.

    python scripts/benchmark_scale.py --rows 20000000        # seed, then time
    python scripts/benchmark_scale.py --bench-only           # time what is there
    python scripts/benchmark_scale.py --rows 1000000 --drop  # start clean

Every performance decision in this codebase so far is an argument, not a
measurement: the trigram index, the partial indexes on the default view, the
batched dedup probes, the 20,000 count ceiling. All of them are reasoned about
a 20M-row table nobody has built. This makes the question answerable.

Seeding runs server-side from generate_series -- one INSERT..SELECT, no Python
loop, no round trips -- so 20M rows is minutes rather than hours. Values are
drawn to resemble the real distribution that matters for query plans: a long
tail of communities, ~40% of rows carrying a valid mobile, procedure values
spread over orders of magnitude. It is not realistic data, it is realistically
SHAPED data, which is what the planner responds to.

Timings come from EXPLAIN (ANALYZE, BUFFERS) on the exact statements the API
issues, so a slow result names the plan that caused it.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import psycopg2

# Query shapes the dashboard actually issues. Each is (label, sql).
# Kept as literal SQL rather than built through SQLAlchemy so the plan being
# measured is unambiguous and can be pasted straight into psql.
QUERIES = [
    ("default view, first page",
     """SELECT * FROM records
        WHERE status = 'VALID' AND has_valid_mobile
        ORDER BY procedure_value DESC NULLS LAST, bedroom DESC NULLS LAST,
                 name ASC NULLS LAST, id DESC
        LIMIT 50"""),
    ("default view, page 100 (offset 5000)",
     """SELECT * FROM records
        WHERE status = 'VALID' AND has_valid_mobile
        ORDER BY procedure_value DESC NULLS LAST, id DESC
        LIMIT 50 OFFSET 5000"""),
    ("default view filtered to one community",
     """SELECT * FROM records
        WHERE status = 'VALID' AND has_valid_mobile AND community = 'Dubai Marina'
        ORDER BY procedure_value DESC NULLS LAST, id DESC
        LIMIT 50"""),
    ("search, one token",
     """SELECT * FROM records WHERE search_text LIKE '%mohammed%' LIMIT 50"""),
    ("search, three tokens (BitmapAnd)",
     """SELECT * FROM records
        WHERE search_text LIKE '%mohammed%'
          AND search_text LIKE '%marina%'
          AND search_text LIKE '%heights%'
        LIMIT 50"""),
    ("search, phone fragment",
     """SELECT * FROM records WHERE mobile_digits LIKE '%505518569%' LIMIT 50"""),
    ("capped count (the ceiling that replaced COUNT(*))",
     """SELECT count(*) FROM (
          SELECT 1 FROM records WHERE status = 'VALID' AND has_valid_mobile
          LIMIT 20000) s"""),
    ("uncapped count, for comparison",
     """SELECT count(*) FROM records WHERE status = 'VALID' AND has_valid_mobile"""),
    ("facets from the materialised view",
     """SELECT field, value FROM mv_record_facets WHERE value <> ''
        ORDER BY field, value"""),
    ("dashboard stats from the materialised view",
     """SELECT * FROM mv_record_stats LIMIT 1"""),
    ("dedup probe: 1000 identity hashes",
     """SELECT DISTINCT identity_hash FROM records
        WHERE identity_hash IN (
          SELECT identity_hash FROM records TABLESAMPLE SYSTEM (0.01) LIMIT 1000)"""),
    ("dedup probe: property keys",
     """SELECT property_key, id, name FROM records
        WHERE property_key IN (
          SELECT property_key FROM records TABLESAMPLE SYSTEM (0.01)
          WHERE property_key IS NOT NULL LIMIT 1000)
          AND name IS NOT NULL AND status <> 'DUPLICATE'"""),
    # Sorts with no index behind them. Included precisely because they are the
    # suspected weak spot: the API exposes 13 sortable columns and only the
    # default view's are indexed.
    ("sort by size (no index)",
     """SELECT * FROM records WHERE status = 'VALID'
        ORDER BY size DESC NULLS LAST, id DESC LIMIT 50"""),
    ("sort by record_date (no index)",
     """SELECT * FROM records WHERE status = 'VALID'
        ORDER BY record_date DESC NULLS LAST, id DESC LIMIT 50"""),
]

SEED_SQL = """
INSERT INTO records (
    name, community, sub_community, building_cluster, unit_number,
    size, bedroom, party_type, mobile_1, email_address,
    property_type, developer, project, nationality,
    record_date, procedure_value,
    job_id, source_file, status, identity_hash, engine_version, created_at
)
SELECT
    (ARRAY['Mohammed Al Rashid','Sara Haddad','Omar Khalid','Layla Nasser',
           'Yusuf Aziz','Fatima Hassan','Ahmed Mansour','Noura Saleh'])[1 + (i %% 8)]
        || ' ' || (i %% 100000)::text,
    -- Zipf-ish: a few communities hold most rows, with a long tail. Uniform
    -- data would make every index look better than it is.
    (ARRAY['Dubai Marina','Jumeirah Village Circle','Business Bay',
           'Downtown Dubai','Dubai Hills Estate','DAMAC Hills 2','Al Barsha 1',
           'Palm Jumeirah','Arjan','Al Furjan'])[1 + (i %% 10) / (1 + (i %% 3))],
    'Sub ' || (i %% 400)::text,
    'Cluster ' || (i %% 5000)::text,
    (1000 + (i %% 9000))::text,
    500 + (i %% 4000),
    (1 + (i %% 5))::text || ' BR',
    CASE WHEN i %% 2 = 0 THEN 'Buyer' ELSE 'Seller' END,
    -- ~40%% carry a valid UAE mobile, matching the real contactable share.
    CASE WHEN i %% 5 < 2
         THEN '+9715' || (ARRAY['0','2','4','5','6','8'])[1 + (i %% 6)]
              || lpad((i %% 10000000)::text, 7, '0')
         ELSE NULL END,
    CASE WHEN i %% 7 = 0 THEN 'user' || i::text || '@example.com' ELSE NULL END,
    (ARRAY['Apartment','Villa','Townhouse','Plot','Office'])[1 + (i %% 5)],
    (ARRAY['Emaar Properties','DAMAC Properties','Nakheel','Sobha Realty',
           'Meraas'])[1 + (i %% 5)],
    'Project ' || (i %% 800)::text,
    (ARRAY['India','Pakistan','United Arab Emirates','United Kingdom',
           'Egypt'])[1 + (i %% 5)],
    timestamptz '2018-01-01' + (i %% 2900) * interval '1 day',
    -- Spread over orders of magnitude, like real transaction values.
    (100000 + (i %% 97) * 50000 + (i %% 7) * 1000000)::float8,
    1, 'benchmark_seed.csv', 'VALID',
    md5(i::text), 2, now()
FROM generate_series(%s, %s) AS i;
"""


def _connect(db_url):
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    return conn


def seed(cur, total: int, batch: int = 1_000_000) -> None:
    """Insert `total` rows server-side, in batches so progress is visible."""
    done = 0
    while done < total:
        n = min(batch, total - done)
        t0 = time.monotonic()
        cur.execute(SEED_SQL, (done + 1, done + n))
        done += n
        print(f"  seeded {done:,}/{total:,}  (+{n:,} in {time.monotonic()-t0:.1f}s)",
              flush=True)


def bench(cur) -> None:
    print(f"\n{'query':<48} {'ms':>10}  plan")
    print("-" * 100)
    for label, sql in QUERIES:
        try:
            cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)
            plan = cur.fetchone()[0][0]
            ms = plan["Execution Time"]
            node = plan["Plan"]["Node Type"]
            # Name the index when there is one; "Seq Scan" here is the finding.
            detail = plan["Plan"].get("Index Name", "")
            if not detail:
                sub = plan["Plan"].get("Plans") or []
                detail = next((p.get("Index Name", "") for p in sub
                               if p.get("Index Name")), "")
            flag = "  <-- SEQ SCAN" if "Seq Scan" in str(plan) else ""
            print(f"{label:<48} {ms:>10.1f}  {node} {detail}{flag}")
        except Exception as exc:
            print(f"{label:<48} {'n/a':>10}  {type(exc).__name__}: "
                  f"{str(exc).splitlines()[0][:40]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=0,
                    help="How many rows to seed before benchmarking.")
    ap.add_argument("--bench-only", action="store_true",
                    help="Skip seeding; time whatever is already there.")
    ap.add_argument("--drop", action="store_true",
                    help="Delete benchmark rows first (only rows this script wrote).")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url or "sqlite" in db_url.lower():
        print("Needs PostgreSQL. SQLite has none of the machinery being measured "
              "(generated columns, trigram indexes, materialised views).")
        return 1

    conn = _connect(db_url)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM records")
    existing = cur.fetchone()[0]
    print(f"records currently in table: {existing:,}")

    # Refuse to touch a table this script did not fill. Seeding 20M synthetic
    # rows into a live corpus would be unrecoverable without a restore.
    cur.execute("SELECT count(*) FROM records WHERE source_file <> 'benchmark_seed.csv'")
    real_rows = cur.fetchone()[0]
    if real_rows and not args.bench_only:
        print(f"REFUSING: {real_rows:,} rows were not written by this script. "
              f"Point DATABASE_URL at a scratch database, or use --bench-only.")
        return 1

    if args.drop:
        print("deleting previous benchmark rows...")
        cur.execute("DELETE FROM records WHERE source_file = 'benchmark_seed.csv'")

    if args.rows and not args.bench_only:
        print(f"seeding {args.rows:,} rows...")
        t0 = time.monotonic()
        seed(cur, args.rows)
        print(f"seeded in {time.monotonic()-t0:.0f}s")
        # Without fresh statistics the planner has no idea what it is holding
        # and every timing below measures the wrong plan.
        print("ANALYZE...")
        cur.execute("ANALYZE records")
        print("refreshing materialised views...")
        for view in ("mv_record_facets", "mv_record_stats"):
            try:
                cur.execute(f"REFRESH MATERIALIZED VIEW {view}")
            except Exception as exc:
                print(f"  {view}: {exc}")

    cur.execute("SELECT count(*), pg_size_pretty(pg_total_relation_size('records')) "
                "FROM records")
    n, size = cur.fetchone()
    print(f"\nbenchmarking against {n:,} rows, {size} on disk")
    bench(cur)

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
