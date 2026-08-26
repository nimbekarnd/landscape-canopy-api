from datetime import datetime

from pydantic import BaseModel, ConfigDict

from landscape_api.models import Season


class ClientIn(BaseModel):
    name: str
    contact_info: str | None = None
    address: str | None = None


class ClientOut(ClientIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class SpeciesIn(BaseModel):
    common_name: str
    scientific_name: str | None = None


class SpeciesOut(SpeciesIn):
    model_config = ConfigDict(from_attributes=True)
    id: str


class PaletteEntryIn(BaseModel):
    species_id: str
    proportion: float


class PaletteEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    species_id: str
    proportion: float


class ZoneIn(BaseModel):
    kind: str
    geometry: dict
    palette_entries: list[PaletteEntryIn]


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    geometry: dict
    palette_entries: list[PaletteEntryOut]


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    client_id: str
    photo_path: str
    status: str
    created_at: datetime


class RenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    season: Season
    status: str
    image_path: str | None
    error: str | None
    missing_species: list[str]
    created_at: datetime
