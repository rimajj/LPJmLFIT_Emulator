# 0320 — Learned daily water–carbon model, phase A (offline learnability): data, design and pre-registered test

* **Status:** Accepted — pre-registration (2026-10-10), written **before** any model was trained. Results go in a
  later ADR that cites this one; nothing in §4–§6 may be loosened after a score is seen (tightening is allowed).
* **Implements:** `EXECUTION_PLAN.md` §6 arm F2, priority 1 of §9 (revision 3). Goal: ADR 0318.
* Scripts: `scripts/f2_build_daily_table.py` (data), `scripts/f2_train.py` (model + free run + score).
  Data: `/p/projects/open/Jamir/esm_land_emulator_data/f2/`.

## 1. What is being learned

The original's daily exchange of the whole stand (trees + grass, what an atmosphere sees): gross and net primary
production (`gpp`, `npp`), transpiration, soil evaporation, interception, runoff, and the two water stores it carries
day to day — plant-available water in the top metre (`rootmoist`) and snow (`swe`). Daily, per cell, given the
day's weather and the stand as it stood at the end of the previous year. The forest structure itself (counts,
biomass, traits) is the other half of the emulator and is **not** predicted here; in phase A it is taken from the
original's own annual output, so this test isolates the daily model.

## 2. Data inventory (measured 2026-10-10)

| source | content | use |
|---|---|---|
| panel runs of the original (`…_data/trackD/panel/m<k>/<leg>/`), 1 050 cells, 25 patches, 2020–2100 | `daily.parquet`: prec transp evap interc runoff swe rootmoist pet npp gpp (per day); `annual.parquet`: vegc, lai_stand; `fpc_stand.parquet` (band 0 = natural-stand fraction, bands 1–10 = the 10 natural PFTs); `monthly.parquet`: swc + whc_nat for 23 layers; `ind.parquet` | **the training and test venue** |
| daily output exists for | 4 independent members × {`hist` 2000–2019, `ctl_obs`, `mpi-esm1-2-hr_ssp126/370/585`, `ukesm1-0-ll_ssp370`} | |
| forcing | the `.clm` files each leg's config names (`/p/tmp/jamirp/trackD/panel/inputs/<leg>.js`): tas, pr, rsds, lwnet, huss | inputs |
| global daily run 2000–2019 (186 GB, one member) | same daily variables + `swc` per layer, **no** annual stand output from the same run | not used in phase A |

Verified properties (probe scripts in the session scratchpad, numbers here):
* The leg's daily `prec` output equals the forcing file at the same cell/day to ≤ 2e-6 mm (orderA index = `Cell`,
  365-day bands, year index = year − firstyear) — so the forcing join is exact.
* `ctl_obs` (observed 1990–2019 weather, years shuffled): each simulated year matches exactly one observed year
  (max abs diff 0.0, runner-up ≥ 15 mm), and the year sequence is the **same for every cell** checked across two
  blocks (2020→2004, 2021→2017, 2022→2016, 2023→1995, 2024→2007, 2025→2019 in member 3). The builder recovers the
  sequence per (member, leg) and gates it on every cell.
* `rootmoist` never goes below 0 and its annual maximum equals `cap = Σ_{l<3} whc_nat[l]·dz[l]` (dz = 200, 300,
  500 mm) to 1e-4 (median ratio 1.000, 99th pct 1.000); `cap` varies by ≤ 0.13 % within a year. So the top-metre
  bucket has a known capacity.
* The daily exchange of the top metre with the soil below, computed as the residual
  `deep = prec − transp − evap − interc − runoff − Δ(rootmoist + swe)`, is large in gross terms (median Σ|deep|
  418 mm/yr) but nets to ~0 over a year (median 0.002, 10–90 % −102 … +123 mm/yr).
* ⚠ The `hist` leg runs with **rising CO2** (TRENDY file, 2000–2019); every other leg is at constant 409.63 ppm.
  The emulator must not see CO2 (ADR 0004/0107), so `hist` is **excluded** from training and scoring.

## 3. Model design (fixed now)

* **State, closed by construction.** Three stores: snow `S`, top-metre water `W` ∈ [0, cap], and a deep store `D`
  (an anomaly, starts at 0, never an input). Each day the network outputs, from today's inputs and yesterday's
  `S`, `W`:
  * snow: `S_t = S_{t−1}·(1 − m) + prec·f` with `m, f ∈ [0, 1]` (melt fraction, snowfall fraction);
  * `interc = prec·i`, `i ∈ [0, 1]`; `transp, evap, runoff ≥ 0`; `deep` signed;
  * `W_t = W_{t−1} + prec − (S_t − S_{t−1}) − interc − transp − evap − runoff − deep`; an overflow above `cap` is
    added to `runoff`, a deficit below 0 is taken from `deep`. Both are logged (their annual mass is reported).
  * `D_t = D_{t−1} + deep`. Hence `prec − ET − runoff = Δ(S + W + D)` holds exactly every day.
  * `gpp ≥ 0`, `npp` signed, from the same inputs (one network pass per day; all heads see yesterday's stores).
  * Bounds verified on 8.0 M cell-days of one leg: `interc ≤ prec` and `ΔS ≤ prec` on every day, no negative
    transp/evap/runoff/gpp — so the bounded heads above restrict nothing the original does.
* **Inputs** (all causal, none from the target run's fluxes): today's tas, pr, rsds, lwnet, huss; trailing means of
  tas (10 d, 30 d) and rsds (30 d); trailing sums of prec (30 d, 90 d, 365 d) — these stand in for the deep soil's
  memory without carrying it as a drifting state; day of year (sin, cos), sin(latitude), day length; `W_{t−1}`,
  `W_{t−1}/cap`, `S_{t−1}`, `cap`; the stand at the end of the previous year: `lai_stand`, `vegc`, `fpc_stand`
  bands 1–10.
* **Network:** one multilayer perceptron, 2 hidden layers × 64 units, SiLU; all heads from one trunk. Trained
  one-step (yesterday's stores from the truth), loss = per-variable standardised squared error summed over the
  eight targets. Arm **A** is exactly this. Arm **B** (rollout fine-tuning over 365-day sequences, stores carried by
  the model) is run **only if** A fails §5 with a store-drift signature (free-run error ≥ 2× its one-step error on
  ET); otherwise it is not run.
* Years 2020 is a warm-up for the trailing windows and the stand input (end-of-2019 stand from the `hist` leg of the
  same member); scoring uses 2021–2100.

## 4. Splits

* **Held-out space (the primary test):** the five biome blocks (24 Amazon, 32 Sahel, 57 Iberia, 77 Hainich, 90
  Siberia) plus, in every climate stratum with ≥ 2 blocks, its lowest-numbered non-biome block. Everything else
  trains. All four members of a held-out block are held out.
* **Held-out climate:** training legs = `ctl_obs`, `mpi-esm1-2-hr_ssp126`, `mpi-esm1-2-hr_ssp370`. Held out:
  `mpi-esm1-2-hr_ssp585` (amplitude beyond training) and `ukesm1-0-ll_ssp370` (an unseen climate model).
* Early stopping uses 10 % of the training blocks, never a held-out block.

## 5. The bar (EXECUTION_PLAN §6, made exact) — every number from a FREE run

Free run = stores initialised from the truth on 2020-01-01, then carried by the model for 81 years; the stand is the
original's (offline). Scored on held-out blocks. "Cell mean" = 2021–2100 mean annual total; emulator and truth are
each averaged over the four members (each member's emulator run uses that member's stand). ET = transp + evap +
interc.

| # | statistic | pass |
|---|---|---|
| L1 | relative error of the cell mean of GPP, ET, NPP at the five biome cells, on `mpi-esm1-2-hr_ssp370` | within ±5 % at ≥ 4 of 5 cells, for each of the three |
| L2 | median over held-out cells with mean GPP ≥ 50 gC m⁻² yr⁻¹ of the absolute relative error of the cell mean, on each of the five legs | ≤ 5 % for GPP, ET, NPP, every leg |
| L3 | area-weighted (cos lat) total over held-out cells, each leg | within ±5 % for GPP, ET, NPP |
| R1 | GPP change 2071–2100 minus 2021–2050 at the five biome cells, `mpi-esm1-2-hr_ssp370` | the emulator's four-member mean inside the original's four-member [min, max] at ≥ 4 of 5 cells |
| S1 | cost of the daily model per cell-year, one core, batch over the 1 050 panel cells, features + network + bucket, no I/O | ≤ 0.01 core-s |

**Reported beside every number (no pass/fail):** the original's own member spread for the same statistic (sd over
the four members / mean); the same statistics one-step (stores from the truth), so step error and store drift are
separated; R1 also on `ukesm1-0-ll_ssp370` and `mpi-esm1-2-hr_ssp585`, and as an aggregate response ratio
(Σ emulator change / Σ original change over held-out cells); annual mass of the clipping in §3; drift of `D`.
**Whether the original's four-member band at each biome cell excludes zero** is stated next to R1 — where it does
not, the clause cannot distinguish a model from no response, and that cell is said to carry no power.

**Nulls, in the same table:**
* **N1 climatology:** each held-out cell's own day-of-year mean of every flux from its `ctl_obs` leg (same member).
  It has the right level by construction on `ctl_obs` and zero climate response.
* **N2 one-step:** the arm's own one-step score (above).

Pass = L1, L2, L3, R1 and S1 all hold. If the arm fails, the failing statistic is the finding (EXECUTION_PLAN §8),
recorded in the result ADR; phase B (coupled) starts only after a pass.

## 6. What this test does not cover

The stand comes from the original, not from the structure emulator: the structure emulator does not yet produce
`lai_stand` / `fpc_stand`, so the coupling needs a map from its outputs (counts, biomass per tree, traits) to these
inputs, scored in phase B. The panel is 1 050 of 54 020 tree-bearing-or-not cells; the final verdict needs all cells.
