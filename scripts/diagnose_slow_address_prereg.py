#!/usr/bin/env python3
"""PRE-REGISTRATION for the ADR-0040 address-vs-response experiment. Zero new compute; run BEFORE the forests.

WHY THIS EXISTS, and why it must run first
------------------------------------------
ADR 0038 recorded that the copula's +0.037 Wooddens `emu_r` gain comes from six per-cell env columns with
median within-cell sd exactly 0, and proposed the decision rule *"decays toward the 1-NN level (r ~ 0.80)
=> it is an address."* **That rule is wrong, and it would have produced a confident wrong verdict.** 0.80 is
the address's skill under `mod(hash(cell), k)` folds, where every test cell has a training neighbour 0.5°
away. It is not the address's skill under BLOCKED folds, which is what the blocked runs will be compared
against. Using the hash-fold number as the blocked-fold null is exactly the reference-basis error guardrail 7
exists for (CLAUDE.md §6.7), and the size of the mistake is larger than the effect: a pure address scores
far below 0.80 once adjacency is severed, so a blocked p14env landing near 0.78 would be declared "decayed
to the address level" when it is in fact overwhelming evidence AGAINST the address hypothesis.

So this script derives the null under EACH fold design, from the same artifacts, with no forest involved —
and it must be frozen into the ADR before any blocked forest log is read. That ordering is the only thing
that stops the decision rule being written after the outcome is known.

It also computes the read-out that the whole S2 milestone has been missing.

THE SECOND GATE: the WARMING response, not the level
----------------------------------------------------
`emu_r` is a LEVEL statistic over per-cell medians. On the pooled table the historic->ssp370 per-cell shift
has sd equal to only ~18-29 % of the between-cell sd of the level, so `emu_r` is ~4-5x more sensitive to
spatial interpolation than to the transient response — and the transient response is the ONLY thing a
coupled warming run turns on. Blocked CV tests whether the published number is honest; it does not test
production risk. Both are gates now. This script measures the transient one directly from the existing
per-row predictions and the `scenario.i64` sidecar the pooled table already carries.

WHAT IT COMPUTES
----------------
`--mode response` (R0-A), per axis, on per-cell medians taken SEPARATELY in the historic and ssp370 blocks
for cells with >= MINSTEM stems in BOTH:
  * `Rr`  = r(Dpred, Dobs)                — is the pattern of the shift predicted at all?
  * `Ra`  = sd(Dpred) / sd_true(Dobs)      — amplitude, with sd_true noise-corrected by a split-half estimate
                                             of Dobs's own reliability (the shift is a difference of two
                                             noisy medians, so its raw sd is inflated; not correcting this
                                             makes every emulator look under-dispersed)
  * `Rb`  = mean(Dpred) - mean(Dobs)       — systematic damping or amplification of the mean shift
  * `ceil` = sqrt(reliability)              — the highest `Rr` any predictor could reach
  all with a TILE-CLUSTER bootstrap 95 % CI (resampling 15° tiles, not cells: the naive per-cell bootstrap
  understates the spatial-sampling sd of these statistics by ~5x because neighbouring cells are not
  independent).

`--mode surrogate` (R0-B), per axis and per fold design in FOLDMAP_DIR: 1-NN transfer of the per-cell median
from the training fold, in four conditioning spaces —
  * `geo`   unit-sphere position                     = a PURE ADDRESS. **This is the pre-registered null.**
  * `env6`  the 6 env columns, IQR-standardised      = the static climate ENVELOPE
  * `dyn7`  per-cell means of the 7 live base columns (the `co2` column is a dead constant, ADR 0004)
  * `both`  dyn7 + env6                              = the conditioning the 14-column artifact carries
and reports `DELTA = both - dyn7`, the surrogate of the conditioning lever. A forest is not needed to learn
whether the lever's INFORMATION survives blocking; 1-NN is a weak learner, so it is a conservative screen.

The fold designs are READ from fold maps written by `scripts/blocked_cv_folds_probe.jl`
(`cell fold bufmask`), because `mod(hash(tile), k)` is Julia's `hash` and Python cannot reproduce it — and a
Python-recomputed split would silently score a different experiment than the one the forests run.

Usage:
    TABLE=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8 \
    FOLDMAP_DIR=/p/tmp/jamirp/emulator_global/tables/foldmaps \
    CELL_LATLON=/p/tmp/jamirp/emulator_global/tables/cell_latlon.txt \
      python scripts/diagnose_slow_address_prereg.py --mode surrogate

    TABLE=/p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8 \
    PRED=/p/tmp/jamirp/emulator_global/capacity/frozen-pooled-env-qrf-b6x2M LABEL=p14env \
      python scripts/diagnose_slow_address_prereg.py --mode response

Env: TABLE (required: Y_*.f64 + cells.i64 + scenario.i64 + manifest), PRED + LABEL (response mode; may be
     repeated as PRED2/LABEL2), FOLDMAP_DIR + CELL_LATLON (surrogate mode), MINSTEM (20), AXES,
     NBOOT (400), TILE_DEG (15), ENV_COLS, CELL_YEAR_FEATS.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy.spatial import cKDTree

BASE = "/p/tmp/jamirp/emulator_global"
TABLE = os.environ.get("TABLE", f"{BASE}/slow_copula_pooled_w20_t8")
MINSTEM = int(os.environ.get("MINSTEM", "20"))
NBOOT = int(os.environ.get("NBOOT", "400"))
TILE_DEG = float(os.environ.get("TILE_DEG", "15"))
CELL_LATLON = os.environ.get("CELL_LATLON", f"{BASE}/tables/cell_latlon.txt")
FOLDMAP_DIR = os.environ.get("FOLDMAP_DIR", f"{BASE}/tables/foldmaps")
CELL_YEAR_FEATS = os.environ.get("CELL_YEAR_FEATS", f"{BASE}/tables/cell_year_feats.parquet")
ENV_COLS = [
    c.strip()
    for c in os.environ.get(
        "ENV_COLS",
        "prec_mean,eco_diag_p_pet_ratio,eco_diag_pet_mean,eco_diag_vpd_mean,pr_cv_monthly,humid_mean",
    ).split(",")
    if c.strip()
]


def manifest(d: str) -> dict:
    m = {}
    for line in open(f"{d}/manifest_copula.txt"):
        p = line.rstrip("\n").split("\t")
        if len(p) == 2:
            m[p[0]] = p[1]
    return m


def latlon() -> pl.DataFrame:
    rows = []
    for line in open(CELL_LATLON):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        p = s.split()
        rows.append((int(p[0]), float(p[3]), float(p[4])))
    return pl.DataFrame({"Cell": [r[0] for r in rows], "lat": [r[1] for r in rows], "lon": [r[2] for r in rows]})


def latlon_lut(ll: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Cell-indexed lat/lon arrays, so a tile label can be taken in the CALLER's row order.

    Why this exists rather than a join: the response mode used to build its bootstrap cluster labels as
    `ll.join(DataFrame(Cell=cells_of_the_statistic), on="Cell", how="inner")`, which returns rows in **`ll`'s**
    order, while `dp`/`dy` are in the order polars' `group_by` happened to emit. The labels were therefore a
    PERMUTATION of the rows they were supposed to cluster, and a `tl = tl[:min(len(tl), len(dy))]` truncation
    silently absorbed any length mismatch on top of that. Scrambled cluster labels make a tile bootstrap
    degenerate toward an independent-cell bootstrap, i.e. they UNDERSTATE the spatial sampling sd — the exact
    error the tile clustering was introduced to remove.

    It was invisible because the point estimates never use `tl`, so only the CIs were wrong. The detector was
    reproducibility: `cluster_boot` has a FIXED `seed=12345`, yet two runs over identical inputs (jobs 1681338
    and 1681925) printed identical point estimates and DIFFERENT CIs — possible only because
    `per_cell_scenario`'s `group_by` row order varies run to run while `ll`'s does not.
    `[VERIFIED 2026-08-03]`
    """
    cell = ll["Cell"].to_numpy()
    n = int(cell.max()) + 1
    lat = np.full(n, np.nan)
    lon = np.full(n, np.nan)
    lat[cell] = ll["lat"].to_numpy()
    lon[cell] = ll["lon"].to_numpy()
    return lat, lon


def unit_sphere(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    la, lo = np.deg2rad(lat), np.deg2rad(lon)
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def tile_id(lat: np.ndarray, lon: np.ndarray, deg: float) -> np.ndarray:
    """Bootstrap CLUSTER id. Resampling cells treats neighbours as independent, which they are not."""
    return (np.floor((lat + 90.0) / deg) * 100000 + np.floor((lon + 180.0) / deg)).astype(np.int64)


def cluster_boot(stat_fn, tiles: np.ndarray, nboot: int, seed: int = 12345):
    """Tile-cluster bootstrap CI: resample whole tiles with replacement, recompute the statistic."""
    rng = np.random.default_rng(seed)
    ut = np.unique(tiles)
    idx_by_tile = {t: np.flatnonzero(tiles == t) for t in ut}
    out = []
    for _ in range(nboot):
        pick = rng.choice(ut, size=len(ut), replace=True)
        sel = np.concatenate([idx_by_tile[t] for t in pick])
        v = stat_fn(sel)
        if v is not None and np.isfinite(v):
            out.append(v)
    if len(out) < 20:
        return (np.nan, np.nan, np.nan)
    a = np.sort(np.asarray(out))
    return (float(np.std(a)), float(a[int(0.025 * len(a))]), float(a[int(0.975 * len(a)) - 1]))


# ----------------------------------------------------------------------------- R0-A: warming response
def per_cell_scenario(pred_dir: str, axes: list[str]) -> pl.DataFrame:
    """Per (Cell, scenario) median of Y and pred, plus the rank-parity half-medians of Y for reliability."""
    cells = np.fromfile(f"{TABLE}/cells.i64", dtype="<i8")
    scen = np.fromfile(f"{TABLE}/scenario.i64", dtype="<i8")
    if len(scen) != len(cells):
        raise SystemExit("FATAL: scenario.i64 length != cells.i64 length")
    out = None
    for a in axes:
        y = np.fromfile(f"{TABLE}/Y_{a}.f64", dtype="<f8")
        p = np.fromfile(f"{pred_dir}/pred_{a}.f64", dtype="<f8")
        if not (len(y) == len(p) == len(cells)):
            raise SystemExit(f"FATAL: length mismatch on axis {a}")
        df = pl.DataFrame({"Cell": cells, "scen": scen, "y": y, "p": p})
        df = df.with_columns((pl.int_range(pl.len()).over(["Cell", "scen"]) % 2).alias("h"))
        d = df.group_by(["Cell", "scen"]).agg(
            pl.col("y").median().alias(f"y_{a}"),
            pl.col("p").median().alias(f"p_{a}"),
            pl.col("y").filter(pl.col("h") == 0).median().alias(f"h0_{a}"),
            pl.col("y").filter(pl.col("h") == 1).median().alias(f"h1_{a}"),
            pl.len().alias(f"n_{a}"),
        )
        out = d if out is None else out.join(d, on=["Cell", "scen"], how="inner")
    return out


def mode_response(axes: list[str]) -> None:
    preds = [(os.environ["PRED"], os.environ.get("LABEL", "A"))]
    if os.environ.get("PRED2", "").strip():
        preds.append((os.environ["PRED2"], os.environ.get("LABEL2", "B")))
    ll = latlon()
    LAT_BY_CELL, LON_BY_CELL = latlon_lut(ll)
    print("== R0-A  WARMING RESPONSE from existing predictions (zero new compute)")
    print(f"   table {TABLE}   MINSTEM={MINSTEM} in BOTH scenario blocks   NBOOT={NBOOT} tile-{TILE_DEG}deg clusters")
    for pred_dir, label in preds:
        t = per_cell_scenario(pred_dir, axes)
        sc = sorted(t["scen"].unique().to_list())
        if len(sc) != 2:
            raise SystemExit(f"FATAL: expected 2 scenario tags, got {sc} — not a pooled table?")
        lo, hi = sc
        a0 = t.filter(pl.col("scen") == lo)
        a1 = t.filter(pl.col("scen") == hi)
        j = a0.join(a1, on="Cell", how="inner", suffix="_hi")
        print(f"\n-- {label}  ({pred_dir})")
        print(f"   {j.height} cells present in both scenario blocks (tags {lo} -> {hi})")
        for a in axes:
            k = j.filter((pl.col(f"n_{a}") >= MINSTEM) & (pl.col(f"n_{a}_hi") >= MINSTEM))
            dy = k[f"y_{a}_hi"].to_numpy() - k[f"y_{a}"].to_numpy()
            dp = k[f"p_{a}_hi"].to_numpy() - k[f"p_{a}"].to_numpy()
            lev = k[f"y_{a}"].to_numpy()
            # split-half reliability of the OBSERVED shift: the same difference formed from the two
            # rank-parity halves. Spearman-Brown lifts a half-length correlation to full length.
            dh0 = k[f"h0_{a}_hi"].to_numpy() - k[f"h0_{a}"].to_numpy()
            dh1 = k[f"h1_{a}_hi"].to_numpy() - k[f"h1_{a}"].to_numpy()
            ok = np.isfinite(dy) & np.isfinite(dp) & np.isfinite(dh0) & np.isfinite(dh1)
            dy, dp, dh0, dh1, lev = dy[ok], dp[ok], dh0[ok], dh1[ok], lev[ok]
            rh = float(np.corrcoef(dh0, dh1)[0, 1])
            rel = 2 * rh / (1 + rh) if rh > -1 else np.nan
            sd_true = float(np.std(dy)) * np.sqrt(max(rel, 0.0))
            # Tile labels in the STATISTIC's row order — never via a join (see latlon_lut's docstring).
            cells_k = k["Cell"].to_numpy()[ok]
            if cells_k.max() >= LAT_BY_CELL.size or not np.isfinite(LAT_BY_CELL[cells_k]).all():
                miss = cells_k[~np.isfinite(LAT_BY_CELL[np.minimum(cells_k, LAT_BY_CELL.size - 1)])]
                raise SystemExit(f"FATAL: {np.unique(miss).size} cells absent from {CELL_LATLON}")
            tl = tile_id(LAT_BY_CELL[cells_k], LON_BY_CELL[cells_k], TILE_DEG)
            assert tl.size == dy.size, f"tile labels {tl.size} != rows {dy.size}"
            Rr = float(np.corrcoef(dp, dy)[0, 1])
            Ra = float(np.std(dp)) / sd_true if sd_true > 0 else np.nan
            Rb = float(np.mean(dp) - np.mean(dy))
            sdr, r_lo, r_hi = cluster_boot(lambda s: float(np.corrcoef(dp[s], dy[s])[0, 1]), tl, NBOOT)
            sdb, b_lo, b_hi = cluster_boot(lambda s: float(np.mean(dp[s]) - np.mean(dy[s])), tl, NBOOT)
            print(
                f"   {a:<10s} n={len(dy):>6d}  Rr={Rr:+.4f} [{r_lo:+.4f},{r_hi:+.4f}]  "
                f"ceil={np.sqrt(max(rel, 0.0)):.4f}  Ra={Ra:.4f}  "
                f"Rb={Rb:+.5g} [{b_lo:+.5g},{b_hi:+.5g}]  "
                f"meanDobs={np.mean(dy):+.5g}  sd(Dobs)/sd(level)={np.std(dy) / np.std(lev):.4f}"
            )
        print("   Rb CI excluding 0 ⇒ the mean shift is systematically damped (negative) or amplified.")
        print("   sd(Dobs)/sd(level) is why `emu_r` is a weak production gate: the warming signal is that")
        print("   fraction of the spatial signal, so a level statistic is ~1/that more sensitive to space.")


# ----------------------------------------------------------------------------- R0-B: 1-NN surrogate
def read_foldmap(path: str):
    meta, cells, fold, mask = {}, [], [], []
    for line in open(path):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            p = s.split()
            if len(p) == 3:
                meta[p[1]] = p[2]
            continue
        p = s.split()
        cells.append(int(p[0]))
        fold.append(int(p[1]))
        mask.append(int(p[2]))
    return meta, np.array(cells), np.array(fold), np.array(mask)


def percell_medians(axes: list[str]) -> pl.DataFrame:
    cells = np.fromfile(f"{TABLE}/cells.i64", dtype="<i8")
    out = None
    for a in axes:
        y = np.fromfile(f"{TABLE}/Y_{a}.f64", dtype="<f8")
        d = (
            pl.DataFrame({"Cell": cells, "y": y})
            .group_by("Cell")
            .agg(pl.col("y").median().alias(f"y_{a}"), pl.len().alias("nstem"))
        )
        out = d if out is None else out.join(d.drop("nstem"), on="Cell", how="inner")
    return out


def dyn_means(ncond: int, nbase: int = 7) -> pl.DataFrame:
    """Per-cell means of the LIVE base conditioning columns, straight off the table's own Xc."""
    cells = np.fromfile(f"{TABLE}/cells.i64", dtype="<i8")
    n = len(cells)
    X = np.memmap(f"{TABLE}/Xc.f64", dtype="<f8", mode="r", shape=(n, ncond))
    acc = {}
    step = 4_000_000
    sums = np.zeros((int(cells.max()) + 1, nbase))
    cnts = np.zeros(int(cells.max()) + 1)
    for i0 in range(0, n, step):
        i1 = min(n, i0 + step)
        blk = np.asarray(X[i0:i1, :nbase], dtype=np.float64)
        c = cells[i0:i1]
        np.add.at(sums, c, blk)
        np.add.at(cnts, c, 1.0)
    keep = cnts > 0
    ids = np.flatnonzero(keep)
    acc["Cell"] = ids
    for j in range(nbase):
        acc[f"dyn{j}"] = sums[ids, j] / cnts[ids]
    return pl.DataFrame(acc)


def nn_r(space: np.ndarray, y: np.ndarray, fold: np.ndarray, mask: np.ndarray) -> float:
    """1-NN transfer of y from each fold's TRAINING set (fold != k, minus the buffered cells)."""
    pred = np.full(len(y), np.nan)
    for k in np.unique(fold):
        te = fold == k
        tr = (~te) & ((mask & (1 << int(k))) == 0)
        if te.sum() < 2 or tr.sum() < 2:
            continue
        d, j = cKDTree(space[tr]).query(space[te], k=1)
        pred[te] = y[tr][j]
    ok = np.isfinite(pred)
    return float(np.corrcoef(pred[ok], y[ok])[0, 1]) if ok.sum() > 10 else np.nan


def mode_surrogate(axes: list[str], ncond: int) -> None:
    print("== R0-B  1-NN SURROGATE — the fold-mode-matched ADDRESS NULL (zero new compute, no forest)")
    print("   `geo` is the PRE-REGISTERED NULL for each fold design. The published r~0.80 is the HASH-fold")
    print("   number and must NOT be used as the blocked-fold null (that is the ADR-0040 correction).")
    med = percell_medians(axes).filter(pl.col("nstem") >= MINSTEM)
    ll = latlon()
    env = (
        pl.scan_parquet(CELL_YEAR_FEATS)
        .select(["Cell"] + ENV_COLS)
        .group_by("Cell")
        .agg([pl.col(c).cast(pl.Float64).mean().alias(c) for c in ENV_COLS])
        .collect()
    )
    dyn = dyn_means(ncond)
    t = med.join(ll, on="Cell", how="inner").join(env, on="Cell", how="inner").join(dyn, on="Cell", how="inner")
    print(f"   {t.height} cells with >= {MINSTEM} stems and full covariates")

    geo = unit_sphere(t["lat"].to_numpy(), t["lon"].to_numpy())

    def iqr_std(cols):
        a = np.column_stack([t[c].to_numpy() for c in cols]).astype(np.float64)
        q = np.percentile(a, [25, 75], axis=0)
        s = np.where((q[1] - q[0]) > 0, q[1] - q[0], 1.0)
        return (a - np.median(a, axis=0)) / s

    env6 = iqr_std(ENV_COLS)
    dyn7 = iqr_std([f"dyn{j}" for j in range(7)])
    spaces = {"geo": geo, "env6": env6, "dyn7": dyn7, "both": np.hstack([dyn7, env6])}

    maps = sorted(Path(FOLDMAP_DIR).glob("foldmap_*.txt"))
    if not maps:
        raise SystemExit(f"FATAL: no foldmap_*.txt in {FOLDMAP_DIR} — run scripts/blocked_cv_folds_probe.jl with FOLDMAP_DIR set")
    cellv = t["Cell"].to_numpy()
    for mp in maps:
        meta, mc, mf, mm = read_foldmap(str(mp))
        fm = pl.DataFrame({"Cell": mc, "f": mf, "m": mm}).join(pl.DataFrame({"Cell": cellv}), on="Cell", how="inner")
        order = {c: i for i, c in enumerate(cellv)}
        pos = np.array([order[c] for c in fm["Cell"].to_numpy()])
        fold = np.full(len(cellv), -1)
        mask = np.zeros(len(cellv), dtype=np.int64)
        fold[pos] = fm["f"].to_numpy()
        mask[pos] = fm["m"].to_numpy()
        sel = fold >= 0
        tag = f"{meta.get('mode', '?')} B={meta.get('block_deg', '-')} D={meta.get('buffer_deg', '-')} salt={meta.get('salt', '-')}"
        ntr = np.mean([((fold != k) & ((mask & (1 << int(k))) == 0) & sel).sum() for k in np.unique(fold[sel])])
        print(f"\n-- {mp.name}   {tag}   mean train cells/fold = {ntr:.0f} of {sel.sum()}")
        for a in axes:
            y = t[f"y_{a}"].to_numpy()
            rs = {k: nn_r(v[sel], y[sel], fold[sel], mask[sel]) for k, v in spaces.items()}
            print(
                f"   {a:<10s} geo(NULL)={rs['geo']:+.4f}  env6={rs['env6']:+.4f}  dyn7={rs['dyn7']:+.4f}  "
                f"both={rs['both']:+.4f}  DELTA(both-dyn7)={rs['both'] - rs['dyn7']:+.4f}"
            )


def main() -> None:
    mode = "surrogate"
    if "--mode" in sys.argv:
        mode = sys.argv[sys.argv.index("--mode") + 1]
    man = manifest(TABLE)
    axes = os.environ.get("AXES", man.get("axes", "SLA Wooddens D95max minwscal")).split()
    ncond = int(man["ncond"])
    if mode == "response":
        mode_response(axes)
    elif mode == "surrogate":
        mode_surrogate(axes, ncond)
    else:
        raise SystemExit(f"FATAL: --mode must be response|surrogate, got {mode}")
    print("\n== done")


if __name__ == "__main__":
    main()
