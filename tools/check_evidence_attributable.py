#!/usr/bin/env python3
"""check_evidence_attributable — does every `validates` name reach a concept that EXISTS?

WHAT `validates` IS FOR. An acceptance card lists the concepts it validates so that evidence can be
ATTRIBUTED: without it a suite proves the warehouse satisfies an assumption while nothing records
which part of the model was thereby validated. The list is only worth as much as its resolvability
— a name that reaches no concept attributes its evidence to nothing at all, and says so nowhere.

THE MEASURED FAILURE THAT FORCED THIS. A console pane matched `validates` against each concept's
DISPLAY TITLE instead of its declared `concept.name`. A title is written for a reader ("Net
Revenue") and a name is an identity ("NetRevenue"); the two coincide only for concepts whose label
happens to be a single word. On one bundle that was four concepts of twenty-two: those four
rendered convincing numbers while the other eighteen rendered `0 check(s) name it`. 241 of 652
attributions were visible and 411 were silently lost.

WHY A ZERO IS THE DANGEROUS OUTPUT, and why this gate exists rather than a code review. Nothing
about that page looked broken. `0 check(s) name it` is well-formed, it is what an unmeasured concept
would also render, and the two readings — "nobody has measured this" and "I looked under the wrong
name" — are opposite findings sharing one appearance. This estate has now shipped that exact shape
three times: a scorecard publishing `covered: 0 of 22` from a join empty by construction, a register
match against served ids while the register recorded raw ones, and this. A join on names fails
SILENTLY; a dereference of a declared identity fails LOUDLY. This is the dereference.

WHAT IT REFUSES TO DO. It does not require every concept to be measured — a concept nothing names
is a legitimate and reportable state, not an error, and failing it would push people to author
attributions they have not earned. What it refuses is a `validates` entry that resolves to NO
declared concept, because that entry is evidence pointed at nothing while looking like evidence
pointed at something.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D  # noqa: E402

UNRESOLVABLE = "validates-unresolvable"
NO_IDENTITY = "concept-without-identity"


def _load(p: pathlib.Path):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def declared_identities(root: pathlib.Path) -> tuple[dict[str, str], list[str]]:
    """({name: stem}, [stems with no declared name]).

    The identity is `concept.name` — the value cards use. A concept without one cannot be addressed
    by any card, so it is reported separately rather than folded into the resolvable set.
    """
    by_name: dict[str, str] = {}
    nameless: list[str] = []
    for f in sorted((root / "ontology" / "concepts").glob("*.yaml")):
        con = (_load(f).get("concept") or {})
        nm = con.get("name")
        if isinstance(nm, str) and nm.strip():
            by_name[nm.strip()] = f.stem
        else:
            nameless.append(f.stem)
    return by_name, nameless


def judge(validates: dict[str, int], identities: set[str], nameless: list[str]) -> list[tuple[str, str]]:
    """PURE: {validates_value: card_count} + declared identities -> [(class, sentence)].

    Kept free of the filesystem so the rule can be mutant-tested without a bundle on disk — an
    instrument exercisable only by the thing it inspects cannot be shown to work.
    """
    out: list[tuple[str, str]] = []
    for value, n in sorted(validates.items()):
        if value not in identities:
            near = sorted(i for i in identities if i.lower() == value.lower().replace(" ", ""))
            hint = f" Did you mean {near[0]!r}?" if near else ""
            out.append(
                (
                    UNRESOLVABLE,
                    f"{n} card(s) attribute evidence to {value!r}, which names no declared "
                    f"concept — that evidence reaches nothing.{hint}",
                )
            )
    for stem in nameless:
        out.append(
            (
                NO_IDENTITY,
                f"concept {stem!r} declares no concept.name, so no card can address it and no "
                f"count over it can be distinguished from 'never measured'.",
            )
        )
    return out


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

    cards_file = root / "acceptance" / "test_cards.json"
    if not cards_file.exists():
        return D.refuse_empty("check_evidence_attributable", cards_file, unit="card")
    try:
        cards = json.loads(cards_file.read_text(encoding="utf-8")).get("cards") or []
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: check_evidence_attributable — {cards_file.name} unreadable: {str(e)[:100]}")
        return 1
    if not cards:
        return D.refuse_empty("check_evidence_attributable", cards_file, unit="card")

    by_name, nameless = declared_identities(root)
    if not by_name and not nameless:
        return D.refuse_empty(
            "check_evidence_attributable", root / "ontology" / "concepts", unit="concept"
        )

    validates: dict[str, int] = {}
    for c in cards:
        for v in c.get("validates") or []:
            validates[str(v)] = validates.get(str(v), 0) + 1

    findings = judge(validates, set(by_name), nameless)

    # ADDRESSED vs MERELY DECLARED — reported, never failed. A concept nothing names is a real
    # state of the bundle and the number worth seeing; authoring attributions to clear a gate
    # would be the cure that causes the disease.
    addressed = {by_name[v] for v in validates if v in by_name}
    unaddressed = sorted(set(by_name.values()) - addressed)
    attributions = sum(validates.values())

    if a.json:
        print(
            json.dumps(
                {
                    "concepts": len(by_name) + len(nameless),
                    "addressed": len(addressed),
                    "unaddressed": unaddressed,
                    "attributions": attributions,
                    "findings": [{"class": k, "msg": m} for k, m in findings],
                },
                indent=1,
            )
        )
        return 1 if findings else 0

    for k, m in findings:
        print(f"  [{k}] {m}")
    if unaddressed:
        print(
            f"  [unaddressed] {len(unaddressed)} concept(s) no card names: "
            f"{', '.join(unaddressed[:6])}{' …' if len(unaddressed) > 6 else ''}"
        )
    tail = (
        f"{attributions} attribution(s) over {len(validates)} distinct name(s) resolved against "
        f"{len(by_name)} declared concept identit(ies); {len(addressed)} concept(s) addressed"
    )
    if findings:
        print(f"FAIL: check_evidence_attributable — {len(findings)} unattributable name(s) — {tail}")
        return 1
    print(f"PASS: check_evidence_attributable — {tail}")
    return 0


def self_test() -> int:
    """One mutant per way attribution can silently reach nothing, plus the controls."""
    ids = {"NetRevenue", "LineItem", "CostCentre"}
    cases = [
        ("a resolvable name is not a finding", {"NetRevenue": 28}, ids, [], 0),
        # THE MEASURED DEFECT: the display title used where the identity was required.
        (
            "a display title instead of the identity is unresolvable",
            {"Net Revenue": 28},
            ids,
            [],
            1,
        ),
        ("a spelling drift is unresolvable", {"Line Item": 61}, ids, [], 1),
        ("several bad names each report once", {"Cost Centre": 28, "Gross Margin": 23}, ids, [], 2),
        ("a concept with no identity is reported", {"NetRevenue": 1}, ids, ["orphan"], 1),
        # NEGATIVE CONTROLS.
        ("an empty validates set is not a finding", {}, ids, [], 0),
        ("a concept nothing names is NOT a finding", {"NetRevenue": 1}, ids, [], 0),
        (
            "every name resolving reports nothing even at scale",
            {"NetRevenue": 28, "LineItem": 61, "CostCentre": 56},
            ids,
            [],
            0,
        ),
    ]
    bad = 0
    for name, validates, identities, nameless, want in cases:
        got = len(judge(validates, identities, nameless))
        if got != want:
            bad += 1
            print(f"  [SELF-TEST FAIL] {name}: {got} finding(s), expected {want}")
    n = len(cases)
    print(
        f"{'PASS' if not bad else 'FAIL'}: check_evidence_attributable self-test — {n - bad}/{n} "
        f"case(s): 5 mutant(s) of the rule (a display title, a spelling drift, several at once, "
        f"a concept with no identity), and 3 negative control(s) (an empty set, an unmeasured "
        f"concept, and an all-resolving set)"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
