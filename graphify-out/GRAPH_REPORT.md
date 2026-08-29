# Graph Report - Prototype  (2026-08-29)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 993 nodes · 2222 edges · 58 communities (52 shown, 6 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 144 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3d4acae0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Bulk Postgres Loader
- React Frontend Components
- ORM Models & Alembic Env
- Format Detection & Header Mapping
- Frontend Build Dependencies
- Job Control API
- Number Normalization Tests
- DB Sessions & Data Repair Scripts
- Dedup Heuristics & Hardening Tests
- Field Cleaning Functions
- Product Architecture (Docs)
- Ingestion Orchestrator & Enrichment
- Property Reference (Portal Data)
- Auth Login & Tokens
- Cross-Register Dedup & Reprocessing
- Records Query, Export & Dashboard
- Security, Bootstrap & Erasure Schemas
- Outreach: Leads, Activity & Verdicts
- Free-Text Search Acceleration
- Pydantic API Schemas
- Column Alias Management
- Railway Deploy Config
- Supabase Root Package
- Record Validation & Engine Version
- PDPL Erasure
- Docs & PDF Generation
- Vercel Deploy Config
- User Admin Endpoints
- Deprecated Trigram Script
- JWT Dependency Guards
- Root Package Entry
- Application Settings
- Upload & Background Job Runner
- Developer Canonicalization
- Phone Normalization (E.164)
- Online Index Migration Script
- Date Cleaning
- Size & Number Cleaning (sq.m to sq.ft)
- Baseline & Dedup Migrations
- Migration Runner
- System Architecture (Docs)
- Scale Benchmark Harness
- Job Signal Migration
- Search Acceleration Migration
- Global Exception Handling
- Health Check Endpoint
- Job Signal Model

## God Nodes (most connected - your core abstractions)
1. `User` - 65 edges
2. `Record` - 61 edges
3. `ProcessingJob` - 32 edges
4. `Base` - 28 edges
5. `_get_or_create_lead()` - 25 edges
6. `UserRole` - 24 edges
7. `Processor` - 24 edges
8. `SourceFile` - 23 edges
9. `apiFetch()` - 22 edges
10. `load_reference()` - 20 edges

## Surprising Connections (you probably didn't know these)
- `test_generated_columns_track_updates()` --uses--> `Record`  [INFERRED]
  tests/test_search_acceleration.py → backend/app/models/models.py
- `test_has_valid_mobile_is_computed_by_the_database()` --uses--> `Record`  [INFERRED]
  tests/test_search_acceleration.py → backend/app/models/models.py
- `test_search_text_is_populated_and_lowercased()` --uses--> `Record`  [INFERRED]
  tests/test_search_acceleration.py → backend/app/models/models.py
- `ingest_file()` --uses--> `Record`  [INFERRED]
  scripts/direct_ingest_all.py → backend/app/models/models.py
- `main()` --uses--> `Record`  [INFERRED]
  scripts/direct_ingest_all.py → backend/app/models/models.py

## Import Cycles
- None detected.

## Communities (58 total, 6 thin omitted)

### Community 0 - "Bulk Postgres Loader"
Cohesion: 0.27
Nodes (11): bulk_insert_records(), insert_errors(), insert_job(), insert_source_file(), main(), pg_connect(), Path, Batch-process all Dubai Hills XLSX files directly into Supabase. Steps: 1.… (+3 more)

### Community 1 - "React Frontend Components"
Cohesion: 0.07
Nodes (44): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema, App(), AuthLockScreen(), CallQueue() (+36 more)

### Community 2 - "ORM Models & Alembic Env"
Cohesion: 0.09
Nodes (42): Alembic environment. The database URL is taken from the application settings…, run_migrations_offline(), _url(), Fail jobs whose worker is gone. Called once at startup. A redeploy, OOM kill or…, reap_stale_jobs(), Base, JobStatus, ProcessingError (+34 more)

### Community 3 - "Format Detection & Header Mapping"
Cohesion: 0.06
Nodes (67): detect_format(), find_header_row(), _known_header_tokens(), _looks_like_data(), _norm_cell(), open_source(), Exception, Path (+59 more)

### Community 4 - "Frontend Build Dependencies"
Cohesion: 0.06
Nodes (31): dependencies, lucide-react, react, react-dom, tailwindcss, @tailwindcss/vite, devDependencies, oxlint (+23 more)

### Community 5 - "Job Control API"
Cohesion: 0.21
Nodes (23): cancel_job(), get_global_errors_summary(), get_job(), get_job_errors(), get_job_errors_aggregate(), _job_out(), list_jobs(), pause_job() (+15 more)

### Community 7 - "DB Sessions & Data Repair Scripts"
Cohesion: 0.10
Nodes (6): get_db(), get_read_db(), Session, _sqlite_pragmas(), listens_for, Fast SQL-based database reclassification and phone cleaning script. Performs…

### Community 8 - "Dedup Heuristics & Hardening Tests"
Cohesion: 0.07
Nodes (29): Any, ExportAuditLog, RecordStatus, clean_community(), calculate_name_similarity(), extract_property_key(), _first_nonblank(), normalize_name_tokens() (+21 more)

### Community 9 - "Field Cleaning Functions"
Cohesion: 0.22
Nodes (12): clean_bedroom(), clean_email(), clean_name(), clean_nationality(), clean_party_type(), clean_property_type(), clean_text(), clean_unit() (+4 more)

### Community 10 - "Product Architecture (Docs)"
Cohesion: 0.20
Nodes (10): Batch Studio, Cleaning Engine, Developer Reference Resolver, Header Remapping Studio, Neumorphic UI, OpenPyXL, Pandas, Phone Standardizer (+2 more)

### Community 11 - "Ingestion Orchestrator & Enrichment"
Cohesion: 0.06
Nodes (47): BatchOutcome, Batch processing orchestrator. Flow per the prototype spec: read -> map ->…, _alternation(), canon(), clean_filename_community(), Development, _emirate_of(), enrich() (+39 more)

### Community 12 - "Property Reference (Portal Data)"
Cohesion: 0.06
Nodes (44): _building_key(), _iter_sheets(), _key(), load_property_reference(), _norm_header(), _parse_location(), PropertyFacts, PropertyReference (+36 more)

### Community 13 - "Auth Login & Tokens"
Cohesion: 0.18
Nodes (16): CreateUserRequest, login(), LoginRequest, BaseModel, post, Authentication and User Management REST Endpoints., Authenticate user with email & password and return signed JWT., TokenResponse (+8 more)

### Community 14 - "Cross-Register Dedup & Reprocessing"
Cohesion: 0.06
Nodes (51): engine_status(), BackgroundTasks, get, post, Session, Re-derive stale records from their stored source files. Queues up to `limit`…, Jobs holding at least one record below the current engine version. Ordered…, How much of the corpus was produced by which engine version. (+43 more)

### Community 15 - "Records Query, Export & Dashboard"
Cohesion: 0.17
Nodes (22): dashboard_stats(), export_records(), _facet_cache(), filter_options(), get_record(), get_record_audits(), list_records(), _matview() (+14 more)

### Community 16 - "Security, Bootstrap & Erasure Schemas"
Cohesion: 0.17
Nodes (19): ErasureIn, ErasureOut, BaseModel, Right to erasure. The platform holds names, phone numbers and email addresses…, Reprocessing: re-deriving stored records with the current engine rules. A…, hash_password(), Enterprise Security and RBAC Authentication Core. Provides: - bcrypt password…, RBAC dependency factory checking user role. (+11 more)

### Community 17 - "Outreach: Leads, Activity & Verdicts"
Cohesion: 0.06
Nodes (84): ActivityIn, ActivityOut, clear_verdict(), _get_or_create_lead(), LeadOut, LeadPatch, list_leads(), log_activity() (+76 more)

### Community 18 - "Free-Text Search Acceleration"
Cohesion: 0.10
Nodes (31): build_search_filter(), _escape_like(), has_indexable_token(), _phone_variants(), Free-text search query construction. Replaces the original `ILIKE '%q%'` fan-…, True when at least one token is long enough for the trigram index., Return a SQLAlchemy predicate for a free-text query, or None. Every token must…, Neutralise LIKE metacharacters so user input is matched literally. (+23 more)

### Community 19 - "Pydantic API Schemas"
Cohesion: 0.15
Nodes (14): ErrorResponse, JobDetail, JobOut, ORMModel, Page, ProcessingErrorOut, BaseModel, datetime (+6 more)

### Community 20 - "Column Alias Management"
Cohesion: 0.20
Nodes (12): add_alias(), column_mappings(), delete, post, Expose the mapping layer so the dashboard can show why a column landed where., Save updated mapping config to disk and reload in-memory engine structures., Add a new custom header alias for a target field and persist permanently., Remove a custom header alias permanently. (+4 more)

### Community 21 - "Railway Deploy Config"
Cohesion: 0.22
Nodes (8): build, builder, dockerfilePath, deploy, restartPolicyMaxRetries, restartPolicyType, startCommand, $schema

### Community 22 - "Supabase Root Package"
Cohesion: 0.25
Nodes (7): ai, dependencies, ai, @supabase/ssr, @supabase/supabase-js, @supabase/ssr, @supabase/supabase-js

### Community 23 - "Record Validation & Engine Version"
Cohesion: 0.11
Nodes (16): Ingestion engine. ENGINE_VERSION identifies the set of cleaning, validation,…, count_populated_fields(), identity_hash(), is_valid_contact(), is_valid_property_context(), json_safe(), Record validation + transformation into the DB row shape. Rules encode the…, Stable identity for dedup. Person + location. Mobile alone is unsafe (shared… (+8 more)

### Community 24 - "PDPL Erasure"
Cohesion: 0.12
Nodes (33): apply_erasures(), erase_record(), list_erasures(), get, post, Session, Erase the person behind a record, now and on every future ingest. Idempotent:…, The erasure register, newest first. What an auditor asks to see. (+25 more)

### Community 25 - "Docs & PDF Generation"
Cohesion: 0.50
Nodes (3): generate_pdf_from_markdown(), Path, Generate comprehensive, beautifully styled PDF documentation and organize all…

### Community 26 - "Vercel Deploy Config"
Cohesion: 0.50
Nodes (3): builds, routes, version

### Community 27 - "User Admin Endpoints"
Cohesion: 0.21
Nodes (14): ADMIN, create_user(), get_me(), list_users(), Depends, get, put, Session (+6 more)

### Community 29 - "JWT Dependency Guards"
Cohesion: 0.21
Nodes (14): decode_access_token(), get_current_user(), get_current_user_optional(), Depends, Session, Strict authenticated user dependency., Ensure user has unmasked export permission., Decode and verify JWT signature and expiration. (+6 more)

### Community 38 - "Application Settings"
Cohesion: 0.33
Nodes (5): _finalise(), Central configuration. All values overridable via .env / environment., Validate the settings that must not be wrong in production., Settings, BaseSettings

### Community 39 - "Upload & Background Job Runner"
Cohesion: 0.17
Nodes (11): inspect_file_endpoint(), BackgroundTasks, Accept an Excel/CSV upload, register it, and (by default) start processing., Inspect file column headers without registering a job., Process one job. Runs in a FastAPI background task with its own session., run_job(), upload_file(), Refresh of the cached aggregates that back the dashboard. `mv_record_facets`… (+3 more)

### Community 40 - "Developer Canonicalization"
Cohesion: 0.50
Nodes (4): clean_developer(), _developer_key(), Reduce a developer string to its brand token for canonical lookup., Canonicalise a developer name, or None when the value names no builder. Unknown…

### Community 41 - "Phone Normalization (E.164)"
Cohesion: 0.50
Nodes (4): clean_phone(), clean_phones_multi(), Extract and normalize all phone numbers from a value (which may contain…, Return (E.164-ish normalized number, flag). Handles the defects the audit…

### Community 42 - "Online Index Migration Script"
Cohesion: 0.67
Nodes (3): _facet_view_sql(), main(), Apply migration 9c41ab7de205 to a large PostgreSQL table without downtime.…

### Community 43 - "Date Cleaning"
Cohesion: 0.67
Nodes (3): clean_date(), datetime, timedelta

### Community 44 - "Size & Number Cleaning (sq.m to sq.ft)"
Cohesion: 0.67
Nodes (3): clean_number(), clean_size(), Clean size number, automatically converting Sqm (m2) to Sq.Ft (1 m2 = 10.76391…

### Community 46 - "Migration Runner"
Cohesion: 0.36
Nodes (6): _alembic_config(), current_revision(), Run Alembic migrations at startup, including first-time adoption. The database…, Bring the database up to the latest revision. Safe to call repeatedly., upgrade_to_head(), Config

### Community 47 - "System Architecture (Docs)"
Cohesion: 0.38
Nodes (7): DataLink Engine, FastAPI Backend, React 18 + Vite Frontend, SQLModel / SQLAlchemy, Supabase PostgreSQL, Tailwind CSS, Vite React Template

### Community 48 - "Scale Benchmark Harness"
Cohesion: 0.43
Nodes (6): bench(), _connect(), main(), Seed a PostgreSQL database to N million records and time the real queries.…, Insert `total` rows server-side, in batches so progress is visible., seed()

### Community 49 - "Job Signal Migration"
Cohesion: 0.50
Nodes (3): _job_fk_name(), Actual name of the records.job_id foreign key in this database. Autogenerate…, upgrade()

### Community 51 - "Global Exception Handling"
Cohesion: 0.50
Nodes (4): Exception, Request, unhandled(), exception_handler

### Community 56 - "Health Check Endpoint"
Cohesion: 0.67
Nodes (3): health(), get, Liveness + database reachability. A health check that only proves the process…

## Knowledge Gaps
- **52 isolated node(s):** `BatchOutcome`, `react/rules-of-hooks`, `$schema`, `STAGE_STYLE`, `ICON_FOR` (+47 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `Job Control API` to `ORM Models & Alembic Env`, `Upload & Background Job Runner`, `Dedup Heuristics & Hardening Tests`, `Auth Login & Tokens`, `Cross-Register Dedup & Reprocessing`, `Records Query, Export & Dashboard`, `Security, Bootstrap & Erasure Schemas`, `Outreach: Leads, Activity & Verdicts`, `Column Alias Management`, `PDPL Erasure`, `User Admin Endpoints`, `JWT Dependency Guards`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `Alembic` connect `Baseline & Dedup Migrations` to `ORM Models & Alembic Env`, `Migration Runner`, `System Architecture (Docs)`, `Job Signal Migration`, `Search Acceleration Migration`, `Cross-Register Dedup Migration`, `Engine Version Lineage Migration`, `Leads & Activities Migration`, `Erasure Requests Migration`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `Record` connect `Cross-Register Dedup & Reprocessing` to `ORM Models & Alembic Env`, `Job Control API`, `Dedup Heuristics & Hardening Tests`, `Records Query, Export & Dashboard`, `Security, Bootstrap & Erasure Schemas`, `Outreach: Leads, Activity & Verdicts`, `Free-Text Search Acceleration`, `PDPL Erasure`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `User` (e.g. with `get_me()` and `list_users()`) actually correct?**
  _`User` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `Record` (e.g. with `ingest_file()` and `main()`) actually correct?**
  _`Record` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `ProcessingJob` (e.g. with `reprocess()` and `setup_database()`) actually correct?**
  _`ProcessingJob` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Base` (e.g. with `db()` and `db()`) actually correct?**
  _`Base` has 7 INFERRED edges - model-reasoned connections that need verification._