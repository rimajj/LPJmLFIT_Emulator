# HANDOFF — Next-Session Takeover Prompt

**Read this first, then `MEMORY.md` (durable facts) and the tail of `JOURNAL.md` (narrative).**
You are continuing an in-progress build of an ESM-ready LPJmL-FIT hybrid land component (S = slow ML
distribution emulator, F = fast physical core kept, E = new energy balance). Phase 0 DESIGN is frozen
and on `main`. Two big things are now DONE (CI repair + the component-S port); the live work is
**Phase 1 data generation (P3b: the daily-output re-run + water closure)**.

Repo: `/p/projects/open/Jamir/esm_land_emulator` → remote `git@github-esm:rimajj/LPJmLFIT_Emulator.git`
(SSH alias `github-esm`, deploy key `~/.ssh/esm_land_emulator_deploy`; **push works with NO manual auth**).
**`main` HEAD = `c3831aa`** (local + remote in sync).

---

## ⚙️ WORKFLOW CHANGE (owner decision, session 2) — WORK ON `main` DIRECTLY

The owner switched away from the trunk-based + short-lived-branches + PR-per-change model. **Going
forward: commit and push straight to `main`. No feature branches, no PRs, no branch protection.**
- CI still runs on every push to `main` (workflows trigger on `push: main`), so you keep the test
  signal — it's now a **smoke alarm** (tells you after) not a **gate** (blocks before). If a push
  turns `main` red, fix forward.
- This is a deliberate relaxation of `ENGINEERING_STANDARDS.md` §0/§1 (which mandated PRs + branch
  protection as the "hard gate" for AI code). **TODO: record it** — add a short ADR (e.g.
  `docs/decisions/0013-main-only-workflow.md`) and soften the §1 wording, so the docs match reality.
- Practical upside: no more force-pushes (no rebasing) and no branch-protection mutations → the
  auto-mode permission classifier stops prompting for those.
- **Do NOT set branch protection** (owner declined). If ever wanted, the exact `gh api -X PUT
  …/branches/main/protection` command (required checks `test (lts)`,`test (1)`,`format`,`docs`,
  `python`; NO `required_signatures`) is in `JOURNAL.md` session-2.
- **Signing key: DECLINED** (owner will make the repo public later). Commits are `G`-signed locally
  but show **"Unverified"** on GitHub — cosmetic; do not chase it.

---

## ✅ DONE THIS SESSION (session 2)

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

## ▶️ PRIORITY 1 (live) — P3b: daily-output re-run → WATER CLOSURE (+ daily carbon)

**Goal:** enable **daily output**, re-run the Historical transient **2000–2019 restarting from
`restart_1999.lpj` (spinup end — NOT `restart_2019.lpj`)**, then verify **water closure** and re-check
carbon at daily resolution.

**OWNER GUIDANCE (session 2) — pick one; do NOT use the clustering pipeline for now:**
- **(a) Just run the whole global script** — full 67,420-cell grid, **~1–2 h on 2048 cores**. Simplest;
  produces full-global daily output (bounded by choosing few daily vars + short write window if needed).
- **(b)** Run individual biome cells or small **boxes** of cells as separate single jobs (contiguous
  `startgrid`/`endgrid` index ranges).
- **(c)** Regrid the climate + soil inputs onto a **new grid containing only the wanted cells**.

**Regrid / CLM toolkit (owner-provided, VERIFIED present):** `/p/projects/biodiversity/bloh/git/master_bsq/bin/`
— `getcellindex` (lat/lon → cell index), `cutclm`, `regridclm`, `regridlpj`, `cdf2clm`, `clm2cdf`,
`catclm`, `mergeclm`, `joingrid`, `pasteclm`, `printclm`, `mathclm`, `cru2clm`, `cdf2grid`, `arr2clm`, …
Use these to build subset `.clm`/`.grid`/`.bin` inputs for options (b)/(c).

**HOW to enable daily output (VERIFIED, no recompile):** add `"timestep":"daily"` to the chosen
outputs in the transient `lpjml_*.js` output list. For water closure add daily **transp, evap, interc,
runoff, prec, pet** and the **layer soil water `swc`** (+ `npp`,`gpp` for sub-annual carbon). The run
script's `//#define DAILY_OUTPUT` (line ~140) is the compile-time alternative (commented).

**Restart wiring:** the transient phase already runs `FROM_RESTART` with `"nspinup":0` (script line
~333) reading the spinup restart — point it at the EXISTING
`…/transient_2000_2019_npatch25_nspinup1000_nspinyear30_random_seed1/restart/restart_1999.lpj`
(path in `config/paths.yaml`), so you **skip the 1000-yr spinup**.

**Run script:** `/home/jamirp/scripts/clustering/global/bash_run_model/run_spinup_transient_ground_truth_general_global_historical.sh`
(auto-generates `input_*.js`+`lpjml_*.js`+SLURM `.jcf` and submits). Cell domain: `"startgrid":"all"`
(line ~312) or a contiguous `startgrid`/`endgrid` range (line ~313). SLURM: `--qos=short`/`--exclusive`,
account `waldspektrum`, `--ntasks` up to 2048. **Never run on the login node.** Daily outputs →
`/p/tmp/jamirp/esm_land_daily` (paths.yaml `paths.daily_output_run_root`).

**Water-closure gate (after the run):** per cell/day, `prec == transp + evap + interc + runoff +
Δsoilwater (+ snow)`. Also re-run the carbon check at daily resolution (annual already passed).

**globalflux reference (already analysed):** `…seed1/output/globalflux_2000_2019.csv` — 17 cols
`Year,NEP,GPP,NPP,RH,estab,negc_fluxes,fire,NBP,transp,evap,interc,prec,SoilC,SoilC_slow,LitC,VegC`
(fluxes 1e15 gC/yr, pools 1e15 gC).

---

## PRIORITY 2 (housekeeping)
- **Dependabot: 8 open PRs (#1–9).** Several are now **obsolete** because their bumps violate the new
  caps (pandas→3 #6, pyarrow→25 #9, pytest→9 #8) — they'd fail `uv sync --frozen`. Safe to **close**
  those three; the GitHub-Actions bumps (#1–5: setup-julia, codecov, setup-uv, checkout, cache) can be
  reviewed/merged normally. Consider taming `.github/dependabot.yml` (monthly + grouped) to stop the
  branch spam the owner noticed. (Earlier "do NOT touch #1–10" is superseded now that caps are in.)
- Add the **ADR + standards edit** for the main-only workflow (see WORKFLOW CHANGE above).

## PRIORITY 3 — resume the phased plan
`DEVELOPMENT_PLAN.md` §6. After Phase 1 gates pass: per-tree carbon pools (allometric reconstruction
or a RAW `ind` re-gen), then component E inputs (wind `sfcwind` + surface pressure `ps` + FLUXNET/
PLUMBER2), Phase 4.

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
