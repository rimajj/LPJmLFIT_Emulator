#!/usr/bin/env python3
"""explore_de_grass_attrib.py — LINE X, Germany emulator: which tree input keeps grass2's leaf area from declining in
the coupled emulator?

Context (_status/HS.md, 2026-10-03): in the coupled TAB + grass2 run grass leaf area stays at ~1.8-2.1 after 2010 where
the original falls to 1.13-1.35; on the ORIGINAL's trees the same grass model is already too high, but less so. The
coupled run's grass state is not saved, and does not need to be: grass2 carries its own state, so it can be replayed
along ANY tree history.

Method (read-only; no model run). A GRASS-ONLY replay of grass2 in AR mode with exactly the coupled run's random
numbers (engine Rand(arm, rep, gcm).uniform("g2_grass", y, Cell, Patch), the sorted residual tables, float32 state
storage — explore_de_tab_g2.TabALG2._grass line for line), driven by a tree history from either
  O  the original (its patch table: printed living n / fpc / agb at y, fpc at y+1, the cover-loss ring), or
  E  the coupled emulator run (rebuilt from its printed rosters exactly as the engine computes them; the ring is
     seeded at the start year from the original's patch table, as the engine's initial state is),
and with one GROUP of tree inputs swapped between the two (patches paired by index: identical at the start, then
exchangeable). Climate and cell statics are the same for both sources.
GATE: arm E on the chunk the coupled run logged (runs/_diag_g2ar/grass_diag.jsonl) must reproduce that log per year.

Usage:  explore_de_grass_attrib.py [--run _tabg2_ar] [--chunks 0,1] [--gate-log runs/_diag_g2ar/grass_diag.jsonl]
Writes  shared/eval/grass_attrib_<run>.csv (per year x arm) and _windows.csv (window means + shares of E - O)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_engine as eng  # noqa: E402
import explore_de_grass2 as g2  # noqa: E402

XDE = g2.XDE
NPATCH = 250
KEY = ["Cell", "Patch", "Type", "ID"]
TREE = ["n_live_y", "sum_fpc_y", "sum_agb_y", "sum_fpc_y1", "frac_loss_lag0", "frac_loss_lag1", "frac_loss_lag2"]
GROUPS = {
    "COVER": ["sum_fpc_y", "sum_fpc_y1"],
    "COVER_y": ["sum_fpc_y"],
    "COVER_y1": ["sum_fpc_y1"],
    "N": ["n_live_y"],
    "AGB": ["sum_agb_y"],
    "LOSS": ["frac_loss_lag0", "frac_loss_lag1", "frac_loss_lag2"],
}
WINDOWS = [(1986, 1995), (1996, 2005), (2006, 2015), (2016, 2025), (2026, 2035), (2036, 2044)]


def run_dir(run, gcm, seed, leg):
    return os.path.join(XDE, "runs", run, "tabAL", f"{gcm}_s{seed}_1985-2044_{leg}_actual_r1")


def emulator_trees(rd, chunks, leg, uni: pl.DataFrame, years, ring0: np.ndarray) -> dict:
    """{y: frame (Cell, Patch) + TREE columns} from the coupled run's printed rosters, the engine's bookkeeping."""
    pk = ["Cell", "Patch"]
    cols = KEY + ["isdead", "fpc_ind", "agb"]
    live = {}
    for y in list(years) + [years[-1] + 1]:
        scen = "Historical" if y <= 2014 else leg
        fs = [os.path.join(rd, f"chunk_{c:03d}", f"y{y}_{scen}.parquet") for c in chunks]
        R = pl.concat([pl.read_parquet(f, columns=cols) for f in fs], how="vertical_relaxed").filter(
            (pl.col("Type") <= 6) & (pl.col("isdead") == 0))
        assert R.select(KEY).n_unique() == R.height, f"duplicate living keys in {y}"
        live[y] = R
    ring = ring0.copy()
    out = {}
    for y in years:
        L = live[y]
        st = L.group_by(pk).agg(n_live_y=pl.len().cast(pl.Float64),
                                sum_fpc_y=pl.col("fpc_ind").cast(pl.Float64).sum(),
                                sum_agb_y=pl.col("agb").cast(pl.Float64).sum())
        nx = live[y + 1].group_by(pk).agg(sum_fpc_y1=pl.col("fpc_ind").cast(pl.Float64).sum())
        if y > years[0]:  # loss during y: fpc at y-1 of stems living at y-1 that are flagged dead or absent at y
            prev = live[y - 1].select(*KEY, "fpc_ind")
            j = prev.join(L.select(KEY).with_columns(_s=pl.lit(True)), on=KEY, how="left").with_columns(
                _s=pl.col("_s").fill_null(False))
            g = j.group_by(pk).agg(_tot=pl.col("fpc_ind").cast(pl.Float64).sum(),
                                   _lost=(pl.col("fpc_ind").cast(pl.Float64) * ~pl.col("_s")).sum())
            g = uni.join(g, on=pk, how="left").with_columns(pl.col("_tot", "_lost").fill_null(0.0))
            tot, lost = g["_tot"].to_numpy(), g["_lost"].to_numpy()
            frac = np.where(tot > 0, lost / np.where(tot > 0, tot, 1.0), 0.0).astype(np.float32)
            ring = np.concatenate([frac[:, None], ring[:, :-1]], axis=1)
        D = (uni.join(st, on=pk, how="left").join(nx, on=pk, how="left")
             .with_columns(pl.col("n_live_y", "sum_fpc_y", "sum_agb_y", "sum_fpc_y1").fill_null(0.0)))
        out[y] = D.with_columns(**{f"frac_loss_lag{k}": pl.Series(ring[:, k].astype(np.float64)) for k in range(3)})
    return out


class Replay:
    """grass2 AR step exactly as TabALG2._grass (mode 'ar'), one carried state per arm."""

    def __init__(self, G: g2.Grass2, rand: eng.Rand, base0: pl.DataFrame):
        self.G, self.rand = G, rand
        self.tabs = [np.sort(t) for t in G.tabs]
        self.st = {v: base0[c].cast(pl.Float32).to_numpy().copy() for v, c in (("fpc", g2.GF), ("LAI", g2.GL),
                                                                              ("agb", g2.GA))}
        self.e = None

    def step(self, base: pl.DataFrame, trees: pl.DataFrame, y: int):
        G = self.G
        X = base.with_columns(**{g2.GF: pl.Series(self.st["fpc"]), g2.GL: pl.Series(self.st["LAI"]),
                                 g2.GA: pl.Series(self.st["agb"])},
                              **{c: trees[c] for c in TREE})
        X = g2.add_g2(X.with_columns(d_sum_fpc=pl.col("sum_fpc_y1") - pl.col("sum_fpc_y")))
        z = X["z_y"].to_numpy()
        z1 = z + G.mean_dz(X)
        u = self.rand.uniform("g2_grass", y, X["Cell"].to_numpy(), X["Patch"].to_numpy())
        b = np.searchsorted(G.edges, z1)
        r = np.empty_like(z1)
        for i in range(10):
            m = b == i
            if m.any():
                tab = self.tabs[i]
                r[m] = tab[np.minimum((u[m] * len(tab)).astype(np.int64), len(tab) - 1)]
        e0 = self.e if self.e is not None else np.zeros_like(r)
        r = G.rho * e0 + np.sqrt(1 - G.rho ** 2) * r
        self.e = r
        z1 = np.clip(z1 + r, np.log(g2.EPS), np.log(G.C["LAI_max"] * 1.2 + g2.EPS))
        L = np.maximum(np.exp(z1) - g2.EPS, 0.0)
        t1 = trees["sum_fpc_y1"].to_numpy().astype(np.float64)
        fpc, agb = g2.closure(L, t1, G.C)
        pot = 1 - np.exp(-G.C["K"] * L)
        cap = (pot - fpc) > 1e-3
        diag = {"g_mean": float(fpc.mean()), "L_mean": float(L.mean()), "t1_mean": float(t1.mean()),
                "cap_share": float(cap.mean())}
        self.st = {"fpc": fpc.astype(np.float32), "LAI": L.astype(np.float32), "agb": agb.astype(np.float32)}
        return diag, L, fpc, t1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="_tabg2_ar")
    ap.add_argument("--gcm", default="ACCESS-CM2")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--leg", default="ssp370")
    ap.add_argument("--chunks", default="0,1")
    ap.add_argument("--gate-log", default=os.path.join(XDE, "runs", "_diag_g2ar", "grass_diag.jsonl"))
    ap.add_argument("--gate-chunk", type=int, default=0)
    a = ap.parse_args()
    t0 = time.time()
    rd = run_dir(a.run, a.gcm, a.seed, a.leg)
    rj = json.load(open(os.path.join(rd, "run.json")))
    assert json.loads(rj["kwargs"]).get("mode") == "ar" and rj["stepper"].endswith("TabALG2"), rj
    chunks = [int(c) for c in a.chunks.split(",")]
    cells_by_chunk = {c: json.load(open(os.path.join(rd, f"meta_{c:03d}.json")))["cells"] for c in chunks}
    cells = sorted(sum(cells_by_chunk.values(), []))
    B = g2.original_series(a.gcm, a.seed, a.leg, cells)  # state years 1985..2043, sorted Year, Cell, Patch
    years = sorted(B["Year"].unique().to_list())
    byY = {y: g for (y,), g in B.partition_by("Year", as_dict=True, maintain_order=True).items()}
    uni = byY[years[0]].select("Cell", "Patch")
    for y in years:
        assert byY[y].select("Cell", "Patch").equals(uni), f"patch set changes in {y}"
    assert uni.height == len(cells) * NPATCH
    ring0 = np.column_stack([byY[years[0]][f"frac_loss_lag{k}"].cast(pl.Float32).fill_null(np.nan).to_numpy()
                             for k in range(3)])
    TE = emulator_trees(rd, chunks, a.leg, uni, years, ring0)
    TO = {y: byY[y].select("Cell", "Patch", *[pl.col(c).cast(pl.Float64) for c in TREE]) for y in years}
    print(f"{len(cells)} cells, {uni.height} patches, years {years[0]}..{years[-1]}; inputs built "
          f"{time.time() - t0:.0f} s", flush=True)

    arms = {"O": {}, "E": {}}
    for g, cs in GROUPS.items():
        arms[f"O+{g}"] = {"from_E": cs}
        arms[f"E-{g}"] = {"from_O": cs}
    G = g2.Grass2("DEV-A", kappa=1.0)  # TabAL default kappa (run.json kwargs carry only the mode)
    rand = eng.Rand(rj["arm"], rj["rep"], rj["gcm"])
    reps = {k: Replay(G, rand, byY[years[0]]) for k in arms}
    gate_mask = uni["Cell"].is_in(cells_by_chunk[a.gate_chunk]).to_numpy()
    gate_rows, rows = [], []
    for y in years:
        base = byY[y]
        for k, spec in arms.items():
            if k == "O":
                T = TO[y]
            elif k == "E":
                T = TE[y]
            elif "from_E" in spec:
                T = TO[y].with_columns([TE[y][c] for c in spec["from_E"]])
            else:
                T = TE[y].with_columns([TO[y][c] for c in spec["from_O"]])
            d, L, fpc, t1 = reps[k].step(base, T, y)
            if k == "E":
                m = gate_mask
                pot = 1 - np.exp(-G.C["K"] * L[m])
                gate_rows.append({"Year": y + 1, "g_mean": float(fpc[m].mean()), "L_mean": float(L[m].mean()),
                                  "t1_mean": float(t1[m].mean()),
                                  "cap_share": float(((pot - fpc[m]) > 1e-3).mean())})
            closed = t1 >= 0.45
            rows.append({"arm": k, "Year": y + 1, **d, "L_closed": float(L[closed].mean()) if closed.any() else None,
                         "L_open": float(L[t1 < 0.3].mean()) if (t1 < 0.3).any() else None})
        rows.append({"arm": "truth", "Year": y + 1, "g_mean": float(base["g_fpc_y1"].cast(pl.Float64).mean()),
                     "L_mean": float(base["g_LAI_y1"].cast(pl.Float64).mean()),
                     "t1_mean": float(base["sum_fpc_y1"].cast(pl.Float64).mean()), "cap_share": None,
                     "L_closed": float(base.filter(pl.col("sum_fpc_y1") >= 0.45)["g_LAI_y1"].cast(pl.Float64).mean()),
                     "L_open": float(base.filter(pl.col("sum_fpc_y1") < 0.3)["g_LAI_y1"].cast(pl.Float64).mean())})
        if y == years[0]:
            # GATE early: the first year must already match, or nothing downstream is about the coupled run
            ref = {r["Year"]: r for r in map(json.loads, open(a.gate_log))}
            gr = gate_rows[-1]
            rel = {c: abs(gr[c] / ref[gr["Year"]][c] - 1) for c in ("g_mean", "L_mean", "t1_mean", "cap_share")}
            print("gate first year", gr["Year"], rel, flush=True)
        if y % 10 == 0:
            print(f"  {y + 1} done ({time.time() - t0:.0f} s)", flush=True)
    # ---- gate over all years
    ref = {r["Year"]: r for r in map(json.loads, open(a.gate_log))}
    worst = {}
    for gr in gate_rows:
        for c in ("g_mean", "L_mean", "t1_mean", "cap_share"):
            worst[c] = max(worst.get(c, 0.0), abs(gr[c] / ref[gr["Year"]][c] - 1))
    ok = all(v < 1e-4 for v in worst.values())
    print("GATE arm E vs the coupled run's own log (max rel over years):", worst, "PASS" if ok else "FAIL", flush=True)
    R = pl.DataFrame(rows)
    tag = a.run.strip("_") + "_c" + "".join(str(c) for c in chunks)
    out = os.path.join(g2.EVAL, f"grass_attrib_{tag}.csv")
    R.write_csv(out)
    # ---- windows + shares
    W = []
    for lo, hi in WINDOWS:
        m = R.filter(pl.col("Year").is_between(lo, hi)).group_by("arm").agg(
            pl.col("L_mean", "g_mean", "L_closed", "L_open", "cap_share", "t1_mean").mean())
        v = {r["arm"]: r for r in m.to_dicts()}
        dEO = v["E"]["L_mean"] - v["O"]["L_mean"]
        for k in v:
            r = dict(window=f"{lo}-{hi}", **v[k])
            if k.startswith("O+"):
                r["share_add"] = (v[k]["L_mean"] - v["O"]["L_mean"]) / dEO if dEO else None
            if k.startswith("E-"):
                r["share_remove"] = (v["E"]["L_mean"] - v[k]["L_mean"]) / dEO if dEO else None
            W.append(r)
    Wd = pl.DataFrame(W)
    Wd.write_csv(out.replace(".csv", "_windows.csv"))
    pl.Config.set_tbl_rows(200)
    pl.Config.set_tbl_width_chars(240)
    print(Wd.pivot(on="window", index="arm", values="L_mean").with_columns(pl.exclude("arm").round(3)))
    print(Wd.filter(pl.col("arm").str.contains(r"[+-]")).select("window", "arm", "share_add", "share_remove")
          .with_columns(pl.col("share_add", "share_remove").round(2))
          .pivot(on="window", index="arm", values=["share_add", "share_remove"]))
    print(Wd.filter(pl.col("arm").is_in(["truth", "O", "E"])).select(
        "window", "arm", "L_closed", "L_open", "t1_mean").sort("arm", "window"))
    print("wrote", out, f"({time.time() - t0:.0f} s)")
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
