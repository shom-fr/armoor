/**
 * timeseries.js – Draw a time-series line chart on a canvas.
 */

const PAD = { top: 28, right: 16, bottom: 48, left: 58 };

/**
 * Render a time-series into a canvas element.
 *
 * @param {HTMLCanvasElement} canvas
 * @param {Object}  data           – response from /api/datasets/<id>/timeseries
 * @param {number}  [currentIdx]   – index of current time step (draws a vertical marker)
 */
export function drawTimeseries(canvas, data, currentIdx = 0) {
  const W   = canvas.width  = canvas.offsetWidth;
  const H   = canvas.height = canvas.offsetHeight || 200;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);

  const values = data.values;
  const times  = data.times;
  const n      = values.length;

  if (!n) { _noData(ctx, W, H); return; }

  // ── Extents ──────────────────────────────────────────────────────────────
  const finite = values.filter(v => v !== null);
  if (!finite.length) { _noData(ctx, W, H); return; }

  let yMin = Math.min(...finite);
  let yMax = Math.max(...finite);
  if (yMin === yMax) { yMin -= 1; yMax += 1; }

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top  - PAD.bottom;

  const xScale = i   => PAD.left + (i / (n - 1)) * plotW;
  const yScale = val => PAD.top  + (1 - (val - yMin) / (yMax - yMin)) * plotH;

  // ── Grid lines ────────────────────────────────────────────────────────────
  ctx.strokeStyle = "rgba(255,255,255,0.07)";
  ctx.lineWidth   = 1;
  const nGrid = 4;
  for (let k = 0; k <= nGrid; k++) {
    const y = PAD.top + (k / nGrid) * plotH;
    ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(PAD.left + plotW, y);
    ctx.stroke();
  }

  // ── Current-time marker ───────────────────────────────────────────────────
  if (currentIdx >= 0 && currentIdx < n) {
    const xc = xScale(currentIdx);
    ctx.strokeStyle = "rgba(233,69,96,0.7)";
    ctx.lineWidth   = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(xc, PAD.top); ctx.lineTo(xc, PAD.top + plotH);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // ── Line ──────────────────────────────────────────────────────────────────
  ctx.strokeStyle = "#53c0f0";
  ctx.lineWidth   = 1.8;
  ctx.beginPath();
  let firstPoint = true;
  for (let i = 0; i < n; i++) {
    if (values[i] === null) { firstPoint = true; continue; }
    const x = xScale(i);
    const y = yScale(values[i]);
    firstPoint ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    firstPoint = false;
  }
  ctx.stroke();

  // ── Dots at each point ────────────────────────────────────────────────────
  ctx.fillStyle = "#53c0f0";
  for (let i = 0; i < n; i++) {
    if (values[i] === null) continue;
    ctx.beginPath();
    ctx.arc(xScale(i), yScale(values[i]), 2.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // ── Y axis labels ─────────────────────────────────────────────────────────
  ctx.fillStyle  = "rgba(255,255,255,0.55)";
  ctx.font       = "10px system-ui";
  ctx.textAlign  = "right";
  for (let k = 0; k <= nGrid; k++) {
    const val = yMin + (1 - k / nGrid) * (yMax - yMin);
    const y   = PAD.top + (k / nGrid) * plotH;
    ctx.fillText(_fmt(val), PAD.left - 4, y + 3);
  }

  // ── X axis labels (time) ──────────────────────────────────────────────────
  ctx.textAlign = "center";
  const step = Math.max(1, Math.round(n / 6));
  for (let i = 0; i < n; i += step) {
    const x     = xScale(i);
    const label = _shortTime(times[i]);
    ctx.save();
    ctx.translate(x, PAD.top + plotH + 14);
    ctx.rotate(-Math.PI / 5);
    ctx.fillText(label, 0, 0);
    ctx.restore();
  }

  // ── Axis lines ────────────────────────────────────────────────────────────
  ctx.strokeStyle = "rgba(255,255,255,0.2)";
  ctx.lineWidth   = 1;
  ctx.beginPath();
  ctx.moveTo(PAD.left, PAD.top);
  ctx.lineTo(PAD.left, PAD.top + plotH);
  ctx.lineTo(PAD.left + plotW, PAD.top + plotH);
  ctx.stroke();

  // ── Units label ───────────────────────────────────────────────────────────
  if (data.units) {
    ctx.fillStyle = "rgba(255,255,255,0.35)";
    ctx.font      = "10px system-ui";
    ctx.textAlign = "left";
    ctx.fillText(data.units, PAD.left + 2, PAD.top - 8);
  }
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

function _shortTime(t) {
  if (typeof t === "string" && t.length >= 10) return t.slice(0, 10);
  return String(t);
}
