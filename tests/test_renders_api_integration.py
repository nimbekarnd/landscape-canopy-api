import io
from pathlib import Path

import pytest

from landscape_api.routers.renders import close_orchestrator, get_orchestrator
from landscape_api.services.generation import GenerationOrchestrator, RenderOutcome
from landscape_api.services.image_edit_client import GenerationResult
from landscape_api.services.reference_images import CachingReferenceImageService
from landscape_api.main import app

from conftest import make_test_jpeg_bytes


class _FakeSucceedingClient:
    def generate(self, request):
        return GenerationResult(image_bytes=b"rendered-bytes")


class _ExplodesForSeasonClient:
    """Raises a non-ImageEditError for one season, succeeds for the others."""

    def __init__(self, season_value: str):
        self._season_value = season_value

    def generate(self, request):
        if f"{self._season_value} season" in request.prompt:
            raise ValueError(f"catastrophe during {self._season_value}")
        return GenerationResult(image_bytes=b"rendered-bytes")


class _NoOpProvider:
    def fetch(self, common_name, season):
        return None


def _make_real_orchestrator(tmp_path, image_edit_client=None):
    return GenerationOrchestrator(
        reference_service=CachingReferenceImageService(
            provider=_NoOpProvider(), cache_dir=tmp_path / "refs"
        ),
        image_edit_client=image_edit_client or _FakeSucceedingClient(),
        renders_dir=tmp_path / "renders",
    )


def _make_project(client):
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]
    photo = io.BytesIO(make_test_jpeg_bytes())
    project_resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", photo, "image/jpeg")},
    )
    return project_resp.json()["id"]


def _make_project_and_zone(client):
    project_id = _make_project(client)

    species_resp = client.post("/species", json={"common_name": "Red Maple"})
    species_id = species_resp.json()["id"]

    client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
        },
    )
    return project_id


def test_generate_renders_for_requested_seasons(client, tmp_path):
    app.dependency_overrides[get_orchestrator] = lambda: _make_real_orchestrator(tmp_path)

    project_id = _make_project_and_zone(client)

    resp = client.post(f"/projects/{project_id}/renders", json={"seasons": ["fall", "spring"]})

    assert resp.status_code == 201
    renders = resp.json()
    assert {r["season"] for r in renders} == {"fall", "spring"}
    assert all(r["status"] == "succeeded" for r in renders)

    list_resp = client.get(f"/projects/{project_id}/renders")
    assert len(list_resp.json()) == 2

    app.dependency_overrides.pop(get_orchestrator, None)


def test_generate_renders_on_project_without_zones_returns_422(client, tmp_path):
    """I3: generation must be blocked with a validation message, not run empty."""
    app.dependency_overrides[get_orchestrator] = lambda: _make_real_orchestrator(tmp_path)

    project_id = _make_project(client)

    resp = client.post(f"/projects/{project_id}/renders", json={"seasons": ["fall"]})

    assert resp.status_code == 422
    assert "no zones" in resp.json()["detail"]
    assert client.get(f"/projects/{project_id}/renders").json() == []

    app.dependency_overrides.pop(get_orchestrator, None)


def test_render_response_includes_real_zone_snapshot(client, tmp_path):
    """I4: the snapshot must capture zone + palette detail, not just a count."""
    app.dependency_overrides[get_orchestrator] = lambda: _make_real_orchestrator(tmp_path)

    project_id = _make_project_and_zone(client)

    resp = client.post(f"/projects/{project_id}/renders", json={"seasons": ["fall"]})
    assert resp.status_code == 201

    snapshot = resp.json()[0]["zone_snapshot"]
    assert "zone_count" not in snapshot
    assert len(snapshot["zones"]) == 1
    zone = snapshot["zones"][0]
    assert zone["kind"] == "region"
    assert zone["geometry"] == {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]}
    assert zone["palette_entries"] == [
        {
            "species_id": zone["palette_entries"][0]["species_id"],
            "species_name": "Red Maple",
            "proportion": 100.0,
        }
    ]

    # And it survives a round-trip through the listing endpoint.
    listed = client.get(f"/projects/{project_id}/renders").json()[0]
    assert listed["zone_snapshot"] == snapshot

    app.dependency_overrides.pop(get_orchestrator, None)


def test_unreadable_photo_yields_failed_render_rows_not_500(client, tmp_path):
    """C2: a corrupt photo must produce failed rows with a 201, not a 500."""
    app.dependency_overrides[get_orchestrator] = lambda: _make_real_orchestrator(tmp_path)

    project_id = _make_project_and_zone(client)
    photo_path = Path(client.get(f"/projects/{project_id}").json()["photo_path"])
    photo_path.write_bytes(b"corrupted-not-an-image")

    resp = client.post(
        f"/projects/{project_id}/renders", json={"seasons": ["spring", "fall"]}
    )

    assert resp.status_code == 201
    renders = resp.json()
    assert len(renders) == 2
    assert all(r["status"] == "failed" for r in renders)
    assert all(r["image_path"] is None for r in renders)
    assert all(r["error"] for r in renders)
    assert len(client.get(f"/projects/{project_id}/renders").json()) == 2

    app.dependency_overrides.pop(get_orchestrator, None)


def test_mixed_success_and_failure_across_seasons(client, tmp_path):
    """C2: one season blowing up must not lose the other seasons' results."""
    app.dependency_overrides[get_orchestrator] = lambda: _make_real_orchestrator(
        tmp_path, image_edit_client=_ExplodesForSeasonClient("summer")
    )

    project_id = _make_project_and_zone(client)

    resp = client.post(
        f"/projects/{project_id}/renders",
        json={"seasons": ["spring", "summer", "fall"]},
    )

    assert resp.status_code == 201
    by_season = {r["season"]: r for r in resp.json()}
    assert by_season["spring"]["status"] == "succeeded"
    assert by_season["fall"]["status"] == "succeeded"
    assert by_season["summer"]["status"] == "failed"
    assert "catastrophe during summer" in by_season["summer"]["error"]

    app.dependency_overrides.pop(get_orchestrator, None)


def test_each_season_is_committed_independently(client, tmp_path):
    """C2: an exception escaping the orchestrator cannot discard earlier seasons."""

    class _ExplodingOrchestrator:
        def generate_for_season(self, project, zones, season):
            if season.value == "summer":
                raise RuntimeError("orchestrator itself blew up")
            return RenderOutcome(
                status="succeeded",
                image_path=tmp_path / "fake-render.jpg",
                error=None,
                missing_species=[],
            )

    app.dependency_overrides[get_orchestrator] = lambda: _ExplodingOrchestrator()

    project_id = _make_project_and_zone(client)

    with pytest.raises(RuntimeError):
        client.post(
            f"/projects/{project_id}/renders",
            json={"seasons": ["spring", "summer", "fall"]},
        )

    # Spring was committed before summer failed, so it must still exist.
    persisted = client.get(f"/projects/{project_id}/renders").json()
    assert [r["season"] for r in persisted] == ["spring"]

    app.dependency_overrides.pop(get_orchestrator, None)


def test_get_render_image_returns_bytes_for_succeeded_render(client, tmp_path):
    app.dependency_overrides[get_orchestrator] = lambda: _make_real_orchestrator(tmp_path)

    project_id = _make_project_and_zone(client)
    resp = client.post(f"/projects/{project_id}/renders", json={"seasons": ["fall"]})
    render_id = resp.json()[0]["id"]

    image_resp = client.get(f"/renders/{render_id}/image")
    assert image_resp.status_code == 200
    assert image_resp.headers["content-type"] == "image/jpeg"
    assert image_resp.content == b"rendered-bytes"

    app.dependency_overrides.pop(get_orchestrator, None)


def test_get_render_image_404_for_failed_render(client, tmp_path):
    app.dependency_overrides[get_orchestrator] = lambda: _make_real_orchestrator(tmp_path)

    project_id = _make_project_and_zone(client)
    photo_path = Path(client.get(f"/projects/{project_id}").json()["photo_path"])
    photo_path.write_bytes(b"corrupted-not-an-image")

    resp = client.post(f"/projects/{project_id}/renders", json={"seasons": ["fall"]})
    render_id = resp.json()[0]["id"]
    assert resp.json()[0]["status"] == "failed"

    image_resp = client.get(f"/renders/{render_id}/image")
    assert image_resp.status_code == 404

    app.dependency_overrides.pop(get_orchestrator, None)


def test_get_render_image_404_for_missing_render(client):
    resp = client.get("/renders/does-not-exist/image")
    assert resp.status_code == 404


def test_get_orchestrator_is_cached_per_process():
    """I2: a new httpx.Client must not be built per render request."""
    close_orchestrator()  # start from a clean cache
    try:
        first = get_orchestrator()
        second = get_orchestrator()
        assert first is second
    finally:
        close_orchestrator()

    assert get_orchestrator.cache_info().currsize == 0
