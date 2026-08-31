# ✅ DataLink Engine — Verification & Release Test Checklist

This checklist must be executed before every milestone git commit and prior to the Day 23 production release.

---

## 1. Engine & Normalization Verification
- [ ] **UAE Phone E.164 Formatting:** `0501234567`, `501234567`, `+971 50 123 4567` all format to `+971501234567`.
- [ ] **Multi-phone Cell Distribution:** Cells with multiple numbers populate `mobile_1`, `mobile_2`, `mobile_3` without duplicates.
- [ ] **Size Conversion:** Column headers containing `(sqm|sq.m|m2)` multiply values by `10.7639` to store sq.ft.
- [ ] **Unit Number Cleaning:** Floats like `101.0` are stripped of `.0` to become `101`.
- [ ] **Reference Data Enrichment:** Developer names (e.g. `Emaar Properties`) correctly enrich from `uae_developers.json`.
- [ ] **Deduplication Tiers:** Exact SHA-256 matches flag `DUPLICATE`; token fuzzy match collapses cross-register owners.

---

## 2. API & Database Integrity
- [ ] **FastAPI Health Check:** `GET /health` returns `200 OK` with `database: "ok"`.
- [ ] **Alembic Head:** `alembic current` confirms head revision matches `a7b4e9f1c260`.
- [ ] **Trigram Search Performance:** Search queries over `search_text` return in `<10ms` utilizing GIN index.
- [ ] **RBAC Protection:** Unauthenticated requests receive `401 Unauthorized`; non-admin export calls receive `403 Forbidden`.
- [ ] **PDPL Erasure:** `POST /api/erasure/requests` scrubs phone and email identities from active records.

---

## 3. Storage & Queue Infrastructure (Week 1–2 Milestones)
- [ ] **Presigned URL Generation:** `POST /api/upload/presign` returns authenticated, time-limited S3 upload URL.
- [ ] **S3 Upload Flow:** Binary uploads to S3 succeed with public read access blocked.
- [ ] **SQS Job Queue:** Submitting a job pushes an SQS message with valid Job ID.
- [ ] **Worker Isolation:** Corrupted rows log to `processing_errors` without terminating the worker process.

---

## 4. Pre-Commit Command Suite
Run these verification commands before every milestone checkpoint:
```bash
# 1. Run engine & system health check
python scripts/health_check.py

# 2. Run unit and integration test suite
pytest -q

# 3. Check git working directory status
git status
```
