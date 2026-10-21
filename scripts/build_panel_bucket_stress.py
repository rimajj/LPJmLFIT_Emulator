#!/usr/bin/env python3
"""build_panel_bucket_stress.py -- a DAILY soil-water stress index from the daily weather alone, per panel cell and
year, for the forest map's departure model (ADR 0355).

The original's drought mortality integrates, day by day over its stress window, VPD x the shortfall of its
supply/demand ratio wscal = emax * wr / (ALPHAM * eeq) below a threshold (waterstress_tree.c, water_stressed.c:133).
The yearly climate statistics carry no soil water. This builds a forcing-only top-metre bucket (snow, capacity = the
cell's top-metre water capacity at the end of 2019) and six yearly statistics of it (ADR 0355 sec. 2):
  bk_s50, bk_s30  sum over the C's accumulator window (days 15-365 north / 196-365 south) on days with T > 10 C of
                  VPD (kPa) * max(0, theta - wscal), theta 0.5 / 0.3
  bk_wscal        mean wscal over those days (1 if none);  bk_dry  days with wscal < 0.5 among them
  bk_wmin30       minimum 30-day running mean of W/C over the calendar year;  bk_aetpet  sum evaporation / sum PET
Bucket: snow below 0 C, melt 3 mm/C/day; PET = explore_glob_climate.pet_pt, eeq = PET / 1.32; evaporation =
min(E_b * W/C, PET); W <- min(C, max(0, W + rain + melt - evaporation)); wscal = min(1, 10 * (W/C) / (1.391 * eeq)).

Stages (positional):
  calib   choose E_b in {2,3,5,8} on the observed-weather leg ctl_obs, run m1 (f2 arrays): the highest median over
          cells of the daily correlation of W/C with the original's rootmoist/cap -> bucket_params.json
  build   every scenario leg of the panel (A7.ALL_SLEGS) from the daily forcing files, observed 1996-2019 in front,
          years 2000-2100 -> xpanel/climate_bucket/<leg>.parquet
  check   C1: on the 13 held-out-model legs with daily output (f2, run m1): daily corr(W/C, original), year-to-year
          corr of bk_s50 / bk_wscal from the bucket vs from the original's own soil water (same formulas)
  events  C2: z-anomaly (vs the 30 years before) of each statistic in ADR 0350's shared tree-count event years, and
          the AUC event years vs the same cells' other years, beside the yearly water balance cwb_ann
SLURM: calib/check ~5-10 min, build ~10-20 min on 16 cpus; events seconds.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_climate as GC  # noqa: E402
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_prep as PP  # noqa: E402
from explore_de_climate import daylength_hours, vpd_c  # noqa: E402

F2 = "/p/projects/reformit/Jamir/esm_land_emulator_data/f2"
OUT = os.path.join(PP.OUT, "climate_bucket")
PARAMS = os.path.join(OUT, "bucket_params.json")
STATS = ["bk_s50", "bk_s30", "bk_wscal", "bk_dry", "bk_wmin30", "bk_aetpet"]
EB_GRID = (2.0, 3.0, 5.0, 8.0)
MELT, EMAX_C, ALPHAM, PT = 3.0, 10.0, 1.391, GC.PRIESTLEY_TAYLOR
F2_LEGS = ["gfdl-esm4_ssp126_daily", "gfdl-esm4_ssp370_daily", "gfdl-esm4_ssp585_daily",
           "ipsl-cm6a-lr_ssp126_daily", "ipsl-cm6a-lr_ssp370_daily", "ipsl-cm6a-lr_ssp585_daily",
           "mpi-esm1-2-hr_ssp126", "mpi-esm1-2-hr_ssp370", "mpi-esm1-2-hr_ssp585",
           "mri-esm2-0_ssp126_daily", "mri-esm2-0_ssp370_daily", "mri-esm2-0_ssp585_daily", "ukesm1-0-ll_ssp370"]
NB = 365


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def capacity(cells: np.ndarray) -> np.ndarray:
    """Top-metre capacity (mm) at the end of 2019, mean over runs m1-m4 (f2 cap arrays, column 0 = 2019)."""
    fc = pl.read_parquet(os.path.join(F2, "cells.parquet"))["Cell"].to_numpy()
    caps = [np.load(os.path.join(F2, f"cap_m{m}_ctl_obs.npy"), mmap_mode="r")[:, 0] for m in (1, 2, 3, 4)]
    c = np.mean(np.stack(caps), axis=0).astype(np.float64)
    pos = {int(x): i for i, x in enumerate(fc)}
    out = np.array([c[pos[int(x)]] for x in cells])
    assert np.isfinite(out).all() and (out > 0).all(), "capacity missing or zero"
    return out


class Bucket:
    """Daily top-metre bucket carried across years; `year` takes (ncell, 365) arrays and returns the year's daily
    relative soil water, wscal, evaporation and PET."""

    def __init__(self, cap: np.ndarray, lat: np.ndarray, eb: float):
        self.cap, self.eb = cap, eb
        self.W, self.snow = cap.copy(), np.zeros_like(cap)
        self.dl = daylength_hours(lat)

    def year(self, T, P, SW, LW):
        pet = GC.pet_pt(T, SW, LW, self.dl)
        eeq = pet / PT
        n = T.shape[0]
        w, ws, ev = (np.empty((n, NB)) for _ in range(3))
        for d in range(NB):
            t, p = T[:, d], P[:, d]
            snowfall = np.where(t < 0.0, p, 0.0)
            melt = np.minimum(self.snow + snowfall, MELT * np.maximum(t, 0.0))
            self.snow = self.snow + snowfall - melt
            rel = self.W / self.cap
            e = np.minimum(self.eb * rel, pet[:, d])
            self.W = np.clip(self.W + (p - snowfall) + melt - e, 0.0, self.cap)
            w[:, d] = self.W / self.cap
            ev[:, d] = e
            with np.errstate(divide="ignore", invalid="ignore"):
                ws[:, d] = np.where(eeq[:, d] > 0, np.minimum(1.0, EMAX_C * w[:, d] / (ALPHAM * eeq[:, d])), 1.0)
        return w, ws, ev, pet


def wscal_from(w: np.ndarray, T, SW, LW, dl) -> np.ndarray:
    """The same wscal formula on any relative soil water (the original's own, for check C1)."""
    eeq = GC.pet_pt(T, SW, LW, dl) / PT
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(eeq > 0, np.minimum(1.0, EMAX_C * w / (ALPHAM * eeq)), 1.0)


def year_stats(w, ws, ev, pet, T, Q, win) -> dict[str, np.ndarray]:
    vpd = vpd_c(T, GC.rh_from_q(Q, T)) / 1000.0
    g = win & (T > 10.0)
    ng = g.sum(1)
    run = np.cumsum(np.concatenate([np.zeros((w.shape[0], 1)), w], axis=1), axis=1)
    m30 = (run[:, 30:] - run[:, :-30]) / 30.0
    with np.errstate(invalid="ignore", divide="ignore"):
        return {"bk_s50": np.where(g, vpd * np.maximum(0.0, 0.5 - ws), 0.0).sum(1),
                "bk_s30": np.where(g, vpd * np.maximum(0.0, 0.3 - ws), 0.0).sum(1),
                "bk_wscal": np.where(ng > 0, np.where(g, ws, 0.0).sum(1) / np.maximum(ng, 1), 1.0),
                "bk_dry": (g & (ws < 0.5)).sum(1).astype(np.float64),
                "bk_wmin30": m30.min(1),
                "bk_aetpet": np.where(pet.sum(1) > 0, ev.sum(1) / pet.sum(1), 1.0)}


def f2_leg(leg: str, m: int = 1):
    """(forcing (ncell, 82*365, 5) from 2019, original's relative top-metre water (ncell, 81*365) from 2020, cap)."""
    f = np.load(os.path.join(F2, f"forc_m{m}_{leg}.npy"), mmap_mode="r")
    dd = np.load(os.path.join(F2, f"daily_m{m}_{leg}.npy"), mmap_mode="r")
    cp = np.load(os.path.join(F2, f"cap_m{m}_{leg}.npy"), mmap_mode="r")
    worig = np.asarray(dd[:, :, 6], dtype=np.float64) / np.repeat(np.asarray(cp[:, 1:], dtype=np.float64), NB, 1)
    return f, np.clip(worig, 0.0, 1.0)


def run_f2(f, cap, lat, eb):
    """Bucket over an f2 forcing array; returns per-year lists of (w, ws, ev, pet, T, Q, SW, LW) for 2020-2100."""
    b = Bucket(cap, lat, eb)
    ny = f.shape[1] // NB
    out = []
    for y in range(ny):
        a = np.asarray(f[:, y * NB:(y + 1) * NB, :], dtype=np.float64)
        T, P, SW, LW, Q = (a[:, :, k] for k in range(5))
        r = b.year(T, P, SW, LW)
        if y >= 1:  # 2019 is the spin-up year
            out.append((*r, T, Q, SW, LW))
    return out


def daily_corr(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    xm, ym = x - x.mean(1, keepdims=True), y - y.mean(1, keepdims=True)
    den = np.sqrt((xm ** 2).sum(1) * (ym ** 2).sum(1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return (xm * ym).sum(1) / den


def stage_calib(_a):
    os.makedirs(OUT, exist_ok=True)
    fc = pl.read_parquet(os.path.join(F2, "cells.parquet"))
    cells, lat = fc["Cell"].to_numpy(), fc["lat"].to_numpy().astype(np.float64)
    cap = capacity(cells)
    f, worig = f2_leg("ctl_obs", 1)
    res = {}
    for eb in EB_GRID:
        yrs = run_f2(f, cap, lat, eb)
        wb = np.concatenate([r[0] for r in yrs], axis=1)
        c = daily_corr(wb, worig)
        res[eb] = dict(median_corr=float(np.nanmedian(c)), q25=float(np.nanquantile(c, 0.25)),
                       mean_w_bucket=float(wb.mean()), mean_w_orig=float(worig.mean()))
        log(f"E_b {eb}: daily corr(W/C, original) median {res[eb]['median_corr']:.3f} (q25 {res[eb]['q25']:.3f}); "
            f"mean W/C {res[eb]['mean_w_bucket']:.3f} vs original {res[eb]['mean_w_orig']:.3f}")
    best = max(res, key=lambda k: res[k]["median_corr"])
    json.dump(dict(E_b=best, grid=res, leg="ctl_obs", member=1), open(PARAMS, "w"), indent=1)
    log(f"CHOSEN E_b = {best} -> {PARAMS}")


def eb_chosen() -> float:
    return float(json.load(open(PARAMS))["E_b"])


def build_leg(leg: str) -> str:
    out = os.path.join(OUT, f"{leg}.parquet")
    if os.path.exists(out):
        return out
    t0 = time.time()
    c = PP.cells()
    idx, lat = c["Cell"].to_numpy(), c["lat"].to_numpy().astype(np.float64)
    obs, sc = PP._open(PP.OBS), PP._open(PP._scen_paths(leg))
    b = Bucket(capacity(idx), lat, eb_chosen())
    win = GC.window_mask(lat)
    rows = []
    for y in range(1996, 2101):
        src = obs if y <= 2019 else sc
        arr = {v: np.asarray(mm[y - fy][idx], dtype=np.float64) * scalar for v, (mm, fy, scalar) in src.items()}
        T, P, SW, LW, Q = arr["temp"], arr["prec"], arr["swdown"], arr["lwnet"], arr["humid"]
        w, ws, ev, pet = b.year(T, P, SW, LW)
        if y >= 2000:
            s = year_stats(w, ws, ev, pet, T, Q, win)
            rows.append(pl.DataFrame({"Cell": idx.astype(np.int32), "Year": np.full(len(idx), y, np.int32),
                                      **{k: v.astype(np.float64) for k, v in s.items()}}))
    d = pl.concat(rows)
    assert all(np.isfinite(d[k].to_numpy()).all() for k in STATS), f"{leg}: non-finite statistic"
    d.write_parquet(out)
    log(f"bucket {leg}: {d.height} rows ({time.time() - t0:.0f}s)")
    return out


def stage_build(a):
    os.makedirs(OUT, exist_ok=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for o in ex.map(build_leg, A7.ALL_SLEGS):
            log("done", os.path.basename(o))


def check_leg(leg: str) -> dict:
    fc = pl.read_parquet(os.path.join(F2, "cells.parquet"))
    cells, lat = fc["Cell"].to_numpy(), fc["lat"].to_numpy().astype(np.float64)
    f, worig = f2_leg(leg, 1)
    yrs = run_f2(f, capacity(cells), lat, eb_chosen())
    win, dl = GC.window_mask(lat), daylength_hours(lat)
    wb = np.concatenate([r[0] for r in yrs], axis=1)
    sb, so = {k: [] for k in STATS}, {k: [] for k in STATS}
    for i, (w, ws, ev, pet, T, Q, SW, LW) in enumerate(yrs):
        wo = worig[:, i * NB:(i + 1) * NB]
        for k, v in year_stats(w, ws, ev, pet, T, Q, win).items():
            sb[k].append(v)
        for k, v in year_stats(wo, wscal_from(wo, T, SW, LW, dl), ev, pet, T, Q, win).items():
            so[k].append(v)
    r = dict(leg=leg, daily_w=float(np.nanmedian(daily_corr(wb, worig))))
    for k in ("bk_s50", "bk_wscal", "bk_wmin30"):
        x, y = np.stack(sb[k], 1), np.stack(so[k], 1)
        ok = (x.std(1) > 0) & (y.std(1) > 0)
        r[f"yearly_{k}"] = float(np.nanmedian(daily_corr(x[ok], y[ok]))) if ok.any() else float("nan")
        r[f"cells_{k}"] = int(ok.sum())
    return r


def stage_check(a):
    with ProcessPoolExecutor(max_workers=min(a.workers, 4)) as ex:
        rs = list(ex.map(check_leg, F2_LEGS))
    d = pl.DataFrame(rs)
    pl.Config.set_tbl_rows(50)
    pl.Config.set_tbl_cols(20)
    pl.Config.set_tbl_width_chars(200)
    print(d)
    med = {c: float(d[c].median()) for c in d.columns if c.startswith(("daily", "yearly"))}
    print("C1 medians over the 13 legs:", {k: round(v, 3) for k, v in med.items()})
    d.write_csv(os.path.join(OUT, "check_c1.csv"))


def zscores(d: pl.DataFrame, cols: list[str]) -> pl.DataFrame:
    d = d.sort("Cell", "Year")
    ex = []
    for c in cols:
        mu = pl.col(c).shift(1).rolling_mean(window_size=30, min_samples=15).over("Cell")
        sd = pl.col(c).shift(1).rolling_std(window_size=30, min_samples=15).over("Cell")
        ex.append(pl.when(sd > 1e-6 * (mu.abs() + 1.0)).then((pl.col(c) - mu) / sd).otherwise(0.0).alias(f"z_{c}"))
    return d.with_columns(ex)


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """P(score of an event year > score of another year), ties half."""
    x = np.concatenate([pos, neg])
    r = np.argsort(np.argsort(x, kind="mergesort"), kind="mergesort").astype(np.float64)
    _, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)  # average ranks over ties
    s = np.bincount(inv, weights=r) / cnt
    rk = s[inv] + 1.0
    return float((rk[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def stage_events(_a):
    ev = pl.read_parquet(os.path.join(PP.OUT, "eval", "extreme_legacy_events.parquet"))
    ev = ev.filter((pl.col("q") == "tree_count") & pl.col("shared")).select(
        pl.col("case").alias("leg"), pl.col("Cell").cast(pl.Int32), pl.col("year").cast(pl.Int32).alias("Year"))
    cols = STATS + ["cwb_ann", "prec_ann"]
    sign = {"bk_s50": 1, "bk_s30": 1, "bk_dry": 1, "bk_wscal": -1, "bk_wmin30": -1, "bk_aetpet": -1,
            "cwb_ann": -1, "prec_ann": -1}  # the direction a drought moves each statistic
    zs = []
    for leg in sorted(ev["leg"].unique().to_list()):
        b = pl.read_parquet(os.path.join(OUT, f"{leg}.parquet"))
        h = pl.read_parquet(os.path.join(PP.CLIM_DIR, "hist.parquet")).select("Cell", "Year", "cwb_ann", "prec_ann")
        s = pl.read_parquet(os.path.join(PP.CLIM_DIR, f"{leg}.parquet")).select("Cell", "Year", "cwb_ann", "prec_ann")
        cl = pl.concat([h.filter(pl.col("Year") < 2020), s]).with_columns(
            pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32), pl.col("cwb_ann").cast(pl.Float64),
            pl.col("prec_ann").cast(pl.Float64))
        z = zscores(b.join(cl, on=["Cell", "Year"], how="inner"), cols).filter(pl.col("Year").is_between(2025, 2090))
        evc = ev.filter(pl.col("leg") == leg)
        z = z.filter(pl.col("Cell").is_in(evc["Cell"].implode())).join(
            evc.with_columns(pl.lit(True).alias("event")), on=["Cell", "Year"], how="left").with_columns(
            pl.col("event").fill_null(False), pl.lit(leg).alias("leg"))
        zs.append(z.select("leg", "Cell", "Year", "event", *[f"z_{c}" for c in cols]))
    Z = pl.concat(zs)
    rows = []
    for c in cols:
        e, o = Z.filter(pl.col("event"))[f"z_{c}"].to_numpy(), Z.filter(~pl.col("event"))[f"z_{c}"].to_numpy()
        rows.append(dict(stat=c, z_event_median=float(np.median(e)), z_other_median=float(np.median(o)),
                         auc=auc(sign[c] * e, sign[c] * o), events=len(e)))
    R = pl.DataFrame(rows)
    pl.Config.set_tbl_rows(20)
    print(R)
    R.write_csv(os.path.join(OUT, "check_c2_events.csv"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["calib", "build", "check", "events"])
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    {"calib": stage_calib, "build": stage_build, "check": stage_check, "events": stage_events}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
