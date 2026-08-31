# Purges unidentifiable artifact rows and duplicate records
"""Delete records that carry no information, and reclaim the space.

    python scripts/cleanup_bad_records.py            # report only, deletes nothing
    python scripts/cleanup_bad_records.py --apply    # actually delete
    python scripts/cleanup_bad_records.py --apply --vacuum

WHAT THIS DELETES, AND WHY ONLY THIS

Three categories, all of which are provably redundant rather than merely
low-quality:

  DUPLICATE      the dedup engine already matched these to another row that is
                 still present. Deleting a duplicate loses nothing.
  identifies
  nobody         no name, no phone, no email, no community, no unit, no plot.
                 There is no person and no property in the row.
  header
  artefacts      "Total Owner Details" and similar parsed out of a spreadsheet
                 heading into the community column.

WHAT THIS DELIBERATELY DOES NOT DELETE

INCOMPLETE. It is 60% of the table and looks like an obvious cleanup target,
and deleting it would be a serious mistake: 117,763 of those rows carry BOTH a
name and a phone number. They are contactable people. They were classified
INCOMPLETE by an engine that, among other things, could not read Property Type
for 60% of rows, collapsed numbered communities together, and stored square
metres as square feet.

Those defects are fixed. Reprocessing (POST /api/maintenance/reprocess) will
promote an unknown but substantial share of them to VALID. Delete them first
and that is unrecoverable -- the source files can be re-ingested, but only if
they still exist, and the outreach history attached to them cannot be.

So: run this, then reprocess, then look at what is still INCOMPLETE.

REQUIRES WRITE ACCESS
A project over its storage quota is switched read-only by Supabase, and that is
enforced below the session setting -- SET default_transaction_read_only = off
appears to succeed and writes still fail. There is no client-side way around
it. Restore write access first.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

import psycopg2

# Each is (label, WHERE clause). Kept separate so the report says which rule
# matched what, rather than one opaque total.
RULES = [
    ("marked DUPLICATE by dedup",
     "status = 'DUPLICATE'"),
    ("identifies nobody and locates nothing",
     "name IS NULL AND mobile_1 IS NULL AND email_address IS NULL "
     "AND community IS NULL AND unit_number IS NULL AND plot_number IS NULL"),
    ("community is a spreadsheet header artefact",
     "lower(community) LIKE '%owner detail%' OR lower(community) LIKE '%total owner%'"),
]

COMBINED = " OR ".join(f"({c})" for _, c in RULES)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Delete. Without this, nothing is written.")
    ap.add_argument("--vacuum", action="store_true",
                    help="VACUUM FULL afterwards to return the space to disk. "
                         "Takes an ACCESS EXCLUSIVE lock for the duration.")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url or "sqlite" in db_url.lower():
        print("Needs PostgreSQL.")
        return 1

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT count(*), pg_size_pretty(pg_database_size(current_database())) "
                "FROM records")
    before, size = cur.fetchone()
    print(f"records: {before:,}   database: {size}\n")

    total = 0
    for label, cond in RULES:
        cur.execute(f"SELECT count(*) FROM records WHERE {cond}")
        n = cur.fetchone()[0]
        total += n
        print(f"  {label:<46}{n:>9,}")
    cur.execute(f"SELECT count(*) FROM records WHERE {COMBINED}")
    combined = cur.fetchone()[0]
    print(f"  {'COMBINED (rules overlap)':<46}{combined:>9,}"
          f"  {100 * combined / before:.1f}%\n")

    # Stated every run, not just the first: this is the mistake the script
    # exists to prevent.
    cur.execute("""SELECT count(*) FROM records WHERE status = 'INCOMPLETE'
                   AND name IS NOT NULL AND mobile_1 IS NOT NULL""")
    contactable = cur.fetchone()[0]
    print(f"NOT deleted: {contactable:,} INCOMPLETE rows have a name AND a phone.")
    print("Reprocess before judging those -- the engine that rejected them has\n"
          "since been corrected.\n")

    if not args.apply:
        print("Report only. Re-run with --apply to delete.")
        conn.close()
        return 0

    cur.execute(f"DELETE FROM records WHERE {COMBINED}")
    print(f"deleted {cur.rowcount:,} row(s)")

    if args.vacuum:
        # Plain DELETE marks rows dead but returns nothing to the filesystem,
        # which is the whole point when the goal is getting under a quota.
        print("VACUUM FULL records ... (table is locked until it finishes)")
        cur.execute("VACUUM FULL records")
        cur.execute("ANALYZE records")

    cur.execute("SELECT count(*), pg_size_pretty(pg_database_size(current_database())) "
                "FROM records")
    after, size_after = cur.fetchone()
    print(f"\nrecords: {after:,}   database: {size_after}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
