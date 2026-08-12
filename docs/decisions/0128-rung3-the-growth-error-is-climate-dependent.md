# ADR 0128 — Rung 3 under climate change: F's growth error IS climate-dependent, and the fast core's own warming response in carbon uptake is WRONG at the temperate prototype and SIGN-WRONG in the Sahel

- **Status:** accepted
- **Date:** 2026-08-12
- **Line:** M (multi-cell coupled S+F+E) · ADR block 0120–0139
- **Consumes:** ADR 0127 (the three-channel decomposition and the harness this re-runs), ADR 0125/0126
  (the historic-window rung-3 result and the per-PFT parameters), ADR 0106 (the acceptance criterion,
  whose binding clause this is), ADR 0111 §9 (band a response ratio and guard its denominator), ADR 0093
  §5 (quote the target's own noise floor with every fidelity number), ADR 0004/0107 (constant CO2)
- **Supersedes:** nothing. **Closes the item** that ADR 0125 §7.4 and three successive line-M handoffs
  listed as *"cheap and still unmeasured … the acceptance criterion's binding clause"*.

## 1. Context — the one thing rung 3 had never measured

`EXECUTION_PLAN.md` rung 3 is *"F alone, on the C's own canopy"*, and its exit gate is that the growth
error is quantified and either fixed or bounded. Every F-vs-C growth number in this repo — ADR 0053, 0060,
0125, 0126, 0127 — is on the **historic 2010–2019** window. ADR 0106's acceptance criterion is explicitly
binding on climate change (*"of course also and especially under climate change"*), and the project's
central open failure is that the emulator's warming response is wrong. **Nobody had asked whether the fast
core's own error is the same size in a warmed world.**

## 2. What was run

The ADR 0127 harness, unchanged in its physics, on the **ssp370 2090–2099** window: F is restarted from
the C's own roster every year and each stem scored against its own next-year row, exactly as in the
historic arm. Four arms (A = beech everywhere; Abg = A + the seeded below-ground pool; P = per-cohort PFT
parameters, ADR 0126; Pbg = P + the seed).

Enabling changes, all one-line and all default-preserving: `SCENARIO`/`IND_PARQUET` env knobs on
`scripts/build_biome_stem_growth_reference.py` and `scripts/extract_cell_individuals.py`, and
`SCENARIO`/`Y0`/`Y1`/`FORCING_DIR` on `scripts/biome_sapwood_bg_probe.jl`. The per-cell ssp370 daily
forcing comes from the existing `scripts/build_hainich_response_forcing.py` (`SITE=<name>`), which gates
its own read against each cell's committed historic forcing fixture — **all five cells passed that gate at
≤1.8e-5**, which is what proves the cell index, the YEARCELL decode, the mixed v2/v3 `.clm` scalar branch
and the units.

**THE CONTROL, and it is what licenses the comparison:** the same probe re-run on the historic window
after the scenario refactor reproduces its own committed table **byte-identically** and still passes ADR
0125's 20-number basis gate. Logs `logs/M-sapbgctl2.1765953.out` (control) and
`logs/M-sapbgssp2.1765952.out` (ssp370).

## 3. ⚠ FIRST, THE YARDSTICK — there was none, and it changes which cells can be read at all

The target is stochastic and no noise floor for *this* quantity existed. Measured from the two existing
ground-truth seeds (`scripts/diagnose_c_assimilate_noise.py`; per-cell annual tree assimilate, `Type<=6 &
D95max>0`, living **and** dead, over the configured 25 patches):

| cell | level floor, historic | level floor, ssp370 | **the C's own warming change** (2-seed mean ± spread) | signal / floor |
|---|---|---|---|---|
| boreal_siberia | 1.0 % | 8.2 % | +36.7 ± 20.5 | **1.8** |
| temperate_hainich | 5.3 % | 6.0 % | **−33.9 ± 1.4** | **24.2** |
| mediterranean_iberia | 12.6 % | 8.6 % | −121.4 ± 43.4 | **2.8** |
| semiarid_sahel | 8.4 % | 1.8 % | +77.6 ± 11.6 | **6.7** |
| tropical_amazon | 2.1 % | 1.0 % | −248.6 ± 30.4 | **8.2** |

⇒ **at two of the five cells the truth's own warming response is not determined at two seeds** (boreal 1.8,
mediterranean 2.8, against ADR 0111 §9's S/N ≥ 3 bar). Those cells are reported as **unresolved**, not as
passes or failures. This is the quantitative case for the two extra reference seeds `EXECUTION_PLAN.md`
rung 0 already asks the integrator for.

Cross-check: this unpaired population reproduces the probe's paired `bmi_C` to **<0.2 %** at Hainich
(489.9 vs 489.0) and the Amazon (1073.2 vs 1072.5) — two independent readers, one run.

## 4. The result

`assimilate_response` = (F's change between the two windows) / (the C's own change), with **the same
stands and the same forcing on both sides in both windows**, so the stand difference between the decades
is controlled by construction. 1 = exactly right, 0 = no response, < 0 = wrong sign.

Arm **Pbg** — per-cohort PFT parameters + the seeded below-ground pool, the most faithful configuration
that exists today (`test/testitems/references/M_growth_channel_climate_response.csv`):

| cell | `bmi_F/C` historic | `bmi_F/C` ssp370 | change | **response** | verdict |
|---|---|---|---|---|---|
| boreal_siberia | 1.251 | 1.204 | −0.047 | 1.02 | **unresolved** (truth S/N 1.8) |
| temperate_hainich | 1.196 | 1.277 | **+0.081** | **0.08** | **FAIL — F reproduces 8 % of a decline determined to 4 %** |
| mediterranean_iberia | 2.864 | 3.338 | **+0.474** | 2.25 | **unresolved** (truth S/N 2.8) |
| semiarid_sahel | 1.119 | **0.657** | **−0.461** | **−0.34** | **FAIL on SIGN** |
| tropical_amazon | 1.066 | 1.063 | −0.003 | 1.08 | **PASS** |

Arm A (the published historic basis) gives the same picture where it is readable — Hainich **0.02**,
Amazon 0.46 — and is uninterpretable at the two hot cells, whose arm-A assimilate is negative (the ADR 0125
`respcoeff` defect).

**Three statements, in decreasing strength:**

1. **The fast core's carbon uptake barely responds to warming at the temperate prototype.** The C's own
   assimilate falls **−33.9 ± 1.4 gC/m²/yr** (both seeds; the tightest response signal of the five, S/N 24)
   and F's moves **−2.8** — 8 %. This is not a level bias re-expressed: F's *level* error at Hainich is
   +20 % in both windows, so the level and the response fail independently.
2. **In the semi-arid cell F moves the wrong way.** The C's assimilate rises **+77.6 ± 11.6** and F's falls
   **−28.6**. The level ratio drops out of band with it, **1.119 → 0.657**.
3. **The tropical cell passes** (response 1.08, level 1.066/1.063 against a 1–2 % floor).

**So the level and the response are not the same test, and passing one does not imply the other.** Under
arm Pbg the assimilate ratio is inside `[0.8, 1.25]` at three cells in each window — **but not the same
three**: the Sahel leaves the band under warming and Hainich drifts out of it. A configuration validated on
the historic decade is not thereby validated under climate change.

## 5. Consequences

1. **Rung 3 cannot exit on the historic window alone.** Its exit gate must be scored in both climates. The
   harness now does that with four environment variables and no code change; the recipe is in the probe
   header and in `lines/M/STATE.md`.
2. **The head of the F-side queue is confirmed and sharpened.** ADR 0127 re-pointed it from allocation to
   the assimilate; this ADR says the assimilate error is **not a stable multiplicative bias** — it is
   climate-dependent, and at Hainich the *response* is the more severe failure of the two. A fix that
   improves the historic level while leaving the response at 0.08 has not fixed rung 3.
3. **Two more reference seeds are now quantitatively justified** for this quantity too: 2 of 5 cells cannot
   be scored at two seeds. Raised to the integrator (`EXECUTION_PLAN.md` rung 0 already carries the ask).
4. **The below-ground pool's seed is confirmed harmless-to-helpful in both climates** — on the per-PFT
   arms it lowers the assimilate by **1.1–6.3 %** (historic) and **2.4–5.3 %** (ssp370), moving every
   readable cell toward the C. It does not change any verdict here.
5. **The three-channel decomposition holds in the warmed window** and the ranking is unchanged: at
   Hainich, arm A, the surplus is **+193.4 gC/m²/yr = +149.5 assimilate (77 %, exactly as historic)
   + 18.7 loss + 25.1 below-ground sink**; on arm Pbg, **+174.3 = 126.1 + 22.8 + 25.4 (72 %)**.

## 6. Scope — what this is NOT

* **Five cells of 54 020, one seed for the emulator arms, ten years per window.** A mechanism result, not
  fidelity evidence (ADR 0106).
* The two windows are different decades of different runs, so the **stands** differ as well as the climate.
  That is controlled for the response statistic — F is handed the C's own stand in both windows, so both
  sides see the same stand and the same weather — but it is not a clean climate-only contrast for any
  statement about the *stand*.
* **Both arms use the historic per-cell soil column.** `whc_nat` evolves with soil carbon in the C
  (ADR 0050), so F's water holding capacity in the ssp370 window is an approximation. It is the same
  approximation in every arm, so it cannot manufacture a between-arm difference; it *can* bias the
  between-window one, and the Sahel — the cell that fails on sign — is the one where that matters most.
  **Closing it is the first thing to check before treating the Sahel sign error as physics.**
* CO2 is ~409.63 ppm in both windows (the historic 2019 value and the ADR 0004 constant from 2020), so the
  contrast is climate-only. The emulator's lack of a CO2 response is **not** at issue here (ADR 0107).
* `slow = nothing` throughout: this is F alone on the C's own canopy, with no demography.
