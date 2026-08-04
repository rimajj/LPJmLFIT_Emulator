#!/usr/bin/env python3
"""PAIRED tile-cluster bootstrap of the WARMING-RESPONSE statistics (`Rr`, `Ra`, `Rb`), plus the
patch-year-parity correction to the reliability ceiling.

WHY (Phase 0 of the wood-density damping plan, 2026-08-04)
----------------------------------------------------------
Two instruments the response gate rests on are missing or wrong, and both err in the emulator's favour:

(a) **There is no paired bootstrap for any response statistic.** `diagnose_slow_address_prereg.py`
    calls `cluster_boot` on MARGINAL `Rr` and `Rb` only (one arm at a time), which is why ADR 0042
    §5.1 had to record every inter-arm response gap as "far inside the marginal intervals ... not a
    resolved difference", and why §10 caveat 7b costed a paired instrument at "~15 lines" and left it
    unbuilt. Without it NO acceptance threshold on a response delta can be written, because its noise
    scale is unknown. This script supplies `sd_paired(dRr)`, `sd_paired(dRb)`, `sd_paired(d|Ra-1|)`.

(b) **The split-half reliability halves share their patch-years.** `address_prereg` builds them as
    `pl.int_range(pl.len()).over(["Cell","scen"]) % 2` on a table sorted by `(Cell, Patch, Year)`
    (`build_slow_runtime_table.py:352`). Consecutive rows are therefore the SAME patch-year, so the
    two halves interleave WITHIN every retained patch-year and see the identical year set. The
    split-half then captures within-patch-year stem noise but not the between-patch-year component --
    which, on a `STEM_CAP=400` cluster-subsampled table, is the dominant term. Consequences: `rel` is
    too high, so the 0.9201 `Rr` ceiling is an UPPER BOUND ON THE CEILING; and `sd_true` is too
    large, so `Ra` is UNDERSTATED (arm A's real over-dispersion exceeds the logged 1.0728).

    The fix needs a patch-year grouping, which the table has no `Year` column for. It does not need
    one: the copula table BROADCASTS the per-(Cell,Patch,Year) conditioning aggregates onto every
    stem row of that patch-year (`build_slow_runtime_table.py:352` inner join), so rows of one
    patch-year carry BIT-IDENTICAL `Xc` head values. Runs of identical `Xc[:, :4]` within a
    (Cell, scen) block therefore ARE the patch-year groups -- an exact reconstruction, not an
    inferred one, and it needs no schema change and no re-derivation gate. Collision (two distinct
    patch-years with four bit-identical float64 aggregates) is reported, not assumed away.

Both reliability variants are computed side by side, so the STEM-parity numbers reproduce the logged
ceiling (the harness-validation gate) while the PATCH-YEAR numbers are the corrected instrument.

GATE (non-negotiable, `residual-diagnosis` skill section 3): every arm's logged `Rr`/`Ra`/`Rb` from
ADR 0042 section 5's table must be reproduced from its stored `pred_*.f64` BEFORE any bootstrap is
reported, so the noise is attached to the same numbers the verdicts quote. A failure means the
harness is wrong; it is a hard exit, not a warning.

BASIS. Pooled `w20` `t8` table, seed1, per-(Cell, scenario) medians, `Delta` = (ssp370 block median)
- (historic block median) per cell, cells with >= MINSTEM stems in BOTH blocks. The env/geo/perm arm
tables are symlink farms whose `cells.i64`/`scenario.i64`/`Y_*.f64` point into `_t8`
(inode-verified), so one target basis is loaded once and shared -- exactly as the arms were scored.

NOT measured here (so every sd below is a strict LOWER bound on replication noise): forest-seed noise
(`seed = a` is hard-wired at `ntrees = 6`), fold-colouring noise (see BLOCK_SALT arms), and the
`STEM_CAP` cluster-subsampling draw (the bootstrap resamples tiles, not the cap -- which is why the
published `Rb` CI understates its own interval; `CAP_HASH_SEED` is the separate fix for that).

Usage:  scripts/sbatch_python.sh S-resppower scripts/diagnose_slow_response_power.py
Env:    NBOOT (2000), TILE_DEG (15.0), MINSTEM (20), BOOT_SEED (12345), AXES (all four)
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

CAP = Path("/p/tmp/jamirp/emulator_global/capacity")
TBL = Path("/p/tmp/jamirp/emulator_global")
BASIS = TBL / "slow_copula_pooled_w20_t8"
LATLON = TBL / "tables/cell_latlon.txt"

AXES = [a for a in os.environ.get("AXES", "SLA,Wooddens,D95max,minwscal").split(",") if a.strip()]
GATE_AXIS = "Wooddens"          # the only axis ADR 0042 section 5 logs a response table for
MINSTEM = int(os.environ.get("MINSTEM", "20"))
NBOOT = int(os.environ.get("NBOOT", "2000"))
TILE_DEG = float(os.environ.get("TILE_DEG", "15.0"))
BOOT_SEED = int(os.environ.get("BOOT_SEED", "12345"))
NCOND_HEAD = 4                  # the four transient flux aggregates == the patch-year fingerprint

# arm -> (prediction dir, fold mode, logged (Rr, Ra, Rb) for GATE_AXIS from ADR 0042 section 5)
# Job 1683182, i.e. AFTER the section 7.3 cluster-label fix. The pre-fix intervals from jobs
# 1680715 / 1681338 were understated 3-5x and must not be quoted.
ARMS = {
    "A_p8_hash":     (CAP / "p8-hash-mtry4",        "hash",  (+0.3751, 1.0728,  -971.5)),
    "B_p14env_hash": (CAP / "pooled-env-qrf-b6x2M", "hash",  (+0.4146, 0.8694,  -892.0)),
    "G_p14perm_hash": (CAP / "p14perm-hash",        "hash",  (+0.3598, 1.0192,  -680.3)),
    "E_p14geo_hash": (CAP / "p14geo-hash",          "hash",  (+0.4361, 0.9079, -1313.2)),
    "C_p8_blk":      (CAP / "p8-blk15-buf5-mtry4",  "block", (+0.2953, 1.1189,  -896.6)),
    "D_p14env_blk":  (CAP / "p14env-blk15-buf5",    "block", (+0.2648, 0.8629,  -733.4)),
    "F_p14geo_blk":  (CAP / "p14geo-blk15-buf5",    "block", (+0.2173, 0.8495, -1507.6)),
}
LOGGED_MEANDOBS = 2432.9        # ADR 0042 section 5, GATE_AXIS
LOGGED_CEIL_STEM = 0.9201       # the stem-parity ceiling this script must reproduce, then correct

# The paired deltas the gate will be written on. Each is (treatment, matched baseline) at ONE fold
# mode and ONE colouring -- never across fold modes (ADR 0042 section 5.2: `Rr`'s env-p8 delta flips
# sign, +0.0395 hash vs -0.0305 blocked) and never across bases.
PAIRS = [
    ("B_p14env_hash", "A_p8_hash"),
    ("G_p14perm_hash", "A_p8_hash"),
    ("E_p14geo_hash", "A_p8_hash"),
    ("D_p14env_blk", "C_p8_blk"),
    ("F_p14geo_blk", "C_p8_blk"),
]


def seg_median(v: np.ndarray, starts: np.ndarray, counts: np.ndarray) -> np.ndarray:
    out = np.empty(len(starts), dtype=np.float64)
    for i in range(len(starts)):
        s = starts[i]
        out[i] = np.median(v[s:s + counts[i]])
    return out


def seg_median_masked(v: np.ndarray, starts: np.ndarray, counts: np.ndarray,
                      mask: np.ndarray) -> np.ndarray:
    """Median of v over rows of each segment where `mask` is True; NaN for an empty half."""
    out = np.empty(len(starts), dtype=np.float64)
    for i in range(len(starts)):
        s, c = starts[i], counts[i]
        m = mask[s:s + c]
        out[i] = np.median(v[s:s + c][m]) if m.any() else np.nan
    return out


def patch_year_parity(order: np.ndarray, starts: np.ndarray, counts: np.ndarray, n: int):
    """Parity of the PATCH-YEAR index within each (Cell, scen) segment.

    Patch-year groups are runs of bit-identical `Xc[:, :NCOND_HEAD]`. Returns (mask, n_groups,
    n_singleton_runs) where `mask` selects half 0. Also returns the per-segment patch-year count so
    a segment with a single patch-year -- where the split is degenerate -- can be reported.
    """
    xc = np.memmap(BASIS / "Xc.f64", dtype="<f8", mode="r")
    ncond = xc.size // n
    if xc.size % n:
        raise SystemExit(f"FATAL: Xc.f64 size {xc.size} not divisible by n={n}")
    xc = xc.reshape(n, ncond)
    head = np.ascontiguousarray(xc[:, :NCOND_HEAD])[order]   # (n, 4) in segment order
    del xc
    # A row starts a new patch-year iff any head value differs from the previous row.
    newgrp = np.empty(len(head), dtype=bool)
    newgrp[0] = True
    newgrp[1:] = np.any(head[1:] != head[:-1], axis=1)
    del head
    newgrp[starts] = True                                    # every segment starts a new patch-year
    pyidx = np.cumsum(newgrp) - 1                            # global patch-year index, 0-based
    # Parity must restart at each segment, or two adjacent segments would share a parity phase.
    pyidx = pyidx - np.repeat(pyidx[starts], counts)
    mask = (pyidx % 2) == 0
    npy_seg = np.add.reduceat(newgrp.astype(np.int64), starts)
    return mask, int(newgrp.sum()), npy_seg


def response_stats(dp: np.ndarray, dy: np.ndarray, sd_true: float, sel: np.ndarray):
    """(Rr, Ra, Rb) on rows `sel`. `sd_true` is held FIXED at its full-sample value: it is a
    property of the target's reliability, not of the resample, and re-estimating it per draw would
    inject the split-half's own noise into every arm's Ra identically (killing the pairing).

    Returns Ra RAW; take `abs(Ra - 1)` at the point of use. The gate needs the raw value to compare
    against ADR 0042's logged column, and reconstructing it from `|Ra-1|` requires guessing a sign."""
    p, y = dp[sel], dy[sel]
    rr = float(np.corrcoef(p, y)[0, 1])
    ra = float(np.std(p)) / sd_true if sd_true > 0 else np.nan
    rb = float(p.mean() - y.mean())
    return rr, ra, rb


def main() -> int:
    print("=" * 108)
    print("PAIRED response bootstrap + patch-year-parity ceiling correction")
    print(f"basis {BASIS.name}   MINSTEM={MINSTEM} in BOTH blocks   NBOOT={NBOOT}   tiles {TILE_DEG}deg")
    print("=" * 108)

    cells = np.fromfile(BASIS / "cells.i64", dtype="<i8")
    scen = np.fromfile(BASIS / "scenario.i64", dtype="<i8")
    n = len(cells)
    if len(scen) != n:
        raise SystemExit("FATAL: scenario.i64 length != cells.i64 length")
    tags = sorted(np.unique(scen).tolist())
    if len(tags) != 2:
        raise SystemExit(f"FATAL: expected 2 scenario tags, got {tags} -- not a pooled table?")
    lo_tag, hi_tag = tags
    print(f"   rows = {n:,}   scenario tags {lo_tag} -> {hi_tag}")

    # (Cell, scen) segments. STABLE sort so within-segment row order stays FILE order, which is what
    # polars `int_range().over([...])` enumerates -- required to reproduce the logged stem parity.
    order = np.lexsort((scen, cells))
    key = cells[order].astype(np.int64) * 4 + scen[order].astype(np.int64)
    uniq_key, starts, counts = np.unique(key, return_index=True, return_counts=True)
    seg_cell = uniq_key // 4
    seg_scen = uniq_key % 4
    del key
    print(f"   (Cell, scen) segments = {len(uniq_key):,}   mean stems/segment = {counts.mean():.1f}")

    # ---- the two reliability groupings
    stem_mask = np.zeros(n, dtype=bool)
    pos = np.arange(n, dtype=np.int64) - np.repeat(starts, counts)
    stem_mask[:] = (pos % 2) == 0
    del pos
    py_mask, npy_total, npy_seg = patch_year_parity(order, starts, counts, n)
    degen = int((npy_seg < 2).sum())
    print(f"   patch-year groups reconstructed from identical Xc[:, :{NCOND_HEAD}] runs: {npy_total:,}")
    print(f"   patch-years/segment: min {npy_seg.min()}  median {int(np.median(npy_seg))}  "
          f"max {npy_seg.max()}   segments with <2 patch-years (degenerate split) = {degen:,}")
    print(f"   mean stems per patch-year = {counts.sum() / npy_total:.1f}   "
          f"(a value near 1 would mean the Xc fingerprint is collapsing distinct patch-years)")

    # ---- per-segment medians: observed, its two half-splits under both groupings, and each arm's pred
    print("\n   loading per-(Cell, scen) medians ...")
    ymed, yh_stem, yh_py, pmed = {}, {}, {}, {}
    for a in AXES:
        v = np.fromfile(BASIS / f"Y_{a}.f64", dtype="<f8")[order]
        ymed[a] = seg_median(v, starts, counts)
        yh_stem[a] = (seg_median_masked(v, starts, counts, stem_mask),
                      seg_median_masked(v, starts, counts, ~stem_mask))
        yh_py[a] = (seg_median_masked(v, starts, counts, py_mask),
                    seg_median_masked(v, starts, counts, ~py_mask))
        del v
        for nm, (pdir, _, _) in ARMS.items():
            p = np.fromfile(pdir / f"pred_{a}.f64", dtype="<f8")
            if len(p) != n:
                raise SystemExit(f"FATAL: {nm} pred_{a} length {len(p)} != {n}")
            pmed[(nm, a)] = seg_median(p[order], starts, counts)
            del p
        print(f"     {a}: done")

    # ---- pivot to per-cell Delta (cells present in BOTH blocks, >= MINSTEM in both)
    lo_i = np.flatnonzero(seg_scen == lo_tag)
    hi_i = np.flatnonzero(seg_scen == hi_tag)
    c_lo, c_hi = seg_cell[lo_i], seg_cell[hi_i]
    common, il, ih = np.intersect1d(c_lo, c_hi, return_indices=True)
    lo_i, hi_i = lo_i[il], hi_i[ih]
    ok = (counts[lo_i] >= MINSTEM) & (counts[hi_i] >= MINSTEM)
    lo_i, hi_i, common = lo_i[ok], hi_i[ok], common[ok]
    print(f"\n   cells in both blocks with >= {MINSTEM} stems in both = {len(common):,}")

    # ---- lat/lon -> tile clusters, built in the STATISTIC's row order (never via a join: ADR 0042
    #      section 7.3 fixed a bootstrap whose cluster labels were not row-aligned).
    maxc = int(max(common.max(), 0)) + 1
    lat = np.full(maxc, np.nan)
    lon = np.full(maxc, np.nan)
    for ln in LATLON.read_text().splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        f = ln.split()
        c = int(f[0])
        if c < maxc:
            lat[c], lon[c] = float(f[3]), float(f[4])
    if not (np.isfinite(lat[common]).all() and np.isfinite(lon[common]).all()):
        raise SystemExit("FATAL: missing lat/lon for some scored cell")
    tiles = (np.floor((lat[common] + 90.0) / TILE_DEG) * 100000
             + np.floor((lon[common] + 180.0) / TILE_DEG)).astype(np.int64)
    ut, tinv = np.unique(tiles, return_inverse=True)
    torder = np.argsort(tinv, kind="stable")
    ts = np.searchsorted(tinv[torder], np.arange(len(ut)))
    te = np.searchsorted(tinv[torder], np.arange(len(ut)), side="right")
    idx_by_tile = [torder[ts[i]:te[i]] for i in range(len(ut))]
    print(f"   {len(ut)} tiles   size min {min(len(x) for x in idx_by_tile)}  "
          f"median {int(np.median([len(x) for x in idx_by_tile]))}  max {max(len(x) for x in idx_by_tile)}")

    # ---- Delta arrays + both reliability ceilings
    DY, DP, CEIL, SDTRUE = {}, {}, {}, {}
    print("\n" + "=" * 108)
    print("RELIABILITY CEILING -- logged stem parity vs the corrected patch-year parity")
    print("=" * 108)
    print(f"   {'axis':10s} {'rh_stem':>9s} {'rel_stem':>9s} {'ceil_stem':>10s} "
          f"{'rh_py':>9s} {'rel_py':>9s} {'ceil_py':>10s} {'d_ceil':>9s} {'sd_true ratio':>14s}")
    for a in AXES:
        dy = ymed[a][hi_i] - ymed[a][lo_i]
        DY[a] = dy
        row = {}
        for tag, halves in (("stem", yh_stem[a]), ("py", yh_py[a])):
            h0, h1 = halves
            d0 = h0[hi_i] - h0[lo_i]
            d1 = h1[hi_i] - h1[lo_i]
            m = np.isfinite(d0) & np.isfinite(d1)
            rh = float(np.corrcoef(d0[m], d1[m])[0, 1])
            rel = 2 * rh / (1 + rh) if rh > -1 else np.nan
            rel = float(min(max(rel, 0.0), 1.0))
            row[tag] = (rh, rel, np.sqrt(rel), float(np.std(dy)) * np.sqrt(rel))
        CEIL[a] = {k: v[2] for k, v in row.items()}
        SDTRUE[a] = {k: v[3] for k, v in row.items()}
        print(f"   {a:10s} {row['stem'][0]:9.4f} {row['stem'][1]:9.4f} {row['stem'][2]:10.4f} "
              f"{row['py'][0]:9.4f} {row['py'][1]:9.4f} {row['py'][2]:10.4f} "
              f"{row['py'][2] - row['stem'][2]:+9.4f} {row['py'][3] / row['stem'][3]:14.4f}")
        for nm in ARMS:
            DP[(nm, a)] = pmed[(nm, a)][hi_i] - pmed[(nm, a)][lo_i]
    print("   PREDICTION under test: patch-year parity LOWERS the ceiling and RAISES |Ra-1|, because")
    print("   the stem-parity halves share their patch-years and so omit the between-patch-year term.")

    # ---- GATE
    print("\n" + "=" * 108)
    print(f"GATE -- reproduce ADR 0042 section 5's logged {GATE_AXIS} response table (stem-parity basis)")
    print("=" * 108)
    if GATE_AXIS not in AXES:
        raise SystemExit(f"FATAL: GATE_AXIS {GATE_AXIS} not in AXES {AXES}")
    dy_g = DY[GATE_AXIS]
    sdt_stem = SDTRUE[GATE_AXIS]["stem"]
    print(f"   meanDobs = {dy_g.mean():+.5g}   (logged {LOGGED_MEANDOBS:+.5g}, "
          f"d = {dy_g.mean() - LOGGED_MEANDOBS:+.3g})")
    print(f"   ceiling  = {CEIL[GATE_AXIS]['stem']:.4f}   (logged {LOGGED_CEIL_STEM:.4f}, "
          f"d = {CEIL[GATE_AXIS]['stem'] - LOGGED_CEIL_STEM:+.4f})")
    allrows = np.arange(len(dy_g))
    ok_gate = True
    print(f"\n   {'arm':16s} {'Rr':>9s} {'log':>8s} {'d':>9s} | {'Ra':>8s} {'log':>7s} {'d':>9s} "
          f"| {'Rb':>10s} {'log':>9s} {'d':>9s}")
    for nm, (_pdir, _fm, (lrr, lra, lrb)) in ARMS.items():
        rr, ra, rb = response_stats(DP[(nm, GATE_AXIS)], dy_g, sdt_stem, allrows)
        drr, dra, drb = rr - lrr, ra - lra, rb - lrb
        bad = abs(drr) > 5e-4 or abs(dra) > 5e-4 or abs(drb) > 1.0
        ok_gate &= not bad
        print(f"   {nm:16s} {rr:+9.4f} {lrr:+8.4f} {drr:+9.1e} | {ra:8.4f} {lra:7.4f} {dra:+9.1e} "
              f"| {rb:+10.1f} {lrb:+9.1f} {drb:+9.2f}  {'MISMATCH' if bad else 'OK'}")
    if not ok_gate:
        raise SystemExit(
            "FATAL: response reproduction gate FAILED. The bootstrap would be attached to different "
            "numbers than the ADRs quote. Fix the harness before interpreting anything "
            "(residual-diagnosis skill section 3)."
        )
    print("\n   GATE PASSED -- the paired noise scales below attach to the logged statistics.")

    # ---- paired bootstrap, both reliability bases
    for rel_tag in ("stem", "py"):
        print("\n" + "=" * 108)
        print(f"PAIRED TILE-CLUSTER BOOTSTRAP   reliability basis = {rel_tag}   NBOOT={NBOOT}")
        print("=" * 108)
        for a in AXES:
            sdt = SDTRUE[a][rel_tag]
            # Gate statistics are (Rr, |Ra-1|, Rb): the amplitude criterion is a DISTANCE from
            # perfect dispersion, so an arm that over- and one that under-disperses are both
            # penalised. Converting here keeps the paired differences on the gated quantity.
            def gstats(nm, sel):
                rr, ra, rb = response_stats(DP[(nm, a)], DY[a], sdt, sel)
                return rr, abs(ra - 1.0), rb

            full = {nm: gstats(nm, np.arange(len(DY[a]))) for nm in ARMS}
            rng = np.random.default_rng(BOOT_SEED)
            draws = {(t, b, s): np.empty(NBOOT) for t, b in PAIRS for s in ("Rr", "Ra1", "Rb")}
            marg = {(nm, s): np.empty(NBOOT) for nm in ARMS for s in ("Rr", "Ra1", "Rb")}
            for k in range(NBOOT):
                pick = rng.integers(0, len(ut), size=len(ut))
                sel = np.concatenate([idx_by_tile[i] for i in pick])
                cur = {nm: gstats(nm, sel) for nm in ARMS}
                for nm, v in cur.items():
                    for j, s in enumerate(("Rr", "Ra1", "Rb")):
                        marg[(nm, s)][k] = v[j]
                for t, b in PAIRS:
                    for j, s in enumerate(("Rr", "Ra1", "Rb")):
                        draws[(t, b, s)][k] = cur[t][j] - cur[b][j]
            print(f"\n-- {a}   ceiling {CEIL[a][rel_tag]:.4f}   sd_true {sdt:.5g}   "
                  f"meanDobs {DY[a].mean():+.5g}")
            print(f"   {'arm':16s} {'Rr':>9s} {'sd':>7s} | {'|Ra-1|':>8s} {'sd':>7s} "
                  f"| {'Rb':>10s} {'sd':>8s}")
            for nm in ARMS:
                r = full[nm]
                print(f"   {nm:16s} {r[0]:+9.4f} {marg[(nm,'Rr')].std():7.4f} | "
                      f"{r[1]:8.4f} {marg[(nm,'Ra1')].std():7.4f} | "
                      f"{r[2]:+10.1f} {marg[(nm,'Rb')].std():8.1f}")
            print(f"\n   PAIRED deltas (treatment - matched baseline, same fold mode & colouring)")
            print(f"   {'pair':30s} {'stat':6s} {'point':>10s} {'sd_paired':>10s} "
                  f"{'2.5%':>10s} {'97.5%':>10s} {'|pt|/sd':>8s} {'P(<=0)':>7s}")
            for t, b in PAIRS:
                for j, s in enumerate(("Rr", "Ra1", "Rb")):
                    d = draws[(t, b, s)]
                    d = d[np.isfinite(d)]
                    pt = full[t][j] - full[b][j]
                    sd = float(d.std())
                    lo, hi = np.percentile(d, [2.5, 97.5])
                    z = abs(pt) / sd if sd > 0 else np.inf
                    print(f"   {t + ' - ' + b:30s} {s:6s} {pt:+10.4f} {sd:10.4f} "
                          f"{lo:+10.4f} {hi:+10.4f} {z:8.2f} {float((d <= 0).mean()):7.3f}")
        print("\n   The `sd_paired` column IS the number the Phase-0 acceptance thresholds are")
        print("   multiples of. Quote paired deltas only -- never a blocked LEVEL on its own")
        print("   (re-colouring moves a single-arm blocked level ~10x more than a paired delta).")

    print("\n" + "=" * 108)
    print("DONE")
    print("=" * 108)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
