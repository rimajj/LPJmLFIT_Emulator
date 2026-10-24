#!/usr/bin/env python3
"""xtf_drift_noise.py -- ADR 0371 (SEPARATE EXPERIMENT, not for the paper): the noise of ADR 0370's per-leg drift
clause, measured with two ensembles of the same daily network, and the candidates re-judged with the noise-calibrated
clause.

Reads the ratio tables written by `xtf_daily.py scoreens` (OUT/ens/ratios_stand_emul_main2<suffix>.csv):
  _n1     MRb vs MRa (same design, disjoint seeds)     -> null N1
  _n2     MRa vs B   (retrained vs deployed copies)    -> null N2
  ''      every ensemble vs B                          -> the decision (candidates MEP, MEPx, TP)
  _vsMR   candidates vs MRa                            -> reported only
Prints the nulls' statistics, the decision of ADR 0371 section 3 and writes OUT/ens/drift_noise.json.
"""

from __future__ import annotations

import json

import numpy as np
import polars as pl

ROOT = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/daily/ens"
FLUXES = ("gpp", "npp", "et", "runoff")
CANDS = ("MEP", "MEPx", "TP")


def ratios(sfx):
    return pl.read_csv(f"{ROOT}/ratios_stand_emul_main2{sfx}.csv").filter(~pl.col("co2fix"))


def arm_stats(df, arm):
    """Per flux: median q, worst q, worst max(q, 1/q), worst |drift excess|, worst drift excess, legs over +0.08."""
    o = {}
    x = df.filter(pl.col("arm") == arm)
    for v in FLUXES:
        y = x.filter(pl.col("flux") == v)
        q = np.concatenate([y["q_early"].to_numpy(), y["q_late"].to_numpy()])
        d = y["d_drift"].to_numpy()
        o[v] = dict(nlegs=len(d), median_q=round(float(np.median(q)), 3), worst_q=round(float(q.max()), 3),
                    worst_q_sym=round(float(np.maximum(q, 1 / q).max()), 3),
                    worst_abs_drift=round(float(np.abs(d).max()), 3), worst_drift=round(float(d.max()), 3),
                    legs_over=int((d > 0.08).sum()))  # fmt: skip
    return o


def main():
    nulls = {"N1 MRb vs MRa": arm_stats(ratios("_n1"), "MRb"), "N2 MRa vs B": arm_stats(ratios("_n2"), "MRa")}
    noise = any(s[v]["legs_over"] > 0 for s in nulls.values() for v in FLUXES)
    L = {v: dict(L_q=max(s[v]["worst_q_sym"] for s in nulls.values()),
                 L_drift=max(s[v]["worst_abs_drift"] for s in nulls.values()),
                 count=max(s[v]["legs_over"] for s in nulls.values())) for v in FLUXES}  # fmt: skip
    res = {"nulls": nulls, "clause is noise (a null breaks it)": noise, "calibrated limits": L, "candidates": {}}
    vb, vm = ratios(""), ratios("_vsMR")
    for c in CANDS:
        s, ok, why = arm_stats(vb, c), True, []
        for v in FLUXES:
            lim = 0.95 if v == "npp" else 1.05
            checks = {"median": s[v]["median_q"] <= lim,
                      "worst q": s[v]["worst_q"] <= max(1.25, L[v]["L_q"]),
                      "worst drift": s[v]["worst_drift"] <= max(0.08, L[v]["L_drift"]),
                      "legs over": s[v]["legs_over"] <= L[v]["count"]}  # fmt: skip
            why += [f"{v} {k}" for k, good in checks.items() if not good]
            ok &= all(checks.values())
        res["candidates"][c] = {"vs B": s, "vs MRa (reported)": arm_stats(vm, c),
                                "passes calibrated rule": bool(noise and ok), "fails on": why}
    if not noise:
        res["decision"] = "no null breaks the clause: ADR 0370's rejections stand; stop (z3)"
    elif res["candidates"]["MEP"]["passes calibrated rule"]:
        res["decision"] = "MEP passes the calibrated rule: package it as a release candidate (ADR 0371 3(iii))"
    else:
        passing = [c for c in CANDS if res["candidates"][c]["passes calibrated rule"]]
        res["decision"] = f"MEP fails the calibrated rule; passing: {passing or 'none'} -> nothing built"
    with open(f"{ROOT}/drift_noise.json", "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
