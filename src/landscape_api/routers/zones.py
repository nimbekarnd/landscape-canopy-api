from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from landscape_api.db import get_db
from landscape_api.models import Project, Species, Zone, PaletteEntry
from landscape_api.schemas import ZoneIn, ZoneOut
from landscape_api.validation import validate_palette_entries, ZoneValidationError

router = APIRouter(tags=["zones"])


@router.post("/projects/{project_id}/zones", response_model=ZoneOut, status_code=201)
def create_zone(project_id: str, payload: ZoneIn, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    requested_ids = [e.species_id for e in payload.palette_entries]
    if requested_ids:
        known_ids = {
            row_id
            for (row_id,) in db.query(Species.id).filter(Species.id.in_(requested_ids))
        }
        missing_ids = [
            species_id for species_id in dict.fromkeys(requested_ids)
            if species_id not in known_ids
        ]
        if missing_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown species id(s): {', '.join(missing_ids)}",
            )

    try:
        validate_palette_entries(
            [(e.species_id, e.proportion) for e in payload.palette_entries]
        )
    except ZoneValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    zone = Zone(project_id=project_id, kind=payload.kind, geometry=payload.geometry)
    zone.palette_entries = [
        PaletteEntry(species_id=e.species_id, proportion=e.proportion)
        for e in payload.palette_entries
    ]
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/projects/{project_id}/zones", response_model=list[ZoneOut])
def list_zones(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.zones
