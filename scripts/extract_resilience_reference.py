#!/usr/bin/env python3
"""M4 — the C oracle's RESILIENCE reference: how much memory LPJmL-FIT's vegetation actually carries.

The resilience battery (``ENGINEERING_STANDARDS`` §2 item 11, ``DEVELOPMENT_PLAN`` §5, reimplemented from
Bathiany et al. 2024 doi:10.1111/gcb.17613 — ``LPJ_resilience`` carries NO licence so none of its code is
copied) scores the coupled emulator on *dynamics*, not on yearly levels. Its first two metrics need a
reference measured on the C's own output before the emulator can be scored against anything:

  * **lag-1 autocorrelation of the standing state as a function of climate** — the documented ~0.2-in-wet
    → ~0.75-in-dry gradient. Quoted from the literature it is a claim; measured here it is a number for
    THIS run, THIS window and THIS population, which is what a gate needs.
  * **variance / SD vs climate** — the same series' detrended spread.

BASIS (the four ADR-0053/0054 checks, inherited from ``extract_biome_slow_oracle.py``, which is this file's
sibling — read its docstring for the full argument):

1. TREE-ONLY, ``Type <= 6`` (ADR 0031, imported from the one canonical ``TREE_TYPES``) and ``isdead == 0``.
2. PER-PATCH SERIES, not per-cell. Each of a cell's ~25 patches is an INDEPENDENT stochastic realization of
   the same cell and the same climate, and the coupled driver runs ONE patch — so the like-for-like series
   is a single patch's, and the cell's answer is the MEAN over its patches. Pooling the patches into a
   per-cell total first would average away exactly the internal variability whose memory is being measured
   (a 25-patch mean has ~1/25 the stochastic variance, which inflates the apparent autocorrelation).
3. YEAR-MATCHED, 2000-2019 = the full extent of the historic ``ind`` table (checked, not assumed) and the
   window the coupled probe replays.
4. The >5 m population the ``ind`` writer emits (``fwriteoutput_ind.c:84``).

THREE METHOD CHOICES THAT CHANGE THE ANSWER, stated because they must be applied IDENTICALLY on the
emulator side (``scripts/biome_resilience_probe.jl`` reimplements this estimator and is gated against the
synthetic AR(1) case in ``resilience_battery_tests.jl``):

  a. **DETREND FIRST.** 2000-2019 is a transient window (rising CO2, warming), and lag-1 AC of a trended
     series is inflated toward 1 — a pure linear ramp has AC 1 with no memory at all. Every series is
     linearly detrended before the AC is taken. ``ac1_raw`` is emitted next to it so the size of that
     effect is visible rather than hidden.
  b. **n = 20 IS SHORT and the estimator is BIASED LOW.** For an AR(1) with the mean estimated from the
     same sample, E[r1] ~= phi - (1 + 3 phi)/n, i.e. -0.16 at phi = 0.75, n = 20 — comparable to the whole
     wet-to-dry gradient. ``ac1_debias`` inverts that (phi = (r1 + 1/n)/(1 - 3/n)); ``ac1_detr`` does not.
     The GATE uses ``ac1_detr`` because the emulator side is measured on the same 20 points with the same
     estimator, so the bias cancels in the comparison; ``ac1_debias`` is for reading the gradient against
     the literature.
  c. **AN EMPTY PATCH IS A ZERO, NOT A GAP.** A patch with no living >5 m tree in year y emits no rows, so
     a naive group-by silently DROPS it. Dropped years shorten the series and break the lag structure —
     and they are concentrated in exactly the dry, high-memory cells the gradient is about. Missing
     (Cell, Patch, Year) cells are filled with 0, which is what they physically are in this population.

Emits (committed, small):
  test/testitems/references/M_resilience_reference_cells.csv     the 5 coupled biome cells, both seeds
  test/testitems/references/M_resilience_reference_gradient.csv  the global aridity-binned AC gradient
  test/testitems/references/M_resilience_reference_series.csv    their per-YEAR patch-ensemble series
  test/testitems/references/M_resilience_reference_meta.json
and (large, /p/tmp, not committed) the per-cell table behind the gradient, for any follow-up.

Run:  TIME=01:00:00 NCPUS=32 scripts/sbatch_python.sh M-resref scripts/extract_resilience_reference.py
      (~40 s: the per-year Year predicate prunes row groups, so each of the 40 scans reads ~1 GB.)
      SMOKE=1 restricts it to the 5 biome cells and writes to /p/tmp instead — EXPORT it, the wrapper
      only forwards a fixed list of env knobs and SMOKE is not on it (a bare prefix silently no-ops).
"""
import json
import os
import sys
import warnings

import numpy as np
import polars as pl

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python", "src"))
from lpjmlfit_emulator.data import TREE_TYPES  # noqa: E402  the ONE canonical definition (ADR 0031)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # never hard-code (CLAUDE.md §9.6)
REFDIR = os.path.join(REPO, "test", "testitems", "references")
ART = "/p/tmp/jamirp/emulator_global"
IND = os.path.join(ART, "ind_hist_seed{seed}_all.parquet")
NPATCH = os.path.join(ART, "tables", "cell_npatch.parquet")
FEATS = os.path.join(ART, "tables", "cell_year_feats.parquet")
SCRATCH = os.environ.get("OUT", "/p/tmp/jamirp/M_resilience")

CELLS = {  # the M_cells.csv registry, cold -> hot
    "boreal_siberia": 52059,
    "temperate_hainich": 42490,
    "mediterranean_iberia": 33335,
    "semiarid_sahel": 18371,
    "tropical_amazon": 12045,
}
Y0, Y1 = 2000, 2019
YEARS = list(range(Y0, Y1 + 1))
NY = len(YEARS)
SEEDS = (1, 2)
VARS = ("n", "agb")           # per-patch living tree COUNT and aboveground carbon (gC/m2)
MAXLAG = 5
# A series must actually vary to have an autocorrelation. An all-zero patch (no >5 m tree in any year of
# the window) has zero variance and is excluded — counted, not silently dropped.
MIN_PATCHES = 5               # a cell needs this many varying patch-series for a usable cell-level mean
# SMOKE=1 restricts the scan to the 5 biome cells (seconds instead of ~an hour) and writes NOTHING to the
# committed reference dir — for checking the pipeline before spending the full scan.
SMOKE = os.environ.get("SMOKE", "") not in ("", "0", "no")


# ── the estimator (reimplemented in Julia by scripts/biome_resilience_probe.jl — keep them in step) ──────
# Written ROW-WISE over a (nseries, nyear) matrix: the global pass forms ~2.7 M series and a per-series
# Python loop calling lstsq would dominate the runtime. The closed-form least-squares detrend below is the
# same fit `np.linalg.lstsq([t, 1], x)` returns.
def detrend_rows(x):
    """Remove each row's least-squares linear trend (method choice (a)); returns the residual matrix."""
    n = x.shape[1]
    t = np.arange(n, dtype=float)
    tc = t - t.mean()
    slope = (x @ tc) / float(tc @ tc)
    return x - x.mean(axis=1, keepdims=True) - slope[:, None] * tc[None, :]


def acf_rows(x, maxlag=MAXLAG):
    """Biased (divide-by-n) sample ACF at lags 1..maxlag of each mean-removed row; NaN where constant."""
    d = x - x.mean(axis=1, keepdims=True)
    den = np.einsum("ij,ij->i", d, d)
    bad = den <= 0.0
    den = np.where(bad, np.nan, den)
    return np.stack([np.einsum("ij,ij->i", d[:, k:], d[:, :-k]) / den for k in range(1, maxlag + 1)], axis=1)


def ac_stats_rows(x):
    """-> dict of per-row resilience statistics for a (nseries, nyear) matrix (method choices (a)+(b))."""
    x = np.atleast_2d(np.asarray(x, dtype=float))
    n = x.shape[1]
    d = detrend_rows(x)
    r_raw = acf_rows(x, 1)[:, 0]
    r = acf_rows(d, MAXLAG)
    r1 = r[:, 0]
    mu = x.mean(axis=1)
    sd = d.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        # Marriott-Pope / Kendall small-sample correction, inverted for phi (method choice (b)).
        debias = (r1 + 1.0 / n) / (1.0 - 3.0 / n)
        cv = np.where(mu > 0, sd / mu, np.nan)
        # tau = -1/ln(phi): the AR(1) restoring timescale the perturbation-recovery arm must reproduce.
        tau = np.where((r1 > 0.0) & (r1 < 1.0), -1.0 / np.log(np.where((r1 > 0.0) & (r1 < 1.0), r1, 0.5)), np.nan)
    return {
        "ac1_raw": r_raw, "ac1_detr": r1, "ac1_debias": debias,
        **{f"ac{k}_detr": r[:, k - 1] for k in range(2, MAXLAG + 1)},
        "sd_detr": sd, "mean": mu, "cv_detr": cv, "tau_yr": tau,
    }


STAT_KEYS = ("ac1_raw", "ac1_detr", "ac1_debias", *[f"ac{k}_detr" for k in range(2, MAXLAG + 1)],
             "sd_detr", "mean", "cv_detr", "tau_yr")


# ── the scan: one collect PER YEAR, so memory is bounded and the Year predicate prunes row groups ────────
def scan_seed(seed, cell_filter=None):
    """-> (cells, patches, years, n, agb) dense arrays; missing (Cell,Patch,Year) filled with 0."""
    filt_base = pl.col("Type").is_in(list(TREE_TYPES)) & (pl.col("isdead") == 0)
    if cell_filter is not None:
        filt_base = filt_base & pl.col("Cell").is_in(list(cell_filter))
    frames = []
    for y in YEARS:
        # NON-streaming on purpose: `collect(engine="streaming")` is not deterministic in the KEY SET it
        # emits at this scale (CLAUDE.md §4 / ADR 0036 §5b) and whole groups appearing or vanishing would
        # be indistinguishable from the genuine empty-patch zeros this function has to reconstruct.
        df = (
            pl.scan_parquet(IND.format(seed=seed))
            .filter(filt_base & (pl.col("Year") == y))
            .group_by(["Cell", "Patch"])
            .agg(pl.len().alias("n"), pl.col("agb").sum().alias("agb"))
            .collect()
        )
        assert df.select(["Cell", "Patch"]).n_unique() == df.height, f"DUPLICATED (Cell,Patch) key, seed{seed} {y}"
        frames.append(df.with_columns(pl.lit(y, dtype=pl.Int64).alias("Year")))
        print(f"  seed{seed} {y}: {df.height} patch-rows", flush=True)
    tab = pl.concat(frames)

    # How many patches a cell HAS. `cell_npatch.parquet` is NOT authoritative here — measured on this
    # table, 5 cells of seed2 are absent from it entirely and 139 cells carry an observed Patch id at or
    # ABOVE its `n_patches`. So take the elementwise MAXIMUM of the two: a patch that emitted a row
    # certainly exists, and a patch cell_npatch knows about but which never held a >5 m tree also exists
    # (it is a genuine all-zero series). Both disagreements are counted, never silently absorbed.
    # Consequence of getting it wrong in each direction: too FEW patches drops real series; too MANY adds
    # all-zero ones, which the patch basis excludes and which leave the cellmean AC unchanged (it is
    # scale-invariant) while shifting only its level.
    npatch = pl.read_parquet(NPATCH)
    tbl = dict(zip(npatch["Cell"].to_list(), npatch["n_patches"].to_list()))
    cells = sorted(tab["Cell"].unique().to_list())
    obs_max = dict(tab.group_by("Cell").agg(pl.col("Patch").max().alias("m")).iter_rows())
    missing = sum(1 for c in cells if c not in tbl)
    over = sum(1 for c in cells if c in tbl and obs_max[c] >= tbl[c])
    if missing or over:
        print(f"  NOTE: cell_npatch.parquet disagrees for {missing} absent + {over} under-counted cells "
              f"of {len(cells)} — using max(n_patches, observed max Patch id + 1)", flush=True)
    np_of = {c: max(int(tbl.get(c, 0)), int(obs_max[c]) + 1) for c in cells}
    maxp = max(np_of[c] for c in cells)
    ci = {c: i for i, c in enumerate(cells)}
    nmat = np.zeros((len(cells), maxp, NY), dtype=np.float64)
    amat = np.zeros((len(cells), maxp, NY), dtype=np.float64)
    ci_arr = np.array([ci[c] for c in tab["Cell"].to_list()], dtype=np.int64)
    p_arr = tab["Patch"].to_numpy().astype(np.int64)
    y_arr = tab["Year"].to_numpy().astype(np.int64) - Y0
    if p_arr.max() >= maxp:
        raise SystemExit(f"observed Patch id {p_arr.max()} >= cell_npatch's max n_patches {maxp}")
    nmat[ci_arr, p_arr, y_arr] = tab["n"].to_numpy().astype(np.float64)
    amat[ci_arr, p_arr, y_arr] = tab["agb"].to_numpy().astype(np.float64)
    # patches beyond a cell's OWN n_patches never exist — mask them so they are not read as all-zero
    valid = np.zeros((len(cells), maxp), dtype=bool)
    for c, i in ci.items():
        valid[i, : np_of[c]] = True
    return np.array(cells), valid, nmat, amat




def all_cell_stats(valid, mat):
    """Per-cell resilience statistics on BOTH series bases, for every cell at once.

    * ``patch`` basis  — one series per (Cell, Patch); the cell value is the MEAN over its patch-series and
      ``*_psd`` is the between-patch SD. This is the like-for-like basis for the coupled driver, which runs
      ONE patch, and ``*_psd`` is the spread a single-patch estimate samples from.
    * ``cellmean`` basis (``cm_*``) — average the patches FIRST, then take the AC. A 25-patch mean has ~1/25
      of the stochastic variance, so its AC is systematically HIGHER; this is the basis a cell-level,
      gridded-output analysis (and the literature's vegC-per-cell gradient) is on. Emitted next to the
      other so the two are never confused: they are different numbers about the same run.
    """
    ncell, maxp, ny = mat.shape
    flat = mat.reshape(-1, ny)
    st = ac_stats_rows(flat)
    # a patch-series must both EXIST (`valid`) and VARY to carry an autocorrelation; an all-zero patch
    # (no >5 m tree in any year of the window) is counted out, not silently averaged in as a NaN
    varies = (flat.max(axis=1) > flat.min(axis=1)).reshape(ncell, maxp)
    use = valid & varies
    out = {"npatch_used": use.sum(axis=1).astype(np.int64)}
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN rows are dropped by MIN_PATCHES below
        for k in STAT_KEYS:
            v = st[k].reshape(ncell, maxp).astype(float).copy()
            v[~use] = np.nan
            out[k] = np.nanmean(v, axis=1)
            out[k + "_psd"] = np.nanstd(v, axis=1, ddof=1)
        cm = np.where(valid[:, :, None], mat, np.nan)
        cmser = np.nanmean(cm, axis=1)
        stc = ac_stats_rows(cmser)
        for k in STAT_KEYS:
            out["cm_" + k] = stc[k]
        # ── IS THE MEASURED AC ATTENUATED BY DEMOGRAPHIC SHOT NOISE? A patch holds only ~4-11 stems, and
        # lag-1 AC of signal+white-noise is phi * s2/(s2+q), attenuated toward 0 by an amount that is
        # itself climate-dependent (the dry cells' CV is ~8x the wet ones'). So "AC is flat across
        # aridity" has to be separated from "AC is graded but the dry cells are noisier". TWO diagnostics,
        # because the obvious correction turns out not to apply:
        #
        # 1. `cm_between_over_within` = (between-patch variance / P) / (year-to-year variance of the patch
        #    MEAN). If the between-patch spread were per-year sampling noise this would be <= 1 and the
        #    variance-based correction phi = num/(den - n*q) would work. MEASURED it is 1.3-12.6, i.e. the
        #    between-patch spread is 1-2 orders LARGER than what the patch mean actually varies by from
        #    year to year — proof that it is a PERSISTENT patch-level offset (patch i is denser than patch
        #    j decade after decade) which cancels in the mean, not noise. The variance-based correction is
        #    therefore inapplicable here and is deliberately NOT emitted: it would divide by a negative
        #    denominator in most cells and report a silently self-selected subsample of the rest.
        # 2. `ac2_over_ac1` — the noise-IMMUNE estimate. Additive white noise scales every ACF lag by the
        #    same factor a = s2/(s2+q), so for AR(1)+noise r1 = a*phi and r2 = a*phi^2 and the ratio
        #    r2/r1 = phi is free of it. If the series were badly noise-attenuated this ratio would sit
        #    well ABOVE r1; measured it sits at or below r1, so there is no large white-noise component to
        #    correct for and the flatness is a property of the run, not of the estimator.
        npatch = valid.sum(axis=1).astype(float)[:, None]
        q = np.nanmean(np.nanvar(cm, axis=1, ddof=1) / np.maximum(npatch, 1.0), axis=1)
        d = detrend_rows(np.nan_to_num(cmser))
        out["cm_between_over_within"] = q / np.maximum(np.einsum("ij,ij->i", d, d) / cmser.shape[1], 1.0e-30)
        r1 = out["ac1_detr"]
        out["ac2_over_ac1"] = np.where(np.abs(r1) > 1.0e-6, out["ac2_detr"] / np.where(np.abs(r1) > 1.0e-6, r1, np.nan), np.nan)
    return out


def climate_of():
    """Per-cell window-mean aridity. `eco_diag_p_pet_ratio` is Float32 and polars accumulates a Float32
    mean IN Float32 (CLAUDE.md §4) — cast to Float64 BEFORE the mean or the value lands ~3e-7 off."""
    df = (
        pl.scan_parquet(FEATS)
        .filter((pl.col("Year") >= Y0) & (pl.col("Year") <= Y1))
        .select(
            pl.col("Cell"),
            pl.col("eco_diag_p_pet_ratio").cast(pl.Float64),
            pl.col("eco_diag_dry_spell_mean").cast(pl.Float64),
            pl.col("prec_mean"),
            pl.col("temp_mean"),
        )
        .group_by("Cell")
        .agg(pl.all().mean())
        .collect()
    )
    assert df["Cell"].n_unique() == df.height, "DUPLICATED Cell key in the climate table"
    return df


# the columns emitted per (cell, seed, var, basis) row — `patch` rows carry `ac1_detr_psd`, `cellmean` rows
# do not (there is only one series), so it is written as an empty field rather than a fabricated 0
CELL_STATS = ("mean", "sd_detr", "cv_detr", "ac1_raw", "ac1_detr", "ac1_debias", "tau_yr",
              *[f"ac{k}_detr" for k in range(2, MAXLAG + 1)])


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    name_of = {v: k for k, v in CELLS.items()}
    clim = climate_of()
    clim_of = {r["Cell"]: r for r in clim.iter_rows(named=True)}

    per_seed, series = {}, {}
    for seed in SEEDS:
        print(f"== scanning seed{seed} ==", flush=True)
        cells, valid, nmat, amat = scan_seed(seed, cell_filter=set(CELLS.values()) if SMOKE else None)
        print(f"   {len(cells)} cells, {int(valid.sum())} patch-series", flush=True)
        # the per-YEAR patch-ensemble series of the 5 biome cells — what the probe's ANCHORED arm forces
        # `s.n_prev` onto, and what the emulator's own series is scored against year by year
        for cell in CELLS.values():
            i = int(np.searchsorted(cells, cell))
            if i >= len(cells) or cells[i] != cell:
                raise SystemExit(f"biome cell {cell} absent from the seed{seed} scan")
            v = valid[i]
            series[(seed, cell)] = {
                "npatch": int(v.sum()),
                "n_mean": nmat[i][v].mean(axis=0), "n_sd": nmat[i][v].std(axis=0, ddof=1),
                "agb_mean": amat[i][v].mean(axis=0), "agb_sd": amat[i][v].std(axis=0, ddof=1),
            }
        stats = {var: all_cell_stats(valid, mat) for var, mat in (("n", nmat), ("agb", amat))}
        keep = np.ones(len(cells), dtype=bool)
        for var in VARS:
            keep &= stats[var]["npatch_used"] >= MIN_PATCHES
        have_clim = np.array([int(c) in clim_of for c in cells])
        keep &= have_clim
        print(
            f"   {int(keep.sum())} cells kept "
            f"({int((~have_clim).sum())} lacked climate, "
            f"{int((len(cells) - keep.sum() - (~have_clim).sum()))} had < {MIN_PATCHES} varying patches)",
            flush=True,
        )
        cols = {"cell": cells[keep].astype(np.int64)}
        for var in VARS:
            for k, v in stats[var].items():
                cols[f"{var}__{k}"] = np.asarray(v)[keep]
        for ck in ("eco_diag_p_pet_ratio", "eco_diag_dry_spell_mean", "prec_mean", "temp_mean"):
            cols[{"eco_diag_p_pet_ratio": "p_pet", "eco_diag_dry_spell_mean": "dry_spell"}.get(ck, ck)] = (
                np.array([clim_of[int(c)][ck] for c in cells[keep]], dtype=float)
            )
        per_seed[seed] = pl.DataFrame(cols)
        big = os.path.join(SCRATCH, f"resilience_percell_seed{seed}.parquet")
        per_seed[seed].write_parquet(big)
        print(f"   wrote {big}", flush=True)

    outdir = SCRATCH if SMOKE else REFDIR   # a smoke run must never touch a committed fixture

    # ── OUTPUT 1: the five coupled biome cells, both seeds, both bases — the per-cell gate reference ─────
    ccols = ["name", "cell", "seed", "var", "basis", "npatch_used", *CELL_STATS, "ac1_detr_psd",
             "ac2_over_ac1", "between_over_within", "p_pet", "prec_mean", "temp_mean"]
    crows = []
    for seed in SEEDS:
        d = per_seed[seed]
        for cell in CELLS.values():
            sub = d.filter(pl.col("cell") == cell)
            if sub.height != 1:
                raise SystemExit(f"biome cell {cell} not in the seed{seed} table (height={sub.height})")
            r = sub.row(0, named=True)
            for var in VARS:
                for basis, pre in (("patch", ""), ("cellmean", "cm_")):
                    crows.append(
                        {
                            "name": name_of[cell], "cell": cell, "seed": seed, "var": var, "basis": basis,
                            "npatch_used": r[f"{var}__npatch_used"],
                            **{k: r[f"{var}__{pre}{k}"] for k in CELL_STATS},
                            # `ac1_detr_psd` (the between-patch spread) exists only on the patch basis;
                            # the shot-noise correction only on the cellmean basis (it needs the 25
                            # patches to estimate the noise). Written as an EMPTY field on the other,
                            # never as a fabricated 0.
                            "ac1_detr_psd": r[f"{var}__ac1_detr_psd"] if basis == "patch" else None,
                            "ac2_over_ac1": r[f"{var}__ac2_over_ac1"] if basis == "patch" else None,
                            "between_over_within": (
                                r[f"{var}__cm_between_over_within"] if basis == "cellmean" else None
                            ),
                            "p_pet": r["p_pet"], "prec_mean": r["prec_mean"], "temp_mean": r["temp_mean"],
                        }
                    )
    cout = os.path.join(outdir, "M_resilience_reference_cells.csv")
    with open(cout, "w") as f:
        f.write(
            f"# The C oracle's RESILIENCE reference for the 5 coupled biome cells, {Y0}-{Y1}, historic, both\n"
            f"# seeds. One row per (cell, seed, variable, BASIS). `var` = n (living >5 m tree stems in a\n"
            f"# patch) or agb (that patch's aboveground tree carbon, gC/m2 — agb_tree.c is already per unit\n"
            f"# area). `basis` = patch (one series per patch; the value is the MEAN over the cell's patch-\n"
            f"# series and `ac1_detr_psd` is the between-patch SD = the spread a SINGLE-patch estimate, which\n"
            f"# is what the coupled driver produces, samples from) or cellmean (average the 25 patches FIRST,\n"
            f"# then take the AC — ~1/25 of the stochastic variance, so systematically HIGHER; this is the\n"
            f"# cell-level basis a gridded analysis is on). The two are different numbers about the same run.\n"
            f"# Series are LINEARLY DETRENDED before the AC (`ac1_raw` is not); `ac1_debias` applies the\n"
            f"# n={NY} small-sample correction. seed1-vs-seed2 on the same statistic is the irreducible noise\n"
            f"# floor. Emitted by scripts/extract_resilience_reference.py — see that docstring for the basis.\n"
        )
        f.write(",".join(ccols) + "\n")
        for r in crows:
            f.write(
                ",".join(
                    ("" if r[c] is None else str(r[c])) if c in
                    ("name", "cell", "seed", "var", "basis", "npatch_used")
                    else ("" if r[c] is None else f"{r[c]:.6f}")
                    for c in ccols
                ) + "\n"
            )
    print(f"\nwrote {cout}  ({len(crows)} rows)")

    # ── OUTPUT 1b: the per-YEAR patch-ensemble series of the 5 biome cells ───────────────────────────────
    # This is the series everything else in the battery is derived from, and the probe needs it directly:
    # the ANCHORED arm overwrites `s.n_prev` with `n_mean` each year, and the AC comparison is year-matched.
    # It OVERLAPS `M_slow_oracle_counts.csv` on 2010-2019, which is a free independent-extractor check —
    # a different script, a different scan, the same population — so it is asserted, not just noted.
    scols = ["name", "cell", "seed", "year", "npatch", "n_mean", "n_sd", "agb_mean", "agb_sd"]
    srows = [
        {
            "name": name_of[cell], "cell": cell, "seed": seed, "year": Y0 + t,
            "npatch": series[(seed, cell)]["npatch"],
            **{k: float(series[(seed, cell)][k][t]) for k in ("n_mean", "n_sd", "agb_mean", "agb_sd")},
        }
        for seed in SEEDS for cell in CELLS.values() for t in range(NY)
    ]
    m3 = os.path.join(REFDIR, "M_slow_oracle_counts.csv")
    if os.path.exists(m3):
        prev = {}
        with open(m3) as f:
            hdr = None
            for ln in f:
                if ln.startswith("#"):
                    continue
                p = ln.rstrip("\n").split(",")
                if hdr is None:
                    hdr = p
                    continue
                r = dict(zip(hdr, p))
                prev[(int(r["seed"]), int(r["cell"]), int(r["year"]))] = float(r["n_mean"])
        checked = 0
        for r in srows:
            k = (r["seed"], r["cell"], r["year"])
            if k in prev:
                if abs(prev[k] - r["n_mean"]) > 1.0e-6:
                    raise SystemExit(
                        f"DISAGREES with the M3 fixture at {k}: {prev[k]} vs {r['n_mean']} — the two "
                        f"extractors are on different populations, which invalidates one of them"
                    )
                checked += 1
        print(f"cross-check vs M_slow_oracle_counts.csv: {checked} overlapping cell-years agree to 1e-6")
    sout = os.path.join(outdir, "M_resilience_reference_series.csv")
    with open(sout, "w") as f:
        f.write(
            f"# The C oracle's per-YEAR patch-ensemble series for the 5 coupled biome cells, {Y0}-{Y1},\n"
            f"# historic, both seeds — the series every statistic in M_resilience_reference_cells.csv is\n"
            f"# derived from, and the one scripts/biome_resilience_probe.jl's ANCHORED arm forces\n"
            f"# `s.n_prev` onto each year. n_mean/agb_mean are the mean over the cell's `npatch`\n"
            f"# INDEPENDENT patches (n_sd/agb_sd their between-patch SD). Its 2010-2019 `n_mean` values are\n"
            f"# asserted equal to M_slow_oracle_counts.csv's — a different script, a different scan, the\n"
            f"# same population. Emitted by scripts/extract_resilience_reference.py.\n"
        )
        f.write(",".join(scols) + "\n")
        for r in srows:
            f.write(",".join(str(r[c]) if c in ("name", "cell", "seed", "year", "npatch")
                             else f"{r[c]:.6f}" for c in scols) + "\n")
    print(f"wrote {sout}  ({len(srows)} rows)")

    print(f"\n=== the 5 coupled biome cells (seed1, detrended) ===")
    print(f"{'cell':<22} {'var':>4} {'basis':>9} {'mean':>11} {'ac1':>7} {'+-psd':>7} {'debias':>7} "
          f"{'tau':>6} {'floor':>7} {'ac1_raw':>8}")
    for r in crows:
        if r["seed"] != 1:
            continue
        o = [x for x in crows if x["seed"] == 2 and x["name"] == r["name"]
             and x["var"] == r["var"] and x["basis"] == r["basis"]][0]
        psd = "      -" if r["ac1_detr_psd"] is None else f"{r['ac1_detr_psd']:7.3f}"
        print(f"{r['name']:<22} {r['var']:>4} {r['basis']:>9} {r['mean']:11.2f} {r['ac1_detr']:7.3f} "
              f"{psd} {r['ac1_debias']:7.3f} {r['tau_yr']:6.2f} "
              f"{abs(r['ac1_detr'] - o['ac1_detr']):7.3f} {r['ac1_raw']:8.3f}")

    # ── OUTPUT 2: the GLOBAL aridity gradient — the ~0.2-wet -> ~0.75-dry claim, measured ────────────────
    # Binned by P/PET decile over the cells present in BOTH seeds, so each bin's number is a mean over
    # hundreds-to-thousands of cells and the n=20 sampling noise (SE ~ 0.22 per series) averages out.
    both = per_seed[1].join(per_seed[2], on="cell", how="inner", suffix="_s2")
    if both.height < 100:
        print(f"\n[SMOKE] only {both.height} cells in both seeds — skipping the global gradient")
        return
    ppet = both["p_pet"].to_numpy()
    q = np.nanquantile(ppet, np.linspace(0.0, 1.0, 11))
    q[0] -= 1.0e-9
    grows = []
    for b in range(10):
        m = (ppet > q[b]) & (ppet <= q[b + 1])
        if m.sum() == 0:
            continue
        rec = {"bin": b + 1, "ncell": int(m.sum()), "p_pet_lo": float(q[b]), "p_pet_hi": float(q[b + 1]),
               "p_pet_med": float(np.nanmedian(ppet[m]))}
        for var in VARS:
            for basis, pre in (("patch", ""), ("cellmean", "cm_")):
                # ac1_raw is carried per BIN, not just per cell: whether the documented wet-to-dry AC
                # gradient exists at all in this run, and whether it is a TREND artefact rather than
                # memory, is exactly the difference between this column and ac1_detr.
                for stat in ("ac1_detr", "ac1_debias", "ac1_raw", "cv_detr", "sd_detr"):
                    a = both[f"{var}__{pre}{stat}"].to_numpy()[m]
                    a2 = both[f"{var}__{pre}{stat}_s2"].to_numpy()[m]
                    rec[f"{var}_{basis}_{stat}"] = float(np.nanmean(a))
                    rec[f"{var}_{basis}_{stat}_floor"] = float(np.nanmean(np.abs(a - a2)))
            # the two shot-noise DIAGNOSTICS (see all_cell_stats) — not a correction, evidence
            for stat in ("cm_between_over_within", "ac2_over_ac1"):
                a = both[f"{var}__{stat}"].to_numpy()[m]
                a2 = both[f"{var}__{stat}_s2"].to_numpy()[m]
                rec[f"{var}_{stat}"] = float(np.nanmean(a))
                rec[f"{var}_{stat}_floor"] = float(np.nanmean(np.abs(a - a2)))
        grows.append(rec)
    gcols = list(grows[0].keys())
    gout = os.path.join(outdir, "M_resilience_reference_gradient.csv")
    with open(gout, "w") as f:
        f.write(
            f"# The C oracle's lag-1 AUTOCORRELATION-vs-CLIMATE gradient, {Y0}-{Y1}, historic — the measured\n"
            f"# form of the '~0.2 in wet -> ~0.75 in dry' claim (DEVELOPMENT_PLAN §5). Cells are binned by\n"
            f"# P/PET decile (bin 1 = DRIEST). Both series bases are emitted (see the _cells.csv header):\n"
            f"# `patch` = mean over the cell's ~25 independent patch-series, `cellmean` = the AC of the\n"
            f"# 25-patch AVERAGE series. `*_floor` = mean |seed1 - seed2| of the same bin statistic = the\n"
            f"# irreducible noise floor. Detrended; see the script docstring for the three method choices.\n"
        )
        f.write(",".join(gcols) + "\n")
        for r in grows:
            f.write(",".join(str(r[c]) if c in ("bin", "ncell") else f"{r[c]:.6f}" for c in gcols) + "\n")
    print(f"wrote {gout}  ({len(grows)} bins)")

    print(f"\n=== the measured AC-vs-aridity gradient (bin 1 = DRIEST) ===")
    print(f"{'bin':>3} {'ncell':>7} {'P/PET':>7} | {'n detr':>7} {'floor':>6} {'n RAW':>7} {'n debi':>7} "
          f"| {'n cellmn':>9} {'r2/r1':>7} {'betw/wit':>9} | {'agb r2/r1':>10} | {'n cv':>7}")
    for r in grows:
        print(f"{r['bin']:>3} {r['ncell']:>7} {r['p_pet_med']:7.3f} | {r['n_patch_ac1_detr']:7.3f} "
              f"{r['n_patch_ac1_detr_floor']:6.3f} {r['n_patch_ac1_raw']:7.3f} "
              f"{r['n_patch_ac1_debias']:7.3f} | {r['n_cellmean_ac1_detr']:9.3f} "
              f"{r['n_ac2_over_ac1']:7.3f} {r['n_cm_between_over_within']:9.2f} "
              f"| {r['agb_ac2_over_ac1']:10.3f} | {r['n_patch_cv_detr']:7.3f}")
    print("r2/r1 = the NOISE-IMMUNE AR(1) coefficient (white noise scales every lag equally, so the")
    print("ratio is free of it). It sits at or BELOW ac1_detr, so the series is not badly attenuated")
    print("and the flat ac1 column is a property of the run, not of the estimator. betw/wit = the")
    print("between-patch variance / P over the year-to-year variance of the patch MEAN: >> 1 proves")
    print("that spread is a PERSISTENT patch offset, not sampling noise, so a variance-based")
    print("attenuation correction does not apply here (see the all_cell_stats comment).")
    print("A gradient present in RAW but absent in detr is a TREND, not memory: a linear ramp has lag-1")
    print("AC 1 with no memory at all. A gradient in NEITHER means this run has no resolvable one on a")
    print(f"{NY}-year window — detrending is a high-pass filter, so memory with a timescale >~ n/2 is")
    print("removed with the trend and cannot be distinguished from it here.")

    meta = {
        "purpose": "M4 — the C's resilience reference (AC-vs-climate + variance) for the coupled battery",
        "scenario": "historic",
        "window": [Y0, Y1],
        "window_is_full_table_extent": True,
        "seeds": list(SEEDS),
        "tree_types": list(TREE_TYPES),
        "variables": {"n": "living >5 m tree stems per patch", "agb": "patch aboveground tree C, gC/m2"},
        "series_bases": {
            "patch": "one series per (Cell,Patch); cell value = mean over patch-series, psd = their SD",
            "cellmean": "the AC of the 25-patch AVERAGE series — ~1/25 the stochastic variance, higher AC",
        },
        "empty_patch_year": "filled with 0 (an empty patch emits no rows) — method choice (c)",
        "detrend": "least-squares linear, before every AC; ac1_raw is the undetrended counterpart",
        "debias": f"phi = (r1 + 1/n)/(1 - 3/n), the Marriott-Pope/Kendall n={NY} correction",
        "min_varying_patches": MIN_PATCHES,
        "reimplemented_in": "scripts/biome_resilience_probe.jl (same estimator, applied to the emulator)",
        "reference": "Bathiany et al. 2024 doi:10.1111/gcb.17613 (method reimplemented, no code copied)",
        "sources": {
            str(s): {"path": IND.format(seed=s), "bytes": os.path.getsize(IND.format(seed=s))} for s in SEEDS
        },
        "ncells_scored": {str(s): int(per_seed[s].height) for s in SEEDS},
        "biome_cells": CELLS,
    }
    mout = os.path.join(outdir, "M_resilience_reference_meta.json")
    with open(mout, "w") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\nwrote {mout}")


if __name__ == "__main__":
    main()
