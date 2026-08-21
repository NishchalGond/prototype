# API Contract — DataLink Real Estate Processing Backend

**Owner:** Backend Team · **Consumer:** Frontend Client  
**Base URL:** `http://127.0.0.1:8001/api` (Local) / `https://prototype-production-4598.up.railway.app/api` (Production)  
**Interactive Docs:** `/docs` · **OpenAPI:** `/openapi.json`  
**Version:** 2.1.0  
**Primary Tooling:** Visual Studio Code (VS Code)  

---

## 1. Database & Cloud Architecture

| Layer | Implementation |
|---|---|
| **Database** | PostgreSQL 15+ hosted on **Supabase Cloud** (`pooler.supabase.com:5432`) |
| **Backend** | Python 3.12 + FastAPI on Railway |
| **Frontend** | React 18 + Vite on Vercel |

---

## 2. Global Standards & Conventions

- All list endpoints are **paginated** using a standard envelope (`items`, `total`, `page`, `page_size`, `total_pages`, `has_next`, `has_prev`).
- All IDs are **integers**.
- All timestamps are ISO-8601 UTC.
- Absent data is `null`. The backend never substitutes artificial placeholders.
- Surface area is stored as a standard float in **square feet (sq.ft)** ($1 \text{ sqm} = 10.7639 \text{ sq.ft}$).
- Property Procedure Values are stored as floats in **AED**.

---

## 3. Record Classification Scenarios

| Status | Definition | Viewable State |
|---|---|---|
| **`VALID`** | Record possesses **both** a valid name and at least one contact channel (`mobile_1`, `mobile_2`, `mobile_3`, or `email_address`). | Default view in Records Explorer. |
| **`INCOMPLETE`** | Record contains ownership/location details but has no contact details (blank in original file). | Filterable in Records Explorer via `status=INCOMPLETE`. |
| **`DUPLICATE`** | Record has an exact SHA-256 identity hash match (`name + community + unit_number + mobile/email`). | Stored in DB with `status=DUPLICATE` and flag `duplicate_identity_hash`. |
| **`INVALID`** | Record failed core schema validation. | Logged in `processing_errors`. |

---

## 4. Endpoints Specification

### 4.1 Ingestion & File Upload
- `POST /api/upload/inspect`: Multipart upload for pre-flight column schema mapping and sheet role detection.
- `POST /api/upload`: Multipart upload to register a new processing job with optional `batch_size` (default 500).

### 4.2 Job Execution & Live Controls
- `POST /api/jobs/{id}/start`: Initiates background ingestion job.
- `POST /api/jobs/{id}/pause`: Safely pauses a running job at the next batch boundary.
- `POST /api/jobs/{id}/resume`: Resumes a paused job.
- `POST /api/jobs/{id}/cancel`: Cancels execution.
- `GET /api/jobs/{id}`: Real-time progress status, rows processed, and percentage.
- `GET /api/jobs/{id}/errors`: Row-level failure trail.

### 4.3 Processed Dataset & Export
- `GET /api/records`: Paginated, filterable, and sortable dataset. Supports `q` (free-text), `community`, `property_type`, `bedroom`, `status`, `sort_by`, `sort_dir`.
- `GET /api/records/export`: Streams filtered records directly to formatted openpyxl Excel (`format=xlsx`) or UTF-8 CSV (`format=csv`).
- `GET /api/records/filters`: Distinct values for frontend dropdowns.

### 4.4 Dashboard Metrics
- `GET /api/dashboard/stats`: Returns `total_records`, `valid_records`, `duplicate_records`, `success_rate`, `community_distribution`, and `recent_jobs`.
