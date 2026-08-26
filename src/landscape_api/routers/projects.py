from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from landscape_api.config import get_settings
from landscape_api.db import get_db
from landscape_api.models import Client, Project
from landscape_api.schemas import ProjectOut

router = APIRouter(tags=["projects"])


@router.post("/clients/{client_id}/projects", response_model=ProjectOut, status_code=201)
def create_project(client_id: str, photo: UploadFile, db: Session = Depends(get_db)):
    client_row = db.get(Client, client_id)
    if client_row is None:
        raise HTTPException(status_code=404, detail="Client not found")

    project = Project(client_id=client_id, photo_path="")
    db.add(project)
    db.flush()  # assign project.id before writing the file

    settings = get_settings()
    dest = settings.photos_dir() / f"{project.id}.jpg"
    dest.write_bytes(photo.file.read())
    project.photo_path = str(dest)

    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
