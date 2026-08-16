#!/usr/bin/env python3
"""check_enumeration_closure.py — a CLOSED value set may not contain a member you admit you guessed.

THE CONTRADICTION
-----------------
``values.closure: closed`` is a promise: *these are all the valid values, so an engine may filter on
them, refuse anything outside them, and never probe the data to find more.* A member carrying
``confidence: I`` (inferred) or ``Q`` (needs-SME) is the opposite statement: *I am not sure this value
is real.* Holding both at once means the ontology is telling a consumer "trust this list completely"
and "I made part of it up" in the same breath — and the consumer only reads the first half.

WHY THIS EXISTS
---------------
On 2026-08-16 fpl2's ``perspective.yaml`` declared ``closure: closed`` over two members, while marking
the second one ``confidence: I`` with the note "it may be a literal such as 'Brand' or the brand's own
letter; do not assume without confirming". Nothing flagged it. A probe of the fact showed the real
domain had SIX members — one Group role and five NAMED brands. Worse, because the file believed
non-Group was a single undifferentiated bucket, its default rule had been written to permit "or apply
no filter, if the grounded relation defaults to Group" — and the relation does not: Group is 52% of
789,131,541 rows, so an unfiltered read blends six overlapping perspectives and roughly doubles the
answer. The self-contradiction in `values` was the visible tell of a live double-count downstream.

THE FIX IS CHEAP: either confirm the member (probe it, then mark it C), or say ``closure: open`` and
let the engine know it must not treat the list as exhaustive. What is not allowed is claiming both.

NOT A DEFECT: a closed set that DELEGATES its members to a register (``values.realized_by`` with
``params.register``) instead of listing them inline. That is the hold-it-once law working as intended —
the domain lives in data/lookups/ and the concept reads it. Demanding inline items would force a second
copy that drifts. The gate checks the register RESOLVES instead.

OFFLINE + pure-structural. Usage:  python3 tools/check_enumeration_closure.py <bundle-root>
    exit 0 = every closed value set is fully confirmed ; exit 1 = a contradiction.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

CONFIRMED = {"C"}
UNCONFIRMED_MEANING = {"I": "inferred — not independently confirmed",
                       "Q": "needs-SME — explicitly unanswered",
                       "P": "proposed — not ratified",
                       "B": "believed — not verified"}


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: check_enumeration_closure.py <bundle-root>")
        return 2
    root = Path(argv[1]).resolve()
    cdir = root / "ontology" / "concepts"
    print(f"── enumeration-closure gate ── a closed set may not contain an unconfirmed member ── {root} ──\n")
    if not cdir.exists():
        print(f"  [WARN]  no ontology/concepts directory under {root} — nothing to check")
        return 0

    errors: list[str] = []
    checked = 0
    for f in sorted(cdir.rglob("*.yaml")):
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN]  cannot parse {f.name}: {e}")
            continue
        v = d.get("values")
        if not isinstance(v, dict):
            continue
        closure, items = v.get("closure"), v.get("items") or []
        rel = f.relative_to(root)
        if closure != "closed":
            continue
        checked += 1

        # A closed set may name its members INLINE (`items`) or DELEGATE to a register
        # (`realized_by: {udf: mac.canon.*_from_register, params: {register: <name>}}`). Delegation is
        # not a gap — it is the hold-it-once law: the value domain lives in data/lookups/<name>.csv and
        # the concept READS it. Demanding inline items would force a second copy that drifts. So the
        # register form passes, and instead we check the register actually resolves.
        rb = v.get("realized_by") or {}
        register = ((rb.get("params") or {}).get("register") or "") if isinstance(rb, dict) else ""
        if register:
            stem_r = register[:-4] if register.endswith(".csv") else register
            hits = list((root / "data" / "lookups").glob(f"{stem_r}*.csv")) if (root / "data" / "lookups").exists() else []
            if not hits:
                errors.append(f"{rel} — closure 'closed' delegates its value domain to register "
                              f"'{register}', but no matching CSV exists under data/lookups/ — the "
                              f"closed set resolves to nothing")
            continue
        if not items:
            errors.append(f"{rel} — closure 'closed' but it neither enumerates `values.items` nor "
                          f"delegates to a register via `values.realized_by`: the promise 'these are "
                          f"all the valid values' names none of them")
            continue
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            conf = str(it.get("confidence") or "").strip()
            if conf and conf not in CONFIRMED:
                why = UNCONFIRMED_MEANING.get(conf, "not confirmed")
                errors.append(f"{rel} — closure 'closed' but member '{it.get('code', i)}' carries "
                              f"confidence '{conf}' ({why}). Either confirm the member and mark it C, "
                              f"or set closure to 'open'.")

    for e in errors:
        print(f"  [ERROR] {e}")
    print()
    if errors:
        print(f"✗ {len(errors)} closed value set(s) contain a member the ontology admits it has not "
              f"confirmed — a consumer reads 'closed' and trusts the whole list")
        return 1
    print(f"✓ OK — {checked} closed value set(s); every member is SME-confirmed (C)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
