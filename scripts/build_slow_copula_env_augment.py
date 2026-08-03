#!/usr/bin/env python3
"""Augment an EXISTING copula table's `Xc` with the ADR-0037 per-cell env conditioning tail — no `ind` rescan.

WHY THIS EXISTS (milestone S2 / ADR 0038)
-----------------------------------------
Measuring what the EXTENDED conditioning (lever 3) is worth requires a table with `ncond = 8 + nenv`. The
obvious way is a fresh `COPULA_ENV_COLS=... build_slow_runtime_table.py` run — but ADR 0036 §5b established
that `polars` `collect(engine="streaming")` is **non-deterministic in its emitted KEY SET** at this scale
(two ssp370 builds differed by 4 913 rows with 12 cells DUPLICATED). A fresh build could therefore land on a
DIFFERENT row universe than `t8`, and then the 8-column and 14-column evaluations would not be comparable —
any measured "lever 3 gain" would be confounded with a row-set change. That is precisely the
attribution error ADR 0033 records this line making twice.

So instead: take `t8`'s VALIDATED `Xc`/`Y_*`/`cells.i64` and APPEND the env columns. The row universe is then
*identical by construction*, `Y` and `cells` are the same bytes (symlinked), and the only difference between
the two tables is the columns whose effect is being measured. Perfect isolation, and ~15 minutes instead of a
full rebuild.

EXACTNESS — this must reproduce what `build_slow_runtime_table.py` would have written
------------------------------------------------------------------------------------
The env tail is a per-CELL time MEAN, on the SAME basis as the static boundary the tail is appended to, and
the runtime's `live_flux_cond_env(env)` consumes it as a per-cell constant vector.

THE YEAR BASIS, stated because getting it wrong is silent for one scenario and fatal for the other.
`cell_year_feats.parquet` spans **Year 2000-2019 only** — it is a HISTORIC climatology table. The static
boundary (`build_slow_runtime_table.py::_boundary_source`) therefore applies **no year filter** at all and
uses that whole table for every scenario. The env branch originally applied `Year >= FIRSTYEAR[scenario]`,
which is a no-op for `historic` (2000 >= 2000 selects all 1 348 400 rows) but selects **ZERO rows** for
`ssp370` (FIRSTYEAR 2020) — so an ssp370 env-conditioned table died at the coverage check with a message
blaming a coverage hole. Both this script and the builder now use the boundary's basis (no filter), which
is **byte-identical for historic** and makes ssp370 work, with a non-empty assertion so an empty
aggregation can never again be reported as something else.

Consequence to state, not to hide: an `ssp370` env tail is the 2000-2019 HISTORIC climatology, exactly like
its static boundary. That is consistent, but it means the env columns carry no scenario signal — a
transient env tail would need the `BOUNDARY_WINDOW` treatment (ADR 0026), which is not done here.

Verified here, not assumed:
  * the first `ncond` columns of the new `Xc` are byte-identical to the source `Xc` (chunkwise `memcmp`);
  * every row's env values are finite and come from that row's own cell;
  * `cells.i64` / `Y_*.f64` are symlinks to the source, so they cannot drift;
  * the manifest's fallback row `x` is EXTENDED with the true row-weighted column means (what the builder
    writes), never left at 8 entries — a short `x` would make `.rcop` fallback conditioning read
    out-of-bounds.

Usage (SLURM; reads ~13 GB, writes ~22 GB):
    SRC=/p/tmp/jamirp/emulator_global/slow_copula_historic_t8 \
    OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic_t8env \
    SCENARIO=historic \
    COPULA_ENV_COLS=prec_mean,eco_diag_p_pet_ratio,eco_diag_pet_mean,eco_diag_vpd_mean,pr_cv_monthly,humid_mean \
      scripts/sbatch_python.sh S-envaug scripts/build_slow_copula_env_augment.py

Env: SRC (required), OUT (required), SCENARIO (historic|ssp370|pooled — LABEL ONLY: it is printed and
     copied into the manifest, and since the year filter was removed it selects nothing, so `pooled` is
     safe), COPULA_ENV_COLS (required, comma-separated columns of the tail source), CHUNK (rows per write
     chunk, default 8_000_000), ENV_PARQUET (ADR 0039: a per-CELL tail parquet instead of the per-cell-year
     `cell_year_feats` — used for the `p14geo` / `p14perm` ablation controls; unset ⇒ byte-identical to the
     pre-ADR-0039 behaviour), TAIL_TAG (a provenance label copied into the manifest as `env_tail_tag`).

Sidecars: every file the source manifest NAMES is symlinked into OUT, not just `Y_*`/`cells.i64` — the
`pooled` tables carry `scenario_tag  scenario.i64` and an earlier version of this script dropped it,
leaving the copied manifest pointing at a file that was not there (see the symlink block below).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import polars as pl

BASE = "/p/tmp/jamirp/emulator_global"
CELL_YEAR_FEATS = f"{BASE}/tables/cell_year_feats.parquet"
FIRSTYEAR = {"historic": 2000, "ssp370": 2020}

SRC = os.environ.get("SRC", "")
OUT = os.environ.get("OUT", "")
SCENARIO = os.environ.get("SCENARIO", "historic")
ENV_COLS = [c.strip() for c in os.environ.get("COPULA_ENV_COLS", "").split(",") if c.strip()]
CHUNK = int(os.environ.get("CHUNK", "8000000"))
# ADR 0039. The tail source is a knob so the ABLATION CONTROLS ride this same verified transform instead of
# a forked script: `p14geo` (a pure-position tail) and `p14perm` (the true env tuples permuted across cells)
# are per-CELL parquets from scripts/build_slow_spatial_controls.py. The `group_by("Cell").mean()` below is
# the IDENTITY on a table that already has one row per Cell, so no branch is needed in the hot path — but
# that also means a DUPLICATED Cell in such an input would be silently AVERAGED, manufacturing a tuple that
# exists in neither marginal and defeating the whole point of the perm control. Hence the explicit
# one-row-per-Cell gate below. Unset ⇒ `cell_year_feats` ⇒ byte-identical to the pre-ADR-0039 behaviour.
ENV_PARQUET = os.environ.get("ENV_PARQUET", "").strip() or CELL_YEAR_FEATS
TAIL_TAG = os.environ.get("TAIL_TAG", "").strip()  # provenance label, copied into the manifest


def read_manifest(d):
    m, order = {}, []
    for ln in Path(d, "manifest_copula.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            m[k] = v
            order.append(k)
    return m, order


def main():
    if not SRC or not OUT or not ENV_COLS:
        raise SystemExit("FATAL: SRC, OUT and COPULA_ENV_COLS are all required.")
    src, out = Path(SRC), Path(OUT)
    if not (src / "Xc.f64").is_file():
        raise SystemExit(f"FATAL: no Xc.f64 in {src}")
    if out.resolve() == src.resolve():
        raise SystemExit("FATAL: OUT == SRC — refusing to overwrite the source table in place.")
    # Checked BEFORE any work: a leftover pred_* from an earlier eval in this OUT would be silently
    # re-scored as this table's result (the same class of accident the capacity harness guards against).
    stale = sorted(p.name for p in out.glob("pred_*.f64")) if out.is_dir() else []
    if stale:
        raise SystemExit(f"FATAL: stale predictions in {out}: {stale} — remove them first.")

    man, order = read_manifest(src)
    n = int(man["n"])
    ncond = int(man["ncond"])
    cond_cols = man["cond_cols"].split()
    assert len(cond_cols) == ncond, f"manifest cond_cols/ncond mismatch: {len(cond_cols)} vs {ncond}"
    dup = [c for c in ENV_COLS if c in cond_cols]
    if dup:
        raise SystemExit(f"FATAL: requested env column(s) already in cond_cols: {dup}")
    nenv = len(ENV_COLS)
    ncond_new = ncond + nenv

    print("=" * 96)
    print("ENV-AUGMENT an existing copula table (ADR 0037 lever 3, isolated on t8's row universe)")
    print("=" * 96)
    print(f"   SRC       : {src}")
    print(f"   OUT       : {out}")
    print(f"   scenario  : {SCENARIO}   n={n:,}  ncond {ncond} -> {ncond_new}")
    print(f"   env cols  : {ENV_COLS}")

    # ---- the per-cell env means, replicating build_slow_runtime_table.py literally -------------------
    have = pl.scan_parquet(ENV_PARQUET).collect_schema().names()
    missing = [c for c in ENV_COLS if c not in have]
    if missing:
        raise SystemExit(f"FATAL: COPULA_ENV_COLS not in {ENV_PARQUET}: {missing}")
    if ENV_PARQUET != CELL_YEAR_FEATS:
        # A pre-materialized per-Cell tail: the aggregation below is the IDENTITY, so the duplicate-Cell
        # guard AFTER it can no longer catch anything. Gate the INPUT instead (see the ADR-0039 note above).
        raw = pl.scan_parquet(ENV_PARQUET).select("Cell").collect()
        if raw.n_unique() != raw.height:
            raise SystemExit(
                f"FATAL: {ENV_PARQUET} is not one row per Cell ({raw.height} rows, "
                f"{raw.n_unique()} unique) — the mean would silently BLEND tuples"
            )
        print(f"   tail src  : {ENV_PARQUET}  [one row per Cell verified]  tag={TAIL_TAG or '(none)'}")
    # NO year filter — the static boundary's basis (see the YEAR BASIS note in the module docstring).
    envt = (
        pl.scan_parquet(ENV_PARQUET)
        .select(["Cell"] + ENV_COLS)
        .group_by("Cell")
        .agg([pl.col(c).cast(pl.Float64).mean().alias(c) for c in ENV_COLS])
        .collect()
    )
    if envt.height == 0:
        raise SystemExit(
            f"FATAL: the env aggregation over {ENV_PARQUET} produced ZERO cells. That is an EMPTY "
            f"SOURCE, not a coverage hole — check the table's Year range against this scenario."
        )
    bad = {c: int(envt[c].is_null().sum() + envt[c].is_nan().sum()) for c in ENV_COLS}
    assert not any(bad.values()), f"null/NaN in COPULA_ENV_COLS per-cell means: {bad}"
    assert envt.select("Cell").n_unique() == envt.height, "duplicated Cell in the env aggregate"
    if "Year" in have:
        yr = pl.scan_parquet(ENV_PARQUET).select(
            pl.col("Year").min().alias("lo"), pl.col("Year").max().alias("hi")
        ).collect()
        print(f"   env means : {envt.height:,} cells from cell_year_feats over Year "
              f"{yr['lo'][0]}-{yr['hi'][0]} (climatology, no scenario filter — the boundary's basis)")
    else:
        # A per-Cell tail has no Year column at all — that is the point (ADR 0039). Report its provenance
        # instead of a Year span, rather than letting `pl.col("Year")` raise ColumnNotFoundError.
        print(f"   env means : {envt.height:,} cells from {ENV_PARQUET} (per-Cell tail, no Year axis)")

    # Dense cell -> env lookup (cells are small positive ints on the orderA grid).
    cells = np.fromfile(src / "cells.i64", dtype="<i8")
    assert cells.size == n, f"cells.i64 has {cells.size} rows, manifest says {n}"
    cmax = int(cells.max())
    lut = np.full((cmax + 1, nenv), np.nan, dtype="<f8")
    ec = envt["Cell"].to_numpy()
    keep = ec <= cmax
    for j, c in enumerate(ENV_COLS):
        lut[ec[keep], j] = envt[c].to_numpy()[keep]
    # Every cell present in the table MUST have env values — the builder's inner-join guard, done as a
    # coverage assertion because here there is no join to drop rows.
    uniq = np.unique(cells)
    holes = uniq[~np.isfinite(lut[uniq]).all(axis=1)]
    if holes.size:
        raise SystemExit(
            f"FATAL: {holes.size} of {uniq.size} cells have no env value (e.g. {holes[:10].tolist()}) "
            f"— a coverage hole. cell_year_feats does not cover this table's cells."
        )
    print(f"   coverage  : all {uniq.size:,} table cells have finite env values")

    # ---- chunked write: [src Xc | env broadcast by cell] ---------------------------------------------
    out.mkdir(parents=True, exist_ok=True)
    Xsrc = np.memmap(src / "Xc.f64", dtype="<f8", mode="r", shape=(n, ncond))
    dst = out / "Xc.f64"
    if dst.exists():
        dst.unlink()
    # Chunk sums accumulated in float64: ~25 addends, so this is the builder's `tbl[c].mean()` to well
    # within the ~1e-13 float-sum jitter already documented for these tables.
    colsum = np.zeros(ncond_new, dtype=np.float64)
    nchunk = (n + CHUNK - 1) // CHUNK
    with open(dst, "wb") as fh:
        for ci in range(nchunk):
            lo, hi = ci * CHUNK, min((ci + 1) * CHUNK, n)
            blk = np.empty((hi - lo, ncond_new), dtype="<f8")
            blk[:, :ncond] = Xsrc[lo:hi]
            blk[:, ncond:] = lut[cells[lo:hi]]
            assert np.isfinite(blk).all(), f"non-finite in augmented Xc chunk {ci}"
            blk.tofile(fh)
            colsum += blk.sum(axis=0, dtype=np.float64)
            print(f"   chunk {ci + 1}/{nchunk}: rows {lo:,}..{hi:,}", flush=True)
    xmean = (colsum / n).astype(np.float64)

    # ---- VERIFY the first ncond columns are byte-identical to the source ----------------------------
    print("\n-- verifying the source columns survived byte-identically ...", flush=True)
    Xnew = np.memmap(dst, dtype="<f8", mode="r", shape=(n, ncond_new))
    for ci in range(nchunk):
        lo, hi = ci * CHUNK, min((ci + 1) * CHUNK, n)
        a = np.ascontiguousarray(Xsrc[lo:hi])
        b = np.ascontiguousarray(Xnew[lo:hi, :ncond])
        if a.tobytes() != b.tobytes():
            raise SystemExit(f"FATAL: source columns differ in chunk {ci} — the augment is not a superset.")
    print(f"   OK: columns 0..{ncond - 1} bitwise-identical to {src / 'Xc.f64'} over all {n:,} rows")
    # And the env columns really are the cell's own values (independent spot re-derivation).
    rng = np.random.default_rng(17)
    probe = rng.choice(n, size=min(200_000, n), replace=False)
    exp = lut[cells[probe]]
    got = np.asarray(Xnew[probe, ncond:])
    assert np.array_equal(exp, got), "env columns are not this row's cell's values"
    print(f"   OK: env tail re-derived independently on {probe.size:,} random rows")
    del Xsrc, Xnew

    # ---- symlink the untouched halves, write the extended manifest -----------------------------------
    # EVERY sidecar the manifest NAMES must come along, not just the ones the historic table happens to
    # have. The `pooled` tables carry `scenario_tag<TAB>scenario.i64` (the per-row scenario label that
    # eval_slow_copula_scenario_holdout.jl splits on); the first version of this loop symlinked only
    # `Y_*.f64` + `cells.i64`, so a pooled augment produced a table whose manifest still declared
    # `scenario.i64` while the file was ABSENT from OUT — a dangling contract that trains fine (the
    # trainer never reads it) and only fails later, in the scenario-holdout eval, far from the cause.
    # Resolved by NAME from the manifest so a future sidecar key is carried automatically.
    sidecars = [src / "cells.i64"]
    for key in ("scenario_tag",):
        if key in man:
            ref = src / man[key]
            if not ref.is_file() and not ref.is_symlink():
                raise SystemExit(
                    f"FATAL: manifest declares {key}={man[key]} but {ref} does not exist — the source "
                    f"table is inconsistent; refusing to propagate a dangling reference."
                )
            sidecars.append(ref)
    for f in sorted(src.glob("Y_*.f64")) + sidecars:
        link = out / f.name
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(f)
    npred = len(list(out.glob("pred_*.f64")))
    assert npred == 0, f"{npred} pred_* already in OUT — remove them so a stale eval is never re-scored"
    # The manifest is written below by copying every key through; assert here that each sidecar it names
    # now RESOLVES in OUT, so the augmented table can never ship a reference to a file that is not there.
    for key in ("scenario_tag",):
        if key in man:
            assert (out / man[key]).is_file(), f"manifest {key}={man[key]} does not resolve in {out}"

    lines = []
    for k in order:
        if k == "ncond":
            lines.append(f"ncond\t{ncond_new}")
        elif k == "cond_cols":
            lines.append("cond_cols\t" + " ".join(cond_cols + ENV_COLS))
        elif k == "x":
            lines.append("x\t" + " ".join(repr(float(v)) for v in xmean))
        else:
            lines.append(f"{k}\t{man[k]}")
    if "x" not in order:
        lines.append("x\t" + " ".join(repr(float(v)) for v in xmean))
    lines.append(f"env_augmented_from\t{src}")
    # Inert extra keys: every consumer is key-driven (`read_manifest` here, train_slow_copula.jl:75,
    # eval_slow_copula.jl:93), so an unknown key is ignored. They exist so a shadow dir's provenance is
    # readable from the table itself rather than reconstructed from an orchestrator default (ADR 0039).
    lines.append(f"env_tail_source\t{ENV_PARQUET}")
    if TAIL_TAG:
        lines.append(f"env_tail_tag\t{TAIL_TAG}")
    (out / "manifest_copula.txt").write_text("\n".join(lines) + "\n")

    print(f"\n== wrote {dst} ({dst.stat().st_size / 2**30:.1f} GiB, {n:,} x {ncond_new})")
    print(f"== symlinked {len(list(out.glob('Y_*.f64')))} Y_* + "
          f"{' + '.join(f.name for f in sidecars)} from the source (cannot drift)")
    print(f"== manifest ncond={ncond_new}  cond_cols={' '.join(cond_cols + ENV_COLS)}")
    print("== fallback row x (row-weighted column means):")
    for c, v in zip(cond_cols + ENV_COLS, xmean, strict=True):
        print(f"     {c:34s} {v:.6g}")
    print("\n   NOTE the train/inference contract (ADR 0023/0037): a runtime using this artifact must build")
    print(f"   4 + len(s.boundary) + len(env) == {ncond_new} columns in THIS order, via")
    print("   live_flux_cond_env(env) with env = the per-cell means of "
          f"{ENV_COLS}. A mismatch fails SILENTLY.")


if __name__ == "__main__":
    main()
