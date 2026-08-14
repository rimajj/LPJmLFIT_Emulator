#!/usr/bin/env python3
"""Price item (c2) of line M's photosynthesis shortlist: the water filter's SOIL-TEMPERATURE gate.

WHY THIS EXISTS (line M, rung 3; `residual-diagnosis` §17 -- "a day count is not a magnitude").
The C forces the GSI water-phenology filter fully OPEN while the topsoil is cold:

    phenology_gsi.c:67   if(soil->temp[0] < 10) pft->phen_gsi.wscal = 1;   /* else the sigmoid */

F_diff's `rollout_daily_canopy` passes AIR temperature into that slot (`fdiff.jl:2220` hands
`f.temp` to `phenology_gsi_step`'s `soiltemp` argument; `PhenParams.soiltemp_gate` = 10.0). Soil
lags air, so F opens and closes the gate on the wrong spring and autumn days -- the partial-leaf-day
regime ADR 0136 localised F's GPP error to. ⚠ The C's own comment on that line says "below 5 degree"
while the code tests `< 10`; trust the code (CLAUDE.md §3's comment/code mismatch family).

THE ORACLE. `scripts/run_soiltemp_gate_cells.sh` adds the DAILY `soiltemp1` output, which
`update_daily.c:200` accumulates as `patch->soil.temp[0]` -- the very variable the gate branches on,
carried as the stand's patch-ensemble mean (that averaging is the one basis caveat; see there).
Air temperature comes from the committed `biome_forcing_*.csv` fixtures, i.e. the same forcing F is
driven with, so the two sides of the comparison see one climate.

⚠ THE SIGN IS NOT ONE-SIGNED, AND THE PREDICTION IS RECORDED HERE BEFORE THE RUN (ADR 0131's rule:
write the prediction into the harness, not into the ADR afterwards). The two flip directions push
F's leaf display OPPOSITE ways:

  * SPRING-type flip (air >= 10, soil < 10): the C forces the filter OPEN (=1); F applies the
    sigmoid, which is <= 1. ⇒ F's `phen` is TOO LOW, F absorbs LESS.
  * AUTUMN-type flip (air < 10, soil >= 10): the C applies the sigmoid; F forces OPEN.
    ⇒ F's `phen` is TOO HIGH, F absorbs MORE.

So the net term's sign is a property of which direction carries more light, per cell -- it is NOT
derivable from the mechanism, and the two directions partly cancel. Prediction recorded before the
run: the spring-type flip dominates on light, because at equal air temperature a spring day is
brighter than an autumn one at these latitudes and the soil's thermal lag is in the same direction
all year. Whichever way it lands, read the result next to ADR 0135/0136's count of four independent
faithful terms that all move F's absorption DOWN while its GPP measures ABOVE the C's.

THREE DAMPENERS, EACH OF WHICH MUST BE APPLIED BEFORE A DAY COUNT BECOMES A MAGNITUDE:

 1. **The filter is a LOW-PASS, not the gate.** The gate sets the filter's TARGET; the state moves
    `f += (target - f) * tau`. So an N-day flip run moves the filter by at most `1 - (1-tau)^N` of
    the way, and `wscal_tau` spans **0.01 to 0.44** across the tree PFTs (id 1 and id 4 are 0.01,
    i.e. a ~100-day time constant -- a week-long flip moves those filters by ~7 %). A per-cell
    magnitude therefore needs that cell's own PFT composition, which this script reads.
 2. **The swing is `1 - sigma`, not 1.** A flipped day only matters to the extent the water filter
    would have been CLOSED on it, and `1` is the upper bound of that. Every magnitude here is
    therefore an UPPER BOUND, labelled as one -- closing it needs the realised daily water
    availability, which only F's own rollout carries (item (c1)'s Stage C).
 3. **`phen` is a PRODUCT of four filters.** A day when `tmin` or `light` is already ~0 cannot be
    rescued or spoiled by the water filter. Not corrected for here; it biases every number DOWN,
    which is the safe direction for an upper bound but must be said.

Traps handled: the `.nc` is 20 noleap years from `restart_1999` and the forcing fixture covers
2010-2019, so the two are aligned on (year, doy) rather than by position; grass rows are excluded
from the composition read via `Type <= 6` AND `D95max > 0` (ADR 0110); output goes to stdout and
/p/tmp, never to a committed fixture.

Usage:  python3 scripts/diagnose_phenology_soiltemp_gate.py
"""

from __future__ import annotations

import os
import sys

import netCDF4 as nc
import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from extract_biome_forcing import BIOMES  # noqa: E402  (repo-root path set above)

RUN_ROOT = "/p/tmp/jamirp/esm_land_daily"
RUNTAG = "M_soiltemp"
Y0, Y1 = 2000, 2019           # the run window
SCORE_Y0, SCORE_Y1 = 2010, 2019   # the window the committed forcing fixtures cover
GATE = 10.0                   # `phenology_gsi.c:67` / `PhenParams.soiltemp_gate`
IND = "/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet"

# `wscal_tau` per tree PFT, verbatim from `FDiff.pft_phenparams` (src/fdiff.jl:1524-1548).
WSCAL_TAU = {0: 0.44, 1: 0.01, 2: 0.1, 3: 0.1, 4: 0.01, 5: 0.1, 6: 0.8}


def read_soiltemp(name: str, cell: int) -> np.ndarray:
    d = f"{RUN_ROOT}/daily_{Y0}_{Y1}_{RUNTAG}_{name}_c{cell}_seed1/output/d_soiltemp1.nc"
    with nc.Dataset(d) as ds:
        v = np.asarray(ds.variables["soiltemp1"][:]).reshape(-1)
    exp = (Y1 - Y0 + 1) * 365
    assert v.size == exp, f"{name}: expected {exp} daily values, got {v.size}"
    return v


def read_forcing(name: str) -> pl.DataFrame:
    p = f"{REPO}/test/testitems/references/biome_forcing_{name}.csv"
    # PIN the dtypes: polars infers from the first rows and `precip` starts with whole numbers at
    # some cells, so inference calls it i64 and then dies on the first fractional value (the same
    # trap CLAUDE.md §3 records for the `ind` TXT reader's `mort_*` columns).
    return pl.read_csv(
        p,
        comment_prefix="#",
        schema_overrides={
            "year": pl.Int32, "doy": pl.Int32, "temp": pl.Float64, "swdown": pl.Float64,
            "lwnet": pl.Float64, "precip": pl.Float64, "huss": pl.Float64,
            "daylength": pl.Float64, "co2": pl.Float64,
        },
    ).select(["year", "doy", "temp", "swdown"])


def composition(cell: int) -> dict[int, int]:
    df = (
        pl.scan_parquet(IND)
        .filter(
            (pl.col("Cell") == cell)
            & (pl.col("Type") <= 6)
            & (pl.col("D95max") > 0)
            & (pl.col("isdead") == 0)
            & (pl.col("Year") >= SCORE_Y0)
        )
        .group_by("Type")
        .len()
        .collect()
    )
    return dict(zip(df["Type"].to_list(), df["len"].to_list(), strict=True))


def runs(mask: np.ndarray) -> list[int]:
    """Lengths of the contiguous True runs in `mask`."""
    out, cur = [], 0
    for m in mask:
        if m:
            cur += 1
        elif cur:
            out.append(cur)
            cur = 0
    if cur:
        out.append(cur)
    return out


def main() -> int:
    print("# GSI water-filter SOIL-TEMPERATURE gate audit — item (c2)")
    print(f"# gate: the C forces the filter OPEN while soil.temp[0] < {GATE} degC; F uses AIR temp")
    print(f"# oracle: daily `soiltemp1` (= patch-mean soil.temp[0]), scored {SCORE_Y0}-{SCORE_Y1}")
    print()

    per_cell = {}
    for name, cell in BIOMES.items():
        st_all = read_soiltemp(name, cell)
        fc = read_forcing(name)
        years = np.repeat(np.arange(Y0, Y1 + 1), 365)
        doys = np.tile(np.arange(1, 366), Y1 - Y0 + 1)
        sel = (years >= SCORE_Y0) & (years <= SCORE_Y1)
        pairs = zip(years[sel], doys[sel], strict=True)
        key = {(int(y), int(d)): i for i, (y, d) in enumerate(pairs)}
        st = st_all[sel]

        air = np.full(st.size, np.nan)
        sw = np.full(st.size, np.nan)
        for y, d, t, s in fc.iter_rows():
            i = key.get((int(y), int(d)))
            if i is not None:
                air[i], sw[i] = t, s
        assert not np.isnan(air).any(), f"{name}: forcing does not cover {SCORE_Y0}-{SCORE_Y1}"

        c_open = st < GATE                 # the C's verdict: filter forced OPEN
        f_open = air < GATE                # F's verdict on air temperature
        spring = c_open & ~f_open          # C open, F applies sigmoid ⇒ F too LOW
        autumn = ~c_open & f_open          # C applies sigmoid, F open ⇒ F too HIGH
        per_cell[name] = dict(
            st=st, air=air, sw=sw, spring=spring, autumn=autumn,
            c_open=c_open, comp=composition(cell),
        )

    # ── Panel 0 — the lag itself ───────────────────────────────────────────────────────────────
    print("## Panel 0 — the soil-vs-air lag (the mechanism), and how often each side is cold")
    print(f"{'cell':<22}{'mean(soil-air)':>15}{'sd':>7}{'lag_d':>7}"
          f"{'%d soil<10':>11}{'%d air<10':>10}")
    for name, r in per_cell.items():
        diff = r["st"] - r["air"]
        lag = _best_lag(r["air"], r["st"])
        print(
            f"{name:<22}{diff.mean():>15.2f}{diff.std():>7.2f}{lag:>7d}"
            f"{100 * r['c_open'].mean():>11.1f}{100 * (r['air'] < GATE).mean():>10.1f}"
        )
    print()

    # ── Panel A — the flips, by direction ─────────────────────────────────────────────────────
    print("## Panel A — GATE-VERDICT FLIPS by direction. `spring` = C open / F closed (F too LOW);")
    print("##   `autumn` = C closed / F open (F too HIGH). Shares are of all scored days.")
    print(f"{'cell':<22}{'%spring':>9}{'%autumn':>9}{'%any':>7}"
          f"{'maxrun_sp':>11}{'maxrun_au':>11}")
    for name, r in per_cell.items():
        rs, ra = runs(r["spring"]), runs(r["autumn"])
        print(
            f"{name:<22}{100 * r['spring'].mean():>9.2f}{100 * r['autumn'].mean():>9.2f}"
            f"{100 * (r['spring'] | r['autumn']).mean():>7.2f}"
            f"{(max(rs) if rs else 0):>11d}{(max(ra) if ra else 0):>11d}"
        )
    print()

    # ── Panel B — LIGHT-weighted, which is the magnitude (§17 step 3) ─────────────────────────
    print("## Panel B — the same flips weighted by the quantity the gate acts on (absorbed light,")
    print("##   first order ∝ swdown). This is the UPPER BOUND on the annual assimilation at")
    print("##   stake: it assumes the water filter would be FULLY CLOSED on every flipped day and")
    print("##   ignores that `phen` is a product of four filters (both biases are stated in the")
    print("##   module docstring). `net` = spring − autumn = the signed direction of F's error.")
    print(f"{'cell':<22}{'%light_sp':>11}{'%light_au':>11}{'%light_net':>12}  sign of F's error")
    for name, r in per_cell.items():
        tot = r["sw"].sum()
        ls = 100 * r["sw"][r["spring"]].sum() / tot
        la = 100 * r["sw"][r["autumn"]].sum() / tot
        net = ls - la
        sign = "F absorbs LESS" if net > 0 else ("F absorbs MORE" if net < 0 else "none")
        print(f"{name:<22}{ls:>11.3f}{la:>11.3f}{net:>12.3f}  {sign}")
    print()

    # ── Panel C — the low-pass dampener turns a run length into filter units ──────────────────
    print("## Panel C — DAMPENER 1: the filter is a low-pass, so an N-day flip run moves it by at")
    print("##   most `1-(1-tau)^N`. `tau_eff` is the stem-count-weighted `wscal_tau` of the cell's")
    print("##   own tree PFTs (they span 0.01 to 0.8, a 100-day vs a 1-day time constant).")
    print(f"{'cell':<22}{'dom_pft':>8}{'tau_eff':>9}{'maxrun':>8}"
          f"{'resp@maxrun':>13}{'resp@median':>13}")
    for name, r in per_cell.items():
        comp = r["comp"]
        n = sum(comp.values())
        tw = sum(WSCAL_TAU[p] * c for p, c in comp.items() if p in WSCAL_TAU)
        tau = tw / n if n else float("nan")
        dom = max(comp, key=comp.get) if comp else -1
        allruns = runs(r["spring"] | r["autumn"])
        mx = max(allruns) if allruns else 0
        md = int(np.median(allruns)) if allruns else 0
        print(
            f"{name:<22}{dom:>8}{tau:>9.3f}{mx:>8d}"
            f"{(1 - (1 - tau) ** mx if mx else 0.0):>13.3f}"
            f"{(1 - (1 - tau) ** md if md else 0.0):>13.3f}"
        )
    print()

    # ── Panel D — verdict, computed here (ADR 0104) ────────────────────────────────────────────
    print("## Panel D — VERDICT. `bound` = the light-weighted |net| share x the low-pass response")
    print("##   at the MEDIAN flip run, i.e. the upper bound after dampener 1. `CANNOT BIND` if")
    print("##   that bound is below 0.1 % of annual light -- ADR 0136's residual is ~3 %, so a")
    print("##   term two orders below it cannot be the compensating error.")
    print(f"{'cell':<22}{'%light_net':>12}{'resp':>8}{'bound_%':>10}  verdict")
    for name, r in per_cell.items():
        tot = r["sw"].sum()
        net = abs(
            100 * r["sw"][r["spring"]].sum() / tot - 100 * r["sw"][r["autumn"]].sum() / tot
        )
        comp = r["comp"]
        n = sum(comp.values())
        tau = sum(WSCAL_TAU[p] * c for p, c in comp.items() if p in WSCAL_TAU) / n if n else 0.0
        allruns = runs(r["spring"] | r["autumn"])
        md = int(np.median(allruns)) if allruns else 0
        resp = 1 - (1 - tau) ** md if md else 0.0
        bound = net * resp
        print(
            f"{name:<22}{net:>12.3f}{resp:>8.3f}{bound:>10.4f}"
            f"  {'CAN BIND' if bound >= 0.1 else 'CANNOT BIND'}"
        )
    return 0


def _best_lag(air: np.ndarray, soil: np.ndarray, maxlag: int = 60) -> int:
    """Lag in days that maximises corr(air shifted forward, soil) — soil follows air."""
    best, bl = -2.0, 0
    for k in range(0, maxlag + 1):
        a = air[: air.size - k] if k else air
        s = soil[k:] if k else soil
        c = float(np.corrcoef(a, s)[0, 1])
        if c > best:
            best, bl = c, k
    return bl


if __name__ == "__main__":
    raise SystemExit(main())
