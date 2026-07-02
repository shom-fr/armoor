/**
 * api.js – Thin wrappers around fetch() for the armoor viewer Flask API.
 */

const BASE = "";   // same origin

async function apiFetch(url, options = {}) {
  const resp = await fetch(BASE + url, options);
  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      msg = body.error || msg;
    } catch (_) { /* ignore */ }
    throw new Error(msg);
  }
  return resp;
}

// ── Config ────────────────────────────────────────────────────────────────

/**
 * Fetch server-side frontend configuration (currently just the default
 * render mode: "auto" / "2d" / "3d").
 */
export async function fetchConfig() {
  const resp = await apiFetch("/api/config");
  return resp.json();
}

// ── Datasets ─────────────────────────────────────────────────────────────

export async function loadDataset(path, fmt = "zarr", onProgress) {
  const resp = await apiFetch("/api/datasets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, fmt }),
  });
  const init = await resp.json();

  // Poll until the background load job finishes.
  const { job_id } = init;
  for (;;) {
    await new Promise(r => setTimeout(r, 1500));
    const sr = await apiFetch(`/api/datasets/jobs/${job_id}`);
    const job = await sr.json();
    if (job.status === "error") throw new Error(job.error);
    if (job.status === "ready") return job;
    onProgress?.(job.message ?? "Loading…");
  }
}

export async function listDatasets() {
  const resp = await apiFetch("/api/datasets");
  return resp.json();
}

export async function closeDataset(id) {
  const resp = await apiFetch(`/api/datasets/${id}`, { method: "DELETE" });
  return resp.json();
}

// ── Metadata ──────────────────────────────────────────────────────────────

export async function getMetadata(id) {
  const resp = await apiFetch(`/api/datasets/${id}/metadata`);
  return resp.json();
}

// ── Tiles ─────────────────────────────────────────────────────────────────

/**
 * Build the URL for a scalar tile (PNG).
 *
 * @param {string}  id         - Dataset ID
 * @param {Object}  params
 * @param {string}  params.variable
 * @param {number}  params.time_idx
 * @param {number}  [params.depth_idx]
 * @param {string}  [params.colormap]
 * @param {number}  [params.vmin]
 * @param {number}  [params.vmax]
 * @param {number}  [params.width]
 * @param {number}  [params.height]
 * @returns {string} Full URL with query string
 */
export function tileUrl(id, params) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) qs.set(k, v);
  }
  return `/api/datasets/${id}/tile?${qs}`;
}

export async function fetchTileMeta(id, params, signal) {
  const url = tileUrl(id, params);
  const resp = await apiFetch(url, signal ? { signal } : {});
  return {
    blob: await resp.blob(),
    bbox: {
      west:  parseFloat(resp.headers.get("X-Bbox-West")),
      south: parseFloat(resp.headers.get("X-Bbox-South")),
      east:  parseFloat(resp.headers.get("X-Bbox-East")),
      north: parseFloat(resp.headers.get("X-Bbox-North")),
    },
    vmin: parseFloat(resp.headers.get("X-Vmin")),
    vmax: parseFloat(resp.headers.get("X-Vmax")),
  };
}

// ── Grid mesh ─────────────────────────────────────────────────────────────

/**
 * Fetch the geographic vertex grid for the scalar overlay mesh.
 *
 * @param {string} id
 * @param {number} [nx=64]
 * @param {number} [ny=32]
 * @returns {{ lons: number[][], lats: number[][], nx: number, ny: number }}
 */
export async function fetchGrid(id, nx = 64, ny = 32) {
  const resp = await apiFetch(`/api/datasets/${id}/grid?nx=${nx}&ny=${ny}`);
  return resp.json();
}

// ── Wind ──────────────────────────────────────────────────────────────────

/**
 * Fetch the u/v wind grid JSON.
 *
 * @param {string} id
 * @param {Object} params  – { u_var, v_var, time_idx, depth_idx, nx, ny }
 */
export async function fetchWind(id, params) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) qs.set(k, v);
  }
  const resp = await apiFetch(`/api/datasets/${id}/wind?${qs}`);
  return resp.json();
}

// ── Operations ────────────────────────────────────────────────────────────

/**
 * Apply an armoor operation to a dataset.
 *
 * @param {string} id
 * @param {string} operation   – e.g. "filter", "interp_time", …
 * @param {Object} params      – operation-specific parameters
 * @returns {Object}           – { new_id, … }
 */
export async function applyOperation(id, operation, params) {
  const resp = await apiFetch(`/api/datasets/${id}/operations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operation, params }),
  });
  return resp.json();
}
