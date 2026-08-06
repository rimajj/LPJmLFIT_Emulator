### Changed

- **Line M / ADR 0058 — the coupled driver adopts line E's two-layer prognostic ground-heat column
  (ADR 0074), and it turns out to be free.** `scripts/run_coupled_biomes.jl` and `biome_coupled_tests.jl`
  items 2 and 3 now pass `SEBParams(enable_two_layer = true)` **explicitly**; the package default stays
  `false` (`src/components/energy.jl` is line E's file). This closes E's fourth integration point, which
  had superseded ADR 0073's `lambda_g = 1.0` request, which had superseded ADR 0072's refuted `stab_amp`
  one — neither of the earlier two is live.

  **Two questions, both pre-registered, both measured** (`scripts/two_layer_coupled_probe.jl`, jobs 1716625
  / 1716628; two arms differing only in the flag, driven through the real `run_coupled_cell`):

  *What moves?* LE by ≤ **2.2e−5** relative and GPP by ≤ **1.3e−4** — against a stated 1e−3 threshold — so
  it is an **H/G repartition**, not a coupled-physics change, and the LE/GPP pins ADR 0057 just
  regenerated move by ≤ 4e−5. What does move is the ground-heat term itself, and the reason is worth more
  than the pass: under a repeating forcing a soil column must take up **zero** net heat per year, and the
  default scheme — whose reference is a 30-day EWMA of *air* temperature — cannot honour that. It ran a
  **persistent +6.4 W/m² sink at `semiarid_sahel`** for ten straight years (~7 % of that cell's Rn) with
  no reservoir behind it, and the two-layer column hands that energy back to H (58.2 → 64.1 W/m²) while
  driving ⟨G⟩ → 0 by construction. `sd(G)` falls **6–7×** in every cell — the defect ADR 0073 measured
  against the towers, now confirmed inside the coupled model at five biomes and closed.

  *Does the closed column drift?* ADR 0074 §5 could only bound this on 4–16 yr tower records where
  variability and drift are entangled; under M's **strictly cyclic** 60-yr rollout they are not.
  Phase-matched drift is **−2e−4 K/yr** at both the coldest and hottest column (250× inside the stated
  0.05 K/yr bound), decaying, equilibrated within a decade, with the 60-yr AGB ratio unchanged between
  arms and energy closing at 2.8e−14.

  **A metric bug worth carrying:** the first drift number was `(T2[end] − T2[end−9])/9` = **0.222 K/yr**,
  ~1000× the truth, because the committed forcing is a **10-year cycle** and those two years sit at
  different phases of it — the same trap that makes a raw `T1(y1)` vs `T1(y60)` look like a 5.8 K drift.
  **Under a cyclic forcing, compare only years an integer number of cycles apart.** The per-cycle series
  printed beside the summary is what caught it.

  ADR 0058 §4 lists exhaustively which gates deliberately stay on the default scheme (those scored against
  ADR 0055's fixtures, and every E-owned gate) and §5 hands the **default flip** back to line E with a
  pre-registered pass condition, so an opt-in whose default is now known to be worse cannot quietly stall.
