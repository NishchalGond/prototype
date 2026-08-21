# 📖 DataLink Engine — Complete Master Manual & Technical Reference

> **Unified Specification & Architecture Guide**  
> **Version**: 2.1.0  
> **Status**: Production Ready / Verified  
> **Primary Tooling**: Visual Studio Code (VS Code)  

---

# Part I: System Architecture & Pipeline Engineering

## 1. Architecture Overview
DataLink Engine is a high-performance, fault-tolerant real estate data normalization, cleaning, and ingestion platform. It ingests messy, multi-builder Excel (`.xlsx`, `.xls`) and CSV spreadsheets into a canonical schema in PostgreSQL (Supabase).

$$\text{Raw File / Folder} \longrightarrow \text{Inspection} \longrightarrow \text{Header Mapping} \longrightarrow \text{Cleaning} \longrightarrow \text{Enrichment} \longrightarrow \text{Deduplication & Classification} \longrightarrow \text{PostgreSQL Storage} \longrightarrow \text{Export (XLSX/CSV)}$$

---

## 2. Core Ingestion & Processing Scenarios

### Scenario 1: Outreach-Ready Records (`VALID`)
- **Condition**: Record contains a valid person/entity name **AND** at least one usable contact detail (`Mobile 1`, `Mobile 2`, `Mobile 3`, or `Email Address`).
- **Action**: Saved to database with `status = "VALID"`. Serves as the **default view** in the Processed Records Explorer.

### Scenario 2: Missing Contact Records (`INCOMPLETE`)
- **Condition**: Record has property details and owner name, but contact fields in the raw source spreadsheet were blank.
- **Action**: Stored in PostgreSQL with `status = "INCOMPLETE"`. Tagged with `incomplete_missing_contact` validation flag. Excluded from default view to ensure outreach safety, but fully searchable via the `INCOMPLETE` filter.

### Scenario 3: Duplicate Record Management (`DUPLICATE`)
- **Condition**: A row's SHA-256 identity hash (`Name + Community + Unit Number + Contact Details`) matches an already-ingested record.
- **Action**: Stored in PostgreSQL with `status = "DUPLICATE"` and tagged with `duplicate_identity_hash`. Counted in job audit logs and dashboard metrics as `Duplicates Filtered`. Enables full traceability without losing source entries.

### Scenario 4: Critical Parsing Failures (`INVALID`)
- **Condition**: Row failed structural validation (e.g., unparseable row or corrupted procedure value).
- **Action**: Recorded in `processing_errors` table with exact source row number, error code, and error message.

### Scenario 5: Missing Community Auto-Inference
- **Condition**: Raw Excel file has blank `Community` column or no community header.
- **Action**: The engine cleans the filename stem (strips `[Club Villas]`, `2021`, `(c)`, `done`) and infers the clean title-cased community name (e.g. `"Club Villas"`, `"Sidra 1"`).

### Scenario 6: Dubai Hills Master Builder Auto-Resolution
- **Condition**: Sub-community belongs to Dubai Hills (`Club Villas`, `Sidra`, `Maple`, `Fairway Vistas`, `Park Heights`, `Mulberry`, `Acacia`, `Golf Grove`, etc.).
- **Action**: Engine automatically populates `Developer = "Emaar Properties"`.

### Scenario 7: In-Flight Process Controls
- **Live Progress Bar**: Displays live row-by-row streaming counter (`12,500 / 52,723 rows (23%)`) and animated gradient bar.
- **Pause & Resume**: Safe batch-boundary holding (`POST /api/jobs/{id}/pause` and `POST /api/jobs/{id}/resume`).
- **Stop / Cancel**: Graceful termination (`POST /api/jobs/{id}/cancel`).

---

# Part II: REST API Contract

## API Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload/inspect` | Inspects workbook structure, header mappings, and sheet roles. |
| `POST` | `/api/upload` | Uploads an Excel or CSV file and registers a processing job. |
| `POST` | `/api/jobs/{id}/start` | Starts background execution of an uploaded job. |
| `POST` | `/api/jobs/{id}/pause` | Safely pauses a running job at batch boundary. |
| `POST` | `/api/jobs/{id}/resume` | Resumes a paused processing job. |
| `POST` | `/api/jobs/{id}/cancel` | Halts and cancels a processing job. |
| `GET` | `/api/jobs/{id}` | Fetches real-time status and row counts. |
| `GET` | `/api/jobs/{id}/errors` | Retrieves row-level error audit logs. |
| `GET` | `/api/jobs` | Lists all historical and active processing jobs. |
| `GET` | `/api/records` | Paginated, filterable list of processed records. |
| `GET` | `/api/records/export` | Streams filtered records to Excel (`.xlsx`) or CSV (`.csv`). |
| `GET` | `/api/records/filters` | Distinct values for dropdown filters. |
| `GET` | `/api/dashboard/stats` | High-level metrics: total clean records, success rate, duplicate counts. |
| `GET` | `/api/column-mappings` | Returns canonical target fields, aliases, and exclusion rules. |

---

# Part III: Canonical 23 Standard Fields Dictionary

| # | Field Name | SQL Column | Data Type | Description |
|---|---|---|---|---|
| 1 | **Name** | `name` | `VARCHAR(512)` | Full legal name of person or purchasing entity. |
| 2 | **Community** | `community` | `VARCHAR(256)` | Primary master development (e.g. `Dubai Hills`). |
| 3 | **Sub-Community** | `sub_community` | `VARCHAR(256)` | Specific neighborhood or enclave (e.g. `Park Heights II`). |
| 4 | **Building/Cluster** | `building_cluster` | `VARCHAR(256)` | Building name, tower number, or cluster name. |
| 5 | **Unit Number** | `unit_number` | `VARCHAR(128)` | Apartment, villa, or suite number. |
| 6 | **Size** | `size` | `FLOAT` | Standardized surface area in **square feet (sq.ft)**. |
| 7 | **Plot Reg. No** | `plot_reg_no` | `VARCHAR(128)` | Official land pre-registration number. |
| 8 | **Plot Number** | `plot_number` | `VARCHAR(128)` | Municipality or master plot number. |
| 9 | **DMNO** | `dmno` | `VARCHAR(128)` | Dubai Municipality Number. |
| 10 | **DMsubno** | `dmsubno` | `VARCHAR(128)` | Dubai Municipality Sub-Number. |
| 11 | **Bedroom** | `bedroom` | `VARCHAR(64)` | Standardized bedroom count (`Studio`, `1 BR`, `2 BR`, etc.). |
| 12 | **Type (Buyer/Seller)** | `party_type` | `VARCHAR(64)` | Party transaction role (`Buyer`, `Seller`, `Owner`). |
| 13 | **Mobile 1** | `mobile_1` | `VARCHAR(64)` | Primary contact number in standardized E.164 format. |
| 14 | **Mobile 2** | `mobile_2` | `VARCHAR(64)` | Secondary mobile number. |
| 15 | **Mobile 3** | `mobile_3` | `VARCHAR(64)` | Tertiary contact number. |
| 16 | **Email Address** | `email_address` | `VARCHAR(256)` | Validated, lowercase email address. |
| 17 | **PI number** | `pi_number` | `VARCHAR(128)` | Property identifier / DLD reference number. |
| 18 | **Nationality** | `nationality` | `VARCHAR(128)` | Standardized nationality / country name. |
| 19 | **Property Type** | `property_type` | `VARCHAR(128)` | Property classification (`Residential`, `Commercial`, `Land`, `Villa`, `Flat`). |
| 20 | **Date** | `record_date` | `DATE` | Official transaction or register date. |
| 21 | **Procedure Value** | `procedure_value` | `FLOAT` | Property transaction value in **AED**. |
| 22 | **Developer** | `developer` | `VARCHAR(256)` | Master developer resolved from UAE reference (`Emaar Properties`). |
| 23 | **Project** | `project` | `VARCHAR(256)` | Project naming as declared in the registry. |

---

# Part IV: CLI Direct Ingestion Engine

Run direct bulk processing anytime:
```powershell
python scripts/direct_ingest_all.py
```
This bypasses browser uploads and streams all files directly into Supabase PostgreSQL with real-time terminal output.
