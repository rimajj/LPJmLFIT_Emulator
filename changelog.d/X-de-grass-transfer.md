### Added
- Line X (Germany emulator prototype): grass-only replay that rebuilds a coupled run's grass state from its rosters
  and attributes the grass excess (`scripts/explore_de_grass_attrib.py`), one-step / five-step grass checks per
  climate model (`scripts/explore_de_grass_onestep.py`) and a training-weather-range check
  (`scripts/explore_de_grass_climrange.py`). Finding: the coupled grass excess on the held-out climate model is a
  transfer failure of the grass model's weather response; on the training climate model's second seed the carried
  hidden young-tree cover passes the late-period bars with no over-recruitment.
