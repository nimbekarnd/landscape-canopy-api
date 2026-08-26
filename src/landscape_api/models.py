import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from landscape_api.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"


class Species(Base):
    __tablename__ = "species"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    common_name: Mapped[str]
    scientific_name: Mapped[str | None] = mapped_column(default=None)


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    name: Mapped[str]
    contact_info: Mapped[str | None] = mapped_column(default=None)
    address: Mapped[str | None] = mapped_column(default=None)

    projects: Mapped[list["Project"]] = relationship(back_populates="client")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    photo_path: Mapped[str]
    status: Mapped[str] = mapped_column(default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    client: Mapped["Client"] = relationship(back_populates="projects")
    zones: Mapped[list["Zone"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    renders: Mapped[list["Render"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    kind: Mapped[str]  # "region" or "pin"
    geometry: Mapped[dict] = mapped_column(JSON)

    project: Mapped["Project"] = relationship(back_populates="zones")
    palette_entries: Mapped[list["PaletteEntry"]] = relationship(
        back_populates="zone", cascade="all, delete-orphan"
    )


class PaletteEntry(Base):
    __tablename__ = "palette_entries"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"))
    species_id: Mapped[str] = mapped_column(ForeignKey("species.id"))
    proportion: Mapped[float]

    zone: Mapped["Zone"] = relationship(back_populates="palette_entries")
    species: Mapped["Species"] = relationship()


class Render(Base):
    __tablename__ = "renders"

    id: Mapped[str] = mapped_column(primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    season: Mapped[Season]
    status: Mapped[str]  # "succeeded" or "failed"
    image_path: Mapped[str | None] = mapped_column(default=None)
    error: Mapped[str | None] = mapped_column(default=None)
    missing_species: Mapped[list] = mapped_column(JSON, default=list)
    zone_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped["Project"] = relationship(back_populates="renders")
