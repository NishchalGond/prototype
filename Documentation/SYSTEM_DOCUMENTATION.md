# 📖 DataLink Engine — Complete System & Architecture Documentation

> **Document Version**: 2.1.0  
> **Status**: Production Ready / Verified  
> **Target Audience**: Technical Reviewers, Solution Architects, Data Engineers, QA Teams  
> **Primary Development Environment**: Visual Studio Code (VS Code)

---

## 1. Executive Summary & Objective

**DataLink Engine** is a high-throughput, fault-tolerant real estate data normalization, enrichment, and ingestion platform. It transforms disparate, messy, multi-builder Excel (`.xlsx`, `.xls`) and CSV spreadsheets into a canonical, outreach-ready relational dataset stored in PostgreSQL (Supabase).

The system operates on a **strictly linear, unidirectional pipeline**:
$$\text{Raw File} \longrightarrow \text{Inspect/Map} \longrightarrow \text{Clean} \longrightarrow \text{Validate} \longrightarrow \text{Enrich (UAE Reference)} \longrightarrow \text{Deduplicate & Classify} \longrightarrow \text{PostgreSQL Storage} \longrightarrow \text{Explorer / Export}$$

---

## 2. Technology Stack & Tooling

The platform was developed and tested using **Visual Studio Code (VS Code)** with a dedicated Python virtual environment (`.venv`) and Node.js toolchain.

| Layer | Technology | Version | Purpose & Rationale |
|---|---|---|---|
| **IDE / Tooling** | **Visual Studio Code (VS Code)** | 1.85+ | Primary development environment for Python, React, SQL, and Git version control. |
| **Frontend UI** | **React** + **Vite** | React 18, Vite 5.0 | High-performance component-driven interface with sub-millisecond HMR and instant state updates. |
| **Design System** | **Vanilla CSS + Neumorphism** | CSS Variables | Tactile White & Dark Slate Neumorphic UI with soft 3D elevation, debossed insets, and high-contrast typography. |
| **Icons** | **Lucide React** | 0.344+ | Crisp, accessible SVG icon library. |
| **Backend Framework**| **Python + FastAPI** | Python 3.12, FastAPI 0.110+ | Asynchronous REST backend with automatic OpenAPI documentation and strict Pydantic v2 data validation. |
| **Web Server** | **Uvicorn** | 0.28+ | Lightning-fast ASGI web server. |
| **Data Processing** | **Pandas & OpenPyXL** | 2.2+, 3.1+ | Memory-bounded tabular data streaming, robust header extraction, and multi-sheet parsing. |
| **Database ORM** | **SQLAlchemy** | 2.0+ | Declarative models, connection pooling, and atomic batch transactions. |
| **Database** | **PostgreSQL (Supabase)** | PG 15+ | Transactional ACID storage with JSONB support, composite indexing, and connection pooling. |
| **Cloud Hosting** | **Vercel** (Frontend) + **Railway** (Backend) | Production | Global edge delivery with automated CI/CD from GitHub. |

---

## 3. Architecture & Data Flow

```
                           ┌──────────────────────────────────────────────────────────┐
                           │          React 18 + Vite Neumorphic Frontend             │
                           │  • Password Auth Lock Screen (`dev123`)                  │
                           │  • Universal Multi-File / Folder Drag & Drop Upload      │
                           │  • Real-Time Polling Job Tracker & Live Progress Bar     │
                           │  • Pause, Resume & Stop Batch Controls                   │
                           │  • Filtered Dataset Explorer & Export Studio (XLSX/CSV)  │
                           └────────────────────────────┬─────────────────────────────┘
                                                        │ HTTP REST (JSON / Multipart)
                                                        ▼
                           ┌──────────────────────────────────────────────────────────┐
                           │               FastAPI Python 3.12 Backend                │
                           │  • Boundary Controller & Upload Buffer                   │
                           │  • Background Worker Task Orchestrator & Signal Bus      │
                           │  • Filter Query Builder & Streaming Export Engine        │
                           └────────────────────────────┬─────────────────────────────┘
                                                        │
                                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         DataLink Core Processing Engine                                             │
├───────────────────┬───────────────────┬───────────────────┬───────────────────┬───────────────────┬─────────────────┤
│ 1. Header Mapping │ 2. Data Cleaning  │ 3. Validation     │ 4. Enrichment     │ 5. Deduplication  │ 6. Batch Commit │
│ Target Catalog of │ • Phone E.164     │ 4 Core Statuses:  │ Auto-populates    │ SHA-256 identity  │ In-memory chunk │
│ 23 canonical      │ • Area sqm ➔ sqft │ VALID, INCOMPLETE,│ Community & Dev   │ hash across batch │ of 500-1000     │
│ fields + Remap    │ • Casing & Trim   │ DUPLICATE, INVALID│ from filename & DB│ & database        │ rows per commit │
└───────────────────┴───────────────────┴───────────────────┴───────────────────┴───────────────────┴─────────────────┘
                                                        │
                                                        ▼
                           ┌──────────────────────────────────────────────────────────┐
                           │             PostgreSQL Database (Supabase)               │
                           │  • `records`: Cleaned canonical records (All Statuses)   │
                           │  • `processing_jobs`: Job execution audit & metrics      │
                           │  • `processing_errors`: Row-level failure trail          │
                           │  • `source_files`: File signatures & SHA-256 metadata    │
                           └──────────────────────────────────────────────────────────┘
```

---

## 4. Pipeline Stages & Execution Scenarios

### Stage 1: Ingestion, Inspection & Universal Drag-and-Drop
- **Folder & File Drop**: Users can drag and drop individual Excel (`.xlsx`, `.xls`) or CSV files, or drop **entire folders** from anywhere on their operating system. The browser recursively traverses directory trees to locate tabular data files.
- `POST /api/upload/inspect` examines the workbook headers, row counts, and sheet roles without writing to the database.
- Files named with `"consolidated"` are tagged as `Pre-Consolidated File` to avoid re-processing redundant master registers.

### Stage 2: Canonical Column Mapping
- The engine maps raw source headers (e.g., `Client Name`, `Mobile Number`, `Flat No`, `Gross Area`) against **23 standard fields**.
- **Tie-Breaking Preference**: When sheets contain multiple phone columns (e.g., `PHONE` and `MOBILE`), higher-ranked columns (such as `MOBILE` with direct cell numbers) take precedence, while lower-ranked columns cascade to `Mobile 2` or `Mobile 3` so no data is lost.
- Users can review or override mappings in the interactive **Header Remapping Studio** before starting the job.

### Stage 3: Data Cleaning & Normalization
- **Phone Numbers**: Normalizes international and UAE numbers to standard E.164 formats (`+971...`, `+1...`, `+44...`).
- **Surface Area**: Automatically converts square meters to square feet using the exact ratio $1 \text{ m}^2 = 10.7639 \text{ sq.ft}$.
- **Text & Casing**: Strips noise characters, unifies letter casing, and decouples buyer names from corporate builder names.

### Stage 4: Record Status Classification Scenarios

Every processed row is categorized into one of **four deterministic statuses**:

| Record Status | Classification Criteria | Storage & UI Behavior |
|---|---|---|
| **`VALID`** | Record possesses **both** a verified person/entity name **and** at least one usable contact detail (`Mobile 1`, `Mobile 2`, `Mobile 3`, or `Email Address`). | Stored in PostgreSQL. Displayed as the **default view** in Processed Records Explorer (outreach-ready). |
| **`INCOMPLETE`** | Record has a valid name or property location, but **lacks all contact details** (phone and email cells were blank in source spreadsheet). | Stored in PostgreSQL with `status = "INCOMPLETE"` and validation flag `incomplete_missing_contact`. Selectable in UI filter. |
| **`DUPLICATE`** | Record's SHA-256 identity hash matches a previously seen record (`Name + Community + Unit Number + Contact Details`). | Stored in PostgreSQL with `status = "DUPLICATE"` and validation flag `duplicate_identity_hash`. Allows complete auditability without losing source occurrences. |
| **`INVALID`** | Record failed critical structural validation (e.g. unparseable row format or corrupted procedure values). | Logged in `processing_errors` table with exact source row number, error code, and error message. |

### Stage 5: Master Developer & Filename Community Auto-Inference

When raw Excel sheets lack explicit `Community` or `Developer` columns:

1. **Filename Community Extraction**:
   - The engine cleans the filename stem by stripping dates (`2021`, `2022`, `June`), brackets (`[Club Villas]`), version noise (`(c)`, `(d)`, `new`, `done`, `consolidated`), and normalizes it to clean title case.
   - Example: `[Club Villas] Club Villas.xlsx` $\rightarrow$ `Community = "Club Villas"`
   - Example: `Sidra 1 (c) 2022 June.xlsx` $\rightarrow$ `Community = "Sidra 1"`
2. **Master Developer Resolution**:
   - Matches `Community`, `Sub-Community`, or filename against the **UAE Development Builders Reference** (483 communities across all 7 emirates).
   - All Dubai Hills sub-projects (`Club Villas`, `Sidra`, `Maple`, `Fairway Vistas`, `Park Heights`, `Mulberry`, `Acacia`, `Golf Place`, `Golf Grove`, etc.) automatically resolve `Developer = "Emaar Properties"`.

### Stage 6: Real-Time Streaming & Pipeline Controls
- **Live Progress Bar**: Displays real-time row processing counters (`12,500 / 52,723 rows (23%)`), active sheet name, and animated gradient visual progress.
- **Pause & Resume**: Users can click **Pause** at any time. The engine safely holds at the current batch boundary without losing already-committed records. Clicking **Resume** continues seamlessly.
- **Stop (Cancel)**: Users can click **Stop** to halt execution immediately.

### Stage 7: Memory-Bounded Batch Persistence
- Ingests in chunks of 500–1,000 rows within isolated database transactions.
- If a chunk fails, only that batch rolls back while previous successful batches remain intact.

---

## 5. Direct Database Ingestion CLI Engine

For high-throughput batch operations where browser uploads are not needed, the CLI engine [`scripts/direct_ingest_all.py`](file:///c:/Users/USER/Downloads/Prototype/scripts/direct_ingest_all.py) enables direct bulk ingestion:

```powershell
python scripts/direct_ingest_all.py
```

- Reads directly from local raw file batches.
- Runs all 7 engine stages in-process.
- Directly inserts batches into Supabase PostgreSQL.
- Immediately populates the live dashboard.

---

## 6. User Interface Features

1. **Neumorphic Auth Lock Screen**:
   - Gated with access key `dev123`.
   - Shake animation on incorrect entry; automatic session persistence in `localStorage`.
2. **Light & Dark Theme Converter**:
   - Dynamic toggle with persistent high-contrast typography (`#F8FAFC` headings, `#F1F5F9` body) ensuring 100% visibility in dark mode.
3. **Interactive Search & Multi-Column Filters**:
   - Live free-text search across Name, Community, Unit, Mobile, Developer, and Plot.
   - Categorical dropdowns for Community, Property Type (Residential, Commercial, Land), Bedroom count, and Status (`VALID`, `INCOMPLETE`, `DUPLICATE`, `ALL`).
4. **Excel & CSV Export Engine**:
   - Dedicated **`Export Excel (.xlsx)`** and **`Export CSV (.csv)`** buttons.
   - Preserves active search queries and filter parameters — exports only the records matching the user's view.

---

## 7. Verification & Health Audit

The entire codebase passes all verification criteria:
- **FastAPI / Uvicorn Server**: Running and healthy at `http://127.0.0.1:8001/docs`.
- **Vite / React Client**: Production build succeeds in < 1 second.
- **Database Connectivity**: Verified connection to Supabase PostgreSQL pooler.
- **Data Integrity Test**: Automated health check confirms 100% pass rate across enrichment, validation, deduplication, and schema definitions.
