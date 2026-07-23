---
status: "accepted"
date: 2026-07-23
deciders: "engineering agent (standing autonomous delegation, STEERING_PROMPT); reversible by the owner or a superseding ADR"
consulted: "ADR 0018 (growth-ownership split — S owns count/establishment/mortality/trait spread), ADR 0020 (S is flux-driven, conditioned at runtime on the channel it trained on), ADR 0022 (hand-rolled zero-dep DRF), ADR 0023 (production DRF runtime-consistency + the age_mean-counter train/inference trap), docs/p1_s_in_loop_design.md §3/§4/§7-step-8/§8-risk-5, and a 3-lens adversarial design review (conservation / roster-atomicity+determinism+Float32 / train-inference+gate-impact)"
informed: "src/components/slow.jl (RecruitCopula, _merge_pair!, _apply_kcap_merge!, _commit_membership!, _mean_age_weighted, the FluxDrivenSlowEmulator append/merge reconcile + age0/k_cap/recruit_copula fields); scripts/build_slow_runtime_table.py + scripts/train_slow_drf.jl (age_mean = mean(Age-1), age0 in meta); test/testitems/slow_membership_tests.jl; test/testitems/{slow_production_drf,slow_oracle}_tests.jl (age0 wiring + oracle basis); the regenerated drf_forest_hainich.drf + _meta.txt; MEMORY.md; JOURNAL.md; CHANGELOG.md; the slow-drf-pipeline skill"
---

# Component S has a DYNAMIC cohort roster (recruit APPEND + K-cap MERGE) and a TRUE per-cohort age; the DRF is retrained on the genuine mean age

> **Status note.** `accepted` 2026-07-23 under the standing autonomous delegation. It completes the last
> structural piece of P1 (the flux-driven S owning establishment as *real* cohorts) and **supersedes ADR
> 0023 §3** on one point: `age_mean` is now trained on the true mean tree age, not the elapsed-year counter.
> Everything is Hainich-only scaffolding (guardrail #6); the production copula artifacts and the global
> runtime-consistent table remain P3/Phase-2 follow-ups. Reversible by a superseding ADR.

## Context and Problem Statement

Through ADR 0023 the `FluxDrivenSlowEmulator` ran in the coupled loop, but establishment **mixed** a fixed
sapling into the shortest existing cohort on a **fixed roster**, and `s.age` was a uniform elapsed-year
counter (`zeros`, `+= 1`/yr, never reset). Three consequences blocked "S owns demography" (ADR 0018) from
being real:

1. **Recruitment created no genuine cohorts.** Diluting an existing cohort is not establishment; the roster
   never gained an age-0 recruit, so there was no true age structure and the built Gaussian-copula
   recruit-trait sampler (`sample_copula!`, ADR 0023 §4c) had no consumer (design risk #5).
2. **`age_mean` was degenerate.** It ranged ~[0,19] (a year counter), while the true Hainich beech mean age
   is ≈45 yr (oracle q05..q95 = 15..109). ADR 0023 §3 deliberately trained the DRF on the counter *because*
   the runtime could not produce a real mean age — and flagged promoting it as the single biggest remaining
   train/inference-shift item, conditional on the append/merge work landing.
3. **The roster could not change length.** The daily rollout indexes five length-K `FDiffFastCore` fields by
   cohort position (`pools`/`tmpls`/`inds`/`pft_ids`/`bm_inc_acc`) plus `s.age`; any add/remove without an
   atomic rebuild bounds-errors or silently misaccumulates NPP (design risk #5).

## Decision

1. **Dynamic roster, confined to Tier-1 (`FluxDrivenSlowEmulator`).** Tier-0 (`DemographicSlowEmulator`)
   stays fixed-roster (its `slow_demography_tests` length gates are untouched).
   - **Establishment APPENDS** a real age-0 recruit cohort of density `dn=(ρ−1)·dtree` (was: mix into the
     shortest cohort). Recruit per-individual pools = the fixed `sapl`, or a copula draw if the opt-in hook
     is set; tmpl/pft_id reuse the beech recruit cohort's (no new PFT id). Routed
     `record_estab!(vegc_full_ind(recruit)·dn)`.
   - **K-cap MERGE** bounds the roster: while `length > k_cap` (default `max(2·K₀,40)`), merge the tree pair
     with the smallest `|Δheight|` (deterministic index-order scan, first argmin on ties). Merged cohort
     nind-weights ALL FIVE carbon pools (incl `sapwood_bg_c`) + age; inherits the dominant (higher-nind)
     parent's `sla`/`wooddens`/`tmpl`/`pft_id` (keeps `tmpl.photo.sla` consistent with `pools.sla`);
     re-derives height (pipe model, guarded `leaf>0`) and crownarea (Jucker). Carbon-neutral — no ledger
     entry (`vegc_full_ind` is linear, so `vegc_full(m)·n_m == Σ vegc_full(parent)·n_parent` to rounding).
   - **`_commit_membership!`** is the ATOMIC rebuild: replaces every length-K `fc` field in one shot,
     REALLOCATING `bm_inc_acc = zeros(T,K′)` (never `fill!`), rebuilding `inds` LAST over the full new roster
     via `_patch_fpars`, resetting the within-year accumulators + per-PFT phenology, and setting `s.age`
     + recomputing `s.recruit_idx`.

2. **`age_mean` is a TRUE nind-weighted mean cohort age (supersedes ADR 0023 §3).** Recruits enter at age 0;
   merges nind-weight parent ages; `s.age .+= 1` remains the SOLE per-year increment (applied after the
   commit's start-of-year assignment). `flux_feature_vector` computes `Σ age_i·nind_i / Σ nind_i` over tree
   cohorts (guarded against a zero tree-nind denominator). The DRF is retrained on the matching aggregate:
   `scripts/build_slow_runtime_table.py` now emits `age_mean = mean(Age−1)` per living tree stem
   (start-of-year age — the runtime feature is built before the increment; emitted `Age` is post-increment,
   CLAUDE.md §3). Each `ind` row is one stem, so the per-stem `mean` equals the runtime nind-weighted cohort
   mean by construction.

3. **`age0` seed keeps the runtime feature in-band.** `build_slow_runtime_table.py` writes
   `age0 = median(age_mean column)` (≈43.6 at Hainich) to the DRF meta; `train_slow_drf.jl` propagates it;
   the coupled builders read it and pass `age0=` to the constructor (which seeds `s.age = fill(age0, K)`).
   Without this the runtime would start at age 0 — below the trained minimum (15.5) for ~15 model years — the
   exact OOD shift the promotion removes. The coupled gates ASSERT `age0 > 0` (fail loudly if the wiring is
   dropped), since the DRF leaf-clamps OOD inputs and would otherwise pass silently.

4. **Copula recruit-trait hook is opt-in (`recruit_copula::Union{Nothing,RecruitCopula}`, default nothing).**
   When set, establishment draws `sample_copula!(s.rng, cop, axis_forests, x)` (deterministic on the
   emulator's seeded RNG) and maps the traits to the recruit's pools via a supplied `to_pools`. Default
   `nothing` reproduces the fixed-sapling behaviour, so committed gates are unaffected. This **wires the
   ADR-0023 §4c sampler into establishment** end-to-end (tested in Float64 + Float32). The production
   axis-forest artifacts + correlation matrix are a **P3 (multi-cell) concern** — at a single beech cell the
   trait axes {SLA, Wooddens, β_root} are near-degenerate.

5. **Regenerate the committed DRF as a pair.** `drf_forest_hainich.drf` + `_meta.txt` (golden pairs) are
   retrained together (in-sample R² 0.977, unchanged nfeat=15). The Gate-3 oracle compares on the C `ind`
   output basis: since the C `ind` writer excludes sub-5 m saplings (truth Height q05 = 5.21 m) and ADR-0024
   establishment creates genuine ~1 m recruits, the coupled Height quantiles are taken over cohorts ≥5 m — a
   documented reference-basis alignment (residual-diagnosis), not a tolerance fudge.

## Consequences

- **Positive.** S now genuinely owns establishment (real age-0 cohorts), mortality (thinning), and roster
  size (K-cap merge) per ADR 0018; `age_mean` is a real demographic signal (the ADR-0023 §3 trap is closed
  by construction — feature and training aggregate match, and the `age0` seed + `age0>0` assertion prevent a
  silent regression); the copula sampler is wired + tested; carbon conserves across append/merge to
  ~1e-12 gC (Float64) and ≤1e-5·C_scale (Float32); the atomic rebuild closes design risk #5 (a coupled run
  that appends AND merges completes with all roster arrays mutually consistent).
- **Negative / deferred.** Hainich-only scaffolding. The copula's production axis forests + R, the global
  runtime-consistent table (`soilmoist`/`lai` proxies), and the in-loop OOD demonstration remain
  follow-ups. The merged-cohort sla/wooddens inherit the dominant parent (a documented geometry
  simplification; carbon-exact regardless). Whole-cohort DROP is not implemented (thinning is fractional;
  the K-cap merge bounds the roster) — a below-threshold drop can be added if a future cell drives cohorts
  to ~0 nind.

## Alternatives considered

- **Keep mixing into an existing cohort (ADR 0023 behaviour).** Rejected — it is not establishment, cannot
  produce a true age structure, and leaves the copula sampler unused.
- **Grow K unbounded (no merge).** Rejected — the daily-loop cost and the size distribution degrade over a
  multi-decade run; a K-cap merge preserves the K≪N structural speed-up (ADR 0018 gate-4) with minimal
  distribution distortion.
- **Train `age_mean` on the post-increment `Age` (not `Age−1`).** Rejected — `flux_feature_vector` is built
  before the annual increment, so the runtime age is start-of-year; `mean(Age−1)` is the consistent
  aggregate.
- **Leave `age_mean` a counter (ADR 0023 §3).** Superseded — that was explicitly conditional on the roster
  staying fixed; with a dynamic roster the counter would itself be the train/inference shift.
- **Compare the oracle Height on all cohorts incl <5 m recruits.** Rejected — a reference-basis mismatch
  against the C `ind` truth (which excludes sub-5 m saplings); the ≥5 m window compares like with like.
