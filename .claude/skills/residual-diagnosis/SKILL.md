---
name: residual-diagnosis
description: The mandatory discipline BEFORE chasing any fidelity residual (an F_diff-vs-C gap, an S-panel miss, an energy/closure discrepancy) — state the reference basis and a falsifiable hypothesis, confirm the comparison basis is correct, and time-box before writing probe scripts. Use it at the start of any "why doesn't X match Y?" investigation.
---

# residual-diagnosis — don't chase a residual blind

This exists because the grass-overshoot investigation ran ~10 sessions (17–26) of "RE-DIAGNOSIS #1/#2/#3",
"REFUTED", "RULED OUT" — and ended in *"it was a reference-basis artifact"*: the gap came from comparing
against the wrong reference. The ~20 `scripts/grass_*` probes are the fingerprint of skipping this step.

**Do all four BEFORE writing a probe script.** Write them down (JOURNAL or a scratch note) so they can be
checked later.

## 1. State the reference basis — exactly what am I comparing against?

- Which C run / which output file / which cell / which years / which seed?
- Is the reference the **right object**? (per-PFT vs stand-aggregate; daily vs annual; per-individual vs
  per-m²; leaf-on vs all-year; `swc` fractional vs absolute mm.) Most "residuals" here were basis
  mismatches, not physics gaps.
- Does the reference path actually run in the **`individual=true`, carbon-only** config? (Grep the C
  guards — see `lpjmlfit-cbinary` / the individual-mode gotcha. Porting a dead C path is the classic
  session-16/17/19 waste.)

## 2. State a falsifiable hypothesis

"The gap is caused by X" where X predicts a **specific, measurable** consequence that a single cheap check
can confirm or kill. "Something is off in grass" is not a hypothesis. "The gap is the below-ground
sapwood respiration term missing from Ra, which should shift CUE by ~2%" is.

## 3. Confirm the comparison basis is correct — one cheap check first

Before the expensive probe: reproduce a *known* number (e.g. the C run's own reported annual total, or a
byte-identical baseline) through your comparison harness. If your harness can't reproduce a number you
already trust, fix the harness before interpreting any residual.

## 4. Time-box and set an escalation trigger

Decide up front: "N hours / M probes; if the hypothesis isn't confirmed by then, escalate to the owner
rather than opening RE-DIAGNOSIS #k." Escalate with the reference basis, the hypothesis, and what killed
it — not with another probe.

## Naming

Diagnostic scripts must be `*_probe.jl` / `*_diagnosis.jl` / `*_decomp.jl` — **never** `*_test(s).jl`
(ReTestItems scans the whole repo and fails collection on a non-`@testitem` file with that name).

## Output

A diagnosis is done when you can state: the reference basis, the hypothesis, the check that confirmed or
killed it, and whether the residual is (a) a real physics gap to fix opt-in, (b) a reference-basis
artifact (no code change), or (c) an accepted limitation to document. State which — don't leave it open.
