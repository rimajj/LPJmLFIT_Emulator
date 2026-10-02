#!/usr/bin/env python3
"""explore_de_hidden_persist.py — LINE X, Germany emulator: is the unseen (< 5 m) tree cover implied by the capped
grass cover a PERSISTENT patch state (worth carrying in the emulator), and what bounds it where the cap does not bind?

h_y = 1 - grass_fpc_y - sum_fpc_y where the cap binds (pot - grass_fpc > 1e-3, pot = 1 - exp(-K LAI_grass));
elsewhere only the upper bound hub_y = 1 - pot_y - sum_fpc_y is known (h_y <= hub_y). Original's stored recruit
features, ACCESS s1 Historical, all 907 dev cells. Reports: P(capped at y+1 | capped at y), corr(h_y, h_y+1) on
both-capped pairs, corr(h_y, recruits_y+1) within tree-cover bins, and the h distribution vs patch age-since-loss.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_grass2 as g2  # noqa: E402
import explore_de_sh_patchheads as ph  # noqa: E402

S = (pl.scan_parquet(os.path.join(ph.FEAT, "ACCESS-CM2_Historical_s1_h1985.parquet"))
     .select("Year", "Cell", "Patch", g2.GF, g2.GL, "sum_fpc_y", "n_recruit_y1", "L0", "L1").collect())
K = g2.Grass2("DEV-A").C["K"]
S = S.with_columns(pot=1 - (-K * pl.col(g2.GL).cast(pl.Float64)).exp()).with_columns(
    capped=(pl.col("pot") - pl.col(g2.GF)) > 1e-3,
    h=1 - pl.col(g2.GF).cast(pl.Float64) - pl.col("sum_fpc_y"),
    hub=1 - pl.col("pot") - pl.col("sum_fpc_y"))
N = S.select("Cell", "Patch", (pl.col("Year") - 1).cast(pl.Int16).alias("Year"),
             pl.col("capped").alias("capped1"), pl.col("h").alias("h1"), pl.col("hub").alias("hub1"))
J = S.join(N, on=["Cell", "Patch", "Year"], how="inner")
c, c1 = J["capped"].to_numpy(), J["capped1"].to_numpy()
print(f"rows {J.height}; P(capped) {c.mean():.3f}; P(capped y+1 | capped y) {c1[c].mean():.3f}; "
      f"P(capped y+1 | not capped y) {c1[~c].mean():.3f}")
b = c & c1
h, h1 = J["h"].to_numpy(), J["h1"].to_numpy()
print(f"both capped: {b.sum()} pairs; corr(h_y, h_y+1) {np.corrcoef(h[b], h1[b])[0, 1]:.3f}; "
      f"median h {np.median(h[b]):.4f}, median dh {np.median(h1[b] - h[b]):+.4f}")
hub = J["hub"].to_numpy()
q = np.quantile(hub[~c], [0.1, 0.9]).round(3)
print(f"not capped: median upper bound on h {np.median(hub[~c]):.3f} (q10/q90 {q})")
rec = J["n_recruit_y1"].cast(pl.Float64).to_numpy()
t = J["sum_fpc_y"].to_numpy()
tb = np.digitize(t, (0.2, 0.3, 0.4, 0.5, 0.6))
for j in range(6):
    m = c & (tb == j)
    if m.sum() > 100:
        print(f"tcov bin {j}: capped n {m.sum()}, corr(h, recruits next yr) {np.corrcoef(h[m], rec[m])[0, 1]:.3f}")
# h after a canopy loss: recruits come from the hidden layer, so h should fall in the year recruits appear
m = c & c1
d = h1[m] - h[m]
r = rec[m]
for k in (0, 1, 2, 3):
    mm = (r >= k) if k == 3 else (r == k)
    print(f"capped both yrs, recruits={k}{'+' if k == 3 else ''}: n {mm.sum()}, mean dh {d[mm].mean():+.4f}")
