"""SQLAlchemy models. Target: PostgreSQL. Compatible with SQLite for local dev."""
import os
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Computed, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Search acceleration columns are computed by the database, not the application,
# so they can never drift out of sync with the fields they summarise. PostgreSQL
# is the production target and gets the exact expressions; SQLite (local dev
# only) gets simplified equivalents because it has no regexp_replace and no `~`
# operator. The dev approximations are good enough to keep `create_all` working
# and are never relied on for correctness -- the SQLite search path in
# core/search.py queries the underlying columns directly instead.
_IS_SQLITE = "sqlite" in os.getenv("DATABASE_URL", "sqlite").lower()

# Every field the free-text search needs to reach, concatenated and lowercased.
_SEARCH_SOURCE_FIELDS = (
    "name", "community", "sub_community", "building_cluster", "unit_number",
    "mobile_1", "mobile_2", "mobile_3", "email_address", "plot_number",
    "pi_number", "project", "developer", "property_type", "nationality",
)
SEARCH_TEXT_EXPR = "lower(" + " || ' ' || ".join(
    f"coalesce({f}, '')" for f in _SEARCH_SOURCE_FIELDS
) + ")"

_MOBILE_BLOB = " || ' ' || ".join(
    f"coalesce({f}, '')" for f in ("mobile_1", "mobile_2", "mobile_3"))

if _IS_SQLITE:
    # SQLite has no regexp_replace; strip the punctuation that actually occurs
    # in the cleaned E.164 output.
    MOBILE_DIGITS_EXPR = _MOBILE_BLOB
    for _ch in ("+", "-", " ", "(", ")"):
        MOBILE_DIGITS_EXPR = f"replace({MOBILE_DIGITS_EXPR}, '{_ch}', '')"
    # No regex: approximate "looks like a real international number".
    HAS_VALID_MOBILE_EXPR = (
        "(mobile_1 IS NOT NULL AND mobile_1 <> '' "
        "AND lower(mobile_1) <> 'n/a' AND length(mobile_1) >= 11 "
        "AND substr(mobile_1, 1, 1) = '+')"
    )
else:
    MOBILE_DIGITS_EXPR = f"regexp_replace({_MOBILE_BLOB}, '[^0-9]', '', 'g')"
    # Mirrors the three accepted shapes the API previously evaluated per row at
    # query time: UAE mobile, UAE landline, and any other E.164 number.
    HAS_VALID_MOBILE_EXPR = (
        "(mobile_1 IS NOT NULL AND mobile_1 <> '' "
        "AND lower(mobile_1) <> 'n/a' AND ("
        r"mobile_1 ~ '^\+9715[024568][0-9]{7}$' OR "
        r"mobile_1 ~ '^\+971[234679][0-9]{7}$' OR "
        r"mobile_1 ~ '^\+[1-9][0-9]{9,14}$'))"
    )


# community|building|unit blocking key. Deliberately expressed with only
# CASE/upper/trim/coalesce/nullif so one definition serves PostgreSQL and the
# SQLite dev database alike.
_PROPERTY_UNIT_EXPR = (
    "coalesce(nullif(trim(unit_number), ''), nullif(trim(plot_number), ''))"
)
PROPERTY_KEY_EXPR = (
    "CASE WHEN trim(coalesce(community, '')) <> '' "
    f"AND {_PROPERTY_UNIT_EXPR} IS NOT NULL "
    "THEN upper(trim(community)) || '|' || "
    "upper(trim(coalesce(building_cluster, ''))) || '|' || "
    f"upper({_PROPERTY_UNIT_EXPR}) END"
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserRole:
    ADMIN = "ADMIN"
    DATA_PROCESSOR = "DATA_PROCESSOR"
    VIEWER = "VIEWER"
    ALL = (ADMIN, DATA_PROCESSOR, VIEWER)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.VIEWER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    can_export: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExportAuditLog(Base):
    __tablename__ = "export_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True)
    format: Mapped[str] = mapped_column(String(16))
    filter_criteria: Mapped[dict | None] = mapped_column(JSON)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    exported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class RecordEditAudit(Base):
    __tablename__ = "record_edits_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True)
    field_name: Mapped[str] = mapped_column(String(64), index=True)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class JobStatus:
    UPLOADED = "UPLOADED"
    READING = "READING"
    PROCESSING = "PROCESSING"
    VALIDATING = "VALIDATING"
    SAVING = "SAVING"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    ALL = (UPLOADED, READING, PROCESSING, VALIDATING, SAVING, PAUSED, CANCELLED,
           COMPLETED, COMPLETED_WITH_ERRORS, FAILED)

    # States that imply a worker should be actively advancing the job. A row
    # sitting in one of these with a stale heartbeat means its worker died.
    ACTIVE = (READING, PROCESSING, VALIDATING, SAVING, PAUSED)

    # Terminal states: no worker will touch these again.
    TERMINAL = (CANCELLED, COMPLETED, COMPLETED_WITH_ERRORS, FAILED)


class JobSignal:
    """Out-of-band control requests, stored on the job row.

    Previously these lived in a module-level dict, which only worked when the
    request that set the signal happened to land on the same process running
    the job. Persisting them means pause/cancel behave identically with any
    number of workers, and survive a restart.
    """
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    CANCEL = "CANCEL"


class RecordStatus:
    VALID = "VALID"
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"
    INCOMPLETE = "INCOMPLETE"
    QUARANTINED = "QUARANTINED"   # parsed but failed a hard business rule


class SourceFile(Base):
    __tablename__ = "source_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(512), index=True)
    stored_path: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content_sha256: Mapped[str] = mapped_column(String(64), index=True)
    detected_format: Mapped[str | None] = mapped_column(String(32))
    sheet_count: Mapped[int | None] = mapped_column(Integer)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="source_file")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_file_id: Mapped[int] = mapped_column(ForeignKey("source_files.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.UPLOADED, index=True)

    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    current_sheet: Mapped[str | None] = mapped_column(String(255))
    batch_size: Mapped[int] = mapped_column(Integer, default=1000)

    # what the mapper decided, surfaced so the UI can show provenance
    mapping_report: Mapped[dict | None] = mapped_column(JSON)

    # Pause/resume/cancel requested by an operator; read by the worker between
    # batches. NULL means "no pending request".
    control_signal: Mapped[str | None] = mapped_column(String(16))

    # Touched by the worker on every progress tick. The startup reaper uses it
    # to tell a genuinely running job from one whose process is gone.
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    message: Mapped[str | None] = mapped_column(Text)

    source_file: Mapped[SourceFile] = relationship(back_populates="jobs")
    errors: Mapped[list["ProcessingError"]] = relationship(
        back_populates="job", cascade="all, delete-orphan")


class ProcessingError(Base):
    __tablename__ = "processing_errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
    sheet_name: Mapped[str | None] = mapped_column(String(255))
    batch_number: Mapped[int | None] = mapped_column(Integer)
    source_row: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(16), default="ERROR")  # ERROR | WARNING
    code: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[ProcessingJob] = relationship(back_populates="errors")


class Record(Base):
    """The 23 standard fields + provenance + quality metadata.

    Every business field is nullable: the audit showed only Name, Unit Number
    and Mobile 1 are near-universal across the 100 source files. Absent data is
    stored as NULL, never as an invented value.
    """
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- the 23 target fields ------------------------------------------
    name: Mapped[str | None] = mapped_column(String(512), index=True)
    community: Mapped[str | None] = mapped_column(String(255), index=True)
    sub_community: Mapped[str | None] = mapped_column(String(255), index=True)
    building_cluster: Mapped[str | None] = mapped_column(String(255), index=True)
    unit_number: Mapped[str | None] = mapped_column(String(128), index=True)
    size: Mapped[float | None] = mapped_column(Float)
    plot_reg_no: Mapped[str | None] = mapped_column(String(128))
    plot_number: Mapped[str | None] = mapped_column(String(128), index=True)
    dmno: Mapped[str | None] = mapped_column(String(64))
    dmsubno: Mapped[str | None] = mapped_column(String(64))
    bedroom: Mapped[str | None] = mapped_column(String(64), index=True)
    party_type: Mapped[str | None] = mapped_column(String(32), index=True)   # Buyer/Seller
    mobile_1: Mapped[str | None] = mapped_column(String(32), index=True)
    mobile_2: Mapped[str | None] = mapped_column(String(32))
    mobile_3: Mapped[str | None] = mapped_column(String(32))
    email_address: Mapped[str | None] = mapped_column(String(320), index=True)
    pi_number: Mapped[str | None] = mapped_column(String(64), index=True)
    nationality: Mapped[str | None] = mapped_column(String(128))
    property_type: Mapped[str | None] = mapped_column(String(128), index=True)
    record_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    procedure_value: Mapped[float | None] = mapped_column(Float)
    developer: Mapped[str | None] = mapped_column(String(255), index=True)
    project: Mapped[str | None] = mapped_column(String(255), index=True)

    # --- provenance ------------------------------------------------------
    # ON DELETE CASCADE: ProcessingError already cascaded, Record did not, so
    # deleting a job left its rows behind pointing at a job id that no longer
    # exists.
    job_id: Mapped[int] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="CASCADE"), index=True)
    source_file: Mapped[str] = mapped_column(String(512), index=True)
    source_sheet: Mapped[str | None] = mapped_column(String(255))
    source_row: Mapped[int | None] = mapped_column(Integer)

    # --- quality & dedup -------------------------------------------------
    status: Mapped[str] = mapped_column(String(24), default=RecordStatus.VALID, index=True)
    identity_hash: Mapped[str] = mapped_column(String(64), index=True)
    fuzzy_match_score: Mapped[float | None] = mapped_column(Float)
    fuzzy_matched_id: Mapped[int | None] = mapped_column(Integer)
    validation_flags: Mapped[list | None] = mapped_column(JSON)
    enriched_fields: Mapped[list | None] = mapped_column(JSON)
    owner_count: Mapped[int | None] = mapped_column(Integer)   # joint ownership size
    # Which set of engine rules produced this row. See engine/__init__.py.
    # NULL means it predates versioning, which is equivalent to "stale".
    # Indexed because the reprocess planner's only question is "which rows are
    # not at the current version", asked over the whole table.
    engine_version: Mapped[int | None] = mapped_column(Integer, index=True)
    extras: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # --- search acceleration (database-generated, never written by the app) --
    # These exist so the dashboard's two hottest predicates stop being computed
    # per row at query time:
    #
    #   search_text       one lowercased blob of every searchable field, with a
    #                     single GIN trigram index over it. Replaces an OR of
    #                     ILIKE across 13 separately-indexed columns, which the
    #                     planner could only answer with a full sequential scan.
    #   mobile_digits     digits-only form of all three mobile columns, so a
    #                     number can be found however it was typed.
    #   has_valid_mobile  the default view's "verified valid mobile" rule,
    #                     evaluated once at write time instead of running three
    #                     regexes against every row on every page load.
    #
    # Computed(persisted=True) emits GENERATED ALWAYS AS ... STORED, so
    # SQLAlchemy omits them from INSERT/UPDATE automatically and no ingest or
    # edit path can leave them stale.
    # Blocking key for Tier-2 fuzzy dedup: community|building|unit, uppercased,
    # falling back to plot number when there is no unit. NULL when the row has
    # no locatable property, so the partial index below stays small.
    #
    # This exists as a generated column for the same reason search_text does --
    # dedup has to probe it for a whole batch of incoming rows at once, and an
    # expression the planner cannot index turns every batch into a table scan.
    # engine/dedup.py:extract_property_key() produces the identical string in
    # Python; test_dedup_key_matches_sql_expression guards the pair.
    property_key: Mapped[str | None] = mapped_column(
        Text, Computed(PROPERTY_KEY_EXPR, persisted=True), nullable=True)

    search_text: Mapped[str | None] = mapped_column(
        Text, Computed(SEARCH_TEXT_EXPR, persisted=True), nullable=True)
    mobile_digits: Mapped[str | None] = mapped_column(
        Text, Computed(MOBILE_DIGITS_EXPR, persisted=True), nullable=True)
    has_valid_mobile: Mapped[bool | None] = mapped_column(
        Boolean, Computed(HAS_VALID_MOBILE_EXPR, persisted=True), nullable=True)

    __table_args__ = (
        Index("ix_records_location", "community", "building_cluster", "unit_number"),
        # Tier-2 dedup probes this for every incoming batch.
        Index("ix_records_property_key", "property_key"),
        Index("ix_records_job_status", "job_id", "status"),
        # run_job preloads every identity_hash already stored for the file it is
        # about to ingest; without this the lookup scans the whole table.
        # Deliberately NOT unique: the pipeline records DUPLICATE-status rows on
        # purpose, and a unique constraint would reject them at insert.
        Index("ix_records_sourcefile_identity", "source_file", "identity_hash"),
    )


class LeadStage:
    """Where a lead sits in the sales conversation, not its data quality.

    Deliberately separate from Record.status (VALID / INVALID / DUPLICATE /
    INCOMPLETE), which describes the row, not the person. Overloading one field
    with both meanings is how "is this record clean?" and "did we sell to them?"
    become the same question, and neither can be answered afterwards.
    """
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    INTERESTED = "INTERESTED"
    NEGOTIATING = "NEGOTIATING"
    WON = "WON"
    LOST = "LOST"
    # Honoured by list and export paths. An opt-out that only lives in a note
    # field is not an opt-out.
    DO_NOT_CONTACT = "DO_NOT_CONTACT"

    ALL = (NEW, CONTACTED, INTERESTED, NEGOTIATING, WON, LOST, DO_NOT_CONTACT)
    OPEN = (NEW, CONTACTED, INTERESTED, NEGOTIATING)


class ActivityKind:
    CALL = "CALL"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    MEETING = "MEETING"
    NOTE = "NOTE"
    STAGE_CHANGE = "STAGE_CHANGE"

    ALL = (CALL, WHATSAPP, EMAIL, MEETING, NOTE, STAGE_CHANGE)


class Lead(Base):
    """Outreach state for one owner. Created on first contact, not at ingest.

    Not columns on Record, for two reasons. At 20M rows, where a small fraction
    is ever worked, per-lead columns would be mostly NULL and every schema
    change would rewrite the whole table. And Record is derived data: it is
    deleted and rewritten wholesale whenever a job is reprocessed.

    That second point drives the keying. `identity_hash` is the durable link,
    because it survives a reprocess that renumbers every row. `record_id` is a
    convenience pointer for joins and is deliberately ON DELETE SET NULL: when
    reprocessing deletes the record, the lead must NOT go with it. Call history
    is not derivable from a source file -- lose it and it is gone.
    """
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The durable identity. Survives reprocessing; relink_leads() re-attaches
    # record_id afterwards by matching on it.
    identity_hash: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    record_id: Mapped[int | None] = mapped_column(
        ForeignKey("records.id", ondelete="SET NULL"), index=True)

    stage: Mapped[str] = mapped_column(String(24), default=LeadStage.NEW, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True)
    # The one question a sales desk asks every morning: what is due today.
    next_action_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    activities: Mapped[list["LeadActivity"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan")

    __table_args__ = (
        # The work queue: "my open leads, soonest first".
        Index("ix_leads_queue", "owner_user_id", "stage", "next_action_at"),
    )


class LeadActivity(Base):
    """Append-only record of what was actually done. Never edited, never derived."""
    __tablename__ = "lead_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Hangs off the lead, never off the record, so a reprocess cannot cascade
    # it away.
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True)
    # Denormalised so history stays readable after a user is deleted.
    user_email: Mapped[str] = mapped_column(String(320))

    kind: Mapped[str] = mapped_column(String(24), index=True)
    outcome: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True)

    lead: Mapped["Lead"] = relationship(back_populates="activities")


class ErasureRequest(Base):
    """A person asked to be removed. Durable, because records are not.

    Redacting the rows is not enough on its own: records are derived data,
    rebuilt from the stored source file whenever a job is reprocessed, and that
    file still contains the person. Without a standing record of the request,
    the next reprocess quietly restores what was erased.

    Keyed by identity_hash for the same reason leads are -- it is the only
    identifier that survives rows being deleted and rewritten. apply_erasures()
    re-applies redaction after every ingest.

    Kept separate from Lead: someone can ask to be erased without ever having
    been contacted, and an auditor asks for this register on its own.
    """
    __tablename__ = "erasure_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    identity_hash: Mapped[str] = mapped_column(String(64), index=True, unique=True)

    requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True)
    # Denormalised so the register stays complete after a user is deleted.
    requested_by_email: Mapped[str] = mapped_column(String(320))
    reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_redacted: Mapped[int] = mapped_column(Integer, default=0)
