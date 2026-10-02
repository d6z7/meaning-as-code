#!/usr/bin/env python3
"""A CONCEPT MUST NEVER CARRY A VALUE LIST. The gate for the ban.

Operator ruling, 2026-10-02, given twice:

    "i want a RULE which prohibits creation of values in concepts ... i want you to expell values out
     of vocabulary and make sure that it cannot creap IN ... because otherwise we will never finish"

    "WTF is this doing here still `values: closure: closed items: - code: AUD ...` — i told you to ban
     it from constitution!!!"

THE BANNED SHAPE is `values:` with `items:` in a concept YAML. Values belong in a register
(`data/lookups/<name>.lookup.csv`) and the column that carries them points at it with `register:`.
The blueprint already said so: "A register is a value set: one virtual table per set of values,
attached to every column that carries it" (guardrails/strategy.yaml).

MEASURED ON contoso5 WHEN THE BAN WAS MADE: 5 concepts inlined 49 values that were byte-for-byte the
same sets as 5 lookup files, with no reference between them — and `color.yaml` already carried 17
members where its register had 16. One fact, two homes, already disagreeing.

A RULE WITH NO CHECKER IS PROSE. The operator predicted exactly how it creeps back: "AI would be
inclined to put all information that we generate ... there". So this exits 1, and a concept that
still carries values must be named in `STANDING` below with its reason and its owner — never silently
tolerated, which is the one thing this estate refuses (`a-red-gate-must-stop-something`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

#: CONCEPTS THAT STILL CARRY VALUES, each with WHY and what unblocks it. A declared standing failure
#: is news that has been read; an undeclared one is news. Removing an entry here is the work.
STANDING: dict[str, str] = {
    # EMPTY, AND THAT IS THE POINT. Both entries were cleared on 2026-10-02: Color's 17th member was
    # a lowercase `blue` the transform already folds (the warehouse has 16, measured), and Country's
    # nine moved to its register once the declared value-domain path stopped emitting CSV headers as
    # the entry column. A new entry here is a debt, not a workaround.
}


def concepts(root: Path):
    directory = root / "ontology" / "concepts"
    if not directory.is_dir():
        return
    for path in sorted(directory.rglob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue  # an unparseable concept is another gate's business
        if not isinstance(doc, dict):
            continue
        name = ((doc.get("concept") or {}) if isinstance(doc.get("concept"), dict) else {}).get(
            "name"
        )
        if name:
            yield path, str(name), doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", default=".", help="the bundle root")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    root = Path(args.bundle).resolve()
    offenders: list[tuple[str, int, str]] = []
    standing_seen: set[str] = set()
    total = 0
    for path, name, doc in concepts(root):
        total += 1
        items = ((doc.get("values") or {}) if isinstance(doc.get("values"), dict) else {}).get(
            "items"
        )
        if not items:
            continue
        if name in STANDING:
            standing_seen.add(name)
            print(f"  STANDING  {name:20s} {len(items):3d} value(s) — {STANDING[name]}")
            continue
        offenders.append((name, len(items), path.name))

    print(f"\n── no-inline-values gate ── {total} concept(s) under {root} ──")
    stale = sorted(set(STANDING) - standing_seen)
    if stale:
        print(
            f"\nSTALE STANDING ENTRIES ({len(stale)}): {', '.join(stale)} no longer carry values — "
            f"remove them from STANDING so the next one that regresses is NEWS."
        )
    if offenders:
        print(f"\nFAIL — {len(offenders)} concept(s) carry an inline value list:")
        for name, n, file in offenders:
            print(f"    {name:20s} {n:3d} value(s)   {file}")
        print(
            "\n  Values belong in a register. Cut one with tools/mac_lookups.py and point the "
            "column at it:\n"
            "      <column>:\n"
            "        role: dimension\n"
            "        register: data/lookups/<name>.lookup.csv\n"
            "  then delete the `values:` block. A declared value-domain register contributes its "
            "members to resolution (resolver/registers.py), so nothing is lost by deleting them."
        )
        return 1
    if stale:
        return 1
    print("\n✓ OK — no concept carries an inline value list beyond the declared standing failures.")
    return 0


def _self_test() -> int:
    """The gate must FAIL on a bundle that inlines values and PASS on one that does not."""
    import tempfile

    ok = True
    for label, body, expect in (
        ("a concept with values", "concept:\n  name: Thing\nvalues:\n  items:\n    - code: A\n", 1),
        ("a concept without", "concept:\n  name: Thing\n", 0),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "ontology" / "concepts"
            d.mkdir(parents=True)
            (d / "thing.yaml").write_text(body)
            found = [
                1
                for _p, _n, doc in concepts(Path(tmp))
                if ((doc.get("values") or {}).get("items"))
            ]
            got = 1 if found else 0
            print(f"  {'✓' if got == expect else '✗'} {label}: detected={got} expected={expect}")
            ok = ok and got == expect
    print("PASS: self-test" if ok else "FAIL: self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
