#!/usr/bin/env python3
"""explore_glob_tabroot.py -- LINE X: build a Germany-format data root (XDE_ROOT) over the GLOBAL venue so the
per-tree TAB chain (explore_de_sh_* / explore_de_tab_* / explore_de_engine) runs on Billing's global runs unchanged
except for its env-gated knobs. Map, blockers and stage order: docs/notes/exploration_glob_tab_port.md.

ROOT  <DATA>/xde   (DATA = the global venue, ADR 0313-0315)
  shared/registry/cell_map.parquet
      Cell (= Cell16, 0..N-1, what every table below carries) <-> Cell_orig (grid.bin order). N = the global
      registry's dev cells (Cell_orig % 10 == 0) that are not rock. Renumbering removes the Int16 cell-id casts of the
      Germany chain (blocker B1) without code changes; map Cell back before scoring with explore_glob_eval.
  ind_dev/<member>.parquet
      29-column per-tree tables, Cell16 (Int16 here, Int32 elsewhere -- as in Germany), Germany member names
      <gcm>_Historical_s<k>_h1985 / <gcm>_<ssp>_s<k>_w2071 (SH2 reads them BY NAME)
  shared/registry/members.parquet
      the Germany schema (the columns the chain reads), npatch 25, rh_on 1 (Billing reads specific humidity
      correctly, ADR 0314 sec. 2), bin_feb2026 1 (both builds postdate the stale-slot fix), nothing excluded
  shared/registry/segments.parquet
      per (gcm, traj, seed, Year): Historical 1951-2014; each ssp trajectory 1951-2100 with clim_scen Historical
      <= 2014. pair_ok: Historical 1985-2013; ssp 2071-2099 (the ssp window's chain starts fresh at 2071 -- see the
      SH3/SH4 non-contiguous-window handling)
  shared/registry/folds.parquet    Cell16, block, is_dev = True, fold (the global 5-degree folds), lon, lat
  shared/registry/splits.parquet   split DEV-A = GS370's training side: train = seeds 2,3,4,6 x (Historical,
      ssp126, ssp245); test_truth = seed 8 (all legs); test_ref = seed 7 (all legs)
  climate/cell_year.parquet        the GFDL-ESM4 historical + ssp tables, scen "historical" -> "Historical", Cell16
  climate/cell_static.parquet      Cell16, lon, lat, soil_code
  shared/climate/cell_year_ext.parquet
      key + excluded / exclusion_reason / truth_usable + the anomalies the global tables lack (vs the same cell's
      1985-2014 Historical mean): anom_<f>_tr20, anom_tstress_pft0..6, anom_vpd_{mean,jja,win10_sum}_eff
  shared/climate/clim8514.parquet  (gcm, Cell16) + the 1985-2014 mean of every numeric climate column

MEMBERS  the Feb-5-2026 build GFDL-ESM4 members 2,3,4,6,7,8 (GS370's train / replica / truth); the May build and the
GSWP3 reanalysis members are not included (ADR 0315 sec. 11: one build per emulator).

GATES (_gates.json): cell_map bijective and < 32768; every member's dev table has exactly the mapped cells' rows
(row count equal to the source's rows of those cells); climate key unique and complete (every Cell16 x year);
anomalies: anom_tmean_ann recomputed independently on 1985-2014 has mean 0 per cell (|mean| < 1e-4).

Run: explore_glob_tabroot.py [all|cells|ind|registry|climate|gates]   (~15 min, SLURM: scripts/sbatch_python.sh)
"""

from __future__ import annotations

import json
import os
import sys
import time

import polars as pl

DATA = "/p/projects/open/Jamir/esm_land_emulator_data/billing_global"
ROOT = os.environ.get("XDE_ROOT", os.path.join(DATA, "xde"))
GREG = os.path.join(DATA, "registry")
GCM = "GFDL-ESM4"
SEEDS = (2, 3, 4, 6, 7, 8)
SSPS = ("ssp126", "ssp245", "ssp370")
TRAIN_SEEDS, TRUTH, REPLICA = (2, 3, 4, 6), 8, 7
TRAIN_SCEN = ("Historical", "ssp126", "ssp245")
NPATCH = 25
HIST = (1985, 2014)
WIN = (2071, 2100)
SEG_FIRST = 1951
BASE = (1985, 2014)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def p(*parts):
    return os.path.join(ROOT, *parts)


def gname(scen: str, seed: int) -> str:  # the global registry's member name
    return f"{GCM}_{scen}_s{seed}_{'h1985' if scen == 'historical' else 'w2071'}"


def dname(scen: str, seed: int) -> str:  # the Germany-format member name
    h = scen == "historical"
    return f"{GCM}_{'Historical' if h else scen}_s{seed}_{'h1985' if h else 'w2071'}"


def cmap() -> pl.DataFrame:
    return pl.read_parquet(p("shared", "registry", "cell_map.parquet"))


# ------------------------------------------------------------------------------------------------ cells
def stage_cells():
    os.makedirs(p("shared", "registry"), exist_ok=True)
    f = pl.read_parquet(os.path.join(GREG, "folds.parquet")).filter(pl.col("is_dev") & ~pl.col("rock")).sort("Cell")
    m = f.select(pl.col("Cell").alias("Cell_orig")).with_row_index("Cell").with_columns(
        pl.col("Cell").cast(pl.Int32))
    assert m.height < 32768
    m.write_parquet(p("shared", "registry", "cell_map.parquet"))
    f.join(m, left_on="Cell", right_on="Cell_orig").select(
        pl.col("Cell_right").alias("Cell"), "block", pl.lit(True).alias("is_dev"), "fold", "lon", "lat"
    ).sort("Cell").write_parquet(p("shared", "registry", "folds.parquet"))
    st = pl.read_parquet(os.path.join(DATA, "climate", "cell_static.parquet"))
    os.makedirs(p("climate"), exist_ok=True)
    st.join(m, left_on="Cell", right_on="Cell_orig").select(
        pl.col("Cell_right").alias("Cell"), "lon", "lat", "soil_code").sort("Cell").write_parquet(
        p("climate", "cell_static.parquet"))
    log(f"cells: {m.height} dev non-rock cells mapped")


# ------------------------------------------------------------------------------------------------ per-tree tables
def stage_ind():
    os.makedirs(p("ind_dev"), exist_ok=True)
    m = cmap()
    gm = pl.read_parquet(os.path.join(GREG, "members.parquet"))
    for seed in SEEDS:
        for scen in ("historical",) + SSPS:
            src = gm.filter(pl.col("member") == gname(scen, seed))["ind_dev_path"].item()
            out = p("ind_dev", f"{dname(scen, seed)}.parquet")
            if os.path.exists(out):
                continue
            t0 = time.time()
            d = (pl.scan_parquet(src).join(m.lazy(), left_on="Cell", right_on="Cell_orig", how="inner")
                 .drop("Cell").rename({"Cell_right": "Cell"}).with_columns(pl.col("Cell").cast(pl.Int16))
                 .sort("Year", "Cell", "Patch", "Type", "ID").collect())
            d.write_parquet(out, compression="zstd", statistics=True, row_group_size=500_000)
            log(f"{dname(scen, seed)}: {d.height} rows ({time.time() - t0:.0f}s)")


# ------------------------------------------------------------------------------------------------ registry
def stage_registry():
    gm = pl.read_parquet(os.path.join(GREG, "members.parquet"))
    rows, segs, spl = [], [], []
    for seed in SEEDS:
        for scen in ("historical",) + SSPS:
            g = gm.filter(pl.col("member") == gname(scen, seed)).row(0, named=True)
            assert g["build"] == "Feb 5 2026", g
            s = "Historical" if scen == "historical" else scen
            y0, y1 = HIST if scen == "historical" else WIN
            yrs = list(range(y0, y1 + 1))
            pairs = list(range(y0, y1))
            name = dname(scen, seed)
            rows.append(dict(member=name, gcm=GCM, scen=s, seed=seed, win="h1985" if s == "Historical" else "w2071",
                             ind_path=p("ind_full_not_built"), ind_dev_path=p("ind_dev", f"{name}.parquet"),
                             src_csv=None, build=g["build"], npatch=NPATCH, rh_on=1, rh_on_log=1, bin_feb2026=1,
                             years_present=yrs, years_complete=yrs, n_years_complete=len(yrs),
                             usable_pair_years=pairs, n_pair_years=len(pairs), truncated=False, conversion_ok=True,
                             excluded=False, exclusion_reason=None, excluded_by=None, global_member=g["member"],
                             run_dir=g["run_dir"]))
            # segments: one trajectory per (scen, seed); an ssp trajectory carries the historical years too
            last = HIST[1] if s == "Historical" else WIN[1]
            for y in range(SEG_FIRST, last + 1):
                in_hist = y <= HIST[1]
                if s == "Historical":
                    pair_ok = HIST[0] <= y < HIST[1]
                else:
                    pair_ok = (HIST[0] <= y < HIST[1]) or (WIN[0] <= y < WIN[1])
                tw = ("h1985" if HIST[0] <= y <= HIST[1] else ("w2071" if WIN[0] <= y <= WIN[1] else None))
                segs.append(dict(gcm=GCM, scen=s, seed=seed, Year=y, src_scen="Historical" if in_hist else s,
                                 build=g["build"], bin_feb2026=1, rh_on=1, rh_on_log=1, humid_kind="huss",
                                 run_ok=True, tree_window=tw, tree_year_complete=tw is not None,
                                 pair_ok_raw=pair_ok, clim_scen="Historical" if in_hist else s,
                                 clim_recycled=False, clim_year=y, chain_clean=True, excluded=False,
                                 exclusion_reason=None, pair_ok=pair_ok,
                                 use="trees" if tw is not None else "no_tree_table"))
            role = ("train" if (seed in TRAIN_SEEDS and s in TRAIN_SCEN) else
                    "test_truth" if seed == TRUTH else "test_ref" if seed == REPLICA else "unused")
            spl.append(dict(split="DEV-A", gcm=GCM, scen=s, seed=seed, win=rows[-1]["win"], src_member=name,
                            role=role, h4_contrast_ok=True, kind="GS370 (ADR 0315)", excluded_by=None))
    seg = pl.DataFrame(segs).with_columns(pl.col("seed").cast(pl.Int32), pl.col("Year").cast(pl.Int32),
                                          pl.col("clim_year").cast(pl.Int32), pl.col("bin_feb2026").cast(pl.Int64),
                                          pl.col("rh_on").cast(pl.Int64), pl.col("rh_on_log").cast(pl.Int64))
    # one trajectory row per (gcm, scen, seed, Year): drop the duplicate the four windows of one seed would create
    seg = seg.unique(["gcm", "scen", "seed", "Year"], keep="first", maintain_order=True).sort(
        "gcm", "scen", "seed", "Year")
    pl.DataFrame(rows).write_parquet(p("shared", "registry", "members.parquet"))
    seg.write_parquet(p("shared", "registry", "segments.parquet"))
    pl.DataFrame(spl).write_parquet(p("shared", "registry", "splits.parquet"))
    log(f"registry: {len(rows)} members, {seg.height} segment rows, {len(spl)} split rows")


# ------------------------------------------------------------------------------------------------ climate
def stage_climate():
    m = cmap()
    os.makedirs(p("shared", "climate"), exist_ok=True)
    parts = []
    for scen in ("historical",) + SSPS:
        d = (pl.scan_parquet(os.path.join(DATA, "climate", "cell_year", f"{GCM}_{scen}.parquet"))
             .join(m.lazy(), left_on="Cell", right_on="Cell_orig", how="inner").drop("Cell")
             .rename({"Cell_right": "Cell"})
             .with_columns(pl.col("Cell").cast(pl.Int32),
                           pl.lit("Historical" if scen == "historical" else scen).alias("scen"))
             .collect())
        parts.append(d)
    cy = pl.concat(parts, how="vertical_relaxed").sort("gcm", "scen", "Cell", "Year")
    lead = ["gcm", "scen", "Cell", "Year"]
    cy = cy.select(lead + [c for c in cy.columns if c not in lead])
    cy.write_parquet(p("climate", "cell_year.parquet"), compression="zstd")
    log(f"cell_year: {cy.height} rows, {cy.width} columns")
    num = [c for c, t in cy.schema.items() if c not in lead and t.is_numeric()]
    base = (cy.filter((pl.col("scen") == "Historical") & pl.col("Year").is_between(*BASE))
            .group_by("gcm", "Cell").agg(pl.len().alias("n_years"),
                                         *[pl.col(c).cast(pl.Float64).mean().alias(c) for c in num]))
    assert (base["n_years"] == BASE[1] - BASE[0] + 1).all()
    base.sort("gcm", "Cell").write_parquet(p("shared", "climate", "clim8514.parquet"))
    new = ([f"{f}_tr20" for f in ("tcold_month", "twarm_month", "gdd5")] + [f"tstress_pft{k}" for k in range(7)]
           + [f"vpd_{f}_eff" for f in ("mean", "jja", "win10_sum")])
    assert not set(f"anom_{c}" for c in new) & set(cy.columns)
    ext = cy.select(lead + new).join(base.select("gcm", "Cell", *[pl.col(c).alias(f"_b_{c}") for c in new]),
                                     on=["gcm", "Cell"], how="left")
    ext = ext.select(lead + [pl.lit(False).alias("excluded"), pl.lit(None, pl.String).alias("exclusion_reason"),
                             pl.lit(True).alias("truth_usable")]
                     + [(pl.col(c).cast(pl.Float64) - pl.col(f"_b_{c}")).cast(pl.Float32).alias(f"anom_{c}")
                        for c in new])
    ext.write_parquet(p("shared", "climate", "cell_year_ext.parquet"), compression="zstd")
    log(f"cell_year_ext: {ext.height} rows; clim8514: {base.height} cells")


# ------------------------------------------------------------------------------------------------ gates
def stage_gates():
    g = {}
    m = cmap()
    g["cell_map_bijective"] = bool(m["Cell"].n_unique() == m.height == m["Cell_orig"].n_unique()
                                   and m["Cell"].max() < 32768 and m["Cell"].min() == 0)
    gm = pl.read_parquet(os.path.join(GREG, "members.parquet"))
    rows_ok = {}
    for seed in SEEDS:
        for scen in ("historical",) + SSPS:
            src = gm.filter(pl.col("member") == gname(scen, seed))["ind_dev_path"].item()
            n_src = (pl.scan_parquet(src).filter(pl.col("Cell").is_in(m["Cell_orig"].to_list()))
                     .select(pl.len()).collect().item())
            n_out = pl.scan_parquet(p("ind_dev", f"{dname(scen, seed)}.parquet")).select(pl.len()).collect().item()
            rows_ok[dname(scen, seed)] = bool(n_src == n_out)
    g["ind_rows_equal_source"] = rows_ok
    cy = pl.scan_parquet(p("climate", "cell_year.parquet"))
    k = cy.select(pl.len().alias("n"), pl.struct("gcm", "scen", "Cell", "Year").n_unique().alias("u")).collect()
    g["climate_key_unique"] = bool(k["n"][0] == k["u"][0])
    per = cy.group_by("scen").agg(pl.len().alias("n"), pl.col("Year").n_unique().alias("ny")).collect()
    g["climate_complete"] = {r["scen"]: bool(r["n"] == r["ny"] * m.height) for r in per.iter_rows(named=True)}
    chk = (cy.filter((pl.col("scen") == "Historical") & pl.col("Year").is_between(*BASE))
           .group_by("Cell").agg((pl.col("tmean_ann").cast(pl.Float64)
                                  - pl.col("tmean_ann").cast(pl.Float64).mean()).mean().alias("a"),
                                 pl.col("anom_tmean_ann").cast(pl.Float64).mean().alias("b")).collect())
    g["anom_tmean_base_mean_max"] = float(chk["b"].abs().max())
    g["anom_tmean_base_ok"] = bool(chk["b"].abs().max() < 1e-4)
    ex = pl.scan_parquet(p("shared", "climate", "cell_year_ext.parquet"))
    e = (ex.filter((pl.col("scen") == "Historical") & pl.col("Year").is_between(*BASE))
         .group_by("Cell").agg(pl.col("anom_gdd5_tr20").cast(pl.Float64).mean().alias("a")).collect())
    g["ext_anom_base_mean_max"] = float(e["a"].abs().max())
    g["pass"] = bool(g["cell_map_bijective"] and all(rows_ok.values()) and g["climate_key_unique"]
                     and all(g["climate_complete"].values()) and g["anom_tmean_base_ok"]
                     and g["ext_anom_base_mean_max"] < 1e-3)
    json.dump(g, open(p("_gates.json"), "w"), indent=1)
    log(json.dumps(g))


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    order = ["cells", "ind", "registry", "climate", "gates"]
    for s in (order if st == "all" else st.split(",")):
        log(f"=== {s}")
        globals()[f"stage_{s}"]()
    log("=== DONE")
