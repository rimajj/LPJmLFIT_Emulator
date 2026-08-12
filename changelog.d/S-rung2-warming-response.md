### Added

- **The rung-2 warming-response experiment (line S).** The learned demography now runs inside LPJmL-FIT's
  own physics over *both* legs of the scenario pair — historic 2000–2019 and ssp370 2020–2100 — at 15 cells
  spanning the global climate range, so the deliverable is a measured *response* rather than a present-day
  agreement number. New: `scripts/build_rung2_boundary_series.py` (the per-cell/scenario/year bioclimate the
  count model conditions on, plus the frozen-climate control), `scripts/select_rung2_response_cells.py` +
  the committed `test/testitems/references/S_rung2_response_cells.csv` (a pre-registered cell set that keys
  on present-day climate only), `scripts/run_rung2_response_matrix.sh` (the whole matrix), and
  `scripts/diagnose_rung2_response.py` (per-cell response, error-in-variables slope, Cochran's Q).
- **A frozen-climate control arm.** The two scenario legs have different lengths (20 vs 81 years), so a raw
  historic→ssp370 difference mixes a genuine climate response with 61 extra years of free-running drift.
  `BOUNDARY=frozen` reruns the ssp370 leg with the climate held at present day, so the difference between
  the two isolates the climate channel with drift removed.

### Fixed

- **The rung-2 harness conditioned every year on a frozen present-day climate.** It read its four-column
  bioclimatic tail once from the per-cell registry, which holds the 2000–2019 climatology. On an ssp370 leg
  that showed the count model present-day climate for all 81 future years, which would have driven any
  measured warming response to ~0 *by construction*. It now advances the tail per year, the same treatment
  the shipped runtime already applies (ADR 0026) and the one the pooled production model was trained under.
  Passing no series keeps the old static behaviour, so ADR 0176's arms still reproduce byte-for-byte.
- **`scripts/run_daily_subset.sh` could not generate a runnable ssp370 config at all.** Its CO2 forcing path
  named a loose file that was removed when a sibling directory was reorganised on 2026-07-27/28, so the
  branch died in pre-flight with `ERROR100: Cannot open file`. Repointed to the recovered copy and verified
  by checksum and size.
- **The recorded baseline and the arms had drifted onto different binaries.** The baseline path used
  whatever `bin/lpjml` currently is, which gained the ADR-0130 `ind`-writer switches on 2026-08-12, while
  the arms run `bin/lpjml_rung2_v6`. Baseline recording now lives in the same script as the arms and is
  pinned to the same executable by construction.
