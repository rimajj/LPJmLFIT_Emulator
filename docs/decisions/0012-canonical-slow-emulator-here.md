---
status: "accepted"
date: 2026-07-16
deciders: "Jamir Priesner (owner)"
consulted: "DESIGN.md §6, DEVELOPMENT_PLAN.md §2.2, ECOSYSTEM_AND_COUPLING.md; the prior sibling project /p/projects/open/Jamir/emulator"
informed: "python/README.md, lpjmlfit_emulator (component S), ADR 0002/0005"
---

# Canonicalize component S in this repository; port the sibling once, then abandon it

## Context and Problem Statement

Two codebases for the slow trait/size **distribution** emulator (component S) had diverged: a prior
**sibling** project at `/p/projects/open/Jamir/emulator` (a LightGBM + Gaussian-copula distribution
emulator — early, lightly trained, with documented in-principle failures on the SSP370 transient and a
per-cell biomass ceiling; see its `PROJECT_REVIEW.md`), and this repository's S component
(`DESIGN.md` §6 positions the hybrid as the fix for exactly that failure). Maintaining two S codebases
is untenable. Which is authoritative going forward?

## Decision Drivers

- One source of truth for S; no drift between two codebases.
- This repo is the auditable, tested, CI-gated home for the whole hybrid (S/F/E); S must live inside it.
- The sibling holds genuinely reusable assets (full metrics library, the seed1-vs-seed2 noise-floor
  evaluation discipline, a baseline model/feature/data pipeline) worth keeping — but as *ported code we
  own*, not a live external dependency (owner's own prior work, so no external-license concern).
- Reproducibility: record where ported code came from.

## Considered Options

- **Keep developing S in the sibling** and depend on / sync with it from here.
- **Add the sibling as a submodule or Python dependency.**
- **Port the sibling's worthwhile code into this repo ONCE, then treat the sibling as frozen** and
  develop S only here.

## Decision Outcome

Chosen: **port once, then canonicalize S here.** The sibling's reusable code (full `metrics.py`, the
noise-floor evaluation discipline from `eval_presentday_critical.py`, and the "direct" baseline
model/feature/data/transform pipeline) is ported into `python/src/lpjmlfit_emulator/` with a
provenance header on every file; the sibling folder is then **frozen** (not a submodule, dependency,
or sync target). Improvements to S happen **only in this repo** from now on. Large trained artifacts
(`models/*`, 262 MB–1.1 GB) and datasets are **not** copied — they stay on the filesystem and will be
referenced via DVC pointers; only small reference artifacts (the published floor numbers,
`debias_presentday.json`) are brought in.

**Provenance:** the sibling is **not a git repository**, so the port is pinned by timestamp — newest
source file mtime **2026-07-14**, ported on **2026-07-16**. Recorded in each ported file's header.

### Consequences

- Good: the repo is fully self-contained for S; single source of truth; the reusable metrics + eval
  discipline + baseline are preserved and now tested/CI-gated here.
- Good: no fragile cross-project coupling; the sibling can be archived.
- Bad / carried forward: the sibling's history is not in git, so provenance is a timestamp, not a
  commit; and the ported baseline inherits the sibling's known limitations (equilibrium mapping,
  per-cell ceiling) — which is precisely what the hybrid (F + flux-then-integrate S) is designed to
  fix (ADR 0001/0003), so the port is a *starting point to improve*, not an endpoint.

## Pros and Cons of the Options

### Keep developing in the sibling / depend on it

- Good: no porting effort.
- Bad: two sources of truth; drift; the sibling is outside this repo's tests/CI/docs auditing.

### Submodule / Python dependency on the sibling

- Good: single copy of the code.
- Bad: a live external dependency on a non-git, ad-hoc folder; breaks self-containment and the "owner
  controls everything from this repo" principle; couples releases to an unversioned tree.

### Port once, canonicalize here (chosen)

- Good: self-contained, tested, owned; sibling frozen.
- Bad: one-time porting cost; provenance is a timestamp (sibling not versioned).

## More Information

Port scope and what was intentionally left behind are recorded in `JOURNAL.md` and the porting PR.
Ported into `python/src/lpjmlfit_emulator/`: `metrics.py` (full), `evaluation.py` (noise-floor
discipline + `PUBLISHED_NOISE_FLOOR`), `features.py`, `transforms.py`, `drivers.py`, `data.py`,
`baseline.py`, `train.py`. Verified by `pytest` + `ruff` in `py311_new` and by reproducing the
published per-cell noise-floor numbers `{Height:0.020, agb:0.113, npp:0.062, LAI:0.025}`. Revisit only
if S is ever spun out into its own package (it should not be, per this ADR).
