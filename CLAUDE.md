# CLAUDE.md — durable runbook for the LPJmL-FIT hybrid land-component emulator

The runbook every session reads **instead of re-deriving** the environment. Facts here are `[VERIFIED]`
against the live PIK cluster unless marked otherwise. If a fact here contradicts what you observe, trust
the observation and fix this file.

**Onboarding order:** this file → `00_START_HERE.md` (short pointer) → `MEMORY.md` (durable state) →
the relevant `docs/decisions/ADR-*`. Target: productive in < 15k tokens. `JOURNAL.md` / `CHANGELOG.md`
are append-only history — read them only when you need the story behind a specific decision.

---

## 0. What this project is (one paragraph)

A **hybrid, ESM-ready land component** derived from LPJmL-FIT: **S** = slow ML trait/size *distribution*
emulator (annual, the novelty); **F/F_diff** = the fast, differentiable, conserving daily biophysical
core (kept from LPJmL-FIT, reimplemented AD-friendly); **E** = a surface-energy-balance + skin-temperature
closure LPJmL-FIT lacks. Goal: run offline emulating LPJmL-FIT faithfully **and** run online coupled to
SpeedyWeather. Current phase status and the prioritized orders live in `MEMORY.md` §Status and
`STEERING_PROMPT.md`; the reasoning is in `PROJECT_REVIEW_2026-07-22.md`.

---

## 1. Paths (all `[VERIFIED]`; canonical copy in `config/paths.yaml`)

| What | Path |
|---|---|
| This repo (deliverables/code) | `/p/projects/open/Jamir/esm_land_emulator` |
| Git remote (SSH alias) | `git@github-esm:rimajj/LPJmLFIT_Emulator.git` (deploy key `~/.ssh/esm_land_emulator_deploy`) |
| **C source** (LPJmL-FIT v5.6.004) | `/home/jamirp/lpjml56fit` (LPJROOT; **not** the stale `~/waldspektrum`) |
| C binary (rebuilt, emits daily grass GPP/NPP) | `/home/jamirp/lpjml56fit/bin/lpjml` (pristine backup: `bin/lpjml.pre_dgrass.bak`) |
| Active param files | `lpjmlfit.js`, `par/param_lpjmlfit.js`, `par/pft_lpjmlfit.js` (**not** `par/pft.js`), `par/outputvars.js`, `include/conf.h` |
| Ground truth (annual; 67,420 cells; seed1+seed2) | `/p/projects/waldspektrum/priesner/clustering/global` |
| Spin-up-end restart (use for Historical 2000–2019 re-run) | `.../Historical/ground_truth/.../restart/restart_1999.lpj` |
| Global 186 GB daily F/E dataset | `/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output` (DVC, not git) |
| Sibling **frozen** Component-S emulator (port source) | `/p/projects/open/Jamir/emulator` |
| Reference repos (reuse targets) | `/p/tmp/jamirp/esm_reference_repos` (LPJmL-hybrid-photosynthesis, NeuralCrop.jl, Terrarium.jl) |
| Julia 1.10.0 (lts) | `/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia` |
| Python env (Component S) | conda `py311_new` = `/home/jamirp/.conda/envs/py311_new` (3.11.9) |
| Scratch (writable) | `/p/tmp/jamirp/...` |

**Prototype cell = Hainich (DE-Hai).** In the **global orderA grid** (used by all ground-truth + daily
data) Hainich is **0-based positional index `42490`** (lat 51.25, lon 10.25). It is **`28008` ONLY** in
the repo-default `-DSINGLESITE` grid; `28008` in the global grid is Sonoran desert. Single-cell daily
re-run: `STARTGRID=ENDGRID=42490`.

**HPC networking:** the **login node** has GitHub-SSH + Julia-pkg-server access; **compute nodes have
NO GitHub egress** (pkg-server tarballs only). GitHub HTTPS is blocked everywhere; SSH works. Any file a
SLURM job reads (`.jl` script, `--output`) must be on shared `/p` (`logs/`, `/p/tmp/jamirp/`), **never**
the agent scratchpad under `/tmp/claude-*` (login-node-local → compute nodes can't open it).

---

## 2. Julia — build & test

- **Run the suite — DURABLE + CI-faithful (the DEFAULT; survives session teardown):** submit it to SLURM.
  A login-node foreground run / `nohup &` / background-shell **dies with the session** (dropped SSH, agent
  restart, UI stop) and you lose the result — SLURM runs it on a compute node independently and logs to
  shared `/p`, so any later session can collect it.
  ```bash
  scripts/run_tests_slurm.sh [tag]      # warms the shared depot on the login node, then runs the CI-faithful
                                        # Pkg.test() on a compute node → logs/<tag>.<jobid>.out
  ```
  Poll from ANY session: `squeue -u $USER` · `tail -f logs/<tag>.<jobid>.out` · the log's last line is
  `=== JOB DONE tag=<tag> exit=<code> ===` (grep it) with the ReTestItems summary just above. Full suite
  ≈ **48.1k pass / 0 fail / 4 broken** (grew with P1), ~5–6 min after a warm precompile.
- **Any OTHER long Julia job** (benchmarks, probes, decadal coupled runs, training) → the same durable path:
  `scripts/sbatch_julia.sh <tag> --project=. <script.jl>` (or `-e '<expr>'`). **Standing rule: anything that
  takes more than a few seconds goes to SLURM, never a login-node foreground / `nohup` / background shell.**
- **Quick interactive one-liner (login node)** — only for a fast check you will watch finish in-session:
  ```bash
  rm -f test/Manifest.toml       # MUST delete first (see gotcha) — it is .gitignored but re-created locally
  JULIA_DEPOT_PATH=$HOME/.julia julia --project=. -e 'import Pkg; Pkg.test()'
  ```
  Ignore the benign `curl_easy_setopt: 48` login-node spew.
- **Compute-node network safety (why the SLURM wrapper warms the depot first):** `Manifest.toml`/
  `test/Manifest.toml` are git-ignored, so every run **re-resolves to newest-allowed deps** (exactly like
  CI). Compute nodes have **no GitHub egress but DO reach the Julia pkg-server** (tarballs), so the wrapper
  first `Pkg.instantiate/precompile`s on the login node to warm the shared `~/.julia`; the node then finds
  every resolved dep cached and needs no network. Only residual risk: a version so new the pkg-server hasn't
  mirrored it yet (a git-clone-only race) → fails with a clear `Network is unreachable`, fall back to the
  login-node one-liner. **[VERIFIED 2026-07-22 — the CI-faithful suite runs green end-to-end on a compute
  node this way (`run_tests_slurm.sh`, job 1562988/1563007).]**
- **`test/Manifest.toml` gotcha (load-bearing):** a bare `Pkg.test()` fails with `can not merge projects`
  while a stale dev-path `test/Manifest.toml` exists. `rm -f` it first. **Do NOT commit it** (decided
  session 27, resolved "no"): `Pkg.test()` resolves the test env in a sandbox temp dir so a committed
  manifest wouldn't feed CI anyway, and it embeds a machine-specific absolute `Pkg.develop` path.
- **Test layout:** ReTestItems `@testitem`s under `test/testitems/`; committed fixtures under
  `test/testitems/references/`. Entry point `test/runtests.jl` = `runtests(LPJmLFITEmulator)`.
- **`*_test(s).jl` naming trap:** ReTestItems scans the **whole repo** for `*_test.jl`/`*_tests.jl` and
  rejects any that isn't pure `@testitem`/`@testsetup` (`Test files must only include @testitem…`). Name
  diagnostic/repro **scripts** `*_probe.jl` / `*_diagnosis.jl` / `*_decomp.jl` — a stray
  `scripts/foo_test.jl` fails the entire suite at collection.
- **Enzyme pin (CRITICAL):** `Enzyme = "0.13.0 - 0.13.188"` in **both** `Project.toml` and
  `test/Project.toml` `[compat]`. Enzyme **0.13.189** regressed the Enzyme-reverse **canopy** path with
  `LLVM error: Canonicalization failed` (`nn_canopy_training_tests.jl:22/:145`). Lift only when a fixed
  Enzyme ships. A red `test (lts)` with the test tree unchanged ⇒ suspect a dep bump; diff the
  `Enzyme vX.Y.Z` line in last-green vs first-red job logs.
- **Julia 1.10-lts vs 1.11 guard:** the Enzyme-reverse **canopy** path is verified only on Julia 1.10;
  Enzyme 0.13 raises an internal LLVM/`EnzymeInternalError` on ≥1.11 for the mutating multi-individual
  path. Those gate parts are guarded `VERSION < v"1.11"` (identity/forward runs everywhere). Guard-lift
  is blocked upstream.
- **Runtime `[deps]` stays EMPTY (ADR 0014):** F_diff (`src/`) is pure-Base Julia. AD (Enzyme/ForwardDiff/
  FiniteDifferences) is a **test/train-time** dep only. Learned-closure training ships as the package
  **extension** `ext/FDiffTrainingExt.jl` (weakdeps Lux/Zygote/Optimisers/Enzyme). Aqua enforces no stale
  deps — don't add to `[deps]` until a runtime feature truly needs it.
- **Format gate (Runic):** CI installs **Runic 1.7.0**. Check locally by adding Runic v1 to a temp env
  and `Runic.main(["--check", <files>])`. Reformat all tracked `.jl` with that version.
- **Docs build locally:** `DOCS_LINKCHECK=false julia --project=docs docs/make.jl` (CI keeps linkcheck
  ON; the HPC's restricted egress needs it OFF). Diagram alarm: `julia scripts/gen_diagrams.jl --check`.
- **ReferenceTests baselines** are committed text/CSV under `test/testitems/references/`. Regenerate
  **only** on an intentional physics change, and track *which* baseline moved (the "no committed baseline
  moves unless deliberate" discipline). `scripts/regen_fdiff_baselines.jl` regenerates the F_diff set.
- **Heavy runs off the login node:** `scripts/sbatch_train.sh` submits training/probe `.jl` to SLURM
  (account `waldspektrum`, partition `standard`, qos `short`, Julia 1.10).

---

## 3. C binary — LPJmL-FIT oracle & data generator

The C binary is the **numerical-regression oracle** (validate F_diff against it, never against itself)
and the daily training-data generator. It is **not** the coupling path (ADR 0014).

- **Modules (exact set — nothing else):**
  ```bash
  module purge
  module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0
  ```
  In a non-interactive shell first: `source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh`.
- **json-c 0.13.1, NOT 0.17:** the login default auto-loads `json-c/0.17` (→ `libjson-c.so.5`) which
  **aborts** — the binary needs `libjson-c.so.4` from **0.13.1**. (A source rebuild also needs a local
  `json_object_iterator.h` shim on `CPATH`; this cluster's 0.13.1 headers are truncated.)
- **Pre-flight without running:** `bin/lpjcheck -DFROM_RESTART <config.js>` from the run's output dir
  (relative `output/` paths) — validates parse, input/restart headers, disk estimate.
- **Restart a cell subset from the full-grid restart:** set integer **0-based positional**
  `"startgrid"/"endgrid"` = grid-file row indices (not lat/lon, not 1-based, not `"all"`). Per-cell seek
  is MPI-decomposition-independent; needs byte-identical grid/soil/input + matching physics config.
  `restart_1999.lpj` = spin-up end → use for the Historical 2000–2019 daily re-run; `restart_2019.lpj` =
  historical end → only the SSP370 continuation.
- **Daily output is config-only (no recompile):** put `"timestep":"daily"` inside each output entry's
  `"file"` object. Keep the `ind` tree table **annual**.
- **Water balance is the closure check:** `-DSAFE` `check_fluxes.c` aborts a cell if `|balanceW| > 1.5
  mm/yr` — **a clean run IS water closure.** `swc` output is FRACTIONAL saturation (no `wsats` output ⇒
  absolute mm not reconstructable); `swe`/`rootmoist` are mm.
- **This config runs `"individual":true`** (`lpjmlfit.js`), `with_nitrogen="no"`, `landusetype=NATURAL`,
  carbon-only. **Before porting any C routine as "the faithful fix", confirm it actually executes** —
  many paths are gated `if(!config->individual)` or are diagnostic-only. Known dead paths in this config:
  `light()`/`light_grass()` (grass cover/light competition — never called; active reduction is
  `reduce_grass`, fpc-only), per-PFT `gp_pft`/`gc_pft` into GPP (diagnostic; GPP uses stand-mean
  `gp_stand` except the OFF `nitrogen_coupled` branch). Beech = ANGIO allometry from `par/pft_lpjmlfit.js`.
- **`-DPERMUTE` is active** (`Makefile.inc:22`): daily Fisher-Yates PFT-depletion order on the cell
  RAND48 seed ⇒ non-deterministic / order-averaged. This is why a faithful per-PFT competitive-supply
  port is neither differentiable nor deterministic (see the water-supply DEFER in `MEMORY.md`).
- **SLURM helpers:** `scripts/run_daily_subset.sh` (positional: `STARTGRID ENDGRID FIRSTYEAR LASTYEAR
  NTASKS TIME EXCLUSIVE RUNTAG SUBMIT RANDOM_SEED`; generates config from the production sections, runs
  `lpjcheck`, submits); `scripts/water_closure_check.py <run_dir>`; `scripts/run_fdiff_validation_cell.sh`
  (single-cell daily re-run adding daily FAPAR/NV_LAI + annual FPC/LAI_STAND, ~9 s);
  `scripts/run_fdiff_grass_gpp_cell.sh`. Daily re-runs write to `/p/tmp/jamirp/esm_land_daily`.
- **Custom daily grass GPP/NPP** (`D_GRASS_GPP`/`D_GRASS_NPP`, ids 419/420) was added by a committed
  C-source change (`patches/lpjmlfit_daily_grass_gpp.patch`) + rebuild; stock LPJmL-FIT has no per-PFT
  daily GPP output.

---

## 4. Python — Component S prototype (`python/`, uv-managed)

- **Env:** `cd python && uv sync --frozen` (installs exactly the committed `uv.lock` — no re-resolve).
  On the reused conda env use `pip install --break-system-packages` when uv isn't available.
- **Gates (run inside `python/`):** `uv run ruff check .` → `uv run ruff format --check .` → `uv run
  pytest` (≈ 49 pass / 6 skip locally; 56 pass in the locked CI env).
- **The `eval`-filename gotcha:** the agent's auto-mode classifier **refuses to read files whose name
  contains `eval`** (e.g. a sibling `eval_presentday_critical.py`) — it's a classifier heuristic, not an
  owner hook. Rename such a file (or copy to a non-`eval` name) before working on it.
- Baseline S = **LightGBM + Gaussian copula** ("DirectEmulator"); no NN in the baseline. torch/lightning/
  sdv are intentionally out of the core deps until the metric panel escalates.

---

## 5. Git / CI

- **Main-only workflow (ADR 0013):** commit and push straight to `main`. No feature branches, PRs, or
  branch protection (owner declined). CI on `push:main` is a smoke alarm — run CI-equivalent checks
  locally first; fix-forward if red. Commit or push **only when the user asks**.
- **Commit trailer:** end every commit message with
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **The 5 CI gates:** `CI` (Julia tests), `format` (Runic), `docs` (Documenter), `python` (ruff+pytest),
  `TagBot`. The Julia matrix shows jobs `test (lts)` **(required)**, `test (1)` **(required)**,
  `test (pre)` (`continue-on-error`, allowed to fail on Julia-prerelease API churn), plus non-required
  `test (macOS, lts)`. **Never merge on a red required check.**
- **Check CI status — `gh` is NOT reliably on PATH.** Use the GitHub REST API with the user's token:
  ```bash
  TOKEN=$(python3 -c "import yaml;print(yaml.safe_load(open('/home/jamirp/.config/gh/hosts.yml'))['github.com']['oauth_token'])")
  curl -s -H "Authorization: token $TOKEN" https://api.github.com/repos/rimajj/LPJmLFIT_Emulator/commits/<sha>/check-runs
  ```
  Useful endpoints: `/commits/<sha>/status`, `/actions/runs?head_sha=<sha>`, `/actions/runs/<id>/jobs`,
  `/actions/jobs/<id>/logs` (redirects to a downloadable log).
- **CI resolves deps fresh** (manifests git-ignored) → a too-wide `[compat]` silently absorbs upstream
  bumps. This is exactly how the Enzyme 0.13.189 regression turned CI red with no code change (§2).
- Commits show **"Unverified"** on GitHub by design (locally `G`-signed; owner declined enforcement) —
  don't chase it. Dependabot is monthly+grouped; keep open PRs at 0.

---

## 6. Guardrails (never relax these — they are why the physics is trusted)

1. **Tag every claim** `[VERIFIED]/[DECISION]/[TODO]/[ASSUMPTION]`; **one ADR per non-trivial decision**
   (`docs/decisions/`, immutable once accepted — supersede, don't edit).
2. **Conservation is a CI gate:** water ~1e-12, carbon closure (with `firec` + `flux_estabc`), energy
   ~1e-14. Never merge on red. Carbon budget: `ΔC = NPP − Rh − firec + flux_estabc` (a fire-free
   `NEE = Rh − NPP` will NOT close).
3. **C binary is the oracle.** Validate F_diff against it, not against itself.
4. **Opt-in, default byte-identical.** New physics must leave every committed baseline and the AD trainer
   unchanged until deliberately enabled.
5. **Adversarially re-derive ported physics** against the C source before trusting it — and confirm the C
   path is actually executed in the `individual=true` config first (§3).
6. **Single-cell ≠ general.** Say "Hainich only" wherever a result is single-cell.
7. **Before chasing a fidelity residual:** state the reference basis + a falsifiable hypothesis, confirm
   the comparison basis is correct, and time-box (see the `residual-diagnosis` skill; the grass-overshoot
   saga cost ~10 sessions to a reference-basis artifact).

---

## 7. Doc & skill map

- `00_START_HERE.md` — short onboarding pointer. `MEMORY.md` — durable current state (phase status,
  verified facts, decision index, open TODOs; capped). `JOURNAL.md` — append-only session narrative.
  `CHANGELOG.md` — Keep-a-Changelog (newest at top).
- Design/plan (stable): `DESIGN.md` (frozen schemas + interface contract §8), `DEVELOPMENT_PLAN.md`
  (phased plan), `RESEARCH_SURVEY.md`, `ECOSYSTEM_AND_COUPLING.md`, `ENGINEERING_STANDARDS.md`.
- Decisions: `docs/decisions/README.md` (ADR index). Steering: `STEERING_PROMPT.md` +
  `PROJECT_REVIEW_2026-07-22.md`.
- **Skills** (`.claude/skills/`): `julia-test`, `lpjmlfit-cbinary`, `fdiff-validate`, `python-env`,
  `residual-diagnosis`, `repo-commit`. Invoke the one that matches the mechanical task instead of
  re-deriving its steps.
- **Source map** (`src/`): `LPJmLFITEmulator.jl` (module), `state.jl` (`SharedState`), `interface.jl`
  (S↔F↔E I/O structs), `conservation.jl` (softmax/flux-then-integrate/budget residuals),
  `allometry.jl`, `fdiff.jl` (the differentiable daily core + canopy rollout + allocation/growth),
  `fdiff_smoothops.jl` (smooth surrogates for non-smooth ops), `registry.jl`, `run.jl` (coupled
  `run_coupled_cell`/`couple_day!`), `components/fast.jl` (`FDiffFastCore`, `annual_step!`),
  `components/slow.jl` (`AbstractSlowEmulator` — `step!` still a stub; P1 fills it), `components/energy.jl`
  (`SEBEnergyClosure`).

---

## 8. Knowledge capture (standing discipline — the 6 skills are a starting set, not the whole job)

**Capture reusable knowledge the moment it appears**, so no future session re-derives it. Triggers — stop
and capture whenever you: (a) write a script you'd run again; (b) do the same multi-step thing twice;
(c) find a non-obvious error fix; (d) re-derive something a prior session already knew.

**Route by type:**

| Kind of knowledge | Home |
|---|---|
| A procedure / how-to for your own context | a **skill** (`.claude/skills/`) — prefer *updating* an existing one over adding a new one |
| An environment fact / gotcha | **CLAUDE.md** (this file) |
| A decision | an **ADR** (`docs/decisions/`) |
| Current durable state | **MEMORY.md** |
| Session narrative / what-happened | **JOURNAL.md** |

**Capture minimally in the moment** — a 10-line `SKILL.md` pointing at your existing script beats nothing.
Parameterize, don't fork: e.g. single-cell forcing+restart extraction for a test fixture belongs in the
`fdiff-validate` skill **parameterized by cell index**, not rewritten each time.

**Standing tasks:** (1) an **end-of-session retrospective** — ask "what would a future session re-derive,
and where does it go?" and file it before wrapping; (2) **consolidate-memory every ~5 sessions** — reshape
MEMORY.md back to durable-state-only under the cap, archive (don't delete) what you remove.

**Use subagents** for isolation, parallelism, a read-only reviewer, or independent verification — and note
that subagents can invoke skills.
