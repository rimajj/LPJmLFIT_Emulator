#!/usr/bin/env python3
"""Serve LPJmL-FIT's OWN recorded demography back to it through the rung-2
substitution hook (line M, ADR 0061 + the read-back half).

Why this exists
---------------
The substitution hook (``include/rung2apply.h``, ``LPJ_RUNG2_APPLY_DIR``) lets an
external demography decide who dies and who establishes.  Before any emulator is
plugged into it, the harness has to be measured against the one decision whose
right answer is known: **the C's own**.  This script reads a roster dump produced
by the observation hook (``LPJ_RUNG2_DIR``) and replays, patch-year by patch-year,
exactly the kill set and recruit set the C chose in that run.

What a replay run does and does NOT reproduce
---------------------------------------------
It does **not** reproduce the run bit-for-bit, and that is expected, not a bug:

* the substituted recruit path skips the C's own Poisson draw and its
  inheritance-channel draws and does its own ``addpft`` draws instead, so the
  per-cell RAND48 stream position diverges the moment the first recruit appears;
* a recruit carries seven sampled trait axes, and the interface substitutes four
  (SLA, wood density, D95max, minwscal).  ``emax``, ``k_root`` and ``beta_2``
  keep the C's own uniform draw, so they differ from the recorded recruit even
  when the substituted four match exactly.

So the replay measures the harness's **intrinsic divergence** — how fast a run
separates from the recorded one while being fed that run's own answers.  That is
the noise floor every later rung-2 arm has to be read against: a substituted
demography cannot be credited with a difference smaller than this.

Because the trajectories separate, a recorded kill set names trees that no longer
exist in the live roster.  The harness intersects the recorded set with the roster
the C actually presents (an unmatched kill is a fatal error on the C side by
design) and logs both counts — that intersection shortfall is the divergence
measurement.

Usage
-----
    python3 rung2_replay_harness.py --dump <LPJ_RUNG2_DIR of a recorded run> \
                                    --apply-dir <LPJ_RUNG2_APPLY_DIR> \
                                    [--log <path>] [--max-idle 600]

Run it in the background of the same job as the substituted lpjml.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import time

REQ_RE = re.compile(r"req_r(\d+)_y(\d+)_p(\d+)\.ready$")


def parse_dump(path: str):
    """Read a roster dump into {(year, patch): {phase: [...]}} for all three phases.

    The dump is self-describing: the '#H T ...' line carries the column names, so
    nothing here hard-codes the 49-field schema.
    """
    cols = None
    out: dict[tuple[int, int], dict[str, list[dict]]] = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H T "):
                cols = line.split()[2:]
                continue
            if line[0] != "T":
                continue
            if cols is None:
                sys.exit(f"FATAL: {path}: a T record before its '#H T' header")
            f = line.split()[1:]
            if len(f) != len(cols):
                sys.exit(f"FATAL: {path}: T record has {len(f)} fields, header says {len(cols)}")
            rec = dict(zip(cols, f))
            key = (int(rec["year"]), int(rec["patch"]))
            out.setdefault(key, {"pre": [], "mort": [], "post": []})[rec["phase"]].append(rec)
    return out


def derive_decisions(dump: dict):
    """Kill set and recruit set per patch-year, from the C's own rosters.

    Dead trees are deleted at the end of iterateyear (after outputs), so a row
    with isdead==1 is a death of THAT year; a `post` row with age==0 is a recruit
    of that year (annual_tree increments age for everything that was already
    there).

    KILLS COME FROM THE `mort` PHASE, NOT `post` — this is load-bearing (ADR 0120
    §5's open question, resolved).  The interface owns the demographic hazards
    (mortality_tree_ind, the allocation kill, the bioclimatic !survive), all of
    which are settled by the time `mort` is dumped.  FIRE runs after that and is
    a disturbance the C keeps, but it also sets isdead, so a kill set read off
    `post` silently contains fire's victims.  Replaying those as demographic
    kills is wrong twice over: the interface claims a death it does not own, and
    because fire_tree_ind() draws erand48 ONLY for trees that are not already
    dead (short-circuit &&), pre-killing fire's victim changes how many draws
    fire consumes and moves the whole per-cell random stream.  Measured on the
    `post` basis: the first patch-year with kills (2002, patch 2) diverged from a
    provably identical state, and the arm ended 1.37x denser at 20 years.
    """
    decisions = {}
    for key, phases in sorted(dump.items()):
        pre, mort, post = phases["pre"], phases["mort"], phases["post"]
        if not mort:
            sys.exit(
                f"FATAL: year {key[0]} patch {key[1]}: no `mort` phase in the dump. "
                "This dump predates the pre-fire phase; re-record it with the current "
                "binary (MODE=record bash scripts/run_rung2_replay_arm.sh)."
            )
        kills, recruits = [], []
        for r in mort:
            if int(r["isdead"]):
                kills.append((int(r["pft_id"]), int(r["treeidx"])))
        for r in post:
            if int(r["age"]) == 0:
                recruits.append(
                    (
                        int(r["pft_id"]),
                        float(r["sla"]),
                        float(r["wooddens"]),
                        float(r["D95max"]),
                        float(r["minwscal"]),
                    )
                )
        pre_keys = {(int(r["pft_id"]), int(r["treeidx"])) for r in pre}
        post_keys = {(int(r["pft_id"]), int(r["treeidx"])) for r in post}
        rec_keys = {(int(r["pft_id"]), int(r["treeidx"])) for r in post if int(r["age"]) == 0}
        # the accounting the observation gate already proved; assert it here too so
        # a malformed dump cannot quietly become a wrong replay
        if post_keys - rec_keys != pre_keys:
            sys.exit(
                f"FATAL: year {key[0]} patch {key[1]}: post-minus-recruits "
                f"({len(post_keys - rec_keys)}) is not the pre roster ({len(pre_keys)})"
            )
        # every kill must name a tree of the pre roster, or the phase pairing is wrong
        stray = set(kills) - pre_keys
        if stray:
            sys.exit(
                f"FATAL: year {key[0]} patch {key[1]}: {len(stray)} `mort`-phase kill(s) "
                "name trees absent from the pre roster"
            )
        decisions[key] = {"kills": kills, "recruits": recruits, "n_pre": len(pre_keys)}
    return decisions


def read_request_roster(path: str):
    """The (pft_id, treeidx) set the C is actually presenting this patch-year."""
    cols, keys = None, set()
    with open(path) as fh:
        for line in fh:
            if line.startswith("#H T "):
                cols = line.split()[2:]
                continue
            if line[0] != "T":
                continue
            rec = dict(zip(cols, line.split()[1:]))
            keys.add((int(rec["pft_id"]), int(rec["treeidx"])))
    return keys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump", required=True, help="LPJ_RUNG2_DIR of the RECORDED observation run")
    ap.add_argument("--apply-dir", required=True, help="LPJ_RUNG2_APPLY_DIR of the substituted run")
    ap.add_argument("--log", default=None, help="per-patch-year divergence log (default: <apply-dir>/replay_log.txt)")
    ap.add_argument(
        "--mode",
        choices=("both", "kills", "recruits", "none"),
        default="both",
        help="which half of the interface to substitute; the other half is deferred back to the C. "
        "Running 'kills' and 'recruits' separately is what makes a divergence attributable; "
        "'none' defers BOTH and is the null control — it must reproduce the recorded run exactly, "
        "which is what proves the rendezvous itself perturbs nothing.",
    )
    ap.add_argument("--max-idle", type=float, default=600.0, help="exit after this many idle seconds")
    ap.add_argument("--poll", type=float, default=0.002, help="seconds between directory scans")
    args = ap.parse_args()

    dumps = sorted(glob.glob(os.path.join(args.dump, "roster_rank*.txt")))
    if not dumps:
        sys.exit(f"FATAL: no roster_rank*.txt under {args.dump}")
    decisions: dict = {}
    for d in dumps:
        decisions.update(derive_decisions(parse_dump(d)))
    print(f"harness: {len(decisions)} recorded patch-years from {len(dumps)} dump file(s)", flush=True)

    os.makedirs(args.apply_dir, exist_ok=True)
    log_path = args.log or os.path.join(args.apply_dir, "replay_log.txt")
    log = open(log_path, "w")
    log.write("#H L year patch n_pre_live n_pre_recorded n_kill_recorded n_kill_served n_recruit\n")

    served: set[str] = set()
    last_seen = time.time()
    while time.time() - last_seen < args.max_idle:
        hits = 0
        for ready in sorted(glob.glob(os.path.join(args.apply_dir, "req_r*_y*_p*.ready"))):
            m = REQ_RE.search(os.path.basename(ready))
            if m is None or ready in served:
                continue
            rank, year, patch = (int(x) for x in m.groups())
            req_txt = ready[: -len(".ready")] + ".txt"
            if not os.path.exists(req_txt):
                continue
            live = read_request_roster(req_txt)
            dec = decisions.get((year, patch))
            if dec is None:
                sys.exit(f"FATAL: no recorded decision for year {year} patch {patch}")
            # the recorded kill set may name trees this trajectory no longer has
            kills = [k for k in dec["kills"] if k in live]
            base = os.path.join(args.apply_dir, f"rsp_r{rank:04d}_y{year:05d}_p{patch:03d}")
            with open(base + ".txt", "w") as fh:
                fh.write(f"# replay of the recorded C decision, year {year} patch {patch}\n")
                if args.mode in ("recruits", "none"):
                    fh.write("MORT_C\n")       # who dies stays with the C
                else:
                    for pft_id, treeidx in kills:
                        fh.write(f"K {pft_id} {treeidx}\n")
                if args.mode in ("kills", "none"):
                    fh.write("ESTAB_C\n")      # who establishes stays with the C
                else:
                    for pft_id, sla, wd, d95, mws in dec["recruits"]:
                        fh.write(f"R {pft_id} {sla!r} {wd!r} {d95!r} {mws!r}\n")
                fh.write("END\n")
            open(base + ".ready", "w").close()
            log.write(
                f"L {year} {patch} {len(live)} {dec['n_pre']} "
                f"{len(dec['kills'])} {len(kills)} {len(dec['recruits'])}\n"
            )
            log.flush()
            served.add(ready)
            hits += 1
        if hits:
            last_seen = time.time()
        else:
            time.sleep(args.poll)
    log.close()
    print(f"harness: served {len(served)} patch-years, log -> {log_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
