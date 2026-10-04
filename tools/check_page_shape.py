#!/usr/bin/env python3
"""check_page_shape.py — A PAGE IS THE SHAPE ITS GUARDRAIL DECLARES.

WHAT A SCHEMA IS FOR YAML, THIS IS FOR MARKDOWN. The estate holds every other form to a declaration
and held pages to none:

    yaml   validate_schema.py + mac.schema.json      structure, types, closed enums
    csv    check_sample_matches_descriptor.py        header == the descriptor's columns
    md     check_pages_current.py                    STALENESS ONLY

ITS SUBJECT IS A BUNDLE, AND THE MANUAL IS NOT ONE. This gate takes a bundle root in argv[1] and
judges the pages a DELIVERY writes there. `reference_manual/` — this repository's own 123 authored
pages, which until 2026-10-04 were named by no declaration at all — is held by
`tools/check_manual_page_shape.py` against `authored:` entries in `guardrails/`. Four measured
reasons for the split are in that file's header; the one that settles it is that declaring a manual
page under `delivers:` put `reference_manual/patterns/*.md` into `mac_manifest.bom()` as ABSENT from
contoso5, breaking the completeness answer the BOM exists to give. The two gates share `sections()`
below and NOTHING else — one heading parser, two subjects. Do not merge them back.

IT DOES NOT RE-RENDER, AND THAT IS THE WHOLE POINT. `check_pages_current` renders the page again and
byte-compares, which catches a page drifting from its source and CANNOT catch the renderer changing
what it emits — the comparator and the renderer are the same code, so they agree by construction.
That is the same defect `NAME-MATCHES` shipped with, where the glob that selected the files and the
regex that judged them came from one string. This reads the DELIVERED BYTES and holds them against
the DECLARATION.

Operator, 2026-09-29: "my question is not if you can do it ONCE ... the question is if you can do it
EVERY TIME!?!?!?" — measured, the cardinality this bundle stores in every descriptor stopped
appearing on its pages and nothing objected, because nothing had ever said it should.

ASSERT LITTLE AND TRUE. A shape rule that cries wolf gets ignored and is then worse than nothing, so
a guardrail governs only the sections it names: a section with no declared pattern is reported `n/a`,
never guessed at.

    python3 check_page_shape.py <bundle>
    python3 check_page_shape.py --self-test
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

OK, VIOLATION, NA = "ok", "violation", "n/a"
REJECTS = ("SECTION_MISSING", "LINE_MALFORMED", "UNGOVERNED_SECTION")


def _i(subject, verdict, note=""):
    return {"subject": subject, "verdict": verdict, "note": note}


def sections(text: str) -> dict:
    """{heading -> [content line, ...]} from a delivered page. `## X` opens a section.

    A PARSER, NOT A RENDERER. It takes the bytes somebody actually reads.
    """
    out, cur = {}, None
    for line in (text or "").splitlines():
        h = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if h:
            # A HEADING'S NAME IS WHAT PRECEDES ITS QUALIFIER. Renderers put live detail in the
            # heading itself — `## Lineage (column-level)`, `## High priority — 1 question(s)`,
            # `## Chain — \`raw source → transformation\`` — so the literal string varies with the
            # data and a declaration could never name it. The name is the stable part: everything
            # before a parenthetical or an em-dash qualifier.
            cur = re.sub(r"\s*\(.*\)\s*$", "", h.group(1))
            cur = re.split(r"\s+—\s+", cur, maxsplit=1)[0].strip()
            out.setdefault(cur, [])
            continue
        if cur is not None and line.strip():
            out[cur].append(line.rstrip())
    return out


#: When a declared section is REQUIRED. Each predicate reads the page's own SOURCE descriptor, so
#: "required" means "the data for it exists", never "somebody remembered to write it".
def _needs(cond: str, descriptor: dict) -> bool | None:
    cols = (descriptor or {}).get("columns") or []
    if cond == "always":
        return True
    if cond == "when_a_column_has_references":
        return any(isinstance(c, dict) and c.get("references") for c in cols)
    if cond == "when_a_column_has_a_register":
        return any(isinstance(c, dict) and c.get("register") for c in cols)
    return None                                       # an unknown condition is NOT a silent True


def resolve_shape(shape: dict, items: dict) -> dict:
    """Follow `lines_like` to the kind that OWNS the line rules, so a pattern has one home.

    A copy of a regex is a second home and it drifted inside four minutes: the served page's copy
    was double-escaped (`\\\\.` for `\\.`) and rejected three correctly rendered pages. The rule
    lives with the kind that defined it; everyone else points at it.
    """
    ref = shape.get("lines_like")
    if not ref:
        return shape
    kind = str(ref).split("#")[-1]
    owner = (items.get(kind) or {}).get("shape") or {}
    out = dict(shape)
    out["lines"] = {**(owner.get("lines") or {}), **(shape.get("lines") or {})}
    out["line_forms"] = {**(owner.get("line_forms") or {}), **(shape.get("line_forms") or {})}
    out["line_selectors"] = {**(owner.get("line_selectors") or {}), **(shape.get("line_selectors") or {})}
    return out


def check_page(rel: str, text: str, shape: dict, descriptor: dict) -> list:
    """One page against one `shape` declaration. The ENUMERATION CONTRACT: one item per subject."""
    out = []
    present = sections(text)
    declared = {s["heading"]: s for s in (shape.get("sections") or [])}
    patterns = shape.get("lines") or {}
    words = shape.get("line_forms") or {}

    for head, spec in declared.items():
        need = _needs(str(spec.get("required")), descriptor)
        if need is None:
            out.append(_i(f"{rel}#{head}", NA,
                          f"required: {spec.get('required')!r} is not a condition this gate knows — "
                          f"an unknown condition is not a silent pass"))
            continue
        if not need:
            out.append(_i(f"{rel}#{head}", NA, "the data for this section does not exist on this relation"))
            continue
        if head not in present:
            out.append(_i(f"{rel}#{head}", VIOLATION,
                          f"SECTION_MISSING — the descriptor has the data and the page has no `## {head}`"))
            continue
        rx = patterns.get(head)
        if not rx:
            out.append(_i(f"{rel}#{head}", NA, "present; no line pattern is declared for it"))
            continue
        # WHICH LINES THE PATTERN JUDGES, declared. A bullet section governs `- ` lines; a table
        # section governs `| ` rows. The SME sign-off page rendered SEVEN questions with an empty
        # first cell for months, and no bullet pattern could ever have seen it.
        sel = (shape.get("line_selectors") or {}).get(head, "^- ")
        bad = [ln for ln in present[head] if re.match(sel, ln) and not re.match(rx, ln)]
        if bad:
            out.append(_i(f"{rel}#{head}", VIOLATION,
                          f"LINE_MALFORMED — {len(bad)} of {len(present[head])} line(s) do not match "
                          f"`{words.get(head, rx)}`: {bad[0][:90]}"))
        else:
            out.append(_i(f"{rel}#{head}", OK,
                          f"{len(present[head])} line(s) match {words.get(head, 'the declared pattern')}"))
    return out


def run(root: pathlib.Path, framework: pathlib.Path) -> list:
    import yaml

    sys.path.insert(0, str(framework / "tools"))
    import mac_manifest as M

    items = M.declared_items(framework)
    shaped = {k: v for k, v in items.items() if (v.get("shape") or {}).get("sections")}
    if not shaped:
        return [_i("«declarations»", NA, "no guardrail declares a page `shape` — nothing to hold")]

    out = []
    for name, item in sorted(shaped.items()):
        path = str(item.get("path") or "")
        glob = re.sub(r"\{[^}]*\}", "*", path.split("|")[0].strip())
        pages = sorted(root.glob(glob))
        # A MORE SPECIFIC DECLARATION OWNS ITS FILE. `data/sources/*.md` also matches `index.md`,
        # which `plane_overview` declares by its exact name — so this kind judged another kind's
        # page and reported a missing `## Columns` on a plane overview. The estate's existing
        # tie-break (most literal characters outside a wildcard) settles it, and a rule that cries
        # wolf once gets ignored for ever afterwards.
        mine = []
        for pg in pages:
            rel_p = str(pg.relative_to(root))
            owner = max((o for o in items.values() if M._claims(o.get("path"), rel_p)),
                        key=lambda o: M.specificity(o.get("path")), default=None)
            if owner is None or owner.get("path") == item.get("path"):
                mine.append(pg)
        pages = mine
        if not pages:
            out.append(_i(name, NA, f"no page under {glob} in this bundle"))
            continue
        for pg in pages:
            rel = str(pg.relative_to(root))
            # THE PAGE'S OWN SOURCE, so "required" is a fact about the data and not about the page.
            src = pg.with_suffix(".yaml")
            desc = {}
            if src.is_file():
                try:
                    desc = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
                except Exception:                                         # noqa: BLE001
                    desc = {}
            out += check_page(rel, pg.read_text(encoding="utf-8"),
                              resolve_shape(item["shape"], items), desc)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    fw = pathlib.Path(__file__).resolve().parent.parent
    if a.self_test:
        return _self_test()
    try:
        import yaml                                                       # noqa: F401
    except ImportError as exc:
        print(f"REFUSED: {exc}")
        return 2
    items = run(pathlib.Path(a.root).resolve(), fw)
    bad = [i for i in items if i["verdict"] == VIOLATION]
    na = sum(1 for i in items if i["verdict"] == NA)
    print(f"── page shape ── {pathlib.Path(a.root).name} ──")
    print(f"  {len(items)} enumerated · {len(items) - len(bad) - na} held · {len(bad)} failed · {na} n/a")
    for i in bad:
        print(f"    ✗ {i['subject']}")
        print(f"        {i['note']}")
    if bad:
        print(f"\nFAIL: check_page_shape — {len(bad)} page section(s) are not the shape their guardrail "
              f"declares. A page is what a person READS; a renderer that changes what it emits and a "
              f"comparator that re-renders will always agree, which is why this reads the delivered bytes.")
        return 1
    print("\nPASS: check_page_shape — every governed section is the shape its guardrail declares.")
    return 0


def _self_test() -> int:
    ok = [0, 0]

    def case(what, cond):
        ok[0] += 1
        ok[1] += bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + what)

    SHAPE = {
        "sections": [{"heading": "Columns", "required": "always"},
                     {"heading": "Foreign keys", "required": "when_a_column_has_references"}],
        "lines": {"Foreign keys": r"^- `[^`]+` → `[^`.]+\.[^`]+` \([a-z]+:[a-z]+, [a-z]+:[a-z]+\)$"},
        "line_forms": {"Foreign keys": "- `column` → `relation.column` (child:parent, child:parent)"},
    }
    WITH_REF = {"columns": [{"name": "CustomerKey", "references": {"to": "customer.CustomerKey"}}]}
    NO_REF = {"columns": [{"name": "X"}]}
    GOOD = ("## Columns\n\n| a |\n\n## Foreign keys\n\n"
            "- `CustomerKey` → `customer.CustomerKey` (many:one, mandatory:optional)\n")

    case("a page in the declared shape HOLDS",
         not [i for i in check_page("p.md", GOOD, SHAPE, WITH_REF) if i["verdict"] == VIOLATION])
    # ── the two failures that actually happened ───────────────────────────────────────────────
    REPR = ("## Columns\n\n## Foreign keys\n\n"
            "- `OrderDate` → `{'to': 'date.Date', 'cardinality': {'child': 'many'}}`\n")
    case("MUTANT a mapping printed as a Python repr is REFUSED",
         any(i["verdict"] == VIOLATION and "LINE_MALFORMED" in i["note"]
             for i in check_page("p.md", REPR, SHAPE, WITH_REF)))
    DROPPED = "## Columns\n\n## Foreign keys\n\n- `CustomerKey` → `customer.CustomerKey`\n"
    case("MUTANT cardinality silently dropped is REFUSED",
         any(i["verdict"] == VIOLATION and "LINE_MALFORMED" in i["note"]
             for i in check_page("p.md", DROPPED, SHAPE, WITH_REF)))
    MISSING = "## Columns\n\n| a |\n"
    case("MUTANT a required section absent while its data exists is REFUSED",
         any(i["verdict"] == VIOLATION and "SECTION_MISSING" in i["note"]
             for i in check_page("p.md", MISSING, SHAPE, WITH_REF)))
    case("a section absent because its DATA is absent is n/a, not a violation",
         all(i["verdict"] != VIOLATION for i in check_page("p.md", MISSING, SHAPE, NO_REF)))
    case("an UNKNOWN required-condition is n/a with its reason, never a silent pass",
         any(i["verdict"] == NA and "not a condition this gate knows" in i["note"]
             for i in check_page("p.md", GOOD, {"sections": [{"heading": "Columns", "required": "whenever"}]}, {})))
    case("a heading with a parenthetical still resolves to its name",
         "Lineage" in sections("## Lineage (column-level)\n\n- x\n"))
    case("a section with NO declared pattern is n/a, not guessed at",
         any(i["verdict"] == NA and "no line pattern" in i["note"]
             for i in check_page("p.md", GOOD,
                                 {"sections": [{"heading": "Columns", "required": "always"}]}, {})))

    # ── the COLUMNS table: role and reference must agree ──────────────────────────────────────
    # THE PATTERN IS READ FROM THE GUARDRAIL, NOT RESTATED HERE. A self-test that carries its own
    # copy of the rule proves the copy, not the rule — and the one time a pattern in this estate
    # was written down twice, the second copy was double-escaped and refused three correct pages
    # within four minutes. If the declaration is unreadable that is itself a failure, so it is a
    # case rather than an exception.
    import yaml
    try:
        _g = yaml.safe_load((pathlib.Path(__file__).resolve().parents[1]
                             / "guardrails/data/sources.yaml").read_text())
        _sh = _g["delivers"]["relation_page"]["shape"]
        COLS = {"sections": [{"heading": "Columns", "required": "always"}],
                "lines": {"Columns": _sh["lines"]["Columns"]},
                "line_selectors": {"Columns": _sh["line_selectors"]["Columns"]},
                "line_forms": {"Columns": _sh["line_forms"]["Columns"]}}
    except Exception as exc:                                    # pragma: no cover - a red case
        COLS = None
        case(f"the Columns rule is readable from its guardrail ({exc})", False)

    if COLS:
        def _page(*rows):
            return ("## Columns\n\n| column | type | role | reference |\n|---|---|---|---|\n"
                    + "\n".join(rows) + "\n")

        def _bad(text):
            return any(i["verdict"] == VIOLATION and "LINE_MALFORMED" in i["note"]
                       for i in check_page("p.md", text, COLS, WITH_REF))

        case("a plain key, a plain value and a plain FK all HOLD",
             not _bad(_page("| `order_key` | integer | PK1 |  |",
                            "| `rate` | decimal | value |  |",
                            "| `order_date` | timestamp | FK | → `dim_date.date_day` |")))
        # THE ROW THIS ESTATE SHIPPED THIS MORNING. contoso5/data/datasets/v_contoso5_fx_rate.md,
        # and five more like it: the key position was printed and the reference, which the cell to
        # its right showed with an arrow, was not named. Once `FK` prints for the 17 columns whose
        # role IS `foreign_key`, its absence on the other 6 asserts something false.
        case("MUTANT a key column that references a parent without naming FK is REFUSED",
             _bad(_page("| `date_day` | timestamp | PK1 | → `dim_date.date_day` |")))
        case("MUTANT the same lie told the other way — FK with no reference — is REFUSED",
             _bad(_page("| `order_date` | timestamp | FK |  |")))
        case("a key column that names BOTH holds",
             not _bad(_page("| `date_day` | timestamp | PK1 · FK | → `dim_date.date_day` |")))
        case("a register beside the arrow does not disturb the rule",
             not _bad(_page("| `from_currency` | string | PK2 · FK | "
                            "→ `dim_currency.currency_code` · register: `v_x_from_currency` |")))
        case("a register with NO arrow needs no FK",
             not _bad(_page("| `status` | string | value | register: `v_x_status` |")))
        # WITHOUT THE SELECTOR THIS RULE EATS ITS OWN TABLE. The header row carries the word
        # `reference` and no arrow, the `|---|` rule carries neither; both are structure, not data,
        # and a bullet-shaped default selector would have judged neither while a bare `^\|` would
        # have judged both. The selector requires the backtick that opens a column name.
        case("the header row and the |---| rule are structure, not data, and are not judged",
             not _bad(_page("| `rate` | decimal | value |  |")))

    print(("PASS" if ok[1] == ok[0] else "FAIL")
          + f": check_page_shape self-test — {ok[1]}/{ok[0]} case(s), including the three failures "
            f"this gate was written for: a mapping rendered as a repr, a measured fact dropped, "
            f"and a key column that referenced a parent without saying so.")
    return 0 if ok[1] == ok[0] else 1


if __name__ == "__main__":
    sys.exit(main())
