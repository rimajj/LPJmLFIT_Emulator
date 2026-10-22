#!/usr/bin/env python3
"""build_population_release.py -- add the TREE-POPULATION outputs (ADR 0363 stage A + B, shipped by ADR 0365) to an
existing release, without changing anything the release already does.

The base release's files are copied unchanged (structure, stand, departure and daily models, setups); added:
  population.json            levels, variables, feature list per quantity, the diversity-index constants
  lgb_pop_<var>_<pn>.txt     8 variables x 9 quantile levels (arm AQ of ADR 0363: one model per level)
  lgb_pop_share_<t>.txt      7 tree-type shares
  popsetup_m<k>.npz          per run k = 1..4: the population quantities' anchors (N, 81), the run's own 2000-2019
                             levels and their offset from the training runs', and its 2019 living trees >= 5 m
                             (the donors of the virtual trees)
Training exactly as scripts/explore_panel_popmap.py `fit` (same rows, anchors, inputs, LightGBM settings); a fold
release (base built with --hold-gcm g) holds out g as there, a deployment release trains on every run and leg.
Gates before release.json is written:
  (P1) fold only: the package's anchors equal the test rows' anchors of the training table (exact), and the saved
       models, fed the training table's test rows, reproduce the scored ADR 0363 predictions preds_<g>_<var>.parquet
       (AQ columns; LightGBM refits on identical rows: median |diff| ~0, reported). Age's fit is not reproducible
       run to run (ADR 0365): its gate is "within 2x the measured refit-to-refit spread" (needs the two refits
       POPMAP_SFX=_refit / _refit2 of explore_panel_popmap.py fit --group Age);
  (P2) the population setups' cell order equals the base setups'.
Run on SLURM (~30 min, ~150 GB):
  PARTITION=priority QOS=priority NCPUS=32 TIME=02:00:00 scripts/sbatch_python.sh poprel-<tag> \\
      scripts/build_population_release.py --base <release dir> --out <new dir>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_popmap as PM  # noqa: E402
import explore_panel_prep as PP  # noqa: E402
import explore_panel_yearly_drift as YD  # noqa: E402
import fdiversity as FD  # noqa: E402
from lpjmlfit_emulator.landemu import population as POP  # noqa: E402

F2 = "/p/projects/open/Jamir/esm_land_emulator_data/f2"
ROSTER = "/p/projects/reformit/Jamir/esm_land_emulator_data/xpanel_rosters"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def git_sha():
    try:
        return subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def base_and_feats(train_legs: list[str]):
    """The training-run x training-leg states of every population quantity (for the setup anchors), and per-run
    start levels (s0, memoff) -- the same rule as explore_panel_popmap.add_quantities."""
    qs = POP.POP_Q
    st = pl.concat([d for m in PP.MEMBERS for lg in A7.ALL_SLEGS if (d := PM.yearly2(m, lg, qs)) is not None])
    base = st.filter(pl.col("member").is_in(YD.TRAIN_M) & pl.col("leg").is_in(train_legs))
    anc = base.group_by("Cell", "Year").agg([pl.col(q).mean().alias(f"anc_{q}") for q in qs])
    h = pl.concat([d.with_columns(pl.lit(m).alias("member")) for m in PP.MEMBERS
                   if (d := PM.yearly2(m, "hist", qs)) is not None])
    s0 = h.group_by("Cell", "member").agg([pl.col(q).mean().alias(f"s0_{q}") for q in qs])
    hm = s0.filter(pl.col("member").is_in(YD.TRAIN_M)).group_by("Cell").agg(
        [pl.col(f"s0_{q}").mean().alias(f"hm_{q}") for q in qs])
    s0 = s0.join(hm, on="Cell").with_columns(
        [(pl.col(f"s0_{q}") - pl.col(f"hm_{q}")).alias(f"memoff_{q}") for q in qs]).drop([f"hm_{q}" for q in qs])
    return anc, s0


def fit_models(tr: pl.DataFrame, out: str) -> dict:
    feats = {}
    t0 = time.time()
    for q in POP.POP_Q:
        f = PM.feats_for(q, [])
        t = tr.filter(pl.col(q).is_not_null() & pl.col(f"anc_{q}").is_not_null())
        y = PM.tgt(q, t[q].to_numpy().astype(float), t[f"anc_{q}"].to_numpy().astype(float))  # shares: v - anc
        ok = np.isfinite(y)
        m = PM.fit(t.select(f).to_numpy()[ok], y[ok])
        m.save_model(os.path.join(out, f"lgb_pop_{q}.txt"))
        feats[q] = f
        log(f"fitted {q} on {int(ok.sum())} rows ({time.time() - t0:.0f}s)")
    return feats


NONDET = {"Age"}  # measured 2026-10-22: two refits of preds_gfdl-esm4_Age differ (median 0.18 yr at the median level)


def refit_spread(g: str, v: str) -> float:
    """Median |relative difference| between two refits of the same population model (popmap fit with POPMAP_SFX=_refit
    and _refit2), over the nine levels -- the run-to-run spread of a fit that is not reproducible."""
    a, b = (pl.read_parquet(os.path.join(PM.OUT, f"preds_{g}_{v}{s}.parquet")).filter(pl.col("member") == YD.TRUTH)
            for s in ("_refit", "_refit2"))
    j = a.join(b, on=["leg", "Cell", "Year"], suffix="_r")
    x = j.select([f"AQ_{v}_{pn}" for pn in POP.PN]).to_numpy().astype(float)
    y = j.select([f"AQ_{v}_{pn}_r" for pn in POP.PN]).to_numpy().astype(float)
    f = np.isfinite(x) & np.isfinite(y)
    return float(np.median(np.abs(x[f] - y[f]) / np.maximum(np.abs(y[f]), 1e-9)))


def gate_fold(g: str, te: pl.DataFrame, out: str, feats: dict, anc: pl.DataFrame) -> dict:
    import lightgbm as lgb

    t = te.filter(pl.col("member") == YD.TRUTH)
    new = [q for q in POP.POP_Q if q not in YD.QS]  # the trait medians' anchors come from the base setup (gate 3)
    j = t.select("Cell", "Year", *[f"anc_{q}" for q in new]).join(anc, on=["Cell", "Year"], suffix="_s")
    worst = max(float((j[f"anc_{q}"] - j[f"anc_{q}_s"]).abs().max() or 0.0) for q in new)
    log(f"GATE (P1a) population anchors vs the test rows': {j.height} rows, max |diff| {worst:.2e}")
    assert worst < 1e-9, "population anchors differ from the test rows'"
    res = {"anchor_max_abs": worst}
    for v in POP.POP_VARS:
        ref = pl.read_parquet(os.path.join(PM.OUT, f"preds_{g}_{v}.parquet")).filter(pl.col("member") == YD.TRUTH)
        cols = dict.fromkeys(["leg", "Cell", "Year", *[c for pn in POP.PN for c in feats[f"{v}_{pn}"]],
                              *[f"anc_{v}_{pn}" for pn in POP.PN]])
        x = t.select(list(cols)).join(ref.select("leg", "Cell", "Year", *[f"AQ_{v}_{pn}" for pn in POP.PN]),
                                      on=["leg", "Cell", "Year"], how="inner")
        P = []
        for pn in POP.PN:
            q = f"{v}_{pn}"
            p = lgb.Booster(model_file=os.path.join(out, f"lgb_pop_{q}.txt")).predict(x.select(feats[q]).to_numpy())
            P.append(PM.untgt(q, p, x[f"anc_{q}"].to_numpy().astype(float)))
        P = np.sort(np.column_stack(P), axis=1)
        R = x.select([f"AQ_{v}_{pn}" for pn in POP.PN]).to_numpy().astype(float)
        f = np.isfinite(P) & np.isfinite(R)
        d = np.abs(P[f] - R[f]) / np.maximum(np.abs(R[f]), 1e-9)
        res[v] = {"rows": x.height, "median_rel": float(np.median(d)), "p995_rel": float(np.quantile(d, 0.995)),
                  "max_rel": float(d.max())}
        log(f"GATE (P1b) {v}: package models vs scored AQ predictions, {x.height} rows: |rel diff| median "
            f"{res[v]['median_rel']:.1e}, 99.5th pct {res[v]['p995_rel']:.1e}, max {res[v]['max_rel']:.1e}")
        if v in NONDET:
            # ADR 0365: this variable's LightGBM fit is not reproducible run to run (two refits with the same code,
            # data and settings differ as much); the gate is then: within 2x the measured refit-to-refit spread
            sp = refit_spread(g, v)
            res[v]["refit_spread_median_rel"] = sp
            log(f"GATE (P1b) {v}: fit not reproducible run to run -- refit vs refit median |rel diff| {sp:.1e}; "
                f"require the package's <= 2x that")
            assert res[v]["median_rel"] <= 2 * sp, f"{v}: outside the refit-to-refit spread"
            continue
        assert res[v]["median_rel"] < 1e-6 and res[v]["p995_rel"] < 1e-2, f"{v}: models do not reproduce the scores"
    return res


def write_popsetups(out: str, anc: pl.DataFrame, s0: pl.DataFrame) -> list[str]:
    cells = pl.read_parquet(os.path.join(F2, "cells.parquet"))["Cell"].cast(pl.Int32).to_numpy()
    n, years = len(cells), np.arange(2020, 2101)
    grid = pl.DataFrame({"Cell": np.repeat(cells, len(years)).astype(np.int32),
                         "Year": np.tile(years, n).astype(np.int32)})
    A = grid.join(anc.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32)),
                  on=["Cell", "Year"], how="left")
    base = {"cell": cells}
    for q in POP.POP_Q:
        base[f"anc/{q}"] = A[f"anc_{q}"].to_numpy().astype(np.float64).reshape(n, len(years))
    written = []
    for k in (1, 2, 3, 4):
        assert np.array_equal(np.load(os.path.join(out, f"setup_m{k}.npz"))["cell"], cells), "GATE (P2) cell order"
        s = pl.DataFrame({"Cell": cells}).join(s0.filter(pl.col("member") == k).with_columns(
            pl.col("Cell").cast(pl.Int32)), on="Cell", how="left")
        z = dict(base)
        z.update({f"s0/{q}": s[f"s0_{q}"].to_numpy().astype(np.float64) for q in POP.POP_Q})
        z.update({f"memoff/{q}": s[f"memoff_{q}"].to_numpy().astype(np.float64) for q in POP.POP_Q})
        # the four trait medians are also structure-map quantities: the population models were trained on the
        # structure table's anchors / start levels for them (explore_panel_popmap.add_quantities), so take the base
        # setup's arrays -- one value per name in the emulator's feature dict
        bs = np.load(os.path.join(out, f"setup_m{k}.npz"))
        for q in POP.POP_Q:
            if f"anc/{q}" in bs.files:
                for kind in ("anc", "s0", "memoff"):
                    z[f"{kind}/{q}"] = bs[f"{kind}/{q}"]
        r = pl.read_parquet(os.path.join(ROSTER, f"m{k}_hist.parquet")).filter(pl.col("Year") == 2019)
        r = pl.DataFrame({"Cell": cells, "i": np.arange(n)}).join(
            r.with_columns(pl.col("Cell").cast(pl.Int32)), on="Cell", how="inner").sort("i", "Patch")
        cnt = np.bincount(r["i"].to_numpy(), minlength=n)
        z["ptr"] = np.concatenate([[0], np.cumsum(cnt)]).astype(np.int64)
        z["tree/Type"] = r["Type"].to_numpy().astype(np.int8)
        for v in POP.POP_VARS:
            z[f"tree/{v}"] = r[v].to_numpy().astype(np.float32)
        p = os.path.join(out, f"popsetup_m{k}.npz")
        np.savez(p, **z)
        written.append(p)
        log(f"popsetup m{k}: {n} cells, {len(r)} donor trees ({(cnt > 0).mean():.3f} of cells have donors), "
            f"anchors finite {np.isfinite(z['anc/Height_p50']).mean():.3f}")
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="an existing release directory (copied unchanged)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(os.path.join(a.out, "release.json")):
        sys.exit(f"{a.out} already holds a release; never overwrite one in place")
    with open(os.path.join(a.base, "release.json")) as fh:
        cfg = json.load(fh)
    g = cfg["hold_gcm"]
    os.makedirs(a.out, exist_ok=True)
    for f in sorted(os.listdir(a.base)):
        if os.path.isfile(os.path.join(a.base, f)) and f != "release.json":
            shutil.copy2(os.path.join(a.base, f), os.path.join(a.out, f))
    log(f"copied base release {a.base} ({cfg['kind']}, hold {g})")
    t0 = time.time()
    if g is None:
        YD.TRAIN_M = tuple(PP.MEMBERS)  # deployment: every run trains (as build_emulator_release.build_tables)
    R = YD.build_rows(g, t0=t0)
    tr = R["tr"].filter(pl.col("Year").is_in(R["train_years"]))
    tr = PM.add_quantities(tr, POP.POP_Q, R["train_legs"])
    log(f"training rows {tr.height} ({time.time() - t0:.0f}s)")
    feats = fit_models(tr, a.out)
    del tr
    anc, s0 = base_and_feats(R["train_legs"])
    gates = {}
    if g is not None:
        te = PM.add_quantities(R["te"], POP.POP_Q, R["train_legs"])
        gates = gate_fold(g, te, a.out, feats, anc)
    setups = write_popsetups(a.out, anc, s0)
    pcfg = {"levels": POP.PN, "vars": POP.POP_VARS, "log_eps": {v: e for v, e in PM.LOGV.items()},
            "features": feats, "diversity_constants": {t: FD.load_constants()[t] for t in FD.TRAITS},
            "virtual_trees": {"n_per_patch_scale": POP.NPATCH, "donor": "the run's own 2019 living trees >= 5 m",
                              "draw": "no repeats while the roster lasts (ADR 0363 sec. 12)",
                              "seed": "cell * 7919 + year"},
            "train_years": R["train_years"], "arm": "AQ (ADR 0363 sec. 3)"}
    with open(os.path.join(a.out, "population.json"), "w") as fh:
        json.dump(pcfg, fh, indent=1)
    cfg.update({"version": os.path.basename(os.path.normpath(a.out)), "base_release": cfg["version"],
                "git_sha": git_sha(), "built": time.strftime("%Y-%m-%d %H:%M"),
                "population": {"adr": "0363/0365", "popsetups": [os.path.basename(p) for p in setups],
                               "gates": gates, "check_pred_dir": PM.OUT}})
    with open(os.path.join(a.out, "release.json"), "w") as fh:
        json.dump(cfg, fh, indent=1)
    log(f"release written to {a.out} ({time.time() - t0:.0f}s)")
    log("=== DONE")


if __name__ == "__main__":
    main()
