#!/usr/bin/env python
"""explore_de_verify_sh14_calsplit.py -- verifier: is the calibrated tolerance's 95 % an in-sample number?

Line X round 2 (2026-10-01). The calibration multiplier k (per quantity, per target kind) is fit on the very
replica it is then scored on. Here: fit k on one GCM's rows only (R.calibrate_table on that subset), apply the k to
the OTHER GCM's rows, and measure the replica's panel106 conjunctive pass there (per gcm, scen, window, Cell).
Also recomputes the in-sample conjunctive pass grouped correctly by (gcm, scen, window, Cell).
Writes /p/tmp/jamirp/X_de/_reports/r2_verify_SH14_calsplit.json."""
import json
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_reference as R  # noqa: E402

out = {}
for scale, f in [("cell", f"{R.OUT}/tolerance.parquet"), ("block", f"{R.OUT}/block/tolerance.parquet")]:
    t = pl.scan_parquet(f).filter(pl.col("quantity").is_in(R.PANEL106)).collect()
    floor, base = R._floor_base()

    def conj(tab, col):
        ok = ((pl.col("R") - pl.col("C")).abs() <= pl.col(col) * (1 + 1e-9))
        return tab.filter(pl.col("R").is_not_null()).group_by(["gcm", "scen", "window", "Cell", "target_kind"]).agg(
            ok.all().alias("a")).group_by(["target_kind"]).agg(pl.col("a").mean().alias("conj")).sort(
            "target_kind").to_dicts()

    rec = {"in_sample_allowed_cal": conj(t, "allowed_cal")}
    for fit_g in ["MPI-ESM1-2-HR", "ACCESS-CM2"]:
        app_g = [g for g in ["MPI-ESM1-2-HR", "ACCESS-CM2"] if g != fit_g][0]
        fit, _ = R.calibrate_table(t.filter(pl.col("gcm") == fit_g).drop("allowed_cal"), "s_med", "k_fit")
        cal = _[["quantity", "target_kind", "k"]]
        app = t.filter(pl.col("gcm") == app_g).join(cal, on=["quantity", "target_kind"], how="left").with_columns(
            pl.max_horizontal(floor, pl.col("k").fill_null(0.0) * pl.col("s_med") * base).alias("allowed_xg"))
        rec[f"fit_{fit_g}_apply_{app_g}"] = conj(app, "allowed_xg")
        rec[f"in_sample_{app_g}"] = conj(t.filter(pl.col("gcm") == app_g), "allowed_cal")
    out[scale] = rec
    print(scale, json.dumps(rec), flush=True)
json.dump(out, open(f"{R.XDE}/_reports/r2_verify_SH14_calsplit.json", "w"), indent=1)
print("=== DONE ===", flush=True)
