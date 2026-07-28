# JOURNAL — LINE O (online coupling: Terrarium + SpeedyWeather (P4/P5))

> **Append-only, newest at the bottom.** Narrative for THIS LINE only: what you did, the commands, the
> results, dead ends. Durable state goes to `lines/O/STATE.md` (and its `## NEXT` block — refresh it before
> your session ends); cross-cutting durable facts go to `MEMORY.md`; the story of one change goes to a
> `changelog.d/O-<slug>.md` fragment. Pre-split history for the whole project: the root `JOURNAL.md`.
>
> Entry template:
> ```
> ## YYYY-MM-DD — <short title>  [milestone O<n>]
> - **Goal:**
> - **Did:**
> - **Result / evidence:** (numbers, job ids, gate outcomes)
> - **Decisions:** (ADR NNNN if any)
> - **Next:** (mirror into STATE.md's NEXT block)
> ```

## 2026-07-28 — line created (ADR 0028/0029)
- **Goal:** stand up line O as an independent work line so it can run concurrently with the other lines.
- **Did:** created by the Phase-0 setup session on `main`: branch `line/O` + worktree `wt-O`,
  `lines/O/{STATE.md,JOURNAL.md}`, ADR block assigned, ownership recorded in ADR 0029.
- **Result / evidence:** see the root `JOURNAL.md` Phase-0 entry for the setup evidence.
- **Decisions:** ADR 0028 (branch+worktree per line, supersedes 0013), ADR 0029 (the split + ownership).
- **Next:** the `## NEXT — start here` block in `lines/O/STATE.md`.

## 2026-07-28 — O1: the P5 licensing basis (ADR 0080)  [milestone O1]
- **Goal:** write the good-faith EUPL↔AGPL↔MIT licensing ADR that `STEERING_PROMPT.md` P5 asks for — the
  thing that has to exist before a Terrarium/SpeedyWeather dependency can be taken at all.
- **Did:** audited every inbound work against upstream rather than from memory, then wrote ADR 0080 +
  `docs/third_party_licensing.md` (register + gate) + the `dependency-license-gate` skill; fixed the two
  attribution defects the audit turned up.
  - Read the actual files: `Terrarium.jl/{LICENSE,NOTICE}`, `/home/jamirp/lpjml56fit/LICENSE`,
    `NeuralCrop.jl/LICENSE`, `LPJmL-hybrid-photosynthesis/LICENSE`; WebFetch for SpeedyWeather.jl,
    Oceananigans, Thermodynamics, FreezeCurves, json-c, and the GitHub API for repo `license`/`private`.
  - Resolved `RingGrids` + `SpeedyWeatherInternals` via the General-registry tarball: **both are
    subpackages of the SpeedyWeather.jl monorepo**, so they inherit its EUPL-1.2. (`tar xzf` paths have no
    `./` prefix; the earlier attempt failed on that.)
  - Diffed `NeuralCrop.jl/src/training/training_loop.jl::train_loop_rollout!` (170 lines, clone `dff3fc8`)
    against `ext/FDiffTrainingExt.jl::train_fdiff_rollout!` to settle the "port" question by evidence.
- **Result / evidence:**
  - `[VERIFIED]` **SpeedyWeather.jl is EUPL-1.2, not MIT** (ADR 0015 already said so; my prior was wrong —
    which is exactly why the skill now forbids stating a licence from memory). **No `NOTICE`** (HTTP 404).
  - `[VERIFIED]` **Terrarium's `NOTICE` extends EUPL Art. 5 to *any* licence for "normal use of the Work as
    a library"** — the single fact that unblocks P4, and it is in `NOTICE`, not `LICENSE`. Nobody had read it.
  - `[VERIFIED]` **The repo is PUBLIC with no `LICENSE`** — GitHub API `private: false`, `license: null`;
    `git log --all -- LICENSE` is empty (it never existed); `Project.toml` has no `license`; `CITATION.cff`'s
    is commented "TBD"; `README.md` §License says "To be set by the owner". `docs/make.jl`'s "the repo is
    PRIVATE" comment is **stale**. Meanwhile `patches/lpjmlfit_daily_grass_gpp.patch` ships verbatim context
    lines from AGPL-3.0 `conf.h`/`outputvars.js` ⇒ a live compliance gap, not a hypothetical one.
  - `[VERIFIED]` The trainer shares **no expression** with NeuralCrop's: overlap is only
    `Zygote.withgradient` → finite-loss guard → `Optimisers.update` in a windowed day loop (those libraries'
    documented API + TBPTT itself, Williams & Zipser 1990). The reference threads 19 positional args through
    jld2 chunk loading, per-cell batching, `ps_frozen`, device dispatch, an LR schedule, a validation split
    and checkpointing; ours takes 6 and adds the detached-state carry (`_advance_state`) it doesn't have.
    So the *code* was fine and the *wording* was wrong — reworded in `ext/` ×3, `src/LPJmLFITEmulator.jl`,
    `src/fdiff.jl`.
  - Transitive tree walked: Oceananigans MIT, Thermodynamics Apache-2.0, **FreezeCurves LGPL-2.1** (the one
    node whose strict-2.1-only reading is GPL-3-incompatible — a non-issue only because we never distribute
    it; the flag to re-check if the vendoring posture ever changes).
  - Gate met: **ADR 0080 accepted**; the `MEMORY.md` licensing TODO is resolved and narrowed to a single
    named owner action (file `LICENSE`), with "make the repo private again" as the interim alternative.
- **Decisions:** **ADR 0080** — AGPL-3.0-or-later outbound (*forced*: LPJmL-FIT copyleft ∧ EUPL Appendix);
  READ/DEPEND/VENDOR separated, vendoring needs its own ADR; NeuralCrop method-only permanently;
  ADR 0017 **annotated, not superseded** (its blocker was VENDOR-only; its outcome stands on the
  zero-`[deps]` + v0.1.x drivers); one ADR 0015 claim corrected — obligations attach on **distribution**,
  which a public repo already performs, not on commercial use.
- **Dead ends / notes:** `RingGrids.jl` as a standalone repo → 404 (it's a monorepo subpackage; the 404
  proves nothing). The GitHub API's `license: null` is ambiguous — it means *either* unlicensed *or*
  unclassifiable, so the file has to be fetched before concluding.
- **Deliberately NOT done (scope discipline):** did not file `LICENSE` — choosing a licence is the copyright
  holder's act, not the agent's (ADR 0080 §4 names it); did not touch `Project.toml` (integrator-only) or
  `docs/make.jl`'s stale PRIVATE comment + now-possibly-unneeded `linkcheck_ignore` (integrator — the `docs`
  gate doesn't run on line branches, so a line can't verify a change to it).
- **Next:** O2 — write `docs/p4_online_coupling_design.md` against the real cloned Terrarium API.
