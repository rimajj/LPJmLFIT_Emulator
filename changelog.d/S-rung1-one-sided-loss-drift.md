### Added

- **Line S (rung 1):** `scripts/rung1_drift_attribution.py` — the no-refit diagnostic ADR 0115 §6.3
  pre-registered. At a fixed lead it builds each cell's **excess drift** (the self-feeding count arm's
  `bias(ssp370) − bias(historic)` minus the one-step control's on the same rows) and attributes it to the
  cell's ssp370-minus-historic change in each conditioning feature three ways — weighted univariate
  correlation, standardised multiple regression with a VIF beside every coefficient, and greedy forward
  selection on weighted R² — always with the control's own decomposition printed beside the arm's. It
  reuses `rung1_response_decay.py`'s `lead_index` and area weights by import rather than re-deriving them,
  and opens with a reconciliation panel against ADR 0115 §3.
- **Line S:** the same script's response-decomposition panels, which are what the pre-registered form could
  not deliver: the drift regressed on **LPJmL-FIT's own** per-cell count response, the mean drift by decile
  of that response (with the cell's stem count and the level-normalised drift beside it, so a one-sided
  error is separable from one that merely scales with density), and the incremental R² of the 13 varying
  conditioning features over that response alone.

### Documented

- **ADR 0116** — the count recursion's scenario-asymmetric drift runs through the **stand-state** channel,
  and it is a **one-sided failure to follow stem losses**. The previous stem count and the mean cohort age
  carry it (univariate r −0.34 / +0.33 at lead 18) while every climate and flux feature sits at |r| ≤ 0.084;
  the one-step control decomposes differently and far more weakly (R² 0.096 vs 0.250, selecting a flux
  first, with a previous-count correlation of ≈ 0), so the channel belongs to the recursion rather than to
  the rows. The finding is the asymmetry: the arm reproduces **86.7 % of a large stem decline but 96.2 % of
  a large increase**, so with LPJmL-FIT's own global response being a net loss the rectified error surfaces
  as a spurious positive drift — the wrong-signed aggregate response of ADR 0113, explained. Controlled
  against the truth-binning confound (the excess column cancels it by construction) and against stem
  density (the extreme deciles differ 1.3× in count; the asymmetry survives normalising at 3.0×). Next
  count arm is judged on the loss side, and no climate/flux conditioning change should be proposed without
  refuting the attribution table first.

### Fixed

- **ADR 0115 §3's control row at lead 5 reads +0.024; it should read +0.031** — a one-row transcription slip
  from a CSV whose rows include lead 4, which the table's columns skip. Recorded in ADR 0116 §1 rather than
  edited in place (ADRs are immutable). No conclusion of ADR 0115 depends on it: its prose quotes the
  lead-18 excess (+0.074), which is unaffected, and the arm row reproduces exactly.
