"""Right to erasure.

The platform holds names, phone numbers and email addresses of identified
private individuals, which under the UAE PDPL carries a right to have them
deleted on request. Redacting the rows is the easy half.

The hard half is that records are DERIVED. Reprocessing rebuilds them from the
source file stored at upload, and that file still contains the person, so a
redaction applied today is silently undone by the next engine fix. That is why
the request itself is stored: apply_erasures() re-runs after every ingest, so
erasure survives the pipeline rather than racing it.

What is removed is the person, not the property. Name, phone numbers, email and
nationality are cleared, along with `extras`, which carries whatever unmapped
columns the source had -- the owner registers put dates of birth and passport
details there. The unit, community, size and transaction value stay: they
describe real estate, and the business record of a sale is not the data subject.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..core.security import require_role
from ..database.session import get_db
from ..models.models import (
    ErasureRequest, Lead, LeadStage, Record, User, UserRole,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["erasure"])

# Erasure destroys data that cannot be recovered from the source file once the
# request is standing. Administrators only.
_ADMIN = require_role([UserRole.ADMIN])

# The columns that identify a person. search_text, mobile_digits and
# has_valid_mobile are generated from these, so they clear themselves -- which
# is exactly why those were made generated columns rather than app-written ones.
PERSONAL_FIELDS = {
    "name": None,
    "mobile_1": None,
    "mobile_2": None,
    "mobile_3": None,
    "email_address": None,
    "nationality": None,
    # Unmapped source columns land here, and the owner registers put dates of
    # birth and passport details among them.
    "extras": None,
}


class ErasureIn(BaseModel):
    reason: str | None = None


class ErasureOut(BaseModel):
    id: int
    identity_hash: str
    requested_by_email: str
    reason: str | None
    created_at: datetime
    last_applied_at: datetime | None
    records_redacted: int

    model_config = {"from_attributes": True}


def _redact(db: Session, identity_hashes) -> int:
    """Clear personal fields on every record matching these identities."""
    hashes = [h for h in identity_hashes if h]
    if not hashes:
        return 0
    return db.execute(
        update(Record)
        .where(Record.identity_hash.in_(hashes), Record.name.is_not(None))
        .values(**PERSONAL_FIELDS)
    ).rowcount


def apply_erasures(db: Session, job_id: int) -> int:
    """Re-apply standing erasures to the rows a job just wrote.

    Called after every ingest, not just reprocessing. A person who asked to be
    erased can appear again in a register uploaded next month; without this the
    request would only ever have covered the files that existed when it was
    made.
    """
    standing = db.scalars(select(ErasureRequest.identity_hash)).all()
    if not standing:
        return 0

    hashes = set(db.scalars(
        select(Record.identity_hash)
        .where(Record.job_id == job_id, Record.identity_hash.in_(standing))
    ).all())
    if not hashes:
        return 0

    redacted = _redact(db, hashes)
    if redacted:
        db.execute(
            update(ErasureRequest)
            .where(ErasureRequest.identity_hash.in_(hashes))
            .values(last_applied_at=datetime.now(timezone.utc),
                    records_redacted=ErasureRequest.records_redacted + 1)
        )
        db.commit()
        log.info("re-applied erasure to %d row(s) written by job %d",
                 redacted, job_id)
    return redacted


@router.post("/records/{record_id}/erase", response_model=ErasureOut, status_code=201)
def erase_record(
    record_id: int,
    payload: ErasureIn,
    user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    """Erase the person behind a record, now and on every future ingest.

    Idempotent: erasing an already-erased identity refreshes the request rather
    than failing, because a second request from the same person is a normal
    thing to receive and should not read as an error.
    """
    record = db.get(Record, record_id)
    if record is None:
        raise HTTPException(404, f"Record {record_id} not found.")

    req = db.scalar(select(ErasureRequest)
                    .where(ErasureRequest.identity_hash == record.identity_hash))
    if req is None:
        req = ErasureRequest(identity_hash=record.identity_hash,
                             requested_by_user_id=user.id,
                             requested_by_email=user.email,
                             reason=payload.reason)
        db.add(req)
        db.flush()

    redacted = _redact(db, [record.identity_hash])
    req.last_applied_at = datetime.now(timezone.utc)
    req.records_redacted = (req.records_redacted or 0) + redacted

    # Suppress from outreach too. Erasing the contact details while leaving the
    # lead callable would put the row back in the queue the moment a reprocess
    # rebuilt it from source.
    lead = db.scalar(select(Lead).where(Lead.identity_hash == record.identity_hash))
    if lead is None:
        db.add(Lead(identity_hash=record.identity_hash,
                    stage=LeadStage.DO_NOT_CONTACT))
    else:
        lead.stage = LeadStage.DO_NOT_CONTACT
        lead.next_action_at = None

    db.commit()
    db.refresh(req)
    log.info("erasure applied to %d record(s) for identity %s",
             redacted, record.identity_hash[:12])
    return req


@router.get("/erasures", response_model=list[ErasureOut])
def list_erasures(
    _user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    """The erasure register, newest first. What an auditor asks to see."""
    return db.scalars(
        select(ErasureRequest).order_by(ErasureRequest.created_at.desc())
    ).all()


@router.get("/erasures/verify")
def verify_erasures(
    _user: User = Depends(_ADMIN),
    db: Session = Depends(get_db),
):
    """Confirm no standing erasure has personal data against it.

    A non-zero leaked count means an ingest wrote a person back after their
    request and apply_erasures did not run -- worth alerting on rather than
    discovering during an audit.
    """
    standing = db.scalars(select(ErasureRequest.identity_hash)).all()
    leaked = 0
    if standing:
        leaked = db.scalar(
            select(func.count(Record.id))
            .where(Record.identity_hash.in_(standing), Record.name.is_not(None))
        ) or 0
    return {
        "standing_requests": len(standing),
        "records_still_holding_personal_data": leaked,
        "clean": leaked == 0,
    }
