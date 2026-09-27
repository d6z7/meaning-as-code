#!/usr/bin/env python3
"""check_vocabulary_parity.py — THE SCHEMA MAY NOT KEEP ITS OWN COPY OF A VOCABULARY.

ONE HOME PER FACT. `mac_vocabulary.yaml` declares what the terms of a vocabulary ARE. Where
`mac.schema.json` constrains a slot governed by one of those vocabularies, its `enum` must be that
vocabulary's terms — not a hand-typed list beside them, because two lists of the same fact drift and
neither is marked as the copy.

THE DEFECT THIS REPAIRS, MEASURED 2026-09-27, and I caused half of it. Closing the concept column
map's `role` that morning, I derived the enum from contoso4's 142 delivered declarations —
`[key, dimension, measure, attribute]` — without checking that `mac_vocabulary.yaml#column_role`
had declared the same slot for months, closed, as
`[key, dimension, measure, period, housekeeping]`. So the framework then said two different things
about one word, and nothing could report it. The estate's own law covers it: check for an unread
declaration before proposing a new one. I proposed one instead.

WHAT IT FOUND ON ITS FIRST RUN, both still open for a ruling:
    concept column `role`   schema has `attribute`; the vocabulary has `period`, `housekeeping`
    TableFile `role`        schema has `audit`, `delivery_axis`, `unknown`; the vocabulary has none of them
    concept column `identity`  AGREE — canonical | part | reference
A disagreement is a FAILURE here and not a warning. Which side is right is a human's call — the
delivered bundles use `attribute` 45 times and `period`/`housekeeping` zero — but "the framework
contradicts itself about a closed vocabulary" is not a judgement, it is a fact, and it fails.

THE PAIRS ARE DECLARED BELOW AND NOWHERE ELSE. Adding a governed slot is one line here; the
alternative is a gate that walks the schema guessing which enums are vocabularies, which would be a
third opinion about the same fact.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

#: (label, JSON path into mac.schema.json, vocabulary block). The path is a list of keys/indices so it
#: reads like the document rather than like a query language.
PAIRS = (
    ("concept column `role`",
     ["$defs", "grounding", "properties", "sources", "items", "properties", "columns",
      "oneOf", 1, "additionalProperties", "properties", "role"], "column_role"),
    ("concept column `identity`",
     ["$defs", "grounding", "properties", "sources", "items", "properties", "columns",
      "oneOf", 1, "additionalProperties", "properties", "identity"], "identity_role"),
    ("TableFile column `role`",
     ["$defs", "TableFile", "properties", "columns", "items", "properties", "role"], "storage_role"),
)

ACCEPTED_SHAPE = """\
ACCEPTED SHAPE — run inside a MAC framework checkout carrying mac.schema.json and
mac_vocabulary.yaml side by side.
usage: check_vocabulary_parity.py [--self-test]
"""


def dig(doc, path: list):
    """Walk `path`, or raise KeyError naming the step that failed — a gate must say WHERE it lost its
    way, not report a clean absence."""
    cur = doc
    for i, step in enumerate(path):
        try:
            cur = cur[step]
        except (KeyError, IndexError, TypeError) as exc:
            raise KeyError(f"mac.schema.json has no {'.'.join(map(str, path[:i + 1]))}") from exc
    return cur


def compare(schema: dict, vocab: dict, pairs=PAIRS) -> list:
    """One row per governed slot: (label, block, schema_terms, vocab_terms, state, detail)."""
    out = []
    for label, path, block in pairs:
        try:
            slot = dig(schema, path)
        except KeyError as exc:
            out.append((label, block, set(), set(), "missing_slot", str(exc)))
            continue
        enum = slot.get("enum")
        body = vocab.get(block)
        if body is None:
            out.append((label, block, set(enum or []), set(), "missing_block",
                        f"mac_vocabulary.yaml declares no {block!r} block, so the slot's enum answers "
                        f"to nothing"))
            continue
        terms = body.get("terms")
        if terms is None:
            terms = body.get("members")
        vt = set(terms or {}) if isinstance(terms, dict) else {
            (x.get("term") if isinstance(x, dict) else x) for x in (terms or [])}
        vt = {str(t) for t in vt if t}
        if enum is None:
            out.append((label, block, set(), vt, "unconstrained",
                        f"the slot carries NO enum while {block!r} declares "
                        f"{len(vt)} term(s) — the vocabulary is closed and the schema admits anything"))
            continue
        se = {str(e) for e in enum}
        if se == vt:
            out.append((label, block, se, vt, "ok", f"{len(se)} term(s), identical"))
        else:
            out.append((label, block, se, vt, "disagree",
                        f"schema-only: {', '.join(sorted(se - vt)) or 'none'} | "
                        f"vocabulary-only: {', '.join(sorted(vt - se)) or 'none'}"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    try:
        import yaml
    except ImportError as exc:
        print(f"COULD NOT RUN: {exc}\n\n{ACCEPTED_SHAPE}")
        return 2
    root = pathlib.Path(__file__).resolve().parent.parent
    sp, vp = root / "mac.schema.json", root / "mac_vocabulary.yaml"
    for f in (sp, vp):
        if not f.is_file():
            print(f"COULD NOT RUN: {f.name} is not in this checkout, so parity cannot be read. A gate "
                  f"missing one of its two sources must refuse, not pass.\n\n{ACCEPTED_SHAPE}")
            return 2
    rows = compare(json.loads(sp.read_text(encoding="utf-8")),
                   yaml.safe_load(vp.read_text(encoding="utf-8")) or {})
    bad = [r for r in rows if r[4] != "ok"]
    print(f"  VOCABULARY PARITY — {len(rows)} governed slot(s) declared in this gate\n")
    for label, block, se, vt, state, detail in rows:
        print(f"  [{'ok  ' if state == 'ok' else 'FAIL'}] {label:26} vs mac_vocabulary.yaml#{block}")
        print(f"           {detail}")
        if state == "disagree":
            print(f"           schema     ({len(se)}): {', '.join(sorted(se))}")
            print(f"           vocabulary ({len(vt)}): {', '.join(sorted(vt))}")
    if bad:
        print(f"\nFAIL: check_vocabulary_parity — {len(bad)} of {len(rows)} governed slot(s) disagree "
              f"with the vocabulary that declares them. One fact, two homes: the framework "
              f"contradicts itself about a CLOSED vocabulary, and no bundle can be conformant to both")
        return 1
    print(f"\nPASS: check_vocabulary_parity — {len(rows)} of {len(rows)} governed slot(s) carry exactly "
          f"the terms their vocabulary declares")
    return 0


def _self_test() -> int:
    """A mutant per reject class, the two real disagreements among them."""
    SCH = {"$defs": {"x": {"properties": {"role": {"enum": ["key", "dimension"]}}}}}
    VOC = {"column_role": {"kind": "vocabulary", "closed": True,
                           "terms": {"key": {}, "dimension": {}}}}
    P = [("slot", ["$defs", "x", "properties", "role"], "column_role")]
    cases = []
    def case(label, cond):
        cases.append((label, bool(cond)))

    case("identical term sets pass", compare(SCH, VOC, P)[0][4] == "ok")

    # THE REAL REGRESSION: I added `attribute` to the schema while the vocabulary said
    # period/housekeeping. Both directions must be reported, not just the schema's extras.
    s2 = {"$defs": {"x": {"properties": {"role": {"enum": ["key", "dimension", "attribute"]}}}}}
    v2 = {"column_role": {"kind": "vocabulary", "closed": True,
                          "terms": {"key": {}, "dimension": {}, "period": {}, "housekeeping": {}}}}
    r = compare(s2, v2, P)[0]
    case("MUTANT a schema-only term fails", r[4] == "disagree" and "attribute" in r[5])
    case("the failure also names the VOCABULARY-only terms",
         "period" in r[5] and "housekeeping" in r[5])

    # An unconstrained slot beside a CLOSED vocabulary is the state `measure.type` is in, and the
    # state `role` was in until item 10. Absence of an enum is a failure, not a pass.
    r = compare({"$defs": {"x": {"properties": {"role": {"type": "string"}}}}}, VOC, P)[0]
    case("MUTANT no enum at all beside a closed vocabulary fails", r[4] == "unconstrained")

    r = compare(SCH, {}, P)[0]
    case("MUTANT a vocabulary block that does not exist fails", r[4] == "missing_block")
    r = compare({"$defs": {}}, VOC, P)[0]
    case("MUTANT a schema path that does not exist fails and NAMES the step",
         r[4] == "missing_slot" and "$defs.x" in r[5])

    # `members:` must read the same as `terms:`, so an older framework checkout reports the same
    # findings instead of refusing — a gate that cannot read yesterday's tree teaches nothing.
    r = compare(SCH, {"column_role": {"kind": "value_domain", "closed": True,
                                      "members": {"key": {}, "dimension": {}}}}, P)[0]
    case("a `members:` block is read the same as a `terms:` block", r[4] == "ok")

    bad = [l for l, ok in cases if not ok]
    for l in bad:
        print(f"  FAIL  {l}")
    n = len(cases)
    if bad:
        print(f"\nFAIL: check_vocabulary_parity self-test — {len(bad)} of {n} case(s) failed")
        return 1
    print(f"PASS: check_vocabulary_parity self-test — {n}/{n} case(s): a disagreement is reported in "
          f"BOTH directions, an unconstrained slot beside a closed vocabulary fails, a missing block "
          f"or a missing schema path fails and names what was missing, and `members:` reads as `terms:`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
