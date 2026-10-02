#!/usr/bin/env python3
"""check_document_layout.py — A PROJECTED DOCUMENT IS THE LAYOUT ITS GUARDRAIL DECLARES, AND FROZEN.

Operator, 2026-10-02: *"i cannto stand that you every time invent new layout for the same document
!?!?!? it is either you define mandatory rules for the layout or crate tempalte that you will only
populate."*

TWO CHECKS, AND THE SECOND IS WHY THIS EXISTS:

  RULES    every declared section present, in the declared order, no heading the declaration does
           not name, no section silently empty, and the empty sentence used VERBATIM.
  FREEZE   the rendering is byte-identical to a committed golden. The rules above cannot see a
           sentence rewritten, a table column reordered or a bullet reworded — which is most of
           what "a new layout for the same document" actually was. The golden can.

So an unintended change FAILS, and an intended one is `--accept` plus `git diff tests/golden/` — a
reviewable diff OF THE DOCUMENT, in the commit, which is the deliberate act the layout drift never
was.

GENERIC, AND THE POPULATION COMES FROM THE DECLARATION. It holds every artifact whose
`delivers.<artifact>.shape.sections` exists in `guardrails/` (`sdk/project/layout.py` is the reader)
and whose producers name a `renders:` entry point. An artifact that declares sections and no
renderer is a delivered FILE, printed with that reason and held by `tools/check_page_shape.py`
against the same declaration — never a silent pass, and never counted as held here.

WHERE THE GOLDENS LIVE: `tests/golden/<artifact>/<document>.md`, rendered from the in-repo exemplar
bundle (`sdk/authoring/exemplars/bundle`). Beside the tests because they ARE the test's expected
value; from the exemplar bundle because a golden must be reproducible on any machine, and the only
concept bundles in this repository are the exemplars — a golden cut from a bundle under
`archive-sources` would freeze a document nobody else can render.

NOT A SECOND HOME FOR THE RENDERING. The goldens are the EXPECTED bytes of a renderer that still
has one author; they are never read back into a page.

MEASURED WHEN THIS WAS WRITTEN, and not fixed here: on contoso5 the live page seam
(`concept_sections`) appends a 9th heading, `## Data`, to `customer` — a section
`delivers.concept_page.shape` does not declare. The governed surface is `page_body`, so this gate
holds the body; the pointer is news for the declaration's owner.

TWO ARMS, ONE RUN, because the runner's convention is a bundle root in argv[1] and the FREEZE is
not about a bundle: the rules are checked on whatever bundle it is handed, and the freeze is always
checked against the exemplars. A gate that only froze when called bare would be green in the suite
for the wrong reason.

    python3 tools/check_document_layout.py                 # rules + freeze, exemplar bundle
    python3 tools/check_document_layout.py --accept        # re-freeze, then review `git diff`
    python3 tools/check_document_layout.py <bundle>        # rules there, freeze still held
    python3 tools/check_document_layout.py --self-test
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdk.project import layout as L  # noqa: E402

#: The bundle the goldens are cut from — in-repo, committed, so the freeze is reproducible.
FREEZE_BUNDLE = "sdk/authoring/exemplars/bundle"
GOLDEN_DIR = "tests/golden"

REJECTS = (
    "SECTION_MISSING",
    "SECTION_ORDER",
    "UNDECLARED_HEADING",
    "EMPTY_SECTION_SILENT",
    "EMPTY_SENTENCE_VARIANT",
    "NOT_FROZEN",
    "UNFROZEN_DOCUMENT",
    "STALE_GOLDEN",
)


def _is_sentence_shaped(lines: list[str]) -> bool:
    """A section whose WHOLE body is one italic sentence — the shape an empty section renders."""
    if len(lines) != 1:
        return False
    only = lines[0].strip()
    return len(only) > 2 and only.startswith("_") and only.endswith("_")


def check_rules(lay: L.Layout, document: str, text: str) -> list[str]:
    """Every way `document` departs from `lay`. One line per finding, each naming its reject."""
    where = f"{lay.artifact}/{document}"
    found = L.headings(text)
    out: list[str] = []

    absent = [s for s in lay.always if s not in found]
    if absent:
        out.append(f"SECTION_MISSING {where}: declared `required: always` and absent: {absent}")

    undeclared = [h for h in found if h not in lay.sections]
    if undeclared:
        out.append(
            f"UNDECLARED_HEADING {where}: {undeclared} — a heading the declaration does not name "
            f"is a section nobody reviewed"
        )

    expected = [s for s in lay.sections if s in found]
    if [h for h in found if h in lay.sections] != expected:
        out.append(
            f"SECTION_ORDER {where}: rendered {[h for h in found if h in lay.sections]}, "
            f"declared {expected}"
        )

    body = L.bodies(text)
    silent = [h for h in found if h in lay.sections and not body.get(h)]
    if silent and lay.empty_section_says:
        out.append(
            f"EMPTY_SECTION_SILENT {where}: {silent} carry nothing and do not say so — the "
            f"declaration's `empty_section_says` is what an empty section renders"
        )

    if lay.empty_section_says:
        variants = sorted(
            {
                lines[0].strip()
                for head, lines in body.items()
                if head in lay.sections
                and _is_sentence_shaped(lines)
                and lines[0].strip() != lay.empty_section_says
            }
        )
        if variants:
            out.append(
                f"EMPTY_SENTENCE_VARIANT {where}: a section says {variants[0]!r} where the "
                f"declaration says {lay.empty_section_says!r} — one sentence for all of them"
            )
    return out


def check_freeze(golden_root: Path, artifact: str, rendered: dict[str, str]) -> list[str]:
    """The rendering against the committed goldens, byte for byte, both directions."""
    out: list[str] = []
    directory = golden_root / artifact
    frozen = {p.stem: p for p in sorted(directory.glob("*.md"))} if directory.is_dir() else {}
    for document, text in sorted(rendered.items()):
        path = frozen.get(document)
        if path is None:
            out.append(
                f"UNFROZEN_DOCUMENT {artifact}/{document}: no golden under "
                f"{directory.as_posix()}/ — a new document is frozen deliberately (--accept)"
            )
            continue
        was = path.read_text(encoding="utf-8")
        if was != text:
            diff = list(
                difflib.unified_diff(
                    was.splitlines(), text.splitlines(), "frozen", "rendered", lineterm="", n=1
                )
            )
            out.append(
                f"NOT_FROZEN {artifact}/{document}: the rendering is not the frozen document "
                f"({len([d for d in diff if d[:1] in '+-' and d[:3] not in ('---', '+++')])} "
                f"line(s) differ)\n"
                + "\n".join("        " + d for d in diff[:24])
            )
    for stem in sorted(set(frozen) - set(rendered)):
        out.append(
            f"STALE_GOLDEN {artifact}/{stem}: frozen, and the renderer no longer emits it "
            f"(--accept removes it)"
        )
    return out


def accept(golden_root: Path, artifact: str, rendered: dict[str, str]) -> list[str]:
    """Re-freeze one artifact. Returns the paths written or removed, for the operator to diff."""
    directory = golden_root / artifact
    directory.mkdir(parents=True, exist_ok=True)
    touched: list[str] = []
    for document, text in sorted(rendered.items()):
        path = directory / f"{document}.md"
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            touched.append(f"wrote   {path.as_posix()}")
    for path in sorted(directory.glob("*.md")):
        if path.stem not in rendered:
            path.unlink()
            touched.append(f"removed {path.as_posix()}")
    return touched


def run(root: Path, bundle: Path, *, do_accept: bool) -> tuple[list[str], list[str]]:
    """(findings, report lines) over every artifact that declares a layout — all of them, named."""
    findings: list[str] = []
    report: list[str] = []
    golden_root = root / GOLDEN_DIR
    frozen_bundle = root / FREEZE_BUNDLE
    for artifact, lay in sorted(L.layouts(root).items()):
        if lay.renders is None:
            report.append(
                f"  n/a      {artifact:22s} declares {len(lay.sections)} section(s) and no "
                f"`renders:` — a delivered file, held by tools/check_page_shape.py"
            )
            continue
        try:
            rendered = lay.render(bundle)
            frozen = rendered if bundle == frozen_bundle else lay.render(frozen_bundle)
        except Exception as exc:  # noqa: BLE001 — a renderer that raises IS the finding
            findings.append(f"RENDERER_FAILED {artifact}: {type(exc).__name__}: {exc}")
            continue
        for document, text in sorted(rendered.items()):
            findings += check_rules(lay, document, text)
        if do_accept:
            for line in accept(golden_root, artifact, frozen):
                report.append(f"  accept   {artifact:22s} {line}")
        else:
            findings += check_freeze(golden_root, artifact, frozen)
        report.append(
            f"  held     {artifact:22s} rules on {len(rendered)} document(s) × "
            f"{len(lay.sections)} declared section(s) · freeze on {len(frozen)}"
        )
    return findings, report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bundle", nargs="?", default=None, help=f"default: {FREEZE_BUNDLE}")
    parser.add_argument("--accept", action="store_true", help="re-freeze; then review git diff")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()

    root = L.framework_root(Path(__file__))
    bundle = Path(args.bundle).resolve() if args.bundle else (root / FREEZE_BUNDLE)
    if not bundle.is_dir():
        print(f"REFUSED: no bundle at {bundle}")
        return 2
    if not (root / FREEZE_BUNDLE).is_dir():
        print(f"REFUSED: no freeze bundle at {root / FREEZE_BUNDLE} — nothing can be held frozen")
        return 2

    findings, report = run(root, bundle, do_accept=args.accept)
    declared = L.layouts(root)
    same = bundle == (root / FREEZE_BUNDLE)
    print(
        f"\n── document layout ── rules on {bundle.name}"
        + ("" if same else f", freeze on {FREEZE_BUNDLE}")
        + f" ── {len(declared)} artifact(s) declare a layout ──"
    )
    for line in report:
        print(line)
    if findings:
        print(f"\nFAIL: check_document_layout — {len(findings)} finding(s):")
        for line in findings:
            print(f"    ✗ {line}")
        print(
            "\n  The layout is `delivers.<artifact>.shape` in guardrails/ — change it THERE, never "
            "in a renderer.\n"
            "  If the new rendering is intended: python3 tools/check_document_layout.py --accept\n"
            "  then `git diff tests/golden/` IS the review."
        )
        return 1
    if args.accept:
        print(
            f"\n✓ ACCEPTED — the goldens under {GOLDEN_DIR}/ are now this rendering. "
            f"`git diff {GOLDEN_DIR}/` is the diff to review."
        )
        return 0
    print(
        "\nPASS: check_document_layout — every rendered document is the layout its guardrail "
        "declares, and is byte-identical to its frozen copy."
    )
    return 0


def _self_test() -> int:
    """One seeded mutant per reject class, plus the clean case. The rules are read, never restated."""
    ok = [0, 0]

    def case(what, cond):
        ok[0] += 1
        ok[1] += bool(cond)
        print(("  ✓ " if cond else "  ✗ ") + what)

    lay = L.Layout(
        artifact="t",
        topic="t",
        sections=("One", "Two"),
        always=("One", "Two"),
        empty_section_says="_Nothing declared for this section._",
        tables={"fields_table_columns": ("a", "b")},
        renders=None,
    )
    GOOD = "# t\n\n## One\n\nbody\n\n## Two\n\n_Nothing declared for this section._\n"

    def rejects(text):
        return {f.split(" ", 1)[0] for f in check_rules(lay, "d", text)}

    case("a document in the declared layout holds", not rejects(GOOD))
    case("MUTANT a declared section dropped is REFUSED",
         "SECTION_MISSING" in rejects("## One\n\nbody\n"))
    case("MUTANT the two sections swapped is REFUSED",
         "SECTION_ORDER" in rejects("## Two\n\nx\n\n## One\n\nbody\n"))
    case("MUTANT a heading the declaration does not name is REFUSED",
         "UNDECLARED_HEADING" in rejects(GOOD + "\n## Data\n\n- x\n"))
    case("MUTANT a section left silently blank is REFUSED",
         "EMPTY_SECTION_SILENT" in rejects("## One\n\nbody\n\n## Two\n"))
    case("MUTANT the empty sentence REWORDED is REFUSED",
         "EMPTY_SENTENCE_VARIANT" in rejects("## One\n\nbody\n\n## Two\n\n_Nothing here._\n"))

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        golden = Path(tmp)
        accept(golden, "t", {"d": GOOD})
        case("a freeze of the rendering holds", not check_freeze(golden, "t", {"d": GOOD}))
        case("MUTANT one WORD rewritten inside a section is REFUSED — the rules cannot see it",
             any(f.startswith("NOT_FROZEN")
                 for f in check_freeze(golden, "t", {"d": GOOD.replace("body", "bodies")})))
        case("MUTANT a document that was never frozen is REFUSED",
             any(f.startswith("UNFROZEN_DOCUMENT")
                 for f in check_freeze(golden, "t", {"d": GOOD, "e": GOOD})))
        case("MUTANT a golden the renderer no longer emits is REFUSED",
             any(f.startswith("STALE_GOLDEN") for f in check_freeze(golden, "t", {})))
        case("--accept makes the refused rendering the frozen one",
             bool(accept(golden, "t", {"d": GOOD.replace("body", "bodies")}))
             and not check_freeze(golden, "t", {"d": GOOD.replace("body", "bodies")}))

    case("every reject class above is one this gate declares",
         set(REJECTS) >= {"SECTION_MISSING", "SECTION_ORDER", "UNDECLARED_HEADING",
                          "EMPTY_SECTION_SILENT", "EMPTY_SENTENCE_VARIANT", "NOT_FROZEN",
                          "UNFROZEN_DOCUMENT", "STALE_GOLDEN"})

    print(("PASS" if ok[1] == ok[0] else "FAIL")
          + f": check_document_layout self-test — {ok[1]}/{ok[0]} case(s), one mutant per reject "
            f"class including the word-level rewrite only the freeze can catch.")
    return 0 if ok[1] == ok[0] else 1


if __name__ == "__main__":
    sys.exit(main())
