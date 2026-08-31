# 🏛️ Architecture Decision Records (ADRs)

---

### ADR 001: Preserve Core Normalization Engine As-Is
* **Date:** 2026-08-31
* **Status:** Accepted
* **Context:** The normalization algorithms in `engine/cleaning.py`, `engine/detection.py`, and `engine/reference.py` have been hardened and verified with 155+ test cases.
* **Decision:** We will **not rebuild or refactor core normalization rules**. Production changes will focus exclusively on wrapping the engine in cloud-native storage, queuing, and container infrastructure.
* **Consequences:** Eliminates regression risk on data formatting, E.164 phone parsing, and UAE developer reference matching.

---

### ADR 002: Direct-to-S3 Presigned Uploads vs Server Multipart Streaming
* **Date:** 2026-08-31
* **Status:** Accepted
* **Context:** Uploading 10+ multi-gigabyte spreadsheets through FastAPI API containers consumes server RAM and risks timeout/OOM crashes.
* **Decision:** Frontend will request a temporary presigned URL from `POST /api/upload/presign` and stream files directly to Amazon S3. The API server only receives the metadata and S3 key.
* **Consequences:** API containers remain lightweight (can run on 0.5 vCPU / 1GB RAM) with zero risk of server memory exhaustion during batch uploads.

---

### ADR 003: Amazon SQS Decoupled Ingestion Queue
* **Date:** 2026-08-31
* **Status:** Accepted
* **Context:** Background processing running inside the web process causes job loss on server restarts.
* **Decision:** Use Amazon SQS Standard Queue with a dedicated Dead Letter Queue (DLQ). Workers run as independent ECS Fargate tasks scaling dynamically based on queue depth.
* **Consequences:** Guarantees durable job delivery, retry handling, and independent scaling.

---

### ADR 004: Amazon Aurora Serverless v2 PostgreSQL with RDS Proxy
* **Date:** 2026-08-31
* **Status:** Accepted
* **Context:** High-concurrency client requests and worker batch operations risk database connection pool exhaustion.
* **Decision:** Deploy Amazon Aurora Serverless v2 with AWS RDS Proxy. GIN Trigram indexes (`pg_trgm`) will be preserved for fast multi-token search over `search_text`.
* **Consequences:** Sub-millisecond connection reuse, automatic compute scaling (0.5 to 16 ACU), and Multi-AZ high availability.

---

### ADR 005: CloudFront CDN + S3 for React 18 SPA Delivery
* **Date:** 2026-08-31
* **Status:** Accepted
* **Context:** Fast global edge caching and SSL termination are required for the Neumorphic web interface.
* **Decision:** Build static Vite React bundle (`dist/`) and deploy to S3 behind Amazon CloudFront with Origin Access Control (OAC).
* **Consequences:** <50ms edge latency for UAE operators, automated SSL/TLS via ACM, and zero server maintenance for frontend hosting.
