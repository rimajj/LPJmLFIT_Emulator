### Changed

- **Component E: the two-layer prognostic ground-heat column is now the DEFAULT** (`SEBParams.enable_two_layer`,
  ADR 0075). This answers line M's pre-registered ask (ADR 0058 §5) and closes the two-scheme split the
  repository has been running since. Guardrail 4 is re-served by the **opt-out** — `enable_two_layer = false`
  reproduces the pre-E7 closure exactly, so every published pre-E7 number stays reproducible — and
  `lambda_g` / `tau_soil` are inert under the default. Daily step, four PLUMBER2 towers: H R² up at three of
  four sites (DE-Hai 0.035 → 0.645, AU-ASM 0.329 → 0.775, AU-Tum −0.478 → −0.362), G R² up from −4…−39 to
  +0.07…+0.72 at **all four**, Rn flat within 0.005. The pre-registered criterion **fails at AU-Rob**
  (0.069 → −0.176), the one site ADR 0073 had already excluded from scoring H (`ε_obs` −47.5 W/m²; its two
  `λ_g` targets disagree 13.6×; the fitted `λ_g = 1.0` arm fails there too) — recorded in ADR 0075 §1 rather
  than smoothed over. Stateless callers, including E's committed P2 tower gate, are unaffected **by
  construction**: `solve_seb` never reads the flag.

### Fixed

- **`scripts/e_two_layer_probe.jl`: the sub-daily `z1 = 0.2 m` control arm omitted `z_soil1` and so silently
  tracked the package default.** Honest while that default was 0.2 m; the moment ADR 0074 set it to 0.75 m the
  arm labelled `z1=0.2` became a duplicate of the 0.75 m arm (visible as two byte-identical thickness arms in
  `e7_two_layer_probe_v5.txt`). Consequence: ADR 0074 §6's sub-daily `T_skin` figures are at 0.2 m, not at the
  shipped default — at 0.75 m the cost is larger (AU-Tum 0.773 → 0.547, AU-Rob 0.385 → **−0.116**). Corrected
  in ADR 0075 §4, re-measured in report `_v6`, and captured in the `plumber2-reference` skill.

### Added

- Component E gate pinning ADR 0072's night-cold sign **under the new default**, where it deepens rather than
  disappears (towers: −0.95 → −3.17 K at AU-ASM, −1.99 → −3.67 K at AU-Tum, −1.09 → −2.03 K at AU-Rob;
  synthetic diurnal cycle −1.474 → −2.496 K), so the outstanding canopy-heat-storage term trips it.
- Daily-step `T_skin` per site in the two-layer probe — never pinned before, though `run.jl` solves once per
  day: R² 0.981 → 0.979 (AU-ASM), 0.900 → 0.851 (AU-Tum), 0.858 → 0.793 (AU-Rob).
