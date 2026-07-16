"""Direct (non-recursive) climate -> distribution emulator (component S baseline).

For any (Cell, Year) the :class:`DirectEmulator` predicts the stand's per-variable
distribution DIRECTLY from climate features and renders a tree table by reusing an
allometric fan-out + trait machinery. There is NO recursion over years, so the model
is structurally drift-free at any horizon (2100 SSP included).

Model pieces
------------
  count_        LightGBM Poisson: mean living stems / patch (per Cell,Year) + NB dispersion
  frac_[t]      LightGBM regressor: fraction of stems that are PFT t (t in 0..6), renormalised
  axis_[t][a]   ResidualRegressor: climate-conditioned marginal of axis a for PFT t,
                a in {logHeight, Age, SLA, Wooddens, beta_root}
  copula_[t]    5x5 within-stand Gaussian-copula correlation of the 5 axes for PFT t
                (so a rendered stand reproduces logH~Age 0.70, logH~Wooddens -0.23, ...)
  fanout_[v]    ResidualRegressor: agb/vegc/npp/LAI/fpc_ind/D95/transp/minwscal/k_root
                from logHeight+Age+traits+competition+static+climate (reused fan-out)
  link_*        Longevity=f(SLA), D95max=g(beta_root)
  wscal_*       dedicated TWO-PART water-stress model (spike at ~1 + value when stressed)
  grass_[v]     reused grass sub-model

Rendering a year (all cells at once, vectorised):
  count -> per-patch NB draw -> assign PFT by fractions -> per PFT, draw copula-correlated
  uniforms and map each axis through its climate-conditioned marginal -> competition ->
  fan-out -> wscal -> links -> grass. Joint structure is consistent BY CONSTRUCTION.

This module also carries the shared LightGBM baseline pieces (``LGB_COMMON``,
:func:`add_competition`, :class:`ResidualRegressor`) that the emulator builds on.

Provenance: ported once on 2026-07-16 from the frozen sibling emulator module(s)
direct_emulator.py and ibm_model.py (only LGB_COMMON, add_competition and
ResidualRegressor) (newest sibling source mtime 2026-07-14). This repository is the
single source of truth for component S; the sibling is frozen (ADR 0012) — port once,
do not sync.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from scipy import stats as sps

from .features import AXES, CLIM, FEATURES, STATIC, TREE_TYPES
from .transforms import MonotoneLink

__all__ = ["LGB_COMMON", "add_competition", "ResidualRegressor", "DirectEmulator"]

LGB_COMMON = dict(
    n_estimators=400,
    num_leaves=63,
    learning_rate=0.05,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    min_child_samples=100,
    n_jobs=-1,
    verbosity=-1,
)


# ==========================================================================
# Competition features (single source of truth; used at train prep & rollout)
# ==========================================================================
def add_competition(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-(Cell,Patch) competition features to a single-year tree table (pandas)."""
    g = df.groupby(["Cell", "Patch"], sort=False)
    df = df.copy()
    df["comp_n"] = g["Height"].transform("size")
    df["comp_meanH"] = g["Height"].transform("mean")
    df["comp_maxH"] = g["Height"].transform("max")
    sumH = g["Height"].transform("sum")
    df["comp_relH"] = df["Height"] / df["comp_maxH"].clip(lower=1e-6)
    df["comp_rankfrac"] = g["Height"].rank(method="average") / df["comp_n"]
    df["comp_crowd"] = (sumH - df["Height"]) / df["comp_maxH"].clip(lower=1e-6)
    if "LAI" in df:
        df["comp_totLAI"] = g["LAI"].transform("sum")
        df["comp_totfpc"] = g["fpc_ind"].transform("sum")
        df["comp_openness"] = (1.0 - df["comp_totfpc"]).clip(lower=0.0)
    return df


# ==========================================================================
# Reusable regressor with empirical residual resampling (heteroscedastic)
# ==========================================================================
class ResidualRegressor:
    """LightGBM mean (optionally in log space) + residuals binned by predicted
    value, resampled at generation time to reproduce the conditional spread &
    marginal shape (incl. skew/heavy tails)."""

    def __init__(self, log_target=False, n_bins=12, max_pool=20000, pool_seed=0, **lgb):
        self.log_target = log_target
        self.n_bins = n_bins
        self.max_pool = max_pool  # cap stored residuals per bin (memory at scale)
        self.pool_seed = pool_seed
        self.lgb = {**LGB_COMMON, **lgb}

    def _fwd(self, y):
        return np.log1p(np.clip(y, 0, None)) if self.log_target else np.asarray(y, float)

    def _inv(self, z):
        return np.clip(np.expm1(z), 0, None) if self.log_target else z

    def fit(self, X, y):
        yz = self._fwd(y)
        self.model_ = LGBMRegressor(**self.lgb).fit(X, yz)
        pred = self.model_.predict(X)
        resid = yz - pred
        # bin residuals by predicted quantile for heteroscedasticity
        edges = np.quantile(pred, np.linspace(0, 1, self.n_bins + 1))
        self._edges = np.unique(edges)
        prng = np.random.default_rng(self.pool_seed)

        def _cap(a):
            a = np.asarray(a, float)
            if self.max_pool and a.size > self.max_pool:
                a = prng.choice(a, self.max_pool, replace=False)
            return a

        self._resid_bins = []
        idx = np.clip(np.searchsorted(self._edges, pred) - 1, 0, len(self._edges) - 2)
        for b in range(len(self._edges) - 1):
            r = resid[idx == b]
            self._resid_bins.append(_cap(r if r.size > 20 else resid))
        self._resid_all = _cap(resid)
        self.features_ = list(X.columns)
        return self

    def predict_mean(self, X):
        return self._inv(self.model_.predict(X[self.features_]))

    def sample(self, X, rng):
        pred = self.model_.predict(X[self.features_])
        idx = np.clip(np.searchsorted(self._edges, pred) - 1, 0, len(self._edges) - 2)
        out = np.empty_like(pred)
        for b in range(len(self._edges) - 1):
            mask = idx == b
            if mask.any():
                pool = self._resid_bins[b]
                out[mask] = pred[mask] + rng.choice(pool, size=mask.sum(), replace=True)
        return self._inv(out)

    def sample_u(self, X, u):
        """Copula-driven sampling: instead of resampling a random residual, take the
        empirical residual at supplied uniform quantile `u` (per row, in [0,1]).
        Preserves the rank given by `u` so several ResidualRegressors can be coupled
        by correlated uniforms while each keeps its climate-conditioned mean + shape."""
        pred = self.model_.predict(X[self.features_])
        idx = np.clip(np.searchsorted(self._edges, pred) - 1, 0, len(self._edges) - 2)
        u = np.clip(np.asarray(u, float), 1e-6, 1 - 1e-6)
        out = np.empty_like(pred)
        for b in range(len(self._edges) - 1):
            mask = idx == b
            if mask.any():
                pool = np.sort(self._resid_bins[b])
                out[mask] = pred[mask] + np.quantile(pool, u[mask])
        return self._inv(out)

    def resid_rank(self, X, y):
        """Return the standard-normal score of each observation's residual within its
        predicted-value bin (used to estimate the within-stand copula correlation)."""
        pred = self.model_.predict(X[self.features_])
        resid = self._fwd(y) - pred
        return resid


# ------------------------- feature definitions ---------------------------
TRAITS = ["SLA", "Wooddens", "beta_root"]
COMP_HEIGHT = ["comp_n", "comp_meanH", "comp_maxH", "comp_relH", "comp_rankfrac", "comp_crowd"]
COMP_CANOPY = ["comp_totLAI", "comp_totfpc", "comp_openness"]
FANOUT_FEATS = ["logHeight", "Age"] + TRAITS + COMP_HEIGHT + STATIC + CLIM
FANOUT_LOG = ["agb", "vegc", "npp", "LAI", "fpc_ind", "D95", "transp"]
FANOUT_LIN = ["minwscal", "k_root"]
FANOUT_DIAG = FANOUT_LOG + FANOUT_LIN  # wscal_mean handled by the dedicated model
GRASS_FEATS = ["comp_n", "comp_meanH", "comp_maxH"] + COMP_CANOPY + STATIC + CLIM
WSCAL_FEATS = [
    "temp",
    "prec",
    "swrad",
    "temp_anom",
    "prec_anom",
    "swrad_anom",
    "temp_mean",
    "prec_mean",
    "soil_code",
    "soil_depth",
    "logHeight",
]

HEIGHT_FLOOR = 5.0
HEIGHT_CAP = 45.0
WSCAL_HI = 0.99


def _nearest_corr(R):
    R = np.atleast_2d(np.asarray(R, float))
    R[~np.isfinite(R)] = 0.0
    np.fill_diagonal(R, 1.0)
    ev, V = np.linalg.eigh(R)
    ev = np.clip(ev, 1e-6, None)
    R = V @ np.diag(ev) @ V.T
    d = np.sqrt(np.diag(R))
    return R / np.outer(d, d)


class DirectEmulator:
    def __init__(self, seed=42, n_patches_default=25):
        self.seed = seed
        self.n_patches_default = n_patches_default

    # ------------------------------------------------------------------ fit
    def fit(self, tree, count, frac, tree_step, grass):
        self.count_ = LGBMRegressor(objective="poisson", **LGB_COMMON).fit(
            count[FEATURES], count["stems"].values
        )
        mu, var = float(count["stems"].mean()), float(count["stems"].var())
        self.count_nb_r_ = max(mu * mu / max(var - mu, 1e-6), 0.5) if var > mu else 1e6

        self.frac_ = {}
        for t in TREE_TYPES:
            self.frac_[t] = LGBMRegressor(**LGB_COMMON).fit(frac[FEATURES], frac[f"f{t}"].values)

        self.axis_, self.copula_ = {}, {}
        for t in TREE_TYPES:
            sub = tree[tree["Type"] == t]
            self.axis_[t] = {}
            resid = np.empty((len(sub), len(AXES)))
            for j, a in enumerate(AXES):
                rr = ResidualRegressor(log_target=False, n_bins=16).fit(
                    sub[FEATURES], sub[a].values
                )
                self.axis_[t][a] = rr
                resid[:, j] = rr.resid_rank(sub[FEATURES], sub[a].values)
            # copula on normal-scored residuals (within-conditional-mean coupling)
            Z = np.empty_like(resid)
            n = len(sub)
            for j in range(len(AXES)):
                Z[:, j] = sps.norm.ppf(sps.rankdata(resid[:, j]) / (n + 1))
            self.copula_[t] = _nearest_corr(np.corrcoef(Z, rowvar=False))

        ts = tree_step.copy()
        ts["logHeight"] = np.log(ts["Height"].clip(lower=HEIGHT_FLOOR))
        self.fanout_ = {}
        for v in FANOUT_DIAG:
            self.fanout_[v] = ResidualRegressor(log_target=(v in FANOUT_LOG), n_bins=16).fit(
                ts[FANOUT_FEATS], ts[v].values
            )

        self.link_long_ = MonotoneLink(increasing=False).fit(
            ts["SLA"].values, ts["Longevity"].values
        )
        self.link_d95max_ = MonotoneLink(increasing="auto").fit(
            ts["beta_root"].values, ts["D95max"].values
        )

        tw = tree.copy()
        hi = (tw["wscal_mean"].values >= WSCAL_HI).astype(int)
        self.wscal_clf_ = LGBMClassifier(**LGB_COMMON).fit(tw[WSCAL_FEATS], hi)
        self.wscal_hi_pool_ = tw.loc[tw["wscal_mean"] >= WSCAL_HI, "wscal_mean"].values
        low = tw[tw["wscal_mean"] < WSCAL_HI]
        self.wscal_lo_ = ResidualRegressor(log_target=False, n_bins=16).fit(
            low[WSCAL_FEATS], low["wscal_mean"].values
        )

        self.grass_ = {}
        for v in ["agb", "vegc", "npp", "LAI"]:
            self.grass_[v] = ResidualRegressor(log_target=True, n_bins=12).fit(
                grass[GRASS_FEATS], grass[f"grass_{v}"].values
            )

        return self

    # --------------------------------------------------------------- render
    def render_year(self, feats_year, npatch_map, rng, with_grass=False):
        """feats_year: DataFrame with one row per Cell, columns Cell + FEATURES (single year).
        Returns a pooled tree table (Cell, Patch, Type, Height, Age, traits, diagnostics)."""
        fy = feats_year.reset_index(drop=True)
        cells = fy["Cell"].values
        Xc = fy[FEATURES]
        mu = np.clip(self.count_.predict(Xc), 0.05, None)
        npat = np.array([int(npatch_map.get(c, self.n_patches_default)) for c in cells])

        # per-patch stem counts (NB around per-cell mean)
        patch_cell = np.repeat(cells, npat)
        patch_within = (
            np.concatenate([np.arange(k) for k in npat]) if len(npat) else np.array([], int)
        )
        patch_mu = np.repeat(mu, npat)
        r = self.count_nb_r_
        if np.isfinite(r) and r < 1e5:
            p = r / (r + patch_mu + 1e-9)
            pc = rng.negative_binomial(r, p).astype(int)
        else:
            pc = rng.poisson(patch_mu).astype(int)
        pc = np.clip(pc, 0, 80)
        if pc.sum() == 0:
            return pd.DataFrame(columns=["Cell", "Patch", "Type", "Height", "Age"] + TRAITS)

        tree_cell = np.repeat(patch_cell, pc)
        tree_patch = np.repeat(patch_within, pc)
        # broadcast features to trees via cell index
        cell_pos = {c: i for i, c in enumerate(cells)}
        pos = np.array([cell_pos[c] for c in tree_cell])
        feat_arr = fy[FEATURES].values[pos]
        T = pd.DataFrame(feat_arr, columns=FEATURES)
        T["Cell"] = tree_cell
        T["Patch"] = tree_patch

        # PFT assignment from predicted fractions
        fr = np.stack([np.clip(self.frac_[t].predict(Xc), 0, None) for t in TREE_TYPES], axis=1)
        fr_sum = fr.sum(1, keepdims=True)
        fr = np.where(fr_sum > 1e-9, fr / fr_sum, 1.0 / len(TREE_TYPES))
        cum = np.cumsum(fr[pos], axis=1)
        u = rng.random(len(T))
        tidx = (u[:, None] > cum).sum(1).clip(0, len(TREE_TYPES) - 1)
        T["Type"] = np.array(TREE_TYPES)[tidx]

        # per-PFT copula-coupled axis sampling
        for a in AXES:
            T[a] = 0.0
        for t in TREE_TYPES:
            m = T["Type"].values == t
            n = int(m.sum())
            if n == 0:
                continue
            L = np.linalg.cholesky(self.copula_[t])
            U = sps.norm.cdf(rng.standard_normal((n, len(AXES))) @ L.T)
            Xg = T.loc[m, FEATURES]
            for j, a in enumerate(AXES):
                T.loc[m, a] = self.axis_[t][a].sample_u(Xg, U[:, j])

        T["Height"] = np.clip(np.exp(T["logHeight"].values), HEIGHT_FLOOR, HEIGHT_CAP)
        T["logHeight"] = np.log(T["Height"].clip(lower=HEIGHT_FLOOR))
        T["Age"] = np.clip(np.round(T["Age"].values), 1, None)
        T["beta_root"] = T["beta_root"].clip(lower=1e-4)

        # competition (within Cell,Patch of this single year), then fan-out
        T = add_competition(T)
        for v in FANOUT_DIAG:
            T[v] = self.fanout_[v].sample(T, rng)
        T["Longevity"] = self.link_long_.sample(T["SLA"].values, rng)
        T["D95max"] = self.link_d95max_.sample(T["beta_root"].values, rng)
        T["gpp"] = T["npp"].values
        T["wscal_mean"] = self._render_wscal(T, rng)
        return T

    def _render_wscal(self, T, rng):
        phi = self.wscal_clf_.predict_proba(T[WSCAL_FEATS])[:, 1]
        is_hi = rng.random(len(T)) < phi
        out = np.empty(len(T))
        if is_hi.any():
            out[is_hi] = rng.choice(self.wscal_hi_pool_, size=int(is_hi.sum()), replace=True)
        if (~is_hi).any():
            out[~is_hi] = self.wscal_lo_.sample(T[~is_hi], rng)
        return np.clip(out, 0.0, 1.0)

    def grass_rows(self, T, rng):
        """Grass aggregate per (Cell,Patch) given a rendered tree table T (canopy context)."""
        g = T.groupby(["Cell", "Patch"], sort=False)
        ctx = g.agg(
            comp_n=("Height", "size"),
            comp_meanH=("Height", "mean"),
            comp_maxH=("Height", "max"),
            comp_totLAI=("LAI", "sum"),
            comp_totfpc=("fpc_ind", "sum"),
        ).reset_index()
        ctx["comp_openness"] = (1.0 - ctx["comp_totfpc"]).clip(lower=0.0)
        # attach static + climate from any tree row of the cell
        srep = T.drop_duplicates("Cell").set_index("Cell")[STATIC + CLIM]
        ctx = ctx.join(srep, on="Cell")
        out = ctx[["Cell", "Patch"]].copy()
        for v in ["agb", "vegc", "npp", "LAI"]:
            out[f"grass_{v}"] = self.grass_[v].sample(ctx, rng)
        return out

    def render(self, feats, npatch_map, years, rng=None, with_grass=False):
        """feats: DataFrame (Cell, Year) + FEATURES. Render every (Cell,Year) independently."""
        rng = rng or np.random.default_rng(self.seed)
        out_t, out_g = {}, {}
        for y in years:
            fy = feats[feats["Year"] == y].drop(columns=["Year"])
            if not len(fy):
                continue
            T = self.render_year(fy, npatch_map, rng)
            T["Year"] = y
            out_t[y] = T
            if with_grass:
                out_g[y] = self.grass_rows(T, rng)
        return (out_t, out_g) if with_grass else out_t

    # ------------------------------------------------------------- persist
    def save(self, d):
        d = Path(d)
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "direct_emulator.pkl", "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(d):
        with open(Path(d) / "direct_emulator.pkl", "rb") as f:
            return pickle.load(f)
