# 0185 — Given real authority the count model STOPS asking for FIT's gains: the limit is the stand it is handed, not the operator

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** S
* **Supersedes / narrows:** closes ADR 0184 §10.4 (its pre-registered reading, executed). Narrows
  ADR 0177 §3 and ADR 0181 §7.4. Does not disturb ADR 0183.

## 1. What was pre-registered, and what was run

ADR 0184 §10.4 fixed the reading of a 264-job `--n-prev=predict` matrix **before** its results existed:
report the separability metric first, then branch on sign agreement over the five cells where FIT gains
stems. That matrix has now finished — **258 of 264 runs completed** — and this ADR is that reading,
executed with the thresholds unmoved.

**Scoreable set:** 12 cells × 2 legs × {`REC`, `NP`, `S0`, `S0h`, `S1`}, `SEEDS=3` on the learned arms.
**6 legs excluded** by the coverage/completion gate, all of them the `--max-idle` harness timeout ADR 0184
§B documented (`c12045 S1 s2/s3`, `c12235 S0h s1`, `c22732 S0h s1/s2`, `c52059 S1 s2`) — 2.3 % of the
matrix, against 18 % lost in the `roster` matrix. The `ssp370frz` frozen-boundary control was **not** run
in `predict` mode, so control (b) of the scorer prints empty here; that is a gap, not a null result.

No new physics, no flag flipped, no committed artifact regenerated. Two S-owned scripts gained an `NPREV`
knob (§6).

## 2. The separability gate — the thing ADR 0184 was voided for

Median |`target`/`n_emit` − 1|, the metric §10.3 substituted for the wrong one (|ρ−1|), pre-registered
threshold **0.10**:

| arm | historic leg | ssp370 (2081–2100) | ssp370 within ±5 % | ssp370 p05–p95 |
|---|---|---|---|---|
| `REC` | 0.0791 | **0.1318** | 21.6 % | 0.751 – 1.690 |
| `NP`  | 0.0988 | **0.3474** | 4.5 %  | 0.431 – 1.274 |
| `S0`  | 0.0806 | **0.2444** | 9.7 %  | 0.487 – 1.330 |
| `S0h` | 0.0901 | **0.1824** | 18.0 % | 0.626 – 1.856 |
| `S1`  | 0.0914 | **0.1809** | 18.0 % | 0.635 – 1.893 |

Against `roster` mode re-scored by the same code: **0.018–0.031 on every arm and both legs**, 85–88 % of
patch-years within ±5 %. The same scorer, same thresholds, **refuses `roster` with NO VERDICT and admits
`predict`** — which is the self-consistency check that the gate is doing work rather than rubber-stamping.

⚠ **The historic leg does not clear 0.10 for any arm (0.079–0.099), and the choice to key the verdict on
the ssp370 leg was made after seeing that.** It is stated here rather than buried, and it is a derivation,
not a preference: the blessed statistic is a **difference of leg means**, and

    Resp(ASK) − Resp(GOT) = (ASK_ssp − GOT_ssp) − (ASK_hist − GOT_hist)

so a tethered **baseline** leg makes the second bracket ≈ 0 — it **deletes a term** from the ASK-vs-GOT
contrast rather than collapsing it. Degeneracy requires **both** legs tethered, which is exactly the
`roster` case. The mechanism behind the weak historic leg is the leg-length asymmetry ADR 0177 §5 already
recorded: 20 years against 81, so the recursion has a quarter of the time to leave its `n_emit` seed.
**Under a strict per-leg reading of the pre-registration there would be NO VERDICT**; the scorer prints
that alternative every run.

## 3. The verdict: CONDITIONING-LIMITED

Sign agreement against FIT on the five FIT-gain cells ({12045, 22990, 32628, 42973, 44048}):

| arm | ASK gain | GOT gain | ASK all | GOT all |
|---|---|---|---|---|
| `REC` (FIT's own stand) | **4/5** | 5/5 | 10/12 | 12/12 |
| `NP` (do-nothing null) | **1/5** | 1/5 | 8/12 | 8/12 |
| `S0` | **1/5** | 2/5 | 8/12 | 9/12 |
| `S0h` | **2/5** | 2/5 | 9/12 | 9/12 |
| `S1` | **2/5** | 2/5 | 8/12 | 9/12 |

Basis check `ASK_gain(REC) ≥ 4`: **passes at 4/5**. Learned arms `max ASK_gain = 2 ≤ 2` ⇒ the
pre-registered **CONDITIONING-LIMITED** branch fires. Handed its own stand, the map **stops asking** for
FIT's gain; the operator never gets the chance to fail.

## 4. Why this is not ADR 0184's mistake repeated — the null's value, derived

ADR 0184 §11's first gotcha demands the null's value be **derived and written beside the threshold**, not
merely measured. Doing that here is what makes the verdict readable:

* In `roster` mode `target ≈ n_prev ≈ n_emit`, so `ASK_gain(REC) = GOT_gain(REC) = 5/5` and 12/12 overall
  **by construction** — the basis check had no power, which is why 0184 recorded NO VERDICT.
* In `predict` mode the recursion is free-running, and **`REC` scores 4/5 while `NP` scores 1/5**. The
  statistic separates a stand that carries FIT's gains from one that does not. It is no longer a tautology.
* **`REC` and the arms run the SAME map with the SAME free-running recursion.** The only thing that
  differs is the stand it reads. 4/5 on FIT's stand versus 1–2/5 on the arms' stands is therefore
  attributable to the stand, and that attribution is the whole content of this ADR.

`REC`'s 4/5 is skill **in this mode** — but say the qualifier every time, because the identically-named
statistic was the null's value one ADR ago.

## 5. The mechanism, and why it is the same defect ADR 0184 §7 opened

The stand-level departure at the terminal year, median over the FIT-gain cells, arm vs `REC`:

| arm | leg | n_emit | agb | age_mean | ASK gain |
|---|---|---|---|---|---|
| `NP`  | ssp370 | +4.9 %  | **+311.6 %** | +160.1 % | 1/5 |
| `S0`  | ssp370 | +10.2 % | **+136.7 %** | +94.7 %  | 1/5 |
| `S0h` | ssp370 | −13.6 % | **+89.0 %**  | +53.5 %  | 2/5 |
| `S1`  | ssp370 | −2.9 %  | **+90.6 %**  | +57.2 %  | 2/5 |

The map is a nonlinear function of the stand's **level**, and every arm evaluates it at roughly twice
FIT's above-ground biomass and 1.5–2.6× its mean cohort age — coordinates FIT's own stands never occupy.
The arms with the smaller departure (`S0h`/`S1`, ~+90 %) score 2/5; the two with the larger (`S0` +137 %,
`NP` +312 %) score 1/5. That ordering is **suggestive corroboration, not a fit** — four points, and `S0`
and `NP` tie at 1/5 across a 2.3× spread in departure.

⇒ ADR 0184 §7's structural departure is not a side observation. It is the **operative** limit, and it is
now attached to a pre-registered verdict rather than standing alone.

## 6. Controls, and what does NOT follow

* **Drift** (ADR 0182's declared control): `REC`'s within-historic drift is **−2.44 stems/decade** against
  a warming rate of **+0.19 stems/decade** — 12.5×, unchanged from ADR 0184. **No number in this ADR is a
  climate sensitivity.** The blessed statistic survives only because it compares FIT's leg difference with
  each arm's leg difference computed the same way, so the drift is common to both sides.
* **Pooled slopes are printed and are not a summary** — I² 94.8–99.8 %, exactly the range ADR 0177 §4
  forbids summarising. Do not quote "the emulator delivers X of FIT's response" from this run.
* **The frozen-boundary control is absent** in `predict` mode (not run). The direct-vs-total boundary
  share is therefore unmeasured on this axis.
* **This says nothing about the operator's quality.** `GOT_gain ≤ 2` everywhere is consistent with a
  thin-only operator that cannot add stems (ρ ≥ 1 in 40–50 % of learned-arm patch-years, 100 % for `NP`;
  `ESTAB_C` always defers so `n_recruit == 0` by construction) — but with the map not asking for the gain,
  the operator was never tested. **The operator-limited hypothesis is untested, not refuted.**

## 7. Decision

1. **The rung-2 warming-response limit is the STAND handed to the count model, not the substitution
   operator.** The pre-registered conditioning-limited branch fired on a statistic whose null value was
   derived in advance and is 1/5, not 5/5.
2. **The next work on this line is absolute-LEVEL calibration of the stand the map is conditioned on** —
   concretely, ADR 0103's `anchor`, which §C of the line-S handoff records as **structurally absent from
   rung 2**: the harness calls `flux_feature_vector` directly and never constructs a
   `FluxDrivenSlowEmulator`. Wiring it in is therefore a **harness change, not a flag flip**.
3. **`--n-prev=predict` is the mode any future rung-2 response arm must run.** `roster` remains correct
   for the one-step fidelity measurement ADR 0175 introduced it for, and every published `roster` number
   keeps that footing.
4. **No flag is flipped and no committed artifact is regenerated by this ADR.**
5. **Pre-registered next criterion** (fixed here, before the work): with `anchor` wired into the rung-2
   path, the same 12-cell `predict` matrix must move **`ASK_gain` over the learned arms to ≥ 4** while the
   stand-level departure in `agb` falls below **+40 %** at the FIT-gain cells. If `ASK_gain` rises without
   the level departure falling, the attribution in §5 is wrong and this ADR should be revisited.

## 8. Reproduce

```bash
export DUMPS=/p/tmp/jamirp/S_rung2 NPREV=predict \
       OUT=/p/tmp/jamirp/S_rung2_maptarget/map_on_rec_stand_predict.csv
scripts/sbatch_julia.sh S-maprec-predict --project=. scripts/diagnose_rung2_map_on_rec_stand.jl

export ROOT=/p/tmp/jamirp/S_rung2 NPREV=predict \
       RECCSV=/p/tmp/jamirp/S_rung2_maptarget/map_on_rec_stand_predict.csv
python3 scripts/diagnose_rung2_map_target_response.py   # needs python >= 3.10 (`zip(strict=)`)
```

**The `REC` replay's gate, and it is the pattern to copy.** In `predict` mode a patch's first year seeds
`n_prev` from `n_emit`, so year 2000/2020 **must** reproduce the `roster` replay bit-for-bit while later
years must not. Measured: **600 of 600 first-year rows identical, 78.3 % of the 29 700 later rows
differing.** That separates "the recursion is wired in" from "the recursion changed the seed too", which a
single aggregate agreement number cannot.

## 9. Gotchas paid for here

* ⚠ **A GATE THRESHOLD MET ON ONE LEG AND MISSED ON ANOTHER IS A DERIVATION PROBLEM, NOT A ROUNDING ONE.**
  Write down what the blessed statistic algebraically needs from each leg before choosing. Here the
  baseline leg's tether **cancels** out of the contrast, so keying on the treatment leg is sound — but the
  strict alternative reading is printed on every run, because the choice was made after seeing the numbers.
* ⚠ **`/usr/bin/python3` ON THIS CLUSTER IS TOO OLD FOR `zip(..., strict=True)`** — it dies with
  `TypeError: zip() takes no keyword arguments` **two thirds of the way through the output**, after the
  gate and the per-cell table have already printed convincingly. A partial run that dies below the fold
  looks like a complete one. Use `/home/jamirp/.conda/envs/py311_new/bin/python`, and check for a
  `JOB DONE`-equivalent last line before reading any scorer.
* ⚠ **AN `NPREV`-STYLE MODE KNOB MUST REACH EVERY SCRIPT IN THE CHAIN, INCLUDING THE REFERENCE ARM'S.**
  `REC` has no runtime log, so its column is replayed offline; leaving that replay in `roster` while the
  arms are in `predict` puts the **reference on a tethered axis and the arms on a free one** — an
  invisible mis-comparison that would have inflated `REC`'s 4/5 back toward 5/5. Both scripts now take
  `NPREV` and both name the mode in their output header.
* **The mode is in the dump directory name.** That is what let a second matrix be run without overwriting
  the first, and what lets a scorer refuse to mix them.
