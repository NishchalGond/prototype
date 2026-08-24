"""Test suite for comprehensive number normalization.

Tests:
1. Phone number float .0 stripping and scientific notation handling.
2. UAE mobile and landline standard E.164 normalization.
3. International phone normalization.
4. Multi-phone extraction from single cell.
5. Monetary values and procedure values cleaning & rounding.
6. Area/size SqM to SqFt conversion and rounding.
7. Unit number, plot number, and code float .0 and comma normalization.
"""
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

import pytest
from engine import cleaning as C
from engine import validation as V


def test_phone_float_zero_stripping():
    # Excel float input as float or str with .0
    assert C.clean_phone(971501234567.0) == ("+971501234567", None)
    assert C.clean_phone("971501234567.0") == ("+971501234567", None)
    assert C.clean_phone(501234567.0) == ("+971501234567", None)
    assert C.clean_phone("0501234567.0") == ("+971501234567", None)


def test_uae_phone_formats():
    # Mobile with 050 / 50 / 00971 / +971 / 971
    assert C.clean_phone("0501234567") == ("+971501234567", None)
    assert C.clean_phone("501234567") == ("+971501234567", None)
    assert C.clean_phone("00971501234567") == ("+971501234567", None)
    assert C.clean_phone("+971 50 123 4567") == ("+971501234567", None)
    assert C.clean_phone("971-55-9876543") == ("+971559876543", None)
    assert C.clean_phone("971|50-6597775") == ("+971506597775", None)
    assert C.clean_phone("9710501234567") == ("+971501234567", None)

    # Landlines
    assert C.clean_phone("043920430") == ("+97143920430", None)
    assert C.clean_phone("43920430") == ("+97143920430", None)
    assert C.clean_phone("026543210") == ("+97126543210", None)


def test_international_phones():
    assert C.clean_phone("+44 7911 123456") == ("+447911123456", None)
    assert C.clean_phone("0014155552671") == ("+14155552671", None)
    assert C.clean_phone("+966 50 123 4567") == ("+966501234567", None)
    assert C.clean_phone("+91 98765 43210") == ("+919876543210", None)


def test_invalid_and_truncated_phones():
    # 8-digit truncated mobile (like +55240883, 055240883, 55240883, 97155240883)
    assert C.clean_phone("+55240883")[0] is None
    assert C.clean_phone("055240883")[0] is None
    assert C.clean_phone("55240883")[0] is None
    assert C.clean_phone("97155240883")[0] is None
    assert C.clean_phone("+97155240883")[0] is None
    assert C.clean_phone("12345")[0] is None
    assert C.clean_phone("050123")[0] is None


def test_invalid_phone_record_becomes_incomplete():
    fields = {
        "Name": "24 FRAMES LIMITED",
        "Mobile 1": "+55240883", # Invalid 8-digit truncated mobile
        "Community": "Mulberry at Park heights",
        "Building/Cluster": "MULBERRY II at PARK HEIGHTS",
        "Unit Number": "117",
        "Bedroom": "2 BR",
    }
    row, flags = V.transform(fields, {})
    assert row["mobile_1"] is None
    assert "phone_too_short_for_uae" in flags
    
    # Record has no valid contact info, so status must be INCOMPLETE
    has_name = bool(row.get("name") and str(row.get("name")).strip())
    has_contact = bool(row.get("mobile_1") or row.get("email_address"))
    has_property = V.is_valid_property_context(row)
    
    assert has_name is True
    assert has_contact is False
    assert has_property is True
    
    status = "VALID" if (has_name and has_contact and has_property) else "INCOMPLETE"
    assert status == "INCOMPLETE"


def test_multi_phone_extraction():
    numbers, flags = C.clean_phones_multi("0501234567 / 0559876543")
    assert numbers == ["+971501234567", "+971559876543"]

    numbers, flags = C.clean_phones_multi("+971501234567, 0521112233; +447911123456")
    assert numbers == ["+971501234567", "+971521112233", "+447911123456"]


def test_clean_number():
    assert C.clean_number("AED 1,500,000.50") == 1500000.50
    assert C.clean_number("2,345,678") == 2345678.0
    assert C.clean_number("$50,000") == 50000.0
    assert C.clean_number("0") is None
    assert C.clean_number(-500) is None
    assert C.clean_number(None) is None


def test_clean_size():
    assert C.clean_size("1,250.5 sq ft") == 1250.5
    # SqM to SqFt conversion
    sqm_val = 100
    expected_sqft = round(100 * C.SQM_TO_SQFT_MULT, 2)
    assert C.clean_size("100 sqm") == expected_sqft
    assert C.clean_size("100 m2") == expected_sqft
    assert C.clean_size(100, raw_header="Area (Sqm)") == expected_sqft


def test_clean_unit_and_plot():
    assert C.clean_unit("101.0") == "101"
    assert C.clean_unit(101.0) == "101"
    assert C.clean_unit("G1-0") == "G1"
    assert C.clean_unit("1,204") == "1204"
    assert C.clean_unit("Villa 45") == "Villa 45"


def test_transform_multi_phone_populates_slots():
    fields = {
        "Name": "Ahmed Al Maktoum",
        "Mobile 1": "0501234567 / 0557654321",
        "Mobile 2": "0529998877",
        "Community": "Dubai Hills Estate",
        "Unit Number": "101.0",
        "Procedure Value": "AED 2,500,000",
        "Size": "1500 sqft",
    }
    row, flags = V.transform(fields, {})
    assert row["mobile_1"] == "+971501234567"
    assert row["mobile_2"] == "+971557654321"
    assert row["mobile_3"] == "+971529998877"
    assert row["unit_number"] == "101"
    assert row["procedure_value"] == 2500000.0
    assert row["size"] == 1500.0
