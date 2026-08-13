# ADR 0138 — The C's `tstress < 1e-2` photosynthesis gate is mechanically negligible: closing ADR 0135's shortlist item (b) without a port

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** M
* **Related:** ADR 0135 (the shortlist this closes an item of), ADR 0136 (the residual it is measured
  against), ADR 0131 (the *other* gate in the same call — `gpd > 1e-5`, which IS live), ADR 0126
  (the per-PFT parameter table this reads `temp_photos`/`temp_co2` from)

## Context

ADR 0135 established that F_diff's light input to tree photosynthesis is faithful, so the measured GPP
excess lives in the kernel, and left a shortlist of three candidate terms. Item (a) (the λ-solve Vcmax
basis) was closed by ADR 0136. This record closes **item (b)**: the C hard-zeroes photosynthesis when the
temperature-stress scalar falls below a threshold, and F_diff has no such branch.

The C applies the threshold **twice**, both live in the `individual=true`, carbon-only configuration with
no `config->` guard on either:

* `src/lpj/photosynthesis.c:54-61` — `if(tstress<1e-2) { *agd=0; *rd=0; if(comp_vm) *vm=0; return 0; }`
* `include/pft.h:341` — `#define isphoto(tstress) (tstress>=1e-2)`, consumed at
  `src/lpj/water_stressed.c:196`.

F_diff (`src/fdiff.jl:503 temp_stress`, `:541 photosynthesis`) has no threshold at all: `tstress`
multiplies `c1`/`c1o` linearly and that is the whole of its effect. A source comment at
`src/fdiff.jl:234` already asserted that this makes "that HALF of the C's gate already emulated" — an
argument from code structure, never measured. This record measures it.

## Decision

**Do not port the gate.** It is an **accepted limitation**, recorded and closed, not an opt-in flag.
ADR 0135's item (b) is struck from the photosynthesis queue; only item (c) (the phenology trajectory)
remains open.

## The measurement

Three findings, two of them closed-form and therefore independent of any cell set.

### 1. F's `agd`, `rd` and `vm` are *exactly* proportional to `tstress`

In the C3 path `c1 = tstress·alphac3·(…)` while `c2` contains no `tstress`; hence `vm ∝ c1/c2`,
`je ∝ c1`, `jc ∝ vm`, the co-limitation solution for `adt` is homogeneous of degree 1 in `(je, jc)`, and
`rd = b·vm`. The SLA-Vcmax cap is the only nonlinearity and cannot bind at `tstress < 1e-2`, where `vm`
sits >100× below its unstressed value.

**Verified against F's own kernel, not only read off the source** — `FDiff.photosynthesis` at
`tstress = 1e-2` returns exactly 1e-2 of its `tstress = 1` value for `agd`, `rd` *and* `vm`, to
**1.6e-9**, at both a winter (−8 °C, 2 MJ/m²) and a growing-season (15 °C, 8 MJ/m²) day.

⇒ **the C's gate discards at most 1 % of what that same day would carry at full temperature
suitability.** This is the ceiling on the whole term, before any cell is looked at.

### 2. At the hot end the gate is redundant *by construction* — F already carries that cutoff

`temp_stress.c:38` sets `k3 = ln(99)/(temp_co2_high − temp_photos_high)`, so
`high(temp_co2_high) = 1 − 0.01·e^{ln 99} = 0.01` **exactly**, and `low ≈ 1` at warm temperature. So
`tstress(temp_co2_high) ≈ 1e-2` = the threshold: the gate fires precisely where the
`if(temp < pftpar->temp_co2.high)` **hard cutoff** already fires, and F_diff carries that cutoff as a
sigmoid (`fdiff.jl:514 gate_co2`).

⇒ **the gate's only live content is the cold end.**

### 3. The cold end is unreachable at three of five biome cells and negligible at the other two

Cold-end threshold, closed form (`high ≈ 1` ⇒ `tstress = low = 1e-2` at `T* = k2 − ln(99)/k1`):

| PFT | `temp_co2` low/high | `T*` |
|---|---|---|
| 0 tropical broadleaved evergreen | 2 / 55 | **+3.0 °C** |
| 1–6 (every other tree) | −4 / 38–42 | **−6.0 °C** |

Scored over each cell's own committed 10-yr daily forcing and its own PFT composition, weighting each
day by `tstress · swdown` (assimilation is linear in `apar` to first order) and setting `phen = 1` on
every day — which **inflates** the answer, because gated days are deep-winter days where GSI phenology
drives `phen` towards 0 while the growing-season denominator sits near `phen = 1`:

| cell | tree PFTs | `T_min` | `T*` | gated days | **bound on gated share of annual assimilation** | verdict |
|---|---|---|---|---|---|---|
| `boreal_siberia` | 4, 5, 6 | −54.4 | −6.0 | 1721 / 3650 | **0.0460 %** | CAN BIND |
| `temperate_hainich` | 1, 2, 3, 4, 5 | −15.0 | −6.0 | 74 / 3650 | **0.0063 %** | CAN BIND |
| `mediterranean_iberia` | 1, 2, 3 | −1.9 | −6.0 | 0 | 0 | CANNOT BIND |
| `tropical_amazon` | 0 | +23.5 | +3.0 | 0 | 0 | CANNOT BIND |
| `semiarid_sahel` | 0 | +20.2 | +3.0 | 0 | 0 | CANNOT BIND |

**The three zeros are structural, not empty probes** (residual-diagnosis: an exactly-zero effect is a red
flag, never a result). Iberia's coldest day in ten years is −1.9 °C against a −6.0 °C threshold; the two
tropical cells are 100 % PFT id 0, whose threshold is +3.0 °C against minima of +20.2 and +23.5 °C. The
scorer prints `T_min` beside `T*` and computes the `CAN BIND` / `CANNOT BIND` verdict itself.

⚠ **`boreal_siberia` is the case that makes the point.** 47 % of its days are gated — the highest
incidence possible among the five — and the assimilation-weighted share is still **0.046 %**, because
the gated days are also the darkest and coldest of the year. **A day count is not a magnitude**; had this
been scored on incidence it would have read as the largest term on the shortlist.

## Consequences

1. **Item (b) is closed at 0.046 % against a +3.0 % residual** — 65× too small at the worst cell, 480× at
   Hainich. It cannot be the compensating error ADR 0135/0136 are looking for. Do not re-open it, and do
   not build the opt-in flag: a flag whose measured ceiling is 0.05 % is maintenance cost with no
   measurement behind it, and guardrail 4's corollary (an opt-in default known wrong is a defect on a
   timer) argues *against* shipping one here, not for it.
2. **The `fdiff.jl:234` comment's structural claim was right, and is now a measurement.** Updated in place
   to cite this record rather than assert the halves argument. This is ADR 0108's rule applied to our own
   reasoning — "input X is bounded" bounds what X can carry and says nothing about what the model does,
   until someone runs it.
3. **ADR 0135's shortlist now has one item left: (c), the phenology trajectory.** The compensating-error
   search narrows to it plus whatever the four already-identified faithful-but-worse terms are paying for.
   The count of such terms is unchanged at four; this is not a fifth.
4. **The `+3.0 °C` threshold for the tropical evergreen is worth remembering separately.** It is 9 °C
   above every other tree's and would make the gate a *live* term for a high-elevation or
   seasonally-cool cell dominated by PFT id 0 — a population none of the five biome cells samples. Stated
   as a validity-envelope disclosure on this record's scope, not as an open item.

## Harness

`scripts/diagnose_tstress_photo_gate.py` — no simulation, no SLURM, runs in under a second on committed
fixtures. Carries the reference basis, the closed-form derivation, the falsifiable hypothesis, the
conservatism argument for the bound, the per-cell `CAN BIND` / `CANNOT BIND` verdict, and the final
verdict against the ADR-0136 residual. Lints clean under the repo's configured rule set
(`ruff check --select E,F,I,UP,B --line-length 100`).
