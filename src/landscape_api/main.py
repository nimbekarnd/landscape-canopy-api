from fastapi import FastAPI

app = FastAPI(title="Landscape Canopy API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
