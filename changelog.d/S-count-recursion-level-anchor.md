### Changed

- **Line M's "the count recursion is unanchored" (ADR 0054) is answered, and it decomposes into THREE
  defects with three owners
  ([ADR 0102](docs/decisions/0102-the-count-recursion-has-no-level-anchor.md)).** M measured that a
  free-running coupled rollout integrates a ~5 %/yr one-step count bias into +36–81 % over ten years, that
  teacher-forcing `s.n_prev` onto the C truth removes **59–72 %** of the coupled count error, and correctly
  refused to fix it inside `src/components/slow.jl` (line S's exclusive path, ADR 0029). Measured on the S
  side at Hainich over 150 constant-forcing years:
  - **(A) Exposure bias** — the training `n_prev` is the C's own previous `n_living` (a `shift(1)` of the
    truth) while the runtime feeds the DRF its own output. Real, but **training-side**: it needs scheduled
    sampling or dropping `n_prev` from the feature set, i.e. a global retrain. Not closable from `slow.jl`.
  - **(B) State incoherence** — `slow.jl:1026` clamps `ρ` but `:1110` assigns the **unclamped** `target` to
    `n_prev`, so a clamp-binding year desynchronises the AR state from the roster permanently. This was the
    leading hypothesis and it is **MEASURED EMPTY**: the clamp binds **0 of 150 years** and the roster
    tracks the `ρ` it was handed to `1.5e-13`. Closed; do not spend time here.
  - **(C) No level anchor — the dominant defect, and new.** `ρ` is a unit-free ratio and the roster is
    advanced multiplicatively, `D_T = D_0·Πρ_t`, so the count DRF's **absolute** skill (OOS R² 0.982) is
    used only through year-on-year ratios and its level is discarded by construction. Perturb the initial
    stand density by **4×** and the terminal densities still differ by **4.21×** after **300** identical-forcing
    years — **retention 1.036**, and the horizon sweep shows it converging to a **non-zero asymptote of
    ≈1.04** (peaking at 1.40 around year 25, then flat from year 150 to year 300) rather than decaying to 0.
    There is no restoring force — not a weak one, none. The dissociation is the finding: an `n_init` sweep
    shows the **AR state** converging (terminal spread 6.7 %, retention **0.092**, four of five seeds
    landing on an identical 6.7529) while the **physical stand** those same runs carry retains **60.2 %** of
    its spread. So the constructor docstring's "self-corrected by the `max_*` clamp thereafter" is true of
    the AR state and **false of the stand**.
  - **This completes M's own same-day decomposition (`9ad8721b`)** rather than correcting it. M split the
    +36–81 % into a recursion factor **×1.26–1.53** and a **year-1 level offset ×1.05–1.12**. What is added
    here is the level term's *fate*: teacher forcing repairs the **ratio** each year and nothing repairs the
    **level**, so that offset — and any level error acquired later — is permanent. It is visible in M's own
    numbers: the forced boreal arm flattens to **1.12–1.17**, flat but still displaced by the 1.12 it
    started with. An initialisation artifact that never decays is a free parameter, not an artifact.
  - **Consequence for the queue:** milestone **S2 (recruit conditioning) is no longer top priority**. An
    unanchored level compounds without bound and no conditioning skill can correct it, because the channel
    that would carry the correction is discarded upstream. The fix is **specified but deliberately not
    landed** — it needs the count↔density conversion (patch area) at the S↔F seam, i.e. an `interface.jl`
    addition (line M's) plus a `slow.jl` change (S's), and it moves every committed coupled baseline.
  - **ADR 0101 §5 is re-read:** the 4.5×-FIT swing from `n_init` 11.0 → 7.0 is not an artifact quirk, it is
    this recursion property. That promotes S→M integration point #2 from a provenance defect to a
    correctness one.

- **`docs/component_s_public_report.tex` — four corrections, three of them substantive.**
  - The warming-response damping is **39.9 %**, not ≈ 37 %, and the deficit is **971.5** internal units, not
    892, giving **+1461** rather than +1541. The 37 %/−892 pair was arm **B** (`p14env-hash`), the *refused*
    env arm, quoted as if it were the deployed configuration (ADR 0044 §Consequences).
  - The `Rr` **ceiling is stated on the patch-year reliability basis** (Wooddens **0.9543**, all four axes
    0.94–0.97), replacing the superseded stem-parity ceiling (0.9201, range 0.87–0.96) and the flattering
    percentages computed against it. The basis is now named in the text.
  - **New: the defect is placement, not shrinkage** — dispersion ratio **1.034** against a target of 1 while
    the pattern captures 39 % of ceiling, i.e. right-sized shifts in the wrong cells. Any lever justified by
    "fixing attenuation" is aimed at a defect that is not present.
  - **Recursive stability moves from "not yet tested — no evidence either way" to "not established
    (measured, negative)"**, and the roadmap is **reordered**: anchoring the recursion becomes item 1, ahead
    of the warming-response gap, per ADR 0102. The claim that the trait-conditioning work "is the single
    highest-value piece of remaining work" is retired.
  - A new §`sec:traitmort` reports Phase 3A honestly: the operator changes the **level** of community wood
    density by `+7 041 ± 334` (t = 21) and reproduces FIT's age–wood-density signature, while its
    contribution to the warming **response** is `+0.26 [−0.38, +0.90]` × the FIT shift — not distinguishable
    from zero. The report's standing claim that mortality is trait-blind is scoped to the *deployed*
    configuration.

### Added

- **`scripts/diagnose_count_recursion_anchor.jl`** — the three-section diagnosis behind ADR 0102:
  (a) **coherence**, the per-year `n_prev` / `target` / raw ratio / clamped `ρ` / realized-density table with
  the clamp-binding count and the cumulative AR-vs-roster divergence; (b) **anchoring**, an `n_init` sweep
  measuring whether the recursion forgets its initial condition; (c) **level anchor**, the decisive test —
  perturb the initial density and measure retention against horizon. It prints an explicit verdict for the
  "(B) is empty" outcome, because a null there is a real and reportable result rather than a failed probe.

### Fixed

- **Line M's `wscal_leafon` default flip is unblocked from S's side and pre-authorised.** M recorded it as
  "S's to schedule" and it had sat, because flipping the default reds `slow_production_drf_tests.jl`'s
  assertion that the out-of-band conditioning set is *exactly* `{water_stress}`. That assertion now admits
  **exactly the two admissible states** — `{water_stress}` with the flag off, the **empty set** with it on —
  and still fails on any third outcome, so the flip no longer needs a synchronised two-sided commit. S
  endorses it on M's own measurement (ADR 0051): Hainich's `water_stress` goes **0.3050 → 0.0034** against a
  C truth of 0.0014 and a trained band of [0, 0.04315], so the flip **closes S's last out-of-band
  conditioning column**. Expect it to move M's pinned per-cell coupled baselines — a deliberate regeneration
  under guardrail 4.

  Hainich cell 42490 only (guardrail 6), constant repeated-2010 forcing, committed demo artifact pair. No
  committed baseline, artifact, fixture or default moved; runtime `[deps]` stays empty.
