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
