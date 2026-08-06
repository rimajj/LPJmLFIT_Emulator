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

## Two traps that make a residual look explained when it isn't (added 2026-08-04, ADR 0044/0046)

**1. GATE A NEW STATISTICAL INSTRUMENT ON THE PUBLISHED NUMBERS BEFORE INTERPRETING IT.** If you build or
extend a metric harness, make it re-derive every already-logged value it is meant to explain, from the stored
artifacts, and **hard-exit on a mismatch** — otherwise the noise scale you measure attaches to a different
statistic than the verdict quotes. This caught nothing the first time only because it passed: the paired
response bootstrap reproduced all seven ADR-0042 arms to <=5e-5 on 52 450 cells, which is what licenses every
threshold derived from it. A harness that cannot reproduce the number it is auditing is the bug; fix it first.

**2. A "PLACEMENT" RESIDUAL LOOKS EXACTLY LIKE A "SHRINKAGE" RESIDUAL IN THE MEAN — separate them before
choosing a lever.** If a model damps the MEAN of a signed quantity, the reflex is attenuation/shrinkage, and
the reflex fix is more conditioning capacity or more covariates. But shrinkage damps mean **and** dispersion
together. Check the dispersion ratio: Component S damps the mean wood-density warming shift by 39.9 % while
its dispersion ratio is **1.034** — right-sized shifts in the wrong cells, which cancel in the mean. Every
lever aimed at attenuation (including a formal acceptance criterion, ADR 0030 C2) was therefore aimed at a
defect the emulator does not have. Cheap discriminators, all tables rather than jobs: the dispersion ratio,
a binned calibration curve of predicted-vs-observed change (shrinkage = straight line slope<1 through the
origin; offset = slope~1 intercept<0; placement = near-flat with correct spread), and decomposing the TRUTH's
own signal into the channels the model can and cannot represent.

**Corollary — a global support check can say "in domain" while the model extrapolates locally.** Only 1.02 %
of ssp370 rows exceed the *global* historic `gdd5` band, and 0.000 % exceed it on the flux drivers, so a
grid-wide band test reports "in domain". For a spatially-conditioned emulator the support that matters is the
**neighbourhood's**, not the grid's — measure the fraction of a cell's rows outside *that cell's own* (or its
k nearest training neighbours') historic range.

## Two more traps, from measuring an operator instead of a residual (added 2026-08-04, ADR 0048)

**3. BEFORE BELIEVING A NULL, PROVE THE THING YOU WERE TESTING ACTUALLY RAN.** A no-difference result and a
never-executed operator produce the *same* output — a column of zeros — and the first reads as "harmless".
Line S was told to check whether the k-cap cohort merge distorts community wood density by comparing
`k_cap = default` against `k_cap = typemax(Int)`. Δ was **exactly 0.0 in every year of a 150-yr rollout, in
both arms**, because the default `k_cap = max(2·K_initial, 40)` needs the roster to double and establishment
fired in only 12 of 149 years — **0 merges, ever**. Forced to fire at `k_cap = 20`, the same operator moved
the community mean by **3.1–5.1× the signal it was being cleared against**. Publishing the first number would
have retired a live defect on a vacuous measurement.

So: instrument the ACTIVATION COUNT, not just the effect, and make a zero count print as a warning next to
the Δ (`"⚠ NO MERGE EVER FIRED — this Δ bounds nothing"`). Then add an arm that forces activation, and report
*that* as the bound. This is the same family as §3e ("ask whether that assertion CAN fail") — a null from an
inactive code path is an un-failable test wearing a number.

**4. A ROLLOUT DRIFTS UNDER CONSTANT FORCING — measure that BEFORE attributing any drift to the signal.**
Run the rollout with the forcing year repeated, no signal of any kind, and see how far the quantity of
interest moves. Component S's community wood density drifts **1.34× the FIT warming shift, in the OPPOSITE
direction, settling at year 52** — a relaxation from the C-derived initial state to the emulator's own fixed
point, larger than the signal and on the same timescale as the 80-yr scenario window. Consequences that
generalize to any recursive emulator arm:

- **Difference every arm against a matched constant-forcing control, re-run in the SAME generation** (never
  inherited from a log — the standing no-bundling rule, now with a magnitude attached to why). An
  uncontrolled arm can show the right sign for entirely the wrong reason, or hide a real improvement.
- **Score past the transient.** Find the settling year (first year within a tolerance of the final value) and
  measure beyond it, or difference at matched year indices.
- **Get the replacement timescale for free** while you are there: from the per-year recruit fraction `e`,
  `τ = −1/ln(1−e)`. Component S: `e` = 0.0106 in firing years / 0.0010 run-mean ⇒ **τ = 94 / 1 003 yr**, only
  ~14 % of the population replaced in 150 yr. That is a hard upper bound on how fast any fix acting only
  through NEW members can move the answer — worth computing before choosing between an entry-side and a
  standing-population-side mechanism.

Harness: `scripts/kcap_merge_confound_probe.jl` (Hainich, one year per `run_coupled_cell` call so the
community state is readable at every year boundary; carries the activation counter, the forced arm, the
constant-forcing control and the settling year). Reuse its `rollout(...)` shape rather than writing a third
harness.

## Two more, from a number that did not survive replication (added 2026-08-05, ADR 0101)

**5. IF THE QUANTITY IS A DIFFERENCE OF STOCHASTIC ROLLOUTS, REPLICATE IT BEFORE YOU WRITE IT DOWN.** §4
above says difference every arm against a matched control. That is necessary and **not sufficient**: a
controlled difference of *small-sample stochastic* rollouts can have a sampling spread the size of the effect,
and every within-run precaution (window means, matched year indices, matched forcing) is blind to it. Line S
measured a 2×2 double difference at one cell as `+1.40× FIT`, published it, and on replication over the
emulator's own recruit seed found **sd = 0.67–1.74× FIT** — so the number was one draw, its 95 % CI straddled
zero, and on two other artifacts the effect was **indistinguishable from zero**. The original was not a *bug*
(it sat 0.03 from its configuration's ensemble mean) and reproduced to the digit; it was a *fair draw reported
as a measurement*.

- **Find the nuisance parameters and count them.** Anything the science claim does not depend on but the
  number does: an RNG seed, a per-cell initial condition, which trained artifact carries a learned channel, a
  scoring window. Vary each *separately*, holding the rest fixed. Here the seed gave ±1.0× FIT, the initial
  condition 4.5× FIT, the artifact 3.1× FIT — all larger than the ~1× being claimed.
- **A shared seed across arms does NOT pair them** if the arms' internal state diverges (rosters, cohort
  lists, anything appended). Measured: `sd(Δ_treatment)` ≡ `sd(interaction)`, i.e. zero cancellation. Do not
  assume a common-seed design buys variance reduction — check it.
- **Report mean ± SEM with `n` and a CI, and state what the CI EXCLUDES** — that is usually the informative
  half ("both CIs exclude the previously published +1.40×").
- **Compute the replication cost and let it choose the instrument.** `n ≈ 7.84·(σ/δ)²` at 80 % power: ~8
  replicates for a 1σ effect, **~115** for the 0.26σ actually seen ⇒ the single-cell harness is a *mechanism*
  check and the global gate is the only thing that can carry the claim.
- **Watch which claim replication strengthens.** Here the *level* effect went to `t` = 10–24 while the
  *response* effect vanished. That asymmetry is evidence about which one was real, and it is free.

**6. A CORRECT MEASUREMENT CAN CARRY A WRONG CAUSAL READING — test the candidate levers separately.** The
same work had a clean diagnostic (a trained-band excursion: the driver ran 0.658 band widths out of band,
16× worse in the warmed arm than the control arm) and drew the wrong conclusion from it: *"the artifact was
trained on one scenario ⇒ retrain on both."* Measured, retraining across scenarios moved the answer by
`t = −1.03` (nothing), while widening the band the *other* way — pooling across **cells** — moved it by
`t = +4.28`. The band widened 4.79× from cell pooling and **−0.04 %** from scenario pooling.

- **A localisation is not an attribution.** "Channel X is out of band" identifies *where*; it says nothing
  about *which axis of the training design* put it there. An asymmetry along one axis (worse under warming)
  does not make that axis the fix — anything that widens the band fixes it.
- **Build the ladder that holds one factor fixed at a time** before acting on the plausible story. Two extra
  ensembles cost ~30 min here and inverted the conclusion.
- **Corollary for diagnostics you write:** a message that hard-codes one configuration's answer will
  confidently *mislabel* the configuration you introduce to test it. Two such messages in this harness called
  the correctly-trained artifact "an out-of-band extrapolation". Classify on the measured facts, not on the
  configuration you had when you wrote the message.

Harness: `scripts/run_response_seed_ensemble.sh` + `scripts/summarize_response_seed_ensemble.py` (the
summarizer derives its statistics from the raw corners, self-checks them against the log's own printed
ratios, and *excludes* rather than averages any replicate that violated a precondition).

## Two more, from diagnosing a RECURSION rather than a residual (added 2026-08-05, ADR 0102)

Both cost or saved a wrong turn on line S while answering line M's "the count recursion is unanchored".

- **A code-level inconsistency is a HYPOTHESIS about the trajectory, not a defect, until you show the
  branch executes.** `slow.jl:1026` clamps a ratio and `:1110` stores the *unclamped* value — a real
  inconsistency, S-owned, cheap to fix, and byte-identical exactly where the current code is already
  correct. The ideal shape for a fix, and **completely empty**: the clamp binds **0 of 150 years**. One
  4-minute job before writing the patch is what stopped it shipping. This is CLAUDE.md §3's
  `individual=true` dead-path rule (*confirm the C path actually runs before porting it*) turned on **our
  own** code — the reflex is weaker there precisely because we can read the source and feel certain.
  Corollary: an empty result here is a *reportable finding*, not a failed probe. Write the "this is empty"
  verdict into the probe's output so the next session does not re-derive it.
- **Separate the STATE VARIABLE from its DIAGNOSTIC — they can disagree, and the diagnostic is the one you
  will instrument by reflex.** The emulator's AR state (`n_prev`) and the physical roster it is supposed to
  describe converge *differently*: an `n_init` sweep retains **0.092** of its spread in the AR state and
  **60.2 %** in the stand. A probe that measured only `n_prev` would have confirmed the docstring
  (`slow.jl:844-846`, "self-corrected by the `max_*` clamp thereafter") and closed the investigation with a
  clean, wrong answer. Ask which variable the *consumer* actually sees — here line F sees the stand, not
  the AR state — and measure that one.
- **Perturb the state, not only the seed, and read RETENTION vs HORIZON.** "Does this recursion have an
  attractor?" is answered by scaling the initial condition and watching whether the spread decays. Report
  retention at several horizons: this one *rose* to 1.40 at yr 25 before settling, so a single late read
  would have understated it and a single early read would have overstated it. A retention converging to a
  **non-zero asymptote** (1.04 here, flat yr 150→300) is the signature of no restoring force at all, and is
  a much stronger statement than any one-step bias estimate.

**Cross-line corollary (this one is about process, not measurement).** Read the sibling line's **latest
commits**, not only the ADR you were handed: line M refined ADR 0054 four hours before this probe landed,
independently reaching the same decomposition, and the handoff text still said otherwise. Diff
`origin/main` *before* writing your attribution, not after. And read the part of their result that does
**not** fit — M's teacher forcing recovering 59–72 % rather than ~100 % was the entire clue, sitting in
print, unremarked.

**Corollary — a cross-line contract QUANTITY can move under you, so re-derive the basis from the source
before you score anything.** Line O's O3b was aimed at a retired basis on *both* sides at once: the runtime
target (`slow.jl`'s `soilmoist`) had been redefined by ADR 0035 from an unweighted whole-column mean to a
`whcs`-weighted mean over the top 3 layers (1.0 m) read at year end, *and* the reference distribution had
been replaced because the old one was `swc` = water over **saturation** capacity, i.e. exactly the
porosity-normalized quantity the mapping was designed to avoid. Two tells worth memorising: (1) the retired
and live references had nearly the same **mean** (0.5075 vs 0.478) and completely different **shape** (q25
0.319 vs 0.0) — *matching on the mean alone would have certified the wrong basis*; (2) the warning was
sitting in the line's own `STATE.md`, written by the sibling line, and was found only on the pre-merge
rebase. **Before scoring a cross-line quantity: open the function that computes it and read it, and
re-check which artifact the reference numbers came from.** Verify the sibling's claim against the source
rather than adopting it — here it checked out, but the check is what makes it usable. If a job is already
running on the old basis, **cancel it**; a number on the wrong basis costs more than the compute.

## When the constant you "don't have" is three files away (added 2026-08-05, ADR 0103)

ADR 0102 concluded a fix was blocked because the coupled loop lacked the count↔density conversion, and
deferred it to another line as an interface change. The conversion is `param.patcharea = 225.0` m² (15×15),
sitting in `par/lpjparam_fit.js`, with `new_tree.c:209` giving every individual `nind = 1/patcharea`. The
owner spotted it in one line. Two rules came out of that, and both generalise well beyond this repo:

- **"X cancels" is a statement about an EXPRESSION, not about X.** CLAUDE.md carries *"with
  `nind = 1/patcharea` … the patcharea cancels"* — true, and true only of the ADR-0035 per-patch LAI
  derivation it was written about. Read as a property of the *quantity*, it becomes "we never need
  patcharea", which is false in every other expression. When you meet a "cancels"/"drops out"/"is
  arbitrary" note, ask **cancels against what, in which expression** before inheriting it as a constraint.
- **Before concluding a quantity is unavailable, grep the upstream source for it.** The C source, its
  parameter files and the committed fixtures are all readable from here. Verify with `cpp -P` (CLAUDE.md §3
  — and check for duplicate keys), then confirm end-to-end against a fixture: `sum(nind) × 225 = 17.000`
  exactly, on the committed Hainich patch, settled it in one command. A two-minute check stood between a
  shipped fix and a deferred cross-line negotiation.

**And the finding that check exposed, which is the more important one: a validation suite built entirely on
ratios, distributions and correlations is BLIND TO AN ABSOLUTE-LEVEL ERROR by construction.** The coupled
stand sat **1.41× denser** than its own count model's absolute prediction, indefinitely, while the ADR-0030
per-cell trait gate, the count R² (0.982), the pooled-KS checks and the trained-band diagnostic were all
green — because not one of them reads a level. If every metric in a panel is scale-invariant, the panel
cannot see a scale error. **Add at least one absolute check** (predicted level vs the model's own target, in
the consumer's units) whenever a component's output is consumed as a level rather than as a shape.

**Corollary (added 2026-08-05, same ADR): a test that fails on a threshold YOU chose is data about the
system, not just a bad threshold.** A new testitem asserted an anchored rollout forgets its initial
condition within 25 years and failed at 0.425 against a demanded 0.3. Relaxing the number would have taken
one minute and hidden the finding. Measuring the curve instead showed convergence is **non-monotone** — a
fast collapse by yr 5, a transient re-divergence peaking near yr 25, settling by yr 50–100 — which is a
caveat that changes how a downstream line must score its 10-year runs. **Before adjusting a threshold you
wrote, plot the quantity against the axis you assumed it was monotone in.** The threshold is a hypothesis
too.


---

## A pre-registered criterion needs the SAME basis check as a residual (added 2026-08-06, ADR 0104)

Pre-registering a pass/fail criterion before a run is good practice and it works — it stops you tuning a
knob until it passes. **It does not stop you measuring the wrong quantity**, and it is *more* exposed to
that than an ordinary residual is, because the commitment is made at the moment of least information about
the intervention. §1's rule ("state the reference basis") applies to a criterion, not just to a gap.

**The check, and it is two minutes:**

> **Read the diff. Name the variable the change writes to. Confirm the criterion's metric is a function of
> that variable.**

ADR 0103 §6 pre-registered a flip criterion for the Component-S level anchor and scored it on
`s.target_history`. The change is seven lines (`slow.jl:1066-1070`): it multiplies the **roster** (`dtree`);
`target` appears only on the right-hand side, as the thing being aimed at. **The anchor never writes
`target_history`.** So the criterion measured a second-order feedback (moved stand → moved canopy features →
different DRF row next year) with its own per-cell sign, and it scored FAIL in 4 of 5 cells on a change
that, measured on the stand, improved **all five cells at all three settings**.

**The tell was already printed and nobody read it that way.** The same run reported the stand landing on its
own count model's target at **1.001 in all five cells**, two tables below a criterion scoring FAIL in four.
**Two tables that disagree that completely are not measuring one thing** — treat that as a basis alarm, the
same as §3b's <0.99 cross-check.

**Corollary — when a control arm and a truth disagree, score against the TRUTH.** The same session nearly
repeated the error an hour later on the memory arm: the obvious read is `anchored − free`, which showed a
degradation in 8 of 10 pairs. But the free arm sat *above* the C's autocorrelation in 9 of 10, so lowering
the AC moved **toward** the oracle. Mean |AC − oracle| went 0.0439 → 0.0405, i.e. an improvement. **A control
arm is a reference, not a target.**

**And check that the arm you were pointed at is the arm you need.** Line M's caveat named an existing
`anchor0` arm — which is **teacher forcing**, a different intervention that *injects* an external series'
memory. Running it would have answered a question about something else. Read what the arm DOES, not what it
is called.

**When you do change the yardstick after seeing results — and sometimes you must — the new one is only
legitimate if its justification does not depend on the results.** State that explicitly. Here the argument
is readable off the seven-line diff and would have held identically if every cell had passed. If you cannot
make that argument, you are rationalising, not correcting.

**Deleting a clause after measuring it is allowed on the same terms.** A 100-year biomass-drift clause was
dropped from the re-registered criterion because the mechanism says the anchor cannot affect it (that drift
lives in the fast core's carbon pools). Recorded in the ADR with its measured numbers, and still reported in
every run — dropped as a *gate*, not hidden as a *fact*.

**Have the SCRIPT compute the headline statistic, not you.** The `pin1` control figure in ADR 0104 §6 was
mental arithmetic over a printed 10-row table and it was wrong by 75 % (0.0556 for a true 0.0973). It was
caught only because the summary was later added to the probe and the number re-derived. A per-row table
printed by a job is machine truth; **any aggregate you form by reading it is not**, and it will be quoted
onward as if it were. Add the aggregate to the script and re-run — these probes cost seconds to minutes.

**Re-deriving it by hand from the printed table is not the same as re-running.** That intermediate step
caught the 75 % error but introduced a second, smaller one: recomputing from the table's `%.3f` values gave
0.0975 where the script's full-precision answer is **0.0973**. Rounded inputs propagate. The hand
recomputation is worth doing immediately — it is what caught the real error, in seconds — but it is a
*triage* step, not the number you publish.

## A reference basis has more than ONE AXIS — naming a confound is not closing it (added 2026-08-06, ADR 0105)

The section above fixed the *metric* axis of a basis (score the quantity the change writes). It is not the
only axis, and getting one right feels like getting the basis right. **List the axes explicitly before you
publish a number.** For a coupled-emulator-vs-C comparison here there are at least three:

| axis | the question | how it went wrong |
|---|---|---|
| **metric** | is the scored quantity a function of what the change writes? | ADR 0103 §6 scored the count model's *prediction* for a change that writes the *roster* |
| **population / canopy** | did you run the same members the reference ran? | ADR 0104 ran the single **modal** (densest) patch against a C that reports a **25-patch mean** |
| **aggregation** | mean-of-ratios or ratio-of-means; year-matched or window-mean? | a drifting 0.8→1.7 ratio has a 10-yr mean of 1.00 |

**The rule this cost a published recommendation:**

> When you write "⚠ this confound means the measured effect is an UPPER BOUND", you have not measured the
> effect. **Do not publish a recommended value, a default, or a tuned parameter from that arm.** Either
> close the confound first, or publish the finding *without* the recommendation and say what would close it.

ADR 0104 named the modal-patch confound in its own §5, called its benefit an upper bound, and recommended
`anchor = 0.25` anyway. Re-run on the ensemble (ADR 0105), the free-running error was **4× smaller**
(mean score 0.679 → 0.159), the sign of one cell's error **reversed** (Sahel 1.55× over-dense → 0.52×
*under*), and the intervention went from "improves all five cells" to **worsening the mean at every
setting**. Nothing was wrong with the arithmetic; the arm was never a measurement of the thing it decided.

**Corollary — an ATTRIBUTION arm inherits every basis error of its harness.** A diagnostic arm feels more
robust than a skill measurement because it is "just isolating a term". It is not. ADR 0054's teacher-forced
arm was measured on the modal patch AND scored on the prediction, published as removing 59–72 % of the
coupled count error, and **inverted under either correction** — on the ensemble, scored against the C, it is
worse in all five cells. Apply the metric check and the population check to your controls too.

**And the cheap one: PRICE a retrain (or any expensive fix) OFFLINE before buying it.** Before committing to
retraining a model to remove a feedback bias, reduce the loop to its scalar form and measure the terms from
the tables you already have: the one-step bias `b` (model fed the TRUE previous value) and the loop gain
`g = ∂pred/∂feedback_feature`, giving `e_k = b(1−g^k)/(1−g)`. Two hundred lines and one 4-minute job stood
in for a global two-artifact retrain here — and the answer was **empty** (`b` = −0.0014 on counts of ~10,
`g` = 0.56 ⇒ bounded 2.28× amplification). ⚠ Measure `g` with a **secant, not a derivative**: a tree
ensemble is piecewise constant, so an infinitesimal step returns 0 for almost every row and reports "no
feedback" from a model that has plenty. Report several step sizes so the step is not a hidden knob.
Entry point: `scripts/exposure_bias_probe.jl`.

**When the offline prediction and the coupled measurement disagree, that gap is itself the measurement.**
Here the offline AR(1) predicted +4.2 / −5.9 / +10.5 / −0.0 / +0.2 % per cell against a coupled
+35 / +15 / +38 / −48 / +4 % — wrong size everywhere, wrong sign twice. Since the offline number is computed
with the model fed the *reference's own* features, the residual is by construction everything the coupled
loop adds. That located the defect in a different component (and a different line's paths) without a single
further probe.
