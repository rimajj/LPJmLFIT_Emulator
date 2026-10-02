#!/usr/bin/env python3
"""explore_de_sh_oracle.py — LINE X, Germany data-driven emulator, shared item SH8: the ORACLE-1 arm.

Rule deaths on TRUTH growth, one year at a time: each year the stepper starts from the truth roster at y (the
engine state is discarded and rebuilt), draws every tree's death with the original model's own rules (SH2
explore_de_sh_rules) from the truth's y+1 growth efficiency G, water integral W, counter of y and age, then the
bioclimatic survive() test, then fire on the survivors with the patch fire fraction identified from the truth
(f = max(0.001, sum E / sum D) per cell-year from SH4). Survivors are emitted with the truth's grown state; trees the
truth does not print at y+1 stay unprinted; the truth's new stems at y+1 (recruits and re-entries) are added as
they are. Nothing is learned.

What it measures: the ceiling of ANY design that keeps the original model's death rules (the structured design's
skeleton) — the error that remains when growth is perfect, i.e. the cost of the death channels the rule library
cannot see (the leaf-carbon kill, negative pools; listed in the rules README) and of the fire identification. It
also tests the rule library end to end through the engine and scorer.

Use (through the SH6 engine):
  explore_de_engine.py submit --arm oracle1 --stepper explore_de_sh_oracle:Oracle1 --gcm MPI-ESM1-2-HR --seed 1
      --start 1985 --end 2044 --legs ssp126,ssp370
  explore_de_score.py score --pred <run dir> --format roster --label oracle1 --split DEV-B --start-year 1985 ...
Also `python explore_de_sh_oracle.py deaths --member M` = the same draw teacher-forced over a whole member window,
written as yearly death-rate / hard-kill / fire-share series beside the truth (no engine needed; SLURM).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_engine as en  # noqa: E402
import explore_de_sh_patch as sp  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402

KEY = tr.KEY
OUT = os.path.join(tr.XDE, "shared", "oracle")


def rule_fates(T: pl.DataFrame, clim_y1: pl.DataFrame, fire_f: pl.DataFrame, rh_on: int, P, uni) -> dict:
    """T: transition rows (living at y) with targets at y+1. Returns dict of bool arrays over T's rows:
    dead_hazard, dead_survive, dead_fire, dead (all), and the rule hazard."""
    typ = T["Type"].to_numpy().astype(np.int64)
    n = T.height
    G = T["G_y1"].cast(pl.Float64).to_numpy()
    W = T["W_y1"].cast(pl.Float64).fill_null(0.0).to_numpy()
    cprev = T["c_y"].to_numpy().astype(np.int64)
    age_pre = T["Age"].cast(pl.Float64).to_numpy()  # printed Age at y = pre-increment age of year y+1
    ts = np.zeros(n)
    cj = T.select("Cell").join(clim_y1.with_columns(pl.col("Cell").cast(pl.Int16)), on="Cell", how="left")
    for k in range(tr.MAX_TREE_TYPE + 1):
        m = typ == k
        if m.any():
            ts[m] = cj[f"tstress_pft{k}"].cast(pl.Float64).fill_null(0.0).to_numpy()[m]
    sat = ~np.isfinite(G)  # mort_npp printed >= 1: counter and G not identifiable -> hazard 1
    out = rl.mortality_step(typ, T["Wooddens"].to_numpy(), age_pre, cprev, np.where(sat, 0.0, G), W, ts, rh_on, P)
    mort = np.where(sat, 1.0, out["mort"])
    u1, u2 = uni("hazard"), uni("fire")
    dead_h = u1 < mort
    tc = cj["tcold_month_tr20"].cast(pl.Float64).to_numpy()
    tw = cj["twarm_month_tr20"].cast(pl.Float64).to_numpy()
    sv = rl.survive(tc, tw, P)[np.arange(n), typ]
    dead_s = ~dead_h & ~sv
    f = T.select("Cell", "Patch").join(fire_f, on=["Cell", "Patch"], how="left")["f"].fill_null(
        P.g["fire_floor"]).to_numpy()
    pk = rl.fire_kill_prob(typ, f, P)
    dead_f = ~dead_h & ~dead_s & (u2 < pk)
    return {"dead": dead_h | dead_s | dead_f, "dead_hazard": dead_h, "dead_survive": dead_s, "dead_fire": dead_f,
            "mort": mort, "c_y1": out["c"]}


def fire_fraction(patch_y: pl.DataFrame, P) -> pl.DataFrame:
    """Truth-identified fire fraction, ONE value per cell-year: f = max(0.001, sum E / sum D) over the cell's
    patches (SH4 fire_E_y1 / fire_D_y1), returned per (Cell, Patch). Per-patch E/D is NOT used: one patch-year's
    excess deaths are dominated by the Bernoulli noise of the hazard deaths, and flooring the negative half keeps
    only positive noise (measured MPI s1 1987, cells < 200: per-patch f gave 812 fire deaths against a total
    excess of 94). Pooling is unbiased for the cell total; it gives up the within-cell patch variation of fire."""
    fl = float(P.g["fire_floor"])
    c = patch_y.group_by("Cell").agg(_e=pl.col("fire_E_y1").cast(pl.Float64).sum(),
                                     _d=pl.col("fire_D_y1").cast(pl.Float64).sum())
    c = c.with_columns(f=pl.when(pl.col("_d") > 0).then(pl.max_horizontal(pl.lit(fl), pl.col("_e") / pl.col("_d")))
                       .otherwise(fl))
    return patch_y.select("Cell", "Patch").join(c.select("Cell", "f"), on="Cell", how="left")


class Oracle1:
    needs_bank = False

    def __init__(self, cellset: str = "dev"):
        self.cellset = cellset

    def init(self, state, ctx):
        self.mem, self.seg, _ = tr.registry()
        self.P = ctx["P"]

    def _member(self, ctx, y, raw=False):
        """Member window holding the TRANSITION rows of y (raw=False: Historical stores y < its last year) or the
        printed rows of year y (raw=True: Historical holds y <= its last year)."""
        hist = tr.historical_of(self.mem, ctx["gcm"], ctx["seed"])
        last = max(int(v) for v in hist["years_complete"])
        if (y <= last) if raw else (y < last):
            return hist
        return self.mem.filter((pl.col("gcm") == ctx["gcm"]) & (pl.col("scen") == ctx["traj"])
                               & (pl.col("seed") == ctx["seed"]) & ~pl.col("excluded")).row(0, named=True)

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        y, y1 = year, year + 1
        cells = state.cell["cells"].tolist()
        m = self._member(ctx, y)
        T = pl.concat([pl.scan_parquet(os.path.join(tr.TRANS, self.cellset, m["member"], f"cb={cb}", f"y{y}.parquet"))
                       .filter(pl.col("Cell").is_in(cells)).collect()
                       for cb in tr.sources(m, self.cellset)])
        Pt = pl.concat([pl.scan_parquet(os.path.join(sp.PATCH, self.cellset, m["member"], f"cb={cb}", f"y{y}.parquet"))
                        .filter(pl.col("Cell").is_in(cells)).select("Cell", "Patch", "fire_E_y1", "fire_D_y1")
                        .collect() for cb in tr.sources(m, self.cellset)])
        pres = T.filter(pl.col("fate_y1") < 2)

        def uni(stream):
            return rand.uniform(stream, y, pres["Cell"].to_numpy(), pres["Patch"].to_numpy(), pres["Type"].to_numpy(),
                                pres["ID"].to_numpy())

        fx = rule_fates(pres, clim_y1, fire_fraction(Pt, self.P), flags_y1["rh_on"], self.P, uni)
        rec = {c: pres[c].to_numpy() for c in ["Cell", "Patch", "Type", "ID"] + tr.TRAITS}
        for f in ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "npp", "transp", "wscal_mean", "mort_npp",
                  "mort_age", "mort_water", "mort_temp", "mort"]:
            rec[f] = pres[f"{f}_y1"].to_numpy()
        rec["Age"] = pres["Age"].to_numpy() + 1
        rec["c"] = fx["c_y1"]
        rec["G"] = pres["G_y1"].fill_null(0.0).to_numpy()
        rec["W"] = pres["W_y1"].fill_null(0.0).to_numpy()
        rec["d_agb_prev"] = (pres["agb_y1"] - pres["agb"]).to_numpy()
        rec["isdead"] = fx["dead"]
        # the truth's new stems at y+1 (recruits + re-entries), as printed
        src = list(tr.sources(self._member(ctx, y1, raw=True), self.cellset).values())
        raw = pl.concat([tr.read_year(s, y1, None).filter(pl.col("Cell").is_in(cells)) for s in src])
        new = tr.with_key(raw.filter(pl.col("Type") <= tr.MAX_TREE_TYPE)).join(T.select(KEY), on=KEY, how="anti")
        nrec = {c: new[c].to_numpy() for c in ["Cell", "Patch", "Type", "ID"] + tr.TRAITS
                + ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age", "npp", "transp", "wscal_mean",
                   "mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]}
        nrec["isdead"] = new["isdead"].to_numpy() == 1
        for f, v in (("c", 0), ("G", 0.0), ("W", 0.0), ("d_agb_prev", 0.0)):
            nrec[f] = np.full(new.height, v)
        R = {k: np.concatenate([np.asarray(rec[k]), np.asarray(nrec[k])]) for k in rec}
        n = state.n
        # the engine state is discarded (hidden + removed) and rebuilt from the truth: a one-step oracle
        self.last = {"year": y1, "n_present": pres.height, "dead": int(fx["dead"].sum()),
                     "dead_hazard": int(fx["dead_hazard"].sum()), "dead_fire": int(fx["dead_fire"].sum()),
                     "dead_survive": int(fx["dead_survive"].sum()),
                     "truth_dead": int((pres["fate_y1"] == 1).sum()),
                     "truth_hard": int(pres["hard_y1"].fill_null(False).sum())}
        return en.StepOut(tree={}, isdead=np.zeros(n, bool), hidden=np.ones(n, bool), remove=np.ones(n, bool),
                          recruits=R)


# ------------------------------------------------------------------------------------------------ teacher-forced series
def stage_deaths(a):
    """Yearly Germany-dev death-rate / hard-kill / fire-share series: rule draw vs truth, one member window."""
    P = rl.load_params()
    mem, seg, _ = tr.registry()
    row = tr.member_row(mem, a.member)
    gcm, traj, seed = row["gcm"], row["scen"], int(row["seed"])
    g = json.load(open(os.path.join(tr.TRANS, a.cellset, a.member, "cb=dev", "_gates.json")))
    rand = en.Rand("oracle1_deaths", 1, gcm)
    rows = []
    for y in g["out_years"]:
        T = pl.read_parquet(os.path.join(tr.TRANS, a.cellset, a.member, "cb=dev", f"y{y}.parquet"))
        Pt = pl.read_parquet(os.path.join(sp.PATCH, a.cellset, a.member, "cb=dev", f"y{y}.parquet"),
                             columns=["Cell", "Patch", "fire_E_y1", "fire_D_y1"])
        cells = np.unique(T["Cell"].to_numpy())
        clim = en.Climate(gcm, traj, seed, cells, "actual").year(y + 1)
        pres = T.filter(pl.col("fate_y1") < 2)

        def uni(stream, pres=pres, y=y):
            return rand.uniform(stream, y, pres["Cell"].to_numpy(), pres["Patch"].to_numpy(),
                                pres["Type"].to_numpy(), pres["ID"].to_numpy())

        fx = rule_fates(pres, clim, fire_fraction(Pt, P), en.Climate(gcm, traj, seed, cells[:1]).flags(y + 1)["rh_on"],
                        P, uni)
        td = (pres["fate_y1"] == 1).to_numpy()
        th = pres["hard_y1"].fill_null(False).to_numpy()
        rows.append({"Year": y + 1, "n": pres.height, "truth_death_rate": td.mean(),
                     "rule_death_rate": fx["dead"].mean(),
                     "truth_hard_share": th[td].mean() if td.any() else np.nan,
                     "rule_hard_share": (fx["mort"] >= 1)[fx["dead"]].mean() if fx["dead"].any() else np.nan,
                     "rule_fire_share": fx["dead_fire"][fx["dead"]].mean() if fx["dead"].any() else np.nan,
                     "truth_firelike_share": (td & ~th & (pres["mort_y1"].to_numpy() < 0.01))[td].mean(),
                     "rule_expected_death_rate": float(np.mean(fx["mort"]))})
    df = pl.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    df.write_csv(os.path.join(OUT, f"deaths_{a.member}.csv"))
    c = np.corrcoef(df["truth_death_rate"].to_numpy(), df["rule_death_rate"].to_numpy())[0, 1]
    summ = {"member": a.member, "years": df.height, "truth_death_rate_mean": float(df["truth_death_rate"].mean()),
            "rule_death_rate_mean": float(df["rule_death_rate"].mean()), "corr_yearly_death_rate": float(c),
            "truth_hard_share_mean": float(df["truth_hard_share"].mean()),
            "rule_hard_share_mean": float(df["rule_hard_share"].mean()),
            "rule_fire_share_mean": float(df["rule_fire_share"].mean()),
            "truth_firelike_share_mean": float(df["truth_firelike_share"].mean())}
    json.dump(summ, open(os.path.join(OUT, f"deaths_{a.member}.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["deaths"])
    ap.add_argument("--member", default="MPI-ESM1-2-HR_ssp370_s1_w2015")
    ap.add_argument("--cellset", default="dev")
    a = ap.parse_args(argv)
    {"deaths": stage_deaths}[a.stage](a)


if __name__ == "__main__":
    main()
