"""Enrichment must fill more, and never fill wrongly.

Coverage is worth nothing if the values are wrong: a wrong developer on a
record looks exactly like a right one to the sales desk, so every rule here is
biased toward leaving a field empty over guessing at it.
"""
from engine.reference import (
    MIN_DEVELOPER_CONFIDENCE, Development, ReferenceData, enrich,
    load_reference,
)

REFERENCE_JSON = "engine/resources/uae_developers.json"


def _fields(**kw):
    base = {"Community": None, "Sub-Community": None, "Project": None,
            "Building/Cluster": None, "Developer": None}
    base.update(kw)
    return base


def _enrich(fields, ref=None):
    flags: list[str] = []
    filled = enrich(fields, ref or load_reference(REFERENCE_JSON),
                    source_name=None, flags=flags)
    return filled, flags


# --- lookup precision -------------------------------------------------------

def test_a_generic_trailing_word_does_not_pick_a_developer():
    # "Lime Gardens" is Emaar in Dubai Hills. The reference holds an unrelated
    # development called "The Gardens" (Nakheel); matching on the bare token
    # "gardens" used to assign the wrong builder.
    fields = _fields(Community="Lime Gardens")
    _enrich(fields)
    assert fields["Developer"] == "Emaar Properties"


def test_the_most_specific_development_wins():
    ref = load_reference(REFERENCE_JSON)
    match = ref.lookup("dubai hills estate golf place")
    assert match is not None and match.name == "Dubai Hills Estate"


def test_an_unknown_place_enriches_nothing():
    fields = _fields(Community="Nonexistent Place 9000")
    filled, _ = _enrich(fields)
    assert fields["Developer"] is None
    assert "developer" not in filled


def test_lookup_results_are_cached_per_instance():
    ref = load_reference(REFERENCE_JSON)
    assert ref.lookup("Business Bay") is ref.lookup("Business Bay")


# --- confidence gating ------------------------------------------------------

def _ref_with(confidence):
    return ReferenceData([Development(
        name="Testville", emirate="Dubai", region="Testville Region",
        developer="Test Developer", dev_type="Master-planned community",
        confidence=confidence)])


def test_low_confidence_developers_are_withheld_and_recorded():
    fields = _fields(Community="Testville")
    filled, flags = _enrich(fields, _ref_with("Low"))
    assert fields["Developer"] is None
    assert "developer" not in filled
    # Recorded, so an empty Developer is distinguishable from missing source
    # data rather than looking like one.
    assert "enrichment_developer_withheld_low_confidence" in flags


def test_medium_confidence_developers_are_filled_but_flagged():
    fields = _fields(Community="Testville")
    filled, flags = _enrich(fields, _ref_with("Medium"))
    assert fields["Developer"] == "Test Developer"
    assert "developer" in filled
    assert "enriched_developer_medium_confidence" in flags


def test_high_confidence_developers_are_filled_without_a_caveat():
    fields = _fields(Community="Testville")
    _, flags = _enrich(fields, _ref_with("High"))
    assert not any("confidence" in f for f in flags)


def test_the_confidence_floor_is_medium():
    assert MIN_DEVELOPER_CONFIDENCE == "medium"


# --- what enrichment must never do ------------------------------------------

def test_sourced_values_are_never_overwritten():
    fields = _fields(Community="Sidra", Developer="Some Other Builder")
    filled, _ = _enrich(fields)
    assert fields["Developer"] == "Some Other Builder"
    assert "developer" not in filled


def test_community_is_filled_from_the_development_not_its_region():
    # region is the broader area; filling Community with it loses the precision
    # the sales desk filters on.
    ref = ReferenceData([Development(
        name="Testville", emirate="Dubai", region="Greater Test Area",
        developer=None, dev_type=None, confidence="High")])
    fields = _fields(Project="Testville")
    _enrich(fields, ref)
    assert fields["Community"] == "Testville"


def test_enrichment_is_recorded_on_every_filled_field():
    fields = _fields(Community="Sidra")
    filled, flags = _enrich(fields)
    assert "developer" in filled
    assert "enriched_developer_from_master_community" in flags
