"""explore_de_tab_probe2.py — LINE X, Germany emulator: instrumented copies of the coupled TAB arms with the new grass
model (TabALG2, closure) and the carried hidden cover (TabALG2HS), dumping for EVERY printed living tree (no height
cut by default) the exact inputs of the growth-efficiency, growth and survival heads and the step's draws.

Same heads, same calibration, same random-number streams as the scored arms when run with --arm tabAL, so the
emitted rosters must equal the scored run's chunk files (gate in explore_de_tree_attrib.py).
Dump: <dump_dir>/<traj>/y<Y>_c<firstcell>.parquet with the key (Cell, Patch, Type, ID, SLA, Wooddens), Year (= y),
every feature of gsign / gmag_* / dagb / surv, and G1, p_gneg, c1, mu_dagb, e_prev, e_new, da, p_death.

Usage (engine):  explore_de_engine.py run --arm tabAL --stepper explore_de_tab_probe2:TabALG2HSProbe
                 --kwargs '{"mode": "ar", "param": "bite", "dump_dir": "..."}' --gcm MPI-ESM1-2-HR --seed 2 ...
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_tab_g2 as tg2  # noqa: E402

KEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]
HEADS = ("gsign", "gmag_neg", "gmag_pos", "dagb", "surv")


class _DumpMixin:
    def __init__(self, dump_dir: str, hcut: float = 0.0, **kw):
        super().__init__(**kw)
        self.dump_dir, self.hcut = dump_dir, float(hcut)
        self._st = {}

    def init(self, state, ctx):
        super().init(state, ctx)
        cols = []
        for h in HEADS:
            meta = self.H.m[h][2]
            cols += meta["features_B0"] + meta["features_B1"]
        self.cols = [c for c in dict.fromkeys(cols) if c not in KEY + ["G_y1", "c_y1"]]

    def _sample_G(self, X, u_s, u_r):
        G1, p = super()._sample_G(X, u_s, u_r)
        self._st.update(X=X, G1=G1, p=p)
        return G1, p

    def _growth(self, X, G1, c1, e_prev, z):
        da, dv, e_new = super()._growth(X, G1, c1, e_prev, z)
        self._st.update(c1=c1, e_prev=np.nan_to_num(e_prev["dagb"]), e_new=e_new["dagb"], da=da)
        return da, dv, e_new

    def _p_death_learned(self, X, G1, c1):
        p = super()._p_death_learned(X, G1, c1)
        self._st["pd"] = p
        return p

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
            e_new=pl.Series(s["e_new"][idx].astype(np.float32)), da=pl.Series(s["da"][idx].astype(np.float32)),
            p_death=pl.Series(np.asarray(s.get("pd", np.full(len(t["Cell"]), np.nan)))[idx].astype(np.float32)))
        od = os.path.join(self.dump_dir, ctx["traj"])
        os.makedirs(od, exist_ok=True)
        D.write_parquet(os.path.join(od, f"y{int(year)}_c{int(state.cell['cells'][0])}.parquet"),
                        compression="zstd")
        self._st = {}
        return out


class TabALG2Probe(_DumpMixin, tg2.TabALG2):
    pass


class TabALG2HSProbe(_DumpMixin, tg2.TabALG2HS):
    pass
