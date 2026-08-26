from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def enable_sqlite_foreign_keys(engine) -> None:
    """Enforce foreign keys on every new SQLite connection for this engine.

    SQLite ships with foreign-key enforcement disabled, so it must be turned on
    per-connection via PRAGMA. Engines that skip this silently accept orphaned
    rows (e.g. a palette entry pointing at a nonexistent species).
    """

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine(db_path: Path):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    enable_sqlite_foreign_keys(engine)
    return engine


SessionLocal: sessionmaker | None = None


def configure_session(engine) -> None:
    global SessionLocal
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    if SessionLocal is None:
        raise RuntimeError("Session not configured; call configure_session() first")
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
