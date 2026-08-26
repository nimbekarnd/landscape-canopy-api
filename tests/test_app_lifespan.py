"""C1: the app must initialize its own database, not rely on test fixtures."""

import io

from fastapi.testclient import TestClient

from landscape_api.main import app

from conftest import make_test_jpeg_bytes


def test_lifespan_creates_db_and_serves_db_backed_endpoints(tmp_path, monkeypatch):
    data_dir = tmp_path / "real-data"
    monkeypatch.setenv("LANDSCAPE_DATA_DIR", str(data_dir))

    # Deliberately no get_db override: this exercises the real engine/session
    # wiring set up by the lifespan handler.
    assert not app.dependency_overrides

    with TestClient(app) as real_client:
        client_resp = real_client.post("/clients", json={"name": "Lifespan Client"})
        assert client_resp.status_code == 201
        client_id = client_resp.json()["id"]

        photo = io.BytesIO(make_test_jpeg_bytes())
        project_resp = real_client.post(
            f"/clients/{client_id}/projects",
            files={"photo": ("yard.jpg", photo, "image/jpeg")},
        )
        assert project_resp.status_code == 201
        project_id = project_resp.json()["id"]

        species_resp = real_client.post("/species", json={"common_name": "Red Maple"})
        assert species_resp.status_code == 201
        species_id = species_resp.json()["id"]

        zone_resp = real_client.post(
            f"/projects/{project_id}/zones",
            json={
                "kind": "region",
                "geometry": {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
                "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
            },
        )
        assert zone_resp.status_code == 201

        assert real_client.get(f"/projects/{project_id}/zones").status_code == 200

    assert (data_dir / "app.db").exists()


def test_lifespan_enforces_foreign_keys_on_the_real_engine(tmp_path, monkeypatch):
    """C3: FK enforcement is on for the production engine too."""
    monkeypatch.setenv("LANDSCAPE_DATA_DIR", str(tmp_path / "real-data"))

    from sqlalchemy import text

    from landscape_api.db import get_engine

    engine = get_engine(tmp_path / "fk.db")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
    engine.dispose()
