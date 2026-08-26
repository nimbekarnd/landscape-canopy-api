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
