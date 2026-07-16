# JOURNAL.md — running log

> Append-only, timestamped. What you did, commands, results, checkpoint outcomes, dead ends.
> Newest entries at the bottom. Keep `MEMORY.md` for durable state; keep this for narrative history.

Entry template:
```
## YYYY-MM-DD HH:MM — <short title>  [phase N]
- Goal:
- Did:
- Result / evidence (paths, metrics, file:line):
- Decisions / MEMORY.md updates:
- Next:
```

---

## (planning handover) — project scaffolding created  [pre-Phase-0]
- Goal: hand the project to the build/train agent with research, source findings, plan, and package in place.
- Did: created `00_START_HERE.md`, `SOURCE_FINDINGS.md`, `DEVELOPMENT_PLAN.md`, `RESEARCH_SURVEY.md`, `MEMORY.md`, this journal, and `config/` (paths, hpc_slurm, environment).
- Result / evidence: source findings verified against the tree (daily-output config mechanism; absence of surface energy balance) — see `SOURCE_FINDINGS.md` and `MEMORY.md` §2.
- Decisions: hybrid (phased) chosen; HPC = PIK; agent re-runs LPJmL-FIT for data. See `MEMORY.md` §3.
- Next: agent reads the four docs, sets up env, verifies build, **locates input datasets** (`config/paths.yaml:lpjml.inputs`; absolute heterogeneous paths under `/p/projects/lpjml/input/...`), re-verifies the two load-bearing findings, reconciles the prototype generation mechanism (BLOCKER, see MEMORY §5), writes `DESIGN.md`, then stops at the DESIGN checkpoint.

## (planning handover) — adversarial review pass + fixes  [pre-Phase-0]
- Goal: stress-test the plan/package before handoff.
- Did: independent reviewer verified all 4 load-bearing source claims (correct) and found defects; fixed all of them across the docs.
- Fixes applied: (D1) carbon budget now includes fire `firec` + establishment `flux_estabc` (GlobFIRM is ON); (D2) energy closure now uses ONE skin temperature — E→F T_skin feedback made mandatory so G is consistent; (D3) LE=λ·ET uses sublimation λ for snow, demand-cap water returned to F; (D4) contradictory prototype recipe converted to an explicit DESIGN reconciliation task (repo has npatch:25 + SINGLESITE, not 50k realizations); (D5) resolved residual-H vs softmax — LE is water-limited so H closes as a documented residual exception; (D6) distributional carbon conservation now specified as flux-then-integrate (advance the population, don't regenerate); (D7) input paths corrected to /p/projects/lpjml/input/... (heterogeneous, no single root); (D8) OOD warming forcing must be a real trajectory, recorded as a dependency; (D9) interface table completed (S→E, carbon F→E); (D10) surface pressure `ps` added as a needed input; (D11) pip deps pinned + `drf` PyPI-name-collision warning. Minors: enth keyed to NHEATGRIDP; reservoir caveat elevated (live in transient run); mortality drivers + file pointers corrected.
- Result: package internally consistent; two Phase-1 blockers (prototype mechanism, input paths) now explicit DESIGN tasks rather than hidden errors.
- Next: as above.

## (planning handover) — ecosystem & coupling assessment (user-requested)  [pre-Phase-0]
- Goal: assess 3 repos the user flagged (LPJmL-hybrid-photosynthesis, Terrarium.jl, SpeedyWeather.jl) for reuse and as a coupling target.
- Did: investigated all three via GitHub/raw/docs; wrote `ECOSYSTEM_AND_COUPLING.md`; threaded decisions into DEVELOPMENT_PLAN §1, START_HERE §1, MEMORY §3/§8, environment.yml.
- Findings: they form one PIK/TUM Julia+Enzyme differentiable ESM ecosystem (+ NumericalEarth.jl coupler), same institute as LPJmL. Terrarium already has the surface energy balance + prognostic skin temperature LPJmL-FIT lacks (→ reuse as component E). LPJmL-hybrid-photosynthesis/NeuralCrop = differentiable-LPJmL-core template (same group). SpeedyWeather = best online-coupled differentiable demo target (documented external-land interface; Enzyme AD; but no carbon cycle → NEE diagnostic-only).
- Decisions: architecture unchanged & validated; stack pivots Julia-first; reuse Terrarium SEB/skin-temp; couple via SpeedyWeather for methodology, CliMA/ICON for real ESM; do offline PLUMBER2/FLUXNET first. License review (AGPL↔EUPL↔MIT) + author outreach flagged as TODO.
- Next: as above (Phase-0 DESIGN now also confirms the Julia stack and studies Terrarium's SEB + the differentiable-λ pattern).

## (planning handover) — NeuralCrop.jl + LPJ_resilience + constant-CO₂ constraint  [pre-Phase-0]
- Goal: assess 2 more user-flagged repos and fold in the CO₂ constraint.
- Did: investigated NeuralCrop.jl (public now) and LPJ_resilience; updated ECOSYSTEM_AND_COUPLING §6, DEVELOPMENT_PLAN §3/§5/§6/§7, MEMORY §2/§3, START_HERE §8.
- Findings: NeuralCrop.jl (Yunan Lin, arXiv:2512.20177) = differentiable Julia/Lux+Zygote LPJmL with NN λ/Vcmax + neural-ODE allocation + rollout training + pretrain→FLUXNET-finetune — but CROP-ONLY (no trees/FIT), scaffold training code, CC BY-NC license → reference/parts-bin, not drop-in F2. LPJ_resilience (Bathiany et al. 2024 GCB) = resilience-metric battery (AC-vs-climate, recovery rate, shuffle test) + finding that forest memory is slow woody-C + climate-dependent population turnover + warning about AR oscillations/AC-gap/blow-up; no license. CO₂: with_nitrogen=no → constant future CO₂ → OOD is warming/precip at constant CO₂; SpeedyWeather no-carbon is a non-issue; CO₂-fertilization projections out of scope.
- Decisions: added resilience battery to §5 eval; reframed OOD; F2 reuses NeuralCrop.jl parts (license permitting) + LPJmL-hybrid-photosynthesis λ-solve; documented constant-CO₂ inherited limitation. License/outreach TODOs logged.
- Next: as above.

## 2026-07-15 14:xx — Phase 0 DESIGN: investigation, verification, DESIGN.md, config resolved  [phase 0]
- Goal: execute the Phase-0 plan — ground-truth the environment, re-verify the two load-bearing findings, resolve inputs + run recipe, reconcile the prototype mechanism, freeze schemas, write DESIGN.md, review it, stop at the DESIGN checkpoint.
- Did:
  - **Ground-truthed the env** (login03). Handover path `/home/jamirp/waldspektrum` is WRONG — real LPJmL-FIT tree = `/home/jamirp/lpjml56fit` (LPJROOT already correct in Makefile.inc:38; binary already built, v5.6.004, git b2e5ca9). User pointed me to the production run script `run_spinup_transient_ground_truth_global_ssp370.sh`.
  - **Re-verified BOTH load-bearing findings myself** against the real tree: daily output = config flag (`fscanoutput.c:390-391`, `iterateyear.c:207-208`, `getmintimestep.c:24-27`); NO surface energy balance (0 hits skin_temp/netrad/energy_balance/bowen; petpar2.c:72 equilibrium ET no wind term; update_soil_thermal_state.c:125 air-temp Dirichlet BC).
  - **4 subagents** (parallel): (1) state vector — confirmed all SOURCE_FINDINGS Q4 with file:line (NSOILLAYER=23, NHEATGRIDP=23, 7 tree C-pools tree.h:50, Climbuf, seed, Sapling); correction: `sla` is in Pft/sapling not Pfttree. (2) output schema — `ind` CSV = 29 cols (pools commented out at fwriteoutput_ind.c:58-67; RAW exposes 4 pools+geometry); banding swc/soiltemp/perc=23, soilc_layer/aet_layer=22; PET=eeq*1.32; ALPHAM=1.391/GM=3.26. (3) reservoir/ET/huss — patch key STABLE under landuse=no even with reservoir=true (full gating chain cited); no energy balance; huss hard dep. (4) prior-work mining.
  - Confirmed `lwnet` = net LW downward-positive (petpar2.c:39,72) myself.
  - **Prior-work finding (major):** sibling offline emulator `/p/projects/open/Jamir/emulator` (LightGBM+copula S) already built on this exact data; its PROJECT_REVIEW.md documents that a pure equilibrium climate→distribution mapping CANNOT do the SSP transient / no-analog future — evidence-based justification for THIS project's hybrid. Reuse its data/eval/env; don't redo.
  - **Data reality:** ground truth ALREADY EXISTS (Historical obsclim 2000–2019 seed1+seed2 = noise-floor pair, 44 GB ind each; SSP370 MPI-ESM1-2-HR 2020–2100 seed1 180 GB + seed2 in progress; restart 120 GB), 67,420-cell 0.5° global grid (63,119 with trees). ALL ANNUAL — no daily output anywhere.
  - **Wrote DESIGN.md** (state vector, interface contract, data schema, build+run recipe, prototype reconciliation, prior-work positioning, limitations, full file:line provenance appendix). **Resolved config/paths.yaml + config/hpc_slurm.yaml** with real values (LPJROOT, modules, inputs, restart, env py311_new, scratch). Updated MEMORY.md §1/§4/§5/§6/§8.
  - **Dispatched adversarial-review workflow** (`review-design-md`, run wf_fb9d234e-b5b): 4 dimensions (citations, completeness vs brief, correctness, adversarial) each finding independently verified.
- Result / evidence: DESIGN.md, config/*.yaml, MEMORY.md updated in `/p/projects/open/Jamir/esm_land_emulator`. All 5 SOURCE_FINDINGS open items resolved; prototype-mechanism BLOCKER + reservoir LIVE caveat both resolved.
- Decisions:
  - Prototype = one existing global cell (candidate Hainich 28008); no single-site re-run needed for S.
  - S conserves carbon at vegc/agb granularity (CSV limit); structure re-derived by allometry; enable RAW `ind` in Phase 1 if per-pool fidelity needed.
  - OOD forcing = the existing SSP370 MPI-ESM1-2-HR trajectory (real GCM, constant CO₂) — not a synthetic delta.
  - **Daily-output run DEFERRED to Phase 1** (it's the first Phase-1 task, needs SLURM + a valid single-site/restart setup; mechanism is already source-verified, so the Phase-0 "findings reproduced" gate is met). Not run on the login node.
- Next: incorporate confirmed review findings into DESIGN.md; append review outcome here; STOP at the DESIGN checkpoint and report. Phase 1 = enable daily output + RAW ind, re-run prototype cell from restart, verify water/carbon budgets close vs globalflux (gate).

## 2026-07-15 15:xx — Phase 0: adversarial review of DESIGN.md + fixes applied  [phase 0]
- Goal: review DESIGN.md before Phase 1 (brief §2 requirement).
- Did: ran a 4-dimension review workflow (citations / completeness / correctness / adversarial), each finding independently verified against source. 22 raised, **16 survived** verification. Applied ALL 16 to DESIGN.md + config.
- Key fixes: (14, only surviving MAJOR) Historical daily re-run must restart from **restart_1999.lpj** (spinup end), NOT restart_2019 (=historical end, for SSP continuation) — both now in paths.yaml. (7/9) reconciled the woody-C contradiction: "data already exists" is true only for Tier-1 aggregate (agb/vegc/traits) S; the sapwood/heartwood memory state (Tier-2) needs allometric reconstruction (pipe model) or a RAW `ind` re-gen of the full ground truth. (10) split the Phase-1 gate: carbon closure testable NOW on annual globalflux; water closure needs the daily re-run. (11) S prototype = small biome-stratified MULTI-cell set, not one cell (one cell can't test the conditional response — the sibling's exact failure). (8) added flux_estabc to the F→E handoff. (1/6) fixed the leafmass citation (not in the fwriteoutput_ind.c:58-67 commented block). (13) noted E reuses Terrarium.jl SEB + carried the AGPL/EUPL/CC-BY-NC licensing blocker. (2) added an energy-reference schema stub (PLUMBER2 vars/units/resolution). (3,4,5,12,15,16) wind-absent-in-production clarification, binary runtime-validated (`bin/lpjml -h` works with netcdf-c/4.9.2), interface units/struct-field signatures, OOD noise-floor scope, F1 callable-interface Phase-3 spike, year-range + SSP daily-ness. 6 findings were refuted (no action).
- Also: validated the binary this phase — `bin/lpjml -h` → "C Version 5.6.004 (Feb 5 2026)" with modules incl. netcdf-c/4.9.2 (pinned in hpc_slurm.yaml). Binary help exposes `-couple host[:port]` (candidate F1/ESM interface).
- Result: DESIGN.md internally consistent + review-hardened; schemas frozen. **DESIGN checkpoint reached.**
- Next: per user, continue with DESIGN_CHECKPOINT_PROMPT.md.

## 2026-07-16 — Engineering scaffold + unit-test-foundation doc edits  [phase 0→1 handoff]
- Goal: stand up the repo as an auditable Julia software product (DESIGN_CHECKPOINT_PROMPT.md / ENGINEERING_STANDARDS.md); apply owner-requested edits adding an explicit unit-test base.
- Did (scaffold): git init on `main`; SSH commit signing + repo-scoped deploy key (`~/.ssh/esm_land_emulator_deploy`) generated; remote `origin=git@github-esm:rimajj/LPJmLFIT_Emulator.git` via SSH alias; committer `jamir.priesner@pik-potsdam.de`. Built Project.toml (pkg `LPJmLFITEmulator`, uuid e4cfba23-…), README/CHANGELOG/CITATION/.gitignore/.gitattributes/.dvcignore/data. Wrote & VALIDATED the Julia src (module/state/interface/conservation/registry/S-F-E stubs load; conservation helpers pass). Five parallel subagents built: `.github/` CI (YAML validated), `docs/` Documenter+ADRs (in progress at time of writing), `test/` 11 scientific-gate @testitems (parse OK; Supposition UUID verified), diagrams (`scripts/gen_diagrams.jl` runs; `--check` diff-alarm proven both ways) + curated Mermaid, `python/` prototype (21 pytest pass in py311_new; hypothesis absent there → clean skips). Validated `bin/lpjml -h` (netcdf-c/4.9.2). Owner: SSH deploy key (auth) + repo `rimajj/LPJmLFIT_Emulator`; public deploy+signing keys handed over to add on GitHub.
- Did (this edit, owner-requested, idempotent): ENGINEERING_STANDARDS.md §2 → renamed to "unit-test base + scientific gates on top" and inserted the testing-pyramid + project-specific unit-test list (incl. the 272.15-vs-273.15 K reference-repo bug rationale). DESIGN_CHECKPOINT_PROMPT.md item 2 → leads with the unit-test base before the tooling list. EDIT 2 (§6 docs-only) and EDIT 4 (FIXED DECISIONS docs-only + closing line) were ALREADY present → skipped.
- Result: committed the two standards edits (docs: add unit-test foundation …). Engineering scaffold otherwise staged for the initial-skeleton commit pending the docs subagent + end-to-end validation.
- Next: finish docs subagent; validate assembled tree; make the initial-skeleton commit; push once owner adds the deploy key; set branch protection; then resume DEVELOPMENT_PLAN §6 (Phase 1).

## 2026-07-16 — Scaffold end-to-end validation (all green) + fixes  [phase 0→1 handoff]
- Goal: validate the assembled tree before the initial-skeleton commit (don't commit red).
- Did & fixed (all surfaced by actually running the suites, not assumed):
  1. **Root `Project.toml`**: removed the malformed empty `[extras]`/`[targets] test=[]` stanza (conflicts with the `test/Project.toml` test-env; `Pkg.test()` errored "target test must be a list").
  2. **ReTestItems discovery**: renamed all test files to `*_tests.jl` — ReTestItems `is_test_file` (ReTestItems.jl:710) only scans `_test(s).jl`/`-test(s).jl`; unrenamed files → 0 items discovered.
  3. **Supposition × ReTestItems incompat**: `@check` inside `@testitem` crashes the worker on Supposition v0.3.5 ("SuppositionReport has no field results"). Rewrote the 3 property testitems (conservation_closure, invariance, physical_boundedness) to seeded **StableRNGs loops** (same property coverage, worker-safe); kept deterministic anchors. Supposition kept as a test dep with a NB comment.
  4. **JET caught a REAL bug**: `Base.@kwdef struct SharedState{T}` generated a zero-param `SharedState()` that referenced unbound `T` in `zeros(T,…)` defaults (6 JET errors). Patching with an extra method triggered "method overwriting during precompilation" (Julia 1.10) → broke Aqua `persistent_tasks`. Fixed by dropping `@kwdef` for **explicit constructors** (`SharedState{T}(;…)` + default-eltype `SharedState(;…)≡SharedState{Float64}`); JET now clean, precompile clean.
- Result / evidence: **Julia `Pkg.test()` = 21071 pass / 6 broken (intentional Phase-6 @test_broken) / 0 fail / 0 error**; JET 0 reports; Aqua all pass; `gen_diagrams.jl --check` exit 0; `bin/lpjml -h` OK (netcdf-c/4.9.2); Python `pytest` 21 pass in py311_new; all CI YAML parse. `SharedState()`→Float64, `{Float32}`→Float32.
- Note: root `Manifest.toml` deferred (main pkg has empty [deps]; pin when Phase-3+ deps are added). curl_easy_setopt:48 warnings during Pkg are a benign PIK login-node libcurl quirk (resolution falls back to cache).
- Next: initial-skeleton commit; push when deploy key added; branch protection; resume Phase 1.

## 2026-07-16 — Scaffold pushed to main; Task-B port started; CI broken; session handoff  [phase 0→1]
- Did: committed the scaffold in chunks (b95627c..57e3a95, all signed `G`) and **pushed `main`** to origin via the deploy key (owner added it). Started **Task B** (canonicalize component S) on branch `feat/port-slow-emulator`: wrote ADR 0012 + index, ported `metrics.py` (full, merged), copied `reference/debias_presentday.json`, created `python/config/`. Wrote `HANDOFF_NEXT_SESSION.md` (takeover prompt).
- BLOCKERS / open:
  - **CI RED on main @ 57e3a95** (owner mail): `python`(4), `format`(2), `docs`(5) annotations. Diagnosed NOT-one-cause: `python` = floating deps + no `uv.lock` → `uv sync` pulls majors (pandas 3 / pyarrow 25 / pytest 9; = Dependabot #1–10); `format` = Runic action/formatting; `docs` = Documenter plugin API + doctest + linkcheck 404 on private-repo URLs. Fix per PRIORITY 1 in the handoff. Don't touch Dependabot PRs #1–10.
  - **"eval"-named file writes/reads DENIED** ("The user doesn't want to take this action right now") — blocks the noise-floor `evaluation.py` module + reading sibling `eval_presentday_critical.py`. Owner decision pending (rename to `noise_floor.py` recommended / clear hook / skip / owner writes). An AskUserQuestion was cut off by a permission-stream error at session end.
  - **`gh` token invalid**, signing key + branch protection = owner actions.
- Result: main has the full scaffold; Task B ~30% (metrics + ADR + reference done; evaluation blocked; transforms/drivers/features/baseline/train/data/tests/README pending). This session's context is near full → handed off.
- Next (next session): read `HANDOFF_NEXT_SESSION.md`. Fix CI (P1) → finish the S port (P2) → Phase 1 daily-output re-run from restart_1999 (P3).

## 2026-07-16 (session 2) — PRIORITY 1: fix red CI on main (three independent causes)  [phase 0→1]
- Goal: get `python`, `format`, `docs` workflows green on main (were red on 57e3a95). `gh` token still invalid → reproduced every failure locally instead of pulling logs.
- Did (all on branch `fix/ci-green` off 57e3a95, reproduced + verified locally, then ff-merged to main):
  - **format (Runic):** installed Runic 1.7.0 (= what `runic-action@v1`/`version:'1'` uses; confirmed action usage via its README — checks all repo .jl by default, setup-julia optional). `Runic.main(--check)` flagged 18 of 24 tracked .jl (alignment spacing, `T<:Real`→`T <: Real`, `2.50e6`→`2.5e6`, `Bool=false`→`Bool = false`, `main`→`return if`). Ran `--inplace`; re-check clean (24/24 ✔). Verified no behaviour change: `Pkg.test()` still **21071 pass / 6 broken**, `gen_diagrams.jl --check` exit 0.
  - **python (deps + ruff):** two causes. (1) floating `>=` + no `uv.lock` → CI `uv sync` pulls breaking majors (pandas 3 / pyarrow 25 / pytest 9 / sklearn 2 = the Dependabot bumps). Added upper-bound caps to pyproject.toml matching known-good py311_new (pandas 2.3.2, pyarrow 23, numpy 2.2.6, sklearn 1.7.2, …; ruff capped <0.15 as pre-1.0 minors move lint rules); installed uv 0.11.29 in an isolated venv; `uv lock` → committed `python/uv.lock` (46 pkgs); workflow now `uv sync --frozen`. (2) `ruff format --check` failed on 3 never-formatted files (data.py, metrics.py, test_metrics.py) → ran `ruff format`. Verified from a CLEAN venv: `uv sync --frozen` + `ruff check` + `ruff format --check` + `pytest` all exit 0 (**27 passed** — hypothesis now present via lock, so property tests run instead of skipping).
  - **docs (Documenter, strict):** the real cause was NOT linkcheck (make.jl didn't even enable it) — it was a broken cross-ref: `[`checkdims`](@ref)` in explanation/architecture.md, because `checkdims` is documented via @autodocs but **not exported**, so it's absent from `Main`. Fixed by adding a `CurrentModule = LPJmLFITEmulator` @meta block (same pattern as api.md/model_description.md/diagrams.md). Also, per ENGINEERING_STANDARDS §4/§9, **enabled `linkcheck=true`** with `linkcheck_ignore=[r"https://github\.com/rimajj/LPJmLFIT_Emulator(/.*)?"]` (our own self-links 404 for unauthenticated linkcheck while the repo is private; all other links still checked) — confirmed active by a broken-link sanity test (`[:linkcheck]` fail) then reverting. Silenced two DocumenterCitations `.bib`-comment warnings (reworded refs.bib `%` comments to drop the literal at-sign cite forms). `julia --project=docs docs/make.jl` builds clean, exit 0.
- Result / evidence: 4 signed commits `50423f1..22a7b37` (style-julia, build-python+lock, style-python, fix-docs) + this journal/changelog. Local verification: Julia tests 21071/6-broken; docs build+linkcheck exit 0; python (clean uv venv) 27 passed + ruff clean. Did NOT touch Dependabot PRs #1–10.
- Decisions: direct-to-main for the CI repair (authorized in handoff; branch protection not yet on; only way to get real CI feedback since `gh` can't open a PR). Committed uv.lock resolves newest-within-cap (sklearn 1.9.0, scipy 1.17.1, xarray 2025.12.0) — newer than py311_new but green; lock is CI's source of truth.
- Next: PRIORITY 2 (finish component-S port on feat/port-slow-emulator), then rebase it onto fixed main. PRIORITY 3 (Phase 1). Owner actions still open: `gh auth login`, branch protection on main, add signing key as type "Signing Key".
