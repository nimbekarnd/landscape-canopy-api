from PIL import Image

from landscape_api.services.mask_overlay import build_mask_overlay


class _FakeZone:
    def __init__(self, kind, geometry):
        self.kind = kind
        self.geometry = geometry


def test_build_mask_overlay_draws_region_and_pin(tmp_path):
    photo_path = tmp_path / "yard.jpg"
    Image.new("RGB", (100, 100), color="blue").save(photo_path)

    zones = [
        _FakeZone("region", {"points": [[10, 10], [50, 10], [50, 50], [10, 50]]}),
        _FakeZone("pin", {"point": [80, 80]}),
    ]
    output_path = tmp_path / "mask.png"

    result_path = build_mask_overlay(photo_path, zones, output_path)

    assert result_path == output_path
    mask = Image.open(output_path)
    assert mask.size == (100, 100)
    # A pixel inside the painted region should be white; a corner outside any zone should be black.
    assert mask.getpixel((30, 30))[:3] == (255, 255, 255)
    assert mask.getpixel((1, 1))[:3] == (0, 0, 0)
