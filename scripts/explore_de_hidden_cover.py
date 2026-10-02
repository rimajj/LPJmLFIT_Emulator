#!/usr/bin/env python3
"""explore_de_hidden_cover.py — LINE X, Germany emulator: a carried HIDDEN-COVER state for the < 5 m trees, so that
the grass cover the recruit head reads keeps the original's patch-specific signal.

C rule (establishmentpft_ind.c:197-204, reduce_grass.c): after establishment, if total patch cover > 1 every grass
fpc is divided so that grass = 1 - ALL tree cover (printed > 5 m trees + the unprinted < 5 m layer + this year's
saplings); LAI/agb are untouched. So, with pot = 1 - exp(-K LAI) the grass's own cover and t the printed tree cover,
    grass fpc = min(pot, 1 - t - h),      h = the hidden < 5 m cover.
grass2 (explore_de_grass2.closure) replaces h by a per-tree-cover-bin median, which erases the patch-specific h the
recruit head relies on (_status/RG.md; _status/HR.md: dropping grass fpc costs the head 5.2 % deviance, and the TRUTH
of last year's h alone recovers 72 % of that => h persists enough to be worth carrying).

The model (HS) works on observables only — no latent imputation. State carried per patch at y: cap_y (the cap
binds), d_y = 1 - g_y - t_y (= h_y where cap_y; an upper bound on h_y elsewhere). Step y -> y+1, AFTER the tree step
(t_{y+1}, n recruits at y+1 known) and AFTER grass2 has produced LAI_{y+1} (=> pot_{y+1}):
    P(cap_{y+1})                       binary booster
    bite_{y+1} = pot_{y+1} - g_{y+1}   (> 1e-3 by definition where capped)  log-scale booster + residual draws
    g_{y+1} = pot_{y+1} - bite if capped else pot_{y+1},  clipped to [0, pot_{y+1}]
The recruit head (SH13, unchanged) then reads g as it always did.

STAGES
  train   --split DEV-A    training members, the grass2 patch thinning, val fold from the split spec
  onestep --gcm --seed --leg   on the ORIGINAL's trees and grass LAI (truth t_{y+1}, LAI_{y+1}, recruits): HS draws vs
          truth (P(cap) calibration, bite quantiles) and the SH13 recruit head on HS grass vs the original's grass vs
          the grass2 closure, 5-yr windows, + Poisson deviance.  -> shared/eval/hidden_cover_onestep_<tag>.csv
Pre-registration: _status/HS.md (written before the runs).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_grass2 as g2  # noqa: E402
import explore_de_sh_patchheads as ph  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as th  # noqa: E402

XDE = tr.XDE
EVAL = os.path.join(XDE, "shared", "eval")
STATUS = os.path.join(XDE, "_status", "HS.md")
LOGS = os.path.join(REPO, "logs")
PY = ph.PY
GF, GL = g2.GF, g2.GL
TOL = 1e-3
NTH = int(os.environ.get("SLURM_CPUS_PER_TASK", "8"))
FEAT = (["cap_y", "d_y", "h_y", "bite_y", "z_y", "pot_y1", "s_y1", "sum_fpc_y", "sum_fpc_y1", "d_sum_fpc",
         "n_recruit_y1", "n_live_y", "sum_agb_y", "frac_loss_lag0", "frac_loss_lag1", "frac_loss_lag2", "soil_code"]
        + [f"c85_{f}" for f in F.C85_F] + th.GRASS_CLIM)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def status(msg):
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {msg}\n")


def derive(D: pl.DataFrame, K: float, L1=None, t1=None) -> pl.DataFrame:
    """State features at y and the y+1 drivers. L1/t1 override the next-year grass LAI / tree cover (rollout)."""
    if L1 is not None:
        D = D.with_columns(pl.Series("_L1", L1))
    else:
        D = D.with_columns(pl.col("g_LAI_y1").cast(pl.Float64).alias("_L1"))
    if t1 is not None:
        D = D.with_columns(pl.Series("sum_fpc_y1", t1))
    L = pl.col(GL).cast(pl.Float64)
    g = pl.col(GF).cast(pl.Float64)
    t = pl.col("sum_fpc_y").cast(pl.Float64)
    pot = 1 - (-K * L).exp()
    D = D.with_columns(cap_y=((pot - g) > TOL).cast(pl.Float64), d_y=1 - g - t, bite_y=(pot - g).clip(lower_bound=0),
                       z_y=(L + g2.EPS).log(), pot_y1=1 - (-K * pl.col("_L1")).exp())
    return D.with_columns(h_y=pl.when(pl.col("cap_y") > 0).then(pl.col("d_y")).otherwise(None),
                          s_y1=1 - pl.col("sum_fpc_y1").cast(pl.Float64) - pl.col("pot_y1"),
                          d_sum_fpc=pl.col("sum_fpc_y1").cast(pl.Float64) - t).drop("_L1")


def add_recruits(D: pl.DataFrame) -> pl.DataFrame:
    """n_recruit_y1 per (member, Cell, Patch, Year) from the SH13 feature tables (recruits first printed at y+1)."""
    parts = []
    for m in D["member"].unique().to_list():
        parts.append(pl.scan_parquet(os.path.join(ph.FEAT, f"{m}.parquet"))
                     .select(pl.lit(m).alias("member"), "Year", "Cell", "Patch", "n_recruit_y1").collect())
    R = pl.concat(parts).with_columns(pl.col("Year").cast(D["Year"].dtype), pl.col("Cell").cast(D["Cell"].dtype),
                                      pl.col("Patch").cast(D["Patch"].dtype))
    n0 = D.height
    D = D.join(R, on=["member", "Year", "Cell", "Patch"], how="inner")
    assert D.height == n0, f"recruit join lost rows {n0} -> {D.height}"
    return D


def targets(D):
    L1 = D["g_LAI_y1"].cast(pl.Float64).to_numpy()
    g1 = D["g_fpc_y1"].cast(pl.Float64).to_numpy()
    pot1 = D["pot_y1"].to_numpy()
    cap1 = (pot1 - g1) > TOL
    return L1, g1, pot1, cap1


def stage_train(a):
    import lightgbm as lgb
    spec = json.load(open(os.path.join(F.SAMPLES, a.split, "split.json")))
    K = float(g2.Grass2(a.split).C["K"])
    D = th.grass_frame(a.split, "train", spec["train"], spec["cells_train"], frac=a.frac)
    D = add_recruits(derive(D, K))
    folds = pl.read_parquet(os.path.join(tr.REG, "folds.parquet")).select(pl.col("Cell").cast(D["Cell"].dtype),
                                                                           "fold")
    D = D.join(folds, on="Cell", how="left")
    va = D["fold"].to_numpy() == spec["val_fold"]
    _, g1, pot1, cap1 = targets(D)
    X = F.to_matrix(D, FEAT)
    log(f"train: {D.height} rows ({va.sum()} val); cap binds next year in {cap1.mean():.3f}")
    base = dict(learning_rate=0.05, num_leaves=63, min_data_in_leaf=500, lambda_l2=1.0, feature_fraction=0.9,
                bagging_fraction=0.7, bagging_freq=1, max_bin=255, num_threads=NTH, verbose=-1, seed=17,
                deterministic=True, force_row_wise=True)
    cb = [lgb.early_stopping(50, verbose=False), lgb.log_evaluation(200)]
    dtr = lgb.Dataset(X[~va], cap1[~va].astype(float), feature_name=FEAT)
    dva = lgb.Dataset(X[va], cap1[va].astype(float), reference=dtr)
    bc = lgb.train(dict(base, objective="binary", metric="binary_logloss"), dtr, a.rounds, valid_sets=[dva],
                   callbacks=cb)
    s1 = D["s_y1"].to_numpy()
    yb = np.log(np.maximum(pot1 - g1, TOL)) if a.param == "bite" else (pot1 - g1) + s1  # h1 = 1 - g1 - t1
    mc = cap1
    dtr = lgb.Dataset(X[~va & mc], yb[~va & mc], feature_name=FEAT)
    dva = lgb.Dataset(X[va & mc], yb[va & mc], reference=dtr)
    bb = lgb.train(dict(base, objective="regression", metric="l2"), dtr, a.rounds, valid_sets=[dva], callbacks=cb)
    d = th.mdir(a.split)
    sfx = "" if a.param == "bite" else f"_{a.param}"
    bc.save_model(os.path.join(d, f"hs{sfx}_cap.txt"), num_iteration=bc.best_iteration)
    bb.save_model(os.path.join(d, f"hs{sfx}_bite.txt"), num_iteration=bb.best_iteration)
    # validation diagnostics + nulls
    p = bc.predict(X[va], num_iteration=bc.best_iteration)
    yv = cap1[va].astype(float)

    def ll(q):
        q = np.clip(q, 1e-6, 1 - 1e-6)
        return float(-np.mean(yv * np.log(q) + (1 - yv) * np.log(1 - q)))

    cy = D["cap_y"].to_numpy()
    trn = ~va
    pc = {k: cap1[trn & (cy == k)].mean() for k in (0.0, 1.0)}
    null_persist = np.where(cy[va] > 0, pc[1.0], pc[0.0])
    pr = bb.predict(X[va & mc], num_iteration=bb.best_iteration)
    r = yb[va & mc] - pr
    edges = np.quantile(pr, np.linspace(0, 1, 11)[1:-1])
    bins = np.searchsorted(edges, pr)
    rng = np.random.default_rng(7)
    tabs = {f"d{i}": rng.choice(r[bins == i], size=min(20000, int((bins == i).sum())), replace=False)
            .astype(np.float32) for i in range(10)}
    np.savez(os.path.join(d, f"hs{sfx}_bite_resid.npz"), edges=edges, **tabs)
    # null for bite: persistence of last year's bite where it was capped too, else the training median
    by = D["bite_y"].to_numpy()
    both = va & mc & (cy > 0)
    med = float(np.median(yb[trn & mc]))
    pers = np.log(np.maximum(by[both], TOL)) if a.param == "bite" else D["d_y"].to_numpy()[both]
    # the quantity that matters either way: the implied hidden cover h1 on capped val rows
    h_pred = (np.exp(pr) + s1[va & mc]) if a.param == "bite" else pr
    h_true = (pot1 - g1 + s1)[va & mc]
    meta = {"K": K, "TOL": TOL, "param": a.param, "features": FEAT,
            "h_val_rmse": float(np.sqrt(np.mean((h_pred - h_true) ** 2))),
            "h_val_rmse_null_median": float(np.sqrt(np.mean((h_true - np.median(h_true)) ** 2))),
            "h_val_rmse_null_persist_both": float(np.sqrt(np.mean(((pot1 - g1 + s1)[both]
                                                                   - D["d_y"].to_numpy()[both]) ** 2))),
            "h_val_corr": float(np.corrcoef(h_pred, h_true)[0, 1]), "n_rows": D.height, "n_val": int(va.sum()),
            "cap_frac_next": float(cap1.mean()),
            "cap_val_logloss": ll(p), "cap_val_logloss_null_persist": ll(null_persist),
            "cap_val_logloss_null_const": ll(np.full(yv.size, cap1[trn].mean())),
            "bite_val_rmse_log": float(np.sqrt(np.mean(r ** 2))),
            "bite_val_rmse_log_null_median": float(np.sqrt(np.mean((yb[va & mc] - med) ** 2))),
            "bite_val_rmse_log_on_both_capped": float(np.sqrt(np.mean((yb[both] - bb.predict(
                X[both], num_iteration=bb.best_iteration)) ** 2))),
            "bite_val_rmse_log_null_persist_both_capped": float(np.sqrt(np.mean((yb[both] - pers) ** 2))),
            "cap_iter": bc.best_iteration, "bite_iter": bb.best_iteration,
            "gain_cap": th.gains(bc, FEAT), "gain_bite": th.gains(bb, FEAT)}
    json.dump(meta, open(os.path.join(d, f"hs{sfx}_meta.json"), "w"), indent=1)
    msg = (f"train {a.split} param {a.param}: {D.height} rows; implied h rmse {meta['h_val_rmse']:.4f} (median null "
           f"{meta['h_val_rmse_null_median']:.4f}, corr {meta['h_val_corr']:.3f}; persistence on both-capped "
           f"{meta['h_val_rmse_null_persist_both']:.4f}); cap logloss {meta['cap_val_logloss']:.4f} (persist null "
           f"{meta['cap_val_logloss_null_persist']:.4f}, const {meta['cap_val_logloss_null_const']:.4f}); bite rmse "
           f"log {meta['bite_val_rmse_log']:.4f} (median null {meta['bite_val_rmse_log_null_median']:.4f}); on "
           f"both-capped {meta['bite_val_rmse_log_on_both_capped']:.4f} vs persistence "
           f"{meta['bite_val_rmse_log_null_persist_both_capped']:.4f}; iters {bc.best_iteration}/{bb.best_iteration}")
    log(msg)
    status(msg)


class HS:
    def __init__(self, split="DEV-A", param="bite"):
        import lightgbm as lgb
        d = th.mdir(split)
        sfx = "" if param == "bite" else f"_{param}"
        self.param = param
        self.meta = json.load(open(os.path.join(d, f"hs{sfx}_meta.json")))
        self.bc = lgb.Booster(model_file=os.path.join(d, f"hs{sfx}_cap.txt"))
        self.bb = lgb.Booster(model_file=os.path.join(d, f"hs{sfx}_bite.txt"))
        R = np.load(os.path.join(d, f"hs{sfx}_bite_resid.npz"))
        self.edges = R["edges"]
        self.tabs = [R[f"d{i}"] for i in range(10)]
        self.K = self.meta["K"]

    def step(self, D: pl.DataFrame, rng, u_cap=None, u_res=None):
        """D = derive()d frame (incl. n_recruit_y1). -> grass fpc at y+1. Uniforms from rng, or given (engine)."""
        if u_cap is None:
            u_cap = rng.random(D.height)
            u_res = rng.random(D.height)
        X = F.to_matrix(D, self.meta["features"])
        pc = self.bc.predict(X, num_threads=NTH)
        mb = self.bb.predict(X, num_threads=NTH)
        b = np.searchsorted(self.edges, mb)
        r = np.empty_like(mb)
        for i in range(10):
            m = b == i
            if m.any():
                tab = self.tabs[i]
                r[m] = tab[np.minimum((u_res[m] * len(tab)).astype(np.int64), len(tab) - 1)]
        pot1 = D["pot_y1"].to_numpy()
        if self.param == "bite":
            bite = np.exp(mb + r)
        else:  # h drawn, kept above the slack so that the cap really binds
            bite = np.maximum(mb + r - D["s_y1"].to_numpy(), TOL)
        cap = u_cap < pc
        g1 = np.where(cap, np.clip(pot1 - bite, 0.0, pot1), pot1)
        return g1, pc, cap


def stage_onestep(a):
    import explore_de_recruit_grass as rg
    t0 = time.time()
    cells = sorted(pl.read_parquet(g2.F.patch_file(f"{a.gcm}_Historical_s{a.seed}_h1985", 1985),
                                   columns=["Cell"])["Cell"].unique().to_list())
    D = g2.original_series(a.gcm, a.seed, a.leg, cells)
    S = rg.stored(a.gcm, a.seed, a.leg, cells)
    hs = HS(a.split, a.param)
    G2 = g2.Grass2(a.split, kappa=1.0)
    Hd = ph.load_heads(a.split)
    K = hs.K
    rng = np.random.default_rng(23)
    years = sorted(D["Year"].unique().to_list())
    byD = {y: g for (y,), g in D.partition_by("Year", as_dict=True, maintain_order=True).items()}
    byS = {y: g for (y,), g in S.partition_by("Year", as_dict=True, maintain_order=True).items()}
    rows = []
    for y in years:
        if y + 1 not in byS:
            continue
        X0 = byD[y]
        S1 = byS[y + 1]
        assert X0.select("Cell", "Patch").equals(S1.select("Cell", "Patch")), f"patch order {y}"
        Xd = derive(X0.with_columns(n_recruit_y1=byS[y]["n_recruit_y1"]), K)
        g_true = S1[GF].cast(pl.Float64).to_numpy()
        L1 = X0["g_LAI_y1"].cast(pl.Float64).to_numpy()
        t1 = X0["sum_fpc_y1"].cast(pl.Float64).to_numpy()
        assert np.max(np.abs(g_true - X0["g_fpc_y1"].cast(pl.Float64).to_numpy())) < 1e-5
        fc, _ = g2.closure(L1, t1, G2.C)
        srcs = {"orig": g_true, "closure": fc}
        for k in range(a.ndraw):
            g1, pc, cap = hs.step(Xd, rng)
            srcs[f"hs{k}"] = g1
        obs = S1["n_recruit_y1"].cast(pl.Float64).to_numpy()
        pot1 = Xd["pot_y1"].to_numpy()
        cap_true = (pot1 - g_true) > TOL
        mus = {k: Hd.recruit_mean(S1.with_columns(pl.Series(GF, v).cast(pl.Float32)), kappa=1.0)
               for k, v in srcs.items()}
        mus["hs_avg"] = np.mean([mus[f"hs{k}"] for k in range(a.ndraw)], axis=0)
        for k, mu in mus.items():
            if k.startswith("hs") and k != "hs_avg" and k != "hs0":
                continue
            rows.append(dict(Year=y + 1, src=k, mu_pp=float(mu.mean()), obs_pp=float(obs.mean()),
                             dev=ph.pois_dev(mu, obs), p_cap_model=float(pc.mean()), p_cap_true=float(cap_true.mean()),
                             g_mean=float(srcs.get(k, srcs["hs0"]).mean()), g_true_mean=float(g_true.mean())))
        if y % 10 == 0:
            log(f"{y} ({time.time() - t0:.0f} s)")
    R = pl.DataFrame(rows)
    tag = f"{a.gcm}_s{a.seed}_{a.leg}" + ("" if a.param == "bite" else f"_{a.param}")
    out = os.path.join(EVAL, f"hidden_cover_onestep_{tag}.csv")
    R.write_csv(out)
    W = R.with_columns(win=pl.col("Year") // 5 * 5).group_by("win", "src").agg(pl.col("mu_pp", "obs_pp", "dev").mean())
    base = W.filter(pl.col("src") == "orig").select("win", pl.col("mu_pp").alias("mo"))
    W = W.join(base, on="win").with_columns(rel=pl.col("mu_pp") / pl.col("mo") - 1)
    pl.Config.set_tbl_rows(100)
    pl.Config.set_tbl_width_chars(200)
    print("recruit head mean relative to the head on the original's grass, by 5-yr window")
    print(W.pivot(on="src", index="win", values="rel").sort("win").with_columns(pl.exclude("win").round(4)))
    print("Poisson deviance per patch-year")
    print(W.pivot(on="src", index="win", values="dev").sort("win").with_columns(pl.exclude("win").round(4)))
    C = R.filter(pl.col("src") == "hs0").select("Year", "p_cap_model", "p_cap_true", "g_mean", "g_true_mean")
    print(C.with_columns(win=pl.col("Year") // 5 * 5).group_by("win").agg(pl.exclude("Year").mean()).sort("win"))
    status(f"onestep {tag}: wrote {out}")
    log("wrote", out)


def stage_replay(a):
    """Grass-only FREE run on the original's trees: HS carries its own (cap, d, h, bite) state from 1985 on, i.e. the
    grass fpc it produced last year is what derive() reads next year. Two arms for the grass LAI: the original's
    (isolates HS's own drift) and grass2's AR free run (the arm a coupled run would use). The shipped recruit head reads
    each arm's grass fpc; compared with the head on the original's grass, and with the grass2 closure free run."""
    import explore_de_recruit_grass as rg
    t0 = time.time()
    cells = sorted(pl.read_parquet(g2.F.patch_file(f"{a.gcm}_Historical_s{a.seed}_h1985", 1985),
                                   columns=["Cell"])["Cell"].unique().to_list())
    D = g2.original_series(a.gcm, a.seed, a.leg, cells)
    S = rg.stored(a.gcm, a.seed, a.leg, cells)
    hs = HS(a.split, a.param)
    G2 = g2.Grass2(a.split, kappa=1.0)
    Hd = ph.load_heads(a.split)
    K = hs.K
    years = sorted(D["Year"].unique().to_list())
    byD = {y: g for (y,), g in D.partition_by("Year", as_dict=True, maintain_order=True).items()}
    byS = {y: g for (y,), g in S.partition_by("Year", as_dict=True, maintain_order=True).items()}
    sub200 = np.isin(byD[years[0]]["Cell"].to_numpy(), cells[:200])
    rng = {"hs_origL": np.random.default_rng(31), "hs_g2L": np.random.default_rng(32),
           "g2": np.random.default_rng(32)}
    X0 = byD[years[0]]
    st = {k: {c: X0[c].cast(pl.Float64).to_numpy().copy() for c in (g2.GF, g2.GL, g2.GA)} for k in rng}
    e_prev = {k: np.zeros(X0.height) for k in rng}
    rows = []
    for y in years:
        if y + 1 not in byS:
            break
        Xy = byD[y]
        t1 = Xy["sum_fpc_y1"].cast(pl.Float64).to_numpy()
        S1 = byS[y + 1]
        obs = S1["n_recruit_y1"].cast(pl.Float64).to_numpy()
        nrec = byS[y]["n_recruit_y1"]
        new = {}
        for k in rng:
            Xk = Xy.with_columns(*[pl.Series(c, st[k][c]) for c in (g2.GF, g2.GL, g2.GA)])
            if k == "hs_origL":
                L1 = Xy["g_LAI_y1"].cast(pl.Float64).to_numpy()
            else:  # grass2 AR free run of the LAI, from this arm's own grass
                _, L1, _, e_prev[k] = G2.step(g2.add_g2(Xk), t1, rng[k], e_prev[k], ar=True)
            if k == "g2":
                g1, _ = g2.closure(L1, t1, G2.C)
            else:
                g1, _, _ = hs.step(derive(Xk.with_columns(n_recruit_y1=nrec), K, L1=L1), rng[k])
            new[k] = {g2.GF: g1, g2.GL: L1, g2.GA: G2.C["AGB_PER_LAI"] * L1}
        st = new
        mu0 = Hd.recruit_mean(S1, kappa=1.0)
        g_true = S1[GF].cast(pl.Float64).to_numpy()
        for sub, m in (("all", np.ones(obs.size, bool)), ("c200", sub200)):
            rows.append(dict(Year=y + 1, src="orig", cells=sub, mu_pp=float(mu0[m].mean()), obs_pp=float(obs[m].mean()),
                             dev=ph.pois_dev(mu0[m], obs[m]), g_mean=float(g_true[m].mean()),
                             p_g_lt1e3=float((g_true[m] < 1e-3).mean())))
        for k in rng:
            mu = Hd.recruit_mean(S1.with_columns(pl.Series(GF, st[k][g2.GF]).cast(pl.Float32),
                                                 pl.Series(GL, st[k][g2.GL]).cast(pl.Float32),
                                                 pl.Series(g2.GA, st[k][g2.GA]).cast(pl.Float32)), kappa=1.0)
            for sub, m in (("all", np.ones(obs.size, bool)), ("c200", sub200)):
                rows.append(dict(Year=y + 1, src=k, cells=sub, mu_pp=float(mu[m].mean()), obs_pp=float(obs[m].mean()),
                                 dev=ph.pois_dev(mu[m], obs[m]), g_mean=float(st[k][g2.GF][m].mean()),
                                 p_g_lt1e3=float((st[k][g2.GF][m] < 1e-3).mean())))
        if y % 10 == 0:
            log(f"{y} ({time.time() - t0:.0f} s)")
    R = pl.DataFrame(rows)
    tag = f"{a.gcm}_s{a.seed}_{a.leg}" + ("" if a.param == "bite" else f"_{a.param}")
    out = os.path.join(EVAL, f"hidden_cover_replay_{tag}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(100)
    pl.Config.set_tbl_width_chars(200)
    for sub in ("all", "c200"):
        W = (R.filter(pl.col("cells") == sub).with_columns(win=pl.col("Year") // 5 * 5).group_by("win", "src")
             .agg(pl.col("mu_pp", "obs_pp", "dev", "g_mean", "p_g_lt1e3").mean()))
        base = W.filter(pl.col("src") == "orig").select("win", pl.col("mu_pp").alias("mo"))
        W = W.join(base, on="win").with_columns(rel=pl.col("mu_pp") / pl.col("mo") - 1)
        for v in ("rel", "dev", "g_mean", "p_g_lt1e3"):
            print(f"--- {sub}: {v}")
            print(W.pivot(on="src", index="win", values=v).sort("win").with_columns(pl.exclude("win").round(4)))
    status(f"replay {tag}: wrote {out}")
    log("wrote", out)


def stage_submit(a):
    me = os.path.abspath(__file__)

    def jcf(name, body, dep=None, cpus=16):
        f = os.path.join(XDE, "_jobs", f"HS_{name}.jcf")
        L = ["#!/bin/bash", f"#SBATCH --job-name=X-de-HS-{name}", "#SBATCH --account=waldspektrum",
             "#SBATCH --partition=priority", "#SBATCH --qos=priority", f"#SBATCH --cpus-per-task={cpus}",
             "#SBATCH --time=03:00:00", f"#SBATCH --output={LOGS}/X-de-HS-{name}.%j.out"]
        if dep:
            L.append(f"#SBATCH --dependency=afterok:{dep}")
        L += ["set -eu", f"export POLARS_MAX_THREADS={cpus}", body, 'echo "=== JOB DONE exit=$? ==="']
        open(f, "w").write("\n".join(L) + "\n")
        return subprocess.run(["sbatch", "--parsable", f], capture_output=True, text=True,
                              check=True).stdout.strip().split(";")[0]

    train_cmd = f"{PY} {me} train --split {a.split} --frac {a.frac} --param {a.param}"
    jt = None if (a.skip_train or a.replay) else jcf(f"train_{a.param}", train_cmd)
    if a.replay:
        jr = jcf(f"replay_{a.param}", f"{PY} {me} replay --split {a.split} --gcm {a.gcm} --seed {a.seed} --leg {a.leg} "
                 f"--param {a.param}")
        status(f"submitted replay {jr}")
        print(jr)
        return
    jo = jcf(f"onestep_{a.param}", f"{PY} {me} onestep --split {a.split} --gcm {a.gcm} --seed {a.seed} --leg {a.leg} "
             f"--param {a.param}", dep=jt)
    status(f"submitted train {jt}, onestep {jo}")
    print(jt, jo)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="stage", required=True)
    for s in ("train", "onestep", "replay", "submit"):
        p = sub.add_parser(s)
        p.add_argument("--split", default="DEV-A")
        p.add_argument("--frac", type=float, default=0.25)
        p.add_argument("--rounds", type=int, default=2000)
        p.add_argument("--gcm", default="ACCESS-CM2")
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--leg", default="ssp370")
        p.add_argument("--ndraw", type=int, default=4)
        p.add_argument("--skip-train", action="store_true")
        p.add_argument("--param", choices=["bite", "h"], default="bite")
        p.add_argument("--replay", action="store_true", help="submit: the grass-only free run")
    a = ap.parse_args()
    {"train": stage_train, "onestep": stage_onestep, "replay": stage_replay, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
