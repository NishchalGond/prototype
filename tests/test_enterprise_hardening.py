"""Automated Enterprise Hardening Verification Suite.

Tests:
1. JWT authentication, bcrypt password hashing, and RBAC roles.
2. Near-duplicate fuzzy deduplication with token normalization and synonym expansion.
3. Hardened PUT /api/records/{id} with re-cleaning, re-validation, and audit logging.
4. Export audit logging.
5. Ingestion error aggregate analysis.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from backend.app.database.session import SessionLocal, init_db
from backend.app.main import app
from backend.app.models.models import User, UserRole, Record, RecordStatus, RecordEditAudit, ExportAuditLog
from engine.dedup import calculate_name_similarity, normalize_name_tokens, extract_property_key

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure database tables are initialized."""
    init_db()


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


def test_admin_seed_and_login():
    # Trigger admin seed endpoint
    seed_res = client.post("/api/auth/seed-admin")
    assert seed_res.status_code == 200

    # Login with valid admin credentials
    login_res = client.post(
        "/api/auth/login",
        json={"email": "admin@datalink.ae", "password": "admin321"}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["user"]["email"] == "admin@datalink.ae"
    assert token_data["user"]["role"] == "ADMIN"

    # Login with invalid password
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "admin@datalink.ae", "password": "wrong_password"}
    )
    assert bad_login.status_code == 401


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
def test_hardened_record_update_and_audit():
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
        res = client.put(f"/api/records/{rec_id}", json=update_payload)
        assert res.status_code == 200
        updated = res.json()
        assert updated["name"] == "Jonathan Doe"
        assert updated["mobile_1"] == "+971509998877"
        assert updated["bedroom"] == "2 BR"

        # Check audit log trail
        audits_res = client.get(f"/api/records/{rec_id}/audits")
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
def test_export_audit_logging():
    db = SessionLocal()
    try:
        initial_count = db.scalar(select(func.count(ExportAuditLog.id))) or 0
    finally:
        db.close()

    # Trigger a CSV export
    res = client.get("/api/records/export?format=csv&limit=10")
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
def test_aggregate_error_summary():
    res = client.get("/api/errors/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_logged_errors" in data
    assert "top_error_codes" in data


def test_status_classification_rules():
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
        res1 = client.put(f"/api/records/{sparse_rec.id}", json={"name": "Sparse Contact"})
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

        res2 = client.put(f"/api/records/{complete_rec.id}", json={"unit_number": "1204"})
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


