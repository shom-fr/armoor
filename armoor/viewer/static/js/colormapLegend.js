/**
 * colormapLegend.js – Draws a colorbar on a <canvas> element.
 *
 * Fetches color data from the backend's colormap strip endpoint, or builds
 * it client-side using a simple colour interpolation table.
 *
 * For simplicity we request the colormap strip as a PNG from the tile endpoint
 * with a synthetic 1-pixel-tall strip, then draw it stretched onto the legend
 * canvas.  Alternatively, the backend could expose a dedicated /colormap route.
 *
 * Here we implement a lightweight client-side approach using a fetch to the
 * tile endpoint with a tiny 256×1 strip dataset (fallback: gradient of greys
 * if the fetch is skipped).
 */

/**
 * @param {HTMLCanvasElement} canvas
 * @param {string}  cmapName  – e.g. "cmo.thermal"
 * @param {number}  vmin
 * @param {number}  vmax
 * @param {HTMLElement} [vminEl]  – element to update with vmin label
 * @param {HTMLElement} [vmaxEl]  – element to update with vmax label
 */
export async function drawLegend(canvas, cmapName, vmin, vmax, vminEl, vmaxEl) {
  const ctx = canvas.getContext("2d");
  const W   = canvas.width  = canvas.offsetWidth  || 280;
  const H   = canvas.height = canvas.offsetHeight || 24;

  // Try to fetch the colormap strip from the backend
  try {
    const url = `/api/colormap-strip?name=${encodeURIComponent(cmapName)}&n=256`;
    const resp = await fetch(url);
    if (resp.ok) {
      const blob = await resp.blob();
      const bmp  = await createImageBitmap(blob);
      ctx.drawImage(bmp, 0, 0, W, H);
    } else {
      _drawFallback(ctx, W, H);
    }
  } catch (_) {
    _drawFallback(ctx, W, H);
  }

  // Labels
  if (vminEl) vminEl.textContent = _fmt(vmin);
  if (vmaxEl) vmaxEl.textContent = _fmt(vmax);
}

function _drawFallback(ctx, W, H) {
  const grad = ctx.createLinearGradient(0, 0, W, 0);
  grad.addColorStop(0,    "#0a0a2e");
  grad.addColorStop(0.25, "#0074b7");
  grad.addColorStop(0.5,  "#00b4d8");
  grad.addColorStop(0.75, "#90e0ef");
  grad.addColorStop(1,    "#caf0f8");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);
}

function _fmt(v) {
  if (Math.abs(v) >= 1000 || (Math.abs(v) < 0.01 && v !== 0)) {
    return v.toExponential(2);
  }
  return v.toFixed(2);
}
