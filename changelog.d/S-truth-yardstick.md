### Added

- **The reference model's own yardstick, on 51 767 of the 54 020 tree-bearing cells and both scenarios**
  (`EXECUTION_PLAN.md` rung 0, line S; ADR 0111). `scripts/build_truth_yardstick_tables.py` reduces all four
  ground-truth `ind` parquets (2.55 × 10⁹ stem-year rows) to small per-cell tables in 3.5 min;
  `scripts/diagnose_truth_yardstick.py` turns them into a stratified per-quantity noise floor on two stated
  bases, the reliability λ of the single-seed warming response for 1/2/4 seeds, an area-weighted +
  latitude-band aggregate response metric, and a re-scored deattenuated response slope for any copula table's
  out-of-sample predictions. Committed reference:
  `test/testitems/references/S_truth_yardstick_summary.csv` (272 rows).

### Fixed

- **Three independent errors in the yardstick the emulator's warming response was being judged against**
  (ADR 0111). ADR 0093 §3e had the reliability and the deattenuated slope **swapped** in the Wooddens and
  D95max rows; the reliability and the slope had been computed on **different bases** (log-space single-year
  vs linear all-years-pooled), so their quotient was undefined; and a per-patch density had been divided by
  the number of **occupied** patches, which cancels part of its own sampling noise and understated the sparse
  stratum's floor by 3× (10.5 % instead of 27.0 %).

### Changed

- **The `<2 stems/patch` tolerances quoted in an earlier record (31.6 % counts / 42.7 % carbon) are not exactly
  reproducible** — the stated-basis values are 27.3 % / 37.8 %. The year, dead stems and grass inclusion were
  each tested and ruled out as the cause; the remainder is an undocumented difference in that record's
  per-cell estimator. The new floor states its population and regenerates with one command.

- **The response panel, corrected on one self-consistent basis:** SLA over-responds by 25–35 % (previously
  read as "already correct"), Wooddens is the worst axis at 0.66–0.69, D95max is **not** the worst
  (0.72–0.85 — its small raw slope was mostly attenuation, its reliability being 0.198), minwscal is correct
  at 1.05. "Four broken axes" and "two broken axes at 0.63/0.51" are both retired.
- **The tree-count warming response is measured as faithful** — per-cell deattenuated slope 1.01, validated by
  a 0.9948 cross-check between two independent code paths — so "the response is indistinguishable from zero"
  is not true of counts; the response error lives in the trait axes. Counts are the mirror image of wood
  density: counts get the per-cell pattern right and under-shoot the global total (0.69×), wood density gets
  the total right (1.13×) and the pattern wrong (0.66).
- **The aggregate (area-weighted, latitude-banded) response is now the primary response statistic** and the
  per-cell map a reported secondary: area-weighted signal-to-noise is 25–489 against a per-cell 0.5–3.1.
- **Banding the response ratio found four wrong-signed regional responses that no earlier statistic could
  see** — tree counts in the tropics, specific leaf area in the subtropics and mid-latitudes, drought
  tolerance in the boreal zone — so the count shortfall is not a uniform 31 % under-response but a correct
  mid-latitude and boreal response plus a tropical response of the wrong sign. Ratios whose denominator is
  not determined by the reference data now print `n/d` instead of a number, which caught and retracted a
  draft claim of this work's own ("14 % of the height response") before it was published.
