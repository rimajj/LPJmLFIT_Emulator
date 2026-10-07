"""explore_de_tab_margin.py — LINE X, Germany emulator: the coupled TAB arm whose growth-efficiency SIGN comes from the
per-tree MARGIN model (explore_de_nppmodel2.py arm "MS") instead of the gsign head. Arm "gqm".
(pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "CM, the margin model as the G-SIGN draw")

The C: a tree has a negative-growth year when its NPP falls below its loss (turnover + reproduction + excess + debt).
MS predicts the margin m = log(gain_y1 / L_y1) (mean mu and per-tree spread s) from tree state + the cell's annual and
monthly weather anomalies + thr = log(L_y / gain_y) = the tree's own previous margin with the sign flipped. Here:
  m   = mu + s * Phi^-1(u_s)       u_s = the SAME uniform stream as the shipped sign draw ("tab_gsign"), so G < 0 <=>
                                   u_s < Phi(-mu / s): common random numbers with the gqsc baseline
  G   = gqsc's quantile MAGNITUDE heads, conditioned on that sign (unchanged)
  thr carried per tree (aux_tree "thr" = -m of the last draw); start roster: from its true npp / G / leaf area
      (NaN where undefined or first-printed); recruits: NaN (MS was trained with thr missing on first-printed rows)
The weather inputs are the gsign_info cell-year table (explore_de_nppmodel2.weather), keyed by the transition's start
year y: traj "Historical" for y <= 2013, the leg from 2014 (the table's convention).

Usage (engine):  explore_de_engine.py run --arm tabAL --stepper explore_de_tab_margin:TabALG2HSGQMProbe
                 --kwargs '{"mode": "ar", "param": "bite", "dump_dir": "..."}' --gcm ... --legs ...
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl
from scipy.special import ndtr, ndtri

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_bmdelta as bd  # noqa: E402
import explore_de_gquant as gqm  # noqa: E402
import explore_de_nppmodel2 as n2  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402
import explore_de_tab_probe2 as pr2  # noqa: E402

UCLIP = 1e-9
THR_CLIP = 10.0


def thr_start(t: dict, is_new: np.ndarray) -> np.ndarray:
    """log(L_y / gain_y) of a start roster from its printed npp, G and leaf area (explore_de_bmdelta.side)."""
    typ = t["Type"].astype(np.int64)
    k = np.where(np.isin(typ, bd.NEEDLE), bd.K_NL, bd.K_BL)
    lai, fpc = t["LAI"].astype(np.float64), t["fpc_ind"].astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        la = lai * fpc * bd.PATCHAREA / (1 - np.exp(-k * lai))
        gain = t["npp"].astype(np.float64) * bd.PATCHAREA
        L = gain - t["G"].astype(np.float64) * la
        thr = np.log(L / gain)
    ok = (gain > 0) & (L > 0) & (lai > 0) & (fpc > 0) & np.isfinite(thr) & ~np.asarray(is_new, bool)
    return np.where(ok, thr, np.nan).astype(np.float32)


class TabALG2HSGQM(gqm.TabALG2HSGQ):
    def __init__(self, margin_arm: str = "MS", **kw):
        super().__init__(**kw)
        self.margin_arm = margin_arm
        self._state = self._year = self._traj = self._thr_next = None

    def init(self, state, ctx):
        super().init(state, ctx)
        self.MA = n2.Arm(self.margin_arm)
        W, self.wcols = n2.weather()
        cells = state.cell["cells"]
        W = W.filter((pl.col("gcm") == self.gcm) & (pl.col("seed") == self.seed)
                     & pl.col("Cell").is_in([int(c) for c in cells]))
        # (traj, Year) -> weather matrix aligned with the engine's cell order (NaN where the table has no row)
        self.W = {}
        for (traj, yr), g in W.group_by(["traj", "Year"]):
            M = np.full((len(cells), len(self.wcols)), np.nan, np.float32)
            ci = state.cell_index(g["Cell"].to_numpy().astype(np.int64))
            M[ci] = g.select(self.wcols).to_numpy().astype(np.float32)
            self.W[(str(traj), int(yr))] = M
        thr = thr_start(state.tree, state.aux_tree["is_new"])
        state.aux_tree["thr"] = thr
        tr.log(f"TabALG2HSGQM: margin arm {self.margin_arm} ({len(self.MA.cols)} features), weather "
               f"{len(self.W)} (traj, year) frames; start thr finite {np.isfinite(thr).mean():.3f}, median "
               f"{np.nanmedian(thr):.3f}")

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        self._state, self._year, self._traj = state, int(year), ctx["traj"]
        out = super().step(state, ctx, year, clim_y1, flags_y1, rand)
        assert self._thr_next is not None and len(self._thr_next) == state.n
        out.aux_tree["thr"] = self._thr_next
        nrec = 0 if out.recruits is None else len(out.recruits["Cell"])
        out.aux_recruits = dict(out.aux_recruits or {}, thr=np.full(nrec, np.nan, np.float32))
        self._thr_next = None
        return out

    def _margin_matrix(self, X: pl.DataFrame) -> np.ndarray:
        st, y = self._state, self._year
        assert X.height == st.n, (X.height, st.n)
        traj = "Historical" if y <= 2013 else self._traj
        Wm = self.W.get((traj, y))
        if Wm is None:
            raise KeyError(f"no weather frame for {traj} {y}")
        Wr = Wm[st.cell_index(st.tree["Cell"].astype(np.int64))]
        wi = {c: i for i, c in enumerate(self.wcols)}
        cols = []
        for c in self.MA.cols:
            if c == "thr":
                cols.append(np.asarray(st.aux_tree["thr"], np.float32))
            elif c in wi:
                cols.append(Wr[:, wi[c]])
            else:
                cols.append(X[c].cast(pl.Float32).to_numpy())
        return np.column_stack(cols)

    def _sample_G(self, X, u_s, u_r):
        mu, s = self.MA.pred(self._margin_matrix(X))
        u = np.clip(np.asarray(u_s, np.float64), UCLIP, 1 - UCLIP)
        m = mu + s * ndtri(u)
        p = ndtr(-mu / s)
        neg = m < 0
        # the magnitude of the drawn sign: gq.sample draws neg = u_s < p_eff, so pass p_eff = 1 / 0
        G = self.gq.sample(X, neg.astype(np.float64), u_s, u_r)
        self._thr_next = np.clip(-m, -THR_CLIP, THR_CLIP).astype(np.float32)
        return G, p


class TabALG2HSGQMProbe(pr2._DumpMixin, TabALG2HSGQM):
    """the same with the per-tree dump of explore_de_tab_probe2 (p_gneg = Phi(-mu/s), the margin's own P(G < 0))."""
