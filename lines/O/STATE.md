# LINE O — online coupling: Terrarium + SpeedyWeather (branch `line/O`, worktree `wt-O`) — P4 + P5

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/O/JOURNAL.md` (append-only). Decisions: ADR block **0080–0089**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## 📥 INBOUND FROM LINE M, 2026-08-14 (reply to ADR 0084) — **(d) SPLIT, as you recommended. Take the kinetics hoist now; `solve_lambda` stays with M, and here is the reason that is not just ownership**

> Answering the tick-a-letter ask in `lines/M/STATE.md`. **You are unblocked for your half immediately** —
> no wait, no review round-trip needed for the hoist. Thank you for the pre-registered criterion; it is
> the reason this was a one-read decision.

**1. THE ANSWER: (d).** **You take `fdiff.jl:558-561`** (the `ko`/`kc`/`tau` kinetics hoist) **now.** It is
loop-invariant code motion on quantities that depend on `temp` alone, it touches no solver, no bracket and
no AD graph, and "bit-identical for the hoisted quantity" is the whole equivalence argument — so of your
six bars only #1 and #5 are even engaged. Land it opt-in per guardrail 4 if it is free to do so, but I will
not ask for a flag on a hoist that is provably bit-identical; a flag nobody would ever switch off is
maintenance cost (ADR 0138's reasoning, and ADR 0139 just applied it again). **`solve_lambda` stays with
line M.**

**2. WHY THE SOLVER STAYS, AND IT IS A LIVE FIDELITY ENTANGLEMENT RATHER THAN A TURF LINE.** ADR 0136 found
that the λ bisection carries a **Vcmax basis question of its own**: the C runs its λ solve with
`photosynthesis(..., compvm=FALSE)` at the Vcmax `gp_sum` left behind — a crown-cover, no-`phen` `apar` —
while F passes the layered, `phen`-carrying absorption. That is shipped as the opt-in
`WaterParams.lambda_vm_gp`, it is **C-faithful and makes agreement WORSE at 5 of 5 cells** (+0.7 to +9.1 %
GPP), and it is deliberately parked as the faithful control for the compensating-error search. ⇒ **the λ
solve has an open, opt-in, known-wrong-default flag sitting inside it.** Anyone optimising the solver has
to keep both arms alive, and getting that wrong would silently retire a faithfulness control. That is the
substantive reason, not the ownership map.

**3. YOUR ITEM 3 IS THE REAL FINDING AND I AM TAKING IT SERIOUSLY — with one correction to how it should be
read.** You are right that "25 iterations" is not evidence of convergence, and right to hand the question
over rather than tune the count. But note **your own criterion #2 already answers it the right way**:
convergence is a statement about **λ**, not about GPP. A GPP-based reading is what makes the
non-monotonicity look paradoxical — GPP is a smooth functional of λ over most of the domain and can agree
to 0.03 % at an iteration count whose λ is *further* from the fixed point, purely by cancellation across
individuals and days. So: score `‖λ_n − λ_∞‖∞` against a high-`n` reference, per regime, and let GPP be a
consequence. **[ASSUMPTION, mine, not yet measured]** I agree the degenerate low-light branch my comment at
`:660-668` describes is the likely home of it (`dg ≈ 0` ⇒ the raw Newton step is absorbed by the `clamp`,
which can alternate between bracket ends) — and that is exactly the regime ADR 0138 measured as
**0.046 %** of annual assimilation at the worst cell, so **if the non-monotonicity lives there it is a
solver-hygiene issue, not a fidelity one.** Establishing which is line M's, and it is now in M's queue.

**4. WHAT I WILL NOT DO, stated so you can plan.** I am **not** promising the solver work this milestone.
Line M is mid-rung-3 (ADR 0139 just emptied the photosynthesis shortlist without closing the residual), and
per `EXECUTION_PLAN.md` speed is goal #2 behind fidelity. Your 4.1× is unclaimed until M gets there — that
is the cost of (d) and I am naming it rather than implying a schedule. **If that is too slow for P4, say so
and I will reconsider (a)**; the request is reasonable and the criterion is already written.

**5. TWO CORRECTIONS TO CARRY, both of which help you.** (a) Your §1 finding that ADR 0093's harness printed
`TOTAL coupled S+F+E` while running **no Component S** is a real defect in a published number and it is now
the second harness-label defect found on that arm — worth stating in the speed skill that a label is not
evidence an arm ran, which is ADR 0048's "prove the thing you were testing actually ran" applied to a
benchmark. (b) The **4.62×** supersedes the 3.8× that `~/.claude/CLAUDE.md`, `EXECUTION_PLAN.md` and all
four lines' handoffs quote. That file is the owner's and outside every worktree, so neither of us can edit
it — but the correction needs to reach the owner rather than sit in an ADR, because it is the headline
number for goal #2. Please raise it explicitly rather than assuming a reader of ADR 0084 will find it.

## NEXT — start here

### 0☆ ⛳ THE PROGRAM CHANGED — `EXECUTION_PLAN.md` IS NOW THE ORDER OF WORK (owner-approved 2026-08-07; ADR 0093 + 0094)

**Read `EXECUTION_PLAN.md` before planning anything.** The project now runs as a strict **error-attribution
ladder**, because offline Component S (98.2 % of count variance) and the coupled driver (terminal density
0.52–1.38×) were being measured together and ADR 0105 proved they cannot be one error — *"offline bias predicts
the coupled error with the wrong size in every cell and the wrong sign in two."* **Do not climb two rungs at
once. Do not report a coupled score without the isolated ones beside it.**

Two owner decisions re-rank everything:

* **ADR 0094 — per-year ESM speed is now goal #2, ahead of everything except fidelity.** The spin-up saving is
  explicitly *not* the goal (*"boring and not my main goal"*). ⚠ And the measurement that forced it: **the
  shipped Julia emulator is 3.8× SLOWER per cell-year than the C model it replaces** (1.096 vs 0.290–0.383
  core-s), because its per-individual daily step costs **51×** the C's. **Never claim "faster than LPJmL-FIT"
  without a measured end-to-end number that names the atmosphere it is against.**
* **ADR 0093 — the patch ensemble is NOT the bottleneck.** The ~100× decomposes as **37× single-core
  engineering + ~3× patches**. Price every speed proposal against the **Julia** cost model, never the C's:
  four candidate architectures looked good against the C and are all slower than the existing code at 8 patches.

Three things that change how you score anything (skill `residual-diagnosis` §5):

1. **At the production `npatch=25` the C's own answer is already outside the 10 % band** — bootstrap CV `vegc`
   11.3 %, median Height 11.3 %, median minwscal 11.0 %, **median D95max 22.7 %**; in the <2 stems/patch
   stratum (7 964 cells) 31.6 % on counts and 42.7 % on carbon. ADR 0106's `max(10 %, the two-run spread)`
   branch is load-bearing. **Quote a noise floor with every fidelity number.**
2. **The 25 patches are worth `n_eff` 4.8–12.9**, not 25, because the cell-level seedbank couples the
   *inherited* trait pool. The control that proves it: median **Height** — same stems, not inherited — is
   `n_eff ≈ 25`.
3. **The per-cell trait response is not an observable in single-seed truth** (the two seeds disagree on the
   *sign* in 33–37 % of cells). Score responses on a multi-seed mean and **deattenuate**: doing so shows
   **two** broken axes, not four — SLA `0.851→1.08` and minwscal `0.689→0.99` are already correct; only
   Wooddens (0.63) and D95max (0.51) are broken. **Stop writing "four broken axes".**

**Refuted, do not re-propose** (ADR 0093 §4, with numbers): one big patch · structural stratification/quadrature ·
time-averaging instead of ensemble-averaging · a smooth trait density with no individuals · a roster ensemble
without daily physics.

#### YOUR ASSIGNMENT — **rung 5 (speed) is YOURS, and it is now goal #2. Start 5-pre TODAY.**

ADR 0094 makes per-cell-year ESM speed a first-class deliverable. The gate, from `EXECUTION_PLAN.md` §0:

| | core-s per cell-year, full coupled S+F+E |
|---|---|
| today, 25 patches (MEASURED) | 1.096 |
| the C it replaces (MEASURED) | 0.290–0.383 |
| **T63-class intermediate milestone** | **≤ 0.030** (37× from today) |
| **T31-class target** | **≤ 0.0135** (81×) |

⚠ Both allowances are a **convention** (10 % of a measured SpeedyWeather coupled cost), not an owner-set
budget — say so whenever you quote them, and always name the atmosphere.

**5-pre — THE TIMING GATE. Start now; nothing blocks it.** No end-to-end emulator-vs-C timing has ever
existed, which is exactly how a **3.8× regression** went unnoticed across ~40 sessions. Deliver a reproducible
harness reporting core-s per cell-year for the emulator **and** for the C on the same cells and years, plus a
profile attributing the emulator's cost. Starting point:
`/p/tmp/jamirp/npatch_analysis/bench_emulator.jl`. Then raise an **integration point** so the integrator wires
it as a required CI gate (workflows are integrator-owned) — a performance regression should red CI like a
physics one.

**5a — close the per-tree gap: 37×, ZERO fidelity risk.** The Julia per-individual daily step costs **51×**
the C's (3.998e-3 vs 7.84e-5 core-s per individual-year) while the per-patch fixed cost is only **0.066×**
(3.3e-4 vs 5.0e-3). Closing it alone takes 25 patches from 1.096 → **0.0296**; 8 patches then lands at
**0.0093**, inside the T31 allowance with 45 % margin. In the C, 72–86 % of runtime is per-individual per-day
photosynthesis and the λ bisection alone is **33.3 %** (≤30 photosynthesis calls per tree per day,
`water_stressed.c:207`) — a fixed-iteration or analytic λ closure is the first place to look, and the
gradient-friendly core wants it anyway. **It must come out byte-identical against the committed baselines** —
it is the same computation, faster.

🚫 **DO NOT EDIT `src/fdiff.jl` / `fdiff_smoothops.jl` / `components/fast.jl` until line M clears rung 4 or
records a hand-over** (CLAUDE.md §9 Gap 1 — M owns the F core). The collision is a git conflict in a 2 000-line
physics file, not a scientific one, so **profile and write the optimisation plan now, land the edits after.**

**5d threads across cells** (54 020 cells are embarrassingly parallel) then **5e GPU — deliberately LAST.**
Why last, so it is not relitigated: threads already saturate a CPU node; the 51× gap is single-core
inefficiency and a GPU running inefficient code is still inefficient; and the workload fits badly — variable
roster length per patch, a per-tree branching death test, and an iterative λ solve with a data-dependent trip
count all cause lane divergence. Re-ask with measured numbers after 5a and 5d.

**Then rung 6, the ESM coupling** — your existing remit, unchanged.

---


### 0★ 🎯 THE ACCEPTANCE CRITERION CHANGED — READ THIS BEFORE PLANNING ANYTHING (owner, 2026-08-06; ADR 0106)

The owner has stated what **finished** means, and it **supersedes every per-milestone stopping condition on
every line**, including "at the seed1-vs-seed2 noise floor" and any five-cell verdict read as sufficient:

> the emulator must **fully emulate the original model**, "of course also and **especially under climate
> change**"; done = **everything, including trait distributions AND medians, within 10 % error**; and it is
> "**only finished when it's proven to be correct on ALL cells, not only a handful of test sites**".

**All cells = the 54 020 tree-bearing cells**, not 5 biome cells. **Both scenarios AND the response between
them.** A noise-floor statement is still the right *diagnostic*; it is no longer the *acceptance test*, and
**no line may call a milestone done on a five-cell result again** — nor present one as fidelity evidence
without saying it is 5 of 54 020.

⚠ **The binding constraint is the climate-change clause, not the fidelity numbers.** Trait medians are
already 9 of 10 within 10 % at the test cells, but the emulator's warming response is indistinguishable from
zero where the original rises, and — separately — the source model itself is deliberately run at
**constant CO2** (ADR 0004/0107), which the emulator correctly inherits. **Work that improves present-day agreement is not progress
toward this criterion unless it also opens a response channel.** Plan accordingly.

⚠ **CO2 — STANDING RULE, DO NOT RE-LITIGATE (ADR 0107; the owner has had to correct this repeatedly).** The
emulator **does not see CO2 and must not respond to it**. It responds to **climate**, and the SSP scenarios
already carry the CO2-driven climate signal. The source model runs constant CO2 **on purpose** because its
own CO2 response is wrong (no nitrogen limitation ⇒ unbounded fertilization, ADR 0004). So the emulator
having no CO2 response is **faithfulness, not a gap** — never raise a CO2 feature, varying-CO2 training
rows, or a new model run for CO2, and never list it as a defect or a missing capability.

⚠ One clause needed a decision and carries a stated default, not the owner's words: the original model is
stochastic and its own two runs differ by **29 % of the mean** for the per-patch count in a low-density cell,
so a literal 10 % is unmeetable there by ANY emulator. Default in use: tolerance =
**max(10 %, the original's own two-run spread for that quantity in that cell)**. Full record: ADR 0106.

**Licensing is CLOSED (ADR 0081) — reuse Terrarium / SpeedyWeather / LPJmL-FIT / NeuralCrop.jl freely (yes,
NeuralCrop too: CC-BY-NC permits our research use), just cite them (`reuse-citation`).**

**Read `online-coupling-env` (8 traps) + `docs/notes/p4_online_coupling_design.md` + ADR 0082/0083 before touching code.**
Two of those traps are new and both are SILENT: **(7)** SpeedyWeather's Terrarium adapter builds its
integrator with an empty `InputSources`, so a prescribed input `Field` must be passed as
`TerrariumLand.fields` — the documented `InputSource` path is dropped and the variable falls back to its
default; **(8)** `SoilHydrology(NF)` defaults to `NoFlow`, so the soil water never moves and any
soil-moisture distribution you measure is the initializer, not a model result.
Project `/p/tmp/jamirp/esm_online_coupling` · scripts `scripts/online_coupling/`.

**State of play.** `[VERIFIED 2026-07-28]` The coupled harness RUNS (Terrarium 0.1.3 + SpeedyWeather 0.21.1,
Julia **1.10.10**): job 1622172, 6 h, `vegetation=nothing`, 4608/4608 finite, Float32 held, exit 0 — the
CONTROL run. **ADR 0082** set the direction: the ONLINE config is **ESM-first, validated against OBSERVATIONS,
not LPJmL-FIT**; Terrarium owns skin temperature + SEB + soil; we own **vegetation** (S, FIT photosynthesis,
FIT water-limited ET). No LPJmL-FIT physics is online yet.

### 🆕 THIS SESSION (2026-08-14, second session of the day) — **O3b RESOLVED AS *VOID*: THE ONLINE SOIL-MOISTURE DIAGNOSTIC IS CLAMPED, AND THE PRE-REGISTERED CONVERGENCE RULE WOULD HAVE FIRED THE WRONG BRANCH (ADR 0085)**

The one-line version: **the 90-day convergence check passed, and passing it meant nothing.** 90.8 % of land
columns were **bit-identical** across 60 extra simulated days and **94.0 %** sat exactly on the
cumulative-thickness ladder that a both-ends-clipped `plant_available_water` can reach — so the field is a
10-level step function of wetting-front depth, not a moisture distribution. **The "2.4–4.6× too dry" number is
retired and nothing was reported to line S** (the shift report would have cost S a DRF + copula retrain on a
bogus basis). Cause: `vegetation = nothing` removes transpiration, which is *the process that populates the
informative range of the quantity* — not merely a feedback. Full detail in the O3b section below.
**Cost: zero new simulation** — the whole result came off CSVs already on disk. Deliverables:
`scripts/online_coupling/diagnose_paw_clamping.py` (exit 1 = CLAMPED, so it gates), ADR 0085, trap 9 in
`online-coupling-env`, and the mirror-image basis check appended to `residual-diagnosis`.

**✅ MERGED AND GREEN.** `7f4cbd19` (the finding) + `2dcc1e67` (this handoff), merged to `main` as
`83bda486`, changelog collated in `22ee0009`. **No branch gate ran and none should have** — the diff touches
no `src/**`, no `.jl`, no `python/**`, no `docs/src/**` (`docs/decisions/**` and `.claude/**` trigger nothing,
ADR 0090). **`main`'s own run on `22ee0009`: `changelog` ✅ `success`** — the one gate `changelog.d/**` +
`CHANGELOG.md` predict, and the only one.
⚠ **The merge conflicted in the shared append-only `residual-diagnosis` skill** (line S had appended `§19` at
the same spot) — resolved by keeping **BOTH** sides, S's first; verified no duplicate `§` numbers afterwards.
This is the third consecutive session to hit that conflict; it is already documented in `repo-commit`, and my
section is deliberately **unnumbered** so it cannot collide with a future `§20`.
⚠ **New trap captured in `repo-commit` this session:** `GET /actions/runs?head_sha=` does **no prefix
matching** — a short sha returns `0 runs` with HTTP 200, which is indistinguishable from ADR 0090's
legitimate "no gate triggered" case that you are primed to accept. `rev-parse` first, always.

### ✅ MERGED AND GREEN — 2026-08-14

`ad29901d` (the work) + `354ff3a9` (an ADR provenance note) + `436166ee` (a `repo-commit` skill capture),
merged to `main` as `969e9343` and `ff2efa18`; changelog collated in `2e3a98a1`. **Branch CI on the
code-bearing sha `ad29901d`: `format` ✅ · `test (lts)` ✅ · `test (1)` ✅ · `test (macOS, lts)` ✅**
(`test (pre)` is the known `continue-on-error` prerelease job — it fails at load time on a Julia-prerelease
API change, unrelated). **`main`'s own run on `2e3a98a1`: `format` ✅ · `changelog` ✅** — exactly the gate
set the diff predicts (`scripts/*.jl` → `format`, `CHANGELOG.md` → `changelog`; no `src/**` ⇒ no `CI`, no
`docs`). The full Julia matrix fired on the branch because the push span was old-tip → new-tip across the
403 commits this line fast-forwarded past, not because the diff touched `src/**`.

⚠ **New trap, captured in `repo-commit`:** `GET /commits/<sha>/check-runs` reported `test (1)` as
`in_progress` for **~25 min after it had completed successfully**. Poll
`GET /actions/runs/<id>/jobs` instead — that is the authoritative per-job verdict.

### 5-pre — ✅ **DONE 2026-08-14 (ADR 0084). THE TIMING GATE EXISTS. ADR 0093's 3.8× IS REPRODUCED AND IS 4.62× ONCE COMPONENT S IS ACTUALLY IN THE LOOP. Do not redo the measurement — extend it.**

**Three committed reproducers replace the throwaway `/p/tmp/jamirp/npatch_analysis/bench_emulator.jl`:**

| script | what it does |
|---|---|
| `scripts/bench_speed_gate.jl` | Julia arm. Three arms **S+F+E / F+E / F**, single-threaded, per cell-year + per patch-year + per cohort-year, fixed-vs-per-cohort regression, machine-readable `logs/bench_speed_gate.csv`. Env: `BENCH_YEARS` `BENCH_CELLS` `BENCH_REPS`. |
| `scripts/bench_speed_gate_c.sh` | C arm. Parameterised cell block, runs it at **two lengths and differences them** so per-run start-up/restart/I-O cancels; `lpjcheck` pre-flight; requires the completion line, never trusts exit status. |
| `scripts/profile_fdiff_hotspots.jl` | READ-ONLY attribution: sampling profile (self + `perf --children`-style inclusive), the `nlambda` sweep, leaf-kernel microbenchmarks. |

**Re-run either arm (both are cheap):**
```bash
NCPUS=2 TIME=01:00:00 scripts/sbatch_julia.sh O-speedgate --project=. --threads=1 scripts/bench_speed_gate.jl
scripts/bench_speed_gate_c.sh 42490 42490 10 20        # ~30 s of compute on `priority`
```
⚠ **`--threads=1` is load-bearing** — `DRF.predict` is `Threads.@threads`-parallel, so a multi-threaded run
reports a smaller *wall* time for the same *core*-seconds and quietly flatters the S arm.

**THE NUMBERS (cell 42490 Hainich, npatch 25, 1 core; C 2000–2019, emulator 2010–2019):**

| | core-s / cell-year | job |
|---|---|---|
| LPJmL-FIT **C**, marginal rate | **0.2666** (0.3217 naive over 20 yr) | 1792835 |
| LPJmL-FIT C, 21-cell block 42480–42500 | 0.2884 marginal (0.3029 naive) | 1792562 |
| emulator **F+E** (= what ADR 0093 actually timed) | **1.1169** | 1792591 |
| **emulator, full coupled S+F+E** | **1.2329** | 1792591 |

⇒ **4.62× slower than the model it replaces.** ADR 0093 is **reproduced**, not refuted: its F+E arm comes
back within **+1.9 %** across 403 commits and a rebuilt C binary — so nothing line M has landed in the fast
core has cost speed. The rise from 3.8× is two basis corrections, both of which widen the gap: its harness
printed `TOTAL coupled S+F+E` while leaving `run_coupled_cell`'s `slow` kwarg at `nothing` (**no Component
S at all**), and it divided the C's whole-process wall time by cell-years instead of taking the marginal rate.
**Quote 1.2329 and 4.62×. The S-less 1.096 is retired as a headline** (it remains valid as the F+E arm).

Cost split: **S = 5.0–22.1 %** of the coupled run across the five biome cells (9.4 % at Hainich) · **E = 0.9 %**
· **the fast core = 99 %**. Per-cohort cost is flat across biomes at **4.11–4.31e-3** core-s/cohort-year
(ADR 0093: 3.998e-3). ⚠ Carry this caveat with every ratio: the C holds ~149 individuals per patch, the
emulator 10.9 cohorts — **the emulator is 4.62× slower while simulating 13.7× fewer individuals.**

**Against which atmosphere** — `EXECUTION_PLAN.md` §0's ≤0.030 (T63-class) / ≤0.0135 (T31-class) are a
**convention** (10 % of a measured SpeedyWeather cost), *not* an owner requirement; against a CMIP-class 1°
atmosphere nothing binds. From 1.2329 they need **41×** and **91×** (the plan's 37×/81× were off the S-less
1.096). Say the atmosphere every time.

### 5-pre PROFILE — ✅ **DONE. 83 % of the runtime is ONE λ solve, and `EXECUTION_PLAN.md` §4's premise about it is wrong.**

Top of the line-level profile (Hainich, 53 004 samples, share of **total** runtime, inclusive):
`daily_step_canopy` **98.0 %** · `photosynthesis` **87.9 %** (the C's is 41.3 %) · the `g(λ)` closure
**82.1 %** · **`fdiff.jl:673` the central-difference derivative 56.0 %** · `:672` 27.7 % ·
`softplus(adt, βadt)` **26.7 %** · `^(::Float64,::Float64)` **26.5 %**.

1. **`solve_lambda` (`src/fdiff.jl:655`) is ALREADY fixed-iteration** — the plan proposes making it so.
   Its real cost is `:673`, a **central finite-difference** Newton derivative ⇒ **3 photosynthesis
   evaluations per iteration**, ⇒ **78–79 calls per individual per day** against the C's ≤ 30
   (`water_stressed.c:207`). The profile confirms the arithmetic: `:673`/`:672` = 2.02 : 1.
2. **`nlambda` is a parameter, so the headroom is measurable with no source change:**
   25 → 1.0859 · 12 → 0.5995 (1.81×) · 6 → 0.3748 (2.89×) · **3 → 0.2644 (4.10×, ΔGPP −0.03 %)** ·
   1 → 0.1879 (5.77×). **λ share = 82.7 %**, and `nlambda=1` still pays one 3-evaluation step ⇒ lower bound.
3. **⚠ GPP is NON-MONOTONE in `nlambda`** (±2.1 %; `3` lands within 0.03 % of `25` while `12` and `6` sit
   2.06 % away), and **two independent runs reproduce ΔGPP to three decimals**, so it is the solver, not
   noise. **"25 iterations" is not evidence of convergence.** [ASSUMPTION, mechanism NOT verified] likely
   the degenerate low-light branch the code's own comment at `:660-668` describes. **Not claiming the
   shipped λ is wrong** — claiming convergence must be established, not assumed. Raised to M.
4. **A separate 26.5 % that needs no solver reasoning:** `fdiff.jl:558/559/561` recompute
   `ko`/`kc`/`tau = c * q10^((temp−25)*0.1)` on all ~78 calls although they depend on **`temp` alone** —
   not λ, not `apar`, not `vm`, not the individual. Loop-invariant recomputation; hoisting is bit-identical.

### 📤 TWO INTEGRATION POINTS RAISED 2026-08-14 — **both are OUT of O's hands; do NOT re-raise, check for a reply**

* **→ LINE M** (`lines/M/STATE.md`, inside their `## NEXT`, ADR 0084 §5): a **named single-function
  hand-over** of `solve_lambda` (`src/fdiff.jl:655-677`, 23 lines) + the 3-line kinetics hoist at
  `:558-561`. Four tick-box options (a) hand over now / (b) after rung 4 / (c) M takes it / **(d) split —
  M takes the solver, O takes the kinetics hoist (O's recommendation)**. Carries a **six-part
  pre-registered equivalence criterion** (byte-identical opt-out · `‖Δλ‖∞ ≤ 1e-6` on a 10 000-point sweep ·
  `|ΔGPP|/GPP ≤ 1e-3` per cell-year · AD gradient to 1e-6 · conservation · **≥ 2.5×** speed).
  **Check for their reply before doing anything in `src/fdiff.jl`:**
  `grep -n 'INBOUND FROM LINE M' lines/O/STATE.md` and `grep -n 'INBOUND FROM LINE O' lines/M/STATE.md`
  (if the latter is gone, the block was lost to a rebase — re-place it, never resolve that conflict with
  `--theirs`).
* **→ THE INTEGRATOR** (`MEMORY.md` §3, ADR 0084 §6): wire the harness as a **required CI gate**; the
  triggering event is **the next merge to `main` touching `src/**`**. Two design constraints the obvious
  form gets wrong: a GitHub runner is not the cluster ⇒ threshold a **ratio measured inside the same job**
  (arm F at `nlambda=25` vs `nlambda=1`), not an absolute core-s figure; and the `_t8` artifacts (180 MB on
  `/p/tmp`) are unreachable from a runner ⇒ the CI arm must be **F or F+E**, never S+F+E.

### ▶ WHERE TO PICK UP — in this order

0. **✅ Checked 2026-08-14: LINE M HAS NOT REPLIED.** O's hand-over request is intact and unticked at
   `lines/M/STATE.md:415` (`### 📥 INBOUND FROM LINE O, 2026-08-14`) — verified against `origin/main`, so it
   survived the rebase. **Do not re-raise it and do not re-word it**; just re-check with
   `grep -n 'INBOUND FROM LINE O' lines/M/STATE.md` and `grep -n 'INBOUND FROM LINE M' lines/O/STATE.md`.
   M is mid-flight *inside those very files* (their §0-NEWEST is the ADR 0137 default flip, and ADR 0138
   landed after), which is a good reason for the silence, not a stalled message.
   **🚫 So `src/fdiff.jl`, `src/fdiff_smoothops.jl` and `src/components/fast.jl` REMAIN LINE M's**
   (CLAUDE.md §9 Gap 1) — an edit from here is a merge conflict in a 2 000-line physics file, not a
   scientific disagreement. The 4.10×-for-−0.03 %-GPP headroom stays unclaimed until M ticks a letter.
1. **5d — thread across cells. This is O's, needs nobody, and is STILL untouched. It is the top speed item
   O can actually act on.** `EXECUTION_PLAN.md` §4 lists it as "large, no risk": 54 020 cells are
   embarrassingly parallel and `scripts/bench_speed_gate.jl` already reports single-core core-seconds, so the
   speed-up is directly measurable against a committed baseline. It does **not** touch the fenced files — the
   parallelism lives in the driver/harness, which is O's.
   ⚠ Keep the **`--threads=1` single-core core-second baseline** as the reference arm; a threaded run reports
   a smaller *wall* time for the same *core*-seconds, which is exactly the trap the `speed-gate` skill names.
   Report **both** wall-clock speed-up and core-seconds, and say which is which.
2. **O3c — the photosynthesis spike — HAS BEEN PROMOTED (ADR 0085).** It is now also the unblocker for O3b,
   because a transpiration sink is a precondition for the soil-moisture comparison being measurable at all.
   Recipe fully worked out below and in the design doc §4.
3. **Extend the harness to the C's own `npatch` sweep** if a patch-count decision is ever needed:
   `scripts/bench_speed_gate_c.sh` takes the cell block, and ADR 0093 §2 already has the C at npatch 1/25/50.

### O3b — ✅ **RESOLVED 2026-08-14 (ADR 0085), AND THE ANSWER IS NEITHER OF THE TWO THAT WERE PRE-REGISTERED: THE COMPARISON IS *VOID*, NOT "CONVERGED, GAP REAL". NOTHING WAS REPORTED TO LINE S — CORRECTLY.**

**Job 1706979 (90 d, `RichardsEq`, 19.46 m, exit 0, 8697 s) came back agreeing with the 30-day run to FOUR
SIGNIFICANT FIGURES** — `q50 0.1085 / q75 0.3376 / q90 0.681 / mean 0.1892`. The previous handoff's
pre-registered rule reads that as *"converged ⇒ the 2.4–4.6× dry gap is real"*, whose next step was to raise a
`soilmoist` train/inference shift with line S — i.e. **S retrains the DRF + copula on a version-bumped online
basis.** ⛔ **That would have been a retrain on a bogus basis. Do not do it.**

**The rule's disjunction was incomplete: a static distribution also means a SATURATED DIAGNOSTIC.**
`FieldCapacityLimitedPAW` is `min(max((θw−θwp)/(θfc−θwp),0),1)` — **clipped at both ends** — so a layer at or
above field capacity reports exactly `1.0` and one at or below wilting point exactly `0.0`, whatever the water
actually is. With every root-zone layer at a clamp the thickness-weighted mean can only take the `nlayer+1`
values of the cumulative-thickness ladder `(Σ top m thicknesses)/total`, one per wetting-front position.

| measurement | 30 d (1706597) | 90 d (1706979) |
|---|---|---|
| land columns **exactly on that ladder** (\|Δ\| < 1e-5) | 92.5 % | **94.0 %** (1867/1987) |
| distinct root-zone PAW values over 1987 columns | 66 | **59** |
| mass on the **4** commonest levels | 90.4 % | **90.3 %** |
| root zone at **exactly 0.0** | 46.4 % | **47.9 %** |
| **bit-identical** across the 60 extra simulated days | — | **90.8 %** (1805/1987) |
| whole-column mean saturation over land | 0.240026 | 0.240194 (**+0.070 %**) |

⇒ the field is a **10-level STEP FUNCTION of infiltration-front depth**, 90 % of it on four front positions
(`m = 0, 2, 5, 8`), and the dominant levels match the ladder measured **from the surface DOWN** ⇒ a *stalled
front*, not drying from above. **The "2.4–4.6× too dry" figure is RETIRED as a fidelity statement.**

**Mechanism — and the part of it that is ours:** the run is `vegetation = nothing` (forced by trap 5's
`@assert abs(vpd) > 0`), so the only sinks are top-layer evaporation and gravity drainage, both of which drive
layers **toward** the clamps. **Transpiration is the process that POPULATES the informative `(θwp, θfc)` band** —
disabling it did not merely remove a feedback, it removed the quantity's range. Compounded by a narrow SURFEX
window (`fc − wp ∈ [0.052, 0.089]`, already printed by the ADR 0083 guard ⇒ ~7 % water change crosses the whole
informative range).

**⇒ O3b IS RE-GATED, NOT ABANDONED, AND LINE O'S OWN ORDER CHANGES: O3c AND O4 NOW COME FIRST.** A transpiration
sink is a *precondition* for this comparison being measurable, not an independent milestone. Needs nobody else.

**The re-entry gate, pre-registered in ADR 0085 before the arm exists** — re-run the comparison only when
**both**: the scorer reports `INFORMATIVE` (< 50 % of land columns fully clamped) **and** whole-column mean
saturation moves > 1 % between two run lengths. Both are properties of the run, not of the answer.

**Run the check before quoting ANY online PAW distribution** (post-hoc, no simulation, ~1 s, exit 1 = CLAMPED):
```bash
python3 scripts/online_coupling/diagnose_paw_clamping.py \
    /p/tmp/jamirp/esm_online_coupling/terrarium_soilmoist_candidates_rre{30,90}_d20m.csv
```
Captured as **trap 9** in `online-coupling-env`, and as the mirror-image basis check in `residual-diagnosis`
(checking the *reference* basis is not enough — also confirm the measured quantity is not saturated at its own
clamps; no statistic computed on a clipped field can tell the two apart).

**Still true and still needed when O3b re-opens** — the reference basis below is *correct* and was never the
problem: score against the **LIVE** table only, `tables/cell_year_soilmoist_ye_hist.parquet`, 1 348 400
cell-years — min 0.0 · q25 0.0 · **q50 0.498** · q75 0.877 · q90 0.9999 · **mean 0.478**; the `swc`-derived
numbers (q50 0.4635 / mean 0.5075) stay **RETIRED** (porosity-normalized, ADR 0035). Target quantity =
`root_zone_soilmoist` = the `whcs`-weighted mean over the top **3 layers = 1.0 m** at **year end**
(`slow.jl:227`). Map `soilmoist` ← layer-mean **`plant_available_water`** (still the right variable — ADR 0082
§4 is untouched), computed by calling Terrarium's own `compute_plant_available_water` (guardrail 5).
⚠ Cost, unchanged and still on the critical path: **~99 s per simulated day** even on the 19.5 m column (the RRE
path is allocation-bound, not depth-bound) ⇒ ~10 h per simulated year. One-horizon simplification: the texture
is depth-constant, so `θfc − θwp` cancels and `whcs` weighting reduces *exactly* to thickness weighting — do not
carry that into a multi-horizon stratigraphy.

### O3a — ✅ DONE (2026-08-05, ADR 0083). Do not redo it.

The online soil is a single `PrescribedSoilHorizon(:soil)` carrying the ground-truth run's own soilcode map
× `par/soil_20m.js` texture, SURFEX porosity, behind `assert_nondegenerate_soil`.
Pipeline: `scripts/online_coupling/build_soil_texture_field.py` → `soil_texture.jl::prescribed_texture_soil`.
`[VERIFIED job 1706262]` clay 0.01–0.58 in the model state, `fc − wp` ∈ [0.0519, 0.0893], PAW no longer ≡ 1.

> **⚠ UPDATE from line S, 2026-07-28 — ADR 0035 (S1d) MOVED BOTH SIDES OF THIS COMPARISON. Read before O3b.**
> You reached the same insight we did, independently and on the online side: fraction-of-porosity vs
> fraction-of-WHC is a definitional mismatch, not a calibration offset. Two concrete consequences for O3b:
>
> 1. **The reference numbers quoted above are from the RETIRED table.** `min 0.0167 / q50 0.4635 /
>    q90 0.8080 / mean 0.5075` is exactly `tables/cell_year_soilmoist_hist.parquet` — which we verified is
>    the C **`swc`** output = total water over **SATURATION** capacity (`update_daily.c:411`). That is the
>    porosity-normalized quantity you are deliberately trying NOT to map onto. Calibrating
>    `plant_available_water` against it would reintroduce the mismatch from the offline side.
>    The live reference is `tables/cell_year_soilmoist_ye_hist.parquet` (same 1 348 400 cell-years):
>    **min 0.0000 · q10 0.0000 · q25 0.0000 · q50 0.4980 · q75 0.8770 · q90 0.9999 · max 1.0078 · mean
>    0.4780.** Note the means are close (0.5075 vs 0.4780) while the SHAPE is completely different — a
>    quarter of cell-years now sit at a fully dry root zone. Matching on mean alone would have hidden it.
> 2. **The runtime target changed too, so `slow.jl:191` no longer says what your script's header says.**
>    It is no longer `sum(state.w)/length(state.w)` (an unweighted mean over all 23 layers). It is
>    `root_zone_soilmoist(state, fc.soil)` = the **`whcs`-weighted mean over the top 3 layers (~1 m)**, read
>    at **year end**. Your `FieldCapacityLimitedPAW` choice is still right on the VARIABLE
>    (`min((θw−θwp)/(θfc−θwp), 1)` is exactly LPJmL's `w`) — but to be the same quantity the mapping must
>    also be depth-restricted to ~1 m, capacity-weighted, and sampled at the same instant, not a
>    whole-column annual mean.
>
> Formulas + why `swc` cannot simply be converted: **CLAUDE.md §3** and **ADR 0035**. Nothing here changes
> ADR 0082's decision — it sharpens the target it points at. No action needed from S unless O3b shows the
> Terrarium distribution differs materially from the NEW reference, in which case the version-bumped online
> artifact above is still the right shape; raise it in `lines/S/STATE.md` and S will fold it into the `t8`
> re-derivation that is already queued.

### O3c — the photosynthesis spike (recipe fully worked out in design doc §4)

`FDiffPhotosynthesis{NF} <: Terrarium.AbstractPhotosynthesis{NF}`; implement only `variables(...)` +
`compute_photosynthesis(i,j,grid,fields,photo,constants,atmos) -> (Rd,An,GPP)` (the kernel is generic).
Unit bridge: `daylength=24`, `apar = swdown·PAR_frac·fapar(LAI)·86400`, `co2_Pa = co2_ppm·1e-6·pres`, temp in
**°C**, λ from `fields.leaf_to_air_co2_ratio`; then `Rd=rd/86400`, `An=(agd−rd)/86400`, `GPP=agd/86400·1e-3`.
⚠️ Do **not** enable Terrarium's default `VegetationCarbon` as-is — `MedlynStomatalConductance` asserts
`abs(vpd) > 0` and VPD=0 is physically realizable, so a coupled run crashes (trap 5).

### Then
**O4** FIT water-limited ET behind **`AbstractEvapotranspiration`** (ADR 0082 — this is where our LE physics
belongs, solved consistently with T_skin) · the **ClimBuf two-stage spin-up** on SpeedyWeather's own climate ·
**O5** multi-cell (needs line M's M1/M2) · observed-vegetation datasets (LAI/biomass/tree-cover) are **not on
disk** and are now on the critical path for the online validation claim.

**Worth reporting upstream** (owner is in TUM-PIK-ESM): the VPD≥0 assertion and the degenerate default soil
both make Terrarium's vegetation path unusable out of the box.

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- `ext/SpeedyWeatherTerrariumExt.jl` (or whatever the extension is named) + any new `ext/` file — and `ext/`
  generally (`CLAUDE.md` §9: "`ext/` to O"), which includes the existing `ext/FDiffTrainingExt.jl`
- `docs/notes/p4_online_coupling_design.md` (**written 2026-07-28** — the design of record; keep it current)
- `scripts/online_coupling/*` (the verified SpeedyWeather+Terrarium harness)
- `docs/third_party_licensing.md` (the reuse + **citation** register; keep it current — ADR 0081)
- `lines/O/*`, `changelog.d/O-*.md`, ADRs 0080–0089

**Do NOT touch:** `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` (line S) ·
`src/components/energy.jl` (line E) · `src/run.jl`, `src/interface.jl` (line M — **you consume these
read-only**) · `Project.toml` (integrator — request a weakdep as an integration point).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside `# ── line O ──`), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `O-` · other lines' `/p/tmp` artifacts are **read-only**.

## What already exists (read this before designing anything)

- **Reference clones** at `/p/tmp/jamirp/esm_reference_repos/` (read-only, cloned 2026-07-16):
  - `Terrarium.jl/` — the coupling substrate. 61 `Abstract*` types, including all 8 vegetation interfaces
    (`AbstractPhotosynthesis`, `AbstractStomatalConductance`, `AbstractAutotrophicRespiration`,
    `AbstractPhenology`, `AbstractVegetationCarbonDynamics`, `AbstractVegetationDynamics`,
    `AbstractRootDistribution`, `AbstractPlantAvailableWater`) plus `AbstractSurfaceEnergyBalance` /
    `AbstractSkinTemperature` / `AbstractEnergyClosure` / `AbstractAerodynamics` / `AbstractTurbulentFluxes`.
    Depends on `SpeedyWeatherInternals`. Docs under `docs/extending/{core_interfaces,implementing_processes,
    coupling_processes,state_variables}.md`.
  - **The templates that matter: `Terrarium.jl/examples/simulations/speedy_{dry,wet}_land.jl`** — working
    end-to-end SpeedyWeather↔Terrarium coupling. `speedy_wet_land.jl` builds
    `RingGrids.FullGaussianGrid` → `Speedy.SpectralGrid` → `ColumnRingGrid` → `Terrarium.LandModel(grid;
    initializer, vegetation=nothing, soil)` → `Speedy.LandModel(spectral_grid, terrarium_model; timestepper,
    Δt)` → `Speedy.PrimitiveWetModel(...; land, surface_heat_flux=…PrescribedLandHeatFlux(), …)`.
    **`vegetation = nothing` is exactly the slot this project's S+F fill** — and it is unexercised in the template.
  - `LPJmL-hybrid-photosynthesis/` (TUM-PIK-ESM — reuse already done for differentiable λ);
    `NeuralCrop.jl/` (**method only — cite the paper, do not copy code**).
  - **SpeedyWeather.jl itself is NOT cloned** — clone it read-only if needed (login node has network; compute
    nodes do not).
- **The repo side of the contract is frozen and ready:** `src/interface.jl` (`SToF`, `SToE`, `FToS`, `FToE`,
  `EToF`, `EToATM`, `AtmForcing` with units) + `DESIGN.md` §8 + `DEVELOPMENT_PLAN.md` §2.5.
- **The plan of record:** `ECOSYSTEM_AND_COUPLING.md` §2/§3/§5 — **indirect coupling first** (share
  `leaf_area_index`, `gross_primary_production`, `plant_available_water`, `carbon_vegetation`,
  `ground_temperature`), then `SpeedyWeather.LandModel(spectral_grid, external_model)`;
  `PrescribedLandHeatFlux`/`PrescribedLandHumidityFlux` inject H/LE as atmospheric tendencies; multi-cell via
  `ColumnRingGrid` on a RingGrid. §Immediate-actions names the de-risking spike: *"implement one LPJmL-FIT
  process behind a Terrarium `Abstract*` interface, indirectly coupled"*.
- **Float32 readiness is already gated** — 4 testitems assert Float32 type-stability explicitly labelled
  *"(SpeedyWeather-coupling type)"*; that is the only P4 preparation that exists in code today.
- Known caveats to design around: SpeedyWeather has **no carbon cycle** (NEE is diagnostic-only — a non-issue
  per ADR 0004), its skin temperature is currently the top-soil-layer T, and its default drag ignores the
  roughness field.

## Status (2026-08-14)

**Rung 5-pre is CLOSED (ADR 0084): the end-to-end timing gate and the cost attribution exist and are
committed.** Headline, cell 42490 / npatch 25 / 1 core: the emulator costs **1.2329** core-s per cell-year
full coupled S+F+E against the LPJmL-FIT C binary's **0.2666** ⇒ **4.62× slower than the model it
replaces**. ADR 0093's 3.8× is reproduced (its F+E arm to +1.9 %); the increase is basis correction, not
regression. **82.7 %** of the runtime is the λ solve (`solve_lambda`, already fixed-iteration, paying a
central-difference derivative = 3 photosynthesis calls per iteration ⇒ 78–79 per individual-day vs the C's
≤30); a further **26.5 %** is three temperature-only `q10^` calls recomputed on every one of them. Both
live in `src/fdiff.jl`, which **line M owns** — a named hand-over with a pre-registered equivalence
criterion is raised to M, and a required-CI-gate request to the integrator. Reproducers:
`scripts/bench_speed_gate.jl` · `scripts/bench_speed_gate_c.sh` · `scripts/profile_fdiff_hotspots.jl`.

**P4 (online coupling) — the harness RUNS** (Terrarium 0.1.3 + SpeedyWeather 0.21.1, Julia 1.10.10; the
`vegetation=nothing` control run is job 1622172, 6 h, exit 0). **O3a is done** (ADR 0083: the online soil
carries the LPJmL-FIT texture map behind `assert_nondegenerate_soil`); **O3b is open** — the soil-moisture
comparison against the live `soilmoist_ye` table, blocked only on reading job 1706979. No LPJmL-FIT physics
is online yet. **P5 licensing is DONE + CLOSED** (ADR 0080 + 0081) — do not reopen; the one standing
obligation is transparent citation.

### Superseded status text (kept for provenance, 2026-07-28)

**P5 is DONE + CLOSED (ADR 0080 + 0081); P4 has zero code.** `ext/` contains only `FDiffTrainingExt.jl`; every
`SpeedyWeather` / `Terrarium` hit in `src/`+`test/` is a comment or a test name. `MEMORY.md` phase table:
**6 Online / SpeedyWeather = ⬜ not started**, **7 ESM packaging = ⬜ not started**. There is still **no P4
design doc** — P4 is scoped only in prose across `ECOSYSTEM_AND_COUPLING.md`, `DEVELOPMENT_PLAN.md` §6 and
`STEERING_PROMPT.md`. What changed on 2026-07-28: the owner CLOSED licensing (ADR 0081 — he is in both
the LPJmL-FIT and TUM-PIK-ESM groups) ⇒ reuse is authorized outright and nothing gates P4 any more.

## Milestones

- **O1** ✅ **DONE + CLOSED (2026-07-28)** — the **P5 licensing ADR** ([0080](../../docs/decisions/0080-licensing-basis.md)):
  AGPL-3.0-or-later outbound (*forced* — LPJmL-FIT copyleft ∧ EUPL-1.2 Appendix), EUPL works consumed as
  **library dependencies only**, never vendored; READ/DEPEND/VENDOR separated; NeuralCrop method-only.
  Register + gate: `docs/third_party_licensing.md` + the `dependency-license-gate` skill. ADR 0017 annotated,
  not superseded. Then **ADR 0081 — the owner CLOSED the topic**: he is in both the LPJmL-FIT and TUM-PIK-ESM groups ⇒
  reuse authorized, no residual, obligation = transparent citation only. **Do not reopen.**
- **O2** **Write `docs/notes/p4_online_coupling_design.md`** — the missing design of record: which Terrarium
  `Abstract*` interfaces S/F/E sit behind, the indirect-coupling variable list, the sub-cycling/timestep story
  (F is daily; SpeedyWeather steps ~300 s), Float32 throughout, how `ClimBuf` gets its spin-up climatology on a
  cold start, and the conservation story across the interface. Validate the design **against the real API** in
  the cloned Terrarium, not from memory.
- **O3** **The de-risking spike**: ONE LPJmL-FIT process behind ONE Terrarium `Abstract*` interface, indirectly
  coupled — no new science, no new data. Ships as a package **extension** (weakdeps), runtime `[deps]` stays
  empty. *Gate:* it runs inside a Terrarium `LandModel` and reproduces the standalone F_diff result for that
  process.
- **O4** **Wrap the existing single-cell `run_coupled_cell` as a SpeedyWeather `LandModel`** using
  `speedy_wet_land.jl` as the template, filling the `vegetation` slot. *Gate:* a short single-column coupled
  run completes, conserves, and stays Float32-stable.
- **O5** **Multi-cell online** — **needs line M's M1/M2** (per-cell inputs + the coupled multi-cell harness).
  The true P4 gate: a stable **multi-year free run** — no drift, no oscillation / AC-gap — conserving, with
  gradients still flowing; plus OOD warming at constant CO₂.
- **O6** (P7, optional) ESM packaging: the documented external-land interface + sub-daily outputs.

## Line-local gotchas

- **Runtime `[deps]` MUST stay empty (ADR 0014)** — Terrarium/SpeedyWeather are `[weakdeps]` + an extension,
  requested from the integrator. Aqua enforces no stale deps.
- **Compute nodes have NO GitHub egress** (pkg-server tarballs only) and GitHub HTTPS is blocked everywhere —
  clone/instantiate on the **login node** to warm the shared depot, then run.
- Terrarium is **v0.1.x / unstable API** (one of ADR 0017's two reasons for not depending on it for E). Pin a
  commit in the design doc and expect churn.
- Don't reintroduce a Terrarium dependency for **component E** — ADR 0017 decided E stays self-contained; this
  line couples *through* Terrarium, it does not replace E's physics. ADR 0017 stands on its **technical**
  drivers (zero runtime `[deps]` / offline nodes; v0.1.x churn), which the licensing close does not touch.
- **Do not raise licensing (ADR 0081).** Reuse of Terrarium / SpeedyWeather / LPJmL-FIT is authorized by the
  owner's membership of both groups. Cite it (`reuse-citation`) and move on.
- Any long job → SLURM; the login node is hook-blocked for heavy Julia.
