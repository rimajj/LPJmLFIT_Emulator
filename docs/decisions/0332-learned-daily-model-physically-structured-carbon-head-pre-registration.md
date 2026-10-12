# 0332 — Learned daily model with a physically structured carbon head (pre-registration)

* **Status:** Pre-registered 2026-10-12, before implementation and before any run. Result appended below.
* **Follows:** ADR 0328 §4 (more climate models: the falsifier fired — the gap to the original still grows under the
  two warmest unseen climate models, so "the next arm is a physically constrained carbon head").
* Tooling: `scripts/f2_train.py --carbon-head physical` (new, opt-in; default `free` = the existing head, unchanged).

## 1. What the failure looks like (measured 2026-10-12 from arm C's and the control's saved annual totals)

Held-out cells (238), sums over cells and members, emulator ÷ original:

| leg | GPP 2021–40 → 2081–00 | plant respiration (GPP − NPP) | NPP/GPP original → emulator, 2081–00 |
|---|---|---|---|
| observed weather | 0.995 → 0.999 | 1.014 → 1.019 | 0.413 → 0.401 |
| MPI ssp585 | 0.997 → 0.993 | 1.019 → 1.014 | 0.384 → 0.372 |
| UKESM ssp370 | 0.996 → **0.970** | 1.015 → 0.993 | 0.366 → 0.350 |
| IPSL ssp585 | 0.996 → **0.984** | 1.015 → 1.004 | 0.367 → 0.354 |

(arm C; the control is the same shape, its GPP 1.3 % higher throughout.) Two separate defects: **(a)** under the
warmest climates the learned photosynthesis falls 1.5–3 % behind the original by the end of the century (two thirds
of cells low); **(b)** plant respiration is 1.5–3 % too high on *every* leg, observed weather included — a constant
bias, and the cause of arm C's 3–5 % NPP area-total error. The fall of the original's carbon-use efficiency under
warming (0.41 → 0.37) is tracked; it is not the problem. ADR 0327 §4: the growth of the error goes with how far the
stand's leaf area exceeds any training run (Spearman +0.41 GPP).

## 2. The arm (one change: the carbon head)

Arm P (`P_3x256_seed0..4`, ensemble `PE_5seed`) = arm C exactly (same training legs, 40 M samples, 3 × 256 trunk,
no humidity input, deep drainage D/365, five seeds), except that GPP and NPP come from a structured head; the water
fluxes still come from the trunk as before.

* **GPP = ε · rsds · (1 − exp(−0.5 · LAI)) · f_T · f_W · f_L · f_S**, ε > 0 a learned scalar; each limiter is a
  small separate network (2 × 64) squashed to (0, 1) that sees only its own inputs:
  f_T: today's, 10-day and 30-day air temperature · f_W: soil water (fraction of capacity, mm, capacity), snow,
  today's / 30 / 90 / 365-day rain, net longwave · f_L: radiation today and 30-day, day length, day of year, latitude ·
  f_S: stand leaf area, vegetation carbon, cover by plant type. 0.5 is the original's light-extinction coefficient for
  the layered canopy (`k_lambert`).
  *Why it should help (a):* GPP is linear in absorbed light at a fixed limiter, so more leaf area than any training run
  raises GPP through the original's own canopy law instead of a learned saturation; and the temperature limiter is a
  function of temperature only, learned across all cells — today's hot places teach it what a warmed cold place does
  (space for time), which a joint network has no reason to do.
* **NPP = A − R_m − 0.25 · max(A − R_m, 0)** with A = (1 − c_d) · GPP — the original's own form (`npp_tree.c:52`,
  growth respiration `r_growth` 0.25): c_d ∈ (0, 0.3) a learned scalar (leaf dark respiration share);
  R_m = B_w · g(T_air) + B_r · g(T_mix), g the original's temperature response
  `exp(308.56 · (1/56.02 − 1/(T + 46.02)))`, 0 below −40 °C (`temp_response.c:33`); B_w ≥ 0 a network of the stand
  only, B_r ≥ 0 of the stand and the season (day of year, day length, latitude) — the original's root term carries leaf
  phenology; T_mix a learned blend of today's and 30-day air temperature (the original uses top-layer soil
  temperature, which follows air temperature with no lag at four of five test cells, CLAUDE.md §3).
  *Why it should help (b):* respiration's temperature dependence is fixed to the original's, so the network only has to
  learn how much respiring biomass a stand holds.

## 3. Pre-registered numbers (ADR 0325 yardstick, `scripts/f2_relative_score.py`, free runs, held-out cells)

* **Primary (same as ADR 0328's):** arm P's GPP and NPP drift (single-year error ratio 2081–2100 ÷ 2021–2040) ≤ 1.2 on
  UKESM ssp370 and on each IPSL leg, **and** lower than arm C's on the same leg.
* **Secondary:** NPP area-total error ≤ 2 % on every leg (arm C: 2.9–4.8 %); plant respiration emulator ÷ original
  within 1 % of 1 on observed weather (arm C 1.014–1.019).
* **Must not get worse:** GPP / ET typical-cell error on the MPI legs ≤ 1.15 × arm C's and ≤ 3× a second run; MPI
  drift ≤ 1.2; cost ≤ 0.01 core-s per cell-year (the ADR 0320 speed bar).
* **Falsifier:** arm P's UKESM GPP and NPP drift within 0.05 of arm C's ⇒ the growth is not an extrapolation-form
  problem; next is to test whether it is the stand input (phase B's emulated stand, or leaf area by plant type).
* **Expectation:** UKESM 2081–2100 GPP emulator ÷ original moves from 0.970 to ≥ 0.985; respiration bias falls below
  1 %; typical-cell levels worsen by 0–15 % (the structure costs flexibility), most on GPP in the tropics, where light
  is not limiting and f_W carries the signal.

## 4. Result (2026-10-13; jobs 2474216–21, GPU; run `PE_5seed`)

Training: every member's validation error on daily GPP / NPP is **2.3× / 2.2× arm C's** (normalised squared error
0.165–0.177 vs 0.070–0.077 GPP, 0.227–0.245 vs 0.108–0.116 NPP), consistently over five seeds; the water fluxes
match arm C's (the trunk is unchanged). Scored with `f2_relative_score.py CE_5seed PE_5seed`
(`DATA/f2/runs/relative_score_CE_PE.md`) and `f2_carbon_split.py`.

| leg | GPP typical early/late, P (C) | NPP typical, P (C) | GPP drift P (C) | NPP drift P (C) |
|---|---|---|---|---|
| UKESM ssp370 | 5.48/6.72 (2.08/2.73) | 6.89/12.69 (3.31/4.57) | **1.42** (1.30) | **1.73** (1.41) |
| IPSL ssp126 | 6.03/5.86 (2.31/2.72) | 5.79/5.80 (3.43/4.06) | 1.01 (1.08) | 1.05 (1.14) |
| IPSL ssp370 | 5.23/5.84 (1.86/2.07) | 6.03/9.06 (3.20/3.37) | 1.03 (0.92) | 1.27 (1.08) |
| IPSL ssp585 | 5.57/6.74 (2.11/2.48) | 6.76/9.70 (3.94/3.88) | 1.30 (1.22) | 1.77 (1.27) |
| MPI ssp126/370/585 | 4.86–5.91 (1.89–2.26) | 6.46–8.25 (2.87–3.54) | 0.87–1.09 | 0.93–1.21 |

**Verdict: FAILS on every pre-registered count.** Primary: drift ≤ 1.2 and below arm C only for GPP on IPSL ssp126
(1.01 vs 1.08; its NPP 1.05 vs 1.14 likewise) — UKESM and IPSL ssp585 are worse than arm C on both fluxes.
Secondary: NPP area totals 1.2–4.9 % (≤ 2 % on 8 of 14 legs, not all); respiration on observed weather **1.053**
(arm C 1.014–1.019, target within 1 %) — worse. Must-not-worsen: MPI GPP typical 4.9–5.9× a second run (bar ≤ 1.15 ×
arm C and ≤ 3×) — **fails by 2.5×**; ET unchanged (1.8–2.6×) ✓; MPI drift ≤ 1.21 (NPP ssp585 1.21, just over) ✗;
cost 9.3e-3 core-s per cell-year ✓ (≤ 0.01, but 45 % above arm C's 6.4e-3). The falsifier as written ("within 0.05 of
arm C") did not fire, because the effect was large **in the wrong direction** (UKESM +0.12 GPP, +0.32 NPP).

**Against the expectations.** The level loss was 2.5–3×, not 0–15 %. The expected mechanism did not appear either:
UKESM GPP emulator ÷ original went 1.021 → 0.976 between 2021–40 and 2081–00 (a fall of 0.045, against arm C's 0.026),
i.e. **the structured head under-responds to warming more than the free network**, although it gets more leaf area
through the original's own canopy law and a temperature limiter that sees temperature only.

**Reading.** The original's daily GPP is not a product of separable limiters: its photosynthesis co-limits light and
Rubisco and couples water stress to temperature and light through the stomatal solve, so a separable form loses
most of the daily skill. The late-century shortfall survives — larger — with leaf area entering through the
canopy law, so it is not a learned saturation in leaf area; and a temperature-only limiter learned across all cells
(space for time) does not transfer the response either. This form is closed; `--carbon-head physical` stays as an
opt-in record, default off. A constrained head would need the co-limitation itself (a light × capacity minimum), which
is close to re-implementing the original's photosynthesis — not pre-registered here.
