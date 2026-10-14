#!/usr/bin/env python3
"""bench_coupled_speed.py -- ONE END-TO-END TIMING of the whole learned emulator (STATE NEXT item 6; skill speed-gate):
the structure map, the stand map and the learned daily water-carbon model run together, year by year, in one process on
one core, with the stand each year's daily run reads coming from the stand map's prediction of the year before.
Run on a compute node (needs ~120 GB host RAM for the training table; the timed loop itself is small):
  PARTITION=priority QOS=priority NCPUS=32 TIME=02:00:00 \
    scripts/sbatch_python.sh bench-coupled scripts/bench_coupled_speed.py   (env: G, SCEN, NYEARS, CHECK_TAG)

SETUP (offline, NOT timed, multithreaded): the stand map's training table for held-out climate model G
(explore_panel_stand_map.build_rows, unseen run m4), the six structure models of the year-by-year arm (ADR 0330,
explore_panel_yearly_drift: same features, targets, LightGBM settings) and the twelve stand models (ADR 0331); the five
networks of the deployment daily model (arm D, ADR 0335/0336) on CPU.

THE TIMED LOOP (time.process_time = CPU time of the whole process; torch, LightGBM and BLAS limited to 1 thread), for
each year y = 2020..2100 over all 1 050 panel cells, leg G_ssp370, run m4:
  1. the daily model: 365 days of inputs with incrementally updated trailing windows (as f2_train.bench_speed), the
     five-network ensemble, the closed bucket (float64, as f2_train.run_free); it reads the stand at the end of y-1 --
     the original's for 2020 (the known start), the stand map's prediction afterwards;
  2. the yearly climate statistics from year y's daily weather (explore_glob_climate.year_features: tas, pr, rsds,
     lwnet, huss of the leg's own forcing; wind is synthetic -- the daily arrays carry none, and the function is
     branch-free, so its cost does not depend on the values) and the 30-year running-window update;
  3. the feature matrices: a copy of the per-cell, per-year lookup rows (anchors, start levels, offsets -- built offline
     from the original's runs, as in deployment) and of the 25 trailing-window climate columns;
  4. the six structure models and the twelve stand models predict year y; the stand vector for year y+1's daily run.
STATED SIMPLIFICATIONS: the climate columns the models read in step 3 are the training table's values for that year
(computed offline from the same weather by the same function), not step 2's output, so that the predictions equal the
validated arms'; step 2 is still computed and paid for. The daily model's soil capacity per year is the original's (as
in every scored run of the daily model, f2_train). No I/O is timed.
CHECKS (a label is not evidence): (a) the refitted structure and stand models reproduce the saved predictions
(LightGBM multithreaded training is not bit-reproducible: median |diff| <= 1e-6 and max <= 1 % of the quantity's
90th-percentile size; a relative error per row is meaningless for plant covers near 0); (b) the
loop's annual GPP / ET / NPP / runoff for run m4 reproduce the scored phase-B run of the same model and stand (DATA/
runs/<CHECK_TAG>/annual.npz, GPU, float32 inputs): median per-cell |relative difference| of the 2021-2100 mean < 1e-3.
THE ORIGINAL, for the ratio (ADR 0084 / 0086, cell 42490, 1 core, marginal rate): 0.267 core-s per cell-year at 25
patches (the panel's count); ~6.7 at the ~500 patches of publication runs.
"""

from __future__ import annotations

import os

for _v in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_climate as GC  # noqa: E402
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_stand_map as SM  # noqa: E402
import explore_panel_yearly_drift as YD  # noqa: E402
import f2_train as F  # noqa: E402
from explore_de_climate import daylength_hours  # noqa: E402

G = os.environ.get("G", "gfdl-esm4")
SCEN = os.environ.get("SCEN", "ssp370")
LEG = f"{G}_{SCEN}"
DLEG = LEG + "_daily" if G in ("gfdl-esm4", "ipsl-cm6a-lr", "mri-esm2-0") else LEG
K = 4  # the unseen run
MEMBERS = [f"D_3x256_seed{i}" for i in range(5)]
CHECK_TAG = os.environ.get("CHECK_TAG", "PD_B")
NYEARS = int(os.environ.get("NYEARS", "81"))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------------------------------ setup (offline, untimed)
import lightgbm as lgb  # noqa: E402
import torch  # noqa: E402

F.NH, F.NL, F.NPP_HEAD, F.DEEP_TAU = 256, 3, "ra", 365.0
F.DROP[:] = [F.FEAT["huss"]]
cells_df = pl.read_parquet(os.path.join(F.DATA, "cells.parquet"))
cell_ids = cells_df["Cell"].cast(pl.Int32).to_numpy()
lat = cells_df["lat"].to_numpy().astype(np.float32)
nc = len(cell_ids)

tr, te = SM.build_rows(G, K)
fs, fx = YD.feats(), SM.stand_feats()
assert all(c in fx for c in fs), "the structure features must be a subset of the stand features"
si = [fx.index(c) for c in fs]
models_s, models_x = {}, {}
t0 = time.time()
for q in YD.QS:
    t = tr.filter(pl.col(q).is_not_null() & pl.col(f"anc_{q}").is_not_null())
    if q in YD.LOG_EPS:
        y = np.log((t[q].to_numpy() + YD.LOG_EPS[q]) / (t[f"anc_{q}"].to_numpy() + YD.LOG_EPS[q]))
    else:
        y = (t[q] - t[f"anc_{q}"]).to_numpy()
    models_s[q] = lgb.train(A7.PARAMS, lgb.Dataset(t.select(fs).to_numpy(), y), A7.ROUNDS)
for q in SM.SQ:
    t = tr.filter(pl.col(q).is_not_null() & pl.col(f"anc_{q}").is_not_null())
    models_x[q] = lgb.train(A7.PARAMS, lgb.Dataset(t.select(fx).to_numpy(), (t[q] - t[f"anc_{q}"]).to_numpy()),
                            A7.ROUNDS)
log(f"fitted {len(models_s)} structure + {len(models_x)} stand models ({time.time() - t0:.0f} s wall, offline)")
del tr

# per-year lookup rows, aligned to the daily model's cell order (cells without a row stay NaN -> original's stand)
ty = te.filter((pl.col("member") == K) & (pl.col("leg") == LEG))
grid = pl.DataFrame({"Cell": np.repeat(cell_ids, NYEARS), "pos": np.repeat(np.arange(nc), NYEARS),
                     "Year": np.tile(np.arange(2020, 2020 + NYEARS), nc).astype(np.int32)})
j = grid.join(ty.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32)),
              on=["Cell", "Year"], how="left").sort("Year", "pos")  # rows = (year, the daily model's cell order)
LOOK = j.select(fx).to_numpy().astype(np.float64).reshape(NYEARS, nc, len(fx))
ANC_S = {q: j[f"anc_{q}"].to_numpy().astype(float).reshape(NYEARS, nc) for q in YD.QS}
ANC_X = {q: j[f"anc_{q}"].to_numpy().astype(float).reshape(NYEARS, nc) for q in SM.SQ}
have = np.isfinite(j["anc_lai_stand"].to_numpy().astype(float)).reshape(NYEARS, nc)
ci = [fx.index(c) for c in YD.CLIM]
CLIMW = LOOK[:, :, ci].copy()  # the trailing-window climate columns, copied into the matrix each year
log(f"lookup rows: {NYEARS} years x {nc} cells x {len(fx)} features; cell-years without a row {int((~have).sum())}")

# CHECK (a): refitted models vs the saved predictions (multithreaded, untimed)
X_all = LOOK.reshape(-1, len(fx))
ok_a = True
for kind, models, anc, pf in (("structure", models_s, ANC_S, os.path.join(YD.OUT, f"preds_{G}.parquet")),
                              ("stand", models_x, ANC_X, os.path.join(SM.OUT, SM.pred_name(G, K)))):
    old = pl.read_parquet(pf).filter((pl.col("member") == K) & (pl.col("leg") == LEG)).with_columns(
        pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32))
    old = grid.join(old, on=["Cell", "Year"], how="left").sort("Year", "pos")
    for q, m in models.items():
        p = m.predict(X_all[:, si] if kind == "structure" else X_all)
        a = anc[q].reshape(-1)
        if q in YD.LOG_EPS and kind == "structure":
            p = (a + YD.LOG_EPS[q]) * np.exp(p) - YD.LOG_EPS[q]
        else:
            p = p + a
        if kind == "stand" or q == "n_per_patch":
            p = np.maximum(p, 0.0)
        o = old[q].to_numpy().astype(float)
        f = np.isfinite(o) & np.isfinite(p)
        d = np.abs(p[f] - o[f])
        scale = np.quantile(np.abs(o[f]), 0.9) if f.any() else np.nan  # the quantity's own size (covers are ~1e-3)
        rel = d.max() / max(scale, 1e-12) if f.any() else np.nan
        good = f.any() and np.median(d) <= 1e-6 * max(scale, 1e-12) and rel < 0.01
        ok_a &= bool(good)
        log(f"CHECK (a) {kind} {q}: {int(f.sum())} rows, median |diff| {np.median(d):.2e}, "
            f"max |diff| per 90th-pct size {rel:.2e} "
            f"-> {'OK' if good else 'MISMATCH'}")

# the daily model
dev = torch.device("cpu")
nets = []
for t in MEMBERS:
    n, ck = F.load_net(os.path.join(F.DATA, "runs", t, "model.pt"), dev)
    n.load_state_dict(ck)
    nets.append(n.eval())
net = F.Ensemble(nets).eval()
tag = f"m{K}_{DLEG}"
forc = np.load(os.path.join(F.DATA, f"forc_{tag}.npy"))  # (nc, WARM + ND, 5) tas pr rsds lwnet huss
daily0 = np.load(os.path.join(F.DATA, f"daily_{tag}.npy"), mmap_mode="r")
W0 = np.array(daily0[:, 0, F.RM], dtype=np.float64)
S0 = np.array(daily0[:, 0, F.SWE], dtype=np.float64)
st0 = F.stand_features(np.load(os.path.join(F.DATA, f"stand_{tag}.npy")))  # (nc, 82, 12); index 0 = end of 2019
cap = np.load(os.path.join(F.DATA, f"cap_{tag}.npy"))
sinA, cosA, slat = F.calendar_features(lat)
hs = F.hemisphere_sign(slat)
dl_tab = F.daylength(lat, np.arange(1, 366)).astype(np.float32)  # (nc, 365): a per-cell table in deployment

# climate statistics inputs
dlh = daylength_hours(lat.astype(float))
win, hsm = GC.window_mask(lat.astype(float)), GC.summer_mask(lat.astype(float))
prm = GC.pft_temp_params()
lo, hi = prm["temp_low"].to_numpy(), prm["temp_high"].to_numpy()
WIND = np.abs(np.random.default_rng(1).normal(3, 1, (nc, 365)))

# ------------------------------------------------------------------------------------------ the timed loop
torch.set_num_threads(1)
T = {k: 0.0 for k in ("daily", "climate", "window", "features", "structure", "stand")}
ann = np.zeros((nc, NYEARS, 4))  # gpp, et, npp, runoff
struct_out = {q: np.zeros((NYEARS, nc)) for q in YD.QS}
st_cur = st0[:, 0].copy()  # stand read in 2020: the original's end of 2019
W, S, D = W0.copy(), S0.copy(), np.zeros(nc)
buf10 = forc[:, F.WARM - 10 : F.WARM, 0].copy()
buf30t = forc[:, F.WARM - 30 : F.WARM, 0].copy()
buf30r = forc[:, F.WARM - 30 : F.WARM, 2].copy()
pbuf = forc[:, : F.WARM, 1].copy()
sums = {"t10": buf10.sum(1), "t30": buf30t.sum(1), "r30": buf30r.sum(1), "p30": pbuf[:, -30:].sum(1),
        "p90": pbuf[:, -90:].sum(1), "p365": pbuf.sum(1)}
acc, ring, k_ring = None, None, 0
x = np.empty((nc, F.NIN), np.float32)
Xs = np.empty((nc, len(fx)))
wall0, cpu0 = time.perf_counter(), time.process_time()
with torch.no_grad():
    for iy in range(NYEARS):
        # 1. the daily model, year 2020 + iy, reading the stand at the end of the year before
        c0 = time.process_time()
        capy = cap[:, iy].astype(np.float64)
        capf = cap[:, iy].astype(np.float32)
        for dd in range(365):
            d = iy * 365 + dd
            f = forc[:, F.WARM + d]
            tas, pr = f[:, 0], f[:, 1]
            i10, i30, i365 = d % 10, d % 30, d % 365
            sums["t10"] += tas - buf10[:, i10]
            buf10[:, i10] = tas
            sums["t30"] += tas - buf30t[:, i30]
            buf30t[:, i30] = tas
            sums["r30"] += f[:, 2] - buf30r[:, i30]
            buf30r[:, i30] = f[:, 2]
            sums["p365"] += pr - pbuf[:, i365]
            sums["p90"] += pr - pbuf[:, (i365 - 90) % 365]
            sums["p30"] += pr - pbuf[:, (i365 - 30) % 365]
            pbuf[:, i365] = pr
            if d == 0:
                continue  # Jan 1 2020 is the initial state (as f2_train.run_free)
            x[:, 0], x[:, 1], x[:, 2], x[:, 3], x[:, 4] = tas, np.log1p(pr), f[:, 2], f[:, 3], f[:, 4] * 1000.0
            x[:, 5], x[:, 6], x[:, 7] = sums["t10"] / 10, sums["t30"] / 30, sums["r30"] / 30
            x[:, 8], x[:, 9] = np.log1p(sums["p30"]), np.log1p(sums["p90"])
            x[:, 10], x[:, 11] = np.log1p(sums["p365"]), dl_tab[:, dd]
            x[:, F.NFORC], x[:, F.NFORC + 1] = sinA[d] * hs, cosA[d] * hs
            x[:, F.NFORC + 2] = slat
            Wf = W.astype(np.float32)
            x[:, F.NFORC + 3] = Wf / np.maximum(capf, 1.0)
            x[:, F.NFORC + 4] = Wf / 1000.0
            x[:, F.NFORC + 5] = np.log1p(S.astype(np.float32))
            x[:, F.NFORC + 6] = capf / 1000.0
            x[:, F.NFORC + 7 :] = st_cur
            x[:, F.DROP] = 0.0
            y = net(torch.from_numpy(x), torch.from_numpy(pr.astype(np.float32)),
                    torch.from_numpy(S.astype(np.float32))).numpy().astype(np.float64)
            W, S, D, runoff, *_ = F.bucket_step(y, pr.astype(np.float64), W, S, D, capy)
            ann[:, iy, 0] += y[:, 6]
            ann[:, iy, 1] += y[:, 1] + y[:, 2] + y[:, 3]
            ann[:, iy, 2] += y[:, 7]
            ann[:, iy, 3] += runoff
        c1 = time.process_time()
        T["daily"] += c1 - c0
        # 2. yearly climate statistics from this year's daily weather + the 30-year running window
        sl = slice(F.WARM + iy * 365, F.WARM + (iy + 1) * 365)
        res, _ = GC.year_features(forc[:, sl, 0].astype(float), forc[:, sl, 1].astype(float),
                                  forc[:, sl, 4].astype(float), forc[:, sl, 2].astype(float),
                                  forc[:, sl, 3].astype(float), WIND, dlh, win, hsm, lo, hi)
        c2 = time.process_time()
        T["climate"] += c2 - c1
        stack = np.stack([np.asarray(v, dtype=float) for v in res.values()], 1)
        if acc is None:
            acc, ring = np.zeros_like(stack), np.zeros((30, *stack.shape))
        acc += stack - ring[k_ring % 30]
        ring[k_ring % 30] = stack
        k_ring += 1
        _ = acc / min(k_ring, 30)
        c3 = time.process_time()
        T["window"] += c3 - c2
        # 3. the feature matrices
        Xs[:] = LOOK[iy]
        Xs[:, ci] = CLIMW[iy]
        Xstruct = np.ascontiguousarray(Xs[:, si])
        c4 = time.process_time()
        T["features"] += c4 - c3
        # 4. structure and stand models for year y; the stand vector for next year's daily run
        for q, m in models_s.items():
            p = m.predict(Xstruct, num_threads=1)
            a = ANC_S[q][iy]
            struct_out[q][iy] = (a + YD.LOG_EPS[q]) * np.exp(p) - YD.LOG_EPS[q] if q in YD.LOG_EPS else p + a
        c5 = time.process_time()
        T["structure"] += c5 - c4
        new = np.empty((nc, len(SM.SQ)))
        for jq, (q, m) in enumerate(models_x.items()):
            new[:, jq] = np.maximum(m.predict(Xs, num_threads=1) + ANC_X[q][iy], 0.0)
        if iy + 1 < NYEARS:
            nxt = st0[:, iy + 1].copy()  # cells without a prediction keep the original's (as the phase-B arrays)
            new[:, 1] = np.log1p(new[:, 1])  # the daily model's stand input: lai, log1p(vegc), fpc 1..10
            ok = have[iy][:, None] & np.isfinite(new)
            nxt[ok] = new[ok]
            st_cur = nxt.astype(np.float32)
        T["stand"] += time.process_time() - c5
cpu_tot, wall_tot = time.process_time() - cpu0, time.perf_counter() - wall0
cy = nc * NYEARS
log(f"TIMED LOOP: {NYEARS} years x {nc} cells = {cy} cell-years; CPU {cpu_tot:.1f} s, wall {wall_tot:.1f} s "
    f"(CPU / wall = {cpu_tot / wall_tot:.2f}; 1.00 = one core)")
for k, v in T.items():
    log(f"  {k:10s} {v / cy:.3e} core-s per cell-year ({100 * v / cpu_tot:.1f} %)")
per = cpu_tot / cy
log(f"END-TO-END: {per:.3e} core-s per cell-year (one core, all parts in one loop). Earlier sum of separately timed "
    f"parts: 6.5e-3 (ADR 0330). The original: 0.267 at 25 patches -> {0.267 / per:.0f}x less; ~6.7 at 500 patches "
    f"-> {6.7 / per:.0f}x less.")

# CHECK (b): the loop's fluxes vs the scored phase-B run
ok_b = None
npz = os.path.join(F.DATA, "runs", CHECK_TAG, "annual.npz")
if NYEARS == F.NY and os.path.exists(npz):
    ref = np.load(npz)[f"free__{DLEG}"][K - 1]  # (nc, NY, 4): gpp, et, npp, runoff (f2_train.ANNUAL order)
    ok_b = True
    for jv, v in enumerate(F.ANNUAL):
        a, b = ann[:, 1:, jv].mean(1), ref[:, 1:, jv].mean(1)
        m = np.abs(b) > 1.0
        r = np.abs(a[m] / b[m] - 1)
        tot = a[m].sum() / b[m].sum() - 1
        ok_b &= bool(np.median(r) < 1e-3)
        log(f"CHECK (b) {v}: {int(m.sum())} cells, median |rel diff| of the 2021-2100 mean {np.median(r):.2e}, "
            f"90th pct {np.quantile(r, 0.9):.2e}, total {tot:+.2e} -> {'OK' if np.median(r) < 1e-3 else 'MISMATCH'}")
else:
    log(f"CHECK (b) skipped: {npz} missing or NYEARS < {F.NY}")
np.savez(os.path.join(F.DATA, "runs", f"bench_coupled_{LEG}.npz"), ann=ann, **{f"s_{q}": v for q, v in
                                                                               struct_out.items()})
log(f"checks: (a) {'OK' if ok_a else 'MISMATCH'}, (b) {ok_b}")
log("=== DONE")
