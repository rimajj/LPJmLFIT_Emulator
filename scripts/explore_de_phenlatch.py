"""explore_de_phenlatch.py — LINE X, Germany emulator: reconstruct the C's whole-leaf-drop LATCH per tree PFT from the
daily forcing, and test whether it carries the year-to-year negative-growth share.
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "I6 leaf-drop latch")

C path (individual = true, new_phenology = true; daily_natural.c:124 passes air temp and swdown):
  phenology_gsi.c:49-58  f += (logistic(driver) - f) * tau for f in tmin (temp), tmax (temp, falling), light (swdown);
                         each floored at epsilon. Water factor: 1 while layer-1 soil temp < 10 C, else a near-step in
                         the stem's own wscal - minwscal (NOT reconstructable here: soil water is not in the forcing;
                         this probe sets it to 1 and says so).
  phen = tmin * tmax * light * water;  then turnover_daily (turnover_daily_tree.c:42-76) with the day's phen and the
  aphen accumulated so far:  release if phen > 0.25 & latched & aphen > aphen_min;  DROP (whole leaf pool, aphen = 0,
  phen = 0, latched) if phen < 0.25 & aphen > aphen_min & not latched;  else drip if not latched.
  Then on day 14 (COLDEST_DAY_NHEMISPHERE, day 1-based) aphen = 0 and latch released; then aphen += phen.
  Annual (turnover_tree.c:100): leaf turnover = leaf_c/1.05 if latched at year end, else the accumulated daily sum
  = n_drops * leaf_c/1.05 + drip_days * leaf_c / max(longevity, 1.05) / 365.
Stages
  sim    per GCM, the 907 dev cells, Historical 1975-2014 then each ssp 2015-2044, the 7 tree PFTs ->
         shared/eval/phenlatch_dev.parquet (gcm, traj, Cell, Year, Type, n_drops, first_drop, latched_end, drip_days,
         + monthly mean factors for the gate)
  gate   reconstructed monthly mean tmin/tmax/light factors vs the C's mphen_pft_{tmin,tmax,light} (per-PFT bands)
  test   per-(Cell, Year, Type) negative-growth share from the trans table vs the latch; yearly correlations and the
         gsign_info out-of-year regressions with latch features added (set BL = B + latch)
Usage:  python explore_de_phenlatch.py sim|gate|test|all
"""

from __future__ import annotations

import glob
import os
import sys
import time
import zlib

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_climate as cl  # noqa: E402
import explore_de_gsign_info as gi  # noqa: E402

XDE = gi.XDE
OUTP = os.path.join(gi.EVAL, "phenlatch_dev.parquet")
GATEP = os.path.join(gi.EVAL, "phenlatch_gate.csv")
NT = 7
EPS = 1.0e-6  # [ASSUMPTION] LPJmL `epsilon` floor; only matters for the floor of a factor
COLDEST_DAY = 14
SIM0 = 1975  # spin the factors and the latch from here (Historical file starts 1950)


def pft_params():
    from pathlib import Path

    import build_mort_params_reference as b

    d, _ = b.cpp_json(Path(b.LPJROOT) / "par" / "pft_lpjmlfit.js")
    pft = d["pftpar"]
    P = {}
    for k in ("tmin", "tmax", "light"):
        P[k] = {f: np.array([pft[t][k][f] for t in range(NT)]) for f in ("slope", "base", "tau")}
    P["aphen_min"] = np.array([pft[t]["aphen_min"] for t in range(NT)], dtype=float)
    return P


def logistic(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -700, 700)))


def simulate(T: np.ndarray, S: np.ndarray, P: dict, years: np.ndarray, state=None):
    """T, S: (nyear, ncell, 365) air temperature and swdown. Returns per (year, cell, type) counts + monthly factor
    means, and the end state (to continue a leg)."""
    ny, nc, _ = T.shape
    if state is None:
        f = {k: np.ones((nc, NT)) for k in ("tmin", "tmax", "light")}
        aphen = np.zeros((nc, NT))
        latched = np.zeros((nc, NT), bool)
    else:
        f, aphen, latched = state
    out = {k: np.zeros((ny, nc, NT), np.int16) for k in ("n_drops", "first_drop", "drip_days", "n_release")}
    out["latched_end"] = np.zeros((ny, nc, NT), bool)
    mon = {k: np.zeros((ny, 12, nc, NT), np.float32) for k in ("tmin", "tmax", "light")}
    mb = np.cumsum([0] + list(cl.DPM))
    amin = P["aphen_min"][None, :]
    for iy in range(ny):
        out["first_drop"][iy] = -1
        for d in range(365):
            day = d + 1
            t = T[iy, :, d][:, None]
            s = S[iy, :, d][:, None]
            pt, px, pl_ = P["tmin"], P["tmax"], P["light"]
            f["tmin"] += (logistic(pt["slope"] * (t - pt["base"])) - f["tmin"]) * pt["tau"]
            f["tmin"] = np.maximum(EPS, f["tmin"])
            f["tmax"] += (logistic(-px["slope"] * (t - px["base"])) - f["tmax"]) * px["tau"]
            f["tmax"] = np.maximum(EPS, f["tmax"])
            arg = -pl_["slope"] * (s - pl_["base"])
            f["light"] = np.where(arg < 200, f["light"] + (logistic(-arg) - f["light"]) * pl_["tau"],
                                  f["light"] - f["light"] * pl_["tau"])
            f["light"] = np.maximum(EPS, f["light"])
            phen = f["tmin"] * f["tmax"] * f["light"]
            rel = (phen > 0.25) & latched & (aphen > amin)
            latched = latched & ~rel
            out["n_release"][iy] += rel
            drop = (phen < 0.25) & (aphen > amin) & ~latched
            out["n_drops"][iy] += drop
            fd = out["first_drop"][iy]
            out["first_drop"][iy] = np.where(drop & (fd < 0), day, fd)
            out["drip_days"][iy] += ~latched & ~drop
            latched = latched | drop
            phen = np.where(drop, 0.0, phen)
            aphen = np.where(drop, 0.0, aphen)
            if day == COLDEST_DAY:
                aphen[:] = 0.0
                latched[:] = False
            aphen = aphen + phen
            m = np.searchsorted(mb, d, side="right") - 1
            for k in mon:
                mon[k][iy, m] += f[k] / cl.DPM[m]
        out["latched_end"][iy] = latched
    return out, mon, (f, aphen, latched)


def read_leg(gcm, leg, cells, y_from, y_to):
    fy, ny = cl.LEG_YEARS[leg]
    arrs = {}
    for v in ("temp", "swdown"):
        mm, firstyear, ncell, nbands, scalar = cl.open_clm(cl.forcing_path(gcm, leg, v))
        assert firstyear == fy and ncell == cl.NCELL and nbands == 365, (gcm, leg, v)
        arrs[v] = np.stack([np.asarray(mm[y - fy], dtype=np.float64)[cells] * scalar
                            for y in range(y_from, y_to + 1)])
    return arrs["temp"], arrs["swdown"]


def to_frame(out, mon, gcm, traj, cells, years):
    ny, nc = len(years), len(cells)
    idx = dict(gcm=[gcm] * (ny * nc * NT), traj=[traj] * (ny * nc * NT),
               Cell=np.repeat(np.tile(cells, ny), NT).astype(np.int16),
               Year=np.repeat(years, nc * NT).astype(np.int16),
               Type=np.tile(np.arange(NT), ny * nc).astype(np.int8))
    cols = {k: v.reshape(-1) for k, v in out.items()}
    for k, a in mon.items():
        for m in range(12):
            cols[f"f_{k}_m{m + 1:02d}"] = a[:, m].reshape(-1)
    return pl.DataFrame({**idx, **cols})


def stage_sim():
    t0 = time.time()
    P = pft_params()
    cells = np.arange(0, cl.NCELL, 10)
    cells = cells[np.isin(cells, pl.read_parquet(gi.AGG)["Cell"].unique().to_numpy())]
    parts = []
    for gcm in cl.GCMS:
        T, S = read_leg(gcm, "Historical", cells, SIM0, 2014)
        yrs = np.arange(SIM0, 2015)
        out, mon, st = simulate(T, S, P, yrs)
        keep = yrs >= 1985
        parts.append(to_frame({k: v[keep] for k, v in out.items()}, {k: v[keep] for k, v in mon.items()},
                               gcm, "Historical", cells, yrs[keep]))
        print(f"{gcm} Historical simulated ({time.time() - t0:.0f}s)", flush=True)
        for leg in cl.SSPS:
            T, S = read_leg(gcm, leg, cells, 2015, 2044)
            st_leg = tuple(x.copy() for x in (dict((k, v.copy()) for k, v in st[0].items()), st[1], st[2]))
            o2, m2, _ = simulate(T, S, P, np.arange(2015, 2045), state=st_leg)
            parts.append(to_frame(o2, m2, gcm, leg, cells, np.arange(2015, 2045)))
            print(f"{gcm} {leg} simulated ({time.time() - t0:.0f}s)", flush=True)
    D = pl.concat(parts)
    D.write_parquet(OUTP)
    print("wrote", OUTP, D.height)
    S = D.group_by("gcm", "Type").agg(pl.col("n_drops").mean(), (pl.col("n_drops") >= 2).mean().alias("ge2"),
                                      pl.col("latched_end").mean(), pl.col("first_drop").median(),
                                      pl.col("drip_days").mean()).sort("gcm", "Type")
    print(S)


def stage_gate():
    """Monthly mean factor vs the C's per-PFT monthly phenology outputs (one historical member per GCM, seed 1)."""
    import netCDF4

    D = pl.read_parquet(OUTP).filter(pl.col("traj") == "Historical")
    cm = pl.read_parquet(os.path.join(XDE, "shared", "gap", "cellmap.parquet"))
    rows = []
    for gcm in cl.GCMS:
        base = os.path.join(cl.RUNS, gcm, "Historical", "random_seed_1", "output")
        Dg = D.filter(pl.col("gcm") == gcm)
        cells = np.sort(Dg["Cell"].unique().to_numpy())
        cmc = cm.filter(pl.col("Cell").is_in(cells)).sort("Cell")
        iy, ix = cmc["ilat"].to_numpy(), cmc["ilon"].to_numpy()
        for k in ("tmin", "tmax", "light"):
            p = os.path.join(base, f"mphen_pft_{k}_.nc")
            with netCDF4.Dataset(p) as ds:
                v = [x for x in ds.variables if x.startswith("phen_")]
                a = np.ma.filled(ds[v[0]][:].astype(np.float64), np.nan)
            # (time, pft, lat, lon) expected
            a = a[:, :, iy, ix] if a.ndim == 4 else None
            assert a is not None, (p, "unexpected dims")
            for t in range(NT):
                c = a[:, t, :].reshape(30, 12, len(cells))
                e = (Dg.filter(pl.col("Type") == t).sort("Year", "Cell")
                     .select([f"f_{k}_m{m:02d}" for m in range(1, 13)]).to_numpy().reshape(30, len(cells), 12)
                     .transpose(0, 2, 1))
                ok = np.isfinite(c) & (c > 0)
                if ok.sum() == 0:
                    rows.append(dict(gcm=gcm, factor=k, Type=t, n=0))
                    continue
                d = e[ok] - c[ok]
                rows.append(dict(gcm=gcm, factor=k, Type=t, n=int(ok.sum()), mean_c=float(c[ok].mean()),
                                 mean_e=float(e[ok].mean()), max_abs=float(np.abs(d).max()),
                                 p99_abs=float(np.quantile(np.abs(d), 0.99)),
                                 corr=float(np.corrcoef(e[ok], c[ok])[0, 1])))
    R = pl.DataFrame(rows)
    R.write_csv(GATEP)
    pl.Config.set_tbl_rows(100)
    print(R.with_columns(pl.col(pl.Float64).round(5)))


def stage_test():
    import lightgbm as lgb

    t0 = time.time()
    L = pl.read_parquet(OUTP).select("gcm", "traj", "Cell", "Year", "Type", "n_drops", "first_drop", "latched_end",
                                     "drip_days", "n_release")
    # per (member, Cell, y, Type) negative-growth share from the trans table
    parts = []
    for mem in gi.clean_members():
        fs = sorted(glob.glob(os.path.join(XDE, "shared", "trans", "dev", mem, "cb=dev", "y*.parquet")))
        parts.append(pl.concat([pl.scan_parquet(f).select("gcm", "traj", "seed", "Year", "Cell", "Type", "Longevity",
                                                          "c_y", "c_y1", "fate_y1") for f in fs])
                     .filter((pl.col("Type") <= 6) & (pl.col("fate_y1") < 2))
                     .group_by("gcm", "traj", "seed", "Cell", "Year", "Type")
                     .agg(n=pl.len(), neg=(pl.col("c_y1") >= 1).cast(pl.Float64).mean(),
                          lon=pl.col("Longevity").cast(pl.Float64).mean())
                     .collect(engine="streaming"))
    N = pl.concat(parts, how="vertical_relaxed").with_columns(y1=(pl.col("Year") + 1).cast(pl.Int16))
    assert N.select("gcm", "traj", "seed", "Cell", "Year", "Type").n_unique() == N.height
    # the latch of print year y1 (the transition y -> y1 is decided by y1's turnover); Historical for y1 <= 2014
    N = N.with_columns(ltraj=pl.when(pl.col("y1") <= 2014).then(pl.lit("Historical")).otherwise(pl.col("traj")),
                       Cell=pl.col("Cell").cast(pl.Int16), Type=pl.col("Type").cast(pl.Int8))
    N = N.join(L.rename({"traj": "ltraj", "Year": "y1"}), on=["gcm", "ltraj", "Cell", "y1", "Type"], how="left")
    assert N["n_drops"].null_count() == 0, "latch join misses"
    # expected annual leaf turnover fraction of leaf_c from the reconstructed latch
    N = N.with_columns(F=pl.when(pl.col("latched_end")).then(1 / 1.05).otherwise(
        pl.col("n_drops") / 1.05 + pl.col("drip_days") / 365.0 / pl.max_horizontal(pl.col("lon"), pl.lit(1.05))))
    c2 = gi.cells200()
    rows = []
    for (gcm, traj, seed, t), g in N.filter(pl.col("Cell").is_in(c2)).group_by("gcm", "traj", "seed", "Type"):
        if g["n"].sum() < 20000:
            continue
        w = pl.col("n").cast(pl.Float64)
        Y = g.group_by("y1").agg(((pl.col("neg") * w).sum() / w.sum()).alias("neg"),
                                 ((pl.col("F") * w).sum() / w.sum()).alias("F"),
                                 ((pl.col("n_drops").cast(pl.Float64) * w).sum() / w.sum()).alias("drops"),
                                 ((pl.col("latched_end").cast(pl.Float64) * w).sum() / w.sum()).alias("latched"))
        r = {c: float(np.corrcoef(Y["neg"], Y[c])[0, 1]) if Y[c].std() > 0 else float("nan")
             for c in ("F", "drops", "latched")}
        rows.append(dict(gcm=gcm, traj=traj, seed=seed, Type=t, trees=int(g["n"].sum()),
                         neg=float(Y["neg"].mean()), F=float(Y["F"].mean()), drops=float(Y["drops"].mean()),
                         **{f"corr_{k}": v for k, v in r.items()}))
    R = pl.DataFrame(rows).sort("Type", "gcm", "traj", "seed")
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(220)
    print("per-PFT yearly corr of the neg share with the reconstructed latch (200 cells):")
    print(R.filter(pl.col("seed") == 1).with_columns(pl.col(pl.Float64).round(3)))
    R.write_csv(os.path.join(gi.EVAL, "phenlatch_yearly.csv"))
    # cell-level latch features (tree-weighted over PFTs) added to gsign_info set B
    Cf = (N.group_by("gcm", "traj", "seed", "Cell", "Year")
          .agg(*[((pl.col(c).cast(pl.Float64) * pl.col("n")).sum() / pl.col("n").sum()).alias(f"L_{c}")
                 for c in ("F", "n_drops", "latched_end", "drip_days")]))
    A = pl.read_parquet(gi.AGG)
    X, sets = gi.features(A)
    X = X.join(Cf.with_columns(pl.col("seed").cast(pl.Int8), pl.col("Year").cast(pl.Int16)),
               on=["gcm", "traj", "seed", "Cell", "Year"], how="left")
    lc = ["L_F", "L_n_drops", "L_latched_end", "L_drip_days"]
    assert X["L_F"].null_count() == 0
    sets = {"B": sets["B"], "BL": sets["B"] + lc, "AL": sets["A"] + lc}
    X = X.with_columns(grp=pl.concat_str([pl.col("clim_scen_y1"), pl.col("clim_year_y1").cast(pl.Utf8)])
                       .map_elements(lambda s: zlib.crc32(s.encode()) % gi.NGRP, return_dtype=pl.Int64))
    is_train = (pl.col("gcm") == "MPI-ESM1-2-HR") & (pl.col("seed") == 1) & pl.col("traj").is_in(
        ["Historical", "ssp126", "ssp370"])
    TR = X.filter(is_train)
    Pm = dict(objective="regression", learning_rate=0.03, num_leaves=31, min_data_in_leaf=100, feature_fraction=0.7,
              bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1,
              num_threads=int(os.environ.get("OMP_NUM_THREADS", "8")), seed=7)
    res = []
    for t in gi.TARGETS:
        wcol = {"neg": "n", "start": "n0", "cont1": "n1"}[t]
        T_ = TR.filter(pl.col(t).is_not_null() & (pl.col(wcol) > 0))
        y, w, g = T_[t].to_numpy(), T_[wcol].to_numpy().astype(float), T_["grp"].to_numpy()
        H = X.filter(~is_train & pl.col(t).is_not_null() & (pl.col(wcol) > 0) & (pl.col("seed") == 1))
        for sname, cols in sets.items():
            Xt = T_.select(cols).to_numpy().astype(np.float32)
            best = []
            for k in range(gi.NGRP):
                te, es = g == k, g == (k + 1) % gi.NGRP
                trn = ~(te | es)
                b = lgb.train(Pm, lgb.Dataset(Xt[trn], y[trn], weight=w[trn]), num_boost_round=3000,
                              valid_sets=[lgb.Dataset(Xt[es], y[es], weight=w[es])],
                              callbacks=[lgb.early_stopping(50, verbose=False)])
                best.append(b.best_iteration)
            bf = lgb.train(Pm, lgb.Dataset(Xt, y, weight=w), num_boost_round=int(np.median(best)))
            Hp = H.with_columns(pl.Series("p", bf.predict(H.select(cols).to_numpy().astype(np.float32))))
            for (gcm, traj), grp in Hp.group_by("gcm", "traj"):
                r = gi.ycorr(grp.filter(pl.col("Cell").is_in(c2)), t, "p", wcol)
                res.append(dict(target=t, set=sname, gcm=gcm, traj=traj, **r))
            print(f"{t} {sname}: {best}  ({time.time() - t0:.0f}s)", flush=True)
    R2 = pl.DataFrame(res)
    R2.write_csv(os.path.join(gi.EVAL, "phenlatch_fit.csv"))
    for t in gi.TARGETS:
        print(t)
        print(R2.filter(pl.col("target") == t).with_columns(k=pl.concat_str([pl.col("gcm").str.slice(0, 3),
                                                                              pl.lit("_"), pl.col("traj")]))
              .pivot(on="set", index="k", values=["corr", "slope"]).sort("k").with_columns(pl.col(pl.Float64).round(3)))


def main():
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    if st in ("sim", "all"):
        stage_sim()
    if st in ("gate", "all"):
        stage_gate()
    if st in ("test", "all"):
        stage_test()


if __name__ == "__main__":
    main()
