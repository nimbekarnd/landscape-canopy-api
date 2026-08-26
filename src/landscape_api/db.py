from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def get_engine(db_path: Path):
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


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
