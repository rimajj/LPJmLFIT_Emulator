---
name: residual-diagnosis
description: The mandatory discipline BEFORE chasing any fidelity residual (an F_diff-vs-C gap, an S-panel miss, an energy/closure discrepancy) — state the reference basis and a falsifiable hypothesis, confirm the comparison basis is correct, and time-box before writing probe scripts. Use it at the start of any "why doesn't X match Y?" investigation. ALSO how to trisect the fallout when a basis error IS found (ADR 0060): a RATIO over time is partly robust to a basis substitution while a LEVEL is not, so label every downstream claim ratio-or-level before re-measuring; emit both columns side by side rather than replacing one; cross-check the corrected reference through a second independent reader; add the column additively and diff row-by-row. ALSO the FORCING-basis check every learned-component score needs before it is believed (ADR 0112): trace each conditioning feature back to who computed it, because K-fold BY CELL holds out space not time and a lagged-truth feature (`n_prev`, `*_init`, any AR state — grep the table builder for `shift(`) makes the score one-step teacher-forced; then build the NULL that is handed the same thing and learns nothing and score it in the SAME process — a metric the null also passes (here a deattenuated response slope of 1.03 vs the model's 1.01) has no power and cannot be quoted as evidence. And separate an INITIALISATION gap from a GROWTH gap by reading the quantity at t=0 against the exact inputs the state was built from -- noting that a demography-off kernel arm has no mortality, so a monotone rise there is expected and cannot convict the growth code.
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

**Under parallel lines, a REBASE can change the configuration your measurement was made in.** The mandated
`git pull --rebase origin main` before a push can pull in another line's **default flip** — landing between
your jobs and your ADR, so the numbers you are about to publish were measured on a configuration that no
longer exists on `main`. Cheap fix: **after the final rebase, re-run the decisive probe and diff the two
logs.** (Line E's ground-heat default landed 20 minutes before ADR 0105 was pushed; the re-run reproduced
every printed digit, so the ADR could say so instead of carrying an unstated caveat.) ⚠ **A null here needs
the fire-check too** — confirm the new path actually executed, or "identical" may just mean the flip never
reached your code. The tell that made ADR 0105's null meaningful was that the 1e-12 carbon residuals *did*
move while every reported quantity did not.

## An ABSENT behaviour is not automatically a MISSING one (added 2026-08-06, ADR 0107)

Before calling anything a gap, defect or limitation: **check whether it was DESIGNED OUT.** One question per
candidate row — *is there an accepted decision saying this should not be there?* — and `grep` the ADR index
for the term before writing the row.

A gap list built by asking *"what does the model not do?"* will confidently promote **every deliberate
simplification to a defect.** ADR 0106 listed "the emulator has no CO2 response" as "FAILS COMPLETELY, the
largest single gap" and escalated it to a possible new run of the reference model. It is the opposite: the
reference model is deliberately run at constant CO2 (its own CO2 response is wrong without nitrogen
limitation), so **an emulator with no CO2 response MATCHES the reference** — adding one would be a fidelity
*regression*. The governing decision (ADR 0004) was **listed in the offending document's own `Related` line**:
**citing a decision is not reading it**, and retrieval next to contradiction is a real failure mode.

**Corollary, and it is the mechanical fix: under a "match the reference" criterion, state every candidate gap
as a COMPARISON against the reference, never as an absolute capability.** "X has no Y" is not a finding.
"X's Y differs from the reference's Y" is — and phrasing it that way makes the CO2 row self-evidently false
before anyone has to argue about it. Apply this to every row of a gap table, without exception.

⚠ **And a wrong claim in a handoff banner is not a documentation error — it is misdirected sessions.** This
one reached `MEMORY.md`, all four lines' `## NEXT` blocks and `~/.claude/CLAUDE.md` before it was caught. When
a correction lands, **fix every place the claim was broadcast in the same commit**, and if the owner reports
having corrected it before, record it as *standing, do-not-re-litigate* rather than as a fact.

---

## MEASURE THE BASELINE BEFORE ARGUING FROM CODE STRUCTURE THAT A CHANNEL IS CLOSED (`[VERIFIED 2026-08-06]`, ADR 0108 §1)

The sibling of the rule above, applied to **our own reasoning** rather than to a gap list — and it caught a
false claim that had already reached an ADR draft, a changelog entry, three source-comment blocks and a
testitem header before one 3-minute job killed it.

**The shape of the error.** You read the code, find that a conditioning input is a frozen per-cell constant,
and conclude the model "therefore cannot respond to that driver *by construction*" and its response is
"structurally zero". The first half is true and checkable. **The second half is a non-sequitur**, because the
frozen input is one of several: in the case that produced this rule, the frozen tail was **6 of 14** columns
and four of the remaining eight varied per cell-year, carrying much of the same physical signal. Measured, the
response was **not zero** — slopes 0.16-0.85 across four axes, partial and axis-dependent.

**Why it is seductive, and why review does not catch it.** A structural argument reads as *stronger* than a
measurement ("by construction" sounds like proof), it is cheap, and every individual sentence in it is true.
It also predicts a dramatic finding, which is exactly when scrutiny should go up. A reviewer checking the
claim re-reads the same code and agrees.

**The rule.** *"Input X is constant" bounds what X can carry. It says nothing about what the model does.*
Before writing that a response is absent, zero, structurally impossible, or closed:

1. **Name the statistic** that would show the response, and make it a *response* statistic, not a level one —
   a model can match the reference in two regimes separately and still have zero response between them, so
   score the DIFFERENCE (e.g. regress the emulator's per-cell change on the reference's per-cell change
   through the origin; the slope is the answer, 0 = closed, 1 = right).
2. **Measure it on the SHIPPED artifact first.** That number is the reference basis for whatever you are about
   to build, and "success" means beating it — not moving off an assumed zero.
3. **Enumerate the other inputs** and ask which of them already carry the driver you think is missing.

The payoff is not only avoiding the wrong claim: the baseline measurement is usually the most valuable thing
produced, because it is a real global number where the line had been quoting five-cell ones.

**And when the claim has already been written down, correct every copy in the same commit** — ADR, ADR index,
changelog, source comments, test headers, journal, STATE. A corrected ADR with an uncorrected code comment is
how the wrong version survives.

---

## Before you SIMULATE to test a claim about the C, check whether the C already EMITS it per individual (ADR 0110, line S, 2026-08-06)

The companion to the rule above. That one says *measure the baseline before arguing from code structure*.
This one says *the measurement is often far cheaper than you assume, because the oracle already published the
answer.*

**The annual `ind` table is PER-STEM, and it carries derived state, not just inputs.** Its 29 columns include
`wscal_mean` (each individual's own annual-mean water scalar), `minwscal`, `D95max`, `beta_root`, `D95`,
`k_root`, `Age`, `Height`, and **the four realized hazards** `mort_npp` / `mort_age` / `mort_water` /
`mort_temp` plus `mort` and `isdead`. So a whole class of questions — "do individuals actually differ in X?",
"does X track trait Y once composition and size are controlled?", "how much of the hazard does the term we
zeroed actually carry?", "does that change under warming?" — is a **parquet scan over the real trees the C
grew**, not a simulation, not a proxy, and with no modelling assumptions of your own in the answer.

**It is fast.** Row-group pruning makes a single-cell filter ~**0.1 s** over the 22 GB historic / 92 GB ssp370
tables. There is no reason to reach for a simulated probe first.

```python
lf = pl.scan_parquet("/p/tmp/jamirp/emulator_global/ind_hist_seed1_all.parquet")
df = lf.filter((pl.col("Cell") == 42490) & (pl.col("Type") <= 6) & (pl.col("D95max") > 0)).collect()
```

**Use it as an ORACLE for a port, not just for a baseline.** The table often contains both the input and the
C's own derived output, which turns "is my port right?" into a direct comparison instead of a
self-consistency check. ADR 0110 validated a `getbetaroot.c` port to **5e-7** by reading each stem's `D95max`
*and* the `beta_root` the C computed from it. Prefer that to any golden file you generate yourself.

**Four traps, all of which cost something here:**

- **Grass rows have their tree fields ZEROED** (`fwriteoutput_ind.c:139-189`), so filter `Type <= 6` **AND**
  `D95max > 0`. A bare `Type <= 6` is not enough on its own if ids drift.
- **A raw correlation across a cell mixes three things** — between-PFT composition, tree size/ontogeny, and
  the trait. Rooting depth in particular is set BOTH by the sampled trait and by tree height
  (`getrootdepth`). Centre within **(PFT × age band)** and pool, or you will report a composition effect as a
  trait effect. It matters: Hainich's raw and within-band numbers agreed (0.189 / 0.184) but the boreal cell's
  flipped sign (−0.180 / +0.021).
- **`wscal_mean` is an all-365-day POTENTIAL index and equals 1 on a no-demand day** (ADR 0051). Any spread
  computed from it is a **lower bound** on the growing-season daily spread — say so with the number.
- **A zero can be the trait, not a defect.** The Sahel showed exactly 0 drought mortality in the driest cell
  of the five. Cause: `waterstress_tree` gates on `wscal < mort_water_res − minwscal`, and those stems average
  `minwscal` 0.655 ⇒ a threshold of 0.095 against `wscal` 0.641, so it never fires — they are drought-tolerant
  *by trait*. Chase a surprising zero to its gate before calling it a bug or a missing mechanism.

**Pre-register the pass criterion in the script, before the run, and then report against it honestly** — the
Phase-0 check here passed on its 3-part median rule while one sub-test failed at 2 of 5 cells, and the write-up
says so rather than quietly dropping the sub-test. Rewriting a criterion after seeing its arm is the ADR-0104
error. Worked example: `scripts/diagnose_per_tree_water_access.py`.

---

## 5. Before calling a residual real: is the TARGET noisier than the residual? (ADR 0093, integrator, 2026-08-07)

LPJmL-FIT is stochastic and its own answer at the production `npatch=25` is **already outside the 10 %
acceptance band** for several quantities. So a "miss" can be the target's own scatter. Do these three
checks *before* diagnosing a residual against any per-cell C statistic.

**(a) Look up the noise floor for the quantity you are scoring.** Bootstrap CV of the C's own cell estimator
at `npatch=25` (Amazon replicate run, 50 000 patches): `n_trees` 8.9 % · `vegc` **11.3 %** · median Height
**11.3 %** · median Wooddens 3.3 % · median SLA 2.4 % · median minwscal **11.0 %** · **median D95max 22.7 %**.
Production two-seed medians over 53 111 cells: `n_trees` 7.6 %, `D95max` 11.6 %; in the **<2 stems/patch**
stratum (7 964 cells) 31.6 % on counts and 42.7 % on carbon. **A 12 % per-cell miss on `vegc` in a sparse
cell is not a residual — it is the model.** ADR 0106's tolerance is `max(10 %, the two-run spread)`; use the
second branch.

**(b) The 25 patches are NOT 25 samples — correct for it.** The cell-level seedbank (`getsapling.c`,
`cell->treelist`, filled `foreachpatch`) couples the **inherited** trait pool: measured `n_eff` = 12.9
(`n_trees`), 8.2 (Wooddens), 5.2 (SLA), **4.8 (D95max)**. The control that isolates the channel: median
**Height** — same stems, same patches, *not* inherited — has `n_eff ≈ 25`. So if a trait statistic looks
noisy and a size statistic on the same stems does not, that is the seedbank, not your code.

⚠ **(c)'s NUMBERS ARE SUPERSEDED — see `## 5c-CORRECTED` at the end of this file (ADR 0111); the method below is right, the numbers are not.**

**(c) Deattenuate before concluding a RESPONSE is broken.** Scoring a warming response against ONE seed
regresses on a noisy regressor and biases every slope toward zero. Estimate reliability
`λ = Var(true)/(Var(true)+Var(noise))` from the two seeds that already exist in both scenarios, and report
the raw slope **and** `slope/λ`. Measured: SLA `0.851 → 1.08` and minwscal `0.689 → 0.99` — **already
correct**, not broken; only Wooddens (0.63) and D95max (0.51) are genuine. This single correction re-pointed
the project's whole response diagnosis from four broken axes to two.

⚠ **The per-cell trait response is not an observable at all in single-seed truth.** The two seeds disagree
on the **sign** of the hist→ssp370 trait shift in **33–37 %** of cells (S/N 1.25 / 0.92 / 1.68 for
Wooddens / D95max / minwscal), while the **area-mean** `vegc` response is −11.28 % against 0.055 % noise
(S/N ≈ 200). Score a response on a multi-seed mean and/or in aggregate; a per-cell single-seed response
plot is mostly noise. Two more reference seeds cost ~35 000 core-h ≈ 17 h on 2048 cores.

**A cost regression is a residual too, and nobody was checking.** Before optimising anything, time the
emulator end-to-end against the C on the same cells and years. Measured 2026-08-07: the shipped Julia
emulator is **3.8× SLOWER** per cell-year than the C it replaces (1.096 vs 0.290–0.383 core-s), because its
per-individual daily step is **51×** the C's while its per-patch fixed cost is **0.066×**. Every speed
proposal must be priced against the **Julia** cost model — four architectures that looked good against the C
were all slower than the existing code at 8 patches. Harness: `/p/tmp/jamirp/npatch_analysis/bench_emulator.jl`.

---

## A basis error does NOT invalidate every claim built on it — sort them by RATIO vs LEVEL (added 2026-08-06, ADR 0060)

When you find that a comparison used the wrong reference column, the reflex is either to withdraw everything
downstream or to hope none of it mattered. Neither is right, and there is a cheap rule that sorts them:

> **A ratio of the same quantity over time is partly robust to a basis substitution; a level is not.**

Measured, on the two FPC outputs LPJmL-FIT writes from the same trees (crown-cover sum vs a leaf-area
Beer–Lambert form, **1.5–2.3× apart**): every *level* claim inverted — "the fast core under-predicts canopy
cover in all five cells (0.31–0.72×)" became over-prediction in four of five (1.05–1.47×) — while the *drift*
ratios moved almost not at all (the C's own 2019/2010 ratio: 0.89 vs 0.90 boreal, 0.97 vs 1.00 Hainich, 1.25
vs 1.23 Sahel; only mediterranean 0.77 vs 0.67 and Amazon 0.89 vs 0.99 shifted materially). So a sibling
line's attribution built on the *drift* survived intact while the *level* statement inside it died.

- **Enumerate the downstream claims and label each RATIO or LEVEL before re-running anything.** That predicts
  which ones need re-measuring and which only need a footnote, and it is usually a 5-minute reading exercise.
- **Emit BOTH columns and keep printing them side by side.** Withdrawing the wrong one and deleting it means
  the next session cannot tell a corrected number from an uncorrected one. Two adjacent columns can never be
  substituted silently again; one column with a better name can.
- **Cross-check the corrected reference through a SECOND, independent reader before quoting it.** Two
  harnesses reading one table and agreeing to the digit is what licenses the number — and it is nearly free
  when a sibling probe already loads the same fixture.
- **Add the column additively and prove it.** Append new columns last and diff every pre-existing value
  row-by-row against the pre-edit file. A basis fix that also moves a committed baseline is two changes
  wearing one commit, and guardrail 4 cannot tell them apart.

**And separate an INITIALISATION gap from a GROWTH gap before attributing either.** A reconstructed initial
state scored at the first *annual* output already contains a year of the model's own dynamics. Read the
quantity at **t = 0**, before any step, against the exact inputs the state was built from: here that gave
1.00–1.04 in all five cells and **eliminated the reconstruction as a cause in one column**, leaving growth.
Sibling trap in the same arm: a kernel-isolation configuration that switches demography off has **no
mortality and no establishment**, so a monotone rise in a standing-stock quantity is *expected by
construction* and that arm cannot convict the growth code. Quote a growth number from the coupled arm; the
isolation arm can only convict a cell where the quantity moves in the direction nothing else can produce.

## 5c-CORRECTED. THE YARDSTICK ITSELF WAS WRONG THREE WAYS — use these numbers, not §5(c)'s (line S, 2026-08-10, ADR 0111)

§5's *method* is right and its (a)/(b) numbers stand. **Its (c) numbers do not.** Reproducing that correction
on one self-consistent basis over **51 767 of the 54 020 tree-bearing cells**, both scenarios, turned up three
independent errors — and each is a trap you can repeat in any two-seed analysis.

**(1) `λ` and `slope/λ` are easy to transpose, and the transposition is self-consistent.** Both numbers are
in the same range for a broken axis, and both satisfy `deatt ≥ slope`, so neither an eyeball nor an
internal-consistency check catches a swap. ADR 0093 §3e has them swapped in exactly its Wooddens and D95max
rows. **Guard:** print `slope`, `λ` and `slope/λ` in ONE row from ONE expression, never assemble the table by
hand from two sources.

**(2) `λ` IS BASIS-SPECIFIC. A reliability belongs to a STATISTIC.** Dividing statistic A's slope by
statistic B's reliability is undefined, and it happened here because λ was log-space/single-year/≥50
stems/43 257 cells/uncapped while the slope was linear/all-years-pooled/≥30 stems/52 074 cells/`STEM_CAP=400`.
**Guard:** compute λ and the slope in the same function, over the same rows. Then run the check below.

**★ (3) THE CHECK THAT VALIDATES A DEATTENUATION: vary the basis and watch the QUOTIENT.** Across the capped
and uncapped bases the raw slope moved up to **21 %** and λ up to **25 %**, while `slope/λ` moved **≤3 %** on
all four production trait axes. That invariance is what licenses steering by a deattenuated number. `Height`
FAILED it (1.05 vs 0.85) and is therefore quotable only as a range. **If the quotient is not basis-invariant,
you do not have a deattenuated slope — you have two errors that happened to divide.**

**(4) A PER-PATCH DENSITY MUST BE DIVIDED BY THE CONFIGURED PATCH COUNT, NEVER BY THE OCCUPIED ONE.** Dividing
a cell's stem count by the number of patches that happen to hold a tree makes the denominator co-vary with the
numerator across seeds and **cancels part of the sampling noise** — it understated the sparse stratum's floor
by **3×** (10.5 % where the truth is 27.0 %). Use the configured `npatch` (25 here) and assert no cell-year
exceeds it. ⚠ `cell_npatch.parquet` is itself derived from occupied patches, so it is the wrong table for this.
**Tell:** a "reproduction" that misses a published number by ~3× is a bug, not a basis nuance.

**(5) ALWAYS NAME THE FLOOR'S BASIS — per-cell-YEAR and per-cell CLIMATOLOGY differ by 2–3×.** A 20-year mean
averages ~√20 of the noise away. Per cell-year: counts 8.59 %, carbon 11.93 %, sparse stratum **27.0 % /
37.2 %** — which is the basis §5(c)'s 31.6 %/42.7 % lives on, though **those two numbers are not exactly
reproducible and the ~14 % gap is unresolved**: the year, dead stems and grass inclusion were each tested and
ruled out (job 1743684), leaving an undocumented difference in that record's per-cell estimator. Per-cell
20-yr climatology: counts 6.77 %, carbon 10.16 %, sparse stratum 16.6 % / 25.3 %. **Use a floor you can
regenerate with one command, and state its population** (here: survivors, `Type<=6`, divided by the
configured `NPATCH=25`). **`D95max` exceeds 10 % in EVERY density stratum** (10.1–15.4 %).

**(6) ABOVE 1.0, A BIGGER SLOPE IS WORSE. The target is 1.0.** Score `|deattenuated slope − 1|`, not the
slope. The corrected panel (2-seed deattenuated, shipped pin): **SLA 1.28 — OVER-responds by ~30 %**, minwscal
1.06 correct, **Wooddens 0.66 — the worst axis**, **D95max 0.73 — NOT the worst** (its raw 0.163 is mostly
attenuation: λ = 0.198, the only quantity whose per-cell response S/N is below 1, at 0.50). So retire **both**
"four broken axes" *and* "two broken axes at 0.63/0.51".

**(7) Score the AGGREGATE as primary.** Area-weighted response S/N is **25–489** against a per-cell 0.5–3.1 —
but report LATITUDE BANDS, because above-ground carbon responds −1.5 % (tropical) / −3.9 % (temperate) /
**+19.4 % (boreal)** against a global −0.54 %. A global mean alone calls that "almost no carbon response".

**Don't re-derive any of this.** `scripts/build_truth_yardstick_tables.py` (stage 1, 2.55e9 stem-year rows →
small per-cell tables in 3.5 min) then `scripts/diagnose_truth_yardstick.py` with `PRED_DIR=<dir1>,<dir2>`
scores any number of arms on the one canonical basis. Committed table:
`test/testitems/references/S_truth_yardstick_summary.csv`. **λ for 1/2/4 seeds** — counts .908/.952/.975 ·
carbon .616/.762/.865 · SLA .645/.784/.879 · Wooddens .510/.676/.807 · D95max **.198/.330/.497** · minwscal
.640/.780/.877 · Height .315/.480/.648 — which is also the quantitative case for the extra reference seeds.

**(8) SCORE THE PER-CELL PATTERN *AND* THE AREA-MEAN TOTAL — they fail independently, and one alone hides the
defect.** Added 2026-08-10 with the count side (`COUNT_DIR=<pooled count table with y.f64 + preds_oos.f64>`,
which `diagnose_truth_yardstick.py` scores alongside the trait axes). Measured on the shipped generation:
**counts** deattenuated per-cell slope **1.01** but area-mean response only **0.69×** the truth — the right
*pattern*, too small a *total*. **Wooddens** is the exact mirror: area-mean **1.13×** but per-cell **0.66** —
the right *total*, in the *wrong places*. Either statistic alone reports one of them as fine. So: a per-cell
slope near 1 does **not** mean the response is right, and a correct area mean does **not** either. ⇒ **the
tree-count warming response is faithful per cell; the response error lives in the TRAIT axes** — do not write
"the warming response is indistinguishable from zero" without naming the quantity.
**And cross-check the basis whenever the truth comes from a second table** (ADR 0030): the count table's own
seed1 response vs this reduction's correlated at **r = 0.9948** — two independent code paths over one run.
Below ~0.9 you are comparing different quantities and no slope is comparable to the rest of the panel.

**(9) BAND THE RESPONSE RATIO, AND GUARD ITS DENOMINATOR — an aggregate ratio is two traps at once.**
Added 2026-08-10; both traps fired inside one afternoon's work.
* **A positive GLOBAL ratio hides wrong-SIGNED regional responses.** Measured, area-weighted prediction ÷
  truth by latitude band: tree counts +0.71 globally but **−0.51 in the tropics** (temperate 0.93, boreal 1.07
  are fine); SLA +1.94 globally but **−3.91 subtropical** and **−0.29 temperate**; minwscal +2.95 but
  **−4.45 boreal**. So "counts respond 31 % too weakly" was never the defect — a correct mid-latitude and
  boreal response plus a tropical **sign error** was. A global aggregate is a ratio of near-cancelling sums
  (the truth's global mean count response is ~3 % of its between-cell spread), so it can look right while the
  pattern is wrong, and vice versa.
* **★ A ratio whose DENOMINATOR is not determined must print `n/d`, never a number.** Guard: compute the
  truth aggregate's own two-seed noise **in that band** and require S/N ≥ 3. `D95max`'s tropical band comes
  out S/N 1 — no D95max claim is possible for the tropics on this reference data at `npatch=25`.
* **And keep exactly ONE definition of "the aggregate ratio".** An unweighted mean-ratio and an area-weighted
  one disagreed by **20×** on `Height` (0.14 vs 2.88) because its global aggregate is a near-zero residue
  (S/N 4) — and a draft ADR had already published the 0.14 as "the emulator delivers 14 % of the height
  response". The band ratios then showed Height is roughly RIGHT (0.92–1.51). **Neither number was a result.**
  If two "global" numbers for the same quantity can coexist in your output, one of them will end up in a
  conclusion.

## ★ THE FORCING BASIS IS A REFERENCE BASIS — AND A METRIC A NULL ALSO PASSES HAS NO POWER (line S, 2026-08-10, ADR 0112)

Two checks to run **before** you interpret any fidelity or response number of a learned component. They are
cheap, they are mechanical, and skipping the first one let "the count response is faithful" stand as a result
for a model that had been handed the answer.

**(1) Ask what the model was HANDED, not just what it was scored against.** Trace every conditioning feature
back to who computed it. In this repo the production count model's 15 features are *all* built from LPJmL-FIT's
own output for the same `(Cell, Patch, Year)` — and one of them, `n_prev`, is FIT's own answer for the previous
year. Plus: **K-fold *by cell* holds out SPACE, not TIME.** Held-out cells with per-row prediction is still a
one-step score in which nothing the model predicts is ever fed back. Three labels, and one is mandatory on
every number you publish:

| label | what the model is handed |
|---|---|
| **one-step, C-forced** | the reference model's own state *and* fluxes for the same step, incl. its previous-year answer |
| **flux-forced, state-recursed** | the reference model's fluxes; the model's own previous state |
| **free-running** | boundary conditions only |

The tell that you need this check: a feature list containing anything named `*_prev`, `*_init`, `lag*`, `n_0`,
or any "AR state". Grep the table builder for `shift(` / `.over(` — that is where a lagged truth enters.

**(2) Then build the null that is handed the same thing and learns nothing**, and score it through the SAME
code path, on the SAME cell set, in the SAME process (that is why `diagnose_truth_yardstick.py` takes a
comma-separated `COUNT_DIR` — two invocations is how two bases drift apart). For a lagged-truth feature the
null is "predict the lagged truth": `scripts/build_count_persistence_null.py`, ~40 lines, symlinks the shared
provenance arrays so it cannot drift from its source table.

What that measured here: R² 0.9622 (null) vs 0.9824 (model); per-cell response slope 0.980 vs 0.958;
deattenuated 1.029 vs 1.006; and the null reproduced the *regional* pattern including a wrong-signed tropical
response that had just been written up as "a concrete, localised target". ⇒ **the per-cell deattenuated slope
has essentially no power against persistence**, so it cannot be used to argue the emulator responds; and the
band-wise sign pattern was a property of the statistic, not a defect to go and fix. The statistic that *did*
discriminate was the **aggregate area-weighted ratio** (0.536 / 0.691 / 1.0 target).

⚠ **A null is a CONTROL, not a floor.** Do not quote it as "the skill of no model". The persistence null's own
aggregate ratio is 0.536 rather than 1.0 purely because a one-year lag under a trend shifts an N-year window
mean by `(first − last)/N` — an artifact of the null, not a property of the emulator.

⚠ **And do not read a null result as "the model is worthless".** State both directions: this model removes
**53.3 %** of the null's residual variance and adds a third of the missing response amplitude. The finding is
about what the *metric* proves, not about whether the model does anything.

## WHEN YOU CLOSE A "ONE DEFINITION ONLY" TRAP, GREP FOR THE OTHER CODE PATH — IT SURVIVED (line S, 2026-08-10, ADR 0113 §5)

ADR 0111 removed the second (unweighted) definition of the aggregate response ratio from the **trait** scoring
path and wrote "do not reintroduce a second one". The **count** path in the same file kept it for another month,
because nobody grepped. It was invisible for exactly the reason these bugs always are: on the production arm the
two definitions agree (0.691 unweighted vs 0.707 area-weighted). It only showed up on a new arm, where they
disagreed **fourfold and by sign** (−0.93 vs −0.226) — an unweighted mean-ratio is dominated by cells whose own
denominator is near zero, which is why the weighted one is the definition to keep.

So: after fixing a definition, `grep -n "<the quantity>" <file>` and check **every** call site, and prefer
computing the blessed quantity **once** in a helper both paths call (here: `band_ratios(...)["GLOBAL"]`) over
fixing two copies. And when two definitions of the same statistic agree on your current data, that is not
evidence they are the same quantity — it is the reason the bug survives to the run where they differ.

**The related honesty rule:** a corrected label can make an earlier finding *stronger*, and you have to say so.
Correcting this one moved the persistence null from "0.536 vs the model's 0.691" to "**0.685 vs 0.707**" — i.e.
the null matches the production model on the aggregate response too, so the finding got sharper, not softer.
Re-read what the corrected number does to the conclusion; do not assume a correction only ever costs you.

## A DRIFT ONLY MATTERS IF IT DOES NOT CANCEL — RESOLVE IT BY THE VARIABLE YOU ARE DIFFERENCING (line S, 2026-08-11, ADR 0115)

When the headline statistic is a **difference** (two scenarios, two treatments, before/after), a bias that is the
same on both sides costs nothing. So the useful question about a drifting recursion is never "how big is the
drift?" but "**how much of it fails to cancel?**" — and the two have completely different sizes here: the count
recursion's total drift saturates at a harmless < 2 % of the mean, while the part that differs between the two
climate scenarios reaches **90 % of the reference model's entire warming response, with the opposite sign**.
Resolving the bias by scenario at fixed lead was two lines of extra grouping and it converted "the response
inverts, we don't know why" into a quantified mechanism.

The corollary is a warning about explanations that feel structural: the previous ADR had attributed the
asymmetry to the two scenarios' chains having different lengths (19 vs 80 years). That is a real difference and a
plausible mechanism — and it was **wrong**. The test is a **matched-depth** re-score (keep only the lead values
present on both sides, weight them equally, so the lead mix is identical by construction). The inversion
survived it. **Before accepting a bookkeeping explanation for a scientific result, build the arm in which the
bookkeeping difference is removed** — it is usually cheap, and here it saved the next experiment from being
aimed at the wrong thing.

**And check what currently bounds the quantity before you change its form.** "Predict the increment/ratio so the
level cancels" is the standard fix for a drifting autoregressive model; measured, it made every statistic worse,
because a forest predicting a LEVEL has leaf values inside the training range and therefore cannot run away —
the level target was silently doing the job of the anchor an earlier ADR had gone looking for. Ask what keeps
today's predictor in range, and assume any reformulation deletes it.

## Before reading ANY correlation or attribution panel: check the variable actually VARIES (ADR 0117)

A column with no variance and a genuinely uncorrelated column produce the **same** degenerate output, and
they have **opposite** implications — "this input cannot matter, drop the question" versus "this input is
independent, which is itself a finding". Distinguishing them costs one line and skipping it nearly published
a wrong conclusion.

The tell is a panel that is *too clean*: correlations of exactly `±0.0000` against every other axis, `nan`
where a spread should be, or — the giveaway — an **arithmetically impossible** standardised statistic. A
selection differential of **−284 standard deviations** is not a strong effect; it is a near-zero denominator.
Any |z| beyond ~10 in a panel built on millions of rows is a broken denominator until proven otherwise.

So: **make the variability audit the FIRST panel, not a footnote** — per stratum, print each column's
distinct-value count, min and max — and have downstream panels print `const` rather than a ratio when a
column is degenerate. Then confirm the cause at its source rather than inferring it from the data: here the
trait was a **scalar in the live parameter file**, with the sampled-interval form commented out, so the
"uncoupled trait" reading was never on the table.

Worked example, reusable as-is on any axis: `scripts/diagnose_recruit_trait_axis_coupling.py`.

## A POOLED difference can be almost entirely COMPOSITION — run the within-group control in the SAME script (line S, 2026-08-11, ADR 0118)

**The trap.** You compare two sub-populations pooled over the globe (young stems vs all stems, one scenario
vs another, cells inside a band vs outside) and read the difference as the mechanism you were looking for.
But the two sub-populations may simply LIVE IN DIFFERENT PLACES, and then the pooled difference is a
weighted-average artefact — Simpson's paradox with a physical label on it.

**Measured cost of not doing it.** ADR 0118 compared FIT's standing trait marginal against its youngest-stem
marginal to size how much selection the recruit copula's training target already carries. Pooled, two of the
four axes looked catastrophic — rooting depth **−49.6 %**, drought threshold **−35.9 %** of the mean. Formed
*within* each (Cell, PFT) group and then averaged, the same two collapse to **−2.4 %** and **+0.4 %**: about
95 % of the apparent displacement was *where young stems live*, which the per-cell conditioning already
handles. **The pooled panel alone would have reported a four-axis crisis, of which exactly one was real.**

**And the control can point the other way, which is the reason to run it rather than to argue about it.**
On the axis that mattered (wood density) the displacement got **bigger** under the control, +5.4 % → **+12.2 %**
— composition had been *masking* it. So this is not a "pooled overstates things" rule; it is that pooled and
within-group are different quantities and you cannot predict the sign of the difference.

**Do this.** Emit both panels from one script, side by side, on one row universe — never as a follow-up run.
Then: (a) state which one answers your question (here: within-group, because the model being judged is
conditioned per cell); (b) **do not blend their ratios**. A within-group panel usually needs a coverage floor
(`n >= 30`), which makes it a BIASED SUBSAMPLE with its own denominator — in ADR 0118 the subsample's own
warming response was **−3698** against the pooled **+1848**, *opposite in sign*, so a ratio built from one
panel's numerator and the other's denominator is meaningless. One ratio definition per panel (ADR 0111 §5b),
and say which panel each quoted number is on.

Worked example: `scripts/diagnose_copula_selection_confound.py` (`pooled_panel` / `percell_panel`).

## CHECK WHETHER THE DECISION YOU ARE EXTENDING WROTE ITS OWN EXPIRY CONDITION (line S, 2026-08-11, ADR 0118)

**A good ADR often names the future change that would invalidate it — and nothing in this repo enforces
that the change, when it arrives, goes back and reads it.** ADR 0025 §3 picked the recruit copula's training
target (FIT's *survivors*) and wrote the condition into the decision text: *"Trait-dependent mortality is a
much larger, separate change; **if ever added, this training target must change**."* Trait-dependent
mortality was then built (ADR 0047), wired (ADR 0049) and adopted as a cross-line interface (ADR 0117) —
**three decision records over two weeks, none of which cited ADR 0025** — and the arm was one session from
running on an invalidated target.

**The 60-second check, before starting any arm that changes a model's behaviour:**

```bash
grep -rn "must change\|no longer\|ceases to\|if ever\|expiry\|only valid\|premise" docs/decisions/00NN-*.md
grep -rln "0025" docs/decisions/            # who has cited the ADR you depend on? (often: nobody)
```

Read the ADR that OWNS the artifact you are about to feed (its training target, its basis, its default), not
only the ADRs in your own chain. The failure mode is silent by construction: the invalidated ADR is
`accepted`, its artifact still loads, every gate stays green, and the number you produce is simply
answering a different question than the one you will report.

## AN EXACTNESS GATE IS ONLY AS WIDE AS THE STATE DISTRIBUTION IT RAN ON (line M, 2026-08-11, ADR 0124)

A port that reproduces the reference **exactly** — 0 exceedances, max relative Δ 1.7e-15 — was gated on
**one trajectory**: the recorded run's own states. The moment an arm was run whose whole point was to behave
differently, it visited a state region with **7× the rate of one hard-kill branch** that the gate had barely
sampled. The port held there, but that was luck until it was measured, and the check is one command.

So: **an identity/exactness gate is a statement about the states it saw, not about the function.** When you
introduce an arm, a flag flip, or any change whose purpose is a different trajectory, **re-run the gate on
that arm's own output** before crediting the arm with anything. Cheap, and it separates "the operator is
exact" from "the operator is exact where we happened to look". The same reasoning applies to a fixture: a
committed reference sampled from one regime does not gate a second regime.

## A GLOBAL REFERENCE IS NOT A PER-CELL ACCEPTANCE TARGET — SCORE THE TRUTH AGAINST IT FIRST (ADR 0124)

A committed fixture held FIT's per-PFT age–trait gradient over **all 54 020 cells**, and a prior ADR said to
test a new operator's gradient SHAPE against it. Done at one cell, that test **fails FIT itself**: the C's own
recording at cell 42490 scores Spearman ρ of −0.500 / −0.314 / +0.400 / −0.500 / +0.800 against the global
fixture, because one cell is a different population (its own PFT set, its own age structure, ~10⁴ stems not
10⁷). An arm scored that way would have been rejected for reproducing the truth.

**The check that costs nothing and settles it: put the TRUTH's own row through your scorer.** If the reference
you are scoring against cannot recognise the reference implementation, it is the wrong reference for that
scope — and printing the truth's row makes that a measurement in the output rather than an argument in a
review. Then pick the like-for-like basis (here: that cell's own recorded run) and keep the global fixture for
the global claim.

## MATCHING A CONSTRAINT EVERY STEP DOES NOT MEAN REPRODUCING THE QUANTITY IT CONSTRAINS (ADR 0124)

Two arms were handed **identical count targets, in expectation, in every one of 500 steps**, and both drew
unbiased (579 vs 581.6 expected; 1 096 vs 1 105.9). They ended **1.05× and 1.21×** on that very count.
The constraint was state-dependent: the arm that satisfied it *badly* (sparing the individuals the reference
condemned) raised its own future target, so it removed **twice as many** individuals in total and still
finished denser.

Generalisable: **when a target is computed from the state the operator is changing, honouring it pointwise is
not a conservation law.** Before reading a ratio as "the constraint held", check whether the constraint's own
inputs are downstream of the operator — and report the constrained quantity's *composition* (here the age
structure, and the identity overlap with the truth's own individuals), because a scalar ratio hides two
compensating errors as easily as it shows one.

## A COMMENT SAYING AN OMISSION IS DELIBERATE IS A CLAIM, NOT EVIDENCE — AND CHECK **BOTH** SCENARIOS' BASIS (line S, 2026-08-12, ADR 0171)

Three generalizable moves, each of which changed a conclusion.

**1. The reference-basis audit must cover every scenario, not the one with a committed fixture.** A single-cell
builder gated its **historic** conditioning boundary against a committed fixture and passed for weeks; its
**ssp370** boundary was never gated against anything, and was a different quantity from the trained table for
**19 of 81 years** (up to +10.7 % and +1.94 °C). The asymmetry survived because the gated half is the half a
fixture existed for. ⇒ enumerate the *bases*, not the *fixtures*: one gate per (scenario × conditioning axis),
and if a global table exists, gate against **the table the model was fitted on** rather than a derived fixture.

**2. A code comment that explains why something is deliberately absent is exactly where to look.** The
offending line read *"X accepts the short window … so replicating it is what keeps this fixture consistent with
the basis the artifacts were TRAINED against."* It named a checkable claim about another script — and reading
that script showed it did the opposite (it averaged over the whole file from its own first year). Rule: **a
comment asserting consistency with a reference is a test you have not run.** Grep the reference, don't trust
the prose; a confident justification for an omission is a stronger signal than no comment at all.

**3. Before attributing (or panicking about) a defect's impact, find the model's own CHANNEL-LIVENESS
diagnostic.** The arm prints `max |Δ output|` between a transient and a static conditioning input under
identical forcing. It read **exactly 0.0** on the artifact every published number used — that artifact's
boundary axes are constant in training, so no split exists on them and the channel cannot carry anything — and
**2022–2406** on the production artifact. That one line converted "how much did every past number move?" into
"provably zero, and here is the 40-seed reproduction to the digit", and localised where the defect *would*
have bitten. ⇒ when a conditioning input turns out wrong, the first question is not *how wrong* but **whether
the consumer can see that input at all**; a learned model trained on a constant is blind to it by construction.

**And the corollary for impact statements:** where the channel *was* live, the same fix moved the arm by
**0.03 ×FIT against a 0.32 ×FIT SEM** — an order of magnitude below the ensemble's own precision. Quote a
defect's size against the measurement's own noise, and keep the off-basis arm as a **named control** rather than
deleting it (`BND_FIXTURE=` + an `ALLOW_…=1` escape hatch that prints which basis it wrote), or the before/after
comparison becomes unrunnable the moment you fix the bug.
## A BOUNDED STOCK'S DRIFT IS A LOWER BOUND ON THE RATE ERROR DRIVING IT (line M, 2026-08-12, ADR 0125)

A decade of "the canopy drifts +27 %" was being read as the size of the fast core's growth problem.
Measured at the level the model actually computes — one stem, one year, restarted from the reference's own
forest each year — the per-year growth error compounds to **20.4×** at the cell whose free-running drift is
**1.67×**. The free-running number is smaller because the quantity **saturates**: crown area is capped,
cover is bounded by 1, and light competition closes the stand. Nothing about it is closer to correct.

- **Score the RATE, not the accumulated stock, whenever the stock has a ceiling** (cover fractions, LAI,
  anything normalised, anything with a `min`/`clamp` on its path, any state with a negative feedback).
  Ask: *can this quantity express the error I am attributing to it?* — the sibling of §3e's "ask whether
  that assertion CAN fail".
- **The fix is usually a restart arm, and it is cheap.** Re-initialise the model from the reference's own
  state every step and score the one-step increment. That also splits a per-step bias (it reappears every
  step) from something the free-running loop manufactures out of its own accumulated state (it does not).
- **A stable per-step error with OPPOSITE SIGNS across cells is a parameter, not a physics gap.** Here the
  per-step error was 1.6–4.0× too fast at three cells and *negative* at two — and a single per-PFT constant
  the emulator holds as one scalar (`respcoeff`, 0.2 tropical vs 1.2 temperate/boreal in the C) explained
  the whole tropical half. **Before attributing a per-cell flux/growth gap to physics, check whether the
  parameter is per-PFT in the reference and your code is using one value for all of them** — and test it as
  an ARM. The arm's own control is the cells where the substitution is a no-op by construction: if they
  move, the arm is doing more than one thing.
- **Decompose "flux in" from "flux kept" before choosing a lever.** The reference emits per-stem annual NPP,
  so `input_F/input_C` and `kept = Δstock / input` separate photosynthesis+respiration from
  allocation+turnover in one table with no new run. Here they were *different defects in different cells*:
  input right and `kept` 1.85× at boreal, input negative at the tropics.

## A "ONE-VARIABLE" ARM THAT SILENTLY CARRIES A SECOND CHANGE IS WORSE THAN NO ARM (line M, 2026-08-12, ADR 0126 §5)

**What happened.** Arm P (per-cohort PFT parameters, nine at once) made two of five cells worse, so it was
decomposed into one-field arms — the right move. Every one-field arm was built by constructing the core with
the real per-stem PFT ids **plus** one field's per-PFT value. But `pft_ids` also selects each PFT's own GSI
**phenology**, which the baseline arm (no `pft_ids` at all) did not have. So every column of the first
attribution table carried the phenology change as well, and the table credited it to whichever parameter
happened to be in that column: `respcoeff`, `alloc`, `allom` and `traits` all read *the same* 1.026 at the
boreal cell against a baseline of 1.049, and the Sahel read 0.557 in four columns whose fields are beech's
there. Every one of those numbers is a phenology effect wearing another parameter's name.

**The tell, and it is cheap to look for.** *Several arms that should be exact no-ops return the same value,
and it is not the baseline's.* A one-field arm at a cell where that field already equals the default MUST
reproduce the baseline exactly. If a batch of them agrees with each other instead, the common difference is
the confound — look at what the arm's construction turns on besides the field.

**The rule.** For a decomposition arm, name the switch you flip and then ask what ELSE that switch controls:
a constructor argument, an id vector, a `!== nothing` branch that has more than one consumer. Then add the
**switch-only baseline arm** (all fields at the default, the switch on) and difference every column against
*that*, not against the untouched control. Two arms, one extra run, and the attribution becomes real.
`scripts/biome_canopy_growth_probe.jl`'s `:phen` subset is that baseline; its header says in so many words
that the columns are read against it and not against arm `A`.

**Second finding from the same check, worth generalising:** the confound was a REAL PRE-EXISTING GAP, not
just noise. Beech phenology for the larch and the tropical evergreen moved the Sahel's assimilate ratio by
+1.01 and the Mediterranean's by +0.38 — larger than most of the parameters under test — and it had been in
every five-cell F number for months because the probe never passed an argument that already existed. **When
a decomposition uncovers a confound, measure it and report it as a result; do not just subtract it out.**
---

## A ONE-SIDED ERROR AGAINST A NET-SIGNED TRUTH RECTIFIES — so a LEVEL gate can pass BECAUSE OF the error that fails the RESPONSE gate (line S, 2026-08-12, ADR 0174 §3b)

The most consequential compensating error found in this project is not a cancellation between two terms. It is
a **rectification**, and it is invisible to every symmetric diagnostic:

* the count recursion follows **86.7 %** of a large FIT decline but **96.2 %** of a large increase (ADR 0116);
* FIT's global count response is a **net loss**, so the asymmetry does not average out over cells — it
  rectifies into a **systematic positive drift of +0.155 stems/patch, saturating** (ADR 0114);
* that drift is **the same size as FIT's entire global count response** (≈ −0.14 stems/patch);
* and it is **small enough to sit inside the level tolerance** (bias < 2 % of the mean against a 6.8–16.6 %
  two-run floor) **while consuming the whole response signal**, flipping the area-weighted ratio
  +0.707 → −0.226.

**The reusable shape.** Whenever a model is scored on both a level and a response, and its per-case error is
**asymmetric in the direction of change**, check the *sign structure of the truth* before concluding anything
from the level. If the truth's aggregate response has a net sign, an asymmetric error becomes a bias in the
response with no corresponding failure in the level — so the level result is not independent evidence, it is
partly a *consequence* of the response defect. Two operational rules follow:

1. **Resolve the error by the direction of change, not just by magnitude.** Bin cases into "truth went up" and
   "truth went down" and report the follow-through fraction in each. A single RMSE, R², or aggregate ratio
   cannot see this. (`scripts/rung1_drift_attribution.py` does the decile version.)
2. **A proposed fix must show the deficient side improving WITHOUT the other side's magnitude rising**
   (ADR 0116 §5's pre-registered form). An aggregate ratio alone cannot distinguish a real fix from a new
   compensating bias on the other side — it will happily reward one.

## AN ARM'S ADVANTAGE MAY BE A DUPLICATION OF SOMETHING ITS TRAINING TARGET ALREADY CONTAINS (line S, ADR 0118 → 0174 §3c)

Before believing that adding a mechanism improved a learned component, ask **what the training target was
fitted on**. The recruit copula's marginals are fitted on FIT's *survivors*, so they already carry the
trait-dependent selection that switching on a mortality operator proposes to add — **+12.18 % on Wooddens
within a cell-PFT group**, of which 0.56 does not cancel in a response.

The trap has a specific shape that makes it worse than a plain bias: **it lands on the arm and not on its
null.** A trait-*blind* null (uniform thinning) is unaffected, because that is precisely the design the
survivor marginal was matched to — so the duplication goes straight onto the headline `arm − null` difference.
A symmetric-looking A/B comparison is therefore not protection. Check the target's fitting population, and
check whether the ADR that chose it wrote an expiry condition (ADR 0025 §3 did; four later ADRs missed it).

## THE THREE-QUESTION CHECK BEFORE BELIEVING ANY LEARNED-COMPONENT ARM (line S, 2026-08-12, ADR 0174 §5.3)

Rung 1's exit verdict makes this a standing rule rather than a per-case observation. For any new arm:

1. **Name its null** and score the null in the same process (ADR 0112). A metric the null also passes has no
   power — measured: three arms spanning R² 0.982 → 0.918 and a response ratio spanning +0.707 → **−0.226**
   all score the per-cell deattenuated count slope between 0.976 and 1.029.
2. **Check the statistic's own noise floor**, by simulating data that genuinely satisfies the model being
   tested. ADR 0093 §5.3's published Beta figure (0.0437–0.0476) sat *at* its own one-sample statistic's floor
   (0.0434–0.0475 at n = 150) and so could not have detected the misfit it was quoted as measuring (ADR 0173).
3. **Check for duplication** of what the training target already contains (previous section).

And when quoting: **label every number *level or response* and *one-step or free-running*.** Those four
combinations have different verdicts, and three of the four have been quoted interchangeably in this repo's
own history.

## A RATIO WHOSE DENOMINATOR IS ALSO WRONG RE-EXPRESSES THE NUMERATOR'S ERROR — SCORE THE ABSOLUTE IDENTITY (line M, 2026-08-12, ADR 0127)

§2c says decompose a residual algebraically before sweeping anything. This is the sharpest instance found
here, and it cost two ADRs pointing at the wrong subsystem.

**The shape.** You split an error into "how much comes in" and "what fraction of it is retained"
(`keep = Δstock / flux_in`), find the input right at some cells and the *fraction* wrong, and conclude the
retention machinery is broken. That inference is only valid if the LOSSES scale with the input. Here they
do not: a summergreen sheds its whole leaf pool and its fine-root pool every year regardless of that year's
NPP, so the losses are **stock-driven** while the input is not — and a too-large input mechanically raises
the retained *fraction* with a perfectly faithful allocation. Measured: F's absolute litter + reproduction
flux was right to **1.8 %** (262.1 vs 266.8 gC/m²/yr) at the cell whose `keep` ratio was **49 % high**.

**The fix, and it needs no new run.** Write the conservation identity of the quantity and difference the
two sides term by term:

    Δstock = flux_in − loss − Δ(other stocks)
    ⇒ Δstock_model − Δstock_truth = (in_m − in_t) − (loss_m − loss_t) − (other_m − other_t)

Three named, **exactly additive** channels in absolute units. At the prototype cell they came out 77 % /
3 % / 20 %, i.e. the item two decision records had named "the binding gap" was 3 % of it. Report the
channels; keep the ratio only as a derived column.

**Two guards that go with it.**
- **A mean of per-year ratios is not a retained fraction when the denominator changes sign.** The published
  panel used `mean_y(Δ/flux)`; at the cell whose annual assimilate crosses zero that read **+0.350** where
  the ratio-of-means is **−0.059**. Both definitions now print side by side (ADR 0060) and the sign-changing
  one is reported as undefined, not as a number.
- **When you add a second reader of the same fixtures, gate it on reproducing every published number first.**
  It failed on the first attempt — and the failure *was* the finding above, because the only two things that
  differed were the ratio definition and the reference used for the start state.

**And check whether the "other stocks" term is even the same object on both sides.** Here it was not: the
reference's below-ground bucket holds fine roots **plus two woody pools the model does not have**, which is
why that channel was non-zero at all. Read the accumulation expression in the source for both sides
(§3f) before differencing — a term that exists on one side only is a finding, not a bug in the comparison.

## A NULL FROM AN UNDERPOWERED TEST IS NOT A NULL — PRICE THE TEST BEFORE READING IT (line M, 2026-08-12, ADR 0129)

ADR 0174 §5.3 says check a statistic's own noise floor. This is the cheapest possible instance, and it
sat one sentence away from a published wrong conclusion.

**The shape.** You have a mechanism that predicts a regression slope of exactly +1 (or exactly 0). You fit
it, it looks decisive, you suspect the fit is really two shared decadal trends, you refit on the
**detrended** series — the honest move — and the slope collapses to ~0. The reflex reading is *"refuted"*.

**It usually is not, and the check is four lines.** Detrending is not free: it removes most of the
regressor's variance, and whether anything is left depends on how smooth the regressor is. Here the
regressor (a slowly-drifting population share) had a detrended residual spread of **0.0102** in log while
the response carried **0.0134** of weather-year flux noise ⇒ **SE(slope) = 3.63**. A test with a standard
error of 3.6 cannot distinguish a slope of 0 from a slope of 1 — its point estimate of 0.22 carries no
information at all, in either direction. Two of the other four cells were at SE 41.8 and 5.3.

    SE(slope) ≈ sd(resid_y) / (sd(resid_x) · sqrt(n − 2))

- **Print `sd(resid_x)`, `sd(resid_y)` and `SE(slope)` in the same row as every detrended fit.** Without
  them a collapsed slope is unreadable, and it will be read as a refutation because that is the shorter
  sentence.
- **State the answer as the BRACKET the underpowered test failed to narrow**, with both endpoints and
  what each assumes. A bracket that straddles the verdict is a result; a point estimate picked from one
  end of it is not.
- **Then name the measurement that would close it** — and prefer one that changes the *reference* over
  one that adds another arm to the model. Here no emulator experiment can ever separate the two channels,
  because the ambiguity lives in what the reference model writes out.

## WRITE THE PREDICTION INTO THE HARNESS BEFORE THE ARM RUNS — AND CHECK WHETHER A "SIGNED" EFFECT IS ACTUALLY CONDITIONAL (line M, 2026-08-12, ADR 0131)

**The trap.** A defect had been on the queue for weeks with its direction stated as settled — two
independent design notes said *"fixing it ALONE would push CUE further from the C"*, and a third note
inherited the sentence. Both were reasoning from the mechanism, not from a measurement, and **both had the
sign wrong**, because the effect is not signed at all: it is *conditional on a state variable neither note
named*. The gate scales net daytime assimilation `A = gpp − rd` by a factor in `(0,1]`, and
`npp = A − rmaint − rgrowth(A − rmaint)`, so gating **raises** `npp` exactly where the ungated `A` was
NEGATIVE and lowers it otherwise. The notes had silently assumed every affected day is one of the
pathological ones. Measured, the affected days were carbon-POSITIVE at one cell and negative at another —
the fix helps at three of five cells and hurts at one, and no single sign statement is true.

**The two habits that turn this from an embarrassment into a result.**

1. **Write the prediction, with its reasoning, into the probe script's own comment block before the arm
   runs** — not into the ADR afterwards. Then the failure is dated and attributable, and the ADR can report
   *which* clause failed and *why*, which localises the error to one unstated assumption. A prediction
   recorded after the numbers exist can only ever confirm.
2. **Before believing any "this fix pushes X in direction D" claim, write the effect as an expression and
   ask what it depends on.** If the sign depends on the sign of an intermediate quantity, the claim is a
   claim about the *distribution of that quantity*, i.e. about the cells — so it needs a per-cell
   measurement, and a word like "rare" in the original note is a statement about the CELL, not about the
   model. At a semiarid cell the "rare" days carried the entire sign of the annual carbon balance.

**Corollary for attribution records.** When one arm fixes a defect at two cells, do not write that the
defect has one cause. Here an earlier record grouped two cells under a per-parameter defect; the new gate
flips one of them on its own and leaves the other untouched, so that cell had **two independent sufficient
causes and the record stated one of them as the one**. Test each candidate cause against each cell
separately before grouping them in a sentence.

---

## §8 — CHECK THE INITIAL CONDITION, NOT ONLY THE REFERENCE DATASET (ADR 0132, 2026-08-13)

The "confirm the comparison basis" rule (§3) is usually applied to the *reference* side — which C output,
which population, which units. It applies just as hard to the **state the model starts the step from**,
and that failure mode is quieter because nothing looks wrong: the arm runs, the harness gates pass, and
the new mechanism simply reports **exactly zero effect**.

**The case.** F's below-ground wood pool is pinned by the C to a demand `D` computed on the *post*-turnover
sapwood, and the following year's turnover takes `r = turnover_sapwood` off it again — so a stem entering
a year holds `(1−r)·D`. The design note seeded it at the bare `D`. With that seed the post-turnover pool
and the recomputed demand are **equal**, so the annual top-up computes as identically 0: the port was
inert, and the probe would have measured its own seeding convention. The seed was wrong by **4 %** and that
4 % *was* the entire mechanism. Fixing it took the top-up from **0 of 272** stems to **205 of 272**.

**The generalisation, worth checking before any mechanism arm is scored.**

1. **A quantity defined as a year-over-year DIFFERENCE OF STATE cannot be measured by a harness that
   re-initialises from truth every year** — unless the initialisation is built from the *previous* step's
   truth. Year-paired probes (this repo's rung-3 alignment A) are exactly that kind of harness. Ask: *what
   does this state variable equal at the start of the step, in the C, expressed in quantities my fixture
   actually carries?* If the answer references a different year's fixture, read that fixture.
2. **Derive the closed form before running the arm.** Here two lines of algebra — the demand is linear in
   sapwood at fixed height, and the pipe model fixes `sapwood/height` in terms of leaf carbon — give
   `D = c·leaf·sla·wooddens/k_latosa` and hence "the sink is paid on the growth of the LEAF pool". That
   single sentence predicts the zero, explains it, and tells you what the seed must be. A closed form is
   cheaper than a 15-minute SLURM arm and it makes a null result interpretable instead of ambiguous.
3. **An exactly-zero effect is a red flag, never a result.** Physical mechanisms give small numbers, not
   `0.0` on every one of 272 stems. If an arm reports exact zero, suspect an identity in the setup before
   concluding the mechanism is negligible.
4. **The seed is part of the OPERATOR, not part of the setup.** Two arms that differ in a seeding
   convention are different physics, so never compare a statistic across a seed change without saying so —
   and keep the old convention available on the old arms so the published numbers stay reproducible.

**Corollary for pre-registration.** A pre-registered pass criterion can be internally inconsistent with the
document that sets it: ADR 0127 §6 required this mechanism to close a channel its own §5 had already
measured it explains 11 % of, at that cell. When writing a criterion, cross-check it against every number
already in the same document — otherwise the arm is graded against a bar its author's own data refutes.

---

## A "RESPONSE" MEASURED ACROSS TWO LEGS OF DIFFERENT LENGTH IS DRIFT UNTIL PROVEN OTHERWISE (ADR 0177 → 0178)

The shape: you compare a model against truth in regime A and regime B and report the CHANGE, `B − A`, as
the model's sensitivity to whatever distinguishes them. **If leg B also runs longer than leg A, `B − A` is
the sensitivity PLUS the extra free-running drift**, and a model with *zero* sensitivity still posts a large
number. Measured cost of not catching this: an emulator's warming response was first reported as
through-origin slopes of 1.33–1.48 (i.e. "over-responds by ~40 %") across 12 cells; with the drift removed
the drift share turned out to be **94–100 %** and the real sensitivity slope was **−0.03 to +0.04** — not a
too-strong response but **no response at all**. The two readings imply completely different next work.

**The fix is a THIRD arm, not a correction term.** Rerun leg B with the *driver under test* frozen at its
leg-A value, everything else identical — same initial state, same seeds, same length. Then

```
sensitivity = B(driver live) − B(driver FROZEN)      drift = B(driver FROZEN) − A
```

and the two are separated by construction rather than by an assumption about how drift accumulates.

Three rules that made this work, all cheap:

* **Pick a null whose sensitivity term is zero BY CONSTRUCTION, and check it first.** Here the persistence
  null never consults the learned model, so freezing the model's input cannot change its answer — and it
  returned **exactly 0.000 at every one of 12 cells**. That is what licenses reading a small non-zero
  elsewhere as real instead of as harness noise. A control you cannot predict the answer to is not a
  control. (Same discipline as this skill's "build the null that is handed the same thing and learns
  nothing" rule — here the null validates the *instrument*, not the claim.)
* **Report the drift SHARE, not just the decomposed terms.** `|drift| / (|drift| + |sensitivity|)` is the
  one number that says whether the original headline was measuring anything.
* **Do not read per-cell ratios once the numerator collapses.** With a sensitivity of ~0.1 stems over
  denominators of ~0.2, individual `sensitivity/truth` ratios reached ±2.5 on pure noise while the pooled
  slope was ~0. Quote the across-cell slope and the share; list the per-cell ratios as diagnostics only.

**Generalisation:** the same trap fires whenever the two arms of a comparison differ in ANY dimension that
accumulates — leg length, spin-up, number of update steps, sequence length. Before reporting a difference
as a sensitivity, ask *what else grows between the two arms*, and freeze the driver to find out.

## INTERROGATE THE FITTED FUNCTION BEFORE RETRAINING IT — liveness panel, scale anchor, secant (line S, 2026-08-13, ADR 0179/0180)

When a learned component shows no response to a driver, the reflex is to retrain. Two short jobs on the
**artifact you already shipped** can locate the defect first, and one of them nearly always changes the
sentence you were about to write.

**1. THE LIVENESS PANEL, FIRST, PRINTING EVERY FEATURE.** Count the ensemble's splits per input and print
`NO SPLITS` explicitly for any zero (ADR 0171 §3). This is one pass over the trees. In ADR 0179 it did NOT
end the investigation — it *prevented the wrong write-up*: "the model never learned climate" was about to be
recorded as "there are no splits on it", and the forest splits on those two features **77 440 times, 10.20 %
of all splits**, thresholds spanning the whole training range. The channel was wide open and empty, which is a
different defect from a closed one and has a different fix. The feature that *did* read 0 splits was the one
deliberately held constant — so the panel also proves a designed-out input is designed out (ADR 0107).

**2. A FLAT RESULT IS UNREADABLE WITHOUT A LIVE-CHANNEL SCALE ANCHOR.** "0.057 stems" means nothing on its
own. Move a feature *known to work* by its own observed shift, over the **same rows, through the same code
path**, and report the ratio: 0.057 against 1.278 = 4.4 % is a finding; the bare number is not. Do the same
against the reference's own response magnitude so the fraction is in the deliverable's units.

**3. USE AN OBSERVED SECANT, AND CHECK IT CLEARS THE QUANTIZATION STEP.** A tree ensemble is piecewise
constant, so an infinitesimal step returns 0 for almost every row (ADR 0105). A secant fixes that — but it can
*still* return exactly 0 when the observed shift is smaller than the bin: two cells in ADR 0179 read
`0.0000` because the split thresholds sit at half-integers (the target is an integer count) and their shifts
stayed inside one bin. **An exact zero is a red flag, never a result** (ADR 0132 §3). Check which direction it
biases the conclusion and say so — there it deflated the anchor, i.e. it flattered the channel under test.

**4. SEPARATE THE POOLED (BETWEEN-GROUP) FROM THE OPERATIVE (WITHIN-GROUP) SWEEP — a pooled global fit will
learn the driver as a GROUP IDENTIFIER.** This is ADR 0118's rule applied to partial dependence, and it is
the hypothesis a naive full-range sweep gets wrong: a model fitted across 58 588 cells is certain to split on
climate as a *location label*, so a full-range sweep can look steep while the within-cell response is zero —
which reads as "the model has it, the loop is broken" and sends the work to the wrong place. Emit both panels
from one script, plus a **local** full-range sweep on each group's own rows, which distinguishes "flat here"
(a plateau between two splits) from "flat everywhere".

**5. PRICE THE RETRAIN AS A ONE-VARIABLE ARM, AND NEUTRALISE IN PLACE RATHER THAN DROPPING.** To test whether
feature *k* is starving the others, overwrite column *k* with a constant instead of removing it: the feature
count, the column indices and `mtry` stay identical, so the only thing that changes is the information it
carries (ADR 0126 §5 — name the switch, then ask what else the switch controls). Retrain the **control in the
same process on the same rows and seed**; comparing against a shipped artifact confounds the row set with the
ablation. Two basis checks before reading either arm: reproduce a published statistic of the table (the
persistence null's R², here 0.9623 vs a published 0.9622) and reproduce the shipped artifact's own behaviour
(split share 10.10 % vs 10.20 %, R² 0.9801 vs 0.9824).

**6. READ THE ABLATED MODEL'S SKILL, NOT ONLY THE EFFECT YOU WERE TESTING FOR.** The most consequential
number in ADR 0180 was incidental: with the suspect feature removed entirely, R² was **0.9620 against the
persistence null's 0.9623** — i.e. the remaining features reconstructed the target as well as the lagged truth
did, so removing the suspected leak did not de-leak the target at all. That reframed the defect from "one
feature is hogging the signal" to "the target is nearly determined by the state description it is conditioned
on", which is a different and more expensive problem. **Ask what the ablated model still knows and where it
knows it from** — a *contemporaneous state* feature can be as much of a leak as an explicit lagged one, and
whether it is a leak at RUNTIME depends on who computes it there (in this repo those features come from the
fast core's own pools, so they are not).

**And report a partial result as partial.** The measured factor was 2.85× on a channel that is 4.7 % of the
target, with no improvement in SIGN (7/12 → 8/12) — real, paired at 13 of 15 cells, and not a licence to buy
a global retrain (ADR 0105). Pre-register the threshold that separates "supported" from "partial" from
"refuted" in the script, before the run, and let it print the verdict.

Worked examples: `scripts/slow_climate_partial_dependence_probe.jl` (panels 0/A/B/C/D + verdict) and
`scripts/slow_nprev_ablation_probe.jl` (the one-variable in-place ablation + its two basis checks).

---

## A PARTIAL FREEZE PUTS THE UNFROZEN CHANNEL INTO THE RESIDUAL BUCKET — READ THE FROZEN FILE'S COLUMNS (line S, 2026-08-13, ADR 0181 §6)

The "third arm, not a correction term" rule (ADR 0177 → 0178, above) is right and it has a failure mode that
looks exactly like success. `sensitivity = B(driver live) − B(driver FROZEN)` is only the sensitivity of the
channel you actually froze. **If the driver reaches the model through more than one route and you froze one
of them, the other route's contribution lands in `drift` by construction** — and `drift` is precisely the
term nobody re-examines, because the whole point of the design was to discard it.

Measured cost here: a frozen-climate control froze the **4 boundary columns** the count model conditions on
(`--freeze` writes `Year,eco_diag_gdd_5,tas_cold_month,soil_depth,co2` and nothing else) while the other 11
features stayed live on a stand the reference model was still growing under transient warming. Its result —
"climate term ~0, drift share 94–100 %" — is a correct statement about the **direct** channel and was written
up, cited and inherited as *"no warming response reaches the model"*. Measured on the stand channel it had
folded into drift, that channel carries a through-origin slope of **0.994** against the reference's own
per-cell response. The wrong sentence had reached two later decision records and the line's working handoff
before anyone opened the freeze.

**The check, and it is one command:** `head` the file the freeze actually wrote (or `grep` the writer for its
column list) and compare it against the model's full input vector. Then, for every input NOT in that list,
ask whether the driver under test can reach it. Write the answer into the arm's own header.

Two corollaries:

* **Name the arm after what it freezes, not after the driver.** "frozen-climate" invites the reading
  "climate cannot reach the model"; "frozen-boundary-columns" does not, and would have prevented this.
* **A decomposition into (sensitivity, drift) is only exhaustive if the freeze is total.** When it is not,
  report a third named term — here `stand-mediated response` — even if you cannot measure it yet. An
  unnamed channel inside a residual is indistinguishable from zero, and will be quoted as zero.

## A PRE-REGISTERED THRESHOLD IS NOT A PRE-REGISTERED VERDICT — CHECK THAT THE EXPRESSION USES THE BLESSED STATISTIC (line S, 2026-08-13, ADR 0181 §4)

ADR 0104 says a pre-registered criterion needs the same basis check as a residual. This is the narrower,
dumber version of that failure, and it survived writing the thresholds down correctly.

The probe's header named the area-weighted aggregate as the binding statistic, printed a warning that the
per-cell slope is not it, and defined **both** pairs of thresholds as constants before the run. Its `verdict`
expression then branched on the per-cell slope alone — the statistic ADR 0112 had already proved has **no
power**, because the do-nothing persistence null scores 1.029 on it against the model's 1.006. It printed
`H_map SUPPORTED` (slope 0.944) for an arm the blessed statistic scores at 0.292, i.e. PARTIAL.

Nothing about the pre-registration was wrong. The *wiring* was. So:

* **Grep your own verdict expression for the variable name of the blessed statistic before you submit.** If
  it is not in there, the pre-registration is decorative.
* **If the blessed statistic is computed by a DIFFERENT job, the probe must not print a verdict at all.**
  Print the thresholds, print the diagnostic, print the command that produces the deciding number, and stop.
  A script that can only see a powerless statistic will use it.
* **Label a powerless diagnostic AT ITS PRINT SITE, not only in the header.** The header warning was there
  and was read past — the verdict line four rows below it is where the reader is.

## A SCRIPT'S DEFAULT OUTPUT PATH CAN BE A COMMITTED SHARED FIXTURE (line S, 2026-08-13, ADR 0181 §8)

CLAUDE.md §9 item 6 covers a script that hard-codes the *integrator's* repo path. This is the sibling: a
script whose default output is a **committed fixture inside your own worktree**, so running it looks clean —
no permission error, no foreign path, nothing in the log — and shows up only as an unexplained `M` in
`git status` that is easy to sweep into the commit.

`diagnose_truth_yardstick.py` defaults `OUT_SUMMARY` to
`test/testitems/references/S_truth_yardstick_summary.csv`, and a `COUNT_DIR`-only invocation **drops every
trait row** from it (66 deletions, 24 insertions). Regenerating a shared baseline is an integration point,
not a side effect. **Before running any analysis script, grep it for the repo-relative paths it writes**
(`grep -n "OUT_\|write_csv\|to_csv\|to_parquet" <script>`) and redirect them to `/p/tmp`; then `git status`
after the job and treat any modified tracked file you did not intend as a finding, not as noise.
## §9 — BEFORE PORTING A REFERENCE'S *BRANCH*, EVALUATE **BOTH** OF ITS BRANCHES ON THE REFERENCE'S OWN REALISED INPUTS (line M, 2026-08-13, ADR 0134)

§8 says derive the closed form before running the arm. This is its cheaper sibling, for the very common
task *"the C has a conditional and F only implements one side of it"*. The reflex is to port the missing
branch and measure what it buys. **Do the two-line check first: compute what each of the reference's
branches would return, over the reference's own realised per-stem inputs, and see whether they differ
at all.** A clamp, a `min`/`max`, a saturation or a threshold can make two textually different branches
**evaluate to the same number** over most of the parameter range the reference actually visits — in
which case the "missing" branch was never distinguishable and there is nothing to port.

**Measured cost of not doing it.** An item sat on line M's queue through **two handoffs**, framed as
cheap and well-localised: the C gates a full-leaf recycle (`leaf/1.05`) on a runtime latch and F applies
it unconditionally, so F "runs a summergreen recycle for the evergreen PFTs". The non-latched branch
drips at `1/max(pft->longevity, 1.05)` — and the `max` **clamps it to 0.9524/yr, exactly the latched
branch's rate**. Since 100.0 % of the stems at the target cell have leaf longevity below the clamp, the
two branches are the same number there and F was already exactly right. Stem-weighted, F over-shed
**0.3 %** of the leaf pool at the cell the work was aimed at. One parquet scan over the reference's own
per-stem output settled it and retired a planned state machine, a new per-stem field and an incidence
probe.

- **Score the branches in the units the CONSUMER sees, not the rate.** Here that is the leaf fraction
  *retained into allocation* (`1 − 1/max(L, 1.05)` vs `1 − 1/1.05`), because that is what enters the
  allocation solve. A rate difference can look large while the quantity downstream of it is clamped.
- **Report a per-cell (or per-stratum) `CANNOT BIND` / `CAN BIND` verdict, computed by the script.** A
  mean over the whole population hides exactly the heterogeneity that decides where to work: the same
  audit that gave 0.3 % at the target cell gave **24.8 %** and **12.4 %** at two others, which is the
  actual finding. Have the script print the verdict (ADR 0104's "have the SCRIPT compute the headline
  statistic").
- **Then check the incidence question is still live before promising it.** Which branch *fires* is a
  separate measurement from whether the branches *differ*. Where they do not differ, incidence is
  irrelevant and the item is dead **mechanically** — say so, so the next session does not re-open it
  with a probe. Where they do differ, the branch-difference is an **UPPER BOUND** and publishing a
  default or a parameter off it is the ADR-0105 error.
- **The dead-path check (CLAUDE.md §3 / guardrail 5) runs FIRST and is separate from this.** In the same
  case the conditional that was believed to select the branch (`phenology_tree.c`'s
  SUMMERGREEN/RAINGREEN/EVERGREEN switch) is **dead code** in the live configuration, *and* the parameter
  it keys on is uniform across all seven PFTs anyway. Three independent refutations, all readable from
  the source in under an hour: is the branch reachable · does its key actually vary · do the branches
  differ numerically.
- **While you are in the reference's per-stem output, check whether the parameter is per-INDIVIDUAL.**
  The same read established that leaf longevity is drawn per stem from the stem's own SLA
  (`new_tree.c:215` `corr_corridor`) and emitted as a column, *not* the per-PFT residence time the
  emulator stores — so a naive port of the branch would have used the wrong quantity (retaining 0.75
  where the truth is 0.44). ⚠ And a par-file `{mean, ...}` field is **not** the realised centre: the file
  said 2.0 yr where the realised median was **0.286**. Same shape as ADR 0047's interval-`"median"`-
  outside-`[low, high]`.

Worked example: `scripts/diagnose_leaf_turnover_regime.py` (variability audit first per ADR 0117, then
the retained-fraction panel with the decisive "fraction of stems past the clamp" column and the per-cell
verdict, then the trait-corridor check).

## A STATISTIC THAT THE DO-NOTHING NULL ALSO PASSES CANNOT CREDIT THE THING UNDER TEST (line S, 2026-08-13, ADR 0182)

ADR 0182 asked whether each rung-2 arm's own stand warms like LPJmL-FIT's. All three real arms passed the
pre-registered test — shift magnitude ≥ FIT's, direction agreement 0.76–0.91, and **0.97–0.99 in the cells
where FIT's own stand moves substantially.** Then the persistence null `NP`, which learns nothing at all,
scored **0.910** on the same direction test in the same cells.

The reason is structural and was knowable in advance: in a rung-2 arm **the C grows the stand** and the
emulator only decides who dies, so the stand's warming shift is *inherited*, and every arm inherits it. The
test therefore has exactly one power — it can **clear or convict** the hypothesis "the state handed to the
learned map does not move". It cannot rank the arms.

**Do this:** when you build a test around a quantity that a shared upstream also produces, score the
do-nothing null on the SAME statistic in the SAME cells, and write the null's number into the result table
next to the arms'. If the null passes too, say so in the headline and state which of the two things the test
can still decide. (Same shape as ADR 0112's deattenuated-slope trap, where all four arms scored 0.97–1.03,
and it recurs whenever a statistic is dominated by a channel none of the arms own.)

## A LEG-MEAN DIFFERENCE NEEDS A SAME-FORCING CONTROL, AND THE REFERENCE'S OWN DRIFT MAY BE THE LARGEST (ADR 0182 §4)

The companion to the drift rule already recorded above (ADR 0177 → 0178). Compute the SAME leg-shift
statistic **between two halves of one leg**, where the forcing does not change and there is no excursion to
find, and express both as a per-decade RATE (the half-leg centroids are ~10 yr apart; two legs' centroids
were ~50.5 yr apart, so the raw numbers are not comparable).

Two things this caught that the headline table hid:

* the arms' drift rate was 3.0–3.6× their warming rate — but **the reference's own was 5.39×**, the largest
  of all five arms. Reading the control against 0 instead of against the reference would have published
  FIT's own decadal variability as an arm defect.
* on absolute magnitudes the arms' within-leg decadal mobility (1.04–1.34) stood in the same ~1.5×
  proportion to FIT's (0.86) as their leg shift did ⇒ the arms' shift ratio of 1.6 was **mobility, not a
  stronger response**. "The arms warm 1.6× more than FIT" was one table away from being written down.

**Declare the control with the thresholds, before the run, and put the reference through it too.**

## TWO STATISTICS THAT SOUND EQUIVALENT — MASS SHARE vs DECISION SHARE — DISAGREED BY 4–10× (line S, ADR 0183 §4)

Pricing what a missing model input costs: LPJmL-FIT's drought and cold hazards carry **29–37 % of its graded
per-individual hazard mass** and only **3–9 % of its certain kills** (the decisions that actually remove a
tree). An input can dominate the continuous quantity and be nearly irrelevant to the discrete outcome the
consumer depends on. **Score the statistic the consumer consumes**, and if you report a mass share, report
the decision share beside it.

## ASK WHETHER YOUR PERTURBATION CAN MOVE THE METRIC BOTH WAYS — PRECISION WAS 1.0 BY CONSTRUCTION (ADR 0183 §4)

The same measurement reported recall 0.909–0.972 at precision **1.0000** for the zeroed-input arm, four times
over, which looks like a suspiciously clean result and is in fact a tautology: the four hazards are
non-negative and additive before a `min(1, ·)` cap, so zeroing two of them can only LOWER the total and a
stem certain under the zeros is certain under the real values. Precision carried no information at all;
recall was the whole measurement.

**Before quoting a precision/recall (or specificity/sensitivity) pair, check the monotonicity of the
perturbation.** If it can only move the metric one way, name the informative half and drop the other.

## CHECK WHICH QUANTITY A HARNESS ACTUALLY FEEDS ITS OWN TEST BEFORE BUILDING A BLOCKER ON IT (ADR 0183 §2)

ADR 0176 §4's entire pre-registered blocker for a flag flip rested on the rung-2 arms having used *FIT's own*
hazard, so that the port was unproven. `rung2_s_demography_harness.jl:539` reads `Tree.mort`, and that
field's own declaration comment (:206) says `TraitMortality.mortality_hazard` — **the port**. The harness
never reads the dump's `mort_prob` column at all. Only a nearby inline comment (:533) called it "FIT's own
hazard", and that comment is what got written into the ADR.

**Trace the field, not the prose around it** — declaration, then assignment, then use. A blocker that names a
specific input is worth ten minutes of grep before it becomes a milestone's gate.

## §10 — A COMMENTED-OUT BRANCH IS A DEAD PATH THAT `grep` CANNOT DISTINGUISH FROM LIVE CODE (line M, 2026-08-13, ADR 0135)

§9 says: before porting a reference's *branch*, evaluate both of its branches on the reference's own realised
inputs. This is the step before that one — **make sure the branch you are comparing against is compiled at
all.** Guardrail 5 and the `individual=true` dead-path rule are usually applied to a *config* gate
(`if(!config->individual)`); they apply just as hard to a `/* ... */` block, and that case is quieter, because
a config gate is at least visible in the same line of output.

**What it cost.** `getfpar.c:108-124` carries **three** expressions for one quantity (the stem leaf-area
density the layered-light integration runs on). A `sed` line range and a `grep` both surfaced a commented-out
variant. Scored against it, the emulator's light model looked 5–37× too optically thin, with the reference's
canopy fully opaque (absorbed fraction 1.000 at all five cells) — a dramatic, internally consistent,
cross-cell-reproducible finding that was one commit away from opening a rewrite of a **faithful** component.
Read verbatim in context, the live line matched the port exactly, cap and cap-ordering included.

- **`awk`/`sed` the ENCLOSING lines, not the matching one.** `grep -n` gives you a line; it does not tell you
  whether `/*` opened above it. Print ±10 lines and look for the delimiters. If a file offers several
  candidate expressions for one quantity, assume at most one is live until you have seen the comment
  structure.
- **Two or more variants of one expression in a file is itself a signal** — it usually means the reference's
  own authors experimented there, so it is exactly the quantity a port is most likely to have taken from the
  wrong copy. Say in the ADR which one is live and why.
- **The same file can hold a live/dead pair one level up.** Here the *function pointer* was also a pair:
  under `individual:true` the registered `fpar()` is `fpar_tree_ind` (the layered share) and `fpar_tree` (the
  crown-cover form) is dead — so `grep fpar_tree` finds a plausible, wrong definition too. Follow the
  registration (`fscanpft_*.c`), not the function name.
- **Then score the port against something the reference EMITS, not only against its source.** That is what
  makes the verdict a measurement: the port's patch LAI was checked against the run's own `LAI_STAND` output
  (0.87–0.98 at four of five cells, below 1 by exactly the known writer cut). Pick the output that constrains
  the quantity — the obvious-looking one here (`FAPAR`) is built from a *different* variable
  (`albedo_tree.c:75` uses `pft->fpc`), i.e. §3f's same-name-different-quantity trap.
- **Report the refutation, with the retracted number.** A future session will find the same commented-out
  line. Writing down "this is dead, here is the 5–37× artefact it produces" is what stops it being rediscovered
  as a finding.
