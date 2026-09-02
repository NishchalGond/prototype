# 🐞 DataLink Engine — Known Issues & Defect Registry

This document tracks identified bugs, edge cases, and their current mitigation or resolution status.

---

## 🟢 Resolved in Baseline Prototype
| ID | Description | Root Cause | Resolution |
|---|---|---|---|
| **DEF-001** | `clean_size` ignored header units | Raw header string was not passed down the transformation pipeline | Updated `transform()` in `validation.py` to forward `size_header`. |
| **DEF-002** | Numbered communities collapsed | Trailing digits were stripped before canonical lookup | Fixed regex in `cleaning.py` to preserve community numbers (`Al Barsha 1/2/3`). |
| **DEF-003** | Emaar stamped on all Dubai Hills | Fallback rule assumed whole estate was Emaar | Added sub-community developer mapping in `reference.py`. |
| **DEF-004** | Stale jobs hung on server restart | In-memory job state died with the Python process | Added `reap_stale_jobs()` in `lifespan` hook to mark orphaned jobs `FAILED`. |

---

## 🟡 Active Monitoring & Upcoming Milestones
| ID | Area | Severity | Description | Target Milestone |
|---|---|---|---|---|
| **ISSUE-101** | Storage | **High** | `SourceFile.stored_path` is a local filesystem path. Blocks Day 14: API and Worker run as separate ECS services with per-task ephemeral storage, so the worker cannot read files the API wrote. Raised from Low — see [#4](https://github.com/LuxProHub/prototype/discussions/4). | **Day 4:** Storage Adapter + S3. Pull forward — Days 9–12 assume the worker can read source files. |
| **ISSUE-102** | Queue | **Low** | Worker polling costs one indexed SELECT per worker per `WORKER_POLL_SECONDS` (default 2s). Not a bottleneck at current volume, and 2s dispatch latency is immaterial for jobs measured in minutes. Lowered from Medium — see [#3](https://github.com/LuxProHub/prototype/discussions/3). | **Day 8, deferred:** revisit when workers span AZs, poll traffic shows in RDS metrics, or scale-to-zero is needed. |
| **ISSUE-103** | Frontend | Low | Direct upload passes multipart file payload through API process. | **Day 15:** Connect React to S3 Presigned URL direct binary streaming. |

---

## 🔍 Triage Notes

Recorded from the design discussions so the reasoning is not lost when these
issues are picked up.

### ISSUE-101 — three independent failure modes ([#4](https://github.com/LuxProHub/prototype/discussions/4))

Local-disk storage does not degrade under Day 14, it stops working. Fixing any
one of these alone is not sufficient:

1. **Separate filesystems.** Fargate ephemeral storage is scoped per task. The
   API records `stored_path`; the worker resolves it against its own empty
   filesystem and raises `FileNotFoundError`.
2. **Deploys wipe state.** Jobs re-read the workbook on restart, so every deploy
   strands every incomplete job.
3. **Horizontal scaling.** Even with a shared volume, two API tasks behind an
   ALB means an upload lands on whichever task served the request.

The failure is quiet: the job fails at read time and `reap_stale_jobs()` marks
it `FAILED`, giving the operator no signal that the cause is architectural.

**`stored_path` must change with the adapter.** With `LocalStorage` and
`S3Storage` both live, the column would hold filesystem paths and S3 keys with
nothing recording which is which. Storing a scheme-qualified URI
(`file:///…`, `s3://…`) keeps `String(1024)`, makes the Alembic migration a
reversible backfill rather than a type change, and leaves local development and
the SQLite fallback working unchanged.

**Glacier lifecycle conflicts with reprocessing.** The 60-day transition assumes
source files are write-once. They are not: `start_job` supports reprocessing a
`COMPLETED` job with `force`, and that path re-reads the workbook. Reprocessing
anything older than 60 days hits an object in Glacier, which is an error until a
restore completes, not a slow read. Either exclude source files from the
lifecycle rule, use Glacier Instant Retrieval, or document that reprocessing has
a 60-day window.

**Presigned uploads and `content_sha256`.** Under Day 15 the API never sees the
bytes, but `content_sha256` is load-bearing for the duplicate-upload check in
`jobs.py`. Preferred fix is `x-amz-checksum-sha256` on the presigned PUT so S3
itself rejects a mismatched body — the client supplies the value but cannot lie
about it, and upload-time dedup stays synchronous. The S3 ETag is not a
substitute: it is MD5, and for multipart uploads it is a hash of part hashes.

### ISSUE-102 — dispatch and state are separate concerns ([#3](https://github.com/LuxProHub/prototype/discussions/3))

The Day 8 milestone and the `worker.py` docstring appeared to contradict each
other. They do not, once "queue" is split into dispatch and state. SQS can
replace dispatch only; the jobs table remains the source of truth for state:

- **The claim stays.** The compare-and-set on `status == UPLOADED` in `run_job()`
  is what makes at-least-once delivery safe — a duplicate message matches zero
  rows and returns. It is already the idempotency mechanism Day 11 calls for,
  and is covered by `tests/test_worker_claim.py`.
- **The heartbeat and reaper stay.** A visibility timeout protects a message
  while a consumer holds it; it says nothing about a worker that dies *after*
  deleting its message. `heartbeat_at` plus `reap_stale_jobs()` is the only
  thing that recovers those.
- **`control_signal` requires the table.** Pause, resume and cancel are written
  onto the job row and read mid-run. SQS cannot deliver a signal to a consumer
  that already holds the message.

If Day 8 proceeds, scope it to a wake-up signal plus DLQ and do not move job
state into SQS — that is the "second source of truth" `worker.py` warns about.
Two operational notes: do not delete the message before the job completes, and
a retry that creates a *new* job row for the same source file loses the
`exclude_job_id` protection in `DedupIndex` and will flag its predecessor's rows
as duplicates.
