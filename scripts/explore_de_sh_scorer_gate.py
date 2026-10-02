#!/usr/bin/env python
"""explore_de_sh_scorer_gate.py -- SH14 gate: the scorer amendments ADD, they do not change.

Line X, Germany emulator exploration, round 2 (2026-10-01). Compares the rebuilt reference + nulls against the
pre-SH14 backup (/p/tmp/jamirp/X_de/shared/scorer/backup_pre_SH14/reference) on every ROUND-1 column, and
tabulates how the other-seed (replica) pass fractions change under the SH14 symmetric tolerances.

  gate     -> /p/tmp/jamirp/X_de/shared/scorer/sh14_gate.json (+ printed), exit 0 iff every round-1 column of
              levels_long, tolerance (cell/block/block_dev), calibration (level/response multipliers) and the four
              round-1 nulls' conjunctive/criterion summaries is identical (floats within 1e-12 relative)
  changes  -> /p/tmp/jamirp/X_de/shared/scorer/sh14_null_table.csv: per (null, scale, cells, tolerance, panel,
              window, scen_set) median/min/max over (gcm, scen) of the conjunctive pass fraction + ceiling medians
              (ceiling_same, and for contrasts ceiling_unbr_lo/hi = unbranched-legs bracket)
  prereg   -> sh14_prereg_null_values.csv (contrasts on ssp370 alone for H4; ssp245 separate)
  OWNER DECISION 2026-10-01 (clean reference set, the default; XDE_REFSET=full for the legacy tables):
  gate_clean -> sh14_clean_gate.json: the clean set (reference/clean) carries no excluded target, and its levels and
              every NON-calibrated tolerance column equal the full set's on the 1985-2044 targets (cell, block,
              block_dev; truth seed 1 and 2); the calibration multipliers (refitted on 1985-2044 only) are tabulated
  snr        -> sh14_clean_snr.csv: signal-to-noise of each 1985-2044 response statistic (r2015, c2015 ssp370/ssp245)
              per quantity, at cell / block / block_dev scale and for the Germany + tercile aggregates
  changes / prereg write the clean tables under the old names (legacy copies: backup_pre_SH14clean/)
  SH14 repair 2 (verifier r2_verify_SH14.json):
  snr        now carries the PURE-NOISE reference beside every row: for |(C+R)/2| / |C-R| with zero true signal and
              exchangeable Gaussian seeds the ratio is |Cauchy|/2 -> median 0.5, P(>1) = 1 - (2/pi) atan(2) = 0.2952,
              P(>=3) = 1 - (2/pi) atan(6) = 0.1051, sign agreement 0.5 [DERIVED, checked by simulation in the stage]
              + z of frac_sn_gt1 against 0.2952 (units are spatially correlated: the z is optimistic) + a verdict
              column; aggregates are flagged "one draw per GCM"
  ceilings   -> sh14_ceiling_per_window.csv: the replica's panel106 conjunctive pass per (cells, scale, truth seed,
              gcm, scen, window) under allowed_cal / allowed_cal_xg / allowed_cal1_xg (+ the unbranched-legs bracket
              for contrasts) and the member's role -- the per-window ceiling to quote beside any block H2 number
  primary    -> sh14_primary_gate_nulls.csv: the PRIMARY gate (block c2015 ssp370 panel106, arm cal_xg vs 0.9 x the
              replica's cal_xg on the same rows) as each null scores it, with its verdict
"""

from __future__ import annotations

import json
import os
import sys

import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_reference as R  # noqa: E402

REF = R.REFOUT  # the selected reference set (clean by default; XDE_REFSET=full -> legacy reference/)
FULL = R.OUT
BAK = f"{R.XDE}/shared/scorer/backup_pre_SH14/reference"
OUTD = f"{R.XDE}/shared/scorer"
K = ["gcm", "scen", "window", "Cell", "quantity"]


def cmp(old: pl.DataFrame, new: pl.DataFrame, keys: list[str], name: str) -> dict:
    cols = [c for c in old.columns if c not in keys]
    miss = [c for c in cols if c not in new.columns]
    j = old.with_columns(pl.lit(True).alias("_o")).join(
        new.select(keys + [c for c in cols if c in new.columns]).with_columns(pl.lit(True).alias("_n")),
        on=keys, how="left", suffix="_n")
    rec = {"name": name, "rows_old": old.height, "rows_new_total": new.height,
           "old_rows_missing_in_new": int(j["_n"].is_null().sum()), "columns_missing_in_new": miss, "diffs": {}}
    bad = rec["old_rows_missing_in_new"] + len(miss)
    for c in cols:
        if c in miss:
            continue
        a, b = j[c], j[f"{c}_n"]
        nn = int((a.is_null() != b.is_null()).sum())
        if a.dtype.is_float():
            # SH14 repair (verifier): NaN-aware. NaN == NaN and +-inf == +-inf count as equal, a NaN or inf against
            # anything else is a mismatch, and finite pairs must agree to 1e-12 relative. (The old test skipped a
            # column whose max relative difference was NaN, so such a column could never fail.)
            ca, cb = pl.col(c), pl.col(f"{c}_n")
            both = j.filter(ca.is_not_null() & cb.is_not_null())
            nan_mis = int((both[c].is_nan() != both[f"{c}_n"].is_nan()).sum()) if both.height else 0
            inf_mis = both.filter((ca.is_infinite() | cb.is_infinite()) & ~(ca.is_nan() | cb.is_nan())
                                  & (ca != cb)).height if both.height else 0
            fin = both.filter(ca.is_finite() & cb.is_finite())
            rel = fin.select(((ca - cb).abs() / ca.abs().clip(1e-300)).max()).item() if fin.height else 0.0
            d = nn + nan_mis + inf_mis + int((rel or 0.0) > 1e-12)
            if d or (rel or 0) > 0:
                rec["diffs"][c] = {"null_mismatch": nn, "nan_mismatch": nan_mis, "inf_mismatch": inf_mis,
                                   "max_rel": rel}
            bad += d
        else:
            d = nn + int((a.cast(pl.Utf8) != b.cast(pl.Utf8)).fill_null(False).sum())
            if d:
                rec["diffs"][c] = {"mismatch": d}
            bad += d
    rec["ok"] = bad == 0
    return rec


def gate() -> int:
    recs = []
    recs.append(cmp(pl.read_parquet(f"{BAK}/levels_long.parquet"), pl.read_parquet(f"{REF}/levels_long.parquet"),
                    ["gcm", "scen", "seed", "window", "Cell", "quantity"], "levels_long"))
    for sub in ["", "block/", "block_dev/"]:
        o = pl.read_parquet(f"{BAK}/{sub}tolerance.parquet")
        n = pl.read_parquet(f"{REF}/{sub}tolerance.parquet")
        recs.append(cmp(o, n, K, f"{sub}tolerance.parquet"))
        oc = pl.read_csv(f"{BAK}/{sub}calibration.csv")
        nc = pl.read_csv(f"{REF}/{sub}calibration.csv").filter(pl.col("target_kind").is_in(["level", "response"]))
        recs.append(cmp(oc, nc, ["quantity", "target_kind"], f"{sub}calibration.csv"))
        if sub:
            recs.append(cmp(pl.read_parquet(f"{BAK}/{sub}mask.parquet"), pl.read_parquet(f"{REF}/{sub}mask.parquet"),
                            ["gcm", "scen", "window", "quantity", "Cell"], f"{sub}mask.parquet"))
    for null in ["null_a_other_seed", "null_b_persistence", "null_d_equilibrium", "null_e_germany_mean"]:
        for sub in ["", "block/"]:
            o = pl.read_csv(f"{BAK}/scores/{null}/{sub}summary_conjunctive.csv")
            n = pl.read_csv(f"{REF}/scores/{null}/{sub}summary_conjunctive.csv", infer_schema_length=None)
            if null == "null_a_other_seed":
                # round-1 defect (fixed by SH14): null (a)'s ceiling_* were read from its OWN previous output, i.e.
                # one rebuild stale. Compare its own fractions, and require ceiling_* == own fractions now.
                own = ["all_pass_frac", "all_pass_cell_frac", "all_pass_q90_frac", "all_pass_cal_frac"]
                o = o.drop([f"ceiling_{c}" for c in own], strict=False)
                selfd = n.select([(pl.col(c) - pl.col(f"ceiling_{c}")).abs().max().alias(c) for c in own]).row(0)
                recs.append({"name": f"{null}/{sub}ceiling_equals_own", "rows_old": n.height,
                             "rows_new_total": n.height, "diffs": {"max_abs": max(selfd)}, "ok": max(selfd) == 0.0})
            recs.append(cmp(o, n, ["gcm", "scen", "window", "panel"], f"{null}/{sub}summary_conjunctive"))
            fo = f"{BAK}/scores/{null}/{sub}summary_criterion.csv"
            if os.path.exists(fo):
                o = pl.read_csv(fo)
                n = pl.read_csv(f"{REF}/scores/{null}/{sub}summary_criterion.csv", infer_schema_length=None).filter(
                    pl.col("response_target") == "r2071")
                recs.append(cmp(o, n, ["gcm", "scen", "panel"], f"{null}/{sub}summary_criterion(r2071)"))
            o = pl.read_csv(f"{BAK}/scores/{null}/{sub}summary_quantity.csv")
            n = pl.read_csv(f"{REF}/scores/{null}/{sub}summary_quantity.csv", infer_schema_length=None)
            recs.append(cmp(o, n, ["gcm", "scen", "window", "quantity"], f"{null}/{sub}summary_quantity"))
    ok = all(r["ok"] for r in recs)
    out = {"gate": "SH14 additive-only: every round-1 column identical after the rebuild", "ok": ok,
           "n_comparisons": len(recs), "failed": [r["name"] for r in recs if not r["ok"]], "comparisons": recs}
    json.dump(out, open(f"{OUTD}/sh14_gate.json", "w"), indent=1, default=str)
    for r in recs:
        print(("OK  " if r["ok"] else "FAIL"), r["name"], r["rows_old"], r["rows_new_total"],
              json.dumps(r["diffs"], default=str)[:300], flush=True)
    print("GATE", "PASS" if ok else "FAIL", flush=True)
    return 0 if ok else 5


TOLS = {"all_pass_frac": "stratum(r1)", "all_pass_cell_frac": "cell(r1,asym)", "all_pass_q90_frac": "q90(r1)",
        "all_pass_cal_frac": "cal(r1)", "all_pass_cell_abs_frac": "cell_abs(SH14)",
        "all_pass_c_frac": "stratum_c(SH14)", "all_pass_q90_c_frac": "q90_c(SH14)",
        "all_pass_cal_c_frac": "cal_c(SH14)",
        # SH14 repair: one multiplier per kind; cross-GCM fits (the replica's value is an out-of-sample ceiling)
        "all_pass_cal1_frac": "cal1(SH14r)", "all_pass_cal_xg_frac": "cal_xg(SH14r)",
        "all_pass_cal1_xg_frac": "cal1_xg(SH14r)"}
SCEN_SETS = {"all": None, "ssp370": ["ssp370"], "ssp245": ["ssp245"], "ssp126": ["ssp126"],
             "Historical": ["Historical"]}


def _agg(c: pl.DataFrame, col: str, by: list[str]) -> pl.DataFrame:
    agg = [pl.col(col).median().alias("med"), pl.col(col).min().alias("min"),
           pl.col(col).max().alias("max"), pl.len().alias("n_gcm_scen"),
           pl.col("n_cells").median().alias("n_units_med")]
    for pre, name in [("ceiling_same_", "ceiling_same_med"), ("ceiling_unbr_lo_", "ceiling_unbr_lo_med"),
                      ("ceiling_unbr_hi_", "ceiling_unbr_hi_med")]:
        if f"{pre}{col}" in c.columns:
            agg.append(pl.col(f"{pre}{col}").median().alias(name))
    return c.group_by(by).agg(agg)


def changes() -> int:
    """Null table: per (null, cell set, scale, tolerance, panel, window, scen_set) median/min/max over (gcm, scen) +
    the ceiling medians. scen_set = all (round-1 convention) or one scenario (SH14 repair: H4 contrasts must be
    read on ssp370 alone; ssp245 contrasts = scenario + binary)."""
    rows = []
    for cellset, d in [("all", f"{REF}/scores"), ("dev907", f"{REF}/scores_dev"),
                       ("fold5dev185", f"{REF}/scores_fold5dev")]:
        if not os.path.isdir(d):
            continue
        for lab in sorted(os.listdir(d)):
            if not lab.startswith("null_"):
                continue
            for scale, sub in [("cell", ""), ("block", "block/")]:
                for kind, fn in [("conj", "summary_conjunctive.csv"), ("crit", "summary_criterion.csv")]:
                    f = f"{d}/{lab}/{sub}{fn}"
                    if not os.path.exists(f):
                        continue
                    c = pl.read_csv(f, infer_schema_length=None).filter(pl.col("panel").is_in(["panel106",
                                                                                               "extended"]))
                    if kind == "crit":
                        c = c.with_columns((pl.lit("criterion_") + pl.col("response_target")).alias("window"))
                    for ssn, scens in SCEN_SETS.items():
                        cs = c if scens is None else c.filter(pl.col("scen").is_in(scens))
                        if not cs.height:
                            continue
                        for col, tn in TOLS.items():
                            if col not in cs.columns:
                                continue
                            rows.append(_agg(cs, col, ["window", "panel"]).with_columns(
                                pl.lit(lab).alias("null"), pl.lit(scale).alias("scale"),
                                pl.lit(cellset).alias("cells"), pl.lit(tn).alias("tolerance"),
                                pl.lit(ssn).alias("scen_set")))
    t = pl.concat(rows, how="diagonal_relaxed")
    for cc in ["ceiling_same_med", "ceiling_unbr_lo_med", "ceiling_unbr_hi_med"]:
        if cc not in t.columns:
            t = t.with_columns(pl.lit(None, dtype=pl.Float64).alias(cc))
    t = t.with_columns(pl.lit(R.REFSET).alias("reference_set"))
    t = t.select(["reference_set", "null", "cells", "scale", "tolerance", "panel", "window", "scen_set", "med", "min",
                  "max",
                  "n_gcm_scen", "n_units_med", "ceiling_same_med", "ceiling_unbr_lo_med", "ceiling_unbr_hi_med"]) \
        .sort(["null", "cells", "scale", "tolerance", "panel", "window", "scen_set"])
    t.write_csv(f"{OUTD}/sh14_null_table.csv")
    with pl.Config(tbl_rows=300, tbl_width_chars=220, float_precision=3, fmt_str_lengths=40):
        print(t.filter((pl.col("panel") == "panel106") & (pl.col("cells") == "all") & (pl.col("scen_set") == "all")
                       & pl.col("tolerance").is_in(["cal(r1)", "cal_xg(SH14r)", "cal1_xg(SH14r)"])
                       & pl.col("null").is_in(["null_a_other_seed", "null_a_other_seed_t2"])))
    return 0


PREREG_TOLS = ["cal(r1)", "cal1(SH14r)", "cal_xg(SH14r)", "cal1_xg(SH14r)", "cell_abs(SH14)", "stratum(r1)"]
PREREG_WINDOWS = ["h1985", "w2015", "r2015", "c2015", "criterion_r2015", "criterion_c2015"] if R.REFSET == "clean" \
    else ["h1985", "w2015", "w2071", "r2015", "r2071", "c2015", "c2071", "criterion_r2071", "criterion_c2071"]


def prereg() -> int:
    """sh14_prereg_null_values.csv: the null values that replace the pre-registration table. panel106 only, truth
    seed 1 and 2. Levels and r* responses: scen_set "all" (the round-1 convention). Contrasts (c*, criterion_c2071):
    scen_set "ssp370" is the H4 row; "ssp245" is reported separately and labelled scenario + binary."""
    t = pl.read_csv(f"{OUTD}/sh14_null_table.csv", infer_schema_length=None)
    isc = pl.col("window").str.starts_with("c") | pl.col("window").str.starts_with("criterion_c")
    p = t.filter((pl.col("panel") == "panel106") & pl.col("tolerance").is_in(PREREG_TOLS)
                 & pl.col("window").is_in(PREREG_WINDOWS)
                 & ((~isc & (pl.col("scen_set") == "all")) | (isc & pl.col("scen_set").is_in(["ssp370", "ssp245"]))))
    p = p.with_columns(
        pl.when(isc & (pl.col("scen_set") == "ssp370") & pl.col("window").str.ends_with(R.PRIMARY_CONTRAST))
        .then(pl.lit(f"PRIMARY response {R.PRIMARY_CONTRAST} (ssp370 only)"))
        .when(isc & (pl.col("scen_set") == "ssp370")).then(pl.lit("H4 contrast (ssp370 only)"))
        .when(isc).then(pl.lit("NOT for H4: ssp245 = scenario + binary change"))
        .otherwise(pl.lit("")).alias("use"),
        pl.when(pl.col("tolerance").str.contains("_xg")).then(pl.lit("out-of-sample for the replica (k fitted on the "
                                                                     "other GCM)"))
        .when(pl.col("tolerance").str.starts_with("cal")).then(pl.lit("IN-SAMPLE for the replica: its value is an "
                                                                      "upper bound on what an equally good run gets"))
        .when(pl.col("tolerance").str.starts_with("cell_abs")).then(pl.lit("replica passes by construction"))
        .otherwise(pl.lit("")).alias("replica_note"))
    p = p.sort(["cells", "scale", "window", "scen_set", "tolerance", "null"])
    p.write_csv(f"{OUTD}/sh14_prereg_null_values.csv")
    with pl.Config(tbl_rows=400, tbl_width_chars=250, float_precision=3, fmt_str_lengths=30):
        print(p.filter((pl.col("tolerance").is_in(["cal(r1)", "cal_xg(SH14r)", "cal1_xg(SH14r)"]))
                       & (pl.col("cells") == "dev907") & (pl.col("scale") == "block")
                       & ~pl.col("null").str.ends_with("_t2")).select(
            ["window", "scen_set", "tolerance", "null", "med", "ceiling_same_med", "ceiling_unbr_lo_med",
             "ceiling_unbr_hi_med"]).sort(["window", "scen_set", "tolerance", "null"]))
    return 0


# ---------------------------------------------------------------------------------------------------------
# OWNER DECISION 2026-10-01: the clean (1985-2044) reference set
# ---------------------------------------------------------------------------------------------------------
NONCAL = ["C", "R", "scale", "dens", "stratum", "spread_cell", "s_med", "s_q90", "s_n", "stratum_own", "tol_source",
          "allowed", "allowed_q90", "allowed_cell", "sn_cell", "spread_cell_c", "s_med_c", "s_q90_c",
          "allowed_cell_abs", "allowed_c", "allowed_q90_c", "dev_unbr_lo", "dev_unbr_hi"]
CAL = ["allowed_cal", "allowed_cal_c", "allowed_cal1", "allowed_cal_xg", "allowed_cal1_xg"]


def gate_clean() -> int:
    assert R.REFSET == "clean", "gate_clean runs on the clean reference set"
    recs = []
    clean_w = list(R.WINDOWS)
    lc = pl.read_parquet(f"{REF}/levels_long.parquet")
    lf = pl.scan_parquet(f"{FULL}/levels_long.parquet").filter(pl.col("window").is_in(clean_w)).collect()
    recs.append(cmp(lf, lc, ["gcm", "scen", "seed", "window", "Cell", "quantity"],
                    "levels_long clean == full[1985-2044]"))
    recs[-1]["ok"] = recs[-1]["ok"] and lc.height == lf.height
    excl = {}
    calrows = []
    for sub in ["", "block/", "block_dev/"]:
        for sfx in ["", "_t2"]:
            tc = pl.read_parquet(f"{REF}/{sub}tolerance{sfx}.parquet")
            excl[f"{sub}tolerance{sfx}"] = sorted(set(tc["window"].unique().to_list()) & set(R.EXCLUDED_TARGETS))
            tf = pl.scan_parquet(f"{FULL}/{sub}tolerance{sfx}.parquet").filter(
                pl.col("window").is_in(tc["window"].unique().to_list())).collect()
            keep = [c for c in NONCAL if c in tf.columns]
            r = cmp(tf.select(K + keep), tc.select(K + keep), K, f"{sub}tolerance{sfx} non-calibrated columns")
            r["ok"] = r["ok"] and tc.height == tf.height
            recs.append(r)
            if sub:
                mc = pl.read_parquet(f"{REF}/{sub}mask{sfx}.parquet")
                mf = pl.scan_parquet(f"{FULL}/{sub}mask{sfx}.parquet").filter(
                    pl.col("window").is_in(clean_w)).collect()
                r = cmp(mf, mc, ["gcm", "scen", "window", "quantity", "Cell"], f"{sub}mask{sfx}")
                r["ok"] = r["ok"] and mc.height == mf.height
                recs.append(r)
            # calibration: how much the 1985-2044-only fit moved each tolerance (informational, not gated)
            j = tc.select(K + ["target_kind"] + CAL).join(tf.select(K + CAL), on=K, suffix="_full")
            for c in CAL:
                calrows.append(j.group_by(["target_kind"]).agg(
                    (pl.col(c) / pl.col(f"{c}_full")).filter(pl.col(f"{c}_full") > 0).median().alias("ratio_med"),
                    (pl.col(c) / pl.col(f"{c}_full")).filter(pl.col(f"{c}_full") > 0).quantile(0.05)
                    .alias("ratio_q05"),
                    (pl.col(c) / pl.col(f"{c}_full")).filter(pl.col(f"{c}_full") > 0).quantile(0.95)
                    .alias("ratio_q95")).with_columns(
                    pl.lit(f"{sub or 'cell/'}{sfx or '_t1'}").alias("table"), pl.lit(c).alias("column")))
    recs.append({"name": "no excluded target in any clean tolerance table", "rows_old": 0, "rows_new_total": 0,
                 "diffs": excl, "ok": not any(excl.values())})
    lvw = sorted(set(lc["window"].unique().to_list()))
    recs.append({"name": "clean levels_long windows", "rows_old": 0, "rows_new_total": lc.height,
                 "diffs": {"windows": lvw}, "ok": lvw == sorted(clean_w)})
    cal = pl.concat(calrows).sort(["table", "column", "target_kind"])
    cal.write_csv(f"{OUTD}/sh14_clean_calibration_vs_full.csv")
    ok = all(r["ok"] for r in recs)
    out = {"gate": "clean reference set (owner decision 2026-10-01): no excluded target; levels and every "
                   "non-calibrated tolerance column identical to the full set on 1985-2044", "ok": ok,
           "n_comparisons": len(recs), "failed": [r["name"] for r in recs if not r["ok"]], "comparisons": recs,
           "calibration_ratio_clean_over_full": cal.to_dicts()}
    json.dump(out, open(f"{OUTD}/sh14_clean_gate.json", "w"), indent=1, default=str)
    for r in recs:
        print(("OK  " if r["ok"] else "FAIL"), r["name"], r["rows_old"], r["rows_new_total"],
              json.dumps(r["diffs"], default=str)[:300], flush=True)
    with pl.Config(tbl_rows=200, tbl_width_chars=200, float_precision=3):
        print(cal)
    print("GATE_CLEAN", "PASS" if ok else "FAIL", flush=True)
    return 0 if ok else 6


NULL_SN_MED = 0.5
NULL_GT1 = 1 - 2 / 3.141592653589793 * 1.1071487177940904  # 1 - (2/pi) atan(2)
NULL_GE3 = 1 - 2 / 3.141592653589793 * 1.4056476493802699  # 1 - (2/pi) atan(6)


def _null_check() -> dict:
    """Monte-Carlo check of the analytic pure-noise reference (1e6 exchangeable Gaussian seed pairs, no signal)."""
    import numpy as np
    rng = np.random.default_rng(20261001)
    c, r = rng.standard_normal(1_000_000), rng.standard_normal(1_000_000)
    sn = np.abs((c + r) / 2) / np.abs(c - r)
    return {"mc_sn_med": float(np.median(sn)), "mc_gt1": float((sn > 1).mean()), "mc_ge3": float((sn >= 3).mean()),
            "mc_sign_agree": float((c * r > 0).mean()), "analytic_gt1": NULL_GT1, "analytic_ge3": NULL_GE3}


def snr() -> int:
    """Signal-to-noise of each 1985-2044 response statistic: per unit (cell or block), signal = |mean over the two
    seeds of the response| = |(C + R)/2|, noise = |C - R| (the two-seed spread of that same response). Reported per
    (scale, truth seed 1, gcm, scen, target, quantity): n units, median S/N, fraction of units with S/N > 1
    (|response| exceeds the two-seed noise) and >= 3 (determined), and the fraction where the two seeds agree on the
    sign; then the Germany-wide and tercile aggregates from aggregate.parquet. [MEASURED on the original model
    only.] r2015 = w2015 - h1985 (contains the 1985->2020 CO2 rise); c2015 = ssp370|ssp245 - ssp126 in 2015-2044."""
    rows = []
    tg = list(R.RESPONSES) + list(R.CONTRASTS)
    for scale, f in [("cell", f"{REF}/tolerance.parquet"), ("block", f"{REF}/block/tolerance.parquet"),
                     ("block_dev", f"{REF}/block_dev/tolerance.parquet")]:
        t = pl.scan_parquet(f).filter(pl.col("window").is_in(tg) & pl.col("R").is_not_null()).select(
            ["gcm", "scen", "window", "Cell", "quantity", "C", "R"]).collect()
        sig, noi = ((pl.col("C") + pl.col("R")) / 2).abs(), (pl.col("C") - pl.col("R")).abs()
        t = t.with_columns(sig.alias("sig"), noi.alias("noise"),
                           pl.when(noi > 0).then(sig / noi).when(sig > 0).then(float("inf")).otherwise(None)
                           .alias("sn"))
        a = t.group_by(["gcm", "scen", "window", "quantity"]).agg(
            pl.len().alias("n_units"), pl.col("sn").median().alias("sn_med"),
            (pl.col("sn") > 1).mean().alias("frac_sn_gt1"), (pl.col("sn") >= 3).mean().alias("frac_sn_ge3"),
            ((pl.col("C") * pl.col("R")) > 0).mean().alias("frac_seed_sign_agree"),
            pl.col("sig").median().alias("signal_med"), pl.col("noise").median().alias("noise_med"))
        rows.append(a.with_columns(pl.lit(scale).alias("scale")))
    ag = pl.read_parquet(f"{REF}/aggregate.parquet").filter(pl.col("window").is_in(tg))
    for reg in [R.REGION_ALL, "south", "central", "north"]:
        x = ag.filter(pl.col("region") == reg).select(
            ["gcm", "scen", "window", "quantity", pl.lit(1).cast(pl.UInt32).alias("n_units"),
             pl.col("sn").alias("sn_med"), (pl.col("sn") > 1).cast(pl.Float64).alias("frac_sn_gt1"),
             (pl.col("sn") >= 3).cast(pl.Float64).alias("frac_sn_ge3"),
             ((pl.col("aggC") * pl.col("aggR")) > 0).cast(pl.Float64).alias("frac_seed_sign_agree"),
             ((pl.col("aggC") + pl.col("aggR")) / 2).abs().alias("signal_med"),
             pl.col("noise").alias("noise_med")])
        rows.append(x.with_columns(pl.lit(f"aggregate_{reg}").alias("scale")))
    out = pl.concat(rows, how="vertical_relaxed").with_columns(
        pl.lit(NULL_SN_MED).alias("null_sn_med"), pl.lit(NULL_GT1).alias("null_frac_sn_gt1"),
        pl.lit(NULL_GE3).alias("null_frac_sn_ge3"), pl.lit(0.5).alias("null_frac_sign_agree"),
        ((pl.col("frac_sn_gt1") - NULL_GT1) / (NULL_GT1 * (1 - NULL_GT1) / pl.col("n_units")).sqrt())
        .alias("z_gt1_vs_null"),
    ).with_columns(
        pl.when(pl.col("scale").str.starts_with("aggregate")).then(pl.lit("one draw per GCM: no distribution"))
        .when(pl.col("z_gt1_vs_null") < 2).then(pl.lit("indistinguishable from zero signal"))
        .when(pl.col("frac_sn_gt1") < 0.5).then(pl.lit("above pure noise but not determined in most units"))
        .otherwise(pl.lit("determined in most units")).alias("verdict"),
    ).with_columns(
        pl.when(pl.col("window").str.starts_with("c") & (pl.col("scen") == "ssp370")).then(pl.lit("PRIMARY"))
        .when(pl.col("scen") == "ssp245").then(pl.lit("scenario + binary"))
        .otherwise(pl.lit("")).alias("note"),
        pl.lit(R.REFSET).alias("reference_set")).sort(["scale", "window", "scen", "gcm", "quantity"])
    out.write_csv(f"{OUTD}/sh14_clean_snr.csv")
    # compact view: median over gcm of each quantity, panel quantities of interest
    qs = ["n_per_patch", "agb_stand", "SLA_q50", "Wooddens_q50", "D95max_q50", "minwscal_q50", "Height_q50",
          "agb_q50", "share_3"]
    v = out.filter(pl.col("quantity").is_in(qs)).group_by(["scale", "window", "scen", "quantity"]).agg(
        pl.col("sn_med").median(), pl.col("frac_sn_gt1").median(), pl.col("frac_sn_ge3").median(),
        pl.col("frac_seed_sign_agree").median(), pl.col("n_units").max(), pl.col("z_gt1_vs_null").median(),
        pl.col("verdict").mode().first().alias("verdict_mode")).with_columns(
        pl.lit(NULL_SN_MED).alias("null_sn_med"), pl.lit(NULL_GT1).alias("null_frac_sn_gt1"),
        pl.lit(NULL_GE3).alias("null_frac_sn_ge3"), pl.lit(0.5).alias("null_frac_sign_agree")).sort(
        ["scale", "window", "scen", "quantity"])
    v.write_csv(f"{OUTD}/sh14_clean_snr_compact.csv")
    # panel106 summary per (scale, target, scen): how many of the 31 quantities are determined in most units
    p = out.filter(pl.col("quantity").is_in(R.PANEL106)).group_by(["scale", "window", "scen"]).agg(
        pl.col("frac_sn_gt1").median().alias("panel106_med_frac_units_sn_gt1"),
        pl.col("frac_sn_ge3").median().alias("panel106_med_frac_units_sn_ge3"),
        (pl.col("frac_sn_gt1") > 0.5).mean().alias("panel106_frac_quantity_gcm_with_majority_sn_gt1"),
        (pl.col("frac_sn_ge3") > 0.5).mean().alias("panel106_frac_quantity_gcm_with_majority_sn_ge3"),
        pl.col("sn_med").median().alias("panel106_sn_med")).sort(["scale", "window", "scen"])
    p = p.with_columns(pl.lit(NULL_GT1).alias("null_frac_units_sn_gt1"),
                       pl.lit(NULL_GE3).alias("null_frac_units_sn_ge3"), pl.lit(NULL_SN_MED).alias("null_sn_med"))
    p.write_csv(f"{OUTD}/sh14_clean_snr_panel.csv")
    nc = _null_check()
    json.dump(nc, open(f"{OUTD}/sh14_snr_null_check.json", "w"), indent=1)
    print("pure-noise reference (analytic vs Monte Carlo):", nc, flush=True)
    with pl.Config(tbl_rows=400, tbl_width_chars=220, float_precision=3):
        print(p)
        print(v.filter(pl.col("scale").is_in(["cell", "block", "block_dev", f"aggregate_{R.REGION_ALL}"])))
    return 0


CEIL_COLS = ["all_pass_cal_frac", "all_pass_cal_xg_frac", "all_pass_cal1_xg_frac"]


def ceilings() -> int:
    """Per-window replica ceilings: null (a)'s own panel106 conjunctive pass (it IS the replica) per (cells, scale,
    truth seed, gcm, scen, window), with the unbranched bracket for contrasts and the member role."""
    rows = []
    for cellset, d in [("all", f"{REF}/scores"), ("dev907", f"{REF}/scores_dev")]:
        for ts, sfx in [(1, ""), (2, "_t2")]:
            for scale, sub in [("cell", ""), ("block", "block/")]:
                f = f"{d}/null_a_other_seed{sfx}/{sub}summary_conjunctive.csv"
                if not os.path.exists(f):
                    continue
                c = pl.read_csv(f, infer_schema_length=None).filter(pl.col("panel") == "panel106")
                keep = ["gcm", "scen", "window", "n_cells"] + CEIL_COLS + [
                    x for x in c.columns if x.startswith("ceiling_unbr_") and any(x.endswith(y) for y in CEIL_COLS)] \
                    + [x for x in ["role", "held_out"] if x in c.columns]
                rows.append(c.select(keep).with_columns(pl.lit(cellset).alias("cells"), pl.lit(ts).alias("truth_seed"),
                                                        pl.lit(scale).alias("scale")))
    t = pl.concat(rows, how="diagonal_relaxed").sort(["cells", "scale", "truth_seed", "window", "gcm", "scen"])
    t.write_csv(f"{OUTD}/sh14_ceiling_per_window.csv")
    with pl.Config(tbl_rows=300, tbl_cols=12, tbl_width_chars=220, float_precision=3):
        print(t.filter(pl.col("window").is_in(["h1985", "w2015"]) & (pl.col("truth_seed") == 1)).select(
            ["cells", "scale", "window", "gcm", "scen", "n_cells"] + CEIL_COLS))
    return 0


def primary() -> int:
    """The PRIMARY gate as each null scores it (nulls_primary_gate*.csv written by the scorer's nulls command)."""
    rows = []
    for cellset, d in [("all", f"{REF}/scores"), ("dev907", f"{REF}/scores_dev"),
                       ("fold5dev185", f"{REF}/scores_fold5dev")]:
        for ts, sfx in [(1, ""), (2, "_t2")]:
            f = f"{d}/nulls_primary_gate{sfx}.csv"
            if os.path.exists(f):
                rows.append(pl.read_csv(f, infer_schema_length=None).with_columns(
                    pl.lit(cellset).alias("cells"), pl.lit(ts).alias("truth_seed")))
    t = pl.concat(rows, how="diagonal_relaxed").sort(["cells", "scale", "truth_seed", "null", "gcm"])
    t.write_csv(f"{OUTD}/sh14_primary_gate_nulls.csv")
    with pl.Config(tbl_rows=300, tbl_cols=14, tbl_width_chars=250, float_precision=3, fmt_str_lengths=40):
        print(t.filter(pl.col("scale") == "block").select(
            ["cells", "truth_seed", "null", "gcm", "role", "arm_cal_xg", "ceiling_same_cal_xg", "ratio_cal_xg",
             "arm_cal", "ceiling_same_cal", "ceiling_unbr_lo_cal_xg", "ceiling_unbr_hi_cal_xg", "verdict"]))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "gate"
    sys.exit({"gate": gate, "changes": changes, "prereg": prereg, "gate_clean": gate_clean, "snr": snr,
              "ceilings": ceilings, "primary": primary}[cmd]())
