#!/usr/bin/env python3
"""diagnose_extreme_year_legacy.py -- does the yearly forest map miss the aftermath of single extreme years? (ADR 0350)

Per case (5 held-out climate models x ssp126/370/585) and dense cell (per-year anchor >= 5 trees per patch), the
event = the year y in 2025-2090 of the truth's (run m4) largest one-year relative drop d_T = 1 - T(y)/T(y-1), kept if
d_T >= 0.15; SHARED if >= 2 of the 3 second runs (m1-m3) drop by >= 0.5 d_T in the same year, else CHANCE. Done for
tree count and for stand biomass (tree count x biomass per tree). Measures per class, pooled over cases:
  capture   d_X/d_T (emulator = the deployed map's predictions for m4), d_R/d_T (second runs), d_H/d_T (harness m5)
  aftermath L = mean(y+1..y+10)/mean(y-5..y-1) - 1; median |L_X - L_T| vs median |L_R - L_T|
  window    median |X-T|/T in years y..y+10 over the second runs' same, divided by that ratio in the cells' other years
Reads xpanel/yearly + xpanel/eval/yearly/preds_<g>.parquet (SUFFIX env picks a prediction variant). ~1 min; SLURM.
Output: xpanel/eval/extreme_legacy_events.parquet (one row per event) + the verdict table on stdout.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_panel_prep as PP  # noqa: E402
import explore_panel_yearly_drift as YD  # noqa: E402

Y0, Y1 = 2020, 2100
YEARS = np.arange(Y0, Y1 + 1)
EV0, EV1, DMIN, SHARE, NSHARE = 2025, 2090, 0.15, 0.5, 2
PRE, POST = 5, 10
SUFFIX = os.environ.get("SUFFIX", "")


def wide(d: pl.DataFrame, col: str, cells: np.ndarray) -> np.ndarray:
    """(ncell, nyear) array of `col`, NaN where missing."""
    p = d.select("Cell", "Year", col).pivot(on="Year", index="Cell", values=col)
    p = pl.DataFrame({"Cell": cells}).join(p.with_columns(pl.col("Cell").cast(pl.Int64)), on="Cell", how="left")
    out = np.full((len(cells), len(YEARS)), np.nan)
    for j, y in enumerate(YEARS):
        if str(y) in p.columns:
            out[:, j] = p[str(y)].cast(pl.Float64).to_numpy()
    return out


def quantities(d: pl.DataFrame, cells: np.ndarray) -> dict[str, np.ndarray]:
    n = wide(d, "n_per_patch", cells)
    a = np.nan_to_num(wide(d, "agb_per_stem", cells))  # no stems -> no biomass per tree
    return {"tree_count": n, "stand_biomass": n * a}


def drop(v: np.ndarray, j: np.ndarray) -> np.ndarray:
    """1 - v[y]/v[y-1] at year index j per row."""
    r = np.arange(len(v))
    prev, cur = v[r, j - 1], v[r, j]
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(prev > 0, 1.0 - cur / prev, np.nan)


def after(v: np.ndarray, j: np.ndarray) -> np.ndarray:
    r = np.arange(len(v))
    pre = np.stack([v[r, j - k] for k in range(1, PRE + 1)]).mean(0)
    post = np.stack([v[r, j + k] for k in range(1, POST + 1)]).mean(0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(pre > 0, post / pre - 1.0, np.nan)


def relerr(x: np.ndarray, t: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(t > 0, np.abs(x - t) / t, np.nan)


def events_for_case(g: str, s: str, P: pl.DataFrame) -> list[dict]:
    leg = f"{g}_{s}"
    T = YD.yearly(YD.TRUTH, leg)
    if T is None:
        return []
    X = P.filter(pl.col("leg") == leg)
    cells = np.sort(X["Cell"].unique().cast(pl.Int64).to_numpy())
    anc = wide(X, "anc_n_per_patch", cells)
    q = {"truth": quantities(T, cells), "emulator": quantities(X, cells),
         "harness": quantities(YD.yearly(YD.SECOND, leg), cells)}
    for m in YD.POOL:
        q[f"r{m}"] = quantities(YD.yearly(m, leg), cells)
    rows = []
    jlo, jhi = EV0 - Y0, EV1 - Y0
    for qn in ("tree_count", "stand_biomass"):
        t = q["truth"][qn]
        with np.errstate(divide="ignore", invalid="ignore"):
            d = np.where(t[:, :-1] > 0, 1.0 - t[:, 1:] / t[:, :-1], np.nan)  # d[:, j-1] = drop into year index j
        dw = d[:, jlo - 1 : jhi]
        ok = np.isfinite(dw).any(1)
        j = np.full(len(cells), jlo)
        j[ok] = np.nanargmax(np.where(np.isfinite(dw), dw, -np.inf)[ok], 1) + jlo
        dT = drop(t, j)
        dense = anc[np.arange(len(cells)), j] >= YD.DENSE
        keep = ok & dense & (dT >= DMIN)
        if not keep.any():
            continue
        dR = np.stack([drop(q[f"r{m}"][qn], j) for m in YD.POOL])
        shared = (dR >= SHARE * dT).sum(0) >= NSHARE
        LT = after(t, j)
        win = np.zeros_like(t, dtype=bool)
        for k in range(POST + 1):
            win[np.arange(len(cells)), j + k] = True
        excl = win.copy()
        for k in range(1, PRE + 1):
            excl[np.arange(len(cells)), j - k] = True
        for i in np.flatnonzero(keep):
            row = dict(case=leg, g=g, ssp=s, Cell=int(cells[i]), q=qn, year=int(YEARS[j[i]]), d_T=float(dT[i]),
                       shared=bool(shared[i]), L_T=float(LT[i]), T_pre=float(t[i, j[i] - PRE : j[i]].mean()))
            for nm in ("emulator", "harness", *[f"r{m}" for m in YD.POOL]):
                v = q[nm][qn]
                row[f"d_{nm}"] = float(drop(v[i : i + 1], j[i : i + 1])[0])
                row[f"L_{nm}"] = float(after(v[i : i + 1], j[i : i + 1])[0])
                e = relerr(v[i], t[i])
                row[f"ewin_{nm}"] = float(np.nanmedian(e[win[i]])) if np.isfinite(e[win[i]]).any() else np.nan
                rest = e[~excl[i]]
                row[f"erest_{nm}"] = float(np.nanmedian(rest)) if np.isfinite(rest).any() else np.nan
            rows.append(row)
    return rows


def summarise(ev: pl.DataFrame) -> pl.DataFrame:
    out = []
    pool = [f"r{m}" for m in YD.POOL]
    for (qn, sh), e in ev.group_by("q", "shared", maintain_order=True):
        dT, LT = e["d_T"].to_numpy(), e["L_T"].to_numpy()

        def cap(nm, e=e, dT=dT):
            return float(np.nanmedian(e[f"d_{nm}"].to_numpy() / dT))

        def gap(nm, e=e, LT=LT):
            return float(np.nanmedian(np.abs(e[f"L_{nm}"].to_numpy() - LT)))

        def wratio(nm, e=e):
            win = np.nanmedian(e[f"ewin_{nm}"].to_numpy())
            rest = np.nanmedian(e[f"erest_{nm}"].to_numpy())
            return win, rest

        rcap = float(np.nanmedian(np.concatenate([e[f"d_{r}"].to_numpy() / dT for r in pool])))
        rgap = float(np.nanmedian(np.concatenate([np.abs(e[f"L_{r}"].to_numpy() - LT) for r in pool])))
        rw = [wratio(r) for r in pool]
        rwin, rrest = float(np.median([w for w, _ in rw])), float(np.median([r for _, r in rw]))
        out.append(dict(
            q=qn, events=e.height, cls="shared" if sh else "chance", median_d_T=float(np.median(dT)),
            median_L_T=float(np.nanmedian(LT)),
            capture_emulator=cap("emulator"), capture_second=rcap, capture_harness=cap("harness"),
            gap_emulator=gap("emulator"), gap_second=rgap, gap_harness=gap("harness"),
            gap_ratio=gap("emulator") / rgap if rgap > 0 else np.nan,
            window_ratio_event=wratio("emulator")[0] / rwin, window_ratio_rest=wratio("emulator")[1] / rrest,
        ))  # fmt: skip
    return pl.DataFrame(out).sort("q", "cls")


def main():
    rows = []
    for g in PP.GCMS:
        pf = os.path.join(YD.OUT, f"preds_{g}{SUFFIX}.parquet")
        if not os.path.exists(pf):
            continue
        P = pl.read_parquet(pf).filter(pl.col("member") == YD.TRUTH)
        for s in ("ssp126", "ssp370", "ssp585"):
            r = events_for_case(g, s, P)
            print(f"{g}_{s}: {len(r)} events", flush=True)
            rows += r
    ev = pl.DataFrame(rows)
    ev.write_parquet(os.path.join(PP.OUT, "eval", f"extreme_legacy_events{SUFFIX}.parquet"))
    sm = summarise(ev)
    with pl.Config(tbl_rows=20, tbl_width_chars=250, float_precision=3, tbl_cols=20):
        print(sm)
    t = sm.filter((pl.col("q") == "tree_count") & (pl.col("cls") == "shared"))
    if t.height == 0 or t["events"][0] < 100:
        n = 0 if t.height == 0 else t["events"][0]
        print(f"\nVERDICT (ADR 0350 sec. 3): {n} shared tree-count events < 100 -> nothing to fix")
    else:
        r = t.row(0, named=True)
        miss = r["capture_emulator"] <= 0.5 * r["capture_second"] and r["gap_ratio"] >= 1.5
        print(f"\nVERDICT (ADR 0350 sec. 3): shared tree-count events {r['events']}, capture "
              f"{r['capture_emulator']:.3f} vs second runs {r['capture_second']:.3f}, aftermath gap ratio "
              f"{r['gap_ratio']:.2f} -> {'MISSES climate-forced aftermaths' if miss else 'nothing to fix'}")
    print("=== DONE")


if __name__ == "__main__":
    main()
