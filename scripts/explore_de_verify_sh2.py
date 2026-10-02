#!/usr/bin/env python3
"""explore_de_verify_sh2.py — adversarial verifier for SH2 (exact rule library), line X Germany emulator.

Independent re-implementation (does NOT call the library's recovery/gate code; reads only params.json values and
the allometry coefficients) of:
  A. printed mort == min(1, sum) on non-hard rows; mort_age from Age-1; tolerant counter; c=5 => isdead;
     counter recursion within a window AND across the 2014 -> 2015 restart boundary (not tested by the builder);
     the "power" of the recursion gate (how many pairs carry a non-trivial c1 = c0 + 1 >= 2);
     strict (tol 0) formula failure rate for comparison.
  B. height allometry Type-1 R2 on ACCESS Historical s2 with the DEV-A coefficients, a self-fit, and an
     extended self-fit (+ ln LAI, ln fpc_ind, ln vegc, ln D95, ln Age, ln Longevity) to test the
     "information limit of (agb, Wooddens, SLA)" claim.
  C. the library's exclusion guard (calls rl.assert_usable on every registry member).
Writes /p/tmp/jamirp/X_de/_reports/verify_sh2_measure.json. Usage: explore_de_verify_sh2.py
"""
import json
import math
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XDE = "/p/tmp/jamirp/X_de"
DEV = f"{XDE}/ind_dev"
OUTJ = f"{XDE}/_reports/verify_sh2_measure.json"
P = json.load(open(f"{XDE}/shared/rules/params.json"))
PFT = {r["pft_id"]: r for r in P["pft"]}
KM = P["global"]["k_mort"]
KEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def arr(name):
    return np.array([PFT[k][name] for k in sorted(PFT)], dtype=np.float64)


WD1, WD2, LONG = arr("wdmort_1"), arr("wdmort_2"), arr("longevity_age")


def load(member):
    cols = ["Year", "Cell", "Patch", "Type", "ID", "SLA", "Wooddens", "Age", "isdead",
            "mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]
    df = pl.scan_parquet(f"{DEV}/{member}.parquet").filter(pl.col("Type") <= 6).select(cols).collect()
    t = df["Type"].to_numpy().astype(np.int64)
    wd = df["Wooddens"].to_numpy().astype(np.float64)
    mmax = 10.0 ** (WD1[t] + WD2[t] / (wd / 1e6))
    mn = df["mort_npp"].to_numpy().astype(np.float64)
    r = mn / mmax
    c_tol = np.minimum(np.maximum(0.0, np.ceil(r - 1.0 - 1e-4)), 5).astype(np.int64)
    c_strict = np.minimum(np.maximum(0.0, np.ceil(r - 1.0)), 5).astype(np.int64)
    return df.with_columns(pl.Series("c", c_tol), pl.Series("cs", c_strict), pl.Series("sat", mn >= 1.0))


def battery(df):
    o = {"n": df.height}
    mo, mn, ma, mw, mt = (df[c].to_numpy().astype(np.float64) for c in ["mort", "mort_npp", "mort_age", "mort_water", "mort_temp"])
    nh = mo < 1.0
    s = np.minimum(1.0, mn + ma + mw + mt)
    rel = np.abs(mo - s)[nh] / np.maximum(mo[nh], 1e-30)
    rel[(mo[nh] == 0) & (s[nh] == 0)] = 0
    o["mortsum_max_rel"] = float(rel.max())
    o["mortsum_n_gt_1e-5"] = int((rel > 1e-5).sum())
    t = df["Type"].to_numpy().astype(np.int64)
    age = df["Age"].to_numpy().astype(np.float64) - 1.0
    pa = np.minimum(1.0, -math.log(0.001) * 3.0 / LONG[t] * (age / LONG[t]) ** 2)
    ra = np.abs(ma - pa) / np.maximum(pa, 1e-30)
    ra[(ma == 0) & (pa == 0)] = 0
    o["mortage_max_rel"] = float(ra.max())
    # mort_age with the WRONG age basis (printed Age) — the gate must be able to fail
    pa2 = np.minimum(1.0, -math.log(0.001) * 3.0 / LONG[t] * ((age + 1) / LONG[t]) ** 2)
    o["mortage_wrong_basis_max_rel"] = float((np.abs(ma - pa2) / np.maximum(pa2, 1e-30)).max())
    c = df["c"].to_numpy()
    isd = df["isdead"].to_numpy()
    o["c5_n"] = int((c >= 5).sum())
    o["c5_dead_share"] = float(isd[c >= 5].mean())
    o["c_hist"] = {int(k): int((c == k).sum()) for k in range(6)}
    o["mort_water_pos_share"] = float((mw > 0).mean())
    o["dead_share"] = float(isd.mean())
    o["dead_with_mort_lt_1_share_of_dead"] = float(((isd == 1) & (mo < 1)).sum() / max((isd == 1).sum(), 1))
    return o


def recursion(a_df, b_df, label):
    """a = rows at y (alive), b = rows at y+1 (same identity key)."""
    a = a_df.filter(pl.col("isdead") == 0).select(KEY + ["Year", "c", "cs"]).with_columns((pl.col("Year").cast(pl.Int32) + 1).alias("Y1"))
    b = b_df.select(KEY + ["Year", "c", "cs", "Age", "sat"]).rename({"Year": "Y1", "c": "c1", "cs": "cs1"}).with_columns(pl.col("Y1").cast(pl.Int32))
    pr = a.join(b, on=KEY + ["Y1"], how="inner")
    assert pr.select(KEY + ["Y1"]).n_unique() == pr.height
    base = np.where(pr["Age"].to_numpy() - 1.0 == 1.0, 0, pr["c"].to_numpy())
    bases = np.where(pr["Age"].to_numpy() - 1.0 == 1.0, 0, pr["cs"].to_numpy())
    c1 = pr["c1"].to_numpy()
    cs1 = pr["cs1"].to_numpy()
    ok = ~pr["sat"].to_numpy()
    fail = ok & ~((c1 == 0) | (c1 == base + 1))
    fails = ok & ~((cs1 == 0) | (cs1 == bases + 1))
    o = {"label": label, "pairs": int(pr.height), "fail": int(fail.sum()), "fail_rate": float(fail.sum() / max(pr.height, 1)),
         "strict_fail": int(fails.sum()), "strict_fail_rate": float(fails.sum() / max(pr.height, 1)),
         "pairs_c1_0": int((c1 == 0).sum()), "pairs_c1_1": int((c1 == 1).sum()),
         "pairs_c1_ge2_consistent": int(((c1 >= 2) & (c1 == base + 1)).sum())}
    # a random-shuffle null for the recursion: permute c1 across pairs -> failure rate the gate would see
    rng = np.random.default_rng(1)
    c1p = rng.permutation(c1)
    o["null_shuffled_c1_fail_rate"] = float((ok & ~((c1p == 0) | (c1p == base + 1))).mean())
    # how many distinct years in the pairs
    o["years"] = [int(pr["Y1"].min()) - 1, int(pr["Y1"].max()) - 1] if pr.height else None
    return o


def allometry():
    m = "ACCESS-CM2_Historical_s2_h1985"
    df = (pl.scan_parquet(f"{DEV}/{m}.parquet").filter(pl.col("Type") == 1)
          .select("Height", "agb", "Wooddens", "SLA", "LAI", "fpc_ind", "vegc", "D95", "Age", "Longevity").collect())
    df = df.filter(pl.all_horizontal([pl.col(c) > 0 for c in df.columns]))
    y = np.log(df["Height"].to_numpy().astype(np.float64))
    L = {c: np.log(df[c].to_numpy().astype(np.float64)) for c in df.columns if c != "Height"}
    co = pl.read_parquet(f"{XDE}/shared/rules/height_allometry.parquet").filter(
        (pl.col("split") == "DEV-A") & (pl.col("cellset") == "dev_f1234") & (pl.col("Type") == 1)).row(0, named=True)
    pred = co["b0"] + co["b_agb"] * L["agb"] + co["b_wd"] * L["Wooddens"] + co["b_sla"] * L["SLA"]
    sst = float(((y - y.mean()) ** 2).sum())

    def r2(res):
        return 1 - float(res @ res) / sst

    out = {"member": m, "n": int(y.size), "r2_devA_coef": r2(y - pred)}
    for name, feats in [("self_base", ["agb", "Wooddens", "SLA"]),
                        ("self_plus_LAI_fpc", ["agb", "Wooddens", "SLA", "LAI", "fpc_ind"]),
                        ("self_plus_vegc", ["agb", "Wooddens", "SLA", "vegc"]),
                        ("self_all", ["agb", "Wooddens", "SLA", "LAI", "fpc_ind", "vegc", "D95", "Age", "Longevity"])]:
        X = np.column_stack([np.ones(y.size)] + [L[f] for f in feats])
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        res = y - X @ b
        out[name] = {"r2": r2(res), "rmse_log": float(np.sqrt(np.mean(res ** 2)))}
    return out


def exclusion():
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import explore_de_sh_rules as rl
    m = pl.read_parquet(f"{XDE}/shared/registry/members.parquet")
    refused, allowed = [], []
    for mem, win in m.select("member", "win").iter_rows():
        try:
            rl.assert_usable(mem)
            allowed.append((mem, win))
        except rl.ExcludedMemberError:
            refused.append((mem, win))
    return {"n_refused": len(refused), "refused_wins": sorted({w for _, w in refused}),
            "n_allowed": len(allowed), "allowed_wins": sorted({w for _, w in allowed})}


def main():
    res = {}
    res["exclusion"] = exclusion()
    log("exclusion", res["exclusion"])
    res["allometry"] = allometry()
    log("allometry", res["allometry"])
    for gcm, scen, seed in [("MPI-ESM1-2-HR", "ssp370", 1), ("ACCESS-CM2", "ssp370", 2)]:
        h = load(f"{gcm}_Historical_s{seed}_h1985")
        w = load(f"{gcm}_{scen}_s{seed}_w2015")
        tag = f"{gcm}_{scen}_s{seed}"
        res[tag] = {"battery_h1985": battery(h), "battery_w2015": battery(w),
                    "rec_within_w2015": recursion(w, w, "within w2015"),
                    "rec_within_h1985": recursion(h, h, "within h1985"),
                    "rec_boundary_2014_2015": recursion(h.filter(pl.col("Year") == 2014), w.filter(pl.col("Year") == 2015), "2014->2015")}
        # identity continuity across the boundary: share of 2014 living trees found in 2015
        a = h.filter((pl.col("Year") == 2014) & (pl.col("isdead") == 0)).select(KEY).unique()
        b = w.filter(pl.col("Year") == 2015).select(KEY).unique()
        res[tag]["boundary_identity_share_found"] = float(a.join(b, on=KEY, how="semi").height / max(a.height, 1))
        log(tag, json.dumps(res[tag], default=float)[:3000])
        json.dump(res, open(OUTJ, "w"), indent=1, default=float)
    json.dump(res, open(OUTJ, "w"), indent=1, default=float)
    log("VERIFY_SH2 DONE ->", OUTJ)


if __name__ == "__main__":
    main()
