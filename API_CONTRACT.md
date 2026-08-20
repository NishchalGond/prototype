# API Contract — Prototype Data Processing Backend

**Owner:** Claude (backend) · **Consumer:** Antigravity (frontend)
**Base URL:** `http://127.0.0.1:8001` (see §0 on the port)
**Interactive docs:** `/docs` · **OpenAPI:** `/openapi.json`
**Version:** 1.0.0

This contract is stable. Changes are announced in `FRONTEND_BACKEND_COLLABORATION.md` before implementation.

---

## 0. Port and database status

| | Current | Target |
|---|---|---|
| Port | Canonical backend on **8001**; the stub still holds **8000** | 8000 once the stub is retired |
| Database | `prototype_core.db` (SQLite) | `prototype.db`, then PostgreSQL |

The stub on :8000 holds `prototype.db` open, so the real backend uses its own file to avoid corrupting a running process. Its 1,264 mock rows are preserved at `prototype.stub-backup.db`. When you stop the stub, I'll switch the port and DB path — one config change, no code change.

---

## 1. Conventions

- All list endpoints are **paginated** and return the same envelope.
- All IDs are **integers**.
- All timestamps are ISO-8601 UTC.
- Absent data is `null`. The backend never substitutes a placeholder.
- Money and area are numbers, not display strings (`size: 190.71`, not `"190.71 sqm"`). A `size_display` string is provided for convenience.

### Pagination envelope

```json
{
  "items": [ ... ],
  "total": 1076,
  "page": 1,
  "page_size": 50,
  "total_pages": 22,
  "has_next": true,
  "has_prev": false
}
```

### Error shape

```json
{ "detail": "Job 99 not found.", "code": null }
```

| Status | Meaning |
|---|---|
| 400 | Bad parameter (e.g. unknown `sort_by`) |
| 404 | Resource not found |
| 409 | Job already running |
| 413 | Upload exceeds size limit |
| 415 | Unsupported file type |
| 422 | Request validation failed (FastAPI default) |
| 500 | `{"detail": "Internal server error.", "code": "INTERNAL_ERROR"}` |

---

## 2. `GET /api/dashboard/stats`

Dashboard summary tiles.

**Parameters:** none.

**Response**

```json
{
  "total_files": 3,
  "total_jobs": 3,
  "total_records": 1076,
  "valid_records": 1076,
  "invalid_records": 0,
  "duplicate_records": 384,
  "total_errors": 1,
  "success_rate": 100.0,
  "jobs_by_status": { "COMPLETED": 2, "FAILED": 1 },
  "records_by_status": { "VALID": 1076 },
  "top_communities": [ { "community": "Al Kifaf", "count": 614 } ],
  "community_distribution": [ { "name": "Al Kifaf", "count": 614 } ],
  "field_completeness": { "name": 99.8, "unit_number": 100.0, "mobile_1": 88.2, "bedroom": 1.0 },
  "last_job": { "...JobOut..." },
  "recent_jobs": [ { "...JobOut..." } ]
}
```

`field_completeness` is the percentage of stored records where each of the 23 fields is non-null. **Low numbers are real** — the source files are genuinely sparse (`bedroom` is empty in 398 of 400 rows of the Al Kifaf file). Render them as data quality, not as an error.

---

## 3. `POST /api/files/upload`

Multipart upload. Starts processing immediately unless `autostart=false`.

**Parameters:** `file` (multipart, required) · `autostart` (query bool, default `true`)
**Accepted:** `.xlsx` `.xlsm` `.xls` `.csv` — detected by magic bytes, not extension.

**Response `201`**

```json
{
  "job_id": 1,
  "source_file_id": 1,
  "filename": "Al Kifaf_Park Gate 1 and 2.xlsx",
  "size_bytes": 94543,
  "detected_format": "xlsx",
  "status": "UPLOADED",
  "duplicate_of_job_id": null
}
```

`detected_format` may be `xlsx` `xls` `html_table` `csv` `encrypted` `unknown`. `duplicate_of_job_id` is set when the identical file (same SHA-256) was uploaded before — show a warning, don't block.

An `encrypted` file uploads fine but its job will land in `FAILED` with an actionable message. That is correct behaviour, not a bug.

---

## 4. `GET /api/jobs`

**Parameters:** `status` · `page` · `page_size`
**Response:** paginated `JobOut`.

### JobOut

```json
{
  "id": 1,
  "source_file_id": 1,
  "filename": "Al Kifaf_Park Gate 1 and 2.xlsx",
  "status": "COMPLETED",
  "total_rows": 998,
  "processed_rows": 998,
  "valid_rows": 614,
  "invalid_rows": 0,
  "duplicate_rows": 384,
  "skipped_rows": 0,
  "error_count": 0,
  "progress_percent": 100.0,
  "current_sheet": null,
  "batch_size": 1000,
  "message": null,
  "started_at": "2026-08-17T11:39:37Z",
  "finished_at": "2026-08-17T11:39:38Z",
  "created_at": "2026-08-17T11:39:37Z",

  "error_rows": 0,
  "completed_at": "2026-08-17T11:39:38Z",
  "current_batch": 1,
  "total_batches": 1
}
```

The last four are compatibility mirrors of your stub's field names; they are computed, always present, and safe to keep using.

**Statuses:** `UPLOADED` `READING` `PROCESSING` `VALIDATING` `SAVING` `COMPLETED` `COMPLETED_WITH_ERRORS` `FAILED`

---

## 5. `POST /api/jobs/{job_id}/start`

Re-runs a job. `409` if already running. Returns `JobOut`.

## 6. `GET /api/jobs/{job_id}`

`JobOut` plus `mapping_report` — per sheet, exactly which source column went to which target field:

```json
"mapping_report": {
  "Sheet1": {
    "mapped": { "Name": "Name", "Mobile1": "Mobile 1", "Building Name": "Building/Cluster" },
    "composite": { "premise1": 5 },
    "extras": ["Serial No.", "Stage"],
    "excluded": ["Password"],
    "unmapped": [],
    "positional_fallback": false
  }
}
```

This powers the column-mapping verification screen. `positional_fallback: true` means the sheet had no header row and was mapped by column position.

## 7. `GET /api/jobs/{job_id}/errors`

**Parameters:** `severity` (`ERROR`|`WARNING`) · `page` · `page_size`

```json
{
  "id": 1, "job_id": 3, "sheet_name": null, "batch_number": null, "source_row": null,
  "severity": "ERROR", "code": "UNREADABLE_FILE",
  "message": "File is password-protected (OLE2 EncryptedPackage). Supply the password or remove protection before uploading.",
  "payload": null, "created_at": "2026-08-17T11:39:49Z"
}
```

**Codes:** `UNREADABLE_FILE` `JOB_CRASHED` `SHEET_FAILED` `BATCH_INSERT_FAILED` `MAP_FAILED` `NO_MAPPABLE_COLUMNS` `INVALID_RECORD`

---

## 8. `GET /api/records`

**Search:** `q` — matches name, community, sub-community, building, unit, all three mobiles, email, plot number, PI number, project, developer.

**Filters:** `community` `sub_community` `building_cluster` `property_type` `bedroom` `developer` `nationality` `source_file` `job_id` `status` `has_mobile` `has_email`

**Sort:** `sort_by` ∈ `id name community sub_community building_cluster unit_number size created_at record_date` · `sort_dir` ∈ `asc desc`

**Paging:** `page` · `page_size` (max 500)

### RecordOut — the 23 fields plus provenance

```json
{
  "id": 2,
  "name": "DILEEP KUMAR HARKISHAN DAS",
  "community": "Al Kifaf",
  "sub_community": "Park Gate Residences",
  "building_cluster": "PARK GATE RESIDENCES 4",
  "unit_number": "2101",
  "size": 191.47,
  "plot_reg_no": null,
  "plot_number": null,
  "dmno": null,
  "dmsubno": null,
  "bedroom": null,
  "party_type": null,
  "mobile_1": "+971503777756",
  "mobile_2": null,
  "mobile_3": null,
  "email_address": null,
  "pi_number": null,
  "nationality": null,
  "property_type": "Mixed-use master plan",
  "record_date": null,
  "procedure_value": null,
  "developer": "Dubai Properties",
  "project": null,

  "job_id": 1,
  "source_file": "Al Kifaf_Park Gate 1 and 2.xlsx",
  "source_sheet": "Sheet1",
  "source_row": 3,
  "status": "VALID",
  "validation_flags": ["phone_local_no_country_code"],
  "enriched_fields": ["developer", "property_type"],
  "extras": { "Serial No.": 2 },
  "created_at": "2026-08-17T11:39:38Z",

  "bedroom_type": null,
  "mobile": "+971503777756",
  "record_status": "VALID",
  "size_display": "191.47 sqm"
}
```

**Three fields worth surfacing in the UI:**

- **`enriched_fields`** — these values were *derived* from the UAE developer reference workbook, not read from the uploaded file. Worth a subtle marker so users know the difference.
- **`validation_flags`** — per-record quality notes. See §10.
- **`extras`** — source columns with no home in the 23. Good for a detail-view "raw source" panel.

## 9. `GET /api/records/filters`

Distinct values for dropdowns. Call once per dataset change.

```json
{ "communities": [...], "sub_communities": [...], "property_types": [...],
  "bedrooms": [...], "developers": [...], "source_files": [...], "statuses": [...] }
```

## 10. `GET /api/records/{record_id}`

Single `RecordOut`. `404` if absent.

### validation_flags reference

| Flag | Meaning |
|---|---|
| `phone_local_no_country_code` | Real number, country not determinable — stored without `+` |
| `phone_precision_lost_in_excel` | Excel stored it as a float; trailing digits already gone |
| `phone_corrupt_scientific` / `phone_too_short` / `phone_too_long` | Rejected, field is null |
| `email_invalid` | Failed format check, field is null |
| `date_unparseable` | Source had a value the parser could not read |
| `size_implausible` | > 100,000, dropped |
| `no_contact` / `no_location` / `uncontactable` | Record kept but incomplete |

## 11. `GET /api/column-mappings`

The full mapping layer: `target_fields` (23), `field_to_column`, `aliases` (185 source-header spellings), `composite_fields`, `exclude_columns`, `do_not_map`, `alias_count`.

`do_not_map` is worth showing — it explains why a column that *looks* relevant was deliberately ignored (e.g. `Created by` is a CRM user, not a property developer).

---

## 12. Notes on data you will see

- **`duplicate_rows` can be large and is usually correct.** The Al Kifaf file has 384 genuine repeat rows out of 998.
- **Sparse fields are real.** Across the 100-file corpus only Name, Unit Number and Mobile 1 exceed 85% coverage; `Procedure Value` appears in 6% of files.
- **A `FAILED` job is not always a system fault.** Encrypted files fail by design with an actionable message.
