### Changed

- **Milestone S2's gate is MET for the first time, and ADR 0037's thesis is superseded (ADR 0038).** The
  12-rung QRF × capacity matrix completed. The ESTIMATOR lever is the larger one on `emu_r` (+0.050 vs
  +0.037) but **saturates at Wooddens 0.867** — fitted asymptote 0.870, and reaching the 0.889 threshold by
  capacity alone would need ~1000× the entire 197 721 867-row table — so it cannot close the gap at any
  artifact size. `ncond` 8→14 at **fixed** 6×2M/d22/QRF=1 delivers **+0.037 `emu_r` and +0.0966 `sd_ratio`**,
  the larger lever on criterion 2 (the axis that was actually failing), and carries both criteria across.
  **S2's premise — "expand the conditioning" — is vindicated, not refuted:** the estimator had to be fixed
  *before* the conditioning could pay, because at 50k subsample there is ~0.93 rows/cell and six extra
  columns have no resolution in which to express themselves. ADR 0037's "second-order lever, ~4× smaller" is
  wrong by ~4× in the opposite direction, and its 0.916 was a per-cell **LightGBM upper bound** that did not
  transfer to the DRF.
  Shipped config `env-qrf-b6x2M` (6 trees × 2M subsample, `max_depth` 22, `min_leaf` 20,
  `QRF=1`, `ncond` 14): Wooddens `emu_r` **0.901** (58.0 % of the GAP closed, and ≥56.7 % under all five
  defensible conventions), `sd_ratio` **0.8541**, pooled KS improving on **all four** axes
  (.0032/.0024/.0019/.0013), `r_center` gaining on all four. The comparison is PAIRED (folds and quantile
  levels depend only on cell id / row index) and its basis is identical at the **inode** level.
  Artifact `recruit_copula_global_historic_t9.rcop`: 507 985 666 B, **load 6.77 s = 71.6 MiB/s measured**
  (an earlier "~12 s at 42 MB/s" was never measured), byte-reproducible across independent re-runs. `b6x8M`
  rejected: +0.002 `emu_r` for 4× the bytes and worse pooled KS on all four axes.
- **The `.rcop` size coefficient is 10.58**, not 10.7 (`bytes ≈ C·ntrees·subsample·naxes`; t8 gives 10.66).
- **The subsample lever is exhausted past ~2M rows/tree at BOTH conditioning widths** (+0.003 at `ncond` 8,
  +0.002 at 14); the *level* it plateaus at is set by the conditioning, not by capacity. The "tree count is
  inert" trio (12/24/40 × 500k) is a different experiment and is **not** evidence of subsample saturation.
- **QRF's payoff shrinks as capacity grows, and the mechanism is measured**: the pooled-default max-leaf
  weight share is median 11.2 % at t8's 60 trees = 6.7× QRF's `1/T`, but median 48.9 % at t9's 6 trees =
  only 2.9× — so what QRF corrects is largely absent at 6 trees (+0.013 `emu_r` at 40 trees/50k vs +0.002 at
  6 trees/2M, where it also *costs* 0.013 of dispersion).

### Added

- **`.rcop` format v2 carries `qrf`** (`DRF.save_copula(...; qrf)` / `load_copula` → 6-tuple). The QRF leaf
  weighting selects a different conditional distribution from the same forests and previously lived ONLY in
  the sidecar `_meta.txt`, while line M's contract pins a `.rcop` *path* — so a consumer that missed the
  sidecar silently sampled the estimator that was not scored, with every draw in range. Flipping it changes
  all three of t9's golden draws. v1 still loads and means `qrf = false`, `qrf` is the sixth tuple element so
  all five pre-existing 5-way call sites are untouched, and a forged v99 header is refused ⇒ guardrail 4
  holds and nothing line M pinned needs regenerating. Recorded as a **version bump** of the frozen S→M
  contract, not a mutation.
- **`FluxDrivenSlowEmulator` rejects a conditioning-width mismatch at CONSTRUCTION.** `DRF._check_nfeat`
  fires only inside `sample_copula!`, reached only when a patch actually recruits — so a cell that thins
  every year, or an all-grass patch, never draws, and a mis-wired coupled run completes "successfully" while
  conserving carbon. The constructor is the only place holding both the boundary and the copula, so it now
  probes the policy once. A new testitem builds a 14-column `qrf=true` copula **through the emulator** (a
  composition no test had ever run), plus both crossed mismatches and a wrong-length boundary.
- Measured the previously-unmeasured **leaf geometry at the production config** (`rcop_leaf_geometry_probe.jl`
  on t9): 33 449–46 036 leaves/tree, **52.3–67.0 % of stored values still depth-capped**, and only 84–86 % of
  large leaves at `max_depth` (vs 99.9–100 % at 50k/d14). Depth is therefore **not** exhausted at d22/2M and
  is still free in bytes.

### Fixed

- **The ADR-0030 gate now refuses to quote a floor from two seeds that are the same seed.** The ceiling is
  `sqrt(rel_P·rel_Y)` with `rel_Y = floor_r`, so a duplicated realization gives `floor_r ≡ 1` and fabricated
  headroom on every axis, with no error — and the existing `seed1-basis ≥ 0.99` check compares a table to the
  parquet of the *same* seed, so it reads 1.000 and is structurally blind. **The ssp370
  `..._random_seed2` ground truth IS such a duplicate**: `ind_2020_2100.csv` is 193 097 583 638 B in both
  seeds with equal md5 on blocks at MB 0/30000/120000, because its config sets `"random_seed": 2` but its
  `restart_filename` points at the *historic seed1* `restart_2019.lpj` — under `-DFROM_RESTART` the per-cell
  RAND48 state is restored, making the seed inert. (The historic pair is genuinely independent: each reads
  its own relative `restart/restart_1999.lpj`.) Self-tested both ways: the negative control aborts, the
  positive control passes and reproduces the published baseline exactly.
- **The struct-axes disagreement message was misdirected.** It said "Rebuild the seed2 table with the same
  `STRUCT_AXES`", but the seed2 tables *do* carry agb+Height — it is the seed1 **shadow** manifest that
  `diagnose_copula_capacity.sh`'s `TRAIT_ONLY=1` trimmed. Following it cost a pointless multi-hour rebuild
  and fixed nothing. The message now names the narrower side and points at `TRAIT_ONLY`.

### Deprecated

- **`recruit_copula_global_historic_t9.rcop` is the historic-STATIC artifact and is NOT line M's production
  copula.** The six env columns have within-cell sd **exactly 0 for 100 % of cells** — they are per-cell
  constants broadcast across years, so they cannot encode a warming response, and in the pooled table a
  cell's historic and ssp370 rows carry bit-identical env values. A 1-NN lookup on those columns reaches
  Wooddens r = 0.800 with a median distance to the nearest training neighbour of **1.00°** (q25 = 0.50°, the
  adjacent cell), against r = 0.445 / 14.51° for the existing boundary constants — so they resolve to a
  geographic address, and K-fold-**by-cell** CV cannot separate a transferable environmental response from
  spatial interpolation. The +0.037 is a valid offline gain whose generalization is **unestablished**;
  production turns on a spatially blocked re-score, which is now the named next step.

### Documentation

- **Recorded that `run_global_slow_copula.sh` scores a different estimator than it ships**: `NTREES` (60)
  feeds `train_slow_copula.jl` ⇒ the shipped `.rcop`, while `EVAL_NTREES` (40) feeds `eval_slow_copula.jl` ⇒
  the scored OOS. So every published **t8** gate number describes a 40-tree estimator while the artifact line
  M pins is 60-tree (read off the artifacts: t8 `ntrees=60`, 3 000 000 stored leaf values = 60 × 50 000; t9
  `ntrees=6`, 12 000 000 = 6 × 2 000 000). **t9 is the first generation where the two agree.** Tree count is
  nearly inert for skill (±0.002 over 3.3×) so the t8 headline barely moved, but it is *not* inert for the
  leaf-weight skew the QRF argument rests on (6.7× `1/T` at 60 trees vs 2.9× at 6) — attribute weighting
  figures to the right object. Also resolves the apparent "40 vs 60" contradiction in
  `diagnose_copula_capacity.sh`'s size comment: both are right, about different objects.
