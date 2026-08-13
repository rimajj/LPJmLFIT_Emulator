### Added

- **Rung-2 gross-budget demography arms `G0`/`G0h`/`G1`** (`scripts/rung2_s_demography_harness.jl`, ADR
  0240). The same three mortality operators as `S0`/`S0h`/`S1`, asked for a GROSS kill budget spent from a
  per-patch running account (`acct += (1−ρ)·n_tree + #{age == 1}`) instead of the net count change. Four
  columns appended to `s_arm_log.txt` (`n_age1 budget rho_eff acct`); the pre-existing arms are
  byte-identical.
- `scripts/diagnose_rung2_gross_account_identity.py` — the derivable a-priori gate on those arms: the
  account identity row by row (451 161 patch-years, max |diff| 0) and the uniform arm's spend ratio
  against its derived 1.000.
- `scripts/check_rung2_campaign_coverage.py` — which legs of a rung-2 campaign finished, and the re-run
  lines for the rest. A healthy run never prints `harness: served <N>`, so that line's absence is not a
  failure signal; the C's own completion line plus the arm log's patch-year count are.
- `diagnose_rung2_kill_budget.py` panel F — nomination rate, the empty-budget gate, two lumpiness columns
  and the MEASURED roster horizon that ADR 0189 §7a requires beside every kill rate.

### Fixed

- **An empty patch deadlocked the rung-2 harness.** `read_request` took the `(year, patch)` identity from
  the tree rows, but a patch with no living trees emits no `T` record, so the response was written under
  `rsp_…_y-0001_p-01` while the C waited for the real name and died 600 s later on `ERROR043: rung2 apply:
  no answer`. Cost 53 of 360 legs; latent for the whole rung-2 investigation because no `S*` arm ever
  empties a patch. The identity now comes from the `P grow` record, the tree rows are checked against it,
  and a request whose identity is still negative is refused instead of answered.
- `run_rung2_s_arm.sh`: the harness idle timeout is now `MAXIDLE` (default 300 → **900 s**), which must
  exceed the C's own 600 s apply timeout, and is interpolated into the job file so a run records what it used.

### Changed

- One exported `ARMS` (comma or space separated) now widens `diagnose_rung2_map_target_response`,
  `kill_budget`, `kill_selectivity` and `anchor_preflight` together, defaults unchanged so every published
  table reproduces. The pre-registered verdict arm sets (`LEARNED`, `OPERATOR_ARMS`) deliberately do not
  follow it.
