#!/usr/bin/env python3
"""build_release_daily_mep.py -- ADR 0372 section 4: a copy of a nitrogen-on release with ONLY its daily networks
replaced by the running-means daily networks (xtf_daily.py arms MEPh / MEPt, seeds 0-4), which read two opt-in
input groups the package computes itself: 32 exponential running means of the weather and a 52-number description
of the place over the 30 years before the run (MEPh, fixed) or before each year (MEPt, trailing).

Every base file except daily.npz, release.json, setup_*.npz and runs/ is copied unchanged. daily.npz is exported
from the PyTorch checkpoints (+ ema_tau, place_mode); each setup gets the yearly place summaries of 1990-2019
(observed GSWP3-W5E5 1990-2018 + the setup's own 2019 warm-up year) beside its unchanged arrays.

Gates (abort before release.json is written):
  (1) numpy == PyTorch on 20 000 real teacher-forced rows of a held-out leg, extras included (< 1e-5);
  (E) the package's daily-updated extras == the training arrays (xtf_daily.Extras) over 3 years incl. 2 year ends;
  (S) every base setup array unchanged; the setup's warm-up year == the training arrays' 2019;
  (C) every copied file byte-identical to the base's.

  python scripts/build_release_daily_mep.py --base .../release/non_fold_v1 --out .../release/non_fold_v2meph --arm MEPh
  python scripts/build_release_daily_mep.py --base .../release/non_v1 --out .../release/non_v2mept --arm MEPt --deploy
      (ADR 0373: the deployment networks xtf_daily.py train --deploy -> runs/MEPtD_s0..4; gate (1)'s leg is then a
      training leg, which a numpy-vs-PyTorch identity does not care about)
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import shutil
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "python", "src"))
import build_emulator_release as BR  # noqa: E402
import xtf_daily as X  # noqa: E402
from lpjmlfit_emulator.landemu.daily import DailyModel, DailyState, place_year_parts  # noqa: E402

SKIP = {"daily.npz", "release.json", "runs"}
GATE_LEG = "mpi-esm1-2-hr_ssp585"  # a held-out climate model, the hottest scenario
MODE = {"MEPh": "fixed", "MEPt": "trailing"}


def place_parts(warm):
    """(mon, s1, s2), each (30, N, ...): 1990-2018 observed + the setup's 2019 (= warm, (N, 365, 5))."""
    h = X.hist_raw()
    years = [h[:, i * 365 : (i + 1) * 365] for i in range(h.shape[1] // 365)] + [np.asarray(warm, np.float32)]
    assert len(years) == X.PLACE_YEARS
    ps = [place_year_parts(y) for y in years]
    return tuple(np.stack([p[i] for p in ps]) for i in range(3))


def export(out, arm, run):
    import f2_train as F
    import torch

    X.configure()
    nets, arrs = [], {"n_members": np.int64(5), "drop": np.array(F.DROP, np.int64), "deep_tau": np.float64(365.0),
                      "co2_input": np.bool_(True), "ema_tau": np.array(X.EMA_TAU, np.float64),
                      "place_mode": np.str_(MODE[arm])}  # fmt: skip
    for i in range(5):
        net, _ = X.load(f"{X.OUT}/runs/{run}_s{i}/model.pt", torch.device("cpu"))
        assert net.arm == arm, f"{run}_s{i} is arm {net.arm}, not {arm}"
        net.eval()
        nets.append(net)
        lin = [m for m in net.trunk if isinstance(m, torch.nn.Linear)]
        arrs[f"m{i}/n_layers"] = np.int64(len(lin) - 1)
        for j, m in enumerate(lin):
            arrs[f"m{i}/W{j}"] = m.weight.detach().numpy().astype(np.float32)
            arrs[f"m{i}/b{j}"] = m.bias.detach().numpy().astype(np.float32)
        for k in ("mu", "sd", "ysd"):
            arrs[f"m{i}/{k}"] = getattr(net, k).numpy().astype(np.float32)
    path = os.path.join(out, "daily.npz")
    np.savez(path, **arrs)
    dm = DailyModel.load(path)
    assert dm.place_mode == MODE[arm] and dm.ema_tau == tuple(float(t) for t in X.EMA_TAU)

    # GATE (1)
    lat = pl.read_parquet(f"{X.F2N}/cells.parquet")["lat"].to_numpy().astype(np.float32)
    ml = F.MemberLeg(2, GATE_LEG, lat)
    forc = np.load(f"{X.F2N}/forc_m2_{GATE_LEG}.npy")
    ex = X.Extras(X.ARMS[arm][1], forc)
    rng = np.random.default_rng(0)
    c, d = rng.integers(0, ml.daily.shape[0], 20000), rng.integers(1, F.ND, 20000)
    x = np.concatenate([ml.inputs_teacher(c, d), ex.take(c, d)], -1).astype(np.float32)
    x[:, F.DROP] = 0.0  # as the package (the networks' own sd for that column is ~0 either way)
    prec = ml.daily[c, d, F.PREC].astype(np.float32)
    S = ml.daily[c, d - 1, F.SWE].astype(np.float32)
    with torch.no_grad():
        t = lambda v: torch.from_numpy(v)  # noqa: E731
        yt = np.mean([n(t(x), None, t(prec), t(S)).numpy() for n in nets], 0)
    yn = dm.predict(x, prec, S)
    rel = float((np.abs(yn - yt) / np.maximum(np.abs(yt).max(axis=0), 1e-6)).max())
    BR.log(f"GATE (1) daily numpy vs torch ({arm}, extras included): max |diff| / largest |output| = {rel:.2e}")
    assert rel < 1e-5, "numpy port of the daily model differs from PyTorch"
    return dm, forc, ex, rel


def gate_extras(dm, forc, ex, parts):
    nc = forc.shape[0]
    ds = DailyState(np.zeros(nc), np.zeros(nc), np.zeros(nc), np.zeros(nc), forc[:, :365], ema_tau=dm.ema_tau,
                    place=parts, place_mode=dm.place_mode)  # fmt: skip
    worst = 0.0
    for d in range(3 * 365):
        ds.push(forc[:, 365 + d])
        if d >= 1:
            a, b = ds.extras(), ex.at(d, nc)
            worst = max(worst, float((np.abs(a - b) / (np.abs(b) + 1e-3)).max()))
        if d % 365 == 364:
            ds.end_year(forc[:, 365 + d - 364 : 365 + d + 1])
    BR.log(f"GATE (E) package extras (online, 3 years) vs training arrays: max rel diff {worst:.2e}")
    assert worst < 1e-5, "the package's extras differ from the training's"
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", required=True, choices=list(MODE))
    ap.add_argument("--deploy", action="store_true", help="networks <arm>D_s0..4 (ADR 0373)")
    ap.add_argument("--adr", default="")
    a = ap.parse_args()
    run = f"{a.arm}D" if a.deploy else a.arm
    a.adr = a.adr or ("0373" if a.deploy else "0372")
    if os.path.exists(a.out):
        sys.exit(f"refusing to overwrite {a.out}")
    os.makedirs(a.out)
    names = sorted(n for n in os.listdir(a.base) if n not in SKIP)
    copied = [n for n in names if not (n.startswith("setup_") and n.endswith(".npz"))]
    for n in copied:
        src = os.path.join(a.base, n)
        assert os.path.isfile(src), f"unexpected directory in the base release: {src}"
        shutil.copy2(src, os.path.join(a.out, n))
    dm, forc, ex, rel = export(a.out, a.arm, run)

    worst_e = None
    for n in sorted(set(names) - set(copied)):
        z = np.load(os.path.join(a.base, n))
        base = {k: z[k] for k in z.files}
        assert np.array_equal(base["warm"], forc[:, :365]), "setup warm-up year != the training arrays' 2019"
        parts = place_parts(base["warm"])
        np.savez(os.path.join(a.out, n), **base, place_mon=parts[0], place_s1=parts[1], place_s2=parts[2])
        z2 = np.load(os.path.join(a.out, n))
        same = all(np.array_equal(z2[k], v, equal_nan=v.dtype.kind == "f") for k, v in base.items())
        BR.log(f"GATE (S) {n}: base arrays unchanged {same}; warm-up year == training 2019 True; + place_* (30 yr)")
        assert same
        worst_e = gate_extras(dm, forc, ex, parts)

    bad = [n for n in copied if not filecmp.cmp(os.path.join(a.base, n), os.path.join(a.out, n), shallow=False)]
    BR.log(f"GATE (C) {len(copied)} copied files byte-identical to the base: {not bad}")
    assert not bad, f"copies differ: {bad}"

    with open(os.path.join(a.base, "release.json")) as fh:
        cfg = json.load(fh)
    base_name = os.path.basename(os.path.normpath(a.base))
    members = [f"xtf/daily/runs/{run}_s{i}" for i in range(5)]
    cfg.update({
        "version": os.path.basename(os.path.normpath(a.out)), "base_release": base_name,
        "base_daily_members": cfg.get("daily_members"), "daily_members": members,
        "daily_extras": {"arm": a.arm, "ema_tau_days": list(X.EMA_TAU), "place_mode": MODE[a.arm],
                         "place_years": X.PLACE_YEARS, "place_history": "GSWP3-W5E5 1990-2018 + setup warm-up 2019"},
        "built": time.strftime("%Y-%m-%d %H:%M"), "git_sha": BR.git_sha(), "adr": a.adr,
    })  # fmt: skip
    cfg["gates"] = dict(cfg.get("gates", {}), daily_numpy_vs_torch_max_rel=rel, setups_unchanged=True,
                        extras_online_vs_training_max_rel=worst_e, copies_identical=True)  # fmt: skip
    with open(os.path.join(a.out, "release.json"), "w") as fh:
        json.dump(cfg, fh, indent=1)
    BR.log(f"wrote {a.out} (base {base_name}, daily {run} s0..4, place {MODE[a.arm]})")


if __name__ == "__main__":
    main()
