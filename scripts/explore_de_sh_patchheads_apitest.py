"""explore_de_sh_patchheads_apitest.py — LINE X, SH13 helper: check the patch heads can be driven from an SH6 engine
RosterState exactly as a stepper would (patch_frame_from_state -> fire_f / recruit_mean / recruit_draw / entry_sample),
and that the state-built features agree with the SH4-table-built features for the same patches and year.

Usage (SLURM, seconds):  python explore_de_sh_patchheads_apitest.py [--split DEV-A] [--ncell 20]
Writes <patchheads>/<split>/_apitest.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_engine as en  # noqa: E402
import explore_de_sh_patchheads as ph  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--ncell", type=int, default=20)
    a = ap.parse_args(argv)
    H = ph.load_heads(a.split)
    gcm, seed, start = "MPI-ESM1-2-HR", 1, 1985
    member = f"{gcm}_Historical_s{seed}_h{start}"
    F = pl.scan_parquet(os.path.join(ph.FEAT, f"{member}.parquet")).filter(pl.col("Year") == start).collect()
    cells = np.sort(F["Cell"].unique().to_numpy())[: a.ncell].astype(np.int32)
    st = en.load_init(en.init_name(gcm, seed, start, "Historical"), "dev", cells)
    clim = en.Climate(gcm, "Historical", seed, st.cell["cells"]).year(start + 1)
    T = F.filter(pl.col("Cell").is_in(cells.tolist())).sort("Cell", "Patch")
    # the per-tree step outcome of the truth is not in the state: test with "no deaths this step" and compare only
    # the features that do not depend on the step (state at y, loss ring, climate, cell shares)
    n = st.n
    X = ph.patch_frame_from_state(st, clim, np.zeros(n, bool), np.zeros(n, bool),
                                  agb_dead_y=T["agb_dead_y"].cast(pl.Float64).to_numpy())
    rep = {"member": member, "year": start, "n_cells": len(cells), "n_patches": X.height}
    cmp = {}
    cols = ["n_live_y", "sum_fpc_y", "sum_agb_y", "patch_lai_y", "L1", "cell_stems_per_patch", "cell_share_t3",
            "n_eligible_pft_y1", "tmean_ann_y1", "anom_cwb_jja_y1"] + [g for g in T.columns if g.startswith("grass")]
    for c in cols:
        if c not in X.columns:
            cmp[c] = "missing in state frame"
            continue
        a_, b_ = X[c].cast(pl.Float64).to_numpy(), T[c].cast(pl.Float64).to_numpy()
        both = ~(np.isnan(a_) | np.isnan(b_))
        cmp[c] = {"max_abs_diff": float(np.max(np.abs(a_[both] - b_[both]))) if both.any() else None,
                  "max_rel_diff": float(np.max(np.abs(a_[both] - b_[both]) / np.maximum(np.abs(b_[both]), 1e-9)))
                  if both.any() else None,
                  "nan_mismatch": int(np.sum(np.isnan(a_) != np.isnan(b_)))}
    rep["feature_agreement_state_vs_table"] = cmp
    f = H.fire_f(X)
    mu = H.recruit_mean(X)
    rng = np.random.default_rng(1)
    k = H.recruit_draw(mu, rng.random(len(mu)))
    terc = H.clim_tercile(X["tmean_ann_y1"].to_numpy())
    s = H.entry_sample(np.full(5, 3), terc[:5], rng.random(5))
    rep.update(fire_f_mean_state=float(f.mean()), fire_f_mean_table=float(H.fire_f(T).mean()),
               fire_f_min=float(f.min()), recruit_mean_state=float(mu.mean()),
               recruit_mean_table=float(H.recruit_mean(T).mean()), draw_mean=float(k.mean()),
               obs_mean=float(T["n_recruit_y1"].mean()), entry_sample_beech={c: v.tolist() for c, v in s.items()},
               note="state frame uses 'no deaths this step' (fpc_surv = sum_fpc, L0 = 0), the table uses the "
                    "truth's step loss, so recruit means differ by that term only")
    out = os.path.join(H.dir, "_apitest.json")
    json.dump(rep, open(out, "w"), indent=1, default=float)
    print(json.dumps(rep, indent=1, default=float), flush=True)


if __name__ == "__main__":
    main()
