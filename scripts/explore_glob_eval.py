#!/usr/bin/env python3
"""explore_glob_eval.py -- LINE X, the scorer for the global venue (ADR 0315), and its baselines.

Per-cell statistics are the Germany reference's, reduced by THE SAME CODE (explore_de_reference.living /
reduce_window; ADR 0111 basis: per cell, pooled over a 30-year window), with NPATCH = 25. Round 1 scores the DEV
cells (Cell % 10 == 0, the converted ind_dev tables) -- 10 % of the grid, NOT the acceptance criterion's all cells.

STAGES
  levels    every member-window of the registry -> eval/levels/<member>.parquet (dev cells, its window) and the
            member's last-year snapshot (h1985 legs: 2014) -> eval/levels/<member>_y<last>.parquet
  nulls     scores the baselines on the GS370 venue (truth = member 8, ssp370, 2071-2100) -> eval/nulls_GS370.csv
  all       levels, nulls

THE PANEL (ADR 0315 sec. 4): n_per_patch (stems), agb per stem (agb_stand / n_per_patch), and the q50 of SLA,
Wooddens, D95max, minwscal. A cell passes when EVERY panel quantity passes (conjunctive). Cells: dev cells with a
living tree in the truth's h1985 or w2071 window.
TOLERANCE per (cell, quantity): |T| * max(10 %, S), S = median over the cell's density stratum (n_per_patch of the
truth: <2, 2-5, 5-10, 10-20, >20) of |T - R| / mean(T, R), T = member 8, R = member 7 (the other member) -- ADR 0111's
form. Every pass rate is also reported at a flat 10 % (ADR 0315: 25 patches widen S).
AREA TOTALS: sum(area * n_per_patch) and agb per stem = sum(area * agb_stand) / sum(area * n_per_patch), ratio P/T.
RESPONSE per cell: d = X(w2071) - X(h1985), each prediction against ITS OWN baseline (the nulls that start from the
truth member use member 8's h1985). Reported: area-weighted aggregate ratio sum(dP)/sum(dT), the OLS slope of dP on
dT across cells, and that slope deattenuated for the truth's own member noise (var(dT8 - dT7) / 2).

BASELINES and what each MUST return (written before the run, ADR 0184; the `expect` column of the output):
  ceiling     member 7 (its own h1985 -> ssp370 w2071): level pass rate <= 1, area ratios ~1 (|r-1| < 0.05),
              aggregate response ratio ~1 (0.8-1.2).
  persist_h   member 8's own 1985-2014 statistics carried to 2071-2100: response EXACTLY 0 (slope 0, aggregate 0)
              -- a harness check; any non-zero value is a bug.
  persist_2014  member 8's 2014 snapshot carried forward: response = (2014 - 1985-2014 mean), small vs the warming
              response; level pass rate below the ceiling.
  lookup_245  mean over the GS370 training members (2,3,4,6) of the SAME cell's ssp245 2071-2100 statistics: the
              nearest training scenario; aggregate response ratio < 1 if ssp370's response exceeds ssp245's.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_reference as R  # noqa: E402  (THE reduction)

DATA = "/p/projects/open/Jamir/esm_land_emulator_data/billing_global"
REG = os.path.join(DATA, "registry")
EVAL = os.path.join(DATA, "eval")
LEV = os.path.join(EVAL, "levels")
NPATCH = 25
WIN = {"h1985": (1985, 2014), "w2071": (2071, 2100), "h1990": (1990, 2019)}
PANEL = ["n_per_patch", "agb_per_stem", "SLA_q50", "Wooddens_q50", "D95max_q50", "minwscal_q50"]
STRATA = [2.0, 5.0, 10.0, 20.0]
TRUTH, REPLICA, TRAIN = 8, 7, (2, 3, 4, 6)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def dev_cells() -> pl.DataFrame:
    f = pl.read_parquet(os.path.join(REG, "folds.parquet"))
    return f.filter(pl.col("is_dev") & ~pl.col("rock")).select("Cell", "lat", "fold")


def reduce(path: str, y0: int, y1: int, cells: list[int]) -> pl.DataFrame:
    lf = pl.scan_parquet(path).filter(pl.col("Year").is_between(y0, y1) & pl.col("Cell").is_in(cells))
    lf = lf.select(pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32), pl.col("Type").cast(pl.Int8),
                   pl.col("isdead").cast(pl.Int8), *[pl.col(t).cast(pl.Float32) for t in R.TRAITS])
    ny = lf.select(pl.col("Year").n_unique()).collect().item()
    assert ny == y1 - y0 + 1, f"{path}: {ny} years in {y0}-{y1}"
    trees = R.living(lf).collect()
    cy = pl.DataFrame({"Cell": cells, "n_years": [ny] * len(cells)})
    d = R.reduce_window(trees, cy, NPATCH)
    return d.with_columns(pl.when(pl.col("n_per_patch") > 0).then(pl.col("agb_stand") / pl.col("n_per_patch"))
                          .otherwise(None).alias("agb_per_stem"))


def stage_levels():
    os.makedirs(LEV, exist_ok=True)
    m = pl.read_parquet(os.path.join(REG, "members.parquet"))
    cells = dev_cells()["Cell"].to_list()
    for r in m.iter_rows(named=True):
        out = os.path.join(LEV, f"{r['member']}.parquet")
        y0, y1 = WIN[r["window"]]
        if not os.path.exists(out):
            t0 = time.time()
            reduce(r["ind_dev_path"], y0, y1, cells).write_parquet(out)
            log(f"{r['member']}: {y0}-{y1} reduced ({time.time() - t0:.0f}s)")
        snap = os.path.join(LEV, f"{r['member']}_y{y1}.parquet")
        if r["window"] == "h1985" and not os.path.exists(snap):
            reduce(r["ind_dev_path"], y1, y1, cells).write_parquet(snap)
            log(f"{r['member']}: {y1} snapshot reduced")


def lev(member: str, suffix: str = "") -> pl.DataFrame:
    return pl.read_parquet(os.path.join(LEV, f"{member}{suffix}.parquet")).select(["Cell"] + PANEL)


def mname(scen: str, seed: int) -> str:
    return f"GFDL-ESM4_{scen}_s{seed}_{'h1985' if scen == 'historical' else 'w2071'}"


def long(d: pl.DataFrame, name: str) -> pl.DataFrame:
    return d.unpivot(index="Cell", on=PANEL, variable_name="q", value_name=name)


def score(pred_w: pl.DataFrame, pred_h: pl.DataFrame, T_w, T_h, R_w, R_h, cells: pl.DataFrame) -> dict:
    j = (long(T_w, "T").join(long(R_w, "R"), on=["Cell", "q"]).join(long(pred_w, "P"), on=["Cell", "q"])
         .join(long(T_h, "Th"), on=["Cell", "q"]).join(long(R_h, "Rh"), on=["Cell", "q"])
         .join(long(pred_h, "Ph"), on=["Cell", "q"]).join(cells, on="Cell"))
    dens = T_w.select("Cell", pl.col("n_per_patch").alias("dens"))
    j = j.join(dens, on="Cell").with_columns(
        pl.col("dens").cut(STRATA, labels=["<2", "2-5", "5-10", "10-20", ">20"]).alias("stratum"),
        ((pl.col("T") - pl.col("R")).abs() / ((pl.col("T") + pl.col("R")).abs() / 2)).alias("spread"))
    S = j.group_by(["q", "stratum"]).agg(pl.col("spread").median().alias("S"))
    j = j.join(S, on=["q", "stratum"]).with_columns(
        (pl.col("T").abs() * pl.max_horizontal(pl.lit(0.10), pl.col("S"))).alias("allowed"))
    j = j.with_columns(((pl.col("P") - pl.col("T")).abs() <= pl.col("allowed") * (1 + 1e-9)).alias("pass"),
                       ((pl.col("P") - pl.col("T")).abs() <= 0.10 * pl.col("T").abs() * (1 + 1e-9)).alias("pass10"))
    # a quantity with no truth value (too few stems for a quantile) is not scored; a missing prediction fails
    j = j.filter(pl.col("T").is_not_null()).with_columns(pl.col("pass").fill_null(False), pl.col("pass10").fill_null(False))
    cellpass = j.group_by("Cell").agg(pl.col("pass").all().alias("ok"), pl.col("pass10").all().alias("ok10"))
    out = dict(n_cells=cellpass.height, pass_rate=float(cellpass["ok"].mean()),
               pass_rate_flat10=float(cellpass["ok10"].mean()))
    for q in PANEL:
        jq = j.filter(pl.col("q") == q)
        out[f"pass_{q}"] = float(jq["pass"].mean())
    # area totals
    a = (T_w.select("Cell", pl.col("n_per_patch").alias("nT"), (pl.col("agb_per_stem") * pl.col("n_per_patch")).alias("bT"))
         .join(pred_w.select("Cell", pl.col("n_per_patch").alias("nP"),
                             (pl.col("agb_per_stem") * pl.col("n_per_patch")).alias("bP")), on="Cell")
         .join(cells, on="Cell").with_columns(np.cos(np.deg2rad(pl.col("lat"))).alias("w")).fill_null(0.0))
    sw = lambda c: float((a[c] * a["w"]).sum())  # noqa: E731
    out["stems_ratio"] = sw("nP") / sw("nT")
    out["agb_per_stem_ratio"] = (sw("bP") / sw("nP")) / (sw("bT") / sw("nT"))
    # response, per quantity
    jr = j.with_columns((pl.col("P") - pl.col("Ph")).alias("dP"), (pl.col("T") - pl.col("Th")).alias("dT"),
                        (pl.col("R") - pl.col("Rh")).alias("dR")).drop_nulls(["dP", "dT", "dR"])
    for q in ("n_per_patch", "agb_per_stem", "Wooddens_q50", "SLA_q50"):
        x = jr.filter(pl.col("q") == q)
        dP, dT, dR = (x[c].to_numpy() for c in ("dP", "dT", "dR"))
        w = np.cos(np.deg2rad(x["lat"].to_numpy()))
        vT, noise = np.var(dT), np.var(dT - dR) / 2
        c = np.cov(dP, dT)[0, 1]
        out[f"resp_{q}_agg_ratio"] = float((w * dP).sum() / (w * dT).sum())
        out[f"resp_{q}_slope"] = float(c / vT)
        out[f"resp_{q}_slope_deatt"] = float(c / (vT - noise)) if vT > noise else None
        out[f"resp_{q}_noise_share"] = float(noise / vT)
    return out


def stage_nulls():
    cells = dev_cells()
    T_w, T_h = lev(mname("ssp370", TRUTH)), lev(mname("historical", TRUTH))
    R_w, R_h = lev(mname("ssp370", REPLICA)), lev(mname("historical", REPLICA))
    tb = (T_w.filter(pl.col("n_per_patch") > 0).select("Cell")
          .vstack(T_h.filter(pl.col("n_per_patch") > 0).select("Cell")).unique())
    cells = cells.join(tb, on="Cell")
    log(f"scored cells (dev, tree-bearing in the truth): {cells.height}")
    snap = lev(mname("historical", TRUTH), "_y2014")
    look = pl.concat([lev(mname("ssp245", s)) for s in TRAIN]).group_by("Cell").agg(
        [pl.col(q).mean() for q in PANEL])
    look_h = pl.concat([lev(mname("historical", s)) for s in TRAIN]).group_by("Cell").agg(
        [pl.col(q).mean() for q in PANEL])
    arms = {
        "ceiling": (R_w, R_h, "pass <= 1; area ratios within 0.05 of 1; aggregate response 0.8-1.2"),
        "persist_h": (T_h, T_h, "response EXACTLY 0 (harness check)"),
        "persist_2014": (snap, T_h, "small response; pass below ceiling"),
        "lookup_245": (look, look_h, "aggregate response ratio < 1 if ssp370 warms more than ssp245"),
    }
    rows = []
    for name, (pw, ph, expect) in arms.items():
        s = score(pw, ph, T_w, T_h, R_w, R_h, cells)
        rows.append(dict(split="GS370", baseline=name, expect=expect, **s))
        log(name, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}))
    df = pl.DataFrame(rows)
    df.write_csv(os.path.join(EVAL, "nulls_GS370.csv"))
    ph = df.filter(pl.col("baseline") == "persist_h")
    harness_ok = all(abs(ph[f"resp_{q}_agg_ratio"][0]) < 1e-12 for q in ("n_per_patch", "agb_per_stem"))
    log(f"HARNESS CHECK persist_h response == 0: {'PASS' if harness_ok else 'FAIL'}")


if __name__ == "__main__":
    os.makedirs(EVAL, exist_ok=True)
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    for s in (["levels", "nulls"] if st == "all" else st.split(",")):
        log(f"=== {s}")
        {"levels": stage_levels, "nulls": stage_nulls}[s]()
    log("=== DONE")
