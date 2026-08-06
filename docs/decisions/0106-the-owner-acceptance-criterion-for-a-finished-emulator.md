# ADR 0106 — the OWNER's acceptance criterion for a finished emulator: everything within 10 %, on ALL cells, under climate change too

* **Status:** Accepted
* **Date:** 2026-08-06
* **Line:** S (recorded here because S was told; **this is a PROJECT-WIDE owner decision and binds all four
  lines**, so it is mirrored in `MEMORY.md` §owner decisions and in `~/.claude/CLAUDE.md` — the latter
  because a repo `CLAUDE.md` is only as current as the branch a session stands on, and two lines were
  measured on 2026-08-06 to be missing a project-wide rule for exactly that reason)
* **Decides:** the definition of DONE for the hybrid land-component emulator, in the owner's own terms:
  **(1)** the emulator must **fully emulate the original model** — not a subset of quantities;
  **(2)** **especially under climate change**, not only for present-day climate;
  **(3)** every quantity — **tree counts AND trait distributions AND trait medians** — within **10 %** of
  the original; **(4)** proven on **ALL cells**, not on a handful of test sites.
* **Supersedes:** every prior implicit or stated stopping condition on any line, including "at the
  seed1-vs-seed2 noise floor", "within N noise floors", and any five-cell verdict read as sufficient.
  A noise-floor statement is still the right *diagnostic*; it is no longer the *acceptance test*.
* **Related:** ADR 0004 (CO2 is a constant in every deployed training row ⇒ no CO2 response at all),
  ADR 0101 (the measured warming response is indistinguishable from zero where the original rises),
  ADR 0038/0040/0042 (the conditioning set — the only channel that can carry a warming signal),
  ADR 0026 (the transient per-cell-year boundary machinery that already exists), ADR 0030 (the trait gate),
  ADR 0044 (the global gate), ADR 0105 (the measurements this criterion re-scopes).

## 1. The criterion, verbatim from the owner (2026-08-06)

> "the emulator should fully emulate the original model, and of course also and especially under climate
> change" · "the work is done if everything, also trait distributions and medians, is close to the
> original, less than 10 % error" · "it is of course only finished when it's proven to be correct on all
> cells, not only a handful of test sites"

## 2. What that makes checkable — the panel, the metric, the population

**The panel** (every item, not a chosen subset):

| quantity | the emulated thing |
|---|---|
| tree density / count | per-patch `n_living` |
| the four recruit trait axes | `SLA`, `Wooddens`, `D95max`, `minwscal` — **median** and **distribution** |
| the size/biomass axes | `Height`, `agb` |
| the annual carbon and water fluxes the coupled model reports | GPP/NPP, LE, and the closures |

**The metric.** For a level or a median: `|E − C| / C ≤ 0.10`. For a **distribution**: the same 10 % bound
applied to **each** reported quantile (q05, q25, q50, q75, q95) — the natural extension of the owner's
wording, and stricter than any single summary statistic. Stated explicitly because "10 % of a distribution"
is otherwise ambiguous, and an ambiguous acceptance test is not an acceptance test.

**The population.** Every cell of the tree-bearing population — **54 020 cells** carry trees of the 67 420
on the grid (ADR 0031's corrected population, ids 0–6). Not the five biome cells; not the 45 009 of the
superseded truncated population.

**Both scenarios AND the response between them.** Historic *and* ssp370 each within 10 %, and — the part
that makes "especially under climate change" testable — the **change** from one to the other within 10 %
as well. A model can match both levels while getting the response wrong only if the errors are correlated;
requiring the difference is what closes that.

## 3. ⚠ One clause needs an owner decision, because 10 % is unachievable for a reason that is not our fault

**The original model is stochastic.** Two runs of LPJmL-FIT that differ only in their random seed disagree
with each other, and in some cells they disagree by **more than 10 %**. Measured: the two ground-truth
members' per-patch tree count differs by **29 % of the mean** at `tropical_amazon`, because that cell
carries only ~4.7 trees per patch and one tree living or dying is a 21 % change. There is no single "the
original's answer" there to be within 10 % of.

So a literal reading of the criterion is unmeetable **by construction** in low-density cells — by any
emulator, including a second run of the original model itself.

**Proposed resolution, and the default this project will use unless the owner says otherwise:**

> the tolerance is **`max(10 %, the original model's own two-run spread for that quantity in that cell)`**

which is 10 % everywhere the original is reproducible to better than 10 %, and the original's own
irreducible spread where it is not. **This is the only clause of the criterion that is not the owner's own
words**, so it is flagged rather than absorbed. The alternative readings — score against the mean of many
original runs (expensive, and only available for the two seeds that exist), or exempt low-density cells
(hides a real weakness) — are both worse.

## 4. Where the emulator actually stands against this today — the honest gap list

Stated so the criterion has a baseline and nobody has to re-derive it.

| criterion clause | status | the number |
|---|---|---|
| trait **medians**, 5 test cells | **mostly passing** | 9 of 10 cell×axis pairs within 10 %; `temperate_hainich` `Wooddens` +10.7 % |
| trait **distributions**, 5 test cells | **not measured on this metric** | reported as RMSE over quantiles ÷ the original's own spread: 0.14–1.31. `boreal_siberia` `SLA` at 1.31 is far out |
| tree **density**, 5 test cells | **FAILS** | +4 % to +38 % at four cells, **−48 %** at `semiarid_sahel` |
| **all cells** | **NOT PROVEN** | the coupled model runs at **5** of 54 020 cells. The offline emulator *is* scored globally by held-out cell, but the coupled loop is not |
| **under climate change — warming** | **FAILS** | the emulator's warming response is *indistinguishable from zero* where the original rises (+0.26 ×, confidence interval spanning zero) |
| **under climate change — CO2** | **FAILS COMPLETELY** | CO2 is the constant 369 ppm in **every training row of every deployed artifact**, so the emulator has **no CO2 response at all**. This is the largest single gap and it is structural, not a tuning error |

⇒ **the binding constraint is §2's climate-change clause, not the fidelity numbers.** Two of the panel's
rows are near the bar already; the response channels are largely absent. Work that improves present-day
agreement is therefore not progress toward this criterion unless it also opens a response channel.

## 5. Consequences

1. **The conditioning work (milestone S2) is not one lever among several — it is the critical path**, because
   it is the only channel through which a warming signal can reach the emulator's recruits. It is promoted
   from "top S-owned item by elimination" to **the** item.
2. **CO2 needs its own item, and it does not exist yet.** ADR 0004 recorded the constant; nothing has been
   scheduled to remove it. A CO2 response requires training rows in which CO2 varies, which the current
   ground-truth pair does not provide at fixed 409.63 ppm from 2020. **Raised as a new open question with
   no owner** — it may need a new run of the original model, which is an owner-level cost decision.
3. **"All cells" changes what a gate is.** A five-cell coupled verdict can now only ever be a *screen*. The
   coupled model has to scale toward the full population (line M) and the acceptance measurement has to be a
   global, per-cell, out-of-sample comparison — the machinery for which exists on the offline side
   (`emulator-validation-figures`, K-fold by cell, per-cell maps) and does not on the coupled side.
4. **No line may declare a milestone "done" on a five-cell result again**, and no report may present one as
   evidence of fidelity without saying it is five cells of 54 020.

## 6. The method rule

**An acceptance criterion is a deliverable, and its absence is a defect.** This project ran for months with
per-milestone gates (noise floors, band checks, R²) and no project-level stopping condition, which is how
"the open questions are closed" came to be reported as near-finished while the emulator had no
climate-change response at all. A gate answers "did this change help?"; only an acceptance criterion answers
"are we done?" **Ask for one, in the owner's terms, and write it down where every line reads it — before
the next milestone, not after.**
