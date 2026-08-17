### Added

- **What the ported death-rate equation actually needs to be fed — measured, and the answer is that the
  emulator's current inputs are not enough
  ([ADR 0243](docs/decisions/0243-which-of-the-hazards-inputs-the-standalone-emulator-needs.md)).**
  The previous decision record showed that giving every tree the original model's own one-year death
  probability reproduces its stem count and biomass to ~4 % over 81 years — but inside that harness the
  equation is handed the original model's own two accumulated stress signals (how much water shortfall
  and how many too-hot/too-cold days each tree experienced through the year), which the standalone
  emulator does not compute. `scripts/diagnose_rung2_hazard_inputs.jl` prices that gap with no model run:
  the same shipped equation is re-evaluated on **1 389 207 tree-years** of state already on disk, on
  identical trees, under five input variants. The blessed number is the fraction of the deaths the
  original model's own stand is asking for that the equation still nominates. **On the inputs the coupled
  emulator hands it today (both stress signals zero) that fraction is 0.78 — a 22 % shortfall, which
  fails the tolerance derived from the earlier measured relation between a mortality shortfall and the
  biomass it lets accumulate (0.867).** The water signal is responsible for 2.4–2.8× more of it than the
  temperature one (dropping water alone costs 14–16 percentage points, temperature alone 6–8), and the
  two are additive to 2e-4, so they can be costed and wired independently. The shortfall is a
  **dry-cell** effect, not a global level error: the two stress terms are 31 % of the original's total
  death probability pooled, but 67 % at one cell (where the nominated fraction falls to 0.46) and 0.05 %
  at another. Three checks make the number trustworthy — a derivable identity check passes first (the
  equation reproduces the original's own probability to 9e-16), a free derivable inequality holds with
  informative slack (a third of the discarded stress mass lands on trees that die anyway), and the answer
  is the same measured on the original's stand and on the emulator's own. **The trees that stop dying are
  the tall ones:** the shortest fifth of the stand keeps 86 % of its nominated deaths while the taller
  four fifths lose 26–38 %, which is exactly where the earlier records located the excess biomass, and a
  tilt like that cannot be absorbed by a scale factor. Also measured, and unexpected: **the
  consecutive-bad-years counter each tree carries is worth more than the temperature signal** (9 vs 6
  percentage points), so a fresh rollout under-hazards its declining trees while that counter fills. And a
  cheap-looking shortcut is closed — the annual water index the emulator already has explains under a
  quarter of the variance of the daily integral it would stand in for. **The machinery for the missing
  signals already exists and is switched off**, behind a chain of three flags of which two silently
  defeat it: switching on the one that names them, without the two that supply the per-tree daily water
  status, reproduces the zeroed case with no error and no warning — raised to the physics line as a
  fail-loudly request. ⚠ What this does **not** show: the cost of the emulator's OWN stress signals, which
  no stored state can carry. It brackets that case between 0.78 and 1.00 and says so; it establishes only
  that the death-rate operator cannot run on zeros. No `src/**` change, no flag flipped, no default moved.
