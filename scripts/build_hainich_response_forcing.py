#!/usr/bin/env python3
"""Build the PER-CELL two-scenario daily forcing + transient boundary the Phase-3A RESPONSE arm needs.

WHY THIS EXISTS. ADR 0049 wired FIT's per-individual mortality hazard into `reconcile_demography!` and
measured it against a matched control — but under CONSTANT forcing, i.e. it measured a LEVEL change, not a
response. FIT's +2432.9 gC/m^3 per-cell wood-density shift (ADR 0046 §1) is a BETWEEN-SCENARIO difference
(historic run vs ssp370 run), so the question Phase 3A exists to answer needs the emulator run under BOTH
climates and the two differences differenced. That needs real per-year forcing for both scenarios at one
cell, which is what this script extracts.

WHAT IT PRODUCES

  (a) `<OUT_DIR>/<scenario>_<cell>_daily.csv`  — NOT committed (it is data; ~0.9 MB/scenario, and the .clm
      sources are 4-12 GB each). Columns/units are byte-compatible with the committed
      `hainich_forcing_2010.csv`: `year,doy,temp,swdown,lwnet,precip,huss,co2`
      (degC, W/m2, W/m2 NET longwave, mm/day, kg/kg, ppm). `daylength` is NOT emitted — the coupled
      harness's `AtmForcing` does not consume it.
  (b) `test/testitems/references/S_hainich_response_boundary.csv` (or, for `SITE=<name>`,
      `S_response_boundary_<name>.csv`) — COMMITTED, 1 row per (scenario, year):
      the ADR-0026 trailing-W transient boundary axes (`gdd5`, `tas_cold_month`) that
      `FluxDrivenSlowEmulator`'s `boundary_series` consumes, plus `co2` and the five per-year forcing means
      that let any later session verify (a) was rebuilt from the same source without shipping the daily file.

THE SCENARIO PAIR IS FIT's OWN CONTRAST, DELIBERATELY — INCLUDING ITS CONFOUNDS.
`historic` = the observational `*_test.clm` (1901-2019) with the real rising CO2; `ssp370` = the
MPI-ESM1-2-HR ssp370 files (2015-2100) with CO2 held at 409.63 ppm from 2020 (ADR 0004). Those are exactly
the two forcings the two LPJmL-FIT ground-truth runs used, so the emulator contrast is the analogue of
FIT's +2432.9. It therefore inherits FIT's confounds and they must be quoted with the number, not hidden:
the scenarios come from DIFFERENT data sources (reanalysis vs one GCM, so a model bias enters the
difference alongside the warming) and their mean CO2 differs (~345 vs 409.63 ppm). Default window lengths
are matched at 81 years each so the two arms are differenced at matched year indices.

GATES (all hard exits — the extraction is worthless if any fails)
  1. the historic W=20 boundary for 2000-2019 reproduces the committed `climbuf_hainich_boundary_w20.csv`
     (the fixture ADR 0027's ClimBuf is itself tested against) — this proves the single-cell read path is
     the same quantity as the global `build_transient_boundary.py` build, whose functions it imports rather
     than re-deriving. At a non-Hainich `SITE` the reference is the global trailing-W table itself, which is
     measured to agree with that fixture to 4.88e-06 gdd5 at Hainich, so the substitution is verified;
  1b. the SSP370 W=20 boundary reproduces `cell_year_boundary_ssp370_w20.parquet` for this cell — NEW
     (2026-08-12, ADR 0171) and it caught a real defect: the ssp side had no monthly lead-in, so 19 of its 81
     conditioning years (2020-2038) were a DIFFERENT quantity from the one the DRF/copula were trained on, by
     up to +210 gdd5 (+10.7 %) and +1.94 °C. See `gate_ssp_boundary` for the full account;
  2. the historic 2010 daily row block reproduces this cell's own committed forcing fixture
     (`hainich_forcing_2010.csv`, or `biome_forcing_<site>.csv` for another SITE) — this proves the cell
     index, the YEARCELL decode, the v2/v3 scalar branch and the units all match the fixture the arm was
     measured on;
  3. CO2 is flat at 409.63 from 2020 (ADR 0004) — a rising ssp CO2 would mean the wrong forcing file.

Env: SITE (a name in M_cells.csv; default = Hainich, byte-identical to every earlier run) · CELL (42490;
     refused without SITE if != 42490, so another cell cannot overwrite the Hainich fixture) ·
     HIST_Y0/HIST_Y1 (1939/2019) · SSP_Y0/SSP_Y1 (2020/2100) · W (20) · SSP_LEAD (the ssp monthly start;
     default = max(.clm first year, SSP_Y0-(W-1)) = the trained basis; SSP_LEAD=2020 reproduces the pre-ADR-0171
     fixture bit-for-bit) · OUT_DIR
Run: python3 scripts/build_hainich_response_forcing.py                       (seconds; single-cell memmap reads)
     SITE=tropical_amazon python3 scripts/build_hainich_response_forcing.py  (a second cell)
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_transient_boundary as btb  # noqa: E402  — reuse open_clm / gdd5_tcm / MONTH_BOUNDS

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
G = "/p/projects/waldspektrum/priesner/clustering/global"
CO2_FILE = f"{G}/global_co2_ann_1700_2019_const_2100.txt"

# variable -> (historic .clm, ssp370 .clm). Column names/units follow `hainich_forcing_2010.csv`.
SRC = {
    "temp": (f"{G}/temperature_test.clm", f"{G}/ssp370/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"),
    "swdown": (f"{G}/short_wave_radiation_test.clm", f"{G}/ssp370/rsds_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"),
    "lwnet": (f"{G}/long_wave_radiation_test.clm", f"{G}/ssp370/lwnet_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"),
    "precip": (f"{G}/precipitation_test.clm", f"{G}/ssp370/pr_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"),
    "huss": (f"{G}/humid_test.clm", f"{G}/ssp370/huss_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"),
}
VARS = list(SRC)
SCEN_IDX = {"historic": 0, "ssp370": 1}
# the global trailing-W boundary tables the artifacts were TRAINED against — the per-cell substitute for
# gate 1 at any cell that has no committed ClimBuf fixture, and a NEW ssp370-side gate at every cell
BND_TBL = {
    s: f"/p/tmp/jamirp/emulator_global/tables/cell_year_boundary_{s}_w20.parquet" for s in SCEN_IDX
}
HAINICH = 42490


def resolve_site():
    """`(site, cell)` from `SITE` (a name in the committed `M_cells.csv`) and/or `CELL`.

    ⚠ THE DEFAULT MUST STAY HAINICH AND BYTE-IDENTICAL. Every ADR-0100/0101/0170 response number was
    measured on the `S_hainich_response_boundary.csv` this script writes, so a second cell may not reuse
    that filename — `SITE=<name>` writes `S_response_boundary_<name>.csv` instead and leaves the Hainich
    fixture untouched. Passing `CELL` alone (no `SITE`) keeps the historical behaviour exactly, including
    the output name, which is why `CELL != 42490` without `SITE` is refused rather than silently
    overwriting the Hainich fixture with another cell's boundary."""
    site = os.environ.get("SITE", "").strip()
    cell_env = os.environ.get("CELL", "").strip()
    if not site:
        cell = int(cell_env or HAINICH)
        if cell != HAINICH:
            raise SystemExit(
                f"FATAL: CELL={cell} without SITE would write another cell's boundary into the committed "
                "S_hainich_response_boundary.csv. Pass SITE=<name from M_cells.csv> instead."
            )
        return "temperate_hainich", cell
    rows = read_ref_csv(os.path.join(REFDIR, "M_cells.csv"))
    if site not in rows["name"]:
        raise SystemExit(f"FATAL: SITE={site} is not a name in M_cells.csv ({sorted(set(rows['name']))})")
    i = rows["name"].index(site)
    cell = int(rows["cell"][i])
    if cell_env and int(cell_env) != cell:
        raise SystemExit(f"FATAL: SITE={site} is cell {cell} in M_cells.csv but CELL={cell_env} was passed")
    print(f"== SITE={site} -> cell {cell} (lat {rows['lat'][i]}, lon {rows['lon'][i]}) from M_cells.csv")
    return site, cell


def boundary_ref_path(site, cell):
    """Where the committed boundary fixture for this site goes (Hainich keeps its historical name)."""
    if cell == HAINICH and site == "temperate_hainich":
        return os.path.join(REFDIR, "S_hainich_response_boundary.csv")
    return os.path.join(REFDIR, f"S_response_boundary_{site}.csv")


def read_bnd_table(scen, cell):
    """`{year: (gdd5, tas_cold_month)}` for one cell from the global trailing-W boundary table."""
    import polars as pl

    df = (
        pl.scan_parquet(BND_TBL[scen])
        .filter(pl.col("Cell") == cell)
        .select("Year", "eco_diag_gdd_5", "tas_cold_month")
        .collect()
        .sort("Year")
    )
    if df.height == 0:
        raise SystemExit(f"FATAL: cell {cell} absent from {BND_TBL[scen]}")
    return {int(r[0]): (float(r[1]), float(r[2])) for r in df.iter_rows()}


def read_cell_years(path, cell, y0, y1):
    """Daily values for ONE cell over years `y0..y1` inclusive -> (nyear, 365) float64 in physical units.

    Applies the header's `scalar` (the v2 int16 ssp files are stored as physical x10 — CLAUDE.md §3), and
    reads only the cell's own band block per year, so an 11 GB .clm costs ~365 floats per year."""
    mm, fy, ncell, nbands, sc = btb.open_clm(path)
    if nbands != 365:
        raise SystemExit(f"FATAL: {path} nbands={nbands} (expected 365 noleap)")
    if not (0 <= cell < ncell):
        raise SystemExit(f"FATAL: cell {cell} outside {path} ncell={ncell}")
    navail = mm.shape[0]
    out = np.empty((y1 - y0 + 1, 365), dtype=np.float64)
    for k, Y in enumerate(range(y0, y1 + 1)):
        iY = Y - fy
        if iY < 0 or iY >= navail:
            raise SystemExit(f"FATAL: year {Y} outside {os.path.basename(path)} coverage [{fy}, {fy + navail - 1}]")
        out[k] = np.asarray(mm[iY, cell], dtype=np.float64) * sc
    del mm
    return out


def monthly_means(daily):
    """(nyear, 365) -> (nyear, 12) monthly means in float32, byte-for-byte `build_transient_boundary.py`'s
    `monthly_means_by_year` (which casts the year to float32 BEFORE averaging)."""
    n = daily.shape[0]
    out = np.empty((n, 12), dtype=np.float32)
    for iy in range(n):
        yr = daily[iy].astype(np.float32)
        for m in range(12):
            out[iy, m] = yr[btb.MONTH_BOUNDS[m] : btb.MONTH_BOUNDS[m + 1]].mean()
    return out


def read_co2():
    co2 = {}
    with open(CO2_FILE) as f:
        for ln in f:
            parts = ln.split()
            if len(parts) == 2:
                co2[int(parts[0])] = float(parts[1])
    return co2


def read_ref_csv(path):
    """`{column: [str, ...]}` of a committed reference CSV (skipping `#` comments)."""
    lines = [ln.strip() for ln in open(path) if ln.strip() and not ln.strip().startswith("#")]
    hdr = lines[0].split(",")
    rows = [ln.split(",") for ln in lines[1:]]
    return {h: [r[j] for r in rows] for j, h in enumerate(hdr)}


def gate_boundary(hist_monthly, mon_y0, W, cell):
    """GATE 1 — the historic trailing-W boundary must reproduce the basis the artifacts were trained on.

    At Hainich that basis is the committed `climbuf_hainich_boundary_w20.csv` (unchanged, so every earlier
    run's gate line is reproduced verbatim). At any other cell there is no committed ClimBuf fixture, so the
    reference is the GLOBAL trailing-W table itself — which is the stronger statement of the same claim, and
    is measured to agree with the Hainich fixture to **4.88e-06 gdd5 / 4.91e-10 °C** (float32 print noise) at
    the one cell where both exist, so the substitution is verified rather than assumed."""
    if cell == HAINICH:
        ref = read_ref_csv(os.path.join(REFDIR, "climbuf_hainich_boundary_w20.csv"))
        want = {int(y): (float(ref["gdd5"][j]), float(ref["tas_cold_month"][j])) for j, y in enumerate(ref["year"])}
        src = "climbuf_hainich_boundary_w20.csv"
    else:
        want = read_bnd_table("historic", cell)
        src = f"cell_year_boundary_historic_w20.parquet[cell {cell}]"
    worst = 0.0
    for Y, (wg, wt) in sorted(want.items()):
        iY = Y - mon_y0
        if iY < 0:
            raise SystemExit(f"FATAL: gate year {Y} predates the monthly lead-in start {mon_y0}")
        lo = max(0, iY - W + 1)
        clim = hist_monthly[lo : iY + 1].mean(axis=0).reshape(1, 12)
        g, t = btb.gdd5_tcm(clim)
        worst = max(worst, abs(float(g[0]) - wg), abs(float(t[0]) - wt))
    # the reference is float32 with ~7 significant digits, so an exact float32 match still shows ~1e-5 on a
    # gdd5 of ~1800 and ~1e-3 on the ~10 000 of a tropical cell; anything above that is a different
    # quantity, not a print artefact. Scale the tolerance with the magnitude rather than pinning 1e-3, which
    # would red a correct tropical build.
    tol = max(1.0e-3, 1.0e-6 * max(abs(g) for g, _ in want.values()))
    print(f"== GATE 1 historic boundary vs {src}: worst |diff| = {worst:.3g} over {len(want)} yr (tol {tol:.3g})")
    if worst > tol:
        raise SystemExit(f"FATAL GATE 1: trailing-W boundary does not reproduce the trained basis ({worst:.4g})")


def gate_ssp_boundary(ssp_monthly, mon_y0, W, cell, ssp_y0, ssp_y1):
    """GATE 1b — the SSP370 trailing-W boundary must ALSO reproduce the trained basis. NEW, and it is the
    gate that caught the defect this function exists for.

    ⚠ WHY IT WAS MISSING AND WHAT IT FOUND. The historic side of this script always applied a `W-1` year
    monthly LEAD-IN, and gate 1 above proves it lands on the trained basis. The ssp370 side did **not**, and
    a comment asserted the omission was deliberate — that `build_transient_boundary.py` "accepts the short
    window for 2020-2034 as a documented edge, so replicating it is what keeps this fixture consistent with
    the boundary table the artifacts were TRAINED against". **Measured, that claim was false.** The global
    builder builds its monthly climatology over the WHOLE .clm (`mby`, from its first year 2015) and then
    takes `lo = max(0, iY - W + 1)`, so its 2020 window is 2015-2020; this script's started at 2020, so its
    2020 window was 2020 alone. The two bases differed at Hainich for **2020-2038** — 19 of 81 years — by up
    to **+210 gdd5 (+10.7 %)** and **+1.94 °C** `tas_cold_month`, decaying to exactly 0 from 2039 on.
    That is the ADR-0023 train/inference-shift trap: 19 years of the response arm's conditioning were a
    different quantity from the one the DRF and copula were fitted on. The fix is to give the ssp side the
    same lead-in the historic side always had; this gate makes a regression impossible."""
    want = read_bnd_table("ssp370", cell)
    want = {Y: v for Y, v in want.items() if ssp_y0 <= Y <= ssp_y1}
    if not want:
        raise SystemExit(f"FATAL GATE 1b: the ssp370 boundary table has no years in [{ssp_y0}, {ssp_y1}]")
    worst_g = worst_t = 0.0
    worst_year = None
    for Y, (wg, wt) in sorted(want.items()):
        iY = Y - mon_y0
        lo = max(0, iY - W + 1)
        clim = ssp_monthly[lo : iY + 1].mean(axis=0).reshape(1, 12)
        g, t = btb.gdd5_tcm(clim)
        dg, dt = abs(float(g[0]) - wg), abs(float(t[0]) - wt)
        if dg > worst_g:
            worst_g, worst_year = dg, Y
        worst_t = max(worst_t, dt)
    tol = max(1.0e-3, 1.0e-6 * max(abs(g) for g, _ in want.values()))
    print(
        f"== GATE 1b ssp370 boundary vs cell_year_boundary_ssp370_w20.parquet[cell {cell}]: "
        f"worst |dgdd5| = {worst_g:.3g} (yr {worst_year})  |dtcm| = {worst_t:.3g}  over {len(want)} yr "
        f"(tol {tol:.3g})"
    )
    if max(worst_g, worst_t) > tol:
        msg = (
            f"GATE 1b: the ssp370 boundary is NOT the quantity the artifacts were trained on "
            f"(worst gdd5 {worst_g:.4g} at {worst_year}, tcm {worst_t:.4g}). The usual cause is a missing "
            f"monthly lead-in: the trained basis reaches back into the .clm's own first year, not to SSP_Y0."
        )
        # The ONE legitimate reason to write an off-basis fixture is reproducing a number that was measured
        # on it (ADR 0100/0101/0170 were), and that must be deliberate and loud rather than a silent pass.
        if os.environ.get("ALLOW_UNTRAINED_SSP_BASIS", "0") == "1":
            print(f"⚠⚠ {msg}\n⚠⚠ ALLOW_UNTRAINED_SSP_BASIS=1 ⇒ writing it anyway. Any number measured on "
                  "this fixture is on the PRE-ADR-0171 basis and must say so.")
        else:
            raise SystemExit(f"FATAL {msg}")


def gate_daily_2010(daily, hist_y0, site, cell):
    """GATE 2 — the historic 2010 daily block must reproduce this cell's own committed forcing fixture.

    Hainich uses `hainich_forcing_2010.csv` (unchanged). Any other site uses the committed
    `biome_forcing_<site>.csv`, which carries the same cell's REAL `_test.clm` daily forcing for 2010-2019 in
    the same columns and units — so the cell index, the YEARCELL decode, the v2/v3 scalar branch and the
    units are gated at every site, not only at Hainich."""
    if cell == HAINICH and site == "temperate_hainich":
        ref = read_ref_csv(os.path.join(REFDIR, "hainich_forcing_2010.csv"))
        src = "hainich_forcing_2010.csv"
        sel = slice(None)
    else:
        ref = read_ref_csv(os.path.join(REFDIR, f"biome_forcing_{site}.csv"))
        src = f"biome_forcing_{site}.csv"
        rows = [j for j, y in enumerate(ref["year"]) if int(y) == 2010]
        if len(rows) != 365:
            raise SystemExit(f"FATAL GATE 2: {src} has {len(rows)} rows for 2010, expected 365")
        sel = rows
    iY = 2010 - hist_y0
    if iY < 0:
        raise SystemExit("FATAL: HIST_Y0 > 2010, cannot run gate 2")
    worst = {}
    for v in VARS:
        got = daily[v][iY]
        col = ref[v] if sel == slice(None) else [ref[v][j] for j in sel]
        want = np.array([float(x) for x in col], dtype=np.float64)
        if want.size != 365:
            raise SystemExit(f"FATAL GATE 2: fixture has {want.size} rows, expected 365")
        worst[v] = float(np.max(np.abs(got - want)))
    print(f"== GATE 2 daily 2010 vs {src}: " + "  ".join(f"{v}={worst[v]:.3g}" for v in VARS))
    # the .clm stores these at 0.1 precision (huss at float32), and the fixture prints them verbatim, so an
    # exact match is expected; the tolerance only absorbs the fixture's decimal printing.
    bad = [v for v in VARS if worst[v] > (1.0e-7 if v == "huss" else 5.0e-2)]
    if bad:
        raise SystemExit(f"FATAL GATE 2: {bad} differ from {src} — wrong cell/units/decode")


def main():
    site, cell = resolve_site()
    hist_y0 = int(os.environ.get("HIST_Y0", "1939"))
    hist_y1 = int(os.environ.get("HIST_Y1", "2019"))
    ssp_y0 = int(os.environ.get("SSP_Y0", "2020"))
    ssp_y1 = int(os.environ.get("SSP_Y1", "2100"))
    W = int(os.environ.get("W", "20"))
    out_dir = os.environ.get("OUT_DIR", "/p/tmp/jamirp/emulator_global/S_response_forcing")
    nh, ns = hist_y1 - hist_y0 + 1, ssp_y1 - ssp_y0 + 1
    print(f"== cell={cell}  historic {hist_y0}-{hist_y1} ({nh} yr)  ssp370 {ssp_y0}-{ssp_y1} ({ns} yr)  W={W}")
    if nh != ns:
        print(f"   NOTE: window lengths differ ({nh} vs {ns}) — the arms cannot be differenced at matched year indices")

    co2 = read_co2()
    for Y in list(range(hist_y0, hist_y1 + 1)) + list(range(ssp_y0, ssp_y1 + 1)):
        if Y not in co2:
            raise SystemExit(f"FATAL: year {Y} absent from {CO2_FILE}")
    flat = {co2[Y] for Y in range(2020, ssp_y1 + 1)}
    print(f"== GATE 3 co2 from 2020: {sorted(flat)} ppm  (ADR 0004 expects the single value 409.63)")
    if flat != {409.63}:
        raise SystemExit(f"FATAL GATE 3: ssp370 CO2 is not flat 409.63 ({sorted(flat)}) — wrong forcing file")

    # ── extract, gate, write ────────────────────────────────────────────────────────────────────────────
    daily = {}
    for scen, si in SCEN_IDX.items():
        y0, y1 = (hist_y0, hist_y1) if scen == "historic" else (ssp_y0, ssp_y1)
        daily[scen] = {v: read_cell_years(SRC[v][si], cell, y0, y1) for v in VARS}

    # ── the boundary needs a W-1 year LEAD-IN ON BOTH SCENARIOS, or the first target years get a SHORT
    #    trailing window that is NOT the quantity the artifacts were trained on ─────────────────────────────
    # The historic .clm starts 1901, so a full W-year window is available for every target year >= 1920 and
    # there is no reason to accept the truncated one (measured: without the lead-in, 1939's `tas_cold_month`
    # reads -3.1 °C off a 1-YEAR window instead of a 20-year climatology).
    #
    # ⚠ THE SSP370 SIDE USED TO SKIP THIS, AND THE COMMENT THAT JUSTIFIED IT WAS WRONG (fixed 2026-08-12,
    # ADR 0171). It claimed `build_transient_boundary.py` accepts a short 2020-2034 window so replicating it
    # keeps the fixture consistent with the trained basis. In fact the global builder averages `mby` over the
    # WHOLE .clm from its own first year (2015) — its 2020 window is 2015-2020, while this script's was 2020
    # alone. Measured at Hainich, the two bases differ for 2020-2038 by up to +210 gdd5 (+10.7 %) and
    # +1.94 °C, i.e. 19 of 81 conditioning years the response arm fed the learned model were a different
    # quantity from training. Both scenarios now take the lead-in, clamped to the .clm's own coverage, and
    # GATE 1b below compares the result to the trained table so this cannot regress silently.
    # `SSP_LEAD=<year>` pins the ssp monthly start by hand: `SSP_LEAD=2020` reproduces the pre-fix fixture
    # bit-for-bit, which is how ADR 0100/0101/0170's numbers stay reproducible on their own basis.
    mon_y0 = hist_y0 - (W - 1)
    hist_lead = read_cell_years(SRC["temp"][0], cell, mon_y0, hist_y1)
    hist_monthly = monthly_means(hist_lead)
    _, ssp_fy, _, _, _ = btb.open_clm(SRC["temp"][1])
    ssp_mon_y0 = int(os.environ.get("SSP_LEAD", max(ssp_fy, ssp_y0 - (W - 1))))
    if ssp_mon_y0 < ssp_fy:
        raise SystemExit(f"FATAL: SSP_LEAD={ssp_mon_y0} predates the ssp .clm's first year {ssp_fy}")
    ssp_lead = read_cell_years(SRC["temp"][1], cell, ssp_mon_y0, ssp_y1)
    ssp_monthly = monthly_means(ssp_lead)
    print(
        f"== boundary lead-in: historic monthly from {mon_y0} (full W={W} from {hist_y0}); "
        f"ssp370 monthly from {ssp_mon_y0} (.clm starts {ssp_fy}; full W from {ssp_mon_y0 + W - 1})"
    )
    gate_boundary(hist_monthly, mon_y0, W, cell)
    gate_ssp_boundary(ssp_monthly, ssp_mon_y0, W, cell, ssp_y0, ssp_y1)
    gate_daily_2010(daily["historic"], hist_y0, site, cell)

    os.makedirs(out_dir, exist_ok=True)
    hdr_units = "temp degC, swdown/lwnet W/m2 (lwnet NET), precip mm/day, huss kg/kg, co2 ppm"
    for scen in SCEN_IDX:
        y0, y1 = (hist_y0, hist_y1) if scen == "historic" else (ssp_y0, ssp_y1)
        path = os.path.join(out_dir, f"{scen}_{cell}_daily.csv")
        with open(path, "w") as f:
            f.write(f"# Cell {cell} REAL LPJmL-FIT daily forcing, scenario {scen}, {y0}-{y1}. {hdr_units}.\n")
            f.write(
                "# Built by scripts/build_hainich_response_forcing.py (gated vs "
                + ("hainich_forcing_2010.csv" if cell == HAINICH else f"biome_forcing_{site}.csv")
                + ").\n"
            )
            f.write("year,doy," + ",".join(VARS) + ",co2\n")
            for k, Y in enumerate(range(y0, y1 + 1)):
                c = co2[Y]
                cols = [daily[scen][v][k] for v in VARS]
                for d in range(365):
                    vals = ",".join(f"{c[d]:.8g}" for c in cols)
                    f.write(f"{Y},{d + 1},{vals},{c:.2f}\n")
        print(f"== wrote {path}  ({(y1 - y0 + 1) * 365} rows, {os.path.getsize(path) / 1e6:.2f} MB)")

    # committed boundary + per-year provenance summary
    ref_path = boundary_ref_path(site, cell)
    with open(ref_path, "w") as f:
        f.write(
            f"# Cell {cell} ({site}) two-scenario ADR-0026 transient boundary (trailing W={W}) + per-year forcing means.\n"
            "# The boundary axes are `FluxDrivenSlowEmulator`'s `boundary_series` rows 1:2 (gdd5, tas_cold_month);\n"
            "# soil_depth and the co2 tail entry stay as the artifact's own `boundary` (this file's co2 is the\n"
            "# FORCING co2 the daily file carries, which is a different tail entry — ADR 0004 pins the artifact's).\n"
            "# The five *_mean columns are provenance: they let a later session verify the (uncommitted) daily\n"
            "# file was rebuilt from the same .clm without shipping it. Built by\n"
            "# scripts/build_hainich_response_forcing.py; gdd5/tas_cold_month via build_transient_boundary.py's\n"
            "# own gdd5_tcm, gated against the trained trailing-W basis on BOTH scenarios (gates 1 + 1b).\n"
            f"# ssp370 monthly lead-in starts {ssp_mon_y0} (ADR 0171 — SSP_LEAD=2020 reproduces the pre-fix file).\n"
        )
        f.write("scenario,year,gdd5,tas_cold_month,co2," + ",".join(f"{v}_mean" for v in VARS) + "\n")
        for scen, monthly, m0 in (("historic", hist_monthly, mon_y0), ("ssp370", ssp_monthly, ssp_mon_y0)):
            y0, y1 = (hist_y0, hist_y1) if scen == "historic" else (ssp_y0, ssp_y1)
            for k, Y in enumerate(range(y0, y1 + 1)):
                iY = Y - m0
                lo = max(0, iY - W + 1)
                g, t = btb.gdd5_tcm(monthly[lo : iY + 1].mean(axis=0).reshape(1, 12))
                means = ",".join(f"{daily[scen][v][k].mean():.8g}" for v in VARS)
                f.write(f"{scen},{Y},{float(g[0]):.9g},{float(t[0]):.9g},{co2[Y]:.2f},{means}\n")
    print(f"== wrote {ref_path}  ({nh + ns} rows, {os.path.getsize(ref_path) / 1e3:.1f} kB)")

    # ── the warming signal, so the arm's forcing contrast is on the record ──────────────────────────────
    def m(scen, v):
        return float(daily[scen][v].mean())

    print("\n== FORCING CONTRAST (scenario means over the two windows) — quote these with any response number")
    print(f"   {'var':8s}{'historic':>12s}{'ssp370':>12s}{'delta':>12s}")
    for v in VARS:
        print(f"   {v:8s}{m('historic', v):12.5g}{m('ssp370', v):12.5g}{m('ssp370', v) - m('historic', v):+12.4g}")
    hc = np.mean([co2[Y] for Y in range(hist_y0, hist_y1 + 1)])
    sc_ = np.mean([co2[Y] for Y in range(ssp_y0, ssp_y1 + 1)])
    print(f"   {'co2':8s}{hc:12.5g}{sc_:12.5g}{sc_ - hc:+12.4g}   (FIT's own basis: rising vs flat, ADR 0004)")
    gh, th = btb.gdd5_tcm(hist_monthly[-W:].mean(axis=0).reshape(1, 12))
    gs, ts = btb.gdd5_tcm(ssp_monthly[-W:].mean(axis=0).reshape(1, 12))
    print(
        f"   boundary (last {W} yr of each): gdd5 {float(gh[0]):.1f} -> {float(gs[0]):.1f} "
        f"({float(gs[0]) - float(gh[0]):+.1f})   tas_cold_month {float(th[0]):.3f} -> {float(ts[0]):.3f} "
        f"({float(ts[0]) - float(th[0]):+.3f})"
    )
    print(
        "\n   CAVEATS THAT TRAVEL WITH THE NUMBER: the two scenarios are DIFFERENT DATA SOURCES (reanalysis vs\n"
        "   MPI-ESM1-2-HR), so a GCM bias enters the difference alongside the warming; and mean CO2 differs by\n"
        f"   {sc_ - hc:+.1f} ppm. Both are FIT's own configuration, which is why this pair is the analogue of\n"
        "   FIT's +2432.9 shift — but neither may be dropped when the response is quoted."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
