import io


def _make_project(client):
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]
    photo = io.BytesIO(b"fake-jpeg-bytes")
    project_resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", photo, "image/jpeg")},
    )
    return project_resp.json()["id"]


def test_create_zone_with_valid_proportions(client):
    project_id = _make_project(client)
    species_resp = client.post("/species", json={"common_name": "Red Maple"})
    species_id = species_resp.json()["id"]

    resp = client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["palette_entries"][0]["proportion"] == 100.0


def test_create_zone_with_invalid_proportions_returns_422(client):
    project_id = _make_project(client)
    species_resp = client.post("/species", json={"common_name": "Red Maple"})
    species_id = species_resp.json()["id"]

    resp = client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [{"species_id": species_id, "proportion": 40.0}],
        },
    )
    assert resp.status_code == 422
    assert "sum to 100" in resp.json()["detail"]


def test_list_zones_for_project(client):
    project_id = _make_project(client)
    species_resp = client.post("/species", json={"common_name": "Red Maple"})
    species_id = species_resp.json()["id"]
    client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "pin",
            "geometry": {"point": [5, 5]},
            "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
        },
    )
    resp = client.get(f"/projects/{project_id}/zones")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
