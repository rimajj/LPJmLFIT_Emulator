#!/usr/bin/env python3
"""bench_structure_speed.py -- the per-cell-year COST of the structure half of the emulator (STATE NEXT item 6; skill
speed-gate). Run on a compute node:
  NCPUS=16 scripts/sbatch_python.sh bench-structure scripts/bench_structure_speed.py

WHAT IS TIMED (CPU time of this process, time.process_time, ONE thread for every timed part):
  (a) climate statistics: explore_glob_climate.year_features -- the 25+ yearly statistics the structure map reads
      (monthly means, growing degree days, frost days, dry spell, water balance, humidity, temperature-stress days...)
      computed from one year of DAILY weather for the 1 050 panel cells. The arrays are synthetic with realistic ranges
      (the function is branch-free numpy over (cells, 365) arrays, so its cost does not depend on the values); plus the
      30-year running-window update (a running sum).
  (b) the structure map: the best arm A7rH (ADR 0316 sec. 11-13) refitted exactly as explore_panel_a7.py mode `cnt`
      for held-out model gfdl-esm4 (fit cost reported separately -- it is offline, done once), then its SIX models
      (tree count, biomass per tree, four trait medians; 400 trees each) predicting every test row with num_threads=1.
  NOT timed (stated): building the per-cell anchor table (a lookup, offline) and any I/O.
CHECK that the arm ran (skill speed-gate: a label is not evidence): the refitted tree-count predictions must reproduce
the saved `cnt` A7rH ones (LightGBM multithreaded training is not bit-reproducible here, ADR 0316 sec. 12, so: median
|diff| < 1e-6 trees per patch and max < 1 % of the cell's value).
THE ORIGINAL, for the ratio (ADR 0084 / 0086, cell 42490, 1 core, marginal rate): 0.267 core-s per cell-year at 25
patches (the panel's patch count); cost(J) = 0.00404 + 0.013398 J => ~6.7 at the ~500 patches of publication runs.
RESULT 2026-10-12 (job 2467166, ADR 0330): climate statistics 2.4e-5 + window 1.8e-7 + six models 5.3e-5 = 7.8e-5
core-s per cell-year; check OK (2e-15). With the daily half (6.4e-3): 6.5e-3 -> ~41x less than the original at 25
patches, ~1000x at 500 (a sum of parts, not a coupled run).
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_climate as GC  # noqa: E402
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_prep as PP  # noqa: E402
from explore_de_climate import daylength_hours  # noqa: E402

G = "gfdl-esm4"
REPS = int(os.environ.get("REPS", "20"))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def cpu(f, reps):
    f()  # warm
    t0 = time.process_time()
    for _ in range(reps):
        r = f()
    return (time.process_time() - t0) / reps, r


# ------------------------------------------------------------------------------------------------ (a) climate
cells = PP.cells()
lat = cells["lat"].to_numpy().astype(float)
n = len(lat)
rng = np.random.default_rng(1)
day = np.arange(365)[None, :]
season = np.cos(2 * np.pi * (day - 196) / 365) * np.sign(lat)[:, None]
T = 15 - 0.4 * np.abs(lat)[:, None] + 12 * season + rng.normal(0, 3, (n, 365))
P = np.where(rng.random((n, 365)) < 0.4, rng.gamma(0.8, 6.0, (n, 365)), 0.0)
Q = np.clip(0.004 + 0.0004 * T + rng.normal(0, 0.001, (n, 365)), 1e-4, 0.03)
SW = np.clip(180 + 100 * season + rng.normal(0, 40, (n, 365)), 0, 400)
LW = -60 + rng.normal(0, 15, (n, 365))
W = np.abs(rng.normal(3, 1, (n, 365)))
dl = daylength_hours(lat)
win, hs = GC.window_mask(lat), GC.summer_mask(lat)
prm = GC.pft_temp_params()
lo, hi = prm["temp_low"].to_numpy(), prm["temp_high"].to_numpy()
t_feat, (res, _) = cpu(lambda: GC.year_features(T, P, Q, SW, LW, W, dl, win, hs, lo, hi), REPS)
assert all(np.isfinite(v).all() for v in res.values()), "non-finite climate statistic"
acc = np.zeros((n, len(res)))
ring = np.zeros((30, n, len(res)))
stack = np.stack([np.asarray(v, dtype=float) for v in res.values()], 1)


def window_update(k=[0]):  # noqa: B006 -- running 30-year sum: add the new year, drop the oldest
    i = k[0] % 30
    acc[:] += stack - ring[i]
    ring[i] = stack
    k[0] += 1
    return acc / 30


t_win, _ = cpu(window_update, REPS * 10)
log(f"(a) climate statistics: {t_feat / n:.3e} core-s per cell-year ({len(res)} statistics); "
    f"30-yr window update {t_win / n:.3e}")

# ------------------------------------------------------------------------------------------------ (b) structure map
import lightgbm as lgb  # noqa: E402

df = A7.build_rows()
new_m = [m for m in (5, 6) if A7.lev(m, "hist", "h2000") is not None]
legs = [lg for lg in A7.ALL_SLEGS if A7.gcm_of(lg) != G] + ["ctl_obs"]
legs = [lg for lg in legs if df.filter(pl.col("leg") == lg).height > 0]
mem = (*A7.TRAIN_M, *new_m)
an = A7.anchored(df, legs, mem)
tr = an.filter(pl.col("member").is_in(list(mem)) & pl.col("leg").is_in(legs))
te = an.filter((pl.col("member") == A7.TRUTH) & pl.col("leg").is_in([f"{G}_{s}" for s in PP.SCENS] + ["ctl_obs"])
               & (pl.col("win") == "w2071"))
f = A7.feats_r("A7r")
models, t_fit = {}, 0.0
for q in A7.PANEL:  # A7rH: tree count as A7r (absolute residual), biomass per tree on the log target, traits as A7r
    t = tr.filter(pl.col(q).is_not_null() & pl.col(f"anc_{q}").is_not_null())
    if q == "agb_per_stem":
        e = A7.LOG_EPS[q]
        y = np.log((t[q].to_numpy() + e) / (t[f"anc_{q}"].to_numpy() + e))
    else:
        y = (t[q] - t[f"anc_{q}"]).to_numpy()
    t0 = time.time()
    models[q] = lgb.train(A7.PARAMS, lgb.Dataset(t.select(f).to_numpy(), y), A7.ROUNDS)
    t_fit += time.time() - t0
log(f"(b) fitted 6 models on {tr.height} rows: {t_fit:.0f} s wall at {A7.PARAMS['num_threads']} threads (offline)")
Xte = te.select(f).to_numpy()
anc_n = te["anc_n_per_patch"].to_numpy().astype(float)


def predict_all():
    return {q: m.predict(Xte, num_threads=1) for q, m in models.items()}


t_pred, pr = cpu(predict_all, max(3, REPS // 4))
p_n = np.maximum(pr["n_per_patch"] + anc_n, 0.0)
old = pl.read_parquet(os.path.join(A7.EVAL, "preds_seen", "s1", f"cnt_{G}_A7rH.parquet"))
j = te.select("Cell", "leg").with_columns(pl.Series("new", p_n)).join(old.select("Cell", "leg", "n_per_patch"),
                                                                       on=["Cell", "leg"])
d = (j["new"] - j["n_per_patch"]).abs()
rel = (d / j["n_per_patch"].abs().clip(lower_bound=0.1)).max()
log(f"CHECK the arm ran: {j.height} rows vs saved A7rH tree count, median |diff| {d.median():.2e}, "
    f"max relative {rel:.2e} -> {'OK' if d.median() < 1e-6 and rel < 0.01 else 'MISMATCH'}")
per = t_pred / Xte.shape[0]
log(f"(b) structure map, 6 models x {A7.ROUNDS} trees, {Xte.shape[0]} rows: {per:.3e} core-s per cell-year")
tot = t_feat / n + t_win / n + per
log(f"TOTAL structure half: {tot:.3e} core-s per cell-year (single core). The original: 0.267 at 25 patches "
    f"-> {0.267 / tot:.0f}x less; ~6.7 at 500 patches -> {6.7 / tot:.0f}x less. "
    "Daily half (5-seed ensemble, ADR 0323/0324): 6.4e-3.")
log(f"WHOLE emulator (structure + daily): {tot + 6.4e-3:.3e} -> {0.267 / (tot + 6.4e-3):.0f}x less than the original at"
    f" 25 patches, {6.7 / (tot + 6.4e-3):.0f}x at 500")
log("=== DONE")
