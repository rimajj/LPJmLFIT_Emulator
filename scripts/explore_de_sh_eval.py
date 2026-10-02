#!/usr/bin/env python3
"""explore_de_sh_eval.py — LINE X, Germany data-driven emulator, shared item SH9: EVALUATION RUNNER + COMPARISON.

Scores any arm's engine run (SH6 run directory) with the UNCHANGED scorer (explore_de_score.py, roster format,
--scope covered) on two cell lists — all 907 dev cells (in-place for a model trained on folds 1-4: NOT evidence) and
the fold-5 dev cells (places no model saw) — and collects every arm into ONE table, shared/eval/comparison.csv,
always beside the other-seed ceiling on the same rows (ceiling_same_*). Owner decision 2026-10-01: windows are h1985
(1985-2014) and w2015 (2015-2044); the primary response is the ssp370 - ssp126 contrast c2015.

  score    --run DIR --label L [--split DEV-A] [--start-year Y] [--legs-branched yes|state-only|no|unknown]
           [--held-out-place true|false|unknown]   (SLURM job per cell list; idempotent)
  dynamics --run DIR --label L [--truth-members ...]  Germany-dev yearly series: death rate (flagged dead / living
           the year before), recruits per living stem (stems whose (Cell, Patch, Type, ID) were not printed the year
           before), c >= 1 prevalence, c = 5 share of deaths — arm vs truth, plus their yearly correlation
  table    -> shared/eval/comparison.csv (+ comparison_dynamics.csv): per label x cell list x scale x (gcm, scen,
           window) the panel106 conjunctive pass under the calibrated tolerance (in-sample and other-GCM fitted),
           ceiling_same of the same rows, the ratio, the primary-gate verdict, and the aggregate-response pass
           among determined quantities. Read every number as a RATIO to the ceiling; never quote a per-cell
           response pass alone.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_trans as tr  # noqa: E402

XDE = tr.XDE
EVAL = os.path.join(XDE, "shared", "eval")
SCORES = os.path.join(EVAL, "scores")
CELLS = {"dev": os.path.join(XDE, "shared", "scorer", "cells_dev.txt"),
         "f5": os.path.join(XDE, "shared", "scorer", "cells_fold5_dev.txt")}
SCORER = os.path.join(REPO, "scripts", "explore_de_score.py")
log = tr.log


def stage_score(a):
    os.makedirs(SCORES, exist_ok=True)
    logs = os.path.join(REPO, "logs")
    for cl, cf in CELLS.items():
        lab = f"{a.label}_{cl}"
        if os.path.exists(os.path.join(SCORES, lab, "summary_conjunctive.csv")) and not a.force:
            log(f"{lab}: scored, skipping")
            continue
        extra = ["--split", a.split, "--legs-branched", a.legs_branched, "--held-out-place",
                 "true" if cl == "f5" else a.held_out_place]
        if a.start_year:
            extra += ["--start-year", str(a.start_year)]
        cmd = " ".join([tr.PY, SCORER, "score", "--pred", a.run, "--format", "roster", "--label", lab, "--scope",
                        "covered", "--cells", cf, "--out", SCORES] + extra)
        jcf = os.path.join(XDE, "_jobs", f"X-de-eval-{lab}.jcf")
        with open(jcf, "w") as f:
            f.write(f"""#!/bin/bash
#SBATCH --job-name=X-de-eval-{lab}
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task=8
#SBATCH --time=01:00:00
{f'#SBATCH --dependency=afterok:{a.dependency}' if a.dependency else ''}
#SBATCH --output={logs}/X-de-eval-{lab}.%j.out
export POLARS_MAX_THREADS=8
{cmd}
echo "=== JOB DONE eval {lab} exit=$? ==="
""")
        jid = subprocess.run(["sbatch", "--parsable", jcf], capture_output=True, text=True, check=True).stdout.strip()
        log(f"{lab}: job {jid}")


def _yearly(roster: pl.LazyFrame) -> pl.DataFrame:
    """Germany-wide yearly dynamics of a roster (Year, Cell, Patch, Type, ID, isdead, c)."""
    R = roster.filter(pl.col("Type") <= tr.MAX_TREE_TYPE).select("scen", "Year", "Cell", "Patch", "Type", "ID",
                                                                 "isdead", "c").collect()
    out = []
    for scen in sorted(R["scen"].unique().to_list()):
        S = R.filter(pl.col("scen").is_in([scen, "Historical"]))
        ys = sorted(S["Year"].unique().to_list())
        prev = None
        for y in ys:
            cur = S.filter(pl.col("Year") == y)
            if prev is not None:
                live_prev = prev.filter(pl.col("isdead") == 0)
                k = ["Cell", "Patch", "Type", "ID"]
                new = cur.join(prev.select(k), on=k, how="anti").height
                dead = cur.filter(pl.col("isdead") == 1)
                out.append({"scen": scen, "Year": y, "death_rate": dead.height / max(live_prev.height, 1),
                            "recruits_per_stem": new / max(live_prev.height, 1),
                            "c_ge1_prev": float((cur.filter(pl.col("isdead") == 0)["c"] >= 1).mean()),
                            "c5_share_of_deaths": float((dead["c"] >= 5).mean()) if dead.height else None})
            prev = cur
    return pl.DataFrame(out)


def stage_dynamics(a):
    os.makedirs(EVAL, exist_ok=True)
    E = _yearly(pl.scan_parquet(os.path.join(a.run, "chunk_*", "*.parquet"))).with_columns(src=pl.lit("arm"))
    cells = [int(x) for x in open(CELLS["dev"]).read().split()]
    mem, _, _ = tr.registry()
    T = []
    gcm = pl.scan_parquet(os.path.join(a.run, "chunk_*", "*.parquet")).select("gcm").first().collect().item()
    run = json.load(open(os.path.join(a.run, "run.json")))
    seed = a.truth_seed or int(run["seed"])
    hist = tr.historical_of(mem, gcm, seed)
    for leg in run["legs"].split(","):
        parts = [pl.scan_parquet(hist["ind_dev_path"]).with_columns(scen=pl.lit("Historical"))]
        if leg != "Historical":
            r = mem.filter((pl.col("gcm") == gcm) & (pl.col("scen") == leg) & (pl.col("seed") == seed)
                           & ~pl.col("excluded")).row(0, named=True)
            parts.append(pl.scan_parquet(r["ind_dev_path"]).with_columns(scen=pl.lit(leg)))
        # the truth table has no counter column: recover it the SH3 way is heavy; use the transition table's c_y
        lf = pl.concat(parts, how="diagonal").filter(pl.col("Cell").is_in(cells) & pl.col("Year").is_between(
            run["start"], run["end"])).with_columns(c=pl.lit(0, pl.Int8))
        t = _yearly(lf).filter(pl.col("scen") == leg)
        T.append(t)
    T = pl.concat(T).unique(["scen", "Year"]).with_columns(src=pl.lit("truth")).drop("c_ge1_prev",
                                                                                     "c5_share_of_deaths")
    J = E.join(T.drop("src"), on=["scen", "Year"], suffix="_truth", how="left").sort("scen", "Year")
    J.write_csv(os.path.join(EVAL, f"dynamics_{a.label}.csv"))
    summ = {}
    for scen in J["scen"].unique().to_list():
        j = J.filter(pl.col("scen") == scen).drop_nulls(["death_rate_truth"])
        if j.height > 3:
            summ[scen] = {q: {"arm_mean": float(j[q].mean()), "truth_mean": float(j[f"{q}_truth"].mean()),
                              "corr": float(np.corrcoef(j[q].to_numpy(), j[f"{q}_truth"].to_numpy())[0, 1])}
                          for q in ("death_rate", "recruits_per_stem")}
    json.dump(summ, open(os.path.join(EVAL, f"dynamics_{a.label}.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


def stage_table(a):
    rows = []
    for d in sorted(glob.glob(os.path.join(SCORES, "*"))):
        lab = os.path.basename(d)
        arm, cl = lab.rsplit("_", 1)
        for scale, sub in (("cell", ""), ("block", "block")):
            f = os.path.join(d, sub, "summary_conjunctive.csv")
            if not os.path.exists(f):
                continue
            s = pl.read_csv(f, infer_schema_length=10000).filter(pl.col("panel") == "panel106")
            for r in s.iter_rows(named=True):
                row = {"arm": arm, "cells": cl, "scale": scale, "gcm": r["gcm"], "scen": r["scen"],
                       "window": r["window"], "role": r.get("role"), "held_out": r.get("held_out"),
                       "n_cells": r["n_cells"]}
                for p in ("cal", "cal_xg"):
                    v, c = r.get(f"all_pass_{p}_frac"), r.get(f"ceiling_same_all_pass_{p}_frac")
                    row[f"pass_{p}"] = v
                    row[f"ceiling_{p}"] = c
                    row[f"ratio_{p}"] = (v / c) if (v is not None and c not in (None, 0)) else None
                rows.append(row)
        pg = os.path.join(d, "primary_gate.csv")
        if os.path.exists(pg):
            for r in pl.read_csv(pg, infer_schema_length=10000).iter_rows(named=True):
                rows.append({"arm": arm, "cells": cl, "scale": r["scale"], "gcm": r["gcm"], "scen": r["scen"],
                             "window": "PRIMARY_" + r["window"], "role": r["role"], "held_out": r["held_out"],
                             "pass_cal_xg": r["arm_cal_xg"], "ceiling_cal_xg": r["ceiling_same_cal_xg"],
                             "ratio_cal_xg": r["ratio_cal_xg"], "verdict": r["verdict"]})
        ag = os.path.join(d, "aggregate_response.csv")
        if os.path.exists(ag):
            g = pl.read_csv(ag, infer_schema_length=10000).filter(pl.col("determined_same").cast(pl.Utf8) == "true")
            for (gcm, scen, win), grp in g.group_by(["gcm", "scen", "window"]):
                rows.append({"arm": arm, "cells": cl, "scale": "aggregate", "gcm": gcm, "scen": scen,
                             "window": win, "n_cells": grp.height,
                             "pass_cal": float((grp["pass_same"].cast(pl.Utf8) == "true").mean())})
    os.makedirs(EVAL, exist_ok=True)
    df = pl.DataFrame(rows, infer_schema_length=None)
    df.write_csv(os.path.join(EVAL, "comparison.csv"))
    pl.Config.set_tbl_rows(60)
    pl.Config.set_tbl_cols(14)
    print(df.filter(pl.col("window").is_in(["h1985", "w2015", "c2015", "r2015"]) & (pl.col("scale") != "aggregate"))
          .select("arm", "cells", "scale", "scen", "window", "pass_cal", "ceiling_cal", "ratio_cal", "pass_cal_xg",
                  "ratio_cal_xg").sort("arm", "cells", "scale", "window", "scen"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["score", "dynamics", "table"])
    ap.add_argument("--run")
    ap.add_argument("--label")
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--start-year", type=int)
    ap.add_argument("--legs-branched", default="unknown")
    ap.add_argument("--held-out-place", default="unknown")
    ap.add_argument("--truth-seed", type=int)
    ap.add_argument("--dependency")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    {"score": stage_score, "dynamics": stage_dynamics, "table": stage_table}[a.stage](a)


if __name__ == "__main__":
    main()
