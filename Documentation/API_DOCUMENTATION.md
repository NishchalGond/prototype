# 🌐 DataLink Engine — Complete REST API Specification

> **API Version**: 2.1.0  
> **Base URL**: `http://127.0.0.1:8001/api` (Local) / `https://prototype-production-4598.up.railway.app/api` (Production)  
> **Primary Development Environment**: Visual Studio Code (VS Code)  
> **Documentation Formats**: OpenAPI 3.0 (`/openapi.json`), Swagger UI (`/docs`), ReDoc (`/redoc`)

---

## 1. Authentication & Protocols

All endpoints accept and return `application/json` (except file upload and data export endpoints).

| Protocol | Specification |
|---|---|
| **Content-Type** | `application/json` (Requests & Responses) |
| **File Uploads** | `multipart/form-data` |
| **File Exports** | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (`.xlsx`) and `text/csv; charset=utf-8` (`.csv`) |
| **CORS** | Enabled for `localhost:3000`, `localhost:5173`, and Vercel domains (`https://*.vercel.app`) |

---

## 2. API Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/upload/inspect` | Inspects workbook structure, header mappings, and sheet roles without database writes. |
| `POST` | `/api/upload` | Uploads an Excel or CSV file and registers a processing job. |
| `POST` | `/api/jobs/{id}/start` | Starts background execution of an uploaded job. |
| `POST` | `/api/jobs/{id}/pause` | Safely pauses a running job at the current batch boundary. |
| `POST` | `/api/jobs/{id}/resume` | Resumes a paused processing job. |
| `POST` | `/api/jobs/{id}/cancel` | Halts and cancels a running or paused processing job. |
| `GET` | `/api/jobs/{id}` | Fetches real-time status, row counts, and progress percentage. |
| `GET` | `/api/jobs/{id}/errors` | Retrieves row-level error audit logs for a specific job. |
| `GET` | `/api/jobs` | Lists all historical and active processing jobs. |
| `GET` | `/api/records` | Paginated, filterable, sortable list of processed records. |
| `GET` | `/api/records/export` | Streams filtered records to formatted Excel (`.xlsx`) or UTF-8 CSV (`.csv`). |
| `GET` | `/api/records/filters` | Distinct values for frontend filter dropdowns (Communities, Property Types, Bedrooms, Statuses). |
| `GET` | `/api/dashboard/stats` | High-level metrics: total clean records, success rate, duplicate counts, and community distribution. |
| `GET` | `/api/column-mappings` | Returns canonical target fields, aliases, and exclusion rules. |

---

## 3. Detailed Endpoint Reference

### 3.1 Inspect File (`POST /api/upload/inspect`)
Examines workbook sheets, detected columns, and provisional target mappings before starting ingestion.

**Request:** `multipart/form-data` with `file: Binary`

**Response Example (`200 OK`):**
```json
{
  "filename": "Club Villas.xlsx",
  "detected_format": "xlsx",
  "total_rows_estimate": 158,
  "header_count": 8,
  "mapped_count": 8,
  "mapped_columns_preview": [
    { "raw_header": "NAME", "mapped_target": "Name" },
    { "raw_header": "PHONE", "mapped_target": "Mobile 1" },
    { "raw_header": "EMAIL", "mapped_target": "Email Address" },
    { "raw_header": "Rooms", "mapped_target": "Bedroom" },
    { "raw_header": "Villa NO", "mapped_target": "Unit Number" }
  ]
}
```

---

### 3.2 Upload & Register Job (`POST /api/upload`)
Uploads a source file to disk and registers a new `ProcessingJob` entry in PostgreSQL.

**Query Parameters:**
- `batch_size` *(integer, optional)*: Batch chunk size (default `500`).
- `autostart` *(boolean, optional)*: If `true`, starts ingestion immediately.

**Response Example (`201 Created`):**
```json
{
  "job_id": 4,
  "source_file_id": 4,
  "filename": "Club Villas.xlsx",
  "status": "UPLOADED",
  "total_rows": 158,
  "size_bytes": 27546
}
```

---

### 3.3 Job Controls: Pause, Resume & Cancel

#### Pause Job (`POST /api/jobs/{id}/pause`)
Halts execution gracefully at the current batch transaction boundary.
```json
{
  "id": 4,
  "status": "PAUSED",
  "processed_rows": 12500,
  "total_rows": 17340,
  "progress_percent": 72.1
}
```

#### Resume Job (`POST /api/jobs/{id}/resume`)
Continues processing a paused job from where it left off.
```json
{
  "id": 4,
  "status": "PROCESSING",
  "processed_rows": 12500,
  "total_rows": 17340,
  "progress_percent": 72.1
}
```

#### Cancel Job (`POST /api/jobs/{id}/cancel`)
Stops execution and marks the job as `CANCELLED`.
```json
{
  "id": 4,
  "status": "CANCELLED",
  "message": "Job cancelled by user.",
  "processed_rows": 12500
}
```

---

### 3.4 List Processed Records (`GET /api/records`)
Fetches paginated records with multi-field search and filters.

**Query Parameters:**
- `q` *(string, optional)*: Free-text search across name, community, unit, mobile, developer.
- `community` *(string, optional)*: Filter by exact community name.
- `property_type` *(string, optional)*: Filter by property type (e.g. `Residential`, `Commercial`, `Land`).
- `bedroom` *(string, optional)*: Filter by bedroom count (e.g. `1 BR`, `2 BR`, `3 BR`).
- `status` *(string, optional)*: Record status filter:
  - `VALID` *(default)*: Only outreach-ready records (has verified name AND phone/email).
  - `INCOMPLETE`: Records missing contact information.
  - `DUPLICATE`: Duplicate records stored for auditability.
  - `ALL`: All records combined.
- `page` *(integer, default 1)*: Page number.
- `page_size` *(integer, default 25)*: Records per page.
- `sort_by` *(string, default `id`)*: Sort column (`name`, `community`, `unit_number`, `bedroom`, `procedure_value`, `mobile_1`).
- `sort_dir` *(string, `asc` | `desc`)*: Sort direction.

**Response Example (`200 OK`):**
```json
{
  "items": [
    {
      "id": 1,
      "name": "AAKASH JAYAPRAKASH",
      "community": "Dubai Hills - Park",
      "sub_community": "PARK HEIGHTS II",
      "building_cluster": "2",
      "unit_number": "1713",
      "size": 149.47,
      "bedroom": null,
      "mobile_1": "+971506506989",
      "email_address": null,
      "developer": "Emaar Properties",
      "status": "VALID",
      "source_file": "DHE 2021 NEW.xlsx"
    }
  ],
  "total": 7190,
  "page": 1,
  "page_size": 25,
  "total_pages": 288,
  "has_next": true,
  "has_prev": false
}
```

---

### 3.5 Export Dataset (`GET /api/records/export`)
Streams formatted records based on active search and filter parameters.

**Query Parameters:**
- `format` *(string, required)*: `xlsx` (styled Excel workbook) or `csv` (UTF-8 with BOM).
- All filter parameters from `GET /api/records` (`q`, `community`, `property_type`, `bedroom`, `status`, `sort_by`, `sort_dir`).

**Response:** File stream with dynamic attachment header:
```http
Content-Disposition: attachment; filename="datalink_export_20260821_130000.xlsx"
```

---

### 3.6 Dashboard Summary Stats (`GET /api/dashboard/stats`)
Returns high-level KPI metrics across the platform.

**Response Example (`200 OK`):**
```json
{
  "total_records": 16573,
  "valid_records": 7190,
  "invalid_records": 1,
  "duplicate_records": 2118,
  "success_rate": 43.4,
  "total_files": 3,
  "total_jobs": 4,
  "community_distribution": [
    { "name": "Dubai Hills - Hills Grove", "count": 9415 },
    { "name": "Dubai Hills - Park", "count": 3000 },
    { "name": "Club Villas", "count": 158 }
  ]
}
```
