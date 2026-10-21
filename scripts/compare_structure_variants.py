#!/usr/bin/env python3
"""compare_structure_variants.py -- pairwise arithmetic for yearly forest-map variants (ADR 0349 / 0351).

Usage: python scripts/compare_structure_variants.py REF_SUFFIX CAND_SUFFIX [CAND_SUFFIX ...] [--dense anchor|truth]
       (suffixes as given to final_structure_score.py via SUFFIX, e.g. _rerun _soilcat; "" = the stored map)

Reads xpanel/eval/final_structure_<dense><suffix>.csv (emulator rows). Per group (dense/sparse) and quantity: the
median over the 15 cases of CAND rho50 / REF rho50 and of rho90, the number of cases where CAND is lower, and both
runs' median rho50; then the relaxed-standard criteria (ADR 0318 sec. 2) each run passes (median <= limit AND
>= 12 of 15 cases), listing any criterion that passes in REF and fails in CAND. Seconds.
"""

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_panel_prep as PP  # noqa: E402

LIM = {"D1": ("dense", "rho50", 1.2), "D2": ("dense", "rho90", 1.5), "S1": ("sparse", "rho50", 3.0)}
TOT = {"D3": ("dense", 0.05), "S2": ("sparse", 0.25)}


def load(suffix: str, dense: str) -> pl.DataFrame:
    f = os.path.join(PP.OUT, "eval", f"final_structure_{dense}{suffix}.csv")
    return pl.read_csv(f).filter(pl.col("cand") == "emulator")


def criteria(d: pl.DataFrame) -> dict[str, bool]:
    out = {}
    for c, (grp, col, lim) in LIM.items():
        for q, x in d.filter(pl.col("grp") == grp).group_by("q"):
            v = x[col].to_numpy()
            out[f"{c} {q[0]}"] = bool(np.nanmedian(v) <= lim and (v <= lim).sum() >= 12)
    for c, (grp, lim) in TOT.items():
        x = d.filter((pl.col("grp") == grp) & (pl.col("q") == "n_per_patch"))
        for col in ("tot_stems", "tot_biomass"):
            v = np.abs(x[col].to_numpy())
            out[f"{c} {col}"] = bool(np.nanmedian(v) <= lim and (v <= lim).sum() >= 12)  # NaN skipped, as the scorer
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dense = "truth" if "--dense" in sys.argv and sys.argv[sys.argv.index("--dense") + 1] == "truth" else "anchor"
    args = [a for a in args if a not in ("anchor", "truth")]
    ref_s, cands = args[0], args[1:]
    ref = load(ref_s, dense)
    cref = criteria(ref)
    print(f"reference {ref_s or '(stored)'}: {sum(cref.values())} of {len(cref)} criteria pass (dense by {dense})")
    for cs in cands:
        c = load(cs, dense)
        j = c.join(ref, on=["leg", "grp", "q"], suffix="_ref")
        t = (j.group_by("grp", "q").agg(
            (pl.col("rho50") / pl.col("rho50_ref")).median().alias("ratio50"),
            (pl.col("rho90") / pl.col("rho90_ref")).median().alias("ratio90"),
            (pl.col("rho50") < pl.col("rho50_ref")).sum().alias("cases_better"),
            pl.col("rho50_ref").median().alias("ref_rho50"), pl.col("rho50").median().alias("cand_rho50"),
            pl.len().alias("cases")).sort("grp", "q"))
        cc = criteria(c)
        lost = [k for k in cref if cref[k] and not cc.get(k, False)]
        gained = [k for k in cref if not cref[k] and cc.get(k, False)]
        with pl.Config(tbl_rows=20, float_precision=3, tbl_width_chars=160):
            print(f"\n== {cs} vs {ref_s or '(stored)'}: {sum(cc.values())} of {len(cc)} criteria pass; "
                  f"lost {lost or 'none'}; gained {gained or 'none'}")
            print(t)


if __name__ == "__main__":
    main()
