#!/usr/bin/env python3
"""explore_glob_clock.py -- LINE X: does arm A2g (the cell-level LSTM, ADR 0315 sec. 12) read the CLIMATE or the
CALENDAR? Its climate-blind twin "responded" (tree-count slope 0.69, the full wood-density aggregate), so a recurrent
model may have learned the warming pattern as a function of elapsed years. A model that reads the calendar would
respond to a stabilised or cooling scenario as if it warmed -- disqualifying inside an Earth System Model.

Two one-variable tests, no retraining (the fold models of jobs 2445840 are loaded as they are):

  A  SCENARIO CONTRAST (truth exists, same venue). Per cell, X(ssp370, 2071-2100) - X(ssp126, 2071-2100), arm vs
     member 8, deattenuated with member 7 (ev.score with the ssp126 window in the "historical" slot). Both legs start
     from the same 2014 state and run the same number of years, so the calendar CANCELS: whatever survives is the
     climate channel. ssp370 is held out of training, ssp126 is not.
  B  NO-WARMING DRIVE (counterfactual). The lstm free-runs 2015 -> 2100 from member 8's 2014 state on the
     historical 1985-2014 climate years, shuffled per 30-yr cycle (fixed seed), the *_tr20 means recomputed from that
     series -- the same construction as the original model's constant-climate control (`fix_climate_shuffle`).
     There is no Billing truth for it. The original model's answer is taken from the track-D PANEL (1 050 cells, a
     different build and cell set -- labelled so): ctl_obs (1990-2019 weather shuffled) vs gfdl-esm4_ssp370 and
     _ssp126, members m1-m3, from the same 2019 state. Compared as a RATIO of area-weighted changes,
     R(drive) = d(drive) / d(ssp370), d = window(2071-2100) - window(first free decade of the no-warming drive).

STAGES
  predict   harness re-prediction + the drives {ssp370, ssp126, nowarm} for lstm and lstmCB -> <OUT>/<arm>_f<k>.parquet
  panel     the original model's windows on the panel -> <OUT>/panel_windows.parquet
  score     both tests -> eval/clock_contrast.csv, eval/clock_nowarm.csv

WHAT EACH MUST RETURN, written before the run (ADR 0184):
  harness-1  re-predicting ssp370/ssp126 S14 with the loaded fold models reproduces the stored f<k>_pred.parquet:
             max relative difference in stems < 1e-5. Otherwise the loader, not the arm, is being tested.
  harness-2  the trailing-20-yr mean recomputed by this script over the stored historical series equals the stored
             *_tr20 for 1985-2014 (max |diff| < 1e-3 in the column's units).
  harness-3  lstmCB's contrast A is EXACTLY 0 (frozen climate is the 1985-2014 mean whatever the scenario).
  harness-4  panel: ctl_obs and ssp370 start from the same 2019 state, so their 2020 stems agree within 2 %
             (area-weighted) in every member.
  ceiling    member 7's contrast A: deattenuated slope ~1 by construction of the deattenuation (0.8-1.2), aggregate
             0.8-1.2.
  if the lstm reads CLIMATE: contrast A aggregate and deattenuated slope in [0.7, 1.3] for stems and wood density;
             R(nowarm) close to the panel's R(ctl) (|difference| <= 0.3) for each quantity.
  if it reads the CALENDAR (the hypothesis this probe tests): contrast A for wood density ~0 (its twin already
             carried the whole wood-density aggregate, 0.96); R(nowarm) for wood density ~1 and for stems >= 0.35
             (the twin's tree-count aggregate share, 0.33 / 0.95).
  DECISION (pre-registered): quantity q is CALENDAR-DRIVEN in this arm if R_lstm(nowarm, q) - R_panel(ctl, q) > 0.3,
             or its contrast-A deattenuated slope < 0.5 where the truth contrast's noise share is < 0.5. A quantity
             whose truth contrast is noise-dominated (share >= 0.5) is reported, not read.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_reference as R  # noqa: E402
import explore_glob_eval as ev  # noqa: E402
import explore_glob_lstm as L  # noqa: E402

OUT = os.path.join(ev.EVAL, "arms", "A2g_clock")
PANEL_DIR = "/p/projects/open/Jamir/esm_land_emulator_data/trackD/panel"
PANEL_CSV = os.path.join(REPO, "test", "testitems", "references", "S_D0_panel_blocks.csv")
PANEL_LEGS = ("ctl_obs", "gfdl-esm4_ssp370", "gfdl-esm4_ssp126")
PANEL_MEMBERS = (1, 2, 3)
TR20 = {"tcold_month_tr20": "tcold_month", "twarm_month_tr20": "twarm_month", "gdd5_tr20": "gdd5"}
QS = ("n_per_patch", "agb_per_stem", "Wooddens_q50", "SLA_q50")
log = L.log


# ------------------------------------------------------------------------------------------------ climates
def nowarm_climate(cells: list[int], seed: int = 20151) -> np.ndarray:
    """(cells, T, 2F): 1985-2014 as observed, 2015-2100 = 1985-2014 years shuffled per 30-yr cycle; tr20 recomputed."""
    base = sorted(set(L.CLIM) - set(TR20) | set(TR20.values()))
    h = (
        pl.scan_parquet(os.path.join(L.CLIMD, "GFDL-ESM4_historical.parquet"))
        .filter(pl.col("Cell").is_in(cells))
        .select(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32), *[pl.col(c).cast(pl.Float64) for c in
                                                                                 sorted(set(base) | set(TR20))])
        .collect()
    )
    yh = np.arange(h["Year"].min(), L.YS + 1)
    census = pl.DataFrame({"Cell": np.repeat(cells, len(yh)).astype(np.int32),
                           "Year": np.tile(yh, len(cells)).astype(np.int32)})
    h = census.join(h, on=["Cell", "Year"], how="left").sort("Cell", "Year")
    M = {c: h[c].to_numpy().reshape(len(cells), len(yh)) for c in h.columns if c not in ("Cell", "Year")}
    rng = np.random.default_rng(seed)
    src = np.arange(L.Y0, L.YS + 1)
    pick = np.concatenate([rng.permutation(src) for _ in range(int(np.ceil((L.Y1 - L.YS) / len(src))))])[: L.Y1 - L.YS]
    years = np.concatenate([yh, np.arange(L.YS + 1, L.Y1 + 1)])
    full = {c: np.concatenate([M[c], M[c][:, pick - yh[0]]], axis=1) for c in M}

    def trailing20(A):
        cs = np.concatenate([np.zeros((A.shape[0], 1)), np.cumsum(A, axis=1)], axis=1)
        out = np.full_like(A, np.nan)
        out[:, 19:] = (cs[:, 20:] - cs[:, :-20]) / 20.0
        return out

    for k, src_c in TR20.items():
        tr = trailing20(full[src_c])
        i0, i1 = L.Y0 - yh[0], L.YS - yh[0] + 1
        err = float(np.nanmax(np.abs(tr[:, i0:i1] - M[k][:, i0:i1])))
        log(f"HARNESS-2 {k}: max |recomputed - stored| over 1985-2014 = {err:.2e} ({'PASS' if err < 1e-3 else 'FAIL'})")
        full[k] = np.concatenate([M[k], tr[:, len(yh):]], axis=1)
    sel = (years >= L.Y0)
    lev = np.stack([full[c][:, sel] for c in L.CLIM], axis=2)
    assert lev.shape[1] == L.T and np.all(np.isfinite(lev)), "no-warming climate incomplete"
    cm = lev[:, : L.I14 + 1].mean(axis=1, keepdims=True)
    log(f"no-warming years 2015-2024 drawn from: {pick[:10].tolist()}")
    return np.concatenate([lev, lev - cm], axis=2).astype(np.float32)


# ------------------------------------------------------------------------------------------------ predict
def stage_predict(a) -> None:
    import torch

    torch.set_num_threads(1)
    os.makedirs(OUT, exist_ok=True)
    folds = ev.dev_cells()
    cells = folds["Cell"].to_list()
    idx = {c: i for i, c in enumerate(cells)}
    S_all = L.static(cells)
    real = {s: L.climate(s, cells, "real") for s in ("ssp370", "ssp126")}
    froz = {s: L.climate(s, cells, "frozen") for s in ("ssp370", "ssp126")}
    nw = nowarm_climate(cells)
    X8 = {s: L.full_state(ev.TRUTH, s, cells)[0] for s in ("ssp370", "ssp126")}
    # "leaky" = the stored predictions' input: ffill over the WHOLE leg, so a variable that is missing in all of
    # 1985-2014 (no trees -> no trait quantiles) is back-filled from that leg's 2071-2100 TRUTH. "clean" masks
    # 2015-2100 before filling. Both legs share the same 1985-2014 truth.
    clean = X8["ssp370"].copy()
    clean[:, L.I14 + 1 :] = np.nan
    n_leak = int(np.any(~np.isfinite(clean[:, : L.I14 + 1]).all(axis=1) & np.isfinite(X8["ssp370"]).any(axis=1),
                        axis=1).sum())
    log(f"cells with a state variable missing in all of 1985-2014 but present later (leak-exposed): {n_leak}")
    runs = {
        "lstm": [("ssp370_leaky", X8["ssp370"], real["ssp370"]), ("ssp126_leaky", X8["ssp126"], real["ssp126"]),
                 ("ssp370", clean, real["ssp370"]), ("ssp126", clean, real["ssp126"]), ("nowarm", clean, nw)],
        "lstmCB": [("ssp370_leaky", X8["ssp370"], froz["ssp370"]), ("ssp126_leaky", X8["ssp126"], froz["ssp126"]),
                   ("ssp370", clean, froz["ssp370"]), ("ssp126", clean, froz["ssp126"])],
    }
    worst = 0.0
    for arm, todo in runs.items():
        d = os.path.join(L.OUT, arm)
        for k in range(1, 6):
            ck = torch.load(f"{d}/f{k}.pt", weights_only=False)
            mu, sd, cmu, csd = ck["mu"], ck["sd"], ck["cmu"], ck["csd"]
            i_te = np.array([idx[c] for c in folds.filter(pl.col("fold") == k)["Cell"].to_list()])
            te = [cells[i] for i in i_te]
            D = X8["ssp370"].shape[2]
            model = L.make_model(D, D + real["ssp370"].shape[2] + S_all.shape[1])
            model.load_state_dict(ck["state"])
            model.eval()
            stored = pl.read_parquet(f"{d}/f{k}_pred.parquet").filter(pl.col("start") == "S14")
            out = []
            for drive, Xs, C in todo:
                Xf = L.ffill(Xs[i_te])
                Xf = np.where(np.isfinite(Xf), Xf, mu)
                Z = torch.tensor((Xf - mu) / sd, dtype=torch.float32)
                Cc = torch.tensor((C[i_te] - cmu) / csd, dtype=torch.float32)
                with torch.no_grad():
                    P = L.rollout(model, Z, Cc, torch.tensor(S_all[i_te]),
                                  torch.full((len(i_te),), L.I14 + 1, dtype=torch.long), L.T - 1).numpy()
                phys = L.from_z(P * sd + mu)
                df = pl.DataFrame({"Cell": np.repeat(te, L.T - 1).astype(np.int32),
                                   "Year": np.tile(L.YEARS[1:], len(te)).astype(np.int32),
                                   **{c: v.reshape(-1) for c, v in phys.items()}})
                if drive.endswith("_leaky"):
                    j = df.join(stored.filter(pl.col("scen") == drive.split("_")[0]), on=["Cell", "Year"], suffix="_s")
                    assert j.height == df.height, "stored predictions do not cover the re-prediction"
                    rel = float(((j["n_per_patch"] - j["n_per_patch_s"]).abs()
                                 / j["n_per_patch_s"].abs().clip(lower_bound=1e-6)).max())
                    worst = max(worst, rel)
                out.append(df.with_columns(pl.lit(drive).alias("drive")))
            pl.concat(out).write_parquet(os.path.join(OUT, f"{arm}_f{k}.parquet"))
            log(f"{arm} fold {k}: {len(te)} cells predicted")
    log(f"HARNESS-1 max relative stems difference vs stored predictions = {worst:.2e} "
        f"({'PASS' if worst < 1e-5 else 'FAIL'})")


# ------------------------------------------------------------------------------------------------ panel
def panel_cells() -> pl.DataFrame:
    b = pl.read_csv(PANEL_CSV)
    rows = []
    for r in b.iter_rows(named=True):
        for i, c in enumerate(range(r["start"], r["end"] + 1)):
            rows.append({"Cell": c, "block": r["block"], "lat": r["lat"], "lon": r["lon_w"] + 0.5 * i})
    return pl.DataFrame(rows).with_columns(pl.col("Cell").cast(pl.Int32))


def stage_panel(_a) -> None:
    os.makedirs(OUT, exist_ok=True)
    pc = panel_cells()
    cells = pc["Cell"].to_list()
    out = []
    for m in PANEL_MEMBERS:
        for leg in PANEL_LEGS:
            f = os.path.join(PANEL_DIR, f"m{m}", leg, "ind.parquet")
            for y0, y1 in ((2020, 2020), (2020, 2029), (2071, 2100)):
                t0 = time.time()
                lf = pl.scan_parquet(f).filter(pl.col("Year").is_between(y0, y1)).select(
                    pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32), pl.col("Type").cast(pl.Int8),
                    pl.col("isdead").cast(pl.Int8), *[pl.col(t).cast(pl.Float32) for t in R.TRAITS])
                ny = lf.select(pl.col("Year").n_unique()).collect().item()
                assert ny == y1 - y0 + 1, f"{f}: {ny} years in {y0}-{y1}"
                trees = R.living(lf).collect()
                d = R.reduce_window(trees, pl.DataFrame({"Cell": cells, "n_years": [ny] * len(cells)}), ev.NPATCH)
                d = d.with_columns(pl.when(pl.col("n_per_patch") > 0).then(pl.col("agb_stand") / pl.col("n_per_patch"))
                                   .otherwise(None).alias("agb_per_stem"))
                out.append(d.select(["Cell"] + ev.PANEL).with_columns(
                    pl.lit(m).alias("member"), pl.lit(leg).alias("leg"), pl.lit(f"{y0}-{y1}").alias("win")))
                log(f"panel m{m} {leg} {y0}-{y1}: {trees.height} stem-years ({time.time() - t0:.0f}s)")
    pl.concat(out).write_parquet(os.path.join(OUT, "panel_windows.parquet"))


# ------------------------------------------------------------------------------------------------ score
def agg(d: pl.DataFrame, w: pl.DataFrame) -> dict:
    """Area-weighted stems, biomass per stem (ratio of totals), and mean medians."""
    x = d.join(w, on="Cell").with_columns((pl.col("agb_per_stem") * pl.col("n_per_patch")).fill_null(0.0).alias("b"))
    sw = lambda c: float((x[c].fill_null(0.0) * x["w"]).sum()) / float(x["w"].sum())  # noqa: E731
    out = {"n_per_patch": sw("n_per_patch"), "agb_per_stem": sw("b") / sw("n_per_patch")}
    for q in ("Wooddens_q50", "SLA_q50"):
        y = x.drop_nulls(q)
        out[q] = float((y[q] * y["w"]).sum() / y["w"].sum())
    return out


def stage_score(_a) -> None:
    cells = ev.dev_cells()
    w = cells.select("Cell", np.cos(np.deg2rad(pl.col("lat"))).alias("w"))
    T = {s: ev.lev(ev.mname(s, ev.TRUTH)) for s in ("historical", "ssp126", "ssp245", "ssp370")}
    Rp = {s: ev.lev(ev.mname(s, ev.REPLICA)) for s in ("historical", "ssp126", "ssp245", "ssp370")}
    sc = cells.join(pl.concat([T[s].filter(pl.col("n_per_patch") > 0).select("Cell") for s in T]).unique(), on="Cell")
    P = {arm: pl.concat([pl.read_parquet(os.path.join(OUT, f"{arm}_f{k}.parquet")) for k in range(1, 6)])
         for arm in ("lstm", "lstmCB")}
    win = {(arm, dr, y0): L.window_stats(P[arm].filter(pl.col("drive") == dr), y0, y1)
           for arm in P for dr in P[arm]["drive"].unique().to_list() for (y0, y1) in ((2071, 2100), (2015, 2024))}
    gm = os.path.join(ev.EVAL, "arms", "GM", "A7s")
    a7 = {s: pl.read_parquet(os.path.join(gm, f"pred_{s}_w2071.parquet")) for s in ("ssp126", "ssp370")}

    # ---- 0: the input leak. "_leaky" must reproduce ADR 0315 sec. 12 (lstm 0.125 pass, slope 0.86; lstmCB 0.102).
    rows = []
    sc370 = cells.join(pl.concat([T[s].filter(pl.col("n_per_patch") > 0).select("Cell")
                                  for s in ("historical", "ssp370")]).unique(), on="Cell")
    for arm in ("lstm", "lstmCB"):
        for v in ("ssp370_leaky", "ssp370"):
            s = ev.score(win[(arm, v, 2071)], T["historical"], T["ssp370"], T["historical"], Rp["ssp370"],
                         Rp["historical"], sc370)
            rows.append({"arm": arm, "input": "leaky (as published)" if v.endswith("leaky") else "clean", **s})
            log("LEAK", arm, v, {k: round(s[k], 4) for k in ("pass_rate", "stems_ratio", "agb_per_stem_ratio",
                                                             "resp_n_per_patch_slope_deatt",
                                                             "resp_Wooddens_q50_slope_deatt")})
    pl.DataFrame(rows, infer_schema_length=None).write_csv(os.path.join(ev.EVAL, "clock_leak.csv"))

    # ---- A: scenario contrast ssp370 - ssp126 at 2071-2100 (clean input)
    rows = []
    for name, p370, p126 in (
        ("ceiling_member7", Rp["ssp370"], Rp["ssp126"]),
        ("lstm", win[("lstm", "ssp370", 2071)], win[("lstm", "ssp126", 2071)]),
        ("lstmCB", win[("lstmCB", "ssp370", 2071)], win[("lstmCB", "ssp126", 2071)]),
        ("A7s_GM_in_sample", a7["ssp370"], a7["ssp126"]),
    ):
        s = ev.score(p370, p126, T["ssp370"], T["ssp126"], Rp["ssp370"], Rp["ssp126"], sc)
        r = {"test": "contrast_ssp370_minus_ssp126", "arm": name}
        r.update({k: v for k, v in s.items() if k.startswith("resp_")})
        rows.append(r)
        log("A", name, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if "slope_deatt" in k
                        or "agg_ratio" in k or "noise" in k})
    cb = rows[2]
    z = all(abs(cb[f"resp_{q}_agg_ratio"]) < 1e-12 for q in ("n_per_patch", "Wooddens_q50"))
    log(f"HARNESS-3 lstmCB contrast exactly 0: {'PASS' if z else 'FAIL'}")
    pl.DataFrame(rows).write_csv(os.path.join(ev.EVAL, "clock_contrast.csv"))

    # ---- B: no-warming ratios
    rows = []
    pw = panel_cells().join(
        pl.read_parquet(os.path.join(ev.DATA, "climate", "cell_static.parquet")).select(
            "Cell", pl.col("lat").round(2).alias("lat"), pl.col("lon").round(2).alias("lon")).rename({"Cell": "bCell"}),
        on=["lat", "lon"], how="left")
    matched = pw.filter(pl.col("bCell").is_in(cells["Cell"].to_list()))
    log(f"panel cells {pw.height}, mapped to the Billing grid {pw.drop_nulls('bCell').height}, "
        f"of them dev cells (matched subset) {matched.height}")
    subsets = {"dev_all": w, "dev_in_panel": w.filter(pl.col("Cell").is_in(matched["bCell"].to_list()))}
    for sub, ws in subsets.items():
        for arm in ("lstm", "lstmCB"):
            drives = P[arm]["drive"].unique().to_list()
            ref = "nowarm" if arm == "lstm" else "ssp370"
            e = agg(win[(arm, ref, 2015)], ws)
            th = agg(T["historical"], ws)
            late = {dr: agg(win[(arm, dr, 2071)], ws) for dr in drives}
            for dr in drives:
                r = {"test": "nowarm", "source": f"{arm} (Billing Feb build)", "cells": sub, "drive": dr,
                     "n_cells": ws.height}
                for q in QS:
                    r[f"d_{q}"] = late[dr][q] - e[q]
                    r[f"R_{q}"] = (late[dr][q] - e[q]) / (late["ssp370"][q] - e[q])
                    r[f"R_{q}_vs_1985_2014"] = (late[dr][q] - th[q]) / (late["ssp370"][q] - th[q])
                rows.append(r)
        for leg in ("ssp126",):  # the truth's own 126/370 ratio on the 1985-2014 baseline (no no-warming leg exists)
            th = agg(T["historical"], ws)
            r = {"test": "nowarm", "source": "truth member 8 (Billing Feb build)", "cells": sub, "drive": leg,
                 "n_cells": ws.height}
            for q in QS:
                r[f"R_{q}_vs_1985_2014"] = (agg(T[leg], ws)[q] - th[q]) / (agg(T["ssp370"], ws)[q] - th[q])
            rows.append(r)
    pan = pl.read_parquet(os.path.join(OUT, "panel_windows.parquet"))
    pwc = pw.select("Cell", np.cos(np.deg2rad(pl.col("lat"))).alias("w"))
    pmatch = pwc.filter(pl.col("Cell").is_in(matched["Cell"].to_list()))
    for sub, wsel in (("panel_all", pwc), ("panel_matched", pmatch)):
        for m in (*PANEL_MEMBERS, "mean"):
            ms = PANEL_MEMBERS if m == "mean" else (m,)

            def W(leg, win_, ms=ms, wsel=wsel):
                v = [agg(pan.filter((pl.col("member") == k) & (pl.col("leg") == leg) & (pl.col("win") == win_)), wsel)
                     for k in ms]
                return {q: float(np.mean([x[q] for x in v])) for q in QS}

            e = W("ctl_obs", "2020-2029")
            l370 = W("gfdl-esm4_ssp370", "2071-2100")
            if m != "mean":
                s0, s1 = W("ctl_obs", "2020-2020"), W("gfdl-esm4_ssp370", "2020-2020")
                log(f"HARNESS-4 panel m{m} {sub}: 2020 stems ctl/ssp370 = {s0['n_per_patch'] / s1['n_per_patch']:.4f}")
            for leg, dr in (("ctl_obs", "nowarm"), ("gfdl-esm4_ssp126", "ssp126"), ("gfdl-esm4_ssp370", "ssp370")):
                lt = W(leg, "2071-2100")
                r = {"test": "nowarm", "source": f"original model, panel m{m} (panel build)", "cells": sub,
                     "drive": dr, "n_cells": wsel.height}
                for q in QS:
                    r[f"d_{q}"] = lt[q] - e[q]
                    r[f"R_{q}"] = (lt[q] - e[q]) / (l370[q] - e[q])
                rows.append(r)
    df = pl.DataFrame(rows, infer_schema_length=None)
    df.write_csv(os.path.join(ev.EVAL, "clock_nowarm.csv"))
    with pl.Config(tbl_rows=60, tbl_cols=20, tbl_width_chars=250):
        print(df.select("source", "cells", "drive", *[f"R_{q}" for q in QS]))
        print(df.select("source", "cells", "drive", *[f"d_{q}" for q in QS]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["predict", "panel", "score"])
    a = ap.parse_args()
    {"predict": stage_predict, "panel": stage_panel, "score": stage_score}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
