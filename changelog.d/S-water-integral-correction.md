### Fixed

- **Correction to the previous entry's per-cell justification: the water signal, not the temperature one,
  is the larger term at ten of twelve cells
  ([ADR 0245 §0](docs/decisions/0245-the-water-integral-is-the-one-that-matters-and-a-correction-to-0244.md)).**
  The temperature-signal fix was justified in part by calling it "the dominant of the two at the cold
  cells", quoting a count of 24.1 stressed days a year at the boreal cell against a water figure of 0.34.
  That comparison was wrong in two independent ways and is withdrawn. The water figures came from a scan
  that took the first tree of each (year, plant type) group — valid for the temperature count, which is
  genuinely constant within such a group, but not for the water signal, which is per-tree and varies inside
  it (the true tree-weighted means are 0.414 / 0.035 / 2.361 / 1.270, not the sampled values). And the two
  raw signals are not commensurable in any case: one is an integer day count entering its death-risk term
  through a factor of 5/365, the other an unbounded humidity-weighted sum entering a different factor.
  On the statistic that *is* commensurable — each signal's cost in the mortality the original model's own
  stand asks for, which the earlier measurement had already produced per cell — **the temperature signal is
  the larger term at exactly one of twelve cells, ties at the cell that was named as the example, and the
  water signal is larger at the other ten**, costing 43 % of the nominated mortality at one cell on its own.
  **Nothing else about the previous entry changes:** both defects it found were real, the exact 4 334/4 334
  verification stands, the fix and its default remain, and the temperature signal is still worth 5.6–7.9 %
  of the total pooled and is still the only half that can be supplied exactly. ⚠ The lesson recorded with
  it: when a measurement already reports the comparable quantity per unit, quote that rather than forming a
  second comparison by hand — and a quantity that is constant within a group and one that varies within it
  cannot be summarised by the same one-line scan.
