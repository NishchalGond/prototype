"""Record validation + transformation into the DB row shape.

Rules encode the audit's findings. A record is INVALID only when it cannot
identify anybody or anything; softer problems raise flags but keep the record,
because the source data is genuinely sparse (only Name / Unit Number / Mobile 1
appear in >85% of files).
"""
from __future__ import annotations

import hashlib

from . import cleaning as C


# building-level parent rows: whole-building records that are not units
_BUILDING_MARKERS = ("LEVELS", "SHOPS", "FLATS", "OFFICES")


def looks_like_building_row(extras: dict, fields: dict) -> bool:
    if fields.get("Unit Number"):
        return False
    hits = sum(1 for k in extras
               if str(k).strip().upper() in _BUILDING_MARKERS
               and extras[k] not in (None, "", 0))
    return hits >= 2


def transform(fields: dict, extras: dict) -> tuple[dict, list[str]]:
    """Map target-label dict -> DB column dict, cleaning every value."""
    flags: list[str] = []
    row: dict = {}

    row["name"] = C.clean_name(fields.get("Name"))
    row["community"] = C.clean_community(fields.get("Community"))
    row["sub_community"] = C.clean_text(fields.get("Sub-Community"))
    row["building_cluster"] = C.clean_text(fields.get("Building/Cluster"))
    row["unit_number"] = C.clean_unit(fields.get("Unit Number"))
    row["plot_reg_no"] = C.clean_text(fields.get("Plot Reg. No"))
    row["plot_number"] = C.clean_unit(fields.get("Plot Number"))
    row["dmno"] = C.clean_text(fields.get("DMNO"))
    row["dmsubno"] = C.clean_text(fields.get("DMsubno"))
    row["bedroom"], bflag = C.clean_bedroom(fields.get("Bedroom"))
    if bflag:
        flags.append(bflag)
        extras.setdefault("Bedroom (raw, rejected)", fields.get("Bedroom"))
    row["party_type"] = C.clean_party_type(fields.get("Type (Buyer/Seller)"))
    row["pi_number"] = C.clean_text(fields.get("PI number"))
    row["nationality"] = C.clean_nationality(fields.get("Nationality"))
    row["property_type"] = C.clean_text(fields.get("Property Type"))
    row["developer"] = C.clean_text(fields.get("Developer"))
    row["project"] = C.clean_text(fields.get("Project"))

    row["size"] = C.clean_size(fields.get("Size"))
    row["procedure_value"] = C.clean_number(fields.get("Procedure Value"))
    row["record_date"] = C.clean_date(fields.get("Date"))
    if fields.get("Date") is not None and row["record_date"] is None:
        flags.append("date_unparseable")

    # phones: normalize, drop duplicates, keep order, fill 3 slots
    seen: set[str] = set()
    mobiles: list[str] = []
    for key in ("Mobile 1", "Mobile 2", "Mobile 3"):
        num, flag = C.clean_phone(fields.get(key))
        if flag:
            flags.append(flag)
        if num and num not in seen:
            seen.add(num)
            mobiles.append(num)
    for i, slot in enumerate(("mobile_1", "mobile_2", "mobile_3")):
        row[slot] = mobiles[i] if i < len(mobiles) else None

    email, eflag = C.clean_email(fields.get("Email Address"))
    row["email_address"] = email
    if eflag:
        flags.append(eflag)

    if row["size"] is not None and row["size"] > 100000:
        flags.append("size_implausible")
        row["size"] = None

    return row, flags


def json_safe(value):
    """Coerce anything bound for a JSON column into a serialisable form.

    The owner register puts real datetimes (DOB, ISSUE DATE, EXPIRY DATE) into
    `extras`, and both JSONB and SQLite JSON reject them.
    """
    import datetime as _dt
    import decimal as _dec

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, _dec.Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


def identity_hash(row: dict) -> str:
    """Stable identity for dedup.

    Person + location. Mobile alone is unsafe (shared family/agent numbers) and
    location alone is unsafe (joint ownership puts several people on one unit),
    so identity is the pair.
    """
    parts = [
        (row.get("name") or "").upper(),
        row.get("mobile_1") or "",
        (row.get("community") or "").upper(),
        (row.get("building_cluster") or "").upper(),
        (row.get("unit_number") or "").upper(),
        (row.get("plot_number") or "").upper(),
    ]
    return hashlib.sha256("|".join(parts).encode("utf8")).hexdigest()


def is_valid_property_context(row: dict) -> bool:
    """A record has valid real estate property context if:
    1. It has a Unit Number, Plot Number, or PI Number.
    2. OR it has BOTH a valid Developer AND a valid Community.
    3. OR it has BOTH a Building/Cluster AND a valid Community.
    4. OR it has BOTH a Developer AND a Project.
    """
    comm = C.clean_community(row.get("community"))
    dev = C.clean_text(row.get("developer"))
    unit = C.clean_unit(row.get("unit_number"))
    plot = C.clean_unit(row.get("plot_number"))
    pi = C.clean_text(row.get("pi_number"))
    bldg = C.clean_text(row.get("building_cluster"))
    proj = C.clean_text(row.get("project"))

    if unit or plot or pi:
        return True
    if dev and comm:
        return True
    if bldg and comm:
        return True
    if dev and proj:
        return True
    return False


def count_populated_fields(row: dict) -> int:
    """Count non-null, non-N/A business fields on a record."""
    fields_to_check = [
        "name", "mobile_1", "mobile_2", "mobile_3", "email_address",
        "community", "sub_community", "building_cluster", "unit_number",
        "plot_number", "bedroom", "procedure_value", "developer", "project",
        "property_type", "party_type"
    ]
    count = 0
    for f in fields_to_check:
        val = row.get(f)
        if val is not None and str(val).strip() != "":
            if f == "community":
                comm = C.clean_community(val)
                if comm:
                    count += 1
            else:
                count += 1
    return count


def validate(row: dict) -> tuple[bool, list[str]]:
    """A record must identify a person OR a property. Both empty = useless."""
    flags: list[str] = []
    has_person = bool(row.get("name") or row.get("mobile_1") or row.get("email_address"))

    comm = C.clean_community(row.get("community"))

    has_property = bool(row.get("unit_number") or row.get("plot_number")
                        or row.get("building_cluster") or row.get("pi_number")
                        or comm or row.get("developer") or row.get("project"))

    if not has_person and not has_property:
        return False, ["empty_record"]
    if not has_person:
        flags.append("no_contact")
    if not has_property:
        flags.append("no_location")
    if not row.get("mobile_1") and not row.get("email_address"):
        flags.append("uncontactable")
    return True, flags

