/**
 * viewer.js – Entry point. Resolves the render mode (2D Leaflet vs 3D
 * iTowns), lazily loads only the corresponding bundle, then bootstraps the
 * map/globe and the sidebar.
 */

import { fetchConfig } from "./api.js";
import { Sidebar } from "./sidebar.js";

export const MODE_STORAGE_KEY = "armoor-viewer-mode";

/** True if the browser can create a WebGL2 rendering context. */
export function supportsWebGL2() {
  try {
    const canvas = document.createElement("canvas");
    return !!(window.WebGL2RenderingContext && canvas.getContext("webgl2"));
  } catch (_) {
    return false;
  }
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload  = () => resolve();
    s.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(s);
  });
}

function loadStylesheet(href) {
  const link = document.createElement("link");
  link.rel  = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

/**
 * Determine the requested render mode, before capability resolution.
 *
 * Priority: URL query param (session override) > localStorage (persisted
 * user choice from the sidebar toggle) > server default (deployment-wide,
 * e.g. forced "2d" on a headless HPC node) > "auto".
 */
function getRequestedMode(serverDefault) {
  const qs = new URLSearchParams(window.location.search).get("mode");
  const stored = window.localStorage.getItem(MODE_STORAGE_KEY);
  return qs || stored || serverDefault || "auto";
}

/**
 * Resolve the requested mode to a concrete, safe-to-use mode.
 *
 * "2d" is always honoured as-is. "3d" and "auto" both require a WebGL2
 * capability check: iTowns throws during GlobeView construction when
 * WebGL2 is unavailable (see globe.js), so an explicit "3d" request must
 * still fall back to "2d" rather than crashing the bootstrap.
 */
function resolveRenderMode(requested) {
  if (requested === "2d") return "2d";
  return supportsWebGL2() ? "3d" : "2d";
}

async function createView(mode) {
  if (mode === "3d") {
    const { Globe } = await import("./globe.js");
    return new Globe("globe-viewer");
  }
  await loadScript("/js/vendor/leaflet.js");
  loadStylesheet("/css/vendor/leaflet.css");
  const { PlanarMap } = await import("./planarMap.js");
  return new PlanarMap("globe-viewer");
}

document.addEventListener("DOMContentLoaded", async () => {
  let serverDefault = "auto";
  try {
    ({ render_mode: serverDefault } = await fetchConfig());
  } catch (_) {
    // Server unreachable / old version without /api/config — fall back to auto.
  }

  const requested = getRequestedMode(serverDefault);
  const mode = resolveRenderMode(requested);

  if (requested === "3d" && mode !== "3d") {
    document.getElementById("status-bar").textContent =
      "WebGL2 unavailable — falling back to 2D mode";
  }

  // ── View (2D Leaflet or 3D globe) ───────────────────────────────────────
  const view = await createView(mode);

  // ── Sidebar ──────────────────────────────────────────────────────────────
  const sidebar = new Sidebar(view);   // eslint-disable-line no-unused-vars
  sidebar.setRenderMode(mode);

  // ── Resize particle canvas to match container ──────────────────────────
  const gc = document.getElementById("globe-container");
  const pc = document.getElementById("particle-canvas");
  const resize = () => {
    pc.width  = gc.offsetWidth;
    pc.height = gc.offsetHeight;
  };
  resize();
  window.addEventListener("resize", resize);
});
