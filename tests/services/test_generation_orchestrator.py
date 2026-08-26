from pathlib import Path

from PIL import Image

from landscape_api.models import Season
from landscape_api.services.generation import GenerationOrchestrator
from landscape_api.services.image_edit_client import GenerationResult, ImageEditError


class _FakeSpecies:
    def __init__(self, common_name):
        self.common_name = common_name


class _FakeEntry:
    def __init__(self, common_name, proportion):
        self.species = _FakeSpecies(common_name)
        self.proportion = proportion


class _FakeZone:
    def __init__(self, kind, geometry, palette_entries):
        self.kind = kind
        self.geometry = geometry
        self.palette_entries = palette_entries


class _FakeProject:
    def __init__(self, photo_path):
        self.photo_path = photo_path


class _FakeReferenceService:
    def __init__(self, has_image: bool):
        self._has_image = has_image

    def get_reference_image(self, common_name, season):
        return Path("fake-ref.jpg") if self._has_image else None


class _AlwaysSucceedsClient:
    def generate(self, request):
        return GenerationResult(image_bytes=b"rendered-bytes")


class _AlwaysFailsClient:
    def __init__(self):
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        raise ImageEditError("boom")


class _FailsOnceThenSucceedsClient:
    def __init__(self):
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        if self.calls == 1:
            raise ImageEditError("transient failure")
        return GenerationResult(image_bytes=b"rendered-bytes")


def _make_project_photo(tmp_path):
    photo_path = tmp_path / "yard.jpg"
    Image.new("RGB", (50, 50), color="green").save(photo_path)
    return photo_path


def test_successful_generation_returns_succeeded_outcome(tmp_path):
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [_FakeZone("region", {"points": [[0, 0], [10, 0], [10, 10]]}, [_FakeEntry("Red Maple", 100.0)])]

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=_AlwaysSucceedsClient(),
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.FALL)

    assert outcome.status == "succeeded"
    assert outcome.image_path.exists()
    assert outcome.missing_species == []


def test_missing_reference_image_flags_species_but_still_succeeds(tmp_path):
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [_FakeZone("region", {"points": [[0, 0], [10, 0], [10, 10]]}, [_FakeEntry("Rare Shrub", 100.0)])]

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=False),
        image_edit_client=_AlwaysSucceedsClient(),
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.SPRING)

    assert outcome.status == "succeeded"
    assert outcome.missing_species == ["Rare Shrub"]


def test_retries_once_then_succeeds(tmp_path):
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [_FakeZone("region", {"points": [[0, 0], [10, 0], [10, 10]]}, [_FakeEntry("Red Maple", 100.0)])]
    flaky_client = _FailsOnceThenSucceedsClient()

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=flaky_client,
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.WINTER)

    assert outcome.status == "succeeded"
    assert flaky_client.calls == 2


def test_fails_after_retry_exhausted(tmp_path):
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [_FakeZone("region", {"points": [[0, 0], [10, 0], [10, 10]]}, [_FakeEntry("Red Maple", 100.0)])]
    failing_client = _AlwaysFailsClient()

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=failing_client,
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.SUMMER)

    assert outcome.status == "failed"
    assert outcome.image_path is None
    assert failing_client.calls == 2
    assert "boom" in outcome.error


class _RaisesUnexpectedErrorClient:
    """Raises something that is NOT an ImageEditError."""

    def __init__(self):
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        raise ValueError("unexpected non-ImageEditError blow-up")


def test_unreadable_photo_returns_failed_outcome_instead_of_raising(tmp_path):
    """C2: build_mask_overlay raising must degrade to a failed outcome."""
    photo_path = tmp_path / "corrupt.jpg"
    photo_path.write_bytes(b"not-actually-an-image")
    project = _FakeProject(photo_path=str(photo_path))
    zones = [
        _FakeZone(
            "region",
            {"points": [[0, 0], [10, 0], [10, 10]]},
            [_FakeEntry("Red Maple", 100.0)],
        )
    ]

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=_AlwaysSucceedsClient(),
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.FALL)

    assert outcome.status == "failed"
    assert outcome.image_path is None
    assert outcome.error


def test_missing_photo_file_returns_failed_outcome(tmp_path):
    """C2: a FileNotFoundError from the photo path must not propagate."""
    project = _FakeProject(photo_path=str(tmp_path / "nope.jpg"))
    zones = [
        _FakeZone(
            "region",
            {"points": [[0, 0], [10, 0], [10, 10]]},
            [_FakeEntry("Red Maple", 100.0)],
        )
    ]

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=_AlwaysSucceedsClient(),
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.SPRING)

    assert outcome.status == "failed"
    assert outcome.image_path is None


def test_malformed_zone_geometry_returns_failed_outcome(tmp_path):
    """C2: a KeyError from bad geometry must not propagate."""
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [_FakeZone("region", {"wrong_key": []}, [_FakeEntry("Red Maple", 100.0)])]

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=_AlwaysSucceedsClient(),
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.WINTER)

    assert outcome.status == "failed"
    assert outcome.missing_species == []


def test_non_image_edit_error_from_client_returns_failed_outcome(tmp_path):
    """C2: only ImageEditError is retried; other client errors still fail cleanly."""
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [
        _FakeZone(
            "region",
            {"points": [[0, 0], [10, 0], [10, 10]]},
            [_FakeEntry("Red Maple", 100.0)],
        )
    ]
    failing_client = _RaisesUnexpectedErrorClient()

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=failing_client,
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.SUMMER)

    assert outcome.status == "failed"
    assert failing_client.calls == 1  # not retried
    assert "unexpected non-ImageEditError" in outcome.error


def test_close_closes_underlying_client(tmp_path):
    """I2: the orchestrator can release its client's resources."""

    class _ClosableClient:
        def __init__(self):
            self.closed = False

        def generate(self, request):  # pragma: no cover - not exercised here
            raise AssertionError("not called")

        def close(self):
            self.closed = True

    closable = _ClosableClient()
    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=closable,
        renders_dir=tmp_path / "renders",
    )

    orchestrator.close()

    assert closable.closed is True
