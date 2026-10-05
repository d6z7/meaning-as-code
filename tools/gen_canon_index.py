#!/usr/bin/env python3
"""gen_canon_index — the canon tree in rules_and_canons/README.md, grouped by the pattern it serves.

NO GROUPING AND NO COUNT ON THE PAGE THIS WRITES IS TYPED HERE. The middle layer of the tree is
`mac_vocabulary.yaml#canon.terms[*].serves`, which every canon already declares and which names a
page under `reference_manual/patterns/`. So the groups are READ, not authored: a canon moves between
groups by changing its declaration, and a group appears or disappears because the canons did.

THE DIRECTORY CARRIES THE SAME GROUPING. `reference_manual/rules_and_canons/<serves>/<name>.md` since
2026-10-05, so the tree this renders and the tree on disk are built from one declaration and cannot
disagree. Basenames were PRESERVED through the move, which is what kept it mechanical: 50 markdown
links needed only a group segment inserted after `canon/`, 33 links out of the moved pages needed one
more `../`, and 9 sibling links were re-pointed. `check_canon_documented` moved from a flat `glob` to
`rglob` in the same change — a flat glob measured 0 described against 21 undescribed the moment the
pages moved.

decisions/ WAS NOT TOUCHED. Its records are dated, they cite canon paths as backticked prose rather
than markdown links, and check_dangling_references does not judge a path whose first segment is not
an owned directory. A dated record may describe where a page was on its date.

Usage:
  python3 tools/gen_canon_index.py            # write the region between the sentinels
  python3 tools/gen_canon_index.py --check    # exit 1 if the page has drifted from the declarations
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOCAB = ROOT / "mac_vocabulary.yaml"
PAGE = ROOT / "reference_manual" / "rules_and_canons" / "README.md"
PAGES_DIR = ROOT / "reference_manual" / "rules_and_canons"
PATTERNS_DIR = ROOT / "reference_manual" / "patterns"

#: The runtime is a different repository and is read, never imported — the same posture
#: check_canon_implemented.py takes. Absent, the status column says so rather than guessing.
RUNTIME = pathlib.Path(
    "<redacted-home>/dev/mac-platform/packages/mac-runtime/src/mac_runtime/canon.py"
)

BEGIN = "<!-- BEGIN generated: canon tree (tools/gen_canon_index.py) -->"
END = "<!-- END generated: canon tree -->"


def runtime_lists() -> tuple[set[str], set[str], bool]:
    """(implemented, known_unimplemented, found). Parsed as text; no import across the boundary."""
    if not RUNTIME.is_file():
        return set(), set(), False
    src = RUNTIME.read_text(encoding="utf-8")
    out = []
    for block in ("IMPLEMENTED", "KNOWN_UNIMPLEMENTED"):
        marker = block + ": dict[str, str] = {"
        if marker not in src:
            return set(), set(), False
        seg = src.split(marker, 1)[1]
        seg = seg[: seg.find("\n}")]
        out.append({n.replace("mac.canon.", "") for n in re.findall(r'"(mac\.canon\.[a-z_]+)"', seg)})
    return out[0], out[1], True


def terms() -> dict[str, dict]:
    block = (yaml.safe_load(VOCAB.read_text(encoding="utf-8")) or {}).get("canon") or {}
    t = block.get("terms") or {}
    bad = sorted(n for n, b in t.items() if not isinstance(b, dict))
    if bad:
        # A TERM WITH NO FIELDS HAS NO GROUP, so the tree cannot be built from it. This is the exact
        # defect `ratio_select` carried for three days: authored as a bare string, it declared no
        # `serves`, and every reader that asked the term a question got nothing.
        raise SystemExit(
            f"REFUSED: canon.terms {bad} are not mappings, so they declare no `serves` and the "
            f"tree has nowhere to put them. A canon term declares serves, needs_sqlglot and doc."
        )
    return t


def render() -> str:
    t = terms()
    impl, unimpl, found = runtime_lists()
    described = {p.stem for p in PAGES_DIR.rglob("*.md") if p.stem != "README"}
    patterns = {p.stem for p in PATTERNS_DIR.glob("*.md")}

    groups: dict[str, list[str]] = {}
    for name, body in t.items():
        groups.setdefault(str(body.get("serves") or "(undeclared)"), []).append(name)
    # BIGGEST GROUP FIRST, then alphabetically — a stable order, so a regeneration that changes
    # nothing produces no diff.
    order = sorted(groups, key=lambda g: (-len(groups[g]), g))

    L: list[str] = [BEGIN, ""]
    L.append(f"**{len(t)} canons across {len(order)} patterns.** The middle layer is not a filing "
             f"choice: it is each canon's own `serves`, the data pattern it exists for, which also "
             f"names its page under [`patterns/`](../patterns/). A canon changes group by changing that "
             f"declaration.")
    L.append("")
    if found:
        L.append(f"| | defined | described | implemented |")
        L.append(f"|---|---|---|---|")
        L.append(f"| **count** | {len(t)} | {len(described & set(t))} | {len(impl)} |")
        L.append(f"| **read from** | `mac_vocabulary.yaml#canon.terms` | "
                 f"`rules_and_canons/**/*.md` | `mac_runtime.canon.IMPLEMENTED` |")
        L.append("")
        L.append("`tools/check_canon_documented.py` holds the three together; this table is read "
                 "from the same places it reads.")
    else:
        L.append("> The runtime could not be read, so no implementation status is shown rather than "
                 "a guessed one.")
    L.append("")

    for g in order:
        members = sorted(groups[g])
        link = f"[`{g}`](../patterns/{g}.md)" if g in patterns else f"`{g}`"
        # FOLDABLE, so twelve groups are a page you can scan rather than scroll. `<details>` is the
        # one collapsible GitHub-flavoured markdown admits, and it needs the blank lines around the
        # table or the markdown inside a block-level HTML element is rendered as literal text.
        # OPEN BY DEFAULT on the largest group only: a page whose every group is shut shows a reader
        # nothing, and one whose every group is open is the flat list this replaced.
        L.append(f"<details{' open' if len(members) > 2 else ''}>")
        L.append(f"<summary><b>{g}</b> &nbsp;·&nbsp; {len(members)} canon"
                 f"{'s' if len(members) != 1 else ''}</summary>")
        L.append("")
        L.append(f"Pattern: {link}")
        L.append("")
        # NO DEFINITION TEXT HERE, DELIBERATELY. Each canon's meaning is rendered once, lower on this
        # page, by gen_vocabulary_terms.py reading the same vocabulary. Excerpting it into the tree
        # would make the tree a second home for a sentence that already has one, and the two would
        # drift the moment someone edited the shorter copy. The tree carries NAVIGATION and STATUS.
        L.append("| canon | long form | definition | runtime | sqlglot |")
        L.append("|---|---|---|---|---|")
        for n in members:
            body = t[n]
            page = f"[page]({g}/{n}.md)" if n in described else "—"
            if not found:
                status = "—"
            elif n in impl:
                status = "**acts**"
            elif n in unimpl:
                status = "declared only"
            else:
                status = "unknown"
            sqlglot = "yes" if body.get("needs_sqlglot") else "no"
            L.append(f"| `{n}` | {page} | [below](#maccanon{n.replace('_', '')}) | {status} | {sqlglot} |")
        L.append("")
        L.append("</details>")
        L.append("")

    L.append(END)
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    page = PAGE.read_text(encoding="utf-8")
    if BEGIN not in page or END not in page:
        print(f"REFUSED: {PAGE.name} carries no generated region. Add the two sentinels:\n"
              f"  {BEGIN}\n  {END}")
        return 2
    head, rest = page.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    fresh = render()
    rebuilt = head + fresh + tail

    if args.check:
        if rebuilt == page:
            print(f"PASS: gen_canon_index --check — {PAGE.name}'s canon tree matches the declarations.")
            return 0
        print(f"FAIL: {PAGE.name}'s canon tree has drifted from mac_vocabulary.yaml#canon.terms "
              f"and/or the runtime registry. Run: python3 tools/gen_canon_index.py")
        return 1

    if rebuilt == page:
        print(f"PASS: gen_canon_index — {PAGE.name} already current, nothing written.")
        return 0
    PAGE.write_text(rebuilt, encoding="utf-8")
    t = terms()
    groups = len({str(b.get("serves")) for b in t.values()})
    print(f"PASS: gen_canon_index — wrote {PAGE.name}: {len(t)} canons in {groups} groups.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
