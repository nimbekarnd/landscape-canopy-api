from sqlalchemy import text
from landscape_api.db import get_engine, Base


def test_get_engine_creates_working_sqlite_connection(tmp_path):
    engine = get_engine(tmp_path / "test.db")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
    assert result == 1
