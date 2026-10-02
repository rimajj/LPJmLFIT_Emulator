#!/usr/bin/env python3
"""explore_de_struct_gates.py — LINE X, Germany data-driven emulator, B-STRUCT item B2: RESPONSE GATES of the heads.

All teacher-forced (true tree state at y, true climate), on the B1 heads (explore_de_struct_heads). Split = parameter
(DEV-A default). Every number states its basis (members, cells, sample).

  g1        ACCESS-CM2 Historical seed 1 (held-out climate model), transitions 1985->1986 ... 2013->2014, all 907 dev
            cells (B1 eval rows, u_hash < 0.03): Germany-mean yearly fraction of stems with G_{y+1} < 0, truth vs the
            mean predicted P(G<0). GATE: Pearson r >= 0.8. Ceiling beside it: the same series seed 1 vs seed 2.
  partial   partial R2 of the climate block on WITHIN-CELL anomalies of the cell-year mean G (and of the fraction
            G<0): anomaly = cell-year mean minus the cell's mean over years; R2 of the predicted anomaly with the true
            climate vs with YEAR-SHUFFLED climate (each cell's (y, y+1) climate pair replaced by another year's pair of
            the same cell and trajectory; the tree state is untouched). partial = 1 - SSE_true / SSE_shuffled. The
            split-half reliability of the truth anomaly (two disjoint halves of the sampled trees) is reported as a
            sampling-noise indicator only; it is NOT a ceiling, because prediction and truth share the sampled trees
            (tree-composition noise is common to both; the shuffled control is what removes it).
  hot       the hottest 10 % of training cell-years by tmean_ann of y+1 and a random 10 % of the other cell-years
            (control) are both removed from the training sample; gclf and gall are refitted with the production
            round count; error ratio hot / control (Brier of P(G<0), MSE of G, and 1 - R2) on those held-out rows.
  response  on fold-5 cells (B1 eval rows, u_hash < 0.15): per cell-year, D = X(ssp370) - X(ssp126) for X = fraction
            G<0 / mean G, truth seed 1 vs prediction (each leg's own seed-1 state, teacher-forced), 2015-2044, and a
            CLIMATE SWAP (the same ssp126 seed-1 trees under the ssp370 climate: the learned climate response alone).
            Among the
            cell-years where |D_truth,s1| > |D_truth,s1 - D_truth,s2| (the two-seed spread), the share where the
            predicted D has the observed sign. Also Germany-scale (fold-5 mean per year) and 30-year cell means.
            Both GCMs: ACCESS-CM2 (held-out climate model) and MPI-ESM1-2-HR (training climate, held-out cells).
STAGES  g1 · partial · hot · response · report · submit
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
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_struct_heads as hd  # noqa: E402

XDE = tr.XDE
OUT = os.environ.get("B2_OUT", os.path.join(XDE, "struct", "gates"))
STATUS = os.path.join(XDE, "_status", "B2.md")
REPORTS = os.path.join(XDE, "_reports")
PY = tr.PY
LOGDIR = os.path.join(REPO, "logs")
U_PARTIAL = float(os.environ.get("B2_U_PARTIAL", "0.06"))
HOT_Q = 0.90
log = hd.log


def status(line: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


def pred(split, member) -> pl.DataFrame:
    return pl.read_parquet(os.path.join(hd.OUT, split, "pred", f"{member}.parquet"))


def save(name, obj):
    os.makedirs(OUT, exist_ok=True)
    json.dump(obj, open(os.path.join(OUT, f"{name}.json"), "w"), indent=1)


def pearson(a, b) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[m], b[m])[0, 1]) if m.sum() > 2 else float("nan")


# ------------------------------------------------------------------------------------------------ g1
def yearly_neg(d: pl.DataFrame) -> pl.DataFrame:
    return (d.filter(pl.col("gsign_t").is_not_null()).group_by("Year")
            .agg(obs=pl.col("gsign_t").mean(), pred=pl.col("p_gneg").mean(), n=pl.len()).sort("Year"))


def stage_g1(a):
    out = {"basis": "B1 eval rows u_hash < 0.03 on all 907 dev cells; truth = share of present stems with G_{y+1} < 0"}
    for m in ("ACCESS-CM2_Historical_s1_h1985", "ACCESS-CM2_Historical_s2_h1985", "ACCESS-CM2_ssp370_s1_w2015",
              "ACCESS-CM2_ssp126_s1_w2015", "MPI-ESM1-2-HR_ssp245_s2_w2015", "MPI-ESM1-2-HR_Historical_s2_h1985"):
        p = os.path.join(hd.OUT, a.split, "pred", f"{m}.parquet")
        if not os.path.exists(p):
            continue
        y = yearly_neg(pred(a.split, m).filter(pl.col("u_hash") < hd.U_EV_ALL))
        out[m] = {"r": pearson(y["obs"].to_numpy(), y["pred"].to_numpy()), "years": y["Year"].to_list(),
                  "obs": y["obs"].to_list(), "pred": y["pred"].to_list(),
                  "mean_obs": float(y["obs"].mean()), "mean_pred": float(y["pred"].mean()),
                  "sd_obs": float(y["obs"].std()), "sd_pred": float(y["pred"].std())}
    a1, a2 = out.get("ACCESS-CM2_Historical_s1_h1985"), out.get("ACCESS-CM2_Historical_s2_h1985")
    if a1 and a2:
        out["ceiling_seed1_vs_seed2_r"] = pearson(np.asarray(a1["obs"]), np.asarray(a2["obs"]))
        out["pass"] = bool(a1["r"] >= 0.8)
    save("g1", out)
    status(f"g1: ACCESS Historical s1 r = {a1['r']:.3f} (gate >= 0.8), seed ceiling "
           f"{out.get('ceiling_seed1_vs_seed2_r', float('nan')):.3f}")


# ------------------------------------------------------------------------------------------------ partial
def _anom(d: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
    cy = d.group_by("Cell", "Year").agg([pl.col(c).mean() for c in cols] + [pl.len().alias("n")])
    return cy.with_columns([(pl.col(c) - pl.col(c).mean().over("Cell")).alias(f"a_{c}") for c in cols])


def _r2a(t, p):
    return float(1 - np.sum((t - p) ** 2) / np.sum(t ** 2))


def stage_partial(a):
    H = hd.StructHeads.load(a.split)
    out = {}
    sets = [("ACCESS-CM2_Historical_s1_h1985", pl.lit(True), "all_dev"),
            ("MPI-ESM1-2-HR_Historical_s1_h1985", pl.col("fold") == hd.HOLD_FOLD, "fold5")]
    for member, cf, lab in sets:
        t0 = time.time()
        df = hd.read_member_rows(member, cf, pl.col("u_hash") < U_PARTIAL)
        df = df.filter(pl.col("g_ok")).with_row_index("_i")
        clim_cols = H.climate_columns()
        m_true = H.predict(H.X(df))
        # year-shuffled climate: per cell, a random permutation of the member's years (deterministic)
        cy = df.select(["Cell", "Year"] + clim_cols).unique(["Cell", "Year"]).sort("Cell", "Year")
        rng = np.random.default_rng(20261002)
        maps = []
        for c, g in cy.group_by("Cell", maintain_order=True):
            yrs = g["Year"].to_numpy()
            perm = yrs.copy()
            while len(yrs) > 1 and np.any(perm == yrs):   # a derangement: no year keeps its own climate
                perm = rng.permutation(yrs)
            maps.append(pl.DataFrame({"Cell": np.full(len(yrs), c[0], np.int16), "Year": yrs, "src": perm}))
        mp = pl.concat(maps).with_columns(pl.col("Year").cast(pl.Int16), pl.col("src").cast(pl.Int16))
        sh = mp.join(cy.rename({"Year": "src"}), on=["Cell", "src"], how="left").drop("src")
        base = df.drop(clim_cols + [c for c in df.columns if c.startswith("a_") or c.startswith("c8_")
                                     or c in ("tstress_y", "tstress_y1", "soil_code")])
        dfs = hd.add_features(base.join(sh, on=["Cell", "Year"], how="left")).sort("_i")
        assert dfs.height == df.height
        m_shuf = H.predict(H.X(dfs))
        d = df.select("Cell", "Year", "u_hash", pl.col("G_y1").cast(pl.Float64).alias("G"),
                      (pl.col("G_y1") < 0).cast(pl.Float64).alias("neg")).with_columns(
            pt=pl.Series(m_true["mu_gall"]), ps=pl.Series(m_shuf["mu_gall"]),
            qt=pl.Series(m_true["p_gneg"]), qs=pl.Series(m_shuf["p_gneg"]))
        A = _anom(d, ["G", "neg", "pt", "ps", "qt", "qs"])
        half = [(_anom(d.filter((pl.col("u_hash") * 1e6).cast(pl.Int64) % 2 == k), ["G", "neg"])) for k in (0, 1)]
        hh = half[0].join(half[1], on=["Cell", "Year"], suffix="_2")
        res = {"member": member, "cells": lab, "rows": d.height, "cell_years": A.height,
               "trees_per_cell_year_median": float(A["n"].median())}
        for tgt, pt_, ps_ in (("G", "pt", "ps"), ("neg", "qt", "qs")):
            t = A[f"a_{tgt}"].to_numpy()
            r_t, r_s = _r2a(t, A[f"a_{pt_}"].to_numpy()), _r2a(t, A[f"a_{ps_}"].to_numpy())
            sse_t = np.sum((t - A[f"a_{pt_}"].to_numpy()) ** 2)
            sse_s = np.sum((t - A[f"a_{ps_}"].to_numpy()) ** 2)
            rel = pearson(hh[f"a_{tgt}"].to_numpy(), hh[f"a_{tgt}_2"].to_numpy())
            res[tgt] = {"r2_true_climate": r_t, "r2_shuffled_climate": r_s, "partial_r2_climate": float(
                1 - sse_t / sse_s), "split_half_reliability_truth": rel, "var_anomaly": float(np.var(t))}
        out[f"{member}|{lab}"] = res
        log(f"partial {member} {lab}: {json.dumps({k: res[k] for k in ('G', 'neg')})} ({time.time() - t0:.0f} s)")
    save("partial", out)
    status("partial: " + "; ".join(f"{k}: G partial {v['G']['partial_r2_climate']:.3f} "
                                   f"(true {v['G']['r2_true_climate']:.3f} / shuffled "
                                   f"{v['G']['r2_shuffled_climate']:.3f})" for k, v in out.items()))


# ------------------------------------------------------------------------------------------------ hot
def stage_hot(a):
    df = hd.load_sample(a.split)
    cyk = df.select("member", "Cell", "Year", "tmean_ann_y1").unique(["member", "Cell", "Year"])
    thr = float(cyk["tmean_ann_y1"].quantile(HOT_Q))
    rng = np.random.default_rng(11)
    cyk = cyk.with_columns(hot=pl.col("tmean_ann_y1") > thr, r=pl.Series(rng.random(cyk.height)))
    cyk = cyk.with_columns(ctrl=(~pl.col("hot")) & (pl.col("r") < 0.1 / HOT_Q))
    df = df.join(cyk.select("member", "Cell", "Year", "hot", "ctrl"), on=["member", "Cell", "Year"], how="left")
    hot, ctrl = df["hot"].to_numpy(), df["ctrl"].to_numpy()
    out = {"basis": f"DEV-A training sample (MPI s1 Historical/ssp126/ssp370, folds 1-4, u_hash < {hd.U_BASE}); "
                    f"hot = tmean_ann(y+1) > {thr:.3f} C (90th percentile of training cell-years); control = random "
                    "10 % of the other cell-years; both removed from training, models refitted at the production "
                    "round count", "threshold_tmean": thr,
           "hot_cell_years": int(cyk["hot"].sum()), "ctrl_cell_years": int(cyk["ctrl"].sum())}
    for head in ("gclf", "gall"):
        info = json.load(open(os.path.join(hd.OUT, a.split, "models", f"{head}.json")))
        names = hd.feature_names(False)
        rows = hd.head_rows(df, head)
        y = df[hd.HEAD_TARGET[head]].to_numpy().astype(np.float64)
        X = hd.matrix(df, names)
        trm = rows & ~hot & ~ctrl
        t0 = time.time()
        b = hd.fit_one(X[trm], y[trm], None, None, head, names, rounds=info["rounds"])
        res = {"train_rows": int(trm.sum())}
        for lab, m in (("hot", rows & hot), ("ctrl", rows & ctrl)):
            p = b.predict(X[m])
            mse = float(np.mean((p - y[m]) ** 2))
            res[lab] = {"n": int(m.sum()), "mse": mse, "r2": float(1 - mse / np.var(y[m])), "bias": float(
                np.mean(p - y[m])), "mean_obs": float(np.mean(y[m]))}
        res["mse_ratio_hot_over_ctrl"] = res["hot"]["mse"] / res["ctrl"]["mse"]
        res["one_minus_r2_ratio"] = (1 - res["hot"]["r2"]) / (1 - res["ctrl"]["r2"])
        out[head] = res
        log(f"hot {head}: {json.dumps(res)} ({time.time() - t0:.0f} s)")
    save("hot", out)
    status(f"hot: thr {thr:.2f} C; gclf Brier ratio {out['gclf']['mse_ratio_hot_over_ctrl']:.2f}, gall MSE ratio "
           f"{out['gall']['mse_ratio_hot_over_ctrl']:.2f}")


# ------------------------------------------------------------------------------------------------ response
def _cy(d: pl.DataFrame) -> pl.DataFrame:
    return (d.group_by("Cell", "Year").agg(
        neg=pl.col("gsign_t").mean(), p=pl.col("p_gneg").filter(pl.col("gsign_t").is_not_null()).mean(),
        G=pl.col("G_y1").filter(pl.col("g_ok")).cast(pl.Float64).mean(),
        mG=pl.col("mu_gall").filter(pl.col("g_ok")).mean(), n=pl.len()))


def stage_response(a):
    out = {"basis": "fold-5 dev cells (185 cells, 11 blocks), B1 eval rows u_hash < 0.15; transitions y -> y+1 with "
                    "y+1 in 2015-2044; teacher-forced on each scenario leg's own seed-1 state"}
    for gcm in ("ACCESS-CM2", "MPI-ESM1-2-HR"):
        legs = {}
        for scen in ("ssp126", "ssp370"):
            for s in (1, 2):
                m = f"{gcm}_{scen}_s{s}_w2015"
                d = pred(a.split, m).filter((pl.col("fold") == hd.HOLD_FOLD) & (pl.col("u_hash") < hd.U_EV_F5))
                legs[(scen, s)] = _cy(d)
        k = ["Cell", "Year"]
        J = (legs[("ssp370", 1)].join(legs[("ssp126", 1)], on=k, suffix="_126")
             .join(legs[("ssp370", 2)].select(k + ["neg", "G"]), on=k, suffix="_370s2")
             .join(legs[("ssp126", 2)].select(k + ["neg", "G"]), on=k, suffix="_126s2"))
        res = {"cell_years": J.height}
        # climate swap: the SAME ssp126 seed-1 trees under the ssp370 climate (isolates the learned climate response)
        H = hd.StructHeads.load(a.split)
        sw = {}
        for ct in ("ssp126", "ssp370"):
            ds = hd.read_member_rows(f"{gcm}_ssp126_s1_w2015", pl.col("fold") == hd.HOLD_FOLD,
                                     pl.col("u_hash") < hd.U_EV_F5, clim_traj=ct)
            mm = H.predict(H.X(ds))
            sw[ct] = _cy(ds.with_columns(p_gneg=pl.Series(mm["p_gneg"]), mu_gall=pl.Series(mm["mu_gall"])))
        S = sw["ssp370"].join(sw["ssp126"], on=k, suffix="_126").select(
            k + [(pl.col("p") - pl.col("p_126")).alias("dsw_neg"), (pl.col("mG") - pl.col("mG_126")).alias("dsw_G")])
        J = J.join(S, on=k, how="left")
        for X, P_ in (("neg", "p"), ("G", "mG")):
            d1 = (J[X] - J[f"{X}_126"]).to_numpy()
            d2 = (J[f"{X}_370s2"] - J[f"{X}_126s2"]).to_numpy()
            dp = (J[P_] - J[f"{P_}_126"]).to_numpy()
            spread = np.abs(d1 - d2)
            det = np.abs(d1) > spread
            agree = np.sign(dp) == np.sign(d1)
            r = {"determined_share": float(det.mean()), "n_determined": int(det.sum()),
                 "sign_agree_determined": float(agree[det].mean()) if det.any() else None,
                 "sign_agree_all": float(agree[np.abs(d1) > 0].mean()), "corr_pred_obs_all": pearson(dp, d1),
                 "corr_obs_seed1_seed2": pearson(d1, d2), "mean_obs_D": float(np.nanmean(d1)),
                 "mean_pred_D": float(np.nanmean(dp))}
            # Germany-scale (fold-5 mean per year) and per-cell 30-yr means
            Jy = J.with_columns(d1=pl.Series(d1), d2=pl.Series(d2), dp=pl.Series(dp))
            gy = Jy.group_by("Year").agg(pl.col("d1", "d2", "dp").mean()).sort("Year")
            dety = np.abs(gy["d1"].to_numpy()) > np.abs(gy["d1"].to_numpy() - gy["d2"].to_numpy())
            agy = np.sign(gy["dp"].to_numpy()) == np.sign(gy["d1"].to_numpy())
            r["germany_yearly"] = {"years": int(gy.height), "determined": int(dety.sum()),
                                   "sign_agree_determined": float(agy[dety].mean()) if dety.any() else None,
                                   "corr_pred_obs": pearson(gy["dp"].to_numpy(), gy["d1"].to_numpy()),
                                   "corr_seed1_seed2": pearson(gy["d1"].to_numpy(), gy["d2"].to_numpy())}
            gc = Jy.group_by("Cell").agg(pl.col("d1", "d2", "dp").mean())
            detc = np.abs(gc["d1"].to_numpy()) > np.abs(gc["d1"].to_numpy() - gc["d2"].to_numpy())
            agc = np.sign(gc["dp"].to_numpy()) == np.sign(gc["d1"].to_numpy())
            r["cell_30yr"] = {"cells": int(gc.height), "determined": int(detc.sum()),
                              "sign_agree_determined": float(agc[detc].mean()) if detc.any() else None,
                              "corr_pred_obs": pearson(gc["dp"].to_numpy(), gc["d1"].to_numpy())}
            dsw = J[f"dsw_{X}"].to_numpy()
            agsw = np.sign(dsw) == np.sign(d1)
            r["climate_swap"] = {"what": "same ssp126 seed-1 trees, ssp370 minus ssp126 climate",
                                 "sign_agree_determined": float(agsw[det].mean()) if det.any() else None,
                                 "corr_with_obs_all": pearson(dsw, d1), "mean_D": float(np.nanmean(dsw)),
                                 "share_of_pred_D_variance": float(np.nanvar(dsw) / np.nanvar(dp))}
            res[X] = r
        out[gcm] = res
        log(f"response {gcm}: {json.dumps(res)}")
    save("response", out)
    status("response: " + "; ".join(
        f"{g}: P(G<0) sign {v['neg']['sign_agree_determined']} on {v['neg']['n_determined']} determined cell-years, "
        f"mean G sign {v['G']['sign_agree_determined']} on {v['G']['n_determined']}" for g, v in out.items()
        if isinstance(v, dict) and "neg" in v))


def stage_report(a):
    rep = {"item": "B2", "split": a.split}
    for n in ("g1", "partial", "hot", "response"):
        p = os.path.join(OUT, f"{n}.json")
        rep[n] = json.load(open(p)) if os.path.exists(p) else None
    os.makedirs(REPORTS, exist_ok=True)
    json.dump(rep, open(os.path.join(REPORTS, "r2_B2.json"), "w"), indent=1)
    status("report -> _reports/r2_B2.json")


def stage_submit(a):
    me = os.path.abspath(__file__)
    jd = os.path.join(XDE, "_jobs")
    os.makedirs(jd, exist_ok=True)
    jids = []
    for st, cpus, tm in (("g1", 4, "00:30:00"), ("partial", 16, "02:00:00"), ("hot", 16, "04:00:00"),
                         ("response", 4, "00:30:00")):
        p = os.path.join(jd, f"X-de-B2-{st}.jcf")
        lines = ["#!/bin/bash", f"#SBATCH --job-name=X-de-B2-{st}", "#SBATCH --account=waldspektrum",
                 "#SBATCH --partition=standard", "#SBATCH --qos=short", f"#SBATCH --cpus-per-task={cpus}",
                 f"#SBATCH --time={tm}", f"#SBATCH --output={LOGDIR}/X-de-B2-{st}.%j.out"]
        if a.dep:
            lines.append(f"#SBATCH --dependency={a.dep}")
        lines += ["set -eu", f"cd {REPO}", "export PYTHONUNBUFFERED=1", f"{PY} {me} {st} --split {a.split}"]
        open(p, "w").write("\n".join(lines) + "\n")
        jids.append(subprocess.run(["sbatch", "--parsable", p], capture_output=True, text=True,
                                   check=True).stdout.strip())
    p = os.path.join(jd, "X-de-B2-report.jcf")
    open(p, "w").write("\n".join(["#!/bin/bash", "#SBATCH --job-name=X-de-B2-report", "#SBATCH --account=waldspektrum",
                                  "#SBATCH --partition=standard", "#SBATCH --qos=short", "#SBATCH --cpus-per-task=1",
                                  "#SBATCH --time=00:10:00", f"#SBATCH --dependency=afterany:{':'.join(jids)}",
                                  f"#SBATCH --output={LOGDIR}/X-de-B2-report.%j.out", "set -eu", f"cd {REPO}",
                                  f"{PY} {me} report --split {a.split}"]) + "\n")
    jr = subprocess.run(["sbatch", "--parsable", p], capture_output=True, text=True, check=True).stdout.strip()
    status(f"submitted g1/partial/hot/response {jids} + report {jr}" + (f" (dep {a.dep})" if a.dep else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["g1", "partial", "hot", "response", "report", "submit"])
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--dep", default=None)
    a = ap.parse_args(argv)
    {"g1": stage_g1, "partial": stage_partial, "hot": stage_hot, "response": stage_response, "report": stage_report,
     "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
