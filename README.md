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
