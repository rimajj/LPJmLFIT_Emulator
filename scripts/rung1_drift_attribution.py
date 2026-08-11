#!/usr/bin/env python3
"""RUNG 1 — WHICH conditioning feature carries the scenario signal into the recursion's drift.

Pre-registered by ADR 0115 §6.3 (and item (i) of line S's handoff). ADR 0115 §3 measured that the
self-feeding count arm's bias is **climate-dependent**: at exactly lead 18 the historic chains sit at
+0.024 stems/patch while the ssp370 chains sit at +0.150, so the part that does NOT cancel in the scenario
difference is +0.126 — about 90 % of LPJmL-FIT's entire global count response (~ -0.14), with the opposite
sign. That asymmetry, not inaccuracy, is what eats the difference ADR 0106 is about.

This script asks the one cheap well-posed follow-up: **which of the 15 conditioning features is the channel?**
No refit, no new model run — the arm's predictions, the control's predictions, the proven (Cell, Patch, Year)
keys and the frozen feature matrix `X.f64` are all on disk.

WHAT IT COMPUTES, at each fitted lead s (default 5 / 12 / 18; 18 is the deepest lead BOTH scenarios reach):

  per cell c, over the rows at EXACTLY lead s (the same `lead_index` chain definition as
  `scripts/rung1_response_decay.py` — imported, not re-derived, so the panels stay comparable):

    drift_arm(c)  = mean(pred_arm - truth | ssp370)  -  mean(pred_arm - truth | historic)
    drift_ref(c)  = the same for the ONE-STEP control, on the SAME rows
    excess(c)     = drift_arm(c) - drift_ref(c)            <- the recursion's own scenario asymmetry
    dX_j(c)       = mean(X_j | ssp370) - mean(X_j | historic)   for each conditioning feature j

  then three attributions of `excess` on the 15 `dX_j`:

    1. **univariate** weighted Pearson r per feature — what each channel carries on its own;
    2. **standardised multiple regression** (weighted least squares on z-scored columns, so the coefficients
       ARE standardised) with a VIF beside every coefficient, because the dX_j are all driven by the same
       warming and are heavily collinear — a multiple coefficient alone would be uninterpretable;
    3. **greedy forward selection** on weighted R² — the collinearity-robust reading: which single feature
       explains most of the excess drift, and what each further feature adds.

  All three are run for `drift_ref` as well (**the control's own decomposition, printed beside the arm's**,
  ADR 0114 §5.4's rule): a feature that explains the control's scenario asymmetry just as well is a property
  of the rows, not of the recursion.

  Plus a per-latitude-band univariate table for the leading features, because the tropics invert
  (ADR 0113 §2c) and a global-only correlation would hide it.

BASIS AND LIMITS — state them wherever a number from here is quoted:
  * counts are the count table's OWN seed-1 truth in stems/patch (`y.f64`), NOT the yardstick's basis;
    never quote one of these numbers against `S_truth_yardstick_summary.csv` (ADR 0114 §5.5).
  * the regressors are **LPJmL-FIT's own** feature changes (the frozen `X.f64`), not the arm's recursed
    state. That is deliberate: the question is which climate/state channel the scenario signal enters
    through, and FIT's own change is the exogenous version of it. `n_prev`'s dX is therefore FIT's
    previous-year count change, not the arm's.
  * `co2` is constant by construction (ADR 0107) and `soil_depth` is a per-cell constant, so both have
    dX == 0 and are dropped automatically; the printed table says which columns were dropped.
  * this is an ASSOCIATION over cells. It names the channel that carries the signal; it does not prove a
    mechanism, and with collinear regressors the forward-selection path is the honest reading.

Usage (SLURM; EXPORT every knob — sbatch_python.sh forwards only a fixed list, CLAUDE.md §9):
    export ARM=/p/tmp/jamirp/emulator_global/rung1_count_arm_a1
    export REF=/p/tmp/jamirp/emulator_global/slow_count_pooled_w20_t8
    export KEYS=/p/tmp/jamirp/emulator_global/rung1_keys_t8
    export OUT=/p/tmp/jamirp/emulator_global/rung1_drift_attribution.csv
    NCPUS=24 TIME=01:00:00 scripts/sbatch_python.sh S-driftattr scripts/rung1_drift_attribution.py
Env: ARM, REF (the one-step control), KEYS, SRC (feature dir holding X.f64 + colnames; defaults to REF),
     OUT (CSV), FIT_LEADS (default "5,12,18"), MIN_CELLS (2000), TOPK (5), CHUNK (4000000).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
# the SAME chain/lead definition and the SAME area weights as the decay panel (ADR 0115 §6.3 requires it,
# or this table is not comparable to ADR 0115 §3)
from rung1_response_decay import LAT_BANDS, lead_index, load_latlon  # noqa: E402

BASE = "/p/tmp/jamirp/emulator_global"
ARM = Path(os.environ.get("ARM", f"{BASE}/rung1_count_arm_a1"))
REF = Path(os.environ.get("REF", f"{BASE}/slow_count_pooled_w20_t8"))
KEYS = Path(os.environ.get("KEYS", f"{BASE}/rung1_keys_t8"))
SRC = Path(os.environ.get("SRC", str(REF)))
OUT = Path(os.environ.get("OUT", f"{BASE}/rung1_drift_attribution.csv"))
FIT_LEADS = [int(s) for s in os.environ.get("FIT_LEADS", "5,12,18").split(",")]
MIN_CELLS = int(os.environ.get("MIN_CELLS", "2000"))
TOPK = int(os.environ.get("TOPK", "5"))
CHUNK = int(os.environ.get("CHUNK", "4000000"))

ROWS: list[dict] = []


def read_manifest(d: Path) -> dict[str, str]:
    man: dict[str, str] = {}
    for ln in (d / "manifest.txt").read_text().splitlines():
        if "\t" in ln:
            k, v = ln.split("\t", 1)
            man[k] = v
    return man


def gather_rows(path: Path, n: int, p: int, mask: np.ndarray) -> np.ndarray:
    """Rows of the (n, p) float64 matrix at `mask`, read as CONTIGUOUS chunks.

    `X.f64` is 14.6 GB and the mask selects a few million scattered rows; fancy-indexing a memmap turns that
    into millions of random reads on Lustre. A chunked sequential pass costs one streaming read of the file.
    """
    X = np.memmap(path, dtype="<f8", mode="r", shape=(n, p))
    out = np.empty((int(mask.sum()), p), dtype=np.float64)
    at = 0
    for a in range(0, n, CHUNK):
        b = min(a + CHUNK, n)
        mk = mask[a:b]
        k = int(mk.sum())
        if k:
            out[at:at + k] = np.asarray(X[a:b])[mk]
            at += k
    if at != out.shape[0]:
        raise SystemExit(f"FATAL: gathered {at} rows, expected {out.shape[0]}")
    return out


def wstats(x: np.ndarray, w: np.ndarray) -> tuple[float, float]:
    m = float((w * x).sum() / w.sum())
    v = float((w * (x - m) ** 2).sum() / w.sum())
    return m, float(np.sqrt(max(v, 0.0)))


def zscore(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    m, s = wstats(x, w)
    return (x - m) / s if s > 0 else np.zeros_like(x)


def wls_r2(Z: np.ndarray, zy: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, float]:
    """Weighted LS of z-scored `zy` on z-scored columns `Z` (no intercept — both are weighted-centred).

    Returns (standardised coefficients, weighted R^2).
    """
    sw = np.sqrt(w)[:, None]
    beta, *_ = np.linalg.lstsq(Z * sw, zy * np.sqrt(w), rcond=None)
    resid = zy - Z @ beta
    sse = float((w * resid ** 2).sum())
    sst = float((w * zy ** 2).sum())
    return beta, 1.0 - sse / sst if sst > 0 else np.nan


def vifs(Z: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Variance-inflation factor per column: 1/(1 - R^2) of that column on all the others."""
    out = np.empty(Z.shape[1])
    for j in range(Z.shape[1]):
        others = np.delete(Z, j, axis=1)
        _, r2 = wls_r2(others, Z[:, j], w)
        out[j] = 1.0 / max(1.0 - r2, 1e-12) if np.isfinite(r2) else np.nan
    return out


def wcorr(x: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    mx, sx = wstats(x, w)
    my, sy = wstats(y, w)
    if sx <= 0 or sy <= 0:
        return np.nan
    return float((w * (x - mx) * (y - my)).sum() / w.sum() / (sx * sy))


def forward_select(Z: np.ndarray, zy: np.ndarray, w: np.ndarray, names: list[str],
                   steps: int) -> list[tuple[str, float]]:
    chosen: list[int] = []
    path: list[tuple[str, float]] = []
    for _ in range(min(steps, Z.shape[1])):
        best, best_r2 = -1, -np.inf
        for j in range(Z.shape[1]):
            if j in chosen:
                continue
            _, r2 = wls_r2(Z[:, chosen + [j]], zy, w)
            if np.isfinite(r2) and r2 > best_r2:
                best, best_r2 = j, r2
        if best < 0:
            break
        chosen.append(best)
        path.append((names[best], best_r2))
    return path


def main() -> int:
    man_arm = read_manifest(ARM)
    man_src = read_manifest(SRC)
    n, p = int(man_src["n"]), int(man_src["p"])
    cols = man_src["colnames"].split()
    if len(cols) != p:
        raise SystemExit(f"FATAL: {len(cols)} colnames but p={p}")
    if int(man_arm["n"]) != n:
        raise SystemExit(f"FATAL: arm n={man_arm['n']} != feature n={n}")

    cells = np.fromfile(ARM / "cells.i64", dtype="<i8")
    scen = np.fromfile(ARM / man_arm.get("scenario_tag", "scenario.i64"), dtype="<i8")
    y = np.fromfile(ARM / "y.f64", dtype="<f8")
    pa = np.fromfile(ARM / "preds_oos.f64", dtype="<f8")
    pr = np.fromfile(REF / "preds_oos.f64", dtype="<f8")
    years = np.fromfile(KEYS / "years.i64", dtype="<i8")
    patches = np.fromfile(KEYS / "patches.i64", dtype="<i8")
    for nm, arr in [("cells", cells), ("scen", scen), ("y", y), ("arm", pa), ("ref", pr),
                    ("years", years), ("patches", patches)]:
        if arr.size != n:
            raise SystemExit(f"FATAL: {nm} has {arr.size} rows, expected {n}")

    print(f"== ARM={ARM.name}  REF={REF.name}  SRC={SRC.name}  n={n:,}  p={p}")
    lead = lead_index(scen, cells, patches, years)
    ok = (years >= 0) & np.isfinite(pa) & np.isfinite(pr)
    sel = ok & np.isin(lead, FIT_LEADS)
    print(f"== fitted leads {FIT_LEADS}: {int(sel.sum()):,} rows selected of {int(ok.sum()):,} usable")

    print(f"== streaming {SRC / 'X.f64'} ({n * p * 8 / 1e9:.1f} GB) in {CHUNK:,}-row chunks ...",
          flush=True)
    Xs = gather_rows(SRC / "X.f64", n, p, sel)
    print(f"== gathered {Xs.shape[0]:,} x {Xs.shape[1]} feature rows", flush=True)

    ll = load_latlon()
    df = pl.DataFrame({"Cell": cells[sel], "s": scen[sel], "lead": lead[sel].astype("int64"),
                       "y": y[sel], "b_arm": (pa[sel] - y[sel]), "b_ref": (pr[sel] - y[sel]),
                       **{f"f_{c}": Xs[:, j] for j, c in enumerate(cols)}})
    del Xs

    # ---- reconciliation to ADR 0115 §3: the ROW-level bias by scenario at each fitted lead ------------
    print("\n--- 0. RECONCILIATION to ADR 0115 §3 (row-level mean bias, stems/patch) ---")
    print(f"{'lead':>5s} {'rows h':>11s} {'rows s370':>11s} {'ARM h':>9s} {'ARM s370':>9s} "
          f"{'ARM diff':>9s} {'REF h':>9s} {'REF s370':>9s} {'REF diff':>9s} {'excess':>9s}")
    for s in FIT_LEADS:
        d = df.filter(pl.col("lead") == s)
        h = d.filter(pl.col("s") == 0)
        q = d.filter(pl.col("s") == 1)
        ah, aq = h["b_arm"].mean(), q["b_arm"].mean()
        rh, rq = h["b_ref"].mean(), q["b_ref"].mean()
        print(f"{s:5d} {h.height:11,d} {q.height:11,d} {ah:9.4f} {aq:9.4f} {aq - ah:9.4f} "
              f"{rh:9.4f} {rq:9.4f} {rq - rh:9.4f} {(aq - ah) - (rq - rh):9.4f}")
        ROWS.append(dict(section="reconciliation", lead=s, feature=None, band="ALL",
                         n_cells=h.height + q.height, arm_bias_historic=ah, arm_bias_ssp370=aq,
                         arm_drift=aq - ah, ref_bias_historic=rh, ref_bias_ssp370=rq,
                         ref_drift=rq - rh, excess_drift=(aq - ah) - (rq - rh)))

    fcols = [f"f_{c}" for c in cols]
    for s in FIT_LEADS:
        d = df.filter(pl.col("lead") == s)
        g = d.group_by(["Cell", "s"]).agg([pl.col(c).mean() for c in ["y", "b_arm", "b_ref"] + fcols])
        h = g.filter(pl.col("s") == 0).drop("s")
        q = g.filter(pl.col("s") == 1).drop("s")
        j = h.join(q, on="Cell", how="inner", suffix="_q")
        if j.height < MIN_CELLS:
            print(f"\n[lead {s}] only {j.height} cells in BOTH scenarios — skipped (MIN_CELLS={MIN_CELLS})")
            continue
        cellv = j["Cell"].to_numpy()
        drift_arm = (j["b_arm_q"] - j["b_arm"]).to_numpy()
        drift_ref = (j["b_ref_q"] - j["b_ref"]).to_numpy()
        excess = drift_arm - drift_ref
        dy = (j["y_q"] - j["y"]).to_numpy()          # FIT's OWN per-cell count response at this lead
        dX = np.column_stack([(j[f"{c}_q"] - j[c]).to_numpy() for c in fcols])

        lat = (pl.DataFrame({"Cell": cellv}).join(ll.select(["Cell", "lat", "w"]), on="Cell", how="left"))
        w = np.nan_to_num(lat["w"].to_numpy(), nan=0.0)
        latv = lat["lat"].to_numpy()
        keep = w > 0
        cellv, drift_arm, drift_ref, excess, dy, dX, w, latv = (a[keep] for a in
                                                               (cellv, drift_arm, drift_ref, excess, dy,
                                                                dX, w, latv))

        live = [k for k in range(len(cols)) if wstats(dX[:, k], w)[1] > 0]
        dropped = [cols[k] for k in range(len(cols)) if k not in live]
        names = [cols[k] for k in live]
        Z = np.column_stack([zscore(dX[:, k], w) for k in live])

        me, sde = wstats(excess, w)
        ma, sda = wstats(drift_arm, w)
        mr, sdr = wstats(drift_ref, w)
        print(f"\n=========== LEAD {s}: {len(cellv):,} cells with rows in BOTH scenarios ===========")
        print(f"  area-weighted mean drift: ARM {ma:+.4f} (sd {sda:.4f})  REF {mr:+.4f} (sd {sdr:.4f})  "
              f"EXCESS {me:+.4f} (sd {sde:.4f})   [stems/patch]")
        print(f"  dropped (zero scenario change, by construction): {', '.join(dropped) or '(none)'}")

        z_ex, z_arm, z_ref = (zscore(v, w) for v in (excess, drift_arm, drift_ref))
        b_ex, r2_ex = wls_r2(Z, z_ex, w)
        b_arm, r2_arm = wls_r2(Z, z_arm, w)
        b_ref, r2_ref = wls_r2(Z, z_ref, w)
        vf = vifs(Z, w)
        r_ex = np.array([wcorr(dX[:, k], excess, w) for k in live])
        r_arm = np.array([wcorr(dX[:, k], drift_arm, w) for k in live])
        r_ref = np.array([wcorr(dX[:, k], drift_ref, w) for k in live])

        print("\n  --- 1+2. ATTRIBUTION of the EXCESS drift, control's own decomposition beside it ---")
        print(f"  weighted R^2:  excess {r2_ex:.4f}   arm-drift {r2_arm:.4f}   "
              f"CONTROL-drift {r2_ref:.4f}")
        print(f"  {'feature':<18s} {'r(excess)':>10s} {'beta_std':>9s} {'VIF':>7s} | "
              f"{'r(arm)':>8s} {'beta_arm':>9s} | {'r(REF)':>8s} {'beta_REF':>9s}")
        for i in np.argsort(-np.abs(r_ex)):
            print(f"  {names[i]:<18s} {r_ex[i]:+10.4f} {b_ex[i]:+9.4f} {vf[i]:7.1f} | "
                  f"{r_arm[i]:+8.4f} {b_arm[i]:+9.4f} | {r_ref[i]:+8.4f} {b_ref[i]:+9.4f}")
            ROWS.append(dict(section="attribution", lead=s, feature=names[i], band="ALL",
                             n_cells=len(cellv), r_excess=float(r_ex[i]), beta_excess=float(b_ex[i]),
                             vif=float(vf[i]), r_arm=float(r_arm[i]), beta_arm=float(b_arm[i]),
                             r_ref=float(r_ref[i]), beta_ref=float(b_ref[i]), r2_excess=r2_ex,
                             r2_arm=r2_arm, r2_ref=r2_ref,
                             mean_excess=me, mean_arm_drift=ma, mean_ref_drift=mr))

        print("\n  --- 3. GREEDY FORWARD SELECTION (weighted R^2; the collinearity-robust reading) ---")
        for tag, zt in [("excess", z_ex), ("arm", z_arm), ("REF-control", z_ref)]:
            path = forward_select(Z, zt, w, names, TOPK)
            trail = "  ->  ".join(f"{nm} ({r2:.3f})" for nm, r2 in path)
            print(f"  {tag:<12s}: {trail}")
            for rank, (nm, r2) in enumerate(path, start=1):
                ROWS.append(dict(section="forward_selection", lead=s, feature=nm, band="ALL",
                                 n_cells=len(cellv), series=tag, rank=rank, r2_cum=r2))

        print(f"\n  --- 4. TOP-{TOPK} FEATURES BY LATITUDE BAND (univariate r with the EXCESS drift) ---")
        # positions into `names`/`live` (NOT original column ids) — `dX` still carries all p columns,
        # so it is indexed with `live[i]`
        top = [int(i) for i in np.argsort(-np.abs(r_ex))[:TOPK]]
        print(f"  {'band':<12s} {'cells':>7s} {'mean excess':>12s} " +
              " ".join(f"{names[i]:>14s}" for i in top))
        for bname, lo, hi in [("GLOBAL", 0.0, 90.1)] + LAT_BANDS:
            m = (np.abs(latv) >= lo) & (np.abs(latv) < hi)
            if m.sum() < 200:
                continue
            mb, _ = wstats(excess[m], w[m])
            rs = [wcorr(dX[m, live[i]], excess[m], w[m]) for i in top]
            print(f"  {bname:<12s} {int(m.sum()):7,d} {mb:+12.4f} " +
                  " ".join(f"{r:+14.4f}" for r in rs))
            for i, r in zip(top, rs):
                ROWS.append(dict(section="band_univariate", lead=s, feature=names[i], band=bname,
                                 n_cells=int(m.sum()), r_excess=float(r), mean_excess=float(mb)))

        # ---- 5. the drift against FIT's OWN response -------------------------------------------------
        # §1-4 regress on z-scored, weighted-CENTRED columns, so they explain the drift's cross-cell
        # SPREAD and are blind to its MEAN — and the mean is what inverts the aggregate response. By
        # construction drift = (prediction response) - (truth response), so regressing the drift on the
        # cell's own truth response `dy` splits it into the part that is simply FIT's response NOT
        # REPRODUCED (slope) and a part that is independent of it (intercept).
        print("\n  --- 5. IS THE DRIFT JUST THE MISSING PART OF FIT'S OWN RESPONSE? ---")
        mdy, sdy = wstats(dy, w)
        print(f"  FIT's own area-weighted count response at this lead: {mdy:+.4f} stems/patch "
              f"(sd {sdy:.4f})")
        print(f"  {'series':<12s} {'slope on dy':>12s} {'intercept':>10s} {'r':>8s} "
              f"{'implied resp. slope':>20s} {'resid sd':>9s}")
        for tag, dr in [("arm", drift_arm), ("REF-control", drift_ref), ("excess", excess)]:
            mdr, _ = wstats(dr, w)
            cov = float((w * (dy - mdy) * (dr - mdr)).sum() / w.sum())
            slope = cov / (sdy ** 2) if sdy > 0 else np.nan
            icept = mdr - slope * mdy
            rr = wcorr(dy, dr, w)
            res = dr - (icept + slope * dy)
            _, rsd = wstats(res, w)
            # Δpred = Δtruth + drift, so the per-cell prediction-vs-truth response slope is 1 + slope.
            # ⚠ quoted here ONLY as a decomposition of the drift — ADR 0113 §3 retired the per-cell
            # response slope as a fidelity DISCRIMINATOR and that retirement is not reopened.
            print(f"  {tag:<12s} {slope:+12.4f} {icept:+10.4f} {rr:+8.4f} "
                  f"{1.0 + slope if tag != 'excess' else np.nan:20.4f} {rsd:9.4f}")
            ROWS.append(dict(section="drift_vs_truth_response", lead=s, feature="dy", band="ALL",
                             n_cells=len(cellv), series=tag, slope_on_dy=float(slope),
                             intercept=float(icept), r_excess=float(rr), resid_sd=float(rsd),
                             mean_truth_response=float(mdy), mean_drift=float(mdr)))

        print("\n  --- 5b. MEAN DRIFT BY DECILE OF FIT's OWN RESPONSE (where does the mean come from?) ---")
        print("      `level` = the cell's own mean stem count over the two scenarios; the two RELATIVE")
        print("      columns exist to separate a genuinely ONE-SIDED error from a drift that merely")
        print("      scales with stem count (declining cells being the dense ones).")
        lvl = 0.5 * (j["y"].to_numpy()[keep] + j["y_q"].to_numpy()[keep])
        qs = np.quantile(dy, np.linspace(0, 1, 11))
        qs[0], qs[-1] = -np.inf, np.inf
        print(f"  {'decile':>6s} {'cells':>7s} {'mean dy':>9s} {'level':>7s} {'ARM drift':>10s} "
              f"{'REF drift':>10s} {'excess':>9s} {'ARM/level':>10s} {'excess/level':>12s}")
        for q in range(10):
            m = (dy >= qs[q]) & (dy < qs[q + 1])
            if m.sum() < 50:
                continue
            row = [wstats(v[m], w[m])[0] for v in (dy, lvl, drift_arm, drift_ref, excess,
                                                   drift_arm / np.maximum(lvl, 1e-9),
                                                   excess / np.maximum(lvl, 1e-9))]
            print(f"  {q + 1:6d} {int(m.sum()):7,d} {row[0]:+9.4f} {row[1]:7.3f} {row[2]:+10.4f} "
                  f"{row[3]:+10.4f} {row[4]:+9.4f} {row[5]:+10.4f} {row[6]:+12.4f}")
            ROWS.append(dict(section="drift_by_response_decile", lead=s, band="ALL", feature=None,
                             n_cells=int(m.sum()), rank=q + 1, mean_truth_response=row[0],
                             mean_level=row[1], mean_arm_drift=row[2], mean_ref_drift=row[3],
                             mean_excess=row[4], arm_drift_rel=row[5], excess_rel=row[6]))

        print("\n  --- 5c. DO THE CONDITIONING FEATURES ADD ANYTHING BEYOND dy? (forced-in R^2) ---")
        zdy = zscore(dy, w)
        for tag, zt in [("excess", z_ex), ("arm", z_arm), ("REF-control", z_ref)]:
            _, r2_dy = wls_r2(zdy[:, None], zt, w)
            _, r2_all = wls_r2(np.column_stack([zdy, Z]), zt, w)
            print(f"  {tag:<12s}: R^2(dy alone) {r2_dy:.4f}  ->  R^2(dy + all 13 features) {r2_all:.4f}"
                  f"   (features add {r2_all - r2_dy:+.4f})")
            ROWS.append(dict(section="incremental_r2", lead=s, band="ALL", feature=None,
                             n_cells=len(cellv), series=tag, r2_dy_only=r2_dy, r2_dy_plus_features=r2_all,
                             r2_gain=r2_all - r2_dy))

    pl.DataFrame(ROWS, infer_schema_length=None).write_csv(OUT)
    print(f"\nwrote {len(ROWS)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
