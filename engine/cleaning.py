"""Value-level normalization.

Every rule here traces to a defect actually observed in the 100 source files.
Nothing invents a value: if a field cannot be parsed confidently it becomes
None and a validation flag is raised.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

# --------------------------------------------------------------------------
NULL_TOKENS = {"", "-", "--", "—", ".", "..", "n/a", "na", "null", "none", "nil",
               "#n/a", "unknown", "not available", "0", "total owner details",
               "owner details", "owners data", "total owners", "owner detail"}

_ID_PREFIX_RE = re.compile(r"^\[[A-Za-z0-9]+\]\s*")
_WS_RE = re.compile(r"\s+")


def clean_text(v, *, strip_id_prefix: bool = True) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        s = str(int(v))
    else:
        s = str(v).replace("\xa0", " ")
        if re.fullmatch(r"-?\d+\.0+", s.strip()):
            s = s.strip().split(".")[0]
    s = _WS_RE.sub(" ", s).strip()
    if strip_id_prefix:
        s = _ID_PREFIX_RE.sub("", s).strip()
    if s.lower() in NULL_TOKENS:
        return None
    return s or None


def clean_name(v) -> str | None:
    s = clean_text(v)
    if not s:
        return None
    if s.lower() in ("owner", "owners data", "name"):
        return None
    # CRM record labels like "Owners Data #193265" are not people
    if re.fullmatch(r"owners?\s+data\s*#\d+", s, re.I):
        return None
    return s


# --------------------------------------------------------------------------
# phones
# --------------------------------------------------------------------------
_UAE_PREFIXES = ("50", "52", "54", "55", "56", "58")
_UAE_LANDLINE_AREA_CODES = ("2", "3", "4", "6", "7", "9")
_PHONE_SPLIT_RE = re.compile(r"[/,;\n\r&|]|\s+(?:and|or)\s+", re.I)


def clean_phone(v) -> tuple[str | None, str | None]:
    """Return (E.164-ish normalized number, flag).

    Handles the defects the audit found: '971|50-6597775' pipe form, the
    letter-O-for-zero typo, float/scientific rendering, and separator soup.
    """
    if v is None:
        return None, None
    
    if isinstance(v, float) and v.is_integer():
        v = int(v)
        
    s = str(v).strip()
    if not s or s.lower() in NULL_TOKENS:
        return None, None

    # scientific notation from a float cell, e.g. 5.0655e10 / 7.4995E+21.
    # Excel already destroyed the trailing digits here, so the value is
    # reconstructed-at-best and is always flagged rather than trusted.
    from_scientific = False
    if re.fullmatch(r"\d+\.\d+[eE][+-]?\d+", s):
        try:
            f = float(s)
        except ValueError:
            return None, "phone_unparseable"
        if f > 1e15:
            return None, "phone_corrupt_scientific"
        s = f"{int(f)}"
        from_scientific = True
    elif re.fullmatch(r"\d+\.0+", s):
        s = s.split(".")[0]

    s = s.replace("|", " ")
    # O/o used for a leading zero
    s = re.sub(r"^[Oo](?=\d)", "0", s)
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None, "phone_no_digits"

    if digits.startswith("00"):
        digits = digits[2:]

    if len(digits) < 7:
        return None, "phone_too_short"
    if len(digits) > 15:
        return None, "phone_too_long"

    # --- resolve to E.164 only when the country is actually knowable --------
    if from_scientific:
        # keep the digits for a human to inspect; never assert a country code
        return None, "phone_precision_lost_in_excel"

    if digits.startswith("971"):
        rest = digits[3:]
        # Sources double up prefixes and keep the trunk zero:
        #   971 0 55 4570666   -> 971554570666
        #   971 00 971 56981   -> 97156981
        while rest.startswith("0"):
            rest = rest[1:]
        if rest.startswith("971"):
            rest = rest[3:]
        
        # UAE mobile: must have exactly 9 digits starting with 50, 52, 54, 55, 56, 58
        if rest[:2] in _UAE_PREFIXES:
            if len(rest) != 9:
                return None, "phone_too_short_for_uae" if len(rest) < 9 else "phone_too_long_for_uae"
            return "+971" + rest, None
            
        # UAE landline: must have exactly 8 digits starting with area code (2, 3, 4, 6, 7, 9)
        if rest and rest[0] in _UAE_LANDLINE_AREA_CODES:
            if len(rest) != 8:
                return None, "phone_too_short_for_uae" if len(rest) < 8 else "phone_too_long_for_uae"
            return "+971" + rest, None

        if len(rest) == 9:
            return "+971" + rest, None

        return None, "phone_invalid_for_uae"

    # UAE Mobile with trunk zero: 0501234567 (10 digits) -> +971501234567
    if digits.startswith("0") and len(digits) >= 2 and digits[1:3] in _UAE_PREFIXES:
        if len(digits) != 10:
            return None, "phone_too_short_for_uae" if len(digits) < 10 else "phone_too_long_for_uae"
        return "+971" + digits[1:], None

    # UAE Mobile without trunk zero: 501234567 (9 digits) -> +971501234567
    if digits[:2] in _UAE_PREFIXES:
        if len(digits) != 9:
            return None, "phone_too_short_for_uae" if len(digits) < 9 else "phone_too_long_for_uae"
        return "+971" + digits, None

    # UAE Landline with trunk zero: 043920430 (9 digits) -> +97143920430
    if digits.startswith("0") and len(digits) >= 2 and digits[1] in _UAE_LANDLINE_AREA_CODES:
        if len(digits) != 9:
            return None, "phone_too_short_for_uae" if len(digits) < 9 else "phone_too_long_for_uae"
        return "+971" + digits[1:], None

    # UAE Landline without trunk zero: 43920430 (8 digits) -> +97143920430
    if digits and digits[0] in _UAE_LANDLINE_AREA_CODES and len(digits) <= 8:
        if len(digits) != 8:
            return None, "phone_too_short_for_uae"
        return "+971" + digits, None

    if digits.startswith("0"):
        return None, "phone_local_no_country_code"

    # Standard international E.164 (10 to 15 digits)
    if 10 <= len(digits) <= 15 and not digits.startswith("0"):
        return "+" + digits, None

    return None, "phone_invalid"


def clean_phones_multi(v) -> tuple[list[str], list[str]]:
    """Extract and normalize all phone numbers from a value (which may contain multiple delimited numbers)."""
    if v is None:
        return [], []
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    if not s or s.lower() in NULL_TOKENS:
        return [], []

    if isinstance(v, int) or not _PHONE_SPLIT_RE.search(s):
        num, flag = clean_phone(v)
        return ([num] if num else []), ([flag] if flag else [])

    parts = _PHONE_SPLIT_RE.split(s)
    numbers: list[str] = []
    flags: list[str] = []
    seen: set[str] = set()
    for p in parts:
        p = p.strip()
        if not p or p.lower() in NULL_TOKENS:
            continue
        num, flag = clean_phone(p)
        if flag and flag not in flags:
            flags.append(flag)
        if num and num not in seen:
            seen.add(num)
            numbers.append(num)
    return numbers, flags


def is_mobile(number: str | None) -> bool:
    if not number:
        return False
    d = number.lstrip("+")
    if d.startswith("971"):
        return d[3:5] in _UAE_PREFIXES
    return True          # non-UAE: cannot tell, keep it


# --------------------------------------------------------------------------
# email
# --------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def clean_email(v) -> tuple[str | None, str | None]:
    s = clean_text(v, strip_id_prefix=False)
    if not s:
        return None, None
    s = s.split(",")[0].strip().lower()
    if not _EMAIL_RE.match(s):
        return None, "email_invalid"
    return s, None


# --------------------------------------------------------------------------
# numbers / dates
# --------------------------------------------------------------------------
_CURRENCY_RE = re.compile(r"[^\d.\-]")


def clean_number(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        f = float(v)
        return None if f <= 0 else round(f, 2)
    s = str(v).strip()
    if not s or s.lower() in NULL_TOKENS:
        return None
    s = _CURRENCY_RE.sub("", s)      # 'AED0' -> '0', '1,533.74' -> '1533.74'
    if not s or s in (".", "-"):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if f <= 0:
        return None
    return round(f, 2)


_SQM_HEADER_RE = re.compile(r"(sqm|sq\s*\.?\s*m|m2|m²|sq\s*meter|square\s*meter)", re.I)
_SQM_VAL_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:sqm|sq\s*\.?\s*m|m2|m²|sq\s*meter|square\s*meter)", re.I)
_UNIT_STRIP_RE = re.compile(r"\s*(?:sqm|sq\s*\.?\s*m|m2|m²|sq\s*meter|square\s*meter|sq\s*\.?\s*ft|sqft|square\s*feet|feet|ft)\s*$", re.I)
SQM_TO_SQFT_MULT = 10.763910416711


def clean_size(v, raw_header: str | None = None) -> float | None:
    """Clean size number, automatically converting Sqm (m2) to Sq.Ft (1 m2 = 10.76391 sq.ft)."""
    if v is None:
        return None

    is_sqm = False
    cleaned_input = v
    if isinstance(v, str):
        if _SQM_VAL_RE.search(v):
            is_sqm = True
        cleaned_input = _UNIT_STRIP_RE.sub("", v).strip()
    elif raw_header and _SQM_HEADER_RE.search(str(raw_header)):
        is_sqm = True

    f = clean_number(cleaned_input)
    if f is None:
        return None

    if is_sqm:
        f = round(f * SQM_TO_SQFT_MULT, 2)
    else:
        f = round(f, 2)

    return f



_EXCEL_EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)
_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y %I:%M:%S %p",
                 "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d")


def clean_date(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        n = float(v)
        if 1 < n < 80000:                      # plausible Excel serial
            from datetime import timedelta
            return _EXCEL_EPOCH + timedelta(days=n)
        return None
    s = str(v).strip()
    if not s or s.lower() in NULL_TOKENS:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# domain-specific
# --------------------------------------------------------------------------
_BED_RE = re.compile(r"(\d+)\s*(?:bhk|b\s*/?\s*r|bed(?:room)?s?)", re.I)


_BEDROOM_MAX = 10  # UAE residential listings do not exceed this; higher values
                    # are source data-entry errors (bathroom count, unit code, etc.)


def clean_bedroom(v) -> tuple[str | None, str | None]:
    """Return (value, flag). Values above a plausible residential bedroom
    count are not silently trusted -- the source is wrong, not the parser,
    so the record is flagged rather than storing a fabricated-looking "26 BR".
    """
    s = clean_text(v)
    if not s:
        return None, None
    low = s.lower()
    if "studio" in low:
        return "Studio", None
    n = None
    m = _BED_RE.search(low)
    if m:
        n = int(m.group(1))
    elif re.fullmatch(r"\d{1,3}", s):
        n = int(s)
    if n is not None:
        if n > _BEDROOM_MAX:
            return None, "bedroom_implausible"
        return f"{n} BR", None
    if low == "penthouse":
        return "Penthouse", None
    if low == "retail":
        return "Retail", None
    return s, None


def clean_unit(v) -> str | None:
    """Unit refs carry a trailing '-N' suffix in the DLD owner register
    ('G1-0' on the owner side vs 'G1' on the property side) and strip float artifacts."""
    s = clean_text(v)
    if not s:
        return None
    s = re.sub(r"(-0|[-s]+)$", "", s).strip()
    if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        s = s.replace(",", "")
    return s or None


def clean_party_type(v) -> str | None:
    s = clean_text(v)
    if not s:
        return None
    u = s.upper()
    if u.startswith("BUY"):
        return "Buyer"
    if u.startswith("SELL"):
        return "Seller"
    return None          # A/B/C/D block codes and other noise are not a party type


def clean_nationality(v) -> str | None:
    s = clean_text(v)
    if not s:
        return None
    if s.upper() in ("UAE", "U.A.E", "U.A.E."):
        return "United Arab Emirates"
    return s.title() if s.isupper() and len(s) > 3 else s


_COMMUNITY_CANON_MAP = {
    "DAMAC HILLS": "DAMAC Hills",
    "DAMAC HILLS 2": "DAMAC Hills 2",
    "DUBAI HILLS": "Dubai Hills Estate",
    "DUBAI HILLS ESTATE": "Dubai Hills Estate",
    "BUSINESS BAY": "Business Bay",
    "AL BARARI": "Al Barari",
    "AL FURJAN": "Al Furjan",
    "PALM JUMEIRAH": "Palm Jumeirah",
    "JUMEIRAH VILLAGE CIRCLE": "Jumeirah Village Circle",
    "JUMEIRAH LAKE TOWERS": "Jumeirah Lake Towers",
    "JUMEIRAH BEACH RESIDENCE": "Jumeirah Beach Residence",
    "DUBAI MARINA": "Dubai Marina",
    "DUBAI SILICON OASIS": "Dubai Silicon Oasis",
    "DOWNTOWN DUBAI": "Downtown Dubai",
    "ARABIAN RANCHES": "Arabian Ranches",
    "AL BARSHA": "Al Barsha",
    "AL KIFAF": "Al Kifaf",
    "MEYDAN": "Meydan",
    "TOWN SQUARE": "Town Square",
}


_COMMUNITY_HEADER_NOISE_RE = re.compile(
    r"^(total\s+owners?(\s+details)?|owners?\s+details?|owners?\s+data|owner\s+details)(\s*#\d+)?$", re.I
)


def clean_community(v) -> str | None:
    s = clean_text(v)
    if not s:
        return None

    if _COMMUNITY_HEADER_NOISE_RE.match(s.strip()):
        return None

    # Strip trailing plot/sub-location numbers attached to community names (e.g. DAMAC HILLS 1044 -> DAMAC HILLS)
    stripped = re.sub(r"\s+\d+$", "", s).strip()
    upper_stripped = stripped.upper()

    if upper_stripped in _COMMUNITY_CANON_MAP:
        return _COMMUNITY_CANON_MAP[upper_stripped]

    upper_raw = s.upper()
    if upper_raw in _COMMUNITY_CANON_MAP:
        return _COMMUNITY_CANON_MAP[upper_raw]

    if len(stripped) > 2 and stripped.isupper():
        return stripped.title()

    return stripped if stripped else s

