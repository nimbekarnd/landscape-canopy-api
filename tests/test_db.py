from sqlalchemy import text
from landscape_api.db import get_engine, Base


def test_get_engine_creates_working_sqlite_connection(tmp_path):
    engine = get_engine(tmp_path / "test.db")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_get_engine_enforces_foreign_keys(tmp_path):
    """C3: SQLite FK enforcement must be on for every connection."""
    engine = get_engine(tmp_path / "fk.db")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_test_fixture_session_enforces_foreign_keys(db_session):
    """C3: the fixture engine gets the same PRAGMA as production."""
    assert db_session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_orphaned_palette_entry_is_rejected_by_the_database(db_session):
    """C3: an unknown species_id cannot reach the database undetected."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    from landscape_api.models import Client, PaletteEntry, Project, Zone

    client_row = Client(name="Agriformers")
    db_session.add(client_row)
    db_session.flush()
    project = Project(client_id=client_row.id, photo_path="/tmp/x.jpg")
    db_session.add(project)
    db_session.flush()
    zone = Zone(project_id=project.id, kind="region", geometry={"points": []})
    zone.palette_entries = [PaletteEntry(species_id="nope", proportion=100.0)]
    db_session.add(zone)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
