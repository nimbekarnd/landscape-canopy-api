from pathlib import Path

from PIL import Image, ImageDraw

PIN_RADIUS = 15


def build_mask_overlay(photo_path: Path, zones: list, output_path: Path) -> Path:
    with Image.open(photo_path) as photo:
        width, height = photo.size

    mask = Image.new("RGB", (width, height), color="black")
    draw = ImageDraw.Draw(mask)

    for zone in zones:
        if zone.kind == "region":
            points = [tuple(p) for p in zone.geometry["points"]]
            draw.polygon(points, fill="white")
        elif zone.kind == "pin":
            x, y = zone.geometry["point"]
            draw.ellipse(
                [x - PIN_RADIUS, y - PIN_RADIUS, x + PIN_RADIUS, y + PIN_RADIUS],
                fill="white",
            )

    mask.save(output_path)
    return output_path
