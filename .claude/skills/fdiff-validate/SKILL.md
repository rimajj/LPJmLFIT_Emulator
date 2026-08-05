---
name: fdiff-validate
description: The recurring extract -> validate -> baseline loop for checking the differentiable fast core F_diff against the LPJmL-FIT C oracle (kernel-isolation drive, Hainich cell 42490 harness, the extract_fdiff_* / validate_fdiff_* scripts, ReferenceTests baselines). Use whenever validating or refining F_diff fidelity vs the C binary, or wiring a new physics term into the daily/canopy rollout. ALSO the four MANDATORY basis checks before comparing ANY C output to F_diff (ADR 0053): the C's daily fluxes are ALL-PFT so grass must be removed via d_grass_gpp (up to 42 % of GPP); the driver's modal patch is 1.12-1.72x denser than the C's 25-patch ensemble mean; a 10-yr-mean ratio hides canopy drift so score year-matched and read the ratio SHAPE; and the daily NetCDF `units` attribute lies (says /month, values are per-day). Names scripts/extract_biome_fdiff_oracle.py, scripts/biome_fdiff_oracle_probe.jl, M_fdiff_oracle_biomes.csv, the rootmoist soil-water check. ALSO the S-SIDE twin (ADR 0054) — validating COUPLED demography + trait distributions against the annual `ind` parquet in seed1-vs-seed2 noise floors (scripts/extract_biome_slow_oracle.py, scripts/biome_slow_oracle_probe.jl, M_slow_oracle_counts.csv) — and the trap that dominates it: NEVER score a recursive emulator's free-running rollout without also running the TEACHER-FORCED arm (overwrite `s.n_prev` with the C truth each year), because the training table's `n_prev` is the C's own previous count and a free rollout integrates a ~5 %/yr one-step bias into +36-81 % over a decade; measured at 59-72 % of the total coupled count error.
---

# fdiff-validate — cross-check F_diff against the C oracle

The discipline that keeps F_diff trustworthy: F_diff reproduces the **C binary's** daily/annual outputs on
the prototype cell to tolerance, and gradients match finite differences. Validate against the oracle, never
against F_diff itself. Prototype cell = **Hainich (DE-Hai), global orderA index 42490**.

## The loop

1. **Extract** the C-oracle reference for the cell (Python, reads the daily/annual run outputs).
   **Parameterize every extractor by cell index (`--cell`, default 42490=Hainich) + year(s)** so a new
   cell is a flag, never a new script — this is the reusable-fixture pattern, don't fork per cell:
   - `scripts/extract_fdiff_validation_inputs.py` — daily forcing + FAPAR/PET "crutch" drivers.
   - `scripts/extract_fdiff_individuals.py` / `..._multiyear.py` — the `ind` per-tree table → `TreePools`.
   - `scripts/extract_fdiff_decadal.py`, `scripts/extract_fdiff_cell_multiyear.py` — multi-year series.
   - `scripts/extract_fdiff_grass_daily.py`, `scripts/extract_grass_structure_decadal.py` — grass.
   Reference fixtures land in `test/testitems/references/` (e.g. `hainich_individuals_2010.csv`,
   `fdiff_annual_totals.txt`, `hainich_canopy_baseline_2010.txt`). The single-cell daily forcing+restart
   re-run these read from is produced by `scripts/run_fdiff_validation_cell.sh` (`lpjmlfit-cbinary` skill).
2. **Validate** F_diff against them:
   - `scripts/validate_fdiff_vs_cbinary.jl` — annual totals vs the C oracle.
   - `scripts/validate_fdiff_structure.jl` — allometry/structure.
   - `scripts/validate_fdiff_canopy.jl` — multi-individual canopy rollout.
   These are also encoded as gates: `numerical_regression_tests.jl`, `cbinary_validation_tests.jl`,
   `multi_individual_tests.jl`, `dynamic_structure_tests.jl`, `decadal_validation_tests.jl`,
   `gradient_correctness_tests.jl`.
3. **Baseline**: regenerate `test/testitems/references/*` **only** on an intentional physics change; note
   *which* baseline moved. `scripts/regen_fdiff_baselines.jl` regenerates the F_diff annual-totals set.

## Kernel-isolation drive

When validating one kernel (photosynthesis, PET/ET, water, respiration) in isolation, drive F_diff with
the C-run's own FAPAR / PET as a "crutch" so a discrepancy localizes to that kernel instead of compounding
through the whole rollout. Remove the crutch for the end-to-end regression.

## The cheapest global check on F_diff's SOIL WATER — the C's `rootmoist` (ADR 0052)

Measure **any** soil-water residual against this FIRST; it needs **no new HPC run** and works for **any
cell on the global grid** (`d_rootmoist.nc` is already in the global daily output).

    w_C(cell, day) = rootmoist / Σ_{l<3} whc_nat[l, month] · soildepth[l]      soildepth = 200,300,500 mm

That is exactly `slow.jl::root_zone_soilmoist(state, soil)` (`ROOT_ZONE_LAYERS = 3`), so the two sides are
the SAME quantity — the §3f test is already passed. Reference pair, copy them:
`scripts/boreal_soilice_diagnosis.py` (C side, gridded lat/lon → nearest cell from `M_cells.csv`) +
`scripts/boreal_soilice_probe.jl` (F side). Report a **monthly climatology per cell**, not an annual mean —
that is what makes a seasonal mechanism (freezing, drying) legible at a glance.

Two things it settled at once, and both matter for any F-water claim:

- **F_diff has NO soil ice.** The C's root-zone `w` at boreal Siberia is **exactly 0.000 for Nov–Apr**
  (all of it ice — `rootmoist = Σ w·whcs` and `w` excludes ice) while F_diff's is flat at 0.67–0.91. So
  every water-stress-like quantity is unreliable in a seasonally frozen cell, and it fails *silently* in
  the unstressed direction (a supply/demand cap just binds all year). Flag cold cells explicitly.
- **F_diff's root-zone water runs too DRY in dry cells** — Sahel Jan 0.361 vs the C's 0.533, mediterranean
  Jul 0.239 vs 0.369, same seasonal shape. Candidate terms: the `_infiltrate` cascade (no surface /
  infiltration-excess runoff — a documented v2 item), `_soil_evap`, the absent free-water `w_fw` reservoir.

**Use `rootmoist`, never `swc`** — `swc` is total water over *saturation* capacity and is NOT invertible to
the model's `w` (ADR 0035). Two variables, overlapping numeric ranges, different denominators.

## The FOUR basis checks to run BEFORE comparing any C output to F_diff (ADR 0053)

Each of these produced a confident, wrong fidelity number in the M3 F-side work before it was caught. Run
them as a checklist; three are one-liners. The reusable pair is `scripts/extract_biome_fdiff_oracle.py`
(C side → the committed `M_fdiff_oracle_biomes.csv` + `..._annual.csv`) and
`scripts/biome_fdiff_oracle_probe.jl` (F side, 25-patch ensemble) — copy them, don't re-derive.

1. **The C's daily fluxes are ALL-PFT; the coupled driver's canopy is TREE-ONLY** (`M_individuals_*.csv`
   keeps `type <= 6`). Grass carries **42.4 %** of GPP at boreal Siberia, 28.4 % mediterranean, 19.3 %
   Sahel, 5.8 % Hainich, 0.2 % Amazon. Remove it *exactly* — the binary already emits per-PFT daily grass
   GPP (`conf.h` id 419) and a single-cell re-run costs ~9 s:
   `CELL=<orderA> RUNTAG=M_grass_val SUBMIT=yes bash scripts/run_fdiff_grass_gpp_cell.sh`
   ⇒ `gpp_tree = d_gpp − d_grass_gpp`. **Do NOT correct by the FPC share instead** — grass under a closed
   canopy is light-limited, so the FPC share over-states the flux share in every cell: 1.31× boreal, 1.86×
   mediterranean, 2.08× Sahel, 2.98× Hainich (5.6× Amazon, where both numbers are ~0 and the ratio is noise).
   `transp` and `a_lai_stand` have NO per-PFT daily equivalent and are simply not splittable; say so.
2. **The driver runs ONE patch; the C reports the 25-patch ENSEMBLE MEAN.** The modal patch (most stems)
   that `run_coupled_biomes.jl` picks is denser than the ensemble by FPC **1.72×** (Sahel), 1.48× (boreal),
   1.19×, 1.14×, 1.12× — the same magnitude as the biases being measured. Run each patch independently and
   average the OUTPUTS (`readcanopy_patches` in the probe); never put 25 patches' stems in one core, which
   would make them compete for light inside a single canopy (the C's `getfpar.c` is per-patch too).
   This is load-bearing: it flips Sahel's GPP verdict from **1.03 ("exact") to 0.75 (−25 %)**, and flips its
   sign relative to ADR 0052.
3. **A 10-yr-mean ratio hides canopy drift.** Under `slow = nothing` F's canopy is free-running and drifts
   −13.5 % to +64.5 % in FPC. Score **F year k against C year k** and read the ratio series' SHAPE:
   monotone = structural drift, flat-but-offset = a genuine flux-level bias. They need different fixes, and
   a mean cannot tell them apart — boreal's 1.18 mean is a run from 0.80 to 1.70; Sahel's 0.75 is a collapse
   from 1.10 to 0.59.
4. **The daily NetCDF `units` attribute lies.** It reads `gC/m2/month` / `mm/month` on files written with
   `"timestep":"daily"`; the values ARE per-day. Check by magnitude (Hainich GPP 3.27 ⇒ ~1195 gC/m²/yr,
   correct for a temperate forest) and never divide by 30.

Also: `d_nv_lai` is NOT a per-PFT stand LAI. `daily_natural.c:340` accumulates `actual_lai(pft)/npatch` and
`actual_lai_tree` (`lai_tree.c:29`) is `leaf_c*sla/crownarea*phen` — the **within-crown** LAI, no `nind`, no
crown-area weighting. Summing its bands gives a sum of within-crown LAIs. The stand basis needs the
`1/(1−exp(−k·LAI))` factor (which F already forms as `plai_i`, `fast.jl:219`).

## The S-SIDE twin — validating the COUPLED demography/traits (ADR 0054)

Same loop, different oracle: the annual `ind` parquet instead of the daily NetCDF.
`scripts/extract_biome_slow_oracle.py` (C truth, both seeds → `M_slow_oracle_{counts,traits}.csv` +
`_meta.json`) → `scripts/biome_slow_oracle_probe.jl` (the coupled run, scored in noise floors). Both are
parameterized by the `CELLS` / `M_cells.csv` registry — add a cell there, don't fork the script.

The four basis checks above **all apply**, with these S-side readings:

- **Tree-only:** grass rows are emitted with every tree field **zeroed**, so a `Type` regression is a spike
  at 0 in a trait marginal, not just noise. A strictly positive q05 on `Wooddens` is the cheap tell.
- **Per-patch, not per-cell:** Component S's count target is `n_living` per **(Cell, Patch, Year)** and the
  coupled driver runs ONE patch, while the C emits **25**. Score against the per-patch ensemble MEAN. The
  per-cell total is ~25× larger; the driver's own modal patch is 1.6–2.0× the ensemble mean stem count.
- **Year-matched:** three of five cells drift monotonely; their 10-yr means read 1.2–1.4 and hide it.
- **The >5 m population:** `fwriteoutput_ind.c:84` emits only `height > height_min = 5 m`. Self-consistent
  with the count target, but it is not the stand's total stem number.

**Cross-check the population against a second extractor.** The 2010 per-cell totals must equal
`M_cells.csv`'s `n_trees` (122 / 282 / 214 / 272 / 276), which `extract_cell_individuals.py` derived through
a different code path. Two extractors agreeing on one population is the evidence the filter is right; it is
a CI assertion in `biome_coupled_tests.jl`.

### ⚠ NEVER score a recursive emulator free-running without the TEACHER-FORCED arm

A coupled rollout is a recursion: the count DRF's prediction becomes next year's `n_prev` feature. In the
**training table** `n_prev` is the C's OWN previous `n_living` (`build_slow_runtime_table.py:572`), never a
prediction — so a free rollout is off that basis by construction and integrates any one-step bias without
bound. Arm B overwrites `s.n_prev` with the C truth after each year (a driver-level write to a public mutable
field; nothing in S's `slow.jl` is touched) and splits the error:

    free − forced = the AR-recursion amplification      forced − 1 = the per-year model on F's own features

Measured at ADR 0054: the recursion is **59–72 %** of the total coupled count error in all five cells, and
forcing it flattens boreal 1.12→1.74 into a flat 1.12–1.17. Skipping this arm would have indicted a count
model that is actually within 0.2–3.9 noise floors. The same arm is the ready-made before/after test for any
fix to the recursion.

### The noise floor is the only honest scale

LPJmL-FIT is stochastic (RAND48 + `-DPERMUTE`), so seed1 vs seed2 is the irreducible error. Emit **both**
seeds for every statistic and report error in floors. Watch the denominator: a tight floor makes a tiny
absolute error look enormous (Sahel SLA reads 7.9 floors = a 4.6 % error on a 0.0002 floor), and a loose one
does the reverse (Amazon's count floor is 29 % of the mean, because the cell has 4.7 trees per patch). Quote
the absolute number next to the ratio, always.

## Rules

- **Confirm the C path actually runs in the `individual=true` config before porting it** (see the
  `lpjmlfit-cbinary` skill — light/grass-competition and per-PFT-into-GPP paths are dead here).
- **Opt-in, default byte-identical:** a new physics term must default to leaving every committed baseline
  and the AD trainer unchanged (constructor kwargs default to the old behavior), until deliberately flipped
  on with an explicit baseline regeneration.
- **Gradients:** any new op must keep the `gradient_correctness` gate green (Enzyme/ForwardDiff vs
  FiniteDifferences through the rollout, no NaN/Inf). Non-smooth ops get a smooth surrogate in
  `src/fdiff_smoothops.jl` + a test bounding its deviation.
- Before chasing a fidelity residual, run the `residual-diagnosis` skill (state the reference basis + a
  falsifiable hypothesis + time-box — this is where the grass saga went wrong).
- **Provisioning a NEW cell's inputs is a different skill: `provision-coupled-cell`** (soil column from
  `whc_nat`, per-cell canopy, the `M_*` fixtures, the per-cell `d_fapar` oracle re-run, ADR 0050). This skill
  covers *validating* F_diff on a cell whose inputs already exist.

Full history of the C-validation work: `docs/phase3_fdiff_cbinary_validation.md`.
