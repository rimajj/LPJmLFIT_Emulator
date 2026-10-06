#!/usr/bin/env python3
"""explore_de_rec_lstmstats.py -- line X, Germany emulator, track C-RECUR item C0: "LSTM-STATS".

The quickest answer to the owner's "is LSTM also an option?": a cell-level LSTM over YEARLY CELL
STATISTICS (stems per patch, stand biomass, PFT shares, yearly trait/size quantiles) plus climate,
trained multi-step on training members only, free-run from a test member's truth state and scored
with `explore_de_score.py --format stats`. It emits NO tree roster: a data point, not a candidate.
Pre-registration + results: /p/tmp/jamirp/X_de/_status/C0.md; machine-readable report
/p/tmp/jamirp/X_de/_reports/r2_C0.json.

Only 1985-2044 is read (owner decision 2026-10-01: the 2071-2100 / 3071-3100 production segments
ran with the wrong humidity setting). Nothing Germany-specific is baked in beyond the defaults
below (paths, cell lists, npatch).

STAGES (heavy ones on SLURM; `submit-*` write a raw jcf under <XDE>/_jobs and sbatch it)
  yearly --member M      yearly per-cell statistics of one clean member-window from ind_dev
                         (living trees, the scorer's population) -> <OUT>/yearly/<M>.parquet
  submit-yearly          array job over the 16 clean member-windows (standard/short)
  replay                 G0 conformance: the truth's own yearly statistics pushed through the
                         window aggregator -> <OUT>/preds/truthagg_*.parquet (stats format)
  train --fold k --arm A one cross-fit model (A = lstm | lstmCB) trained on DEV-A training
                         members, dev cells of the other folds -> <OUT>/models/<A>_f<k>.pt/.json
  predict --arm A        free runs of every fold model on its own fold's cells for every test
                         member, starts S14 (truth 1985-2014 warm-up) and S85 (truth 1985 only)
                         -> yearly + window statistics; A = lstm | lstmCB | lstmCBres (the lstm
                         model run on resampled Historical climate)
  pers                   persistence null: the truth's living 2014 roster frozen -> stats
  submit-score           scorer calls (fold 5 alone, pooled cross-fit) per arm x start x group
  report                 collect -> <OUT>/comparison_C0.csv
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
OUT = os.environ.get("C0_OUT", f"{XDE}/recurrent/lstmstats")
PY = "/home/jamirp/.conda/envs/py311_new/bin/python"
LOGDIR = f"{REPO}/logs"
JOBS = f"{XDE}/_jobs"
IND_DEV = f"{XDE}/ind_dev"
NPATCH = int(os.environ.get("XDE_NPATCH", "250"))
HMIN = 5.0
NMIN_STEMYEARS = 30
CELLS_DEV = f"{XDE}/shared/scorer/cells_dev.txt"
CELLS_F5 = f"{XDE}/shared/scorer/cells_fold5_dev.txt"
FOLDS = f"{XDE}/shared/registry/folds.parquet"
SCORER = f"{REPO}/scripts/explore_de_score.py"
SPLIT = "DEV-A"
YEAR0, YEAR1, YSPLIT = 1985, 2044, 2014  # first year, last year, last Historical year
TRAIN = {"gcm": "MPI-ESM1-2-HR", "seed": 1, "scens": ["ssp126", "ssp370"]}  # DEV-A training members
# test members: (gcm, start/truth seed, scenarios); MPI ssp245 is scored against seed 2 (critic gap
# 2)
TESTS = {
    "ACCESS": ("ACCESS-CM2", 1, ["ssp126", "ssp245", "ssp370"]),
    "MPI": ("MPI-ESM1-2-HR", 2, ["ssp126", "ssp245", "ssp370"]),
}
GCMS = ["ACCESS-CM2", "MPI-ESM1-2-HR"]
SSPS = ["ssp126", "ssp245", "ssp370"]

TRAITS = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "Height", "agb"]
LOGT = {"Height", "agb"}  # modelled in log space
PS = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
PN = ["p01", "p05", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
QS = [0.05, 0.25, 0.50, 0.75, 0.95]  # the scorer's window quantiles
QN = ["q05", "q25", "q50", "q75", "q95"]
PFTS = list(range(7))
STATE = (
    ["n_per_patch", "agb_stand"]
    + [f"share_{t}" for t in PFTS]
    + [f"{v}_{p}" for v in TRAITS for p in PN]
)
CLIM = [
    "tmean_ann",
    "tcold_month",
    "twarm_month",
    "gdd5",
    "frost_days",
    "days_gt30",
    "prec_ann",
    "prec_jja",
    "pet_jja",
    "cwb_ann",
    "cwb_jja",
    "cwb_min3",
    "dry_spell_max",
    "rh_jja",
    "vpd_jja",
    "vpd_win10_sum",
    "swdown_ann",
    "tcold_month_tr20",
    "twarm_month_tr20",
    "gdd5_tr20",
]
CLIM_EXT = [
    "tstress_pft0",
    "tstress_pft1",
    "tstress_pft2",
    "tstress_pft3",
]  # pft 4-6 never accumulate in Germany
SOILS = [1, 4, 7, 8, 9, 11, 12, 13]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def members_clean() -> list[str]:
    out = []
    for g in GCMS:
        for s in (1, 2):
            out.append(f"{g}_Historical_s{s}_h1985")
            out += [f"{g}_{sc}_s{s}_w2015" for sc in SSPS]
    return out


def read_cells(path: str) -> list[int]:
    return [int(x) for x in open(path).read().split()]


def jcf(
    name: str,
    body: str,
    cpus: int = 8,
    mem: str = "40G",
    time_: str = "02:00:00",
    array: str | None = None,
    dep: str | None = None,
) -> str:
    os.makedirs(JOBS, exist_ok=True)
    os.makedirs(LOGDIR, exist_ok=True)
    f = f"{JOBS}/{name}.jcf"
    arr = f"#SBATCH --array={array}\n" if array else ""
    dp = f"#SBATCH --dependency=afterok:{dep}\n" if dep else ""
    out = f"{LOGDIR}/{name}.%A_%a.out" if array else f"{LOGDIR}/{name}.%j.out"
    with open(f, "w") as fh:
        fh.write(f"""#!/bin/bash
#SBATCH --job-name={name}
#SBATCH --account=waldspektrum
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --cpus-per-task={cpus}
#SBATCH --mem={mem}
#SBATCH --time={time_}
{arr}{dp}#SBATCH --output={out}
export POLARS_MAX_THREADS={cpus}
export OMP_NUM_THREADS={cpus}
export C0_OUT={OUT}
cd {REPO}
{body}
echo "=== JOB DONE {name} exit=$? ==="
""")
    jid = subprocess.run(
        ["sbatch", "--parsable", f], capture_output=True, text=True, check=True
    ).stdout.strip()
    log(f"submitted {name}: job {jid} ({f})")
    return jid


# --------------------------------------------------------------------------------------------------
# 1. yearly statistics from the original's tree tables
# --------------------------------------------------------------------------------------------------
def stage_yearly(a) -> None:
    m = a.member
    src = f"{IND_DEV}/{m}.parquet"
    y0, y1 = (1985, 2014) if m.endswith("h1985") else (2015, 2044)
    cells = read_cells(CELLS_DEV)
    t0 = time.time()
    lf = (
        pl.scan_parquet(src)
        .select(["Year", "Cell", "Type", "isdead"] + TRAITS)
        .filter(
            (pl.col("Type") <= 6)
            & (pl.col("isdead") == 0)
            & (pl.col("Height") >= HMIN)
            & pl.col("Year").is_between(y0, y1)
        )
    )
    aggs = [pl.len().alias("n_living"), pl.col("agb").cast(pl.Float64).sum().alias("agb_sum")]
    aggs += [(pl.col("Type") == t).sum().alias(f"n_t{t}") for t in PFTS]
    aggs += [
        pl.col(v).cast(pl.Float64).quantile(p, interpolation="linear").alias(f"{v}_{pn}")
        for v in TRAITS
        for p, pn in zip(PS, PN, strict=True)
    ]
    g = lf.group_by(["Cell", "Year"]).agg(aggs).collect()
    g = g.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32))
    assert g.select("Cell", "Year").n_unique() == g.height, "duplicate (Cell, Year)"
    census = pl.DataFrame(
        {
            "Cell": np.repeat(cells, y1 - y0 + 1).astype(np.int32),
            "Year": np.tile(np.arange(y0, y1 + 1), len(cells)).astype(np.int32),
        }
    )
    extra = g.join(census, on=["Cell", "Year"], how="anti")
    assert extra.height == 0, f"{extra.height} rows outside the dev census"
    d = census.join(g, on=["Cell", "Year"], how="left").with_columns(
        pl.col("n_living").fill_null(0),
        pl.col("agb_sum").fill_null(0.0),
        *[pl.col(f"n_t{t}").fill_null(0) for t in PFTS],
    )
    d = d.with_columns(
        (pl.col("n_living") / NPATCH).alias("n_per_patch"),
        (pl.col("agb_sum") / NPATCH).alias("agb_stand"),
        *[
            pl.when(pl.col("n_living") > 0)
            .then(pl.col(f"n_t{t}") / pl.col("n_living"))
            .otherwise(None)
            .alias(f"share_{t}")
            for t in PFTS
        ],
    )
    parts = m.split("_")
    gcm, scen, seed = parts[0], parts[1], int(parts[2][1:])
    d = d.with_columns(
        pl.lit(gcm).alias("gcm"),
        pl.lit(scen).alias("scen"),
        pl.lit(seed).cast(pl.Int8).alias("seed"),
    )
    os.makedirs(f"{OUT}/yearly", exist_ok=True)
    d.sort("Cell", "Year").write_parquet(f"{OUT}/yearly/{m}.parquet")
    # gate against the shared cell_year table (n_living, agb_sum, medians) where it exists
    cy = (
        pl.read_parquet(f"{XDE}/reference/cell_year/{m}.parquet")
        .select(
            pl.col("Cell").cast(pl.Int32),
            pl.col("Year").cast(pl.Int32),
            "n_living",
            "agb_sum",
            "Height_q50",
            "SLA_q50",
        )
        .filter(pl.col("Cell").is_in(cells))
    )
    j = cy.join(d, on=["Cell", "Year"], how="inner", suffix="_me")
    gate = {
        "member": m,
        "rows": d.height,
        "joined": j.height,
        "cell_year_rows": cy.height,
        "n_living_mismatch": int((j["n_living"] != j["n_living_me"]).sum()),
        "agb_sum_max_rel": float(
            ((j["agb_sum"] - j["agb_sum_me"]).abs() / j["agb_sum"].abs().clip(1e-9)).max() or 0.0
        ),
        "Height_q50_max_abs": float((j["Height_q50"] - j["Height_p50"]).abs().max() or 0.0),
        "SLA_q50_max_abs": float((j["SLA_q50"] - j["SLA_p50"]).abs().max() or 0.0),
        "seconds": round(time.time() - t0, 1),
    }
    json.dump(gate, open(f"{OUT}/yearly/{m}.gate.json", "w"), indent=1)
    log(json.dumps(gate))


def stage_submit_yearly(a) -> None:
    mem = members_clean()
    body = (
        f"M=({' '.join(mem)})\n"
        f"{PY} scripts/explore_de_rec_lstmstats.py yearly --member ${{M[$SLURM_ARRAY_TASK_ID]}}"
    )
    jcf("X-C0-yearly", body, cpus=8, mem="60G", time_="01:30:00", array=f"0-{len(mem) - 1}")


# --------------------------------------------------------------------------------------------------
# 2. window aggregation (yearly -> scorer window statistics)
# --------------------------------------------------------------------------------------------------
def _mixture_quantiles(qv: np.ndarray, w: np.ndarray, probs=QS) -> np.ndarray:
    """qv: (n_years, len(PS)) yearly quantiles (finite), w: (n_years,) stem-year weights.
    Returns the quantiles `probs` of the w-weighted mixture of the yearly piecewise-linear CDFs
    (knots PS, linear tails to 0 / 1)."""
    keep = w > 0
    qv, w = qv[keep], w[keep]
    if w.sum() <= 0:
        return np.full(len(probs), np.nan)
    qv = np.sort(qv, axis=1)
    span = np.maximum(qv[:, -1] - qv[:, 0], 1e-9 * np.maximum(np.abs(qv[:, 4]), 1.0))
    qv = qv + np.asarray(PS)[None, :] * 1e-7 * span[:, None]  # strictly increasing knots
    lo = qv[:, 0] - (qv[:, 1] - qv[:, 0]) * PS[0] / (PS[1] - PS[0])
    hi = qv[:, -1] + (qv[:, -1] - qv[:, -2]) * (1 - PS[-1]) / (PS[-1] - PS[-2])
    xs = np.concatenate([lo[:, None], qv, hi[:, None]], axis=1)  # (n, 11)
    ps = np.concatenate([[0.0], PS, [1.0]])
    grid = np.unique(xs.ravel())
    F = np.zeros_like(grid)
    for i in range(xs.shape[0]):
        F += w[i] * np.interp(grid, xs[i], ps, left=0.0, right=1.0)
    F /= w.sum()
    F = np.maximum.accumulate(F)
    out = np.empty(len(probs))
    for k, p in enumerate(probs):
        j = int(np.searchsorted(F, p, side="left"))
        if j <= 0:
            out[k] = grid[0]
        elif j >= len(grid):
            out[k] = grid[-1]
        else:
            f0, f1 = F[j - 1], F[j]
            out[k] = grid[j - 1] + (p - f0) / max(f1 - f0, 1e-300) * (grid[j] - grid[j - 1])
    return out


def window_stats(Y: pl.DataFrame, years: tuple[int, int], keys=("gcm", "scen")) -> pl.DataFrame:
    """Y: yearly statistics (Cell, Year, keys, STATE columns in physical units). Returns the
    scorer's wide stats rows (keys, Cell, the QUANTITIES) over the years in [y0, y1]."""
    y0, y1 = years
    Y = Y.filter(pl.col("Year").is_between(y0, y1)).sort(list(keys) + ["Cell", "Year"])
    rows = []
    for kv, grp in Y.group_by(list(keys) + ["Cell"], maintain_order=True):
        nyr = grp.height
        n = np.clip(grp["n_per_patch"].to_numpy().astype(float), 0, None)
        stemyears = n * NPATCH
        tot = stemyears.sum()
        r = dict(zip(list(keys) + ["Cell"], kv, strict=True))
        r["n_years"] = nyr
        r["n_per_patch"] = float(n.mean())
        r["agb_stand"] = float(np.clip(grp["agb_stand"].to_numpy().astype(float), 0, None).mean())
        sh = np.stack(
            [np.nan_to_num(grp[f"share_{t}"].to_numpy().astype(float)) for t in PFTS], axis=1
        )
        for t in PFTS:
            r[f"share_{t}"] = float((sh[:, t] * stemyears).sum() / tot) if tot > 0 else None
        for v in TRAITS:
            if tot < NMIN_STEMYEARS:
                for qn in QN:
                    r[f"{v}_{qn}"] = None
                continue
            qv = np.stack([grp[f"{v}_{pn}"].to_numpy().astype(float) for pn in PN], axis=1)
            ok = np.all(np.isfinite(qv), axis=1)
            qq = _mixture_quantiles(qv[ok], stemyears[ok])
            for qn, x in zip(QN, qq, strict=True):
                r[f"{v}_{qn}"] = float(x)
        rows.append(r)
    return pl.DataFrame(rows, infer_schema_length=None)


WINDOWS = {"h1985": (1985, 2014), "w2015": (2015, 2044)}


def load_yearly(gcm: str, seed: int) -> pl.DataFrame:
    fs = [f"{OUT}/yearly/{gcm}_Historical_s{seed}_h1985.parquet"] + [
        f"{OUT}/yearly/{gcm}_{sc}_s{seed}_w2015.parquet" for sc in SSPS
    ]
    return pl.concat([pl.read_parquet(f) for f in fs], how="diagonal_relaxed")


def stage_replay(a) -> None:
    """G0: truth yearly statistics -> window statistics, scored like an arm (stats format)."""
    os.makedirs(f"{OUT}/preds", exist_ok=True)
    for grp, (gcm, seed, _scens) in TESTS.items():
        Y = load_yearly(gcm, seed)
        parts = []
        h = window_stats(Y.filter(pl.col("scen") == "Historical"), WINDOWS["h1985"])
        parts.append(h.with_columns(pl.lit("h1985").alias("window")))
        w = window_stats(Y.filter(pl.col("scen") != "Historical"), WINDOWS["w2015"])
        parts.append(w.with_columns(pl.lit("w2015").alias("window")))
        d = pl.concat(parts, how="diagonal_relaxed").drop("n_years")
        d.write_parquet(f"{OUT}/preds/truthagg_{grp}.parquet")
        log(f"replay {grp}: {d.height} rows")


# --------------------------------------------------------------------------------------------------
# 3. tensors: state transform, climate, sequences
# --------------------------------------------------------------------------------------------------
def to_z_raw(Y: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Physical yearly statistics -> transformed state X (N, D) and loss weights W (N, D)."""
    n = Y["n_per_patch"].to_numpy().astype(float)
    cols = [np.log(n + 0.05), np.log(Y["agb_stand"].to_numpy().astype(float) + 1.0)]
    for t in PFTS:
        cols.append(Y[f"share_{t}"].to_numpy().astype(float))
    for v in TRAITS:
        for pn in PN:
            x = Y[f"{v}_{pn}"].to_numpy().astype(float)
            cols.append(np.log(np.maximum(x, 1e-3)) if v in LOGT else x)
    X = np.stack(cols, axis=1)
    nl = Y["n_living"].to_numpy().astype(float) if "n_living" in Y.columns else n * NPATCH
    wq = np.clip(nl / 20.0, 0, 1)
    W = np.ones_like(X)
    W[:, 0] = 3.0
    W[:, 1] = 3.0
    W[:, 2:] = wq[:, None]
    W[~np.isfinite(X)] = 0.0
    return X, W


def from_z_raw(X: np.ndarray) -> dict[str, np.ndarray]:
    out = {
        "n_per_patch": np.clip(np.exp(X[:, 0]) - 0.05, 0, None),
        "agb_stand": np.clip(np.exp(X[:, 1]) - 1.0, 0, None),
    }
    sh = np.clip(X[:, 2:9], 0, None)
    s = sh.sum(axis=1, keepdims=True)
    sh = np.where(s > 0, sh / np.where(s > 0, s, 1), 1.0 / 7)
    for t in PFTS:
        out[f"share_{t}"] = sh[:, t]
    k = 9
    for v in TRAITS:
        q = X[:, k : k + len(PN)]
        q = np.exp(q) if v in LOGT else q
        q = np.sort(q, axis=1)
        for j, pn in enumerate(PN):
            out[f"{v}_{pn}"] = q[:, j]
        k += len(PN)
    return out


def ffill_seq(X: np.ndarray) -> np.ndarray:
    """X: (S, T, D) with NaN -> forward fill along T, then backward fill (remaining NaN are
    replaced by the training mean by the caller)."""
    X = X.copy()
    S, T, D = X.shape
    for t in range(1, T):
        m = ~np.isfinite(X[:, t])
        X[:, t][m] = X[:, t - 1][m]
    for t in range(T - 2, -1, -1):
        m = ~np.isfinite(X[:, t])
        X[:, t][m] = X[:, t + 1][m]
    return X


def climate_table(gcm: str, scens: list[str], mode: str) -> dict[str, np.ndarray]:
    """Per scen -> (cells, years YEAR0..YEAR1, F) climate [levels, anomalies], dev cells.
    mode: 'real' | 'frozen' (cell's 1985-2014 mean, anomalies 0) | 'resample' (blind_yearmap
    rep 1: each year's climate replaced by a Historical year, same map for every cell/scen)."""
    cells = read_cells(CELLS_DEV)
    years = np.arange(YEAR0, YEAR1 + 1)
    base = (
        pl.scan_parquet(f"{XDE}/climate/cell_year.parquet")
        .filter((pl.col("gcm") == gcm) & pl.col("Cell").is_in(cells))
        .select(["scen", "Cell", "Year"] + CLIM)
    )
    ext = (
        pl.scan_parquet(f"{XDE}/shared/climate/cell_year_ext.parquet")
        .filter((pl.col("gcm") == gcm) & pl.col("Cell").is_in(cells))
        .select(["scen", "Cell", "Year"] + CLIM_EXT)
    )
    C = (
        base.join(ext, on=["scen", "Cell", "Year"], how="left")
        .collect()
        .with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32))
    )
    clim = (
        pl.read_parquet(f"{XDE}/shared/climate/clim8514.parquet")
        .filter(pl.col("gcm") == gcm)
        .select([pl.col("Cell").cast(pl.Int32)] + CLIM + CLIM_EXT)
    )
    clim = pl.DataFrame({"Cell": np.asarray(cells, dtype=np.int32)}).join(
        clim, on="Cell", how="left"
    )
    cm = clim.select(CLIM + CLIM_EXT).to_numpy().astype(float)  # (cells, F)
    assert np.all(np.isfinite(cm)), "clim8514 missing for a dev cell"
    ymap = None
    if mode == "resample":
        ymap = pl.read_parquet(f"{XDE}/shared/registry/blind_yearmap.parquet").filter(
            (pl.col("gcm") == gcm) & (pl.col("rep") == 1)
        )
        ymap = dict(zip(ymap["Year"].to_list(), ymap["src_year"].to_list(), strict=True))
    out = {}
    for sc in scens:
        lev = np.empty((len(cells), len(years), cm.shape[1]))
        for j, y in enumerate(years):
            if mode == "frozen":
                lev[:, j] = cm
                continue
            yy = ymap[int(y)] if mode == "resample" else int(y)
            s = "Historical" if yy <= YSPLIT else sc
            r = C.filter((pl.col("scen") == s) & (pl.col("Year") == yy))
            r = pl.DataFrame({"Cell": np.asarray(cells, dtype=np.int32)}).join(
                r, on="Cell", how="left"
            )
            lev[:, j] = r.select(CLIM + CLIM_EXT).to_numpy().astype(float)
        assert np.all(np.isfinite(lev)), f"missing climate {gcm} {sc} {mode}"
        anom = lev - cm[:, None, :]
        out[sc] = np.concatenate([lev, anom], axis=2)
    return out


def soil_onehot(cells: list[int]) -> np.ndarray:
    s = pl.read_parquet(f"{XDE}/climate/cell_static.parquet").select(
        pl.col("Cell").cast(pl.Int32), "soil_code"
    )
    s = pl.DataFrame({"Cell": np.asarray(cells, dtype=np.int32)}).join(s, on="Cell", how="left")
    code = s["soil_code"].to_numpy()
    return np.stack([(code == k).astype(float) for k in SOILS], axis=1)


def build_sequences(gcm: str, seed: int, scens: list[str], clim_mode: str) -> dict:
    """Sequences over the dev cells for one (gcm, seed): trajectories Historical + scen.
    Returns X (S, T, D) transformed (NaN where undefined), W (S, T, D), C (S, T, F) climate of
    year t (row t = year YEAR0 + t), soil (S, 8), cell (S,), scen (S,)."""
    cells = read_cells(CELLS_DEV)
    T = YEAR1 - YEAR0 + 1
    Y = load_yearly(gcm, seed)
    hist = Y.filter(pl.col("scen") == "Historical")
    clim = climate_table(gcm, scens, clim_mode)
    soil = soil_onehot(cells)
    Xs, Ws, Cs, So, Ce, Sc = [], [], [], [], [], []
    for sc in scens:
        d = pl.concat([hist, Y.filter(pl.col("scen") == sc)], how="diagonal_relaxed").sort(
            "Cell", "Year"
        )
        assert d.height == len(cells) * T, (d.height, len(cells) * T)
        X, W = to_z_raw(d)
        Xs.append(X.reshape(len(cells), T, -1))
        Ws.append(W.reshape(len(cells), T, -1))
        Cs.append(clim[sc])
        So.append(soil)
        Ce.append(np.asarray(cells))
        Sc += [sc] * len(cells)
    return {
        "X": np.concatenate(Xs),
        "W": np.concatenate(Ws),
        "C": np.concatenate(Cs),
        "soil": np.concatenate(So),
        "cell": np.concatenate(Ce),
        "scen": np.asarray(Sc),
    }


# --------------------------------------------------------------------------------------------------
# 4. the model
# --------------------------------------------------------------------------------------------------
def _torch():
    import torch

    return torch


def make_model(d_state: int, d_in: int, hidden: int = 64, layers: int = 2):
    torch = _torch()
    nn = torch.nn

    class LSTMStats(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(d_in, hidden, num_layers=layers, batch_first=True)
            self.head = nn.Linear(hidden, d_state)
            nn.init.zeros_(self.head.weight)
            nn.init.zeros_(self.head.bias)

        def step(self, inp, hc):
            o, hc = self.lstm(inp[:, None, :], hc)
            return self.head(o[:, 0]), hc

    return LSTMStats()


def rollout(model, Z, C, soil, t_free, n_steps):
    """Z: (S, T, D) standardised truth state (filled), C: (S, T, F) standardised climate (row
    t = year t), soil: (S, 8), t_free: (S,) long: steps t < t_free take the TRUTH state as input,
    steps >= t_free their own prediction; returns P (S, n_steps, D), P[:, t] = state t+1."""
    torch = _torch()
    S = Z.shape[0]
    hc = None
    z = Z[:, 0]
    preds = []
    for t in range(n_steps):
        use_truth = (t < t_free)[:, None] if t > 0 else torch.ones(S, 1, dtype=torch.bool)
        zin = torch.where(use_truth, Z[:, t], z)
        dz, hc = model.step(torch.cat([zin, C[:, t + 1], soil], dim=1), hc)
        z = zin + dz
        preds.append(z)
    return torch.stack(preds, dim=1)


def fold_cells(k: int) -> tuple[list[int], list[int]]:
    f = pl.read_parquet(FOLDS).filter(pl.col("is_dev"))
    test = sorted(f.filter(pl.col("fold") == k)["Cell"].to_list())
    train = sorted(f.filter(pl.col("fold") != k)["Cell"].to_list())
    return train, test


def stage_train(a) -> None:
    torch = _torch()
    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "8")))
    rng = np.random.default_rng(1000 + a.fold)
    torch.manual_seed(1000 + a.fold)
    clim_mode = "frozen" if a.arm == "lstmCB" else "real"
    seq = build_sequences(TRAIN["gcm"], TRAIN["seed"], TRAIN["scens"], clim_mode)
    train_cells, _ = fold_cells(a.fold)
    f = pl.read_parquet(FOLDS).filter(pl.col("is_dev"))
    blocks = sorted(f.filter(pl.col("Cell").is_in(train_cells))["block"].unique().to_list())
    vblocks = set(
        rng.choice(blocks, size=max(1, int(round(0.15 * len(blocks)))), replace=False).tolist()
    )
    vcells = set(f.filter(pl.col("block").is_in(list(vblocks)))["Cell"].to_list()) & set(
        train_cells
    )
    tr = np.isin(seq["cell"], list(set(train_cells) - vcells))
    va = np.isin(seq["cell"], list(vcells))
    Xf = ffill_seq(seq["X"])
    # standardisation from the training sequences only
    mu = np.nanmean(seq["X"][tr].reshape(-1, Xf.shape[2]), axis=0)
    sd = np.nanstd(seq["X"][tr].reshape(-1, Xf.shape[2]), axis=0)
    sd = np.where(sd > 1e-6, sd, 1.0)
    Xf = np.where(np.isfinite(Xf), Xf, mu)
    Zs = (Xf - mu) / sd
    cmu = seq["C"][tr].reshape(-1, seq["C"].shape[2]).mean(axis=0)
    csd = seq["C"][tr].reshape(-1, seq["C"].shape[2]).std(axis=0)
    csd = np.where(csd > 1e-9, csd, 1.0)
    Cs = (seq["C"] - cmu) / csd
    D, F = Zs.shape[2], Cs.shape[2]
    model = make_model(D, D + F + len(SOILS))
    T = Zs.shape[1]

    def tt(x, m):
        return torch.tensor(x[m], dtype=torch.float32)

    Ztr, Ctr, Str, Wtr = tt(Zs, tr), tt(Cs, tr), tt(seq["soil"], tr), tt(seq["W"], tr)
    Zva, Cva, Sva, Wva = tt(Zs, va), tt(Cs, va), tt(seq["soil"], va), tt(seq["W"], va)

    def loss_fn(P, Z, W, t_free, K):
        # P[:, t] predicts Z[:, t+1]; loss on free-run steps t in [t_free-1, t_free-1+K)
        S = Z.shape[0]
        tgrid = torch.arange(P.shape[1])[None, :].expand(S, -1)
        m = ((tgrid >= (t_free - 1)[:, None]) & (tgrid < (t_free - 1 + K)[:, None])).float()
        err = (P - Z[:, 1 : P.shape[1] + 1]) ** 2 * W[:, 1 : P.shape[1] + 1]
        return (err.sum(dim=2) * m).sum() / (m.sum() * D)

    def val_loss(K=30, t_start=YSPLIT - YEAR0 + 1):
        with torch.no_grad():
            S = Zva.shape[0]
            tf = torch.full((S,), t_start, dtype=torch.long)
            P = rollout(model, Zva, Cva, Sva, tf, T - 1)
            lv = float(loss_fn(P, Zva, Wva, tf, K))
            Pp = Zva[:, t_start - 1 : t_start][
                :, [0] * (T - 1)
            ]  # persistence of the truth 2014 state
            Pp = torch.cat([Zva[:, 1:t_start], Pp[:, : T - t_start]], dim=1)
            lp = float(loss_fn(Pp, Zva, Wva, tf, K))
        return lv, lp

    opt = torch.optim.Adam(model.parameters(), lr=a.lr, weight_decay=1e-5)
    curriculum = [1, 3, 5, 10, 20, 30]
    hist = []
    best = (np.inf, None, None)
    it = 0
    t0 = time.time()
    for K in curriculum:
        n_it = a.iters if K < 30 else 2 * a.iters
        for _ in range(n_it):
            S = Ztr.shape[0]
            idx = torch.randint(0, S, (min(a.batch, S),))
            tf = torch.randint(1, T - K + 1, (len(idx),))
            nst = int(tf.max()) - 1 + K
            P = rollout(model, Ztr[idx], Ctr[idx], Str[idx], tf, nst)
            loss = loss_fn(P, Ztr[idx], Wtr[idx], tf, K)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            it += 1
            if it % 50 == 0:
                lv, lp = val_loss()
                hist.append(
                    {
                        "it": it,
                        "K": K,
                        "train": float(loss),
                        "val30": lv,
                        "val30_persist": lp,
                        "sec": round(time.time() - t0, 1),
                    }
                )
                if K >= 10 and lv < best[0]:
                    best = (lv, it, {k: v.detach().clone() for k, v in model.state_dict().items()})
                if it % 200 == 0:
                    log(json.dumps(hist[-1]))
        if K == 20:
            for gparam in opt.param_groups:
                gparam["lr"] = a.lr * 0.3
    if best[2] is not None:
        model.load_state_dict(best[2])
    lv, lp = val_loss()
    os.makedirs(f"{OUT}/models", exist_ok=True)
    torch.save(
        {"state": model.state_dict(), "mu": mu, "sd": sd, "cmu": cmu, "csd": csd, "D": D, "F": F},
        f"{OUT}/models/{a.arm}_f{a.fold}.pt",
    )
    info = {
        "arm": a.arm,
        "fold": a.fold,
        "clim_mode": clim_mode,
        "n_train_seq": int(tr.sum()),
        "n_val_seq": int(va.sum()),
        "val_blocks": sorted(int(b) for b in vblocks),
        "best_it": best[1],
        "val30_best": lv,
        "val30_persist": lp,
        "converged": bool(lv < lp),
        "iters_total": it,
        "train_seconds": round(time.time() - t0, 1),
        "history": hist,
        "lr": a.lr,
        "batch": a.batch,
        "iters_per_phase": a.iters,
    }
    json.dump(info, open(f"{OUT}/models/{a.arm}_f{a.fold}.json", "w"), indent=1)
    log(f"done fold {a.fold} arm {a.arm}: val30 {lv:.4f} vs persistence {lp:.4f} best_it {best[1]}")


def stage_submit_train(a) -> None:
    for arm in a.arms.split(","):
        body = (
            f"{PY} scripts/explore_de_rec_lstmstats.py train --arm {arm} "
            "--fold $((SLURM_ARRAY_TASK_ID+1)) "
            f"--iters {a.iters} --batch {a.batch} --lr {a.lr}"
        )
        jcf(
            f"X-C0-train-{arm}",
            body,
            cpus=8,
            mem="24G",
            time_="03:00:00",
            array="0-4",
            dep=a.dependency,
        )


# --------------------------------------------------------------------------------------------------
# 5. free runs
# --------------------------------------------------------------------------------------------------
def stage_predict(a) -> None:
    torch = _torch()
    torch.set_num_threads(1)  # single thread: the timing below is core-seconds
    arm = a.arm
    model_arm = "lstm" if arm == "lstmCBres" else arm
    clim_mode = {"lstm": "real", "lstmCB": "frozen", "lstmCBres": "resample"}[arm]
    os.makedirs(f"{OUT}/preds", exist_ok=True)
    timing = []
    for grp, (gcm, seed, scens) in TESTS.items():
        seq = build_sequences(gcm, seed, scens, clim_mode)
        T = seq["X"].shape[1]
        for k in range(1, 6):
            ck = torch.load(f"{OUT}/models/{model_arm}_f{k}.pt", weights_only=False)
            model = make_model(ck["D"], ck["D"] + ck["F"] + len(SOILS))
            model.load_state_dict(ck["state"])
            model.eval()
            _, test_cells = fold_cells(k)
            m = np.isin(seq["cell"], test_cells)
            Xf = ffill_seq(seq["X"][m])
            Xf = np.where(np.isfinite(Xf), Xf, ck["mu"])
            Z = torch.tensor((Xf - ck["mu"]) / ck["sd"], dtype=torch.float32)
            C = torch.tensor((seq["C"][m] - ck["cmu"]) / ck["csd"], dtype=torch.float32)
            So = torch.tensor(seq["soil"][m], dtype=torch.float32)
            for start, tfree in (("S14", YSPLIT - YEAR0 + 1), ("S85", 1)):
                tf = torch.full((Z.shape[0],), tfree, dtype=torch.long)
                t1 = time.process_time()
                with torch.no_grad():
                    P = rollout(model, Z, C, So, tf, T - 1).numpy()
                cpu = time.process_time() - t1
                timing.append(
                    {
                        "grp": grp,
                        "fold": k,
                        "start": start,
                        "cpu_s": cpu,
                        "cell_years": int(Z.shape[0] * (T - 1)),
                    }
                )
                Pz = P * ck["sd"] + ck["mu"]  # (S, T-1, D): years YEAR0+1 .. YEAR1
                S_ = Pz.shape[0]
                phys = from_z_raw(Pz.reshape(S_ * (T - 1), -1))
                yrs = np.tile(np.arange(YEAR0 + 1, YEAR1 + 1), S_)
                Yp = pl.DataFrame(
                    {
                        "Cell": np.repeat(seq["cell"][m], T - 1).astype(np.int32),
                        "Year": yrs.astype(np.int32),
                        "scen": np.repeat(seq["scen"][m], T - 1),
                        **{c: phys[c] for c in phys},
                    }
                ).with_columns(pl.lit(gcm).alias("gcm"))
                Yp.write_parquet(f"{OUT}/preds/yearly_{arm}_{start}_{grp}_f{k}.parquet")
                parts = []
                if start == "S85":
                    # Historical part is identical for every leg (deterministic): take the first
                    # scenario's
                    h = Yp.filter(
                        (pl.col("scen") == scens[0]) & (pl.col("Year") <= YSPLIT)
                    ).with_columns(pl.lit("Historical").alias("scen"))
                    parts.append(
                        window_stats(h, (YEAR0 + 1, YSPLIT)).with_columns(
                            pl.lit("h1985").alias("window")
                        )
                    )
                parts.append(
                    window_stats(Yp, WINDOWS["w2015"]).with_columns(pl.lit("w2015").alias("window"))
                )
                st = pl.concat(parts, how="diagonal_relaxed").drop("n_years")
                st.write_parquet(f"{OUT}/preds/stats_{arm}_{start}_{grp}_f{k}.parquet")
                log(
                    f"{arm} {start} {grp} fold {k}: {st.height} stats rows, {cpu:.2f} cpu-s for "
                    f"{Z.shape[0] * (T - 1)} cell-years"
                )
    json.dump(timing, open(f"{OUT}/preds/timing_{arm}.json", "w"), indent=1)


def stage_pers(a) -> None:
    sys.path.insert(0, f"{REPO}/scripts")
    import explore_de_reference as R

    os.makedirs(f"{OUT}/preds", exist_ok=True)
    for grp, (gcm, seed, scens) in TESTS.items():
        w = pl.read_parquet(f"{R.OUT}/frozen/{gcm}_s{seed}_y2014.parquet").select(
            ["Cell"] + R.QUANTITIES
        )
        d = pl.concat(
            [
                w.with_columns(
                    pl.lit(gcm).alias("gcm"),
                    pl.lit(sc).alias("scen"),
                    pl.lit("w2015").alias("window"),
                )
                for sc in scens
            ]
        )
        d.write_parquet(f"{OUT}/preds/stats_pers14_S14_{grp}_all.parquet")
        log(f"pers14 {grp}: {d.height}")


# --------------------------------------------------------------------------------------------------
# 6. scoring
# --------------------------------------------------------------------------------------------------
def stage_submit_score(a) -> None:
    sdir = f"{OUT}/scores"
    os.makedirs(sdir, exist_ok=True)
    os.makedirs(f"{OUT}/manifests", exist_ok=True)
    cmds = []
    arms = a.arms.split(",")
    for arm in arms:
        starts = ["S14"] if arm == "pers14" else (["ALL"] if arm == "truthagg" else ["S14", "S85"])
        for start in starts:
            for grp, (_gcm, seed, _scens) in TESTS.items():
                base = [
                    PY,
                    SCORER,
                    "score",
                    "--format",
                    "stats",
                    "--scope",
                    "covered",
                    "--split",
                    SPLIT,
                    "--legs-branched",
                    "yes",
                    "--truth-seed",
                    str(seed),
                    "--out",
                    sdir,
                ]
                if start in ("S14", "S85"):
                    # stats format: the initial-state year is excluded by the submission itself
                    # (S85's h1985 is
                    # built from 1986-2014; S14 emits no h1985), so no --start-year here (roster-
                    # only flag)
                    base += ["--start-seed", str(seed)]
                if arm in ("pers14", "truthagg"):
                    pred = (
                        f"{OUT}/preds/stats_pers14_S14_{grp}_all.parquet"
                        if arm == "pers14"
                        else f"{OUT}/preds/truthagg_{grp}.parquet"
                    )
                    for cl, cf in (("f5", CELLS_F5), ("dev", CELLS_DEV)):
                        lab = f"C0{arm}_{start}_{grp}_{cl}"
                        cmds.append(
                            base
                            + [
                                "--pred",
                                pred,
                                "--label",
                                lab,
                                "--cells",
                                cf,
                                "--held-out-place",
                                "true",
                            ]
                        )
                    continue
                # fold 5 alone (folds 1-4 trained it)
                lab = f"C0{arm}_{start}_{grp}_f5"
                cmds.append(
                    base
                    + [
                        "--pred",
                        f"{OUT}/preds/stats_{arm}_{start}_{grp}_f5.parquet",
                        "--label",
                        lab,
                        "--cells",
                        CELLS_F5,
                        "--held-out-place",
                        "true",
                    ]
                )
                # pooled cross-fit: every fold model on its own fold only
                man = f"{OUT}/manifests/{arm}_{start}_{grp}.csv"
                pl.DataFrame(
                    {
                        "pred": [
                            f"{OUT}/preds/stats_{arm}_{start}_{grp}_f{k}.parquet"
                            for k in range(1, 6)
                        ],
                        "format": ["stats"] * 5,
                        "fold": [str(k) for k in range(1, 6)],
                    }
                ).write_csv(man)
                lab = f"C0{arm}_{start}_{grp}_xf"
                cmds.append(
                    base
                    + [
                        "--manifest",
                        man,
                        "--label",
                        lab,
                        "--cells",
                        CELLS_DEV,
                        "--held-out-place",
                        "true",
                    ]
                )
    lst = f"{JOBS}/X-C0-score.cmds"
    with open(lst, "w") as fh:
        for c in cmds:
            fh.write(" ".join(c) + "\n")
    body = f'CMD=$(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" {lst})\necho "$CMD"\neval "$CMD"'
    jcf(
        "X-C0-score",
        body,
        cpus=4,
        mem="40G",
        time_="01:00:00",
        array=f"0-{len(cmds) - 1}%12",
        dep=a.dependency,
    )
    log(f"{len(cmds)} scorer calls")


def stage_report(a) -> None:
    sdir = f"{OUT}/scores"
    rows = []
    for d in sorted(glob.glob(f"{sdir}/C0*")):
        lab = os.path.basename(d)
        for scale, sub in (("cell", ""), ("block", "block")):
            f = os.path.join(d, sub, "summary_conjunctive.csv")
            if not os.path.exists(f):
                continue
            s = pl.read_csv(f, infer_schema_length=10000).filter(pl.col("panel") == "panel106")
            for r in s.iter_rows(named=True):
                row = {
                    "label": lab,
                    "scale": scale,
                    "gcm": r["gcm"],
                    "scen": r["scen"],
                    "window": r["window"],
                    "role": r.get("role"),
                    "held_out": r.get("held_out"),
                    "n_units": r["n_cells"],
                }
                for p in ("cal", "cal_xg"):
                    v, c = r.get(f"all_pass_{p}_frac"), r.get(f"ceiling_same_all_pass_{p}_frac")
                    row[f"pass_{p}"] = v
                    row[f"ceiling_{p}"] = c
                rows.append(row)
        pg = os.path.join(d, "primary_gate.csv")
        if os.path.exists(pg):
            for r in pl.read_csv(pg, infer_schema_length=10000).iter_rows(named=True):
                rows.append(
                    {
                        "label": lab,
                        "scale": r["scale"],
                        "gcm": r["gcm"],
                        "scen": r["scen"],
                        "window": "PRIMARY_" + r["window"],
                        "role": r["role"],
                        "held_out": r["held_out"],
                        "pass_cal_xg": r["arm_cal_xg"],
                        "ceiling_cal_xg": r["ceiling_same_cal_xg"],
                        "verdict": r["verdict"],
                    }
                )
    df = pl.DataFrame(rows, infer_schema_length=None)
    df.write_csv(f"{OUT}/comparison_C0.csv")
    pl.Config.set_tbl_rows(400)
    pl.Config.set_tbl_cols(14)
    pl.Config.set_tbl_width_chars(220)
    print(df.sort("label", "scale", "window", "scen"))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "stage",
        choices=[
            "yearly",
            "submit-yearly",
            "replay",
            "train",
            "submit-train",
            "predict",
            "pers",
            "submit-score",
            "report",
        ],
    )
    ap.add_argument("--member")
    ap.add_argument("--fold", type=int)
    ap.add_argument("--arm", default="lstm")
    ap.add_argument("--arms", default="lstm,lstmCB")
    ap.add_argument("--iters", type=int, default=300)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--dependency")
    a = ap.parse_args(argv)
    {
        "yearly": stage_yearly,
        "submit-yearly": stage_submit_yearly,
        "replay": stage_replay,
        "train": stage_train,
        "submit-train": stage_submit_train,
        "predict": stage_predict,
        "pers": stage_pers,
        "submit-score": stage_submit_score,
        "report": stage_report,
    }[a.stage](a)


if __name__ == "__main__":
    main()
