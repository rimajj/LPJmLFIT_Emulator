"""explore_de_recruit_attrib.py — LINE X, Germany emulator: which input makes the recruit head over-recruit?

Context (explore_de_recruit_drift.py, 2026-10-02): in the TAB free run the stand never matures (mean tree agb stays
~500 where the original reaches ~900, cover 0.44-0.46 vs 0.48) and recruits stay at the young-forest rate (0.34-0.37
vs 0.21-0.24 per patch-year). Is the head responding to the open canopy (an honest response to a wrong stand), or to a
self-reinforcing input such as the cell's stem density (more stems -> more recruits -> more stems)?

Method (read-only; no model run):
  1. rebuild the SH13 recruit-head state features from a printed roster (one function, applied to BOTH sources):
     n_live_y, sum_fpc_y, sum_agb_y, patch_lai_y, fpc_surv_y1, L0, L1, L2_5, L6_20, cell_stems_per_patch,
     cell_share_t0..6; cell-year climate + n_eligible_pft_y1 and the grass columns come from the ORIGINAL's stored
     feature table (the free run's grass is not saved — that is the one input not swapped, stated in the output).
  2. GATE: on the original's roster the rebuilt features must equal the stored SH13 feature table (max rel diff
     < 1e-5, float32 storage) and the head's summed mean must agree to < 1e-4 relative. A failed gate stops the run.
  3. sum of head means: on the original (expect ~ observed recruits), on the free run (expect ~ the free run's own
     recruits), and on the original with ONE feature group replaced by the free run's (cell groups joined by Cell;
     patch groups paired by patch index, which is a random pairing because patches are exchangeable).
Pre-registered reading: if swapping the patch canopy state (C) alone carries most of the gap, the head is honest and
the fix is the stand (growth); if the cell density group (A) carries a large share, there is a feedback channel in the
head itself that a free run amplifies, and the fix is in the head's inputs.

Usage:  python explore_de_recruit_attrib.py [--arm tabAL] [--kappa 1.0] [--chunks 0,1] [--years 1995,2005,...]
Writes /p/tmp/jamirp/X_de/shared/eval/recruit_attrib_<arm>.csv
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_sh_patchheads as ph  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
RUN = "ACCESS-CM2_s1_1985-2044_ssp126+ssp245+ssp370_actual_r1"
# the raw (Cell, Patch, Type, ID) key has ~2 800 duplicates in 569 M tree rows; adding the immutable traits SLA and
# Wooddens removes all of them (round-1 conversion gate) — with the raw key the loss-history gate fails on 2-6 patches
KEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]
COLS = ["Year", "Cell", "Patch", "Type", "ID", "SLA", "Wooddens", "isdead", "fpc_ind", "agb", "LAI"]
NPATCH = 250
NLAG = 20
GROUPS = {
    "A_cell_density": ["cell_stems_per_patch"],
    "B_cell_composition": [f"cell_share_t{k}" for k in range(7)],
    "C_patch_canopy": ["n_live_y", "sum_fpc_y", "sum_agb_y", "patch_lai_y"],
    "D_this_step_loss": ["fpc_surv_y1", "L0"],
    "E_loss_history": ["L1", "L2_5", "L6_20"],
    "C1_n_live": ["n_live_y"],
    "C2_sum_fpc": ["sum_fpc_y"],
    "C3_sum_agb": ["sum_agb_y"],
    "C4_patch_lai": ["patch_lai_y"],
    "C2+C4_cover": ["sum_fpc_y", "patch_lai_y"],
}


def roster_arm(arm, chunks, leg):
    fs = []
    for c in chunks:
        d = os.path.join(XDE, "runs", arm, RUN, f"chunk_{c:03d}")
        fs += sorted(glob.glob(os.path.join(d, "*_Historical.parquet"))) + sorted(
            glob.glob(os.path.join(d, f"*_{leg}.parquet")))
    return pl.concat([pl.read_parquet(f, columns=COLS) for f in fs], how="vertical_relaxed").filter(
        pl.col("Type") <= 6)


def members(leg):
    m = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == "ACCESS-CM2") & (pl.col("seed") == 1) & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", leg]))
    return {r["scen"]: r for r in m.iter_rows(named=True)}


def roster_truth(cells, leg):
    ms = members(leg)
    parts = [pl.scan_parquet(ms[s]["ind_dev_path"]).select(COLS) for s in ("Historical", leg)]
    return (pl.concat(parts, how="vertical_relaxed")
            .filter(pl.col("Cell").is_in(cells) & (pl.col("Type") <= 6)).collect())


def features(R: pl.DataFrame, years: list[int], cells: list[int]) -> pl.DataFrame:
    """SH13 recruit-head state features rebuilt from a printed roster (SH4 definitions)."""
    y0 = int(R["Year"].min())
    by = {y: g for (y,), g in R.partition_by("Year", as_dict=True).items()}
    uni = pl.DataFrame({"Cell": np.repeat(cells, NPATCH).astype(np.int16),
                        "Patch": np.tile(np.arange(NPATCH), len(cells)).astype(np.int16)})
    pk = ["Cell", "Patch"]

    def live(y):
        return by[y].filter(pl.col("isdead") == 0)

    def loss_during(t):  # fpc at t-1 of stems living at t-1 that are flagged dead or absent at t
        lv = live(t - 1).select(*KEY, "fpc_ind")
        surv = live(t).select(KEY).with_columns(_s=pl.lit(True))
        j = lv.join(surv, on=KEY, how="left").with_columns(_s=pl.col("_s").fill_null(False))
        g = j.group_by(pk).agg(_tot=pl.col("fpc_ind").cast(pl.Float64).sum(),
                               loss=(pl.col("fpc_ind").cast(pl.Float64) * ~pl.col("_s")).sum())
        g = g.with_columns(frac=pl.when(pl.col("_tot") > 0).then(pl.col("loss") / pl.col("_tot")).otherwise(0.0))
        return uni.join(g.select(*pk, "frac", "loss"), on=pk, how="left").with_columns(
            pl.col("frac", "loss").fill_null(0.0))

    out = []
    for y in years:
        L = live(y)
        st = L.group_by(pk).agg(n_live_y=pl.len().cast(pl.Float64),
                                sum_fpc_y=pl.col("fpc_ind").cast(pl.Float64).sum(),
                                sum_agb_y=pl.col("agb").cast(pl.Float64).sum(),
                                patch_lai_y=(pl.col("LAI").cast(pl.Float64) * pl.col("fpc_ind").cast(pl.Float64)).sum())
        D = uni.join(st, on=pk, how="left").with_columns(
            pl.col("n_live_y", "sum_fpc_y", "sum_agb_y", "patch_lai_y").fill_null(0.0))
        ly1 = loss_during(y + 1)
        D = D.join(ly1.select(*pk, loss_y1="loss"), on=pk, how="left")
        lags = []
        for k in range(NLAG):
            t = y - k
            lags.append(loss_during(t)["frac"].to_numpy() if t >= y0 + 1 else np.full(uni.height, np.nan))
        M = np.column_stack(lags)
        D = D.with_columns(
            fpc_surv_y1=(pl.col("sum_fpc_y") - pl.col("loss_y1")).clip(lower_bound=0.0),
            L0=pl.when(pl.col("sum_fpc_y") > 0).then(pl.col("loss_y1") / pl.col("sum_fpc_y")).otherwise(0.0),
            L1=pl.Series(M[:, 0]), L2_5=pl.Series(ph._nansum_or_nan(M[:, 1:5])),
            L6_20=pl.Series(ph._nansum_or_nan(M[:, 5:20])))
        n = L.group_by("Cell").agg(_n=pl.len().cast(pl.Float64))
        sh = L.group_by("Cell", "Type").agg(_k=pl.len().cast(pl.Float64))
        ce = n.with_columns(cell_stems_per_patch=pl.col("_n") / NPATCH)
        for k in range(7):
            ce = ce.join(sh.filter(pl.col("Type") == k).select("Cell", pl.col("_k").alias(f"_k{k}")), on="Cell",
                         how="left").with_columns((pl.col(f"_k{k}").fill_null(0.0) / pl.col("_n"))
                                                  .alias(f"cell_share_t{k}")).drop(f"_k{k}")
        D = D.join(ce.drop("_n"), on="Cell", how="left").with_columns(
            pl.col("cell_stems_per_patch", *[f"cell_share_t{k}" for k in range(7)]).fill_null(0.0))
        out.append(D.with_columns(Year=pl.lit(y, pl.Int16)).drop("loss_y1"))
    return pl.concat(out)


def stored(leg, years, cells):
    """The original's stored SH13 feature rows (state + climate + grass + observed recruits)."""
    ms = members(leg)
    parts = []
    for s in ("Historical", leg):
        f = os.path.join(ph.FEAT, f"{ms[s]['member']}.parquet")
        parts.append(pl.scan_parquet(f).filter(pl.col("Year").is_in(years) & pl.col("Cell").is_in(cells)))
    return pl.concat(parts, how="diagonal_relaxed").collect().sort("Year", "Cell", "Patch")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="tabAL")
    ap.add_argument("--kappa", type=float, default=1.0)
    ap.add_argument("--chunks", default="0,1")
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--years", default="1995,2005,2020,2030,2040")
    a = ap.parse_args()
    years = [int(y) for y in a.years.split(",")]
    H = ph.load_heads("DEV-A")
    meta = H.meta["recruit"]
    state_cols = meta["state_feats"]
    A = roster_arm(a.arm, [int(c) for c in a.chunks.split(",")], a.leg)
    cells = sorted(A["Cell"].unique().to_list())
    T = roster_truth(cells, a.leg)
    print(f"{a.arm}: {A.height} rows; truth {T.height} rows; {len(cells)} cells", flush=True)
    S = stored(a.leg, years, cells)
    assert S.select("Year", "Cell", "Patch").n_unique() == S.height, "duplicate stored keys"
    Ft = features(T, years, cells).sort("Year", "Cell", "Patch")
    Fa = features(A, years, cells).sort("Year", "Cell", "Patch")
    assert Ft.height == S.height == Fa.height, (Ft.height, S.height, Fa.height)
    rebuilt = [c for c in state_cols if c in Ft.columns]
    other = [c for c in S.columns if c not in rebuilt]
    # ---- gate: rebuilt == stored on the original
    gate = {}
    yr0 = S["Year"].to_numpy()
    for c in rebuilt:
        x, s = Ft[c].cast(pl.Float64).to_numpy(), S[c].cast(pl.Float64).to_numpy()
        both = ~(np.isnan(x) | np.isnan(s))
        gate[c] = {"max_rel": float(np.max(np.abs(x[both] - s[both]) / np.maximum(np.abs(s[both]), 1e-6)))
                   if both.any() else 0.0, "nan_mismatch": int(np.sum(np.isnan(x) != np.isnan(s)))}
    base = S.select(other)
    XT = pl.concat([base, Ft.select(rebuilt)], how="horizontal")
    mu_stored = H.recruit_mean(S, kappa=a.kappa)
    mu_T = H.recruit_mean(XT, kappa=a.kappa)
    gate["_mu_sum_rel"] = float(abs(mu_T.sum() / mu_stored.sum() - 1.0))
    bad = {c: v for c, v in gate.items() if c != "_mu_sum_rel" and (v["max_rel"] > 1e-5 or v["nan_mismatch"])}
    print("GATE rebuilt-vs-stored:", json.dumps(gate), flush=True)
    for c in ("L1", "L2_5", "L6_20"):
        x, s_ = Ft[c].cast(pl.Float64).to_numpy(), S[c].cast(pl.Float64).to_numpy()
        d = np.abs(x - s_) > 1e-5 * np.maximum(np.abs(s_), 1e-3)
        print(c, {int(y): (int(d[yr0 == y].sum()), float(np.nanmean(x[yr0 == y])), float(np.nanmean(s_[yr0 == y])))
                  for y in years}, flush=True)
    if bad or gate["_mu_sum_rel"] > 1e-4:
        print("GATE FAILED:", json.dumps(bad))
        sys.exit(2)
    # ---- attribution
    XA = pl.concat([base, Fa.select(rebuilt)], how="horizontal")
    rows = []
    obs = S["n_recruit_y1"].cast(pl.Float64).to_numpy()
    yr = S["Year"].to_numpy()

    def add(label, X):
        mu = H.recruit_mean(X, kappa=a.kappa)
        for y in years + [None]:
            m = np.ones(len(mu), bool) if y is None else (yr == y)
            rows.append({"swap": label, "Year": y if y is not None else 0, "mu_pp": float(mu[m].mean()),
                         "obs_truth_pp": float(obs[m].mean())})

    add("none (original stand)", XT)
    add("ALL tree-derived (free-run stand, original grass)", XA)
    for g, cols in GROUPS.items():
        add(g, XT.with_columns([XA[c] for c in cols]))
        add(f"all except {g}", XA.with_columns([XT[c] for c in cols]))
    R = pl.DataFrame(rows)
    # realised free-run recruits per patch-year at the same years (first appearance of a key, as in the eval)
    seen, prev, realised = None, None, {}
    for y in sorted(A["Year"].unique().to_list()):
        cur = A.filter(pl.col("Year") == y).select(KEY)
        if prev is not None and (y - 1) in years:
            new = cur.join(prev, on=KEY, how="anti").join(seen, on=KEY, how="anti")
            realised[y - 1] = new.height / (len(cells) * NPATCH)
        seen = cur if seen is None else pl.concat([seen, cur]).unique()
        prev = cur
    R = R.join(pl.DataFrame({"Year": list(realised), "arm_realised_pp": list(realised.values())}), on="Year",
               how="left")
    out = os.path.join(XDE, "shared", "eval", f"recruit_attrib_{a.arm}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_width_chars(220)
    P = R.pivot(on="Year", index="swap", values="mu_pp")
    print(P.with_columns(pl.exclude("swap").round(4)))
    print("observed original:", R.filter(pl.col("swap") == "none (original stand)").select("Year", "obs_truth_pp"))
    print("realised free run:", realised)
    print("wrote", out)


if __name__ == "__main__":
    main()
