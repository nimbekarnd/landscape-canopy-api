from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from landscape_api.db import get_db
from landscape_api.models import Project, Species, Zone, PaletteEntry
from landscape_api.schemas import ZoneIn, ZoneOut
from landscape_api.validation import validate_palette_entries, ZoneValidationError

router = APIRouter(tags=["zones"])


def _validate_palette(db: Session, palette_entries: list) -> None:
    """Reject unknown species ids or proportions that don't sum to 100 (422)."""
    requested_ids = [e.species_id for e in palette_entries]
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
            [(e.species_id, e.proportion) for e in palette_entries]
        )
    except ZoneValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _get_zone_in_project(db: Session, project_id: str, zone_id: str) -> Zone:
    zone = db.get(Zone, zone_id)
    if zone is None or zone.project_id != project_id:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


@router.post("/projects/{project_id}/zones", response_model=ZoneOut, status_code=201)
def create_zone(project_id: str, payload: ZoneIn, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    _validate_palette(db, payload.palette_entries)

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


@router.patch("/projects/{project_id}/zones/{zone_id}", response_model=ZoneOut)
def update_zone(
    project_id: str, zone_id: str, payload: ZoneIn, db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    zone = _get_zone_in_project(db, project_id, zone_id)

    _validate_palette(db, payload.palette_entries)

    zone.kind = payload.kind
    zone.geometry = payload.geometry
    zone.palette_entries = [
        PaletteEntry(species_id=e.species_id, proportion=e.proportion)
        for e in payload.palette_entries
    ]
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/projects/{project_id}/zones/{zone_id}", status_code=204)
def delete_zone(project_id: str, zone_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    zone = _get_zone_in_project(db, project_id, zone_id)

    db.delete(zone)
    db.commit()
