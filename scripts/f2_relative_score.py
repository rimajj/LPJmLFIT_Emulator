#!/usr/bin/env python3
"""Re-score learned-daily-model arms on the second-run error ratio (ADR 0317 measure, ADR 0325).

Usage: python scripts/f2_relative_score.py [tag ...]   (default: RE_5seed)

Reads DATA/runs/<tag>/annual.npz only (no model, seconds). Basis, per held-out cell with a
2021-2100 mean GPP >= 50 gC m-2 yr-1 (the ADR 0320 L2 mask):
  emulator error  e_E = |E_k - T_k| / |T_k|   member k's emulator (run on member k's stand) vs
                                               member k of the original, pooled over k = 1..4
  second run      e_R = |T_j - T_k| / |T_k|   every ordered pair j != k of the original
  ratio rho_p = P_p[e_E] / P_p[e_R] over (cell, member) for p = 50 (typical) and 90 (bad cells).
Timescales: 30-year windows 2021-2050 and 2071-2100 (the structure standard's window), and single
years (normalised by the cell's 2021-2100 mean, so a near-zero NPP year cannot blow up a ratio).
Response: |dE - dT| vs |dR - dT|, d = (2071-2100) - (2021-2050). Area totals: cos-lat weighted
sum over the same cells, relative error, emulator vs second run. Drift: the single-year ratio per
decade; drift (owner, ADR 0325) = the gap to the original GROWING, scored as the 2081-2100 over the
2021-2040 single-year ratio, so a transient change in the values themselves is not drift.
Harness rows: "second run" (member j as the emulator; must be ~1.0) and "oracle" (mean of the
three other members; Gaussian expectation sqrt((1+1/3)/2) = 0.82). Derived before running.
"""

import os
import sys
from itertools import permutations

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f2_train as F  # noqa: E402

V = ("gpp", "et", "npp", "runoff")
EARLY, LATE, ALL = slice(1, 31), slice(51, 81), slice(1, 81)  # 2021-2050, 2071-2100, 2021-2100


def _pairs_err(t, est, norm):
    """est: list of (k, array (nc, ...)) estimates of member k; |est - t_k| / norm_k pooled."""
    return np.concatenate([(np.abs(e - t[k]) / norm[k]).ravel() for k, e in est])


def ratios(t, e, mask, kind):
    """t, e: (4, nc, NY) for one variable. Returns dict of statistic -> value."""
    t = t[:, mask].astype(np.float64)
    e = e[:, mask].astype(np.float64)
    ms = range(4)
    if kind == "second run":  # member j stands in for the emulator of member k (harness)
        e_est = [(k, t[(k + 1) % 4]) for k in ms]
    elif kind == "oracle":
        e_est = [(k, t[[j for j in ms if j != k]].mean(0)) for k in ms]
    else:
        e_est = [(k, e[k]) for k in ms]
    r_est = [(k, t[j]) for j, k in permutations(ms, 2)]
    out = {}
    for name, sl in (("win early", EARLY), ("win late", LATE)):
        tw = t[:, :, sl].mean(2)
        nrm = np.abs(tw)
        eE = _pairs_err(tw, [(k, x[:, sl].mean(1)) for k, x in e_est], nrm)
        eR = _pairs_err(tw, [(k, x[:, sl].mean(1)) for k, x in r_est], nrm)
        for p in (50, 90):
            out[f"{name} p{p}"] = np.percentile(eE, p) / np.percentile(eR, p)
        out[f"{name} 2nd-run p50"] = np.percentile(eR, 50)
    # response
    d = lambda x: x[..., LATE].mean(-1) - x[..., EARLY].mean(-1)  # noqa: E731
    dt = d(t)
    rE = np.concatenate([np.abs(d(x) - dt[k]) for k, x in e_est])
    rR = np.concatenate([np.abs(d(x) - dt[k]) for k, x in r_est])
    for p in (50, 90):
        out[f"response p{p}"] = np.percentile(rE, p) / np.percentile(rR, p)
    # single years, by decade (drift)
    nrm = np.abs(t[:, :, ALL].mean(2))[:, :, None]
    dec = []
    for d0 in range(1, 81, 10):
        sl = slice(d0, d0 + 10)
        eE = _pairs_err(t[:, :, sl], [(k, x[:, sl]) for k, x in e_est], nrm)
        eR = _pairs_err(t[:, :, sl], [(k, x[:, sl]) for k, x in r_est], nrm)
        dec.append(np.percentile(eE, 50) / np.percentile(eR, 50))
    out["year p50 by decade"] = dec
    out["drift"] = np.mean(dec[-2:]) / np.mean(dec[:2])
    return out


def totals(t, e, w, mask):
    """Area-total relative error over 2021-2100 per member; emulator and second run (worst abs)."""
    tt = (w[mask] * t[:, mask][:, :, ALL].mean(2)).sum(1)  # (4,)
    ee = (w[mask] * e[:, mask][:, :, ALL].mean(2)).sum(1)
    em = np.abs(ee / tt - 1)
    sr = np.array([abs(tt[j] / tt[k] - 1) for j, k in permutations(range(4), 2)])
    return em.mean(), sr.mean()


def main():
    tags = sys.argv[1:] or ["RE_5seed"]
    cells = pl.read_parquet(os.path.join(F.DATA, "cells.parquet"))
    ho = cells["heldout"].to_numpy()
    w = np.cos(np.radians(cells["lat"].to_numpy()))
    J = {v: i for i, v in enumerate(F.ANNUAL)}
    for tag in tags:
        z = np.load(os.path.join(F.DATA, "runs", tag, "annual.npz"))
        print(f"\n## {tag}  (ratio = emulator error / second-run error; 1.00 = a second run)\n")
        print(
            "| leg | flux | kind | 30-yr p50 early/late | 30-yr p90 early/late "
            "| response p50/p90 | single-year p50 per decade 2021..2100 | drift "
            "| area total err (2nd run) | 2nd-run 30-yr p50 |"
        )
        print("|---|---|---|---|---|---|---|---|---|---|")
        for leg in F.ALL_LEGS:
            t, fr = z[f"truth__{leg}"], z[f"free__{leg}"]
            mask = ho & (t[:, :, ALL, J["gpp"]].mean(2).mean(0) >= 50)
            for v in V:
                # harness rows once; one-step rows on the held-out climates separate a
                # carried-store drift (free grows, one-step flat) from extrapolation (both grow)
                kinds = ("free",)
                if v == "gpp" and leg == "ctl_obs":
                    kinds += ("second run", "oracle")
                if leg in F.TEST_LEGS:
                    kinds += ("onestep",)
                for kind in kinds:
                    e = z[f"onestep__{leg}"] if kind == "onestep" else fr
                    r = ratios(t[..., J[v]], e[..., J[v]], mask, kind)
                    te, ts = (
                        totals(t[..., J[v]], e[..., J[v]], w, mask)
                        if kind in ("free", "onestep")
                        else (np.nan, np.nan)
                    )
                    dec = " ".join(f"{x:.1f}" for x in r["year p50 by decade"])
                    w50 = f"{r['win early p50']:.2f}/{r['win late p50']:.2f}"
                    print(
                        f"| {leg} | {v} | {kind} | {w50} "
                        f"| {r['win early p90']:.2f}/{r['win late p90']:.2f} "
                        f"| {r['response p50']:.2f}/{r['response p90']:.2f} | {dec} "
                        f"| {r['drift']:.2f} "
                        f"| {te:.3f} ({ts:.3f}) | {r['win late 2nd-run p50']:.4f} |"
                    )
        print(f"\ncells scored per leg: {int(mask.sum())} held-out cells with mean GPP >= 50")


if __name__ == "__main__":
    main()
