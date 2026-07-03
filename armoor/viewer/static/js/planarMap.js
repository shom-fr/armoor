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
    // Two mutually-exclusive rendering paths:
    //  - `_overlay` (plain L.imageOverlay): used only when no vertex grid is
    //    available for the dataset (no lon/lat coordinates at all).
    //  - mesh canvas: used whenever a vertex grid is available — the normal
    //    case. Native ocean-model grids (HYCOM, NEMO, …) are curvilinear or
    //    non-uniformly spaced, so stretching the tile image linearly across
    //    a straight bbox misplaces every pixel except at the four corners.
    //    This mirrors globe.js's `_buildOverlayMesh` (which tessellates a
    //    WebGL mesh from the same /api/.../grid vertices) using canvas
    //    triangle texture-mapping instead, since Leaflet has no built-in
    //    way to warp an image overlay onto an arbitrary quad mesh.
    this._overlay = null;
    this._meshGrid    = null;
    this._meshImg     = null;
    this._meshOpacity = 0.85;
    this._meshRAF     = null;
    this._meshCanvas  = this._createMeshCanvas(containerId);
    this._meshCtx     = this._meshCanvas.getContext('2d');

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

    const scheduleMeshRedraw = () => this._scheduleMeshRedraw();
    this._map.on('move zoom resize', scheduleMeshRedraw);

    // Shim providing MapLibre-compatible API for probe.js / particles.js
    this.map = this._shim();
  }

  // ── Scalar data layer ─────────────────────────────────────────────────────

  /**
   * @param {string}  imageUrl
   * @param {Object}  bbox          – { west, east, south, north } in degrees
   * @param {number}  [opacity]
   * @param {Object|null} [vertexGrid]  – { lons, lats, nx, ny } from
   *   /api/.../grid. When available, the tile is warped onto the true
   *   per-vertex geographic grid (see class-level comment); otherwise it
   *   falls back to a plain rectangular L.imageOverlay.
   */
  setScalarLayer(imageUrl, bbox, opacity = 0.85, vertexGrid = null) {
    this._meshOpacity = opacity;

    if (vertexGrid && Array.isArray(vertexGrid.lons) && vertexGrid.lons.length > 1) {
      if (this._overlay) {
        this._map.removeLayer(this._overlay);
        this._overlay = null;
      }
      this._meshGrid = vertexGrid;
      const img = new Image();
      img.onload = () => {
        if (this._meshImg !== img) return; // superseded by a newer load
        this._scheduleMeshRedraw();
      };
      this._meshImg = img;
      img.src = imageUrl;
      return;
    }

    // Fallback: dataset has no lon/lat coordinates to build a grid from.
    this._clearMesh();
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
    if (this._overlay) {
      this._map.removeLayer(this._overlay);
      this._overlay = null;
    }
    this._clearMesh();
  }

  setScalarOpacity(o) {
    this._meshOpacity = o;
    this._overlay?.setOpacity(o);
    if (this._meshGrid) this._scheduleMeshRedraw();
  }

  // ── Mesh canvas (curvilinear-grid-aware scalar overlay) ───────────────────

  _createMeshCanvas(containerId) {
    const host = document.getElementById(containerId);
    const canvas = document.createElement('canvas');
    Object.assign(canvas.style, {
      position:      'absolute',
      top:           '0',
      left:          '0',
      width:         '100%',
      height:        '100%',
      pointerEvents: 'none',
      zIndex:        '450',
    });
    host.parentNode.insertBefore(canvas, host.nextSibling);
    return canvas;
  }

  _clearMesh() {
    this._meshGrid = null;
    this._meshImg  = null;
    if (this._meshRAF) {
      cancelAnimationFrame(this._meshRAF);
      this._meshRAF = null;
    }
    this._meshCtx.clearRect(0, 0, this._meshCanvas.width, this._meshCanvas.height);
  }

  _scheduleMeshRedraw() {
    if (this._meshRAF) return;
    this._meshRAF = requestAnimationFrame(() => {
      this._meshRAF = null;
      this._redrawMesh();
    });
  }

  _redrawMesh() {
    const canvas = this._meshCanvas;
    const size = this._map.getSize();
    if (canvas.width !== size.x || canvas.height !== size.y) {
      canvas.width  = size.x;
      canvas.height = size.y;
    }
    const ctx = this._meshCtx;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const grid = this._meshGrid;
    const img  = this._meshImg;
    if (!grid || !img || !img.complete || !img.naturalWidth) return;

    const { lons, lats, nx, ny } = grid;
    const iw = img.naturalWidth;
    const ih = img.naturalHeight;

    // Screen-space position of every grid vertex, computed once per redraw.
    const pts = new Array(ny + 1);
    for (let j = 0; j <= ny; j++) {
      const row = new Array(nx + 1);
      for (let i = 0; i <= nx; i++) {
        row[i] = this._map.latLngToContainerPoint([lats[j][i], lons[j][i]]);
      }
      pts[j] = row;
    }

    ctx.globalAlpha = this._meshOpacity;

    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const p00 = pts[j][i],     p10 = pts[j][i + 1];
        const p01 = pts[j + 1][i], p11 = pts[j + 1][i + 1];

        // Source pixel coords: the tile image is south-up flipped server
        // side (row 0 = north), so v grows southward — see
        // rendering/raster.py::slice_to_png's np.flipud.
        const u0 = (i / nx) * iw,       u1 = ((i + 1) / nx) * iw;
        const v0 = (1 - j / ny) * ih,   v1 = (1 - (j + 1) / ny) * ih;

        _drawTexturedTriangle(ctx, img,
          u0, v0, u1, v0, u0, v1,
          p00.x, p00.y, p10.x, p10.y, p01.x, p01.y);
        _drawTexturedTriangle(ctx, img,
          u1, v0, u1, v1, u0, v1,
          p10.x, p10.y, p11.x, p11.y, p01.x, p01.y);
      }
    }

    ctx.globalAlpha = 1;
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

// ---------------------------------------------------------------------------

/**
 * Draw the portion of `img` inside source triangle (sx0,sy0)-(sx1,sy1)-
 * (sx2,sy2) warped onto destination triangle (dx0,dy0)-(dx1,dy1)-(dx2,dy2),
 * via the unique affine transform mapping one triangle onto the other
 * (closed-form solution of the 3-point-correspondence linear system).
 */
function _drawTexturedTriangle(
  ctx, img,
  sx0, sy0, sx1, sy1, sx2, sy2,
  dx0, dy0, dx1, dy1, dx2, dy2,
) {
  const denom = sx0 * (sy1 - sy2) + sx1 * (sy2 - sy0) + sx2 * (sy0 - sy1);
  if (Math.abs(denom) < 1e-9) return;

  const a = (dx0 * (sy1 - sy2) + dx1 * (sy2 - sy0) + dx2 * (sy0 - sy1)) / denom;
  const b = (dy0 * (sy1 - sy2) + dy1 * (sy2 - sy0) + dy2 * (sy0 - sy1)) / denom;
  const c = (dx0 * (sx2 - sx1) + dx1 * (sx0 - sx2) + dx2 * (sx1 - sx0)) / denom;
  const d = (dy0 * (sx2 - sx1) + dy1 * (sx0 - sx2) + dy2 * (sx1 - sx0)) / denom;
  const e = (dx0 * (sx1 * sy2 - sx2 * sy1) + dx1 * (sx2 * sy0 - sx0 * sy2) + dx2 * (sx0 * sy1 - sx1 * sy0)) / denom;
  const f = (dy0 * (sx1 * sy2 - sx2 * sy1) + dy1 * (sx2 * sy0 - sx0 * sy2) + dy2 * (sx0 * sy1 - sx1 * sy0)) / denom;

  ctx.save();
  ctx.beginPath();
  ctx.moveTo(dx0, dy0);
  ctx.lineTo(dx1, dy1);
  ctx.lineTo(dx2, dy2);
  ctx.closePath();
  ctx.clip();
  ctx.transform(a, b, c, d, e, f);
  ctx.drawImage(img, 0, 0);
  ctx.restore();
}
