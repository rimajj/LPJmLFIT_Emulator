#!/usr/bin/env python
"""explore_de_verify_sh14_gate.py -- verifier re-check of the SH14 additive-only gate, NaN/inf-aware.

Line X round 2 (2026-10-01). The builder's gate skips a float column whose max relative difference is NaN
(`not (rel != rel)`); this re-runs old-vs-new on the round-1 tolerance tables counting every row whose values
differ, treating NaN==NaN and inf==inf as equal and anything else unequal. Writes
/p/tmp/jamirp/X_de/_reports/r2_verify_SH14_gate.json."""
import json

import numpy as np
import polars as pl

REF = "/p/tmp/jamirp/X_de/reference"
BAK = "/p/tmp/jamirp/X_de/shared/scorer/backup_pre_SH14/reference"
K = ["gcm", "scen", "window", "Cell", "quantity"]
out = {}
for sub in ["", "block/", "block_dev/"]:
    o = pl.read_parquet(f"{BAK}/{sub}tolerance.parquet")
    n = pl.read_parquet(f"{REF}/{sub}tolerance.parquet").select(o.columns)
    j = o.join(n, on=K, how="left", suffix="_n")
    rec = {"rows_old": o.height, "rows_joined": j.height}
    for c in o.columns:
        if c in K:
            continue
        a, b = j[c], j[f"{c}_n"]
        if a.dtype.is_float():
            x, y = a.to_numpy().astype(float), b.to_numpy().astype(float)
            xn, yn = np.isnan(x), np.isnan(y)
            same = (xn & yn) | (x == y) | (~xn & ~yn & np.isfinite(x) & np.isfinite(y)
                                           & (np.abs(x - y) <= 1e-12 * np.maximum(np.abs(x), 1e-300)))
            rec[c] = {"n_diff": int((~same).sum()), "n_nan_old": int(xn.sum()), "n_inf_old": int(np.isinf(x).sum())}
        else:
            rec[c] = {"n_diff": int((a.cast(pl.Utf8).fill_null("<null>") != b.cast(pl.Utf8).fill_null("<null>")).sum())}
    rec["total_diff"] = sum(v["n_diff"] for k, v in rec.items() if isinstance(v, dict))
    out[sub or "cell"] = rec
    print(sub or "cell", json.dumps(rec)[:1500], flush=True)
json.dump(out, open("/p/tmp/jamirp/X_de/_reports/r2_verify_SH14_gate.json", "w"), indent=1)
print("=== DONE ===", flush=True)
