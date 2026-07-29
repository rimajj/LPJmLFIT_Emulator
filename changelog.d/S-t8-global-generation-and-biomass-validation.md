### Added

- **Component S: the emulator's BIOMASS and SIZE distributions are now validated per-cell out-of-sample**
  (ADR 0036). An opt-in `STRUCT_AXES=agb,Height` adds per-stem aboveground biomass and height to the
  `MODE=copula` table as appended diagnostic axes, so they get the same K-fold-BY-CELL OOS treatment as the
  four production recruit traits — plus new figures `12_biomass_percell` / `13_map_biomass` and
  `metrics_biomass.txt`, where predicted stand biomass is composed from the emulator's two halves
  (`OOS count x OOS per-stem agb`) and reported against LPJmL-FIT's own per-patch `sum(agb)`.
  The axes are **structurally excluded** from the serialized production `.rcop` that line M pins (ADR 0025),
  and the production axes' OOS predictions are **bit-identical** with the option on or off (gated by a
  50-cell smoke that `cmp`s them).
- `scripts/run_slow_validation_figures.sh` — the whole validation figure set for a generation (historic +
  ssp370 + pooled) plus one self-contained HTML report, as ONE SLURM job.
- `scripts/build_slow_validation_report.py` — inlines a generation's figures and `metrics*.txt` into a single
  portable HTML page (a reporter: every number is read verbatim from the metrics files).
- `scripts/run_pooled_slow_copula.sh` gained the `DEPENDENCY=afterok:<jid>` knob the other three
  orchestrators already had.

### Changed

- **The GLOBAL Component-S tables and artifacts are re-derived as generation `t8`** on the ADR-0035 feature
  bases (`soilmoist` = root-zone year-end plant-available fraction of WHC; `lai` = the per-patch
  reconstruction), for historic, SSP370 and the pooled multi-regime pair. `_t7` is untouched; line M re-pins
  deliberately.
- `noise_floor_vs_emulator.py` reports the ADR-0030 floor / ceiling / dispersion arithmetic for the structure
  axes too, tagged `[diag]` and strictly outside the gate's verdict and exit code.
- Figures 09-11 size their panel grid from the axis count instead of a hard-coded 2x2 (which would have
  silently dropped any axis past the fourth), and switch to log axes for heavy-tailed axes.

### Fixed

- **`build_slow_runtime_table.py`: a silent row-set corruption in the global count tables.**
  `polars` `collect(engine="streaming")` is not deterministic in the KEY SET it emits at global scale (only
  its float-sum jitter was documented): two ssp370 builds over the same `ind` parquet produced 99 023 397 vs
  99 028 310 rows — 141 cells differed, 4 913 rows missing, 12 cells with DUPLICATED keys — and the AR
  self-join amplified each duplicate into four rows. The existing coverage guards structurally could not catch
  it, because duplication makes `dropped = h_before − h_after` go negative so a `drop_frac` test never fires.
  Now a hard `(Cell,Patch,Year)` key-set invariant fails the build loud, and the AR lag is taken with a window
  shift instead of a 100M x 100M self-join (gated: rebuilding the historic table reproduces the shipped one
  with `y`/`cells` byte-identical and `X` to 0.000e+00 relative difference). The affected per-scenario ssp370
  artifact was rebuilt; its OOS R² is unchanged at 0.9823.
- Documentation corrections that were substantive, not cosmetic: `STEM_CAP` is a patch-year **cluster**
  subsample, not the per-stem sample it was documented as (so the stand-biomass composite is refused for the
  pooled pair, whose two tables weight the scenarios differently); the biomass `basis_ratio` is an exact
  identity on matched rows and therefore a **row-universe** check, not the `Cov(N, mean size)` correction it
  was described as; figure 06 is not a distributional check, because the count DRF is scored with a
  conditional mean; and the default (non-transient) boundary is the 2000-2019 historic climatology for BOTH
  scenarios.
