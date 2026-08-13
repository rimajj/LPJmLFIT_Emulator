### Added

- Line S: `NPREV` mode knob on both rung-2 map-target scorers
  (`scripts/diagnose_rung2_map_target_response.py`, `scripts/diagnose_rung2_map_on_rec_stand.jl`),
  selecting which `--n-prev` matrix of dumps is read. Default stays `roster`, so every published
  number reproduces unchanged. The Julia replay gained the shipped `n_prev[patch] = target`
  recursion, mirroring `rung2_s_demography_harness.jl`.
- Line S: a pre-registered SEPARABILITY GATE in the response scorer — median
  `|target/n_emit - 1|` per arm and leg, printed before any response statistic and suppressing the
  verdict for any arm that fails it (ADR 0184 §10.4). It refuses the `roster` matrix and admits the
  `predict` one at the same threshold.

### Changed

- Line S: the rung-2 warming-response limit is now attributed to the STAND the count model is
  conditioned on, not to the substitution operator (ADR 0185). On the 264-job `--n-prev=predict`
  matrix (258 completed), the map handed FIT's own stand reproduces FIT's gain direction at 4 of 5
  cells while the do-nothing null returns 1 of 5; handed each arm's own stand it returns 1–2 of 5.
  The pre-registered `CONDITIONING-LIMITED` branch fires. The operator-limited hypothesis is
  untested rather than refuted.
