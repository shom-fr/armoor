/**
 * planarMap.js – Leaflet 2D planisphere wrapper.
 *
 * Public interface compatible with probe.js, particles.js, layer.js and
 * sidebar.js (same contract as globe.js's Globe class). Used instead of the
 * iTowns 3D globe on machines without WebGL2 (see viewer.js render-mode
 * resolution).
 *
 * Leaflet is loaded globally via a plain <script> tag (window.L) — it is
 * only fetched when the 2D mode is actually selected, see viewer.js.
 */

const L = window.L;

// Matches the equirectangular tile pyramid served by
// armoor/viewer/api/basemap.py's tile_geo() endpoint (2^(z+1) cols x 2^z
// rows) — the built-in L.CRS.EPSG4326 uses the same grid.
const BASEMAP_URL = '/basemap/geo/{z}/{x}/{y}.png';

export class PlanarMap {
  constructor(containerId) {
    this._map = L.map(containerId, {
      crs: L.CRS.EPSG4326,
      center: [20, 0],
      zoom: 2,
      minZoom: 1,
      maxZoom: 8,
    });

    L.tileLayer(BASEMAP_URL, { maxZoom: 8 }).addTo(this._map);

    // ── Scalar data overlay ───────────────────────────────────────────────
    this._overlay = null;

    // ── Markers ───────────────────────────────────────────────────────────
    this._markerLayer = L.layerGroup().addTo(this._map);

    // ── GeoJSON line sources/layers (mirrors globe.js's MapLibre shim) ─────
    this._sources = new Map();   // id -> geojson-like spec
    this._lines   = new Map();   // id -> L.Polyline

    // ── Polygon draw state ───────────────────────────────────────────────
    this._polyPts    = [];
    this._polyClickH = null;
    this._polyDblH   = null;

    // ── Event bridge ─────────────────────────────────────────────────────
    this._handlers = {};

    this._map.on('click', (e) => {
      this._emit('click', {
        lngLat:         { lng: e.latlng.lng, lat: e.latlng.lat },
        preventDefault: () => {},
      });
    });
    this._map.on('move',    () => this._emit('move'));
    this._map.on('moveend', () => this._emit('moveend'));

    // Shim providing MapLibre-compatible API for probe.js / particles.js
    this.map = this._shim();
  }

  // ── Scalar data layer ─────────────────────────────────────────────────────

  /**
   * @param {string}  imageUrl
   * @param {Object}  bbox          – { west, east, south, north } in degrees
   * @param {number}  [opacity]
   * @param {Object|null} [_vertexGrid]  – ignored in 2D: the server already
   *   resamples curvilinear grids onto a regular lat/lon raster (see
   *   rendering/raster.py::slice_to_png), so a plain image overlay is
   *   always correctly aligned — no tessellation needed as in the 3D globe.
   */
  setScalarLayer(imageUrl, bbox, opacity = 0.85, _vertexGrid = null) {
    const bounds = L.latLngBounds([bbox.south, bbox.west], [bbox.north, bbox.east]);
    if (!this._overlay) {
      this._overlay = L.imageOverlay(imageUrl, bounds, { opacity }).addTo(this._map);
    } else {
      this._overlay.setUrl(imageUrl);
      this._overlay.setBounds(bounds);
      this._overlay.setOpacity(opacity);
    }
  }

  removeScalarLayer() {
    if (!this._overlay) return;
    this._map.removeLayer(this._overlay);
    this._overlay = null;
  }

  setScalarOpacity(o) {
    this._overlay?.setOpacity(o);
  }

  // ── Camera / navigation ───────────────────────────────────────────────────

  flyToBbox(bbox) {
    this._map.fitBounds([[bbox.south, bbox.west], [bbox.north, bbox.east]]);
  }

  // ── Polygon draw ──────────────────────────────────────────────────────────

  enablePolygonDraw(callback) {
    this.disablePolygonDraw();
    this._polyPts = [];

    this._polyClickH = (e) => {
      this._polyPts.push([e.latlng.lng, e.latlng.lat]);
      this._updatePolyLine();
    };
    this._polyDblH = () => {
      if (this._polyPts.length >= 3) callback([...this._polyPts]);
      this.disablePolygonDraw();
    };
    this._map.on('click',    this._polyClickH);
    this._map.on('dblclick', this._polyDblH);
    this._map.getContainer().style.cursor = 'crosshair';
  }

  disablePolygonDraw() {
    if (this._polyClickH) {
      this._map.off('click',    this._polyClickH);
      this._map.off('dblclick', this._polyDblH);
      this._polyClickH = this._polyDblH = null;
    }
    this._map.getContainer().style.cursor = '';
    this._removeLine('__poly__');
    this._polyPts = [];
  }

  _updatePolyLine() {
    if (this._polyPts.length >= 2)
      this._setLine('__poly__', [...this._polyPts, this._polyPts[0]], '#e94560');
  }

  // ── Markers ───────────────────────────────────────────────────────────────

  addMarker(lon, lat, element) {
    const icon = L.divIcon({ html: element, className: '', iconSize: null });
    const marker = L.marker([lat, lon], { icon, interactive: false }).addTo(this._markerLayer);
    return { remove: () => this._markerLayer.removeLayer(marker) };
  }

  // ── Coordinate projection (geographic → screen pixel) ────────────────────

  project([lon, lat]) {
    const p = this._map.latLngToContainerPoint([lat, lon]);
    return { x: p.x, y: p.y };
  }

  getCenter() {
    const c = this._map.getCenter();
    return { lng: c.lng, lat: c.lat };
  }

  get domElement() {
    return this._map.getContainer();
  }

  // ── Event helpers ─────────────────────────────────────────────────────────

  on(ev, h)  { (this._handlers[ev] ??= []).push(h); }
  off(ev, h) {
    if (this._handlers[ev])
      this._handlers[ev] = this._handlers[ev].filter(x => x !== h);
  }

  // ── Private ───────────────────────────────────────────────────────────────

  _emit(ev, arg) { this._handlers[ev]?.forEach(h => h(arg)); }

  _setLine(id, lonLatPairs, color = '#ffffff') {
    this._removeLine(id);
    if (lonLatPairs.length < 2) return;
    const latlngs = lonLatPairs.map(([lon, lat]) => [lat, lon]);
    const line = L.polyline(latlngs, { color, weight: 2 }).addTo(this._map);
    this._lines.set(id, line);
  }

  _removeLine(id) {
    const line = this._lines.get(id);
    if (!line) return;
    this._map.removeLayer(line);
    this._lines.delete(id);
  }

  // ── Shim: MapLibre-compatible API ─────────────────────────────────────────

  _shim() {
    const g = this;
    return {
      on:            (ev, h) => g.on(ev, h),
      off:           (ev, h) => g.off(ev, h),
      project:       ll      => g.project(ll),
      getCenter:     ()      => g.getCenter(),
      isStyleLoaded: ()      => true,
      getCanvas:     ()      => g.domElement,

      addSource(id, spec) { g._sources.set(id, spec); },
      getSource(id) {
        const s = g._sources.get(id);
        if (!s) return undefined;
        return { setData(data) {
          s.data = data;
          const c = data?.geometry?.coordinates;
          if (c?.length >= 2) g._setLine(id, c, '#53c0f0');
        }};
      },
      addLayer(spec) {
        const c = g._sources.get(spec.source)?.data?.geometry?.coordinates;
        if (c?.length >= 2)
          g._setLine(spec.id, c, spec.paint?.['line-color'] ?? '#ffffff');
      },
      getLayer(id)     { return g._lines.has(id) ? { id } : undefined; },
      removeLayer(id)  { g._removeLine(id); },
      removeSource(id) { g._sources.delete(id); },
      setPaintProperty(_, prop, val) {
        if (prop === 'raster-opacity') g.setScalarOpacity(val);
      },
      fitBounds(b) {
        g.flyToBbox({ west: b[0][0], south: b[0][1], east: b[1][0], north: b[1][1] });
      },
    };
  }
}
