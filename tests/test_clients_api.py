import io

from conftest import make_test_jpeg_bytes


def test_create_and_fetch_client(client):
    create_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    assert create_resp.status_code == 201
    client_id = create_resp.json()["id"]

    get_resp = client.get(f"/clients/{client_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Agriformers Pilot"


def test_list_projects_for_client(client):
    client_id = client.post("/clients", json={"name": "Agriformers Pilot"}).json()["id"]

    photo = io.BytesIO(make_test_jpeg_bytes())
    project_resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", photo, "image/jpeg")},
    )
    project_id = project_resp.json()["id"]

    resp = client.get(f"/clients/{client_id}/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) == 1
    assert projects[0]["id"] == project_id


def test_list_projects_for_missing_client_returns_404(client):
    resp = client.get("/clients/does-not-exist/projects")
    assert resp.status_code == 404
