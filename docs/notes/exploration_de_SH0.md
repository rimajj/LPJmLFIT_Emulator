# Germany emulator, shared item SH0: registry, segment flags, folds, shared climate-blind year map

> **v2 (2026-10-01): owner decision applied. Only the 1985-2044 data is used, see the last section. The v1 text below describes training on 2071-2100, which is superseded.**

Line X, round 2, 2026-10-01. Script `scripts/explore_de_sh_registry.py` (seconds, login node) plus the truth
cross-check `scripts/explore_de_sh_registry_datacheck.py` (SLURM job 2370634, about 1 min). Outputs and a
consumer README: `/p/tmp/jamirp/X_de/shared/registry/` (`_README.md`, `_gates.json`, `_datacheck.json`).

## What was built
* **members** (40 member-windows): the LPJmL job that actually wrote each tree table. It is found as the job whose
  SLURM start-end interval contains the moment the table's header (`.csv.json`) was written, and whose config
  matches the header's `history`. For each window it records the binary build, the config, the restart it
  started from, the patch count (250, parsed from the log, not assumed), the humidity flag, whether the window is
  truncated, which years are complete, and which one-step year pairs are usable.
* **segments** (14 072 rows): one row per (GCM, trajectory, seed, year). Historical runs cover 1950-2014; each ssp
  trajectory covers 1950-3100, and its years up to 2014 come from the same-seed Historical run. Each row carries
  the humidity flag and the binary flag, a segment id per C configuration, and the climate year the C actually
  read (after 2100, the per-seed recycled year recovered in round 1).
* **folds**: 9 065 tree cells → 52 one-degree blocks → 5 folds, assigned greedily (dev-cell count, then total
  count, then block id), so the result is deterministic. Each fold has 10-11 blocks, 1 772-1 855 cells and
  179-185 dev cells. Fold-mean 1985-2014 temperature is 8.98-9.26 °C for both GCMs, so the held-out fold 5 is
  not climatically unusual (9.10 °C MPI).
* **blind year map**: for each (GCM, replicate 1-4, year 1985-3100), one year drawn from 1985-2014. The same
  map is used by every cell and every arm. Draws use SHA-256 of `salt|gcm|r|year` mod 30, so they do not
  depend on numpy's RNG version.
* **splits / test_pairs** (added beyond the spec, because the critic's binding amendments needed a home):
  - DEV-A: train on MPI seed 1 Historical + ssp126 + ssp370 (windows h1985/w2015/w2071). Test on ACCESS
    ssp126/245/370 (truth seed 1) and MPI ssp245, which is scored against seed 2 (critic gap 2).
  - DEV-A2: train on MPI seed 1 Historical + ssp126. Test on MPI ssp370, truth seed 2. Same binary throughout
    (critic gap 7).
  - DEV-B: the mirror, ACCESS → MPI.
  - Every ssp245 trajectory is labelled "+ binary (different C build)" and `h4_contrast_ok = false`.

## Gates (all pass) [MEASURED]
* Folds: 9 065 cells, 52 blocks, every block in exactly one fold, 907 dev cells.
* Humidity flag: 0 in all 24 lpjml_2100/3100 segments of the 12 ssp members (720 trajectory-years) and 1 in all
  13 352 other years. Two independent readings agree on every row: a text grep of each config's `.js`, and
  LPJmL's own warning in the writer's `.err` log (`Name 'relative_humidity' ... set to false`).
* Humidity flag against the truth (dev cells, every member-window and year): in all 693 rh-off member-years,
  0 living trees have mort_water > 0. In all 480 rh-on member-years, at least one tree does (median share
  1.1-1.3 %, minimum 3e-6).
* Binary flag: the Feb-5-2026 build wrote every ssp245 segment and only those; the Dec-17-2025 build wrote
  everything else.
* Truncation: only MPI ssp370 seed 2 w3071 is truncated (complete years 3071-3072, usable pair 3071 only).
  Mechanism found [MEASURED, sacct + mtimes]: the successful run (job 6225106, 2026-01-05) was overwritten by a
  re-run (job 6746126, 2026-01-30) that was cancelled after 4 minutes.
* Writer attribution: each of the 40 windows was written by the last attempt of its segment.
* Restart chain: every segment starts from the restart written by the previous segment (ssp 2044 starts from
  the same-seed Historical restart_2014). Each spinup log's `Random seed` matches its seed directory.
* Segment keys are unique, no year gaps, and no `pair_ok` across the 2044→2071 or 2100→3071 gaps.
* Pairs per ssp trajectory: 117 = 29 (1985-2013) + 1 (2014→2015) + 29 + 29 + 29.
* Determinism: a rebuild in a fresh process is byte-identical (sha256) for all 7 tables, and `check` mode reports
  every table identical. The four blind-map replicates differ from each other in ≥ 95.6 % of years.

## Caveats
* **The blind map is i.i.d. by year, as the spec says.** This removes year-to-year persistence along with the
  trend. Baseline lag-1 autocorrelation of the dev-mean climate after detrending, over 30 years (standard error
  about 0.18):
  - MPI annual temperature: 0.43
  - MPI precipitation: 0.28
  - ACCESS temperature: -0.22
  - ACCESS precipitation: 0.13
  - summer water balance: 0.00 (MPI), 0.21 (ACCESS)

  So only MPI temperature carries persistence that is clearly above noise, and a climate-blind arm loses it. The
  1985-2014 baseline itself warms by 0.44-0.49 K/decade, so the blind climate is the baseline average, not 1985.
* The segment ids split the spec's "2101-3100" into 4 (2101-3070) and 5 (3071-3100), because the two C
  configurations differ in the humidity flag (on, then off).
* The humidity flag is a property of the configuration, not of the climate. Carry it as an input, and never use
  it to "fix" the truth.

## v2 revision, 2026-10-01: the owner's decision to use only the correct 1985-2044 data

**What changed and why.** The owner asked to double-check that the 2071-2100 and 3071-3100 runs used the wrong
humidity setting and, if so, to use only the earlier, correct data. The registry now checks it and enforces it.

* **Three independent readings agree on all 64 final C segments** [MEASURED]:
  1. The config text: `relative_humidity: true` is present in every 2015-2044, 2045-2070 and 2101-3070
     configuration and in Historical. It is absent in every 2071-2100 and 3071-3100 configuration of all 12
     scenario members, and LPJmL's default is false.
  2. LPJmL's own warning in the error log: it set the flag to false for exactly those 24 segments.
  3. The input table in the run log: those 24 segments list the humidity input as `humid` (read as specific
     humidity). All 40 others list it as `rhumid`. All of them read the same file (`HRMean_*_germany.clm`), which
     holds relative humidity.
* **Confirmed on the truth itself** (SLURM job 2371073; dev cells; 12 scenario members, both seeds) [MEASURED]:
  - Share of living trees with water-stress mortality above 0: 0.016-5.1 % in 2015, 0.076-9.4 % in 2044, and
    exactly 0 in 2071 and in 2100 for all 12 members.
  - All 693 member-years in the excluded windows have no such tree.
  - All 480 member-years in the kept windows have at least one.
* **How the exclusion is derived.** It comes from the data, not from a list of years. A simulated year counts as
  clean only if its own configuration and every configuration upstream in its restart chain read humidity
  correctly. In this archive the first unclean year is 2071 in all 12 scenario trajectories, and no Historical
  year is unclean. The years 2101-3070 are excluded too, because they restart from the corrupted 2100 state. The
  years 2045-2070 are clean but have no tree table. They are marked `no_tree_table`, for the optional check
  against cell totals only.
* **Effects in the tables:**
  - All 24 late-century windows are marked `excluded`. Each has a reason and the owner decision attached, and
    all are kept on disk. In `splits` their role is `excluded_rh_off`, and no train, test, reference or
    equilibrium role points at them.
  - One-step pairs: 476 member pairs remain, out of 1 144 before. That is 59 per scenario trajectory
    (1985→2044) and 29 per Historical run. `pair_ok` is now true only for clean pairs. The old value is kept
    as `pair_ok_raw`.
  - Test pairs score only 1985-2014 and 2015-2044. Start years are 1985 (headline) and 2014 (secondary). A free
    run ends at 2044, or at 2070 if it is checked only on cell totals.
  - The climate-blind year map now ends at 2070. Its 1985-2070 rows are byte-identical to the earlier map.
  - New table `contrasts`: the response statistics. The primary one is the difference between scenarios at
    fixed GCM and seed in 2015-2044. The binding version is ACCESS-CM2 ssp370 minus ssp126 for the headline
    split, truth seed 1, both legs held out and the same binary. The change from 1985-2014 to 2015-2044 is
    listed as secondary. Any contrast with an ssp245 leg is labelled "different binary".
* **Gates:** 15 of 15 pass, adding six to the original nine. The rebuild is byte-identical, and `check` reports
  all 8 tables identical.
* **Limitation to disclose with every result:** the warming this data can test is the early-century warming
  (2015-2044) only. The late-century runs are unusable until the owner re-runs them with the humidity setting
  fixed.
* The pre-decision tables, script, gates and report are kept in
  `/p/tmp/jamirp/X_de/shared/registry/_superseded_v1_pre_owner_exclusion/`.
