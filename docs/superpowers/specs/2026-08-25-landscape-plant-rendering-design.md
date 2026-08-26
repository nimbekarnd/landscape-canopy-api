# Landscape Plant Rendering Tool — Design Spec

Date: 2026-08-25

## Overview

A web app for native/sustainable landscape designers (e.g. permaculture
consultants like Agriformers) that lets a designer upload a client's yard
photo, mark planting zones, assign plant species and proportions to each
zone, and generate photorealistic renders of the yard populated with those
plants across seasons. It replaces "imagine what this will look like" with
an actual before/after image the designer can use during a client
consultation to pitch and iterate on a design live.

## Goals

- Designer can upload a yard photo and mark planting zones (painted regions)
  and/or individual plant pins.
- Designer can build a species/shrub palette and tag each zone with species
  + relative proportions.
- Designer can select which seasons to render; default is all four.
- Generated renders should be visually convincing on three axes: plausible
  placement/geometry, recognizable species appearance, and correct seasonal
  foliage state.
- Designer can regenerate a single season after tweaking a zone's species,
  proportions, or pin placement, without regenerating the others.
- Projects persist per client so a designer can revisit and iterate across
  consultations.

## Non-goals (for this version)

- No homeowner/self-serve mode — designer-operated only.
- No billing, multi-tenant account management, or client-facing portal.
- No custom-trained ML models — generation is orchestrated through an
  existing hosted multimodal image-editing API.
- No procedural/exact geometric compositing (e.g. depth-estimated tree
  placement with rendered cutouts) — placement accuracy comes from
  zone/pin input plus a regenerate-and-nudge loop, not pixel-exact
  guarantees.

## Users

Primary user: a landscape/permaculture designer running the tool during or
after a client site visit, using it as a design and sales-pitch aid.

## Architecture

Three main pieces:

1. **Web app frontend** — designer-facing UI: photo upload, zone-painting
   canvas (draw regions + drop pins), plant palette builder, per-zone
   species tags + proportion sliders, season selector, and a render gallery.
2. **Backend API** — owns persistence (clients, projects, zones, palette,
   season selections, renders) and orchestrates generation: builds the mask
   overlay + reference images + structured prompt per season, calls the
   image-editing model, stores results.
3. **Reference image service** — given a species name, fetches/caches
   realistic reference photos per season (web image search or a plant image
   dataset/API), giving the generation call real visual grounding instead of
   relying on text description alone.

Generation itself is a hosted API call to a multimodal image-editing model
(e.g. Gemini 2.5 Flash Image) — there is no self-hosted ML/GPU
infrastructure to run or manage.

## Data Model

- **Client** — name, contact info, address (optional).
- **Project** — belongs to a Client; holds the original yard photo, creation
  date, status.
- **Zone** — belongs to a Project; a painted region (polygon/mask) or an
  individual pin; has a list of PaletteEntries.
- **PaletteEntry** — belongs to a Zone; a species tag + proportion value
  (0–100%; entries within a zone sum to 100%).
- **Species** — a reusable catalog entry (common name, scientific name);
  shared across the app, not scoped to one project, so a designer's palette
  grows over time.
- **Render** — belongs to a Project; one per generated season; stores the
  output image, the season, and a pointer to the exact Zone/PaletteEntry
  snapshot used to produce it, so a later regenerate-with-different-settings
  doesn't lose traceability of what produced an earlier image.

## Generation Data Flow

1. Designer paints zones and/or drops pins, tags each with species from the
   Palette, sets proportions, and picks seasons (default: all four).
2. Backend resolves reference images for each tagged species: check cache →
   if missing, fetch via the reference image service → cache the result.
3. For each selected season, backend builds a request to the image-edit
   model: original photo + zone mask overlay + reference image crops for
   the season + a structured prompt (species names, per-zone proportions,
   season, placement instructions) → calls the API → stores the result as a
   Render.
4. Designer reviews renders. If a zone or pin needs adjustment, the designer
   nudges it or changes species/proportions and regenerates just the
   affected season(s), not the full set. This regenerate loop is the
   accuracy safety-valve given that placement/proportion are steered by the
   model rather than guaranteed exactly.

## Error Handling

- Image-edit API failure or timeout → retry once, then surface a clear
  per-season failure state in the UI; seasons that succeeded still display.
- Reference image service can't find a photo for a species → fall back to a
  text-only prompt for that species and flag it in the UI so the designer
  knows that species may render less accurately.
- A zone with no species tagged, or proportions that don't sum to 100% →
  block generation for that zone with a validation message rather than
  silently producing a bad render.

## Testing Strategy

API-first, TDD-friendly:

- **Data model + validation** (proportions sum to 100%, a zone requires at
  least one species) — pure unit tests.
- **Reference image service** — unit tests against a mocked fetch client;
  a smaller set of integration tests against the real source, run less
  frequently (network/cost cost).
- **Generation orchestration** — unit tests around request-building (given
  zones/palette/season, does it build the correct payload) with the
  image-edit API call mocked; a small number of real end-to-end tests
  behind a flag, since each real call costs money and time.
- Frontend testing strategy is out of scope for this spec — to be scoped
  separately once the frontend build is planned.

## Open Questions / Future Work

- Exact choice of reference-image source (general web image search vs. a
  dedicated plant image dataset/API) — to be resolved during implementation
  based on licensing and quality.
- Frontend framework and hosting choice — not yet decided; to be scoped in
  the implementation plan.
- Whether Species catalog needs admin curation/moderation once shared across
  designers, or stays freeform.
