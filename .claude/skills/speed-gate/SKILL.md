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
* **26.5 % is loop-invariant recomputation**: `fdiff.jl:558/559/561` recompute
  `ko`/`kc`/`tau = c·q10^((temp−25)·0.1)` on all ~78 calls although they depend on **`temp` alone**.

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
