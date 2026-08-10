# EXECUTION_PLAN.md — the current program, owner-approved 2026-08-07

**Read this after `CLAUDE.md` and before `lines/<X>/STATE.md`.** It is the *dated, executable* program:
which rung of the ladder your line is on, what decides whether you climb, and what you must not start yet.
`DEVELOPMENT_PLAN.md` stays the stable phased architecture; `STEERING_PROMPT.md` is older and its ordering
is superseded by this file. Evidence behind every number here: **ADR 0093**. The goal re-ranking: **ADR 0094**.

**Integrator-owned.** A line does not edit this file — it records progress in its own `STATE.md` and raises a
change here as an integration point.

---

## 0. The goal, in the owner's own ranking (ADR 0094)

> *"I want a fast emulator that can be run in an ESM without too much compute cost."* — owner, 2026-08-07,
> when told the spin-up saving was the project's measured compute case: *"the savings for the spin-up is
> boring and not my main goal."*

So the ranking is:

1. **A faithful emulator** — tree counts, trait distributions and trait medians within `max(10 %, the C's own
   two-run spread)` on all 54 020 tree-bearing cells, both scenarios, **and the response between them**
   (ADR 0106, unchanged and still binding).
2. **Fast enough to live inside an ESM.** This is now a **first-class deliverable, not a by-product.**
3. **Coupled to the ESM.**

**The speed target, stated as a gate so it can be measured:**

| gate | core-s per cell-year, full coupled S+F+E | speedup needed from today |
|---|---|---|
| today, 25 patches (MEASURED) | 1.096 | — |
| the C model it replaces (MEASURED) | 0.290–0.383 | 2.9–3.8× just to reach parity |
| **T63-class allowance (intermediate milestone)** | **≤ 0.030** | **37×** |
| **T31-class allowance (the real target)** | **≤ 0.0135** | **81×** |

⚠ The two allowances are a **convention** (10 % of a measured SpeedyWeather coupled cost), not an owner
requirement. They are the best available number; if the owner sets a different budget, this table changes and
nothing else does. Against a CMIP-class 1° atmosphere (~50 core-s per land-column-year) nothing binds at all —
**so always say which atmosphere a speed claim is against.**

**Never again claim "faster than LPJmL-FIT" without a measured end-to-end number.** As of 2026-08-07 the
emulator is **3.8× slower** than the model it replaces and nothing in the repo was measuring it.

---

## 1. Why a ladder, and not more of the same

Offline Component S explains 98.2 % of the variance in per-patch tree counts and 99.9 % of per-cell means.
The coupled driver is 1.35 / 1.15 / 1.38 / **0.52** / 1.04 × on terminal density across the five biome cells.
Those cannot both describe one error — and ADR 0105 records the proof: *"offline bias predicts the coupled
error with the wrong size in every cell and the wrong sign in two."*

**At least three error sources are being measured only in combination:** the learned demography, the fast
physics, and the feedback between them. Every rung below isolates exactly one. **Do not climb two at once.**

### The hypothesis this ladder exists to test (owner agreed, 2026-08-07)

**Compensating errors.** The demography model may have been tuned, implicitly, while the fast core was
biased — two errors that cancel at present-day and stop cancelling under a different climate. The evidence
that puts this in play: teacher-forcing the emulator with the C truth made the score **worse in all five
cells** (0.149→0.277, 0.086→0.153, 0.180→0.259, 0.349→0.460, 0.029→0.069). That is backwards.

⚠ **Therefore: if rung 1 scores WORSE than the coupled result, that is the finding, not a failed test.**
Pre-registered here so no session can reinterpret it later. It would also explain the flat warming response
directly, which makes it the highest-value single result available.

---

## 2. The ladder — ownership, entry, exit

| rung | what runs | isolates | line | gate to climb |
|---|---|---|---|---|
| **0** | re-score existing artefacts on a corrected yardstick | the **target** | **S** (+ integrator for the seeds) | a noise floor + a deattenuated response slope exist for all four trait axes and counts |
| **1** | S alone, fed the C's own per-tree fluxes | **S's demography** | **S** | rung-1 score reported *against the rung-0 noise floor*, with the compensating-errors verdict stated |
| **2** | S + the **real C** fast part, closed annual loop | **the feedback**, physics exact | **M** (S = contract counterpart) | the loop runs 20 yr on ≥5 cells and its score is reported next to rung 1's |
| **3** | F alone, fed the C's own canopy | **F's physics** | **M** | the decadal canopy drift is quantified and either fixed or bounded |
| **4** | S + F coupled | the residual | **M** | residual = rung1 ⊕ rung3 ⊕ loop, attributed |
| **5** | speed | — | **O** (+ M for the F core) | each sub-step byte-identical or explicitly opt-in |
| **6** | ESM coupling | — | **O** | — |

### What can run in PARALLEL right now

* **S** starts rung 0 today (existing artefacts, no new runs) and rolls into rung 1. Nothing blocks it.
* **M** can build the rung-2 harness **now**, in parallel with S's rung 1 — the harness build does not depend
  on rung 1's answer, only its *interpretation* does.
* **O** starts rung 5's **prerequisite** now: the end-to-end timing gate and the profile (§4). **O does not
  edit `src/fdiff.jl` until M clears rung 4 or explicitly hands the file over** (CLAUDE.md §9 Gap 1 allows a
  recorded hand-over) — the collision is a git conflict in a 2 000-line physics file, not a scientific one.
* **E** continues its own observational programme; it is **not on the critical path**. E is a required
  reviewer for rung 5b (§4) because sharing a soil column touches the ground-heat column E owns.

---

## 3. Rungs 0–4 in detail

### Rung 0 — fix the yardstick · line S · days, no new model runs

The emulator is being scored against **one roll of a stochastic model's dice**, and for two trait axes the
dice are louder than the signal. Deliver:

1. **A per-cell, per-quantity noise floor** from the two existing seeds, for counts, stand carbon and all four
   trait medians, **stratified by stem density** (the <2 stems/patch stratum is 7 964 cells at 31.6 % on
   counts / 42.7 % on carbon — it cannot share a tolerance with dense forest).
2. **The deattenuated response slope.** `λ = Var(true)/(Var(true)+Var(noise))` from the two seeds in both
   scenarios; report the raw slope **and** `slope/λ`. Already measured once: SLA `0.851→1.08`,
   minwscal `0.689→0.99` — **already correct**; only **Wooddens (0.63)** and **D95max (0.51)** are broken.
   Reproduce it properly, then **retire "four broken axes" from every document that says it.**
3. **A response score that is not per-cell single-seed.** The two seeds disagree on the *sign* in 33–37 % of
   cells while the area-mean carbon response has signal-to-noise ≈ 200. Define and publish an aggregate
   response metric (area-mean and/or biome-mean) as the primary, with per-cell as a reported secondary.

**Integrator, in parallel:** schedule **two more reference seeds** (~35 000 core-h ≈ 17 h on 2048 cores),
both scenarios. Gate each with `scripts/diagnose_ind_seed_independence.py`; a second seed is a second
**spin-up** (ADR 0041 — bumping `random_seed` under `-DFROM_RESTART` yields a byte-identical clone).

### Rung 1 — S alone, on the C's own fluxes · line S · no C/Julia mixing needed

**The `ind` parquet already IS the C's fast part** — per (Cell, Patch, Year) it carries each tree's growth,
water stress and four death rates. Feed those to the demography and ask: given perfect physics, does it
reproduce FIT's forest?

Run it as a **stated set of arms**, and report all of them:

* **A** — free-running (today's behaviour), the control.
* **B** — fed the C's own per-tree fluxes each year.
* **C** — B **plus** `trait_mortality` ON. This is the pre-registered flip test for that flag.
* **D** — C **plus** the bounded-Beta trait family replacing the copula marginals.

Cheap wins to fold in and measure separately, all from ADR 0093 §5:

* **The determinism dividend is free**: predict the ensemble *expectation*, not a draw. Worth **+2.9 to
  +14.4 pp** of cells inside the 10 % band at zero compute cost.
* **Bounded Beta on each PFT's own trait interval**: median per-cell KS **0.042–0.073** vs the shipped
  copula's **0.129–0.173** — 2–3× better, two moments, no fitting. `new_tree.c:38-61` reflects traits at the
  interval edges, which is why a bounded family is the right one.
* **`trait_mortality`**: keeping `mort_max(wooddens)` **per-individual** holds the wood-density selection
  differential at **0.98–1.06 across all seven PFTs** even with growth efficiency collapsed to a patch mean.
  Collapse `mort_max` too and it drops 47–100 % and **flips sign in PFTs 3, 5, 6**.

**FLIP CRITERION for `trait_mortality` (pre-registered, guardrail-4 corollary):** flip the default to ON if
arm C improves the **deattenuated Wooddens response slope** by ≥+0.10 over arm B **and** does not lose more
than 1.0 pp of cells inside the 10 % band on any of the four trait axes or on counts. Decide from arm C
against arm B only — not from a later arm, and not re-read after the fact (the ADR-0104 error).

### Rung 2 — S + the real C fast part · line M · the harness

**Narrow interface first — this is the recommendation the owner asked for.** Replace **only who dies and who
establishes.** Leave turnover, allocation and growth to the C. Reasons, in order of weight:

1. It keeps the C's internal per-tree accumulators intact — the running water stress, the growth-failure
   counter — which **three of the four death rates depend on** and which the emulator does not currently
   produce (`waterstress_tree.c:31-38`, `mortality_tree_ind.c:66-96`).
2. It halves the interface surface, so a failure is attributable.
3. Widening later is then its own experiment, one function at a time.

**Where to hook it.** The whole demography is one loop, `src/lpj/annual_natural.c:55-232` in
`/home/jamirp/lpjml56fit`: `annualpft` (turnover/allocation/mortality) at :73, `light` at :118 (**dead** under
`individual=true`), fire at :121-135, `establishmentpft_ind` at :145. Add an **opt-in config flag** that dumps
the patch roster + accumulated per-tree fluxes at the top of the block and reads a replacement roster at the
bottom. Precedent for the mechanics: `patches/lpjmlfit_daily_grass_gpp.patch` + rebuild
(skill `lpjmlfit-cbinary`). Per-year file I/O is free at a handful of cells.

**This is a throwaway test harness, not a deliverable.** Build it cheap. Its only job is to answer *is the
defect in S, in F, or in the loop?* Keep it opt-in so the stock binary stays byte-identical.

Fallbacks if the hook stalls: (b) step the C one year at a time through restart files, rewriting the restart
between years (needs a writer for `fwritecell.c` → `fwritestandlist` → `fwritestand` → `fwritepftlist`);
(c) link LPJmL as a shared library and `ccall` — **not worth it** (global state, MPI, its own I/O).

### Rung 3 — F alone, on the C's own canopy · line M

Partly exists (`fdiff-validate`). The open item is the **decadal canopy drift**: over 2010–2019 F's leaf
cover moves **1.56×** where the C's moves 0.90× (boreal), 1.27 vs 1.00 (Hainich), 0.71 vs 1.23 (Sahel).
Score **year-matched over a decade**, not as a 10-year-mean ratio, which hides drift. Read the ratio's
**shape**. Mandatory basis checks before comparing anything: `fdiff-validate` §the four basis checks.

### Rung 4 — coupled · line M

Only now is a residual attributable, because 1–3 are clean. Report the decomposition explicitly:
residual = (rung 1) ⊕ (rung 3) ⊕ (the loop). If the three do not add up, the loop is amplifying, and that is
a result worth its own ADR.

---

## 4. Rung 5 — speed, in the order the measurement forces · line O (+ M for the F core)

**This is now goal #2, not a tidy-up.** The order below is forced by the cost anatomy, not by taste.

| # | step | worth | risk | owner | notes |
|---|---|---|---|---|---|
| **5-pre** | **the end-to-end timing gate** | — | none | **O** | **start now.** See below. |
| **5a** | close the per-tree gap in the Julia core | **37×** | **none** | **O** after M clears rung 4 (or a recorded hand-over) | must be **byte-identical** against the committed baselines — it is the same computation, faster |
| **5b** | one shared soil column per cell | removes the floor that caps everything else at ~3× | low, measured | **M**, **E reviews** | share the soil column, **never** the canopy |
| **5c** | 25 patches → 8–12 | ~3× | small, quantified | **M** | `scripts/run_coupled_biomes.jl`; sd cost ×1.15–1.43 |
| **5d** | threads across cells | large | none | **O** | 54 020 cells are embarrassingly parallel |
| **5e** | GPU | re-ask with numbers | high effort, poor fit | **O** | **deliberately last** |

**5-pre, the standing gate O starts with.** No end-to-end emulator-vs-C timing has ever existed — which is
exactly how a 3.8× regression went unnoticed. Deliver a reproducible harness that reports core-s per cell-year
for the emulator and for the C on the same cells and years, and a profile attributing the emulator's cost.
Starting point: `/p/tmp/jamirp/npatch_analysis/bench_emulator.jl`. Then **the integrator wires it as a
required gate** (workflows are integrator-owned) so a performance regression reds CI like a physics one.

**Why 5a is worth 37× and carries no fidelity risk.** The Julia per-individual daily step costs **51×** the
C's (3.998e-3 vs 7.84e-5 core-s per individual-year) while its per-patch fixed cost is only **0.066×**
(3.3e-4 vs 5.0e-3). Closing that gap alone takes 25 patches from 1.096 → **0.0296**; 8 patches then lands at
**0.0093**, inside the T31 allowance with 45 % margin. In the C, 72–86 % of runtime is per-individual
per-day photosynthesis and the λ bisection alone is **33.3 %** (≤30 photosynthesis calls per tree per day,
`water_stressed.c:207`) — a fixed-iteration or analytic λ closure is the first thing to look at, and the
gradient-friendly core wants it anyway.

**Why the patch cut is LAST and not first.** Because patch reduction in the *emulator* has no fixed-cost
floor (unlike the C's 33 %), the ~100× decomposes as **37× engineering + ~3× patches**. Price every future
speed proposal against the **Julia** cost model: four candidate architectures looked good against the C and
are all **slower than the existing code at 8 patches** (ADR 0093 §2).

**Why GPU is last.** 54 020 independent cells already saturate a CPU node through threads; the 51× gap is
single-core inefficiency and a GPU running inefficient code is still inefficient; and the workload fits badly
— variable roster length per patch, a per-tree branching death test, and an iterative λ solve with a
data-dependent trip count all cause lane divergence.

---

## 5. Standing rules this program adds

1. **Every speed claim carries a measured end-to-end number and names the atmosphere it is measured against.**
2. **Every fidelity claim carries the target's own noise floor** for that quantity and stratum
   (skill `residual-diagnosis` §5).
3. **Response is scored on a multi-seed mean and deattenuated**; a per-cell single-seed response plot is
   mostly noise (signs disagree in 33–37 % of cells).
4. **Do not climb two rungs at once**, and do not report a coupled score without the isolated ones beside it.
5. **Refuted routes stay refuted** (ADR 0093 §4): one big patch (−81.3 % recruitment), structural
   stratification (variance-reduction 1.00–1.13 on traits), time-averaging (32–41 yr decorrelation), a smooth
   trait density with no individuals (flips the selection sign in 4 of 7 PFTs), a roster ensemble without
   daily physics (flips the minwscal selection sign). Re-proposing one of these needs new evidence, not a
   new argument.
6. **The emulator must not see CO2** (ADR 0107, closed, do not re-litigate).

---

## 6. Where each line records what

Unchanged from CLAUDE.md §9 — restated because this program spans all four lines:

| kind | destination |
|---|---|
| rung progress + the `## NEXT` handoff | `lines/<X>/STATE.md` (**yours only**) |
| narrative | `lines/<X>/JOURNAL.md` (append) |
| a decision | an ADR from **your** block (S 0100–0119 · M 0120–0139 · E 0140–0149 · O 0150–0159 · integrator 0094–0099) |
| a cross-cutting `[VERIFIED]` fact | `MEMORY.md` (additive) |
| changelog | a **new** `changelog.d/<X>-<slug>.md` |
| a change to THIS file, or to the rung ownership | an **integration point** — raise it, do not edit |

**Cross-line integration points this program creates, all of which must be recorded in BOTH lines' STATE.md:**

* **S → M (rung 2):** the demography entry point the C hook calls. S owns its shape; M owns the harness.
* **M → O (rung 5a):** the hand-over of `src/fdiff.jl` for performance work, after rung 4.
* **M → E (rung 5b):** the shared soil column touches E's ground-heat column.
* **any line → integrator:** the extra seeds, the timing gate becoming a CI gate, `Project.toml`,
  `scripts/sbatch_*`, `config/**`.
