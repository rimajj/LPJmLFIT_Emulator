"""Adversarial re-measurement of the Germany `ind` transition anatomy (line X, exploration).

Independent code (does NOT import explore_de_anatomy.py). Reads the converted full-block parquet
/p/tmp/jamirp/X_de/ind/<gcm>/<scen>/s<seed>/<window>/cb=NN/part-0.parquet on the subsample
Cell % 10 == 5 (disjoint from the anatomy agent's Cell % 10 == 0 dev subset), and writes one JSON per
member-window to /p/tmp/jamirp/X_de/anatomy_verify/.

usage:  python explore_de_anatomy_verify.py run <gcm> <scen> <seed> <window> [<prev_window_for_continuity>]
        python explore_de_anatomy_verify.py census <gcm> <scen> <seed> <window>
"""

import glob
import json
import math
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IND = "/p/tmp/jamirp/X_de/ind"
OUT = "/p/tmp/jamirp/X_de/anatomy_verify"
MOD, REM = int(os.environ.get("VERIFY_MOD", "10")), 5
OUT = OUT + os.environ.get("VERIFY_OUTSUFFIX", "")

# [SOURCE] par/pft_lpjmlfit.js via cpp -P (fcd3a30): resist, wooddens/D95max intervals; wdmort from
# test/testitems/references/S_pft_mortality_params.csv; longevity ("age") 400 except id 5 = 125.
RESIST = {0: 0.12, 1: 0.12, 2: 0.5, 3: 0.3, 4: 0.12, 5: 0.3, 6: 0.12}
WD1 = {0: -2.458, 1: -2.625, 2: -2.625, 3: -2.465, 4: -2.43, 5: -2.43, 6: -2.43}
WD2 = {0: 0.129, 1: 0.236, 2: 0.236, 3: 0.148, 4: 0.143, 5: 0.143, 6: 0.143}
LONG = {0: 400.0, 1: 400.0, 2: 400.0, 3: 400.0, 4: 400.0, 5: 125.0, 6: 400.0}
WD_IV = {0: (70000, 650000), 1: (117000, 418500), 2: (145600, 637000), 3: (147870, 637000),
         4: (117000, 418500), 5: (147870, 418500), 6: (117000, 418500)}
D95_IV = {0: (51, 1800), 1: (51, 1000), 2: (51, 1000), 3: (51, 500), 4: (51, 500), 5: (51, 500),
          6: (51, 300)}
KMORTBG_LNF = -math.log(0.001)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def mapexpr(col, d, default=None):
    return pl.col(col).replace_strict(d, default=default, return_dtype=pl.Float64)


def load(gcm, scen, seed, win):
    root = f"{IND}/{gcm}/{scen}/s{seed}/{win}"
    files = sorted(glob.glob(f"{root}/cb=*/part-0.parquet"))
    assert files, root
    df = pl.scan_parquet(files).filter(pl.col("Cell") % MOD == REM).collect()
    return df


def add_keys(tr):
    return tr.with_columns(
        kS=(pl.col("SLA").cast(pl.Float64) * 1e9).round().cast(pl.Int64),
        kW=(pl.col("Wooddens").cast(pl.Float64) * 10).round().cast(pl.Int64),
    )


RAW = ["Cell", "Patch", "Type", "ID"]
TK = RAW + ["kS", "kW"]


def add_counter(tr):
    mmax = (10.0 ** (mapexpr("Type", WD1) + mapexpr("Type", WD2)
                     / (pl.col("Wooddens").cast(pl.Float64) / 1e6)))
    r = pl.col("mort_npp").cast(pl.Float64) / mmax
    tr = tr.with_columns(r=r)
    tr = tr.with_columns(
        c_their=pl.max_horizontal(pl.lit(0), (pl.col("r") - 1e-9).ceil() - 1).cast(pl.Int32),
        c_rob=pl.max_horizontal(pl.lit(0), (pl.col("r") - 1 - 1e-4).ceil()).cast(pl.Int32),
    )
    return tr


def q(s, qs=(0.0, 0.01, 0.05, 0.5, 0.95, 0.99, 1.0)):
    s = s.drop_nulls()
    if s.len() == 0:
        return None
    return {str(x): float(s.quantile(x)) for x in qs}


def census(df, years):
    expected = set(range(REM, 9067, MOD)) - {31, 32}
    cy = df.group_by(["Year", "Cell"]).len()
    out = {}
    holes = 0
    per = {}
    for y in years:
        cells = set(cy.filter(pl.col("Year") == y)["Cell"].to_list())
        miss = expected - cells
        holes += len(miss)
        per[int(y)] = len(cells)
    out["expected_cells"] = len(expected)
    out["cells_per_year"] = per
    out["census_holes"] = holes
    return out


def run(gcm, scen, seed, win, prev_win=None):
    t0 = time.time()
    label = f"{gcm}_{scen}_s{seed}_{win}"
    R = {"member": label, "subsample": f"Cell % {MOD} == {REM}"}
    df = load(gcm, scen, seed, win)
    log("loaded", label, df.height)
    years = sorted(df["Year"].unique().to_list())
    R["years"] = [int(years[0]), int(years[-1]), len(years)]
    R["census"] = census(df, years)
    # grass rows
    gr = df.filter(pl.col("Type") > 6)
    gp = gr.group_by(["Year", "Cell", "Patch"]).agg(n=pl.len(), types=pl.col("Type").unique())
    R["grass"] = {
        "rows_per_patch_hist": {str(k): int(v) for k, v in
                                gp.group_by("n").len().sort("n").iter_rows()},
        "patches_per_cellyear": q(gp.group_by(["Year", "Cell"]).len()["len"].cast(pl.Float64)),
        "type_counts": {str(k): int(v) for k, v in gr.group_by("Type").len().sort("Type").iter_rows()},
        "grass_ID_Height_Age_nonzero": int(gr.filter((pl.col("ID") != 0) | (pl.col("Height") != 0)
                                                     | (pl.col("Age") != 0)).height),
    }
    tr = df.filter(pl.col("Type") <= 6)
    del df
    tr = add_keys(tr)
    tr = tr.with_columns(
        n_raw=pl.len().over(["Year"] + RAW),
        n_tk=pl.len().over(["Year"] + TK),
        n_notype=pl.len().over(["Year", "Cell", "Patch", "ID"]),
    )
    # ---------------- duplicates
    dy = tr.group_by("Year").agg(
        rows=pl.len(),
        dup_raw_rows=(pl.col("n_raw") > 1).sum(),
        dup_tk_rows=(pl.col("n_tk") > 1).sum(),
        dup_notype_rows=(pl.col("n_notype") > 1).sum(),
    ).sort("Year")
    dd = tr.filter(pl.col("n_raw") > 1)
    dgrp = dd.group_by(["Year"] + RAW).agg(
        nAge=pl.col("Age").n_unique(), nSLA=pl.col("kS").n_unique(),
        ndead=pl.col("isdead").sum(), n=pl.len(), types=pl.col("Type").first())
    R["dups"] = {
        "per_year_raw_dup_rows": dict(zip(map(str, dy["Year"].to_list()),
                                          dy["dup_raw_rows"].to_list(), strict=True)),
        "total_raw_dup_rows": int(dy["dup_raw_rows"].sum()),
        "total_tk_dup_rows": int(dy["dup_tk_rows"].sum()),
        "total_notype_dup_rows": int(dy["dup_notype_rows"].sum()),
        "groups": dgrp.height,
        "groups_age_differs": int((dgrp["nAge"] > 1).sum()),
        "groups_sla_differs": int((dgrp["nSLA"] > 1).sum()),
        "group_type_counts": {str(k): int(v) for k, v in dgrp.group_by("types").len().iter_rows()},
        "dup_row_age_q": q(dd["Age"].cast(pl.Float64)),
    }
    log("dups done", R["dups"]["total_raw_dup_rows"], R["dups"]["total_tk_dup_rows"])
    # ---------------- counter + hazard checks
    tr = add_counter(tr)
    tr = tr.with_columns(
        hard=(pl.col("mort") >= 0.999999),
        msum=pl.min_horizontal(pl.lit(1.0), (pl.col("mort_npp") + pl.col("mort_age")
                                             + pl.col("mort_water") + pl.col("mort_temp")).cast(pl.Float64)),
        mage_pred=pl.min_horizontal(pl.lit(1.0), KMORTBG_LNF * 3.0 / mapexpr("Type", LONG)
                                    * ((pl.col("Age").cast(pl.Float64) - 1) / mapexpr("Type", LONG)) ** 2),
        mage_pred_noshift=pl.min_horizontal(pl.lit(1.0), KMORTBG_LNF * 3.0 / mapexpr("Type", LONG)
                                            * (pl.col("Age").cast(pl.Float64) / mapexpr("Type", LONG)) ** 2),
        resist=mapexpr("Type", RESIST),
    )
    first = years[0]
    mc = tr.with_columns(
        first=(pl.col("Year") == first),
        sum_viol=((~pl.col("hard")) & ((pl.col("mort") - pl.col("msum")).abs()
                                       > 2e-5 * pl.max_horizontal(pl.lit(1e-3), pl.col("msum")))),
        range_viol=pl.any_horizontal([(pl.col(c) < 0) | (pl.col(c) > 1) | pl.col(c).is_nan()
                                      for c in ["mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]]),
        age_relerr=((pl.col("mort_age") - pl.col("mage_pred")).abs()
                    / pl.max_horizontal(pl.lit(1e-12), pl.col("mage_pred"))),
        age_relerr_ns=((pl.col("mort_age") - pl.col("mage_pred_noshift")).abs()
                       / pl.max_horizontal(pl.lit(1e-12), pl.col("mage_pred_noshift"))),
    ).group_by("first").agg(
        n=pl.len(), sum_viol=pl.col("sum_viol").sum(), range_viol=pl.col("range_viol").sum(),
        age_relerr_q999=pl.col("age_relerr").filter(pl.col("mort_age") > 1e-6).quantile(0.999),
        age_relerr_max=pl.col("age_relerr").filter(pl.col("mort_age") > 1e-6).max(),
        age_relerr_ns_med=pl.col("age_relerr_ns").filter(pl.col("mort_age") > 1e-6).median(),
        npp_eq1=(pl.col("mort_npp") >= 0.999999).sum(),
        hard_not_dead=(pl.col("hard") & (pl.col("isdead") == 0)).sum(),
    )
    R["mort_checks"] = {("first_year" if r["first"] else "other_years"): {k: (float(v) if v is not None else None) for k, v in r.items() if k != "first"} for r in mc.iter_rows(named=True)}
    # counter bands
    rr = tr["r"]
    bands = {"(0.8334,1.6666)": ((rr > 0.8334) & (rr < 1.6666)), "(2.0001,2.4999)": ((rr > 2.0001) & (rr < 2.4999)),
             "(3.0001,3.3333)": ((rr > 3.0001) & (rr < 3.3333)), "(4.0001,4.1666)": ((rr > 4.0001) & (rr < 4.1666)),
             ">6.0001": (rr > 6.0001), "(5.0001,6)_c5": ((rr > 5.0001) & (rr <= 6.0001))}
    R["counter"] = {
        "band_counts": {k: int(v.sum()) for k, v in bands.items()},
        "rows": tr.height,
        "c_hist": {str(k): int(v) for k, v in tr.group_by("c_rob").len().sort("c_rob").iter_rows()},
        "c_their_ne_rob": int((tr["c_their"] != tr["c_rob"]).sum()),
        "c5_rows": int((tr["c_rob"] >= 5).sum()),
        "c5_not_dead": int(((tr["c_rob"] >= 5) & (tr["isdead"] == 0)).sum()),
        "c5_not_hard": int(((tr["c_rob"] >= 5) & (~tr["hard"])).sum()),
        "near_integer_r": int((((rr - rr.round()).abs() < 2e-5) & (rr > 0.5)).sum()),
        "prev_c_ge1_live": float(tr.filter(pl.col("isdead") == 0)["c_rob"].ge(1).mean()),
    }
    log("counter", R["counter"]["band_counts"], R["counter"]["c_hist"])
    # ---------------- hazard / fire accounting per year
    hz = tr.group_by("Year").agg(
        n=pl.len(), deaths=pl.col("isdead").sum(), hazard=pl.col("mort").cast(pl.Float64).sum(),
        hard=pl.col("hard").sum(), hard_dead=(pl.col("hard") & (pl.col("isdead") == 1)).sum(),
        floor=((1 - pl.col("resist")) * 0.001 * (1 - pl.col("mort").cast(pl.Float64))).sum(),
    ).sort("Year").with_columns(resid=pl.col("deaths") - pl.col("hazard") - pl.col("floor"))
    tot = hz.select(pl.all().exclude("Year").sum()).row(0, named=True)
    R["hazard"] = {
        "totals": {k: float(v) for k, v in tot.items()},
        "share_hazard": tot["hazard"] / tot["deaths"],
        "share_hard": tot["hard"] / tot["deaths"],
        "share_floor": tot["floor"] / tot["deaths"],
        "share_resid": tot["resid"] / tot["deaths"],
        "per_year": hz.to_dicts(),
    }
    # calibration of printed hazard by bin (non-hard)
    nh = tr.filter(~pl.col("hard"))
    cal = nh.with_columns(b=pl.col("mort").cast(pl.Float64).cut([1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3])).group_by("b").agg(
        n=pl.len(), mort_mean=pl.col("mort").mean(), death_rate=pl.col("isdead").mean()).sort("b")
    R["hazard"]["calibration_nonhard"] = [{k: (str(v) if k == "b" else float(v)) for k, v in r.items()} for r in cal.iter_rows(named=True)]
    # fire-by-resist test: excess death rate over printed hazard, per Type, non-hard rows
    ft = nh.group_by("Type").agg(n=pl.len(), deaths=pl.col("isdead").sum(),
                                  hz=pl.col("mort").cast(pl.Float64).sum(),
                                  expo=(1 - pl.col("mort").cast(pl.Float64)).sum()).sort("Type")
    ft = ft.with_columns(excess_rate=(pl.col("deaths") - pl.col("hz")) / pl.col("expo"),
                         one_minus_resist=1 - mapexpr("Type", RESIST))
    ft = ft.with_columns(f_implied=pl.col("excess_rate") / pl.col("one_minus_resist"))
    R["fire_by_type_pooled"] = ft.to_dicts()
    # matched within cell-year: beech (3) vs conifer group (1,4,6 resist .12) and vs type 2
    def grp_rate(sub):
        return sub.group_by(["Year", "Cell"]).agg(
            d=pl.col("isdead").sum(), h=pl.col("mort").cast(pl.Float64).sum(),
            e=(1 - pl.col("mort").cast(pl.Float64)).sum())
    b = grp_rate(nh.filter(pl.col("Type") == 3))
    matched = {}
    for name, sel in {"conifer_146": [1, 4, 6], "type2": [2], "type5": [5], "type0": [0]}.items():
        o = grp_rate(nh.filter(pl.col("Type").is_in(sel)))
        j = b.join(o, on=["Year", "Cell"], suffix="_o")
        if j.height == 0:
            continue
        eb = (j["d"].sum() - j["h"].sum()) / j["e"].sum()
        eo = (j["d_o"].sum() - j["h_o"].sum()) / j["e_o"].sum()
        rexp = (1 - np.mean([RESIST[t] for t in sel])) / (1 - RESIST[3])
        matched[name] = {"cellyears": j.height, "beech_excess": float(eb), "other_excess": float(eo),
                         "ratio_other_over_beech": float(eo / eb) if eb != 0 else None,
                         "ratio_expected_if_fire": float(rexp), "other_deaths": int(j["d_o"].sum())}
    R["fire_by_type_matched_cellyear"] = matched
    log("hazard", R["hazard"]["share_hazard"], R["hazard"]["share_hard"], matched)
    # ---------------- pairing y -> y+1
    cols = TK + ["Year", "Age", "isdead", "Height", "agb", "vegc", "D95max", "minwscal", "Longevity",
                 "beta_root", "c_rob", "c_their", "mort", "n_raw", "n_tk"]
    cur = tr.select(cols)
    nxt = tr.select(TK + ["Year", "Age", "isdead", "Height", "agb", "vegc", "D95max", "minwscal",
                          "Longevity", "beta_root", "c_rob", "c_their", "n_tk"]).with_columns(Year=pl.col("Year") - 1)
    nxt = nxt.rename({c: c + "_n" for c in nxt.columns if c not in TK + ["Year"]})
    cur = cur.filter((pl.col("Year") < years[-1]) & (pl.col("n_tk") == 1))
    nxt = nxt.filter(pl.col("n_tk_n") == 1)
    j = cur.join(nxt, on=TK + ["Year"], how="left")
    j = j.with_columns(matched=pl.col("Age_n").is_not_null())
    live = j.filter(pl.col("isdead") == 0)
    dead = j.filter(pl.col("isdead") == 1)
    m = live.filter(pl.col("matched"))
    trait_ok = ((pl.col("D95max") == pl.col("D95max_n")) & (pl.col("minwscal") == pl.col("minwscal_n"))
                & (pl.col("Longevity") == pl.col("Longevity_n")) & (pl.col("beta_root") == pl.col("beta_root_n")))
    fy = live.group_by("Year").agg(n=pl.len(), alive=(pl.col("matched") & (pl.col("isdead_n") == 0)).sum(),
                                    dies=(pl.col("matched") & (pl.col("isdead_n") == 1)).sum(),
                                    absent=(~pl.col("matched")).sum()).sort("Year")
    fy = fy.with_columns(f_alive=pl.col("alive") / pl.col("n"), f_dies=pl.col("dies") / pl.col("n"),
                         f_absent=pl.col("absent") / pl.col("n"))
    ab = live.filter(~pl.col("matched"))
    R["pairing"] = {
        "live_rows_y": live.height,
        "pairs": m.height,
        "age_plus1_frac": float((m["Age_n"] == m["Age"] + 1).mean()),
        "age_fail": int((m["Age_n"] != m["Age"] + 1).sum()),
        "trait4_ok_frac": float(m.select(trait_ok.mean()).item()),
        "dead_y_seen_at_y1": int(dead["matched"].sum()),
        "dead_y_rows": dead.height,
        "fate_totals": {"alive": int(fy["alive"].sum()), "dies": int(fy["dies"].sum()), "absent": int(fy["absent"].sum())},
        "fate_frac_range": {c: [float(fy[c].min()), float(fy[c].max())] for c in ["f_alive", "f_dies", "f_absent"]},
        "fate_frac_mean": {c: float(fy[c].mean()) for c in ["f_alive", "f_dies", "f_absent"]},
        "absent_height_q": q(ab["Height"].cast(pl.Float64)),
        "absent_H_lt_5p5_frac": float((ab["Height"] < 5.5).mean()) if ab.height else None,
        "absent_H_ge_10": int((ab["Height"] >= 10).sum()),
        "absent_c_hist": {str(k): int(v) for k, v in ab.group_by("c_rob").len().sort("c_rob").iter_rows()},
        "absent_rawdup": int((ab["n_raw"] > 1).sum()),
    }
    # absent: reappear later?
    keys_by_year = tr.select(TK + ["Year"]).unique()
    abk = ab.select(TK + ["Year"]).rename({"Year": "y0"})
    later = abk.join(keys_by_year, on=TK, how="inner").filter(pl.col("Year") > pl.col("y0") + 1)
    reap = later.group_by(TK + ["y0"]).agg(gap=(pl.col("Year").min() - pl.col("y0").first()))
    R["pairing"]["absent_reappear_frac"] = reap.height / max(1, ab.height)
    R["pairing"]["absent_reappear_gap_q"] = q(reap["gap"].cast(pl.Float64)) if reap.height else None
    # raw-key pairing (duplicates dropped, no trait key) failure rate
    cur2 = tr.filter((pl.col("Year") < years[-1]) & (pl.col("n_raw") == 1) & (pl.col("isdead") == 0)).select(RAW + ["Year", "Age", "kS"])
    nx2 = tr.filter(pl.col("n_raw") == 1).select(RAW + ["Year", "Age", "kS"]).with_columns(Year=pl.col("Year") - 1)
    j2 = cur2.join(nx2, on=RAW + ["Year"], how="inner", suffix="_n")
    R["pairing"]["rawkey_pairs"] = j2.height
    R["pairing"]["rawkey_age_or_sla_fail"] = int(((j2["Age_n"] != j2["Age"] + 1) | (j2["kS_n"] != j2["kS"])).sum())
    # counter recursion + observable biomass sign
    mm = m.with_columns(dvegc=pl.col("vegc_n") - pl.col("vegc"), dagb=pl.col("agb_n") - pl.col("agb"))
    rec_ok = (pl.col("c_rob_n") == 0) | (pl.col("c_rob_n") == pl.col("c_rob") + 1)
    R["counter"]["recursion_fail"] = int(mm.select((~rec_ok).sum()).item())
    R["counter"]["recursion_pairs"] = mm.height
    rec_ok_t = (pl.col("c_their_n") == 0) | (pl.col("c_their_n") == pl.col("c_their") + 1)
    R["counter"]["recursion_fail_their_formula"] = int(mm.select((~rec_ok_t).sum()).item())
    conf = mm.group_by([(pl.col("c_rob_n") > 0).alias("cpos"), (pl.col("dvegc") < 0).alias("dvegc_neg"),
                        (pl.col("dagb") < 0).alias("dagb_neg")]).len()
    R["counter"]["confusion_cnext_pos_vs_dvegc_dagb_neg"] = [{k: (bool(v) if k != "len" else int(v)) for k, v in r.items()} for r in conf.iter_rows(named=True)]
    def acc(col):
        return float(mm.select(((pl.col("c_rob_n") > 0) == (pl.col(col) < 0)).mean()).item())
    R["counter"]["sign_agreement_dvegc"] = acc("dvegc")
    R["counter"]["sign_agreement_dagb"] = acc("dagb")
    # stems that died (isdead_n==1) also: counter recursion on dying stems
    log("pairing", R["pairing"]["fate_frac_mean"], R["pairing"]["age_plus1_frac"], R["counter"]["recursion_fail"])
    # ---------------- recruitment
    firsty = tr.group_by(TK).agg(fy=pl.col("Year").min())
    trf = tr.join(firsty, on=TK, how="left")
    prev_keys = tr.select(TK + ["Year"]).unique().with_columns(Year=pl.col("Year") + 1).with_columns(prev=pl.lit(True))
    trf = trf.join(prev_keys, on=TK + ["Year"], how="left").with_columns(prev=pl.col("prev").fill_null(False))
    newrows = trf.filter((~pl.col("prev")) & (pl.col("Year") > years[0]))
    rec = newrows.filter(pl.col("fy") == pl.col("Year"))
    reent = newrows.filter(pl.col("fy") < pl.col("Year"))
    live_all = tr.filter(pl.col("isdead") == 0)
    # per cell-year
    cyr = rec.group_by(["Year", "Cell"]).len()
    cells_years = tr.filter(pl.col("Year") > years[0]).select(["Year", "Cell"]).unique()
    cyr = cells_years.join(cyr, on=["Year", "Cell"], how="left").with_columns(pl.col("len").fill_null(0))
    # per patch-year over all grass-row patches
    patches = gp.filter(pl.col("Year") > years[0]).select(["Year", "Cell", "Patch"])
    pr = rec.group_by(["Year", "Cell", "Patch"]).len()
    pr = patches.join(pr, on=["Year", "Cell", "Patch"], how="left").with_columns(pl.col("len").fill_null(0))
    live_prev_n = live_all.filter(pl.col("Year") < years[-1]).group_by("Year").len().rename({"len": "nlive"}).with_columns(Year=pl.col("Year") + 1)
    rate = rec.group_by("Year").len().join(live_prev_n, on="Year").with_columns(r=pl.col("len") / pl.col("nlive"))
    oob_w = rec.with_columns(lo=pl.col("Type").replace_strict({k: v[0] for k, v in WD_IV.items()}, return_dtype=pl.Float64),
                             hi=pl.col("Type").replace_strict({k: v[1] for k, v in WD_IV.items()}, return_dtype=pl.Float64),
                             dlo=pl.col("Type").replace_strict({k: v[0] for k, v in D95_IV.items()}, return_dtype=pl.Float64),
                             dhi=pl.col("Type").replace_strict({k: v[1] for k, v in D95_IV.items()}, return_dtype=pl.Float64))
    R["recruit"] = {
        "n_recruits": rec.height, "n_reentries": reent.height,
        "reentry_share_of_new": reent.height / max(1, newrows.height),
        "rate_per_live_q": q(rate["r"].cast(pl.Float64)),
        "per_cellyear_q": q(cyr["len"].cast(pl.Float64)),
        "zero_cellyears": int((cyr["len"] == 0).sum()), "cellyears": cyr.height,
        "per_patchyear_mean": float(pr["len"].mean()), "per_patchyear_var_over_mean": float(pr["len"].var() / pr["len"].mean()),
        "height_q": q(rec["Height"].cast(pl.Float64)), "age_q": q(rec["Age"].cast(pl.Float64)),
        "dead_first_year_frac": float(rec["isdead"].mean()),
        "type_share": {str(k): v / rec.height for k, v in rec.group_by("Type").len().sort("Type").iter_rows()},
        "standing_type_share": {str(k): v / live_all.height for k, v in live_all.group_by("Type").len().sort("Type").iter_rows()},
        "wooddens_out_of_own_interval_frac": float(oob_w.select(((pl.col("Wooddens") < pl.col("lo") - 0.5) | (pl.col("Wooddens") > pl.col("hi") + 0.5)).mean()).item()),
        "d95max_out_of_own_interval_frac": float(oob_w.select(((pl.col("D95max") < pl.col("dlo") - 1e-3) | (pl.col("D95max") > pl.col("dhi") + 1e-3)).mean()).item()),
        "c_at_entry_hist": {str(k): int(v) for k, v in rec.group_by("c_rob").len().sort("c_rob").iter_rows()},
    }
    # gap response: patch live fpc at y vs recruits at y+1
    pf = live_all.group_by(["Year", "Cell", "Patch"]).agg(fpc=pl.col("fpc_ind").cast(pl.Float64).sum(), nl=pl.len())
    pd_ = tr.filter(pl.col("isdead") == 1).group_by(["Year", "Cell", "Patch"]).agg(nd=pl.len())
    base = gp.select(["Year", "Cell", "Patch"]).join(pf, on=["Year", "Cell", "Patch"], how="left").join(
        pd_, on=["Year", "Cell", "Patch"], how="left").with_columns(pl.col("fpc").fill_null(0.0), pl.col("nl").fill_null(0), pl.col("nd").fill_null(0))
    base = base.sort(["Cell", "Patch", "Year"]).with_columns(
        fpc_prev=pl.col("fpc").shift(1).over(["Cell", "Patch"]),
        yprev=pl.col("Year").shift(1).over(["Cell", "Patch"]))
    prn = pr.with_columns(Year=pl.col("Year") - 1).rename({"len": "rec_next"})
    g = base.join(prn, on=["Year", "Cell", "Patch"], how="inner")
    g = g.with_columns(
        fpc_dm=pl.col("fpc") - pl.col("fpc").mean().over(["Year", "Cell"]),
        rec_dm=pl.col("rec_next") - pl.col("rec_next").mean().over(["Year", "Cell"]),
        nd_dm=pl.col("nd") - pl.col("nd").mean().over(["Year", "Cell"]))
    def corr(a, b_):
        return float(np.corrcoef(g[a].to_numpy(), g[b_].to_numpy())[0, 1])
    ev = g.filter((pl.col("yprev") == pl.col("Year") - 1) & (pl.col("fpc_prev") > 0.05))
    ev = ev.with_columns(loss=1 - pl.col("fpc") / pl.col("fpc_prev"))
    R["recruit"]["gap"] = {
        "within_cellyear_corr_rec_next_vs_fpc": corr("fpc_dm", "rec_dm"),
        "within_cellyear_corr_rec_next_vs_deaths": corr("nd_dm", "rec_dm"),
        "mean_rec_next_all": float(g["rec_next"].mean()),
        "mean_rec_next_after_ge50pct_loss": float(ev.filter(pl.col("loss") >= 0.5)["rec_next"].mean()),
        "n_events_ge50": int((ev["loss"] >= 0.5).sum()),
        "mean_rec_next_no_loss": float(ev.filter(pl.col("loss") <= 0.0)["rec_next"].mean()),
    }
    log("recruit", R["recruit"]["n_recruits"], R["recruit"]["gap"])
    # ---------------- continuity with previous window
    if prev_win:
        pv = add_keys(load(gcm, "Historical" if prev_win == "h1985" else scen, seed, prev_win))
        pv = pv.filter((pl.col("Type") <= 6) & (pl.col("Year") == pv["Year"].max()))
        pv = pv.with_columns(n_tk=pl.len().over(TK)).filter((pl.col("n_tk") == 1) & (pl.col("isdead") == 0))
        f0 = tr.filter((pl.col("Year") == years[0]) & (pl.col("n_tk") == 1)).select(TK + ["Age", "isdead"])
        jc = pv.select(TK + ["Age"]).join(f0, on=TK, how="left", suffix="_n")
        R["continuity"] = {"prev_window": prev_win, "live_prev": jc.height,
                           "matched": int(jc["Age_n"].is_not_null().sum()),
                           "age_plus1_frac_matched": float((jc.filter(pl.col("Age_n").is_not_null())["Age_n"] == jc.filter(pl.col("Age_n").is_not_null())["Age"] + 1).mean()),
                           "absent_frac": float(jc["Age_n"].is_null().mean()),
                           "cells_prev": pv["Cell"].n_unique(), "cells_first": f0["Cell"].n_unique()}
        log("continuity", R["continuity"])
    R["wall_s"] = time.time() - t0
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{label}.json", "w") as fh:
        json.dump(R, fh, indent=1, default=str)
    log("WROTE", f"{OUT}/{label}.json", "wall", R["wall_s"])


def census_only(gcm, scen, seed, win):
    label = f"{gcm}_{scen}_s{seed}_{win}"
    df = load(gcm, scen, seed, win)
    years = sorted(df["Year"].unique().to_list())
    R = {"member": label, "years": years, "census": census(df, years)}
    tr = add_keys(df.filter(pl.col("Type") <= 6))
    last = years[-1]
    cells_last = tr.filter(pl.col("Year") == last)["Cell"].unique()
    R["last_year_cells_max"] = int(cells_last.max())
    # naive pairing of last two years
    a = tr.filter((pl.col("Year") == last - 1) & (pl.col("isdead") == 0)).select(TK)
    b = tr.filter(pl.col("Year") == last).select(TK).with_columns(x=pl.lit(1))
    jj = a.join(b, on=TK, how="left")
    R["naive_last_pair_absent_frac"] = float(jj["x"].is_null().mean())
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{label}_census.json", "w") as fh:
        json.dump(R, fh, indent=1, default=str)
    log("WROTE census", R)


def extras(gcm, scen, seed, win):
    """Die-offs and patch-matched fire-by-resistance test (fire_frac is per PATCH in firepft.c)."""
    label = f"{gcm}_{scen}_s{seed}_{win}"
    df = load(gcm, scen, seed, win)
    tr = df.filter(pl.col("Type") <= 6).with_columns(resist=mapexpr("Type", RESIST),
                                                       hard=pl.col("mort") >= 0.999999)
    del df
    R = {"member": label, "subsample": f"Cell % {MOD} == {REM}"}
    g = tr.group_by(["Year", "Cell", "Type"]).agg(n=pl.len(), d=pl.col("isdead").sum(),
                                                   hz=pl.col("mort").cast(pl.Float64).sum())
    g3 = g.filter(pl.col("n") >= 3)
    R["dieoff"] = {"groups_n_ge3": g3.height,
                   "all_dead": int((g3["d"] == g3["n"]).sum()),
                   "ge90pct_dead": int((g3["d"] >= 0.9 * g3["n"]).sum()),
                   "ge90pct_dead_excess_deaths": float(g3.filter(pl.col("d") >= 0.9 * pl.col("n")).select((pl.col("d") - pl.col("hz")).sum()).item()),
                   "all_dead_examples": g3.filter(pl.col("d") == pl.col("n")).sort("n", descending=True).head(10).to_dicts()}
    nh = tr.filter(~pl.col("hard"))
    def prate(sub):
        return sub.group_by(["Year", "Cell", "Patch"]).agg(
            d=pl.col("isdead").sum(), h=pl.col("mort").cast(pl.Float64).sum(),
            e=(1 - pl.col("mort").cast(pl.Float64)).sum(), n=pl.len())
    b = prate(nh.filter(pl.col("Type") == 3))
    out = {}
    for name, sel in {"conifer_146": [1, 4, 6], "type1": [1], "type4": [4], "type2": [2], "type5": [5], "type0": [0], "type6": [6]}.items():
        o = prate(nh.filter(pl.col("Type").is_in(sel)))
        j = b.join(o, on=["Year", "Cell", "Patch"], suffix="_o")
        if j.height == 0:
            continue
        eb = (j["d"].sum() - j["h"].sum()) / j["e"].sum()
        eo = (j["d_o"].sum() - j["h_o"].sum()) / j["e_o"].sum()
        # bootstrap over patch-years for the ratio
        rng = np.random.default_rng(0)
        arr = j.select(["d", "h", "e", "d_o", "h_o", "e_o"]).to_numpy()
        rs = []
        for _ in range(200):
            ix = rng.integers(0, len(arr), len(arr))
            a = arr[ix].sum(0)
            if a[0] - a[1] != 0:
                rs.append(((a[3] - a[4]) / a[5]) / ((a[0] - a[1]) / a[2]))
        rexp = (1 - np.mean([RESIST[t] for t in sel])) / (1 - RESIST[3])
        out[name] = {"patchyears": j.height, "beech_excess": float(eb), "other_excess": float(eo),
                     "ratio": float(eo / eb) if eb else None,
                     "ratio_ci90": [float(np.quantile(rs, 0.05)), float(np.quantile(rs, 0.95))] if rs else None,
                     "ratio_expected_if_fire": float(rexp), "other_deaths": int(j["d_o"].sum()),
                     "other_stems": int(j["n_o"].sum())}
    R["fire_by_type_matched_patchyear"] = out
    # patch clustering of non-hazard deaths: whole-patch kills
    pa = tr.group_by(["Year", "Cell", "Patch"]).agg(n=pl.len(), d=pl.col("isdead").sum(),
                                                     hz=pl.col("mort").cast(pl.Float64).sum(),
                                                     nh_d=(pl.col("isdead").cast(pl.Int32) * (~pl.col("hard")).cast(pl.Int32)).sum())
    pa4 = pa.filter(pl.col("n") >= 4)
    R["patch_kills"] = {"patchyears_n_ge4": pa4.height,
                        "ge50pct_dead": int((pa4["d"] >= 0.5 * pa4["n"]).sum()),
                        "ge50pct_dead_expected_poisson_binom_mean_hz": float(pa4.select((pl.col("hz") >= 0.5 * pl.col("n")).sum()).item()),
                        "all_dead": int((pa4["d"] == pa4["n"]).sum())}
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/{label}_extras.json", "w") as fh:
        json.dump(R, fh, indent=1, default=str)
    log("WROTE extras", json.dumps(R, default=str)[:3000])


if __name__ == "__main__":
    pl.Config.set_tbl_rows(50)
    if sys.argv[1] == "run":
        run(*sys.argv[2:6], *(sys.argv[6:7] or [None]))
    elif sys.argv[1] == "extras":
        extras(*sys.argv[2:6])
    elif sys.argv[1] == "census":
        census_only(*sys.argv[2:6])
    else:
        raise SystemExit(__doc__)
