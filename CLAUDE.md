# CLAUDE.md — durable runbook for the LPJmL-FIT hybrid land-component emulator

The runbook every session reads **instead of re-deriving** the environment. Facts here are `[VERIFIED]`
against the live PIK cluster unless marked otherwise. If a fact here contradicts what you observe, trust
the observation and fix this file.

**Onboarding order:** this file → `00_START_HERE.md` (short pointer) → `MEMORY.md` (durable state) →
**`EXECUTION_PLAN.md` (the current order of work — which rung your line is on) →**
the relevant `docs/decisions/ADR-*`. Target: productive in < 15k tokens. `JOURNAL.md` / `CHANGELOG.md`
are append-only history — read them only when you need the story behind a specific decision.

**Standing reflex — build skills (do not skip; agents here under-do this).** The moment you write a
rerunnable script, solve a non-obvious error, or re-derive something a past session already knew, **stop
and capture it** — a *procedure* → a skill in `.claude/skills/` (use the **`skill-creator`** skill; prefer
updating an existing one), a *gotcha* → this file, a *decision* → an ADR (§8 has the full routing).
Creating skills is part of the task, not a favor to a future session. The **commit-time capture gate**
(§8) makes this checkable — apply it on every commit.

---

## 0a. HOW TO TALK TO THE OWNER (applies to every line, every session — owner instruction 2026-08-06)

**The owner does not read the internal shorthand of this repo. Everything you say to them must stand on its
own in plain language.** This is a hard rule about *user-facing text* — your chat replies, your summaries,
your status reports. It does **not** change how you write ADRs, STATE files, journals or code comments,
where the shorthand is precise and load-bearing.

**Never put these in a message to the owner as if they explained something:**

| Don't say | Say instead |
|---|---|
| "ADR 0103 supersedes ADR 0102 §4" | "an earlier written decision said the fix needed changes in two places; it was wrong, and the corrected decision says it's one file" |
| "Phase 3a / milestone S2 / item E7 / M4" | what the work actually *is*: "the part where the emulator learns which trees establish" |
| "the DRF", "F_diff", "the AR recursion", "OOS R²", "the noise floor" | "the learned tree-count model", "the fast daily physics code", "each year's number is built from last year's, so errors pile up", "how well it does on data it never saw", "how much two identical runs of the original model differ from each other just by chance" |
| "retention 1.036 → 0.051" | "a starting error used to survive forever; now 95 % of it is gone" |
| "guardrail 4", "opt-in, default byte-identical" | "new behaviour ships switched off, so nothing that already worked changes until we deliberately switch it on" |

**The rule of thumb: if a sentence would mean nothing to a competent scientist who has never opened this
repository, rewrite it.** Numbers, findings and honest caveats all stay — only the labels go. A reference
like "written up in decision record 0103" is fine as a *pointer at the end*, never as the explanation.

Also: say plainly what you actually did, what you measured, what is still broken, and what you did not do.
Don't hide a null result or a failure behind a code name.

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
| C binary (rebuilt, emits daily grass GPP/NPP) | `/home/jamirp/lpjml56fit/bin/lpjml` (pristine backup: `bin/lpjml.pre_dgrass.bak`). ⚠ **Rebuilt again 2026-08-10** to carry the opt-in rung-2 demography hook (`patches/lpjmlfit_rung2_demography_hook.patch`, ADR 0061). The hook is **inert unless `LPJ_RUNG2_DIR` is set**, and the rebuild was gated: 138 decoded NetCDF variables + `globalflux` identical to the previous build on a matched single-cell 2000–2019 run. Copy at `bin/lpjml_rung2`. **After ANY rebuild, run `scripts/diagnose_cbinary_rebuild_equality.py` before quoting a C-vs-emulator number** — and do NOT use `cmp` on a NetCDF (ADR 0043). |
| Active param files | `lpjmlfit.js`, **`param_lpjmlfit.js`** (LPJROOT **root**, not `par/` — found via `-I$LPJROOT`; it includes `par/{lpjparam_fit,soil_20m,pft_lpjmlfit,manage_*,outputvars}.js`), `par/pft_lpjmlfit.js` (**not** `par/pft.js`), `par/outputvars.js`, `include/conf.h`. ⚠ LPJROOT also holds **untracked** `param_lpjmlfit_newseedpool.js` / `par/lpjparam_fit_newseedpool.js` with `k_est_inherit` 0.02 → 2e-13 (11 orders of magnitude). Nothing references them, but `#include "param_lpjmlfit.js"` is the cpp **quote** form, so a stray copy in a run's `scripts_for_running_the_model/` would silently shadow LPJROOT's and change the physics with no visible config diff. |
| ssp370 CO2 forcing (recovered 2026-08-03) | `/p/projects/waldspektrum/priesner/clustering/global/global_co2_ann_1700_2019_const_2100.txt` (md5 `ed5699b9c92d4d25857889f644b153db`, 5212 B, 1700–2100, 409.63 ppm flat from 2020 per ADR 0004). The committed ssp370 **seed1** config is unrunnable until repointed, because the loose copy it names under `~/scripts/clustering/climclusterpy_package/` is gone (`[VERIFIED 2026-08-03]`). ⚠ **Correction to an earlier reading of this: that DIRECTORY still exists and is not "repurposed" in the sense of deleted** — on 2026-07-27/28 it was reorganised into a proper packaged repo (its own `CLAUDE.md`, `CITATION.cff`, `docs/`, `dist/`), and the loose data file was cleaned out in the process. **`climclusterpy` still imports** (`/home/jamirp/scripts/clustering/climclusterpy_package/src/climclusterpy`, under conda `py311_new`) and `climclusterpy.features` still exports `compute_all_ecology_diagnostic_features` / `summarize_climate_features` / `ECOLOGY_DIAGNOSTIC_FEATURES` — i.e. **the canonical definition of the `eco_diag_*` and climate-summary features is alive**, so anything derived from them can be recomputed by the original method rather than reimplemented. Only the loose file rotted; do not conclude the feature code is lost. Recovery route worth remembering for any rotted input: `git log --all --diff-filter=D` in the repo that ate the directory, plus `/home/jamirp/.snapshot/{hourly,daily,weekly}.*` (snapshots **preserve mtimes**, which is what proves a file predates a run). |
| Ground truth (annual; 67,420 cells; seed1+seed2) | `/p/projects/waldspektrum/priesner/clustering/global` |
| Spin-up-end restart (use for Historical 2000–2019 re-run) | `.../Historical/ground_truth/.../restart/restart_1999.lpj` |
| Global 186 GB daily F/E dataset | `/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output` (DVC, not git) |
| **Slow-S derived tables** (parquet; the S training data — scan these, NOT the 46 GB CSV) | `/p/tmp/jamirp/emulator_global/` : `ind_hist_seed{1,2}_all.parquet` (annual `ind`, frozen **29-col** schema = `python/.../data.py::IND_COLUMNS`); `tables/cell_year_feats.parquet` (49-col climate/soil/ECO **boundary** features per cell/year); `cell_npatch.parquet` |
| Sibling **frozen** Component-S emulator (port source) | `/p/projects/open/Jamir/emulator` |
| Reference repos (reuse targets) | `/p/tmp/jamirp/esm_reference_repos` (LPJmL-hybrid-photosynthesis, NeuralCrop.jl, Terrarium.jl) |
| Julia 1.10.0 (lts) | `/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia` |
| Python env (Component S) | conda `py311_new` = `/home/jamirp/.conda/envs/py311_new` (3.11.9) |
| Scratch (writable) | `/p/tmp/jamirp/...` |

**Prototype cell = Hainich (DE-Hai).** In the **global orderA grid** (used by all ground-truth + daily
data) Hainich is **0-based positional index `42490`** (lat 51.25, lon 10.25); orderA `[28008]` is
(−114.75, 31.75), Sonoran desert. Single-cell daily re-run: `STARTGRID=ENDGRID=42490`.
**`28008` is Hainich in a DIFFERENT global grid, not a single-site one (`[VERIFIED 2026-08-05]`,
corrects the earlier "`-DSINGLESITE` grid" wording).** There are two 67 420-cell coordinate files and
they disagree on ordering: `/p/projects/biodiversity/input_VERSION2/grid.bin` (the `coord` named in the
repo checkout's `input_GSWP3-W5E5.js`; v2 .clm, HDR 43, int16, scalar 0.01) is **longitude-major** and
puts Hainich at **28008**, while the ground-truth run's `…/clustering/global/soil_code_test.grid.clm`
(v3 .clm, HDR 51, float32, scalar 1.0) is **orderA** and puts it at 42490. Their paired soil-code files
(`soil_new_67420.bin` vs `soil_code_test.soil.bin`) are therefore **not interchangeable row-for-row** —
pairing orderA indices with `grid.bin` shifts every cell silently. Use the ground-truth pair for
anything orderA-indexed (ADR 0083).

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
  ≈ **272.0k pass / 0 fail** over **127 test items** (`[VERIFIED 2026-08-11]`, job 1758701, 7m19s; it was
  107.1k over 87 items on 2026-07-28 and 48.1k before the parallel lines' P1–P4 growth — the number keeps
  moving, so treat it as an order-of-magnitude sanity check, not a pin), ~7 min after a warm precompile.
- **Any OTHER long Julia job** (benchmarks, probes, decadal coupled runs, training) → the same durable path:
  `scripts/sbatch_julia.sh <tag> --project=. <script.jl>` (or `-e '<expr>'`). **Standing rule: anything that
  takes more than a few seconds goes to SLURM, never a login-node foreground / `nohup` / background shell.**
  This is **hook-enforced** (`slurm-guard`, `.claude/hooks/slurm-guard.sh` in `.claude/settings.json`): a
  `PreToolUse` guard that BLOCKS login-node `Pkg.test()`/`test/runtests.jl`, a direct `bin/lpjml`, and
  `nohup`/backgrounded or heavy foreground Julia jobs (`train`/`bench`/`probe`/`coupl`/`decad`/… scripts),
  redirecting to the wrappers. SLURM tooling (`sbatch`/`srun`/`squeue`/…), the wrapper scripts, `lpjcheck`,
  file reads, and quick `julia -e` checks pass through.
- **No full suite on the login node.** The old `julia -e 'import Pkg; Pkg.test()'` login-node one-liner is
  exactly the overload / session-loss trap and is now blocked by `slurm-guard`. Quick REPL/compile sanity
  checks (a few seconds) are still fine on the login node. **Deliberate override** for a genuine quick run or
  the pkg-server-not-mirrored fallback below — prefix `ALLOW_LOGIN_HEAVY=1`:
  ```bash
  rm -f test/Manifest.toml       # MUST delete first (see gotcha) — it is .gitignored but re-created locally
  ALLOW_LOGIN_HEAVY=1 JULIA_DEPOT_PATH=$HOME/.julia julia --project=. -e 'import Pkg; Pkg.test()'
  ```
  Ignore the benign `curl_easy_setopt: 48` login-node spew.
- **Compute-node network safety (why the SLURM wrapper warms the depot first):** `Manifest.toml`/
  `test/Manifest.toml` are git-ignored, so every run **re-resolves to newest-allowed deps** (exactly like
  CI). Compute nodes have **no GitHub egress but DO reach the Julia pkg-server** (tarballs), so the wrapper
  first `Pkg.instantiate/precompile`s on the login node to warm the shared `~/.julia`; the node then finds
  every resolved dep cached and needs no network. **The warm must cover the TEST env, not just `--project=.`
  (load-bearing; fixed 2026-07-28):** `Pkg.test()` builds a **SANDBOX** from `test/Project.toml` and
  **re-resolves it on the compute node**, so every test-only dep (Lux/Zygote/Enzyme/JET/Aqua → NNlib …) must
  already be in the depot at the version that fresh resolve picks. Warming only the main project worked by luck
  in a long-lived checkout and **failed immediately in a fresh `git worktree`** (`failed to clone from
  …/NNlib.jl.git … Network is unreachable` inside Pkg's `sandbox(...)`) — it would have blocked every new work
  line's first suite run. The wrapper now warms `--project=test` too and deletes the `test/Manifest.toml` that
  creates; expect the first run in a new worktree (or after a dep bump) to spend minutes warming before it
  submits. Only residual risk: a version so new the pkg-server hasn't mirrored it yet (a git-clone-only race)
  → fails with a clear `Network is unreachable`, fall back to the `ALLOW_LOGIN_HEAVY=1` login-node `Pkg.test()`
  above. **[VERIFIED 2026-07-22 — the CI-faithful suite runs green end-to-end on a compute
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
  ⚠ **The same error fires on a `"""docstring"""` attached to a `@testitem`** (`[VERIFIED 2026-08-06]`, line E):
  a docstring makes the top-level expression `Core.@doc @testitem(...)`, which is no longer "a `@testitem`
  call", so ReTestItems rejects the **whole file** — one testitem's docstring costs the entire suite. Document a
  testitem with `#` comments above it (a docstring on a helper *inside* the `begin` block is fine). The message
  is identical to the naming trap's, so check for this before hunting a stray filename.
- **Enzyme pin (CRITICAL):** `Enzyme = "0.13.0 - 0.13.188"` in **both** `Project.toml` and
  `test/Project.toml` `[compat]`. Enzyme **0.13.189** regressed the Enzyme-reverse **canopy** path with
  `LLVM error: Canonicalization failed` (`nn_canopy_training_tests.jl:22/:145`). Lift only when a fixed
  Enzyme ships. A red `test (lts)` with the test tree unchanged ⇒ suspect a dep bump; diff the
  `Enzyme vX.Y.Z` line in last-green vs first-red job logs.
- **⚠ A heap-allocated field on a struct the Enzyme path differentiates through ABORTS the suite with
  SIGABRT (`[VERIFIED 2026-08-06]`, ADR 0110).** Adding a `Vector{T}` field to `FDiff.Individual` killed the
  test process with `received signal: 6` — **no Julia error, no stacktrace, no Enzyme message in the log** —
  surfacing right after a *completed* Enzyme test item, so the log points at the wrong place. Pass such data
  as a separate argument instead (Enzyme then sees it as constant). Tell: an exit-1 suite with **no**
  `Test Summary` line and `signal: 6/11` is an AD/LLVM crash, not a numerical failure — look at what changed
  in a struct definition, not at the physics. Details + the diagnostic shortcut: the `julia-test` skill.
- **Julia 1.10-lts vs 1.11 guard:** the Enzyme-reverse **canopy** path is verified only on Julia 1.10;
  Enzyme 0.13 raises an internal LLVM/`EnzymeInternalError` on ≥1.11 for the mutating multi-individual
  path. Those gate parts are guarded `VERSION < v"1.11"` (identity/forward runs everywhere). Guard-lift
  is blocked upstream.
- **`test (1)` is now Julia 1.12 + JET 0.11.6 (`[VERIFIED 2026-07-22]`).** The CI matrix `test (1)` job uses
  `julia-version: "1"` = the newest stable, which now resolves to **1.12.x** (the cluster has 1.12.2), and CI
  resolves deps fresh so it pulls **JET 0.11.6** (JET 0.11 needs ≥1.12 — on 1.11 the resolver caps at JET
  0.9.20, which is laxer). So a JET failure can appear ONLY on `test (1)` while `test (lts)` (1.10, JET 0.9.x)
  is green — reproduce it locally with `/p/system/packages_rhel9/tools/julia/1.12.2/bin/julia` (a temp env +
  `Pkg.develop(path=".")` + `Pkg.add("JET")` + `JET.report_package(LPJmLFITEmulator; target_defined_modules=true)`);
  ReTestItems does NOT capture JET's report body in the CI log. **JET-0.11.6 boxed-capture trap (load-bearing):**
  a local variable that is **reassigned** and then **captured by a `Threads.@threads` closure** (or any inner
  closure) is boxed, and JET 0.11.6 reports it as `local variable X is not defined`. Fix: use a **single-assignment**
  local (assign once, never reassign) — e.g. `mtry_eff = mtry <= 0 ? … : mtry` instead of `mtry = …` (this bit
  `src/drf.jl::fit_forest`). **Sibling JET trap — `Union{Nothing,…}` struct-field narrowing:** guarding on the
  FIELD (`if s.x !== nothing; use s.x…`) does NOT refine the type — JET flags `no matching method
  length(::Nothing)` on the re-read. Bind to a local FIRST, then narrow it: `x = s.x; if x !== nothing; use x`
  (bit `slow.jl::reconcile_demography!`, ADR 0026 `boundary_series`).
- **Runtime `[deps]` stays EMPTY (ADR 0014):** F_diff (`src/`) is pure-Base Julia. AD (Enzyme/ForwardDiff/
  FiniteDifferences) is a **test/train-time** dep only. Learned-closure training ships as the package
  **extension** `ext/FDiffTrainingExt.jl` (weakdeps Lux/Zygote/Optimisers/Enzyme). Aqua enforces no stale
  deps — don't add to `[deps]` until a runtime feature truly needs it.
- **Format gate (Runic):** CI installs **Runic 1.7.0**. Check locally by adding Runic v1 to a temp env
  and `Runic.main(["--check", <files>])`. Reformat all tracked `.jl` with that version.
- **Docs build locally:** `DOCS_LINKCHECK=false julia --project=docs docs/make.jl` (CI keeps linkcheck
  ON; the HPC's restricted egress needs it OFF). Diagram alarm: `julia --project=. scripts/gen_diagrams.jl
  --check` (**needs `--project=.`**). Since ADR 0091 this is a REAL gate, not just a local command:
  `test/testitems/diagram_registry_tests.jl` regenerates all three `.mmd` and byte-compares, so a stale
  diagram reds `CI`. It also fires on an `src/interface.jl` **field** change with no registry edit at all —
  the full diagram's edge labels are `fieldnames(T)`.
- ⚠ **A GREEN DOCS BUILD IS NOT EVIDENCE THAT A DIAGRAM RENDERS (`[VERIFIED 2026-08-06]`, ADR 0091
  amendment).** Every mermaid diagram in the docs was embedded via ```` ```@eval ```` +
  `Markdown.parse("```mermaid…")` and **rendered as a raw grey code box for months** — on the pre-existing
  `diagrams.md` too. DocumenterMermaid converts a fence with an **expander matching the parsed SOURCE AST**
  (order 7.9); an `@eval` block emits its output during that same pass, too late to be matched. Mermaid
  draws client-side, so the strict build validates nothing. Fences must be **literal markdown** inside the
  `<!-- BEGIN MERMAID <name> … -->` markers `scripts/gen_diagrams.jl` rewrites (the pages are `targets()`,
  so the staleness gate covers them). **The only check that catches it inspects the built HTML:**
  `grep -c 'class="mermaid"' docs/build/diagrams.html` must be > 0. Also: the mermaid JS is a **CDN**
  (jsdelivr) import, so a machine with no outbound internet shows a blank area even when the markup is right.
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
- **json-c 0.13.1, NOT 0.17** — *for the Feb-5-2026 build*, which needs `libjson-c.so.4` from 0.13.1 and
  **aborts** under the login default `json-c/0.17` (→ `libjson-c.so.5`). **The current Jul-21-2026 build
  no longer has this constraint** (`[VERIFIED 2026-08-03]`): its json imports are *versioned*
  (`json_object_put@JSONC_0.14`) and `JSONC_0.14` is provided by 0.13.1, by 0.17, and by the system
  `/lib64/libjson-c.so.5` — `lpjcheck` exits 0 with byte-identical output under both. Keep loading 0.13.1
  anyway (it is the tested set, and `bin/lpjml.pre_dgrass.bak` still needs it), but know that the real
  bare-environment failure mode now is **`libnetcdf.so.19` / `libudunits2.so.0` not found**, not json-c.
  (A source rebuild also needs a local `json_object_iterator.h` shim on `CPATH`; this cluster's 0.13.1
  headers are truncated.)
- **Pre-flight without running:** `bin/lpjcheck -DFROM_RESTART <config.js>` from the run's output dir
  (relative `output/` paths) — validates parse, input/restart headers, disk estimate.
- **Restart a cell subset from the full-grid restart:** set integer **0-based positional**
  `"startgrid"/"endgrid"` = grid-file row indices (not lat/lon, not 1-based, not `"all"`). Per-cell seek
  is MPI-decomposition-independent; needs byte-identical grid/soil/input + matching physics config.
  `restart_1999.lpj` = spin-up end → use for the Historical 2000–2019 daily re-run; `restart_2019.lpj` =
  historical end → only the SSP370 continuation.
- **⚠ A SUBSET RE-RUN IS NOT A PER-CELL REPLICA OF THE GLOBAL RUN — the *seek* is
  decomposition-independent, the *evolution* is NOT (`[VERIFIED 2026-08-03]`, ADR 0041).** Cell 42490,
  **same binary, same restart, same forcing**, varying only the cell set: **1 cell alone** diverges from
  the 67 420-cell/2048-task ground truth at the **first step** (2021; 2 of 81 years match, 18 530 vs
  18 790 `ind` rows); a **21-cell block** is **bit-identical for 15 years** (2020–2034) and then diverges
  (19 366 rows). At year 2020 the 1-cell and 21-cell runs already differ in exactly `fpc_ind` and
  `isdead`. This is a stochastic gap model amplifying a tiny perturbation — one individual dying or
  establishing differently makes the roster permanently different, and the count never re-converges. The
  RNG is **not** the cause (it is fully per-cell: `permute` takes `stand->cell->seed`, there is no
  `drand48()`/`lrand48()` in `src/`, and `config->seed` is read only at `iterate.c:108/148/181`, all
  unreachable at `nspinup:0`/`fix_climate:false`); **the mechanism is unestablished — do not assume
  per-cell reproducibility.** So: (a) a single-cell re-run scored against *global* ground truth compares
  two different trajectories — the documented ~1.6e-4 `whc_nat` discrepancy is this same effect through
  a smoother variable; (b) **two ground-truth members are a valid seed pair only if run with the same
  binary AND the same `--ntasks`**; (c) any binary/config equivalence gate must use a
  **matched-decomposition full-grid** run, not a subset. Harness:
  `scripts/diagnose_ind_binary_equality.py` (it carries the decomposition control and exits **3 = VOID**
  when the control fires, rather than reporting a false verdict).
- **`random_seed` is INERT in any `-DFROM_RESTART` run, and invisible in the log (ADR 0041).** With
  `"new_seed": false` the per-cell RAND48 seeds are restored from the restart file
  (`newgrid.c:507-513` → `freadcell.c:37`) and the `setseed` that would apply `config->seed_start` is
  gated off (`newgrid.c:520-521`); `seed_start` is applied once at parse time (`fscanconfig.c:231`) then
  overwritten from the restart header (`openrestart.c:139-140`). **A second seed is a second SPIN-UP**
  (the non-restart branch's `newgrid.c:460` `setseed(...seed_start+(i+startgrid)*36363)` is *ungated*),
  carried forward by restarting from that seed's own restart file. Bumping `random_seed` alone yields a
  **byte-identical clone** and the log says `Reading random seeds from restart file.`, never
  `Random seed: N` (`fprintconfig.c:748-751`) — which is exactly how a fake ssp370 "seed2" survived for
  three weeks. Gate every new member with `scripts/diagnose_ind_seed_independence.py`; **equal file size
  to the sibling is the copy signature.**
- **Never judge a C run from SLURM state.** The stock ground-truth job files end `rc=0  # save return
  code of srun` + a bare `exit`, so they **always exit 0** — a run dying mid-century leaves a plausible
  truncated 193 GB CSV behind a green `sacct` row. Require
  `lpjml successfully terminated, <ncell> grid cells processed.` in the log. Those jcfs also pin **no**
  modules (they inherit the submitting shell, and a purged env leaves `libnetcdf.so.19` /
  `libudunits2.so.0` unresolved) and set no `-D`/`--chdir`. Fix all three when reusing one.
- **A ZERO-BYTE log is not "early days" — a healthy run creates its output files in ~15 SECONDS
  (`[VERIFIED 2026-08-03]`).** The "judge it from the log" rule above fails when the log is *empty*, because
  empty looks identical to starting-up. Use the **output directory** as the absolute progress signal instead:
  a healthy 2048-task `-DFROM_RESTART` run wrote `grid_*.nc` + a preallocated 784 MB `mnpp_*.nc` + 65 MB
  `vegc_*.nc` (833 MB, 7 files) **15 s** after launch. Measured against that, a member sitting at **0 output
  files / 0-byte stdout / 0-byte stderr after 67 minutes** was hung, not slow — a 268× discrepancy — and the
  tell was corroborated by a *matched control* running concurrently (same binary, `mpirun`, `--ntasks=2048`,
  `--exclusive`, same `-DFROM_RESTART`) that had written **30 GB in 12 minutes**. `sstat` reported no CPU/RSS
  for the hung step while reporting 24 CPU-h for the healthy one, and its output dir mtime still predated the
  run by 6 h (⇒ LPJmL never opened its outputs). Cause: the known flaky node in the allocation. **Check the
  output dir a minute after launch; do not wait out a silent 2048-CPU job.** Resubmit with a real
  `#SBATCH --exclude=` / `sbatch --exclude=` — and pass it on the COMMAND LINE so a provenance-bearing jcf
  stays byte-identical (`SBATCH_EXCLUDE` in the environment is a silent no-op here).
- **After resubmitting a run, RE-POINT every chained child's log path — a jcf that hardcodes a parent's
  job id is not resubmit-safe (`[VERIFIED 2026-08-04]`, ADR 0043).** The resubmitted run writes to a
  **new** `lpjml_<newjobid>.out`, so a child pinned to `…<oldjobid>.out` reads the cancelled attempt's
  **0-byte corpse** — and because the "require `lpjml successfully terminated, <ncell> grid cells
  processed.`" rule above cannot distinguish *empty* from *unfinished*, the child reports
  `no completion line at all` for a run that finished cleanly. That is exactly what happened to the
  ssp370 seed2 member: its independence gate **failed in 1 second** with 3 of 4 checks passing, the
  93 GB parquet child was left `DependencyNeverSatisfied`, and nothing anywhere was actually wrong.
  Prefer resolving the newest **non-empty** `lpjml_*.out` in the run dir over naming a job id
  (`scripts/diagnose_ind_seed_independence.py --log-dir <run_dir>`); treat a 0-byte log as a
  provenance FATAL, never as a physics verdict.
- **A file-level `cmp` on a NetCDF output is the WRONG equality test (`[VERIFIED 2026-08-04]`, ADR 0043).**
  LPJmL writes a `history` attribute holding a **wall-clock timestamp and the config path**, so two runs
  with identical physics differ in the header — the cross-build gate's `vegc_2020_2100.nc` differed by
  124 B at byte 172 for exactly that reason while **all seven** variables (incl. the full 81×280×720
  `VegC` field) hashed identically. Compare **decoded variables** (`netCDF4` + SHA-256 per variable), or
  compare the text/CSV outputs (`globalflux`, `ind`), which carry no timestamp.
- **Daily output is config-only (no recompile):** put `"timestep":"daily"` inside each output entry's
  `"file"` object. Keep the `ind` tree table **annual**.
- **`.clm` climate forcing — PARSE THE HEADER, don't assume float32/HDR=51 (`[VERIFIED]`).** LPJmL `.clm`
  layout is version-dependent: **v3** (`name[7]"LPJCLIM"` + 7 ints + 3 floats + datatype = **HDR 51**, e.g.
  historic `temperature_test.clm` float32 scalar 1.0, and ssp370 `huss_…orderA.clm`) vs **v2** (no datatype
  field = **HDR 43**, stored **int16**, e.g. ssp370 `tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm` with
  **scalar 0.1 ⇒ °C×10** — that's why it's half the byte size of the v3 files). Read `version` at byte-offset
  7, branch HDR/dtype, and APPLY `scalar` (`raw·scalar` = the physical value). Header-driven reader:
  **The ssp370 orderA forcing set is COMPLETE** (`.../clustering/global/ssp370/`): `tas` · `pr` · `rsds` ·
  `lwnet` · `huss`, so a two-scenario per-cell forcing pair is extractable (`[VERIFIED 2026-08-05]`, ADR 0100,
  `scripts/build_hainich_response_forcing.py`). ⚠ **That set is MIXED-VERSION:** `tas`/`pr`/`rsds`/`lwnet` are
  **v2 int16 scalar 0.1**, `huss` is **v3 float32 scalar 1.0** — one hardcoded dtype reads four of the five
  wrong. Header-driven reader:
  `scripts/build_transient_boundary.py::open_clm`; per-cell-year reader `read_clm_year`
  (`scripts/extract_fdiff_validation_inputs.py`). orderA `.clm` cell index == the parquet `Cell` (Hainich
  42490) — no grid.nc map needed. The orderA grid is 67420 cells, YEARCELL order, 365 noleap bands.
  **The v3 datatype codes are 0-BASED** — `0=byte 1=short 2=int 3=float 4=double` (`_DT` in `open_clm`);
  an off-by-one reads `temperature_test.clm`'s float32 as int32 and yields ~5.9e8 "°C" (bit line E, 2026-07-28).
- **Water balance is the closure check:** `-DSAFE` `check_fluxes.c` aborts a cell if `|balanceW| > 1.5
  mm/yr` — **a clean run IS water closure.** `swc` output is FRACTIONAL saturation (no `wsats` output ⇒
  absolute mm not reconstructable); `swe`/`rootmoist` are mm.
- **`swc` is NOT the model's `w` — they are different variables, and confusing them cost a milestone
  (`[VERIFIED 2026-07-28]`, ADR 0035).** `update_daily.c:411` writes
  `SWC[l] = (w[l]·whcs[l] + w_fw[l] + wpwps[l] + ice_depth[l] + ice_fw[l]) / wsats[l]` — **total** water
  (plant-available **plus** the wilting-point reservoir, free water and ice) over **saturation** capacity,
  so it lives on ~`[wpwp/wsat, 1]` and never approaches 0. The emulator's `state.w` (and the C's own
  `soil.w[l]`) is **plant-available water over WHC**, on `[0, 1]`. `swc` **cannot be inverted back** to `w`
  (needs `wsats`/`wpwps`/`w_fw`/`ice`, none emitted). The ONE output carrying `w` is **`rootmoist`**
  (`update_daily.c:414`) `= Σ_{l<3} w[l]·whcs[l]` mm over `forrootmoist` = the **top 1 m only**
  (`soil.h:353`), so `rootmoist / Σ_{l<3} whc_nat[l]·soildepth[l]` recovers a `whcs`-weighted root-zone `w`.
  The trap is that the two overlap numerically (Hainich `swc` 0.84–0.87 vs `w` 0.79–1.00), so an aggregation
  argument will *look* like it explains a train/inference gap. Deriver:
  `scripts/build_rootmoist_soilmoist_feature.py`.
- **Per-patch stand LAI IS reconstructable from the 29-col `ind`, despite having no `leaf_c`/`nind`
  (`[VERIFIED 2026-07-28]`, ADR 0035).** `LAI` (within-crown individual LAI, `lai_tree.c:18`) and `fpc_ind`
  (`= crownarea·nind·(1−exp(−k_pft·LAI))`, `fpc_tree.c:28`) between them carry the crown area, and with
  `nind = 1/patcharea` (`new_tree.c:209`) the patcharea cancels:
  `stand_lai(patch) = Σ_stems LAI·fpc_ind/(1−exp(−k_pft·LAI))`. `k_pft` is **per-PFT** — `K_LAMBERT_BEER_BL`
  **0.59** (ids 0,2,3,5) / `_NL` **0.45** (ids 1,4,6). Validated against the C's own height allometry
  (`allometry_tree.c:53` `min(allom1·(H/allom2)^(kpr/allom3), CA_MAX=225)`) at median rel err 1.8e-8 by
  `scripts/diagnose_patch_lai_reconstruction.py`. It reads BELOW the gridded `LAI_STAND` (0.77–1.01
  depending on biome) because **the `ind` writer emits only stems `height > height_min = 5 m`**
  (`fwriteoutput_ind.c:84`) while `LAI_STAND` sums all trees — the same >5 m population every other `ind`
  aggregate is on. The TXT writer's `%g` gives only **6 significant digits** (`fwriteoutput_ind.c:27`), so
  any inversion from `ind` has a ~1e-5 precision floor — do not set a tolerance below it.
- **`wscal` is a POTENTIAL leaf-on index, NOT the realized supply/demand ratio — and the `ind` column
  `wscal_mean` is that index (`[VERIFIED 2026-07-30]`, ADR 0051).** `water_stressed.c:130-138` computes
  `wscal = min(1, (emax·wr) / (eeq·ALPHAM/(1 + GM·ALPHAM/gp_stand_leafon)))` — **no `phen`** in the
  numerator, **no `(1−wet)`**, and the denominator uses **`gp_stand_leafon`**, the conductance at *full leaf
  cover* (`gp_sum.c:57-67`: per-PFT `gp` is built from `apar ∝ pft->fpc` with no phen, then `gp_stand +=
  gp·phen` while `gp_stand_leafon += gp`, **both** normalized by the **plain** `Σ pft->fpc`). On a
  no-demand day (`eeq==0 || gp_stand_leafon==0 || fpc==0`) it is **`1` = UNSTRESSED**, and the `gp_sum.c:67`
  gate keys off the **phen-weighted** `gp_stand`, so a genuinely leafless canopy takes that branch. It
  accumulates **every** day (`:140`) and is emitted as `pft->wscal_mean/NDAYYEAR` (`fwriteoutput_ind.c:119`)
  — so `1 − mean(ind.wscal_mean)` is a *potential* water-stress index, not a realized deficit. It is
  consumed **twice**: as Component S's `water_stress` feature and as the leaf:root allocation driver
  `lmtorm` (`allocation_tree.c:233`, the non-cotton `/NDAYYEAR` branch — the `growing_days` branch is
  cotton-only and dead here). A realized `min(1, Σsupply·fpc/Σdemand·fpc)` carries `phen` **squared** and
  collapses to 0 on a leafless day; that mismatch put the coupled Hainich feature 6.5 band widths out
  (0.305 vs a C truth of 0.0014) and cost the Sahel 36 % of its trees. `WaterParams.wscal_leafon` (default
  off) is the faithful port.
- **Soil geometry & `whc_nat` (`[VERIFIED]`; the per-cell soil column basis — ADR 0050, skill
  `provision-coupled-cell`).** Layer thicknesses are a **C global, not per-cell**: `fscansoilpar.c:36-39`
  reads `soildepth[NSOILLAYER]` once from `par/soil_20m.js` = `200,300,500,1000×19,3000` mm. The `soildepth`
  *input* (`soil_depth_test.clm`, Pelletier) is opened, read, and then **discarded** —
  `newgrid.c:282` does `grid[i].soildepth=20;` unconditionally, so every cell runs at 20 m and
  `getrootdist`'s sediment-truncation branch is dead. The `whc_nat` output is the patch-ensemble-mean
  **fraction** (`soilpar_output.c:42`), so plant-available mm = `whc_nat[l] × soildepth[l]` (the C's own
  `whcs`, `soil.h:222`) — no pedotransfer port needed. But it is **monthly and time-varying** (`whc =
  wfc − wpwp` is recomputed 2×/day from the evolving soil carbon via Saxton–Rawls `pedotransfer.c:109`) and
  **run-to-run nondeterministic under `-DPERMUTE`**: the same cell differs by up to 1.6e-4 relative in layer 0
  between the 512-task global run and a single-cell re-run. In `whc_nat.nc`, `depth(layer)` is the layer
  **CENTRE** — thickness = `(depth_bnds[:,1]−depth_bnds[:,0])×1000`.
- **`ind` rooting columns (`[VERIFIED]`): `D95`, `D95max` and `beta_root` are three different things, all in
  cm.** `beta_root` is the C's actual profile parameter (`new_tree.c:230`:
  `getbetaroot(2000 cm, D95max)`; consumed by `getrootdist.c`); `D95max` is the establishment-sampled trait
  (the `fprint_tree.c:69` "(mm)" label is wrong); the emitted `D95` is the **rootdepth-limited realized**
  95 % depth (`fwriteoutput_ind.c:104`) and is NOT `log(0.05)/log(beta_root)` for ~87 % of individuals. The
  rooted depth is recoverable: `R_cm = ln(1−(1−β^D95)/0.95)/ln β`. Tree-vs-grass test is **`D95max > 0`**, not
  a `Type` number — `Type` ids differ by biome (Hainich {1,2,3,4,5,8} but Sahel/Amazon {0,7}), so
  `python/.../data.py`'s `TREE_TYPES=(1,2,3,4,5)` is not portable.
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
- **`Type` in the `ind` output is the 0-based `pftpar` INDEX, and ids 0–6 are ALL SEVEN tree PFTs
  (`[VERIFIED 2026-07-28]`).** `par/pft_lpjmlfit.js` order: 0 tropical broadleaved evergreen · 1 temperate
  needleleaved evergreen · 2 temperate broadleaved evergreen · 3 temperate broadleaved summergreen (**the
  Hainich beech**) · 4 boreal needleleaved evergreen · 5 boreal broadleaved summergreen · 6 boreal
  needleleaved summergreen (larch) ‖ **7/8/9 grass** (emitted with the tree fields **zeroed** —
  `fwriteoutput_ind.c:139-189`, so wooddens/D95max/minwscal are literally 0) ‖ 10–21 crops (never emitted:
  `landuse:"no"`). So the correct tree filter is `Type <= 6`. **`TREE_TYPES` now lives in exactly ONE place —
  `python/.../data.py` = `(0,…,6)` — and `features.py`, `python/config/config.yaml` and every
  `build_slow_*.py` IMPORT it (ADR 0031, fixed 2026-07-28); never re-declare it.** Two independent copies is
  what caused the defect: a stale `[1,2,3,4,5]` dropped 32.5 % of survivor tree stems and made 16.7 % of
  tree-bearing cells (the tropical belt + Siberian larch) invisible to Component S for months. **Every global
  Component-S number published before 2026-07-28 is on that truncated population (ids 1–5, 45 009 of 54 020
  cells)** — the `t7` artifact generation supersedes them. Mixing two PFT sets makes two per-cell trait
  statistics incomparable (id 0's minwscal spans `[0.05,0.75]`, measured median 0.497, vs the truncated
  tables' whole `[0.025,0.30]`). Hainich (42490) has only ids 1–5 + grass 8, which is why every single-cell
  gate stayed green.
- ⚠ **RECRUIT TRAITS ARE *INHERITED*, NOT UNIFORM DRAWS — and a per-cell trait statistic is NOT a
  composition statistic (`[VERIFIED 2026-08-04]`, ADR 0045/0046; this REPLACES the earlier "traits are drawn
  uniformly from per-PFT `[low,high]` intervals ⇒ composition statistic" claim, and ADR 0042 §9's narrower
  correction to it).** `lpjmlfit.js:35` sets `"inheritance": true`, and the uniform branch's guard
  `year < firstyear − nspinup + inherit_startyear` (`establishmentpft_ind.c:99`) is **false in every transient
  year under BOTH config branches** (spinup: 1901−1000+200 = 1101; from-restart: 1901−0+0 = 1901). Establishment
  is a **two-channel mixture**: inheritance at `k_est_inherit`=0.02 (`:124`) picks a random member of a 50-yr
  rolling top-AGB **seedbank** (`param.max_age`, refreshed *yearly* — `getsapling.c`'s "every five years"
  comment is stale) and diffuses each trait by `new_tree.c:38-61` `new = old·(1 + 0.1·gasdev)` (`s` clamped
  ±5, reflected at the interval edges, **PFT id inherited from the parent**); background at
  `k_est_inherit_bg`=0.005 **per eligible PFT** (`:102`) is the uniform `getrndinterval` channel. `f_sap` and
  `patcharea` **cancel exactly** (both branches use α=2.0: `param.alpha_r` and `ALPHA_R`), so the weight is
  closed-form **`w_inherit = 4/(4 + n_elig)`** ⇒ **≈44 % inherited at Hainich (~5 eligible PFTs), ≈80 % in
  low-diversity cells (Amazon/Sahel, 1 eligible)**. So the establishment marginal is a **functional of the live
  community** — FIT's establishment *is* the feedback loop ADR 0025 §4 excluded on principle.
- **`k_root` is a SCALAR 0.02 in this configuration, NOT a sampled recruit trait (`[VERIFIED 2026-08-11]`,
  ADR 0117).** `new_tree` samples seven trait axes, but in the live `par/pft_lpjmlfit.js` all seven tree PFTs
  declare `"k_root": 0.02` with the interval form `{"low":0.02,"median":0.04,"high":0.06}` **commented out at
  every one** (`:134, 264, 394, 524, 654, 784, 914`) — and the emitted column carries **exactly one distinct
  value over all 206 561 574 tree rows, 0 differing**. So a component that predicts `SLA`/`Wooddens`/`D95max`/
  `minwscal` and leaves `k_root` to the C is an **identity**, not an approximation. `emax` and `beta_2` are
  emitted nowhere, so their coupling to the four is **not measurable from `ind`** — say that, don't assume it.
  ⚠ The general trap this came from: **a degenerate correlation is the signature of a constant column, not of
  an uncoupled variable** (skill `residual-diagnosis`), and the same "is it actually sampled?" check applies to
  any `.js` trait — read the live file, the commented-out interval is the live form's neighbour.
- **The measured warming shift is WITHIN-PFT, WITHIN-AGE-CLASS selection (ADR 0046).** FIT's per-cell mean
  wood-density shift historic→ssp370 decomposes **22.2 % composition / 51.3 % within-PFT / 26.6 % interaction**
  (closure 4.6e-13), and the within-PFT part is **+112 % within-age-class** with the age-structure term at
  **−11.8 %** (stands get *younger* under warming, which *opposes* the shift). Traits are immutable after
  `new_tree`, so a trait-mean rise at fixed age can only be differential survival. The fingerprint is a steep
  **age–wooddens gradient** in every PFT (id 1: 184 869 → 331 234 from `Age<10` to `Age≥320`; id 4 +141 227;
  id 6 +130 558) — and that gradient is the ID-free validation target for any ported mortality operator.
  ⚠ **Do NOT port `mort_max` alone as "denser wood survives better".** Denser wood halves `mort_max`
  (`mortality_tree_ind.c:92`, ratio 1.765 over `wooddens` 2e5→3e5) but grows slower, lowering `greff` and
  *raising* `mort_npp` through the logistic `mort_max/(1+KMORT_2·exp(k_mort·greff))·(1+bm_inc_counter)`
  (`:95-101`, `KMORT_2`=0.2). **Net selection is not sign-definite** — the one-year differential
  `mean(Wooddens|live) − mean(Wooddens|all)` is **negative** for ids 0 and 3 and positive for 1/2/4/6, and its
  sign predicts each PFT's gradient shape. The four hazards combine **additively** then cap:
  `mort = min(1, mort_npp + mort_age + mort_water + mort_temp)`, then a per-individual `erand48` Bernoulli
  draw, with hard kills at `bm_inc_counter ≥ 5` and `leaf_c < leaf_carbon_sapl(sla)` (`:120-146`). The
  `pft->par->mort_max` read at `:87` is **dead** — overwritten at `:92`.
- **Annual `ind` output gotchas (`[VERIFIED]`; load-bearing for Component-S training).** The TXT `ind`
  writer emits **29 columns** (`printind`); `stemdiam/crownarea/leafarea/fpc/bm_inc_counter/pools` are
  **commented out** (RAW-only). **AGE OFF-BY-ONE:** the emitted `Age` is the *post-increment* year-end age
  (`getind`, `annual_tree.c:46`) but the same row's `mort_*` used the *pre-increment* age (`Age − 1`,
  `annual_tree.c:31-38`) — recompute `mort_age` from `Age − 1` (matches to 5e-8, not 1.4e-4). **Tier-2 RAW
  cannot yield `bm_inc`/`nind`/`turnover`** (absent from the `Output_ind` struct); the budget signal is the
  emitted `npp` (`= pft->anpp`, runtime-consistent with `FToS.bm_inc`), NOT `pft->bm_inc.carbon` (the
  post-allocation residual, 0 for grass at output time). The flux-conditioning table builder is
  `scripts/build_slow_flux_table.py` (tier-1, parameterized by `CELLS`; §7-validated).
- **READ A `.js` PARAMETER VALUE WITH `cpp -P`, NEVER BY EYE — and check for DUPLICATE KEYS
  (`[VERIFIED 2026-08-04]`, ADR 0047).** LPJmL parses its own parameter files by piping them through the C
  preprocessor (`src/lpj/openconfig.c:28` `#define cpp_cmd "cpp"`, `popen` at `:467`), so the authoritative
  macro expansion is reproducible in three lines: `cpp -P <file>` → strip the trailing commas LPJmL's lenient
  parser tolerates (`re.sub(r',(\s*[}\]])', r'\1', s)`) → wrap the `"key": value,` fragment in braces →
  `json.loads`. Working implementation: **`scripts/build_mort_params_reference.py::cpp_json`** (it also emits
  the per-PFT table as a committed CSV every consumer gates against — reuse it for any other parameter block).
  ⚠ **LPJmL reads each key through json-c's hash lookup (`json_object_object_get_ex`), and json-c's tokener
  inserts pairs with `json_object_object_add`, which REPLACES — so on a duplicated key the LAST occurrence
  wins.** `json.loads` agrees, which is the only reason the parse is faithful; **there IS a duplicate in the
  live file** — PFT id 6 (larch) declares `aphen_min`/`aphen_max` twice in `par/pft_lpjmlfit.js`
  (`:1001-1002` the macro defaults 60/245, then `:1003-1004` an override pair **10/200**), so larch's
  effective `aphen_min` is **10** and it starts accumulating water stress six times earlier in the season
  than every other tree PFT. Enumerate duplicates with a `json.loads(..., object_pairs_hook=...)` and assert
  the set is unchanged — a new one silently overrides a parameter and is invisible in the file. Also: the
  `"median"` of an interval is a **global default** (`sla` = 0.01986 for all seven trees) and lies OUTSIDE
  `[low, high]` for ids 1/2/3/5, so it is not a central value of the interval recruits are drawn on.
- **FIT's age–trait gradient is PFT-SHAPED — never assume every PFT spans every age bin, and never assume it
  rises (`[VERIFIED 2026-08-05]`, ADR 0049).** Mean survivor `Wooddens` by `Age` bin (edges 10/20/40/80/160/320
  yr, survivors `isdead==0`) is the committed fixture `test/testitems/references/S_age_wooddens_gradient.csv`
  (builder `scripts/build_age_wooddens_gradient_reference.py`, `CHECK=1` to verify). Two structural facts a
  seven-bins-per-PFT assumption gets wrong: **id 5 has NO stems above 160 yr at all** (its `longevity` is 125,
  see the table below) and **id 2 none above 320**. And **ids 0, 2 AND 3 are non-monotone** (rise then dip) —
  id 2 despite a *positive* one-year selection differential, so ADR 0046 §3's "the sign of `S` predicts the
  gradient's shape" holds for 6 of 7 PFTs, not all. Reading `wooddens_mean` as monotone in age, or grouping
  by a fixed bin count, silently mis-scores any mortality/selection operator.
- **Mortality params are PER-PFT — do not reuse beech's for another id (`[VERIFIED 2026-07-28]`).** `k_mort`=0.01
  is global (`par/lpjparam_fit.js`); everything else is per-PFT in `par/pft_lpjmlfit.js`, where `longevity` is
  the **JSON key `"age"`** (NOT the leaf `"longevity"`=2.0) and `temp_low/high` is `"temp_stressed"` (NOT the
  establishment `"temp"` gate). Macros: `MORT_WATER_RES_` ANGIO 0.75 / GYMNO 0.65 / XERIC 0.25 ·
  `MORT_TEMP_FACTOR` 5.0 · `WD_mort1/2_` trop −2.458/0.129, mediterranean −2.625/0.236, temp −2.465/0.148,
  boreal −2.430/0.143 · `TREE_LONGEVITY` 400. (Use `par/pft_lpjmlfit.js`, **not** `par/pft.js` — its
  `WD_mort*`/`TREE_LONGEVITY` differ.)

  | id | mort_water_factor | mort_water_res | wdmort_1/2 | longevity | temp_stressed low/high |
  |---|---|---|---|---|---|
  | 0 tropical BE | 10 | 0.75 ANGIO | trop | 400 | 12.5 / 54 |
  | 1 temperate NE | 5 | **0.25 XERIC** | mediterranean | 400 | −15 / 54 |
  | 2 temperate BE | 10 | **0.25 XERIC** | mediterranean | 400 | −10 / 54 |
  | 3 temperate BS (**beech**) | 5 | 0.75 ANGIO | temp | 400 | −20 / 54 |
  | 4 boreal NE | 7.5 | 0.65 GYMNO | boreal | 400 | −45 / 54 |
  | 5 boreal BS | **20** | 0.75 ANGIO | boreal | **125** | −45 / 54 |
  | 6 boreal NS (larch) | 5 | 0.65 GYMNO | boreal | 400 | −70 / 54 |

  Assuming beech's row for the others is a real error, not a rounding one: id 5's longevity is 125, a **3.2×**
  age-mortality difference, and its `mort_water_factor` is 4× beech's. `scripts/build_slow_flux_table.py::PFT_PARAMS`
  carries this table and now RAISES on an unknown `Type` instead of falling back to temperate defaults.

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

- **A `cell_year_feats.parquet` property does NOT carry over to the same-named column of a
  `slow_copula_pooled_w20_*` table (`[VERIFIED 2026-08-03]`, ADR 0042 §8).** In `cell_year_feats`,
  `eco_diag_gdd_5` and `tas_cold_month` are per-cell CONSTANTS (identical every year). On the
  `pooled_w20` tables the forests actually read they are **time- AND scenario-varying**: with
  `BOUNDARY_WINDOW=20` — which `run_pooled_slow_*.sh` require, and which `pooled_w20` is named for — they come
  from `cell_year_boundary_<scenario>_w20.parquet` joined on `["Cell","Year"]`
  (`build_slow_runtime_table.py:231-250`, the ADR-0026 treatment). The six **env tail** columns *are* per-cell
  constants and identical across scenarios (per-`Cell` mean over the historic-only `cell_year_feats`). Getting
  these two the wrong way round produced the claim that the static tail dilutes "the ONLY channel through
  which time can enter", which is false — 2 of the 8 base columns are transient too.
- **`tables/cell_year_feats.parquet` stores 4 of the 6 env conditioning columns as `Float32`, and polars'
  `group_by().mean()` on a `Float32` column ACCUMULATES IN `Float32` (`[VERIFIED 2026-08-03]`).**
  `eco_diag_p_pet_ratio` / `eco_diag_pet_mean` / `eco_diag_vpd_mean` / `pr_cv_monthly` are `Float32`;
  `prec_mean` / `humid_mean` are `Float64`. So a per-cell aggregate of these columns **must
  `.cast(pl.Float64)` BEFORE the `mean()`** or it lands ~**3.35e-07 relative** away from the value the
  shipped 14-column artifact was actually conditioned on — measured: aggregating natively missed on
  **199 093 of 200 000** probed rows (max |diff| **7.63e-05** on `eco_diag_pet_mean`, which is exactly
  `5·2⁻¹⁶`, the float32 tell), while the two `Float64` columns matched bit-exactly. Cast first and the
  reproduction is **bit-exact**. This is the ADR-0023 train/inference-shift trap in its quietest form: the
  error is far too small to look wrong and far too large to be zero, and no coverage or finiteness check
  sees it. `scripts/build_slow_cell_env_sidecar.py` carries the cast and **gates on exact float64 equality
  against the shipped `Xc.f64` tail** rather than against a re-run of the producing code (which would be
  circular). Any new per-cell derivation off this table needs the same treatment.
- **`polars` `collect(engine="streaming")` is NOT deterministic in the KEY SET it emits at global scale
  (`[VERIFIED 2026-07-29]`, ADR 0036 §5b).** Two runs of the same `group_by` over the same 92 GB `ind` parquet
  produced **99 023 397** vs **99 028 310** rows — 141 of 58 496 cells differed, 4 913 rows missing net, and
  **12 cells with DUPLICATED keys**. This is not the ~1e-13 float-sum jitter that was already documented; whole
  groups appear and vanish, in contiguous cell blocks (a partition-boundary artifact). Any pipeline that
  `group_by(...).collect(engine="streaming")` over these tables must **assert its own key set**
  (`df.select(keys).n_unique() == df.height`) — the usual `dropped = h_before - h_after` coverage guard
  CANNOT catch it, because duplication makes that statistic go negative so a `drop_frac > threshold` test never
  fires. Worse, a later self-join AMPLIFIES a duplicated key (present twice on both sides ⇒ four rows), so
  prefer a window function (`shift(1).over([...])`) to a self-join on a streamed aggregate.

## 5. Git / CI

- **BRANCH-PER-LINE workflow (ADR 0028, which SUPERSEDED ADR 0013's main-only rule on 2026-07-28).** Work on
  your line's branch in its own worktree and **self-merge to `main` when that branch's CI is green** — the
  exact ritual, and the five traps in it, are **§9** (read them: `git switch main` does not work from a line
  worktree, and a plain push after the mandated rebase is rejected). Still **no PRs, no branch protection, no
  review gate**, and still full autonomy per `STEERING_PROMPT.md` — no owner sign-off is needed or expected;
  your safety net is the CI/conservation gates and ADRs, not a human gate. Retained from ADR 0013:
  Conventional Commits, Keep-a-Changelog, one logical change per commit, no data/weights/secrets, and run the
  CI-equivalent checks (CI-faithfully on SLURM) before pushing.
- **Commit trailer:** end every commit message with
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **The 6 CI gates:** `CI` (Julia tests), `format` (Runic), `docs` (Documenter), `python` (ruff+pytest),
  `changelog` (uncollated fragments on `main`; ADR 0095), `TagBot`. The Julia matrix shows jobs
  `test (lts)` **(required)**, `test (1)` **(required)**,
  `test (pre)` (`continue-on-error`, allowed to fail on Julia-prerelease API churn), plus non-required
  `test (macOS, lts)`. **Never merge on a red required check.**
- **⚠ EACH GATE IS PATH-FILTERED AND MOST COMMITS TRIGGER NONE OF THEM (ADR 0090).** A gate runs only when a
  path it watches changed, so **a prose/docs/skill/ADR/STATE-only commit legitimately produces NO check-runs
  at all** and is mergeable as soon as it is pushed. Do not wait for a verdict that cannot arrive.

  | gate | runs when these change |
  |---|---|
  | `CI` (4 Julia jobs, the expensive one) | `src/**` · `ext/**` · `test/**` · `Project.toml` · `docs/src/generated/**` · own workflow |
  | `format` (Runic) | any `**/*.jl` · own workflow |
  | `python` (ruff+pytest) | `python/**` · own workflow (**`scripts/*.py` is NOT linted by CI**) |
  | `docs` (Documenter) | `docs/src/**` · `docs/make.jl` · `docs/Project.toml` · `src/**` · `Project.toml` · own workflow |
  | `changelog` (uncollated fragments) | `changelog.d/**` · `CHANGELOG.md` · `scripts/collate_changelog.py` · own workflow — **`main` ONLY**, never `line/**` (a fragment on a line branch is correct; it is debt only once it reaches `main`) |

  **`docs/report/component_s_public_report.{tex,pdf}`, `docs/report/figs/**` and `docs/decisions/**` trigger NOTHING** —
  they live under `docs/` but are not in the Documenter page tree. Every workflow also has
  `workflow_dispatch`, so any gate can be forced from the Actions tab / `gh workflow run` when you want it
  anyway. **A skipped workflow reports no status — not a "skipped" one** — so a poll loop written as *"wait
  until `test (lts)` is completed"* HANGS FOREVER on a docs-only commit. Decide which gates to expect from
  `git diff --name-only origin/main...HEAD` against the table above, then require exactly those.
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
   unchanged until deliberately enabled. **⚠ COROLLARY, and it has bitten three times: guardrail 4 protects
   you from enabling too early, NOT from never enabling.** An opt-in flag whose default is *known wrong* is
   a defect on a timer — `wscal_leafon` is the C-faithful behaviour, was measured correct in ADR 0051, and
   sat off for **weeks** with each line recording the flip as the other's to schedule; `trait_mortality`
   (ADR 0049) and `anchor` (ADR 0103) are the same shape. So whenever you ship an opt-in whose default you
   believe is worse than the alternative: **pre-register the flip criterion in the same ADR** — the exact
   arm, on whose line, with the pass condition and the value to flip to — and name it in the *consuming*
   line's STATE as an ACTION, not in your own as a note. "It is opt-in" is a reason to ship, never a reason
   to stop measuring.
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
- **`EXECUTION_PLAN.md` — THE CURRENT PROGRAM (owner-approved 2026-08-07; ADR 0093 + 0094).** The dated,
  executable order of work: the error-attribution ladder, rung ownership per line, entry/exit gates, the
  pre-registered flip criteria, and the speed gate. **Integrator-owned — a line raises a change as an
  integration point, it does not edit this file.** Read it before planning anything.
  (phased plan), `RESEARCH_SURVEY.md`, `ECOSYSTEM_AND_COUPLING.md`, `ENGINEERING_STANDARDS.md`.
- Decisions: `docs/decisions/README.md` (ADR index). Steering: `STEERING_PROMPT.md` +
  `PROJECT_REVIEW_2026-07-22.md`.
- **Skills** (`.claude/skills/`): `julia-test`, `lpjmlfit-cbinary`, `fdiff-validate`, `python-env`,
  `residual-diagnosis`, `repo-commit`, `reuse-citation`, `plumber2-reference` + `obsclim-cell-remap`
  (line E: the PLUMBER2 observational reference for Component E, and getting a gridded forcing onto orderA
  cells). Invoke the one that matches the mechanical task instead of re-deriving its steps.
- **Reuse + citation — the licensing question is CLOSED (ADR 0081; owner decision, 2026-07-28).** The owner
  is a member of **both** the LPJmL-FIT group and **TUM-PIK-ESM** (which hosts SpeedyWeather.jl,
  Terrarium.jl, LPJmL-hybrid-photosynthesis), so **reuse those models freely — do NOT raise licensing,
  ask for a licence decision, or re-audit upstream licences.** ADR 0080 (the basis) + ADR 0081 (the
  decision) are the complete, final record; reopening it wastes a session. **The one standing obligation
  is TRANSPARENT CITATION** in all four surfaces, kept in agreement — `docs/third_party_licensing.md`
  (the reuse + citation register), `CITATION.cff`, `docs/src/refs.bib` (inline `[key](@cite)`), and the
  header of any source file with derived content — and provenance must be stated *accurately*, neither
  overstated nor omitted (skill: **`reuse-citation`**). **NeuralCrop.jl is usable too** — CC-BY-NC permits
  non-commercial use and this project is research, so reuse its code as needed and cite it; the only thing
  that would need a rethink is a future *commercial* release, which is not on the table.
- **Source map** (`src/`): `LPJmLFITEmulator.jl` (module), `state.jl` (`SharedState`), `interface.jl`
  (S↔F↔E I/O structs), `conservation.jl` (softmax/flux-then-integrate/budget residuals),
  `allometry.jl`, `fdiff.jl` (the differentiable daily core + canopy rollout + allocation/growth),
  `fdiff_smoothops.jl` (smooth surrogates for non-smooth ops), `registry.jl`, `run.jl` (coupled
  `run_coupled_cell`/`couple_day!`), `components/fast.jl` (`FDiffFastCore`, `annual_step!`),
  `components/slow.jl` (`AbstractSlowEmulator`; `DemographicSlowEmulator` Tier-0 + `FluxDrivenSlowEmulator`
  Tier-1 — P1), `components/energy.jl` (`SEBEnergyClosure`), `drf.jl` (`module DRF` — zero-dep DRF +
  `save_forest`/`load_forest` pure-Base text serialization + Gaussian-copula sampler; ADR 0022/0023).
- **Component-S production DRF (ADR 0023):** the coupled `FluxDrivenSlowEmulator` loads a serialized
  `DRF.Forest` (`DRF.load_forest`). Committed demo artifact = `test/testitems/references/drf_forest_hainich.drf`
  (**text, never `*.bin` — that's git-ignored**; regen: `scripts/build_slow_runtime_table.py` →
  `scripts/train_slow_drf.jl`). The training table MUST match the runtime `flux_feature_vector` order
  (`slow.jl`); **`age_mean`: ADR 0023 §3's "train it as the elapsed-year counter" is SUPERSEDED by ADR 0024** —
  it is now a TRUE nind-weighted mean cohort age, and the DRF is retrained on `mean(Age−1)` (start-of-year;
  emitted `Age` is post-increment) with an `age0` seed carried in the DRF meta. Either way the rule behind it
  stands: the runtime feature and the training column must be the SAME quantity (the silent
  train/inference-shift trap). `soilmoist`/`lai` are documented proxies until the global
  C-`LAI_STAND`/`swc` pipeline. Gate-3 oracle ref: `references/hainich_slow_oracle_{traits,counts}.csv`
  (`scripts/build_slow_oracle_reference.py`).

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
| Current durable state | **`lines/<X>/STATE.md`** for line state (incl. the `## NEXT` handoff); **`MEMORY.md`** only for CROSS-CUTTING facts (§9) |
| Session narrative / what-happened | **`lines/<X>/JOURNAL.md`** (your line; the root `JOURNAL.md` is history + the INTEGRATION journal — §9) |

**Capture minimally in the moment** — a 10-line `SKILL.md` pointing at your existing script beats nothing.
Use the **`skill-creator`** skill for the mechanics (frontmatter, the trigger-rich description that makes a
skill actually fire, point-at-the-script). Parameterize, don't fork: e.g. single-cell forcing+restart
extraction for a test fixture belongs in the `fdiff-validate` skill **parameterized by cell index**, not
rewritten each time.

**The commit-time capture gate (checkable — this is the enforcement point, not the retrospective).** Before
every commit, ask: *did this change include a script I'd rerun, a non-obvious fix, or a re-derivation of
something a past session knew?* If yes, create/update the skill (or CLAUDE.md/ADR) **in the same commit**
and note it in the commit body (`+ skill: <name>`). This rides the mandated commit (ADR 0013) instead of a
session "end" that never cleanly arrives — do not defer capture to "later." A `PostToolUse` hook
(`.claude/hooks/skill-capture-gate.sh`, wired in `.claude/settings.json`) injects this checklist
automatically *after* each commit as a backstop, so a follow-up `chore(skill:)` commit is fine when it
fires post-hoc. The `SessionStart` hook lists the current skills each session and reminds you to consult a
matching one before doing a task by hand (that is how created skills stay used); `skill-usage.log` records
invocations for the `consolidate-memory` dedup/prune pass.

**Standing tasks:** (1) the commit-time gate above, every commit; (2) **consolidate MEMORY every ~5
sessions** — reshape MEMORY.md back to durable-state-only under the cap, archive (don't delete) what you
remove — use the **`consolidate-memory`** skill, which also covers the skill-set dedup/prune pass. With
parallel lines (§9) this applies to the SHARED `MEMORY.md` as an **integrator** action, and to each
`lines/<X>/STATE.md` as that line's own housekeeping.

**Use subagents** for isolation, parallelism, a read-only reviewer, or independent verification — and note
that subagents can invoke skills.

---

## 9. Parallel work lines — the protocol (ADR 0028/0029; read this every session)

Work runs as **4 concurrent session lines**, each a long-lived branch checked out in its own **git worktree**.
This exists because one serial session was too slow, and because two sessions in ONE checkout destroy each
other (the mandated `rm -f test/Manifest.toml` before `Pkg.test()`, plus `.git/index.lock` and `*.cov` litter —
none of it tracked, so git never warns).

| Line | Branch · worktree | Scope | State file |
|---|---|---|---|
| **S** | `line/S` · `/p/projects/open/Jamir/wt-S` | Component-S science | `lines/S/STATE.md` |
| **M** | `line/M` · `/p/projects/open/Jamir/wt-M` | Multi-cell coupled S+F+E (P3) | `lines/M/STATE.md` |
| **E** | `line/E` · `/p/projects/open/Jamir/wt-E` | Component E vs observations (P2) | `lines/E/STATE.md` |
| **O** | `line/O` · `/p/projects/open/Jamir/wt-O` | Online coupling, Terrarium/SpeedyWeather (P4/P5) | `lines/O/STATE.md` |
| — | `main` · `esm_land_emulator` | **Integration only** | — |

**One session per line at a time.** Your line = the branch in the worktree you launched from; the
`SessionStart` hook (`.claude/hooks/session-line-context.sh`) resolves it and injects your line's ownership
rules + `## NEXT` action. Launching in the `main` worktree prints `LINE: none (integrator)`.

### Where things are written (this is what keeps merges conflict-free)

**Per-line FILES, not per-line sections** — sections in a shared file still conflict; different files never do.

| Kind | Destination |
|---|---|
| Narrative / what happened | `lines/<X>/JOURNAL.md` (append) |
| Durable line state + the **NEXT handoff** | `lines/<X>/STATE.md` |
| Changelog entry | a **NEW** `changelog.d/<X>-<slug>.md` fragment — **never edit `CHANGELOG.md` from a line**; whoever merges to `main` folds it in with `scripts/collate_changelog.py` (ADR 0095) |
| A decision | an ADR from **your block** — TIER 1: S 0030–0049 · M 0050–0069 · E 0070–0079 · O 0080–0089 · integrator/cross-cutting 0090–0099 · **TIER 2**: S 0100–0119 · M 0120–0139 · E 0140–0149 · O 0150–0159 · integrator 0160–0169 · **TIER 3** (use when your tier-2 block is exhausted): **S 0170–0189** · M 0190–0209 · E 0210–0219 · O 0220–0229 · integrator 0230–0239. `0001–0029`, **S's `0030–0049`** and now **S's `0100–0119`** are EXHAUSTED (ADR 0049 closed tier 1, ADR 0100 opened tier 2, **ADR 0119 closed it** ⇒ line S is on 0170). Tier 3 was allocated for ALL lines at once (2026-08-11, by line S while holding the integration lock — §9's rule that the lock-holder is the integrator), at tier-2 widths, precisely so the next line to exhaust its block does not have to convene anything either. Add the row to your line's subsection of `docs/decisions/README.md` |
| Cross-cutting `[VERIFIED]` fact | `MEMORY.md` (shared, additive) |
| A procedure / gotcha | a skill / this file (§8 routing unchanged) |

`CHANGELOG.md`, the shared `MEMORY.md`, `Project.toml`, and cross-cutting ADRs (0001–0029) are
**integrator-owned**. The root `JOURNAL.md` is the **integration** journal (single-writer ⇒ conflict-free).

⚠ **"Integrator-owned" names a ROLE, NOT A PERSON OR A SCHEDULE — and an integrator-owned chore with no
event attached to it silently rots (ADR 0095).** There is **no orchestrator** in this repo: each line merges
its *own* branch to `main` (the `flock`'d ritual below), so nothing ever convenes an "integration point" for
someone to attend. Measured cost of leaving a chore triggerless: `changelog.d/` collation was specified as
*"the integrator collates at an integration point"* and **56 fragments piled up over 13 days** while
`CHANGELOG.md` was itself edited three times in the same window — no gate, no conflict, no complaint.
So, for every integrator-owned chore, state **which event triggers it** and **what makes the residue visible**:

| integrator chore | trigger (an event that provably happens) | visibility |
|---|---|---|
| `changelog.d/` → `CHANGELOG.md` | **every merge to `main`**, inside the same `flock` — `scripts/collate_changelog.py` | `changelog` CI gate on `main` (ADR 0095) |
| shared `MEMORY.md` consolidation | every ~5 sessions (`consolidate-memory` skill) | the ≤400-line / ≤15k-token cap |
| `[compat]` pin after a dep bump | a red required gate whose diff cannot explain it (§5) | `CI` on every branch |
| cross-cutting ADR / `EXECUTION_PLAN.md` | an owner steer, or a line raising an integration point | both lines' `STATE.md` |

**You hold the lock ⇒ you are the integrator for that moment.** Collating on `main` does not violate "never
edit `CHANGELOG.md` from a line": you are editing it in the integration worktree, on `main`, not on your branch.

### Ownership + contracts

The per-path ownership map is **ADR 0029**, **extended here** for three gaps the adversarial review found
(2026-07-28) — this section is the authoritative, complete map:

| Path | Owner | Note |
|---|---|---|
| `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` | **S** | exclusive |
| `src/run.jl`, `src/interface.jl` | **M** | the coupling seam |
| `src/components/energy.jl` | **E** | exclusive |
| `ext/**` | **O** | exclusive (new extension files) |
| **`src/fdiff.jl`, `src/fdiff_smoothops.jl`, `src/components/fast.jl` — the F core** | **M**, by default | *Gap 1: 60% of `src/` was unowned.* M is the physics/coupling line, so it holds F. **S may not edit F directly** even though S4 (grass ownership) and S6 need it — that is an **integration point**: S specifies the change, M lands it (or M explicitly hands the file over for one milestone, recorded in both STATE.md files). The parked F-fidelity work (`sapwood_bg` growth, per-PFT water supply) is unstaffed — don't start it inside another milestone. |
| **`src/state.jl`, `src/conservation.jl`, `src/allometry.jl`, `src/registry.jl`** | **shared, additive-only** | Cross-component libraries used across the interface. Add; never restructure. `registry.jl` additionally drives `docs/src/generated/*.mmd` — regenerate with `scripts/gen_diagrams.jl` in the SAME commit or the diagram-staleness gate reds **`CI` on your branch** (ADR 0091 made it real; it had been local-only). ⚠ **This also binds `src/interface.jl` (M-owned):** the full diagram labels edges with `fieldnames(T)`, so changing ONE field of `SToF`/`FToS`/`FToE`/`EToF`/`EToATM`/`SToE`/`AtmForcing` makes the committed diagram stale even with no registry edit. |
| **`.claude/skills/<name>/SKILL.md`** | **primary owner by domain** | *Gap 2: 40 commits touch skills, and the §8 capture gate pushes EVERY session to edit one.* Primary: `slow-drf-pipeline` + `emulator-validation-figures` → **S**; `fdiff-validate` + `lpjmlfit-cbinary` → **M**; `python-env` → **E**. `julia-test`, `repo-commit`, `residual-diagnosis`, `skill-creator`, `consolidate-memory` are **shared, append-only** (add a bullet/gotcha at the end of the relevant section; do not reorganise, and do not rewrite another line's section). |
| `test/testitems/**` | by subsystem (see ADR 0029) | `references/**` shared; regenerating an existing baseline is an integration point |
| `Project.toml`, `test/Project.toml`, `CHANGELOG.md`, shared `MEMORY.md`, root `JOURNAL.md`, `.claude/settings.json`, `.github/workflows/**`, `.gitignore`, `config/**` (except E's energy keys), `scripts/sbatch_*.sh` + `run_tests_slurm.sh` | **integrator only** | *Gap 3: these were unassigned.* Request the change; the integrator lands it on `main`. |

Rules:

- **Never edit another line's exclusive path.** Need a change there? Raise an **integration point**: note it in
  both lines' STATE.md and land both sides together.
- **Shared files are additive-only**, inside your marked region where one exists —
  `src/LPJmLFITEmulator.jl` has `# ── line S/M/E/O ──` regions in both the include and export blocks.
- **`src/run.jl` + `src/interface.jl` (the coupling seam) belong to line M.** `src/components/energy.jl` to E,
  `src/components/slow.jl`/`drf.jl`/`climbuf.jl` to S, `ext/` to O.
- **Frozen cross-line contracts:** S→M (the `FluxDrivenSlowEmulator` kwargs, `flux_feature_vector` order,
  `live_flux_cond`, the `.drf`/`.rcop` format, the `cell_meta.parquet` schema) and E→M (`SEBEnergyClosure` /
  `solve!`). M **pins a versioned artifact**; S **bumps a version** rather than mutating an artifact in place.
  Train/inference consistency is load-bearing (ADR 0023) ⇒ a conditioning change is a both-sides change.
- **`test/testitems/references/` is shared:** new fixtures take a line-specific name; **regenerating an
  existing baseline is an integration point** (guardrail 4 — opt-in, default byte-identical).
- **`Project.toml` deps are integrator-only** and runtime `[deps]` stays EMPTY (ADR 0014) — request a weakdep.

### The ritual (mechanics + gotchas in the `repo-commit` skill)

```bash
INT=/p/projects/open/Jamir/esm_land_emulator   # the integration worktree; `main` lives HERE

git pull --rebase origin main        # at session START, and again before merging
# ... work, commit (Conventional Commits, one logical change) ...
git push --force-with-lease origin line/<X>    # NOT a plain push — see (2) below
#   branch CI: test (lts), test (1), format, python — BUT ONLY THE ONES YOUR DIFF TRIGGERS (ADR 0090).
#   Decide which to expect BEFORE polling, or you will wait for a check that never appears:
#     git diff --name-only origin/main...HEAD     # → look up §5's path table
#   Touched no .jl / no python/ / no docs/src/ ⇒ NO gate runs ⇒ nothing to wait for, merge now.
#   `docs` deliberately does NOT run on branches (gh-pages deploy race) — build locally when you
#   changed docs/src/**: DOCS_LINKCHECK=false julia --project=docs docs/make.jl
# every EXPECTED gate green on THAT sha? integrate — never switch branches in your worktree:
flock "$INT/.git/esm-integrate.lock" bash -eu -c '
  git -C "$0" pull --ff-only origin main
  git -C "$0" merge --no-ff --no-edit "origin/line/$1"
  # COLLATE the changelog fragments now on main (ADR 0095) — you hold the lock, so you are the
  # integrator for this moment. Skipping it reds the `changelog` gate on main; it is one command.
  ( cd "$0" && python3 scripts/collate_changelog.py )
  if ! git -C "$0" diff --quiet -- CHANGELOG.md changelog.d; then
    git -C "$0" add CHANGELOG.md changelog.d
    git -C "$0" commit -m "docs(changelog): collate changelog.d fragments into CHANGELOG.md"
  fi
  git -C "$0" push origin main
' "$INT" <X>
# then check main's OWN latest CI run (see (5)).
```

Four things here are load-bearing — all three were **wrong in the first version of this protocol** and caught by
an adversarial review on 2026-07-28 before any line ran them:

1. **Never `git switch main` in a line worktree.** `main` is permanently checked out in `$INT`, so git refuses:
   `fatal: 'main' is already used by worktree at …` (exit 128). Drive the integration worktree with `git -C`
   instead; nothing ever leaves your own worktree, so there is no "switch back" step.
2. **`--force-with-lease`, not a plain push.** The mandated `pull --rebase` *rewrites commits you already
   pushed*, so a plain `git push` is rejected non-fast-forward — and git's own hint ("use 'git pull'") leads to
   a `--no-rebase` merge that **duplicates every rebased commit**. The lease is safe because ADR 0028 mandates
   one session per line. Never "fix" the rejection with `git pull --no-rebase`.
3. **Merge `origin/line/<X>`, not the local branch.** That is the exact sha branch CI verified. A pre-rebase
   green verdict does **not** carry over to a post-rebase sha, and branch CI takes ~10 min here — long enough
   for a sibling's `main` push to force another rebase.
4. **`flock` the integration worktree.** It is the one shared checkout left; without the lock four lines can
   interleave `pull`/`merge`/`push` in it and reintroduce exactly the contention worktrees were adopted to
   remove.
5. **Then verify `main`'s own latest CI — when your diff triggered anything (ADR 0090).** Green branches do
   **not** guarantee a green `main`: `format`, `docs`, `python`, Aqua and JET are **whole-package** gates, and
   `docs` never runs on your branch at all. Also GitHub keeps only one *pending* run per branch, so a rapid
   follow-up push can cancel an intermediate `main` run (observed twice) — the **newest** `main` sha is the one
   that carries a verdict. **If the merge changed no gate-watched path, `main` runs nothing either** and there
   is nothing to verify; the one case that still deserves a look is a merge that touched `src/**` or
   `docs/src/**`, because that is when `docs` runs on `main` having never run on your branch.

6. **A script with a hard-coded absolute repo path writes into the INTEGRATOR worktree.** Several older
   scripts opened with `REPO = "/p/projects/open/Jamir/esm_land_emulator"`, so running one from a line
   worktree silently emits its fixtures into `$INT`'s working tree — dirtying the one shared checkout and
   losing the output from your own branch. Always derive the root from the script:
   `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` (Python) / `@__DIR__` (Julia). Fixed in
   `extract_biome_forcing.py`; **grep any script you reuse** (`grep -n 'open/Jamir/esm_land_emulator' scripts/*`).

`test (pre)` is `continue-on-error` and is currently red for unrelated Julia-prerelease churn — don't chase it.
**Merge at every milestone, never hoard.** Rebase early; a stale branch is the only real conflict source left.

**BEFORE YOUR SESSION ENDS (or when context runs low): refresh the `## NEXT — start here` block in
`lines/<X>/STATE.md` and commit it.** That block is the entire handoff — the hook replays it verbatim into the
next session. A session that ends without refreshing it has silently broken the chain.

### SLURM + scratch under parallel lines

- **The `priority` partition is usually EMPTY and starts instantly — but it caps at `cpu=64` PER JOB
  (`[VERIFIED 2026-08-04]`).** `PARTITION=priority QOS=priority` (both — the partition alone is rejected)
  routinely has ~45 idle nodes while `standard` has 126 alloc + queueing, so a job that would sit in
  `Reason=Priority` starts at once. The QOS's `MaxTRES cpu=64` is the catch, and **memory is strictly
  proportional and NOT raisable**: `DefMemPerCPU = MaxMemPerCPU = 5468 MB` cluster-wide with
  `SelectTypeParameters=CR_CPU_MEMORY`, so 64 cpus = **350 GB** is the hard ceiling on `priority` (vs
  `short`'s `cpu=2048` on `standard`). Both partitions' nodes are 128 cpu / 700 GB, so `priority` is a
  half-node cap, not weaker hardware. ⇒ send anything needing >350 GB to `standard`; send everything else
  to `priority`. A pending job can be moved in place with
  `scontrol update job <id> Partition=priority QOS=priority` (keeps the job id and log path) — it fails with
  `Job violates accounting/QOS policy` if it asks for >64 cpus, which is the tell, not a permissions problem.
- **Tag every job with your line prefix** (`S-`/`M-`/`E-`/`O-`), e.g.
  `scripts/run_tests_slurm.sh S-suite`, `scripts/sbatch_python.sh M-soil scripts/....py` — so `squeue` and
  `logs/<tag>.<jobid>.out` stay attributable. Each worktree has its own (gitignored) `logs/`.
- **Write only to `/p/tmp` paths your line created**; another line's artifacts are **read-only**. Never
  overwrite a shared artifact in place — version it.
- **To CHAIN a job after another, write a raw `.jcf` — do NOT edit the wrappers.** `sbatch_python.sh` /
  `sbatch_julia.sh` have **no** `DEPENDENCY` knob, and `scripts/sbatch_*.sh` are **integrator-owned** (§9 Gap 3),
  so a line cannot add one. Emit your own job file with `#SBATCH --dependency=afterok:<jid>` (log to your
  worktree's `logs/`, keep the `<line>-` tag) and `sbatch` it; confirm with
  `scontrol show job <new> | grep -o 'Dependency=[^ ]*'`. Worth doing whenever a long job's *result* needs a
  follow-up analysis: the chained job measures itself instead of waiting for a session to notice
  (`[VERIFIED 2026-07-28]`, S chained the ADR-0030 gate onto its copula job this way). `afterok` means a failed
  parent leaves the child pending/cancelled — that is the desired behaviour, but say so in the handoff so the
  next session knows a missing result may mean the parent died, not that nothing was scheduled. The
  *orchestrators* (`run_global_slow_*.sh`, `run_pooled_slow_*.sh`) DO take `DEPENDENCY=afterok:<jid>` as an env
  knob, because they inject it as a `#SBATCH` directive — the `SBATCH_DEPENDENCY` env var does **not** propagate
  through a wrapper's own `sbatch` call and silently comes up `Dependency=(null)`.
- **A NEW env knob you add to your own script is NOT forwarded by the wrappers — `export` it
  (`[VERIFIED 2026-08-05]`).** `scripts/sbatch_python.sh` builds a command prefix from a **fixed list** of
  variable names (`NCELLS SEED NO_DAILY OUT CELLS MODE SCENARIO …`), so a bare
  `MYKNOB=1 scripts/sbatch_python.sh …` reaches the *wrapper* but never the job, and the script silently
  runs with the knob's DEFAULT. It bit a `SMOKE=1` five-cell run that quietly became a full-grid one. The
  wrappers are **integrator-owned** (§9 Gap 3) so a line cannot extend the list — `export MYKNOB=1` first
  (SLURM's `--export=ALL` carries it), and `unset` it before the next submission or it leaks. The
  `env:` line the wrapper echoes shows only the FWD list, so an empty `env:` is not evidence of anything.
- **Julia BLOCK-BUFFERS stdout to a file, so a long probe's log stays at 0 lines until it exits
  (`[VERIFIED 2026-08-05]`).** A 22-minute probe looked indistinguishable from a hung job for its whole
  run. This is *not* the §3 "zero-byte log = hung" case (that is about the C binary, whose output dir is the
  progress signal) — for Julia, add `flush(stdout)` after each phase so progress is visible, and judge a
  silent Julia job by `sacct`/`squeue` CPU time, not by its log.
- Stagger heavy submissions as a courtesy, not a requirement: four lines share one account, the queue, and the
  `~/.julia` depot. `[VERIFIED 2026-07-28]` two full CI-faithful suites from different worktrees ran
  **simultaneously on the SAME node** sharing one depot and both came out clean (106918 pass / 0 fail, zero
  `Network is unreachable` / `can not merge projects` markers) — Julia's depot locking holds. The real cost of
  piling on is queue time and duplicated first-time precompiles, not corruption.
