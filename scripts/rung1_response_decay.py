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
  3. **Drift vs lead, RESOLVED BY SCENARIO** (ADR 0114 §5.3b) — the arm's bias at each exact lead, separately
     for the historic and the ssp370 chains. A drift that is the SAME function of lead in both scenarios
     cancels in the scenario difference and cannot by itself invert the response; one that differs is a
     mechanism for the inversion. Printed with the control's bias beside it.
  4. **The response at MATCHED LEAD DEPTH** (ADR 0114 §5.3b) — the headline ratio pairs a historic mean over
     19-year chains with an ssp370 mean over 80-year chains, so the two scenarios are averaged over different
     lead mixes and any lead-dependent drift enters the difference even if it is scenario-independent. Here
     each cell's scenario means are built lead by lead and only over the leads present in BOTH scenarios,
     with equal weight per lead, so the drift cancels by construction. The gap between this ratio and §1's at
     the same horizon IS the unequal-chain-length artefact; whatever survives is a property of the recursion.

WHY the control's BANDS are printed everywhere (ADR 0114 §5.4): a per-band decay curve with no control is
arm-only, and cannot distinguish "the recursion loses the tropics" from "the tropical band is unresolvable on
these rows for any predictor".

Usage (SLURM; EXPORT every knob — sbatch_python.sh forwards only a fixed list, CLAUDE.md §9):
    export ARM=/p/tmp/jamirp/emulator_global/rung1_count_arm_a1
    export KEYS=/p/tmp/jamirp/emulator_global/rung1_keys_t8
    export OUT=/p/tmp/jamirp/emulator_global/rung1_response_decay.csv
    NCPUS=24 TIME=01:00:00 scripts/sbatch_python.sh S-decay scripts/rung1_response_decay.py
Env: ARM (arm dir with preds_oos.f64 + cells.i64 + scenario tag + y.f64), KEYS, OUT (CSV),
     REF (optional second arm dir scored on the same rows — e.g. the one-step production table, for a control),
     HORIZONS (default "1,2,3,5,10,20,40,80"), SNR_MIN (3.0). Counts are in the table's own stems/patch.
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
#: `n_living` in the count table IS ALREADY A PER-PATCH STEM COUNT (mean 8.28 over the 121 495 658 rows),
#: so nothing here divides by the ensemble size. An earlier version of this script divided by NPATCH a second
#: time, which left every RATIO correct (the factor cancels in numerator and denominator) but made the level
#: panels 25x too small for the "stems/patch" label they carried — ADR 0114's variance table is on that
#: scaling, so its means are 1/25 of the ones printed here while its sd RATIOS and correlations are unchanged.
NPATCH = float(os.environ.get("NPATCH", "1"))  # retained for callers that pass it; no longer applied
SNR_MIN = float(os.environ.get("SNR_MIN", "3.0"))
LATLON = f"{BASE}/tables/cell_latlon.txt"
LAT_BANDS = [("tropical", 0.0, 23.5), ("subtropical", 23.5, 35.0), ("temperate", 35.0, 50.0),
             ("boreal", 50.0, 90.1)]

#: exact leads reported by the per-lead panels. 13-19 are load-bearing: the historic chains stop at 19,
#: so those are the DEEPEST leads at which the two scenarios can be compared at all.
LEADS = {1, 2, 3, 4, 5, 8, 12, 15, 18, 19, 20, 30, 40, 60, 80}

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
    print("    ARM and REF (the control) are scored on the SAME rows and the SAME cells, bands and all")
    print(f"{'k':>4s} {'rows':>13s} {'cells':>7s} {'series':>6s}   bands")
    for k in HORIZONS:
        m = ok & (lead <= k)
        if m.sum() < 1000:
            continue
        cols = {"Cell": cells[m], "s": scen[m], "y": y[m], "p": pr[m]}
        if ref is not None:
            cols["r"] = ref[m]
        g = pl.DataFrame(cols).group_by(["Cell", "s"]).agg(pl.all().mean())
        h = g.filter(pl.col("s") == 0).drop("s")
        s_ = g.filter(pl.col("s") == 1).drop("s")
        j = h.join(s_, on="Cell", how="inner", suffix="_ssp")
        cellv = j["Cell"].to_numpy()
        dt = (j["y_ssp"] - j["y"]).to_numpy()
        dp = (j["p_ssp"] - j["p"]).to_numpy()
        br = band_ratios(cellv, dp, dt, ll)
        print(f"{k:4d} {int(m.sum()):13,d} {len(cellv):7,d} {'ARM':>6s}   {fmt(br)}")
        for b, (ratio, nb, num, den, snr) in br.items():
            ROWS.append(dict(section="response_decay", horizon=k, band=b, n_cells=nb, series="arm",
                             arm=ARM.name, pred_response=num, truth_response=den, truth_snr=snr,
                             ratio=ratio if snr >= SNR_MIN else None))
        if ref is not None:
            dr = (j["r_ssp"] - j["r"]).to_numpy()
            rb = band_ratios(cellv, dr, dt, ll)
            print(f"{'':4s} {'':13s} {'':7s} {'REF':>6s}   {fmt(rb)}")
            for b, (ratio, nb, num, den, snr) in rb.items():
                ROWS.append(dict(section="response_decay", horizon=k, band=b, n_cells=nb, series="ref",
                                 arm=Path(REF).name, pred_response=num, truth_response=den, truth_snr=snr,
                                 ratio=ratio if snr >= SNR_MIN else None))

    print("\n--- 2. VARIANCE VS LEAD TIME (is the recursion regressing to a conditional mean?) ---")
    print(f"{'lead':>5s} {'rows':>12s} {'mean(pred)':>11s} {'mean(y)':>9s} {'sd(pred)':>9s} {'sd(y)':>8s} "
          f"{'sd ratio':>9s} {'corr':>7s} {'REF sd ratio':>13s}")
    for s in sorted(LEADS & set(range(1, int(lead.max()) + 1))):
        m = ok & (lead == s)
        if m.sum() < 1000:
            continue
        a, b = pr[m], y[m]
        sda, sdb = float(a.std()), float(b.std())
        cor = float(np.corrcoef(a, b)[0, 1])
        rsd = np.nan
        if ref is not None:
            rsd = float(ref[m].std()) / sdb if sdb else np.nan
        print(f"{s:5d} {int(m.sum()):12,d} {a.mean():11.4f} {b.mean():9.4f} {sda:9.4f} {sdb:8.4f} "
              f"{sda / sdb if sdb else np.nan:9.4f} {cor:7.4f} {rsd:13.4f}")
        ROWS.append(dict(section="variance_vs_lead", horizon=s, band="ALL", n_cells=int(m.sum()),
                         arm=ARM.name, mean_pred=float(a.mean()), mean_truth=float(b.mean()),
                         sd_pred=sda, sd_truth=sdb, sd_ratio=sda / sdb if sdb else None, corr=cor,
                         ref_sd_ratio=rsd))

    print("\n--- 3. DRIFT VS LEAD, RESOLVED BY SCENARIO (does the drift cancel in the difference?) ---")
    print("    bias = mean(pred - truth) in stems/patch (the units of ADR 0113's lead table), at EXACTLY")
    print("    lead s, historic (h) vs ssp370 (s370). A drift that is EQUAL in the two scenarios cancels in")
    print("    the response; the `diff` column is the part that does NOT cancel.")
    print(f"{'lead':>5s} {'rows h':>11s} {'rows s370':>11s} {'ARM bias h':>11s} {'ARM bias s370':>14s} "
          f"{'ARM diff':>9s} {'REF bias h':>11s} {'REF bias s370':>14s} {'REF diff':>9s}")
    for s in sorted(LEADS & set(range(1, int(lead.max()) + 1))):
        mh = ok & (lead == s) & (scen == 0)
        ms = ok & (lead == s) & (scen == 1)
        if mh.sum() < 1000 or ms.sum() < 1000:
            continue
        bh = float((pr[mh] - y[mh]).mean())
        bs = float((pr[ms] - y[ms]).mean())
        rh = rs = np.nan
        if ref is not None:
            rh = float((ref[mh] - y[mh]).mean())
            rs = float((ref[ms] - y[ms]).mean())
        print(f"{s:5d} {int(mh.sum()):11,d} {int(ms.sum()):11,d} {bh:11.4f} {bs:14.4f} {bs - bh:9.4f} "
              f"{rh:11.4f} {rs:14.4f} {rs - rh:9.4f}")
        ROWS.append(dict(section="drift_by_scenario", horizon=s, band="ALL",
                         n_cells=int(mh.sum() + ms.sum()), arm=ARM.name, bias_historic=bh,
                         bias_ssp370=bs, bias_diff=bs - bh, ref_bias_historic=rh, ref_bias_ssp370=rs,
                         ref_bias_diff=rs - rh))

    print("\n--- 4. THE RESPONSE AT MATCHED LEAD DEPTH (only leads present in BOTH scenarios, equal weight) ---")
    print("    §1 averages historic over ~19-year chains and ssp370 over ~80-year ones, so a lead-dependent")
    print("    drift enters the difference even when it is scenario-independent. Here it cannot.")
    print(f"{'k':>4s} {'rows':>13s} {'cells':>7s} {'leads':>6s} {'series':>6s}   bands")
    base = pl.DataFrame({"Cell": cells[ok], "s": scen[ok], "lead": lead[ok].astype("int64"),
                         "y": y[ok], "p": pr[ok],
                         **({"r": ref[ok]} if ref is not None else {})})
    for k in HORIZONS:
        sub = base.filter(pl.col("lead") <= k)
        if sub.height < 1000:
            continue
        g = sub.group_by(["Cell", "s", "lead"]).agg(pl.all().mean())
        h = g.filter(pl.col("s") == 0).drop("s")
        s_ = g.filter(pl.col("s") == 1).drop("s")
        # the inner join on (Cell, lead) is what enforces the matching: a lead present in only one
        # scenario for that cell contributes to neither side
        j = h.join(s_, on=["Cell", "lead"], how="inner", suffix="_ssp")
        if j.height < 1000:
            continue
        per = j.with_columns([(pl.col("y_ssp") - pl.col("y")).alias("dt"),
                              (pl.col("p_ssp") - pl.col("p")).alias("dp")] +
                             ([(pl.col("r_ssp") - pl.col("r")).alias("dr")] if ref is not None else []))
        # equal weight per matched lead within a cell, then one row per cell
        agg = per.group_by("Cell").agg([pl.col("dt").mean(), pl.col("dp").mean(),
                                        pl.col("lead").n_unique().alias("nlead")] +
                                       ([pl.col("dr").mean()] if ref is not None else []))
        cellv = agg["Cell"].to_numpy()
        dt = agg["dt"].to_numpy()
        dp = agg["dp"].to_numpy()
        nl = float(agg["nlead"].mean())
        br = band_ratios(cellv, dp, dt, ll)
        print(f"{k:4d} {int(j.height):13,d} {len(cellv):7,d} {nl:6.1f} {'ARM':>6s}   {fmt(br)}")
        for b, (ratio, nb, num, den, snr) in br.items():
            ROWS.append(dict(section="matched_lead_response", horizon=k, band=b, n_cells=nb, series="arm",
                             arm=ARM.name, pred_response=num, truth_response=den, truth_snr=snr,
                             ratio=ratio if snr >= SNR_MIN else None, mean_matched_leads=nl))
        if ref is not None:
            rb = band_ratios(cellv, agg["dr"].to_numpy(), dt, ll)
            print(f"{'':4s} {'':13s} {'':7s} {'':6s} {'REF':>6s}   {fmt(rb)}")
            for b, (ratio, nb, num, den, snr) in rb.items():
                ROWS.append(dict(section="matched_lead_response", horizon=k, band=b, n_cells=nb,
                                 series="ref", arm=Path(REF).name, pred_response=num, truth_response=den,
                                 truth_snr=snr, ratio=ratio if snr >= SNR_MIN else None,
                                 mean_matched_leads=nl))

    pl.DataFrame(ROWS, infer_schema_length=None).write_csv(OUT)
    print(f"\nwrote {len(ROWS)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
