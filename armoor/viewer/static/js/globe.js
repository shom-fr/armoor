/**
 * globe.js – iTowns GlobeView wrapper.
 *
 * Public interface compatible with probe.js, particles.js, layer.js and sidebar.js.
 */

import * as itowns from '/js/vendor/itowns.js';
import * as THREE  from 'three';

const GEO  = 'EPSG:4326';
const ECEF = 'EPSG:4978';

// Earth mean radius (m) – used for raycasting; WGS84 ellipsoid flattening
// is negligible for interactive picking.
const R_EARTH = 6371000;

export class Globe {
  constructor(containerId) {
    const container = document.getElementById(containerId);
    container.style.position = 'relative';

    // ── iTowns GlobeView ────────────────────────────────────────────────────
    this._view = new itowns.GlobeView(
      container,
      new itowns.Coordinates(GEO, 0, 20),
      { renderer: { antialias: true } },
    );

    // ── Basemap layer via local WMS proxy ───────────────────────────────────
    this._view.addLayer(new itowns.ColorLayer('basemap', {
      source: new itowns.WMSSource({
        url:     `${window.location.origin}/basemap/wms`,
        name:    'basemap',
        crs:     GEO,
        version: '1.3.0',
        format:  'image/jpeg',
        extent:  new itowns.Extent(GEO, -180, 180, -90, 90),
      }),
    }));

    // ── Scalar data overlay (Three.js tessellated mesh) ─────────────────────
    this._dataMesh    = null;
    this._dataBboxKey = null;

    // ── DOM overlay for markers ─────────────────────────────────────────────
    this._overlayEl = document.createElement('div');
    Object.assign(this._overlayEl.style, {
      position: 'absolute', top: '0', left: '0',
      width: '100%', height: '100%',
      pointerEvents: 'none', overflow: 'hidden',
    });
    container.appendChild(this._overlayEl);
    this._markerList = [];

    // ── SVG overlay for lines ────────────────────────────────────────────────
    this._svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    Object.assign(this._svgEl.style, {
      position: 'absolute', top: '0', left: '0',
      width: '100%', height: '100%',
      pointerEvents: 'none', overflow: 'hidden',
    });
    container.appendChild(this._svgEl);
    this._svgLineMap = new Map();  // id → { gEl, gcLL, color }

    // ── Polygon draw state ──────────────────────────────────────────────────
    this._polyPts    = [];
    this._polyClickH = null;
    this._polyDblH   = null;

    // ── Event bridge ────────────────────────────────────────────────────────
    this._handlers = {};

    this._view.domElement.addEventListener('click', e => {
      const c = this._pickCoordsAt(e.clientX, e.clientY);
      if (!c) return;
      this._emit('click', {
        lngLat:         { lng: c.longitude, lat: c.latitude },
        preventDefault: () => {},
      });
    });

    // GlobeControls fires 'change' during interaction and 'end' when done.
    this._view.controls.addEventListener('change', () => {
      this._repositionMarkers();
      this._repositionSvgLines();
      this._emit('move');
    });
    this._view.controls.addEventListener('end', () => {
      this._repositionMarkers();
      this._repositionSvgLines();
      this._emit('moveend');
    });

    // Shim providing MapLibre-compatible API for probe.js / particles.js
    this.map = this._shim();
  }

  // ── Raycasting ────────────────────────────────────────────────────────────

  _pickCoordsAt(clientX, clientY) {
    const rect = this._view.domElement.getBoundingClientRect();
    const nx   = ((clientX - rect.left) / rect.width)  * 2 - 1;
    const ny   = -((clientY - rect.top)  / rect.height) * 2 + 1;

    const rc = new THREE.Raycaster();
    rc.setFromCamera(new THREE.Vector2(nx, ny), this._view.camera.camera3D);

    const hit = new THREE.Vector3();
    if (!rc.ray.intersectSphere(new THREE.Sphere(new THREE.Vector3(), R_EARTH), hit)) {
      return null;
    }

    return new itowns.Coordinates(ECEF, hit.x, hit.y, hit.z).as(GEO);
  }

  // ── Scalar data layer ─────────────────────────────────────────────────────

  /**
   * @param {string}  imageUrl
   * @param {Object}  bbox          – { west, east, south, north } in degrees
   * @param {number}  [opacity]
   * @param {Object|null} [vertexGrid]  – { lons, lats, nx, ny } from /api/.../grid
   *   When provided, the mesh follows the actual geographic grid coordinates
   *   instead of a uniform rectangle, fixing misalignment on curvilinear grids.
   */
  setScalarLayer(imageUrl, bbox, opacity = 0.85, vertexGrid = null) {
    const key = vertexGrid
      ? `vg:${vertexGrid.nx}x${vertexGrid.ny}:${vertexGrid.lons[0][0].toFixed(4)},${vertexGrid.lats[0][0].toFixed(4)}`
      : `${bbox.west},${bbox.east},${bbox.south},${bbox.north}`;
    if (!this._dataMesh || this._dataBboxKey !== key) {
      this._removeDataMesh();
      this._dataMesh    = this._buildOverlayMesh(vertexGrid ?? bbox, opacity);
      this._dataBboxKey = key;
      this._view.scene.add(this._dataMesh);
    }
    this._dataMesh.material.opacity = opacity;

    new THREE.TextureLoader().load(imageUrl, tex => {
      if (!this._dataMesh) return;
      const old = this._dataMesh.material.map;
      tex.flipY = false;
      this._dataMesh.material.map = tex;
      this._dataMesh.material.needsUpdate = true;
      old?.dispose();
      this._view.notifyChange();
    });
  }

  removeScalarLayer() { this._removeDataMesh(); }

  setScalarOpacity(o) {
    if (!this._dataMesh) return;
    this._dataMesh.material.opacity = o;
    this._dataMesh.material.needsUpdate = true;
    this._view.notifyChange();
  }

  _removeDataMesh() {
    if (!this._dataMesh) return;
    this._dataMesh.material.map?.dispose();
    this._dataMesh.material.dispose();
    this._dataMesh.geometry.dispose();
    this._view.scene.remove(this._dataMesh);
    this._dataMesh    = null;
    this._dataBboxKey = null;
  }

  // Tessellated mesh following the globe surface at 200 m altitude.
  // depthTest:false + renderOrder:999 ensure it composites above the basemap.
  // alphaTest:0.01 discards land pixels (alpha=0) without alpha-blending artefacts.
  //
  // spec is either:
  //   { west, east, south, north }              – uniform rectangular bbox
  //   { lons, lats, nx, ny }                    – actual curvilinear grid coords
  // The vertex grid form avoids misalignment on NEMO curvilinear grids.
  _buildOverlayMesh(spec, opacity) {
    const isGrid = Array.isArray(spec.lons);
    const NX = isGrid ? spec.nx : 64;
    const NY = isGrid ? spec.ny : 32;
    const verts = [], uvs = [], idx = [];

    // WGS84 constants for geo→ECEF conversion (avoids slow Coordinates objects)
    const A  = 6378137.0;
    const E2 = 0.00669437999014;  // first eccentricity squared
    const ALT = 5000;             // metres above ellipsoid (clear of basemap tiles)

    for (let j = 0; j <= NY; j++) {
      for (let i = 0; i <= NX; i++) {
        const lon = isGrid
          ? spec.lons[j][i] * Math.PI / 180
          : (spec.west  + (i / NX) * (spec.east  - spec.west)) * Math.PI / 180;
        const lat = isGrid
          ? spec.lats[j][i] * Math.PI / 180
          : (spec.south + (j / NY) * (spec.north - spec.south)) * Math.PI / 180;
        uvs.push(i / NX, 1 - j / NY);
        const N   = A / Math.sqrt(1 - E2 * Math.sin(lat) ** 2);
        const R   = N + ALT;
        const clat = Math.cos(lat);
        verts.push(R * clat * Math.cos(lon), R * clat * Math.sin(lon),
                   (N * (1 - E2) + ALT) * Math.sin(lat));
      }
    }
    for (let j = 0; j < NY; j++) {
      for (let i = 0; i < NX; i++) {
        const a = j * (NX + 1) + i;
        const b = a + 1, c = a + NX + 1, d = c + 1;
        idx.push(a, b, c,  b, d, c);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    geo.setAttribute('uv',       new THREE.Float32BufferAttribute(uvs,   2));
    geo.setIndex(idx);

    const mat = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity,
      alphaTest:  0.01,
      depthWrite: false,
      side:       THREE.FrontSide,
    });

    return new THREE.Mesh(geo, mat);
  }

  // ── Camera / navigation ───────────────────────────────────────────────────

  flyToBbox(bbox) {
    const lon  = (bbox.west  + bbox.east)  / 2;
    const lat  = (bbox.south + bbox.north) / 2;
    const span = Math.max(bbox.east - bbox.west, bbox.north - bbox.south);
    // range: camera-to-target distance in metres; empirical fit
    const range = Math.max(100000, 6e6 * span / 180 * 1.5);

    itowns.CameraUtils.transformCameraToLookAtTarget(
      this._view, this._view.camera.camera3D, {
        coord:   new itowns.Coordinates(GEO, lon, lat),
        range,
        tilt:    90,
        heading: 0,
      },
    );
  }

  // ── Polygon draw ──────────────────────────────────────────────────────────

  enablePolygonDraw(callback) {
    this.disablePolygonDraw();
    this._polyPts = [];

    this._polyClickH = e => {
      const c = this._pickCoordsAt(e.clientX, e.clientY);
      if (!c) return;
      this._polyPts.push([c.longitude, c.latitude]);
      this._updatePolyLine();
    };
    this._polyDblH = () => {
      if (this._polyPts.length >= 3) callback([...this._polyPts]);
      this.disablePolygonDraw();
    };
    this._view.domElement.addEventListener('click',    this._polyClickH);
    this._view.domElement.addEventListener('dblclick', this._polyDblH);
    this._view.domElement.style.cursor = 'crosshair';
  }

  disablePolygonDraw() {
    if (this._polyClickH) {
      this._view.domElement.removeEventListener('click',    this._polyClickH);
      this._view.domElement.removeEventListener('dblclick', this._polyDblH);
      this._polyClickH = this._polyDblH = null;
    }
    this._view.domElement.style.cursor = '';
    this._removeLine('__poly__');
    this._polyPts = [];
  }

  // ── Markers ───────────────────────────────────────────────────────────────

  addMarker(lon, lat, element) {
    const wrapper = document.createElement('div');
    Object.assign(wrapper.style, {
      position: 'absolute', transform: 'translate(-50%,-50%)',
      pointerEvents: 'none',
    });
    wrapper.appendChild(element);
    this._overlayEl.appendChild(wrapper);

    const entry = { el: wrapper, lon, lat };
    this._markerList.push(entry);
    this._repositionMarker(entry);

    return { remove: () => {
      wrapper.remove();
      this._markerList = this._markerList.filter(m => m !== entry);
    }};
  }

  // ── Coordinate projection (geographic → screen pixel) ────────────────────

  project([lon, lat]) {
    const ecef = new itowns.Coordinates(GEO, lon, lat, 0).as(ECEF);
    const pt   = new THREE.Vector3(ecef.x, ecef.y, ecef.z);

    // Hide points on the back hemisphere (surface normal away from camera).
    const camPos = this._view.camera.camera3D.position;
    if (pt.dot(camPos) - pt.lengthSq() < 0) return { x: -9999, y: -9999 };

    pt.project(this._view.camera.camera3D);
    const w = this._view.domElement.clientWidth;
    const h = this._view.domElement.clientHeight;
    return { x: (pt.x + 1) / 2 * w, y: -(pt.y - 1) / 2 * h };
  }

  getCenter() {
    const rect = this._view.domElement.getBoundingClientRect();
    const c = this._pickCoordsAt(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return c ? { lng: c.longitude, lat: c.latitude } : { lng: 0, lat: 0 };
  }

  get domElement() {
    return this._view.domElement;
  }

  // ── Event helpers ─────────────────────────────────────────────────────────

  on(ev, h)  { (this._handlers[ev] ??= []).push(h); }
  off(ev, h) {
    if (this._handlers[ev])
      this._handlers[ev] = this._handlers[ev].filter(x => x !== h);
  }

  // ── Private ───────────────────────────────────────────────────────────────

  _emit(ev, arg) { this._handlers[ev]?.forEach(h => h(arg)); }

  _repositionMarkers() {
    for (const m of this._markerList) this._repositionMarker(m);
  }

  _repositionMarker({ el, lon, lat }) {
    const { x, y } = this.project([lon, lat]);
    if (x < -500 || y < -500) { el.style.display = 'none'; return; }
    el.style.display = '';
    el.style.left    = `${x}px`;
    el.style.top     = `${y}px`;
  }

  _setLine(id, lonLatPairs, color = '#ffffff') {
    this._removeLine(id);
    if (lonLatPairs.length < 2) return;

    // Interpolate in lon/lat to follow the globe surface (great-circle approx.).
    const SEG = 32;
    const gcLL = [];
    for (let i = 0; i < lonLatPairs.length - 1; i++) {
      const [lo1, la1] = lonLatPairs[i];
      const [lo2, la2] = lonLatPairs[i + 1];
      for (let j = 0; j < SEG; j++) {
        gcLL.push([lo1 + (lo2 - lo1) * j / SEG, la1 + (la2 - la1) * j / SEG]);
      }
    }
    gcLL.push(lonLatPairs[lonLatPairs.length - 1]);

    const gEl = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    this._svgEl.appendChild(gEl);

    const entry = { gEl, gcLL, color };
    this._svgLineMap.set(id, entry);
    this._repositionSvgLine(entry);
  }

  _removeLine(id) {
    const e = this._svgLineMap.get(id);
    if (!e) return;
    e.gEl.remove();
    this._svgLineMap.delete(id);
  }

  _repositionSvgLines() {
    for (const entry of this._svgLineMap.values()) this._repositionSvgLine(entry);
  }

  _repositionSvgLine({ gEl, gcLL, color }) {
    gEl.innerHTML = '';
    // Project all points; split into visible segments on back-hemisphere gaps.
    const projected = gcLL.map(([lo, la]) => this.project([lo, la]));
    let seg = [];

    const flush = () => {
      if (seg.length >= 2) {
        const pts = seg.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
        const mkPoly = (stroke, width) => {
          const el = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
          el.setAttribute('points', pts);
          el.setAttribute('stroke', stroke);
          el.setAttribute('stroke-width', width);
          el.setAttribute('fill', 'none');
          el.setAttribute('stroke-linecap', 'round');
          el.setAttribute('stroke-linejoin', 'round');
          return el;
        };
        gEl.appendChild(mkPoly('white', 4));
        gEl.appendChild(mkPoly(color,   2));
      }
      seg = [];
    };

    for (const p of projected) {
      if (p.x < -500 || p.y < -500) { flush(); } else { seg.push(p); }
    }
    flush();
  }

  _updatePolyLine() {
    if (this._polyPts.length >= 2)
      this._setLine('__poly__', [...this._polyPts, this._polyPts[0]], '#e94560');
  }

  // ── Shim: MapLibre-compatible API ─────────────────────────────────────────

  _shim() {
    const g = this, sources = new Map(), layerSrcs = new Map();
    return {
      on:            (ev, h) => g.on(ev, h),
      off:           (ev, h) => g.off(ev, h),
      project:       ll      => g.project(ll),
      getCenter:     ()      => g.getCenter(),
      isStyleLoaded: ()      => true,
      getCanvas:     ()      => g._view.domElement,

      addSource(id, spec) { sources.set(id, spec); },
      getSource(id) {
        const s = sources.get(id);
        if (!s) return undefined;
        return { setData(data) {
          s.data = data;
          const c = data?.geometry?.coordinates;
          if (c?.length >= 2) g._setLine(id, c, '#53c0f0');
        }};
      },
      addLayer(spec) {
        const c = sources.get(spec.source)?.data?.geometry?.coordinates;
        if (c?.length >= 2)
          g._setLine(spec.id, c, spec.paint?.['line-color'] ?? '#ffffff');
        layerSrcs.set(spec.id, spec.source);
      },
      getLayer(id)     { return layerSrcs.has(id) ? { id } : undefined; },
      removeLayer(id)  { g._removeLine(id); layerSrcs.delete(id); },
      removeSource(id) { sources.delete(id); },
      setPaintProperty(_, prop, val) {
        if (prop === 'raster-opacity') g.setScalarOpacity(val);
      },
      fitBounds(b) {
        g.flyToBbox({ west: b[0][0], south: b[0][1], east: b[1][0], north: b[1][1] });
      },
    };
  }
}
