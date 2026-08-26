const state = {
  clientId: null,
  projectId: null,
  species: [],
  zones: [],
  editingZoneId: null,
  drawMode: null, // "region" | "pin" | null
  points: [],
};

async function api(path, opts) {
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ? JSON.stringify(body.detail) : JSON.stringify(body);
    } catch (_) {
      // response wasn't JSON; keep statusText
    }
    throw new Error(`${resp.status}: ${detail}`);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function setError(elId, err) {
  document.getElementById(elId).textContent = err ? err.message || String(err) : "";
}

// ---------- Clients ----------

async function loadClients() {
  const clients = await api("/clients");
  const select = document.getElementById("clientSelect");
  const previous = select.value;
  select.innerHTML = clients
    .map((c) => `<option value="${c.id}">${c.name}</option>`)
    .join("");
  if (clients.some((c) => c.id === previous)) {
    select.value = previous;
  }
  onClientSelected();
}

async function createClient() {
  setError("clientError", null);
  const name = document.getElementById("clientName").value.trim();
  if (!name) return;
  try {
    await api("/clients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    document.getElementById("clientName").value = "";
    await loadClients();
  } catch (err) {
    setError("clientError", err);
  }
}

function onClientSelected() {
  state.clientId = document.getElementById("clientSelect").value || null;
  loadProjectsForClient();
}

// ---------- Species ----------

async function loadSpecies() {
  state.species = await api("/species");
  document.getElementById("speciesList").textContent = state.species
    .map((s) => s.common_name)
    .join(", ") || "(none yet)";
  const select = document.getElementById("paletteSpeciesSelect");
  select.innerHTML = state.species
    .map((s) => `<option value="${s.id}">${s.common_name}</option>`)
    .join("");
}

async function createSpecies() {
  const common_name = document.getElementById("speciesCommonName").value.trim();
  const scientific_name = document.getElementById("speciesScientificName").value.trim() || null;
  if (!common_name) return;
  await api("/species", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ common_name, scientific_name }),
  });
  document.getElementById("speciesCommonName").value = "";
  document.getElementById("speciesScientificName").value = "";
  await loadSpecies();
}

// ---------- Projects ----------

async function loadProjectsForClient() {
  const select = document.getElementById("projectSelect");
  const listEl = document.getElementById("projectList");
  if (!state.clientId) {
    select.innerHTML = "";
    listEl.innerHTML = "";
    state.projectId = null;
    return;
  }
  const projects = await api(`/clients/${state.clientId}/projects`);
  const previous = select.value;
  select.innerHTML = projects
    .map((p) => `<option value="${p.id}">${p.id.slice(0, 8)} (${p.status})</option>`)
    .join("");
  if (projects.some((p) => p.id === previous)) {
    select.value = previous;
  }
  listEl.innerHTML = projects
    .map((p) => `<div class="list-item">${p.id} — ${p.status}<br><img class="thumb" src="/projects/${p.id}/photo" /></div>`)
    .join("");
  onProjectSelected();
}

async function createProject() {
  setError("projectError", null);
  const fileInput = document.getElementById("photoInput");
  if (!state.clientId) {
    setError("projectError", new Error("Create/select a client first."));
    return;
  }
  if (!fileInput.files.length) {
    setError("projectError", new Error("Choose a photo first."));
    return;
  }
  const formData = new FormData();
  formData.append("photo", fileInput.files[0]);
  try {
    await api(`/clients/${state.clientId}/projects`, { method: "POST", body: formData });
    fileInput.value = "";
    await loadProjectsForClient();
  } catch (err) {
    setError("projectError", err);
  }
}

function onProjectSelected() {
  state.projectId = document.getElementById("projectSelect").value || null;
  cancelZoneDraw();
  if (state.projectId) {
    document.getElementById("zonePhoto").src = `/projects/${state.projectId}/photo`;
  } else {
    document.getElementById("zonePhoto").removeAttribute("src");
  }
  loadZones();
  loadRenders();
}

// ---------- Zone drawing ----------

const canvas = () => document.getElementById("zoneCanvas");
const photoImg = () => document.getElementById("zonePhoto");

photoImg().addEventListener("load", () => {
  const img = photoImg();
  const c = canvas();
  c.width = img.clientWidth;
  c.height = img.clientHeight;
  redrawCanvas();
});

// state.points is always stored in the photo's ORIGINAL (natural) pixel
// coordinates, matching what the backend's mask overlay expects when it
// opens the full-resolution photo — not the on-screen display size, which
// can be scaled down by the `max-width` on #zonePhoto. These two helpers
// convert between natural coordinates (storage) and display coordinates
// (drawing) so clicks land in the right spot on any photo size.
function displayScale() {
  const img = photoImg();
  return {
    x: (img.naturalWidth || 1) / (img.clientWidth || 1),
    y: (img.naturalHeight || 1) / (img.clientHeight || 1),
  };
}
function toDisplayPoint([x, y]) {
  const s = displayScale();
  return [x / s.x, y / s.y];
}
function toNaturalPoint(dispX, dispY) {
  const s = displayScale();
  return [dispX * s.x, dispY * s.y];
}

function redrawCanvas() {
  const c = canvas();
  const ctx = c.getContext("2d");
  ctx.clearRect(0, 0, c.width, c.height);
  if (!state.points.length) return;
  const displayPoints = state.points.map(toDisplayPoint);
  ctx.fillStyle = "rgba(255,0,0,0.9)";
  ctx.strokeStyle = "rgba(255,0,0,0.9)";
  if (state.drawMode === "pin") {
    const [x, y] = displayPoints[0];
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, 2 * Math.PI);
    ctx.fill();
    return;
  }
  ctx.beginPath();
  displayPoints.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
  ctx.stroke();
  displayPoints.forEach(([x, y]) => {
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, 2 * Math.PI);
    ctx.fill();
  });
}

canvas().addEventListener("click", (evt) => {
  if (!state.drawMode) return;
  const rect = canvas().getBoundingClientRect();
  const [x, y] = toNaturalPoint(evt.clientX - rect.left, evt.clientY - rect.top);
  if (state.drawMode === "pin") {
    state.points = [[x, y]];
    redrawCanvas();
    openPaletteBuilder();
    return;
  }
  state.points.push([x, y]);
  redrawCanvas();
  document.getElementById("finishRegionBtn").style.display =
    state.points.length >= 3 ? "inline-block" : "none";
});

function startNewZone(kind = "region") {
  if (!state.projectId) {
    alert("Select a project first.");
    return;
  }
  state.editingZoneId = null;
  state.drawMode = kind;
  state.points = [];
  document.getElementById("finishRegionBtn").style.display = "none";
  document.getElementById("paletteBuilder").style.display = "none";
  document.getElementById("zoneEditorHint").textContent =
    kind === "pin" ? "Click once on the photo to place a pin." : "Click 3+ points, then Finish region.";
  redrawCanvas();
}

function finishRegion() {
  if (state.points.length < 3) return;
  openPaletteBuilder();
}

function cancelZoneDraw() {
  state.drawMode = null;
  state.points = [];
  state.editingZoneId = null;
  document.getElementById("finishRegionBtn").style.display = "none";
  document.getElementById("paletteBuilder").style.display = "none";
  document.getElementById("paletteRows").innerHTML = "";
  document.getElementById("zoneEditorHint").textContent = 'Click "New zone" to draw on the photo below.';
  redrawCanvas();
}

function openPaletteBuilder() {
  document.getElementById("paletteBuilder").style.display = "block";
  document.getElementById("zoneEditorHint").textContent = "Add species/proportions below, then Save zone.";
}

function currentPaletteRows() {
  return [...document.querySelectorAll("#paletteRows .palette-row")].map((row) => ({
    species_id: row.dataset.speciesId,
    proportion: parseFloat(row.dataset.proportion),
  }));
}

function addPaletteRow() {
  const speciesId = document.getElementById("paletteSpeciesSelect").value;
  const proportion = parseFloat(document.getElementById("paletteProportion").value);
  if (!speciesId || Number.isNaN(proportion)) return;
  const species = state.species.find((s) => s.id === speciesId);
  const row = document.createElement("div");
  row.className = "palette-row";
  row.dataset.speciesId = speciesId;
  row.dataset.proportion = String(proportion);
  row.innerHTML = `<span>${species ? species.common_name : speciesId} — ${proportion}%</span> <button onclick="this.parentElement.remove()">remove</button>`;
  document.getElementById("paletteRows").appendChild(row);
  document.getElementById("paletteProportion").value = "";
}

async function saveZone() {
  setError("zoneError", null);
  const paletteEntries = currentPaletteRows();
  const geometry =
    state.drawMode === "pin" ? { point: state.points[0] } : { points: state.points };
  const payload = { kind: state.drawMode, geometry, palette_entries: paletteEntries };
  try {
    if (state.editingZoneId) {
      await api(`/projects/${state.projectId}/zones/${state.editingZoneId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      await api(`/projects/${state.projectId}/zones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
    cancelZoneDraw();
    await loadZones();
  } catch (err) {
    setError("zoneError", err);
  }
}

async function loadZones() {
  const listEl = document.getElementById("zoneList");
  if (!state.projectId) {
    listEl.innerHTML = "";
    return;
  }
  state.zones = await api(`/projects/${state.projectId}/zones`);
  listEl.innerHTML = state.zones
    .map((z) => {
      const palette = z.palette_entries
        .map((e) => {
          const sp = state.species.find((s) => s.id === e.species_id);
          return `${sp ? sp.common_name : e.species_id} (${e.proportion}%)`;
        })
        .join(", ");
      return `<div class="list-item">
        <strong>${z.kind}</strong> — ${palette || "(no palette)"}
        <div class="row">
          <button onclick="editZone('${z.id}')">Edit palette</button>
          <button onclick="deleteZone('${z.id}')">Delete</button>
        </div>
      </div>`;
    })
    .join("") || "<p class='muted'>No zones yet.</p>";
}

function editZone(zoneId) {
  const zone = state.zones.find((z) => z.id === zoneId);
  if (!zone) return;
  state.editingZoneId = zoneId;
  state.drawMode = zone.kind;
  state.points = zone.kind === "pin" ? [zone.geometry.point] : zone.geometry.points;
  document.getElementById("paletteRows").innerHTML = "";
  zone.palette_entries.forEach((e) => {
    const species = state.species.find((s) => s.id === e.species_id);
    const row = document.createElement("div");
    row.className = "palette-row";
    row.dataset.speciesId = e.species_id;
    row.dataset.proportion = String(e.proportion);
    row.innerHTML = `<span>${species ? species.common_name : e.species_id} — ${e.proportion}%</span> <button onclick="this.parentElement.remove()">remove</button>`;
    document.getElementById("paletteRows").appendChild(row);
  });
  document.getElementById("zoneEditorHint").textContent =
    "Editing this zone's palette (geometry unchanged). Save zone to PATCH it.";
  openPaletteBuilder();
  redrawCanvas();
}

async function deleteZone(zoneId) {
  if (!confirm("Delete this zone?")) return;
  await api(`/projects/${state.projectId}/zones/${zoneId}`, { method: "DELETE" });
  await loadZones();
}

// ---------- Renders ----------

async function generateRenders() {
  setError("renderError", null);
  if (!state.projectId) {
    setError("renderError", new Error("Select a project first."));
    return;
  }
  const seasons = [...document.querySelectorAll(".season-cb:checked")].map((cb) => cb.value);
  try {
    await api(`/projects/${state.projectId}/renders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seasons }),
    });
    await loadRenders();
  } catch (err) {
    setError("renderError", err);
  }
}

async function loadRenders() {
  const listEl = document.getElementById("renderList");
  if (!state.projectId) {
    listEl.innerHTML = "";
    return;
  }
  const renders = await api(`/projects/${state.projectId}/renders`);
  listEl.innerHTML = renders
    .map((r) => {
      const img = r.status === "succeeded" ? `<img class="thumb" src="/renders/${r.id}/image" />` : "";
      const err = r.error ? `<div class="error">${r.error}</div>` : "";
      return `<div class="list-item"><strong>${r.season}</strong> — ${r.status}${img}${err}</div>`;
    })
    .join("") || "<p class='muted'>No renders yet.</p>";
}

// ---------- Init ----------

loadClients();
loadSpecies();
