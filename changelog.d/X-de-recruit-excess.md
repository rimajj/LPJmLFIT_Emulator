### Added
- Line X (Germany emulator prototype): `scripts/explore_de_recruit_drift.py` and `scripts/explore_de_recruit_attrib.py`
  — read-only probes that trace the free runs' excess recruitment to too-slow growth of large trees (the canopy stays
  open), not to the recruit model; the attribution rebuilds the recruit model's inputs from a roster, gates them
  against the stored training inputs, and swaps one input group at a time.
