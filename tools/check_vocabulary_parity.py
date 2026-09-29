#!/usr/bin/env python3
"""check_vocabulary_parity.py — THE SCHEMA MAY NOT KEEP ITS OWN COPY OF A VOCABULARY.

ONE HOME PER FACT. `mac_vocabulary.yaml` declares what the terms of a vocabulary ARE. Where
`mac.schema.json` constrains a slot governed by one of those vocabularies, its `enum` must be that
vocabulary's terms — not a hand-typed list beside them, because two lists of the same fact drift and
neither is marked as the copy.

THE DEFECT THIS REPAIRS, MEASURED 2026-09-27, and I caused half of it. Closing the concept column
map's `role` that morning, I derived the enum from contoso4's 142 delivered declarations —
`[key, dimension, measure, attribute]` — without checking that `mac_vocabulary.yaml#concept.column.role`
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

WHAT THE INVENTORY OF 2026-09-29 ADDED. Four enum slots were being checked and the schema carries
nine that a closed vocabulary governs; the five uncovered ones were `concept.identity.kind` (still
spelling `resolved_axis`, RETIRED from the vocabulary 2026-09-28 — a ruling made and never landed),
`issues[].status` (`rejected`/`waived` beside a vocabulary that says `wont_fix`), the bare half of
`additivityAxis`, `$defs.credentialMode`, and `transform.metadata.driven_by`. A gate that covers
four of nine reports a PASS with a denominator nobody printed.

THE PAIRS ARE DECLARED BELOW AND NOWHERE ELSE. This module is THE home of the slot -> vocabulary
table: `gen_slot_reference.py` derives each reference page's "choices" from it (`governs_under`),
and `--write` lands the vocabulary's terms INTO the schema from it. Adding a governed slot is one
line here; the alternative is a gate that walks the schema guessing which enums are vocabularies,
which would be a third opinion about the same fact.

TWO MODES.
    --check (default)  report every governed slot; a disagreement FAILS.
    --write BLOCK...   rewrite the `enum` of every slot governed by the NAMED block(s) to the
                       vocabulary's terms, in the vocabulary's order, and nothing else in the file.
                       A block must be named: a bare `--write` would land the two disagreements that
                       are HUMAN RULINGS still owed (TableFile `role`, `dq_status`) as if someone had
                       ruled, and a tool that makes rulings on a bare invocation is a trap.
                       The file is re-serialised with the exact formatting it already has, and the
                       writer REFUSES if the file does not round-trip byte-for-byte first — a
                       re-dump that would move any byte outside an enum is not "rewriting only the
                       enums".
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

#: (label, JSON path into mac.schema.json, vocabulary block). The path is a list of keys/indices so it
#: reads like the document rather than like a query language. EVERY enum slot a closed vocabulary
#: governs is listed; a slot missing from here is a slot nothing checks.
PAIRS = (
    ("concept column `role`",
     ["$defs", "grounding", "properties", "sources", "items", "properties", "columns",
      "oneOf", 1, "additionalProperties", "properties", "role"], "concept.column.role"),
    ("concept column `identity`",
     ["$defs", "grounding", "properties", "sources", "items", "properties", "columns",
      "oneOf", 1, "additionalProperties", "properties", "identity"], "concept.column.identity"),
    ("column ruling `register`",
     ["$defs", "grounding", "properties", "sources", "items", "properties", "columns",
      "oneOf", 1, "additionalProperties", "properties", "rulings", "properties", "register"],
     "name_register"),
    ("TableFile column `role`",
     ["$defs", "TableFile", "properties", "columns", "items", "properties", "role"], "relation.column.role"),
    ("concept identity `kind`",
     ["$defs", "ConceptFile", "properties", "concept", "properties", "identity", "properties", "kind"],
     "concept.identity"),
    ("DQ issue `status`",
     ["$defs", "DataQualityRegisterFile", "properties", "issues", "items", "properties", "status"],
     "dq_status"),
    ("additivity axis (bare)", ["$defs", "additivityAxis", "oneOf", 0], "concept.aggregation_effect"),
    ("$defs.credentialMode", ["$defs", "credentialMode"], "credential_mode"),
    ("transform `driven_by`",
     ["$defs", "TransformFile", "properties", "metadata", "properties", "driven_by"], "transform.driven_by"),
)

#: SLOTS CONSTRAINED BY A REGEX INSTEAD OF AN ENUM. A `pattern` that names a namespace is a THIRD home
#: for the vocabulary — after the vocabulary itself and any enum — and until 2026-09-27 nothing read
#: them. That cost a real failure: renaming `measure_type` to `column.measure_type` passed all four
#: self-tests and only surfaced when contoso4 dropped to 79 of 81, because
#: `^mac\.measure_type\.[A-Za-z_]…` still spelled the old name. Declared here so a rename cannot be
#: "finished" while a pattern still disagrees.
PATTERNS = (
    ("semantics.measure_type token", ["$defs", "semantics", "properties", "measure_type"],
     "concept.column.measure_type"),
    ("semantics.axis_kinds token",
     ["$defs", "semantics", "properties", "axis_kinds", "additionalProperties"], "concept.axis_kind"),
    ("additivity axis token", ["$defs", "additivityAxis", "oneOf", 1], "concept.aggregation_effect"),
)

ACCEPTED_SHAPE = """\
ACCEPTED SHAPE — run inside a MAC framework checkout carrying mac.schema.json and
mac_vocabulary.yaml side by side.
usage: check_vocabulary_parity.py [--check | --write BLOCK [BLOCK ...] | --self-test]
"""


class Refuse(ValueError):
    """The writer will not proceed — the reason is the message, and nothing was written."""


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


def terms_of(vocab: dict, block: str) -> list[str]:
    """The vocabulary's terms for `block`, IN DECLARATION ORDER — `terms:` or the older `members:`,
    a map or a list of {term:} rows. An empty list means the block declares nothing (or is absent)."""
    body = vocab.get(block) or {}
    t = body.get("terms") if body.get("terms") is not None else body.get("members")
    names = list(t) if isinstance(t, dict) else [
        (x.get("term") if isinstance(x, dict) else x) for x in (t or [])]
    return [str(n) for n in names if n]


def governs_under(object_path: list, pairs=PAIRS) -> dict[str, str]:
    """{dotted property key -> vocabulary block} for every governed slot INSIDE the object at
    `object_path` — the "choices" column of a per-slot reference page, derived rather than restated.

    A pair's path must extend the object's through `properties` steps only (`properties.rulings.
    properties.register` -> `rulings.register`); a governed slot reached any other way (an `items`,
    a `oneOf` index) is not a property of this object and is not claimed for its page.
    """
    out: dict[str, str] = {}
    n = len(object_path)
    for _label, path, block in pairs:
        if len(path) <= n or path[:n] != object_path:
            continue
        rest = path[n:]
        if len(rest) % 2 or any(rest[i] != "properties" for i in range(0, len(rest), 2)):
            continue
        out[".".join(str(k) for k in rest[1::2])] = block
    return out


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
        vt = set(terms_of(vocab, block))
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


def compare_patterns(schema: dict, vocab: dict, pats=PATTERNS) -> list:
    """One row per pattern-constrained slot: (label, block, state, detail).

    IT CHECKS TWO THINGS, and the second is the one that bit: the pattern must NAME the vocabulary's
    namespace, and where it also ENUMERATES the terms inline — `(additive|average|none)` — those terms
    must be the vocabulary's. A regex alternation is an enum wearing a disguise.
    """
    import re as _re
    out = []
    for label, path, block in pats:
        try:
            slot = dig(schema, path)
        except KeyError as exc:
            out.append((label, block, "missing_slot", str(exc)))
            continue
        pat = slot.get("pattern")
        if not isinstance(pat, str):
            out.append((label, block, "no_pattern", "the slot carries no `pattern` to check"))
            continue
        want = "mac\\." + block.replace(".", "\\.") + "\\."
        if want not in pat:
            out.append((label, block, "wrong_namespace",
                        f"the pattern does not name {block!r} — it reads {pat!r}, so a token spelled "
                        f"for the CURRENT vocabulary is refused and the old spelling is accepted"))
            continue
        # an inline alternation is an enum in disguise; its members must be the vocabulary's
        alts = _re.search(r"\(([A-Za-z_|]+)\)", pat)
        if alts:
            inline = {a for a in alts.group(1).split("|") if a}
            vt = set(terms_of(vocab, block))
            if inline != vt:
                out.append((label, block, "disagree",
                            f"the pattern enumerates {sorted(inline)} inline and the vocabulary "
                            f"declares {sorted(vt)}"))
                continue
        out.append((label, block, "ok", f"names {block!r}" +
                    (" and its terms match the vocabulary" if alts else "")))
    return out


# ── THE WRITER ──────────────────────────────────────────────────────────────────────────────────

def dumps(doc) -> str:
    """mac.schema.json's own serialisation: 2-space indent, multi-line arrays, non-ASCII kept, one
    trailing newline. Measured 2026-09-29 to reproduce the committed file byte-for-byte."""
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def rewrite(text: str, vocab: dict, blocks: list[str], pairs=PAIRS) -> tuple[str, list[str]]:
    """(new text, labels of the slots whose enum changed). Every slot governed by a NAMED block gets
    the vocabulary's terms in the vocabulary's order; every other byte of the file is untouched.

    REFUSES — nothing returned, nothing written — when a named block governs no slot (a typo would
    otherwise "land" silently), when the vocabulary declares no terms for it (an empty enum admits
    nothing, which is a different fact from "closed"), or when the text does not round-trip through
    `dumps` (the re-dump would then move bytes that are not enums).
    """
    governed = {b for _l, _p, b in pairs}
    unknown = sorted(set(blocks) - governed)
    if unknown:
        raise Refuse(f"no governed slot answers to {', '.join(unknown)}; the governed blocks are "
                     f"{', '.join(sorted(governed))}")
    doc = json.loads(text)
    if dumps(doc) != text:
        raise Refuse("mac.schema.json does not round-trip through json.dumps(indent=2); a re-dump "
                     "would move bytes outside the enums, so nothing was written")
    changed = []
    for label, path, block in pairs:
        if block not in blocks:
            continue
        terms = terms_of(vocab, block)
        if not terms:
            raise Refuse(f"mac_vocabulary.yaml#{block} declares no terms; an enum of nothing is not "
                         f"a closed vocabulary, so {label} was left as it is")
        slot = dig(doc, path)
        if slot.get("enum") == terms:
            continue
        slot["enum"] = terms
        changed.append(label)
    return dumps(doc), changed


def _report(rows, prows) -> int:
    bad = [r for r in rows if r[4] != "ok"] + [r for r in prows if r[2] != "ok"]
    print(f"  VOCABULARY PARITY — {len(rows)} enum slot(s) + {len(prows)} pattern slot(s)\n")
    for label, block, se, vt, state, detail in rows:
        print(f"  [{'ok  ' if state == 'ok' else 'FAIL'}] {label:26} vs mac_vocabulary.yaml#{block}")
        print(f"           {detail}")
        if state == "disagree":
            print(f"           schema     ({len(se)}): {', '.join(sorted(se))}")
            print(f"           vocabulary ({len(vt)}): {', '.join(sorted(vt))}")
    for label, block, state, detail in prows:
        print(f"  [{'ok  ' if state == 'ok' else 'FAIL'}] {label:26} vs mac_vocabulary.yaml#{block}")
        print(f"           {detail}")
    n = len(rows) + len(prows)
    if bad:
        print(f"\nFAIL: check_vocabulary_parity — {len(bad)} of {n} governed slot(s) disagree "
              f"with the vocabulary that declares them. One fact, two homes: the framework "
              f"contradicts itself about a CLOSED vocabulary, and no bundle can be conformant to both")
        return 1
    print(f"\nPASS: check_vocabulary_parity — {n} of {n} governed slot(s) carry exactly "
          f"the terms their vocabulary declares")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--check", action="store_true", help="report only (the default)")
    ap.add_argument("--write", nargs="+", metavar="BLOCK",
                    help="land the named vocabulary block(s) into the schema's enum(s), then report")
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
    text = sp.read_text(encoding="utf-8")
    voc = yaml.safe_load(vp.read_text(encoding="utf-8")) or {}
    if a.write:
        try:
            new, changed = rewrite(text, voc, a.write)
        except Refuse as exc:
            print(f"REFUSED: {exc}\n\n{ACCEPTED_SHAPE}")
            return 2
        if changed:
            sp.write_text(new, encoding="utf-8")
            text = new
            print(f"  WROTE mac.schema.json — {len(changed)} enum(s) now carry their vocabulary's terms: "
                  f"{'; '.join(changed)}\n")
        else:
            print(f"  NOTHING TO WRITE — every slot governed by {', '.join(a.write)} already carries "
                  f"its vocabulary's terms\n")
    schema = json.loads(text)
    return _report(compare(schema, voc), compare_patterns(schema, voc))


def _plant(path: list, leaf):
    """The smallest document in which `path` resolves to `leaf`, so a self-test mutant exercises the
    REAL path declared in PAIRS — a typo in the table fails here, not in the field."""
    doc = leaf
    for step in reversed(path):
        if isinstance(step, int):
            lst = [None] * (step + 1)
            lst[step] = doc
            doc = lst
        else:
            doc = {step: doc}
    return doc


def _self_test() -> int:
    """A mutant per reject class, the two real disagreements among them, and one per governed slot."""
    SCH = {"$defs": {"x": {"properties": {"role": {"enum": ["key", "dimension"]}}}}}
    VOC = {"concept.column.role": {"kind": "vocabulary", "closed": True,
                           "terms": {"key": {}, "dimension": {}}}}
    P = [("slot", ["$defs", "x", "properties", "role"], "concept.column.role")]
    cases = []
    def case(label, cond):
        cases.append((label, bool(cond)))

    case("identical term sets pass", compare(SCH, VOC, P)[0][4] == "ok")

    # THE REAL REGRESSION: I added `attribute` to the schema while the vocabulary said
    # period/housekeeping. Both directions must be reported, not just the schema's extras.
    s2 = {"$defs": {"x": {"properties": {"role": {"enum": ["key", "dimension", "attribute"]}}}}}
    v2 = {"concept.column.role": {"kind": "vocabulary", "closed": True,
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
    r = compare(SCH, {"concept.column.role": {"kind": "value_domain", "closed": True,
                                      "members": {"key": {}, "dimension": {}}}}, P)[0]
    case("a `members:` block is read the same as a `terms:` block", r[4] == "ok")

    # ── ONE MUTANT PER GOVERNED SLOT, ON ITS REAL PATH. The five slots the 2026-09-29 inventory
    #    found uncovered are here with the four before them: a document planted along the path in
    #    PAIRS must resolve, and a stray term on that path must be named. The terms are toys on
    #    purpose — a self-test carrying the vocabulary's real terms would be a third copy of them.
    for label, path, block in PAIRS:
        toy = {block: {"closed": True, "terms": {"a": "", "b": ""}}}
        one = [(label, path, block)]
        case(f"{label}: the declared path resolves and agreeing terms pass",
             compare(_plant(path, {"enum": ["a", "b"]}), toy, one)[0][4] == "ok")
        r = compare(_plant(path, {"enum": ["a", "b", "stray"]}), toy, one)[0]
        case(f"MUTANT {label}: a schema-only term on the declared path fails and is named",
             r[4] == "disagree" and "stray" in r[5])

    # ── THE PAGE DERIVATION: a reference page's "choices" come from PAIRS, not from a second table.
    obj = ["$defs", "grounding", "properties", "sources", "items", "properties", "columns",
           "oneOf", 1, "additionalProperties"]
    g = governs_under(obj)
    case("governs_under derives the column map's three governed keys from PAIRS",
         g == {"role": "concept.column.role", "identity": "concept.column.identity",
               "rulings.register": "name_register"})
    case("governs_under claims nothing for an object that governs nothing",
         governs_under(["$defs", "nothing_here"]) == {})
    case("governs_under does not claim a slot reached through `items`/`oneOf` rather than a property",
         "0" not in governs_under(["$defs", "additivityAxis", "oneOf"]))

    # ── THE WRITER. It lands the vocabulary's terms in the vocabulary's ORDER, touches no other
    #    byte, is idempotent, and refuses the three ways it could do harm.
    text = dumps(s2)
    new, changed = rewrite(text, v2, ["concept.column.role"], P)
    case("--write lands the vocabulary's terms in the vocabulary's order",
         json.loads(new)["$defs"]["x"]["properties"]["role"]["enum"]
         == ["key", "dimension", "period", "housekeeping"])
    case("--write names the slot it changed", changed == ["slot"])
    case("--write is idempotent", rewrite(new, v2, ["concept.column.role"], P) == (new, []))
    strip = lambda t: [ln for ln in t.splitlines() if ln.strip().strip(",").strip('"')
                       not in ("attribute", "period", "housekeeping")]
    case("--write touches nothing but the enum's members", strip(text) == strip(new))
    # a slot governed by a block that was NOT named must be left exactly as it is
    P2 = P + [("other", ["$defs", "x", "properties", "kind"], "concept.identity")]
    s3 = {"$defs": {"x": {"properties": {"role": {"enum": ["key", "dimension", "attribute"]},
                                          "kind": {"enum": ["iso", "resolved_axis"]}}}}}
    v3 = dict(v2, **{"concept.identity": {"closed": True, "terms": {"iso": ""}}})
    new3, ch3 = rewrite(dumps(s3), v3, ["concept.column.role"], P2)
    case("--write leaves a slot alone when its block was not named",
         ch3 == ["slot"] and json.loads(new3)["$defs"]["x"]["properties"]["kind"]["enum"]
         == ["iso", "resolved_axis"])
    def refuses(fn):
        try:
            fn()
        except Refuse:
            return True
        return False
    case("MUTANT --write refuses a block no governed slot answers to (a typo must not land silently)",
         refuses(lambda: rewrite(text, v2, ["concept.column.rol"], P)))
    case("MUTANT --write refuses when the vocabulary declares no terms for the block",
         refuses(lambda: rewrite(text, {"concept.column.role": {"terms": {}}}, ["concept.column.role"], P)))
    case("MUTANT --write refuses a file that does not round-trip through its own serialisation",
         refuses(lambda: rewrite(text.replace("\n", "\n ", 1), v2, ["concept.column.role"], P)))

    # ── THE PATTERN HALF (added after a rename passed every self-test and broke a bundle) ─────────
    SP = [("slot", ["$defs", "x", "properties", "mt"], "concept.column.measure_type")]
    SCHP = lambda pat: {"$defs": {"x": {"properties": {"mt": ({"pattern": pat} if pat else {"type": "string"})}}}}
    VP = {"concept.column.measure_type": {"kind": "value_domain", "closed": True,
                                  "terms": {"flow": {}, "stock": {}}}}
    cp = lambda pat: compare_patterns(SCHP(pat), VP, SP)[0]

    case("a pattern naming the current namespace passes",
         cp(r"^mac\.concept\.column\.measure_type\.[A-Za-z_]+$")[2] == "ok")
    # THE EXACT REGRESSION: the pattern kept the OLD spelling, so a correctly-spelled token is
    # REFUSED and the stale one is accepted -- the worst way round.
    case("MUTANT a pattern naming the OLD namespace fails",
         cp(r"^mac\.measure_type\.[A-Za-z_]+$")[2] == "wrong_namespace")
    case("the failure says a current token would be REFUSED",
         "refused" in cp(r"^mac\.measure_type\.[A-Za-z_]+$")[3])
    case("MUTANT no pattern at all is reported, not passed", cp(None)[2] == "no_pattern")
    # AN INLINE ALTERNATION IS AN ENUM IN DISGUISE and must match the vocabulary's terms.
    case("an inline alternation matching the vocabulary passes",
         cp(r"^mac\.concept\.column\.measure_type\.(flow|stock)$")[2] == "ok")
    case("MUTANT an inline alternation that DRIFTS from the vocabulary fails",
         cp(r"^mac\.concept\.column\.measure_type\.(flow|stock|level)$")[2] == "disagree")
    case("the drift names both sides",
         "level" in cp(r"^mac\.concept\.column\.measure_type\.(flow|stock|level)$")[3])
    case("MUTANT a pattern slot that does not exist fails and names the step",
         compare_patterns({"$defs": {}}, VP, SP)[0][2] == "missing_slot")

    bad = [l for l, ok in cases if not ok]
    for l in bad:
        print(f"  FAIL  {l}")
    n = len(cases)
    if bad:
        print(f"\nFAIL: check_vocabulary_parity self-test — {len(bad)} of {n} case(s) failed")
        return 1
    print(f"PASS: check_vocabulary_parity self-test — {n}/{n} case(s): a disagreement is reported in "
          f"BOTH directions, an unconstrained slot beside a closed vocabulary fails, a missing block "
          f"or a missing schema path fails and names what was missing, `members:` reads as `terms:`, "
          f"each of the {len(PAIRS)} governed slots is exercised on its declared path, a reference "
          f"page's choices derive from PAIRS, --write lands terms in vocabulary order and touches "
          f"nothing else and refuses a typo, an empty block or a file it cannot re-serialise "
          f"faithfully, and a PATTERN must name the current namespace with any inline alternation "
          f"matching the vocabulary's terms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
