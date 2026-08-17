# ADR 0243 — Which of the hazard's inputs the standalone emulator actually needs

* **Status:** proposed (sections 1–4 are the PRE-REGISTRATION and are committed before any number exists)
* **Date:** 2026-08-17
* **Line:** S (Component-S science)
* **Supersedes / amends:** nothing. Builds ADR 0242 §B step 1.
* **Answers:** line S STATE §B step 1 — "measure how much of `H1` survives when the hazard is fed
  emulator-side inputs".

## 1. What is pre-registered here, and why this section exists

ADR 0242 established that FIT's own per-tree hazard applied as a **rate** — no count target, no budget,
no account, no `ρ < 1` gate — reproduces FIT's stem count to +4.4 % and its biomass to +4.1 % over an
81-year free-running leg, with the per-stem mass excess that five ADRs chased gone (−0.3 %). It also
said, in its own §5, that this is a **CEILING and not a fidelity result**: inside rung 2 the hazard is
evaluated on the roster the C hands over at the rendezvous, so it reads **FIT's own two daily stress
integrals**, which the standalone emulator does not have on that basis (ADR 0049 §3, ADR 0051).

The operator is settled. **What it reads is not.** This ADR prices exactly that gap, offline, from the
dumps already on disk — no model run — and it is written this way because the last five ADRs on this
question each turned on a reading fixed in advance, and twice (ADR 0187 §5f, ADR 0242 §7) the clause
that saved the diagnosis was one written down before the numbers.

`TraitMortality.mortality_hazard` consumes nine quantities: `wooddens`, `sla`, `age`, `bm_delta`,
`leafarea`, `leaf_c`, `water_stress`, `temp_stress`, `bm_inc_counter`. Seven of them the coupled
emulator computes for itself and hands over today (`slow.jl::_trait_hazards!`, :868-873): the two
traits and the age are its own roster state, and `bm_delta`, `leafarea`, `leaf_c` come from F's grown
pools. **Two do not**, and one is a state recursion the emulator has to bootstrap:

* **`water_stress`** — FIT's `waterstress_tree.c:31-42` gated daily integral of
  `phen·(vpd/1000)·((mort_water_res − minwscal) − wscal)`, an unbounded annual sum.
* **`temp_stress`** — FIT's `tempstress_tree.c:29` integer count of days outside `[temp_low, temp_high]`.
* **`bm_inc_counter`** — genuine per-individual state (consecutive negative-increment years, hard kill
  at 5). Not recoverable from the annual `ind` output, so a fresh rollout evolves it from 0.

## 2. Reference basis, stated before any number is read

| | |
|---|---|
| rosters | the `predict`-mode `grow` rosters of **`REC`** (LPJmL-FIT's own stand through the pure-observation path — the primary basis, because there FIT's hazard is uncontaminated by any substitution) and of **`H1`** (the stand the rate operator actually built — the corroboration). Seed 1, 12 cells × 2 legs each. |
| phase | `grow` — the rendezvous, which carries **this year's** hazard, and the exact analogue of the runtime feature point. |
| ported | `LPJmLFITEmulator.TraitMortality.mortality_hazard`, reached as the shipped name, with the same call the harness makes (`age = age − 1`, the ADR 0031 off-by-one). **No second copy of the hazard exists in the scorer** — that is what makes an agreement number mean anything (ADR 0183). |
| FIT's own | the dump's `mort_prob` column = the C's `min(1, mort_npp + mort_age + mort_water + mort_temp)`, with its own hard kills already folded in. |
| guard | a stem whose `mort_prob` is not finite and in `[0, 1]` is DROPPED and counted (the field is uninitialised for a stem that has not been through `mortality_tree_ind`). |
| coverage | H1/REC **seed 1 is complete at all 12 cells on both legs** (`check_rung2_campaign_coverage.py`: 351 OK / 9 DEAD of 360 `H*` legs; every DEAD leg is a seed 2–5 run at c32628 / c42973 / c52059, the known open C-side `duplicate roster key` fault). The statistic here is **per-stem**, so a truncated leg would still be scoreable (skill trap 2) — none of the scored legs is truncated, and that is stated rather than assumed. |

⚠ **Why this statistic is immune to the trap that limits most rung-2 numbers.** Every variant below is
evaluated on **the same roster row**, so the stand cancels exactly. Skill trap 5 — in a rung-2 arm the C
grows the stand, so a stand-derived statistic is inherited by every arm including the do-nothing null —
does not apply: nothing here compares two diverged stands.

## 3. The arms are INPUT variants, not operators

Only the hazard's arguments change; the roster, the code path and the shipped parameters do not.

| variant | `water_stress` | `temp_stress` | `bm_inc_counter` | what it is |
|---|---|---|---|---|
| `full` | C's | C's | C's | **= the H1 campaign's own hazard.** The a-priori self-test: it must reproduce `mort_prob`. |
| `zeroWT` | 0 | 0 | C's | **the SHIPPED coupled default** — `slow.jl:865` passes zeros for both unless `WaterParams.trait_drought_mortality` is on, which it is not (`fdiff.jl:354`, default `false`). |
| `zeroW` | 0 | C's | C's | isolates the water integral |
| `zeroT` | C's | 0 | C's | isolates the temp integral |
| `zeroWT_c0` | 0 | 0 | **0** | + the counter a fresh rollout has to bootstrap. Information, not a gate: the counter is state the emulator genuinely carries, so this is a spin-up property of a rollout, not a structural gap. |

⚠ **THE ONE REGIME THIS CANNOT MEASURE, NAMED IN ADVANCE.** There are **three** input regimes, not two.
ADR 0110 Phase 2 already built the emulator-side integrals: `fast.jl::_accumulate_stress!` (:274-289)
accumulates each individual's own `water_stress_increment` / `temp_stress_increment` from F's own daily
`wscal` and air/skin temperature, on the C's own construction, gated on `trait_drought_mortality` (and
needing `per_tree_roots` for a per-tree `wscal`). That regime's *values* are F's, not the C's, so it is
**not measurable from a dump** — it needs a coupled run. This ADR therefore **brackets** it:

```
zeroWT   ≤   F's own integrals (ADR 0110 Phase 2)   ≤   full  (= ADR 0242's ceiling)
```

Any claim about the middle term is out of scope here and will be said to be so.

## 4. The blessed statistic, its DERIVED nulls, and the thresholds

### 4.1 Primary — the nomination-flux ratio

```
Φ(variant)  =  Σ_stems nind · h_variant  /  Σ_stems nind · mort_prob
```

pooled over patch-years and cells per leg, and printed per cell. **Why this one:** ADR 0187 established
that the mortality **rate** is the defect, and ADR 0242's `H1` works because it nominates 5.961 %/yr
against FIT's own gross 5.961. Φ is that same rate ratio, evaluated on identical rosters, so it is the
direct answer to "how much of `H1` survives".

**The nulls, derived rather than measured (this is the part that must be prior):**

1. **Φ(`full`) = 1.0000 exactly.** ADR 0183 measured the port against FIT's own hazard at mean
   |Δhazard| 5e-18 over 1 568 744 stem-years. **If Φ(`full`) is not 1 to within 1e-9, the scorer is
   wrong and no other number in this ADR is read.**
2. **A do-nothing arm has Φ = 0** by construction (`NP` nominates nothing). So Φ(`zeroWT`) ∈ (0, 1) and
   the whole question is *where*.
3. **A derivable INEQUALITY, free and independent.** Zeroing the two stresses can only lower the summed
   hazard, and it cannot change either hard-kill class (`bm_inc_counter ≥ 5`, `leaf_c < leaf_carbon_sapl`
   both read unchanged inputs), so per stem `h_full − h_zeroWT ≤ mort_water + mort_temp`. Hence
   **`1 − Φ(zeroWT) ≤ S_wt`**, where `S_wt = Σ nind·(mort_water + mort_temp) / Σ nind·mort_prob` is FIT's
   own water+temp share of hazard mass. The **slack** in that inequality is exactly what the `min(1, ·)`
   cap and the hard kills absorb, and it is reported.

**The pass threshold, derived from a published measurement rather than chosen.** ADR 0187 measured a
mortality flux at **0.58** of FIT's compounding to **2.90×** the biomass over the 81-year ssp370 leg.
Taking that mapping as log-linear in the shortfall, `factor = exp(k·(1 − Φ))` with
`k = ln(2.90)/0.42 = 2.535`. ADR 0242's standing clause is |dAGB| < 40 %, i.e. factor < 1.40, so

```
1 − Φ  <  ln(1.40)/2.535  =  0.133      ⇒      PASS if  Φ ≥ 0.867
```

Printed beside it, the **no-feedback** bound — `exp(m·T·(1 − Φ))` with FIT's own gross flux
`m = 0.0596/yr` and `T = 81` — which gives Φ ≥ **0.930**. The two differ because a stand that is
under-thinned self-limits (denser stands grow less, and the C's light-driven establishment saturates);
the calibrated constant absorbs that, the naive one does not.

* **Φ ≥ 0.930** ⇒ PASS on both readings.
* **Φ ≤ 0.867** ⇒ FAIL on both readings.
* **0.867 < Φ < 0.930** ⇒ **NO CLEAN VERDICT**, reported as a straddle (ADR 0241's precedent for an
  in-between band), and the decision escalates to a coupled arm.

⚠ **Stated in advance:** the calibration rests on ONE measured (flux, biomass) pair, so it is an
order-of-magnitude conversion, not a law. That is precisely why the straddle band exists and why it is
not being narrowed after the fact (ADR 0187's rule: never move a band once the numbers are in).

### 4.2 Secondary — ordering, because at FIT's full flux WHICH trees die is decisive

ADR 0242's `H0` finding forces this: the same flux spent on the wrong stems annihilated the >5 m stand
(−98.5 % count, −99.6 % agb). A variant that keeps Φ but loses the ordering is therefore **not** a pass.

* **Certain-set recall / precision.** Positives = `h ≥ 1`; the reference is FIT's own `mort_prob ≥ 1`.
  Null: `full` = 1.0000 / 1.0000 by identity. Pre-registered read: a variant **preserves the certain
  set** if recall ≥ 0.9 AND precision ≥ 0.9. (This reuses ADR 0176 §4's machinery at ADR 0176's own
  positives definition, but not its 0.8 thresholds — that criterion was about the *port*, this one is
  about the *inputs*, and 0.9 is stated here rather than inherited.)
* **Flux share by height quintile** of the roster's own `nind`-weighted height distribution: Φ computed
  within each quintile. Pre-registered read: the variant **preserves ordering** if no quintile's Φ
  departs from that leg's pooled Φ by more than **±0.15**. The rationale is ADR 0187's shape-versus-level
  rule — a uniform level shift is recoverable by a scale factor, a tilt is not.
* **Mass selectivity of the nominated flux**, `λ = (flux-weighted mean per-stem mass) / (count-weighted
  mean per-stem mass)`, formed **per patch-year** and then flux-weighted over patch-years, with the
  pooled value printed beside it (skill trap 5e: a ratio-of-fractions pooled over a leg is not its own
  null). Sanity range only, **not a gate**: ADR 0187's FIT λ of 0.900 is on *realized discretionary
  kills* while this is on *total nominated hazard*, so the bases differ and that is said rather than
  glossed.

### 4.3 Information panels — explicitly not gates

* FIT's own hazard-mass shares (`mort_npp` / `mort_age` / `mort_water` / `mort_temp`), which are the
  ceiling on what zeroing can cost, and the slack in §4.1's inequality.
* The hard-kill class census (`:none` / `:bm_inc_counter` / `:ghost_tree`) per variant.
* **How well the C's own annual `1 − wscal_mean` tracks the C's own `water_stress` integral**, per stem,
  as a Pearson `r` **within (cell, PFT)** with the pooled value printed beside it. This bears on step 2's
  cost — if the relation were tight, an annual quantity F already has could stand in for a daily integral
  — and it is reported as information because **feeding `1 − wscal_mean` into a ported equation as though
  it were FIT's integral is exactly the train/inference shift `slow.jl`'s own docstring warns against**
  (ADR 0051). ⚠ The pooled `r` is not quotable as skill: skill trap 5j's tell is that adding units raises
  a cross-sectional correlation, so both are printed and only the within-group one is read.

### 4.4 What this ADR will decide, written down now

* **PASS** (Φ ≥ 0.930, certain set ≥ 0.9/0.9, no quintile tilt) ⇒ wire the rate operator into
  `src/components/slow.jl` (S-owned) with the stresses zeroed, leave `trait_drought_mortality` off,
  and **no integration point with line M is needed**.
* **FAIL** (Φ ≤ 0.867, or the ordering clauses fail) ⇒ the integrals are load-bearing, and `zeroW` vs
  `zeroT` names which one. Note precisely what that costs: the accumulator **already exists** in
  `fast.jl` (M-owned) and an S-side arm can switch it on through the existing kwarg without editing M's
  file, so the measurement needs no integration point; **only changing the shipped default would**, and
  that is a request to line M of the same shape as its own ADR 0136 inbound to this line.
* **STRADDLE** ⇒ no verdict; the next step is a coupled arm, not another offline panel.

## 5. Result

*(to be written after the run — nothing above this line is edited once a number has been seen)*
