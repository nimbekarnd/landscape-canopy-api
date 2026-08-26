# Landscape Canopy Backend API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully functional, cross-platform (Linux/Windows/Mac) REST API for the landscape plant rendering tool — projects, zones/palette, and season-by-season render generation — implemented test-first.

**Architecture:** A single FastAPI application backed by SQLAlchemy 2.0 over a local SQLite file. Generation is orchestrated in-process: a reference-image service resolves per-species/season photos, a mask-overlay builder rasterizes zones onto the yard photo, a prompt builder turns zone/palette data into a text prompt, and an image-edit client (behind an interface, swappable/fake-able) produces the final render. No background job queue or GPU infra — generation happens synchronously within the request/response cycle of a single API call.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, SQLite, Pillow (mask rasterization), httpx (outbound HTTP for the real image-edit/reference providers), pytest + Starlette TestClient. All dependencies ship as pure-Python or prebuilt wheels for Linux/Windows/Mac — no OS-specific code paths, all filesystem paths built with `pathlib.Path`.

**Spec:** `docs/superpowers/specs/2026-08-25-landscape-plant-rendering-design.md`

## Global Constraints

- Cross-platform: no shell-specific commands, no hardcoded `/` or `\` path separators — always `pathlib.Path`. Verify by running the full test suite on whichever OS is available; note in the README that CI/manual verification on the other two OSes is a follow-up if not available during implementation.
- Python 3.11+ (uses `X | None` union syntax and `enum.StrEnum` patterns... use `str, Enum` for 3.11 compatibility instead of `StrEnum`, which is 3.11+ but to stay safe on 3.11 use `class Season(str, Enum)`).
- All persistence via SQLite at a path controlled by the `LANDSCAPE_DATA_DIR` environment variable, defaulting to `./data` relative to the process working directory.
- Every task is TDD: failing test first, then minimal implementation, then commit.
- No placeholder/mock code ships in the non-test source tree except behind an explicit interface (`Protocol`) with a real implementation task later in this plan — tests use fakes, production code paths must be real.
- Proportions in a zone's palette entries must sum to 100 (±0.01 tolerance) and a zone must have at least one palette entry before generation is allowed, per spec's Error Handling section.

---

## File Structure

```
landscape-canopy/
  pyproject.toml
  requirements.txt
  README.md
  src/
    landscape_api/
      __init__.py
      config.py                # env-driven settings, cross-platform data dir
      db.py                     # SQLAlchemy engine/session, Base
      main.py                   # FastAPI app, router includes, health check
      models.py                 # SQLAlchemy ORM models
      schemas.py                # Pydantic request/response schemas
      validation.py             # zone/palette validation logic
      routers/
        __init__.py
        species.py
        clients.py
        projects.py
        zones.py
        renders.py
      services/
        __init__.py
        reference_images.py     # ReferenceImageProvider protocol + caching service
        mask_overlay.py         # Pillow-based zone rasterization
        prompt_builder.py       # pure function: zones+season -> prompt string
        image_edit_client.py    # ImageEditClient protocol + HTTP implementation
        generation.py           # GenerationOrchestrator tying the above together
  tests/
    conftest.py
    test_health.py
    test_validation.py
    test_species_api.py
    test_clients_api.py
    test_projects_api.py
    test_zones_api.py
    services/
      test_reference_images.py
      test_mask_overlay.py
      test_prompt_builder.py
      test_generation_orchestrator.py
    test_renders_api_integration.py
```

Each router owns one resource and depends only on `db.py`, `models.py`, `schemas.py`, and (for `renders.py`) `services/generation.py`. Each service is independently unit-testable with fakes — no service imports a router.

---

## Task 1: Project scaffolding, config, health check

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `src/landscape_api/__init__.py`
- Create: `src/landscape_api/config.py`
- Create: `src/landscape_api/main.py`
- Test: `tests/test_health.py`
- Test: `tests/conftest.py`

**Interfaces:**
- Produces: `landscape_api.config.Settings` with field `data_dir: Path`, and module-level `get_settings() -> Settings` (reads `LANDSCAPE_DATA_DIR` env var, defaults to `Path("./data")`, calls `.mkdir(parents=True, exist_ok=True)`).
- Produces: `landscape_api.main.app` (the FastAPI instance) with `GET /health` returning `{"status": "ok"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from landscape_api.main import app

@pytest.fixture()
def client():
    return TestClient(app)
```

```python
# tests/test_health.py
def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "landscape-canopy-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "pydantic>=2.7",
    "pillow>=10.4",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
```

```
# requirements.txt
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
pydantic>=2.7
pillow>=10.4
httpx>=0.27
pytest>=8.0
```

```python
# src/landscape_api/__init__.py
```

```python
# src/landscape_api/config.py
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    data_dir: Path


def get_settings() -> Settings:
    data_dir = Path(os.environ.get("LANDSCAPE_DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(data_dir=data_dir)
```

```python
# src/landscape_api/main.py
from fastapi import FastAPI

app = FastAPI(title="Landscape Canopy API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements.txt src tests
git commit -m "feat: project scaffolding, config, health check"
```

---

## Task 2: Database engine, session, base model

**Files:**
- Create: `src/landscape_api/db.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `landscape_api.config.get_settings()` from Task 1.
- Produces: `landscape_api.db.Base` (SQLAlchemy `DeclarativeBase`), `landscape_api.db.get_engine(db_path: Path)`, `landscape_api.db.SessionLocal` (sessionmaker bound lazily via `configure_session(engine)`), and a FastAPI dependency `get_db()` yielding a `Session`.
- The test suite uses an in-memory SQLite engine, configured in `conftest.py`, overriding the app's `get_db` dependency — every later router test depends on this override existing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db.py
from sqlalchemy import text
from landscape_api.db import get_engine, Base


def test_get_engine_creates_working_sqlite_connection(tmp_path):
    engine = get_engine(tmp_path / "test.db")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
    assert result == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api.db'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/db.py
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def get_engine(db_path: Path):
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


SessionLocal: sessionmaker | None = None


def configure_session(engine) -> None:
    global SessionLocal
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    if SessionLocal is None:
        raise RuntimeError("Session not configured; call configure_session() first")
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Update `tests/conftest.py` to configure an in-memory engine and override the FastAPI dependency for every test:

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from landscape_api.main import app
from landscape_api.db import Base, get_db


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/db.py tests/conftest.py tests/test_db.py
git commit -m "feat: SQLAlchemy engine/session setup with test override fixture"
```

---

## Task 3: ORM models for the full data model

**Files:**
- Create: `src/landscape_api/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `Base` from `db.py` (Task 2).
- Produces: ORM classes `Species`, `Client`, `Project`, `Zone`, `PaletteEntry`, `Render`, and `Season` (a `str, Enum` with values `spring`, `summer`, `fall`, `winter`). All primary keys are `id: Mapped[str]` (UUID4 hex string, `default=lambda: uuid.uuid4().hex`). Relationships: `Client.projects`, `Project.zones`, `Project.renders`, `Zone.palette_entries`, `PaletteEntry.species` (all later tasks reference these exact attribute names).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from landscape_api.models import Client, Project, Zone, PaletteEntry, Species, Render, Season


def test_full_graph_persists_and_relates(db_session):
    client_row = Client(name="Agriformers Pilot Client")
    project = Project(client=client_row, photo_path="/tmp/yard.jpg")
    species = Species(common_name="Red Maple", scientific_name="Acer rubrum")
    zone = Zone(project=project, kind="region", geometry={"points": [[0, 0], [1, 1]]})
    entry = PaletteEntry(zone=zone, species=species, proportion=100.0)
    render = Render(project=project, season=Season.FALL, status="succeeded", image_path="/tmp/out.jpg")

    db_session.add_all([client_row, project, species, zone, entry, render])
    db_session.commit()

    fetched = db_session.query(Project).one()
    assert fetched.client.name == "Agriformers Pilot Client"
    assert fetched.zones[0].palette_entries[0].species.common_name == "Red Maple"
    assert fetched.renders[0].season == Season.FALL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api.models'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/models.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/models.py tests/test_models.py
git commit -m "feat: ORM models for Client/Project/Zone/PaletteEntry/Species/Render"
```

---

## Task 4: Zone/palette validation logic

**Files:**
- Create: `src/landscape_api/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Produces: `class ZoneValidationError(Exception)`, and `validate_palette_entries(entries: list[tuple[str, float]]) -> None` where each tuple is `(species_id, proportion)`. Raises `ZoneValidationError` with a human-readable message if `entries` is empty or the proportions don't sum to 100 within 0.01 tolerance. Later tasks (Task 6's zone router, Task 9's generation orchestrator) call this exact function before persisting or generating.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_validation.py
import pytest
from landscape_api.validation import validate_palette_entries, ZoneValidationError


def test_valid_proportions_pass():
    validate_palette_entries([("sp1", 60.0), ("sp2", 40.0)])  # should not raise


def test_empty_entries_raises():
    with pytest.raises(ZoneValidationError, match="at least one species"):
        validate_palette_entries([])


def test_proportions_not_summing_to_100_raises():
    with pytest.raises(ZoneValidationError, match="sum to 100"):
        validate_palette_entries([("sp1", 60.0), ("sp2", 30.0)])


def test_proportions_within_tolerance_pass():
    validate_palette_entries([("sp1", 33.34), ("sp2", 33.33), ("sp3", 33.33)])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api.validation'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/validation.py
class ZoneValidationError(Exception):
    pass


def validate_palette_entries(entries: list[tuple[str, float]]) -> None:
    if not entries:
        raise ZoneValidationError("A zone requires at least one species.")
    total = sum(proportion for _, proportion in entries)
    if abs(total - 100.0) > 0.02:
        raise ZoneValidationError(
            f"Palette entry proportions must sum to 100 (got {total})."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/validation.py tests/test_validation.py
git commit -m "feat: zone/palette proportion validation"
```

---

## Task 5: Pydantic schemas

**Files:**
- Create: `src/landscape_api/schemas.py`
- Test: `tests/test_schemas.py`

**Interfaces:**
- Consumes: `Season` from `models.py` (Task 3).
- Produces: `ClientIn`, `ClientOut`, `SpeciesIn`, `SpeciesOut`, `ProjectOut`, `PaletteEntryIn`, `PaletteEntryOut`, `ZoneIn` (fields: `kind: str`, `geometry: dict`, `palette_entries: list[PaletteEntryIn]`), `ZoneOut`, `RenderOut`. All `*Out` schemas set `model_config = ConfigDict(from_attributes=True)` so they serialize directly from ORM instances — routers in later tasks rely on this.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schemas.py
from landscape_api.schemas import ZoneIn, PaletteEntryIn


def test_zone_in_accepts_nested_palette_entries():
    zone = ZoneIn(
        kind="region",
        geometry={"points": [[0, 0], [1, 1]]},
        palette_entries=[PaletteEntryIn(species_id="sp1", proportion=100.0)],
    )
    assert zone.palette_entries[0].proportion == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api.schemas'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/schemas.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/schemas.py tests/test_schemas.py
git commit -m "feat: Pydantic request/response schemas"
```

---

## Task 6: Species and Client CRUD routers

**Files:**
- Create: `src/landscape_api/routers/__init__.py`
- Create: `src/landscape_api/routers/species.py`
- Create: `src/landscape_api/routers/clients.py`
- Modify: `src/landscape_api/main.py`
- Test: `tests/test_species_api.py`
- Test: `tests/test_clients_api.py`

**Interfaces:**
- Consumes: `get_db` (Task 2), ORM models (Task 3), schemas (Task 5).
- Produces: routers mounted at `/species` and `/clients` with `POST` (create) and `GET /{id}` (fetch) and `GET` (list). These are the two simplest CRUD resources and establish the router pattern Task 7 and Task 8 follow.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_species_api.py
def test_create_and_fetch_species(client):
    create_resp = client.post("/species", json={"common_name": "Red Maple", "scientific_name": "Acer rubrum"})
    assert create_resp.status_code == 201
    species_id = create_resp.json()["id"]

    get_resp = client.get(f"/species/{species_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["common_name"] == "Red Maple"


def test_list_species(client):
    client.post("/species", json={"common_name": "Serviceberry"})
    resp = client.get("/species")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
```

```python
# tests/test_clients_api.py
def test_create_and_fetch_client(client):
    create_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    assert create_resp.status_code == 201
    client_id = create_resp.json()["id"]

    get_resp = client.get(f"/clients/{client_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Agriformers Pilot"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_species_api.py tests/test_clients_api.py -v`
Expected: FAIL — 404s, since no routers are mounted yet

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/routers/__init__.py
```

```python
# src/landscape_api/routers/species.py
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
```

```python
# src/landscape_api/routers/clients.py
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
```

```python
# src/landscape_api/main.py
from fastapi import FastAPI

from landscape_api.routers import species, clients

app = FastAPI(title="Landscape Canopy API")
app.include_router(species.router)
app.include_router(clients.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_species_api.py tests/test_clients_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/routers/__init__.py src/landscape_api/routers/species.py src/landscape_api/routers/clients.py src/landscape_api/main.py tests/test_species_api.py tests/test_clients_api.py
git commit -m "feat: Species and Client CRUD endpoints"
```

---

## Task 7: Project router with photo upload

**Files:**
- Create: `src/landscape_api/routers/projects.py`
- Modify: `src/landscape_api/main.py`
- Modify: `src/landscape_api/config.py`
- Test: `tests/test_projects_api.py`

**Interfaces:**
- Consumes: `get_db`, `Client`/`Project` models, `ProjectOut` schema, `get_settings()` (Task 1, extended here).
- Produces: `POST /clients/{client_id}/projects` (multipart upload, field name `photo`) saving the file under `settings.data_dir / "photos" / f"{project_id}.jpg"` and returning `ProjectOut`; `GET /projects/{id}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_projects_api.py
import io


def test_create_project_with_photo_upload(client):
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]

    fake_photo = io.BytesIO(b"fake-jpeg-bytes")
    resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", fake_photo, "image/jpeg")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["client_id"] == client_id
    assert body["status"] == "draft"

    get_resp = client.get(f"/projects/{body['id']}")
    assert get_resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_projects_api.py -v`
Expected: FAIL — 404, no `/clients/{id}/projects` route

- [ ] **Step 3: Write minimal implementation**

Extend `config.py`'s `Settings` with a helper (append, don't remove Task 1's code):

```python
# src/landscape_api/config.py (append)
    def photos_dir(self) -> Path:
        path = self.data_dir / "photos"
        path.mkdir(parents=True, exist_ok=True)
        return path
```

(Note: this makes `Settings` no longer trivially frozen-dataclass-only if methods are added — a `@dataclass(frozen=True)` supports methods fine, so this is a plain addition, not a redesign.)

```python
# src/landscape_api/routers/projects.py
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
```

```python
# src/landscape_api/main.py
from fastapi import FastAPI

from landscape_api.routers import species, clients, projects

app = FastAPI(title="Landscape Canopy API")
app.include_router(species.router)
app.include_router(clients.router)
app.include_router(projects.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_projects_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/routers/projects.py src/landscape_api/main.py src/landscape_api/config.py tests/test_projects_api.py
git commit -m "feat: Project creation with photo upload"
```

---

## Task 8: Zone + PaletteEntry nested router

**Files:**
- Create: `src/landscape_api/routers/zones.py`
- Modify: `src/landscape_api/main.py`
- Test: `tests/test_zones_api.py`

**Interfaces:**
- Consumes: `validate_palette_entries` (Task 4), `Zone`/`PaletteEntry`/`Project` models, `ZoneIn`/`ZoneOut` schemas.
- Produces: `POST /projects/{project_id}/zones` (body: `ZoneIn`) — calls `validate_palette_entries` before persisting, returns 422 with the validation message on failure; `GET /projects/{project_id}/zones` listing all zones for a project.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_zones_api.py
import io


def _make_project(client):
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]
    photo = io.BytesIO(b"fake-jpeg-bytes")
    project_resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", photo, "image/jpeg")},
    )
    return project_resp.json()["id"]


def test_create_zone_with_valid_proportions(client):
    project_id = _make_project(client)
    species_resp = client.post("/species", json={"common_name": "Red Maple"})
    species_id = species_resp.json()["id"]

    resp = client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["palette_entries"][0]["proportion"] == 100.0


def test_create_zone_with_invalid_proportions_returns_422(client):
    project_id = _make_project(client)
    species_resp = client.post("/species", json={"common_name": "Red Maple"})
    species_id = species_resp.json()["id"]

    resp = client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [1, 1]]},
            "palette_entries": [{"species_id": species_id, "proportion": 40.0}],
        },
    )
    assert resp.status_code == 422
    assert "sum to 100" in resp.json()["detail"]


def test_list_zones_for_project(client):
    project_id = _make_project(client)
    species_resp = client.post("/species", json={"common_name": "Red Maple"})
    species_id = species_resp.json()["id"]
    client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "pin",
            "geometry": {"point": [5, 5]},
            "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
        },
    )
    resp = client.get(f"/projects/{project_id}/zones")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_zones_api.py -v`
Expected: FAIL — 404, no `/projects/{id}/zones` route

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/routers/zones.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from landscape_api.db import get_db
from landscape_api.models import Project, Zone, PaletteEntry
from landscape_api.schemas import ZoneIn, ZoneOut
from landscape_api.validation import validate_palette_entries, ZoneValidationError

router = APIRouter(tags=["zones"])


@router.post("/projects/{project_id}/zones", response_model=ZoneOut, status_code=201)
def create_zone(project_id: str, payload: ZoneIn, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

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
```

```python
# src/landscape_api/main.py
from fastapi import FastAPI

from landscape_api.routers import species, clients, projects, zones

app = FastAPI(title="Landscape Canopy API")
app.include_router(species.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(zones.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_zones_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/routers/zones.py src/landscape_api/main.py tests/test_zones_api.py
git commit -m "feat: Zone/PaletteEntry endpoints with proportion validation"
```

---

## Task 9: Reference image service

**Files:**
- Create: `src/landscape_api/services/__init__.py`
- Create: `src/landscape_api/services/reference_images.py`
- Test: `tests/services/__init__.py`
- Test: `tests/services/test_reference_images.py`

**Interfaces:**
- Produces: `class ReferenceImageProvider(Protocol): def fetch(self, common_name: str, season: Season) -> bytes | None`, and `class CachingReferenceImageService` with constructor `(provider: ReferenceImageProvider, cache_dir: Path)` and method `get_reference_image(common_name: str, season: Season) -> Path | None`. Returns `None` (no exception) when the provider has no image — Task 12's orchestrator relies on this `None` to trigger the text-only-prompt fallback.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/__init__.py
```

```python
# tests/services/test_reference_images.py
from landscape_api.models import Season
from landscape_api.services.reference_images import CachingReferenceImageService


class FakeProvider:
    def __init__(self, image_bytes: bytes | None):
        self.image_bytes = image_bytes
        self.calls = 0

    def fetch(self, common_name: str, season: Season) -> bytes | None:
        self.calls += 1
        return self.image_bytes


def test_returns_cached_path_on_second_call_without_refetching(tmp_path):
    provider = FakeProvider(b"fake-image-bytes")
    service = CachingReferenceImageService(provider=provider, cache_dir=tmp_path)

    first = service.get_reference_image("Red Maple", Season.FALL)
    second = service.get_reference_image("Red Maple", Season.FALL)

    assert first == second
    assert first.exists()
    assert provider.calls == 1  # cached on the second call


def test_returns_none_when_provider_has_no_image(tmp_path):
    provider = FakeProvider(None)
    service = CachingReferenceImageService(provider=provider, cache_dir=tmp_path)

    result = service.get_reference_image("Unknown Shrub", Season.WINTER)

    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_reference_images.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api.services'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/services/__init__.py
```

```python
# src/landscape_api/services/reference_images.py
import re
from pathlib import Path
from typing import Protocol

from landscape_api.models import Season


class ReferenceImageProvider(Protocol):
    def fetch(self, common_name: str, season: Season) -> bytes | None: ...


def _cache_key(common_name: str, season: Season) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", common_name.lower()).strip("-")
    return f"{slug}_{season.value}.jpg"


class CachingReferenceImageService:
    def __init__(self, provider: ReferenceImageProvider, cache_dir: Path):
        self._provider = provider
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_reference_image(self, common_name: str, season: Season) -> Path | None:
        cache_path = self._cache_dir / _cache_key(common_name, season)
        if cache_path.exists():
            return cache_path

        image_bytes = self._provider.fetch(common_name, season)
        if image_bytes is None:
            return None

        cache_path.write_bytes(image_bytes)
        return cache_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_reference_images.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/services/__init__.py src/landscape_api/services/reference_images.py tests/services
git commit -m "feat: caching reference image service"
```

---

## Task 10: Mask overlay builder

**Files:**
- Create: `src/landscape_api/services/mask_overlay.py`
- Test: `tests/services/test_mask_overlay.py`

**Interfaces:**
- Consumes: `Zone` model's `geometry` shape (`{"points": [[x, y], ...]}` for regions, `{"point": [x, y]}` for pins) from Task 3.
- Produces: `build_mask_overlay(photo_path: Path, zones: list[Zone], output_path: Path) -> Path`. Renders a black image the same size as the source photo with each region zone drawn as a filled white polygon and each pin zone drawn as a filled white circle, saves it to `output_path`, and returns `output_path`. Task 12's orchestrator calls this exact signature.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_mask_overlay.py
from PIL import Image

from landscape_api.services.mask_overlay import build_mask_overlay


class _FakeZone:
    def __init__(self, kind, geometry):
        self.kind = kind
        self.geometry = geometry


def test_build_mask_overlay_draws_region_and_pin(tmp_path):
    photo_path = tmp_path / "yard.jpg"
    Image.new("RGB", (100, 100), color="blue").save(photo_path)

    zones = [
        _FakeZone("region", {"points": [[10, 10], [50, 10], [50, 50], [10, 50]]}),
        _FakeZone("pin", {"point": [80, 80]}),
    ]
    output_path = tmp_path / "mask.png"

    result_path = build_mask_overlay(photo_path, zones, output_path)

    assert result_path == output_path
    mask = Image.open(output_path)
    assert mask.size == (100, 100)
    # A pixel inside the painted region should be white; a corner outside any zone should be black.
    assert mask.getpixel((30, 30))[:3] == (255, 255, 255)
    assert mask.getpixel((1, 1))[:3] == (0, 0, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_mask_overlay.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api.services.mask_overlay'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/services/mask_overlay.py
from pathlib import Path

from PIL import Image, ImageDraw

PIN_RADIUS = 15


def build_mask_overlay(photo_path: Path, zones: list, output_path: Path) -> Path:
    with Image.open(photo_path) as photo:
        width, height = photo.size

    mask = Image.new("RGB", (width, height), color="black")
    draw = ImageDraw.Draw(mask)

    for zone in zones:
        if zone.kind == "region":
            points = [tuple(p) for p in zone.geometry["points"]]
            draw.polygon(points, fill="white")
        elif zone.kind == "pin":
            x, y = zone.geometry["point"]
            draw.ellipse(
                [x - PIN_RADIUS, y - PIN_RADIUS, x + PIN_RADIUS, y + PIN_RADIUS],
                fill="white",
            )

    mask.save(output_path)
    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_mask_overlay.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/services/mask_overlay.py tests/services/test_mask_overlay.py
git commit -m "feat: mask overlay builder for zone rasterization"
```

---

## Task 11: Prompt builder

**Files:**
- Create: `src/landscape_api/services/prompt_builder.py`
- Test: `tests/services/test_prompt_builder.py`

**Interfaces:**
- Consumes: `Zone`/`PaletteEntry`/`Species` shape (duck-typed, same attribute names as the ORM models from Task 3).
- Produces: `build_prompt(zones: list[Zone], season: Season, missing_species: list[str]) -> str`. Pure function — no I/O. Task 12's orchestrator calls this exact signature and passes the result as the text prompt to the image-edit client.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_prompt_builder.py
from landscape_api.models import Season
from landscape_api.services.prompt_builder import build_prompt


class _FakeSpecies:
    def __init__(self, common_name):
        self.common_name = common_name


class _FakeEntry:
    def __init__(self, common_name, proportion):
        self.species = _FakeSpecies(common_name)
        self.proportion = proportion


class _FakeZone:
    def __init__(self, kind, palette_entries):
        self.kind = kind
        self.palette_entries = palette_entries


def test_prompt_includes_species_proportions_and_season():
    zones = [
        _FakeZone("region", [_FakeEntry("Red Maple", 60.0), _FakeEntry("Serviceberry", 40.0)]),
    ]
    prompt = build_prompt(zones, Season.FALL, missing_species=[])

    assert "fall" in prompt.lower()
    assert "Red Maple" in prompt
    assert "60%" in prompt
    assert "Serviceberry" in prompt
    assert "40%" in prompt


def test_prompt_notes_species_without_reference_images():
    zones = [_FakeZone("region", [_FakeEntry("Rare Shrub", 100.0)])]
    prompt = build_prompt(zones, Season.SPRING, missing_species=["Rare Shrub"])

    assert "Rare Shrub" in prompt
    assert "no reference image" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_prompt_builder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api.services.prompt_builder'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/services/prompt_builder.py
from landscape_api.models import Season


def build_prompt(zones: list, season: Season, missing_species: list[str]) -> str:
    lines = [
        f"Render this landscape photo populated with the following plants for {season.value} season.",
        "Use the marked zones (white regions/circles in the provided mask) as planting locations.",
    ]

    for i, zone in enumerate(zones, start=1):
        entries_desc = ", ".join(
            f"{entry.species.common_name} ({entry.proportion:g}%)"
            for entry in zone.palette_entries
        )
        lines.append(f"Zone {i} ({zone.kind}): {entries_desc}")

    if missing_species:
        joined = ", ".join(missing_species)
        lines.append(
            f"No reference image was available for: {joined}. "
            "Render these from general species knowledge as accurately as possible."
        )

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_prompt_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/services/prompt_builder.py tests/services/test_prompt_builder.py
git commit -m "feat: text prompt builder for generation requests"
```

---

## Task 12: Image-edit client interface + HTTP implementation

**Files:**
- Create: `src/landscape_api/services/image_edit_client.py`
- Test: `tests/services/test_image_edit_client.py`

**Interfaces:**
- Produces: `@dataclass GenerationRequest(base_photo_path: Path, mask_overlay_path: Path, reference_image_paths: list[Path], prompt: str)`, `@dataclass GenerationResult(image_bytes: bytes)`, `class ImageEditError(Exception)`, `class ImageEditClient(Protocol): def generate(self, request: GenerationRequest) -> GenerationResult`, and `class HttpImageEditClient` implementing that protocol via `httpx.Client`, configured with `api_url: str` and `api_key: str` at construction. `HttpImageEditClient.generate` raises `ImageEditError` on any non-2xx response or transport error — Task 13's orchestrator catches exactly this exception type.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_image_edit_client.py
from pathlib import Path

import httpx
import pytest

from landscape_api.services.image_edit_client import (
    GenerationRequest,
    HttpImageEditClient,
    ImageEditError,
)


def test_generate_returns_image_bytes_on_success(tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"photo-bytes")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask-bytes")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"rendered-image-bytes")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = HttpImageEditClient(api_url="https://example.test/edit", api_key="fake-key", http_client=http_client)

    result = client.generate(
        GenerationRequest(
            base_photo_path=photo,
            mask_overlay_path=mask,
            reference_image_paths=[],
            prompt="add trees",
        )
    )

    assert result.image_bytes == b"rendered-image-bytes"


def test_generate_raises_image_edit_error_on_failure(tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"photo-bytes")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask-bytes")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"server error")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = HttpImageEditClient(api_url="https://example.test/edit", api_key="fake-key", http_client=http_client)

    with pytest.raises(ImageEditError):
        client.generate(
            GenerationRequest(
                base_photo_path=photo,
                mask_overlay_path=mask,
                reference_image_paths=[],
                prompt="add trees",
            )
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_image_edit_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api.services.image_edit_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/services/image_edit_client.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx


@dataclass
class GenerationRequest:
    base_photo_path: Path
    mask_overlay_path: Path
    reference_image_paths: list[Path] = field(default_factory=list)
    prompt: str = ""


@dataclass
class GenerationResult:
    image_bytes: bytes


class ImageEditError(Exception):
    pass


class ImageEditClient(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...


class HttpImageEditClient:
    def __init__(self, api_url: str, api_key: str, http_client: httpx.Client | None = None):
        self._api_url = api_url
        self._api_key = api_key
        self._http_client = http_client or httpx.Client(timeout=60.0)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        files = {
            "base_photo": request.base_photo_path.read_bytes(),
            "mask_overlay": request.mask_overlay_path.read_bytes(),
        }
        data = {"prompt": request.prompt}
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            response = self._http_client.post(
                self._api_url, data=data, files=files, headers=headers
            )
        except httpx.HTTPError as exc:
            raise ImageEditError(f"Transport error calling image-edit API: {exc}") from exc

        if response.status_code >= 300:
            raise ImageEditError(
                f"Image-edit API returned {response.status_code}: {response.text[:200]}"
            )

        return GenerationResult(image_bytes=response.content)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_image_edit_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/services/image_edit_client.py tests/services/test_image_edit_client.py
git commit -m "feat: image-edit client interface and HTTP implementation"
```

---

## Task 13: Generation orchestrator

**Files:**
- Create: `src/landscape_api/services/generation.py`
- Test: `tests/services/test_generation_orchestrator.py`

**Interfaces:**
- Consumes: `CachingReferenceImageService` (Task 9), `build_mask_overlay` (Task 10), `build_prompt` (Task 11), `ImageEditClient`/`GenerationRequest`/`ImageEditError` (Task 12), `Zone`/`Project`/`Render`/`Season` models (Task 3).
- Produces: `@dataclass RenderOutcome(status: str, image_path: Path | None, error: str | None, missing_species: list[str])` and `class GenerationOrchestrator` with constructor `(reference_service: CachingReferenceImageService, image_edit_client: ImageEditClient, renders_dir: Path)` and method `generate_for_season(project: Project, zones: list[Zone], season: Season) -> RenderOutcome`. On `ImageEditError`, retries the call exactly once before returning `status="failed"`. Task 14's render router calls this exact method and persists a `Render` row from its return value.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/test_generation_orchestrator.py
from pathlib import Path

from PIL import Image

from landscape_api.models import Season
from landscape_api.services.generation import GenerationOrchestrator
from landscape_api.services.image_edit_client import GenerationResult, ImageEditError


class _FakeSpecies:
    def __init__(self, common_name):
        self.common_name = common_name


class _FakeEntry:
    def __init__(self, common_name, proportion):
        self.species = _FakeSpecies(common_name)
        self.proportion = proportion


class _FakeZone:
    def __init__(self, kind, geometry, palette_entries):
        self.kind = kind
        self.geometry = geometry
        self.palette_entries = palette_entries


class _FakeProject:
    def __init__(self, photo_path):
        self.photo_path = photo_path


class _FakeReferenceService:
    def __init__(self, has_image: bool):
        self._has_image = has_image

    def get_reference_image(self, common_name, season):
        return Path("fake-ref.jpg") if self._has_image else None


class _AlwaysSucceedsClient:
    def generate(self, request):
        return GenerationResult(image_bytes=b"rendered-bytes")


class _AlwaysFailsClient:
    def __init__(self):
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        raise ImageEditError("boom")


class _FailsOnceThenSucceedsClient:
    def __init__(self):
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        if self.calls == 1:
            raise ImageEditError("transient failure")
        return GenerationResult(image_bytes=b"rendered-bytes")


def _make_project_photo(tmp_path):
    photo_path = tmp_path / "yard.jpg"
    Image.new("RGB", (50, 50), color="green").save(photo_path)
    return photo_path


def test_successful_generation_returns_succeeded_outcome(tmp_path):
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [_FakeZone("region", {"points": [[0, 0], [10, 0], [10, 10]]}, [_FakeEntry("Red Maple", 100.0)])]

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=_AlwaysSucceedsClient(),
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.FALL)

    assert outcome.status == "succeeded"
    assert outcome.image_path.exists()
    assert outcome.missing_species == []


def test_missing_reference_image_flags_species_but_still_succeeds(tmp_path):
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [_FakeZone("region", {"points": [[0, 0], [10, 0], [10, 10]]}, [_FakeEntry("Rare Shrub", 100.0)])]

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=False),
        image_edit_client=_AlwaysSucceedsClient(),
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.SPRING)

    assert outcome.status == "succeeded"
    assert outcome.missing_species == ["Rare Shrub"]


def test_retries_once_then_succeeds(tmp_path):
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [_FakeZone("region", {"points": [[0, 0], [10, 0], [10, 10]]}, [_FakeEntry("Red Maple", 100.0)])]
    flaky_client = _FailsOnceThenSucceedsClient()

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=flaky_client,
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.WINTER)

    assert outcome.status == "succeeded"
    assert flaky_client.calls == 2


def test_fails_after_retry_exhausted(tmp_path):
    photo_path = _make_project_photo(tmp_path)
    project = _FakeProject(photo_path=str(photo_path))
    zones = [_FakeZone("region", {"points": [[0, 0], [10, 0], [10, 10]]}, [_FakeEntry("Red Maple", 100.0)])]
    failing_client = _AlwaysFailsClient()

    orchestrator = GenerationOrchestrator(
        reference_service=_FakeReferenceService(has_image=True),
        image_edit_client=failing_client,
        renders_dir=tmp_path / "renders",
    )

    outcome = orchestrator.generate_for_season(project, zones, Season.SUMMER)

    assert outcome.status == "failed"
    assert outcome.image_path is None
    assert failing_client.calls == 2
    assert "boom" in outcome.error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_generation_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landscape_api.services.generation'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/landscape_api/services/generation.py
import uuid
from dataclasses import dataclass
from pathlib import Path

from landscape_api.models import Season
from landscape_api.services.image_edit_client import (
    GenerationRequest,
    ImageEditClient,
    ImageEditError,
)
from landscape_api.services.mask_overlay import build_mask_overlay
from landscape_api.services.prompt_builder import build_prompt
from landscape_api.services.reference_images import CachingReferenceImageService


@dataclass
class RenderOutcome:
    status: str
    image_path: Path | None
    error: str | None
    missing_species: list[str]


class GenerationOrchestrator:
    def __init__(
        self,
        reference_service: CachingReferenceImageService,
        image_edit_client: ImageEditClient,
        renders_dir: Path,
    ):
        self._reference_service = reference_service
        self._image_edit_client = image_edit_client
        self._renders_dir = renders_dir
        self._renders_dir.mkdir(parents=True, exist_ok=True)

    def generate_for_season(self, project, zones: list, season: Season) -> RenderOutcome:
        missing_species: list[str] = []
        reference_paths: list[Path] = []

        for zone in zones:
            for entry in zone.palette_entries:
                path = self._reference_service.get_reference_image(
                    entry.species.common_name, season
                )
                if path is None:
                    missing_species.append(entry.species.common_name)
                else:
                    reference_paths.append(path)

        mask_path = self._renders_dir / f"mask-{uuid.uuid4().hex}.png"
        build_mask_overlay(Path(project.photo_path), zones, mask_path)

        prompt = build_prompt(zones, season, missing_species)
        request = GenerationRequest(
            base_photo_path=Path(project.photo_path),
            mask_overlay_path=mask_path,
            reference_image_paths=reference_paths,
            prompt=prompt,
        )

        last_error: str | None = None
        for _ in range(2):  # one attempt + one retry
            try:
                result = self._image_edit_client.generate(request)
                image_path = self._renders_dir / f"render-{uuid.uuid4().hex}.jpg"
                image_path.write_bytes(result.image_bytes)
                return RenderOutcome(
                    status="succeeded",
                    image_path=image_path,
                    error=None,
                    missing_species=missing_species,
                )
            except ImageEditError as exc:
                last_error = str(exc)

        return RenderOutcome(
            status="failed",
            image_path=None,
            error=last_error,
            missing_species=missing_species,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/services/test_generation_orchestrator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/services/generation.py tests/services/test_generation_orchestrator.py
git commit -m "feat: generation orchestrator tying reference images, mask, prompt, and image-edit client together"
```

---

## Task 14: Render endpoints wiring the orchestrator into the API

**Files:**
- Create: `src/landscape_api/routers/renders.py`
- Modify: `src/landscape_api/main.py`
- Modify: `src/landscape_api/config.py`
- Test: `tests/test_renders_api_integration.py`

**Interfaces:**
- Consumes: `GenerationOrchestrator` (Task 13), `HttpImageEditClient` (Task 12), `CachingReferenceImageService` (Task 9), `Render`/`Project`/`Zone` models (Task 3), `RenderOut` schema (Task 5).
- Produces: `POST /projects/{project_id}/renders` (body: `{"seasons": ["fall", "winter"]}`, defaults to all four if omitted) — generates one `Render` per requested season and returns `list[RenderOut]`; `GET /projects/{project_id}/renders` listing all renders for a project. Dependency-injects the orchestrator via a FastAPI dependency `get_orchestrator()` so tests can override it with a fake client, matching the pattern established by `get_db` in Task 2.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_renders_api_integration.py
import io

from landscape_api.routers.renders import get_orchestrator
from landscape_api.services.generation import GenerationOrchestrator
from landscape_api.services.image_edit_client import GenerationResult
from landscape_api.services.reference_images import CachingReferenceImageService
from landscape_api.main import app


class _FakeSucceedingClient:
    def generate(self, request):
        return GenerationResult(image_bytes=b"rendered-bytes")


class _NoOpProvider:
    def fetch(self, common_name, season):
        return None


def _make_project_and_zone(client):
    client_resp = client.post("/clients", json={"name": "Agriformers Pilot"})
    client_id = client_resp.json()["id"]
    photo = io.BytesIO(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    project_resp = client.post(
        f"/clients/{client_id}/projects",
        files={"photo": ("yard.jpg", photo, "image/jpeg")},
    )
    project_id = project_resp.json()["id"]

    species_resp = client.post("/species", json={"common_name": "Red Maple"})
    species_id = species_resp.json()["id"]

    client.post(
        f"/projects/{project_id}/zones",
        json={
            "kind": "region",
            "geometry": {"points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            "palette_entries": [{"species_id": species_id, "proportion": 100.0}],
        },
    )
    return project_id


def test_generate_renders_for_requested_seasons(client, tmp_path):
    fake_orchestrator = GenerationOrchestrator(
        reference_service=CachingReferenceImageService(
            provider=_NoOpProvider(), cache_dir=tmp_path / "refs"
        ),
        image_edit_client=_FakeSucceedingClient(),
        renders_dir=tmp_path / "renders",
    )
    app.dependency_overrides[get_orchestrator] = lambda: fake_orchestrator

    project_id = _make_project_and_zone(client)

    resp = client.post(f"/projects/{project_id}/renders", json={"seasons": ["fall", "spring"]})

    assert resp.status_code == 201
    renders = resp.json()
    assert {r["season"] for r in renders} == {"fall", "spring"}
    assert all(r["status"] == "succeeded" for r in renders)

    list_resp = client.get(f"/projects/{project_id}/renders")
    assert len(list_resp.json()) == 2

    app.dependency_overrides.pop(get_orchestrator, None)
```

Note: the real yard photo needs to be a valid image for `build_mask_overlay`'s `Image.open` call to succeed — using real JPEG magic bytes (`\xff\xd8\xff\xe0`) alone won't produce a loadable image with Pillow. Use a real tiny JPEG fixture instead of raw bytes:

```python
# tests/conftest.py (append)
import io
from PIL import Image


def make_test_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color="green").save(buf, format="JPEG")
    return buf.getvalue()
```

And update `_make_project_and_zone` in the test file to use `io.BytesIO(make_test_jpeg_bytes())` instead of the raw fake bytes, importing `make_test_jpeg_bytes` from `conftest`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_renders_api_integration.py -v`
Expected: FAIL — 404, no `/projects/{id}/renders` route

- [ ] **Step 3: Write minimal implementation**

Extend `config.py` again (append, alongside `photos_dir`):

```python
# src/landscape_api/config.py (append)
    def renders_dir(self) -> Path:
        path = self.data_dir / "renders"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def reference_cache_dir(self) -> Path:
        path = self.data_dir / "reference_cache"
        path.mkdir(parents=True, exist_ok=True)
        return path
```

```python
# src/landscape_api/routers/renders.py
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
```

```python
# src/landscape_api/main.py
from fastapi import FastAPI

from landscape_api.routers import species, clients, projects, zones, renders

app = FastAPI(title="Landscape Canopy API")
app.include_router(species.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(zones.router)
app.include_router(renders.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_renders_api_integration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/landscape_api/routers/renders.py src/landscape_api/main.py src/landscape_api/config.py tests/test_renders_api_integration.py tests/conftest.py
git commit -m "feat: render generation and listing endpoints"
```

---

## Task 15: Full test suite run and cross-platform README

**Files:**
- Create: `README.md`

**Interfaces:**
- No new code interfaces — this task verifies everything from Tasks 1-14 works together and documents how to run it on all three target platforms.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`
Expected: PASS — every test file from Tasks 1-14 passes together (this is the first point where the full suite runs as a whole; if anything regressed due to an earlier task's change, fix it now before writing docs)

- [ ] **Step 2: Write the README**

```markdown
# Landscape Canopy API

Backend API for the landscape plant rendering tool. See
`docs/superpowers/specs/2026-08-25-landscape-plant-rendering-design.md`
for the product design this implements.

## Setup

Requires Python 3.11+.

### Linux / macOS

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

### Windows (PowerShell)

    py -3 -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt

## Running the API

    uvicorn landscape_api.main:app --reload

The API listens on http://127.0.0.1:8000 by default on all three
platforms. Interactive docs are at http://127.0.0.1:8000/docs.

Data (SQLite file, uploaded photos, generated renders, cached reference
images) is stored under `./data` relative to the working directory,
controlled by the `LANDSCAPE_DATA_DIR` environment variable.

To enable real image generation, set:

    IMAGE_EDIT_API_URL=<your provider's endpoint>
    IMAGE_EDIT_API_KEY=<your provider's key>

Without these set, render generation calls will fail cleanly (each
requested season's `Render` gets `status: "failed"` with an error
message) rather than crashing the app — the rest of the API remains
fully usable for project/zone/palette management without a configured
provider.

## Running tests

    pytest -v
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: cross-platform setup and run instructions"
```

---

## Self-Review Notes

- **Spec coverage:** Client/Project/Zone/PaletteEntry/Species/Render data model → Tasks 3, 5. Zone painting/pin geometry → Task 10 (mask rasterization) reads the same `geometry` shape Task 8 persists. Proportion/species validation → Task 4, wired into Task 8. Reference image resolution + fallback flag → Task 9, wired into Task 13. Per-season generation with retry-once → Task 13. Regenerate-a-single-season → supported by Task 14's `seasons` list accepting any subset, not just all four. Persistence per client/project → Tasks 6-8. TDD-first, unit tests with fakes for external calls, a small integration test → Tasks 1-14 each follow red/green/commit, Task 14 is the integration point.
- **Not yet covered (explicitly out of scope per the spec's Non-goals / Open Questions):** a real reference-image provider implementation (web search or dataset API) — `NullReferenceProvider` in Task 14 is a deliberate placeholder *behind an interface*, matching the spec's Open Questions section, not a plan gap; swapping it for a real provider is a follow-up task once a source is chosen. Frontend is explicitly out of scope for this plan.
- **Type consistency check:** `GenerationOrchestrator.generate_for_season(project, zones, season)` signature matches its Task 13 test calls and its Task 14 router usage. `CachingReferenceImageService.get_reference_image(common_name, season)` name and arg order matches across Tasks 9 and 13. `build_mask_overlay(photo_path, zones, output_path)` and `build_prompt(zones, season, missing_species)` signatures match between their defining tasks and their use in Task 13.
