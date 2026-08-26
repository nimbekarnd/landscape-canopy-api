from landscape_api.models import Season
from landscape_api.services.prompt_builder import build_prompt


class _FakeSpecies:
    def __init__(self, common_name):
        self.common_name = common_name


class _FakeEntry:
    def __init__(self, common_name, proportion):
        self.species = _FakeSpecies(common_name)
        self.proportion = proportion


class _FakeZone:
    def __init__(self, kind, palette_entries):
        self.kind = kind
        self.palette_entries = palette_entries


def test_prompt_includes_species_proportions_and_season():
    zones = [
        _FakeZone("region", [_FakeEntry("Red Maple", 60.0), _FakeEntry("Serviceberry", 40.0)]),
    ]
    prompt = build_prompt(zones, Season.FALL, missing_species=[])

    assert "fall" in prompt.lower()
    assert "Red Maple" in prompt
    assert "60%" in prompt
    assert "Serviceberry" in prompt
    assert "40%" in prompt


def test_prompt_notes_species_without_reference_images():
    zones = [_FakeZone("region", [_FakeEntry("Rare Shrub", 100.0)])]
    prompt = build_prompt(zones, Season.SPRING, missing_species=["Rare Shrub"])

    assert "Rare Shrub" in prompt
    assert "no reference image" in prompt.lower()
