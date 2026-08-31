# Core engine normalization correctness test suite
"""Regression tests for five defects found in the cleaning/enrichment audit.

Each test here failed before the fix and names the specific data corruption it
guards against. They are deliberately behavioural: the defects were all cases
where a unit-tested helper was correct in isolation but wired up wrongly, so
these exercise the path the ingest actually takes.
"""
from engine import cleaning as C
from engine import validation as V
from engine.mapping import ColumnPlan
from engine.reference import (
    _mentions, enrich, load_reference,
)

REFERENCE_JSON = "engine/resources/uae_developers.json"


# --- 1. sq.m -> sq.ft conversion driven by the column header ----------------
# clean_size() always handled `raw_header`, but transform() never passed it, so
# a column named "Area (Sqm)" holding a bare number was stored 10.76x too small.

def test_size_in_a_sqm_column_is_converted():
    row, _ = V.transform({"Size": 100}, {}, size_header="Area (Sqm)")
    assert row["size"] == 1076.39


def test_size_without_a_sqm_header_is_left_alone():
    row, _ = V.transform({"Size": 100}, {}, size_header="Area (Sq.Ft)")
    assert row["size"] == 100.0
    row, _ = V.transform({"Size": 100}, {})
    assert row["size"] == 100.0


def test_header_unit_applies_to_string_values_too():
    # Reading a file yields strings. The header check used to sit behind an
    # `elif isinstance(v, str)`, so it fired for almost nothing real.
    assert C.clean_size("100", raw_header="Total Size Sqm.") == 1076.39
    assert C.clean_size(100, raw_header="builtup_area_sqm") == 1076.39


def test_a_unit_stated_on_the_value_beats_the_header():
    # A cell that says square feet is square feet, whatever the column is called.
    assert C.clean_size("1,250.5 sq ft", raw_header="Total Size Sqm.") == 1250.5
    assert C.clean_size("100 sqm", raw_header="Size sq.ft") == 1076.39


def test_a_sqft_header_does_not_convert():
    assert C.clean_size("100", raw_header="Size sq.ft") == 100.0


def test_column_plan_reports_the_header_feeding_a_target():
    plan = ColumnPlan(index_to_target={0: "Name", 2: "Size"},
                      header=["OWNER NAME", "UNIT", "Area (Sqm)"])
    assert plan.header_for("Size") == "Area (Sqm)"
    assert plan.header_for("Nationality") is None


# --- 2. numbered districts are not collapsed into their base ----------------
# The trailing-digit strip ran before the canonical lookup, merging every
# numbered district into its unnumbered neighbour. community feeds
# identity_hash, so this silently merged distinct properties during dedup too.

def test_numbered_communities_keep_their_number():
    assert C.clean_community("DAMAC HILLS 2") == "DAMAC Hills 2"
    assert C.clean_community("damac hills 2") == "DAMAC Hills 2"
    assert C.clean_community("AL BARSHA 1") == "Al Barsha 1"
    assert C.clean_community("Al Barsha 3") == "Al Barsha 3"
    assert C.clean_community("AL QUOZ 4") == "Al Quoz 4"


def test_numbered_and_unnumbered_communities_stay_distinct():
    assert C.clean_community("DAMAC HILLS") != C.clean_community("DAMAC HILLS 2")
    assert C.clean_community("AL BARSHA 1") != C.clean_community("AL BARSHA 2")


def test_trailing_plot_numbers_are_still_stripped():
    # A large trailing integer is a plot id stuck onto the community name.
    assert C.clean_community("DAMAC HILLS 1044") == "DAMAC Hills"
    assert C.clean_community("AL BARSHA 12") == "Al Barsha"
    # ... including when it trails a genuinely numbered district.
    assert C.clean_community("damac hills 2 1044") == "DAMAC Hills 2"


# --- 3. developer canonicalisation ------------------------------------------
# The README advertised a "Developer Reference Resolver"; the transform ran
# clean_text, so every spelling of one builder stayed a separate facet value.

def test_developer_spellings_collapse_to_one_canonical_name():
    forms = ["EMAAR", "Emaar", "EMAAR PROPERTIES", "Emaar Properties PJSC",
             "EMAAR PROPERTIES L.L.C",
             "Emaar Properties (JV with Meraas/Dubai Holding)"]
    assert {C.clean_developer(f) for f in forms} == {"Emaar Properties"}


def test_developer_canonicalisation_runs_in_the_transform():
    row, _ = V.transform({"Developer": "EMAAR PROPERTIES PJSC"}, {})
    assert row["developer"] == "Emaar Properties"


def test_placeholder_developers_are_dropped():
    for junk in ("Multiple private developers", "Various", "Unknown", "N/A"):
        assert C.clean_developer(junk) is None


def test_unknown_developers_are_preserved_not_discarded():
    # The map cannot know every builder in the UAE; losing a real one is worse
    # than leaving it uncanonicalised.
    assert C.clean_developer("Sobha Realty") == "Sobha Realty"
    assert C.clean_developer("SOME UNKNOWN BUILDER LLC") == "Some Unknown Builder Llc"


def test_brand_match_does_not_fire_on_a_substring():
    assert C.clean_developer("Emcor Facilities") == "Emcor Facilities"


# --- 4. enrichment must not write categories into Property Type -------------
# match.dev_type holds development categories ("Master-planned community"),
# not dwelling types. Filling Property Type with it made records look complete
# while putting a taxonomy label where a Villa/Apartment value belongs.

def test_enrichment_never_fills_property_type():
    ref = load_reference(REFERENCE_JSON)
    fields = {"Community": "Dubai Hills Estate", "Sub-Community": None,
              "Project": None, "Building/Cluster": None}
    filled = enrich(fields, ref, source_name=None)
    assert fields.get("Property Type") is None
    assert "property_type" not in filled


# --- 5. the Dubai Hills developer fallback ----------------------------------
# It blanket-stamped Emaar on every project in the estate, including ones built
# by someone else, and matched on bare substrings.

def test_a_known_non_emaar_project_keeps_its_real_developer():
    ref = load_reference(REFERENCE_JSON)
    fields = {"Community": "Ellington House", "Sub-Community": None,
              "Project": None, "Building/Cluster": None}
    enrich(fields, ref, source_name=None)
    assert fields["Developer"] == "Ellington Properties"


def test_emaar_fallback_still_applies_to_emaar_subprojects():
    ref = load_reference(REFERENCE_JSON)
    for community in ("Sidra", "Club Villas"):
        fields = {"Community": community, "Sub-Community": None,
                  "Project": None, "Building/Cluster": None}
        enrich(fields, ref, source_name=None)
        assert fields["Developer"] == "Emaar Properties", community


def test_fallback_matches_whole_words_only():
    assert not _mentions("limestone tower", "lime gardens")
    assert _mentions("lime gardens dubai hills", "lime gardens")


def test_enrichment_never_overwrites_a_sourced_developer():
    ref = load_reference(REFERENCE_JSON)
    fields = {"Community": "Sidra", "Developer": "Ellington Properties",
              "Sub-Community": None, "Project": None, "Building/Cluster": None}
    filled = enrich(fields, ref, source_name=None)
    assert fields["Developer"] == "Ellington Properties"
    assert "developer" not in filled
