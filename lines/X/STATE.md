# LINE X — project direction & exploration (branch `line/X`, worktree `wt-X`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/X/JOURNAL.md` (append-only). Decisions: tier-1 block
> **0310–0329**, opened by **ADR 0310**. **Next free number: 0311.**
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

### 0✦ 💬 THE OPEN CONVERSATION: could a PURELY data-driven emulator replace the hybrid? (owner, 2026-08-19; **ADR 0310** — the record that opened this line)

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
