#!/usr/bin/env python
"""Do two LPJmL-FIT C runs that should be physically identical actually agree?

The gate you run after **rebuilding the C binary** (a source patch, a toolchain change, a new
compile flag) to prove the rebuild did not move the physics.  Compare a fresh run against a
run made with the previous binary, same config / same cell set / same ``--ntasks``.

Why not ``cmp`` on the files (ADR 0043)
---------------------------------------
LPJmL writes a ``history`` global attribute into every NetCDF output holding a **wall-clock
timestamp and the config path**, so two runs with byte-identical physics differ in the header.
A file-level ``cmp`` reports "DIFFER" for all of them and tells you nothing.  Compare
**decoded variables** instead (SHA-256 over the raw bytes of each variable's values, plus its
dimensions and dtype).  Text outputs (``globalflux*.csv``, ``ind*.csv``) carry no timestamp
and are compared byte-for-byte.

Reference-basis warning (ADR 0041)
----------------------------------
A subset re-run is **not** a per-cell replica of a differently-decomposed run: same binary,
same restart, same forcing, a different cell set ⇒ a different trajectory.  So the two runs
compared here must share the cell set AND the task count.  This script cannot check that for
you — it prints the run directories so the caller can state it.

Usage::

    python scripts/diagnose_cbinary_rebuild_equality.py \
        --ref /p/tmp/jamirp/esm_land_daily/daily_2000_2019_fdiff_val_c42490_seed1/output \
        --new /p/tmp/jamirp/esm_land_daily/daily_2000_2019_M_rung2_gate_c42490_seed1/output

Exit status: 0 = every variable and every text output agrees; 1 = a mismatch; 2 = the two
directories do not hold the same set of files (nothing can be concluded).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import netCDF4  # type: ignore
import numpy as np


def sha_bytes(buf: bytes) -> str:
    return hashlib.sha256(buf).hexdigest()


def hash_netcdf_variables(path: Path) -> dict[str, str]:
    """SHA-256 per variable over dtype + shape + the raw decoded values.

    Deliberately ignores every attribute, including ``history`` (the timestamp that makes a
    file-level compare useless) and ``units``.  A units change IS a real change, but it is a
    metadata change, not a physics one, and conflating them is what this script exists to
    avoid; the caller sees the variable set itself in the report.
    """
    out: dict[str, str] = {}
    with netCDF4.Dataset(path) as ds:
        ds.set_auto_mask(False)
        for name, var in ds.variables.items():
            arr = np.asarray(var[:])
            h = hashlib.sha256()
            h.update(str(arr.dtype).encode())
            h.update(str(arr.shape).encode())
            h.update(np.ascontiguousarray(arr).tobytes())
            out[name] = h.hexdigest()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", required=True, type=Path, help="output dir of the run made with the PREVIOUS binary")
    ap.add_argument("--new", required=True, type=Path, help="output dir of the run made with the NEW binary")
    args = ap.parse_args()

    print(f"ref = {args.ref}")
    print(f"new = {args.new}")
    print("NOTE (ADR 0041): a verdict here is only about the BINARY if both runs used the same")
    print("      cell set and the same --ntasks. This script cannot verify that; state it.\n")

    ref_files = {p.name for p in args.ref.iterdir() if p.is_file()}
    new_files = {p.name for p in args.new.iterdir() if p.is_file()}
    if ref_files != new_files:
        print("FILE SET DIFFERS — nothing can be concluded.")
        print(f"  only in ref: {sorted(ref_files - new_files)}")
        print(f"  only in new: {sorted(new_files - ref_files)}")
        return 2

    n_var_ok = n_var_bad = 0
    bad: list[str] = []
    for name in sorted(ref_files):
        ref_p, new_p = args.ref / name, args.new / name
        if name.endswith(".nc"):
            rh, nh = hash_netcdf_variables(ref_p), hash_netcdf_variables(new_p)
            if set(rh) != set(nh):
                bad.append(f"{name}: variable SET differs ({sorted(set(rh) ^ set(nh))})")
                n_var_bad += 1
                continue
            diffs = [v for v in rh if rh[v] != nh[v]]
            n_var_ok += len(rh) - len(diffs)
            n_var_bad += len(diffs)
            status = "OK " if not diffs else "BAD"
            print(f"  [{status}] {name:<28} {len(rh)} variable(s)" + (f"  DIFFER: {diffs}" if diffs else ""))
            bad.extend(f"{name}:{v}" for v in diffs)
        elif name.endswith(".json"):
            # LPJmL's per-output sidecar embeds the absolute output path; skipped on purpose.
            print(f"  [skip] {name:<28} (sidecar: embeds the run's own output path)")
        else:
            same = ref_p.read_bytes() == new_p.read_bytes()
            print(f"  [{'OK ' if same else 'BAD'}] {name:<28} text, byte-for-byte")
            if same:
                n_var_ok += 1
            else:
                n_var_bad += 1
                bad.append(name)

    print(f"\n{n_var_ok} quantity/quantities identical, {n_var_bad} differ")
    if bad:
        print("MISMATCH — the rebuild moved the model:")
        for b in bad:
            print(f"  {b}")
        return 1
    print("VERDICT: the two builds are numerically identical on this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
