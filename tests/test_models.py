from landscape_api.models import Client, Project, Zone, PaletteEntry, Species, Render, Season


def test_full_graph_persists_and_relates(db_session):
    client_row = Client(name="Agriformers Pilot Client")
    project = Project(client=client_row, photo_path="/tmp/yard.jpg")
    species = Species(common_name="Red Maple", scientific_name="Acer rubrum")
    zone = Zone(project=project, kind="region", geometry={"points": [[0, 0], [1, 1]]})
    entry = PaletteEntry(zone=zone, species=species, proportion=100.0)
    render = Render(project=project, season=Season.FALL, status="succeeded", image_path="/tmp/out.jpg")

    db_session.add_all([client_row, project, species, zone, entry, render])
    db_session.commit()

    fetched = db_session.query(Project).one()
    assert fetched.client.name == "Agriformers Pilot Client"
    assert fetched.zones[0].palette_entries[0].species.common_name == "Red Maple"
    assert fetched.renders[0].season == Season.FALL
