/**
 * section.js – Render a 2-D vertical section (depth × distance) on a canvas.
 *
 * Uses a pcolormesh approach: each cell (d, p) is drawn at its actual
 * physical position derived from distances[p] and depths[d][p], exactly
 * as matplotlib.pcolormesh would place it.
 *
 * Avoids OffscreenCanvas / createImageBitmap for broader browser support
 * (Safari < 16.4 does not implement OffscreenCanvas).
 */

const PAD = { top: 16, right: 16, bottom: 50, left: 58 };

// Cached colormap LUT:  cmapName → Uint8ClampedArray (length 256*4)
const _lutCache = {};

/**
 * Fetch (and cache) the colormap lookup table.
 * Uses a regular <img> element so it works on all browsers.
 *
 * @param {string} cmapName
 * @returns {Promise<Uint8ClampedArray>}
 */
async function getLUT(cmapName) {
  if (_lutCache[cmapName]) return _lutCache[cmapName];

  const resp = await fetch(`/api/colormap-strip?name=${encodeURIComponent(cmapName)}&n=256`);
  if (!resp.ok) throw new Error("Could not fetch colormap strip");

  const blob = await resp.blob();
  const url  = URL.createObjectURL(blob);

  const img = await new Promise((resolve, reject) => {
    const i  = new Image();
    i.onload  = () => resolve(i);
    i.onerror = () => reject(new Error("Colormap image failed to load"));
    i.src = url;
  });

  const oc  = document.createElement("canvas");
  oc.width  = 256;
  oc.height = 1;
  const octx = oc.getContext("2d");
  octx.drawImage(img, 0, 0);
  const lut = octx.getImageData(0, 0, 256, 1).data;

  URL.revokeObjectURL(url);
  _lutCache[cmapName] = lut;
  return lut;
}

/**
 * Draw a 2-D section into a canvas element using pcolormesh-style rendering.
 *
 * depths[d][p] gives the physical depth at z-level d, section point p.
 * Each cell is drawn at its actual (distance, depth) canvas position.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {Object}  data       – response from /api/datasets/<id>/section
 * @param {string}  cmapName   – colormap name (must match tile rendering)
 */
export async function drawSection(canvas, data, cmapName = "cmo.thermal") {
  const W   = canvas.width  = canvas.offsetWidth;
  const H   = canvas.height = canvas.offsetHeight || 240;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);

  const { values, depths, distances, vmin, vmax, variable, units } = data;
  const nDepths = values.length;
  const nPts    = values[0]?.length ?? 0;

  if (!nDepths || !nPts) { _noData(ctx, W, H); return; }

  const lut   = await getLUT(cmapName);
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top  - PAD.bottom;
  const span  = vmax - vmin || 1;

  // ── Determine depth axis bounds ───────────────────────────────────────────
  // depths is 2-D: depths[d][p]. Collect all finite values.
  let depthMin = Infinity;
  let depthMax = -Infinity;
  for (let d = 0; d < nDepths; d++) {
    for (let p = 0; p < nPts; p++) {
      const v = depths[d][p];
      if (v != null && isFinite(v)) {
        if (v < depthMin) depthMin = v;
        if (v > depthMax) depthMax = v;
      }
    }
  }
  if (!isFinite(depthMin)) { depthMin = 0; depthMax = nDepths - 1; }
  if (depthMin === depthMax) depthMax = depthMin + 1;

  const distMin = distances[0];
  const distMax = distances[distances.length - 1] || 1;

  // Map physical coords → canvas pixels
  function xPx(dist) {
    return PAD.left + (dist - distMin) / (distMax - distMin) * plotW;
  }
  function yPx(depth) {
    // depthMin at top (surface or shallowest), depthMax at bottom.
    // Works for both positive (NEMO deptht 0→H) and negative (CROCO z_rho 0→-H).
    return PAD.top + (depth - depthMin) / (depthMax - depthMin) * plotH;
  }

  // ── pcolormesh cell rendering ─────────────────────────────────────────────
  // For each cell (d, p), compute cell boundaries using midpoints between
  // neighbours (as matplotlib pcolormesh does), then fillRect.
  for (let d = 0; d < nDepths; d++) {
    for (let p = 0; p < nPts; p++) {
      const v = values[d][p];
      if (v === null || v === undefined) continue;

      // Horizontal cell edges (midpoints between adjacent distance samples)
      const xL = xPx(p === 0          ? distances[0]
                                       : (distances[p - 1] + distances[p]) / 2);
      const xR = xPx(p === nPts - 1   ? distances[nPts - 1]
                                       : (distances[p] + distances[p + 1]) / 2);

      // Vertical cell edges (midpoints between adjacent depth levels)
      const depthTop = d === 0
        ? depths[0][p]
        : (depths[d - 1][p] + depths[d][p]) / 2;
      const depthBot = d === nDepths - 1
        ? depths[nDepths - 1][p]
        : (depths[d][p] + depths[d + 1][p]) / 2;

      const yT = yPx(Math.min(depthTop, depthBot));
      const yB = yPx(Math.max(depthTop, depthBot));

      const cellW = Math.max(1, xR - xL);
      const cellH = Math.max(1, yB - yT);

      // Colour from LUT
      const t  = Math.max(0, Math.min(255, Math.round((v - vmin) / span * 255)));
      const li = t * 4;
      ctx.fillStyle = `rgb(${lut[li]},${lut[li + 1]},${lut[li + 2]})`;
      ctx.fillRect(xL, yT, cellW, cellH);
    }
  }

  // ── Y axis (depth) ────────────────────────────────────────────────────────
  ctx.fillStyle  = "rgba(255,255,255,0.55)";
  ctx.font       = "10px system-ui";
  ctx.textAlign  = "right";
  const nYTicks  = 6;
  for (let k = 0; k <= nYTicks; k++) {
    const depth = depthMin + (k / nYTicks) * (depthMax - depthMin);
    const y     = yPx(depth);
    const label = `${Number(depth).toFixed(0)} m`;
    ctx.fillText(label, PAD.left - 4, y + 3);

    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    ctx.lineWidth   = 1;
    ctx.beginPath();
    ctx.moveTo(PAD.left, y); ctx.lineTo(PAD.left + plotW, y);
    ctx.stroke();
  }

  // ── X axis (distance) ─────────────────────────────────────────────────────
  ctx.textAlign  = "center";
  ctx.fillStyle  = "rgba(255,255,255,0.55)";
  const nXTicks  = 5;
  for (let k = 0; k <= nXTicks; k++) {
    const frac  = k / nXTicks;
    const x     = PAD.left + frac * plotW;
    const label = `${(frac * distMax).toFixed(0)} km`;
    ctx.fillText(label, x, PAD.top + plotH + 14);
  }

  // ── Axis lines ────────────────────────────────────────────────────────────
  ctx.strokeStyle = "rgba(255,255,255,0.25)";
  ctx.lineWidth   = 1;
  ctx.beginPath();
  ctx.moveTo(PAD.left, PAD.top);
  ctx.lineTo(PAD.left, PAD.top + plotH);
  ctx.lineTo(PAD.left + plotW, PAD.top + plotH);
  ctx.stroke();

  // ── Y axis label ─────────────────────────────────────────────────────────
  ctx.save();
  ctx.translate(10, PAD.top + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillStyle = "rgba(255,255,255,0.35)";
  ctx.font      = "10px system-ui";
  ctx.textAlign = "center";
  ctx.fillText("Depth (m)", 0, 0);
  ctx.restore();

  // ── Colorbar strip (bottom right) ─────────────────────────────────────────
  const cbW = Math.min(120, plotW * 0.3);
  const cbH = 8;
  const cbX = PAD.left + plotW - cbW;
  const cbY = PAD.top + plotH + 24;

  const stripImgData = new ImageData(256, 1);
  for (let t = 0; t < 256; t++) {
    const li = t * 4;
    stripImgData.data[li]     = lut[li];
    stripImgData.data[li + 1] = lut[li + 1];
    stripImgData.data[li + 2] = lut[li + 2];
    stripImgData.data[li + 3] = 255;
  }
  const stripCanvas   = document.createElement("canvas");
  stripCanvas.width   = 256;
  stripCanvas.height  = 1;
  stripCanvas.getContext("2d").putImageData(stripImgData, 0, 0);
  ctx.drawImage(stripCanvas, cbX, cbY, cbW, cbH);
  ctx.strokeStyle = "rgba(255,255,255,0.2)";
  ctx.strokeRect(cbX, cbY, cbW, cbH);

  ctx.fillStyle = "rgba(255,255,255,0.5)";
  ctx.font      = "9px system-ui";
  ctx.textAlign = "left";
  ctx.fillText(_fmt(vmin), cbX, cbY + cbH + 10);
  ctx.textAlign = "right";
  ctx.fillText(_fmt(vmax), cbX + cbW, cbY + cbH + 10);
  ctx.textAlign = "center";
  ctx.fillText(units || variable, cbX + cbW / 2, cbY + cbH + 10);
}

// ---------------------------------------------------------------------------

function _noData(ctx, W, H) {
  ctx.fillStyle = "rgba(255,255,255,0.3)";
  ctx.font      = "12px system-ui";
  ctx.textAlign = "center";
  ctx.fillText("No data", W / 2, H / 2);
}

function _fmt(v) {
  if (Math.abs(v) >= 1000 || (Math.abs(v) < 0.01 && v !== 0)) return v.toExponential(1);
  return v.toFixed(2);
}
