def test_create_and_fetch_client(client):
    create_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    assert create_resp.status_code == 201
    client_id = create_resp.json()["id"]

    get_resp = client.get(f"/clients/{client_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Agriformers Pilot"
