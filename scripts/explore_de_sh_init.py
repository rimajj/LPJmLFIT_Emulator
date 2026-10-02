#!/usr/bin/env python3
"""explore_de_sh_init.py — LINE X, Germany data-driven emulator, shared item SH5: INITIAL STATES.

The state a rollout starts from, for every start year the engine supports (1985 and 2014 on the Historical
trajectory of each GCM/seed; 2044 on each ssp trajectory — the start of the 2045-2070 continuation checked against
SH12's cell aggregates). Everything comes from the converted `ind` tables plus SH3 (hidden state of the year
before) and SH4 (cover-loss history). Owner decision 2026-10-01: no start after 2044.

  shared/init/<cellset>/<gcm>_<traj>_s<seed>_<Y>/
    trees.parquet    living trees at Y (Type <= 6, printed, isdead == 0): KEY, the 6 traits, Height, agb, vegc, LAI,
                     fpc_ind, D95, Age, npp, transp, wscal_mean, mort_* (the printed hazards of year Y), c, G, cenG, W,
                     cenW (c_prev from year Y-1 where the tree was printed), d_agb_prev (agb_Y - agb_{Y-1}; where
                     the tree was not printed at Y-1 or Y is the chain's first year: the per-Type median over the
                     trees that have one — or 0 when none does — and spinin = True)
    patches.parquet  every (Cell, Patch) of npatch: n_live, sum_fpc, sum_agb, grass<t>_{fpc,LAI,agb},
                     frac_loss_lag0..19 / loss_lag0..19 at Y (null where the chain has no history), hist_years
    bank.parquet     the seedbank reconstruction, one row per (Cell, tree key) printed in [Y - max_age + 1, Y] of the
                     chain: Type, traits, first_year, last_year, n_years (years printed inside the window = the
                     tree's multiplicity in a bank refreshed yearly). At 250 patches the C's top-n-by-agb bank
                     (n = seedbank_n(npatch) = 3937) holds every printed tree plus invisible sub-5 m trees, so this
                     is (almost always) a SUBSET of the true bank (SH2 caveat 3/5); bank_years = window length the
                     chain actually covers (1 for a 1985 start).
    idmax.parquet    max printed ID per (Cell, Patch, Type) over the chain up to Y (new IDs must not collide)
    meta.json        member windows used, npatch, seedbank_n, bank_years, gate numbers

GATES  stems_equal_truth (trees rows == living tree rows of the source at Y, fresh scan) · counter_reproduces
       (mort_npp_of(G, c, mort_max) == printed mort_npp within 6-significant-digit print precision on every
       uncensored row) · patch_rows (npatch per cell) · bank_years recorded · hist_years recorded per patch.
STAGES build --cellset dev|full [--start gcm_traj_s<seed>_<Y> ...] [--cb K] · gates --cellset · submit --cellset
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_patch as sp  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402

XDE = tr.XDE
INIT = os.environ.get("SH5_OUT", os.path.join(XDE, "shared", "init"))
STATUS = os.path.join(XDE, "_status", "SH5.md")
KEY = tr.KEY
log = tr.log


def status(line: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


def starts(mem: pl.DataFrame) -> list[tuple[str, str, int, int, str]]:
    """(name, gcm, traj, seed, Y, member-window of Y) for every supported start."""
    out = []
    for r in mem.filter(~pl.col("excluded")).sort("gcm", "scen", "seed").iter_rows(named=True):
        yrs = sorted(int(y) for y in r["years_complete"])
        if r["scen"] == "Historical":
            for Y in (yrs[0], yrs[-1]):
                out.append((f"{r['gcm']}_Historical_s{r['seed']}_{Y}", r["gcm"], "Historical", int(r["seed"]), Y,
                            r["member"]))
        else:
            Y = yrs[-1]
            out.append((f"{r['gcm']}_{r['scen']}_s{r['seed']}_{Y}", r["gcm"], r["scen"], int(r["seed"]), Y,
                        r["member"]))
    return out


def chain_members(mem, gcm, traj, seed, Y):
    """[(member, source year range)] of the chain up to Y, oldest first."""
    hist = tr.historical_of(mem, gcm, seed)
    out = [hist]
    if traj != "Historical":
        out.append(mem.filter((pl.col("gcm") == gcm) & (pl.col("scen") == traj) & (pl.col("seed") == seed)
                              & ~pl.col("excluded")).row(0, named=True))
    return out


def build_one(name, gcm, traj, seed, Y, member, cellset, cb, force=False) -> dict:
    rl.assert_usable(member)
    mem, seg, folds = tr.registry()
    row = tr.member_row(mem, member)
    npatch = int(row["npatch"])
    P = rl.load_params()
    odir = os.path.join(INIT, cellset, name, f"cb={cb}")
    mpath = os.path.join(odir, "meta.json")
    if not force and os.path.exists(mpath) and json.load(open(mpath)).get("complete"):
        log(f"{name} cb={cb}: complete, skipping")
        return json.load(open(mpath))
    os.makedirs(odir, exist_ok=True)
    chain = chain_members(mem, gcm, traj, seed, Y)
    yr_src = {}
    for r in chain:
        for y in r["years_complete"]:
            yr_src[int(y)] = (r["member"], tr.sources(r, cellset)[cb])
    years = sorted(y for y in yr_src if y <= Y)
    src = yr_src[Y][1]
    cells = tr.cells_of(cellset, folds, cb, pl.scan_parquet(src).select(
        pl.concat_list(pl.col("Cell").min(), pl.col("Cell").max()).alias("Cell")).collect().explode("Cell"))
    cell_filter = cells if tr.SMOKE else None
    log(f"{name} cb={cb}: Y={Y} chain {years[0]}-{years[-1]} cells {len(cells)} npatch {npatch}")

    # ---- trees at Y with hidden state (c_prev from Y-1's transition row) and d_agb_prev
    raw = tr.read_year(src, Y, cell_filter)
    trees = tr.with_key(raw.filter((pl.col("Type") <= tr.MAX_TREE_TYPE) & (pl.col("isdead") == 0)))
    prev = None
    if Y - 1 in yr_src:
        pm, _ = yr_src[Y - 1]
        tf = os.path.join(tr.TRANS, cellset, pm, f"cb={cb}", f"y{Y - 1}.parquet")
        prev = pl.read_parquet(tf, columns=KEY + ["c_y", "agb"])
        if cell_filter is not None:
            prev = prev.filter(pl.col("Cell").is_in(cell_filter.tolist()))
    trees = tr.add_hidden(trees, prev.select(KEY + [pl.col("c_y").alias("c")]) if prev is not None else None, P)
    if prev is not None:
        trees = trees.join(prev.select(KEY + [pl.col("agb").alias("_ap")]), on=KEY, how="left").with_columns(
            d_agb_prev=(pl.col("agb") - pl.col("_ap")).cast(pl.Float32)).drop("_ap")
    else:
        trees = trees.with_columns(d_agb_prev=pl.lit(None, pl.Float32))
    med = trees.group_by("Type").agg(_m=pl.col("d_agb_prev").cast(pl.Float64).median())
    trees = (trees.join(med, on="Type", how="left")
             .with_columns(spinin=pl.col("d_agb_prev").is_null(),
                           d_agb_prev=pl.coalesce(pl.col("d_agb_prev"), pl.col("_m").cast(pl.Float32),
                                                  pl.lit(0.0, pl.Float32)))
             .drop("_m", "isdead", "Year"))
    trees = trees.select(KEY + [c for c in trees.columns if c not in KEY]).sort(KEY)
    trees.write_parquet(os.path.join(odir, "trees.parquet"), compression="zstd")

    # ---- gates on trees
    lf = pl.scan_parquet(src).filter((pl.col("Year") == Y) & (pl.col("Type") <= tr.MAX_TREE_TYPE)
                                      & (pl.col("isdead") == 0))
    if cell_filter is not None:
        lf = lf.filter(pl.col("Cell").is_in(cell_filter.tolist()))
    n_src = lf.select(pl.len()).collect().item()
    t = trees["Type"].to_numpy().astype(np.int64)
    mm = rl.mort_max_of(trees["Wooddens"].to_numpy(), t, P)
    mn = rl.mort_npp_of(trees["G"].cast(pl.Float64).to_numpy(), trees["c"].to_numpy(), mm, P=P)
    obs = trees["mort_npp"].cast(pl.Float64).to_numpy()
    ok = trees["cenG"].to_numpy() == 0
    # G is stored float32: allow its rounding (relative 6e-8 on G -> through exp(k_mort G)) plus the print precision
    tol = rl.half_ulp6(obs) * 1.0001 + np.abs(obs) * 1e-6
    bad = int((np.abs(mn - obs) > tol)[ok].sum())
    meta = {"name": name, "gcm": gcm, "traj": traj, "seed": seed, "Y": Y, "member": member, "cellset": cellset,
            "cb": cb, "npatch": npatch, "chain": [r["member"] for r in chain], "n_trees": trees.height,
            "n_src_living": n_src, "stems_equal_truth": trees.height == n_src,
            "counter_rows_checked": int(ok.sum()), "counter_mismatch": bad, "counter_reproduces": bad == 0,
            "spinin_share": float(trees["spinin"].mean()), "prev_year_available": prev is not None}

    # ---- patches: grass + cover-loss history at Y
    universe = (pl.DataFrame({"Cell": cells.astype(np.int16)})
                .join(pl.DataFrame({"Patch": np.arange(npatch, dtype=np.int16)}), how="cross"))
    st = trees.group_by("Cell", "Patch").agg(n_live=pl.len().cast(pl.Int32),
                                             sum_fpc=pl.col("fpc_ind").cast(pl.Float64).sum(),
                                             sum_agb=pl.col("agb").cast(pl.Float64).sum())
    D = universe.join(st, on=["Cell", "Patch"], how="left").with_columns(
        pl.col("n_live").fill_null(0), pl.col("sum_fpc").fill_null(0.0), pl.col("sum_agb").fill_null(0.0))
    grass = raw.filter(pl.col("Type") > tr.MAX_TREE_TYPE)
    for gt in sorted(int(v) for v in grass["Type"].unique().to_list()):
        gg = grass.filter(pl.col("Type") == gt).group_by("Cell", "Patch").agg(
            **{f"grass{gt}_fpc": pl.col("fpc_ind").cast(pl.Float64).sum(),
               f"grass{gt}_LAI": pl.col("LAI").cast(pl.Float64).sum(),
               f"grass{gt}_agb": pl.col("agb").cast(pl.Float64).sum()})
        D = D.join(gg, on=["Cell", "Patch"], how="left").with_columns(
            [pl.col(f"grass{gt}_{q}").fill_null(0.0) for q in ("fpc", "LAI", "agb")])
    pm_y = os.path.join(sp.PATCH, cellset, yr_src[Y][0], f"cb={cb}", f"y{Y}.parquet")
    pm_y1 = os.path.join(sp.PATCH, cellset, yr_src[Y - 1][0], f"cb={cb}", f"y{Y - 1}.parquet") if Y - 1 in yr_src \
        else None
    lagc = [f"{p}_lag{k}" for k in range(sp.NLAG) for p in ("loss", "frac_loss")]
    if os.path.exists(pm_y):
        H = pl.read_parquet(pm_y, columns=["Cell", "Patch"] + lagc)
        meta["history_from"] = f"SH4 patch row of {Y}"
    elif pm_y1 and os.path.exists(pm_y1):
        # Y is the last year of a window (no SH4 row at Y): lag k at Y = lag k-1 at Y-1, lag 0 = the loss during Y
        h = pl.read_parquet(pm_y1, columns=["Cell", "Patch", "loss_y1", "frac_loss_y1"] + lagc)
        H = h.select("Cell", "Patch", pl.col("loss_y1").alias("loss_lag0"), pl.col("frac_loss_y1").alias(
            "frac_loss_lag0"), *[pl.col(f"{p}_lag{k - 1}").alias(f"{p}_lag{k}") for k in range(1, sp.NLAG)
                                 for p in ("loss", "frac_loss")])
        meta["history_from"] = f"SH4 patch row of {Y - 1}, shifted one year"
    else:
        H = universe.with_columns([pl.lit(None, pl.Float32).alias(c) for c in lagc])
        meta["history_from"] = "none (chain's first year)"
    if cell_filter is not None:
        H = H.filter(pl.col("Cell").is_in(cell_filter.tolist()))
    D = D.join(H, on=["Cell", "Patch"], how="left")
    D = D.with_columns(hist_years=pl.sum_horizontal(
        [pl.col(f"loss_lag{k}").is_not_null().cast(pl.Int8) for k in range(sp.NLAG)]).cast(pl.Int8))
    D = D.with_columns([pl.col(c).cast(pl.Float32) for c, ty in D.schema.items() if ty == pl.Float64]).sort(
        "Cell", "Patch")
    D.write_parquet(os.path.join(odir, "patches.parquet"), compression="zstd")
    pc = D.group_by("Cell").len()
    meta["patch_rows_bad"] = int((pc["len"] != npatch).sum())
    meta["hist_years_dist"] = {int(a): int(b) for a, b in D.group_by("hist_years").len().sort("hist_years").rows()}

    # ---- bank + id counters over the chain up to Y
    max_age = int(P.g["max_age"])
    y0 = Y - max_age + 1
    bank_parts, idm = [], None
    for y in years:
        cols = KEY + ["Type", "SLA", "Wooddens", "D95max", "minwscal", "Longevity", "beta_root", "agb"]
        r = tr.with_key(tr.read_year(yr_src[y][1], y, cell_filter).filter(pl.col("Type") <= tr.MAX_TREE_TYPE))
        im = r.group_by("Cell", "Patch", "Type").agg(id_max=pl.col("ID").max())
        idm = im if idm is None else pl.concat([idm, im]).group_by("Cell", "Patch", "Type").agg(pl.col("id_max").max())
        if y >= y0:
            bank_parts.append(r.select(list(dict.fromkeys(cols))).with_columns(Y_=pl.lit(y, pl.Int16)))
    B = pl.concat(bank_parts)
    bank = B.group_by(KEY).agg(first_year=pl.col("Y_").min(), last_year=pl.col("Y_").max(),
                               n_years=pl.len().cast(pl.Int16),
                               **{t: pl.col(t).first() for t in tr.TRAITS})
    bank = bank.sort(KEY)
    bank.write_parquet(os.path.join(odir, "bank.parquet"), compression="zstd")
    idm.sort("Cell", "Patch", "Type").write_parquet(os.path.join(odir, "idmax.parquet"), compression="zstd")
    bs = B.group_by("Cell", "Y_").len()
    meta["seedbank_n"] = rl.seedbank_n(npatch, P)
    meta["bank_years"] = len([y for y in years if y >= y0])
    meta["bank_window"] = [max(y0, years[0]), Y]
    meta["bank_unique_per_cell_median"] = float(bank.group_by("Cell").len()["len"].median())
    meta["printed_per_cell_year_median"] = float(bs["len"].median())
    meta["printed_per_cell_year_gt_seedbank_n"] = float((bs["len"] > meta["seedbank_n"]).mean())
    meta["pass"] = bool(meta["stems_equal_truth"] and meta["counter_reproduces"] and meta["patch_rows_bad"] == 0)
    meta["complete"] = True
    json.dump(meta, open(mpath, "w"), indent=1)
    log(f"{name} cb={cb}: DONE pass={meta['pass']} trees {trees.height} counter_mismatch {bad}/{int(ok.sum())} "
        f"bank_years {meta['bank_years']}")
    return meta


def stage_build(a):
    mem, _, _ = tr.registry()
    S = [s for s in starts(mem) if not a.start or s[0] in a.start]
    for s in S:
        row = tr.member_row(mem, s[5])
        for cb in (a.cb or list(tr.sources(row, a.cellset).keys())):
            t0 = time.time()
            m = build_one(*s, a.cellset, cb, force=a.force)
            status(f"{a.cellset} {s[0]} cb={cb}: pass={m['pass']} trees {m['n_trees']} {time.time() - t0:.0f} s")


def stage_gates(a):
    rows = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(INIT, a.cellset, "*", "cb=*", "meta.json")))]
    mem, _, _ = tr.registry()
    exp = {(s[0], cb) for s in starts(mem) for cb in tr.sources(tr.member_row(mem, s[5]), a.cellset)}
    have = {(r["name"], r["cb"]) for r in rows}
    keep = ["name", "cb", "n_trees", "stems_equal_truth", "counter_mismatch", "counter_rows_checked", "spinin_share",
            "bank_years", "bank_unique_per_cell_median", "printed_per_cell_year_gt_seedbank_n", "pass"]
    out = {"cellset": a.cellset, "expected": len(exp), "built": len(have & exp),
           "missing": sorted(f"{n} cb={c}" for n, c in exp - have),
           "all_pass": bool(rows) and all(r["pass"] for r in rows) and not (exp - have),
           "per_start": [{k: r.get(k) for k in keep} for r in rows]}
    json.dump(out, open(os.path.join(INIT, a.cellset, "_gates.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "per_start"}, indent=1))
    pl.Config.set_tbl_cols(20)
    print(pl.DataFrame(out["per_start"]))


def stage_submit(a):
    mem, _, _ = tr.registry()
    tasks = [(s[0], cb) for s in starts(mem) for cb in tr.sources(tr.member_row(mem, s[5]), a.cellset)]
    jobs = os.path.join(XDE, "_jobs")
    logs = os.path.join(REPO, "logs")
    tl = os.path.join(jobs, f"SH5_{a.cellset}_tasks.txt")
    with open(tl, "w") as f:
        f.writelines(f"{n} {cb}\n" for n, cb in tasks)
    ncpu = 16 if a.cellset == "dev" else 32
    dep = f"#SBATCH --dependency=afterok:{a.dependency}\n" if a.dependency else ""
    jcf = os.path.join(jobs, f"X-de-SH5-{a.cellset}.jcf")
    with open(jcf, "w") as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name=X-de-SH5-{a.cellset}
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task={ncpu}
#SBATCH --time=02:00:00
#SBATCH --array=1-{len(tasks)}%16
{dep}#SBATCH --output={logs}/X-de-SH5-{a.cellset}.%A_%a.out
set -eu
read N CB < <(sed -n "${{SLURM_ARRAY_TASK_ID}}p" {tl})
export POLARS_MAX_THREADS={ncpu}
{tr.PY} {os.path.abspath(__file__)} build --cellset {a.cellset} --start "$N" --cb "$CB"
echo "=== JOB DONE task=$SLURM_ARRAY_TASK_ID start=$N cb=$CB exit=$? ==="
""")
    jid = subprocess.run(["sbatch", "--parsable", jcf], capture_output=True, text=True, check=True).stdout.strip()
    gj = os.path.join(jobs, f"X-de-SH5-{a.cellset}-gates.jcf")
    with open(gj, "w") as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name=X-de-SH5-{a.cellset}-gates
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task=2
#SBATCH --time=00:20:00
#SBATCH --dependency=afterany:{jid}
#SBATCH --output={logs}/X-de-SH5-{a.cellset}-gates.%j.out
{tr.PY} {os.path.abspath(__file__)} gates --cellset {a.cellset}
echo "=== JOB DONE gates exit=$? ==="
""")
    g = subprocess.run(["sbatch", "--parsable", gj], capture_output=True, text=True, check=True).stdout.strip()
    log(f"submitted {jid} ({len(tasks)} tasks), gates {g}")
    status(f"submitted {a.cellset} array {jid} ({len(tasks)} tasks), gates {g}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["build", "gates", "submit", "smoke"])
    ap.add_argument("--cellset", choices=["dev", "full"], default="dev")
    ap.add_argument("--start", action="append")
    ap.add_argument("--cb", action="append")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dependency")
    a = ap.parse_args(argv)
    if a.stage == "smoke":
        global INIT
        tr.SMOKE = True
        tr.TRANS = os.path.join(XDE, "shared", "trans", "_smoke")
        sp.PATCH = os.path.join(XDE, "shared", "patch", "_smoke")
        INIT = os.path.join(XDE, "shared", "init", "_smoke")
        a.cellset = "dev"
        a.start = a.start or ["MPI-ESM1-2-HR_Historical_s1_1985"]
        a.force = True
        stage_build(a)
        return
    {"build": stage_build, "gates": stage_gates, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
