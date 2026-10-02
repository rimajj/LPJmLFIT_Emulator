#!/usr/bin/env python3
"""explore_de_recruit_hidden.py — LINE X, Germany emulator: is the original's grass COVER a proxy for the unseen
(< 5 m) trees, and is that what the recruit head reads?

Context (sixth session, explore_de_recruit_grass.py): grass2's one-step grass lowers the recruit head's mean by
7-11 % (907 cells, 1985-2004) although its mean grass cover and LAI match the original's within a few per cent in
the same bins. Hypothesis: in the original, grass fpc = min(1 - exp(-K LAI), 1 - tree_fpc - hidden), i.e. where the
total-cover cap binds the grass cover carries the patch's OWN cover of the unprinted < 5 m trees — the trees that
become next year's recruits. grass2's closure replaces that patch-specific value by a per-tree-cover-bin median.
Tests (original's stored recruit features, ACCESS s1 Historical, 1986-1995, all 907 dev cells):
  T1  head on the original with ONLY the grass fpc replaced by the grass2 closure of the original's own LAI
      (closure(LAI_y, sum_fpc_y)) — keeps LAI/agb exact. Pre-registered: if this alone gives <= -0.06 relative
      (most of grass2's one-step -0.07..-0.11), the cap channel is the cause.
  T2  T1 but closure with NO cap (fpc = 1 - exp(-K LAI)) — the pure Beer-Lambert grass.
  T3  observed recruits per patch-year by the implied hidden cover h = 1 - grass_fpc - sum_fpc_y where the cap binds
      (cap gap > 1e-3), vs patches where it does not, at matched tree cover — does h predict recruits in the TRUTH?
Output: shared/eval/recruit_hidden_<gcm>_s<seed>.csv
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_grass2 as g2  # noqa: E402
import explore_de_sh_patchheads as ph  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gcm", default="ACCESS-CM2")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--y0", type=int, default=1986)
    ap.add_argument("--y1", type=int, default=1995)
    a = ap.parse_args()
    m = f"{a.gcm}_Historical_s{a.seed}_h1985"
    S = (pl.scan_parquet(os.path.join(ph.FEAT, f"{m}.parquet")).filter(pl.col("Year").is_between(a.y0, a.y1))
         .collect().sort("Year", "Cell", "Patch"))
    H = ph.load_heads(a.split)
    C = g2.Grass2(a.split).C
    L = S[g2.GL].cast(pl.Float64).to_numpy()
    gf = S[g2.GF].cast(pl.Float64).to_numpy()
    t = S["sum_fpc_y"].cast(pl.Float64).to_numpy()
    obs = S["n_recruit_y1"].cast(pl.Float64).to_numpy()
    pot = 1 - np.exp(-C["K"] * L)
    fc, _ = g2.closure(L, t, C)
    mu0 = H.recruit_mean(S, kappa=1.0)
    mu1 = H.recruit_mean(S.with_columns(pl.Series(g2.GF, fc).cast(pl.Float32)), kappa=1.0)
    mu2 = H.recruit_mean(S.with_columns(pl.Series(g2.GF, pot).cast(pl.Float32)), kappa=1.0)
    print(f"{S.height} patch-years {a.y0}-{a.y1}; head mean orig {mu0.mean():.4f}  obs {obs.mean():.4f}")
    print(f"T1 closure-fpc of own LAI: rel {mu1.mean() / mu0.mean() - 1:+.4f}   T2 uncapped: rel "
          f"{mu2.mean() / mu0.mean() - 1:+.4f}")
    gap = pot - gf
    bind = gap > 1e-3
    h = np.where(bind, 1 - gf - t, np.nan)
    print(f"cap binds in {bind.mean():.3f} of patch-years; |closure fpc - orig fpc| q50/90/99 "
          f"{np.quantile(np.abs(fc - gf), [0.5, 0.9, 0.99]).round(4).tolist()}")
    rows = []
    tb = np.digitize(t, (0.2, 0.3, 0.4, 0.5, 0.6))
    for j in range(6):
        mt = tb == j
        rows.append(dict(tcov_bin=j, hbin="not capped", n=int((mt & ~bind).sum()),
                         obs_pp=float(obs[mt & ~bind].mean()) if (mt & ~bind).any() else np.nan,
                         mu0=float(mu0[mt & ~bind].mean()) if (mt & ~bind).any() else np.nan,
                         mu1=float(mu1[mt & ~bind].mean()) if (mt & ~bind).any() else np.nan))
        hb = mt & bind
        if hb.sum() > 50:
            qs = np.quantile(h[hb], [0, 0.25, 0.5, 0.75, 1.0])
            qb = np.clip(np.digitize(h, qs[1:-1]), 0, 3)
            for q in range(4):
                mm = hb & (qb == q)
                rows.append(dict(tcov_bin=j, hbin=f"capped h q{q + 1} ({qs[q]:.3f}-{qs[q + 1]:.3f})", n=int(mm.sum()),
                                 obs_pp=float(obs[mm].mean()), mu0=float(mu0[mm].mean()), mu1=float(mu1[mm].mean())))
    R = pl.DataFrame(rows)
    pl.Config.set_tbl_rows(100)
    pl.Config.set_tbl_width_chars(200)
    print("tcov_bin edges (0.2, 0.3, 0.4, 0.5, 0.6); mu0 = head on orig, mu1 = head with closure fpc (T1)")
    print(R.with_columns(pl.selectors.float().round(4)))
    out = os.path.join(g2.EVAL, f"recruit_hidden_{a.gcm}_s{a.seed}.csv")
    R.write_csv(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
