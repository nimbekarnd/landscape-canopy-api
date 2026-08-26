import io


def test_create_project_with_photo_upload(client):
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]

    fake_photo = io.BytesIO(b"fake-jpeg-bytes")
    resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", fake_photo, "image/jpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["client_id"] == client_id
    assert body["status"] == "draft"

    get_resp = client.get(f"/projects/{body['id']}")
    assert get_resp.status_code == 200
