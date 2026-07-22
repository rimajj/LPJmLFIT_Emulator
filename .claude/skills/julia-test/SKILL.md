---
name: julia-test
description: Run the Julia test suite for the LPJmL-FIT emulator correctly (delete test/Manifest.toml first; login-node/CI-faithful; Enzyme pin; testitems layout; format/JET/Aqua; regenerate ReferenceTests baselines). Use whenever running, adding, or debugging Julia tests, the format gate, or gradient/conservation gates.
---

# julia-test — run the suite the way CI does

## Run the full suite — DURABLE + CI-faithful (the DEFAULT; survives session teardown)

Submit it to SLURM. A login-node foreground run / `nohup &` / background-shell **dies with the session**
(dropped SSH, agent restart, UI stop) — you come back to a half-finished run and no result. SLURM runs it
on a compute node independently and logs to shared `/p`, so ANY later session can collect the result.

```bash
cd /p/projects/open/Jamir/esm_land_emulator
scripts/run_tests_slurm.sh [tag]     # warms the shared depot on the login node, then runs the CI-faithful
                                     # Pkg.test() (rm test/Manifest.toml + re-resolve) on a compute node
```
Collect from ANY session: `squeue -u $USER` · `tail -f logs/<tag>.<jobid>.out` · the log's LAST line is
`=== JOB DONE tag=<tag> exit=<code> ===` (grep it; the ReTestItems `N pass, M fail` summary is just above).
Expect ≈ **48.1k pass / 0 fail / 4 broken**, ~5–6 min. Julia = `/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia` (lts).

**Any OTHER long job (>a few seconds)** — benchmarks, probes, decadal runs, training — uses the same durable
path: `scripts/sbatch_julia.sh <tag> --project=. <script.jl>` (or `-e '<expr>'`); heavy NN training →
`scripts/sbatch_train.sh` (`--project=test`). Keep every job's script + `--output` on shared `/p`
(`logs/`, `/p/tmp/jamirp/`), **never** the `/tmp/claude-*` scratchpad — compute nodes can't open it.

**Why the wrapper warms the depot first (network safety):** manifests are git-ignored ⇒ every run
re-resolves to newest-allowed deps (like CI). Compute nodes have no GitHub egress but DO reach the Julia
pkg-server (tarballs), so the wrapper `Pkg.instantiate/precompile`s on the login node first; the node then
finds every resolved dep cached and needs no network. Residual risk: a not-yet-mirrored version → git-clone
race → clear `Network is unreachable`; fall back to the login-node one-liner below.

## Quick interactive one-liner (login node) — only for a fast check you'll watch finish in-session

```bash
rm -f test/Manifest.toml     # REQUIRED — a stale dev-path manifest makes Pkg.test() fail "can not merge projects"
JULIA_DEPOT_PATH=$HOME/.julia julia --project=. -e 'import Pkg; Pkg.test()'
```
Ignore benign `curl_easy_setopt: 48` spew.

## Gotchas

- **Do NOT commit `test/Manifest.toml`** (settled session 27, "no"): `Pkg.test()` resolves the test env
  in a sandbox temp dir, so it wouldn't feed CI, and it embeds a machine-specific absolute path.
- **Enzyme is pinned `0.13.0 - 0.13.188`** in both `Project.toml` and `test/Project.toml`. 0.13.189
  regressed the Enzyme-reverse canopy path (`LLVM error: Canonicalization failed`). If `test (lts)` goes
  red with the test tree unchanged, suspect a dep bump — diff `Enzyme vX.Y.Z` in last-green vs first-red
  CI job logs.
- **Julia 1.10 vs 1.11:** Enzyme-reverse canopy is verified only on 1.10; canopy gate parts are guarded
  `VERSION < v"1.11"`. Don't "fix" a 1.11 canopy failure by removing the guard.
- **`*_test(s).jl` naming trap:** ReTestItems scans the whole repo for `*_test.jl`/`*_tests.jl` and fails
  collection on any file that isn't pure `@testitem`/`@testsetup`. Name repro/diagnostic scripts
  `*_probe.jl` / `*_diagnosis.jl` / `*_decomp.jl`.
- **Runtime `[deps]` stays EMPTY** (ADR 0014). Aqua fails on stale deps. New training backends go in the
  extension `ext/FDiffTrainingExt.jl` (weakdeps), not `[deps]`.

## Layout & gates

- ReTestItems `@testitem`s under `test/testitems/`; entry `test/runtests.jl` = `runtests(LPJmLFITEmulator)`.
- Fixtures: `test/testitems/references/`.
- Key gates: `gradient_correctness_tests.jl` (Enzyme/ForwardDiff vs FiniteDifferences), `numerical_regression_tests.jl`
  and `cbinary_validation_tests.jl` (vs the C oracle), `conservation_closure_tests.jl`, `energy_closure_tests.jl`,
  `coupled_run_tests.jl`, `biome_coupled_tests.jl`, plus `aqua_tests.jl` / `jet_tests.jl`.

## Format gate (Runic) — CI installs Runic 1.7.0

```bash
julia --project=@runic -e 'import Pkg; Pkg.activate(temp=true); Pkg.add(name="Runic", version="1"); using Runic; exit(Runic.main(["--check", "src", "test", "ext", "scripts"]))'
```
Reformat (drop `--check`) with the same Runic version before pushing.

## Docs (local, egress-safe)

```bash
DOCS_LINKCHECK=false julia --project=docs docs/make.jl      # CI keeps linkcheck ON
julia scripts/gen_diagrams.jl --check                       # diagram drift alarm
```

## Regenerating ReferenceTests baselines

Baselines are committed text/CSV in `test/testitems/references/`. Regenerate **only** on an intentional
physics change, and note *which* baseline moved (the "no committed baseline moves unless deliberate"
discipline). `scripts/regen_fdiff_baselines.jl` regenerates the F_diff annual-totals set. A `sapwood_bg`
default-flip additionally moves the `multi_individual` CUE gate (~0.497) and the coupled/decadal
NPP-derived baselines.
