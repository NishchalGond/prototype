"""Free-text search query construction.

Replaces the original `ILIKE '%q%'` fan-out across 13 columns, which had two
fatal properties at scale:

  1. It was unindexable. Seven of the 13 columns had no trigram index, and a
     single unindexable branch inside an OR forces PostgreSQL to sequentially
     scan the whole table -- the trigram indexes on the other six were dead
     weight. At 20M rows that is a multi-second scan on every keystroke.

  2. It could not answer the question the sales desk actually asks. The whole
     phrase was matched against one column at a time, so "Mohammed Ahmed Marina
     Heights" found nothing: no single column contains all four words. Only an
     exact substring of one field ever matched.

Both are fixed by the same change. `records.search_text` is a STORED generated
column holding the lowercased concatenation of every searchable field, with a
single GIN trigram index over it. A query is tokenised and every token must
appear somewhere in that blob (AND across tokens, implicitly OR across fields),
so tokens may land in different source columns and still match. PostgreSQL
serves each token from the one GIN index and BitmapAnds the results.

SQLite has neither generated-column parity nor trigram indexes, so local dev
falls back to the per-column OR. It is slow, and on a dev-sized database that
does not matter.
"""
from __future__ import annotations

import re

from sqlalchemy import and_, or_

from ..models.models import Record

# Conversational filler the sales desk types but that carries no selectivity.
# Deliberately excludes property vocabulary ("flat", "villa", "tower", "plot"):
# those are real values in the data and dropping them would widen results.
STOPWORDS = frozenset({
    "show", "me", "find", "get", "list", "give", "search", "who", "whom",
    "owns", "own", "owner", "of", "the", "a", "an", "in", "at", "on", "for",
    "is", "are", "was", "and", "with", "that", "this", "all", "any", "please",
})

# Columns the SQLite fallback searches. Mirrors what feeds search_text.
_FALLBACK_COLUMNS = (
    Record.name, Record.community, Record.sub_community,
    Record.building_cluster, Record.unit_number, Record.mobile_1,
    Record.mobile_2, Record.mobile_3, Record.email_address,
    Record.plot_number, Record.pi_number, Record.project,
    Record.developer, Record.property_type, Record.nationality,
)

# A trigram index cannot serve a pattern shorter than three characters, so a
# query made entirely of one- and two-character tokens degrades to a scan. Such
# tokens are kept (they refine an otherwise-matching row) but never allowed to
# be the only thing narrowing the query.
MIN_TRIGRAM_LEN = 3

_PHRASE_RE = re.compile(r'"([^"]+)"')
_SPLIT_RE = re.compile(r"[\s,;|]+")
_DIGITS_RE = re.compile(r"\D+")


def _escape_like(value: str) -> str:
    """Neutralise LIKE metacharacters so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _phone_variants(token: str) -> list[str]:
    """Digit forms of a token worth matching against the stored phone digits.

    Numbers are stored in E.164 (`+971505518569`), but a sales user reads them
    off a phone in national format (`0505518569`) where a leading 0 stands in
    for the country code. A literal substring match therefore misses -- the
    stored digits contain `505518569` but never `0505518569`. Stripping leading
    zeros produces the form that is actually present.

    Tokens shorter than four digits are ignored: they are almost always a unit
    or bedroom number rather than a phone fragment, and matching them against
    every phone in the database only adds noise.
    """
    digits = _DIGITS_RE.sub("", token)
    if len(digits) < 4:
        return []

    variants = [digits]
    trunk_stripped = digits.lstrip("0")
    if trunk_stripped and trunk_stripped != digits and len(trunk_stripped) >= 4:
        variants.append(trunk_stripped)
    return variants


def tokenize(q: str) -> list[str]:
    """Split a raw query into match tokens.

    Double-quoted runs survive as single tokens, so `"al rashid"` stays a
    phrase. Filler words are dropped -- unless dropping them would leave
    nothing, in which case the query really was just filler and the original
    words are used as-is rather than returning every row in the table.
    """
    raw = (q or "").strip().lower()
    if not raw:
        return []

    phrases = [m.group(1).strip() for m in _PHRASE_RE.finditer(raw)]
    remainder = _PHRASE_RE.sub(" ", raw)
    words = [w for w in _SPLIT_RE.split(remainder) if w]

    tokens = [t for t in (phrases + words) if t]
    meaningful = [t for t in tokens if t not in STOPWORDS]
    return meaningful or tokens


def has_indexable_token(tokens: list[str]) -> bool:
    """True when at least one token is long enough for the trigram index."""
    return any(len(t) >= MIN_TRIGRAM_LEN for t in tokens)


def build_search_filter(q: str | None, *, is_postgres: bool):
    """Return a SQLAlchemy predicate for a free-text query, or None.

    Every token must match, so adding words narrows the result set the way a
    user expects. A token matches if it appears anywhere in the concatenated
    searchable text, or -- when it looks like a phone fragment -- anywhere in
    the digits-only phone blob, so `0505518569`, `505518569` and `971505518569`
    all find `+971505518569`.
    """
    tokens = tokenize(q or "")
    if not tokens:
        return None

    clauses = []
    for token in tokens:
        pattern = f"%{_escape_like(token)}%"

        if is_postgres:
            # search_text is generated lowercase, and the token is lowercased,
            # so LIKE suffices -- ILIKE would force a case-folding step the
            # gin_trgm_ops index cannot exploit as cleanly.
            token_clause = Record.search_text.like(pattern, escape="\\")
        else:
            token_clause = or_(*[c.ilike(pattern, escape="\\")
                                 for c in _FALLBACK_COLUMNS])

        for digits in _phone_variants(token):
            # Phone fragments are matched against the normalised digit blob so
            # formatting in the source data cannot hide a number from search.
            digit_pattern = f"%{digits}%"
            if is_postgres:
                token_clause = or_(
                    token_clause,
                    Record.mobile_digits.like(digit_pattern),
                )
            else:
                token_clause = or_(
                    token_clause,
                    *[c.ilike(digit_pattern) for c in
                      (Record.mobile_1, Record.mobile_2, Record.mobile_3)],
                )

        clauses.append(token_clause)

    return and_(*clauses) if len(clauses) > 1 else clauses[0]
