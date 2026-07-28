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

## 2b. For a SMALL effect, prove it's REAL (not run-to-run noise) BEFORE hunting a mechanism

A small metric delta (e.g. a KS/nqrmse difference of ~0.01–0.02, or an ablation A-vs-B gap) can be a real
signal OR just stochastic wobble (forest subsample seed, RNG draw, fold assignment). **Establish which first
— re-run with a perturbed seed** (`SEED_OFFSET`-style) and check whether the sign/ordering is STABLE. If it
flips → it's noise; stop theorizing. If it reproduces → it's real; now the mechanism hunt is warranted. This
cuts both ways: don't dismiss a small effect as noise without the check either. (ADR 0027 SLA/minwscal: my
"it's noise" guess was refuted by a seed+100 re-run — the per-axis pattern was seed-stable, i.e. real; and I
then also refuted the two obvious mechanisms — boundary-importance and space-for-time — and honestly reported
"real but mechanism not cleanly identified" rather than inventing one. Reporting an unconfirmed mechanism is
worse than reporting a characterized-but-unexplained effect.)

## 3. Confirm the comparison basis is correct — one cheap check first

Before the expensive probe: reproduce a *known* number (e.g. the C run's own reported annual total, or a
byte-identical baseline) through your comparison harness. If your harness can't reproduce a number you
already trust, fix the harness before interpreting any residual.

## 3b. A basis cross-check below ~0.99 is a STOP signal, not a footnote (learned the hard way, 2026-07-28)

If you compute the *same* quantity two ways and they disagree, you are comparing two **populations**, not
observing "instability" in one. Do not write a caveat and read the residual "qualitatively" — that ships a
wrong number with an explanation attached. What went wrong in ADR 0030/0031: a published gate carried
`seed1-basis` cross-checks of 0.973 / 0.488 / 0.761 / 0.092 with a committed docstring blaming per-cell-median
instability; the real cause was a stem filter (`Type<=6` vs `TREE_TYPES=[1,2,3,4,5]`) selecting two different
PFT sets, and the "weak" axis' floor was inflated ~3×.
- **The ordering across axes/variables names the mechanism.** Cross-checks that rank SLA ≫ D95max > Wooddens ≫
  minwscal ranked exactly by how disjoint each trait's per-PFT sampling interval is. If one variable's
  cross-check collapses while another's is ~1, ask what *subset* differs, not what is noisy.
- **Cheapest decisive probe:** recompute the statistic on BOTH candidate populations over the rows they share
  and correlate the two versions. If that reproduces the bad cross-check, the population is the bug — done, no
  further probing. (`scripts/diagnose_ind_type_composition.py` is that probe for `ind`-table populations.)
- **Then ask which population is RIGHT** — not just which one matches. Matching the model's own basis makes a
  gap *measurable*; it does not make the basis *correct*. Check the authoritative source (here: the active
  `par/` file + the C writer), because "make the floor match the model" can quietly codify the model's bug.
- **A ceiling from two stochastic realizations is not a predictor ceiling.** With `m = μ(env) + δ(RNG)`,
  `r(seed1,seed2) = var(μ)/(var(μ)+var(δ))`, so a predictor of `μ` scores up to `√` that. Use each side's
  split-half (Spearman-Brown) reliability for the honest ceiling, and always report a **dispersion ratio**
  (`sd(pred)/sd(truth)`) alongside the correlation — a correlation is scale-blind and hides a model that
  regresses everything toward the mean.

## 3c. A regenerated fixture that MOVED: run the CONTROL before blaming your edit (2026-07-28)

When a "regenerate it and it must come back byte-identical" gate fails, you have **two** candidate causes and a
one-tier gate cannot tell them apart:

  (a) your edit changed the computation, or
  (b) **the committed fixture was already stale** — regenerating it from *unchanged* code would move it too.

Do NOT widen the gate, and do NOT write it off as "run-to-run jitter" (§2b). Run the **control**: rebuild the
same artifact with the generator **as of a git ref** (`git show REF:path/to/builder > /tmp/...`, then run that
copy) and diff it against your working tree's output field-by-field. A generator that hard-codes its own
constants is self-contained, so this works even when your edit moved which module a constant comes from.
Interpretation: identical ⇒ your edit is a no-op and the fixture is stale (fix that separately, as its own
deliberate change); different ⇒ that diff *is* your answer, and it names the moved field for you.

The measurement is cheap and it converts an ambiguous red gate into a specific finding. In the case that taught
this, the moved fields (`soilmoist` 0.7→0.86, `lai` 21.2→2.77, everything else bit-identical) named the cause —
a retired proxy→real feature migration — and the control proved the edit under test was innocent
(max|abs diff| = 0 on all 15 columns). Reference implementations:
`scripts/diagnose_slow_table_drift.py` (the control) + `scripts/verify_hainich_demo_artifacts.sh` (a gate with
a three-way `PASS` / `FAIL` / `STALE-FIXTURE` verdict); ADR 0032 for the write-up.

**Generalization worth remembering:** a golden fixture is only a gate on *change* if it is itself current. Two
fixtures that a single consumer loads together (there: a count `.drf` + a recruit `.rcop` sharing four
conditioning columns) must be regenerated together, or they silently drift onto different bases.

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
