#!/usr/bin/env python3
"""Measure the SAMPLING NOISE of the ADR-0040 forest matrix's Delta `emu_r` statistics.

WHY (adversarial power audit of the ADR-0040 verdict, 2026-08-03)
----------------------------------------------------------------
ADR 0040 §7 asserts "a paired tile-cluster bootstrap of a Delta `emu_r` of this kind gives a
spatial-sampling sd of order 0.01" and uses it to declare ADR 0038's +0.002/+0.003 ladder rungs
unresolved. That number is NOT computed anywhere: `diagnose_slow_address_prereg.py::cluster_boot`
is called only on the §4 warming statistics (`Rr`, `Rb`, `Ra`) at lines 215-216, never on `emu_r`.
The §5 decision rule is a comparison of two Deltas and a ratio of them, so the whole adjudication
rests on an unmeasured noise scale.

This script measures it, on exactly the statistic the rule uses, with the arms' OWN stored
predictions. It re-derives `emu_r` itself (per-cell median of pred vs per-cell median of Y, cells at
>= MINSTEM stems) and GATES on reproducing each arm's logged value before bootstrapping, so the
noise is attached to the same number the verdict quotes.

The bootstrap is PAIRED and CLUSTERED: one resample of whole 15-deg tiles is applied to every arm
at once, so it isolates the "which cells/tiles are in the sample" component of the noise and
cancels everything common to the arms. It does NOT measure (a) forest-seed noise (`seed = a` is
hard-wired at `ntrees = 6`) or (b) fold-colouring noise (one salt). It is therefore a strict LOWER
BOUND on replication noise.

Outputs, per axis: point estimate, bootstrap sd, 2.5/97.5 percentiles and tail probabilities for
  d_hash    = p14env_hash  - p8_hash
  d_blk     = p14env_blk   - p8_blk
  ratio     = d_blk / d_hash                (the pre-registered clause-1 statistic)
  clause1   = P(d_blk >= 0.5 * d_hash)      (clause 1 evaluated under resampling)
  gap_blk   = p14env_blk   - p14geo_blk     (the pre-registered clause-2 statistic)
  addr_hash = p14geo_hash  - p8_hash
  width     = p14perm_hash - p8_hash
plus a per-fold decomposition of each Delta (5 held-out fold sets, from the committed foldmaps).

Usage:  scripts/sbatch_python.sh S-power scripts/diagnose_slow_delta_power.py
Env:    NBOOT (4000), TILE_DEG (15.0), MINSTEM (20), BOOT_SEED (12345)
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

CAP = Path("/p/tmp/jamirp/emulator_global/capacity")
TBL = Path("/p/tmp/jamirp/emulator_global")
LATLON = TBL / "tables/cell_latlon.txt"
FOLDMAPS = TBL / "tables/foldmaps"

AXES = ["SLA", "Wooddens", "D95max", "minwscal"]
MINSTEM = int(os.environ.get("MINSTEM", "20"))
NBOOT = int(os.environ.get("NBOOT", "4000"))
TILE_DEG = float(os.environ.get("TILE_DEG", "15.0"))
BOOT_SEED = int(os.environ.get("BOOT_SEED", "12345"))

# arm -> (prediction dir, source table dir, fold mode, logged emu_r per axis in AXES order)
ARMS = {
    "p8_hash":      (CAP / "p8-hash-mtry4",           TBL / "slow_copula_pooled_w20_t8",
                     "hash",  [0.9288, 0.8693, 0.8333, 0.9766]),
    "p14env_hash":  (CAP / "pooled-env-qrf-b6x2M",    TBL / "slow_copula_pooled_w20_t8env",
                     "hash",  [0.9504, 0.9095, 0.8759, 0.9803]),
    "p14geo_hash":  (CAP / "p14geo-hash",             TBL / "slow_copula_pooled_w20_t8geo",
                     "hash",  [0.9565, 0.9231, 0.8831, 0.9817]),
    "p14perm_hash": (CAP / "p14perm-hash",            TBL / "slow_copula_pooled_w20_t8perm",
                     "hash",  [0.9177, 0.8492, 0.8136, 0.9740]),
    "p8_blk":       (CAP / "p8-blk15-buf5-mtry4",     TBL / "slow_copula_pooled_w20_t8",
                     "block", [0.8008, 0.7340, 0.7401, 0.9596]),
    "p14env_blk":   (CAP / "p14env-blk15-buf5",       TBL / "slow_copula_pooled_w20_t8env",
                     "block", [0.8305, 0.7654, 0.7907, 0.9574]),
    "p14geo_blk":   (CAP / "p14geo-blk15-buf5",       TBL / "slow_copula_pooled_w20_t8geo",
                     "block", [0.6594, 0.5786, 0.6825, 0.9351]),
}


LOGGED_SDR = {'p8_hash': [0.9244, 0.7083, 0.7743, 0.9849], 'p14env_hash': [0.9686, 0.8493, 0.8604, 0.9875], 'p14geo_hash': [0.973, 0.8503, 0.8685, 0.9869], 'p14perm_hash': [0.9068, 0.6658, 0.7539, 0.9826], 'p8_blk': [0.8762, 0.6523, 0.7325, 0.9703], 'p14env_blk': [0.9454, 0.7423, 0.8399, 0.9649], 'p14geo_blk': [0.7986, 0.569, 0.7997, 0.9406]}


def seg_median(v, starts, counts):
    out = np.empty(len(starts), dtype=np.float64)
    for i in range(len(starts)):
        s = starts[i]
        out[i] = np.median(v[s:s + counts[i]])
    return out


def rvec(P, Y, sel):
    """Pearson r AND sd(pred)/sd(obs) of each column of P against the matching column of Y, rows `sel`."""
    Ps, Ys = P[sel], Y[sel]
    mp, my = Ps.mean(0), Ys.mean(0)
    cp, cy = Ps - mp, Ys - my
    spp, syy = (cp * cp).sum(0), (cy * cy).sum(0)
    num = (cp * cy).sum(0)
    del Ps, Ys, cp, cy
    return num / np.sqrt(spp * syy), np.sqrt(spp / syy)


def main():
    print("=" * 100)
    print("POWER AUDIT of the ADR-0040 forest matrix — paired tile-cluster bootstrap of Delta emu_r")
    print("=" * 100)
    cells = np.fromfile(TBL / "slow_copula_pooled_w20_t8/cells.i64", dtype="<i8")
    n = len(cells)
    print(f"   rows = {n:,}")
    # The POOLED table is two scenario blocks concatenated, so cells.i64 is sorted only WITHIN a block.
    # Sort once and reuse the permutation for every array (this is the per-cell grouping the gate's polars
    # `group_by(Cell)` does internally; medians are order-invariant so the two agree exactly).
    order = np.argsort(cells, kind="stable")
    cs = cells[order]
    uniq, starts, counts = np.unique(cs, return_index=True, return_counts=True)
    del cs
    print(f"   cells in table = {len(uniq):,}   mean stems/cell = {counts.mean():.1f}")

    # ---- per-cell observed medians, computed independently from EVERY source table and asserted equal
    ymed = {}
    for tbl in sorted({str(v[1]) for v in ARMS.values()}):
        for a in AXES:
            m = seg_median(np.fromfile(f"{tbl}/Y_{a}.f64", dtype="<f8")[order], starts, counts)
            key = a
            if key in ymed:
                if not np.array_equal(ymed[key], m):
                    raise SystemExit(f"FATAL: Y_{a} per-cell medians differ between source tables "
                                     f"({tbl}) — the arms are NOT on one target basis.")
            else:
                ymed[key] = m
        print(f"   Y per-cell medians verified identical for {Path(tbl).name}")

    keep = counts >= MINSTEM
    print(f"   cells with >= {MINSTEM} stems = {keep.sum():,}")
    for a in AXES:
        if not np.all(np.isfinite(ymed[a][keep])):
            raise SystemExit(f"FATAL: non-finite observed median on {a}")

    # ---- per-cell predicted medians per arm, gated against the logged emu_r
    names = list(ARMS)
    cols, colname = [], []
    Ycols = []
    print("\n   GATE — reproduce each arm's logged emu_r from its stored pred_*.f64:")
    ok = True
    for nm in names:
        pdir, _, _, logged = ARMS[nm]
        for j, a in enumerate(AXES):
            p = seg_median(np.fromfile(f"{pdir}/pred_{a}.f64", dtype="<f8")[order], starts, counts)[keep]
            y = ymed[a][keep]
            if not np.all(np.isfinite(p)):
                raise SystemExit(f"FATAL: non-finite predicted median, arm {nm} axis {a}")
            r = float(np.corrcoef(p, y)[0, 1])
            sr = float(p.std() / y.std())
            d = r - logged[j]
            ds = sr - LOGGED_SDR[nm][j]
            flag = "OK " if abs(d) < 5e-5 and abs(ds) < 5e-5 else "MISMATCH"
            if abs(d) >= 5e-5 or abs(ds) >= 5e-5:
                ok = False
            print(f"     {nm:14s} {a:9s} emu_r {r:.6f} (log {logged[j]:.4f}, d={d:+.1e})  "
                  f"sd_ratio {sr:.6f} (log {LOGGED_SDR[nm][j]:.4f}, d={ds:+.1e})  {flag}")
            cols.append(p)
            Ycols.append(y)
            colname.append((nm, a))
    if not ok:
        raise SystemExit("FATAL: emu_r reproduction gate failed — the bootstrap would be on a different "
                         "statistic than the verdict quotes.")
    P = np.column_stack(cols)
    Y = np.column_stack(Ycols)
    ci = {k: i for i, k in enumerate(colname)}

    # ---- bootstrap clusters
    lat = np.full(int(uniq.max()) + 1, np.nan)
    lon = np.full(int(uniq.max()) + 1, np.nan)
    for ln in LATLON.read_text().splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        f = ln.split()
        c = int(f[0])
        if c < len(lat):
            lat[c], lon[c] = float(f[3]), float(f[4])
    cl, co = lat[uniq[keep]], lon[uniq[keep]]
    if not (np.all(np.isfinite(cl)) and np.all(np.isfinite(co))):
        raise SystemExit("FATAL: missing lat/lon for some scored cell")
    tiles = (np.floor((cl + 90.0) / TILE_DEG) * 100000 + np.floor((co + 180.0) / TILE_DEG)).astype(np.int64)
    ut, tinv = np.unique(tiles, return_inverse=True)
    torder = np.argsort(tinv, kind="stable")   # NOT `order` — that is the 42M row permutation, still live
    tstart = np.searchsorted(tinv[torder], np.arange(len(ut)))
    tend = np.searchsorted(tinv[torder], np.arange(len(ut)), side="right")
    idx_by_tile = [torder[tstart[i]:tend[i]] for i in range(len(ut))]
    print(f"\n   bootstrap clusters: {len(ut)} tiles of {TILE_DEG} deg over {keep.sum():,} scored cells")
    print(f"   tile size: min {min(len(x) for x in idx_by_tile)}  median "
          f"{int(np.median([len(x) for x in idx_by_tile]))}  max {max(len(x) for x in idx_by_tile)}")

    # ---- statistics of interest, as functions of the r-vector
    def stats(rs):
        rv, sv = rs
        out = {}
        for a in AXES:
            # criterion 2 (ADR 0030 §4): sd(pred)/sd(Y1) >= 0.75 on Wooddens. Two analysts call it FAILED
            # under blocking off a 0.7423 point estimate — so it needs a noise scale too.
            out[(a, "sdr_p14env_blk")] = sv[ci[("p14env_blk", a)]]
            out[(a, "sdr_p14env_hash")] = sv[ci[("p14env_hash", a)]]
            out[(a, "sdr_blk_minus_075")] = sv[ci[("p14env_blk", a)]] - 0.75
            out[(a, "crit2_blk_PASS")] = 1.0 if sv[ci[("p14env_blk", a)]] >= 0.75 else 0.0
            dh = rv[ci[("p14env_hash", a)]] - rv[ci[("p8_hash", a)]]
            db = rv[ci[("p14env_blk", a)]] - rv[ci[("p8_blk", a)]]
            out[(a, "d_hash")] = dh
            out[(a, "d_blk")] = db
            out[(a, "ratio")] = db / dh if dh != 0 else np.nan
            out[(a, "clause1")] = 1.0 if db >= 0.5 * dh else 0.0
            out[(a, "gap_blk")] = rv[ci[("p14env_blk", a)]] - rv[ci[("p14geo_blk", a)]]
            out[(a, "addr_hash")] = rv[ci[("p14geo_hash", a)]] - rv[ci[("p8_hash", a)]]
            out[(a, "width")] = rv[ci[("p14perm_hash", a)]] - rv[ci[("p8_hash", a)]]
            out[(a, "blk_env_minus_geo_base")] = rv[ci[("p14geo_blk", a)]] - rv[ci[("p8_blk", a)]]
        return out

    full = stats(rvec(P, Y, np.arange(P.shape[0])))

    for seed in (BOOT_SEED, BOOT_SEED + 777):
        rng = np.random.default_rng(seed)
        draws = {k: np.empty(NBOOT) for k in full}
        for b in range(NBOOT):
            pick = rng.integers(0, len(ut), size=len(ut))
            sel = np.concatenate([idx_by_tile[i] for i in pick])
            s = stats(rvec(P, Y, sel))
            for k in draws:
                draws[k][b] = s[k]
        print("\n" + "=" * 100)
        print(f"PAIRED TILE-CLUSTER BOOTSTRAP  NBOOT={NBOOT}  seed={seed}")
        print("=" * 100)
        hdr = (f"   {'axis':9s} {'stat':22s} {'point':>10s} {'boot sd':>9s} {'2.5%':>10s} {'97.5%':>10s} "
               f"{'|point|/sd':>11s} {'P(<=0)':>8s}")
        print(hdr)
        for a in AXES:
            for st in ("d_hash", "d_blk", "ratio", "gap_blk", "addr_hash", "width",
                       "blk_env_minus_geo_base", "sdr_p14env_hash", "sdr_p14env_blk",
                       "sdr_blk_minus_075"):
                d = draws[(a, st)]
                d = d[np.isfinite(d)]
                pt = full[(a, st)]
                sd = float(d.std())
                lo, hi = np.percentile(d, [2.5, 97.5])
                z = abs(pt) / sd if sd > 0 else np.inf
                print(f"   {a:9s} {st:22s} {pt:+10.4f} {sd:9.4f} {lo:+10.4f} {hi:+10.4f} "
                      f"{z:11.2f} {float((d <= 0).mean()):8.3f}")
            c1 = draws[(a, "clause1")]
            c2 = draws[(a, "crit2_blk_PASS")]
            print(f"   {a:9s} {'P(clause1 HOLDS)':22s} {'':10s} {'':9s} {'':10s} {'':10s} {'':11s} "
                  f"{float(np.nanmean(c1)):8.3f}")
            print(f"   {a:9s} {'P(crit2 blk PASS)':22s} {'':10s} {'':9s} {'':10s} {'':10s} {'':11s} "
                  f"{float(np.nanmean(c2)):8.3f}")
        print()

    # ---- per-fold decomposition (design heterogeneity, not resampling)
    print("=" * 100)
    print("PER-FOLD DECOMPOSITION — each Delta recomputed inside each held-out fold's own test cells")
    print("=" * 100)
    for mode, fp in (("hash", FOLDMAPS / "foldmap_hash.txt"),
                     ("block", FOLDMAPS / "foldmap_block15.0_buf5.0_s0.txt")):
        fold = np.full(int(uniq.max()) + 1, -1, dtype=np.int64)
        for ln in fp.read_text().splitlines():
            if ln.startswith("#") or not ln.strip():
                continue
            f = ln.split()
            c = int(f[0])
            if c < len(fold):
                fold[c] = int(f[1])
        fk = fold[uniq[keep]]
        if (fk < 0).any():
            raise SystemExit(f"FATAL: {(fk < 0).sum()} scored cells missing from {fp.name}")
        aname = "p14env_hash" if mode == "hash" else "p14env_blk"
        bname = "p8_hash" if mode == "hash" else "p8_blk"
        print(f"\n-- fold mode {mode}  ({aname} minus {bname})")
        print(f"   {'axis':9s} " + " ".join(f"{'f'+str(k):>9s}" for k in range(5)) +
              f" {'pooled':>9s} {'sd/sqrt5':>9s}")
        for a in AXES:
            vals = []
            for k in range(5):
                s = np.flatnonzero(fk == k)
                rv, _sv = rvec(P, Y, s)
                vals.append(rv[ci[(aname, a)]] - rv[ci[(bname, a)]])
            v = np.array(vals)
            print(f"   {a:9s} " + " ".join(f"{x:+9.4f}" for x in v) +
                  f" {full[(a, 'd_hash' if mode == 'hash' else 'd_blk')]:+9.4f} "
                  f"{v.std(ddof=1) / np.sqrt(5):9.4f}")
        print(f"   test cells/fold: {[int((fk == k).sum()) for k in range(5)]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
