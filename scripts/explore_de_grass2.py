#!/usr/bin/env python3
"""explore_de_grass2.py — LINE X, Germany emulator, track A-TAB: a GRASS model that can collapse to ~0 under a
closing canopy (candidate replacement for the A3 grass heads), and its GRASS-ONLY free-run test.

Why (fourth session, 2026-10-02): replaying the original's grass inside the tabular free run closes 54-85 % of its
drift; the A3 grass heads are three deterministic L2 mean regressions of next-year grass fpc / LAI / agb on the raw
scale, iterated forward. Facts this script rests on, measured on the original's patch table (ACCESS s1, 2000/2040):
  * grass is ONE degree of freedom: agb = 23.673 * LAI to 6 digits in every patch, and fpc = 1 - exp(-0.5 LAI)
    except where grass + visible tree cover reaches ~0.92-0.98 (a cap on total cover, incl. the unseen < 5 m trees);
  * grass fpc is bimodal (30 % of patch-years < 1e-3, 25 % > 0.5) and persistent in LOG space (corr 0.988);
  * once below 1e-4 it stays below 1e-3 the next year in 97.5 % of patches.
MODEL (grass2)  state z = log(LAI + EPS). dz = z_{y+1} - z_y by the same two-stage boosted fit as every A-TAB head
  (B0 state, B1 climate fitted to B0's residual; raw = B0 + kappa B1). Stochastic arms add a residual drawn from the
  out-of-fold residuals per decile of the predicted z_{y+1} (iid, or AR(1) per patch with the measured rho).
  Closure: agb = AGB_PER_LAI * LAI; fpc = min(1 - exp(-K LAI), max(0, 1 - treefpc_{y+1} - delta(treefpc_{y+1}))),
  delta = the median unseen cover per tree-cover bin where the cap binds (training rows).
TEST (replay)  the original's own trees, year by year (1985 -> 2043, Historical then the ssp370 leg), only the grass
  free: arms orig / persist (1985 grass forever) / A3 (old heads) / G2m (mean) / G2s (iid draws) / G2ar (AR draws).
  Strata: every patch, the grass under living stems >= 15 m (stem-weighted, the basis of the growth attribution),
  and tree-cover bins. Also a one-step held-out score of A3 vs G2m on the same rows. Gates are pre-registered in
  _status/G2.md BEFORE the run.
OUTPUT  models  /p/tmp/jamirp/X_de/tab/models/<split>/grass2_*   (B0/B1 boosters, meta json, residual npz)
        eval    /p/tmp/jamirp/X_de/shared/eval/grass2_replay_<gcm>_s<seed>.csv (+ _onestep.csv, _summary.json)
STAGES  train --split DEV-A | replay --gcm ACCESS-CM2 --seed 1 --leg ssp370 | submit train|replay|both
Nothing Germany-specific is hard-coded: the grass PFT, K, AGB_PER_LAI and delta are read / fitted from the data.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as th  # noqa: E402

XDE = tr.XDE
EVAL = os.path.join(XDE, "shared", "eval")
STATUS = os.path.join(XDE, "_status", "G2.md")
EPS = 1e-6
GT = F.GRASS_TYPES[0]
GF, GL, GA = f"grass{GT}_fpc_y", f"grass{GT}_LAI_y", f"grass{GT}_agb_y"
B0F = (["z_y", GF, "sum_fpc_y", "sum_fpc_y1", "d_sum_fpc", "slack_y1", "n_live_y", "sum_agb_y", "frac_loss_lag0",
        "frac_loss_lag1", "frac_loss_lag2", "soil_code"] + [f"c85_{f}" for f in F.C85_F])
B1F = th.GRASS_CLIM + ["sum_fpc_y", "z_y"]
HBIG = 15.0


def status(msg):
    smoke = "[smoke, code path only] " if os.environ.get("TAB_SMOKE") == "1" else ""
    line = f"- {time.strftime('%Y-%m-%d %H:%M')} {smoke}{msg}"
    with open(STATUS, "a") as fh:
        fh.write(line + "\n")
    print(line, flush=True)


def add_g2(D: pl.DataFrame) -> pl.DataFrame:
    return D.with_columns(z_y=(pl.col(GL).cast(pl.Float64) + EPS).log(),
                          slack_y1=1.0 - pl.col("sum_fpc_y1") - pl.col(GF))


# ================================================================================================ train
def fit_closure(D: pl.DataFrame, nb=20) -> dict:
    """K from the uncapped patches, AGB_PER_LAI, and delta(treefpc) where the total-cover cap binds."""
    L1 = D["g_LAI_y1"].to_numpy().astype(np.float64)
    g1 = D["g_fpc_y1"].to_numpy().astype(np.float64)
    A1 = D["g_agb_y1"].to_numpy().astype(np.float64)
    t1 = D["sum_fpc_y1"].to_numpy().astype(np.float64)
    m = (L1 > 1e-4) & (L1 < 1.0)
    kk = -np.log(1 - g1[m]) / L1[m]
    K = float(np.quantile(kk, 0.9))  # uncapped rows sit exactly on K; capped ones below it
    apl = A1[L1 > 1e-4] / L1[L1 > 1e-4]
    pot = 1 - np.exp(-K * L1)
    bind = pot > g1 + 1e-4
    d = 1 - g1 - t1
    edges = np.quantile(t1[bind], np.linspace(0, 1, nb + 1)[1:-1]) if bind.sum() > nb else np.zeros(nb - 1)
    b = np.searchsorted(edges, t1[bind])
    med = [float(np.median(d[bind][b == i])) if (b == i).any() else float(np.median(d[bind])) for i in range(nb)]
    return {"K": K, "K_q": np.quantile(kk, [0.5, 0.9, 0.99]).tolist(), "AGB_PER_LAI": float(np.median(apl)),
            "agb_per_lai_q": np.quantile(apl, [0.001, 0.999]).tolist(), "bind_frac": float(bind.mean()),
            "delta_edges": edges.tolist(), "delta_med": med, "LAI_max": float(L1.max())}


def closure(L, t1, C):
    b = np.searchsorted(np.asarray(C["delta_edges"]), t1)
    cap = np.maximum(1.0 - t1 - np.asarray(C["delta_med"])[b], 0.0)
    return np.minimum(1 - np.exp(-C["K"] * L), cap), C["AGB_PER_LAI"] * L


def stage_train(a):
    spec = json.load(open(os.path.join(F.SAMPLES, a.split, "split.json")))
    D = th.grass_frame(a.split, "train", spec["train"], spec["cells_train"], frac=a.frac)
    D = add_g2(D).with_columns(dz=(pl.col("g_LAI_y1").cast(pl.Float64) + EPS).log() - pl.col("z_y"))
    folds = pl.read_parquet(os.path.join(tr.REG, "folds.parquet")).select(pl.col("Cell").cast(pl.Int16), "fold")
    D = D.join(folds, on="Cell", how="left")
    va = D["fold"].to_numpy() == spec["val_fold"]
    C = fit_closure(D.filter(pl.Series(~va)))
    # closure check on the validation rows with the TRUE next-year LAI
    fh, _ = closure(D["g_LAI_y1"].to_numpy()[va].astype(np.float64), D["sum_fpc_y1"].to_numpy()[va], C)
    err = np.abs(fh - D["g_fpc_y1"].to_numpy()[va])
    C["closure_abs_err_q50_90_99"] = np.quantile(err, [0.5, 0.9, 0.99]).tolist()
    y = D["dz"].to_numpy().astype(np.float64)
    X0, X1 = F.to_matrix(D, B0F), F.to_matrix(D, B1F)
    b0, b1, s0, info = th.fit_two_stage(B0F, B1F, X0, X1, y, np.ones_like(y), ~va, va, "regression",
                                        (a.rounds0, a.rounds1))
    s1 = b1.predict(X1, raw_score=True)
    d = th.mdir(a.split)
    b0.save_model(os.path.join(d, "grass2_dz_B0.txt"), num_iteration=b0.best_iteration)
    b1.save_model(os.path.join(d, "grass2_dz_B1.txt"), num_iteration=b1.best_iteration)
    # residual tables (OOF = validation fold) per decile of predicted z_{y+1}, one per kappa
    z = D["z_y"].to_numpy()[va]
    yv = y[va]
    rng = np.random.default_rng(5)
    resid = {}
    Ov = D.filter(pl.Series(va)).select("member", "Cell", "Patch", "Year")
    for k, p in (("k1", s0[va] + s1[va]), ("k0", s0[va])):
        r = yv - p
        z1p = z + p
        edges = np.quantile(z1p, np.linspace(0, 1, 11)[1:-1])
        b = np.searchsorted(edges, z1p)
        tabs = {f"d{i}": rng.choice(r[b == i], size=min(20000, int((b == i).sum())), replace=False).astype(np.float32)
                for i in range(10)}
        np.savez(os.path.join(d, f"grass2_resid_{k}.npz"), edges=edges, **tabs)
        # AR(1) of the residual along each patch's years
        E = Ov.with_columns(e=pl.Series(r), b=pl.Series(b.astype(np.int8)))
        J = E.join(E.select("member", "Cell", "Patch", (pl.col("Year") - 1).cast(pl.Int16).alias("Year"),
                            pl.col("e").alias("e1")), on=["member", "Cell", "Patch", "Year"], how="inner")
        e0, e1, bj = J["e"].to_numpy(), J["e1"].to_numpy(), J["b"].to_numpy()
        resid[k] = {"edges": edges.tolist(), "sd": [float(np.std(tabs[f"d{i}"])) for i in range(10)],
                    "rho_pooled": float(np.corrcoef(e0, e1)[0, 1]),
                    "rho": [float(np.corrcoef(e0[bj == i], e1[bj == i])[0, 1]) if (bj == i).sum() > 30 else 0.0
                            for i in range(10)],
                    "n_pairs": int(J.height), "rmse_dz": float(np.sqrt(np.mean(r ** 2)))}
    pers = float(np.sqrt(np.mean(yv ** 2)))
    meta = {"head": "grass2", "split": a.split, "EPS": EPS, "grass_type": GT, "features_B0": B0F,
            "features_B1": B1F, "closure": C, "resid": resid, "n_rows": D.height, "n_val": int(va.sum()),
            "rmse_dz_persistence_val": pers, **info, "gain_B0": th.gains(b0, B0F), "gain_B1": th.gains(b1, B1F)}
    json.dump(meta, open(os.path.join(d, "grass2_meta.json"), "w"), indent=1)
    status(f"train {a.split}: {D.height} patch rows; K {C['K']:.4f}, agb/LAI {C['AGB_PER_LAI']:.4f}, cap binds "
           f"{C['bind_frac']:.3f}, closure |err| q50/90/99 {np.round(C['closure_abs_err_q50_90_99'], 4).tolist()}; "
           f"val rmse dz: persistence {pers:.4f}, B0 {resid['k0']['rmse_dz']:.4f}, B0+B1 "
           f"{resid['k1']['rmse_dz']:.4f}; residual rho {resid['k1']['rho_pooled']:.3f}; B0 {info['b0_best_iter']} "
           f"it, B1 {info['b1_best_iter']} it")


# ================================================================================================ predictors
class Grass2:
    def __init__(self, split="DEV-A", kappa=1.0):
        import lightgbm as lgb
        d = th.mdir(split)
        self.meta = json.load(open(os.path.join(d, "grass2_meta.json")))
        self.b0 = lgb.Booster(model_file=os.path.join(d, "grass2_dz_B0.txt"))
        self.b1 = lgb.Booster(model_file=os.path.join(d, "grass2_dz_B1.txt"))
        self.kappa = kappa
        k = "k1" if kappa != 0 else "k0"
        R = np.load(os.path.join(d, f"grass2_resid_{k}.npz"))
        self.edges = R["edges"]
        self.tabs = [R[f"d{i}"] for i in range(10)]
        self.rho = self.meta["resid"][k]["rho_pooled"]
        self.C = self.meta["closure"]

    def mean_dz(self, X: pl.DataFrame):
        s = self.b0.predict(F.to_matrix(X, B0F), raw_score=True)
        if self.kappa:
            s = s + self.kappa * self.b1.predict(F.to_matrix(X, B1F), raw_score=True)
        return s

    def draw(self, z1p, rng):
        b = np.searchsorted(self.edges, z1p)
        r = np.empty_like(z1p)
        for i in range(10):
            m = b == i
            if m.any():
                r[m] = self.tabs[i][rng.integers(0, len(self.tabs[i]), int(m.sum()))]
        return r

    def step(self, X, t1, rng=None, e_prev=None, ar=False):
        """-> fpc, LAI, agb at y+1 and the residual carried (AR)."""
        z = X["z_y"].to_numpy()
        z1 = z + self.mean_dz(X)
        e = np.zeros_like(z1)
        if rng is not None:
            r = self.draw(z1, rng)
            e = self.rho * e_prev + np.sqrt(1 - self.rho ** 2) * r if (ar and e_prev is not None) else r
        z1 = np.clip(z1 + e, np.log(EPS), np.log(self.C["LAI_max"] * 1.2 + EPS))
        L = np.maximum(np.exp(z1) - EPS, 0.0)
        fpc, agb = closure(L, t1, self.C)
        return fpc, L, agb, e


class A3Old:
    """The A3 heads exactly as the stepper calls them (clip fpc to [0, 1], LAI / agb >= 0)."""

    def __init__(self, split="DEV-A", kappa=1.0):
        import lightgbm as lgb
        d = th.mdir(split)
        self.m = {}
        for t in ("g_fpc_y1", "g_LAI_y1", "g_agb_y1"):
            meta = json.load(open(os.path.join(d, f"grass_{t}_meta.json")))
            self.m[t] = (lgb.Booster(model_file=os.path.join(d, f"grass_{t}_B0.txt")),
                         lgb.Booster(model_file=os.path.join(d, f"grass_{t}_B1.txt")), meta)
        self.kappa = kappa

    def step(self, X):
        out = {}
        for t, (b0, b1, meta) in self.m.items():
            s = b0.predict(F.to_matrix(X, meta["features_B0"]), raw_score=True)
            out[t] = s + self.kappa * b1.predict(F.to_matrix(X, meta["features_B1"]), raw_score=True)
        return np.clip(out["g_fpc_y1"], 0, 1), np.maximum(out["g_LAI_y1"], 0), np.maximum(out["g_agb_y1"], 0)


# ================================================================================================ replay
def original_series(gcm, seed, leg, cells):
    """The original's patch rows, state years 1985..(last-1), Historical then <leg>, with next-year tree cover and
    grass, the y+1 climate and the cell statics; one row per (Cell, Patch, Year)."""
    hm, lm = f"{gcm}_Historical_s{seed}_h1985", f"{gcm}_{leg}_s{seed}_w2015"
    cols = ["member", "gcm", "traj", "seed", "Year", "Cell", "Patch", GF, GL, GA, "sum_fpc_y", "n_live_y",
            "sum_agb_y", "frac_loss_lag0", "frac_loss_lag1", "frac_loss_lag2"]
    parts = []
    for m in (hm, lm):
        fs = sorted(glob.glob(os.path.join(F.PATCHT, F.CELLSET, m, "cb=*", "y*.parquet")))
        parts.append(pl.scan_parquet(fs).filter(pl.col("Cell").is_in(cells)).select(cols).collect())
    D = pl.concat(parts)
    assert D.select("Cell", "Patch", "Year").n_unique() == D.height, "duplicate patch-years across the two members"
    nx = D.select("Cell", "Patch", (pl.col("Year") - 1).cast(pl.Int16).alias("Year"),
                  pl.col("sum_fpc_y").alias("sum_fpc_y1"), pl.col(GF).alias("g_fpc_y1"),
                  pl.col(GL).alias("g_LAI_y1"), pl.col(GA).alias("g_agb_y1"))
    D = D.join(nx, on=["Cell", "Patch", "Year"], how="inner").with_columns(
        d_sum_fpc=pl.col("sum_fpc_y1") - pl.col("sum_fpc_y"))
    D = tr.join_climate(D, cols=[f"anom_{f}" for f in F.CLIM_F] + F.ABS_Y1, years=("y1",), ext=True)
    D = D.with_columns(*[pl.col(f"anom_{f}_y1").alias(f"a_{f}_y1") for f in F.CLIM_F])
    D = D.join(F.statics(gcm), on="Cell", how="left")
    miss = D.select(pl.any_horizontal(pl.col(th.GRASS_CLIM).is_null()).sum()).item()
    assert miss == 0, f"{miss} rows without climate"
    return D.sort("Year", "Cell", "Patch")


def big_stem_counts(gcm, seed, leg, cells):
    out = []
    for m in (f"{gcm}_Historical_s{seed}_h1985", f"{gcm}_{leg}_s{seed}_w2015"):
        out.append(pl.scan_parquet(os.path.join(XDE, "ind_dev", f"{m}.parquet"))
                   .filter(pl.col("Cell").is_in(cells) & (pl.col("isdead") == 0) & (pl.col("Height") >= HBIG)
                           & (pl.col("Type") < 7))
                   .group_by("Cell", "Patch", "Year").agg(pl.len().alias("n15")).collect())
    return pl.concat(out).unique(["Cell", "Patch", "Year"], keep="first")


def wquant(x, w, q):
    o = np.argsort(x)
    cw = np.cumsum(w[o])
    return float(x[o][np.searchsorted(cw, q * cw[-1])]) if cw[-1] > 0 else float("nan")


def summarise(arm, Y, fpc, L, tcov, n15, fold5):
    rows = []
    for sub, sm in (("all", np.ones_like(fold5)), ("fold5", fold5)):
        sm = sm.astype(bool)
        strata = {"all": np.ones(len(fpc), bool)}
        for lo, hi in ((0, 0.3), (0.3, 0.45), (0.45, 0.6), (0.6, 1.01)):
            strata[f"cov{lo}-{hi}"] = (tcov >= lo) & (tcov < hi)
        for s, m in strata.items():
            m = m & sm
            if not m.any():
                continue
            rows.append(dict(arm=arm, Year=Y, cells=sub, stratum=s, n=int(m.sum()), fpc_mean=float(fpc[m].mean()),
                             fpc_med=float(np.median(fpc[m])), p_lt1e3=float((fpc[m] < 1e-3).mean()),
                             lai_mean=float(L[m].mean())))
        w = n15 * sm
        if w.sum() > 0:
            rows.append(dict(arm=arm, Year=Y, cells=sub, stratum="under15m", n=int(w.sum()),
                             fpc_mean=float((fpc * w).sum() / w.sum()), fpc_med=wquant(fpc, w, 0.5),
                             p_lt1e3=float(((fpc < 1e-3) * w).sum() / w.sum()),
                             lai_mean=float((L * w).sum() / w.sum())))
    return rows


def stage_replay(a):
    spec = json.load(open(os.path.join(F.SAMPLES, a.split, "split.json")))
    folds = pl.read_parquet(os.path.join(tr.REG, "folds.parquet")).select(pl.col("Cell").cast(pl.Int16), "fold")
    cells = sorted(pl.read_parquet(F.patch_file(f"{a.gcm}_Historical_s{a.seed}_h1985", 1985),
                                   columns=["Cell"])["Cell"].unique().to_list())
    if a.max_cells:
        cells = cells[: a.max_cells]
    t0 = time.time()
    D = original_series(a.gcm, a.seed, a.leg, cells)
    N = big_stem_counts(a.gcm, a.seed, a.leg, cells)
    years = sorted(D["Year"].unique().to_list())
    byY = {y: g for (y,), g in D.partition_by("Year", as_dict=True, maintain_order=True).items()}
    ref = byY[years[0]].select("Cell", "Patch")
    for y in years:
        assert byY[y].select("Cell", "Patch").equals(ref), f"patch set changes in {y}"
    npt = ref.height
    f5 = ref.join(folds, on="Cell", how="left")["fold"].to_numpy() == spec["heldout_fold"]
    print(f"replay {a.gcm} s{a.seed} {a.leg}: {len(cells)} cells, {npt} patches, years {years[0]}..{years[-1]} "
          f"(+1), built in {time.time() - t0:.0f} s", flush=True)
    G2 = Grass2(a.split, kappa=1.0)
    A3 = A3Old(a.split, kappa=1.0)
    arms = ["orig", "persist", "A3", "G2m", "G2s", "G2ar"]
    rng = {k: np.random.default_rng(1000 + i) for i, k in enumerate(arms)}
    y0 = years[0]
    st = {k: {v: byY[y0][c].cast(pl.Float64).to_numpy().copy() for v, c in (("fpc", GF), ("LAI", GL), ("agb", GA))}
          for k in arms}
    e_prev = np.zeros(npt)
    rows, one = [], []

    def n15_at(Y):
        j = ref.with_columns(Year=pl.lit(Y, pl.Int16)).join(N, on=["Cell", "Patch", "Year"], how="left")
        return j["n15"].fill_null(0).to_numpy().astype(np.float64)

    tcov0 = byY[y0]["sum_fpc_y"].to_numpy()
    for k in arms:
        rows += summarise(k, y0, st[k]["fpc"], st[k]["LAI"], tcov0, n15_at(y0), f5)
    for y in years:
        X0 = byY[y]
        t1 = X0["sum_fpc_y1"].to_numpy().astype(np.float64)
        new = {"orig": (X0["g_fpc_y1"].to_numpy(), X0["g_LAI_y1"].to_numpy(), X0["g_agb_y1"].to_numpy()),
               "persist": (st["persist"]["fpc"], st["persist"]["LAI"], st["persist"]["agb"])}
        for k in ("A3", "G2m", "G2s", "G2ar"):
            X = add_g2(X0.with_columns(**{GF: pl.Series(st[k]["fpc"]), GL: pl.Series(st[k]["LAI"]),
                                          GA: pl.Series(st[k]["agb"])}))
            if k == "A3":
                new[k] = A3.step(X)
            elif k == "G2m":
                new[k] = G2.step(X, t1)[:3]
            elif k == "G2s":
                new[k] = G2.step(X, t1, rng[k])[:3]
            else:
                fp, L, ag, e_prev = G2.step(X, t1, rng[k], e_prev, ar=True)
                new[k] = (fp, L, ag)
        # one-step held-out score on the ORIGINAL's state (teacher-forced) — A3 vs G2 mean vs persistence
        Xo = add_g2(X0)
        g_true = X0["g_fpc_y1"].to_numpy().astype(np.float64)
        g_now = X0[GF].to_numpy().astype(np.float64)
        p_a3 = A3.step(Xo)[0]
        p_g2 = G2.step(Xo, t1)[0]
        for lo, hi in ((0, 1e-3), (1e-3, 1e-2), (1e-2, 0.1), (0.1, 0.5), (0.5, 1.01)):
            m = (g_now >= lo) & (g_now < hi)
            if m.any():
                one.append(dict(Year=y, gbin=f"{lo}-{hi}", n=int(m.sum()), true_mean=float(g_true[m].mean()),
                                A3_mean=float(p_a3[m].mean()), G2m_mean=float(p_g2[m].mean()),
                                rmse_A3=float(np.sqrt(np.mean((p_a3[m] - g_true[m]) ** 2))),
                                rmse_G2m=float(np.sqrt(np.mean((p_g2[m] - g_true[m]) ** 2))),
                                rmse_persist=float(np.sqrt(np.mean((g_now[m] - g_true[m]) ** 2)))))
        Y = y + 1
        tcov = t1
        nY = n15_at(Y)
        for k in arms:
            fp, L, ag = (np.asarray(v, np.float64) for v in new[k])
            st[k] = {"fpc": fp, "LAI": L, "agb": ag}
            rows += summarise(k, Y, fp, L, tcov, nY, f5)
        if y % 10 == 0:
            print(f"  {Y} done ({time.time() - t0:.0f} s)", flush=True)
    os.makedirs(EVAL, exist_ok=True)
    tag = f"{a.gcm}_s{a.seed}_{a.leg}" + (f"_c{a.max_cells}" if a.max_cells else "")
    R = pl.DataFrame(rows)
    R.write_csv(os.path.join(EVAL, f"grass2_replay_{tag}.csv"))
    OS = pl.DataFrame(one)
    OS.write_csv(os.path.join(EVAL, f"grass2_replay_{tag}_onestep.csv"))
    summary = gates(R, OS)
    json.dump(summary, open(os.path.join(EVAL, f"grass2_replay_{tag}_summary.json"), "w"), indent=1)
    status(f"replay {tag}: " + json.dumps(summary["headline"]))


def gates(R: pl.DataFrame, OS: pl.DataFrame) -> dict:
    """The pre-registered gates of _status/G2.md, on the 2026-2035 mean (and 1995-2004 for the historic leg)."""
    out = {"windows": {}, "headline": {}}
    for wn, (lo, hi) in (("1995-2004", (1995, 2004)), ("2026-2035", (2026, 2035))):
        W = (R.filter(pl.col("Year").is_between(lo, hi)).group_by("arm", "cells", "stratum")
             .agg(pl.col("fpc_mean", "fpc_med", "p_lt1e3", "lai_mean").mean()))
        res = {}
        for cs in ("all", "fold5"):
            o = {r["stratum"]: r for r in W.filter((pl.col("arm") == "orig") & (pl.col("cells") == cs)).to_dicts()}
            for arm in ("persist", "A3", "G2m", "G2s", "G2ar"):
                a_ = {r["stratum"]: r for r in W.filter((pl.col("arm") == arm) & (pl.col("cells") == cs)).to_dicts()}
                u, p = a_.get("under15m"), a_.get("all")
                uo, po = o.get("under15m"), o.get("all")
                g = {"u15_med": [u["fpc_med"], uo["fpc_med"]], "u15_mean": [u["fpc_mean"], uo["fpc_mean"]],
                     "all_mean": [p["fpc_mean"], po["fpc_mean"]], "all_p_lt1e3": [p["p_lt1e3"], po["p_lt1e3"]],
                     "all_lai_mean": [p["lai_mean"], po["lai_mean"]]}
                g["pass"] = {
                    "u15_med": abs(u["fpc_med"] - uo["fpc_med"]) <= 0.005,
                    "u15_mean": abs(u["fpc_mean"] / uo["fpc_mean"] - 1) <= 0.20,
                    "all_mean": abs(p["fpc_mean"] / po["fpc_mean"] - 1) <= 0.10,
                    "all_p_lt1e3": abs(p["p_lt1e3"] - po["p_lt1e3"]) <= 0.05,
                    "all_lai_mean": abs(p["lai_mean"] / po["lai_mean"] - 1) <= 0.10}
                g["all_pass"] = all(g["pass"].values())
                res[f"{cs}/{arm}"] = g
        out["windows"][wn] = res
    w = out["windows"]["2026-2035"]
    out["headline"] = {k: {"pass": v["all_pass"], "u15_med": np.round(v["u15_med"], 4).tolist(),
                           "all_mean": np.round(v["all_mean"], 4).tolist()} for k, v in w.items()
                       if k.startswith("all/")}
    one = OS.group_by("gbin").agg((pl.col(c) * pl.col("n")).sum() / pl.col("n").sum() for c in
                                 ("true_mean", "A3_mean", "G2m_mean")).sort("gbin")
    out["onestep_mean_by_current_grass"] = one.to_dicts()
    return out


# ================================================================================================ submit
def stage_submit(a):
    jd = os.path.join(XDE, "tab", "_jobs")
    os.makedirs(jd, exist_ok=True)
    py = sys.executable
    me = os.path.abspath(__file__)
    cmds = []
    if a.what in ("train", "both"):
        cmds.append(f"{py} {me} train --split {a.split}")
    if a.what in ("replay", "both"):
        cmds.append(f"{py} {me} replay --split {a.split} --gcm {a.gcm} --seed {a.seed} --leg {a.leg}")
    js = os.path.join(jd, f"G2_{a.what}.sh")
    with open(js, "w") as fh:
        fh.write(f"#!/bin/bash\n#SBATCH --account=waldspektrum --partition=priority --qos=priority\n"
                 f"#SBATCH --job-name=X-grass2 --cpus-per-task=32 --time=03:00:00\n"
                 f"#SBATCH --output={jd}/G2_{a.what}.%j.out\nset -euo pipefail\n"
                 f"export POLARS_MAX_THREADS=32 SLURM_CPUS_PER_TASK=32\n" + "\n".join(cmds)
                 + "\necho '=== JOB DONE ==='\n")
    print(os.popen(f"sbatch {js}").read().strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["train", "replay", "submit"])
    ap.add_argument("what", nargs="?", default="both")
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--frac", type=float, default=0.25)
    ap.add_argument("--rounds0", type=int, default=3000)
    ap.add_argument("--rounds1", type=int, default=1000)
    ap.add_argument("--gcm", default="ACCESS-CM2")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--max-cells", type=int, default=0)
    a = ap.parse_args()
    {"train": stage_train, "replay": stage_replay, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
