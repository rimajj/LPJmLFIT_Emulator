### Added

- Component S: `scripts/diagnose_slow_response_power.py` — the first PAIRED tile-cluster bootstrap of the
  warming-response statistics (`Rr`/`Ra`/`Rb`), gated on reproducing all seven ADR-0042 arms from their
  stored predictions (achieved to ≤5e-5). Closes ADR 0042 §10 caveat 7b.
- Component S: `scripts/diagnose_wooddens_shift_decomposition.py` — decomposes LPJmL-FIT's own
  historic→ssp370 wood-density shift into PFT composition / within-PFT / interaction, and the within-PFT
  part further over age classes, plus the selection differential and the age–trait gradient.

### Changed

- Component S: the reliability ceiling used by every "% of ceiling" claim is corrected. Patch-year-parity
  split-halves (reconstructed exactly from runs of identical broadcast `Xc` values, needing no `Year`
  column) raise the Wooddens ceiling 0.9201 → 0.9543 and lower the deployed arm's dispersion ratio
  1.0728 → 1.034 (ADR 0044).
- `CLAUDE.md` §3: the claim that FIT draws recruit traits uniformly from per-PFT intervals is replaced —
  establishment is a two-channel mixture that is 44–80 % **inherited** from the live community
  (ADR 0045). §9 gains the `priority`-partition/QOS limits.

### Fixed

- Component S: `Rb` is demoted to a veto-only criterion. It is unresolvable as a paired delta
  (`sd_paired` = 533 blocked) and a zero-information permutation buys it at 3.30σ, so "the damping fell
  from A % to B %" is inadmissible in every form (ADR 0044).
