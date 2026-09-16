#!/usr/bin/env python3
"""check_edge_joins_measured — an edge's join predicate is a CLAIM about two relations. Measure it.

WHAT AN EDGE'S PREDICATE ASSERTS. `join_rule: a.x = b.y` with `cardinality: "1"` on the far endpoint
says two measurable things at once: every value of `a.x` finds a partner in `b.y` (CONTAINMENT), and
it finds at most one (FANOUT). Both are countable. Neither was ever counted.

WHY check_edge_claims_proved IS NOT THIS GATE. That one reads the verdict of an expectation a human
cited in `verified_by`. It is correct and it is a bottleneck: evidence exists only where somebody
wrote a test, which is why one edge of thirty-two carried any. This gate needs no author. It reads
the predicate the edge already declares and measures the two numbers the cardinality already claims,
so evidence becomes GENERATED rather than authored.

THE FAILURE THAT FORCED IT. A composed protosql fragment rendered cleanly, resolved every slot, was
refused by nothing, and returned zero rows: its join matched 0 of 206 values while the correct column
matched 578 of 578. Both columns existed and were correctly typed. A predicate that resolves nothing
is indistinguishable, at render time, from one that resolves everything — until someone counts.

WHAT IT REFUSES TO DO. It does not judge an edge that declares no predicate; that absence is a
different finding and belongs to the realisation vocabulary, not here. It does not treat partial
containment as a defect on an endpoint whose cardinality permits it — `0..1` means AT MOST one, and
reading it as EXACTLY one would manufacture failures out of correctly-modelled optional links. What
it refuses is a declared cardinality the data contradicts, and a declared predicate nobody measured.

MEASUREMENT IS SEPARATE, DELIBERATELY. The counting needs a warehouse; the judging must not. The
rule below is pure, so it is mutant-tested offline in full, the way every other rule in this estate
is. The gate reads what a measurement run recorded, exactly as the suite gates read run records.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D  # noqa: E402

UNRESOLVED = "predicate-resolves-nothing"
FANOUT = "fanout-contradicts-cardinality"
UNMEASURED = "predicate-unmeasured"

# An endpoint cardinality is a promise about how many partners a row finds.
#   "1"    exactly one   -> every key must resolve AND find at most one
#   "0..1" at most one   -> may resolve nothing; must never find two
#   "0..N" any number    -> promises nothing, so nothing can contradict it
EXACTLY_ONE = {"1"}
AT_MOST_ONE = {"1", "0..1"}

PREDICATE = re.compile(r"^\s*([\w.]+)\.(\w+)\s*=\s*([\w.]+)\.(\w+)\s*$")


def judge(rows: list[dict]) -> list[tuple[str, str]]:
    """PURE: [{edge, to_card, lhs, matched, fanout, measured}] -> [(reject_class, sentence)].

    Free of the filesystem and of the warehouse so the rule can be exercised in full without
    either — an instrument that can only be tested by the thing it inspects cannot be shown to work.
    """
    out: list[tuple[str, str]] = []
    for r in rows:
        edge, card = r["edge"], str(r.get("to_card") or "")
        if not r.get("measured"):
            out.append(
                (
                    UNMEASURED,
                    f"{edge}: declares a join predicate that no measurement covers — the "
                    f"cardinality {card!r} stands unexamined and cannot be relied on to render",
                )
            )
            continue
        lhs, matched, fan = int(r.get("lhs") or 0), int(r.get("matched") or 0), int(r.get("fanout") or 0)
        if card in EXACTLY_ONE and lhs and matched < lhs:
            pct = 100.0 * matched / lhs
            out.append(
                (
                    UNRESOLVED,
                    f"{edge}: declares {card!r} — EXACTLY one partner per row — but only "
                    f"{matched} of {lhs} distinct key(s) resolve ({pct:.1f}%). "
                    f"{lhs - matched} key(s) join to nothing.",
                )
            )
        if card in AT_MOST_ONE and fan > 1:
            out.append(
                (
                    FANOUT,
                    f"{edge}: declares {card!r} — at most one partner per row — but one key "
                    f"matches {fan} rows. Every fact row joining that key is multiplied {fan}x.",
                )
            )
    return out


def _load(p: pathlib.Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    if "--self-test" in sys.argv[1:]:
        return self_test()
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()

    edges_file = root / "ontology" / "edges.yaml"
    if not edges_file.exists():
        return D.refuse_empty("check_edge_joins_measured", edges_file, unit="edge")
    edges = _load(edges_file).get("edges") or []
    if not edges:
        return D.refuse_empty("check_edge_joins_measured", edges_file, unit="edge")

    # THE MEASUREMENT RECORD, written by a run that had a warehouse. Its absence is not a pass:
    # a gate that reports green because nobody measured is the empty-denominator defect wearing a
    # gate's clothes, and this estate has shipped that five times.
    rec = root / "evidence" / "edge_measurements.json"
    measured: dict[str, dict] = {}
    if rec.exists():
        try:
            for m in json.loads(rec.read_text(encoding="utf-8")).get("results") or []:
                measured[str(m.get("edge"))] = m
        except Exception as e:  # noqa: BLE001
            print(f"FAIL: check_edge_joins_measured — {rec.name} unreadable: {str(e)[:90]}")
            return 1

    declaring, realised_otherwise, unrealised = [], [], []
    for e in edges:
        eid = str(e.get("edge_id"))
        pred = e.get("join_rule")
        if not isinstance(pred, str) or not pred.strip():
            # NOT ALL PREDICATE-LESS EDGES ARE THE SAME, and reporting them as one number was this
            # gate's own version of the defect it exists to catch. An edge may declare its
            # realisation as `resolved_by` (a rule or transform resolves it) or `realized_by` (a
            # column carries it) — those are DECLARED, just not as a join. An edge declaring none
            # of the three is the only real hole.
            if e.get("resolved_by") or e.get("realized_by"):
                realised_otherwise.append(eid)
            else:
                unrealised.append(eid)
            continue
        ep = e.get("endpoints") or {}
        m = measured.get(eid) or {}
        declaring.append(
            {
                "edge": eid,
                "to_card": (ep.get("to") or {}).get("cardinality"),
                "lhs": m.get("lhs"),
                "matched": m.get("matched"),
                "fanout": m.get("fanout"),
                "measured": bool(m),
                "predicate": pred,
            }
        )

    if not declaring:
        return D.refuse_empty("check_edge_joins_measured", edges_file, unit="declared predicate")

    findings = judge(declaring)
    # HOLDING = measured AND named by no finding. Computed from the edge ids the judge reported,
    # not by searching its prose — a substring test against a sentence is the same guess-instead-of-
    # dereference this gate exists to end.
    faulted = {r["edge"] for r in declaring if any(m.startswith(r["edge"] + ":") for _, m in findings)}
    held = [r for r in declaring if r["measured"] and r["edge"] not in faulted]

    if a.json:
        print(
            json.dumps(
                {
                    "edges": len(edges),
                    "declaring": len(declaring),
                    "measured": sum(1 for r in declaring if r["measured"]),
                    "realised_otherwise": realised_otherwise,
                    "unrealised": unrealised,
                    "findings": [{"class": k, "msg": m} for k, m in findings],
                },
                indent=1,
            )
        )
        return 1 if findings else 0

    for k, m in findings:
        print(f"  [{k}] {m}")
    # REPORTED, NEVER FAILED. An edge with no predicate is a REALISATION question — is none needed,
    # or has nobody worked it out? Those are different states and this gate cannot tell them apart,
    # so it counts them and says so rather than guessing.
    if realised_otherwise:
        print(
            f"  [realised-not-joined] {len(realised_otherwise)} edge(s) declare no join_rule "
            f"because a join is not how they are realised — they carry resolved_by or "
            f"realized_by, and this gate has nothing to measure on them"
        )
    if unrealised:
        print(
            f"  [unrealised] {len(unrealised)} edge(s) declare NO realisation at all — not a join, "
            f"not a rule, not a column. Nobody has said how this relationship is reached: "
            f"{', '.join(unrealised[:6])}{' …' if len(unrealised) > 6 else ''}"
        )
    n_meas = sum(1 for r in declaring if r["measured"])
    tail = (
        f"{n_meas} of {len(declaring)} declared predicate(s) measured over {len(edges)} edge(s); "
        f"{len(held)} holding, {len(realised_otherwise)} realised without a join, "
        f"{len(unrealised)} with no realisation at all"
    )
    if findings:
        print(f"FAIL: check_edge_joins_measured — {len(findings)} contradicted claim(s) — {tail}")
        return 1
    print(f"PASS: check_edge_joins_measured — {tail}")
    return 0


def self_test() -> int:
    """One mutant per way a declared join can be false, and the controls that stop over-firing."""
    def row(**kw):
        base = {"edge": "a__of_b", "to_card": "1", "lhs": 100, "matched": 100,
                "fanout": 1, "measured": True}
        base.update(kw)
        return base

    cases = [
        ("a predicate that holds is not a finding", [row()], 0),
        # THE MEASURED DEFECT: a join matching nothing, which renders as an empty result.
        ("exactly-one with keys that resolve to nothing", [row(matched=0)], 1),
        ("exactly-one with partial containment", [row(matched=99)], 1),
        # THE OTHER MEASURED DEFECT: the 215x fanout that multiplied every fact row.
        ("at-most-one with a key matching many rows", [row(fanout=215)], 1),
        ("0..1 still forbids a second partner", [row(to_card="0..1", matched=40, fanout=2)], 1),
        ("both wrong reports both, not one", [row(matched=0, fanout=7)], 2),
        ("a declared predicate nobody measured", [row(measured=False)], 1),
        # NEGATIVE CONTROLS — each is a correctly-modelled shape that must NOT fire.
        ("0..1 permits resolving nothing", [row(to_card="0..1", matched=0, fanout=1)], 0),
        ("0..N promises nothing and cannot be contradicted",
         [row(to_card="0..N", matched=3, fanout=99)], 0),
        ("an empty population is not a finding", [], 0),
    ]
    bad = 0
    for name, rows, want in cases:
        got = len(judge(rows))
        if got != want:
            bad += 1
            print(f"  [SELF-TEST FAIL] {name}: {got} finding(s), expected {want}")
    n = len(cases)
    print(
        f"{'PASS' if not bad else 'FAIL'}: check_edge_joins_measured self-test — {n - bad}/{n} "
        f"case(s): 6 mutant(s) of the rule (resolves nothing, partial containment, fanout on '1', "
        f"fanout on '0..1', both at once, unmeasured) and 4 negative control(s) (a holding "
        f"predicate, optional links that resolve nothing, an unconstrained endpoint, empty)"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
