# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Rung-2 gross-budget demography arms `G0`/`G0h`/`G1`** (`scripts/rung2_s_demography_harness.jl`, ADR
  0240). The same three mortality operators as `S0`/`S0h`/`S1`, asked for a GROSS kill budget spent from a
  per-patch running account (`acct += (1−ρ)·n_tree + #{age == 1}`) instead of the net count change. Four
  columns appended to `s_arm_log.txt` (`n_age1 budget rho_eff acct`); the pre-existing arms are
  byte-identical.
- `scripts/diagnose_rung2_gross_account_identity.py` — the derivable a-priori gate on those arms: the
  account identity row by row (451 161 patch-years, max |diff| 0) and the uniform arm's spend ratio
  against its derived 1.000.
- `scripts/check_rung2_campaign_coverage.py` — which legs of a rung-2 campaign finished, and the re-run
  lines for the rest. A healthy run never prints `harness: served <N>`, so that line's absence is not a
  failure signal; the C's own completion line plus the arm log's patch-year count are.
- `diagnose_rung2_kill_budget.py` panel F — nomination rate, the empty-budget gate, two lumpiness columns
  and the MEASURED roster horizon that ADR 0189 §7a requires beside every kill rate.

### Changed

- One exported `ARMS` (comma or space separated) now widens `diagnose_rung2_map_target_response`,
  `kill_budget`, `kill_selectivity` and `anchor_preflight` together, defaults unchanged so every published
  table reproduces. The pre-registered verdict arm sets (`LEARNED`, `OPERATOR_ARMS`) deliberately do not
  follow it.

### Fixed

- **An empty patch deadlocked the rung-2 harness.** `read_request` took the `(year, patch)` identity from
  the tree rows, but a patch with no living trees emits no `T` record, so the response was written under
  `rsp_…_y-0001_p-01` while the C waited for the real name and died 600 s later on `ERROR043: rung2 apply:
  no answer`. Cost 53 of 360 legs; latent for the whole rung-2 investigation because no `S*` arm ever
  empties a patch. The identity now comes from the `P grow` record, the tree rows are checked against it,
  and a request whose identity is still negative is refused instead of answered.
- `run_rung2_s_arm.sh`: the harness idle timeout is now `MAXIDLE` (default 300 → **900 s**), which must
  exceed the C's own 600 s apply timeout, and is interpolated into the job file so a run records what it used.

### Added

- **The derivation ADR 0188 required before building the gross mortality budget: a lagged recruit count
  carries it exactly, but the budget must not be rectified per patch-year
  ([ADR 0189](docs/decisions/0189-the-lag-is-not-the-obstacle-the-rectified-budget-over-kills.md)).**
  `scripts/diagnose_rung2_gross_budget_lag.py`, SLURM job 1788149, **no model run** — 12 cells × 2 legs of
  `REC` `predict` dumps joined to the count model's own replay on that roster, plus `S1`'s own dumps for the
  arm-stand check, behind ADR 0185 §5's imported completion+coverage gate (30 300 patch-years, 0 unmatched).
  **The recruit term is exactly observable at the rendezvous**: `age` at the `grow` phase is post-increment
  and establishment sets age 0, so the age-1 cohort IS last year's recruits — verified at **29 700 of 29 700
  patch-years (100.000 %)**, needing no dump-format change, no index tracking (hence immune to the
  `ERROR043` duplicate-key fault) and **no integration point with line M's `rung2_apply.c`**. The lag is
  safe on three independent grounds: the count departure it introduces **telescopes** to one year's
  recruitment (1.7 stems, 6.4/7.8 % of roster, against 131.6/667.0 % for the current operator), the
  discretionary capacity it buys is **3.525 %/yr against a 1.5 %/yr criterion** and 6.0× the current
  0.590 %, and FIT's own recruitment **rises +39.8 % between the legs** (4.619 → 6.456 %/yr), so the term
  hands the operator a budget that grows under warming — a response channel the net budget does not have.
  ⚠ **But the instrument as pre-registered would over-kill:** rectifying the budget every patch-year is
  convex, so an unbiased-but-noisy budget over-spends — implied total mortality **6.999 %/yr against FIT's
  own 5.961** on FIT's stand and **8.292 vs 5.001** on the arm's own, i.e. a roster falling to **0.62×** and
  **0.11×** over the 81-year leg. The cause is the count model's per-patch-year error, not the gross-budget
  idea: with a perfect target the same budget reproduces FIT's gross kills and net exactly. Spending from a
  running account instead (a "grow" year repays an earlier overspend rather than being clipped to zero)
  lands total mortality at **5.817 vs 5.961 %/yr**, roster **1.70×**, capacity **2.702 %/yr** — and on the
  arm's own stand **1.493 ± 0.180 %/yr, AT the criterion rather than above it**, which is stated in advance.
  Two gotchas: **a derived anchor must be derived through the same nonlinearity as the statistic** (a
  pre-registered oracle band was obtained from a linear identity against a convex statistic, so it "failed"
  for a property of the instrument — the band was kept, printed and replaced by a perfect-input arm whose
  answer is an exact identity, |diff| 0.0000, rather than moved); and **model the gate, not just the
  budget** — assuming certain deaths are always honoured put the current operator's implied roster at 0.45×,
  contradicting ADR 0186's measured on-target count, and fixing it made the panel agree with that published
  number. No flag flipped, no default moved, no baseline regenerated, no `src/**` change.

### Added

- `scripts/diagnose_tstress_photo_gate.py` — scores the LPJmL-FIT `tstress < 1e-2` photosynthesis gate
  (`photosynthesis.c:54-61` and `isphoto()` at `water_stressed.c:196`) against F_diff's thresholdless
  linear `tstress` factor, over the five biome cells' own committed daily forcing and PFT composition.
  No simulation, no SLURM, sub-second. Carries the reference basis, the closed-form derivation, the
  falsifiable hypothesis, the conservatism argument for its bound, and a per-cell `CAN BIND` /
  `CANNOT BIND` verdict so a zero explains itself
  ([ADR 0138](docs/decisions/0138-the-tstress-photosynthesis-gate-is-mechanically-negligible.md)).

### Changed

- **`WaterParams.gp_stand_leafon_basis` now defaults to `true`** — F_diff's multi-individual canopy path
  builds each individual's potential conductance at FULL leaf cover and normalizes the phen-weighted sum
  by the PLAIN `Σ fpc`, exactly as `gp_sum.c:53-67` does. F previously folded `phen` into the pass-1
  `apar` and into `gmin` and divided by the phen-weighted `Σ fpc·φ`, biasing stand conductance high by
  ≈`1/φ̄` on every partial-leaf day and carrying that into `demand`, `gc`, `gpd`, `fac`, the solved λ and
  GPP. Guardrail 4 is served by the opt-out (`gp_stand_leafon_basis = false` reproduces the previous
  expression exactly). Scope is unchanged and confirmed by measurement: the single-individual
  `daily_step` / `daily_step_ml` baselines reproduce EXACTLY
  ([ADR 0137](docs/decisions/0137-gp-stand-leafon-basis-default-flip.md), executing
  [ADR 0136](docs/decisions/0136-the-two-gp-sum-basis-differences-measured-one-helps-one-hurts.md) §7).
- `test/testitems/references/hainich_canopy_baseline_2010.txt` — regenerated for the flip:
  `gpp_annual` 1237.437115 → 1143.375187 (−7.60 %), `transp_annual` −4.38 %, `evap_annual` +0.93 %,
  `rootmoist_mean` +0.38 %, `interc_annual` unmoved. The producing run's `gps = false` control arm
  reproduced the previous `gpp_annual` to every printed digit in the same run.
- `test/testitems/biome_coupled_tests.jl` — the five coupled biome LE/GPP signatures re-measured; the
  `GPSTAND=0` control arm returned all ten pre-flip numbers to every printed digit. GPP moves −11.6 %
  (`boreal_siberia`), −6.0 %, −2.8 %, −0.5 %, −0.5 %, i.e. ordered by how much of the year each cell
  spends below full leaf, which is the mechanism's own prediction. Latent heat also falls at every cell
  (−1.05 % to −0.03 %) but not in that ordering, since it carries soil evaporation and interception too.
- `test/testitems/decadal_validation_tests.jl` — the decadal GPP level band re-stated `[1.0, 1.12]` →
  `[0.92, 1.02]` at a measured 0.964132 (width unchanged). F now sits ~3.6 % below the C over the decade
  rather than ~4 % above.
- `test/testitems/sapwood_bg_tests.jl`, `test/testitems/grass_structure_tests.jl`,
  `test/testitems/wscal_leafon_tests.jl`, `test/testitems/gpsum_basis_tests.jl` — pins, bands and
  guardrail-4 assertions re-pointed at the new default, each with the measured value and the reason.
- `test/testitems/slow_level_anchor_tests.jl` (line-S-owned) — the unanchored yr-25 retention floor
  re-pinned 0.7 → 0.55 (measured 0.618996) under line S's explicit authorisation. All four
  anchored-vs-unanchored contrast assertions were unaffected.

- `src/fdiff.jl` — the comment beside `tree_demand_gate` no longer asserts from code structure that the
  linear `tstress` factor emulates "that HALF" of the C's gate; it now cites the measurement. Comment
  only, no behaviour change.

### Fixed

- Two assertions that were written as `all(...)` over a vector — the decadal per-year GPP ratios and the
  annual water-stress series — now assert on the extremum instead, so a failure prints the number that
  moved rather than a bare `false`. The previous form cost a whole extra job to learn a magnitude.

### Notes

- The default flip was attempted once and reverted on the same day because its blast radius had not been
  enumerated; it came back at **23 assertions of 275 621 across eight files**, against 3–5 for each of the
  previous four flips. Ten of those were VACUOUS rather than wrong — the gate file's own control arm took
  the package default by omission and became a second copy of the treatment arm at the flip.
- ⚠ The canopy baseline's control arm reproduces the previous `gpp_annual` exactly but the four water rows
  only to ≤ 5.1e-4 relative. That drift is pre-existing and provably not the flip (all three arms in the
  producing run agree on `interc_annual` bitwise); this regeneration absorbs it so the next drift
  measurement starts from zero.
- **UNMEASURED, stated rather than implied:** the yr-150 unanchored retention under the flip. The suite
  reports yr 5 and yr 25 only. Line S has queued the long-horizon assertion in its own file.

- **ADR 0135's photosynthesis shortlist item (b) is CLOSED without a port and without a flag.** F's
  `agd`, `rd` and `vm` are exactly proportional to `tstress` — verified against F's own kernel to 1.6e-9
  — so the C's gate discards at most 1 % of an affected day's full-suitability value. At the hot end the
  threshold coincides with the `temp ≥ temp_co2_high` hard cutoff **by construction**
  (`k3 = ln(99)/(temp_co2_high − temp_photos_high)`), which F already carries, so only the cold end is
  live: below **+3.0 °C** for the tropical evergreen and **−6.0 °C** for every other tree.
  Assimilation-weighted, that is **0.046 %** of the annual total at `boreal_siberia`, **0.0063 %** at
  Hainich, and structurally **0** at the other three cells, whose temperature never reaches the
  threshold — 65× and 480× below the +3.0 % residual it was shortlisted to explain.
- **`boreal_siberia` carries the method finding: 47 % of its days are gated and the effect is still
  0.046 %**, because the gated days are the darkest and coldest of the year. A day count is not a
  magnitude — scored on incidence this item would have read as the largest term on the shortlist.
- Only item (c) (the phenology trajectory) remains on that shortlist. The count of faithful-but-worse
  terms in the compensating-error search is unchanged at four; this is not a fifth.

### Added

- `scripts/diagnose_rung2_kill_budget.py` — identifies why the rung-2 substituted demography kills 3.5–4.2×
  too few of the biomass-bearing trees (ADR 0187 §3), from the arm logs plus the `REC` dumps, with no model
  run. Five panels behind ADR 0185 §5's imported completion+coverage gate: the derived-a-priori self-test on
  the uniform arm, the ρ-clamp incidence, the `ρ ≥ 1` gate, the budget-vs-nominations decomposition, and
  FIT's own gross mortality and recruitment by a count identity over the `grow`/`mort`/`post` phases.

### Changed

- Nothing. No flag flipped, no default moved, no committed baseline regenerated, no `src/**` change.

### Fixed

- Nothing shipped was broken. Two basis errors were found and fixed *inside the new scorer* before its
  numbers were published, and both are recorded as reusable traps (ADR 0188 §8, skill `rung2-dump-analysis`
  traps 5g/5h): a recruit identity that ignored ADR 0123's deferred kills, and a gate stricter than the
  identity it was gating.

### Notes

- **ADR 0188** — the mortality budget is the NET count change, not the GROSS flux. ADR 0187 §B's first
  hypothesis (a kill quota formed on the >5 m emitted population under-killing the whole roster) is
  **refuted** by the harness's own algebra: ρ is a scale-free survival fraction applied to the whole-roster
  density, and the uniform arm spends its quota in full (realized/implied **1.004 ± 0.009**, 0.51 σ, against
  the 0.425 H1 requires). The ρ clamp is not binding either. What is wrong instead: the decision is gated
  `if ρ < 1.0`, so **42–46 %** of patch-years produce an empty kill list and a further **27.9 %** of `S1`'s
  years hit `_hazard_tilt`'s reported `θ = 0` give-up; and the budget `(1−ρ)·n_now` approximates the NET
  count change `K − R` while the flux that moves biomass is the GROSS `K`. Measured on FIT's roster: gross
  mortality **5.65–5.96 %/yr**, recruitment **4.62–6.46 %/yr**, net **−0.54/+0.25 %/yr** — near-stationary
  in count while turning over ~6 %/yr — against an operator budget of **0.78–1.02 %/yr**, i.e.
  **6.4–7.6× short**, with FIT's non-negotiable deaths alone overdrawing the whole budget **4.1–5.3×**. A
  mortality-only operator driven by a next-year count target structurally cannot express gross mortality
  flux, because recruitment is 78–108 % of mortality. The next action and its criterion are pre-registered
  with the lever's current size measured; the count channel (ADR 0186 §8.8) is not re-opened.

### Added

- `scripts/diagnose_rung2_kill_selectivity.py` — scores WHICH trees the rung-2 emulator kills against
  LPJmL-FIT's own kills, off the `mort`-phase roster dumps already on disk (no model run). Six panels:
  a provenance gate against the harness's own audit log, the mass-selectivity statistic
  `LAMBDA = kill_frac_m / kill_frac_n` on the discretionary population stratified by patch-year, the
  size-conditional mortality rate profile in the reference arm's own height quintiles, standardized
  selection differentials, the ADR-0186 §8 reachability clause, and a pre-registered verdict gated by a
  derived-a-priori self-test on the uniform-thinning arm (ADR 0187).

### Changed

- ADR 0186's framing "the emulator kills the right NUMBER of trees and the WRONG trees" is **narrowed**:
  the kill set is measured to be **not** size- or mass-biased (mass selectivity 0.93/1.00 against FIT's
  0.90; near-zero selection differentials; the size-conditional rate profile has FIT's shape). The
  shortfall is the mortality **rate** — 3.5–4.2× too few discretionary deaths, 58 % of FIT's annual mass
  flux, which compounds to 2.83–2.90× over the 81-year leg and so more than covers the observed +90 %
  biomass excess. ADR 0186's own numbers are unchanged (ADR 0187).

### Changed

- **Every control arm that means the pre-ADR-0136 `gp_sum` basis now states `gp_stand_leafon_basis = false`
  explicitly, instead of inheriting it as the package default ([ADR 0136](docs/decisions/0136-the-two-gp-sum-basis-differences-measured-one-helps-one-hurts.md) §7).**
  Byte-identical today — the default has not moved — and that is the point: the explicit value is written
  *before* the flip, not after. A trial flip of the default on 2026-08-13 failed **23 assertions of
  275 621 across eight files**, and **10 of them were one file's comparisons going vacuous** rather than
  wrong: `test/testitems/gpsum_basis_tests.jl`, written one commit earlier to gate this very flag, built
  its base arm as `with_water(p0, (;))` = "the package default", so at the flip it became a second copy of
  the treatment arm and both exact-boundary identities, the fires-off-the-boundary pair and the whole
  signed-direction loop stopped comparing anything. Hardened: that testitem's four arms (each now pinning
  **both** flags), `scripts/biome_sapwood_bg_probe.jl::mkparams` — from which the `Ag`/`Pg`/`gpS`/`vmG`
  arms and all 30 committed `M_growth_channel_decomposition.csv` rows derive — and the three sibling
  probes `biome_canopy_growth_probe.jl` / `biome_resilience_probe.jl` / `biome_slow_oracle_probe.jl`.
  Generalises [ADR 0133](docs/decisions/0133-the-tree-demand-gate-default-flip-is-earned-on-the-carbon-budget-and-paid-for-in-gpp.md) §6
  from probes to tests: **if an assertion's meaning depends on two arms differing, both arms must state
  their value; take the default by omission only in an arm that means "whatever ships".**
- **`scripts/biome_ensemble_pin_probe.jl` and `scripts/regen_fdiff_baselines.jl` gained the pre-flip
  opt-out (`GPSTAND=0` / `canopy_arm(; gps = false)`), wired and inert.** Step 3 of the default-flip
  procedure requires that the run producing the new pins also reproduces the old ones, which an opt-out
  added *after* a flip can no longer do. While the default is still `false` the opt-out arm is bitwise the
  default arm, and the probes assert exactly that — which is what proves the knob is wired to the field it
  names before anyone depends on it.
- **The `gp_stand_leafon_basis` default flip itself is RAISED TO LINE S and parked, not landed.** The 23rd
  assertion is `test/testitems/slow_level_anchor_tests.jl:181` (`ret_025 > 0.7`, measured 0.619 under the
  flip) — the unanchored control's year-25 retention, which is S-owned. An F default that moves an S gate
  is an integration point ([ADR 0059](docs/decisions/0059-the-c-faithful-water-stress-becomes-the-default.md) is the precedent:
  S gave an explicit GO before `wscal_leafon` flipped), so the request, both defensible readings and the
  full 23-assertion enumeration are written into `lines/S/STATE.md`. Nothing is degraded while it sits:
  the flag remains opt-in and off.

### Fixed

- **The runbook now records that GitHub SSH auth to this remote fails *intermittently*** (`CLAUDE.md` §5).
  `git fetch`/`push` can die with `Permission denied (publickey)` — indistinguishable from a revoked deploy
  key — and succeed on the next attempt: 2 of 3 consecutive `ssh -T` calls authenticated seconds apart. The
  entry gives the three-part confirmation (derive the pubkey from the private key, check the key is still
  registered `rw` via the API, then a retry loop) and flags the second-order trap that cost the most time
  here: **when the failing call is the fetch, every remote-tracking ref answers from the last successful
  fetch**, so `git log origin/main..HEAD` can report a pushed branch as unpushed. Same discipline as the
  `/p` EIO transient — prove permanence before declaring an outage.

### Added

- **The rung-2 level-anchor pre-flight, which retired a 264-job matrix in ~7 s ([ADR 0186](docs/decisions/0186-the-count-is-already-on-target-the-excess-is-per-stem-mass-so-the-level-anchor-has-no-lever.md)).**
  New `scripts/diagnose_rung2_anchor_preflight.py` derives what ADR 0103's `anchor` reduces to inside the
  rung-2 harness and pre-flights it against the `predict`-matrix arm logs already on disk — no model run,
  no SLURM job. **The algebra does not carry over from `slow.jl`:** the harness's feature row and count
  target are the >5 m emitted population while the coupled path uses the whole roster, so `patch_area`
  cancels and `ρ_eff = (target/n_prev)^(1−a)·(target/n_emit)^a`. Two measured consequences: the anchor is
  **identically inert in `roster` mode** (916 484 rows, `n_prev` bit-identical to `n_emit`, max |diff| 0),
  so no published `roster` number is at stake; and `a` moves only the ρ conversion, never the feature row,
  so ADR 0184's tether stays off. **Headline: the count is already on target and the excess is per-stem
  mass.** On the ssp370 leg at the FIT-gain cells `S1` holds **−2.9 %** stems and **+90.6 %** biomass
  (`S0h` −13.6 % / +89.0 %), with per-stem mass **+63…+246 %** corroborated by height +12…+45 % and
  `age_mean` +53…+160 % — and the per-year trajectory kills the rescue hypothesis, `S1`'s count staying
  within a few per cent of FIT's for **all 81 years** while biomass climbs monotonically to +91 %.
  ⇒ **ADR 0185 §7.5's pre-registered criterion (agb departure < +40 %) is unreachable by wiring the
  anchor**: granted a perfect anchor and proportional biomass — the most generous bound available — the
  surviving departure is **+75.6 % to +415.1 %**, and for `S1` it is *worse* than unanchored because the
  target sits below FIT's count while the mass sits far above it. ADR 0185 §7.2's named next action is
  withdrawn on measured grounds; its §7.1 conditioning-limited verdict **stands and is sharpened** (the
  displaced coordinate is size and age, not count). **Nothing here is a finding against ADR 0103's anchor
  in the coupled path**, where the measured departure genuinely is a count-level one (1.409× over-density,
  ADR 0103 §2). Panels (4)–(6) **import** `diagnose_rung2_map_target_response.py`'s `Leg`/readers/coverage
  gate rather than re-deriving them, and reproduce ADR 0185 §5's table exactly — a first version that
  re-implemented the basis put `S1`'s count departure at +37 % instead of −2.9 %, a sign flip on the
  quantity the decision turns on. No flag flipped, no artifact regenerated, no `src/**` change.

### Added

- **The two remaining `gp_sum` basis differences between the fast core and the LPJmL-FIT C, measured one
  variable at a time — one helps a lot, one is faithful and makes agreement worse
  ([ADR 0136](docs/decisions/0136-the-two-gp-sum-basis-differences-measured-one-helps-one-hurts.md)).**
  Discharges ADR 0051's registered-but-unmeasured item and executes ADR 0135's shortlist item (a). Both
  differences live in `gp_sum.c:53-67`, both are **exact identities at `phen = 1`** (i.e. partial-leaf-day
  effects), and both ship as opt-in `WaterParams` flags, **default off and byte-identical**.
  **`gp_stand_leafon_basis`** — the C builds each PFT's potential canopy conductance at FULL leaf cover and
  forms `Sum gp*phen / Sum fpc` with a PLAIN denominator; F_diff folded `phen` into the pass-1 absorbed PAR
  and into `gmin` and divided by the phen-weighted denominator, biasing its stand conductance high by
  `~1/mean(phen)` on any partial-leaf day and thereby raising its solved ci:ca ratio and its GPP. Switching
  to the C's basis LOWERS F's tree GPP at **5 of 5** biome cells (direction predicted before the arm ran;
  magnitude ranking predicted too, and smallest at the driest cell because conductance is supply-limited
  there). **On the shipping configuration** (per-PFT parameters + the tree demand gate + the prognostic
  below-ground wood pool) it improves **every cell and every aggregate**: mean `|GPP_F/GPP_C - 1|` over the
  four readable cells **0.0824 -> 0.0328** and mean `|bmi_F/bmi_C - 1|` **0.1266 -> 0.0535**, with Hainich's
  GPP excess going **+9.1 % -> +3.0 %** — from a basis fix with no new physics and no parameter. Its
  apparent overshoot on the historical control arm (boreal 1.044 -> 0.935) is a property of **that arm's
  reference**, not of the flag: ADR 0126 measured that boreal's agreement under beech parameters came from
  two wrong parameters of opposite sign, so a faithfulness fix scored against it necessarily looks like an
  overshoot. The default flip is pre-registered in ADR 0136 §7 with conditions 1-2 already met.
  **`lambda_vm_gp`** — the C's stomatal-optimisation bisection carries the Vcmax left by `gp_sum` (computed
  at a crown-cover, no-phen absorption) while its light-limited term uses the layered phen-scaled
  absorption; only the solved ci:ca ratio differs, because Vcmax does not depend on it and the C's final
  call recomputes at the layered absorption exactly as F_diff does. **No sign was predicted, deliberately,
  and the measured one is positive at all five cells:** the layered absorbed fraction EXCEEDS crown cover in
  a real stand (0.282 vs 0.151 for the unit roster's dominant stem), so the C's Vcmax is the smaller one.
  **A more faithful arm therefore scores WORSE — making this the third independent term to say the fast
  core's true tree-photosynthesis error is LARGER than the GPP ratio that measures it** (ADR 0135 found two
  more, both making F absorb less light while its GPP sits above the C's). Read that ratio as a lower bound.
  `lambda_vm_gp` is explicitly NOT a flip candidate until the compensating error is found; it ships as the
  faithful control for that search. Gated by `test/testitems/gpsum_basis_tests.jl`, which pins both
  exact-boundary identities **bitwise**, each with a matched "the flag actually fires" partner so a green
  identity cannot be an inert code path, and asserts **no sign** for `lambda_vm_gp`. Suite 275 621 pass /
  0 fail with no committed baseline moved; `M_growth_channel_decomposition.csv` gains six arms as **30 added
  lines with 0 pre-existing lines changed**.

### Added

- Line S: `NPREV` mode knob on both rung-2 map-target scorers
  (`scripts/diagnose_rung2_map_target_response.py`, `scripts/diagnose_rung2_map_on_rec_stand.jl`),
  selecting which `--n-prev` matrix of dumps is read. Default stays `roster`, so every published
  number reproduces unchanged. The Julia replay gained the shipped `n_prev[patch] = target`
  recursion, mirroring `rung2_s_demography_harness.jl`.
- Line S: a pre-registered SEPARABILITY GATE in the response scorer — median
  `|target/n_emit - 1|` per arm and leg, printed before any response statistic and suppressing the
  verdict for any arm that fails it (ADR 0184 §10.4). It refuses the `roster` matrix and admits the
  `predict` one at the same threshold.

### Changed

- Line S: the rung-2 warming-response limit is now attributed to the STAND the count model is
  conditioned on, not to the substitution operator (ADR 0185). On the 264-job `--n-prev=predict`
  matrix (258 completed), the map handed FIT's own stand reproduces FIT's gain direction at 4 of 5
  cells while the do-nothing null returns 1 of 5; handed each arm's own stand it returns 1–2 of 5.
  The pre-registered `CONDITIONING-LIMITED` branch fires. The operator-limited hypothesis is
  untested rather than refuted.

### Added

- **Rung-2: the count model's target is tethered to the live stand count, so the warming-response question
  is unanswerable as run — and the arms' stand structure departs by 2×** (line S, ADR 0184). Closes the
  action ADR 0182 pre-registered, with no new model run: the substitution harness already recorded its own
  count target at every rendezvous, so four of the five arms were already measured. New
  `scripts/diagnose_rung2_map_on_rec_stand.jl` supplies the one missing arm (LPJmL-FIT's own roster) by
  replaying the recorded dumps through the *shipped* feature assembly and forest, gated bit-identical
  against the live harness log in the year before any arm diverges; new
  `scripts/diagnose_rung2_map_target_response.py` scores what the map ASKED FOR against what the stand
  REACHED. **Headline:** all 767 rung-2 runs used `--n-prev=roster`, which hands the model the live stem
  count, and the model then returns a count within ±5 % of it in ~85 % of patch-years — its target *is* the
  live count to ±2.3 %. So the two quantities the probe was meant to separate are the same quantity, the
  basis check is passed by a persistence null that learns nothing (12/12 cells, slope 1.06), and the
  pre-registered verdict branch is **overridden as NO VERDICT**. This reconciles three earlier results as
  one mechanism — with the live count the model is accurate but mute, without it expressive but
  mis-levelled — and narrows the earlier "indistinguishable from doing nothing" to a statement about the
  configuration rather than about what the model learned. **Second, independent finding:** nothing anchors
  the stand's size/age structure, and by 2100 the arms hold ~15 % fewer stems but **+99–106 % above-ground
  biomass and +47–84 % mean age** than FIT (the do-nothing null +312 %/+160 %), growing monotonically from
  ~+38 % at the historic leg — a real conditioning defect that no count-based statistic on this line
  detects. A never-before-run `--n-prev=predict` smoke (12 jobs) confirms the map's count state decouples
  from the live stand there (±24 %, ±28 % late century) ⇒ the question *is* answerable in that mode, and the
  full 264-job matrix was submitted. `scripts/rung2_s_demography_harness.jl` gains the repo's standard
  `PROGRAM_FILE` guard so its definitions can be reused instead of copied.

### Added

- **Scoping the photosynthesis half of the assimilate error: the light INPUT to the fast core's tree
  photosynthesis is faithful to the live C, so the GPP excess is in the kernel
  ([ADR 0135](docs/decisions/0135-the-light-input-to-tree-photosynthesis-is-faithful-so-the-gpp-excess-is-in-the-kernel.md)).**
  New 2-second, simulation-free audit `scripts/diagnose_layered_light_basis.py` checks every factor of
  `apar = par·(1−albedo_leaf)·alphaa·fpar` against the LIVE lines of LPJmL-FIT: `par` (`petpar3.c:74`),
  `alphaa`, `albedo_leaf`, the vertical layered Beer–Lambert light model (`getfpar.c`), its leaf-area
  density and `atoh>40` cap, `k_lambert`=0.5, `VSTEP`, crown geometry, and the SLA Vcmax cap (per stem,
  `issla = config->individual` ⇒ ON) — **all match**. The port's basis is additionally scored against a
  quantity the C *emits* rather than against its source: patch LAI reproduces the run's own `LAI_STAND` at
  **0.878 / 0.869 / 0.981 / 0.907** at boreal / Hainich / mediterranean / Sahel, below 1 by exactly the `ind`
  writer's 5 m cut (`tropical_amazon` 0.574 is printed as `CHECK`, not smoothed). **Two live differences
  remain and both make the fast core absorb LESS PAR than the C, while its tree GPP is measured 1.074× ABOVE
  the C's — so neither explains the excess and the kernel-side error is larger than the measured ratio:**
  phenology is applied after the layered share instead of inside the extinction (per-DAY upper bound 15.0 %,
  38.9 %, 19.5 %, 15.0 %, 47.5 % of the core's own absorption at `phen≈0.45`; the annual weight of such days
  is **not** measured, and no default or parameter may be published from a bound), and there is no
  `(1−snowcover)` factor at all (not priceable from the `ind` table — listed, not measured). ⚠ **A first pass
  of this audit produced a 5–37× optical-thickness "defect" that does not exist:** `getfpar.c:108-124` holds
  three expressions for one quantity and both `grep` and a `sed` range land inside its `/* test: */` comment
  blocks. Recorded as a durable trap in `CLAUDE.md` §3 and as `residual-diagnosis` §10 — a commented-out
  branch is a dead path that no config check and no `grep` output distinguishes from live code. The only
  source change is a corrected comment in `src/fdiff.jl`, which had justified the layered-light port with
  ≈0.83 as "the true layered fraction" when 0.83 is the emulator's own absorption and the C output named
  beside it (`d_fapar`) is built from a different variable and cannot validate it. No behaviour change, no
  flag, no default. Remaining shortlist for the photosynthesis half, with the C line that scopes each: the λ
  solve's Vcmax basis, the `tstress<1e-2` hard zeroing, and the phenology trajectory itself.

### Added

- **Line S:** `scripts/diagnose_rung2_stand_warming.py` — scores whether each rung-2 arm's OWN stand shifts
  between the historic and ssp370 legs, against LPJmL-FIT's own stand at the SAME cells, from the roster
  dumps already on disk (no LPJmL run). Reconstructs the six `flux_feature_vector` stand features per
  (year, patch) at the `grow` rendezvous with the runtime's own formulas, gates on complete legs, runs the
  mandatory liveness panel first, and carries a declared DRIFT CONTROL (the same shift between the two
  halves of the historic leg, where there is no warming excursion). Caches one small `.npz` per dump, so the
  ~38 GB text scan is paid once (ADR 0182).
- **Line S:** `scripts/diagnose_rung2_ported_certain_set.jl` — measures the ported per-individual hazard's
  certain-kill set against LPJmL-FIT's own on the same rosters, reaching `TraitMortality.mortality_hazard`
  as the shipped name rather than copying it, plus a ZEROED-STRESS arm that evaluates the hazard exactly as
  the coupled loop runs it (ADR 0183).

### Changed

- **Line S: `trait_mortality` now defaults to `true`** in `FluxDrivenSlowEmulator`
  (`src/components/slow.jl`), so the ρ-thinning runs on the ported FIT per-individual hazard rather than one
  composition-preserving factor. ADR 0176 §4's pre-registered flip criterion (≥ 12 cells, recall AND
  precision ≥ 0.8 of the ported certain-kill set against FIT's own) is met by a wide margin: over
  **1 568 744 stem-years at 15 cells**, both scenarios, recall = precision = **1.0000** with mean
  |Δhazard| = **5e-18**, and still **recall 0.909–0.972 at precision 1.0000** with `water_stress`/
  `temp_stress` zeroed, which is how the coupled loop actually feeds it. **Guardrail 4 is re-served by the
  opt-out `trait_mortality = false`** — every control arm wanting the pre-0183 operator must pass it
  explicitly instead of relying on the default (ADR 0183). Measured blast radius of the flip, from the full
  CI-faithful suite run with only the default changed: **5 assertions of 275 605**, all in
  `test/testitems/slow_trait_mortality_operator_tests.jl` and all one cause — that file's control arm relied
  on the old default and became a second copy of the arm. No conservation gate, AD gate or committed
  baseline moved. The control now passes `trait_mortality = false` explicitly and a new assertion checks the
  new default on the constructor.

### Fixed

- **Line S:** ADR 0176 §4's premise is corrected — the rung-2 `S0h`/`S1` arms were already using the PORTED
  hazard, not FIT's own (`rung2_s_demography_harness.jl:539` reads `Tree.mort`, which is
  `TraitMortality.mortality_hazard`; the harness never reads the dump's `mort_prob`). Only an inline comment
  said otherwise (ADR 0183 §2).
- **Line S:** the line handoff's claim that a small stand shift in a rung-2 arm would indict the fast core is
  corrected — the Julia fast core never runs in a rung-2 arm, where the C grows the stand (ADR 0182 §6).

### Added

- `scripts/diagnose_leaf_turnover_regime.py` — audits the C's per-individual leaf-turnover basis at the
  five coupled biome cells from its own `ind` table (variability audit, retained-leaf fraction per
  branch with a per-cell CANNOT BIND / CAN BIND verdict, and the SLA–longevity corridor). Runs in
  seconds.

### Changed

- **Retired `AllocParams.is_deciduous` as the `boreal_siberia` allocation suspect** (ADR 0134). The
  C's leaf-recycle gate is a runtime latch (`tree->isphen`), not a per-PFT flag, and its two branches
  evaluate to the *same number* for any stem whose leaf longevity is at or below 1.05 yr — which
  measured is 100.0 % of the larch and BoBS stems that are 99 % of that cell. Stem-weighted, F over-
  sheds 0.3 % of the leaf pool there, so no latch-incidence measurement can revive the item. The gap
  is relocated to `tropical_amazon` (12.4 %) and `mediterranean_iberia` (24.8 %), both upper bounds
  until the latch incidence is measured; no default, parameter or recommendation is proposed on that
  basis.
- **Recorded that leaf longevity is a per-individual, SLA-derived trait** (`new_tree.c:215`, emitted
  as the `ind` column `Longevity`), distinct from the per-PFT `turnover.leaf` residence time F stores
  in `AllocParams.turnover_leaf`. No active defect — F's tree path never reads `turnover_leaf` — but
  wiring it into a non-latched branch would retain 0.75 of the leaf pool where the truth is 0.44.

### Fixed

- **Corrected two claims about why F's uniform tree leaf-recycle is faithful** (ADR 0134). The
  `pft_allocparams` docstring in `src/fdiff.jl` justified `AllocParams.is_deciduous = true` by "every
  tree PFT in this configuration is `summergreen` under `new_phenology`". That is true of the parameter
  file and irrelevant to the code: under `new_phenology:true` the `phenology` key is never read for
  leaf turnover, because `daily_natural.c:123` dispatches to `phenology_gsi` and
  `phenology_tree.c`'s phenology switch is dead. The load-bearing reason is the clamp in the C's own
  non-latched branch, `1/max(pft->longevity, 1.05)` (`turnover_daily_tree.c:38`), which caps the drip
  rate at the latched branch's own 0.9524/yr.
- **Replaced an assertion in `scripts/build_pft_fdiff_params_reference.py` that could not fail.** It
  checked `phenology == "summergreen"` for tree ids 0–6 — an inert key, so it would only trip on an
  edit that changes nothing while staying green through the edit that matters. It now asserts the
  `1.05` clamp constant and that each tree's `longevity` is still the `{mean, interc, slope, sigma}`
  corridor form positioned above the clamp, i.e. the quantities a real change would move. The
  committed 43-column `M_pft_fdiff_params.csv` is unchanged and still reproduces byte-for-byte under
  `CHECK=1`.

### Added

- `scripts/slow_stand_forced_response_probe.jl` — hands the tree-count emulator the original model's own
  forest description under both climate scenarios, with no simulation loop anywhere, and asks whether the
  warming response appears. It splits the emulator's inputs into the four groups that different parts of
  the system compute at run time — the daily physics, the forest's own carbon pools, the emulator's own
  memory of last year, and the climate — and moves one group at a time from present-day to end-of-century
  values, so the answer says *which part of the system has to carry the response*. Covers 51 767 of the
  54 020 forested cells, holding out whole cells, and writes its predictions in the format the existing
  scoring script reads so every arm is scored in one process against the same reference.

### Fixed

- The probe's own verdict originally keyed on a statistic that a do-nothing baseline scores just as well on
  (all four arms, that baseline included, land between 0.97 and 1.03), so it announced success for an arm
  the binding statistic rates as partial. The correct thresholds were already written into the file before
  the run and simply were not the ones used. The script now refuses to announce a verdict and names the
  statistic that decides it.
- Recorded the trap that the scoring script writes its summary into a committed shared reference file by
  default, and that running it for count arms alone silently deletes every trait row from that file. It now
  prints the redirect that avoids this. Nothing was committed; the file was restored.

Nothing shipped changed: no defaults were flipped, no trained artifact was regenerated, and both jobs write
only to scratch.

### Measured

- **The tree-count emulator is a description of the forest, not a response to the weather.** Handed the
  original model's own forest, the count it predicts follows that model's warming-driven change almost
  exactly (a slope of 0.99 against the truth) — but essentially all of that comes from the forest
  description itself (biomass, cover, height, age). The two climate inputs contribute a slope of 0.016 and
  the four daily-physics inputs 0.037. The count is close to an arithmetic consequence of the forest it
  sits in, so its response to warming is inherited rather than learned. This confirms, on 51 432 cells and
  with a completely different instrument, what an earlier 12-cell check had found for the climate inputs
  alone, and extends it to the physics inputs, which had never been tested.
- **Even given a perfect forest, the emulator recovers only 29 % of the original model's total warming
  response** (0.292 against 0.707 for the shipped version), and it gets the tropics wrong by a factor of
  −2.5. So the response is not lost in how the emulator is trained to predict; redesigning what it predicts
  — the plan this measurement was run to price — is not where the problem is.
- **A correction to an earlier conclusion of our own.** An earlier control run was summarised as showing
  that no warming response reaches the count emulator through the forest. Read at the source, that control
  froze only the four climate inputs; the eleven others stayed live on a forest the original model was
  still growing under a warming climate, so any response arriving that way was counted as "drift" by
  construction and was never separated out. The control's own numbers and its conclusion about the climate
  inputs stand; the broader sentence built on it does not, and it had propagated into two later documents
  and the working handoff.
- **Removing last year's tree count is worse than it looked.** An earlier measurement priced that change as
  tripling the climate signal. Scored on the statistic the deliverable is actually judged on, the same
  change takes the total warming response from 0.707 to 0.292 and the tropical response from −0.47 to
  −2.48. Both readings are correct — the small climate channel does triple — because most of the shipped
  model's apparent response was simply repeating last year's answer.

### Changed

- **The C's per-tree photosynthesis demand-gate is now ON by default** (`WaterParams.tree_demand_gate`,
  ADR 0133), discharging the flip criterion ADR 0131 §8 pre-registered before the gate existed. All three
  conditions met: the below-ground wood growth port landed (ADR 0132); the assimilate error
  `mean |bmi_F/bmi_C − 1|` over the four readable biome cells FALLS 0.1914 → 0.1581 on the pre-registered
  arm pair and 0.1599 → 0.1266 on the current most-faithful growth arms (−21 % of the error, same −0.0333
  in both); and the blast radius was measured before any baseline was touched — **4 assertions of 275 597**,
  two of them the "default is off" assertions themselves.
- **Two committed baselines deliberately re-measured**, each by a harness that reproduces the pre-flip
  numbers in the same run: the Hainich canopy annual totals (`gpp_annual` only, 1250.124 → 1237.437; the
  four water rows at ratio exactly 1.0, which is the mechanism's own prediction) and the coupled 5-cell
  LE/GPP pins (the new `TREE_GATE=0` opt-out arm reproduced all ten previous pins to every printed digit).
- **The cost is stated with the gain:** the photosynthesis channel gets slightly WORSE
  (`mean |gpp_F/gpp_C − 1|` 0.0570 → 0.0611), entirely at `semiarid_sahel` (0.906 → 0.855), while boreal
  and Hainich improve; coupled stand cover falls 3.1 % at boreal and 1.0 % at Hainich. `semiarid_sahel`'s
  2-year coupled GPP nevertheless RISES 1.6 %, because the gate stops F paying leaf respiration against a
  collapsed assimilation on drought days, so that cell's canopy grows instead of shrinking.

### Fixed

- **Four probes had control arms that would have been silently relabelled by the flip** — the arms in
  `biome_sapwood_bg_probe.jl` / `biome_canopy_growth_probe.jl` / `biome_slow_oracle_probe.jl` /
  `biome_resilience_probe.jl` that MEAN "gate off" now say so instead of inheriting a default that moved.
  Worst case, and it would have been silent: the first probe builds its gated arm by copying its ungated
  one and setting the flag, so `Ag ≡ A` and `Pg ≡ P` would have collapsed and 30 committed rows of the
  growth-channel decomposition would have been reproducible only under labels that no longer described them.
- **A guardrail-4 assertion written one week earlier became a green test that proved nothing**, and is now
  closed with its reason asserted rather than assumed: at the soft default sharpness the gate's sigmoid
  saturates to exactly 1.0 on every day of that fixture's forcing, so "the default reproduces the opt-out
  bit-for-bit" kept passing after the flip for a reason that had nothing to do with the flag.

### Added

- Two diagnostics that answer, from the trained artifact alone and with no LPJmL run, why the tree-count
  emulator shows no warming response — closing the question the frozen-climate control left open
  (ADR 0179, ADR 0180).
  - `scripts/slow_climate_partial_dependence_probe.jl` — sweeps the shipped count model over its two
    climate inputs, on its own training rows, using the exact warming excursion the response campaign was
    fed. Reports a channel-liveness panel (split counts per input) first, a pooled between-cell panel and a
    within-cell panel side by side, and a live-channel scale anchor in the same units, so "flat" is
    falsifiable.
  - `scripts/slow_nprev_ablation_probe.jl` — a one-variable arm that neutralises the previous-year
    tree count in place (not dropped, so the fit's internals are unchanged) and retrains the control in
    the same process, to price a retrain before buying it.

### Measured

- **The count model's climate input is wired up and carries almost nothing.** The forest splits on the two
  climate inputs 77 440 times (10.2 % of all splits, thresholds spanning the whole global range), so it is
  not blind to climate by construction — and yet moving climate across its entire global range changes the
  predicted stem count by 0.28 stems, and moving it by each cell's own historic-to-2100 warming changes it
  by 0.057 stems: 4.4 % of what a channel that does work produces on the same rows, and under 10 % of the
  original model's own response at 9 of 12 cells. A third explanation added before the run — that a global
  fit learned climate as a location label rather than as a response — was also refuted. ⇒ the defect is the
  training target and feature set, not the coupled loop.
- **Removing the previous-year count triples the climate response and is still ~7× short.** 0.084 → 0.238
  stems (4.7 % → 13.5 % of the original model's response), larger at 13 of 15 cells, for 0.018 of predictive
  skill. Reported as a partial result, not a fix: it buys magnitude, not direction (7/12 → 8/12 cells with
  the right sign), so it does not on its own justify a global retrain.
- **The stem count is nearly determined by the stand it sits in.** With the previous-year count removed
  entirely, predictive skill is 0.9620 — indistinguishable from simply repeating last year's answer
  (0.9623), because the remaining inputs describe the same year's stand and a stand of a given biomass,
  cover, height and age holds a nearly fixed number of trees. So the count model's climate inputs are a
  small correction on top of a stand-to-count map, and the warming response has to arrive through the fast
  physics moving the stand.

Nothing shipped changed: no defaults were flipped, no trained artifact was regenerated, and both probes
write only to scratch.

### Added

- **A frozen-climate control for the warming-response experiment, and the decomposition it enables.** The
  two scenario legs differ in length (20 vs 81 years), so a raw historic→future difference mixes the
  climate response with 61 years of free-running drift. `BOUNDARY=frozen` reruns the future leg with the
  climate held at present day — same restart, same seeds, same leg length — so `transient − frozen` is the
  climate response with drift removed and `frozen − historic` is the drift.
  `scripts/diagnose_rung2_response.py` now reports that decomposition per cell and per arm.

### Changed

- **The measured warming response is now known to be ~0, not 1.4× too strong.** With drift differenced out,
  drift accounts for 94–100 % of the apparent response and the surviving climate term's slope against the
  original model's own change is −0.03 to +0.04 for every arm. The control validates itself: the
  do-nothing arm's climate term is exactly 0.000 at all 12 cells, as it must be. Recorded in decision
  record 0178, which narrows 0177's magnitudes without withdrawing its per-cell or sign results.

### Added

- **F_diff: the C's below-ground wood sink is now prognostic (opt-in, ADR 0132).** `TreePools` gains
  `heartwood_bg_c` beside `sapwood_bg_c`, and `grow_individual` / `FDiffFastCore` / `rollout_canopy_years`
  gain `bg_growth`: the below-ground `sapwood_bg → heartwood_bg` turnover (`turnover_tree.c:124-130`) plus
  the C_LATERAL demand top-up deducted from the assimilate *before* the leaf/root/sapwood split
  (`allocation_tree.c:163-209, :268-277`). The port is a pure redistribution — `vegc_full_ind` is
  unchanged between the on and off arms on all 272 committed Hainich stems — which is why the second pool
  is not optional. Default off ⇒ byte-identical (275 597 pass / 0 fail, no baseline moved).
  New gate `test/testitems/sapwood_bg_growth_tests.jl`.
- **`FDiff.sapwood_bg_seed`** — the below-ground pool a stem in the C actually *holds*, `(1−turnover_sapwood)`
  times the C_LATERAL demand. Seeding at the bare demand (the previous convention) makes the pool and the
  demand shrink in lockstep so the annual top-up computes as **exactly zero**: the top-up fires on 0 of 272
  Hainich stems with the old seed and 205 of 272 with this one.

### Changed

- `FDiff.vegc_full_ind` now includes **both** below-ground wood pools, i.e. the C's own `vegc` pool set
  (`veg_sum_tree.c:25`). `vegc_ind` is unchanged. Byte-identical while the pools are 0.
- `scripts/biome_sapwood_bg_probe.jl` gains arms `Abgg`/`Pbgg`/`Pgbgg` and a PART 7 scoring ADR 0127 §6's
  pre-registered criterion: the paired surplus drops **51.3** gC/m²/yr at `temperate_hainich` (bar 30.9,
  **PASS**) and **19.2** at `boreal_siberia` (bar 19.9, **FAIL** — the outcome ADR 0127 §5's own
  `dD/bel_C = 0.11` predicted for that cell). All 35 pre-existing rows of
  `test/testitems/references/M_growth_channel_decomposition.csv` are byte-identical; 15 rows added.

### Added

- **The rung-2 warming-response experiment (line S).** The learned demography now runs inside LPJmL-FIT's
  own physics over *both* legs of the scenario pair — historic 2000–2019 and ssp370 2020–2100 — at 15 cells
  spanning the global climate range, so the deliverable is a measured *response* rather than a present-day
  agreement number. New: `scripts/build_rung2_boundary_series.py` (the per-cell/scenario/year bioclimate the
  count model conditions on, plus the frozen-climate control), `scripts/select_rung2_response_cells.py` +
  the committed `test/testitems/references/S_rung2_response_cells.csv` (a pre-registered cell set that keys
  on present-day climate only), `scripts/run_rung2_response_matrix.sh` (the whole matrix), and
  `scripts/diagnose_rung2_response.py` (per-cell response, error-in-variables slope, Cochran's Q).
- **A frozen-climate control arm.** The two scenario legs have different lengths (20 vs 81 years), so a raw
  historic→ssp370 difference mixes a genuine climate response with 61 extra years of free-running drift.
  `BOUNDARY=frozen` reruns the ssp370 leg with the climate held at present day, so the difference between
  the two isolates the climate channel with drift removed.

### Fixed

- **The rung-2 harness conditioned every year on a frozen present-day climate.** It read its four-column
  bioclimatic tail once from the per-cell registry, which holds the 2000–2019 climatology. On an ssp370 leg
  that showed the count model present-day climate for all 81 future years, which would have driven any
  measured warming response to ~0 *by construction*. It now advances the tail per year, the same treatment
  the shipped runtime already applies (ADR 0026) and the one the pooled production model was trained under.
  Passing no series keeps the old static behaviour, so ADR 0176's arms still reproduce byte-for-byte.
- **`scripts/run_daily_subset.sh` could not generate a runnable ssp370 config at all.** Its CO2 forcing path
  named a loose file that was removed when a sibling directory was reorganised on 2026-07-27/28, so the
  branch died in pre-flight with `ERROR100: Cannot open file`. Repointed to the recovered copy and verified
  by checksum and size.
- **The recorded baseline and the arms had drifted onto different binaries.** The baseline path used
  whatever `bin/lpjml` currently is, which gained the ADR-0130 `ind`-writer switches on 2026-08-12, while
  the arms run `bin/lpjml_rung2_v6`. Baseline recording now lives in the same script as the arms and is
  pinned to the same executable by construction.

### Added

- **`WaterParams.tree_demand_gate` — the C's photosynthesis demand-gate for TREES** (opt-in, default off ⇒
  byte-identical; ADR 0131). `water_stressed.c:196` runs photosynthesis only when the canopy's own demand
  `gpd > 1e-5`, and `:83` has already zeroed leaf respiration `*rd`, so on a gated day the C's PFT makes
  neither gross assimilation nor leaf respiration. That gate is per-`Pft`, and this configuration runs
  `individual:true`, so it applies to every tree — but F_diff's existing `grass_demand_gate` is
  `ind.is_grass`-gated, leaving the tree path ungated since it was written. Measured on all five biome
  cells: it flips `semiarid_sahel`'s annual tree carbon balance from **−83.8 to +34.6 gC/m²/yr** on its own,
  and reduces mean `|bmi_F/bmi_C − 1|` over the four readable cells by **17.5 %** on the shipping parameter
  configuration. The default flip is pre-registered behind the `sapwood_bg` growth port (the two act on the
  same carbon-use-efficiency channel and partially cancel).
- `test/testitems/tree_demand_gate_tests.jl` — pins the mechanism: default off, the off-path reproduces a
  bare `tebs_params()` rollout bit-for-bit, a grass individual is byte-identical when only the tree flag
  flips, the trees are not, and stand GPP is monotone under the gate.
- `scripts/biome_sapwood_bg_probe.jl` — arms `Ag` / `Ags` / `Pg` and PART 6, with the prediction the arm
  tests written down before it ran (it was refuted, which is the result). `arm`/`run_one_year!` gained
  `params` / `grass_gate` keywords; the pre-existing arms A/Abg/P/Pbg are byte-identical.

### Changed

- `test/testitems/references/M_growth_channel_decomposition.csv` — three arm rows appended per cell; every
  pre-existing data row is byte-identical (only the arms legend gained three comment lines).

### Fixed

- `docs/notes/sapwood_bg_design.md` §1/§6 and `docs/notes/phase3_fdiff_cbinary_validation.md` §13 predicted
  the **wrong sign** for this fix, because both assumed every demand-gated day is carbon-negative. With
  `A = gpp − rd`, gating scales `A` by a factor in `(0,1]`, so a gated day raises NPP only where its ungated
  `A` was negative — which is true at `mediterranean_iberia` and false at `temperate_hainich`. Amended in
  place with a pointer to ADR 0131.

### Added

- **Two opt-in C-oracle switches that give the `ind` table the whole stand and REAL per-stem GPP**
  (`patches/lpjmlfit_ind_true_gpp.patch`, ADR 0130). `LPJ_IND_ALL_HEIGHTS` drops the writer's 5 m
  emission cut; `LPJ_IND_TRUE_GPP` swaps in a new `Pft.agpp_gross` accumulating the same `gpp` that
  feeds the `D_GPP` output. Both are **inert unless set** — `agpp`, `printind` and the frozen
  29-column schema are untouched, and neither field is in `fwritepft`/`freadpft`, so
  `restart_1999.lpj` still loads. Rebuild gated on a matched A/B against the preserved previous
  binary: **139 decoded quantities + `globalflux` identical, 0 differ**.
- `scripts/run_ind_true_gpp_cells.sh` — provisions the runs (inserts the `ind` output entry and the
  exports the integrator-owned wrappers do not forward, and **re-validates with `lpjcheck` after
  patching**, which the wrapper's own pre-insert check cannot do). ~10 s per cell.
- `scripts/diagnose_ind_true_gpp.py` + `test/testitems/references/M_ind_true_gpp_reference.csv` —
  the scorer and its committed fixture. Its gate is also a completeness proof: the sum of
  per-individual `gpp` over all PFTs reproduces the run's own annual `d_gpp` to **4.4e-07 over 100
  cell-years**.
- `scripts/biome_sapwood_bg_probe.jl` PART 5d — the split recomputed with both C columns on F's own
  population, printed beside the old ones with `ln(NPP)` as an invariance check.

### Fixed

- **ADR 0129's photosynthesis-vs-respiration split was a bracket (38–78 %); it is now closed at
  ≈43–47 % photosynthesis / ≈57–53 % respiration at the prototype cell** (ADR 0130). The upper end
  is refuted, so the GSI phenology is not the single cause of F's assimilate error.

### Documentation

- **The `ind` table's `gpp` column is a second copy of `npp`, and LPJmL-FIT emits no per-individual
  GPP at all** — `daily_natural.c:193` does `pft->agpp += npp;`, so a per-stem `npp/gpp` is exactly
  1.0000 in all 11 967 tree rows at the five biome cells. This is why removing the height cut alone
  would not have closed the bracket. No published number is affected (every consumer reads `npp`).
  Recorded in `CLAUDE.md` §3 and the `lpjmlfit-cbinary` skill, which also gains the
  build-your-own-A/B rebuild-gate rule and the `ind`-TXT reading traps (it has a header; pin the
  dtypes, because the uninitialised `mort_*` columns defeat type inference).

### Added

- Rung-2 arm `S0h` (`scripts/rung2_s_demography_harness.jl`): uniform thinning that does not override
  deaths LPJmL-FIT's own hazard had already settled. It is the decomposition control that separates the
  two effects bundled into the trait-mortality arm (ADR 0176).

### Changed

- `scripts/diagnose_rung2_armc.py` now auto-discovers the line-S arm dumps (`--glob`) and reads the
  harness log **by its `#H L` header** instead of by column position — the two harnesses that write that
  file do not share a column order, so the positional reader would silently have scored one arm on
  another's columns.

### Fixed

- Nothing shipped changed. The persistence-null arm is confirmed seed-independent — two runs identical in
  every initialised column over 55 546 tree records (ADR 0176 §5).

### Added

- **Line S, rung 2 — the learned demography can now be run inside LPJmL-FIT's own physics.**
  `scripts/rung2_s_demography_harness.jl` serves the C's demography substitution hook from the **production
  count model**: ρ comes from the shipped count DRF evaluated on a feature row built off the C's own live
  roster, with arms `S0` (uniform thinning, the shipped default), `S1` (the trait hazard's ordering) and `NP`
  (the persistence null, ρ = 1). Establishment stays with the C in all three, so every number is a mortality
  result. Unlike arm C (ADR 0124), which took its count target from the ported hazard or the recorded
  baseline, this asks the learned model. (ADR 0175)
- **`patches/lpjmlfit_rung2_hook_v6.patch`** adds `rootzone_w` / `rootzone_whcs` to the hook's per-patch
  record — the one Component-S conditioning feature (`soilmoist`) that no other dumped record could supply.
  Rebuilt binary `bin/lpjml_rung2_v6`; the rebuild-equality gate passes (110 decoded quantities identical,
  `ind` byte-for-byte), and `scripts/diagnose_rung2_rootzone_column.py` proves the new column reproduces the
  run's own `d_rootmoist.nc` to **5.3e-08** relative — the float32 precision of the output. (ADR 0175)
- **`FluxDrivenSlowEmulator(...; roster_n_prev = true)`** re-synchronises the count model's `n_prev` feature
  and the denominator of ρ to the **live roster's own stem count** instead of the emulator's previous
  prediction. Default `false` ⇒ byte-identical. (ADR 0175)

### Changed

- `flux_feature_vector` is split so its body takes `(boundary, ages, n_prev, …)` with the
  `FluxDrivenSlowEmulator` method as a one-line wrapper, letting an external harness whose stand belongs to
  the C build the feature row through the same implementation instead of copying it.

### Fixed

- **Diagnosed a train/inference shift in the shipped coupled emulator (ADR 0175).** The count DRF's `n_prev`
  column was trained as FIT's own previous-year stem count for that patch, but at runtime
  `reconcile_demography!` sets `s.n_prev = target` every year and nothing ever re-synchronises it with the
  roster the other ten feature columns are read from — so the feature row describes two different stands, and
  they diverge without limit. This gives a mechanism for ADR 0113–0116's measurements (free-running destroys
  the response and leaves the level alone; variance and correlation preserved at lead 80, so not a
  regression to the mean; declines under-followed more than increases). **No fidelity number has been
  measured with the flag on yet** — the default stays off until an arm measures it, and the falsifier is
  pre-registered in the ADR.

### Added

- **Rung 3: F's assimilate error at the temperate prototype is split into a photosynthesis and a
  respiration channel, and the split is a measured BRACKET rather than a number** (ADR 0129). The
  fast core takes in ~24 % more carbon per year than LPJmL-FIT does over the same trees, and that is
  77 % of its excess above-ground growth there — but "carbon taken in" is a net flux, and the two
  explanations on record each blamed a different half. Separating them by the exact identity
  `net uptake = photosynthesis × carbon-use efficiency` shows **both are live**: photosynthesis runs
  +8.4 % and carbon-use efficiency +14.0 % as measured. However, the tree list the reference model
  writes out drops every stem under 5 m, so the emulator's stand is missing trees that the reference's
  gross-photosynthesis output still contains. That biases the two channels in opposite directions by
  the same factor — leaving every previously published net-uptake number untouched, and leaving the
  split between the channels undetermined at anywhere from 38 % to 78 % photosynthesis. The
  year-to-year test that would settle it was measured to have a standard error of 3.6 on a quantity
  whose two candidate values are 0 and 1, i.e. it has no power and its apparent answer means nothing.
  Reported as a bracket. Closing it needs a small change on the reference model's side (writing out
  the short stems too), not another emulator experiment.
  New: `scripts/biome_sapwood_bg_probe.jl` PARTs 5/5b/5c; six columns appended to
  `test/testitems/references/M_growth_channel_decomposition.csv` (its 21 existing columns verified
  byte-identical, and the probe's own basis gate still passes). Nothing in `src/` changed.

### Added

- **Rung 3 is now scored under climate change** — the paired per-stem growth harness re-run on the ssp370
  2090–2099 window (ADR 0128). New fixtures `test/testitems/references/M_growth_channel_decomposition_ssp370.csv`
  and `M_growth_channel_climate_response.csv`, new summariser `scripts/growth_channel_climate_response.py`.
  **The fast core's carbon uptake barely responds to warming at the temperate prototype** (it reproduces
  **8 %** of a decline the reference determines to 4 %) and **moves the wrong way in the semi-arid cell**
  (−0.34 of a rise of +77.6 ± 11.6 gC/m²/yr, with the level ratio falling out of band 1.119 → 0.657). The
  tropical cell passes at 1.08; two cells are unresolved because the reference's own response is not
  determined at two seeds.
- **The oracle's own two-seed noise floor on annual tree assimilate**, in both scenarios and on the
  between-window change (`scripts/diagnose_c_assimilate_noise.py`). None existed, so no rung-3 assimilate
  claim had anything to be significant against. Level floor 1.0–12.6 %; the response signal-to-noise is
  24.2 / 8.2 / 6.7 at Hainich / Amazon / Sahel but only 1.8 and 2.8 at the boreal and mediterranean cells,
  which is the quantitative case for the two extra reference seeds.

### Changed

- `scripts/build_biome_stem_growth_reference.py` and `scripts/extract_cell_individuals.py` take a
  `SCENARIO` (or explicit `IND_PARQUET`) knob, and `scripts/biome_sapwood_bg_probe.jl` takes
  `SCENARIO`/`Y0`/`Y1`/`FORCING_DIR`. **All defaults are unchanged**: the historic arm reproduces its
  committed table byte-identically and still passes the 20-number basis gate against ADR 0125's published
  panel. A scenario run writes its own suffixed fixture rather than overwriting the historic one.

### Added

- **The exact three-channel decomposition of the fast core's surplus above-ground growth against the
  LPJmL-FIT oracle** (`scripts/biome_sapwood_bg_probe.jl`, fixture
  `test/testitems/references/M_growth_channel_decomposition.csv`, ADR 0127). Per biome cell and arm, the
  carbon identity `Δagb = assimilate − loss − Δbelow` is differenced against the C so the surplus splits
  exactly into an assimilate channel, a litter/reproduction channel and a below-ground-sink channel, in
  absolute gC/m²/yr. The probe is a second, independent reader of the rung-3 fixtures and is **gated on
  reproducing all 20 of ADR 0125's published `bmi`/`keep` numbers** before any new number is read.

### Changed

- **The `keep` (retained-fraction) statistic is retired as a headline** for the fast core's growth error
  (ADR 0127). At four of the five biome cells it was a ratio-form of the assimilate error already
  attributed elsewhere: at the Hainich prototype **77 %** of the surplus is the assimilate, **3 %**
  allocation, **20 %** the missing below-ground wood sink, and the emulator's absolute litter +
  reproduction flux is right to **1.8 %** while its `keep` ratio is 49 % high.
- `docs/notes/sapwood_bg_design.md` gains §9: the deferred prognostic-growth step needs **two** below-ground
  pools, not one (a single-field port either leaks ~22 gC/m²/yr or over-respires), and the sink it would
  close is now priced at 46 / 20 / 4 % of the surplus at the boreal / temperate / mediterranean cells.

### Fixed

- **ADR 0125's published `keep_F` for `semiarid_sahel` (0.350) is withdrawn as undefined.** It is a mean of
  per-year ratios whose denominator changes sign between years; the ratio-of-means is −0.059. Both
  definitions are now printed side by side and carried in the fixture.

### Added

- **`scripts/eval_slow_beta_arm.jl` — three marginal arms from ONE set of forests, with the invariant enforced
  rather than asserted.** It re-runs the copula evaluator's own loop on the same table (same
  `mod(hash(cell), kfolds)` folds, same `fit_forest(...; seed = a)`, same per-row uniform) and reads the
  copula's empirical quantile, a bounded-Beta draw and the conditional **expectation** off the same leaf pool,
  so the arms differ in the marginal family and nothing else. A **fatal** gate checks the pooled reading
  against `DRF.predict_quantile` on sampled rows of every fold and axis; a **reported** gate checks this run's
  copula column against the table's stored one. Output is a shadow dir the existing
  `scripts/score_slow_copula_ks.py` scores with no new scorer and no second KS definition.

- **First measurement of the "determinism dividend"** (predict the ensemble expectation rather than draw a
  realisation — ADR 0093 §5 item 5, an EXECUTION_PLAN rung-1 deliverable that had never been run). It is free
  as a by-product of the Beta's moments. ⚠ Its published +2.9 to +14.4 percentage-point figure is on a
  **mean-based band metric**; the arm here is scored on a **distributional** per-cell KS, where a point mass
  has no dispersion, so the two framings are reported separately and the band-metric half remains open.
  Measured: the expectation arm's median per-cell KS is 3.0–3.9× the copula's (0.496–0.531) and its pooled KS
  48–158× (0.19–0.32). That is the *expected* consequence of a point mass against a distributional target, and
  what it settles is narrow but was genuinely open — the dividend cannot be read as a free win for the
  trait-distribution target; taking it would be a deliberate trade of distributional fidelity for band
  accuracy, and both sides must then be quoted.

- **The recruit-channel response arm now spans FIVE biome cells, and the sign instability is systematic
  rather than a three-cell accident ([ADR 0172](docs/decisions/0172-the-recruit-response-sign-is-unstable-within-one-eligibility-regime.md)).**
  Two further 40-seed ensembles (`semiarid_sahel`, `mediterranean_iberia`; jobs 1762007–1762088, 80/80 usable
  with zero hard kills, count overrides or k-cap merges) extend ADR 0171's cross-cell table. The **LEVEL**
  effect survives everywhere — the ported establishment rule raises the standing community's mean wood
  density at all five cells, +19 349 to +30 251 gC/m³ at t = 6.1–7.9, i.e. 8–12× FIT's entire warming shift
  as a static offset — so `recruit_establishment` stays **OFF** and the reason is now five cells. The
  **RESPONSE** contribution does not: −0.89 / +1.98 / −1.91 / −1.67 / +3.56 ×FIT, and the three cells that
  share the *same* eligibility regime (`n_elig = 4`, the modal 49 % of tree-bearing cells) **disagree beyond
  seed noise** — Cochran's Q = 8.03, df 2, **p = 0.018**, I² = 75 %, with two of three pairs separating on a
  Welch t (p = 0.026 and 0.010). Meanwhile the *shipped* channel's own response shows **no** heterogeneity across those same
  three cells (Q = 0.51, p = 0.77, I² = 0 %). ⇒ ADR 0171 §5's pre-registered "one cell per eligibility
  regime, sign must agree" condition is retired: it groups on a variable that does not organise the effect.
  Its replacement requires ≥ 12 named cells, a weighted mean in [0.9, 1.1] ×FIT **and** a non-significant Q,
  so that disagreeing cells cannot pool to the right answer by cancellation.
  Per-seed rows: `test/testitems/references/S_recruit_multicell_seed_ensembles.csv` (7 ensembles, 280 rows).

- **`scripts/split_estab_eligibility_percell.py` and `scripts/append_response_ensemble_reference.py` — the
  two hand steps in the cross-cell recipe are scripts now.** The first splits a multi-cell
  `build_estab_eligibility.py` CSV into the per-site fixtures the response probe reads, preserving the header
  and the load-bearing row order; it is gated by reproducing both of ADR 0171's hand-split fixtures
  **byte-identically**. The second prefixes the run identity onto the seed rows and appends them to the
  committed cross-cell reference, refusing a duplicate tag and cross-checking the logs' own `n_init`/`age0`
  and artifact against that site's `M_cells.csv` row.

- **`scripts/build_estab_regime_table.py` — the reproducer ADR 0171 §4's regime table never had, which
  found that the table means something different from what it says
  ([ADR 0172](docs/decisions/0172-the-recruit-response-sign-is-unstable-within-one-eligibility-regime.md)).**
  The published header reads "(2010, `Type <= 6`)", but the classification is the **minimum over the 20
  historic years**, so its `n_elig = 0` class means *"the gate is closed in at least one of 20 years"*, not
  *"this cell is in the pure-inheritance regime"*. On the ADR's own cell universe (52 451, reproduced
  exactly): min-over-window puts 5 882 cells / 11.21 % / 29 median stems in class 0 — the published row, now
  gated — while the single-year snapshot puts 1 931 / 3.7 % there and only **739 cells / 1.4 %** of the
  runnable set are closed in all 20 years, at a median of 1 stem per patch. The committed fixture
  `test/testitems/references/S_estab_regime_table.csv` carries both classifications and both cell bases side
  by side, plus a persistence section.

- **Arm D — the bounded-Beta-vs-copula comparison, re-established like-for-like
  ([ADR 0173](docs/decisions/0173-arm-d-the-beta-advantage-was-three-confounds-not-a-family.md)).**
  `scripts/score_beta_vs_copula_likeforlike.py` prices each confound folded into ADR 0093 §5.3's "2–3×"
  (estimator, grouping, information) on one row universe with the repo's one `ks2`, gated on reproducing the
  published Beta number on its own basis; `scripts/eval_slow_beta_arm.jl` then answers the deployable
  question by deriving the copula's empirical quantile and a bounded Beta from the **same** fitted forest,
  the same leaf pool and the same uniform, so the two arms differ in the marginal family and nothing else —
  checked, not asserted, by a fatal gate against `DRF.predict_quantile`.

### Changed

- **Rung 1 of the error-attribution ladder is CLOSED, with the two-part score and the compensating-errors
  verdict its exit gate asks for
  ([ADR 0174](docs/decisions/0174-rung-1-exit-the-compensating-errors-verdict.md)).** The gate reads *"rung-1
  score reported against the rung-0 noise floor, with the compensating-errors verdict stated"* and the second
  clause had no answer anywhere in the repo; ten ADRs each held a piece. No new computation. **LEVEL: passes
  by a margin** — the free-running count level's bias never exceeds +0.16 stems/patch on a mean of 8.28
  (< 2 %) against the C's own two-run floor of 6.77 % over all cells and 16.63 % in the `<2 stems/patch`
  stratum, and the deattenuated trait slopes are SLA 1.28 / Wooddens 0.66 / D95max 0.73 / minwscal 1.06.
  **RESPONSE: fails, on sign not magnitude** — the area-weighted count response ratio is +0.707 one-step and
  **−0.226 free-running**, with a measured validity horizon of ~3 years. The two verdicts concern different
  mechanisms and must not be averaged, so every rung-1 number now carries two labels: *level or response* and
  *one-step or free-running*. **The compensating-errors verdict is YES, with three named and sized channels:**
  teacher forcing (a null copying LPJmL-FIT's own previous-year count matches or beats the production model on
  every response statistic); a rectified loss-side error (86.7 % of a large decline followed vs 96.2 % of a
  large increase, which against a net-loss global response rectifies into +0.155 stems/patch — the same size
  as FIT's entire global count response, so the component passes its level gate *because of* the error that
  fails its response gate); and a survivor-trained recruit marginal that already contains the selection an
  added mortality operator would supply. Four things are now forbidden by name (a count-level anchor, a
  variance-preserving count predictor, arm D, and the offline pure-inheritance arm), each with the measurement
  that must be refuted first.

- **Rung-1 arm D is DESCOPED — its motivating "bounded Beta beats the copula 2–3×" was three confounds, not a
  distribution family ([ADR 0173](docs/decisions/0173-arm-d-the-beta-advantage-was-three-confounds-not-a-family.md)).**
  ADR 0118 asked for the comparison to be re-established like-for-like before arm D ran; it now is, and the
  claim does not survive. `scripts/score_beta_vs_copula_likeforlike.py` reproduces ADR 0093 §5.3's number on
  its own basis under a hard gate, then prices each confound: the two sides were **not the same statistic**
  (a one-sample KS against a Beta fitted to that sample's own moments, per cell-and-PFT on the densest 400
  cells per PFT, versus a two-sample out-of-sample KS per cell with the PFTs mixed). The estimator alone costs
  1.7–2.4×, the grouping a further 1.2–1.5×, and the published Beta number sits **at its own statistic's noise
  floor** (0.0437–0.0476 against a simulated 0.0434–0.0475 at n = 150). Like for like, the Beta given each
  test cell's **own observed** moments ties the **out-of-sample** copula on two axes and is **7–12 % worse**
  on the other two. Both sit only 1.1–1.5× above the split-half floor of their grouping, so neither family is
  the binding constraint on that score. And the **deployable** arm settles it from the other direction: a Beta
  carrying the *same learned two moments*, off the same forests, leaf pool and uniform as the copula, is worse
  on **all four axes** — median per-cell KS +36 % / +9 % / +13 % / +28 %, pooled KS **6.5–16.6× worse**, every
  axis failing the `≤ 0.02` criterion the copula passes. The run's own control reproduces the published panel
  **to the digit** (median per-cell KS 0.1725 / 0.1287 / 0.1575 / 0.1487, pooled 0.0039 / 0.0065 / 0.0020 /
  0.0040), so both arms sit on exactly the published basis.

### Fixed

- **A stored out-of-sample prediction column on a scratch copula table can be STALE with respect to today's
  evaluator, and nothing flagged it.** The stock, unmodified `scripts/eval_slow_copula.jl` no longer reproduces
  the `pred_<axis>.f64` committed in an old smoke table (all four axes differ, worst |Δ| ≈ 3.0e5 gC/m³ on wood
  density) even at that table's own fold count, while `src/drf.jl`'s default numerics are unchanged. ⚠ The
  **production** table is unaffected — the new arm's re-derived copula column is **bit-identical** to
  `slow_copula_pooled_w20_t8`'s stored one over 402 163 checked rows, which is what anchors the arm-D
  comparison to the published artifact. But building arm D the obvious way — stored column as one arm, fresh
  column as the other — would have put a code change *inside* the family comparison on any table where the
  divergence exists, with no check able to catch it.

- **`scripts/build_hainich_response_forcing.py` and the eligibility builder now cover all five provisioned
  biome cells.** `SITE=semiarid_sahel` and `SITE=mediterranean_iberia` produce their committed transient
  boundary and per-cell(-year) eligible-PFT series; both cells pass the historic and ssp370 boundary gates
  against the trained global table at **worst |diff| = 0** and the daily-forcing fixture gate at ≤ 1.8e-05.

### Added

- **Per-PFT parameters for the fast core, so each tree cohort runs its own physiology instead of beech's
  ([ADR 0126](docs/decisions/0126-per-cohort-pft-parameters-for-the-fast-core.md)).** `FDiffFastCore` gave
  **every tree in every cell** the temperate-beech parameter set. The measured cost (ADR 0125): the
  maintenance-respiration coefficient `respcoeff` is **0.2** for the tropical broadleaved evergreen tree
  (PFT id 0) and **1.2** for all six temperate/boreal trees, so at the two hot biome cells — 100 % id 0 by
  sapwood — F over-respired every stem sixfold and its annual carbon balance went **negative** where the
  C model's was +1073 gC/m²/yr. Four more parameters differ materially: the Beer–Lambert extinction
  `lightextcoeff` (0.45 needleleaved / 0.59 broadleaved), the photosynthesis optimum `temp_photos` (15/25 °C
  for the three boreal trees vs 20/30 for the other four), the minimum canopy conductance `gmin`
  (0.3–1.6), and leaf/root residence (1, 2 or 4 years; sapwood 25 or 30).
  New in `FDiff`: `pft_respparams` / `pft_tempstressparams` / `pft_allocparams` / `pft_allometry` /
  `pft_canopy_traits`, and the per-individual bundle `PFTPhys` / `pft_phys(ids)`. The consuming path takes
  them as an optional per-individual vector (`daily_step_canopy(...; pftphys=)`,
  `individuals_from_pools(...; pftphys=)`, `individual_from_pools(...; k_beer=, tstress=)`,
  `_treepools_fpc(...; k_beer=)`, `_patch_fpars(...; kbeers=)`) and `FDiffFastCore(...; per_pft_params=true)`
  builds it from real per-cohort `pft_ids`.
  **Opt-in and default byte-identical** (guardrail 4): `nothing`/`false` keeps the single shared set, and
  `pft_*(3)` returns F's shipped beech configuration *exactly* (`pft_allocparams(8) ==
  grass_allocparams()` likewise), so a beech-only stand is bit-for-bit unchanged with the channel on — the
  property `test/testitems/per_pft_params_tests.jl` asserts on a full simulated year. The numbers live in
  exactly one place: `test/testitems/references/M_pft_fdiff_params.csv`, generated from the live
  `par/pft_lpjmlfit.js` by `scripts/build_pft_fdiff_params_reference.py` with `cpp -P` (the preprocessor
  LPJmL itself pipes its parameter files through), and gated value-by-value against the Julia literals.
  ⚠ **F-side only:** `run_coupled_cell` REFUSES `per_pft_params=true` together with a slow emulator,
  because S's demography rebuilds the roster with the single shared allometry — that would run two
  `k_beer` bases in one simulation. Wiring the per-cohort sets through `src/components/slow.jl` is an
  integration point raised to line S.
  **The pre-registered pass criterion FAILED and the default was NOT flipped.** Measured at the five biome
  cells (historic 2010–2019, `slow = nothing`, per-stem paired against the C's own individuals): the two hot
  cells are fixed — the Amazon's annual carbon balance goes from **−223 to +1199 gC/m²/yr** against a truth
  of **+1073**, and the Sahel's from −0.457× to **1.132×** — while boreal_siberia moves **1.049 → 1.275**
  and mediterranean_iberia **2.727 → 3.056**, i.e. away from the truth. These are the model's own
  parameters, so the failure is not an argument to revert: it says the criterion required one change to
  also close two defects that were already attributed elsewhere (a 1.5–1.9× allocation/turnover gap and the
  Mediterranean cell's independent 1.3–1.5× photosynthesis bias). Eight single-variable arms attribute it:
  the respiration coefficient is the whole tropical fix on its own (Amazon −0.21 → 1.13), the boreal cell is
  moved by the photosynthesis temperature optimum and the minimum canopy conductance, and the
  Mediterranean cell by the phenology alone.

### Fixed

- **Every tree in the five-cell fast-core probe was running beech's leaf phenology, including the larch and
  the tropical evergreen ([ADR 0126](docs/decisions/0126-per-cohort-pft-parameters-for-the-fast-core.md)
  §5).** `FDiffFastCore` has taken per-cohort `pft_ids` — which select each PFT's own growing-season index
  filters — since long before this change, and the probe simply never passed them. Passing them, with
  nothing else changed, moves the Sahel cell's annual assimilate ratio by **+1.01** (−0.457 → 0.557) and the
  Mediterranean cell's by **+0.38**. Any five-cell fast-core number in this repo that predates ADR 0126
  should be read as being on beech phenology. It also narrows ADR 0125's Sahel reading: about a third of the
  shortfall there was this, not the dry-cell root zone.

### Added

- **Rung 3 (line M): F's canopy growth measured PAIRED PER STEM against LPJmL-FIT's own individuals, five
  biome cells, 2010–2019** (ADR 0125). Enabled by establishing that `(Cell, Patch, ID)` is a *stable
  cross-year individual identity* in the annual `ind` output (13 152 stem-years: `Age` +1 on all 10 323
  pairs, immutable traits bit-identical, only 8 vanishings and all within 0.4 m of the writer's 5 m cut).
  New: `scripts/build_biome_stem_growth_reference.py` (+ the committed per-cell/per-year accounting
  `test/testitems/references/M_stem_growth_reference.csv`), `scripts/biome_canopy_growth_probe.jl`,
  `scripts/diagnose_oracle_run_divergence.py`.
- `test/testitems/references/M_individuals_<cell>_2010.csv` gain `id` and `age` columns, appended last;
  every pre-existing value verified byte-identical row-by-row.

### Fixed

- `scripts/extract_cell_individuals.py` no longer eats the shared per-cell registry. It rewrote
  `M_cells.csv` from its own ten-column header and dropped every row whose field count differed, so a
  re-run would have silently deleted the six columns `extract_cell_slow_init.py` appends (the pinned
  Component-S per-cell seed: `n_init`, `age0`, the four-column boundary). The merge now preserves columns
  and comment lines it does not own; a re-run over the live registry is byte-identical.

### Added

- **The response-arm harness now runs at any of the five provisioned biome cells, not only Hainich**
  (`SITE=<name from M_cells.csv>` on `scripts/trait_mortality_arm_probe.jl` and
  `scripts/build_hainich_response_forcing.py`). A non-default site takes its trees, soil column, forcing,
  latitude, per-cell stem/age seeds and static boundary from the committed per-cell fixtures — never from the
  Hainich-trained artifact meta. `SITE` unset is byte-identical to every earlier run, verified two ways: a
  matched-seed pre/post-refactor pair differing only in the scope label, and a 40-seed ensemble reproducing
  ADR 0170's published arm to every digit (ADR 0171 §1).
- **New committed fixtures:** the two-scenario transient boundary and the per-cell(-year) eligible-PFT set for
  `tropical_amazon` and `boreal_siberia`, plus `S_recruit_multicell_seed_ensembles.csv` — the 200-row per-seed
  record behind ADR 0171's cross-cell table.
- **`BND_FIXTURE`** on the probe: run the arm against another transient-boundary file, so a conditioning-basis
  comparison never needs the committed fixture hand-edited.

### Changed

- `test/testitems/references/S_hainich_response_boundary.csv` regenerated on the corrected basis (the
  historic half is unchanged; the ssp370 half changes only for 2020–2038 and is exact from 2039). The
  pre-fix basis stays reproducible bit-for-bit via `SSP_LEAD=2020 ALLOW_UNTRAINED_SSP_BASIS=1`, and is
  retained as ADR 0171's own control arm.
- The response-boundary testitem gains a CI-safe tell for a truncated averaging window (the largest
  year-on-year jump against the series' own median jump — 13.1 before the fix, 4.0 after; the gate allows 8),
  because the trained reference table lives on scratch and CI cannot read it.

### Fixed

- **A train/inference inconsistency in the response arm's SSP370 conditioning basis (ADR 0171 §2).** The
  builder gave only the historic scenario a 20-year monthly lead-in, so the ssp370 side's first years were
  averaged over 1, 2, 3 … years instead of 20 — making **19 of 81 conditioning years a different quantity from
  the one the learned models were trained on**, by up to **+210 growing-degree-days (+10.7 %)** and
  **+1.94 °C**. A code comment asserted the omission was deliberate and consistent with the training basis;
  measured against that basis, it was not. Both scenarios now take the lead-in, and a new hard gate compares
  the result to the trained table for the run's own cell (it now reproduces it exactly, at all three cells).
  **No published number moves:** every number measured on this arm used an artifact whose two boundary axes are
  constant in training, so its boundary channel is provably inert (the probe's own liveness check reads exactly
  0.0), and the 40-seed reproduction confirms it. Where the channel *is* live, the fix moves the arm by
  **0.03 ×** the reference warming shift against a sampling error of **0.32 ×** — real, correct, and an order
  of magnitude below the ensemble's own precision.

### Measured

*ADR 0171 — the recruit arm at three cells:*

- **The ported establishment rule raises the standing community's mean wood density at all three cells
  measured** — +2.20 % (temperate), +4.93 % (tropical), +5.00 % (boreal), each at t ≥ 5.1, i.e. 2.1–4.4× the
  entire observed warming shift as a static offset. This is the robust finding and it is why the rule **stays
  switched off** by default; the one-cell +8.5 % of ADR 0170 is the same conclusion on a different artifact.
- **Its contribution to the warming response is not even sign-stable**: −0.89 ± 0.32, +1.98 ± 0.93 and
  −1.91 ± 0.53 × the reference shift at the three cells, and it *also* reverses (+3.41 → −0.89) when the
  learned artifact is swapped at a fixed cell. ⇒ ADR 0170 §2's "the port removes a wrong-signed response" is a
  statement about one cell on one artifact and must not be generalised; a **third** condition is added to the
  pre-registered flip criterion (at least one cell per eligibility regime, artifact held fixed and named, sign
  must agree).
- **The baseline being scored against is itself strongly cell-dependent** (+0.27, +0.30, **+1.94** × the
  reference shift) — at the boreal cell the *shipped* configuration already overshoots the observed warming
  shift by 94 %, and the ported rule removes that response rather than adding one.
- **The bioclimatic recruit gate moves in opposite directions with warming**, and the earlier reading
  generalised the wrong way: at the temperate cell it CLOSES (the three boreal tree types are expelled once
  the 20-year cold-month mean passes 0 °C, so more recruits come from the cell's own seed bank), at the boreal
  cell it OPENS (temperate types are admitted, so fewer do). The tropical cell's is static.
- **The low-diversity regime is not where it was thought to be**: the Amazon and Sahel admit four tree types
  (not one). Only **124 of 52 451** tree-bearing cells admit exactly one; the modal cell admits four (49 %),
  and the genuinely inheritance-dominated regime is the **11.2 %** that admit none — untested, and the class
  with the worst noise floor (median 29 stems).

### Added

- **Arm C of the rung-2 demography experiment** — the substituted per-individual mortality interface line S
  specified (ADR 0117 option (c)), run end-to-end against the LPJmL-FIT C oracle at cell 42490
  (25 patches, 2000–2019, 16 runs, 5 seeds per arm). `scripts/rung2_armc_harness.jl` is the Julia rendezvous
  server (it calls the *shipped* `TraitMortality.mortality_hazard` and `LPJmLFITEmulator._hazard_tilt`, never a
  copy of either), `scripts/run_rung2_armc.sh` submits one arm, `scripts/diagnose_rung2_armc.py` scores them.
  ADR 0124.

### Changed

- The rung-2 mortality interface is **adopted** in line S's option-(c) form: it is exact end-to-end live
  (ρ from the port vs the C's own `mort_prob` agree to 4.4e-16 over 5 000 patch-years; θ = 1 to 4.5e-14 over
  2 500; the C's audit shows `n_kill_applied/n_kill_c` 0.980–1.014 with **zero** trees spared that the C was
  certain of), and it reaches 1.050× on terminal stems, 0.952× on the wood-density selection differential and
  the per-PFT age–wooddens gradient ordering in 5 of 5 PFTs. **Those are ceiling numbers, not an emulator
  score** — with the count target taken from the operator's own hazard θ is 1 identically, so that arm *is*
  FIT's mortality with an independent draw.
- **The no-selection null (uniform ρ-thinning, the shipped default) fails on every statistic**: 1.209× stems,
  0.241× of the selection differential, one PFT's gradient backwards — and, the largest departure, it converts
  a mature stand into a young one (terminal `<20`/`20–40`/`≥40` yr stems 336–404/25–47/26–47 against the C's
  118/120/127) while keeping only 10–16 % of the C's own ≥40 yr individuals. **`C1 − C0` = 71.1 % of FIT's
  wood-density differential is differential survival**, so a count-only interface cannot reach it.

### Fixed

- Nothing in shipped code. Two measurement rules were corrected instead: FIT's **global** age–wooddens
  gradient fixture cannot serve as a **per-cell** acceptance target (the C's own recording at this cell scores
  Spearman ρ from −0.500 to +0.800 against it, so a naive reading would fail FIT itself), and an identity gate
  is only as wide as the state distribution it ran on (ADR 0122's gate had seen only the recorded trajectory;
  re-run on the null arm's — 7× the ghost-tree rate — it still holds exactly, and that re-run is now part of
  the procedure).

### Added

- **Per-cell(-year) bioclimatic eligible-PFT table for the ported establishment rule**
  (`scripts/build_estab_eligibility.py`, ADR 0170): all 67 420 cells × 20 historic years, from FIT's own
  gate inputs (`temp_min20`/`temp_max20` = 20-yr running means of each year's coldest/warmest monthly
  mean, the current year's daily GDD5 and precipitation total), gated against FIT's own `ind` output at a
  0.076 % residual. Committed single-cell fixture `test/testitems/references/S_hainich_estab_eligibility.csv`.
- **`ARM=recruit` dimension on `scripts/trait_mortality_arm_probe.jl`** — the response 2×2 with the
  contrast axis switched from `trait_mortality` to the recruit channel (R0 = pinned copula, R1 = the
  ADR-0119 ported rule), plus a mechanism panel that reads the DRAWN recruit marginal per scenario, and a
  per-year eligibility policy fed from the fixture above.
- `EstabDiag` now records the four drawn trait values, so the recruit marginal can be tracked directly
  instead of being inferred from the standing community (gated by the establishment testitem).

### Changed

- `scripts/summarize_response_seed_ensemble.py` is arm-aware: it labels the arm, applies the recruit
  arm's own preconditions (the rule must have drawn, and the seedbank must have filled), and refuses to
  average two different arms into one ensemble.

### Fixed

- Documented that `n_elig == 0` does **not** mean "nothing establishes here": FIT's inheritance channel
  (`establishmentpft_ind.c:125`) is not bioclimatically gated, so a cell whose gate has closed keeps
  recruiting its resident genotypes. The ported sampler already behaved correctly; the description of the
  gate did not.

### Changed

- **Line M — the rung-2 demography rendezvous moved behind the growth loop, and the one-year lag is gone
  exactly (ADR 0123).** The C used to ask the external demography for its answer at the *top* of the
  annual block, while its own hazard runs after turnover and allocation, so the roster it published
  carried last year's growth state. Measured, that inverted the sign of the wood-density selection
  signal (ratio −0.825 against the C). The hazard and its random draw now run unchanged but no tree is
  removed inside the loop: each verdict is recorded, the rendezvous opens afterwards on a new `grow`
  dump phase holding the complete current-year roster, and a kill pass applies the verdicts.
  On the new basis the interface reproduces the C's own per-tree ordering exactly — Spearman ρ = 1.000
  at p05, median *and* minimum over all 500 patch-years — and the selection differential ratio is
  +1.000. The 942-of-9 951 record skip disappears with it, so the youngest cohort is no longer
  invisible. `patches/lpjmlfit_rung2_hook_v5.patch` supersedes v4.

### Fixed

- **Line M — the roster key table no longer silently caps at 1024 entries** (it stopped recording
  duplicates past the cap, which would have made a kill instruction ambiguous in a dense cell).

### Notes

- The deferral is shared by *both* rung-2 hooks, so the recorded baseline and every replayed arm sit on
  the same code path and the null control is exact by construction (identical in every initialised
  column over 40 161 tree records; no divergence in all 2 000 patch-years of cell state). With both
  environment variables unset the stock model is untouched — 139 decoded quantities identical, 0 differ.
  The deferred path does move the C's *own* trajectory relative to stock by 0.05 % of stem-years over
  20 years at one cell (identical terminal stem count); that is disclosed with every rung-2 number.
- Any roster dump recorded before this change is unusable as a replay basis; the harness now fails
  loudly on one instead of replaying a stale roster.

### Added

- **Line M — the rung-2 mortality port is verified against the C binary EXACTLY, and it is now a CI gate**
  (ADR 0122). `scripts/diagnose_rung2_hazard_identity.jl` scores line S's ported per-individual mortality
  hazard (`src/trait_mortality.jl`, which has no call site and had never been checked against the C on real
  per-tree state) against the LPJmL-FIT C binary's own `mortality_tree_ind` on all 9 951 tree-patch-years of
  the recorded rung-2 dump (cell 42490, 25 patches, 2000–2019, PFT ids 1–6). All four hazards, the capped
  total and both hard kills agree to double round-off (max relative Δ **1.6e-15**, 0 exceedances; 175
  growth-failure kills and 195 ghost-tree kills classified correctly). This is the free identity gate line S
  offered in ADR 0117 item 4, and it makes ADR 0049's "θ = 1 recovers FIT exactly" a measurement rather than
  an assertion. `test/testitems/m_rung2_hazard_identity_tests.jl` re-scores the port on every CI run against a
  333-record PFT-stratified C-truth fixture (`test/testitems/references/M_rung2_hazard_identity.csv`).
- **Line M — two dump columns that make the fourth hazard observable**
  (`patches/lpjmlfit_rung2_hook_v4.patch`, supersedes v3). `bm_delta` and `leafarea_real` are published as
  write-only `Pfttree` fields, because `mort_npp` — the hazard through which the whole wood-density trait
  channel enters — needs post-allocation quantities that are not reconstructable from the previous schema.
  Both are initialised on both tree-creation paths, unlike their `mort_*` siblings, since the external
  demography reads them. The restart-file format is unchanged. Two rebuilds, each gated on decoded variables:
  110 quantities identical, 0 differ, with the `ind` and `globalflux` text outputs byte-for-byte.

### Changed

- **Line M — arm C is pre-registered as NOT scorable on the trait question from the current rendezvous**
  (ADR 0122). The external demography is asked for its answer at the top of the annual block, so it sees last
  year's growth outcome. Per-tree ordering survives that (Spearman ρ median 0.900 against the C's own hazard),
  but the one-year wood-density selection differential flips sign: the C's +17 729 gC/m³ against the lagged
  basis's −14 528 (ratio −0.819). Attributed one term at a time, it is the consecutive-growth-failure counter,
  not the growth-efficiency lag (which comes out at ratio +1.001) and not the hard kills. The fix is a change
  to where the rendezvous happens, not to the ported operator; the lag does not exist in the standalone
  emulator, where the fast core computes the year's growth before the demography runs.

### Fixed

- **Line M — the rung-2 dump-equality gate no longer reports a false failure on an exact arm** (ADR 0122).
  Uninitialised first-year values of the two new columns made it call an arm whose roster was identical in
  every year, and whose cell state agreed in all 1 500 patch-years, "DIFFERENT model state". The ADR-0121
  replay floor survives the schema change unchanged: null control 1.000, kills arm 1.000 exact, no year differs.

### Added

- **The ported LPJmL-FIT establishment rule — recruit traits computed from the C's parameter files instead
  of learned from its output ([ADR 0119](docs/decisions/0119-port-fits-establishment-rule-instead-of-learning-a-recruit-marginal.md)).**
  Implements an explicit owner steer: which trees are *born* in FIT is a parameter-file fact (uniform draws
  on each PFT's own trait intervals, mixed with inheritance from the cell's rolling top-AGB seedbank at the
  closed-form weight `4/(4 + n_elig)` — ≈44 % inherited in a five-PFT cell, ≈80 % in a single-PFT one), so
  only *who survives* has to be learned. This removes by construction the double count
  [ADR 0118](docs/decisions/0118-the-recruit-copula-already-carries-the-selection-arm-c-would-add.md)
  measured at **+12.18 % on `Wooddens`**, where the survivor-trained recruit copula already carries the
  selection the `trait_mortality` operator adds. New `Establishment` submodule (pure Base, zero new deps)
  ports the eligibility gate (`establish.c:29-33`), both channels' rates
  (`establishmentpft_ind.c:97-140`), the uniform draw (`numeric.h:59`), the inheritance diffusion
  (`new_tree.c:38-61`) and the 50-year rolling top-AGB seedbank (`getsapling.c`); the opt-in
  `FluxDrivenSlowEmulator(...; recruit_establishment = RecruitEstablishment(...))` hook feeds it the
  emulator's OWN roster each year and records a per-year `EstabDiag` (channel, eligible count, seedbank
  state) — reading which is a stated precondition for interpreting any arm. **Default `nothing` ⇒ every
  committed baseline, the AD gate and every pinned artifact byte-identical**, and the flip criterion is
  pre-registered in the same ADR (§6) with the kill condition that matters: the recruit channel must not
  reproduce the count recursion's climate-dependent error
  ([ADR 0112-0116](docs/decisions/0116-the-count-recursions-drift-is-a-one-sided-failure-to-follow-stem-losses.md)).
  Three departures from the C are stated rather than hidden — the port is distributional (FIT's RAND48
  stream and `gasdev` cache are not reproducible), one cohort per year replaces FIT's Poisson counts, and
  the drawn PFT identity reaches the roster only behind a second flag because the canopy template still
  carries the donor cohort's physiology. Also **corrects ADR 0045's wording**: the interval-violation rule
  is not a reflection but an inward uniform redraw between the parent and the crossed bound, with a point
  mass on the bound — which is exactly where the boreal `minwscal`/`d95max` intervals live. Parameters live
  in ONE generated artifact (`test/testitems/references/S_pft_estab_params.csv` via
  `scripts/build_estab_params_reference.py`, reusing the existing `cpp -P` parser rather than a second
  copy), gated row-by-row by `test/testitems/slow_establishment_tests.jl`.

### Added

- **The roster dump's patch record now carries the three channels of cell-level state no per-tree record can
  carry** (line M, ADR 0121): the per-cell RAND48 stream position, the parity of `gasdev()`'s
  process-global spare-deviate cache, and checksums of the top-AGB seedbank contents. This is what turned
  ADR 0120's open question — identical state, different demographic answer — from a claim into a
  measurement: at the divergence onset the `pre` phase agrees in every one of them and the roster, and the
  `post` phase does not. New scorer `scripts/diagnose_rung2_cellstate_equality.py`; `MODE=record` added to
  `scripts/run_rung2_replay_arm.sh`, because a rebuild that changes the dump schema invalidates the recorded
  baseline every arm is scored against.

### Changed

- `cell->treelen_old` / `treelist_old` are documented as **uninitialised memory in every real run** and are
  deliberately not dumped: their sole writer sits behind `if(config->isequal)`, which is TRUE only when
  every cell in a run shares identical coordinates (and is hardwired FALSE for a single cell), so the branch
  is dead and `mergesapling()` has no caller anywhere in the C source.

### Fixed

- **Rung-2 replay: the kill set no longer claims fire's victims, and the mortality half of the demography
  interface now replays exactly** (line M, ADR 0121, supersedes ADR 0120 §5's replay numbers). The harness
  derived its kill set as "any `post`-phase tree with `isdead == 1`", but `isdead` has more than one author:
  `fire_tree_ind` also sets it, *after* the hook's decision point. Replaying fire's victims as demographic
  kills both claimed a death the narrow interface does not own and moved the per-cell random stream — fire
  draws `erand48` only for trees that are not already dead, so pre-killing its victim changes how many draws
  it consumes. The roster dump gains a third phase, `mort`, written after the demographic hazards and before
  fire; kills are read there. Terminal stems (replay ÷ recorded, cell 42490, 25 patches, 20 years):
  `kills` **1.37 → 1.000, exact** — identical in every initialised per-tree column and every cell-state
  column, no year differs; `recruits` 0.91 → 0.907; `both` 1.30 → 1.367.

### Added

- **Sized the selection already absorbed into the recruit copula's training target — a pre-registered
  condition that had gone unchecked for two weeks ([ADR 0118](docs/decisions/0118-the-recruit-copula-already-carries-the-selection-arm-c-would-add.md)).**
  [ADR 0025](docs/decisions/0025-component-s-recruit-trait-copula.md) §3 trains the copula's trait marginals
  on LPJmL-FIT's *surviving* stems and wrote its own expiry condition — *"if trait-dependent mortality is
  ever added, this training target must change"*. Arm C is that change, and no decision record in the
  0047→0049→0117 chain cites it. `scripts/diagnose_copula_selection_confound.py` measures the
  entry→survivor displacement on 197.7 M historic + 828.8 M ssp370 surviving tree stems, both ground-truth
  members, all four live trait axes, with no refit and no new model run (jobs 1754705/1754709, ~7 min each).
  Within a cell-PFT group the displacement is **+12.18 % on wood density** — the exact axis
  [ADR 0049](docs/decisions/0049-trait-mortality-wired-in-the-count-channel-bounds-it.md)'s flip criterion is written on —
  and **0.56 of it does not cancel in a warming response**; the other three axes are ≤ 0.9 %. Because
  uniform thinning (the arm's null) is exactly the trait-blind design the survivor marginal was matched to,
  the bias lands on the arm and not on its null, so **`C1 − C0` may no longer be reported as "how much of
  the trait response is selection"**; the flip criterion gains two pre-registered conditions (read the tilt
  θ first, and test the per-PFT gradient *shape*, which a uniform double count cannot fake). The
  composition control is what makes the panel readable: pooled, rooting depth (−49.6 %) and the drought
  threshold (−35.9 %) look catastrophic and collapse to −2.4 % / +0.4 % within cell, so ~95 % of that is
  *where young stems live* rather than selection. Every figure is a **lower bound** — the tree table drops
  stems below 5 m, so selection before that height is invisible. Seed agreement ≲ 2 % throughout. Also
  scopes arm D: it inherits the double count, and its motivating 2–3× goodness-of-fit win has **no
  committed reproducer** in this repo and appears to compare oracle-fitted moments against out-of-sample
  predictions, making it an upper bound rather than a realizable gain. Changes no code, artifact or default.

### Added

- **Line S (rung 2):** `scripts/diagnose_recruit_trait_axis_coupling.py` — decides whether the recruit-trait
  axes the rung-2 hook leaves on LPJmL-FIT's own draw cost the interface anything. It audits each axis's
  variability per PFT **first** (a constant column and an uncoupled trait produce the same degenerate
  correlation but have opposite implications), then measures within-(PFT, age-bin) coupling among survivors
  and the one-year selection differential.

### Fixed

- **Line S:** the recruit-axis diagnostic no longer reports a selection differential for a constant column —
  its first run printed −284 standard deviations for an axis with exactly one distinct value, which is
  arithmetically impossible and was a near-zero-variance denominator. It now prints `const`.

### Documentation

- **ADR 0117** — line S's reply to the rung-2 demography interface line M raised (and recorded unanswered in
  its own ADR 0120): **S returns a per-individual survival probability and M draws**. A count-only interface
  cannot carry the trait response even in principle, because that response is within-PFT, within-age-class
  differential survival; ranking on the C's own hazard would make any trait result the C's selection rather
  than the emulator's. The existing opt-in trait-dependent mortality operator already emits exactly this
  shape, so the null arm and the selection arm share one wire format and no new model is needed — which also
  unblocks line S's own arm C, whose only blocker was the lack of a roster harness. Records the risk to
  measure first (the learned count target may leave the selection no room) and the free identity gate the
  harness makes available.

### Added

- **Line S (rung 1):** `scripts/rung1_drift_attribution.py` — the no-refit diagnostic ADR 0115 §6.3
  pre-registered. At a fixed lead it builds each cell's **excess drift** (the self-feeding count arm's
  `bias(ssp370) − bias(historic)` minus the one-step control's on the same rows) and attributes it to the
  cell's ssp370-minus-historic change in each conditioning feature three ways — weighted univariate
  correlation, standardised multiple regression with a VIF beside every coefficient, and greedy forward
  selection on weighted R² — always with the control's own decomposition printed beside the arm's. It
  reuses `rung1_response_decay.py`'s `lead_index` and area weights by import rather than re-deriving them,
  and opens with a reconciliation panel against ADR 0115 §3.
- **Line S:** the same script's response-decomposition panels, which are what the pre-registered form could
  not deliver: the drift regressed on **LPJmL-FIT's own** per-cell count response, the mean drift by decile
  of that response (with the cell's stem count and the level-normalised drift beside it, so a one-sided
  error is separable from one that merely scales with density), and the incremental R² of the 13 varying
  conditioning features over that response alone.

### Fixed

- **ADR 0115 §3's control row at lead 5 reads +0.024; it should read +0.031** — a one-row transcription slip
  from a CSV whose rows include lead 4, which the table's columns skip. Recorded in ADR 0116 §1 rather than
  edited in place (ADRs are immutable). No conclusion of ADR 0115 depends on it: its prose quotes the
  lead-18 excess (+0.074), which is unaffected, and the arm row reproduces exactly.

### Documentation

- **ADR 0116** — the count recursion's scenario-asymmetric drift runs through the **stand-state** channel,
  and it is a **one-sided failure to follow stem losses**. The previous stem count and the mean cohort age
  carry it (univariate r −0.34 / +0.33 at lead 18) while every climate and flux feature sits at |r| ≤ 0.084;
  the one-step control decomposes differently and far more weakly (R² 0.096 vs 0.250, selecting a flux
  first, with a previous-count correlation of ≈ 0), so the channel belongs to the recursion rather than to
  the rows. The finding is the asymmetry: the arm reproduces **86.7 % of a large stem decline but 96.2 % of
  a large increase**, so with LPJmL-FIT's own global response being a net loss the rectified error surfaces
  as a spurious positive drift — the wrong-signed aggregate response of ADR 0113, explained. Controlled
  against the truth-binning confound (the excess column cancels it by construction) and against stem
  density (the extreme deciles differ 1.3× in count; the asymmetry survives normalising at 3.0×). Next
  count arm is judged on the loss side, and no climate/flux conditioning change should be proposed without
  refuting the attribution table first.

### Added

- **Rung 2's substitution half — the LPJmL-FIT C binary can now accept an external demography**
  (line M, ADR 0120). A second opt-in hook (`LPJ_RUNG2_APPLY_DIR`) hands each patch's tree roster to
  an external process at the top of the annual demography block, blocks for its answer, and applies a
  kill set plus a complete recruit set; `MORT_C` / `ESTAB_C` defer either half back to the C so a
  divergence is attributable. Committed as `patches/lpjmlfit_rung2_hook_v2.patch`, which supersedes
  `patches/lpjmlfit_rung2_demography_hook.patch` (retained for the provenance of the previously gated
  binary). With both environment variables unset the binary is numerically identical to the previous
  one — 139 decoded quantities plus `globalflux`, 0 differ, re-checked after each rebuild.
- `scripts/rung2_replay_harness.py`, `scripts/run_rung2_replay_arm.sh` — replay LPJmL-FIT's own
  recorded demography back to it through the hook, in four arms (`kills`, `recruits`, `both`, `none`).
- `scripts/diagnose_rung2_replay_identity.py`, `scripts/diagnose_rung2_dump_equality.py` — score a
  replay arm against the run it replays, and compare two roster dumps column by column.

### Fixed

- Two columns of the rung-2 roster dump are **uninitialised memory** and must not be read (ADR 0120):
  `sapwood_old` is a dead struct field that LPJmL-FIT never writes or reads, and the `mort_*` columns
  are meaningless for any tree that has not yet been through `mortality_tree_ind` — which includes
  every recruit at the `post` of its own establishment year, correcting ADR 0061's wider claim that
  they are valid at `post`.

### Added

- **Line S (rung 1):** `scripts/rung1_count_ratio_arm.jl` — the ratio-target count arms R0 (teacher-forced)
  and R1 (state-recursed), identical to the A0/A1 arms except for the target `n_t / n_{t-1}` and the
  multiplicative reconstruction, with a free `max |R1 − R0| = 0` gate on the first-year rows.
- **Line S:** `scripts/rung1_response_decay.py` gains three panels — the one-step control's per-band columns
  at every horizon (closing ADR 0114 §5.4), the arm's drift at exact lead resolved by scenario, and the
  response computed at **matched lead depth** (only leads present in both scenarios, equal weight).

### Changed

- **Line S:** `scripts/rung1_response_decay.py` no longer divides `n_living` by the patch-ensemble size — the
  column is already a per-patch stem count. Every ratio it has ever produced is unaffected (the factor
  cancels); its level panels were 25× too small for their "stems/patch" label. ADR 0114 §1's mean row is on
  the old scaling and is flagged, not re-scaled.

### Documentation

- **ADR 0115** — the count recursion's drift is **scenario-asymmetric**: it survives exact lead matching, so
  it is not the unequal-chain-length artefact ADR 0114 §2 named, and at lead 18 it manufactures 90 % of
  LPJmL-FIT's own global count-response magnitude with the opposite sign. Training on the year-on-year ratio
  instead of the level is refuted in accuracy, drift, scenario asymmetry and aggregate response — the level
  target is itself the level anchor. Next experiment (no refit): name the conditioning feature that carries
  the scenario signal into the error.

### Added

- **Line S / rung 1 — the count emulator's validity horizon is measured** (ADR 0114).
  `scripts/rung1_response_decay.py` reuses the recursion arm's own predictions and the proven per-row keys — no
  retraining, ~2 minutes — to answer why self-feeding destroys the warming response. It is **not** the model
  collapsing onto an average: after 80 years of feeding on itself the prediction still carries 90 % of the
  truth's between-patch spread and correlates with it at 0.94. What breaks is a slowly-saturating level drift
  (+0.16 stems per patch) that happens to be the same size as LPJmL-FIT's entire global count response, and that
  is not the same size in the two climate scenarios. Measured horizon: **the stem-count warming response is
  faithful for about three years of self-feeding, degraded by ten, and inverted by forty** — and at a single
  step it is right in every latitude band (0.90–1.07), which is the strongest evidence so far that the count
  model does have a warming response at all.
- Consequence recorded as a decision: **do not "fix" the recursion with a variance-preserving or
  distribution-sampling count predictor** — any such proposal has to refute the spread measurement first. The
  next experiments target the drift's dependence on lead time instead.

### Added

- **Line S / rung 1 — the persistence null control for the count response** (ADR 0112).
  `scripts/build_count_persistence_null.py` writes the predictor "copy LPJmL-FIT's own stem count from last
  year, learn nothing" into a scorable arm directory (shared provenance symlinked, so it cannot drift from the
  table it is a null for), and `scripts/diagnose_truth_yardstick.py` now accepts a comma-separated `COUNT_DIR`
  so an arm and its null are scored in one process, on one cell set, on one basis.
- **Line S / rung 1 — the flux-forced, state-recursed count arm (A1)**:
  `scripts/rung1_count_recursion_arm.jl` feeds each year's own count prediction in as the next year's
  previous-year count, per (Cell, Patch) chain, changing nothing else — same folds, same forests, same seed —
  and prints error against LPJmL-FIT as a function of lead time, which the one-step basis cannot produce.
- **Line S — a proven key attachment for the frozen production count table**:
  `scripts/attach_count_table_keys.py` recovers the (Cell, Patch, Year) key of all 121 495 658 rows by
  replaying the table builder's own key pipeline and verifying it row-for-row against `y.f64`,
  `X[:, n_prev]` and `cells.i64` before writing anything (100.0000 %, both scenarios). The chain the recursion
  needs is not inferable from the frozen table, and both plausible shortcuts corrupt the sparse cells.

*arm A1, ADR 0113:*

- **The rung-1 recursion arm is measured.** Making the count feed itself (`rung1_count_recursion_arm.jl`,
  4 min on 48 cpus over 121 495 658 rows) leaves the *level* almost untouched — error against LPJmL-FIT grows
  from 0.60 to 1.72 stems per patch over 80 years and then stops growing, with a mean bias never above 2 % —
  but the *warming response* collapses and reverses sign: the area-weighted global count response ratio goes
  from +0.707 (one-step) to **−0.226**, and every latitude band gets worse. So for stem counts the level is not
  what fails the acceptance criterion; the response is.
- **The per-cell response slope is retired as a discriminator for counts.** Three arms whose out-of-sample R²
  spans 0.982 → 0.962 → 0.918 and whose global response ratio spans +0.707 → +0.685 → −0.226 all score a
  deattenuated per-cell slope between 0.976 and 1.029.
- **No level anchor for the global count recursion** — there is no runaway to anchor at this scale, which
  contradicts the natural reading of the earlier single-cell drift result and agrees with ADR 0105.

### Changed

- **Every published global Component-S fidelity number now carries a forcing basis label** (ADR 0112). All of
  them are **one-step, C-forced**: the count model is handed LPJmL-FIT's own roster and fluxes for the same
  patch-year, including its previous-year count, and the out-of-sample evaluation predicts each row from that
  row's own features. Measured consequence: a persistence null reaches R² 0.9622 against the production model's
  0.9824 and a deattenuated count response slope of 1.029 against 1.006 — so "the count response is faithful
  per cell" is retired as evidence about the emulator, and the wrong-signed regional count responses of
  ADR 0111 §5b are shown to be present in the null as well. On the aggregate area-weighted response ratio the
  two are also close (0.685 null / 0.707 model / 1.0 target), so on every response statistic the null matches
  the production model — the only place the learned model clearly wins is accuracy.
- **`EXECUTION_PLAN.md` rung 1's arm list is superseded** — its arm B is what is already measured, and the
  missing control is arm A. Replacement ladder in ADR 0112 §4b. That file is integrator-owned; this is an
  integration point, not an edit.

### Fixed

- **A second, unweighted definition of the aggregate response ratio was still live in the count path** of
  `scripts/diagnose_truth_yardstick.py` — the trap ADR 0111 closed on the trait side. It agrees with the
  area-weighted definition on the production arm (0.691 vs 0.707) and disagrees by a factor of four on the
  recursed arm (−0.93 vs −0.226). Now one definition, area-weighted, `n/d` below signal-to-noise 3.
  Consequence: ADR 0111 §4b's "area-mean 0.691×" is the unweighted number mislabelled; the area-weighted value
  is 0.707, and the conclusion it supported is unchanged.

### Added

- **`scripts/collate_changelog.py` — deterministic, idempotent fragment collation.** Splits each fragment on
  its `### <Category>` headings (**most fragments are multi-category**; one has six, which is why hand
  collation is error-prone), groups into **one new `### <Category>` group** inserted after `## [Unreleased]`
  matching the file's existing shape, and deletes the collated fragments. Verified on the first run: **1832
  insertions, 0 deletions, 245/245 bullets present** — the change to `CHANGELOG.md` is provably purely
  additive. **Errors on an unknown category** rather than silently inventing a section; the allowed list is
  the six Keep-a-Changelog ones plus the seven already in practice here (`Documentation`, `Validation`,
  `Verified`, `Measured`, `Verdict`, `Gates`, `Notes`, with `Documented` an alias). Preserves a heading's
  parenthetical qualifier as an italic lead-in. Derives the repo root from `__file__`, so running it from a
  line worktree cannot write into the integrator worktree. `--check` and `--dry-run` included.
- **A sixth CI gate, `changelog`.** Runs `--check` on **`main` only** — a fragment on a `line/**` branch is
  correct, since that is where fragments are authored; it is debt only once it reaches `main`. So a merge that
  skips collation reds `main` with the exact list and the one command that fixes it. Pure-stdlib, seconds, no
  dependencies. Deliberately **not** a bot that commits to `main` (write permissions, push-loop risk, no
  precedent) and deliberately **not** a count-or-age threshold (a knob that drifts; "zero uncollated on
  `main`" is the actual invariant).

### Changed

- **Changelog collation now attaches to the merge, not to a role
  ([ADR 0095](docs/decisions/0095-integrator-chores-need-an-event-not-a-role.md); owner question,
  2026-08-10).** ADR 0029 fixed changelog *authoring* — per-line `changelog.d/` fragments with disjoint
  filenames — and that half worked. It left collation as *"the integrator collates … at an integration
  point"*, which named no event that reliably happens: ADR 0028 has **every line merge its own branch**, so
  nothing convenes an integration point and "the integrator" is whichever session happens to launch in the
  `main` worktree. Measured cost: **56 fragments uncollated for 13 days** (oldest 2026-07-28; 129 category
  chunks, 245 bullets; S 31 · M 13 · E 6 · O 5 · integrator 1) while `CHANGELOG.md` was itself edited three
  times in the same window. Nothing failed — no gate watched `changelog.d/` and fragments cannot conflict by
  design, so the debt was **invisible by construction**. Now: **whoever merges to `main` collates, inside the
  same `flock`** (holding the lock *is* holding the integrator role; the edit happens on `main`, so the
  "never edit `CHANGELOG.md` from a line branch" rule is intact).
- **`CLAUDE.md` §9 now states that "integrator-owned" names a role, not a person or a schedule**, and carries
  a chore → **event** → **visibility** table for all four integrator chores. A new integrator-owned chore
  must name both, or it rots the same way — the same shape as guardrail 4's corollary, where three opt-in
  flags with known-wrong defaults sat for weeks because each line recorded the flip as the other's to schedule.

### Added

- **The nocturnal-H diagnosis for Component E (line E, milestone E6; ADR 0073 — supersedes ADR 0072 items 4
  and 6).** `scripts/e_nocturnal_h_decomp.jl` attributes the H error by **exact algebra** rather than by
  parameter sweep. Because `H` is the exact residual `Rn_m − LE − G_m`, its error obeys identically
  `ΔH = ΔRn − ΔG + ε_obs`, where `ε_obs = Rn_o − LE − H_o − G_o` is the **tower's own non-closure** — an error
  no closing model can remove. `g_a` appears in none of the three terms. The probe reports, per site: a harness
  check (model self-closure `= 0.0` exactly; the identity closes to `≤ 2.3e-13`; ADR 0072's night numbers
  reproduced digit for digit), the decomposition night/day/all, `G` scored against **both** the measured plate
  `Qg` and the budget-implied sink `G_res = Rn_o − LE − H_o`, **night-only** `Rn` (never reported before), a
  100× `g_a` bracket, the tower's measured-`u*` `g_a` substituted into the real solver, the model's **native
  daily step**, the observation-implied `λ_g`, and a `λ_g` sensitivity table.
- `scripts/build_e_seb_validation_table.py` now also emits **`ustar`** (u\* ≤ 0 masked — a documented OzFlux
  artifact). Row counts are unchanged at all four sites, so ADR 0072's basis is untouched.
- A synthetic CI testitem pinning the **lever ranking** (`test/testitems/energy_closure_tests.jl` — *"nocturnal
  H is a ground-heat lever, not an aerodynamic one"*), so the refuted hypothesis cannot quietly re-open.

- **Component E is now validated against flux towers (line E, milestone E4 — the P2 gate; ADR 0072).**
  `scripts/build_e_seb_validation_table.py` stages a tower-forced driving table per PLUMBER2 site (the tower's
  own `swdown/lwdown/tair/psurf/wind`, its measured LE, its **observed albedo** from Σ SWup/Σ SWdown, its canopy
  and — load-bearing — its **measurement height**, which overrides `SEBParams.z_ref`), and
  `scripts/validate_e_seb_vs_plumber2.jl` runs `solve_seb` over every step and scores H, T_skin and Rn: bias,
  RMSE, MAE, R², OLS slope, all/day/**night**, half-hourly **and daily**, the fraction inside PLUMBER2's own
  `|h_cor_uc|` band, the mean diurnal cycle, and a `stab_amp`/`stab_k` sweep.
- **The gate is frozen as a regression test**: two committed extracts sampled every 12th day of year at every
  3rd hour across the whole record (`test/testitems/references/e4_seb_drive_{DE-Hai,AU-ASM}.csv`) re-run the same comparison inside
  `test/testitems/energy_closure_tests.jl`, with the known night-cold-bias pinned as a sign assertion so a
  future fix trips the test instead of drifting silently.

- **Component-E observational reference (line E, milestone E1; ADR 0070).** PLUMBER2 v1-0 is now staged and
  loadable: `scripts/fetch_plumber2_sites.py` downloads 9 sites (DE-Hai — the Hainich prototype cell — plus
  one tower per biome slot of `test/testitems/biome_coupled_tests.jl`, plus the 4 OzFlux sites that carry
  `LWup`) from the anonymously-readable NCI THREDDS `ks32` collection and writes a `manifest.json` with a
  `sha256` per file; `scripts/validate_e_plumber2_load.py` loads Flux + Met into a model-facing half-hourly
  frame and emits the sanity report — coverage, QC-flag composition, unit/range checks, the observed
  `Rn = LE + H + G` residual and closure slope, daytime Bowen ratio, a mean-diurnal `SWdown` peak-hour check
  of the time axis, and `T_skin` inverted from `LWup` at E's own emissivity — plus
  `halfhourly_/daily_/diurnal_<site>.parquet` (the daily gate *and* the retained sub-daily cycle).
  `config/paths.yaml` `data.energy_reference` is no longer a TODO.

- Component E gate pinning ADR 0072's night-cold sign **under the new default**, where it deepens rather than
  disappears (towers: −0.95 → −3.17 K at AU-ASM, −1.99 → −3.67 K at AU-Tum, −1.09 → −2.03 K at AU-Rob;
  synthetic diurnal cycle −1.474 → −2.496 K), so the outstanding canopy-heat-storage term trips it.
- Daily-step `T_skin` per site in the two-layer probe — never pinned before, though `run.jl` solves once per
  day: R² 0.981 → 0.979 (AU-ASM), 0.900 → 0.851 (AU-Tum), 0.858 → 0.793 (AU-Rob).

- **Component E: opt-in two-layer prognostic ground-heat column** (`SEBParams.enable_two_layer`, default
  `false` ⇒ every baseline byte-identical). Replaces the single conductance against a 30-day EWMA of *air*
  temperature with a prognostic two-layer soil column (`G = κ_g(T_skin − T1)`, `κ_g = 2λ_soil/z1`, the
  MITgcm land-package `T1`/`T2` update), so the ground reference is the surface's own thermal state.
  An **independent implementation** of the MITgcm formulation, cross-read against SpeedyWeather.jl's
  `LandBucketTemperature` and Terrarium.jl's half-cell skin temperature; no code copied, no new dependency
  (ADR 0074, ADR 0017). `SEBParams` also gains an explicit `dt_seconds`, which is what makes a sub-daily
  step well-defined.
- `scripts/e_two_layer_probe.jl` + `scripts/e_seb_drive_common.jl` (shared PLUMBER2 drive-table readers and
  metrics, extracted so future probes stop copying them).

- **Wind + surface pressure for Component E (line E, milestone E2; ADR 0071).**
  `scripts/remap_wind_psurf_cells.py` remaps daily `sfcwind` [m/s] and `ps` [Pa] from the ISIMIP3a obsclim
  GSWP3-W5E5 tree — the same climate family the LPJmL-FIT run itself consumed — onto the model's orderA cells
  (`grid.nc` `cellid` → lat/lon → source axis, matched by value with an exactness assertion), dropping 29
  February for the model's noleap-365 calendar. Writes the committed per-cell fixtures
  `test/testitems/references/wind_psurf_<biome>.csv` (`year,doy,wind,psurf`, 2010–2019 × 365 d) for the same
  five biome cells as `biome_forcing_<biome>.csv`. `config/paths.yaml`
  `lpjml.energy_extra_inputs.{sfcwind,ps}` are no longer TODOs.
- The script carries its own four-part gate, all **PASS at all five cells**: exact agreement with an
  independent `xarray` label lookup; an obsclim-`tas`-vs-`temperature_test.clm` round-trip
  (`max|Δ| = 0.000 °C` over 365 days) that proves the lat/lon ↔ orderA-cell mapping against a file the C run
  actually read; calendar agreement with the LPJmL-prepared noleap wind (to its 0.01 m/s quantization); and a
  physical cross-check at Hainich against the DE-Hai tower — grid wind −10.1 %, psurf +1649 Pa, i.e. a 0.5°
  cell mean ≈143 m below the tower.

- **Line M — the level anchor's flip criterion is measured, and it FAILS (ADR 0056, answering ADR 0103 §6).**
  `scripts/biome_slow_oracle_probe.jl` gains two anchored arms (`anchor = 0.5` and `0.1`) beside the existing
  free and `n_prev`-teacher-forced ones, a clause-by-clause evaluation of line S's pre-registered criterion
  with thresholds fixed in-script before the run, a mechanism check that the anchor actually fired, and a
  per-year report separating the two competing explanations of the one cell that breaks.

- **M3 F-side — a per-cell F_diff-vs-C oracle for all five biome cells** (ADR 0053). The C's daily
  `d_gpp`/`d_transp` are grid-cell totals over **all** PFTs while the coupled driver's canopy is tree-only,
  so the grass share was removed **exactly** rather than caveated: four cheap single-cell re-runs
  (`CELL=<c> RUNTAG=M_grass_val scripts/run_fdiff_grass_gpp_cell.sh`, ~9 s each) added the custom per-PFT
  daily grass GPP output, giving `gpp_tree = d_gpp − d_grass_gpp`. Grass carries **42.4 %** of GPP at boreal
  Siberia, 28.4 % mediterranean, 19.3 % Sahel, 5.8 % Hainich, 0.2 % Amazon.
  - `scripts/extract_biome_fdiff_oracle.py` → the committed `test/testitems/references/M_fdiff_oracle_biomes.csv`
    (+ `_meta.json`): per-cell monthly climatology 2010–2019 of tree GPP, ET and its three components,
    tree FPC and stand LAI, each with its basis recorded and its splittability stated.
  - `scripts/biome_fdiff_oracle_probe.jl` → the F side, on the C's own **25-patch ensemble** basis, at
    ADR 0051's `wscal_leafon = true` (passed explicitly; the package default stays `false`).

- `fpc_tree_crown` (and `fpc_grass_crown` on the monthly table) in
  `test/testitems/references/M_fdiff_oracle_biomes{,_annual}.csv`, plus `fpc_tree_crown_mean`,
  `fpc_grass_crown_mean` and `crown_over_stand_fpc` in `M_fdiff_oracle_meta.json`. Appended last, with both
  `basis` strings now naming which functional form they are — **every pre-existing column is byte-identical**
  (verified row-by-row), so no committed baseline moves.
- `scripts/biome_fdiff_oracle_probe.jl` PART 6: year-matched FPC ratios on the crown basis, the `>5m_frac`
  column (the fraction of the C's own crown cover that lives in the stems above 5 m the `ind` writer
  actually emits — 0.71 at boreal and the Sahel, so no ratio may be read against 1.0), and F's crown cover
  at **t = 0**. That last column separates the canopy reconstruction from the fast core's growth and shows
  the **reconstruction is faithful (1.00–1.04 in all five cells)**, eliminating it as a cause.
  `biome_slow_oracle_probe.jl`'s canopy report now prints both bases side by side.

- **Line M / M2 — the flux-driven Component S now runs in the MULTI-CELL coupled loop.** All five biome
  cells (boreal / temperate / mediterranean / semi-arid / tropical) build their own `FluxDrivenSlowEmulator`
  from their own `n_init` / `age0` / slow boundary — folded into the committed `references/M_cells.csv` by
  `scripts/extract_cell_slow_init.py` — plus their own per-cell `ClimBuf` for the transient bioclimatic
  boundary. Previously the driver ran `slow=nothing`, so the coupled evidence for S was single-cell
  (Hainich) while the global evidence was offline-only.

  New gate (third test item in `test/testitems/biome_coupled_tests.jl`), asserted in **every** cell: carbon
  at the S↔F handoff ≤1e-6·C_scale and <1e-6; energy <1e-6 W/m²; deterministic under seed; a fixed-N control
  proving F alone cannot move tree N; and the `ClimBuf` driving only the two climate axes
  (`soil_depth`/`co2` pass through) with its recomputed `gdd5` ordering the cells the same way their baked
  C-derived `gdd5` does.

- **M3 S-side — the coupled demography/trait oracle vs the LPJmL-FIT C truth, closing the P3 gate**
  (ADR 0054). `scripts/extract_biome_slow_oracle.py` builds the C's per-cell demography + trait reference
  for the five biome cells from the annual `ind` parquet (historic, both seeds, 2010–2019) on ADR 0053's
  four bases — tree-only via the imported `TREE_TYPES`, the C's **25-patch ensemble** rather than a per-cell
  total, year-matched, and the writer's `height > 5 m` population — committed as
  `test/testitems/references/M_slow_oracle_{counts,traits}.csv` + `M_slow_oracle_meta.json`.
  `scripts/biome_slow_oracle_probe.jl` scores the coupled S+F+E loop against it in seed1-vs-seed2 noise
  floors, with an `n_prev` teacher-forcing arm that attributes the error.
- A CI `@testitem` guarding the new fixture's **basis** (`biome_coupled_tests.jl`): coverage, the per-patch
  identity `n_mean · npatch == n_cell_total` at `npatch == 25`, a two-extractor population cross-check
  against `M_cells.csv`'s `n_trees`, quantile monotonicity, a strictly positive q05 on every axis (the
  zeroed-grass-row tell) and `Height` q05 ≥ 5 m. The skill measurement itself stays cluster-only — the
  pinned `_t8` pair is 180 MB on `/p/tmp` and CI has no cluster.

- **The M4 RESILIENCE BATTERY (line M, milestone M4; ADR 0055).** `ENGINEERING_STANDARDS` §2's last stubbed
  gates — three `@test_skip false` in `resilience_battery_tests.jl` (item 11) and one in
  `rollout_stability_tests.jl` (item 4) — are replaced by real tests, and the metrics behind them are
  measured rather than quoted. Method reimplemented from Bathiany et al. 2024 (doi:10.1111/gcb.17613);
  `LPJ_resilience` has no licence, so none of its code is copied.
  - `scripts/extract_resilience_reference.py` — the C's own memory from the annual `ind` parquet,
    **52 544 / 52 551 cells (seed1/seed2) × 2000–2019** — the full extent of the historic table, 52 224
    cells present in both seeds — on ADR 0053/0054's four bases. Emits `references/M_resilience_reference_{cells,gradient,series}.csv` + `_meta.json`. Its
    per-year patch-ensemble means are asserted equal to `M_slow_oracle_counts.csv`'s on all 100 overlapping
    cell-years — a different script, a different scan, the same population.
  - `scripts/biome_resilience_probe.jl` — the coupled side: a **3×2 shuffle design** (forcing
    ordered/year-shuffled × demography free/`n_prev`-pinned/absent) plus ADR 0054's teacher-forced anchor
    arm, over a **one-member-per-patch ensemble** of the year-2000 canopy, then a 100-year cycled rollout
    carrying a pool-perturbation recovery experiment. Emits `references/M_resilience_battery.csv`,
    `_shuffle.csv`, `_longrun.csv`.
  - `scripts/extract_biome_forcing.py` gains `FIRSTYEAR`/`LASTYEAR` (default unchanged; the widened
    2000–2019 window reproduces the committed 2010–2019 fixture **byte-identically** on all five cells).
  - CI computes what CI honestly can — the estimator against synthetic AR(1)/ramp series with known
    answers, and a real `slow = nothing` F+E rollout that is perturbed, shuffled and run 60 years — and
    gates the cluster-measured numbers as fixtures. No `src/` change; every committed baseline is
    byte-identical.

- **Per-cell input provisioning for the multi-cell coupled S+F+E driver ([ADR 0050](docs/decisions/0050-per-cell-input-provisioning.md)) — milestone M1.**
  The coupled driver was already N-cell-agnostic, but all five biome cells reused **Hainich's** soil column
  and **Hainich's** canopy. Each cell now carries its own inputs, produced by two new committed extractors:
  - **`scripts/extract_cell_soilcolumn.py`** — the per-layer soil column that previously had *no* generating
    script at all. `whcs_mm` = the C's own `WHC_NAT` output (the patch-ensemble-mean `whc` fraction,
    `soilpar_output.c:42`) × the cell-invariant layer thickness read from `depth_bnds`, reduced by a mean over
    all 240 monthly steps; `rootdist` = the fpc-weighted mean over the cell's living trees of each
    individual's own `getrootdist.c` profile, using FIT's own `beta_root` with the rooted depth recovered by
    inverting the emitted `D95` (`R = ln(1−(1−β^D95)/0.95)/ln β`, [VERIFIED] `R ≥ D95` and `R ≤ 2000 cm` for
    every individual in all five cells). **Gate: re-extracting cell 42490 reproduces all 23 printed rows of
    the committed `hainich_soilcolumn.txt` byte-identically** (`max|Δwhcs| = 3.7e-5 mm`,
    `max|Δrootdist| = 4.3e-7`) — which required finding that the fixture came from the *single-cell* run, not
    the 512-task global one (they differ by 1.6e-4 relative in layer 0 under `-DPERMUTE`), and that the time
    mean must accumulate in float32.
  - **`scripts/extract_cell_individuals.py`** — the N-cell generalization of `extract_fdiff_individuals.py`
    (whose reconstruction physics it imports rather than duplicates). Reproduces the committed Hainich
    numbers exactly (`cell_fapar_leafon` 0.8339690, 297/272/25 individuals) and validates every other cell
    against **that cell's own** C daily FAPAR from a fresh single-cell re-run.
  - `scripts/extract_biome_forcing.py` now holds **the** canonical N-cell registry (`cells_from_env`), which
    both new extractors import, and `references/M_cells.csv` carries cell/lat/lon from `grid.nc` `cellid`, so
    the hard-coded `BIOMES` dict and hard-coded latitude list are gone. Its committed forcing output is
    byte-identical after the refactor.

  The emergent rooting gradient comes straight out of FIT's trait distributions: top-1 m root fraction
  99.3 % (semi-arid Sahel) → 88.6 % (boreal) → 87.8 % (Hainich) → 61.5 % (mediterranean) → 53.2 % (tropical
  Amazon), effective D95 72 cm → 690 cm. `scripts/run_coupled_biomes.jl` now runs both the per-cell and the
  legacy common-Hainich configuration, so the **vegetation+soil** contribution is separable from the climate
  contribution for the first time: +10.8 W/m² LE in the Amazon, −7.6 W/m² in the Sahel, mediterranean Bowen
  1.27 → 0.65. Energy still closes to ~1e-14 W/m² in every cell.
  Gated by `test/testitems/biome_coupled_tests.jl` (now two test items: the per-cell inputs are well-formed
  **and pairwise distinct** — the guard against silently falling back to one cell's inputs — plus the
  unchanged energy-closure and climate-partitioning assertions). Suite 106,987 pass / 0 fail / 4 broken.
  `hainich_soilcolumn.txt` and `hainich_individuals_2010.csv` are untouched, so no committed baseline moves.
  Honest limitations: the canopy reconstruction is leaf-on, so reconstructed/C peak FAPAR runs ~1.3–1.6
  across the five cells (Hainich 1.60); `getrootdist`'s permafrost redistribution of roots below
  `mean_maxthaw` is not ported (no output carries the thaw state); and every biome still runs beech ANGIO
  PFT parameters (milestone M5).
  \+ skill: `provision-coupled-cell`.

- **An opt-in demography observation hook in the LPJmL-FIT C binary** (`patches/lpjmlfit_rung2_demography_hook.patch`),
  the observation half of the rung-2 harness. Activated by the environment variable `LPJ_RUNG2_DIR`; with it
  unset the model is numerically identical to the previous build. Dumps each patch's tree roster at the top
  of the annual demography block and again after establishment, including the three per-tree accumulators
  three of the four death rates read (`water_stress`, `temp_stress`, `bm_inc_counter`) and all seven carbon
  pools — none of which the `ind` output carries. ADR 0061.
- `scripts/diagnose_cbinary_rebuild_equality.py` — the gate to run after **any** rebuild of the C binary.
  Compares **decoded NetCDF variables** (a file-level `cmp` is defeated by LPJmL's `history` timestamp,
  ADR 0043) plus the text outputs byte-for-byte.
- `scripts/diagnose_rung2_roster_vs_ind.py` — proves the hook's post-demography roster reproduces the C's
  own `ind` table on the same run (5 465 trees, identical tree sets, all 21 shared columns to ≤5.0e-6).

- **Line M / M2 (in progress):** `scripts/extract_cell_slow_init.py` — folds the per-cell Component-S
  initial state (`n_init`, `age0`) and the 4-column slow boundary
  (`eco_diag_gdd_5, tas_cold_month, soil_depth, co2`, in the runtime
  `flux_feature_vector`/`live_flux_cond` tail order) out of line S's `cell_meta.parquet` sidecar and into the
  committed `references/M_cells.csv`, so the multi-cell coupled driver and its CI gate read one tracked table
  instead of a `/p/tmp` DVC artifact. Re-verifies the artifact's trained boundary order against its own
  `*_meta.txt` rather than assuming it, and **aborts** if any requested cell is absent from the pinned
  `cell_meta` (a cell the pinned DRF never saw has no honest `n_init`/`age0`).

- **The project's licensing basis — order P5 is done ([ADR 0080](docs/decisions/0080-licensing-basis.md)).**
  **Outbound = AGPL-3.0-or-later**, and it is *forced* rather than chosen: it is simultaneously what
  LPJmL-FIT's AGPL-3.0 copyleft requires of a derivative work and a licence the **EUPL-1.2 Appendix** names
  as a "Compatible Licence", so EUPL Art. 5's compatibility clause sanctions combining with Terrarium.jl and
  SpeedyWeather.jl (**both EUPL-1.2** — verified upstream, not MIT). That makes the position valid whether or
  not a package dependency counts as a derivative work — the question EUPL Art. 1 explicitly leaves to
  national law — which is the main reason a permissive outbound licence was rejected. **Terrarium.jl's
  `NOTICE` extends Art. 5 to *any* licence for "the normal use of the Work as a library"**, so taking it as
  `[weakdeps]` + a package extension is clean: **P4 (online coupling) is unblocked**, with runtime `[deps]`
  still empty (ADR 0014). The ADR separates **READ / DEPEND / VENDOR** as three different acts with different
  rules — vendoring third-party code now requires its own ADR — and fixes NeuralCrop.jl as *method-only*
  permanently (CC-BY-NC's NonCommercial term cannot be combined with AGPL-3.0 §7, so a work derived from both
  would be undistributable) and LPJ_resilience as reimplement-from-paper (unlicensed ⇒ all rights reserved).
  ADR 0017 is **annotated, not superseded**: its licensing driver was only ever about the VENDOR tier, and its
  outcome stands on its two independent drivers. New operational companion
  `docs/third_party_licensing.md` — the inbound-work register (licence, tier, *how it was verified*,
  obligation) plus the mandatory before-you-take-a-dependency checklist, driven by the new
  `dependency-license-gate` skill.

- **The SpeedyWeather ↔ Terrarium online-coupling harness runs on this cluster (P4).** Terrarium 0.1.3 +
  SpeedyWeather 0.21.1 now install alongside the emulator, and the upstream coupled model has been **verified
  running on a compute node** (6 simulated hours, `vegetation = nothing`, 4608/4608 cells finite, Float32
  held, T_skin −16.7…25.0 °C) — the control run against which our own physics will be judged.
  `[VERIFIED]` **SpeedyWeather ships `SpeedyWeatherTerrariumExt`**, giving
  `SpeedyWeather.LandModel(::SpectralGrid, ::Terrarium.AbstractModel)`, so Terrarium is the *supported*
  land-model socket and we write no atmosphere↔land plumbing. New `docs/p4_online_coupling_design.md` is the
  design of record (every API claim read from the installed packages), new `scripts/online_coupling/` holds
  the harness, and the new **`online-coupling-env`** skill captures the four traps that each cost a failed
  job: Julia **1.10.0 cannot precompile this stack** (`KeyError: "KernelAbstractions"`; 1.10.10 does it in
  81 s), `SpeedyWeather.EarthOrography` **downloads an artifact inside `initialize!`** so assets must be
  warmed on the login node, **Terrarium state is °C not Kelvin**, and `Pkg.status()` throws
  `KeyError: "Dates"`. The design's central finding: Terrarium steps at Δt = 300 s while F is daily and S
  annual, so rate processes couple directly but stateful ones need a piecewise-constant tendency — which
  ForwardEuler integrates to exactly the daily total, preserving conservation by construction. **No
  LPJmL-FIT physics is in the coupled loop yet**; the `FDiffPhotosynthesis` spike is specified in §4.

- **Line O / O3a — a real, spatially varying soil texture for the online (Terrarium) soil, plus a guard
  against the silent degeneracy it fixes** ([ADR 0083](docs/decisions/0083-online-soil-texture-and-degeneracy-guard.md)).
  Terrarium's default stratigraphy is pure sand (`clay = 0`), which collapses SURFEX's wilting point and
  field capacity to *exactly zero* and makes `plant_available_water ≡ 1` everywhere — no error, just
  "fully unstressed everywhere". The online soil now uses a single `PrescribedSoilHorizon` carrying the
  LPJmL-FIT ground-truth soil-texture map (`scripts/online_coupling/build_soil_texture_field.py` →
  `soil_texture.jl`), with SURFEX porosity, and `assert_nondegenerate_soil` throws on any configuration
  where `field_capacity <= wilting_point`.
- The texture must be supplied through `TerrariumLand`'s `fields`, **not** `InputSources`:
  `SpeedyWeatherTerrariumExt` builds its `ModelIntegrator` with an empty `InputSources`, so the input
  path used by Terrarium's own SoilGrids example is silently dropped under SpeedyWeather. A gate asserts
  the texture actually reached the model state.

- `scripts/biome_slow_oracle_probe.jl` — an opt-in level-anchor arm (`ANCHOR=<a>`) with the pre-registered
  criterion evaluated mechanically, plus the physical-stand table the corrected yardstick needs. With
  `ANCHOR` unset the script runs its previous two arms and prints its previous reports unchanged.
- `scripts/biome_resilience_probe.jl` — opt-in `lvl0`/`lvl1` arms scoring the level anchor's effect on
  year-to-year memory, reported as distance to the C oracle. These are **not** the existing `anchor0` arm
  (which is teacher forcing). Mean `|AC − C's AC|` **0.0439 free → 0.0405 anchored**; the anchor does not
  buy its level fix with dead dynamics. With `ANCHOR` unset the battery and its committed fixtures are
  unchanged; with it set, fixture writes are redirected to scratch so no committed baseline can move.

- `scripts/diagnose_ind_type_composition.py` — global per-`Type` census of the `ind` ground truth: stems,
  cells, cells lost entirely, and the per-cell trait-median shift induced by a PFT-set restriction.

- **Spatially BLOCKED cross-validation for the recruit-trait copula evaluation** (line S, ADR 0040 —
  the gate on promoting ADR 0038's 14-column artifact). `scripts/eval_slow_copula.jl` gains
  `FOLD_MODE=hash|block`, `BLOCK_DEG`, `BUFFER_DEG`, `CELL_LATLON` and `MTRY`. Blocked mode assigns folds to
  B°×B° tiles and then removes from each fold's TRAINING set every cell within `BUFFER_DEG` of any of that
  fold's test cells, so the evaluation can distinguish an environmental response from spatial interpolation
  off the test cell's immediate neighbours. All five knobs default to the pre-existing behaviour and the
  `pred_<axis>.f64` bytes are **verified byte-identical** with them unset (six of six files on the 50-cell
  smoke table).
- `scripts/build_slow_spatial_controls.py` — provisions the three position artifacts the experiment needs
  from `grid.nc`: `cell_latlon.txt` (plain text, because the eval has no Parquet/NetCDF dependency),
  `cell_geo_tail.parquet` (a pure-position conditioning tail) and `cell_env_perm_tail_s<seed>.parquet`
  (the true env tuples permuted across cells — same width, same cell-level 6-way joint, zero geography,
  asserted by a lexicographic bijection check and a neighbour-correlation report).
- `scripts/blocked_cv_folds_probe.jl` — gates the fold machinery before any compute is spent: re-derives the
  realized nearest-training-cell distance by great-circle brute force (independently of the eval's own grid
  dilation) and asserts the buffer is honoured, plus a block-size × buffer design sweep.
- `scripts/diagnose_slow_neighbour_skill.py` — scores an EXISTING matched prediction pair stratified by each
  test cell's distance to its nearest training cell, at zero new compute.
- `scripts/build_slow_copula_env_augment.py` gains `ENV_PARQUET` / `TAIL_TAG` so the ablation control tails
  ride the same verified transform instead of a forked script, with a new one-row-per-`Cell` gate on the
  input (the `group_by("Cell").mean()` is the identity for a per-cell tail, so a duplicated `Cell` would
  otherwise be silently AVERAGED into a tuple present in neither marginal).

- `scripts/build_slow_cell_env_sidecar.py` emits `tables/cell_env.parquet` — the per-cell env conditioning
  sidecar the 14-column recruit-trait copula needs to be coupled-runnable at all. Until now nothing in the
  runtime supplied those six values: every caller hand-built them from `cell_year_feats.parquet` inside a
  bespoke script, which is unreachable from CI and basis-sensitive. Both open handoffs listed this as a
  standing blocker. 67 420 cells (a superset of the pinned table's 58 766, so line M can provision any grid
  cell), 2.0 MiB, with a manifest recording the basis, the year span, and the column order a positional
  consumer must respect.

- `scripts/verify_hainich_demo_artifacts.sh` — the byte-identity gate (guardrail 4) for any Component-S
  pipeline change claimed to be a no-op at the prototype cell. Regenerates all four committed Hainich demo
  artifacts and gives a **two-tier** verdict: `PASS`, `FAIL` (the edit moved the table), or `STALE-FIXTURE`
  (the fixture was already out of date) — a one-tier gate cannot tell those apart.
- `scripts/diagnose_slow_table_drift.py` — the control for that gate: builds the same single-cell table with
  `build_slow_runtime_table.py` as of a git `REF` and with the working tree, and diffs `X` column-by-column.
  Answers "did my edit change the table, or was the fixture already stale?" with a measurement.
- `scripts/diagnose_lai0_growth_eff.py` — the `lai == 0` / `growth_eff` census per seed and per tree
  population, and the reproducer for the cross-seed-join diagnosis above.
- **`VERSION=<tag>`** on `run_global_slow_{training,copula}.sh` and `run_pooled_slow_{training,copula}.sh`:
  suffixes every table dir, artifact and log so a retrain on a changed basis writes **new versioned files**
  and line M re-pins deliberately (ADR 0029/0031), instead of overwriting artifacts M depends on.

- **`.rcop` format v2 carries `qrf`** (`DRF.save_copula(...; qrf)` / `load_copula` → 6-tuple). The QRF leaf
  weighting selects a different conditional distribution from the same forests and previously lived ONLY in
  the sidecar `_meta.txt`, while line M's contract pins a `.rcop` *path* — so a consumer that missed the
  sidecar silently sampled the estimator that was not scored, with every draw in range. Flipping it changes
  all three of t9's golden draws. v1 still loads and means `qrf = false`, `qrf` is the sixth tuple element so
  all five pre-existing 5-way call sites are untouched, and a forged v99 header is refused ⇒ guardrail 4
  holds and nothing line M pinned needs regenerating. Recorded as a **version bump** of the frozen S→M
  contract, not a mutation.
- **`FluxDrivenSlowEmulator` rejects a conditioning-width mismatch at CONSTRUCTION.** `DRF._check_nfeat`
  fires only inside `sample_copula!`, reached only when a patch actually recruits — so a cell that thins
  every year, or an all-grass patch, never draws, and a mis-wired coupled run completes "successfully" while
  conserving carbon. The constructor is the only place holding both the boundary and the copula, so it now
  probes the policy once. A new testitem builds a 14-column `qrf=true` copula **through the emulator** (a
  composition no test had ever run), plus both crossed mismatches and a wrong-length boundary.
- Measured the previously-unmeasured **leaf geometry at the production config** (`rcop_leaf_geometry_probe.jl`
  on t9): 33 449–46 036 leaves/tree, **52.3–67.0 % of stored values still depth-capped**, and only 84–86 % of
  large leaves at `max_depth` (vs 99.9–100 % at 50k/d14). Depth is therefore **not** exhausted at d22/2M and
  is still free in bytes.

*post-merge measurement:*

- **The production config TRANSFERS to the `pooled_w20` basis line M actually pins** (job 1647661, 57 719
  cells, A/B on one basis via `score_slow_copula_dispersion.py`): Wooddens `emu_r` 0.8261 → **0.9095**,
  `sd_ratio` 0.6119 → **0.8493** (criterion 2 **FAIL → PASS**), slope `Y1~pred` 1.3501 → 1.0708. Criterion 3
  improves on all four axes against the *pooled* baseline (SLA .0039→.0009, Wooddens .0065→.0007, D95max
  .0020→.0014, minwscal .0040→.0003), and every axis gains `emu_r` (SLA +0.0510, Wooddens +0.0834, D95max
  +0.0996, minwscal +0.0131).
  **Read it correctly:** this is the FULL three-lever delta against a 60-tree/50k/d14/ncond-8/QRF=0 baseline,
  **not** the isolated conditioning lever — the comparable full-stack figures are historic +0.087 `emu_r` /
  +0.1766 `sd_ratio` versus pooled +0.0834 / +0.2374, so the config transfers and does *better* on dispersion
  there. Criteria 1 and 4 remain uncomputable for pooled (no pooled seed2), and this does **not** resolve the
  spatial-address question — the pooled folds are still `mod(hash(cell), k)` and the env columns are identical
  for a cell across both scenarios, so spatially blocked CV is still the gate on production.

- `scripts/rcop_acceptance_probe.jl` — acceptance test for a **production** recruit-trait copula artifact,
  run in a FRESH process against the shipped `.rcop` + its sidecar `_meta.txt`. `train_slow_copula.jl`
  already round-trips the bundle inside the process that built it, with the forests still in memory; that
  proves serialization is self-consistent but not that a later process can use the file. The probe closes
  that gap: it times the load, checks every axis forest's `nfeat` against the header `ncond`, cross-checks
  the sidecar's `ncond`/`cond_cols`/`axes`, reproduces the golden `(seed, x)→draw` pairs, rebuilds the
  conditioning row through the actual runtime policy (`live_flux_cond` or `live_flux_cond_env`) and asserts
  it equals the artifact's own fallback row, and confirms a wrong-width row is REJECTED rather than
  silently answered. On `recruit_copula_global_historic_t9.rcop` (484.5 MiB): **load 6.77 s = 71.6 MiB/s
  measured** (an earlier handoff's "~12 s at 42 MB/s" was an unmeasured estimate), all checks PASS.
- `scripts/score_slow_copula_dispersion.py` — the **seed1-only** between-cell statistics (`emu_r`,
  `sd(pred)/sd(Y1)`, OLS slope) with an A/B diff of two prediction sets on one basis. The ADR-0030 gate
  needs a **seed2** realization for its ceiling, `%GAP` and `r_center`, and a seed2 table exists for
  `historic` ONLY — so criterion 2 (the under-dispersion axis the whole S2 milestone is about) was not
  measurable for the `pooled` artifact line M pins. This measures it. The per-cell reduction is IMPORTED
  from `noise_floor_vs_emulator.percell_table` rather than reimplemented, so it cannot drift from the
  gate's own definition; it prints, rather than hides, that criteria 1 and 4 stay unmeasured without a
  seed2.

- **Two probes that decompose the Component-S recruit-trait GAP before any conditioning change is written**
  (milestone S2). `scripts/diagnose_copula_cond_ceiling.py` splits the ADR-0030 per-cell trait GAP into
  *estimator inefficiency* vs *new-covariate headroom* by fitting a direct per-cell regressor (K-fold by cell)
  on the current conditioning versus a wider environmental set; it validates itself against the documented
  `emu_r`/`floor_r`/`sd_ratio` first and stops if they disagree. `scripts/diagnose_copula_capacity.sh` re-runs
  the K-fold-by-cell OOS evaluation at a chosen estimator capacity on an **unchanged** table — via a shadow
  directory of input-only symlinks, so a re-evaluation can never overwrite a validated generation's
  `pred_<axis>.f64` — and scores the ADR-0030 gate, measuring capacity in isolation from any conditioning
  change.

- **`scripts/diagnose_count_recursion_anchor.jl`** — the three-section diagnosis behind ADR 0102:
  (a) **coherence**, the per-year `n_prev` / `target` / raw ratio / clamped `ρ` / realized-density table with
  the clamp-binding count and the cumulative AR-vs-roster divergence; (b) **anchoring**, an `n_init` sweep
  measuring whether the recursion forgets its initial condition; (c) **level anchor**, the decisive test —
  perturb the initial density and measure retention against horizon. It prints an explicit verdict for the
  "(B) is empty" outcome, because a null there is a real and reportable result rather than a failed probe.

- **Component S: the ADR-0030 gate's criterion 3 is now actually measured.** The criterion is *pooled KS*, but
  the copula evaluator prints `nqrmse` and the noise-floor gate prints neither, so every capacity rung had been
  scored without it. `scripts/score_slow_copula_ks.py` reports pooled KS, median per-cell KS, `nqrmse` and
  median relative quantile error per axis on one row universe, importing the same `ks2` that produced the
  published `metrics_traits.txt` numbers. The two statistics are not interchangeable — they disagree by ~55×
  in magnitude (`agb`: `nqrmse` 0.6432 vs KS 0.0116) and in *direction* — and on the corrected statistic the
  `b6x2M` capacity rung **improves the pooled marginal on all four trait axes**, reversing the verdict
  recorded in ADR 0037.
- **Component S: per-rung leaf geometry.** `eval_slow_copula.jl` now prints leaves per tree, the leaf-size
  distribution, the share of stored values sitting at `depth == max_depth`, and the size-biased expected draw
  pool. Measured on the `t8` artifact, 99.9–100 % of leaves holding at least `2·min_leaf` values sit exactly at
  `max_depth` and 57–67 % of all stored values are in one — so the marginal forests are truncated by the depth
  budget, and `max_depth` is a lever that costs no artifact bytes while `subsample` scales them linearly.
- **Component S: `scripts/build_slow_copula_env_augment.py`** derives an extended-conditioning copula table by
  appending the per-cell env tail to an existing table's `Xc` rather than rebuilding from the `ind` parquet, so
  a conditioning experiment cannot be confounded by the polars-streaming key-set non-determinism of ADR 0036
  §5b. Verified bitwise-identical on the inherited columns across all 197 721 867 rows.

- **ADR 0043 — the cross-build gate PASSES: the `Feb  5 2026` and `Jul 21 2026` LPJmL-FIT builds are
  trajectory-identical and may be pooled as a pure seed pair.** Closes the question ADR 0041 specified
  but could not run to a verdict. The matched-decomposition gate (full-grid 67 420 cells / 2048 tasks,
  a faithful re-run of the ssp370 seed1 member) reproduces the seed1 ground truth bit-for-bit:
  `globalflux` `cmp`-identical, `vegc` identical across all seven variables by SHA-256, and the 193 GB
  per-individual `ind` roster `cmp`-identical over all 81 years — a far stronger result than the gate
  required, since `ind` is the finest grain the model emits.
- `scripts/diagnose_ind_seed_independence.py` gains **`--log-dir <run_dir>`**, which resolves the newest
  non-empty `lpjml_*.out` instead of taking a pinned job id, and now treats a 0-byte log as a distinct
  provenance FATAL rather than a gate failure.

- `scripts/exposure_bias_probe.jl` — prices the exposure-bias retrain **offline** from the existing `_t8`
  tables (one-step bias `b`, AR gain `g = ∂pred/∂n_prev`, and the implied compounding `b(1−g^k)/(1−g)`)
  before anything is spent on training. Its verdict: the bias is **empty** (−0.0014 stems/patch/yr
  held-out-cell OOS on counts of ~10, `g = 0.56` ⇒ a bounded 2.28× amplification), so the retrain is
  cancelled rather than deferred (ADR 0105 §5).
- `scripts/biome_slow_oracle_probe.jl` — REPORTS 8 and 9: the same five biome cells run with **one
  ensemble member per patch** (the basis the C reports and the count model was trained on), scoring the
  ADR 0104 §7 criterion clause by clause and splitting the residual with a teacher-forced arm. The modal
  reports are unchanged and reproduce ADR 0104's published numbers in the same run, so the two bases are
  visible side by side.
- `scripts/biome_resilience_probe.jl` — the memory clause's PASS/FAIL is now computed in-script, including
  its new per-pair tolerance, instead of being read off the table by hand.

- **Runtime-consistency is now observable and CI-gated, not inferred (ADR 0034).**
  `FluxDrivenSlowEmulator.feature_history` records the exact `flux_feature_vector` row handed to the forest
  each year (diagnostic only — no numerical change, every committed baseline byte-identical), and
  `scripts/train_slow_drf.jl` writes the trained `y_min`/`y_max`/`feat_min`/`feat_max` bands into every
  artifact meta. `slow_production_drf_tests.jl` now asserts the RUNTIME rows against that band. This replaces
  a check that could not fail: a DRF prediction is a convex combination of training leaf means, so "predicted
  targets are inside the training band" holds however out-of-domain the input is — which is exactly how a
  two-order-of-magnitude proxy-basis shift stayed invisible behind green gates.
- `scripts/measure_hainich_gate_bands_probe.jl` — re-measures every threshold the four committed-Hainich-fixture
  gates assert, in one run, plus the two checks the tests structurally cannot do (artifact-vs-artifact basis
  agreement, and runtime-vs-trained feature band). `DRF_ART`/`DRF_META` point it at an older artifact to
  produce the BEFORE column of a before/after table; it reproduced the documented pre-S1c numbers
  (0.39 / 1.25 / 0.67) exactly, which is what validates the harness.

- **A LEVEL ANCHOR for the coupled stand — opt-in, default-off, and it closes a 41 % over-density nothing
  in this project could see ([ADR 0103](docs/decisions/0103-the-level-anchor-ships-the-conversion-was-a-constant.md)).**
  `FluxDrivenSlowEmulator(...; anchor = a, patch_area = 225.0)`. ADR 0102 measured that the coupled stand has
  no level anchor — it is advanced by a pure ratio, `D_T = D_0·Πρ_t`, so the count DRF's *absolute* skill
  never reaches it — and then **deferred the fix on a false premise** (see below). It is now built:
  - **Mechanism.** A **geometric** blend of the AR ratio and the ratio that lands the stand on the DRF's
    absolute target: `ρ_eff = (target/n_prev)^(1−a)·(D_want/D)^a` with `D_want = target/patch_area`, clamped
    by `max_mort`/`max_estab` exactly as before. Geometric rather than arithmetic keeps the update
    multiplicative and strictly positive, so the carbon routing is untouched and `a` is a **relaxation rate**
    (time constant ≈ `1/a` years) rather than a mixing weight.
  - **`anchor = 0` does not evaluate the branch** ⇒ every committed baseline, ReferenceTest and AD gate is
    byte-identical. This is the ADR-0049 opt-in pattern reused unchanged, and it is *measured*, not asserted:
    the new testitem compares the full density trajectory with `==`, not `isapprox`.
  - **Measured** (job 1707102, Hainich, 150 yr, the same 4× initial-density sweep as ADR 0102 §3):

    | `anchor` | retention | terminal spread | stand ÷ its own count target |
    |---|---|---|---|
    | 0.00 | 1.0364 | 4.207× | **1.409** |
    | 0.10 | **0.0513** | 1.074× | **1.000** |
    | 0.25 | 0.0491 | 1.071× | 1.000 |
    | 0.50 | 0.0513 | 1.074× | 1.000 |
    | 1.00 | 0.0762 | 1.111× | 1.000 |

    The initialisation is forgotten (retention ÷20) **and** a previously invisible level error is closed: the
    unanchored stand settles **1.409× denser than its own count model's absolute prediction**. Every existing
    gate — the ADR-0030 per-cell trait gate, the count R², the trained-band check — reads ratios,
    distributions or correlations, so **none of them can see an absolute-level error**.
  - **Recommendation for line M: `anchor = 0.1`** — 0.1–0.5 are equivalent and `a = 1` is measurably *worse*
    (retention 0.076), because a hard anchor overwrites the stand's own dynamics each year so a perturbation
    is re-imposed through the clamp and the recruit branch instead of relaxing away. This is the measured
    value the owner's standing pre-authorisation of M's baseline regeneration was waiting on.
  - **`patch_area` travels with the ARTIFACT, not the cell.** 225 m² is `param.patcharea` of the training
    runs — a global constant in this configuration, so no `cell_meta.parquet` column — but stock LPJmL-FIT
    uses **100.0**, so an artifact built from a different `patcharea` run must pass its own value or the
    anchor pulls the stand to a level wrong by the ratio of the two areas. Inert when `anchor == 0`.
- `test/testitems/slow_level_anchor_tests.jl` — pins byte-identity at `a = 0` (with `==`), that `a > 0`
  actually anchors (so the test cannot pass on a no-op — the ADR-0048 never-fired-null failure mode), that
  retention drops, that `patch_area` is load-bearing when on and inert when off, carbon closure, determinism,
  and the `[0,1]` kwarg validation in both directions.

- `scripts/diagnose_per_tree_water_access.py` — the Phase-0 kill/proceed check for the rooting-depth gap.
  Measures, on the LPJmL-FIT C model's own per-individual `ind` output rather than by simulation, how
  differently real trees in the same cell and year experience water: the across-tree spread of `wscal_mean`,
  its amplification in dry years, the within-(PFT × age-band) correlation with each stem's own `beta_root` /
  `D95max`, and the share of total mortality hazard carried by `mort_water` / `mort_temp` together with the
  selection differential those hazards impose on rooting depth. Pre-registered pass criterion; both
  scenarios; 5 biome cells.

- **Per-tree root profiles and per-tree water status** in the differentiable fast core (ADR 0110, opt-in via
  `WaterParams.per_tree_roots`, default off ⇒ every committed baseline byte-identical). Each individual with a
  rooting-depth trait now gets its own root-weighted soil moisture, its own water supply, its own water
  scalar, and withdraws down its own profile — instead of every tree sharing one cell-average profile
  collapsed to a single scalar. Two trees differing only in rooting depth are no longer identical in the
  water balance.
  - `FDiff.betaroot_from_d95max` / `FDiff.jackson_rootdist` / `FDiff.per_tree_rootdists` — ports of the C's
    `soil/getbetaroot.c` and `lpj/getrootdist.c`, **validated to 5e-7 against the C's own emitted
    `beta_root`** across the full trait range (an oracle test, not self-consistency).
  - `FDiff.getvpd` — port of `spitfire/getvpd.c` on the `relative_humidity = false` branch this configuration
    takes; `DailyForcing` gains `humid` (specific humidity, already column 7 of every committed forcing
    fixture).
  - `TreePools` gains `d95max` and `minwscal`; `Individual` unchanged (see below); `daily_step_canopy` takes a
    `rootdists` keyword and returns `wscal_ind` / `wr_ind`.
  - The C's **order-free** first cap — no individual may draw more from a layer than its own FPC share
    (`water_stressed.c:159-161`) — via `WaterParams.per_tree_fpc_cap`. The order-*dependent* residue cap
    stays out of scope.
- **The drought and heat mortality hazards can be switched on** (ADR 0110, `WaterParams.trait_drought_mortality`,
  default off). ADR 0049 §3 set `mort_water` and `mort_temp` to zero because the emulator had neither the C's
  per-individual daily water scalar nor a per-tree drought threshold; both now exist.
  `TraitMortality.water_stress_increment` / `temp_stress_increment` port `tree/waterstress_tree.c` and
  `tree/tempstress_tree.c` one day at a time, and `FDiffFastCore` accumulates them per individual over the
  year.

- Component S: `src/trait_mortality.jl` (`module TraitMortality`) — the LPJmL-FIT per-individual tree
  mortality hazard, ported in full from `mortality_tree_ind.c:89-133`: the wood-density-dependent
  `mort_max`, the growth-efficiency logistic, age/water/temperature stress, their **additive** combination
  with per-component and total caps, and the two hard kills. This is the trait-dependent selection operator
  ADR 0046 confirmed as the lever for FIT's within-PFT wood-density warming shift. It has **no call site**:
  every committed baseline, ReferenceTest and AD path is byte-identical (guardrail 4), and the runtime
  `[deps]` stays empty (ADR 0014). ADR 0047.
- Component S: `scripts/build_mort_params_reference.py` →
  `test/testitems/references/S_pft_mortality_params.csv` — the ONE per-PFT mortality-parameter table,
  generated by expanding `$LPJROOT/par/pft_lpjmlfit.js` with the same `cpp -P` LPJmL itself pipes it
  through (`openconfig.c:28,467`). All three consumers now gate against it (the Julia table via
  `test/testitems/slow_trait_mortality_tests.jl`, `build_slow_flux_table.py::PFT_PARAMS` via a new
  import-time `gate_pft_params_against_reference()`, and the same under CI via
  `python/tests/test_mort_params_reference.py`) — no hand-maintained second copy, which is the ADR-0031
  defect class. The pytest includes a mutation test: perturbing one value must make the gate fail.
- Component S: `scripts/kcap_merge_confound_probe.jl` — measures whether the k-cap merge's dominant-parent
  trait inheritance confounds a trait-response measurement, and the rollout's constant-forcing baseline
  drift and recruitment relaxation timescale. ADR 0048.

- **`DRF.predict_quantile` gains the Meinshausen (2006) quantile-regression-forest leaf weighting, opt-in via
  `qrf = true`** (ADR 0037), threaded through `DRF.sample_copula!` and reachable from
  `scripts/eval_slow_copula.jl` with `QRF=1`. The default remains the pre-existing equal-weight
  concatenation, so every committed artifact, golden draw pair and reference baseline is bitwise unchanged.
- **Opt-in EXTENDED recruit-copula conditioning**, in lockstep on both sides: `COPULA_ENV_COLS` in
  `scripts/build_slow_runtime_table.py` appends per-cell `cell_year_feats` columns after the boundary tail,
  and `live_flux_cond_env(env)` in `src/components/slow.jl` builds the matching runtime row. Both default to
  an empty tail, which reproduces the existing 8-column conditioning exactly. Implemented as a policy
  FACTORY rather than a new field because `RecruitCopula.cond` is already pluggable (ADR 0025) — so this
  needs no struct change, no `.rcop` format change, and no change to `live_flux_cond`, and it leaves the
  count DRF's shared boundary tail (hence its `nfeat` and line M's pinned count artifact) untouched.
- `scripts/diagnose_copula_cond_ceiling.py` gains `ENV_SETS`, ranking compact candidate covariate subsets by
  what they add over the current conditioning — because adding all 28 environmental columns would grow `Xc`
  from 12.6 GB to ~57 GB and push `mtry = round(sqrt(p))` from 3-of-8 to 6-of-36, diluting the informative
  columns among correlated climate ones.

- **Component S / Phase 3A Stage 3 — the RESPONSE arm (ADR 0100).** `scripts/trait_mortality_arm_probe.jl`
  gained `MODE=response`: a 2×2 of {`trait_mortality` on, off} × {historic, ssp370 forcing}, all four rollouts
  advanced in one process at matched year indices, scored as a double difference. New extractor
  `scripts/build_hainich_response_forcing.py` pulls **real** daily forcing for both scenarios from the same
  orderA `.clm` files the two LPJmL-FIT ground-truth runs read (+2.45 K, +709 gdd5 at Hainich), behind three
  hard gates — it reproduces the committed `climbuf_hainich_boundary_w20.csv` and `hainich_forcing_2010.csv`,
  and asserts ADR 0004's flat ssp370 CO2. New committed fixture
  `test/testitems/references/S_hainich_response_boundary.csv` (per-scenario-year transient boundary + the
  per-year forcing means, so the uncommitted daily forcing is verifiable without shipping it).
- **Line S ADR block tier 2.** `docs/decisions/README.md` and `CLAUDE.md` §9 now pre-allocate a second ADR
  block per line (S 0100–0119 · M 0120–0139 · E 0140–0149 · O 0150–0159 · integrator 0160–0169); ADR 0049
  had exhausted line S's tier-1 block 0030–0049 mid-milestone.

- **`scripts/run_response_seed_ensemble.sh`** + **`scripts/summarize_response_seed_ensemble.py`** — submit
  and reduce a response ensemble. The summarizer reports mean ± SEM, `t` and a 95 % CI with `n`, derives the
  three response numbers from the four 2×2 corners (and self-checks them against the log's printed ×FIT
  values, catching the unit bug of re-scaling an already-scaled ratio), refuses to mix artifacts or initial
  conditions in one ensemble, and **excludes** rather than averages any run that violated a precondition.
- **A second precondition on any response measurement (ADR 0101 §2):** *hard kills = 0 and count-override
  (shortfall) years = 0*, alongside ADR 0048's merge dormancy. Changing only `n_init` 11.0 → 7.0 fires
  6 hard kills plus one count-override year and swings the operator's contribution from `+0.756×` to
  `−3.714×` FIT — the hazard stops redistributing a DRF-set count and the double difference measures a
  different object.
- `test/testitems/references/S_response_seed_ensemble.csv` — the 32 per-seed rows behind every number above
  (three artifacts, all four corners, both preconditions per row).
- `scripts/trait_mortality_arm_probe.jl` gains `SEED`, `DRF_ART`/`RCOP_ART`, `N_INIT`/`AGE0`/`BOUNDARY`.
  `SEED=1` on the committed demo pair reproduces ADR 0100's primary **to the digit** (`R_ctl` −5 945.79,
  `R_arm` −2 545.21, interaction +3 400.58), so the ensemble is a superset of that measurement rather than a
  different harness. Two messages that asserted the *demo* artifact's properties as if they were the
  harness's were fixed: "not inert ⇒ out-of-band extrapolation" (which mis-reported a correctly-trained
  artifact as broken — the global artifacts' boundary channel is live *and* in band, worth 1 105 gC/m³ mean
  on the historic-only pair and 3 165 gC/m³ = 1.30× FIT on the pooled one, against the demo's **exactly 0.0
  in all 8 seeds**, a harder confirmation of ADR 0100 §4 than the single run it had), and the claim that the
  boundary rows always read `Inf`.

- `scripts/build_slow_ind_parquet.py` — the missing `ind_*.csv` → parquet step, parameterized by
  `SRC`/`OUT`. Previously reachable only via the FROZEN sibling repo's `global_extract.py`, whose
  `--which` is argparse-restricted to a hard-coded three-entry dict, so a new scenario/seed could
  not be named at all. Asserts the frozen 29-column `IND_COLUMNS` header and keeps the
  load-bearing `schema_overrides` (polars infers `Wooddens` as integer from the first rows).
- `scripts/diagnose_ind_seed_independence.py` — gate a new ground-truth member before deriving
  anything from it: completion line (not SLURM state), final year, size *differs* from the sibling,
  and sampled MB windows differ at every offset. Equal size is the copy signature.
- `scripts/diagnose_ind_binary_equality.py` — per-cell bit-equality of a subset re-run against the
  global ground truth, **with a decomposition control** (single cell vs a block containing it), so
  a mismatch is attributable to the binary rather than to the MPI decomposition. Needed because the
  current `bin/lpjml` is not merely "Feb-5 source + the daily-grass-GPP patch" but also a
  RHEL8→RHEL9 toolchain rebuild.
- Recovered the ssp370 CO2 forcing that the seed1 run read and installed it durably at
  `/p/projects/waldspektrum/priesner/clustering/global/global_co2_ann_1700_2019_const_2100.txt`
  (md5 `ed5699b9c92d4d25857889f644b153db`). Its original path was inside a scripts directory that
  was repurposed for an unrelated project, so the seed1 config had become unrunnable. Identity
  established four independent ways (git blob, a filesystem snapshot whose mtime predates the run,
  reconstruction from the TRENDY v12 source, and the documented 409.63 ppm constant).

- **Component S: the emulator's BIOMASS and SIZE distributions are now validated per-cell out-of-sample**
  (ADR 0036). An opt-in `STRUCT_AXES=agb,Height` adds per-stem aboveground biomass and height to the
  `MODE=copula` table as appended diagnostic axes, so they get the same K-fold-BY-CELL OOS treatment as the
  four production recruit traits — plus new figures `12_biomass_percell` / `13_map_biomass` and
  `metrics_biomass.txt`, where predicted stand biomass is composed from the emulator's two halves
  (`OOS count x OOS per-stem agb`) and reported against LPJmL-FIT's own per-patch `sum(agb)`.
  The axes are **structurally excluded** from the serialized production `.rcop` that line M pins (ADR 0025),
  and the production axes' OOS predictions are **bit-identical** with the option on or off (gated by a
  50-cell smoke that `cmp`s them).
- `scripts/run_slow_validation_figures.sh` — the whole validation figure set for a generation (historic +
  ssp370 + pooled) plus one self-contained HTML report, as ONE SLURM job.
- `scripts/build_slow_validation_report.py` — inlines a generation's figures and `metrics*.txt` into a single
  portable HTML page (a reporter: every number is read verbatim from the metrics files).
- `scripts/run_pooled_slow_copula.sh` gained the `DEPENDENCY=afterok:<jid>` knob the other three
  orchestrators already had.

- **Trait-dependent mortality is wired into the coupled loop, opt-in (ADR 0049, Phase 3A Stage 2).**
  `FluxDrivenSlowEmulator(...; trait_mortality = true)` replaces the composition-preserving uniform
  ρ-thinning with ADR 0047's ported LPJmL-FIT per-individual hazard: each tree cohort's share of the year's
  deaths is set by its own `wooddens`/`sla`/age through `TraitMortality.mortality_hazard`, then reconciled
  with the DRF's count target by a **proportional-hazards tilt** `f_i = (1 − mort_i)^θ` — bounded in [0,1],
  order-preserving, and recovering FIT exactly at `θ = 1`. The default (`false`) does not evaluate the
  hazard, so every committed baseline, ReferenceTest and AD path is byte-identical and the runtime `[deps]`
  stays empty. New: `TraitMortDiag` + `trait_mortality_diag(s)` (the per-year mean hazard, tilt, hard-kill
  count and count-target `shortfall`), so "did the operator fire" is observable before any before/after Δ is
  believed. Requires real `fc.pft_ids` — the lookup **errors** rather than defaulting to beech.
- `test/testitems/references/S_age_wooddens_gradient.csv` — FIT's own per-PFT age–wooddens gradient, the
  ID-free acceptance target of ADR 0046 §3, as a committed fixture. Generated by
  `scripts/build_age_wooddens_gradient_reference.py` on byte-for-byte the basis that produced the ADR, which
  it **asserts** reproduces to 1 gC/m³ (`CHECK=1` re-verifies against a fresh scan). Two refinements of the
  ADR fall out: **id 2's gradient is non-monotone too** (it dips at the 40–80 yr bin despite a positive
  one-year selection differential), and id 5 has **no stems above 160 yr** at all (longevity 125) while id 2
  has none above 320 — so a gradient test must not assume seven bins per PFT.
- `scripts/trait_mortality_arm_probe.jl` — the Stage-2 arm measurement on the ADR-0048 protocol: arm and
  matched constant-forcing control re-run in the same process at matched year indices, the operator's own
  diagnostics printed first, the produced age–wooddens gradient scored against the fixture, and the
  gross-vs-net turnover diagnostic that explains the tilt distribution.

- **Component S — the recruit-trait moisture conditioning can now vary with the climate (ADR 0108).** Six of
  the fourteen numbers the recruit-trait sampler is conditioned on describe a cell's moisture *climate*, and
  they were a per-cell average of 2000-2019 weather reused unchanged for every year of every scenario — so a
  tree establishing in 2100 was conditioned on its cell's present-day moisture climate. (The sampler is not
  otherwise blind to moisture: four of the remaining eight numbers do change year by year, and measured
  against the original model the emulator's per-cell trait shift between scenarios already tracks the real one
  with a slope of 0.85 for leaf area per unit mass but only 0.16 for rooting depth — partial, and worst
  exactly where a moisture climate should matter most.) Three additions open the frozen channel, all switched
  off by default:
  - `ENV_WINDOW=W` in `scripts/build_slow_runtime_table.py` builds the tail per cell **and year** from the
    trailing-W-year tables instead of averaging it away.
  - `live_flux_cond_env_series` in `src/components/slow.jl` is the matching runtime policy, advancing the tail
    one row per simulated year in step with the existing time-varying temperature tail.
  - every training table now writes a per-row `years.i64` alongside `cells.i64`, because the year cannot be
    recovered from a finished table after the fact (measured: the per-cell-year columns are ambiguous between
    two years for ~140 of 1.35 M historic cell-years).
- `scripts/run_moisture_conditioning_arm.sh` runs the comparison as one job: one base table, the old and the
  new tail appended to it, so the two differ in those six columns and nothing else and are scored on identical
  cell folds.
- `scripts/diagnose_env_window_gate.py` is the gate: with the switch off the builder reproduces the previous
  version's output byte-for-byte, with it on only the six columns move, and every probed row carries its own
  cell-and-year values re-derived independently from the source data.

- **The reference model's own yardstick, on 51 767 of the 54 020 tree-bearing cells and both scenarios**
  (`EXECUTION_PLAN.md` rung 0, line S; ADR 0111). `scripts/build_truth_yardstick_tables.py` reduces all four
  ground-truth `ind` parquets (2.55 × 10⁹ stem-year rows) to small per-cell tables in 3.5 min;
  `scripts/diagnose_truth_yardstick.py` turns them into a stratified per-quantity noise floor on two stated
  bases, the reliability λ of the single-seed warming response for 1/2/4 seeds, an area-weighted +
  latitude-band aggregate response metric, and a re-scored deattenuated response slope for any copula table's
  out-of-sample predictions. Committed reference:
  `test/testitems/references/S_truth_yardstick_summary.csv` (272 rows).

- Component S: `scripts/diagnose_slow_response_power.py` — the first PAIRED tile-cluster bootstrap of the
  warming-response statistics (`Rr`/`Ra`/`Rb`), gated on reproducing all seven ADR-0042 arms from their
  stored predictions (achieved to ≤5e-5). Closes ADR 0042 §10 caveat 7b.
- Component S: `scripts/diagnose_wooddens_shift_decomposition.py` — decomposes LPJmL-FIT's own
  historic→ssp370 wood-density shift into PFT composition / within-PFT / interaction, and the within-PFT
  part further over age classes, plus the selection differential and the age–trait gradient.

### Changed

- **Component E: the two-layer prognostic ground-heat column is now the DEFAULT** (`SEBParams.enable_two_layer`,
  ADR 0075). This answers line M's pre-registered ask (ADR 0058 §5) and closes the two-scheme split the
  repository has been running since. Guardrail 4 is re-served by the **opt-out** — `enable_two_layer = false`
  reproduces the pre-E7 closure exactly, so every published pre-E7 number stays reproducible — and
  `lambda_g` / `tau_soil` are inert under the default. Daily step, four PLUMBER2 towers: H R² up at three of
  four sites (DE-Hai 0.035 → 0.645, AU-ASM 0.329 → 0.775, AU-Tum −0.478 → −0.362), G R² up from −4…−39 to
  +0.07…+0.72 at **all four**, Rn flat within 0.005. The pre-registered criterion **fails at AU-Rob**
  (0.069 → −0.176), the one site ADR 0073 had already excluded from scoring H (`ε_obs` −47.5 W/m²; its two
  `λ_g` targets disagree 13.6×; the fitted `λ_g = 1.0` arm fails there too) — recorded in ADR 0075 §1 rather
  than smoothed over. Stateless callers, including E's committed P2 tower gate, are unaffected **by
  construction**: `solve_seb` never reads the flag.

- `solve_seb` gained a trailing `lambda_g =` keyword defaulting to `p.lambda_g` — the default call is
  bit-for-bit the previous computation.
- `docs/src/explanation/architecture.md`: the component-E section still claimed E **reuses** Terrarium.jl's
  `SurfaceEnergyBalance`. ADR 0017 superseded that in July — E is self-contained. Corrected, with the
  Terrarium/SpeedyWeather relationship (coupling substrate, cross-read only) stated accurately.

- Nothing shipped moves. `anchor` stays opt-in and default `0`; no committed baseline, artifact or fixture
  was regenerated, and `src/` is untouched by this change.

- **Line M re-pinned the Component-S artifact to the `_t8` generation** (ADR 0023 — a deliberate, two-sided
  adoption): `drf_forest_global_pooled_w20_t8.drf` + `recruit_copula_global_pooled_w20_t8.rcop`, sha256s
  recorded in `lines/M/STATE.md`. `_t8` re-derives the population on the ADR-0035 feature bases, so a
  *coupled* run no longer inherits the retired `soilmoist`/`lai` bases; the previous `pooled_w20` pin had
  never been trained on the `semiarid_sahel` cell at all. Verified independently rather than from the
  handoff note — both halves deserialize, the meta `colnames`/`cond_cols` tails match
  `flux_feature_vector`/`live_flux_cond`, `nfeat = 8` per axis forest confirms ADR 0036's diagnostic axes
  are absent from the `.rcop`, and 5/5 cell coverage was read out of the parquet directly.

- `scripts/extract_cell_slow_init.py` emits round-trippable `repr` (`%.17g`) values instead of `%.6f`.
  These feed DRF split thresholds, and `%.6f` truncated Hainich's `eco_diag_gdd_5` 1863.695068359375 →
  1863.695068. With exact output, `M_cells.csv`'s Hainich row is bit-identical to the committed
  `drf_forest_hainich_meta.txt`'s own baked boundary/`n_init`/`age0`, which upgrades the provenance check
  from a tolerance to an exact equality.

- `DEVELOPMENT_PLAN` §5's first resilience bullet is annotated in place: its `~0.2-in-wet → ~0.75-in-dry`
  lag-1 autocorrelation gradient is **not reproduced** on this run (see the verdict below), so it cannot be
  used as an acceptance criterion as written. The second bullet (variance/SD vs climate) is the replacement.
- The live P3-vs-Phase-6 inconsistency for this gate is settled: it is Phase-6 *work* pulled forward into
  P3 / line M, because everything it needs exists now. The "Phase-6 scaffold" comments are gone.

- **Line M / ADR 0057 — the production 5-biome coupled driver runs the PATCH ENSEMBLE, not the modal
  patch, and the CI signatures were regenerated for it.** LPJmL-FIT simulates each cell as 25 replicate
  patches and every gridded output it writes is the patch-ensemble mean; ADR 0053 made that the M-line
  comparison basis and moved the oracle probes to it, but `scripts/run_coupled_biomes.jl` and the CI gate
  pinning its per-cell signatures (`biome_coupled_tests.jl` item 2) were left driving the single **modal**
  (= densest) patch. Both now run every patch independently — its own core, soil water and energy closure —
  and average the outputs. This is a deliberate baseline move under guardrail 4, in its own commit.

  **The artifact is small in energy and large in carbon** (`scripts/biome_ensemble_pin_probe.jl`, job
  1716587, both bases measured in one run, 2 yr): `mod/ens` is **1.009–1.057 on LE** but up to **1.331 on
  GPP** (boreal). LE is water- or energy-limited in all five climates and therefore buffered against canopy
  density; GPP is not. The density artifact does **not** predict the flux one — `semiarid_sahel` has the
  largest FPC artifact (1.588×) and the smallest flux artifact in the set (GPP **0.990**: extra leaf area
  buys nothing when water is the constraint) — and the ratio is horizon-dependent, flipping sign at the
  driver's 10-year horizon for the Sahel (0.821) and mediterranean (0.961). It can never be carried as a
  per-cell correction factor; re-run on the ensemble instead.

  The same job reproduced the OLD committed pins to every printed digit on the modal basis, which is what
  makes this a measured basis change rather than a re-record of whatever the new code prints. The new pins
  stay a driver-level fallback detector: minimum pairwise separation 13.2 % on LE (gate rtol 2 %) and 27.0 %
  on GPP (rtol 3 %). The ensemble costs **10.6 s** for the whole five-cell CI set, and the gate now asserts
  the Phase-4 energy closure **per patch** — 25× more closure evidence than before.

  Five gates/probes stay single-member **on purpose**, each carrying the reason at the reader (ADR 0057 §4):
  the M2 conservation/determinism gate, the rollout-stability and resilience-battery gates (member-invariant
  structural claims), `scripts/wscal_leafon_probe.jl` (so it still reproduces ADR 0051's published numbers)
  and `scripts/boreal_soilice_probe.jl` (a seasonal shape, not a level).

  Rule recorded: **a canopy basis is part of a result's reference basis (guardrail 7) — state it where the
  number is produced**, because a modal-patch number and an ensemble number are not comparable and nothing
  in the code makes the difference visible.

- The C oracle binary `/home/jamirp/lpjml56fit/bin/lpjml` was rebuilt on 2026-08-10 and now contains the
  (inert) hook. Verified numerically identical to the previous build: 138 decoded NetCDF variables plus
  `globalflux` unchanged on a matched single-cell 2000–2019 run. A copy is kept as `bin/lpjml_rung2`.

- **Line M / ADR 0058 — the coupled driver adopts line E's two-layer prognostic ground-heat column
  (ADR 0074), and it turns out to be free.** `scripts/run_coupled_biomes.jl` and `biome_coupled_tests.jl`
  items 2 and 3 now pass `SEBParams(enable_two_layer = true)` **explicitly**; the package default stays
  `false` (`src/components/energy.jl` is line E's file). This closes E's fourth integration point, which
  had superseded ADR 0073's `lambda_g = 1.0` request, which had superseded ADR 0072's refuted `stab_amp`
  one — neither of the earlier two is live.

  **Two questions, both pre-registered, both measured** (`scripts/two_layer_coupled_probe.jl`, jobs 1716625
  / 1716628; two arms differing only in the flag, driven through the real `run_coupled_cell`):

  *What moves?* LE by ≤ **2.2e−5** relative and GPP by ≤ **1.3e−4** — against a stated 1e−3 threshold — so
  it is an **H/G repartition**, not a coupled-physics change, and the LE/GPP pins ADR 0057 just
  regenerated move by ≤ 4e−5. What does move is the ground-heat term itself, and the reason is worth more
  than the pass: under a repeating forcing a soil column must take up **zero** net heat per year, and the
  default scheme — whose reference is a 30-day EWMA of *air* temperature — cannot honour that. It ran a
  **persistent +6.4 W/m² sink at `semiarid_sahel`** for ten straight years (~7 % of that cell's Rn) with
  no reservoir behind it, and the two-layer column hands that energy back to H (58.2 → 64.1 W/m²) while
  driving ⟨G⟩ → 0 by construction. `sd(G)` falls **6–7×** in every cell — the defect ADR 0073 measured
  against the towers, now confirmed inside the coupled model at five biomes and closed.

  *Does the closed column drift?* ADR 0074 §5 could only bound this on 4–16 yr tower records where
  variability and drift are entangled; under M's **strictly cyclic** 60-yr rollout they are not.
  Phase-matched drift is **−2e−4 K/yr** at both the coldest and hottest column (250× inside the stated
  0.05 K/yr bound), decaying, equilibrated within a decade, with the 60-yr AGB ratio unchanged between
  arms and energy closing at 2.8e−14.

  **A metric bug worth carrying:** the first drift number was `(T2[end] − T2[end−9])/9` = **0.222 K/yr**,
  ~1000× the truth, because the committed forcing is a **10-year cycle** and those two years sit at
  different phases of it — the same trap that makes a raw `T1(y1)` vs `T1(y60)` look like a 5.8 K drift.
  **Under a cyclic forcing, compare only years an integer number of cycles apart.** The per-cycle series
  printed beside the summary is what caught it.

  ADR 0058 §4 lists exhaustively which gates deliberately stay on the default scheme (those scored against
  ADR 0055's fixtures, and every E-owned gate) and §5 hands the **default flip** back to line E with a
  pre-registered pass condition, so an opt-in whose default is now known to be worse cannot quietly stall.

- **Line M / ADR 0059 — the C-faithful leaf-on water scalar is now the DEFAULT, and it is worth 3.5× of the
  Sahel's carbon.** `WaterParams.wscal_leafon` flips to `true`; guardrail 4 is re-served by the **opt-out**
  (`wscal_leafon = false` reproduces the pre-ADR-0051 expression exactly, and both arms run on every CI
  pass). This closes the flip line S GO'd explicitly and that CLAUDE.md's guardrail-4 corollary names by
  name as "a defect on a timer" — it shipped opt-in while ADR 0051 measured it, then sat off for a week
  with each line recording the flip as the other's to schedule.

  **A full CI-faithful suite with only the default flipped failed 3 assertions out of 111,237** — the
  opt-in guarantee itself, and `semiarid_sahel`'s two pinned signatures. Nothing else in the tree moves.
  Four of five cells shift by ≤ 1.2 %; the Sahel's GPP goes **0.386 → 1.367 gC/m²/day (+254 %)**, which
  against the C's own tree GPP of 1.513 is **0.26× → 0.90×**. The pre-flip expression scored every leaf-off
  day as fully water-stressed, and that number drives the leaf:root allocation `lmtorm` — so the cell with
  the most leaf-off days starved its own leaf pool. **The honest cost is in the same cell:** its ET goes
  from 1.19× to 1.26× the C's, i.e. the flip trades a large carbon gain for a ~6 % worse ET overshoot
  (ADR 0053's open item (a), unchanged in kind).

  **Why this was worth doing beyond faithfulness:** until now the gate pinned a configuration *no published
  F-vs-C comparison ever ran* — every oracle probe on this line passes `wscal_leafon = true` explicitly, so
  the default arm was the one nobody scored. A default and a measurement basis that disagree is the
  train/inference-shift hazard in its cheapest form, and it survived precisely because both were
  individually documented. Line S's independent endorsement is on the conditioning side: Hainich's annual
  `water_stress` goes 0.3050 → 0.0034 against a C truth of 0.0014 and a trained band of [0, 0.04315].

  Also aligned with line E's parallel default flip (ADR 0075): the pin probe and the coupled gate no longer
  hardcode a ground-heat flag where they meant "the package default", and the stale "the default is off"
  comments are corrected. A control arm that hardcodes a flag stops being a control the moment the default
  moves — which is exactly what ADR 0075 §4 paid for.

  `biome_coupled_tests.jl` item 2's pinned LE/GPP are regenerated for the new defaults
  (`scripts/biome_ensemble_pin_probe.jl`, job 1718307), in their own commit.

- **The ONLINE configuration is now ESM-first and validated against OBSERVATIONS, not LPJmL-FIT
  ([ADR 0082](docs/decisions/0082-online-esm-first-ownership-and-validation.md), owner decision).** Two
  explicit configurations replace one compromised model. **OFFLINE** is unchanged and keeps guardrail 3 (the C
  binary is the oracle). **ONLINE** hands skin temperature, the surface energy balance and the soil
  water/thermal column to **Terrarium**, and is scored against PLUMBER2/FLUXNET fluxes and observed
  LAI/biomass/tree-cover — so a divergence from LPJmL-FIT online is no longer automatically a bug.
  Conservation (guardrail 2) binds both. Our contribution online is **vegetation**: Component S, FIT
  photosynthesis behind `AbstractPhotosynthesis`, and FIT's water-limited ET behind the pluggable
  **`AbstractEvapotranspiration`** slot. The deciding evidence for handing over the SEB: Terrarium computes LE
  *through* the ET scheme **inside** its skin-temperature solve and then recomputes ET at the converged
  T_skin (`surface_energy_balance.jl:128/149-151`), so LE and T_skin are mutually consistent — whereas
  Component E takes LE from F evaluated at a *different* temperature and makes H the residual (ADR 0017's
  documented "no privileged residual" exception). Offline that is a caveat; online it is a defect, because
  SpeedyWeather computes its own humidity flux. We also inherit two-phase heat conduction with freeze curves,
  which we do not have and which is not optional for boreal/permafrost land. **`ClimBuf`** cold-starts from a
  ~20–30 yr SpeedyWeather-only spin-up on **its own** climate; obsclim seeding is rejected because
  SpeedyWeather's climate is not Earth's, which would bias the establishment gate for a full trailing window.
  ADR 0017's scope narrows to offline **without** being superseded — Component E remains the offline closure
  and an independent cross-check on Terrarium's SEB.
- **`soilmoist` must map to the layer-mean of Terrarium's `plant_available_water`, not
  `saturation_water_ice`.** The latter is normalized by **porosity** (θ/θ_sat) while LPJmL's `w` is a fraction
  of **water-holding capacity**, so substituting it is a *definitional* mismatch rather than a distribution
  shift; `FieldCapacityLimitedPAW` computes `min((θw−θwp)/(θfc−θwp), 1)`, which is exactly LPJmL's semantics.
  Training reference measured for comparison (historic, 1 348 400 cell-years): `soilmoist` min 0.017,
  q50 0.464, mean 0.508. Re-validating — and if needed retraining — Component S on Terrarium-derived
  `soilmoist` is an **integration point with line S** (a version-bumped online artifact, never an in-place
  mutation), and is a hard gate on online demography.

- `scripts/online_coupling/diagnose_soilmoist_shift.jl` now runs on the prescribed soil, evaluates
  plant-available water with Terrarium's own `compute_plant_available_water` (instead of a hand-rolled
  re-derivation that ignored the organic fraction), and reports the ADR 0082 §4 `soilmoist` comparison
  over land columns only, as both an unweighted layer mean and a thickness-weighted top-2 m mean.

- **The licensing question is CLOSED; reuse is authorized; citation is the requirement
  ([ADR 0081](docs/decisions/0081-owner-closes-licensing-reuse-authorized.md)).** The owner is a member of
  **both** upstream groups — the **LPJmL-FIT** group and **TUM-PIK-ESM**, which hosts SpeedyWeather.jl,
  Terrarium.jl and LPJmL-hybrid-photosynthesis — the fact missing from every prior analysis. So those models
  are reused freely, with no licence analysis, licence decision or upstream re-audit needed, including for P4
  online coupling. `LICENSE` is no longer a blocker or a tracked TODO. **The one standing obligation is
  transparent citation** across four surfaces kept in agreement: the register (now
  `docs/third_party_licensing.md` — *reuse + citation*, reframed from a licence gate), `CITATION.cff`,
  `docs/src/refs.bib`, and the header of every source file with derived content — stated *accurately*, neither
  overstated nor omitted. The `dependency-license-gate` skill is replaced by **`reuse-citation`**, and the
  licensing sections of `CLAUDE.md`, `MEMORY.md` and `lines/O/STATE.md` collapse to "closed, cite, move on" so
  no future session relitigates it. ADR 0080 is retained for its verified upstream register and its
  depend-don't-vendor hygiene, with only its §4 owner-action checklist superseded. **Not reopened, and not
  licence caveats:** NeuralCrop.jl stays method-only (CC-BY-NC, a different author outside both groups) and
  runtime `[deps]` stays empty (ADR 0014 — a *technical* constraint from the GitHub-egress-free compute nodes,
  so Terrarium/SpeedyWeather still enter as `[weakdeps]` + an extension).

- **Amendment, same day — NeuralCrop.jl is usable too.** ADR 0081 first read CC-BY-NC as "no code"; the owner
  corrected it and is right: **NonCommercial permits non-commercial use, and this project is research use.**
  So NeuralCrop.jl's code may be reused, cited (arXiv:2512.20177). Only a future commercial release would
  need a rethink. The one genuine exception is **LPJ_resilience** — and not for NonCommercial reasons: it
  carries no licence at all, so its published metrics are implemented from the paper.

- **Component S — the level anchor's pre-registered flip criterion was scored on the wrong quantity, and is
  re-specified** (ADR 0104). Evaluated verbatim on the 5-cell coupled oracle the criterion FAILS, reproduced
  independently by lines S and M to the same digits. It scores the count model's *prediction*, which the
  anchor never writes; the anchor multiplies the roster density. On the corrected yardstick — the stand's
  density against the C's per-patch mean ÷ `patch_area` — the anchor improves **all five cells at all three
  settings**, mean `|ln(density/truth)|` **0.679 → 0.478 / 0.361 / 0.329** for `a` = 0.1 / 0.25 / 0.5.
  Revised recommendation **`anchor = 0.25`** (was 0.1). The default stays **off**: a modal-patch
  initialisation confound must be cleared on the patch-ensemble driver first.

- **Component-S trait gate (`scripts/noise_floor_vs_emulator.py`) is now basis-clean and
  attenuation-corrected (ADR 0030).** The seed1-vs-seed2 per-cell trait floor is measured on the emulator's
  OWN stem population (two `MODE=copula` builds differing only in `SEED`), gated by a `seed1-basis ≥ 0.99`
  cross-check against an independent parquet re-derivation (now **1.000** on all four axes, was
  0.973/0.488/0.761/0.092). `floor_r` is a realization-vs-realization correlation, so the reported ceiling is
  `√(rel_P·rel_Y)` from each side's split-half reliability, and the headline metric is `(GAP, r_center)` plus
  the between-cell dispersion ratio. Exact per-axis headroom (ids-1..5 population): **Wooddens +0.226 ·
  minwscal +0.153 · SLA +0.115 · D95max +0.102**.
- `scripts/sbatch_python.sh` forwards the full env-knob set (`MODE`, `SCENARIO`, `BOUNDARY_WINDOW`,
  `STEM_CAP`, `SOIL_TBL_PATH`, `LAI_TBL_PATH`, …). Previously an unlisted knob passed as a command prefix
  reached the wrapper but **not** the job, so e.g. `MODE=copula` silently built a *count* table.

- **ADR 0040 rejects the decision rule proposed in ADR 0038** for the address-vs-response question. The
  fold-mode-matched address null under `block(15°,5°)` is Wooddens **0.140/0.210**, not the `r≈0.80` that
  ADR 0038 named — that figure is a pure address's skill under `mod(hash(cell),k)` folds, so using it as a
  blocked-fold threshold is a reference-basis error (guardrail 7) that would have declared a strong response
  an address. The corrected rule is pre-registered before any forest result is read.
- **A second promotion gate is added: the warming Δ-response.** `emu_r` is a level statistic and
  `sd(Δobs)/sd(level)` is only 0.198–0.306, so the existing gate is 3–5× more sensitive to spatial
  interpolation than to the transient response a coupled run depends on. Measured from existing predictions,
  the shipped env-conditioned artifact damps the mean Wooddens warming shift by **37 %** (tile-cluster
  bootstrap CI excludes zero) and both arms capture only 24–62 % of the transient pattern against a
  0.87–0.96 split-half ceiling.
- ADR 0038's saturation fit and its "0.889 needs ~1052× the table" extrapolation are re-labelled
  **unresolved**: they rest on +0.002/+0.003 `emu_r` increments against a spatial-sampling sd of order 0.01,
  with no seed replication anywhere in the ladder.

- **ADR 0042 adjudicates ADR 0040's pre-registered address-vs-response rule on the completed seven-arm forest
  matrix: RESPONSE — the six env conditioning columns are not merely a spatial address**, and the verdict is
  **final**: the second colouring's flip thresholds were recorded in the ADR *before* the deciding rung landed,
  and the two colourings' blocked deltas then agreed to 0.0024 against a 0.0157 tolerance, so the
  "NOT RESOLVABLE" clause does not fire and clause 1 is met on both colourings on all four axes. Wooddens `Δ_blocked = +0.0315` [+0.0011, +0.0633], clearing the pre-registered bar
  `0.5·Δ_hash = +0.0201`, while the pure-position control collapses 0.1868 below the treatment and 0.1553
  below no tail at all. The frozen 1-NN surrogate screen predicted ~86 % retention and the forests delivered
  78/119/137 % on the three axes with a resolvable delta.
- The salt replicate also validated the experimental design, which is the most transferable result here:
  re-colouring the spatial blocks moved the **single-arm** blocked `emu_r` by +0.0136 (half the delta under
  test) but moved the **paired delta** by only +0.0024, because the colouring effect is common to both arms and
  cancels in the difference. A blocked *level* is therefore colouring-sensitive and must not be quoted alone or
  across colourings; a blocked *paired delta* at a shared colouring is robust. Build blocked comparisons as
  paired deltas.
- **ADR 0040 §4's attribution of the transient damping to the env tail is refuted**, using the matched `p8`
  arm that ADR itself asked for: the ncond-8 baseline damps the Wooddens warming shift 39.9 % on its own. Its
  §5 promotion gate is therefore simultaneously *met* and *mis-specified* — passable by a change that degrades
  the transient — and is re-specified on `Rb` **and** `Rr` **and** `|Ra − 1|` at both fold modes. Under the
  re-specified gate the tail fails: `Rr` (transient pattern) flips sign with fold design, +0.0395 at hash to
  −0.0305 at blocked. The two gates dissociate — the level delta survives blocking, the transient one does not.
- Line M's re-pin refusal **stands on new grounds** (the old ones are refuted); the request to fix
  `extract_cell_slow_init.py`'s `cond_cols[-4:]` check to the positional `cond_cols[4:8]` is unchanged.
- Corrects two ADR 0040 statements: `eco_diag_gdd_5`/`tas_cold_month` **are** time- and scenario-varying on the
  `pooled_w20` tables the forests read (per-cell constants only in `cell_year_feats.parquet`), and the single
  "spatial-sampling sd of order 0.01" is superseded by a measured 0.004–0.006 (hash) / 0.012–0.016 (blocked).

- ADR 0031's global re-derivation runs on the `t7` artifact generation
  (`…_t7.drf` / `…_t7.rcop`, `slow_{count,copula}_*_t7/`). The pre-0031 artifacts are retained unchanged; every
  global Component-S fidelity number published before this is on the truncated population (ids 1–5,
  45 009 cells) and is superseded by the re-measured `t7` numbers, not silently restated.

- **Milestone S2's gate is MET for the first time, and ADR 0037's thesis is superseded (ADR 0038).** The
  12-rung QRF × capacity matrix completed. The ESTIMATOR lever is the larger one on `emu_r` (+0.050 vs
  +0.037) but **saturates at Wooddens 0.867** — fitted asymptote 0.8696 (half-life 1.82 doublings), 0.0194 short of
  0.889 at infinite subsample, and reaching the threshold at the terminal marginal rate would need 14.7 more
  doublings = 1052× the entire 197 721 867-row table — so it cannot close the gap at any
  artifact size. `ncond` 8→14 at **fixed** 6×2M/d22/QRF=1 delivers **+0.037 `emu_r` and +0.0966 `sd_ratio`**,
  the larger lever on criterion 2 (the axis that was actually failing), and carries both criteria across.
  **S2's premise — "expand the conditioning" — is vindicated, not refuted:** the estimator had to be fixed
  *before* the conditioning could pay, because at 50k subsample there is ~0.93 rows/cell and six extra
  columns have no resolution in which to express themselves. ADR 0037's "second-order lever, ~4× smaller" is
  wrong by ~4× in the opposite direction, and its 0.916 was a per-cell **LightGBM upper bound** that did not
  transfer to the DRF.
  Shipped config `env-qrf-b6x2M` (6 trees × 2M subsample, `max_depth` 22, `min_leaf` 20,
  `QRF=1`, `ncond` 14): Wooddens `emu_r` **0.901** (58.0 % of the GAP closed, and ≥56.7 % under all five
  defensible conventions), `sd_ratio` **0.8541**, pooled KS improving on **all four** axes
  (.0032/.0024/.0019/.0013), `r_center` gaining on all four. The comparison is PAIRED (folds and quantile
  levels depend only on cell id / row index) and its basis is identical at the **inode** level.
  Artifact `recruit_copula_global_historic_t9.rcop`: 507 985 666 B, **load 6.77 s = 71.6 MiB/s measured**
  (an earlier "~12 s at 42 MB/s" was never measured), byte-reproducible across independent re-runs. `b6x8M`
  rejected: +0.002 `emu_r` for 4× the bytes and worse pooled KS on all four axes.
- **The `.rcop` size coefficient is 10.58**, not 10.7 (`bytes ≈ C·ntrees·subsample·naxes`; t8 gives 10.66).
- **The subsample lever is exhausted past ~2M rows/tree at BOTH conditioning widths** (+0.003 at `ncond` 8,
  +0.002 at 14); the *level* it plateaus at is set by the conditioning, not by capacity. The "tree count is
  inert" trio (12/24/40 × 500k) is a different experiment and is **not** evidence of subsample saturation.
- **QRF's payoff shrinks as capacity grows, and the mechanism is measured**: the pooled-default max-leaf
  weight share is median 11.2 % at t8's 60 trees = 6.7× QRF's `1/T`, but median 48.9 % at t9's 6 trees =
  only 2.9× — so what QRF corrects is largely absent at 6 trees (+0.013 `emu_r` at 40 trees/50k vs +0.002 at
  6 trees/2M, where it also *costs* 0.013 of dispersion).

- **Milestone S2 is re-scoped on measurement: the trait GAP is dominated by ESTIMATOR CAPACITY, not by a
  missing covariate.** On `t8` historic (52 165 cells) the estimator share of the GAP is
  +0.080/+0.102/+0.089/+0.032 (SLA/Wooddens/D95max/minwscal) against a new-covariate share of
  +0.011/+0.025/+0.042/+0.004. Wooddens reaches `r` 0.916 and `sd_ratio` 0.896 from the *existing* eight
  conditioning columns — both already past the S2 gate targets (0.889 / 0.75). Mechanism, measured on the
  production artifact: `SUBSAMPLE=50000` against ~158M training rows yields **1063 leaves per tree for 54 020
  cells**, so each leaf hands ~51 cells one identical conditional distribution, and `DRF.predict_quantile`
  pools leaf values across trees into a mixture that reproduces the global marginal (pooled `nqrmse` 0.013,
  KS 0.0065) while leaving the per-cell conditional under-resolved (`sd(pred)/sd(Y1)` 0.678, slope
  `Y1~pred` 1.20). Pooled-marginal metrics are structurally blind to this. The conditioning expansion remains
  a real but secondary, separately-attributable follow-up, because the boundary tail carries no moisture or
  precipitation climatology while FIT's establishment gates are temperature *and* moisture.

- **Line M's "the count recursion is unanchored" (ADR 0054) is answered, and it decomposes into THREE
  defects with three owners
  ([ADR 0102](docs/decisions/0102-the-count-recursion-has-no-level-anchor.md)).** M measured that a
  free-running coupled rollout integrates a ~5 %/yr one-step count bias into +36–81 % over ten years, that
  teacher-forcing `s.n_prev` onto the C truth removes **59–72 %** of the coupled count error, and correctly
  refused to fix it inside `src/components/slow.jl` (line S's exclusive path, ADR 0029). Measured on the S
  side at Hainich over 150 constant-forcing years:
  - **(A) Exposure bias** — the training `n_prev` is the C's own previous `n_living` (a `shift(1)` of the
    truth) while the runtime feeds the DRF its own output. Real, but **training-side**: it needs scheduled
    sampling or dropping `n_prev` from the feature set, i.e. a global retrain. Not closable from `slow.jl`.
  - **(B) State incoherence** — `slow.jl:1026` clamps `ρ` but `:1110` assigns the **unclamped** `target` to
    `n_prev`, so a clamp-binding year desynchronises the AR state from the roster permanently. This was the
    leading hypothesis and it is **MEASURED EMPTY**: the clamp binds **0 of 150 years** and the roster
    tracks the `ρ` it was handed to `1.5e-13`. Closed; do not spend time here.
  - **(C) No level anchor — the dominant defect, and new.** `ρ` is a unit-free ratio and the roster is
    advanced multiplicatively, `D_T = D_0·Πρ_t`, so the count DRF's **absolute** skill (OOS R² 0.982) is
    used only through year-on-year ratios and its level is discarded by construction. Perturb the initial
    stand density by **4×** and the terminal densities still differ by **4.21×** after **300** identical-forcing
    years — **retention 1.036**, and the horizon sweep shows it converging to a **non-zero asymptote of
    ≈1.04** (peaking at 1.40 around year 25, then flat from year 150 to year 300) rather than decaying to 0.
    There is no restoring force — not a weak one, none. The dissociation is the finding: an `n_init` sweep
    shows the **AR state** converging (terminal spread 6.7 %, retention **0.092**, four of five seeds
    landing on an identical 6.7529) while the **physical stand** those same runs carry retains **60.2 %** of
    its spread. So the constructor docstring's "self-corrected by the `max_*` clamp thereafter" is true of
    the AR state and **false of the stand**.
  - **This completes M's own same-day decomposition (`9ad8721b`)** rather than correcting it. M split the
    +36–81 % into a recursion factor **×1.26–1.53** and a **year-1 level offset ×1.05–1.12**. What is added
    here is the level term's *fate*: teacher forcing repairs the **ratio** each year and nothing repairs the
    **level**, so that offset — and any level error acquired later — is permanent. It is visible in M's own
    numbers: the forced boreal arm flattens to **1.12–1.17**, flat but still displaced by the 1.12 it
    started with. An initialisation artifact that never decays is a free parameter, not an artifact.
  - **Consequence for the queue:** milestone **S2 (recruit conditioning) is no longer top priority**. An
    unanchored level compounds without bound and no conditioning skill can correct it, because the channel
    that would carry the correction is discarded upstream. The fix is **specified but deliberately not
    landed** — it needs the count↔density conversion (patch area) at the S↔F seam, i.e. an `interface.jl`
    addition (line M's) plus a `slow.jl` change (S's), and it moves every committed coupled baseline.
  - **ADR 0101 §5 is re-read:** the 4.5×-FIT swing from `n_init` 11.0 → 7.0 is not an artifact quirk, it is
    this recursion property. That promotes S→M integration point #2 from a provenance defect to a
    correctness one.

- **`docs/component_s_public_report.tex` — four corrections, three of them substantive.**
  - The warming-response damping is **39.9 %**, not ≈ 37 %, and the deficit is **971.5** internal units, not
    892, giving **+1461** rather than +1541. The 37 %/−892 pair was arm **B** (`p14env-hash`), the *refused*
    env arm, quoted as if it were the deployed configuration (ADR 0044 §Consequences).
  - The `Rr` **ceiling is stated on the patch-year reliability basis** (Wooddens **0.9543**, all four axes
    0.94–0.97), replacing the superseded stem-parity ceiling (0.9201, range 0.87–0.96) and the flattering
    percentages computed against it. The basis is now named in the text.
  - **New: the defect is placement, not shrinkage** — dispersion ratio **1.034** against a target of 1 while
    the pattern captures 39 % of ceiling, i.e. right-sized shifts in the wrong cells. Any lever justified by
    "fixing attenuation" is aimed at a defect that is not present.
  - **Recursive stability moves from "not yet tested — no evidence either way" to "not established
    (measured, negative)"**, and the roadmap is **reordered**: anchoring the recursion becomes item 1, ahead
    of the warming-response gap, per ADR 0102. The claim that the trait-conditioning work "is the single
    highest-value piece of remaining work" is retired.
  - A new §`sec:traitmort` reports Phase 3A honestly: the operator changes the **level** of community wood
    density by `+7 041 ± 334` (t = 21) and reproduces FIT's age–wood-density signature, while its
    contribution to the warming **response** is `+0.26 [−0.38, +0.90]` × the FIT shift — not distinguishable
    from zero. The report's standing claim that mortality is trait-blind is scoped to the *deployed*
    configuration.

- CLAUDE.md §3 gains two C-oracle gotchas: a chained child that hardcodes a parent's job id is not
  resubmit-safe (and an empty log is indistinguishable from an unfinished run unless called out), and a
  file-level `cmp` on a NetCDF output is the wrong equality test because LPJmL writes a timestamped
  `history` attribute.
- Reclaimed ~181 GB by deleting the cross-build gate's redundant `ind_2020_2100.csv`, retained only until
  its bit-identity to the seed1 original was proven.

- Component S — the level anchor's default question is **closed**: the flip criterion re-registered in
  ADR 0104 §7 was run on the 25-patch ensemble and **fails at all three settings**, so `anchor` stays
  opt-in and default `0` (ADR 0105). Most of the level defect it was built for was the modal-patch
  initialisation the earlier measurement started from: free-running terminal density/truth across the five
  biome cells is 1.04–1.38× (and 0.52× at the Sahel) on the ensemble, against 1.55–3.01× on the modal
  patch. No code, artifact, baseline or default moved.

- **Measured, and documented as debt: 4 of 15 runtime feature columns are still outside the trained band
  (ADR 0034), from three separate causes** — `water_stress` 0.323–0.331 vs [0, 0.043] (an **F_diff-vs-C**
  difference; the F core is line M's), `soilmoist` 0.792–0.999 vs [0.842, 0.867] (a year-end instantaneous
  value against an annual-mean training basis), and `lai`/`fpc` (one patch against the C's cell-mean
  `LAI_STAND`). So the demo emulator is conditioned consistently on 11 of 15 columns, **not** fully
  runtime-consistent, and the Gate-3 improvement above must not be re-cited as such. The set is pinned by the
  new assertion, so a *new* column drifting out fails CI. Fixing the two S-side causes is milestone **S1d**,
  which precedes S2; `water_stress` is raised to line M.

- `make_recruit_to_pools` writes the sampled `D95max` and `minwscal` into each recruit's `TreePools` (located
  by axis name; an artifact lacking those axes still loads and leaves both unset ⇒ unchanged behaviour).
  `_merge_pair!`, `_with_nind` and `grow_individual` carry both traits — without that, every cohort merge,
  density change or growth step would silently reset them.

- Component S: the k-cap merge is measured as **dormant, not harmless** (ADR 0048). At the default
  `k_cap = max(2K, 40)` it fires **0 times in 150 years** at Hainich — establishment fires in only 12–14 of
  149 years, so the roster never doubles — which makes the obvious default-vs-disabled null a
  non-measurement. Forced to fire at `k_cap = 20` it moves the community wood-density mean by up to
  **3.1–5.1× the FIT warming shift**. Stage 2 is unblocked without a merge fix, with an explicit re-check
  trigger for any config that tightens the cap or scales the roster.
- Component S: a new mandatory control for every Phase-3A response arm — the rollout's **constant-forcing**
  community wood density drifts **1.34× the FIT warming shift in the OPPOSITE direction, settling in ~52
  years** (production copula-on config, no climate signal present). Any response arm must be differenced
  against a matched constant-forcing control re-run in the same generation, and measured past the
  transient. Recruitment dilution gives `τ ≈ 94 yr`, an upper bound on how fast any recruit-mediated fix
  can act. ADR 0048.

- `scripts/trait_mortality_arm_probe.jl`: the response headline is a **window mean** (`SCORE_WINDOW`, default
  the last 20 yr) rather than a terminal-year read — with real interannual forcing the year-to-year
  interaction swings by more than the signal — and `K_CAP` is exposed so the k-cap merge can be held dormant.
  `MODE=stage2` is unchanged and reproduces every ADR-0049 headline number (job 1700483).

- **The Phase-3A response arm is now a SEED ENSEMBLE, and ADR 0100's response contribution does not survive
  it ([ADR 0101](docs/decisions/0101-the-response-arm-needs-a-seed-ensemble-and-the-baseline-defect-was-cell-scope.md)).**
  ADR 0100 handed forward a falsifiable prediction — re-run its 2×2 against the global `pooled_w20`
  artifacts and `|R_ctl|` should shrink or flip. It does. But running it also exposed that the number being
  predicted was never resolvable from one run:
  - **`SEED` was hard-coded to 1.** Exposed as a knob, the double difference has a **seed sd of 0.67–1.74×
    the FIT reference shift — the same size as the effect.** Holding the seed common across the four corners
    does *not* pair them (`sd(Δ_ssp)` 2 419 ≡ `sd(interaction)` 2 452 gC/m³; the rosters diverge after
    year 1), so replication is the only variance lever: ~8 seeds resolve a 1×-FIT effect, **~115** the 0.26×
    actually measured.
  - **The operator's contribution to the warming RESPONSE is indistinguishable from zero on both global
    artifacts** — `+0.048 [−0.380, +0.476]` (historic-only, n = 12) and `+0.263 [−0.377, +0.903]`
    (`pooled_w20_t8`, the pair line M pins, n = 12). **Both CIs exclude ADR 0100's `+1.40×`**, and even on
    ADR 0100's own demo artifact the 8-seed CI `[−0.100, +2.812]` straddles zero. Its `+1.398` was a *fair*
    draw — 0.03 from that artifact's mean — with ~6× overstated precision. **Phase 3A's Stage-3 response
    claim is withdrawn; `+1.40× FIT` must not be quoted.**
  - **ADR 0049's LEVEL claim is confirmed and strengthened:** `+6 718 ± 286` / `+7 041 ± 334` /
    `+8 959 ± 862` gC/m³ across the three artifacts, `t` = 10.4–23.5. Replication makes this one *stronger*.
  - **ADR 0100's headline finding was a single-cell FIXTURE artefact, and the sign reverses on a global
    artifact.** `R_ctl` = `−1.234 [−2.058, −0.411]` on the demo pair (significant, so ADR 0100 §2 was real
    *for its artifact*) but **`+0.417 [+0.050, +0.784]` — FIT's own sign — on the global historic-only pair**,
    and `−0.000 ± 0.367` on the pooled one. The deployment defect is milder and different: *no* warming
    response where FIT has +1×, which is a conditioning-set question (milestone S2).
  - **The attribution was wrong: cell scope, not scenario coverage.** demo → global-historic with the
    scenario held fixed gives `ΔR_ctl = +1.651 ± 0.386` (`t` = +4.28); global-historic → pooled with the
    scope held fixed gives `−0.417 ± 0.403` (`t` = −1.03). The mechanism is in the metadata: cross-**cell**
    pooling widens the `soilmoist` trained band **4.79×** (0.209 → 1.002) while adding the entire ssp370
    scenario widens it **−0.04 %**. ⇒ **an excursion diagnostic localises a channel; it does not identify
    which axis of the training design to change.** ADR 0100 §5's measurement was right and its causal
    reading was not.

- **Component S (S1d, ADR 0035): `soilmoist` and `lai` are on ONE basis in the training table and the
  coupled runtime — and neither fix is the one ADR 0034 predicted.**
  - `soilmoist` was not a time-aggregation mismatch but the **wrong variable**: the training column reduced
    the C `swc` output (total water over SATURATION capacity, `update_daily.c:411`) while the runtime fed
    `state.w` (plant-available water as a fraction of WHC). `swc` cannot be inverted back — LPJmL-FIT emits
    no `wsats`/`wpwps`. Both sides now use the root-zone (`forrootmoist`, top 1 m), `whcs`-weighted mean of
    `w` at year end: new deriver `scripts/build_rootmoist_soilmoist_feature.py` (from `d_rootmoist.nc` +
    `whc_nat.nc`) and new `LPJmLFITEmulator.root_zone_soilmoist` in `src/components/slow.jl`, which all
    three `slow.jl` call sites use. This finally matches `FToS.soilmoist`'s own documented definition.
  - `lai` is now the **per-patch** stand LAI, reconstructed in-row from the emitted `LAI` + `fpc_ind`
    (`build_slow_runtime_table.py::patch_stand_lai_expr`), replacing the C `LAI_STAND` cell-mean join that
    was broadcast onto per-patch rows. Contrary to the previously documented limitation, this IS
    reconstructable from the 29-column `ind` output; the new
    `scripts/diagnose_patch_lai_reconstruction.py` validates it against the C's own crown allometry
    (median relative error 1.8e-8 over 22 498 stems in five biomes). `growth_eff`'s divisor inherits the
    fix, so its numerator and denominator are finally the same patch and the same stem population.
- `flux_feature_vector` takes the fast core's `SoilColumn` as a sixth positional argument (it had no caller
  outside `slow.jl`). The frozen S→M contract — feature-column ORDER, `live_flux_cond`, the `.drf`/`.rcop`
  format, `FluxDrivenSlowEmulator` kwargs — is unchanged.
- Committed Hainich demo artifacts `drf_forest_hainich.drf` (+ meta) and `recruit_copula_hainich.rcop`
  (+ meta) regenerated **together from one table build**; the two oracle reference CSVs are unchanged.
- `scripts/build_swc_soilmoist_feature.py` and `scripts/build_laistand_lai_feature.py` marked SUPERSEDED
  (retained so the pre-0035 tables and artifacts stay reproducible). The new `soilmoist` table is written
  to a new `_ye` path; no existing artifact is overwritten in place.

- **The GLOBAL Component-S tables and artifacts are re-derived as generation `t8`** on the ADR-0035 feature
  bases (`soilmoist` = root-zone year-end plant-available fraction of WHC; `lai` = the per-patch
  reconstruction), for historic, SSP370 and the pooled multi-regime pair. `_t7` is untouched; line M re-pins
  deliberately.
- `noise_floor_vs_emulator.py` reports the ADR-0030 floor / ceiling / dispersion arithmetic for the structure
  axes too, tagged `[diag]` and strictly outside the gate's verdict and exit code.
- Figures 09-11 size their panel grid from the axis count instead of a hard-coded 2x2 (which would have
  silently dropped any axis past the fourth), and switch to log axes for heavy-tailed axes.

- `_merge_pair!` / `_apply_kcap_merge!` / `_commit_membership!` take an optional `counters` keyword carrying
  the per-cohort `bm_inc_counter` roster (inherited from the dominant parent on a merge, committed atomically
  with `pools`/`ages`/`tmpls`/`pft_ids`). Defaulted to `nothing`, so every pre-0049 call is unchanged.

- `scripts/pool_slow_tables.py` now refuses to pool two scenarios whose conditioning tails were built on
  different time bases — a static half and a time-varying half would fabricate part of the scenario contrast —
  and carries the per-row year through to the pooled table.

- **The `<2 stems/patch` tolerances quoted in an earlier record (31.6 % counts / 42.7 % carbon) are not exactly
  reproducible** — the stated-basis values are 27.3 % / 37.8 %. The year, dead stems and grass inclusion were
  each tested and ruled out as the cause; the remainder is an undocumented difference in that record's
  per-cell estimator. The new floor states its population and regenerates with one command.

- **The response panel, corrected on one self-consistent basis:** SLA over-responds by 25–35 % (previously
  read as "already correct"), Wooddens is the worst axis at 0.66–0.69, D95max is **not** the worst
  (0.72–0.85 — its small raw slope was mostly attenuation, its reliability being 0.198), minwscal is correct
  at 1.05. "Four broken axes" and "two broken axes at 0.63/0.51" are both retired.
- **The tree-count warming response is measured as faithful** — per-cell deattenuated slope 1.01, validated by
  a 0.9948 cross-check between two independent code paths — so "the response is indistinguishable from zero"
  is not true of counts; the response error lives in the trait axes. Counts are the mirror image of wood
  density: counts get the per-cell pattern right and under-shoot the global total (0.69×), wood density gets
  the total right (1.06×) and the pattern wrong (0.66).
- **The aggregate (area-weighted, latitude-banded) response is now the primary response statistic** and the
  per-cell map a reported secondary: area-weighted signal-to-noise is 25–489 against a per-cell 0.5–3.1.
- **Banding the response ratio found four wrong-signed regional responses that no earlier statistic could
  see** — tree counts in the tropics, specific leaf area in the subtropics and mid-latitudes, drought
  tolerance in the boreal zone — so the count shortfall is not a uniform 31 % under-response but a correct
  mid-latitude and boreal response plus a tropical response of the wrong sign. Ratios whose denominator is
  not determined by the reference data now print `n/d` instead of a number, which caught and retracted a
  draft claim of this work's own ("14 % of the height response") before it was published.

- Component S: the reliability ceiling used by every "% of ceiling" claim is corrected. Patch-year-parity
  split-halves (reconstructed exactly from runs of identical broadcast `Xc` values, needing no `Year`
  column) raise the Wooddens ceiling 0.9201 → 0.9543 and lower the deployed arm's dispersion ratio
  1.0728 → 1.034 (ADR 0044).
- `CLAUDE.md` §3: the claim that FIT draws recruit traits uniformly from per-PFT intervals is replaced —
  establishment is a two-channel mixture that is 44–80 % **inherited** from the live community
  (ADR 0045). §9 gains the `priority`-partition/QOS limits.

- **CI now runs only when the changed paths can change its verdict (ADR 0090, owner decision).** Every
  workflow was previously unfiltered, so the Julia matrix — four jobs at ~10 min each including macOS — ran
  identically for a change to `src/fdiff.jl` and for a sentence in a LaTeX report. Each gate now declares its
  inputs: `CI` ← `src/** ext/** test/** Project.toml docs/src/generated/**`; `format` ← any `**/*.jl`;
  `python` ← `python/**`; `docs` ← `docs/src/** docs/make.jl docs/Project.toml src/** Project.toml`.
  All four also gain `workflow_dispatch` so any gate can be forced on demand.
- **A prose/docs/skill/ADR/handoff-only commit now triggers no gate and is mergeable immediately.** Note the
  consequence: a workflow that does not trigger reports **no check-run at all** (not a "skipped" one), so a
  poll that waits for `test (lts)` to complete hangs forever. The merge ritual now derives the expected gate
  set from `git diff --name-only origin/main...HEAD`. Updated in `CLAUDE.md` §5/§9, the `repo-commit` skill,
  `ENGINEERING_STANDARDS.md`, `STEERING_PROMPT.md` and `MEMORY.md`.
- ADR numbering: the cross-cutting block 0001–0029 is exhausted; **0090–0099 is now the integrator block**.

### Fixed

*in the validation itself, before the verdict was accepted:*

- **`Qle_cor`/`Qh_cor` can be ≈0 garbage instead of a fill value.** At DE-Hai the uncorrected `le` is all-NaN for
  2010–2012 and the energy-balance correction emitted ≈0 there (annual mean `le_cor` 0.39 / −0.09 / 0.04 W/m²
  vs 30–40 W/m² in 2000–2009), so a finiteness filter kept 36 550 rows of it and the closure — fed LE ≈ 0 —
  put all the available energy into H, inflating DE-Hai's apparent H bias to +39.8 W/m². The driving-table
  builder now also requires the **uncorrected** `le` to be finite (DE-Hai → its 175 344 jointly-valid steps,
  matching ADR 0070's coverage). Found by the new regression fixture on its first run.

- **`scripts/e_two_layer_probe.jl`: the sub-daily `z1 = 0.2 m` control arm omitted `z_soil1` and so silently
  tracked the package default.** Honest while that default was 0.2 m; the moment ADR 0074 set it to 0.75 m the
  arm labelled `z1=0.2` became a duplicate of the 0.75 m arm (visible as two byte-identical thickness arms in
  `e7_two_layer_probe_v5.txt`). Consequence: ADR 0074 §6's sub-daily `T_skin` figures are at 0.2 m, not at the
  shipped default — at 0.75 m the cost is larger (AU-Tum 0.773 → 0.547, AU-Rob 0.385 → **−0.116**). Corrected
  in ADR 0075 §4, re-measured in report `_v6`, and captured in the `plumber2-reference` skill.

- The F-side comparison now runs the **patch ensemble** instead of the modal patch. The modal patch that
  `run_coupled_biomes.jl` / `wscal_leafon_probe.jl` select is systematically denser than the 25-patch
  ensemble mean the C reports — FPC **1.72×** (Sahel), 1.48× (boreal), 1.19×, 1.14×, 1.12× — i.e. a
  reference-basis artifact the same size as the flux biases being measured.

- **The F-vs-C canopy-cover comparison scored the wrong one of the C's two FPC outputs, and correcting it
  flips the sign in four of five biome cells** (ADR 0060). LPJmL-FIT writes both `a_fpc` (the patch-mean sum
  of individual crown covers, `fpc_tree.c:28`) and `a_fpc_stand` (per-PFT leaf area through a single
  Beer–Lambert saturation over the whole patch) — different functional forms of different arguments,
  differing 1.5–2.3× in the same cell-year. The fast core computes the crown form, so `a_fpc` is the
  comparable output; the oracle used `a_fpc_stand`. **Withdraws ADR 0053 finding 4** ("the fast core
  under-predicts tree FPC in all five cells, 0.31–0.72×"): on the comparable output it *over*-predicts in
  four cells (1.05–1.47×) and under-predicts only in the semi-arid Sahel (0.54×).

- **The 5-biome energy/partitioning test could not detect a driver-level fallback** (M1 review debt #1): it
  passed verbatim when all five cells reverted to Hainich's soil and canopy, because its assertions were
  closure, finiteness and qualitative orderings. It now pins each cell's own mean LE and GPP (±2 % / ±3 %,
  against a 24.9…119.3 W/m² between-cell spread) and asserts the five signatures are mutually
  distinguishable at those tolerances.

- Nothing — no runtime code changed. Every committed baseline stays byte-identical; the probe passes
  `wscal_leafon = true` explicitly rather than moving the default (ADR 0051, still line S's to schedule).

- **CI (integrator, `main` `47c6407a`):** pinned `JET = "0.9, 0.11"` in `test/Project.toml` `[compat]`.
  JET **0.12.0** removed the `target_defined_modules` configuration that `test/jet_tests.jl` passes, so
  `test (1)` (Julia 1.12) errored with `JETConfigError` **repo-wide** on a fresh resolve — reproduced
  identically on `line/M` and `line/O` with no test-tree change, while `test (lts)` stayed green (JET 0.11+
  needs Julia ≥1.12, so 1.10 resolves 0.9.20). Second instance of the "CI resolves deps fresh ⇒ a missing
  `[compat]` absorbs a breaking bump" class after Enzyme 0.13.189.

- `julia-test` skill: the "run the full suite" recipe hard-coded `cd` to what is now the **integrator**
  worktree, so following it from a line session would have submitted a suite testing `main` instead of the
  branch under test.

- **Line M / ADR 0051 — F_diff's daily `wscal` was the REALIZED supply/demand ratio; the C's is a
  POTENTIAL leaf-on index.** This closes the last of ADR 0034 §1's three runtime↔training conditioning
  shifts (the other two were line S's, ADR 0035), and it was the stated blocker on M3.

  Both sides carry the column name `water_stress` and both form it as `1 − wscal_mean`, which is why the
  gap was recorded as "same definition on both sides". Reading the expressions
  (`water_stressed.c:130-140`, `gp_sum.c:57-67`) shows they are different physical variables: the C asks
  *if this canopy were at FULL leaf cover, could the soil meet the evaporative demand?* — no `phen` in the
  numerator, the leaf-on conductance `gp_stand_leafon` (normalized by the **plain** `Σfpc`) and no
  `(1−wet)` in the denominator, and `wscal = 1` (**unstressed**) on a no-demand day. F_diff's
  `min(1, Σsupply·fpc / Σdemand·fpc)` carried `phen` **squared** in the numerator and degenerated to **0**
  (maximally stressed) as leaf display vanished.

  Available as **`WaterParams.wscal_leafon`, default `false`** — every committed baseline and the AD trainer
  are byte-identical (guardrail 4). Enabling it moves Hainich's annual `water_stress` from 6–7 trained-band
  widths above the C's `[0, 0.04315]` to **inside** it (0.3050 → 0.0034 against a C truth of 0.0014, a
  **152×** error reduction), and puts `tropical_amazon` **inside the seed1-vs-seed2 noise floor** (0.4×);
  `semiarid_sahel` improves 6.7×, `mediterranean_iberia` 2.1×. `boreal_siberia` is **not** closed — the C
  says it *is* stressed (0.3146) and the C-faithful expression under-stresses it to 0.000, with F_diff's
  absent soil-ice/permafrost representation the leading (explicitly unverified) hypothesis.

  Why it gated M3: coupled on the pinned `_t8` forest, end-of-run tree N moves **−36.4 % in
  `semiarid_sahel`** (19 → 12) — the cell whose conditioning shift was largest — so a per-cell demography
  score taken before this fix was reading a badly displaced Sahel.

  Evidence: `scripts/wscal_leafon_probe.jl` (the coupled A/B, 5 cells × 10 yr) and
  `scripts/wscal_c_truth_diagnosis.py` (the reference, derived per cell/year exactly as the training table
  forms the column, scored against the seed1-vs-seed2 noise floor). Gate:
  `test/testitems/wscal_leafon_tests.jl` — the C's semantics (phenology-independence, the no-demand
  branch, the cap) plus the end-to-end in-band result, all on committed fixtures.

- **Line M — `FToS.soilmoist` now uses the ADR-0035 root-zone basis.** `components/fast.jl` built it as
  `sum(state.w)/length(state.w)`, an unweighted mean over all 23 layers, while `interface.jl:37` documents
  the field as the root-zone fraction of WHC and Component S computes exactly that
  (`root_zone_soilmoist` — the top 1 m, `whcs`-weighted, what the C's `rootmoist` measures). Two
  definitions of one named quantity is the hazard ADR 0035 exists to remove. Nothing consumed the field
  numerically, so this is a definition alignment, not a physics change.

- **Line M / ADR 0052 — F_diff has no soil ice, and that is the CONFIRMED cause of the boreal
  water-stress residual ADR 0051 left open.** Ran ADR 0051's own recorded falsifiable test (no new HPC
  run — `d_rootmoist.nc` is already in the global daily output). Recovering the C's root-zone
  plant-available fraction as `rootmoist / Σ_{l<3} whc_nat[l]·soildepth[l]` (per ADR 0035 `rootmoist` is
  the only C output carrying the model's `w`) gives **exactly 0.000 for Nov–Apr** at `boreal_siberia` —
  every drop in the top metre is ice — against F_diff's flat **0.67–0.91 all year**, so `emax·wr` beats
  the leaf-on demand every day and the leaf-on `wscal` is pinned at **1.000 in all twelve months**. Not a
  bad `wscal`: the right `wscal` of a soil column that cannot freeze.

  The same measurement identified a **second, distinct residual**: F_diff's root-zone water runs
  systematically **too dry in dry cells** (Sahel Jan 0.361 vs the C's 0.533; mediterranean Jul 0.239 vs
  0.369), same seasonal shape — which is what remains of those two cells' ADR-0051 gap and points the
  opposite way (over-stress). The five-cell `water_stress` picture is now fully attributed to three
  separate causes, one of them fixed. No code change; both fixes are deliberately left scoped as
  ADR-0052 consequences with their reference bases established.

  New reusable check: the C's `rootmoist` + `whc_nat` give a per-cell, per-day reference for the
  emulator's root-zone water anywhere on the global grid, with no new HPC run —
  `scripts/boreal_soilice_diagnosis.py` (C side) and `scripts/boreal_soilice_probe.jl` (F side).

- **Two third-party attribution defects found by the ADR 0080 audit** (comment-only; behaviour and every
  committed baseline byte-identical, guardrail 4). (1) The TBPTT trainer described itself as "the finished
  port of NeuralCrop.jl's `train_loop_rollout!` scaffold" (`ext/FDiffTrainingExt.jl` ×3,
  `src/LPJmLFITEmulator.jl`, `src/fdiff.jl`) while the same sentence said "no code copied" — and NeuralCrop.jl
  is CC-BY-NC, so an inaccurate provenance claim is itself the exposure. A direct comparison against
  `NeuralCrop.jl/src/training/training_loop.jl` confirmed **no shared expression**: the only overlap is
  `Zygote.withgradient` → finite-loss guard → `Optimisers.update` in a windowed day loop, i.e. those
  libraries' documented API plus TBPTT itself (Williams & Peng 1990), while the reference spreads jld2
  chunk loading, per-cell batching, `ps_frozen`, device dispatch, an LR schedule, a validation split and
  checkpointing across 19 positional arguments and lacks our detached-state carry (`_advance_state`). The
  wording now states independent implementation with NeuralCrop cited as prior art. (2)
  `patches/json_object_iterator.h.shim` contains verbatim declarations from json-c's public header but
  carried no MIT notice; json-c's copyright + permission notice is now reproduced in it.

- `CLAUDE.md` §1: `28008` is Hainich's index in `input_VERSION2/grid.bin` — a **longitude-major global**
  grid — not in a `-DSINGLESITE` grid. That file and the orderA `soil_code_test.grid.clm` are not
  interchangeable row-for-row, nor are their paired soil-code files.

- Withdrew two published Component-S claims (ADR 0030): the trait floor is **not** 0.90–0.97 on the
  population the emulator trains on (Wooddens is **0.694**, so the "+0.40 headroom" was ~3× inflated), and
  **D95max is not "at floor"** (+0.102 to the reachable ceiling, not +0.021). The "per-cell-median
  instability" explanation of the low basis cross-checks was also wrong — the cause is PFT-set truncation
  (ADR 0031). Split-half analysis shows the floor is **trajectory divergence**, not finite-stem noise.

- `scripts/diagnose_copula_capacity.sh` now passes `BLOCK_SALT` **explicitly** into
  `scripts/eval_slow_copula.jl` and echoes it in the `=== FOLDS:` header. It previously appeared nowhere in
  the driver, so a salt-1 rung depended on `sbatch --export=ALL` inheritance reaching a variable the Julia
  invocation's own env prefix did not list — and the log header would not have revealed a silent fallback to
  salt 0. That failure mode fabricates a *perfectly agreeing* blocked-CV replicate, which is exactly what
  ADR 0040 §5's "NOT RESOLVABLE if the two salts disagree" clause exists to detect, so it would have forced
  a false RESOLVED. Same class as ADR 0041's inert `random_seed` under `FROM_RESTART`.

- `scripts/diagnose_copula_capacity.sh` gained an `EXCLUDE=` knob that emits a real
  `#SBATCH --exclude=`. The `SBATCH_EXCLUDE` environment variable recommended for the known
  flaky-node mode is **not** a recognised sbatch input on this cluster and is ignored silently:
  job 1680828 died `0:53`/no-log on `cso14c74`, and the resubmission carrying
  `SBATCH_EXCLUDE=cso14c74` (job 1681087) landed on `cso14c74` again and died the same way.

- `lines/S/STATE.md` recorded the pooled `t8` copula baseline as "60-tree/50k/d14"; the evaluation that
  produced those predictions ran at **40** trees (`run_pooled_slow_copula.sh` defaults). The 60 is
  `train_slow_copula.jl`'s artifact setting, printed later in the same log.

- `scripts/diagnose_slow_address_prereg.py` built its bootstrap tile-cluster labels through a join that
  returns rows in the latlon frame's order while the statistic's arrays are in `group_by` output order, with a
  `tl[:min(len(tl), len(dy))]` truncation absorbing any length mismatch. The labels were a permutation of the
  rows they clustered, which degenerates a tile bootstrap toward an independent-cell bootstrap and
  **understates** the spatial sd — the exact error the clustering exists to remove. Point estimates never
  touch the labels, so only the CIs were wrong. Detected because `cluster_boot` has a fixed seed yet two runs
  over identical inputs printed different intervals. Fixed with a cell-indexed lookup plus a length assertion,
  and verified by running each gate twice and diffing: both now byte-identical. The re-measured intervals are
  3–5× wider and materially change what may be claimed — the blocked-fold damping is no longer significant,
  and no inter-arm difference is resolvable from marginal CIs (a paired difference bootstrap is the missing
  statistic, noted as a caveat with its fix).

- The sidecar's gate caught a real train/inference shift on its first run, which is why it exists. Four of the
  six env columns are stored `Float32` in `cell_year_feats.parquet` and polars' `group_by().mean()`
  accumulates in `Float32`, so the obvious aggregation lands ~3.35e-07 relative away from the values the
  shipped artifact was conditioned on — 199 093 of 200 000 probed rows differed, max |diff| 7.63e-05 on
  `eco_diag_pet_mean` (exactly `5·2⁻¹⁶`). Casting to `Float64` before the mean reproduces the shipped
  `Xc.f64` tail **bit-exactly**. The gate compares against the shipped `Xc` rather than against a re-run of
  the producing code, because the latter would be circular. Recorded in CLAUDE.md §4.

- **Component S now trains on LPJmL-FIT's COMPLETE tree PFT set (`Type ∈ 0..6`)** — ADR 0031. `TREE_TYPES` was
  `[1,2,3,4,5]`, a stale-yaml port defect that silently dropped the tropical broadleaved evergreen (id 0) and
  the boreal larch (id 6): **32.5 % of survivor tree stems** and **16.7 % of tree-bearing cells** (the tropical
  belt + the Siberian larch zone) were invisible to the emulator. Measured on the seed2 historic copula table,
  the widening takes it from 133.5 M stems / 45 072 cells to **197.8 M stems / 54 058 cells**, and `minwscal`
  from the truncated `[0.025, 0.30]` span to FIT's true `[0.025, 0.75]`.
  The constant now lives in **one** place (`lpjmlfit_emulator.data.TREE_TYPES`); `features.py`,
  `python/config/config.yaml` and every `scripts/build_slow_*.py` / `noise_floor_vs_emulator.py` **import** it
  instead of re-declaring it, so the two copies that caused the defect cannot drift again.
- **`growth_eff` now matches the runtime's zero-leaf-area guard** (`fast.jl:369`
  `leaf_area > 0 ? applied/leaf_area : 0`), replacing a `÷ max(lai, EPS)` divisor that turned a joined
  `LAI_STAND == 0` into `applied_npp × 1e6` — a train/inference shift on a primary mortality driver (ADR 0023).
  The C oracle guards it the same way (`mortality_tree_ind.c:95`). The previously **unexplained** seed1-vs-seed2
  asymmetry is now diagnosed: there is exactly one `cell_year_lai_*` table and it is **seed1-derived**, so
  joining it onto seed1 `ind` is self-consistent (**0** of 23.9 M tree groups hit `lai == 0`) while seed2 hits
  21 501 groups / 204 867 stems. Under the new rule that same seed2 build maxes at 4.3e4 instead of 1.19e9,
  right at seed1's 3.1e4. A `GROWTH_EFF_MAX` assertion now fails the build loud, because the coverage guards
  structurally cannot catch it (a zero `lai` is *present*, not missing).
- **All seven tree PFTs' mortality parameters are now `[VERIFIED]` per-PFT** in
  `scripts/build_slow_flux_table.py::PFT_PARAMS`, read from the active `par/pft_lpjmlfit.js` by a brace-depth
  parse that reproduces the previously-verified beech row as its own cross-check. Adding ids 0/6 exposed that
  the old dict applied temperate/angiosperm values to *every* id and was therefore also wrong for ids 1, 2, 4
  and 5 — most sharply id 5, whose longevity is **125**, not `TREE_LONGEVITY` 400 (a 3.2× age-mortality error),
  and whose `mort_water_factor` is 20, not 5. An unknown `Type` now raises instead of silently taking
  temperate defaults.

- **The ADR-0030 gate now refuses to quote a floor from two seeds that are the same seed.** The ceiling is
  `sqrt(rel_P·rel_Y)` with `rel_Y = floor_r`, so a duplicated realization gives `floor_r ≡ 1` and fabricated
  headroom on every axis, with no error — and the existing `seed1-basis ≥ 0.99` check compares a table to the
  parquet of the *same* seed, so it reads 1.000 and is structurally blind. **The ssp370
  `..._random_seed2` ground truth IS such a duplicate**: `ind_2020_2100.csv` is 193 097 583 638 B in both
  seeds with equal md5 on blocks at MB 0/30000/120000, because its config sets `"random_seed": 2` but its
  `restart_filename` points at the *historic seed1* `restart_2019.lpj` — under `-DFROM_RESTART` the per-cell
  RAND48 state is restored, making the seed inert. (The historic pair is genuinely independent: each reads
  its own relative `restart/restart_1999.lpj`.) Self-tested both ways: the negative control aborts, the
  positive control passes and reproduces the published baseline exactly.
- **The struct-axes disagreement message was misdirected.** It said "Rebuild the seed2 table with the same
  `STRUCT_AXES`", but the seed2 tables *do* carry agb+Height — it is the seed1 **shadow** manifest that
  `diagnose_copula_capacity.sh`'s `TRAIT_ONLY=1` trimmed. Following it cost a pointless multi-hour rebuild
  and fixed nothing. The message now names the narrower side and points at `TRAIT_ONLY`.

- **The copula env-augment dropped every manifest-named sidecar except `cells.i64`
  (`scripts/build_slow_copula_env_augment.py`).** `pooled` tables carry `scenario_tag  scenario.i64` (the
  per-row scenario label `eval_slow_copula_scenario_holdout.jl` splits on), and the symlink loop handled
  only `Y_*.f64` + `cells.i64`. A pooled augment therefore produced a table whose copied manifest still
  declared `scenario.i64` while the 337 MB file was absent from the output — a dangling reference that
  TRAINS fine (the trainer never reads it) and only fails later in the scenario-holdout eval, far from the
  cause. Sidecars are now resolved BY NAME from the manifest, missing-in-source is a hard error, and a
  post-write assertion re-checks that every name the emitted manifest declares resolves in the output.
  First exercised building `slow_copula_pooled_w20_t8env`.
- **The copula sidecar meta hard-coded the 8-column conditioning policy
  (`scripts/train_slow_copula.jl`).** Its header line always read `Conditioning order = live_flux_cond
  (4 flux drivers + boundary tail)`, which is correct only while every artifact is 8 wide. A 14-column
  artifact is built by `live_flux_cond_env`, so the one human-readable statement of the train/inference
  contract named the WRONG runtime policy — precisely the silent shift ADR 0023 warns about. The line is
  now derived from `ncond`.

- `scripts/diagnose_copula_capacity.sh`'s artifact-clobber guard was locale-sensitive: it hashed
  `ls pred_*.f64 | sort`, and the login node collates in `en_US.UTF-8` (case-insensitive) while the SLURM
  batch shell collates in `C`, so the same untouched files hashed differently and the guard reported a false
  "the shadow leaked". Both sides now force `LC_ALL=C`, and the failure path prints the name/size/mtime
  triples so a real incident is distinguishable from a guard artefact.

- **Line M's `wscal_leafon` default flip is unblocked from S's side and pre-authorised.** M recorded it as
  "S's to schedule" and it had sat, because flipping the default reds `slow_production_drf_tests.jl`'s
  assertion that the out-of-band conditioning set is *exactly* `{water_stress}`. That assertion now admits
  **exactly the two admissible states** — `{water_stress}` with the flag off, the **empty set** with it on —
  and still fails on any third outcome, so the flip no longer needs a synchronised two-sided commit. S
  endorses it on M's own measurement (ADR 0051): Hainich's `water_stress` goes **0.3050 → 0.0034** against a
  C truth of 0.0014 and a trained band of [0, 0.04315], so the flip **closes S's last out-of-band
  conditioning column**. Expect it to move M's pinned per-cell coupled baselines — a deliberate regeneration
  under guardrail 4.

  Hainich cell 42490 only (guardrail 6), constant repeated-2010 forcing, committed demo artifact pair. No
  committed baseline, artifact, fixture or default moved; runtime `[deps]` stays empty.

- **Component S / DRF: a wrong-length conditioning row was an out-of-bounds heap read, not an error.**
  `DRF._leaf` reads `x[f]` inside an `@inbounds` block, so querying an `nfeat`-feature forest with a shorter
  row returned whatever bytes followed `x` and produced a plausible in-range trait. `predict` and
  `predict_quantile` now check the length, and `DRF.load_copula` fails fast when any marginal's `nfeat`,
  `length(cond_cols)` or `length(x)` disagrees with the header's `ncond` — the only enforcement of the
  ADR-0023 train/inference contract once a copula's conditioning width changes. Byte-identical for every
  correctly-sized call: the committed Hainich fixture's golden draws are unchanged.
- **Component S: the extended-conditioning env tail selected ZERO cells for SSP370.** `cell_year_feats` is a
  historic climatology table (Year 2000–2019) that the static boundary reads whole for every scenario, but the
  env branch filtered `Year >= FIRSTYEAR[scenario]` — 67 420 cells for `historic`, **0** for `ssp370`, which
  then failed downstream with a message blaming a coverage hole. Both `build_slow_runtime_table.py` and the
  new augment script now use the boundary's basis, verified byte-identical for `historic`.
- **Component S: the capacity harness aborted before submitting when its source table held no predictions.**
  Its clobber-guard fingerprint ran `ls pred_*.f64`, which exits non-zero on an empty match and, under
  `set -o pipefail`, killed `diagnose_copula_capacity.sh` before `sbatch`.

- The ssp370 seed2 **independence gate had failed spuriously**: when the hung member was resubmitted, its
  chained gate jcf still named the *cancelled* attempt's 0-byte log, so it reported `no completion line at
  all` for a C run that had in fact terminated cleanly over all 67 420 cells — and left the 93 GB parquet
  conversion stranded on `DependencyNeverSatisfied`. Re-run against the real log, the member **passes all
  four checks** and is confirmed a genuine second realization.

- **The committed Hainich demo count DRF is regenerated onto the REAL feature basis, so the two artifacts one
  emulator loads together are on ONE basis again (ADR 0032 closed, milestone S1c).**
  `test/testitems/references/drf_forest_hainich.drf` + `_meta.txt` were trained on the retired proxy features
  (`soilmoist = 0.7`, `lai = 21.2`, `growth_eff = 19`) while `recruit_copula_hainich.rcop` beside them was on
  the real ones — a live ADR-0023 train/inference shift on the artifact the in-loop gates read first. Both are
  now rebuilt from a single table build; the `.rcop`, its meta and both `hainich_slow_oracle_*.csv` came back
  **byte-identical**, and the `.rcop`'s conditioning row now lies inside the `.drf`'s trained band on all
  **8/8** shared columns (0 violations). Every re-measured Hainich drift threshold improved: Gate-3 Height
  `nqrmse` **0.3895 → 0.2998**, median Height ratio 1.2463 → 1.1316, settled count ratio 0.6734 → **1.2808**
  (the in-domain flux drivers raise the count from ~6.8 to ~12.9 stems/patch, and more stems sharing the same
  carbon are smaller trees). The Gate-3 alarm is **tightened 0.45 → 0.40** accordingly — no threshold widened.

- **ADR 0102 §4's central claim was wrong, and the correction matters more than the fix.** It stated the
  anchor "requires the count↔density conversion at the S↔F seam — an `interface.jl` addition, which is line
  M's", and on that basis deferred a one-file change into a cross-line integration point. **The conversion is
  a documented constant:** `par/lpjparam_fit.js:17` sets `"patcharea": 225.0` m² (15×15) and
  `src/tree/new_tree.c:209` gives every individual `nind = 1/patcharea`. **The project owner caught it.**
  Verified rather than taken on trust, per CLAUDE.md §3: `cpp -P` over the *live* config yields exactly one
  `"patcharea"` (225.0, no duplicate-key override — the trap that makes larch's `aphen_min` 10 instead of
  60), and the committed fixture agrees end-to-end (`sum(nind) × 225 = 17.000`, every individual at `1/225`).
  Two transferable lessons:
  - **"X cancels" is a statement about an expression, not about X.** CLAUDE.md's own sentence — "with
    `nind = 1/patcharea` the patcharea cancels" — is true of the ADR-0035 per-patch LAI derivation and was
    read as a general property of the quantity. The follow-up question, *cancels against what?*, was never
    asked.
  - **Before routing work to another line, confirm the thing you need is actually theirs.** ADR 0029 stops
    lines editing each other's files; it does not make a constant from a third repository into another line's
    property. Deferring a one-file change to a negotiation is a real cost.

- A `Vector` field on `FDiff.Individual` aborts the Enzyme reverse pass with SIGABRT (a bare LLVM abort with
  no Julia error, surfacing right after the grass Enzyme training test item). The per-tree root profiles now
  travel as a separate argument that Enzyme sees as constant data. Recorded on the struct so it is not
  reintroduced.

- Component S: two previously unrecorded facts about the C parameter file, both surfaced by generating the
  reference instead of transcribing it. PFT id 6 (larch) declares `aphen_min`/`aphen_max` **twice** —
  macro defaults 60/245 followed by an override pair 10/200 — and json-c's last-wins lookup makes 10/200
  effective, so larch accumulates water stress six times earlier in the season than the other six tree
  PFTs. And `sla_median` (0.01986) is a single global default that lies **outside** `[low, high]` for ids
  1, 2, 3 and 5, so it is not a central value of the interval recruits are drawn on. The builder enumerates
  the duplicate keys and asserts the set is unchanged, so a new silent override cannot slip through.

- **The distributional forest was not using its own estimator.** `predict_quantile` concatenated every tree's
  leaf values and took an unweighted quantile, giving each stored value weight `1/sum_t |L_t(x)|` — so a tree
  contributed in proportion to how large its leaf happened to be, instead of the `1/T` a quantile-regression
  forest prescribes. The two coincide only for equal leaf sizes, and the production global copula is far from
  that: over the Wooddens marginal's 70 854 leaves, sizes run min 20 / median 26 / q99 371 / max 4016
  (coefficient of variation 2.01). Routing real conditioning rows through that 60-tree forest, the largest
  leaf hit takes **median 11.1 % / mean 12.2 % / q90 18.8 %** of the prediction weight against QRF's
  **1.7 % = 1/60** — a **6.7x typical over-weight, 11.3x in the sparse-conditioning decile**
  (`scripts/rcop_leaf_geometry_probe.jl`; 5.8-6.7x typical across the four axes). The bias has a
  direction: a big leaf spans a wide region of conditioning space, so its values approximate the global
  marginal and over-weighting it drags each cell's conditional toward that marginal — an attenuation
  mechanism. Those large leaves are **depth-capped, not gain-exhausted**: 99.9-100 % of leaves holding at
  least `2*min_leaf` values sit at exactly `depth == max_depth`, and 57-67 % of all stored values are in one.
  Verified as a weighting effect and not the accompanying quantile-convention change: measured separately on
  the production artifact, the convention accounts for 0.002-0.014 % and the weighting for 1.67-4.43 %, a
  315-1507x ratio. `DRF.predict` was already correct (it averages leaf means at `1/T`), so the count DRF and
  every count skill number are unaffected.

- Nothing in shipped code: `trait_mortality` remains opt-in and default-off, so every committed baseline,
  ReferenceTest and AD path is byte-identical and runtime `[deps]` stays empty.

- **S→M integration point #2 (raised, not yet landed):** the `pooled_w20` artifact ships **no
  `cell_meta.parquet`** — its meta names one that does not exist — and its two training sub-tables disagree
  on Hainich's per-cell seed (`n_init`/`age0` 11.0/43.556 vs 7.0/46.0), a **4.5× FIT** swing in the measured
  response. `M_slow_init_meta.json` silently resolves this to the well-behaved branch (so nothing is broken
  in M's current pin) and takes its **boundary row** from `slow_runtime_historic_t8` — a table the pinned
  artifact was never trained on (gdd5 1 863.7 vs the training basis's 1 698.0, 23 % of the warming signal) —
  while on that artifact the boundary channel is worth **3 165 gC/m³ = 1.30× FIT** on ensemble average.
  Either ship a pooled `cell_meta.parquet` or record the substitution and its consequence in the pin's
  provenance.

  Hainich cell 42490 only (guardrail 6); `trait_mortality` stays opt-in and default-off; runtime `[deps]`
  stays empty; `MODE=stage2` is untouched and remains the ADR-0049 regression; no committed baseline moved.
  Nothing here may be quoted against the ADR-0044 global gate — which ADR 0101 now argues is the *only*
  right instrument for a response claim, with the required replication count measured.

- The `lai == 0 → growth_eff` blow-up class (ADR 0031) is now structurally impossible rather than guarded:
  `lai` is derived from the same `ind` rows being aggregated, so it can no longer come from a different
  seed's trajectory via a cross-seed join.

- **The ssp370 `random_seed2` ground truth was a bit-identical copy of seed1; produced the real
  one.** `random_seed` is **inert** in any `-DFROM_RESTART` run: with `"new_seed": false` the
  per-cell RAND48 seeds are restored from the restart file (`newgrid.c:507-513` →
  `freadcell.c:37`) and the code that would apply `config->seed_start` is gated off
  (`newgrid.c:520-521`); `seed_start` is applied once at parse time (`fscanconfig.c:231`) and then
  overwritten from the restart header (`openrestart.c:139-140`). The broken member set
  `random_seed: 2` but restarted from the **historic seed1** `restart_2019.lpj`, so it inherited
  seed1's exact state — and because `new_seed` is false the log prints `Reading random seeds from
  restart file.` instead of `Random seed: 2`, so nothing warned. A noise floor built from it
  reports `floor_r ≡ 1`, i.e. fabricated emulator headroom. **A second seed is a second SPIN-UP
  carried forward**, not a changed `random_seed` (ADR 0041).

- **`build_slow_runtime_table.py`: a silent row-set corruption in the global count tables.**
  `polars` `collect(engine="streaming")` is not deterministic in the KEY SET it emits at global scale (only
  its float-sum jitter was documented): two ssp370 builds over the same `ind` parquet produced 99 023 397 vs
  99 028 310 rows — 141 cells differed, 4 913 rows missing, 12 cells with DUPLICATED keys — and the AR
  self-join amplified each duplicate into four rows. The existing coverage guards structurally could not catch
  it, because duplication makes `dropped = h_before − h_after` go negative so a `drop_frac` test never fires.
  Now a hard `(Cell,Patch,Year)` key-set invariant fails the build loud, and the AR lag is taken with a window
  shift instead of a 100M x 100M self-join (gated: rebuilding the historic table reproduces the shipped one
  with `y`/`cells` byte-identical and `X` to 0.000e+00 relative difference). The affected per-scenario ssp370
  artifact was rebuilt; its OOS R² is unchanged at 0.9823.
- Documentation corrections that were substantive, not cosmetic: `STEM_CAP` is a patch-year **cluster**
  subsample, not the per-stem sample it was documented as (so the stand-biomass composite is refused for the
  pooled pair, whose two tables weight the scenarios differently); the biomass `basis_ratio` is an exact
  identity on matched rows and therefore a **row-universe** check, not the `Cov(N, mean size)` correction it
  was described as; figure 06 is not a distributional check, because the count DRF is scored with a
  conditional mean; and the default (non-transient) boundary is the 2000-2019 historic climatology for BOTH
  scenarios.

- **Documented a measured defect in the Component-S training population (ADR 0031): `TREE_TYPES =
  [1,2,3,4,5]` drops a third of LPJmL-FIT's forest.** `Type` in the annual `ind` output is the 0-based
  `pftpar` index, and ids **0–6 are all seven tree PFTs** (7/8/9 grass, 10–21 crops), so the production
  DRF/copula builders silently omit id 0 (tropical broadleaved evergreen) and id 6 (boreal larch):
  **64 179 572 of 197 721 867 survivor tree stems = 32.5 %**, with **9 011 of 54 020 tree-bearing cells
  (16.7 %) invisible to Component S** — the tropical belt and the Siberian larch zone — and 41.8 % of cells
  losing more than half their stems. Because FIT draws traits uniformly from per-PFT `[low, high]` intervals,
  the truncation also biases retained cells: per-cell trait medians correlate only 0.09–0.97 between the two
  populations, and the complete set carries 1.3–2.7× more between-cell spread. Provenance is a stale sibling
  `configs/config.yaml`, never an ADR; the correct constant already exists at
  `python/src/lpjmlfit_emulator/features.py:50`, and the python LightGBM `DirectEmulator` path is unaffected.
  Every declaration site now carries an ADR-0031 pointer; the correction itself (one imported constant +
  re-derive → retrain → re-validate → re-measure the ADR-0030 gate, with versioned artifacts and an
  integration point with line M) is the next line-S work item. Committed baselines, golden fixtures and the
  runtime are untouched — Hainich contains only ids 1–5, which is why every single-cell gate stayed green.
- Recorded (not yet fixed) a related conditioning hazard: `growth_eff = applied_npp / max(lai, EPS)` divides
  by `EPS = 1e-6` where the joined `LAI_STAND` is exactly 0 (202 106 of 1 348 400 historic cell-years),
  producing a `growth_eff` maximum of **1.19e9**. The coverage guards cannot catch it — the feature tables are
  complete, so a zero is *present*, not missing.

- **Three independent errors in the yardstick the emulator's warming response was being judged against**
  (ADR 0111). ADR 0093 §3e had the reliability and the deattenuated slope **swapped** in the Wooddens and
  D95max rows; the reliability and the slope had been computed on **different bases** (log-space single-year
  vs linear all-years-pooled), so their quotient was undefined; and a per-patch density had been divided by
  the number of **occupied** patches, which cancels part of its own sampling noise and understated the sparse
  stratum's floor by 3× (10.5 % instead of 27.0 %).

- Component S: `Rb` is demoted to a veto-only criterion. It is unresolvable as a paired delta
  (`sd_paired` = 533 blocked) and a zero-information permutation buys it at 3.30σ, so "the damping fell
  from A % to B %" is inadmissible in every form (ADR 0044).

### Deprecated

- **`recruit_copula_global_historic_t9.rcop` is the historic-STATIC artifact and is NOT line M's production
  copula.** The six env columns have within-cell sd **exactly 0 for 100 % of cells** — they are per-cell
  constants broadcast across years, so they cannot encode a warming response, and in the pooled table a
  cell's historic and ssp370 rows carry bit-identical env values. A 1-NN lookup on those columns reaches
  Wooddens r = 0.800 with a median distance to the nearest training neighbour of **1.00°** (q25 = 0.50°, the
  adjacent cell), against r = 0.445 / 14.51° for the existing boundary constants — so they resolve to a
  geographic address, and K-fold-**by-cell** CV cannot separate a transferable environmental response from
  spatial interpolation. The +0.037 is a valid offline gain whose generalization is **unestablished**;
  production turns on a spatially blocked re-score, which is now the named next step.

### Documentation

- **Recorded that `run_global_slow_copula.sh` scores a different estimator than it ships**: `NTREES` (60)
  feeds `train_slow_copula.jl` ⇒ the shipped `.rcop`, while `EVAL_NTREES` (40) feeds `eval_slow_copula.jl` ⇒
  the scored OOS. So every published **t8** gate number describes a 40-tree estimator while the artifact line
  M pins is 60-tree (read off the artifacts: t8 `ntrees=60`, 3 000 000 stored leaf values = 60 × 50 000; t9
  `ntrees=6`, 12 000 000 = 6 × 2 000 000). **t9 is the first generation where the two agree.** Tree count is
  nearly inert for skill (±0.002 over 3.3×) so the t8 headline barely moved, but it is *not* inert for the
  leaf-weight skew the QRF argument rests on (6.7× `1/T` at 60 trees vs 2.9× at 6) — attribute weighting
  figures to the right object. Also resolves the apparent "40 vs 60" contradiction in
  `diagnose_copula_capacity.sh`'s size comment: both are right, about different objects.

- ADR 0110 — the "structurally impossible" per-individual water-supply verdict was reached on **grass** and
  does not apply to **trees**. `beta_root` is set per individual from that individual's own `D95max`
  (`new_tree.c:229-230`), the trait spans 51–1800 cm within a single PFT, and the C's per-individual `wr`,
  `supply`, `wscal` and the routinely-firing "own FPC share" cap are all **order-independent** — the
  `-DPERMUTE` randomness touches only the residue cap and realized GPP. Measured: across-tree water-scalar
  spread of 0.16–0.19 in the water-limited cells (our fast core carries one number), a 0.83 within-band
  correlation between a stem's root profile and its own water status in the Sahel, and drought-killed stems
  rooting 57 % shallower than the population mean at Hainich. Verdict PASS; per-tree roots + per-tree water
  + un-zeroing the two hazards ADR 0049 left at zero is the decided path, in three separately-gated
  default-byte-identical steps.

- ADR 0110 — the "structurally impossible" per-individual water-supply verdict was reached on **grass** and
  does not apply to **trees**, and the `-DPERMUTE` randomness behind it does not touch the per-individual
  quantities the drought channel needs (they read a soil column frozen for the whole permuted loop). Narrows
  `docs/water_supply_perpft_design.md`'s DEFER to the order-dependent residue cap alone; reopens the channel
  ADR 0049 §3 closed. Flip criteria pre-registered.

- `CLAUDE.md` §0a — a standing project-level rule binding **every** work line: reports to the project owner
  must be in plain language. No decision-record numbers, no milestone or phase codes, no repo jargon
  standing in for an explanation; a label is a pointer, never an explanation. Numbers, findings and caveats
  all stay — only the internal shorthand goes. The section carries a translation table. It binds
  user-facing text only; ADRs, STATE files, journals and code comments keep the precise shorthand, where it
  is load-bearing. Owner instruction, 2026-08-06.

### Verified

- **E7 beats the fitted `λ_g = 1.0` it was only asked to match**, with nothing fitted (497k PLUMBER2 tower
  steps, 4 sites; harness reproduces ADR 0073's published numbers digit for digit). Daily step, at the two
  sites whose towers can score H: DE-Hai H R² 0.035 → 0.645 (fitted arm 0.637) and G R² −39.4 → 0.717
  (0.657); AU-ASM H R² 0.329 → 0.775 (0.745) and G R² −15.4 → 0.614 (0.477). `Rn` unchanged within ±0.005.
- Sub-daily, the diurnal amplitude of `G` becomes correct at closed-canopy sites (DE-Hai all-hours sd(G)
  5.75 vs observed 5.66, against the default's 34.7) and **night `G` R² turns positive at DE-Hai (+0.394)**.
  Nocturnal **H** R² stays negative (−0.324) exactly as ADR 0073's `ε_obs` bound requires.
- No secular drift: at the 16-year AU-Tum record the second-half annual-mean trend is −0.059 K/yr (T1) and
  −0.015 K/yr (T2), with mean daily `G` 0.001–0.072 W/m² — the closed-bottom column self-equilibrates, so
  no deep-restore term is needed.
- Known limitations, quoted rather than hidden: one global `z1` cannot serve both a closed canopy and a
  sparse desert (AU-ASM's observed all-hours sd(G) is 64 W/m²), and sub-daily `T_skin` degrades at
  AU-Tum/AU-Rob.

### Measured

*no default changed:*

- **The extra conditioning describing each cell's moisture climate turns out to trade present-day accuracy
  against climate response, and the time-varying version buys the response back (ADR 0109).** Scored on
  identical rows across 52,074 cells in both scenarios: adding those six numbers as fixed per-cell values
  improves how many cells land within 10 % of the original model (by 3–5 percentage points) and *degrades* how
  well the emulator reproduces the original's shift between present-day and the warm future — on all four
  traits. Making them time-varying recovers most of that shift (for wood density the original's mean shift is
  +2406, the frozen version predicts +1529, the time-varying one +2402) at a cost of under one percentage
  point of present-day accuracy. The time-varying version is **not** switched on: the go/no-go test written
  down beforehand was not met, and the coupled check it also requires has not been run. Nothing that was
  running changes.

### Verdict

*same 497 936 tower steps, 4 sites — full numbers in ADR 0073:*

- **The stability / `g_a` hypothesis is REFUTED, three independent ways.** The closure's nocturnal `g_a` is
  within **0.7 %** of DE-Hai's measured-`u*` value (0.05724 vs 0.05685 m/s) and within a factor 2 at every
  site; substituting the measurement makes nocturnal H **worse at all four sites**; and a **100× `g_a`
  bracket cannot reach positive nocturnal R²** anywhere (best −0.06). ADR 0072's monotone `stab_amp` sweep was
  a **bias-cancellation artifact** — suppressing `g_a` offsets the ground-heat error without fixing it.
- **The mechanism is the ground-heat term's timescale.** `G = λ_g(T_skin − t_soil)` with `λ_g = 7.0` and a
  τ = 30 d EWMA reference has no diurnal soil inertia and no canopy decoupling: sd(`G_model`) is **5–7×**
  sd(`G_observed`) at the closed-canopy forest sites (34.7 vs 5.7 W/m² at DE-Hai), G night R² −3.4…−51.1, and
  **88 % of DE-Hai's +14.04 W/m² nocturnal H bias is `ΔG`**.
- **`λ_g ≈ 1.0`, not 7.0, at the daily step the coupled model actually runs** (`run.jl:93` calls `solve!` once
  per day). Three independent lines agree: the observation-implied `λ_g` is **0.83–1.10** at all four sites at
  the daily step; `λ_g ≈ 1.0` reproduces the observed daily sd(`G_o`) of 4.3–6.3 W/m²; and daily H skill
  improves at 3 of 4 sites — **DE-Hai R² 0.03 → 0.64** (RMSE 38.1 → 23.4), **AU-ASM 0.33 → 0.74** (31.8 → 19.6).
  A broad optimum (0.5 and 1.0 score alike), degrading only the already-suspect AU-Rob.
- **Part of the residual is UNCLOSABLE.** Mean nocturnal `ε_obs`: DE-Hai **−0.32** (the tower closes — the
  trustworthy site), AU-ASM −12.0, AU-Rob −47.5, AU-Tum **−62.3** W/m². At the daily step `ε_obs` accounts for
  essentially the entire mean H bias at three sites, while DE-Hai's daily H bias is **+0.87 W/m²**. AU-Tum and
  AU-Rob **cannot** honestly score a closing model's nocturnal H; they remain valid for `T_skin`.
- **Nocturnal *skill* (R² > 0) is not recoverable by any parameter value in the present form** — that needs a
  force-restore / two-layer soil scheme with a real diurnal wave plus canopy heat storage. This bounds line O:
  the online sub-daily coupling inherits an R² < 0 nocturnal H until that lands.
- **No default changed and no physics changed** (guardrail 4). `lambda_g` is already a `SEBParams` field, so
  `SEBEnergyClosure(params = SEBParams(lambda_g = 1.0))` works today with zero code change. Flipping the
  default moves every coupled/biome baseline ⇒ **`lambda_g` is now the live E→M integration point, and
  `stab_amp` is withdrawn as one.**

*497 936 tower steps, 4 sites — full numbers in ADR 0072:*

- **`Rn` verified:** R² 0.986–0.996, bias +1.95…+10.2 W/m², under the towers' own albedo.
- **`T_skin` verified where observable:** daily RMSE 1.41–1.97 K, R² 0.76–0.95 (AU-Tum / AU-ASM / AU-Rob).
  Not at Hainich — PLUMBER2 carries no `LWup` there.
- **`H` verified in the mean, not in variability:** every site's bias (+6.4 to −19.2 W/m²) is inside the
  dataset's own uncertainty and **76.4 % of DE-Hai daily means fall inside `|h_cor_uc|`**, but daily R² is 0.125
  (AU-Tum) to 0.778 (AU-ASM) and **nocturnal H has R² −1.0…−5.6 everywhere**.
- **Named failure mode:** the closure runs **1–2 K too cold at night** (modelled night `T_skin − Tair` −3.4/−2.6/
  −1.8 K vs observed −1.4/−1.7/−0.7 K) — too little nocturnal turbulent + ground coupling.
- **Methodological finding:** half-hourly H R² (0.647 at DE-Hai) is **inflated by the diurnal cycle**; the daily
  mean (0.257) is the honest number.
- **Stability correction:** ON beats OFF at night (RMSE 37.0 vs 41.7 DE-Hai; 29.7 vs 46.4 AU-ASM), and the sweep
  is monotone in `stab_amp` up to 0.9 ⇒ the 0.75 default is **too weak**. No default was changed (guardrail 4);
  the retune is an integration point with line M, and the monotonicity suggests the bounded-tanh *form*, not the
  coefficient, is the real limit.

*full numbers in ADR 0055:*

- **The documented AC-vs-climate gradient is not in this model on this basis.** Detrended lag-1
  autocorrelation of the per-patch living tree count is **flat at 0.452–0.541 across all ten P/PET
  deciles**, and the driest decile is the **lowest**, not the highest; `agb` behaves the same
  (0.448–0.544). The seed1-vs-seed2 floor is 0.042–0.062, so the flatness is a result, not noise. Two
  diagnostics rule out shot-noise attenuation as the explanation: the noise-immune `r₂/r₁` sits *below*
  `r₁` everywhere (0.31–0.41) rather than above it, and the between-patch spread is 1.18–12.6× larger than
  the year-to-year variance of the patch mean, i.e. a persistent patch offset rather than sampling noise —
  which is also why the obvious variance-based attenuation correction was written, measured, and discarded.
- **The variance gradient is real and large:** CV 1.149 (driest) → 0.143 (wettest), 8×, monotone over the
  dry half.
- **Carried caveat:** 20 years is all the historic `ind` table has, and linear detrending is a high-pass
  filter, so memory with a timescale ≳ 10 yr is removed with the trend. The honest statement is "not
  resolvable on this window and basis", not "the literature is wrong".
- **The coupled emulator has NO AC gap.** The deployed arm sits **0.1–0.6 between-patch SDs** from the C on
  every cell and both variables (mean 0.32) — the first coupled result on this line inside the noise floor
  everywhere. Consistent with ADR 0054, whose error is in the count **level**: a detrended lag-1
  autocorrelation is blind to a level and to a monotone drift.
- **The shuffle test PASSES and the memory is F's carbon pools, not S's recursion.** Destroying the
  climate's year-to-year sequencing leaves AC at **0.460–0.653** (inherited ≤ 0.146 either way), pinning
  the count-space AR feature leaves **0.391–0.704**, and `slow = nothing` already carries **0.454–0.691**.
  `|free1 − pin1| ≤ 0.135`: **ADR 0054's unanchored recursion drives the count level drift and contributes
  essentially nothing to the memory timescale** — two different failure modes, one of them absent.
- **ADR 0054's teacher-forced anchor arm makes the AC WORSE in two cells** (Amazon `n` 0.066 vs a C of
  0.501 = 2.3 SDs; mediterranean 1.2 SDs). It is a diagnostic, not a fix to deploy — a caveat on the open
  line-S integration point, which was raised on the level improvement alone.
- **No limit cycle** over 100 cycled years (`osc` 0.06–0.50, at or below white noise), nothing non-finite,
  carbon closing at ≤ 2.1e-11 throughout. **Three open findings recorded rather than smoothed over:**
  `semiarid_sahel` does not recover from the pool perturbation (τ 602 yr, r² 0.38, vs 47–54 yr / 0.60–0.73
  elsewhere); there is **no steady state under cyclic forcing** (AGB drifts 1.39–5.15× over the century);
  and the AC-implied timescale (1.2–2.9 yr) is **~20× shorter** than the measured recovery time (~50 yr),
  so an autocorrelation must not be read as a restoring rate.

### Gates

- `soilmoist` is **inside** the trained band (was 5.1× band width); `lai` fell from 2.9× to 0.021× (12-yr)
  / 0.086× (20-yr). The pinned out-of-band set in `slow_production_drf_tests.jl` shrinks to
  `{water_stress}` alone — an F_diff-vs-C difference owned by line M — with new bounds asserting
  `soilmoist` exactly inside and `lai`/`fpc` ≤ 0.2 band widths.
- Thresholds **tightened, none widened**: DIRECT copula draws SLA 0.22 → 0.10 (measured 0.1274 → 0.0391)
  and Wooddens 0.12 → 0.06 (0.0346 → 0.0273). Gate-3 Height `nqrmse` 0.2998 → 0.2990 (alarm stays 0.40),
  settled count ratio 1.2808 → 1.1597, carbon residual 1.9e-12, artifact basis-agreement violations 0.

### Notes

- **T_skin is not observable at Hainich from PLUMBER2**: its FLUXNET2015/LaThuile-sourced files carry no
  upwelling longwave. T_skin validation moves to the OzFlux subset (ADR 0070); Component E's LE/H/T_skin stay
  `[ASSUMPTION]` until milestone E4.
- Observed daytime Bowen ratios reproduce the ordering `biome_coupled_tests.jl` asserts: GF-Guy 0.30 <
  AU-Rob 0.52 ≈ AU-How 0.54 < AU-Tum 0.80 < DE-Hai 0.96 < FI-Hyy 1.23 < FR-Pue 1.70 < US-SRM 3.31 < AU-ASM 4.57.

- **SSP370 surface pressure remains unsourced** — the raw MPI-ESM1-2-HR set has `sfcwind` but no `ps`, and no
  LPJmL-prepared `ps` exists on the cluster. The future branch of E stays on a fixed pressure.
- The tower comparison shows grid-cell forcing ≠ tower forcing, so E4 must drive with the **tower's** wind and
  psurf when scoring against tower fluxes, and with these remapped fields for model-grid runs.
- Feeding the fields into the coupled driver touches `src/run.jl` (line M's path) — an integration point, not
  part of this change.

- **The anchor fires perfectly and the level error it closes is larger than the single-cell evidence showed.**
  Stand density × `patch_area` / the DRF's own target is **1.001 in all five biome cells** at `a = 0.5`, versus
  **1.46–2.21** free-running — so ADR 0103 §2's 41 % over-density is a Hainich number, and across biomes the
  free-running stand sits **46–121 %** denser than its own count model's absolute prediction (worst
  `tropical_amazon`, 2.21×). No gate in this project reads that level.
- **Criterion (iii) carbon closes** in every cell and every arm by six orders of margin; **(i) and (ii) fail.**
  (i) fails structurally — the drift lives in the DRF's *target*, which F's canopy drives, and ADR 0103 itself
  states the anchor does not close ADR 0102 mechanism (A); the criterion asked for something the mechanism
  never claimed. (ii) fails on a new finding: anchoring closes a `density → fpc → target → density` loop that
  is benign in four cells (`tropical_amazon` steps down then recovers, Hainich's gate metric improves
  4.5 → 3.2 noise floors) and **runaway in `semiarid_sahel`** (`fpc` 0.281 → 0.057 monotone, target
  13.5 → 4.46, E/C 1.19 → 0.33). That is the Sahel's fourth independent symptom.
- `anchor = 0.1` is the worst available setting at line M's 10-year horizon: 15–46 % of the level correction
  and essentially none of the drift benefit, while still costing the Sahel.

- No `src/` change; every committed baseline is byte-identical. `wscal_leafon` remains `false` by default —
  flipping it is still the open two-sided integration point with line S (ADR 0051).

### Added
- **`EXECUTION_PLAN.md` — the current order of work, as an error-attribution ladder
  ([ADR 0093](docs/decisions/0093-the-patch-ensemble-is-not-the-bottleneck-the-per-tree-loop-is.md) +
  [ADR 0094](docs/decisions/0094-per-year-esm-speed-is-the-goal-the-spinup-saving-is-not.md); owner-approved
  2026-08-07).** Two measurements re-rank the whole programme. **(1) The shipped Julia emulator is 3.8× SLOWER
  per cell-year than the C model it replaces** (1.096 vs 0.290–0.383 core-s), its per-individual daily step
  costing 51× the C's while its per-patch fixed cost is 0.066× — so the ~100× needed for an ESM decomposes as
  **37× single-core engineering + ~3× patch reduction**, and the patch ensemble is the *last* lever, not the
  first. No end-to-end emulator-vs-C timing had ever been made, which is how that regression went unnoticed;
  one becomes a required gate. **(2) The owner re-ranks the compute case** — per-year ESM speed is goal #2 and
  the spin-up saving is explicitly not the goal, superseding ADR 0092's conclusion. Also measured and recorded:
  `npatch` is numerical (<0.15 % on every cell-mean at 50 vs 25); the 25 patches are worth `n_eff` 4.8–12.9
  because the cell-level seedbank couples the *inherited* trait pool (isolated by the non-inherited
  median-Height control at `n_eff ≈ 25`); at `npatch=25` the C's own answer is already outside the 10 % band on
  carbon, median height, minwscal and rooting depth; the per-cell trait response is below the two-seed noise
  floor (signs disagree in 33–37 % of cells) while the area-mean response has signal-to-noise ≈ 200; and
  deattenuating for target noise shows **two** broken response axes, not four. Five patch-reduction routes are
  refuted with numbers (one big patch, structural stratification, time-averaging, a smooth trait density with
  no individuals, a roster ensemble without daily physics) and three cheap wins survive (share the soil column
  but never the canopy; trait-dependent mortality holds the wood-density selection at 0.98–1.06 across all
  seven PFTs; a bounded Beta per trait interval beats the shipped copula 2–3× on per-cell KS). The ladder is
  wired into all four lines' `STATE.md` handoffs with rung ownership — S 0/1, M 2/3/4, O 5, E off the critical
  path — and the pre-registered flip criterion for `trait_mortality`. `docs/decisions/README.md` marks ADR 0092
  resolved. Adds a fifth pre-check to the `residual-diagnosis` skill: *is the target noisier than the residual?*
- **A FULL data-flow diagram, generated from the code, plus the staleness gate that was missing
  ([ADR 0091](docs/decisions/0091-the-full-dataflow-diagram-is-code-derived-and-the-staleness-gate-becomes-real.md);
  owner request 2026-08-06).** New page `docs/src/explanation/dataflow.md` embedding a new generated
  `docs/src/generated/dataflow_full.mmd`: every input dataset LPJmL-FIT is driven by, the C model, its
  outputs, the derived training tables, the two learned artifacts, and the runtime S/F/E seam — with
  offline training/validation paths **dashed** so a coupled run is visually distinct from the pipeline
  that built it. `src/registry.jl` gains `DataNode`/`DataEdge`/`STAGES`/`DATA_NODES`/`DATA_EDGES`, purely
  additive: `COMPONENTS`/`FLUXES` and both pre-existing generated diagrams are **byte-identical**
  (guardrail 4). **Runtime edge labels are REFLECTED from `fieldnames` of the `src/interface.jl` structs**
  (new `payload_type` field), so the diagram tracks the interface contract mechanically — adding a field
  to `SToF` changes the diagram.
  **The gate:** `.github/workflows/CI.yml` had watched `docs/src/generated/**` since the beginning,
  annotated *"diagram fixtures the suite compares against registry.jl"*, and
  [ADR 0090](docs/decisions/0090-ci-runs-only-when-it-can-change-the-verdict.md) repeated it — but **no
  test compared them**, and `docs/src/generated/components.mmd` was consequently stale from the Phase-4
  commit `773945fb` for weeks, contradicting `src/registry.jl` with nothing failing. New
  `test/testitems/diagram_registry_tests.jl` closes it with four gates: staleness (byte-compare against a
  regeneration), reflection (every typed edge's label == its struct's `fieldnames`, field **count**
  included, so a hand-edited label cannot pass), provenance (every `DataNode.path_key` resolves in
  `config/paths.yaml`, via a ~20-line Base indentation reader so runtime `[deps]` stays empty, ADR 0014),
  and structure (no dangling endpoint, orphan node, unrendered stage, empty stage or duplicate id).
  `gen_diagrams.jl`'s `main(ARGS)` is now guarded by `abspath(PROGRAM_FILE) == @__FILE__` — the test
  *includes* the script, and an unguarded run would regenerate the fixtures mid-test and destroy the
  signal. Alarm verified to fire both ways (perturbed ⇒ exit 1, restored ⇒ exit 0). Documents, for the
  first time, that F computes light competition, photosynthesis and respiration **per individual tree**
  while water demand is stand-level *as in the original*, and that the earlier single-representative-tree
  core was −42 % GPP / +45 % transpiration.
- **`docs/README.md` + `docs/notes/README.md`** — a layout index for `docs/`: what each subdirectory is,
  which CI gate it triggers (most of `docs/` triggers **none**), and where a new document belongs.

### Added
- **THE central production problem is now named and recorded: the patch ensemble**
  ([ADR 0092](docs/decisions/0092-the-patch-ensemble-is-the-central-production-problem.md); owner
  instruction 2026-08-07, *"a major gap in the whole strategy of the whole emulator project … document that
  as THE major thing to solve … that is the central task and challenge"*). LPJmL-FIT runs replicate patches
  because it is a **stochastic gap model** — it seeds random individuals and lets environmental filtering
  choose survivors. **Component S predicts that outcome directly, so the emulator does not need patches to
  do the filtering** — yet the coupled driver still evaluates the daily physics on **every** patch (ADR
  0057, correct for comparison validity). Consequence, now stated plainly: **the runtime-dominating term is
  unchanged from the C model, and the emulator's compute case rests almost entirely on skipping the
  ~1000-year spin-up, not on being cheaper per simulated day.** 25 patches stays fine for testing and
  validation; **production has no viable configuration yet**, and the planned 500-patch regeneration makes
  per-cell physics 20× worse — a global coupled online run at that scale is unaffordable. Records what a
  solution must not break (comparison basis · the nonlinearity `mean(f(state)) ≠ f(mean(state))`, with the
  measured counter-example that a *denser* patch produced slightly *less* carbon · within-patch suppression
  structure), an option space with **none preferred** (fewer / representative-stratified / effective stand
  + bias correction / hybrid), and four experiments — of which the **end-to-end emulator-vs-original timing
  has never been made**. **Status OPEN on purpose:** the owner has asked to decide the strategy in
  discussion, so the ADR frames rather than decides. Raised to the top of `MEMORY.md` §5 and
  `STEERING_PROMPT.md` as **P0★**, above P1–P6, with an explicit "do not pick a strategy unilaterally".
  **Standing disclosure obligation:** no claim that the emulator is "faster than LPJmL-FIT" without saying
  the saving is the spin-up.

### Fixed
- **The docs' Mermaid diagrams were never rendering — ALL of them, for months** (ADR 0091 amendment;
  found by the owner opening the built site). Every diagram was embedded with ```` ```@eval ```` +
  `Markdown.parse("```mermaid…")`, which reads correctly and produces a **grey code box of raw
  `flowchart LR` text**. DocumenterMermaid converts a fence with an *expander* matching nodes of the
  **parsed source AST** (order 7.9); an `@eval` block emits its output during that same expansion pass,
  after the matcher walked the node, so the fence is never converted. Measured on the built site: **0**
  `class="mermaid"` elements while DocumenterMermaid's `mermaid.esm.min.mjs` loader was injected on every
  page — renderer present and idle. **Nothing caught it because Mermaid draws client-side, so a green
  strict docs build is not evidence a diagram renders.** Fix: fences are now literal markdown inside
  `<!-- BEGIN MERMAID <name> … -->` markers that `scripts/gen_diagrams.jl` rewrites, and the two pages
  are `targets()` alongside the `.mmd`, so the staleness gate covers the embedded fences and page-vs-source
  drift is impossible. This fixes all five previously-dead diagrams on `docs/src/diagrams.md` as well as
  the new one. Verified on the rebuilt site: **5** mermaid elements on `diagrams.html`, **1** on
  `explanation/dataflow.html`, **0** code-block-wrapped `flowchart` occurrences. The check
  (`grep -c 'class="mermaid"' docs/build/<page>.html`) is now recorded in `CLAUDE.md` and the `julia-test`
  skill next to the regeneration commands.

### Changed
- **`docs/` reorganised (ADR 0091).** The ten loose engineering notes moved from the top level of `docs/`
  into `docs/notes/`; the general-audience LaTeX report moved to `docs/report/` and `docs/figs/` with it
  to `docs/report/figs/` (which keeps `\graphicspath{{figs/}}` valid — **the `.tex` is unchanged**). The
  notes were **misfiled, not obsolete**: every one is cited by name from live source and tests, and
  `phase3_fdiff_cbinary_validation.md` alone has 31 inbound references including `src/fdiff.jl` and about
  ten test files. References were rewritten in live files only; **append-only history**
  (`CHANGELOG.md`, `JOURNAL.md`, `docs/archive/**`, `changelog.d/*`) and the **immutable numbered decision
  records** keep the old paths, which correctly describe where the files were when written — both new
  READMEs record the move and date. Comment-only pointer fixes landed in three committed reference
  fixtures; **no baseline moved** (their readers skip `#` lines, so no compared value changed).
- **Corrected three places that documented the diagram gate as non-existent or local-only** —
  `CI.yml`'s path comment, `CLAUDE.md` §2/§9, and the `julia-test` skill (which explicitly said *"NO CI
  job runs this check … don't assume CI will catch it"*). The skill now also records the surprising
  trigger: an `src/interface.jl` field change reds the suite with no registry edit at all.
- **`docs/src/howto/build_docs.md`** absorbed the one unique tip from an untracked, mostly duplicate
  `docs/viewing_built_docs.md` (serving the built site over HTTP), which was then deleted; the page also
  gained the `DOCS_LINKCHECK=false` HPC note and a correction — the diagram alarm is enforced by the test
  suite, not by the `docs` job.
- **Component S — ONLINE transient boundary "Climbuf" BUILT ([ADR 0027](docs/decisions/0027-adopt-transient-boundary-production.md)'s "to build").**
  The coupled-run counterpart of S's offline pre-baked `boundary_series`: `ClimBuf` (`src/climbuf.jl`) is a
  per-cell trailing-W-yr climate ring (default `W=CLIMBUFSIZE=20`, mirroring FIT's Climbuf) the coupled driver
  feeds F's daily air temperature; each year end it recomputes the two TIME-VARYING boundary axes
  (`gdd5`/`tas_cold_month`, Thom-1966 monthly method) from the trailing-window climatology and refreshes the
  `FluxDrivenSlowEmulator`'s `s.boundary` BEFORE `reconcile_demography!` — so a warming cell's establishment
  gate shifts instead of freezing at the initial climatology. Wired as the opt-in `run_coupled_cell(...; climbuf=)`
  (default `nothing` ⇒ `s.boundary` constant, byte-identical, ADR 0027's static fallback); needs no
  SpeedyWeather (runs in the existing multi-year driver; P4 will reuse the object). **Offline parity (the
  ADR-0023 train/inference contract):** reproduces `scripts/build_transient_boundary.py` to
  float32-summation-order — daily→monthly max\|Δ\| 1.9e-6 °C; per-year window boundary 2000-2019 max\|Δgdd5\|
  3.7e-4 / max\|Δtcm\| 1.8e-7; the W=20 window ending 2019 == the committed DRF meta boundary
  (gdd5=1863.695 / tas_cold=0.2184). Conditioning-only (touches no carbon/water/energy). Gated by
  `test/testitems/climbuf_tests.jl` (parity + coupled wiring: conserves, deterministic, warming shifts the
  gate, guards) against the committed Hainich fixture `test/testitems/references/climbuf_hainich_*.csv`
  (`scripts/build_climbuf_parity_fixture.py`). Design doc flipped design→BUILT.
- **GLOBAL pooled multi-regime results + the honest static-vs-transient ablation.** The pooled+transient
  COUNT DRF generalizes to an UNSEEN climate regime almost perfectly — **hold-out-by-scenario R²=0.9847**
  (train on one regime, test the held-out other; both directions) ≈ the within-regime by-cell R²=0.9852. The
  pooled+transient COPULA reproduces both regimes' trait distributions (pooled OOS nqrmse 0.010–0.020).
  **Honest ablation (counts AND traits):** a STATIC-boundary pooled model gives the SAME COUNT scenario-holdout
  (R²=0.9844/0.9848); and the COPULA scenario-holdout (`eval_slow_copula_scenario_holdout.jl`) is MIXED,
  axis-dependent, both excellent (transient-vs-static avg KS: SLA 0.049/0.028, Wooddens 0.008/0.020, D95max
  0.012/0.019, minwscal 0.026/0.012 — all ≤ 0.05). ⇒ **In this constant-CO₂, flux-driven regime the TRANSIENT
  boundary delivers no clear, consistent win over STATIC — the FLUX DRIVERS (ADR 0020) carry the unseen-regime
  generalization for BOTH counts and traits.** The validated production win is the POOLED MULTI-REGIME
  flux-driven design (one model reproduces the unseen regime); the transient boundary stays opt-in/default-OFF,
  retained for physical correctness (a frozen establishment gate is wrong under +80 yr warming) and prospective
  N-limited / varying-CO₂ regimes where the slow bioclimate should matter — not promoted to default (its
  build/runtime/data-gen infra is kept at zero baseline cost). Reported honestly, no over-crediting.
  **Diagnosis follow-up ([ADR 0027](docs/decisions/0027-adopt-transient-boundary-production.md)):** the
  SLA/minwscal dip is REAL + seed-robust (a seed+100 re-run reproduces it, no winner flips — NOT noise), but
  is explained by neither boundary usage (importance ~identical ~0.44 across axes) nor space-for-time (spatial
  vs temporal gdd5→trait gradients don't map cleanly; traits are largely regime-invariant). Defensible read:
  out-of-range extrapolation of the copula's boundary→trait map on the held-out regime (ssp gdd5 ~+672 above
  the historic range) — axis-specific, net a wash (KS ≤0.05), decision unchanged. Tooling:
  `scripts/diagnose_boundary_axes.jl`, `scripts/diagnose_space_for_time.py`, a `SEED_OFFSET` hook in
  `eval_slow_copula_scenario_holdout.jl`. Future refinement: PER-AXIS copula conditioning (drop the boundary
  from SLA/minwscal). The **online-coupling Climbuf** was spec'd in
  `docs/online_transient_boundary_climbuf.md` and is now **BUILT** (see the top Climbuf entry).
  **Perf:** parallelized the copula OOS eval AND `DRF.predict(::Matrix)` (both were single-threaded → the
  global evals now run in minutes, bit-identically; suite green 106820 pass).
- **Component S — TRANSIENT (time-varying) bioclimatic boundary + the pooled-multi-regime design ([ADR 0026](docs/decisions/0026-component-s-pooled-multiregime-transient-boundary.md), refines ADR 0020, keeps ADR 0004).**
  The slow bioclimatic boundary (`gdd5`/`tas_cold_month`) was a per-cell CLIMATOLOGICAL-STATIC normal — identical
  every year (Hainich = 1863.70/0.2184 across all 20 historic years) — so a warming cell's establishment gate was
  FROZEN over the transient (the SSP feature table never even populated it → SSP ran on the historic climate mean).
  ADR 0026 makes it a **trailing-W-yr climatology** per (cell,year), mirroring FIT's ~20-yr Climbuf; scenarios pool
  into ONE environment-conditioned model (CO₂ stays constant, ADR 0004); eval adds hold-out-by-scenario. Default OFF
  ⇒ every committed baseline byte-identical (guardrail 4).
  - **Runtime (`src/components/slow.jl`).** `FluxDrivenSlowEmulator` gains an opt-in per-year `boundary_series`;
    `reconcile_demography!` advances `s.boundary` to this year's row (indexed by `s.year`, clamped) BEFORE building
    the feature row, so both the count-DRF features and the copula's `live_flux_cond` conditioning track the year's
    bioclimate. `boundary_series=nothing` (default) leaves `s.boundary` constant ⇒ byte-identical; a CONSTANT series
    reproduces the static boundary bit-for-bit (tested). JET-clean (bind-then-narrow the `Union{Nothing,…}` field).
  - **Data-gen (`scripts/build_transient_boundary.py`).** Recomputes `gdd5` (Thom-1966 monthly, identical to the
    static climclusterpy method) + `tas_cold_month` on a trailing window from the orderA daily temperature `.clm`,
    header-driven (handles the v3-float32 HIST + the v2-int16 SSP °C×10 layouts). VERIFIED: a W=20 window ending 2019
    reproduces the static Hainich `gdd5=1863.695`/`tas_cold=0.2184` bit-for-bit; global tables built for both
    scenarios (SSP370 Hainich warms Δgdd5=+605, Δtas_cold=+1.79 °C over 2020→2100; global mean Δgdd5 +672).
  - **Build table (`scripts/build_slow_runtime_table.py`).** `BOUNDARY_WINDOW=W` opt-in swaps the per-cell static
    boundary mean for the per-(Cell,Year) transient join (count + copula modes); boundary column order/names
    unchanged (feature-order contract preserved); default (unset) = static = byte-identical.
  - **Pooling (`scripts/pool_slow_tables.py` + `scripts/run_pooled_slow_training.sh` + `scripts/eval_slow_scenario_holdout.jl`).**
    Row-concatenate per-scenario transient tables into ONE multi-regime table (per-row `scenario.i64` tag; AR
    `n_prev` stays within-scenario so it never splices two climate models); the orchestration builds both
    scenarios' transient count tables → pools → trains ONE cell-agnostic count DRF → runs the HOLD-OUT-BY-SCENARIO
    unseen-regime eval (train on the other regime, test the held-out one) + a pooled by-cell baseline. Validated
    on the Hainich pooled table. The pooled+transient count DRF **held-out-by-cell TEST R²=0.9852** (5295 test
    cells / 7.6M rows on the 77.6M-row pooled table).
  - **Pooled copula (`scripts/run_pooled_slow_copula.sh` + build-script `STEM_CAP`).** The same pooling for the
    recruit-trait copula: an opt-in per-cell `STEM_CAP` (default 0 = keep all → byte-identical) random-subsamples
    each cell's surviving stems (a marginal + per-cell KS needs only a few hundred), so the pooled copula
    (~730M stems un-capped) stays tractable; `pool_slow_tables.py` auto-detects the copula table (Xc / Y_axis).
    Global historic copula OOS (pre-pooling, K-fold-by-cell, 133M stems): nqrmse SLA 0.016 / Wooddens 0.022 /
    D95max 0.028 / minwscal 0.038.
- **P1 Tier-1 v3 — Component S owns establishment as REAL cohorts: dynamic roster (recruit APPEND + K-cap MERGE),
  a TRUE per-cohort age, and the copula recruit-trait sampler wired in ([ADR 0024](docs/decisions/0024-component-s-dynamic-membership-and-true-age.md), supersedes ADR 0023 §3).**
  The last structural piece of P1 — the flux-driven S now genuinely owns count/establishment/mortality/trait
  spread (ADR 0018), not just a fixed-roster density nudge. Confined to `FluxDrivenSlowEmulator` (Tier-0 stays
  fixed-roster); opt-in, zero new runtime `[deps]`.
  - **Dynamic cohort roster (design risk #5 closed).** Establishment now APPENDS a real age-0 recruit cohort
    (`dn=(ρ−1)·dtree`; fixed sapling or copula-sampled traits) instead of mixing into an existing cohort; a
    K-cap MERGE (`_apply_kcap_merge!`, deterministic smallest-|Δheight| scan) bounds the roster; and
    `_commit_membership!` atomically rebuilds EVERY length-K `FDiffFastCore` field (pools/tmpls/inds/pft_ids +
    a REALLOCATED `bm_inc_acc`, `inds` last over `_patch_fpars`) plus `s.age`/`recruit_idx`. Carbon routes on
    `vegc_full_ind`: APPEND→`record_estab!`, MERGE→carbon-neutral (nind-weights all 5 pools incl `sapwood_bg_c`,
    re-derives pipe-model height + Jucker crownarea).
  - **True per-cohort age (supersedes ADR 0023 §3's counter).** Recruits enter at age 0, merges nind-weight
    parent ages, `s.age .+= 1` is the sole increment; `flux_feature_vector`'s `age_mean` is now the nind-weighted
    tree-only mean. The DRF is retrained on `mean(Age−1)` per living stem (start-of-year age; ind `Age` is
    post-increment), and `build_slow_runtime_table.py`/`train_slow_drf.jl` carry an `age0` seed (median training
    age ≈43.6) into the DRF meta that the coupled builders read (`age0=`) so the runtime feature starts inside
    the trained band — the coupled gates assert `age0>0` (a dropped wire-up would silently re-open the OOD shift).
    Retrained `drf_forest_hainich.drf` + `_meta.txt` (40 trees, in-sample R²=0.977, nfeat unchanged=15).
  - **Copula recruit-trait sampler WIRED (ADR 0023 §4c consumer).** `FluxDrivenSlowEmulator` gains an opt-in
    `recruit_copula::RecruitCopula` (default `nothing` ⇒ fixed sapling, gates unaffected); when set, the APPEND
    path draws `sample_copula!(s.rng, …)` deterministically and maps traits→recruit pools. Production axis
    artifacts + correlation matrix deferred to P3 (single-cell beech trait axes are near-degenerate).
  - **[VERIFIED] `test/testitems/slow_membership_tests.jl` (4 testitems, incl Float32).** A coupled run that
    APPENDS and MERGES completes with all six roster arrays mutually length-consistent (risk #5); carbon
    conserves ~2e-12 gC (Float64) / ≤1e-5·C_scale (Float32) across append+merge incl a seeded `sapwood_bg`
    cohort; age develops genuine per-cohort spread (survivors age +N, recruits enter at 0); the copula hook is
    live + deterministic. Gate-3 oracle RE-MEASURED on the C `ind` ≥5 m basis (the C writer excludes sub-5 m
    saplings; residual-diagnosis basis alignment): nqrmse ≈0.39 (was ~0.31), median ratio ≈1.25, count ratio
    ≈0.67 — the honest recursive-vs-non-recursive drift, all in-band; the drift alarm moved to 0.45 with the
    documented re-measurement. Hainich-only scaffolding.
- **P1 Tier-1 Step 4 — the PRODUCTION Component-S DRF loads from a serialized artifact + a runtime-consistent
  training table + the Gate-3 oracle + the copula recruit-trait sampler ([ADR 0023](docs/decisions/0023-component-s-production-drf-runtime-consistency.md)).**
  Closes the gap that Step 3's in-loop test used an in-test DRF — the model that is validated is now the model
  that runs. Zero new runtime `[deps]` (all pure Base, ADR 0014).
  - **(4a) DRF serialization + production artifact.** `DRF.save_forest`/`load_forest` (`src/drf.jl`) — a pure-Base
    text round-trip (magic `LPJMLFIT_DRF` + version; Float64 via Julia's shortest round-trippable decimal),
    verified **BITWISE** (predictions strict `==`, both `store_values` modes, NaN fill, ragged leaf values).
    `scripts/build_slow_runtime_table.py` builds a **runtime-consistent** feature table (exact
    `flux_feature_vector` order; `water_stress`=1−wscal_mean — fixing the OOD-table `mort_water`-inversion
    mismatch; `age_mean`=elapsed-year counter, NOT mean Age — closing the biggest train/inference-shift risk;
    `soilmoist`/`lai` documented proxies pending the global C-`LAI_STAND`/`swc` pipeline). `scripts/train_slow_drf.jl`
    fits + serializes the committed Hainich demo artifact `test/testitems/references/drf_forest_hainich.drf`
    (40 trees, ~95 KB, in-sample R²=0.975) + a meta/golden file.
    - **[VERIFIED] `test/testitems/slow_production_drf_tests.jl`:** the LOADED production DRF drives the coupled
      Hainich loop — predicts counts INSIDE its training band (targets 9.5→6.9, no wild extrapolation ⇒
      runtime-consistent), MOVES tree N (F alone holds it fixed), conserves carbon at the S↔F handoff to ~1e-12 gC,
      energy closes (7e-15), deterministic under seed. `drf_serialization_tests.jl` gates the round-trip + the
      committed artifact's golden (feature→prediction) pairs bitwise.
  - **(4b) Gate-3 oracle** (`test/testitems/slow_oracle_tests.jl`; `scripts/build_slow_oracle_reference.py` →
    `references/hainich_slow_oracle_{traits,counts}.csv`). The coupled flux-driven S size distribution matches the
    LPJmL-FIT C ground truth at Hainich (cell 42490): nind-weighted Height quantiles vs the C truth to
    IQR-normalized quantile-RMSE **~0.31** (median 8.9 vs 7.9 m), framed honestly as a recursive-coupled-S
    vs non-recursive-C-truth **drift alarm** (Hainich-only), not a parity gate.
  - **(4c) Gaussian-copula recruit-trait sampler BUILT** (`src/drf.jl`: `chol_lower`, `norminv` [Acklam],
    `normcdf` [A&S 26.2.17], `GaussianCopula`, `copula_uniforms!`, `sample_copula!`). Draws correlated recruit
    traits {logHeight, Age, SLA, Wooddens, beta_root} via the Cholesky of a committed correlation matrix mapped
    through the per-axis flux-conditioned `predict_quantile` marginals — the pure-Base analog of the sibling's
    `ResidualRegressor.sample_u`. **[VERIFIED] `test/testitems/drf_copula_tests.jl`:** recovers a target
    correlation from draws (±0.03), induces positive trait correlation, deterministic under `Xoshiro256pp`,
    Cholesky round-trips + guards non-PD. Its consumer (assigning drawn traits to APPENDED recruit cohorts) lands
    with the membership append/merge path (design risk #5); until then survivors keep frozen traits.
  - **Still open (v3, documented):** the GLOBAL runtime-consistent DRF (C-`LAI_STAND` + daily `swc`, many cells,
    C-truth demography target — a Phase-2 SLURM pipeline); wiring the copula into establishment; the in-loop OOD
    win; promoting the runtime `age_mean` to a true per-cohort mean age + retrain (ADR 0023 §3).
- **P1 Tier-1 Step 3 — the FLUX-DRIVEN Component S is IN the coupled loop (ADR 0020/0021/0022).**
  `FluxDrivenSlowEmulator{T} <: AbstractSlowEmulator` (`src/components/slow.jl`) sets the demography TARGET
  from the trained flux-conditioned DRF instead of Tier-0's constant rate: each year S builds a flux feature
  vector (F's delivered `FToS` fluxes + this-year patch state + the recursive AR count + a baked slow
  bioclimatic boundary), predicts the target with the DRF, and moves the coupled tree density toward
  `target/n_prev` (a UNIT-FREE ratio — the count↔density gap cancels) through the SAME carbon-conserving
  mortality/establishment machinery as Tier-0. Wires in via the existing `reconcile_demography!` interface
  (no change to `run.jl`); opt-in behind `run_coupled_cell(...; slow=)`, `slow=nothing` byte-identical
  (guardrail 4). Zero new runtime `[deps]`/`[weakdeps]` (the DRF + Xoshiro are pure Base, ADR 0022).
  - **[VERIFIED] Gates (Hainich 42490, `test/testitems/slow_flux_driven_tests.jl`; full CI-faithful suite
    green 48127 pass / 0 fail / 4 broken):** the DRF target DRIVES the demography (a decline-predicting
    forest shrinks N 0.076→0.013 indiv/m², a growth-predicting forest grows it 0.076→0.26, monotone in the
    predicted direction); the S↔F handoff CONSERVES carbon to **~1e-12 gC ≪ the 1e-6·C_scale gate** in both
    directions; energy still closes (1.4e-14); the coupled N trajectory is DETERMINISTIC under a seed; and it
    is type-stable + conserving in **Float32** (the SpeedyWeather-coupling type).
- **P1 Tier-1 Step 2 — the flux-driven premise is VALIDATED + a zero-dep native-Julia DRF (ADR 0020/0021/0022).**
  The falsifiable ADR-0020 success test now has a result on the warm+dry OOD holdout (space-for-time SSP370
  proxy), and it **supports ADR 0020** three independent ways. New pieces:
  - `src/drf.jl` (`module DRF`) — a **zero-dependency** distributional random forest in pure Base Julia
    (hand-rolled Xoshiro256++ RNG; subbagged variance-reduction trees; leaves optionally store sample values
    for quantile/distributional queries; per-tree-seeded ⇒ multithreaded fit is bit-reproducible). This is the
    model the flux-driven S will use — trained AND run natively, no new `[deps]`/`[weakdeps]`
    (**[ADR 0022](docs/decisions/0022-component-s-handrolled-drf.md)**; EvoTrees verified available as a fallback
    but deliberately not adopted, to keep the trusted-physics CI free of dependency-churn risk).
  - `scripts/build_slow_count_table.py` — the biome-scale count-model table (1,323,905 rows / 4000 lat-stratified
    tree cells / 400 warm+dry holdout cells) carrying BOTH channels (flux drivers + patch state + AR + slow
    boundary; and the DirectEmulator's raw climate + climatology + the SAME boundary) so the comparison is
    apples-to-apples; `scripts/export_count_matrices.py` dumps a zero-dep raw-Float64 payload;
    `scripts/flux_ood_experiment.jl` fits the DRF on each channel and scores in-distribution vs OOD;
    `scripts/sbatch_python.sh` (the Python twin of `sbatch_julia.sh`).
  - **[VERIFIED 2026-07-22] OOD verdict** (living-tree count / patch; DRF, seed 1): climate-only fails OOD
    (**R²=−0.16**, ≈ the boundary floor — the documented equilibrium-ML failure, reproduced); the flux-driven S
    as designed beats it **2.35×** (OOD MAE 0.68 vs 1.59, **R²=0.76 vs −0.16**); fluxes ISOLATED (no AR/state)
    still beat climate **1.25×** OOD; and holding recursion fixed, flux+AR (R²=0.76) far exceeds climate+AR
    (R²=0.43). Honest nuance: AR/persistence alone reaches OOD R²=0.55, but flux-conditioning adds decisive OOD
    generalisation on top of both climate and recursion. `⇒ ADR 0020's flux-driven premise is validated.`
- **P1 Tier-1 Step 1 — flux-conditioning training data (ADR 0020/0021).** `scripts/build_slow_flux_table.py`
  builds the per-(cell,year,patch,individual) FToS-mapped table for the flux-driven Component S from the
  tier-1 annual `ind` parquet (`/p/tmp/jamirp/emulator_global/ind_hist_seed{1,2}_all.parquet`) + the daily set
  + the slow bioclimatic boundary (`cell_year_feats.parquet`) + CO₂ — no C-binary re-run needed. `bm_inc ← npp`
  (runtime-consistent with `FToS.bm_inc`), `growth_eff` inverted from `mort_npp`, stress inverted from
  `mort_water`/`mort_temp` + daily within-year statistics, AR state from the prev-year distribution summary.
  Parameterised by `CELLS` (Hainich 42490 first, then the biome set). Committed fixture
  `test/testitems/references/slow_flux_table_hainich.csv` (82 rows) + `slow_flux_table_schema.json`.
- **Physics re-verified on real data (spec §7):** `mort_age` recompute matches the emitted column to **4.97e-8**
  and the `mort` additive identity to **8.99e-7** across 5052/5307 real Hainich rows — confirming the
  `[VERIFIED]` beech mortality parameters against the C oracle.

### Fixed
- **`docs/slow_flux_conditioning_data_spec.md` corrections + a new `[VERIFIED]` finding.** (1) §2 wrongly listed
  `stemdiam/crownarea/leafarea/fpc` as present in the annual TXT `ind` output — they are RAW-only (only
  `fpc_ind` is TXT). (2) Pinned the parameter hazards: `mort_age` longevity = JSON key `"age"` = 400 (NOT the
  leaf `"longevity"` = 2.0, a ~200× trap); `k_mort` = 0.01; `mort_prob` is saved AFTER the cap/immediate-death/
  ghost-tree overrides (components don't sum on override rows). (3) **AGE OFF-BY-ONE:** the emitted `Age` is the
  post-increment year-end age, but the row's `mort_*` were computed with the pre-increment age (`Age − 1`) —
  recompute matches to 5e-8 with `Age − 1` vs 1.4e-4 with `Age`; the table carries `age_mort = Age − 1`.
  (4) Tier-2 RAW cannot yield `bm_inc`/`nind`/`turnover` (absent from `Output_ind`); the exact path is a small
  tier-3 patch, and the budget signal is the emitted `npp`/`anpp` (not the post-allocation `pft->bm_inc.carbon`).
- **P1 wiring made runnable + a regression it exposed.** The uncommitted Tier-0 work had never been executed:
  `stand_structure_tof` referenced a `SoilColumn.soildepth` field that did not exist — added it (populated by
  `hainich_soilcolumn` from the `soildepth` kwarg it already receives; the one positional `SoilColumn(...)`
  call in `scripts/grass_drought_rooting_probe.jl` updated to match). Replacing the old
  `step!(::AbstractSlowEmulator,…)` stub with `reconcile_demography!` broke `limiting_cases_tests.jl:38`
  (it expected the old stub to throw `ErrorException`, now a `MethodError`) — updated it to assert the new
  abstract `reconcile_demography!` fallback throws. Caught by the first full SLURM suite run.
- **Multi-cell biome gate — corrected an over-strict latent-heat assertion to the true, BOUNDED invariant.**
  `test/testitems/biome_coupled_tests.jl` asserted `all(le ≥ −1e-9)`, but F's ET is built from `smoothmin`
  (fdiff_smoothops.jl) and `smoothmin(a, b, β) ≤ min(a, b)` undershoots by ≤ log(2)/β EVEN for `a, b ≥ 0`.
  In the fully water-depleted dry-season corner the semi-arid Sahel cell hits `le ≈ −0.6 W/m²` (physical
  ET = 0; this model has no dew/condensation term) — a bounded smooth-surrogate artifact of the committed F
  core, harmless to E's closure (`H := Rn − LE − G` absorbs it). Assert the bound (`le ≥ −2 W/m²`) instead of
  exact non-negativity; full CI-faithful suite green (47906 pass / 0 fail / 4 broken).
- **Component E — documented two `solve_seb` stability-correction caveats** (no behaviour change): the 0.25×
  suppression floor deliberately UNDER-suppresses strongly-stable nocturnal turbulence and is load-bearing
  for the coupled `|T_skin − T_air|` gates; the effective `g_a` is not re-clamped to `[ga_min, ga_max]` after
  the stability multiply (the bound is intentionally on the NEUTRAL conductance; safe as `g_a` is never a
  denominator and `EToF.g_a` is not consumed downstream).

### Added
- **P1 — COMPONENT S IS IN THE COUPLED LOOP (Tier-0): the project's novelty now runs (ADR 0018/0019/0020).**
  `DemographicSlowEmulator` (`src/components/slow.jl`) is the concrete slow emulator wired into
  `run_coupled_cell(...; slow=)`: each year F grows every representative cohort's CARBON at fixed `nind`
  (`grow_annual_accounted!`), then S applies its **demography** — count `N`, establishment (fills the open
  canopy `max(1−Σfpc,0)` into the shortest tree cohort, mixing a fixed sapling), mortality (growth-efficiency
  rate → litter) — routing every carbon movement through a `CarbonLedger`. **Tier-0 is deterministic,
  physical-rate, ML-free (runtime `[deps]` stays EMPTY)** and, per ADR 0020, already **flux-driven** (the
  rate channel reads `FToS.growth_eff`/`water_stress`/`soilmoist` — F's delivered fluxes — not this-year raw
  climate). **Gates met on Hainich (`test/testitems/slow_demography_tests.jl`):** Gate-1 — S runs ≥20 yr,
  energy still closes (1.4e-14 W/m²), and the count `N` evolves year-to-year while the fixed-N F baseline
  holds tree `N` constant (so the change is causally S); Gate-2 — the S↔F handoff conserves carbon to
  **~3e-12 gC ≪ the 1e-6·C_scale gate** on forced N-up / N-down / seeded-`sapwood_bg` / stagnating-cohort
  years; Gate-4 — a FIXED roster of K persistent cohorts (the structural basis of the speed-up; timing via
  `scripts/bench_slow_speedup.jl` off the login node). New `run.jl` `stand_structure_tof` re-derives the full
  `SToF` (incl. D95 rooting depth) from the S-updated population. `slow=nothing` stays byte-identical to the
  pre-S self-growing path. Independently verified by three adversarial reviewers (conservation refutation +
  correctness + test-adequacy). **Tier-1 (flux-conditioned ML inference + the warm+dry OOD benchmark) is the
  next step, now in P1 scope per ADR 0020.**
- **Durable SLURM job infrastructure — long jobs survive session teardown.** `scripts/run_tests_slurm.sh`
  runs the CI-faithful suite (`rm test/Manifest.toml` + fresh re-resolve → `Pkg.test()`) on a compute node,
  and `scripts/sbatch_julia.sh <tag> ...` submits any Julia work the same way; both warm the shared `~/.julia`
  depot on the login node first (compute nodes reach the pkg-server but not GitHub), log to `logs/<tag>.<jobid>.out`
  with a `JOB DONE … exit=N` marker, and are collectable from any later session (`squeue`/`sacct`/the log).
  Documented as the standing default in CLAUDE.md §2 + the `julia-test` skill. [VERIFIED green end-to-end.]
- **PHASE 5 — MULTI-CELL / BIOME GENERALIZATION: the coupled emulator runs across the full climate
  envelope, energy closing everywhere (DEVELOPMENT_PLAN §6 Phase 5).** `scripts/extract_biome_forcing.py`
  pulls REAL GSWP3-W5E5 daily forcing (the model-grid `_test` `.clm`, YEARCELL float32 — the validated
  grid whose cell 42490 = Hainich) for five biome-representative cells and commits small per-cell CSVs
  (`test/testitems/references/biome_forcing_{boreal_siberia,temperate_hainich,mediterranean_iberia,
  semiarid_sahel,tropical_amazon}.csv`, decade 2010–2019). `scripts/run_coupled_biomes.jl` drives the
  coupled S+F+E loop with a COMMON canopy across all cells (isolating the climate effect) and reports the
  emergent, climate-driven energy partitioning:
  - boreal (−7 °C): LE 24, H 9, low fluxes + cold skin; temperate (9 °C): LE 43, Bowen 0.26;
    mediterranean (15 °C): **Bowen 1.27 (H-dominated, summer-dry)**; semi-arid (30 °C): **Bowen 0.87,
    H 72 (water-limited)**; tropical (28 °C, 2158 mm): **LE 102, Bowen 0.10 (LE-dominated), GPP 2275**.
  - **Energy closes to ≤ 3e-14 W/m² in EVERY regime.** Gate `test/testitems/biome_coupled_tests.jl`:
    closure + physical bounds for all five biomes, plus the emergent ordering (tropical LE > boreal;
    dry-biome Bowen > tropical Bowen; tropical Rn > boreal Rn). Honest scope: a common (non-biome-
    calibrated) canopy + constant wind/psurf isolate the climate signal — biome PFT parameters + spin-up
    are the documented next step. Runtime `[deps]` EMPTY.
- **COMPONENT E FIDELITY — Monin–Obukhov surface-layer STABILITY correction on `g_a` (ON by default).**
  The neutral log-law over/under-states turbulent exchange under buoyancy; `H` is the residual and the
  worst-modeled flux (PLUMBER2), so this is the highest-value E refinement. `solve_seb` now multiplies the
  aerodynamic conductance by a smooth, bounded stability factor of the bulk Richardson number
  `Ri_b = g(z−d)(Tair−Tskin)/(Tair·U²)`: `Fs(Ri) = 1 − stab_amp·tanh(stab_k·Ri/2)` (∈ [0.25, 1.75], `Fs(0)=1`,
  C∞ ⇒ AD-safe), solved jointly with `T_skin` by a Picard-coupled fixed-graph Newton (`n_newton` 12→25).
  **Verified:** stable nights suppress `g_a` ⇒ stronger radiative cooling; unstable days enhance `g_a` ⇒ hot
  surface ventilated; closure stays EXACT (machine precision) and the aerodynamic identity holds to ~2e-9;
  ForwardDiff-vs-FiniteDifferences still matches, Float32 clean (`energy_closure_tests.jl` gains a stability
  testitem). Toggle with `SEBParams(enable_stability=false)` for the neutral limit. Runtime `[deps]` EMPTY.
- **PHASE 4 — COMPONENT E (surface energy balance + skin-temperature closure) IMPLEMENTED, and the
  end-to-end coupled S+F+E emulator RUNS on a cell (DEVELOPMENT_PLAN §6 Phase 4; ADR 0017).** The
  ESM-ready closure LPJmL-FIT lacks — the reason the whole project exists — was a stub that only threw;
  it is now real, and F+E run coupled over a cell producing the atmosphere-facing outputs.
  - **`src/components/energy.jl`: `SEBEnergyClosure` + the pure kernels `solve_seb` / `aerodynamic_conductance`.**
    Solves ONE skin temperature `T_skin` from `Rn(T_skin) = SW(1−α) + ε·LW − εσT_skin⁴` and closes
    `Rn = LE + H + G` with `H = ρc_p g_a (T_skin − Tair)` — **LE fixed by F (water-limited), H the
    residual** (the documented "no privileged residual" exception). Fixed-iteration damped Newton with a
    FIXED graph (AD-friendly, the `solve_lambda` pattern); `g_a` from the neutral log-law; `G = λ_g(T_skin
    − T_soil)` with a deep-soil-temp EWMA state E owns. Demand cap (`LE ≤ Rn − G`) implemented but OFF by
    default (uncapped ⇒ exact closure + conservation-safe; capping would drop water F committed to until
    the unused-water return is wired). **Self-contained — no Terrarium.jl runtime dep** (ADR 0017
    supersedes 0006's reuse: open AGPL↔EUPL licensing blocker + the zero-runtime-deps/offline-node
    constraints, exactly as ADR 0014 did for the fast core; physics decisions retained).
  - **`src/run.jl`: the coupled run loop `run_coupled_cell` / `couple_day!` / `stand_structure_toe`.** Per
    day: F (`FDiffFastCore.step!`) → `FToE`; structure (`SToE`) re-derived from F's own prognostic canopy;
    E (`solve!`) → `EToATM` (LE, H, G, T_skin, NBP_atm, z0) + `EToF`; **the mandatory E→F skin-temperature
    feedback** hands `T_skin` back to F's phenology soil-temp gate for the next day. Water & carbon
    conserved by F; energy closed by construction in E.
  - **`FDiffFastCore` gains two fields** — `soiltemp_skin` (the E→F feedback; NaN default ⇒ air-temp proxy
    ⇒ BYTE-IDENTICAL to the pre-feedback adapter) and `last_albedo` (write-only diagnostic so E's Rn uses
    F's dynamic albedo). Every existing baseline + the AD trainer untouched.
  - **Verified (`test/testitems/energy_closure_tests.jl` + `test/testitems/coupled_run_tests.jl`):** energy
    closes to **machine precision** (max |Rn−(LE+H+G)| = 1.4e-14 W/m² over a 13,824-case grid AND every
    day of a real Hainich year); `solve_seb` is AD-friendly (ForwardDiff vs FiniteDifferences) + Float32;
    the coupled Hainich year is physically plausible (skin near air, day heating / night cooling, growing-
    season LE > winter). Full CI-faithful suite green.
  - **DEPLOYMENT DEMONSTRATION (`scripts/run_coupled_cell.jl`):** the coupled emulator run over the Hainich
    cell (25 patches, cell-mean) for the committed decade 2009–2019 produces the full ESM output series and
    **emergently captures the 2018 European drought** — summer Bowen ratio 0.89 vs ~0.15–0.29 in normal
    years (water stress → ET suppressed → sensible heat up), with annual-mean G ≈ 0 (no spurious heat
    sink) and no multi-year drift. Writes `logs/coupled_decadal_hainich.csv`.
  - **Honest scope:** wind + surface pressure are held constant (the underlying LPJmL run never used them;
    the committed forcing CSV omits them) — sourcing GSWP3-W5E5 `sfcwind`/`ps` is the documented next step;
    `g_a` is neutral-only (a stability correction is the next fidelity step); LE uses vaporization λ for all
    ET (a snow-sublimation split is pending); the slow emulator S is not yet wired into deployment (F
    self-computes its structure); E's LE/H/T_skin against FLUXNET/PLUMBER2 is the external-data-bounded
    validation still to source (Hainich = DE-Hai). Runtime `[deps]` still EMPTY.
- **IMPLEMENTED the below-ground root-sapwood pool `sapwood_bg` + its phen-gated maintenance (opt-in,
  default byte-identical) — the §8-GO'd tree-CUE frontier (Phase-3 scale-up step 11 follow-up #11;
  `docs/sapwood_bg_design.md` §8).** F_diff omitted the C's below-ground root-sapwood pool, so it never paid
  that pool's phen-gated maintenance respiration and its tree CUE (NPP/GPP) sat ~0.51 vs the C's ~0.46.
  - **`TreePools` (10→11 fields) + `Individual` (16→17 fields)** gain `sapwood_bg_c` / `c_sapwood_bg`, each
    with a **backward-compatible constructor** (the old arity fills the pool with 0), so all ~33 existing
    construction sites — including the Enzyme SoA trainer `rollout_canopy_years_gpp` and every committed
    baseline — are **byte-identical**. `autotrophic_respiration` gains a default-0 `c_sapwood_bg` kwarg adding
    the phen-gated soil-temp maintenance `phen·c_sapwood_bg/cn_sapwood` (`npp_tree.c:51`); `daily_step_canopy`
    passes `ind.c_sapwood_bg·nind` (trees only). `individual_from_pools` + `grow_individual` carry the pool.
  - **`reconstruct_sapwood_bg(sapwood_c, height, wooddens, rootdist, soildepth)`** seeds the pool at init from
    the C's C_LATERAL allocation demand (`allocation_tree.c:163-189`, verbatim), required because the
    emulator's fixed demography can't bootstrap the C's `>0`-gated pool growth (design §4.1).
  - **Verified in-model (new `test/testitems/sapwood_bg_tests.jl`):** on the committed Hainich 2010 cell,
    seeding the pool moves tree CUE **0.512 → 0.497** (the growth-respiration-rebated decrement the model
    applies), **GPP byte-identical** (maintenance changes NPP, not GPP), CUE stays inside the gate band
    `[0.42, 0.56]`; the reconstructed pool is 531.4 gC/m² (22.7 % of above-ground sapwood) — matching the §8
    probe. Grass seeds 0 (a tree pool). Full CI-faithful suite green.
  - **Scope:** the pool is STATIC-seeded; its prognostic C_LATERAL growth + carbon-debt (design §5.4), the
    Enzyme SoA `sapbgcs` thread, and flipping the seed on by default (with baseline regeneration) are the
    deferred next steps. Runtime `[deps]` still EMPTY.

### Changed
- **RAN the mandated `sapwood_bg` quantification probe → GO (Phase-3 scale-up step 11 follow-up #10;
  `docs/sapwood_bg_design.md` §8).** The design (`sapwood_bg_design.md` §7) required a scripts-only probe to
  predict the tree-CUE decrement of adding the C's below-ground root-sapwood pool BEFORE the invasive
  `TreePools`/`Individual` struct change. `scripts/sapwood_bg_quantification_probe.jl` reuses the validated
  F_diff kernels for the baseline (the CUE-gate's own `mkind` + `rollout_daily_canopy`), reconstructs
  `sapwood_bg` per tree from the C_LATERAL demand (`allocation_tree.c:163-189`, verbatim), and adds only the
  phen-gated maintenance term (`npp_tree.c:51`). Reproduced twice, identical. No `src/`/`test/` change;
  `[deps]` still EMPTY.
  - **GO, and the design §4.2 floor-break fear is REFUTED.** Pool = 531.4 gC/m² (22.7 % of above-ground
    sapwood); ΔRa_bg = 24.3 gC/m²/yr (1.94 % of GPP); CUE moves 0.5118 → 0.4924 (conservative) / 0.4973
    (growth-resp-adjusted). Every prediction incl. the ±30 % band (0.487–0.498) stays inside the gate
    `[0.42, 0.56]` with large margin — no floor-break, struct plumbing de-risked.
  - **HONEST CAVEAT:** `sapwood_bg` ALONE closes only ~40–50 % of the 0.51→0.46 gap (lands ~0.49, ~0.03 above
    the C) — a validated fidelity refinement of an already-in-band metric, not a full closure. Full closure
    needs the coupled `rd`-gate too (design §6, which partially cancels). GO is on the physics + de-risking;
    spending the 2–3 implementation sessions now vs. after higher-value frontiers is a sequencing call.
- **SCOPED the per-PFT competitive water-supply fix + CORRECTED the §26.4 diagnosis in two load-bearing ways
  (Phase-3 scale-up step 11 follow-up #9; `docs/water_supply_perpft_design.md`, docs §26.4 CORRECTION #2).**
  A code-verified deep-read of `water_stressed.c` + `daily_natural.c` vs `daily_step_canopy`, turning §26.4's
  "FIX DIRECTION" into an implementable design. Diagnosis/design only — **no `src/`/`test/` change**, `[deps]`
  still EMPTY.
  - **The mechanism sharpens to the `aet_cor` competitive per-layer supply cap ALONE.** §26.4 bundled the fix
    as "per-PFT `wscal` + the sequential competitive cap"; the source shows the `wscal` half is DEGENERATE in
    this FIT config — `EMAX_ANGIO = EMAX_GRASS = 10.0` (`par/pft_lpjmlfit.js:116-118`) and grass shares beech's
    `beta_root=0.8`, so per-PFT `wscal` is ≈identical between grass and trees and feeds only phenology +
    allocation, not the within-day GPP solve. The entire 2018 grass overshoot rides on `aet_cor`.
  - **`-DPERMUTE` makes an exact faithful port structurally impossible on the AD/deterministic path.** The FIT
    build (`/home/jamirp/lpjml56fit/Makefile.inc:22`; all `config/Makefile.*` platform templates) re-draws the
    PFT depletion order EVERY day via Fisher-Yates on the cell RAND48 seed, so there is no deterministic
    "trees-first" to port — the C's grass suppression is an order-averaged stochastic outcome. A deterministic
    approximation would over-suppress; a faithful replication is non-differentiable + non-deterministic (breaks
    Enzyme/ForwardDiff + `determinism_tests`); and the `aet_cor` cap is a loop-carried read-modify-write
    accumulator directly on the trained-GPP reverse path.
  - **Recommendation: DEFER** behind the `FluxHooks` learned per-individual correction (already sees `wr` +
    per-individual `apar`), exactly as the §26/§26.1 grass LEVEL gap was deferred; pursue the structural cap
    only if the learned lever proves insufficient. Two scripts-only de-risking probes specified before any
    `src/` edit (a deterministic-vs-Monte-Carlo-PERMUTE `aet_cor` magnitude probe + an Enzyme-feasibility spike).
- **The `FDiffFastCore` deployment adapter reaches `rollout_canopy_years` GRASS parity (Phase-3 scale-up step
  11 follow-up #8; docs §27).** §26.3 flipped the self-driven rollout to the validated-faithful grass config
  but the `FDiffFastCore` SharedState adapter (`src/components/fast.jl`, the ESM coupling surface) still grew
  grass with the TREE machinery. Now it mirrors `rollout_canopy_years`, all **grass-only**:
  - **Per-PFT GSI phenology** (per-DISTINCT-PFT filters + lag-1 forest-floor light `grass_lf` for grass,
    carried as persisted struct state since the adapter is day-by-day), the **§26 demand-gate** (constructor
    wraps `params` via `_with_grass_gate`), **grass allocation** (`grow_grass_individual`), and **grass
    establishment** (re-seed when patch FPC < 1).
  - **Nothing regresses:** a tree-only core is **byte-identical** (per-PFT phenology for an all-id-3 patch is
    the same beech GSI; gate/alloc/establishment are `is_grass`-gated). The **AD trainer**
    `rollout_canopy_years_gpp` is untouched (a separate function; this adapter is the non-AD deployment
    surface). No new exports; runtime `[deps]` still EMPTY.
  - **Test:** the `FDiffFastCore` gate (`test/testitems/coupling_tests.jl`), previously tree-only, now also
    drives a mixed tree+grass core 4 coupled years — grass finite, non-negative, no woody pools/height (grass
    allocation ran), trees grow; establishment payoff checked as a provably-≥ differential (survival is
    light-dependent, so not asserted). Full suite **26,214 pass / 0 fail / 4 broken**.
- **DIAGNOSED the 2018 warm/dry-year grass-NPP amplitude residual — a GENUINE grass water-supply gap (Phase-3
  scale-up step 11 follow-up #7; docs §26.4).** §26.2's last honest grass residual — the matched per-year
  structure gives F/C 1.87 in the 2018 European drought (F_diff's grass over-produces) — is diagnosed with
  three cheap matched-structure SLURM probes (diagnosis only; **no `src/`/`test/` change**, `[deps]` still
  EMPTY):
  - **It is NOT a structure/leaf artifact** (`corr(F/C, fed_leaf) = −0.12`) and **NOT the fresh-soil annual
    reset** — carrying F_diff's own multi-year soil column across 2009→2019 gives byte-identical 2018 numbers
    (F/C 1.87, growing-season `wscal` 0.939). It IS a water-supply effect: the drought barely reaches
    F_diff's grass water state (2018 `wscal` 0.939 vs 0.976 normal) while its per-leaf grass NPP stays high
    (F/leaf 2.591 vs the C's 1.386, which the drought DOES suppress).
  - **Root cause (code-verified, both sides; an adversarial C-source cross-check overturned a
    plausible-but-wrong first reading).** `daily_step_canopy` runs ONE stand-level water balance: `wr` from a
    single shared `soil.rootdist` (`fdiff.jl:1467-1473`), each grass's `supply_i = emax·wr·phi` the UNCAPPED
    potential (`:1528`), and the reported `wscal = min(1, Σsupply·fpc/Σdemand·fpc)` (`:1587`) one FPC-weighted
    (tree-dominated) scalar that saturates near 1. It barely moves in 2018 because of demand-saturation
    (Σsupply routinely > Σdemand) + top-layer over-recharge (`_infiltrate` refills to field capacity each rain,
    `:812-832`, no competitive depletion). The C (`water_stressed.c`, per-PFT at `daily_natural.c:181`) shares
    the same soil column but keeps a per-PFT `wscal` (`:130-140`) AND a sequential competitive per-layer
    availability cap (`aet_cor`, `:153-177,264-275`): the dominant trees deplete the shared layers first, so
    the grass's realized supply collapses in drought — the suppression F_diff never sees. **CORRECTION:** the
    C's grass is NOT shallow-rooted (`new_grass.c:40` = full depth, `beta_root=0.8` identical to trees,
    `pft.js:494/1110`) and `gp_stand` is FAITHFUL to the C — so the gap is the per-PFT `wscal` + competitive
    supply depletion, NOT rooting depth and NOT the conductance. The rooting counterfactual (shallowing the
    stand rooting → 2018 `wscal` drop ~6×, F/C 1.87 → 1.13) is a LEVER localizing the effect to the `wr`/supply
    channel, not a match to the C.
  - **Classification.** Same FAMILY as §20/§22 (F_diff aggregates the C's per-PFT state into stand quantities)
    but on the water-SUPPLY axis: per-PFT `wscal` + sequential competitive per-layer depletion — NOT the shared
    `gp_stand` conductance (faithful here), NOT a GPP-response, parameter, or soil-memory gap. Modest,
    extreme-year effect (aggregate grass fidelity ~0.95–1.10). Fix direction: a per-PFT realized-supply water
    balance porting `water_stressed.c`'s per-PFT `wscal` + `aet_cor` competitive cap — a coupled structural
    item, deferred. Reproduction: `scripts/grass_drought_{amplitude,soilmemory,rooting}_probe.jl`.
- **The validated-faithful grass config is now the coupled-rollout DEFAULT (Phase-3 scale-up step 11
  follow-up #6; docs §26.3).** §26.2 settled that F_diff's grass FLUX is faithful to the C, but the two
  mechanisms that make it so — the §26 photosynthesis demand-gate and the §22 grass establishment — were
  still OPT-IN, so the DEFAULT multi-year coupled rollout `rollout_canopy_years` kept the deep-shade grass
  overshoot and (with the gate on) would have extincted dim-patch grass. This flips the default.
  - **`rollout_canopy_years` now defaults `grass_demand_gate=true` + `grass_estab=grass_estabparams(T)`.** A
    helper `_with_grass_gate(p, on)` reconstructs `p.water` with the gate on at the C's sharp step
    `βgpd_gate=1e8` (the value `scripts/grass_daily_curve_fdiff.jl` validated in §26.2; the rollout is the
    non-differentiable diagnostic path, so the steep sigmoid costs no gradient). Pass
    `grass_demand_gate=false` / `grass_estab=nothing` for the pre-§26.3 references.
  - **Grass-only ⇒ nothing validated regresses.** A tree-only rollout is **byte-identical** (gate is gated on
    `ind.is_grass`; establishment is a no-op with no grass — verified `leaf_c`/`height` equal to the last
    bit). The Enzyme/decadal path `rollout_canopy_years_gpp` reads `p.water` directly (gate off) and is
    **unchanged** — trainer byte-identical + gradient-stable, §21 decadal GPP unaffected.
  - **Validated self-driven over the real decade** (`scripts/grass_default_flip_probe.jl`, SLURM: committed
    Hainich 25 mixed patches, 2008 structure self-driven 2009–2019). The two payoffs: the GATE lowers total
    grass carbon 111.0 → 86.6 gC/m² (removes the deep-shade overshoot); ESTABLISHMENT restores the grass the
    gate alone would extinct (survivors **14/25 → 25/25**). Each mechanism alone is worse (gate-alone
    extincts; no-gate overshoots); together they give the gate-corrected level with no extinction, all
    physical over 11 years.
  - **Honest scope:** validates the FLIP's mechanism payoffs + that the default is the §26.2-validated FLUX
    config — NOT that the self-driven grass STRUCTURE matches the C per-patch (the §24 compressed-grass item
    is separate). The `FDiffFastCore` v1 adapter still grows grass as a tree (documented follow-up).
  - Reworked two `grass_structure_tests.jl` testitems (pre-§26.3 references made explicit) + a new "the
    default is now the faithful grass config" gate. Runtime `[deps]` still EMPTY.
- **Grass-equilibrium CO-CALIBRATION — the §25 hard-floor lever REFUTED; the faithful mechanism is the C's
  photosynthesis DEMAND-GATE; the gate EXPOSES the true residual (a grass-NPP LEVEL undershoot); establishment
  stabilizes the self-driven equilibrium (Phase-3 scale-up step 11 follow-up #3; docs §26).** §25 named a
  co-calibrated next step of three interacting faithful mechanisms — (i) the grass-gated hard GPP floor
  `max(0,agd)`, (ii) the grass GSI light-limiter season (`:linear` vs `:exp` forest-floor light), (iii) grass
  establishment. A co-calibration probe (`scripts/grass_cocalibration_probe.jl`: matched-structure per-patch
  spectrum + gate-sharpness sweep + the self-driven 11-yr equilibrium; SLURM) pins them:
  - **REFUTED — the §25 hard-floor lever (i).** Applied grass-gated it drives the deep-shade patches (3/4/18,
    C grass NPP 0.01–0.09) to **−98 / −14 / −30 gC/m²/yr** and extincts **18/25** patches in the self-driven
    rollout. Root cause: flooring the DEMAND `gpd→0` collapses `fac = gpd/1.6·co2`, so the fixed-graph λ-solve
    returns a degenerate low λ that suppresses `agd` while `rd` (from the precomputed `vm`) stays normal ⇒
    `agd − rd ≪ 0`. A hard GPP floor is the WRONG mechanism. (§25's Finding-4 "0.37×" tested a GPP-ONLY floor
    with a soft demand; the scaffolding's `βflux_grass` floored BOTH, exposing the sharper NEGATIVE pathology.)
  - **The C's actual mechanism is a photosynthesis DEMAND-GATE + phen-scaled maintenance:** `water_stressed.c:196`
    `if(gpd>1e-5 && isphoto)` computes `agd`/`rd`, else `agd=0` (photosynthesis skipped); `npp_grass.c`
    `mresp = root·nind·respcoeff·k·nc·gtemp_soil·pft->phen`. F_diff ALREADY matches `mresp·phen`
    (`autotrophic_respiration`; grass `c_sapwood=0`); the only missing piece is the gate.
  - **Committed FIX — a grass photosynthesis DEMAND-GATE** (`WaterParams.grass_demand_gate`, opt-in): a smooth
    `stable_sigmoid(βgpd_gate·(gpd−1e-5))` on the pre-floor demand multiplies grass GPP AND `rd`, zeroing both
    as demand→0 while the λ-solve keeps the bounded soft-`βflux` `fac` (no degeneracy). Eliminates the negative
    pathology — deep-shade grass NPP positive-and-suppressed, the "C<1 ⇒ F<1" shade count **0/4 → 4/4**, no
    negatives (with `:linear`). Grass-gated ⇒ trees byte-identical; opt-in (default off ⇒ byte-identical).
    Replaces the refuted `βflux_grass` knob.
  - **The gate EXPOSES the true residual:** with the faithful gate the matched-structure grass NPP is aggregate
    **0.83× the C** (median 0.48×; bright patches 12–44 % low); the §25 "1.13×" was **inflated by the soft
    `softplus(agd, βflux=50)` floor producing grass GPP on the sub-threshold (`gpd≤1e-5`) days the C GATES OFF**
    — right number, wrong mechanism. The real residual is a grass-NPP LEVEL gap on the *above-threshold* days
    (cross-patch corr unchanged ~0.973 — the ranking is right, only the level is low).
  - **Establishment (`establishment_grass.c`) is NECESSARY for the self-driven equilibrium:** without it the
    gated/shaded grass extincts 17–18/25 patches; with it **0 extinct**. Committed as an opt-in `grass_estab`
    kwarg on `rollout_canopy_years` (`GrassEstabParams`/`grass_estabparams`/`_treepools_fpc`), grass-only.
  - **`:exp` forest-floor light NOT adopted:** with the gate it drives deep-shade grass NPP negative again
    (leaf-on-but-demand-gated days pay phen-scaled root maintenance with no photosynthesis); `:linear` retained.
    The `:exp` mode (`grass_lf_mode`/`phen_params_by_pft` kwargs) is kept inert + characterized.
  - All committed knobs opt-in / grass-gated ⇒ every validated tree path is byte-identical (full suite **26200 pass / 4 broken** (26183 baseline + the §26 gate)). New gate "Grass demand-gate + establishment — §26 faithful
    deep-shade balance; trees byte-identical" (`grass_structure_tests.jl`). Reproduction
    `scripts/grass_cocalibration_probe.jl` (self-checking, SLURM). Runtime `[deps]` stays EMPTY. **Next:** close
    the grass-NPP LEVEL gap on the above-threshold days (grass shares the beech photo params); then flip the
    gate + establishment to the coupled-rollout DEFAULT once validated against a MULTI-YEAR C grass reference.
  - **Follow-up (`scripts/grass_npp_level_probe.jl`): the level gap is NOT the grass temp/albedo params.** The
    ACTIVE grass id 8 has `temp_photos {10,30}` (raises cool-temp NPP: agg 0.833 → 0.901) and `albedo_leaf 0.23`
    (lowers GPP: → 0.757) — **together ≈ 0.82**, the two nearly cancel and the ~18 % undershoot PERSISTS
    (corr ~0.975). So the residual is a deeper grass GPP-vs-light gap (Vcmax / co-limitation / λ), worst at
    intermediate shade — needs the C's daily GRASS GPP for a matched-leaf/light decomposition. The faithful
    grass `temp_photos {10,30}` + `albedo_leaf 0.23` remain a fidelity improvement for a canonical grass builder.
  - **Follow-up #2 (session 23; docs §26.1): the proposed "C re-run" is really a C RECOMPILE, and the residual
    is param-faithful + season-shaped — NOT the forest-floor light or the GSI cold-start.** No physics change;
    diagnosis + roadmap correction + two committed self-checking SLURM reproductions
    (`scripts/grass_npp_light_response_probe.jl` 1540816, `scripts/grass_gsi_warmstart_probe.jl` 1540819).
    (1) **LPJmL-FIT has NO per-PFT/per-individual DAILY GPP output** (`par/outputvars.js`: only annual `PFT_NPP`
    /`ind` + cell-total `d_gpp`/`d_npp`), so "extract per-PFT daily GPP" is impossible and a config-only re-run
    cannot make it — it needs a C-SOURCE change + RECOMPILE (a new class of work). (2) Source audit: the grass
    photosynthesis KERNEL is byte-faithful (co-limitation the exact quadratic `photosynthesis.c:150`), `apar` is
    validated (§20), and grass id 8 respiration params (`respcoeff 1.2`, `cn_ratio.root CTON_ROOT`,
    `ratio.root 1.16`) are LITERALLY beech's — so the ~18 % gap is not a parameter. (3) The undershoot is
    **gate-independent, above-threshold, and tracks the grass ACTIVE-DAY fraction**, growing with shade
    (brightest-half agg F/C 0.861; F/C 0.86 at ff 0.50 → 0.57 at ff 0.29; active-day frac 0.66 → 0.30) — a
    season-shape residual, not GPP-per-active-leaf. (4) The faithful `:exp` forest-floor light is **REFUTED** as
    the fix (brightest-half F/C 0.861 → 0.755, 7 deep-shade negatives — refutes §26's deferred `:exp` lever).
    (5) The grass GSI **cold-start is REFUTED** (5-yr continuous warm-up: year 1 == year 5 to every digit).
    **Recommendation: DEFER to the learned canopy Vcmax/λ correction (§16/§18, proven on trees) rather than
    recompile;** if a hard-coded fix is later wanted, validate a grass-phenology-season fit against a multi-year
    grass NPP reference sliced from the on-disk production `ind` output (no C re-run).
  - **Follow-up #3 (session 24; docs §26.2): BUILT the C's daily grass GPP/NPP output — and it shows F_diff's
    grass is FAITHFUL; the §26/§26.1 "level gap" was a REFERENCE-BASIS ARTIFACT.** Added two scalar daily
    outputs to the LPJmL-FIT C source (`D_GRASS_GPP`/`D_GRASS_NPP`, `include/conf.h` ids 419/420, `NOUT`→421;
    cell-mean per-day accumulation in `src/lpj/daily_natural.c` beside the `GPP`/`NPP` writes; explicit flush in
    `src/lpj/fwriteoutput.c`; registered in `par/outputvars.js`) and rebuilt the FIT binary (18 insertions/1
    deletion — `patches/lpjmlfit_daily_grass_gpp.patch`; a local shim `patches/json_object_iterator.h.shim`
    works around this cluster's truncated `json-c/0.13.1` headers). Verified the new daily output integrates to
    the stock annual `pft_npp` band-8 grass value (50 ≈ 51). **Comparing F_diff's cell-mean daily grass NPP
    (matched 2008 structure, faithful params, demand-gate ON) to the C's OWN daily grass NPP over 2009–2019:
    aggregate ΣF/ΣC = 0.95, mean per-year F/C = 0.98 (range 0.72–1.19, NO systematic bias), season length
    faithful (actR 1.02), amplitude faithful (ampR 0.96), daily r ≈ 0.86.** So F_diff's grass GPP/NPP is
    faithful; the §26/§26.1 "0.82×" came from measuring F_diff (run on 2009 forcing) against the C's 2008
    `ind`-output NPP — a year/basis mismatch (the C's grass NPP swings 28–51 gC/m²/yr year-to-year). No F_diff
    physics change; the already-committed demand-gate + faithful grass params are what make it faithful.
    Committed: the C-source patch + shim (`patches/`), the CI-friendly reference
    `test/testitems/references/hainich_grass_daily_2009_2019.csv`, and scripts `run_fdiff_grass_gpp_cell.sh` /
    `extract_fdiff_grass_daily.py` / `grass_daily_curve_fdiff.jl` / `compare_grass_daily_c_vs_fdiff.py`. The
    grass-NPP thread (§20→§26.2) is CLOSED: the grass is faithful. Runtime `[deps]` stays EMPTY.
    - **Per-year matched-structure check (honest refinement; `scripts/extract_grass_structure_decadal.py` +
      `grass_daily_curve_fdiff.jl` `GRASS_STRUCT_CSV`).** Feeding F_diff each year's OWN C structure (2009–2019,
      the tightest matched-structure+forcing test) gives aggregate ΣF/ΣC = **1.10** (mean 1.12, range 0.77–1.87),
      season faithful (actR≈1.0) with a mild AMPLITUDE overshoot in warm/dry years (2018 European drought F/C
      1.87). So the two matched-forcing tests BRACKET unity (0.95 with 2008 structure, 1.10 per-year) —
      robustly confirming no systematic ~0.82× undershoot, but the honest claim is grass faithful to ~±10–15%
      aggregate with a warm/dry-year amplitude residual (a grass drought-response effect, partly confounded by
      per-year structure reconstruction), not a clean 1.0.
- **Independent adversarial verification of the §24 → §25 grass re-diagnosis chain + §24 superseded-banner /
  factual fixes (Phase-3 scale-up step 11 follow-up #2 verification; docs §24 banner + §25 "Independently
  verified").** A 4-lens refutation workflow (each lens tried to REFUTE a load-bearing claim) + an all-25-patch
  fapar check confirmed §25 and correctly superseded §24's forward-looking lever: (1) `light()`/`light_grass()`
  are dead code in `individual:true` (`annual_natural.c:117`); (2) `reduce_grass` is fpc-only and its
  `fpc_total > 1` cap fires at **0/25** Hainich patches (max FPC 0.955); (3) grass `temp_photos` 10/30 raises
  cool-temp NPP (params can't fix it); (4) the ~2.9 gC/m²/yr floor is the `softplus(agd, βflux=50)` artifact;
  (5) **F_diff's grass fapar reproduces the C's `fpar_leafon` to 6 s.f. at every patch (ratio 1.0)** — the light
  absorption is byte-faithful, so §25's "the gap is phenology, not light" holds. The §25 fix (4.26 → 1.13×) was
  **independently reproduced** (`scripts/grass_phen_probe.jl`, SLURM: beech 4.26/0.93 → per-PFT 1.13/0.973). §24
  now carries a superseded banner (its diagnostic Findings 1–3 HOLD; Finding 4's carbon-balance lever + next step
  are refuted by §25) and two factual fixes (patch-0 FPC 0.47+0.09=0.56; grass `alphaa` 0.5 vs beech 0.55 was
  omitted). New reproduction `scripts/grass_fapar_faithfulness_check.jl` (self-checking `@assert`, SLURM). Also
  refreshed the stale `MEMORY.md` header (§25 had not updated it). Runtime `[deps]` stays EMPTY.
- **Grass-overshoot RE-DIAGNOSIS #3 + FIX — the §24 "carbon balance" is per-PFT grass PHENOLOGY (dominant),
  wired into the coupled rollout; conductance / cover / carbon-balance / respiration / params all RULED OUT
  (Phase-3 scale-up step 11 follow-up #2; docs §25).** §24 (session 19) set the next step as "a light-limited
  grass carbon balance." Five committed SLURM decomposition probes on the Hainich 2008 reference pin that
  lever — it is **two faithful mechanisms F_diff was missing, dominated by per-PFT PHENOLOGY, not any
  carbon-balance/conductance/respiration parameter**, and they interact (must be co-calibrated).
  - **Committed fix** — `rollout_canopy_years` now drives each individual's leaf phenology with its OWN PFT's
    GSI (a `pft_ids` kwarg, default grass→8 / tree→3), so a shaded understory grass runs its light limiter on
    the tree-attenuated forest-floor light and is leaf-on far less than the canopy trees (`phenology_gsi.c:30-35`;
    the FIT `new_phenology:true`). `per_pft_phenology` existed since §19 but was only in `rollout_daily_canopy`,
    not the multi-year coupled rollout. **Effect:** the matched-structure grass NPP overshoot (grass held at the
    C's 2008 leaf, trees fixed, matched fpar) drops **4.26× → 1.13×** the C with cross-patch corr **0.929 →
    0.973**. **Tree path BYTE-IDENTICAL:** the beech GSI `pft_phenparams(3) === tebs_phenparams`, so the id-3
    trees are unchanged — full suite **26174 pass / 0 fail / 4 broken** (unchanged). New gate: the
    "coupled rollout uses PER-PFT grass phenology" testitem in `grass_structure_tests.jl`.
  - **Finding — the softplus GPP floor is the DEEP-SHADE lever, necessary but NOT sufficient.** `softplus(agd,
    βflux=50)` injects `log(2)/50 ≈ 0.0139` gC/m²/day even at ~zero light (≈2.9 gC/m²/yr) — the §24
    light-insensitive floor. A hard `max(0,agd)` (the C's `water_stressed.c:259`) collapses it and extinguishes
    the deepest-shade patches, but leaves the moderate-patch overshoot (that is the phenology). Must be
    grass-gated (a stand-wide `βflux` change perturbs the validated TREE NPP 1.5 %).
  - **Finding — demand/gmin/conductance/respiration/params are faithful/inert.** The `gc·fpc − gmin·fpar`
    demand (`fdiff.jl:1518`) is byte-faithful to `water_stressed.c:194`; grass `gmin` is inert under shade; at
    matched leaf+light the grass GPP-per-absorbed-light is IDENTICAL to the validated trees' (`3.025e-6` gC/J,
    `λ=0.85`) and grass respiration matches the C (`npp_grass.c`; CUE ≈ the trees'). **Rules out §21 (per-PFT
    conductance), §22 (cover competition), §24 (carbon-balance/params).**
  - **Corrected next step (co-calibrated, NOT committed):** the grass-gated hard GPP floor `max(0,agd)` +
    the grass GSI light-limiter season (`light_base`/`grass_lf`) to the C's grass leaf-on days (the hard floor
    alone over-suppresses — matched-structure 0.37× undershoot) + grass **establishment/re-seeding**
    (S-demography) for the self-driven dim-patch grass where NPP < turnover. Reproductions
    `scripts/grass_lightconductance_decomp.jl`, `scripts/grass_carbonbalance_probe.jl`,
    `scripts/grass_phen_probe.jl` (self-checking `@assert`s, SLURM). Runtime `[deps]` stays EMPTY.

### Fixed
- **CI `test (lts)` green again — the failure was an Enzyme 0.13.189 REGRESSION, not the test tree
  (Phase-3 scale-up step 11 CI follow-up; docs §23).** Pinned `Enzyme = "0.13.0 - 0.13.188"` in both the
  root and `test/Project.toml` `[compat]`. **Root cause (conclusively bisected from the CI logs):** the
  green run `a6d6975` resolved **Enzyme v0.13.188** and the Enzyme-reverse canopy testitems
  (`nn_canopy_training_tests.jl:22` and `:145`) PASSED; the very next push (`f65ca84`, ~5 h later) resolved
  **v0.13.189** and those same items began failing with `LLVM error: Canonicalization failed`. The test
  tree was **byte-identical** across the two commits (`git diff a6d6975 HEAD -- test/` is empty), and
  `test/Manifest.toml` is git-ignored so CI re-resolves fresh each run and auto-upgraded 188 → 189. 0.13.189
  is the latest published Enzyme, so the fix is to cap at the last-good 0.13.188 until a fixed Enzyme ships.
  Only `test (lts)` is a REQUIRED check; `test (1)` (Julia 1.11, where the `VERSION < v"1.11"` guards skip
  the Enzyme canopy items) stayed green; `test (macOS, lts)` (non-required) failed for the same Enzyme
  reason and is fixed by the same pin; `test (pre)` is `continue-on-error` (allowed to fail) and fails for
  an unrelated Julia-prerelease `ScopedValue` API break (`setindex!(::ScopedValue, ::Bool)`), untouched here.
  - **Corrects the session-17 diagnosis.** Step 11 (below) attributed the failure to adding the heavy grass
    re-diagnosis `@testitem`s "poisoning" the parallel ReTestItems worker pool, and reverted the test tree to
    `a6d6975` as the fix. That is **refuted**: the revert (`6514fd7`) left CI still red with the identical
    `LLVM error` — because the cause is the moving Enzyme dependency, not the test set. (Keeping the grass
    reproduction as a SLURM script rather than a `@testitem` remains reasonable to keep a heavy compile out of
    CI, but it was never the fix for this failure.)

### Added
- **Grass-overshoot RE-DIAGNOSIS #2 — the §22 cover-competition next step targets an INACTIVE code path;
  the real gap is a light-limited grass carbon balance (Phase-3 scale-up step 11 follow-up; docs §24).**
  §22 (session 17) corrected the roadmap to porting the LPJmL grass cover competition
  (`light.c`→`light_grass.c`→`fpc_grass.c`, "kills excess grass leaf/root to litter"). Re-examined against the
  actually-active FIT code path + a per-patch SLURM reproduction on the committed Hainich 2008/2010 reference;
  no physics change (corrected diagnosis + two committed reproductions + roadmap correction).
  - **Finding 1** — the FIT config runs `"individual":true` (`lpjmlfit.js:34`), and `annual_natural.c:117`
    gates `light()` behind `if(!config->individual)` — so `light()`/`light_grass()` are **never called**. The
    individual-mode cover reduction is `establishmentpft_ind.c:168-176` → `reduce_grass()`, which is **only**
    `pft->fpc /= factor` (`reduce_grass.c`; no carbon killed) and is gated on **total** cover `fpc_total > 1`
    — inactive in the typical Hainich patch (tree+grass FPC < 1). Porting `light_grass.c` carbon-killing would
    add a mechanism the C does not run in this config — the *same class of error* §22 caught in §21.
  - **Finding 2** — the C's grass leaf is a smooth monotone function of forest-floor light (0.011 → 215 gC/m²
    across the 25 patches) satisfying the steady-state balance NPP ≈ 1.8·leaf at *every* patch — bounded by the
    light-limited carbon balance alone, no hard cap.
  - **Finding 3** — F_diff's grass genuinely OVERSHOOTS even with trees held at the C's own structure (Exp A,
    identical forest-floor light): grass leaf median **92.5 (50–194)** vs the C's **6.5 (0.01–215)**, median
    ratio **×13.9**, deep-shade patches ×100–6900, cross-patch corr **0.57** (compressed, not light-tracking).
    Real + structural — not a tree-growth or §22-repro setup artifact.
  - **Finding 4** — the mechanism is an **under-light-limited grass NPP, ~2–3× the C at matched absorbed
    light** (the grass absorbed-PAR reproduces the C's `fpar_leafon` — §20's 5-s.f. match — so the light
    *absorption* is faithful; the gap is GPP/NPP per unit absorbed light). F_diff's grass makes ~2.9 gC/m²/yr
    NPP even at ~zero leaf/light, nearly the same in a shaded vs a bright patch — a light-insensitive NPP floor.
    Through the turnover balance this becomes the extinct-vs-thriving divergence. **Vindicates session 15's
    original "~3× grass NPP" as a per-patch, per-light fact** — §22's "faithful 0.83×" was a cell-total ratio
    dominated by the few high-leaf patches, masking the shaded-patch overshoot.
  - **Corrected next step** — a **light-limited grass carbon balance** (grass GPP/NPP → 0 under deep shade,
    scaling with the already-faithful absorbed light), pinned with a light- vs conductance-limitation
    decomposition (prime suspects: the `gc·fpc` conductance term uses the un-attenuated grass cover while the
    light term uses the tree-attenuated `fpar`, `water_stressed.c:194`/`fdiff.jl:1518`; and the single stand
    `gmin` vs the C's grass `gmin=0.8`). **Grass-specific** (the tree path — decadal GPP ×1.066, §21 — stays
    byte-identical) and AD-safe. **NOT** `light.c`/`light_grass.c` cover competition (inactive), **NOT** per-PFT
    conductance (§22), **NOT** grass photosynthesis params (grass `temp_photos` 10/30 would *raise* NPP at cool
    Hainich temps). Reproductions `scripts/grass_cover_mechanism_diagnosis.jl` + `scripts/grass_lightbalance_probe.jl`
    (self-checking `@assert`s). Runtime `[deps]` stays EMPTY.
- **Grass-overshoot RE-DIAGNOSIS — the §21 per-PFT-conductance next step is REFUTED; roadmap corrected
  (Phase-3 scale-up step 11; docs §22).** Session 16 (§21) attributed the §20 self-driven grass-NPP
  overshoot (~3×) to the shared stand-mean conductance `gp_stand` "over-supplying the understory grass" and
  set **per-PFT/per-individual canopy conductance** as the next step. Re-diagnosed from the LPJmL-FIT C
  source + a faithful instrumented reproduction on the committed Hainich 2010 cell (adversarially verified —
  four independent lenses, all confirming); no physics change (diagnosis + roadmap correction).
  - **Finding 1** — the C's returned GPP uses `gp_stand` for every natural PFT incl. grass (`water_stressed.c`
    line 194 ← `gc` ← `gp_stand`); the per-PFT `gp_pft`/`gc_pft` feed ONLY the `PFT_GCGP` diagnostic
    (`daily_natural.c:187`). So a per-PFT GPP conductance is **less** faithful, not more.
  - **Finding 2** — F_diff's grass GPP **already uses `gp_stand`** (measured `gc_grass ≈ 0.75·gp_stand`; the
    moist Hainich soil, growing-season `wscal ≈ 0.99`, keeps it only mildly water-limited), exactly as the C
    does; the grass's own `gp` is only ~0.14·`gp_stand`, so a per-PFT (own-`gp`) conductance would change the
    grass GPP **~43 %** — a large **de-calibration** away from the C-faithful value, not a fix.
  - **Finding 3** — at the C's OWN structure the per-year grass NPP is **faithful** (total **0.83×**, `fpar`
    matches). The "3×" is a **multi-year structural-feedback over-growth** (leaf → LAI → forest-floor `fpar`
    → NPP), unbounded because F_diff lacks the C's grass **cover/light competition** (`light.c` →
    `light_grass.c` kills excess grass leaf/root back to `1 − tree cover`).
  - **Corrected next step: grass cover/light competition** (`light.c` → `light_grass.c` → `fpc_grass.c`),
    optionally with the supply-side per-layer soil-water competition (`water_stressed.c:153-179`) — **NOT**
    per-PFT conductance (diagnostic-only in the C's GPP, and would degrade the validated tree GPP).
  - **Reproduction `scripts/grass_overshoot_diagnosis.jl`** (self-contained on the committed 2010/2008
    reference; run off the login node via SLURM) reproduces + asserts all three: per-year NPP faithful (ratio
    ∈ [0.6, 1.3], measured 0.832); grass GPP uses the stand mean (`mean gc/gp_stand > 0.5`, measured 0.751;
    own `gp` 0.138·`gp_stand`) + a per-PFT conductance would change grass GPP `> 0.2` (measured 0.427);
    self-driven grass over-grows > 2× (leaf 6.4 → 160, ×25 over 11 yr). It is a **script, not a CI
    `@testitem`, by design** — adding the heavy per-cell conductance instrumentation to the parallel
    ReTestItems pool tripped a pre-existing Enzyme-0.13/Julia-1.10-`lts` `LLVM error: Canonicalization failed`
    in the unrelated Enzyme-reverse canopy testitems (a known Enzyme+worker fragility); the script keeps that
    compilation out of the test pool while staying committed + reproducible. Runtime `[deps]` stays EMPTY.
- **Decadal (11-year) fidelity validation of the coupled multi-year rollout (Phase-3 scale-up step 10;
  docs §21).** §18 validated the cell × multi-year objective over 3 years (2009–2011); this extends the
  committed real reference to a full DECADE (2009–2019) and answers the fidelity-horizon question — starting
  from the 2008 reconstructed 25-patch structure and self-driving 11 years (each patch grown by its own
  pipe-model allocation, kernel-isolation C-FAPAR phenology), does the coupled rollout stay faithful to the
  C's OWN per-year annual GPP?
  - **`scripts/extract_fdiff_decadal.py`** — slices `hainich_decadal_forcing.csv` + `hainich_decadal_targets.csv`
    (2009–2019 daily forcing + per-year daily C GPP/FAPAR) from the full-period single-cell daily CSV already
    on disk (no C re-run), reusing the committed 2008 start structure.
  - **★ Result: the coupled rollout stays faithful over the decade** — mean cell-mean annual-GPP ratio
    **1.066** (the inherited ~+7 % GPP-phenology level, §13/§19), each year bounded 1.01–1.11 (a mild
    mid-decade drift that recovers, **no runaway**), and **interannual correlation r = 0.86** with the C's
    year-to-year variability (tracks the real forcing, not a flat mean).
  - **Gate `decadal_validation_tests.jl`** (self-contained): the 25-patch rollout runs 11 years and stays
    physical (finite/positive/bounded per-year GPP); mean ratio ≤ 1.12; each year 0.9–1.2; per-year
    correlation with the C > 0.7. Runtime `[deps]` stays EMPTY.
  - **Two investigation findings recorded** (roadmap, no code change): the §20 self-driven **grass-NPP
    overshoot is structural** — carbon-only run, grass fPAR matches the C, light-limited, root C:N/respcoeff
    equal the beech values; the residual is the **shared stand-mean conductance** (`gp_stand` over-supplies
    the understory grass), needing per-PFT conductance, not a parameter fix. **[SUPERSEDED by §22 /
    scale-up step 11:** this `gp_stand` attribution is **refuted** — the C's GPP itself uses `gp_stand`, and
    F_diff's grass GPP already matches it (`gc_grass ≈ 0.75·gp_stand`, so a per-PFT conductance would
    *de-calibrate* it ~43 %); the per-year grass NPP is faithful (0.83×) and the overshoot is a multi-year
    cover-competition gap; per-PFT conductance is NOT the fix.**]** The **Enzyme-on-Julia-≥1.11 guard-lift is blocked upstream**
    — the latest Enzyme 0.13.187 still raises `EnzymeInternalError` on the mutating canopy reverse pass on
    Julia 1.11.7.
- **Prognostic GRASS structure — the `allocation_grass.c` port (Phase-3 scale-up step 9; docs §20).** The
  multi-year rollout previously grew only trees; grasses were held fixed and — because the `ind`-output
  reconstruction gives grass rows `leaf_c = crownarea = nind = 0` (grass is a per-**area** cohort) — were
  structurally dropped from the multi-year path. Grass leaf/root carbon are now PROGNOSTIC via a faithful
  differentiable port of the LPJmL-FIT NATURAL-veg annual grass sequence `turnover_grass.c` →
  `allocation_grass.c` (`annual_grass.c:29-30`) — essential for running F_diff on grasslands.
  - **`grow_grass_individual(alloc, tree, bm_inc_ind, wscal_mean)`** — closed-form carbon math: leaf turns
    over daily + root monthly (annual pool `→ pool·(1 − rate)`); reproduction reserve removed before
    allocation; natural-veg full-reallocation partitions `bm_net` at `lmtorm = lmro_ratio·(lmro_offset +
    (1 − lmro_offset)·min(1, wscal))` with the no-reallocation caps + negative-leaf branch.
  - **`grass_allocparams()`** — temperate C3 grass (id 8) verbatim from the active `par/pft_lpjmlfit.js`
    (`lmro_ratio 0.8`, `lmro_offset 0.5`, leaf turnover rate `1.0`, root `0.5`, `reprod_cost 0.1`).
  - **`grass_treepools(agb, vegc, sla)`** — per-area reconstruction (leaf = `agb`, root = `vegc − agb`,
    `crownarea = nind = 1`); with this convention the existing `fpar`/`fpc` recompute reproduces the C
    (recomputed grass `fpar = 0.03042` vs the C's `0.0304233`). Wired into `rollout_canopy_years`/
    `rollout_canopy_years_gpp` via a `galloc` kwarg; the grass branch fires only for `is_grass` individuals,
    so all committed TREE baselines + the Enzyme trainer are **byte-identical**.
  - **Allocation faithfulness (the deliverable):** golden-vs-`allocation_grass.c` across every branch
    **< 1e-5**; carbon conservation **4.4e-16**; fed the C's grass NPP the allocation equilibrates to the
    C's grass leaf:root **0.791 vs 0.799** (the `bm_inc_ext` crutch, as the tree allocation was validated
    before its self-NPP was calibrated in §13).
  - **Honest finding:** F_diff's SELF-computed grass NPP is ~3× the C's (grass shares the beech
    photosynthesis/respiration params), so a self-driven grass overshoots — the grass-NPP calibration is the
    documented next step (parallel to the tree NPP calibration, §13).
  - **Gate `grass_structure_tests.jl`** (5 testitems): param fidelity + reconstruction; golden + conservation
    + bounds; equilibrium-fed-C-NPP → C structure; ForwardDiff (scalar + through the coupled multi-year
    grass-inclusive rollout) vs FD; Enzyme reverse through the grass-inclusive multi-year path (guarded
    `VERSION < 1.11`). Runtime `[deps]` stays EMPTY.
- **Per-PFT GSI leaf phenology (Phase-3 scale-up step 8; docs §19).** Generalizes the self-computed leaf
  phenology (§11) from ONE beech GSI applied patch-wide to PER-PFT: the LPJmL-FIT config runs
  `phenology_gsi` for every natural PFT (`lpjmlfit.js` `"new_phenology":true` + `"individual":true`; the
  "evergreen"-named PFTs run the full four-limiter GSI, not static `phen≡1`), so each individual now gets
  its own PFT's leaf-display curve.
  - **`pft_phenparams(id, T)`** — the twelve GSI parameters (`tmin/tmax/light`·slope·base·tau + `wscal`)
    for each 0-based natural PFT id 0–9, verbatim from the ACTIVE `par/pft_lpjmlfit.js`. `wscal_base =
    minwscal_median·100` (the C's individual-mode water inflection, `phenology_gsi.c:64-66`, NOT the inert
    par-file `wscal.base`). `tebs_phenparams()` == `pft_phenparams(3)`.
  - **`per_pft_phenology(pft_ids, forcings; …)`** — standalone per-PFT driver (one `PhenState` per distinct
    PFT → per-day × per-individual leaf display); grasses (id ≥ 7) drive the light limiter with forest-floor
    light `grass_light_frac·swdown`.
  - **Per-individual `phen` wiring** — `daily_step_canopy`/`patch_albedo` accept `phen` as a scalar OR a
    per-individual vector (compile-time-dispatched `_phen_at`; the scalar path is **byte-identical**, so
    every committed baseline + the Enzyme trainer are untouched). `rollout_daily_canopy` gains a `pft_ids`
    kwarg co-solving per-PFT phenology with the stand water feedback + a lag-1 grass forest-floor light
    attenuation. The Enzyme multi-year training path keeps its scalar C-FAPAR phen (unchanged).
  - **Result (25-patch Hainich 2010):** per-PFT phenology moves the standalone cell GPP annual ratio vs the
    C **1.134 → 1.097** (closer to the C) with daily r improving **0.988 → 0.993**, driven by the minority
    the beech-patch-wide phen got wrong (evergreens hold winter leaves; grass understory is light-shaded).
  - **Gate `per_pft_phenology_tests.jl`** (self-contained): param fidelity vs `par/pft_lpjmlfit.js` (all
    ids 0–9); distinct/bounded/physically-ordered trajectories; scalar-vs-vector byte-identity (Δ = 0);
    per-PFT self-driven rollout closes water and reduces to the beech default on an all-beech patch.
  Runtime `[deps]` stays EMPTY.
- **NN training on the CELL × MULTI-YEAR objective against a REAL multi-year reference (Phase-3 scale-up
  step 7b-cell-multiyear; ADR 0016).** Composes §16 (cell) with §17 (multi-year): the learned Vcmax/λ
  correction is trained so the **cell-mean PER-YEAR annual GPP** matches the C binary's own per-year annual
  GPP over the full 25-patch Hainich cell, with **every patch grown across years** through the pipe-model
  allocation. §17's two flagged next steps — the cell-multi-year objective and a real multi-year reference —
  both land here.
  - **Cell × multi-year loss + trainer** `fdiff_cell_multiyear_gpp_loss` / `train_fdiff_cell_multiyear_rollout!`
    (extension): the cell MSE over years `L = (1/NY)Σ_y (Ḡ_y − T_y)²`, `Ḡ_y = (1/P)Σ_p G_{p,y}`, factors
    exactly patch-by-patch (`∂L/∂ps = Σ_p ∂/∂ps Σ_y c_y·G_{p,y}`, `c_y = (2/(NY·P))(Ḡ_y − T_y)` detached), so
    every reverse pass is the proven single-patch multi-year `rollout_canopy_years_gpp` Enzyme path — **no
    monolithic multi-patch AD** — and the per-patch gradients are summed by reusing one accumulating
    `Duplicated` shadow. One Enzyme reverse per patch over the FULL multi-year rollout per epoch (no
    per-chunk TBPTT). Runtime `[deps]` still EMPTY.
  - **Real committed multi-year reference** (`scripts/extract_fdiff_cell_multiyear.py`, sliced from the
    already-on-disk C re-run — no C re-run needed): the 2008 start-year 25-patch structure
    (`hainich_individuals_2008.csv`), per-year 2009–2011 daily forcing (`hainich_multiyear_forcing.csv`), and
    those years' daily C GPP + FAPAR (`hainich_multiyear_targets.csv`).
  - **Verification / gate** — new self-contained cell × multi-year testitem in `nn_canopy_training_tests.jl`
    (3 ragged patches × NY = 2): identity per-year Δ = 0; the per-patch-decomposed cell-multi-year gradient
    vs FiniteDifferences to **max rel err 1.5e-10**; recovery loss down **98.8 %** in 25 epochs, trained cell
    GPP within **0.07 %** of a known `vm=1.15/λ=1.05` target. Enzyme parts guarded `VERSION < v"1.11"`.
    Driver `scripts/train_fdiff_cell_multiyear.jl`; report §18; ADR 0016 (addendum).
  - **Result (full 25-patch cell, real 2008→2011 reference, kernel-isolation C-FAPAR phenology)** — the
    learned correction closes the cell-mean annual-GPP LEVEL against the real C per-year annual GPP through
    the multi-year structure feedback: mean model/C ratio **1.034 → 0.998** (`:vm`) → **0.996** (`:vm,:λ`);
    per-year 1.026/1.014/1.063 → 0.992/0.981/1.022 (`:vm`). One shared correction fit across years trims the
    year-to-year spread (2011 the high-GPP outlier) rather than zeroing each year. Full suite
    **25,943 pass / 0 fail / 4 broken** on Julia 1.10.
- **`scripts/sbatch_train.sh`** — submit the F_diff NN-training drivers as durable SLURM batch jobs on a
  compute node (`standard`/`qos=short`, `--project=test`, Julia 1.10), so the heavy Enzyme-reverse training
  runs (the cell × multi-year fit is a one-time ~7-min compile + ~30-min run) are off the login node and
  survive a dropped interactive session.
- **NN training THROUGH the multi-year structure/allocation feedback (Phase-3 scale-up step 7b-multiyear;
  ADR 0016).** §16's documented frontier — training GPP to match the C *while the canopy structure grows
  between years via the allocation* — is now Enzyme-differentiable. Session 11's `EnzymeNoTypeError` was
  root-caused (NOT the guessed `BitVector`/`_solve_leaf_inc` temporary, both of which differentiate cleanly
  in isolation) to a **struct-in-memory** failure: a `Vector{TreePools}` field-scatter of `grow_individual`'s
  branchy output copies the struct's trailing `is_grass::Bool` + padding as `Anything` in an 80-byte memcpy.
  - **Struct-of-arrays fix.** `_patch_fpars` split into an Enzyme-typeable SoA core `_patch_fpars_soa`
    (plain `Vector{Float64}` field arrays) + a thin `Vector{TreePools}` unpacking wrapper — **byte-identical**
    (max|Δ| = 0.0), so no committed canopy baseline moves. New dependency-free `rollout_canopy_years_gpp`
    (exported): the multi-year coupled rollout in SoA form (same physics as `rollout_canopy_years`),
    returning per-year annual stand GPP; soil carried across years as fields, `phens` materialized to a
    concrete type — the two smaller `EnzymeNoTypeError` mechanisms documented in the report Enzyme note.
  - **Multi-year trainer** `fdiff_multiyear_gpp_loss` / `train_fdiff_multiyear_rollout!` (extension) — one
    Enzyme reverse gradient of the FULL multi-year loss per epoch (the annual structure feedback stays inside
    the differentiated unit). Runtime `[deps]` still EMPTY.
  - **Verification / gate** — Enzyme reverse through the full SoA structure → daily rollout → grow →
    next-year chain matches FiniteDifferences to ~1e-11 (scalar hook) / 8.2e-10 (network-param gradient);
    ForwardDiff through the physics to ~1e-13. New self-contained multi-year testitem in
    `nn_canopy_training_tests.jl`: identity (Δ = 0), Enzyme-vs-FD gradient, and recovery of a known
    `vm=1.15/λ=1.05` correction (loss 16.2 → 0.12, 99.3 %; trained GPP within 0.28 %). Enzyme parts guarded
    `VERSION < v"1.11"`. Driver `scripts/train_fdiff_multiyear.jl`; report §17; ADR 0016 (addendum).
- **NN training against the REAL C-binary daily GPP on the full 25-patch cell + the λ lever (Phase-3
  scale-up step 7b-cell; ADR 0016).** §15 recovered a *synthetic* correction on one patch; this trains the
  learned correction against the LPJmL-FIT C binary's own daily GPP on the full Hainich cell (25 patches /
  297 individuals) — the honest validation objective — and turns on the λ head.
  - **Cell (multi-patch) loss + trainer** `fdiff_cell_gpp_loss` / `train_fdiff_cell_rollout!` (extension):
    the C daily GPP is the cell-mean over patches, so one shared learned correction is trained so the
    cell-mean GPP matches the C. The cell-MSE gradient is computed by an **exact per-patch decomposition**
    (Gauss–Newton residual reweighting: `∂L/∂ps = Σ_p ∂/∂ps Σ_i c_i·g_{p,i}`, `c_i = (2/(D·P))(ḡ_i−t_i)`
    detached), so every reverse pass is the proven single-patch `daily_step_canopy` Enzyme path — **no
    monolithic multi-patch AD entry point** — and the per-patch gradients are summed by reusing one
    accumulating `Duplicated` shadow. Runtime `[deps]` still empty.
  - **Result (full 25-patch Hainich, kernel-isolation C-FAPAR phenology):** the learned Vcmax lever closes
    the GPP level from **1.093 → 1.023** (`:vm`) and **→ 1.010** (`:vm, :λ`) against the real C daily GPP,
    while the daily correlation **improves** (full-year 0.9978 → 0.9983, growing-season 0.9973 → 0.9990) —
    the opposite of the single-representative path (§14), where the light-limited residual made Vcmax the
    wrong lever and the fit degraded the shape. The canopy residual IS Vcmax-shaped. Driver
    `scripts/train_fdiff_canopy_cell.jl`; report `docs/phase3_fdiff_cbinary_validation.md` §16.
  - **Gate** `test/testitems/nn_canopy_training_tests.jl` (cell testitem, 3 ragged patches, self-contained):
    identity (Δ = 0, both vm+λ hooks); **cell gradient (Gauss–Newton decomposition) vs FiniteDifferences,
    max rel err 6.1e-10** on the full multi-patch cell MSE; recovery of a known vm=1.15/λ=1.05 correction
    (loss 0.330 → 0.011, trained cell GPP within 0.04 %). Enzyme parts guarded to `VERSION < v"1.11"` (§15).
  - **Multi-year objective through the structure/allocation feedback — the next frontier.** Enzyme reverse
    through `rollout_canopy_years` (`_patch_fpars` layered-light recompute + `grow_individual`'s allocation
    Newton) raises `EnzymeNoTypeError` on Julia 1.10 — an Enzyme type-analysis blocker on the composed
    structure path, not a differentiability problem (§12's ForwardDiff `d(structure)/d(bm_inc)` /
    `d(structure)/d(α_c3)` already match FD). Documented in §16 as the follow-up.
- **NN training on the coupled CANOPY path — Enzyme reverse through the array-mutating rollout (Phase-3
  scale-up step 7b-canopy; ADR 0016).** Applies the learned correction where the residual is
  Vcmax/phenology-shaped (the coupled canopy), and closes the AD-through-mutation follow-up flagged since
  step 2.
  - **Per-individual NN hooks in `FDiff.daily_step_canopy`** (threaded through `rollout_daily_canopy` +
    `rollout_canopy_years`): each individual's learned Vcmax/λ correction from its own feature vector
    `[temp, swdown, daylength, apar_i, wr, co2]`, applied consistently to pass-1 (gp_sum) and pass-2
    (GPP/λ) Vcmax. Identity fast path when off ⇒ **every committed canopy baseline byte-identical** (gate
    Δ = 0).
  - **Enzyme-reverse trainer** `train_fdiff_canopy_rollout!` + loss `fdiff_canopy_gpp_loss` (extension):
    `daily_step_canopy` mutates the per-layer soil arrays, which Zygote can't cross — so it trains with
    Enzyme reverse (`Duplicated` params + fresh `make_zero` shadow + `set_runtime_activity`, Lux's
    `AutoEnzyme` idiom). `Enzyme` becomes a 4th extension trigger (`FDiffTrainingExt` now needs
    `Lux`/`Zygote`/`Optimisers`/`Enzyme`); runtime `[deps]` still empty.
  - **Gate** `test/testitems/nn_canopy_training_tests.jl` (self-contained: 4 individuals, 5-layer soil,
    40-day forcing): identity (Δ = 0); **Enzyme gradient w.r.t. NN params vs FiniteDifferences, max rel
    err 1.2e-8** through the mutating canopy path; recovery of a known correction (loss 0.205 → 1.1e-3,
    trained GPP within 3 %, recovered Vcmax scale ≈ 1.18 vs the known 1.20 — the small low-bias is the
    understory `je`-limit). Report `docs/phase3_fdiff_cbinary_validation.md` §15.
  - **Julia-version caveat (CI-surfaced):** the Enzyme-reverse canopy path is verified on **Julia 1.10**
    (lts; `Project.toml` compat `julia = "1.10"`). On **Julia ≥ 1.11**, Enzyme 0.13 raises an internal LLVM
    compiler error through this complex mutating path (the single-bucket Enzyme gate compiles fine on 1.11).
    The per-individual `FDiffParams{T}` construction in `daily_step_canopy` was switched from the keyword to
    the equivalent **positional** constructor (Enzyme-transparent; behaviour-identical), and the
    Enzyme-dependent parts of the canopy gate are guarded to `VERSION < v"1.11"` (identity runs everywhere)
    so CI's forward-compat `test (1)` job stays green. Lifting the guard is an upstream-Enzyme follow-up.
- **Gradient-based online rollout training — NN λ/Vcmax hooks + finished TBPTT loop (Phase-3 scale-up
  step 7b; ADR 0016).** The milestone the differentiable-first core (ADR 0014) exists to enable.
  - **Dependency-free NN hooks in the physics** (`FDiff.FluxHooks`): optional LEARNED multiplicative
    corrections to the two photosynthesis levers a hybrid trains — Vcmax (`vm`) and the ci:ca ratio `λ` —
    threaded through `daily_step`/`rollout`/`annual_npp`. Default `nothing` = the identity fast path, so
    **every regression baseline is byte-identical when the hook is off**; the runtime stays
    dependency-free (the physics only ever *calls* the hook). `photosynthesis` gains a `vm_scale` kwarg
    (applied at Vcmax, propagating into potential conductance + leaf respiration); the λ hook re-clamps to
    the physical bracket. Feature vector `[temp, swdown, daylength, apar, w_soil, co2]`.
  - **Training as a PACKAGE EXTENSION** `ext/FDiffTrainingExt.jl` (weakdeps `Lux`/`Zygote`/`Optimisers`,
    activated by `using` them; runtime `[deps]` stays empty): a Lux MLP with a **zero-initialized final
    layer** (untrained ⇒ exactly the identity correction), `build_fdiff_nn` / `neural_vm_hook` /
    `neural_lambda_hook`, the scalar rollout GPP loss `fdiff_gpp_loss`, and the finished TBPTT
    online-rollout loop `train_fdiff_rollout!` — a working port of NeuralCrop.jl's broken
    `train_loop_rollout!` scaffold (Zygote reverse-mode + `Optimisers.update` + detached soil-water state
    carried across chunk boundaries).
  - **Gate** `test/testitems/nn_training_tests.jl`: (1) identity (hook-off == committed baseline;
    zero-init net == pure physics to 1e-10); (2) gradient correctness (Zygote gradient w.r.t. NN params
    vs FiniteDifferences, rtol 1e-4 — the AD-vs-FD discipline of the physics gradient gate); (3) recovery
    of a known correction (loss 0.67 → ~1e-3, trained GPP within 0.1 %, recovered Vcmax scale ≈ the known
    1.30 — an identifiability proof of the machinery).
  - **Physical finding:** fitting the learned Vcmax correction to the LPJmL-FIT C daily GPP on the
    single-representative path only PARTIALLY closes the level gap (annual ratio ≈ 0.64 → ≈ 0.79) — that
    gap is **light/structure-limited** (Haxeltine–Prentice co-limitation saturates at the light-limited
    rate `je`), so Vcmax is the wrong lever there; it is exactly why the multi-individual canopy step
    (§9) closed GPP by spreading light. The learned Vcmax/λ correction belongs on the **coupled canopy
    path** (Enzyme-reverse-through-mutation), the documented next step. Driver `scripts/train_fdiff_nn.jl`;
    report `docs/phase3_fdiff_cbinary_validation.md` §14; ADR 0016.
- Root `Project.toml` gains `[weakdeps]` + `[extensions]` (`FDiffTrainingExt`) and their `[compat]`; the
  runtime `[deps]` is still empty (dependency-free core, ADR 0014). `test/Project.toml` gains
  `Lux`/`Zygote`/`Optimisers`.

### Changed
- **Beech GSI phenology `tmin` corrected to the ACTIVE FIT parameter file (docs §19).** The beech (TeBS)
  cold-temperature limiter was `tmin_slope=2.0`, `tmin_base=8.0` — the **standard** `par/pft.js` values —
  but the FIT run uses **`par/pft_lpjmlfit.js`** (`tmin_slope=4.0`, `tmin_base=8.5`; the other beech GSI
  params already matched). Correcting them makes the self-computed phenology consistent with the C binary it
  validates against: the standalone 25-patch canopy GPP annual ratio tightens **1.17 → 1.13**, transp
  **1.08 → 1.05**, daily r ≈ 0.99 unchanged. Only `hainich_canopy_baseline_2010.txt` moved (`gpp`
  1286 → 1250, `transp` 258 → 251); the C-FAPAR-driven single-rep/multilayer baselines and
  `fdiff_annual_totals.txt` are unmoved.
- **Self-computed canopy NPP CALIBRATED — the `bm_inc` crutch removed (Phase-3 scale-up step 7a).** The
  step-6 over-respiration (standalone canopy NPP ≈ −25 vs the C's ≈ +507 gC/m²/yr) was decomposed against
  the C target (`Ra = R_leaf + R_maint + R_growth`) to two faithful-to-`npp_tree.c` fixes in
  `FDiff.autotrophic_respiration` — NOT a constants error:
  - **The growth-respiration `max(0,·)` floor was far too soft.** The C is a hard branch
    `npp = (assim<mresp) ? assim−mresp : (assim−mresp)·(1−r_growth)` (`npp_tree.c:52`, `assim = gpp−rd`),
    i.e. `R_growth = r_growth·max(0, gpp−rd−mresp)`, zero when carbon-negative; F_diff smoothed it with
    `softplus(·, β=1)`, whose `log(2)/β ≈ 0.69 gC` offset injected a phantom growth respiration into every
    carbon-negative individual/day (≈ +730 gC/m²/yr aggregated). Sharpened via a new `RespParams.βgrowth`
    (= 50, matching the other flux floors).
  - **Fine-root maintenance is now phen-gated** (`npp_tree.c:51` scales the root/`sapwood_bg` block by
    `pft->phen`, above-ground sapwood year-round): `R_maint = respcoeff·k·gtemp·(C_sap/CN_sap +
    phen·C_root/CN_root)`. The three call sites pass the day's `phen`.
  - **Result:** standalone canopy annual NPP **−25 → +663 gC/m²/yr** (C 507); winter leaf-off **−250 →
    −6.7** (C −13); daily NPP **r 0.987**; carbon-use efficiency **NPP/GPP 0.52 vs the C's 0.46**. In the
    kernel-isolation config (C FAPAR+PET, GPP≈C) the respiration **total Ra = 592.8 vs the C's 595.6 — a
    0.5 % match**, so the standalone NPP overshoot (×1.31) is inherited from the documented +17 %
    GPP-phenology level, not a respiration miscalibration.
  - **The `bm_inc` crutch is removed:** `rollout_canopy_years` defaults fully self-driven, and
    `FDiffFastCore` always self-accumulated its own NPP. The self-driven coupled loop grows structure
    smoothly (year-1 mean tree height 9.41 m vs the C's 9.344; 8-year H 9.41 → 10.28; no blow-up).
  - Adversarially re-verified against `npp_tree.c` / `water_stressed.c` / `daily_natural.c`. Two
    documented second-order residuals remain (both pre-existing v1, partially cancelling): omitted
    `sapwood_bg` below-ground maintenance (NPP high) and un-gated `rd` on rare water-stress-collapse days
    (NPP low). Report `docs/phase3_fdiff_cbinary_validation.md` §13.
- **Numerical-regression baseline** `test/testitems/references/fdiff_annual_totals.txt`: `npp`
  871.81 → 893.28 (the sharpened growth-resp floor removes the phantom respiration on the synthetic
  scenario too); `gpp`/`transp`/`evap`/`runoff`/`precip` are byte-identical (the fix is downstream of GPP
  and the water balance). The water/light canopy baselines are unchanged.
- **Gates:** new self-computed-NPP gate in `multi_individual_tests.jl` (positive NPP; ratio ≤ 1.6; CUE ∈
  [0.42, 0.56]; daily r > 0.95; bounded winter deficit); `dynamic_structure_tests.jl` and
  `coupling_tests.jl` now run the coupled loop fully self-driven. `scripts/validate_fdiff_canopy.jl`
  fixed (stale `nind` constructor) + extended to report NPP/CUE. Full suite **25,865 pass / 0 fail /
  4 broken**; ForwardDiff/Enzyme still match finite differences (the fixes add no new conditionals);
  Runic-clean.

### Added
- **Dynamic (prognostic) canopy structure + the S↔F coupling adapter (Phase-3 scale-up step 6).** The
  multi-individual canopy's per-individual carbon pools are now PROGNOSTIC: they accumulate the daily
  `bm_inc` (= Σ daily NPP, per-m² patch basis — the new `npp_ind` flux) and GROW at the annual boundary
  via a faithful DIFFERENTIABLE port of the LPJmL-FIT year-end sequence `turnover_tree.c` →
  `allocation_tree.c` → `allometry_tree.c`. New `FDiff` API: `AllocParams`, `TreePools`, `grow_individual`
  (reproduction reserve + sapwood→heartwood + summergreen leaf/root recycle + pipe-model allocation +
  allometry), `_alloc_residual`/`_solve_leaf_inc` (a fixed-graph damped-Newton allocation solve — the
  λ-solve AD pattern, not the C's bisection), `individual_from_pools`/`_patch_fpars` (getfpar
  layered-light recompute as heights grow), `rollout_canopy_years` (the multi-year coupled loop),
  `tebs_allocparams`. Verified line-by-line against the C source (9-agent extraction workflow +
  adversarial re-derivation).
  - **Decisive validation:** the pipe-model invariant `leaf ≈ k_latosa·sapwood/(wooddens·H·sla)` holds
    after allocation to **max rel. error 2.9e-16**; carbon conservation `Δ(pools) = bm_net − turnover` is
    exact; **ForwardDiff `d(height)/d(bm_inc)` & `d(sapwood)/d(bm_inc)` match finite differences**; a
    coupled multi-year rollout (2009 start + 2010 forcing + the C's `bm_inc`) gives **year-1 mean tree
    height 9.34 m = the C's actual 2010 value** (from 2009's 9.21) and an 8-year trajectory grows smoothly
    with no blow-up.
  - **`FDiffFastCore <: AbstractFastCore` — `AbstractFastCore.step!` no longer throws.** Daily
    `step!(fc, state::SharedState, bc::SToF, forcing::AtmForcing) -> FToE` maps the shared per-layer soil
    water ↔ the `SoilColumn`, self-computes daylength/GSI-phenology/dynamic-albedo `eeq`, runs one
    `daily_step_canopy`, **writes the soil water back into `SharedState.w` in place**, and returns the
    daily `FToE` (`LE = λ·ET`); the year-end `annual_step!(fc, state) -> FToS` grows the prognostic
    structure and returns the conserved increment for S — the flux-then-integrate S↔F handoff (DESIGN §8).
  - **A load-bearing per-m² maintenance-respiration fix:** `daily_step_canopy` had fed per-individual
    pools into the maintenance term against per-m² GPP/leaf-resp; added `nind` to `FDiff.Individual` and
    the `×nind` factor (`npp_tree.c:51`) so NPP is per-m² consistent (the committed water/light baselines
    are unchanged). **Known residual (RESOLVED in step 7a, above):** F_diff's self-computed canopy NPP
    over-respired (≈ −25 vs the C's ≈ +512 gC/m²/yr) — the real causes were the soft growth-resp floor +
    un-phen-gated root maintenance (the maintenance constants matched the C exactly); until then the
    coupled loop used a `bm_inc` crutch (the C's per-individual NPP — the same kernel-isolation methodology
    used for the FAPAR/PET crutches), and a carbon-deficit individual stagnates rather than blowing up the
    pipe-model height.
  - New gates `test/testitems/dynamic_structure_tests.jl` (allocation invariant, conservation, growth,
    AD; 30 tests) + `test/testitems/coupling_tests.jl` (the `FDiffFastCore` adapter + coupled loop; 15
    tests), self-contained on the committed 2010 reference. Data reconstruction
    `scripts/extract_fdiff_individuals_multiyear.py` (2008–2011 per-individual pools incl. heartwood) +
    committed `references/hainich_structure_growth.txt`; driver `scripts/validate_fdiff_structure.jl`.
    Report `docs/phase3_fdiff_cbinary_validation.md` §12. Full suite **25,856 pass / 0 fail / 4 broken**;
    JET/Aqua/gradient green; Runic-clean.
- **Differentiable multi-layer soil water for `F_diff` (Phase-3 scale-up step 2).** Replaced the single
  soil bucket with a 23-layer differentiable column (`FDiff.SoilColumn`, `FDiffStateML`,
  `daily_step_ml`/`rollout_daily_ml`, `hainich_soilcolumn`): fill-to-field-capacity infiltration
  cascade, Jackson-1996 β root distribution (D95 ≈ 115 cm → ~93 % of roots in the top 1 m), per-layer
  root-weighted transpiration withdrawal, and top-300 mm quadratic soil evaporation. Per-layer
  capacities are taken from the C run's own `whc_nat` output (no pedotransfer port); the runtime stays
  dependency-free and water closes to ~1e-12 mm.
  - Validated on Hainich (same FAPAR-driven harness): **GPP daily correlation 0.76 → 0.93**,
    **transpiration 0.91 → 0.96**, and root-zone water now representable per layer (r = 0.87) — at
    essentially unchanged levels. This **localizes the residual transpiration/GPP level gaps to the
    demand-side / single-representative-individual step, not soil supply** (the next scale-up item).
  - New gate `test/testitems/multilayer_soil_tests.jl` (per-day water closure, no-NaN, soil-water +
    GPP/transp correlations vs the C binary, ForwardDiff differentiability, drift baseline) with
    committed `references/hainich_soilcolumn.txt` + `hainich_ml_baseline_2010.txt`. Report
    `docs/phase3_fdiff_cbinary_validation.md` §8. Full suite **25,788 pass / 0 fail**. ForwardDiff
    differentiates the layered rollout; Enzyme reverse-mode through it is a documented follow-up.
- **`F_diff` ↔ LPJmL-FIT C-binary quantitative validation on the prototype cell (Phase-3 scale-up
  step 1).** `F_diff` driven by Hainich's (global-grid cell **42490**) REAL daily `.clm` forcing + the
  C binary's ACTUAL daily FAPAR (kernel-isolation drive), compared to LPJmL-FIT's own daily
  GPP/transp/PET. **PET/radiation path validated tight** (daily ratio 1.05, r 0.999); **GPP seasonal
  dynamics captured** (annual r 0.96, within-year growing-season daily r 0.96) with level −42%;
  **transpiration timing captured** (r 0.91–0.97) with level +40–47% — the level offsets attributed
  to the documented multi-PFT/representative-individual + 23-layer-soil scale-up gaps (photosynthesis
  kernel `#define`s are byte-identical, so not kernel bugs).
  - New: `scripts/run_fdiff_validation_cell.sh` (single-cell daily re-run adding daily FAPAR + NV_LAI +
    annual FPC_STAND/LAI_STAND), `scripts/extract_fdiff_validation_inputs.py` (LPJmL `.clm` YEARCELL
    reader — validated against the model's own `d_prec` to 0.0 — + `petpar2` daylength + C-target
    extraction), `scripts/validate_fdiff_vs_cbinary.jl` (multi-year analysis driver).
  - New gate `test/testitems/cbinary_validation_tests.jl` (committed one-year 2010 reference:
    `hainich_{forcing,cbinary_targets,fdiff_baseline}_2010.*`) + a `ReferenceTests` drift alarm on
    `F_diff`'s own annual totals on real forcing. Replaces the "`F_diff` pinned against ITSELF" note.
    Report `docs/phase3_fdiff_cbinary_validation.md`; metrics
    `artifacts/metrics/phase3_fdiff_cbinary_validation.json`. Full suite **25,768 pass / 0 fail**.
  - `F_diff` additions (AD-safe; the numerical-regression baseline is unchanged): `Structure.alphaa`
    (PAR-use fraction, default 1.0; TeBS 0.55), the SLA-dependent Vcmax cap (`PhotoParams.issla`,
    default off), an **external-FAPAR drive mode** (`daily_step`/`rollout`/new `rollout_daily` accept a
    per-day `fapar`), and `tebs_params()`/`tebs_structure()` (the beech PFT-3 set). The λ-solve Newton
    iterate is now `clamp`ed to the physical bracket `[0.02, 0.85]` (fixes a deep-winter low-light NaN;
    a `smooth_clamp` was rejected because `softplus(β·huge)` overflows the AD dual). That clamp is a
    conditional, so **Enzyme reverse-mode now uses `set_runtime_activity`** (still exact vs finite
    differences; ForwardDiff unaffected; the gradient-correctness gate is unchanged).
- **⚠️ Corrected the prototype-cell index:** Hainich (DE-Hai) in the **global orderA grid** (all
  ground-truth + daily data) is 0-based index **42490** (lat 51.25/lon 10.25), NOT `28008` (= Sonoran
  desert in that grid; 28008 is Hainich only in the repo default `-DSINGLESITE` grid). Fixed in
  `MEMORY.md`, `DESIGN.md`, `config/paths.yaml`.
- **Differentiable fast core (`F_diff`) — early one-cell spike (ADR 0014/0015).** Built F
  differentiable from the start (owner decision superseding the F1-now/F2-later split): the shared
  **allometry/diagnostics** library (`src/allometry.jl` — pipe-model height, Jucker 2022 crown/stem,
  LAI, Beer–Lambert FPC, pure & differentiable), a **smooth-surrogate** library (`src/fdiff_smoothops.jl`
  — softplus/smoothmin/max/clamp with tested `log(2)/β` deviation bounds), and the **`F_diff` daily
  biophysics** (`src/fdiff.jl` — C3/C4 Haxeltine & Prentice photosynthesis, the λ ci:ca supply/demand
  solve, Priestley–Taylor PET/ET, soil-water bucket + snow, Lloyd–Taylor respiration; pure
  `daily_step` + 365-day `rollout`). Same equations as the LPJmL-FIT C core, C-source constants.
  **Runtime is dependency-free**; AD is a test-time tool (ADR 0014).
  - **Gradient-correctness gate MET:** Enzyme reverse-mode **and** ForwardDiff match FiniteDifferences
    to ~1e-11 for `d(annual NPP)/dx` (x = CO₂, emax, α_c3, initial soil water) through the full daily
    rollout incl. the λ Newton solve and the autoregressive soil-water coupling — no NaN/Inf. This is
    the differentiability the reference repos do not demonstrate (they detach physics).
  - New gates: `allometry_tests.jl` (values/limits/monotonicity/types), `smoothops_tests.jl`
    (surrogate deviation bounds), `fdiff_physics_tests.jl` (water closure ~1e-12, boundedness,
    limiting cases, determinism, Float32), filled-in `gradient_correctness_tests.jl` (AD vs FD) and
    `numerical_regression_tests.jl` (annual-totals baseline `references/fdiff_annual_totals.txt`).
    Full suite: **25,756 pass / 0 fail** (JET clean; a latent `@kwdef` unbound-`T` bug in
    `FDiffParams` that JET caught was fixed). Reuse map + citations in ADR 0015 / CITATION.cff.
  - Report: `docs/phase3_fdiff_spike.md` (feasibility verdict, non-smoothness issues hit, effort
    estimate ≈ 2.5–4 months to cover all of F). `DEVELOPMENT_PLAN.md` §2.3/§6 updated.
- **Phase 0 (DESIGN)** deliverable `DESIGN.md`: re-verified the two load-bearing LPJmL-FIT
  findings (daily output is config-only; no surface energy balance), froze the shared-state
  vector and the S↔F↔E interface contract, froze the data schema, and resolved the build/run
  recipe and input-data paths. Adversarially reviewed (16/22 findings applied).
- Engineering scaffold to `ENGINEERING_STANDARDS.md`: Julia package skeleton
  (`LPJmLFITEmulator`), `@testitem` scientific-gate placeholders (conservation, gradient
  correctness, rollout stability, determinism, resilience battery, …), GitHub Actions CI
  (tests/format/docs/python/TagBot/dependabot), Documenter.jl documentation (Diátaxis +
  citations + model card + datasheets), ADRs for decisions already made, curated Mermaid +
  code/config-derived diagrams, and reproducibility wiring (StableRNGs, DrWatson, DVC, MLflow).
- Resolved `config/paths.yaml` and `config/hpc_slurm.yaml` to the real PIK cluster values
  (LPJROOT `/home/jamirp/lpjml56fit`, verified modules, production input/restart paths,
  Python env `py311_new`).

- **Component S canonical port** (`feat/port-slow-emulator`, ADR 0012): ported the slow
  distributional emulator from the now-frozen sibling `/p/projects/open/Jamir/emulator` into
  `python/src/lpjmlfit_emulator/` — `transforms.py` (signed-log + isotonic monotone links),
  `drivers.py` (annual climate/CO₂ aggregation, xarray-guarded), `features.py`
  (`build_cell_year_feats` + climclusterpy/NetCDF-guarded eco diagnostics), `baseline.py` (the
  DIRECT non-recursive climate→distribution emulator + `ResidualRegressor`/`add_competition`),
  `train.py` (holdout/train/eval helpers, matplotlib-guarded), extended `data.py` (validated
  `load_ind` loader + generalized `build_patch_summaries`, frozen 29-col schema kept), a curated
  `__init__.py` public API, and `python/config/config.yaml`. Each ported module carries a
  provenance header and was adversarially fidelity-checked against its source. New tests
  (`test_transforms.py`, `test_features.py`, `test_noise_floor.py`, extended `test_data.py`) →
  **49 passed / 6 skipped** in `py311_new`; 56 passed + ruff-clean in the locked CI env.
- `noise_floor.py`: seed1-vs-seed2 noise-floor diagnostics (per-cell magnitude floor
  `median|s1-s2|/s1`, ranking ceiling, per-cell error distribution p50/p75/p90, fraction within
  floor, latitude-band bias) layered on `metrics.py`; its test asserts the published per-variable
  floor `{Height:0.020, agb:0.113, npp:0.062, LAI:0.025}`. Rebuilt from the documented discipline
  (the sibling `eval_presentday_critical.py` is unreadable under the auto-mode classifier's
  "eval"-filename heuristic — not an owner-configured hook).

- **Phase 1 / P3b — daily-output re-run + WATER-CLOSURE gate (PASSED).** `scripts/run_daily_subset.sh`
  enables daily output (no recompile) and re-runs the Historical transient from the spinup-end
  `restart_1999.lpj` over a contiguous cell subset; `scripts/water_closure_check.py` verifies closure.
  Boreal validation run (cells 45000–45999, 2000–2002, 83 s): LPJmL's `-DSAFE` per-cell/year water
  balance passed for all 1000 cells × 3 yr (a clean run *is* closure to ≤1.5 mm/yr), daily fluxes
  integrate to the annual `globalflux` to 5 sig figs, cumulative per-cell imbalance median 2.7 %, and
  daily NPP → annual NPP ratio 1.000. Report: [`docs/phase1_p3b_water_closure.md`](docs/phase1_p3b_water_closure.md);
  summary `artifacts/metrics/p3b_water_closure_boreal_c45000_45999.json`. Verified against LPJmL source
  (adversarially): contiguous-subset restart via 0-based positional `startgrid`/`endgrid`; daily via
  `"timestep":"daily"` in the entry's `file` object; `swc` is fractional saturation (`wsats` not output);
  build modules need `json-c/0.13.1` (not 0.17).
- **Full-global daily F/E training dataset generated** — all **67,420 cells × 2000–2019** (186 GB,
  daily prec/transp/evap/interc/runoff/swe/swc/rootmoist/whc_nat/pet/npp/gpp), restarted from the seed1
  spinup-end restart so it reproduces the seed1 Historical trajectory at daily resolution. Water closure
  re-confirmed at scale: clean run with no water-balance error (SAFE, all cells × 20 yr), daily fluxes
  integrate to the annual `globalflux` to ~5 sig figs, per-cell multi-year imbalance median 0.87 %.
  Summary `artifacts/metrics/p3b_water_closure_global_c0_67419.json`; data on `/p/tmp` (DVC, not in git).
  Generator/analysis parameterized (`TIME`/`EXCLUSIVE`) + made dask-lazy/memory-safe for the ~185 GB
  scale. Both Phase-1 gates (carbon + water) now pass.
- **Phase 2 (slow emulator, offline) — gate met at the baseline tier.** `scripts/train_slow_emulator.py`
  trains the ported DIRECT `DirectEmulator` on a biome-stratified 6000-cell set and scores rendered
  holdout distributions vs the seed1-vs-seed2 noise floor (random in-distribution + warm+dry OOD),
  building `tree_step`/`grass`/holdout subsets from the `ind` parquet. In-distribution: median KS 0.023,
  joint energy within 1.72× the floor, drift-free, per-cell NPP conserved ~21% median. Warm+dry OOD:
  ks 32× floor — the documented equilibrium-ML limitation the Phase-3 hybrid targets. No generative
  escalation triggered (ADR 0005). Report [`docs/phase2_slow_emulator.md`](docs/phase2_slow_emulator.md);
  artifacts `artifacts/metrics/phase2_slow_emulator_{random,oodwarm}_6000.json`.

### Changed
- **Workflow → main-only** ([ADR 0013](docs/decisions/0013-main-only-workflow.md)): commit and push
  straight to `main`; no feature branches, PRs, or branch protection (owner declined), and no
  signed-commit enforcement. CI still runs on `push: main` as a smoke alarm (fix-forward if red).
  `ENGINEERING_STANDARDS.md` §1 softened to point at the ADR (original PR/branch-protection posture
  retained struck-through, with the reinstatement command).
- `.github/dependabot.yml` **tamed**: monthly (was weekly) + grouped updates (one consolidated PR per
  ecosystem per cycle) to stop the per-package branch spam.
- `ENGINEERING_STANDARDS.md` §2 and `DESIGN_CHECKPOINT_PROMPT.md` item 2 now lead with an explicit
  **unit-test foundation** (testing pyramid: unit → integration → system) beneath the scientific
  gates, with a project-specific unit-test list (allometry, unit conversions, softmax/allocation,
  config parsing, data loaders, index/date math, numerical kernels, error handling).

### Fixed
- **CI green on `main`** — repaired the three workflows that were red on `57e3a95` (three independent
  causes):
  - `python`: floating `>=` deps with no lockfile let CI resolve breaking majors. Added upper-bound
    caps matching the known-good `py311_new` set, committed `python/uv.lock`, and switched the job to
    `uv sync --frozen`. Also ran `ruff format` on the never-formatted scaffold sources.
  - `format`: reformatted all 18 tracked Julia files with Runic 1.7.0 (the version the job installs).
  - `docs`: fixed a broken `[`checkdims`](@ref)` cross-reference (non-exported symbol → added a
    `CurrentModule` @meta block), enabled `linkcheck` with an ignore for private-repo self-links, and
    silenced two DocumenterCitations `.bib`-comment warnings. Each fix was reproduced and verified
    locally (uv venv for Python; local Julia 1.10 + Documenter 1.17 for format/docs).

### Validation
- Scaffold validated locally end-to-end: **Julia `Pkg.test()` green** (21,071 assertions pass, 6
  intentional `@test_broken` Phase-6 placeholders, 0 fail/error; Aqua + JET clean), **Python `pytest`
  green** (21 pass in `py311_new`), diagram diff-alarm (`gen_diagrams.jl --check`) green, all CI YAML
  parses, and `bin/lpjml -h` runs (netcdf-c/4.9.2). JET caught and fixed a real `SharedState`
  constructor bug (`@kwdef` unbound type parameter) during scaffolding.

### Notes
- No modelling behaviour yet — this release is the design freeze + auditable engineering skeleton.
- Data, model weights, and restarts are never committed (tracked via DVC pointers).
- Root `Manifest.toml` deferred until Phase-3+ deps are added (the package currently has empty `[deps]`).

[Unreleased]: https://github.com/rimajj/LPJmLFIT_Emulator/commits/main
