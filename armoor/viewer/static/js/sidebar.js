/**
 * sidebar.js – UI logic: panel toggles, dataset loading, variable/time/depth
 * controls, diagnostics (time series + section), and particle system controls.
 */

import { loadDataset, closeDataset, getMetadata, fetchTileMeta, fetchWind } from "./api.js";
import { ScalarLayerManager } from "./layer.js";
import { ParticleSystem } from "./particles.js";
import { drawLegend } from "./colormapLegend.js";
import { Probe } from "./probe.js";
import { drawTimeseries } from "./timeseries.js";
import { drawSection } from "./section.js";

// Must match viewer.js's MODE_STORAGE_KEY (kept as a literal here to avoid
// a circular import between viewer.js and sidebar.js).
const MODE_STORAGE_KEY = "armoor-viewer-mode";

export class Sidebar {
  constructor(globe) {
    this.globe    = globe;
    this.layerMgr = new ScalarLayerManager(globe);
    this.probe    = new Probe(globe);

    this._datasetId     = null;
    this._metadata      = null;
    this._playTimer     = null;
    this._preloadAbort  = null;   // AbortController for in-progress preload

    // Particle system
    const particleCanvas = document.getElementById("particle-canvas");
    this.particles = new ParticleSystem(particleCanvas, globe);
    this._particlesEnabled = false;

    // Chart panel state
    this._chartMode = null;   // "timeseries" | "section"

    this._inspectHandler = null;   // MapLibre click handler for point inspection
    this._pointMarker    = null;   // dot marker for the last inspected point

    this._bindPanelToggles();
    this._bindDataset();
    this._bindVariable();
    this._bindTimeDepth();
    this._bindDiagnostics();
    this._bindCurrents();
    this._bindChartPanel();
    this._bindProbeBox();
    this._bindRenderModeToggle();

    window.addEventListener("resize", () => {
      const gc = document.getElementById("globe-container");
      this.particles.resize(gc.offsetWidth, gc.offsetHeight);
    });
  }

  // ── Render mode toggle (2D / 3D) ─────────────────────────────────────────

  /** Reflect the currently active render mode in the toggle button state. */
  setRenderMode(mode) {
    document.querySelectorAll("#render-mode-toggle .mode-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mode === mode);
    });
  }

  _bindRenderModeToggle() {
    document.querySelectorAll("#render-mode-toggle .mode-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        window.localStorage.setItem(MODE_STORAGE_KEY, btn.dataset.mode);
        window.location.reload();
      });
    });
  }

  // ── Panel collapsing ──────────────────────────────────────────────────────

  _bindPanelToggles() {
    document.querySelectorAll(".panel-header").forEach((hdr) => {
      hdr.addEventListener("click", () => {
        hdr.closest(".panel").classList.toggle("collapsed");
      });
    });
  }

  // ── Dataset ───────────────────────────────────────────────────────────────

  _bindDataset() {
    document.getElementById("btn-load").addEventListener("click",   () => this._loadDataset());
    document.getElementById("btn-unload").addEventListener("click", () => this._unloadDataset());
  }

  async _loadDataset() {
    const path = document.getElementById("ds-path").value.trim();
    const fmt  = document.getElementById("ds-fmt").value;
    if (!path) { this._status("Please enter a dataset path", "error"); return; }

    this._status("Loading dataset…");
    try {
      const info = await loadDataset(path, fmt, (msg) => this._status(`Loading… ${msg}`));
      this._datasetId = info.id;
      this._metadata  = await getMetadata(info.id);

      this._populateVariableSelect(info.variables);
      this._populateWindVarSelects(info.variables);
      this._updateSliderRanges(info.time_count, info.depth_count);

      document.getElementById("ds-info").textContent =
        `ID: ${info.id.slice(0, 8)}… | ${info.variables.length} vars | ` +
        `${info.time_count} times | ${info.depth_count} depths`;

      this._enableInspect();
      this._status(`Loaded: ${path}`, "ok");
      document.getElementById("panel-variable").classList.remove("collapsed");
      document.getElementById("panel-timedepth").classList.remove("collapsed");
    } catch (err) {
      this._status(`Load error: ${err.message}`, "error");
    }
  }

  async _unloadDataset() {
    if (!this._datasetId) return;
    try {
      await closeDataset(this._datasetId);
      this.layerMgr.remove();
      this.particles.stop();
      this.probe.deactivate();
      this._disableInspect();
      this._hideChart();
      this._datasetId = null;
      this._metadata  = null;
      document.getElementById("ds-info").textContent = "";
      this._status("Dataset unloaded");
    } catch (err) {
      this._status(`Unload error: ${err.message}`, "error");
    }
  }

  // ── Variable ──────────────────────────────────────────────────────────────

  _bindVariable() {
    document.getElementById("btn-render").addEventListener("click", () => this._render());
    document.getElementById("var-opacity").addEventListener("input", (e) => {
      const v = parseFloat(e.target.value);
      document.getElementById("opacity-val").textContent = v.toFixed(2);
      this.layerMgr.setOpacity(v);
    });
  }

  async _render() {
    if (!this._datasetId) { this._status("No dataset loaded", "error"); return; }
    this._status("Rendering…");
    try {
      const params = this._tileParams();
      const { vmin, vmax } = await this.layerMgr.update(
        this._datasetId, params,
        parseFloat(document.getElementById("var-opacity").value),
      );

      document.getElementById("var-vmin").placeholder = vmin.toFixed(4);
      document.getElementById("var-vmax").placeholder = vmax.toFixed(4);

      await drawLegend(
        document.getElementById("legend-canvas"),
        params.colormap, vmin, vmax,
        document.getElementById("legend-vmin"),
        document.getElementById("legend-vmax"),
      );
      this._status("OK", "ok");
    } catch (err) {
      this._status(`Render error: ${err.message}`, "error");
    }
  }

  _tileParams() {
    const variable = document.getElementById("var-select").value;
    const colormap = document.getElementById("var-cmap").value;
    const timeIdx  = parseInt(document.getElementById("time-slider").value, 10);
    const depthIdx = parseInt(document.getElementById("depth-slider").value, 10);
    const vminRaw  = document.getElementById("var-vmin").value.trim();
    const vmaxRaw  = document.getElementById("var-vmax").value.trim();
    const p = { variable, colormap, time_idx: timeIdx, depth_idx: depthIdx };
    if (vminRaw) p.vmin = parseFloat(vminRaw);
    if (vmaxRaw) p.vmax = parseFloat(vmaxRaw);
    return p;
  }

  // ── Time & Depth ──────────────────────────────────────────────────────────

  _bindTimeDepth() {
    const timeSlider  = document.getElementById("time-slider");
    const depthSlider = document.getElementById("depth-slider");

    // Debounce helper – waits 250 ms after the last change before rendering.
    let _debounceTimer = null;
    const scheduleRender = () => {
      clearTimeout(_debounceTimer);
      _debounceTimer = setTimeout(() => this._render(), 250);
    };

    timeSlider.addEventListener("input", () => {
      document.getElementById("time-label").textContent =
        this._timeLabel(parseInt(timeSlider.value, 10));
      if (this._datasetId) scheduleRender();
    });
    depthSlider.addEventListener("input", () => {
      document.getElementById("depth-label").textContent =
        this._depthLabel(parseInt(depthSlider.value, 10));
      if (this._datasetId) {
        // Z level changed → cached frames at the old level are no longer valid.
        this._stopPlay();
        scheduleRender();
      }
    });

    document.getElementById("btn-time-prev").addEventListener("click",  () => this._stepSlider("time-slider", -1));
    document.getElementById("btn-time-next").addEventListener("click",  () => this._stepSlider("time-slider", +1));
    document.getElementById("btn-depth-prev").addEventListener("click", () => this._stepSlider("depth-slider", -1));
    document.getElementById("btn-depth-next").addEventListener("click", () => this._stepSlider("depth-slider", +1));

    document.getElementById("btn-play").addEventListener("click", () => this._startPlay());
    document.getElementById("btn-stop").addEventListener("click", () => this._stopPlay());
    document.getElementById("fps-slider").addEventListener("input", (e) => {
      document.getElementById("fps-val").textContent = e.target.value;
    });
  }

  _stepSlider(id, delta) {
    const s = document.getElementById(id);
    s.value = Math.max(parseInt(s.min), Math.min(parseInt(s.max),
      parseInt(s.value, 10) + delta));
    s.dispatchEvent(new Event("input"));
  }

  _timeLabel(idx) {
    const times = this._metadata?.time_values;
    return times?.[idx] ?? String(idx);
  }

  _depthLabel(idx) {
    return String(idx);
  }

  _startPlay() {
    this._stopPlay();
    if (!this._datasetId) return;

    const timeMax = parseInt(document.getElementById("time-slider").max, 10);
    if (timeMax < 1) { this._status("No time animation: single step", "error"); return; }

    const params    = this._tileParams();
    const timeCount = timeMax + 1;
    const fps       = parseInt(document.getElementById("fps-slider").value, 10);
    const opacity   = parseFloat(document.getElementById("var-opacity").value);

    const btnPlay = document.getElementById("btn-play");
    btnPlay.disabled = true;

    this._preloadAbort = new AbortController();
    const { signal } = this._preloadAbort;

    this._status(`Loading ${timeCount} frames…`);

    this.layerMgr.preloadFrames(
      this._datasetId, params, timeCount,
      (loaded, total) => this._status(`Loading frames… ${loaded} / ${total}`),
      signal,
    ).then(() => {
      if (signal.aborted) return;
      btnPlay.disabled = false;
      this._status("▶ Playing");

      this._playTimer = setInterval(() => {
        const s = document.getElementById("time-slider");
        let v = parseInt(s.value, 10) + 1;
        if (v > parseInt(s.max)) v = 0;
        s.value = v;
        document.getElementById("time-label").textContent = this._timeLabel(v);
        this.layerMgr.showFrame(v, opacity);
      }, 1000 / fps);
    }).catch((err) => {
      if (err.name === "AbortError") return;
      btnPlay.disabled = false;
      this._status(`Preload error: ${err.message}`, "error");
    });
  }

  _stopPlay() {
    if (this._preloadAbort) {
      this._preloadAbort.abort();
      this._preloadAbort = null;
    }
    if (this._playTimer) {
      clearInterval(this._playTimer);
      this._playTimer = null;
    }
    document.getElementById("btn-play").disabled = false;
  }

  // ── Diagnostics ───────────────────────────────────────────────────────────

  _bindDiagnostics() {
    document.getElementById("btn-mode-ts").addEventListener("click",  () => this._activateTsMode());
    document.getElementById("btn-mode-sec").addEventListener("click", () => this._activateSecMode());
    document.getElementById("btn-mode-off").addEventListener("click", () => this._deactivateDiag());
  }

  _activateTsMode() {
    if (!this._datasetId) { this._status("Load a dataset first", "error"); return; }
    this._setDiagMode("timeseries");
    this._status("Click on the field to get a time series…");
    document.getElementById("diag-hint").textContent = "Click on the globe to extract a time series at that point.";

    this.probe.enableTimeseries(async ({ lon, lat }) => {
      const variable = document.getElementById("var-select").value;
      const depthIdx = parseInt(document.getElementById("depth-slider").value, 10);
      this._status("Fetching time series…");
      try {
        const resp = await fetch(
          `/api/datasets/${this._datasetId}/timeseries` +
          `?variable=${encodeURIComponent(variable)}&lon=${lon}&lat=${lat}&depth_idx=${depthIdx}`
        );
        if (!resp.ok) throw new Error((await resp.json()).error);
        const data = await resp.json();
        const currentIdx = parseInt(document.getElementById("time-slider").value, 10);
        this._showChart(
          `Time series – ${variable} @ lon=${lon.toFixed(2)}, lat=${lat.toFixed(2)}, depth=${data.depth_val ?? depthIdx}m`,
          (canvas) => drawTimeseries(canvas, data, currentIdx),
        );
        this._status("OK", "ok");
      } catch (err) {
        this._status(`Time series error: ${err.message}`, "error");
      }
    });
  }

  _activateSecMode() {
    if (!this._datasetId) { this._status("Load a dataset first", "error"); return; }
    this._setDiagMode("section");
    this._status("Click the first point of the section…");
    document.getElementById("diag-hint").textContent = "Click to add waypoints — right-click to finish the section.";

    this.probe.enableSection(async ({ pts }) => {
      const variable = document.getElementById("var-select").value;
      const colormap = document.getElementById("var-cmap").value;
      const timeIdx  = parseInt(document.getElementById("time-slider").value, 10);
      this._status("Fetching section…");
      try {
        const lons = pts.map(p => p.lon).join(",");
        const lats = pts.map(p => p.lat).join(",");
        const resp = await fetch(
          `/api/datasets/${this._datasetId}/section` +
          `?variable=${encodeURIComponent(variable)}` +
          `&lons=${lons}&lats=${lats}&time_idx=${timeIdx}&n_points=150`
        );
        if (!resp.ok) throw new Error((await resp.json()).error);
        const data = await resp.json();
        const p0 = pts[0], pN = pts[pts.length - 1];
        const label = pts.length === 2
          ? `[${p0.lon.toFixed(1)},${p0.lat.toFixed(1)}]→[${pN.lon.toFixed(1)},${pN.lat.toFixed(1)}]`
          : `${pts.length} waypoints`;
        this._showChart(
          `Section – ${variable} (t=${timeIdx})  ${label}`,
          (canvas) => drawSection(canvas, data, colormap),
        );
        this._status("OK", "ok");
        // Keep section mode active for a new section
        this._activateSecMode();
      } catch (err) {
        this._status(`Section error: ${err.message}`, "error");
      }
    });
  }

  _deactivateDiag() {
    this.probe.deactivate();
    this._setDiagMode(null);
    document.getElementById("diag-hint").textContent = "Select a mode, then click on the globe.";
    this._status("armoor viewer");
  }

  _setDiagMode(mode) {
    this._chartMode = mode;
    document.getElementById("btn-mode-ts").classList.toggle("active",  mode === "timeseries");
    document.getElementById("btn-mode-sec").classList.toggle("active", mode === "section");
  }

  // ── Chart panel ───────────────────────────────────────────────────────────

  _bindChartPanel() {
    document.getElementById("chart-close").addEventListener("click", () => {
      this._hideChart();
      this._deactivateDiag();
    });
  }

  _showChart(title, renderFn) {
    document.getElementById("chart-title").textContent = title;
    const panel  = document.getElementById("chart-panel");
    const canvas = document.getElementById("chart-canvas");
    panel.classList.add("visible");
    // Give the browser a frame to lay out the panel before reading offsetWidth
    requestAnimationFrame(() => {
      Promise.resolve(renderFn(canvas)).catch((err) => {
        this._status(`Render error: ${err.message}`, "error");
      });
    });
  }

  _hideChart() {
    document.getElementById("chart-panel").classList.remove("visible");
  }

  // ── Currents / Particles ──────────────────────────────────────────────────

  _bindCurrents() {
    document.getElementById("toggle-particles").addEventListener("change", async (e) => {
      this._particlesEnabled = e.target.checked;
      if (this._particlesEnabled) {
        const gc = document.getElementById("globe-container");
        this.particles.resize(gc.offsetWidth, gc.offsetHeight);
        await this._updateWind();
        this.particles.start();
      } else {
        this.particles.stop();
      }
    });

    document.getElementById("nb-particles").addEventListener("input", (e) => {
      this.particles.nbParticles = parseInt(e.target.value, 10);
      document.getElementById("nb-particles-val").textContent = e.target.value;
      if (this._particlesEnabled) this.particles._initParticles();
    });
    document.getElementById("speed-scale").addEventListener("input", (e) => {
      this.particles.speedScale = parseFloat(e.target.value);
      document.getElementById("speed-scale-val").textContent = e.target.value;
    });
    document.getElementById("trail-opacity").addEventListener("input", (e) => {
      this.particles.trailOpacity = parseFloat(e.target.value);
      document.getElementById("trail-opacity-val").textContent = e.target.value;
    });
  }

  async _updateWind() {
    if (!this._datasetId) return;
    const uVar = document.getElementById("wind-u-var").value;
    const vVar = document.getElementById("wind-v-var").value;
    if (!uVar || !vVar) return;

    const timeIdx  = parseInt(document.getElementById("time-slider").value, 10);
    const depthIdx = parseInt(document.getElementById("depth-slider").value, 10);
    try {
      const grid = await fetchWind(this._datasetId,
        { u_var: uVar, v_var: vVar, time_idx: timeIdx, depth_idx: depthIdx });
      this.particles.setGrid(grid);
    } catch (err) {
      this._status(`Wind error: ${err.message}`, "error");
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  _populateVariableSelect(variables) {
    const sel = document.getElementById("var-select");
    sel.innerHTML = "";
    for (const v of variables) {
      const opt = document.createElement("option");
      opt.value = opt.textContent = v;
      sel.appendChild(opt);
    }
  }

  _populateWindVarSelects(variables) {
    for (const selId of ["wind-u-var", "wind-v-var"]) {
      const sel = document.getElementById(selId);
      sel.innerHTML = "";
      const none = document.createElement("option");
      none.value = ""; none.textContent = "— select —";
      sel.appendChild(none);
      for (const v of variables) {
        const opt = document.createElement("option");
        opt.value = opt.textContent = v;
        if (selId === "wind-u-var" && (v === "u" || v.toLowerCase().includes("uvel"))) opt.selected = true;
        if (selId === "wind-v-var" && (v === "v" || v.toLowerCase().includes("vvel"))) opt.selected = true;
        sel.appendChild(opt);
      }
    }
  }

  _updateSliderRanges(timeCount, depthCount) {
    const ts = document.getElementById("time-slider");
    const ds = document.getElementById("depth-slider");
    ts.max = Math.max(0, timeCount  - 1);
    ds.max = Math.max(0, depthCount - 1);
    ts.value = ds.value = 0;
    document.getElementById("time-label").textContent  = this._timeLabel(0);
    document.getElementById("depth-label").textContent = this._depthLabel(0);
  }

  // ── Point probe ───────────────────────────────────────────────────────────

  _bindProbeBox() {
    document.getElementById("probe-box-close").addEventListener("click", () => {
      document.getElementById("probe-box").hidden = true;
      if (this._pointMarker) { this._pointMarker.remove(); this._pointMarker = null; }
    });
  }

  _enableInspect() {
    if (this._inspectHandler) return;

    this._inspectHandler = async (e) => {
      // Skip when probe mode is active (section / timeseries)
      if (this.probe._mode !== null) return;
      if (!this._datasetId) return;

      const lon = e.lngLat.lng;
      const lat = e.lngLat.lat;

      const variable = document.getElementById("var-select").value;
      const timeIdx  = parseInt(document.getElementById("time-slider").value, 10);
      const depthIdx = parseInt(document.getElementById("depth-slider").value, 10);
      if (!variable) return;

      // Place / replace dot marker at the clicked location.
      if (this._pointMarker) { this._pointMarker.remove(); this._pointMarker = null; }
      const dotEl = document.createElement('div');
      dotEl.style.cssText = 'width:10px;height:10px;border-radius:50%;background:#e94560;border:1.5px solid white;box-shadow:0 0 4px rgba(0,0,0,0.6);pointer-events:none;';
      this._pointMarker = this.globe.addMarker(lon, lat, dotEl);

      try {
        const resp = await fetch(
          `/api/datasets/${this._datasetId}/point` +
          `?variable=${encodeURIComponent(variable)}` +
          `&lon=${lon}&lat=${lat}` +
          `&time_idx=${timeIdx}&depth_idx=${depthIdx}`,
        );
        if (!resp.ok) return;
        const d = await resp.json();
        this._showProbeBox(d);
      } catch (_) { /* silent */ }
    };

    this.globe.map.on('click', this._inspectHandler);
  }

  _disableInspect() {
    if (this._inspectHandler) {
      this.globe.map.off('click', this._inspectHandler);
      this._inspectHandler = null;
    }
    if (this._pointMarker) {
      this._pointMarker.remove();
      this._pointMarker = null;
    }
    document.getElementById("probe-box").hidden = true;
  }

  _showProbeBox(d) {
    const fmt = (v) => {
      if (v === null || v === undefined) return "—";
      if (typeof v === "number") {
        if (Math.abs(v) >= 1000 || (Math.abs(v) < 0.01 && v !== 0)) return v.toExponential(2);
        return v.toFixed(4);
      }
      return String(v);
    };

    const rows = [
      ["variable", d.variable + (d.units ? ` (${d.units})` : "")],
      ["value",    fmt(d.value)],
      ["lon",      fmt(d.lon) + "°"],
      ["lat",      fmt(d.lat) + "°"],
      ["time",     d.time_str ?? String(d.time_idx)],
      ["depth",    d.depth_val != null ? fmt(d.depth_val) + " m" : `z=${d.depth_idx}`],
    ];

    const table = document.getElementById("probe-table");
    table.innerHTML = rows.map(([k, v]) =>
      `<tr><td>${k}</td><td>${v}</td></tr>`,
    ).join("");

    document.getElementById("probe-box").hidden = false;
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  _status(msg, type = "") {
    const bar = document.getElementById("status-bar");
    bar.textContent = msg;
    bar.className   = type;
  }
}
