### Fixed

- `scripts/diagnose_copula_capacity.sh` now passes `BLOCK_SALT` **explicitly** into
  `scripts/eval_slow_copula.jl` and echoes it in the `=== FOLDS:` header. It previously appeared nowhere in
  the driver, so a salt-1 rung depended on `sbatch --export=ALL` inheritance reaching a variable the Julia
  invocation's own env prefix did not list — and the log header would not have revealed a silent fallback to
  salt 0. That failure mode fabricates a *perfectly agreeing* blocked-CV replicate, which is exactly what
  ADR 0040 §5's "NOT RESOLVABLE if the two salts disagree" clause exists to detect, so it would have forced
  a false RESOLVED. Same class as ADR 0041's inert `random_seed` under `FROM_RESTART`.

- `scripts/diagnose_copula_capacity.sh` gained an `EXCLUDE=` knob that emits a real
  `#SBATCH --exclude=`. The `SBATCH_EXCLUDE` environment variable recommended for the known
  flaky-node mode is **not** a recognised sbatch input on this cluster and is ignored silently:
  job 1680828 died `0:53`/no-log on `cso14c74`, and the resubmission carrying
  `SBATCH_EXCLUDE=cso14c74` (job 1681087) landed on `cso14c74` again and died the same way.
