# Exploration (line X, Germany): SH2 — the original model's annual demography rules as a shared library

*Exploratory note, 2026-10-01 (v3: repaired after the adversarial verifier; v2: the owner's 1985-2044-only decision applied). Not a decision. Script: `scripts/explore_de_sh_rules.py`. Outputs:
`/p/tmp/jamirp/X_de/shared/rules/` (`_README.md` is the consumer guide). Report: `/p/tmp/jamirp/X_de/_reports/r2_SH2.json`.*

## What it is

Every rule LPJmL-FIT applies once a year to each tree, given the tree's growth that year, ported to vectorised numpy
and checked against the printed `ind` tables: the bad-growth counter, the four mortality hazards and their cap, the
counter hard kill, the death draw, fire on survivors with the 0.001 floor, the bioclimatic survival test,
establishment eligibility, the inheritance channel weight, the seedbank size/selection/expiry, the trait mutation
kernel (with the production binary's bound quirk), leaf longevity from SLA and the root profile from D95max; plus a
per-Type height allometry fitted on training members only. It also recovers the hidden per-tree state (counter c,
growth efficiency G, water-stress integral W) from a printed row, with censor codes.

Parameters come from `cpp -P` of the live par files (the production runs used `LPJROOT=/home/jamirp/lpjml56fit`,
whose par files were last committed 2025-11-26, before the runs) and agree exactly with the two generated reference
tables (29 columns). Nothing Germany-specific: PFT set, patch count, soil layers and cells come from files.

## v3: repair after the adversarial verifier (2026-10-01)

82 gates, 73 pass (v2: 62, 61). Basis unchanged: dev subset (Cell % 10 == 0, 907 cells), all tree rows of each
window, 1985-2044 only. Full numbers in `/p/tmp/jamirp/X_de/shared/rules/_gates.json` and `_report.json`.

**Traits (the verifier's major defect).** The v2 trait gate pooled all PFTs, 80 % of whose recruits are beech, and
passed with a tolerance I had set myself and not declared. v3 gates per PFT and per build of the establishment year,
with a declared tolerance (max(25 %, 3 combined standard errors), ≥ 5000 recruits per cell), on two seedbank proxies
(A: living printed trees; C: A plus the sub-5 m years of trees that later reach 5 m). Result:

* **Every per-PFT marginal gate fails somewhere (8 of 8).** Only Type 4 matches in every cell. Examples, MPI ssp370
  s1: Type 1 Wooddens 0.0020 observed vs 0.0124 predicted, Type 2 D95max 0.0172 vs 0.0075, Type 5 Wooddens 0.0256 vs
  0.0113; beech passes in the Dec-2025 members (0.0404 vs 0.0333) but not when split by build in ssp245 (Dec-2025-
  established 0.0235 vs 0.0318, Feb-2026-established 0.0219 vs 0.0150).
* **The kernel itself passes every testable channel-free test.** (K2) Among recruits whose Wooddens is out of their
  own interval — certainly inherited, since the background channel draws inside it — the share with D95max also out:
  beech 0.058-0.080 observed vs 0.055-0.076 predicted over six (member, build) cells with 12.6 k-69 k conditioning
  recruits; Types 2/4/5 also pass (fewer recruits). (Build contrast) Recruits established from 2015 on, ssp245 (Feb-
  2026 build) against ssp370 (Dec-2025) of the same GCM and seed, matched on establishment year: the observed ratio of
  out-of-interval shares is beech Wooddens 0.426 / 0.467 vs 0.437 / 0.473 predicted, D95max 0.752 / 0.753 vs 0.751 /
  0.750 (MPI / ACCESS) — the quirk's size is reproduced to 1-3 %. (K1) Recruits of a PFT not eligible at
  establishment (inheritance is then certain): pass, on 241-4182 recruits per cell. Tally (within 25 % / only within
  3 SE / failed): T1 2/0/0, T2 4/2/0, T3 10/2/0, T4 5/5/0, T5 16/4/0; two Type-1 Wooddens contrasts are untestable
  (< 2 expected events). Types 0 and 6 have no dev recruits.
* **Why the marginals fail — measured, for Wooddens:** the out-of-interval share of visible beech recruits falls from
  0.120 for those that reached 5 m within 5 years to 0.0023 for those that took over 30 (MPI ssp370 s1), while the
  kernel's prediction is flat at 0.029-0.036 [MEASURED]. Under the Dec-2025 quirk the stale interval (PFT 0's,
  70 000-650 000) extends 77 870 below beech's own and only 13 000 above it [SOURCE: par file], so out-of-interval
  beech wood is mostly light; that light wood reaches 5 m sooner is the [ASSUMPTION] that explains the profile. Either
  way, the recruits a window sees are a growth-selected sample. The establishment-year profile shows the same thing and also shows the build switch is exactly at 2015
  (ssp245 beech recruits: 0.0415 established in 2014, 0.018 in 2015; ssp370 0.042 both years; diagnostic
  `scripts/explore_de_sh_rules_diag_build.py` → `shared/rules/_diag/build_by_year.json`). D95max is nearly flat in
  time to 5 m but under-predicted by a constant 15-20 %, which the visible data cannot split between the bank proxy
  and the inheritance-vs-background mix (closed form 0.68; implied 0.88-0.90). The "survival to 5 m" attribution of
  v2 is therefore supported for Wooddens and untested for D95max.
* Consequence for tracks: `inherit_traits` is the establishment rule; visible-recruit trait distributions need the
  learned survival-to-5 m filter for every PFT, and especially for Wooddens.

**Other repairs.**

* Height: the Type-1 FAIL (0.9890) stays, but v2 called it an information limit of the table; it is a limit of the
  three predictors. Adding ln LAI and ln fpc_ind lifts Type 1 to 0.9981 (rmse of ln H 0.008) on the same held-out
  member. Shipped as an optional second coefficient table. The MPI ssp370 s1 height gate is labelled in-sample.
* Counter: the gated recursion now uses the documented call with the previous year's counter: 0 failures in
  49-59 M pairs on the three gate members (plain formula: 74-100).
* `mort_eq_min1_sum_nonhard` now requires both conditions (it was "either"); still passes (max 9.64e-6, 0 violations).
* Relabelled as consistency checks: the one-year chain (its G and W come from the very row it is scored on) and the
  water switch (rh on in every usable member), and the eligibility comparison with round-1 probe C (probe C's own
  inputs, not the C-faithful ones). A persistence null now sits beside the chain: reusing this year's G and W gets
  next year's counter right on 0.905-0.936 of pairs and the hazard within 10 % on 0.83-0.87.
* The stated C order is corrected (hazard, survive, age++ in the PFT loop; fire afterwards on trees not already
  dead), and the death channels the library cannot carry are listed (negative pools, `isneg_tree`, the sapling
  leaf-carbon kill, cut-year/logging). The fire rule is not gated against data here; deferred to SH13.
* Hemisphere: SH1's stress-day window uses the northern reset only (day 14); routed to SH1 for the global run.

## v2: only 1985-2044 data (owner decision, 2026-10-01)

The first version of this item gated on a 2071-2100 member and fitted the height allometry partly on 2071-2100
trees. Those runs read the humidity input wrongly, so water-stress mortality never fires in them; the owner decided
to use only 1985-2044 for now. v2 changes:

* The library **refuses** the 24 late-century member-windows (`ExcludedMemberError`, list from the SH0 v2 registry);
  gate `exclusion_enforced` checks it refuses all 24 without opening a file.
* Gate members: MPI ssp370 seed 1 2015-2044 (as specified), **ACCESS ssp370 seed 2 2015-2044** (replacing the
  specified 2071-2100 window of the same run: held-out climate model, second seed) and, added, **ACCESS Historical
  seed 2 1985-2014** so the historical period is gated on the held-out climate model too. Trait-kernel members: the
  four ssp370/ssp245 2015-2044 members.
* Height allometry refitted on the registry's training role only (Historical 1985-2014 + ssp 2015-2044).
* The robustness census runs on the 16 usable member-windows only. The v1 census job was cancelled because it was
  reading excluded windows; v1 outputs are kept in `shared/rules/_superseded_v1_pre_owner_exclusion/`.

## v2 gates (62; 61 pass, 1 fails; superseded by v3 above where they differ) — basis: dev subset (Cell % 10 == 0, 907 cells), all tree rows of the window

| gate | MPI ssp370 s1 2015-44 (56.8 M rows) | ACCESS ssp370 s2 2015-44 (52.8 M) | ACCESS Hist s2 1985-2014 (63.0 M) | spec |
|---|---|---|---|---|
| printed mort = min(1, Σ parts), non-hard rows | max rel err 9.57e-6, 0 print violations | 9.58e-6, 0 | 9.64e-6, 0 | ≤ 1e-5 |
| mort_age from Age − 1 | 4.43e-6 | 4.43e-6 | 4.43e-6 | ≤ 1e-5 |
| counter recursion (tolerant formula) | 83 / 53.1 M = 1.6e-6 | 74 / 49.3 M = 1.5e-6 | 100 / 59.0 M = 1.7e-6 | ≤ 1e-5 |
| forbidden bands | 0 | 0 | 0 | empty |
| counter 5 ⇒ isdead | 784 402 rows, 100 % | 732 944, 100 % | 829 574, 100 % | 100 % |
| W round trip | 2e-16; 158 capped | 2e-16; 2087 capped | 2e-16; 93 capped | exact |
| G round trip (uncensored) | 6.5e-16; G_low 160, npp_sat 4, G_sign 667 | 7.9e-16; 490 / 0 / 601 | 7.6e-16; 161 / 0 / 617 | exact |
| water rule (all usable data have rh on) | 1.93 % rows > 0, rule = printed to 1e-16 | 2.53 %, 1e-16 | 1.82 %, 3e-17 | — |
| whole mortality chain → printed next year | counter 0.9999999; all five quantities 1.000000 within print precision | same | same | added |
| mort_temp from SH1 day counts | 4.9e-7 | 4.9e-7 | 4.9e-7 | added |
| getbetaroot(D95max) | 6.2e-5 (bisection step 1e-4) | same | same | added |
| Longevity inside ±2σ corridor | max \|z\| 2.00004 | 2.00002 | 2.00003 | added |
| survive(): living trees outside limits | 0 | 0 | 0 | added |
| **height allometry log-R², Types 1-5** | 0.9941 / 0.9961 / 0.9997 / 0.9986 / 0.9958 | 0.9908 / 0.9947 / 0.9997 / 0.9989 / 0.9965 | **0.9890** / 0.9926 / 0.9996 / 0.9988 / 0.9959 — **FAIL** | ≥ 0.99 |

Also: params cpp = reference CSVs (29 columns); selftest; library mort_temp identical to SH1's helper (0 difference,
days 0-365 × 7 PFTs); eligibility reproduces round-1 probe C exactly (max |diff| 0) on the 3 of its 7 members that are
usable (the 4 late-century ones are skipped, not re-read).

Census (16 usable member-windows, 53-65 M tree rows each, not pre-registered): forbidden bands 0, print violations 0
everywhere; recursion failure rate ≤ 1.9e-6; whole chain within print precision on ≥ 0.9999999 of pairs. Censoring
per member (critic gap 8): G_low 127-490, npp_sat 0-5, G_sign 601-667, W capped 70-5677 (the most in MPI ssp126,
5409-5677; the least in ACCESS Historical).

Trait kernel, POOLED over PFTs (v2; kept in v3 only as a spec-level gate — the per-PFT gates above decide what is
verified). Share of new recruits with a trait outside their own PFT's interval; observed / predicted with truth
parents / the other build's prediction; tolerance max(25 %, 0.5 pp), set by the builder and not in the spec: all 8 pass.

| member (build that established the recruits) | Wooddens | D95max |
|---|---|---|
| MPI ssp370 s1 2015-44 (Dec-2025) | 0.0350 / 0.0315 / 0.0136 | 0.0519 / 0.0416 / 0.0313 |
| ACCESS ssp370 s2 2015-44 (Dec-2025) | 0.0465 / 0.0410 / 0.0192 | 0.0455 / 0.0366 / 0.0274 |
| MPI ssp245 s1 2015-44 (56 % Feb-2026) | 0.0195 / 0.0210 / 0.0315 | 0.0440 / 0.0355 / 0.0414 |
| ACCESS ssp245 s2 2015-44 (61 % Feb-2026) | 0.0269 / 0.0272 / 0.0410 | 0.0381 / 0.0309 / 0.0365 |

The spec's band "1.3-2.7 % for ssp245" was written for the late-century ssp245 windows (almost all recruits under
the newer build); in 2015-2044 only 56-61 % of the printed recruits were established by the newer build, so the
observed shares sit between the two builds (Wooddens 1.95-2.69 %).

**The one failure.** The C computes height from the pipe model, height = k_latosa · sapwood / (leaf · SLA ·
Wooddens) (`tree/allometry_tree.c`), so a fit on (agb, Wooddens, SLA) misses the hidden sapwood/leaf split. For the
needle-leaved Type 1 on the held-out-model Historical member the log-R² is 0.9890 (rmse of ln H 0.020, median
height error 0.5 %). Fitted in-sample on that member it is still 0.9894, and adding ln agb², ln agb·ln Wooddens and
ln agb·ln SLA gains < 0.0001 — so it is not a transfer or form problem; it is the limit of these three
predictors for Type 1 (v3 correction: not of the table — ln LAI and ln fpc_ind lift it to 0.9981). Not relaxed. Consequence: carry Height as tree state, or accept ~2 %
height noise for Types 1-2.

## What the gates found that a consumer must know

1. **The build that matters is the one that ESTABLISHED a recruit, not the one that printed it.** Recruits enter
   the table at ~10 yr old, so 44 % of the recruits printed in MPI ssp245 2015-2044 were established by the
   Dec-2025 Historical run. With the print-year build the kernel missed that member's Wooddens share by 35 % (0.0133 vs
   0.0203, smoke subset Cell % 100 == 0); with the establishment-year build it is within 8 % (full dev). `build_of(segments.bin_feb2026 at the establishment year)`.
2. *(v2 text, corrected in v3 above: the attribution holds for Wooddens, measured; it is untested for D95max, and the
   pooled agreement hid per-PFT misses of up to 6x.)* **The kernel under-predicts the out-of-interval share by 10-20 % in the Dec-2025 members (2015-2044)**, mostly in the minority
   PFTs (e.g. MPI ssp370 type 5 Wooddens 0.0256 observed vs 0.0111 predicted; beech 0.0404 vs 0.0368). Both traits
   imply that 0.79-0.88 of the visible recruits came through inheritance, against the closed-form 0.68 —
   inherited recruits reach 5 m more often than background (uniform-trait) ones. That is survival, i.e. the
   learned acceptance filter's job; the rule part is right. The diagnostic "the observed share is closer to this
   build's prediction than to the other build's" fails for one cell of the table (MPI ssp245 D95max), because of
   this common under-prediction.
3. **The counter has one ambiguous band (r ≈ 5)**: c = 4 with G → −∞ (almost no leaf area; the leaf-carbon rule then
   kills it, so `mort` = 1 does not disambiguate — tried: on a v1 smoke subset, recursion failures went from 3 to 202, all with c_prev = 3) or c = 5 with G ≈ 0.
   The tolerant formula reads c = 4; `recover_counter(..., c_prev=...)` resolves it when last year is known.
4. **|G| below ~0.01 is not identifiable** from 6-digit prints; 601-667 rows per member (all 16 usable members) got the wrong recovered
   sign and now carry censor 5 with the counter's sign.
5. **The leaf-carbon hard kill is not reproducible from the table** (needs leaf carbon): 196-878 printed hard kills per usable member have c < 5 and Σ parts < 1 (0.03-0.12 % of hard kills, ≤ 0.002 % of tree rows).
6. Leaf longevity: surviving trees sit slightly high in the corridor (mean z +0.1 for beech, +0.2-0.25 for types
   4/5; SD 0.86-0.88 vs 0.88 for the raw draw) — selection on survival, not a rule error.
7. Eligibility with the C-faithful current-year gdd5 differs from the round-1 probe's 20-yr gdd5 by ≤ 0.002 in
   share.

## Not done

* No rollout uses the library yet (SH6/tracks). The ORACLE-1 null (rule deaths on truth growth) is the end-to-end
  test of the mortality rules plus the fire identity; the chain gate here is its one-step, deterministic part.
* The fire fraction f is not reconstructed here (SH13 learns it); only the kill rule and floor.
* The bank's invisible sub-5 m members cannot be checked from any table.
* Late-century (2071-2100, 3071-3100) behaviour of every rule is untested here by owner decision; the rules are
  the C's and do not depend on the window, but none of the gates above covers those climates.
