#!/usr/bin/env python3
"""summarise_design_sensitivity.py -- the tables of ADR 0359 (design-choice sensitivity of the learning set-up).

  daily  per arm: final validation loss of each seed's network (f2/runs/DC_<ARM>_s<seed>/log.txt, last epoch line),
         mean, sd, ratio to BASE, per-target ratios; STAGE-2 flag = mean below BASE by > 2 % AND by > 2 pooled seed sds.
  map    per arm (suffix _dc_<ARM>_fx, reference the release map _fx) and departure arm (_dc_<ARM>_statedep_fx,
         reference _statedep_fx): median over the 15 cases of the per-case ratio arm / reference of rho50 and rho90 for
         every (group, quantity); drift (2051-70 -> 2081-2100 and 2021-40 -> 2081-2100, dense, tree count and biomass
         per tree); departure arms also the die-off share (median over shared tree-count events of the drop followed).
         Reading (ADR 0359 sec. 1): BETTER if dense tree count AND dense biomass per tree <= 0.98 with nothing > 1.02;
         WORSE if either is > 1.02; else EQUIVALENT.
Usage: python scripts/summarise_design_sensitivity.py [daily|map|all]   (seconds; reads finished arms only)
"""

import os
import re
import sys

import numpy as np
import polars as pl

F2 = "/p/projects/reformit/Jamir/esm_land_emulator_data/f2/runs"
EV = "/p/projects/open/Jamir/esm_land_emulator_data/xpanel/eval"
DAILY = ["BASE", "H128", "H512", "L2", "L4", "RELU", "GELU", "TANH", "E5", "E20", "LR1", "LR10", "B4K", "B64K",
         "NOWIN", "NOPWIN", "NOTWIN"]
MAP = ["L15", "L63", "R200", "R800", "LR025", "LR10", "F10", "MD100", "W10", "W20", "W50", "S2", "S8", "NOS0", "NODC",
       "NOANC"]
DEP = ["DL15", "DL63", "DR200", "DR800", "DZ15", "DZ20"]
TGT = ["gpp", "npp", "transp", "evap", "runoff"]


def last_val(arm, seed):
    f = os.path.join(F2, f"DC_{arm}_s{seed}", "log.txt")
    if not os.path.exists(f) or "== DONE" not in open(f).read():
        return None
    ep = [ln for ln in open(f) if re.match(r"epoch \d+:", ln)]
    m = re.search(r"val ([\d.]+) per-target (\{.*\})", ep[-1])
    per = eval(m.group(2))  # noqa: S307 -- our own log line, a dict literal
    return float(m.group(1)), per


def daily():
    rows = []
    for arm in DAILY:
        v = [x for s in (0, 1, 2) if (x := last_val(arm, s)) is not None]
        if not v:
            continue
        loss = np.array([x[0] for x in v])
        rows.append(dict(arm=arm, seeds=len(v), val=loss.mean(), sd=loss.std(ddof=1) if len(v) > 1 else np.nan,
                         **{t: np.mean([x[1][t] for x in v]) for t in TGT}))
    d = pl.DataFrame(rows)
    if "BASE" not in d["arm"].to_list():
        print(d)
        return
    b = d.filter(pl.col("arm") == "BASE").row(0, named=True)
    sd = np.sqrt(np.nanmean(d["sd"].to_numpy() ** 2))
    d = d.with_columns((pl.col("val") / b["val"]).round(3).alias("ratio"),
                       *[(pl.col(t) / b[t]).round(3).alias(f"r_{t}") for t in TGT])
    d = d.with_columns(((pl.col("val") < 0.98 * b["val"]) & (b["val"] - pl.col("val") > 2 * sd)).alias("stage2"))
    pl.Config.set_tbl_rows(30)
    pl.Config.set_tbl_cols(16)
    pl.Config.set_tbl_width_chars(220)
    print(f"\n== daily screen (pooled seed sd {sd:.5f}; BASE val {b['val']:.5f})")
    print(d.select("arm", "seeds", pl.col("val").round(5), pl.col("sd").round(5), "ratio", *[f"r_{t}" for t in TGT],
                   "stage2").sort("ratio"))


def struct_ratio(sfx, ref):
    fa, fr = (os.path.join(EV, f"final_structure_anchor{s}.csv") for s in (sfx, ref))
    if not os.path.exists(fa):
        return None
    a = pl.read_csv(fa).filter(pl.col("cand") == "emulator")
    r = pl.read_csv(fr).filter(pl.col("cand") == "emulator")
    j = a.join(r, on=["leg", "grp", "q"], suffix="_r")
    return j.group_by("grp", "q").agg((pl.col("rho50") / pl.col("rho50_r")).median().alias("r50"),
                                      (pl.col("rho90") / pl.col("rho90_r")).median().alias("r90"))


def drift(sfx):
    f = os.path.join(EV, "yearly", f"drift_years{sfx}.csv")
    if not os.path.exists(f):
        return {}
    y = pl.read_csv(f).filter((pl.col("grp") == "dense") & (pl.col("cand") == "YA"))
    out = {}
    for q, k in (("n_per_patch", "n"), ("agb_per_stem", "a")):
        t = y.filter(pl.col("q") == q)

        def per(a, b, t=t):
            return t.filter(pl.col("Year").is_between(a, b)).group_by("leg").agg(pl.col("rho50").mean().alias("r"))

        j = per(2021, 2040).join(per(2051, 2070), on="leg", suffix="_m").join(per(2081, 2100), on="leg", suffix="_l")
        out[f"drift_ml_{k}"] = float((j["r_l"] / j["r_m"]).median())
        out[f"drift_el_{k}"] = float((j["r_l"] / j["r"]).median())
    return out


def capture(sfx):
    f = os.path.join(EV, f"extreme_legacy_events{sfx}.parquet")
    if not os.path.exists(f):
        return np.nan
    e = pl.read_parquet(f).filter((pl.col("q") == "tree_count") & pl.col("shared"))
    return float((e["d_emulator"] / e["d_T"]).median())


def maps():
    rows = []
    for arms, ref, kind in ((MAP, "_fx", "map"), (DEP, "_statedep_fx", "departure")):
        for arm in arms:
            sfx = f"_dc_{arm}_statedep_fx" if kind == "departure" else f"_dc_{arm}_fx"
            r = struct_ratio(sfx, ref)
            if r is None:
                continue
            g = {(x["grp"], x["q"]): x for x in r.iter_rows(named=True)}
            dn, da = g[("dense", "n_per_patch")]["r50"], g[("dense", "agb_per_stem")]["r50"]
            worst = max(max(x["r50"], x["r90"]) for x in g.values())
            verdict = ("BETTER" if (dn <= 0.98 and da <= 0.98 and worst <= 1.02) else
                       "WORSE" if (dn > 1.02 or da > 1.02) else "EQUIVALENT")
            row = dict(kind=kind, arm=arm, dense_n=dn, dense_a=da, dense_n90=g[("dense", "n_per_patch")]["r90"],
                       sparse_n=g[("sparse", "n_per_patch")]["r50"], sparse_a=g[("sparse", "agb_per_stem")]["r50"],
                       traits=float(np.median([g[("dense", q)]["r50"] for q in
                                               ("SLA_p50", "Wooddens_p50", "D95max_p50", "minwscal_p50")])),
                       worst=worst, verdict=verdict, **drift(sfx))
            if kind == "departure":
                row["dieoff"] = capture(sfx)
            rows.append(row)
    if not rows:
        print("no finished map arms")
        return
    d = pl.DataFrame(rows, infer_schema_length=None)
    pl.Config.set_tbl_rows(40)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(240)
    print("\n== forest map / departure model: median over 15 cases of arm / release ratio")
    print(d.with_columns([pl.col(c).round(3) for c in d.columns if d[c].dtype == pl.Float64]))
    for ref, kind in (("_fx", "map"), ("_statedep_fx", "departure")):
        x = {**drift(ref), "dieoff": capture(ref) if kind == "departure" else np.nan}
        print(f"reference {ref}: " + ", ".join(f"{k} {v:.3f}" for k, v in x.items()))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("daily", "all"):
        daily()
    if what in ("map", "all"):
        maps()
