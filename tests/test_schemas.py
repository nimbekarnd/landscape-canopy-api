from landscape_api.schemas import ZoneIn, PaletteEntryIn


def test_zone_in_accepts_nested_palette_entries():
    zone = ZoneIn(
        kind="region",
        geometry={"points": [[0, 0], [1, 1]]},
        palette_entries=[PaletteEntryIn(species_id="sp1", proportion=100.0)],
    )
    assert zone.palette_entries[0].proportion == 100.0
