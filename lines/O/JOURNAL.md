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

## 2026-07-28 — owner closes licensing; reuse authorized (ADR 0081)  [milestone O1 closed]
- **Goal:** act on the owner's direct instruction — *"use these models and stop talking about licences; just
  make sure it's transparently cited wherever these models are used"*.
- **The fact that settles it:** the owner is a member of **both** the LPJmL-FIT group **and TUM-PIK-ESM**
  (which hosts SpeedyWeather.jl / Terrarium.jl / LPJmL-hybrid-photosynthesis). That was missing from ADR 0080
  and from every earlier analysis, and it makes the licence question moot in practice.
- **Did:** wrote **ADR 0081** (short, deliberately final) and then stripped licensing prominence everywhere a
  new session actually reads, so this cannot recur:
  - `CLAUDE.md` §7 and `MEMORY.md` §4: the long licensing blocks → "CLOSED, do not reopen; cite instead".
    Dropped the `LICENSE` owner-action TODO. `MEMORY.md` P5 row → DONE + CLOSED, no residual.
  - `lines/O/STATE.md` `## NEXT` → opens with "licensing is closed, do not spend a minute on it", then goes
    straight to **O2** (the P4 design doc) → O3 → O4.
  - `docs/third_party_licensing.md` reframed from a licence gate into the **reuse + citation register**: the
    four citation surfaces, one row per reused work (what it is / what we take / where it's cited), and
    vendoring-needs-an-ADR kept on *maintenance* grounds only.
  - Skill `dependency-license-gate` → **`reuse-citation`** (`git mv`): same useful mechanics (find a Julia
    package's real upstream from the registry tarball; the SpeedyWeather monorepo), reoriented to citation
    accuracy; the AGPL decision table is gone.
  - ADR 0080 `status:` now reads "§4's open owner action CLOSED by ADR 0081 — do not reopen licensing". Its
    factual register and its depend-don't-vendor hygiene are still worth having, so it is not withdrawn.
- **Result / evidence:** every entry point a session reads (SessionStart hook → STATE.md NEXT, CLAUDE.md,
  MEMORY.md) now says "closed, cite, get on with the coupling". Nothing in the repo asks for a licence decision.
- **Decisions:** **ADR 0081** — reuse of LPJmL-FIT / Terrarium / SpeedyWeather / LPJmL-hybrid-photosynthesis
  authorized; obligation = transparent citation only; supersedes ADR 0080 §4. NOT reopened: NeuralCrop.jl
  method-only (CC-BY-NC, different author, outside both groups); runtime `[deps]` empty (ADR 0014 — technical).
- **Lesson for future sessions:** ask the owner for context before writing 300 lines of analysis. The one fact
  that decided this — his group memberships — was one question away, and no amount of reading upstream
  LICENSE files could have produced it.
- **Next:** O2 — `docs/p4_online_coupling_design.md`, validated against the real cloned Terrarium API.

## 2026-07-28 — the online coupling HARNESS RUNS (P4 unblocked in practice)  [milestone O2 + O3 groundwork]
- **Goal:** owner's instruction — "the goal is clear: we want to run the emulator online coupled to
  SpeedyWeather. Make that happen." So: stop writing about it, get the stack running.
- **Did / result:**
  - Installed **Terrarium 0.1.3 + SpeedyWeather 0.21.1** into the shared depot alongside our package.
    Project `/p/tmp/jamirp/esm_online_coupling`, scripts committed to `scripts/online_coupling/`.
  - `[VERIFIED]` **SpeedyWeather ships `SpeedyWeatherTerrariumExt`** → `SpeedyWeather.LandModel(::SpectralGrid,
    ::Terrarium.AbstractModel)`. So Terrarium is the SUPPORTED land-model socket and we write no
    atmosphere↔land plumbing. That is the answer to "what is Terrarium for".
  - `[VERIFIED]` **The reference coupling RUNS on a compute node** (job 1622172): 6 simulated hours,
    `vegetation = nothing`, 4608/4608 cells finite, Float32 held, T_skin −16.7…25.0 °C (mean 4.0),
    T_soil_top mean 4.7 °C, H mean 84.9 / LE mean 10.7 W/m² (bare rocky planet ⇒ high H, low LE is right).
    `=== REFERENCE COUPLING OK ===`, exit 0. This is now the CONTROL run.
  - Wrote `docs/p4_online_coupling_design.md` (the O2 deliverable) from verified source, not memory.
- **Four traps, each one a failed job — all in the new `online-coupling-env` skill:**
  1. **Julia 1.10.0 CANNOT precompile this stack** — `KeyError: "KernelAbstractions"` on RingGrids/Speedy,
     `"GPUArraysCore"` on Terrarium. **1.10.10** does all 272 deps in 81 s. A Pkg bug, not a compat bound.
  2. **`SpeedyWeather.EarthOrography` DOWNLOADS an artifact inside `initialize!`** → compute nodes have no
     egress → curl `RequestError`. Fix: `warm_assets.jl` on the LOGIN node caches it. The *asset* analogue
     of the documented Pkg depot warm.
  3. **Terrarium state is °C, not Kelvin.** My first plausibility assertion demanded 150–350 K and failed a
     perfectly good run. `celsius_to_kelvin` is applied only at the Thermodynamics boundary.
  4. **Never `Pkg.status()`** in a setup script here — `KeyError: "Dates"` from `print_status` when the
     project has a dev'd package with `[weakdeps]`; it aborts before precompile.
- **The real design finding:** Terrarium steps at **Δt = 300 s** under ForwardEuler; F is **daily**, S is
  **annual** (288 and 105 120 land steps respectively). Rate processes (photosynthesis) have **no** mismatch;
  stateful ones need a buffered **piecewise-constant tendency**, which ForwardEuler integrates to exactly the
  daily total ⇒ daily conservation survives sub-daily integration by construction. That is why the spike is
  photosynthesis: it gets our physics genuinely online without solving the hard problem first.
- **NOT done, stated plainly:** no LPJmL-FIT physics is in the coupled loop yet. The harness is verified; the
  `FDiffPhotosynthesis` spike is fully specified in the design doc §4 (including the daily→instantaneous unit
  bridge and its honest cost) and is the next session's first task.
- **Also:** corrected the NeuralCrop stance — CC-BY-NC permits non-commercial use and this is research, so its
  code IS usable, cited. Owner corrected me; I had over-applied the restriction.
- **Next:** O3 — implement `FDiffPhotosynthesis` per design §4 and quantify online-vs-offline GPP at Hainich.
