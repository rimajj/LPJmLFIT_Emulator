---
name: speed-gate
description: Measure and defend the emulator's per-cell-year SPEED — the reproducible end-to-end timing harness for the coupled S+F+E emulator AND for the LPJmL-FIT C binary on the same cells and years, plus the profile that attributes the cost. Use whenever you are about to state, quote or challenge a speed number, a speedup, a core-seconds figure or an ESM compute budget; whenever you touch anything that could cost runtime (src/fdiff.jl, the canopy loop, the λ solve, the patch ensemble, threading); whenever a rung-5 item (5a per-tree, 5b shared soil, 5c fewer patches, 5d threads, 5e GPU) is proposed or scored; or whenever you need the C binary's own cost. Names scripts/bench_speed_gate.jl, scripts/bench_speed_gate_c.sh, scripts/profile_fdiff_hotspots.jl, logs/bench_speed_gate.csv, ADR 0084/0093/0094. Carries the four traps that make a speed number wrong rather than noisy — a naive whole-process wall time, a multi-threaded run reported as core-seconds, a harness whose label claims Component S while `slow=nothing`, and a cell-year ratio quoted without the per-individual normalisation that goes the other way.
---

# speed-gate — measuring per-cell-year cost, and not lying about it

**Speed is goal #2** (ADR 0094; the owner: the spin-up saving is *"boring and not my main goal"*). The
acceptance criterion (fidelity, ADR 0106) still outranks it and is untouched by anything here.

**STANDING RULE — never state a speedup without (a) a measured end-to-end number and (b) the atmosphere
resolution it is measured against.** `EXECUTION_PLAN.md` §0's allowances — **≤ 0.030** core-s per cell-year
at T63-class, **≤ 0.0135** at T31-class — are a **convention** (10 % of a measured SpeedyWeather coupled
cost), **not an owner requirement**; say so when you quote them. Against a CMIP-class 1° atmosphere
(~50 core-s per land-column-year) nothing binds at all.

## The three scripts

| script | arm | cost |
|---|---|---|
| `scripts/probe_c_patch_scaling.sh` | **the patch-scaling law of the C** — `cost(J) = a + b·J`, one spin-up per patch count (npatch is restart-pinned), two transient lengths differenced. Env: `NPATCHES` `SUBMIT` `ROOT` `REPS`. | ~20 min |
| `scripts/probe_c_patch_convergence.sh` | **how many patches each OUTPUT needs** — R independent seeds per patch count ⇒ the estimator's own CV, fitted as `c/√J`, then patches-needed for 10/5/2 %. Env: `NPATCHES` `SEEDS`. | ~40 min |
| `scripts/probe_c_genepool_diversity.sh` | **whether trait diversity collapses at low patch count** — the shared cell-level seed bank is sized `15.75 × npatch`, so few patches impoverish it. Reuses the scaling probe's restarts (`SRC`, `DEPEND=<jobid>`). | ~2 min |
| `scripts/bench_speed_gate.jl` | **the emulator** — three arms `SFE` / `FE` / `F`, per cell-year, per patch-year, per cohort-year, plus a fixed-vs-per-cohort regression. Writes `logs/bench_speed_gate.csv`. Env: `BENCH_YEARS` `BENCH_CELLS` `BENCH_REPS`. | ~4 min, 5 cells |
| `scripts/bench_speed_gate_c.sh` | **the LPJmL-FIT C binary** — parameterised cell block, generates its own config + jcf and submits. Env: `ARM=min\|ind` `SUBMIT` `PERF` `PARTITION` `QOS` `EXCLUSIVE` `ROOT`. | ~30 s–5 min |
| `scripts/profile_fdiff_hotspots.jl` | **attribution** (READ-ONLY): sampling profile, the `nlambda` sweep, leaf-kernel microbenchmarks + the per-individual-per-day call-count audit. | ~4 min |

```bash
NCPUS=2 TIME=01:00:00 scripts/sbatch_julia.sh O-speedgate --project=. --threads=1 scripts/bench_speed_gate.jl
scripts/bench_speed_gate_c.sh 42490 42490 10 20          # cell block, short years, long years
NCPUS=2 TIME=00:40:00 scripts/sbatch_julia.sh O-profile  --project=. --threads=1 scripts/profile_fdiff_hotspots.jl
```

## The baseline every new number is compared against (ADR 0084, 2026-08-14)

Cell **42490** (Hainich), **npatch 25**, **1 core**; C 2000–2019, emulator 2010–2019:

| | core-s / cell-year |
|---|---|
| LPJmL-FIT C, **marginal** rate | **0.2666** (0.3217 naive over 20 yr; 0.2884 marginal over the 21-cell block 42480–42500) |
| emulator **F+E** | **1.1169** |
| **emulator, full S+F+E** | **1.2329** ⇒ **4.62× slower than the model it replaces** |

S costs 5.0–22.1 % of the coupled run (9.4 % at Hainich) · E costs 0.9 % · **the fast core is 99 %**.
Per-cohort cost is flat across biomes at **4.11–4.31e-3** core-s/cohort-year.

## ⚠ TRAP 0 — STATE THE PATCH COUNT, OR THE NUMBER IS MEANINGLESS (ADR 0086, 2026-08-17)

**The single largest error this project has made about speed.** Every recorded speed verdict — ADR 0093's
"the patch ensemble is NOT the bottleneck", ADR 0084's "patch reduction is a clean ~3× worth nothing to
argue about now", and line O's kill of the few-patch→many-patch surrogate — was computed at
**`npatch = 25`**, because that is what the committed ground truth used. **Publication-grade LPJmL-FIT runs
use ~500 patches per cell** (owner, 2026-08-17); 25 was a testing convenience. All three verdicts invert.

Measured (`scripts/probe_c_patch_scaling.sh`, cell 42490, 1 core):

```
cost(J) = 0.00404 + 0.013398 · J     core-s per cell-year      ⇒  J=500 : 6.70 core-s
          ^^^^^^^ everything outside the patch loop = 0.06 % of the bill at J=500
```

⇒ at the production configuration **99.94 % of LPJmL-FIT is the patch ensemble**, the ceiling on patch
reduction is **1658×**, and 500→25 is 19.8×, 500→10 is 48.6×, 500→5 is 94.4×. Every other lever in this
skill is a rounding error beside it.

**So: a *multiplicative* configuration knob must be quoted with every speed number, exactly as the cell and
the core count already are.** `npatch` is restart-pinned (`newgrid.c:477` is the non-restart branch), so a
`-DFROM_RESTART` run silently uses the restart's patch count and ignores the config — pointing five configs
with five `npatch` values at one restart times **the same 25 patches five times**. `probe_c_patch_scaling.sh`
pays for one spin-up per patch count for exactly this reason.

⚠ **And which output you are converging matters more than the patch count itself.** Measured, 10-yr means
at Hainich: gross carbon uptake varies **4.2 %** and net primary production **1.7 %** between 1 and 25
patches, while vegetation carbon varies **34 %**, net ecosystem production **41 %** and establishment
**97 %**. The atmosphere-facing fluxes barely need patches; the forest structure needs all 500. Never quote
"how many patches are needed" without naming the quantity.

## ⚠ THE FOUR TRAPS — each makes a speed number WRONG, not noisy

**1. A whole-process wall time ÷ cell-years is an UPPER bound, not the rate.** It carries MPI start-up,
the restart-file read and output writing, which are per-*run*. Measured: at one cell those are **17.1 %**
of a 20-year run. `bench_speed_gate_c.sh` therefore runs the same block at **two lengths and differences
them**, which cancels every fixed cost exactly. Quote the **marginal** rate; quote the naive one only when
reproducing ADR 0093.

**2. A multi-threaded run is not core-seconds.** `DRF.predict` and `DRF.fit_forest` use
`Threads.@threads`, so a threaded run reports a smaller *wall* time for the same *core* time and flatters
the Component-S arm. **Always `--threads=1`** — note it beats the env var, which `sbatch_julia.sh` sets
to `NCPUS`. `bench_speed_gate.jl` warns if `nthreads() != 1`; do not ignore it.

**3. Read the harness, do not trust its labels.** ADR 0093's `bench_emulator.jl` printed
`TOTAL coupled S+F+E` and ran **no Component S** — `run_coupled_cell`'s `slow` kwarg was left at its
`nothing` default. That one omission is the whole difference between the published 3.8× and the real
4.62×. Before quoting any benchmark, grep it for the kwarg that switches the component you think it ran.

**4. A cell-year ratio and a per-individual ratio point in OPPOSITE directions, so quote both.** The C
carries ~149 in-memory individuals per patch at Hainich; the emulator's roster comes from the `ind`
writer's >5 m stems and carries **10.9 cohorts** — **13.7× less per-individual work**. So the emulator is
4.62× slower end-to-end *while simulating an order of magnitude fewer individuals*, and its per-individual
step costs **58×** the C's. The cell-year ratio is what an ESM pays; the per-individual ratio is what the
engineering has to close. Neither alone is honest.

## Where the emulator's time actually goes (ADR 0084 §3)

`daily_step_canopy` **98.0 %** · `photosynthesis` **87.9 %** (the C's is 41.3 %) · the `g(λ)` closure
**82.1 %** · **`fdiff.jl:673`, the central-difference Newton derivative, 56.0 %** · `:672` 27.7 % ·
`softplus(adt, βadt)` 26.7 % · `^(::Float64,::Float64)` **26.5 %**.

* **`solve_lambda` (`src/fdiff.jl:655`) is ALREADY fixed-iteration** — `EXECUTION_PLAN.md` §4 proposes
  making it so. Its cost is that it takes the Newton derivative by **central finite difference**, so each
  of 25 iterations costs **three** `photosynthesis` evaluations ⇒ **78–79 calls per individual per day**
  against the C's ≤ 30 (`water_stressed.c:207`).
* **`nlambda` is a parameter**, so the λ solve's worth is measurable with **no source change**:
  25 → 1.0859 · 12 → 0.5995 · 6 → 0.3748 · **3 → 0.2644 (4.10×, ΔGPP −0.03 %)** · 1 → 0.1879.
  **λ share = 82.7 %.** This trick — sweep the parameter instead of editing the code — is the general
  move whenever a hot region is behind a knob, and it works from a line that does not own the file.
* ⚠ **GPP is NON-MONOTONE in `nlambda`** (±2.1 %, reproducing to three decimals across independent runs),
  so **"25 iterations" is not evidence of convergence.** Establish convergence before tightening a solve.
* **26.5 % is loop-invariant recomputation**: `photosynthesis` recomputes
  `ko`/`kc`/`tau = c·q10^((temp−25)·0.1)` on all ~78 calls although they depend on **`temp` alone**.
  **The SEAM for this now exists and is in `main` (ADR 0087):** `FDiff.photo_kinetics(p, temp) ->
  (fac_kin, gammastar)` plus a `kin` kwarg on `photosynthesis` whose default recomputes it, so every call
  site is bit-identical (gated bitwise with `===` by `test/testitems/o_photo_kinetics_seam_tests.jl`).
  ⚠ **It is worth 0 % on its own and is deliberately INERT** — the 78 calls originate in the `g(λ)` closure
  *inside* `solve_lambda`, so realising the **≈1.36×** needs two lines there, in **line M's** file. Do not
  quote the 1.36× as achieved; it is arithmetic, not a benchmark.

  ⚠ **And do not cite a hot line by NUMBER out of this skill.** Every `fdiff.jl` line number in the
  profile above has already moved twice — M's ADRs 0135–0139 shifted the kinetics by +13 lines between the
  profile being taken and the seam being landed, so the "`:558/559/561`" this bullet carried for four days
  pointed into `_sla_vm_cap` by the time anyone reopened it. **Grep for the expression** (`q10ko`,
  `photo_kinetics`, `central-difference`) and re-derive the line, or you will price the wrong code.

## Two gotchas in writing a benchmark here

* **Build everything the kernel does not vary over OUTSIDE the timed closure, and consume the result.**
  The first version of `profile_fdiff_hotspots.jl` constructed `params_nlambda(1)` *inside* the timed
  loop and reported `nlambda=1` as **slower** than `nlambda=25` — physically impossible, and that
  impossibility is the tell. A closure-called kernel is also not inlined the way it is inside
  `daily_step_canopy`, so absolute ns figures run ~2× high: read microbenchmarks as *order*, and let the
  parameter sweep carry the attribution.
* **`@printf` needs a literal format string.** `@printf("a\n" * "b\n", x)` throws
  `ArgumentError: First argument to @printf after io must be a format string` — at *runtime*, i.e. after
  the expensive part has already run. Split into `@printf` + `println`.

## The fence — who may edit what

`src/fdiff.jl`, `src/fdiff_smoothops.jl` and `src/components/fast.jl` are **line M's** (CLAUDE.md §9
Gap 1) and hold essentially all of the cost. **Profile and write the plan from any line; land the edits
only after a RECORDED hand-over.** The hand-over of `solve_lambda` was raised with a six-part
pre-registered equivalence criterion in ADR 0084 §5 — reuse its shape for any future one:
byte-identical opt-out · direct solver equivalence (`‖Δλ‖∞`) · flux equivalence with the bar justified
against the *existing* numerical ambiguity · **AD gradient** (an analytic derivative changes the AD graph
— that is the real risk, not the primal) · conservation · a minimum speed-up below which the risk is not
worth taking.

## If you are wiring this into CI (integrator)

Two constraints the obvious design gets wrong: a GitHub runner is **not** the cluster, so threshold a
**ratio measured inside the same job** (arm F at `nlambda=25` vs `nlambda=1`) rather than an absolute
core-s figure; and the pinned `_t8` artifacts (180 MB on `/p/tmp`) are unreachable from a runner, so the
CI arm must be **F or F+E**, never S+F+E.

## ⚠ A HARNESS LABEL IS NOT EVIDENCE THE ARM RAN — CHECK THE ARM'S OWN SWITCH (line M's ask, ADR 0084 §1; 2026-08-14)

This is ADR 0048's *"prove the thing you were testing actually ran"* applied to a benchmark, and on this
arm it has now fired **twice**, which is why it is a standing check rather than an anecdote.

ADR 0093's harness printed `TOTAL coupled S+F+E` while calling `run_coupled_cell` with its **`slow` kwarg
left at the `nothing` default** — i.e. no Component S in the loop at all. The label was the only evidence
the arm existed, and it was wrong: the published headline (**3.8× slower than the C**) was an F+E number
wearing an S+F+E label, and the real figure is **4.62×**. Nothing detected it for ~40 sessions, because a
benchmark has no oracle — an arm that silently does less work returns a *better* number and looks like
success.

**So, for every arm in a timing table, assert the arm from the inside, not from its name:**

* **A defaulted-off component is the failure mode.** Grep the harness for the component's own switch
  (`slow=`, `energy=`, `per_pft_params=`, a `nothing` default) and assert it is populated — `@assert
  fc.slow !== nothing` beside the timing call costs nothing.
* **Assert a quantity only that arm can produce.** S+F+E must move a count/trait the F+E arm cannot touch;
  if arm S+F+E and arm F+E return the *same* number for such a quantity, one of them is mislabelled. This
  is the cheap oracle a benchmark otherwise lacks.
* **Publish the per-arm cost SHARE, not just the totals.** ADR 0084's `S = 5.0–22.1 %` is what makes a
  zero-cost S arm visible at a glance; a table of totals hides it.
* **Sanity-check the ratio between arms.** Two arms whose totals agree to a fraction of a per cent are
  probably the same arm run twice.

⚠ **And the corollary for the C side of any ratio: use the MARGINAL rate, not the whole-process wall time.**
The same ADR corrected a second defect in the same published number — dividing the C's total wall time by
cell-years charges start-up, restart read and I/O to the physics. Run two lengths and difference them
(`scripts/bench_speed_gate_c.sh` does exactly this). Both corrections widened the gap, so the direction of
a harness error is not predictable — do not assume a sloppy baseline flatters the incumbent.
