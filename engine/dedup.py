"""Fuzzy Deduplication and Near-Duplicate Resolution Engine.

Uses standard library difflib and token-normalization heuristics to detect
owner name variations (e.g. "Mohammed Al Rashid" vs "Mohd. Al-Rashid" or
"Emaar Properties PJSC" vs "Emaar Properties") associated with the same
property unit or phone number.
"""
from __future__ import annotations

import difflib
import re
from typing import Any

# Common prefixes, titles, particles, and corporate suffixes to strip for token comparison
_STRIP_TOKENS = {
    "MR", "MRS", "MS", "MISS", "DR", "ENG", "ENGINEER", "SHEIKH", "SHEIKHA",
    "AL", "EL", "BIN", "IBN", "BINT", "THE", "LLC", "PJSC", "FZE", "FZCO",
    "HOLDINGS", "PROPERTIES", "REAL", "ESTATE", "DEVELOPMENT", "LIMITED", "LTD"
}

# Common name contractions and phonetic transliteration synonyms in UAE registers
_NAME_SYNONYMS = {
    "MOHD": "MOHAMMED",
    "MOHMD": "MOHAMMED",
    "MD": "MOHAMMED",
    "MOHAMAD": "MOHAMMED",
    "MOHAMMAD": "MOHAMMED",
    "MUHAMMAD": "MOHAMMED",
    "MUHAMMED": "MOHAMMED",
    "AHMD": "AHMED",
    "AHMAD": "AHMED",
    "ABD": "ABDUL",
    "ABDEL": "ABDUL",
    "SYED": "SAYED",
    "FATMA": "FATIMA",
}


def normalize_name_tokens(name: str | None) -> str:
    """Normalize, expand contractions, and sort name tokens to maximize fuzzy match recall."""
    if not name:
        return ""
    # Uppercase and remove punctuation
    clean = re.sub(r"[^\w\s]", " ", str(name).upper())
    tokens = [t for t in clean.split() if t]
    
    # Expand synonyms/contractions (e.g. MOHD -> MOHAMMED)
    expanded = [_NAME_SYNONYMS.get(t, t) for t in tokens]
    
    # Filter out common stop-tokens if more than 1 token remains
    filtered = [t for t in expanded if t not in _STRIP_TOKENS]
    final_tokens = filtered if filtered else expanded
    
    # Sort tokens so word reordering (e.g. "Rashid Mohammed" vs "Mohammed Rashid") matches 100%
    return " ".join(sorted(final_tokens))


def calculate_name_similarity(name1: str | None, name2: str | None) -> float:
    """Calculate string similarity ratio between two names (0.0 to 1.0)."""
    if not name1 or not name2:
        return 0.0
    
    n1 = normalize_name_tokens(name1)
    n2 = normalize_name_tokens(name2)
    
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    
    return difflib.SequenceMatcher(None, n1, n2).ratio()


def extract_property_key(row: dict[str, Any]) -> str | None:
    """Generate compound property location key (Community + Unit/Plot)."""
    comm = (row.get("community") or "").strip().upper()
    unit = (row.get("unit_number") or row.get("plot_number") or "").strip().upper()
    bldg = (row.get("building_cluster") or "").strip().upper()
    
    if comm and unit:
        return f"{comm}|{bldg}|{unit}"
    return None
