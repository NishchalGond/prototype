# 📋 DataLink Engine — 23-Day Master Task Backlog

---

## 🏗️ Week 1: Understand, Decide & Build the Foundation (Days 1–7)
- [x] **Day 1:** Prototype audit, map engine/backend/frontend/tests, initialize 5 control documents.
- [ ] **Day 2:** Translate target AWS architecture into concrete technical requirements; record decisions in `DECISIONS.md`.
- [ ] **Day 3:** Prepare configuration structure, environment variables (`.env.example`), and Git checkpoints.
- [ ] **Day 4:** Implement pluggable Storage Adapter (`LocalStorage` / `S3Storage`) and S3 Presigned URL endpoint (`POST /api/upload/presign`).
- [ ] **Day 5:** Configure production PostgreSQL / Aurora Serverless v2 connectivity and connection pooler (RDS Proxy).
- [ ] **Day 6:** Validate Alembic migrations, canonical schema, GIN trigram indexes, and baseline data.
- [ ] **Day 7:** Foundation integration: Connect API + Storage + Database; run smoke & regression tests; create Git checkpoint.

---

## ⚡ Week 2: Asynchronous Processing & Production Runtime (Days 8–14)
- [ ] **Day 8:** Implement durable SQS job dispatch queue, retry policy, and Dead Letter Queue (DLQ).
- [ ] **Day 9:** Adapt `worker.py` around queued jobs while preserving existing normalization algorithms in `engine/`.
- [ ] **Day 10:** Worker retrieves source files directly from S3, validates job identity, and invokes `Processor`.
- [ ] **Day 11:** Implement job lifecycle states, idempotency, duplicate protection, and failure capture.
- [ ] **Day 12:** Verify chunked streaming, batch database writes, memory controls, and error logs using 50MB+ datasets.
- [ ] **Day 13:** Author multi-stage Dockerfiles for API and Worker; verify repeatable build artifacts.
- [ ] **Day 14:** Deploy API and Worker to runtime (ECS Fargate); verify `/health` endpoint and service connectivity.

---

## 🌐 Week 3: Complete Application & Operations (Days 15–21)
- [ ] **Day 15:** Connect React `UploadSection.jsx` to direct-to-S3 presigned upload flow with progress tracking.
- [ ] **Day 16:** Complete job status UX: queued, processing, completed, and error states with downloadable export links.
- [ ] **Day 17:** Finalize API ingress, ALB reverse proxy, request timeouts, and TLS-ready access.
- [ ] **Day 18:** Build and distribute static React bundle to S3 + CloudFront CDN; validate SPA routing.
- [ ] **Day 19:** Configure custom domain and SSL/TLS via ACM; verify HTTPS frontend and API paths.
- [ ] **Day 20:** Security hardening: migrate secrets to AWS Secrets Manager; configure AWS WAF and IAM least privilege.
- [ ] **Day 21:** Implement observability: CloudWatch logs, container metrics, queue depth alarms, and `X-Correlation-ID` tracing.

---

## 🚀 Final 2 Days: Prove & Freeze (Days 22–23)
- [ ] **Day 22:** Full system integration test: upload → S3 → SQS → Worker → DB → Export → Download (including edge cases).
- [ ] **Day 23:** Freeze feature additions; run release checklist; document known issues; cut **Production Build v1.0**.

---

## 🔄 Post Day 23: Real-World Run & Improvement Cycle
- [ ] Real workload execution → CloudWatch observation → Issue triage with Claude → Approval & deployment.
