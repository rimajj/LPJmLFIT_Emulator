#!/usr/bin/env python3
"""clu_emu_f2.py -- the learned DAILY water-carbon model on the nitrogen-on clustered runs (ADR 0342): arrays in the
f2 layout (scripts/f2_build_daily_table.py) + a CO2 series, the emulated-stand arrays, and the free runs + response
scores of the held-out climate models.

  build --seed s     per leg of seed s (and the 2019 state from its hist run), into F2N:
                       forc_m<s>_<leg>.npy  (674, 82*365, 5) tas pr rsds lwnet huss, 2019..2100 (2019 = GSWP3-W5E5)
                       daily_m<s>_<leg>.npy (674, 81*365, 10) f2_train.DAILY order, 2020..2100
                       stand_m<s>_<leg>.npy (674, 82, 12) lai_stand vegc fpc1..10 at the END of 2019..2100
                       cap_m<s>_<leg>.npy   (674, 82) top-metre capacity sum_{l<3} whc_nat * dz (year mean)
                       co2_m<s>_<leg>.npy   (82,) CO2 ppm 2019..2100 (the file the run read)
                     GATE (FATAL): the run's own daily precipitation == the forcing, every cell and day
  standB <arm>       the stand the yearly maps emulate (clu_emu_maps.py predict), 2020..2100, with the original's
                     2019 state first -> F2N/stand_emul_<arm>/stand_m2_<leg>.npy (f2_train --stand-dir)
  run <tag> [--stand-dir d]   free runs of the trained daily model on every held-out leg of seed 2, annual
                     GPP/NPP/ET/runoff; with seed 3 as the second run -> F2N/runs/<tag>/response.csv (ADR 0342 sec. 4)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
import clu_emu_maps as M  # noqa: E402

F2N = "/p/projects/open/Jamir/esm_land_emulator_data/f2_non"
DAILY = ["prec", "transp", "evap", "interc", "runoff", "swe", "rootmoist", "pet", "npp", "gpp"]
FKEYS = ["temp", "prec", "swdown", "lwnet", "humid"]
DZ = np.array([200.0, 300.0, 500.0])  # top-metre layers (soil_20m: 200, 300, 500 mm)
STANDQ = ["lai_stand", "vegc"] + [f"fpc{p}" for p in range(1, 11)]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def read_raw(path):
    """LPJmL raw output + its .json -> (nyear, nstep, nbands, ncell) float32, firstyear."""
    m = json.load(open(path + ".json"))
    dt = {"float": np.float32, "double": np.float64, "short": np.int16, "int": np.int32}[m["datatype"]]
    a = np.fromfile(path, dtype=dt)
    shp = (m["nyear"], m.get("nstep", 1), m.get("nbands", 1), m["ncell"])
    assert a.size == int(np.prod(shp)), (path, a.size, shp, m.get("order"))
    assert m.get("order", "cellseq") == "cellseq", m.get("order")
    return (a.reshape(shp) * m.get("scalar", 1.0)).astype(np.float32), int(m["firstyear"])


def forcing(leg, y0, y1):
    from build_transient_boundary import open_clm

    files = M.forcing_files(leg)
    out = []
    for k in FKEYS:
        mm, fy, ncell, nb, sc = open_clm(files[k])
        out.append(np.asarray(mm[y0 - fy: y1 - fy + 1], np.float32) * np.float32(sc))  # (Y, N, 365)
    return np.stack(out, -1)  # (Y, N, 365, 5)


def cap_of(odir, tag, y0, y1):
    w, fy = read_raw(f"{odir}/whc_nat_{tag}.bin")  # (Y, 12, layers, N)
    top = (w[y0 - fy: y1 - fy + 1, :, :3, :] * DZ[None, None, :, None]).sum(2).mean(1)  # (Y, N)
    return top.T


def stand_arr(df, y0, y1):
    d = df.filter(pl.col("Year").is_between(y0, y1)).sort("Year", "Cell")
    n = M.cells().height
    return np.stack([d[q].cast(pl.Float64).to_numpy().reshape(y1 - y0 + 1, n) for q in STANDQ], -1).transpose(1, 0, 2)


def stage_build(a):
    s = a.seed
    os.makedirs(F2N, exist_ok=True)
    c = M.cells()
    if not os.path.exists(f"{F2N}/cells.parquet"):
        c.select("Cell", pl.col("Cell").alias("block"), "lat", "lon", "heldout", pl.lit("").alias("biome"),
                 "region_km2").write_parquet(f"{F2N}/cells.parquet")
    hd = M.base_dir(s) + "/output"
    h_forc = forcing("hist", 2019, 2019)[0]  # (N, 365, 5)
    h_stand = stand_arr(M.read_stand(hd, "historical", 2019, 2019), 2019, 2019)  # (N, 1, 12)
    h_cap = cap_of(hd, "historical", 2019, 2019)  # (N, 1)
    co2 = json.load(open(f"{M.OUT}/climate/co2.json"))
    man = {}
    for g, t in M.all_legs():
        leg = M.leg_name(g, t)
        tag = f"m{s}_{leg}"
        od = M.leg_dir(s, g) + "/output"
        if os.path.exists(f"{F2N}/daily_{tag}.npy") or not os.path.exists(f"{od}/d_gpp_{t}.bin.json"):
            continue
        t0 = time.time()
        f = forcing(f"{g}_{t.replace('co2fix', '')}", 2020, 2100)  # (81, N, 365, 5)
        forc = np.concatenate([h_forc[:, None], f.transpose(1, 0, 2, 3)], 1).reshape(c.height, 82 * 365, 5)
        cols = []
        for v in DAILY:
            x, fy = read_raw(f"{od}/d_{v}_{t}.bin")  # (81, 365, 1, N)
            assert fy == 2020 and x.shape[:2] == (81, 365), (v, fy, x.shape)
            cols.append(x[:, :, 0, :].transpose(2, 0, 1).reshape(c.height, 81 * 365))
        daily = np.stack(cols, -1)
        err = float(np.abs(daily[:, :, 0] - forc[:, 365:, 1]).max())
        assert err < 1e-3, f"{tag}: daily precipitation differs from the forcing by {err} mm"
        stand = np.concatenate([h_stand, stand_arr(M.read_stand(od, t, 2020, 2100), 2020, 2100)], 1)
        cap = np.concatenate([h_cap, cap_of(od, t, 2020, 2100)], 1)
        cser = np.array([co2["ssp370co2fix" if "co2fix" in t else t][str(y)] for y in range(2019, 2101)], np.float32)
        over = float(np.nanmax(daily[:, :, 6] / np.repeat(np.maximum(cap[:, 1:], 1.0), 365, 1)))
        for k, arr in (("forc", forc), ("daily", daily), ("stand", stand), ("cap", cap), ("co2", cser)):
            np.save(f"{F2N}/{k}_{tag}.npy", np.asarray(arr, np.float32))
        man[tag] = {"prec_gate_max_abs_mm": err, "rootmoist_over_cap_max": over, "co2_2100": float(cser[-1])}
        log(f"{tag}: prec gate {err:.1e} mm, rootmoist/cap max {over:.3f}, CO2 2100 {cser[-1]:.0f} "
            f"({time.time() - t0:.0f}s)")
    p = f"{F2N}/manifest_s{s}.json"
    old = json.load(open(p)) if os.path.exists(p) else {}
    json.dump({**old, **man}, open(p, "w"), indent=1)


def stage_standB(a):
    pr = pl.read_parquet(f"{M.OUT}/maps/{a.arm}/preds.parquet")
    od = f"{F2N}/stand_emul_{a.arm}"
    os.makedirs(od, exist_ok=True)
    n = M.cells().height
    for leg in pr["leg"].unique().to_list():
        tag = f"m2_{leg}"
        if not os.path.exists(f"{F2N}/stand_{tag}.npy"):
            continue
        orig = np.load(f"{F2N}/stand_{tag}.npy")
        d = pr.filter(pl.col("leg") == leg).sort("Year", "Cell")
        em = np.stack([d[q].to_numpy().reshape(81, n) for q in STANDQ], -1).transpose(1, 0, 2)
        em = np.where(np.isfinite(em), np.maximum(em, 0.0), orig[:, 1:])  # no anchor -> the original's value
        np.save(f"{od}/stand_{tag}.npy", np.concatenate([orig[:, :1], em], 1).astype(np.float32))
    log(f"emulated stand arrays -> {od}")


def stage_run(a):
    import f2_train as F
    import torch

    F.DATA, F.CO2_INPUT = F2N, a.co2
    F.MEMBERS[:] = [2]
    F.NH, F.NL, F.NPP_HEAD, F.DEEP_TAU, F.STAND_DIR = 256, 3, "ra", 365.0, a.stand_dir
    F.DROP[:] = [F.FEAT["huss"]]
    if a.co2:
        F.NIN = F.NFORC + 3 + 4 + 12 + 1
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    nets = []
    for t in a.members.split(","):
        n, ck = F.load_net(f"{F2N}/runs/{t}/model.pt", dev)
        n.load_state_dict(ck)
        nets.append(n.eval())
    net = F.Ensemble(nets).to(dev).eval()
    c = M.cells()
    lat = c["lat"].to_numpy().astype(np.float32)
    w, ho = c["region_km2"].to_numpy(), c["heldout"].to_numpy()
    out = f"{F2N}/runs/{a.tag}"
    os.makedirs(out, exist_ok=True)
    rows, ann = [], {}
    early, late = slice(1, 31), slice(51, 81)  # 2021-2050, 2071-2100
    for g in M.TEST_GCMS:
        for s in M.SSPS + M.FIX_TEST:
            leg = M.leg_name(g, s)
            if not os.path.exists(f"{F2N}/daily_m2_{leg}.npy"):
                continue
            ml = F.MemberLeg(2, leg, lat)
            tr = F.truth_annual(ml)
            fr, _ = F.run_free(net, ml, dev)
            sec = None
            if os.path.exists(f"{F2N}/daily_m3_{leg}.npy"):
                F.STAND_DIR = ""
                sec = F.truth_annual(F.MemberLeg(3, leg, lat))
                F.STAND_DIR = a.stand_dir
            for v in F.ANNUAL:
                ann[f"truth__{leg}__{v}"], ann[f"free__{leg}__{v}"] = tr[v], fr[v]
                base = tr[v][:, early].mean(1)
                dT = tr[v][:, late].mean(1) - base
                dE = fr[v][:, late].mean(1) - fr[v][:, early].mean(1)
                dS = None if sec is None else sec[v][:, late].mean(1) - sec[v][:, early].mean(1)
                lev = np.abs(fr[v][:, late].mean(1) / np.where(np.abs(tr[v][:, late].mean(1)) > 1e-6,
                                                              tr[v][:, late].mean(1), np.nan) - 1)
                for grp, gm in (("all", np.ones(len(dT), bool)), ("heldout_cells", ho)):
                    st = M.response_stats(np.where(gm, dE, np.nan), dT, dS, w, base, True)
                    rows.append(dict(gcm=g, ssp=s, q=v, cells=grp, level_typ_err=float(np.nanmedian(lev[gm])), **st))
            log(f"{leg}: free run done")
    df = pl.DataFrame(rows)
    df.write_csv(f"{out}/response.csv")
    np.savez_compressed(f"{out}/annual.npz", **ann)
    with pl.Config(tbl_rows=100, tbl_cols=20, tbl_width_chars=240, float_precision=3):
        print(df.filter(pl.col("cells") == "all"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["build", "standB", "run"])
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--arm", default="main")
    ap.add_argument("--tag", default="")
    ap.add_argument("--members", default="")
    ap.add_argument("--stand-dir", dest="stand_dir", default="")
    ap.add_argument("--co2", action="store_true")
    a = ap.parse_args()
    {"build": stage_build, "standB": stage_standB, "run": stage_run}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
