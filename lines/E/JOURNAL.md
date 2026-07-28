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
