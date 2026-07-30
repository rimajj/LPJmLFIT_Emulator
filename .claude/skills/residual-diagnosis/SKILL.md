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

## 2c. If the quantity is a RESIDUAL, decompose it algebraically BEFORE sweeping anything

When the thing you are diagnosing is defined as a residual — Component E's `H = Rn − LE − G`, a carbon
closure term, any "everything else" bucket — its error is **algebraically constrained**, and writing that
constraint down costs nothing and settles the attribution outright. For E (ADR 0073):

    H_m = Rn_m − LE − G_m   (exact)   ⇒   ΔH = ΔRn − ΔG + ε_obs,   ε_obs ≡ Rn_o − LE − H_o − G_o

Every W/m² of the error had to be one of three terms, **and `g_a` was in none of them** — so no `g_a`
sweep could ever have identified the cause, even though sweeping it visibly moved the metric.

- **A monotone sweep on a residual is usually BIAS CANCELLATION, not evidence.** ADR 0072 read a
  `stab_amp` sweep that improved monotonically to its bound as "the stability form is the limitation".
  It wasn't: the parameter shifted the solved state in whichever direction offset a *different* term's
  error. Measured afterwards, the modelled conductance was within **0.7 %** of the tower's measured value.
- **Include the REFERENCE's own inconsistency as a named term.** `ε_obs` (the tower's failure to close)
  was −62 W/m² at one site — larger than the entire "model error" being chased there. A model that closes
  exactly *cannot* match a reference that doesn't, so that part is unclosable by construction and the site
  simply cannot score that quantity. Don't let it dilute a mean; say which sites can constrain the thing.
- **Perturb parameters through the REAL solver, never a re-implementation.** Find an existing input the
  target is exactly proportional to (for `g_a` under `enable_stability=false`, that is `wind`) and scale
  that. A diagnostic re-implementation introduces exactly the basis mismatch §1 is about.
- **Compare levers over each parameter's OBSERVATIONALLY-IMPLIED range, not over equal multiples.** A 100×
  bracket on a parameter known to ±20 % proves nothing; the honest ranking used ±(0.8–1.7)× for the
  measured conductance against 1.0-vs-7.0 for the unconstrained one.
- **Check the model's NATIVE STEP before calling a sub-daily miss a bug.** The coupled driver called the
  closure once per DAY, so the half-hourly diagnosis was of a regime the model never runs in — and the
  defect turned out to be a *timescale* mismatch in a coefficient, visible only once the comparison was
  redone at the native step.

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
same artifact with the generator **as of a git ref** (`git show REF:path/to/builder`, then run that copy) and
diff it against your working tree's output field-by-field. This works even when your edit moved which module a
constant comes from. Interpretation: identical ⇒ your edit is a no-op and the fixture is stale (fix that
separately, as its own deliberate change); different ⇒ that diff *is* your answer, and it names the moved field.

Two traps in running the extracted copy, both of which bit on the first attempt:
- **Extract it into a MIRRORED repo root, not a flat temp dir.** These scripts resolve their own root as
  `Path(__file__).resolve().parents[1]` and import from it (e.g. the one shared `TREE_TYPES`), so from
  `/p/tmp/x/foo.py` that root becomes `/p/tmp` and the import dies with `ModuleNotFoundError`. Write it to
  `<work>/ctlrepo_<sha>/scripts/` with `python/` and `src/` symlinked back to the real repo (and set
  `PYTHONPATH` too). A generator that hard-codes its constants hides this — which is why it passed once and
  then broke as soon as the constant became an import.
- **A control that FAILS TO RUN is INCONCLUSIVE, never a FAIL.** Give it a distinct exit code. Reporting a
  build error as "your edit moved the table" is the loudest possible wrong conclusion from a gate whose whole
  job is telling those two apart.

The measurement is cheap and it converts an ambiguous red gate into a specific finding. In the case that taught
this, the moved fields (`soilmoist` 0.7→0.86, `lai` 21.2→2.77, everything else bit-identical) named the cause —
a retired proxy→real feature migration — and the control proved the edit under test was innocent
(max|abs diff| = 0 on all 15 columns). Reference implementations:
`scripts/diagnose_slow_table_drift.py` (the control) + `scripts/verify_hainich_demo_artifacts.sh` (a gate with
a three-way `PASS` / `FAIL` / `STALE-FIXTURE` verdict); ADR 0032 for the write-up.

**Generalization worth remembering:** a golden fixture is only a gate on *change* if it is itself current. Two
fixtures that a single consumer loads together (there: a count `.drf` + a recruit `.rcop` sharing four
conditioning columns) must be regenerated together, or they silently drift onto different bases.

## 3d. A biased basis can make you rebuild the wrong THING, not just misread a number (2026-07-28)

§3b says a basis cross-check below ~0.99 is a STOP. Here is what it costs when you treat it as a footnote —
because the failure is not "the number was off", it is **"we concluded the model class was wrong."**

Component S scored per-cell trait medians on a silently truncated stem population (2 of 7 tree PFTs dropped).
On that basis the emulator reproduced only **0.55** of the true between-cell spread on its worst axis, which was
diagnosed as *missing composition signal → we need a per-PFT/mixture model* — a structural rewrite, promoted to
leading hypothesis in an ADR. Fixing the population instead moved that axis from `emu_r` 0.567 → **0.807** and
dispersion 0.546 → **0.718**, and took another axis to near-ceiling, **with no structural change at all**. The
rewrite was never needed.

The mechanism is worth internalising, because it is not "less data": **the exclusion was correlated with
predictability.** The dropped PFTs were the two whose composition is *most* determined by environment (a
climatically distinctive tropical belt; an extreme-continental larch zone). What survived was the sub-population
where the conditioning genuinely has least to say. A biased basis does not just add noise — it can select for
exactly the regime where your model looks worst, and then that looks like evidence about the model.

So, before proposing a structural change to fix a residual:
- **Ask what population the metric was computed on, and whether the exclusion could correlate with the thing
  being predicted.** "Fewer cells / fewer samples" is benign; "the excluded cells are the easy ones" is not.
- **Prefer fixing the basis over adding model capacity.** Basis fixes are cheap, reversible and falsifiable;
  a mixture model is none of those. Reach for capacity only after the basis is known clean.
- **When the population changes, re-run the scoring gate AND re-baseline every open milestone gate in the same
  pass.** A population change moves the floor, the ceiling and the metric's normalizer at once, so a gate written
  against the old basis silently changes difficulty — and the next milestone will take credit for the basis fix
  (here the population fix alone delivered 30 % of a follow-on milestone's target).
- **Say which prior conclusions the fix withdraws.** Two published claims died with this basis; naming them is
  what stops them being re-cited. (ADR 0033 is the write-up; ADR 0030 §4 is the scoring method that survived.)

## 3e. Before trusting a green gate, ask whether that assertion CAN fail (2026-07-28)

A gate on a model's **output** cannot test its **input** basis when the output is bounded by construction. The
case: "the emulator's predicted counts are inside its training band" guarded runtime-consistency for months and
was green throughout a two-orders-of-magnitude conditioning shift — because a random-forest prediction is a
*convex combination of training leaf means*, so it can never leave `[min y, max y]` whatever it is fed. The
assertion was not weak, it was **incapable of failing**. It was an artifact-integrity check wearing a
consistency check's name.

So when a residual survives behind a green gate:
- **Work out the assertion's reachable range before believing it.** If no input can violate it, it is not
  evidence. Bounded-by-construction outputs (forest/ensemble means, softmax, anything clamped, anything
  normalized) are the usual offenders; so is a tolerance far looser than the quantity's own spread.
- **Move the check to the input side, and make the reference explicit.** Record what the model was actually
  fed (a per-year feature history costs nothing) and ship the trained **per-feature band** inside the artifact
  itself, so train-vs-inference is comparable at every call site without re-deriving the training table.
- **PIN the known-bad set rather than asserting perfection or writing prose.** Asserting "zero violations" when
  three are known reds the suite and pressures you into a rushed fix or a silent widening; documenting them in
  an ADR alone is exactly how the last one came back. Assert the *exact* set, with a margin cut that keeps a
  marginal column from flapping across CPU microarchitectures, and tighten it as each cause closes.
- **A band is a measurement, not a tunable.** "Widen the band so the runtime fits" destroys the only signal
  that can catch the next shift. Bring the runtime to the reference, or change the reference deliberately with
  its own decision record.
- **When one fix exposes several causes, route them by owner and finish the milestone.** Here the surviving
  shift split into a temporal-aggregation choice, a spatial-aggregation choice, and a *different component's*
  physics gap — bundling them into the current milestone would have re-created the entanglement the milestone
  was carved out to avoid. (ADR 0034 is the write-up; ADR 0032 is the defect it closes.)

## 3f. Same NAME ≠ same QUANTITY — check that before you argue about aggregation (2026-07-28, ADR 0035)

Two sides of a comparison can carry the same column name, plausible units, and **overlapping numeric
ranges** and still be different physical variables. When they are, every aggregation story (annual mean vs
instant, cell mean vs patch, weighted vs unweighted) will *sound* like it explains the gap — and "fixing"
the aggregation turns the alarm green over a mismatch, which is strictly worse than the documented residual
it replaces, because you have now spent the alarm.

This is not hypothetical: a Component-S conditioning feature was diagnosed and routed as a temporal
aggregation mismatch, and the training column was actually the C's `swc` (**total** water over
**saturation** capacity) against a runtime `w` (**plant-available** water over **WHC**). Hainich values
0.84–0.87 vs 0.79–1.00 — close enough to look like the same thing sampled differently.

The check, before choosing between bases:

1. **Open the source on BOTH sides and read the expression, not the name.** For a C output that means the
   accumulation line (`getoutput(...,X,config) += …`), not the `outputvars.js` `descr`.
2. **Ask what normalises it** — fraction *of what*? Summed *over which* index set? Two fractions on
   different denominators are different variables even when both live in [0,1].
3. **Ask whether it is invertible to the one you want.** If recovering it needs quantities the model never
   emits, no reduction of it will ever work; go find the output that carries your variable directly.
4. Only once both sides are the SAME quantity does the aggregation question become well-posed.

Corollary, same milestone: **"quantity X is not reconstructable from the output" is a claim to RE-DERIVE,
not to inherit.** A skill and a builder docstring both asserted a per-patch stand LAI was unrecoverable
from a 29-column table; two of the emitted columns carried it exactly. When you do reconstruct something,
validate it against an **independent** expression in the source (crown area from `fpc_ind` vs from the
height allometry), never against a quantity that differs from it for a *second* reason — and set the
tolerance at the data's own precision floor (a `%g` text writer gives six significant digits, so an
inversion cannot beat ~1e-5; a genuinely wrong constant shows as a percent-level bias in the MEDIAN).

## 3g. Run the probe on EVERY cell you have, not the one with a committed reference (2026-07-30, ADR 0051)

§3f says read the expression on both sides. Do that, and the mechanism is usually obvious *before* any
probe. The trap that remains is **attributing** it: a definitional gap normally has several independent
terms, and which one dominates is **climate-dependent** — so a single-cell probe will confidently name the
wrong one.

Concretely (`water_stress`, ADR 0051): the C's `wscal` differed from F_diff's in three ways at once —
a missing `phen` in the numerator, a leaf-on vs actual conductance in the denominator, and `wscal = 1`
instead of `0` on a no-demand day. The stated hypothesis was that the third dominated, predicting a
leaf-off day fraction ≈ the observed annual stress. At **Hainich** that is flatly wrong: it has *zero*
zero-GPP days (evergreen PFTs assimilate year-round), so the branch never fires there and the shift is
entirely the other two terms. The predicted mechanism *is* dominant at the **boreal** cell (31.3 % of days
score exactly 0 vs exactly 1). Both are real; one cell would have published one of them as "the" cause.

- **Five cells cost nothing extra** once the driver is written — the same loop over a registry. Do it by
  default for anything the coupled loop feeds, and report the per-cell table, not a single number.
- **Derive the reference for every cell too, don't lean on the one committed band.** The "6.6× band width"
  framing existed only because Hainich happened to have a committed artifact meta. Deriving the C column
  per cell/year (exactly as the training table forms it) + the **seed1-vs-seed2 noise floor** is what
  turned a one-cell claim into a five-cell result — and it is what exposed the cell the fix does *not*
  close (boreal: error 0.35 → 0.31, i.e. it changed **sign** rather than shrinking).
- **Report the cell the fix fails on, with a tagged `[ASSUMPTION]` mechanism and a falsifiable test —
  never a second same-milestone fix.** Naming "F_diff has no soil ice, and the C's `wr` is over
  plant-available water" plus "compare F_diff's root-zone `w` to the C's `rootmoist` at cell 52059" is a
  finding. Guessing a second fix to make all five cells green is how one milestone silently becomes three.
- **A "conditioning shift" and "out-of-band extrapolation" are different failures, and a GLOBAL band cannot
  distinguish them.** The shifted values sat *inside* the global pooled band and only violated the
  single-cell one — i.e. the model was evaluated at a perfectly valid point belonging to a *much drier
  cell*. Score a per-cell feature against **that cell's own** reference (cf. §3e).
- **Quantify the downstream consequence, or "the conditioning is wrong" stays arguable.** Carrying the A/B
  through to end-of-run tree N gave **−36.4 %** in the semi-arid cell vs ≤1.7 % elsewhere — which is what
  actually justified blocking the milestone, and it landed in the cell with the largest shift.

**And: a probe cannot replace a unit assertion on a branch.** The first implementation wired the
no-demand gate to the wrong accumulator, so that branch never fired — and **every coupled number was
byte-identical** either way, because a downstream cap already produced the same value on exactly those
days. Only an exact-boundary unit test (`phen ≡ 0` ⇒ must be exactly 1.0) caught it. When you port a
guarded C expression, assert **each guard at its exact boundary**, not just the aggregate it feeds.

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
