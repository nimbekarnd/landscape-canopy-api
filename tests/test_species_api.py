def test_create_and_fetch_species(client):
    create_resp = client.post("/species", json={"common_name": "Red Maple", "scientific_name": "Acer rubrum"})
    assert create_resp.status_code == 201
    species_id = create_resp.json()["id"]

    get_resp = client.get(f"/species/{species_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["common_name"] == "Red Maple"


def test_list_species(client):
    client.post("/species", json={"common_name": "Serviceberry"})
    resp = client.get("/species")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
