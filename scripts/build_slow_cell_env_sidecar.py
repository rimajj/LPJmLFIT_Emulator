#!/usr/bin/env python3
"""Emit the PER-CELL env conditioning sidecar (`cell_env.parquet`) a coupled caller needs — ADR 0038/0040.

WHY THIS EXISTS
---------------
The 14-column recruit-trait copula conditions on six per-cell env columns appended to the eight base
`cond_cols`. Nothing in the runtime supplies those six values. `FluxDrivenSlowEmulator` / the `.rcop`
sampler are handed a conditioning vector by the caller, and the four base boundary values arrive through
`M_cells.csv`, but the env tail has no such channel: every user so far has hand-built it by scanning
`tables/cell_year_feats.parquet` inside a bespoke script. That makes the 14-column artifact **not
coupled-runnable** — it is unreachable from CI, and it is basis-sensitive in the one way this project has
already been bitten by (ADR 0023: the runtime feature and the training column must be the SAME quantity).
Both open handoffs list this sidecar as a standing blocker, on both tracks.

So: emit the six values per cell, ONCE, by the same aggregation the training tail used, and **gate the
result against the shipped artifact's own `Xc`** rather than against a re-run of the code that produced it.

THE BASIS, stated because getting it wrong is silent
----------------------------------------------------
The training tail is a per-CELL time MEAN over `cell_year_feats.parquet` with **no year filter at all**
(`build_slow_copula_env_augment.py`: the year filter was REMOVED because `Year >= FIRSTYEAR` is a no-op for
historic and selects ZERO rows for ssp370). `cell_year_feats` spans Year 2000-2019 only, so the tail is a
2000-2019 historic climatology **for every scenario** — the same basis as the static boundary it is appended
to. This script reproduces exactly that, and records it in the sidecar manifest.

Consequence worth restating rather than hiding: because the tail is static, an ssp370 row carries the
historic climatology, so these columns cannot carry a transient response by construction (ADR 0040 §7). This
sidecar is therefore the correct provisioning for the artifact AS IT EXISTS; it is not a fix for that.

THE GATE — this is the point of the script
------------------------------------------
A sidecar recomputed with the same code as the trainer proves nothing (it is circular). So the check reads
the SHIPPED table's `Xc.f64` columns `ncond_base .. ncond-1` for a random sample of real rows, looks up each
row's cell in the freshly built sidecar, and requires **exact float64 equality**. That closes the loop
end-to-end: whatever the runtime reads out of this parquet is bit-identical to what the forest was
conditioned on for that cell. Any mismatch means a train/inference shift and the script exits non-zero.

Also asserted: one row per Cell; the six columns finite everywhere; the emitted column ORDER equals the
shipped manifest's `cond_cols` tail order (a permuted sidecar would be silently accepted by a positional
consumer, which is exactly how a 14-column artifact would be mis-conditioned).

COVERAGE. The sidecar is emitted for every cell in `cell_year_feats` (67 420), a SUPERSET of the pinned
table's 58 766 tree-recruit cells, so line M can provision any grid cell without regenerating it. The
manifest records both counts and which cells are outside the pinned table's support (there the values are
valid climatology but the forest never saw a row from that cell).

Env:
  TABLE  the shipped 14-column table to gate against
         (default /p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8env)
  BASE   the 8-column source it was augmented from, used only to learn `ncond_base`
         (default /p/tmp/jamirp/emulator_global/slow_copula_pooled_w20_t8)
  OUT    output parquet (default /p/tmp/jamirp/emulator_global/tables/cell_env.parquet)
  NPROBE number of random rows to gate (default 200_000)
  SEED   probe RNG seed (default 20260803)

Run:  python3 scripts/build_slow_cell_env_sidecar.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

BASE_DIR = Path("/p/tmp/jamirp/emulator_global")
CELL_YEAR_FEATS = BASE_DIR / "tables" / "cell_year_feats.parquet"

TABLE = Path(os.environ.get("TABLE", str(BASE_DIR / "slow_copula_pooled_w20_t8env")))
BASE = Path(os.environ.get("BASE", str(BASE_DIR / "slow_copula_pooled_w20_t8")))
OUT = Path(os.environ.get("OUT", str(BASE_DIR / "tables" / "cell_env.parquet")))
NPROBE = int(os.environ.get("NPROBE", "200000"))
SEED = int(os.environ.get("SEED", "20260803"))


def read_manifest(d: Path) -> dict[str, str]:
    man: dict[str, str] = {}
    for line in (d / "manifest_copula.txt").read_text().splitlines():
        if "\t" in line:
            k, v = line.split("\t", 1)
            man[k] = v
    return man


def main() -> None:
    if not CELL_YEAR_FEATS.is_file():
        raise SystemExit(f"FATAL: no {CELL_YEAR_FEATS}")
    man = read_manifest(TABLE)
    man_base = read_manifest(BASE)
    ncond = int(man["ncond"])
    ncond_base = int(man_base["ncond"])
    cond_cols = man["cond_cols"].split()
    assert len(cond_cols) == ncond, f"manifest cond_cols/ncond mismatch: {len(cond_cols)} vs {ncond}"
    env_cols = cond_cols[ncond_base:]
    nenv = len(env_cols)
    if nenv <= 0:
        raise SystemExit(f"FATAL: {TABLE} has no env tail ({ncond} == base {ncond_base})")
    print(f"== gating against {TABLE}")
    print(f"   ncond {ncond_base} -> {ncond}   env tail ({nenv}) = {' '.join(env_cols)}")

    # ---- build the sidecar: the trainer's aggregation, no year filter -------------------------------
    have = pl.scan_parquet(CELL_YEAR_FEATS).collect_schema().names()
    missing = [c for c in env_cols if c not in have]
    if missing:
        raise SystemExit(f"FATAL: env cols absent from {CELL_YEAR_FEATS}: {missing}")
    yr = pl.scan_parquet(CELL_YEAR_FEATS).select(
        pl.col("Year").min().alias("y0"), pl.col("Year").max().alias("y1")
    ).collect()
    y0, y1 = int(yr["y0"][0]), int(yr["y1"][0])
    # ⚠ CAST TO Float64 BEFORE THE MEAN. Four of the six env columns are stored **Float32** in
    # `cell_year_feats.parquet` (`eco_diag_p_pet_ratio`, `eco_diag_pet_mean`, `eco_diag_vpd_mean`,
    # `pr_cv_monthly`; `prec_mean` and `humid_mean` are Float64), and polars' `group_by().mean()` on a
    # Float32 column ACCUMULATES IN Float32 and returns Float32. Aggregating natively therefore lands
    # ~3.35e-07 relative away from the values the shipped artifact was conditioned on — the naive version
    # of this script missed on 199 093 of 200 000 probed rows (max |diff| 7.63e-05 on `eco_diag_pet_mean`,
    # = 5*2^-16, the float32 tell), while the two Float64 columns matched exactly. Casting first reproduces
    # the shipped `Xc` tail BIT-EXACTLY, which is what makes the gate below an equality test rather than a
    # tolerance. `[VERIFIED 2026-08-03]` by scripts-adjacent diagnostic on 50 000 rows: native 49 771/50 000
    # rows differing, cast-first 0/50 000.
    env = (
        pl.scan_parquet(CELL_YEAR_FEATS)
        .select(["Cell"] + [pl.col(c).cast(pl.Float64) for c in env_cols])
        .group_by("Cell")
        .mean()
        .sort("Cell")
        .collect()
    )
    if env.height == 0:
        raise SystemExit("FATAL: the env aggregation produced ZERO cells")
    assert env.select("Cell").n_unique() == env.height, "duplicated Cell in the env aggregate"
    vals = env.select(env_cols).to_numpy().astype("<f8")
    if not np.isfinite(vals).all():
        bad = int((~np.isfinite(vals)).any(axis=1).sum())
        raise SystemExit(f"FATAL: {bad} cells have a non-finite env value")
    print(f"   built {env.height:,} cells x {nenv} cols from Year {y0}-{y1} (no year filter — trainer basis)")

    # ---- the GATE: the shipped Xc's own tail, for real rows -----------------------------------------
    n = int(man["n"])
    cells = np.fromfile(TABLE / "cells.i64", dtype="<i8")
    assert cells.size == n, f"cells.i64 has {cells.size} entries, manifest n={n}"
    Xc = np.memmap(TABLE / "Xc.f64", dtype="<f8", mode="r", shape=(n, ncond))
    rng = np.random.default_rng(SEED)
    probe = np.sort(rng.choice(n, size=min(NPROBE, n), replace=False))
    got = np.asarray(Xc[probe, ncond_base:])              # what the forest was conditioned on
    cmax = int(env["Cell"].max())
    lut = np.full((cmax + 1, nenv), np.nan, dtype="<f8")
    lut[env["Cell"].to_numpy()] = vals
    want = lut[cells[probe]]                              # what a runtime caller would read
    if np.isnan(want).any():
        uncov = np.unique(cells[probe][np.isnan(want).any(axis=1)])
        raise SystemExit(f"FATAL: {uncov.size} probed cells absent from the sidecar, e.g. {uncov[:5]}")
    if not np.array_equal(got, want):
        d = np.abs(got - want)
        j = int(np.unravel_index(np.argmax(d), d.shape)[1])
        raise SystemExit(
            f"FATAL: sidecar != the shipped Xc tail on {int((d > 0).any(axis=1).sum())} of "
            f"{probe.size} probed rows (worst column {env_cols[j]}, max |diff| {d.max():.6g}). "
            "That is a train/inference shift — do NOT ship this sidecar."
        )
    print(f"   GATE OK: exact float64 equality on {probe.size:,} random rows of {TABLE.name}/Xc.f64")

    # ---- coverage vs the pinned table's support ----------------------------------------------------
    tcells = np.unique(cells)
    outside = int(env.height - np.intersect1d(tcells, env["Cell"].to_numpy()).size)
    missing_from_sidecar = int(np.setdiff1d(tcells, env["Cell"].to_numpy()).size)
    if missing_from_sidecar:
        raise SystemExit(f"FATAL: {missing_from_sidecar} table cells have no env row")
    print(f"   coverage: {tcells.size:,} cells in {TABLE.name}; sidecar has {env.height:,} "
          f"({outside:,} outside the table's support — valid climatology, unseen by the forest)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    env.write_parquet(OUT)
    manifest = OUT.with_suffix(".manifest.txt")
    manifest.write_text(
        "\n".join(
            [
                f"artifact\t{OUT}",
                f"ncells\t{env.height}",
                f"env_cols\t{' '.join(env_cols)}",
                "basis\tper-Cell mean over cell_year_feats, NO year filter (the trainer's basis)",
                f"year_span\t{y0}-{y1}",
                "scenario_dependence\tNONE — a 2000-2019 climatology is used for every scenario,"
                " so these columns cannot carry a transient response (ADR 0040 §7)",
                f"source\t{CELL_YEAR_FEATS}",
                f"gated_against\t{TABLE}/Xc.f64 columns {ncond_base}..{ncond - 1}",
                f"gate\texact float64 equality on {probe.size} random rows (seed {SEED})",
                f"table_cells\t{tcells.size}",
                f"cells_outside_table_support\t{outside}",
                "consumer\tappend in THIS column order after the 4 boundary values;"
                " cond_cols[ncond_base:] of the pinned artifact must match env_cols above",
            ]
        )
        + "\n"
    )
    print(f"\n== wrote {OUT} ({OUT.stat().st_size / 2**20:.1f} MiB, {env.height:,} x {nenv})")
    print(f"== wrote {manifest}")
    print("== NOTE for line M: this provisions the artifact AS IT EXISTS. It does not make the tail")
    print("   transient, and it does not by itself justify re-pinning — see the ADR-0040 successor.")


if __name__ == "__main__":
    sys.exit(main())
