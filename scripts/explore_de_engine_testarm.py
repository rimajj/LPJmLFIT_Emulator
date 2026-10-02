#!/usr/bin/env python3
"""explore_de_engine_testarm.py — LINE X, Germany emulator: a deliberately random toy stepper for the engine's
determinism and chunk-boundary conformance tests (SH6 tests iii, iv). Not a model: every tree grows 2 % +- noise,
dies with probability 0.03, and each patch recruits Poisson(0.3) beech-like trees whose traits are copied from a
random seedbank member of the cell. All randomness goes through the engine's Rand, so the output must be
byte-identical for the same (arm, rep) whatever the chunking, and different for another rep."""
import explore_de_engine as en
import numpy as np


class Noisy:
    needs_bank = True

    def init(self, state, ctx):
        pass

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        t = state.tree
        keys = (t["Cell"], t["Patch"], t["Type"], t["ID"])
        z = rand.normal("grow", year, *keys)
        g = 1.02 + 0.01 * z
        upd = {f: t[f] * g for f in ("Height", "agb", "vegc", "fpc_ind")}
        upd["Age"] = t["Age"] + 1
        dead = rand.uniform("die", year, *keys) < 0.03
        hidden = t["hidden"].copy()
        cells = state.cell["cells"]
        npatch = state.npatch
        pc = np.repeat(cells, npatch)
        pp = np.tile(np.arange(npatch), len(cells))
        k = rand.poisson(np.full(len(pc), 0.3), "nrec", year, pc, pp)
        rc, rp = np.repeat(pc, k), np.repeat(pp, k)
        bank = state.cell["bank"]
        rec = {"Cell": rc, "Patch": rp, "Type": np.full(len(rc), 3)}
        for f in en.tr.TRAITS:
            rec[f] = np.zeros(len(rc), np.float32)
        for c in np.unique(rc):
            m = rc == c
            b = bank.filter(bank["Cell"] == c)
            idx = rand.generator("donor", year, c).integers(0, b.height, int(m.sum()))
            for f in en.tr.TRAITS:
                rec[f][m] = b[f].to_numpy()[idx]
        for f, v in (("Height", 5.5), ("agb", 2000.0), ("vegc", 2500.0), ("LAI", 1.0), ("fpc_ind", 0.002),
                     ("D95", 50.0), ("Age", 12.0)):
            rec[f] = np.full(len(rc), v, np.float32)
        return en.StepOut(tree=upd, isdead=dead, hidden=hidden, recruits=rec)
