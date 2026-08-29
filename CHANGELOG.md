# What changed

Everything below landed on `main` in two merges: `c100ccf` (data quality, scale,
reprocessing) and `3d4acae` (outreach, compliance, feedback loop).

**155 tests** pass, up from 38. Migration head `a7b4e9f1c260`.

---

## 1. Six data-corruption defects

Each was silently wrong on every ingest, and each now has a regression test that
fails without the fix.

| # | Defect | Effect |
|---|--------|--------|
| 1 | `clean_size` was never given the column header | sq.m columns stored **10.76x too small** |
| 2 | The header was only read for non-string values | so fix 1 still did nothing for anything read from a file |
| 3 | Trailing digits stripped before the canonical lookup | `Al Barsha 1/2/3`, `Al Quoz 1-4`, `DAMAC Hills 2` all collapsed into one community |
| 4 | Enrichment wrote development categories into Property Type | records looked complete while holding `Master-planned community` where a dwelling type belongs |
| 5 | The Dubai Hills fallback stamped Emaar on the whole estate | including Ellington House, built by Ellington Properties |
| 6 | No developer canonicalisation existed | `EMAAR`, `Emaar Properties`, `EMAAR PROPERTIES L.L.C` were three separate filter values |

Defect 3 mattered more than it looks: `community` feeds `identity_hash`, so it
was corrupting deduplication as well as display.

Defect 1 is worth remembering. The unit test passed the whole time, because it
called `clean_size(100, raw_header="Area (Sqm)")` directly while the pipeline
called `clean_size(value)` with no header. **The test tested the helper, not the
wiring.**

## 2. Search and scale

- Free-text search rewritten onto a generated `search_text` column with a single
  GIN trigram index. The old `ILIKE` across 13 columns had one unindexable
  branch inside an `OR`, which forces a sequential scan and made the existing
  trigram indexes dead weight. Multi-token queries now match across columns, so
  `Mohammed Ahmed Marina Heights` finds the owner.
- `has_valid_mobile` became a stored generated column instead of three regexes
  evaluated per row on every page load, with partial indexes built on it that
  match the default sort term for term.
- Facets and dashboard aggregates moved to materialised views, refreshed when a
  job finishes, with a live-query fallback so a missing view degrades to slow
  rather than broken.
- Row counts stop at 20,000 and the UI shows `20,000+`, instead of presenting a
  floor as an exact total.
- Connection pool defaults cut from 20+40 / 25+50 to 5+10 / 10+20. The old
  ceilings allowed 135 connections from a single worker, which exceeds
  PostgreSQL's default `max_connections` on its own — the failure at ~60 users
  was the database refusing connections, not slow queries.

## 3. Deduplication across registers

`seen_hashes` was filtered to `source_file == <this file>`, and the fuzzy tier
lived only for one `process()` call. The same owner arriving in two builder
registers was stored twice, both `VALID` — the exact duplicate this platform
exists to collapse.

`DedupIndex` now probes the database one batch at a time: **three indexed
queries per 1,000 rows** rather than three per row. A generated `property_key`
makes the fuzzy blocking key indexable, and its SQL and Python definitions are
pinned together by a test, because divergence would silently stop matches rather
than fail loudly. `fuzzy_matched_id` is finally populated — the column existed
and was never written.

## 4. Property Type: 40% → 82%

Present in only 41% of source rows and, where present, in registry vocabulary
(`Unit`, `Flat`, `Land`) rather than what the desk filters on.

Structural inference was measured first and **does not work**: `FLOOR`, the one
signal separating an apartment from a villa, is populated in 0% of sampled rows.
So the value comes from your Property Finder export (90,807 listings) via a
location-keyed reference matching at three precisions, each with its own
dominance threshold. A 50/50 mixed tower fills nothing.

Held-out accuracy where it predicts: **70%**, or **81%** excluding rows whose
register value is itself junk. The residual error is almost entirely Plot vs
Villa — a land-registry / market vocabulary disagreement, not a mistake.

The distilled index (560KB) is committed, so a clean clone enriches without the
23MB export present.

## 5. Reprocessing — the fix that reaches old data

Every correctness fix above changes what the pipeline *would* produce, not what
it already produced. Records now carry `engine_version`:

```
GET  /api/maintenance/engine-status   what is stale, and how much
POST /api/maintenance/reprocess       re-derive it, oldest job first
```

Reprocessing reuses the restart path, which deletes a job's rows before
rewriting them, so it converges rather than duplicating.

## 6. Ingest out of the web process

`worker.py` polls for queued jobs. No Redis, no Celery — the jobs table already
had states, control signals, a heartbeat and a reaper; a broker would have been
a second source of truth. Safety is one compare-and-set at the top of `run_job`,
so the API's background task, the reprocess endpoint and any number of workers
can all fire on the same id without coordination.

## 7. Outreach, and the feedback loop

The platform could find a contactable owner and had nowhere to record that
anyone called them.

- **Leads and an append-only activity log**, keyed by `identity_hash` rather
  than `record_id`, so call history survives the reprocessing that deletes and
  rewrites records. `relink_leads()` reattaches afterwards; a lead whose hash
  changed surfaces at `/leads/orphans` instead of vanishing.
- **Log from the Record Inspector** — one submit logs the activity, moves the
  stage, assigns the owner and schedules the callback.
- **Call Queue** — `?mine=true&due=true`, the morning list.
- **Contact verdicts** are the part with real leverage. A salesperson who dials
  and hears *wrong number* has produced better evidence about that number than
  any rule in the pipeline: `has_valid_mobile` only says a number is well
  **formed**; only a call says it is **wrong**. `WRONG_NUMBER`, `NOT_OWNER` and
  `SOLD` suppress the record from the list and exports and survive reprocessing.
  `UNREACHABLE` deliberately does not — nobody answering is not evidence.
  `/leads/needs-new-number` is the re-sourcing list: known-valuable properties
  with a known-bad contact.
- Verdicts are **attributable and reversible**. One click hides a record from
  the whole desk, so it records who judged it and can be undone.

## 8. Compliance

- `DO_NOT_CONTACT` is enforced on the list and export paths, not merely stored.
  An opt-out that still appears in the CSV is a note, not an opt-out.
- **Right to erasure** clears the person (name, phones, email, nationality, and
  `extras`, which carries passport and date-of-birth details from the owner
  registers) while keeping the property. It is re-applied after **every** ingest,
  because records are rebuilt from a source file that still contains them — a
  redaction without a standing request is undone by the next reprocess, and
  there is a test that proves exactly that.
- `/erasures` is the register an auditor asks for; `/erasures/verify` reports
  whether any standing request still has personal data against it.

## 9. Infrastructure and correctness

- **CI** (there was none): pytest, frontend lint and build, and every migration
  applied to a real PostgreSQL 16 **including a full rollback and re-apply**.
  The migrations carry PostgreSQL-only SQL that SQLite cannot parse, so nothing
  else exercises it.
- **`PRAGMA foreign_keys=ON`** for SQLite. Without it SQLite ignores every
  `ON DELETE` clause in the schema, so dev silently disagreed with production
  about referential integrity — including a `records.job_id` CASCADE added
  earlier specifically to stop orphaned rows. Turning it on exposed two existing
  tests inserting records against a job that did not exist.
- **`record_edits_audit` no longer cascades.** Reprocessing used to delete every
  hand-correction and the record of who made it. A correction is no more
  derivable from a source file than a phone call is.
- **`USAGE` routed to extras.** It was aliased to Property Type, putting area
  zones like `Airport` into a dwelling-type field — 29 rows in a 1,328-row
  sample.

---

## Known gaps

- **Nothing here has been measured at scale.** Every performance claim is an
  argument about a 20M-row table that does not exist yet.
  `scripts/benchmark_scale.py` seeds one and runs `EXPLAIN (ANALYZE, BUFFERS)`
  over the real query shapes, flagging sequential scans. It needs a reachable
  PostgreSQL and has never run.
- **13 sortable columns, only the default view's are indexed.** `size` and
  `record_date` have nothing behind them. Deliberately not fixed with
  speculative indexes — each costs write throughput on every ingest. Measure
  first.
- **Two identical copies of `column_mapping.json`** exist, at the repo root and
  in `engine/resources/`. Only the second is loaded. This already caused one
  wasted fix.
- **Retention.** Erasure covers requests; nothing expires data by age.
- **The records table is not keyboard navigable.** Rows are `<tr onClick>` with
  no role or key handler.
- **Dashboard tiles and the record list report different totals** by design —
  tiles count what the database holds, the list shows what the desk may work.
  `suppressed_records` now explains the gap rather than leaving it a mystery.

## Running it

```bash
alembic upgrade head          # or scripts/apply_search_indexes_online.py at scale
python run.py                 # API
python worker.py              # ingest, separately
```
