# EXECUTION_PLAN.md — the current program (revision 3, owner instructions 2026-10-10)

**Revision 3 (2026-10-10).** Two owner decisions change *who* works and *what counts as passing*, not the method
inventory below:

> *"change of plans. the otehr lines stem frmo the beginning of the project, where slow and fast part was deevlopte
> in parralel, as well as the coupling etc. abandon this. I want you to deveop all, no seperation in different
> lines"* (ADR 0319)

> *"I think we have to relax the passing standarts a bit. as long as the dense ells are fine and the sparse cells
> dont drift away completely we should go on. AS before the goal is to have a full LPJmL_FIT emulator that emulates
> everything happening in the mode orders of magnitude faster thatn lpjmlfit and does not drift away in transient
> runs"* — and: *"We also want to simulate teh fast physcs structure!!!"* (ADR 0318)

So: **one development stream** (§9 is now a priority list, not per-line assignments; the "lines" columns below are
history), **the daily exchange is learned** (F2 first; F1 parked unless F2 fails), and **the relaxed standard of
ADR 0318 §2** replaces §0.1's per-cell 10 % rule as the working pass test. Previous version: `git show
2d52f0eb:EXECUTION_PLAN.md`.

**Read this after `CLAUDE.md` and `STATE.md`.** It is the executable program: what is worked on, what decides which
method survives, and what must not be started yet. `DEVELOPMENT_PLAN.md` stays the
stable phased architecture; `STEERING_PROMPT.md` is older and its ordering is superseded by this file.

**Revision 2 replaces the 2026-08-07 error-attribution ladder as the order of work.** The ladder did its job (§11
records what each rung found), and its findings plus a systematic literature review changed *how* we get to the
goal, not the goal itself. Owner, verbatim, 2026-10-08:

> *"based on the findings of this project so far and the findings in the review, update this projects plan. the
> goal stays the same, upate the plan on how to get there if necessary. try all promising methods"*

Evidence and reasoning: **ADR 0096** (the decision) and **`docs/review_comparison.md`** (the comparison against
115 published emulator/hybrid studies, with quotes). Previous version: `git show a0f2cbba:EXECUTION_PLAN.md`.

**Training venue (owner, 2026-10-08, ADR 0313):** the emulator arms train on M. Billing's global standard-trait runs (8 GFDL-ESM4 members × historical + ssp126/245/370, 6 reanalysis members; `/p/projects/open/Jamir/esm_land_emulator_data/billing_global/`), no longer on the Germany runs; **D2 is cancelled**.

**Track D status (2026-10-08):** launched — see §3 and ADR 0246; data under `/p/projects/open/Jamir/esm_land_emulator_data/trackD/` (README there).

**Ownership:** since revision 3 there is one developer; this file is edited like any other, with a revision note.

---

## 0. The goal (ADR 0094, 0106, 0107; restated and the pass test relaxed 2026-10-10, ADR 0318)

1. **Faithful — everything the model does** (forest structure AND the daily carbon/water exchange), "especially under
   climate change". **Working pass test (revision 3, ADR 0318):** dense cells as close as a second run of the
   original (proposed: typical error ≤ 1.2×, worst 10 % ≤ 1.5×, area totals within 5 %), sparse cells must not run
   away (typical ≤ 3×, totals within 25 %), and **no drift in transient runs**. Measured on all 54 020 tree-bearing
   cells for the final verdict. (Superseded wording: `max(10 %, two-run spread)` on every cell, ADR 0106 / 0317.)
2. **Orders of magnitude faster than LPJmL-FIT** — a first-class deliverable, measured end to end.
3. **Coupled to the ESM.**

**CO2: the emulator does not see CO2 and must not respond to it** (ADR 0004/0107; closed — do not re-litigate).

**The speed gate, with the numbers measured since 2026-08-07:**

| configuration | core-s per cell-year | source |
|---|---|---|
| emulator today, full coupled, 25 patches, 1 core | **1.233** (4.62× slower than the original) | ADR 0084 (supersedes ADR 0093's 1.096 / 3.8×) |
| the original, 25 patches | 0.267 (biome range 0.20–0.33) | ADR 0084, 0312 |
| the original, ~500 patches (publication setting) | **7.06** (Hainich) / 4.19 (Amazon); 99.9 % of it is the patch ensemble | ADR 0086 |
| the original, Germany production setting (250 patches) | ~12 | `lines/X/STATE.md` |
| **T63-class allowance** (intermediate) | **≤ 0.030** | convention: 10 % of a measured SpeedyWeather coupled cost |
| **T31-class allowance** (target) | **≤ 0.0135** | same |

The allowances are a convention, not an owner budget; against a CMIP-class 1° atmosphere (~50 core-s per
land-column-year) nothing binds. **Always name the atmosphere a speed claim is measured against.**

---

## 1. Why the "how" changed — seven findings

1. **The warming response is not identifiable in the data we have.** Within one scenario, 76.4 % of a cell's
   warming is predictable from its baseline climate (ADR 0311); the effective sample is ~161 independent 15° tiles
   (ADR 0310). Two members disagree on the per-cell response sign in 18.7–42.2 % of cells (ADR 0111). In Germany
   the usable window (1985–2044) carries almost no scenario contrast, and the 2071–2100 years were run with the
   humidity setting missing. ⇒ **data that identify the response come first (Track D)**; no architecture can be
   judged on the binding clause without them. Literature: present-day perfect, 2100 response badly wrong (R00289).
2. **The demography's failure is a ROLLOUT failure of a one-step-trained operator.** One-step R² 0.982 vs a
   persistence null of 0.962; free-running, the aggregate response flips +0.707 → −0.226 through rectification
   (ADR 0113–0116). Every published remedy — rollout loss with increment targets (R00067, R00593), fitting on the
   free-running trajectory (R00661), a signed zero-sum segment loss (R01133), retraining on the model's own rollout
   states — is untried here. "XGB specifically drifts at long lead times" (R00067) describes our configuration.
3. **Mortality must be a rate, not a count target.** A count target cannot carry a gross mortality budget
   (needed precision 1.1–1.2 %, irreducible floor 4.1–4.6 %; ADR 0241); the original's per-tree hazard applied as
   a rate meets the criterion as a ceiling (ADR 0242). This matches the literature consensus: the learned part
   predicts rates, the host keeps the pools (R00342, R00278).
4. **The re-implemented daily physics is both the speed problem and an unexplained fidelity problem.** Growth
   1.6–4× too fast at three of five cells, Mediterranean GPP 1.61× with the shortlist of causes exhausted, GPP
   warming response 8 % of the original's at Hainich and the wrong sign at the Sahel (ADR 0125, 0128, 0139). No
   speed-up has landed since 2026-08-07. In the literature the large speed-ups come from **learning the expensive
   step or solver** (R02497 18×; R00568 +3 % cost inside LPJmL; ecLand MLP ≈4800×), not from re-implementing it.
5. **At production patch counts the patch ensemble is the dominant cost**, and atmosphere-facing fluxes converge
   within 1.7–6.6 % at a single patch while carbon/establishment do not (ADR 0086). ⇒ the old plan's "patch cut is
   LAST" is reversed: **fluxes on few patches, demography statistics from the emulator** is a first-class lever.
6. **The original's demography is 0.4–1.1 % of its runtime** (ADR 0312). Learning the demography alone buys no
   speed; its value is fidelity and removing the patch ensemble.
7. **No method has been shown to win; several are promising.** In Germany a cell-level LSTM holds 0.79–0.91 of
   held-out cells on an unseen climate model, but emits no trees and has a weak climate channel; per-tree boosted
   trees hold 0.34–0.46 and are nearly matched by their climate-blind twin. ⇒ **run all promising methods in
   parallel as arms on one shared yardstick, and kill them only by pre-registered criteria.**

**What is kept from the ladder:** its principle — **one variable per arm**, and never a coupled score without the
isolated scores beside it.

---

## 2. Program shape

Six tracks run **in parallel**. Decision points (§8) are the only places where arms are dropped.

| track | what it delivers | lines |
|---|---|---|
| **D — data** | runs of the original model in which the warming response is identifiable, plus enough members to calibrate | S (global panel), X (Germany) |
| **Y — the yardstick** | one scorer + one set of nulls applied to every arm | X (Germany), S (global panel) |
| **A — annual demography methods** | 8 arms, from hybrid-with-the-original's-physics to fully learned | S, X |
| **F — daily flux methods** | 3 arms: faster re-implemented physics, a learned daily water–carbon model, few-patch fluxes | M, O, E |
| **C — coupling & stability** | long-run stability gate, complete coupling interface, equilibrium initialiser, online self-test | M, E, X, O |
| **U — uncertainty** | predictive distributions calibrated against independent members | S |

**Venues, in order:** (1) **Germany** — 9 067 cells × 250 patches, 2 climate models, historical + SSP126/245/370,
2 seeds; the owner's first milestone is *"make a germany emulator work … then use the method for the global
emulator"* (2026-10-01). (2) **The global stratified panel** (D0) — ~1 000 cells over the ~161 tiles. (3) **The
five biome cells** — the physics debugging venue only. (4) **All 54 020 cells** — acceptance only.

---

## 3. Track D — data that can identify the response

| id | what | why | cost (derived) | owner |
|---|---|---|---|---|
| **D0** | **The global stratified panel** — ✅ DONE (ADR 0246): 105 contiguous 10-cell blocks = 1 050 cells, 20 climate strata, **96** distinct 15° tiles, the five biome cells included; `test/testitems/references/S_D0_panel_blocks.csv`. Contiguous because LPJmL runs only contiguous cell ranges. Replaces ad-hoc 5/12/674-cell panels for any global score | one comparable venue | none | **S** |
| **D1** | **Constant-climate controls of the original** — 🚀 LAUNCHED (ADR 0246), on D0, four members, via the model's own `fix_climate`: `ctl_obs` = observed 1990–2019 weather shuffled and recycled 2020–2100; `ctl_mpi370` = MPI-ESM1-2-HR ssp370 weather of 2015–2034 recycled (same-model control). Constant CO2 409.63 ppm as in every scenario leg. Not detrended (the built-in mechanism cannot; a 30-yr shuffled window has a stationary mean). The original's response is **scenario − control** | the original's own 2020–2100 change had never been split into climate response and continuing stand dynamics; R00661 isolates its response this way | ~2–3 core-s per block-year | **S** |
| **D2** | ❌ **CANCELLED 2026-10-08 on owner instruction (ADR 0313) before any job started — superseded by Billing's global runs.** *Was:* **Germany re-run with the humidity setting corrected** — ✅ APPROVED by the owner 2026-10-08 and 🚀 LAUNCHED (ADR 0246): all 12 members re-run **2045–2100** in one continuous run from production `restart_2044_nv.lpj` (the production 2045–2070 config + lastyear 2100), so 2045–2070 also gets a per-tree table for the first time; each member with the build its production run used (ssp245 = Feb-2026, row-gated automatically before submission); converted with line X's converter to window `w2045` | the only years in which the Germany scenarios separate | ~2 h on 2 048 cores per member (the per-tree table dominates) | produced on **line S's** branch (line X had a live session); **X** consumes it |
| **D3** | **A 3rd and 4th independent member on D0** — 🚀 LAUNCHED (ADR 0246): every block spun up from scratch for 1000 yr with random_seed 3 / 4 (ADR 0041: a new seed under restart is a clone), then 2000–2019, then every leg; **daily outputs** on six legs (hist, MPI × 3 scenarios, UKESM ssp370, ctl_obs) | calibrated uncertainty needs >2 members; the daily fluxes had **no** two-run spread | ~1 000 core-h for the whole panel campaign | **S** |
| **D4** | **Climate-contrast set on D0 from REAL scenarios** — 🚀 LAUNCHED (ADR 0246; **replaces** the earlier synthetic ×0.5/×1.5 rescaling): ISIMIP3b climate of five models (GFDL-ESM4, IPSL-CM6A-LR, MPI-ESM1-2-HR, MRI-ESM2-0, UKESM1-0-LL) × ssp126 / ssp370 / ssp585, four members, constant CO2. **Hold out ssp585 (the amplitude beyond training) and one whole model** as the out-of-distribution tests | breaks the place-vs-response confounding by construction with realistic co-variation of the variables: stylised T/P grids "failed to extrapolate effectively to the real CMIP6 climate scenarios" (R00430); delta grids work for totals but not composition (R00201) | included above; 65 new orderA forcing files (gated byte-identical procedure) | **S** |

Rules for every Track-D run: same binary as the reference it is compared to; **pinned to one node type**
(`#SBATCH --nodes=1`, CLAUDE.md §3); a subset run is compared only to other runs of the same subset, never row by
row to the global truth (ADR 0041); gate new members with `scripts/diagnose_ind_seed_independence.py`.

---

## 4. Track Y — one yardstick for every arm

**Statistics (all reported for every arm, every venue):**

1. **Level** — fraction of cells inside `max(10 %, two-member spread)` for stems, biomass, and the four trait
   medians and q05–q95 (ADR 0106).
2. **Response** — the aggregate (area-weighted, and per biome) response ratio, deattenuated (ADR 0111). Reference
   response = **scenario − control** once D1/D2 exist; until then scenario − historic, labelled as such.
3. **Free-run stability** — validity horizon; drift at leads 5/20/40/80 yr; **a within-training-period free run**
   (a free run inside the training years, which separates step bias from extrapolation — R00593's test).
4. **Speed** — end-to-end core-s per cell-year on one core, with the atmosphere it is compared against.
5. **Conservation** — carbon/water closure where the arm carries pools.

**Nulls, always in the same table:** persistence; the lookup/analog null; the **climate-blind twin** (same arm,
climate inputs frozen to the baseline); the **frozen-climate control** (ADR 0178); the other member as the
ceiling. **No one-step score is quoted without the free-run score beside it.**

**Tooling:** Germany — `scripts/explore_de_sh_eval.py` (line X's scorer, extended with statistics 3–5). Global
panel — line S's rung-2 scorers, extended to the same statistics. Both write one row per (arm, venue, statistic).

---

## 5. Track A — annual demography methods (all run; Germany first where the arm exists there)

| id | method | literature basis | owner | first step |
|---|---|---|---|---|
| **A1** | **Hybrid with the original's physics**: the original grows the stand, the emulator applies mortality as a per-tree **rate** from its own stress integrals (temperature integral exact and on; water integral next) | rates not counts (R00342, R00278); ADR 0242–0245 | **S** | ADR 0245's water probe (fidelity ≥ 0.867, nulls 0.78 / 1.00) + its cost |
| **A2** | **Rollout-trained recurrent stand/cell model** (the Germany LSTM, extended with a per-tree output stage), trained on increments scaled by their spread with a **rollout loss and a 4 → 8 → 16-year curriculum**, gradient clipping | R00067, R00593 (stable 4-yr free run), R01133 | **X** | add the rollout loss + curriculum to the existing LSTM; then the per-tree stage |
| **A3** | **Per-tree boosted trees retrained on their own free-run states** ("dataset aggregation" / "data as demonstrator"), targets from the original — in Germany via the C re-run driver, globally via the harness that plugs the original's physics into the loop | R00342 (trained on the host's trajectory, collapses on its own); out-of-corpus DAgger / DaD (`docs/review_comparison.md` §7) | **X** | one aggregation round on the TAB arm |
| **A4** | **Free-run calibration**: a handful of bias/response parameters fitted on the free-running trajectory, or a signed zero-sum loss over teacher-forced segments, on top of TAB and of the global count/rate model | R00661 (fits on the 1900–2100 free run), R01133 | **X** (Germany), **S** (global) | aimed at the rectification (86.7 % of declines vs 96.2 % of rises) |
| **A5** | **Neural set model with multi-step training** (D-NSET) | R00593 | **X** | finish the scoring already in progress |
| **A6** | **Per-tree NPP + loss model, sign by the original's own threshold** (the "margin" route) | — (no precedent) | **X** | line X's current NEXT |
| **A7** | **Direct non-recursive map**: 20–30-year climate window → state distribution, no rollout (the frozen sibling emulator's design; EcoDiffusion's non-autoregressive idea) — the benchmark every recursive arm must beat on response | R00514; frozen `emulator` (per-cell r ~0.9 at 2100) | **X** | re-score on the Track-Y statistics |
| **A8** | **Probabilistic state-transition model** (iLand-style transition probabilities) — exploratory, lowest priority | R01728 | **X** | only if a round-1 slot is free |

**Traits:** every arm that emits trees either predicts traits itself or uses the shipped copula sampler (S), scored
on the same statistics. The copula's survivor-training bias (+12.18 % on wood density, ADR 0174) is a known
defect any arm inherits if it uses it.

---

## 6. Track F — daily flux methods

| id | method | owner | first step | pass bar (DP-F) |
|---|---|---|---|---|
| **F0** | the original model's physics — the reference, and A1's physics | — | — | — |
| **F1** | **Re-implemented differentiable physics, made fast**: replace the finite-difference Newton derivative in the λ solve (`src/fdiff.jl:685-707`) with an analytic or implicit-function derivative, wire the precomputed temperature kinetics (≈1.36×, ADR 0087), replace the fixed 25 iterations by a convergence test (3 iterations measured 4.10× at −0.03 % GPP, but GPP is non-monotone ±2.1 % in the count) | **M** (owns the file); **O** measures | the two-line kinetics wiring, then the derivative | GPP/ET/growth ratios unchanged within ±0.5 % at the 5 cells; gradient gate green |
| **F2** | **Learned daily water–carbon model** with soil water as an explicit, residual-updated state and the bucket closed by construction; fluxes re-diagnosed from state each day (aiLand pattern). Inputs: daily forcing + the annual stand state. Energy stays physics (LPJmL-FIT has no energy target, ADR 0310). **Phase A, offline** on the existing ~1 TB daily dataset (spatial blocks + scenario hold-out); **phase B** (coupled) only if A passes | **O** (speed line; owns `ext/`), **M** reviews fidelity with the `fdiff-validate` oracle | phase A learnability test | annual GPP, ET, NPP within ±5 % of the original at ≥4 of 5 biome cells and on the D0 median; SSP370 change in GPP inside the original's two-member band at ≥4 of 5 cells; ≤ 0.01 core-s per cell-year |
| **F3** | **Few representative patches for the fluxes**, canopy = the emulator's ensemble-mean stand; demography statistics from Track A | **M**, **E** reviews (shares the soil column) | 1/3/5 patches vs 25 and 250 (Germany) | fluxes within 5 % of the full-ensemble original; measure the "mean of fluxes vs flux of the mean canopy" gap explicitly |

**Open-ended F fidelity hunts are paused until DP-F**, except where F1 must preserve fidelity. F's known residuals
(ADR 0125/0128/0139) stay documented; if F2 fails, they become the next round.

**Speed levers, re-ranked by the measurements:** (1) the per-tree daily step — F2 or F1; (2) fewer patches — F3;
(3) threads across cells (embarrassingly parallel, untouched); (4) GPU — last. Every lever reports the end-to-end
number from `scripts/bench_speed_gate.jl` and the matching original-model number.

---

## 7. Tracks C and U — coupling, stability, uncertainty

| id | what | owner | why |
|---|---|---|---|
| **C1** | **Long-run stability gate**: any coupled configuration runs 300 yr under recycled climate; its above-ground biomass must become stationary and sit inside the original's own variability under the same forcing. Today it drifts 1.39–5.15× per century (ADR 0055) | **M** | an ESM integrates for centuries; an emulator without a fixed point cannot be initialised from any equilibrium (DifferLand's drift penalty, R00383) |
| **C2** | **Close the coupling interface**: export reflected shortwave, upward longwave, runoff, snow; real wind and pressure in the coupled driver; add heterotrophic respiration with explicit litter/soil pools and fire, so net CO2 exchange is complete (port the original's decomposition, 4.6–6.6 % of its runtime) | **M** (+ **E** for the energy-side exports and wind/pressure) | review requirement 2: no published emulator closes the interface; keep pools explicit (R00755) |
| **C3** | **Equilibrium initialiser**: use an equilibrium predictor (the `vegemu` map, read-only) to start the forward emulator under a new climate; check with the functional restart test (write the state into a restart, let the original continue, measure the relaxation) | **X** | review requirement 1; PHASE (R01211), R00211 |
| **C4** | **Online**: a coupled self-test (learned component trained on the host's own output reproduces the host online) and a "no-learned-process" null, then the chosen fast configuration online | **O**, after DP-S | R00602, R02497 |
| **U1** | **Calibrated uncertainty**: per-cell predictive distributions scored by coverage and rank histograms against the D3 members; the coupler receives the ensemble expectation (worth +2.9 to +14.4 pp of cells in band, ADR 0093) | **S**, after D3 | R00157; the corpus has no emulator scored against seed spread |

---

## 8. Decision points — pre-registered (arm owners may TIGHTEN a threshold before running, never loosen it)

| id | when | question | rule |
|---|---|---|---|
| **DP-0** | D1 + D2 landed | does the original's own response have power? | signal-to-noise ≥ 2 on the primary aggregate response statistic with the four panel members (and the two Germany seeds). If not, D4's held-out ssp585 amplitude becomes the primary response test |
| **DP-A1** | each Track-A arm's first scored free run in Germany (held-out climate model, 1985 → 2044) | does it survive round 1? | survives if (a) cell pass rate ≥ 0.5 × the other-member ceiling, (b) stems and biomass per stem within ±10 % at 2044, and (c) it is **not worse than its climate-blind twin** (before DP-0) / **beats it by more than the member-to-member noise on the response** (after DP-0) |
| **DP-A2** | survivors scored on D0 + D4 | which arms go to all cells? | response ratio (deattenuated, vs the control) inside the original's two-member band on the held-out amplitude (ssp585) and the held-out climate model, with no more than 1 pp loss of level cells vs the best arm |
| **DP-F** | F1 and F2-phase-A scored on the 5 cells + D0 | which fast side? | the cheapest arm meeting its §6 pass bar. If none meets the response clause, the fast side is the bottleneck and gets the next round |
| **DP-C** | the chosen A arm + F arm coupled | is it stable? | C1 passes at ≥ 4 of 5 biome cells and on a D0 subsample |
| **DP-S** | after DP-C | is it fast enough? | end-to-end ≤ 0.030 core-s per cell-year (T63) at the chosen patch count, then ≤ 0.0135 |
| **Accept** | after DP-S | done? | §0 on all 54 020 cells, both scenarios and the response |

⚠ **If the best arm fails a decision point, that is the finding, not a failed test** — record it in an ADR and say
which statistic failed. Do not re-read a criterion after seeing its arm (the ADR-0104 error).

---

## 9. Priorities now (revision 3: one stream, in this order; details and the live NEXT in `STATE.md`)

| # | work | why first | done when |
|---|---|---|---|
| 1 | **F2 — learned daily water–carbon model, phase A offline** (§6) | the missing half of "everything", and the speed lever: the original spends 51–69 % of its runtime in leaf gas exchange + soil water (ADR 0312); nothing exists yet | DP-F bar (§6) on held-out spatial blocks and a held-out scenario, with nulls |
| 2 | **Structure map (A7 family, ADR 0315–0318): dense-cell bias, then the global venue** | closest to passing; dense stem totals are low in 14/15 cases | relaxed standard (ADR 0318 §2) on the panel, then on the global venue |
| 3 | **Transient no-drift test** of both halves, year by year | owner's explicit clause | error over 2020–2100 does not grow (number fixed before the run) |
| 4 | **Speed**, end to end, each half and the whole | goal #2 | measured core-s per cell-year vs the original at its patch count, atmosphere named |
| 5 | **Coupling** (C-track, §7) once 1–4 hold | goal #3 | — |

**Parked:** F1 (re-implementing the physics faster) — only if F2 fails DP-F. Open-ended F_diff fidelity hunts.
Track A arms other than the structure map stay in the inventory; revive one only with a measured reason.

## 10. Standing rules

1. **Every speed claim** carries a measured end-to-end number and names the atmosphere it is measured against.
2. **Every fidelity claim** carries the target's own noise floor for that quantity and stratum, and says how many
   of the 54 020 cells it covers.
3. **Response is scored on a multi-member mean, deattenuated**, against the control once D1 exists.
4. **One variable per arm**; never a coupled score without the isolated ones beside it.
5. **No one-step score without its free-run score beside it**, and no score without its nulls (§4).
6. **Refuted routes stay refuted** (ADR 0093 §4 list; plus: a count target for mortality, ADR 0241; the ratio-target
   count model, ADR 0115; the level anchor, ADR 0105/0113; bounded-Beta marginals, ADR 0173). Re-proposing one
   needs new evidence.
7. **The emulator must not see CO2** (ADR 0107).
8. **No stylised-only factorial training data** (R00430) and **no learned memory in place of an explicit carbon or
   water pool** (R00755).
9. **Original-model re-runs are pinned to one node type** (CLAUDE.md §3).

---

## 11. What the 2026-08-07 ladder found (record; details in the ADRs)

| rung | isolated | outcome |
|---|---|---|
| 0 — yardstick | the target | ✅ noise floors + deattenuated slopes (SLA 1.28, wood density 0.66, D95max 0.73, minwscal 1.06); "four broken axes" retired (ADR 0111) |
| 1 — demography alone on the original's fluxes | the learned demography | ✅ closed: level passes, **response fails on sign** (+0.707 one-step → −0.226 free-running); three compensating errors named (ADR 0174) |
| 2 — demography + the original's physics | the feedback | deep: count target retired from mortality (ADR 0241); hazard-as-rate meets the criterion as a ceiling (ADR 0242); on the emulator's own inputs 0.78 of the mortality flux, temperature integral fixed (ADR 0243–0245) → **continues as A1** |
| 3 — physics alone on the original's canopy | the fast physics | quantified, not fixed: growth 1.6–4× high, Mediterranean GPP 1.61×, warming response wrong (ADR 0125–0139) → **F1/F2** |
| 4 — coupled residual | the remainder | not done → replaced by DP-C on the chosen arms |
| 5 — speed | — | timing gate + profile built (ADR 0084); no speed-up landed; patch cost law measured (ADR 0086) → **F1/F2/F3** |
| 6 — ESM coupling | — | harness runs without this project's physics (ADR 0083/0085) → **C4** |

---

## 12. Where things are recorded

See `CLAUDE.md` §9 (ADR 0319): `STATE.md` (state + NEXT), `JOURNAL.md` (narrative), ADRs with the next free number,
`MEMORY.md` (cross-cutting facts), `CHANGELOG.md` / `changelog.d/`. The per-line files under `lines/` are history.
