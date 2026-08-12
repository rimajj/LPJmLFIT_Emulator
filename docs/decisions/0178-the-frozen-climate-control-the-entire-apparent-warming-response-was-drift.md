# 0178 — the frozen-climate control: the count model's warming response is INDISTINGUISHABLE FROM ZERO, and essentially all of ADR 0177's apparent response was free-running drift

* Status: accepted
* Date: 2026-08-13
* Line: S (tier-3 block 0170–0189)
* **Narrows ADR 0177**, which is not withdrawn: its per-cell table, its sign result and its interface
  findings stand, but its §4 magnitudes (through-origin slopes 1.33–1.48) are now shown to be **drift, not
  sensitivity**. ADR 0177 §5 pre-registered exactly this control and named it the next action; this is it.
* Scope: 12 scored cells of 54 020, ssp370 2020–2100, establishment deferred to the C in every arm,
  `n_living` = terminal-year patch-ensemble mean of stems above the 5 m emission cut.

---

## 1. The control, and why it was necessary

The two legs of the scenario pair differ in LENGTH — historic is 20 years, ssp370 is 81. So
`terminal(ssp370) − terminal(historic)` is the climate response **plus 61 extra years of free-running
drift**, and an arm with no climate sensitivity at all still scores large on it. ADR 0177 could not separate
the two and said so.

The frozen-climate arm removes the drift term **by construction**: the same ssp370 leg, same restart, same
seeds, same 81 years, with only the bioclimatic tail the count model conditions on held at the present-day
climatology (`BOUNDARY=frozen`, `build_rung2_boundary_series.py --freeze`). Seed-paired within each cell:

```
climate response = terminal(arm, ssp370 transient) − terminal(arm, ssp370 FROZEN)
drift            = terminal(arm, ssp370 FROZEN)    − terminal(arm, historic)
```

240 runs on `bin/lpjml_rung2_v6`, 187 complete (see §4).

## 2. THE CONTROL VALIDATES ITSELF — the null's climate term is exactly zero

`NP` (ρ = 1) never consults the count model, so freezing the model's climate input **must** change nothing.
Measured: `climate = 0.000` at **every one of the 12 cells**, exactly. That is not a near-zero — it is the
by-construction zero, and it is what licenses reading a non-zero elsewhere as real. (It also re-confirms
that the frozen and transient runs are otherwise identical: same restart, same seeds, same physics.)

## 3. THE RESULT — the climate channel carries 3–6 % of the magnitude, and does not track FIT

| arm | mean climate | mean drift | drift share of magnitude | climate-vs-truth slope |
|---|---|---|---|---|
| `NP` | 0.000 | −3.947 | **100.0 %** | 0.000 |
| `S0` (shipped uniform) | +0.175 | −2.961 | **94.4 %** | **−0.031** |
| `S0h` (interface control) | +0.134 | −4.693 | **97.2 %** | **+0.044** |
| `S1` (trait ordering) | −0.008 | −4.286 | **99.8 %** | **+0.003** |

**Essentially the entire apparent warming response measured in ADR 0177 was drift.** What remains once
drift is differenced out is a climate term of a few hundredths to a few tenths of a stem, against per-cell
true changes of −5.2 to +5.2 stems — and its slope against FIT's own change is **−0.03 to +0.04 for every
arm**, i.e. indistinguishable from zero and not distinguishable between arms either.

This is the answer to the question the whole rung was built to ask. **The shipped count model does not
respond to climate in any measurable way when it runs free inside FIT's own physics.** It is not that the
response has the wrong magnitude or the wrong sign — there is no response to speak of. ADR 0177's finding
that the arms match the persistence null on DIRECTION now has its mechanism: they match the null because,
on the climate channel, they *are* the null.

⚠ **Do not read the per-cell `clim/truth` ratios in the printed table as skill.** Their numerator is
~0.1 stems and their denominator is sometimes ~0.2, so individual ratios reach ±2.5 on noise. The
per-arm slope over all cells, and the drift share, are the statistics that mean something.

## 4. Coverage and exclusions

187 of 240 frozen runs completed. The losses are the two limits ADR 0177 §6 already recorded, unchanged
here: the C hook's `duplicate roster key` guard (cell-specific; costs whole cells), and **cell 22732's
`S0h`/`S1` arms hanging at the rendezvous — which reproduced in the frozen variant too**, confirming it is
a property of that cell rather than of concurrency or of the transient boundary. Every dump is gated on the
run's own `lpjml successfully terminated` line and on the expected terminal year 2100; exclusions are
printed with reasons. `S1` and `S0h` are scored on 11 cells, the others on 12.

## 5. Consequences

1. **The response deliverable is definitively not met, and the reason is now specific.** Not "the response
   is too weak" but "the climate input moves the model's output by ~0". Any further work on ordering,
   thinning shape or trait selection is downstream of a model that does not see the climate.
2. **Where to look next is now narrow.** The count model's climate information enters through exactly two
   transient features (`eco_diag_gdd_5`, `tas_cold_month`) out of 15, and this experiment holds the other
   13 on the live roster. The natural next measurement is the model's own sensitivity to those two inputs
   — a direct partial-dependence sweep over the trained forest, which needs no LPJmL run at all and would
   say whether the model learned a climate dependence that the free-running loop then fails to express, or
   never learned one. **Do that before any retraining.**
3. **ADR 0175's `roster_n_prev` falsifier resolves negatively.** Its open question was whether the
   free-running response ratio moves materially once `n_prev` is the stand's own count. It is the stand's
   own count throughout this experiment, and the response is ~0, so the `n_prev` defect — real as it is —
   is **not** the mechanism of the response failure. The attribution table ADR 0175 §3 offered should be
   read as withdrawn on that point.
4. **`trait_mortality`'s flip criterion is untouched** (ADR 0176 §4's certain-set test, no new run needed).
   Nothing here argues for or against the flag: all three arms are equally flat on climate.
