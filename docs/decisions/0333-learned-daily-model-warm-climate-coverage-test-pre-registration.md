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
