#!/usr/bin/env python3
"""Score the ADR-0108 moisture arm against ADR 0106's criterion: per-cell trait medians AND the RESPONSE.

WHAT THIS ANSWERS, and why the existing tooling does not
-------------------------------------------------------
ADR 0106's acceptance criterion has three parts, and the shipped figure set covers only the first:

  (1) per-cell trait medians within 10 % of the original model — `plot_slow_emulator_validation.py` does this,
      but per SCENARIO and one generation at a time, and it needs the count-side `preds_oos.f64` to run at all;
  (2) the same in BOTH scenarios;
  (3) **the response between them** — "especially under climate change". Nothing measured this per cell.

(3) is the binding constraint, and it has a single clean statistic. For each cell and axis take the OOS
predicted median and the observed (C-truth) median in each scenario, then the per-cell RESPONSE

    D_truth = median_obs(ssp370) - median_obs(historic)      D_pred = median_pred(ssp370) - median_pred(historic)

and regress `D_pred` on `D_truth` through the origin. The slope IS the answer to "is a response channel open?":

    slope ~ 0   the emulator does not respond where the original does  (a CLOSED channel)
    slope ~ 1   it responds by the right amount
    slope < 0   it responds the wrong way

A per-cell *level* score cannot see this: an emulator can be within 10 % of the median in both scenarios and
still have `D_pred == 0` in every cell, because the two scenarios' cells are scored independently.

PAIRED BY CONSTRUCTION. The two arms (`_env` static tail, `_envT` transient tail) are appended to ONE frozen
base table, share `cells.i64` / `scenario.i64` / `years.i64` / `Y_*.f64` by symlink, and are evaluated on
identical `Cell`-hash folds — so every number below is a paired comparison over the same cells, and any
difference is attributable to the tail's time basis and nothing else (ADR 0108 §4).

CAVEATS THIS PRINTS RATHER THAN HIDES
  * `Y_*` here is FIT's SURVIVOR marginal on the STEM_CAP subsample (a patch-year cluster subsample, ADR
    0026) — a per-cell median is well estimated by it, a tail quantile less so. `stem_cap` is printed.
  * A relative error is undefined where the truth's response is ~0, so the 10 %-band count is reported over
    the cells whose |D_truth| exceeds a stated floor, WITH the excluded count. ADR 0106's stated tolerance is
    max(10 %, the original's own two-run spread); the two-run spread is NOT available per cell here, so this
    reports the 10 % part and says so — it is a screen, not the acceptance verdict.
  * Only cells present in BOTH scenarios can have a response; the intersection size is printed.

Usage (SLURM):
    ARMS=/p/tmp/.../slow_copula_pooled_w20_t9env,/p/tmp/.../slow_copula_pooled_w20_t9envT \
    LABELS=static,transient \
      scripts/sbatch_python.sh S-armresp scripts/diagnose_moisture_arm_response.py
Env: ARMS (comma list of table dirs, required), LABELS (comma list aligned to ARMS; default the dir basenames),
     AXES (default the manifest's production axes), MIN_CELL_STEMS (30), RESP_FLOOR_FRAC (0.02 = the |D_truth|
     floor as a fraction of the axis's own cross-cell spread), OUT_CSV (per-cell table; default none).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import polars as pl

ARMS = [a.strip() for a in os.environ.get("ARMS", "").split(",") if a.strip()]
LABELS = [c.strip() for c in os.environ.get("LABELS", "").split(",") if c.strip()]
AXES_ENV = [a.strip() for a in os.environ.get("AXES", "").split(",") if a.strip()]
MIN_CELL_STEMS = int(os.environ.get("MIN_CELL_STEMS", "30"))
RESP_FLOOR_FRAC = float(os.environ.get("RESP_FLOOR_FRAC", "0.02"))
OUT_CSV = os.environ.get("OUT_CSV", "").strip()


def read_manifest(d: Path) -> dict:
    m = {}
    for ln in (d / "manifest_copula.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            m[k] = v
    return m


def per_cell_medians(cells, scen, vals, min_stems):
    """-> polars frame Cell, s0_med, s1_med, s0_n, s1_n for cells with >= min_stems in BOTH scenarios."""
    df = pl.DataFrame({"Cell": cells, "s": scen, "v": vals})
    g = (df.group_by(["Cell", "s"])
         .agg(pl.col("v").median().alias("med"), pl.len().alias("n"))
         .pivot(on="s", index="Cell", values=["med", "n"]))
    # polars names the pivoted columns med_0/med_1/n_0/n_1 (or med_s_0 depending on version) — resolve by suffix
    cols = g.columns
    def pick(prefix, s):
        cand = [c for c in cols if c.startswith(prefix) and c.rstrip().endswith(str(s))]
        if len(cand) != 1:
            raise SystemExit(f"FATAL: cannot resolve pivoted column {prefix}*{s} from {cols}")
        return cand[0]
    g = g.rename({pick("med", 0): "med_h", pick("med", 1): "med_s",
                  pick("n", 0): "n_h", pick("n", 1): "n_s"})
    g = g.drop_nulls(["med_h", "med_s"]).filter(
        (pl.col("n_h") >= min_stems) & (pl.col("n_s") >= min_stems)
    )
    return g.select(["Cell", "med_h", "med_s", "n_h", "n_s"]).sort("Cell")


def main() -> int:
    if len(ARMS) < 1:
        raise SystemExit("FATAL: ARMS must name at least one copula table dir.")
    labels = LABELS if len(LABELS) == len(ARMS) else [Path(a).name for a in ARMS]

    mans = [read_manifest(Path(a)) for a in ARMS]
    axes = AXES_ENV or mans[0]["axes"].split()
    print("=" * 100)
    print("ADR-0108 moisture arm vs ADR-0106's criterion — per-cell trait MEDIANS and the RESPONSE")
    print("=" * 100)
    for lab, a, m in zip(labels, ARMS, mans, strict=True):
        print(f"   {lab:10s} {a}")
        print(f"              n={int(m['n']):,}  ncond={m['ncond']}  env_basis={m.get('env_basis', '(none)')}"
              f"  stem_cap={m.get('stem_cap', '?')}  cells={m.get('ncells', '?')}")
    print(f"   axes={axes}  MIN_CELL_STEMS={MIN_CELL_STEMS}  RESP_FLOOR_FRAC={RESP_FLOOR_FRAC}")
    # THE PAIRING IS A CLAIM — check it rather than assume it. Different cells.i64/scenario.i64 bytes would
    # make every "static vs transient" difference below partly a row-universe difference (ADR 0033).
    base = Path(ARMS[0])
    cells = np.fromfile(base / "cells.i64", dtype="<i8")
    scen = np.fromfile(base / mans[0]["scenario_tag"], dtype="<i8")
    for a, m in zip(ARMS[1:], mans[1:], strict=True):
        if (np.fromfile(Path(a) / "cells.i64", dtype="<i8") != cells).any():
            raise SystemExit(f"FATAL: {a} has a different cells.i64 — the arms are NOT paired.")
        if (np.fromfile(Path(a) / m["scenario_tag"], dtype="<i8") != scen).any():
            raise SystemExit(f"FATAL: {a} has a different scenario.i64 — the arms are NOT paired.")
    tags = mans[0].get("pooled_scenarios", "historic ssp370").split()
    print(f"   PAIRED: identical cells.i64 + scenario.i64 across all {len(ARMS)} arms "
          f"({len(cells):,} rows; scenario 0={tags[0]}, 1={tags[1]})")

    rows = []
    for ax in axes:
        y = np.fromfile(base / f"Y_{ax}.f64", dtype="<f8")
        for a, m in zip(ARMS[1:], mans[1:], strict=True):
            if (np.fromfile(Path(a) / f"Y_{ax}.f64", dtype="<f8") != y).any():
                raise SystemExit(f"FATAL: {a} has a different Y_{ax} — the arms are NOT paired.")
        truth = per_cell_medians(cells, scen, y, MIN_CELL_STEMS)
        print(f"\n{'=' * 100}\n== axis {ax}  ({truth.height:,} cells with >= {MIN_CELL_STEMS} stems in BOTH "
              f"scenarios)\n{'=' * 100}")
        d_t = (truth["med_s"] - truth["med_h"]).to_numpy()
        spread = float(np.percentile(truth["med_h"].to_numpy(), 90) - np.percentile(truth["med_h"].to_numpy(), 10))
        floor = RESP_FLOOR_FRAC * spread
        print(f"   TRUTH response  D = median(ssp370) - median(historic):")
        print(f"      mean {d_t.mean():+.6g}   median {np.median(d_t):+.6g}   "
              f"p10 {np.percentile(d_t, 10):+.6g}   p90 {np.percentile(d_t, 90):+.6g}")
        print(f"      cross-cell spread of the historic median (p90-p10) = {spread:.6g}; "
              f"|D| floor = {floor:.6g}  ({int((np.abs(d_t) > floor).sum()):,} cells above it)")

        for lab, a in zip(labels, ARMS, strict=True):
            pf = Path(a) / f"pred_{ax}.f64"
            if not pf.exists():
                print(f"   {lab:10s} SKIP — {pf.name} absent (eval_slow_copula.jl has not finished here)")
                continue
            p = np.fromfile(pf, dtype="<f8")
            if p.shape[0] != cells.shape[0]:
                raise SystemExit(f"FATAL: {pf} has {p.shape[0]} rows, the table has {cells.shape[0]}")
            pred = per_cell_medians(cells, scen, p, MIN_CELL_STEMS)
            j = truth.join(pred, on="Cell", how="inner", suffix="_p")
            mh, ms = j["med_h"].to_numpy(), j["med_s"].to_numpy()
            ph, ps = j["med_h_p"].to_numpy(), j["med_s_p"].to_numpy()
            # (1)+(2) LEVEL: per-cell median within 10 %, per scenario
            lv = {}
            for nm, o, q in ((tags[0], mh, ph), (tags[1], ms, ps)):
                rel = np.abs(q - o) / np.maximum(np.abs(o), 1e-30)
                lv[nm] = (float(np.median(rel)), float((rel <= 0.10).mean()))
            # (3) RESPONSE: slope through the origin, sign agreement, and the 10 % band on the response
            dt, dp = ms - mh, ps - ph
            sel = np.abs(dt) > floor
            slope = float((dt[sel] @ dp[sel]) / (dt[sel] @ dt[sel])) if sel.sum() > 1 else float("nan")
            corr = float(np.corrcoef(dt[sel], dp[sel])[0, 1]) if sel.sum() > 2 else float("nan")
            signok = float((np.sign(dp[sel]) == np.sign(dt[sel])).mean()) if sel.sum() else float("nan")
            relr = np.abs(dp[sel] - dt[sel]) / np.abs(dt[sel]) if sel.sum() else np.array([])
            in10 = float((relr <= 0.10).mean()) if relr.size else float("nan")
            print(f"   {lab:10s} LEVEL  median|rel err|  {tags[0]} {lv[tags[0]][0]:.4f} "
                  f"({100 * lv[tags[0]][1]:5.1f} % of cells within 10 %)   "
                  f"{tags[1]} {lv[tags[1]][0]:.4f} ({100 * lv[tags[1]][1]:5.1f} %)")
            print(f"   {'':10s} RESPONSE slope(D_pred on D_truth) = {slope:+.4f}   corr = {corr:+.4f}   "
                  f"sign agreement {100 * signok:5.1f} %   |rel| <=10 % in {100 * in10:5.1f} % of "
                  f"{int(sel.sum()):,} cells")
            print(f"   {'':10s}          mean D_pred {dp.mean():+.6g} vs mean D_truth {dt.mean():+.6g} "
                  f"(ratio {dp.mean() / dt.mean() if dt.mean() != 0 else float('nan'):+.4f})")
            rows.append({
                "axis": ax, "arm": lab, "ncells": int(j.height),
                f"med_relerr_{tags[0]}": lv[tags[0]][0], f"within10_{tags[0]}": lv[tags[0]][1],
                f"med_relerr_{tags[1]}": lv[tags[1]][0], f"within10_{tags[1]}": lv[tags[1]][1],
                "resp_slope": slope, "resp_corr": corr, "resp_sign_ok": signok,
                "resp_within10": in10, "resp_ncells": int(sel.sum()),
                "mean_D_pred": float(dp.mean()), "mean_D_truth": float(dt.mean()),
            })

    if rows:
        summ = pl.DataFrame(rows)
        print(f"\n{'=' * 100}\n== SUMMARY (the response slope is the ADR-0106 climate-change statistic)\n"
              f"{'=' * 100}")
        with pl.Config(tbl_rows=100, tbl_width_chars=200, tbl_cols=20):
            print(summ.select(["axis", "arm", "resp_slope", "resp_corr", "resp_sign_ok", "resp_within10",
                               "mean_D_pred", "mean_D_truth"]))
        if OUT_CSV:
            summ.write_csv(OUT_CSV)
            print(f"== wrote {OUT_CSV}")
    print("\n   NOTE (ADR 0106): the 10 % bands above use the LITERAL 10 %. The stated tolerance is")
    print("   max(10 %, the original model's own two-run spread for that quantity in that cell), and the")
    print("   two-run spread is not available per cell here — so this is a SCREEN, not the acceptance verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
