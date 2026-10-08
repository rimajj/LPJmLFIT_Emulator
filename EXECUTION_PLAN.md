# EXECUTION_PLAN.md — the current program (revision 2, owner instruction 2026-10-08)

**Read this after `CLAUDE.md` and before `lines/<X>/STATE.md`.** It is the executable program: what each line
works on, what decides which method survives, and what must not be started yet. `DEVELOPMENT_PLAN.md` stays the
stable phased architecture; `STEERING_PROMPT.md` is older and its ordering is superseded by this file.

**Revision 2 replaces the 2026-08-07 error-attribution ladder as the order of work.** The ladder did its job (§11
records what each rung found), and its findings plus a systematic literature review changed *how* we get to the
goal, not the goal itself. Owner, verbatim, 2026-10-08:

> *"based on the findings of this project so far and the findings in the review, update this projects plan. the
> goal stays the same, upate the plan on how to get there if necessary. try all promising methods"*

Evidence and reasoning: **ADR 0096** (the decision) and **`docs/review_comparison.md`** (the comparison against
115 published emulator/hybrid studies, with quotes). Previous version: `git show a0f2cbba:EXECUTION_PLAN.md`.

**Integrator-owned.** A line does not edit this file. It records progress in its own `STATE.md` and raises a change
here as an integration point. Whoever holds the merge lock is the integrator for that moment (CLAUDE.md §9).

---

## 0. The goal — unchanged (ADR 0094, 0106, 0107)

1. **Faithful.** Tree counts, trait distributions and trait medians within `max(10 %, the original's own two-run
   spread)` on **all 54 020 tree-bearing cells**, both scenarios, **and the response between them** — "especially
   under climate change" (ADR 0106).
2. **Fast enough to live inside an ESM** — a first-class deliverable.
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
| **D0** | **The global stratified panel**: ~1 000 cells, stratified by biome × climate, spread over the ~161 populated 15° tiles, fixed and committed (cell list + seed). Replaces ad-hoc 5/12/674-cell panels for any global score | one comparable venue | none | **S** |
| **D1** | **Constant-climate control of the original**: from the 2019 restart, 2020–2100 with 1990–2019 weather detrended and recycled, same members, constant CO2 — on D0 (global optional). The original's response is then **SSP370 − control**, not SSP370 terminal − historic terminal | the original's own 2020–2100 change has never been split into climate response and continuing stand dynamics; R00661 isolates its response exactly this way | ~6 core-h per member on D0 at 25 patches | **S** |
| **D2** | **Re-run Germany 2071–2100 with the humidity setting corrected** (from the existing `restart_2070_nv.lpj`, every scenario × seed leg), and the post-2100 continuation if it is used | the only years in which the Germany scenarios separate | ~900 core-h per leg at ~12 core-s per cell-year (~10⁴ for all legs) | **X** — ⚠ **owner decision pending** (recorded 2026-10-01 as the owner's call); everything else proceeds without it |
| **D3** | **A 3rd and 4th independent member on D0** (each a separate spin-up — ADR 0041: a new seed under restart is a byte-identical clone), **with daily outputs** | calibrated uncertainty needs >2 members; the daily fluxes have **no** two-run spread today | ~80 core-h per member | **S** |
| **D4** | **Transient climate-contrast ensemble on D0**: from the 2019 state, 2020–2100 under SSP370, SSP126, the D1 control, SSP370 change patterns of both climate models swapped between cells, and SSP370's change pattern scaled ×0.5 and ×1.5 (scale in temperature and relative humidity, then convert, so the variables stay consistent); ≥2 members; constant CO2. **Hold out ×1.5 and one climate model** as the out-of-distribution test | breaks the place-vs-response confounding by construction. **Anchored on real patterns, NOT stylised factorials**: stylised T/P grids "failed to extrapolate effectively to the real CMIP6 climate scenarios" (R00430); delta grids work for totals but not composition (R00201) | ~100 core-h at 25 patches; ~1 300 at 250 | **S** |

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
| **DP-0** | D1 (+ D2 if approved) landed | does the original's own response have power? | signal-to-noise ≥ 2 on the primary aggregate response statistic with the available members. If not, D4's held-out ×1.5 amplitude becomes the primary response test |
| **DP-A1** | each Track-A arm's first scored free run in Germany (held-out climate model, 1985 → 2044) | does it survive round 1? | survives if (a) cell pass rate ≥ 0.5 × the other-member ceiling, (b) stems and biomass per stem within ±10 % at 2044, and (c) it is **not worse than its climate-blind twin** (before DP-0) / **beats it by more than the member-to-member noise on the response** (after DP-0) |
| **DP-A2** | survivors scored on D0 + D4 | which arms go to all cells? | response ratio (deattenuated, vs the control) inside the original's two-member band on the held-out amplitude and the held-out climate model, with no more than 1 pp loss of level cells vs the best arm |
| **DP-F** | F1 and F2-phase-A scored on the 5 cells + D0 | which fast side? | the cheapest arm meeting its §6 pass bar. If none meets the response clause, the fast side is the bottleneck and gets the next round |
| **DP-C** | the chosen A arm + F arm coupled | is it stable? | C1 passes at ≥ 4 of 5 biome cells and on a D0 subsample |
| **DP-S** | after DP-C | is it fast enough? | end-to-end ≤ 0.030 core-s per cell-year (T63) at the chosen patch count, then ≤ 0.0135 |
| **Accept** | after DP-S | done? | §0 on all 54 020 cells, both scenarios and the response |

⚠ **If the best arm fails a decision point, that is the finding, not a failed test** — record it in an ADR and say
which statistic failed. Do not re-read a criterion after seeing its arm (the ADR-0104 error).

---

## 9. What each line does now (all in parallel)

| line | now | must NOT start yet |
|---|---|---|
| **S** | A1 (ADR 0245's water probe); D0 panel; D1 control; D3 members; then D4; global side of Track Y; A4 on the global model; U1 after D3 | no new one-step count-model work |
| **X** | Germany round 1 of A2–A7 on the Track-Y scorer (owner's Germany-first milestone); D2 when the owner approves; C3 | the global transfer of an arm before it passes DP-A1 |
| **M** | F1 (kinetics wiring → analytic/implicit derivative → convergence test); C1 stability gate; C2 interface + soil respiration/fire; F3 | open-ended F residual hunts (paused until DP-F) |
| **O** | F2 phase A (offline learnability of the daily water–carbon model); the speed harness as a CI gate (request to the integrator); threads across cells | online work beyond the C4 self-test until DP-S |
| **E** | C2 energy-side exports + real wind/pressure in the coupled driver (with M); Experiment B (the closure scored with F's own LE); review F3 | — |
| **integrator** | wire the speed harness as a required gate; keep this file and `MEMORY.md` current | — |

**Integration points this creates (record in BOTH lines' STATE):** M ↔ O for F1/F2 (who edits `src/fdiff.jl`: M
only, unless a hand-over is recorded); M ↔ E for F3 and C2; S ↔ X for the shared Track-Y statistics and D0; S ↔ M
if A1's water integral needs F's per-tree roots (`per_tree_roots`).

---

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

## 12. Where each line records what

| kind | destination |
|---|---|
| progress + the `## NEXT` handoff | `lines/<X>/STATE.md` (yours only) |
| narrative | `lines/<X>/JOURNAL.md` (append) |
| a decision | an ADR from **your current block** (see `docs/decisions/README.md`: S 0246+, M 0190–0209, E 0076–0079 then 0140–0149, O 0088–0089 then 0150–0159, X 0313+, integrator 0097–0099 then 0160–0169) |
| an arm's result | one row per (arm, venue, statistic) in the Track-Y table of your venue, plus an ADR when it decides anything |
| a cross-cutting `[VERIFIED]` fact | `MEMORY.md` (additive) |
| changelog | a new `changelog.d/<X>-<slug>.md` |
| a change to THIS file | an integration point — raise it, do not edit |
