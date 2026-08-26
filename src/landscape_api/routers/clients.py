from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from landscape_api.db import get_db
from landscape_api.models import Client
from landscape_api.schemas import ClientIn, ClientOut

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientOut, status_code=201)
def create_client(payload: ClientIn, db: Session = Depends(get_db)):
    client_row = Client(**payload.model_dump())
    db.add(client_row)
    db.commit()
    db.refresh(client_row)
    return client_row


@router.get("", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return db.query(Client).all()


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: str, db: Session = Depends(get_db)):
    client_row = db.get(Client, client_id)
    if client_row is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client_row
