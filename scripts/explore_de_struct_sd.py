"""explore_de_struct_sd.py — LINE X, Germany emulator, STRUCT track: diagnostic subclass of the
STRUCT stepper for the stem-loss diagnosis (pre-registration /p/tmp/jamirp/X_de/_status/SD.md).

class StructSD(explore_de_struct_stepper.Struct), kwargs (JSON) on top of Struct's:
  hmode     "allom" (default; identical to Struct: Height_{y+1} = fitted allometry of the new
            agb)
            "carry"      Height_{y+1} = Height_y * Hhat(agb_{y+1}) / Hhat(agb_y): the allometric
                         relative increment applied to the tree's OWN height (residual kept)
            "carry_mono" the same, never decreasing: Height_y * max(1, Hhat(agb_{y+1}) /
                         Hhat(agb_y))
  diag_tag  sub-directory for the per-chunk diag JSON (so diagnostic arms never overwrite the
            stored run's diag files)
  dump_dir  if set: per chunk and year one parquet of every tree's step internals
            (<dump_dir>/c<first>-<last>/y<y+1>.parquet: keys, hidden at y, Height y / y+1, agb
            y / y+1, G, latent z of G and dlagb, the three death channels, hidden at y+1, hazard,
            counter)
Run the arm under the STORED run's arm name (--arm struct_noacc) so the random streams are the
stored run's (Rand is keyed on arm, rep, gcm, stream, year, keys — not on chunk or leg);
hmode=allom then reproduces the stored rosters exactly (the gate), and any other hmode differs
ONLY through height.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_struct_stepper as st  # noqa: E402

rl = st.rl


class StructSD(st.Struct):
    def __init__(
        self, hmode: str = "allom", diag_tag: str = "sd", dump_dir: str | None = None, **kw
    ):
        super().__init__(**kw)
        assert hmode in ("allom", "carry", "carry_mono"), hmode
        self.hmode, self.diag_tag, self.dump_dir = hmode, diag_tag, dump_dir

    def init(self, state, ctx):
        super().init(state, ctx)
        d, f = os.path.split(self.diag_path)
        dd = os.path.join(os.path.dirname(d), f"_{self.diag_tag}", os.path.basename(d))
        os.makedirs(dd, exist_ok=True)
        self.diag_path = os.path.join(dd, f)
        self.diag["hmode"] = self.hmode
        cells = state.cell["cells"]
        if self.dump_dir:
            self.dump_path = os.path.join(self.dump_dir, f"c{int(cells[0])}-{int(cells[-1])}")
            os.makedirs(self.dump_path, exist_ok=True)

    def _height_next(self, t, agb, agb1, typ):
        hh1 = rl.predict_height(agb1, t["Wooddens"], t["SLA"], typ, self.allom)
        if self.hmode == "allom":
            return hh1
        hh0 = rl.predict_height(agb, t["Wooddens"], t["SLA"], typ, self.allom)
        r = hh1 / hh0
        if self.hmode == "carry_mono":
            r = np.maximum(r, 1.0)
        return t["Height"].astype(np.float64) * r

    def _hook(self, y, t, keys, hidden0, z, d, agb1, h1, dead_h, dead_s, dead_f, hidden1, mo, R):
        if not self.dump_dir:
            return
        n = len(t["Cell"])
        df = pl.DataFrame(
            {
                "Year": np.full(n, y + 1, np.int16),
                "Cell": np.asarray(t["Cell"], np.int16),
                "Patch": np.asarray(t["Patch"], np.int16),
                "Type": np.asarray(t["Type"], np.int8),
                "ID": np.asarray(t["ID"], np.int32),
                "SLA": np.asarray(t["SLA"], np.float32),
                "Wooddens": np.asarray(t["Wooddens"], np.float32),
                "Age": np.asarray(t["Age"], np.float32),
                "hidden0": np.asarray(hidden0, bool),
                "H0": np.asarray(t["Height"], np.float32),
                "H1": np.asarray(h1, np.float32),
                "agb0": np.asarray(t["agb"], np.float32),
                "agb1": np.asarray(agb1, np.float32),
                "G1": np.asarray(d["G"], np.float32),
                "p_gneg": np.asarray(d["p_gneg"], np.float32),
                "zG": np.asarray(z[:, 0], np.float32),
                "zdlagb": np.asarray(z[:, 2], np.float32),
                "dead_h": np.asarray(dead_h, bool),
                "dead_s": np.asarray(dead_s, bool),
                "dead_f": np.asarray(dead_f, bool),
                "hidden1": np.asarray(hidden1, bool),
                "mort": np.asarray(mo["mort"], np.float32),
                "c1": np.asarray(np.minimum(mo["c"], 5), np.int8),
            }
        )
        df.write_parquet(os.path.join(self.dump_path, f"y{y + 1}.parquet"))
