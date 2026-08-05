# ADR 0049 — trait-dependent mortality is wired in and it selects; the DRF COUNT CHANNEL, not the hazard, bounds what it can express

* **Status:** Accepted
* **Date:** 2026-08-05
* **Line:** S (Component-S science) · ADR block 0030–0049 — **this exhausts the S block; the next S decision
  needs a new range allocated by the integrator (see Consequences).**
* **Decides:** how ADR 0047's ported FIT mortality hazard is wired into `reconcile_demography!` (Phase 3A
  **Stage 2**), and what the controlled measurement says. Three decisions: **(1)** the hazard reshapes the
  ρ-thinning through a **proportional-hazards TILT** solved to land exactly on the DRF's count target, not
  through a linear renormalization; **(2)** `mort_water` and `mort_temp` are set to **zero**, deliberately,
  because the emulator has neither stress integral on FIT's basis; **(3)** the arm is accepted as a
  MECHANISM (it selects, in the right direction, with the right age structure, at ~1e-11 carbon closure) and
  its measured limit is recorded: the DRF's demanded net death is **~0 in most years** (median `|ρ−1|` = 0,
  mean 2.8× below the ported hazard's own rate), so the operator selects at ≥ half FIT's rate in only
  **13.6 %** of the years it runs in — the count channel throttles the selection however faithful the hazard.
* **Related:** ADR 0046 (the shift is within-PFT, within-age selection; §4 — the emulator has zero channel
  for it), ADR 0047 (the offline port + its generated parameter table), ADR 0048 (the measurement protocol:
  matched constant-forcing control, score past yr 52; the merge is dormant), ADR 0044 (placement not
  shrinkage; `Rb` is veto-only), ADR 0024 (the append/merge roster), ADR 0031 (what a defaulted per-PFT
  parameter costs)
* **Evidence:** `scripts/trait_mortality_arm_probe.jl`, jobs `1698789` (5 yr, validation) and `1698791` /
  `1698795` (150 yr); `test/testitems/references/S_age_wooddens_gradient.csv` built by
  `scripts/build_age_wooddens_gradient_reference.py`, job `1698771`;
  `test/testitems/slow_trait_mortality_operator_tests.jl`; suite job `1698797`.

## Context

ADR 0046 measured FIT's per-cell wood-density warming shift as **51.3 % within-PFT / +112 %
within-age-class** selection and showed that Component S has exactly zero channel for it: `slow.jl`'s
ρ-thinning scales every tree cohort's `nind` by ONE factor, which is composition-preserving to floating
point. ADR 0047 ported FIT's per-individual hazard in full, offline, with no call site. ADR 0048 established
the measurement protocol and cleared the two pre-flight confounds.

What remained was the call site — and four design questions the handoff had already framed but not answered:
how to impose the DRF's count target on a per-individual hazard, what to do about the two stress integrals
the emulator does not have, whether to realize FIT's Bernoulli draw or its expectation, and how to score the
result against ADR 0046 §3's age–wooddens gradient, which the ADR published as prose with no artifact.

## Decision

### 1. The acceptance target is now an artifact, and it refines the ADR it came from

`scripts/build_age_wooddens_gradient_reference.py` emits
`test/testitems/references/S_age_wooddens_gradient.csv` — mean/median survivor `Wooddens` and `SLA` per
(scenario, PFT, age bin) from the seed1 `ind` parquets, on **byte-for-byte the basis that produced ADR 0046
§3** (survivors only, no stem filter, fixed edges 10/20/40/80/160/320 yr), and it **asserts the five rows
ADR 0046 published reproduce to 1 gC/m³**. They do, exactly (id 1: 184 869.3 → 331 234.4 against the ADR's
184 869 → 331 234). The fixture is therefore provably the ADR's target rather than a second, silently
different measurement of it — the failure mode that ADR 0030/0033 already paid for once.

Building it produced two facts ADR 0046 did not state, both of which change how an operator must be scored:

* **Three PFTs are non-monotone, not two.** ADR 0046 §3 named ids 0 and 3 (their one-year selection
  differential `S` is negative). **id 2 is also non-monotone** — it rises to 273 634 at bin 2, dips to
  264 692 at bin 3, then recovers to 287 639 — even though its `S` is positive. So "the sign of `S`
  predicts the gradient's shape" is a good rule with a measured exception; the fixture, not the rule, is
  the target.
* **The age axis is PFT-dependent, structurally.** id 5 has **no stems at all above 160 yr** (its longevity
  is 125, not 400 — the row a beech default used to get wrong) and id 2 none above 320 yr. A gradient test
  that assumes seven bins per PFT is testing the wrong thing for two of the seven.

### 2. The count target is imposed as a PROPORTIONAL-HAZARDS TILT, not a renormalization

The constraint is that the DRF sets *how many* die (0.9824 OOS R²) and the hazard sets *which*. The obvious
implementation — scale FIT's survival linearly, `f_i = λ·(1 − mort_i)`, with λ from the count identity — was
**rejected on two counts**: it can hand a cohort `f_i > 1` (mortality that *creates* individuals) and so
needs a clamp-and-redistribute loop, and more importantly it is not a hazard, because it distorts the ratio
between two cohorts' survival by a different amount for every pair.

What is applied instead is FIT's own object, scaled:

```
f_i = (1 − mort_i)^θ = exp(−θ·H_i),        H_i = −ln(1 − mort_i)        # θ multiplies the HAZARD RATE
θ solved (bisection, deterministic, order-independent) so that  Σ nind_i·f_i = ρ·Σ nind_i
```

This is bounded in `[0,1]` by construction, monotone and order-preserving in `mort_i`, and — the property
that makes it a *reconciliation* rather than a different mortality model — it **recovers FIT exactly at
θ = 1**, which is asserted as a test, not asserted as an intention. A hard-killed cohort (`mort_i = 1`) has
`f_i = 0` for every `θ > 0`, faithfully; if the hard kills alone exceed what ρ allows, the operator returns
`θ = 0` and **reports the residual as a `shortfall`** rather than resurrecting a condemned individual. In
150 years at Hainich the shortfall was 0 in every year, so the count target was honoured throughout.

**FIT's Bernoulli draw is applied as its EXPECTATION, and this is a modelling choice with an argument, not a
free simplification.** FIT draws `erand48 < mort` per individual (`mortality_tree_ind.c:145`). The emulator's
cohorts carry a continuous `nind` DENSITY (0.042 individuals/m² total at Hainich), not an integer count, so a
per-individual Bernoulli is not representable on this state; applying the expected survival fraction to a
density is the mean-field limit of that draw, whose variance vanishes as the represented count grows. `s.rng`
exists if a future arm wants the stochastic form on an integer-count state.

### 3. `mort_water` and `mort_temp` are ZERO, deliberately and with a stated cost

FIT's `tree->water_stress` is a gated daily integral of `phen·(vpd/1000)·((mort_water_res − minwscal) − wscal)`
(`waterstress_tree.c:31-42`) and its `temp_stress` an integer count of days outside `temp_stressed`
(`tempstress_tree.c:29`). **The emulator has neither on that basis.** `grow.water_stress` is `1 − wscal_mean`
— a bounded `[0,1]` annual mean of a *different quantity on a different scale*, and ADR 0051 is the record of
how expensive confusing those two already was on another line. Feeding it into a ported equation as though it
were FIT's integral is the ADR-0023 train/inference shift with extra steps.

The cost is bounded and known, which is why this is acceptable rather than merely convenient: `mort_temp` is
**not trait-dependent at all**, and `mort_water`'s only per-cohort variation is the per-PFT
`mort_water_factor` — a BETWEEN-PFT composition effect, not the within-PFT channel ADR 0046 identified as the
lever. Both hazards' contribution to the LEVEL is absorbed by θ. So the omission costs composition, not
selection. Recovering them requires a per-PFT daily accumulator in F, which is line M's file.

`bm_delta` — the numerator of `greff`, and thus the second half of the trait channel — is reconstructed from
`grow_annual_accounted!`'s own accounting identity rather than re-derived: `bm_delta = Δvegc_ind + reprod·bm_ind`
for a growing cohort and `bm_delta = bm_ind` for one the F core FROZE (`fast.jl:360-362`), because a frozen
tree applies no turnover and reporting the growing form there would understate its deficit tenfold.
`bm_inc_counter` is genuine per-individual state that is **not recoverable from the annual `ind` output**, so
it is evolved in the rollout from 0 and carried as a fifth per-cohort roster vector, committed atomically with
`pools`/`ages`/`tmpls`/`pft_ids` (design risk #5).

### 4. What the controlled measurement says (Hainich only — guardrail 6)

150 years, production copula ON, default `k_cap`, ARM and CONTROL differing in **exactly** the
`trait_mortality` flag and both re-run in the same process at matched year indices (ADR 0048). **0 k-cap
merges in either arm**, so the merge confound is absent as ADR 0048 measured.

| | yr 5 | yr 20 | yr 50 | yr 150 | worst |
|---|---|---|---|---|---|
| Δ community `wooddens` (arm − control) | +812 | +1 435 | +8 823 | **+7 899** | +11 256 (yr 46) |
| as a share of the FIT shift (+2 432.9) | 0.33× | 0.59× | 3.63× | **3.25×** | 4.63× |
| Δ community `sla` | +3.5e-5 | +5.7e-5 | +4.0e-4 | +2.6e-4 | |

The operator fired in **132 of 150** years, produced **0 hard kills**, honoured the count target in every
year (`shortfall` = 0, and Σnind agrees with the control to 1.4e-13), and carbon closed at **3.0e-11** —
against the control's 1.9e-11, i.e. unchanged in order (guardrail 2 holds).

**The age–wooddens gradient has the right sign AND the right age structure.** After 150 years the surviving
cohorts occupy bins 4 and 5, and the arm's excess over the control GROWS with age — **+6 565** in bin 4
(80–160 yr) and **+9 642** in bin 5 (160–320 yr). That is the signature ADR 0046 §3 asked for: selection
accumulating over a cohort's lifetime rather than a level offset. (The control's own gradient is not flat,
because the initial roster is FIT's and already carries FIT's age–trait covariance; the arm's Δ is the
operator's contribution and it is what ADR 0046 §4 says the pre-0049 emulator cannot generate.)

### 5. THE FINDING: the DRF's count channel, not the hazard, bounds the selection

The tilt θ is the operator's most informative output, and its distribution over the 132 thinning years is
**bimodal, concentrated at ~0**:

| θ | q10 | **median** | q90 | max | mean | years with θ > 0.5 |
|---|---|---|---|---|---|---|
| | 6.6e-12 | **8.5e-12** | 1.24 | 13.26 | 0.418 | **18 of 132 = 13.6 %** |

θ ≈ 0 means the DRF demanded essentially no net death that year, so the operator had nothing to
redistribute — the hazard was faithful and *inert*. The operator selects at ≥ half FIT's own rate in only
**13.6 %** of the years it runs in. The mechanism is a **gross-versus-net** mismatch, and it is a property
of the emulator's demography, not of the ported hazard:

* FIT's ported hazard on this patch: **1.688 %** of stems per year (min 1.2 %, max 2.3 %) — the right order
  against FIT's own measured `dead_frac` of 2.8–6.2 %/yr (ADR 0046 §3).
* the DRF's demanded `|ρ − 1|`: mean **0.608 %/yr** but **median 0.0 %/yr** — a *forest* prediction is
  piecewise constant, so in most years the target does not move at all and the demanded net death is
  numerically nil. The mean is carried almost entirely by the 18 high-θ years.
* ratio of the means: **2.8×**. That is the honest headline, and it is a distributional statement, not a
  scalar one: the shortfall is not that FIT's hazard is uniformly ~3× the demanded death, it is that the
  demanded death is ~0 most years and occasionally large.
* FIT has a near-stationary count with **large gross turnover** — its deaths and recruits CO-OCCUR every
  year. The emulator's `ρ < 1` and `ρ > 1` branches are **mutually exclusive within a year**, so its gross
  turnover *is* its net change, and a year of zero net change is a year of zero selection.

Selection intensity scales with GROSS deaths, so a faithful hazard wired into a net-only demography is
throttled by the duty cycle above. That is a structural limit of ADR 0024's roster design, not a fidelity
problem in ADR 0047's port. It also explains ADR 0048 §4's `τ` = 94 / 1 003 yr independently: both numbers
are reading the same missing gross turnover from opposite ends.

That the arm nonetheless moves the community mean by 3.25× the FIT shift says the *per-death* selection is
strong — the 18 high-θ years do essentially all of the work, which is consistent with the trajectory's own
shape (Δ 1 435 at yr 20 → 8 823 at yr 50 → frozen thereafter).

## Consequences

* **Stage 2 is DONE as a mechanism, and it is NOT a response measurement.** Everything above is a LEVEL
  change under CONSTANT forcing on ONE cell. FIT's +2432.9 is a *between-scenario* difference. The arm is
  therefore necessary-but-not-sufficient: the next measurement is whether Δ differs between historic and
  warmed forcing, which needs the transient boundary (ADR 0026/0027) on both arms. Do NOT quote "3.25× the
  FIT shift" as a response, and do not quote any of it against the ADR-0044 response gate — the P1 threshold
  is `ΔRr ≥ +0.036` on the global gate, `Rb` is veto-only, and "reduced the damping" remains forbidden
  language (ADR 0044 §2: the residual is PLACEMENT, not shrinkage).
* **The named next lever is CO-OCCURRING gross turnover**, not more hazard fidelity. Letting a year apply
  the hazard's gross deaths AND an establishment influx that restores the DRF's net target would take the
  operator's duty cycle from 13.6 % of thinning years to every year — but it changes the count identity's
  meaning and the recruit channel at once, so it is its own arm with its own ADR and its own matched control
  (handoff item E: never bundle).
* **Default byte-identical, and the flag is the only switch.** `trait_mortality = false` does not evaluate
  the hazard, records no diagnostics and never advances a counter; every committed baseline, ReferenceTest
  and AD path is unchanged (guardrail 4). Runtime `[deps]` stays empty (ADR 0014).
* **`fc.pft_ids` is now load-bearing for any consumer of this flag.** The operator errors on a non-tree id
  rather than defaulting, but a wrong-but-valid id (M's drivers default every tree to beech, `fast.jl:147`)
  would pass silently and evaluate temperate-beech mortality for the tropical and boreal PFTs — the ADR 0031
  defect class. The S-side harness passes real ids from the fixture's own `type` column. **M integration
  point #1 is now a correctness requirement for this arm, not a nicety.**
* **The S→M contract is extended additively, never mutated.** `trait_mortality` is a new defaulted kwarg;
  `_merge_pair!`/`_apply_kcap_merge!`/`_commit_membership!` gained a defaulted `counters` keyword. No
  positional signature, artifact format, feature order or `live_flux_cond` subset moved, so no artifact
  version bump and no integration point is required to land this.
* **ADR block 0030–0049 is EXHAUSTED.** The next line-S decision needs a new range; 0090–0099 is the
  integrator/cross-cutting block and must not be borrowed. Raise it as an integration point (CLAUDE.md §9)
  before writing the next S ADR.

## Alternatives rejected

* **Linear renormalization `f_i = λ·(1 − mort_i)`.** Needs a clamp to stay ≤ 1, and distorts pairwise
  survival ratios — it is not a hazard. §2.
* **Letting the hazard set the count and dropping the DRF's ρ.** This is the version that would have looked
  most "faithful" and is the one to refuse: the DRF's count skill is the emulator's single best-validated
  number (0.9824 OOS R², ADR 0036) and FIT's hazard as portable here is missing two of its four components,
  so handing it the count would trade a measured 0.98 for an unmeasured level.
* **Mapping `1 − wscal_mean` onto FIT's `water_stress` integral to "at least have" `mort_water`.** Same
  quantity name, different definition and scale. §3, and ADR 0051 is the precedent.
* **Realizing the Bernoulli draw.** Not representable on a continuous `nind` density; would add variance
  without changing the mean, on a state whose whole point is that it is a distribution. §2.
* **Fixing the gross-turnover limit inside this arm.** It is the obvious next lever and it is exactly what
  handoff item E forbids bundling: two operators changing at once, one matched control, no attribution.
* **Reporting the arm as a warming RESPONSE.** It is a constant-forcing level change. Stating it as a
  response would be the ADR-0033 error (crediting a level fix for a response gate) a third time.
