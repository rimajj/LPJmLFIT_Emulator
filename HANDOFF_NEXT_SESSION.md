# HANDOFF — Next-Session Takeover Prompt

**Read this first, then `MEMORY.md` (durable facts) and the tail of `JOURNAL.md` (narrative).**
You are continuing an in-progress build of an ESM-ready LPJmL-FIT hybrid land component (S = slow ML
distribution emulator, F = fast physical core kept, E = new energy balance). Phase 0 DESIGN is frozen
and on `main`. DONE: CI repair, the component-S port, carbon closure, and now **P3b — the daily-output
re-run + WATER CLOSURE (PASSED, session 3)**. Both Phase-1 gates (carbon + water) are met.
The next live work is **generating the full-global daily F/E training dataset** (owner scope/resource
decision — see PRIORITY 1) and then **Phase 2+** (`DEVELOPMENT_PLAN.md` §6).

Repo: `/p/projects/open/Jamir/esm_land_emulator` → remote `git@github-esm:rimajj/LPJmLFIT_Emulator.git`
(SSH alias `github-esm`, deploy key `~/.ssh/esm_land_emulator_deploy`; **push works with NO manual auth**).
**Workflow = MAIN-ONLY** (ADR 0013). `gh` authenticated. Run `git log --oneline -5` for the current HEAD.

---

## ⚙️ WORKFLOW CHANGE (owner decision, session 2) — WORK ON `main` DIRECTLY

The owner switched away from the trunk-based + short-lived-branches + PR-per-change model. **Going
forward: commit and push straight to `main`. No feature branches, no PRs, no branch protection.**
- CI still runs on every push to `main` (workflows trigger on `push: main`), so you keep the test
  signal — it's now a **smoke alarm** (tells you after) not a **gate** (blocks before). If a push
  turns `main` red, fix forward.
- This is a deliberate relaxation of `ENGINEERING_STANDARDS.md` §0/§1 (which mandated PRs + branch
  protection as the "hard gate" for AI code). **DONE (session 3):** `docs/decisions/0013-main-only-workflow.md`
  written + §1 softened (struck-through originals + reinstatement command) + ADR index updated.
- Practical upside: no more force-pushes (no rebasing) and no branch-protection mutations → the
  auto-mode permission classifier stops prompting for those.
- **Do NOT set branch protection** (owner declined). If ever wanted, the exact `gh api -X PUT
  …/branches/main/protection` command (required checks `test (lts)`,`test (1)`,`format`,`docs`,
  `python`; NO `required_signatures`) is in `JOURNAL.md` session-2.
- **Signing key: DECLINED** (owner will make the repo public later). Commits are `G`-signed locally
  but show **"Unverified"** on GitHub — cosmetic; do not chase it.

---

## ✅ DONE THIS SESSION (session 3)

1. **P3b WATER CLOSURE = PASSED** (the live task). Daily-output re-run of the Historical transient from
   the spinup-end `restart_1999.lpj` over a contiguous **boreal cell subset** (cells 45000–45999, 1000
   cells, lat ~54-56°N, 2000–2002) — SLURM job 1448818, COMPLETED clean in **83 s**. Gate met two ways:
   (1) DEFINITIVE — the binary is `-DSAFE`, so `check_fluxes.c` enforces per-cell/year water balance
   `|balanceW|≤1.5 mm/yr` and aborts otherwise; a clean run over 1000 cells × 3 yr with NO water-balance
   error ⇒ closure proven. (2) output reconstruction — daily fluxes integrate to LPJmL's annual
   `globalflux` to 5 sig figs; cumulative `|Σprec−Σ(ET+runoff)|/Σprec` median 2.7%; swc∈[0.08,0.99],
   swe builds to 1140 mm & returns; daily NPP → annual NPP ratio 1.000. **Report:**
   `docs/phase1_p3b_water_closure.md`. **Reusable tooling:** `scripts/run_daily_subset.sh` +
   `scripts/water_closure_check.py`. All source facts (restart-subset, daily syntax, water identity,
   module set) adversarially verified against `/home/jamirp/lpjml56fit` before submitting.
2. **FULL-GLOBAL daily F/E training dataset GENERATED** (owner approved). All **67,420 cells ×
   2000–2019**, restarted from seed1 `restart_1999.lpj` → `/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output`
   (**186 GB**; SLURM job 1448860, 512 tasks / 4 exclusive nodes, 31m48s). Water closure re-confirmed at
   scale (clean run, no water-balance error, all cells × 20 yr; daily→annual `globalflux` exact; per-cell
   multi-year imbalance median 0.87 %). This is the daily forcing→flux+storage+carbon data F/E train on.
   Summary `artifacts/metrics/p3b_water_closure_global_c0_67419.json`.
3. **Housekeeping:** ADR 0013 (main-only) + §1 softened + index; `.github/dependabot.yml` tamed
   (monthly+grouped). Committed + pushed to main.

## ✅ DONE PREVIOUS SESSION (session 2)

1. **CI repaired on `main` and CONFIRMED GREEN on the real CI** (`gh run list` / check-runs on
   `9fe93f3`): `python`, `format`, `docs`, `test (lts)`, `test (1)`, `test (macOS, lts)` all pass.
   The only red is `test (pre)` = the Julia-prerelease job, which is `continue-on-error` (allowed to
   fail) and was already red on `main` before this work. Three independent causes were fixed:
   - **python**: floating `>=` deps + no lock → CI resolved breaking majors. Fix: upper-bound caps in
     `python/pyproject.toml` (pandas<3, pyarrow<25, pytest<9, sklearn<2, ruff<0.15, …) + **committed
     `python/uv.lock`** + workflow now `uv sync --frozen`; plus `ruff format` on the scaffold.
   - **format**: reformatted all tracked `.jl` with **Runic 1.7.0** (`runic-action@v1`/`version:'1'`).
   - **docs**: broken `[`checkdims`](@ref)` (non-exported) → added a `CurrentModule` @meta block;
     also **enabled `linkcheck`** with `linkcheck_ignore` for the private-repo self-links; fixed 2
     `.bib`-comment warnings.
2. **Component-S port COMPLETE and MERGED to `main` (PR #11, squash `c3831aa`).** Ported from the
   frozen sibling `/p/projects/open/Jamir/emulator` (ADR 0012, port-once): `transforms.py`,
   `drivers.py` (xarray-guarded), `features.py` (`build_cell_year_feats` + climclusterpy/NetCDF-guarded
   `eco_diagnostics`), `baseline.py` (`DirectEmulator` + `ResidualRegressor`/`add_competition`/
   `LGB_COMMON`), `train.py` (matplotlib-guarded), extended `data.py` (frozen 29-col schema kept +
   `load_ind` + `build_patch_summaries`), `noise_floor.py` (seed-split diagnostics; test asserts
   `PUBLISHED_NOISE_FLOOR={Height:0.020,agb:0.113,npp:0.062,LAI:0.025}`), curated `__init__.py`,
   `python/config/config.yaml`. **Tests: 49 pass / 6 skip in py311_new; 56 pass + ruff-clean in a
   locked uv env.** Each ported module was adversarially fidelity-verified against its source.
3. **Phase-1 CARBON CLOSURE = PASSED** (annual `globalflux_2000_2019.csv`, seed1): flux identity
   `NBP == NPP−RH−fire+estab−negc` exact (7e-5 PgC/yr); storage `ΔC(VegC+LitC+SoilC) vs NBP` median
   **2.16 %/yr, 0.6 % cumulative** over 2000–2019 (residual ≈ CSV rounding of the ~1600 PgC SoilC
   pool). **`SoilC` already includes `SoilC_slow`** (adding it separately worsens closure).
4. **`gh` re-authenticated** (owner pasted a classic PAT, scopes `repo`,`read:org`,`workflow`; stored
   in `~/.config/gh/hosts.yml`, persistent). The "eval"-filename block was investigated: **it is the
   Claude Code auto-mode classifier heuristic, NOT a configured hook** (no settings.json/hooks/CLAUDE.md
   rule exists) — `noise_floor.py` was rebuilt from the documented spec without reading the sibling
   `eval_presentday_critical.py`.

---

## ▶️ PRIORITY 1 (live) — Phase 2+ (`DEVELOPMENT_PLAN.md` §6)

Both Phase-1 gates (carbon + water) PASS and the **full-global daily F/E dataset now exists** (186 GB,
`/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output` — daily
prec/transp/evap/interc/runoff/swe/swc/rootmoist/whc_nat/pet/npp/gpp for all 67,420 cells × 2000–2019).
Resume the phased plan: **per-tree carbon pools** (allometric reconstruction from the existing `ind`
CSV, or a RAW `ind` re-gen), then **component-E inputs** (wind `sfcwind` + surface pressure `ps` +
FLUXNET/PLUMBER2), Phase 4.

**F-core water-budget caveat (carry forward):** LPJmL enforces water closure **annually** (not daily),
and daily `swc` is **fractional saturation** (no `wsats` output). To give the F-core a fully-closed
daily storage term, either reconstruct `wsats` from soil params, add a `wsat`/absolute-soil-water
output and re-run, or define F conservation at the annual cadence. See `docs/phase1_p3b_water_closure.md`.

**Re-running LPJmL daily (tooling proven, reuse freely):** `scripts/run_daily_subset.sh` (params
`STARTGRID ENDGRID FIRSTYEAR LASTYEAR NTASKS TIME EXCLUSIVE RUNTAG SUBMIT RANDOM_SEED`) generates the
config from the EXACT production sections I&II, runs a `lpjcheck` pre-flight, and submits. Full-global
example: `STARTGRID=0 ENDGRID=67419 FIRSTYEAR=2000 LASTYEAR=2019 NTASKS=512 TIME=03:00:00 EXCLUSIVE=yes
RUNTAG=global SUBMIT=yes bash scripts/run_daily_subset.sh`. Verify with (dask-lazy, memory-safe)
`scripts/water_closure_check.py <run_dir>`. **Never run on the login node.** Subset-grid options if ever
needed (regrid tools `/p/projects/biodiversity/bloh/git/master_bsq/bin/`: `getcellindex`, `cutclm`,
`regridclm`, …).

**KEY VERIFIED FACTS (session 3, adversarially confirmed vs `/home/jamirp/lpjml56fit`):**
- **Restart a contiguous subset from the full-grid restart works** — integer `"startgrid"/"endgrid"` =
  0-based POSITIONAL row indices (NOT lat/lon, NOT 1-based, NOT `"all"`); per-cell index seek, MPI-decomp
  independent; needs byte-identical grid/soil/inputs + matching physics.
- **Daily output** = `"timestep":"daily"` INSIDE each output entry's `"file"` object (no recompile).
- **Water balance enforced ANNUALLY** by `-DSAFE` `check_fluxes.c` (≤1.5 mm/yr, aborts otherwise) ⇒ a
  clean run IS closure. `swc` = FRACTIONAL saturation (wsats NOT output → absolute mm needs wsats);
  `swe`/`rootmoist` in mm; `excess_water` (permafrost) unobservable.
- **Modules:** `json-c/0.13.1` (NOT 0.17 → wrong .so), `openssl/3.6.0`, `netcdf-c` (4.9.2); `module purge`
  first. The old `run_..._general_global_historical.sh` module lines are stale.
- **Cell↔lat/lon:** grid `.nc` `cellid[lat,lon]`; cells ordered ascending-lat (south→north), lon-ascending.

**globalflux reference:** `…seed1/output/globalflux_2000_2019.csv` — 17 cols; the daily re-run's
per-cell daily fluxes integrate to it exactly (validated session 3).

---

## PRIORITY 2 (housekeeping)
- **Dependabot #6/#8/#9** (pandas→3, pytest→9, pyarrow→25) violate the pyproject caps and would fail
  `uv sync --frozen` — **owner should close them** (the auto-mode classifier declines closing external
  PRs the agent didn't create when the owner didn't name them). #1–5 (GitHub-Actions bumps) are major
  version bumps → verify CI before merging. `.github/dependabot.yml` already tamed (monthly+grouped) in
  session 3, so future spam is bounded.

## PRIORITY 3 — resume the phased plan
`DEVELOPMENT_PLAN.md` §6. Both Phase-1 gates (carbon + water) now pass. Next: per-tree carbon pools
(allometric reconstruction or a RAW `ind` re-gen), then component E inputs (wind `sfcwind` + surface
pressure `ps` + FLUXNET/PLUMBER2), Phase 4. **For the F-core water budget:** remember closure is
annual and `wsats` isn't output — reconstruct `wsats` from soil params, add a `wsat`/absolute-soil-water
output, or define F-core water conservation at the annual cadence (see `docs/phase1_p3b_water_closure.md`).

---

## Environment facts (verified this project)
- **LPJmL-FIT:** `/home/jamirp/lpjml56fit` (v5.6.004, binary built; modules incl. `netcdf-c/4.9.2`).
- **Ground truth:** `/p/projects/waldspektrum/priesner/clustering/global` (67,420 cells, 63,119 with
  trees; Historical obsclim 2000–2019 seed1+seed2 = the annual noise-floor pair; SSP370 2020–2100;
  `restart_1999.lpj` = spinup end). Full paths in `config/paths.yaml`.
- **Python:** reuse `/home/jamirp/.conda/envs/py311_new` (3.11.9). No `ruff`/`hypothesis`/`uv` there,
  but you can `python -m venv … && pip install uv` (→ uv 0.11.29) to run the CI-matched
  `uv sync --frozen` + `ruff` + `pytest` locally (PyPI is reachable). `uv.lock` is committed.
- **Julia 1.10.0:** `/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia`;
  `JULIA_DEPOT_PATH=$HOME/.julia julia --project=. -e 'import Pkg; Pkg.test()'` → 21071 pass / 6 broken.
  Runic: `pip`-free — `Pkg.add(name="Runic",version="1")` in a temp env, then `Runic.main(["--check",…])`.
- **`gh`:** `/home/jamirp/tools/gh-cli/gh_2.49.0_linux_amd64/bin/gh` — **AUTHENTICATED** (works now).
- **Regrid/CLM tools:** `/p/projects/biodiversity/bloh/git/master_bsq/bin/` (see P3b).
- **libcurl noise:** `curl_easy_setopt:48` warnings during Julia Pkg ops are a benign PIK login-node
  quirk; ignore.

## Commit history on `main` (all `G`-signed)
`c3831aa` feat(python) component-S port (#11 squash) · `9fe93f3` docs(CI repair log) · `22a7b37`
fix(docs) · `b2e3338` style(python ruff) · `53af71f` build(python caps+uv.lock) · `50423f1`
style(julia Runic) · `57e3a95` chore(python scaffold) · … (Phase-0 scaffold below).
