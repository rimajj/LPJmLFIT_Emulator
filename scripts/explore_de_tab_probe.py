"""explore_de_tab_probe.py — LINE X, Germany emulator: an INSTRUMENTED A-L stepper that records, for every printed
living tree at or above a height cut, the exact inputs and intermediate values of the growth chain in the free run.

It is TabAL unchanged (same heads, same calibration, same random-number streams: run it with --arm tabAL so the
engine's Rand is the one the analysed run used) plus a side dump per step:
  <dump_dir>/<traj>/y<Y>_c<firstcell>.parquet  with the key (Cell, Patch, Type, ID, SLA, Wooddens), Year (= y, the
  state year), every feature the gsign / gmag_* / dagb heads read, and the step's G1 (sampled G_{y+1}), p_gneg, c1,
  mu_dagb (growth head mean at G1, c1), e_prev (carried AR residual), e_new, da (= mu_dagb + e_new).
Gate (run by explore_de_growth_attrib.py): the probe run's emitted rosters must equal the analysed tabAL run's
chunk files exactly, or the dump does not describe that run.

Usage (engine):  explore_de_engine.py run --arm tabAL --stepper explore_de_tab_probe:TabALProbe
                 --kwargs '{"dump_dir": "...", "hcut": 12.0}' --gcm ACCESS-CM2 --seed 1 --start 1985 --end 2044
                 --legs ssp370 --chunks 0
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_tab_stepper as ts  # noqa: E402

KEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]


class TabALProbe(ts.TabAL):
    def __init__(self, dump_dir: str, hcut: float = 12.0, **kw):
        super().__init__(**kw)
        self.dump_dir, self.hcut = dump_dir, float(hcut)
        self._st = {}

    def init(self, state, ctx):
        super().init(state, ctx)
        m = self.H.m
        cols = []
        for h in ("gsign", "gmag_neg", "gmag_pos", "dagb"):
            cols += m[h][2]["features_B0"] + m[h][2]["features_B1"]
        self.cols = [c for c in dict.fromkeys(cols) if c not in KEY + ["G_y1", "c_y1"]]

    def _sample_G(self, X, u_s, u_r):
        G1, p = super()._sample_G(X, u_s, u_r)
        self._st.update(X=X, G1=G1, p=p)
        return G1, p

    def _growth(self, X, G1, c1, e_prev, z):
        da, dv, e_new = super()._growth(X, G1, c1, e_prev, z)
        self._st.update(c1=c1, e_prev=np.nan_to_num(e_prev["dagb"]), e_new=e_new["dagb"], da=da)
        return da, dv, e_new

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        out = super().step(state, ctx, year, clim_y1, flags_y1, rand)
        t, s = state.tree, self._st
        m = ~t["hidden"] & ~t["isdead"] & (t["Height"] >= self.hcut)
        idx = np.flatnonzero(m)
        X = s["X"]
        D = pl.DataFrame({k: t[k][idx] for k in KEY}).with_columns(Year=pl.lit(int(year), pl.Int16))
        D = pl.concat([D, X[idx].select([pl.col(c).cast(pl.Float32) for c in self.cols])], how="horizontal")
        D = D.with_columns(
            G1=pl.Series(s["G1"][idx].astype(np.float32)), p_gneg=pl.Series(s["p"][idx].astype(np.float32)),
            c1=pl.Series(np.asarray(s["c1"])[idx].astype(np.int8)),
            mu_dagb=pl.Series((s["da"][idx] - s["e_new"][idx]).astype(np.float32)),
            e_prev=pl.Series(s["e_prev"][idx].astype(np.float32)),
            e_new=pl.Series(s["e_new"][idx].astype(np.float32)), da=pl.Series(s["da"][idx].astype(np.float32)))
        od = os.path.join(self.dump_dir, ctx["traj"])
        os.makedirs(od, exist_ok=True)
        D.write_parquet(os.path.join(od, f"y{int(year)}_c{int(state.cell['cells'][0])}.parquet"),
                        compression="zstd")
        self._st = {}
        return out


class TabALGrassOracle(TabALProbe):
    """Counterfactual: TabALProbe with the next-year grass of every patch REPLAYED from the original model's patch
    table (same cell, same patch index — the free run starts from the original's 1985 patches), everything else
    unchanged (same heads, same random numbers when run with --arm tabAL). The original's grass of the last year
    (2044) is not tabulated; that one step falls back to the grass heads (counted in the log)."""

    MEMBERS = {"Historical": "ACCESS-CM2_Historical_s1_h1985", "ssp370": "ACCESS-CM2_ssp370_s1_w2015"}

    def _grass(self, state, Xp, sum_fpc_y, fpc_next, clim_y1):
        import explore_de_tab_features as F

        y1 = int(self._year) + 1
        m = self.MEMBERS["Historical" if y1 <= 2013 else "ssp370"]
        try:
            f = F.patch_file(m, y1)
        except AssertionError:
            ts.log(f"grass oracle: no original grass for {y1}; using the grass heads")
            return super()._grass(state, Xp, sum_fpc_y, fpc_next, clim_y1)
        cells = state.cell["cells"]
        T = pl.read_parquet(f, columns=["Cell", "Patch", "grass8_fpc_y", "grass8_LAI_y", "grass8_agb_y"]).filter(
            pl.col("Cell").is_in(cells.tolist()))
        npt = len(cells) * state.npatch
        assert T.height == npt, (T.height, npt)
        pi = state.cell_index(T["Cell"].to_numpy()) * state.npatch + T["Patch"].to_numpy().astype(np.int64)
        out = {}
        for v in ("fpc", "LAI", "agb"):
            a = np.full(npt, np.nan, np.float32)
            a[pi] = T[f"grass8_{v}_y"].cast(pl.Float32).to_numpy()
            assert np.isfinite(a).all()
            out[f"grass8_{v}"] = a
        return out

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        self._year = year
        return super().step(state, ctx, year, clim_y1, flags_y1, rand)
