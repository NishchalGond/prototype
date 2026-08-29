"""Executive view: who is doing the work, and what it is producing.

The CEO, CCO and DEVELOPER need to see across the whole desk rather than their
own queue -- how many calls each person made, how many leads they hold, and
what those calls proved. Every number here comes from LeadActivity and Lead,
which are written as a by-product of people doing their job, so nobody has to
maintain a separate report.

Reads only. Nothing here can change a record, a lead or an account, which is
what makes it safe to hand to whoever asks for oversight.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.security import require_role
from ..database.session import get_db
from ..models.models import (
    ActivityKind, ContactVerdict, Lead, LeadActivity, LeadStage, User, UserRole,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_EXEC = require_role(list(UserRole.EXECUTIVE))


@router.get("/team")
def team_performance(
    days: int = Query(30, ge=1, le=365, description="Window for activity counts."),
    _user: User = Depends(_EXEC),
    db: Session = Depends(get_db),
):
    """Per-person activity and pipeline, over a window.

    Activity is counted over `days`; leads held are counted as they stand now.
    Mixing the two would be misleading -- a lead someone opened last year is
    still theirs today, but a call they made last year says nothing about this
    month.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Activity by person and kind. user_email rather than a join to users: the
    # trail is denormalised precisely so it survives an account being deleted,
    # and a departed colleague's calls still count toward the team's history.
    activity = db.execute(
        select(LeadActivity.user_email, LeadActivity.kind,
               func.count(LeadActivity.id))
        .where(LeadActivity.occurred_at >= since)
        .group_by(LeadActivity.user_email, LeadActivity.kind)
    ).all()

    people: dict[str, dict] = {}

    def row(email: str) -> dict:
        return people.setdefault(email, {
            "user": email,
            "activities": {k: 0 for k in ActivityKind.ALL},
            "total_activities": 0,
            "leads_held": 0,
            "leads_by_stage": {s: 0 for s in LeadStage.ALL},
            "verdicts_given": {v: 0 for v in ContactVerdict.ALL},
        })

    for email, kind, n in activity:
        r = row(email)
        r["activities"][kind] = r["activities"].get(kind, 0) + n
        r["total_activities"] += n

    owned = db.execute(
        select(User.email, Lead.stage, func.count(Lead.id))
        .join(User, User.id == Lead.owner_user_id)
        .group_by(User.email, Lead.stage)
    ).all()
    for email, stage, n in owned:
        r = row(email)
        r["leads_held"] += n
        r["leads_by_stage"][stage] = r["leads_by_stage"].get(stage, 0) + n

    # Who is finding the bad data. A person returning many WRONG_NUMBER
    # verdicts is doing the platform a favour, not underperforming, and this is
    # where that shows up as a contribution rather than as a low call-through
    # rate.
    verdicts = db.execute(
        select(Lead.contact_verdict_by, Lead.contact_verdict, func.count(Lead.id))
        .where(Lead.contact_verdict.is_not(None),
               Lead.contact_verdict_by.is_not(None))
        .group_by(Lead.contact_verdict_by, Lead.contact_verdict)
    ).all()
    for email, verdict, n in verdicts:
        r = row(email)
        r["verdicts_given"][verdict] = r["verdicts_given"].get(verdict, 0) + n

    ranked = sorted(people.values(), key=lambda r: -r["total_activities"])
    return {
        "window_days": days,
        "people": ranked,
        "totals": {
            "activities": sum(r["total_activities"] for r in ranked),
            "leads_held": sum(r["leads_held"] for r in ranked),
            "people_active": sum(1 for r in ranked if r["total_activities"]),
        },
    }


@router.get("/pipeline")
def pipeline_summary(
    _user: User = Depends(_EXEC),
    db: Session = Depends(get_db),
):
    """The whole desk's pipeline, and what outreach has proved about the data."""
    stages = dict(db.execute(
        select(Lead.stage, func.count(Lead.id)).group_by(Lead.stage)).all())
    verdicts = dict(db.execute(
        select(Lead.contact_verdict, func.count(Lead.id))
        .where(Lead.contact_verdict.is_not(None))
        .group_by(Lead.contact_verdict)).all())

    now = datetime.now(timezone.utc)
    overdue = db.scalar(
        select(func.count(Lead.id))
        .where(Lead.next_action_at.is_not(None), Lead.next_action_at < now,
               Lead.stage.in_(LeadStage.OPEN))) or 0

    return {
        "by_stage": {s: stages.get(s, 0) for s in LeadStage.ALL},
        "open_leads": sum(stages.get(s, 0) for s in LeadStage.OPEN),
        "overdue_actions": overdue,
        "verdicts": {v: verdicts.get(v, 0) for v in ContactVerdict.ALL},
        # Bad contacts found by people on the phone. This is the number that
        # says how much the database improved because someone worked it.
        "contacts_disproved": sum(verdicts.get(v, 0)
                                  for v in ContactVerdict.SUPPRESSING),
    }
