# 0371 — How noisy is the complete-emulator drift clause? Two ensembles of the same daily network against each other (pre-registration, SEPARATE EXPERIMENT)

* **Status:** pre-registered 2026-10-24, before any fit or run of this record. Results: §5, added after the runs.
* **SEPARATE EXPERIMENT — nothing of it enters the paper** (continues ADR 0368–0370).
* **Owner instruction (2026-10-24):** *"continue with the recommended next steps"* = option (z1) of the ADR 0370
  handoff (measure the drift clause's own noise), then (z2) only if the result says MEP's failure was noise.
* **Why:** ADR 0370 §6.1 rejected all three daily candidates (MEP, MEPx, TP) on one clause of ADR 0367's rule — "no
  leg's drift more than 0.08 above the deployed networks'" — although each cut the typical error 11–19 %. Its post-hoc
  check found the network without the place description breaks the clause as often, and left open whether two
  ensembles of the SAME network would break it too. If they do, the clause cannot be passed by any network on this
  venue and the rejection says nothing about the candidates.

## 1. New networks and runs

* **MR s3 … s9**: the deployed design (MLP 256×3, no extras) retrained by `xtf_daily.py train --arm MR`, exactly as
  MR s0–2 of ADR 0369 (whose scores matched the deployed networks: held-out NPP single-year 1.77 vs 1.77).
* **Ensembles** on ADR 0370's venue (`xtf_daily.py runens`, member 2, emulated stand `stand_emul_main2`, 2020–2100,
  daily outputs of 5 networks averaged, one bucket): **MRa** = MR s0–4, **MRb** = MR s5–9. B (= NC_s0–4, the release's
  networks), MEP, MEPx, TP are reused from ADR 0370 unchanged.

## 2. The nulls

Scored with `xtf_daily.py scoreens` exactly as ADR 0370 §2 (30 rising-CO2 legs, held-out cells, mean GPP ≥ 50,
windows 2021–2050 / 2071–2100, member 3 = second run):

* **N1 = MRb against MRa** — same script, same design, disjoint seeds: the pure seed noise of a 5-member ensemble.
* **N2 = MRa against B** — the retrained copies against the deployed ones (seed noise + any pipeline difference).

Per null and flux: the number of legs whose drift excess exceeds +0.08, the largest |drift excess| over legs
(`L_drift`; absolute, because which ensemble is the reference is arbitrary), and the largest max(q, 1/q) over
leg-windows (`L_q`). Also the null's median q (should be ≈ 1).

## 3. Decision

**(i) Is the clause noise?** If either null has at least one leg over +0.08 in any flux, the clause as written would
reject the deployed design against itself ⇒ it is replaced for this venue by the noise-calibrated version (ii). If
neither null breaks it in any flux, the clause measures something real ⇒ ADR 0370's rejections stand, nothing is
packaged, and the daily/die-off line stops here (z3).

**(ii) Noise-calibrated rule** (only if (i) says noise). Per flux f, with L and counts the maximum over N1 and N2:
* median q unchanged (NPP ≤ 0.95, GPP / ET / runoff ≤ 1.05);
* worst leg-window q ≤ max(1.25, L_q(f));
* worst drift excess ≤ max(0.08, L_drift(f)), AND the number of legs over +0.08 ≤ the nulls' larger count for f.

The decision is on the candidates against B, as ADR 0370. Reported beside it (not deciding): the candidates against
MRa (same training script).

**(iii) What follows.** If **MEP** passes (ii): ADR 0370 §2's "if a candidate passes" steps for MEP — the package
`landemu` gets the running-mean bank + place description as an opt-in daily input (existing releases reproduce bit
for bit), a fold release copy `non_fold_v2mep` with only the daily networks replaced (numpy == PyTorch on the daily
step, max relative difference ≤ 1e-5), and its end-to-end one-core cost per cell-year (`run_emulator_non.py`). It does
not replace any current release without the owner's word. If only **TP** or **MEPx** passes: reported, nothing built
(TP costs ≈ 8× the release's daily step; MEPx was option 2's network) — owner's call. If none passes: stop (z3).

## 4. What this record does not do

No change to any existing release; no full-grid run; no paper text; no new rule for other venues (the calibrated rule
is for this venue and these candidates only).
