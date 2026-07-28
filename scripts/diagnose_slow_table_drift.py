#!/usr/bin/env python3
"""Did MY edit change the Component-S training table, or was the committed fixture already stale?

## Why this exists

`scripts/verify_hainich_demo_artifacts.sh` regenerates the committed Hainich demo artifacts and demands they
come back byte-identical (guardrail 4). But that gate conflates two very different failures:

  (a) the edit under test genuinely changed the features at Hainich  →  STOP, diagnose;
  (b) the committed fixture was ALREADY stale — regenerating it from unchanged code would move it too.

(b) is not hypothetical: it is what happened on 2026-07-28. The committed `drf_forest_hainich.drf` was trained
with the documented Hainich PROXY features (`soilmoist` const 0.7, `lai` = the per-crown ind-LAI sum ≈ 21),
while the current builder inner-joins the REAL features (daily `swc` → 0.85, C `LAI_STAND` → 3.07). The fixture
therefore fails a byte-identity gate under ANY edit, and — worse — it is a live ADR-0023 train/inference shift,
because the coupled runtime feeds `flux_feature_vector` the real values, not the proxies.

## What it does

Builds the same single-cell table twice — once with `build_slow_runtime_table.py` as of a git REF (the control),
once with the working tree (the edit) — and compares `X` column-by-column plus `y`, `n_init` and `age0`.

  * all columns equal (within streaming-sum jitter)  ⇒ the edit is a NO-OP for this cell. Any fixture movement
    the byte-identity gate reports is PRE-EXISTING staleness, not this edit. Proceed, and record the staleness.
  * some column moved                                ⇒ the edit DID change the features. That is the real STOP.

The control builder is extracted with `git show REF:scripts/build_slow_runtime_table.py` and run as a
standalone file, so this works even when the edit changed which module the constants come from.

## Run

    TIME=00:45:00 NCPUS=16 scripts/sbatch_python.sh S-drift scripts/diagnose_slow_table_drift.py

Env: CELL (42490, Hainich), REF (HEAD), SEED (1), MODE (count), WORKDIR (/p/tmp/jamirp/S_table_drift),
     JITTER (1e-11 — the builder's documented ~1e-13 parallel partial-sum jitter, with margin).
Any other knob the builder reads (SCENARIO, BOUNDARY_WINDOW, ...) is forwarded from the environment, so the
control and the edit are always built under IDENTICAL settings.
"""

import os
import subprocess
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
BUILDER = "scripts/build_slow_runtime_table.py"
CELL = os.environ.get("CELL", "42490")
REF = os.environ.get("REF", "HEAD")
SEED = os.environ.get("SEED", "1")
MODE = os.environ.get("MODE", "count")
WORKDIR = os.environ.get("WORKDIR", "/p/tmp/jamirp/S_table_drift")
JITTER = float(os.environ.get("JITTER", "1e-11"))


def _git(*args):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"FATAL: git {' '.join(args)} failed:\n{r.stderr}")
    return r.stdout


def build(script, out, label):
    """Run a builder into `out`. Env is inherited so control and edit share every knob."""
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, CELLS=CELL, SEED=SEED, MODE=MODE, OUT=out)
    print(f"\n{'=' * 96}\n== building {label}: {script}\n{'=' * 96}", flush=True)
    r = subprocess.run([PY, script], env=env, cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-4000:])
        print(r.stderr[-4000:], file=sys.stderr)
        raise SystemExit(f"FATAL: {label} build failed (exit {r.returncode})")
    for li in r.stdout.splitlines():
        if li.startswith("==") or "growth_eff" in li:
            print("   " + li)


def load(out):
    name = "manifest_copula.txt" if MODE == "copula" else "manifest.txt"
    man = dict(li.split("\t", 1) for li in open(f"{out}/{name}").read().splitlines() if "\t" in li)
    if MODE == "copula":
        n, p = int(man["n"]), int(man["ncond"])
        cols = man["cond_cols"].split()
        X = np.fromfile(f"{out}/Xc.f64", dtype="<f8").reshape(n, p)
        ys = {ax: np.fromfile(f"{out}/Y_{ax}.f64", dtype="<f8") for ax in man["axes"].split()}
    else:
        n, p = int(man["n"]), int(man["p"])
        cols = man["colnames"].split()
        X = np.fromfile(f"{out}/X.f64", dtype="<f8").reshape(n, p)
        ys = {man.get("target", "y"): np.fromfile(f"{out}/y.f64", dtype="<f8")}
    return man, cols, X, ys


def main():
    head = _git("rev-parse", "--short", REF).strip()
    dirty = bool(_git("status", "--porcelain", "--", BUILDER).strip())
    print(f"== cell {CELL} · MODE={MODE} · SEED={SEED}")
    print(f"== control REF={REF} ({head}) vs the WORKING TREE ({'modified' if dirty else 'UNMODIFIED'})")
    if not dirty:
        print("   NOTE: the builder is unmodified vs REF, so this run is a pure REPRODUCIBILITY check.")

    ctl_script = os.path.join(WORKDIR, f"builder_{head}.py")
    os.makedirs(WORKDIR, exist_ok=True)
    with open(ctl_script, "w") as f:
        f.write(_git("show", f"{REF}:{BUILDER}"))

    ctl_out, edit_out = f"{WORKDIR}/control", f"{WORKDIR}/edit"
    build(ctl_script, ctl_out, f"CONTROL ({REF} = {head})")
    build(os.path.join(REPO, BUILDER), edit_out, "EDIT (working tree)")

    mc, cc, Xc, yc = load(ctl_out)
    me, ce, Xe, ye = load(edit_out)

    print(f"\n{'=' * 96}\n== CONTROL vs EDIT (cell {CELL})\n{'=' * 96}")
    print(f"   rows       control={Xc.shape[0]}  edit={Xe.shape[0]}   "
          f"{'MATCH' if Xc.shape == Xe.shape else '*** DIFFER ***'}")
    print(f"   colnames   {'MATCH' if cc == ce else '*** DIFFER ***'}")
    for k in ("n_init", "age0", "ncells"):
        if k in mc or k in me:
            same = mc.get(k) == me.get(k)
            print(f"   {k:10s} control={mc.get(k)}  edit={me.get(k)}   "
                  f"{'MATCH' if same else '*** DIFFER ***'}")
    if Xc.shape != Xe.shape or cc != ce:
        print("\n   VERDICT: THE EDIT CHANGED THE TABLE (shape/colnames) — STOP and diagnose.")
        return 1

    print(f"\n   {'column':16s} {'max|abs diff|':>14s} {'max|rel diff|':>14s}  "
          f"{'control mean':>14s} {'edit mean':>14s}")
    worst, worst_col = 0.0, ""
    for j, c in enumerate(cc):
        a, b = Xc[:, j], Xe[:, j]
        ad = np.abs(a - b).max()
        scale = np.maximum(np.abs(a), np.abs(b))
        rd = float(np.max(np.where(scale > 0, np.abs(a - b) / np.where(scale > 0, scale, 1.0), 0.0)))
        if rd > worst:
            worst, worst_col = rd, c
        flag = "" if rd <= JITTER else "   <<< MOVED"
        print(f"   {c:16s} {ad:14.6g} {rd:14.6g}  {a.mean():14.6g} {b.mean():14.6g}{flag}")

    ybad = []
    for k in sorted(set(yc) | set(ye)):
        if k in yc and k in ye and yc[k].shape == ye[k].shape:
            d = float(np.abs(yc[k] - ye[k]).max())
            print(f"   target {k:24s} max|abs diff|={d:.6g}")
            if d > 0:
                ybad.append(k)
        else:
            print(f"   target {k:24s} *** present/shaped differently ***")
            ybad.append(k)

    print(f"\n   worst relative column difference: {worst:.6g}"
          f"{f' (on `{worst_col}`)' if worst > 0 else ''}  [jitter tolerance {JITTER:g}]")
    if worst <= JITTER and not ybad:
        print("   VERDICT: NO-OP — the edit does not change this cell's table.")
        print("            ⇒ if verify_hainich_demo_artifacts.sh still reports moved fixtures, those fixtures")
        print("              are PRE-EXISTING STALE (regenerated from unchanged code they would move too).")
        return 0
    print("   VERDICT: THE EDIT CHANGED THE TABLE — this is the real STOP (ADR 0031 §3). Diagnose before")
    print("            retraining anything global; a moved feature is a train/inference shift (ADR 0023).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
