#!/usr/bin/env python3
# =============================================================================
# growth_channel_climate_response.py — DOES F's GROWTH ERROR DEPEND ON CLIMATE?
#
# WHY THIS EXISTS. ADR 0106's acceptance criterion is binding on the CLIMATE-CHANGE
# clause ("of course also and especially under climate change"), and rung 3 had
# never measured it: every F-vs-C growth number in this repo is on the historic
# 2010-2019 window. This script differences the two committed decomposition tables
# that `scripts/biome_sapwood_bg_probe.jl` writes — historic 2010-2019 and
# ssp370 2090-2099 — into the response statistics, so the headline is computed by
# a script rather than read off two printed tables by eye (ADR 0104's rule).
#
# THE COMPARISON IS "F RESTARTED FROM THE C's OWN STAND, IN TWO CLIMATES", and its
# limits must ride with every number:
#   * the two windows are DIFFERENT DECADES of DIFFERENT RUNS, so the stands differ
#     in age structure and composition as well as in climate. This is not a paired
#     experiment on one set of stems; it is the question "is the per-year growth
#     error the same size in a warmed world?", which is the one rung 3 must answer.
#   * both arms use the HISTORIC per-cell soil column (`M_soilcolumn_<name>.txt`).
#     `whc_nat` evolves with soil carbon in the C, so the ssp370 arm's water
#     holding capacity is an approximation (ADR 0050).
#   * CO2 is ~409.63 ppm in BOTH windows (historic 2019 and the ADR 0004 constant
#     from 2020), so the contrast is climate-only — which is what makes it readable.
#   * five cells of 54 020, seed1, `slow = nothing`. Not fidelity evidence.
#
# Usage:  python3 scripts/growth_channel_climate_response.py
# Env:    HIST / SSP (table paths) · OUT (the committed response table)
# =============================================================================
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
HIST = os.environ.get("HIST", os.path.join(REFDIR, "M_growth_channel_decomposition.csv"))
SSP = os.environ.get("SSP", os.path.join(REFDIR, "M_growth_channel_decomposition_ssp370.csv"))
OUT = os.environ.get("OUT", os.path.join(REFDIR, "M_growth_channel_climate_response.csv"))

# cold -> hot, the canonical registry order
CELLS = ["boreal_siberia", "temperate_hainich", "mediterranean_iberia",
         "semiarid_sahel", "tropical_amazon"]
ARMS = ["A", "Abg", "P", "Pbg"]

HEADER = """\
# M_growth_channel_climate_response.csv — does F_diff's per-year growth error depend on
# CLIMATE? (ADR 0106's binding clause; ADR 0127 §9). The historic 2010-2019 and ssp370
# 2090-2099 decomposition tables, differenced. F is restarted from the C's own stand
# every year in BOTH windows, so this is the per-year growth error in two climates.
#   bmi_ratio_*         = F's annual assimilate over the C's, per window (1.0 = right)
#   bmi_ratio_change    = ssp - historic. > 0 means the error GROWS under warming.
#   assimilate_response = (bmi_F_ssp - bmi_F_hist) / (bmi_C_ssp - bmi_C_hist): how much
#                         of the C's OWN warming change in assimilate F reproduces.
#                         1 = exactly, 0 = no response, < 0 = wrong sign.
#   dagb_ratio_*        = F's paired per-stem above-ground increment over the C's.
# ⚠ The two windows are different decades of different runs, so the STANDS differ too;
# both arms use the HISTORIC soil column; CO2 is ~409.63 ppm in both, so the contrast is
# climate-only. Five cells of 54 020, seed1, slow=nothing — NOT fidelity evidence.
# scripts/growth_channel_climate_response.py
"""



def read(path):
    rows = {}
    hdr = None
    for ln in open(path):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        f = s.split(",")
        if hdr is None:
            hdr = f
            continue
        r = dict(zip(hdr, f, strict=True))
        rows[(r["arm"], r["cell"])] = {
            k: (v if k in ("arm", "cell") else float(v)) for k, v in r.items()
        }
    return rows


def main():
    h, s = read(HIST), read(SSP)
    out = []
    for arm in ARMS:
        for cell in CELLS:
            a, b = h.get((arm, cell)), s.get((arm, cell))
            if a is None or b is None:
                continue
            # the LEVEL statistic on each side: F's assimilate over the C's, and F's surplus
            # above-ground increment as a multiple of the C's own increment
            rh = a["bmi_F"] / a["bmi_C"]
            rs = b["bmi_F"] / b["bmi_C"]
            gh = a["dagb_F"] / a["dagb_C"]
            gs = b["dagb_F"] / b["dagb_C"]
            # the RESPONSE statistic: how much of the C's own warming change does F reproduce?
            # 1.0 = exactly; 0.0 = F does not respond; < 0 = wrong sign.
            dC = b["bmi_C"] - a["bmi_C"]
            dF = b["bmi_F"] - a["bmi_F"]
            resp = dF / dC if abs(dC) > 1e-9 else float("nan")
            out.append(dict(
                arm=arm, cell=cell,
                bmi_ratio_hist=rh, bmi_ratio_ssp=rs, bmi_ratio_change=rs - rh,
                dagb_ratio_hist=gh, dagb_ratio_ssp=gs,
                bmi_C_hist=a["bmi_C"], bmi_C_ssp=b["bmi_C"], d_bmi_C=dC,
                bmi_F_hist=a["bmi_F"], bmi_F_ssp=b["bmi_F"], d_bmi_F=dF,
                assimilate_response=resp,
                surplus_hist=a["surplus"], surplus_ssp=b["surplus"],
                t_input_hist=a["t_input"], t_input_ssp=b["t_input"],
                t_loss_hist=a["t_loss"], t_loss_ssp=b["t_loss"],
                t_nosink_hist=a["t_nosink"], t_nosink_ssp=b["t_nosink"],
            ))

    hdr = list(out[0].keys())
    with open(OUT, "w") as f:
        f.write(HEADER)
        f.write(",".join(hdr) + "\n")
        for r in out:
            f.write(",".join(
                f"{r[k]:.6g}" if isinstance(r[k], float) else str(r[k]) for k in hdr
            ) + "\n")
    print(f"wrote {OUT}  ({len(out)} rows)")

    for arm in ARMS:
        print(f"\n=== arm {arm} — F's assimilate error, historic vs ssp370 ===")
        print(f"{'cell':24s} {'bmi_F/C hist':>12s} {'ssp':>8s} {'change':>8s} "
              f"{'dC':>8s} {'dF':>8s} {'response':>9s}")
        for cell in CELLS:
            r = next((x for x in out if x["arm"] == arm and x["cell"] == cell), None)
            if r is None:
                continue
            print(f"{cell:24s} {r['bmi_ratio_hist']:12.3f} {r['bmi_ratio_ssp']:8.3f} "
                  f"{r['bmi_ratio_change']:+8.3f} {r['d_bmi_C']:8.1f} {r['d_bmi_F']:8.1f} "
                  f"{r['assimilate_response']:9.2f}")
    print("\n`change` > 0 at every cell => F's carbon-input error is LARGER in the warmed world.")
    print("`response` far from 1 => F does not track the C's own warming change in assimilate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
