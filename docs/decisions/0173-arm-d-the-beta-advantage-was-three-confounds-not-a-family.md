# 0173 — Arm D: the bounded Beta's "2–3× better than the copula" is entirely the ESTIMATOR and the GROUPING, not the distribution family — the published Beta number sits at its own statistic's noise floor, and with the test cell's OWN moments the Beta ties or loses to the out-of-sample copula

* Status: accepted
* Date: 2026-08-12
* Line: S (tier-3 block 0170–0189)
* Supersedes: nothing. **Refutes the motivating claim of ADR 0093 §5.3** (measured on its own basis, which it
  reproduces first) and therefore **closes rung-1 arm D of `EXECUTION_PLAN.md` §3 as descoped rather than
  run**. Discharges **ADR 0118 decision 5**, which asked for exactly this like-for-like re-establishment.
  Extends ADR 0031 (one KS definition), ADR 0037/0038 (the DRF's estimator), ADR 0112 (score the null in the
  same process).
* Reproduce:
  * part 1 (the confound ladder, ~19 min): `scripts/sbatch_python.sh S-armd1
    scripts/score_beta_vs_copula_likeforlike.py` (job 1762328). Fixture:
    `test/testitems/references/S_beta_vs_copula_likeforlike.csv` (33 rows).
  * part 2 (the deployable arm, ~30 min × 2): `OUT=…/slow_copula_pooled_w20_t8
    SHADOW=…/armd_pooled_t8_param BETA_INTERVAL=param NCPUS=64 PARTITION=priority QOS=priority
    scripts/sbatch_julia.sh S-armdP3 --project=. scripts/eval_slow_beta_arm.jl` (job **1762720**, the run all
    of §3c's numbers are from; 1762462 was the same computation before GATE C was added) and
    `BETA_INTERVAL=empirical … S-armdE2` (job 1762463), then `SHADOW=<dir> scripts/sbatch_python.sh
    S-ks-<arm> scripts/score_slow_copula_ks.py` on each of the three emitted arms (jobs 1762694, 1762733,
    1762950, 1762951).
  * the previously-uncommitted original: `/p/tmp/jamirp/npatch_analysis/attack/betaks.py` (mtime
    2026-08-07), found while writing part 1 and quoted below.

---

## 0. Reconciliation with the ADRs this discharges (the panel every extension opens with, ADR 0116 §4)

ADR 0093 §5.3 recorded, under "what SURVIVED", a **[MEASURED]** claim: *"A bounded Beta on each PFT's own
trait interval beats the shipped copula 2–3×. Two-moment fit, no fitting procedure, median per-cell KS
**0.042–0.073** vs the copula's **0.129–0.173** (400 cells/PFT with ≥150 stems, historic 2019)."* It became
rung-1 arm D in `EXECUTION_PLAN.md` and was named "the cheapest remaining offline S task" in three
consecutive handoffs.

ADR 0118 decision 5 then flagged that the claim has **no committed reproducer** and suspected the Beta used
each cell's *observed* moments while the copula's figure is K-fold-by-cell *out-of-sample*, making the 2–3× an
upper bound rather than a realizable gain, and required the comparison be re-established like-for-like before
arm D ran.

**ADR 0118's suspicion was right and understated it.** The reproducer exists — uncommitted, on scratch — and
reading it shows the two sides of the ratio are **not the same statistic**. Three separate advantages are
folded into one number. This ADR reproduces the published figure on its own basis (a gate), then prices each
confound, and finds that after all three are removed the Beta has **no advantage at all**. Nothing in
`src/` changed; no default moved.

---

## 1. What the published number actually measured

`/p/tmp/jamirp/npatch_analysis/attack/betaks.py`, verbatim in substance:

```python
def ks_beta(x, l, h):
    u = np.clip((x - l) / (h - l), 1e-9, 1 - 1e-9); m = u.mean(); v = u.var(ddof=1)
    k = m * (1 - m) / v - 1.0; a, b = m * k, (1 - m) * k
    return stats.kstest(u, 'beta', args=(a, b)).statistic      # ONE-sample, parameters from THIS sample
...
cnt = s.Cell.value_counts(); cells = cnt[cnt >= 150].index[:400]   # per (Cell, Type), top 400 per PFT
# its own comment: "take the cells with the most stems, per PFT, to give the Beta its best case"
```

against a hard-coded reference line quoting the copula's `.173 / .129 / .158 / .149`. Those four numbers are
`median_percell_KS` in `figures/emulator_validation/pooled_t8/metrics_traits.txt` — a **two-sample** `ks2`
between the OOS prediction and the truth, grouped **per Cell only** (so every group mixes up to seven tree
PFTs), at a ≥ 20-stem floor over 57 719 cells.

So the ratio compares:

| | the Beta side | the copula side |
|---|---|---|
| statistic | **one-sample** KS vs a Beta fitted to that same sample | **two-sample** `ks2(pred, obs)` |
| parameters | the test group's **own observed** moments | learned, **K-fold-by-cell out-of-sample** |
| grouping | per **(Cell, PFT)**, top 400 cells per PFT by stem count | per **Cell**, PFTs **mixed**, all cells ≥ 20 stems |
| PFT label | **used** (each PFT's own `[low, high]`) | **not available** — `COPULA_COND_COLS` carries no `Type` |

The last row is the confound nobody had named: the shipped copula does not know which PFT a stem is, and the
per-PFT trait intervals are in places **disjoint** (id 3's SLA is [0.0242, 0.0547], id 1's is
[0.005, 0.0187]), so a PFT-mixed per-cell group is a mixture of partly non-overlapping supports — a strictly
harder target for any single distribution.

---

## 2. The ladder: one row universe, `ks2` imported not re-implemented, each rung prices one confound

10 129 503 surviving tree stems, historic 2019, seed 1. `ks2` is imported from
`plot_slow_emulator_validation.py` (ADR 0031's one-definition rule); the copula column is **read** from the
published metrics file, never retyped.

| # | arm | statistic | grouping | SLA | Wooddens | D95max | minwscal |
|---|---|---|---|---|---|---|---|
| 1 | Beta, **oracle** moments, per-PFT | 1-sample, est. params | (Cell,PFT), top-400 | **0.0645** | **0.0476** | **0.0695** | **0.0437** |
| 6 | *that statistic's own noise floor* (n = 150, simulated Beta) | 1-sample, est. params | — | 0.0434 – 0.0475 | | | |
| 2 | Beta, oracle moments, per-PFT | **2-sample** | (Cell,PFT), top-400 | 0.1120 | 0.1026 | 0.1267 | 0.1050 |
| 3 | *split-half floor* | 2-sample | (Cell,PFT), top-400 | 0.0889 | 0.0897 | 0.0887 | 0.0886 |
| 4 | Beta, oracle moments, **PFT-blind** | 2-sample | Cell only, ≥ 20 | 0.1724 | 0.1379 | 0.1573 | 0.1667 |
| 5 | *split-half floor* | 2-sample | Cell only, ≥ 20 | 0.1163 | 0.1173 | 0.1165 | 0.1166 |
| 7 | **the shipped copula** (published, out-of-sample) | 2-sample | Cell only, ≥ 20 | 0.1725 | 0.1287 | 0.1575 | 0.1487 |

**GATE: arm 1 reproduces ADR 0093 §5.3 on ADR 0093's own basis** — per-axis medians 0.0645 / 0.0476 / 0.0695 /
0.0437 against the published range 0.042–0.073. The script dies if it does not, so what follows is a
correction to the *interpretation* of a reproduced number, not a disagreement about the number.

### 2a. The estimator alone eats most of the "2–3×"

Hold the oracle moments and the per-PFT grouping fixed and change only the statistic to the two-sample one
the copula's figure actually is (arm 1 → arm 2): **0.0645 → 0.1120, 0.0476 → 0.1026, 0.0695 → 0.1267,
0.0437 → 0.1050** — a factor of **1.7–2.4×**.

### 2b. And the published Beta number was at its own statistic's noise floor

A one-sample KS with parameters estimated from the same sample is severely optimistically biased (the
Lilliefors problem). Simulating data that genuinely **is** Beta and re-estimating its two moments gives a
median KS of **0.0434–0.0475 at n = 150** (0.0268–0.0290 at n = 400; 0.0171–0.0185 at n = 1000). Arm 1's
Wooddens (**0.0476**) and minwscal (**0.0437**) are *indistinguishable* from that floor. ⇒ on two of four axes
the published number measured "two moments describe a sample of this size", and could not have detected a
family misfit if there was one. This is ADR 0112's lesson — a statistic the null also passes has no power —
arriving in a second place, and the null here was never run.

### 2c. The grouping supplies the rest

Arm 2 → arm 4, per-PFT top-400 → per-Cell PFT-mixed ≥ 20 (the copula's own grouping): **0.1120 → 0.1724,
0.1026 → 0.1379, 0.1267 → 0.1573, 0.1050 → 0.1667**, a further **1.2–1.5×**.

### 2d. THE RESULT: with the test cell's own moments, the Beta ties or LOSES to the out-of-sample copula

Arm 4 vs arm 7, like for like — same statistic, same grouping, same ≥ 20-stem floor:

| axis | Beta, **oracle** moments | shipped copula, **out-of-sample** | the Beta's advantage |
|---|---|---|---|
| SLA | 0.1724 | 0.1725 | **none** (tie) |
| Wooddens | 0.1379 | **0.1287** | **7 % WORSE** |
| D95max | 0.1573 | 0.1575 | **none** (tie) |
| minwscal | 0.1667 | **0.1487** | **12 % WORSE** |

And the Beta in that column is handed each test cell's **own observed** mean and variance, which the copula
has never seen. There is no 2–3×; there is no advantage in either direction on two axes and a deficit on the
other two, from a position of strictly more information.

### 2e. Both arms are close to the irreducible floor of their grouping

The split-half distance of the truth against itself is **0.089** on the per-PFT grouping and **0.117** on the
PFT-mixed one (a ~800-stem group at `STEM_CAP=400` per scenario). So the copula's published 0.129–0.173 is
only **1.1–1.5× its own floor**, and the oracle Beta's 0.138–0.172 likewise. Neither family is the binding
constraint on the per-cell trait-distribution score at this group size; the grouping and the sample size are.

---

## 3. Part 2 — the deployable arm, and why it is a separate measurement

Every Beta arm in §2 has oracle moments. The only design-relevant question is whether a Beta whose two
moments are **learned on the same conditioning and the same folds** would beat the copula's learned empirical
marginal. `scripts/eval_slow_beta_arm.jl` answers it by construction rather than by matching setups: it
re-runs `eval_slow_copula.jl`'s own loop on the same table — same `mod(hash(cell), kfolds)` folds, same
`fit_forest(...; seed = a)`, same `u = rand01!(Xoshiro256pp(i*131 + a))` — and reads **three predictions off
one fitted forest and one leaf pool**:

* `copula` — the pool's empirical `u`-quantile (what the copula ships);
* `beta` — a Beta on the axis's PFT-blind union interval, parameters from that **same pool's** mean and
  variance, at the **same** `u`;
* `expect` — the pool's **mean**, i.e. predict the conditional expectation instead of drawing (§4).

### 3c. THE RESULT: the deployable Beta is WORSE on all four axes, and the control reproduces the published panel to the digit

All three arms come off the same forests in one run (job 1762720), scored by the **existing**
`score_slow_copula_ks.py` with no new scorer:

| arm | statistic | SLA | Wooddens | D95max | minwscal |
|---|---|---|---|---|---|
| **`copula`** — this run's own re-derived column (the CONTROL) | median per-cell KS | **0.1725** | **0.1287** | **0.1575** | **0.1487** |
| | pooled KS | **0.0039** | **0.0065** | **0.0020** | **0.0040** |
| **`beta`** — learned-moment bounded Beta, same forest/pool/`u` | median per-cell KS | 0.2350 | 0.1400 | 0.1775 | 0.1900 |
| | pooled KS | 0.0553 | 0.0421 | 0.0330 | 0.0663 |
| **`expect`** — the conditional expectation (§4) | median per-cell KS | 0.5212 | 0.4963 | 0.5312 | 0.5075 |
| | pooled KS | 0.2930 | 0.3190 | 0.3158 | 0.1909 |

**The control's eight numbers are the published panel exactly** — `figures/emulator_validation/pooled_t8/metrics_traits.txt`
reads median per-cell KS 0.1725 / 0.1287 / 0.1575 / 0.1487 and pooled KS 0.0039 / 0.0065 / 0.0020 / 0.0040.
So this harness reproduces the shipped artifact's own scores to the digit, and the other two arms are on
precisely the published basis rather than a re-derived approximation of it.

**Verdict on the deployable question: replacing the copula's learned empirical marginal with a bounded Beta
carrying the SAME learned two moments is WORSE on every axis, on both statistics.**

* median per-cell KS: **+36.2 % / +8.8 % / +12.7 % / +27.8 %**;
* pooled KS: **14.2× / 6.5× / 16.5× / 16.6×** worse, and every axis fails ADR 0030 §4's criterion 3
  (`pooled KS ≤ 0.02`) which the copula passes on all four.

Combined with §2d — where the Beta given each test cell's **own observed** moments only ties or loses — arm D
is refuted from both directions: the Beta family is not better with learned moments, and it is not better with
oracle moments either.

### 3d. The "the interval was too wide" objection is answered by DEGENERACY, not by a score

`BETA_INTERVAL=empirical` (the training fold's own [min, max] instead of the parameter interval) was included
so that objection could not stand. At global scale it turns out to be **the same arm**: with 42 227 077 stems
the empirical support saturates the parameter interval — byte-identical `pred_*.f64` on Wooddens, D95max and
minwscal, and on SLA a maximum difference of **2.17e-06, i.e. 3.3e-05 of the interval width**, which moves no
printed KS digit (job 1762463, identical scores to four decimals). So the parameter interval is not what is
costing the Beta anything; the family is.

⇒ `beta` and `copula` differ in the marginal **family** and in nothing else. That is enforced by **GATE A
(fatal)**: the pooled reading must equal `DRF.predict_quantile` on sampled rows of every fold and axis
(smoke: 173 908 rows, exact). All three arms are emitted as `pred_<axis>.f64` into shadow dirs with the
source table's `cells.i64`/`Y_*.f64`/manifest symlinked, so the **existing** `score_slow_copula_ks.py`
scores them with no new scorer and no second KS definition.

### 3a. GATE B's outcome, and the ⚠ that is NOT a general claim

**On the production table `slow_copula_pooled_w20_t8`, GATE B PASSES — bit-identical on all four axes over
402 163 checked rows.** So this arm is anchored to the published artifact as well as internally consistent: the
copula column it compares the Beta against *is* the shipped one, and the folds, forests and uniforms are
provably those of the run that produced the pinned artifact. That is the strongest form the like-for-like claim
can take, and it is the basis §2d's comparison should be read on.

⚠ **But it is table-specific, and the counter-example is instructive.** On the old
`/p/tmp/jamirp/emulator_global/smoke_struct_on` table, GATE B **fails on all four axes** (worst |Δ| up to
3.0e5 gC/m³ on Wooddens) — and so does the **stock, unmodified** `eval_slow_copula.jl` re-run on a copy of that
table at its own `KFOLDS=2` (job 1762346), while `src/drf.jl`'s default `qrf = false` numerics are unchanged
(the 2026-07-30/31 commits added `_check_nfeat`, which only throws, the **opt-in** QRF estimator, and `.rcop`
format v2). So **a stored `pred_*.f64` on a scratch table can be stale with respect to today's evaluator**, the
production one is not, and the cause of the smoke table's divergence is unpinned. Do not generalise either way
without checking the table you are using.

**The consequence for method, which is the part that generalises regardless:** the obvious way to build arm D —
take a stored `pred_*.f64` as the copula arm and compute the Beta arm today — would have put a **code change
inside the family comparison** on any table where that divergence exists, and no check would have caught it.
GATE B is reported rather than fatal so the situation is visible either way; GATE A is what makes the
comparison sound independently of it.

### 3b. A third gate, added because the first version of this script shipped a defect the pipeline hid

`GATE C` asserts every emitted shadow dir is complete: all `pred_<axis>.f64` present, each exactly `8·n` bytes,
no filename containing a literal `$`. It exists because the first production run of the three-arm version wrote
**all four axes into one file literally named `pred_$(ax).f64`** in two of the three dirs — an interpolation
escaped away during an editing pass. The failure then surfaced *downstream*, as the scorer erroring on a
missing `Y_` symlink, one step away from the cause; and had the symlink been right, the corrupt single-axis
file would have **scored happily**. A shadow dir is only meaningful if it is complete, so completeness is now
asserted where it is produced rather than discovered where it is consumed.

---

## 4. The determinism dividend is measured for the first time, and its published framing does not transfer

`EXECUTION_PLAN.md` §3 lists, as the first of rung 1's "cheap wins to fold in and measure separately",
ADR 0093 §5's **[FREE]** item: *"predicting the ensemble expectation rather than drawing a realisation halves
the error variance against a stochastic target: +2.9 to +14.4 percentage points of cells inside the 10 % band,
at zero compute cost."* It has **never been measured** (grep: it appears only in ADR 0093, ADR 0114 §1's
re-affirmation, the ADR index and this line's STATE). It is free here because the expectation is the same pool
mean the Beta's moments already need.

⚠ **Read the two framings separately or the result will be mis-stated.** The published +2.9–14.4 pp is on a
**mean-based band metric** (cells inside 10 % on a per-cell aggregate). The arm emitted here is scored on the
copula's **per-cell KS**, a *distributional* metric — and a point mass has no dispersion at all, so a large
per-cell KS for the expectation arm is the **expected** result and is **not** evidence against the band-metric
claim. What this arm settles is narrower and was genuinely open: whether the dividend can be read as a free
win for the trait-**distribution** target, which is what ADR 0025 set the copula up to reproduce. Measured (§3c): the expectation arm's median per-cell KS is **0.4963–0.5312**, i.e. **3.0–3.9× the copula's**,
and its pooled KS is **0.19–0.32**, 48–158× the copula's. That is the expected consequence of predicting a
point mass against a distributional target and it is reported as such — **it is NOT evidence against the
band-metric claim**, which remains unmeasured and is named as the one open rung-1 deliverable in the handoff.
What it does settle, and what was genuinely open: the dividend **cannot** be read as a free win for the
trait-DISTRIBUTION target that ADR 0025 set the copula up to reproduce. If it is taken, it is a deliberate
trade of distributional fidelity for band accuracy, and both sides must be quoted.

---

## 5. Decision

1. **Arm D is DESCOPED, not run.** The motivating advantage does not exist: §2d measures the oracle-moment
   Beta at a tie-or-worse against the out-of-sample copula on the copula's own statistic and grouping. There
   is no basis for replacing the copula's marginals with a bounded Beta, and `EXECUTION_PLAN.md` §3's arm D
   should be struck (an integration point — the file is integrator-owned; raised in this line's STATE).
2. **ADR 0093 §5.3's `[MEASURED]` claim is retired.** Its number is reproducible and correct *as a
   one-sample, oracle-moment, per-PFT, best-case statistic*; it is not a comparison with the copula. Anyone
   re-proposing a bounded-Beta marginal must first refute §2d.
3. **`test/testitems/references/S_beta_vs_copula_likeforlike.csv` is the committed reproducer** for both the
   published claim and its correction, with the gate against the published range built in.
4. **The two-severity gate pattern is the reusable part** (§3a): a fatal gate on the invariant the comparison
   rests on, and a reported gate on the anchor to a stored artifact — because a stored artifact can rot, and
   discovering that inside a comparison is indistinguishable from a scientific result.
5. **`qrf` is untouched here and its own question stays open.** `qrf = false` is still the equal-weight
   estimator ADR 0037/0038 measured is not the quantile-regression forest, and it has never been isolated at
   `ncond = 8`. This ADR deliberately **refuses** `QRF=1` (the Beta reads the unweighted pool, so a QRF
   copula column would not be the same pool and the family comparison would be confounded) — that is a
   separate arm with its own criterion, not a variant of this one.

---

## 6. What is NOT claimed

* **Not** that a Beta cannot describe FIT's within-cell trait distribution. §2b shows the opposite is
  *untested* by the published statistic: the one-sample number is at its floor, so it neither confirms nor
  refutes family adequacy. §2d shows only that a Beta buys nothing **over the shipped copula, on the
  copula's own statistic and grouping, given the same or more information**.
* **Not** that the copula is good. Its per-cell KS is 1.1–1.5× the split-half floor of its grouping (§2e), and
  ADR 0112's teacher-forcing caveat applies to it unchanged. This ADR removes a proposed *replacement*; it
  does not lower the bar for the incumbent.
* **Not** a statement about the per-PFT grouping being wrong. Scoring per (Cell, PFT) is arguably the more
  informative panel; the point is that a number computed on it cannot be compared with one computed per Cell.
* The PFT-blind interval used in §2's arm 4 and in part 2 is the union over the seven tree PFTs. Every
  observed value on all four axes falls **inside** it (0.0 % outside, 42 227 077 rows), so the interval is not
  clipping the target, and `BETA_INTERVAL=empirical` exists so "the parameter interval was too wide" cannot
  explain a null result.
