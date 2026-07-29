#!/usr/bin/env python3
"""Pool per-scenario Component-S training tables into ONE multi-regime table — ADR 0026 §4.

The long-term goal is ONE environment-conditioned emulator across CLIMATE regimes, not one model per
scenario. Each scenario's table is built INDEPENDENTLY by `build_slow_runtime_table.py` (crucially: the AR
`n_prev` join is WITHIN a scenario, so it never crosses the historic↔ssp discontinuity or splices two climate
models), each with its OWN transient boundary (`BOUNDARY_WINDOW`, ADR 0026) and soilmoist/lai. This script
just row-CONCATENATES their frozen outputs into a pooled table + a per-row `scenario.i64` tag (for the
honest hold-out-BY-SCENARIO eval, ADR 0026 §5) — column order is identical across scenarios (the
`flux_feature_vector` contract), so concatenation is valid and cheap.

Works for BOTH the count table (X.f64 / y.f64 / cells.i64 / manifest.txt) and the copula table
(Xc.f64 / Y_<axis>.f64 / cells.i64 / manifest_copula.txt) — detected by which manifest is present.

Copula STRUCT axes (the opt-in diagnostic BIOMASS/SIZE axes, `nstruct`/`struct_axes` in the manifest) are
pooled exactly like the production trait axes and re-declared in the pooled manifest. They are APPENDED
after the production axes, never interleaved: `naxes`/`axes` keep meaning "the production axes" so the
serialized .rcop contract (ADR 0025) is untouched. A manifest WITHOUT `struct_axes` means none, so every
pre-existing table dir pools byte-identically to before.

Env:
  IN_DIRS  = comma-list of per-scenario table dirs (e.g. slow_runtime_historic_w20,slow_runtime_ssp370_w20)
  OUT      = pooled output dir
  TAGS     = optional comma-list of scenario names aligned to IN_DIRS (default: read `scenario` from each manifest)

Run: IN_DIRS=/p/tmp/.../slow_count_hist_w20,/p/tmp/.../slow_count_ssp_w20 OUT=/p/tmp/.../slow_count_pooled_w20 \
     python3 scripts/pool_slow_tables.py
"""

import os
import sys

import numpy as np


def _read_manifest(d):
    for name in ("manifest.txt", "manifest_copula.txt"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            man = {}
            for ln in open(p):
                parts = ln.rstrip("\n").split("\t", 1)
                if len(parts) == 2:
                    man[parts[0]] = parts[1]
            man["_kind"] = "copula" if name == "manifest_copula.txt" else "count"
            man["_file"] = name
            return man
    raise SystemExit(f"FATAL: no manifest(.txt|_copula.txt) in {d}")


def main():
    in_dirs = [d for d in os.environ.get("IN_DIRS", "").split(",") if d.strip()]
    if len(in_dirs) < 2:
        raise SystemExit("IN_DIRS must list >= 2 per-scenario table dirs (comma-separated)")
    out = os.environ["OUT"]
    tags_env = [t for t in os.environ.get("TAGS", "").split(",") if t.strip()]
    os.makedirs(out, exist_ok=True)

    mans = [_read_manifest(d) for d in in_dirs]
    kind = mans[0]["_kind"]
    if any(m["_kind"] != kind for m in mans):
        raise SystemExit(f"FATAL: mixed table kinds {[m['_kind'] for m in mans]} — pool count OR copula, not both")
    tags = tags_env if tags_env else [m.get("scenario", f"s{i}") for i, m in enumerate(mans)]
    if len(tags) != len(in_dirs):
        raise SystemExit(f"TAGS ({len(tags)}) must align with IN_DIRS ({len(in_dirs)})")

    if kind == "count":
        p = int(mans[0]["p"])
        cols = mans[0]["colnames"]
        for m in mans:
            if int(m["p"]) != p or m["colnames"] != cols:
                raise SystemExit("FATAL: count tables have mismatched p/colnames — cannot pool")
        Xs, ys, cs, ss = [], [], [], []
        for i, d in enumerate(in_dirs):
            n = int(mans[i]["n"])
            X = np.fromfile(os.path.join(d, "X.f64"), dtype="<f8").reshape(n, p)
            y = np.fromfile(os.path.join(d, "y.f64"), dtype="<f8")
            c = np.fromfile(os.path.join(d, "cells.i64"), dtype="<i8")
            assert y.shape[0] == n and c.shape[0] == n, f"{d}: n mismatch"
            Xs.append(X); ys.append(y); cs.append(c)
            ss.append(np.full(n, i, dtype="<i8"))
            print(f"   + {tags[i]:10s} {d}: {n} rows")
        X = np.concatenate(Xs); y = np.concatenate(ys); c = np.concatenate(cs); s = np.concatenate(ss)
        X.astype("<f8", copy=False).tofile(os.path.join(out, "X.f64"))
        y.astype("<f8", copy=False).tofile(os.path.join(out, "y.f64"))
        c.astype("<i8", copy=False).tofile(os.path.join(out, "cells.i64"))
        s.astype("<i8", copy=False).tofile(os.path.join(out, "scenario.i64"))
        ntot = X.shape[0]
        with open(os.path.join(out, "manifest.txt"), "w") as f:
            f.write(f"n\t{ntot}\n"); f.write(f"p\t{p}\n")
            f.write(f"nhead\t{mans[0]['nhead']}\n"); f.write(f"nboundary\t{mans[0]['nboundary']}\n")
            f.write(f"colnames\t{cols}\n"); f.write("target\tn_living\n")
            f.write("scenario\tpooled\n")
            f.write("pooled_scenarios\t" + " ".join(tags) + "\n")
            f.write("scenario_tag\tscenario.i64\n")
            f.write(f"ncells\t{len(np.unique(c))}\n")
        print(f"== POOLED count table: {ntot} rows (p={p}) from {len(in_dirs)} scenarios -> {out}")
    else:  # copula
        ncond = int(mans[0]["ncond"])
        axes = mans[0]["axes"].split()
        # Diagnostic STRUCT axes (absent `struct_axes` == none). A MISMATCHED struct set is as fatal as a
        # mismatched axes/cond_cols set: it means the two scenarios were built under different feature
        # contracts, so their rows are not comparable and pooling them would fabricate a table.
        struct = mans[0].get("struct_axes", "").split()
        for m in mans:
            if (int(m["ncond"]) != ncond or m["axes"].split() != axes
                    or m["cond_cols"] != mans[0]["cond_cols"]
                    or m.get("struct_axes", "").split() != struct):
                raise SystemExit(
                    "FATAL: copula tables have mismatched ncond/axes/cond_cols/struct_axes — cannot pool"
                )
        all_axes = axes + struct  # production first, struct APPENDED — order is load-bearing (eval seeds by index)
        Xcs, cs, ss = [], [], []
        Ys = {ax: [] for ax in all_axes}
        for i, d in enumerate(in_dirs):
            n = int(mans[i]["n"])
            Xc = np.fromfile(os.path.join(d, "Xc.f64"), dtype="<f8").reshape(n, ncond)
            Xcs.append(Xc); cs.append(np.fromfile(os.path.join(d, "cells.i64"), dtype="<i8"))
            ss.append(np.full(n, i, dtype="<i8"))
            for ax in all_axes:
                col = np.fromfile(os.path.join(d, f"Y_{ax}.f64"), dtype="<f8")
                assert col.shape[0] == n, f"{d}: Y_{ax}.f64 has {col.shape[0]} rows, manifest says n={n}"
                Ys[ax].append(col)
            print(f"   + {tags[i]:10s} {d}: {n} stems")
        Xc = np.concatenate(Xcs); c = np.concatenate(cs); s = np.concatenate(ss)
        Xc.astype("<f8", copy=False).tofile(os.path.join(out, "Xc.f64"))
        c.astype("<i8", copy=False).tofile(os.path.join(out, "cells.i64"))
        s.astype("<i8", copy=False).tofile(os.path.join(out, "scenario.i64"))
        for ax in all_axes:
            np.concatenate(Ys[ax]).astype("<f8", copy=False).tofile(os.path.join(out, f"Y_{ax}.f64"))
        ntot = Xc.shape[0]
        xmean = [float(Xc[:, j].mean()) for j in range(ncond)]
        with open(os.path.join(out, "manifest_copula.txt"), "w") as f:
            f.write(f"n\t{ntot}\n"); f.write(f"ncond\t{ncond}\n"); f.write(f"naxes\t{len(axes)}\n")
            f.write(f"cond_cols\t{mans[0]['cond_cols']}\n"); f.write("axes\t" + " ".join(axes) + "\n")
            if struct:  # only when present — absent lines == no struct axes, keeping old dirs valid
                f.write(f"nstruct\t{len(struct)}\n")
                f.write("struct_axes\t" + " ".join(struct) + "\n")
            f.write("scenario\tpooled\n"); f.write("pooled_scenarios\t" + " ".join(tags) + "\n")
            f.write("scenario_tag\tscenario.i64\n")
            f.write(f"ncells\t{len(np.unique(c))}\n")
            f.write("x\t" + " ".join(repr(v) for v in xmean) + "\n")
        print(f"== POOLED copula table: {ntot} stems (ncond={ncond}, axes={axes}"
              + (f", struct_axes={struct}" if struct else ", struct_axes=[]") + f") -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
