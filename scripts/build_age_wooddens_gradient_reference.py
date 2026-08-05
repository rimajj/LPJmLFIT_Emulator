#!/usr/bin/env python3
"""Emit THE committed per-PFT AGE-WOODDENS GRADIENT — the acceptance target for the ported hazard.

WHY THIS ARTIFACT EXISTS. ADR 0046 §3 identified FIT's mean-survivor-``Wooddens``-by-Age-bin gradient as
the **ID-free validation target** for a trait-dependent mortality operator: traits are immutable after
``new_tree`` (ADR 0045), so a trait mean that RISES with age can only be cumulative differential
survival. ADR 0046 published five rows of that table in prose and left no artifact, so a Stage-2 arm
had nothing to score against; the handoff (line S, item B) asks for the fixture first. This is it.

WHAT MAKES IT THE RIGHT TARGET, and the trap it is written against. The gradient is **not** monotone in
every PFT. ADR 0046 §3 measures the one-year selection differential
``S = mean(Wooddens|live) - mean(Wooddens|all)`` as NEGATIVE for ids 0 and 3 and positive for 1/2/4/6,
because denser wood halves ``mort_max`` (``mortality_tree_ind.c:92``) but grows more slowly, lowering
``greff`` and RAISING ``mort_npp`` through the logistic — net selection is a competition between the two
and is not sign-definite. So an operator that produces a rising gradient in all seven PFTs has got ids 0
and 3 backwards and is WRONG even if its community-mean response looks right. The emitted
``shape``/``argmax_bin`` columns are what make that failure mode checkable instead of arguable.

BASIS (stated because a mis-stated basis is this line's most expensive recurring error — guardrail 6/7).
Committed seed1 ``ind`` parquets, ``Type`` in the imported ``TREE_TYPES`` (never re-declared — ADR 0031),
survivors only (``isdead == 0``), **no** stem-count filter, FIXED age-bin edges. That is byte-for-byte
``diagnose_wooddens_shift_decomposition.py::age_gradient``'s basis, which is what produced the ADR 0046
§3 numbers — and this script ASSERTS those five published rows reproduce, so the fixture is provably the
ADR's target rather than a second, silently different measurement of it. Three further basis facts that
are properties of the DATA, not choices made here:

  * the ``ind`` writer emits only stems ``height > 5 m`` (``fwriteoutput_ind.c:84``), so the first bin is
    already post-establishment — its mean is the closest OBSERVABLE proxy for the entry marginal, not
    the entry marginal itself;
  * ``Age`` is the POST-increment year-end age (CLAUDE.md §3). The bins are therefore in emitted-``Age``
    units. A hazard recomputed from ``Age - 1`` must still be BINNED on the emitted ``Age`` to compare;
  * the TXT writer's ``%g`` gives 6 significant digits, so nothing inverted from these columns is
    meaningful below ~1e-5 relative.

Both scenarios are emitted. ``historic`` is the acceptance target; ``ssp370`` is there because the whole
point of Phase 3A is a RESPONSE, and the per-PFT change in the gradient is the response's fingerprint
(ADR 0046: ``ΔS`` is positive for 4 of 7 PFTs, largest for id 0 at +450.3).

Usage:
    NCPUS=96 TIME=02:00:00 scripts/sbatch_python.sh S-agegrad \\
        scripts/build_age_wooddens_gradient_reference.py
    CHECK=1 python3 scripts/build_age_wooddens_gradient_reference.py   # regenerate + diff, exit 1 on drift
Env: SEED (1), OUT (the committed reference path), SCENARIOS ("historic,ssp370").
"""

from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

import polars as pl

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "python" / "src"))
from lpjmlfit_emulator.data import TREE_TYPES  # noqa: E402  -- single source of truth (ADR 0031)

IND = {
    "historic": "/p/tmp/jamirp/emulator_global/ind_hist_seed{seed}_all.parquet",
    "ssp370": "/p/tmp/jamirp/emulator_global/ind_ssp370_seed{seed}_all.parquet",
}
SEED = int(os.environ.get("SEED", "1"))
SCENARIOS = [s.strip() for s in os.environ.get("SCENARIOS", "historic,ssp370").split(",") if s.strip()]
OUT = Path(
    os.environ.get(
        "OUT", _REPO / "test" / "testitems" / "references" / "S_age_wooddens_gradient.csv"
    )
)

#: FIXED age-bin edges (years), identical to ``diagnose_wooddens_shift_decomposition.py::AGE_EDGES``.
#: Fixed, not quantile, for two reasons: a global ``rank().over("Type")`` over ~1e9 rows will not stream,
#: and fixed edges make the two scenario blocks comparable bin-by-bin, which quantile bins would not be.
AGE_EDGES = [10.0, 20.0, 40.0, 80.0, 160.0, 320.0]

COLS = [
    "scenario", "pft_id", "agebin", "age_lo", "age_hi", "n",
    "age_mean", "wooddens_mean", "wooddens_median", "sla_mean", "sla_median",
]


def bin_bounds(b: int) -> tuple[float, float]:
    """``[lo, hi)`` of bin id ``b``; the last bin is open-ended (``hi = inf``)."""
    lo = 0.0 if b == 0 else AGE_EDGES[b - 1]
    hi = AGE_EDGES[b] if b < len(AGE_EDGES) else float("inf")
    return lo, hi


def assert_unique(df: pl.DataFrame, keys: list[str], what: str) -> pl.DataFrame:
    """ADR 0036 §5b guard: ``collect(engine="streaming")`` is not deterministic in the KEY SET it emits
    at global scale (whole groups appeared AND duplicated across two runs of the same aggregation), and
    the usual ``rows_before - rows_after`` coverage check cannot see it because duplication makes that
    statistic go negative. A duplicated ``(Type, agebin)`` here would silently re-weight a bin mean."""
    nu = df.select(keys).n_unique()
    if nu != df.height:
        raise SystemExit(
            f"FATAL: {what} emitted {df.height} rows for {nu} unique {keys} "
            f"({df.height - nu} duplicated) -- polars streaming key-set nondeterminism "
            f"(ADR 0036 §5b). Re-run; do NOT interpret this output."
        )
    return df


def gradient(scenario: str) -> pl.DataFrame:
    path = IND[scenario].format(seed=SEED)
    print(f"\n== {scenario}: scanning {path}", flush=True)
    df = (
        pl.scan_parquet(path)
        .filter(pl.col("Type").is_in(TREE_TYPES) & (pl.col("isdead") == 0))
        # bin id as a SUM OF THRESHOLD INDICATORS so it is a sortable integer with no join
        .with_columns(sum((pl.col("Age") >= e).cast(pl.Int32) for e in AGE_EDGES).alias("agebin"))
        .group_by(["Type", "agebin"])
        .agg(
            pl.len().alias("n"),
            pl.col("Age").mean().alias("age_mean"),
            pl.col("Wooddens").mean().alias("wooddens_mean"),
            pl.col("Wooddens").median().alias("wooddens_median"),
            pl.col("SLA").mean().alias("sla_mean"),
            pl.col("SLA").median().alias("sla_median"),
        )
        .collect(engine="streaming")
    )
    assert_unique(df, ["Type", "agebin"], f"{scenario} age gradient")
    return df.sort(["Type", "agebin"])


def build_rows() -> list[dict]:
    rows: list[dict] = []
    for sc in SCENARIOS:
        df = gradient(sc)
        for r in df.iter_rows(named=True):
            lo, hi = bin_bounds(int(r["agebin"]))
            rows.append(
                {
                    "scenario": sc,
                    "pft_id": int(r["Type"]),
                    "agebin": int(r["agebin"]),
                    "age_lo": lo,
                    "age_hi": hi,
                    "n": int(r["n"]),
                    "age_mean": float(r["age_mean"]),
                    "wooddens_mean": float(r["wooddens_mean"]),
                    "wooddens_median": float(r["wooddens_median"]),
                    "sla_mean": float(r["sla_mean"]),
                    "sla_median": float(r["sla_median"]),
                }
            )
    check_against_adr(rows)
    return rows


def shape(rows: list[dict], scenario: str, pft: int) -> dict:
    """Per-PFT gradient SHAPE — the part of the target an operator can get backwards.

    ``delta`` is last bin minus first; ``argmax_bin`` is where the mean PEAKS; ``monotone`` is whether
    the bin means rise weakly monotonically. ADR 0046 §3: ids 1/4/6 are steeply monotone, ids 0 and 3
    are non-monotone (rise then fall) because their one-year selection differential is NEGATIVE.
    """
    seq = sorted(
        (r for r in rows if r["scenario"] == scenario and r["pft_id"] == pft),
        key=lambda r: r["agebin"],
    )
    w = [r["wooddens_mean"] for r in seq]
    return {
        "pft_id": pft,
        "nbin": len(w),
        "first": w[0],
        "last": w[-1],
        "delta": w[-1] - w[0],
        "argmax_bin": seq[int(max(range(len(w)), key=lambda i: w[i]))]["agebin"],
        "monotone": all(b >= a for a, b in zip(w, w[1:])),
        "n_total": sum(r["n"] for r in seq),
    }


#: ADR 0046 §3's published table (historic, mean survivor ``Wooddens`` in the ``<10`` and ``≥320`` bins).
#: Asserted, not restated: if this fixture does not reproduce the ADR it is a SECOND measurement of the
#: target rather than the target, and every Stage-2 verdict scored against it would be unmoored from the
#: decision record. Tolerance is 1 gC/m³ — the ADR quotes integers.
ADR_0046_S3 = {
    1: (184869.0, 331234.0),
    4: (146894.0, 288121.0),
    6: (138072.0, 268630.0),
    3: (217954.0, 262019.0),
    0: (240708.0, 263347.0),
}


def check_against_adr(rows: list[dict]) -> None:
    if "historic" not in SCENARIOS:
        print("\n== ADR 0046 §3 cross-check SKIPPED (historic not in SCENARIOS)")
        return
    print("\n== cross-check against ADR 0046 §3 (historic, `<10` and `>=320` bin means)")
    nbin = len(AGE_EDGES) + 1
    for pft, (exp_first, exp_last) in sorted(ADR_0046_S3.items()):
        sh = shape(rows, "historic", pft)
        assert sh["nbin"] == nbin, (
            f"pft {pft}: {sh['nbin']} age bins, expected {nbin} — AGE_EDGES changed, so this fixture "
            f"is no longer on ADR 0046 §3's basis. Update the ADR cross-check deliberately."
        )
        ok = abs(sh["first"] - exp_first) < 1.0 and abs(sh["last"] - exp_last) < 1.0
        print(
            f"   id {pft}: {sh['first']:>10.1f} -> {sh['last']:>10.1f}   ADR "
            f"{exp_first:>10.1f} -> {exp_last:>10.1f}   {'OK' if ok else 'MISMATCH'}"
        )
        assert ok, (
            f"pft {pft}: gradient endpoints ({sh['first']:.1f}, {sh['last']:.1f}) disagree with ADR "
            f"0046 §3 ({exp_first}, {exp_last}) by more than 1 gC/m³. Either the parquet changed or "
            f"this basis is not the ADR's (survivors only, no MINSTEM, seed1, fixed AGE_EDGES). "
            f"Do NOT widen the tolerance — the whole value of the fixture is that it IS the ADR's target."
        )
    # the SHAPE claim, which is the half of the target an operator can get backwards
    for pft in (1, 4, 6):
        if pft in {r["pft_id"] for r in rows}:
            assert shape(rows, "historic", pft)["monotone"], (
                f"ADR 0046 §3 records pft {pft} as steeply MONOTONE (S > 0); it is not in this build."
            )
    for pft in (0, 3):
        if pft in {r["pft_id"] for r in rows}:
            assert not shape(rows, "historic", pft)["monotone"], (
                f"ADR 0046 §3 records pft {pft} as NON-monotone (its one-year selection differential is "
                f"negative); it is monotone in this build. That is the exact distinction a ported "
                f"hazard is scored on, so it must not be quietly lost."
            )


def render(rows: list[dict]) -> str:
    buf = io.StringIO()
    buf.write(
        "# S_age_wooddens_gradient.csv — the per-PFT AGE-WOODDENS GRADIENT of LPJmL-FIT, the ID-free\n"
        "# acceptance target for the ported trait-dependent mortality hazard (ADR 0046 §3 / ADR 0047).\n"
        "# GENERATED — do not hand-edit.\n"
        "#   regenerate: NCPUS=96 scripts/sbatch_python.sh S-agegrad \\\n"
        "#                   scripts/build_age_wooddens_gradient_reference.py\n"
        "#   verify:     CHECK=1 python3 scripts/build_age_wooddens_gradient_reference.py\n"
        "# BASIS: seed1 `ind` parquets, `Type` in TREE_TYPES (ADR 0031), SURVIVORS only (isdead == 0),\n"
        "# NO stem-count filter, fixed age-bin edges 10/20/40/80/160/320 yr. Byte-for-byte the basis of\n"
        "# `diagnose_wooddens_shift_decomposition.py::age_gradient`, which produced ADR 0046 §3 — and the\n"
        "# builder ASSERTS the five rows that ADR published still reproduce to 1 gC/m3.\n"
        "# READ IT THIS WAY, or the target is misused:\n"
        "#   * traits are IMMUTABLE after establishment (ADR 0045), so a rising bin mean is cumulative\n"
        "#     differential SURVIVAL and nothing else. That is why this is the target.\n"
        "#   * the gradient is NOT monotone in every PFT. ids 1/4/6 rise steeply; ids 0 and 3 rise then\n"
        "#     FALL, because their one-year selection differential is negative (denser wood halves\n"
        "#     mort_max but grows slower, raising mort_npp). An operator that rises everywhere has ids 0\n"
        "#     and 3 backwards and is WRONG even if its community mean response looks right.\n"
        "#   * `Age` is the emitted POST-increment year-end age; a hazard evaluated at `Age - 1`\n"
        "#     (CLAUDE.md §3) must still be BINNED on the emitted `Age` to be comparable.\n"
        "#   * the `ind` writer emits only stems > 5 m, so bin 0 is already post-establishment: it is a\n"
        "#     proxy for the entry marginal, not the entry marginal.\n"
        "#   * `age_hi = inf` marks the open-ended last bin.\n"
        f"# seed = {SEED}; scenarios = {','.join(SCENARIOS)}; historic is the acceptance target and\n"
        "# ssp370 is the RESPONSE fingerprint (ADR 0046: dS is positive for 4 of 7 PFTs, largest id 0).\n"
    )
    w = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n")
    w.writeheader()
    for r in sorted(rows, key=lambda r: (r["scenario"], r["pft_id"], r["agebin"])):
        w.writerow({c: (r[c] if isinstance(r[c], (str, int)) else repr(r[c])) for c in COLS})
    return buf.getvalue()


def main() -> int:
    print("=" * 104)
    print("S_age_wooddens_gradient — the ADR-0046 §3 acceptance target, as a committed fixture")
    print(f"     TREE_TYPES={TREE_TYPES}  SEED={SEED}  scenarios={SCENARIOS}  AGE_EDGES={AGE_EDGES}")
    print("=" * 104)
    rows = build_rows()
    text = render(rows)

    for sc in SCENARIOS:
        print(f"\n== {sc}: per-PFT gradient shape")
        print(
            "   "
            + "".join(
                x.ljust(w)
                for x, w in (
                    ("pft", 5), ("n", 12), ("first", 12), ("last", 12), ("delta", 12),
                    ("argmax_bin", 12), ("monotone", 9),
                )
            )
        )
        for pft in sorted({r["pft_id"] for r in rows if r["scenario"] == sc}):
            sh = shape(rows, sc, pft)
            print(
                "   "
                + "".join(
                    str(x).ljust(w)
                    for x, w in (
                        (sh["pft_id"], 5), (sh["n_total"], 12), (round(sh["first"], 1), 12),
                        (round(sh["last"], 1), 12), (round(sh["delta"], 1), 12),
                        (sh["argmax_bin"], 12), (sh["monotone"], 9),
                    )
                )
            )
    if len(SCENARIOS) == 2 and "historic" in SCENARIOS and "ssp370" in SCENARIOS:
        print("\n== RESPONSE fingerprint: delta(gradient) ssp370 - historic, per PFT")
        for pft in sorted({r["pft_id"] for r in rows}):
            h = shape(rows, "historic", pft)
            s = shape(rows, "ssp370", pft)
            print(
                f"   id {pft}: delta {h['delta']:>10.1f} -> {s['delta']:>10.1f}  "
                f"(change {s['delta'] - h['delta']:+.1f});  first bin "
                f"{h['first']:>10.1f} -> {s['first']:>10.1f}  ({s['first'] - h['first']:+.1f})"
            )

    if os.environ.get("CHECK"):
        if not OUT.exists():
            print(f"\nCHECK: {OUT} does not exist — run without CHECK=1 first.", file=sys.stderr)
            return 1
        old = OUT.read_text()
        if old == text:
            print(f"\nCHECK: {OUT} is up to date ({len(rows)} rows).")
            return 0
        print(f"\nCHECK: DRIFT — {OUT} differs from a fresh scan of the ind parquets.", file=sys.stderr)
        import difflib

        sys.stderr.writelines(
            difflib.unified_diff(old.splitlines(True), text.splitlines(True), "committed", "regenerated")
        )
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"\nwrote {OUT}  ({len(rows)} rows, {len(COLS)} columns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
