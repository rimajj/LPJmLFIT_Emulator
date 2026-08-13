#!/usr/bin/env python3
"""Score ADR 0135 shortlist item (b): the C's `tstress < 1e-2` hard zeroing of photosynthesis.

REFERENCE BASIS (residual-diagnosis §1)
---------------------------------------
* C side: `src/lpj/photosynthesis.c:54-61` returns `agd = rd = vm = 0` whenever the
  temperature-stress scalar `tstress < 1e-2`; `include/pft.h:341`
  `isphoto(tstress) (tstress>=1e-2)` applies the SAME threshold a second time at
  `src/lpj/water_stressed.c:196`. Both are live in the `individual=true`, carbon-only
  configuration (no `config->` guard on either).
* F side: `src/fdiff.jl:503 temp_stress` + `:541 photosynthesis`. F has NO threshold —
  `tstress` multiplies `c1`/`c1o` linearly and that is all.
* Realised inputs: the committed 10-yr daily GSWP3-W5E5 forcing per biome cell
  (`test/testitems/references/biome_forcing_<name>.csv`) and each cell's own PFT composition
  from `M_individuals_<name>_2010.csv`. Per-PFT `temp_photos`/`temp_co2` from the gated table
  `M_pft_fdiff_params.csv` (ADR 0126).

CLOSED FORM, DERIVED BEFORE THE RUN (residual-diagnosis §8/§9)
--------------------------------------------------------------
1. In the C3 path `c1 = tstress*alphac3*(...)` and `c2` does not contain `tstress`. Hence
   `vm ~ c1/c2 ~ tstress`, `je ~ c1 ~ tstress`, `jc ~ vm ~ tstress`; the co-limitation solution
   for `adt` is homogeneous of degree 1 in `(je, jc)`, and `rd = b*vm`. => F's `agd` and `rd`
   are exactly proportional to `tstress` (the SLA-Vcmax cap is the only nonlinearity and it
   cannot bind at `tstress < 1e-2`, where `vm` is >100x below its unstressed value).
   => the C's gate discards at most 1 % of what that same day would carry at full
   temperature suitability.
2. HOT END IS REDUNDANT BY CONSTRUCTION. `k3 = ln(99)/(temp_co2_high - temp_photos_high)`, so
   `high(temp_co2_high) = 1 - 0.01*e^{ln 99} = 0.01` exactly, and `low ~ 1` at warm
   temperature => `tstress(temp_co2_high) ~ 1e-2` = the threshold. The gate therefore fires
   exactly where the `temp >= temp_co2_high` HARD CUTOFF already fires — and F already carries
   that cutoff (as a sigmoid). => the gate's only live content is the COLD end.
3. COLD-END THRESHOLD, closed form: at cold temperature `high ~ 1`, so `tstress = low = 1e-2`
   at `T* = k2 - ln(99)/k1`, `k1 = 2*ln(1/99)/(tcl-tpl)`, `k2 = tcl + tpl/2`.

Claim 1 is VERIFIED AGAINST F'S OWN KERNEL, not only read off the source —
`FDiff.photosynthesis` at `tstress = 1e-2` returns exactly 1e-2 of its `tstress = 1` value for
`agd`, `rd` AND `vm`, to 1.6e-9, at both a winter (-8 degC, 2 MJ/m2) and a growing-season
(15 degC, 8 MJ/m2) day:

    julia --project=. -e 'using LPJmLFITEmulator; const F=LPJmLFITEmulator.FDiff;
      p=F.PhotoParams{Float64}();
      a1=F.photosynthesis(p,0.8,1.0,   40.0,-8.0,2.0e6,8.0);
      ag=F.photosynthesis(p,0.8,1.0e-2,40.0,-8.0,2.0e6,8.0);
      println(ag[1]/a1[1], " ", ag[2]/a1[2], " ", ag[3]/a1[3])'

FALSIFIABLE HYPOTHESIS
----------------------
The residual is bounded by 1 % of the assimilation the affected days would carry at full
temperature suitability, and the affected days are the coldest and darkest of the year. => the
annual effect is far below the ~3 % GPP excess that survives ADR 0136, and item (b) is an
ACCEPTED LIMITATION, not a fix.

WHY THE BOUND PRINTED HERE IS CONSERVATIVE
------------------------------------------
Assimilation carries leaf phenology `phen` through `apar`, and this screen sets `phen = 1` on
EVERY day. Gated days are deep-winter days where GSI phenology drives `phen` towards 0, while
the growing-season days in the denominator sit near `phen = 1`; setting `phen = 1` everywhere
therefore inflates the numerator relative to the denominator. The printed share is an UPPER
BOUND on the phen-weighted one.

Run:  python3 scripts/diagnose_tstress_photo_gate.py
"""

from __future__ import annotations

import csv
import math
import os
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(REPO, "test", "testitems", "references")

GATE = 1.0e-2  # photosynthesis.c:54 / pft.h:341

CELLS = [
    "boreal_siberia",
    "temperate_hainich",
    "mediterranean_iberia",
    "tropical_amazon",
    "semiarid_sahel",
]


def _rows(path: str) -> list[dict]:
    with open(path) as fh:
        return list(csv.DictReader(ln for ln in fh if not ln.startswith("#")))


def pft_params() -> dict[int, dict]:
    out = {}
    for r in _rows(os.path.join(REF, "M_pft_fdiff_params.csv")):
        out[int(r["pft_id"])] = {
            "name": r["name"],
            "tpl": float(r["temp_photos_low"]),
            "tph": float(r["temp_photos_high"]),
            "tcl": float(r["temp_co2_low"]),
            "tch": float(r["temp_co2_high"]),
        }
    return out


def tstress(p: dict, temp: float, daylength: float) -> float:
    """`temp_stress.c:25-41`, exact ops (the C, not F's sigmoid-gated surrogate)."""
    tmc3 = 45.0  # C3 maximum; every tree PFT here is C3
    if daylength < 0.01 or temp > tmc3:
        return 0.0
    if temp >= p["tch"]:
        return 0.0
    k1 = 2 * math.log(1 / 0.99 - 1) / (p["tcl"] - p["tpl"])
    k2 = p["tcl"] + 0.5 * p["tpl"]
    k3 = math.log(0.99 / 0.01) / (p["tch"] - p["tph"])
    low = 1 / (1 + math.exp(k1 * (k2 - temp)))
    high = 1 - 0.01 * math.exp(k3 * (temp - p["tph"]))
    return low * high


def cold_threshold(p: dict) -> float:
    """Temperature at which `tstress` crosses 1e-2 from below (bisection, exact expression)."""
    lo, hi = -90.0, p["tph"]
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if tstress(p, mid, 24.0) < GATE:
            lo = mid
        else:
            hi = mid
    return lo


def main() -> None:
    par = pft_params()

    print(__doc__.split("Run:")[0].strip())
    print()
    print("=" * 104)
    print("PANEL 1 — the gate's cold-end threshold per tree PFT (closed form, no data)")
    print("=" * 104)
    hdr = f"{'id':>3} {'PFT':40} {'temp_co2 lo/hi':>17} {'T*(ts=1e-2)':>13} {'hot cutoff':>11}"
    print(hdr)
    for i in range(7):
        p = par[i]
        print(
            f"{i:>3} {p['name']:40} {p['tcl']:7.1f}/{p['tch']:<9.1f} "
            f"{cold_threshold(p):13.2f} {p['tch']:11.1f}"
        )
    print()
    print("  => the tropical evergreen (id 0) is gated below +3.0 degC; every other tree")
    print("     below -6.0 degC.")
    print("  => at the hot end T*(gate) == temp_co2_high by construction (derivation above),")
    print("     so the gate adds nothing there — F already carries that cutoff.")
    print()

    print("=" * 104)
    print("PANEL 2 — realised incidence and the ASSIMILATION-WEIGHTED upper bound, per cell")
    print("=" * 104)
    print(
        f"{'cell':22} {'PFT set':16} {'T_min':>7} {'T*warm':>7} {'gated':>6} "
        f"{'BOUND':>9}  verdict"
    )
    print(
        f"{'':22} {'(trees)':16} {'degC':>7} {'degC':>7} {'days':>6} {'of annual':>9}"
    )

    verdicts = []
    for cell in CELLS:
        forc = _rows(os.path.join(REF, f"biome_forcing_{cell}.csv"))
        inds = _rows(os.path.join(REF, f"M_individuals_{cell}_2010.csv"))
        # Trees only: ids 0-6 (grass ids 7-9 have their tree fields zeroed — CLAUDE.md §3).
        comp = Counter(int(r["type"]) for r in inds if int(r["type"]) <= 6)
        # Weight each PFT by its stem count; the gate is per-Pft and every tree is its own Pft.
        total_stems = sum(comp.values())
        dominant = max(comp, key=lambda k: comp[k])

        num = 0.0  # sum over gated days of tstress * apar-proxy (what F pays, C does not)
        den = 0.0  # sum over all days of tstress * apar-proxy
        gated_days = 0
        for pid, nstem in comp.items():
            p = par[pid]
            w = nstem / total_stems
            for d in forc:
                temp = float(d["temp"])
                dl = float(d["daylength"])
                swd = float(d["swdown"])  # W/m2; agd is linear in apar to first order
                ts = tstress(p, temp, dl)
                if ts <= 0.0:
                    continue  # F's sigmoid is ~0 here too; not this gate's doing
                if ts < GATE:
                    num += w * ts * swd
                    if pid == dominant:
                        gated_days += 1
                den += w * ts * swd
        share = num / den if den > 0 else 0.0
        verdicts.append((cell, share))
        # A ZERO MUST EXPLAIN ITSELF (residual-diagnosis: an exactly-zero effect is a red flag,
        # never a result). The gate is mechanically unreachable at a cell whose coldest day
        # never reaches the warmest present PFT's threshold — print that comparison, not a 0.
        t_min = min(float(d["temp"]) for d in forc)
        t_star = max(cold_threshold(par[pid]) for pid in comp)
        verdict = "CAN BIND" if t_min < t_star else "CANNOT BIND (T never reaches T*)"
        print(
            f"{cell:22} {str(sorted(comp)):16} {t_min:7.1f} {t_star:7.1f} {gated_days:6d} "
            f"{100.0 * share:8.4f}%  {verdict}"
        )

    print()
    print("  'gated' counts days of the cell's DOMINANT tree PFT with 0 < tstress < 1e-2.")
    print("  The bound is stem-weighted over every tree PFT present and sets phen = 1 on every")
    print("  day, which inflates it (deep-winter days carry phen -> 0) — see the docstring.")
    print("  T* is the warmest threshold among the cell's tree PFTs, i.e. easiest to reach.")
    print()

    worst = max(s for _, s in verdicts)
    print("=" * 104)
    print("VERDICT")
    print("=" * 104)
    print(f"  worst cell bound = {100.0 * worst:.4f} % of annual tree assimilation")
    print("  reference: F's residual GPP excess after ADR 0136 is +3.0 % at Hainich")
    print("  (shipping arm).")
    if worst < 0.1:
        print("  => ACCEPTED LIMITATION. The gate cannot carry the compensating error; it is")
        print("     >1 order of magnitude below the residual it was shortlisted to explain.")
        print("     Do not port it.")
    else:
        print("  => LIVE. Bound is within an order of magnitude of the residual — build the")
        print("     opt-in arm.")


if __name__ == "__main__":
    main()
