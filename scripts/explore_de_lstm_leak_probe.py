#!/usr/bin/env python3
"""explore_de_lstm_leak_probe.py -- LINE X: how exposed is the GERMANY cell-level LSTM (explore_de_rec_lstmstats.py)
to the input leak found in the global arm (ADR 0315 sec. 14.1)?

Its prediction input (ffill_seq, line ~777) fills missing state values forward and then BACKWARD over the whole
1985-2044 leg. So a state column missing in all of 1985-2014 (a treeless cell has no trait quantiles or PFT shares)
is back-filled from the test leg's own 2015-2044 truth for the S14 start; for the S85 start any column missing at
1985 is back-filled from the first later year that has it. This counts, per test leg, the exposed cells and their
share of the leg's 2015-2044 stems. No model is run.

Expected before the run: a handful of cells (Germany is almost fully forested; the global venue had 303 of 6 420).
"""

from __future__ import annotations

import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_rec_lstmstats as G  # noqa: E402


def main() -> None:
    i14 = G.YSPLIT - G.YEAR0
    print(f"years {G.YEAR0}-{G.YEAR1}, split {G.YSPLIT}", flush=True)
    for grp, (gcm, seed, scens) in G.TESTS.items():
        seq = G.build_sequences(gcm, seed, scens, "real")
        X = seq["X"]
        fin = np.isfinite(X)
        stems = np.exp(X[:, i14 + 1 :, 0]) - 0.05  # n per patch, 2015-2044
        # S14: a column missing in all of 1985-2014 but present in 2015-2044
        e14 = np.any(~fin[:, : i14 + 1].any(axis=1) & fin[:, i14 + 1 :].any(axis=1), axis=1)
        # S85: a column missing at 1985 but present in some later year
        e85 = np.any(~fin[:, 0] & fin[:, 1:].any(axis=1), axis=1)
        for sc in scens:
            m = seq["scen"] == sc
            tot = float(np.nansum(stems[m]))
            print(
                f"{grp} {sc}: cells {int(m.sum())} | S14-exposed {int(e14[m].sum())} "
                f"({float(np.nansum(stems[m & e14])) / tot:.4f} of 2015-2044 stems) | "
                f"S85-exposed {int(e85[m].sum())} ({float(np.nansum(stems[m & e85])) / tot:.4f})",
                flush=True,
            )


if __name__ == "__main__":
    main()
