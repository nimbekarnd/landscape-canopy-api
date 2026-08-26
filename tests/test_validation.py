import pytest
from landscape_api.validation import validate_palette_entries, ZoneValidationError


def test_valid_proportions_pass():
    validate_palette_entries([("sp1", 60.0), ("sp2", 40.0)])  # should not raise


def test_empty_entries_raises():
    with pytest.raises(ZoneValidationError, match="at least one species"):
        validate_palette_entries([])


def test_proportions_not_summing_to_100_raises():
    with pytest.raises(ZoneValidationError, match="sum to 100"):
        validate_palette_entries([("sp1", 60.0), ("sp2", 30.0)])


def test_proportions_within_tolerance_pass():
    validate_palette_entries([("sp1", 33.34), ("sp2", 33.33), ("sp3", 33.33)])
