# START HERE — LPJmL-FIT hybrid land-component emulator

A short pointer. It replaces the old 1,675-line handoff (retired 2026-07-22, P0 consolidation; full copy
in `docs/archive/`). Goal: be productive in **< 15k tokens**.

## Read in this order

1. **`CLAUDE.md`** — the durable runbook: paths, Julia/C-binary/Python/CI commands, every environment
   gotcha, the guardrails, and §8 the knowledge-capture discipline. *Read this first every session.*
2. **`MEMORY.md`** — current durable state: phase status, verified facts, the ADR index, open TODOs.
3. **`docs/decisions/`** — the ADRs (audit trail). `README.md` there is the index.
4. As needed: `STEERING_PROMPT.md` (the owner's orders P0–P6) + `PROJECT_REVIEW_2026-07-22.md` (the
   reasoning behind them); `DESIGN.md` (frozen schemas + the S↔F↔E interface contract §8);
   `DEVELOPMENT_PLAN.md`, `RESEARCH_SURVEY.md`, `ECOSYSTEM_AND_COUPLING.md`, `ENGINEERING_STANDARDS.md`.

`JOURNAL.md` (append-only narrative) and `CHANGELOG.md` (per-change story) are history — open them only
for the story behind a specific change, not to onboard.

## What this is (one paragraph)

A **hybrid, ESM-ready land component** from LPJmL-FIT: **S** = slow ML emulator of the per-cell trait/size
*distribution* (annual, the scientific novelty); **F/F_diff** = the fast, differentiable, conserving daily
biophysical core kept from LPJmL-FIT; **E** = a surface-energy-balance + skin-temperature closure LPJmL-FIT
lacks. It must run **offline** (emulate LPJmL-FIT faithfully) **and online** (coupled to SpeedyWeather).

## Where the project is (2026-07-22)

Phases 0–4 done: global dataset + water/carbon closure (P1); S offline baseline gate met, warm+dry OOD
fails as expected (P2); F_diff C-validated **on Hainich only** with verified gradients (P3); energy
balance E closes to 1e-14 W/m² and the end-to-end coupled emulator **runs** (P4). Phase 5 (multi-cell)
just started.

**The whole remaining project:** S is **not yet in the coupled loop** (the novelty is unrealized and the
speed-up unmeasured); E is **not validated against FLUXNET/PLUMBER2**; nothing runs multi-cell held-out or
online; wind/psurf forcing isn't sourced. Everything C-validated is **Hainich only** — single-cell is
scaffolding, not evidence. Say "Hainich only" wherever a result is single-cell.

## The one open gate

**P1 (put S in the coupled loop) is blocked on ratifying [ADR 0018](docs/decisions/0018-growth-ownership-split.md)**
— the growth-ownership split (F_diff owns representative-individual *carbon* growth; S owns the
*distribution + demography*). It is `proposed`; the owner ratifies (or overturns) it before P1 code lands.

## The golden rules (full list in CLAUDE.md §6)

- Tag claims `[VERIFIED]/[DECISION]/[TODO]/[ASSUMPTION]`; one ADR per non-trivial decision.
- Conservation is a CI gate (water ~1e-12, carbon, energy ~1e-14) — never merge on red.
- The C binary is the **oracle**; validate F_diff against it, not itself. Confirm a C path actually runs
  in the `individual=true` config before porting it.
- New physics is **opt-in, default byte-identical** until deliberately enabled.
- Before chasing a fidelity residual: state the reference basis + a falsifiable hypothesis, confirm the
  comparison basis, and time-box (the `residual-diagnosis` skill).
- Reuse-first (Terrarium / hybrid-photosynthesis / NeuralCrop); reimplementation needs an ADR.
- Capture reusable knowledge as you go and route it by type (CLAUDE.md §8).
