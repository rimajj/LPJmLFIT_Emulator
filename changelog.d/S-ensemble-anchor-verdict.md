### Changed

- Component S — the level anchor's default question is **closed**: the flip criterion re-registered in
  ADR 0104 §7 was run on the 25-patch ensemble and **fails at all three settings**, so `anchor` stays
  opt-in and default `0` (ADR 0105). Most of the level defect it was built for was the modal-patch
  initialisation the earlier measurement started from: free-running terminal density/truth across the five
  biome cells is 1.04–1.38× (and 0.52× at the Sahel) on the ensemble, against 1.55–3.01× on the modal
  patch. No code, artifact, baseline or default moved.

### Added

- `scripts/exposure_bias_probe.jl` — prices the exposure-bias retrain **offline** from the existing `_t8`
  tables (one-step bias `b`, AR gain `g = ∂pred/∂n_prev`, and the implied compounding `b(1−g^k)/(1−g)`)
  before anything is spent on training. Its verdict: the bias is **empty** (−0.0014 stems/patch/yr
  held-out-cell OOS on counts of ~10, `g = 0.56` ⇒ a bounded 2.28× amplification), so the retrain is
  cancelled rather than deferred (ADR 0105 §5).
- `scripts/biome_slow_oracle_probe.jl` — REPORTS 8 and 9: the same five biome cells run with **one
  ensemble member per patch** (the basis the C reports and the count model was trained on), scoring the
  ADR 0104 §7 criterion clause by clause and splitting the residual with a teacher-forced arm. The modal
  reports are unchanged and reproduce ADR 0104's published numbers in the same run, so the two bases are
  visible side by side.
- `scripts/biome_resilience_probe.jl` — the memory clause's PASS/FAIL is now computed in-script, including
  its new per-pair tolerance, instead of being read off the table by hand.
