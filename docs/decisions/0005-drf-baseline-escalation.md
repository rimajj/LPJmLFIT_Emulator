---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "RESEARCH_SURVEY.md B, DEVELOPMENT_PLAN.md §2.2"
informed: "ADR 0002, the model card"
---

# Distributional Random Forest baseline for S, with an escalation ladder

## Context and Problem Statement

Component S must model `p(traits, size ∣ drivers, state)` + count `N`. Which method — a statistical
distributional regressor or a deep generative model? See `RESEARCH_SURVEY.md` B.

## Decision Drivers

- Data efficiency and interpretability at the prototype stage.
- Faithful **multivariate dependence** (trait trade-offs), not just marginals.
- Avoid mode collapse / small-data memorization.
- Keep a benchmark that any fancier method must beat.

## Considered Options

- **DRF** (Distributional Random Forest) — one forest returns the whole conditional joint as a
  weighted sample; + a negative-binomial/ZINB count model for `N`.
- **Moments + copula** (QRF/NGBoost/GAMLSS marginals + conditional copula).
- **Deep conditional generative** (TabDiff/TabSyn, conditional normalizing flow).
- **GAN-family** (CTGAN).

## Decision Outcome

Chosen: **DRF baseline + NB/ZINB count model**, with a documented **escalation ladder** to
TabDiff/TabSyn or a conditional normalizing flow **only if** the metric panel shows the baseline
misses multimodal or nonlinear/tail dependence. DRF is the best off-the-shelf first choice
(preserves trade-offs automatically, no parametric copula assumption, data-efficient). GANs are
avoided as first choice (instability, mode collapse), and diffusion can memorize on small data.

### Consequences

- Good: interpretable, data-efficient, dependence-aware baseline; a benchmark to beat.
- Good: matches the existing sibling stack (LightGBM/copula) and the Python `py311_new` env.
- Bad: may need escalation for hard dependence structure — kept as an explicit, gated path, not a
  default.
- Bad: DRF is not natively differentiable — the coupled system uses a Julia/Lux port (see
  [ADR 0007](0007-julia-primary-stack.md)).

## More Information

Evaluation panel (never one metric): KS/Wasserstein/CRPS + energy score **and variogram score** +
PCD + detection AUC + physical/allometric checks (`DEVELOPMENT_PLAN.md` §5). Keep the statistical
baseline as the benchmark to beat (`RESEARCH_SURVEY.md` B.2 caveats).
