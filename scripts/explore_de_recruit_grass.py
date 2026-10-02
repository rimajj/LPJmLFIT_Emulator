#!/usr/bin/env python3
"""explore_de_recruit_grass.py — LINE X, Germany emulator: does the recruit head under-recruit because it READS the
grass2 model's grass, with the trees held exactly at the original's?

Context (fifth session, 2026-10-02): TAB + grass2 recruits ~11-20 % too few in 1987-2010 while the old TAB recruited
too many. In the coupled runs the 1986 tree roster is identical across the TAB arms (same random streams), so the
1987 recruit difference (grass2 0.335 vs grass-replay 0.381 per patch, truth 0.368) is the 1986 grass alone. This
probe repeats that test on the ORIGINAL's trees for every year, so that no tree drift is mixed in.

Method (read-only; no emulator run):
  grass at state year y from seven sources, everything else = the original's stored recruit-head features:
    orig      the original's grass                          (the gate: head mean == stored-feature head mean)
    persist   the 1985 grass held forever                   (a reference, not a model)
    G2m_1     grass2 mean, one step from the original's y-1 grass + trees
    G2s_1     grass2 with an iid residual draw, one step
    A3_free   the old A3 heads, grass-only free run from 1985 on the original's trees
    G2m_free  grass2 mean, grass-only free run
    G2ar_free grass2 with AR(1) draws, grass-only free run (the arm the coupled run used)
  summed recruit-head mean per patch-year, by year; and in 1986-1995 split by the ORIGINAL's tree cover and by the
  original's grass level, with each source's mean grass in the same bins (so a recruit gap can be traced to a grass
  gap in the same patches).
Output: shared/eval/recruit_grass_<gcm>_s<seed>_<leg>{,_bins}.csv
Pre-registration: _status/RG.md (written before the run).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_grass2 as g2  # noqa: E402
import explore_de_sh_patchheads as ph  # noqa: E402

XDE = g2.XDE
EVAL = g2.EVAL
GCOLS = (g2.GF, g2.GL, g2.GA)


def stored(gcm, seed, leg, cells):
    parts = []
    for m in (f"{gcm}_Historical_s{seed}_h1985", f"{gcm}_{leg}_s{seed}_w2015"):
        parts.append(pl.scan_parquet(os.path.join(ph.FEAT, f"{m}.parquet")).filter(pl.col("Cell").is_in(cells)))
    S = pl.concat(parts, how="diagonal_relaxed").collect().sort("Year", "Cell", "Patch")
    assert S.select("Year", "Cell", "Patch").n_unique() == S.height, "duplicate stored keys"
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gcm", default="ACCESS-CM2")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--max-cells", type=int, default=0)
    ap.add_argument("--chunk-cells", type=int, default=200, help="the first N cells = the coupled runs' chunks 0-1")
    a = ap.parse_args()
    t0 = time.time()
    cells = sorted(pl.read_parquet(g2.F.patch_file(f"{a.gcm}_Historical_s{a.seed}_h1985", 1985),
                                   columns=["Cell"])["Cell"].unique().to_list())
    if a.max_cells:
        cells = cells[: a.max_cells]
    D = g2.original_series(a.gcm, a.seed, a.leg, cells)
    S = stored(a.gcm, a.seed, a.leg, cells)
    years = sorted(D["Year"].unique().to_list())
    byD = {y: g for (y,), g in D.partition_by("Year", as_dict=True, maintain_order=True).items()}
    byS = {y: g for (y,), g in S.partition_by("Year", as_dict=True, maintain_order=True).items()}
    ref = byD[years[0]].select("Cell", "Patch")
    for y in years:
        assert byD[y].select("Cell", "Patch").equals(ref), f"patch set changes in {y} (series)"
        assert byS[y].select("Cell", "Patch").equals(ref), f"patch set differs in {y} (stored vs series)"
    sub200 = np.isin(ref["Cell"].to_numpy(), cells[: a.chunk_cells])
    print(f"{a.gcm} s{a.seed} {a.leg}: {len(cells)} cells, {ref.height} patches, state years {years[0]}..{years[-1]}"
          f" ({time.time() - t0:.0f} s)", flush=True)
    H = ph.load_heads(a.split)
    G2 = g2.Grass2(a.split, kappa=1.0)
    A3 = g2.A3Old(a.split, kappa=1.0)
    # ---- gate 1: the patch table's grass == the stored recruit features' grass (same quantity, two pipelines)
    gate = {}
    for c in GCOLS:
        x = np.concatenate([byD[y][c].cast(pl.Float64).to_numpy() for y in years])
        s = np.concatenate([byS[y][c].cast(pl.Float64).to_numpy() for y in years])
        gate[c] = float(np.max(np.abs(x - s)))
    print("GATE grass series vs stored (max abs):", json.dumps(gate), flush=True)
    assert max(gate.values()) < 1e-5, "grass in the patch series != grass in the stored recruit features"
    rng = {"G2s_1": np.random.default_rng(11), "G2ar_free": np.random.default_rng(12)}
    free = {k: {v: byD[years[0]][c].cast(pl.Float64).to_numpy().copy() for v, c in zip(GCOLS, GCOLS, strict=True)}
            for k in ("A3_free", "G2m_free", "G2ar_free")}
    persist = {c: byD[years[0]][c].cast(pl.Float64).to_numpy().copy() for c in GCOLS}
    e_prev = np.zeros(ref.height)
    one = {}
    rows, bins = [], []
    for i, y in enumerate(years):
        Sy = byS[y]
        src = {"orig": {c: Sy[c].cast(pl.Float64).to_numpy() for c in GCOLS}, "persist": persist}
        if i > 0:
            src.update(one)
            for k in free:
                src[k] = free[k]
        mu = {}
        for k, g in src.items():
            X = Sy.with_columns(*[pl.Series(c, g[c]).cast(pl.Float32) for c in GCOLS])
            mu[k] = H.recruit_mean(X, kappa=1.0)
        if i == 0:
            mu_st = H.recruit_mean(Sy, kappa=1.0)
            gate["_mu_orig_vs_stored_rel"] = float(abs(mu["orig"].sum() / mu_st.sum() - 1))
            print("GATE head(orig grass) vs head(stored):", gate["_mu_orig_vs_stored_rel"], flush=True)
            assert gate["_mu_orig_vs_stored_rel"] < 1e-6
        obs = Sy["n_recruit_y1"].cast(pl.Float64).to_numpy()
        tcov = Sy["sum_fpc_y"].cast(pl.Float64).to_numpy()
        gtrue = src["orig"][g2.GF]
        for k in src:
            for sub, m in (("all", np.ones(ref.height, bool)), ("c200", sub200)):
                rows.append(dict(Year=y, src=k, cells=sub, mu_pp=float(mu[k][m].mean()),
                                 obs_pp=float(obs[m].mean()), grass_fpc_mean=float(src[k][g2.GF][m].mean()),
                                 grass_lai_mean=float(src[k][g2.GL][m].mean()),
                                 p_grass_lt1e3=float((src[k][g2.GF][m] < 1e-3).mean())))
        if y <= 1995 and i > 0:
            for bname, v, edges in (("tcov", tcov, (0, 0.2, 0.3, 0.4, 0.5, 0.6, 1.01)),
                                    ("gtrue", gtrue, (0, 1e-3, 0.05, 0.2, 0.4, 0.6, 1.01))):
                b = np.digitize(v, edges) - 1
                for j in range(len(edges) - 1):
                    m = b == j
                    if not m.any():
                        continue
                    for k in src:
                        bins.append(dict(Year=y, by=bname, lo=edges[j], hi=edges[j + 1], src=k, n=int(m.sum()),
                                         mu_sum=float(mu[k][m].sum()), obs_sum=float(obs[m].sum()),
                                         grass_fpc_mean=float(src[k][g2.GF][m].mean()),
                                         grass_lai_mean=float(src[k][g2.GL][m].mean()),
                                         grass_agb_mean=float(src[k][g2.GA][m].mean())))
        # ---- advance the grass sources to y+1 (one-step from the original's y; free runs from their own y)
        if i == len(years) - 1:
            break
        X0 = byD[y]
        t1 = X0["sum_fpc_y1"].to_numpy().astype(np.float64)
        Xo = g2.add_g2(X0)
        fp, L, ag, _ = G2.step(Xo, t1)
        one = {"G2m_1": {g2.GF: fp, g2.GL: L, g2.GA: ag}}
        fp, L, ag, _ = G2.step(Xo, t1, rng["G2s_1"])
        one["G2s_1"] = {g2.GF: fp, g2.GL: L, g2.GA: ag}
        for k in free:
            X = g2.add_g2(X0.with_columns(*[pl.Series(c, free[k][c]) for c in GCOLS]))
            if k == "A3_free":
                fp, L, ag = A3.step(X)
            elif k == "G2m_free":
                fp, L, ag, _ = G2.step(X, t1)
            else:
                fp, L, ag, e_prev = G2.step(X, t1, rng["G2ar_free"], e_prev, ar=True)
            free[k] = {g2.GF: np.asarray(fp, np.float64), g2.GL: np.asarray(L, np.float64),
                       g2.GA: np.asarray(ag, np.float64)}
        if y % 10 == 0:
            print(f"  {y} done ({time.time() - t0:.0f} s)", flush=True)
    tag = f"{a.gcm}_s{a.seed}_{a.leg}" + (f"_c{a.max_cells}" if a.max_cells else "")
    R = pl.DataFrame(rows)
    B = pl.DataFrame(bins)
    R.write_csv(os.path.join(EVAL, f"recruit_grass_{tag}.csv"))
    B.write_csv(os.path.join(EVAL, f"recruit_grass_{tag}_bins.csv"))
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_width_chars(250)
    for sub in ("all", "c200"):
        W = (R.filter(pl.col("cells") == sub).with_columns(win=pl.col("Year") // 5 * 5)
             .group_by("win", "src").agg(pl.col("mu_pp").mean(), pl.col("obs_pp").mean()))
        base = W.filter(pl.col("src") == "orig").select("win", pl.col("mu_pp").alias("mu_orig"))
        W = W.join(base, on="win").with_columns(rel=pl.col("mu_pp") / pl.col("mu_orig") - 1)
        print(f"--- {sub}: recruit-head mean per patch-year relative to the head on the original's grass")
        print(W.pivot(on="src", index="win", values="rel").sort("win").with_columns(pl.exclude("win").round(4)))
    Bs = (B.group_by("by", "lo", "hi", "src").agg(pl.col("n").sum(), pl.col("mu_sum").sum(), pl.col("obs_sum").sum(),
                                                 (pl.col("grass_fpc_mean") * pl.col("n")).sum().alias("_g"),
                                                 (pl.col("grass_lai_mean") * pl.col("n")).sum().alias("_l"))
          .with_columns(mu_pp=pl.col("mu_sum") / pl.col("n"), obs_pp=pl.col("obs_sum") / pl.col("n"),
                        g=pl.col("_g") / pl.col("n"), lai=pl.col("_l") / pl.col("n")))
    print("--- 1986-1995, by bin: recruit-head mean per patch-year (mu) and mean grass cover (g)")
    for v in ("mu_pp", "g", "lai"):
        print(Bs.pivot(on="src", index=["by", "lo", "hi"], values=v).sort("by", "lo")
              .with_columns(pl.selectors.float().round(4)))
    print(Bs.filter(pl.col("src") == "orig").select("by", "lo", "n", "obs_pp").sort("by", "lo"))
    print("wrote", os.path.join(EVAL, f"recruit_grass_{tag}.csv"), f"({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
