from fastapi import FastAPI

from landscape_api.routers import species, clients

app = FastAPI(title="Landscape Canopy API")
app.include_router(species.router)
app.include_router(clients.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
