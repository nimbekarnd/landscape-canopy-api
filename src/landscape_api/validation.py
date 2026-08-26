class ZoneValidationError(Exception):
    pass


def validate_palette_entries(entries: list[tuple[str, float]]) -> None:
    if not entries:
        raise ZoneValidationError("A zone requires at least one species.")
    total = sum(proportion for _, proportion in entries)
    if abs(total - 100.0) > 0.02:
        raise ZoneValidationError(
            f"Palette entry proportions must sum to 100 (got {total})."
        )
