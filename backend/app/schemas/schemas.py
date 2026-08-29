"""Pydantic response models. These define the stable contract for Antigravity.

Rule: field names and types here do not change without a note in
FRONTEND_BACKEND_COLLABORATION.md first.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, computed_field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    # True when counting stopped at the ceiling instead of scanning the whole
    # match set, i.e. `total` is a floor ("20,000+") rather than an exact count.
    # Defaulted so existing paginated endpoints need no change.
    total_capped: bool = False


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


# --------------------------------------------------------------------------
class SourceFileOut(ORMModel):
    id: int
    filename: str
    size_bytes: int
    content_sha256: str
    detected_format: str | None
    sheet_count: int | None
    is_encrypted: bool
    uploaded_at: datetime


class JobOut(ORMModel):
    id: int
    source_file_id: int
    filename: str | None = None
    status: str
    total_rows: int
    processed_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    skipped_rows: int
    error_count: int
    progress_percent: float
    current_sheet: str | None
    batch_size: int
    message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


    # --- compatibility aliases for Antigravity's existing UI ---------------
    # Additive only. Canonical names are the ones above; these mirror the
    # stub contract so no frontend code has to change on these fields.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def error_rows(self) -> int:
        return self.invalid_rows

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completed_at(self) -> datetime | None:
        return self.finished_at

    @computed_field  # type: ignore[prop-decorator]
    def total_batches(self) -> int:
        if not self.batch_size:
            return 0
        return max(1, -(-self.total_rows // self.batch_size)) if self.total_rows else 0

    @computed_field  # type: ignore[prop-decorator]
    def current_batch(self) -> int:
        if not self.batch_size:
            return 0
        return -(-self.processed_rows // self.batch_size) if self.processed_rows else 0


class JobDetail(JobOut):
    mapping_report: dict[str, Any] | None = None


class SheetInfoOut(BaseModel):
    name: str
    total_rows: int
    n_cols: int
    headerless: bool
    is_reference: bool
    mapped_targets: list[str] = Field(default_factory=list)
    unmapped_headers: list[str] = Field(default_factory=list)
    header: list[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    job_id: int
    source_file_id: int
    filename: str
    size_bytes: int
    detected_format: str | None
    status: str
    # --- structure, inspected at upload so the UI can populate its tiles ----
    total_rows: int = 0
    sheet_count: int = 0
    mapped_target_count: int = 0
    mapped_targets: list[str] = Field(default_factory=list)
    sheets: list[SheetInfoOut] = Field(default_factory=list)
    is_reference_file: bool = False
    readable: bool = True
    message: str | None = None
    duplicate_of_job_id: int | None = Field(
        default=None,
        description="Set when this exact file (same sha256) was already uploaded.",
    )


class ProcessingErrorOut(ORMModel):
    id: int
    job_id: int
    sheet_name: str | None
    batch_number: int | None
    source_row: int | None
    severity: str
    code: str
    message: str
    payload: dict[str, Any] | None
    created_at: datetime


class RecordUpdate(BaseModel):
    name: str | None = None
    community: str | None = None
    sub_community: str | None = None
    building_cluster: str | None = None
    unit_number: str | None = None
    size: float | None = None
    plot_reg_no: str | None = None
    plot_number: str | None = None
    dmno: str | None = None
    dmsubno: str | None = None
    bedroom: str | None = None
    party_type: str | None = None
    mobile_1: str | None = None
    mobile_2: str | None = None
    mobile_3: str | None = None
    email_address: str | None = None
    pi_number: str | None = None
    nationality: str | None = None
    property_type: str | None = None
    procedure_value: float | None = None
    developer: str | None = None
    project: str | None = None
    status: str | None = None


class RecordOut(ORMModel):
    id: int
    name: str | None
    community: str | None
    sub_community: str | None
    building_cluster: str | None
    unit_number: str | None
    size: float | None
    plot_reg_no: str | None
    plot_number: str | None
    dmno: str | None
    dmsubno: str | None
    bedroom: str | None
    party_type: str | None
    mobile_1: str | None
    mobile_2: str | None
    mobile_3: str | None
    email_address: str | None
    pi_number: str | None
    nationality: str | None
    property_type: str | None
    record_date: datetime | None
    procedure_value: float | None
    developer: str | None
    project: str | None

    job_id: int
    source_file: str
    source_sheet: str | None
    source_row: int | None
    status: str
    identity_hash: str | None = None
    fuzzy_match_score: float | None = None
    fuzzy_matched_id: int | None = None
    engine_version: int | None = None
    validation_flags: list[str] | None
    enriched_fields: list[str] | None
    extras: dict[str, Any] | None
    created_at: datetime

    # --- compatibility aliases for Antigravity's existing UI ---------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def bedroom_type(self) -> str | None:
        return self.bedroom

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mobile(self) -> str | None:
        return self.mobile_1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def record_status(self) -> str:
        return self.status

    @computed_field  # type: ignore[prop-decorator]
    @property
    def size_display(self) -> str | None:
        return None if self.size is None else f"{self.size:g} sqm"


class DashboardStats(BaseModel):
    total_files: int
    total_jobs: int
    total_records: int
    # Held but not workable: opt-outs and disproved contacts. Explains why the
    # tile and the record list report different numbers.
    suppressed_records: int = 0
    valid_records: int
    invalid_records: int
    duplicate_records: int
    total_errors: int
    jobs_by_status: dict[str, int]
    records_by_status: dict[str, int]
    top_communities: list[dict[str, Any]]
    field_completeness: dict[str, float]
    last_job: JobOut | None
    success_rate: float = 0.0
    # mirrors of the stub contract so the existing dashboard keeps rendering
    community_distribution: list[dict[str, Any]] = Field(default_factory=list)
    recent_jobs: list[JobOut] = Field(default_factory=list)


class ColumnMappingOut(BaseModel):
    target_fields: list[str]
    field_to_column: dict[str, str]
    aliases: dict[str, list[str]]
    composite_fields: dict[str, Any]
    exclude_columns: list[str]
    do_not_map: dict[str, str]
    alias_count: int


class FilterOptions(BaseModel):
    communities: list[str]
    sub_communities: list[str]
    property_types: list[str]
    bedrooms: list[str]
    developers: list[str]
    source_files: list[str]
    statuses: list[str]


class AliasRequest(BaseModel):
    target_field: str
    alias: str

