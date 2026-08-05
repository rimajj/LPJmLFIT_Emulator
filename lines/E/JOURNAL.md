# JOURNAL — LINE E (Component E vs observations (P2))

> **Append-only, newest at the bottom.** Narrative for THIS LINE only: what you did, the commands, the
> results, dead ends. Durable state goes to `lines/E/STATE.md` (and its `## NEXT` block — refresh it before
> your session ends); cross-cutting durable facts go to `MEMORY.md`; the story of one change goes to a
> `changelog.d/E-<slug>.md` fragment. Pre-split history for the whole project: the root `JOURNAL.md`.
>
> Entry template:
> ```
> ## YYYY-MM-DD — <short title>  [milestone E<n>]
> - **Goal:**
> - **Did:**
> - **Result / evidence:** (numbers, job ids, gate outcomes)
> - **Decisions:** (ADR NNNN if any)
> - **Next:** (mirror into STATE.md's NEXT block)
> ```

## 2026-07-28 — line created (ADR 0028/0029)
- **Goal:** stand up line E as an independent work line so it can run concurrently with the other lines.
- **Did:** created by the Phase-0 setup session on `main`: branch `line/E` + worktree `wt-E`,
  `lines/E/{STATE.md,JOURNAL.md}`, ADR block assigned, ownership recorded in ADR 0029.
- **Result / evidence:** see the root `JOURNAL.md` Phase-0 entry for the setup evidence.
- **Decisions:** ADR 0028 (branch+worktree per line, supersedes 0013), ADR 0029 (the split + ownership).
- **Next:** the `## NEXT — start here` block in `lines/E/STATE.md`.

## 2026-07-28 — E1 DONE: PLUMBER2 staged, loaded, sanity-checked — and T_skin turns out NOT to be observable at Hainich  [milestone E1]

- **Goal:** unblock the data-bounded line: acquire the observational reference for Component E (DE-Hai +
  biome sites), land it under `config/paths.yaml` `data.energy_reference`, write a loader + first sanity report.

- **Did:**
  1. **Probed egress before assuming a blocker.** `curl` from the login node reaches `zenodo.org`,
     `data.icos-cp.eu`, `fluxnet.org`, `api.github.com` **and** `thredds.nci.org.au` — so the assumption that
     acquisition needs a human download was wrong. The NCI THREDDS **`ks32` collection serves PLUMBER2 v1-0
     anonymously**: catalog `…/thredds/catalog/ks32/CLEX_Data/PLUMBER2/v1-0/Flux/catalog.html` lists all 170
     sites (102 FLUXNET2015 / 45 LaThuile / 23 OzFlux), `fileServer/…` streams the NetCDF with no auth.
     (Also found, and rejected, a local `/p/projects/lpjml/reference_data/fluxnet` tree — another group's
     staging dir, undocumented provenance; see ADR 0070.)
  2. **Wrote `scripts/fetch_plumber2_sites.py`** — a site table (id → PLUMBER2 stem, biome slot, note), an
     idempotent size-checked download, and a `manifest.json` with URL + bytes + `sha256` per file. It reads
     the destination from `config/paths.yaml` (small `${a.b}`-expanding reader, no PyYAML dependency).
  3. **Staged 6 sites**, then — after inspecting the variable inventory (below) — **3 more**: 9 sites,
     122 MB raw. `DE-Hai` (prototype) + `FI-Hyy` / `FR-Pue` / `US-SRM` + `AU-How` / `GF-Guy`, plus the OzFlux
     `AU-Tum` / `AU-Rob` / `AU-ASM`.
  4. **Wrote `scripts/validate_e_plumber2_load.py`** — loads Flux + Met into one model-facing half-hourly
     frame (`le/h/rn/g/swdown/lwdown/tair/qair/wind/psurf/precip/ustar/lai/…` + every `*_qc`), and reports
     coverage, QC composition, unit/range checks, the observed energy budget + closure slope, daytime Bowen,
     a time-axis check, and `T_skin` from `LWup`. Writes `halfhourly_/daily_/diurnal_<site>.parquet`,
     `site_summary.csv`, `plumber2_sanity_report.txt` under `…/fluxnet_plumber2/derived/` (300 MB total).

- **Result / evidence** (`derived/plumber2_sanity_report.txt`, 9 sites, all RANGE CHECK **PASS** — a few
  documented outlier WARNs):

  | site | slot | IGBP | record | Rn | LE | H | Bowen(day) | closure slope | joint-valid |
  |---|---|---|---|---|---|---|---|---|---|
  | DE-Hai | temperate | DBF | 2000–2012, 30 min | 57.6 | 32.2 | 15.0 | 0.96 | 0.882 (0.971 corr.) | 76.9 % |
  | AU-Tum | temperate | EBF | 2002–2017, 60 min | 101.6 | 71.3 | 38.3 | 0.80 | 0.678 (0.868) | 100 % |
  | FI-Hyy | boreal | ENF | 1996–2014, 30 min | 54.0 | 25.8 | 17.5 | 1.23 | 0.773 | 39.1 % |
  | FR-Pue | mediterranean | EBF | 2000–2014, 30 min | 80.4 | 28.4 | 26.1 | 1.70 | 0.662 | 55.6 % |
  | US-SRM | semi-arid | WSA | 2004–2014, 30 min | 100.3 | 24.8 | 63.0 | 3.31 | 0.806 | 100 % |
  | AU-ASM | semi-arid | ENF | 2011–2017, 30 min | 129.3 | 23.6 | 86.5 | 4.57 | 0.772 | 100 % |
  | AU-How | savanna | WSA | 2003–2017, 30 min | 150.4 | 93.4 | 41.1 | 0.54 | 0.782 | 100 % |
  | GF-Guy | tropical | EBF | 2004–2014, 30 min | 141.8 | 109.0 | 21.3 | 0.30 | 0.777 | 98.7 % (no Qg) |
  | AU-Rob | tropical | EBF | 2014–2017, 30 min | 151.0 | 91.1 | 31.2 | 0.52 | 0.599 | 100 % |

  Fluxes in W/m². **Observed Bowen ordering = the ordering `biome_coupled_tests.jl` asserts** (tropical 0.30
  → temperate ~0.9 → mediterranean 1.7 → semi-arid 3.3–4.6). Uncorrected closure slopes 0.60–0.88 with the
  EB-corrected fluxes at 0.87–1.02 — textbook FLUXNET non-closure, so **compare E against `Qle_cor`/`Qh_cor`
  and quote both**. `Qg` sign is `positive INTO ground` at 7 of 8 Qg sites (DE-Hai's ±0.3 W/m² difference
  can't discriminate). Time axis is **local standard time** at all 9 (mean-diurnal `SWdown` peaks 11.0–12.5 h).
  PLUMBER2's own daytime joint uncertainty (`*_cor_uc`, only on the 4 FLUXNET2015 sites): DE-Hai **LE ±50.1,
  H ±56.6 W/m²**; FI-Hyy ±48.3/±68.9; FR-Pue ±40.7/±70.4; US-SRM ±24.2/±59.3. That is the E4 band — and H's
  band exceeds LE's at every one of them, confirming `DEVELOPMENT_PLAN` §7's warning that H is the hard one.

- **The two findings that changed the plan:**
  1. **`T_skin` is NOT observable at DE-Hai.** PLUMBER2's FLUXNET2015/LaThuile files have `SWup` but **no
     `LWup`** and no surface temperature; only the **OzFlux** files carry `LWup`. So T_skin is derived at
     AU-Tum / AU-ASM / AU-Rob / AU-How by inverting E's own longwave term at ε = 0.97 (brightness-T differs by
     only +0.16…+0.48 K, so emissivity is not the limiting uncertainty). Daytime `T_skin − Tair` = **+1.11 K**
     (AU-Tum), **+4.70 K** (AU-ASM), **+0.65 K** (AU-Rob) — physical; **AU-How = −1.85 K daytime** (−3.97 K
     nighttime) — **suspect, diagnose before use**. No boreal OzFlux site ⇒ boreal T_skin unsourced. ADR 0070.
  2. **`_FillValue = -9999` leaks through `np.asarray()`.** netCDF4 returns a *masked* array;
     `np.asarray(masked)` drops the mask and hands back the raw −9999. First DE-Hai run reported **mean
     LE = −2283 W/m²** and Bowen −0.04. `np.ma.filled(..., np.nan)` fixed it (→ +32.2 W/m², Bowen 0.96).
     Related, verified: at DE-Hai all 52 608 `Qle_qc == 5` rows *are* the fill rows and match the variable's
     own `Missing_%: 23.1` — in the PLUMBER2 **Flux** files flag 5 marks data left MISSING, not filled.

- **Dead ends / judgement calls:** the range check first FAILed on ~6 variables; each was inspected rather
  than the band widened blind — negative nighttime `SWup` (radiometer zero offset, min −3.4 W/m²), negative
  `Ustar` at AU-ASM (625 samples, OzFlux processing artifact — any u*-based `g_a` check must drop u* ≤ 0),
  `CO2air` median 650 ppm at AU-ASM (in-canopy nocturnal build-up; that site's CO₂ is unusable quantitatively),
  half-hourly `GPP` negative to −48 µmol/m²/s (nighttime-partitioning artifact), `Qair` → 4.7e-8 kg/kg in the
  Finnish cold-dry tail, 100 mm/h precip at AU-Rob (real tropical convection). Bands now document each
  acceptance; the FAIL/WARN split is 0.1 % of the finite record, so a genuine unit error still FAILs.

- **Decisions:** **ADR 0070** — PLUMBER2 v1-0 as the reference, the 9-site set, and the split E4 gate
  (LE/H/Rn at DE-Hai + biomes; T_skin at OzFlux only).

- **Next:** E2 (the `sfcwind`/`ps` cross-grid remap) is now the critical path — see STATE.md `## NEXT`.
  Note the E4 pairing hazards already found: leap vs noleap-365, local-standard time, and
  `Qle_cor`-vs-`Qle` choice.

## 2026-07-28 — E2 DONE: wind + psurf remapped onto orderA cells, mapping PROVEN by a tas round-trip  [milestone E2]

- **Goal:** kill the named blocker — Component E runs on a constant wind and a fixed psurf, so E4 cannot
  honestly score LE/H against a tower. Source both forcings, get them onto the model's orderA cells, and prove
  the mapping instead of assuming it.

- **Did:**
  1. **Searched for the source rather than accepting the milestone's assumption.** The milestone named the raw
     SSP370 MPI-ESM1-2-HR NetCDFs — but that set is `hurs huss lwnet pr rsds sfcwind tas tasmax tasmin`:
     **no `ps` at all**. Found instead
     `/p/projects/isimip/isimip/ISIMIP3a/InputData/climate/atmosphere/obsclim/global/daily/historical/GSWP3-W5E5/`
     with **both** `gswp3-w5e5_obsclim_ps_global_daily_*.nc` [Pa] and `…_sfcwind_…` [m/s], daily 1901–2019 —
     i.e. the **same obsclim family the LPJmL-FIT run itself consumed**. Also checked and rejected: WFDE5_CRU
     `PSurf` (ends 2018, different family), the LPJmL-prepared obsclim `.clm`/`.nc` (no `ps`, and its wind is
     quantized), and elevation-derived psurf (no weather).
  2. **Wrote `scripts/remap_wind_psurf_cells.py`** — `grid.nc cellid` → (lat, lon) → source axis matched **by
     value with an exactness assertion**, 29 February dropped for the model's noleap-365, one read per
     (cell, decadal file) because obsclim is chunked `[1,360,720]`+zlib (a single-cell decade read ≈ 8 s).
     Emits committed fixtures `test/testitems/references/wind_psurf_<biome>.csv` (`year,doy,wind,psurf`,
     2010–2019 × 365 d) for the same 5 cells and decade as the existing `biome_forcing_<biome>.csv` — a NEW
     fixture family, so no committed baseline moves.
  3. Ran the full 5-cell job on SLURM (`E-windps`, job 1617515, exit 0).

- **Result / evidence — the E2 gate PASSES at all five biome cells:**

  | check | result |
  |---|---|
  | (a) index arithmetic vs `xarray` label `.sel` | `max|Δ| = 0` for `sfcwind` **and** `ps`, every cell |
  | (b) obsclim `tas` .nc vs model-grid `temperature_test.clm` | **`max|Δ| = 0.000 °C` over 365 days, all 5 cells** (means −9.552 / 7.381 / 14.926 / 28.303 / 30.231 °C) |
  | (c) leap-dropped wind vs the LPJmL-prepared **noleap** wind | agrees to `≤3.8e-7 m/s` after matching that file's **0.01 m/s quantization** (raw `max|Δ| ≤ ½` step) |
  | (d) Hainich cell vs the DE-Hai tower (E1 data) | wind 3.246 vs 3.609 m/s (**−10.1 %**); psurf 97 522 vs 95 873 Pa (**+1649 Pa ⇒ cell mean ≈143 m below the tower's 430 m**) |

  Per-cell 2010–2019 means — wind [m/s] / psurf [Pa]: boreal_siberia 2.868 / 96 718 · temperate_hainich
  3.220 / 97 548 · mediterranean_iberia 2.590 / 93 868 · semiarid_sahel 3.246 / 97 135 · tropical_amazon
  1.490 / 100 638. All inside the physical bands the script asserts.

- **Two traps hit and fixed:**
  1. **The `.clm` v3 datatype codes are 0-BASED** (`0=byte 1=short 2=int 3=float 4=double`). My reader used a
     1-based map, read `temperature_test.clm`'s float32 as int32, and check (b) "failed" with a clm mean of
     **5.9e8 °C**. Fixed → `max|Δ| = 0.000`. Now in `CLAUDE.md` §3 and the new skill.
  2. **The LPJmL-prepared obsclim wind is quantized to 0.01 m/s** (int16·0.01 in the `.clm` twin), so check (c)
     "failed" at `max|Δ| = 4.998e-3` — exactly ½ a step. The comparison now rounds to the prepared grid first.

- **Judgement calls:** no global `.clm` written (5 cells × 10 yr is what anything consumes today; a 1.9 GB
  global daily wind `.clm` before a consumer exists is speculative). SSP370 psurf left unsourced and recorded
  as such rather than papered over with an elevation formula that has no synoptic variability.

- **Decisions:** **ADR 0071** — obsclim GSWP3-W5E5 as the wind/psurf source, the grid + calendar conventions,
  the four-part gate, and the open SSP370-psurf gap. `config/paths.yaml`
  `lpjml.energy_extra_inputs.{sfcwind,ps}` filled.

- **Next:** E3 (sublimation-λ split, self-contained) then E4 (the P2 gate). E5 = feed these fields into the
  coupled driver — an **integration point with line M** (`src/run.jl` is M's path); noted in both STATE files.

## 2026-07-28 — E3 re-scoped: the sublimation-λ split is NOT an E-only change  [milestone E3 → integration point]

- **Goal:** start E3 (use `LAMBDA_SUBLIMATION` where the flux leaves snow/ice) — the plan called it
  self-contained inside `src/components/energy.jl`.
- **Did:** read the seam before writing code. `FToE` (`src/interface.jl:44`) carries **`le`, already formed as
  λ·ET** — `src/components/fast.jl:236` does `le = et/86400 · LAMBDA_VAPORIZATION` with
  `et = transp + evap + interc`. So (i) the λ choice is made in the **F core**, not in E; (ii) that ET sum has
  no snow/ice component to split; (iii) `FToE` carries no snow mass or snow fraction, so `energy.jl` cannot
  even see which part of `le` left snow. Both files are **line M's** (`src/interface.jl` explicitly, and the F
  core per `CLAUDE.md` §9's ownership resolution).
- **Result:** E3 is an **integration point with M**, not an E milestone — recorded as such in
  `lines/M/STATE.md` (with the concrete shape: F partitions ET, then either a new `FToE` field or apply
  `conservation.jl::latent_heat(et; sublimation)` next to the partition; opt-in, default byte-identical).
  Doing it from E alone would mean inventing a snow fraction — exactly the kind of unfaithful "fix" guardrail 5
  exists to stop.
- **Consequence for E4 (now NEXT), same reading:** since LE arrives pre-formed from F, **E's own predictions
  are T_skin, H and G — not LE**. So the P2 gate must run **Experiment A** first (force `solve_seb` with the
  tower's own forcing *and the tower's* `le_cor`, then score E's H against `h_cor` and E's T_skin against the
  OzFlux `t_skin`), which isolates the closure from F's ET error, and only then **Experiment B** (F's LE
  feeding E). The A−B difference *is* F's ET error, which is the attribution the gate has to state. Also
  logged: `solve_seb` is instantaneous (fine at 30 min) but `solve!`'s `t_soil` EWMA has `tau_soil` in **days**
  — the diurnal test must scale it or drive `solve_seb` directly.
- **Decisions:** none new (ADR 0070/0071 stand); this is a scope correction inside the line plan.
- **Next:** E4 as re-specified in `lines/E/STATE.md` `## NEXT`.

## 2026-07-28 — E4 Experiment A: the P2 gate RAN. Rn + T_skin verified, H only in the mean, nocturnal H is the failure mode  [milestone E4]

- **Goal:** run the P2 gate — score Component E against flux towers — and say precisely what may now be claimed.

- **Design (the part that decides everything):** `FToE` hands E `le` **already formed** as λ·ET
  (`components/fast.jl:236`), so **LE is F's number**; E's own outputs are **T_skin, H, G**. Experiment A
  therefore drives `solve_seb` with a tower's own forcing **and the tower's own `le_cor`** — F's ET error is
  excluded by construction, and a miss is unambiguously E's. Every boundary value comes from the observation
  where one exists: **albedo** = the tower's Σ SWup/Σ SWdown, canopy height and — load-bearing — `z_ref` =
  the site's **measurement** height (43.5 m at DE-Hai; the 10 m default would evaluate `g_a` at a level the
  forcing was never measured at). `t_soil` reproduces `solve!`'s τ = 30 d EWMA on **daily-mean** Tair (the
  per-step recursion at 30 min would decay ~48× too fast).

- **Did:** `scripts/build_e_seb_validation_table.py` (tower-forced driving tables, 4 sites) →
  `scripts/validate_e_seb_vs_plumber2.jl` (pure-Base driver: `solve_seb` per step; bias/RMSE/MAE/R²/slope for
  H, T_skin and Rn; all / day / **night**; **half-hourly and daily**; the fraction inside PLUMBER2's own
  `|h_cor_uc|`; the mean diurnal cycle; a `stab_amp`/`stab_k` sweep). Jobs `E-sebtable2` 1622120,
  `E-e4a3` 1622127. **497 936 tower steps.**

- **Result / evidence:**

  | site | steps | H bias | H RMSE | H R² all/day/**night** | H daily bias/RMSE/R² | T_skin RMSE / R² | Rn R² |
  |---|---|---|---|---|---|---|---|
  | DE-Hai | 175 344 | **+6.4** | 54.8 | 0.647 / 0.535 / **−1.02** | +6.4 / 33.4 / 0.257 | — (no LWup) | **0.986** |
  | AU-Tum | 134 898 | −19.2 | 80.3 | 0.569 / 0.390 / **−1.70** | −19.2 / 37.8 / 0.125 | 3.21 K / 0.773 | 0.989 |
  | AU-ASM | 122 736 | −6.8 | 59.2 | 0.898 / 0.780 / **−1.01** | −6.8 / 18.3 / **0.778** | 2.59 K / 0.941 | **0.996** |
  | AU-Rob | 64 958 | −7.8 | 110.7 | −0.01 / −0.22 / **−5.62** | −7.8 / 34.5 / 0.256 | 3.34 K / 0.385 | 0.995 |

  Daily T_skin RMSE **1.41–1.97 K**, R² 0.76–0.95. At DE-Hai (the only site with a band): **76.4 % of 3 653
  daily means** and 57.2 % of 175 344 half-hours inside `|h_cor_uc|` (±40.94 W/m²).
  ⇒ **Rn VERIFIED · T_skin VERIFIED where observable · H verified in the MEAN, not in variability.**

- **The failure mode, named:** the closure runs **1–2 K too cold at night** — modelled night `T_skin − Tair`
  −3.38 / −2.62 / −1.82 K (AU-Tum / AU-ASM / AU-Rob) vs observed −1.39 / −1.67 / −0.74 K — and nocturnal H has
  R² < 0 at **every** site. The stability correction is right to be ON (night RMSE 37.0 vs 41.7 DE-Hai, 29.7 vs
  46.4 AU-ASM) but its `stab_amp = 0.75` is **too weak**: the sweep is **monotone up to 0.9** at both sites, i.e.
  the optimum sits at the parameter's bound ⇒ suspect the bounded-tanh *form*, not the coefficient. **No default
  was changed** (guardrail 4; a flip is an M integration point).

- **Methodological finding worth keeping:** the half-hourly H R² (0.647 at DE-Hai) is **inflated by the diurnal
  cycle** — most half-hourly variance *is* the day/night swing, which any closure driven by observed SWdown
  reproduces. The daily-mean R² (0.257) is the honest number. Quote daily.

- **The bug the new regression fixture caught on its first run (and it was MINE, in the verdict):** committing a
  single-year fixture (DE-Hai 2010) reported an H bias of **+39.8 W/m²** where the record said +11.4. Cause:
  at DE-Hai the **uncorrected `le` is all-NaN for 2010–2012** (that is where the site's 23.1 % missing LE sits)
  and PLUMBER2's EB correction emitted **≈0 instead of a fill value** there (annual mean `le_cor` 0.39 / −0.09 /
  0.04 W/m² vs 30–40 in 2000–2009), while `h_cor_uc` vanishes. My completeness filter only tested `le_cor` for
  finiteness, so it kept **36 550 rows of garbage**, and feeding the closure LE ≈ 0 pushes all available energy
  into H. Fixed by also requiring the **uncorrected** `le` to be finite (DE-Hai → 175 344 rows = exactly ADR
  0070's jointly-valid count), and the fixtures are now **stratified every 12th day × every 3rd hour across the
  whole record**. The whole DE-Hai verdict was recomputed: bias +11.4 → **+6.4**, daily R² 0.087 → **0.257**,
  all-R² 0.573 → 0.647. Other sites unaffected.

- **AU-Rob is a suspect site, not an E failure:** its own tower budget is the worst of the nine staged (closure
  slope 0.599) and its H is unpredictable even in daylight (R² −0.22) while its T_skin still scores 0.762 daily.

- **Decisions:** **ADR 0072** — the P2 verdict, with the pre-fix baseline numbers, the named failure mode, the
  stability finding, and the gate frozen as a CI regression test (the night-cold bias pinned as a *sign*
  assertion, so a genuine fix trips it and forces a supersede).

- **Next:** **E6 — diagnose the nocturnal H failure** (start by forcing `g_a` from the towers' measured `u*`:
  that one experiment separates "wrong `g_a`" from "wrong G / wrong radiative loss"). See STATE `## NEXT`.

## 2026-07-28 — session 2 (line E): E6, the nocturnal-H diagnosis

**Outcome: the failure is a ground-heat *timescale* error, and the hypothesis I was handed was wrong.**
ADR 0073 (supersedes ADR 0072 items 4 + 6). Probe `scripts/e_nocturnal_h_decomp.jl`, jobs `E-e6decomp`
1622483 → `E-e6decomp4` 1622494. Report: `<energy_reference>/derived/seb_validation/e6_nocturnal_h_decomp.txt`.

**What made it cheap: refusing to sweep.** The handoff (and ADR 0072 item 6) ranked the stability form
first, on the strength of a `stab_amp` sweep that was monotone to its bound. But `H` is not *predicted* by
the closure — it is the **exact residual** `Rn_m − LE − G_m`. So with the tower's own non-closure written
as `ε_obs = Rn_o − LE − H_o − G_o`, the error obeys **identically** `ΔH = ΔRn − ΔG + ε_obs`, and **`g_a` is
in none of those three terms**. A hand-integration of one representative DE-Hai night predicted the
stability-ON-vs-OFF difference as +7.2 W/m² before any code ran; the report said +6.7. That was the signal
the frame was right, and the whole diagnosis followed from `g_obs`/`rn_obs` columns the drive tables
*already carried* — one new column (`ustar`) and no new observations.

**Three refutations of the g_a hypothesis** (`residual-diagnosis` P3, stated before the run):
- the closure's nocturnal `g_a` is within **0.7 %** of DE-Hai's measured-`u*` value (0.05724 vs 0.05685);
- substituting the measured `g_a` makes nocturnal H **worse at all four sites** (it does *improve* night
  `T_skin` at AU-Tum, 3.32 → 2.47 K — it is the better `g_a`; H still degrades, because H is the residual);
- a **100× `g_a` bracket** cannot reach positive nocturnal R² anywhere.
The monotone sweep was **bias cancellation**: suppressing `g_a` shifts the skin in whichever direction
offsets the ground-heat error. Time not spent retuning `stab_amp`: probably several sessions.

**The mechanism.** `G = λ_g(T_skin − t_soil)`, `λ_g = 7.0`, τ = 30 d EWMA reference ⇒ no diurnal soil
inertia, no canopy decoupling. sd(`G_m`) is **5–7×** sd(`G_o`) at the forest sites (34.7 vs 5.7 at DE-Hai);
**88 %** of DE-Hai's +14.04 night H bias is `ΔG`. Then the scoping fact that reframed everything:
**`run.jl:93` calls `solve!` ONCE PER DAY** — Parts 1–6 were diagnosing a sub-daily regime the coupled model
never runs in. Solving on daily-mean forcing, as the driver actually does, three independent lines give
**`λ_g ≈ 1.0`**: the implied fit is 0.83–1.10 at all four sites, `λ_g ≈ 1.0` reproduces the observed daily
sd(`G_o`), and daily H R² goes 0.03 → **0.64** (DE-Hai) and 0.33 → **0.74** (AU-ASM).

**The §3b moment.** Fitting `λ_g` against the measured plate `Qg` and against the budget-implied sink
`G_res = Rn_o − LE − H_o` gave 0.90 vs **9.67** at AU-Tum and 1.46 vs **19.92** at AU-Rob — an order of
magnitude. Per `residual-diagnosis` §3b that is a STOP signal, not a footnote, and here it *localised which
sites can be trusted*: the two fits agree only where `ε_obs ≈ 0` (DE-Hai −0.32, AU-ASM −12.0) and diverge
where the tower's nocturnal budget is broken (AU-Tum −62.3, AU-Rob −47.5). **AU-Tum and AU-Rob cannot score
a closing model's nocturnal H at all** — that part of ADR 0072's "failure at every site" was never E's.

**What I did NOT do.** No default changed, no line of `energy.jl` touched (guardrail 4) — `lambda_g` is
already a `SEBParams` field, so the fix is available today as
`SEBEnergyClosure(params = SEBParams(lambda_g = 1.0))`. Flipping the default moves every coupled/biome
baseline ⇒ M's call. The ADR 0072 night-cold sign assertion therefore still passes, as it should.

**Honest limit:** nocturnal R² > 0 is **not** reachable by any `λ_g` — `ε_obs` scatter alone (sd 36 W/m² at
DE-Hai) is the size of the night H RMSE. Real sub-daily fidelity needs a force-restore / two-layer soil
scheme + canopy heat storage. That is a design change and it **bounds line O**, whose online coupling is the
sub-daily use case.

**Captured:** ADR 0073 · the `plumber2-reference` skill gained a "diagnosing a residual in H" section (the
decomposition, the exact-`g_a`-injection-via-wind trick, the `ε_obs` trap, the daily-step scoping check) ·
a synthetic CI testitem pinning the lever ranking · `build_e_seb_validation_table.py` now emits `ustar`.

- **Next:** hand `λ_g = 1.0` to line M as the integration point, then E4 Experiment B. See STATE `## NEXT`.

---

## Session 3 (2026-08-05) — E7: build the design change ADR 0073 deferred, and measure it

**Why now, not E4-B.** The session opened with a question about provenance: is the surface-energy problem
already solved in Terrarium/SpeedyWeather, and did E take code from them? Answering it properly (ADR 0006 →
0017, plus reading both upstreams' actual source) surfaced two things worth more than the queued E4-B:

1. **A stale doc.** `docs/src/explanation/architecture.md` still told readers E *reuses* Terrarium.jl's
   `SurfaceEnergyBalance`. ADR 0017 superseded that on 2026-07-22. Fixed, with the real relationship stated
   (coupling substrate for P4; cross-read only, no code) — the four citation surfaces now agree.
2. **The "design change" ADR 0073 deferred is already written down twice, upstream.** SpeedyWeather's
   `LandBucketTemperature` *is* the MITgcm two-layer soil model (~15 lines of published equations) and
   Terrarium has a full conduction column with a half-cell skin temperature. So "force-restore / two-layer
   soil scheme" was never a research project — it was an afternoon of independent implementation against two
   working references, with reuse already authorized (ADR 0081). Meanwhile the thing E does *better* than
   Terrarium is the aerodynamic side: Terrarium's atmosphere→surface drag is `ConstantAerodynamics`, Cₕ =
   1.2e-3, its own docstring calling it a "Dummy implementation".

**Verified first that the λ_g handoff was already done.** The previous session's `## NEXT` listed it as the
one open action; it was in fact already fully recorded in `lines/M/STATE.md` (third integration point, with
the `stab_amp` withdrawal). `lambda_g` is still 7.0 on `main`, so M has not landed it — nothing to re-raise.

**The result, which exceeded the hypothesis.** H1 said the unfitted scheme should *match* the fitted
`λ_g = 1.0`. It beats it, at both sites whose towers can score H: daily H R² 0.645 vs 0.637 (DE-Hai) and
0.775 vs 0.745 (AU-ASM), and on `G` itself 0.717 vs 0.657 and 0.614 vs 0.477. Sub-daily, the diurnal `G`
amplitude becomes correct at closed canopies (DE-Hai all-hours sd 5.75 vs observed 5.66, against the
default's 34.7) and **night `G` R² goes positive (+0.394)** — the first arm ever to have skill in `G`.
Nocturnal **H** R² stays negative (−0.324), which is what ADR 0073's `ε_obs` bound requires, so H2 is
partially supported and honestly so.

**The finding I did not expect.** MITgcm's `z1 = 0.2 m` is tuned for a model that steps in *minutes*. At our
daily step the layer-1 relaxation number is **1.125**, so the top layer equilibrates with `T_skin` inside
one step and `G` collapses into a day-to-day *difference* of `T_skin` — measured as daily G R² −2.8 and
sd(G) 2.2× observed. The first probe run looked mediocre for exactly this reason. A thickness sweep fixed it
(`z1 = 0.75 m`, `dt·rate` 0.093) inside a broad optimum where H R² moves only 0.634→0.647, so the default is
set on a **resolution** criterion rather than a fit.

**Two things I checked because they could have made the scheme unusable.** (a) Explicit Euler: holding `G`
constant over the step — the MITgcm form — is both energy-exact (the column gains exactly the reported
`G·dt`) and stable at a daily step (only the inter-layer term is stiff, limit ≈ 21 d). Recomputing `G`
mid-step would have imposed a 1.8 d limit and overshot every day. (b) Drift: the bottom is closed and there
is no restoring term, and line M runs decadal. Annual means show no runaway — the 16-year AU-Tum record
trends −0.059 K/yr — because the surface feedback self-equilibrates ⟨G⟩ → 0. Short records look like drift
and are interannual variability; measuring annual means instead of (last − first) is what separated them.

**Honest costs, recorded not buried:** one global `z1` cannot serve a closed canopy *and* a sparse desert
(AU-ASM's observed all-hours sd(G) is 64 W/m², and it wants a much thinner layer), sub-daily `T_skin`
degrades at AU-Tum/AU-Rob, and `theta_soil` is a constant because the frozen `FToE` carries no soil
moisture. `Rn` is preserved within ±0.005, not improved.

**Captured:** ADR 0074 · `scripts/e_two_layer_probe.jl` + `scripts/e_seb_drive_common.jl` (the drive-table
readers/metrics extracted so the next probe stops copying them) · 2 new testitems (default-off byte
identity, closure exactness, the energy-exact column invariant, 4000-step stability, `dt_seconds`
correctness) · the MITgcm register/CITATION.cff/refs.bib/header citation set · the architecture-doc fix.

- **Next:** the E→M integration point is now **`enable_two_layer = true`**, superseding `λ_g = 1.0`. Then
  E4-B. See STATE `## NEXT`.
