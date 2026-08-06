# ADR 0058 — M adopts E's two-layer ground-heat column: it is an H/G repartition, not a coupled-physics change, and it removes a persistent +6.4 W/m² ground sink the default scheme had no reservoir for

* **Status:** Accepted
* **Date:** 2026-08-06
* **Line:** M (multi-cell coupled S+F+E) · ADR block 0050–0069 (tier 1)
* **Answers:** **ADR 0074** (line E), the integration point E raised when it shipped
  `SEBParams.enable_two_layer` and recommended line M enable it — which **supersedes** ADR 0073's
  `lambda_g = 1.0` request, itself superseding ADR 0072's refuted `stab_amp` one. **Neither of the earlier
  two is live; do not act on them.**
* **Decides:** **(1)** M's coupled world runs the two-layer column: `scripts/run_coupled_biomes.jl` and
  `biome_coupled_tests.jl` items 2 and 3 pass `SEBParams(enable_two_layer = true)` **explicitly**.
  **(2)** The **package default stays `false`** — `src/components/energy.jl` is line E's exclusive path and
  flipping it moves E's own tower gates. Flipping it is raised back to E in §5 with the M-side evidence and
  a pre-registered criterion (guardrail 4's corollary: an opt-in whose default is known worse is a defect
  on a timer). **(3)** The named gates in §4 stay on the default scheme because they score against fixtures
  measured under it; regenerating those is scheduled, not silent.
* **Related:** ADR 0074 (the scheme + its tower evidence), ADR 0073 (the diagnosis: `sd(G_m)` 5–7× the
  observed, no soil thermal inertia), ADR 0072 (the P2 verdict + the night-cold sign pin), ADR 0057 (the
  patch-ensemble basis these numbers are on), ADR 0055 (the resilience/rollout fixtures still on the old
  scheme), CLAUDE.md §6 guardrails 2, 4 and 7
* **Evidence:** `scripts/two_layer_coupled_probe.jl`, jobs **1716625** and **1716628** (the re-run after
  the drift metric was corrected, §3). Two arms differing ONLY in `enable_two_layer`, driven through the
  real `run_coupled_cell`. Part 1: five biome cells × 25 patches × 10 yr. Part 2: 60-yr cyclic rollout at
  the coldest and hottest column. Pins re-measured by `scripts/biome_ensemble_pin_probe.jl` with
  `TWO_LAYER=1`, job **1716621**. Suite: job **1716629**. Driver on the new configuration: job **1716630**.

## 1. Two questions, both stated falsifiably before the run

E's evidence is tower-side (497 k half-hourly steps, 4 sites) and it stands. What only M can measure is
what the scheme does **inside the coupled loop**, where E's `H := Rn − LE − G` residual sits downstream of
F's LE and upstream of F's `T_skin` feedback:

* **Q1 — what actually moves?** *Prediction:* LE and GPP move by **< 1e-3 relative** (F's ET is water- or
  demand-limited in all five climates and its `T_skin` sensitivity is weak) while H moves by O(1–10) W/m².
  If LE/GPP move more, this is a coupled-physics change needing its own baseline regeneration, not a
  repartition.
* **Q2 — does the closed column drift?** `step_soil_column!` has a **closed bottom** (ADR 0074: "no deep
  restore"), so the two layers integrate the net annual ground-heat flux with nothing pulling them back.
  ADR 0074 §5 checked this on tower records of 4–16 yr, where climate variability and drift are entangled.
  Under a **strictly cyclic** forcing they are not: a periodic forcing means any trend is the model's own.
  *Prediction:* |dT2/dt| < 0.05 K/yr and decaying.

## 2. Q1 — it is an H/G repartition (and the default scheme was leaking energy into the ground)

10 yr, 25-patch ensemble, `slow = nothing`, package-default parameters otherwise (job 1716625):

| cell | dLE/LE | dGPP/GPP | ΔH W/m² | ΔG W/m² | ΔT_skin K | ⟨G⟩ def → 2layer | sd(G) def → 2layer |
|---|---|---|---|---|---|---|---|
| boreal_siberia | −5.4e−06 | −4.8e−05 | −1.862 | +1.298 | +0.080 | **−1.369 → −0.071** | 64.2 → **9.0** |
| temperate_hainich | −7.3e−07 | −6.7e−06 | +0.101 | −0.161 | +0.004 | +0.156 → −0.006 | 30.6 → **4.4** |
| mediterranean_iberia | +2.2e−05 | +1.3e−04 | +1.348 | −1.437 | +0.008 | +1.422 → −0.015 | 29.1 → **4.0** |
| semiarid_sahel | +4.6e−09 | −2.6e−07 | **+5.900** | **−6.433** | +0.081 | **+6.425 → −0.008** | 16.7 → **2.3** |
| tropical_amazon | −5.2e−12 | +5.7e−11 | +0.136 | −0.142 | +0.001 | +0.142 → −0.000 | 7.2 → **1.1** |

**Q1 PASSES with three orders of margin** — the largest LE change is 2.2e−5 and the largest GPP change
1.3e−4, against a 1e−3 threshold. Energy closes at 2.8e−14 in every patch and both arms (guardrail 2).

The finding worth more than the pass is the **⟨G⟩ column**. Under a repeating forcing a soil column must
take up **zero** net heat per year. The default scheme cannot honour that — its reference is a 30-day EWMA
of *air* temperature, which has no memory of what the ground already absorbed — and it runs a **persistent
+6.4 W/m² sink at `semiarid_sahel`** for ten straight years, ~7 % of that cell's Rn, with no reservoir
behind it. The two-layer column drives ⟨G⟩ → 0 **by construction** (it is the reservoir), and hands the
energy back to H: Sahel H **58.2 → 64.1 W/m²**. So this is not only "better G": it removes a standing
misattribution of H in the driest cell.

`sd(G)` falls by **6–7×** in every cell — the same defect ADR 0073 measured against the towers
(`sd(G_m)` 5–7× `sd(G_o)`), now confirmed to be present in the coupled model at five biomes, and closed.

**Consequence for the baselines:** ADR 0057's regenerated LE/GPP pins move by **≤ 4e−5 relative** under the
new scheme (job 1716621). They are re-pinned to the two-layer arm's exact values because that is the
configuration the gate now runs, but they provably **do not discriminate the two schemes** — the honest
statement of what those pins detect is a per-cell *input* fallback, not an energy-scheme change. The
handoff's expectation that this change "moves every coupled and 5-biome baseline" was **wrong in the
direction that matters**: it moves H and G, which nothing in M's gate set pins.

## 3. Q2 — no drift; and the first metric I wrote answered a different question

Phase-matched over the 60-yr cyclic rollout (job 1716628):

| cell | arm | T2 at yr 10 → 60 | dT2/dt overall | dT2/dt tail | AGB_end/AGB_1 |
|---|---|---|---|---|---|
| boreal_siberia | def | −7.0975 (inert) | 0 | 0 | 5.709 |
| boreal_siberia | 2LAYER | −6.4090 → −6.4188 | **−1.9e−4 K/yr** | −8e−5 | 5.708 |
| semiarid_sahel | def | 29.8896 (inert) | 0 | 0 | 1.091 |
| semiarid_sahel | 2LAYER | 30.6340 → 30.6243 | **−2.0e−4 K/yr** | −2.0e−4 | 1.091 |

**Q2 PASSES by ~250×**, the boreal tail rate is less than half its overall rate (equilibration, not a
runaway), the column settles within the first decade, and the 60-yr AGB ratio is unchanged between arms —
so the rollout-stability gate's boundedness claims are untouched. Energy closes at 2.8e−14 over 60 years.

**The first version of the drift metric was wrong, and it is worth recording why.** It read
`(T2[end] − T2[end−9])/9` and reported **0.222 K/yr** — a factor of ~1000 above the phase-matched truth —
because the committed forcing is a **10-year cycle** and years `end` and `end−9` sit at *different phases*
of it. The same trap made the raw `T1(y1) = −31.57` vs `T1(y60) = −25.73` look like a 5.8 K drift when it
is phase 1 vs phase 10 of the seasonal cycle. **Under a cyclic forcing, compare only years an integer
number of cycles apart.** The printed per-cycle series is what caught it — a single summary number would
have been believed.

## 4. What deliberately stays on the DEFAULT scheme

| stays default | why |
|---|---|
| `resilience_battery_tests.jl` (all items) and `rollout_stability_tests.jl`'s AC-gap check | they score the emulator against `M_resilience_battery*.csv`, produced by a cluster probe run under the default scheme (ADR 0055). Re-running the arm changes ADR 0055's *published* numbers — a separate measurement with its own verdict, not a side effect of this one |
| every E-owned gate (`energy_closure_tests.jl`, the PLUMBER2 tower items) | E's file, E's default; ADR 0072's night-cold **sign** pin is only re-pinned when the package default flips (§5) |
| `wscal_leafon_probe.jl`, `boreal_soilice_probe.jl` | reproduce published ADR numbers on the scheme those were measured with |

This leaves the repo running **two ground-heat schemes in different gates**, which is exactly the
basis-confusion this line keeps paying for — so it is declared here, listed exhaustively, and each site
says which scheme it is on at the point the number is produced (the ADR 0057 rule, applied to E's scheme).

## 5. Back to line E: the default flip, with a pre-registered criterion

**M's ask:** flip `SEBParams.enable_two_layer` to `true` by default, and re-pin ADR 0072's night-cold sign
assertion in `energy_closure_tests.jl` in the same change. M's evidence, which is what E did not have:

* the scheme is **free** in the coupled loop — LE and GPP move by ≤ 1.3e−4 relative (§2);
* it removes a **persistent up-to-6.4 W/m² ground sink** and a 6–7× `sd(G)` inflation at five biomes (§2);
* it does **not drift** over 60 cyclic years, at −2e−4 K/yr (§3), which ADR 0074 §5 could only bound with
  entangled climate variability;
* ADR 0074 §6's cost is **sub-daily `T_skin`**, and M's operational step is **daily**, where E measured the
  `T_skin` R² as nearly flat (AU-Tum 0.864 → 0.851, AU-Rob 0.81 → 0.79).

**PASS condition (pre-registered, so this cannot quietly stall):** E flips the default iff, on E's own
tower harness, the two-layer arm's **daily** H R² is ≥ the default's at every site (already measured:
0.645 vs 0.637 DE-Hai, 0.775 vs 0.745 AU-ASM) **and** the re-pinned night-cold assertion is restated as a
measured sign rather than deleted. If E declines, the reason belongs in an E-block ADR, because M's coupled
world now runs the scheme either way and a permanent default/driver mismatch is a documented hazard.

## 6. Consequences

* Any coupled number quoted from `run_coupled_biomes.jl` from today is **two-layer ground heat + 25-patch
  ensemble + `wscal_leafon = false`**; the driver prints all three at the top of its output.
* `FToE` still carries no soil moisture, so `theta_soil` stays a constant 0.5 (ADR 0074's open E→M
  integration point). M's `FToE` is the file that would carry it — untouched here, and it is the natural
  next E↔M step now that the column is in the loop.
* `scripts/two_layer_coupled_probe.jl` is the harness to re-run whenever the scheme, `z1`, or `C` changes;
  it prints both arms, so it always re-states the control.
