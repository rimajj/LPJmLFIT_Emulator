### Added

- **Rung 2's substitution half — the LPJmL-FIT C binary can now accept an external demography**
  (line M, ADR 0120). A second opt-in hook (`LPJ_RUNG2_APPLY_DIR`) hands each patch's tree roster to
  an external process at the top of the annual demography block, blocks for its answer, and applies a
  kill set plus a complete recruit set; `MORT_C` / `ESTAB_C` defer either half back to the C so a
  divergence is attributable. Committed as `patches/lpjmlfit_rung2_hook_v2.patch`, which supersedes
  `patches/lpjmlfit_rung2_demography_hook.patch` (retained for the provenance of the previously gated
  binary). With both environment variables unset the binary is numerically identical to the previous
  one — 139 decoded quantities plus `globalflux`, 0 differ, re-checked after each rebuild.
- `scripts/rung2_replay_harness.py`, `scripts/run_rung2_replay_arm.sh` — replay LPJmL-FIT's own
  recorded demography back to it through the hook, in four arms (`kills`, `recruits`, `both`, `none`).
- `scripts/diagnose_rung2_replay_identity.py`, `scripts/diagnose_rung2_dump_equality.py` — score a
  replay arm against the run it replays, and compare two roster dumps column by column.

### Fixed

- Two columns of the rung-2 roster dump are **uninitialised memory** and must not be read (ADR 0120):
  `sapwood_old` is a dead struct field that LPJmL-FIT never writes or reads, and the `mort_*` columns
  are meaningless for any tree that has not yet been through `mortality_tree_ind` — which includes
  every recruit at the `post` of its own establishment year, correcting ADR 0061's wider claim that
  they are valid at `post`.
