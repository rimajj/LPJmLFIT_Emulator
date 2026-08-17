### Fixed

- **The emulator can hand the death-rate equation the original model's own heat/cold-stress signal
  EXACTLY — and two defects were stopping it
  ([ADR 0244](docs/decisions/0244-the-emulator-can-supply-fits-heat-cold-stress-integral-exactly.md)).**
  The previous decision record measured that running the ported death-rate equation on the inputs the
  coupled emulator passes today loses 22 % of the mortality the original model's own stand is asking for.
  Reading the code path against the original model before switching anything on found that simply enabling
  the switch would have handed over a *wrong* signal rather than a missing one — which is worse, because
  mis-directed deaths at the full rate destroy the stand while every stem-count diagnostic still looks
  fine. **(1)** The temperature signal was gated behind per-tree *water* state it does not need: the
  original model counts days outside each plant type's own tolerated temperature band and reads nothing
  else, so with the per-tree water option off — the shipped default — the temperature-driven death risk was
  silently zero even with the switch on. It is the **larger** of the two signals at the cold cells (24
  stressed days a year at the boreal cell against a water signal of 0.34), while at the dry cells the
  ordering reverses (21.1 against 0.0) — the two bind at **different** places, so neither is the small one.
  **(2)** Both signals — and the leaf-unfolding day count with them — are zeroed by the original model on a
  **fixed calendar day** that depends only on the hemisphere (day 14 north, day 195 south), *after* that
  day's increment, so the value its annual mortality step reads is not a calendar-year total at all. The
  emulator cleared them at the end of the calendar year instead. **Measured against the original model's
  own recorded values over 4 334 (cell, year, plant type) groups, no model run:** its own window reproduces
  them **4 334 / 4 334 exactly, integer for integer**, while a calendar year is wrong in **431** groups,
  over-counts the stressed-day total by **+17.1 %** and misses by up to **14 days** — and in the southern
  hemisphere the two windows differ by half a year. ⚠ The original model's own *comment* on that reset says
  "start of vegetation period" while its *code* says a fixed day; the code is the authority, and a
  phenological reading would not have reproduced the recorded values. Both defects are fixed, the reset day
  and the hemisphere test are now carried faithfully, and the behaviour is **inert by construction** for
  every existing configuration (the accumulator returns before touching anything while the switch is off).
  The switch had **no test and no probe at all**, which is how two defects survived in shipped code; it now
  has four assertions encoding the original model's semantics, including the surviving window in each
  hemisphere and at the equator. What is **not** fixed: the water signal still needs the per-tree rooting
  option, whose runtime cost is unmeasured, so it remains zero by default and the bracket around it
  (0.78 with nothing, 1.00 with the original's own values) is unchanged and still open.

  **The switch is now ON by default for the temperature half** (the water half stays off). Both full-suite
  runs — before and after the default change — came back **275 634 pass / 0 fail**, i.e. the change moved
  nothing in the tests. ⚠ That is a fact about the test fixtures, not about the change: the plant type used
  in the tests tolerates −20 to +54 °C, the widest band in the table, and no test's weather leaves it, so
  the suite **cannot witness** this switch at all. It was predicted for that reason before the run. The
  evidence that it works is the 4 334-group exact match and the new test's −30 °C arms; the default itself
  is now pinned by an assertion so a silent revert is loud. Where it does bite is the real cells: the
  original model's own count runs 0 to 24 stressed days a year across the twelve cells under study, three
  of them above 12.
