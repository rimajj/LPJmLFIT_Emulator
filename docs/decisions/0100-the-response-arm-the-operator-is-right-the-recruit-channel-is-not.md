# ADR 0100 — the RESPONSE arm: the ported hazard contributes the right response, and it exposes a larger error of the OPPOSITE sign in the recruit channel

* **Status:** Accepted
* **Date:** 2026-08-05
* **Line:** S (Component-S science) · **ADR block 0100–0119 — this ADR OPENS line S's tier-2 block**, because
  ADR 0049 exhausted the tier-1 block 0030–0049. `docs/decisions/README.md` now pre-allocates a tier-2 block
  for every line (S 0100–0119 · M 0120–0139 · E 0140–0149 · O 0150–0159 · integrator 0160–0169) so an
  exhausted line never has to negotiate a range mid-milestone again, and two lines exhausting in the same
  week cannot collide.
* **Decides:** Phase 3A **Stage 3** — how the trait-mortality arm's *warming response* is measured (as
  opposed to ADR 0049's constant-forcing *level* change), and what that measurement says. Four decisions:
  **(1)** the response is measured as a **2×2 double difference** on **real two-scenario forcing taken from
  the same `.clm` files the two LPJmL-FIT ground-truth runs used**, all four rollouts advanced in one process
  at matched year indices; **(2)** the headline is a **window mean**, not a terminal-year read; **(3)** the
  roster cap is raised until the k-cap merge is **dormant**, and the production-cap run is demoted to a
  sensitivity check; **(4)** the arm is accepted, and the finding it produces — that the emulator's *baseline*
  warming response has the **wrong sign** and is larger than the operator's contribution — is recorded as the
  next lever rather than folded into this arm.
* **Related:** ADR 0049 (Stage 2 — the wiring, the tilt, and the count-channel throttle), ADR 0048 (the
  measurement protocol; the merge is trait-destructive at 3.1–5.1× the signal), ADR 0046 (the target: FIT's
  shift is within-PFT, within-age selection, +2432.9 gC/m³ per cell), ADR 0026/0027 (the transient boundary /
  `boundary_series`), ADR 0034 (the trained-band excursion diagnostic), ADR 0025 (`live_flux_cond`, the
  copula's conditioning subset), ADR 0004 (ssp370 CO2 is flat 409.63 from 2020), ADR 0044 (the global
  response gate — **nothing here may be quoted against it**)
* **Evidence:** `scripts/build_hainich_response_forcing.py` (three gates, all green);
  `scripts/trait_mortality_arm_probe.jl` `MODE=response`; jobs `1700471` (primary, merge dormant),
  `1700472` (production-cap sensitivity), `1700508` (primary + the band diagnostic), `1700644` (primary
  re-run on the corrected fixture — identical to the digit), `1700483` (the **Stage-2 regression** —
  reproduces every ADR-0049 headline number), `1700642` (suite); committed fixture
  `test/testitems/references/S_hainich_response_boundary.csv` + `test/testitems/slow_response_boundary_tests.jl`.

## Context

ADR 0049 wired ADR 0047's ported FIT mortality hazard into `reconcile_demography!` and measured it against a
matched control: controlled Δ community wood density **+7 899 gC/m³ = 3.25× the FIT shift, same sign**, with
the right age structure. But it measured that under **constant forcing** — one repeated year — so it is a
**level** change. FIT's +2432.9 is a **between-scenario** difference (its historic run vs its ssp370 run), and
ADR 0049's own Consequences say so explicitly: *"Do NOT quote 3.25× the FIT shift as a response."*

The question Phase 3A exists to answer is therefore still open: does the operator make the emulator's wood
density respond to *warming* the way FIT's does? Answering it needs the emulator run under two climates.

## Decision

### 1. The scenario pair is FIT's own contrast, including its confounds

`scripts/build_hainich_response_forcing.py` extracts, for one cell, the real daily forcing of **both**
scenarios from the same orderA `.clm` files the two ground-truth runs read — historic (`*_test.clm`,
observational, real rising CO2) 1939–2019 and ssp370 (`*_mpi-esm1-2-hr_ssp370_*_orderA.clm`, CO2 flat at
409.63 from 2020 per ADR 0004) 2020–2100, **81 years each so the arms difference at matched year indices**.
Measured contrast at Hainich: **+2.45 K** mean air temperature, +6.98 W/m² shortwave, −0.03 mm/day precip,
+709 gdd5, **+2.53 K** coldest-month mean.

Using FIT's own two forcings is what makes the result the analogue of FIT's +2432.9 — and it inherits FIT's
confounds, which travel with the number rather than being hidden: **the two scenarios are different data
sources** (reanalysis vs one GCM, so a model bias enters the difference alongside the warming) and their
**mean CO2 differs by +65.9 ppm** (343.8 vs 409.63). The builder prints both every run.

A synthetic ΔT ramp was rejected: it would have made every number arguable as *"that is not ssp370"*, and the
real files were available at a cost of seven seconds.

**The daily forcing is deliberately NOT committed** (1.7 MB/scenario; the `.clm` sources are 4–12 GB). What
*is* committed is `S_hainich_response_boundary.csv` — per (scenario, year) the two ADR-0026 transient boundary
axes plus the five per-year forcing means, 16 kB — so a later session can verify a rebuild produced the same
forcing without shipping it.

### 2. Three gates, because a forcing extraction that is wrong is worse than none

1. the historic trailing-W=20 boundary reproduces the committed `climbuf_hainich_boundary_w20.csv` (worst
   |diff| **4.9e-06** on a gdd5 of ~1800 — a float32 print artefact, i.e. exact);
2. the historic 2010 daily block reproduces the committed `hainich_forcing_2010.csv` — **the fixture the
   Stage-2 arm was itself measured on** — to ≤ 1.8e-05 on every variable, which is what proves the cell index,
   the YEARCELL decode, the v2-int16-×0.1 vs v3-float32 branch (CLAUDE.md §3) and the units all agree;
3. ssp370 CO2 is flat 409.63 from 2020 (ADR 0004) — a rising value would mean the wrong forcing file.

The builder **imports** `build_transient_boundary.py`'s `open_clm`/`gdd5_tcm`/`MONTH_BOUNDS` rather than
re-deriving them, so gate 1 is a comparison against the global builder's own method and not against a second
implementation of it.

### 3. The headline is a WINDOW MEAN, and the roster cap is raised until the merge is dormant

Two protocol decisions that each changed the answer by more than a FIT shift:

* **Window mean, not terminal year.** With real interannual forcing the year-to-year interaction swings by
  more than the signal: measured **−1 070 → +290 → +3 132 → +239 → +5 388** across report years 10/20/40/60/81.
  FIT's +2432.9 is itself a run mean. The headline is therefore the mean over the last `SCORE_WINDOW` = 20
  years, and the terminal-year read is printed beside it. Scoring the terminal year alone would have reported
  **+5 388 = 2.21× FIT** where the honest number is **+3 401 = 1.40×**.
* **The k-cap merge, dormant for 150 constant-forcing years, WAKES under real forcing.** ADR 0048 measured 0
  merges in 150 yr at the default cap and concluded the confound was absent; the response arm's real forcing
  appends more recruits and hit the default `max(2K, 40)` = 40 cap **8–9 times per arm in 81 years**. Since
  ADR 0048 also measured the merge as trait-destructive at 3.1–5.1× the signal, the primary run raises
  `k_cap` to 400 (merge count 0 in all four corners) and the production-cap run becomes a sensitivity check.
  **This is the first quantitative measurement of the merge's cost on a RESPONSE rather than a level, and it
  is large: the merge destroys 54 % of the operator's response contribution** (+1 552.6 = 0.638× FIT at the
  default cap vs **+3 400.6 = 1.398× FIT** merge-free). ⇒ *the default cap is wrong for any transient run,
  and "the merge is dormant" is a property of a forcing configuration, never of the cap.*

### 4. `MODE=stage2` stays byte-identical — the regression is a job, not an intention

`rollout(...)` gained `forcing`, `boundary_series`, `t_soil0` and `k_cap` knobs, all defaulted to the
Stage-2 construction. Job `1700483` re-ran the ADR-0049 measurement through the modified harness and
reproduced **every** headline number: 132 of 150 thinning years, θ median **8.453e-12**, 0 k-cap merges,
worst |Δwd| 11 256.4 at yr 46, scored Δwd **+7 899.35 = 3.2469×**. Guardrail 4 holds by measurement.

## What the arm says

Hainich only (guardrail 6), 81 yr per corner, merge dormant, carbon closing at 0.8–1.6e-11 in all four
corners, `boundary_series` transient on both scenarios.

| community wood density (gC/m³), mean over yr 62–81 | ctl (`trait_mortality=false`) | arm (`true`) | Δ = arm − ctl |
|---|---|---|---|
| historic forcing | 231 338.9 | 237 522.4 | **+6 183.5** |
| ssp370 forcing | 225 393.1 | 234 977.1 | **+9 584.0** |
| **R = ssp370 − historic** | **−5 945.8** | **−2 545.2** | **interaction +3 400.6** |

As a share of FIT's +2432.9 per-cell shift:

| | value | ×FIT |
|---|---|---|
| `R_ctl` — the **pre-0049 emulator's own** warming response | −5 945.8 | **−2.44×** |
| `R_arm` — with the ported hazard wired in | −2 545.2 | **−1.05×** |
| **interaction `R_arm − R_ctl` = the operator's contribution to the RESPONSE** | **+3 400.6** | **+1.40×** |

### 1. The operator's response contribution is the right sign and the right order of magnitude

**+1.40× the FIT shift, positive, from a mechanism that has no knowledge of FIT's answer.** This is the
measurement Phase 3A was created to make, and the one ADR 0049 explicitly declined to claim.

Read from the other direction it is the same statement and easier to interpret: **the operator's level effect
is itself larger under warming — Δ = +6 183.5 = 2.54× FIT under historic forcing, +9 584.0 = 3.94× under
ssp370 — and that increase *is* the response contribution** (3.94 − 2.54 = 1.40). So the operator does not
merely add a constant offset that survives a scenario difference; it selects *harder* in a warmer climate,
which is what a within-PFT selection mechanism should do and what §3 explains. (The historic-forcing level
2.54× is also the like-for-like successor to ADR 0049's constant-forcing 3.25× — real interannual forcing
reduces the level effect somewhat, and neither number is a response.)

### 2. THE FINDING: the emulator's BASELINE warming response has the WRONG SIGN, and it is larger

FIT's community wood density **rises** +2432.9 under warming. The pre-0049 emulator's **falls** 5 945.8 —
wrong sign, 2.44× FIT in magnitude. The ported hazard **shrinks that wrong-signed response by 57.2 % in
magnitude** (−2.44× → −1.05×) and **closes 40.6 % of the gap to FIT's +2432.9** (error −8 378.7 →
−4 978.1), but does not flip the sign, because the error it has to cancel is larger than the mechanism it
adds. Both bases are given because they differ and the magnitude one flatters the result — the gap-closed
figure is the honest headline.

**The residual is attributable, and the attribution is forced, not inferred.** `wooddens` is immutable after
`new_tree`, so the `nind`-weighted community mean can only move if the *weights* move. In the control there
are exactly three ways that can happen, and two are excluded by construction: the ρ-thinning scales every
cohort's `nind` by **one** factor (composition-preserving to floating point — ADR 0046 §4), and a cohort is
**removed only inside `_merge_pair!`**, whose sole caller is `_apply_kcap_merge!` — verified by inspection:
every `deleteat!` in `slow.jl` is in that one function, and the merge count is **0 in all four corners**. The
remaining channel is recruits entering with copula-drawn traits, so `R_ctl` **is** the recruit channel's
warming response — and it points the wrong way. Two candidate causes, distinguished by §5's band diagnostic:

* the `.rcop` is fit on the **historic scenario alone** (`scenario historic` in its meta), so ssp370
  conditioning values may be an **extrapolation** ⇒ the fix is retraining on the pooled historic+ssp370 table
  (an artifact version bump, S→M integration point);
* or the conditioning values are in band and the artifact's genuine conditional response has the wrong sign
  ⇒ the fix is the **conditioning set**, i.e. milestone S2, and Phase 3A cannot deliver it.

This reframes the line's priority: **the mortality channel is no longer the binding constraint on the
warming response — the recruit channel is.** ADR 0049 handed forward "co-occurring gross turnover" as the
named next lever; this measurement demotes it, because a larger opposite-signed error sits upstream of it.

### 3. Warming LOOSENS ADR 0049's count-channel throttle

ADR 0049's central limit was that the DRF demands ~zero net death in most years, so the operator has nothing
to redistribute (θ median 8.5e-12; θ > 0.5 in 13.6 % of thinning years). Under real forcing the throttle is
much looser, and **warming loosens it further**:

| | thinning yr | ported hazard | DRF's demanded \|ρ−1\| | θ median | θ mean | θ > 0.5 |
|---|---|---|---|---|---|---|
| ADR 0049, constant forcing, 150 yr | 132 | 1.688 %/yr | **0.608 %/yr (median 0.0)** | 8.5e-12 | 0.418 | 13.6 % |
| historic forcing, 81 yr | 48 | 1.410 %/yr | 1.868 %/yr | 0.965 | 1.566 | **54.2 %** |
| ssp370 forcing, 81 yr | 48 | 1.406 %/yr | **2.176 %/yr** | 0.941 | 1.763 | **62.5 %** |

So ADR 0049 §5's 13.6 % duty cycle is **an artefact of constant forcing**, not a property of the emulator's
demography: a real climate makes the DRF's target move every year, and the operator selects in a majority of
thinning years. The gross-vs-net argument still holds in principle (deaths and recruits remain mutually
exclusive within a year), but its measured cost was overstated ~4× by the constant-forcing basis. This is
also why the response contribution (1.40×) is comparable to the level contribution (3.25×) rather than an
order smaller.

### 4. The boundary channel is EXACTLY inert for this cell's committed artifacts

Measured, not assumed: rerunning the ssp370 control with `boundary_series = nothing` gives `max |Δwd| = 0.0`
against the transient run. Cause is in the metadata — the demo `.drf` has `feat_min == feat_max` on both
`eco_diag_gdd_5` and `tas_cold_month`, and the `.rcop`'s conditioning row is a single point, so a forest can
carry **no split** on those columns and the copula **no conditional variation**. Two consequences:

* good news for this arm — the response above is carried entirely by the flux/state head, which *is* trained
  over a real range, so **none of it is a boundary extrapolation**;
* a real limitation of the **per-cell demo artifact**, not of the mechanism: a +709 gdd5 / +2.53 K
  coldest-month shift moves nothing. The global `pooled_w20` artifacts train on a live transient boundary
  (ADR 0026) and do not have this defect, so any global re-measurement must not inherit this null.

**Independently re-confirmed, by accident.** A defect found in the fixture *after* the primary run — the
historic trailing window had no lead-in, so its first 19 years were computed on a truncated climatology
(1939's `tas_cold_month` read −3.11 °C off a 1-year window instead of **−0.54**) — was fixed and the primary
re-run (job `1700644`). **Every headline number came back identical to the digit** (`R_ctl` −5 945.79,
`R_arm` −2 545.21, interaction +3 400.58): 19 changed boundary rows moved nothing, which is what §4 predicts
and a second, unplanned test of it. *Gate 1 did not catch that defect* because it samples 2000–2019, where the
window is already full — a gate that only checks the easy end of a range does not cover the range.

### 5. Trained-band excursion says it is an EXTRAPOLATION, and names `soilmoist` as the channel

The discriminating measurement is not *"is the runtime out of band"* — for `water_stress` the answer has been
yes since S1d and it is line M's — but *"does the ssp370 arm go **further** out than the historic one"*. Only
a scenario-dependent excursion can make `R_ctl` an extrapolation artefact rather than a genuine conditional
response. Excursions below in **trained-band widths**, from `feature_history` against the demo `.drf` meta's
`feat_min`/`feat_max` (same training generation, and per the S1c gate the same basis on all shared columns):

| copula conditioning column | trained band | historic range | ssp370 range | exc_hist | exc_ssp | **ssp/hist** |
|---|---|---|---|---|---|---|
| `bm_inc_cell` | [132.7, 757.7] | [445.0, 775.4] | [453.7, 803.8] | 0.028 | 0.074 | 2.6× |
| `growth_eff` | [114.3, 251.6] | [96.5, 146.5] | [80.3, 195.7] | 0.130 | 0.248 | 1.9× |
| `water_stress` | [0, 0.0432] | [~0, 0.0713] | [~0, 0.0570] | **0.653** | 0.320 | **0.49×** |
| **`soilmoist`** | [0.7908, 1.0] | [0.7823, 0.9991] | **[0.6532, 0.9991]** | 0.041 | **0.658** | **16.1×** |

**`soilmoist` is the channel.** The ssp370 arm drives the root-zone soil moisture **0.658 band widths below
anything the copula was trained on** — a **16×** larger excursion than the historic arm — while the copula is
fit on the **historic scenario alone**. And a DRF/copula asked for an out-of-band input does not extrapolate,
it **saturates**: a forest prediction is a convex combination of training leaf means (the S1d proof), so the
recruit conditional under a drying ssp370 climate is **clamped to the driest leaf the historic run contains**.
That is a sufficient mechanism for a wrong-signed `R_ctl`, and it is a defect of the *artifact's training
scenario*, not of the conditioning set.

Two exclusions the table also buys, both worth keeping:

* **`water_stress` is NOT the scenario-specific driver.** Its excursion is *larger* under historic (0.653 vs
  0.320, ratio 0.49×) — so S1d's known out-of-band column, which is line M's to fix, cannot be what makes the
  ssp370 arm different. A retune of it would not move `R_ctl`.
* **The two boundary rows read `Inf`** because their trained band has **zero width**. That is §4's measured
  inertness seen from the other side: a column that is constant in training is infinitely out of band *and*
  carries no split, so it is simultaneously the most extreme excursion in the table and provably harmless.
  Any diagnostic that ranks excursions must special-case a zero-width band, or it will rank the one channel
  that cannot act above the one that does.

**The falsifiable prediction this hands forward:** re-running this arm against the **global pooled_w20
`.rcop`/`.drf`** — trained on historic **and** ssp370, so `soilmoist` down to 0.65 is in band and the boundary
axes are live — should shrink `|R_ctl|` substantially or flip its sign. If it does not, the cause is the
conditioning set (milestone S2) rather than the training scenario, and Phase 3A cannot deliver it.

## Consequences

* **Phase 3A Stage 3 is DONE, and Phase 3A's mechanism claim is now complete**: the ported hazard produces a
  warming response of the right sign and order (+1.40× FIT) on top of the right level change and the right
  age structure (ADR 0049). `trait_mortality` remains **opt-in and default-off**, so every committed
  baseline, ReferenceTest and AD path is unchanged and runtime `[deps]` stays empty.
* **The next lever is the RECRUIT channel, not more mortality fidelity — specifically, a POOLED-scenario
  artifact.** ADR 0049's "co-occurring gross turnover" is demoted: it would enlarge a mechanism that already
  has the right sign, while the larger error points the other way and lives upstream. §5 localises it to
  `soilmoist` running 0.66 band widths below a historic-only copula's training range, so the cheapest next arm
  is re-running this 2×2 against the existing global `pooled_w20` artifacts (no new training) and checking
  whether `|R_ctl|` shrinks. That also lifts §4's boundary-inertness null, since those artifacts train on a
  live transient boundary.
* **`k_cap` is now a documented confound for any transient run** — the default cap costs 54 % of the response
  contribution, and its dormancy under constant forcing does not transfer. Any future arm on real forcing
  must report the merge count per corner and raise the cap until it is 0.
* **ADR 0049 §5's 13.6 % duty cycle must be quoted with its basis.** It is a constant-forcing number and is
  ~4× pessimistic about real forcing. §3 supersedes its *interpretation* (the count channel is a weaker
  bottleneck than stated), not its mechanism (gross ≠ net remains true).
* **Nothing here may be quoted against the ADR-0044 response gate.** That gate is global, its P1 threshold is
  `ΔRr ≥ +0.036`, `Rb` is veto-only, and *"reduced the damping from A % to B %"* remains forbidden language
  (ADR 0044 §2: the residual is PLACEMENT, not shrinkage). This is one cell, on a demo artifact whose
  boundary channel is inert, with FIT's own two confounds attached.
* **`fc.pft_ids` remains M integration point #1** and is unchanged by this arm (ADR 0049 §Consequences).
* **The S→M contract is untouched.** No kwarg was removed, no artifact format, feature order or
  `live_flux_cond` subset moved; the new knobs are probe-side and defaulted.

## Alternatives rejected

* **A synthetic ΔT/CO2 ramp instead of the real ssp370 files.** Cheaper, and every number would have been
  arguable as not-ssp370. §1.
* **Scoring the terminal year.** Would have reported +2.21× FIT instead of +1.40×, on a quantity whose
  year-to-year swing exceeds the signal. §3.
* **Running the primary at the production `k_cap`.** Would have reported +0.638× FIT and silently attributed
  a merge artefact to the hazard — precisely what ADR 0048 built its merge diagnostic to prevent. §3.
* **Committing the daily forcing.** 3.4 MB of data in a repo whose rule is no datasets; the per-year means
  are committed instead and the builder is deterministic and gated. §1.
* **Treating `R_ctl`'s wrong sign as this arm's problem to fix.** It is a recruit-channel defect, it needs
  its own ADR and its own matched control, and bundling it here would leave two operators changing at once
  with one control — handoff item F, which has now caught seven wrong turns on this line.
* **Concluding "the emulator's warming response is wrong" from a single cell.** The sign is a strong claim
  and it is stated as *measured at Hainich on the demo artifact*, with the global re-measurement named as the
  test. Guardrail 6.
