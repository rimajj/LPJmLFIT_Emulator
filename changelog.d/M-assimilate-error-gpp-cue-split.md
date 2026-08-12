### Added

- **Rung 3: F's assimilate error at the temperate prototype is split into a photosynthesis and a
  respiration channel, and the split is a measured BRACKET rather than a number** (ADR 0129). The
  fast core takes in ~24 % more carbon per year than LPJmL-FIT does over the same trees, and that is
  77 % of its excess above-ground growth there — but "carbon taken in" is a net flux, and the two
  explanations on record each blamed a different half. Separating them by the exact identity
  `net uptake = photosynthesis × carbon-use efficiency` shows **both are live**: photosynthesis runs
  +8.4 % and carbon-use efficiency +14.0 % as measured. However, the tree list the reference model
  writes out drops every stem under 5 m, so the emulator's stand is missing trees that the reference's
  gross-photosynthesis output still contains. That biases the two channels in opposite directions by
  the same factor — leaving every previously published net-uptake number untouched, and leaving the
  split between the channels undetermined at anywhere from 38 % to 78 % photosynthesis. The
  year-to-year test that would settle it was measured to have a standard error of 3.6 on a quantity
  whose two candidate values are 0 and 1, i.e. it has no power and its apparent answer means nothing.
  Reported as a bracket. Closing it needs a small change on the reference model's side (writing out
  the short stems too), not another emulator experiment.
  New: `scripts/biome_sapwood_bg_probe.jl` PARTs 5/5b/5c; six columns appended to
  `test/testitems/references/M_growth_channel_decomposition.csv` (its 21 existing columns verified
  byte-identical, and the probe's own basis gate still passes). Nothing in `src/` changed.
