import os
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from landscape_api.config import get_settings
from landscape_api.db import get_db
from landscape_api.models import Project, Render, Season
from landscape_api.schemas import RenderOut
from landscape_api.services.generation import GenerationOrchestrator
from landscape_api.services.image_edit_client import GeminiImageEditClient
from landscape_api.services.reference_images import CachingReferenceImageService

router = APIRouter(tags=["renders"])


class NullReferenceProvider:
    """Used when no reference-image provider is configured; every lookup misses."""

    def fetch(self, common_name: str, season: Season) -> bytes | None:
        return None


@lru_cache(maxsize=1)
def get_orchestrator() -> GenerationOrchestrator:
    """Build the orchestrator once per process.

    Cached because each construction creates an ``httpx.Client``; without the
    cache every render request leaked a connection pool.
    """
    settings = get_settings()
    reference_service = CachingReferenceImageService(
        provider=NullReferenceProvider(),
        cache_dir=settings.reference_cache_dir(),
    )
    image_edit_client = GeminiImageEditClient(
        api_key=os.environ.get("IMAGE_EDIT_API_KEY", ""),
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-image"),
    )
    return GenerationOrchestrator(
        reference_service=reference_service,
        image_edit_client=image_edit_client,
        renders_dir=settings.renders_dir(),
    )


def close_orchestrator() -> None:
    """Release the cached orchestrator's HTTP resources (called on app shutdown)."""
    if get_orchestrator.cache_info().currsize:
        get_orchestrator().close()
    get_orchestrator.cache_clear()


def _build_zone_snapshot(zones: list) -> dict:
    """Capture the zone/palette configuration a render was produced from."""
    return {
        "zones": [
            {
                "id": zone.id,
                "kind": zone.kind,
                "geometry": zone.geometry,
                "palette_entries": [
                    {
                        "species_id": entry.species_id,
                        "species_name": entry.species.common_name,
                        "proportion": entry.proportion,
                    }
                    for entry in zone.palette_entries
                ],
            }
            for zone in zones
        ]
    }


class GenerateRendersIn(BaseModel):
    seasons: list[Season] = list(Season)


@router.post("/projects/{project_id}/renders", response_model=list[RenderOut], status_code=201)
def generate_renders(
    project_id: str,
    payload: GenerateRendersIn,
    db: Session = Depends(get_db),
    orchestrator: GenerationOrchestrator = Depends(get_orchestrator),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    zones = project.zones
    if not zones:
        raise HTTPException(
            status_code=422,
            detail="Project has no zones; add at least one zone before generating renders.",
        )

    zone_snapshot = _build_zone_snapshot(zones)

    results = []
    for season in payload.seasons:
        outcome = orchestrator.generate_for_season(project, zones, season)
        render = Render(
            project_id=project_id,
            season=season,
            status=outcome.status,
            image_path=str(outcome.image_path) if outcome.image_path else None,
            error=outcome.error,
            missing_species=outcome.missing_species,
            zone_snapshot=zone_snapshot,
        )
        # Commit per season so a later season's failure cannot discard an
        # earlier season's already-successful render.
        db.add(render)
        db.commit()
        db.refresh(render)
        results.append(render)

    return results


@router.get("/projects/{project_id}/renders", response_model=list[RenderOut])
def list_renders(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.renders


@router.get("/renders/{render_id}/image")
def get_render_image(render_id: str, db: Session = Depends(get_db)):
    render = db.get(Render, render_id)
    if render is None or render.status != "succeeded" or not render.image_path:
        raise HTTPException(status_code=404, detail="Render image not available")
    return FileResponse(render.image_path, media_type="image/jpeg")
