---
name: julia-test
description: Run the Julia test suite for the LPJmL-FIT emulator correctly (`julia` is NOT on PATH — use /p/system/packages_rhel9/tools/julia/1.10.0/bin/julia; delete test/Manifest.toml first; login-node/CI-faithful; Enzyme pin; testitems layout; format/JET/Aqua; regenerate ReferenceTests baselines). Use whenever running, adding, or debugging Julia tests, the format gate, gradient/conservation gates, or any `julia ...` command (which needs the absolute path).
---

# julia-test — run the suite the way CI does

## ⚠️ `julia` is NOT on PATH (every session — stop hitting `bash: julia: command not found`)

There is no `julia` on the login-node PATH. **Always use the absolute path**, or set a shorthand at the
start of the Bash call (shell state does NOT persist between calls, so re-set it each call):
```bash
JULIA=/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia   # lts 1.10.0 — the CI-faithful one
$JULIA --startup-file=no -e '...'
```
Every `julia ...` command in this skill (format gate, docs, gen_diagrams, the `ALLOW_LOGIN_HEAVY=1`
fallback, quick REPL checks) means **`$JULIA`** / the absolute path. The SLURM wrappers
(`run_tests_slurm.sh`, `sbatch_julia.sh`) already hard-code it, so they Just Work. Julia 1.12 (for
reproducing a `test (1)`-only JET failure, CLAUDE.md §2) is `/p/system/packages_rhel9/tools/julia/1.12.2/bin/julia`.

## Run the full suite — DURABLE + CI-faithful (the DEFAULT; survives session teardown)

Submit it to SLURM. A login-node foreground run / `nohup &` / background-shell **dies with the session**
(dropped SSH, agent restart, UI stop) — you come back to a half-finished run and no result. SLURM runs it
on a compute node independently and logs to shared `/p`, so ANY later session can collect the result.

```bash
cd <YOUR worktree>                   # e.g. /p/projects/open/Jamir/wt-M — NOT a hard-coded path (see below)
scripts/run_tests_slurm.sh [tag]     # warms the shared depot on the login node, then runs the CI-faithful
                                     # Pkg.test() (rm test/Manifest.toml + re-resolve) on a compute node
```
Collect from ANY session: `squeue -u $USER` · `tail -f logs/<tag>.<jobid>.out` · the log's LAST line is
`=== JOB DONE tag=<tag> exit=<code> ===` (grep it; the ReTestItems `N pass, M fail` summary is just above).
Expect ≈ **48.1k pass / 0 fail / 4 broken**, ~5–6 min. Julia = `/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia` (lts).

**Run it from YOUR OWN worktree, and tag with your line prefix** (ADR 0028; this line used to read
`cd /p/projects/open/Jamir/esm_land_emulator`, which is now the **integrator** worktree). The wrapper resolves
its own root — `REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"` — so `wt-M/scripts/run_tests_slurm.sh`
tests `wt-M` and logs to `wt-M/logs/`; invoking the *integrator's* copy would silently test `main` instead of
your branch and litter the one shared checkout. Verified 2026-07-28 (`M-suite-jetpin`, job 1622318). Same
class as CLAUDE.md §9 item 6 ("a script with a hard-coded absolute repo path writes into the integrator
worktree") — the difference is that here the hard-coded path is in the *instructions*, not the script.

**A `test/Project.toml` `[compat]` change forces a fresh resolve**, so expect the wrapper to spend an extra
minute or two re-resolving + precompiling both envs on the login node before it submits. That is the warm
working (it is what keeps the compute node off the network), not a hang.

**Any OTHER long job (>a few seconds)** — benchmarks, probes, decadal runs, training — uses the same durable
path: `scripts/sbatch_julia.sh <tag> --project=. <script.jl>` (or `-e '<expr>'`); heavy NN training →
`scripts/sbatch_train.sh` (`--project=test`). Keep every job's script + `--output` on shared `/p`
(`logs/`, `/p/tmp/jamirp/`), **never** the `/tmp/claude-*` scratchpad — compute nodes can't open it.

**Why the wrapper warms the depot first (network safety):** manifests are git-ignored ⇒ every run
re-resolves to newest-allowed deps (like CI). Compute nodes have no GitHub egress but DO reach the Julia
pkg-server (tarballs), so the wrapper `Pkg.instantiate/precompile`s on the login node first; the node then
finds every resolved dep cached and needs no network. Residual risk: a not-yet-mirrored version → git-clone
race → clear `Network is unreachable`; fall back to the `ALLOW_LOGIN_HEAVY=1` login-node one-liner below.

**⚠️ The warm MUST cover the TEST env, not just `--project=.` (this bit on 2026-07-28; fixed in the wrapper).**
`Pkg.test()` does **not** use `test/Project.toml` in place — it builds a **SANDBOX** env from it and
**re-resolves that sandbox** to newest-allowed versions, and that resolve runs **on the compute node**. So every
test-only dep (Lux/Zygote/Enzyme/JET/Aqua → NNlib …) must already be in the shared depot *at the version the
fresh resolve picks*. Warming only the main project left that to luck: it worked in a long-lived checkout whose
depot had accumulated the versions, and **failed instantly in a fresh `git worktree`** with
`failed to clone from https://github.com/FluxML/NNlib.jl.git … Network is unreachable` inside Pkg's
`sandbox(...)` — i.e. it would break every new work line's (ADR 0028) first suite run. `run_tests_slurm.sh` now
also resolves/precompiles `--project=test` (with `Pkg.develop(path=REPO)`) and then **deletes the
`test/Manifest.toml` that warm creates** (a leftover triggers the `can not merge projects` failure below, and it
must never be committed). Consequence to expect: the **first** run after a dep bump or in a new worktree spends
several minutes warming on the login node before it submits — that is the fix working, not a hang.

## Login node: NO full suite (hook-enforced)

The full `Pkg.test()` suite on the login node overloads the node and dies with a dropped session — the
`slurm-guard` PreToolUse hook (`.claude/hooks/slurm-guard.sh`) **blocks** it (also `test/runtests.jl`,
`bin/lpjml`, and `nohup`/backgrounded or heavy foreground Julia jobs). Use `run_tests_slurm.sh` /
`sbatch_julia.sh`. Quick REPL/compile checks (seconds) still run fine on the login node.

**Deliberate override** — only for the pkg-server-not-mirrored fallback above, prefix `ALLOW_LOGIN_HEAVY=1`:
```bash
rm -f test/Manifest.toml     # REQUIRED — a stale dev-path manifest makes Pkg.test() fail "can not merge projects"
ALLOW_LOGIN_HEAVY=1 JULIA_DEPOT_PATH=$HOME/.julia julia --project=. -e 'import Pkg; Pkg.test()'
```
Ignore benign `curl_easy_setopt: 48` spew.

## Gotchas

- **Do NOT commit `test/Manifest.toml`** (settled session 27, "no"): `Pkg.test()` resolves the test env
  in a sandbox temp dir, so it wouldn't feed CI, and it embeds a machine-specific absolute path.
- **Enzyme is pinned `0.13.0 - 0.13.188`** in both `Project.toml` and `test/Project.toml`. 0.13.189
  regressed the Enzyme-reverse canopy path (`LLVM error: Canonicalization failed`). If `test (lts)` goes
  red with the test tree unchanged, suspect a dep bump — diff `Enzyme vX.Y.Z` in last-green vs first-red
  CI job logs.
- **JET is pinned `"0.9, 0.11"`** in `test/Project.toml` (added 2026-07-28). **JET 0.12 REMOVED the
  `target_defined_modules` option** that `test/jet_tests.jl` passes ⇒
  `JETConfigError: Given unexpected configuration: target_defined_modules = true`. It surfaces **only on
  `test (1)`** (Julia 1.12 resolves JET 0.11+) while `test (lts)` (Julia 1.10, JET 0.9.x) stays green — the
  giveaway is a summary like *"106848 passed, 0 failed, 1 errored"* where the lone error is the JET config.
  Lift by migrating the call to JET 0.12's replacement API, then widening the bound. **JET had no `[compat]`
  entry at all before this** — that absence was the root cause, so when a gate dep goes red, check whether
  it is pinned before anything else.
- **Julia 1.10 vs 1.11:** Enzyme-reverse canopy is verified only on 1.10; canopy gate parts are guarded
  `VERSION < v"1.11"`. Don't "fix" a 1.11 canopy failure by removing the guard.
- **`*_test(s).jl` naming trap:** ReTestItems scans the whole repo for `*_test.jl`/`*_tests.jl` and fails
  collection on any file that isn't pure `@testitem`/`@testsetup`. Name repro/diagnostic scripts
  `*_probe.jl` / `*_diagnosis.jl` / `*_decomp.jl`.
- **Runtime `[deps]` stays EMPTY** (ADR 0014). Aqua fails on stale deps. New training backends go in the
  extension `ext/FDiffTrainingExt.jl` (weakdeps), not `[deps]`.
- **Float32 coupled-loop test trap:** `run_coupled_cell(fc::FDiffFastCore{T}, clo::SEBEnergyClosure{T}, …)`
  dispatches on a SHARED `T` across `(fc, clo)`, but the bare `SEBEnergyClosure(; …)` / `SharedState(; …)`
  constructors DEFAULT to `{Float64}`. A test that builds a `{Float32}` core/slow/forcings but a bare-ctor
  closure/state hits a `MethodError: no method matching run_coupled_cell(::FDiffFastCore{Float32}, …
  ::SEBEnergyClosure{Float64}, …)`. Build them explicitly: `SEBEnergyClosure{Float32}(; …)` /
  `SharedState{Float32}(; …)`. Sibling Float32 tests that only call `reconcile_demography!` never surface
  this — the first test to drive the FULL coupled loop in Float32 will (bit `slow_membership_tests.jl`).
  A green suite is the check; the plain compile smoke won't catch a dispatch gap only the Float32 path hits.

## Layout & gates

- ReTestItems `@testitem`s under `test/testitems/`; entry `test/runtests.jl` = `runtests(LPJmLFITEmulator)`.
- Fixtures: `test/testitems/references/`.
- Key gates: `gradient_correctness_tests.jl` (Enzyme/ForwardDiff vs FiniteDifferences), `numerical_regression_tests.jl`
  and `cbinary_validation_tests.jl` (vs the C oracle), `conservation_closure_tests.jl`, `energy_closure_tests.jl`,
  `coupled_run_tests.jl`, `biome_coupled_tests.jl`, plus `aqua_tests.jl` / `jet_tests.jl`.

## Auditing a gate or fixture assertion you just wrote

This repo's trust model IS its gates and committed fixtures, so a gate that looks green while proving
nothing is the most expensive possible bug. Two checks, both of which have caught a real hole here
(ADR 0050, 2026-07-28):

1. **Does the gate exercise the code path the ARTIFACTS take?** A generator with modes/flags can certify
   mode A while every committed file is produced by mode B — then the whole B derivation ships covered by
   nothing. Diff "what the gate calls" against "what `main()` defaults to", and unit-gate the difference
   (e.g. check a ported routine against an independent closed-form evaluation of the source algorithm).
   The same applies to env-var provenance: if `SRC=x` is gate-certified and `SRC=y` is merely *allowed*,
   make `y` abort rather than inherit the verdict.
2. **Are ordering assertions permutation-insensitive?** `@test a > b > c` over per-cell fixtures pins the
   ORDER, not which file belongs to which cell. Enumerate the permutations of your fixture set and count how
   many satisfy every assertion — if it is more than 1, a mis-paired fixture ships green. Fix with per-item
   provenance PINS (a numeric value only that item's own data produces) and row-wise identity assertions
   instead of an order-blind `Set` comparison. Derive pinned numbers FROM the committed file
   programmatically; transcribing them by hand is its own failure mode (it cost a red suite here).

Also: keep tolerances at the artifact's real precision (accumulated print rounding), not at a round number
that happens to pass — a tolerance 20× looser than the worst committed deviation admits the very drift the
assertion exists to catch.

3. **Give the mechanism enough YEARS to happen, or your "it does something" assertion tests the test.**
   `reconcile_demography!` FORCES `ρ = 1` on its year-0 call (`s.year == 0`) to seed the recursive AR state,
   so the first year-end is a deliberate no-op and the first real demographic change lands at the **second**
   year-end. In an `nyears = 2` coupled gate that change is applied *after* the last simulated day, so S
   provably cannot move F's fluxes and an `npp_with_S != npp_without_S` assertion fails for a reason that is
   a property of the test, not the model (cost a full suite run, job 1643115 → fixed at `nyears = 4`).
   Before asserting that a slow/annual mechanism changed something, count the steps between when it FIRST
   acts and when the run ends. Related: `@test length(s.target_history) == nyears` is the cheap check that
   the year-end hook fired as often as you think — `run_coupled_cell` only calls it on
   `i % days_per_year == 0`, so a forcing length that is not a whole number of years silently drops the last.

4. **Pin fixtures at ROUND-TRIPPABLE precision when they feed a model, not at display precision.** A tree
   ensemble compares features against split thresholds, so a truncated fixture can land on the other side of
   a split. `%.6f` truncated a committed boundary value 1863.695068359375 → 1863.695068; emitting `repr`
   (`%.17g`) from the Python extractor made the row bit-identical to the artifact's own baked meta, which
   then upgraded a fuzzy `isapprox` provenance check into an exact `==`. If two files are supposed to hold
   the same quantity from the same upstream, make the test an equality — it is a far stronger statement that
   the derivation pulled the right columns in the right ORDER.

## Format gate (Runic) — CI installs Runic 1.7.0

`julia` is not on PATH (see the ⚠️ note at the top) — use the absolute path / `$JULIA`:
```bash
JULIA=/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia
$JULIA --startup-file=no -e 'import Pkg; Pkg.activate(temp=true); Pkg.add(name="Runic", version="1"); using Runic; exit(Runic.main(["--check", "src", "test", "ext", "scripts"]))'
```
Pass specific files instead of the dirs for a fast targeted check. Reformat with `--inplace` (or drop
`--check`) with the same Runic version before pushing.

**`slurm-guard` false-positives on the format check.** The guard matches the *command text*, so a Runic
invocation that merely **names** a heavy-looking script (`validate_*.jl`, `train_*.jl`, `*_probe.jl`,
`run_coupled_*.jl`) is blocked as "a heavy Julia job" even though it only parses files. A format check is a
genuine seconds-long job: prefix **`ALLOW_LOGIN_HEAVY=1`**. (Same class as the `repo-commit` skill's
"slurm-guard false-positives on commit MESSAGE text".)

**Two traps that let an unformatted file reach CI (both bit ADR 0026):** (1) CI checks ALL of
`src test ext scripts` — a targeted single-file check misses a sibling you also touched (a NEW
`scripts/*.jl` is the usual culprit). Check the DIRS, or every touched file. (2) **NEVER pipe the check to
`tail`/`grep`** — `$JULIA -e 'exit(Runic.main([...]))' | tail` returns *tail's* exit code (0), MASKING
Runic's non-zero exit, so a broken file looks formatted. Capture Runic's exit directly (`… ; echo rc=$?`),
no pipe. Runic wants multi-line function calls with each arg group on its own indented line and the closing
`)` on its own line — a common miss when hand-editing a multi-line `println(...)`.

## Docs (local, egress-safe)

```bash
DOCS_LINKCHECK=false julia --project=docs docs/make.jl      # CI keeps linkcheck ON ($JULIA — not on PATH)
julia --project=. scripts/gen_diagrams.jl --check           # diagram drift alarm — NEEDS --project=.
```
First run in a fresh checkout: `$JULIA --project=docs -e 'import Pkg; Pkg.develop(path="."); Pkg.instantiate()'`.
**Do that BEFORE submitting the docs build to SLURM too** — `scripts/sbatch_julia.sh` warms only `--project=.`
and `--project=test`, never `--project=docs`, and compute nodes have no egress. Skipping it fails on the node
with `ArgumentError: Package Documenter … is required but does not seem to be installed`, which reads like a
missing dependency but is an unwarmed environment (and a bare `Pkg.instantiate()` without the `Pkg.develop`
first fails earlier still, with `expected package LPJmLFITEmulator [e4cfba23] to be registered` — it is a
local path dep, exactly as `.github/workflows/docs.yml` does it).
(`docs/Manifest.toml` is gitignored, so that `Pkg.develop` is safe to run in any worktree.)

**Two traps in the diagram alarm, both hit on 2026-07-28:** (1) `gen_diagrams.jl` does `using
LPJmLFITEmulator`, so without **`--project=.`** it dies with `ArgumentError: Package LPJmLFITEmulator not found
in current path` — which reads like a broken checkout, not a missing flag. (2) **NO CI job runs this check**
(grep `.github/workflows` for `gen_diagrams` — nothing), so CLAUDE.md §9's "the diagram-staleness gate reds
`main`" means the LOCAL alarm only. `docs/src/generated/components.mmd` had consequently been stale since the
Phase-4 commit `773945fb` — the rendered diagram contradicted `src/registry.jl` for weeks. **Run it whenever you
touch `src/registry.jl`, and don't assume CI will catch it.**

**Strict-docs gotcha (`warnonly=false`, `checkdocs=:exports`) — a docstring change can turn `docs` RED while
all tests stay green.** Two ways it bites:
1. A NEW EXPORTED symbol with no docstring → `checkdocs=:exports` fails. `docs/src/reference/api.md` uses
   `@autodocs Modules=[LPJmLFITEmulator]`, so any exported symbol is auto-listed once it HAS a docstring.
2. An `@ref` **inside a rendered docstring** (i.e. an `LPJmLFITEmulator` symbol) pointing at a symbol that is
   NOT rendered → broken cross-ref → strict-build failure. The `DRF` submodule is NOT in api.md's `@autodocs`,
   so `` [`DRF.foo`](@ref) `` from a top-module docstring breaks it — use a plain `` `DRF.foo` `` code span.
   (`@ref`s BETWEEN `DRF` docstrings are harmless: DRF docstrings aren't rendered, so Documenter never
   processes them — that's why the pre-existing `save_forest`↔`load_forest` @refs are fine.)
Reproduce with the local docs build above; CI surfaces it only as a red `docs` check (not in the test log).

## Regenerating ReferenceTests baselines

Baselines are committed text/CSV in `test/testitems/references/`. Regenerate **only** on an intentional
physics change, and note *which* baseline moved (the "no committed baseline moves unless deliberate"
discipline). `scripts/regen_fdiff_baselines.jl` regenerates the F_diff annual-totals set. A `sapwood_bg`
default-flip additionally moves the `multi_individual` CUE gate (~0.497) and the coupled/decadal
NPP-derived baselines.
