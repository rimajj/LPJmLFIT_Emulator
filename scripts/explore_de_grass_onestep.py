#!/usr/bin/env python3
"""explore_de_grass_onestep.py — LINE X, Germany emulator: is grass2's too-slow grass decline under a closed canopy
a per-step mean error or long-horizon accumulation? (pre-registration: /p/tmp/jamirp/X_de/_status/GA.md)

On the ORIGINAL's trees and grass (no emulator involved), for every state year y: the truth L_{y+1}; grass2 one step
ahead from the true grass state, mean only and with one residual draw (the coupled run's u stream, e0 = 0); and a
K-step chain started from the truth at y-K+1 (AR residual carried, as in the free run). Strata by next-year printed
tree cover. Then the one-step log residual (true dz - predicted mean dz) in closed patches against candidate missing
inputs: implied hidden cover h_y where the cover cap binds, stand biomass, recent cover loss.
Writes shared/eval/grass_onestep_<gcm>_s<seed>_<leg>_c<N>.csv (+ _resid.csv)."""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_engine as eng  # noqa: E402
import explore_de_grass2 as g2  # noqa: E402
import explore_de_grass_attrib as ga  # noqa: E402

WINDOWS = ga.WINDOWS


def strata(t1):
    return {"closed": t1 >= 0.45, "mid": (t1 >= 0.3) & (t1 < 0.45), "open": t1 < 0.3, "all": np.ones(len(t1), bool)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gcm", default="ACCESS-CM2")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--run", default="_tabg2_ar")  # only for its cell list
    ap.add_argument("--chunks", default="0,1")
    ap.add_argument("--k", type=int, default=5)
    a = ap.parse_args()
    rd = ga.run_dir(a.run, "ACCESS-CM2", 1, "ssp370")  # the coupled run only supplies the cell list
    cells = sorted(sum((json.load(open(os.path.join(rd, f"meta_{int(c):03d}.json")))["cells"]
                        for c in a.chunks.split(",")), []))
    B = g2.original_series(a.gcm, a.seed, a.leg, cells)
    years = sorted(B["Year"].unique().to_list())
    byY = {y: g for (y,), g in B.partition_by("Year", as_dict=True, maintain_order=True).items()}
    G = g2.Grass2("DEV-A", kappa=1.0)
    rand = eng.Rand("tabAL", 1, a.gcm)
    tabs = [np.sort(t) for t in G.tabs]
    K = G.C["K"]

    def draw(z1, y, X):
        u = rand.uniform("g2_grass", y, X["Cell"].to_numpy(), X["Patch"].to_numpy())
        b = np.searchsorted(G.edges, z1)
        r = np.empty_like(z1)
        for i in range(10):
            m = b == i
            if m.any():
                r[m] = tabs[i][np.minimum((u[m] * len(tabs[i])).astype(np.int64), len(tabs[i]) - 1)]
        return r

    def lai(z1):
        z1 = np.clip(z1, np.log(g2.EPS), np.log(G.C["LAI_max"] * 1.2 + g2.EPS))
        return np.maximum(np.exp(z1) - g2.EPS, 0.0)

    rows, res = [], []
    for y in years:
        X = g2.add_g2(byY[y])
        z = X["z_y"].to_numpy()
        mu = G.mean_dz(X)
        Lm = lai(z + mu)
        Ld = lai(z + mu + draw(z + mu, y, X))
        Lt = X["g_LAI_y1"].cast(pl.Float64).to_numpy()
        zt = np.log(Lt + g2.EPS)
        t1 = X["sum_fpc_y1"].cast(pl.Float64).to_numpy()
        # K-step chain from the truth at y-K+1 (AR carried), ending at the same y+1
        Lk = None
        if y - a.k + 1 >= years[0]:
            st = {"fpc": byY[y - a.k + 1][g2.GF].cast(pl.Float32).to_numpy(),
                  "LAI": byY[y - a.k + 1][g2.GL].cast(pl.Float32).to_numpy(),
                  "agb": byY[y - a.k + 1][g2.GA].cast(pl.Float32).to_numpy()}
            e = None
            for s in range(y - a.k + 1, y + 1):
                Xs = g2.add_g2(byY[s].with_columns(**{g2.GF: pl.Series(st["fpc"]), g2.GL: pl.Series(st["LAI"]),
                                                      g2.GA: pl.Series(st["agb"])}))
                zz = Xs["z_y"].to_numpy() + G.mean_dz(Xs)
                r = draw(zz, s, Xs)
                r = G.rho * (e if e is not None else 0.0) + np.sqrt(1 - G.rho ** 2) * r
                e = r
                Ls = lai(zz + r)
                f, ag = g2.closure(Ls, byY[s]["sum_fpc_y1"].cast(pl.Float64).to_numpy(), G.C)
                st = {"fpc": f.astype(np.float32), "LAI": Ls.astype(np.float32), "agb": ag.astype(np.float32)}
            Lk = st["LAI"].astype(np.float64)
        for s, m in strata(t1).items():
            if not m.any():
                continue
            rows.append({"Year": y + 1, "stratum": s, "n": int(m.sum()), "L_truth": float(Lt[m].mean()),
                         "L_mean1": float(Lm[m].mean()), "L_draw1": float(Ld[m].mean()),
                         f"L_chain{a.k}": float(Lk[m].mean()) if Lk is not None else None,
                         "z_truth": float(zt[m].mean()), "z_pred1": float((z + mu)[m].mean())})
        # residual diagnostics in closed patches
        g = X[g2.GF].cast(pl.Float64).to_numpy()
        Ly = X[g2.GL].cast(pl.Float64).to_numpy()
        t = X["sum_fpc_y"].cast(pl.Float64).to_numpy()
        capped = (1 - np.exp(-K * Ly)) - g > 1e-3
        h = np.where(capped, 1 - g - t, np.nan)
        cm = t1 >= 0.45
        res.append(pl.DataFrame({"Year": np.full(cm.sum(), y + 1, np.int16), "resid": (zt - (z + mu))[cm],
                                 "z_y": z[cm], "h_y": h[cm], "capped": capped[cm],
                                 "sum_agb_y": X["sum_agb_y"].cast(pl.Float64).to_numpy()[cm],
                                 "n_live_y": X["n_live_y"].cast(pl.Float64).to_numpy()[cm],
                                 "loss3": X.select(pl.sum_horizontal(pl.col("frac_loss_lag0", "frac_loss_lag1",
                                                                             "frac_loss_lag2").fill_null(0.0)))
                                 .to_series().to_numpy()[cm]}))
    R = pl.DataFrame(rows)
    tag = f"{a.gcm}_s{a.seed}_{a.leg}_c{len(cells)}"
    out = os.path.join(g2.EVAL, f"grass_onestep_{tag}.csv")
    R.write_csv(out)
    E = pl.concat(res)
    E.write_parquet(out.replace(".csv", "_resid.parquet"))
    pl.Config.set_tbl_rows(100)
    pl.Config.set_tbl_width_chars(220)
    W = []
    for lo, hi in WINDOWS:
        W.append(R.filter(pl.col("Year").is_between(lo, hi)).group_by("stratum").agg(
            pl.exclude("Year", "stratum", "n").mean()).with_columns(window=pl.lit(f"{lo}-{hi}")))
    W = pl.concat(W).sort("stratum", "window")
    print(W.with_columns(pl.selectors.float().round(3)))
    # residual vs candidate inputs, closed patches, by window halves
    E = E.with_columns(per=pl.when(pl.col("Year") <= 2005).then(pl.lit("1986-2005")).otherwise(pl.lit("2006-2044")))
    print("closed patches: mean log residual (true dz - predicted) by period:")
    print(E.group_by("per").agg(pl.len(), pl.col("resid").mean(), pl.col("capped").mean()).sort("per"))
    for c in ("h_y", "sum_agb_y", "loss3", "z_y"):
        D = E.filter(pl.col(c).is_not_null() & pl.col(c).is_not_nan())
        D = D.with_columns(q=pl.col(c).qcut(5, labels=[f"q{i}" for i in range(5)], allow_duplicates=True))
        print(f"resid by quintile of {c} (closed patches):")
        print(D.group_by("per", "q").agg(pl.len(), pl.col(c).mean().alias("x"), pl.col("resid").mean())
              .sort("per", "q").with_columns(pl.col("x", "resid").round(3)))
    print("wrote", out)


if __name__ == "__main__":
    main()
