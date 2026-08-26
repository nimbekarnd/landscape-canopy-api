def test_ui_index_page_is_served(client):
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Landscape Canopy" in resp.text


def test_ui_app_js_is_served(client):
    resp = client.get("/ui/app.js")
    assert resp.status_code == 200
    assert "generateRenders" in resp.text


def test_ui_mount_does_not_shadow_api_routes(client):
    resp = client.get("/clients")
    assert resp.status_code == 200
