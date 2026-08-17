# ADR 0243 — Which of the hazard's inputs the standalone emulator actually needs

* **Status:** accepted (sections 1–4 are the PRE-REGISTRATION and were committed before any number existed: commit `270ab35a`)
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

## 5. Result — the shipped default FAILS, and the WATER integral is the reason

`scripts/diagnose_rung2_hazard_inputs.jl`, SLURM job 1815280, 48 dumps, **1 389 207 tree stem-years**,
no model run. The independent cross-check is `scripts/diagnose_rung2_ported_certain_set.jl` (job 1815281,
its `NPREV` knob added for this), which reaches the certain-set numbers through different code.

**PANEL A — the identity self-test passes first.** `max |h_full − mort_prob| = 8.9e-16` over all cells and
`Φ(full) = 1.0000000000` on every arm and leg, reproducing ADR 0183 through a second scorer. Zero stems
dropped on the `mort_prob` guard.

### 5.1 The blessed statistic

`Φ` = nominated mortality flux relative to FIT's own, on identical rosters:

| variant | REC historic | REC ssp370 | H1 historic | H1 ssp370 |
|---|---|---|---|---|
| `full` (the self-test) | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `zeroT` (temp dropped) | 0.9209 | 0.9437 | 0.9207 | 0.9449 |
| `zeroW` (**water** dropped) | 0.8625 | 0.8399 | 0.8569 | 0.8413 |
| **`zeroWT` = the SHIPPED default** | **0.7834** | **0.7834** | **0.7776** | **0.7862** |
| `zeroWT_c0` (counter never learned) | 0.6847 | 0.7001 | 0.6818 | 0.6932 |

**Φ(zeroWT) = 0.78 ⇒ FAIL** on all four (arm, leg) combinations, against the pre-registered fail bound of
0.867 — not a straddle, and outside by a margin (0.084 below the fail line, 0.147 below the pass line).
Running the hazard on the inputs the emulator actually hands it today throws away **22 % of the mortality
flux FIT's own stand is asking for**, which is the same *kind* of shortfall ADR 0187 measured for the
retired count-budget operator (there 42 %) — smaller, and still over the line.

Three things make the number trustworthy rather than merely large:

1. **NULL 3, the derivable inequality, HOLDS with informative slack.** `1 − Φ(zeroWT) = 0.2166` against
   `S_wt = 0.3190` (ssp370, REC) ⇒ slack **0.1025**. So about a third of the water+temp hazard mass is
   absorbed by the `min(1, ·)` cap and the hard kills: those stems die anyway. The inequality could not
   have been satisfied by a broken scorer, and its slack is a second, independent quantity.
2. **The decomposition is ADDITIVE to 2e-4.** `(1 − Φ(zeroW)) + (1 − Φ(zeroT)) = 0.1601 + 0.0563 = 0.2164`
   against a measured `1 − Φ(zeroWT) = 0.2166`. The hazard terms are additive before the cap, so this is
   expected — and it means **there is no interaction to reason about**: the two integrals can be costed
   and wired independently.
3. **The answer does not depend on whose stand it is measured on.** `REC` (FIT's own roster) and `H1` (the
   roster the rate operator built) give 0.7834 vs 0.7776 and 0.7834 vs 0.7862. Skill trap 5 does not bite
   here by construction — every variant is evaluated on the same row — and the agreement confirms it.

**WHICH integral: water, by 2.4–2.8×.** Dropping water costs 13.8/16.0 percentage points of flux; dropping
temperature costs 7.9/5.6. FIT's own water+temp share of hazard mass is **31 %** pooled, and it is
concentrated: at **c44048 it is 67 %** (Φ(zeroWT) = 0.464) and at **c52059 35 %** (Φ = 0.736), while at
c12235 it is **0.05 %** (Φ = 1.0000). ⇒ the defect is a *dry-cell* defect, not a global level error, and a
global mean would understate it at exactly the cells where mortality matters most.

### 5.2 The ordering clauses — the certain set survives, the SIZE ordering does not

* **Certain set: PRESERVED.** Recall 0.9825 / 0.9545 (REC), 0.9783 / 0.9581 (H1), all above the 0.9 clause.
  ⚠ **Precision is 1.0000 at every cell BY CONSTRUCTION and is not evidence**: zeroing can only lower a
  hazard, so the zeroed certain set is a strict subset of FIT's. Only recall carries information here. The
  cross-check script printed that precision column as a pass for the whole question; its wording has been
  narrowed in the same commit, because "the certain set survives" is exactly the reading this ADR refutes.
* **Height-quintile ordering: TILTED, and the tilt is the shape that matters.** `max |Φ_q − Φ|` is
  **0.185 / 0.162** (REC) and **0.177 / 0.168** (H1), all outside the ±0.15 clause. The profile (REC,
  ssp370): Q1 **0.864**, Q2 0.672, Q3 0.745, Q4 **0.622**, Q5 0.713. The shortest quintile keeps most of
  its nominated flux — those stems are condemned by `mort_npp` and the sapling-carbon hard kill regardless
  — while the taller four lose 26–38 %. ⇒ **zeroing the water integral spares big trees preferentially**,
  which is precisely where ADR 0241 §6 located the entire per-stem mass excess (the open-ended top height
  bin). Under ADR 0242's `H0` finding — at FIT's full flux, WHICH trees die is decisive — a tilt in this
  direction is the failure mode with teeth, not a level offset a scale factor could absorb.
* Mass selectivity of the nominated flux moves little (`full` 0.518 → `zeroWT` 0.506 per patch-year,
  ssp370 REC), which is consistent: the tilt is in *height*, and λ is a mass-weighting statistic pooled
  over a right-skewed within-patch mass distribution. Reported as the sanity range it was pre-registered
  as, and it gates nothing.

### 5.3 The counter is worth as much as the temperature integral — and that was not expected

`zeroWT_c0` is the pessimistic bound on never learning `bm_inc_counter` (holding it at 0 forever rather
than bootstrapping it from 0): **Φ 0.685 / 0.700**, certain-set recall **0.851 (NOT preserved)**, quintile
tilt **0.28**. The hard-kill census shows the mechanism exactly — `bm_inc_counter` kills go 2 506 → **0**
on the ssp370 leg while `ghost_tree` kills rise only 20 023 → 20 132. So the counter contributes
**~9 pp** of flux beyond the two integrals, i.e. **more than `temp_stress`'s 5.6**. The coupled
`_trait_hazards!` already advances it every year precisely so it cannot drift (`slow.jl` :812-818), which
is the right design; this measures what that design is worth and says the rollout's first years
under-hazard its declining cohorts by up to this much.

### 5.4 An annual proxy cannot stand in for the daily integral

Information panel, and it closes a cheap-looking shortcut before anyone tries it. The correlation between
the C's own annual `1 − wscal_mean` — which F already has — and the C's own `water_stress` integral, formed
**within (cell, PFT)**: median `r` **0.4876** (historic) / **0.3981** (ssp370), range 0.05–0.69 over 7
PFTs. That is `r²` ≈ 0.16–0.24 ⇒ an annual mean explains under a quarter of the variance of the integral it
would be standing in for. Feeding it in as though it were the integral is the ADR 0023 train/inference
shift and would not even buy accuracy. ⚠ Note the direction here: the **pooled** `r` is 0.21, *lower* than
the within-group median — the opposite of skill trap 5j's usual inflation, because the per-PFT relations
have different slopes and cancel when pooled. Both are printed; only the within-group value is read.

## 6. What this changes, and what it does NOT

**The §4.4 FAIL branch fires.** The rate operator cannot be wired with the stresses zeroed: it would go
into the coupled loop nominating 78 % of the flux it needs, with the shortfall concentrated in the tall
stems whose mass is the known excess.

**The fix already exists and is switched off.** ADR 0110 Phase 2 built exactly these two integrals per
individual (`fast.jl::_accumulate_stress!`), on the C's own construction. So the action is a **flag chain**,
not new physics — and this is the guardrail-4 corollary again (an opt-in flag whose default is measured
wrong is a defect on a timer, exactly as `wscal_leafon` was for weeks):

⚠ **THE CHAIN IS THREE FLAGS DEEP AND TWO OF THEM SILENTLY DEFEAT IT.** `water_stress_acc` is only ever
non-zero when **all three** of `per_tree_roots` (default **false**, `fdiff.jl:335`), `wscal_leafon`
(default true since ADR 0059) and `trait_drought_mortality` (default **false**, `fdiff.jl:354`) hold:
`wscal_ind` is allocated only under `per_tree && w.wscal_leafon` (`fdiff.jl:2092`), and
`_accumulate_stress!` returns early on `ws === nothing`. So **turning `trait_drought_mortality` on alone
reproduces the zeroed regime — this ADR's FAIL case — with no error, no warning and no visible
difference.** Anyone measuring the flip would conclude the integrals do not help. That is a real trap on
an M-owned file and it is raised as such (§7).

**What is NOT claimed.** `Φ(zeroWT) = 0.78` is the cost of **zero** inputs, not the cost of **F's** inputs.
The regime that matters for the standalone emulator sits between this and ADR 0242's ceiling and is
**UNMEASURED** — no dump can carry it, because F's integrals are F's own values. The pre-registration said
so before the run and the number does not change it: **this ADR does not establish that the coupled rate
operator works, only that it cannot work on zeros.** Nor does it revisit ADR 0242's ceiling caveat.

**No `src/**` change, no flag flipped, no default moved, no baseline regenerated.** The two touched scripts
gained an `NPREV` knob and a narrowed printed conclusion; a default run of the cross-check still selects
the same dumps and prints the same numbers it always did.

## 7. Actions this ADR creates

1. **Line S, next:** measure the middle term. A coupled arm with `per_tree_roots = true`,
   `wscal_leafon = true`, `trait_drought_mortality = true` scored on `Φ` against the C's own
   `water_stress` at the same cells — the F-vs-C comparison of the *integral itself*, which is an
   `fdiff-validate`-shaped question and needs no rung-2 run. **Pre-register it with the bracket as its
   two nulls: 0.78 (zeros) and 1.00 (the C's own).** The pass condition is Φ ≥ 0.867 by the same derivation.
2. **A REQUEST TO LINE M (integration point, raised in `lines/M/STATE.md`):** make the silent chain loud.
   A `trait_drought_mortality = true` configuration whose `wscal_ind` is `nothing` should ERROR rather
   than accumulate zeros — the same "fail loudly instead of defaulting" discipline `pft_mort_params`
   already applies. `fast.jl`/`fdiff.jl` are M-owned, so line S does not touch them; the measurement in
   action 1 needs no change, only the default flip would.
3. **Do NOT** re-run the `H*` campaign, propose a count-side instrument, or feed `1 − wscal_mean` into
   the hazard as a proxy (§5.4 measures why it would not work).
