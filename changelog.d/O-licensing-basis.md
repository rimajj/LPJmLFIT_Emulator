### Added

- **The project's licensing basis — order P5 is done ([ADR 0080](docs/decisions/0080-licensing-basis.md)).**
  **Outbound = AGPL-3.0-or-later**, and it is *forced* rather than chosen: it is simultaneously what
  LPJmL-FIT's AGPL-3.0 copyleft requires of a derivative work and a licence the **EUPL-1.2 Appendix** names
  as a "Compatible Licence", so EUPL Art. 5's compatibility clause sanctions combining with Terrarium.jl and
  SpeedyWeather.jl (**both EUPL-1.2** — verified upstream, not MIT). That makes the position valid whether or
  not a package dependency counts as a derivative work — the question EUPL Art. 1 explicitly leaves to
  national law — which is the main reason a permissive outbound licence was rejected. **Terrarium.jl's
  `NOTICE` extends Art. 5 to *any* licence for "the normal use of the Work as a library"**, so taking it as
  `[weakdeps]` + a package extension is clean: **P4 (online coupling) is unblocked**, with runtime `[deps]`
  still empty (ADR 0014). The ADR separates **READ / DEPEND / VENDOR** as three different acts with different
  rules — vendoring third-party code now requires its own ADR — and fixes NeuralCrop.jl as *method-only*
  permanently (CC-BY-NC's NonCommercial term cannot be combined with AGPL-3.0 §7, so a work derived from both
  would be undistributable) and LPJ_resilience as reimplement-from-paper (unlicensed ⇒ all rights reserved).
  ADR 0017 is **annotated, not superseded**: its licensing driver was only ever about the VENDOR tier, and its
  outcome stands on its two independent drivers. New operational companion
  `docs/third_party_licensing.md` — the inbound-work register (licence, tier, *how it was verified*,
  obligation) plus the mandatory before-you-take-a-dependency checklist, driven by the new
  `dependency-license-gate` skill.

### Fixed

- **Two third-party attribution defects found by the ADR 0080 audit** (comment-only; behaviour and every
  committed baseline byte-identical, guardrail 4). (1) The TBPTT trainer described itself as "the finished
  port of NeuralCrop.jl's `train_loop_rollout!` scaffold" (`ext/FDiffTrainingExt.jl` ×3,
  `src/LPJmLFITEmulator.jl`, `src/fdiff.jl`) while the same sentence said "no code copied" — and NeuralCrop.jl
  is CC-BY-NC, so an inaccurate provenance claim is itself the exposure. A direct comparison against
  `NeuralCrop.jl/src/training/training_loop.jl` confirmed **no shared expression**: the only overlap is
  `Zygote.withgradient` → finite-loss guard → `Optimisers.update` in a windowed day loop, i.e. those
  libraries' documented API plus TBPTT itself (Williams & Zipser 1990), while the reference spreads jld2
  chunk loading, per-cell batching, `ps_frozen`, device dispatch, an LR schedule, a validation split and
  checkpointing across 19 positional arguments and lacks our detached-state carry (`_advance_state`). The
  wording now states independent implementation with NeuralCrop cited as prior art. (2)
  `patches/json_object_iterator.h.shim` contains verbatim declarations from json-c's public header but
  carried no MIT notice; json-c's copyright + permission notice is now reproduced in it.
