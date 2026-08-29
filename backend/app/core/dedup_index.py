"""Cross-register duplicate lookups against rows already in the database.

Dedup used to see only the file being ingested. `seen_hashes` was preloaded
filtered by `source_file == <this file>`, and the Tier-2 fuzzy structures were
plain dicts that lived for the duration of one `process()` call, so the same
owner arriving in two different builder registers was stored twice, both VALID.
For a platform whose stated job is consolidating multi-builder registers, that
is the one duplicate that matters most.

Loading every hash into a Python set does not scale -- at 20M rows that is
gigabytes of process memory per worker, and it would be stale the moment a
concurrent job commits. Instead the engine hands this class one batch of
candidate keys at a time and gets back only the ones that already exist:

    3 indexed queries per 1,000-row batch, rather than 3 per row.

Every probe is chunked, because a query with 20,000 bind parameters is its own
kind of outage.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.models import Record

log = logging.getLogger(__name__)

# Bind-parameter ceiling per probe. PostgreSQL's protocol limit is 65535; this
# leaves generous headroom and keeps individual statements cheap to plan.
CHUNK = 1000


def _chunks(values, size=CHUNK):
    values = list(values)
    for i in range(0, len(values), size):
        yield values[i:i + size]


class DedupIndex:
    """Batch-granularity lookups into the existing corpus.

    Scoped to a single job's session. `exclude_job_id` keeps a job from
    matching against rows it wrote itself: a retried or resumed job would
    otherwise find its own first attempt and mark every row a duplicate.
    """

    def __init__(self, db: Session, *, exclude_job_id: int | None = None):
        self.db = db
        self.exclude_job_id = exclude_job_id

    def _base(self, stmt):
        if self.exclude_job_id is not None:
            stmt = stmt.where(Record.job_id != self.exclude_job_id)
        return stmt

    def seen_hashes(self, hashes) -> set[str]:
        """Which of these identity hashes are already stored."""
        found: set[str] = set()
        for chunk in _chunks({h for h in hashes if h}):
            stmt = self._base(
                select(Record.identity_hash)
                .where(Record.identity_hash.in_(chunk))
                .distinct()
            )
            found.update(self.db.scalars(stmt).all())
        return found

    def seen_properties(self, keys) -> dict[str, tuple[int, str]]:
        """property_key -> (record id, owner name) for keys already stored.

        One representative row per key is enough: the caller only needs a name
        to compare against, and any owner already recorded on that unit is an
        equally valid comparison target.
        """
        out: dict[str, tuple[int, str]] = {}
        for chunk in _chunks({k for k in keys if k}):
            stmt = self._base(
                select(Record.property_key, Record.id, Record.name)
                .where(Record.property_key.in_(chunk))
                .where(Record.name.is_not(None))
                .where(Record.status != "DUPLICATE")
            )
            for key, rec_id, name in self.db.execute(stmt):
                if key and key not in out:
                    out[key] = (rec_id, name)
        return out

    def seen_phones(self, phones) -> dict[str, tuple[int, str]]:
        """mobile_1 -> (record id, owner name) for numbers already stored."""
        out: dict[str, tuple[int, str]] = {}
        for chunk in _chunks({p for p in phones if p}):
            stmt = self._base(
                select(Record.mobile_1, Record.id, Record.name)
                .where(Record.mobile_1.in_(chunk))
                .where(Record.name.is_not(None))
                .where(Record.status != "DUPLICATE")
            )
            for phone, rec_id, name in self.db.execute(stmt):
                if phone and phone not in out:
                    out[phone] = (rec_id, name)
        return out


class NullDedupIndex:
    """No-op index. Restores single-file dedup when no database is available."""

    def seen_hashes(self, hashes) -> set[str]:
        return set()

    def seen_properties(self, keys) -> dict[str, tuple[int, str]]:
        return {}

    def seen_phones(self, phones) -> dict[str, tuple[int, str]]:
        return {}
