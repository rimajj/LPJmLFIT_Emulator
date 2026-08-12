### Added

- **The exact three-channel decomposition of the fast core's surplus above-ground growth against the
  LPJmL-FIT oracle** (`scripts/biome_sapwood_bg_probe.jl`, fixture
  `test/testitems/references/M_growth_channel_decomposition.csv`, ADR 0127). Per biome cell and arm, the
  carbon identity `Δagb = assimilate − loss − Δbelow` is differenced against the C so the surplus splits
  exactly into an assimilate channel, a litter/reproduction channel and a below-ground-sink channel, in
  absolute gC/m²/yr. The probe is a second, independent reader of the rung-3 fixtures and is **gated on
  reproducing all 20 of ADR 0125's published `bmi`/`keep` numbers** before any new number is read.

### Changed

- **The `keep` (retained-fraction) statistic is retired as a headline** for the fast core's growth error
  (ADR 0127). At four of the five biome cells it was a ratio-form of the assimilate error already
  attributed elsewhere: at the Hainich prototype **77 %** of the surplus is the assimilate, **3 %**
  allocation, **20 %** the missing below-ground wood sink, and the emulator's absolute litter +
  reproduction flux is right to **1.8 %** while its `keep` ratio is 49 % high.
- `docs/notes/sapwood_bg_design.md` gains §9: the deferred prognostic-growth step needs **two** below-ground
  pools, not one (a single-field port either leaks ~22 gC/m²/yr or over-respires), and the sink it would
  close is now priced at 46 / 20 / 4 % of the surplus at the boreal / temperate / mediterranean cells.

### Fixed

- **ADR 0125's published `keep_F` for `semiarid_sahel` (0.350) is withdrawn as undefined.** It is a mean of
  per-year ratios whose denominator changes sign between years; the ratio-of-means is −0.059. Both
  definitions are now printed side by side and carried in the fixture.
