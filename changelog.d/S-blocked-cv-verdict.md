### Changed

- **ADR 0042 adjudicates ADR 0040's pre-registered address-vs-response rule on the completed seven-arm forest
  matrix: RESPONSE — the six env conditioning columns are not merely a spatial address**, and the verdict is
  **final**: the second colouring's flip thresholds were recorded in the ADR *before* the deciding rung landed,
  and the two colourings' blocked deltas then agreed to 0.0024 against a 0.0157 tolerance, so the
  "NOT RESOLVABLE" clause does not fire and clause 1 is met on both colourings on all four axes. Wooddens `Δ_blocked = +0.0315` [+0.0011, +0.0633], clearing the pre-registered bar
  `0.5·Δ_hash = +0.0201`, while the pure-position control collapses 0.1868 below the treatment and 0.1553
  below no tail at all. The frozen 1-NN surrogate screen predicted ~86 % retention and the forests delivered
  78/119/137 % on the three axes with a resolvable delta.
- The salt replicate also validated the experimental design, which is the most transferable result here:
  re-colouring the spatial blocks moved the **single-arm** blocked `emu_r` by +0.0136 (half the delta under
  test) but moved the **paired delta** by only +0.0024, because the colouring effect is common to both arms and
  cancels in the difference. A blocked *level* is therefore colouring-sensitive and must not be quoted alone or
  across colourings; a blocked *paired delta* at a shared colouring is robust. Build blocked comparisons as
  paired deltas.
- **ADR 0040 §4's attribution of the transient damping to the env tail is refuted**, using the matched `p8`
  arm that ADR itself asked for: the ncond-8 baseline damps the Wooddens warming shift 39.9 % on its own. Its
  §5 promotion gate is therefore simultaneously *met* and *mis-specified* — passable by a change that degrades
  the transient — and is re-specified on `Rb` **and** `Rr` **and** `|Ra − 1|` at both fold modes. Under the
  re-specified gate the tail fails: `Rr` (transient pattern) flips sign with fold design, +0.0395 at hash to
  −0.0305 at blocked. The two gates dissociate — the level delta survives blocking, the transient one does not.
- Line M's re-pin refusal **stands on new grounds** (the old ones are refuted); the request to fix
  `extract_cell_slow_init.py`'s `cond_cols[-4:]` check to the positional `cond_cols[4:8]` is unchanged.
- Corrects two ADR 0040 statements: `eco_diag_gdd_5`/`tas_cold_month` **are** time- and scenario-varying on the
  `pooled_w20` tables the forests read (per-cell constants only in `cell_year_feats.parquet`), and the single
  "spatial-sampling sd of order 0.01" is superseded by a measured 0.004–0.006 (hash) / 0.012–0.016 (blocked).

### Fixed

- `scripts/diagnose_slow_address_prereg.py` built its bootstrap tile-cluster labels through a join that
  returns rows in the latlon frame's order while the statistic's arrays are in `group_by` output order, with a
  `tl[:min(len(tl), len(dy))]` truncation absorbing any length mismatch. The labels were a permutation of the
  rows they clustered, which degenerates a tile bootstrap toward an independent-cell bootstrap and
  **understates** the spatial sd — the exact error the clustering exists to remove. Point estimates never
  touch the labels, so only the CIs were wrong. Detected because `cluster_boot` has a fixed seed yet two runs
  over identical inputs printed different intervals. Fixed with a cell-indexed lookup plus a length assertion,
  and verified by running each gate twice and diffing: both now byte-identical. The re-measured intervals are
  3–5× wider and materially change what may be claimed — the blocked-fold damping is no longer significant,
  and no inter-arm difference is resolvable from marginal CIs (a paired difference bootstrap is the missing
  statistic, noted as a caveat with its fix).
