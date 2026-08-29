"""Property Type: normalise what exists, fill what doesn't, guess at nothing.

Property Type was present in ~40% of sampled source rows and, where present,
stated in registry vocabulary ("Unit", "Flat", "Land") rather than the market
vocabulary the sales desk filters on. These tests pin both halves of the fix:
the vocabulary normaliser, and the location-keyed property reference that fills
the rest without inventing anything.
"""
import pytest

from engine import cleaning as C
from engine.property_reference import (
    DOMINANCE, PropertyReference, load_property_reference,
)
from engine.reference import ReferenceData, enrich


# --- vocabulary normalisation ----------------------------------------------

def test_registry_vocabulary_becomes_market_vocabulary():
    # The five values actually observed in the Dubai Hills registers.
    assert C.clean_property_type("Unit") == "Apartment"
    assert C.clean_property_type("Flat") == "Apartment"
    assert C.clean_property_type("Land") == "Plot"
    assert C.clean_property_type("Building") == "Building"
    assert C.clean_property_type("Commercial") == "Commercial"


def test_one_kind_of_property_collapses_to_one_filter_value():
    for form in ("Flat", "FLAT", "Unit", "Apartment", "APT",
                 "Residential Flat", "Residential Flat - Freehold"):
        assert C.clean_property_type(form) == "Apartment", form


def test_a_longer_phrase_wins_over_the_word_inside_it():
    assert C.clean_property_type("Hotel Apartment") == "Hotel Apartment"
    assert C.clean_property_type("Town House") == "Townhouse"


def test_null_tokens_produce_nothing():
    for junk in ("n/a", "N/A", "-", "", None, "unknown"):
        assert C.clean_property_type(junk) is None


def test_an_unrecognised_type_is_kept_not_discarded():
    # The source may know something this map does not.
    assert C.clean_property_type("Bulk Sale Portfolio") == "Bulk Sale Portfolio"


def test_case_variants_do_not_become_separate_filter_entries():
    assert C.clean_property_type("VILLA") == C.clean_property_type("villa")


# --- the property reference -------------------------------------------------

def _rows(*specs):
    out = []
    for community, building, unit, ptype, beds, size in specs:
        out.append({"community": community, "building": building,
                    "unit_number": unit, "property_type": ptype,
                    "bedrooms": beds, "size": size})
    return out


@pytest.fixture
def reference():
    specs = [("Dubai Marina", "Marina Heights", "", "Apartment", 2, 900)] * 6
    specs += [("Dubai Marina", "Marina Heights", "1204", "Penthouse", 4, 2400)]
    specs += [("Dubai Hills Estate", "Club Villas", "", "Villa", 4, 4500)] * 5
    # A genuinely mixed tower: half offices, half apartments.
    specs += [("Business Bay", "Mixed Tower", "", "Office", 1, 800)] * 3
    specs += [("Business Bay", "Mixed Tower", "", "Apartment", 1, 800)] * 3
    return PropertyReference(_rows(*specs))


def test_an_exact_unit_match_is_authoritative(reference):
    facts = reference.lookup("Dubai Marina", "Marina Heights", "1204")
    assert (facts.property_type, facts.precision) == ("Penthouse", "unit")


def test_a_uniform_tower_answers_for_its_other_units(reference):
    facts = reference.lookup("Dubai Marina", "Marina Heights", "0808")
    assert (facts.property_type, facts.precision) == ("Apartment", "building")


def test_a_mixed_building_refuses_to_answer(reference):
    # 50/50 offices and apartments. Stamping either on the other half would be
    # the same failure as writing development categories into Property Type.
    assert reference.lookup("Business Bay", "Mixed Tower", "5") is None


def test_an_unknown_location_matches_nothing(reference):
    assert reference.lookup("Nowhere", "Nothing", "1") is None


def test_a_small_group_is_not_treated_as_dominant():
    share, count = DOMINANCE["building"]
    ref = PropertyReference(_rows(
        *[("Dubai Marina", "Tiny Tower", "", "Villa", 1, 100)] * (count - 1)))
    assert ref.lookup("Dubai Marina", "Tiny Tower", "9") is None


def test_community_precision_needs_a_far_stronger_majority():
    building_share, _ = DOMINANCE["building"]
    community_share, community_count = DOMINANCE["community"]
    assert community_share > building_share
    assert community_count > DOMINANCE["building"][1]


def test_reference_values_are_normalised_on_load():
    ref = PropertyReference(_rows(
        *[("DUBAI MARINA", "Marina Heights", "", "Flat", 2, 900)] * 4))
    facts = ref.lookup("Dubai Marina", "Marina Heights", "77")
    assert facts.property_type == "Apartment"


def test_a_missing_reference_file_is_not_an_error(tmp_path):
    ref = load_property_reference(tmp_path / "does_not_exist.csv")
    assert len(ref) == 0


def test_column_spellings_are_detected_across_export_formats(tmp_path):
    path = tmp_path / "portal_export.csv"
    path.write_text(
        "Master Project,Tower Name,Unit No,Property Type EN,Beds,Size Sqft\n"
        + "\n".join("Dubai Marina,Marina Heights,,Apartment,2,900"
                    for _ in range(4)),
        encoding="utf-8")
    ref = load_property_reference(path)
    facts = ref.lookup("Dubai Marina", "Marina Heights", "101")
    assert facts is not None and facts.property_type == "Apartment"


# --- enrichment behaviour ---------------------------------------------------

def _enrich(fields, properties):
    flags: list[str] = []
    filled = enrich(fields, ReferenceData([]), source_name=None,
                    flags=flags, properties=properties)
    return filled, flags


def _fields(**kw):
    base = {"Community": None, "Sub-Community": None, "Project": None,
            "Building/Cluster": None, "Unit Number": None,
            "Property Type": None, "Bedroom": None, "Size": None}
    base.update(kw)
    return base


def test_enrichment_fills_property_type_and_records_its_precision(reference):
    fields = _fields(Community="Dubai Marina", **{"Building/Cluster": "Marina Heights"},
                     **{"Unit Number": "0808"})
    filled, flags = _enrich(fields, reference)
    assert fields["Property Type"] == "Apartment"
    assert "property_type" in filled
    assert "enriched_property_type_at_building_precision" in flags


def test_bedroom_and_size_come_only_from_an_exact_unit(reference):
    # A tower-level match says nothing about one apartment's bedroom count.
    fields = _fields(Community="Dubai Marina", **{"Building/Cluster": "Marina Heights"},
                     **{"Unit Number": "0808"})
    _enrich(fields, reference)
    assert fields["Bedroom"] is None and fields["Size"] is None

    exact = _fields(Community="Dubai Marina", **{"Building/Cluster": "Marina Heights"},
                    **{"Unit Number": "1204"})
    _enrich(exact, reference)
    assert exact["Bedroom"] == "4 BR"
    assert exact["Size"] == 2400.0


def test_a_sourced_property_type_is_never_replaced(reference):
    fields = _fields(Community="Dubai Marina", **{"Building/Cluster": "Marina Heights"},
                     **{"Unit Number": "1204"}, **{"Property Type": "Flat"})
    filled, _ = _enrich(fields, reference)
    assert fields["Property Type"] == "Flat"     # normalised later, in transform
    assert "property_type" not in filled


def test_enrichment_without_a_property_reference_changes_nothing():
    fields = _fields(Community="Dubai Marina", **{"Building/Cluster": "Marina Heights"})
    filled, _ = _enrich(fields, None)
    assert fields["Property Type"] is None
    assert "property_type" not in filled


# --- portal export adapter (Property Finder shape) --------------------------

def test_portal_location_string_is_split_correctly():
    from engine.property_reference import _parse_location
    # community is the segment before the city; building is the first.
    assert _parse_location(
        "Skycourts Tower F, Skycourts Towers, Dubai Land Residence Complex, Dubai"
    ) == ("Dubai Land Residence Complex", "Skycourts Tower F", "Skycourts Towers")
    assert _parse_location("The Diamond, Dubai Sports City, Dubai") == (
        "Dubai Sports City", "The Diamond", "")


def test_a_location_without_a_city_still_parses():
    from engine.property_reference import _parse_location
    assert _parse_location("Marina Heights, Dubai Marina") == (
        "Dubai Marina", "Marina Heights", "")
    assert _parse_location("") == ("", "", "")


def test_portal_and_register_building_names_reduce_to_one_key():
    from engine.property_reference import _building_key
    # The naming gap that stopped building-level matches from firing.
    assert _building_key("Maple at Dubai Hills Estate") == _building_key("Maple")
    assert _building_key("Sidra Villas") == _building_key("Sidra")
    assert _building_key("Shoreline Apartments") == _building_key("Shoreline")


def test_building_key_only_strips_descriptors_from_the_end():
    from engine.property_reference import _building_key
    assert _building_key("Villa Lantana") == "villa lantana"


def test_a_development_name_matches_without_a_community():
    # Owner registers carry no Community on ~76% of rows; the development name
    # alone has to be enough or almost nothing matches.
    ref = PropertyReference(_rows(
        *[("Dubai Hills Estate", "Sidra Villas", "", "Villa", 4, 4500)] * 5))
    facts = ref.lookup(None, "Sidra", "12")
    assert facts is not None and facts.property_type == "Villa"


def test_a_register_community_is_also_tried_as_a_development_name():
    # A register's "Community" is as often a sub-development ("Club Villas") as
    # a master community.
    ref = PropertyReference(_rows(
        *[("Dubai Hills Estate", "Club Villas", "", "Villa", 4, 4500)] * 5))
    facts = ref.lookup("Club Villas", None, "12")
    assert facts is not None and facts.property_type == "Villa"
