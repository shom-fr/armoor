/**
 * layer.js – Manages the scalar imagery layer on the MapLibre globe.
 *
 * Normal rendering: fetchTileMeta → object-URL → Globe.setScalarLayer.
 * Animated playback: preloadFrames pre-fetches every time step into a
 * Map<time_idx → {url, bbox, vmin, vmax}>, then showFrame swaps frames
 * instantly from that cache with no server round-trip.
 */

import { fetchTileMeta, fetchGrid } from "./api.js";

const PRELOAD_CONCURRENCY = 4;

export class ScalarLayerManager {
  /**
   * @param {import("./globe.js").Globe} globe
   */
  constructor(globe) {
    this.globe      = globe;
    this._objectUrl = null;

    // Frame cache for animated playback
    /** @type {Map<number, {url:string, bbox:Object, vmin:number, vmax:number}>} */
    this._frames    = new Map();
    this._cacheKey  = null;   // identifies the params the cache was built for

    // Geographic vertex grid – fetched once per dataset, keyed by dataset ID.
    this._vertexGrid   = null;
    this._vertexGridId = null;

    // Track which dataset we last flew to, so changing variable/time/depth
    // does not reset the camera.
    this._flyDatasetId = null;
  }

  /** Fetch (and cache) the geographic vertex grid for *datasetId*. */
  async _ensureGrid(datasetId) {
    if (this._vertexGridId !== datasetId) {
      this._vertexGrid   = await fetchGrid(datasetId).catch(() => null);
      this._vertexGridId = datasetId;
    }
    return this._vertexGrid;
  }

  // ── Single-frame render ──────────────────────────────────────────────────

  /**
   * Fetch a tile and display it. Clears any existing frame cache.
   *
   * @param {string}  datasetId
   * @param {Object}  params       – forwarded to fetchTileMeta
   * @param {number}  [opacity]
   * @returns {{ vmin: number, vmax: number, bbox: Object }}
   */
  async update(datasetId, params, opacity = 0.85) {
    // Any manual render invalidates the animation cache.
    this._cacheKey = null;
    this.clearFrameCache();

    if (this._objectUrl) {
      URL.revokeObjectURL(this._objectUrl);
      this._objectUrl = null;
    }

    const [{ blob, bbox, vmin, vmax }, grid] = await Promise.all([
      fetchTileMeta(datasetId, params),
      this._ensureGrid(datasetId),
    ]);
    this._objectUrl = URL.createObjectURL(blob);

    this.globe.setScalarLayer(this._objectUrl, bbox, opacity, grid);
    if (datasetId !== this._flyDatasetId) {
      this.globe.flyToBbox(bbox);
      this._flyDatasetId = datasetId;
    }

    return { vmin, vmax, bbox };
  }

  remove() {
    this.clearFrameCache();
    this.globe.removeScalarLayer();
    if (this._objectUrl) {
      URL.revokeObjectURL(this._objectUrl);
      this._objectUrl = null;
    }
    this._flyDatasetId = null;
  }

  setOpacity(opacity) {
    this.globe.setScalarOpacity(opacity);
  }

  // ── Animated playback ────────────────────────────────────────────────────

  /**
   * Pre-fetch all time steps and store as blob-URL frames.
   * If the cache is already valid for these params, returns immediately.
   *
   * @param {string}   datasetId
   * @param {Object}   params      – tile params (time_idx is overridden per frame)
   * @param {number}   timeCount
   * @param {Function} [onProgress]  – (loaded, total) => void
   * @param {AbortSignal} [signal]
   */
  async preloadFrames(datasetId, params, timeCount, onProgress, signal) {
    const key = datasetId + "|" + _cacheKey(params);

    // Reuse existing complete cache if nothing changed.
    if (this._cacheKey === key && this._frames.size === timeCount) {
      onProgress?.(timeCount, timeCount);
      return;
    }

    this._cacheKey = null;
    this.clearFrameCache();

    // Grid is dataset-scoped; fetch it before the frame loop.
    await this._ensureGrid(datasetId);

    let loaded = 0;

    for (let start = 0; start < timeCount; start += PRELOAD_CONCURRENCY) {
      if (signal?.aborted) throw new DOMException("Aborted", "AbortError");

      const batch = [];
      for (let t = start; t < Math.min(start + PRELOAD_CONCURRENCY, timeCount); t++) {
        batch.push(
          fetchTileMeta(datasetId, { ...params, time_idx: t }, signal)
            .then(({ blob, bbox, vmin, vmax }) => {
              if (signal?.aborted) return;
              this._frames.set(t, { url: URL.createObjectURL(blob), bbox, vmin, vmax });
              onProgress?.(++loaded, timeCount);
            }),
        );
      }
      await Promise.all(batch);
    }

    this._cacheKey = key;
  }

  /**
   * Display a pre-fetched frame.  No server request, no camera movement.
   *
   * @param {number} timeIdx
   * @param {number} opacity
   * @returns {{ vmin: number, vmax: number }|null}  null if frame not cached
   */
  showFrame(timeIdx, opacity) {
    const frame = this._frames.get(timeIdx);
    if (!frame) return null;
    this.globe.setScalarLayer(frame.url, frame.bbox, opacity, this._vertexGrid);
    return { vmin: frame.vmin, vmax: frame.vmax };
  }

  /** Release all cached blob URLs. */
  clearFrameCache() {
    for (const f of this._frames.values()) URL.revokeObjectURL(f.url);
    this._frames.clear();
    this._cacheKey = null;
  }
}

// ---------------------------------------------------------------------------

/** Stable cache key: all params except time_idx, sorted. */
function _cacheKey(params) {
  const { time_idx, ...rest } = params;
  return JSON.stringify(Object.fromEntries(Object.entries(rest).sort()));
}
