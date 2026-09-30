# LINE X — project direction & exploration (branch `line/X`, worktree `wt-X`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/X/JOURNAL.md` (append-only). Decisions: tier-1 block
> **0310–0329**, opened by **ADR 0310**. **Next free number: 0313.**
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

---

## What this line is (created 2026-08-19 on owner instruction)

Owner, verbatim: *"you are also nto the correct person to discuss this with. relocate our whole discussion to
a new line that is responisble for these project lever decisions and exploring new ideas."*

**Line X is where project-level direction is explored and where new ideas are worked out before anybody
builds them.** It exists because the four component lines (S, M, E, O) are each mid-ladder on a specific
subsystem, so a question like *"should the whole architecture be different?"* has no owner: whichever line is
asked either has to act on it (wrong — it is not their call) or drop it (worse). Line X can hold an open
question, measure it, and leave it open.

### Scope — what line X DOES

* **Explore directions that deviate from the current architecture** — the hybrid, the ladder, the component
  split. Adversarially, with measurements, against the existing records.
* **Own the owner conversations about direction**, and record what the owner actually said, verbatim, next to
  every open exploration.
* **Price alternatives honestly** — including pricing the *incumbent* fairly, which is where exploration work
  usually cheats (see the traps below).
* **Write the exploration up as an ADR from block 0310–0329**, marked `exploratory` unless the owner promotes
  it.
* **Read anything. Measure anything read-only.**

### Scope — what line X does NOT do

* ⚠ **It does not implement.** No `src/**`, no `ext/**`, no flags, no artifacts. A finding that survives
  becomes a *proposal*; the owner decides; the owning line builds it.
* ⚠ **It does not write into another line's `STATE.md`, `MEMORY.md`, or `EXECUTION_PLAN.md`.** Line X's whole
  value is that it can hold an idea without pushing it at anyone. **Propagation is an owner decision.** This
  is not a style preference — it is the instruction that created the line:
  *"no! stop! dont write anythign of this to other lines!!!"*
* **It does not merge another line's work or act as the integrator.** (Except in the ordinary sense that
  whoever holds the `flock` is the integrator for that moment — §9.)
* **It does not re-litigate closed owner decisions.** Standing closures: **CO2** (the emulator does not see
  CO2 and must not respond to it — ADR 0004/0107; never propose a CO2 feature or list its absence as a
  defect), **licensing/reuse** (ADR 0080/0081 — reuse is authorised, cite transparently, never raise it
  again), **the spin-up saving is not the goal** (ADR 0094), and **the acceptance criterion** (ADR 0106 —
  line X may *propose* an amendment, explicitly and with both patch counts stated, but never adopt one as a
  premise).

### Owned paths

| path | note |
|---|---|
| `lines/X/**` | exclusive |
| `docs/decisions/0310-0329` | exclusive (tier-1 block; tier-2 would be 0330–0349) |
| `changelog.d/X-*.md` | new fragments only — **never** edit `CHANGELOG.md` from a line |
| `docs/notes/exploration_*.md` | exclusive — long-form exploration notes that are not decisions |
| `scripts/explore_*.py` / `scripts/explore_*.jl` | exclusive — read-only probes. ⚠ Derive the repo root from the script (`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` / `@__DIR__`), never a hard-coded absolute path, or you write into the integrator worktree (§9 trap 6). |

**Everything else is read-only to line X**, including all of `src/**`, `test/**`, `python/**`, every other
line's `lines/*/STATE.md`, `MEMORY.md`, and `EXECUTION_PLAN.md`.

### The four traps this line is most likely to fall into

These are not hypothetical — every one of them was committed in line X's own opening exploration (ADR 0310)
and caught only by adversarial review.

1. ⚠ **Rigging the comparison against the incumbent.** ADR 0310's speed case claimed "210× faster than the C"
   by measuring against a 25-patch configuration that the same repo had already shown nobody needs for the
   quantity being priced. **Price the incumbent at the configuration it would actually be run at.**
2. ⚠ **Reporting a skill number with no null.** A one-step forest-state operator scored 0.9824 — against a
   persistence null of **0.9622**. A per-cell response model scored 0.748 — against a **pure lat/lon
   geographic address at 0.654**. **Derive what each null must return and write it down BEFORE the run**
   (ADR 0184's rule). A missing null is the single most common way an exploration reports a discovery.
3. ⚠ **Substituting a convenient basis for the owner's.** ADR 0310 nearly concluded that the response bar
   needs 0.12 % level accuracy, from an area-weighted **global aggregate** that appears in **no** acceptance
   criterion; on the owner's **per-cell** basis the number is 1.86 %, fifteen times looser. **State the basis
   in the same sentence as the number.**
4. ⚠ **Letting a measurement go stale.** ADR 0310's first draft reasoned from records that stopped ~30 ADRs
   before the present day, and two of its "blocking data gaps" were refutable with one `ls`. **Check the
   newest ADR number and the newest STATE files before concluding anything is unmeasured or impossible.**

---

## NEXT — start here

### 00✦ 🔨 OWNER INSTRUCTION 2026-09-30: BUILD the data-driven emulator, Germany first (supersedes "line X does not implement" FOR THIS BUILD ONLY)

Owner, verbatim: *"ok go on and build the emulator. you can also do it for germany only now, for testing. for germany we have runs with
more pathces and several different ssp scenarios and two differnt models in /p/projects/waldspektrum/data/LPJmlFit/productionruns_Jamir"*
(the real path is `/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir`), and *"be aware that the trasnioent run is only until
2100, after that the climate is recycled, so no warmin response is tehre"*. Ultracode (multi-agent) switched on by the owner the same turn.
**The build stays inside line X's owned paths** (`scripts/explore_de_*.py`, `/p/tmp/jamirp/X_de/`, `docs/notes/exploration_de_*.md`):
it is a standalone prototype, no `src/**` edits, nothing propagated to other lines.

**The Germany data [VERIFIED 2026-09-30]:** 2 GCMs (MPI-ESM1-2-HR, ACCESS-CM2) x {Historical, ssp126, ssp245, ssp370} x 2 independent
spin-up seeds, 9067 cells (~8 km), **npatch 250**, all 16 runs log a clean termination. `ind` tables: Historical 1985-2014; each ssp
2015-2044 / 2071-2100 / 3071-3100 (**no table for 2045-2070**; **3071-3100 is recycled shuffled 2071-2100 climate = equilibrium test
only, never a response window**). ⚠ MPI ssp370 seed2 `ind_3100.csv` is 10 GB vs ~120 GB siblings — suspect truncated. Fire is ON.
Daily forcing `/p/projects/waldspektrum/data/FirEUrisk/<GCM>/{TMean,tpr,HRMean,SWR,LWR,windspeed}_<GCM>_<leg>_germany.clm` (v3 float32).
The original costs ~12 core-s per cell-year at 250 patches (2048 tasks x 3556 s / (65 yr x 9067 cells)).
**Why this data matters:** the same cell sees six different futures (2 GCMs x 3 scenarios) — the design that can break the
"warming vs character of the place" confound ADR 0311 found, and ssp245 is a bracketed held-out scenario.

**Round 1 workflow `wf_89265fa2-f32`** (conversion of all 40 tables to parquet, climate features, transition anatomy + verifier,
scorer + null scores, 3-architect design panel + judge, critic). Resume: `Workflow({scriptPath:
"~/.claude/projects/-p-projects-open-Jamir-esm-land-emulator-lines-X/a19083d6-0024-4d05-8614-5e108626a023/workflows/scripts/de-emulator-germany-foundation-wf_89265fa2-f32.js",
resumeFromRunId: "wf_89265fa2-f32"})`. Round 2 = build + train + free-running rollouts + held-out scoring, from the judge's work items.


### 0✦ 💬 NEW OWNER QUESTION, ANSWERED — where does the ORIGINAL model's time go? (owner, 2026-09-02; **ADR 0312**)

Owner, verbatim: *"find out which parts of the original model consume most computational time (e.g.
photosysntesis or other processes). we can use this as basis for explorign soltutions where only these
processes are learned."* **Measured at five biome sites on the unmodified binary — no rebuild, so the oracle's
reference basis is untouched.** Three things to carry forward:

1. ⚠ **The pre-registered falsifier for that strategy FIRED at all five sites.** The largest single process
   (the per-tree daily assimilation/conductance kernel) is **36–46 %** of runtime, so making it entirely
   **free** buys only **1.57–1.84×** — against a requirement of **≈15–25×**. ⇒ *"learn only the expensive
   process"* works **only as a portfolio covering ≥ 90 % of the daily loop**, which is close to a
   whole-daily-core replacement, not a surgical one. **And every ceiling assumes the replacement is FREE; at
   20 % of the replaced cost, 1.84× becomes 1.56×. Never quote a ceiling as a speed-up.**
2. ⛳ **The annual demography — the whole block the learned slow component replaces — is 0.44–1.06 % of the
   original model's runtime.** The correct reading is **not** "we learned the cheap part": it is that the
   demography's speed value was never its own cost but that **it removes the patch tax** (cost is linear in
   patch count, this configuration runs 25, and a component predicting the ensemble expectation converts a
   ~25× multiplier into 1 — a bigger lever than every process combined). The reason nobody sets the patch
   count to 1 is **fidelity, not speed**.
3. **Two targets worth pricing, different in kind.** A quarter of the entire model (**21–27 %**) is
   `exp`/`pow`/`log` ⇒ an **engineering** target, no learning, no fidelity risk, ceiling 1.28–1.37×. And the
   **λ root-find** is the best-posed *learning* target in the model — smooth, deterministic, scalar output,
   no state, unlimited training data, sitting on the largest share (33.3 % inclusive) — but the gross flux is
   **non-monotone** in its iteration count, so its convergence cannot be assumed.

**The cheapest missing number in ADR 0312: re-measure the patch-count slope on this binary.** It is cited from
ADR 0093, not reproduced, and my own blocks disagree with its published value by a factor ~1.4–2.

### 0b✦ 💬 THE OPEN CONVERSATION, ROUND 2 IS MEASURED AND HALF-FINISHED (owner, 2026-08-19 → 2026-09-02; **ADR 0311**)

**Still an owner conversation, not a work item. Still nothing raised with S/M/E/O, nothing in `MEMORY.md` or
`EXECUTION_PLAN.md`, nothing implemented.** Owner's words this round: *"continue the exploration of the
feasibility of a **more** data driven emulator"* — **more**, not necessarily **purely**, and nobody has yet
priced the middle of that spectrum.

**⚠ READ `ADR 0311` BEFORE ANYTHING ELSE. It overturns ADR 0310's headline verdict.** Three
things you must not carry forward from ADR 0310 as stated:

1. **"ZERO positive evidence exists for the warming response" is NO LONGER TRUE.** A direct
   20-yr-climatology → 20-yr-window-state map beats a coordinates-only null under **spatially blocked** folds
   by **+0.162…+0.715** on the clean 20-vs-20-yr response, and climate *subsumes* the address rather than
   proxying it. Its verifier attacked with three independent address nulls and the margin came out
   **2–6× larger**. ADR 0310's kill of this claim was a hash-fold artifact on a drift-contaminated target.
2. **"The geographic-address null was never run" is FALSE** — it was built, pre-registered, published and
   committed sixteen days earlier (ADR 0038/0040/0042, plus `blocked_cv_folds_probe.jl`,
   `build_slow_spatial_controls.py`, `diagnose_slow_address_prereg.py`). **Reuse it; do not rebuild it.**
3. **"Single-draw R² cannot discriminate arms" is overstated** — the exact Bernoulli floor is ~28 % of the
   residual variance, not all of it.

**The four things that now matter most:**

* ⛳ **The identification limit is the deepest result and it bounds every cross-sectional design.** Within one
  emissions scenario a cell's warming increment is **76.4 %** predictable from its own baseline climate, so
  "response to warming" and "sensitivity of this place" are **not separately identified**. Consistently:
  knowing the future climate adds nothing over knowing today's on 5 of 6 targets, and a **counterfactual with
  warming scaled to zero still reproduces 76–110 %** of the predicted per-cell change. ⇒ **the third forcing
  leg is the only way to break it**, and the literature says only a **bracketed** design has precedent
  (historic + ssp370 bracket ssp126 at 0.227×).
* ⛳ **The per-tree hidden state is exactly recoverable and propagable — but UNVERIFIED** (its adversarial
  verifier died to a usage limit; `scripts/explore_verify_b1.py` exists and was never run to completion).
  **Finishing that verification is the single cheapest high-value action available.**
* ⚠ **Per tree, climate adds nothing beyond the stand** (+0.0030, below the pre-registered 0.005; within noise
  under blocking) ⇒ a free-running rollout's response can only come from state it generates itself.
* ⚠ **The map is 7.2 % of cells on the owner's conjunctive basis and LOSES to persistence on the future state**
  (7.35 % vs 12.96 %), and space-for-time transfer is **sign-wrong** in the 3.7 % of genuinely extrapolating
  cells.

### 1✦ THE UNFINISHED HALF — resume the campaign from cache (no new design needed)

Three measurements, the spectrum synthesis and the completeness critic **did not run** (usage limit, then
server overload). Everything that did run **replays from cache**:

```
Workflow({scriptPath: '~/.claude/projects/-p-projects-open-Jamir-esm-land-emulator-lines-X/
  71d6fd2b-2837-45c1-9b0b-0e3e1b72c572/workflows/scripts/
  data-driven-emulator-feasibility-round2-wf_5ba7e1aa-b45.js',
  resumeFromRunId: 'wf_5ba7e1aa-b45'})
```
Restore `ITEMS` (currently `.slice(0, 3)`) and set `RUN_SYNTH = true`. What is queued in it:
**B4** the ssp126 bracketed held-out leg (⚠ gate its Aug-12-vs-Feb-5 build provenance FIRST; it is raw CSV
only, 186 GB/seed, and is in **no** shared table) · **B5** whether a fixed-size stand summary suffices for the
daily fluxes · **B6** the closed density-feedback rollout with a stochastic binomial-survival/Poisson-birth
head · **the synthesis that prices the WHOLE SPECTRUM** from the shipping hybrid to the pure learned model,
which is what the owner's word *"more"* actually asks for · the completeness critic.
⚠ **Add the persistence null to the pre-registration TEMPLATE, not only to the brief's prose** — ADR 0310
§2(ii) made it a STANDING RULE and the very next campaign violated it anyway (see ADR 0311 §8).

### 2✦ WHAT IS ON DISK ALREADY — look before building (all read-only, no model run needed)

`/p/tmp/jamirp/X_explore/`: `prep_paired_stems.parquet` (21 785 911 × 40, year-paired per-stem on the
**corrected** identity key) · `prep_patch_year_stand.parquet` (2 553 172 × 43) ·
`prep_cell_window_state.parquet` (334 212 × 26, **both seeds** ⇒ a per-cell two-seed noise floor for the
20-yr state with no model run) · `prep_cell_window_clim.parquet` (202 260 × 37, incl. unit-sphere x/y/z) ·
`prep_cell_year_census.parquet` (11 029 804 × 9) · `prep_suspect_cell_blocks.csv` (**the exclusion list — join
it, or you will measure five damaged blocks**) · the `b3_*`, `vb2_*`, `vb3_*` result sets.
Probes: `scripts/explore_{prep_tables,hidden_counter,perstem_ladder,direct_window_map}.py` and
`scripts/explore_verify_b{1,2,3}.py`. Literature: `docs/notes/exploration_data_driven_literature.md`.

### 3✦ THREE CORRECTIONS OWED TO OTHER LINES — RAISED IN ADR 0311 §6, DELIBERATELY NOT PROPAGATED

**Propagation is the owner's call, not this line's.** (a) **ADR 0125's per-stem identity key is WRONG** — it is
`(Cell, Patch, PFT, ID)`; the tree number comes from a **per-PFT** counter, the documented key fails the
identity gates on every leg, and the corrected one gives 0 violations of 20.4 M pairs on three checks.
(b) `bm_inc_counter` **is** recoverable from the annual `ind` output, and it **is** populated into the output
struct at `fwriteoutput_ind.c:167` with only its print line commented out at `:96`. (c) The heat/cold stress
day count is **exactly** invertible as `round(mort_temp × 365/5)`. Plus: the two roster seeds were **never
re-verified as a valid ADR-0041 pair**, which is an open gate on every number in ADR 0311.

**Do NOT redo** ADR 0310's six investigations or ADR 0311's three measurements. Transcripts:
`…/subagents/workflows/wf_1392bef9-337/journal.jsonl` (round 1) and `…/wf_5ba7e1aa-b45/journal.jsonl`
(round 2 — one `{"type":"result"}` line per agent; the `/tmp` task-output files have since been cleared, so the
journal is the only copy).

---

### 0a✦ 💬 ROUND 1 — the record that opened this line (**ADR 0310**; superseded in part by 0311 above)

**This is an owner conversation in progress, not a work item.** Answer questions, measure, deepen it.
**Do not implement, do not raise it with line S/M/E/O, do not write it into `MEMORY.md` or
`EXECUTION_PLAN.md`.** Promotion is the owner's call. Both governing instructions are quoted verbatim in
ADR 0310's Status box — read them first.

**What the owner asked:** drop the hybrid — learn `(forest state, climate) → next forest state` directly and
roll it out, plus a second head for the daily fluxes an atmosphere needs. *"Do you think this is learnable /
achievable?"* Offline first; the hope is that it captures **the warming response**, not just the steady state.

**The answer delivered — it is SIX problems, not one, and lumping them is why it looks either obviously right
or obviously refuted:**

| part | verdict |
|---|---|
| daily **water + carbon** fluxes | data exist (~1 TB, both scenarios); **learnability untested** |
| daily **energy** fluxes | ⛔ **impossible from this model, permanently** — of 421 outputs only monthly albedo + soil temperature are energy-adjacent |
| one-year-ahead step, teacher-forced | **already built, and 96 % of its skill is the persistence null** (0.9622 of 0.9824) |
| free-running century rollout | stable — but **every reason given for the stability was a tree-ensemble artifact**, and rollout training has never been tried here |
| **the warming response** | ⛔ **not demonstrated, and ZERO positive evidence exists** — the one claim died to a geographic-address null (lat/lon alone 0.654 of the 0.748) |
| speed | ✅ **≈0.0032 core-s/cell-year at fp64**, fits the strict convention with 4× margin |

**The four things that matter if the owner picks this up** (all measured; full detail in ADR 0310 §5):

1. **The strongest objection is specific, and it just became TESTABLE.** Every tree carries a private
   consecutive-bad-years counter; it is trait-correlated (+19 % wood density across its range), 11.69 % of
   stems carry **44.8 % of all mortality**, and summarising it away **reverses the selection sign in 4 of 7
   tree types** (ADR 0093 §4.4 — which is owner-approved and says the density family is *dead*). ⛳ **NEW: that
   counter IS dumped per stem in the rung-2 roster files** (§7.3), so the refutation can be measured instead
   of believed. **This is the highest-information thing available.**
2. **The architecture nobody priced: a permutation-equivariant set/graph network over the per-stem roster.**
   Still purely learned (no ported equations) but it **keeps the individuals** ⇒ **2.55e9 paired per-stem
   labels** instead of 1.2e8 cell-year rows; it is the only candidate that survives (1); and it pays no patch
   tax. ADR 0086 §5d's "learned annual operator = 1.3–1.5× only" **does not apply** to it (that costing
   assumed the daily soil loop stays).
3. **The head should be STOCHASTIC, and the target the ensemble distribution.** Rectification (86.7 % of a
   decline reproduced vs 96.2 % of a rise) is the *definitional* failure of a self-fed conditional-mean
   regressor. A **binomial-survival + Poisson-birth** head is conservative by construction and structurally
   forbids the measured 799.5-stem blow-up. Precedent: GraphCast → GenCast.
4. **Single-draw R² cannot discriminate arms.** Deeper history buys **0.00024** of variance; the ~2.4 %
   surviving lag-1 is the C's own Bernoulli noise ⇒ the ceiling is a **variance** ceiling. Any experiment
   guarded on an R² floor is mis-designed. (This also **narrows** "the state is not Markov" to the trait-axis
   selection covariance — it is *not* true of count predictability.)

**Three measured facts sitting unpropagated in ADR 0310 §7** — real, and deliberately NOT in `MEMORY.md`:
**ssp126 both seeds completed 2026-08-18** (591 GB, correct seed protocol; warms **0.227×** of ssp370 on a
common baseline; pattern correlation only **0.19–0.22**; **15–26 % of cells COOL** ⇒ useless per cell,
excellent as a held-out test that a memorised warming pattern must fail; ⚠ built with an Aug-12 binary vs
Feb-5 for the other legs, so gate the provenance) · **a 1000-step global vegetation-carbon trajectory exists
for both seeds** (`vegc_spinup_1999.nc`) · **the bad-years counter + all four hazards are in the rung-2
dumps.**

**Do NOT redo** the six investigations or their refutations. Transcript:
`~/.claude/projects/-p-projects-open-Jamir-wt-O/d1fedf05-84e7-49aa-8351-cc3c0206c27b/subagents/workflows/wf_1392bef9-337/journal.jsonl`
(one `{"type":"result"}` line per agent), replayable from cache with
`Workflow({scriptPath: '…/pure-data-driven-emulator-feasibility-wf_1392bef9-337.js', resumeFromRunId: 'wf_1392bef9-337'})`.
⚠ **ADR 0310 §10 lists five OPEN disagreements between an investigator and its reviewer — quote neither side
of any of them as fact**, in particular whether the measured −0.226 response inversion bounds a closed
rollout from below or from above (it changes the prior on the whole question).

**Housekeeping owed on this line's first working session:** none — the line was bootstrapped complete
(charter, block, worktree, hook entry, index rows). Just refresh this block before you end.

---

## Milestones

**X1 — the purely-data-driven direction (OPEN, owner conversation).** ADR 0310. Status: explored, adversarially
reviewed, no decision. Awaiting the owner.

**X2 — round 2: is a MORE data-driven emulator feasible? (OPEN, owner conversation, HALF-MEASURED).** ADR 0311
+ `docs/notes/exploration_data_driven_literature.md`. Status: three of six planned measurements done, two of
them adversarially verified (both `NARROWED`, neither refuted), one unverified. **What would have to be true to
promote it:** (a) the warming-response signal that survives blocked folds must also survive a **bracketed
held-out forcing leg** — the only design with published precedent — because within one scenario the forcing is
**76.4 %** predictable from the baseline climate and so is not separately identified; (b) the per-tree
hidden-state propagation result must survive its **unrun** adversarial verifier; (c) the per-cell conjunctive
pass rate must move from **7.2 %** toward the acceptance criterion, on a reference at acceptance-grade patch
count, not at 25; and (d) somebody must price the **middle** of the spectrum, which is what the owner's word
*"more"* asks about and which no record yet covers.

*(Future explorations append here. One subsection each: the question, what the owner said, what was measured,
what would have to be true to promote it.)*

---

## Line X gotchas

* **The SessionStart hook is generic over `line/*`** — it reads `lines/<letter>/STATE.md` and needs no
  per-line code. Only the integrator-worktree hint list names worktrees explicitly, and `wt-X` was added
  there when the line was created.
* **Read `EXECUTION_PLAN.md` before proposing a direction change** — it is the owner-approved order of work
  and it is **integrator-owned**. A line raises a change to it; it never edits it.
* **`scripts/*.py` is not linted by CI.** Lint any probe yourself with the repo's real rule set:
  `ruff check --select E,F,I,UP,B --line-length 100 scripts/explore_<x>.py`. `B905` (a `zip()` without
  `strict=`, which silently truncates) and `B023` (a closure over a loop variable) catch real defects in
  exactly the paired-array comparisons an exploration does constantly.
* **Path-filtered CI (ADR 0090):** a line-X commit is normally prose + `scripts/*.py` only, which triggers
  **no gate at all** — so there is no verdict to wait for and the merge can proceed as soon as it is pushed.
  Decide the expected set from `git diff --name-only origin/main...HEAD` against CLAUDE.md §5's table.
