# ADR 0085 — The online `plant_available_water` field is CLAMPED, so O3b's convergence check is VOID, not passed

* **Status:** accepted
* **Date:** 2026-08-14
* **Line:** O (online coupling)
* **Supersedes:** nothing. **Amends** the O3b reading in `lines/O/STATE.md` and narrows ADR 0082 §4.
* **Relates to:** ADR 0082 (online is ESM-first, validated against observations), ADR 0083 (the
  prescribed soil texture + degeneracy guard), ADR 0035 (line S: `soilmoist` is `w` over the top
  1 m at year end, not `swc`), ADR 0023 (train/inference consistency).

## 1. Context — the pre-registered question, and why the obvious answer is wrong

O3b's open item was a **`soilmoist` train/inference shift** for Component S. `soilmoist` is a
trained feature of the learned demography model; online the soil is Terrarium's, so the online
field must be the *same quantity* as the one the model was trained on, not merely a wetness index.

The previous handoff had measured the 30-day run (job 1706597) at root-zone PAW `q50 0.109 /
q75 0.338 / q90 0.681 / mean 0.199` against LPJmL-FIT's live reference `q50 0.498 / q75 0.877 /
q90 0.9999 / mean 0.478`, i.e. an upper half **2.4–4.6× too dry**, and it pre-registered a
disjunction:

> Compare 1706979's distribution against the table above — **if they agree, the run has converged
> and the gap is real; if 1706979 is drier again, it is still draining.**

Job **1706979** (90 days, `RichardsEq`, 19.46 m column, exit 0, 8697 s) returned
`q50 0.1085 / q75 0.3376 / q90 0.681 / mean 0.1892`. The quantiles agree with the 30-day run **to
four significant figures**. Read literally, the pre-registered rule fires "converged ⇒ the gap is
real" and the next step would be to raise a train/inference shift with line S — which, under the
S→M artifact contract, means S retrains the learned demography model and the trait sampler on a
version-bumped online soil-moisture basis.

**That would have been wrong, and the cost of being wrong is a retrain on a bogus basis.** The
disjunction is incomplete: it assumes a static distribution can only mean a converged physical
balance. It can also mean the *diagnostic* is saturated.

## 2. Decision

**O3b is VOID in the vegetation-free configuration. Do not score the online root-zone PAW
distribution against LPJmL's `soilmoist_ye`, and do not report a train/inference shift to line S.**
The comparison is re-gated behind a configuration in which the diagnostic is measurably
informative; the gate is the scorer named in §5 and its `INFORMATIVE` verdict.

## 3. The evidence — four measurements, all from data already on disk, no new simulation

`FieldCapacityLimitedPAW` is `W = min(max((θw − θwp)/(θfc − θwp), 0), 1)` — **clipped at both
ends**. A layer at or above field capacity reports exactly `1.0`; a layer at or below wilting point
reports exactly `0.0`; in both cases the reported value is independent of how much water is
actually present. If every layer of the root zone sits at one of those two clamps, the
thickness-weighted root-zone mean can only take the `nlayer + 1` values of the cumulative-thickness
ladder

```
ladder[m] = (Σ of the top m layer thicknesses) / (total root-zone thickness)
```

— one value per position of a sharp wetting front. For the O3b geometry
(`ExponentialSpacing(N=30, Δz_min=0.05, Δz_max=2.5)`, 10 layers within 1 m, 0.9876 m) that ladder
is `0, 0.050628, 0.108546, 0.174868, 0.250709, 0.337586, 0.437019, 0.550425, 0.681045, 0.829891, 1`.
The layer thicknesses are read out of Terrarium's own `get_spacing`, not hand-derived (guardrail 5),
and the scorer gates their sum against the depth the run itself logged.

| # | measurement | 30 d (1706597) | 90 d (1706979) |
|---|---|---|---|
| 1 | land columns lying **exactly on that ladder** (\|Δ\| < 1e-5) | **92.5 %** (1838/1987) | **94.0 %** (1867/1987) |
| 2 | distinct root-zone PAW values over 1987 columns | 66 | 59 |
| 3 | mass on the **4** commonest levels | 90.4 % | 90.3 % |
| 4 | root zone at **exactly 0.0** (bone dry) | 46.4 % | 47.9 % |

and between the two runs:

| # | measurement | value |
|---|---|---|
| 5 | land columns **bit-identical** in root-zone PAW across 60 extra simulated days | **90.8 %** (1805/1987) |
| 6 | whole-column mean saturation over land | 0.240026 → 0.240194 (**+0.070 %**) |

⇒ The field is a **10-level step function of the infiltration-front depth**, and 90 % of it sits at
one of four front positions (`m = 0, 2, 5, 8`). It is not a moisture distribution. Its quantiles
were unchanged from 30 to 90 days because the diagnostic is clamped, not because a balance
converged — the *water* is not necessarily static (measurement 6 shows it barely moved either, but
that is a separate fact; measurement 5 alone cannot distinguish the two, which is exactly the
inferential trap).

**The dominant levels match the ladder measured from the SURFACE DOWN**, so the wet layers are the
*top* ones: water arriving at the surface wets the top layers to field capacity while the rest of
the root zone stays at residual — a stalled infiltration front, not a drying-from-above profile.

## 4. Why — the mechanism, and the part of it that is a configuration choice

Two contributors, one of which is ours:

1. **There is no transpiration sink.** `diagnose_soilmoist_shift.jl` runs `vegetation = nothing`,
   deliberately: Terrarium's default `VegetationCarbon` crashes a coupled run on
   `MedlynStomatalConductance`'s `@assert abs(vpd) > 0` (`online-coupling-env` trap 5). So the only
   sinks are bare-soil evaporation at the very top and gravity drainage, and the only source is
   surface precipitation. In LPJmL-FIT, transpiration removes water from *throughout* the root zone
   every day, which is the mechanism that holds layers in the intermediate `(θwp, θfc)` band where
   PAW is informative at all. **Removing vegetation does not merely remove a feedback — it removes
   the process that populates the range of the quantity being measured.**
2. **The plant-available window is narrow.** SURFEX gives `field_capacity − wilting_point ∈
   [0.0519, 0.0893]` volumetric over the 4608 columns (the ADR 0083 guard already prints this). A
   layer traverses the entire informative range on ~7 % volumetric water change, so any sharp front
   reads as binary at layer resolution.

(1) is a configuration choice on line O's critical path; (2) is a property of the soil
parameterisation and is not by itself a defect.

## 5. Consequences

* **The O3b "2.4–4.6× too dry" number is retired as a fidelity statement.** It is a statement about
  a step function's quantiles. It was never quoted outside this line; the inbound note in
  `lines/S/STATE.md` correctly said no action was needed from S unless the distributions differed
  materially, and **that condition is now not met — it is not yet measurable.**
* **New committed scorer:** `scripts/online_coupling/diagnose_paw_clamping.py`. Post-hoc, reads the
  candidate CSVs, needs no simulation, ~1 s. Reports the ladder fraction, the level histogram, the
  front-depth distribution and the cross-run bit-identity, and **exits non-zero on `CLAMPED`**, so
  it can gate the comparison rather than merely inform it. Lints clean under the repo's real rule
  set (`E,F,I,UP,B`, line length 100).
* **O3b is re-gated, not abandoned.** The order of work changes: **O3c (the photosynthesis spike)
  and O4 (water-limited ET) now come BEFORE the `soilmoist` comparison**, because a transpiration
  sink is a precondition for the comparison being meaningful, not an independent milestone. This is
  a reordering within line O and needs nobody else.
* **The re-entry gate is pre-registered here, before the arm exists:** re-run the comparison only
  when the scorer reports `INFORMATIVE` (< 50 % of land columns fully clamped) **and** the
  whole-column mean saturation moves by > 1 % between two run lengths. Both are properties of the
  run, not of the answer, so they cannot be re-read after seeing the arm.
* **Guardrail 7 / `residual-diagnosis` gains a case.** The reference basis was correct here (ADR
  0035's live table, root-zone, year-end) and the comparison was still void, because the basis
  discipline as written checks *the reference*. This adds the mirror-image check: **confirm the
  quantity being measured is not saturated at its own clamps.** A clipped diagnostic is
  indistinguishable from a converged one by any statistic computed on it alone — it takes either a
  second run (bit-identity) or the structural ladder test above.

## 6. What this does NOT claim

* It does **not** claim Terrarium's hydrology is wrong. Under no transpiration, a stalled front and
  a bimodal profile are the *expected* behaviour, not a bug.
* It does **not** claim the online soil will match LPJmL once vegetation is in. That is the open
  question; this ADR only establishes that it is currently unmeasurable.
* It does **not** revisit ADR 0082's decision that PAW (not `saturation_water_ice`) is the right
  variable. `min((θw−θwp)/(θfc−θwp), 1)` is still exactly LPJmL's `w` semantics; the finding is
  about the *state* the variable is being evaluated in, not the variable.
* Measurement 6 (whole-column saturation +0.070 %) is reported as an observation. Whether the soil
  is receiving realistic precipitation from SpeedyWeather at all is **not established here** and is
  the natural next probe; it is not needed for this ADR's verdict, which rests on the ladder
  structure.
