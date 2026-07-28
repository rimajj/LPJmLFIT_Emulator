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
