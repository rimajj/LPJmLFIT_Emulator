### Added

- **Sized the selection already absorbed into the recruit copula's training target — a pre-registered
  condition that had gone unchecked for two weeks ([ADR 0118](docs/decisions/0118-the-recruit-copula-already-carries-the-selection-arm-c-would-add.md)).**
  [ADR 0025](docs/decisions/0025-component-s-recruit-trait-copula.md) §3 trains the copula's trait marginals
  on LPJmL-FIT's *surviving* stems and wrote its own expiry condition — *"if trait-dependent mortality is
  ever added, this training target must change"*. Arm C is that change, and no decision record in the
  0047→0049→0117 chain cites it. `scripts/diagnose_copula_selection_confound.py` measures the
  entry→survivor displacement on 197.7 M historic + 828.8 M ssp370 surviving tree stems, both ground-truth
  members, all four live trait axes, with no refit and no new model run (jobs 1754705/1754709, ~7 min each).
  Within a cell-PFT group the displacement is **+12.18 % on wood density** — the exact axis
  [ADR 0049](docs/decisions/0049-trait-mortality-wired-in-the-count-channel-bounds-it.md)'s flip criterion is written on —
  and **0.56 of it does not cancel in a warming response**; the other three axes are ≤ 0.9 %. Because
  uniform thinning (the arm's null) is exactly the trait-blind design the survivor marginal was matched to,
  the bias lands on the arm and not on its null, so **`C1 − C0` may no longer be reported as "how much of
  the trait response is selection"**; the flip criterion gains two pre-registered conditions (read the tilt
  θ first, and test the per-PFT gradient *shape*, which a uniform double count cannot fake). The
  composition control is what makes the panel readable: pooled, rooting depth (−49.6 %) and the drought
  threshold (−35.9 %) look catastrophic and collapse to −2.4 % / +0.4 % within cell, so ~95 % of that is
  *where young stems live* rather than selection. Every figure is a **lower bound** — the tree table drops
  stems below 5 m, so selection before that height is invisible. Seed agreement ≲ 2 % throughout. Also
  scopes arm D: it inherits the double count, and its motivating 2–3× goodness-of-fit win has **no
  committed reproducer** in this repo and appears to compare oracle-fitted moments against out-of-sample
  predictions, making it an upper bound rather than a realizable gain. Changes no code, artifact or default.
