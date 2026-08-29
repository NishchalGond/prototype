"""Automated Enterprise Hardening Verification Suite.

Tests:
1. JWT authentication, bcrypt password hashing, and RBAC roles.
2. Near-duplicate fuzzy deduplication with token normalization and synonym expansion.
3. Hardened PUT /api/records/{id} with re-cleaning, re-validation, and audit logging.
4. Export audit logging.
5. Ingestion error aggregate analysis.

All /api routes except /api/auth/login now require a Bearer token, so the
request helpers below attach an admin one. Tests that previously called these
endpoints anonymously were asserting behaviour that no longer exists.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from backend.app.database.session import SessionLocal, init_db
from backend.app.main import app
from backend.app.models.models import (User, UserRole, Record, RecordStatus,
                                       RecordEditAudit, ExportAuditLog,
                                       ProcessingJob, SourceFile)
from engine.dedup import calculate_name_similarity, normalize_name_tokens, extract_property_key

client = TestClient(app)

TEST_ADMIN_EMAIL = "pytest-admin@datalink.ae"
TEST_ADMIN_PASSWORD = "pytest-admin-pw-2026"


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure database tables exist and a known admin is available."""
    init_db()
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == TEST_ADMIN_EMAIL))
        if not existing:
            db.add(User(
                email=TEST_ADMIN_EMAIL,
                hashed_password=hash_password(TEST_ADMIN_PASSWORD),
                full_name="Pytest Administrator",
                role=UserRole.ADMIN,
                is_active=True,
                can_export=True,
            ))
            db.commit()

        # Records below are inserted with job_id=1. Foreign keys are enforced
        # now (PRAGMA foreign_keys=ON), so the parent rows have to exist --
        # previously SQLite accepted the dangling reference silently.
        if not db.get(ProcessingJob, 1):
            src = db.scalar(select(SourceFile).where(SourceFile.id == 1))
            if not src:
                src = SourceFile(id=1, filename="test_sheet.xlsx",
                                 stored_path="/tmp/test_sheet.xlsx",
                                 size_bytes=1, content_sha256="t" * 64)
                db.add(src)
                db.flush()
            db.add(ProcessingJob(id=1, source_file_id=src.id, status="COMPLETED"))
            db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def auth_headers(setup_database):
    """Bearer header for an admin, used by every authenticated request below."""
    res = client.post("/api/auth/login",
                      json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# --------------------------------------------------------------------------
# 1. AUTH & SECURITY TESTS
# --------------------------------------------------------------------------
def test_bcrypt_hashing():
    raw = "secure_password_123"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token_lifecycle():
    data = {"sub": "100", "email": "test@datalink.ae", "role": "ADMIN"}
    token = create_access_token(data)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "100"
    assert decoded["email"] == "test@datalink.ae"
    assert decoded["role"] == "ADMIN"


def test_admin_login(setup_database):
    login_res = client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["user"]["email"] == TEST_ADMIN_EMAIL
    assert token_data["user"]["role"] == "ADMIN"

    # Login with invalid password
    bad_login = client.post(
        "/api/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": "wrong_password"}
    )
    assert bad_login.status_code == 401


def test_public_seed_admin_endpoint_is_gone():
    """It created an ADMIN and returned the password to any caller."""
    assert client.post("/api/auth/seed-admin").status_code == 404


def test_data_endpoints_reject_anonymous_callers():
    """The records API holds owner names, phone numbers and emails."""
    for method, path in (
        ("get", "/api/records"),
        ("get", "/api/records/export"),
        ("get", "/api/dashboard/stats"),
        ("get", "/api/records/filters"),
        ("get", "/api/jobs"),
        ("get", "/api/column-mappings"),
    ):
        res = getattr(client, method)(path)
        assert res.status_code == 401, f"{method.upper()} {path} -> {res.status_code}"


def test_tokens_signed_with_the_old_hardcoded_key_are_rejected():
    import jwt
    forged = jwt.encode({"sub": "1", "role": "ADMIN"},
                        "datalink-enterprise-jwt-super-secret-key-2026",
                        algorithm="HS256")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


# --------------------------------------------------------------------------
# 2. FUZZY DEDUPLICATION TESTS
# --------------------------------------------------------------------------
def test_fuzzy_name_normalization_and_similarity():
    # Test Arabic transliteration synonyms
    sim1 = calculate_name_similarity("Mohd. Al-Rashid", "Mohammed Al Rashid")
    assert sim1 >= 0.90, f"Expected high similarity, got {sim1}"

    # Test title and corporate suffix removal
    sim2 = calculate_name_similarity("Emaar Properties PJSC", "Emaar Properties")
    assert sim2 == 1.0, f"Expected 1.0 match, got {sim2}"

    # Test word order independence
    sim3 = calculate_name_similarity("Rashid Mohammed", "Mohammed Rashid")
    assert sim3 == 1.0, f"Expected 1.0 match, got {sim3}"

    # Test completely different names
    sim4 = calculate_name_similarity("Fatima Al Mansoori", "John Smith")
    assert sim4 < 0.30


def test_property_key_extraction():
    row1 = {"community": "Dubai Hills Estate", "building_cluster": "Park Point", "unit_number": "507"}
    key1 = extract_property_key(row1)
    assert key1 == "DUBAI HILLS ESTATE|PARK POINT|507"


# --------------------------------------------------------------------------
# 3. RECORD UPDATE & AUDIT TRAIL TESTS
# --------------------------------------------------------------------------
def test_hardened_record_update_and_audit(auth_headers):
    db = SessionLocal()
    try:
        # Create a test record
        test_rec = Record(
            name="John Doe",
            community="Dubai Hills",
            unit_number="101",
            mobile_1="+971501234567",
            status=RecordStatus.VALID,
            identity_hash="test_hash_123",
            source_file="test_sheet.xlsx",
            job_id=1
        )
        db.add(test_rec)
        db.commit()
        db.refresh(test_rec)
        rec_id = test_rec.id

        # Update record via PUT endpoint
        update_payload = {
            "name": "Jonathan Doe",
            "mobile_1": "050-999-8877", # Should be cleaned to +971509998877
            "bedroom": "2 BR"
        }
        res = client.put(f"/api/records/{rec_id}", json=update_payload, headers=auth_headers)
        assert res.status_code == 200
        updated = res.json()
        assert updated["name"] == "Jonathan Doe"
        assert updated["mobile_1"] == "+971509998877"
        assert updated["bedroom"] == "2 BR"

        # Check audit log trail
        audits_res = client.get(f"/api/records/{rec_id}/audits", headers=auth_headers)
        assert audits_res.status_code == 200
        audits = audits_res.json()
        assert len(audits) >= 2 # name and mobile_1 changed

        fields_changed = {a["field_name"] for a in audits}
        assert "name" in fields_changed
        assert "mobile_1" in fields_changed

    finally:
        db.close()


# --------------------------------------------------------------------------
# 4. EXPORT AUDIT LOGGING TESTS
# --------------------------------------------------------------------------
def test_export_audit_logging(auth_headers):
    db = SessionLocal()
    try:
        initial_count = db.scalar(select(func.count(ExportAuditLog.id))) or 0
    finally:
        db.close()

    # Trigger a CSV export
    res = client.get("/api/records/export?format=csv&limit=10", headers=auth_headers)
    assert res.status_code == 200

    db = SessionLocal()
    try:
        new_count = db.scalar(select(func.count(ExportAuditLog.id))) or 0
        assert new_count == initial_count + 1
        latest = db.scalars(select(ExportAuditLog).order_by(ExportAuditLog.id.desc())).first()
        assert latest.format == "CSV"
    finally:
        db.close()


# --------------------------------------------------------------------------
# 5. AGGREGATE ERROR SUMMARY & STATUS CLASSIFICATION TESTS
# --------------------------------------------------------------------------
def test_aggregate_error_summary(auth_headers):
    res = client.get("/api/errors/summary", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_logged_errors" in data
    assert "top_error_codes" in data


def test_status_classification_rules(auth_headers):
    db = SessionLocal()
    try:
        # Record with Name & Mobile but NO property details -> INCOMPLETE
        sparse_rec = Record(
            name="Sparse Contact",
            mobile_1="+971501112233",
            community="Total Owner Details",  # Generic placeholder
            status=RecordStatus.VALID,
            identity_hash="test_sparse_hash_001",
            source_file="test_sheet.xlsx",
            job_id=1
        )
        db.add(sparse_rec)
        db.commit()
        db.refresh(sparse_rec)

        # Trigger record update validation via endpoint
        res1 = client.put(f"/api/records/{sparse_rec.id}", json={"name": "Sparse Contact"},
                          headers=auth_headers)
        assert res1.status_code == 200
        assert res1.json()["status"] == "INCOMPLETE"

        # Record WITH property details and 5+ fields -> VALID
        complete_rec = Record(
            name="Complete Lead",
            mobile_1="+971509998877",
            community="Dubai Hills Estate",
            building_cluster="The One Hotel",
            unit_number="1204",
            status=RecordStatus.INCOMPLETE,
            identity_hash="test_complete_hash_002",
            source_file="test_sheet.xlsx",
            job_id=1
        )
        db.add(complete_rec)
        db.commit()
        db.refresh(complete_rec)

        res2 = client.put(f"/api/records/{complete_rec.id}", json={"unit_number": "1204"},
                          headers=auth_headers)
        assert res2.status_code == 200
        assert res2.json()["status"] == "VALID"

    finally:
        db.close()


def test_total_owner_details_community_cleaning():
    from engine.cleaning import clean_community
    assert clean_community("Total Owner Details") is None
    assert clean_community("OWNER DETAILS") is None
    assert clean_community("Owners Data") is None
    assert clean_community("Dubai Hills Estate") == "Dubai Hills Estate"


