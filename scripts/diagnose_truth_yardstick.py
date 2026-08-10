#!/usr/bin/env python3
"""RUNG 0, STAGE 2 — build the YARDSTICK the emulator is scored against, from the two ground-truth seeds.

`EXECUTION_PLAN.md` rung 0 asks for three things. This computes all three from the stage-1 reduction
(`scripts/build_truth_yardstick_tables.py`), on ONE stated basis per number:

  1. **THE NOISE FLOOR** — per cell, per quantity, the two seeds' own disagreement, stratified by stem
     density. This is the `max(10 %, the model's own two-run spread)` half of ADR 0106's tolerance, and for
     several acceptance quantities it is LARGER than the 10 %, i.e. the target is noisier than the tolerance.

  2. **THE DEATTENUATED RESPONSE SLOPE.** A scored slope of `D_pred` on `D_truth` is attenuated because the
     regressor `D_truth` is one roll of the dice. With two seeds the reliability is estimable:

         vD    = ½·Var(D₁ − D₂)          the variance of ONE seed's response noise
         varS  = Var(½(D₁+D₂)) − vD/2    the variance of the true between-cell response signal
         λ_k   = varS / (varS + vD/k)    the reliability of a k-seed-mean regressor

     and `slope/λ` estimates the slope against a noise-free truth. **λ is basis-specific**: it must be
     computed on the SAME statistic, in the SAME units, over the SAME cells as the slope it is divided into,
     or the quotient means nothing. That is why stage 1 emits an `uncapped` and a `capped` basis.

  3. **AN AGGREGATE RESPONSE METRIC.** The per-cell response is smaller than its own two-seed noise in a
     third of cells and the two seeds disagree on its SIGN in 33-37 % of them (ADR 0093 §3d), so a per-cell
     single-seed response score is largely a noise measurement. The area-weighted response has a
     signal-to-noise two orders of magnitude higher. This publishes the area-weighted global response and a
     latitude-band panel as the PRIMARY response statistic, with per-cell reported as a secondary.

WHAT IT SCORES THE EMULATOR ON (optional, `PRED_DIR=`)
-----------------------------------------------------
Given a copula table dir with `pred_<axis>.f64` (K-fold-by-cell OOS predictions) it recomputes the per-cell
response slope three ways on ONE basis — against seed1 alone (as published), against the two-seed mean, and
deattenuated — plus the aggregate ratio. The point is not a new number for its own sake: it is that the
published slope and the λ it was divided by in ADR 0093 §3e came from different bases.

Usage (SLURM):
    YARD=/p/tmp/jamirp/emulator_global/yardstick_v1 \
    PRED_DIR=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8 \
      scripts/sbatch_python.sh S-yardscore scripts/diagnose_truth_yardstick.py
Env: YARD (stage-1 dir), PRED_DIR (optional), BASIS (capped400|pooled; default capped400 = the basis the
     published slopes were scored on), MIN_CELL_STEMS (30), OUT_SUMMARY (CSV; default
     <repo>/test/testitems/references/S_truth_yardstick_summary.csv), OUT_PERCELL (optional parquet),
     COUNT_DIR (optional; one or MORE comma-separated pooled COUNT tables with y.f64 + preds_oos.f64 —
     scores the count response too, all in one process so an arm and its null control share the cell set).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import polars as pl

_REPO = Path(__file__).resolve().parent.parent
YARD = Path(os.environ.get("YARD", "/p/tmp/jamirp/emulator_global/yardstick_v1"))
PRED_DIRS = [d.strip() for d in os.environ.get("PRED_DIR", "").split(",") if d.strip()]
#: one or MORE pooled count tables (comma-separated), so an ARM and its null control are scored in the same
#: process, against the same paired cell set — the rung-1 arms must never be compared across two invocations.
COUNT_DIRS = [d.strip() for d in os.environ.get("COUNT_DIR", "").split(",") if d.strip()]
BASIS = os.environ.get("BASIS", "capped400").strip()
MIN_CELL_STEMS = int(os.environ.get("MIN_CELL_STEMS", "30"))
#: the CONFIGURED patch ensemble size — the denominator of every per-patch density here. It must be the
#: configured count (25 everywhere in this run, ADR 0093), NEVER the number of patches that happen to hold a
#: tree: dividing by OCCUPIED patches lets a seed with fewer stems also have a smaller denominator, which
#: cancels part of the sampling noise and understates the floor ~3x in the sparse stratum. `cell_npatch.parquet`
#: is itself derived from occupied patches, so it is the wrong table for this job.
NPATCH = int(os.environ.get("NPATCH", "25"))
OUT_SUMMARY = Path(
    os.environ.get("OUT_SUMMARY", str(_REPO / "test/testitems/references/S_truth_yardstick_summary.csv"))
)
OUT_PERCELL = os.environ.get("OUT_PERCELL", "").strip()
LATLON = "/p/tmp/jamirp/emulator_global/tables/cell_latlon.txt"

TRAIT_AXES = ["SLA", "Wooddens", "D95max", "minwscal"]
STRUCT_AXES = ["Height", "Age"]
#: cell-level count/carbon quantities, derived per (Cell, Year) then averaged over years
FLUX_QTY = ["n_per_patch", "agb_per_patch", "vegc_per_patch"]
DENSITY_EDGES = [0.0, 2.0, 5.0, 10.0, 20.0, np.inf]
DENSITY_LABELS = ["<2", "2-5", "5-10", "10-20", ">20"]
LAT_BANDS = [("tropical", 0.0, 23.5), ("subtropical", 23.5, 35.0), ("temperate", 35.0, 50.0),
             ("boreal", 50.0, 90.1)]

ROWS: list[dict] = []


def rec(**kw) -> None:
    ROWS.append(kw)


# ----------------------------------------------------------------------------- loading
def load_cell_level(scenario: str, seed: int) -> pl.DataFrame:
    """Per-cell truth: the count/carbon quantities (year-averaged) + the trait medians on BASIS."""
    cy = pl.read_parquet(YARD / f"cell_year_{scenario}_seed{seed}.parquet")
    flux = (
        cy.with_columns(
            (pl.col("n_stems") / NPATCH).alias("n_per_patch"),
            (pl.col("agb_sum") / NPATCH).alias("agb_per_patch"),
            (pl.col("vegc_sum") / NPATCH).alias("vegc_per_patch"),
        )
        .group_by("Cell")
        .agg([pl.col(q).mean().alias(q) for q in FLUX_QTY]
             + [pl.len().cast(pl.Int32).alias("n_years"), pl.col("n_stems").sum().alias("n_stems_total")])
    )
    fn = f"cell_pooled_{scenario}_seed{seed}.parquet" if BASIS == "pooled" \
        else f"cell_{BASIS}_{scenario}_seed{seed}.parquet"
    med = pl.read_parquet(YARD / fn).select(
        ["Cell", "n_stems"] + [f"{a}_med" for a in TRAIT_AXES + STRUCT_AXES]
    ).rename({"n_stems": "n_stems_basis"})
    return flux.join(med, on="Cell", how="inner").sort("Cell")


def load_latlon() -> pl.DataFrame:
    rows = []
    for ln in Path(LATLON).read_text().splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        p = ln.split()
        rows.append((int(p[0]), float(p[3]), float(p[4])))
    d = pl.DataFrame(rows, schema=["Cell", "lat", "lon"], orient="row")
    # equal-angle grid ⇒ cell area ∝ cos(lat). Un-normalised: only weight RATIOS enter a weighted mean.
    w = np.clip(np.cos(np.deg2rad(d["lat"].to_numpy())), 0.0, None)
    return d.with_columns(pl.Series("w", w))


# ----------------------------------------------------------------------------- 1. noise floor
def spread_stats(x1: np.ndarray, x2: np.ndarray) -> dict:
    """The two-run spread of a cell estimator, in the acceptance criterion's own relative units."""
    m = 0.5 * (x1 + x2)
    g = np.isfinite(x1) & np.isfinite(x2) & (m > 0)
    if g.sum() < 20:
        return {}
    rel = np.abs(x1 - x2)[g] / m[g]
    cv1 = rel / np.sqrt(2.0)  # one run's Monte-Carlo CV from a 2-member sample
    return {
        "n_cells": int(g.sum()),
        "mean_value": float(m[g].mean()),
        "two_run_reldiff_median_pct": float(100 * np.median(rel)),
        "two_run_reldiff_p90_pct": float(100 * np.percentile(rel, 90)),
        "one_run_cv_median_pct": float(100 * np.median(cv1)),
        "one_run_cv_rms_pct": float(100 * np.sqrt((cv1 ** 2).mean())),
        "frac_cells_spread_gt_10pct": float((rel > 0.10).mean()),
        "tolerance_median_pct": float(100 * max(0.10, np.median(rel))),
    }


def noise_floor(scenario: str, s1: pl.DataFrame, s2: pl.DataFrame) -> pl.DataFrame:
    j = s1.join(s2, on="Cell", how="inner", suffix="_2")
    # the acceptance population: tree-bearing in BOTH runs, with enough stems for a median to mean anything
    j = j.filter(
        (pl.col("n_stems_basis") >= MIN_CELL_STEMS) & (pl.col("n_stems_basis_2") >= MIN_CELL_STEMS)
    )
    dens = 0.5 * (j["n_per_patch"].to_numpy() + j["n_per_patch_2"].to_numpy())
    print(f"\n--- 1. NOISE FLOOR — {scenario}, basis={BASIS}, {j.height:,} cells "
          f"(>= {MIN_CELL_STEMS} stems in both seeds) ---")
    print(f"{'quantity':16s} {'stratum':8s} {'cells':>7s} {'mean':>12s} {'2-run med%':>10s} "
          f"{'p90%':>7s} {'1-run CV%':>9s} {'>10%':>6s} {'tolerance%':>10s}")
    quantities = FLUX_QTY + [f"{a}_med" for a in TRAIT_AXES + STRUCT_AXES]
    for q in quantities:
        x1, x2 = j[q].to_numpy().astype(float), j[f"{q}_2"].to_numpy().astype(float)
        for lab, lo, hi in [("ALL", 0.0, np.inf)] + list(
            zip(DENSITY_LABELS, DENSITY_EDGES[:-1], DENSITY_EDGES[1:], strict=True)
        ):
            m = (dens >= lo) & (dens < hi)
            st = spread_stats(x1[m], x2[m])
            if not st:
                continue
            rec(section="noise_floor", scenario=scenario, basis=BASIS, quantity=q, stratum=lab, **st)
            print(f"{q:16s} {lab:8s} {st['n_cells']:7d} {st['mean_value']:12.4g} "
                  f"{st['two_run_reldiff_median_pct']:10.2f} {st['two_run_reldiff_p90_pct']:7.1f} "
                  f"{st['one_run_cv_median_pct']:9.2f} {100 * st['frac_cells_spread_gt_10pct']:5.1f}% "
                  f"{st['tolerance_median_pct']:10.2f}")
    return j


def noise_floor_yearwise(scenario: str) -> None:
    """The SAME floor on a per-(Cell, Year) basis — a DIFFERENT question, and the one already published.

    ADR 0093 §3c's `<2 stems/patch` tolerances (count 31.6 %, carbon 42.7 %) are SINGLE-YEAR numbers. A
    20-year mean averages ~√20 of that away, so the climatological floor is ~4× smaller. Both are correct
    for their own question — a per-cell-year score must use this one, a cell-climatology score the other —
    and quoting one as the tolerance for the other is a 4× error in either direction. Publish both.
    """
    a = pl.read_parquet(YARD / f"cell_year_{scenario}_seed1.parquet")
    b = pl.read_parquet(YARD / f"cell_year_{scenario}_seed2.parquet")
    if max(int(a["n_patch"].max()), int(b["n_patch"].max())) > NPATCH:
        raise SystemExit(f"FATAL: a cell-year holds more than NPATCH={NPATCH} occupied patches — the "
                         f"configured ensemble size is wrong, and every per-patch density here is scaled by it.")
    j = a.join(b, on=["Cell", "Year"], how="inner", suffix="_2").with_columns(
        (pl.col("n_stems") / NPATCH).alias("n_per_patch"),
        (pl.col("n_stems_2") / NPATCH).alias("n_per_patch_2"),
        (pl.col("agb_sum") / NPATCH).alias("agb_per_patch"),
        (pl.col("agb_sum_2") / NPATCH).alias("agb_per_patch_2"),
        (pl.col("vegc_sum") / NPATCH).alias("vegc_per_patch"),
        (pl.col("vegc_sum_2") / NPATCH).alias("vegc_per_patch_2"),
    )
    dens = 0.5 * (j["n_per_patch"].to_numpy() + j["n_per_patch_2"].to_numpy())
    print(f"\n--- 1b. NOISE FLOOR, PER (CELL, YEAR) — {scenario}, {j.height:,} cell-years "
          f"(no cap: a single year's full roster) ---")
    print(f"{'quantity':16s} {'stratum':8s} {'cell-yrs':>9s} {'mean':>12s} {'2-run med%':>10s} "
          f"{'p90%':>7s} {'1-run CV%':>9s} {'>10%':>6s} {'tolerance%':>10s}")
    for q in FLUX_QTY + [f"{a_}_med" for a_ in TRAIT_AXES + STRUCT_AXES]:
        x1, x2 = j[q].to_numpy().astype(float), j[f"{q}_2"].to_numpy().astype(float)
        for lab, lo, hi in [("ALL", 0.0, np.inf)] + list(
            zip(DENSITY_LABELS, DENSITY_EDGES[:-1], DENSITY_EDGES[1:], strict=True)
        ):
            m = (dens >= lo) & (dens < hi)
            st = spread_stats(x1[m], x2[m])
            if not st:
                continue
            rec(section="noise_floor_yearwise", scenario=scenario, basis="cell_year_uncapped",
                quantity=q, stratum=lab, **st)
            print(f"{q:16s} {lab:8s} {st['n_cells']:9d} {st['mean_value']:12.4g} "
                  f"{st['two_run_reldiff_median_pct']:10.2f} {st['two_run_reldiff_p90_pct']:7.1f} "
                  f"{st['one_run_cv_median_pct']:9.2f} {100 * st['frac_cells_spread_gt_10pct']:5.1f}% "
                  f"{st['tolerance_median_pct']:10.2f}")


# ----------------------------------------------------------------------------- 2. lambda
def reliability(d1: np.ndarray, d2: np.ndarray) -> dict:
    """λ_k from two paired single-seed responses. Linear units, same statistic as the slope's regressor."""
    g = np.isfinite(d1) & np.isfinite(d2)
    d1, d2 = d1[g], d2[g]
    vD = 0.5 * float(np.var(d1 - d2, ddof=1))          # variance of ONE seed's response noise
    dbar = 0.5 * (d1 + d2)
    varS = max(float(np.var(dbar, ddof=1)) - vD / 2.0, 0.0)
    lam = lambda k: varS / (varS + vD / k) if (varS + vD / k) > 0 else float("nan")  # noqa: E731
    return {
        "n_cells": int(g.sum()),
        "response_noise_sd_1seed": float(np.sqrt(vD)),
        "response_signal_sd": float(np.sqrt(varS)),
        "response_snr": float(np.sqrt(varS / vD)) if vD > 0 else float("inf"),
        "lambda_1seed": lam(1), "lambda_2seed": lam(2), "lambda_4seed": lam(4),
        "frac_cells_resp_below_own_noise": float((np.abs(dbar) < np.abs(d1 - d2) / np.sqrt(2.0)).mean()),
        "frac_cells_seeds_disagree_on_sign": float((np.sign(d1) != np.sign(d2)).mean()),
        "mean_response": float(dbar.mean()),
    }


def paired_frame(H: dict, S: dict, ll: pl.DataFrame) -> pl.DataFrame:
    """ONE cell set for every response number: present with enough stems in ALL FOUR runs.

    Both ends of a difference must be the same cells. Aggregating each scenario over whatever cells it
    happens to have would let a cell that is tree-bearing in only one scenario contribute to one end of the
    response only — a composition change dressed up as a response.
    """
    cols = FLUX_QTY + [f"{a}_med" for a in TRAIT_AXES + STRUCT_AXES]
    keep = ["Cell"] + cols + ["n_stems_basis"]
    j = (H[1].select(keep).join(H[2].select(keep), on="Cell", suffix="_h2")
         .join(S[1].select(keep), on="Cell", suffix="_s1")
         .join(S[2].select(keep), on="Cell", suffix="_s2")
         .join(ll.select(["Cell", "lat", "w"]), on="Cell", how="inner"))
    return j.filter(
        (pl.col("n_stems_basis") >= MIN_CELL_STEMS) & (pl.col("n_stems_basis_h2") >= MIN_CELL_STEMS)
        & (pl.col("n_stems_basis_s1") >= MIN_CELL_STEMS) & (pl.col("n_stems_basis_s2") >= MIN_CELL_STEMS)
    ).sort("Cell")


def response_tables(j: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """Per-cell paired responses D_s = X_s(ssp370) - X_s(historic), one chain per seed."""
    cols = FLUX_QTY + [f"{a}_med" for a in TRAIT_AXES + STRUCT_AXES]
    out = {"Cell": j["Cell"]}
    lam = {}
    print(f"\n--- 2. RESPONSE RELIABILITY (deattenuation) — basis={BASIS}, {j.height:,} cells present in "
          f"all four runs ---")
    print(f"{'quantity':16s} {'cells':>7s} {'meanD':>11s} {'signal sd':>10s} {'noise sd':>9s} {'S/N':>6s} "
          f"{'lam1':>6s} {'lam2':>6s} {'lam4':>6s} {'<noise':>7s} {'signflip':>8s}")
    for q in cols:
        h1 = j[q].to_numpy().astype(float)
        h2 = j[f"{q}_h2"].to_numpy().astype(float)
        s1 = j[f"{q}_s1"].to_numpy().astype(float)
        s2 = j[f"{q}_s2"].to_numpy().astype(float)
        d1, d2 = s1 - h1, s2 - h2
        out[f"D1_{q}"], out[f"D2_{q}"] = d1, d2
        st = reliability(d1, d2)
        lam[q] = st
        rec(section="reliability", scenario="hist->ssp370", basis=BASIS, quantity=q, stratum="ALL", **st)
        print(f"{q:16s} {st['n_cells']:7d} {st['mean_response']:11.4g} {st['response_signal_sd']:10.4g} "
              f"{st['response_noise_sd_1seed']:9.4g} {st['response_snr']:6.2f} {st['lambda_1seed']:6.3f} "
              f"{st['lambda_2seed']:6.3f} {st['lambda_4seed']:6.3f} "
              f"{100 * st['frac_cells_resp_below_own_noise']:6.1f}% "
              f"{100 * st['frac_cells_seeds_disagree_on_sign']:7.1f}%")
    return pl.DataFrame(out), lam


# ----------------------------------------------------------------------------- 3. aggregate response
def aggregate_response(j: pl.DataFrame) -> None:
    cols = FLUX_QTY + [f"{a}_med" for a in TRAIT_AXES + STRUCT_AXES]
    lat = np.abs(j["lat"].to_numpy())
    wall = j["w"].to_numpy().astype(float)
    print(f"\n--- 3. AGGREGATE RESPONSE (area-weighted; the PRIMARY response statistic) — basis={BASIS} ---")
    print(f"{'quantity':16s} {'band':12s} {'cells':>7s} {'hist':>12s} {'response':>12s} {'resp %':>8s} "
          f"{'2-seed noise':>12s} {'S/N':>9s}")
    for q in cols:
        h1 = j[q].to_numpy().astype(float)
        h2 = j[f"{q}_h2"].to_numpy().astype(float)
        s1 = j[f"{q}_s1"].to_numpy().astype(float)
        s2 = j[f"{q}_s2"].to_numpy().astype(float)
        fin = np.isfinite(h1) & np.isfinite(h2) & np.isfinite(s1) & np.isfinite(s2)
        for band, lo, hi in [("GLOBAL", 0.0, 90.1)] + LAT_BANDS:
            m = fin & (lat >= lo) & (lat < hi) & (wall > 0)
            if m.sum() < 20:
                continue
            w = wall[m]
            wm = lambda x: float((x[m] * w).sum() / w.sum())  # noqa: E731
            r1 = wm(s1) - wm(h1)
            r2 = wm(s2) - wm(h2)
            rbar = 0.5 * (r1 + r2)
            noise = abs(r1 - r2) / np.sqrt(2.0)
            base = 0.5 * (wm(h1) + wm(h2))
            snr = abs(rbar) / noise if noise > 0 else float("inf")
            rec(section="aggregate_response", scenario="hist->ssp370", basis=BASIS, quantity=q, stratum=band,
                n_cells=int(m.sum()), hist_level=base, response=rbar,
                response_pct=100 * rbar / base if base else np.nan,
                two_seed_noise=noise, response_snr=snr)
            print(f"{q:16s} {band:12s} {int(m.sum()):7d} {base:12.5g} {rbar:12.5g} "
                  f"{100 * rbar / base if base else np.nan:7.2f}% {noise:12.4g} {snr:9.1f}")


# ----------------------------------------------------------------------------- 4. score the emulator
def band_ratios(cell: np.ndarray, dp: np.ndarray, d1: np.ndarray, d2: np.ndarray,
                ll: pl.DataFrame) -> dict:
    """Area-weighted (prediction response ÷ truth response) per latitude band, WITH a determinacy guard.

    Why banding is not optional: a global aggregate is a ratio of near-CANCELLING sums (the truth's global
    mean count response is ~3 % of its between-cell spread, because regional responses partly oppose each
    other), so a wrong regional pattern can still produce a right-looking global ratio — or a right pattern a
    wrong-looking one.

    Why the guard is not optional either: when a band's TRUTH response is small compared with its own
    two-seed noise, the ratio's denominator is undetermined and the ratio is meaningless at any value. It is
    reported as `n/d` rather than as a number. This is how `Height`'s "0.14" was caught: on an unweighted
    global mean it read 0.14, area-weighted it read 2.88, and its band S/N shows why neither is a result.
    """
    lat = pl.DataFrame({"Cell": cell}).join(ll.select(["Cell", "lat", "w"]), on="Cell", how="left")
    la = np.abs(lat["lat"].to_numpy().astype(float))
    w = lat["w"].to_numpy().astype(float)
    dbar = 0.5 * (d1 + d2)
    out = {}
    for band, lo, hi in [("GLOBAL", 0.0, 90.1)] + LAT_BANDS:
        m = np.isfinite(la) & (la >= lo) & (la < hi) & (w > 0)
        if m.sum() < 20:
            continue
        ww = w[m] / w[m].sum()
        num = float((dp[m] * ww).sum())
        den = float((dbar[m] * ww).sum())
        # the truth aggregate's OWN two-seed noise in this band -> is the denominator even determined?
        noise = abs(float((d1[m] * ww).sum()) - float((d2[m] * ww).sum())) / np.sqrt(2.0)
        snr = abs(den) / noise if noise > 0 else float("inf")
        out[band] = (num / den if den != 0 else np.nan, int(m.sum()), num, den, snr)
    return out


def fmt_band(br: dict, indent: str) -> str:
    """`n/d` where the truth's band response is not determined (S/N < 3) — never a number."""
    return indent + "band pred/truth: " + "  ".join(
        f"{b} " + (f"{v[0]:+.2f}" if v[4] >= 3.0 else "n/d") + f"(S/N {v[4]:.0f})" for b, v in br.items()
    )


def score_emulator(resp: pl.DataFrame, pred_dir: str, ll: pl.DataFrame) -> None:
    d = Path(pred_dir)
    man = {}
    for ln in (d / "manifest_copula.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            man[k] = v
    cells = np.fromfile(d / "cells.i64", dtype="<i8")
    scen = np.fromfile(d / man["scenario_tag"], dtype="<i8")
    print(f"\n--- 4. THE EMULATOR'S RESPONSE SLOPE, RE-SCORED ON ONE BASIS — {d.name} ---")
    print("    slope = OLS through the origin of D_pred on D_truth over the cells common to both.")
    print(f"{'axis':12s} {'cells':>7s} {'slope vs seed1':>15s} {'slope vs 2-seed':>16s} {'lam1':>6s} "
          f"{'lam2':>6s} {'deatt(1seed)':>13s} {'deatt(2seed)':>13s} {'aggregate ratio':>16s}")
    for axis in TRAIT_AXES + STRUCT_AXES:
        f = d / f"pred_{axis}.f64"
        if not f.exists():
            print(f"{axis:12s} (no pred_{axis}.f64 — skipped)")
            continue
        pred = np.fromfile(f, dtype="<f8")
        if pred.size != cells.size:
            print(f"{axis:12s} SKIPPED: pred has {pred.size} rows, cells.i64 has {cells.size}")
            continue
        pf = pl.DataFrame({"Cell": cells, "s": scen, "v": pred})
        g = pf.group_by(["Cell", "s"]).agg(pl.col("v").median().alias("m"))
        h = g.filter(pl.col("s") == 0).select("Cell", pl.col("m").alias("ph"))
        s = g.filter(pl.col("s") == 1).select("Cell", pl.col("m").alias("ps"))
        p = h.join(s, on="Cell", how="inner").with_columns((pl.col("ps") - pl.col("ph")).alias("Dp"))
        q = f"{axis}_med"
        t = resp.select(["Cell", f"D1_{q}", f"D2_{q}"]).join(p.select(["Cell", "Dp"]), on="Cell", how="inner")
        cellv = t["Cell"].to_numpy()
        d1 = t[f"D1_{q}"].to_numpy().astype(float)
        d2 = t[f"D2_{q}"].to_numpy().astype(float)
        dp = t["Dp"].to_numpy().astype(float)
        ok = np.isfinite(d1) & np.isfinite(d2) & np.isfinite(dp)
        cellv, d1, d2, dp = cellv[ok], d1[ok], d2[ok], dp[ok]
        dbar = 0.5 * (d1 + d2)
        sl1 = float((dp * d1).sum() / (d1 * d1).sum())
        slb = float((dp * dbar).sum() / (dbar * dbar).sum())
        # λ recomputed on THESE cells (the pred join shrinks the set) so the quotient is self-consistent
        st = reliability(d1, d2)
        l1, l2 = st["lambda_1seed"], st["lambda_2seed"]
        br = band_ratios(cellv, dp, d1, d2, ll)
        aggr = br["GLOBAL"][0] if br["GLOBAL"][4] >= 3.0 else float("nan")   # AREA-WEIGHTED, one definition
        rec(section="emulator_slope", scenario="hist->ssp370", basis=BASIS, quantity=q, stratum="ALL",
            n_cells=int(ok.sum()), pred_dir=d.name, slope_vs_seed1=sl1, slope_vs_2seed_mean=slb,
            lambda_1seed=l1, lambda_2seed=l2, deatt_slope_1seed=sl1 / l1 if l1 else np.nan,
            deatt_slope_2seed=slb / l2 if l2 else np.nan, aggregate_response_ratio=aggr)
        print(f"{axis:12s} {int(ok.sum()):7d} {sl1:15.3f} {slb:16.3f} {l1:6.3f} {l2:6.3f} "
              f"{sl1 / l1 if l1 else np.nan:13.3f} {slb / l2 if l2 else np.nan:13.3f} {aggr:16.3f}")
        print(fmt_band(br, "             "))
        for b, (ratio, n, num, den, snr) in br.items():
            rec(section="band_response_ratio", scenario="hist->ssp370", basis=BASIS, quantity=q, stratum=b,
                n_cells=n, pred_dir=d.name, response=num, hist_level=den, response_snr=snr,
                aggregate_response_ratio=ratio if snr >= 3.0 else None)
    print("\n    NOTE on `deatt`: `slope/λ` is only meaningful when the slope and λ are computed on the SAME")
    print("    statistic, units, cells and basis — which is what this block does and what ADR 0093 §3e did")
    print("    NOT do (its λ was log-space, single-year 2019/2099, >=50 stems, 43 257 cells; the slope was")
    print("    linear, all-years-pooled, >=30 stems, 52 074 cells).")


def score_counts(resp: pl.DataFrame, count_dir: str, ll: pl.DataFrame) -> None:
    """The COUNT side of the same question, from a pooled count table's OOS predictions.

    `n_living` is per (Cell, Patch, Year), so a per-cell mean over rows is stems per patch — the same
    quantity as `n_per_patch` here, and the first quantity ADR 0106 names. Its λ is the highest of any
    quantity (0.908 for one seed), so the count slope needs the least correction and is the most directly
    readable of the panel.
    """
    d = Path(count_dir)
    man = {}
    for ln in (d / "manifest.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            man[k] = v
    cells = np.fromfile(d / "cells.i64", dtype="<i8")
    scen = np.fromfile(d / man["scenario_tag"], dtype="<i8")
    y = np.fromfile(d / "y.f64", dtype="<f8")
    pr = np.fromfile(d / "preds_oos.f64", dtype="<f8")
    print(f"\n--- 4b. THE COUNT RESPONSE, from {d.name} (target {man['target']}, n={len(y):,}) ---")
    if not (len(cells) == len(scen) == len(y) == len(pr)):
        print(f"    SKIPPED: length mismatch cells {len(cells)} scen {len(scen)} y {len(y)} pred {len(pr)}")
        return
    g = (pl.DataFrame({"Cell": cells, "s": scen, "y": y, "p": pr})
         .group_by(["Cell", "s"]).agg(pl.col("y").mean().alias("y"), pl.col("p").mean().alias("p")))
    h = g.filter(pl.col("s") == 0).select("Cell", pl.col("y").alias("yh"), pl.col("p").alias("ph"))
    s = g.filter(pl.col("s") == 1).select("Cell", pl.col("y").alias("ys"), pl.col("p").alias("ps"))
    t = (h.join(s, on="Cell", how="inner")
         .join(resp.select(["Cell", "D1_n_per_patch", "D2_n_per_patch"]), on="Cell", how="inner"))
    dtab = (t["ys"] - t["yh"]).to_numpy()          # the count table's OWN truth response (seed1)
    dp = (t["ps"] - t["ph"]).to_numpy()
    d1 = t["D1_n_per_patch"].to_numpy()
    d2 = t["D2_n_per_patch"].to_numpy()
    ok = np.isfinite(dtab) & np.isfinite(dp) & np.isfinite(d1) & np.isfinite(d2)
    cellv = t["Cell"].to_numpy()[ok]
    dtab, dp, d1, d2 = dtab[ok], dp[ok], d1[ok], d2[ok]
    dbar = 0.5 * (d1 + d2)
    st = reliability(d1, d2)
    sl_tab = float((dp * dtab).sum() / (dtab * dtab).sum())
    sl1 = float((dp * d1).sum() / (d1 * d1).sum())
    slb = float((dp * dbar).sum() / (dbar * dbar).sum())
    # the ADR-0030 cross-check: the count table's own seed1 response vs THIS reduction's seed1 response.
    # These are two independent code paths over the same run; a low correlation means the two are not the
    # same quantity and no slope below is comparable to the trait panel's.
    xchk = float(np.corrcoef(dtab, d1)[0, 1])
    l1, l2 = st["lambda_1seed"], st["lambda_2seed"]
    # ONE definition of the aggregate ratio — AREA-WEIGHTED, `n/d` below S/N 3 (ADR 0111 §5b). This path used
    # to record the UNWEIGHTED `mean(Dp)/mean(Dbar)` as well, which is the same two-definitions trap ADR 0111
    # closed on the trait side: on the recursed arm the two disagree by a factor of 4 (-0.93 vs -0.23) because
    # an unweighted mean-ratio is dominated by cells whose own denominator is near zero.
    br = band_ratios(cellv, dp, d1, d2, ll)
    aggr = br["GLOBAL"][0] if br["GLOBAL"][4] >= 3.0 else float("nan")
    rec(section="count_slope", scenario="hist->ssp370", basis=BASIS, quantity="n_per_patch", stratum="ALL",
        n_cells=int(ok.sum()), pred_dir=d.name, slope_vs_seed1=sl1, slope_vs_2seed_mean=slb,
        lambda_1seed=l1, lambda_2seed=l2, deatt_slope_1seed=sl1 / l1, deatt_slope_2seed=slb / l2,
        aggregate_response_ratio=aggr)
    print(f"    cells {int(ok.sum()):,}  basis cross-check r(table's own seed1 D, this reduction's seed1 D) "
          f"= {xchk:.4f}   {'OK' if xchk > 0.9 else 'LOW — the two are not the same quantity, stop'}")
    print(f"    slope vs the table's own truth {sl_tab:.3f} | vs this seed1 {sl1:.3f} | vs 2-seed mean "
          f"{slb:.3f}   λ1 {l1:.3f} λ2 {l2:.3f}")
    print(f"    DEATTENUATED  {sl1 / l1:.3f} (1-seed)  {slb / l2:.3f} (2-seed)     "
          f"aggregate pred/truth (AREA-WEIGHTED) {aggr:.3f}")
    print(fmt_band(br, "    "))
    for b, (ratio, n, num, den, snr) in br.items():
        rec(section="band_response_ratio", scenario="hist->ssp370", basis=BASIS, quantity="n_per_patch",
            stratum=b, n_cells=n, pred_dir=d.name, response=num, hist_level=den, response_snr=snr,
            aggregate_response_ratio=ratio if snr >= 3.0 else None)


def main() -> int:
    print("=" * 118)
    print("RUNG 0 — THE YARDSTICK: the reference model's own noise floor, response reliability, and "
          "aggregate response")
    print("=" * 118)
    print(f"  YARD={YARD}  BASIS={BASIS}  NPATCH={NPATCH}  MIN_CELL_STEMS={MIN_CELL_STEMS}  PRED_DIRS={PRED_DIRS or '(none)'}")
    ll = load_latlon()
    H = {s: load_cell_level("historic", s) for s in (1, 2)}
    S = {s: load_cell_level("ssp370", s) for s in (1, 2)}
    for nm, D in (("historic", H), ("ssp370", S)):
        print(f"  {nm}: seed1 {D[1].height:,} cells, seed2 {D[2].height:,} cells")
    noise_floor("historic", H[1], H[2])
    noise_floor("ssp370", S[1], S[2])
    noise_floor_yearwise("historic")
    noise_floor_yearwise("ssp370")
    j = paired_frame(H, S, ll)
    print(f"\n  paired cell set (>= {MIN_CELL_STEMS} stems in ALL FOUR runs): {j.height:,} cells")
    resp, lam = response_tables(j)
    aggregate_response(j)
    for pd_ in PRED_DIRS:
        score_emulator(resp, pd_, ll)
    for cd_ in COUNT_DIRS:
        score_counts(resp, cd_, ll)
    if OUT_PERCELL:
        resp.write_parquet(OUT_PERCELL)
        print(f"\nwrote per-cell responses -> {OUT_PERCELL}")
    summary = pl.DataFrame(ROWS, infer_schema_length=None)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    summary.write_csv(OUT_SUMMARY)
    print(f"wrote summary ({summary.height} rows) -> {OUT_SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
