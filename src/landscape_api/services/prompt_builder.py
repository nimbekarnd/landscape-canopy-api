from landscape_api.models import Season


def build_prompt(zones: list, season: Season, missing_species: list[str]) -> str:
    lines = [
        f"Render this landscape photo populated with the following plants for {season.value} season.",
        "Use the marked zones (white regions/circles in the provided mask) as planting locations.",
    ]

    for i, zone in enumerate(zones, start=1):
        entries_desc = ", ".join(
            f"{entry.species.common_name} ({entry.proportion:g}%)"
            for entry in zone.palette_entries
        )
        lines.append(f"Zone {i} ({zone.kind}): {entries_desc}")

    if missing_species:
        joined = ", ".join(missing_species)
        lines.append(
            f"No reference image was available for: {joined}. "
            "Render these from general species knowledge as accurately as possible."
        )

    return "\n".join(lines)
