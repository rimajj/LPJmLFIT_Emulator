#!/usr/bin/env python
"""explore_de_sh_scorer_power.py -- SH14 diagnostic: what would an INDEPENDENT run, exactly as good as the
original's second seed, be expected to pass under each tolerance column?

Line X, Germany emulator exploration, round 2 (2026-10-01). The other-seed null passes allowed_cell_abs =
max(0.1|C|, |C-R|) at 1.0 BY CONSTRUCTION (its own deviation is the tolerance), so that 1.0 says nothing about
whether a third, independent run would pass. Exchangeability gives the answer: for an independent run E drawn
like R, |E - C| has the same distribution as |R - C|. Proxy for that distribution per row: the empirical
distribution of the normalised two-seed deviation r = |C-R|/base over the cells of the same (gcm, scen, window,
quantity, density stratum), base = |C| (relative levels), 1 (shares), the response/contrast scale. Then
P(pass) = ECDF(allowed/base). Conjunctive expectation per cell = product over the panel's quantities (treats
quantities as independent: quantiles of one trait are positively correlated, so the true value is HIGHER --
read it as a lower bound). Writes /p/tmp/jamirp/X_de/shared/scorer/sh14_independent_run_expectation.csv.
[ASSUMPTION] cells within a stratum are exchangeable in their relative two-seed deviation.

SH14 REPAIR (verifier): the calibrated columns are NOT estimated here any more. Their multipliers were fitted on
the very deviations this ECDF reads, so the estimate is circular (it returned 0.99709 for allowed_cal at cell
h1985 = the replica's in-sample marginal). The calibrated tolerances are instead judged OUT OF SAMPLE: the
`transfer` table (sh14_calibration_transfer.csv) gives the replica's panel106 conjunctive pass under the in-sample
calibrations (allowed_cal, allowed_cal1) and under the same calibrations fitted on the OTHER GCM only
(allowed_cal_xg, allowed_cal1_xg), per scale (cell / block / block_dev), truth seed, target kind and scenario set.
OWNER DECISION 2026-10-01: runs on the selected reference set (XDE_REFSET, default clean = 1985-2044 only).
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_reference as R  # noqa: E402

OUTD = f"{R.XDE}/shared/scorer"
COLS = ["allowed", "allowed_cell", "allowed_cell_abs", "allowed_c"]  # calibrated columns: see transfer()
CAL_COLS = ["allowed_cal", "allowed_cal1", "allowed_cal_xg", "allowed_cal1_xg"]


def main() -> int:
    rows = []
    for scale, f in [("cell", f"{R.REFOUT}/tolerance.parquet"), ("block", f"{R.REFOUT}/block/tolerance.parquet")]:
        t = pl.scan_parquet(f).filter(pl.col("quantity").is_in(R.PANEL106) & pl.col("R").is_not_null()).select(
            ["gcm", "scen", "window", "Cell", "quantity", "target_kind", "stratum", "C", "R", "scale"] + COLS
        ).collect()
        isf = pl.col("quantity").str.starts_with("share_")
        base = pl.when(isf).then(pl.lit(1.0)).when(pl.col("target_kind") == "level").then(pl.col("C").abs()) \
            .otherwise(pl.col("scale"))
        t = t.with_columns(base.alias("base")).filter(pl.col("base") > 0).with_columns(
            ((pl.col("C") - pl.col("R")).abs() / pl.col("base")).alias("r"))
        g = ["gcm", "scen", "window", "quantity", "stratum"]
        parts = []
        for _, sub in t.group_by(g):
            rs = np.sort(sub["r"].to_numpy())
            out = {}
            for c in COLS:
                thr = (sub[c] / sub["base"]).to_numpy() * (1 + 1e-9)
                out[f"p_{c}"] = np.searchsorted(rs, thr, side="right") / len(rs)
            parts.append(sub.select(["gcm", "scen", "window", "Cell", "quantity", "target_kind"]).with_columns(
                [pl.Series(k, v) for k, v in out.items()]))
        p = pl.concat(parts)
        # per-quantity marginal expectation and the conjunctive (product) expectation per cell
        marg = p.group_by(["target_kind", "window"]).agg([pl.col(f"p_{c}").mean().alias(f"marg_{c}") for c in COLS])
        conj = p.group_by(["gcm", "scen", "window", "Cell", "target_kind"]).agg(
            [pl.col(f"p_{c}").log().sum().exp().alias(f"conj_{c}") for c in COLS]).group_by(
            ["target_kind", "window"]).agg([pl.col(f"conj_{c}").mean().alias(f"conj_{c}") for c in COLS])
        rows.append(marg.join(conj, on=["target_kind", "window"]).with_columns(pl.lit(scale).alias("scale")))
    out = pl.concat(rows).sort(["scale", "target_kind", "window"])
    out.write_csv(f"{OUTD}/sh14_independent_run_expectation.csv")
    with pl.Config(tbl_rows=100, tbl_cols=20, tbl_width_chars=250, float_precision=3):
        print(out)
    transfer()
    print("=== DONE explore_de_sh_scorer_power ===", flush=True)
    return 0


def transfer() -> None:
    """Replica (other seed) panel106 conjunctive pass per (gcm, scen, window, unit), then median/min/max over
    (gcm, scen) -- for scen_set all and, for contrasts, ssp370 alone (H4) and ssp245 alone."""
    rows = []
    for scale, d in [("cell", R.REFOUT), ("block", f"{R.REFOUT}/block"), ("block_dev", f"{R.REFOUT}/block_dev")]:
        for ts, sfx in [(1, ""), (2, "_t2")]:
            t = pl.scan_parquet(f"{d}/tolerance{sfx}.parquet").filter(
                pl.col("quantity").is_in(R.PANEL106) & pl.col("R").is_not_null()).select(
                ["gcm", "scen", "window", "Cell", "quantity", "target_kind", "C", "R"] + CAL_COLS).collect()
            dev = (pl.col("R") - pl.col("C")).abs()
            u = t.group_by(["gcm", "scen", "window", "Cell", "target_kind"]).agg(
                [(dev <= pl.col(c) * (1 + 1e-9)).all().alias(c) for c in CAL_COLS])
            g = u.group_by(["gcm", "scen", "window", "target_kind"]).agg([pl.col(c).mean() for c in CAL_COLS])
            for ssn, sc in [("all", None), ("ssp370", ["ssp370"]), ("ssp245", ["ssp245"])]:
                x = g if sc is None else g.filter(pl.col("scen").is_in(sc))
                if not x.height:
                    continue
                a = x.group_by(["window", "target_kind"]).agg(
                    [pl.col(c).median().alias(f"{c}_med") for c in CAL_COLS]
                    + [pl.col(c).min().alias(f"{c}_min") for c in CAL_COLS] + [pl.len().alias("n_gcm_scen")])
                rows.append(a.with_columns(pl.lit(scale).alias("scale"), pl.lit(ts).alias("truth_seed"),
                                           pl.lit(ssn).alias("scen_set")))
    out = pl.concat(rows).sort(["scale", "truth_seed", "target_kind", "window", "scen_set"])
    out.write_csv(f"{OUTD}/sh14_calibration_transfer.csv")
    with pl.Config(tbl_rows=300, tbl_cols=20, tbl_width_chars=250, float_precision=3):
        print(out.filter(pl.col("truth_seed") == 1).select(
            ["scale", "target_kind", "window", "scen_set", "n_gcm_scen"] + [f"{c}_med" for c in CAL_COLS]))


if __name__ == "__main__":
    sys.exit(main())
