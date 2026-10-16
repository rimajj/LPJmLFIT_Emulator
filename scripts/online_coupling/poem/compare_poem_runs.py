"""Are two POEM runs the same model trajectory? (ADR 0347 gates)

    python compare_poem_runs.py <run_a> <run_b>     exit 0 iff every variable is bit-identical

Compares the DECODED variables (SHA-256 of the raw array bytes) of every FMS restart file the runs
wrote at their end (RESTART/*.res.nc), every history file (history/*.nc) and every LPJmL
output (history/output-*/*.nc), never the files
themselves: a NetCDF header carries timestamps and paths, so identical physics gives different
bytes (CLAUDE.md sec. 3, ADR 0043). Variables named ``*time*`` bounds are compared too -- the
runs must cover the same period.
"""

from __future__ import annotations

import glob
import hashlib
import os
import sys

import netCDF4
import numpy as np


def digests(path):
    out = {}
    with netCDF4.Dataset(path) as ds:
        ds.set_auto_maskandscale(False)
        for v in ds.variables:
            a = np.ascontiguousarray(ds.variables[v][...])
            out[v] = hashlib.sha256(a.tobytes()).hexdigest()
    return out


def files(run):
    fs = sorted(glob.glob(os.path.join(run, "RESTART", "*.res.nc")))
    fs += sorted(glob.glob(os.path.join(run, "history", "*.nc")))
    fs += sorted(glob.glob(os.path.join(run, "history", "output-*", "*.nc")))  # LPJmL's own
    fs += sorted(glob.glob(os.path.join(run, "output", "*.nc")))  # LPJmL's own, short runs
    return {os.path.relpath(f, run): f for f in fs}


def main(a, b):
    fa, fb = files(a), files(b)
    assert fa, f"no RESTART/history NetCDF files in {a}"
    if set(fa) != set(fb):
        print("file sets differ:", sorted(set(fa) ^ set(fb)))
        return 1
    nvar = ndiff = 0
    for rel in sorted(fa):
        da, db = digests(fa[rel]), digests(fb[rel])
        if set(da) != set(db):
            print(f"{rel}: variable sets differ {sorted(set(da) ^ set(db))}")
            ndiff += 1
            continue
        bad = [v for v in da if da[v] != db[v]]
        nvar += len(da)
        ndiff += len(bad)
        print(f"{rel}: {len(da)} variables, {len(bad)} differ{(' ' + str(bad[:8])) if bad else ''}")
    print(
        f"TOTAL {nvar} variables in {len(fa)} files, {ndiff} differ ->",
        "IDENTICAL" if ndiff == 0 else "DIFFERENT",
    )
    return 0 if ndiff == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
