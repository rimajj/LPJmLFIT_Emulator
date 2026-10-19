#!/usr/bin/env python3
"""clu_emu.py -- training data for the WARMING-RESPONSE PROOF (ADR 0342): clustered runs of the merged LPJmL-FIT
model with NITROGEN ON (no phosphorus) and TRANSIENT CO2, made with the lpjml-fit tooling
(/home/jamirp/lpjml-fit/scripts/clustered, used unchanged; this script only prepares what it reads).

Stages:
  grid    a REPRESENTATIVE grid for the owner's 674 regions: ONE real cell per region, run with 25 forest patches
          (owner 2026-10-15: representative mode = fewer cells, 25 patches each; distributed mode gave 1 patch).
          The cell is the FIRST of the region's 25 randomly drawn members in the existing distributed grid
          (k674_lowrank_hist_dist25_seed1) that is not a repeated slot -- i.e. one random member, the package's
          own representative='random' design. Written in the distributed grid's file layout (a .grid.clm + a
          cluster_distributed_mapping_674.csv with one row per region) so cut_inputs.py / cut_scenario.py read
          it unchanged; with no repeated cell every NetCDF input is also found at its true coordinate.
  hook <settings file>
          the CONFIG_HOOK clustered_run.sh calls: rewrites the transient (FROM_RESTART) output list to the lean set
          the emulator trains on -- per-tree table, stand (fpc_stand, lai_stand, vegc, agb), carbon pools, DAILY
          water/carbon fluxes + snow + root-zone water as per-cell binary ("raw" + .json, ~1 MB per variable-year
          instead of ~300 MB on the global lat/lon grid), monthly whc_nat. Drops the trait histograms (they made a
          run ~650 GB).
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import numpy as np

CLU = Path("/p/projects/reformit/Jamir/lpjml-fit-clustered")
DIST = CLU / "grids" / "k674_lowrank_hist_dist25_seed1"
REP = CLU / "grids" / "k674_lowrank_hist_rep1_seed1"


def stage_grid() -> int:
    sys.path.insert(0, "/home/jamirp/lpjml-fit/scripts/clustered")
    from cut_inputs import grid_coords, key, patch_ncell, read_header

    if (REP / "clm_files").exists():
        sys.exit(f"{REP} exists; never overwrite a grid in place")
    (gfile,) = sorted((DIST / "clm_files").glob("*.grid.clm"))
    (mfile,) = sorted((DIST / "nc_files").glob("cluster_distributed_mapping_*.csv"))
    rows = list(csv.DictReader(open(mfile)))
    xy = grid_coords(gfile)
    slot_of = {key(lo, la): i for i, (lo, la) in enumerate(xy)}
    chosen = {}
    for r in rows:  # mapping order = draw order within each region
        c = r["cluster_label"]
        same = key(float(r["grid_longitude"]), float(r["grid_latitude"])) == key(
            float(r["original_longitude"]), float(r["original_latitude"]))
        if c not in chosen and same:
            chosen[c] = r
    labels = sorted({r["cluster_label"] for r in rows}, key=lambda s: int(float(s)))
    missing = [c for c in labels if c not in chosen]
    assert not missing, f"regions without a non-repeated member: {missing}"
    sel = [chosen[c] for c in labels]
    slots = np.array([slot_of[key(float(r["grid_longitude"]), float(r["grid_latitude"]))] for r in sel])
    assert len(set(slots.tolist())) == len(slots) == 674
    (REP / "clm_files").mkdir(parents=True)
    (REP / "nc_files").mkdir()
    h, off = read_header(gfile)
    raw = open(gfile, "rb").read()
    width = (len(raw) - off) // (h["ncell"] * 2)
    data = np.frombuffer(raw[off:], dtype=np.dtype(f"V{width}")).reshape(h["ncell"], 2)
    out = REP / "clm_files" / gfile.name.replace("dist", "rep")
    with open(out, "wb") as fh:
        fh.write(patch_ncell(raw[:off], len(slots)))
        np.ascontiguousarray(data[slots]).tofile(fh)
    with open(REP / "nc_files" / mfile.name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(sel)
    got = grid_coords(out)
    want = np.array([[float(r["grid_longitude"]), float(r["grid_latitude"])] for r in sel])
    assert np.abs(got - want).max() < 0.01, "grid coordinates do not match the chosen members"
    (REP / "README.txt").write_text(
        "Representative grid for ADR 0342 (esm_land_emulator scripts/clu_emu.py grid): one real cell per region\n"
        "of "
        f"{DIST.name} (first non-repeated drawn member = a random member), {len(slots)} cells, npatch 25.\n"
        "The mapping CSV keeps the distributed file name so cut_inputs.py reads it unchanged.\n")
    print(f"grid {out}: {len(slots)} cells, coordinates checked; mapping {REP / 'nc_files' / mfile.name}")
    print(f"lat range {want[:, 1].min():.2f}..{want[:, 1].max():.2f}")
    return 0


# ------------------------------------------------------------------------------------------------ output hook
CDF = ["grid", "fpc_stand", "lai_stand", "vegc", "agb", "soilc", "litc", "firec", "rh"]  # rh monthly; rest annual
DAILY = ["gpp", "npp", "transp", "evap", "interc", "runoff", "prec", "pet", "swe", "rootmoist"]
FILE = {"fpc_stand": "fpc", "lai_stand": "lai", "rh": "mrh"}


def lean_outputs() -> str:
    lines = ['    { "id" : "ind", "file" : { "fmt" : "txt", "name" : "output/ind_historical.csv" }},',
             '    { "id" : "globalflux", "file" : { "fmt" : "txt", "name" : "output/globalflux_historical.csv"}},']
    for v in CDF:
        nm = f"output/{FILE.get(v, v)}_historical.nc"
        lines.append(f'    {{ "id" : "{v}", "file" : {{ "fmt" : "cdf", "name" : "{nm}"}}}},')
    lines.append('    { "id" : "whc_nat", "file" : { "fmt" : "raw", "name" : "output/whc_nat_historical.bin"}},')
    for v in DAILY:
        lines.append(f'    {{ "id" : "{v}", "file" : {{ "fmt" : "raw", "timestep" : "daily", '
                     f'"name" : "output/d_{v}_historical.bin"}}}},')
    lines[-1] = lines[-1].rstrip(",")
    return "\n".join(lines)


def stage_hook(path: str) -> int:
    p = Path(path)
    s = p.read_text()
    o = s.index('"output"')  # the first output list is the transient one (#ifdef FROM_RESTART ... #else)
    a = s.rindex("#ifdef FROM_RESTART", 0, o)
    b = s.index("#else", o)
    blk = s[a:b]
    m = re.search(r'"output"\s*:\s*\[(.*?)\n\s*\]', blk, flags=re.S)
    assert m, "no output list in the FROM_RESTART block"
    new_blk = blk[: m.start(1)] + "\n" + lean_outputs() + "\n" + blk[m.end(1):]
    s = s[:a] + new_blk + s[b:]
    p.write_text(s)
    blk2 = s[a: s.index("#else", s.index('"output"', a))]
    ids = re.findall(r'"id"\s*:\s*"([a-z_0-9]+)"', blk2)
    assert ids == ["ind", "globalflux", *CDF, "whc_nat", *DAILY], ids
    assert "_mass" not in blk2 and "_ind_" not in blk2
    print(f"hook: {p.name}: transient output list -> {len(ids)} entries ({', '.join(ids)})")
    return 0


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else ""
    if st == "grid":
        sys.exit(stage_grid())
    if st == "hook":
        sys.exit(stage_hook(sys.argv[2]))
    if len(sys.argv) == 2 and sys.argv[1].endswith((".cjson", ".js")):  # called as CONFIG_HOOK <settings file>
        sys.exit(stage_hook(sys.argv[1]))
    print(__doc__)
    sys.exit(2)
