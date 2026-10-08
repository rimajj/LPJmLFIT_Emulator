### Added
- Line X: the model-version transfer split (GV) on Billing's global runs (`scripts/explore_glob_gv.py`, ADR 0315 §10).
  The May-2026 build is indistinguishable from the February build and an emulator trained on February runs transfers
  without loss; the October builds are four different models (biomass per tree differs by up to 30 % on identical
  forcing) and a February-trained emulator fails on them (0.3 % of cells vs 16 % run-to-run agreement).
