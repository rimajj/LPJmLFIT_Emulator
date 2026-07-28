---
status: "accepted"
date: 2026-07-28
deciders: "Jamir Priesner (owner)"
consulted: "ADR 0028 (the branch/worktree mechanism); STEERING_PROMPT.md §Orders P1-P6 + the dependency line; MEMORY.md §5 open TODOs; ADR 0020/0023/0025 (the S conditioning + artifact contracts); ADR 0014 (empty runtime deps); the 2026-07-28 contention audit"
informed: "CLAUDE.md §9, 00_START_HERE.md, MEMORY.md (router), lines/{S,M,E,O}/STATE.md, docs/decisions/README.md, the repo-commit skill"
---

# Four work lines (S / M / E / O): per-path ownership, frozen cross-line contracts, per-line coordination files

## Context and Problem Statement

[ADR 0028](0028-parallel-session-lines.md) established *how* concurrent sessions share the repo (a branch +
worktree each, self-merged on green CI). It deliberately left open *what* the lines are and *who owns which
file*. Without that, four sessions following the standing knowledge-capture discipline (`CLAUDE.md` §8 —
which pushes **every** session to write MEMORY + JOURNAL + CHANGELOG + a skill + possibly an ADR on **every**
commit) would collide constantly, and would collide worst in the documents rather than the code.

The 2026-07-28 audit quantified it: `CHANGELOG.md` is touched by ~54 of 128 commits and is written by
**inserting at the top**, so two lines produce overlapping same-line hunks of 20–40-line prose blocks;
`MEMORY.md` (47/128) is **rewritten in place** and periodically **destructively reshaped** by the
`consolidate-memory` skill, so a deletion from one line auto-merges against an insertion from another into a
state neither intended; `JOURNAL.md` (63/128 — the most-touched file in the repo) is appended at EOF, so every
concurrent commit conflicts in its last hunk; and ADR numbers are allocated by `ls docs/decisions/` with **no
allocator**, so two lines both pick `0028`. Meanwhile `src/` and `test/testitems/` already partition cleanly
by subsystem. So: which lines, owning which paths, coordinating through which files?

## Decision Drivers

- **Independence must be real, not nominal.** A "line" is only worth its overhead if it can run a full
  session — edit, test on SLURM, commit, merge — without waiting on another line.
- **Conflict-freedom comes from disjoint FILES, not disjoint sections.** Two lines editing different sections
  of one file still conflict on merge, and `CHANGELOG.md`'s top-insert is the pathological case. Different
  files never conflict.
- **The one genuine coupling is S → M.** M's coupled runs consume S's runtime API and its trained artifacts,
  and train/inference consistency is load-bearing (ADR 0023) — a conditioning change must move both sides at
  once or the coupled loop silently runs on the wrong feature contract.
- **Cross-cutting facts must not fragment.** "Hainich = 42490", the fire/CO₂ regime, the `individual=true`
  dead C paths — if these move into per-line files they will be re-derived, which is the exact waste
  `CLAUDE.md` §8 exists to prevent.
- **The frontier is already mapped.** `STEERING_PROMPT.md` P2–P6 plus `MEMORY.md` §5 name the remaining work;
  the split should follow those seams rather than invent new ones.
- **Runtime `[deps]` stays empty (ADR 0014).** Any line wanting a dependency (Terrarium, NetCDF) must not be
  able to add one unilaterally.

## Considered Options

- **A. Four lines S / M / E / O, per-path exclusive ownership, per-line coordination files, frozen
  cross-line contracts.**
- **B. Two lines (S + M)** — the owner's initial sketch: Component-S science and the coupled multi-cell path
  through to SpeedyWeather.
- **C. Per-line sections inside the existing shared MEMORY/JOURNAL/CHANGELOG** rather than per-line files.
- **D. One line per ADR-order (P2…P6)** — five-plus lines, mechanically following `STEERING_PROMPT.md`.

## Decision Outcome

Chosen option: **A — four lines with exclusive path ownership, per-line coordination files, and frozen
cross-line contracts.**

### The four lines

| Line | Branch / worktree | Scope | Maps to |
|---|---|---|---|
| **S** | `line/S` · `wt-S` | Component-S science: close the trait per-cell-median headroom, grass ownership, cohort DROP, in-loop OOD | the novelty's remaining fidelity gap |
| **M** | `line/M` · `wt-M` | Multi-cell coupled S+F+E: per-cell inputs, S in the multi-cell driver, C-truth validation, resilience battery | P3 |
| **E** | `line/E` · `wt-E` | Component E vs observations: PLUMBER2/FLUXNET, the `sfcwind`/`ps` cross-grid remap, sublimation-λ | P2 |
| **O** | `line/O` · `wt-O` | Online coupling: the licensing basis, the P4 design doc, Terrarium `Abstract*` wrap, SpeedyWeather `LandModel` | P4 + P5 |

Per-line milestones live in `lines/<X>/STATE.md` (mutable working state, not frozen here).

### Path ownership (exclusive unless marked shared)

| Path | Owner |
|---|---|
| `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` | **S** |
| `scripts/*slow*`, `scripts/flux_ood_experiment.jl`, `scripts/diagnose_*`, `scripts/noise_floor_vs_emulator.py` | **S** |
| `test/testitems/{slow_*,drf_*,recruit_copula_*,climbuf_*,carbon_ledger_*}` | **S** |
| `src/run.jl`, `src/interface.jl` — **the coupling seam** | **M** |
| `scripts/{run_coupled_biomes.jl,extract_biome_forcing.py}` + new per-cell extractors | **M** |
| `test/testitems/{biome_coupled,coupled_run,resilience_battery,rollout_stability}_tests.jl` | **M** |
| `src/components/energy.jl`, `test/testitems/energy_closure_tests.jl` | **E** |
| `config/paths.yaml` — the energy/wind/psurf keys | **E** |
| `ext/SpeedyWeatherTerrariumExt.jl` (new), `docs/p4_online_coupling_design.md` (new) | **O** |
| `lines/<X>/STATE.md`, `lines/<X>/JOURNAL.md`, `changelog.d/<X>-*.md` | that line |
| `src/LPJmLFITEmulator.jl` include/export block | **shared** — append only inside your `# ── line <X> ──` marked region |
| `CLAUDE.md`, `MEMORY.md` (shared facts) | **shared** — additive only; reconciled at integration |
| `test/testitems/references/*` | **shared** — new fixtures take a line prefix; **regenerating an existing baseline is an integration point** (guardrail 4) |
| `Project.toml`, `test/Project.toml` (deps/`[compat]`) | **integrator only** — a dependency needs its own ADR; runtime `[deps]` stays empty (ADR 0014) |
| `STEERING_PROMPT.md`, `DESIGN.md`, `docs/decisions/00*` (accepted) | owner-owned / immutable — read-only |

Touching another line's exclusive path is a protocol violation: raise it as an integration point instead.

### Frozen cross-line contracts

Changing one of these is an **integration point** — coordinate, land both sides together, and note it in both
lines' STATE.md:

- **S → M** (the only substantive coupling): `FluxDrivenSlowEmulator(fc, forest; …)` keyword surface; the
  `flux_feature_vector` column order; the `live_flux_cond` subset (ADR 0025); the `.drf`/`.rcop` serialization
  format (ADR 0023); the `cell_meta.parquet` schema. **M pins a versioned artifact path; S bumps a version in
  the artifact meta rather than mutating an artifact in place.** Because train/inference consistency is
  load-bearing, a conditioning change is *by definition* a both-sides change.
- **E → M**: the `SEBEnergyClosure` constructor + `solve!` signature.
- **O → all**: `src/interface.jl` is consumed **read-only** (already frozen, `DESIGN.md` §8).

### Coordination files

- `lines/<X>/STATE.md` — that line's durable state. **First section is `## NEXT — start here`**, which the
  `SessionStart` hook prints; the ending session's duty is to refresh it (that *is* the handoff, ADR 0028).
- `lines/<X>/JOURNAL.md` — that line's append-only narrative. The root `JOURNAL.md` is frozen at the split
  marker and preserved as history (never deleted, never appended again).
- `changelog.d/<line>-<slug>.md` — changelog **fragments**, collated into `CHANGELOG.md` at integration. This
  removes the repo's worst conflict outright.
- `MEMORY.md` — slimmed to **shared-only**: what-this-is, the cross-cutting `[VERIFIED]` facts, the ADR index
  pointer, and a **router table** to each line's STATE.md. The duplicate ADR index it used to carry is
  dropped; `docs/decisions/README.md` is the single source.
- **ADR number blocks** (removes the allocator race): shared/cross-cutting **0028–0029**, **S 0030–0049**,
  **M 0050–0069**, **E 0070–0079**, **O 0080–0089**. Each line appends to its own subsection of the index.
- **SLURM tag prefixes** `S-` / `M-` / `E-` / `O-` so `squeue` and `logs/<tag>.<jobid>.out` are attributable,
  and **per-line `/p/tmp` output directories** — another line's data artifacts are read-only.

### Consequences

- Good, because every line can complete a full edit→test→commit→merge cycle without waiting on another.
- Good, because the four highest-traffic coordination files stop conflicting **by construction** (different
  files), rather than by careful merging.
- Good, because cross-cutting knowledge stays in one shared place, so it is not re-derived per line.
- Good, because the S→M contract is written down, so the one real break risk is scheduled instead of
  discovered by a silently-wrong coupled run.
- Bad, because onboarding now has two levels (shared `MEMORY.md` + a line's `STATE.md`). Mitigated by the
  hook, which delivers the line level automatically, and by `00_START_HERE.md` becoming a router.
- Bad, because `MEMORY.md` and `CLAUDE.md` remain shared and can still conflict (additively, rarely — 47 and
  7 commits historically). Accepted: fragmenting them would cause worse re-derivation.
- Bad, because O5 (multi-cell online) genuinely depends on M1/M2, so line O is not fully independent to its
  end. Accepted: O1–O4 are independent and are most of O's work.
- Neutral: `consolidate-memory` now applies to the shared `MEMORY.md` **and** each line's STATE.md; running it
  on the shared file is an integrator action, not a line action.

## Pros and Cons of the Options

### A. Four lines with ownership + contracts + per-line files

- Good, because it staffs every unblocked order (P2, P3, P4/P5) at once instead of queueing them.
- Good, because E and O are almost perfectly disjoint from S and M in both `src/` and `test/`.
- Bad, because four lines is the most coordination surface and the most owner review load.

### B. Two lines (S + M)

- Good, because it is the smallest change and the least to track.
- Bad, because it leaves P2 unstaffed — the one `[ASSUMPTION]` under an "ESM-ready" claim (E's LE/H/T_skin are
  "validated only out-of-model") — despite P2 being fully independent and needing no S or M code.
- Bad, because it puts P4 at the tail of a sequential M line, when O1–O4 need nothing from M.

### C. Per-line sections in the shared files

- Good, because it needs no new files and keeps one place to read.
- Bad, because it does not actually work: git conflicts are textual, so same-file edits still collide — and
  `CHANGELOG.md`'s top-insert collides on the *same lines* in the worst possible form.
- Bad, because `consolidate-memory`'s destructive reshape can silently auto-merge away another line's section.

### D. One line per steering order (P2…P6)

- Good, because it maps 1:1 onto `STEERING_PROMPT.md` and needs no interpretation.
- Bad, because the orders are not equal-sized or equally independent (P5 is largely an owner action; P6 is
  explicitly gated on an owner discussion), so several "lines" would idle.
- Bad, because P3 and P4 share the coupling seam (`run.jl`/`interface.jl`) and would contend; grouping them
  as M and O with the seam owned by M is what makes them separable.

## More Information

- **Mechanism:** [ADR 0028](0028-parallel-session-lines.md). **Runbook:** `CLAUDE.md` §9. **Ritual:** the
  `repo-commit` skill. **Router:** `00_START_HERE.md` → `MEMORY.md` → `lines/<X>/STATE.md`.
- **Contract sources this ADR freezes rather than redefines:** ADR 0020 (flux-driven conditioning), ADR 0023
  (runtime-consistent serialized artifact + train/inference consistency), ADR 0024 (dynamic roster), ADR 0025
  (`live_flux_cond`), ADR 0014 (empty runtime deps), `DESIGN.md` §8 (the S↔F↔E interface).
- **Validated by** a conflict-free merge of two different lines into `main` back-to-back, and by the shared
  suite staying green after both (baseline 106918 pass / 0 fail / 4 broken).
- **Revisit when** a line finishes its scope (retire or repurpose the branch), when a fifth line is wanted
  (allocate the next ADR block), or when the S→M contract needs to change structurally rather than
  incrementally.
