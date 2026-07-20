/**
 * probe.js – Globe interaction modes: point click (time series) and
 * multi-point section definition.
 *
 * Section: left-click to add waypoints, right-click to finalise.
 */

export class Probe {
  /**
   * @param {import("./globe.js").Globe} globe
   */
  constructor(globe) {
    this.globe         = globe;
    this._mode         = null;
    this._handler      = null;
    this._contextMenuH = null;

    this._pts                  = [];  // waypoints collected in section mode
    this._sectionEntities      = [];  // active dots (cleared on _deactivate)
    this._savedSectionEntities = [];  // persisted dots + line after finalise
  }

  // ── Public API ────────────────────────────────────────────────────────────

  /**
   * Switch to time-series click mode.
   * @param {Function} onPick  – called with { lon, lat }
   */
  enableTimeseries(onPick) {
    this._deactivate();
    this._mode = "timeseries";
    this._setupHandler((lonLat) => {
      this._clearEntities();
      this._addDot(lonLat, "#e94560");
      onPick(lonLat);
    });
  }

  /**
   * Switch to multi-point section mode.
   * Left-click adds a waypoint; right-click finalises (≥ 2 points required).
   *
   * @param {Function} onSection  – called with { pts: [{lon, lat}, …] }
   */
  enableSection(onSection) {
    this._deactivate();
    this._mode = "section";

    const clickH = (e) => {
      const lonLat = { lon: e.lngLat.lng, lat: e.lngLat.lat };
      if (this._pts.length === 0) this._clearSavedSection();
      this._pts.push(lonLat);
      this._addDot(lonLat, this._pts.length === 1 ? "#e94560" : "#53c0f0");
      this._updateWipLine();
      this._setStatus(this._pts.length === 1
        ? "Click to add waypoints — right-click to finish"
        : `${this._pts.length} points — right-click to finish the section`);
    };

    const contextMenuH = (e) => {
      e.preventDefault();  // suppress browser context menu
      if (this._pts.length < 2) return;

      // Move dots to saved slot; replace WIP line with final line.
      this._clearWipLine();
      const finalId = `section-line-${Date.now()}`;
      this._addFinalLine(finalId);
      this._savedSectionEntities = [
        ...this._sectionEntities,
        { _type: 'layer', id: finalId },
      ];
      this._sectionEntities = [];

      // Detach handlers.
      this.globe.map.off('click', clickH);
      this.globe.domElement.removeEventListener('contextmenu', contextMenuH);
      this._handler      = null;
      this._contextMenuH = null;
      this._mode         = null;

      const pts = [...this._pts];
      this._pts = [];
      onSection({ pts });
    };

    this.globe.map.on('click', clickH);
    this.globe.domElement.addEventListener('contextmenu', contextMenuH);
    this._handler      = clickH;
    this._contextMenuH = contextMenuH;
  }

  /** Remove all probe entities and event handlers. */
  deactivate() {
    this._deactivate();
    this._clearSavedSection();
  }

  // ── Internal ──────────────────────────────────────────────────────────────

  _setupHandler(callback) {
    const handler = (e) => callback({ lon: e.lngLat.lng, lat: e.lngLat.lat });
    this.globe.map.on('click', handler);
    this._handler = handler;
  }

  _deactivate() {
    if (this._handler) {
      this.globe.map.off('click', this._handler);
      this._handler = null;
    }
    if (this._contextMenuH) {
      this.globe.domElement.removeEventListener('contextmenu', this._contextMenuH);
      this._contextMenuH = null;
    }
    this._clearEntities();
    this._clearWipLine();
    this._mode = null;
    this._pts  = [];
  }

  _addDot({ lon, lat }, color) {
    const el = document.createElement('div');
    el.style.cssText = [
      'width:12px', 'height:12px', 'border-radius:50%',
      `background:${color}`, 'border:1.5px solid white',
      'box-shadow:0 0 4px rgba(0,0,0,0.6)', 'pointer-events:none',
    ].join(';');
    const marker = this.globe.addMarker(lon, lat, el);
    this._sectionEntities.push(marker);
  }

  _updateWipLine() {
    if (this._pts.length < 2) return;
    const id = '__section_wip__';
    const coords = this._pts.map(p => [p.lon, p.lat]);
    this.globe.map.addSource(id, {
      type: 'geojson',
      data: { type: 'Feature', geometry: { type: 'LineString', coordinates: coords } },
    });
    this.globe.map.addLayer({
      id, type: 'line', source: id,
      paint: { 'line-color': '#53c0f0', 'line-width': 2 },
    });
  }

  _clearWipLine() {
    const id = '__section_wip__';
    if (this.globe.map.getLayer(id))  this.globe.map.removeLayer(id);
    if (this.globe.map.getSource(id)) this.globe.map.removeSource(id);
  }

  _addFinalLine(id) {
    const coords = this._pts.map(p => [p.lon, p.lat]);
    this.globe.map.addSource(id, {
      type: 'geojson',
      data: { type: 'Feature', geometry: { type: 'LineString', coordinates: coords } },
    });
    this.globe.map.addLayer({
      id, type: 'line', source: id,
      paint: { 'line-color': '#53c0f0', 'line-width': 2 },
    });
  }

  _clearEntities() {
    for (const e of this._sectionEntities) {
      if (typeof e.remove === 'function') {
        e.remove();
      } else if (e._type === 'layer') {
        if (this.globe.map.getLayer(e.id))  this.globe.map.removeLayer(e.id);
        if (this.globe.map.getSource(e.id)) this.globe.map.removeSource(e.id);
      }
    }
    this._sectionEntities = [];
  }

  _clearSavedSection() {
    for (const e of this._savedSectionEntities) {
      if (typeof e.remove === 'function') {
        e.remove();
      } else if (e._type === 'layer') {
        if (this.globe.map.getLayer(e.id))  this.globe.map.removeLayer(e.id);
        if (this.globe.map.getSource(e.id)) this.globe.map.removeSource(e.id);
      }
    }
    this._savedSectionEntities = [];
  }

  _setStatus(msg) {
    const bar = document.getElementById("status-bar");
    if (bar) bar.textContent = msg;
  }
}
