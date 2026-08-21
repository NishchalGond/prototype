"""Reference data + enrichment.

Source: "Builders data/UAE_Development_Builders.xlsx" — 483 UAE developments
across 7 emirates, 324 with a named master developer, each carrying a
confidence level (High/Medium/Low).

Used to fill `Developer` (only 11% of source files carry one) and to
canonicalise community names. Enrichment never overwrites a value that came
from the source file, and every enriched field is recorded on the record so
the frontend can distinguish sourced data from derived data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_PUNCT_RE = re.compile(r"[^a-z0-9]+")
_NOISE = {"the", "at", "residences", "residence", "tower", "towers", "phase",
          "overall", "community", "development"}


def canon(s) -> str:
    if not s:
        return ""
    t = _PUNCT_RE.sub(" ", str(s).lower()).strip()
    words = [w for w in t.split() if w not in _NOISE]
    return " ".join(words) if words else t


@dataclass(frozen=True)
class Development:
    name: str
    emirate: str
    region: str | None
    developer: str | None
    dev_type: str | None
    confidence: str | None


class ReferenceData:
    def __init__(self, developments: list[Development]):
        self.developments = developments
        self._by_canon: dict[str, Development] = {}
        for d in developments:
            k = canon(d.name)
            if k and (k not in self._by_canon or _rank(d) > _rank(self._by_canon[k])):
                self._by_canon[k] = d

    def lookup(self, *candidates) -> Development | None:
        """Exact canonical match on any candidate, then containment."""
        keys = [canon(c) for c in candidates if c]
        for k in keys:
            if k and k in self._by_canon:
                return self._by_canon[k]
        for k in keys:
            if len(k) < 5:
                continue
            for ck, dev in self._by_canon.items():
                if len(ck) >= 5 and (k == ck or k.startswith(ck + " ") or ck in k.split()):
                    return dev
        return None

    def __len__(self) -> int:
        return len(self.developments)


_CONF_RANK = {"high": 3, "medium": 2, "low": 1}


def _rank(d: Development) -> int:
    return _CONF_RANK.get((d.confidence or "").lower(), 0) + (2 if d.developer else 0)


def _emirate_of(sheet: str) -> str:
    return sheet.replace("Developers", "").replace("(Verified)", "").strip() or "UAE"


_JSON_FALLBACK = Path(__file__).resolve().parent / "resources" / "uae_developers.json"


def _load_from_json(json_path: Path) -> ReferenceData:
    """Load developments from the bundled JSON (used on Railway where xlsx
    is gitignored)."""
    import json
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    devs = [
        Development(
            name=d["name"],
            emirate=d.get("emirate", "UAE"),
            region=d.get("region"),
            developer=d.get("developer"),
            dev_type=d.get("dev_type"),
            confidence=d.get("confidence"),
        )
        for d in data
    ]
    return ReferenceData(devs)


@lru_cache(maxsize=1)
def load_reference(path_str: str) -> ReferenceData:
    path = Path(path_str)

    # --- if direct json path ---
    if path.suffix.lower() == ".json" and path.exists():
        return _load_from_json(path)

    # --- try xlsx first (local dev) ---
    if path.exists() and path.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError:
            pass
        else:
            devs: list[Development] = []
            wb = load_workbook(path, read_only=True, data_only=True)
            try:
                for ws in wb.worksheets:
                    if "Developer" not in ws.title:
                        continue
                    rows = ws.iter_rows(values_only=True)
                    try:
                        header = [("" if c is None else str(c)).strip() for c in next(rows)]
                    except StopIteration:
                        continue
                    hl = [h.lower() for h in header]

                    def find(*needles, exact=False):
                        for i, h in enumerate(hl):
                            for n in needles:
                                if (h == n) if exact else (n in h):
                                    return i
                        return None

                    i_name = find("development")
                    i_dev = find("developer", "builder")
                    i_reg = find("region", "zone")
                    i_type = find("development type", "type")
                    i_conf = find("confidence")
                    if i_name is None:
                        continue

                    emirate = _emirate_of(ws.title)
                    for r in rows:
                        if i_name >= len(r) or r[i_name] in (None, ""):
                            continue
                        def get(i):
                            if i is None or i >= len(r):
                                return None
                            v = r[i]
                            if v in (None, "", "—", "-"):
                                return None
                            return str(v).strip()
                        devs.append(Development(
                            name=str(r[i_name]).strip(),
                            emirate=emirate,
                            region=get(i_reg),
                            developer=get(i_dev),
                            dev_type=get(i_type),
                            confidence=get(i_conf),
                        ))
            finally:
                wb.close()
            return ReferenceData(devs)

    # --- fallback: bundled JSON (Railway / production) ---
    if _JSON_FALLBACK.exists():
        return _load_from_json(_JSON_FALLBACK)

    return ReferenceData([])


_MONTHS_AND_NOISE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|"
    r"201\d|202\d|done|new|full|master|others|contacts|ongoing|update|partial|consolidated|"
    r"file is hanging|hanging|end)\b",
    re.IGNORECASE,
)


def clean_filename_community(filename: str | None) -> str:
    """Extract a clean community / project name from an uploaded file name."""
    if not filename:
        return ""
    stem = Path(filename).stem
    # If filename has a bracketed tag like [Club Villas] Club Villas.xlsx, extract
    bracket_match = re.match(r"^\[(.*?)\]\s*(.*)", stem)
    tag = None
    if bracket_match:
        tag, rest = bracket_match.groups()
        stem = rest if rest.strip() else tag

    # Strip parenthesized tokens like (2022), (c), (1)
    s = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", stem)
    # Strip noise terms
    s = _MONTHS_AND_NOISE.sub(" ", s)
    # Strip punctuation / separators
    s = re.sub(r"[-_./\\]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\b(done|new)\b", "", s, flags=re.IGNORECASE).strip()

    if not s and tag:
        s = _MONTHS_AND_NOISE.sub(" ", tag).strip()

    words = s.split()
    if words and (s.isupper() or s.islower()):
        s = " ".join(w.capitalize() for w in words)
    return s


_DUBAI_HILLS_SUBPROJECTS = (
    "club villas", "fairway vistas", "sidra", "maple", "park heights",
    "mulberry", "acacia", "park point", "park ridge", "golf place",
    "golf grove", "golf suites", "golf views", "golf ville", "emerald hills",
    "majestic vistas", "hills grove", "hills view", "collective", "elvira",
    "lime", "address hillcrest", "ellington house", "dhe", "dubai hills",
    "parkway vistas", "golf link", "golf palace", "parkridge",
)


def enrich(fields: dict, ref: ReferenceData, source_name: str | None = None) -> list[str]:
    """Fill Community (from filename if missing) and Developer from the UAE reference workbook.

    Returns the list of field names that were filled by enrichment rather than
    read from the source file. Never overwrites valid source data.
    """
    filled: list[str] = []
    inferred_comm = clean_filename_community(source_name) if source_name else ""

    # 1. If Community is absent or blank in the row, use the inferred community from filename
    if not fields.get("Community") and inferred_comm:
        fields["Community"] = inferred_comm
        filled.append("community")

    # 2. Check reference table lookup
    if len(ref):
        match = ref.lookup(
            fields.get("Project"),
            fields.get("Sub-Community"),
            fields.get("Community"),
            fields.get("Building/Cluster"),
            inferred_comm if inferred_comm else None,
        )
        if match:
            if not fields.get("Developer") and match.developer:
                fields["Developer"] = match.developer
                filled.append("developer")
            if not fields.get("Community") and match.region:
                fields["Community"] = match.region
                if "community" not in filled:
                    filled.append("community")
            if not fields.get("Property Type") and match.dev_type:
                fields["Property Type"] = match.dev_type
                filled.append("property_type")

    # 3. Dubai Hills Master Builder Fallback (All Dubai Hills sub-communities are Emaar)
    all_text = " ".join(
        str(fields.get(k) or "") for k in ("Community", "Sub-Community", "Project", "Building/Cluster")
    ).lower() + " " + inferred_comm.lower()

    if not fields.get("Developer") and any(sp in all_text for sp in _DUBAI_HILLS_SUBPROJECTS):
        fields["Developer"] = "Emaar Properties"
        filled.append("developer")

    return filled
