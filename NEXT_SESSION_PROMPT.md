# NEXT_SESSION_PROMPT — autonomous completion of the LPJmL-FIT hybrid emulator

> Paste this to the next coding-agent session. It is the standing brief; the durable *state* lives in
> `MEMORY.md` and the *runbook* in `CLAUDE.md` — read those, don't duplicate them here.

## Who you are / mission

You are the sole autonomous engineering agent for the **ESM-ready hybrid land-component emulator** derived
from LPJmL-FIT (S = slow ML trait/size **distribution + demography** emulator — the novelty; F/F_diff = the
differentiable conserving daily biophysical core; E = the surface-energy-balance/skin-temperature closure).
**Mission: finish it** — run offline emulating LPJmL-FIT faithfully **and** online coupled to SpeedyWeather.
You have full autonomy (`STEERING_PROMPT.md`): decide, record each decision in an ADR, commit+push to main
as you go, self-verify at each gate. No owner sign-off is required or expected. **There is no other active
session** — you own the whole thing now.

## Onboard fast (target < 15k tokens)

`CLAUDE.md` (runbook) → `00_START_HERE.md` → `MEMORY.md` (durable state) → then the P1 specifics:
ADR **0018** (growth-ownership), **0020** (S is flux-driven — the governing conditioning contract),
**0021** (S is native Julia; supersedes 0019's port mechanism), `docs/p1_s_in_loop_design.md`,
`docs/slow_flux_conditioning_data_spec.md`.

## Where things stand (main @ `4054f14d`, clean, CI green)

- **★ P1 Tier-1 STEP 1 DONE (2026-07-22):** the flux-conditioning training data is materialised (tier-1, no C
  re-run) — `scripts/build_slow_flux_table.py` + committed Hainich fixture/schema; the `[VERIFIED]` mortality
  physics is re-confirmed on real data and the **`Age` off-by-one** was caught. Next = the native-Julia
  flux-driven S (see *First concrete action* below).

- **Phases 0–4 done; Phase 5 started.** Global daily dataset + water/carbon closure PASSED; S offline
  baseline met (climate-only, warm+dry OOD fails ~32× floor — the gap the hybrid must close); F_diff
  C-validated **Hainich only**; E closes to 1.4e-14 W/m² (not yet validated vs FLUXNET/PLUMBER2).
- **★ P1 Tier-0 JUST LANDED: Component S is IN the coupled loop** (the novelty runs).
  `run_coupled_cell(...; slow=DemographicSlowEmulator(fc))`: F grows cohort carbon at fixed N
  (`grow_annual_accounted!`), then S applies demography (count N / establishment / mortality) through a
  `CarbonLedger`. Carbon conserves at the handoff to **~3e-12 gC ≪ the 1e-6·C_scale gate**; N evolves; energy
  still closes; `slow=nothing` byte-identical. Tier-0 is deterministic/physical-rate, ML-free, TREE-only
  (grass demography stays F-side), fixed cohort roster. Tested in `test/testitems/slow_demography_tests.jl`;
  full CI-faithful suite green **48101 pass / 0 fail / 4 broken**.
- **★ ADR 0020 accepted (governing):** S is **flux-driven, not climate-equilibrium**. Condition on F's
  delivered fluxes as **annual statistics** (extremes/timing/stress-day counts, NOT means) + the
  autoregressive prev-year distribution + N + the slow bioclimatic boundary (Climbuf, coldest-month T, gdd5,
  CO₂, soil, stand age). **Drop this-year raw climate** as a primary driver. `bm_inc` is both a feature and
  the conservation budget. It **overrides ADR 0019's "climate-only weights in P1" clause** — the
  flux-conditioned retrain is now in P1 scope.
- **★ ADR 0021 accepted (governing, owner refinement):** S is **trained AND run in NATIVE JULIA**
  (EvoTrees.jl/DRF + Lux + hand-rolled Julia copula), dependency-light, **no Python at runtime**, shipped via
  a package extension (empty core `[deps]`, ADR 0014). Python is confined to (a) building the training table
  and (b) running the climate-only DirectEmulator as the OOD benchmark. **Build S once** — no
  `src/slow_infer.jl` Python-inference port (supersedes ADR 0019's mechanism). A quick Python feature
  prototype is throwaway; port the design to Julia before the P1 gate.
- **★ Durable SLURM job infra (USE IT):** anything that takes more than a few seconds goes to SLURM so it
  survives session teardown — `scripts/run_tests_slurm.sh [tag]` (CI-faithful suite on a compute node) and
  `scripts/sbatch_julia.sh <tag> --project=. <script.jl>` (any Julia job). Both warm the shared depot on the
  login node first; log to `logs/<tag>.<jobid>.out` with a `=== JOB DONE … exit=N ===` marker; collect from
  any session via `squeue`/`sacct`/`grep JOB DONE`. **Never** run a long job as a login-node foreground /
  `nohup &` / background shell — it dies with the session (this cost the prior session a run). Documented in
  CLAUDE.md §2 + the `julia-test` skill.

## Hard operating rules (do not relax — they are why the physics is trusted)

1. **Long jobs → SLURM** (above). C-binary runs → the `lpjmlfit-cbinary` skill (exact module set, json-c
   0.13.1, restart-from-spinup, config-only daily output).
2. **Conservation is a CI gate:** carbon handoff ~1e-6·C_scale, water ~1e-12, energy ~1e-14. Never merge
   red. `ΔC = NPP − Rh − firec + flux_estabc`.
3. **The C binary is the oracle** — validate F_diff/S against it, never against itself. Adversarially
   re-derive any ported physics against the C source, and confirm the C path actually executes under
   `individual=true` before porting (`lpjmlfit-individual-mode-gotcha`).
4. **Opt-in, default byte-identical:** new physics leaves every committed baseline + the AD trainer
   unchanged until deliberately enabled. Runtime `[deps]` stays EMPTY (ADR 0014); ML/AD are test/train-time
   (extension `ext/FDiffTrainingExt.jl`).
5. **One ADR per non-trivial decision; tag every claim** `[VERIFIED]/[DECISION]/[TODO]/[ASSUMPTION]`.
6. **Commit + push to main as you go** (ADR 0013, main-only). Commit trailer
   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Check CI via the GitHub REST API (gh not on
   PATH) — see the `repo-commit` skill / CLAUDE.md §5.
7. **Before chasing any residual:** invoke the `residual-diagnosis` skill (state the reference basis + a
   falsifiable hypothesis + time-box). Say "Hainich only" wherever a result is single-cell.
8. **Capture knowledge as you go** (procedure→skill, gotcha→CLAUDE.md, decision→ADR, state→MEMORY,
   narrative→JOURNAL); end-of-session retrospective; consolidate MEMORY every ~5 sessions.

## The plan to finish (priority order; each names its gate)

**P1 Tier-1 — the flux-driven S (the immediate next work; ADR 0020).** This is what makes the hybrid beat
the equilibrium-ML baseline.
1. **Materialise the flux-conditioning data** (`docs/slow_flux_conditioning_data_spec.md`). The four
   mortality drivers are already in the annual `ind` output; the genuine gap is per-individual
   `bm_inc`/`nind` (the budget) + the raw `water_stress`/`temp_stress` accumulators — largely reconstructable
   from the existing 186 GB daily set. Three cost tiers (no-recompile → RAW `ind` → a small committed C
   patch+rebuild). **Start on the Hainich prototype cell (global-grid 42490) via SLURM**, then scale to the
   6000-cell biome set. Definitions are `[VERIFIED]` vs `mortality_tree_ind.c`/`waterstress_tree.c`/
   `tempstress_tree.c`.
2. **Train S NATIVELY in Julia (ADR 0021 — do NOT build `src/slow_infer.jl` / do NOT port a Python model).**
   Distributional/count model = **EvoTrees.jl** (or a Julia DRF); NN parts (if any) = **Lux**; Gaussian
   copula Cholesky + inverse-CDF + Poisson/NB sampler = **hand-rolled Julia on `Random.Xoshiro`**. Train
   directly off the aligned table from step 1. Ship the learned S via a **package extension** (weakdeps
   EvoTrees/Lux) so the core keeps empty runtime `[deps]` (ADR 0014), and it runs with **no Python at
   runtime**. Python is confined to step 1's table build + the DirectEmulator OOD benchmark (a quick Python
   feature prototype is throwaway — port the design to Julia before the P1 gate; do not build S twice).
   *Gate:* the native model's Gate-3 accuracy + seeded reproducibility + core `[deps]` stays empty.
3. **Wire the ML channel into `DemographicSlowEmulator` (Tier-1):** extend `FToS` + the within-year
   accumulators to carry the annual **statistics** ADR 0020 specifies (not just means); condition on fluxes +
   AR state + slow bioclimatic boundary. Add K-cap membership **append/merge** (Tier-0 is a fixed roster) —
   rebuild `fc.pools/inds/tmpls/pft_states/bm_inc_acc` **atomically** (design risk #5) and re-derive merged
   height from the merged pools (never mass-average height). Decide grass demography ownership (risk #8).
4. **Gate-3 + the falsifiable ADR-0020 success test:** coupled S-owned marginals vs the offline panel
   (`references/slow_panel_hainich.csv`) and vs the **LPJmL-FIT C ground truth** (the oracle testitem, the
   load-bearing one), AND **flux-driven S beats the climate-only `DirectEmulator` on the warm+dry OOD
   holdout** (closes the ~32×-floor gap — if it does not, ADR 0020 is falsified). Run `residual-diagnosis`
   before chasing any miss.
5. **Gate-4 speed-up:** `scripts/bench_slow_speedup.jl` records the overhead + the C-IBM horizon-collapse
   ratio off the login node, at **matched gate-3 panel error**.

**P2 — validate E vs observations (parallel to P1, non-S).** Source FLUXNET/PLUMBER2 DE-Hai + real
`sfcwind`/`ps` (needs a cross-grid remap — raw GSWP3 `.clm` is a different int16 re-ordered grid; raw cell
42490 ≠ Hainich); sublimation-λ split. *Gate:* LE/H/T_skin within PLUMBER2 bands at ≥1 site.

**P3 — multi-cell generalization** (after P1). Coupled S+F+E on the 6000-cell biome set; held-out **cells and
scenarios**; the LPJ_resilience battery (shuffle test + climate-dependent ACF). *Gate:* per-cell error vs the
seed1-vs-seed2 noise floor; resilience metrics preserved. Also biome-calibrated PFT params + spin-up.

**P4 — online coupling with SpeedyWeather** (after P3 + P5). S/F/E as Terrarium `Abstract*` processes via
`SpeedyWeatherTerrariumExt`; rollout curriculum + input-noise; multi-year free run; OOD warming at constant
CO₂; **fine-tune S online against F_diff's delivered fluxes** (ADR 0020). *Gate:* stable conserving
multi-year free run; gradients flow.

**P5 — reuse + licensing reconciliation** (start early; unblocks P4). The EUPL↔AGPL↔MIT read; new ADR.

**P6 — nitrogen limitation** (research; only after P1–P4). A learned differentiable N-downregulation closure
to lift the constant-CO₂ ceiling.

## Known deferred / gotchas (carry until closed)

- Grass demography is F-side in Tier-0 (`reconcile_demography!` skips grass) — decide ownership before
  generalizing (design risk #8). `sapwood_bg` prognostic growth is static-seeded. Per-PFT competitive
  water-supply is DEFERRED behind the FluxHooks learned lever (`-DPERMUTE` makes a faithful port
  non-differentiable). Enzyme pinned `≤0.13.188`; the Enzyme-reverse canopy path is 1.10-only (guarded
  `VERSION < v"1.11"`). Owner actions (not blockers): formal ADR-0018 stamp, the licensing read, the N-track
  "(c)" discussion.

## First concrete action

**P1 Tier-1 step 1 (flux-conditioning data) is DONE** (2026-07-22, commit `4054f14d`): the annual `ind` ground
truth is already parquet at `/p/tmp/jamirp/emulator_global/ind_hist_seed{1,2}_all.parquet` (no C re-run
needed); `scripts/build_slow_flux_table.py` builds the FToS-mapped tier-1 table (parameterized by `CELLS`),
physics re-verified on real data (`mort_age` 4.97e-8, `mort` identity 8.99e-7 — PASS; caught the **`Age`
off-by-one** → the table carries `age_mort = Age − 1`). Fixture + schema committed under
`test/testitems/references/`. See CLAUDE.md §3, `docs/slow_flux_conditioning_data_spec.md` §4, MEMORY §5,
`[[ind-output-age-offbyone]]`.

Pick up **P1 Tier-1 steps 2–4 — the native-Julia flux-driven S** (the novelty + the P1 gate):
1. **Scale the table to the biome set.** Extend `scripts/build_slow_flux_table.py` to reuse
   `train_slow_emulator.py`'s lat-decile cell selection + `T.climate_zone_holdout` (warm+dry) so the flux-S and
   the climate-only DirectEmulator benchmark share the SAME cells/holdout; add a `NO_DAILY` fast path (annual
   features are complete for all cells; the daily within-year stats read the 186 GB global set — verify its
   `[time,ncell]` layout in `_read_daily_1d` before scaling). Run via SLURM (durable).
2. **Train S natively in Julia (ADR 0021).** EvoTrees.jl/DRF count model + hand-rolled Gaussian-copula
   recruit-trait sampler on `Random.Xoshiro` (+ Lux only if an NN part is needed). Ship as a **package
   extension** (weakdeps EvoTrees/Lux, following `ext/FDiffTrainingExt.jl`; core `[deps]` stays empty, Aqua).
   EvoTrees is pkg-server-fetchable but NOT yet in the depot — warm it on the login node first (compute nodes
   have no GitHub egress).
3. **Wire `FluxDrivenSlowEmulator` into `reconcile_demography!`** (the ONLY method the interface needs; there
   is no `step!` for slow emulators — `run.jl` discards the returned `FToS`, the real surface is the in-place
   `fc` mutation + `CarbonLedger` closure). Add the deferred **daily-flux-statistics accumulation hook** +
   extend `FToS` (opt-in, default byte-identical, guardrail 4). Handle membership append/merge atomically
   (design risk #5) and decide grass ownership (#8).
4. **The falsifiable ADR-0020 gate:** the native-Julia flux-driven S must beat the climate-only DirectEmulator
   on the warm+dry OOD holdout, at matched in-distribution error. Run `residual-diagnosis` before chasing a miss.

Deferred (off the critical path): the minimal tier-3 C patch (`nind`+`turnover_ind`; uncomment
`crownarea/leafarea/bm_inc_counter`; NOT the risky `bm_inc` snapshot) + rebuild + Hainich re-run, for the exact
per-individual budget + the ~14 % non-invertible `growth_eff` rows — do it only when the §7.3 budget tie-out or
the scale-up demonstrably needs it. Log progress in JOURNAL; open an ADR only if you change a governing decision.
