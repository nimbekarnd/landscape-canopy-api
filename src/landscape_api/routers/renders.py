import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from landscape_api.config import get_settings
from landscape_api.db import get_db
from landscape_api.models import Project, Render, Season
from landscape_api.schemas import RenderOut
from landscape_api.services.generation import GenerationOrchestrator
from landscape_api.services.image_edit_client import HttpImageEditClient
from landscape_api.services.reference_images import CachingReferenceImageService

router = APIRouter(tags=["renders"])


class NullReferenceProvider:
    """Used when no reference-image provider is configured; every lookup misses."""

    def fetch(self, common_name: str, season: Season) -> bytes | None:
        return None


def get_orchestrator() -> GenerationOrchestrator:
    settings = get_settings()
    reference_service = CachingReferenceImageService(
        provider=NullReferenceProvider(),
        cache_dir=settings.reference_cache_dir(),
    )
    image_edit_client = HttpImageEditClient(
        api_url=os.environ.get("IMAGE_EDIT_API_URL", ""),
        api_key=os.environ.get("IMAGE_EDIT_API_KEY", ""),
    )
    return GenerationOrchestrator(
        reference_service=reference_service,
        image_edit_client=image_edit_client,
        renders_dir=settings.renders_dir(),
    )


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
            zone_snapshot={
                "zone_count": len(zones),
            },
        )
        db.add(render)
        results.append(render)

    db.commit()
    for render in results:
        db.refresh(render)
    return results


@router.get("/projects/{project_id}/renders", response_model=list[RenderOut])
def list_renders(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.renders
