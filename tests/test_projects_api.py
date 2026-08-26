import io

from conftest import make_test_jpeg_bytes


def test_create_project_with_photo_upload(client):
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]

    photo = io.BytesIO(make_test_jpeg_bytes())
    resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", photo, "image/jpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["client_id"] == client_id
    assert body["status"] == "draft"

    get_resp = client.get(f"/projects/{body['id']}")
    assert get_resp.status_code == 200


def test_get_project_photo_returns_image_bytes(client):
    client_id = client.post("/clients", json={"name": "Agriformers Pilot"}).json()["id"]
    photo_bytes = make_test_jpeg_bytes()
    project_resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", io.BytesIO(photo_bytes), "image/jpeg")},
    )
    project_id = project_resp.json()["id"]

    resp = client.get(f"/projects/{project_id}/photo")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == photo_bytes


def test_get_project_photo_404_for_missing_project(client):
    resp = client.get("/projects/does-not-exist/photo")
    assert resp.status_code == 404


def test_create_project_with_non_image_upload_returns_422(client):
    """I5: uploading arbitrary bytes must be rejected, not written as a .jpg."""
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]

    not_an_image = io.BytesIO(b"this is definitely not a jpeg")
    resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", not_an_image, "image/jpeg")},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Uploaded file is not a valid image."
