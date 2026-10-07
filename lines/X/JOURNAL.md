# LINE X — JOURNAL (append-only)

Narrative for line X only. Durable state: `lines/X/STATE.md`. Decisions: ADR block 0310–0329.
Newest entry at the bottom.

---

## 2026-08-19 — the line is created, and its first exploration is relocated into it

**Why the line exists.** The owner asked whether a *purely data-driven* emulator could replace the hybrid —
learn `(forest state, climate) → next forest state`, roll it out, plus a daily flux head for an ESM. The
question was put to **line O** (online coupling), which explored it, and the owner then corrected the venue
twice in quick succession:

1. *"no! stop! dont write anythign of this to other lines!!! we are jsut discussion a new direction of this
   project here, nothing to do wiht other lines!!!"* — issued while line O was mid-write of an INBOUND block
   into `lines/S/STATE.md` and about to append cross-cutting facts to `MEMORY.md`. **Both were abandoned; the
   `lines/O/STATE.md` edit was reverted with `git checkout --`.** Nothing reached another line.
2. *"you are also nto the correct person to discuss this with. relocate our whole discussion to a new line
   that is responisble for these project lever decisions and exploring new ideas."*

**What that diagnosed, and it is a real structural gap, not a preference.** The four component lines are each
mid-ladder on one subsystem. A question of the form *"should the architecture be different?"* therefore has no
owner: whichever line is asked must either act on it (wrong — not their call) or drop it. Line O's own
exploration illustrates the failure mode exactly — it produced a defensible finding and then, following the
capture discipline in CLAUDE.md §8 faithfully, immediately began pushing it into two other lines' state. **The
discipline was right and the venue was wrong.** Line X can hold an open question without pushing it at anyone.

**What was done.**

* **Line X bootstrapped complete**, so its first working session starts on content rather than plumbing:
  `lines/X/STATE.md` (charter — scope, the "does NOT do" list, owned paths, the four traps), this journal,
  branch `line/X`, worktree `/p/projects/open/Jamir/wt-X`, ADR block **0310–0329** allocated in CLAUDE.md §9
  (tier-2 reserved at 0330–0349), the row in `docs/decisions/README.md`, and `wt-X` added to the
  SessionStart hook's integrator hint list. The hook needed **no** code change — it is generic over `line/*`
  and resolves `lines/<letter>/STATE.md`.
* **ADR 0088 → ADR 0310, relocated before it was ever committed**, with a Status box quoting both owner
  instructions and stating plainly that nothing was raised with any line and nothing binds anyone.

**The finding itself** (full record in ADR 0310): the proposal is **six problems with six answers**. Daily
water/carbon = data exist, learnability untested. Daily **energy = impossible from this model, permanently**
(of 421 outputs, only monthly albedo + soil temperature are energy-adjacent). One-step operator = already
built, **96 % of its skill is the persistence null** (0.9622 of 0.9824). Century rollout = stable, but every
reason given for the stability was a piecewise-constant-forest artifact, and rollout training has never been
run here. **The warming response = not demonstrated, and zero positive evidence exists** — the one claim died
to a null nobody had run (a pure lat/lon address scores 0.654 of the 0.748 attributed to climate). Speed =
**≈0.0032 core-s/cell-year at fp64**, inside the strict convention with 4× margin.

**Method note worth keeping.** 6 investigations → 6 adversarial reviewers → synthesis → completeness critic
(14 agents, 2.66 M tokens). **All six investigations were refuted.** The reviewers killed five numbers that
would otherwise have been reported to the owner as measurements: a speed figure timed on arrays that had
overflowed to `inf`; a "210× faster than the C" comparison rigged against a configuration nobody runs; a
"needs 0.12 % level accuracy" bar computed on a global aggregate that appears in no acceptance criterion; a
cross-leg error correlation that was actually an 80-year within-chain memory decay; and the response-recovery
headline that fell to the geographic null. **The critic then found the single most important omission — an
architecture that is purely learned yet keeps the per-individual roster — which no investigator and no
reviewer had considered.** ⇒ the adversarial layer earned its cost, and the *completeness* layer earned it
twice; neither is optional on a direction question.

**Also corrected during the session, to the owner, unprompted:** my own earlier hypothesis that the flat
warming response was caused by conditioning on per-cell constants. **Refuted by measurement** — 13 of 15
inputs do vary between scenarios. The real cause is a target defect (the next-year count is 96 % determined
before climate is consulted), which survived review.

**Left open on purpose:** five investigator-vs-reviewer disagreements (ADR 0310 §10), the largest being
whether the measured −0.226 response inversion bounds a closed rollout from below or from above. Recording
them as disagreements rather than picking a side is the point of the line.

## 2026-08-19 / 2026-09-02 — round 2: the response verdict flips, and the campaign is half-finished

**What the owner asked:** *"continue the exploration of the efasability of a more data driven emulator."*
Note **more**, not **purely** — ADR 0310 had priced only the pure endpoint against the shipping hybrid, so the
middle of the spectrum was, and still is, unpriced.

**What was run.** A 16-agent campaign (`wf_5ba7e1aa-b45`): 2 scouts + 1 shared-table prep, 6 pre-registered
measurements each pipelined into an adversarial verifier, a spectrum synthesis, a completeness critic.
**11 agents completed** across three launches. It took three attempts — a session usage limit killed 10 of 11
on the first, transient 529s killed the three measurements on the second, and the limit took B1's verifier on
the third. Lesson worth keeping: **run a large campaign in waves and lean on `resumeFromRunId`** — trimming
`ITEMS` to `.slice(0, 3)` and deferring the synthesis meant nothing completed was ever re-spent, and the
per-call cache made the third launch cost only the three measurements plus two verifiers.

**The result, in one line: ADR 0310's headline verdict on the warming response is overturned, and the reason it
was wrong is the fold scheme.** A direct, non-autoregressive climatology → 20-year-window-state map — the
architecture ADR 0310 §4 listed as *"never considered"* — beats a coordinates-only null under spatially
blocked folds by **+0.162…+0.715** on a clean 20-vs-20-year response target, with climate *subsuming* the
address rather than proxying it, and the margin got **2–6× larger** when its verifier attacked it with three
independent address nulls instead of one. ADR 0310 had killed that claim on **hash folds** against a
**drift-contaminated 20-vs-81-year** target. So the first positive evidence in this project for the part the
owner actually cares about exists — while the same map sits at **7.2 %** of cells on the owner's conjunctive
per-cell basis and **loses to persistence** on the future state.

**The deepest finding was not on anyone's list.** Within a single emissions scenario, a cell's warming
increment is **76.4 %** linearly predictable from its own baseline climate ⇒ *"response to warming"* and
*"sensitivity of this place"* are **not separately identified**. Three independent consequences all agreed:
knowing the future climate adds nothing over knowing today's on 5 of 6 targets; the change-only arm carries
almost nothing; and a counterfactual with the warming scaled to **zero** still reproduces **76–110 %** of the
predicted per-cell change, while a structurally scenario-blind control returned exactly 1.0000 in 18 of 18
groups (so the probe was correctly wired). That single number is why the third forcing leg went from
nice-to-have to necessary — and the literature scout had independently established that only a **bracketed**
held-out design has ever succeeded anywhere in earth-system science.

**The adversarial layer earned its cost again, and in a new way.** Round 1's reviewers killed five numbers.
This round they *improved* one: B3's verifier found a 4-way inner join that silently dropped **4 635 cells with
no tree today and +6.455 stems/patch in the 2080s** — the poleward treeline advance, the model's single largest
warming response, 231× the mean of the cells that were scored. Repairing it took the response R² from 0.274 to
**0.529**. A verifier making a finding *stronger* by fixing a survivorship defect is a mode neither round had
seen. B2's verifier went the other way and refuted a magnitude: the growth target is one-step, and copying
last year's own increment with **zero parameters** returns **90.7 %** of the reported R² — so the honest span
is +0.0817, not 0.887, and the reported block decomposition understated the patch by 11× and climate by 10×.
**The correction ran against that item's own thesis and left it standing**, because the absolute climate
increment never moved.

⚠ **The process lesson is uncomfortable and is the highest-value thing here.** ADR 0310 §2(ii) wrote the
persistence rule down as a **STANDING RULE**, after a reviewer killed a headline on exactly it. **The very next
campaign violated it anyway**, having been instructed to read that record. A rule living in an ADR body does
not fire; it has to be in the pre-registration template the measuring agent fills in. Two sibling failures
recurred the same way: three of one item's five "surprises" were stale against records it had been told to
read, and one numbers row existed in **no log and no artifact** (the verifier reproduced most of it, found a
label error and one unreproducible figure) ⇒ anything tagged `[MEASURED]` needs a log line.

**Three corrections that belong to other lines were found and deliberately NOT propagated** (ADR 0311 §6;
propagation is the owner's call). The largest: **ADR 0125's per-stem cross-year identity key is wrong** — it is
`(Cell, Patch, PFT, ID)`, because the tree number is issued by a per-PFT counter. On the documented key the
identity gates **failed on every leg**; on the corrected key, **0 violations of 20.4 million consecutive-year
pairs on three independent checks**. The prep agent found it by taking the gate seriously instead of assuming
the record was right, and kept the failing job log as evidence. Anyone building a per-stem model on the
documented key would have been pairing trees that are not the same tree.

**Left deliberately unfinished:** the ssp126 bracketed held-out test, flux-state sufficiency, the closed
density-feedback rollout with a stochastic head, the spectrum synthesis, the completeness critic, and B1's
verifier. All queued in a resumable workflow; everything already done replays from cache. The purely
data-driven direction is **still not refuted and still not demonstrated** — but for the first time it has a
positive measurement on the response and a measured negative on the channel that would have to carry it.

## 2026-09-02 — a second exploration line: where the ORIGINAL model's time actually goes

**The owner's question, verbatim:** *"find out which parts of the original model consume most computational
time (e.g. photosysntesis or other processes). we can use this as basis for explorign soltutions where only
these processes are learned."* A good question and the sharpest version of the speed problem, because it turns
"learn everything" into "learn only what is expensive".

**Two decisions about method that made this cheap and safe.** First, the trap check: a partial C profile
already existed (ADR 0093, owner-approved — four inclusive shares) and the speed-gate harness already had an
unused `PERF=1` knob, so this was PARTLY DONE, not new. Second, and better: the **production binary already
carries debug symbols and is not stripped**, so `perf record` needs no rebuild — which matters a great deal,
because a rebuild moves the reference basis every C-vs-emulator number in the repo is measured against. So the
whole measurement was done by *invoking* line O's harness unmodified, with `ROOT` pointed at line X's scratch,
and a 108 MB profile from 14 August turned out to still be on disk — meaning the first complete answer came out
of **existing data with no model run at all.** Four biome runs then took eight minutes each.

**What the gates earned.** I wrote three pass/fail gates before looking at anything, and they caught two
parsing bugs in my own probe that would have produced a confidently wrong table: the math-library attribution
double-counted nested call-graph levels (inflating it from 25.4 % to 39.2 % — the completeness gate caught it),
and the inclusive parse silently keyed every symbol with perf's trailing columns glued on, so every lookup
missed and the agreement gate returned `n/a` at all five sites instead of PASS. A third gate — agreement with
ADR 0093's published inclusive shares — **passed at Hainich and missed at the other four**, and that miss is
the finding rather than an error: I had applied a Hainich-specific published number as a gate everywhere, and
the shares are genuinely biome-dependent. Recorded as a pre-registration miss on the gate's scope.

**The answer, and it is not what the framing expects.** The largest single process is the per-tree daily
assimilation/conductance kernel at 36–46 % of runtime — so making it **entirely free** buys **1.57–1.84×**,
against a requirement of ≈15–25×. The pre-registered falsifier for "learn only the expensive process" fired at
all five sites. After the top two processes the profile is genuinely **flat**: nothing else is worth more than
1.1× alone. So the strategy survives only as a portfolio covering ≥ 90 % of the daily loop — which is close to
a whole-daily-core replacement, not a surgical one. And every one of those ceilings assumes the replacement
costs nothing; at 20 % of the replaced cost, 1.84× becomes 1.56×.

⛳ **The strategically interesting number is the small one.** The entire annual demography — allocation,
mortality, establishment, turnover, the whole block the project's learned slow component replaces — is
**0.44–1.06 %** of the original model's runtime, with an Amdahl ceiling of 1.01×. The tempting reading is
"we have been learning the cheapest 0.6 % and keeping the expensive 98 % as physics". **That reading is
wrong, and getting it right is the contribution:** the demography's speed value was never its own cost, it is
that it **removes the patch tax**. Cost is linear in patch count, this configuration runs 25, and a component
that predicts the ensemble expectation converts a ~25× multiplier into 1 — a larger lever than every process
in the table combined. The reason nobody simply sets the patch count to 1 is fidelity, not speed. ⚠ I did not
re-measure that slope; it is ADR 0093's, and my own blocks disagree with its published per-patch-year value by
a factor ~1.4–2, unreconciled. That is the cheapest missing number in the record.

**Two targets fell out that are different in kind.** A quarter of the whole model (21–27 % of self time) is
`exp`, `pow` and `log` — an *engineering* target with no learning and no fidelity risk, and the same defect
class as the emulator's own 26.5 % in floating-point power (ADR 0084). And the λ root-find is the
best-posed *learning* target in the model: smooth, deterministic, scalar output, no state, no drift, unlimited
training data, sitting on the largest share (33.3 % inclusive) because of the up-to-30 photosynthesis calls it
makes per tree per day — with the caution that the gross flux is non-monotone in that solve's iteration count,
so its convergence cannot be assumed.

**Also worth keeping:** the marginal cost varies only 1.7× across biomes (0.1996 tropical to 0.3349 boreal
core-seconds per cell-year at 25 patches), and — against the obvious expectation — **the tropical cell is the
cheapest and the boreal one the most expensive.** The daily loop is 97.4–98.2 % of the run everywhere.

Meanwhile the round-2 data-driven campaign hit the session usage limit for a third time; B4/B5/B6, the
spectrum synthesis, the completeness critic and B1's verifier are still outstanding and still cached.


---

## 2026-09-30 — the owner asks why a data-driven transition emulator should be impossible, then says: build it (Germany)

Owner question (verbatim, abridged): *"I still can't believe that a data-driven emulator of lpjml-FIT that can emulate transient runs is not
possible ... given the forest state now and the climate of the next year, what is the forest like in the next year ... The most naive
emulator would be like a look up table ... what is the reason that it is not learnable? Do we need better data? more patches per cell?"*
Answered from ADR 0310/0311/0312: not shown impossible; partly learnable; the specific obstacles are the tiny per-year climate signal
under per-tree dice rolls, error build-up in free runs of one-step-trained models, the warming-vs-place confound from a single scenario,
and invisible state (sub-5 m trees, the bad-growth counter — recoverable). More patches helps the trait targets (whose two-seed
reproducibility is poor at 25 patches) but not the confound; designed climate variation does. The owner then pointed at the Germany
production runs (250 patches, 2 GCMs x 4 legs x 2 seeds) and instructed the build; see STATE `00✦`.

---

## 2026-10-02 (third session) — the free runs' extra recruits are the stand's fault, not the recruit model's

Picked up NEXT item (1). Pre-registered three readings (flicker of trees around the 5 m print threshold; an open
canopy honestly inviting recruits; a self-reinforcing input in the recruit model) and measured from the saved free
runs, no model run. Flicker is negligible. The original model self-thins — fewer, much bigger trees, a closing canopy,
recruitment falling by a third — while the tabular free run never matures. Deaths remove the same biomass in both;
the difference is that big trees grow 15–25 % slower in the free run. An input-swap test (rebuild the recruit model's
inputs from a roster, first proven identical to the stored training inputs on the original, then swap one group at a
time) put ~90 % of the excess on canopy cover alone. The cell-level stem density, my main suspect for a runaway loop,
pushes the other way. The gate earned its keep twice: it caught that the plain tree key has duplicates (the trait-
extended key fixes it), which would otherwise have shown as a phantom history mismatch in 2–6 patches per year.
Consequence recorded in STATE: do not let the free-run calibration absorb this into the recruit offset.

---

## 2026-10-02 (fourth session) — the free run's big trees grow slowly because its grass never dies back

Picked up the growth half of the drift. Pre-registered first that a one-step bias would have to be at least
0.004/yr to explain the gap; on the original's held-out states it is 0.000-0.0024, so the free run builds most of
it itself. Re-ran the tabular free run with an instrumented copy of the stepper (proved identical to the analysed
run, file for file) and paired every big tree with the same tree in the original. The deterministic growth chain
fed the free run's inputs loses 0.0029/yr against the same chain fed the original's; swapping one input group at a
time put it on the grass under the trees and on the place-wide stem count, with the tree's own shape and the patch
stand pushing slightly the other way. The grass is the striking part: in the original it disappears under a
maturing canopy, in the free run it creeps up, because the grass model is a mean regression applied year after
year and a mean can never reach zero. A counterfactual that replays only the original's grass closes 54-85 % of
the drift in stems, recruits, biomass, big-tree growth and cover. This also qualifies the earlier recruit finding,
which had held grass at the original's values. Next: a grass model that can collapse, tested in isolation first.

---

## 2026-10-02 (fifth session) — a grass model that can collapse; it fixes the 2030s, not the 1990s

Picked up NEXT item (1). First looked at what grass in the original actually is: one number per patch (leaf area),
with biomass exactly 23.67 x leaf area and cover following from leaf area unless the patch is full; it is bimodal and
very persistent on a log scale. So the new model predicts next year's log leaf area plus a residual drawn from its own
out-of-sample errors, and derives cover and biomass from it. Pre-registered a grass-only test (the original's trees,
only grass free, 907 places of a climate model the model never saw) with a falsifier: if the old grass model did not
drift on its own, the earlier diagnosis was wrong. It does drift (under big trees it holds 5 % cover where the
original has none). The new model passes every bar in the 1990s and misses one in the 2030s — it keeps too much grass
under closed canopy and too little in the open, i.e. it responds too weakly to tree cover. Coupled into the full
tabular emulator it closes 84-103 % of the 2030s gap in stem count, recruitment and biomass per stem, and about half of
the big-tree growth gap — better than the earlier "replay the original's grass" counterfactual, which turns out not to
be an upper bound because it paired the original's grass with different trees. But the 1990s-2000s are now wrong in
the other direction (too few stems and recruits, stems too heavy): the stand matures early and arrives at the right
2030s state by a different path, so part of the 2030s agreement is compensation. Next: find what drives the early
path, and tune the grass on a development set that is not the test.

---

## 2026-10-02 (sixth session) — the grass was smuggling in the young trees

Picked up NEXT item (1), the too-early maturation with the new grass model. The coupled runs already isolated the first
year: the tree rosters are identical across the emulator variants in 1986, and the new grass alone lowers 1987 recruits
by 12 %. Pre-registered and ran the same swap on the original's own trees for every year: the new grass lowers the
recruit model's output by 7-11 % until about 2005 and raises it after 2025, one step ahead as much as in a free run, so
nothing accumulates. In the patches carrying the gap the new grass has the right average cover and leaf area, which
pointed away from the grass amount. Replacing only the grass cover by the new model's cover rule, with the original's
own grass leaf area kept, reproduces the whole effect. The reason is that where the patch is full the original's grass
cover is whatever the trees leave, including the young trees below the 5 m print threshold, so it measures them; in the
original, recruits next year rise three- to four-fold with that squeezed-out cover, and it drains when recruits appear.
The recruit model learned to read it; any grass model with a closure rule erases it. The young-tree layer is a hidden
state the emulator needs to carry itself.

---

## 2026-10-03 (seventh session) — carrying the young trees, and what that exposed

Picked up the hidden young-tree layer. First tried the cheapest fix: let the recruit model stop reading grass cover.
That removes the bias, but costs 5 % of its skill on every scenario of the climate model it never saw, so the signal
is real. Putting last year's true hidden cover back recovers about 70 % of that, which is more than I had expected.
The reason became clear from the next model: total tree cover at all heights barely changes from year to year, and
the "hidden" share only looks noisy because cover moves to the printed side when a young tree passes 5 m. Built a
model of next year's cover cap that carries this. One step ahead on the original's trees it is close to perfect. A
grass-only free run fails, but that run feeds the carried state with the original's recruits, so it cannot test a
state that recruitment itself depends on. In the coupled emulator it fixes the early recruit shortfall, then
over-recruits by 15-27 % from 2006 on. A logged re-run showed why: in both emulator variants, grass leaf area stays far
too high after 2000, where in the original it falls by 60 %. The current variant's near-correct late recruitment was
two errors cancelling. Next: find what in the emulator's own trees keeps the grass from declining.

---

## 2026-10-05 (eighth session) — the grass excess is a climate-model transfer failure, not the emulator's trees

Picked up the open question of what keeps grass from thinning in the coupled emulator. The coupled run never saved its
grass, but the grass model carries its own state and the emulator's random numbers are keyed by place and year, so I
could replay the grass model along the emulator's tree history and reproduce its grass exactly (to a few parts per
million), then replay it along the original's trees. The guess I wrote down beforehand was wrong: the emulator's trees
account for about an eighth of the excess; the grass model on the original's own trees accounts for the rest. Swapping
single groups of tree inputs was uninformative, because after 1985 the same patch number holds different stands in the
two runs. One year ahead the grass model is roughly right in leaf area but, under closed canopy, too slow to let grass
collapse in a handful of warm bad years, and grass near zero stays there, so the misses ratchet. It does not do this
on the climate model it was trained on, with new trees, nor on that model's unseen medium-emissions years (where its
year-to-year error is larger but has no consistent sign), so it is a failure to carry its weather response over to
the second climate model; the bad years are mostly inside the training weather range. Re-running the coupled
emulator on the training climate model's second seed: grass stays within 13 % of the original, and carrying the
hidden young-tree layer halves the early recruit deficit with no late over-recruitment. The late over-recruitment on
ACCESS was the ACCESS grass. What remains on clean ground is on the tree side: stems get too heavy too early and too
few die in the middle decades.

---

## 2026-10-05/06 (ninth session) — the small trees were not growing too fast after all

Picked up the tree side of the early maturation. One year ahead, on the original's own states, the emulator's growth
and death models are nearly right; only small trees in the first decade grow a little fast. So the coupled run builds
its error from its own drifting inputs. Swapping inputs for the same tree between the emulator and the original
showed that the first-decade excess comes from the tree's own previous-year growth state, which the emulator draws
too high early on; the grass, which I had predicted, carries none of it. After 1995 the trees both runs share show
no growth excess at all. Splitting the small trees by whether they were there at the start or recruited later, and
by size, showed no mix effect either, and showed that the excess I had been chasing after 2000 was in the median
only: on average small trees grow at the right rate, the emulator just has too few very fast years. What is left is
the early growth-state drift and too few deaths of big trees in two decades.

The re-runs of the original that print every tree taught me something about the cluster: a run whose tasks land on
nodes of different processor types diverges from production from the first year, while every run on one processor
type reproduces it exactly. A prediction from the node lists alone got three of three right. All failed runs are
resubmitted on single nodes.

---

## 2026-10-06 (tenth session) — the early growth-state drift is in the shape of the random draw

Picked up why the emulator's trees start the 1990s with too high a growth state. The start is exact. One year ahead,
on the original's own inputs, the emulator's draw of next year's growth efficiency already has a median about 6 % too
high while its average is nearly right; letting it carry its own draws forward, with everything else held at the
original's values, doubles that to 13 %, which is almost all of what the full free run shows. So it is not other
drifting inputs. A direct calibration check (where each true value falls inside the emulator's predicted distribution)
showed what is wrong: the spread is about right, but the centre bends the wrong way with the tree's previous growth
state — too high for middling trees, too low for the fastest — and every year carries a common shift the weather
inputs do not explain, even though this member shares its weather with the training data. The fix is a model of the
whole distribution rather than a mean plus a pooled residual. The sapling re-runs of the original were cancelled from
the owner's account at 07:00 while waiting in the queue; the ones that had finished are collected and checked.

---

## 2026-10-06 (eleventh and twelfth sessions) — a model of the whole distribution for the growth state

Replaced the emulator's draw of each tree's next-year growth efficiency (an average plus a pooled leftover error) by
a model of eleven quantiles of it. On the held-out member it is far better calibrated (the share of true values below
its median ranges 0.47-0.53 across groups of trees, where the old draw ranged 0.29-0.67) and about a third sharper,
but it still misses my pre-registered ±0.02 band in a few groups. Its tails came out a little too narrow; a
standard post-hoc widening overshot slightly on the held-out member. The real surprise was elsewhere: the model that
decides whether growth goes negative was badly under-confident (where it said 3 %, the truth was 0.7 %), with errors
that cancel on average, which is why every earlier check called it right. A two-number recalibration fixes it per
probability band but leaves a growth-state-shaped error in the second decade.

Fed its own draws for twenty years with everything else from the original, the new model ends 4 % low where the old
one ended 14 % high: still outside my ±3 % bar. Every version amplifies its one-year error by about 2.3 when it
feeds on itself, so that bar needs about 1 % one-year accuracy. I ran the full emulator anyway, saying so beforehand,
because the chain test pairs the model's own draws with the original's growth history, a state the real emulator never
sees. In the full emulator the first-decade drift is gone, the overweight trees of 1996-2025 shrink to a third of
their excess, and stem counts stay within 1 % until 2025, which supports the last session's explanation. What is
left: the growth state now drifts low from 1995, too few big trees die in 2016-25, and biomass creeps 5 % high by the
2040s. It costs four times as much as before, so it needs shrinking before it can count for speed.

## 2026-10-06 — thirteenth session (x-8f): the other three designs; the quantile G model will not shrink

Owner: "work on the other emulator methods while this is running". The coupled gqs run sat queued on `standard`;
moved to `priority` it ran at once, and was scored twice by accident (this session and x-2f, who then handed the line
over) — the two scorings agree on every verdict. Three helpers ran in parallel: the quick cell-level LSTM (very good
cell statistics on held-out places and GCM, no transferable scenario contrast, no trees), the neural set model (built,
gated, stage 1 trained; its stage-2 gate has no power; recruits fall short for the same grass reason as TAB), and the
STRUCT diagnosis (the "2x biomass" was the median tree; the stem deficit is the missing recruit acceptance — a
training-member-only filter closes 106 % of it). I tried three pre-registered ways to make the quantile G model cheap
(truncation, residual start, distillation); all failed, and the distillation failure showed why: the model's per-tree
quantile shape is irregular (its raw levels cross in over half the rows). The cheap decisive test — does the coupled
model need that accuracy at all (coupled rq) — was submitted and then killed when every one of the owner's SLURM jobs,
another project's included, was cancelled at 18:42:34 by someone outside this session. Not resubmitted. A helper's
claim that an unordered group_by caused run-to-run differences did not reproduce; the fix was kept, the claim softened.

## 2026-10-06 — fourteenth session: the death shortfall is small trees in bad years

Owner: "continue". Resubmitted the cheaper growth-model test that the mass cancellation had killed, on the standard
queue because the owner's own jobs were filling the fast one; it ran cleanly at about 2 core-seconds per cell-year,
less than half the full quantile model. While it waited to be scored, I took the item labelled "too few big trees
die in 2016-25" and split the shortfall into "fewer trees at risk" and "lower death rate" per size class. The label
was wrong: almost all of it is trees of 5-10 m, and it sits in a handful of years in which the original kills far
more trees than usual (2019 is the largest: 7.5 % of small trees against the emulator's 5.4 %). Those years are not
fires or patch clearings — deaths are spread across patches — and the emulator gets the timing right but damps the
size of each pulse, while killing slightly too many in quiet years. Two checks are queued: whether the damping comes
through the sampled growth state (which feeds the death model) or from the death model itself, and which input
carries the low growth-state drift of 1995-2004.

Later the same session: the extra deaths in the bad years are not more likely ordinary deaths. They are the
original's two certain-kill rules — a tree that has had five consecutive years of negative growth, or whose leaves
have shrunk below a sapling's, dies for sure. Those rules account for all of the pulse; ordinary deaths are flat from
year to year. The emulator has the five-bad-years rule too, and it fires in the right years, but only about two
thirds as often in each pulse, while its share of bad-growth draws hardly moves between good and bad years. The
reading is that in the original, a bad year is bad for many trees at once, and the emulator draws each tree's bad
year independently. A one-step check of exactly that is queued but will not start until tomorrow, as are the scoring
of the cheaper growth model and the 1995-2004 attribution.

## 2026-10-06/07 — sixteenth session: the year-to-year skill was memorised weather

Owner: "continue". The open item was why the emulator under-reproduces how often a run of bad-growth years continues
into a second year, which damps the original's death pulses. First the explanation: what the current predictor gets
wrong follows the weather of the year the run started — a run that began in a dry, bright year tends to end (the
tree recovers), one that began in ordinary weather tends to continue. How many trees in the cell started a run
together explains nothing. A model term that lets the weather response differ for trees already in a run looked
like a large improvement (year-to-year slope 0.85 → 0.97) — but the test held out places, not years, and every
place in Germany shares a year's weather. Holding out whole years, the gain vanished: it had memorised the years.
That raised a bigger question, and the answer is uncomfortable: the shipped predictor's excellent year-to-year
timing on the second MPI run (correlation 0.98) is itself mostly memorised, because that run uses the same weather
years as training. On MPI's own SSP2-4.5 years, which it never saw, it is 0.78; on the ACCESS climate model 0.43-0.63.
Averages stay right everywhere. The mechanism is in the training code — every weather part stops training when it
stops improving on other cells of the same years — but fixing the stopping rule only removed the inflated score; it
did not raise the skill on unseen years (0.775 → 0.790). The limit is information in the annual weather inputs.
All earlier timing results on the second MPI run, the death-pulse deficit included, were scored on trained weather
years; the next session measures them on unseen ones first.

## 2026-10-07 — seventeenth session: the honest baseline, and where the bad-growth swing lives

Owner: "continue". First the measurement the last session asked for: the coupled emulator run on weather it never
trained on. On the MPI model's medium-emissions scenario the forest state holds (biomass per tree and tree counts
within a few per cent), but the timing of mortality pulses degrades from a 0.93 to a 0.79 year-to-year correlation,
pulse years are 25 % short and calm years over-killed by 14 %. On the ACCESS climate model the timing falls to 0.51
and, separately, the stand drifts after about twenty years (too many, too small trees). These are the numbers any
fix has to beat.

Then the question of whether better timing is even possible. The original model's two random-seed runs on identical
weather agree on the year-to-year share of trees with a bad-growth year at 0.999: the swing is pure weather, so the
ceiling is about 1, not 0.8. Monthly weather gets a simple model from 0.86 to 0.92 on unseen years; twice as many
training years barely helps; even the original's own monthly productivity and soil water add almost nothing; and a
leaf-shedding switch in the C code, reconstructed exactly from the daily forcing, turns out to fire once every year
for beech and so cannot carry a swing. What finally located it: a tree has a bad-growth year when its own
productivity falls below its losses, and the losses barely move — taking this year's productivity with last year's
losses reproduces the yearly swing at 0.83-0.97. The swing is individual trees crossing a threshold, which averages
blur. That suggests modelling each tree's productivity (smooth, well-posed) and letting the original's own threshold
decide the sign; a first test of that is running.
