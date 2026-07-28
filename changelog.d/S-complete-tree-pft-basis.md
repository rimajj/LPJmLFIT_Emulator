### Fixed

- **Component S now trains on LPJmL-FIT's COMPLETE tree PFT set (`Type ∈ 0..6`)** — ADR 0031. `TREE_TYPES` was
  `[1,2,3,4,5]`, a stale-yaml port defect that silently dropped the tropical broadleaved evergreen (id 0) and
  the boreal larch (id 6): **32.5 % of survivor tree stems** and **16.7 % of tree-bearing cells** (the tropical
  belt + the Siberian larch zone) were invisible to the emulator. Measured on the seed2 historic copula table,
  the widening takes it from 133.5 M stems / 45 072 cells to **197.8 M stems / 54 058 cells**, and `minwscal`
  from the truncated `[0.025, 0.30]` span to FIT's true `[0.025, 0.75]`.
  The constant now lives in **one** place (`lpjmlfit_emulator.data.TREE_TYPES`); `features.py`,
  `python/config/config.yaml` and every `scripts/build_slow_*.py` / `noise_floor_vs_emulator.py` **import** it
  instead of re-declaring it, so the two copies that caused the defect cannot drift again.
- **`growth_eff` now matches the runtime's zero-leaf-area guard** (`fast.jl:369`
  `leaf_area > 0 ? applied/leaf_area : 0`), replacing a `÷ max(lai, EPS)` divisor that turned a joined
  `LAI_STAND == 0` into `applied_npp × 1e6` — a train/inference shift on a primary mortality driver (ADR 0023).
  The C oracle guards it the same way (`mortality_tree_ind.c:95`). The previously **unexplained** seed1-vs-seed2
  asymmetry is now diagnosed: there is exactly one `cell_year_lai_*` table and it is **seed1-derived**, so
  joining it onto seed1 `ind` is self-consistent (**0** of 23.9 M tree groups hit `lai == 0`) while seed2 hits
  21 501 groups / 204 867 stems. Under the new rule that same seed2 build maxes at 4.3e4 instead of 1.19e9,
  right at seed1's 3.1e4. A `GROWTH_EFF_MAX` assertion now fails the build loud, because the coverage guards
  structurally cannot catch it (a zero `lai` is *present*, not missing).
- **All seven tree PFTs' mortality parameters are now `[VERIFIED]` per-PFT** in
  `scripts/build_slow_flux_table.py::PFT_PARAMS`, read from the active `par/pft_lpjmlfit.js` by a brace-depth
  parse that reproduces the previously-verified beech row as its own cross-check. Adding ids 0/6 exposed that
  the old dict applied temperate/angiosperm values to *every* id and was therefore also wrong for ids 1, 2, 4
  and 5 — most sharply id 5, whose longevity is **125**, not `TREE_LONGEVITY` 400 (a 3.2× age-mortality error),
  and whose `mort_water_factor` is 20, not 5. An unknown `Type` now raises instead of silently taking
  temperate defaults.

### Added

- `scripts/verify_hainich_demo_artifacts.sh` — the byte-identity gate (guardrail 4) for any Component-S
  pipeline change claimed to be a no-op at the prototype cell. Regenerates all four committed Hainich demo
  artifacts and gives a **two-tier** verdict: `PASS`, `FAIL` (the edit moved the table), or `STALE-FIXTURE`
  (the fixture was already out of date) — a one-tier gate cannot tell those apart.
- `scripts/diagnose_slow_table_drift.py` — the control for that gate: builds the same single-cell table with
  `build_slow_runtime_table.py` as of a git `REF` and with the working tree, and diffs `X` column-by-column.
  Answers "did my edit change the table, or was the fixture already stale?" with a measurement.
- `scripts/diagnose_lai0_growth_eff.py` — the `lai == 0` / `growth_eff` census per seed and per tree
  population, and the reproducer for the cross-seed-join diagnosis above.
- **`VERSION=<tag>`** on `run_global_slow_{training,copula}.sh` and `run_pooled_slow_{training,copula}.sh`:
  suffixes every table dir, artifact and log so a retrain on a changed basis writes **new versioned files**
  and line M re-pins deliberately (ADR 0029/0031), instead of overwriting artifacts M depends on.

### Changed

- ADR 0031's global re-derivation runs on the `t7` artifact generation
  (`…_t7.drf` / `…_t7.rcop`, `slow_{count,copula}_*_t7/`). The pre-0031 artifacts are retained unchanged; every
  global Component-S fidelity number published before this is on the truncated population (ids 1–5,
  45 009 cells) and is superseded by the re-measured `t7` numbers, not silently restated.
