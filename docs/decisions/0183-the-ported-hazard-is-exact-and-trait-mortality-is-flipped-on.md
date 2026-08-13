# ADR 0183 — The ported hazard reproduces FIT's own EXACTLY, survives the zeroed stress integrals, and `trait_mortality` is flipped ON

- **Status:** accepted
- **Date:** 2026-08-13
- **Line:** S
- **Closes:** ADR 0176 §4's pre-registered flip criterion (which replaced ADR 0049's)
- **Corrects:** ADR 0176 §4's premise about which hazard the rung-2 arms used (§2)
- **Scripts:** `scripts/diagnose_rung2_ported_certain_set.jl` (new)
- **Artifacts:** `logs/S-certain2.1773377.out` · `/p/tmp/jamirp/S_rung2_standwarm/ported_certain_set.csv`

## 1. The criterion, and the standing reason it had to be settled

ADR 0176 §4 pre-registered: *"on ≥ 12 named cells, the ported hazard's certain set (`mort ≥ 1`) against
FIT's own on the SAME rosters must reach recall ≥ 0.8 with precision ≥ 0.8; the harness already sees both,
so this costs one comparison pass and no new run. If it passes, flip."* It had sat unmeasured, which is
exactly guardrail 4's corollary — an opt-in flag whose default is believed wrong is a defect on a timer —
and exactly what the owner's standing steer forbids ("why do you switch important mechanisms off??",
"'it is opt-in' is not a sufficient answer").

## 2. First, a correction: the arms were ALREADY using the port

ADR 0176 §4 says the ~85 % of `S1`'s advantage that comes from honouring certain kills was obtained from
*"FIT's own `mort ≥ 1`, read off the C's roster"*, and that the coupled flip therefore rests on the port
reproducing it. **That is wrong on a point of code.** `rung2_s_demography_harness.jl:539` computes
`certain = [t.mort >= 1.0 for t in trees]`, and `Tree.mort` — its own field comment at :206 — is
`TraitMortality.mortality_hazard`, evaluated at :262 on the roster's state. The harness never reads the
dump's `mort_prob` at all; only an inline comment at :533 calls that field "FIT's own hazard". So the
`S0h`/`S1` advantage ADR 0176 measured was already the **port's**, and this measurement is not a gate the
flip was waiting on. What it does is price how much of the port's certain set is FIT-faithful rather than
the port's own accident — and what the coupled flip actually rested on was a *different* thing: whether the
coupled loop can supply the hazard's inputs. §4 measures that too.

## 3. Basis

| | |
|---|---|
| rosters | the `REC` dumps (FIT's own roster through the pure-observation path; FIT's hazard uncontaminated by any substitution) as headline, with the `S1` rosters beside them |
| phase | `grow`, where the roster carries THIS year's hazard — `mortality_tree_ind` runs inside the growth loop, ahead of the `grow` dump. Verified: for a stem present in both, all five `mort_*` columns are bit-identical at `grow` and at `mort`. The hook's own "uninitialised garbage" warning applies to `pre` and to a recruit's establishment year, not here. |
| ported | `LPJmLFITEmulator.TraitMortality.mortality_hazard`, reached as the shipped name with the same call the harness makes (`age = age − 1`, the emitted age being post-increment). **No second copy of the hazard exists in the scorer** — that is the point. |
| FIT's own | the dump's `mort_prob` = the C's `min(1, mort_npp + mort_age + mort_water + mort_temp)` |
| sample | **15 cells** (the criterion names ≥ 12), both scenarios, **1 568 744 stem-years**, 99 897 certain kills, **0 stems dropped** by the finiteness guard |
| seeds | one seed per (arm, cell, scenario): the hazard is a deterministic function of the roster, so extra seeds add rosters, not independent verdicts on the same rosters |

## 4. The result

**The port is not approximately right, it is exact.**

| arm / leg | stems | FIT certain | recall | precision | mean \|Δhazard\| |
|---|---|---|---|---|---|
| `REC` historic | 193 804 | 6 926 | **1.0000** | **1.0000** | 5.0e-18 |
| `REC` ssp370 | 553 729 | 24 400 | **1.0000** | **1.0000** | 4.9e-18 |
| `S1` historic | 213 012 | 14 684 | **1.0000** | **1.0000** | 5.8e-18 |
| `S1` ssp370 | 608 199 | 53 887 | **1.0000** | **1.0000** | 6.8e-18 |

Not one stem-year disagrees, and the hazards agree to floating-point noise. Handed the C's own per-tree
inputs, `mortality_hazard` **is** `mortality_tree_ind`'s probability.

**And it survives the inputs the coupled loop cannot supply.** `slow.jl::_trait_hazards!` (:865-869) feeds
`water_stress = temp_stress = 0` unless `FDiffFastCore`'s `trait_drought_mortality` is also on, because F
has neither of FIT's daily stress integrals on FIT's basis (ADR 0049 §3, ADR 0051). Re-evaluating the same
hazard with both zeroed — **i.e. as the coupled loop actually runs it**:

| arm / leg | recall | precision | FIT's own `mort_water + mort_temp` share of hazard MASS |
|---|---|---|---|
| `REC` historic | 0.9698 | 1.0000 | 29.4 % |
| `REC` ssp370 | 0.9557 | 1.0000 | 31.2 % |
| `S1` historic | 0.9718 | 1.0000 | 30.9 % |
| `S1` ssp370 | **0.9087** | 1.0000 | 36.6 % |

⇒ the criterion (≥ 0.8 / ≥ 0.8) passes in every arm × leg, worst case 0.909.

**The interesting structure, and it is not an accident:** the two stress hazards carry **29-37 % of the
graded hazard mass** and yet only 3-9 % of the *certain* kills. FIT's certain kills are made by
`mort_npp`'s growth-failure escalation and the hard kills, not by drought or cold. **Precision is exactly
1.0000 for structural reasons, not measured ones** — the four hazards are non-negative and additive before
the `min(1, ·)` cap, so zeroing two of them can only lower the total and a stem certain with zeros is
certain with the real stresses. **Read recall alone as the informative number.**

## 5. Decisions

1. **[DECISION] `trait_mortality` default flips `false` → `true`** in `FluxDrivenSlowEmulator`
   (`src/components/slow.jl`). ADR 0176 §4's criterion is met by a wide margin, on 15 cells rather than 12,
   with the coupled loop's own degraded inputs.
2. **[DECISION] Guardrail 4 is now served by the OPT-OUT `trait_mortality = false`.** Every control arm
   that wants the pre-0183 composition-preserving thinning must pass it **explicitly**; a control that
   relied on the default is now measuring the new operator. The docstring says so at the flag.
3. **[DECISION] Do NOT flip `FDiffFastCore`'s `trait_drought_mortality` on the strength of this.** It is
   line M's file (ADR 0029), and this measurement shows the certain set does not need it. What it would buy
   is the *ordering* among non-certain stems, which is unmeasured here — raise it as an integration point,
   not as a flag decision.
4. **[TODO, pre-registered here] The residual this does not cover:** ADR 0176 attributed ~85 % of `S1`'s
   advantage to honouring certain kills (that share is what recall 0.909-0.972 measures) and ~15 % to trait
   *ordering* among the survivors, which loses 29-37 % of its hazard mass under the zeroing. Criterion for
   deciding whether that matters: on the same rosters, the Spearman rank correlation between the zeroed and
   full hazards over non-certain tree stems, and the wood-density selection differential each produces.
   ≥ 0.9 and a same-sign differential ⇒ the zeroing costs nothing that matters; below that ⇒ the
   `trait_drought_mortality` integration point is worth raising with M.

## 5b. One caveat the flip carries, stated rather than discovered later

`_trait_hazards!` reads `TraitMortality.pft_mort_params(pft_ids[i])`, and `FDiffFastCore`'s `pft_ids`
**defaults to `t.is_grass ? 8 : 3`** — every tree a beech (ADR 0126 §5). Grass cohorts are skipped, so
nothing errors; but a coupled caller that has not wired real per-cohort ids now runs the **ported hazard
with beech's mortality parameters for every tree**, and those parameters are strongly per-PFT (ADR 0049's
table: `mort_water_factor` 5–20, `longevity` 125 or 400, four different `WD_mort` pairs). The measurement
above used the C's own per-tree ids, so **it does not license the flip for an unwired caller.** This is the
same defect class as ADR 0125/0126's beech-for-everything, it is pre-existing rather than introduced here,
and the fix is on the shared path M already built (`pft_ids` + `per_pft_params`) — but a coupled score
produced without real ids must say so.

## 6. What the flip costs, measured

The full CI-faithful suite was run with **only the default changed** (job 1773395), so its failure list *is*
the blast radius. It is **5 assertions of 275 605**, all in one testitem —
`test/testitems/slow_trait_mortality_operator_tests.jl` — and all one cause: **that file's CONTROL arm was
constructed without the kwarg and therefore relied on the old default**, so at the flip it silently became a
second copy of the arm. The five are its inertness pair (`trait_mortality_diag`/`mort_diag` empty), the
control's composition-invariance identity, and the two per-cohort contrasts that compare arm against control.
Nothing else in the tree moved: no conservation gate, no AD/gradient gate, no committed ReferenceTests
baseline, no other testitem. This is the third default flip on this line to come in at a handful of moved
assertions rather than a broad regression (`julia-test` skill records the pattern).

Fix applied in the same commit, and it is the general lesson: **the control now passes
`trait_mortality = false` explicitly**, with a comment saying it must stay that way, and a new assertion
(1b) checks on the constructor that the DEFAULT is the operator — so a future silent flip back cannot pass
this file either. **Re-run job 1773556: 275 606 pass / 0 fail, 7m23s.**

**⚠ THE PROBE AUDIT, AND WHAT IT DOES *NOT* LICENSE (`julia-test` step 5/6).** 75 call sites construct a
`FluxDrivenSlowEmulator` outside `slow.jl`. The suite proves the TEST files are insensitive to the flip (only
the 5 above moved), but six **probe scripts** take the default by omission and therefore now run the new
operator:

    scripts/kcap_merge_confound_probe.jl · scripts/biome_slow_oracle_probe.jl
    scripts/wscal_leafon_probe.jl · scripts/biome_resilience_probe.jl
    scripts/measure_hainich_gate_bands_probe.jl · scripts/diagnose_count_recursion_anchor.jl

They are deliberately NOT edited here: a probe whose arm means "whatever ships" *should* take the default by
omission, and guessing which of the six meant that rather than "the uniform thinning" would be inventing
intent. **What follows instead is a labelling rule: every number those six have already published is a
PRE-0183 (composition-preserving thinning) number.** Do not compare a fresh run of any of them against an
old printed value without accounting for the flip, and when one is next touched, make the flag explicit in
every arm that means a specific value (`scripts/trait_mortality_arm_probe.jl` already does).


## 7. Gotchas paid for here

- **An exact-agreement result is a reason to check for a tautology, not to celebrate.** The agreement is
  real precisely *because* the port was handed the C's own per-tree inputs; the same number would be
  meaningless if the scorer had re-derived any of them. Reach the hazard as the shipped name and feed it
  only dumped columns.
- **Precision can be 1.0 by construction.** Before quoting a precision/recall pair, ask whether the
  perturbation under test can only move the statistic one way — here, zeroing two non-negative additive
  terms cannot create a false certain kill, so precision carries no information at all.
- **A hazard-MASS share and a certain-SET share are different questions and they disagreed by 4-10×.** An
  input that carries a third of the mass may carry almost none of the decisions.
