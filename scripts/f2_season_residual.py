#!/usr/bin/env python3
"""Where in the year the learned daily model's carbon error sits, per held-out block (ADR 0334 §1).

Usage: python scripts/f2_season_residual.py <ensemble_tag> [leg] [member]   (default ctl_obs, 1)

One-step (teacher-forced stores, the original's own stand) daily GPP and plant respiration
(GPP - NPP) of the ensemble named by runs/<tag>/log.txt, for every held-out cell; summed per block
and calendar month, printed as emulator - original in gC/m2 per cell per year, plus each block's
annual ratio and its latitude. A residual that is large and seasonal only south of the equator
points at the absolute day-of-year input; a flat offset points at a level bias.
"""

import ast
import os
import sys

import numpy as np
import polars as pl
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f2_train as F  # noqa: E402

MONTH = np.repeat(np.arange(12), [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


def setup(tag, dev):
    line = open(os.path.join(F.DATA, "runs", tag, "log.txt")).readline()
    args = ast.literal_eval(line.split("args=", 1)[1])
    F.NH, F.NL, F.NPP_HEAD = args["hidden"], args["layers"], args["npp_head"]
    F.CARBON_HEAD = args.get("carbon_head", "free")
    F.DROP[:] = [F.FEAT[v] for v in args.get("drop_inputs", "").split(",") if v]
    F.SEASON_PHASE = args.get("season_phase", "calendar")
    nets = []
    for t in args["ensemble"].split(","):
        n, ck = F.load_net(os.path.join(F.DATA, "runs", t, "model.pt"), dev)
        n.load_state_dict(ck)
        nets.append(n.eval())
    return F.Ensemble(nets).to(dev)


def main():
    tag = sys.argv[1]
    leg = sys.argv[2] if len(sys.argv) > 2 else "ctl_obs"
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    net = setup(tag, dev)
    cdf = pl.read_parquet(os.path.join(F.DATA, "cells.parquet"))
    lat = cdf["lat"].to_numpy().astype(np.float32)
    ho = np.where(cdf["heldout"].to_numpy())[0]
    blk = cdf["block"].to_numpy()
    ml = F.MemberLeg(k, leg, lat)
    days = np.arange(1, F.ND)
    mon = MONTH[days % 365]
    res = {}
    for c in ho:
        cells = np.full(len(days), c)
        x = ml.inputs_teacher(cells, days)
        y, prec, S_prev, _ = ml.targets(cells, days)
        p = F.predict(net, x, prec, S_prev, dev)
        for nm, e, t in (("gpp", p[:, 6], y[:, 6]), ("resp", p[:, 6] - p[:, 7], y[:, 6] - y[:, 7])):
            r = res.setdefault((blk[c], nm), np.zeros((3, 12)))
            r[0] += np.bincount(mon, e, 12)
            r[1] += np.bincount(mon, t, 12)
            r[2] += 1
    print(f"## {tag} one-step, m{k}_{leg}: emulator - original, gC/m2/cell/yr, by month\n")
    print("| block | lat | flux | year E/T | " + " | ".join("JFMAMJJASOND") + " |")
    print("|---|---|---|---|" + "---|" * 12)
    for b in sorted({blk[c] for c in ho}):
        for nm in ("gpp", "resp"):
            e, t, n = res[(b, nm)]
            d = (e - t) / n[0] / F.NY
            print(f"| {b} | {lat[blk == b].mean():.1f} | {nm} | {e.sum() / t.sum():.3f} | "
                  + " | ".join(f"{v:+.1f}" for v in d) + " |")  # fmt: skip


if __name__ == "__main__":
    main()
