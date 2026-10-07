"""explore_de_nppmodel2.py — LINE X, Germany emulator: the NPP route with a LOSS model and a per-tree spread.
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "I9 NPP route + LOSS model + per-tree spread")

I8 (explore_de_nppmodel.py) modelled the tree's log NPP change and thresholded it against LAST year's loss, with one
global residual sd. Its own ceiling (true NPP, last year's loss) was 0.83-0.97 and its mean ran high. In the C
(turnover_tree.c:55-97) the loss is turnover of the start-of-year pools + reprod_cost * gain + cmass_excess (a phenology
fraction of what is left) + debt payback — part of it moves with this year's gain. Here:
  W   log(npp_y1/npp_y)                                    on tree state + weather            (I8's model, refitted)
  L   log(L_y1/L_y)                                        on tree state + weather + TRUE NPP change + log(L_y/gain_y)
  M   margin log(gain_y1/L_y1)                             on tree state + weather + log(L_y/gain_y)
  MN  M without the weather anomalies (null)
each with a second booster on its log squared out-of-year residual (per-tree spread, "h"). Implied P(G_y1 < 0):
  W / Wh   Phi((thr - mu_W) / sd_W),                 thr = log(L_y/gain_y)
  WLh      sum_k w_k Phi((mu_L(lr_k) - lr_k + thr) / sd_L(lr_k)),  lr_k = mu_W + sd_W x_k (9 Gauss-Hermite nodes)
  cfL      the same with lr = the TRUE NPP change (the loss model's own ceiling)
  M / Mh / MNh   Phi(-mu_M / sd_M)
Usage:  python explore_de_nppmodel2.py fit W|L|M|MN   -> tab/models/DEV-A/npp2/<arm>.*
        python explore_de_nppmodel2.py score          -> shared/eval/nppmodel2_yearly.csv
        python explore_de_nppmodel2.py fit MS / score_ms -> the stepper-feasible margin model (no npp / transp /
                                                         wscal_mean input; thr missing for first-printed trees)
"""

from __future__ import annotations

import json
import os
import sys
import time
import zlib

import numpy as np
import polars as pl
from scipy.stats import norm

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_bmdelta as bd  # noqa: E402
import explore_de_gsign_info as gi  # noqa: E402
import explore_de_nppmodel as nm  # noqa: E402

MDIR = os.path.join(gi.XDE, "tab", "models", "DEV-A", "npp2")
TEST_FRAC = 0.3
JOIN = ["gcm", "traj", "seed", "Cell", "Year"]
P = dict(objective="regression", learning_rate=0.1, num_leaves=127, min_data_in_leaf=200, feature_fraction=0.7,
         bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1,
         num_threads=int(os.environ.get("OMP_NUM_THREADS", "8")), seed=7)
PS = dict(P, learning_rate=0.05, num_leaves=31, min_data_in_leaf=1000)
NSD = 300
GAIN_EPS = 1e-3
MS_DROP = ("npp", "transp", "wscal_mean")


def weather():
    X, sets = gi.features(pl.read_parquet(gi.AGG))
    wcols = [c for c in sets["B"] if c not in sets["0"]] + [c for c in sets["0"] if c.startswith("c85_")]
    W = X.select("gcm", "traj", pl.col("seed").cast(pl.Int8), pl.col("Cell").cast(pl.Int16),
                 pl.col("Year").cast(pl.Int16), "clim_scen_y1", "clim_year_y1", *wcols)
    return W, wcols


def y1_side(d: pl.DataFrame) -> pl.DataFrame:
    """Next-year gain and loss; keep rows where both are defined (uncensored G_y1, leaf area > 0)."""
    d = d.filter((pl.col("cenG_y1") == 0) & (pl.col("LAI_y1") > 0) & (pl.col("fpc_ind_y1") > 0))
    d = d.with_columns(*bd.side("_y1"))
    return d.filter(pl.col("L") > 0).with_columns(
        ll=(pl.col("L_y1").clip(1e-6) / pl.col("L")).log(),
        m=(pl.col("gain_y1").clip(GAIN_EPS) / pl.col("L_y1").clip(1e-6)).log())


def arm_spec(arm: str, wcols: list[str]) -> tuple[list[str], str]:
    clim = [c for c in wcols if c.startswith("c85_")]
    return {"W": (nm.TREE + wcols, "lr"),
            "L": (nm.TREE + wcols + ["lr", "thr"], "ll"),
            "M": (nm.TREE + wcols + ["thr"], "m"),
            "MN": (nm.TREE + clim + ["thr"], "m"),
            # stepper-feasible margin model: no per-tree flux inputs the TAB roster does not carry (npp, transp,
            # wscal_mean); thr is the tree's own previous margin (-m_y), NaN for a first-printed tree (is_new_y)
            "MS": ([c for c in nm.TREE if c not in MS_DROP] + wcols + ["thr"], "m")}[arm]


def stage_fit(arm: str):
    import lightgbm as lgb

    t0 = time.time()
    W, wcols = weather()
    TR = pl.concat([nm.load(m, frac=nm.FRAC) for m in nm.TRAIN], how="vertical_relaxed").join(W, on=JOIN, how="left")
    assert TR[wcols[0]].null_count() == 0
    if arm != "W":  # W keeps I8's rows exactly; the loss / margin targets need next year's loss
        TR = y1_side(TR)
    if arm == "MS":  # a recruit's first step has no carried margin in the stepper: train it as missing too
        TR = TR.with_columns(thr=pl.when(pl.col("is_new_y").fill_null(False)).then(None).otherwise(pl.col("thr")))
        print(f"arm MS: thr set missing on {int(TR['thr'].null_count())} first-printed rows", flush=True)
    TR = TR.with_columns(grp=pl.concat_str([pl.col("clim_scen_y1"), pl.col("clim_year_y1").cast(pl.Utf8)])
                         .map_elements(lambda s: zlib.crc32(s.encode()) % gi.NGRP, return_dtype=pl.Int64))
    cols, tgt = arm_spec(arm, wcols)
    print(f"arm {arm}: train rows {TR.height}, {len(cols)} features, target {tgt} ({time.time() - t0:.0f}s)",
          flush=True)
    Xt = TR.select(cols).to_numpy().astype(np.float32)
    y, g = TR[tgt].to_numpy(), TR["grp"].to_numpy()
    oof, best = np.full(len(y), np.nan), []
    for k in range(gi.NGRP):
        te, es = g == k, g == (k + 1) % gi.NGRP
        trn = ~(te | es)
        b = lgb.train(P, lgb.Dataset(Xt[trn], y[trn], categorical_feature=[0]), num_boost_round=3000,
                      valid_sets=[lgb.Dataset(Xt[es], y[es], categorical_feature=[0])],
                      callbacks=[lgb.early_stopping(50, verbose=False)])
        best.append(b.best_iteration)
        oof[te] = b.predict(Xt[te], num_iteration=b.best_iteration)
        print(f"  fold {k}: best {b.best_iteration} ({time.time() - t0:.0f}s)", flush=True)
    res = y - oof
    sd = float(np.std(res))
    print(f"arm {arm}: out-of-year residual sd {sd:.4f} (target sd {y.std():.4f}, R2 {1 - res.var() / y.var():.3f})",
          flush=True)
    bf = lgb.train(P, lgb.Dataset(Xt, y, categorical_feature=[0]), num_boost_round=int(np.median(best)))
    # per-tree spread: log squared out-of-year residual, then a constant so that mean(res^2 / s^2) = 1
    z = np.log(res ** 2 + 1e-4 * res.var())
    bs = lgb.train(PS, lgb.Dataset(Xt, z, categorical_feature=[0]), num_boost_round=NSD)
    zs = bs.predict(Xt)
    c = float(np.log(np.mean(res ** 2 / np.exp(zs))))
    s = np.exp(0.5 * (zs + c))
    q = np.quantile(s, np.linspace(0, 1, 11))
    dec = np.clip(np.searchsorted(q, s, side="right") - 1, 0, 9)
    calib = [float(np.std(res[dec == i] / s[dec == i])) for i in range(10)]
    print(f"arm {arm}: spread sd range {q[0]:.4f}-{q[-1]:.4f}; z-score sd by spread decile "
          + " ".join(f"{v:.2f}" for v in calib), flush=True)
    os.makedirs(MDIR, exist_ok=True)
    bf.save_model(os.path.join(MDIR, f"{arm}.mu.txt"))
    bs.save_model(os.path.join(MDIR, f"{arm}.sd.txt"))
    json.dump(dict(cols=cols, target=tgt, sd=sd, c=c, best=best, calib=calib, n=int(TR.height)),
              open(os.path.join(MDIR, f"{arm}.json"), "w"), indent=1)
    print(f"saved {arm} ({time.time() - t0:.0f}s)")


class Arm:
    def __init__(self, arm: str):
        import lightgbm as lgb

        self.meta = json.load(open(os.path.join(MDIR, f"{arm}.json")))
        self.mu = lgb.Booster(model_file=os.path.join(MDIR, f"{arm}.mu.txt"))
        self.sdb = lgb.Booster(model_file=os.path.join(MDIR, f"{arm}.sd.txt"))
        self.cols = self.meta["cols"]

    def pred(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return self.mu.predict(X), np.exp(0.5 * (self.sdb.predict(X) + self.meta["c"]))


def stage_score():
    t0 = time.time()
    W, wcols = weather()
    A = {a: Arm(a) for a in ("W", "L", "M", "MN")}
    xk, wk = np.polynomial.hermite_e.hermegauss(9)
    wk = wk / wk.sum()
    c2 = gi.cells200()
    rows = []
    for mem in nm.TEST:
        D = y1_side(nm.load(mem, cells=c2, frac=TEST_FRAC).join(W, on=JOIN, how="left"))
        assert D[wcols[0]].null_count() == 0
        thr, lr = D["thr"].to_numpy(), D["lr"].to_numpy()
        out = D.select("Year", true=(pl.col("gain_y1") < pl.col("L_y1")).cast(pl.Float64),
                       cf_gain=(pl.col("gain_y1") < pl.col("L")).cast(pl.Float64))
        XW = D.select(A["W"].cols).to_numpy().astype(np.float32)
        muW, sW = A["W"].pred(XW)
        p = {"W": norm.cdf((thr - muW) / A["W"].meta["sd"]), "Wh": norm.cdf((thr - muW) / sW)}
        XL = D.select(A["L"].cols).to_numpy().astype(np.float32)
        il = A["L"].cols.index("lr")

        def ploss(lrv, XL=XL, il=il, thr=thr):
            XL[:, il] = lrv
            muL, sL = A["L"].pred(XL)
            return norm.cdf((muL - lrv + thr) / sL)

        p["cfL"] = ploss(lr)
        p["WLh"] = sum(w * ploss(muW + sW * x) for x, w in zip(xk, wk, strict=True))
        for a in ("M", "MN"):
            mu, s = A[a].pred(D.select(A[a].cols).to_numpy().astype(np.float32))
            p[a + "h"] = norm.cdf(-mu / s)
            if a == "M":
                p["M"] = norm.cdf(-mu / A[a].meta["sd"])
        out = out.with_columns(*[pl.Series(f"p_{k}", v) for k, v in p.items()])
        Y = out.group_by("Year").agg(pl.all().mean(), n=pl.len()).sort("Year").with_columns(member=pl.lit(mem))
        rows.append(Y)
        print(f"{mem}: {D.height} trees, true mean {Y['true'].mean():.4f} ({time.time() - t0:.0f}s)", flush=True)
        windows = [("all", Y)]
        if mem.startswith("ACCESS") or "ssp245" in mem:
            windows.append(("2015-44", Y.filter(pl.col("Year") >= 2014)))
        for wn, Yw in windows:
            if Yw.height < 10:
                continue
            t = Yw["true"].to_numpy()
            for c in ["cf_gain"] + [f"p_{k}" for k in p]:
                e = Yw[c].to_numpy()
                print(f"   {wn:7s} {c:8s} corr {np.corrcoef(t, e)[0, 1]:.3f}  slope "
                      f"{np.cov(t, e)[0, 1] / t.var(ddof=1):.3f}  mean {e.mean():.4f} (true {t.mean():.4f})",
                      flush=True)
    path = os.path.join(gi.EVAL, "nppmodel2_yearly.csv")
    pl.concat(rows).write_csv(path)
    print("wrote", path)


def stage_score_ms():
    """MS (stepper-feasible margin) vs Mh one step on the I9 test rows: same members, cells, tree sample; MS sees thr
    missing on first-printed rows exactly as the stepper will."""
    t0 = time.time()
    W, wcols = weather()
    A = {a: Arm(a) for a in ("M", "MS")}
    c2 = gi.cells200()
    rows = []
    for mem in nm.TEST:
        D = y1_side(nm.load(mem, cells=c2, frac=TEST_FRAC).join(W, on=JOIN, how="left"))
        assert D[wcols[0]].null_count() == 0
        out = D.select("Year", true=(pl.col("gain_y1") < pl.col("L_y1")).cast(pl.Float64))
        mu, s = A["M"].pred(D.select(A["M"].cols).to_numpy().astype(np.float32))
        DS = D.with_columns(thr=pl.when(pl.col("is_new_y").fill_null(False)).then(None).otherwise(pl.col("thr")))
        muS, sS = A["MS"].pred(DS.select(A["MS"].cols).to_numpy().astype(np.float32))
        out = out.with_columns(p_Mh=pl.Series(norm.cdf(-mu / s)), p_MSh=pl.Series(norm.cdf(-muS / sS)))
        Y = out.group_by("Year").agg(pl.all().mean(), n=pl.len()).sort("Year").with_columns(member=pl.lit(mem))
        rows.append(Y)
        print(f"{mem}: {D.height} trees ({time.time() - t0:.0f}s)", flush=True)
        windows = [("all", Y)]
        if mem.startswith("ACCESS") or "ssp245" in mem:
            windows.append(("2015-44", Y.filter(pl.col("Year") >= 2014)))
        for wn, Yw in windows:
            if Yw.height < 10:
                continue
            t = Yw["true"].to_numpy()
            for c in ("p_Mh", "p_MSh"):
                e = Yw[c].to_numpy()
                print(f"   {wn:7s} {c:6s} corr {np.corrcoef(t, e)[0, 1]:.3f}  slope "
                      f"{np.cov(t, e)[0, 1] / t.var(ddof=1):.3f}  mean {e.mean():.4f} (true {t.mean():.4f})",
                      flush=True)
    path = os.path.join(gi.EVAL, "nppmodel2_ms_yearly.csv")
    pl.concat(rows).write_csv(path)
    print("wrote", path)


def stage_score_ms_size():
    """MZ: one-step MSh negative-share bias by height class (< 10 / >= 10 m) and carried-margin presence, per member and
    period (<= 2013 / >= 2014 start year), truth vs mean Phi(-mu/s)."""
    W, wcols = weather()
    A = Arm("MS")
    c2 = gi.cells200()
    rows = []
    for mem in nm.TEST:
        D = y1_side(nm.load(mem, cells=c2, frac=TEST_FRAC).join(W, on=JOIN, how="left"))
        D = D.with_columns(thr=pl.when(pl.col("is_new_y").fill_null(False)).then(None).otherwise(pl.col("thr")))
        mu, s = A.pred(D.select(A.cols).to_numpy().astype(np.float32))
        T = D.select("Year", "Height", "thr").with_columns(
            true=(D["gain_y1"] < D["L_y1"]).cast(pl.Float64), p=pl.Series(norm.cdf(-mu / s)),
            hcls=pl.when(pl.col("Height") >= 10).then(pl.lit("ge10")).otherwise(pl.lit("lt10")),
            thr_ok=pl.col("thr").is_not_null(), per=pl.when(pl.col("Year") <= 2013).then(pl.lit("<=2013"))
            .otherwise(pl.lit(">=2014")))
        for keys in (["per", "hcls"], ["per", "hcls", "thr_ok"]):
            G = (T.group_by(keys).agg(pl.col("true", "p").mean(), n=pl.len()).with_columns(
                member=pl.lit(mem), bias=pl.col("p") - pl.col("true")).sort(keys))
            rows.append(G)
            print(mem, keys)
            print(G.with_columns(pl.col(pl.Float64).round(4)), flush=True)
    path = os.path.join(gi.EVAL, "nppmodel2_ms_size.csv")
    pl.concat(rows, how="diagonal_relaxed").write_csv(path)
    print("wrote", path)


def stage_shared(nrep: int = 20):
    """I10: how much of the margin model's residual is SHARED by the trees of a cell-year, and does drawing that part as
    a common shock restore the amplitude of the yearly swings? Split fitted on ACCESS Historical (held-out GCM, past
    weather), applied to the futures + MPI ssp245. Per member: residual r = m - mu_M; rho = var(cell-year mean of r,
    corrected for its finite-n sampling part) / var(r). Simulation: m* = mu_M + s_M (sqrt(rho) z_cy + sqrt(1-rho) z_i),
    yearly share of m* < 0 per replicate; reported: mean single-realisation corr / slope with the truth, and the ratio
    of the simulated yearly share sd to truth's (amplitude)."""
    t0 = time.time()
    W, wcols = weather()
    M = Arm("M")
    c2 = gi.cells200()
    rng = np.random.default_rng(11)
    rho_fit = None
    rows = []
    for mem in ["ACCESS-CM2_Historical_s1_h1985"] + [m for m in nm.TEST if "Historical" not in m]:
        D = y1_side(nm.load(mem, cells=c2, frac=TEST_FRAC).join(W, on=JOIN, how="left"))
        mu, s = M.pred(D.select(M.cols).to_numpy().astype(np.float32))
        D = D.select("Year", "Cell", "m", true=(pl.col("gain_y1") < pl.col("L_y1")).cast(pl.Float64)).with_columns(
            z=pl.Series((D["m"].to_numpy() - mu) / s), mu=pl.Series(mu), s=pl.Series(s))
        G = D.group_by("Year", "Cell").agg(zb=pl.col("z").mean(), n=pl.len(), zv=pl.col("z").var())
        zb, n = G["zb"].to_numpy(), G["n"].to_numpy()
        vb = float(np.var(zb) - np.mean(G["zv"].fill_null(0).to_numpy() / n))
        rho = max(vb, 0.0) / float(D["z"].var())
        if rho_fit is None:
            rho_fit = rho
        cy = D.select(k=pl.col("Year").cast(pl.Int64) * 100000 + pl.col("Cell").cast(pl.Int64))["k"].to_numpy()
        _, inv = np.unique(cy, return_inverse=True)
        yr = D["Year"].to_numpy()
        T = D.group_by("Year").agg(pl.col("true").mean()).sort("Year")
        t = T["true"].to_numpy()
        mu_a, s_a = D["mu"].to_numpy(), D["s"].to_numpy()
        res = {}
        for lab, r_ in (("indep", 0.0), ("shared", rho_fit)):
            cs, sl, amp = [], [], []
            for _ in range(nrep):
                zc = rng.standard_normal(inv.max() + 1)[inv]
                zi = rng.standard_normal(len(inv))
                neg = (mu_a + s_a * (np.sqrt(r_) * zc + np.sqrt(1 - r_) * zi)) < 0
                e = pl.DataFrame({"Year": yr, "neg": neg.astype(np.float64)}).group_by("Year").agg(
                    pl.col("neg").mean()).sort("Year")["neg"].to_numpy()
                cs.append(np.corrcoef(t, e)[0, 1])
                sl.append(np.cov(t, e)[0, 1] / t.var(ddof=1))
                amp.append(e.std() / t.std())
            res[lab] = (float(np.mean(cs)), float(np.mean(sl)), float(np.mean(amp)))
        rows.append(dict(member=mem, rho_member=rho, rho_used=rho_fit,
                         **{f"{k}_{q}": v[i] for k, v in res.items() for i, q in enumerate(("corr", "slope", "amp"))}))
        print(f"{mem}: rho {rho:.3f} (used {rho_fit:.3f}); indep corr/slope/amp {res['indep']}; shared "
              f"{res['shared']} ({time.time() - t0:.0f}s)", flush=True)
    path = os.path.join(gi.EVAL, "nppmodel2_shared.csv")
    pl.DataFrame(rows).write_csv(path)
    print("wrote", path)


if __name__ == "__main__":
    if sys.argv[1] == "fit":
        stage_fit(sys.argv[2])
    elif sys.argv[1] == "shared":
        stage_shared()
    elif sys.argv[1] == "score_ms":
        stage_score_ms()
    elif sys.argv[1] == "score_ms_size":
        stage_score_ms_size()
    else:
        stage_score()
