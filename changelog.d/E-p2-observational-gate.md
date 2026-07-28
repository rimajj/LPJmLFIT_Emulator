### Added

- **Component E is now validated against flux towers (line E, milestone E4 — the P2 gate; ADR 0072).**
  `scripts/build_e_seb_validation_table.py` stages a tower-forced driving table per PLUMBER2 site (the tower's
  own `swdown/lwdown/tair/psurf/wind`, its measured LE, its **observed albedo** from Σ SWup/Σ SWdown, its canopy
  and — load-bearing — its **measurement height**, which overrides `SEBParams.z_ref`), and
  `scripts/validate_e_seb_vs_plumber2.jl` runs `solve_seb` over every step and scores H, T_skin and Rn: bias,
  RMSE, MAE, R², OLS slope, all/day/**night**, half-hourly **and daily**, the fraction inside PLUMBER2's own
  `|h_cor_uc|` band, the mean diurnal cycle, and a `stab_amp`/`stab_k` sweep.
- **The gate is frozen as a regression test**: two committed extracts sampled every 12th day of year at every
  3rd hour across the whole record (`test/testitems/references/e4_seb_drive_{DE-Hai,AU-ASM}.csv`) re-run the same comparison inside
  `test/testitems/energy_closure_tests.jl`, with the known night-cold-bias pinned as a sign assertion so a
  future fix trips the test instead of drifting silently.

### Verdict (497 936 tower steps, 4 sites — full numbers in ADR 0072)

- **`Rn` verified:** R² 0.986–0.996, bias +1.95…+10.2 W/m², under the towers' own albedo.
- **`T_skin` verified where observable:** daily RMSE 1.41–1.97 K, R² 0.76–0.95 (AU-Tum / AU-ASM / AU-Rob).
  Not at Hainich — PLUMBER2 carries no `LWup` there.
- **`H` verified in the mean, not in variability:** every site's bias (+6.4 to −19.2 W/m²) is inside the
  dataset's own uncertainty and **76.4 % of DE-Hai daily means fall inside `|h_cor_uc|`**, but daily R² is 0.125
  (AU-Tum) to 0.778 (AU-ASM) and **nocturnal H has R² −1.0…−5.6 everywhere**.
- **Named failure mode:** the closure runs **1–2 K too cold at night** (modelled night `T_skin − Tair` −3.4/−2.6/
  −1.8 K vs observed −1.4/−1.7/−0.7 K) — too little nocturnal turbulent + ground coupling.
- **Methodological finding:** half-hourly H R² (0.647 at DE-Hai) is **inflated by the diurnal cycle**; the daily
  mean (0.257) is the honest number.
- **Stability correction:** ON beats OFF at night (RMSE 37.0 vs 41.7 DE-Hai; 29.7 vs 46.4 AU-ASM), and the sweep
  is monotone in `stab_amp` up to 0.9 ⇒ the 0.75 default is **too weak**. No default was changed (guardrail 4);
  the retune is an integration point with line M, and the monotonicity suggests the bounded-tanh *form*, not the
  coefficient, is the real limit.

### Fixed (in the validation itself, before the verdict was accepted)

- **`Qle_cor`/`Qh_cor` can be ≈0 garbage instead of a fill value.** At DE-Hai the uncorrected `le` is all-NaN for
  2010–2012 and the energy-balance correction emitted ≈0 there (annual mean `le_cor` 0.39 / −0.09 / 0.04 W/m²
  vs 30–40 W/m² in 2000–2009), so a finiteness filter kept 36 550 rows of it and the closure — fed LE ≈ 0 —
  put all the available energy into H, inflating DE-Hai's apparent H bias to +39.8 W/m². The driving-table
  builder now also requires the **uncorrected** `le` to be finite (DE-Hai → its 175 344 jointly-valid steps,
  matching ADR 0070's coverage). Found by the new regression fixture on its first run.
