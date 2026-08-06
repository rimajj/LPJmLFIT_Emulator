# ADR 0057 — the 5-biome coupled driver moves to the PATCH ENSEMBLE, and the modal-patch artifact is 1.01–1.06× on LE but up to 1.33× on GPP

* **Status:** Accepted
* **Date:** 2026-08-06
* **Line:** M (multi-cell coupled S+F+E) · ADR block 0050–0069 (tier 1)
* **Decides:** **(1)** `scripts/run_coupled_biomes.jl` — the production 5-biome coupled driver — and the CI
  gate that pins its per-cell signatures (`biome_coupled_tests.jl` item 2) now run **every patch of the
  cell's canopy independently and average the outputs**, which is the basis the C itself reports.
  **(2)** The pinned per-cell LE/GPP signatures are **regenerated** on that basis (a deliberate baseline
  move under guardrail 4, in its own commit). **(3)** Named single-member gates and probes stay on the
  **modal patch on purpose** (§4) — this is a decision, not an omission, and each carries the reason at
  its reader.
* **Related:** ADR 0053 (measured the modal-patch artifact on the F-side oracle and made the ensemble the
  M-line comparison basis), ADR 0054 / ADR 0055 (the S-side oracle and the resilience battery, both already
  ensemble-driven), ADR 0056 (the anchor verdict, measured on the ensemble), CLAUDE.md §6 guardrail 4
  (opt-in / default byte-identical — a baseline move must be deliberate and attributable) and guardrail 7
  (state the reference basis first)
* **Evidence:** `scripts/biome_ensemble_pin_probe.jl`, job **1716587** (2 yr, 5 cells, 125 patch-runs,
  10.6 s) — it measures BOTH bases in one run. Driver re-run: job **1716592**. CI-faithful suite:
  job **1716594**.

## 1. The reference basis, stated first

LPJmL-FIT simulates each cell as **25 replicate patches** and every gridded output it writes is the
**patch-ensemble mean** — that is the quantity every C-side fixture in this line carries
(`M_fdiff_oracle_biomes*.csv`, `M_slow_oracle_counts.csv`, `M_resilience_battery.csv`). The coupled driver
instead built its core from the single **modal** patch (the one with the most living trees, i.e. the
*densest*), a choice that was never argued for — it came from the original single-cell Hainich harness,
where one patch was the point.

ADR 0053 already measured what that costs on the F-side oracle (modal FPC **1.12–1.72×** the ensemble) and
moved the *oracle probes* to the ensemble. The production driver and the CI signatures were left behind.
This ADR finishes that move. Nothing about the model changes; what changes is which quantity the driver
reports.

## 2. What the artifact actually is (job 1716587)

Both bases, same run, 2 years, default parameters (`wscal_leafon = false` — these feed a CI fingerprint,
not a science number), `slow = nothing`:

| cell | LE_ens | LE_mod | mod/ens | GPP_ens | GPP_mod | mod/ens | fpc_ens | fpc_mod | mod/ens |
|---|---|---|---|---|---|---|---|---|---|
| boreal_siberia | 23.94 | 24.91 | **1.040** | 1.007 | 1.340 | **1.331** | 0.294 | 0.436 | 1.480 |
| temperate_hainich | 40.45 | 41.37 | 1.023 | 3.445 | 3.662 | 1.063 | 0.564 | 0.642 | 1.137 |
| mediterranean_iberia | 46.62 | 49.27 | **1.057** | 5.056 | 5.382 | 1.064 | 0.440 | 0.538 | 1.223 |
| semiarid_sahel | 33.18 | 33.49 | 1.009 | 0.3859 | 0.3819 | **0.990** | 0.189 | 0.299 | **1.588** |
| tropical_amazon | 116.11 | 119.26 | 1.027 | 6.925 | 7.564 | 1.092 | 0.657 | 0.760 | 1.156 |

Three things in that table are worth keeping:

* **The artifact is far bigger in carbon than in energy.** LE moves ≤ 5.7 %, GPP up to **33 %**. LE is
  supply-limited (soil water) or demand-limited (available energy) in every one of these climates, so it
  is buffered against canopy density; GPP is not. A driver validated only on the energy partitioning would
  have concluded the basis "barely matters".
* **The size of the FPC artifact does not predict the size of the flux artifact.** `semiarid_sahel` has the
  **largest** density artifact (1.588×) and the **smallest** flux artifact in the set (GPP 0.990, i.e. the
  denser patch produces *slightly less* carbon) — its GPP is water-limited, so extra leaf area buys nothing.
  `boreal_siberia` has a smaller density artifact and the largest GPP one. Density → flux is
  climate-dependent; do not convert one into the other.
* **The modal patch is biased in one direction by construction.** It is selected as the densest patch, so
  it reads high on Rn (more absorbed radiation) and, at four of five cells, on both LE and GPP. This is a
  *selection*, not sampling noise — averaging more patches would not have fixed it.

**The ratio is also HORIZON-dependent.** The driver's own 10-year run (job 1716592) gives
`mod/ens` = 1.078 / 1.030 / 1.006 / 0.997 / 1.018 on LE and 1.267 / 1.049 / **0.961** / **0.821** / 1.040 on
GPP — the mediterranean and Sahel signs flip relative to the 2-year table above as the denser patch's own
drift (ADR 0053) accumulates. So the artifact cannot be carried as a per-cell correction factor at all:
re-run on the ensemble, never rescale.

**Harness check (what makes this a measurement and not a re-record):** the same job, on the modal basis,
reproduced the *currently committed* pins to every printed digit in all five cells — `24.9117 / 1.34002`,
`41.3672 / 3.66247`, `49.2742 / 5.38191`, `33.4942 / 0.381906`, `119.264 / 7.56402`. So the probe provably
drives the gate's own configuration, and the new numbers differ only in the basis.

## 3. What moved

* `scripts/run_coupled_biomes.jl` — per-cell and legacy-common-Hainich arms both ensemble-driven; Bowen is
  formed from the **ensemble-mean H and LE** (a ratio of means, which is what a gridded H/LE comparison is;
  a mean of per-patch ratios diverges on any patch whose growing-season LE approaches zero). A `mod/ens`
  table is printed beside the results so the old basis stays visible rather than being silently dropped.
* `test/testitems/biome_coupled_tests.jl` item 2 — drives all 25 patches, asserts the Phase-4 energy gate
  **per patch** (25× more closure evidence than before, at 10.6 s for the whole 5-cell set), and pins the
  ensemble-mean LE/GPP. The pins stay a driver-level fallback detector: min pairwise separation is
  **13.2 %** on LE (gate rtol 2 %) and **27.0 %** on GPP (rtol 3 %).
* `scripts/biome_ensemble_pin_probe.jl` — new, committed, and the thing to re-run whenever these pins have
  to move again.

## 4. What deliberately stays single-member

A gate belongs on the ensemble only if it makes a claim about a **level** that the C reports. These make
member-**invariant** claims, so the ensemble would buy nothing and cost 25×:

| stays modal | why |
|---|---|
| `biome_coupled_tests.jl` item 3 (M2) | carbon closure at the S↔F handoff, energy closure, determinism under seed, the DRF's structural output range, the ClimBuf's per-cell forcing — none is a level |
| `rollout_stability_tests.jl` (coupled 60-yr) | boundedness, "no limit cycle", "the oscillation does not grow" |
| `resilience_battery_tests.jl` (both items) | recovery is monotone and bounded; the cluster probe behind the fixture (`biome_resilience_probe.jl`) is already full-ensemble |
| `scripts/wscal_leafon_probe.jl` | kept modal ON PURPOSE so it still reproduces the numbers ADR 0051 published; both arms run the same patch and differ only in the flag |
| `scripts/boreal_soilice_probe.jl` | compares a seasonal SHAPE ("high all year vs a winter collapse"), not a level |

Each of those files now carries that reason at the reader, pointing here. **The rule to carry forward: a
canopy basis is part of a result's reference basis (guardrail 7) — state it where the number is produced,
because a modal-patch number and an ensemble number are not comparable and nothing in the code makes the
difference visible.**

## 5. Consequences

* Every level this driver printed before today was on the denser modal patch. Numbers quoted from it in
  earlier line-M notes are **≈1.0–1.08× high on LE and up to 1.33× high on GPP** — re-run rather than
  rescale, since §2 shows the ratio is cell-, variable- AND horizon-specific (it even changes sign).
* The F-side biases in `lines/M/STATE.md` item 5 are unaffected: they were measured by
  `biome_fdiff_oracle_probe.jl`, which was already on the ensemble (ADR 0053).
* Item 3's inbound `SEBParams.enable_two_layer` (ADR 0074, line E) moves these same pins. It is the **next**
  change, with its **own** commit and its own regeneration — bundling the two would make neither
  attributable (guardrail 4). Re-measure between them with `scripts/biome_ensemble_pin_probe.jl`.
* The driver still runs at the package **default** `wscal_leafon = false`. That is unchanged by this ADR and
  remains line S's flip to schedule (ADR 0051); any *science* number off this driver must pass
  `wscal_leafon = true` explicitly and say so.
