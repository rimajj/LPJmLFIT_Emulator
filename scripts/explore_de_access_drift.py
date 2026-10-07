"""explore_de_access_drift.py — LINE X, Germany emulator: is the coupled emulator's stand drift on the OTHER climate
model (ACCESS-CM2 s1 ssp370: recruits +10..+28 % from 2006, stems +8..+16 %, biomass per stem -12..-18 % from 2016) the
grass model's poor transfer across climate models (eighth session: grass2 one step ahead on ACCESS is biased
-0.11/yr in log LAI after 2006), or the tree heads'? (pre-registration: /p/tmp/jamirp/X_de/_status/TS.md,
"ACCESS stand drift, grass counterfactuals")

Two counterfactual steppers on top of the honest-baseline arm (TabALG2HSGQProbe, kwargs as in
_jobs/probe2_g2hsgqsc_acc1.jcf), same random streams:
  GrassLAIOracle   next-year grass LEAF AREA (and biomass = the fixed biomass/LAI ratio) of every patch replayed from
                   the original's patch table; grass COVER still from the carried hidden-cover model, driven by the
                   emulator's own recruits and tree cover — isolates the grass AMOUNT.
  GrassFullOracle  grass leaf area, cover and biomass all replayed (as explore_de_tab_probe.TabALGrassOracle did for
                   the old arm) — adds the cover / hidden-sapling channel.
The original's patches are the same cells and patch indices (the free run starts from its 1985 patches), but after
1985 they are different stands, so a replay pastes the original's grass onto another roster: an attribution, not an
upper bound (fifth session).
Usage: as a --stepper of explore_de_engine.py run, e.g. explore_de_access_drift:GrassLAIOracle
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_gquant as gq  # noqa: E402
import explore_de_grass2 as g2  # noqa: E402
import explore_de_tab_features as F  # noqa: E402
import explore_de_tab_stepper as ts  # noqa: E402


def _member(gcm: str, seed: int, leg: str, y1: int) -> str:
    # same split as explore_de_tab_probe.TabALGrassOracle (verified there against the patch tables)
    return f"{gcm}_Historical_s{seed}_h1985" if y1 <= 2013 else f"{gcm}_{leg}_s{seed}_w2015"


class _OracleMixin:
    LEG = os.environ.get("XDE_ORACLE_LEG", "ssp370")
    SEED = int(os.environ.get("XDE_ORACLE_SEED", "1"))

    def _orig(self, X: pl.DataFrame):
        """the original's next-year grass (fpc, LAI, agb) aligned to the rows of X; None if untabulated."""
        y1 = int(self._year) + 1
        try:
            f = F.patch_file(_member(self.gcm, self.SEED, self.LEG, y1), y1)
        except AssertionError:
            ts.log(f"grass oracle: no original grass for {y1}; using the model")
            return None
        T = pl.read_parquet(f, columns=["Cell", "Patch", g2.GF, g2.GL, g2.GA]).with_columns(
            pl.col("Cell").cast(pl.Int64), pl.col("Patch").cast(pl.Int64))
        K = X.select(pl.col("Cell").cast(pl.Int64), pl.col("Patch").cast(pl.Int64)).join(
            T, on=["Cell", "Patch"], how="left", maintain_order="left")
        out = {c: K[c].cast(pl.Float64).to_numpy() for c in (g2.GF, g2.GL, g2.GA)}
        assert all(np.isfinite(v).all() for v in out.values()), "original grass missing for some patches"
        return out


class GrassLAIOracle(_OracleMixin, gq.TabALG2HSGQProbe):
    def _cover(self, X, L, fpc_next):
        o = self._orig(X)
        if o is not None:
            L = np.maximum(o[g2.GL], 0.0)
        self._L_used = L
        return super()._cover(X, L, fpc_next)

    def _grass(self, state, Xp, sum_fpc_y, fpc_next, clim_y1):
        out = super()._grass(state, Xp, sum_fpc_y, fpc_next, clim_y1)
        out[g2.GL[:-2]] = self._L_used  # the LAI the cover was computed from (replayed when tabulated)
        return out


class GrassFullOracle(_OracleMixin, gq.TabALG2HSGQProbe):
    def _cover(self, X, L, fpc_next):
        o = self._orig(X)
        if o is None:
            self._full = None
            return super()._cover(X, L, fpc_next)
        self._full = o
        return o[g2.GF], o[g2.GA]

    def _grass(self, state, Xp, sum_fpc_y, fpc_next, clim_y1):
        out = super()._grass(state, Xp, sum_fpc_y, fpc_next, clim_y1)
        if self._full is not None:
            out[g2.GL[:-2]] = self._full[g2.GL]
        return out
