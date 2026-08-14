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

## 2026-07-28 (cont.) — ADR 0082 + two silent-failure findings in Terrarium's vegetation path  [O2/O3a]
- **Owner steering:** online = best possible ESM, NOT LPJmL-FIT fidelity; validate against observed
  climate/vegetation; and do the soil-moisture validation/retraining.
- **ADR 0082** records it: two explicit configurations. OFFLINE unchanged (guardrail 3, C-binary oracle).
  ONLINE = Terrarium owns skin temperature + SEB + soil water/thermal, we own vegetation (S + FIT
  photosynthesis + FIT water-limited ET via the pluggable `AbstractEvapotranspiration`), scored against
  PLUMBER2/FLUXNET + observed vegetation. Guardrail 3 SCOPED not weakened; conservation binds both.
  ClimBuf cold-starts from a SpeedyWeather-only spin-up on ITS OWN climate (obsclim seeding rejected).
- **Deciding evidence for handing over the SEB:** `surface_energy_balance.jl:128` computes LE *through* the
  ET scheme INSIDE the skin-temperature solve, then :149-151 recomputes ET at the CONVERGED T_skin ⇒ LE and
  T_skin mutually consistent. Component E takes LE from F at a DIFFERENT temperature and makes H the residual
  (ADR 0017's own "no privileged residual" exception). Offline a caveat; online a defect.
- **TWO SILENT-FAILURE FINDINGS in Terrarium's vegetation path — both would have wasted runs:**
  1. `[VERIFIED job 1622826]` Enabling the default `VegetationCarbon` CRASHES a coupled run:
     `AssertionError: vapor pressure deficit must be greater than zero` (`MedlynStomatalConductance`
     asserts `abs(vpd) > 0`, medlyn_stomatal_conductance.jl:51). VPD=0 is physically realizable.
  2. `[VERIFIED job 1622830]` **The default stratigraphy is pure sand (`clay=0`), which collapses SURFEX's
     `wilting_point = 37.13e-3·√(clay·100)` and `field_capacity = 89.0e-3·(clay·100)^0.35` to EXACTLY ZERO**,
     so `plant_available_water = min(1, θw/0) ≡ 1.0` wherever there's water. **It does not error — it
     silently reports "fully unstressed everywhere"**, deleting the drought response while looking plausible.
     This is the more dangerous of the two. Promoted to a PREREQUISITE (O3a): prescribe a real clay/porosity
     field via `PrescribedSoilHorizon`, and add a guard rejecting `field_capacity <= wilting_point`.
- **soilmoist mapping settled semantically:** `soilmoist` ← layer-mean **`plant_available_water`**, NOT
  `saturation_water_ice` (porosity- vs WHC-normalized = a DEFINITIONAL mismatch, not a distribution shift).
  LPJmL training reference measured for the comparison (historic, 1348400 cell-years): min 0.0167, q50 0.4635,
  mean 0.5075. The comparison itself is blocked on O3a — cannot compare against a degenerate PAW ≡ 1.
- **The 2-day coupled run itself worked** (135 s, soil state `(4608,1,30)`) — the harness is solid; both
  failures were in Terrarium's vegetation/soil defaults, not the coupling.
- **Next:** O3a (real soil texture + the degeneracy guard) → O3b (finish the soilmoist comparison, raise the
  line-S integration point) → O3c (the photosynthesis spike).

## 2026-08-05 — O3a done: a real soil texture, the degeneracy guard, and TWO more silent defaults  [O3a/O3b]

- **O3a SHIPPED (ADR 0083).** The online soil is now a single `PrescribedSoilHorizon` carrying the
  **ground-truth run's own** soilcode map × `par/soil_20m.js` sand/silt/clay, with SURFEX porosity.
  `[VERIFIED job 1706262]` the prescription reaches the model state (clay 0.01–0.58, mean 0.182), the
  guard passes (`fc − wp` ∈ [0.0519, 0.0893]), PAW is no longer identically 1. Chosen over SoilGrids 2.0
  deliberately: using the C oracle's own texture keeps the online soil consistent with BOTH the offline
  oracle and the `soilmoist` training reference O3b scores against — SoilGrids would confound exactly
  that comparison, and needs egress the compute nodes don't have.
- **Trap 7 — the documented Terrarium input path DOESN'T WORK under SpeedyWeather.**
  `SpeedyWeatherTerrariumExt` builds its `ModelIntegrator` with an **empty `InputSources(NF)`** (on
  purpose — so its own `set!` of the atmospheric forcings isn't overwritten). So an `InputSource`-based
  prescription, which is what Terrarium's own `soil_heat_global_soilgrids.jl` example uses, is **silently
  dropped**, and `sand_fraction` falls back to its declared default of 1.0 — straight back into trap 6.
  Only `TerrariumLand.fields` is forwarded. There is now a gate that reads `state.soil.clay_fraction`
  back and asserts it is non-zero *and* spatially varying: a dropped prescription looks exactly like a
  working one.
- **Trap 8 — `SoilHydrology(NF)` defaults to `NoFlow`: the soil water NEVER MOVES.** `[VERIFIED job
  1706262]` layer-mean saturation was `min == max == 0.8917` over all 4608 columns after 2 coupled days —
  i.e. exactly the `SoilInitializer`'s `SaturationWaterTable` (vadose 0.75 / saturated below 5 m) —
  *despite* the adapter faithfully pushing `rainfall`/`snowfall` into the Terrarium inputs every step.
  **Any soil-moisture distribution measured under the default hydrology is the initializer, not a model
  result.** This is why my first gate mis-fired: I had gated on "fraction of columns pinned at PAW = 1",
  which is a property of the WATER state, not of the soil configuration. Split it: the O3a gate now
  tests that PAW is a genuine spatially varying function of the state (passes), and the water state is
  reported separately with an explicit "O3b NOT MEANINGFUL" verdict when saturation is uniform.
- **`RichardsEq` works in the coupled loop** `[VERIFIED job 1706324, exit 0]` — 10 simulated days, 1094 s,
  4608×30 columns, saturation spread 0.565, no non-finite. But the answer is **not yet quotable**: from a
  near-saturated initial column the profile is still mid-drainage, mean PAW 0.104 (unweighted) / 0.225
  (top 2 m) against LPJmL's 0.5075. So the two runs BRACKET the reference (NoFlow 0.95 ← 0.5075 → RRE-10d
  0.10) and neither is a spin-up. **Do not report a `soilmoist` shift from either.**
- **The likely root cause of the mismatch is geometry, and it is fixable.** `ExponentialSpacing(N=30,
  Δz_min=0.05)` defaults to `Δz_max = 100`, giving a **433 m** column — 20× LPJmL's 20 m. An unweighted
  30-layer mean over that is dominated by deep permanently-saturated layers and is simply **not the same
  operator** as `slow.jl`'s unweighted mean over 23 layers spanning 20 m. `Δz_max = 2.5` gives ≈19.5 m,
  matching LPJmL's geometry and equilibrating ~20× faster. Added as the `DZMAX` knob; **job 1706462**
  (`FLOW=rre DAYS=30 DZMAX=2.5`) is the first run on the right basis.
- **Cost note for the plan:** RRE at Δt = 300 s over 4608×30 columns runs ~110 s per simulated day and
  allocates 8.3 TiB with 47 % GC time over 10 days. A multi-year spin-up on the 433 m column is days of
  compute; on a 20 m column it should be far cheaper, but the spin-up requirement is now on the critical
  path for O3b and should be sized before O3c is started.
- **Also corrected CLAUDE.md §1:** `28008` is Hainich's index in `input_VERSION2/grid.bin` — a
  longitude-major **global** grid, not a `-DSINGLESITE` grid (orderA[28008] is Sonoran desert). That coord
  file and the ground-truth `soil_code_test.grid.clm` are not interchangeable row-for-row, nor are their
  paired soil-code files. Bit me on the first run of `build_soil_texture_field.py`, caught by its Hainich gate.
- **Next:** read job 1706462 → if the 20 m column gives a plausible spun-up distribution, finish O3b and
  raise the line-S integration point; then O3c (the `FDiffPhotosynthesis` spike).

### Late correction — line S's ADR 0035 moved BOTH sides of the O3b target (2026-08-05)

Found on the pre-merge rebase: S had written a warning block into `lines/O/STATE.md`. **Verified it
against `src/components/slow.jl:227` before acting on it** — it is right, and my script was aimed at a
retired basis on both sides:

- **Runtime target.** No longer `sum(state.w)/length(state.w)`. It is `root_zone_soilmoist(state, soil)`
  = the **`whcs`-weighted mean over `ROOT_ZONE_LAYERS = 3` layers** = LPJmL's 200+300+500 mm = exactly
  **1.0 m**, read at year end. My "top 2 m, thickness-weighted" was the right *shape* but the wrong depth.
- **Reference distribution.** The numbers I had been printing (q50 0.4635, mean 0.5075) are the **retired**
  `swc`-derived table = total water over SATURATION capacity — i.e. the porosity-normalized quantity ADR
  0082 §4 deliberately rejects. Scoring against it would have reintroduced the mismatch from the offline
  side. Live: `cell_year_soilmoist_ye_hist.parquet` — min 0.0 · q25 0.0 · **q50 0.498** · q75 0.877 ·
  q90 0.9999 · **mean 0.478**. Means are close (0.478 vs 0.5075), the SHAPE is not — a quarter of
  cell-years sit at a fully dry root zone. Matching on the mean alone would have hidden that.

Retargeted the script to the 1 m root zone and the live reference, and **cancelled job 1706462**
mid-flight rather than let it produce a number on the retired basis; resubmitted as **1706597**
(`FLOW=rre DAYS=30 DZMAX=2.5`). One simplification worth recording: with a **single**
`PrescribedSoilHorizon` the texture is depth-constant within a column, so `θfc − θwp` cancels in the
normalized weighted mean and the `whcs` weighting reduces **exactly** to thickness weighting. That is a
property of the one-horizon configuration only — a multi-horizon stratigraphy must carry the capacity
weights explicitly.

This is the `residual-diagnosis` rule paying off in the direction it usually doesn't: the comparison basis
was wrong *before* any residual was chased, and the cost of noticing late was one cancelled job rather
than a session spent explaining a fake shift.

### The first O3b measurement on the CORRECT basis — job 1706597 (2026-08-05)

`FLOW=rre DAYS=30 DZMAX=2.5`, exit 0, 2973 s. Column **19.46 m** (LPJmL's is 20 m); root zone = **10 of
30 layers = 0.988 m** (LPJmL's top 3 = 1.00 m). Saturation spread over land 0.903 ⇒ the water state is a
model result, not the initializer. O3a gate passes (PAW spread 0.667, nothing pinned at 1.0).

| quantile | LPJmL live `soilmoist_ye` | Terrarium root-zone PAW (30 d) |
|---|---|---|
| min | 0.0 | 0.0 |
| q10 | 0.0 | 0.0 |
| q25 | 0.0 | 0.0 |
| **q50** | **0.498** | **0.109** |
| q75 | 0.877 | 0.338 |
| q90 | 0.9999 | 0.681 |
| max | 1.008 | 1.0 |
| **mean** | **0.478** | **0.199** |

**Read it honestly, in two halves.** The **dry tail agrees exactly** — min/q10/q25 all 0.0 in both. That is
the distinctive feature of the live reference (a quarter of cell-years at a fully dry root zone, the thing
that the retired `swc` table hid), and the online soil reproduces it without tuning. The **upper half is
systematically too dry**: q50 off by 4.6×, mean by 2.4×.

**This is NOT yet a train/inference shift, and must not be reported to line S as one.** Two confounds are
un-excluded, and both push the same way:
1. **Soil spin-up.** 30 days from a near-saturated column is still draining — mean saturation fell 0.89 → 0.24.
   A monotone drying trend cannot be distinguished from an equilibrium that is genuinely drier.
2. **Atmosphere spin-up.** SpeedyWeather's own precipitation climatology has had 30 days to establish from
   its default initial state, so the soil is being driven by a spinning-up rainfall field.
Only after the distribution stops moving is the residual attributable to Terrarium's hydrology.
**Job 1706979** (`DAYS=90`, same config) is the convergence check: if its distribution matches 1706597's,
the run has converged and the gap is real; if it is drier again, it is still draining.

Cost measured: 30 d = 2973 s (35 G allocations, 25 TiB, 47 % GC) ⇒ ~99 s per simulated day even on the
19.5 m column — the RRE path's allocation behaviour, not the depth, dominates. A multi-year spin-up at this
rate is ~10 h per simulated year and needs either a coarser Δt for the soil sub-step or an upstream fix.

**Next:** read 1706979 → converged: raise the line-S integration point with the numbers; not converged:
extend, and size the spin-up honestly before spending more. Then O3c.

---

## 2026-08-14 — rung 5-pre: the timing gate, the profile, and two integration points (ADR 0084)

**Task.** Build the reproducible end-to-end timing harness `EXECUTION_PLAN.md` §4 asks for — core-seconds
per cell-year for the shipped emulator *and* for the LPJmL-FIT C binary on the same cells and years — and
either reproduce or refute ADR 0093's `1.096 vs 0.290–0.383`. Then attribute the emulator's cost. Then
raise the `solve_lambda` hand-over to line M and the CI-gate request to the integrator. The fence held:
nothing under `src/**` was touched.

**Result: reproduced, and worse than published.** Cell 42490, npatch 25, 1 core — the C is **0.2666**
core-s/cell-year (marginal), the emulator **1.1169** at F+E and **1.2329** at full S+F+E ⇒ **4.62×**.
ADR 0093's F+E arm comes back within **+1.9 %** across 403 commits and a rebuilt C binary, which is
itself worth knowing: line M's work inside the fast core has cost no speed. The rise from 3.8× is two
basis corrections that both widen the gap.

**The two basis errors, because they are the transferable part.**

1. **`bench_emulator.jl` printed `TOTAL coupled S+F+E` and ran no Component S** — `run_coupled_cell`'s
   `slow` kwarg was left at its `nothing` default. I only caught it by reading the script rather than its
   output. Component S turns out to cost 5–22 % (9.4 % at Hainich), so the label was wrong by about the
   size of the thing it claimed to include.
2. **The C side was a whole-process wall time ÷ cell-years.** That carries MPI start-up, the restart read
   and output writing — measured at **17.1 %** of a 20-year single-cell run. The harness now runs the same
   block at two lengths and differences them, which cancels every per-run cost exactly.

**The profile, and the thing I did not expect.** 82.7 % of runtime is the λ solve. But
`EXECUTION_PLAN.md` §4 proposes replacing a bisection with "a fixed-iteration or analytic λ closure", and
**`solve_lambda` is already fixed-iteration** — its cost is that `:673` takes the Newton derivative by
central finite difference, so each of 25 iterations costs three `photosynthesis` evaluations (78–79 calls
per individual per day against the C's ≤30). The profile confirms the arithmetic independently:
`:673`/`:672` = 2.02 : 1, exactly the 2-calls-to-1 the code implies.

The useful method here was **sweeping `nlambda`, which is a parameter, instead of editing the code** —
that measured the λ path's end-to-end worth (4.10× at nlambda=3 for −0.03 % on GPP) from a line that is
not allowed to touch the file. Worth reaching for whenever a hot region sits behind a knob.

⚠ **And an open question I am handing to M rather than answering: GPP is non-monotone in `nlambda`**
(±2.1 %; nlambda=3 lands within 0.03 % of 25 while 12 and 6 sit 2.06 % away), reproducing to three
decimals across two independent runs on different nodes. So it is the solver, not noise, and "25
iterations" is not evidence of convergence. I did **not** verify the mechanism and said so; the code's own
comment at `:660-668` about the degenerate `dg ≈ 0` branch is the obvious candidate. This is a fast-core
physics question and M owns the file.

**Two mistakes I made in the harness, both caught by their own impossibility.**
`profile_fdiff_hotspots.jl` first built `params_nlambda(1)` *inside* the timed closure and duly reported
`nlambda=1` as **slower** than `nlambda=25`. And a two-line concatenated `@printf` format string threw
`ArgumentError` at runtime — after the expensive part had already run — which cost a whole re-submission.
Both are now in the `speed-gate` skill.

**Raised, and out of my hands.** (a) To **line M**: a named single-function hand-over of `solve_lambda`
(23 lines) + the three-line kinetics hoist at `:558-561`, with four tick-box options and a six-part
pre-registered equivalence criterion (ADR 0084 §5). Written into their `## NEXT` so their session banner
prints it. (b) To **the integrator**: wire the harness as a required CI gate, with the event named (the
next merge to `main` touching `src/**`) and the two design constraints that make the obvious form fail
(a runner is not the cluster ⇒ threshold a ratio measured in-job; the `_t8` artifacts are unreachable ⇒
arm F or F+E only).

**Not done, deliberately:** O3b (the online soil-moisture comparison) did not move — the session was
re-tasked onto rung 5, and O3b needs nothing from it. Its handoff is intact and relabelled honestly.

**Jobs:** 1792591 (Julia gate), 1792835 + 1792562 (C arm), 1792811 / 1793072 / 1793368 (profile; the
first died on the `@printf` bug after producing the profile and sweep, the third is the clean run).
**Capture:** new skill `speed-gate`.

---

## 2026-08-14 (session 2) — O3b resolved as VOID: the online soil-moisture diagnostic is clamped

**Entered** with the previous handoff's pick-up list: (1) check line M for a reply to the `solve_lambda`
hand-over, (2) 5d thread-across-cells, (3) read job 1706979 and finish the O3b `soilmoist` comparison.

**M has not replied.** The inbound block is intact and unticked at `lines/M/STATE.md:415`, verified against
`origin/main` so it survived the rebase. M is working inside `src/fdiff.jl` right now (ADR 0137's default flip,
then 0138), which explains the silence. The F-core files stay fenced; the 4.10× λ headroom stays unclaimed.
Did not re-raise — re-raising a live message is how these get duplicated.

**Job 1706979 (90 d) had completed** and returned root-zone PAW quantiles matching the 30-day run to four
significant figures. The previous handoff had *pre-registered* that as "converged ⇒ the 2.4–4.6× dry gap is
real", whose next step was to raise a train/inference shift with line S. Two things stopped me short of that.

1. The agreement was **too** good: `q90 = 0.681` identical, `q75 = 0.3376` vs `0.338`. A Richards-equation soil
   under a live atmosphere does not reproduce its own quantiles to four digits over 60 more simulated days.
2. So I went to the per-column CSVs instead of the log summary — **90.8 % of the 1987 land columns were
   bit-identical to 1e-12**, and the non-zero values took only **nine distinct levels across 909 columns**.

Nine levels is a lattice, so I looked for the lattice. First guess (wetting front from the bottom up, wet below)
was **wrong** — the values are not the bottom-up cumulative thicknesses. Reading Terrarium's own `get_spacing`
for the real geometry and testing the *surface-down* cumulative ladder instead: **94.0 % of land columns land on
it to |Δ| < 1e-5.** That is the whole story — `FieldCapacityLimitedPAW` is clipped at both ends, every root-zone
layer is at one clamp or the other, and the thickness-weighted mean can therefore only report the depth of a
stalled infiltration front. 90 % of the domain sits on four front positions; 47.9 % is bone dry. Whole-column
mean saturation moved +0.070 % in 60 days.

**Mechanism, and the part of it that is ours:** the run is `vegetation = nothing` (forced by trap 5's
`@assert abs(vpd) > 0`). The only remaining sinks — top-layer evaporation and gravity drainage — both push
layers *toward* the clamps. Transpiration is the one sink that removes water from the middle of the column, so
disabling vegetation did not merely remove a feedback: **it removed the range the measured quantity varies
over.** Compounded by a narrow SURFEX window (`fc − wp ∈ [0.052, 0.089]`), already printed by the ADR 0083
guard, which had been sitting in the logs the whole time.

**Verdict: O3b is VOID in this configuration, not "converged, gap real".** The "2.4–4.6× too dry" figure is
retired as a fidelity statement and **nothing was reported to line S** — which is the point of the session,
because the alternative was S retraining two learned artifacts on a soil-moisture basis that is a step
function. The reference basis was *correct* throughout (ADR 0035's live year-end root-zone table); the arm's own
variable was the problem, which is a check the basis discipline did not previously contain.

**Consequences taken.** O3b is re-gated behind a pre-registered `INFORMATIVE` condition written before the arm
exists (< 50 % of columns fully clamped *and* column storage moving > 1 % between two run lengths). **Line O
reorders its own work: O3c (the vegetation/photosynthesis spike) and O4 now precede the comparison**, because a
transpiration sink is a precondition for it being measurable rather than an independent milestone. This needs
nobody else's agreement — it is inside O's own scope.

**Captured** (§8 gate, all in the same commit): `scripts/online_coupling/diagnose_paw_clamping.py` — post-hoc,
no simulation, ~1 s, **exits non-zero on `CLAMPED`** so it gates a comparison rather than informing one, lints
clean under the repo's real rule set; **ADR 0085**; **trap 9** in `online-coupling-env`, plus a correction to
trap 8, whose closing advice ("run two lengths and check it stopped moving") is exactly what failed here;
and the mirror-image basis check appended to the shared `residual-diagnosis` — *checking the reference basis is
not enough, also confirm the measured quantity is not saturated at its own clamps.*

**Method note worth keeping.** The entire result cost **zero new simulation** — it came off CSVs written nine
days earlier. The instinct that paid was distrusting an agreement that was better than the physics could
justify, and going to per-sample data rather than the summary the log had already printed.

**Did not get to:** 5d (thread across cells) — still O's, still needs nobody, now the top actionable speed item.

**Merge + two more captures.** Merged as `83bda486` (collation `22ee0009`); `main`'s `changelog` gate green,
and it was correctly the *only* gate — nothing in the diff is watched. Two incidental captures, both in
`repo-commit`: the shared `residual-diagnosis` conflict (third consecutive session; line S had appended §19 at
the same spot — kept both sides, S's first, and left my section unnumbered so it cannot collide with a future
§20), and a new one worth more than it looks: **`?head_sha=` does no prefix matching, so a short sha returns
`0 runs` at HTTP 200.** That is dangerous here specifically because ADR 0090 makes "no gate triggered" the
common, mergeable case — so the empty list is an answer you are primed to accept for a commit whose gates
actually ran. `rev-parse` first, and cross-check against the gate set the diff predicts.
