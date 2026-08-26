import io

from conftest import make_test_jpeg_bytes


def _make_project(client):
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]
    photo = io.BytesIO(make_test_jpeg_bytes())
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


def test_create_zone_with_unknown_species_id_returns_422(client):
    """C3: an orphaned palette entry must be rejected up front, not persisted."""
    project_id = _make_project(client)

    resp = client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [
                {"species_id": "does-not-exist", "proportion": 100.0}
            ],
        },
    )
    assert resp.status_code == 422
    assert "does-not-exist" in resp.json()["detail"]

    # And nothing was written.
    assert client.get(f"/projects/{project_id}/zones").json() == []


def test_create_zone_with_invalid_kind_returns_422(client):
    """I5: kind is constrained to the values build_mask_overlay understands."""
    project_id = _make_project(client)
    species_id = client.post("/species", json={"common_name": "Red Maple"}).json()["id"]

    resp = client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "blob",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
        },
    )
    assert resp.status_code == 422


def test_update_zone_replaces_geometry_kind_and_palette(client):
    project_id = _make_project(client)
    maple_id = client.post("/species", json={"common_name": "Red Maple"}).json()["id"]
    oak_id = client.post("/species", json={"common_name": "White Oak"}).json()["id"]

    zone_id = client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [{"species_id": maple_id, "proportion": 100.0}],
        },
    ).json()["id"]

    resp = client.patch(
        f"/projects/{project_id}/zones/{zone_id}",
        json={
            "kind": "pin",
            "geometry": {"point": [5, 5]},
            "palette_entries": [
                {"species_id": maple_id, "proportion": 40.0},
                {"species_id": oak_id, "proportion": 60.0},
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "pin"
    assert body["geometry"] == {"point": [5, 5]}
    assert {(e["species_id"], e["proportion"]) for e in body["palette_entries"]} == {
        (maple_id, 40.0),
        (oak_id, 60.0),
    }

    # And the replacement is what a subsequent fetch sees too.
    listed = client.get(f"/projects/{project_id}/zones").json()
    assert len(listed) == 1
    assert len(listed[0]["palette_entries"]) == 2


def test_update_zone_with_invalid_proportions_returns_422(client):
    project_id = _make_project(client)
    species_id = client.post("/species", json={"common_name": "Red Maple"}).json()["id"]
    zone_id = client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
        },
    ).json()["id"]

    resp = client.patch(
        f"/projects/{project_id}/zones/{zone_id}",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [{"species_id": species_id, "proportion": 40.0}],
        },
    )
    assert resp.status_code == 422
    assert "sum to 100" in resp.json()["detail"]


def test_update_zone_returns_404_for_missing_zone(client):
    project_id = _make_project(client)
    resp = client.patch(
        f"/projects/{project_id}/zones/does-not-exist",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [],
        },
    )
    assert resp.status_code == 404


def test_delete_zone_removes_it(client):
    project_id = _make_project(client)
    species_id = client.post("/species", json={"common_name": "Red Maple"}).json()["id"]
    zone_id = client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
        },
    ).json()["id"]

    resp = client.delete(f"/projects/{project_id}/zones/{zone_id}")
    assert resp.status_code == 204

    assert client.get(f"/projects/{project_id}/zones").json() == []


def test_delete_zone_returns_404_for_missing_zone(client):
    project_id = _make_project(client)
    resp = client.delete(f"/projects/{project_id}/zones/does-not-exist")
    assert resp.status_code == 404
