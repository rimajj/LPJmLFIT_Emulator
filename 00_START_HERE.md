# START HERE — LPJmL-FIT hybrid land-component emulator

A router, not a status page. Goal: be productive in **< 15k tokens**.


> ⛳ **THE ORDER OF WORK IS `EXECUTION_PLAN.md`** (owner-approved 2026-08-07; ADR 0093 + 0094). The project runs
> as an **error-attribution ladder** — rung 0/1 line S · rung 2/3/4 line M · rung 5 (speed) line O · line E off
> the critical path. Two owner decisions re-rank everything: **per-year ESM speed is now goal #2** and the
> spin-up saving is explicitly not the goal (ADR 0094), and **the shipped Julia emulator is 3.8× SLOWER per
> cell-year than the C model it replaces** — the ~100× needed decomposes as **37× single-core engineering +
> ~3× patches**, so the patch ensemble is the *last* lever, not the first (ADR 0093).

## 0. Which line are you? (read this first)

Work runs as **4 parallel session lines** (ADR [0028](docs/decisions/0028-parallel-session-lines.md) /
[0029](docs/decisions/0029-line-split-and-ownership.md)), one long-lived branch + git worktree each. **Your
line is the branch checked out in the directory you launched from**, and the `SessionStart` hook already told
you which one, along with your next action. If you skipped it: `git rev-parse --abbrev-ref HEAD`.

| Line | Branch · worktree | Scope | Start here |
|---|---|---|---|
| **S** | `line/S` · `wt-S` | Component-S science (the ML novelty) | [`lines/S/STATE.md`](lines/S/STATE.md) |
| **M** | `line/M` · `wt-M` | Multi-cell coupled S+F+E — P3 | [`lines/M/STATE.md`](lines/M/STATE.md) |
| **E** | `line/E` · `wt-E` | Component E vs observations — P2 | [`lines/E/STATE.md`](lines/E/STATE.md) |
| **O** | `line/O` · `wt-O` | Online coupling: Terrarium + SpeedyWeather — P4/P5 | [`lines/O/STATE.md`](lines/O/STATE.md) |
| — | `main` · `esm_land_emulator` | **Integration only** (merges, changelog collation, shared files, deps) | this file → `CLAUDE.md` §9 |

**Your line's `STATE.md` is the authority on what to do next** — its `## NEXT — start here` block is the
previous session's handoff. Do not plan from this file.

## 1. Read in this order

1. **`CLAUDE.md`** — the durable runbook: paths, Julia/C-binary/Python/CI commands, every environment gotcha,
   the guardrails, §8 knowledge capture, and **§9 the parallel-line protocol**. *Read this every session.*
2. **`lines/<X>/STATE.md`** — your line's scope, owned paths, do-not-touch paths, frozen cross-line contracts,
   milestones, and the `NEXT` action.
3. **`MEMORY.md`** — **shared** durable state only: the router, cross-cutting `[VERIFIED]` facts, the
   load-bearing ADR constraints, and the cross-line frontier map.
4. **`docs/decisions/`** — the ADRs (audit trail); `README.md` is the index and holds the per-line number blocks.
5. As needed: `STEERING_PROMPT.md` (the owner's orders P1–P6) + `PROJECT_REVIEW_2026-07-22.md` (the reasoning);
   `DESIGN.md` (frozen schemas + the S↔F↔E interface contract §8); `DEVELOPMENT_PLAN.md`, `RESEARCH_SURVEY.md`,
   `ECOSYSTEM_AND_COUPLING.md`, `ENGINEERING_STANDARDS.md`.

**History, not onboarding:** `lines/<X>/JOURNAL.md` (your line's narrative), the root `JOURNAL.md` (project
history to 2026-07-27 + integration entries), `CHANGELOG.md`. Open them for the story behind one change.

## 2. What this is (one paragraph)

A **hybrid, ESM-ready land component** from LPJmL-FIT: **S** = slow ML emulator of the per-cell trait/size
*distribution* (annual, the scientific novelty); **F/F_diff** = the fast, differentiable, conserving daily
biophysical core kept from LPJmL-FIT; **E** = a surface-energy-balance + skin-temperature closure LPJmL-FIT
lacks. It must run **offline** (emulate LPJmL-FIT faithfully) **and online** (coupled to SpeedyWeather).

## 3. Where the project is (2026-07-28)

Phases 0–4 **done**: global daily dataset + water/carbon closure; F_diff C-validated (Hainich) with verified
gradients; energy balance E closes to ~1e-14 W/m²; the end-to-end coupled emulator runs. **P1 is done** — the
flux-driven Component S is IN the coupled loop, conserving carbon to ~1e-12 gC (ADR 0018→0027), and the
**offline global S generalizes**: counts per-cell-mean r²=0.9994 (**at** the seed1-vs-seed2 noise floor),
held-out-by-scenario R²=0.9847, trait pooled marginals KS 0.004–0.015.

**What remains** (one line owns each — see the table above): E is **not validated against FLUXNET/PLUMBER2**
and wind/psurf are not model-ready (**E**); the **coupled** run beyond Hainich is F+E-only with `slow=nothing`,
and the resilience battery is 4 stubs (**M**); trait **per-cell medians** have real model headroom, Wooddens
r=0.52 against a 0.90–0.97 floor (**S**); nothing runs online with SpeedyWeather and the licensing basis is
unwritten (**O**). F_diff and the coupled loop are **C-validated on Hainich only** — say "Hainich only"
wherever a result is single-cell; the global evidence is the *offline* S.

## 4. The golden rules (full list in `CLAUDE.md` §6, protocol in §9)

- **Stay in your line's lane.** Editing another line's exclusive path is a protocol violation — raise it as an
  integration point (ADR 0029). Shared files are additive-only, inside your `# ── line <X> ──` region.
- **Write to per-line files:** narrative → `lines/<X>/JOURNAL.md`; state → `lines/<X>/STATE.md`; changelog → a
  **new** `changelog.d/<X>-<slug>.md` fragment (**never** edit `CHANGELOG.md` from a line); decisions → an ADR
  from **your** number block.
- **Refresh your `## NEXT` block before the session ends.** That block is the handoff the hook replays.
- Tag claims `[VERIFIED]/[DECISION]/[TODO]/[ASSUMPTION]`; one ADR per non-trivial decision.
- Conservation is a CI gate (water ~1e-12, carbon, energy ~1e-14) — never merge on red.
- The C binary is the **oracle**; validate F_diff against it, not itself. Confirm a C path actually runs in the
  `individual=true` config before porting it.
- New physics is **opt-in, default byte-identical** until deliberately enabled.
- Before chasing a fidelity residual: state the reference basis + a falsifiable hypothesis, confirm the
  comparison basis, and time-box (the `residual-diagnosis` skill).
- Reuse-first (Terrarium / hybrid-photosynthesis / NeuralCrop); reimplementation needs an ADR.
- Anything longer than a few seconds goes to **SLURM** (hook-enforced), tagged with your line prefix.
- Capture reusable knowledge as you go and route it by type (`CLAUDE.md` §8).
