# ADR 0048 — the k-cap merge is dormant, not harmless; the constant-forcing baseline drift is the real confound

* **Status:** Accepted
* **Date:** 2026-08-04
* **Line:** S (Component-S science) · ADR block 0030–0049
* **Decides:** the two pre-flight questions that gate Phase 3A **Stage 2** (wiring the ported hazard of
  ADR 0047 into `slow.jl`). Verdicts: **(1)** `_merge_pair!`'s trait-non-conservation does NOT have to be
  fixed first — it never fires at the default `k_cap` — but it is a **latent** defect of 3.1–5.1× the signal
  and must be re-checked before any config tightens the cap or scales the roster; **(2)** every Stage-2
  response measurement MUST be differenced against a **matched constant-forcing control run in the same
  generation**, because the rollout's own relaxation transient is **1.34× the FIT warming shift, in the
  opposite direction, settling in ~52 years**.
* **Related:** ADR 0046 §4 (the emulator has zero channel for the shift; the merge and the recruit append
  are the only two operators that move the community trait mean), ADR 0047 (the ported hazard), ADR 0044
  (placement, not shrinkage; the frozen thresholds), ADR 0024 (the append/merge roster design)
* **Evidence:** `scripts/kcap_merge_confound_probe.jl`, job `1694397` (exit 0); the two earlier attempts
  `1694111` (script error) and `1694359`/`1694373` (the same numbers, before the reporting fix) agree.

## Context

ADR 0046 §4 identified exactly two operators that can move Component S's community wood-density mean: the
appended copula recruits, and the k-cap merge. `_merge_pair!` (`slow.jl:441-445`) conserves carbon by
`nind` weight but **inherits the dominant parent's `sla`/`wooddens` outright** — a trait-non-conservative
operator sitting directly in the path of the planned fix. If it moves the community mean by anything
comparable to the +2432.9 (median) / +3808.0 (mean) shift the hazard must explain, then every before/after
measurement of the hazard is confounded by the roster bound, and the merge has to be fixed first.

Measuring it needs no new physics, so the handoff put it before the runtime change.

## Decision — what was measured

Basis: the committed Hainich (cell 42490) coupled harness, byte-for-byte
`measure_hainich_gate_bands_probe.jl`'s construction (same fixtures, modal patch, forcing, seed 1),
advanced **one year at a time** for 150 years so the community state is read at every year boundary.
Arms: {copula OFF, copula ON} × {`k_cap` = default (= `max(2K, 40)` = 40), `k_cap` = 20 (TIGHT),
`k_cap` = `typemax(Int)` (merge DISABLED)}. Initial roster K = 17; initial community `wooddens` = 235 469.6.

### 1. At the default `k_cap` the merge NEVER FIRES — so the obvious measurement is a non-measurement

**0 merges in 150 years, in both copula arms.** The default-vs-disabled Δ(community wooddens) is therefore
**exactly 0.0 in every year**, which says nothing whatever about the operator: it says the operator never
ran. Mechanism: `k_cap = max(2·K_initial, 40)` needs the roster to double, the roster grows by at most ONE
cohort per establishment year, and **establishment fires in only 12–14 of 149 years** (`ρ > 1`). The roster
goes 17 → 29 (copula OFF) / 31 (copula ON) and then stops.

This is the trap the probe is written against. A default-arm null here reads exactly like "the merge is
harmless" and is not that.

### 2. When forced to fire, the merge distorts the community trait mean by 3.1–5.1× the signal

With `k_cap` = 20 — just above the initial roster, so the merge is forced — against the merge-disabled
reference:

| arm | merges / 150 yr | Δwd @ yr 20 | @ yr 50 | @ yr 150 | worst \|Δwd\| | as a share of the FIT shift |
|---|---|---|---|---|---|---|
| copula OFF | 20 | +3 568 | +8 678 | +12 375 | **12 375** (yr 146) | **5.09×** |
| copula ON (production) | 21 | +4 222 | +3 769 | +6 888 | **7 627** (yr 136) | **3.13×** |

The first merge (yr 8) moves the mean by **0.0** with the copula off and **+8.2** with it on — because with
no copula every recruit shares `sapl.wooddens`, so merging two recruit cohorts is trait-exact. That is the
operator's benign case, and it is not the production case.

**So `_merge_pair!` is trait-destructive at a magnitude that would swamp the signal — it simply is not
reached in the current configuration.** Recording it as "not a confound" without the second arm would have
been the wrong sentence.

Note the Σnind difference between the TIGHT and reference arms (+6.0 % by yr 150) is **not** a conservation
violation: `_merge_pair!` conserves Σnind within the call (gated by `slow_membership_tests.jl`), but the
merged roster changes the stand aggregates the DRF is conditioned on (`lai`/`fpc`/`age_mean`/`n_living`),
so the count target diverges from the next year on. Carbon still closes at ~1.3e-11 in every arm.

### 3. The real confound is the CONSTANT-FORCING baseline drift, and it is larger than the signal

The merge-disabled reference is a rollout under the **same year's forcing repeated 150 times** — no climate
signal of any kind. Its community wood density nonetheless moves:

| arm | drift yr 1 → 150 | as a share of the FIT shift | settles at | direction vs FIT's warming shift |
|---|---|---|---|---|
| copula OFF | **+9 273** | 3.81× | yr 57 | same |
| copula ON (production) | **−3 267** | **1.34×** | **yr 52** | **OPPOSITE** |

The production configuration's community wood density relaxes from its C-derived initial state to an
internal fixed point, moving **1.34× the FIT warming shift** and in the **wrong direction**, and it takes
**~52 years** to settle — squarely inside the 80-year historic→ssp370 window a transient response is
measured over. After the fixed point the trajectory is frozen (yr 100 and yr 150 agree to the printed
digit).

This is a spin-up/relaxation transient, not an unbounded drift — but on the timescale and at the amplitude
of the signal, which is what makes it decision-relevant.

### 4. The recruitment-dilution timescale, for the record

From `s.target_history`: the emulator's per-year recruit fraction `e = max(ρ−1, 0)` averages **0.0106**
over the years establishment fires and **0.0010** over all years, giving

```
τ = −1/ln(1−e)  =  94 yr  (firing-year e)   /   1 003 yr  (run-mean e)
```

Only ~14 % of the population is replaced by recruits in 150 years. So recruitment is a **slow** channel:
it can carry a trait response, but it cannot carry a fast one, which is consistent with the ~52-year
observed relaxation and with ADR 0044's finding that the deficiency is placement rather than amplitude.

## Consequences

* **Stage 2 is unblocked without a merge fix.** The merge is dormant at the default `k_cap`, so a Stage-2
  before/after measurement on the Hainich harness is not confounded by it.
* **A standing check, not a closed question.** Any change that tightens `k_cap`, raises establishment, or
  scales the roster (a denser global cell) can wake the operator. The probe is the check; re-run it before
  concluding anything about a trait trajectory in a new configuration. Fixing `_merge_pair!` to conserve
  traits by `nind` weight — as it already conserves carbon — remains the correct eventual repair and needs
  its own ADR when a configuration reaches the cap.
* **Every Stage-2 response arm needs a matched constant-forcing control, re-run in the same generation.**
  Handoff item F already required matched baselines; this quantifies why: the uncontrolled baseline motion
  is 1.34× the signal and opposes it, so an uncontrolled arm could show the *right* sign for entirely the
  wrong reason, or hide a real improvement.
* **The measurement window matters.** A response measured over fewer than ~52 rollout years is dominated by
  the relaxation transient. Either spin the rollout past its fixed point first, or difference against the
  control at matched year indices.
* **`τ ≈ 94 yr` is an upper bound on how fast any recruit-mediated fix can act.** A mechanism that only
  changes the *entry* marginal (the deprioritised inheritance operator, ADR 0045) is limited by this
  timescale regardless of how correct it is — an independent second reason to prefer the mortality lever,
  which acts on the standing population every year.

## Alternatives rejected

* **Reporting the default-arm Δ = 0 as "the merge is not a confound".** The literal handoff instruction was
  to run default vs `typemax(Int)` and check whether it moves. It does not move — because it never runs.
  Publishing that null would have retired a live defect on a vacuous measurement. The TIGHT arm is what
  makes the verdict mean anything.
* **Fixing `_merge_pair!` now anyway, since it is measurably wrong.** Tempting at 5.1×, but it is
  unreachable in every current configuration, so the fix would change no result while adding a second
  moving part to a stage whose whole discipline is one change at a time (handoff item F). Deferred with an
  explicit trigger.
* **Treating the constant-forcing drift as a bug to fix before Stage 2.** It is a relaxation from a
  C-derived initial state toward the emulator's own fixed point; whether that fixed point is right is the
  *level* question (ADR 0030/0033), not the *response* question, and conflating them is what ADR 0033 had
  to correct once already. Controlled for, not fixed.
