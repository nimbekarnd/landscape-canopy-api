import io

from landscape_api.routers.renders import get_orchestrator
from landscape_api.services.generation import GenerationOrchestrator
from landscape_api.services.image_edit_client import GenerationResult
from landscape_api.services.reference_images import CachingReferenceImageService
from landscape_api.main import app

from conftest import make_test_jpeg_bytes


class _FakeSucceedingClient:
    def generate(self, request):
        return GenerationResult(image_bytes=b"rendered-bytes")


class _NoOpProvider:
    def fetch(self, common_name, season):
        return None


def _make_project_and_zone(client):
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]
    photo = io.BytesIO(make_test_jpeg_bytes())
    project_resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", photo, "image/jpeg")},
    )
    project_id = project_resp.json()["id"]

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
    fake_orchestrator = GenerationOrchestrator(
        reference_service=CachingReferenceImageService(
            provider=_NoOpProvider(), cache_dir=tmp_path / "refs"
        ),
        image_edit_client=_FakeSucceedingClient(),
        renders_dir=tmp_path / "renders",
    )
    app.dependency_overrides[get_orchestrator] = lambda: fake_orchestrator

    project_id = _make_project_and_zone(client)

    resp = client.post(f"/projects/{project_id}/renders", json={"seasons": ["fall", "spring"]})

    assert resp.status_code == 201
    renders = resp.json()
    assert {r["season"] for r in renders} == {"fall", "spring"}
    assert all(r["status"] == "succeeded" for r in renders)

    list_resp = client.get(f"/projects/{project_id}/renders")
    assert len(list_resp.json()) == 2

    app.dependency_overrides.pop(get_orchestrator, None)
