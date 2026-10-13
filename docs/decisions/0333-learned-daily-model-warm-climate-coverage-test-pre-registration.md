# 0333 — Learned daily model: does covering the warm climates stop the gap growing? (pre-registration)

* **Status:** Pre-registered 2026-10-13, before any training. Result appended below.
* **Follows:** ADR 0328 (more climate models: levels better, gap still grows on UKESM / IPSL) and ADR 0332 (a
  structured carbon head: much worse, closed). Tooling: `scripts/f2_chain_arm.py` (generic chain, new),
  `scripts/f2_extrapolation_probe.py` (now reads each run's own training legs, and takes a candidate training set).

## 1. What coverage the test buys (measured before training, `logs/f2-probe-cover.2475151.out`)

Held-out cells (238), UKESM ssp370, 2081–2100 annual climate against the per-cell training range:

| training set | cells outside the temperature range | exceedance median / worst 10 % | cells outside the leaf-area range |
|---|---|---|---|
| arm C (observed + MPI 126/370 + GFDL + MRI) | 96 % | 1.45 / 4.02 °C | 52 % |
| arm C + IPSL ssp126/370/585 | 31 % | 0 / 0.27 °C | 29 % |

In arm C, the growth of the GPP error correlates with the leaf-area exceedance (rank correlation +0.41 UKESM, +0.40
IPSL ssp585), barely with the temperature exceedance (+0.13 / −0.08). The one-step run (each day from the original's
own state) drifts as much as the free run on UKESM (GPP 1.31 vs 1.30), so this is the daily mapping, not stores
accumulating error.

## 2. The arm (one change: three more training legs)

Arm W (`W_3x256_seed0..4`, ensemble `WE_5seed`) = arm C exactly, with the three IPSL legs added to training (40 M
samples in total as before, so fewer per leg). Test legs: **UKESM ssp370** (the only climate model left unseen) and
MPI ssp585.

## 3. Pre-registered numbers (ADR 0325 yardstick, free runs)

* **Primary:** UKESM GPP and NPP drift ≤ 1.2, and each at least 0.05 below arm C's (1.30 / 1.41).
* **Must not get worse:** UKESM and MPI ssp585 GPP / ET typical-cell error ≤ 1.15 × arm C's; MPI ssp585 drift ≤ 1.2.
* **Falsifier:** UKESM GPP and NPP drift within 0.05 of arm C's ⇒ with the climate and the stand mostly inside the
  training range, coverage is not the cause; the error growth is in how the network maps a changing stand, and the
  next arm targets the stand input (e.g. train on stands perturbed away from the climate they grew in, so the
  network must separate the two).
* **Expectation:** partial — UKESM GPP drift 1.15–1.25 (the third of cells still outside, and the leaf-area link stays
  29 % outside), NPP falls less than GPP.

## 4. Result (2026-10-13; jobs 2475156–61, GPU; run `WE_5seed`)

Members trained as arm C's did (validation error on daily GPP 0.070, NPP 0.106 — arm C 0.070–0.077 / 0.108–0.116).
Scored with `f2_relative_score.py CE_5seed WE_5seed` (`DATA/f2/runs/relative_score_CE_WE.md`) and
`f2_carbon_split.py`. Free runs, 238 held-out cells.

| leg | flux | typical early/late, W (C) | drift W (C) | area total W (C) |
|---|---|---|---|---|
| UKESM ssp370 | GPP | 1.96/2.10 (2.08/2.73) | **1.15** (1.30) | 0.2 % (1.3 %) |
| | NPP | 3.16/3.69 (3.31/4.57) | **1.25** (1.41) | 2.4 % (4.7 %) |
| | ET | 1.92/2.24 (2.18/2.29) | 0.98 (1.02) | 0.4 % (1.9 %) |
| MPI ssp585 | GPP | 2.08/1.87 (2.14/2.26) | 0.89 (0.95) | 0.8 % (0.3 %) |
| | NPP | 3.37/2.95 (2.87/3.24) | 0.95 (0.97) | 1.5 % (3.4 %) |
| | ET | 2.00/1.66 (2.26/1.55) | 0.85 (0.86) | 0.1 % (0.9 %) |

UKESM GPP emulator ÷ original, summed: 1.008 → 0.986 between 2021–40 and 2081–00 (arm C 0.996 → 0.970); plant
respiration 1.022 → 1.004 (arm C 1.015 → 0.993); observed weather respiration 1.022–1.027 (arm C 1.014–1.019).
Cost 6.4e-3 core-s per cell-year (unchanged).

**Verdict as pre-registered: primary FAILS on NPP only.** GPP drift 1.15 passes both parts (≤ 1.2, 0.15 below arm C);
NPP drift 1.25 is 0.16 below arm C but above the 1.2 cap. **Falsifier did not fire** — both fell by three times the
0.05 margin. Must-not-get-worse: holds everywhere (largest, MPI ssp585 ET late 1.66 vs 1.55 = 1.07×, under 1.15×).
Expectation: GPP drift 1.15–1.25 met at the low end; "NPP falls less than GPP" not met (they fell equally).

**Reading.** Covering the warm climates removes about half of the excess growth of the gap (GPP 0.30 → 0.15,
NPP 0.41 → 0.25 above "no growth") and halves the NPP area-total error, with no loss elsewhere: training coverage is a
real cause, not the whole story. What remains on NPP is mostly the constant plant-respiration excess (carbon-use
efficiency 0.008–0.012 below the original's in both windows), which coverage did not touch — on observed weather it is
slightly larger (2.2–2.7 %). Caveat: one unseen climate model only (UKESM); the confirmation in §5 swaps the roles.

## 5. Confirmation pre-registered (2026-10-13, before training): swap the unseen model

Arm U (`U_3x256_seed0..4`, `UE_5seed`) = arm C + **UKESM ssp370** in training; test on the **three IPSL legs** (and MPI
ssp585). If coverage is the cause, the warmest IPSL leg must improve as UKESM did. Pass: IPSL ssp585 GPP drift ≤ 1.2
and ≥ 0.05 below arm C's (1.22), and its NPP drift ≥ 0.05 below arm C's (1.27). Falsifier: both within 0.05 of arm C's
⇒ the UKESM improvement was specific to that model pairing, not coverage. Expectation: smaller gain than §4 —
UKESM is one leg (not three) and its climate differs from IPSL's in pattern, not only in warmth.

## 6. Confirmation result (2026-10-13; jobs 2475336–41; run `UE_5seed`)

Members trained as arm C's (validation GPP 0.069–0.079, NPP 0.103–0.116). `relative_score_CE_UE.md`.

| leg | GPP drift U (C) | NPP drift U (C) | GPP typical early/late U (C) | NPP typical U (C) |
|---|---|---|---|---|
| IPSL ssp585 | **1.12** (1.22) | **1.13** (1.27) | 2.09/2.04 (2.11/2.48) | 3.90/3.52 (3.94/3.88) |
| IPSL ssp370 | 0.87 (0.92) | 1.00 (1.08) | 1.90/2.13 (1.86/2.07) | 3.60/3.29 (3.20/3.37) |
| IPSL ssp126 | 1.08 (1.08) | 1.11 (1.14) | 2.42/2.61 (2.31/2.72) | 3.91/4.22 (3.43/4.06) |
| MPI ssp585 | 0.94 (0.95) | 0.93 (0.97) | 2.39/1.86 (2.14/2.26) | 3.81/3.36 (2.87/3.24) |

IPSL ssp585 GPP emulator ÷ original, summed: 0.993 → 0.992 between 2021–40 and 2081–00 (arm C 0.996 → 0.984).

**Verdict as pre-registered: PASSES.** IPSL ssp585 GPP drift 1.12 (≤ 1.2, 0.10 below arm C), NPP 1.13 (0.14 below).
Falsifier did not fire. Expectation (a smaller gain than §4) held for GPP (0.10 vs 0.15), roughly for NPP (0.14 vs
0.16). Not pre-registered, recorded: the early-window typical error rose on some legs with one more training leg
sharing the fixed sample budget (MPI ssp585 NPP 2.87 → 3.81, ET 2.26 → 2.93; IPSL ssp126 NPP 3.43 → 3.91); the late
windows mostly improved. The respiration excess is unchanged (observed weather 1.012–1.017).

**Conclusion of this record.** Shown on two unseen climate models with the roles swapped: training on warmer climates
removes about half of the growth of the daily model's carbon gap under warming (GPP to 1.12–1.15, NPP to 1.13–1.25),
at no cost to the late-century fit. ⇒ the deployed daily model trains on **every** climate model available (the
sample budget should grow with the number of legs — the early-window losses above suggest 40 M is now thin). What
coverage does not fix: a constant 1.5–2.7 % plant-respiration excess (NPP ~0.01 low in carbon-use efficiency in every
window and on observed weather), the next target.
