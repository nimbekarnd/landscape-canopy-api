from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from landscape_api.db import get_db
from landscape_api.models import Species
from landscape_api.schemas import SpeciesIn, SpeciesOut

router = APIRouter(prefix="/species", tags=["species"])


@router.post("", response_model=SpeciesOut, status_code=201)
def create_species(payload: SpeciesIn, db: Session = Depends(get_db)):
    species = Species(**payload.model_dump())
    db.add(species)
    db.commit()
    db.refresh(species)
    return species


@router.get("", response_model=list[SpeciesOut])
def list_species(db: Session = Depends(get_db)):
    return db.query(Species).all()


@router.get("/{species_id}", response_model=SpeciesOut)
def get_species(species_id: str, db: Session = Depends(get_db)):
    species = db.get(Species, species_id)
    if species is None:
        raise HTTPException(status_code=404, detail="Species not found")
    return species
