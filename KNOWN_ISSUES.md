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
| **ISSUE-101** | Storage | Low | Raw uploaded files remain in `uploads/` on local disk indefinitely. | **Day 4:** Migrate to S3 with automated 60-day lifecycle transition to Glacier. |
| **ISSUE-102** | Queue | Medium | Worker polling SQLite/PostgreSQL uses periodic DB queries. | **Day 8:** Migrate to event-driven Amazon SQS with long-polling. |
| **ISSUE-103** | Frontend | Low | Direct upload passes multipart file payload through API process. | **Day 15:** Connect React to S3 Presigned URL direct binary streaming. |
