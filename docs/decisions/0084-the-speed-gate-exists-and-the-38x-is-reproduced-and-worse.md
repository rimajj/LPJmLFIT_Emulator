# ADR 0084 — the end-to-end speed gate exists, ADR 0093's 3.8× is REPRODUCED (and is 4.6× once Component S is actually in the loop), and 83 % of the emulator's runtime is one λ solve

* **Status:** accepted
* **Date:** 2026-08-14
* **Line:** O (block 0080–0089) · `EXECUTION_PLAN.md` §4 rung **5-pre**
* **Supersedes / corrects:** nothing is superseded. **ADR 0093 §2's Julia figures are CORRECTED in
  basis, not in magnitude** — its harness printed `TOTAL coupled S+F+E` while running **no Component S**
  (`bench_emulator.jl` left `run_coupled_cell`'s `slow` kwarg at its `nothing` default), and it divided a
  whole-process wall time by cell-years on the C side rather than taking the marginal rate. Both are
  fixed here; both make the gap *larger*, not smaller.
* **Related:** 0094 (per-year ESM speed is goal #2), 0093 (the cost anatomy), 0023 (the pinned `_t8`
  Component-S artifacts), 0057/0105 (the patch-ensemble basis), 0041 (a subset re-run is not a per-cell
  replica — why this is a timing measurement and never a fidelity one)
* **Reproducer (committed, and this is the deliverable):**
  `scripts/bench_speed_gate.jl` (Julia arm) · `scripts/bench_speed_gate_c.sh` (C arm) ·
  `scripts/profile_fdiff_hotspots.jl` (the attribution)
* **Evidence:** SLURM jobs `1792591` (Julia, `logs/O-speedgate.1792591.out`), `1792835` + `1792562`
  (C, `/p/tmp/jamirp/O_speedgate_c/*/bench.*.out`), `1792811` + `1793072` (profile,
  `logs/O-profile*.out`)

---

## 1. Context — every speed statement in this project rested on one unreproducible measurement

ADR 0094 made per-cell-year ESM speed goal #2. The only number behind it was a single session's
throwaway script on `/p/tmp` (`bench_emulator.jl`, job 1722379): **1.096** core-s per cell-year for the
emulator against **0.290–0.383** for the C binary it replaces. Nothing in the repository measured speed,
and nothing in CI could catch a regression — which is how a 3.8× regression survived ~40 sessions.

Two defects in that measurement had to be settled before anything could be built on it, and they pull in
opposite directions, so neither could be assumed away:

1. **Component S was never in the loop.** The label said `S+F+E`; the code ran F+E. S is annual, so its
   cost could have been negligible — or, since it deserialises a 50 MB decision forest and a 128 MB
   copula and samples recruits every year, it could have been large. Unmeasured either way.
2. **The C side was a naive ratio.** A whole-process wall time divided by cell-years includes MPI
   start-up, the restart-file read and output writing, all of which are per-*run* costs. That inflates
   the C's apparent per-cell-year cost and therefore *understates* the emulator's disadvantage.

## 2. THE MEASUREMENT — same cell, same patch count, one core

**Basis, stated in full because none of these numbers means anything without it.** Cell **42490**
(Hainich, 51.25 °N / 10.25 °E, global orderA 0-based index), **npatch = 25**, **1 core**, single thread
(`--threads=1`; `DRF.predict` is `Threads.@threads`-parallel, so a multi-threaded run reports a smaller
*wall* time for the same *core*-seconds). The emulator runs **2010–2019** (10 yr, the span of the
committed biome forcing); the C runs **2000–2019** (20 yr) from the shared 1999 spin-up-end restart.
The C figures are the **marginal** rate — the same cell block run at 10 and at 20 years, differenced, so
every per-run fixed cost cancels exactly.

| what | core-s per **cell-year** | basis |
|---|---|---|
| **LPJmL-FIT C, cell 42490 alone** | **0.2666** (marginal) · 0.3217 naive over 20 yr | job 1792835; per-run fixed cost 1.10 s = 17.1 % of the 20-yr run |
| **LPJmL-FIT C, cells 42480–42500 (21 cells)** | **0.2884** (marginal) · 0.3029 naive over 20 yr | job 1792562; fixed cost 6.10 s = 4.8 % — ADR 0093's own block |
| emulator, **F + E** (= exactly what ADR 0093 timed) | **1.1169** | job 1792591 |
| **emulator, full coupled S + F + E** (the production configuration) | **1.2329** | job 1792591 |

**Verdict: ADR 0093 is REPRODUCED, not refuted.** Its F+E arm reproduces to **+1.9 %** (1.1169 vs 1.096)
across 403 commits and a rebuilt C binary — which is itself the useful result, because it means the
per-tree cost has not drifted while line M has been working inside the fast core.

⚠ **The C binary is not the one ADR 0093 timed** — it was rebuilt on **2026-08-12** for line M's opt-in
`ind`-writer switches (ADR 0130), and the harness prints its mtime with every run for exactly this reason.
It does not affect the comparison: those switches are `#ifdef`-gated additions to the `ind` writer, and
the `ARM=min` arm used here emits only `grid` + `globalflux` — it never writes `ind` at all. The 21-cell
block reproduces ADR 0093's 0.290 at 0.303 naive / 0.288 marginal, which is the empirical confirmation.

**And on the corrected basis the gap is worse than published:**

| ratio | value | reading |
|---|---|---|
| ADR 0093's published figure | 3.8× | F+E only, against the C's naive rate |
| this record, like-for-like with ADR 0093 (F+E vs the 21-cell naive rate) | 3.69× | reproduction check |
| **production S+F+E vs the C at the SAME cell, marginal rate** | **4.62×** | **the number to quote** |
| production S+F+E vs the 21-cell block, marginal rate | 4.27× | |

Component S costs **9.4 %** at Hainich (1.2329 vs 1.1169) and **5.0–22.1 %** across the five biome cells
— real, and small enough that it was never the story. The energy closure E costs **0.9 %** (1.1169 vs
1.1069 for F alone). **The fast core is 99 % of the bill**, exactly as ADR 0093 said.

### 2a. The per-individual normalisation, and the caveat that must travel with it

The emulator's per-cohort-year cost is **flat across biomes** — 4.11e-3 to 4.31e-3 core-s per cohort-year
over cells spanning boreal Siberia to the Amazon, against ADR 0093's 3.998e-3. The C, at ADR 0093's
restart byte-accounting figure of **~149 in-memory individuals per patch at Hainich** (*not re-measured
here — carried from ADR 0093*), sits at 0.2666/(25 × 149) = **7.16e-5** core-s per individual-year
against its published 7.84e-5. Ratio: **58×** (ADR 0093 said 51×).

⚠ **This is the caveat that must accompany the end-to-end ratio in both directions.** The C carries ~149
individuals per patch; the emulator's roster is built from the `ind` writer's >5 m stems and carries
**10.9 cohorts** per patch — **13.7× less per-individual work**. So the emulator is 4.6× slower end-to-end
*while simulating an order of magnitude fewer individuals*. Neither number alone is honest: the
cell-year ratio is what an ESM pays, the per-individual ratio is what the engineering has to close.

### 2b. Against which atmosphere — the standing rule

`EXECUTION_PLAN.md` §0's allowances (**≤ 0.030** core-s per cell-year at T63-class, **≤ 0.0135** at
T31-class) are a **convention** — 10 % of a measured SpeedyWeather coupled cost — **not an owner
requirement.** Against a CMIP-class 1° atmosphere (~50 core-s per land-column-year) nothing binds at all.
Every speed claim from this line names its atmosphere. From 1.2329, T63-class needs **41×** and T31-class
needs **91×** (the plan's 37×/81× were computed from the S-less 1.096).

## 3. WHERE THE TIME GOES — 83 % is one λ solve, and the plan's premise about it is wrong

Sampling profile, Hainich, 53 004 samples, single core, `nlambda = 25`. Shares are of **total runtime**
and are inclusive per source line (the `perf report --children` view, so they are directly comparable
with ADR 0093's C profile). The C's corresponding figures are in the last column.

| # | share | what | where | the C |
|---|---|---|---|---|
| 1 | 98.0 % | `daily_step_canopy` — the per-individual daily loop | `fdiff.jl:1827` | `update_daily` 98.6 % |
| 2 | 87.9 % | **`photosynthesis`, all call sites** | `fdiff.jl:552` | `photosynthesis` 41.3 % |
| 3 | 86.2 % | the `solve_lambda` call site in the canopy loop | `fdiff.jl:2029` | — |
| 4 | **82.1 %** | **`g(λ)` — the residual closure inside `solve_lambda`** | `fdiff.jl:656` | `bisect` 33.3 % |
| 5 | **56.0 %** | **`dg = (g(λ+h) − g(λ−h)) / 2h` — the central-difference derivative** | `fdiff.jl:673` | — (the C has no derivative) |
| 6 | 27.7 % | `gλ = g(λ)` | `fdiff.jl:672` | — |
| 7 | **26.7 %** | `adt_pos = softplus(adt, βadt)` = `log1p(exp(β·adt))/β` | `fdiff.jl:612` | — |
| 8 | **26.5 %** | `^(::Float64, ::Float64)` — **all of it from the three q10 lines below** | `Base/math.jl:1213` | `__libm_pow_l9` 6.8 % |
| 9 | 24.1 % | the `softplus` body | `fdiff_smoothops.jl:46` | — |
| 10 | 15.0 % | `tau = tau25 * q10tau^((temp−25)*0.1)` | `fdiff.jl:561` | — |
| 11 | 11.7 % | `kc = kc25 * q10kc^((temp−25)*0.1)` | `fdiff.jl:559` | — |
| 12 | 7.1 % | `agd` co-limitation + `sqrt_floor` | `fdiff.jl:607` | — |
| 13 | 4.7 % | `ko = ko25 * q10ko^((temp−25)*0.1)` | `fdiff.jl:558` | — |
| 14 | 2.9 % | `smoothmin` (the conductance cap) | `fdiff_smoothops.jl:65` | — |

**The independent confirmation — the λ sweep.** `nlambda` is a *parameter* (`FDiffParams.nlambda`), so
the λ solve's end-to-end worth is measurable without touching a line of `src/`. Same 25-patch Hainich
decade, same process:

| `nlambda` | core-s / cell-yr | speed-up | Σ GPP vs `nlambda = 25` |
|---|---|---|---|
| 25 (shipped) | 1.0859 | 1.00× | — |
| 12 | 0.5995 | 1.81× | +2.06 % |
| 6 | 0.3748 | 2.89× | +2.06 % |
| 3 | 0.2644 | 4.10× | **−0.03 %** |
| 2 | 0.2255 | 4.81× | +2.04 % |
| 1 | 0.1879 | 5.77× | −0.35 % |

⇒ **the λ path is 82.7 % of the emulator's runtime** (1 − 0.1879/1.0859), and `nlambda = 1` still pays one
full 3-evaluation Newton step, so that is a **lower bound**. Two independent runs of this sweep (jobs
1793072 and 1793368, different nodes) give 82.7 % and 82.8 %, and **ΔGPP identical to three decimals in
every row** — so the non-monotonicity in the last column is a deterministic property of the solver, not
sampling noise.

Leaf-kernel microbenchmarks agree with that picture (job 1793368; indicative only — a kernel reached
through a closure is not inlined the way it is inside `daily_step_canopy`, so the absolute figures run
~2× high): `solve_lambda` at `nlambda = 25` costs **7601 ns** against **352 ns** at `nlambda = 1`, i.e.
**304 ns per Newton iteration**, which is three photosynthesis evaluations at the inlined price.

### 3a. ⚠ THREE THINGS THIS OVERTURNS OR ADDS

**(a) `EXECUTION_PLAN.md` §4's prescription for 5a is aimed at a defect that is not there.** The plan
says the C's λ *bisection* is 33.3 % of the C's runtime and proposes "a fixed-iteration or analytic λ
closure" for the Julia core. **`solve_lambda` (`src/fdiff.jl:655`) is already fixed-iteration.** The
excess is elsewhere and the plan does not mention it: the Newton derivative is taken by **central finite
difference**, so each of the 25 iterations costs **three** `photosynthesis` evaluations rather than one.
Counting the call sites in `daily_step_canopy`:

```
:1947  photosynthesis(comp_vm=true )   gp / conductance path                        1
:1956  photosynthesis(comp_vm=true )   layered low-light share (conditional)       0-1
:1994  photosynthesis(comp_vm=true )   vm for the λ solve                            1
:2029  solve_lambda → 25 iterations × 3 evaluations (central difference)           75
:2034  photosynthesis(comp_vm=false)   final assimilation at the solved λ            1
                                                                            ---------
                                                       TOTAL   78–79 calls per individual per day
```
against the C's **≤ 30** (`water_stressed.c:207`, one call per bisection step). So the fix is not "make
it fixed-iteration" — it is **stop paying 3 evaluations per iteration, and stop paying 25 iterations**.

**(b) 26.5 % of total runtime is three temperature-only power calls that are recomputed 78× per
individual per day.** `ko`, `kc` and `tau` (`fdiff.jl:558/559/561`) depend on **`temp` alone** — not on
λ, not on `apar`, not on `vm`, not on the individual. They are therefore invariant across every iteration
of the λ loop *and* across every individual in the patch on a given day, yet they are evaluated on each
of the ~78 calls. This is loop-invariant recomputation, not physics, and hoisting it is provably
bit-identical for the hoisted quantity.

**(c) The λ iteration's answer is not monotone in its own iteration count, and 22 of the 25 iterations
buy no accuracy this diagnostic can see.** Total GPP moves by up to **2.1 %** across
`nlambda ∈ {1,2,3,6,12,25}` **non-monotonically** — `nlambda = 3` lands within 0.03 % of `nlambda = 25`
while `nlambda = 12` and `6` sit 2.06 % away, i.e. the result depends on *which* iteration count, not on
*how many*. [ASSUMPTION, mechanism NOT verified] The likely cause is the degenerate low-light regime the
code's own comment describes (`fdiff.jl:660-668`: `dg ≈ 0` ⇒ the raw Newton step diverges and is absorbed
by the hard `clamp`), where the iterate can alternate between the bracket ends instead of converging.
**This is not a claim that the shipped λ is wrong** — it is a claim that "25 iterations" is not evidence
of convergence, and that anyone tightening the solve must establish convergence rather than assume it.
Line M is the right owner of that question and it is raised to them in §5.

## 4. DECISION

1. **The gate is the three committed scripts**, and every future speed claim in this project cites a run
   of them. `scripts/bench_speed_gate.jl` writes `logs/bench_speed_gate.csv` in a machine-readable form
   for a CI gate to threshold.
2. **The quoted headline number is `1.2329` core-s per cell-year, full coupled S+F+E, cell 42490,
   25 patches, 1 core, 2010–2019 — 4.62× the C binary on the same cell.** The S-less 1.096 is retired as
   a headline (it remains valid as the F+E arm).
3. **Rung 5a's first target is `solve_lambda` and the loop-invariant kinetics in `photosynthesis`,
   in that order** — 82.7 % and 26.5 % of runtime respectively. Both are `src/fdiff.jl`, which line M
   owns; a **named single-function hand-over is raised in §5** rather than taken.
4. **The patch ensemble stays last** (ADR 0093 §2 unchanged and now re-confirmed): the emulator's
   per-patch fixed cost is 1.5–11.3 % of a patch's total, so patch reduction scales as ~1/J with no
   Amdahl floor — it is a clean ~3× that can be taken at any time and is worth nothing to argue about now.

## 5. INTEGRATION POINT RAISED TO LINE M — hand over `solve_lambda` only

Recorded in `lines/M/STATE.md` and mirrored in `lines/O/STATE.md`. **Scope: the single function
`solve_lambda`, `src/fdiff.jl:655-677` — 23 lines — plus the three-line kinetics hoist at
`fdiff.jl:558-561`.** Nothing else in `src/fdiff.jl`, `src/fdiff_smoothops.jl` or
`src/components/fast.jl` is requested; line M keeps the file.

**Pre-registered equivalence criterion (written 2026-08-14, BEFORE the work, so it cannot be re-read
after seeing its arm).** The replacement is accepted iff **all six** hold:

| # | test | bar | why this bar |
|---|---|---|---|
| 1 | opt-out arm (flag off) | every committed ReferenceTests baseline **byte-identical** | guardrail 4 |
| 2 | direct solver equivalence | `‖Δλ‖∞ ≤ 1e-6` over a 10 000-point sweep of the `(fac, tstress, co2_Pa, temp, apar, daylength, vm)` box sampled from a real Hainich year | the *direct* proof; everything else is a proof about consequences |
| 3 | flux equivalence | `|Δ GPP| / GPP ≤ 1e-3` per cell-year on all 5 biome cells × 10 yr × 25 patches; `≤ 1e-4` in the annual mean | **20× tighter than the current solver's own iteration-count sensitivity (2.1 %)**, and three orders below the C's own two-run spread (7.6 % counts / 11.3 % vegc at npatch=25) ⇒ it provably cannot move a fidelity verdict |
| 4 | gradient | the Enzyme/ForwardDiff canopy gates stay green; `d GPP / d sla` agrees with the baseline to 1e-6 relative | an analytic derivative **changes the AD graph** — this is the actual risk, not the primal |
| 5 | conservation | water ~1e-12, carbon closure, energy ~1e-14 unchanged | existing CI gate |
| 6 | speed | **≥ 2.5×** on `scripts/bench_speed_gate.jl` arm F at Hainich | below that the risk is not worth taking; the sweep says 2.9–4.1× is available |

**What is NOT being claimed:** that the shipped λ or the shipped GPP is wrong; that the 2.1 %
iteration-count sensitivity is an error rather than a property of a damped solve near a degenerate
bracket; or that line M must act on this before clearing rung 4. This is a costed, self-contained,
provably-equivalent optimisation with a ready-made test — not a physics dispute.

## 6. INTEGRATION POINT RAISED TO THE INTEGRATOR — make speed a required CI gate

Workflows are integrator-owned (CLAUDE.md §9 Gap 3). Requested: a `perf` job that runs
`scripts/bench_speed_gate.jl` at **one cell, `BENCH_YEARS=3`, `--threads=1`** (≈ 25 core-s of work plus
artifact load) on the same path filter as `CI` (`src/**`, `ext/**`, `Project.toml`), and **fails on a
regression greater than 10 %** against a committed threshold. A performance regression should red CI like
a physics one. Two constraints that make this non-trivial and must be designed around, not ignored:

* **A GitHub runner is not the cluster.** The absolute number is not portable, so the gate must threshold
  a **ratio against a baseline measured in the same job**, or be pinned to a self-hosted runner. The
  cheapest correct form is a *relative* gate: run arm F at `nlambda = 25` and at `nlambda = 1` in the same
  process and assert the ratio stays in a band — that is machine-independent and catches exactly the class
  of regression that happened here.
* **The pinned `_t8` artifacts (180 MB on `/p/tmp`) are not available to a GitHub runner**, so the CI arm
  must be **F or F+E**, not S+F+E. The S+F+E number stays a cluster measurement.

Until that lands, the gate is manual and this ADR is its baseline.
