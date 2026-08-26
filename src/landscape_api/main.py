from contextlib import asynccontextmanager

from fastapi import FastAPI

from landscape_api.config import get_settings
from landscape_api.db import Base, configure_session, get_engine
from landscape_api.routers import species, clients, projects, zones, renders


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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
