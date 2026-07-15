---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "DESIGN.md §4.2/§9, DEVELOPMENT_PLAN.md §3/§5/§7, ECOSYSTEM_AND_COUPLING.md §6"
informed: "ADR 0011, the SSP370 datasheet"
---

# Operate in a constant-CO₂ regime

## Context and Problem Statement

LPJmL-FIT here runs `with_nitrogen="no"`. Without nitrogen limitation, CO₂ fertilization is unbounded,
so a rising-CO₂ future run makes vegetation carbon blow up. How is CO₂ handled for training and
application? See `DESIGN.md` §4.2/§9 and `ECOSYSTEM_AND_COUPLING.md` §6.

## Decision Drivers

- Physical realism / numerical stability of the *source* model (no carbon runaway).
- The OOD test must be a **realistic** trajectory, not a synthetic delta.
- Honesty about the resulting validity envelope.

## Considered Options

- **Rising CO₂** future trajectories (realistic emissions CO₂).
- **Constant CO₂** held fixed after 2019 (the SSP370 forcing uses `..._const_2100.txt`).
- **Enable nitrogen limitation** to bound CO₂ fertilization.

## Decision Outcome

Chosen: **constant CO₂** for the future runs (and thus for the emulator's regime). It is the only
option consistent with the existing `with_nitrogen="no"` ground truth and avoids the carbon runaway;
enabling nitrogen is a different (future) model. The OOD stress test is therefore **warming +
precipitation variability at constant CO₂**, using the real SSP370 GCM trajectory
([SSP370 datasheet](../src/model/datasheets/ssp370.md)).

### Consequences

- Good: stable, physically bounded ground truth; a *realistic* OOD trajectory (not a stylized delta).
- Good: SpeedyWeather's lack of a carbon cycle becomes a **non-issue** — CO₂ is not a varying coupling
  variable and `NBP_atm` is diagnostic-only.
- Bad (inherited limitation): the emulator is valid **only** at constant/near-historical CO₂ and
  **must not be used to project CO₂-fertilization responses** — stated in every write-up.
- Bad: a future N-limited version (cf. NeuralCrop's N cycle) would be needed for CO₂-response
  projections.

## More Information

This is a *carried-forward limitation*, listed in `DESIGN.md` §9 and the docs
[Limitations](../src/explanation/limitations.md) page.
