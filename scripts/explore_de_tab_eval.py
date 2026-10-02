#!/usr/bin/env python3
"""explore_de_tab_eval.py — LINE X, Germany emulator, design track A-TAB: held-out gates and reports for the heads of
explore_de_tab_heads.py (items A2-A5), the A2 between-scenario CONTRAST gate, the A5 recruit-trait sampler fit
(KS) and its gates, and an API smoke/timing test on a real initial state. Called through
`explore_de_tab_heads.py eval --item A2|A3|A4|A5 | contrast | traits | apitest`.

All held-out numbers are on UNWEIGHTED rows (A1 eval samples: u_hash < 0.02 of every tree row of the held-out
member/cells, or full tables where stated). kappa = 1 is the full model, kappa = 0 the climate-blind arm.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_heads as Hh  # noqa: E402

SETS = ["F5", "GCM", "SCEN", "SEED2"]
EPS = 1e-6
SMOKE = Hh.SMOKE  # TAB_SMOKE=1: code-path check on tiny slices, written to *_smoke reports


def r2(y, p):
    y = np.asarray(y, np.float64)
    p = np.asarray(p, np.float64)
    m = np.isfinite(y) & np.isfinite(p)
    y, p = y[m], p[m]
    return float(1 - np.mean((y - p) ** 2) / np.var(y)) if len(y) > 1 else float("nan")


def logloss(y, p):
    p = np.clip(np.asarray(p, np.float64), EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    try:
        return float(roc_auc_score(y, p))
    except ValueError:
        return float("nan")


def calib(df: pl.DataFrame, by: str, pcol: str, ycol: str, n_min=50):
    g = df.group_by(by).agg(n=pl.len(), pred=pl.col(pcol).cast(pl.Float64).mean(),
                            obs=pl.col(ycol).cast(pl.Float64).mean()).filter(pl.col("n") >= n_min).sort(by)
    return [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()} for r in g.to_dicts()]


def deciles(x, nd=10):
    e = np.quantile(x, np.linspace(0, 1, nd + 1)[1:-1])
    return np.searchsorted(e, x)


def L(df):
    return df.head(40000) if SMOKE else df


def keep_cols(H, names):
    c = []
    for n in names:
        if n in H.m:
            c += H.m[n][2]["features_B0"] + H.m[n][2]["features_B1"]
    return [x for x in dict.fromkeys(c) if x not in ("h_phys", "G_y1", "c_y1", "dlog_agb_y1", "dlog_vegc_y1")]


TGT_KEEP = ["G_y1", "c_y1", "agb_y1", "vegc_y1", "LAI_y1", "fpc_ind_y1", "D95_y1", "Height_y1", "mort_y1",
            "mort_npp_y1", "fate_y1", "cenG_y1", "is_recruit_y", "bin_feb2026_y1"]


def rpt(item, out):
    p = os.path.join(Hh.REPORTS, f"r2_{item}{'_smoke' if SMOKE else ''}.json")
    old = json.load(open(p)) if os.path.exists(p) else {}
    old.update(out)
    json.dump(old, open(p, "w"), indent=1, default=float)
    return p


# ================================================================================================ A2
def eval_A2(split):
    H = Hh.TabHeads.load(split, heads=["gsign", "gmag_neg", "gmag_pos", "dagb", "surv"])
    # persistence-of-sign null: training rates P(G_{y+1} < 0 | sign(G_y), c_y, Type), inverse-probability weighted
    trn = pl.scan_parquet(Hh.sample_files(split, "train")).filter(
        (pl.col("fate_y1") <= 1) & (pl.col("cenG_y1") != 3) & (pl.col("fold") != -1)).group_by(
        (pl.col("G_y") < 0).alias("gneg_y"), "c_y", "Type").agg(
        p_null=((pl.col("G_y1") < 0).cast(pl.Float64) * pl.col("w_ip")).sum() / pl.col("w_ip").sum()).collect()
    keep = keep_cols(H, ["gsign", "gmag_neg", "gmag_pos"]) + TGT_KEEP
    out = {"basis": "unweighted held-out rows (u_hash < 0.02); present stems with known G sign",
           "null": "P_train(G_{y+1}<0 | sign G_y, c_y, Type)", "sets": {}}
    rng = np.random.default_rng(20261002)
    for s in SETS:
        df = L(Hh.load_rows(split, s, (pl.col("fate_y1") <= 1) & (pl.col("cenG_y1") != 3), keep=keep))
        df = df.with_columns((pl.col("G_y") < 0).alias("gneg_y")).join(trn, on=["gneg_y", "c_y", "Type"],
                                                                        how="left")
        y = (df["G_y1"].to_numpy() < 0).astype(np.float64)
        p1 = H.p_gneg(df, 1.0)
        p0 = H.p_gneg(df, 0.0)
        pn = df["p_null"].fill_null(float(y.mean())).to_numpy()
        df = df.with_columns(p1=pl.Series(p1), p0=pl.Series(p0), yneg=pl.Series(y),
                             dec=pl.Series(deciles(p1)), Y1=(pl.col("Year") + 1))
        o = {"n": df.height, "obs_rate": float(y.mean()), "pred_rate_k1": float(p1.mean()),
             "pred_rate_k0": float(p0.mean()), "null_rate": float(pn.mean()),
             "logloss": {"k1": logloss(y, p1), "k0": logloss(y, p0), "null": logloss(y, pn)},
             "brier": {"k1": float(np.mean((p1 - y) ** 2)), "k0": float(np.mean((p0 - y) ** 2)),
                       "null": float(np.mean((pn - y) ** 2))},
             "auc": {"k1": auc(y, p1), "k0": auc(y, p0), "null": auc(y, pn)},
             "calib_decile": calib(df, "dec", "p1", "yneg"), "calib_c": calib(df, "c_y", "p1", "yneg"),
             "calib_year": calib(df, "Y1", "p1", "yneg")}
        # magnitudes (uncensored rows), per sign, against persistence of the same-sign |G_y|
        mg = {}
        dd = df.filter(pl.col("cenG_y1") == 0)
        for sg, nm in (("neg", "gmag_neg"), ("pos", "gmag_pos")):
            d = dd.filter((pl.col("G_y1") < 0) if sg == "neg" else (pl.col("G_y1") > 0))
            yy = np.log(np.abs(d["G_y1"].to_numpy().astype(np.float64)))
            m1 = H.raw(nm, d, 1.0)
            m0 = H.raw(nm, d, 0.0)
            gy = d["G_y"].to_numpy().astype(np.float64)
            same = (gy < 0) if sg == "neg" else (gy > 0)
            pers = np.where(same & (gy != 0), np.log(np.abs(np.where(gy == 0, 1, gy))), np.nan)
            mg[sg] = {"n": d.height, "r2_k1": r2(yy, m1), "r2_k0": r2(yy, m0),
                      "r2_persist_copy_same_sign_rows": r2(yy[same], pers[same]),
                      "r2_k1_same_sign_rows": r2(yy[same], m1[same]), "share_same_sign": float(same.mean())}
        o["magnitude"] = mg
        # sampled G vs observed G (one draw)
        Gs = H.sample_G(df, rng.random(df.height), rng.random(df.height), 1.0)
        Go = df["G_y1"].to_numpy().astype(np.float64)
        qs = [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
        o["sampled_G_quantiles"] = {"q": qs, "obs": np.quantile(Go, qs).tolist(),
                                    "sampled": np.quantile(Gs, qs).tolist()}
        o["sampled_neg_rate"] = float((Gs < 0).mean())
        # counter by the rule, from sampled G: P(c_{y+1} >= 1) and c=5 kill rate vs observed
        cs = H.counter(df["c_y"].to_numpy(), Gs, df["Age"].to_numpy())
        co = df["c_y1"].to_numpy()
        o["counter"] = {"obs_c_ge1": float((co >= 1).mean()), "pred_c_ge1": float((cs >= 1).mean()),
                        "obs_c5": float((co >= 5).mean()), "pred_c5": float((cs >= 5).mean()),
                        "rule_identity_with_true_G": float((H.counter(df["c_y"].to_numpy(), Go,
                                                                       df["Age"].to_numpy()) == co).mean())}
        out["sets"][s] = o
        print(s, json.dumps({k: v for k, v in o.items() if not k.startswith("calib")}, default=float)[:1500],
              flush=True)
    rpt("A2", {"heldout": out, "models": {n: _meta_summary(H, n) for n in ("gsign", "gmag_neg", "gmag_pos")}})
    Hh.status("A2", f"eval written ({', '.join(SETS)})")


def _meta_summary(H, n):
    if n not in H.m:
        return None
    m = H.m[n][2]
    return {k: m.get(k) for k in ("n_rows", "n_train", "n_val", "max_rows", "b0_best_iter", "b1_best_iter",
                                  "b0_val", "b1_val", "t_b0_s", "t_b1_s")} | {
        "top_gain_B0": dict(list(m["gain_B0"].items())[:12]), "top_gain_B1": dict(list(m["gain_B1"].items())[:8])}


# ================================================================================================ contrast gate
def contrast(split):
    """Between-scenario contrast of mean P(G_{y+1}<0), fold-5 cells, ssp370 - ssp126, y+1 = 2015..2044."""
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    H = Hh.TabHeads.load(split, heads=["gsign"])
    keep = keep_cols(H, ["gsign"]) + ["G_y1", "cenG_y1", "fate_y1"]
    cells = spec["cells_f5"][:15] if SMOKE else spec["cells_f5"]
    yrs = range(2014, 2017) if SMOKE else range(2014, 2044)
    res = {}
    for gcm in ("ACCESS-CM2", "MPI-ESM1-2-HR"):
        obs = {}
        for scen in ("ssp126", "ssp370"):
            for seed in (1, 2):
                m = f"{gcm}_{scen}_s{seed}_w2015"
                rows = []
                for y in yrs:
                    lf = F.raw_training_frame(m, y, cells).filter((pl.col("fate_y1") <= 1)
                                                                  & (pl.col("cenG_y1") != 3))
                    d = Hh.add_next(F.assemble(lf)).select(list(dict.fromkeys(keep + ["Cell", "Year"]))).collect()
                    r = d.select("Cell", "Year", yneg=(pl.col("G_y1") < 0).cast(pl.Float64))
                    if seed == 1:
                        r = r.with_columns(p1=pl.Series(H.p_gneg(d, 1.0)), p0=pl.Series(H.p_gneg(d, 0.0)))
                    rows.append(r.group_by("Cell", "Year").agg(pl.all().mean(), n=pl.len()))
                A = pl.concat(rows)
                obs[(scen, seed)] = A
                print(gcm, scen, seed, A.height, flush=True)
        k = ["Cell", "Year"]
        J = (obs[("ssp370", 1)].select(k, o370=pl.col("yneg"), p1_370="p1", p0_370="p0")
             .join(obs[("ssp126", 1)].select(k, o126=pl.col("yneg"), p1_126="p1", p0_126="p0"), on=k)
             .join(obs[("ssp370", 2)].select(k, o370s2=pl.col("yneg")), on=k)
             .join(obs[("ssp126", 2)].select(k, o126s2=pl.col("yneg")), on=k))
        J = J.with_columns(d1=pl.col("o370") - pl.col("o126"), d2=pl.col("o370s2") - pl.col("o126s2"),
                           dp1=pl.col("p1_370") - pl.col("p1_126"), dp0=pl.col("p0_370") - pl.col("p0_126"))
        J = J.with_columns(spread=(pl.col("d1") - pl.col("d2")).abs())
        Q = J.filter(pl.col("d1").abs() > pl.col("spread"))
        hit1 = float((np.sign(Q["dp1"].to_numpy()) == np.sign(Q["d1"].to_numpy())).mean()) if Q.height else None
        hit0 = float((np.sign(Q["dp0"].to_numpy()) == np.sign(Q["d1"].to_numpy())).mean()) if Q.height else None
        allhit1 = float((np.sign(J["dp1"].to_numpy()) == np.sign(J["d1"].to_numpy())).mean())
        res[gcm] = {"cell_years": J.height, "qualifying": Q.height, "share_qualifying": Q.height / max(J.height, 1),
                    "sign_hit_k1": hit1, "sign_hit_k0": hit0, "sign_hit_k1_all_cell_years": allhit1,
                    "pass_k1": bool(hit1 is not None and hit1 >= 0.70),
                    "corr_pred_obs_k1": float(np.corrcoef(J["dp1"].to_numpy(), J["d1"].to_numpy())[0, 1]),
                    "corr_pred_obs_k0": float(np.corrcoef(J["dp0"].to_numpy(), J["d1"].to_numpy())[0, 1]),
                    "corr_obs_seed1_seed2": float(np.corrcoef(J["d1"].to_numpy(), J["d2"].to_numpy())[0, 1]),
                    "mean_abs_d1": float(J["d1"].abs().mean()), "mean_abs_dp1": float(J["dp1"].abs().mean()),
                    "n_cells": int(J["Cell"].n_unique()), "n_blocks": _nblocks(J["Cell"].unique().to_list())}
        J.write_parquet(os.path.join(Hh.mdir(split), f"contrast_{gcm}.parquet"))
        print(gcm, res[gcm], flush=True)
    res["definition"] = ("fold-5 dev cells; per (cell, y+1 in 2015-2044) mean over present stems of 1{G_{y+1}<0} "
                         "(observed) and of P(G_{y+1}<0) (predicted, truth seed-1 state); d1 = ssp370 - ssp126 seed 1, "
                         "d2 same for seed 2; qualifying: |d1| > |d1 - d2|; gate: sign(pred) == sign(d1) in >= 70 %")
    res["primary"] = "ACCESS-CM2 (held-out climate model); MPI is in-sample climate"
    rpt("A2", {"contrast_gate": res})
    ra, rm = res["ACCESS-CM2"], res["MPI-ESM1-2-HR"]
    Hh.status("A2", f"contrast gate: ACCESS hit {ra['sign_hit_k1']} (k0 {ra['sign_hit_k0']}) on {ra['qualifying']} "
                    f"cell-years; MPI hit {rm['sign_hit_k1']}")


def _nblocks(cells):
    f = pl.read_parquet(os.path.join(tr.REG, "folds.parquet")).filter(pl.col("Cell").is_in(cells))
    return int(f["block"].n_unique())


# ================================================================================================ A3
def eval_A3(split):
    H = Hh.TabHeads.load(split)
    keep = keep_cols(H, ["gsign", "gmag_neg", "gmag_pos", "dagb", "dvegc", "dlai", "dfpc", "dd95"]) + TGT_KEEP
    out = {"basis": "unweighted held-out rows; present stems at y+1 (alive or flagged dead)", "sets": {}}
    rng = np.random.default_rng(7)
    allom = rl.load_allometry(split)
    allom_x = rl.load_allometry(split, ext=True)
    for s in SETS:
        df = L(Hh.load_rows(split, s, pl.col("fate_y1") <= 1, keep=keep))
        df = df.filter(pl.col("Type").is_in(allom["Type"].to_list()))
        agb, agb1 = df["agb"].to_numpy().astype(np.float64), df["agb_y1"].to_numpy().astype(np.float64)
        y_dl = np.log(agb1 / agb)
        d2 = agb1 - agb
        G1, c1 = df["G_y1"].to_numpy(), df["c_y1"].to_numpy()
        o = {"n": df.height}
        # teacher-forced (true next-year G and c): NOT a skill claim
        tf1, tfv1, _ = H.growth(df, G1, c1, kappa=1.0)
        tf0, _, _ = H.growth(df, G1, c1, kappa=0.0)
        # honest one-step: G from the A2 heads (deterministic plug-in E[G], and one random draw incl. AR noise)
        Ge = H.expected_G(df, 1.0)
        ce = H.counter(df["c_y"].to_numpy(), Ge, df["Age"].to_numpy())
        pe1, _, _ = H.growth(df, Ge, ce, kappa=1.0)
        Ge0 = H.expected_G(df, 0.0)
        pe0, _, _ = H.growth(df, Ge0, H.counter(df["c_y"].to_numpy(), Ge0, df["Age"].to_numpy()), kappa=0.0)
        Gs = H.sample_G(df, rng.random(df.height), rng.random(df.height), 1.0)
        cs = H.counter(df["c_y"].to_numpy(), Gs, df["Age"].to_numpy())
        z = {"dagb": rng.standard_normal(df.height), "dvegc": rng.standard_normal(df.height)}
        e0 = {"dagb": np.zeros(df.height), "dvegc": np.zeros(df.height)}
        ps1, _, _ = H.growth(df, Gs, cs, e0, z, kappa=1.0)
        prev = df["d_agb_prev"].to_numpy().astype(np.float64)
        mprev = np.isfinite(prev)
        d1 = prev[mprev]
        y2 = d2[mprev]
        rho = np.corrcoef(d1, y2)[0, 1]
        o["dagb"] = {
            "r2_dlog_teacher_forced_k1": r2(y_dl, tf1), "r2_dlog_teacher_forced_k0": r2(y_dl, tf0),
            "r2_dlog_expectedG_k1": r2(y_dl, pe1), "r2_dlog_expectedG_k0": r2(y_dl, pe0),
            "r2_dlog_one_draw_k1": r2(y_dl, ps1),
            "null_basis_rows": int(mprev.sum()),
            "R2_dagb_persist_null": float(rho ** 2),
            "R2_dagb_copy_null": float(1 - np.mean((y2 - d1) ** 2) / np.var(y2)),
            "sd_ratio_d1_d2": float(np.std(d1) / np.std(y2)),
            "R2_dagb_teacher_forced_k1": r2(y2, (agb * np.exp(tf1) - agb)[mprev]),
            "R2_dagb_expectedG_k1": r2(y2, (agb * np.exp(pe1) - agb)[mprev]),
            "R2_dagb_expectedG_k0": r2(y2, (agb * np.exp(pe0) - agb)[mprev]),
            "R2_dagb_one_draw_k1": r2(y2, (agb * np.exp(ps1) - agb)[mprev]),
        }
        yv = np.log(df["vegc_y1"].to_numpy().astype(np.float64) / df["vegc"].to_numpy())
        o["dvegc"] = {"r2_dlog_teacher_forced_k1": r2(yv, tfv1)}
        # closures, teacher-forced on the true G, c and growth
        cl = H.closures(df, G1, c1, y_dl, yv, 1.0)
        for g, col in (("dlai", "LAI"), ("dfpc", "fpc_ind"), ("dd95", "D95")):
            if g in cl:
                yy = np.log(df[f"{col}_y1"].to_numpy().astype(np.float64) / df[col].to_numpy())
                o[g] = {"r2_teacher_forced_k1": r2(yy, cl[g]), "r2_zero_change_null": r2(yy, np.zeros_like(yy)),
                        "sd_target": float(np.std(yy))}
        # height: allometry of the TRUE agb_{y+1} + a fixed per-tree offset from year y
        H0 = df["Height"].to_numpy().astype(np.float64)
        H1o = df["Height_y1"].to_numpy().astype(np.float64)
        wd, sla, ty = df["Wooddens"].to_numpy(), df["SLA"].to_numpy(), df["Type"].to_numpy()
        off = np.log(H0) - np.log(rl.predict_height(agb, wd, sla, ty, allom))
        hb = rl.predict_height(agb1, wd, sla, ty, allom) * np.exp(off)
        lai, fpc = df["LAI"].to_numpy(), df["fpc_ind"].to_numpy()
        offx = np.log(H0) - np.log(rl.predict_height(agb, wd, sla, ty, allom_x, lai=lai, fpc_ind=fpc))
        hx = rl.predict_height(agb1, wd, sla, ty, allom_x, lai=df["LAI_y1"].to_numpy(),
                               fpc_ind=df["fpc_ind_y1"].to_numpy()) * np.exp(offx)
        hn = rl.predict_height(agb1, wd, sla, ty, allom)
        o["height"] = {"r2_dH_allom_offset": r2(H1o - H0, hb - H0), "r2_dH_allom_ext_offset": r2(H1o - H0, hx - H0),
                       "r2_dH_allom_no_offset": r2(H1o - H0, hn - H0),
                       "rmse_lnH_offset": float(np.sqrt(np.mean((np.log(H1o) - np.log(hb)) ** 2))),
                       "rmse_lnH_ext_offset": float(np.sqrt(np.mean((np.log(H1o) - np.log(hx)) ** 2))),
                       "rmse_lnH_persist": float(np.sqrt(np.mean((np.log(H1o) - np.log(H0)) ** 2))),
                       "basis": "teacher-forced: true agb_{y+1} (and LAI/fpc for the extended form)"}
        out["sets"][s] = o
        print(s, json.dumps(o, default=float)[:2500], flush=True)
    # AR tables
    out["ar"] = {g: {k: H.ar[g][k] for k in ("rho_pooled", "n_pairs_total")} | {
        "rho_median_by_type": {t: float(np.median(v)) for t, v in H.ar[g]["rho"].items()}} for g in H.ar}
    # grass head and the grass-importance decision
    out["grass"] = eval_grass(split, H)
    rpt("A3", {"heldout": out, "models": {n: _meta_summary(H, n) for n in ("dagb", "dvegc", "dlai", "dfpc", "dd95")}})
    Hh.status("A3", "eval written")


def eval_grass(split, H):
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    res = {}
    gshare = {}
    for n in ("gsign", "dagb", "surv"):
        if n in H.m:
            g = H.m[n][2]["gain_B0"]
            gshare[n] = float(sum(v for k, v in g.items() if k.startswith("grass")))
    res["grass_gain_share_in_tree_heads"] = gshare
    res["decision"] = ("keep the grass head" if max(gshare.values() or [0]) >= 0.01 else
                       "drop: grass features carry < 1 % of the gain of every tree head; carry grass by persistence")
    for s, mem, cells in (("F5", spec["train"], spec["cells_f5"]), ("GCM", spec["heldout"]["GCM"], spec["cells_dev"])):
        D = Hh.grass_frame(split, s, mem, cells[:10] if SMOKE else cells, frac=0.1)
        pr = H.grass(D, 1.0)
        res[s] = {"n": D.height}
        for t, src in (("g_fpc_y1", "grass8_fpc_y"), ("g_LAI_y1", "grass8_LAI_y"), ("g_agb_y1", "grass8_agb_y")):
            if t in pr:
                y = D[t].to_numpy()
                res[s][t] = {"r2_k1": r2(y, pr[t]), "r2_k0": r2(y, H.grass(D, 0.0)[t]),
                             "r2_persist": r2(y, D[src].to_numpy())}
    return res


# ================================================================================================ A4
def eval_A4(split):
    H = Hh.TabHeads.load(split, heads=["gsign", "gmag_neg", "gmag_pos", "surv", "surv_phys"])
    keep = keep_cols(H, ["surv", "surv_phys", "gsign", "gmag_neg", "gmag_pos"]) + TGT_KEEP + ["tstress_own_y1"]
    P = rl.load_params()
    out = {"basis": "unweighted held-out rows; present stems at y+1 with c_{y+1} < 5 (c = 5 is the rule kill)",
           "sets": {}}
    rng = np.random.default_rng(11)
    for s in SETS:
        df = L(Hh.load_rows(split, s, pl.col("fate_y1") <= 1, keep=keep))
        allp = df
        df = df.filter(pl.col("c_y1") < 5)
        y = (df["fate_y1"].to_numpy() == 1).astype(np.float64)
        G1, c1 = df["G_y1"].to_numpy(), df["c_y1"].to_numpy()
        p = {"surv_k1": H.p_death(df, G1, c1, False, 1.0), "surv_k0": H.p_death(df, G1, c1, False, 0.0),
             "phys_k1": H.p_death(df, G1, c1, True, 1.0), "phys_k0": H.p_death(df, G1, c1, True, 0.0)}
        mort = df["mort_y1"].to_numpy().astype(np.float64)
        hp = Hh.h_phys(df["Type"].to_numpy(), df["Wooddens"].to_numpy(), df["Age"].to_numpy(), G1, c1,
                       df["tstress_own_y1"].to_numpy(), P)
        fire_like = mort < 0.01
        o = {"n": df.height, "obs_death_rate": float(y.mean()),
             "logloss": {k: logloss(y, v) for k, v in p.items()} | {"null_printed_hazard": logloss(y, mort),
                                                                     "null_rule_hazard": logloss(y, hp)},
             "auc": {k: auc(y, v) for k, v in p.items()} | {"null_printed_hazard": auc(y, mort)},
             "pred_death_rate": {k: float(v.mean()) for k, v in p.items()},
             "fire_like_share_of_deaths": {
                 "obs": float(y[fire_like].sum() / max(y.sum(), 1)),
                 **{k: float(v[fire_like].sum() / v.sum()) for k, v in p.items()}},
             "fire_like_definition": "flagged dead with c_{y+1} < 5 and printed mort_{y+1} < 0.01"}
        d = df.with_columns(p=pl.Series(p["surv_k1"]), pp=pl.Series(p["phys_k1"]), yd=pl.Series(y),
                            mdec=pl.Series(deciles(mort)), Y1=pl.col("Year") + 1)
        o["calib_mort_decile_surv_k1"] = calib(d, "mdec", "p", "yd")
        o["calib_mort_decile_phys_k1"] = calib(d, "mdec", "pp", "yd")
        o["calib_c_surv_k1"] = calib(d, "c_y1", "p", "yd")
        o["calib_c_phys_k1"] = calib(d, "c_y1", "pp", "yd")
        o["calib_year_surv_k1"] = calib(d, "Y1", "p", "yd")
        # chain check: sampled G -> rule counter (kills at 5) -> learned survival, on ALL present stems
        Gs = H.sample_G(allp, rng.random(allp.height), rng.random(allp.height), 1.0)
        cs = H.counter(allp["c_y"].to_numpy(), Gs, allp["Age"].to_numpy())
        pdth = H.p_death(allp, Gs, cs, False, 1.0)
        o["chain_one_draw"] = {"obs_dead_rate_all_present": float((allp["fate_y1"].to_numpy() == 1).mean()),
                               "pred_dead_rate": float(pdth.mean()),
                               "obs_rule_kills_c5": float((allp["c_y1"].to_numpy() >= 5).mean()),
                               "pred_rule_kills_c5": float((cs >= 5).mean())}
        out["sets"][s] = o
        print(s, json.dumps({k: v for k, v in o.items() if not k.startswith("calib")}, default=float)[:2000],
              flush=True)
    rpt("A4", {"heldout": out, "models": {n: _meta_summary(H, n) for n in ("surv", "surv_phys")}})
    Hh.status("A4", "eval written")


# ================================================================================================ A5
def eval_A5(split):
    H = Hh.TabHeads.load(split, heads=["rtype"])
    out = {"rtype": {}}
    for s in SETS:
        fs = glob.glob(os.path.join(F.SAMPLES, split, "recruits", s, "*.parquet"))
        D = pl.read_parquet(fs).filter(pl.col("Type").is_in(F.RECR_TYPES) & (pl.col("u_rec") < 0.25))
        D = L(F.recruit_features(D))
        lab = np.searchsorted(F.RECR_TYPES, D["Type"].to_numpy())
        p1 = H.recruit_type_probs(D, 1.0)
        p0 = H.recruit_type_probs(D, 0.0)
        sh = np.stack([D[f"ce_share_t{k}"].fill_null(0).to_numpy() for k in F.RECR_TYPES], 1).astype(np.float64)
        sh = (sh + 0.01) / (sh + 0.01).sum(1, keepdims=True)
        ll = {k: float(-np.mean(np.log(np.clip(v[np.arange(len(lab)), lab], EPS, 1)))) for k, v in
              (("k1", p1), ("k0", p0), ("null_cell_share", sh))}
        out["rtype"][s] = {"n": D.height, "logloss": ll,
                           "obs_share": {k: float((lab == i).mean()) for i, k in enumerate(F.RECR_TYPES)},
                           "pred_share_k1": {k: float(p1[:, i].mean()) for i, k in enumerate(F.RECR_TYPES)},
                           "accuracy_k1": float((p1.argmax(1) == lab).mean()),
                           "accuracy_null": float((sh.argmax(1) == lab).mean())}
        print(s, out["rtype"][s], flush=True)
    out["rtype_model"] = _meta_summary(H, "rtype")
    rpt("A5", out)
    Hh.status("A5", "rtype eval written")


def run(split, item):
    {"A2": eval_A2, "A3": eval_A3, "A4": eval_A4, "A5": eval_A5}[item](split)


# ================================================================================================ A5 trait sampler
def standing_year(member, y, cells):
    f = [x for x in F.trans_files(member) if x.endswith(f"y{y}.parquet")][0]
    return pl.scan_parquet(f).filter(pl.col("Cell").is_in(cells)).select(
        "Cell", "Type", "Year", pl.col("agb").cast(pl.Float64), *[pl.col(k).cast(pl.Float64) for k, _ in
                                                                    Hh.TRAIT_AX]).collect()


def ks_stat(a, b):
    a = np.sort(a)
    b = np.sort(b)
    x = np.concatenate([a, b])
    return float(np.max(np.abs(np.searchsorted(a, x, side="right") / len(a)
                               - np.searchsorted(b, x, side="right") / len(b))))


def traits(split):
    """Fit (w, a, s) per Type by minimum summed KS distance (SLA, Wooddens, D95max, minwscal) between simulated and
    observed TRAINING recruits (training members, folds 1-4, every 3rd year), with common random numbers; then the
    held-out gates: beech recruit-vs-standing cell-mean slope and outside-own-interval shares per binary."""
    P = rl.load_params()
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    rec = pl.read_parquet(glob.glob(os.path.join(F.SAMPLES, split, "recruits", "train", "*.parquet"))).filter(
        pl.col("Type").is_in(F.RECR_TYPES))
    years = sorted(rec["Year"].unique().to_list())[::3]
    rec = rec.filter(pl.col("Year").is_in(years))
    # fitting cell-years: every 3rd recruit year, a fixed 40 % of the training cells (donor pools stay complete)
    cells = [c for c in spec["cells_train"] if (c * 2654435761) % 1000 < 400]
    rec = rec.filter(pl.col("Cell").is_in(cells))
    parts = []
    for mi, m in enumerate(spec["train"]):
        for y in years:
            if any(f.endswith(f"y{y}.parquet") for f in F.trans_files(m)):
                parts.append(standing_year(m, y, cells).with_columns(YearX=pl.lit(mi * 10000 + y, pl.Int32)))
    st = pl.concat(parts)
    rec = rec.with_columns(YearX=(pl.col("member").replace_strict(spec["train"], list(range(len(spec["train"]))),
                                                                   return_dtype=pl.Int32) * 10000
                                  + pl.col("Year").cast(pl.Int32)))
    grid_w = [0.0, 0.25, 0.5, 0.7, 0.85, 0.95, 1.0]
    grid_a = [0.0, 0.5, 1.0, 2.0]
    grid_s = [0.02, 0.05, 0.1, 0.15, 0.2, 0.3]
    if SMOKE:
        grid_w, grid_a, grid_s, years = [0.0, 0.5, 1.0], [0.0, 1.0], [0.1], years[:1]
        rec = rec.filter(pl.col("Year").is_in(years))
    fit, tab = {}, {}
    for t in F.RECR_TYPES:
        R = rec.filter(pl.col("Type") == t)
        if R.height > 60000:
            R = R.filter(pl.col("u_rec") < 60000 / R.height)
        obs = {k: R[k].to_numpy().astype(np.float64) for k, _ in Hh.TRAIT_AX}
        S = st.filter(pl.col("Type") == t).select(pl.col("Cell"), pl.col("Type"), pl.col("YearX").alias("Year"),
                                                  "agb", *[k for k, _ in Hh.TRAIT_AX])
        D = Hh.prep_donors(np.full(R.height, t), R["Cell"].to_numpy(), S, recruit_year=R["YearX"].to_numpy())
        U = Hh.crn(R.height, np.random.default_rng(1000 + t))  # common random numbers across the grid
        best = None
        rows = []
        for a_ in grid_a:
            for s_ in grid_s:
                for w_ in grid_w:
                    sim = Hh.mix_draw(D, {str(t): {"w": w_, "a": a_, "s": s_}}, "dec2025", U, P)
                    ks = {k: ks_stat(sim[k], obs[k]) for k, _ in Hh.TRAIT_AX}
                    tot = sum(ks.values())
                    rows.append({"w": w_, "a": a_, "s": s_, "ks_sum": tot, **ks})
                    if best is None or tot < best["ks_sum"]:
                        best = rows[-1]
        fit[str(t)] = {"w": best["w"], "a": best["a"], "s": best["s"]}
        tab[str(t)] = {"best": best, "n_recruits": R.height, "n_standing": S.height,
                       "share_with_same_type_stem": float(D["has"].mean()),
                       "uniform_only": [r for r in rows if r["w"] == 0.0][0],
                       "kernel_like_a0_s0.1_bestw": min((r for r in rows if r["a"] == 0.0 and r["s"] == 0.1),
                                                        key=lambda r: r["ks_sum"])}
        print(t, tab[str(t)], flush=True)
    json.dump(fit, open(os.path.join(Hh.mdir(split), "traits_fit.json"), "w"), indent=1)
    out = {"fit": fit, "fit_detail": tab, "fit_basis": f"training recruits, years {years}, folds 1-4, dec2025"}
    out["gates"] = trait_gates(split, fit, P)
    rpt("A5", {"traits": out})
    Hh.status("A5", f"traits fit {fit}; gates written")


def interval_out(typ, k, v, P):
    pre = dict(Hh.TRAIT_AX)[k]
    lo, hi = P[f"{pre}_low"][typ], P[f"{pre}_high"][typ]
    return (v < lo * (1 - 1e-6)) | (v > hi * (1 + 1e-6))


def trait_gates(split, fit, P):
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    mem = {m: spec["rows"][m] for m in spec["rows"]}
    tests = {"GCM": [m for m in spec["heldout"]["GCM"] if "Historical" not in m],
             "SCEN": spec["heldout"]["SCEN"], "SEED2": [m for m in spec["heldout"]["SEED2"] if "Historical" not in m]}
    res = {}
    for s, ms in tests.items():
        for m in (ms[:1] if SMOKE else ms):
            cells = spec["cells_dev"][:30] if SMOKE else spec["cells_dev"]
            build = "feb2026" if int(mem[m]["bin_feb2026"]) == 1 else "dec2025"
            R = pl.read_parquet(glob.glob(os.path.join(F.SAMPLES, split, "recruits", s, f"{m}.parquet"))).filter(
                pl.col("Type").is_in(F.RECR_TYPES))
            R = R.filter(pl.col("Cell").is_in(cells))
            years = sorted(R["Year"].unique().to_list())[: (2 if SMOKE else None)]
            rng = np.random.default_rng(5)
            sims = []
            for y in years:
                Ry = R.filter(pl.col("Year") == y)
                S = standing_year(m, y, cells).select(pl.col("Cell").cast(pl.Int16), pl.col("Type").cast(pl.Int8),
                                                      "agb", *[k for k, _ in Hh.TRAIT_AX])
                sim = Hh.sample_traits(Ry["Type"].to_numpy(), Ry["Cell"].to_numpy(), S, fit, build, rng, P)
                sims.append(Ry.select("Cell", "Type", "Year", "Age", *[k for k, _ in Hh.TRAIT_AX]).with_columns(
                    *[pl.Series(f"p_{k}", sim[k]) for k, _ in Hh.TRAIT_AX], donor=pl.Series(sim["donor"])))
            D = pl.concat(sims)
            ty = D["Type"].to_numpy()
            o = {"build": build, "n_recruits": D.height, "outside_interval": {}}
            for k in ("Wooddens", "D95max"):
                ob = interval_out(ty, k, D[k].to_numpy(), P)
                pr = interval_out(ty, k, D[f"p_{k}"].to_numpy(), P)
                est = (D["Year"] + 1 - D["Age"] + 1).to_numpy()
                o["outside_interval"][k] = {
                    "obs": float(ob.mean()), "pred": float(pr.mean()),
                    "obs_beech": float(ob[ty == 3].mean()), "pred_beech": float(pr[ty == 3].mean()),
                    "obs_established_before_2015": float(ob[est < 2015].mean()) if (est < 2015).any() else None,
                    "obs_established_2015_on": float(ob[est >= 2015].mean()) if (est >= 2015).any() else None}
            # beech locality slope (round-1 definition): standing means at the first year per (Cell, Type), recruit
            # means pooled over the window; groups n_st >= 30 and n_rec >= 10; slope across cells
            y0 = years[0]
            S0 = standing_year(m, y0, cells)
            tx = [k for k, _ in Hh.TRAIT_AX]
            agg_st = S0.group_by("Cell", "Type").agg([pl.len().alias("n_st")]
                                                     + [pl.col(k).mean().alias(f"{k}_st") for k in tx])
            agg_r = D.group_by("Cell", "Type").agg([pl.len().alias("n_rec")]
                                                   + [pl.col(k).cast(pl.Float64).mean().alias(f"{k}_rec") for k in tx]
                                                   + [pl.col(f"p_{k}").mean().alias(f"{k}_prd") for k in tx])
            G = agg_st.join(agg_r, on=["Cell", "Type"]).filter((pl.col("n_st") >= 30) & (pl.col("n_rec") >= 10))
            sl = {}
            for t in F.RECR_TYPES:
                g = G.filter(pl.col("Type") == t)
                if g.height < 20:
                    continue
                sl[t] = {"groups": g.height}
                for k, _ in Hh.TRAIT_AX:
                    x = g[f"{k}_st"].to_numpy()
                    xc = x - x.mean()
                    for lab, col in (("obs", f"{k}_rec"), ("pred", f"{k}_prd")):
                        yv = g[col].to_numpy()
                        sl[t][f"{k}_{lab}"] = float((xc * (yv - yv.mean())).sum() / (xc * xc).sum())
            o["slope_recruit_on_standing"] = sl
            o["donor_share"] = float(D["donor"].mean())
            res[m] = o
            print(m, json.dumps(o, default=float)[:1500], flush=True)
    res["note"] = ("beech slope reference 0.71-1.07 is round 1's single-member measurement (MPI seed 1); here the "
                   "standing year is each window's first table year (2014) and recruits are pooled over 2015-2044")
    return res


# ================================================================================================ API test
def apitest(split, n_cells=40):
    """One A-TAB transition on a real SH5 initial state (MPI Historical s1 2014 -> 2015 under ssp370, fold-5 cells),
    via the public API only; checks finiteness, compares the step's aggregate outcomes with the truth table, and
    times it (process time per tree; single process, LightGBM threads = SLURM cpus)."""
    import explore_de_engine as en
    spec = json.load(open(os.path.join(F.SAMPLES, split, "split.json")))
    cells = np.array(spec["cells_f5"][:n_cells], np.int32)
    gcm, seed, Y = "MPI-ESM1-2-HR", 1, 2014
    state = en.load_init(f"{gcm}_Historical_s{seed}_{Y}", F.CELLSET, cells)
    fi = glob.glob(os.path.join(F.XDE, "shared", "init", F.CELLSET, f"{gcm}_Historical_s{seed}_{Y}", "cb=*",
                                "trees.parquet"))[0]
    it = pl.read_parquet(fi).filter(pl.col("Cell").is_in(cells.tolist())).sort(["Cell", "Patch", "Type", "ID"])
    F.init_conventions(state, it["spinin"].to_numpy(), Y)
    t0 = time.process_time()
    w0 = time.time()
    H = Hh.TabHeads.load(split)
    t_load = time.process_time() - t0
    state.aux_tree["h_off"] = H.height_offset(state.tree["agb"], state.tree["Wooddens"], state.tree["SLA"],
                                              state.tree["Type"], state.tree["Height"])
    ch = en.Climate(gcm, "Historical", seed, state.cell["cells"], "actual")
    c1 = en.Climate(gcm, "ssp370", seed, state.cell["cells"], "actual")
    rand = en.Rand("A-TAB-test", 1, gcm)
    cy, cy1 = ch.year(Y), c1.year(Y + 1)
    t1 = time.process_time()
    X = H.features(state, cy, cy1, gcm)
    t2 = time.process_time()
    out = H.transition(X, state, rand, Y)
    t3 = time.process_time()
    n = state.n
    tru = pl.scan_parquet(glob.glob(os.path.join(tr.TRANS, F.CELLSET, f"{gcm}_ssp370_s{seed}_w2015", "cb=*",
                                                 f"y{Y}.parquet"))).filter(pl.col("Cell").is_in(cells.tolist())).collect()
    res = {"trees": n, "cells": len(cells), "cpu_s_load": t_load, "cpu_s_features": t2 - t1,
           "cpu_s_transition": t3 - t2, "wall_s_total": time.time() - w0,
           "cpu_us_per_tree_step": 1e6 * (t3 - t1) / n, "threads": Hh.NTHREADS,
           "finite": {k: bool(np.isfinite(np.asarray(v, np.float64)).all()) for k, v in out["tree"].items()},
           "pred_dead_rate": float(out["isdead"].mean()), "obs_dead_rate": float((tru["fate_y1"] == 1).mean()),
           "pred_mean_dlog_agb": float(np.mean(np.log(out["tree"]["agb"] / state.tree["agb"]))),
           "obs_mean_dlog_agb": float(np.log(tru.filter(pl.col("fate_y1") <= 1)["agb_y1"].to_numpy()
                                             / tru.filter(pl.col("fate_y1") <= 1)["agb"].to_numpy()).mean()),
           "pred_neg_G": float((out["tree"]["G"] < 0).mean()),
           "obs_neg_G": float((tru.filter(pl.col("fate_y1") <= 1)["G_y1"] < 0).mean())}
    rpt("A1", {"api_test": res})
    print(json.dumps(res, indent=1, default=float), flush=True)
    Hh.status("A1", f"apitest: {res['cpu_us_per_tree_step']:.1f} cpu-us/tree-step over {n} trees ({Hh.NTHREADS} thr)")
