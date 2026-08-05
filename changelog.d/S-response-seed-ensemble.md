### Changed

- **The Phase-3A response arm is now a SEED ENSEMBLE, and ADR 0100's response contribution does not survive
  it ([ADR 0101](docs/decisions/0101-the-response-arm-needs-a-seed-ensemble-and-the-baseline-defect-was-cell-scope.md)).**
  ADR 0100 handed forward a falsifiable prediction — re-run its 2×2 against the global `pooled_w20`
  artifacts and `|R_ctl|` should shrink or flip. It does. But running it also exposed that the number being
  predicted was never resolvable from one run:
  - **`SEED` was hard-coded to 1.** Exposed as a knob, the double difference has a **seed sd of 0.67–1.74×
    the FIT reference shift — the same size as the effect.** Holding the seed common across the four corners
    does *not* pair them (`sd(Δ_ssp)` 2 419 ≡ `sd(interaction)` 2 452 gC/m³; the rosters diverge after
    year 1), so replication is the only variance lever: ~8 seeds resolve a 1×-FIT effect, **~115** the 0.26×
    actually measured.
  - **The operator's contribution to the warming RESPONSE is indistinguishable from zero on both global
    artifacts** — `+0.048 [−0.380, +0.476]` (historic-only, n = 12) and `+0.263 [−0.377, +0.903]`
    (`pooled_w20_t8`, the pair line M pins, n = 12). **Both CIs exclude ADR 0100's `+1.40×`**, and even on
    ADR 0100's own demo artifact the 8-seed CI `[−0.100, +2.812]` straddles zero. Its `+1.398` was a *fair*
    draw — 0.03 from that artifact's mean — with ~6× overstated precision. **Phase 3A's Stage-3 response
    claim is withdrawn; `+1.40× FIT` must not be quoted.**
  - **ADR 0049's LEVEL claim is confirmed and strengthened:** `+6 718 ± 286` / `+7 041 ± 334` /
    `+8 959 ± 862` gC/m³ across the three artifacts, `t` = 10.4–23.5. Replication makes this one *stronger*.
  - **ADR 0100's headline finding was a single-cell FIXTURE artefact, and the sign reverses on a global
    artifact.** `R_ctl` = `−1.234 [−2.058, −0.411]` on the demo pair (significant, so ADR 0100 §2 was real
    *for its artifact*) but **`+0.417 [+0.050, +0.784]` — FIT's own sign — on the global historic-only pair**,
    and `−0.000 ± 0.367` on the pooled one. The deployment defect is milder and different: *no* warming
    response where FIT has +1×, which is a conditioning-set question (milestone S2).
  - **The attribution was wrong: cell scope, not scenario coverage.** demo → global-historic with the
    scenario held fixed gives `ΔR_ctl = +1.651 ± 0.386` (`t` = +4.28); global-historic → pooled with the
    scope held fixed gives `−0.417 ± 0.403` (`t` = −1.03). The mechanism is in the metadata: cross-**cell**
    pooling widens the `soilmoist` trained band **4.79×** (0.209 → 1.002) while adding the entire ssp370
    scenario widens it **−0.04 %**. ⇒ **an excursion diagnostic localises a channel; it does not identify
    which axis of the training design to change.** ADR 0100 §5's measurement was right and its causal
    reading was not.

### Added

- **`scripts/run_response_seed_ensemble.sh`** + **`scripts/summarize_response_seed_ensemble.py`** — submit
  and reduce a response ensemble. The summarizer reports mean ± SEM, `t` and a 95 % CI with `n`, derives the
  three response numbers from the four 2×2 corners (and self-checks them against the log's printed ×FIT
  values, catching the unit bug of re-scaling an already-scaled ratio), refuses to mix artifacts or initial
  conditions in one ensemble, and **excludes** rather than averages any run that violated a precondition.
- **A second precondition on any response measurement (ADR 0101 §2):** *hard kills = 0 and count-override
  (shortfall) years = 0*, alongside ADR 0048's merge dormancy. Changing only `n_init` 11.0 → 7.0 fires
  6 hard kills plus one count-override year and swings the operator's contribution from `+0.756×` to
  `−3.714×` FIT — the hazard stops redistributing a DRF-set count and the double difference measures a
  different object.
- `test/testitems/references/S_response_seed_ensemble.csv` — the 32 per-seed rows behind every number above
  (three artifacts, all four corners, both preconditions per row).
- `scripts/trait_mortality_arm_probe.jl` gains `SEED`, `DRF_ART`/`RCOP_ART`, `N_INIT`/`AGE0`/`BOUNDARY`.
  `SEED=1` on the committed demo pair reproduces ADR 0100's primary **to the digit** (`R_ctl` −5 945.79,
  `R_arm` −2 545.21, interaction +3 400.58), so the ensemble is a superset of that measurement rather than a
  different harness. Two messages that asserted the *demo* artifact's properties as if they were the
  harness's were fixed: "not inert ⇒ out-of-band extrapolation" (which mis-reported a correctly-trained
  artifact as broken — the global artifacts' boundary channel is live *and* in band, worth 1 105 gC/m³ mean
  on the historic-only pair and 3 165 gC/m³ = 1.30× FIT on the pooled one, against the demo's **exactly 0.0
  in all 8 seeds**, a harder confirmation of ADR 0100 §4 than the single run it had), and the claim that the
  boundary rows always read `Inf`.

### Fixed

- **S→M integration point #2 (raised, not yet landed):** the `pooled_w20` artifact ships **no
  `cell_meta.parquet`** — its meta names one that does not exist — and its two training sub-tables disagree
  on Hainich's per-cell seed (`n_init`/`age0` 11.0/43.556 vs 7.0/46.0), a **4.5× FIT** swing in the measured
  response. `M_slow_init_meta.json` silently resolves this to the well-behaved branch (so nothing is broken
  in M's current pin) and takes its **boundary row** from `slow_runtime_historic_t8` — a table the pinned
  artifact was never trained on (gdd5 1 863.7 vs the training basis's 1 698.0, 23 % of the warming signal) —
  while on that artifact the boundary channel is worth **3 165 gC/m³ = 1.30× FIT** on ensemble average.
  Either ship a pooled `cell_meta.parquet` or record the substitution and its consequence in the pin's
  provenance.

  Hainich cell 42490 only (guardrail 6); `trait_mortality` stays opt-in and default-off; runtime `[deps]`
  stays empty; `MODE=stage2` is untouched and remains the ADR-0049 regression; no committed baseline moved.
  Nothing here may be quoted against the ADR-0044 global gate — which ADR 0101 now argues is the *only*
  right instrument for a response claim, with the required replication count measured.
