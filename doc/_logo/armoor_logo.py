"""ARMOOR logo drawn with matplotlib.

The two interlaced O's of ARMOOR compare observations with a model. Shapely
does the boolean geometry (bands, cut-outs at the crossings), so the
interlacing stays correct on a transparent background. The observation
pattern comes from fixed random seeds: every run draws the same logo.

The documentation build (doc/conf.py) calls build_doc_assets() to write the
images into doc/_static/logo/ (not versioned).

The first O holds the observations: thin broken tracks that fade in and out,
with stations of varying size. The second O holds the model: a continuous field
of filled contour bands whose inner isolines are slightly offset.

Requires matplotlib, numpy, shapely and fonts/Manrope-Bold.ttf (SIL OFL 1.1).

Examples
--------
python doc/_logo/armoor_logo.py logo -o armoor-logo.png
python doc/_logo/armoor_logo.py logo --dark -o armoor-logo-dark.png
python doc/_logo/armoor_logo.py logo --lowercase -o armoor-logo-lowercase.svg --no-fade
python doc/_logo/armoor_logo.py logo --mono "#081B2B" -o armoor-logo-mono.pdf
python doc/_logo/armoor_logo.py mark -o armoor-mark.png
python doc/_logo/armoor_logo.py avatar -o armoor-avatar.png --size 5.12 --dpi 100
python doc/_logo/armoor_logo.py favicon -o armoor-favicon.png --size 0.32 --dpi 100
python doc/_logo/armoor_logo.py doc -o doc/_static/logo   # every image used by the documentation

From Python::

    import matplotlib.pyplot as plt
    from armoor_logo import draw_logo

    fig, ax = plt.subplots(figsize=(8, 2.4))
    draw_logo(ax)
"""

import argparse
import math
import random
from pathlib import Path

import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, PathPatch, Rectangle
from matplotlib.path import Path as MPath
from matplotlib.textpath import TextPath
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

FONT_FILE = Path(__file__).parent / "fonts" / "Manrope-Bold.ttf"

NAVY, WHITE = "#081B2B", "#FFFFFF"
ICE = "#CFE7F6"  # letters on navy: very light blue rather than white
# Contour colour scale, outer contour first. On light grounds it stops short of white.
RAMP_DARK = ["#1B5A8A", "#3E9ED8", "#7CBFE8", "#B9DDF4", "#FFFFFF"]
RAMP_LIGHT = ["#1B5A8A", "#3E9ED8", "#7CBFE8", "#A6D2EF", "#CFE7F6"]
FLAT_OBS, FLAT_MODEL = "#7CBFE8", "#3E9ED8"  # simplified rings (favicon)

STEP = 0.40  # distance between the two O centres, in O widths
STROKE = 0.36  # O stroke, relative to its half-width (Manrope Bold)
HALO = 0.38  # gap around the upper strand at a crossing, relative to the stroke
SHIFT = 2.2  # offset of the model's inner isolines, in contour bands
TRACKING = 0.03  # letter-spacing, in em


def _font():
    from fontTools.ttLib import TTFont

    font = TTFont(FONT_FILE)
    return FontProperties(fname=FONT_FILE), font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm


FP, CMAP, HMTX, UPM = _font()


# ---------------------------------------------------------------- geometry helpers


def _ellipse(cx, cy, a, b, n=360):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return Polygon(np.c_[cx + a * np.cos(t), cy + b * np.sin(t)])


def _ring(cx, cy, a, b, width):
    """Elliptical annulus whose outer edge has half-axes (a, b)."""
    return _ellipse(cx, cy, a, b).difference(_ellipse(cx, cy, a - width, b - width))


def _sector(cx, cy, a, b, w, t0, length, n=None):
    """Thick elliptical arc (screen convention: angle grows clockwise)."""
    n = n or max(8, int(48 * length))
    t = np.linspace(t0, t0 + length, n)
    outer = np.c_[cx + (a + w / 2) * np.cos(t), cy - (b + w / 2) * np.sin(t)]
    inner = np.c_[cx + (a - w / 2) * np.cos(t), cy - (b - w / 2) * np.sin(t)][::-1]
    return Polygon(np.vstack([outer, inner]))


def _to_path(geom):
    """Shapely (Multi)Polygon -> matplotlib Path, holes included."""
    verts, codes = [], []
    polys = [geom] if geom.geom_type == "Polygon" else [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]
    for poly in polys:
        if poly.is_empty:
            continue
        poly = orient(poly, 1.0)
        for ring in (poly.exterior, *poly.interiors):
            xy = np.asarray(ring.coords)
            verts.extend(xy.tolist())
            codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(xy) - 2) + [MPath.CLOSEPOLY])
    return MPath(verts, codes) if verts else None


def _fill(ax, geom, color, alpha=1.0, zorder=2):
    path = _to_path(geom)
    if path is not None:
        ax.add_patch(PathPatch(path, facecolor=color, edgecolor="none", lw=0, alpha=alpha, zorder=zorder))
    return path


# ---------------------------------------------------------------- the OO


class _OO:
    """Geometry of the interlaced pair, for the font's O (or o)."""

    def __init__(self, ch, x0=0.0):
        (x_min, y_min), (x_max, y_max) = TextPath((0, 0), ch, size=UPM, prop=FP).get_extents().get_points()
        self.lsb = x_min
        self.rx, self.ry = (x_max - x_min) / 2, (y_max - y_min) / 2
        self.cy = (y_min + y_max) / 2
        self.sw = self.rx * STROKE
        self.step = 2 * self.rx * STEP
        self.halo = self.sw * HALO
        self.c1x = x0 + self.rx  # observations
        self.c2x = self.c1x + self.step  # model
        self.width = self.step + 2 * self.rx
        a, b = self.rx - self.sw / 2, self.ry - self.sw / 2
        yoff = b * math.sqrt(1 - (self.step / 2 / a) ** 2)
        disc = self.sw * 1.4
        xc = self.c1x + self.step / 2
        self.top = Point(xc, self.cy + yoff).buffer(disc, 64)  # model passes over the observations
        self.bottom = Point(xc, self.cy - yoff).buffer(disc, 64)  # observations pass over the model

    def ring(self, cx, grow=0.0):
        return _ring(cx, self.cy, self.rx + grow, self.ry + grow, self.sw + 2 * grow)

    def model_bands(self, colors):
        """Filled contours: painter's order, each band minus all bands drawn after it."""
        n, band = len(colors), self.sw / len(colors)
        discs = []
        for k in range(n):
            off = SHIFT * band * math.sin(math.pi * k / n)  # zero on the O's own edges
            discs.append(_ellipse(self.c2x + off * 0.6, self.cy - off * 0.8, self.rx - k * band, self.ry - k * band))
        shape = self.ring(self.c2x)
        bands = []
        for k, col in enumerate(colors):
            later = unary_union(discs[k + 1:]) if k + 1 < n else None
            region = discs[k].difference(later) if later is not None else discs[k]
            bands.append((region.intersection(shape), col))
        return bands

    def observations(self, colors):
        """Broken tracks and stations, with the same seeds as the SVG kit."""
        n, band = len(colors), self.sw / len(colors)
        w, lw = band * 0.38, band * 0.26
        tracks, stations = [], []

        def pt(a0, b0, t):
            return self.c1x + a0 * math.cos(t), self.cy - b0 * math.sin(t)

        for k, col in enumerate(colors):
            rnd = random.Random(2000 + 37 * k)
            a0, b0 = self.rx - band * (k + 0.5), self.ry - band * (k + 0.5)
            t = rnd.uniform(0, 1.0)
            end = t + 2 * math.pi
            while t < end:
                length = min(rnd.uniform(0.45, 1.5), end - t)
                tracks.append(dict(a=a0, b=b0, t=t, length=length, w=w, color=col))
                if rnd.random() < 0.35:  # a station on the track itself
                    xy = pt(a0, b0, t + length * rnd.uniform(0.3, 0.7))
                    stations.append(dict(xy=xy, r=band * rnd.uniform(0.35, 0.95), lw=lw, color=col))
                gap = rnd.uniform(0.16, 0.34)
                if t + length + gap < end:  # a station in the gap
                    xy = pt(a0, b0, t + length + gap / 2)
                    stations.append(dict(xy=xy, r=band * rnd.uniform(0.35, 0.95), lw=lw, color=col))
                t += length + gap
        return tracks, stations

    def track_shape(self, tr, grow=0.0):
        return _sector(self.c1x, self.cy, tr["a"], tr["b"], tr["w"] + grow, tr["t"], tr["length"])


def _fading_track(ax, oo, tr, shape, zorder):
    """Fill `shape` with the track colour, alpha rising and falling along the arc."""
    path = _to_path(shape)
    if path is None:
        return
    x0, y0, x1, y1 = shape.bounds
    nx = ny = 160
    xs, ys = np.meshgrid(np.linspace(x0, x1, nx), np.linspace(y0, y1, ny))
    ang = np.arctan2(-(ys - oo.cy) / tr["b"], (xs - oo.c1x) / tr["a"])
    s = np.mod(ang - tr["t"], 2 * np.pi) / tr["length"]
    alpha = np.clip(s / 0.22, 0, 1) * np.clip((1 - s) / 0.22, 0, 1)
    rgba = np.zeros((ny, nx, 4))
    rgba[..., :3] = np.array([int(tr["color"][i:i + 2], 16) / 255 for i in (1, 3, 5)])
    rgba[..., 3] = alpha
    im = ax.imshow(rgba, extent=(x0, x1, y0, y1), origin="lower", interpolation="bilinear", zorder=zorder)
    im.set_clip_path(PathPatch(path, transform=ax.transData))


def draw_oo(ax, x0=0.0, ch="O", dark=False, mono=None, flat=None, fade=True):
    """Draw the interlaced OO with its left edge at x0. Returns the _OO geometry.

    mono: one colour -> two plain interlaced rings.
    flat: (obs colour, model colour) -> two plain rings in two colours.
    fade: tracks fade in and out (drawn as clipped images); False keeps the output fully vector.
    """
    oo = _OO(ch, x0)
    if mono or flat:
        c1, c2 = (mono, mono) if mono else flat
        r1, r2 = oo.ring(oo.c1x), oo.ring(oo.c2x)
        _fill(ax, r1.difference(oo.ring(oo.c2x, oo.halo).intersection(oo.top)), c1)
        _fill(ax, r2.difference(oo.ring(oo.c1x, oo.halo).intersection(oo.bottom)), c2)
        return oo

    ramp = RAMP_DARK if dark else RAMP_LIGHT
    tracks, stations = oo.observations(ramp)
    station_shapes = [Point(*st["xy"]).buffer(st["r"], 48).difference(Point(*st["xy"]).buffer(st["r"] - st["lw"], 48))
                      for st in stations]

    # model: cut where the observations pass over it (bottom crossing), around their actual tracks
    lift = unary_union([oo.track_shape(tr, 2 * oo.halo) for tr in tracks]
                       + [Point(*st["xy"]).buffer(st["r"] + oo.halo, 48) for st in stations])
    cut_model = lift.intersection(oo.bottom)
    for region, col in oo.model_bands(ramp):
        _fill(ax, region.difference(cut_model), col, zorder=2)

    # observations: cut where the model passes over them (top crossing)
    cut_obs = oo.ring(oo.c2x, oo.halo).intersection(oo.top)
    for tr in tracks:
        shape = oo.track_shape(tr).difference(cut_obs)
        if fade:
            _fading_track(ax, oo, tr, shape, zorder=3)
        else:
            _fill(ax, shape, tr["color"], zorder=3)
    for st, shape in zip(stations, station_shapes):
        _fill(ax, shape.difference(cut_obs), st["color"], zorder=4)
    return oo


# ---------------------------------------------------------------- public API


def _advance(ch):
    return HMTX[CMAP[ord(ch)]][0]


def draw_logo(ax, word="ARMOOR", dark=False, mono=None, color=None, fade=True, pad=0.06):
    """Draw the wordmark on `ax` (aspect, limits and axis are set). Returns its bbox."""
    text = color or mono or (ICE if dark else NAVY)
    o = "O" if word[0].isupper() else "o"
    x, i = 0.0, 0
    while i < len(word):
        if word[i:i + 2] == o * 2:
            lsb = _OO(o).lsb
            oo = draw_oo(ax, x + lsb, o, dark=dark, mono=mono, fade=fade)
            x += oo.width + 2 * lsb + TRACKING * UPM
            i += 2
            continue
        tp = TextPath((x, 0), word[i], size=UPM, prop=FP)
        ax.add_patch(PathPatch(tp, facecolor=text, edgecolor="none", lw=0, zorder=5))
        x += _advance(word[i]) + TRACKING * UPM
        i += 1
    x -= TRACKING * UPM
    top = max(TextPath((0, 0), word, size=UPM, prop=FP).get_extents().y1, _OO(o).cy + _OO(o).ry)
    bottom = min(0.0, _OO(o).cy - _OO(o).ry)
    m = pad * (top - bottom)
    bbox = (-m, x + m, bottom - m, top + m)
    _frame(ax, bbox)
    return bbox


def draw_mark(ax, dark=False, mono=None, flat=None, fade=True, pad=0.06):
    """Draw the OO symbol alone."""
    oo = draw_oo(ax, 0.0, "O", dark=dark, mono=mono, flat=flat, fade=fade)
    m = pad * oo.width
    bbox = (-m, oo.width + m, oo.cy - oo.ry - m, oo.cy + oo.ry + m)
    _frame(ax, bbox)
    return bbox


def draw_square(ax, frac=0.72, flat=None, tile=False, fade=True):
    """Navy square (or rounded tile) with the OO centred over `frac` of its width."""
    oo = _OO("O")
    side = oo.width / frac
    cx, cy = oo.width / 2, oo.cy
    x0, y0 = cx - side / 2, cy - side / 2
    if tile:
        ax.add_patch(FancyBboxPatch((x0, y0), side, side, boxstyle=f"round,pad=0,rounding_size={side * 14 / 64}",
                                    facecolor=NAVY, edgecolor="none", zorder=0))
    else:
        ax.add_patch(Rectangle((x0, y0), side, side, facecolor=NAVY, edgecolor="none", zorder=0))
    draw_oo(ax, 0.0, "O", dark=True, flat=flat, fade=fade)
    bbox = (x0, x0 + side, y0, y0 + side)
    _frame(ax, bbox)
    return bbox


def _frame(ax, bbox):
    ax.set_xlim(bbox[0], bbox[1])
    ax.set_ylim(bbox[2], bbox[3])
    ax.set_aspect("equal")
    ax.set_axis_off()


def save(kind, out, dark=False, mono=None, lowercase=False, size=8.0, dpi=200, fade=True, background=None):
    """Render one variant to a file. `size` is the figure width in inches.

    background: None -> navy for a dark logo or mark, transparent otherwise;
    "none" -> transparent; any other value -> that colour.
    """
    from matplotlib.figure import Figure

    fig = Figure()
    ax = fig.add_axes((0, 0, 1, 1))
    if kind == "logo":
        bbox = draw_logo(ax, "armoor" if lowercase else "ARMOOR", dark=dark, mono=mono, fade=fade)
    elif kind == "mark":
        bbox = draw_mark(ax, dark=dark, mono=mono, fade=fade)
    elif kind == "avatar":
        bbox = draw_square(ax, 0.72, fade=fade)
    elif kind == "favicon":
        bbox = draw_square(ax, 0.8, flat=(FLAT_OBS, FLAT_MODEL), tile=True)
    else:
        raise ValueError(kind)
    w, h = bbox[1] - bbox[0], bbox[3] - bbox[2]
    fig.set_size_inches(size, size * h / w)
    if background is None:
        background = NAVY if dark and kind in ("logo", "mark") else "none"
    fig.savefig(out, dpi=dpi, facecolor=background, transparent=background == "none")


# Images used by the Sphinx documentation: file name -> save() arguments.
DOC_ASSETS = {
    "armoor-logo.png": dict(kind="logo", size=6, dpi=150),
    "armoor-logo-dark.png": dict(kind="logo", dark=True, background="none", size=6, dpi=150),
    "armoor-logo-navy.png": dict(kind="logo", dark=True, size=6, dpi=150),
    "armoor-logo-lowercase.png": dict(kind="logo", lowercase=True, size=6, dpi=150),
    "armoor-logo-mono.png": dict(kind="logo", mono=NAVY, size=6, dpi=150),
    "armoor-logo-mono-white.png": dict(kind="logo", mono=WHITE, background=NAVY, size=6, dpi=150),
    "armoor-mark.png": dict(kind="mark", size=4, dpi=150),
    "armoor-avatar.png": dict(kind="avatar", size=5.12, dpi=100),
    "armoor-favicon.png": dict(kind="favicon", size=0.64, dpi=100),
}


def build_doc_assets(outdir, force=False):
    """Write DOC_ASSETS into `outdir`; skipped when they are newer than this script and the font."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    source_time = max(Path(__file__).stat().st_mtime, FONT_FILE.stat().st_mtime)
    for name, kwargs in DOC_ASSETS.items():
        out = outdir / name
        if force or not out.exists() or out.stat().st_mtime < source_time:
            save(out=out, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("kind", choices=["logo", "mark", "avatar", "favicon", "doc"],
                   help="'doc' writes every image used by the documentation into the -o directory")
    p.add_argument("-o", "--output", required=True, help="png, svg or pdf file (a directory for 'doc')")
    p.add_argument("--dark", action="store_true", help="navy background, scale up to white")
    p.add_argument("--mono", metavar="COLOR", help="single colour, plain rings")
    p.add_argument("--lowercase", action="store_true")
    p.add_argument("--size", type=float, default=8.0, help="figure width in inches")
    p.add_argument("--dpi", type=float, default=200)
    p.add_argument("--no-fade", action="store_true", help="solid tracks: fully vector svg/pdf")
    a = p.parse_args()
    if a.kind == "doc":
        build_doc_assets(a.output, force=True)
        return
    save(a.kind, a.output, a.dark, a.mono, a.lowercase, a.size, a.dpi, fade=not a.no_fade)


if __name__ == "__main__":
    main()
