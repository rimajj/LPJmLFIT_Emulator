#!/usr/bin/env python3
"""xtf_mep_decide.py -- ADR 0372 section 3 (SEPARATE EXPERIMENT): the running-means daily network with a place
description from PAST weather (MEPh fixed 1990-2019, MEPt trailing 30 years) against the deployed ensemble B on the
complete-emulator venue of ADR 0370. Reads OUT/ens/ratios_stand_emul_main2_372.csv (xtf_daily.py scoreens) and the
one-core costs OUT/runs/<arm>_s0/bench.json; prints the decision and writes OUT/ens/mep_decide.json.
"""

from __future__ import annotations

import json

import numpy as np
import polars as pl

OUT = "/p/projects/open/Jamir/esm_land_emulator_data/xtf/daily"
FLUXES = ("gpp", "npp", "et", "runoff")
MED = {"npp": 0.95, "gpp": 1.05, "et": 1.05, "runoff": 1.05}
WORST = {"gpp": 1.272, "npp": 1.25, "et": 1.256, "runoff": 1.277}  # max(1.25, ADR 0371 N1's largest max(q, 1/q))
CANDS = ("MEPh", "MEPt", "MEP")  # MEP (look-ahead place) for reference only


def main():
    r = pl.read_csv(f"{OUT}/ens/ratios_stand_emul_main2_372.csv").filter(~pl.col("co2fix"))
    cost_b = json.load(open(f"{OUT}/runs/B_s0/bench.json"))["core_s_per_cell_year"]
    res = {"B cost (core-s per cell-year, one network)": cost_b}
    for c in CANDS:
        x, o, fails = r.filter(pl.col("arm") == c), {}, []
        for v in FLUXES:
            y = x.filter(pl.col("flux") == v)
            q = np.concatenate([y["q_early"].to_numpy(), y["q_late"].to_numpy()])
            o[v] = dict(median_q=round(float(np.median(q)), 3),
                        early_q=round(float(np.median(y["q_early"].to_numpy())), 3),
                        late_q=round(float(np.median(y["q_late"].to_numpy())), 3),
                        worst_q=round(float(q.max()), 3), legs_worse_late=int((y["q_late"] > 1).sum()))  # fmt: skip
            fails += [f"{v} median"] * (o[v]["median_q"] > MED[v]) + [f"{v} late"] * (o[v]["late_q"] > 1.0)
            fails += [f"{v} worst"] * (o[v]["worst_q"] > WORST[v])
        try:
            cost = json.load(open(f"{OUT}/runs/{c}_s0/bench.json"))["core_s_per_cell_year"]
            o["cost_vs_B"] = round(cost / cost_b, 3)
            fails += ["cost"] * (cost / cost_b > 1.35)
        except FileNotFoundError:
            o["cost_vs_B"] = None
            fails.append("cost not measured")
        o["mean_median_q"] = round(float(np.mean([o[v]["median_q"] for v in FLUXES])), 4)
        o["fails"], o["passes"] = fails, not fails
        res[c] = o
    ok = [c for c in ("MEPh", "MEPt") if res[c]["passes"]]
    if not ok:
        pick = None
    elif len(ok) == 2 and abs(res["MEPh"]["mean_median_q"] - res["MEPt"]["mean_median_q"]) < 0.01:
        pick = "MEPh"
    else:
        pick = min(ok, key=lambda c: res[c]["mean_median_q"])
    res["decision"] = f"package {pick} (ADR 0372 section 4)" if pick else "neither passes: nothing packaged"
    with open(f"{OUT}/ens/mep_decide.json", "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
