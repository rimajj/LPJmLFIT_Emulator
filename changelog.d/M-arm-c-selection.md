### Added

- **Arm C of the rung-2 demography experiment** — the substituted per-individual mortality interface line S
  specified (ADR 0117 option (c)), run end-to-end against the LPJmL-FIT C oracle at cell 42490
  (25 patches, 2000–2019, 16 runs, 5 seeds per arm). `scripts/rung2_armc_harness.jl` is the Julia rendezvous
  server (it calls the *shipped* `TraitMortality.mortality_hazard` and `LPJmLFITEmulator._hazard_tilt`, never a
  copy of either), `scripts/run_rung2_armc.sh` submits one arm, `scripts/diagnose_rung2_armc.py` scores them.
  ADR 0124.

### Changed

- The rung-2 mortality interface is **adopted** in line S's option-(c) form: it is exact end-to-end live
  (ρ from the port vs the C's own `mort_prob` agree to 4.4e-16 over 5 000 patch-years; θ = 1 to 4.5e-14 over
  2 500; the C's audit shows `n_kill_applied/n_kill_c` 0.980–1.014 with **zero** trees spared that the C was
  certain of), and it reaches 1.050× on terminal stems, 0.952× on the wood-density selection differential and
  the per-PFT age–wooddens gradient ordering in 5 of 5 PFTs. **Those are ceiling numbers, not an emulator
  score** — with the count target taken from the operator's own hazard θ is 1 identically, so that arm *is*
  FIT's mortality with an independent draw.
- **The no-selection null (uniform ρ-thinning, the shipped default) fails on every statistic**: 1.209× stems,
  0.241× of the selection differential, one PFT's gradient backwards — and, the largest departure, it converts
  a mature stand into a young one (terminal `<20`/`20–40`/`≥40` yr stems 336–404/25–47/26–47 against the C's
  118/120/127) while keeping only 10–16 % of the C's own ≥40 yr individuals. **`C1 − C0` = 71.1 % of FIT's
  wood-density differential is differential survival**, so a count-only interface cannot reach it.

### Fixed

- Nothing in shipped code. Two measurement rules were corrected instead: FIT's **global** age–wooddens
  gradient fixture cannot serve as a **per-cell** acceptance target (the C's own recording at this cell scores
  Spearman ρ from −0.500 to +0.800 against it, so a naive reading would fail FIT itself), and an identity gate
  is only as wide as the state distribution it ran on (ADR 0122's gate had seen only the recorded trajectory;
  re-run on the null arm's — 7× the ghost-tree rate — it still holds exactly, and that re-run is now part of
  the procedure).
