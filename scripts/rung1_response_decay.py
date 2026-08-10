#!/usr/bin/env python3
"""RUNG 1 — WHY the recursion kills the warming response: response decay and variance collapse vs LEAD TIME.

ADR 0113 measured that making the count feed itself leaves the LEVEL alone (bias < 2 %, RMSE saturating) while
the area-weighted global response ratio goes from +0.707 to **−0.226**. It left one open question (§6): is the
recursed prediction *regressing to a conditional mean*? Those two possibilities need different fixes —

  * **variance collapse** (the prediction's own spread shrinks with lead time while its mean stays right)
    ⇒ the fix is a variance-preserving predictor: predict the ensemble expectation explicitly, or sample the
    conditional distribution, rather than train a better conditional mean;
  * **spread preserved but decorrelated** ⇒ the fix is in the count model's conditioning, not its output form.

and the ANSWER IS ALREADY ON DISK. No forest refit, no new model run: the arm's own predictions plus the proven
(Cell, Patch, Year) keys are enough.

WHAT IT COMPUTES, all on the count table's OWN seed-1 truth (`y.f64`), which is the basis `score_counts` calls
"slope vs the table's own truth" — the two-seed deattenuation is not defined on a lead-restricted subset, and the
area-weighted aggregate ratio does not need it:

  1. **Response decay** — for each horizon k, restrict to rows at lead <= k, take the per-(Cell, scenario) mean,
     difference the scenarios, and report the AREA-WEIGHTED aggregate ratio (ONE definition, ADR 0111 §5b) plus
     the latitude bands. k = 1 reproduces the one-step arm by construction; the curve says over what horizon the
     emulator's own count still carries a warming signal — which is the number an ESM run actually needs.
  2. **Variance vs lead time** — at each exact lead s: sd(pred), sd(truth), their correlation, and the mean.
     A collapsing sd(pred) with a flat mean is the regression-to-the-mean signature.

Usage (SLURM; EXPORT every knob — sbatch_python.sh forwards only a fixed list, CLAUDE.md §9):
    export ARM=/p/tmp/jamirp/emulator_global/rung1_count_arm_a1
    export KEYS=/p/tmp/jamirp/emulator_global/rung1_keys_t8
    export OUT=/p/tmp/jamirp/emulator_global/rung1_response_decay.csv
    NCPUS=24 TIME=01:00:00 scripts/sbatch_python.sh S-decay scripts/rung1_response_decay.py
Env: ARM (arm dir with preds_oos.f64 + cells.i64 + scenario tag + y.f64), KEYS, OUT (CSV),
     REF (optional second arm dir scored on the same rows — e.g. the one-step production table, for a control),
     HORIZONS (default "1,2,3,5,10,20,40,80"), NPATCH (25), SNR_MIN (3.0).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import polars as pl

BASE = "/p/tmp/jamirp/emulator_global"
ARM = Path(os.environ.get("ARM", f"{BASE}/rung1_count_arm_a1"))
KEYS = Path(os.environ.get("KEYS", f"{BASE}/rung1_keys_t8"))
REF = os.environ.get("REF", f"{BASE}/slow_count_pooled_w20_t8").strip()
OUT = Path(os.environ.get("OUT", f"{BASE}/rung1_response_decay.csv"))
HORIZONS = [int(h) for h in os.environ.get("HORIZONS", "1,2,3,5,10,20,40,80").split(",")]
NPATCH = float(os.environ.get("NPATCH", "25"))
SNR_MIN = float(os.environ.get("SNR_MIN", "3.0"))
LATLON = f"{BASE}/tables/cell_latlon.txt"
LAT_BANDS = [("tropical", 0.0, 23.5), ("subtropical", 23.5, 35.0), ("temperate", 35.0, 50.0),
             ("boreal", 50.0, 90.1)]

ROWS: list[dict] = []


def read_manifest(d: Path) -> dict[str, str]:
    man: dict[str, str] = {}
    for ln in (d / "manifest.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            man[k] = v
    return man


def load_latlon() -> pl.DataFrame:
    rows = []
    for ln in Path(LATLON).read_text().splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        p = ln.split()
        rows.append((int(p[0]), float(p[3]), float(p[4])))
    d = pl.DataFrame(rows, schema=["Cell", "lat", "lon"], orient="row")
    w = np.clip(np.cos(np.deg2rad(d["lat"].to_numpy())), 0.0, None)
    return d.with_columns(pl.Series("w", w))


def lead_index(scen: np.ndarray, cells: np.ndarray, patches: np.ndarray, years: np.ndarray) -> np.ndarray:
    """1-based position of each row within its (scenario, Cell, Patch) run of CONSECUTIVE years.

    Identical chain definition to `scripts/rung1_count_recursion_arm.jl` — a break wherever the scenario, cell
    or patch changes, or the year is not the previous year + 1 — so `lead == 1` is exactly the row that was
    handed LPJmL-FIT's own previous-year count.
    """
    n = scen.size
    key = ((scen * 67421 + cells) * 64 + patches) * 4096 + years
    ordr = np.argsort(key, kind="stable")
    s, c, p, y = scen[ordr], cells[ordr], patches[ordr], years[ordr]
    brk = np.empty(n, dtype=bool)
    brk[0] = True
    brk[1:] = (s[1:] != s[:-1]) | (c[1:] != c[:-1]) | (p[1:] != p[:-1]) | (y[1:] != y[:-1] + 1)
    # position within run = index minus the index of the run's first row
    idx = np.arange(n)
    start = np.maximum.accumulate(np.where(brk, idx, -1))
    lead_sorted = (idx - start + 1).astype("<i4")
    out = np.empty(n, dtype="<i4")
    out[ordr] = lead_sorted
    return out


def band_ratios(cellv, dp, dt, ll) -> dict:
    """AREA-WEIGHTED prediction/truth response ratio, GLOBAL + per latitude band. ONE definition (ADR 0111)."""
    t = (pl.DataFrame({"Cell": cellv, "dp": dp, "dt": dt})
         .join(ll.select(["Cell", "lat", "w"]), on="Cell", how="inner"))
    lat, w, a, b = t["lat"].to_numpy(), t["w"].to_numpy(), t["dp"].to_numpy(), t["dt"].to_numpy()
    out = {}
    for name, lo, hi in [("GLOBAL", 0.0, 90.1)] + LAT_BANDS:
        m = (np.abs(lat) >= lo) & (np.abs(lat) < hi)
        if m.sum() < 50:
            continue
        ww = w[m]
        num = float((ww * a[m]).sum() / ww.sum())
        den = float((ww * b[m]).sum() / ww.sum())
        # S/N of the TRUTH's band response: |weighted mean| / its own weighted standard error
        se = float(np.sqrt((ww ** 2 * (b[m] - den) ** 2).sum()) / ww.sum())
        snr = abs(den) / se if se > 0 else np.inf
        out[name] = (num / den if den else np.nan, int(m.sum()), num, den, snr)
    return out


def fmt(br: dict) -> str:
    return "  ".join(f"{k} " + (f"{v[0]:+.2f}" if v[4] >= SNR_MIN else "n/d") for k, v in br.items())


def main() -> int:
    man = read_manifest(ARM)
    n = int(man["n"])
    scen_file = man.get("scenario_tag", "scenario.i64")
    cells = np.fromfile(ARM / "cells.i64", dtype="<i8")
    scen = np.fromfile(ARM / scen_file, dtype="<i8")
    y = np.fromfile(ARM / "y.f64", dtype="<f8")
    pr = np.fromfile(ARM / "preds_oos.f64", dtype="<f8")
    years = np.fromfile(KEYS / "years.i64", dtype="<i8")
    patches = np.fromfile(KEYS / "patches.i64", dtype="<i8")
    for nm, arr in [("cells", cells), ("scen", scen), ("y", y), ("pred", pr), ("years", years),
                    ("patches", patches)]:
        if arr.size != n:
            raise SystemExit(f"FATAL: {nm} has {arr.size} rows, manifest says {n}")
    ref = np.fromfile(Path(REF) / "preds_oos.f64", dtype="<f8") if REF else None
    if ref is not None and ref.size != n:
        raise SystemExit(f"FATAL: REF preds has {ref.size} rows, expected {n}")

    keyed = years >= 0
    print(f"== ARM={ARM.name}  n={n:,}  keyed={keyed.sum():,}  REF={Path(REF).name if REF else '(none)'}")
    lead = lead_index(scen, cells, patches, years)
    print(f"== lead index: min={lead.min()} max={lead.max()} "
          f"mean={lead.mean():.2f}  rows at lead 1: {(lead == 1).sum():,}")

    ll = load_latlon()
    ok = keyed & np.isfinite(pr)

    print("\n--- 1. RESPONSE DECAY: the area-weighted aggregate ratio using only rows at lead <= k ---")
    print("    (k=1 is the one-step arm by construction; truth = the count table's own seed-1 y)")
    print(f"{'k':>4s} {'rows':>13s} {'cells':>7s} {'ARM ratio':>10s} {'REF ratio':>10s}   bands (ARM)")
    for k in HORIZONS:
        m = ok & (lead <= k)
        if m.sum() < 1000:
            continue
        cols = {"Cell": cells[m], "s": scen[m], "y": y[m] / NPATCH, "p": pr[m] / NPATCH}
        if ref is not None:
            cols["r"] = ref[m] / NPATCH
        g = pl.DataFrame(cols).group_by(["Cell", "s"]).agg(pl.all().mean())
        h = g.filter(pl.col("s") == 0).drop("s")
        s_ = g.filter(pl.col("s") == 1).drop("s")
        j = h.join(s_, on="Cell", how="inner", suffix="_ssp")
        cellv = j["Cell"].to_numpy()
        dt = (j["y_ssp"] - j["y"]).to_numpy()
        dp = (j["p_ssp"] - j["p"]).to_numpy()
        br = band_ratios(cellv, dp, dt, ll)
        gr = br.get("GLOBAL", (np.nan,) * 5)
        rr = np.nan
        if ref is not None:
            dr = (j["r_ssp"] - j["r"]).to_numpy()
            rb = band_ratios(cellv, dr, dt, ll)
            rr = rb["GLOBAL"][0] if rb["GLOBAL"][4] >= SNR_MIN else np.nan
        print(f"{k:4d} {int(m.sum()):13,d} {len(cellv):7,d} {gr[0]:10.3f} {rr:10.3f}   {fmt(br)}")
        for b, (ratio, nb, num, den, snr) in br.items():
            ROWS.append(dict(section="response_decay", horizon=k, band=b, n_cells=nb, arm=ARM.name,
                             pred_response=num, truth_response=den, truth_snr=snr,
                             ratio=ratio if snr >= SNR_MIN else None,
                             ref_ratio=rr if b == "GLOBAL" else None))

    print("\n--- 2. VARIANCE VS LEAD TIME (is the recursion regressing to a conditional mean?) ---")
    print(f"{'lead':>5s} {'rows':>12s} {'mean(pred)':>11s} {'mean(y)':>9s} {'sd(pred)':>9s} {'sd(y)':>8s} "
          f"{'sd ratio':>9s} {'corr':>7s} {'REF sd ratio':>13s}")
    for s in sorted({1, 2, 3, 4, 5, 8, 12, 20, 30, 40, 60, 80} & set(range(1, int(lead.max()) + 1))):
        m = ok & (lead == s)
        if m.sum() < 1000:
            continue
        a, b = pr[m] / NPATCH, y[m] / NPATCH
        sda, sdb = float(a.std()), float(b.std())
        cor = float(np.corrcoef(a, b)[0, 1])
        rsd = np.nan
        if ref is not None:
            rsd = float((ref[m] / NPATCH).std()) / sdb if sdb else np.nan
        print(f"{s:5d} {int(m.sum()):12,d} {a.mean():11.4f} {b.mean():9.4f} {sda:9.4f} {sdb:8.4f} "
              f"{sda / sdb if sdb else np.nan:9.4f} {cor:7.4f} {rsd:13.4f}")
        ROWS.append(dict(section="variance_vs_lead", horizon=s, band="ALL", n_cells=int(m.sum()),
                         arm=ARM.name, mean_pred=float(a.mean()), mean_truth=float(b.mean()),
                         sd_pred=sda, sd_truth=sdb, sd_ratio=sda / sdb if sdb else None, corr=cor,
                         ref_sd_ratio=rsd))

    pl.DataFrame(ROWS, infer_schema_length=None).write_csv(OUT)
    print(f"\nwrote {len(ROWS)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
