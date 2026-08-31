# Normalization and E.164 sanitization routines
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
_SQFT_VAL_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:sq\s*\.?\s*ft|sqft|square\s*feet|feet)", re.I)
_UNIT_STRIP_RE = re.compile(r"\s*(?:sqm|sq\s*\.?\s*m|m2|m²|sq\s*meter|square\s*meter|sq\s*\.?\s*ft|sqft|square\s*feet|feet|ft)\s*$", re.I)
SQM_TO_SQFT_MULT = 10.763910416711


def clean_size(v, raw_header: str | None = None) -> float | None:
    """Clean size number, automatically converting Sqm (m2) to Sq.Ft (1 m2 = 10.76391 sq.ft).

    The unit can be stated in the value ("100 sqm") or only in the column header
    ("Total Size Sqm."). A unit on the value wins, because it describes that one
    cell; the header is the fallback for the far commoner case of a bare number
    under a headline that names the unit once.
    """
    if v is None:
        return None

    is_sqm = False
    value_states_unit = False
    cleaned_input = v
    if isinstance(v, str):
        if _SQM_VAL_RE.search(v):
            is_sqm = value_states_unit = True
        elif _SQFT_VAL_RE.search(v):
            # Explicitly square feet: never re-convert, whatever the header says.
            value_states_unit = True
        cleaned_input = _UNIT_STRIP_RE.sub("", v).strip()

    # Checked for every value type, not just non-strings. Reading a file gives
    # strings, so gating this behind `elif isinstance(v, str)` meant the header
    # was consulted for almost nothing and sq.m columns were stored 10.76x too
    # small.
    if not value_states_unit and raw_header and _SQM_HEADER_RE.search(str(raw_header)):
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


# --------------------------------------------------------------------------
# property type
# --------------------------------------------------------------------------
# Source registers state property type in DLD vocabulary ("Unit", "Flat",
# "Land", "Commercial") while the sales desk works in market vocabulary
# (Apartment, Villa, Townhouse, Plot). Left raw, the same kind of property
# splits across several filter values and the field is close to unusable, which
# is a large part of why it looked empty even where it was populated.
#
# Canonical vocabulary is deliberately small. Distinctions the source data
# cannot support -- Villa vs Townhouse, Apartment vs Duplex -- are not invented
# here; they need the property reference layer.
PROPERTY_TYPES = (
    "Apartment", "Villa", "Townhouse", "Penthouse", "Plot", "Office",
    "Retail", "Warehouse", "Building", "Hotel Apartment", "Commercial",
    "Labour Camp", "Showroom",
)

# Matched on the normalised (uppercase, punctuation-stripped) value. Longest
# phrase wins, so "HOTEL APARTMENT" is not read as "APARTMENT".
_PROPERTY_TYPE_MAP = {
    "APARTMENT": "Apartment", "APARTMENTS": "Apartment", "APT": "Apartment",
    "FLAT": "Apartment", "FLATS": "Apartment", "UNIT": "Apartment",
    "UNITS": "Apartment", "RESIDENTIAL FLAT": "Apartment",
    "RESIDENTIAL UNIT": "Apartment", "RESIDENTIAL APARTMENT": "Apartment",
    "STUDIO": "Apartment",
    "VILLA": "Villa", "VILLAS": "Villa", "RESIDENTIAL VILLA": "Villa",
    "INDEPENDENT VILLA": "Villa", "SINGLE VILLA": "Villa",
    "TOWNHOUSE": "Townhouse", "TOWN HOUSE": "Townhouse", "TH": "Townhouse",
    "PENTHOUSE": "Penthouse", "PENT HOUSE": "Penthouse",
    "DUPLEX": "Apartment",
    "LAND": "Plot", "PLOT": "Plot", "VACANT LAND": "Plot",
    "RESIDENTIAL LAND": "Plot", "COMMERCIAL LAND": "Plot", "LAND PLOT": "Plot",
    "OFFICE": "Office", "OFFICES": "Office", "OFFICE SPACE": "Office",
    "SHOP": "Retail", "SHOPS": "Retail", "RETAIL": "Retail",
    "SHOWROOM": "Showroom", "SHOW ROOM": "Showroom",
    "WAREHOUSE": "Warehouse", "STORE": "Warehouse", "STORAGE": "Warehouse",
    "BUILDING": "Building", "WHOLE BUILDING": "Building", "TOWER": "Building",
    "HOTEL APARTMENT": "Hotel Apartment", "HOTEL APARTMENTS": "Hotel Apartment",
    "HOTEL ROOMS": "Hotel Apartment", "SERVICED APARTMENT": "Hotel Apartment",
    "LABOUR CAMP": "Labour Camp", "LABOR CAMP": "Labour Camp",
    "STAFF ACCOMMODATION": "Labour Camp",
    "COMMERCIAL": "Commercial", "RESIDENTIAL": "Apartment",
}

_PT_PUNCT_RE = re.compile(r"[^A-Z0-9 ]+")
# Longest-first so multi-word entries are tested before their component words.
_PT_PHRASES = sorted(_PROPERTY_TYPE_MAP, key=len, reverse=True)
_PT_PHRASE_RE = re.compile(
    r"\b(?:%s)\b" % "|".join(re.escape(k) for k in _PT_PHRASES))


def clean_property_type(v) -> str | None:
    """Normalise a property type into the canonical vocabulary, or None.

    An unrecognised value is kept rather than dropped -- the source may know
    something this map does not -- but it is title-cased so the same word in
    two letter-cases does not become two filter entries.
    """
    s = clean_text(v)
    if not s:
        return None

    key = _WS_RE.sub(" ", _PT_PUNCT_RE.sub(" ", s.upper())).strip()
    if not key:
        return None

    exact = _PROPERTY_TYPE_MAP.get(key)
    if exact:
        return exact

    # "Residential Flat - Freehold", "Unit (Apartment)" and similar: find the
    # longest known phrase anywhere in the value.
    m = _PT_PHRASE_RE.search(key)
    if m:
        return _PROPERTY_TYPE_MAP[m.group(0)]

    return s.title() if s.isupper() and len(s) > 2 else s


# --------------------------------------------------------------------------
# developers
# --------------------------------------------------------------------------
# Source files write a developer a dozen ways -- "EMAAR", "Emaar Properties",
# "EMAAR PROPERTIES PJSC", "Emaar Properties L.L.C" -- and the reference
# workbook adds its own ("Emaar Properties (JV with Meraas/Dubai Holding)").
# Left alone they are distinct strings, so every Developer filter, facet count
# and GROUP BY splits one builder into several. Canonicalising here is what the
# "Developer Reference Resolver" is supposed to do.

# Parenthetical qualifiers: "(JV with Meraas/Dubai Holding)", "(Verified)".
_DEV_PAREN_RE = re.compile(r"\s*[\(\[].*?[\)\]]", re.S)
# Legal form and generic corporate words, stripped to reach the brand token.
_DEV_SUFFIX_RE = re.compile(
    r"\b(p\.?\s?j\.?\s?s\.?\s?c|l\.?\s?l\.?\s?c|fz\s?-?\s?llc|fzco|fze|psc|"
    r"pvt|private|ltd|limited|co|company|corp|corporation|est|establishment|"
    r"group|holdings?|international|developments?|development|developers?|"
    r"properties|property|real\s+estate|realty|projects?)\b\.?",
    re.I,
)
_DEV_PUNCT_RE = re.compile(r"[^A-Z0-9 ]+")

# Placeholder values that name no builder. Storing them makes a record look
# enriched while giving the sales desk nothing to act on.
_DEV_NOT_A_DEVELOPER = {
    "MULTIPLE PRIVATE", "MULTIPLE", "VARIOUS", "VARIOUS PRIVATE", "PRIVATE",
    "PRIVATE OWNERS", "OWNER", "OWNERS", "INDIVIDUAL", "INDIVIDUALS",
    "UNKNOWN", "OTHER", "OTHERS", "MISC", "MISCELLANEOUS", "TBD", "NA",
    "SELF", "GOVERNMENT", "MUNICIPALITY",
}

# Brand token -> canonical name. Keys are the reduced form produced by
# _developer_key(), so every spelling that reduces to the same brand collapses.
_DEVELOPER_CANON = {
    "EMAAR": "Emaar Properties",
    "EMAAR SOUTH": "Emaar Properties",
    "EMAAR MISR": "Emaar Properties",
    "DAMAC": "DAMAC Properties",
    "NAKHEEL": "Nakheel",
    "ALDAR": "Aldar Properties",
    "SOBHA": "Sobha Realty",
    "MERAAS": "Meraas",
    "DUBAI": "Dubai Properties",
    "DP": "Dubai Properties",
    "DUBAI HOLDING": "Dubai Holding",
    "TECOM": "TECOM Group",
    "AZIZI": "Azizi Developments",
    "DANUBE": "Danube Properties",
    "ELLINGTON": "Ellington Properties",
    "BINGHATTI": "Binghatti Developers",
    "DEYAAR": "Deyaar Development",
    "UNION": "Union Properties",
    "WASL": "Wasl Properties",
    "OMNIYAT": "Omniyat",
    "SELECT": "Select Group",
    "MAG": "MAG Property Development",
    "TIGER": "Tiger Properties",
    "NSHAMA": "Nshama",
    "ARADA": "Arada",
    "BLOOM": "Bloom Holding",
    "EAGLE HILLS": "Eagle Hills",
    "IMKAN": "IMKAN Properties",
    "MODON": "Modon Properties",
    "ALEF": "Alef Group",
    "RAK": "RAK Properties",
    "SHARJAH": "Sharjah Holding",
    "ARABTEC": "Arabtec Holding",
    "SAMANA": "Samana Developers",
    "OBJECT ONE": "Object 1",
    "OBJECT 1": "Object 1",
    "SEVEN": "Seven Tides",
    "SEVEN TIDES": "Seven Tides",
    "SIX CONSTRUCT": "Six Construct",
    "DUBAI SOUTH": "Dubai South",
    "NAKHEEL PJSC": "Nakheel",
    "SHAPOORJI PALLONJI": "Shapoorji Pallonji",
    "ELLINGTON HOUSE": "Ellington Properties",
    "GJ": "GJ Properties",
    "PALMA": "Palma Holding",
    "REPORTAGE": "Reportage Properties",
    "ORA": "Ora Developers",
    "SWANK": "Swank Development",
    "LEOS": "LEOS Developments",
    "PRESCOTT": "Prescott Development",
    "IMAN": "Iman Developers",
    "AYS": "AYS Developers",
    "ZAYA": "Zaya Living",
    "SCHON": "Schon Properties",
    "FAKHRUDDIN": "Fakhruddin Properties",
    "ORANGE": "Orange Developments",
    "AQUA": "Aqua Properties",
    "PANTHEON": "Pantheon Development",
    "VINCITORE": "Vincitore Realty",
}


def _developer_key(s: str) -> str:
    """Reduce a developer string to its brand token for canonical lookup."""
    t = _DEV_PAREN_RE.sub(" ", s).upper()
    # "TECOM Group / Dubai Holding", "Dubai Properties (master developer);
    # many tower developers" -- the first segment names the entity, the rest
    # qualifies it.
    t = re.split(r"[/;]", t)[0]
    t = _DEV_SUFFIX_RE.sub(" ", t)
    t = _DEV_PUNCT_RE.sub(" ", t)
    return _WS_RE.sub(" ", t).strip()


def clean_developer(v) -> str | None:
    """Canonicalise a developer name, or None when the value names no builder.

    Unknown developers are preserved (title-cased when the source shouted them)
    rather than dropped -- the map cannot know every builder in the UAE, and
    losing a real one is worse than leaving it uncanonicalised.
    """
    s = clean_text(v)
    if not s:
        return None

    key = _developer_key(s)
    if not key or key in _DEV_NOT_A_DEVELOPER:
        return None

    canon_name = _DEVELOPER_CANON.get(key)
    if canon_name:
        return canon_name

    # No brand match. Keep the original wording, minus any parenthetical, and
    # fix the all-caps shouting so facets do not split on case alone.
    kept = re.split(r"[;]", _DEV_PAREN_RE.sub(" ", s))[0]
    kept = _WS_RE.sub(" ", kept).strip().rstrip(",")
    return (kept.title() if kept.isupper() and len(kept) > 3 else kept) or None


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
    "DAMAC LAGOONS": "DAMAC Lagoons",
    "DUBAI CREEK HARBOUR": "Dubai Creek Harbour",
    "EMAAR BEACHFRONT": "Emaar Beachfront",
    "DUBAI SPORTS CITY": "Dubai Sports City",
    "JUMEIRAH GOLF ESTATES": "Jumeirah Golf Estates",
    "THE VALLEY": "The Valley",
    "TILAL AL GHAF": "Tilal Al Ghaf",
}

# Districts where a trailing number is part of the name, not a stray plot number.
# "Al Barsha 1/2/3", "Al Quoz 1-4" and "DAMAC Hills 2" are separate communities
# in separate locations; collapsing them into an unnumbered base merges them and
# corrupts identity_hash along with the dedup that depends on it.
_NUMBERED_COMMUNITY_BASES = {
    "DAMAC HILLS", "AL BARSHA", "AL QUOZ", "AL NAHDA", "AL WARQA", "AL WARQAA",
    "MUHAISNAH", "JUMEIRAH", "AL SUFOUH", "AL QUSAIS", "AL TWAR", "AL MIZHAR",
    "INTERNATIONAL CITY", "DUBAI INVESTMENT PARK", "DUBAI INVESTMENTS PARK",
    "JUMEIRAH VILLAGE", "NAD AL SHEBA", "AL SAFA", "UMM SUQEIM", "AL MANARA",
    "AL RASHIDIYA", "AL KHAIL HEIGHTS", "LIVING LEGENDS", "AL WASL",
    "SPRINGS", "MEADOWS", "LAKES", "THE SPRINGS", "THE MEADOWS", "THE LAKES",
    "EMIRATES HILLS", "AL FURJAN", "SERENA", "MUDON", "REEM",
}
# A district suffix is a single small integer. Anything larger is a plot number.
_MAX_DISTRICT_NUMBER = 9
_TRAILING_NUM_RE = re.compile(r"^(.*?)\s+(\d{1,2})$")


_COMMUNITY_HEADER_NOISE_RE = re.compile(
    r"^(total\s+owners?(\s+details)?|owners?\s+details?|owners?\s+data|owner\s+details)(\s*#\d+)?$", re.I
)


def clean_community(v) -> str | None:
    s = clean_text(v)
    if not s:
        return None

    if _COMMUNITY_HEADER_NOISE_RE.match(s.strip()):
        return None

    # The raw value is matched first. A canonical name that legitimately ends in
    # a number ("DAMAC Hills 2") has to win before the trailing-number strip
    # below can eat the digit that distinguishes it.
    upper_raw = s.upper()
    if upper_raw in _COMMUNITY_CANON_MAP:
        return _COMMUNITY_CANON_MAP[upper_raw]

    # A small trailing integer on a known district base is part of the name.
    m = _TRAILING_NUM_RE.match(s)
    if m:
        base_raw, num = m.group(1).strip(), int(m.group(2))
        base_upper = base_raw.upper()
        if base_upper in _NUMBERED_COMMUNITY_BASES and 1 <= num <= _MAX_DISTRICT_NUMBER:
            base = _COMMUNITY_CANON_MAP.get(base_upper)
            if base is None:
                base = base_raw.title() if base_raw.isupper() else base_raw
            return f"{base} {num}"

    # Anything else trailing a number is a plot/sub-location id stuck onto the
    # community name (e.g. "DAMAC HILLS 1044"); drop it.
    stripped = re.sub(r"\s+\d+$", "", s).strip()
    upper_stripped = stripped.upper()

    if upper_stripped in _COMMUNITY_CANON_MAP:
        return _COMMUNITY_CANON_MAP[upper_stripped]

    if len(stripped) > 2 and stripped.isupper():
        return stripped.title()

    return stripped if stripped else s

