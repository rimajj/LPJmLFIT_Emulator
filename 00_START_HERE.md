# START HERE — LPJmL-FIT emulator

A router, not a status page. Goal: be productive in **< 15k tokens**.

> **ONE DEVELOPMENT STREAM (owner decision 2026-10-10, ADR 0319).** The parallel work lines (S/M/E/O/X) are
> retired. One developer works on `main` in `/p/projects/open/Jamir/esm_land_emulator` and owns every path. The
> `wt-*` worktrees and `line/*` branches are frozen history.
>
> **THE GOAL (owner, 2026-10-10, ADR 0318):** a full LPJmL-FIT emulator that emulates **everything** — forest
> structure *and* the daily carbon/water exchange — **orders of magnitude faster** than LPJmL-FIT, and **drift-free
> in transient runs**. Pass standard relaxed: dense cells must be fine, sparse cells must not run away.
> ⚠ The re-implemented daily physics (`src/fdiff.jl`) is **4.62× slower** than the original (ADR 0084): it is the
> fidelity reference, not a fast path — the daily exchange must be learned too.

## 1. Read in this order

1. **`CLAUDE.md`** — the durable runbook: paths, Julia/C-binary/Python/CI commands, every environment gotcha, the
   guardrails (§6), knowledge capture (§8), and **§9 the one-stream protocol**. *Read this every session.*
2. **`STATE.md`** — the goal, where each part stands, and the **`## NEXT — start here`** handoff (the SessionStart
   hook replays it).
3. **`EXECUTION_PLAN.md`** — revision 3: priorities toward the goal, the method inventory, decision points.
4. **`MEMORY.md`** — cross-cutting `[VERIFIED]` facts and the load-bearing ADR constraints.
5. **`docs/decisions/`** — the ADRs; `README.md` is the index. Next free number: see `STATE.md`.

**History, not onboarding:** `JOURNAL.md` (append-only narrative), `CHANGELOG.md`, and the retired lines'
`lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` — their findings and gotchas remain valid; open them for the story
behind a component.

## 2. What exists (one paragraph)

The original plan was a hybrid: **S** = an ML emulator of the per-cell tree/trait distribution (annual), **F/F_diff**
= a differentiable re-implementation of LPJmL-FIT's daily physics, **E** = a surface energy balance, coupled to
SpeedyWeather. Of these, F_diff is C-validated at five biome cells but slower than the original; E closes to
~1e-14 W/m² at Hainich; the online coupling runs only as a harness. The current work (STATE.md) is a learned
emulator of both halves: the forest structure from climate (best setup on a 1 050-cell panel close to the relaxed
standard) and the daily exchange (not started).

## 3. The golden rules (full list in `CLAUDE.md` §6)

- Tag claims `[VERIFIED]/[DECISION]/[TODO]/[ASSUMPTION]`; one ADR per non-trivial decision.
- Every fidelity claim carries its nulls (a second run of the original, persistence, lookup) written down **before**
  the run, and says how many of the 54 020 tree-bearing cells it covers.
- Every speed claim carries an end-to-end measured number and the original's cost at the patch count it is run at.
- Conservation is a CI gate (water ~1e-12, carbon, energy ~1e-14) — never merge on red.
- The C binary is the **oracle**. Confirm a C path actually runs in the `individual=true` config before porting it.
- New physics is **opt-in, default byte-identical** until deliberately enabled.
- The emulator does not see CO2 (ADR 0004/0107, closed). Reuse of LPJmL-FIT / TUM-PIK-ESM code is authorised; cite.
- Anything longer than a few seconds goes to **SLURM** (hook-enforced). Data never in `/home`.
- Talk to the owner in plain language (CLAUDE.md §0a).
- Capture reusable knowledge as you go and route it by type (`CLAUDE.md` §8).
