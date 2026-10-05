#!/usr/bin/env python3
"""check_prose_ratio — how much of a concept document is prose, against how much is declaration.

WHY, AND IT IS A MEASUREMENT BEFORE IT IS A GATE. The operator, 2026-10-05: "some of them which were
heavily worked on have 2x more prosa then the fomal text. this is unreadabl for human ... when i am
reading prosa i make myself opionion not as each line translates into something but how the whole
something work ... then i compare yaml formal format with my understanding of the rule. the way how
it is now ... it is hardly possible."

That is a VERIFICATION being described, not a preference: the prose is read whole to form a view of
what a rule does, and the formal notation is then compared against that view. Interleaving makes both
halves unreadable as wholes, so the comparison cannot be made. The same check exists mechanically in
check_canon_binding -- prose against what its canon renders, by meaning -- for 3 of 21 canons, so a
person is doing by hand across every concept what exists for three.

Measured on contoso5 by THIS tool when it was written: 2,05x overall against a claim of 2x; store
8,00x, country 5,36x, order 3,39x, those three carrying 60 % of the bundle's prose; and the concepts
nobody
has fought over at 0,25x, which makes that a DEMONSTRATED floor rather than an aspiration. 9 031
bytes were YAML comments, 6 042 of them in one file -- prose with no reader at all, invisible to every
gate and impossible to compare against anything.

NO THRESHOLD, DELIBERATELY. This exits 0 and reports. A number chosen before the first three concepts
are converted would be taste; the plan (decisions/PROPOSED-2026-10-05_prose-formal-separation.md,
Phase 3) sets it from the achieved corpus against the 0,25x floor. Until then a gate that FAILED here
would fail on every bundle and teach everyone to ignore it.

WHAT COUNTS AS WHICH, and the rule is one question per line:
  comment   a `#` line. Not data, not projected, read by nothing.
  prose     a block scalar's body (`>` / `|`), or an inline value longer than PROSE_CHARS.
  formal    a key, a short value, a list item -- the skeleton a reader is trying to scan.
A short value is formal because `class: measure` IS the declaration; a paragraph in the same slot is
not a longer declaration, it is a different kind of content. the_content_model.md §2 draws that line
by asking whether two competent models could produce different query behaviour from the slot.

DISCOVERY GOES THROUGH THE LAYOUT RESOLVER, never a hand-written glob. check_canon_binding records
why: globbing `ontology/concepts/*.yaml` "measured ZERO on every foldered bundle and printed a clean
verdict", which is the shape of gate this one is trying not to be.

Contract: one PASS:/FAIL: line, exit 0 or 1, exit 2 when it could not run, denominators printed,
and `--self-test` with one mutant per measurement class.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_project as P  # noqa: E402  — ONE home for where a bundle keeps its concepts

#: An inline value longer than this is prose. 90 is not a ruling: it is wider than every declared
#: enum member, path and vocabulary reference measured on contoso5, and narrower than every sentence.
#: It is reported in the verdict so a reader can see what the figure was computed with.
PROSE_CHARS = 90

_KEY = re.compile(r"^(?:-\s*)?([A-Za-z0-9_\-]+):\s*(.*)$")
_BLOCK = {">", "|", ">-", "|-", ">+", "|+"}


def split_bytes(text: str) -> tuple[int, int, int]:
    """(comment, prose, formal) bytes of one concept document."""
    comment = prose = formal = 0
    in_block = False
    block_indent = 0
    for raw in text.splitlines():
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if in_block:
            # A block scalar ends at the first non-empty line indented no deeper than its key.
            if stripped and indent <= block_indent:
                in_block = False
            else:
                prose += len(stripped)
                continue
        if not stripped:
            continue
        if stripped.startswith("#"):
            comment += len(stripped)
            continue
        m = _KEY.match(stripped)
        if m and m.group(2).strip() in _BLOCK:
            in_block = True
            block_indent = indent
            formal += len(m.group(1)) + 1
            continue
        if m:
            key, value = m.group(1), m.group(2).strip()
            formal += len(key) + 1
            if len(value) > PROSE_CHARS:
                prose += len(value)
            else:
                formal += len(value)
            continue
        formal += len(stripped)
    return comment, prose, formal


def measure(root: pathlib.Path) -> list[tuple[str, int, int, int]]:
    rows = []
    for f in P.concept_files(root):
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        c, p, s = split_bytes(text)
        rows.append((f.stem, c, p, s))
    return rows


def report(rows: list[tuple[str, int, int, int]]) -> None:
    rows = sorted(rows, key=lambda r: -((r[1] + r[2]) / r[3] if r[3] else 0))
    print(f"{'concept':26s} {'comment':>8s} {'prose':>8s} {'formal':>8s}   ratio")
    for name, c, p, s in rows:
        ratio = (c + p) / s if s else 0.0
        print(f"{name:26s} {c:8d} {p:8d} {s:8d}   {ratio:5.2f}x")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    try:
        rows = measure(root)
    except Exception as exc:  # noqa: BLE001
        print(f"REFUSED: could not read {root}'s concepts: {exc}")
        return 2
    # ZERO IS NOT A SCORE. A run that found no concept has measured no document, and saying 0,00x
    # over an empty population is the verdict this estate names most often as the real defect.
    if not rows:
        print(f"REFUSED: no concept document under {P.concepts_dir(root)} — nothing to measure")
        return 2

    report(rows)
    c = sum(r[1] for r in rows)
    p = sum(r[2] for r in rows)
    s = sum(r[3] for r in rows)
    ranked = sorted(rows, key=lambda r: -(r[1] + r[2]))
    worst = max(rows, key=lambda r: (r[1] + r[2]) / r[3] if r[3] else 0)
    wr = (worst[1] + worst[2]) / worst[3] if worst[3] else 0
    #: THE TOP THREE'S SHARE IS THE FIGURE THAT DRIVES THE WORK, not the worst single ratio. Measured
    #: on contoso5: three files hold 60 % of the prose, which is why the plan's pilot is three files
    #: and not seventeen. A ratio says which file is worst; this says how much of the problem it is.
    top3 = sum(r[1] + r[2] for r in ranked[:3])
    share = top3 / (c + p) * 100 if (c + p) else 0
    names = ", ".join(r[0] for r in ranked[:3])
    print(
        f"\nPASS: check_prose_ratio — {(c + p) / s:.2f}x over {len(rows)} concept(s): "
        f"{c + p} byte(s) of prose+comment ({c} in comments) against {s} of declaration. "
        f"Worst {worst[0]} at {wr:.2f}x; the top three ({names}) hold {share:.0f}% of all prose. "
        f"Inline prose threshold {PROSE_CHARS} chars. NO THRESHOLD IS ENFORCED YET — "
        f"PROPOSED-2026-10-05_prose-formal-separation.md Phase 3 sets it from the achieved corpus."
    )
    return 0


def _self_test() -> int:
    checks = 0
    bad: list[str] = []

    def expect(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            bad.append(msg)

    # one mutant per measurement class, each against the class it must NOT be counted as
    c, p, s = split_bytes("# a comment that is only a comment\nclass: measure\n")
    expect(c == len("# a comment that is only a comment"), f"a `#` line is comment, got {c}")
    expect(p == 0, f"a `#` line is not prose, got {p}")

    c, p, s = split_bytes("class: measure\n")
    expect(p == 0 and c == 0 and s > 0, f"a short value is formal, got comment={c} prose={p}")

    long = "x" * (PROSE_CHARS + 1)
    c, p, s = split_bytes(f"definition: {long}\n")
    expect(p == len(long), f"an inline value over {PROSE_CHARS} is prose, got {p}")

    c, p, s = split_bytes("definition: >\n  one line of narrative\n  and a second\nclass: measure\n")
    expect(p > 0, "a block scalar's body is prose")
    expect("class" not in ("",) and s > 0, "a key after a block scalar is still formal")
    c2, p2, s2 = split_bytes("definition: >\n  only narrative\n")
    expect(p2 > 0 and s2 == len("definition:"), f"the block's key is formal, body is not: {s2}")

    # a run over no concept must REFUSE, never report 0,00x
    with tempfile.TemporaryDirectory() as tmp:
        empty = pathlib.Path(tmp)
        (empty / "ontology" / "concepts").mkdir(parents=True)
        expect(main([str(empty)]) == 2, "an empty population must refuse, not pass")

    if bad:
        for b in bad:
            print(f"  [SELF-TEST] {b}")
        print(f"FAIL: check_prose_ratio self-test — {len(bad)} of {checks} check(s) failed")
        return 1
    print(f"PASS: check_prose_ratio self-test — {checks}/{checks} check(s) over 4 measurement class(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
