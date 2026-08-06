# LINE E — Component E vs observations (branch `line/E`, worktree `wt-E`) — P2

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/E/JOURNAL.md` (append-only). Decisions: ADR block **0070–0079**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**E7b is DONE (ADR 0075): the two-layer prognostic ground-heat column is now the PACKAGE DEFAULT.** Line M's
pre-registered ask (ADR 0058 §5) is ANSWERED and the repo no longer runs two ground-heat schemes in different
gates. **Nothing is owed to M any more; the reply is recorded in `lines/M/STATE.md`.** The next action is
E4-Experiment B.

E1, E2, E4-A, E6, E7 and E7b are done (ADR 0070 / 0071 / 0072 / 0073 / 0074 / 0075). **E8 (canopy heat
storage) is still open** — it is the remaining physical term, not this flip.

**What ADR 0075 settled, so you do not reopen it:**
- `SEBParams.enable_two_layer` defaults to **`true`**. Guardrail 4 is served by the **OPT-OUT** —
  `enable_two_layer = false` reproduces the pre-E7 closure exactly — and `lambda_g` / `tau_soil` are now
  **inert under the default**. Any probe arm that wants the pre-E7 closure must pass `false` EXPLICITLY.
- **The pre-registered criterion FAILED at AU-Rob** (daily H R² 0.069 → −0.176) and the flip proceeded on
  grounds published *before* the measurement: ADR 0073 already excluded that tower from scoring H
  (`ε_obs` −47.5 W/m²), the fitted `λ_g = 1.0` arm fails there too (−0.172 ⇒ the site does not discriminate),
  and its pre-E7 "skill" coexists with G R² −4.02 at 2.4× the observed sd(G). Do not re-litigate; if you ever
  need to, ADR 0075 §1 carries all four grounds.
- **The flip moved NOTHING outside `energy_closure_tests.jl`** — full suite 111 227 pass / 3 fail with only
  the default flipped, all three the assertions ADR 0075 re-pins. `solve_seb` never reads the flag, so every
  STATELESS caller (E's committed P2 tower gate included) is scheme-independent **by construction**.
- **ADR 0074 §6's sub-daily `T_skin` cost is at `z1 = 0.2 m`, NOT at the shipped 0.75 m default.** Corrected
  numbers are ADR 0075 §4: at 0.75 m the sub-daily R² is AU-ASM 0.908, AU-Tum 0.547, AU-Rob **−0.116** (the
  earlier 0.945 / 0.667 / 0.166 are the 0.2 m arm). **Daily** `T_skin` — the operational step — is where the
  decision lived and the cost is small: 0.981 → 0.979, 0.900 → 0.851, 0.858 → 0.793.
- **Cause of that mis-attribution, now a skill trap** (`plumber2-reference` TRAP 3): the probe's `z1 = 0.2 m`
  control arm omitted `z_soil1` and silently tracked the package default, so it stopped being a control the
  moment the default moved. **Two arms differing by a parameter must never print identical numbers** — if they
  do, one is not running what its label says. Report `_v6` is the corrected one; `_v5` is wrong sub-daily.

**CI/merge status — nothing is outstanding.** ADR 0075 shipped as `8d3df15e`; branch CI green on every
required gate (`format`, `test (lts)`, `test (1)`, plus non-required `test (macOS, lts)`). Merged to `main` as
**`3ae2be10`**, whose own post-merge run is green on `format`, **`docs`** (the gate that never runs on a
branch), `test (lts)`, `test (1)` and `test (macOS, lts)`. `test (pre)` is red for the **diagnosed** prerelease
reason — `MethodError: no method matching setindex!(::Base.ScopedValues.ScopedValue{Bool}, ::Bool)` at LOAD
time, pulled from the job log, with zero mentions of any file this line touched. Do not chase it.
Local CI-faithful suite before the push: **111 237 pass / 0 fail** (job 1717243).

**Do not redo any of these three — all measured and closed:**
- **`stab_amp` / `g_a`** — refuted (ADR 0073): modelled nocturnal `g_a` within **0.7 %** of DE-Hai's
  measured-`u*` value, substituting the measurement makes night H worse at all 4 sites, a 100× bracket never
  reaches positive nocturnal R².
- **`λ_g = 1.0`** — superseded (ADR 0074). It works, but `enable_two_layer = true` beats it on daily H
  (0.645 vs 0.637 DE-Hai; 0.775 vs 0.745 AU-ASM) *and* on `G` (0.717 vs 0.657; 0.614 vs 0.477), and only the
  two-layer form has a diurnal soil wave. ⚠ **This bullet's old warning — "E must not flip either default, it
  moves every coupled/biome baseline, M lands it" — was measurably WRONG on both halves and is retired
  (ADR 0075).** It moves nothing outside E's own gate file, and E flipped it. `λ_g = 1.0` is now reachable only
  through the `enable_two_layer = false` opt-out, i.e. purely historical.
- **Nocturnal H R² > 0** — still not reachable, now confirmed *with* the better scheme (DE-Hai night H R²
  −1.019 → **−0.324**; RMSE 37.0 → 29.96, bias 14.04 → 3.74). `ε_obs` scatter alone (sd 36 W/m² at DE-Hai)
  is the size of the night H RMSE. The remaining physical term is **canopy heat storage**, not a tune.

**New open items E7 created (all optional, none blocking):**
- **`z_soil1` is surface-dependent.** 0.75 m suits closed canopies; AU-ASM (sparse mulga, observed all-hours
  sd(`G_o`) = **64 W/m²**) wants far thinner. Making `z1`/`C` a function of vegetation would be an **S→E**
  question — `SToE` already carries `lai`/`height`.
- **`theta_soil` is a constant 0.5** because the frozen `FToE` carries no soil moisture ⇒ E→M ask, recorded.
- **Sub-daily `T_skin` degrades at AU-Tum/AU-Rob** with the scheme on — at the SHIPPED `z1 = 0.75 m`,
  R² **0.773 → 0.547** and **0.385 → −0.116** (ADR 0075 §4; the 0.667 / 0.166 this bullet used to quote are
  the `z1 = 0.2 m` arm, which is not the default). Interpretable (`T_skin` does not need the tower to close),
  and the **daily** step is far flatter (0.900 → 0.851, 0.858 → 0.793), so re-measure when canopy heat storage
  lands. This is the one metric the default flip demonstrably costs.

**Then, in order:**
- **E4-Experiment B** (F's LE → E, the coupled number; the A−B difference *is* F's ET error). Score H at
  **DE-Hai and AU-ASM only** — ADR 0073 showed AU-Tum/AU-Rob cannot score a closing model's nocturnal H
  (`ε_obs` −62.3 / −47.5 W/m²); they stay valid for `T_skin`.
- **E5** — feed the E2 wind/psurf to M's driver (`AtmForcing` is built in `src/run.jl`, M-owned).
- **E4b** — T_skin at Hainich from ICOS `LW_OUT` (PLUMBER2 cannot supply it).
- **AU-Rob:** no longer just "suspect" — quantified. Its tower's nocturnal budget misses by −47.5 W/m² and its
  two `λ_g` targets disagree 1.46 vs 19.92. Keep it for `T_skin`, exclude it from H means.

**3. Known capture gap (small, worth closing):** the committed fixtures
`test/testitems/references/e4_seb_drive_{DE-Hai,AU-ASM}.csv` have **no generator script** — they were made ad
hoc ("every 12th day of year × every 3rd hour", recorded only in a test comment). Write
`scripts/build_e_seb_fixture.py`, verify it reproduces the existing columns byte-identically, and add `g_obs`
so the ADR 0073 decomposition can be gated on the fixture too (today only the synthetic lever-ranking testitem
guards it).

**Status of the old "do NOT chase" note:** the two-layer half of it is now **built and measured** (ADR 0074) —
the diurnal `G` wave exists and is correctly scaled at closed canopies (DE-Hai all-hours sd(G) 5.75 vs
observed 5.66, against the default's 34.7) and night `G` R² is **positive (+0.394)**. What remains unreachable
is nocturnal **H** R² > 0, bounded by `ε_obs`; the outstanding physical term is **canopy heat storage**. Line
O's blocker is therefore reduced, not removed.

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

## Status (2026-08-05)

- **E7 DONE — the design change ADR 0073 deferred is BUILT, opt-in, and measured** (ADR 0074).
  `SEBParams.enable_two_layer` (**default `true` since ADR 0075**; it shipped `false` here) replaces
  `G = λ_g(T_skin − t_soil)` with `G = κ_g(T_skin − T1)`, `κ_g = 2λ_soil/z1`, over a prognostic two-layer soil
  column — an **independent implementation** of the MITgcm land-package formulation, cross-read against
  SpeedyWeather's `LandBucketTemperature` and Terrarium's half-cell skin temperature (no code copied, no
  dependency; ADR 0017 intact). It **beats the fitted `λ_g = 1.0`** at the two sites whose towers can score H:
  daily H R² 0.645 / 0.775 (vs 0.637 / 0.745) and daily G R² 0.717 / 0.614 (vs 0.657 / 0.477) at
  DE-Hai / AU-ASM. Sub-daily night `G` R² **+0.394** at DE-Hai. `Rn` preserved within ±0.005. No secular drift
  (16-yr trend −0.059 K/yr; ⟨G⟩ → 0 self-equilibrates, so no deep-restore term is needed).
  **Key gotcha found:** MITgcm's `z1 = 0.2 m` is for a minute-scale model and is **under-resolved at a daily
  step** (`dt·rate` = 1.125 ⇒ `G` degenerates into a day-to-day difference of `T_skin`, daily G R² −2.8);
  default is `z1 = 0.75 m` (`dt·rate` 0.093), chosen on that resolution criterion inside a broad optimum.
  Probe `scripts/e_two_layer_probe.jl`; report `<energy_reference>/derived/seb_validation/e7_two_layer_probe_v5.txt`;
  jobs `E-e7probe` 1705681 … `E-e7final` 1705886.
- **Doc fix:** `docs/src/explanation/architecture.md` had claimed since Phase 4 that E *reuses* Terrarium.jl's
  `SurfaceEnergyBalance`. ADR 0017 superseded that on 2026-07-22 — corrected, and the four citation surfaces
  (register / `CITATION.cff` / `refs.bib` / source header) now agree and name MITgcm as the implemented method.
- **E6 DONE — the nocturnal-H failure is DIAGNOSED** (ADR 0073, supersedes ADR 0072 items 4 + 6). It is a
  ground-heat **timescale** error, not an aerodynamic one. Because `H` is the exact residual `Rn_m − LE − G_m`,
  `ΔH = ΔRn − ΔG + ε_obs` *identically* and `g_a` is in none of those terms. Measured: modelled nocturnal `g_a`
  within **0.7 %** of DE-Hai's measured-`u*` value; substituting the measurement makes night H worse at all 4
  sites; a 100× `g_a` bracket never reaches positive nocturnal R². Meanwhile sd(`G_m`) is **5–7×** sd(`G_o`) at
  the forest sites and **88 %** of DE-Hai's night H bias is `ΔG`. At the daily step `run.jl:93` actually runs,
  three independent lines give **`λ_g ≈ 1.0`, not 7.0** (daily H R² 0.03 → 0.64 DE-Hai, 0.33 → 0.74 AU-ASM).
  Also established: `ε_obs` = **−62.3 / −47.5** W/m² at AU-Tum / AU-Rob ⇒ those towers cannot score a closing
  model's nocturnal H at all. **No default changed** (guardrail 4); probe `scripts/e_nocturnal_h_decomp.jl`,
  report `<energy_reference>/derived/seb_validation/e6_nocturnal_h_decomp.txt`.
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
- **E6** ✅ **DONE 2026-07-28** (ADR 0073) — the nocturnal-H diagnosis. Attributed by **exact algebra**
  (`ΔH = ΔRn − ΔG + ε_obs`), not by sweep. Refutes the stability/`g_a` hypothesis three ways, identifies the
  ground-heat term's **timescale** as the mechanism, recommends **`λ_g = 1.0`** (an E→M integration point;
  `stab_amp` withdrawn as one), and bounds what is achievable: nocturnal R² > 0 needs a force-restore soil
  scheme, not a tune. Probe `scripts/e_nocturnal_h_decomp.jl`; jobs `E-e6decomp` 1622483 … 1622494.
- **E7** ✅ **DONE 2026-08-05** (ADR 0074) — the opt-in two-layer prognostic ground-heat column. Built as the
  design change ADR 0073 deferred, and it **beats the fitted `λ_g`** without fitting: daily H R² 0.645/0.775
  and daily G R² 0.717/0.614 at DE-Hai/AU-ASM, correct sub-daily diurnal `G` amplitude at closed canopies,
  positive night `G` R² (+0.394, DE-Hai). Energy-exact and daily-step-stable by holding `G` fixed over the
  step (the MITgcm form); self-equilibrating, so no deep-restore knob. **Nocturnal H R² stays negative**
  (−0.324) — `ε_obs`-bounded, canopy heat storage is the remaining term. `enable_two_layer = true` is now the
  live E→M integration point, superseding `λ_g = 1.0`.
- **E7b** ✅ **DONE 2026-08-06** (ADR 0075) — the column becomes the **package default**, answering line M's
  pre-registered ask (ADR 0058 §5) and ending the two-scheme split. Guardrail 4 re-served by the opt-out.
  The criterion **failed at AU-Rob only** (the tower ADR 0073 had already excluded from scoring H) and the
  flip proceeded on four pre-published grounds. Blast radius **measured**: 111 227 pass / 3 fail with only the
  default flipped, all three E's own re-pinned assertions ⇒ nothing outside `energy_closure_tests.jl` moves.
  Also corrected ADR 0074 §6 (its sub-daily `T_skin` cost is at `z1 = 0.2 m`, not the shipped 0.75 m) and
  captured the cause as `plumber2-reference` TRAP 3. Report `_v6`, job `E-e7v6` 1717191; suites 1717194/1717229.
- **E8** *(new, optional — the remaining physical term)* **canopy heat storage.** With E7 landed, this is the
  only unexplored term left in the nocturnal-H budget. Would need a canopy heat-capacity state in E and,
  for a real value, biomass/LAI from S — likely an S→E boundary question. Bounded by `ε_obs` regardless, so
  do not expect nocturnal H R² > 0 from it either; the honest target is sub-daily `T_skin` at AU-Tum/AU-Rob.
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
- **A published reservoir parameter is tuned for the PUBLISHER's timestep.** Before adopting one, compute the
  relaxation number `dt·(Σ conductances)/(thickness · heat capacity)` at *our* step. MITgcm/SpeedyWeather's
  soil `z1 = 0.2 m` is for a minute-scale model; at `dt = 1 d` it is **1.125**, so the top layer equilibrates
  inside one step and `G` degenerates into a day-to-day *difference* of `T_skin` (daily G R² −2.8). E7 looked
  mediocre for this reason alone until the thickness was swept (ADR 0074 §2). Default is now `z_soil1 = 0.75`.
- **A diagnosed flux belongs to the START of the step.** `G` is computed from the pre-step `t_soil1` and
  `solve!` *then* advances the column, so asserting `G == κ_g(T_skin − clo.t_soil1)` after the call is off by
  exactly `κ_g·ΔT1`. Capture the pre-step state first — this produced 54 identical CI failures.
- **Reuse `scripts/e_seb_drive_common.jl`** for any new PLUMBER2 probe (readers, `skill`/`fmt`, `nanstd`,
  `loglaw`, `run_site`, `aggregate_daily`). Those helpers were copied three times before being extracted;
  `validate_e_seb_vs_plumber2.jl` and `e_nocturnal_h_decomp.jl` keep their inline copies on purpose (frozen
  ADR 0072/0073 artifacts) — do not make a fourth.
- **Never `git stash -u` while a SLURM job is writing fixtures into this worktree** — the stash pulls the
  files out from under the running job.
- Any long job → SLURM (`scripts/sbatch_python.sh` / `sbatch_julia.sh`); the login node is hook-blocked.
