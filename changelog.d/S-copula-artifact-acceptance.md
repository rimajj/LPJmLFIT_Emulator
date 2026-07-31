### Added

- `scripts/rcop_acceptance_probe.jl` — acceptance test for a **production** recruit-trait copula artifact,
  run in a FRESH process against the shipped `.rcop` + its sidecar `_meta.txt`. `train_slow_copula.jl`
  already round-trips the bundle inside the process that built it, with the forests still in memory; that
  proves serialization is self-consistent but not that a later process can use the file. The probe closes
  that gap: it times the load, checks every axis forest's `nfeat` against the header `ncond`, cross-checks
  the sidecar's `ncond`/`cond_cols`/`axes`, reproduces the golden `(seed, x)→draw` pairs, rebuilds the
  conditioning row through the actual runtime policy (`live_flux_cond` or `live_flux_cond_env`) and asserts
  it equals the artifact's own fallback row, and confirms a wrong-width row is REJECTED rather than
  silently answered. On `recruit_copula_global_historic_t9.rcop` (484.5 MiB): **load 6.77 s = 71.6 MiB/s
  measured** (an earlier handoff's "~12 s at 42 MB/s" was an unmeasured estimate), all checks PASS.
- `scripts/score_slow_copula_dispersion.py` — the **seed1-only** between-cell statistics (`emu_r`,
  `sd(pred)/sd(Y1)`, OLS slope) with an A/B diff of two prediction sets on one basis. The ADR-0030 gate
  needs a **seed2** realization for its ceiling, `%GAP` and `r_center`, and a seed2 table exists for
  `historic` ONLY — so criterion 2 (the under-dispersion axis the whole S2 milestone is about) was not
  measurable for the `pooled` artifact line M pins. This measures it. The per-cell reduction is IMPORTED
  from `noise_floor_vs_emulator.percell_table` rather than reimplemented, so it cannot drift from the
  gate's own definition; it prints, rather than hides, that criteria 1 and 4 stay unmeasured without a
  seed2.

### Fixed

- **The copula env-augment dropped every manifest-named sidecar except `cells.i64`
  (`scripts/build_slow_copula_env_augment.py`).** `pooled` tables carry `scenario_tag  scenario.i64` (the
  per-row scenario label `eval_slow_copula_scenario_holdout.jl` splits on), and the symlink loop handled
  only `Y_*.f64` + `cells.i64`. A pooled augment therefore produced a table whose copied manifest still
  declared `scenario.i64` while the 337 MB file was absent from the output — a dangling reference that
  TRAINS fine (the trainer never reads it) and only fails later in the scenario-holdout eval, far from the
  cause. Sidecars are now resolved BY NAME from the manifest, missing-in-source is a hard error, and a
  post-write assertion re-checks that every name the emitted manifest declares resolves in the output.
  First exercised building `slow_copula_pooled_w20_t8env`.
- **The copula sidecar meta hard-coded the 8-column conditioning policy
  (`scripts/train_slow_copula.jl`).** Its header line always read `Conditioning order = live_flux_cond
  (4 flux drivers + boundary tail)`, which is correct only while every artifact is 8 wide. A 14-column
  artifact is built by `live_flux_cond_env`, so the one human-readable statement of the train/inference
  contract named the WRONG runtime policy — precisely the silent shift ADR 0023 warns about. The line is
  now derived from `ncond`.
