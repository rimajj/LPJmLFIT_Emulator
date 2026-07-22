---
name: fdiff-validate
description: The recurring extract -> validate -> baseline loop for checking the differentiable fast core F_diff against the LPJmL-FIT C oracle (kernel-isolation drive, Hainich cell 42490 harness, the extract_fdiff_* / validate_fdiff_* scripts, ReferenceTests baselines). Use whenever validating or refining F_diff fidelity vs the C binary, or wiring a new physics term into the daily/canopy rollout.
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

Full history of the C-validation work: `docs/phase3_fdiff_cbinary_validation.md`.
