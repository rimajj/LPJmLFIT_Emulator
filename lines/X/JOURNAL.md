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

## 2026-10-07 — eighteenth session: the loss side is solved; the ACCESS drift splits between grass and trees

Continued the bad-growth-year work. Gave the "model productivity, threshold it" route a proper loss model: given the
true productivity, it reproduces the yearly share of trees with negative growth almost perfectly (0.90-0.99), so the
loss side is no longer a limit. Plugged into predicted productivity it got worse, which exposed that the previous
version's good amplitude had been two errors cancelling. Modelling the growth margin directly is the best so far and
beats the shipped sign model on unseen weather (by ~0.1 on the same climate model, 0.2-0.3 on the other). A follow-up
showed its low slopes are timing error, not shrunken swings — my hypothesis there was wrong. Separately, two coupled
counterfactual reruns on ACCESS: pasting in the original's grass amount removes half to two thirds of the stand drift;
pasting its grass cover too removes less. The rest is the tree growth models transferring poorly to the other climate
model. Next: build the margin model into the stepper and score it coupled on unseen weather.

## 2026-10-07 — nineteenth + twentieth sessions: the margin model in the coupled emulator

Owner: "continue". The nineteenth session built the version of the "growth margin" model the emulator can actually
run (it may not read a tree's own productivity, transpiration or water stress, which the emulator does not carry),
wrote the stepper that draws each tree's bad-growth year from it, and pre-registered the coupled test, then ended
before recording anything. This session scored what it had left: dropping those three inputs costs nothing
systematic one step ahead, and the ACCESS big-tree growth deficit is not a generic climate-model problem.

A probe then pinned that deficit down. Given the TRUE next-year growth efficiency, the growth model is exact on every
member; the deficit sits entirely in the drawn efficiency, and there in its size, not its sign: on weather years it
never saw, the yearly mean of the drawn efficiency swings too little (yearly error 20-33 %, anti-correlated with the
true swing). Whether that nets to -3 % or to zero depends on which years a member draws. My two predictions (that the
growth model, then that the sign, carried it) were both wrong; the falsifiers said so.

The coupled margin run itself: on the other climate model the timing of mortality pulses jumps from a 0.51 to a 0.84
year-to-year correlation — the largest gain on unseen weather so far — but the stand degrades on both members: too
many bad-growth years land on big trees, they shrink, the canopy opens and recruits flood in (biomass per tree -10 to
-25 %). Not adoptable as is. A one-step check of whether that size misallocation is the model's or the free run's is
running.

## 2026-10-07 — twenty-first session: size-wise recalibration of the margin model fails; the excess is member transfer

Picked up the twentieth session's NEXT (1): recalibrate the stepper-feasible margin model MS by tree height on training
out-of-fold rows. Added `oof` / `calib` / `score_calib` / `zstats` stages to `scripts/explore_de_nppmodel2.py` (refactored
the fit into `_train_table` + `_fold_oof`; `Arm("MS+c")` applies the probit as a shift/scale of mu, s so the stepper
still draws a carried margin). Pre-registered K before the run: the out-of-year training rows show almost no big-tree
excess (+0.003), so the fitted calibration removed only a third of the test members' excess — falsifier fired, coupled
run not submitted. KZ split the rest: a tail shape (everywhere) plus a mean bias that only appears on unseen members,
largest for the tallest trees on the ACCESS futures (+0.17..+0.38 spread units). In parallel GM (`explore_de_gmargin.py`)
tested the twentieth session's NEXT (2): the exact identity G = r (1 - e^-m) holds; with the true productivity r the
drawn margin carries the magnitude's year swing better than the current quantile sampler, with last year's r it does
not. Details and every number: TS.md, "Pre-registration K" onwards. Jobs 2431747, 2431753, 2432298.

## 2026-10-07 — twenty-second session: where the margin model's tall-tree transfer bias comes from
Three one-step probes on the five test members (details + pre-registrations in `_status/TS.md`, "Pre-registration T" on).
Level swap (T): ACCESS climatology levels -> MPI's closes 5-8 % of the futures' shift; falsifier fired. By warming bin (T3):
the shift exists at equal warming and on fully in-range rows, so it is a GCM-specific response. Refit with ACCESS Historical
in training (T4, arm MSx, 31 min fit): halves it; ssp245 stays worst. One job failed on my own sed mangling the script name
in a copied .jcf (resubmitted). Next: the both-GCM training arm tested on the held-out ssp245 of both GCMs.

## 2026-10-08 (late) — training data moves to Billing's global runs; Germany re-run cancelled (ADR 0313)

Owner asked me to find M. Billing's recent global runs, keep only the normal random-trait ones, and train on those
instead of Germany. Home dir held only code (`LPJmLFit_global_final`, branch `trait_vector`, rebuilt in place); the
runs are in `/p/projects/pbscience/billing/LPJmLFIT/global/` and his `simulation_protocol.txt` names r1 = standard
LPJmL-FIT, r2–r6 = traits prescribed from r1. Audited every r1 member's config, logs (build date, completion),
restart chain: 8 clean GFDL-ESM4 members × 4 legs + 6 reanalysis members. Owner: model version does not matter.
Owner then asked to cancel the Germany re-runs if the global data is better — it is (8 members vs 2, all cells, no
humidity defect); the 18 S-D2 jobs were all still pending, cancelled by explicit id (a pattern-based scancel was
refused by the permission classifier). Converter needed two global-size fixes (Int16 Cell; 1e7 sort-key
multiplier). First table gate: conversion_ok, census/unique "fail" = bare-land cells (1 616 of 1 627 VegC == 0)
and the known duplicate raw key.

## 2026-10-08 (night) — global set: conversion finished, climate inputs built and verified, venue pre-registered (ADR 0314/0315)

Collected the conversion: 32 GFDL-ESM4 tables fine; all six reanalysis tables failed on `header drift` — the Oct-2026
builds write a 30-column `ind` (+Height_max/stemdiam/barkthickness/mort_fire, −wscal_mean/beta_root/k_root). Added a
native layout switch, reconverted (2445730), 38/38 conversion_ok. Built `explore_glob_climate.py` (net longwave PET,
specific-humidity VPD, hemisphere reset windows). ⚠ Mid-session I claimed getvpd.c's `1013.25` was an hPa/Pa slip
making rh 100× too small, and told the owner so; the script's first run refuted it (the formula with hPa yields a
fraction — mean rh 0.63 on a test sample, 0.69 globally). Retracted to the owner, the dependent probe deleted before
it ran. Lesson: check a "units bug" numerically on the real file before saying it. End-to-end gate (printed mort_temp
from tstress_pft<Type>) passed 100 % on all 32 GFDL tables at first try; the Oct tables matched 94.7 % — implied
count exactly 0.8× ⇒ Billing's live par file now sets MORT_TEMP_FACTOR 4.0 (and tropical cold limit 14 °C); with that
override 38/38 at 100 %. Registry: 58 187 tree-bearing cells, 5 folds balanced to ±1 cell, four splits. ADR 0315
pre-registers DP-G1 before any arm runs. Jobs 2445718 (climate), 2445735 (registry), 2445741 (gates).

## 2026-10-08 (late night) — global scorer, baselines and the first arm (ADR 0315 §7–8)
Owner asked why nothing was running: I had stopped after the data prep instead of starting the scorer — no reason to
wait. Built `explore_glob_eval.py` (Germany reduction code, 25 patches, GS370 venue, dev cells) and scored the nulls
(job 2445751, ~2 min). Ceiling only 0.173 conjunctive per-cell pass; the lookup null at 0.100 beat DP-G1 (a)'s 0.087
⇒ tightened (a) to "above the best null". A7 direct map (job 2445762, 3 min): A7s 0.131 pass, response slope 0.63 vs 0
for its twin, but biomass per tree +12.4 % ⇒ fails (b). Owner also asked whether Germany runs were still going: all 18
D2 jobs CANCELLED, the 64 queued S-D*/S-Dcol* jobs are line S's global five-model panel (kept on purpose).

## 2026-10-09 — the calendar test for A2g, and a leak in its published score (ADR 0315 §14)

Built `scripts/explore_glob_clock.py` (expectations in its header before the run): reloaded the A2g fold models,
re-predicted member 8 with (a) ssp370/ssp126 contrast — elapsed time cancels — and (b) a no-warming drive (1985–2014
years shuffled), compared with the track-D panel's constant-climate control. While writing it, found the prediction
input back-fills treeless-in-history cells from the test member's 2071–2100 truth; measured it in the same run.
Jobs 2447108/09/10, all four harness checks pass. Results: leak inflated the tree-count response slope 0.65 → 0.86;
the arm separates scenarios in total but not per cell (0.30); the panel comparison is inconclusive by its own basis.
Next: clean retrain.

## 2026-10-09 (morning) — A2g causal fill + retrain (ADR 0315 §15)

Replaced the forward+backward input fill by a forward-only one in `explore_glob_lstm.py` (training and prediction) and
retrained A2g + twin (2447157/58) and the two per-build runs (2447168/69). Expected (header) slope ≈ 0.65; got 0.85.
Localised it: the 303 exposed cells — leak-trained model with clean input predicts 22 % of their late stems, the retrain
95 %, all other cells agree to 0.4 %. So §14.1 priced a train/inference mismatch, not the leak; withdrawn in §15.
Added `--tag` to `explore_glob_clock.py`; calendar contrast on the clean models: stems slope 0.47 (0.30 before).
Germany LSTM leak probe: 0 exposed cells. Skill gotcha added to `residual-diagnosis`.

## 2026-10-09 (afternoon) — what it takes to run the per-tree arms on the global venue

NEXT item 2 (A3/A4/A6 on the global venue) turned out to need a port first: all three are built on the Germany TAB
stepper. Mapped the whole chain (subagent read of ~25 modules) → `docs/notes/exploration_glob_tab_port.md`: eight
blockers, the data root to build, stage order. Checked the one scientific risk in it — whether the rule library's
parameters are the ones Billing's Feb/May runs used. His live par files differ from ours in 160 values but were edited
after those runs; the runs' own output (longevity inferred from mort_age to 1e-6, k_root, mort_temp) matches the LOCAL
set exactly on both builds. No jobs run.

## 2026-10-09 (midday) — the per-tree arm ported to the global venue, and its first free run

Built a Germany-format data root over the Feb GFDL members (`explore_glob_tabroot.py`), made five env-gated,
Germany-inert changes (horizon, recruit/grass types, one grass model per type, trait build, a late window starting its
own chain), and ran the chain SH2→SH3→SH4→SH5→SH13→A1→A2–A5→A6 prep; every integrity gate passed (counter recursion
holds on all 706 M pairs). Scorer harness exact. Expectations written first (ADR 0315 §16). Result: plain TAB fails —
pass 0.022, trees 1.17, biomass per tree 0.505 — and the climate-blind twin is much closer on totals (0.90 / 0.90): a
climate-driven collapse on top of Germany's slow growth deficit. Submitted a one-channel attribution (§16.2).
Snags: `sh_init submit` ignores `--start` (30 tasks; cancelled), the registry must live under `shared/registry`,
the survival training job segfaulted AFTER saving both heads, the trait fit failed only on a missing `_reports` dir.

## 2026-10-09 (afternoon) — which climate channel collapses the per-tree arm, and the calibration arm A4

Collected the four one-channel runs (two scoring jobs were stuck behind the per-user CPU cap; moved to `standard`).
Growth efficiency is the channel: switching off its climate booster closes 60 % of the biomass-per-tree gap (bar was
≥ 50 %). The two secondary expectations failed — the growth-amount booster does nothing, and the recruit booster was
*suppressing* recruits (switching it off adds 8 % stems). Read-only check: the growth-efficiency sign head is calibrated
on true stands (held-out rows, within 0.4–0.6 points) but the free run's bad-year streak share climbs to 0.135 by 2030
and 0.16 by 2085 vs the original's ~0.12 ⇒ an error that compounds once the simulated stand drifts. ADR 0315 §16.3.
Pre-registered A4 (§16.4) and submitted the calibration grid on member 2 / ssp245 / fold 1 (8 runs, 2450600–19, scorer
gained `--truth-seed`/`--fold`; driver `scripts/explore_glob_a4.py` with stages cal / pick / confirm).
Results (§16.5–16.7): no scalar brings the per-tree arm within ±10 %. The offset family moves the bad-year rate by more
than the free-run excess and buys only a sixth of the gap ⇒ the biomass goes through the learned climate effect on
growth-efficiency MAGNITUDE (an input of the growth heads), not the count of bad years. Split added to the stepper
(`kappa_gsign`/`kappa_gmag`, default 1). The climate-blind twin on member 2 is itself 26 % short on biomass per tree.
Offset −0.5 transfers to member 8 / ssp370 within 0.03 but scores 0.614 / pass 0.024. A4 fails; recommendation to
park the per-tree arms on this venue recorded in STATE. Jobs 2450600–19, 2450733–36, 2450741/42, 2450798/99.

## 2026-10-09 (late afternoon) — the panel venue, the deployment setting, and more data (ADR 0316)

Owner: continue, produce more data if solid results support it; asked for a status report (given in chat). Built the
panel venue on line S's Track-D runs (climate features, levels, yearly stats, control draws recovered exactly from daily
precipitation). Direct map with cells held out: below the lookup null, falsifier fired as written — the split also held
out the cells. Added the deployment setting (cells seen) and a per-cell anchor: A7r passes the bar on 11/13 held-out-model
cases (fails the two hottest), ~0.9 of a second run's agreement in range; global GS370 exactly on the bar. Found that
ADR 0315's 0.131 was a favourable draw (polars row order × LightGBM bagging; 5-seed mean 0.126). Cell-level coverage test
mixed (pooled yes, per case 7/13). Data curves (models, runs, ssp585) all still rising ⇒ produced more data: 5 new climate
models (regrid gate byte-identical) for m1–m4 and two new independent members m5/m6; 62/62 configs pass lpjcheck. Resubmitted
line S's two panel legs that died of a cluster launch failure. 75 panel LSTM fold models trained (all converged), scoring
chained. Jobs 2451013/14/146/116/117/438/440/593/596/605/614/619–23/628/684/711/723/818–29, 2451101–04.
Evening: the panel LSTM scored (2451440) — stable for 3 of 5 held-out models, runaway (up to 6-8x stems) for MRI/UKESM
fits, levels below the direct map; parked. A first summary had averaged the runaways into "2.2x"; caught by checking
the yearly predictions decade by decade. Global A7r with member 7 as a fifth training run: +0.003 (inconclusive, at
the falsifier line), clears the bar by 0.003. The panel extension runs were stuck ~3 days for whole nodes; resubmitted
spread over free cores (new runs need no node pin), all started at once. Prediction test chained (2452216-21).

## 2026-10-09 (night) — the acceptance target becomes "as close as a second run" (ADR 0317)

Owner decided the target is closeness to a second run of the original, "not more than 10 % worse" (then asked whether
20 %). Defined an error-ratio measure (per quantity: centile-50 and centile-90 of per-cell errors vs an unseen run,
divided by a second run's; levels and response; all cells + regions; area totals as a separate check) and measured it
on the panel (`scripts/explore_tolerance_measure.py`). Nulls came out as derived (second run ~1.0, mean of three runs
0.82). The best arm is better than a second run on the four trait medians but 1.4–2.2x worse on tree count and
1.6–1.8x on biomass per tree, hardly better than a lookup; the old conjunctive pass rate had hidden that. Literature
checked (ClimateBench, Lütjens 2025, CESM consistency test, Global Carbon Budget 2024). Recommended 10 % on all cells,
20 % per region (measurement noise). Not propagated.

## 2026-10-09 (late) — global venue on the second-run measure (ADR 0317 §8)

Runs m1–m4 of the more-data campaign finished; m5/m6 still running (spin-ups, history and 2 models done). Collector m1
moved to the priority partition (started at once); m2–m4 collectors still queued on standard, the chained prediction
test waits on them. Wrote `scripts/explore_glob_tolerance.py` (factored `prepare()` out of `explore_glob_a7r.py`),
predictions committed before the run. Result: harness and oracle as derived; A7r is not as close as a second run on tree
count (1.44) or biomass per tree (1.96), and on biomass per tree it does not beat the ssp245 lookup null (1.84). The
miss sits in sparse cells. A fifth training run changes nothing (≤ 0.02). Recorded as ADR 0317 §8 (§7 stays reserved
for the owner's 10 %/20 % answer).
Follow-up, same session: the 'anchor too low' hypothesis refuted on disk (anchor/truth 1.11 for biomass per tree, 0.94 for tree count; ssp370 = more, smaller trees). Next: measure extrapolation of ssp370 climate beyond the training legs.

## 2026-10-10 — the more-data prediction scored (ADR 0316 §10)

All chained jobs had finished overnight (m5/m6 present; line S's two dead m4 legs now exist, so 15 test cases). Aggregated
the five seeds: the pre-registered prediction held on both conditions (+0.033 on ssp370, bar on 12 of 13), base
re-measured 0.161 vs the earlier 0.162. The gain splits as +0.023 from five more climate models and +0.005 from two more
runs. Then read the same predictions on the second-run measure (added a `PRED_SET` knob to
`explore_tolerance_measure.py`, expectations written into its header first): biomass per tree 1.64 → 1.42 (expectation
held), tree count 1.39 → 1.35 (missed the 0.05 expectation, above the falsifier). Conclusion: more climate models help
and have not saturated, but even optimistic linear extrapolation needs ~14–40 training models to reach the owner's
1.1–1.2, and ISIMIP3b has ten. The arm must improve; more runs per cell are not worth producing. A first draft of the
write-up over-counted the 15-case bar passes (14 → 13) and gave a loose extrapolation; both corrected before commit.
Afternoon: broke the remaining error down by tree density — sparse cells (< 5 trees per patch) are 3× a second run while
5–20 classes are near 1.2. The arm fits absolute residuals; switched the target to a log ratio (A7rL, pre-registered):
mixed — biomass per tree improves everywhere (1.42 → 1.26, bad cells 1.71 → 1.26), tree count trades sparse for dense
and its total drifts 4 % low. Combined (A7rH: log target for biomass per tree only) is the new best: pass 0.207. Tree
count is now the binding gap; next one-variable test is a count-aware loss.

## 2026-10-10 (morning) — count-aware loss for tree count (ADR 0316 §12)

Continued from the §11 NEXT. Added mode `cnt` to `explore_panel_a7.py`: Poisson and Tweedie objectives on tree count
with the per-cell anchor as a log offset, the rest of the arm as A7rH; expectations committed before the run (fd0b26c1).
Five seeds on the priority partition (~10 min). Result: the same trade-off as the log target — the sparsest cells gain
(3.45 → 2.19× a second run), typical cells and the stems total lose a little (1.35 → 1.39×; 1.9 % → 3.2 %). Pass rate
0.204 vs 0.207. Most expectations failed, falsifier did not fire. Conclusion: weighting cannot fix tree count; the model
lacks information about how sparse (range-edge) cells respond. The harness also showed LightGBM's multithreaded fits are
not bit-reproducible across runs (one compared case off by ≤ 1 % at 3 cells); recorded, not switched mid-series.
Next: per-cell response features. Jobs 2458085–89.

## 2026-10-10 (late morning) — owner: dense cells first; the error in plain units (ADR 0316 §13)

Owner asked whether the method could go into an ESM, said dense cells matter most and sparse cells less, and asked what
1.35× a second run means in numbers. Wrote `scripts/explore_panel_abs_err.py`: dense cells 7.1 % per cell vs 5.8 % for a
second run (≈1.2×), close to the original's noise; but the dense-cell total is low in all 15 cases (up to −5 %) while a
second run's total is within 0.5 %. Next: locate that bias. Asked whether the dense-first steer should amend the finish
criterion.
