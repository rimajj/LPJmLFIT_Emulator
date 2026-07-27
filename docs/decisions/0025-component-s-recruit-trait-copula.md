---
status: "accepted"
date: 2026-07-27
deciders: "engineering agent (standing autonomous delegation, STEERING_PROMPT); reversible by the owner or a superseding ADR"
consulted: "ADR 0018 (growth-ownership split — S owns the trait spread), ADR 0020 (S conditioned at runtime on the channel it trained on), ADR 0022 (hand-rolled zero-dep DRF + Gaussian copula), ADR 0024 (the copula recruit-trait hook wired opt-in into establishment; dynamic roster), the LPJmL-FIT C trait model (new_tree.c sampling, getbetaroot D95max->beta_root, getrootdist USE_BETA2), and the F<->S coupling granularity (cohorts, not the 25-patch IBM)"
informed: "src/drf.jl (save_copula/load_copula, _parse_forest); src/components/slow.jl (RecruitCopula.cond, make_recruit_to_pools, live_flux_cond); scripts/build_slow_runtime_table.py (MODE=copula), scripts/train_slow_copula.jl, scripts/eval_slow_copula.jl, scripts/run_global_slow_copula.sh, scripts/plot_slow_emulator_validation.py (trait figures 09-11); test/testitems/{recruit_copula_serialization,slow_oracle_traits,slow_membership}_tests.jl; the committed recruit_copula_hainich.rcop demo; the slow-drf-pipeline + emulator-validation-figures skills; MEMORY.md; JOURNAL.md; CHANGELOG.md"
---

# Component S reproduces LPJmL-FIT's within-cell TRAIT distribution via a serialized recruit-trait copula (4 live primaries, survivor-marginal, flux-conditioned)

> **Status note.** `accepted` 2026-07-27 under the standing autonomous delegation. Turns the opt-in
> recruit-trait copula hook of ADR 0024 into a trained, serialized, validated production model. Default is
> still OFF (`recruit_copula = nothing`) — committed baselines + the AD trainer are byte-identical until the
> copula is deliberately switched on. Reversible by a superseding ADR.

## Context and Problem Statement

LPJmL-FIT discovers a cell's tree-trait distribution by brute-force Monte-Carlo: it plants many
random-trait individuals across 25 replicate patches and lets environmental filtering (a per-tree mortality
coin flip) select survivors over a 1000-year spin-up. The emulator replaces that integrator with a
*predictor* running on ~tens of density-weighted cohorts. Through ADR 0024 it reproduced the count/size
distribution, and the Gaussian-copula recruit-trait sampler existed and was wired into establishment as an
opt-in hook — but with **no production artifacts** and no fidelity evidence. Component S therefore did not
yet reproduce the within-cell TRAIT-distribution spread (the spread of SLA / wood density / rooting traits
across the community), which is the S component's stated novelty (ADR 0018).

Two facts shape the design:
1. **The emulator's mortality is trait-blind.** `reconcile_demography!` thins every tree cohort by the same
   fraction `1−ρ`, and the K-cap merge inherits the dominant parent's traits — there is NO differential
   survival. So, unlike FIT (whose distribution emerges from selection), the emulated community trait
   distribution is set **entirely by what is established**.
2. **Of FIT's five nominally-sampled trait primaries, only four carry information here.** FIT samples
   `SLA, wooddens, D95max, beta_2, minwscal`. `beta_2` is **compile-time dead** in this build — its only
   consumer `getrootdist.c:49-57` is `#ifdef USE_BETA2`, and `USE_BETA2` is defined nowhere in the source
   tree — so it feeds zero dynamics and is not emitted to the `ind` output. `beta_root` (emitted) is a
   strictly-monotone transform of the sampled `D95max` (`getbetaroot`, isD95max=true), i.e. one degree of
   freedom, not two.

## Decision

1. **Reproduce the trait distribution by SAMPLING the minimal generative set and DERIVING the rest, not by
   learning every trait jointly.** This mirrors FIT's own factorization: closed-form derivations (LAI from
   SLA, longevity from SLA, allometry) are reproduced exactly, consistently, and differentiably by
   `src/allometry.jl`; ML capacity goes to the genuinely stochastic, climate-dependent part — the recruit
   trait distribution + counts. The trait spread is injected at ESTABLISHMENT via the Gaussian copula.

2. **Four live trait axes: `{SLA, Wooddens, D95max, minwscal}`.** `beta_2` is DROPPED (dead; no C re-run to
   emit it is justified). Use `D95max` (the true FIT primary) as the single rooting axis, not the collinear
   `beta_root`. Of the four, **only SLA + Wooddens feed emulator dynamics** (`TreePools.sla`/`wooddens` →
   LAI, photosynthesis, pipe-model height); `D95max` + `minwscal` are **sampled + validated only** until
   F_diff gains per-tree consumers (a per-tree root distribution → water uptake; a per-tree drought
   threshold) — a separate downstream effort. Reproducing their *distributions* is the goal here.

3. **Train the marginals on FIT's SURVIVING stems (`isdead==0`), flux-conditioned.** Because mortality is
   trait-blind, the emulated community distribution equals the establishment distribution — so drawing
   recruits from FIT's *surviving* marginal makes the community converge to FIT's survivor distribution by
   construction. (Trait-dependent mortality is a much larger, separate change; if ever added, this training
   target must change.)

4. **Condition the axis marginals on climate/flux + bioclimate ONLY** — `live_flux_cond(s, feats)` =
   `[bm_inc_cell, growth_eff, water_stress, soilmoist]` (the 4 `FToS` flux drivers) + the per-cell
   `s.boundary` tail, DELIBERATELY excluding the 6 this-year patch-state aggregates + `n_prev`
   (`feats[5:11]`): establishment responds to the environment, not to the stand's own recursive AR state (a
   feedback loop, and the emergent quantity S predicts rather than conditions on). This subset + ORDER is
   the copula's feature-order contract, mirrored by `build_slow_runtime_table.py MODE=copula`. The
   conditioning policy lives on `RecruitCopula.cond` (a function); the 4-arg constructor defaults it to a
   STATIC policy returning the baked `x`, so pre-ADR-0025 copulas are byte-identical.

5. **Serialize as a pure-Base text `.rcop` bundle (`DRF.save_copula`/`load_copula`), zero runtime dep**
   (ADR 0014). It carries the copula Cholesky `L` (from the LATENT-NORMAL correlation), the per-axis
   `store_values` marginal forests, the axis names, and the conditioning colnames + fallback row. The
   unserializable `to_pools` is rebuilt from the axis names by `make_recruit_to_pools` (overwrites only
   SLA/Wooddens, keeps the sapl's carbon UNCHANGED so the establishment debit is draw-independent ⇒
   conservation is automatic, re-derives height/crown). Committed demo: `recruit_copula_hainich.rcop`; the
   global artifact is DVC.

6. **Validation is two-tier.** (a) A single-cell Hainich Gate-3 trait oracle (`slow_oracle_traits_tests.jl`)
   proves PLUMBING — golden draws (bitwise), conservation, and a TIGHT reproducible direct-draw marginal
   check (openlibm ⇒ platform-independent: SLA nqrmse ≈ 0.13, Wooddens ≈ 0.035) plus a COARSE coupled-
   community alarm (the 20-yr Float64 trajectory's tails diverge by CPU microarch, so it is median-ratio-led
   at ≤ 0.45, like the Height gate). (b) The REAL cross-cell fidelity proof is the multi-cell, honest
   **K-fold-BY-CELL OOS** eval (`eval_slow_copula.jl`) + figures 09-11 (`plot_slow_emulator_validation.py`):
   each cell's marginal predicted by forests that never saw it, compared to the FIT survivor marginal by
   quantile-nqrmse + KS + per-cell KS maps. Single-cell is degenerate and is NOT distributional-skill
   evidence.

## Consequences

- **Positive.** The trait spread is now reproducible + validated across cells, at ~zero runtime cost (a few
  copula draws per establishment year) and fully differentiable on the consumed axes. The deterministic
  decoders (allometry, longevity) stay exact — no capacity spent, no consistency risk, conservation
  unaffected (`vegc_full_ind` is trait-independent). A 13-cell validation gave OOS pooled KS SLA 0.044,
  Wooddens 0.017, D95max 0.029, minwscal 0.021; the global historic run + figures follow.
- **Negative / limits.** (i) Trait-blind mortality means the copula must be *retrained* if selection is ever
  added. (ii) The K-cap merge inherits the dominant parent's traits and there is one draw per establishment
  year, so a tight `k_cap` can under-disperse the community spread — a fidelity knob to sweep. (iii)
  D95max/minwscal have no per-tree consumer yet (sample+validate-only). (iv) `beta_2` remains
  unreproduced-by-design (dead in this build).
- **Guardrail.** Default `recruit_copula = nothing`; no edits to `flux_feature_vector`/`fit_forest`/
  `predict`/the count-DRF path; committed baselines + the AD trainer byte-identical until deliberately
  enabled. `drf.jl` additions clear format(Runic)/JET(closure-free loader)/Aqua.

Refines ADR 0018/0020/0022/0024; does not supersede any prior ADR.
