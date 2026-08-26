from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from landscape_api.config import get_settings
from landscape_api.db import Base, configure_session, get_engine
from landscape_api.routers import species, clients, projects, zones, renders

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the real database on startup and release resources on shutdown."""
    settings = get_settings()
    engine = get_engine(settings.data_dir / "app.db")
    Base.metadata.create_all(engine)
    configure_session(engine)
    try:
        yield
    finally:
        renders.close_orchestrator()
        engine.dispose()


app = FastAPI(title="Landscape Canopy API", lifespan=lifespan)
app.include_router(species.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(zones.router)
app.include_router(renders.router)

# Mounted at /ui (not /) so it never shadows the API routes above — the
# harness's JS calls the API at absolute paths like /clients, which are
# unaffected by this mount.
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
