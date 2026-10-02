# Germany data-driven emulator — track A-TAB (per-tree boosted transition)

Line X exploration note. Status logs: `/p/tmp/jamirp/X_de/_status/A1.md … A6.md`; reports
`/p/tmp/jamirp/X_de/_reports/r2_A1.json … r2_A6.json`. Only 1985–2044 is simulated or scored
(owner decision: the later runs are corrupted).

## A6 — the rollout stepper (`scripts/explore_de_tab_stepper.py`)

One class `TabStepper` implements the shared engine's stepper protocol (`init` / `step`); five
thin subclasses select the arm:

| class | arm | death | climate | calibration |
|---|---|---|---|---|
| `TabAL` | A-L | learned survival head (`surv`); fire is inside it; counter = 5 is a certain kill | all boosters at full weight | `tab/cal/<split>.json` if the calibration item has written it, else none |
| `TabALphys` | A-L+phys | learned head `surv_phys` (adds the rule hazard computed from the sampled growth efficiency, counter and age) | full | as A-L |
| `TabAS` | A-S | the original model's rules: hazard draw, the bioclimatic survival test, then the learned patch fire fraction on the survivors (same order as the rule oracle) | full | as A-L |
| `TabA1step` | A-1step | as A-L | full | never (identical to A-L until calibration exists) |
| `TabAk0` | A-k0 | as A-L | every climate booster weighted 0, and the few places where climate enters directly (which tree types may establish, the climate tercile of the entry-state table, the survival test) read the cell's own frozen 1985–2014 climatology | as A-L |

What one year does, for every tree of a chunk, using only the carried state and the climate
provider (A1's audit proved this feature path equals the training features):

1. features from the state + the climate of year y (carried from the previous step) and y+1;
2. next-year growth efficiency: sign (probability head) and log magnitude (+ an empirical residual
   of its predicted-value decile);
3. the bad-growth counter by the original rule (five bad years in a row kill);
4. relative change of above-ground and total biomass (+ a per-tree autocorrelated residual whose
   strength and size depend on tree type and size), then leaf area, crown cover and rooting depth;
   height = the fitted allometry of the new biomass times the tree's fixed start offset;
5. death (arm-specific, table above);
6. a living tree whose height drops below 5 m is kept unprinted (the engine re-prints it if it
   regrows); a tree that dies below 5 m is removed unprinted;
7. recruits: count per patch from the shared patch heads (negative-binomial draw); entry height and
   age from the shared quantile heads (joined with the observed negative height–age rank
   correlation, −0.23 to −0.39 by type); entry counter / growth efficiency from the shared joint
   entry table; tree type from the recruit-type head; the four inherited traits from the donor
   sampler (donors = the cell's living printed trees of that type); longevity and root profile by
   the rules; biomass, total carbon, leaf area, crown cover, rooting depth, the height offset and
   the 2–3 % dead-on-entry flag from a training recruit of the same type with nearly the same
   entry height (`prep` stage, 805 618 donor rows; biomass by inverting the allometry, so height
   and biomass agree);
8. grass of each patch from the grass heads.

Random numbers are the engine's counter-based ones, keyed per tree / patch / recruit slot, so the
three scenario legs share them.

Stated simplifications: the water-stress mortality term is left out of the rule arm (the track
carries no water-stress integral; it is ~3 % of the hazard: mean 0.0014/yr against a death rate of
0.049/yr); recruits' size state other than height and age is copied from a training donor rather
than predicted.

### Smoke (20 dev cells, MPI-ESM1-2-HR seed 1, ssp370, 1985 → 2044, stop-on-NaN mode)

See the A6 report for the numbers; summary in the A6 section of `r2_A6.json`.
