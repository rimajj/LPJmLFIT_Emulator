#!/usr/bin/env python3
"""O3a — build a REAL per-cell soil-texture field for the online (Terrarium) soil.

WHY THIS EXISTS
---------------
Terrarium's default stratigraphy is `ConstantSoilHorizon` with `SoilTexture(NF)` =
`sand = 1.0, clay = 0.0`.  `SoilHydraulicsSURFEX` then computes

    wilting_point  = 37.13e-3 * sqrt(clay*100)
    field_capacity = 89.0e-3  * (clay*100)^0.35

which are **both exactly zero** at `clay = 0`, so

    plant_available_water = clamp((theta_w - wp) / (fc - wp), 0, 1)  ==  1.0

everywhere there is any water.  It does not error — it silently reports "fully unstressed
everywhere", deleting the drought response.  [VERIFIED 2026-07-28, job 1622830; ADR 0082 §4,
skill `online-coupling-env` trap 6.]  So the online soil MUST be given a real clay fraction.

WHERE THE TEXTURE COMES FROM
----------------------------
The GROUND-TRUTH run's own soil input, so the online soil is texturally consistent with the
offline oracle and with the `soilmoist` training reference we compare against (O3b):

  * `.../clustering/global/soil_code_test.soil.bin` — raw, 1 byte per cell, the LPJmL *soilcode*.
    `newgrid.c:449` does `soil_id = config->soilmap[soilcode] - 1`, and `input_GSWP3-W5E5.js:17`
    gives `soilmap = [null, "clay", ..., "rock and ice"]`, i.e. the byte is a 1-based index into
    the soilmap names (0 = no soil).
  * `par/soil_20m.js` — the `soilpar` table, which carries `sand`/`silt`/`clay` mass fractions
    per soil type.  These are the exact numbers the C oracle uses.
  * `.../clustering/global/soil_code_test.grid.clm` — the **orderA** coordinates (.clm v3,
    float32, HDR=51, scalar 1.0; header parsed, never assumed — CLAUDE.md §3).

  ⚠️ Do NOT use `/p/projects/biodiversity/input_VERSION2/{grid.bin,soil_new_67420.bin}` (the pair
  named in the repo checkout's `input_GSWP3-W5E5.js`).  Both files cover the same 67 420 half-degree
  land cells, but `grid.bin` is in a **different, longitude-major order** in which Hainich is index
  **28008**, not the orderA 42490.  Pairing orderA indices with that grid silently shifts every
  cell.  (This also corrects CLAUDE.md §1, which attributes 28008 to a `-DSINGLESITE` grid: 28008
  is Hainich's index in the repo-default *global* `grid.bin`.)  Mapping here is by lat/lon anyway,
  but the two soil files are not interchangeable row-for-row.

OUTPUT
------
A CSV at `--out` with one row per orderA cell that HAS a soil code:
    cell,lon,lat,soilcode,name,sand,silt,clay
Consumed by `scripts/online_coupling/soil_texture.jl`, which nearest-neighbour-maps it onto the
SpeedyWeather/Terrarium ring grid.

Run on the login node (seconds, pure numpy).
"""

import argparse
import os
import re
import struct
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # NEVER hard-code (CLAUDE.md §9.6)
LPJROOT = os.environ.get("LPJROOT", "/home/jamirp/lpjml56fit")

GROUND_TRUTH = "/p/projects/waldspektrum/priesner/clustering/global"
SOIL_BIN = os.path.join(GROUND_TRUTH, "soil_code_test.soil.bin")
GRID_BIN = os.path.join(GROUND_TRUTH, "soil_code_test.grid.clm")
SOILPAR_JS = os.path.join(LPJROOT, "par", "soil_20m.js")
INPUT_JS = os.path.join(LPJROOT, "input_GSWP3-W5E5.js")

# Hainich, the standing single-cell probe (CLAUDE.md §1): orderA positional index -> (lat, lon).
HAINICH_CELL, HAINICH_LAT, HAINICH_LON = 42490, 51.25, 10.25


def parse_soilmap(path):
    """`soilmap` from the LPJmL input config: a 0-based array whose [soilcode] entry is the soil
    NAME (entry 0 is `null` = no soil).  Returned as {soilcode: name}."""
    with open(path) as fh:
        txt = fh.read()
    m = re.search(r'"soilmap"\s*:\s*\[(.*?)\]', txt, re.S)
    if m is None:
        raise SystemExit(f"FATAL: no soilmap in {path}")
    entries = [e.strip() for e in m.group(1).split(",")]
    out = {}
    for code, e in enumerate(entries):
        if e == "null":
            continue
        q = re.fullmatch(r'"(.*)"', e)
        if q is None:
            raise SystemExit(f"FATAL: unparsable soilmap entry {e!r}")
        out[code] = q.group(1)
    return out


def parse_soilpar(path):
    """{name: (sand, silt, clay)} from `par/soil_20m.js`.  These are mass fractions of the mineral
    matrix and are exactly what Terrarium's `SoilTexture` wants."""
    with open(path) as fh:
        txt = fh.read()
    out = {}
    for line in txt.splitlines():
        if '"name"' not in line or '"sand"' not in line:
            continue
        name = re.search(r'"name"\s*:\s*"([^"]+)"', line).group(1)
        vals = {}
        for k in ("sand", "silt", "clay"):
            mm = re.search(r'"%s"\s*:\s*([0-9.]+)' % k, line)
            if mm is None:
                raise SystemExit(f"FATAL: no {k} for soil {name!r}")
            vals[k] = float(mm.group(1))
        out[name] = (vals["sand"], vals["silt"], vals["clay"])
    if not out:
        raise SystemExit(f"FATAL: no soilpar rows in {path}")
    return out


def read_grid_clm(path):
    """orderA coordinates from grid.bin.  Header-driven (CLAUDE.md §3: PARSE the header) — this is
    a v2 .clm (no datatype field, HDR=43, int16) with nbands=2 = (lon, lat) and scalar 0.01."""
    with open(path, "rb") as fh:
        raw = fh.read(64)
    magic = raw[:7]
    if magic not in (b"LPJGRID", b"LPJCLIM"):
        raise SystemExit(f"FATAL: {path} magic={magic!r} is neither LPJGRID nor LPJCLIM")
    version, order, firstyear, nyear, firstcell, ncell, nbands = struct.unpack("<7i", raw[7 : 7 + 28])
    scalar = struct.unpack("<f", raw[7 + 32 : 7 + 36])[0]
    if version >= 3:
        hdr, code = 51, struct.unpack("<i", raw[7 + 40 : 7 + 44])[0]
        dt = {0: "<i1", 1: "<i2", 2: "<i4", 3: "<f4", 4: "<f8"}[code]  # 0-BASED (CLAUDE.md §3)
    else:
        hdr, dt = 43, "<i2"
    size = os.path.getsize(path)
    expect = hdr + nyear * ncell * nbands * np.dtype(dt).itemsize
    if size != expect:
        raise SystemExit(f"FATAL: {path} size {size} != expected {expect} (v{version} hdr={hdr} dt={dt})")
    arr = np.memmap(path, dtype=dt, mode="r", offset=hdr, shape=(ncell, nbands))
    print(f"== grid={os.path.basename(path)} v{version} dt={dt} scalar={scalar} ncell={ncell} nbands={nbands} hdr={hdr}")
    if nbands != 2:
        raise SystemExit(f"FATAL: grid file has nbands={nbands}, expected 2 (lon, lat)")
    lon = np.asarray(arr[:, 0], dtype=np.float64) * scalar
    lat = np.asarray(arr[:, 1], dtype=np.float64) * scalar
    return lon, lat, ncell


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="/p/tmp/jamirp/esm_online_coupling/lpjml_soil_texture_orderA.csv")
    args = ap.parse_args()

    soilmap = parse_soilmap(INPUT_JS)
    soilpar = parse_soilpar(SOILPAR_JS)
    print(f"== soilmap: {len(soilmap)} codes 1..{max(soilmap)}; soilpar: {len(soilpar)} types")

    missing = sorted({n for n in soilmap.values() if n not in soilpar})
    if missing:
        raise SystemExit(f"FATAL: soilmap names absent from soilpar: {missing}")

    lon, lat, ncell = read_grid_clm(GRID_BIN)

    codes = np.fromfile(SOIL_BIN, dtype=np.uint8)
    if codes.size != ncell:
        raise SystemExit(f"FATAL: soil file has {codes.size} bytes but grid has {ncell} cells")

    # GATE: Hainich must land where CLAUDE.md §1 says it does, or the whole cell indexing is wrong.
    if abs(lat[HAINICH_CELL] - HAINICH_LAT) > 1e-6 or abs(lon[HAINICH_CELL] - HAINICH_LON) > 1e-6:
        raise SystemExit(
            f"FATAL: cell {HAINICH_CELL} is (lat={lat[HAINICH_CELL]}, lon={lon[HAINICH_CELL]}), "
            f"expected Hainich ({HAINICH_LAT}, {HAINICH_LON}) -> grid file is not orderA"
        )
    print(f"== GATE ok: cell {HAINICH_CELL} = Hainich (lat {HAINICH_LAT}, lon {HAINICH_LON})")

    unknown = sorted(set(np.unique(codes)).difference(soilmap).difference({0}))
    if unknown:
        raise SystemExit(f"FATAL: soil codes present in the data with no soilmap entry: {unknown}")

    keep = codes != 0
    print(f"== cells with a soil code: {int(keep.sum())} / {ncell} ({100 * keep.mean():.1f} %)")

    sand = np.full(ncell, np.nan)
    silt = np.full(ncell, np.nan)
    clay = np.full(ncell, np.nan)
    for code, name in soilmap.items():
        sel = codes == code
        if not sel.any():
            continue
        s, si, c = soilpar[name]
        sand[sel], silt[sel], clay[sel] = s, si, c
        print(f"   code {code:2d} {name:<18s} n={int(sel.sum()):6d}  sand={s:.2f} silt={si:.2f} clay={c:.2f}")

    # The SoilTexture constructor asserts sand+silt+clay ~= 1; LPJmL's own table does not always
    # sum to exactly 1 (e.g. "silt" is 0.10/0.60/0.30), so renormalize HERE and say so.
    tot = sand + silt + clay
    bad = keep & (np.abs(tot - 1.0) > 1e-9)
    if bad.any():
        print(f"== renormalizing texture for {int(bad.sum())} cells whose LPJmL fractions do not sum to 1 "
              f"(max |sum-1| = {np.nanmax(np.abs(tot[keep] - 1.0)):.4f})")
    sand, silt, clay = sand / tot, silt / tot, clay / tot

    # THE DEGENERACY GATE, applied at source: SURFEX gives fc = wp = 0 at clay = 0.
    if np.nanmin(clay[keep]) <= 0.0:
        raise SystemExit("FATAL: a kept cell has clay <= 0 -> SURFEX field_capacity == wilting_point (trap 6)")
    print(f"== clay fraction over kept cells: min={np.nanmin(clay[keep]):.4f} "
          f"median={np.nanmedian(clay[keep]):.4f} max={np.nanmax(clay[keep]):.4f}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    idx = np.nonzero(keep)[0]
    with open(args.out, "w") as fh:
        fh.write("cell,lon,lat,soilcode,name,sand,silt,clay\n")
        for i in idx:
            fh.write(
                f"{i},{lon[i]:.4f},{lat[i]:.4f},{codes[i]},{soilmap[int(codes[i])]},"
                f"{sand[i]:.6f},{silt[i]:.6f},{clay[i]:.6f}\n"
            )
    print(f"== wrote {len(idx)} rows -> {args.out}")

    h = HAINICH_CELL
    print(f"== Hainich ({h}): code={codes[h]} {soilmap.get(int(codes[h]), 'NONE')} "
          f"sand={sand[h]:.3f} silt={silt[h]:.3f} clay={clay[h]:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
