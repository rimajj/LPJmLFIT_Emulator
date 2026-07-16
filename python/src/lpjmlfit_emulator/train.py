"""Train and validate the DIRECT climate->distribution emulator (component S).

Fits a :class:`DirectEmulator` on a set of TRAIN cells (all years pooled) and
evaluates it by rendering held-out cells DIRECTLY (no recursion) for every year,
comparing the pooled predicted distribution against the seed1-vs-seed2 NOISE FLOOR.
Provides the reusable pieces of the former orchestration script: the climate-zone
(warm/dry decile, a space-for-time proxy for SSP370 extrapolation) holdout selector,
the model-fitting entry point, the distributional / per-cell metric aggregation, the
monotone per-variable calibrators, and the evaluation + plotting routines.

Provenance: ported once on 2026-07-16 from the frozen sibling emulator module(s)
direct_train_eval.py (newest sibling source mtime 2026-07-14). This repository is the
single source of truth for component S; the sibling is frozen (ADR 0012) — port once,
do not sync.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
from sklearn.isotonic import IsotonicRegression

from .baseline import LGB_COMMON, DirectEmulator
from .features import TREE_TYPES
from .metrics import (
    corr_frobenius,
    energy_distance_mv,
    ks_stat,
    wasserstein_1d_normalized,
)

__all__ = [
    "EVAL_VARS",
    "JOINT_VARS",
    "MAP_VARS",
    "YEARS",
    "EVAL_YEARS",
    "load_living",
    "climate_zone_holdout",
    "train_model",
    "dist_metrics",
    "summarize",
    "fit_calibrators",
    "per_cell_maps",
    "make_plots",
    "evaluate",
]

EVAL_VARS = [
    "Height",
    "Age",
    "agb",
    "vegc",
    "npp",
    "LAI",
    "fpc_ind",
    "D95",
    "SLA",
    "Wooddens",
    "beta_root",
    "transp",
    "wscal_mean",
    "Longevity",
    "D95max",
]
JOINT_VARS = ["Height", "Age", "agb", "npp", "LAI", "D95", "SLA", "Wooddens", "beta_root"]
MAP_VARS = ["Height", "agb", "npp", "LAI"]
YEARS = list(range(2000, 2020))
EVAL_YEARS = list(range(2001, 2020))


def _default_njobs() -> int:
    """Thread count from SLURM/OMP env, defaulting to 32 (former module-level NJOBS)."""
    return int(os.environ.get("SLURM_CPUS_PER_TASK", os.environ.get("OMP_NUM_THREADS", 32)))


def _import_pyplot():
    """Lazily import a headless matplotlib.pyplot (optional dependency).

    Raises a clear ImportError if matplotlib is not installed.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised only when dep is absent
        raise ImportError(
            "matplotlib is required for plotting (per_cell_maps / make_plots); "
            "install it, e.g. `pip install matplotlib`."
        ) from exc
    return plt


def _filter_cells(src, cells):
    """Read/filter a per-cell table to ``cells`` and return a pandas DataFrame.

    ``src`` may be a path to a parquet file, a polars DataFrame/LazyFrame, or a
    pandas DataFrame.
    """
    cells = list(cells)
    if isinstance(src, (str, Path)):
        return pl.read_parquet(src).filter(pl.col("Cell").is_in(cells)).to_pandas()
    if isinstance(src, pl.LazyFrame):
        return src.filter(pl.col("Cell").is_in(cells)).collect().to_pandas()
    if isinstance(src, pl.DataFrame):
        return src.filter(pl.col("Cell").is_in(cells)).to_pandas()
    return src[src["Cell"].isin(cells)].copy()


def load_living(tag, cells, years, data_dir: str | Path = "data_global") -> pd.DataFrame:
    """Load living-tree ``ind`` rows for a seed ``tag`` over given cells/years.

    Reads ``{data_dir}/ind_{tag}_subset.parquet`` and keeps living tree individuals
    (``Type in TREE_TYPES`` and ``isdead == 0``) for the requested cells and years,
    returning the id columns plus ``EVAL_VARS`` present in the table.
    """
    data_dir = Path(data_dir)
    lf = pl.scan_parquet(data_dir / f"ind_{tag}_subset.parquet").filter(
        pl.col("Type").is_in(TREE_TYPES)
        & (pl.col("isdead") == 0)
        & pl.col("Cell").is_in(list(cells))
        & pl.col("Year").is_in(list(years))
    )
    cols = ["Year", "Cell", "Patch", "ID", "Type"] + EVAL_VARS
    have = [c for c in cols if c in lf.collect_schema().names()]
    return lf.select(have).collect().to_pandas()


def climate_zone_holdout(static, frac: float = 0.10, seed: int = 42) -> set[int]:
    """Warmest+driest decile of cells (space-for-time proxy for SSP370).

    ``seed`` is accepted for a uniform holdout-selector signature; the selection is
    deterministic (a stress-quantile threshold) and does not draw random numbers.
    """
    s = static.copy()
    tz = (s["temp_mean"] - s["temp_mean"].mean()) / s["temp_mean"].std()
    pz = (s["prec_mean"] - s["prec_mean"].mean()) / s["prec_mean"].std()
    s["stress"] = tz - pz  # hot (+) and dry (-prec) => high stress
    thr = s["stress"].quantile(1 - frac)
    return set(s.loc[s["stress"] >= thr, "Cell"].astype(int))


def train_model(
    train_cells,
    npatch_map,
    tree,
    count,
    frac,
    tree_step,
    grass,
    seed: int = 42,
    njobs: int | None = None,
) -> DirectEmulator:
    """Build and fit a :class:`DirectEmulator` on the given training tables.

    Each of ``tree``/``count``/``frac``/``tree_step``/``grass`` may be a parquet path
    or an already-loaded polars/pandas DataFrame; all are filtered to ``train_cells``.
    ``njobs`` sets the shared LightGBM thread count (defaults to the SLURM/OMP env
    count, else 32). ``npatch_map`` is accepted for a uniform call signature.
    """
    if njobs is None:
        njobs = _default_njobs()
    LGB_COMMON["n_jobs"] = njobs
    tree = _filter_cells(tree, train_cells)
    count = _filter_cells(count, train_cells)
    frac = _filter_cells(frac, train_cells)
    ts = _filter_cells(tree_step, train_cells)
    gr = _filter_cells(grass, train_cells)
    return DirectEmulator(seed=seed).fit(tree, count, frac, ts, gr)


def dist_metrics(emu_by, true_by, floor_by, years) -> dict:
    """Per-year marginal (KS, normalized Wasserstein) and joint (energy, corr-Frobenius)
    metrics for the emulator vs truth, plus the seed1-vs-seed2 noise floor."""
    out = {"per_year": {}, "vs_floor": {}}
    for y in years:
        e, t = emu_by[y], true_by[y]
        yr = {"marginals": {}, "joint": {}}
        for v in EVAL_VARS:
            if v in e and v in t:
                yr["marginals"][v] = {
                    "ks": ks_stat(t[v].values, e[v].values),
                    "wnorm": wasserstein_1d_normalized(t[v].values, e[v].values),
                }
        yr["joint"] = {
            "energy": energy_distance_mv(t[JOINT_VARS].values, e[JOINT_VARS].values),
            "corr_frob": corr_frobenius(t[JOINT_VARS].values, e[JOINT_VARS].values, "spearman"),
        }
        out["per_year"][y] = yr
        t1, t2 = true_by[y], floor_by[y]
        fl = {"marginals": {}, "joint": {}}
        for v in EVAL_VARS:
            if v in t1 and v in t2:
                fl["marginals"][v] = {
                    "ks": ks_stat(t1[v].values, t2[v].values),
                    "wnorm": wasserstein_1d_normalized(t1[v].values, t2[v].values),
                }
        fl["joint"] = {
            "energy": energy_distance_mv(t1[JOINT_VARS].values, t2[JOINT_VARS].values),
            "corr_frob": corr_frobenius(t1[JOINT_VARS].values, t2[JOINT_VARS].values, "spearman"),
        }
        out["vs_floor"][y] = fl
    return out


def summarize(res, years) -> dict:
    """Reduce per-year metrics to headline emu-vs-floor ratios and a KS drift slope."""

    def med(kind, key):
        vals = [m[key] for y in years for _, m in res[kind][y]["marginals"].items()]
        return float(np.nanmedian(vals))

    e_ks, f_ks = med("per_year", "ks"), med("vs_floor", "ks")
    e_wn, f_wn = med("per_year", "wnorm"), med("vs_floor", "wnorm")
    e_en = float(np.nanmean([res["per_year"][y]["joint"]["energy"] for y in years]))
    f_en = float(np.nanmean([res["vs_floor"][y]["joint"]["energy"] for y in years]))
    e_cf = float(np.nanmean([res["per_year"][y]["joint"]["corr_frob"] for y in years]))
    f_cf = float(np.nanmean([res["vs_floor"][y]["joint"]["corr_frob"] for y in years]))
    # drift: slope of per-year median KS over years (near 0 == no drift)
    ky = [
        np.nanmedian([m["ks"] for _, m in res["per_year"][y]["marginals"].items()]) for y in years
    ]
    slope = float(np.polyfit(np.array(years) - years[0], ky, 1)[0])
    return {
        "emu_median_ks": e_ks,
        "floor_median_ks": f_ks,
        "ks_ratio": e_ks / f_ks if f_ks else np.nan,
        "emu_median_wnorm": e_wn,
        "floor_median_wnorm": f_wn,
        "wnorm_ratio": e_wn / f_wn if f_wn else np.nan,
        "emu_energy": e_en,
        "floor_energy": f_en,
        "energy_ratio": e_en / f_en if f_en else np.nan,
        "emu_corr_frob": e_cf,
        "floor_corr_frob": f_cf,
        "ks_year_slope": slope,
        "ks_first": ky[0],
        "ks_last": ky[-1],
    }


def fit_calibrators(
    model,
    train_cells,
    feats,
    npatch_map,
    n_sample: int = 500,
    seed: int = 42,
    data_dir: str | Path = "data_global",
) -> dict:
    """Train-fit per-variable monotone calibration (isotonic pred->true on per-cell means).

    Corrects the GBM range-compression (slope<1) and systematic bias of the per-cell maps.
    Fit ONLY on training cells so the holdout report stays honest.
    """
    tc = list(train_cells)
    rng = np.random.default_rng(seed)
    if len(tc) > n_sample:
        tc = list(np.array(tc)[rng.permutation(len(tc))[:n_sample]])
    fc = feats[feats["Cell"].isin(tc)]
    emu = model.render(fc, npatch_map, YEARS, np.random.default_rng(seed))
    em = pd.concat([emu[y] for y in YEARS], ignore_index=True).groupby("Cell")[MAP_VARS].mean()
    tt = load_living("hist_seed1", tc, YEARS, data_dir)
    tm = tt.groupby("Cell")[MAP_VARS].mean()
    common = em.index.intersection(tm.index)
    cal = {}
    for v in MAP_VARS:
        iso = IsotonicRegression(out_of_bounds="clip", increasing=True)
        iso.fit(em.loc[common, v].values, tm.loc[common, v].values)
        cal[v] = iso
    return cal


def per_cell_maps(emu_by, true_by, static, years, mode, outdir, calibrators=None) -> dict:
    """Predicted vs true per-cell mean of key vars, pooled over years -> scatter + lat/lon maps.

    If `calibrators` given, also reports calibrated per-cell error.
    """
    plt = _import_pyplot()
    outdir = Path(outdir)
    e = pd.concat([emu_by[y] for y in years], ignore_index=True)
    t = pd.concat([true_by[y] for y in years], ignore_index=True)
    em = e.groupby("Cell")[MAP_VARS].mean()
    tm = t.groupby("Cell")[MAP_VARS].mean()
    common = em.index.intersection(tm.index)
    em, tm = em.loc[common], tm.loc[common]
    st = static.set_index("Cell").loc[common]
    stats = {}
    fig, axes = plt.subplots(2, len(MAP_VARS), figsize=(5 * len(MAP_VARS), 9))
    for j, v in enumerate(MAP_VARS):
        tv, ev = tm[v].values, em[v].values
        rel = (ev - tv) / np.clip(np.abs(tv), 1e-9, None)
        stats[v] = {
            "r": float(np.corrcoef(tv, ev)[0, 1]),
            "median_abs_rel_err": float(np.nanmedian(np.abs(rel))),
            "mean_rel_bias": float(np.nanmean(rel)),
            "slope": float(np.polyfit(tv, ev, 1)[0]),
        }
        if calibrators is not None:
            ec = calibrators[v].predict(ev)
            relc = (ec - tv) / np.clip(np.abs(tv), 1e-9, None)
            stats[v]["cal_median_abs_rel_err"] = float(np.nanmedian(np.abs(relc)))
            stats[v]["cal_mean_rel_bias"] = float(np.nanmean(relc))
        ax = axes[0, j]
        ax.scatter(tv, ev, s=8, alpha=0.4)
        lim = [min(tv.min(), ev.min()), max(tv.max(), ev.max())]
        ax.plot(lim, lim, "k--", lw=1)
        ax.set_xlabel(f"true cell-mean {v}")
        ax.set_ylabel(f"pred {v}")
        ttl = f"{v}: r={stats[v]['r']:.3f} |relerr|={stats[v]['median_abs_rel_err']:.2f}"
        if calibrators is not None:
            ttl += f" (cal {stats[v]['cal_median_abs_rel_err']:.2f})"
        ax.set_title(ttl)
        ax2 = axes[1, j]
        sc = ax2.scatter(
            st["lon"],
            st["lat"],
            c=np.clip(rel, -0.5, 0.5),
            s=10,
            cmap="RdBu_r",
            vmin=-0.5,
            vmax=0.5,
        )
        ax2.set_title(f"{v} rel-err map")
        ax2.set_xlabel("lon")
        ax2.set_ylabel("lat")
        plt.colorbar(sc, ax=ax2, fraction=0.046)
    fig.suptitle(f"[direct/{mode}] per-cell error (pooled over years)")
    fig.tight_layout()
    fig.savefig(outdir / f"direct_percell_{mode}.png", dpi=100)
    plt.close(fig)
    return stats


def make_plots(emu_by, true_by, floor_by, res, years, mode, outdir) -> None:
    """Drift plot (per-year KS emu vs floor) and final-year pooled marginals."""
    plt = _import_pyplot()
    outdir = Path(outdir)
    # drift plot: per-year KS for key vars, emu vs floor
    dv = ["Height", "agb", "npp", "LAI", "wscal_mean"]
    fig, axes = plt.subplots(1, len(dv), figsize=(5 * len(dv), 4))
    for ax, v in zip(axes, dv, strict=False):
        ek = [res["per_year"][y]["marginals"].get(v, {}).get("ks", np.nan) for y in years]
        fk = [res["vs_floor"][y]["marginals"].get(v, {}).get("ks", np.nan) for y in years]
        ax.plot(years, ek, "s--", color="tab:red", label="direct emu")
        ax.plot(years, fk, "^:", color="gray", label="noise floor")
        ax.set_title(f"KS {v}")
        ax.set_xlabel("year")
        ax.set_ylim(bottom=0)
    axes[0].legend(fontsize=8)
    fig.suptitle(f"[direct/{mode}] per-year KS (flat == drift-free)")
    fig.tight_layout()
    fig.savefig(outdir / f"direct_drift_{mode}.png", dpi=100)
    plt.close(fig)

    # final-year marginals
    y = years[-1]
    pv = ["Height", "agb", "npp", "SLA", "Wooddens", "wscal_mean"]
    fig, axes = plt.subplots(1, len(pv), figsize=(4.3 * len(pv), 4))
    for ax, v in zip(axes, pv, strict=False):
        tt = true_by[y][v].values
        ee = emu_by[y][v].values
        lo, hi = np.nanpercentile(np.concatenate([tt, ee]), [0.5, 99.5])
        b = np.linspace(lo, hi, 50)
        ax.hist(tt, bins=b, density=True, alpha=0.5, color="black", label="truth")
        ax.hist(ee, bins=b, density=True, alpha=0.5, color="tab:red", label="direct")
        ax.set_title(f"{v} ({y})")
    axes[0].legend(fontsize=7)
    fig.suptitle(f"[direct/{mode}] pooled marginals, final year")
    fig.tight_layout()
    fig.savefig(outdir / f"direct_marginals_{mode}.png", dpi=100)
    plt.close(fig)


def evaluate(
    model,
    hold_cells,
    feats,
    npatch_map,
    static,
    mode,
    outdir,
    calibrators=None,
    seed: int = 42,
    data_dir: str | Path = "data_global",
) -> dict:
    """Render holdout cells directly and score them against the seed1-vs-seed2 noise floor.

    Writes ``metrics_direct_{mode}.json`` (plus drift / marginal / per-cell plots) into
    ``outdir`` and returns the headline summary dict.
    """
    outdir = Path(outdir)
    fh = feats[feats["Cell"].isin(hold_cells)]
    emu_by = model.render(fh, npatch_map, YEARS, np.random.default_rng(seed))
    t1 = load_living("hist_seed1", hold_cells, YEARS, data_dir)
    t2 = load_living("hist_seed2", hold_cells, YEARS, data_dir)
    true_by = {y: t1[t1.Year == y] for y in YEARS}
    floor_by = {y: t2[t2.Year == y] for y in YEARS}
    res = dist_metrics(emu_by, true_by, floor_by, EVAL_YEARS)
    summ = summarize(res, EVAL_YEARS)
    cellstats = per_cell_maps(emu_by, true_by, static, EVAL_YEARS, mode, outdir, calibrators)
    make_plots(emu_by, true_by, floor_by, res, EVAL_YEARS, mode, outdir)
    (outdir / f"metrics_direct_{mode}.json").write_text(
        json.dumps({"summary": summ, "per_cell": cellstats, "detail": res}, indent=2, default=str)
    )
    return summ
