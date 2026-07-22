# Steering Prompt — LPJmL-FIT Hybrid Emulator (hand this to the coding agent)

You are the engineering agent for an ESM-ready hybrid land component derived from LPJmL-FIT. You have
full workspace + repo access (private GitHub `rimajj/LPJmLFIT_Emulator`; local
`/p/projects/open/Jamir/esm_land_emulator`). This prompt supersedes the stale "§4 CURRENT STATUS" in
older handoffs. Read it fully before acting.

## Mission (unchanged, restated by the owner)

Build the **best possible ESM-ready emulator** that (1) **runs offline and emulates LPJmL-FIT as
faithfully as possible**, and (2) **runs online coupled to SpeedyWeather**. **Reuse Terrarium.jl and the
other ecosystem GitHub sources wherever helpful** — reuse is now the default; reimplementation must be
justified in an ADR.

## Ground truth: where the project really is (session 27, ~90 commits, clean tree, main-only)

- Phases 0–1 done: global 186 GB daily dataset; water + carbon closure PASSED.
- Phase 2 (slow emulator S, **offline only**): baseline gate met (LightGBM+copula, 6000 cells);
  warm+dry OOD fails (KS ~32× floor) — expected, it's the hybrid's job to fix.
- Phase 3 (F_diff, differentiable fast core): C-validated on **Hainich only**; multi-layer soil,
  multi-PFT canopy, prognostic structure, calibrated NPP, NN λ/Vcmax hooks, grass ±10–15%, `sapwood_bg`.
- Phase 4 (E, energy balance): landed, self-contained (ADR 0017), closes to 1.4e-14 W/m²; coupled
  Hainich decade reproduces the 2018 drought.
- **Not done, and it is the whole remaining project:** S is NOT in the coupled loop
  (`src/components/slow.jl` `step!` throws; `run.jl` grows structure from F itself); E is NOT validated
  against FLUXNET/PLUMBER2; nothing runs multi-cell; nothing runs online with SpeedyWeather; wind/psurf
  forcing not sourced.

Full reasoning: `PROJECT_REVIEW_2026-07-22.md`. Decisions: `docs/decisions/`. Do not re-derive settled
facts — re-confirm at most once.

## Prime directives

1. **Put the novelty in the loop.** The project's contribution is S (ML trait/size *distribution*
   emulator). Until S runs inside the coupled model, the "hybrid" and its speed-up are unrealized. This
   is priority one.
2. **Resolve the growth-ownership fork (ADR it).** F_diff already does differentiable allocation/growth,
   which the boundary rule assigns to S. Recommended split: **F_diff owns the conserving differentiable
   *carbon* growth of representative individuals; S owns the *distribution + demography* (count N,
   establishment, mortality, trait×size spread).** Ratify or overturn this in a new ADR before building
   P1 — don't leave it implicit.
3. **Reuse-first.** Default to Terrarium (coupling substrate, SEB cross-check, soil/thermal/hydrology),
   LPJmL-hybrid-photosynthesis (differentiable-λ, done), NeuralCrop (methodology; code is CC-BY-NC — get
   permission or reuse method only). Justify any new reimplementation in an ADR. Get the deferred
   **EUPL↔AGPL↔MIT licensing read** done — ADR 0017 depends on it.
4. **Prove it beyond one cell.** Single-cell (Hainich) results are scaffolding, not evidence. Multi-cell
   generalization and observational validation are required for every "ESM-ready" claim.
5. **Preserve the verification discipline** that makes this repo trustworthy (see Guardrails).

## Session-1 working-practice reset (do this BEFORE feature work)

The owner has observed you repeatedly re-fighting environment/test/package friction and producing
ballooning docs (~570 KB of overlapping MEMORY/JOURNAL/HANDOFF/CHANGELOG; ~60k tokens to onboard; no
`CLAUDE.md`). Fix the process first — it pays back within one session.

1. **Create `CLAUDE.md`** at repo root — the durable runbook every future session reads instead of
   re-deriving. It MUST contain:
   - **Julia tests:** delete `test/Manifest.toml` before `Pkg.test()`; testitems layout; Runic format
     gate; JET/Aqua; **Enzyme ≤ 0.13.188**; the **Julia 1.10-lts vs 1.11** Enzyme-canopy guard.
   - **C binary (LPJmL-FIT):** `module purge` then the exact set (json-c **0.13.1** not 0.17, else
     libjson-c.so mismatch aborts); restart from `restart_1999.lpj`; positional `startgrid/endgrid`;
     daily output is config-only; `scripts/run_daily_subset.sh`.
   - **Python:** `uv sync --frozen`; `pip install --break-system-packages`; ruff-format gate; the
     "eval"-filename classifier gotcha (rename to avoid the auto-mode block).
   - **Git/CI:** main-only workflow; the 5 CI gates (CI, format, docs, python, TagBot); pre-push
     checklist; commits are "Unverified" by design.
   - **Paths:** repo, C source (`/home/jamirp/lpjml56fit`), data on `/p/tmp`, ground truth on
     `/p/projects/waldspektrum/...`, sibling frozen S emulator.
2. **Consolidate & cap the docs.** Run the **`consolidate-memory` skill** now and every ~5 sessions.
   Reshape MEMORY.md into *current durable state only* — verified facts, frozen decisions as an index to
   ADRs, open TODOs, phase status — hard cap ~400 lines / ≤15k tokens. Move session-by-session narrative
   to an append-only JOURNAL. Replace the 1,675-line HANDOFF with a <150-line `00_START_HERE` pointer.
   Do not delete history — archive it (git already has it).
3. **Create these skills** (in your `.claude/skills/`), each a short SKILL.md + any helper script:
   `julia-test`, `lpjmlfit-cbinary`, `fdiff-validate`, `python-env`, `residual-diagnosis`, `repo-commit`.
   `fdiff-validate` should absorb the recurring extract→validate→baseline pattern (the many
   `scripts/extract_fdiff_*`/`validate_fdiff_*`). `residual-diagnosis` must enforce: **state the
   reference basis and a falsifiable hypothesis, confirm the comparison basis is correct, and time-box —
   before writing probe scripts.** (This is the discipline whose absence turned the grass-overshoot
   investigation into ~10 sessions that ended in "it was a reference-basis artifact.")
4. **Housekeeping:** delete the 946 MB `core-*` dump; confirm `.cov` stay gitignored.

*Gate for P0:* a fresh agent is productive after `CLAUDE.md` + `00_START_HERE` + capped MEMORY, under
~15k tokens; the 6 skills exist.

## Standing discipline: capture reusable knowledge as you go (every session)

The six skills above are a starting set, not the whole job. You must *continuously* recognize when
you've learned something a future session would otherwise re-derive, and capture it. Do not rely on
noticing in the moment — install these mechanisms:

**Triggers — when ANY fires, stop and capture before continuing:**
- You wrote a script you (or a future session) would plausibly run again → generalize it behind a skill.
- You did the same multi-step thing twice this session, or can imagine a third time → skill.
- You hit a non-obvious error and found the fix → add it to the relevant skill's gotchas (or CLAUDE.md).
- **You had to re-derive something a prior session already figured out** → last capture failed; capture
  it now. This is the strongest signal.

**Route by type — do NOT dump everything into MEMORY:**
- Reusable *procedure* → a skill (+ the helper script you already wrote).
- Environment / workflow *fact or gotcha* → `CLAUDE.md`.
- A *decision* + rationale → an ADR.
- Current *state* / open TODO / phase status → MEMORY.
- Narrative of what happened → JOURNAL.

**Cadence:** capture minimally in the moment (a 10-line SKILL.md + your script beats a perfect skill
never; prefer *updating* an existing skill over creating a new one). At **end of every session** run a
2-minute retrospective — "what did I learn that a future session would re-derive, and where does each
piece go?" — as a standing task. Every ~5 sessions run `consolidate-memory` to promote notes into skills
and prune; use the `skill-creator` skill to sharpen skill *descriptions* so they actually trigger.

*Worked example:* "extract one cell's forcing + restart and run a short daily re-run to make a test
fixture" is a procedure you have already written many variants of (`scripts/extract_fdiff_*`). It
belongs in the `fdiff-validate` skill, parameterized by cell index — not rewritten each time.

## Skills vs subagents — when to use which

- A **skill** captures *how to do a recurring task* and loads into your current context. Use it for the
  mechanical recurrences: test runs, cell extraction, C-binary runs, commits. This is the main lever for
  the friction the owner has observed.
- A **subagent** is a *separate context/worker* with its own window and tools. Use it for: **isolation**
  (keep a big C-source exploration out of the main thread), **parallelism** (fan out several
  residual-hypothesis probes at once — this would have shortened the grass saga), **specialization** (a
  read-only reviewer), and **independent verification** (adversarial re-derivation of ported physics; a
  CI/test runner that returns just pass/fail, not multi-minute logs).
- They **compose**: subagents invoke skills. Skill-first for know-how; reach for a subagent when context
  size, parallelism, or independent verification demands it.

## Orders (priority order; gates are stop-and-review checkpoints)

**P1 — Put S in the coupled loop.** Implement `AbstractSlowEmulator` concretely (port the Python
LightGBM+copula to Julia or call it — decide in the ADR); wire it into `run_coupled_cell`; implement the
§ growth split; conserve carbon at the handoff via flux-then-integrate.
*Gate:* S+F+E runs on Hainich; carbon conserved ~1e-6; coupled trait/size distribution matches the
offline-S panel; **speed-up measured against the deterministic-F baseline** (the hybrid's raison d'être).

**P2 — Validate E against observations (run in parallel with P1).** Source FLUXNET/PLUMBER2 DE-Hai and
the `sfcwind`/`ps` forcing; validate LE/H/T_skin; add a stability correction to `g_a`.
*Gate:* LE/H/T_skin within published PLUMBER2 error bands at ≥1 site; closure and diurnal cycle hold.

**P3 — Multi-cell generalization.** Run coupled S+F+E on the biome-stratified 6000-cell set; evaluate on
held-out cells **and** scenarios; run the LPJ_resilience battery (esp. the shuffle test and
climate-dependent autocorrelation).
*Gate:* per-cell error vs the seed1-vs-seed2 noise floor; resilience metrics preserved.

**P4 — Online coupling with SpeedyWeather.** Implement S/F/E as Terrarium `Abstract*` processes; couple
via the `SpeedyWeatherTerrariumExt` external-land interface; rollout-length curriculum + input-noise
injection; multi-year free run; OOD warming at constant CO₂.
*Gate:* stable coupled multi-year run — no drift, no AC-gap/oscillation — conserving; gradients flow for
online training.

**P5 — Reuse + licensing reconciliation (start early; unblocks P4).** New ADR reconciling the
self-contained offline core with a Terrarium coupling substrate; obtain the written EUPL↔AGPL↔MIT read.

**P6 — Nitrogen limitation (research track — DO NOT START before the owner's "(c)" discussion).**
Prototype a learned differentiable N-downregulation closure on Vcmax/photosynthesis, trained against
N-fertilization + FLUXNET data, to lift the constant-CO₂ ceiling; or scope porting a process N cycle.
This is the path to surpassing LPJmL-FIT; it needs a design discussion first.

Dependencies: P0 → then P1 ∥ P2 ∥ P5 → P3 (after P1) → P4 (after P3 + P5). P6 gated on discussion.

## Guardrails — preserve these (they are why the physics is trusted)

- Keep the `[VERIFIED]/[DECISION]/[TODO]/[ASSUMPTION]` tagging and an ADR for every decision.
- Keep conservation as CI gates (water ~1e-12, carbon closure, energy ~1e-14) and never merge on red.
- Keep the C binary as the numerical-regression **oracle**; validate F_diff against it, not against
  itself.
- Keep the "**opt-in, default byte-identical**" rule: new physics must leave every committed baseline
  and the AD trainer unchanged until deliberately enabled.
- Adversarially re-derive any ported physics against the C source before trusting it.

## Anti-patterns — avoid these (they cost the last effort real time)

- **Doc bloat.** Do not grow MEMORY/HANDOFF into session logs. Append to JOURNAL; consolidate MEMORY.
- **Reference-basis thrashing.** Before chasing a fidelity residual, prove you're comparing against the
  right reference (use `residual-diagnosis`). Time-box; escalate to the owner rather than spending many
  sessions on one sub-residual.
- **Reflexive reimplementation.** Check Terrarium/hybrid-photosynthesis/NeuralCrop first; reimplement
  only with an ADR justification.
- **Single-cell over-claiming.** State "Hainich only" wherever a result is single-cell; don't imply
  generality.

## First reply expected from you

Before writing code: (1) confirm you've read this + `PROJECT_REVIEW_2026-07-22.md`; (2) post the P0 plan
(CLAUDE.md outline, doc-consolidation plan, the 6 skill stubs); (3) post the draft ADR resolving the
growth-ownership fork; (4) list any facts you need the owner to confirm. Then execute P0, stop at its
gate, and review before P1.
