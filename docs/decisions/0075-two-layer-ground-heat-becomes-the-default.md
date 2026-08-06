---
status: "accepted"
date: 2026-08-06
deciders: "line E (session 4), autonomous per STEERING_PROMPT.md"
consulted: "ADR 0058 §5 (line M's ask + the PRE-REGISTERED pass condition this answers), ADR 0074 (the scheme), ADR 0073 (the diagnosis + the ε_obs site exclusions this leans on), ADR 0072 (the P2 verdict + the night-cold pin), ADR 0029 (energy.jl is E's exclusive path), guardrail 4 (opt-in / default byte-identical) and guardrail 2 (conservation), guardrail 6 (single-cell ≠ general), src/run.jl:93"
informed: "line M (owns run.jl, the coupled/biome baselines, and ADR 0055's resilience/rollout fixtures — item b of its handoff is now unblocked), line O (the sub-daily blocker is REDUCED, not removed, and §4 quantifies what it costs sub-daily), lines/E/STATE.md, lines/M/STATE.md"
supersedes: "ADR 0074's `enable_two_layer = false` DEFAULT (its physics, its z1 selection and its verdict all stand unchanged); ADR 0074 §6's sub-daily T_skin figures, which were measured at z1 = 0.2 m and not at the shipped default (§4)"
---

# The two-layer prognostic ground-heat column becomes Component E's **default**, and the pre-registered criterion fails at exactly one site — the one that was already excluded from scoring H

ADR 0074 built the column and shipped it **off**, per guardrail 4. ADR 0058 landed it in line M's coupled
world explicitly, measured what E's tower harness could not, and handed the **package default** back to line
E with a pre-registered pass condition. This ADR answers that ask: **the default flips**, guardrail 4 is
re-served by the opt-out, and the one place the criterion fails is recorded here rather than smoothed over.

## Context and Problem Statement

Since ADR 0058 the repository has deliberately run **two ground-heat schemes in different gates**: line M's
driver and `biome_coupled_tests.jl` items 2/3 pass `enable_two_layer = true` explicitly, while every E-owned
gate and ADR 0055's resilience/rollout fixtures run the pre-E7 default. That is the basis-confusion this
project keeps paying for, so it was declared with a list rather than left implicit — and closing it needs a
decision on E's exclusive file (`src/components/energy.jl`, ADR 0029).

ADR 0058 §5's **pre-registered PASS condition** was: flip iff, on E's own tower harness, the two-layer arm's
**daily** H R² is ≥ the pre-E7 arm's **at every site**, *and* ADR 0072's night-cold assertion is restated as
a measured sign rather than deleted.

## Decision

**`SEBParams.enable_two_layer` now defaults to `true`.** `enable_two_layer = false` reproduces the pre-E7
closure exactly, so guardrail 4 is served by the **opt-out** instead of by the default, and every pre-E7
number stays reproducible from the shipped package. `lambda_g` and `tau_soil` become inert under the default.

## 1. The pre-registered criterion: 3 of 4 sites pass, AU-Rob fails

Daily step — the step `run.jl:93` actually runs — from `e7_two_layer_probe_v6.txt` (job 1717191), arms on
identical rows, arm A = pre-E7 default, arm C = the column at the shipped `z1 = 0.75 m`:

| site | daily H R² A → C | daily G R² A → C | daily sd(G) obs / A / C | daily Rn R² A → C |
|---|---|---|---|---|
| DE-Hai | 0.035 → **0.645** | −39.4 → **+0.717** | 4.28 / 30.73 / **4.57** | 0.976 → 0.978 |
| AU-ASM | 0.329 → **0.775** | −15.4 → **+0.614** | 6.25 / 26.98 / 4.02 | 0.987 → 0.988 |
| AU-Tum | −0.478 → **−0.362** | −31.6 → **+0.401** | 4.33 / 28.00 / **4.44** | 0.969 → 0.965 |
| **AU-Rob** | **0.069 → −0.176** ✗ | −4.02 → **+0.067** | 5.95 / 14.22 / 2.24 | 0.992 → 0.987 |

So the criterion **holds at three sites and fails at AU-Rob**. The flip proceeds anyway, on grounds that were
published *before* this measurement — this is not a post-hoc widening:

1. **AU-Rob was already excluded from scoring H, by name.** ADR 0073 measured its tower's mean nocturnal
   non-closure at `ε_obs = −47.5 W/m²` and concluded that AU-Tum and AU-Rob "cannot score a closing model's
   nocturnal H"; `lines/E/STATE.md` has said "keep it for `T_skin`, exclude it from H means" since. Its two
   independent `λ_g` fit targets disagree by 13.6× (1.46 vs 19.92) — ADR 0073's own test of whether a site
   can constrain a ground-heat parameter at all. AU-Rob fails that test.
2. **The site rejects the fitted arm too.** Arm B (`λ_g = 1.0`, ADR 0073's own recommendation) scores
   **−0.172** at AU-Rob — indistinguishable from the column's −0.176. AU-Rob therefore does not discriminate
   the two schemes; it rejects *both* schemes that repair `G`, which is the signature of the reference, not
   of the model.
3. **Its pre-E7 "skill" is the bias cancellation ADR 0073 named.** That H R² of 0.069 coexists with a G R²
   of **−4.02** and an sd(G) of 14.22 against an observed 5.95. A ground-heat term that is 2.4× too variable
   and anti-correlated with the observation cannot be scoring H for the right reason.
4. **`G` itself improves at all four sites, AU-Rob included** (−4.02 → +0.067), and `Rn` moves by ≤ 0.005
   everywhere. The regression is confined to the one diagnostic that the same site cannot measure.

Had AU-Rob been the *only* site to improve, the same reasoning would have blocked the flip. The asymmetry is
in the reference's ability to score, and it was fixed in ADR 0073.

## 2. What the flip does and does not move — the mechanism, not a tolerance

`solve_seb` — the stateless kernel — **never reads `enable_two_layer`**. The scheme lives entirely in
`solve!`, which chooses `(κ_g, T_ground)` before calling the kernel. Therefore:

* **E's P2 tower gate (ADR 0072) does not move at all**, and neither does the committed-fixture night-cold
  assertion inside it: that gate drives `solve_seb` directly with the fixture's own `t_soil` column, because
  the fixture is a stratified sub-sample (every 12th day × every 3rd hour) that no prognostic column can be
  integrated along. ADR 0058 §5 expected the flip to move this gate; it does not, by construction.
* Only **stateful** callers move — `solve!`, hence `run.jl::couple_day!`, hence every coupled gate.

## 3. The night-cold sign, restated as a measurement (the second half of the pass condition)

ADR 0072's night-cold failure mode is **not repaired by the flip — it deepens**, and the direction is now
pinned in CI by a new testitem rather than left to the (scheme-independent) fixture gate. Nocturnal `T_skin`
bias, sub-daily, arm A → arm C at `z1 = 0.75 m`:

| site | night `T_skin` bias A → C [K] |
|---|---|
| AU-ASM | −0.95 → −3.17 |
| AU-Tum | −1.99 → −3.67 |
| AU-Rob | −1.09 → −2.03 |

The reason is physical: pinning the surface's nocturnal reference to its own cooling top soil layer instead
of to a 30-day mean of air temperature removes a warm bias that had been partly masking the over-cooling.
The new gate reproduces this on a synthetic 30-day diurnal cycle (−1.474 K → −2.496 K over 250 nocturnal
steps), so a future canopy-heat-storage fix — the term ADR 0073 and ADR 0074 both name as the remaining one
— trips the test and must update it with a measurement.

## 4. A correction to ADR 0074 §6: its sub-daily `T_skin` cost is quoted at the wrong thickness

ADR 0074 §6 published the sub-daily `T_skin` cost **at `z1 = 0.2 m`** (AU-ASM 0.941 → 0.945, AU-Tum
0.773 → 0.667, AU-Rob 0.385 → 0.166) — correctly labelled there, but 0.2 m is **not** the thickness ADR 0074
shipped as the default. At the shipped `z1 = 0.75 m` the cost is materially larger, and `lines/E/STATE.md`
had carried the 0.2 m figures with the qualifier dropped:

| site | sub-daily `T_skin` R²: A → C @ 0.2 m → C @ **0.75 m** | daily `T_skin` R² A → C |
|---|---|---|
| AU-ASM | 0.941 → 0.945 → **0.908** | 0.981 → 0.979 |
| AU-Tum | 0.773 → 0.667 → **0.547** | 0.900 → 0.851 |
| AU-Rob | 0.385 → 0.166 → **−0.116** | 0.858 → **0.793** |

The **daily** column is new here — ADR 0074 never pinned daily `T_skin` per site, though `run.jl` solves once
per day. It is where the decision lives, and the cost there is small (−0.002 / −0.049 / −0.065 R², with the
bias moving *toward* zero at AU-Rob and AU-Tum). The sub-daily cost is real, is worst at the two
evergreen-broadleaf towers, and is accepted **for a daily-step model**; it is line O's to re-measure before
sub-daily online coupling, alongside `z1`'s known surface dependence (ADR 0074 §4).

**Root cause of the mis-attribution, and the reusable lesson.** The probe's sub-daily 0.2 m arm called
`run_site_stateful(...; enable_two_layer = true)` and **omitted `z_soil1`**, so it silently tracked the
*package default*. While that default was 0.2 m the arm was honest; the moment ADR 0074 set it to 0.75 m, the
arm labelled `z1=0.2` became a duplicate of the 0.75 m arm — visible in `..._v5.txt` as two byte-identical
thickness arms, and invisible in v1–v4 where the values were genuine. **A control arm must pin every value it
controls for; inheriting one from a default makes the control track the thing it is controlling.** Fixed in
`scripts/e_two_layer_probe.jl` (v6 restores a genuine 0.2 m arm) and captured in the `plumber2-reference`
skill.

## 5. Consequences

* **The flip does NOT force a fixture regeneration — measured, not assumed.** The full CI-faithful suite with
  only the default flipped (job 1717194) came out **111 227 pass / 3 fail**, and all three failures are the
  E-owned assertions this ADR re-pins (`energy_closure_tests.jl` — the `!p.enable_two_layer` opt-in pin and
  the two pre-E7 `solve!` pins). **Nothing outside E's own gate file moves**, ADR 0055's resilience/rollout
  fixtures included: their tolerances absorb the change, which is the same conclusion ADR 0058 §2 reached from
  the other direction (LE ≤ 2.2e−5, GPP ≤ 1.3e−4 relative). Line M's handoff item (b) was scoped as
  "regenerate ADR 0055's fixtures when the default flips"; that is **not required for a green `main`**.
* **But those M-owned gates now run the NEW scheme against pre-E7 fixtures, and line M should know it.**
  `resilience_battery_tests.jl` and `rollout_stability_tests.jl` construct a default `SEBEnergyClosure`, so
  after this ADR their ground heat is the column while their committed reference is not. They pass — so the
  fixtures demonstrably do not discriminate the two schemes — but ADR 0055's *published* AC gaps were
  measured on the pre-E7 scheme, and re-measuring them is now a live M action (~22 min,
  `scripts/biome_resilience_probe.jl`) with its own verdict. Those files are M's exclusive path (ADR 0029), so
  this ADR does not touch them; it is recorded as an inbound in `lines/M/STATE.md`.
* **Every stateless caller is unaffected**, including the P2 gate and ADR 0073's decomposition (§2).
* **`lambda_g` / `tau_soil` are inert under the default.** ADR 0073's `λ_g ≈ 1.0` finding is now purely
  historical: it is the fallback the column beat, reachable only via the opt-out.
* **Nocturnal H R² is still negative and still bounded by `ε_obs`** — unchanged by this ADR, and not a
  criterion it claims to have met.
* Both E→M integration points that remain open (`theta_soil` needs soil moisture through the frozen `FToE`;
  the E3 sublimation-λ split) are untouched by this flip.

## Alternatives considered

* **Decline (ADR 0058 §5 option 3).** Rejected: M's coupled world runs the column either way, so declining
  freezes a permanent default-vs-driver mismatch — the documented guardrail-4 corollary hazard — for the sake
  of one site that cannot score the metric in question.
* **Hand `energy.jl` to line M for one commit (option 2).** Unnecessary: the change is four lines of default
  plus E's own gates, and the pass condition needed E's harness to evaluate anyway.
* **Flip and simultaneously make `z1` surface-dependent** (ADR 0074 §4's open item). Rejected as scope: it
  needs `SToE`'s `lai`/`height` in a form E has not measured, and it would confound this decision with a new
  one.
* **Re-fit `z1` to recover the sub-daily `T_skin` skill.** Rejected: 0.2 m is under-resolved at the daily
  step (ADR 0074 §3), so this trades the operational metric for a non-operational one, and `z1` was selected
  on a resolution criterion precisely to avoid becoming a fitted knob.

## Provenance

* Report: `<energy_reference>/derived/seb_validation/e7_two_layer_probe_v6.txt` (job `E-e7v6` 1717191),
  which supersedes `_v5.txt` for every sub-daily thickness comparison. Probe:
  `scripts/e_two_layer_probe.jl`; shared harness `scripts/e_seb_drive_common.jl`.
* Coupled-side evidence: ADR 0058 §2/§3 (`scripts/two_layer_coupled_probe.jl`, jobs 1716625/1716628).
* Gates: `test/testitems/energy_closure_tests.jl` — the ADR 0075 opt-in/opt-out item and the new night-cold
  sign item.
