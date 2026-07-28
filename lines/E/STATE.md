# LINE E — Component E vs observations (branch `line/E`, worktree `wt-E`) — P2

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/E/JOURNAL.md` (append-only). Decisions: ADR block **0070–0079**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**E6 — diagnose the NOCTURNAL H failure. This is now the single thing holding Component E back.**
E1, E2 and E4-Experiment-A are DONE (ADR 0070 / 0071 / 0072). The P2 gate ran over 497 936 tower half-hours:
`Rn` is verified (R² 0.986–0.996), `T_skin` is verified where observable (daily RMSE 1.4–2.0 K, R² 0.76–0.95),
and `H`'s **mean** is inside PLUMBER2's own band (76.4 % of DE-Hai daily means) — but **nocturnal H has R²
−1.0…−5.6 at every site**, and the closure runs **1–2 K too cold at night**. Everything needed to work on it is
already staged; do this before adding sites, more experiments, or any retune.

**Start with `residual-diagnosis` (this is exactly its case).** State the reference basis and a falsifiable
hypothesis first, then test. The three candidate mechanisms, in the order the evidence supports:

1. **The stability form, not its coefficient.** The sweep is **monotone in `stab_amp` up to 0.9** at both sites
   (night RMSE 37.0 → 36.1 DE-Hai, 29.7 → 24.2 AU-ASM), i.e. the optimum is at the parameter's bound — a
   bounded `1 − amp·tanh(k·Ri/2)` surrogate cannot suppress stable-layer exchange by the 1–2 orders real
   Monin–Obukhov does (`SEBParams`' own comment admits this). Test whether a genuine ψ-function (or a larger
   bound) removes the night bias *without* breaking the `|T_skin − Tair| < 25/30 K` coupled/biome gates that
   the 0.25 floor currently protects. Falsifiable: if the night bias is a `g_a` problem, forcing `g_a` from the
   tower's **measured `u*`** (`ustar` is in the half-hourly parquet — E1) should collapse the nocturnal error.
   **Run that first: it separates "wrong g_a" from "wrong G / wrong radiative loss" in one experiment.**
2. **The ground-heat term.** `G = lambda_g·(T_skin − T_soil)` with `lambda_g = 7.0` W/m²/K and a τ = 30 d EWMA
   `t_soil` is the crudest part of the closure, and at night G is what should limit the surface's cooling. The
   towers measure `g` (`Qg`, `positive INTO ground` at 7 of 8 sites) — score modelled vs observed G directly,
   day and night, before touching `lambda_g`.
3. **Emissivity / longwave.** Less likely: `Rn` already verifies to R² ≥ 0.986, so the radiative terms are
   right in aggregate.

Constraints while doing this: **opt-in, default byte-identical** (guardrail 4) — the P2 numbers in ADR 0072 are
the pre-fix baseline and the new testitem *pins the night-bias sign*, so a genuine fix will trip that assertion:
update the test and **supersede ADR 0072** in the same change. Any default flip (`stab_amp`, `lambda_g`,
`enable_stability`) moves the coupled/biome baselines ⇒ **integration point with line M**, already raised in
`lines/M/STATE.md`.

**Then, in order:** E4-**Experiment B** (F's LE → E, the coupled number; its difference from A *is* F's ET
error) · **E5** (feed the E2 wind/psurf to M's driver) · **E4b** (T_skin at Hainich from ICOS `LW_OUT`) ·
**AU-Rob** is a suspect site (tower closure slope 0.599, H R² ≈ 0 even by day) — diagnose or drop it, don't let
it dilute a mean.

## The E4 Experiment-A pipeline (rerun in two commands)

```bash
/home/jamirp/.conda/envs/py311_new/bin/python3 scripts/build_e_seb_validation_table.py   # tower-forced tables
STAB_SWEEP=1 scripts/sbatch_julia.sh E-e4a --project=. scripts/validate_e_seb_vs_plumber2.jl
# report: <energy_reference>/derived/seb_validation/e4_experimentA_report.txt
```
`SITES=` / `YEARS=` subset either step. The conventions that make it honest — the tower's own albedo, `z_ref` =
the site's **measurement** height, `t_soil` as a τ=30 d EWMA of **daily-mean** Tair (a per-step EWMA at 30 min
decays ~48× too fast) — are documented in the two scripts' headers; don't re-derive them.

## Still-open design notes carried forward

- **Experiment B (coupled)** — F's LE → E, scored exactly as A was. The A−B difference **is** F's ET error; that
  attribution is the point, so run B only after A's numbers are the reference (they now are: ADR 0072).
- **Score tower fluxes with TOWER forcing** (E2's lesson): the 0.5° cell at Hainich is −10.1 % in wind and
  +1649 Pa in pressure. Use the E2 `wind_psurf_<biome>.csv` fixtures for model-grid runs instead.
- **E3 (sublimation-λ split) is NOT an E-only change — integration point with M.** The λ multiplication happens
  in `src/components/fast.jl` (F core, M-owned), the ET sum there has no snow/ice component to split, and
  `FToE` (`src/interface.jl`, M-owned) carries no snow mass or fraction — `energy.jl` cannot see which part of
  `le` left snow. Raised in `lines/M/STATE.md`; guessing a snow fraction inside E would be invented physics.

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- `src/components/energy.jl`, `test/testitems/energy_closure_tests.jl`
- the energy / `sfcwind` / `ps` keys in `config/paths.yaml`
- new `scripts/` for the remap + the PLUMBER2 validation (name them clearly, e.g. `remap_*`, `validate_e_*`)
- `lines/E/*`, `changelog.d/E-*.md`, ADRs 0070–0079

**Do NOT touch:** `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` (line S) · `src/run.jl`,
`src/interface.jl` (line M owns the coupling seam — request changes through M) · `ext/` (line O) ·
`Project.toml` (integrator; a NetCDF reader belongs in the **Python/script** env or a weakdep, never runtime
`[deps]` — ADR 0014).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside `# ── line E ──`), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `E-` · other lines' `/p/tmp` artifacts are **read-only**.

## The contract you must not silently break (E → M)

Line M runs your closure inside the coupled loop: the `SEBEnergyClosure(...)` constructor + the `solve!`
signature are **frozen**. New physics is **opt-in, default byte-identical** (guardrail 4) — the coupled/biome
baselines and `energy_closure_tests.jl` must not move until a change is deliberately enabled, and flipping a
default is an integration point with M.

## The E4 recipe (everything the P2 gate needs from observations is already staged)

Reference data (ADR 0070; `config/paths.yaml` `data.energy_reference*`, 300 MB on `/p/tmp`, git-untracked):

| what | where |
|---|---|
| raw NetCDF, 9 sites | `…/fluxnet_plumber2/{Flux,Met}/<stem>_{Flux,Met}.nc` + `manifest.json` (sha256 per file) |
| model-facing tables | `…/fluxnet_plumber2/derived/{halfhourly,daily,diurnal}_<site>.parquet` |
| the sanity report | `…/derived/plumber2_sanity_report.txt`, `site_summary.csv` (also `lines/E/data/plumber2_site_summary.csv` in git) |
| re-stage / re-report | `scripts/fetch_plumber2_sites.py` → `scripts/validate_e_plumber2_load.py` (skill: `plumber2-reference`) |

Rules the first-look report already established — follow them instead of re-deriving:

- **Score against `Qle_cor`/`Qh_cor` and quote the uncorrected numbers too.** Uncorrected closure slopes are
  0.60–0.88; corrected 0.87–1.02. A model that closes energy exactly cannot match an unclosed observation.
- **The acceptance band is the dataset's own** `le_cor_uc`/`h_cor_uc` (daytime mean at DE-Hai: LE ±50.1,
  H ±56.6 W/m²) — **present only on the 4 FLUXNET2015 sites**, not on the OzFlux ones.
- **Filter days with `daily_ok`** (≥5/6 of the day's steps present for both LE and H) and always report `n`:
  jointly-valid coverage is 76.9 % DE-Hai, 55.6 % FR-Pue, **39.1 % FI-Hyy**.
- **Pairing hazards:** PLUMBER2 is a **leap** calendar (drop 29 Feb before pairing with noleap-365 model
  output) and its time axis is **local standard time** (verified via the mean-diurnal `SWdown` peak, 11.0–12.5 h
  at all 9 sites). AU-Tum is **hourly**, the rest half-hourly.
- **T_skin only at AU-Tum / AU-ASM / AU-Rob** (OzFlux `LWup`, inverted at ε = 0.97 — see below); **AU-How is
  suspect** (daytime `T_skin − Tair` = −1.85 K) and boreal T_skin has no source at all.
- Observed daytime Bowen, for the biome-ordering anchor: GF-Guy 0.30 < AU-Rob 0.52 ≈ AU-How 0.54 < AU-Tum 0.80
  < DE-Hai 0.96 < FI-Hyy 1.23 < FR-Pue 1.70 < US-SRM 3.31 < AU-ASM 4.57.
- **Open signal to chase in E4 (not yet a finding):** observed DE-Hai **JJA daytime Bowen is 0.64**, whereas the
  coupled Hainich decade reports a non-drought summer Bowen of ~0.2 (drought 2018: 0.89). Definitions differ
  (daytime Σ H/Σ LE here vs the coupled test's summer aggregate), so **make the definitions identical before
  concluding anything** — the honest first step of the comparison, per the `residual-diagnosis` skill.

## The model-grid wind/psurf (E2 output — what E4/E5 drive with)

| what | where |
|---|---|
| source (both vars, daily, 0.5°, obsclim GSWP3-W5E5) | `config/paths.yaml` `lpjml.energy_extra_inputs.{sfcwind,ps}` |
| per-cell fixtures, 2010–2019 × 365 d | `test/testitems/references/wind_psurf_<biome>.csv` (`year,doy,wind,psurf`) |
| remap + the 4-part gate | `scripts/remap_wind_psurf_cells.py` (skill: `obsclim-cell-remap`; ADR 0071) |

2010–2019 means — wind [m/s] / psurf [Pa]: boreal_siberia 2.868 / 96 718 · temperate_hainich 3.220 / 97 548 ·
mediterranean_iberia 2.590 / 93 868 · semiarid_sahel 3.246 / 97 135 · tropical_amazon 1.490 / 100 638.
**Open:** SSP370 `ps` does not exist in the raw GCM set ⇒ the future branch of E stays on a fixed pressure.

## Status (2026-07-28)

- **E4 Experiment A DONE — the P2 gate has run** (ADR 0072): `Rn` R² 0.986–0.996 · `T_skin` daily RMSE
  1.41–1.97 K / R² 0.76–0.95 (3 OzFlux sites) · `H` bias +6.4…−19.2 W/m² with **76.4 %** of DE-Hai daily means
  inside PLUMBER2's own band, but daily R² 0.125–0.778 and **nocturnal R² −1.0…−5.6**. Frozen as a CI regression
  test with two committed fixtures. `MEMORY.md`'s `[ASSUMPTION]` on E is now a quantified `[VERIFIED]`.

- **E1 DONE** — PLUMBER2 v1-0 staged, loaded and sanity-checked at 9 sites; `config/paths.yaml`
  `data.energy_reference` is a resolved path, not a TODO (ADR 0070; `lines/E/JOURNAL.md` 2026-07-28).
- **E2 DONE** — daily wind + psurf remapped onto the 5 orderA biome cells from obsclim GSWP3-W5E5, with the
  lat/lon ↔ orderA mapping **proven** by a `tas` round-trip against `temperature_test.clm` (`max|Δ| = 0.000 °C`,
  all 5 cells) and cross-checked against the DE-Hai tower (ADR 0071; job `E-windps` 1617515).
- `SEBEnergyClosure` (self-contained, ADR 0017 — no Terrarium runtime dep) closes `Rn = LE + H + G` to
  **1.4e-14 W/m²** (13,824 cases; ForwardDiff-vs-FD; Float32 clean), H as the residual.
- Monin–Obukhov `g_a` stability correction is **ON by default**; the aerodynamic identity checks to ~3e-11.
- Emergent behaviour is climate-correct: Bowen ordering across 5 biomes (tropical ~0.10 → semi-arid
  H-dominated), and the coupled Hainich decade reproduces the **2018 drought** (summer Bowen 0.89 vs ~0.2).
- **Not done:** no observational validation *yet* — but both prerequisites now exist (PLUMBER2 reference E1,
  model-grid wind/psurf E2), so **E4 is unblocked on the data side**. The coupled driver still uses the
  constant wind/psurf until the E5 integration point with M lands.
- Honest scope currently recorded: wind is held **constant** and psurf is effectively fixed (the LPJmL run
  never used them — `photosynthesis.c` hard-codes `p=1e5`), and LE uses the **vaporization** λ for all ET
  (no snow-sublimation split).

## Milestones

- **E1** ✅ **DONE 2026-07-28** — PLUMBER2 v1-0, 9 sites, staged + loaded + sanity-checked; `paths.yaml` filled
  (ADR 0070). Finding that reshapes E4: **T_skin is not observable at Hainich** (no `LWup` in the
  FLUXNET2015-sourced files) ⇒ T_skin is validated at the OzFlux sites, biome-analogously.
- **E2** ✅ **DONE 2026-07-28** — wind + psurf from ISIMIP3a obsclim GSWP3-W5E5 (same family as the run's own
  forcing; the raw SSP370 GCM set has **no `ps`**), remapped onto orderA cells, all four gate checks PASS at all
  5 biome cells (ADR 0071). Committed fixtures `wind_psurf_<biome>.csv`; `paths.yaml` keys filled.
- **E3** **Sublimation-λ split — RE-SCOPED 2026-07-28 to an integration point with M** (not E-only: the λ
  multiplication lives in `components/fast.jl` and `FToE` has no snow field — see NEXT above) — use `LAMBDA_SUBLIMATION` when the flux leaves snow/ice rather than
  vaporization for everything (`conservation.jl` already exports both constants). Opt-in, default
  byte-identical.
- **E4** ✅ **Experiment A DONE 2026-07-28** (ADR 0072) — 497 936 tower steps, 4 sites: `Rn` VERIFIED
  (R² 0.986–0.996), `T_skin` VERIFIED where observable (daily RMSE 1.4–2.0 K), `H` verified in the MEAN only
  (76.4 % of DE-Hai daily means inside the band) with **nocturnal H the named failure mode**. Experiment B
  (coupled, F's LE) still open. Original wording: **Validate LE / H / T_skin within PLUMBER2 error bands** at ≥1 site, plus the diurnal cycle, with real
  wind + psurf from E2. Per `DEVELOPMENT_PLAN` §7: **H is the residual and PLUMBER2 flags it as the hardest
  flux to get right — validate it hardest.** *This is the P2 gate.* Then flip `MEMORY.md`'s `[ASSUMPTION]` to
  `[VERIFIED]` with the site + bands quoted. Recipe + the bands/hazards: "The E4 recipe" above. **Split gate**
  (ADR 0070): LE/H/Rn/Bowen at DE-Hai + the biome set; T_skin at AU-Tum/AU-ASM/AU-Rob only.
- **E4b** *(new, optional)* close the **T_skin-at-Hainich** gap from a second source — ICOS `LW_OUT` for DE-Hai
  (`data.icos-cp.eu` is reachable from the login node) or satellite LST — since PLUMBER2 cannot supply it.
- **E5** Feed the real wind/psurf back to line M as an **integration point** — the coupled driver builds
  `AtmForcing` in `src/run.jl`, which **M owns**, so E supplies `wind_psurf_<biome>.csv` + ADR 0071 and the
  driver change lands on M's side, both together. Recorded in `lines/M/STATE.md` too. Then record the
  improvement (the coupled Hainich decade currently runs on a constant wind, so its Bowen/2018-drought numbers
  will move — that is expected, not a regression, and it is a deliberate baseline change).

## Line-local gotchas

- **Parse the `.clm` header, never assume the layout** — v3 (`LPJCLIM`, 7 ints + 3 floats + datatype,
  HDR=51, float32) vs v2 (no datatype field, HDR=43, **int16 with `scalar 0.1` ⇒ °C×10**). Reuse
  `scripts/build_transient_boundary.py::open_clm`; that function already handles both.
- `AtmForcing.tair` is **Kelvin**; F converts with `tair − 273.15`. PLUMBER2 `Tair` is also K — **verified**
  (200–335 K band, all 9 sites inside).
- **`Qle_cor`/`Qh_cor` can be ≈0 GARBAGE rather than a fill value.** At DE-Hai the uncorrected `le` is all-NaN
  for **2010–2012** (that is where the site's 23.1 % missing LE sits) and PLUMBER2's energy-balance correction
  emitted **≈0** there — annual mean `le_cor` 0.39 / −0.09 / 0.04 W/m² against 30–40 W/m² in 2000–2009 — while
  `h_cor_uc` disappears. A finiteness filter passes 36 550 rows of that, and feeding the closure LE ≈ 0 pushes
  all the available energy into H (it inflated DE-Hai's H bias to +39.8 W/m² before it was caught). **Always
  require the UNCORRECTED `le` to be finite as well**; `scripts/build_e_seb_validation_table.py` does. The other
  three staged sites are clean. This is also why a P2 fixture must be sampled **across years**, not from one year.
- **PLUMBER2 `_FillValue = -9999` leaks through `np.asarray()`** — netCDF4 returns a *masked* array and
  `np.asarray` drops the mask, so the fill enters as data (DE-Hai mean LE read −2283 W/m² instead of +32.2).
  Always `np.ma.filled(x, np.nan)`; `scripts/validate_e_plumber2_load.py::_series` is the reference reader.
  Related: in the PLUMBER2 **Flux** files a `*_qc == 5` flag marks data left **MISSING**, not gap-filled
  (verified at DE-Hai: all 52 608 flag-5 rows are fill rows, matching the variable's `Missing_%: 23.1`).
- `swc` output from the C run is **fractional** saturation, not mm (`swe`/`rootmoist` are mm).
- The 5-biome test tolerates LE ≥ −2 W/m² (a bounded smooth-min undershoot in the fully water-depleted corner,
  not a sign bug) — don't "fix" that by changing the physics without reading the comment.
- **`.clm` v3 datatype codes are 0-BASED** (`0=byte 1=short 2=int 3=float 4=double`). A 1-based map reads
  `temperature_test.clm`'s float32 as int32 and reports ~5.9e8 "°C" — it looks like a broken cell mapping when
  it is a broken reader. `scripts/remap_wind_psurf_cells.py::read_test_clm_year` is the correct minimal reader.
- **The LPJmL-prepared obsclim wind is quantized to 0.01 m/s** (`int16·0.01` in the `.clm`), so a raw
  `max|Δ| ≈ 5e-3 m/s` against a full-precision source is ½ a quantization step, not a bug.
- **Never `git stash -u` while a SLURM job is writing fixtures into this worktree** — the stash pulls the
  files out from under the running job.
- Any long job → SLURM (`scripts/sbatch_python.sh` / `sbatch_julia.sh`); the login node is hook-blocked.
