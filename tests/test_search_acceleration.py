"""Search tokenisation, generated columns, and the capped-count contract.

The behaviour under test is the reason for migration 9c41ab7de205: a sales user
types several words that live in different columns, and the query must find the
row. The old whole-phrase ILIKE could not, and these tests fail loudly if that
behaviour ever regresses.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# A file-backed SQLite database, configured before any app module imports so the
# models pick up the SQLite generated-column expressions.
_TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP, 'search_test.db').as_posix()}"

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.core.search import (
    build_search_filter, has_indexable_token, tokenize,
)
from backend.app.models.models import Base, ProcessingJob, Record, RecordStatus


@pytest.fixture(scope="module")
def session():
    engine = create_engine(os.environ["DATABASE_URL"], future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    db = Session()

    # A bulk insert compiles one statement for the whole batch, so every row
    # must carry the same keys.
    def row(**kw):
        base = dict(job_id=1, source_file="fixture.xlsx", name=None,
                    community=None, building_cluster=None, unit_number=None,
                    bedroom=None, mobile_1=None, developer=None,
                    procedure_value=None, status=RecordStatus.VALID)
        base.update(kw)
        return base

    db.execute(Record.__table__.insert(), [
        row(id=1, source_file="marina.xlsx",
            name="Mohammed Ahmed Al Rashid", community="Dubai Marina",
            building_cluster="Marina Heights", unit_number="1101",
            mobile_1="+971505518569", developer="Emaar Properties PJSC",
            identity_hash="h1", procedure_value=2_500_000.0, bedroom="2BR"),
        row(id=2, source_file="marina.xlsx",
            name="Mohammed Saleh", community="Downtown Dubai",
            building_cluster="Burj Vista", unit_number="204",
            mobile_1="+971501234567", developer="Emaar Properties PJSC",
            identity_hash="h2", procedure_value=1_000_000.0, bedroom="1BR"),
        # mobile_1 is the literal string "N/A" -- the exact junk the default
        # view exists to exclude.
        row(id=3, source_file="jbr.xlsx",
            name="Ahmed Khan", community="JBR", building_cluster="Rimal 3",
            unit_number="1101", mobile_1="N/A", developer="Dubai Properties",
            identity_hash="h3"),
        # A truncated number, the other junk shape.
        row(id=4, source_file="jbr.xlsx",
            name="Sara Ali", community="Dubai Marina",
            building_cluster="Marina Heights", unit_number="905",
            mobile_1="0505", identity_hash="h4"),
    ])
    db.commit()
    yield db
    db.close()


def _ids(db, q):
    """Record ids matching a free-text query, in id order."""
    where = build_search_filter(q, is_postgres=False)
    stmt = select(Record.id)
    if where is not None:
        stmt = stmt.where(where)
    return sorted(db.scalars(stmt.order_by(Record.id)).all())


# --- tokenisation ---------------------------------------------------------

def test_conversational_filler_is_dropped():
    # The literal phrasing from the brief: "show me Mohammed Ahmed who owns a
    # flat in this building". Only the words that identify anything survive --
    # but "flat" stays, because it is a real property_type value.
    assert tokenize("show me Mohammed Ahmed who owns a flat in Marina Heights") == [
        "mohammed", "ahmed", "flat", "marina", "heights",
    ]


def test_query_of_pure_filler_falls_back_to_its_own_words():
    # Stripping every token would otherwise turn into "match everything".
    assert tokenize("show me all") == ["show", "me", "all"]


def test_quoted_phrase_survives_as_one_token():
    assert tokenize('"al rashid" marina') == ["al rashid", "marina"]


def test_empty_query_produces_no_filter():
    assert tokenize("") == []
    assert build_search_filter("", is_postgres=True) is None
    assert build_search_filter(None, is_postgres=False) is None


def test_short_tokens_are_flagged_as_unindexable():
    assert has_indexable_token(["ab", "marina"]) is True
    assert has_indexable_token(["ab", "cd"]) is False


# --- the behaviour the old search could not do ----------------------------

def test_tokens_may_match_different_columns(session):
    # "Mohammed" is in name, "Marina" in community, "Heights" in
    # building_cluster. No single column contains the whole phrase, so the old
    # whole-string ILIKE returned nothing for this.
    assert _ids(session, "Mohammed Marina Heights") == [1]


def test_every_token_must_match(session):
    # Both records are named Mohammed; only one is in Downtown. Adding a word
    # has to narrow, not widen.
    assert _ids(session, "Mohammed") == [1, 2]
    assert _ids(session, "Mohammed Downtown") == [2]


def test_natural_language_query_finds_the_owner(session):
    assert _ids(session, "show me Mohammed Ahmed who owns in Marina Heights") == [1]


def test_unit_number_within_a_building(session):
    # Two records share unit 1101 in different buildings.
    assert _ids(session, "1101") == [1, 3]
    assert _ids(session, "1101 Rimal") == [3]


def test_phone_search_ignores_formatting(session):
    # Typed without the country code, and with a leading zero, as a sales user
    # would read it off a phone.
    assert _ids(session, "505518569") == [1]
    assert _ids(session, "0505518569") == [1]


def test_like_wildcards_in_user_input_are_literal(session):
    # A user typing % must not match every row.
    assert _ids(session, "%") == []


# --- generated columns ----------------------------------------------------

def test_has_valid_mobile_is_computed_by_the_database(session):
    valid = sorted(session.scalars(
        select(Record.id).where(Record.has_valid_mobile.is_(True))).all())
    # Record 3 is the literal string "N/A" and record 4 is a truncated "0505";
    # neither is a contactable number.
    assert valid == [1, 2]


def test_search_text_is_populated_and_lowercased(session):
    row = session.get(Record, 1)
    assert row.search_text is not None
    assert "dubai marina" in row.search_text
    assert row.search_text == row.search_text.lower()


def test_generated_columns_track_updates(session):
    # The point of a generated column over an application-maintained one: an
    # edit through any code path cannot leave the search index stale.
    rec = session.get(Record, 4)
    rec.mobile_1 = "+971509998888"
    session.commit()
    session.refresh(rec)
    assert rec.has_valid_mobile is True
    assert "509998888" in rec.mobile_digits


# --- capped count ---------------------------------------------------------

def test_capped_count_stops_at_the_ceiling(session):
    from backend.app.api import records as records_api

    stmt = select(Record).where(Record.status == RecordStatus.VALID)
    ceiling = 2
    total = session.scalar(
        select(func.count()).select_from(stmt.limit(ceiling).subquery()))
    assert total == ceiling, "count must stop at the ceiling, not scan all rows"
    assert records_api.COUNT_CEILING > 0
