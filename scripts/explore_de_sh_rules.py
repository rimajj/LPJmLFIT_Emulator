#!/usr/bin/env python3
"""explore_de_sh_rules.py — LINE X, Germany data-driven emulator, shared item SH2: EXACT RULE LIBRARY.

The original model's own ANNUAL demography rules, pure numpy, importable by every track:

    import sys; sys.path.insert(0, "/p/projects/open/Jamir/wt-X/scripts")
    import explore_de_sh_rules as rl
    P = rl.load_params()                       # per-PFT + global parameters (cpp of the live par files)

Every function is vectorised over trees (numpy arrays; `typ` = the `ind` column Type = 0-based pftpar index).
Each one cites the C line it ports (LPJmL-FIT v5.6.004, /home/jamirp/lpjml56fit/src; production binary =
git fcd3a30 "Dec 17 2025" for Historical/ssp126/ssp370, b2e5ca9 "Feb 5 2026" for every ssp245 segment).

MORTALITY (tree/mortality_tree_ind.c). THE C's ORDER within one year (v3 correction of the stated order):
  tree/annual_tree.c: turnover -> allocation_tree (returns isdead on negative pools) -> mortality_tree_ind
  (hazard draw, then isneg_tree) -> survive() for trees still alive -> age += 1 (all inside the PFT loop of
  lpj/annual_natural.c); THEN, after that loop, lpj/annual_natural.c:170 firepft -> fire_tree_ind kills with
  (1-resist) * fire_frac only trees NOT already dead (short-circuit && in tree/fire_tree_ind.c:25). Fire comes
  LAST; because it only touches survivors the outcome equals "hazard, fire, survive" but the order is the above.
  DEATH CHANNELS THIS LIBRARY DOES NOT CARRY (no table column determines them): (a) allocation_tree's negative-pool
  kill, (b) isneg_tree (any negative pool, fpc <= 1e-20 or nind <= 1e-20) returned when the hazard draw spares the
  tree, (c) the sapling-leaf-carbon kill (:137), (d) the cut_year kill and the logging collateral (inactive in a
  natural run), (e) fire's patch fraction (fire_kill_prob takes it as an input; learning it is SH13's job — the
  fire rule is NOT gated against data here, deferred to SH13).
  mort_max_of(wooddens, typ)              :92   10^(wdmort_1 + wdmort_2/(wooddens/1e6))
  counter_step(c_prev, G, age_pre)        :73-83  c = 0 if age_pre == 1; c+1 if bm_delta < 0 else 0
  mort_npp_of(G, c, mmax, leafarea_ok)    :95-101 min(1, mmax(1+c)/(1+KMORT_2 exp(k_mort G))); 1 if leafarea<=1e-6
  mort_age_of(age_pre, typ)               :107  min(1, LNF(Q+1)/L (age/L)^Q), age_pre = printed Age - 1
  mort_water_of(W, c, typ, rh_on)         :112  min(1, factor W (1+c)/365); W = 0 when rh_on == 0
  mort_temp_of(tstress_days, typ)         :116  min(1, mort_temp_factor * days / 365)
  hazard(mn, ma, mw, mt, c)               :121-130 min(1, sum); 1 if c >= 5 (the leaf-carbon hard kill is NOT
                                          reproducible from the table; it is reported as hard_reason 3)
  death_draw(mort, rng)                   :152  erand48 < mort
  fire_kill_prob(typ, f)                  tree/fire_tree_ind.c:25 + soil/fire_prob.c: (1-resist) * max(f, 0.001)
                                          applied AFTER the whole PFT loop (hazard, survive, age++) to trees not
                                          already dead (lpj/annual_natural.c:170). Not gated against data (SH13).
  RECOVERY from a printed row (the hidden state):
  recover_counter(mort_npp, mmax, c_prev) c = max(0, ceil(r - 1 - 1e-4)), r = mort_npp/mmax (tolerant formula);
                                          PASS c_prev (previous year's recovered counter, -1 unknown) — without it
                                          the c = 4 / c = 5 band at r ~ 5 is read as 4 and the recursion fails on
                                          ~1.5e-6 of pairs instead of the resolved rate in _gates.json
  recover_G(mort_npp, mmax, c)            G = ln(((1+c)/r - 1)/KMORT_2)/k_mort  (+ censor code)
  recover_W(mort_water, c, typ)           W = mort_water * 365 / (factor (1+c))  (+ censor code)
  CENSOR codes: 0 ok · 1 G_low ((1+c)/r - 1 <= 0, G -> -inf) · 2 G_high (mort_npp <= 0, G -> +inf)
                3 NPP_SAT (mort_npp >= 1: capped or leafarea_real <= 1e-6, G and c not identifiable)
                4 W_SAT (mort_water >= 1: capped, W only bounded below) — G and W censoring are separate columns.
                5 G_SIGN (|G| below print precision and its recovered sign contradicted the counter; G set to
                  -1e-9 / 0 with the counter's sign — USABLE as a target, |G| ~ 0)
  The one ambiguous counter band (r ~ 5: c = 4 with G -> -inf, or c = 5 with G -> 0-) is read as c = 4 unless
  the previous year's counter is passed (recover_counter(..., c_prev=...)); see counter_band_ambiguous().
ALLOMETRY: fit_height_allometry / predict_height  — per-Type log-OLS  ln H ~ 1 + ln agb + ln Wooddens + ln SLA,
  coefficients fitted on each split's TRAINING members only (dev cells, folds 1-4): shared/rules/height_allometry.parquet
  OPTIONAL extended form (v3): fit_height_allometry(df, feats=ALLOM_FEATS_EXT) / predict_height_ext adds ln LAI and
  ln fpc_ind (both in the table) -> shared/rules/height_allometry_ext.parquet. Only for a track that carries LAI and
  fpc_ind as state; note fpc_ind = crownarea nind (1 - exp(-k LAI)) and crownarea is itself a function of height in
  the C (allometry_tree.c), so this form recovers height largely through the crown allometry.
ESTABLISHMENT (lpj/establishmentpft_ind.c + lpj/establish.c + lpj/survive.c):
  eligible(tcold20, twarm20, gdd, aprec)  establish.c:29-33 per tree PFT: tcold20 in [temp.low, temp.high],
                                          gdd >= gdd5min (gdd = the CURRENT year's degree days above gddbase,
                                          lpj/updategdd.c, reset each year), twarm20 > 10, aprec >= aprec_min.
                                          tcold20/twarm20 = 20-yr mean INCLUDING the current year (annual_climbuf
                                          runs before annual_stand, lpj/update_annual.c).
  survive(tcold20, twarm20)               survive.c: tcold20 >= temp.low and twarm20 - tcold20 >= min_temprange;
                                          kills any tree of that PFT still alive after the hazard (annual_tree.c:47)
  inherit_weight(n_elig)                  share of recruits from the inheritance channel = Ri/(Ri + n_elig),
                                          Ri = k_est_inherit/k_est_inherit_bg (= 4 here; both channels carry the
                                          same alpha_r, so f_sap cancels — asserted)
  p_inherit_given_type(pi_k, elig_k)      P(inheritance | recruit is PFT k) = Ri pi_k/(Ri pi_k + elig_k),
                                          pi_k = share of PFT k among seedbank entries (parent PFT = recruit PFT)
  seedbank_n(npatch)                      int(n_max * npatch * patcharea / 100)  (lpj/getsapling.c; 3937 at 250)
  seedbank_select(agb, n)                 agb >= the n-th largest agb of ALL trees of the stand (getmaxagb.c)
  seedbank_keep(entry_year, year)         year - entry_year < max_age (entries expire after 50 yr)
TRAITS (tree/new_tree.c):
  draw_new_trait(old, lo, hi, corridor, rng)    :38-61 s ~ N(0,1) clamped +-5; new = old (1 + corridor s);
                                                below lo -> lo + (old-lo) u; above hi -> old + (hi-old) u
  inherit_traits(parent_typ, parents, build, rng)  inheritance branch :120-180. build "dec2025" = the production
                                                quirk: Wooddens and D95max are bounded by the ESTABLISHING slot
                                                (pftpar[0], because establishmentpft_ind.c:121 calls
                                                addpft(patch, config->pftpar, ...)) while SLA/minwscal/emax/beta_2
                                                use the parent's PFT; "feb2026" (commit b2e5ca9) uses the parent's PFT
                                                for all. Recruit PFT = parent PFT in both builds.
  background_traits(typ, rng)             :183-195 uniform on the own PFT's intervals
  longevity_of(sla, typ, rng)             :197 numeric/corr_corridor.c: 10^(interc + slope log10 sla + e),
                                          e ~ N(0, sigma) truncated to |e| <= 2 sigma by rejection
  getbetaroot(d95max)                     :207 + soil/getbetaroot.c + numeric/bisect.c, replicated step by step
                                          (bottom = layerbound[BOTTOMLAYER-1] * 0.1 cm = 2000 cm here)
  build_of(bin_feb2026)                   -> "feb2026" | "dec2025"

STAGES (arg 1):
  params      cpp the live par files -> shared/rules/params.json, cross-checked against the generated
              S_pft_mortality_params.csv / S_pft_estab_params.csv (seconds; login node is fine)
  selftest    scalar-vs-vector and property checks of every function (seconds)
  allometry   fit the per-Type Height allometry for every split on its training members (SLURM)
  gates       all data gates on the gate members (SLURM) -> shared/rules/_gates.json, _report.json
  all         params, selftest, allometry, gates
Nothing Germany-specific is hard-coded: the PFT set, parameters, patch count (registry npatch), soil layers and
cell/year sets come from the par files and the tables. CO2 is never an input. Wind is never an input.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
OUT = os.environ.get("SH2_OUT", os.path.join(XDE, "shared", "rules"))
PARAMS_JSON = os.path.join(OUT, "params.json")
ALLOM = os.path.join(OUT, "height_allometry.parquet")
ALLOM_EXT = os.path.join(OUT, "height_allometry_ext.parquet")
REG = os.path.join(XDE, "shared", "registry")
CLIM = os.path.join(XDE, "climate", "cell_year.parquet")
EXT = os.path.join(XDE, "shared", "climate", "cell_year_ext.parquet")
DEV = os.path.join(XDE, "ind_dev")
PROBE_C = os.path.join(XDE, "struct", "probe_C_estab_eligibility.csv")
LPJROOT = os.environ.get("LPJROOT", "/home/jamirp/lpjml56fit")
CSV_MORT = os.path.join(REPO, "test", "testitems", "references", "S_pft_mortality_params.csv")
CSV_EST = os.path.join(REPO, "test", "testitems", "references", "S_pft_estab_params.csv")

# C #defines (not in any par file) — mortality_tree_ind.c:22-34, establish.c, climate.h, soil.h
KMORT_2 = 0.2
KMORTBG_LNF = -math.log(0.001)
KMORTBG_Q = 2.0
BM_INC_COUNTER_MAX = 5
NDAYYEAR = 365.0
LEAFAREA_MIN = 1e-6
FIRE_FLOOR = 0.001  # soil/fire_prob.c: never returns less than 0.001
TWARM_MIN_TREE = 10.0  # establish.c:33  !(type==TREE && temp_max20 <= 10)
COUNTER_TOL = 1e-4  # tolerant counter formula (round-1 verifier)
BISECT_XACC = 1e-4  # soil/getbetaroot.c EPSILON, passed as xacc
BISECT_MAXIT = 20
STALE_SLOT = 0  # establishmentpft_ind.c:121 addpft(patch, config->pftpar, year, TRUE): the establishing slot
BUILDS = {"Dec 17 2025": "dec2025", "Feb 5 2026": "feb2026"}
CENSOR = {"ok": 0, "G_low": 1, "G_high": 2, "npp_sat": 3, "W_sat": 4, "G_sign": 5}
G_EPS = 1e-9  # magnitude given to a below-print-precision G whose sign comes from the counter

# gate members. OWNER DECISION 2026-10-01: only the 1985-2044 data are usable (the 2071-2100 and 3071-3100
# segments ran with relative_humidity off, so their water-stress mortality is switched off). The spec's second
# member ACCESS-CM2_ssp370_s2_w2071 is replaced by the same trajectory's 2015-2044 window (held-out GCM, seed 2),
# and the held-out GCM's Historical window is added so 1985-2014 is gated too (AMENDMENT, see the report).
GATE_MEMBERS = ["MPI-ESM1-2-HR_ssp370_s1_w2015", "ACCESS-CM2_ssp370_s2_w2015", "ACCESS-CM2_Historical_s2_h1985"]
# the trait-quirk gate needs recruits of both builds: Dec-2025 (ssp370) and the ssp245 members (Feb-2026 from 2015)
TRAIT_MEMBERS = ["MPI-ESM1-2-HR_ssp370_s1_w2015", "ACCESS-CM2_ssp370_s2_w2015",
                 "MPI-ESM1-2-HR_ssp245_s1_w2015", "ACCESS-CM2_ssp245_s2_w2015"]
ALLOW_EXCLUDED = os.environ.get("SH2_ALLOW_EXCLUDED") == "1"  # never set it except to confirm the exclusion


class ExcludedMemberError(RuntimeError):
    """Raised when a tree table of an owner-excluded window (2071-2100 / 3071-3100) is requested."""
TREE_MAX_TYPE_COL = "Type"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ================================================================================================ params
def _dup_hook(dups: set):
    def hook(pairs):
        seen = {}
        for k, v in pairs:
            if k in seen:
                dups.add(k)
            seen[k] = v  # json-c tokener: json_object_object_add REPLACES -> last occurrence wins
        return seen

    return hook


def cpp_json(path: str) -> tuple[dict, set]:
    """Expand an LPJmL .js parameter fragment exactly as LPJmL does (cpp -P, openconfig.c:28,467)."""
    proc = subprocess.run(["cpp", "-P", f"-I{LPJROOT}", path], capture_output=True, text=True, check=True,
                          stdin=subprocess.DEVNULL)
    body = proc.stdout.strip().rstrip(",")
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    body = re.sub(r"(\d)\.(?=\s*[,\]}])", r"\1.0", body)  # C-style "200." -> JSON "200.0"
    dups: set = set()
    return json.loads("{" + body + "}", object_pairs_hook=_dup_hook(dups)), dups


def _iv(x):
    """Interval {'low','high'} or scalar -> (low, high)."""
    if isinstance(x, dict):
        return float(x["low"]), float(x["high"])
    return float(x), float(x)


def build_params() -> dict:
    pft, dups_pft = cpp_json(os.path.join(LPJROOT, "par", "pft_lpjmlfit.js"))
    prm, dups_prm = cpp_json(os.path.join(LPJROOT, "par", "lpjparam_fit.js"))
    soil, _ = cpp_json(os.path.join(LPJROOT, "par", "soil_20m.js"))
    g = prm["param"]
    trees = [p for p in pft["pftpar"] if p["type"] == "tree"]
    # the tree PFTs are the first pftpar entries (gettree / istree_estab iterate while type==TREE)
    for i, p in enumerate(pft["pftpar"][: len(trees)]):
        assert p["type"] == "tree", f"pftpar[{i}] is not a tree but precedes a tree"
    rows = []
    for i, p in enumerate(trees):
        lon = p["longevity"]
        r = {
            "pft_id": i, "name": p["name"],
            # mortality
            "wdmort_1": float(p["wdmort_1"]), "wdmort_2": float(p["wdmort_2"]),
            "mort_water_factor": float(p["mort_water_factor"]), "mort_water_res": float(p["mort_water_res"]),
            "mort_temp_factor": float(p["mort_temp_factor"]), "longevity_age": float(p["age"]),
            "temp_stressed_low": float(p["temp_stressed"]["low"]), "temp_stressed_high": float(p["temp_stressed"]["high"]),
            "resist": float(p["resist"]),
            # establishment / survival
            "temp_low": float(p["temp"]["low"]), "temp_high": float(p["temp"]["high"]),
            "gdd5min": float(p["gdd5min"]), "gddbase": float(p["gddbase"]), "aprec_min": float(p["aprec_min"]),
            "min_temprange": float(p["min_temprange"]), "alpha_r": float(p["alpha_r"]),
            "inherit_corridor": float(p["inherit_corridor"]),
            # traits
            "sla_low": _iv(p["sla"])[0], "sla_high": _iv(p["sla"])[1],
            "wooddens_low": _iv(p["wooddens"])[0], "wooddens_high": _iv(p["wooddens"])[1],
            "d95max_low": _iv(p["D95max"])[0], "d95max_high": _iv(p["D95max"])[1],
            "minwscal_low": _iv(p["minwscal"])[0], "minwscal_high": _iv(p["minwscal"])[1],
            "emax_low": _iv(p["emax"])[0], "emax_high": _iv(p["emax"])[1],
            "beta_2_low": _iv(p["beta_2"])[0], "beta_2_high": _iv(p["beta_2"])[1],
            "k_root_low": _iv(p["k_root"])[0], "k_root_high": _iv(p["k_root"])[1],
            "lon_interc": float(lon["interc"]) if isinstance(lon, dict) else float("nan"),
            "lon_slope": float(lon["slope"]) if isinstance(lon, dict) else float("nan"),
            "lon_sigma": float(lon["sigma"]) if isinstance(lon, dict) else float("nan"),
        }
        rows.append(r)
    sd = [float(x) for x in soil["soildepth"]]
    layerbound = np.cumsum(sd)
    nsl = len(sd)
    bottomlayer = nsl - 1  # soil.h: BOTTOMLAYER = NSOILLAYER-1
    glob = {
        "k_mort": float(g["k_mort"]), "patcharea": float(g["patcharea"]), "k_est_inherit": float(g["k_est_inherit"]),
        "k_est_inherit_bg": float(g["k_est_inherit_bg"]), "param_alpha_r": float(g["alpha_r"]),
        "max_age": int(g["max_age"]), "n_max": int(g["n_max"]), "height_min": float(g["height_min"]),
        "kmort_2": KMORT_2, "kmortbg_lnf": KMORTBG_LNF, "kmortbg_q": KMORTBG_Q,
        "bm_inc_counter_max": BM_INC_COUNTER_MAX, "ndayyear": NDAYYEAR, "fire_floor": FIRE_FLOOR,
        "twarm_min_tree": TWARM_MIN_TREE, "stale_slot": STALE_SLOT,
        "soildepth_mm": sd, "nsoillayer": nsl,
        "betaroot_bottom_cm": float(layerbound[bottomlayer - 1] * 0.1),
    }
    return {"pft": rows, "global": glob, "builds": BUILDS,
            "duplicate_keys_pft": sorted(dups_pft), "duplicate_keys_param": sorted(dups_prm),
            "source": {"lpjroot": LPJROOT, "files": ["par/pft_lpjmlfit.js", "par/lpjparam_fit.js", "par/soil_20m.js"],
                       "method": "cpp -P, trailing commas stripped, json last-wins (as json-c)"}}


@dataclass
class RuleParams:
    """Per-tree-PFT arrays (index = Type) + globals. Built from params.json."""

    raw: dict
    n_pft: int = 0
    a: dict = field(default_factory=dict)  # name -> np.ndarray[n_pft]
    g: dict = field(default_factory=dict)

    def __post_init__(self):
        rows = self.raw["pft"]
        self.n_pft = len(rows)
        for k in rows[0]:
            if k in ("name",):
                continue
            self.a[k] = np.array([r[k] for r in rows], dtype=np.float64)
        self.names = [r["name"] for r in rows]
        self.g = dict(self.raw["global"])

    def __getitem__(self, k):
        return self.a[k]


_P_CACHE: dict = {}


def load_params(path: str = PARAMS_JSON) -> RuleParams:
    if path not in _P_CACHE:
        if os.path.exists(path):
            raw = json.load(open(path))
        else:  # fall back to building from the live par files (needs cpp + LPJROOT)
            raw = build_params()
        _P_CACHE[path] = RuleParams(raw)
    return _P_CACHE[path]


def _P(P):
    return load_params() if P is None else P


def _t(typ):
    return np.asarray(typ, dtype=np.int64)


def _f(x):
    return np.asarray(x, dtype=np.float64)


# ================================================================================================ mortality
def mort_max_of(wooddens, typ, P=None):
    """mortality_tree_ind.c:92  mort_max = 10^(wdmort_1 + wdmort_2 / (wooddens/1e6))."""
    P = _P(P)
    t = _t(typ)
    return np.power(10.0, P["wdmort_1"][t] + P["wdmort_2"][t] / (_f(wooddens) / 1e6))


def counter_step(c_prev, G, age_pre):
    """mortality_tree_ind.c:73-83. age_pre = the tree's age BEFORE this year's increment (= printed Age - 1).
    bm_delta < 0 <=> G < 0 (G = bm_delta/leafarea_real, leafarea_real > 0)."""
    c = np.where(_f(age_pre) == 1, 0, np.asarray(c_prev, dtype=np.int64))
    return np.where(_f(G) < 0, c + 1, 0).astype(np.int64)


def mort_npp_of(G, c, mmax, leafarea_ok=None, P=None):
    """mortality_tree_ind.c:95-101."""
    P = _P(P)
    with np.errstate(over="ignore"):
        v = _f(mmax) * (1.0 + _f(c)) / (1.0 + P.g["kmort_2"] * np.exp(P.g["k_mort"] * _f(G)))
    v = np.minimum(1.0, v)
    if leafarea_ok is not None:
        v = np.where(np.asarray(leafarea_ok, dtype=bool), v, 1.0)
    return v


def mort_age_of(age_pre, typ, P=None):
    """mortality_tree_ind.c:44-48 + :107 mort_min(age, longevity), age = pre-increment age (printed Age - 1)."""
    P = _P(P)
    L = P["longevity_age"][_t(typ)]
    q = P.g["kmortbg_q"]
    return np.minimum(1.0, P.g["kmortbg_lnf"] * (q + 1) / L * np.power(_f(age_pre) / L, q))


def mort_water_of(W, c, typ, rh_on=1, P=None):
    """mortality_tree_ind.c:112. rh_on == 0 (segment config without relative_humidity) => W == 0 exactly
    (getvpd returns 0, waterstress_tree.c never accumulates) => mort_water == 0."""
    P = _P(P)
    W = _f(W) * (np.asarray(rh_on, dtype=np.float64) != 0)
    return np.minimum(1.0, P["mort_water_factor"][_t(typ)] * W / P.g["ndayyear"] * (1.0 + _f(c)))


def mort_temp_of(tstress_days, typ, P=None):
    """mortality_tree_ind.c:116. tstress_days = days in the C's accumulation window (days after the hemisphere's
    reset day: 14 north / 195 south, include/climate.h; SH1's column currently implements the NORTHERN reset only,
    which is correct for Germany but must be made hemisphere-dependent before a global run) with daily
    T < temp_stressed.low or > temp_stressed.high of the tree's PFT (SH1 column tstress_pft<Type>)."""
    P = _P(P)
    return np.minimum(1.0, P["mort_temp_factor"][_t(typ)] * _f(tstress_days) / P.g["ndayyear"])


def hazard(mn, ma, mw, mt, c, P=None):
    """mortality_tree_ind.c:121-130: mort = min(1, sum); counter >= 5 => 1. (The sapling-leaf-carbon kill
    at :133 needs leaf carbon, which the table does not carry.)"""
    P = _P(P)
    m = np.minimum(1.0, _f(mn) + _f(ma) + _f(mw) + _f(mt))
    return np.where(np.asarray(c) >= P.g["bm_inc_counter_max"], 1.0, m)


def death_draw(mort, rng: np.random.Generator):
    """mortality_tree_ind.c:152  erand48 < mort."""
    return rng.random(np.shape(mort)) < _f(mort)


def fire_kill_prob(typ, f, P=None):
    """tree/fire_tree_ind.c:25 with soil/fire_prob.c's floor: (1 - resist[Type]) * max(f, 0.001)."""
    P = _P(P)
    return (1.0 - P["resist"][_t(typ)]) * np.maximum(_f(f), P.g["fire_floor"])


def mortality_step(typ, wooddens, age_pre, c_prev, G, W, tstress_days, rh_on, P=None, rng=None, leafarea_ok=None):
    """One tree-year of mortality_tree_ind.c in the C's order, given this year's learned/replayed G and W.
    age_pre = age BEFORE this year's increment (the tree's printed Age next year minus 1). Returns a dict with
    c (updated counter), mort_npp, mort_age, mort_water, mort_temp, mort and, if rng is given, dead (Bernoulli).
    The caller then applies, in the C's order, the bioclimatic survive() test to the survivors and age += 1, and
    after all trees of the patch are done, fire to every tree not already dead (fire_step). The omitted death
    channels (negative pools / isneg_tree, the sapling-leaf-carbon kill) are listed in the module docstring."""
    P = _P(P)
    mm = mort_max_of(wooddens, typ, P)
    c = counter_step(c_prev, G, age_pre)
    mn = mort_npp_of(G, c, mm, leafarea_ok, P)
    ma = mort_age_of(age_pre, typ, P)
    mw = mort_water_of(W, c, typ, rh_on, P)
    mt = mort_temp_of(tstress_days, typ, P)
    out = {"c": c, "mort_max": mm, "mort_npp": mn, "mort_age": ma, "mort_water": mw, "mort_temp": mt,
           "mort": hazard(mn, ma, mw, mt, c, P)}
    if rng is not None:
        out["dead"] = death_draw(out["mort"], rng)
    return out


def fire_step(typ, f, dead, rng: np.random.Generator, P=None):
    """lpj/annual_natural.c:168-172 -> firepft -> fire_tree_ind: every tree NOT already dead dies with
    (1-resist) max(f, 0.001). f = the patch's fire fraction (learned by SH13; 0.001 = the floor). Returns new dead."""
    dead = np.asarray(dead, dtype=bool)
    u = rng.random(dead.shape)
    return dead | (u < fire_kill_prob(typ, f, P))


def half_ulp6(x):
    """Half a unit in the 6th significant digit of x (the C writer's %g), 0 for x == 0. The 2e-7 nudge puts a
    float32-stored decade value (0.01 stored as 0.0099999998) back into the decade it was printed in."""
    x = np.abs(_f(x))
    with np.errstate(divide="ignore"):
        e = np.floor(np.log10(np.where(x > 0, x * (1 + 2e-7), 1.0)))
    return np.where(x > 0, 0.5 * np.power(10.0, e - 5), 0.0)


def recover_counter(mort_npp, mmax, tol=COUNTER_TOL, c_prev=None):
    """Tolerant counter recovery c = max(0, ceil(r - 1 - 1e-4)), r = mort_npp/mmax. Returns (c Int64 in [0, 5], r).
    Rows with mort_npp >= 1 are censored (see recover_G) and get c clipped to 5.
    ONE AMBIGUOUS BAND: the bands r in ((1+c)/1.2, 1+c) are disjoint for c <= 4, but c = 5's band starts at exactly
    6/1.2 = 5 = the top of c = 4's band, so r ~ 5 is EITHER c = 4 with G -> -inf OR c = 5 with G -> 0-. The printed
    `mort` does NOT resolve it: a c = 4 tree with G -> -inf has almost no leaf area and is hard-killed by the
    sapling-leaf-carbon rule (mortality_tree_ind.c:133), so mort = 1 for both readings [MEASURED: in ACCESS ssp370
    s2 2071-2100 (dev, Cell % 100 == 0) 204 of 204 band rows with mort = 1 had c_prev = 3, i.e. were c = 4].
    The plain formula reads the band as c = 4. If the previous year's counter is known (c_prev, -1 = unknown), a
    band row with c_prev == 4 is set to 5 (the recursion c in {0, c_prev + 1})."""
    r = _f(mort_npp) / _f(mmax)
    with np.errstate(invalid="ignore"):
        c = np.maximum(0.0, np.ceil(r - 1.0 - tol))
    c = np.where(np.isfinite(c), c, 0.0)
    c = np.minimum(c, BM_INC_COUNTER_MAX)
    cmax = BM_INC_COUNTER_MAX
    lo_top = (1.0 + cmax) / (1.0 + KMORT_2)
    if c_prev is not None and lo_top <= cmax * (1 + tol):
        band = (r >= lo_top * (1 - tol)) & (r <= cmax * (1 + tol))
        c = np.where(band & (np.asarray(c_prev) == cmax - 1), cmax, c)
    return c.astype(np.int64), r


def counter_band_ambiguous(r, tol=COUNTER_TOL):
    """Rows in the c = 4 / c = 5 overlap band (see recover_counter)."""
    cmax = BM_INC_COUNTER_MAX
    lo_top = (1.0 + cmax) / (1.0 + KMORT_2)
    return (_f(r) >= lo_top * (1 - tol)) & (_f(r) <= cmax * (1 + tol))


def recover_G(mort_npp, mmax, c, P=None):
    """Invert mort_npp for growth efficiency G = bm_delta/leafarea_real. Returns (G float64, censor int8).
    Censored rows get G clipped to the finite band [-g_lim, +g_lim] with g_lim = ln(1/1e-12/KMORT_2)/k_mort so
    that sign(G) stays usable; exclude them from regression targets (critic gap 8)."""
    P = _P(P)
    mn = _f(mort_npp)
    r = mn / _f(mmax)
    x = ((1.0 + _f(c)) / r - 1.0) / P.g["kmort_2"]
    cen = np.zeros(mn.shape, dtype=np.int8)
    cen = np.where(mn >= 1.0, CENSOR["npp_sat"], cen)
    cen = np.where((cen == 0) & (mn <= 0.0), CENSOR["G_high"], cen)
    cen = np.where((cen == 0) & ~(x > 0.0), CENSOR["G_low"], cen)
    g_lim = math.log(1.0 / 1e-12 / P.g["kmort_2"]) / P.g["k_mort"]
    with np.errstate(divide="ignore", invalid="ignore"):
        G = np.log(np.where(x > 0, x, np.nan)) / P.g["k_mort"]
    G = np.where(cen == CENSOR["G_low"], -g_lim, G)
    G = np.where(cen == CENSOR["G_high"], g_lim, G)
    # npp_sat: the counter is unknown, so is G; its sign is not identifiable either -> NaN (caller decides)
    G = np.where(cen == CENSOR["npp_sat"], np.nan, G)
    G = np.clip(G, -g_lim, g_lim)
    # |G| below the print precision (~0.01) can come out with the wrong sign; the counter fixes the sign
    # (c >= 1 <=> bm_delta < 0 this year <=> G < 0). Such rows are usable targets (|G| ~ 0, sign right).
    c_ = np.asarray(c)
    flip_neg = (cen == 0) & (c_ >= 1) & (G >= 0)
    flip_pos = (cen == 0) & (c_ == 0) & (G < 0)
    G = np.where(flip_neg, -G_EPS, np.where(flip_pos, 0.0, G))
    cen = np.where(flip_neg | flip_pos, CENSOR["G_sign"], cen)
    return G, cen.astype(np.int8)


def recover_W(mort_water, c, typ, P=None):
    """Invert mort_water for the water-stress integral W (tree->water_stress). Returns (W, censor int8);
    W_sat rows (mort_water >= 1) carry the lower bound W = 365/(factor (1+c))."""
    P = _P(P)
    mw = _f(mort_water)
    W = mw * P.g["ndayyear"] / (P["mort_water_factor"][_t(typ)] * (1.0 + _f(c)))
    cen = np.where(mw >= 1.0, CENSOR["W_sat"], 0).astype(np.int8)
    return W, cen


def hard_reason(mort, c, mn, ma, mw, mt, P=None):
    """0 not hard (mort < 1) · 1 counter >= 5 · 2 summed hazard >= 1 · 3 neither (sapling-leaf-carbon kill or
    print rounding)."""
    P = _P(P)
    hard = _f(mort) >= 1.0
    s = _f(mn) + _f(ma) + _f(mw) + _f(mt)
    rsn = np.where(np.asarray(c) >= P.g["bm_inc_counter_max"], 1, np.where(s >= 1.0 - 5e-6, 2, 3))
    return np.where(hard, rsn, 0).astype(np.int8)


# ================================================================================================ allometry
ALLOM_FEATS = ["agb", "Wooddens", "SLA"]
ALLOM_FEATS_EXT = ["agb", "Wooddens", "SLA", "LAI", "fpc_ind"]  # optional form (v3, verifier minor 2)
_BNAME = {"agb": "b_agb", "Wooddens": "b_wd", "SLA": "b_sla", "LAI": "b_lai", "fpc_ind": "b_fpc"}


def _allom_design(agb, wd, sla, *more):
    return np.column_stack([np.ones(len(agb)), np.log(_f(agb)), np.log(_f(wd)), np.log(_f(sla))]
                           + [np.log(_f(m)) for m in more])


def fit_height_allometry(df: pl.DataFrame, feats=None) -> pl.DataFrame:
    """Per-Type OLS ln Height ~ 1 + sum ln feats on rows with Height and every feature > 0.
    feats = ALLOM_FEATS (default: agb, Wooddens, SLA) or ALLOM_FEATS_EXT (adds LAI, fpc_ind).
    Returns one row per Type: b0, b_<feat>..., n, r2_train, rmse_log."""
    feats = list(feats or ALLOM_FEATS)
    out = []
    for t in sorted(df["Type"].unique().to_list()):
        flt = (pl.col("Type") == t) & (pl.col("Height") > 0)
        for f_ in feats:
            flt = flt & (pl.col(f_) > 0)
        d = df.filter(flt)
        if d.height < 10:
            continue
        X = _allom_design(*[d[f_].to_numpy() for f_ in feats])
        y = np.log(d["Height"].to_numpy().astype(np.float64))
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        res = y - X @ b
        r2 = 1.0 - float(res @ res) / float(((y - y.mean()) ** 2).sum())
        row = {"Type": int(t), "b0": b[0]}
        for i, f_ in enumerate(feats):
            row[_BNAME[f_]] = b[1 + i]
        row.update({"n": d.height, "r2_train": r2, "rmse_log": float(np.sqrt(np.mean(res ** 2)))})
        out.append(row)
    return pl.DataFrame(out)


def load_allometry(split: str = "DEV-A", cellset: str = "dev_f1234", ext: bool = False) -> pl.DataFrame:
    return pl.read_parquet(ALLOM_EXT if ext else ALLOM).filter((pl.col("split") == split) & (pl.col("cellset") == cellset))


def predict_height(agb, wooddens, sla, typ, coef: pl.DataFrame, lai=None, fpc_ind=None):
    """Height from the fitted per-Type allometry (coef = load_allometry(split[, ext=True])). Types without a fit ->
    NaN. With an extended coefficient table (b_lai, b_fpc present) lai and fpc_ind are required."""
    t = _t(typ)
    ext = "b_lai" in coef.columns
    names = ["b0", "b_agb", "b_wd", "b_sla"] + (["b_lai", "b_fpc"] if ext else [])
    nt = int(max(int(coef["Type"].max()), int(t.max()) if t.size else 0)) + 1
    B = np.full((nt, len(names)), np.nan)
    for r in coef.iter_rows(named=True):
        B[r["Type"]] = [r[n_] for n_ in names]
    b = B[t]
    z = b[:, 0] + b[:, 1] * np.log(_f(agb)) + b[:, 2] * np.log(_f(wooddens)) + b[:, 3] * np.log(_f(sla))
    if ext:
        if lai is None or fpc_ind is None:
            raise ValueError("extended allometry needs lai and fpc_ind")
        z = z + b[:, 4] * np.log(_f(lai)) + b[:, 5] * np.log(_f(fpc_ind))
    return np.exp(z)


def predict_height_ext(agb, wooddens, sla, lai, fpc_ind, typ, coef_ext: pl.DataFrame):
    """Optional extended allometry (coef_ext = load_allometry(split, ext=True))."""
    return predict_height(agb, wooddens, sla, typ, coef_ext, lai=lai, fpc_ind=fpc_ind)


# ================================================================================================ establishment
def eligible(tcold20, twarm20, gdd, aprec, P=None):
    """establish.c:29-33 for every tree PFT -> bool array [n, n_pft]. `gdd` = the year's degree days above the
    PFT's gddbase (all tree PFTs use 5 C here; asserted) — the CURRENT year, not a 20-yr mean."""
    P = _P(P)
    gb = np.unique(P["gddbase"])
    if gb.size != 1:
        raise NotImplementedError("tree PFTs with different gddbase need one gdd array per base")
    tc = _f(tcold20)[:, None]
    tw = _f(twarm20)[:, None]
    gd = _f(gdd)[:, None]
    ap = _f(aprec)[:, None]
    return ((tc >= P["temp_low"][None, :]) & (tc <= P["temp_high"][None, :]) & (gd >= P["gdd5min"][None, :])
            & (tw > P.g["twarm_min_tree"]) & (ap >= P["aprec_min"][None, :]))


def survive(tcold20, twarm20, P=None):
    """survive.c -> bool [n, n_pft]."""
    P = _P(P)
    tc = _f(tcold20)[:, None]
    tw = _f(twarm20)[:, None]
    return (tc >= P["temp_low"][None, :]) & ((tw - tc) >= P["min_temprange"][None, :])


def _inherit_ratio(P):
    if not np.all(P["alpha_r"] == P.g["param_alpha_r"]):
        raise NotImplementedError("tree alpha_r != param.alpha_r: f_sap does not cancel, no closed-form weight")
    return P.g["k_est_inherit"] / P.g["k_est_inherit_bg"]


def inherit_weight(n_elig, P=None):
    """Expected share of recruits from the inheritance channel (establishmentpft_ind.c:102,124)."""
    P = _P(P)
    R = _inherit_ratio(P)
    return R / (R + _f(n_elig))


def p_inherit_given_type(pi_k, elig_k, P=None):
    """P(inheritance channel | recruit is PFT k): inherited recruits take the parent's PFT, the background
    channel draws only eligible PFTs. pi_k = share of PFT k among seedbank entries. NaN-safe: 0 if both are 0."""
    P = _P(P)
    R = _inherit_ratio(P)
    num = R * _f(pi_k)
    den = num + _f(np.asarray(elig_k, dtype=np.float64))
    with np.errstate(invalid="ignore", divide="ignore"):
        p = np.where(den > 0, num / den, 0.0)
    return p


def seedbank_n(npatch, P=None):
    """getsapling.c: getmaxagb(stand, n_max*npatch*patcharea/100.0) -> int argument (truncation)."""
    P = _P(P)
    return int(P.g["n_max"] * npatch * P.g["patcharea"] / 100.0)


def seedbank_select(agb, n):
    """getmaxagb.c + getsapling.c:58: select every tree with agb >= the n-th largest agb of ALL the stand's trees
    (ties at the threshold are all taken; if fewer than n trees, all are taken)."""
    a = _f(agb)
    if a.size == 0:
        return np.zeros(0, dtype=bool)
    k = min(a.size, n) - 1
    thr = np.partition(-a, k)[k] * -1.0
    return a >= thr


def seedbank_keep(entry_year, year, P=None):
    """getsapling.c:20-30: an entry is deleted once year - entry_year >= max_age."""
    P = _P(P)
    return (np.asarray(year) - np.asarray(entry_year)) < P.g["max_age"]


# ================================================================================================ traits
def build_of(bin_feb2026) -> np.ndarray:
    return np.where(np.asarray(bin_feb2026) == 1, "feb2026", "dec2025")


def draw_new_trait(old, lo, hi, corridor, rng: np.random.Generator):
    """new_tree.c:38-61, vectorised."""
    old = _f(old)
    lo = np.broadcast_to(_f(lo), old.shape)
    hi = np.broadcast_to(_f(hi), old.shape)
    s = np.clip(rng.standard_normal(old.shape), -5.0, 5.0)
    new = old * (1.0 + _f(corridor) * s)
    u = rng.random(old.shape)
    new = np.where(new < lo, lo + (old - lo) * u, np.where(new > hi, old + (hi - old) * u, new))
    return np.where(lo == hi, old, new)


INHERIT_TRAITS = [  # (trait key, param prefix, bound owner in the Dec-2025 build)
    ("emax", "emax", "parent"), ("minwscal", "minwscal", "parent"), ("k_root", "k_root", "parent"),
    ("SLA", "sla", "parent"), ("Wooddens", "wooddens", "slot"), ("D95max", "d95max", "slot"),
    ("beta_2", "beta_2", "parent"),
]


def inherit_traits(parent_typ, parents: dict, build, rng: np.random.Generator, P=None) -> dict:
    """new_tree.c inheritance branch. parents: dict trait -> array (any subset of INHERIT_TRAITS keys).
    build: 'dec2025' | 'feb2026' (scalar or per-row array). Returns dict of the mutated traits; the recruit's
    PFT is parent_typ in both builds. Draw order follows the C (emax, minwscal, k_root, SLA, Wooddens, D95max,
    beta_2) but the numpy stream is not the C's erand48 stream."""
    P = _P(P)
    t = _t(parent_typ)
    b = np.broadcast_to(np.asarray(build), t.shape)
    slot = int(P.g["stale_slot"])
    out = {}
    for key, pre, owner in INHERIT_TRAITS:
        if key not in parents:
            continue
        lo = P[f"{pre}_low"][t]
        hi = P[f"{pre}_high"][t]
        if owner == "slot":
            lo = np.where(b == "dec2025", P[f"{pre}_low"][slot], lo)
            hi = np.where(b == "dec2025", P[f"{pre}_high"][slot], hi)
        corr = P["inherit_corridor"][t]
        out[key] = draw_new_trait(parents[key], lo, hi, corr, rng)
    return out


def background_traits(typ, rng: np.random.Generator, P=None) -> dict:
    """new_tree.c:183-195: uniform on the own PFT's intervals (getrndinterval)."""
    P = _P(P)
    t = _t(typ)
    out = {}
    for key, pre, _ in INHERIT_TRAITS:
        lo, hi = P[f"{pre}_low"][t], P[f"{pre}_high"][t]
        out[key] = lo + (hi - lo) * rng.random(t.shape)
    return out


def longevity_of(sla, typ, rng: np.random.Generator, P=None):
    """new_tree.c:197 corr_corridor(sla, interc, slope, sigma): 10^(interc + log10(sla) slope + e),
    e = sigma * N(0,1) redrawn while |e| > 2 sigma."""
    P = _P(P)
    t = _t(typ)
    sig = P["lon_sigma"][t]
    e = rng.standard_normal(t.shape) * sig
    bad = np.abs(e) > 2 * sig
    while bad.any():
        e[bad] = rng.standard_normal(int(bad.sum())) * sig[bad]
        bad = np.abs(e) > 2 * sig
    return np.power(10.0, P["lon_interc"][t] + np.log10(_f(sla)) * P["lon_slope"][t] + e)


def longevity_z(longevity, sla, typ, P=None):
    """Standardised corridor residual (log10 Longevity - interc - slope log10 SLA)/sigma; |z| <= 2 by construction."""
    P = _P(P)
    t = _t(typ)
    return (np.log10(_f(longevity)) - P["lon_interc"][t] - P["lon_slope"][t] * np.log10(_f(sla))) / P["lon_sigma"][t]


def getbetaroot(d95max, P=None):
    """soil/getbetaroot.c via numeric/bisect.c (xlow 0, xhigh 0.9999, xacc 1e-4, yacc 0, maxit 20), replicated
    step by step: returns xmid at the first iteration where xhigh - xlow < xacc, else the best |f| midpoint."""
    P = _P(P)
    D = _f(d95max)
    B = P.g["betaroot_bottom_cm"]

    def fcn(beta):
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            return (1.0 - np.power(beta, D)) / (1.0 - np.power(beta, B)) - 0.95

    xlow = np.zeros_like(D)
    xhigh = np.full_like(D, 0.9999)
    ylow = fcn(xlow)
    ymin = np.full_like(D, 1e9)
    xmin = np.full_like(D, np.nan)
    done = np.zeros(D.shape, dtype=bool)
    res = np.full_like(D, np.nan)
    for _ in range(BISECT_MAXIT):
        xmid = (xlow + xhigh) * 0.5
        stop = (~done) & ((xhigh - xlow) < BISECT_XACC)
        res = np.where(stop, xmid, res)
        done |= stop
        if done.all():
            break
        ymid = fcn(xmid)
        better = (~done) & (np.abs(ymid) < ymin)
        ymin = np.where(better, np.abs(ymid), ymin)
        xmin = np.where(better, xmid, xmin)
        # yacc == 0: |ymid| < 0 never true
        left = ylow * ymid <= 0
        upd = ~done
        xhigh = np.where(upd & left, xmid, xhigh)
        xlow = np.where(upd & ~left, xmid, xlow)
        ylow = np.where(upd & ~left, ymid, ylow)
    return np.where(done, res, xmin)


# ================================================================================================ stages
def stage_params():
    os.makedirs(OUT, exist_ok=True)
    raw = build_params()
    P = RuleParams(raw)
    checks = {}
    # cross-check against the two generated reference tables (both made by cpp of the same par file)
    m = pl.read_csv(CSV_MORT, comment_prefix="#").sort("pft_id")
    e = pl.read_csv(CSV_EST, comment_prefix="#").sort("pft_id")
    pairs = [(m, "wdmort_1", "wdmort_1"), (m, "wdmort_2", "wdmort_2"), (m, "mort_water_factor", "mort_water_factor"),
             (m, "mort_water_res", "mort_water_res"), (m, "mort_temp_factor", "mort_temp_factor"),
             (m, "longevity", "longevity_age"), (m, "temp_low", "temp_stressed_low"),
             (m, "temp_high", "temp_stressed_high"), (m, "wooddens_low", "wooddens_low"),
             (m, "wooddens_high", "wooddens_high"), (m, "sla_low", "sla_low"), (m, "sla_high", "sla_high"),
             (e, "d95max_low", "d95max_low"), (e, "d95max_high", "d95max_high"), (e, "minwscal_low", "minwscal_low"),
             (e, "minwscal_high", "minwscal_high"), (e, "inherit_corridor", "inherit_corridor"),
             (e, "alpha_r", "alpha_r"), (e, "temp_low", "temp_low"), (e, "temp_high", "temp_high"),
             (e, "gdd5min", "gdd5min"), (e, "aprec_min", "aprec_min")]
    bad = []
    for df, ccol, pcol in pairs:
        a = df[ccol].to_numpy().astype(np.float64)
        b = P[pcol][: len(a)]
        if not (len(a) == P.n_pft and np.array_equal(a, b)):
            bad.append({"csv_col": ccol, "param": pcol, "csv": a.tolist(), "cpp": b.tolist()})
    gl = {"k_mort": (m, "k_mort"), "patcharea": (e, "patcharea"), "k_est_inherit": (e, "k_est_inherit"),
          "k_est_inherit_bg": (e, "k_est_inherit_bg"), "param_alpha_r": (e, "param_alpha_r"),
          "max_age": (e, "max_age"), "n_max": (e, "n_max")}
    for k, (df, col) in gl.items():
        if not np.all(df[col].to_numpy().astype(np.float64) == float(P.g[k])):
            bad.append({"global": k, "csv": df[col].to_list(), "cpp": P.g[k]})
    checks["csv_crosscheck_mismatches"] = bad
    checks["n_pairs_checked"] = len(pairs) + len(gl)
    checks["duplicate_keys_pft"] = raw["duplicate_keys_pft"]
    checks["betaroot_bottom_cm"] = P.g["betaroot_bottom_cm"]
    checks["inherit_ratio"] = _inherit_ratio(P)
    raw["checks"] = checks
    json.dump(raw, open(PARAMS_JSON, "w"), indent=1)
    log("params ->", PARAMS_JSON, "n_pft", P.n_pft, "mismatches", len(bad), "dups", raw["duplicate_keys_pft"])
    if bad:
        log("MISMATCH", json.dumps(bad, indent=1))
    return {"pass": not bad, "n_pft": P.n_pft, **checks}


def stage_selftest():
    """Property and scalar-reference checks (no data)."""
    P = load_params()
    rng = np.random.default_rng(12345)
    res = {}
    # 1. counter/G round trip over the whole admissible domain
    t = rng.integers(1, 4, 200000)
    wd = rng.uniform(150000, 600000, t.size)
    mm = mort_max_of(wd, t, P)
    c0 = rng.integers(0, 5, t.size)
    G = np.where(c0 > 0, -rng.exponential(50, t.size), rng.exponential(50, t.size))
    G = np.where(rng.random(t.size) < 0.5, G, np.sign(G) * rng.uniform(0, 300, t.size))
    c = counter_step(c0, G, np.full(t.size, 10))
    mn = mort_npp_of(G, c, mm, P=P)
    cr, r = recover_counter(mn, mm)
    Gr, cen = recover_G(mn, mm, cr, P)
    ok = (cen == 0)
    res["counter_roundtrip_exact"] = float(np.mean(cr[ok] == c[ok]))
    res["G_roundtrip_max_abs"] = float(np.max(np.abs(Gr[ok] - G[ok])))
    res["n_censored"] = int((~ok).sum())
    # scalar reference for the same rows (plain python transcription of the C)
    i = 17
    cs = 0 if 10 == 1 else int(c0[i])
    cs = cs + 1 if G[i] < 0 else 0
    mms = 10 ** (P["wdmort_1"][t[i]] + P["wdmort_2"][t[i]] / (wd[i] / 1e6))
    mns = min(1.0, mms / (1 + 0.2 * math.exp(P.g["k_mort"] * G[i])) * (1 + cs))
    res["scalar_ref_mort_npp_diff"] = abs(mns - mn[i])
    # 2. bisect replica vs a scalar python transcription of numeric/bisect.c
    D = rng.uniform(51, 1800, 2000)

    def bisect_scalar(d):
        B = P.g["betaroot_bottom_cm"]
        f = lambda b: (1 - b ** d) / (1 - b ** B) - 0.95  # noqa: E731
        xl, xh = 0.0, 0.9999
        yl = f(xl)
        ymin, xmin = 1e9, None
        for _ in range(20):
            xm = (xl + xh) * 0.5
            if xh - xl < 1e-4:
                return xm
            ym = f(xm)
            if abs(ym) < ymin:
                ymin, xmin = abs(ym), xm
            if yl * ym <= 0:
                xh = xm
            else:
                xl, yl = xm, ym
        return xmin

    br = getbetaroot(D, P)
    res["betaroot_vs_scalar_max_abs"] = float(max(abs(br[k] - bisect_scalar(D[k])) for k in range(D.size)))
    # 3. draw_new_trait: properties
    old = rng.uniform(0.0242, 0.0547, 500000)
    new = draw_new_trait(old, 0.0242, 0.0547, 0.1, rng)
    res["draw_new_trait_in_bounds_from_inside"] = float(np.mean((new >= 0.0242) & (new <= 0.0547)))
    res["draw_new_trait_rel_sd"] = float(np.std(new / old - 1))
    # parent outside above: the redraw stays between hi and old (cannot jump inside unless the step lands inside)
    old2 = np.full(200000, 0.06)
    new2 = draw_new_trait(old2, 0.0242, 0.0547, 0.1, rng)
    res["draw_new_trait_from_outside_share_still_outside"] = float(np.mean(new2 > 0.0547))
    # 4. longevity corridor bounds
    sla = rng.uniform(0.0242, 0.0547, 200000)
    tt = np.full(sla.size, 3)
    z = longevity_z(longevity_of(sla, tt, rng, P), sla, tt, P)
    res["longevity_z_absmax"] = float(np.max(np.abs(z)))
    res["longevity_z_sd"] = float(np.std(z))
    res["longevity_z_sd_expected"] = 0.8796  # sd of N(0,1) truncated at +-2
    # 5. inherit weight closed form
    res["inherit_weight_n_elig_5"] = float(inherit_weight(5, P))
    res["seedbank_n_250"] = seedbank_n(250, P)
    res["seedbank_n_25"] = seedbank_n(25, P)
    passed = (res["counter_roundtrip_exact"] == 1.0 and res["G_roundtrip_max_abs"] < 1e-6
              and res["betaroot_vs_scalar_max_abs"] == 0.0 and res["draw_new_trait_in_bounds_from_inside"] == 1.0
              and res["longevity_z_absmax"] <= 2.0 and res["scalar_ref_mort_npp_diff"] < 1e-15)
    res["pass"] = bool(passed)
    log("selftest", json.dumps(res))
    return res


# ------------------------------------------------------------------------------------------------ data helpers
def _registry():
    return (pl.read_parquet(os.path.join(REG, "members.parquet")),
            pl.read_parquet(os.path.join(REG, "segments.parquet")),
            pl.read_parquet(os.path.join(REG, "folds.parquet")),
            pl.read_parquet(os.path.join(REG, "splits.parquet")))


TREE_COLS = ["Year", "Cell", "Patch", "Type", "ID", "isdead", "Height", "Age", "agb", "SLA", "Wooddens",
             "Longevity", "D95max", "beta_root", "minwscal", "mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]


SMOKE = os.environ.get("SH2_SMOKE") == "1"  # restrict every data read to Cell % 100 == 0 (code-path test only)


_EXCL_CACHE: dict = {}


def excluded_members() -> dict:
    """member -> exclusion_reason for every member the SH0 v2 registry marks excluded (owner decision 2026-10-01)."""
    if not _EXCL_CACHE:
        m = pl.read_parquet(os.path.join(REG, "members.parquet"))
        assert "excluded" in m.columns, "registry is pre-v2 (no 'excluded' column): rebuild SH0 first"
        for r in m.filter(pl.col("excluded")).select("member", "exclusion_reason").iter_rows():
            _EXCL_CACHE[r[0]] = r[1]
        _EXCL_CACHE.setdefault("__loaded__", True)
    return {k: v for k, v in _EXCL_CACHE.items() if k != "__loaded__"}


def assert_usable(member: str):
    """Refuse an owner-excluded member (raises ExcludedMemberError). Every data read in this module goes through it."""
    ex = excluded_members()
    if member in ex and not ALLOW_EXCLUDED:
        raise ExcludedMemberError(f"{member} is excluded ({ex[member]}); only 1985-2044 data are usable")


def _scan_dev(member: str) -> pl.LazyFrame:
    assert_usable(member)
    lf = pl.scan_parquet(os.path.join(DEV, f"{member}.parquet")).filter(pl.col("Type") <= 6)
    if SMOKE:
        lf = lf.filter((pl.col("Cell") % 100) == 0)
    return lf


def _read_trees(member: str, cols=None) -> pl.DataFrame:
    cols = TREE_COLS if cols is None else cols
    return _scan_dev(member).select(cols).collect()


def _member_meta(member: str):
    mem, seg, _, _ = _registry()
    r = mem.filter(pl.col("member") == member)
    assert r.height == 1, member
    return r.row(0, named=True)


def _add_hidden(df: pl.DataFrame, P) -> pl.DataFrame:
    """mort_max, r, c, G, cenG, W, cenW for every row (float64)."""
    t = df["Type"].to_numpy()
    mm = mort_max_of(df["Wooddens"].to_numpy(), t, P)
    c, r = recover_counter(df["mort_npp"].to_numpy(), mm)
    G, cg = recover_G(df["mort_npp"].to_numpy(), mm, c, P)
    W, cw = recover_W(df["mort_water"].to_numpy(), c, t, P)
    return df.with_columns(pl.Series("mmax", mm), pl.Series("r", r), pl.Series("c", c), pl.Series("G", G),
                           pl.Series("cenG", cg), pl.Series("W", W), pl.Series("cenW", cw))


# ------------------------------------------------------------------------------------------------ allometry stage
def stage_allometry():
    os.makedirs(OUT, exist_ok=True)
    mem, seg, folds, splits = _registry()
    dev_f1234 = folds.filter(pl.col("is_dev") & (pl.col("fold") <= 4))["Cell"].to_list()
    rows = []
    rows_ext = []
    cache: dict = {}
    for split in sorted(splits["split"].unique().to_list()):
        # training members = registry v2 role 'train' (already clean-only); no window list is hard-coded, and
        # the excluded set is subtracted again as a belt-and-braces check
        trm = sorted(splits.filter((pl.col("split") == split) & (pl.col("role") == "train")
                                   & pl.col("excluded_by").is_null())["src_member"].unique().to_list())
        ex = excluded_members()
        assert not (set(trm) & set(ex)), ("excluded member in a training role", set(trm) & set(ex))
        parts = []
        for m in trm:
            if m not in cache:
                d = (_scan_dev(m)
                     .filter(pl.col("Cell").cast(pl.Int32).is_in(dev_f1234))
                     .select("Year", "Cell", "Patch", "ID", "Type", "Height", "agb", "Wooddens", "SLA", "LAI", "fpc_ind")
                     .filter((pl.struct("Year", "Cell", "Patch", "ID").hash(seed=7) % 10) == 0)
                     .collect())
                cache[m] = d
            parts.append(cache[m])
        df = pl.concat(parts)
        fit = fit_height_allometry(df).with_columns(pl.lit(split).alias("split"), pl.lit("dev_f1234").alias("cellset"),
                                                    pl.lit(" | ".join(trm)).alias("train_members"))
        log("allometry", split, fit.select("Type", "n", "r2_train", "rmse_log").to_dicts())
        rows.append(fit)
        fx = fit_height_allometry(df, ALLOM_FEATS_EXT).with_columns(
            pl.lit(split).alias("split"), pl.lit("dev_f1234").alias("cellset"), pl.lit(" | ".join(trm)).alias("train_members"))
        log("allometry_ext", split, fx.select("Type", "n", "r2_train", "rmse_log").to_dicts())
        rows_ext.append(fx)
    out = pl.concat(rows)
    out.write_parquet(ALLOM)
    pl.concat(rows_ext).write_parquet(ALLOM_EXT)
    log("->", ALLOM, out.height, ALLOM_EXT)
    return out


# ------------------------------------------------------------------------------------------------ gates
def _gate_mortality(member: str, P, rep: dict) -> dict:
    meta = _member_meta(member)
    _, seg, _, _ = _registry()
    df = _add_hidden(_read_trees(member), P)
    n = df.height
    t = df["Type"].to_numpy()
    mn, ma, mw, mt, mo = (df[c].to_numpy().astype(np.float64) for c in ["mort_npp", "mort_age", "mort_water", "mort_temp", "mort"])
    c = df["c"].to_numpy()
    out = {"member": member, "n_tree_rows": n, "build": meta["build"], "rh_on": int(meta["rh_on"])}
    # (1) printed mort == min(1, sum) on non-hard rows
    nh = mo < 1.0
    s = np.minimum(1.0, mn + ma + mw + mt)
    rel = np.abs(mo[nh] - s[nh]) / np.maximum(np.abs(mo[nh]), 1e-300)
    rel = np.where((mo[nh] == 0) & (s[nh] == 0), 0.0, rel)
    out["mortsum_n_nonhard"] = int(nh.sum())
    out["mortsum_max_rel_err"] = float(rel.max())
    out["mortsum_n_rel_gt_1e-5"] = int((rel > 1e-5).sum())
    # print-aware exactness: |mort - sum| <= half-ulp(mort) + sum of half-ulps of the four parts (%g = 6 digits)
    # + float32 storage of the printed decimals (6e-8 relative)
    tol_p = (half_ulp6(mo[nh]) + half_ulp6(mn[nh]) + half_ulp6(ma[nh]) + half_ulp6(mw[nh]) + half_ulp6(mt[nh])
             + 1.2e-7 * (np.abs(mo[nh]) + np.abs(s[nh])))
    out["mortsum_n_print_violations"] = int((np.abs(mo[nh] - s[nh]) > tol_p).sum())
    # hard rows
    hr = hard_reason(mo, c, mn, ma, mw, mt, P)
    out["hard_n"] = int((hr > 0).sum())
    out["hard_reason_counts"] = {k: int((hr == v).sum()) for k, v in {"counter5": 1, "sum_ge_1": 2, "other": 3}.items()}
    isd = df["isdead"].to_numpy()
    out["hard_isdead_share"] = float(isd[hr > 0].mean()) if (hr > 0).any() else None
    # (2) mort_age from Age - 1
    pred_age = mort_age_of(df["Age"].to_numpy().astype(np.float64) - 1.0, t, P)
    ra = np.abs(ma - pred_age) / np.maximum(np.abs(pred_age), 1e-300)
    ra = np.where((ma == 0) & (pred_age == 0), 0.0, ra)
    out["mortage_max_rel_err"] = float(ra.max())
    out["mortage_n_rel_gt_1e-5"] = int((ra > 1e-5).sum())
    # (3) c = 5 => isdead
    c5 = c >= 5
    out["c5_n"] = int(c5.sum())
    out["c5_isdead_share"] = float(isd[c5].mean()) if c5.any() else None
    # (4) forbidden bands (print tolerance 1e-4 relative, the same as the counter formula's)
    r = df["r"].to_numpy()
    cen = df["cenG"].to_numpy()
    okc = cen != CENSOR["npp_sat"]
    up0 = 1.0 / (1.0 + KMORT_2)  # c = 0 <=> G >= 0 <=> r <= 1/1.2
    lo_c = (1.0 + c) / (1.0 + KMORT_2)  # c >= 1 <=> G < 0 <=> r in ((1+c)/1.2, 1+c)
    fb0 = okc & (c == 0) & (r > up0 * (1 + COUNTER_TOL))
    fb1 = okc & (c >= 1) & (r < lo_c * (1 - COUNTER_TOL))
    out["forbidden_band_n"] = int(fb0.sum() + fb1.sum())
    out["forbidden_band_n_c0"] = int(fb0.sum())
    out["forbidden_band_n_cpos"] = int(fb1.sum())
    # (5) censoring + round trips
    out["censor_G_counts"] = {k: int((cen == v).sum()) for k, v in CENSOR.items() if k != "W_sat"}
    out["censor_W_count"] = int((df["cenW"].to_numpy() == CENSOR["W_sat"]).sum())
    G = df["G"].to_numpy()
    ok = (cen == 0) | (cen == CENSOR["G_sign"])
    out["G_finite_on_uncensored_share"] = float(np.isfinite(G[ok]).mean())
    mn_rt = mort_npp_of(G[ok], c[ok], df["mmax"].to_numpy()[ok], P=P)
    rt = np.abs(mn_rt - mn[ok]) / mn[ok]
    ok0 = cen[ok] == 0
    out["G_roundtrip_max_rel_err"] = float(rt[ok0].max())
    out["G_sign_rows_roundtrip_max_rel_err"] = float(rt[~ok0].max()) if (~ok0).any() else 0.0
    W = df["W"].to_numpy()
    cw = df["cenW"].to_numpy()
    okw = cw == 0
    mw_rt = mort_water_of(W[okw], c[okw], t[okw], 1, P)
    with np.errstate(invalid="ignore", divide="ignore"):
        relw = np.where(mw[okw] > 0, np.abs(mw_rt - mw[okw]) / mw[okw], np.abs(mw_rt - mw[okw]))
    out["W_finite_share"] = float(np.isfinite(W).mean())
    out["W_nonneg_share"] = float((W >= 0).mean())
    out["W_roundtrip_max_rel_err"] = float(relw.max()) if relw.size else 0.0
    out["W_max"] = float(W[okw].max())
    out["mort_water_pos_share"] = float((mw > 0).mean())
    # (6) rh_on switch: an rh-off member must print mort_water == 0 everywhere; the rule with rh_on reproduces it
    mw_rule = mort_water_of(W, c, t, int(meta["rh_on"]), P)
    out["water_switch_max_abs_err"] = float(np.abs(mw_rule - mw).max())
    # (7) counter recursion with the trait-extended key
    key = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]
    a = df.filter(pl.col("isdead") == 0).select(key + ["Year", "c"]).with_columns((pl.col("Year") + 1).alias("Y1"))
    b = df.select(key + ["Year", "c", "Age", "cenG", "r"]).rename({"Year": "Y1", "c": "c1", "r": "r1"})
    pr = a.join(b, on=key + ["Y1"], how="inner")
    assert pr.select(key + ["Y1"]).n_unique() == pr.height, "pair key not unique"
    base = np.where(pr["Age"].to_numpy() - 1.0 == 1.0, 0, pr["c"].to_numpy())
    c1 = pr["c1"].to_numpy()
    okp = pr["cenG"].to_numpy() != CENSOR["npp_sat"]
    fail = okp & ~((c1 == 0) | (c1 == base + 1))
    rb = df["r"].to_numpy()
    out["counter_band_rows"] = int(counter_band_ambiguous(rb).sum())
    # how many band rows the recursion would move to c = 5 (previous year c = 4, alive)
    pb = pr.join(df.select(key + ["Year", "r"]).rename({"Year": "Y1"}), on=key + ["Y1"], how="left")
    out["counter_band_rows_with_cprev4"] = int((counter_band_ambiguous(pb["r"].to_numpy()) & (pb["c"].to_numpy() == 4)).sum())
    out["recursion_pairs"] = int(pr.height)
    out["recursion_fail_plain"] = int(fail.sum())
    out["recursion_fail_rate_plain"] = float(fail.sum() / max(pr.height, 1))
    # v3: the same recursion after the c = 4 / c = 5 band is resolved with the previous year's counter, i.e. the
    # call a consumer is told to make (recover_counter(..., c_prev=...)); this is the gated number
    c1_res, _ = recover_counter(np.asarray(pr["r1"].to_numpy(), dtype=np.float64), np.ones(pr.height), c_prev=pr["c"].to_numpy())
    # recover_counter clips to [0, 5] from r; the band rows with c_prev == 4 are lifted to 5, all others unchanged
    c1_res = np.where(counter_band_ambiguous(pr["r1"].to_numpy()), c1_res, c1)
    fail_res = okp & ~((c1_res == 0) | (c1_res == base + 1))
    out["recursion_fail"] = int(fail_res.sum())
    out["recursion_fail_rate"] = float(fail_res.sum() / max(pr.height, 1))
    out["recursion_band_rows_lifted_to_5"] = int((c1_res != c1).sum())
    # (8) mort_temp from SH1's day counts through SH2's rule
    segm = seg.filter((pl.col("gcm") == meta["gcm"]) & (pl.col("scen") == meta["scen"]) & (pl.col("seed") == meta["seed"])) \
              .select("Year", "clim_scen", "clim_year")
    ext = pl.scan_parquet(EXT).filter(pl.col("gcm") == meta["gcm"]).select(
        ["scen", "Cell", "Year"] + [f"tstress_pft{k}" for k in range(P.n_pft)]).collect()
    j = (df.select("Year", "Cell", "Type", "mort_temp").with_columns(pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32))
         .join(segm, on="Year", how="left")
         .join(ext.rename({"scen": "clim_scen", "Year": "clim_year"}), on=["clim_scen", "Cell", "clim_year"], how="left"))
    tt = j["Type"].to_numpy().astype(np.int64)
    days = np.full(j.height, np.nan)
    for k in range(P.n_pft):
        sel = tt == k
        days[sel] = j[f"tstress_pft{k}"].to_numpy()[sel]
    pm = mort_temp_of(days, tt, P)
    err = np.abs(pm - j["mort_temp"].to_numpy().astype(np.float64))
    out["morttemp_n_noclim"] = int(np.isnan(days).sum())
    out["morttemp_max_abs_err"] = float(np.nanmax(err))
    out["morttemp_share_abs_le_1e-6"] = float(np.nanmean(err <= 1e-6))
    # (8b) the whole chain: mortality_step(c_y, G_y+1, W_y+1, tstress_y+1, rh_on, Age_y+1 - 1) vs the printed
    #      y+1 components and hazard, on every non-censored pair
    # j carries df's rows in the join's own order; re-attach df's row ids through an explicit row index on df
    dfi = df.with_row_index("rid").with_columns(pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32))
    jt = (dfi.select("rid", "Year", "Cell").join(segm, on="Year", how="left")
          .join(ext.rename({"scen": "clim_scen", "Year": "clim_year"}), on=["clim_scen", "Cell", "clim_year"], how="left")
          .sort("rid"))
    tt2 = df["Type"].to_numpy().astype(np.int64)
    days_r = np.full(df.height, np.nan)
    for k in range(P.n_pft):
        sel = tt2 == k
        days_r[sel] = jt[f"tstress_pft{k}"].to_numpy()[sel]
    b1 = dfi.select(["rid"] + key + ["Year"]).rename({"Year": "Y1"})
    a0 = (dfi.filter(pl.col("isdead") == 0).select(key + ["Year", "c", "G", "W", "cenG", "cenW"])
          .rename({"G": "G0", "W": "W0", "cenG": "cenG0", "cenW": "cenW0"})
          .with_columns((pl.col("Year") + 1).alias("Y1")))
    ch = a0.join(b1, on=key + ["Y1"], how="inner").sort("rid")
    rid = ch["rid"].to_numpy()
    cen1 = df["cenG"].to_numpy()[rid]
    okc2 = ((cen1 == 0) | (cen1 == CENSOR["G_sign"])) & ~np.isnan(days_r[rid])
    rid = rid[okc2]
    stp = mortality_step(t[rid], df["Wooddens"].to_numpy()[rid], df["Age"].to_numpy().astype(np.float64)[rid] - 1.0,
                         ch["c"].to_numpy()[okc2], df["G"].to_numpy()[rid], df["W"].to_numpy()[rid], days_r[rid],
                         int(meta["rh_on"]), P)
    out["chain_pairs"] = int(rid.size)
    out["chain_counter_exact_share"] = float(np.mean(stp["c"] == c[rid]))
    # the sapling-leaf-carbon hard kill (mort = 1 with c < 5 and sum < 1) needs leaf carbon, which the table does
    # not carry: excluded from the hazard comparison and counted
    leafkill = hr[rid] == 3
    out["chain_leafkill_rows_excluded"] = int(leafkill.sum())
    gsign = cen1[okc2] == CENSOR["G_sign"]
    for comp, arr in [("mort_npp", mn), ("mort_age", ma), ("mort_water", mw), ("mort_temp", mt), ("mort", mo)]:
        pv = arr[rid]
        # printed value vs rule: one half-ulp of the printed value (component), five for the summed hazard
        # (its own rounding + the four parts'), + float32 storage; G_sign rows (|G| below print precision, G set
        # to -1e-9/0) carry the counter tolerance 1e-4 on the two quantities that depend on G
        tolc = (5.0 if comp == "mort" else 1.0) * half_ulp6(np.maximum(np.abs(pv), np.abs(stp[comp]))) \
            + 1.2e-7 * np.abs(pv) + 1e-12 + (COUNTER_TOL * np.abs(pv) * gsign if comp in ("mort_npp", "mort") else 0.0)
        sel = ~leafkill if comp == "mort" else np.ones(rid.size, dtype=bool)
        out[f"chain_{comp}_share_within_print"] = float(np.mean((np.abs(stp[comp] - pv) <= tolc)[sel]))
    # (8c) DIAGNOSTIC, not a rule gate (verifier minor 3): the step fed YEAR-y G and W (persistence) instead of the
    #      y+1 values recovered from the very row it is compared to. It measures how much of next year's printed
    #      mortality a tree's current growth/water state already determines — the null a learned G/W must beat.
    cG0 = ch["cenG0"].to_numpy()[okc2]
    okp0 = ((cG0 == 0) | (cG0 == CENSOR["G_sign"])) & (ch["cenW0"].to_numpy()[okc2] == 0)
    stp0 = mortality_step(t[rid][okp0], df["Wooddens"].to_numpy()[rid][okp0],
                          df["Age"].to_numpy().astype(np.float64)[rid][okp0] - 1.0, ch["c"].to_numpy()[okc2][okp0],
                          ch["G0"].to_numpy()[okc2][okp0], ch["W0"].to_numpy()[okc2][okp0], days_r[rid][okp0],
                          int(meta["rh_on"]), P)
    out["persist_pairs"] = int(okp0.sum())
    out["persist_counter_exact_share"] = float(np.mean(stp0["c"] == c[rid][okp0]))
    for comp, arr in [("mort_npp", mn), ("mort_water", mw), ("mort", mo)]:
        pv = arr[rid][okp0]
        sel = ~leafkill[okp0] if comp == "mort" else np.ones(pv.size, dtype=bool)
        e_ = np.abs(stp0[comp] - pv)[sel]
        out[f"persist_{comp}_median_abs_err"] = float(np.median(e_)) if e_.size else None
        out[f"persist_{comp}_share_rel_le_10pct"] = float(np.mean(e_ <= 0.1 * np.abs(pv[sel]) + 1e-12)) if e_.size else None
    # (9) beta_root from D95max; (10) Longevity corridor
    br = getbetaroot(df["D95max"].to_numpy(), P)
    db = np.abs(br - df["beta_root"].to_numpy().astype(np.float64))
    out["betaroot_max_abs_err"] = float(db.max())
    out["betaroot_share_le_1e-6"] = float((db <= 1e-6).mean())
    z = longevity_z(df["Longevity"].to_numpy(), df["SLA"].to_numpy(), t, P)
    out["longevity_z_absmax"] = float(np.abs(z).max())
    out["longevity_z_share_within_2_plus_1e-3"] = float((np.abs(z) <= 2.0 + 1e-3).mean())
    zz = {}
    for k in np.unique(t):
        zk = z[t == k]
        zz[int(k)] = {"n": int(zk.size), "mean": float(zk.mean()), "sd": float(zk.std())}
    out["longevity_z_by_type"] = zz
    rep[member] = {"mortality": out}
    return out


def _gate_height(member: str, coef: pl.DataFrame) -> dict:
    ext = "b_lai" in coef.columns
    df = _read_trees(member, ["Type", "Height", "agb", "Wooddens", "SLA", "LAI", "fpc_ind"])
    if ext:
        df = df.filter((pl.col("LAI") > 0) & (pl.col("fpc_ind") > 0))
    pred = predict_height(df["agb"].to_numpy(), df["Wooddens"].to_numpy(), df["SLA"].to_numpy(), df["Type"].to_numpy(), coef,
                          lai=df["LAI"].to_numpy() if ext else None, fpc_ind=df["fpc_ind"].to_numpy() if ext else None)
    y = np.log(df["Height"].to_numpy().astype(np.float64))
    lp = np.log(pred)
    t = df["Type"].to_numpy()
    res = {}
    for k in np.unique(t):
        s = (t == k) & np.isfinite(lp)
        if s.sum() < 2:
            res[int(k)] = {"n": int((t == k).sum()), "r2": None}
            continue
        e = y[s] - lp[s]
        r2 = 1 - float(e @ e) / float(((y[s] - y[s].mean()) ** 2).sum())
        res[int(k)] = {"n": int(s.sum()), "r2_log": r2, "rmse_log": float(np.sqrt(np.mean(e ** 2))),
                       "median_abs_rel_err_height": float(np.median(np.abs(np.exp(e) - 1)))}
    return res


def _key_frame(df):
    return df.select("Cell", "Patch", "Type", "ID", "SLA", "Wooddens")


# trait-kernel gate tolerances (AMENDMENT v3, declared before the v3 run: the spec gave a band, not a tolerance)
TRAIT_REL_TOL = 0.25     # |pred - obs| <= max(25 % of obs, 3 combined standard errors)
TRAIT_MIN_N = 5000       # a (member, build, PFT) cell is gated only with >= 5000 recruits
TRAIT_MIN_N_COND = 200   # channel-free tests: >= 200 conditioning recruits
TRAIT_POOLED_ABS = 0.005 # the v2 pooled gate's absolute floor (kept for the pooled, spec-level gate only)
_KPACK = 16              # bank key packing: (cell * 16 + Type) * 10000 + year


def _trait_tol(obs, n, pred, n_pred):
    se = math.sqrt(max(obs * (1 - obs), 0.0) / max(n, 1) + max(pred * (1 - pred), 0.0) / max(n_pred, 1))
    return max(TRAIT_REL_TOL * obs, 3.0 * se)


def _bank_arrays(frame: pl.DataFrame):
    b = frame.sort("Cell", "Type", "Year")
    bc = b["Cell"].to_numpy().astype(np.int64)
    bt = b["Type"].to_numpy().astype(np.int64)
    by = b["Year"].to_numpy().astype(np.int64)
    return {"key": (bc * _KPACK + bt) * 10000 + by, "Wooddens": b["Wooddens"].to_numpy().astype(np.float64),
            "D95max": b["D95max"].to_numpy().astype(np.float64), "ymin": int(by.min()), "n": int(b.height)}


def _kernel_mc(bank, rc, t, ylo, yhi, b_est, P, rng, M):
    """pi_k of the recruit's own PFT among bank entries in [ylo, yhi], and Monte-Carlo P(out | inherited) for
    Wooddens, D95max and both jointly (same parent per draw), per recruit, for builds actual/dec2025/feb2026."""
    n = rc.size
    cnt = np.zeros((n, P.n_pft))
    for k in range(P.n_pft):
        s0 = np.searchsorted(bank["key"], (rc * _KPACK + k) * 10000 + ylo, "left")
        e0 = np.searchsorted(bank["key"], (rc * _KPACK + k) * 10000 + yhi, "right")
        cnt[:, k] = e0 - s0
    tot = cnt.sum(1)
    pi = np.divide(cnt, tot[:, None], out=np.zeros_like(cnt), where=tot[:, None] > 0)
    s_k = np.searchsorted(bank["key"], (rc * _KPACK + t) * 10000 + ylo, "left")
    e_k = np.searchsorted(bank["key"], (rc * _KPACK + t) * 10000 + yhi, "right")
    nk = e_k - s_k
    lo = {k: P[f"{pre}_low"][t] for k, pre in (("Wooddens", "wooddens"), ("D95max", "d95max"))}
    hi = {k: P[f"{pre}_high"][t] for k, pre in (("Wooddens", "wooddens"), ("D95max", "d95max"))}
    res = {}
    for build in ("actual", "dec2025", "feb2026"):
        bb = b_est if build == "actual" else build
        acc = {"Wooddens": np.zeros(n), "D95max": np.zeros(n), "joint": np.zeros(n)}
        for _ in range(M):
            idx = s_k + np.floor(rng.random(n) * np.maximum(nk, 1)).astype(np.int64)
            idx = np.minimum(idx, bank["key"].size - 1)
            new = inherit_traits(t, {"Wooddens": bank["Wooddens"][idx], "D95max": bank["D95max"][idx]}, bb, rng, P)
            o = {k: ((new[k] < lo[k]) | (new[k] > hi[k])) & (nk > 0) for k in ("Wooddens", "D95max")}
            acc["Wooddens"] += o["Wooddens"]
            acc["D95max"] += o["D95max"]
            acc["joint"] += o["Wooddens"] & o["D95max"]
        res[build] = {k: v / M for k, v in acc.items()}
    return pi, nk, res


def _gate_traits(member: str, P, rng_seed: int = 20261001, M: int = 8) -> dict:
    """Out-of-own-interval share of recruit Wooddens/D95max: observed vs the C kernel fed truth parents.
    v3 (verifier major defect): per build of the ESTABLISHMENT year x per PFT; two seedbank proxies; implied
    inheritance share per PFT and trait; two channel-free kernel tests that no channel weight can mask:
      K1 recruits whose PFT was NOT eligible at establishment (only the inheritance channel can make them, so
         P(inherit) = 1 exactly): observed share vs P(out | inherited) directly;
      K2 recruits whose Wooddens is out of its own interval (the background channel draws inside the own interval,
         so such a recruit is certainly inherited): observed P(D95max out | Wooddens out) vs the kernel's joint draw.
    Bank proxies: A = every living printed (> 5 m) tree-year in [y_est-50, y_est-1] (v2); C = A plus the sub-5 m
    tree-years of every tree that LATER appears in print (back-filled from its first printed year and Age: traits
    are immutable). The true bank (top 3937 trees by agb, all heights) contains C's extra entries only if their agb
    clears the threshold, and also sub-5 m trees that died before 5 m, which no proxy can see."""
    meta = _member_meta(member)
    mem, seg, _, _ = _registry()
    gcm, scen, seed, win = meta["gcm"], meta["scen"], int(meta["seed"]), meta["win"]
    assert win == "w2015", "trait gate members must be 2015-2044 windows (owner decision 2026-10-01)"
    assert P.n_pft < _KPACK
    chain = [f"{gcm}_Historical_s{seed}_h1985", f"{gcm}_{scen}_s{seed}_w2015"]
    assert chain[-1] == member
    cols = ["Year", "Cell", "Patch", "Type", "ID", "isdead", "Age", "SLA", "Wooddens", "D95max", "minwscal"]
    frames = [_read_trees(m, cols) for m in chain]
    allr = pl.concat(frames)
    KEY = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]
    y_chain0 = int(allr["Year"].min())
    y0 = int(frames[-1]["Year"].min())
    first = allr.group_by(KEY).agg(pl.col("Year").min().alias("t_first"))
    assert first.select(KEY).n_unique() == first.height
    rec = (frames[-1].join(first, on=KEY, how="inner")
           .filter((pl.col("Year") == pl.col("t_first")) & (pl.col("Year") > y0)))
    rec = rec.with_columns((pl.col("Year") - pl.col("Age").cast(pl.Int32)).cast(pl.Int32).alias("y_est"))
    t = rec["Type"].to_numpy().astype(np.int64)
    obs = {}
    obs_row = {}
    for key, pre in [("Wooddens", "wooddens"), ("D95max", "d95max"), ("SLA", "sla"), ("minwscal", "minwscal")]:
        v = rec[key].to_numpy().astype(np.float64)
        lo, hi = P[f"{pre}_low"][t], P[f"{pre}_high"][t]
        obs_row[key] = (v < lo * (1 - 1e-6)) | (v > hi * (1 + 1e-6))
        obs[key] = float(np.mean(obs_row[key]))
    # bank proxy A (v2) and C (A + back-filled sub-5 m years of later-visible trees)
    liv = allr.filter(pl.col("isdead") == 0).select("Cell", "Type", "Year", "Wooddens", "D95max")
    bankA = _bank_arrays(liv)
    fa = (first.filter(pl.col("t_first") > y_chain0)
          .join(allr.select(KEY + ["Year", "Age", "D95max"]).rename({"Year": "t_first"}), on=KEY + ["t_first"], how="inner"))
    assert fa.select(KEY).n_unique() == fa.height, "back-fill key not unique"
    back = (fa.with_columns(pl.col("Age").round(0).cast(pl.Int32).alias("a"))
            .filter(pl.col("a") >= 1)
            .with_columns(pl.int_ranges(pl.col("t_first").cast(pl.Int32) - pl.col("a"), pl.col("t_first").cast(pl.Int32)).alias("Year"))
            .explode("Year")
            .select(pl.col("Cell"), pl.col("Type"), pl.col("Year").cast(liv["Year"].dtype), pl.col("Wooddens"), pl.col("D95max")))
    bankC = _bank_arrays(pl.concat([liv, back.select(liv.columns)]))
    # bank size diagnostics: printed + back-filled entries per cell-year vs the C's top-n (all trees, all heights)
    npatch = int(meta["npatch"])  # from the registry, never hard-coded
    nbank = seedbank_n(npatch, P)
    per_cy = (pl.concat([liv.select("Cell", "Year"), back.select("Cell", "Year")]).filter(pl.col("Year") >= y_chain0)
              .group_by("Cell", "Year").len())
    per_cyA = liv.group_by("Cell", "Year").len()
    rc = rec["Cell"].to_numpy().astype(np.int64)
    ye = rec["y_est"].to_numpy().astype(np.int64)
    ylo = ye - P.g["max_age"]
    yhi = ye - 1
    cover = yhi >= bankA["ymin"]
    # eligibility at the establishment year (C-faithful: current-year gdd5, 20-yr buffers incl. that year)
    segm = seg.filter((pl.col("gcm") == gcm) & (pl.col("scen") == scen) & (pl.col("seed") == seed)).select(
        pl.col("Year").alias("y_est"), "clim_scen", "clim_year", "bin_feb2026")
    cy = pl.scan_parquet(CLIM).filter(pl.col("gcm") == gcm).select(
        pl.col("scen").alias("clim_scen"), "Cell", pl.col("Year").alias("clim_year"), "tcold_month_tr20",
        "twarm_month_tr20", "gdd5", "prec_ann").collect()
    jj = (rec.select(pl.col("Cell").cast(pl.Int32), "y_est").with_row_index("i")
          .join(segm, on="y_est", how="left").join(cy, on=["clim_scen", "Cell", "clim_year"], how="left").sort("i"))
    has_clim = jj["tcold_month_tr20"].is_not_null().to_numpy()
    el = eligible(jj["tcold_month_tr20"].fill_null(np.nan).to_numpy(), jj["twarm_month_tr20"].fill_null(np.nan).to_numpy(),
                  jj["gdd5"].fill_null(np.nan).to_numpy(), jj["prec_ann"].fill_null(np.nan).to_numpy(), P)
    ar = np.arange(rec.height)
    elk = el[ar, t].astype(np.float64)
    use = cover & has_clim
    b_est = build_of(jj["bin_feb2026"].fill_null(0).to_numpy())
    rng = np.random.default_rng(rng_seed)
    prox = {}
    for nm, bank in (("A", bankA), ("C", bankC)):
        pi, nk, res = _kernel_mc(bank, rc, t, ylo, yhi, b_est, P, rng, M)
        pinh = p_inherit_given_type(pi[ar, t], elk, P)
        prox[nm] = {"pinh": pinh, "nk": nk, "res": res}
    # ---------------- pooled (spec-level, proxy A, unchanged definition from v2)
    pA = prox["A"]
    pred = {}
    for build in ("actual", "dec2025", "feb2026"):
        r_ = pA["res"][build]
        pred[build] = {k: float(np.mean((pA["pinh"] * r_[k])[use])) for k in ("Wooddens", "D95max")}
        pred[build]["P_out_given_inherit"] = {k: float(np.mean(r_[k][use & (pA["nk"] > 0)])) for k in ("Wooddens", "D95max")}
    obs_use = {k: float(np.mean(obs_row[k][use])) for k in ("Wooddens", "D95max")}
    w_eff = {k: (obs_use[k] / pred["actual"]["P_out_given_inherit"][k]) if pred["actual"]["P_out_given_inherit"][k] > 0 else None
             for k in ("Wooddens", "D95max")}
    # ---------------- per build x PFT (v3)
    cells = []
    for bname in ("dec2025", "feb2026"):
        for k in range(P.n_pft):
            sk = use & (t == k) & (b_est == bname)
            n_k = int(sk.sum())
            if n_k == 0:
                continue
            d = {"build": bname, "Type": k, "n": n_k, "gated": n_k >= TRAIT_MIN_N}
            for key in ("Wooddens", "D95max"):
                ob = float(obs_row[key][sk].mean())
                d[f"obs_{key}"] = ob
                for nm in ("A", "C"):
                    px = prox[nm]
                    r_ = px["res"]["actual"]
                    pr_ = float((px["pinh"] * r_[key])[sk].mean())
                    pout = float(r_[key][sk & (px["nk"] > 0)].mean()) if (sk & (px["nk"] > 0)).any() else float("nan")
                    d[f"pred_{key}_{nm}"] = pr_
                    d[f"P_out_given_inherit_{key}_{nm}"] = pout
                    d[f"implied_inherit_share_{key}_{nm}"] = ob / pout if pout > 0 else None
                    d[f"mean_p_inherit_{nm}"] = float(px["pinh"][sk].mean())
                    tol = _trait_tol(ob, n_k, pr_, n_k * M)
                    d[f"tol_{key}_{nm}"] = tol
                    d[f"pass_{key}_{nm}"] = bool(abs(pr_ - ob) <= tol)
                    d[f"ratio_obs_pred_{key}_{nm}"] = ob / pr_ if pr_ > 0 else None
            # K2: P(D95max out | Wooddens out) — channel-free
            wo = sk & obs_row["Wooddens"]
            d["K2_n_wd_out"] = int(wo.sum())
            if wo.sum() > 0:
                ob2 = float(obs_row["D95max"][wo].mean())
                d["K2_obs_P_d95out_given_wdout"] = ob2
                for nm in ("A", "C"):
                    px = prox[nm]
                    r_ = px["res"]["actual"]
                    den = float((px["pinh"] * r_["Wooddens"])[sk].sum())
                    pr2 = float((px["pinh"] * r_["joint"])[sk].sum()) / den if den > 0 else float("nan")
                    d[f"K2_pred_{nm}"] = pr2
                    tol2 = _trait_tol(ob2, int(wo.sum()), pr2 if np.isfinite(pr2) else 0.0, max(int(wo.sum()) * M, 1))
                    d[f"K2_pass_{nm}"] = bool(np.isfinite(pr2) and abs(pr2 - ob2) <= tol2) if wo.sum() >= TRAIT_MIN_N_COND else None
            # K1: ineligible PFT at establishment => P(inherit) = 1 exactly
            k1 = sk & (elk == 0)
            d["K1_n_ineligible"] = int(k1.sum())
            if k1.sum() > 0:
                for key in ("Wooddens", "D95max"):
                    ob1 = float(obs_row[key][k1].mean())
                    d[f"K1_obs_{key}"] = ob1
                    for nm in ("A", "C"):
                        px = prox[nm]
                        m1 = k1 & (px["nk"] > 0)
                        pr1 = float(px["res"]["actual"][key][m1].mean()) if m1.any() else float("nan")
                        d[f"K1_pred_{key}_{nm}"] = pr1
                        tol1 = _trait_tol(ob1, int(k1.sum()), pr1 if np.isfinite(pr1) else 0.0, max(int(m1.sum()) * M, 1))
                        d[f"K1_pass_{key}_{nm}"] = (bool(np.isfinite(pr1) and abs(pr1 - ob1) <= tol1)
                                                    if k1.sum() >= TRAIT_MIN_N_COND else None)
            cells.append(d)
    # selection diagnostic: observed vs predicted share by AGE AT ENTRY (years from establishment to first print at
    # > 5 m). The kernel's prediction does not depend on it; the observed share does if survival/growth to 5 m selects
    # on the trait.
    age_e = rec["Age"].to_numpy().astype(np.float64)
    bins = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 30), (31, 400)]
    by_age = []
    for bname in ("dec2025", "feb2026"):
        for k in range(P.n_pft):
            for a0_, a1_ in bins:
                sk = use & (t == k) & (b_est == bname) & (age_e >= a0_) & (age_e <= a1_)
                if sk.sum() < 500:
                    continue
                d = {"build": bname, "Type": k, "age_entry": f"{a0_}-{a1_}", "n": int(sk.sum())}
                for key in ("Wooddens", "D95max"):
                    d[f"obs_{key}"] = float(obs_row[key][sk].mean())
                    d[f"pred_{key}_C"] = float((prox["C"]["pinh"] * prox["C"]["res"]["actual"][key])[sk].mean())
                by_age.append(d)
    # per (Type, y_est) sums for the matched-establishment-year BUILD CONTRAST (stage_gates pairs ssp245 with ssp370)
    by_yest = []
    pc = prox["C"]
    for k in range(P.n_pft):
        for y in np.unique(ye[use & (t == k)]):
            sk = use & (t == k) & (ye == y)
            d = {"Type": k, "y_est": int(y), "n": int(sk.sum()), "build": str(b_est[sk][0])}
            for key in ("Wooddens", "D95max"):
                d[f"n_obs_{key}"] = int(obs_row[key][sk].sum())
                for b_ in ("dec2025", "feb2026"):
                    d[f"sum_pred_{key}_{b_}"] = float((pc["pinh"] * pc["res"][b_][key])[sk].sum())
            by_yest.append(d)
    nel = el.sum(1)
    return {"member": member, "build": meta["build"], "n_recruits": int(rec.height), "n_used": int(use.sum()),
            "by_age_at_entry": by_age, "by_y_est": by_yest,
            "share_established_by_feb2026": float((b_est == "feb2026")[use].mean()),
            "implied_inherit_share": w_eff, "by_build_type": cells,
            "bank": {"seedbank_n_C": nbank, "npatch": npatch, "proxyA_entries": bankA["n"], "proxyC_entries": bankC["n"],
                     "backfilled_entries": int(back.height),
                     "proxyA_per_cell_year_median": float(per_cyA["len"].median()),
                     "proxyC_per_cell_year_median": float(per_cy["len"].median()),
                     "proxyC_per_cell_year_share_above_seedbank_n": float((per_cy["len"] > nbank).mean())},
            "share_used": float(use.mean()), "years": [y0 + 1, int(frames[-1]["Year"].max())], "bank_chain": chain,
            "obs_all": obs, "obs_used": obs_use, "pred": pred,
            "mean_p_inherit_given_type": float(pA["pinh"][use].mean()),
            "mean_p_inherit_given_type_C": float(prox["C"]["pinh"][use].mean()),
            "mean_n_eligible": float(nel[use].mean()),
            "mean_inherit_weight_unconditional": float(inherit_weight(nel[use], P).mean()),
            "recruit_type_counts": {int(k): int((t == k).sum()) for k in np.unique(t)},
            "median_age_at_entry": float(np.median(rec["Age"].to_numpy()))}


def _gate_eligibility(P) -> dict:
    """Reproduce probe C (struct architect) exactly with its gdd basis (gdd5_tr20), then the C-faithful one."""
    pc = pl.read_csv(PROBE_C)
    cy = pl.scan_parquet(CLIM)
    out = {"rows": [], "skipped_excluded": []}
    maxdiff = 0.0
    ex = excluded_members()
    for r in pc.iter_rows(named=True):
        m = r["member"]
        if m in ex:  # probe C was computed before the owner decision; its late-century rows are not re-read
            out["skipped_excluded"].append(m)
            continue
        assert_usable(m)
        gcm, scen, seed, win = m.rsplit("_", 3)
        cells = pl.scan_parquet(os.path.join(DEV, f"{m}.parquet")).filter(pl.col("Type") <= 6).select(
            pl.col("Cell").cast(pl.Int32)).unique().collect()
        yrs = {"h1985": (1985, 2014), "w2015": (2015, 2044)}[win]
        c = (cy.filter((pl.col("gcm") == gcm) & (pl.col("scen") == scen) & pl.col("Year").is_between(*yrs))
             .select("Cell", "Year", "tcold_month_tr20", "twarm_month_tr20", "gdd5_tr20", "gdd5", "prec_ann").collect()
             .join(cells, on="Cell", how="semi"))
        # probe C's expression (no aprec term, tr20 gdd) through the library
        e_tr20 = eligible(c["tcold_month_tr20"].to_numpy(), c["twarm_month_tr20"].to_numpy(), c["gdd5_tr20"].to_numpy(),
                          np.full(c.height, 1e9), P)
        e_c = eligible(c["tcold_month_tr20"].to_numpy(), c["twarm_month_tr20"].to_numpy(), c["gdd5"].to_numpy(),
                       c["prec_ann"].to_numpy(), P)
        row = {"member": m, "n_cell_years": c.height}
        for k in range(P.n_pft):
            sh = float(e_tr20[:, k].mean())
            d = abs(sh - float(r[f"elig_{k}"]))
            maxdiff = max(maxdiff, d)
            row[f"elig_{k}_lib_tr20"] = sh
            row[f"elig_{k}_probeC"] = float(r[f"elig_{k}"])
            row[f"elig_{k}_faithful"] = float(e_c[:, k].mean())
        row["mean_n_eligible_faithful"] = float(e_c.sum(1).mean())
        out["rows"].append(row)
    out["max_abs_diff_vs_probeC"] = maxdiff
    return out


def _gate_survive(member: str, P) -> dict:
    """Living trees of PFT k in a cell-year where survive(k) is False must be 0 (survive kills them, flagged)."""
    meta = _member_meta(member)
    _, seg, _, _ = _registry()
    df = _read_trees(member, ["Year", "Cell", "Type", "isdead"]).with_columns(pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32))
    segm = seg.filter((pl.col("gcm") == meta["gcm"]) & (pl.col("scen") == meta["scen"]) & (pl.col("seed") == meta["seed"])).select(
        "Year", "clim_scen", "clim_year")
    cy = pl.scan_parquet(CLIM).filter(pl.col("gcm") == meta["gcm"]).select(
        pl.col("scen").alias("clim_scen"), "Cell", pl.col("Year").alias("clim_year"), "tcold_month_tr20", "twarm_month_tr20").collect()
    g = df.group_by("Year", "Cell", "Type").agg(pl.len().alias("n"), (pl.col("isdead") == 0).sum().alias("n_live"))
    g = g.join(segm, on="Year", how="left").join(cy, on=["clim_scen", "Cell", "clim_year"], how="left")
    sv = survive(g["tcold_month_tr20"].to_numpy(), g["twarm_month_tr20"].to_numpy(), P)
    tt = g["Type"].to_numpy().astype(np.int64)
    ok = sv[np.arange(g.height), tt]
    nl = g["n_live"].to_numpy()
    return {"member": member, "groups": int(g.height), "groups_survive_false": int((~ok).sum()),
            "living_rows_where_survive_false": int(nl[~ok].sum()), "rows_where_survive_false": int(g["n"].to_numpy()[~ok].sum())}


def stage_gates():
    os.makedirs(OUT, exist_ok=True)
    P = load_params()
    rep: dict = {"basis": "dev subset (Cell % 10 == 0, 907 cells), tree rows Type <= 6, all years of each window"}
    gates = []

    def G(name, ok, detail):
        gates.append({"name": name, "pass": bool(ok), "detail": detail})
        log("GATE", name, "PASS" if ok else "FAIL", detail)

    pj = json.load(open(PARAMS_JSON))
    G("params_cpp_equals_reference_csvs", not pj["checks"]["csv_crosscheck_mismatches"],
      f"{pj['checks']['n_pairs_checked']} parameter columns; duplicate keys (last wins) {pj['duplicate_keys_pft']}")
    st = stage_selftest()
    rep["selftest"] = st
    G("selftest", st["pass"], json.dumps({k: v for k, v in st.items() if k != "pass"}))
    coef_all = pl.read_parquet(ALLOM)
    coef_ext = pl.read_parquet(ALLOM_EXT)
    # owner decision 2026-10-01: the library must refuse the late-century windows, and nothing it built may use them
    ex = excluded_members()
    mem_all = pl.read_parquet(os.path.join(REG, "members.parquet"))
    ex_wins = sorted(mem_all.filter(pl.col("member").is_in(list(ex)))["win"].unique().to_list())
    refused = []
    if not ALLOW_EXCLUDED:
        for m in sorted(ex):
            try:
                _scan_dev(m)  # raises before any file is opened
            except ExcludedMemberError:
                refused.append(m)
    trm_all = sorted({x for s_ in coef_all["train_members"].to_list() for x in s_.split(" | ")})
    used = set(trm_all) | set(GATE_MEMBERS) | set(TRAIT_MEMBERS)
    rep["exclusion"] = {"excluded_members": sorted(ex), "excluded_windows": ex_wins, "refused_by_library": refused,
                        "allometry_train_members": trm_all, "gate_members": GATE_MEMBERS, "trait_members": TRAIT_MEMBERS}
    G("exclusion_enforced", len(ex) > 0 and set(ex_wins) <= {"w2071", "w3071"} and len(refused) == len(ex)
      and not (used & set(ex)),
      f"{len(ex)} excluded members (windows {ex_wins}); library refuses {len(refused)}/{len(ex)} without reading; "
      f"allometry training members {len(trm_all)} ({sorted({m.rsplit('_', 1)[1] for m in trm_all})}), "
      f"none excluded; gate/trait members none excluded")
    # consistency with SH1's mort_temp helper (the tracks may call either)
    try:
        import explore_de_sh_climate_ext as cx
        tp = cx.pft_temp_params()
        dmax = 0.0
        days = np.arange(0, 366, dtype=np.float64)
        for rr in tp.iter_rows(named=True):
            k = int(rr["pft_id"])
            if k >= P.n_pft:
                continue
            a1 = mort_temp_of(days, np.full(days.size, k), P)
            a2 = cx.mort_temp_from_count(days, rr["mort_temp_factor"], rr["ndayyear"])
            dmax = max(dmax, float(np.abs(a1 - a2).max()))
        G("mort_temp_equals_SH1_helper", dmax == 0.0, f"max |diff| {dmax:.3g} over days 0-365 x {P.n_pft} tree PFTs")
    except Exception as e:  # noqa: BLE001 — report, do not hide
        G("mort_temp_equals_SH1_helper", False, f"could not compare: {e!r}")
    for m in GATE_MEMBERS:
        o = _gate_mortality(m, P, rep)
        G(f"mort_eq_min1_sum_nonhard[{m}]", o["mortsum_max_rel_err"] <= 1e-5 and o["mortsum_n_print_violations"] == 0,
          f"max rel err {o['mortsum_max_rel_err']:.3g} (spec 1e-5; rows above it {o['mortsum_n_rel_gt_1e-5']}), "
          f"print-precision violations {o['mortsum_n_print_violations']}, over {o['mortsum_n_nonhard']} non-hard rows")
        G(f"mort_age_from_Age_minus_1[{m}]", o["mortage_max_rel_err"] <= 1e-5,
          f"max rel err {o['mortage_max_rel_err']:.3g} over {o['n_tree_rows']} rows")
        G(f"counter_recursion[{m}]", o["recursion_fail_rate"] <= 1e-5,
          f"with the c_prev band resolution (the documented call): {o['recursion_fail']} failures / "
          f"{o['recursion_pairs']} pairs = {o['recursion_fail_rate']:.3g} ({o['recursion_band_rows_lifted_to_5']} band rows "
          f"lifted to c=5); plain formula without c_prev: {o['recursion_fail_plain']} = {o['recursion_fail_rate_plain']:.3g}")
        G(f"forbidden_bands_empty[{m}]", o["forbidden_band_n"] == 0,
          f"{o['forbidden_band_n']} rows (c=0: {o['forbidden_band_n_c0']}, c>=1: {o['forbidden_band_n_cpos']})")
        G(f"c5_implies_isdead[{m}]", o["c5_isdead_share"] in (None, 1.0), f"{o['c5_n']} rows, share dead {o['c5_isdead_share']}")
        G(f"W_roundtrip_exact[{m}]", o["W_finite_share"] == 1.0 and o["W_nonneg_share"] == 1.0 and o["W_roundtrip_max_rel_err"] <= 1e-12,
          f"finite {o['W_finite_share']}, max rel err {o['W_roundtrip_max_rel_err']:.3g}, W_sat censored {o['censor_W_count']}")
        G(f"G_roundtrip_exact[{m}]", o["G_finite_on_uncensored_share"] == 1.0 and o["G_roundtrip_max_rel_err"] <= 1e-9,
          f"finite {o['G_finite_on_uncensored_share']}, max rel err {o['G_roundtrip_max_rel_err']:.3g}, censored {o['censor_G_counts']}")
        # CONSISTENCY CHECK, cannot fail on usable data (rh_on = 1 everywhere): a W round trip (verifier minor 3)
        G(f"consistency_mort_water_W_roundtrip_rh_on[{m}]", o["water_switch_max_abs_err"] <= 1e-6 if o["rh_on"] == 1 else o["mort_water_pos_share"] == 0.0,
          f"rh_on={o['rh_on']}, share mort_water>0 {o['mort_water_pos_share']:.4g}, rule max abs err {o['water_switch_max_abs_err']:.3g}")
        # CONSISTENCY CHECK, not a prediction (verifier minor 3): G and W are recovered from the same y+1 row that is
        # compared, so mort_npp/mort_water are round-trip identities; its independent content (recursion, mort_age,
        # mort_temp) is gated separately. The persistence diagnostic (year-y G, W) is reported beside it.
        G(f"consistency_mortality_step_identity[{m}]", o["chain_counter_exact_share"] >= 1 - 1e-5 and o["chain_mort_share_within_print"] >= 1 - 1e-4,
          f"{o['chain_pairs']} pairs ({o['chain_leafkill_rows_excluded']} leaf-carbon hard kills excluded from the hazard): "
          f"counter exact {o['chain_counter_exact_share']:.7f}; share within print precision: "
          + ", ".join(f"{c} {o[f'chain_{c}_share_within_print']:.6f}" for c in ("mort_npp", "mort_age", "mort_water", "mort_temp", "mort")))
        G(f"mort_temp_rule[{m}]", o["morttemp_n_noclim"] == 0 and o["morttemp_max_abs_err"] <= 1e-6,
          f"max abs err {o['morttemp_max_abs_err']:.3g}, share <=1e-6 {o['morttemp_share_abs_le_1e-6']}")
        G(f"getbetaroot[{m}]", o["betaroot_max_abs_err"] <= BISECT_XACC,
          f"max abs err {o['betaroot_max_abs_err']:.3g}, share <=1e-6 {o['betaroot_share_le_1e-6']:.6f}")
        G(f"longevity_corridor_bounds[{m}]", o["longevity_z_share_within_2_plus_1e-3"] == 1.0,
          f"max |z| {o['longevity_z_absmax']:.5f}")
        hard_dead = o["hard_isdead_share"]
        G(f"hard_kill_implies_isdead[{m}]", hard_dead in (None, 1.0), f"{o['hard_n']} hard rows {o['hard_reason_counts']} share dead {hard_dead}")
        # height allometry: DEV-A coefficients (fitted on MPI s1 training members, dev folds 1-4)
        cA = coef_all.filter((pl.col("split") == "DEV-A") & (pl.col("cellset") == "dev_f1234"))
        insample = m in set(cA["train_members"][0].split(" | "))
        lab = "IN-SAMPLE (a training member; 4 of 5 folds' cells were in the fit)" if insample else "out-of-sample member"
        h = _gate_height(m, cA)
        rep[m]["height_allometry_DEV-A"] = h
        rep[m]["height_allometry_insample"] = insample
        gated = {k: v for k, v in h.items() if v.get("r2_log") is not None and v["n"] >= 1000}
        G(f"height_allometry_r2_ge_0.99[{m}]", all(v["r2_log"] >= 0.99 for v in gated.values()),
          f"[{lab}] " + "; ".join(f"Type {k}: R2 {v['r2_log']:.5f} rmse_log {v['rmse_log']:.4f} n {v['n']}" for k, v in gated.items())
          + (f"; not gated (<1000 rows): {[k for k, v in h.items() if k not in gated]}" if len(gated) < len(h) else ""))
        # optional extended allometry (+ ln LAI + ln fpc_ind), same threshold, reported as its own gate
        hx = _gate_height(m, coef_ext.filter((pl.col("split") == "DEV-A") & (pl.col("cellset") == "dev_f1234")))
        rep[m]["height_allometry_ext_DEV-A"] = hx
        gx = {k: v for k, v in hx.items() if v.get("r2_log") is not None and v["n"] >= 1000}
        G(f"height_allometry_ext_r2_ge_0.99[{m}] (optional form)", all(v["r2_log"] >= 0.99 for v in gx.values()),
          f"[{lab}] " + "; ".join(f"Type {k}: R2 {v['r2_log']:.5f} rmse_log {v['rmse_log']:.4f}" for k, v in gx.items()))
        sv = _gate_survive(m, P)
        rep[m]["survive"] = sv
        G(f"survive_no_living_tree_outside_limits[{m}]", sv["living_rows_where_survive_false"] == 0, json.dumps(sv))
    # eligibility vs probe C
    el = _gate_eligibility(P)
    rep["eligibility"] = el
    # CONSISTENCY CHECK with round-1 probe C on probe C's own (non-faithful) inputs: 20-yr gdd5, no aprec. It is NOT a
    # validation of the C-faithful eligibility (current-year gdd5 + aprec), which no model output pins down directly.
    G("consistency_eligibility_equals_probeC", el["max_abs_diff_vs_probeC"] <= 1e-12,
      f"max |diff| {el['max_abs_diff_vs_probeC']:.3g} over {len(el['rows'])} members x {P.n_pft} PFTs (probe C's gdd5_tr20 basis, "
      f"no aprec term; consistency, not validation)")
    # draw_new_trait / build quirk
    tr = {}
    verified = {k: True for k in range(P.n_pft)}
    seen = {k: False for k in range(P.n_pft)}
    for m in TRAIT_MEMBERS:
        o = _gate_traits(m, P)
        tr[m] = o
        b = BUILDS[o["build"]]
        other = "feb2026" if b == "dec2025" else "dec2025"
        for key in ("Wooddens", "D95max"):
            ob, pr, cf = o["obs_used"][key], o["pred"]["actual"][key], o["pred"][other][key]
            tol = max(TRAIT_REL_TOL * ob, TRAIT_POOLED_ABS)
            switch = o["pred"]["dec2025"][key] > o["pred"]["feb2026"][key]
            G(f"draw_new_trait_out_of_interval_POOLED_{key}[{m}]", abs(pr - ob) <= tol and switch,
              f"POOLED over PFTs (80 % beech; per-PFT gates below decide what is verified); proxy A; print build {b} "
              f"(share of recruits established by Feb-2026 {o['share_established_by_feb2026']:.3f}): observed {ob:.4f}, "
              f"predicted {pr:.4f} (tol {tol:.4f}); all-{other} counterfactual {cf:.4f}; implied inheritance share "
              f"{o['implied_inherit_share'][key]:.3f} vs closed form {o['mean_p_inherit_given_type']:.3f}")
        # per (build, PFT): marginal shares on proxy C (gated) and A (reported); channel-free K1/K2 (gated where n allows)
        for key in ("Wooddens", "D95max"):
            cells = [d for d in o["by_build_type"] if d["gated"]]
            ok = all(d[f"pass_{key}_C"] for d in cells)
            G(f"draw_new_trait_per_PFT_{key}[{m}]", ok,
              "; ".join(f"{d['build']} T{d['Type']} n {d['n']}: obs {d[f'obs_{key}']:.4f} pred C {d[f'pred_{key}_C']:.4f} "
                        f"(A {d[f'pred_{key}_A']:.4f}) {'ok' if d[f'pass_{key}_C'] else 'FAIL'}" for d in cells))
            for d in cells:
                seen[d["Type"]] = True
                if not d[f"pass_{key}_C"]:
                    verified[d["Type"]] = False
        k2 = [d for d in o["by_build_type"] if d.get("K2_pass_C") is not None]
        G(f"kernel_channel_free_K2_P_d95out_given_wdout[{m}]", all(d["K2_pass_C"] for d in k2) if k2 else False,
          "; ".join(f"{d['build']} T{d['Type']} n {d['K2_n_wd_out']}: obs {d['K2_obs_P_d95out_given_wdout']:.3f} "
                    f"pred C {d['K2_pred_C']:.3f} (A {d['K2_pred_A']:.3f}) {'ok' if d['K2_pass_C'] else 'FAIL'}" for d in k2)
          or "no (build, PFT) cell with >= 200 Wooddens-out recruits")
        for d in k2:
            seen[d["Type"]] = True
            if not d["K2_pass_C"]:
                verified[d["Type"]] = False
        k1 = [d for d in o["by_build_type"] if d.get("K1_pass_Wooddens_C") is not None]
        if k1:
            okk = all(d["K1_pass_Wooddens_C"] and d["K1_pass_D95max_C"] for d in k1)
            G(f"kernel_channel_free_K1_ineligible_PFT[{m}]", okk,
              "; ".join(f"{d['build']} T{d['Type']} n {d['K1_n_ineligible']}: WD obs {d['K1_obs_Wooddens']:.4f} pred "
                        f"{d['K1_pred_Wooddens_C']:.4f}, D95 obs {d['K1_obs_D95max']:.4f} pred {d['K1_pred_D95max_C']:.4f}" for d in k1))
            for d in k1:
                if not (d["K1_pass_Wooddens_C"] and d["K1_pass_D95max_C"]):
                    verified[d["Type"]] = False
        else:
            rep.setdefault("trait_K1_untestable", []).append(m)
        G(f"draw_new_trait_SLA_minwscal_never_out[{m}]", o["obs_all"]["SLA"] == 0.0 and o["obs_all"]["minwscal"] == 0.0,
          f"observed SLA {o['obs_all']['SLA']}, minwscal {o['obs_all']['minwscal']}")
    # matched-establishment-year BUILD CONTRAST (selection-robust to first order): the same GCM and seed share their
    # 1985-2014 history; recruits established from 2015 on came from the Feb-2026 build in ssp245 and from the
    # Dec-2025 build in ssp370. Observed ratio of out-of-interval shares (ssp370 reweighted to ssp245's y_est mix)
    # vs the kernel's feb/dec ratio on the ssp245 recruits' own parents. Pass: |R_pred - R_obs| <= 25 % of R_obs.
    contrast = []
    for m in TRAIT_MEMBERS:
        if "_ssp245_" not in m:
            continue
        m370 = m.replace("_ssp245_", "_ssp370_")
        if m370 not in tr:
            continue
        for k in range(P.n_pft):
            a = {(d["y_est"]): d for d in tr[m]["by_y_est"] if d["Type"] == k and d["build"] == "feb2026" and d["y_est"] <= 2034}
            b = {(d["y_est"]): d for d in tr[m370]["by_y_est"] if d["Type"] == k}
            ys = sorted(y for y in a if y in b and b[y]["n"] > 0)
            n245 = sum(a[y]["n"] for y in ys)
            if n245 < TRAIT_MIN_N:
                continue
            for key in ("Wooddens", "D95max"):
                o245 = sum(a[y][f"n_obs_{key}"] for y in ys) / n245
                o370 = sum(a[y]["n"] * b[y][f"n_obs_{key}"] / b[y]["n"] for y in ys) / n245
                pf = sum(a[y][f"sum_pred_{key}_feb2026"] for y in ys)
                pdv = sum(a[y][f"sum_pred_{key}_dec2025"] for y in ys)
                if o370 <= 0 or pdv <= 0:
                    continue
                r_obs, r_pred = o245 / o370, pf / pdv
                n370 = sum(b[y]["n"] for y in ys)
                # v3 fix of a degenerate statistic (found on the first full run, AMENDMENT): the SE is taken UNDER THE
                # KERNEL (expected ssp245 count E245 = R_pred o370 n245), and a cell is testable only with >= 10
                # expected ssp245 events and >= 10 ssp370 events; otherwise it is reported as untestable, not failed
                e245 = r_pred * o370 * n245
                k370 = sum(b[y][f"n_obs_{key}"] for y in ys)
                testable = e245 >= 10 and k370 >= 10
                se = r_pred * math.sqrt(1.0 / max(e245, 1e-12) + 1.0 / max(k370, 1e-12))
                ok = abs(r_pred - r_obs) <= max(TRAIT_REL_TOL * r_obs, 3 * se) if testable else None
                contrast.append({"pair": f"{m} vs {m370}", "Type": k, "trait": key, "n_ssp245": n245, "n_ssp370": n370,
                                 "obs_ssp245_feb": o245, "obs_ssp370_dec_reweighted": o370, "R_obs": r_obs,
                                 "R_pred": r_pred, "se_R_under_kernel": se, "expected_events_ssp245": e245,
                                 "events_ssp370": k370, "testable": testable, "pass": ok})
    rep["trait_build_contrast"] = contrast
    if contrast:
        G("kernel_build_contrast_matched_y_est", all(c["pass"] for c in contrast if c["testable"]),
          "; ".join(f"{c['pair'].split('_ssp245_')[0]} T{c['Type']} {c['trait']}: R_obs {c['R_obs']:.3f} (feb {c['obs_ssp245_feb']:.4f} / "
                    f"dec {c['obs_ssp370_dec_reweighted']:.4f}) R_pred {c['R_pred']:.3f} "
                    f"{('ok' if c['pass'] else 'FAIL') if c['testable'] else 'untestable (E245 %.1f, k370 %d)' % (c['expected_events_ssp245'], c['events_ssp370'])}"
                    for c in contrast))
    # two verdicts per PFT. (1) VISIBLE-SHARE: every per-PFT marginal gate and every channel-free test passes.
    # (2) KERNEL (channel-free only: K1, K2, build contrast), split into tests passed within 25 % relative and tests
    # passed only through the 3-SE allowance (small samples, weak evidence).
    cf = {k: {"rel": 0, "se_only": 0, "fail": 0} for k in range(P.n_pft)}

    def _cf(k, ok, obs_, pred_):
        if not ok:
            cf[k]["fail"] += 1
        elif obs_ > 0 and abs(pred_ - obs_) <= TRAIT_REL_TOL * obs_:
            cf[k]["rel"] += 1
        else:
            cf[k]["se_only"] += 1
    for o in tr.values():
        for d in o["by_build_type"]:
            if d.get("K2_pass_C") is not None:
                _cf(d["Type"], d["K2_pass_C"], d["K2_obs_P_d95out_given_wdout"], d["K2_pred_C"])
            if d.get("K1_pass_Wooddens_C") is not None:
                for key in ("Wooddens", "D95max"):
                    _cf(d["Type"], d[f"K1_pass_{key}_C"], d[f"K1_obs_{key}"], d[f"K1_pred_{key}_C"])
    for c in contrast:
        if c["testable"]:
            _cf(c["Type"], c["pass"], c["R_obs"], c["R_pred"])
    rep["kernel_channel_free_tally_by_type"] = cf
    # summary labels (AMENDMENT: an SE-only pass of a small cell no longer downgrades a PFT whose other tests pass
    # within 25 %; the tally is reported beside the label so nothing is hidden)
    rep["kernel_consistent_types"] = sorted(k for k, v in cf.items() if v["rel"] > 0 and v["fail"] == 0)
    rep["kernel_failed_types"] = sorted(k for k, v in cf.items() if v["fail"] > 0)
    rep["visible_share_verified_types"] = sorted(k for k in range(P.n_pft) if seen[k] and verified[k])
    rep["visible_share_not_verified_types"] = sorted(k for k in range(P.n_pft) if seen[k] and not verified[k])
    rep["trait_untested_types"] = sorted(k for k in range(P.n_pft) if not seen[k] and sum(cf[k].values()) == 0)
    log("inherit_traits KERNEL consistent (channel-free):", rep["kernel_consistent_types"], "tally", cf,
        "failed:", rep["kernel_failed_types"], "| VISIBLE-share verified:",
        rep["visible_share_verified_types"], "not:", rep["visible_share_not_verified_types"], "| untested:", rep["trait_untested_types"])
    rep["traits"] = tr
    allpass = all(g["pass"] for g in gates)
    json.dump({"item": "SH2", "all_pass": allpass, "n": len(gates), "n_pass": sum(g["pass"] for g in gates),
               "gates": gates}, open(os.path.join(OUT, "_gates.json"), "w"), indent=1)
    json.dump(rep, open(os.path.join(OUT, "_report.json"), "w"), indent=1, default=float)
    log("GATES", "ALL PASS" if allpass else "SOME FAIL", f"{sum(g['pass'] for g in gates)}/{len(gates)}")
    return allpass


def stage_census():
    """Robustness, not a pre-registered gate: the mortality battery on every USABLE dev member-window (16 of 40;
    the 24 late-century windows are excluded by the owner decision of 2026-10-01 and not read), plus the
    per-member censoring counts SH3 needs (critic gap 8). -> shared/rules/census_members.parquet"""
    os.makedirs(OUT, exist_ok=True)
    P = load_params()
    mem, _, _, _ = _registry()
    rows = []
    only = os.environ.get("SH2_CENSUS_ONLY")
    ex = excluded_members()
    for m in sorted(mem["member"].to_list()):
        if m in ex:  # owner decision 2026-10-01: not read
            continue
        if only and m not in only.split(","):
            continue
        o = _gate_mortality(m, P, {})
        flat = {k: v for k, v in o.items() if not isinstance(v, dict)}
        for k, v in o["censor_G_counts"].items():
            flat[f"censor_G_{k}"] = v
        for k, v in o["hard_reason_counts"].items():
            flat[f"hard_{k}"] = v
        rows.append(flat)
        log("census", m, {k: flat[k] for k in ("n_tree_rows", "recursion_fail", "recursion_pairs", "forbidden_band_n",
                                                "mortsum_n_print_violations", "censor_G_G_low", "censor_G_npp_sat",
                                                "censor_W_count", "morttemp_max_abs_err")})
        pl.DataFrame(rows).write_parquet(os.path.join(OUT, "census_members.parquet"))
    return rows


def main(argv):
    st = argv[1] if len(argv) > 1 else "all"
    if st in ("params", "all"):
        stage_params()
    if st in ("selftest",):
        stage_selftest()
    if st in ("allometry", "all"):
        stage_allometry()
    if st in ("gates", "all"):
        stage_gates()
    if st in ("census",):
        stage_census()
    log("SH2 DONE stage", st)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
