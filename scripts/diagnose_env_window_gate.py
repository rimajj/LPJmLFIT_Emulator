#!/usr/bin/env python3
"""GATE the ADR-0108 transient env tail: default byte-identical, transient actually year-varying.

Runs `build_slow_runtime_table.py` three times over the SAME small cell set and checks the three things
that can each silently invalidate the moisture conditioning:

  A. GUARDRAIL 4 — `ENV_WINDOW` unset must reproduce the PRE-0108 builder's `Xc.f64` BYTE-FOR-BYTE.
     Checked against the actual committed-parent version of the script (`git show <BASE_REF>:...`), not
     against a re-run of the new code, which would be circular.
  B. The transient tail must be YEAR-VARYING and must equal the source table's own value for that
     (Cell, Year) — re-derived here independently from the parquet, not from the builder's own join.
  C. The first 8 conditioning columns (the flux head + boundary tail) must be UNCHANGED between the
     static-tail and transient-tail runs: the ONLY thing `ENV_WINDOW` may move is the last 6 columns.
     Without this, a "the moisture tail helps" result could be a row-universe or boundary change instead
     (the ADR-0033 attribution error this line has made twice).

Also checks that `years.i64` is emitted, is aligned to `Xc`'s rows, and that the manifest carries
`env_basis` — the only field that distinguishes a static-tail from a transient-tail table (same `ncond`,
same `cond_cols`, and the runtime width probe passes for both, so nothing else can).

Usage (SLURM):
    scripts/sbatch_python.sh S-envgate scripts/diagnose_env_window_gate.py
Env: CELLS (default the 5 biome cells), SCENARIO (default historic), WINDOW (20), WORK (scratch dir),
     BASE_REF (git ref holding the pre-0108 builder, default HEAD — set to the parent commit while the
     change is uncommitted), ENV_COLS (the 6 moisture descriptors).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import polars as pl

REPO = Path(__file__).resolve().parent.parent
BASE = "/p/tmp/jamirp/emulator_global"
PY = sys.executable
CELLS = os.environ.get("CELLS", "52059,42490,33335,18371,12045")
SCENARIO = os.environ.get("SCENARIO", "historic")
WINDOW = os.environ.get("WINDOW", "20")
WORK = Path(os.environ.get("WORK", f"{BASE}/S_envgate_{SCENARIO}"))
BASE_REF = os.environ.get("BASE_REF", "HEAD")
ENV_COLS = os.environ.get(
    "ENV_COLS",
    "prec_mean,eco_diag_p_pet_ratio,eco_diag_pet_mean,eco_diag_vpd_mean,pr_cv_monthly,humid_mean",
).split(",")
NHEAD = 8  # the 4 flux drivers + the 4-column boundary tail — everything before the env tail


def run_builder(script: Path, out: Path, extra: dict) -> None:
    env = dict(os.environ)
    env.update({
        "MODE": "copula", "SCENARIO": SCENARIO, "CELLS": CELLS, "OUT": str(out),
        "BOUNDARY_WINDOW": WINDOW, "COPULA_ENV_COLS": ",".join(ENV_COLS),
    })
    env.pop("ENV_WINDOW", None)
    env.pop("STRUCT_AXES", None)
    # The builder resolves the `lpjmlfit_emulator` import from `Path(__file__).parents[1]/python/src`, so the
    # reference COPY (which lives in a scratch dir, not in scripts/) cannot find it. Hand it the same path on
    # PYTHONPATH rather than rewriting the copy — the copy must stay byte-identical to the committed version.
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO / "python" / "src")] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env.update(extra)
    out.mkdir(parents=True, exist_ok=True)
    print(f"\n>>> {script.name}  OUT={out.name}  ENV_WINDOW={env.get('ENV_WINDOW', '(unset)')}", flush=True)
    r = subprocess.run([PY, str(script)], env=env, cwd=str(REPO), capture_output=True, text=True)
    tail = "\n".join((r.stdout or "").splitlines()[-14:])
    print(tail, flush=True)
    if r.returncode != 0:
        print(r.stderr[-4000:], flush=True)
        raise SystemExit(f"FATAL: builder failed (rc={r.returncode}) for OUT={out}")


def read_manifest(d: Path) -> dict:
    m = {}
    for ln in (d / "manifest_copula.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            m[k] = v
    return m


def load(d: Path):
    man = read_manifest(d)
    n, ncond = int(man["n"]), int(man["ncond"])
    X = np.fromfile(d / "Xc.f64", dtype="<f8").reshape(n, ncond)
    cells = np.fromfile(d / "cells.i64", dtype="<i8")
    yrs = np.fromfile(d / "years.i64", dtype="<i8") if (d / "years.i64").exists() else None
    return man, X, cells, yrs


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    old_script = WORK / "build_slow_runtime_table_PRE0108.py"
    src = subprocess.run(["git", "show", f"{BASE_REF}:scripts/build_slow_runtime_table.py"],
                         cwd=str(REPO), capture_output=True, text=True)
    if src.returncode != 0:
        raise SystemExit(f"FATAL: git show {BASE_REF}:scripts/build_slow_runtime_table.py failed: {src.stderr}")
    if "ENV_WINDOW" in src.stdout:
        raise SystemExit(
            f"FATAL: {BASE_REF}'s builder ALREADY knows ENV_WINDOW, so it is not a pre-0108 reference and "
            f"check A would be circular. Point BASE_REF at the commit before this change."
        )
    old_script.write_text(src.stdout)
    print("=" * 96)
    print(f"ADR-0108 env-window gate — scenario={SCENARIO} cells={CELLS} W={WINDOW}")
    print(f"   reference builder: {BASE_REF}:scripts/build_slow_runtime_table.py")
    print("=" * 96)

    d_old, d_stat, d_tran = WORK / "pre0108", WORK / "static", WORK / "transient"
    run_builder(old_script, d_old, {})
    run_builder(REPO / "scripts" / "build_slow_runtime_table.py", d_stat, {})
    run_builder(REPO / "scripts" / "build_slow_runtime_table.py", d_tran, {"ENV_WINDOW": WINDOW})

    m_old, X_old, _, _ = load(d_old)
    m_st, X_st, c_st, y_st = load(d_stat)
    m_tr, X_tr, c_tr, y_tr = load(d_tran)
    fails: list[str] = []

    # ---- A. guardrail 4: the default path is byte-identical to the pre-0108 builder ------------------
    print("\n-- A. default (ENV_WINDOW unset) vs the pre-0108 builder")
    same_bytes = (d_old / "Xc.f64").read_bytes() == (d_stat / "Xc.f64").read_bytes()
    print(f"   Xc.f64 byte-identical : {same_bytes}   ({X_old.shape} vs {X_st.shape})")
    if not same_bytes:
        d = np.abs(X_old - X_st) if X_old.shape == X_st.shape else None
        fails.append(f"A: default Xc differs from pre-0108 (max|diff| "
                     f"{'shape mismatch' if d is None else d.max()})")
    for k in ("n", "ncond", "cond_cols", "axes", "x"):
        if m_old.get(k) != m_st.get(k):
            fails.append(f"A: manifest key {k!r} changed on the default path: {m_old.get(k)!r} -> {m_st.get(k)!r}")
    print(f"   manifest n/ncond/cond_cols/axes/x unchanged : "
          f"{all(m_old.get(k) == m_st.get(k) for k in ('n', 'ncond', 'cond_cols', 'axes', 'x'))}")
    print(f"   env_basis recorded    : static={m_st.get('env_basis')!r} transient={m_tr.get('env_basis')!r}")
    if m_st.get("env_basis") != "static_cell_mean" or m_tr.get("env_basis") != f"transient_w{int(WINDOW)}":
        fails.append(f"A: env_basis not recorded as expected "
                     f"({m_st.get('env_basis')!r} / {m_tr.get('env_basis')!r})")

    # ---- years.i64 present + aligned -----------------------------------------------------------------
    print("\n-- years.i64 sidecar")
    for tag, d, yv, X in (("static", d_stat, y_st, X_st), ("transient", d_tran, y_tr, X_tr)):
        if yv is None:
            fails.append(f"years.i64 missing from the {tag} table")
            continue
        ok = yv.shape[0] == X.shape[0]
        print(f"   {tag:9s}: {yv.shape[0]} rows (X has {X.shape[0]}), Year {yv.min()}-{yv.max()}, aligned={ok}")
        if not ok:
            fails.append(f"years.i64 length {yv.shape[0]} != Xc rows {X.shape[0]} ({tag})")
        if read_manifest(d).get("years_tag") != "years.i64":
            fails.append(f"manifest years_tag missing/wrong in the {tag} table")

    # ---- C. only the env tail moved ------------------------------------------------------------------
    print("\n-- C. static vs transient: the head+boundary columns must be identical")
    if X_st.shape != X_tr.shape or not np.array_equal(c_st, c_tr) or not np.array_equal(y_st, y_tr):
        fails.append("C: static and transient runs have different row universes — cannot isolate the tail")
        print("   ROW UNIVERSE DIFFERS — skipping the column comparison")
    else:
        head_same = np.array_equal(X_st[:, :NHEAD], X_tr[:, :NHEAD])
        print(f"   columns 0..{NHEAD - 1} identical : {head_same}")
        if not head_same:
            j = int(np.argmax(np.abs(X_st[:, :NHEAD] - X_tr[:, :NHEAD]).max(axis=0)))
            fails.append(f"C: head/boundary column {j} moved under ENV_WINDOW — the tail is not isolated")
        tail_moved = not np.array_equal(X_st[:, NHEAD:], X_tr[:, NHEAD:])
        print(f"   env tail (cols {NHEAD}..{X_st.shape[1] - 1}) changed : {tail_moved}")
        if not tail_moved:
            fails.append("C: the env tail is IDENTICAL under ENV_WINDOW — the transient join did nothing")

    # ---- B. the transient tail is year-varying and equals the source table ---------------------------
    print("\n-- B. transient tail re-derived independently from the source parquet")
    envp = f"{BASE}/tables/cell_year_env_{SCENARIO}_w{int(WINDOW)}.parquet"
    ev = (pl.read_parquet(envp).select(["Cell", "Year"] + ENV_COLS)
          .with_columns([pl.col(c).cast(pl.Float64) for c in ENV_COLS]))
    key = {(int(r[0]), int(r[1])): np.array(r[2:], dtype="<f8") for r in ev.iter_rows()}
    nprobe = min(20000, X_tr.shape[0])
    idx = np.random.default_rng(11).choice(X_tr.shape[0], size=nprobe, replace=False)
    bad = 0
    for i in idx:
        want = key.get((int(c_tr[i]), int(y_tr[i])))
        if want is None or not np.array_equal(want, X_tr[i, NHEAD:]):
            bad += 1
    print(f"   {nprobe - bad}/{nprobe} probed rows carry their own (Cell,Year) moisture values")
    if bad:
        fails.append(f"B: {bad} of {nprobe} probed rows do NOT match the source table's (Cell,Year) values")
    # year-variation WITHIN a cell (the whole point: a frozen tail has exactly 1 distinct value per cell)
    print("   distinct tail values per cell (static must be 1, transient must be > 1):")
    for cell in sorted(set(c_tr.tolist())):
        ms = np.unique(X_st[c_st == cell, NHEAD:], axis=0).shape[0]
        mt = np.unique(X_tr[c_tr == cell, NHEAD:], axis=0).shape[0]
        nyr = int(np.unique(y_tr[c_tr == cell]).size)
        print(f"     cell {cell:6d}: static {ms:3d}   transient {mt:3d}   (of {nyr} years)")
        if ms != 1:
            fails.append(f"B: static tail has {ms} distinct values in cell {cell} (must be 1)")
        if mt < 2:
            fails.append(f"B: transient tail has {mt} distinct value(s) in cell {cell} — no year signal")

    print("\n" + "=" * 96)
    if fails:
        print(f"GATE FAILED — {len(fails)} problem(s):")
        for f in fails:
            print(f"   ✗ {f}")
        return 1
    print("GATE PASSED — default byte-identical, years.i64 aligned, tail isolated and year-varying.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
