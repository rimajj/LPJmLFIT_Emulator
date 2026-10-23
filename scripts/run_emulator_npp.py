#!/usr/bin/env python3
"""run_emulator_npp.py -- the emulator's OWN yearly NPP and GPP on every panel run-leg, as an input of the per-tree
mortality model (ADR 0366).

Stages:
  setups  start files for runs m5 and m6 of release v2 (ADR 0366 sec. 3) -> <OUT>/setups/v2_setup_m{5,6}.npz.
          GATE G3 first: the same procedure applied to run m1 (from v2's setup_m2) reproduces v2/setup_m1 exactly.
  run     one core per run-leg (NPROC processes): training = release v2 x runs m1 m2 m3 m5 m6 x all 30 scenario legs;
          test = fold_<g>_v3 x run m4 x <g>'s three legs, g = the first five climate models. Per run-leg: the
          emulated-NPP history (the daily model alone on observed 2000-2019 weather, the run's 2019 stand frozen,
          1999 = warm-up) and then the standard 2020-2100 run from a fresh start (cap fixed = deployment).
          -> <OUT>/runs/<release>/m<k>_<leg>.npz (year 2000..2100, cell, gpp, npp, et, runoff [N, 101], hist flag).
          GATE G2 first: (v2, m1, ukesm1-0-ll_ssp370) reproduces v2/runs/ukesm1-0-ll_ssp370_m1_capfixed.npz.
  table   -> <OUT>/enpp.parquet: member, leg, src (release), Cell, Year 2000-2100, enpp, egpp (gC/m2/yr). Every
          training leg from v2, every test leg (run m4, first five models) from its fold release.

--variant tex (ADR 0367): the same with the soil-texture daily networks, releases v2tex / fold_<g>_v3tex (copies of
v2 / fold_<g>_v3 with only daily.npz replaced, scripts/build_release_daily_swap.py) -> eval/treemort/enpp_tex/. The
m5/m6 start files are v2's (the copies' setups are byte-identical). Gates of the run stage: G2 (v2 reproduces its own
stored run -- the package change leaves a texture-free release alone; written to a new file) and G2t (v2tex
reproduces scripts/run_emulator.py's run of v2tex, which must exist: run_emulator.py --release .../v2tex --run 1
--leg ukesm1-0-ll_ssp370 --cap fixed).
"""

from __future__ import annotations

import os

for _v in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import multiprocessing as mp  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
import build_emulator_forcing as BF  # noqa: E402
import explore_panel_a7 as A7  # noqa: E402
import explore_panel_prep as PP  # noqa: E402

REL = "/p/projects/open/Jamir/esm_land_emulator_data/release"
OUT = os.path.join(PP.OUT, "eval", "treemort", "enpp")
SETUPS = os.path.join(OUT, "setups")  # the m5/m6 start files of v2 (shared by every variant)
VARIANT = ""  # "" = ADR 0366 (v2, fold_<g>_v3); "tex" = ADR 0367 (v2tex, fold_<g>_v3tex)
F2 = BF.F2
TRAIN_RUNS = (1, 2, 3, 5, 6)
TEST_RUN = 4
H0, H1 = 2000, 2019  # emulated-NPP history years
NPROC = int(os.environ.get("NPROC", "64"))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def fold_release(g: str) -> str:
    return os.path.join(REL, f"fold_{g}_v3{VARIANT}")


def deploy_release() -> str:
    return os.path.join(REL, f"v2{VARIANT}")


def setup_path(release: str, k: int) -> str:
    p = os.path.join(release, f"setup_m{k}.npz")
    if os.path.exists(p):
        return p
    import json

    with open(os.path.join(release, "release.json")) as fh:
        base = json.load(fh).get("base_release", os.path.basename(release))
    return os.path.join(SETUPS, f"{base}_setup_m{k}.npz")


# ------------------------------------------------------------------------------------------------ setups
def run_fields(k: int, cells: np.ndarray, own_daily: bool) -> dict:
    """The run-specific fields of a setup (everything else is the same for every run). own_daily: the run has f2
    arrays (m1-m4) -> its own capacity, Jan-1 stores and 2019 cover; else the m1-m4 mean of those (ADR 0366 sec. 3)."""
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import explore_panel_stand_map as SM
    import explore_panel_yearly_drift as YD

    YD.TRAIN_M = tuple(PP.MEMBERS)  # release v2 is a deployment release: every run trained (its memoff basis)
    s0x = YD.s0_table().with_columns(pl.col("Cell").cast(pl.Int32)).join(
        SM.stand_s0().with_columns(pl.col("Cell").cast(pl.Int32)), on=["Cell", "member"], how="left")
    s = pl.DataFrame({"Cell": cells}).join(s0x.filter(pl.col("member") == k), on="Cell", how="left")
    qa = [*YD.QS, *SM.SQ]
    z = {f"s0/{q}": s[f"s0_{q}"].to_numpy().astype(np.float64) for q in qa}
    z.update({f"memoff/{q}": s[f"memoff_{q}"].to_numpy().astype(np.float64) for q in qa})

    def f2(kind, m):
        return np.load(os.path.join(F2, f"{kind}_m{m}_gfdl-esm4_ssp370_daily.npy"), mmap_mode="r")

    srcs = [k] if own_daily else [1, 2, 3, 4]
    z["cap"] = np.mean([f2("cap", m)[:, 0].astype(np.float64) for m in srcs], 0)
    z["W0"] = np.mean([np.array(f2("daily", m)[:, 0, 6], np.float64) for m in srcs], 0)
    z["S0"] = np.mean([np.array(f2("daily", m)[:, 0, 5], np.float64) for m in srcs], 0)
    stand0 = np.mean([f2("stand", m)[:, 0].astype(np.float64) for m in srcs], 0)
    a = pl.read_parquet(os.path.join(PP.table_dir(k, "hist"), "annual.parquet")).filter(pl.col("Year") == 2019)
    a = pl.DataFrame({"Cell": cells}).join(a.with_columns(pl.col("Cell").cast(pl.Int32)), on="Cell", how="left")
    stand0[:, 0] = a["lai_stand"].cast(pl.Float32).to_numpy().astype(np.float64)  # the run's own 2019 values
    stand0[:, 1] = a["vegc"].cast(pl.Float32).to_numpy().astype(np.float64)
    z["stand0"] = stand0
    return z


def stage_setups(_a) -> None:
    base = dict(np.load(os.path.join(REL, "v2", "setup_m2.npz")))
    cells = base["cell"]
    ref = np.load(os.path.join(REL, "v2", "setup_m1.npz"))
    x = dict(base, **run_fields(1, cells, own_daily=True))
    bad = [q for q in ref.files if not np.array_equal(ref[q], x[q], equal_nan=True)]
    log(f"GATE G3 run m1 rebuilt from setup_m2 + m1's own fields: {len(ref.files)} fields, differ: {bad}")
    assert not bad, "the setup procedure does not reproduce v2/setup_m1"
    od = SETUPS
    os.makedirs(od, exist_ok=True)
    for k in (5, 6):
        z = dict(base, **run_fields(k, cells, own_daily=False))
        p = os.path.join(od, f"v2_setup_m{k}.npz")
        np.savez(p, **z)
        fin = {q: float(np.isfinite(z[q]).mean()) for q in ("s0/n_per_patch", "s0/fpc1", "cap", "W0", "stand0")}
        log(f"setup m{k}: {p}; finite shares {fin}; 2019 leaf area mean {np.nanmean(z['stand0'][:, 0]):.3f} "
            f"(m1 {np.nanmean(ref['stand0'][:, 0]):.3f})")


# ------------------------------------------------------------------------------------------------ run
def history(emu, su, obs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """ADR 0366 sec. 1: the daily model alone on observed 2000-2019 weather, 1999 = window warm-up, the run's 2019
    stand frozen, the setup's capacity. Returns yearly GPP and NPP (N, 20)."""
    from lpjmlfit_emulator.landemu.daily import DailyState

    st = emu.start(su)
    st["daily"] = DailyState(su.lat, su.W0, su.S0, su.D0, obs[:, :365], soil=st["daily"].soil)
    gpp, npp = np.zeros((len(su.cell), H1 - H0 + 1)), np.zeros((len(su.cell), H1 - H0 + 1))
    for iy in range(H1 - H0 + 1):
        f = np.asarray(obs[:, 365 * (iy + 1): 365 * (iy + 2)], np.float32)
        emu.begin_year(st)
        for d in range(365):
            day = emu.step_day(st, f[:, d])
            gpp[:, iy] += day["gpp"]
            npp[:, iy] += day["npp"]
        st["year"] = None  # no yearly maps: the stand stays the 2019 one
    return gpp, npp


def run_task(t) -> str:
    release, k, leg, outp = t
    if os.path.exists(outp):
        return f"exists {outp}"
    from lpjmlfit_emulator.landemu import LandEmulator, Setup

    t0 = time.process_time()
    emu = LandEmulator.load(release)
    su = Setup.load(setup_path(release, k))
    forc = np.load(BF.f2_forcing(leg), mmap_mode="r")
    obs = np.load(os.path.join(BF.OUTD, "obs_1999_2019.npy"), mmap_mode="r")
    assert np.array_equal(np.asarray(obs[:, -365:]), np.asarray(forc[:, :365])), "2019 weather differs"
    hg, hn = history(emu, su, obs)
    st = emu.start(su)
    n, ny = len(su.cell), 81
    ann = np.zeros((n, ny, 4))
    for iy in range(ny):
        f = np.asarray(forc[:, 365 * (iy + 1): 365 * (iy + 2)], np.float32)
        d, _ = emu.step_year(st, f, first_day=1 if iy == 0 else 0, cap=None)
        ann[:, iy] = np.stack([d["gpp"].sum(1), (d["interc"] + d["transp"] + d["evap"]).sum(1), d["npp"].sum(1),
                               d["runoff"].sum(1)], 1)
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    tmp = outp + ".tmp.npz"
    np.savez(tmp, cell=su.cell, year=np.arange(H0, 2101), hist=np.arange(H0, 2101) <= H1, ann=ann,
             gpp=np.concatenate([hg, ann[:, :, 0]], 1), npp=np.concatenate([hn, ann[:, :, 2]], 1))
    os.replace(tmp, outp)
    return f"{os.path.basename(release)} m{k} {leg}: {time.process_time() - t0:.0f} core-s"


def tasks() -> list[tuple]:
    out = []
    dr = deploy_release()
    for leg in A7.ALL_SLEGS:  # training legs: release v2 (v2tex)
        for k in TRAIN_RUNS:
            out.append((dr, k, leg, os.path.join(OUT, "runs", os.path.basename(dr), f"m{k}_{leg}.npz")))
    for g in PP.GCMS:  # test legs: the held-out model's fold release, run m4
        for s in PP.SCENS:
            r = fold_release(g)
            out.append((r, TEST_RUN, f"{g}_{s}", os.path.join(OUT, "runs", os.path.basename(r),
                                                           f"m{TEST_RUN}_{g}_{s}.npz")))
    return out


def stage_run(a) -> None:
    """GATE G2 runs in the same pool as the others (it costs one run-leg) and is checked before anything is reported
    as done; --which train|test|all (test needs the fold releases)."""
    dr = deploy_release()
    leg0 = "ukesm1-0-ll_ssp370"
    # (gate output, release, the release's own stored run it must equal)
    gates = [(os.path.join(OUT, "gate", f"v2_m1_{leg0}.npz"), os.path.join(REL, "v2"))]
    if VARIANT:
        gates = [(os.path.join(OUT, "gate", f"v2_m1_{leg0}_pkg{VARIANT}.npz"), os.path.join(REL, "v2")),
                 (os.path.join(OUT, "gate", f"v2{VARIANT}_m1_{leg0}.npz"), dr)]
    for _, r in gates:
        assert os.path.exists(os.path.join(r, "runs", f"{leg0}_m1_capfixed.npz")), f"no stored run in {r}/runs"
    T = [t for t in tasks() if a.which == "all" or (a.which == "train") == (t[0] == dr)]
    T = [(r, 1, leg0, gp) for gp, r in gates] + [t for t in T if not os.path.exists(t[3])]
    missing = sorted({t[0] for t in T if not os.path.exists(os.path.join(t[0], "release.json"))})
    assert not missing, f"releases not built: {missing}"
    log(f"{len(T)} run-legs (incl. the gate) on {NPROC} processes")
    with mp.get_context("spawn").Pool(NPROC) as pool:
        for i, msg in enumerate(pool.imap_unordered(run_task, T)):
            log(f"[{i + 1}/{len(T)}] {msg}")
    for gp, rel in gates:
        g, r = np.load(gp), np.load(os.path.join(rel, "runs", f"{leg0}_m1_capfixed.npz"))
        eq = np.array_equal(g["ann"], r["ann"])
        log(f"GATE G2 {os.path.basename(rel)} m1 {leg0} vs the release's own run: bit-identical {eq}, max |diff| "
            f"{float(np.abs(g['ann'] - r['ann']).max()):.2e}; history NPP 2000-2019 mean "
            f"{g['npp'][:, :20].mean():.1f}, 2020-2039 {g['npp'][:, 20:40].mean():.1f} gC/m2/yr")
        assert eq, "the runner does not reproduce the release's run: every output of this stage is invalid"


# ------------------------------------------------------------------------------------------------ table
def stage_table(_a) -> None:
    parts = []
    for rel, k, leg, p in tasks():
        z = np.load(p)
        n, ny = len(z["cell"]), len(z["year"])
        parts.append(pl.DataFrame({"Cell": np.repeat(z["cell"], ny).astype(np.int32),
                                   "Year": np.tile(z["year"], n).astype(np.int32),
                                   "enpp": z["npp"].reshape(-1), "egpp": z["gpp"].reshape(-1)})
                     .with_columns(pl.lit(k).cast(pl.Int8).alias("member"), pl.lit(leg).alias("leg"),
                                   pl.lit(os.path.basename(rel)).alias("src")))
    d = pl.concat(parts)
    assert d.select("member", "leg", "Cell", "Year").n_unique() == d.height, "duplicate keys"
    assert d.select(pl.col("enpp", "egpp").is_finite().all()).row(0) == (True, True)
    d.write_parquet(os.path.join(OUT, "enpp.parquet"))
    log(f"enpp.parquet: {d.height} rows, {d.select('member', 'leg').n_unique()} run-legs")
    with pl.Config(tbl_rows=-1):
        print(d.group_by("src", (pl.col("Year") > H1).alias("emulated")).agg(
            pl.col("enpp").mean(), pl.col("egpp").mean(), pl.len()).sort("src", "emulated"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["setups", "run", "table"])
    ap.add_argument("--which", default="all", choices=["train", "test", "all"])
    ap.add_argument("--variant", default="", choices=["", "tex"])
    a = ap.parse_args()
    global OUT, VARIANT
    VARIANT = a.variant
    if VARIANT:
        OUT = os.path.join(PP.OUT, "eval", "treemort", f"enpp_{VARIANT}")
    log(f"variant '{VARIANT}': deployment release {deploy_release()}, output {OUT}")
    {"setups": stage_setups, "run": stage_run, "table": stage_table}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
