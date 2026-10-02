"""explore_de_tab_g2.py — LINE X, Germany emulator: the A-L tabular stepper with the A3 grass heads replaced by the
grass2 model (explore_de_grass2.py: next-year log grass LAI + a residual draw, cover / biomass by closure).

Everything else is TabAL unchanged (same heads, calibration and random-number streams when run with --arm tabAL;
the grass draws use their own stream "g2_grass", keyed by (cell, patch), so they do not shift any other draw).
  mode = "s"  : iid residual draws (default)      mode = "ar" : AR(1) residual per patch, carried in aux_patch
  mode = "m"  : mean only, no draw

Usage (engine):  explore_de_engine.py run --arm tabAL --stepper explore_de_tab_g2:TabALG2 --kwargs '{"mode": "s"}'
                 --gcm ACCESS-CM2 --seed 1 --start 1985 --end 2044 --legs ssp370 --chunks 0 1
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_grass2 as g2  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_stepper as ts  # noqa: E402


class TabALG2(ts.TabAL):
    def __init__(self, mode: str = "s", **kw):
        super().__init__(**kw)
        assert mode in ("s", "ar", "m"), mode
        self.mode = mode
        self.G2 = None
        self._e = None

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        self._year, self._rand = int(year), rand
        self._e = state.aux_patch.get("g2_e") if state.aux_patch else None
        out = super().step(state, ctx, year, clim_y1, flags_y1, rand)
        if self.mode == "ar" and self._e_new is not None:
            out.aux_patch["g2_e"] = self._e_new
        return out

    def _grass(self, state, Xp, sum_fpc_y, fpc_next, clim_y1):
        if self.G2 is None:
            self.G2 = g2.Grass2(self.split if hasattr(self, "split") else "DEV-A", kappa=self.kappa)
        G = self.G2
        ring = state.patch["loss_ring"]
        X = Xp.select("Cell", "Patch", g2.GF, g2.GL, g2.GA, "sum_fpc_y", "n_live_y", "sum_agb_y").with_columns(
            sum_fpc_y1=pl.Series(fpc_next), d_sum_fpc=pl.Series(fpc_next - sum_fpc_y),
            **{f"frac_loss_lag{k}": pl.Series(ring[:, k].astype(np.float64)) for k in range(3)})
        cf = clim_y1.select(pl.col("Cell").cast(pl.Int16), *[pl.col(f"anom_{f}").alias(f"a_{f}_y1") for f in F.CLIM_F],
                            *[pl.col(f).alias(f"{f}_y1") for f in F.ABS_Y1])
        X = X.join(cf, on="Cell", how="left", maintain_order="left").join(
            F.statics(self.gcm), on="Cell", how="left", maintain_order="left")
        X = g2.add_g2(X)
        z = X["z_y"].to_numpy()
        z1 = z + G.mean_dz(X)
        self._e_new = None
        if self.mode != "m":
            u = self._rand.uniform("g2_grass", self._year, X["Cell"].to_numpy(), X["Patch"].to_numpy())
            b = np.searchsorted(G.edges, z1)
            r = np.empty_like(z1)
            for i in range(10):
                m = b == i
                if m.any():
                    tab = np.sort(G.tabs[i])
                    r[m] = tab[np.minimum((u[m] * len(tab)).astype(np.int64), len(tab) - 1)]
            if self.mode == "ar":
                e0 = self._e if self._e is not None and len(self._e) == len(r) else np.zeros_like(r)
                r = G.rho * e0 + np.sqrt(1 - G.rho ** 2) * r
                self._e_new = r
            z1 = z1 + r
        z1 = np.clip(z1, np.log(g2.EPS), np.log(G.C["LAI_max"] * 1.2 + g2.EPS))
        L = np.maximum(np.exp(z1) - g2.EPS, 0.0)
        fpc, agb = g2.closure(L, np.asarray(fpc_next, np.float64), G.C)
        return {g2.GF[:-2]: fpc, g2.GL[:-2]: L, g2.GA[:-2]: agb}
