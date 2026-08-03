### Fixed

- `scripts/diagnose_copula_capacity.sh` now passes `BLOCK_SALT` **explicitly** into
  `scripts/eval_slow_copula.jl` and echoes it in the `=== FOLDS:` header. It previously appeared nowhere in
  the driver, so a salt-1 rung depended on `sbatch --export=ALL` inheritance reaching a variable the Julia
  invocation's own env prefix did not list — and the log header would not have revealed a silent fallback to
  salt 0. That failure mode fabricates a *perfectly agreeing* blocked-CV replicate, which is exactly what
  ADR 0040 §5's "NOT RESOLVABLE if the two salts disagree" clause exists to detect, so it would have forced
  a false RESOLVED. Same class as ADR 0041's inert `random_seed` under `FROM_RESTART`.
