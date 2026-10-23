#!/usr/bin/env python3
"""xtf_0369_decide.py -- ADR 0369 (SEPARATE EXPERIMENT, not for the paper): apply the pre-registered decisions.

  python scripts/xtf_0369_decide.py daily [--cost ARM=core-s ...]   experiments A (place) and B (cheap memory)
  python scripts/xtf_0369_decide.py trees                           experiment C (per-tree carbon state)

Reads xtf/daily/score_summary.csv (xtf_daily.py score) and xtf/treemort/score.csv (xtf_tree_models.py score).
Decision group: held-out cells x held-out climate models.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import polars as pl

DAILY = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/daily"
TREES = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/treemort"
GRP = "heldout x heldout-GCM"
FLUXES = ("npp", "et", "runoff")
B_COST = 1.29e-3  # ADR 0368 bench, the deployed network, core-s per cell-year
MEM_ARMS = ("MP", "ME", "MM", "MEP", "MMP")


def daily(a):
    s = pl.read_csv(f"{DAILY}/score_summary.csv").filter(pl.col("group") == GRP)

    def g(arm, flux, c):
        r = s.filter((pl.col("arm") == arm) & (pl.col("flux") == flux))[c]
        return float(r[0]) if len(r) else np.nan

    out = {}
    # A: place test
    shares, none_ = {}, []
    for f in FLUXES:
        sh = []
        for c in ("year_p50", "30y_late_p50"):
            tc, tp, tw = g("TC", f, c), g("TP", f, c), g("TW", f, c)
            sh.append((tc - tp) / (tc - tw))
        shares[f] = [round(x, 2) for x in sh]
        if all((g("TC", f, c) - g("TP", f, c)) <= g("B", f, f"{c}_spread") for c in ("year_p50", "30y_late_p50")):
            none_.append(f)
    n_full = sum(min(v) >= 0.75 for v in shares.values())
    verdict = "EXPLAINS the memory gain" if n_full >= 2 else ("explains NONE of it" if len(none_) >= 2 else "PARTLY")
    out["A place test"] = {"gain share (single-year, late 30-yr)": shares, "no gain within spread": none_,
                           "verdict": verdict}  # fmt: skip
    # B: cheap memory
    cost = dict(kv.split("=") for kv in a.cost)
    res = {}
    for arm in MEM_ARMS:
        wins = []
        for f in FLUXES:
            sp = {c: max(g("B", f, f"{c}_spread"), g("MR", f, f"{c}_spread")) for c in ("year_p50", "30y_late_p50",
                                                                                     "drift")}  # fmt: skip
            ok = all(g("MR", f, c) - g(arm, f, c) > sp[c] for c in ("year_p50", "30y_late_p50"))
            ok &= abs(g(arm, f, "drift") - 1) - abs(g("MR", f, "drift") - 1) <= sp["drift"]
            if ok:
                wins.append(f)
        c = float(cost[arm]) if arm in cost else np.nan
        cheap = c <= 2 * B_COST if np.isfinite(c) else None
        keep = {f: round((g("MR", f, "year_p50") - g(arm, f, "year_p50"))
                         / (g("MR", f, "year_p50") - g("TW", f, "year_p50")), 2) for f in FLUXES}  # fmt: skip
        res[arm] = {"wins": wins, "cost": c, "cheap": cheap, "qualifies": len(wins) >= 2 and bool(cheap),
                    "npp single-year": round(g(arm, "npp", "year_p50"), 3), "share of TW's gain kept": keep}
    q = [k for k, v in res.items() if v["qualifies"]]
    pool = q or list(res)
    chosen = min(pool, key=lambda k: res[k]["npp single-year"])
    out["B cheap memory"] = res
    out["B chosen"] = f"{chosen} ({'qualifies' if q else 'NOT qualifying, re-scored anyway'})"
    out["B baseline MR npp single-year"] = round(g("MR", "npp", "year_p50"), 3)
    out["B deployed B npp single-year"] = round(g("B", "npp", "year_p50"), 3)
    print(json.dumps(out, indent=1))


def trees(_a):
    d = pl.read_csv(f"{TREES}/score.csv").filter(pl.col("group") == GRP)

    def m(prefix, c):
        r = d.filter(pl.col("run").str.starts_with(f"{prefix}_s"))[c].to_list()
        return (float(np.mean(r)), float(np.max(r) - np.min(r)), len(r)) if r else (np.nan, np.nan, 0)

    arms = ["ST", "STCe", "STK", "STKt", "STKCe", "STKe", "STKc"] + sorted(
        {r.rsplit("_s", 1)[0] for r in d["run"].to_list() if r.startswith(("STK", "STC"))} - {"STCt", "STCe"}
        - {"STK", "STKt", "STKCe", "STKe", "STKc"})  # fmt: skip
    tab = {a: {c: m(a, c) for c in ("skill", "dieoff_capture", "rate30_ratio")} for a in arms}
    for a, v in tab.items():
        print(f"{a:8s} skill {v['skill'][0]:.3f} (spread {v['skill'][1]:.3f}, n {v['skill'][2]})  capture "
              f"{v['dieoff_capture'][0]:.3f} (spread {v['dieoff_capture'][1]:.3f})  30-yr {v['rate30_ratio'][0]:.3f}")
    c = lambda a: tab[a]["dieoff_capture"][0]  # noqa: E731
    k = lambda a: tab[a]["skill"][0]  # noqa: E731
    r = lambda a: tab[a]["rate30_ratio"][0]  # noqa: E731
    out = {
        "state carries the die-off signal (STKt capture >= 0.5)": c("STKt") >= 0.5,
        "state alone helps (STK - ST >= 0.03)": round(c("STK") - c("ST"), 3),
        "worth a free-running test (STKe >= STCe + 0.05, skill >= STCe, 30-yr <= 1.1 STCe)":
            c("STKe") >= c("STCe") + 0.05 and k("STKe") >= k("STCe") and r("STKe") <= 1.1 * r("STCe"),
        "carbon-state model adds (STKe - STKCe >= 0.03)": round(c("STKe") - c("STKCe"), 3),
        "share of the bound kept (STKe - ST) / (STKt - ST)": round((c("STKe") - c("ST")) / (c("STKt") - c("ST")), 3),
        "daily-model limit STKc - STKe": round(c("STKc") - c("STKe"), 3),
    }
    for a in arms:
        if a.startswith("STC") and a not in ("STCe", "STCt"):
            out[f"{a} vs STCe (>= +0.03 = the cheaper memory helps die-offs)"] = round(c(a) - c("STCe"), 3)
        if a.startswith("STK") and a not in ("STK", "STKt", "STKCe", "STKe", "STKc"):
            out[f"{a} vs STKe"] = round(c(a) - c("STKe"), 3)
    print(json.dumps(out, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["daily", "trees"])
    ap.add_argument("--cost", nargs="*", default=[], help="ARM=core-s per cell-year from xtf_daily.py bench")
    a = ap.parse_args()
    {"daily": daily, "trees": trees}[a.what](a)


if __name__ == "__main__":
    main()
