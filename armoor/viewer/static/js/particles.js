/**
 * particles.js – Windy-style particle animation on a canvas overlay.
 *
 * The <canvas> is transparent and positioned absolutely above the globe
 * canvas (pointer-events: none), so globe interaction is not affected.
 *
 * Algorithm:
 *   1. Each animation frame: fade existing trails using elapsed real time
 *      (consistent fade rate regardless of FPS).
 *   2. Interpolate (u, v) at each particle's (lon, lat).
 *      – For native curvilinear grids: bucket-hash spatial index +
 *        bilinear interpolation within the enclosing cell.
 *      – For regular grids (legacy): direct bilinear on a regular array.
 *   3. Advance position using actual elapsed time (consistent speed).
 *   4. Convert (lon, lat) → screen pixel via globe.map.project().
 *   5. Draw a short line segment coloured by speed.
 *   6. Reset aged-out or out-of-domain particles randomly in the domain.
 */

export class ParticleSystem {
  /**
   * @param {HTMLCanvasElement}           canvas   – overlay canvas
   * @param {import("./globe.js").Globe}  globe    – globe instance
   */
  constructor(canvas, globe) {
    this.canvas    = canvas;
    this.globe     = globe;
    this.ctx       = canvas.getContext("2d");
    this._grid     = null;
    this._particles = [];
    this._animId   = null;
    this._running  = false;
    this._lastTime = null;
    this._spatialIndex = null;

    // Tunable parameters
    this.nbParticles  = 3000;
    this.speedScale   = 5.0;   // degrees/s per m/s
    this.trailOpacity = 0.92;  // per-frame fade at 60 fps reference
    this.maxAge       = 120;   // frames (at 60 fps reference)

    this._onMapMove = () => {
      this._clear();
      for (const p of this._particles) { p.xPrev = null; p.yPrev = null; }
    };
    globe.map.on('move', this._onMapMove);
  }

  destroy() {
    this.stop();
    this.globe.map.off('move', this._onMapMove);
  }

  // ── Public API ────────────────────────────────────────────────────────────

  setGrid(grid) {
    this._grid = grid;
    this._spatialIndex = null;
    if (grid && grid.type === "native") {
      this._buildSpatialIndex();
    }
    this._clear();
    this._initParticles();
  }

  start() {
    if (this._running) return;
    this._clear();
    this._lastTime = null;
    this._running  = true;
    this._animId   = requestAnimationFrame((t) => this._loop(t));
  }

  stop() {
    this._running = false;
    if (this._animId) {
      cancelAnimationFrame(this._animId);
      this._animId = null;
    }
    this._lastTime = null;
    this._clear();
  }

  resize(w, h) {
    this.canvas.width  = w;
    this.canvas.height = h;
  }

  // ── Internal ──────────────────────────────────────────────────────────────

  _initParticles() {
    if (!this._grid) return;
    const { lon_min, lon_max, lat_min, lat_max } = this._grid;
    this._particles = Array.from({ length: this.nbParticles }, () =>
      this._randomParticle(lon_min, lon_max, lat_min, lat_max),
    );
  }

  _randomParticle(lon_min, lon_max, lat_min, lat_max) {
    // Rejection sampling: prefer positions where |u|+|v| > 0 (ocean cells).
    // Up to 30 tries avoids stationary particles accumulating over land.
    let lon, lat;
    for (let t = 0; t < 30; t++) {
      lon = lon_min + Math.random() * (lon_max - lon_min);
      lat = lat_min + Math.random() * (lat_max - lat_min);
      const [u, v] = this._interpolate(lon, lat);
      if (Math.abs(u) + Math.abs(v) > 1e-6) break;
    }
    return { lon, lat, age: Math.floor(Math.random() * this.maxAge), xPrev: null, yPrev: null };
  }

  _loop(now) {
    if (!this._running) return;
    this._step(now);
    this._animId = requestAnimationFrame((t) => this._loop(t));
  }

  _step(now) {
    if (!this._grid) return;

    // Elapsed time in ms since last frame; capped to avoid large jumps
    // (e.g. after the tab was hidden).
    const elapsed = (this._lastTime != null)
      ? Math.min(now - this._lastTime, 100)
      : 16.67;
    this._lastTime = now;

    // Number of 60-fps reference frames elapsed.
    const nFrames = elapsed / 16.67;

    const { canvas, ctx } = this;
    const W = canvas.width;
    const H = canvas.height;

    // Fade trails proportionally to elapsed time so the visual decay rate
    // is the same regardless of actual FPS.
    const fadeFactor = Math.pow(this.trailOpacity, nFrames);
    ctx.globalCompositeOperation = "destination-in";
    ctx.fillStyle = `rgba(0,0,0,${fadeFactor})`;
    ctx.fillRect(0, 0, W, H);
    ctx.globalCompositeOperation = "source-over";

    const { lon_min, lon_max, lat_min, lat_max } = this._grid;
    const dt = elapsed / 1000;  // seconds

    for (const p of this._particles) {
      const [u, v] = this._interpolate(p.lon, p.lat);
      const speed  = Math.sqrt(u * u + v * v);

      // Immediately recycle particles on land or in the boundary margin.
      if (speed < 1e-6) {
        Object.assign(p, this._randomParticle(lon_min, lon_max, lat_min, lat_max));
        continue;
      }

      const newLon = p.lon + dt * u * this.speedScale;
      const newLat = p.lat + dt * v * this.speedScale;

      const screenPos = this.globe.map.project([p.lon, p.lat]);
      const inView = screenPos.x > -50 && screenPos.x < W + 50 &&
                     screenPos.y > -50 && screenPos.y < H + 50;

      if (inView && p.xPrev !== null) {
        ctx.strokeStyle = _speedColor(speed);
        ctx.lineWidth   = 1.2;
        ctx.beginPath();
        ctx.moveTo(p.xPrev, p.yPrev);
        ctx.lineTo(screenPos.x, screenPos.y);
        ctx.stroke();
      }

      p.xPrev = inView ? screenPos.x : null;
      p.yPrev = inView ? screenPos.y : null;
      p.lon   = newLon;
      p.lat   = newLat;
      p.age  += nFrames;  // age in 60-fps reference frames

      if (
        p.age > this.maxAge ||
        p.lon < lon_min || p.lon > lon_max ||
        p.lat < lat_min || p.lat > lat_max
      ) {
        Object.assign(p, this._randomParticle(lon_min, lon_max, lat_min, lat_max));
      }
    }
  }

  _clear() {
    const { canvas, ctx } = this;
    ctx.globalCompositeOperation = "source-over";
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  // ── Interpolation dispatch ────────────────────────────────────────────────

  _interpolate(lon, lat) {
    if (this._grid && this._grid.type === "native") {
      return this._interpolateNative(lon, lat);
    }
    return this._interpolateRegular(lon, lat);
  }

  // ── Regular-grid interpolation (legacy fallback) ──────────────────────────

  _interpolateRegular(lon, lat) {
    const { u: uGrid, v: vGrid, lon_min, lon_max, lat_min, lat_max, nx, ny } = this._grid;

    const cx = (lon - lon_min) / (lon_max - lon_min) * (nx - 1);
    const cy = (lat - lat_min) / (lat_max - lat_min) * (ny - 1);

    const x0 = Math.max(0, Math.min(nx - 2, Math.floor(cx)));
    const y0 = Math.max(0, Math.min(ny - 2, Math.floor(cy)));
    const x1 = x0 + 1;
    const y1 = y0 + 1;

    const tx = cx - x0;
    const ty = cy - y0;

    return [
      _bilerp(uGrid[y0][x0], uGrid[y0][x1], uGrid[y1][x0], uGrid[y1][x1], tx, ty),
      _bilerp(vGrid[y0][x0], vGrid[y0][x1], vGrid[y1][x0], vGrid[y1][x1], tx, ty),
    ];
  }

  // ── Native curvilinear-grid interpolation ─────────────────────────────────

  /**
   * Build a bucket-hash spatial index over all native grid points.
   * Each point (j, i) is stored in the bucket that covers its (lon, lat).
   * Lookup then searches only the 3×3 neighbourhood of the query bucket.
   */
  _buildSpatialIndex() {
    const { lon: lonG, lat: latG, ny, nx,
            lon_min, lon_max, lat_min, lat_max } = this._grid;
    const NB = 64;
    const buckets = new Array(NB * NB).fill(null).map(() => []);
    const dlon = lon_max - lon_min || 1;
    const dlat = lat_max - lat_min || 1;

    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const bx = Math.min(NB - 1, Math.max(0,
          Math.floor((lonG[j][i] - lon_min) / dlon * NB)));
        const by = Math.min(NB - 1, Math.max(0,
          Math.floor((latG[j][i] - lat_min) / dlat * NB)));
        buckets[by * NB + bx].push(j * nx + i);
      }
    }

    this._spatialIndex = { buckets, NB, nx, dlon, dlat };
  }

  /**
   * Interpolate (u, v) at (qlon, qlat) on the native curvilinear grid.
   *
   * Steps:
   *   1. Find the nearest grid point (j*, i*) via the bucket index.
   *   2. Test the four cells that share (j*, i*) as a corner.
   *   3. For each cell, solve the 2×2 linearised inverse mapping to get
   *      local coordinates (s, t).  Pick the cell whose (s,t) is closest
   *      to [0,1]².
   *   4. Bilinearly interpolate u and v within that cell.
   */
  _interpolateNative(qlon, qlat) {
    const { u: uG, v: vG, lon: lonG, lat: latG, ny, nx,
            lon_min, lon_max, lat_min, lat_max } = this._grid;
    const { buckets, NB, dlon, dlat } = this._spatialIndex;

    const bx0 = Math.min(NB - 1, Math.max(0,
      Math.floor((qlon - lon_min) / dlon * NB)));
    const by0 = Math.min(NB - 1, Math.max(0,
      Math.floor((qlat - lat_min) / dlat * NB)));

    // Find nearest grid point by scanning a 3×3 neighbourhood of buckets
    let bestD2 = Infinity, bestJ = 0, bestI = 0;
    for (let db = -1; db <= 1; db++) {
      for (let da = -1; da <= 1; da++) {
        const bx = bx0 + da, by = by0 + db;
        if (bx < 0 || bx >= NB || by < 0 || by >= NB) continue;
        for (const flat of buckets[by * NB + bx]) {
          const j = (flat / nx) | 0, i = flat % nx;
          const dx = lonG[j][i] - qlon, dy = latG[j][i] - qlat;
          const d2 = dx * dx + dy * dy;
          if (d2 < bestD2) { bestD2 = d2; bestJ = j; bestI = i; }
        }
      }
    }

    // Retire particles within the boundary margin — open-boundary cells have
    // non-physical prescribed values that produce visible "wall" artifacts.
    const MARGIN = 3;
    if (bestJ < MARGIN || bestJ >= ny - MARGIN ||
        bestI < MARGIN || bestI >= nx - MARGIN) {
      return [0, 0];
    }

    // Try the four cells that share (bestJ, bestI) as a corner
    let bestU = uG[bestJ][bestI], bestV = vG[bestJ][bestI];
    let bestErr = Infinity;

    for (const [jc, ic] of [
      [bestJ - 1, bestI - 1],
      [bestJ - 1, bestI],
      [bestJ,     bestI - 1],
      [bestJ,     bestI],
    ]) {
      if (jc < 0 || ic < 0 || jc + 1 >= ny || ic + 1 >= nx) continue;

      const lon00 = lonG[jc    ][ic    ], lat00 = latG[jc    ][ic    ];
      const lon10 = lonG[jc    ][ic + 1], lat10 = latG[jc    ][ic + 1];
      const lon01 = lonG[jc + 1][ic    ], lat01 = latG[jc + 1][ic    ];
      const lon11 = lonG[jc + 1][ic + 1], lat11 = latG[jc + 1][ic + 1];

      // Linearised inverse mapping: solve
      //   (qlon - lon00) = s*(lon10 - lon00) + t*(lon01 - lon00)
      //   (qlat - lat00) = s*(lat10 - lat00) + t*(lat01 - lat00)
      const diLon = lon10 - lon00, diLat = lat10 - lat00;
      const djLon = lon01 - lon00, djLat = lat01 - lat00;
      const det = diLon * djLat - diLat * djLon;
      if (Math.abs(det) < 1e-12) continue;

      const dx = qlon - lon00, dy = qlat - lat00;
      const s = (dx * djLat - dy * djLon) / det;
      const t = (diLon * dy - diLat * dx) / det;

      // Penalise solutions outside [0,1]² to prefer the enclosing cell
      const sc = Math.max(0, Math.min(1, s));
      const tc = Math.max(0, Math.min(1, t));
      const err = (s - sc) * (s - sc) + (t - tc) * (t - tc);

      if (err < bestErr) {
        bestErr = err;
        // Bilinear interpolation with clamped (s, t)
        const ss = sc, tt = tc;
        bestU = (1 - ss) * (1 - tt) * uG[jc    ][ic    ]
              +       ss  * (1 - tt) * uG[jc    ][ic + 1]
              + (1 - ss) *       tt  * uG[jc + 1][ic    ]
              +       ss  *       tt  * uG[jc + 1][ic + 1];
        bestV = (1 - ss) * (1 - tt) * vG[jc    ][ic    ]
              +       ss  * (1 - tt) * vG[jc    ][ic + 1]
              + (1 - ss) *       tt  * vG[jc + 1][ic    ]
              +       ss  *       tt  * vG[jc + 1][ic + 1];
      }
    }

    return [bestU, bestV];
  }
}

// ---------------------------------------------------------------------------

function _bilerp(q00, q10, q01, q11, tx, ty) {
  return (q00 * (1 - tx) + q10 * tx) * (1 - ty) +
         (q01 * (1 - tx) + q11 * tx) * ty;
}

function _speedColor(_speed) {
  return "rgba(255,255,255,0.85)";
}
