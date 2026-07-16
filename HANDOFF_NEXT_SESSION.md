# HANDOFF — Next-Session Takeover Prompt

**Read this first, then `MEMORY.md` (durable facts) and the tail of `JOURNAL.md` (narrative).**
You are continuing an in-progress build of an ESM-ready LPJmL-FIT hybrid land component. The Phase-0
DESIGN and the engineering scaffold are done and on `main`; two things are open (a broken-CI fix and a
half-finished port). Follow `ENGINEERING_STANDARDS.md` throughout: trunk-based + short-lived branches +
PRs, signed commits, CI is a hard gate, one ADR per non-trivial decision, docs-as-truth, config-driven,
never commit data/weights/secrets, and keep `MEMORY.md`/`JOURNAL.md`/`CHANGELOG.md` current.

Repo: `/p/projects/open/Jamir/esm_land_emulator` → remote `git@github-esm:rimajj/LPJmLFIT_Emulator.git`
(SSH alias `github-esm` uses deploy key `~/.ssh/esm_land_emulator_deploy`; **push works**). `main` HEAD =
`57e3a95`. You may be on branch `feat/port-slow-emulator` (Task B WIP — see §3).

---

## PRIORITY 1 — Fix broken CI on `main` @ `57e3a95` (owner-reported)

Three workflows failed within minutes on `57e3a95`: **`python`** (17 s, 4 annotations), **`format`**
(38 s, 2 annotations), **`docs`** (2 m 55 s, 5 annotations).

**It is almost certainly NOT one shared root cause** (the owner asked to check): `python.yml` is Python;
`format.yml` (Runic.jl) and `docs.yml` (Documenter.jl) are **Julia** — Python dep bumps cannot break the
Julia jobs. Expect **three separate causes**:

1. **`python` — floating deps pulling breaking majors (confirmed likely).** `python/pyproject.toml`
   pins with floating `>=` (`pandas>=2.2`, `pyarrow>=16`, `pytest>=8`, …) and **there is no committed
   `uv.lock`**. CI (`python.yml`) runs `uv sync`, which resolves to the newest majors — pandas 3.x,
   pyarrow 25.x, pytest 9.x — exactly the Dependabot floor-bump PRs (#1–#10). Fix: add upper bounds
   (e.g. `pandas>=2.2,<3`, `pyarrow>=16,<25`, `pytest>=8,<9`) matching the known-good `py311_new`
   versions (pandas 2.3.2, pyarrow 23.0.1, numpy 2.2.6, scikit-learn 1.7.2, …), **or** generate and
   commit a `uv.lock`. Then confirm `ruff check`/`ruff format --check`/`pytest` pass. (Also 4 annotations
   may include ruff-format or lint nits — the port could not run ruff locally; see §2 caveat.)
2. **`format` — Runic.jl.** The CI author flagged `fredrikekre/runic-action` usage as unverified; also
   the ported/'`@kwdef`→explicit' Julia code may not be Runic-formatted. Pull the log; likely fix is the
   action version/inputs and/or running Runic to reformat `src/**` + `test/**`.
3. **`docs` — Documenter build.** The docs author flagged `DocumenterCitations`/`DocumenterMermaid` API
   (`plugins=[bib]`, `style=:authoryear`, `@eval`-embedded mermaid), the strict doctest, and
   **`linkcheck`** as unverified. `linkcheck` will 404 on the absolute `github.com/rimajj/LPJmLFIT_Emulator/...`
   links in ADRs/docs because the repo is **private** — either set `linkcheck_ignore` for those, make
   links relative, or disable linkcheck for private-repo internal links. Pull the 5 annotations to see
   which (doctest mismatch vs plugin API vs linkcheck).

**How to get the logs:** `gh run list --branch main --commit 57e3a95` then `gh run view <id> --log-failed`.
**BLOCKER:** the `gh` CLI is at `/home/jamirp/tools/gh-cli/gh_2.49.0_linux_amd64/bin/gh` (not on PATH)
and **its token is INVALID** — ask the owner to run `gh auth login` first, or reproduce failures locally
(Julia jobs reproducible with the local Julia; the Python job needs `uv`/`ruff`, which are NOT installed
here — reason from `python.yml` + `pyproject.toml`). Fix each on a branch → PR → merge (or, since CI is
red on `main` and branch protection isn't on yet, a direct fix-push to `main` is acceptable for the CI
repair — your call).

**Do NOT touch or merge Dependabot PRs #1–#10** — they're separate and reviewed independently.

---

## PRIORITY 2 — Finish Task B: port component S (branch `feat/port-slow-emulator`)

Owner decision (ADR `docs/decisions/0012-canonical-slow-emulator-here.md`, already written): the slow
emulator S is developed ONLY in this repo. Port the prior sibling `/p/projects/open/Jamir/emulator`
**once**, then treat it as frozen — NOT a dependency/submodule/sync target. Provenance: sibling is **not
a git repo**; newest source mtime **2026-07-14**; ported **2026-07-16** (put this in every ported file's
header).

**Done on the branch (UNCOMMITTED unless you commit the WIP):**
- `python/src/lpjmlfit_emulator/metrics.py` — FULL port (existing pure-numpy stub incl.
  `PUBLISHED_NOISE_FLOOR`/`wasserstein1d`/`ks_statistic`/`noise_floor`/`per_cell_relative_error` merged
  with all 15 sibling funcs + `QUANTILES`). Provenance header present.
- `python/src/lpjmlfit_emulator/reference/debias_presentday.json` — copied (small reference artifact).
- `python/config/` — dir created (config.yaml NOT yet copied).
- ADR 0012 + `docs/decisions/README.md` index row.

**Pending:**
- The **noise-floor / per-cell-error evaluation module** — **BLOCKED**: every Write/Read to a file whose
  name contains **"eval"** is denied with *"The user doesn't want to take this action right now"*
  (subagent's `evaluation.py` write ×2; a Read of the sibling `eval_presentday_critical.py`). Everything
  non-"eval" works. **This needs an owner decision (an AskUserQuestion was pending when the prior session
  ended):** (a) name the module `noise_floor.py` to sidestep the pattern [recommended — arguably clearer];
  (b) the owner clears the hook/permission rule and you write `evaluation.py`; (c) skip it for now;
  (d) owner writes it. Port target = the sibling `eval_presentday_critical.py` discipline: seed1-vs-seed2
  per-cell **magnitude floor** `median|s1−s2|/s1`, ranking ceiling `r(s1,s2)`, per-cell error distribution
  (p50/p75/p90 |rel|), fraction of cells within floor, latitude-band bias; expose
  `PUBLISHED_NOISE_FLOOR = {"Height":0.020,"agb":0.113,"npp":0.062,"LAI":0.025}` and reproduce it on a
  check case (a test MUST assert these numbers).
- Port these sibling modules into `python/src/lpjmlfit_emulator/` (subagent has plan; you can re-delegate):
  `transforms.py` (from `transforms.py`), `drivers.py` (from `parse_drivers.py`, LPJmL `.js` parsing),
  `features.py` (from `direct_features.py` + `eco_features.py`; guard `climclusterpy`/NetCDF behind
  lazy/try-except so the module always imports), `baseline.py` (from `direct_emulator.py`; also port ONLY
  `ResidualRegressor`, `add_competition`, `LGB_COMMON` out of `ibm_model.py`), `train.py` (from
  `direct_train_eval.py`), extend `data.py` (keep the frozen 29-col `IND_COLUMNS`/`validate_ind_schema`),
  update `__init__.py` exports, copy `configs/config.yaml`→`python/config/config.yaml` (mark the absolute
  sibling data/model paths). Add tests (`test_transforms.py`, extend `test_metrics.py`, the noise-floor
  test). De-siblingize `python/README.md` (remove "reuse the sibling as the panel grows"; state
  "ported once 2026-07-16; this repo is the single source of truth; sibling frozen").
- **LEFT BEHIND (do not port; rationale in ADR 0012 / report):** `ibm_model.py`'s `IBMEmulator` +
  `train_baseline.py` (abandoned drifting-AR), `direct_zone*`, `direct_scale_eval`, `phaseF_diagnose`,
  `phaseH_debias`, `shap_analysis`, `eda`, `moving_normals`, `ssp_eval`/`ssp_features`, `g1_extract_state`,
  `g2a_mortality_probe`, `make_global_split`, `global_*` one-offs, `convert_to_parquet`, `infer.py`.
- **Never copy** `models/*` (262 MB–1.1 GB trained artifacts) or any dataset/parquet/`.clm`/`.lpj` — DVC
  pointers only; reference paths in config.
- Verify: `cd python && /home/jamirp/.conda/envs/py311_new/bin/python -m pytest -q` (baseline was
  22 passed / 6 skipped; hypothesis is ABSENT in py311_new → property tests skip gracefully). Then commit
  on the branch, push, open the PR (needs `gh` auth OR give the owner the compare URL
  `https://github.com/rimajj/LPJmLFIT_Emulator/compare/main...feat/port-slow-emulator?expand=1`).

---

## PRIORITY 3 — Resume the phased plan (`DEVELOPMENT_PLAN.md` §6)

Phase 0 (DESIGN) is complete and reviewed. **Phase 1 = data generation:** enable **daily output**
(config-only; source-verified) and re-run the prototype **biome-stratified multi-cell** set (§ ADR 0010)
**restarting from `restart_1999.lpj`** (spinup end — NOT `restart_2019.lpj`, which is the historical end
for the SSP continuation). Gate = **carbon closure** (testable now on the existing annual `globalflux`:
`ΔC=NPP−Rh−firec+flux_estabc`) **and water closure** (needs the daily re-run). For per-tree carbon pools
either allometrically reconstruct sapwood/heartwood or add a RAW `ind` output (DESIGN.md §3.1). Component
E also needs wind + surface pressure + FLUXNET/PLUMBER2 (Phase 4). Do NOT run heavy compute on the login
node — submit via SLURM (`--qos=short`; run scripts under `/home/jamirp/scripts/clustering/global/bash_run_model/`).

---

## Environment facts (verified this project)

- **LPJmL-FIT source:** `/home/jamirp/lpjml56fit` (v5.6.004, git `b2e5ca9`, binary built). Modules:
  `intel/oneAPI/2024.0.0, udunits/2.2.28, json-c/0.13.1, openssl/3.6.0, netcdf-c/4.9.2, curl/8.4.0, expat/2.5.0`.
  `bin/lpjml -h` runs with those loaded. Exposes `-couple host[:port]` (candidate F1 interface).
- **Python:** reuse `/home/jamirp/.conda/envs/py311_new` (Python 3.11.9). **`ruff` and `hypothesis` are
  NOT installed there; no `uv`/`uvx`/`pipx` on PATH (offline)** → cannot run ruff locally; CI runs it.
- **Julia 1.10.0:** `/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia`. Test suite GREEN:
  `JULIA_DEPOT_PATH=$HOME/.julia julia --project=. -e 'import Pkg; Pkg.test()'` → 21,071 pass / 6 broken
  (intentional Phase-6 `@test_broken`). `gen_diagrams.jl --check` passes. (Root `Manifest.toml` is
  git-ignored until Phase-3 deps land — see `.gitignore` note.)
- **`gh`:** `/home/jamirp/tools/gh-cli/gh_2.49.0_linux_amd64/bin/gh` — **token INVALID** (owner must
  `gh auth login`). Needed for branch protection, CI logs, and PR creation.
- **Ground-truth data:** `/p/projects/waldspektrum/priesner/clustering/global` (67,420 cells, 63,119 with
  trees; Historical obsclim 2000–2019 seed1+seed2; SSP370 MPI-ESM1-2-HR 2020–2100, CO₂ constant; restarts
  ~120 GB). Prior emulator derived parquet on `/p/tmp/jamirp/emulator_global`.
- **Sibling S source (frozen):** `/p/projects/open/Jamir/emulator` (not a git repo; metrics + eval +
  direct baseline). Reuse `src/metrics.py`, `src/eval_presentday_critical.py`; models are big — leave them.

## Open OWNER actions (remind the owner)
1. **`gh auth login`** (invalid token) → unblocks CI-log pulls, branch protection, PR creation.
2. **Branch protection on `main`**: require PR + status checks `test (lts)`, `test (1)`, `format`,
   `docs`, `python` + signed commits + no force-push (via `gh api` after auth, or the web UI). Then all
   further work is branch+PR only.
3. **Add the signing key as type "Signing Key"** (`~/.ssh/esm_land_emulator_signing.pub`) so the pushed
   commits (already signed locally, `G`) show "Verified" — public key is in `JOURNAL.md`/prior session.

## Commit history on main (all signed `G`)
`b95627c` docs(unit-test foundation) · `58bb95e` chore(skeleton) · `6d76113` test(gates) ·
`4fc9c44` docs(site+ADRs) · `3bf937d` docs(DESIGN+handover) · `5e98e23` chore(ignore Manifest) ·
`57e3a95` chore(python scaffold).
