"""Header → 23-field mapping layer.

Backed by resources/column_mapping.json (derived from the 100-file audit:
194 aliases over 323 distinct source header strings).

Handles the four things a plain alias table cannot:
  1. composite columns   — "Premise 1" is pipe-packed; Tiara phones are label-soup
  2. headerless sheets   — 5 files are a known 25-column owner register
  3. overloaded headers  — AREA is a locality OR a number; TYPE is buyer/seller OR a block code
  4. excluded columns    — credentials and identity documents never enter the dataset
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

RESOURCES = Path(__file__).parent / "resources"
_CFG = json.loads((RESOURCES / "column_mapping.json").read_text(encoding="utf8"))

TARGETS: list[str] = _CFG["target_fields"]

# target label -> DB column
FIELD_TO_COLUMN = {
    "Name": "name",
    "Community": "community",
    "Sub-Community": "sub_community",
    "Building/Cluster": "building_cluster",
    "Unit Number": "unit_number",
    "Size": "size",
    "Plot Reg. No": "plot_reg_no",
    "Plot Number": "plot_number",
    "DMNO": "dmno",
    "DMsubno": "dmsubno",
    "Bedroom": "bedroom",
    "Type (Buyer/Seller)": "party_type",
    "Mobile 1": "mobile_1",
    "Mobile 2": "mobile_2",
    "Mobile 3": "mobile_3",
    "Email Address": "email_address",
    "PI number": "pi_number",
    "Nationality": "nationality",
    "Property Type": "property_type",
    "Date": "record_date",
    "Procedure Value": "procedure_value",
    "Developer": "developer",
    "Project": "project",
}


def norm_header(h) -> str:
    if h is None:
        return ""
    return re.sub(r"\s+", " ", str(h).replace("`", "'").strip()).upper()


# alias -> [targets]
ALIAS: dict[str, list[str]] = {}
for _t, _srcs in _CFG["aliases"].items():
    for _s in _srcs:
        ALIAS.setdefault(norm_header(_s), []).append(_t)

EXCLUDE = {norm_header(x) for x in _CFG.get("exclude_columns", [])}
IGNORE_TO_EXTRAS = {norm_header(x) for x in _CFG.get("ignore_or_extras", [])}
DO_NOT_MAP = {norm_header(x) for x in _CFG.get("do_not_map", {})}

# Headers that legitimately feed two targets. Resolved in resolve_ambiguities().
AMBIGUOUS_PROJECT = {norm_header(x) for x in
                     ("PROJECT", "PROJECT NAME", "PROJECT_NAME_EN", "MASTER PROJECT")}

# The 25-column owner register found headerless in 5 files (positional fallback).
OWNER25 = [
    "P-NUMBER", "AREA", "USAGE", "TOTAL AREA", "PLOT NUMBER", "EMIRATE", "NAME",
    "AREA OWNED", "ADDRESS", "PHONE", "EMAIL", "FAX", "PO BOX", "GENDER", "DOB",
    "MOBILE", "SECONDARY MOBILE", "PASSPORT", "ISSUE DATE", "EXPIRY DATE",
    "PLACE OF ISSUE", "EMIRATES ID NUMBER", "EMIRATES ID EXPIRY DATE",
    "RESIDENCE COUNTRY", "NATIONALITY",
]

COMMUNITY_CODES = _CFG.get("composite_fields", {}).get("community_codes", {})


# When several columns on one sheet map to the same target, column order is the
# wrong tie-breaker. The DLD owner register puts PHONE (a landline) at position
# 10 and MOBILE at 16, so first-wins silently fills Mobile 1 with landlines and
# discards the real mobile. Lower rank wins.
PREFERENCE: dict[str, int] = {}
for _rank, _names in (
    (10, ("MOBILE", "MOBILE 1", "MOBILE1", "MOBILE  1", "MOBILE_1", "PHONE MOBILE")),
    (20, ("CONTACT NO.", "CONTACT NO", "CONTACT", "MOBILE NO", "CONTACT NUMBER")),
    (40, ("PHONE", "PHONE 1", "TELEPHONE", "TELEPHONE NUMBER", "OWNERS_PHONE")),
    (10, ("MOBILE 2", "MOBILE2", "MOBILE  2", "MOBILE_2", "SECONDARY MOBILE")),
    (40, ("PHONE HOME", "PHONE 2", "TELEPHONE RESIDENCE")),
    (10, ("NAME", "FULL NAME", "OWNER'S NAME", "OWNER NAME", "OWNERS NAME",
          "OWNERS_NAME", "OWNER_NAME", "NAMEEN", "IMPORT - OWNER NAME")),
    (30, ("CUSTOMER NAME", "JOINT ACCT NAME", "CONTACT/OCCUPIER PERSONS NAME")),
    (10, ("EMAIL", "EMAIL ADDRESS", "E-MAIL", "OWNERS_EMAIL")),
    (40, ("PERSON MAIL ADDRESS",)),
    (10, ("SIZE", "ACTUAL AREA", "ACTUAL SIZE", "BUA", "BUILT UP")),
    (30, ("TOTAL AREA", "AREA SQFT", "PLOT AREA", "PLOT SIZE", "INTERNAL AREA")),
    # NATIONALITY is the actual field; RESIDENCE COUNTRY is a residence-address
    # column that DLD exports frequently populate with a corrupted or default
    # value ("Puerto Rico 2" on the vast majority of rows in some exports,
    # traced to a source-side defect, not a parsing issue) -- it must never
    # win over a genuine NATIONALITY column on the same sheet.
    (10, ("NATIONALITY",)),
    (40, ("RESIDENCE COUNTRY", "COUNTRYNAMEEN")),
    # low-signal phone fallbacks found via the header_mapping_completed.xlsx
    # cross-check -- same precedence risk as PHONE vs MOBILE: must never win
    # a phone slot over a column that actually says "mobile"/"contact".
    (40, ("LANDLINE", "MOB", "MAIN NUMBER", "SAVED MAIN NUMBER")),
    (45, ("OTHER NUMBERS", "OTHER NUMBER", "OTHER NUMBER ( ADMIN)", "NUMBERS")),
):
    for _n in _names:
        PREFERENCE[norm_header(_n)] = _rank

DEFAULT_RANK = 50


@dataclass
class ColumnPlan:
    """Resolved mapping for one source sheet."""
    index_to_target: dict[int, str] = field(default_factory=dict)
    extras_indexes: dict[int, str] = field(default_factory=dict)
    excluded_indexes: dict[int, str] = field(default_factory=dict)
    composite: dict[str, int] = field(default_factory=dict)   # kind -> col index
    header: list[str] = field(default_factory=list)
    positional: bool = False
    unmapped_headers: list[str] = field(default_factory=list)

    def report(self) -> dict:
        return {
            "mapped": {self.header[i] if i < len(self.header) else f"col{i}": t
                       for i, t in sorted(self.index_to_target.items())},
            "composite": self.composite,
            "extras": sorted(self.extras_indexes.values()),
            "excluded": sorted(self.excluded_indexes.values()),
            "unmapped": self.unmapped_headers,
            "positional_fallback": self.positional,
        }


def _numeric_ratio(samples: list) -> float:
    vals = [s for s in samples if s not in (None, "")]
    if not vals:
        return 0.0
    n = 0
    for v in vals:
        try:
            float(str(v).replace(",", ""))
            n += 1
        except ValueError:
            pass
    return n / len(vals)


def resolve_ambiguities(plan: ColumnPlan, samples: dict[int, list]) -> None:
    """Fix the header names that mean different things in different files.

    AREA  -> numeric column is a size; text column is a locality.
    TYPE  -> only a party type if the values actually look like Buyer/Seller.
    """
    for idx, target in list(plan.index_to_target.items()):
        h = norm_header(plan.header[idx]) if idx < len(plan.header) else ""
        col = samples.get(idx, [])

        if h == "AREA":
            plan.index_to_target[idx] = "Size" if _numeric_ratio(col) > 0.7 else "Community"

        elif h == "TYPE" and target == "Type (Buyer/Seller)":
            vals = {str(v).strip().upper() for v in col if v not in (None, "")}
            if vals and not (vals & {"BUYER", "SELLER"}):
                # e.g. the A/B/C/D block codes seen in 141 rows
                plan.index_to_target.pop(idx)
                plan.extras_indexes[idx] = plan.header[idx]


# Reference/lookup workbooks describe *places*, not people. They must feed the
# enrichment layer, never the records table: a "record" built from one of these
# rows has no owner, no unit and no contact, and silently skews dashboard
# completeness metrics.
_REFERENCE_HEADERS = {
    "MASTER DEVELOPER / BUILDER", "MASTER DEVELOPER", "DEVELOPMENT TYPE",
    "CONFIDENCE",
}
_REFERENCE_SHEET_WORDS = ("developer", "legend", "method", "readme")


def is_reference_sheet(header: list[str], sheet_name: str = "") -> bool:
    """True when a sheet is a developer/community lookup rather than records."""
    name = (sheet_name or "").lower()
    if any(w in name for w in _REFERENCE_SHEET_WORDS):
        hs = {norm_header(h) for h in header if h}
        if hs & _REFERENCE_HEADERS or not hs:
            return True
    hs = {norm_header(h) for h in header if h}
    if not hs:
        return False
    # a Development + Confidence pair with no person/contact column is a lookup
    has_development = any(h.startswith("DEVELOPMENT") for h in hs)
    has_contact = bool(hs & {"NAME", "FULL NAME", "MOBILE", "MOBILE 1", "EMAIL",
                             "EMAIL ADDRESS", "CONTACT NO.", "PHONE",
                             "OWNER'S NAME", "OWNER NAME", "UNIT NUMBER",
                             "NO. OF UNIT", "FLAT NUMBER"})
    return has_development and ("CONFIDENCE" in hs or bool(hs & _REFERENCE_HEADERS)) \
        and not has_contact


_PERSON_TARGETS = {"Name", "Mobile 1", "Mobile 2", "Mobile 3", "Email Address"}
_PLACE_TARGETS = {"Building/Cluster", "Unit Number", "Bedroom", "DMNO", "DMsubno",
                  "Sub-Community", "Plot Reg. No"}


def sheet_role(targets: set[str]) -> str:
    """Classify a mapped sheet as 'property', 'owner', 'both' or 'other'.

    The DLD exports split one logical record across two sheets keyed on
    P-NUMBER: the property sheet carries the location, the owner sheet carries
    the person. Stored separately, every row is half-empty.
    """
    if "PI number" not in targets:
        return "both" if targets & _PERSON_TARGETS else "other"
    has_person = bool(targets & _PERSON_TARGETS)
    has_place = bool(targets & _PLACE_TARGETS)
    if has_person and has_place:
        return "both"
    if has_person:
        return "owner"
    if has_place:
        return "property"
    return "other"


def _matches_owner25(samples: dict[int, list] | None) -> bool:
    """Confirm a headerless 25-column sheet really is the DLD owner register.

    Signature: col0 is a numeric P-NUMBER and col6 holds a name, in most rows.
    Guards against unrelated 25-wide sheets (e.g. the 'Sustainable con' sheet,
    which declares 25 columns but only populates three).
    """
    if not samples:
        return False
    pnums = [v for v in samples.get(0, []) if v not in (None, "")]
    names = [v for v in samples.get(6, []) if v not in (None, "")]
    if len(pnums) < 3 or len(names) < 3:
        return False
    numeric = 0
    for v in pnums:
        try:
            float(str(v).replace(",", ""))
            numeric += 1
        except ValueError:
            pass
    if numeric / len(pnums) < 0.8:
        return False
    alpha = sum(1 for v in names if re.search(r"[A-Za-z؀-ۿ]", str(v)))
    return alpha / len(names) >= 0.7


_EMAIL_LIKE_RE = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")


def _matches_name_phone_email(samples: dict[int, list] | None, n_cols: int) -> bool:
    """Confirm a small headerless 3-4 column sheet is a plain lead list.

    Signature: col0 alphabetic (a name), col1 phone-shaped, col2 an email, in
    most sampled rows. Seen in small lead-list exports (e.g. "24 Luxury leads")
    that would otherwise silently produce zero records -- every row has a real
    contact in it, there's just no header row to name the columns.
    """
    if not samples or n_cols not in (3, 4):
        return False
    names = [v for v in samples.get(0, []) if v not in (None, "")]
    phones = [v for v in samples.get(1, []) if v not in (None, "")]
    emails = [v for v in samples.get(2, []) if v not in (None, "")]
    if len(names) < 3 or len(phones) < 3 or len(emails) < 3:
        return False
    alpha = sum(1 for v in names if re.search(r"[A-Za-z]{3,}", str(v)))
    phoneish = sum(1 for v in phones if re.search(r"\d{7,}", str(v)))
    emailish = sum(1 for v in emails if _EMAIL_LIKE_RE.search(str(v)))
    return (alpha / len(names) >= 0.7 and phoneish / len(phones) >= 0.7
            and emailish / len(emails) >= 0.7)


def build_plan(header: list[str], headerless: bool, n_cols: int,
               samples: dict[int, list] | None = None) -> ColumnPlan:
    plan = ColumnPlan(header=list(header))

    if headerless:
        # Only two shapes are recognised positionally; anything else stays
        # unmapped rather than being guessed at.
        if n_cols >= 25 and _matches_owner25(samples):
            plan.positional = True
            plan.header = list(OWNER25)
            header = plan.header
        elif _matches_name_phone_email(samples, n_cols):
            plan.positional = True
            plan.header = ["Name", "Mobile 1", "Email Address"] + (
                ["extra"] if n_cols == 4 else [])
            header = plan.header
        else:
            plan.unmapped_headers = [f"col{i}" for i in range(n_cols)]
            return plan

    for i, raw in enumerate(header):
        h = norm_header(raw)
        if not h:
            continue
        if h in EXCLUDE:
            plan.excluded_indexes[i] = raw
            continue
        if h == "PREMISE 1":
            plan.composite["premise1"] = i
            continue
        if h in ("PREMISE 2", "PREMISE 3"):
            continue                      # empty in every row of every audited sheet
        if h in ("OWNERS_PHONE",):
            plan.composite["labelled_phones"] = i
            continue
        if h in ("OWNERS_EMAIL",):
            plan.composite["email_list"] = i
            continue
        if h == "AREA OWNED":
            # an ownership *share*, not the unit size — never map to Size
            plan.extras_indexes[i] = raw
            continue
        if h in DO_NOT_MAP or h in IGNORE_TO_EXTRAS:
            plan.extras_indexes[i] = raw
            continue

        targets = ALIAS.get(h)
        if not targets:
            plan.extras_indexes[i] = raw
            plan.unmapped_headers.append(raw)
            continue
        plan.index_to_target[i] = targets[0]

    # PROJECT feeds both Sub-Community and Project. If a MASTER PROJECT column
    # also exists it supplies Community and PROJECT stays Sub-Community/Project;
    # this duplication is applied at row level in apply_plan().
    if samples:
        resolve_ambiguities(plan, samples)
    return plan


# --------------------------------------------------------------------------
# composite parsers
# --------------------------------------------------------------------------
def parse_premise1(value) -> dict:
    """'JBR | DXB | NA | RIMAL 3 1101' -> community / unit / building.

    All 24,033 audited values had exactly 4 parts; part 3 is 'NA' in 57% of rows,
    in which case the unit is embedded in part 4 and we keep part 4 whole rather
    than guessing where the building name ends.
    """
    if not value:
        return {}
    parts = [p.strip() for p in str(value).split("|")]
    if len(parts) < 4:
        return {"Building/Cluster": str(value).strip()} if value else {}
    code, _emirate, unit, building = parts[0], parts[1], parts[2], parts[3]
    out: dict[str, str] = {}
    if code:
        out["Community"] = COMMUNITY_CODES.get(code.upper(), code)
    if building:
        out["Building/Cluster"] = building
    if unit and unit.upper() != "NA":
        out["Unit Number"] = unit
    return out


_PHONE_LABEL_RE = re.compile(
    r"(fax|mobile|home|work|other|tel|phone)\s*\d*\s*:\s*([^,]+)", re.I)


def parse_labelled_phones(value) -> list[str]:
    """'Fax 1: 009714..., Mobile 1: 971505518569' -> only the mobile numbers."""
    if not value:
        return []
    out = []
    for label, num in _PHONE_LABEL_RE.findall(str(value)):
        if label.lower() in ("mobile", "tel", "phone"):
            num = num.strip()
            if num:
                out.append(num)
    return out


def parse_email_list(value) -> list[str]:
    if not value:
        return []
    return [e.strip() for e in re.split(r"[,;]", str(value)) if e.strip()]


# --------------------------------------------------------------------------
_RECORD_LABEL_RE = re.compile(r"^\s*owners?\s+data\s*#?\d*\s*$", re.I)


def _acceptable(target: str, value) -> bool:
    """Reject values that cannot be what the target claims.

    Needed because several sheets carry two columns mapping to the same target
    (the CRM export has both `Name`, a record label like "Owners Data #193265",
    and `Import - Owner name`, the actual person). Without this the left-most
    column wins and the real name is lost.
    """
    if target == "Name":
        s = str(value).strip()
        if _RECORD_LABEL_RE.match(s) or s.isdigit():
            return False
    return True


def apply_plan(plan: ColumnPlan, row: list) -> tuple[dict, dict]:
    """Return (mapped_fields_by_target_label, extras)."""
    out: dict = {}
    extras: dict = {}

    def put(target: str, value, source: str | None = None):
        if value in (None, ""):
            return
        if not _acceptable(target, value):
            return
        if target not in out or out[target] in (None, ""):
            out[target] = value
        elif source and out[target] != value:
            # a lower-ranked column lost this target (e.g. PHONE vs MOBILE).
            # Keep the value rather than discarding it silently.
            extras.setdefault(source, value)

    # best-ranked source column wins each target, not the left-most one
    for i, target in sorted(
        plan.index_to_target.items(),
        key=lambda kv: (PREFERENCE.get(norm_header(plan.header[kv[0]])
                                       if kv[0] < len(plan.header) else "",
                                       DEFAULT_RANK), kv[0]),
    ):
        if i >= len(row):
            continue
        put(target, row[i], plan.header[i] if i < len(plan.header) else None)

    # a lone PROJECT column supplies both Sub-Community and Project
    if "Project" in out and "Sub-Community" not in out:
        out["Sub-Community"] = out["Project"]
    elif "Sub-Community" in out and "Project" not in out:
        src = {norm_header(plan.header[i]) for i in plan.index_to_target
               if plan.index_to_target[i] == "Sub-Community" and i < len(plan.header)}
        if src & AMBIGUOUS_PROJECT:
            out["Project"] = out["Sub-Community"]

    # composites
    if "premise1" in plan.composite:
        i = plan.composite["premise1"]
        if i < len(row):
            for k, v in parse_premise1(row[i]).items():
                put(k, v)

    if "labelled_phones" in plan.composite:
        i = plan.composite["labelled_phones"]
        if i < len(row):
            mobiles = parse_labelled_phones(row[i])
            for slot, num in zip(("Mobile 1", "Mobile 2", "Mobile 3"), mobiles):
                put(slot, num)

    if "email_list" in plan.composite:
        i = plan.composite["email_list"]
        if i < len(row):
            emails = parse_email_list(row[i])
            if emails:
                put("Email Address", emails[0])
                if len(emails) > 1:
                    extras["additional_emails"] = emails[1:]

    for i, name in plan.extras_indexes.items():
        if i < len(row) and row[i] not in (None, ""):
            extras[str(name)] = row[i]

    return out, extras


def is_repeated_header(row: list, plan: ColumnPlan) -> bool:
    """Some exports repeat the header row mid-data (audit found 16 such rows)."""
    hits = 0
    checked = 0
    for i, raw in enumerate(plan.header):
        if i >= len(row) or not raw:
            continue
        checked += 1
        if row[i] is not None and norm_header(row[i]) == norm_header(raw):
            hits += 1
    return checked > 0 and hits >= max(2, checked // 2)
