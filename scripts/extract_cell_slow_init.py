#!/usr/bin/env python3
# =============================================================================
# extract_cell_slow_init.py — PER-CELL Component-S INITIAL STATE + BOUNDARY for
# the multi-cell coupled S+F+E driver (line M, milestone M2: wire the flux-driven
# Component S into the multi-cell driver).
#
# WHY: `run_coupled_cell` already accepts `slow=`, but the multi-cell driver runs
# `slow=nothing`, so the coupled evidence for S is offline-only. To construct one
# `FluxDrivenSlowEmulator` PER CELL, the driver needs, per cell:
#     n_init   — seeds the count-space AR state `n_prev`
#     age0     — seeds `s.age` so the runtime `age_mean` starts INSIDE the DRF's
#                trained mean-age band (ADR 0024 §3)
#     boundary — the baked slow-boundary tail, in the EXACT runtime order
#                `[eco_diag_gdd_5, tas_cold_month, soil_depth, co2]`
# Those live in line S's `cell_meta.parquet` sidecar, which is on /p/tmp (DVC,
# not git) and therefore unreachable from CI. This script folds them into the
# COMMITTED `references/M_cells.csv` so the driver and the CI gate read one small
# tracked table and never touch /p/tmp.
#
# THE FEATURE-ORDER CONTRACT (frozen S->M, ADR 0023): the 4 boundary columns must
# be emitted in the order `slow.jl::flux_feature_vector` appends them (and
# `live_flux_cond` conditions the recruit copula on) — verified against the
# artifact's own `*_meta.txt` `colnames` / `cond_cols`, not assumed. This script
# re-checks that order against the pinned artifact meta when META_TXT is given.
#
# ── WHAT `n_init` / `age0` ACTUALLY ARE (verified in build_slow_runtime_table.py
#    lines 320-332, 2026-07-28) — the reason they cannot be derived locally: they
#    are the per-cell MEDIAN OVER THE TRAINING YEARS of the count target
#    `n_living` and of `age_mean` respectively (with a MIN_YEARS=3 floor). They
#    are therefore statistics OF THE TRAINING WINDOW, not properties of the cell:
#    they CHANGE when S retrains on a different cell set/window, and they are NOT
#    recoverable from the committed single-year `M_individuals_<name>_2010.csv`
#    canopy. Measured across the 44,328 cells shared by `slow_runtime_historic`
#    and `slow_runtime_historic_t7`: `n_init` differs for 15,665 cells (max |Δ|
#    24 individuals) and `age0` for 22,542 (max |Δ| 85 years). So they MUST be
#    read from the cell_meta of the SAME artifact version the driver pins —
#    mixing versions is exactly ADR 0023's train/inference-shift trap.
#
# ── ...WHILE THE 4 BOUNDARY COLUMNS ARE VERSION-INVARIANT (same measurement):
#    `eco_diag_gdd_5`, `tas_cold_month`, `soil_depth` and `co2` are BYTE-IDENTICAL
#    for all 44,328 overlapping cells across those two versions — they are pure
#    per-cell climate/soil diagnostics. Hence `ALLOW_BOUNDARY_FROM=<other meta>`:
#    a boundary row may be sourced from a different version when the pinned one
#    lacks the cell, and the script PROVES the invariance on the overlap before
#    doing so, rather than assuming it.
#
# THE COMPLETENESS GATE (this is what found the M2 blocker): every requested cell
# MUST be present in the pinned cell_meta, or the script ABORTS. A missing cell
# means the pinned DRF was never trained on it, so there is no honest n_init/age0
# for it at that version and the driver must not silently invent one. Running
# this against `drf_forest_global_pooled_w20`'s own tables is how we learned that
# `semiarid_sahel` (18371) is in NEITHER `slow_count_historic_w20` NOR
# `slow_count_ssp370_w20`, while every `_t7` table covers all five cells.
#
# EMITS:
#   <OUT>/M_cells.csv            — the existing table + n_init, age0 and the 4
#                                  boundary columns (comments preserved, rows
#                                  merged BY NAME so column order is stable)
#   <OUT>/M_slow_init_meta.json  — provenance: which cell_meta, its mtime+sha256,
#                                  the artifact pinned, the gate verdict
#
# Usage (login node, ~2 s):
#   /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_cell_slow_init.py
# Env:
#   META      cell_meta.parquet of the PINNED artifact version (required)
#   META_TXT  the pinned artifact's *_meta.txt — re-checks the boundary order
#   ALLOW_BOUNDARY_FROM  a second cell_meta.parquet to source boundary rows for
#             cells absent from META (invariance is PROVEN on the overlap first);
#             n_init/age0 are NEVER taken from it
#   CELLS     "name:idx,..." (default: the 5 committed biome cells)
#   OUT       output dir (default: test/testitems/references)
#   GATE      "no" to downgrade the completeness abort to a warning (NOT for
#             committed fixtures — the emitted meta records the downgrade)
# =============================================================================
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

# Derive the repo root from THIS FILE, never a hard-coded absolute path: a
# hard-coded root makes a line worktree write its fixtures into the INTEGRATOR
# worktree (CLAUDE.md §9 item 6).
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The runtime boundary order — `slow.jl::flux_feature_vector`'s tail, which is
# also `live_flux_cond`'s conditioning tail. Changing this is a both-sides
# integration point with line S, never a local edit.
BOUNDARY_COLS = ["eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2"]
SEED_COLS = ["n_init", "age0"]

DEFAULT_CELLS = {
    "boreal_siberia": 52059,
    "temperate_hainich": 42490,
    "mediterranean_iberia": 33335,
    "semiarid_sahel": 18371,
    "tropical_amazon": 12045,
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_cells(spec):
    if not spec:
        return dict(DEFAULT_CELLS)
    out = {}
    for part in spec.split(","):
        name, idx = part.split(":")
        out[name.strip()] = int(idx)
    return out


def check_boundary_order(meta_txt):
    """Re-verify the artifact's trained tail against BOUNDARY_COLS (never assume)."""
    colnames = cond_cols = None
    with open(meta_txt) as fh:
        for ln in fh:
            if ln.startswith("#") or "\t" not in ln:
                continue
            key, _, val = ln.partition("\t")
            if key.strip() == "colnames":
                colnames = val.split()
            elif key.strip() == "cond_cols":
                cond_cols = val.split()
    if colnames is not None:
        tail = colnames[-len(BOUNDARY_COLS):]
        if tail != BOUNDARY_COLS:
            sys.exit(
                f"FATAL: artifact boundary tail {tail} != runtime order {BOUNDARY_COLS}\n"
                f"  ({meta_txt})\n"
                "  This is an INTEGRATION POINT with line S (ADR 0023), not a local fix."
            )
        print(f"  [gate] DRF colnames tail == runtime order {BOUNDARY_COLS}  OK")
    if cond_cols is not None:
        tail = cond_cols[-len(BOUNDARY_COLS):]
        if tail != BOUNDARY_COLS:
            sys.exit(f"FATAL: copula cond_cols tail {tail} != {BOUNDARY_COLS} ({meta_txt})")
        print(f"  [gate] copula cond_cols tail == runtime order  OK")
    return colnames, cond_cols


def prove_boundary_invariance(pinned, other):
    """The boundary columns must be IDENTICAL on the overlap before borrowing a row."""
    common = pinned.index.intersection(other.index)
    if len(common) == 0:
        sys.exit("FATAL: ALLOW_BOUNDARY_FROM shares no cells with META — cannot prove invariance")
    worst = {}
    for col in BOUNDARY_COLS:
        x = pinned.loc[common, col].astype("float64").to_numpy()
        y = other.loc[common, col].astype("float64").to_numpy()
        worst[col] = float(abs(x - y).max())
    bad = {c: v for c, v in worst.items() if v != 0.0}
    if bad:
        sys.exit(
            "FATAL: boundary columns are NOT identical across the two cell_meta files "
            f"on their {len(common)} shared cells: {bad}\n"
            "  They are version-COUPLED here, so a borrowed boundary row would be a "
            "train/inference shift. Pin one artifact version that covers every cell."
        )
    print(f"  [gate] boundary invariance PROVEN on {len(common)} shared cells (max|Δ| = 0 for all 4)")
    return len(common)


def main():
    meta_path = os.environ.get("META", "")
    if not meta_path:
        sys.exit(
            "FATAL: META is required — the cell_meta.parquet of the PINNED artifact version.\n"
            "  e.g. META=/p/tmp/jamirp/emulator_global/slow_runtime_historic_t7/cell_meta.parquet"
        )
    out_dir = os.environ.get("OUT", os.path.join(REPO, "test", "testitems", "references"))
    cells = parse_cells(os.environ.get("CELLS", ""))
    gate = os.environ.get("GATE", "yes").lower() not in ("no", "0", "false")
    meta_txt = os.environ.get("META_TXT", "")
    borrow_path = os.environ.get("ALLOW_BOUNDARY_FROM", "")

    print(f"== extract_cell_slow_init: {len(cells)} cells")
    print(f"   META = {meta_path}")
    order_checked = None
    if meta_txt:
        order_checked = check_boundary_order(meta_txt)
    else:
        print("   [warn] META_TXT not given — the artifact's trained boundary order was NOT re-checked")

    need = SEED_COLS + BOUNDARY_COLS
    df = pd.read_parquet(meta_path)
    missing_cols = [c for c in ["Cell"] + need if c not in df.columns]
    if missing_cols:
        sys.exit(f"FATAL: {meta_path} lacks columns {missing_cols}")
    pinned = df.set_index("Cell")
    print(f"   cell_meta covers {len(pinned)} cells")

    absent = {n: c for n, c in cells.items() if c not in pinned.index}
    borrow = None
    if absent and borrow_path:
        print(f"   ALLOW_BOUNDARY_FROM = {borrow_path}")
        borrow = pd.read_parquet(borrow_path).set_index("Cell")
        prove_boundary_invariance(pinned, borrow)
        still = {n: c for n, c in absent.items() if c not in borrow.index}
        # boundary can be borrowed; n_init/age0 can NEVER be
        msg = (
            f"cells absent from the PINNED cell_meta: {absent}\n"
            "  Their boundary rows can be borrowed (invariance proven above), but n_init/age0\n"
            "  are medians OVER THE TRAINING WINDOW and are version-coupled, so there is no\n"
            "  honest value for a cell the pinned artifact never saw."
        )
        if still:
            msg += f"\n  Worse, still absent from the borrow source too: {still}"
        if gate:
            sys.exit(f"FATAL (GATE): {msg}\n  Pin an artifact version that covers every cell.")
        print(f"   [WARN] {msg}")
    elif absent:
        msg = (
            f"cells absent from the pinned cell_meta: {absent}\n"
            "  The pinned DRF was never trained on them, so there is no honest n_init/age0.\n"
            "  Pin an artifact version whose cell_meta covers every requested cell (every\n"
            "  `_t7` table does; `*_w20` does not cover semiarid_sahel)."
        )
        if gate:
            sys.exit(f"FATAL (GATE): {msg}")
        print(f"   [WARN] {msg}")

    rows = {}
    for name, cell in cells.items():
        if cell not in pinned.index:
            continue
        r = pinned.loc[cell]
        rows[name] = {c: float(r[c]) for c in need}
        if r.get("n_rows") is not None:
            rows[name]["_n_rows"] = int(r["n_rows"])
    if borrow is not None:
        for name, cell in absent.items():
            if cell in borrow.index:
                rows.setdefault(name, {})
                for c in BOUNDARY_COLS:
                    rows[name][c] = float(borrow.loc[cell, c])

    # ── merge into M_cells.csv BY NAME, preserving its comment header ──
    csv_path = os.path.join(out_dir, "M_cells.csv")
    comments, header, body = [], None, []
    with open(csv_path) as fh:
        for ln in fh:
            s = ln.rstrip("\n")
            if s.startswith("#"):
                comments.append(s)
            elif header is None:
                header = s.split(",")
            elif s.strip():
                body.append(s.split(","))
    name_i = header.index("name")
    add = [c for c in need if c not in header]
    for c in add:
        header.append(c)
    for row in body:
        nm = row[name_i]
        vals = rows.get(nm, {})
        for c in add:
            v = vals.get(c)
            # `repr` (= %.17g) so the Float64 the driver parses is EXACTLY the value the artifact
            # was trained on. Not cosmetic: these feed DRF split thresholds, and the older %.6f
            # truncated Hainich's eco_diag_gdd_5 1863.695068359375 -> 1863.695068. Verified against
            # the committed drf_forest_hainich_meta.txt, whose baked boundary is bit-identical.
            row.append("" if v is None else repr(v))

    note = (
        "# n_init/age0 = per-cell MEDIAN over the training years of n_living / age_mean "
        "(build_slow_runtime_table.py);"
    )
    note2 = (
        "#   version-COUPLED (retraining moves them) => they track the PINNED artifact. "
        "boundary = the runtime tail order."
    )
    note3 = f"# scripts/extract_cell_slow_init.py  META={os.path.basename(os.path.dirname(meta_path))}"
    for extra in (note, note2, note3):
        if extra not in comments:
            comments.append(extra)

    with open(csv_path, "w") as fh:
        for c in comments:
            fh.write(c + "\n")
        fh.write(",".join(header) + "\n")
        for row in body:
            fh.write(",".join(row) + "\n")
    print(f"   wrote {csv_path}  (+{len(add)} columns for {len(rows)}/{len(cells)} cells)")

    meta_out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/extract_cell_slow_init.py",
        "cell_meta": meta_path,
        "cell_meta_sha256": sha256(meta_path),
        "cell_meta_mtime": datetime.fromtimestamp(
            os.path.getmtime(meta_path), timezone.utc
        ).isoformat(),
        "cell_meta_ncells": int(len(pinned)),
        "artifact_meta_txt": meta_txt or None,
        "boundary_order": BOUNDARY_COLS,
        "boundary_order_rechecked": order_checked is not None,
        "seed_cols": SEED_COLS,
        "cells": {n: int(c) for n, c in cells.items()},
        "cells_absent_from_pinned": {n: int(c) for n, c in absent.items()},
        "boundary_borrowed_from": borrow_path or None,
        "completeness_gate": "enforced" if gate else "DOWNGRADED (GATE=no)",
    }
    mpath = os.path.join(out_dir, "M_slow_init_meta.json")
    with open(mpath, "w") as fh:
        json.dump(meta_out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"   wrote {mpath}")


if __name__ == "__main__":
    main()
