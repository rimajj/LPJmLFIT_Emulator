"""One table from speedy_cold_bias_repro.jl logs (cold-bias experiments on SpeedyWeather).

    python summarize_speedy_cold_runs.py logs/speedy-E*.out [...]

Columns: global air T, top-of-atmosphere net, reflected SW, OLR (last year), tropical OLR and
reflected SW, ice-free ocean air - SST (tropics, >= 50), and, if the run had LANDREF, the land
columns minus the W5E5 observations (annual, warmest, coldest month, > 50 deg, precipitation).
Missing values print as -.
"""

from __future__ import annotations

import re
import sys


def num(pattern, text, group=1):
    m = re.search(pattern, text, re.M)
    return float(m.group(group)) if m else None


def parse(path):
    t = open(path, errors="replace").read()
    years = re.findall(r"^\s+year\s+\d+\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$", t, re.M)
    last = [float(x) for x in years[-1]] if years else [None] * 4
    land = lambda q: num(rf"^\s+{q}\s+\S+\s+\S+\s+(\S+)$", t)  # noqa: E731
    z = t[t.find("by latitude") :] if "by latitude" in t else ""  # the zonal block
    return {
        "air": num(r"global mean near-surface air temperature :\s+(\S+)", t),
        "net": last[3],
        "osr": last[1],
        "olr": last[2],
        "olr_tr": num(r"^\s+\|lat\| < 15 \s+(\S+)\s+(\S+)", z),
        "osr_tr": num(r"^\s+\|lat\| < 15 \s+(\S+)\s+(\S+)", z, 2),
        "dT_tr": num(r"^\s+\|lat\| <  15\s+\S+\s+\S+\s+(\S+)$", t),
        "dT_hi": num(r"^\s+\|lat\| >= 50\s+\S+\s+\S+\s+(\S+)$", t),
        "land": land(r"annual air T °C"),
        "warm": land(r"warmest month °C"),
        "cold": land(r"coldest month °C"),
        "hi50": num(r"annual air T model - obs, > 50\s+(\S+) K", t),
        "pr": land(r"precip mm/yr"),
        "done": "JOB DONE exit=0" in t,
    }


COLS = [
    ("air", "air°C", 6),
    ("net", "TOAnet", 7),
    ("osr", "OSR", 6),
    ("olr", "OLR", 6),
    ("olr_tr", "OLRtr", 6),
    ("osr_tr", "OSRtr", 6),
    ("dT_tr", "dTtr", 6),
    ("dT_hi", "dThi", 6),
    ("land", "land", 6),
    ("warm", "warm", 6),
    ("cold", "cold", 6),
    ("hi50", ">50", 6),
    ("pr", "pr", 7),
]


def main():
    print(f"{'run':34s}" + "".join(f"{h:>{w}s}" for _, h, w in COLS))
    for p in sys.argv[1:]:
        r = parse(p)
        name = p.split("/")[-1].rsplit(".", 2)[0] + ("" if r["done"] else " (unfinished)")
        cells = "".join(
            f"{r[k]:>{w}.1f}" if r[k] is not None else f"{'-':>{w}s}" for k, _, w in COLS
        )
        print(f"{name:34s}{cells}")
    print("land/warm/cold/>50/pr = model - W5E5 obs at the 1 197 T31 land columns (K, mm/yr)")
    print("dT = ice-free ocean air - SST (K)")


if __name__ == "__main__":
    main()
