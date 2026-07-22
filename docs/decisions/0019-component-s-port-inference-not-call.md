---
status: "accepted"
date: 2026-07-22
deciders: "Jamir Priesner (owner) — decision authority delegated to the engineering agent"
consulted: "ADR 0014 (empty runtime deps / AD is train-time), ADR 0018 (growth-ownership split), PROJECT_REVIEW_2026-07-22.md §4/§9 (P1); the P1 design workflow synthesis (docs/p1_s_in_loop_design.md); python/src/lpjmlfit_emulator/baseline.py (DirectEmulator)"
informed: "P1 implementation (src/components/slow.jl, src/slow_infer.jl, src/run.jl); MEMORY.md; JOURNAL.md"
---

# Component S: port inference to pure Julia (not call Python), and wrap the machinery (not port the DirectEmulator wholesale)

> **Status note.** `accepted` 2026-07-22 (companion to ADR 0018), under the owner's delegation of decision
> authority to the engineering agent — **reversible by a superseding ADR**. Full architecture + 10-step
> plan: `docs/p1_s_in_loop_design.md`.

## Context and Problem Statement

P1 wires the slow ML component **S** into the coupled Julia loop (the project's novelty; ADR 0018 fixes the
growth-ownership split — S owns distribution + demography, F owns representative-individual carbon growth).
The trained S artifact is the Python `DirectEmulator` (LightGBM + a hand-rolled Gaussian copula +
Poisson/negative-binomial count; `direct_emulator.pkl`, 262 MB – 1.1 GB). Two questions must be settled
before building: **(1)** run S by *calling* the trained Python model from Julia, or *port* its inference to
Julia? **(2)** port the `DirectEmulator` *wholesale*, or reuse only its *machinery* inside a new adapter?

## Decision Drivers

- Runtime `[deps]` must stay **EMPTY** (ADR 0014): `src/` is pure-Base Julia; AD/ML are train/test-time only.
- **Offline compute nodes** have no network at run time (CLAUDE.md §1) — nothing may provision or fetch at run.
- S must stay **outside the AD/gradient loop** (ADR 0014) — non-differentiability of S is fine.
- **ADR 0018**: S must be *recursive* and *demography-only*; it must NOT emit per-tree carbon (F owns that).
- The `DirectEmulator` is **climate-only, non-recursive**, and emits carbon fan-outs (agb/vegc/npp/LAI/
  D95/…) that are exactly what F now owns — a mismatch with the coupled contract (mapping in the design doc).

## Considered Options

- **Call Python in-process** (PythonCall/PyCall) with the trained pickle.
- **Port inference to pure Julia**; keep training in Python.
- **Port the `DirectEmulator` wholesale** vs **reuse only the machinery** in a new demography-only adapter.

## Decision Outcome

**Decision 1 — PORT inference, do not call.** Port S's *inference* to a pure-Base-Julia submodule
(`src/slow_infer.jl`): a LightGBM text-dump tree-walk evaluator, the `ResidualRegressor` empirical-quantile
marginals, the Gaussian copula sampler (precomputed Cholesky + hand-rolled `Φ`/`Φ⁻¹`), and Poisson/NB
samplers (Gamma-Poisson) on the `Random` **stdlib**. Training stays in Python. **Rejected:** PythonCall/
PyCall — CondaPkg provisioning needs network (fails on offline nodes) and adds a heavyweight runtime dep
(violates ADR 0014 + Aqua); likewise `LightGBM.jl`/`Distributions`/`SpecialFunctions` are runtime-dep
additions (`mean`/`std`/Cholesky are hand-rolled to avoid pulling `Statistics`/`LinearAlgebra`). Stdlib
(`Random`, `Printf`) is offline-safe — the empty-`[deps]` rule targets *package* deps.

**Decision 2 — WRAP the machinery, do not port the `DirectEmulator` wholesale.** Reuse the proven
primitives (ResidualRegressor, copula sampler, Poisson+NB count, GBDT tree-walk) but drive them from a
*new*, recursive, demography-only adapter (`DemographicSlowEmulator`, `src/components/slow.jl`) that
predicts a **target envelope** (count `N` + recruit trait distribution), which S converts into demographic
**rates** on persistent representative cohorts. **Rejected:** porting the `DirectEmulator` as-is — it is
non-recursive/climate-only (that is the "regenerate the distribution each year" Option A that ADR 0018
rejected), and its carbon fan-outs re-introduce the double-count with F.

## Consequences

- Good: empty runtime `[deps]` preserved; S runs offline from a committed artifact; S stays outside AD.
- Good: `grow_individual` is untouched — litter accounting is additive (`_turnover_litter`), so every
  committed baseline and the AD trainer stay byte-identical; the whole path is opt-in behind
  `run_coupled_cell(...; slow=nothing)` (default `nothing` ⇒ byte-identical).
- Good: dropping the carbon fan-outs shrinks the Hainich PFT-3 artifact to a few MB (git-committable;
  a global 7-PFT artifact would go to DVC/`/p`, never the login-node scratchpad).
- Bad: a documented **FToS-conditioning gap** — P1 ships climate-only trained weights while the interface
  is `bm_inc`-aware; `FToS` drives only the physical mortality/establishment *rate* channel until an
  FToS-conditioned retrain (out of P1 scope).
- Bad: the pure-Julia GBDT/copula numerics must match Python to ~1e-6 (guarded by a parity fixture; a
  LightGBM version string in the artifact header detects a dump-format change).
- Neutral: complements ADR 0014 (empty deps) and ADR 0018 (growth-ownership); supersedes nothing.

## More Information

Architecture, the 10-step implementation plan, the carbon-conservation strategy for the N-change handoff,
the speed-up measurement design, and the gate-3 distribution-match plan: **`docs/p1_s_in_loop_design.md`**.
ADRs are immutable once accepted — supersede rather than edit.
