#!/usr/bin/env python3
"""RUNG 1, NULL CONTROL — score "copy LPJmL-FIT's own count from last year" on the rung-0 yardstick.

WHY THIS EXISTS (ADR 0112). Every feature the production count DRF is conditioned on is derived from the C
model's OWN roster and fluxes for that very (Cell, Patch, Year) — `build_slow_runtime_table.py` builds
`bm_inc_cell`/`growth_eff`/`water_stress`/`soilmoist` from the `ind` output and `n_prev`/`age_mean`/`agb`/
`lai`/`fpc`/`hmean`/`hmax` from the same roster — and `eval_slow_drf.jl` predicts each row from that row's
own X. So the published OOS score is a ONE-STEP TEACHER-FORCED score, not a free-running one, and one of its
15 features is **FIT's own answer for the previous year**.

A score that is handed last year's truth needs a null model that is handed nothing else:

    n_hat(Cell, Patch, Year) := n_prev = n_living(Cell, Patch, Year - 1)      <- column 10 of X.f64

This writes that predictor into a COUNT_DIR-shaped directory so `scripts/diagnose_truth_yardstick.py` scores
it through the SAME code path, on the SAME paired cell set, in the SAME process as the real arm:

    COUNT_DIR=<production>,<this dir> scripts/sbatch_python.sh S-yardnull scripts/diagnose_truth_yardstick.py

The four provenance files (`cells.i64`, the scenario tag, `y.f64`, `manifest.txt`) are SYMLINKED, never
copied, so the null cannot silently drift from the table it is the null for. Nothing is written into the
frozen source table's directory (CLAUDE.md §9: never overwrite a shared artifact in place).

Usage (SLURM; every knob must be EXPORTed — sbatch_python.sh forwards a fixed list, CLAUDE.md §9):
    export SRC=/p/tmp/jamirp/emulator_global/slow_count_pooled_w20_t8
    export OUT=/p/tmp/jamirp/emulator_global/rung1_count_null_persistence
    scripts/sbatch_python.sh S-nullpersist scripts/build_count_persistence_null.py
Env: SRC (pooled count table dir), OUT (destination), FEATURE (feature name to use as the prediction;
     default `n_prev`).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

SRC = Path(os.environ.get("SRC", "/p/tmp/jamirp/emulator_global/slow_count_pooled_w20_t8"))
OUT = Path(os.environ.get("OUT", "/p/tmp/jamirp/emulator_global/rung1_count_null_persistence"))
FEATURE = os.environ.get("FEATURE", "n_prev").strip()


def read_manifest(d: Path) -> dict[str, str]:
    man: dict[str, str] = {}
    for ln in (d / "manifest.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            man[k] = v
    return man


def r2(y: np.ndarray, p: np.ndarray) -> float:
    return 1.0 - float(((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def main() -> int:
    man = read_manifest(SRC)
    n, p = int(man["n"]), int(man["p"])
    colnames = man["colnames"].split()
    if len(colnames) != p:
        raise SystemExit(f"FATAL: manifest says p={p} but lists {len(colnames)} colnames")
    if FEATURE not in colnames:
        raise SystemExit(f"FATAL: {FEATURE!r} is not a column of {SRC.name}: {colnames}")
    j = colnames.index(FEATURE)
    print(f"== SRC={SRC}  n={n:,}  p={p}  FEATURE={FEATURE} (column {j})")

    X = np.memmap(SRC / "X.f64", dtype="<f8", mode="r", shape=(n, p))
    y = np.fromfile(SRC / "y.f64", dtype="<f8")
    if y.size != n:
        raise SystemExit(f"FATAL: y.f64 has {y.size} rows, manifest says {n}")
    pred = np.ascontiguousarray(X[:, j], dtype="<f8")

    # the reference number the null is there to undercut
    prod = SRC / "preds_oos.f64"
    print(f"== R2 of the null (n_hat = {FEATURE}) = {r2(y, pred):.6f}")
    if prod.exists():
        pr = np.fromfile(prod, dtype="<f8")
        if pr.size == n:
            rp, rn = r2(y, pr), r2(y, pred)
            print(f"== R2 of the production DRF's OOS predictions = {rp:.6f}")
            print(f"== the learned model removes {100 * (1 - (1 - rp) / (1 - rn)):.1f} % of the NULL's "
                  f"residual variance ({1 - rp:.5f} vs {1 - rn:.5f} unexplained)")

    OUT.mkdir(parents=True, exist_ok=True)
    pred.tofile(OUT / "preds_oos.f64")
    # provenance: SYMLINK the shared arrays so the null can never drift from its source table
    for fn in ["cells.i64", "y.f64", man.get("scenario_tag", "scenario.i64")]:
        dst = OUT / fn
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        dst.symlink_to((SRC / fn).resolve())
    lines = [f"{k}\t{v}" for k, v in man.items()]
    lines += [f"null_model\tn_hat = {FEATURE}", f"null_source\t{SRC}",
              "note\tNOT a model. The persistence null control for ADR 0112 — it is handed FIT's own "
              "previous-year count and nothing is learned."]
    (OUT / "manifest.txt").write_text("\n".join(lines) + "\n")
    print(f"== wrote {OUT}/preds_oos.f64 ({pred.size:,} rows) + symlinked provenance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
