### Changed

- **Every control arm that means the pre-ADR-0136 `gp_sum` basis now states `gp_stand_leafon_basis = false`
  explicitly, instead of inheriting it as the package default ([ADR 0136](docs/decisions/0136-the-two-gp-sum-basis-differences-measured-one-helps-one-hurts.md) §7).**
  Byte-identical today — the default has not moved — and that is the point: the explicit value is written
  *before* the flip, not after. A trial flip of the default on 2026-08-13 failed **23 assertions of
  275 621 across eight files**, and **10 of them were one file's comparisons going vacuous** rather than
  wrong: `test/testitems/gpsum_basis_tests.jl`, written one commit earlier to gate this very flag, built
  its base arm as `with_water(p0, (;))` = "the package default", so at the flip it became a second copy of
  the treatment arm and both exact-boundary identities, the fires-off-the-boundary pair and the whole
  signed-direction loop stopped comparing anything. Hardened: that testitem's four arms (each now pinning
  **both** flags), `scripts/biome_sapwood_bg_probe.jl::mkparams` — from which the `Ag`/`Pg`/`gpS`/`vmG`
  arms and all 30 committed `M_growth_channel_decomposition.csv` rows derive — and the three sibling
  probes `biome_canopy_growth_probe.jl` / `biome_resilience_probe.jl` / `biome_slow_oracle_probe.jl`.
  Generalises [ADR 0133](docs/decisions/0133-the-tree-demand-gate-default-flip-is-earned-on-the-carbon-budget-and-paid-for-in-gpp.md) §6
  from probes to tests: **if an assertion's meaning depends on two arms differing, both arms must state
  their value; take the default by omission only in an arm that means "whatever ships".**
- **`scripts/biome_ensemble_pin_probe.jl` and `scripts/regen_fdiff_baselines.jl` gained the pre-flip
  opt-out (`GPSTAND=0` / `canopy_arm(; gps = false)`), wired and inert.** Step 3 of the default-flip
  procedure requires that the run producing the new pins also reproduces the old ones, which an opt-out
  added *after* a flip can no longer do. While the default is still `false` the opt-out arm is bitwise the
  default arm, and the probes assert exactly that — which is what proves the knob is wired to the field it
  names before anyone depends on it.
- **The `gp_stand_leafon_basis` default flip itself is RAISED TO LINE S and parked, not landed.** The 23rd
  assertion is `test/testitems/slow_level_anchor_tests.jl:181` (`ret_025 > 0.7`, measured 0.619 under the
  flip) — the unanchored control's year-25 retention, which is S-owned. An F default that moves an S gate
  is an integration point ([ADR 0059](docs/decisions/0059-the-c-faithful-water-stress-becomes-the-default.md) is the precedent:
  S gave an explicit GO before `wscal_leafon` flipped), so the request, both defensible readings and the
  full 23-assertion enumeration are written into `lines/S/STATE.md`. Nothing is degraded while it sits:
  the flag remains opt-in and off.

### Fixed

- **The runbook now records that GitHub SSH auth to this remote fails *intermittently*** (`CLAUDE.md` §5).
  `git fetch`/`push` can die with `Permission denied (publickey)` — indistinguishable from a revoked deploy
  key — and succeed on the next attempt: 2 of 3 consecutive `ssh -T` calls authenticated seconds apart. The
  entry gives the three-part confirmation (derive the pubkey from the private key, check the key is still
  registered `rw` via the API, then a retry loop) and flags the second-order trap that cost the most time
  here: **when the failing call is the fetch, every remote-tracking ref answers from the last successful
  fetch**, so `git log origin/main..HEAD` can report a pushed branch as unpushed. Same discipline as the
  `/p` EIO transient — prove permanence before declaring an outage.
