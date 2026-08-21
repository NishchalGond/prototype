"""SQLAlchemy models. Target: PostgreSQL. Compatible with SQLite for local dev."""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


class RecordStatus:
    VALID = "VALID"
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"
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
    job_id: Mapped[int] = mapped_column(ForeignKey("processing_jobs.id"), index=True)
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
    extras: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_records_location", "community", "building_cluster", "unit_number"),
        Index("ix_records_job_status", "job_id", "status"),
    )
