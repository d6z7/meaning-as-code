#!/usr/bin/env python3
"""check_wiki_citations — does every citation on a compiled wiki page still resolve?

WHY THIS EXISTS
---------------
A compiled page is A CLAIM ABOUT A CODEBASE THAT MOVES. Code gets renamed, a docstring gets
reworded, a comment block gets deleted in a refactor that touched nothing else — and a page that was
hand-checked in September is false in October with nothing red anywhere. The page still reads
beautifully. That is the whole danger: prose does not rot visibly.

This is the mechanism `sdk/project/knowledge.py` argues for, turned on our own wiki:

    VERBATIM OR NOTHING. Every span rendered here is quoted from the extraction, never paraphrased.
    That is not stylistic: it makes the register mechanically verifiable — a gate can assert that
    each span still appears in the source, which is impossible once someone has summarised it.

That last clause is the reason the wiki quotes rather than summarises, and it is the reason this
file can exist at all. A SUMMARY CANNOT BE CHECKED AGAINST ITS SOURCE. There is no predicate for "is
this paraphrase still fair". There is a predicate for "does this string still appear at this
address", and it is cheap, total and blind to authorial intent — which is exactly what you want from
the thing standing between a knowledge base and quiet falsehood.

`sdk/project/knowledge.py` also draws the line this gate is careful not to cross:

    Judgement about WHICH statements are normative belongs in a separate claims layer, so that
    extraction and interpretation never blur.

So this gate judges RESOLUTION, never IMPORTANCE. Whether a page cites the right line is a human's
read; whether the line it cites still says what the page says it says is a machine's.

THE DENOMINATOR IS THE POINT
----------------------------
    N citation(s) across M page(s) resolved

and the number that matters most is not N, it is the count of pages contributing ZERO to N. A page
with no citations is prose pretending to be compiled knowledge. It is precisely what a
zero-denominator pass looks like in this domain: the gate sweeps it, finds nothing to check, and
without this rule would report it as clean. `tools/mac_public_floor.txt` states the estate's memory
of that failure mode — a floor above the measurement is "141 findings of silent headroom" — and the
wiki version of that headroom is an uncited page. It is therefore a FINDING, not a warning.

The same logic runs one level up, and the harness enforces it: citations are this gate's declared
YARDSTICK (`Outcome.secondary`). A wiki whose pages carry no citations at all resolves nothing, so
it exits 2 — could-not-run — carrying its findings into that line rather than reporting a tree it
never verified as green.

WHAT THIS GATE READS, AND WHO HANDED IT OVER
--------------------------------------------
`tools/mac_wiki.py` compiles the pages. It states, in its own docstring, the exact hole this file
fills — and it is the reason this gate reads the compiler's output rather than a grammar of its own:

    It does not verify that a `file:line` an entry cites still exists — it renders those citations
    and SAYS it has not checked them, because a claim this tool has not established must not be
    printed as if it had.

and on the page itself, under the table it renders:

    **This compiler does not verify that these still exist** — it establishes only that the quotes
    are verbatim. A citation gate over this table is a separate instrument.

This is that instrument. The seam is clean and neither side duplicates the other: `mac_wiki --check`
owns protocol-entry fidelity (the stamp, the source_hash, the verbatim quote blocks); this gate owns
whether what those entries POINT AT is still there.

So a citation is read from three places on a compiled page, and nothing is invented:

  1. the compiler stamp's `entries` list — every protocol entry the page was compiled from
  2. a row of the citations table, `| `TARGET` | `ENTRY` | ` — the compiler's own mechanical
     extraction of what the quoted text points at
  3. `[[cite: TARGET]]` inline — the SPAN-BEARING form, described below

and a TARGET is one of:

    sdk/project/knowledge.py:9          a source address, repo-relative
    sdk/project/knowledge.py:9-12       a source address spanning lines
    2026-09-13/001-slug                 a protocol entry id ('protocol/' prefix optional)
    decisions/2026-09-13_record.md#4.2  a decision record section, by number or by heading slug

FORM 3 EXISTS BECAUSE FORMS 1 AND 2 CANNOT CARRY A SPAN. A table row is an address and nothing more,
so the strongest thing that can be asserted about it is that the address still resolves. A page that
wants its QUOTE checked — the property this whole file argues for — has to put the quote next to the
address, and that is what the inline form is for. It is not a second grammar for the same thing; it
is the one shape in which the verbatim rule becomes checkable against source code:

    > VERBATIM OR NOTHING. Every span rendered here is quoted from the extraction, never
    > paraphrased.

    [[cite: sdk/project/knowledge.py:9]]

The blockquote immediately above (at most one blank line between) is the QUOTED SPAN. How many
citations carried one is PRINTED on every run, because the difference between "the address resolves"
and "the quote is still true" is the difference this gate exists to measure, and a run that checked
no spans must not be reported as if it had.

Citations are read OUTSIDE fenced code blocks only: a fenced citation is an example of the grammar,
not a use of it — this docstring's own examples would otherwise be resolved.

WHAT "VERBATIM" MEANS HERE, STATED EXACTLY
------------------------------------------
"Verbatim" with undisclosed normalisation is a lie, so: before comparison both sides are stripped of
LINE FURNITURE (`#`, `#:`, `//`, `*`, `>`, `\"\"\"`, `'''`) and all runs of whitespace collapse to one
space. Nothing else is touched — case, punctuation, wording and word order are compared exactly.

That is the minimum that makes the rule usable rather than theatrical. A page rewraps a quote to its
own column width and strips the `#:` off a comment block, because it is quoting the TEXT, not the
furniture; it does not get to change a word. `... ` (or `… `) inside a span is an ELISION and matches
any intervening text, so a page may quote the two halves of a sentence that matter. An extra in the
self-test proves both directions of exactly this: rewrapping is forgiven, one changed word is not.

WHERE A QUOTE MUST BE: A `file:line` CITATION ASSERTS THE QUOTE BEGINS ON THAT LINE. This is why
`line-moved` and `span-changed` are two classes and not one. A refactor that inserts an import above
a docstring leaves every quoted span intact and every address stale — a real defect, but a different
one from a reworded sentence, and a gate that reported them under one label would be unable to tell
you which of the two happened. `sdk/gate/demo_right_gate.py` is where that lesson is written down:
two labels have to be two predicates, or one predicate quietly covers for the other.

PREDICATE ORDER IS LOAD-BEARING, for the same reason. Containment is checked BEFORE existence,
because `../../outside/notes.py` also fails to exist — a gate that tested existence first would
report every escape as `file-missing` and its self-test would still look green.

PLACEMENT — why `tools/`, argued
--------------------------------
Beside `tools/check_protocol.py`, which is this gate's sibling: same subsystem (the knowledge
system: protocol in, wiki out), same scope (THIS repository, not a bundle), same shape. The two
gates answer the two halves of one question — check_protocol asks whether the raw record covers the
work, this asks whether the compiled record still quotes something real.

`tools/` is also where this estate's other repo-scoped gate lives (`check_mac_public.py`, which CI
invokes with no argument), and `wiki/README.md` already names `check_wiki_citations` — a document
that cites a gate should find it where the other thirty-five `check_*.py` gates live.

THE MEASURED COST OF THAT CHOICE, since it is not free. `tools/run_framework_gates.sh` globs
`check_*.py` and hands every one of them a BUNDLE root. A bundle has no `wiki/`, so this gate exits
2 there, and the runner counts a could-not-run against the aggregate. Measured on 2026-09-13,
before and after adding this file:

    FAIL: run_framework_gates — 30/35 green, 3 failing, 2 could-not-run over <a bundle> (13s)
    FAIL: run_framework_gates — 31/36 green, 3 failing, 2 could-not-run over <a bundle> (14s)

    check_grain_key_consistency.py             COULD-NOT-RUN
    check_wiki_citations.py                    COULD-NOT-RUN

The could-not-run count did not move: this gate took the slot `check_protocol.py` vacated when it
was repaired the same day. A REPO-SCOPED GATE IN A BUNDLE-SCOPED SWEEP is one fact about the runner,
not a defect in the gate, and the honest fix belongs in the runner — a scope column, so it stops
handing a bundle root to gates whose subject is the repository. What must not happen is the gate
being taught to answer "check the wiki in this bundle" with PASS. There isn't one. Exit 2 is the
only true answer, and this estate's memory of the alternative is `tools/mac_public_floor.txt`.

Contract: one PASS:/FAIL: line, exit 0 or 1, exit 2 for could-not-run, a printed denominator, and
`--self-test` with a mutant per reject class, attributed, via `sdk/gate/contract.py`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT_DEFAULT = Path(__file__).resolve().parent.parent

# `sdk.gate.contract` is the repaired harness and it lives beside this file's repo root, not on the
# path. `tools/run_framework_gates.sh` invokes checkers as bare scripts from an arbitrary cwd with
# no PYTHONPATH, so a gate that assumed the import would resolve would fail with a traceback and be
# counted as a plain failure rather than a could-not-run.
if str(ROOT_DEFAULT) not in sys.path:
    sys.path.insert(0, str(ROOT_DEFAULT))

from sdk.gate import contract  # noqa: E402

NAME = "check_wiki_citations"

#: The grammar, in one regex. `[[cite: TARGET]]` — deliberately not a markdown link: a citation that
#: renders invisibly is a citation a reader cannot audit, and one a compiler can forget to emit
#: without anyone noticing the page got quieter.
CITE_RE = re.compile(r"\[\[cite:\s*(?P<target>[^\]\n]+?)\s*\]\]")

#: `path:LINE` or `path:START-END`, anchored so a Windows drive letter or a URL cannot be mistaken
#: for a line number.
ADDR_RE = re.compile(r"^(?P<path>[^:]+):(?P<start>\d+)(?:-(?P<end>\d+))?$")

#: A protocol entry id: `YYYY-MM-DD/NNN-slug`, with the `protocol/` prefix optional because the
#: compiler stamp omits it and a page's prose tends to include it.
ENTRY_ID_RE = re.compile(r"^(?:protocol/)?\d{4}-\d{2}-\d{2}/[^/]+?(?:\.md)?$")

#: The compiler's page stamp. Its `entries` list is a citation set: a page IS its entries.
STAMP_RE = re.compile(r"^<!-- mac-wiki-stamp (\{.*\}) -->$", re.M)

#: A citations-table row: exactly two cells, each a single backticked token. Matched by SHAPE and
#: then filtered by CONTENT rather than by position under a heading — a gate anchored to a heading
#: string goes silently blind the day the heading is reworded, and silent blindness is the failure
#: mode this whole file exists to prevent.
TABLE_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*$")

#: Suffixes that make a bare token a PATH rather than prose. Mirrors the compiler's own extraction
#: set so the two instruments agree on what a citation even is.
SOURCE_SUFFIXES = (".py", ".md", ".yaml", ".yml", ".json", ".sh", ".txt", ".sql", ".toml")

#: Line furniture: what a page strips off when it quotes the TEXT of a comment or a docstring.
#: Spelled as a list rather than as one regex because THIS TUPLE IS THE DISCLOSURE — the docstring
#: promises exactly this set and nothing else, and a reader must be able to check that promise
#: without decoding escaped quotes inside a raw string.
FURNITURE = ("#:", "#", "//", "*", ">", '"""', "'''")
FURNITURE_RE = re.compile(r"^\s*(?:" + "|".join(re.escape(f) for f in FURNITURE) + r")\s?")

#: An elision in a quoted span. Matches any intervening text, in order.
ELISION_RE = re.compile(r"\s(?:\.\.\.|…)\s")

#: A fence opener/closer. Citations inside a fence are examples of the grammar, not uses of it.
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")

#: Inline code. USE versus MENTION, one level below the fence rule and forced by the same defect:
#: a page that DESCRIBES the citation grammar writes `[[cite: ...]]` in backticks, and a gate that
#: resolves it reports `'...' is cited but the cited file is gone`. The wiki must be able to write
#: about its own grammar without the gate treating the sentence as a claim.
INLINE_CODE_RE = re.compile(r"`[^`]*`")

#: A markdown ATX heading, and its optional leading section number (`## 4 · Title`, `### 4.2 Title`).
HEADING_RE = re.compile(r"^(?P<hashes>\#{1,6})\s+(?P<text>.+?)\s*$")
SECNUM_RE = re.compile(r"^(?P<num>\d[\w.]*?)\.?(?:\s|$)")

#: A README is a section's own signpost — hand-written by definition, and not a compiled page. The
#: precedent is `tools/check_protocol.py`, which skips README.md when collecting protocol entries.
#: Skipped pages are COUNTED AND PRINTED, because "write your prose in README.md" is the obvious way
#: to escape this gate and the only defence against it is that the escape is visible.
SIGNPOST = "README.md"


# -------------------------------------------------------------------------------------------------
# normalisation — the disclosed part of "verbatim"
# -------------------------------------------------------------------------------------------------


#: How many furniture prefixes may be peeled from one line. Quoting NESTS: a page quotes a protocol
#: entry, and that entry was already quoting a source, so the page carries `> > text` where the
#: entry carries `> text` and the source carries `text`. Peeling once made every nested quote on
#: the real wiki report as `span-changed` — 227 findings, none of them true, from a gate that was
#: right about the rule and wrong about the depth.
_MAX_PEEL = 8


def norm_line(text: str) -> str:
    """One source or quote line, stripped of furniture, whitespace-collapsed. Nothing else.

    Peeled repeatedly rather than once, and SYMMETRICALLY on both sides, so that quote depth is
    never mistaken for a change of wording. `>` is furniture wherever it appears in the stack; the
    words after it are the claim.
    """
    for _ in range(_MAX_PEEL):
        peeled = FURNITURE_RE.sub("", text)
        if peeled == text:
            break
        text = peeled
    return re.sub(r"\s+", " ", text).strip()


def norm_span(lines: list[str]) -> str:
    """A quoted block, as one normalised string."""
    return " ".join(p for p in (norm_line(ln) for ln in lines) if p)


def line_index(text: str) -> tuple[str, list[int], list[int]]:
    """(joined normalised text, per-line start offset into it, per-line normalised length).

    Building the index rather than joining-then-searching is what lets `line-moved` be a real
    predicate: the question is not "is the span in this file" but "does it BEGIN on the cited line",
    and that needs each line's own extent in the normalised stream.
    """
    joined: list[str] = []
    starts: list[int] = []
    lengths: list[int] = []
    pos = 0
    for raw in text.splitlines():
        n = norm_line(raw)
        starts.append(pos)
        lengths.append(len(n))
        if n:
            joined.append(n)
            pos += len(n) + 1
    return " ".join(joined), starts, lengths


def _needles(span: str) -> list[str]:
    return [p for p in (s.strip() for s in ELISION_RE.split(span)) if p]


def find_ordered(hay: str, needles: list[str], start: int = 0) -> int:
    """Offset where the FIRST needle matches with the rest following in order, or -1."""
    if not needles:
        return -1
    at = start
    first = -1
    for i, nd in enumerate(needles):
        k = hay.find(nd, at)
        if k < 0:
            return -1
        if i == 0:
            first = k
        at = k + len(nd)
    return first


def begins_within(hay: str, needles: list[str], lo: int, length: int) -> bool:
    """Does an in-order match of `needles` BEGIN inside [lo, lo+length)?

    `length == 0` is a blank cited line and can never anchor a span. Without that guard an inserted
    blank line above a quote would pass: a blank line contributes nothing to the normalised stream,
    so the real text starts at the same offset and the address is off by one with nothing to show
    for it.
    """
    if length <= 0 or not needles:
        return False
    k = lo
    while True:
        k = hay.find(needles[0], k)
        if k < 0 or k >= lo + length:
            return False
        if find_ordered(hay, needles, k) == k:
            return True
        k += 1


# -------------------------------------------------------------------------------------------------
# reading pages
# -------------------------------------------------------------------------------------------------


def pages(wiki_root: Path) -> tuple[list[Path], list[Path]]:
    """(compiled pages, skipped signposts)."""
    if not wiki_root.is_dir():
        return [], []
    found, skipped = [], []
    for p in sorted(wiki_root.rglob("*.md")):
        (skipped if p.name == SIGNPOST else found).append(p)
    return found, skipped


def looks_like_target(tok: str) -> bool:
    """Is this token a citation TARGET, or just a backticked word in a two-column table?

    Content filter, deliberately: it is what lets the table row be matched by shape without the
    gate having to trust a heading to still be spelled the way it was spelled today.
    """
    tok = tok.strip()
    if ENTRY_ID_RE.match(tok) or ADDR_RE.match(tok):
        return True
    head = tok.split("#", 1)[0]
    return head.endswith(SOURCE_SUFFIXES)


def citations(page_text: str) -> list[tuple[int, str, list[str]]]:
    """[(line number, target, quoted span lines)] for one page, from all three forms.

    Fenced regions are skipped for the inline form: a citation inside a fence is an example of the
    grammar rather than a use of it.
    """
    out: list[tuple[int, str, list[str]]] = []
    mentions = 0
    lines = page_text.splitlines()

    # form 1 — the compiler stamp. A page IS the entries it was compiled from, so a stamp naming
    # twelve entries is twelve citations. Reading this is what stops a properly compiled page that
    # happens to point at no source file from being reported as uncited prose.
    m = STAMP_RE.search(page_text)
    if m:
        try:
            stamp = json.loads(m.group(1))
        except ValueError:
            stamp = {}
        stamp_line = page_text[: m.start()].count("\n") + 1
        for eid in stamp.get("entries") or ():
            if isinstance(eid, str) and eid.strip():
                out.append((stamp_line, eid.strip(), []))

    fenced = False
    for i, raw in enumerate(lines):
        if FENCE_RE.match(raw):
            fenced = not fenced
            continue
        if fenced:
            continue

        # form 2 — a citations-table row.
        row = TABLE_ROW_RE.match(raw)
        if row and looks_like_target(row.group(1)):
            out.append((i + 1, row.group(1).strip(), []))
            continue

        # form 3 — the inline, span-bearing form. Mentions inside backticks are stripped first,
        # and a target that is not target-SHAPED is counted as a grammar example rather than
        # silently dropped — see `mentions` in the denominator.
        spoken = INLINE_CODE_RE.sub("", raw)
        hit = CITE_RE.search(spoken)
        if not hit:
            # Counted even when the whole token vanished with its backticks, so that "the gate
            # ignored something citation-shaped here" is a printed number rather than an
            # invisible decision.
            mentions += 1 if CITE_RE.search(raw) else 0
            continue
        if not looks_like_target(hit.group("target")):
            mentions += 1
            continue
        j = i - 1
        if j >= 0 and not lines[j].strip():
            j -= 1
        span: list[str] = []
        while j >= 0 and lines[j].lstrip().startswith(">"):
            span.insert(0, lines[j])
            j -= 1
        out.append((i + 1, hit.group("target"), span))
    return out, mentions


def headings(text: str) -> list[tuple[str, str]]:
    """[(section number or '', heading text)] outside fenced blocks.

    The fence exclusion is not hypothetical: a decision record in this tree opens a fenced block
    whose first line is `# sdk/connector/base.py   (TRACK B)`, which a naive scan reads as a level-1
    heading and would happily resolve a citation against.
    """
    out: list[tuple[str, str]] = []
    fenced = False
    for raw in text.splitlines():
        if FENCE_RE.match(raw):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = HEADING_RE.match(raw)
        if not m:
            continue
        body = m.group("text")
        num = SECNUM_RE.match(body)
        out.append((num.group("num").rstrip(".") if num else "", body))
    return out


def slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


# -------------------------------------------------------------------------------------------------
# the predicates — one per reject class, in the order that keeps them distinct
# -------------------------------------------------------------------------------------------------


def resolve_within(root: Path, rel: str) -> Path | None:
    """The cited path, or None when it escapes the repository root. Checked FIRST, always."""
    target = (root / rel).resolve()
    return target if target.is_relative_to(root.resolve()) else None


def check_citation(root: Path, target: str, span: list[str]) -> tuple[str, str] | None:
    """(reject class, message) or None when the citation resolves."""
    quoted = norm_span(span)

    # --- a protocol entry id ---------------------------------------------------------------------
    # ORDER IS THE WHOLE POINT HERE, and it was measured wrong first. An entry id and an address
    # INTO an entry file differ only by a `:23-40` suffix, so an entry-id test that runs first
    # claims `2026-09-12/002-slug.md:23-40` and reports a perfectly good line-anchored quote as a
    # dangling id — 200-odd findings of the wrong class, every one of them a lie about what broke.
    # An address is therefore recognised BEFORE an id, never after.
    if ENTRY_ID_RE.match(target) and not ADDR_RE.match(target):
        rel = target[len("protocol/"):] if target.startswith("protocol/") else target
        rel = rel[:-3] if rel.endswith(".md") else rel
        path = resolve_within(root, f"protocol/{rel}.md")
        if path is None:
            return "path-escapes-repo", f"{target!r} escapes the repository root"
        if not path.is_file():
            return "entry-dangling", f"no protocol entry {rel!r} — the id resolves to nothing"
        return None

    # --- a decision record section -------------------------------------------------------------
    if "#" in target and not ADDR_RE.match(target):
        rel, _, section = target.partition("#")
        path = resolve_within(root, rel)
        if path is None:
            return "path-escapes-repo", f"{rel!r} escapes the repository root"
        if not path.is_file():
            return "file-missing", f"{rel!r} is cited but the cited file is gone"
        want = section.strip()
        for num, text in headings(path.read_text(encoding="utf-8")):
            # Addressable BY NUMBER and BY SLUG, and the slug is taken with the number stripped
            # off. Section numbers get renumbered by the next insertion; a page that can only cite
            # `#4.2` goes red for an edit that changed nothing it quoted.
            bare = text[len(num):].lstrip(" .-\u00b7\u2014\u2013\t") if num and text.startswith(num) else text
            if want == num or slug(want) in {slug(text), slug(bare)}:
                return None
        return "decision-section-missing", f"{rel!r} has no section {want!r} — the record moved on"

    # --- a source address, with or without a line ------------------------------------------------
    m = ADDR_RE.match(target)
    rel = m.group("path") if m else target
    start = int(m.group("start")) if m else 0
    end = int(m.group("end") or start) if m else 0
    path = resolve_within(root, rel)
    if path is None:
        return "path-escapes-repo", f"{rel!r} escapes the repository root"
    if not path.is_file():
        return "file-missing", f"{rel!r} is cited but the cited file is gone"

    if not m:
        return None  # a bare path asserts only that the file is still there

    text = path.read_text(encoding="utf-8", errors="replace")
    total = len(text.splitlines())
    if start < 1 or end > total:
        return "line-missing", f"{rel} cites line {end} but the file has only {total} line(s)"
    if not quoted:
        return None  # an address with no quoted span asserts only that the address exists

    joined, starts, lengths = line_index(text)
    needles = _needles(quoted)
    if find_ordered(joined, needles, 0) < 0:
        return "span-changed", (
            f"the quoted span no longer appears in {rel} — the page still says it does"
        )
    if not begins_within(joined, needles, starts[start - 1], lengths[start - 1]):
        return "line-moved", (
            f"the quoted span is still in {rel} but no longer begins at line {start} — "
            f"the quote survived, the address did not"
        )
    return None



# -------------------------------------------------------------------------------------------------
# the sweep, and the denominator
# -------------------------------------------------------------------------------------------------


class Result:
    """What one sweep found. Kept as an object so the verdict line and the findings are computed
    from ONE pass — a gate whose printed numbers come from a second, independent traversal can
    disagree with itself, and the reader has no way to tell which half is true."""

    __slots__ = ("found", "pages", "citations", "resolved", "spans", "mentions", "signposts")

    def __init__(self, found, pages_, citations_, resolved, spans, mentions, signposts):
        self.found = found
        self.pages = pages_
        self.citations = citations_
        self.resolved = resolved
        #: how many citations carried a quoted span, i.e. how many had their QUOTE checked and not
        #: merely their address. Printed on every run: a gate that checked no span has established
        #: that the addresses resolve, which is a strictly weaker claim than the one this file
        #: argues for, and the reader is entitled to know which of the two they are holding.
        self.spans = spans
        #: citation-shaped tokens that were MENTIONED rather than used. Counted, never silent: a
        #: skip nobody prints is a hole nobody can find.
        self.mentions = mentions
        self.signposts = signposts


def judge(root: Path) -> Result:
    found: list[tuple[str, str]] = []
    page_files, skipped = pages(root / "wiki")
    total = resolved = spans = mentions = 0

    for page in page_files:
        try:
            shown = page.relative_to(root)
        except ValueError:                                                     # pragma: no cover
            shown = page
        cites, said = citations(page.read_text(encoding="utf-8", errors="replace"))
        mentions += said
        if not cites:
            # NOT a warning. A page that cites nothing has no claim this gate can check, and
            # reporting it as clean is the zero-denominator pass in its purest form.
            found.append((
                "page-uncited",
                f"{shown} carries NO citation — prose pretending to be compiled knowledge",
            ))
            continue
        for lineno, target, span in cites:
            total += 1
            if norm_span(span):
                spans += 1
            bad = check_citation(root, target, span)
            if bad is None:
                resolved += 1
            else:
                found.append((bad[0], f"{shown}:{lineno} — {bad[1]}"))
    return Result(found, len(page_files), total, resolved, spans, mentions, len(skipped))


def outcome(res: Result) -> contract.Outcome:
    return contract.Outcome(
        len(res.found),
        res.pages,
        "page(s)",
        classes={cls for cls, _ in res.found},
        # Citations are the YARDSTICK; pages are the population. Backwards, a wiki full of pages
        # that cite nothing would report as a clean tree it had verified in no single respect.
        secondary=(res.citations, "citation(s) checked"),
    )


def detail(res: Result) -> str:
    uncited = sum(1 for cls, _ in res.found if cls == "page-uncited")
    out = f"{res.resolved} of {res.citations} citation(s) across {res.pages} page(s) resolved"
    out += (
        f"; {res.spans} carried a quoted span checked VERBATIM"
        if res.spans
        else "; 0 carried a quoted span — addresses resolve, no quote was verified"
    )
    if uncited:
        out += f"; {uncited} page(s) carry NO citation"
    if res.mentions:
        out += f"; {res.mentions} grammar example(s) mentioned, not resolved"
    if res.signposts:
        # Disclosed, not silent. "Put the prose in README.md" is the obvious way around this gate,
        # and the only thing that stops it is that the count is printed every single run.
        out += f"; {res.signposts} README signpost(s) skipped, not compiled pages"
    return out


def verdict_of(root: Path) -> tuple[str, int]:
    res = judge(root)
    return contract.verdict(NAME, outcome(res), detail=detail(res))


def run(root: Path) -> int:
    res = judge(root)
    for cls, message in sorted(res.found):
        print(f"  [{cls}] {message}")
    line, code = contract.verdict(NAME, outcome(res), detail=detail(res))
    # stdout is block-buffered when piped and stderr is not, so a could-not-run line printed
    # without this flush arrives ABOVE the findings it is summarising.
    sys.stdout.flush()
    print(line, file=sys.stderr if code == 2 else sys.stdout)
    return code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "root",
        nargs="?",
        default=None,
        help="repository root carrying wiki/, protocol/ and decisions/ (default: this repo)",
    )
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return contract.run_self_test(build())

    root = Path(a.root).resolve() if a.root else ROOT_DEFAULT
    if not root.is_dir():
        return contract.could_not_run(NAME, f"{root} is not a directory")
    if not (root / "wiki").is_dir():
        return contract.could_not_run(
            NAME,
            f"no wiki/ under {root} — this gate's subject is a repository carrying a compiled "
            f"wiki. A root without one is not a clean wiki; it is no wiki",
        )
    return run(root)


# -------------------------------------------------------------------------------------------------
# FIXTURES
#
# The wiki compiler does not exist yet, so there are no real pages to test against. That is what
# `must_pass` and the mutant table are for: the gate's claim to reject is made against trees it
# builds itself, and it is therefore testable on the day it is written rather than on the day the
# first page lands. A gate with no mutant is a gate nobody has tested.
# -------------------------------------------------------------------------------------------------

#: Held as a LIST OF LINES because every citation in the fixture page is an assertion about a line
#: NUMBER. Written as one blob, a stray edit shifts every address by one and the mutants start
#: proving something other than what they are labelled with.
_SRC_LINES = [
    '"""A fixture module. Its only job is to be cited, and then to move.',                    # 1
    "",                                                                                      # 2
    "VERBATIM OR NOTHING. A span quoted on a compiled page must still appear at the address",  # 3
    "the page gives, or the page has quietly become false and nothing would have caught it.",  # 4
    '"""',                                                                                   # 5
    "",                                                                                      # 6
    "#: A prefixed comment block. A page quoting this quotes the TEXT and not the furniture,",  # 7
    "#: so the gate strips the prefix from both sides before it compares them.",              # 8
    "THRESHOLD = 0",                                                                         # 9
    "",                                                                                      # 10
    "",                                                                                      # 11
    "def widen(value):",                                                                     # 12
    "    return value + 1",                                                                  # 13
]
_SRC = "\n".join(_SRC_LINES) + "\n"

_ENTRY = (
    "---\n"
    "when: 2026-09-13T10:00:00\n"
    "what: built the fixture this page cites\n"
    "topics: [gates]\n"
    "track: core\n"
    "kind: build\n"
    "---\n"
    "## WHAT FORCED IT\nA fixture needs a target.\n"
)

_RECORD = (
    "# ADR — a fixture record\n\n"
    "## 1 · Context\n\nSomething had to be decided.\n\n"
    "## 2 · The fixture section\n\nThe section a page cites, by number or by slug.\n"
)

#: A README is the section's signpost, hand-written and uncited BY DESIGN. It is in the clean
#: fixture on purpose: without the skip rule it would fire `page-uncited` and the clean fixture
#: could never pass, so this file is what proves the skip is real rather than asserted.
_SIGNPOST = "# Core\n\nWhat both builders obey.\n"

#: The stamp the compiler puts at the head of every page. Reproduced in the fixture in the SHAPE
#: `tools/mac_wiki.py` actually emits, because a fixture that agrees with a grammar nobody writes
#: tests the gate against a world that does not exist.
_STAMP = (
    '<!-- mac-wiki-stamp {"entries": ["2026-09-13/001-fixture-entry"], '
    '"generator": "mac_wiki.py/1", "source_hash": "0", "spec": "mac.wiki/1", '
    '"topic": "citations", "track": "core", "untracked_entries": 0} -->\n'
)

#: The clean page, carrying all three citation forms.
#:
#: Its quote of lines 3-4 is REWRAPPED at a different column and its quote of lines 7-8 has the
#: `#:` furniture stripped — both deliberate, because a page that could only quote a source at the
#: source's own line width would be unusable and the rule would be ignored.
_PAGE = (
    _STAMP
    + "<!-- GENERATED by mac_wiki.py/1 — do not edit; recompile. -->\n\n"
    "# Citations, compiled\n\n"
    "The register is verifiable because it quotes rather than summarises.\n\n"
    "> VERBATIM OR NOTHING. A span quoted on a compiled page must still\n"
    "> appear at the address the page gives, or the page has quietly become false and nothing\n"
    "> would have caught it.\n\n"
    "[[cite: src/mod.py:3]]\n\n"
    "The furniture belongs to the source, not to the claim.\n\n"
    "> A prefixed comment block. A page quoting this quotes the TEXT and not the furniture,\n"
    "> so the gate strips the prefix from both sides before it compares them.\n\n"
    "[[cite: src/mod.py:7]]\n\n"
    "## Sources these entries cite\n\n"
    "| cited | by entry |\n"
    "|---|---|\n"
    "| `src/mod.py:12` | `2026-09-13/001-fixture-entry` |\n"
    "| `decisions/2026-09-13_fixture-record.md#2` | `2026-09-13/001-fixture-entry` |\n"
)

_PAGE_REL = ("wiki", "core", "citations.md")


def _page_path(root: Path) -> Path:
    return root.joinpath(*_PAGE_REL)


def _append_cite(root: Path, token: str) -> Path:
    """Add ONE citation to the clean page and change nothing else.

    Appending rather than replacing is what keeps a mutant honest: every other citation on the page
    still resolves, so exactly one class can fire and the harness's "no other class fired"
    assertion is testing the predicate rather than the fixture.
    """
    page = _page_path(root)
    page.write_text(page.read_text(encoding="utf-8") + f"\n{token}\n", encoding="utf-8")
    return page


def _clean(root: Path) -> None:
    contract.write(root / "src" / "mod.py", _SRC)
    contract.write(root / "protocol" / "2026-09-13" / "001-fixture-entry.md", _ENTRY)
    contract.write(root / "decisions" / "2026-09-13_fixture-record.md", _RECORD)
    contract.write(root / "wiki" / SIGNPOST, _SIGNPOST)
    contract.write(_page_path(root), _PAGE)


# --- one seeder per reject class ------------------------------------------------------------------


def _m_escapes(root: Path) -> Path:
    """The cited path leaves the repository. The target is MADE TO EXIST on purpose: if it did not,
    a gate that checked existence before containment would still reject it, for the wrong reason,
    and this mutant would be scored as coverage for a predicate that was never written."""
    outside = contract.write(root.parent / "outside" / "notes.py", "elsewhere = 1\n")
    _append_cite(root, "[[cite: ../outside/notes.py:1]]")
    return outside


def _m_file_missing(root: Path) -> Path:
    """The cited file moved. The page still names the old path — the commonest way a page rots."""
    src = root / "src" / "mod.py"
    moved = root / "src" / "mod_moved.py"
    src.rename(moved)
    return moved


def _m_line_missing(root: Path) -> Path:
    """The file shrank past the cited address."""
    return contract.write(root / "src" / "mod.py", "\n".join(_SRC_LINES[:5]) + "\n")


def _m_line_moved(root: Path) -> Path:
    """Three lines land above the docstring. EVERY quoted span is still verbatim intact and every
    address is now stale — the case that makes this a separate class from `span-changed`."""
    prefix = ["from __future__ import annotations", "", "import os"]
    return contract.write(root / "src" / "mod.py", "\n".join(prefix + _SRC_LINES) + "\n")


def _m_span_changed(root: Path) -> Path:
    """One word. The address still resolves, the line still exists, and the page is now false."""
    lines = list(_SRC_LINES)
    lines[2] = lines[2].replace("must still appear", "might still appear")
    return contract.write(root / "src" / "mod.py", "\n".join(lines) + "\n")


def _m_entry_dangling(root: Path) -> Path:
    return _append_cite(root, "[[cite: protocol/2026-09-13/404-never-written]]")


def _m_decision_section(root: Path) -> Path:
    return _append_cite(root, "[[cite: decisions/2026-09-13_fixture-record.md#9.9]]")


def _m_page_uncited(root: Path) -> Path:
    """Prose pretending to be compiled knowledge. It reads perfectly well, which is the problem."""
    return contract.write(
        root / "wiki" / "core" / "principles.md",
        "# Principles\n\nThe register is verifiable because it quotes rather than summarises,\n"
        "and interpretation never blurs into extraction.\n",
    )


_MUTANTS = {
    "path-escapes-repo": _m_escapes,
    "file-missing": _m_file_missing,
    "line-missing": _m_line_missing,
    "line-moved": _m_line_moved,
    "span-changed": _m_span_changed,
    "entry-dangling": _m_entry_dangling,
    "decision-section-missing": _m_decision_section,
    "page-uncited": _m_page_uncited,
}

#: The REASON, not the label. A gate whose disclosure is its own class name has told the reader
#: nothing they could act on, and `expect_line` would be asserting that the gate can spell.
_EXPECT_LINE = {
    "path-escapes-repo": "escapes the repository root",
    "file-missing": "the cited file is gone",
    "line-missing": "but the file has only",
    "line-moved": "no longer begins at line",
    "span-changed": "no longer appears in",
    "entry-dangling": "no protocol entry",
    "decision-section-missing": "has no section",
    "page-uncited": "prose pretending to be compiled knowledge",
}


# --- trees that MUST come back clean ---------------------------------------------------------------


def _mp_elision(root: Path) -> None:
    """A page may quote the two halves of a sentence that matter and elide the middle."""
    _clean(root)
    contract.write(
        root / "wiki" / "core" / "elided.md",
        "# Elision\n\n"
        "> VERBATIM OR NOTHING. ... nothing would have caught it.\n\n"
        "[[cite: src/mod.py:3]]\n",
    )


def _mp_fenced(root: Path) -> None:
    """A citation inside a fence is an EXAMPLE of the grammar, not a use of it.

    Without this rule the first page that documents the citation syntax would be unable to pass,
    and the grammar would become the one thing the wiki cannot write about.
    """
    _clean(root)
    contract.write(
        root / "wiki" / "core" / "grammar.md",
        "# The grammar\n\nA citation looks like this:\n\n"
        "```\n[[cite: src/deleted_long_ago.py:999]]\n```\n\n"
        "and it resolves against the repository root.\n\n"
        "[[cite: src/mod.py:12]]\n",
    )


def _mp_stamp_only_page(root: Path) -> None:
    """A page that cites ONLY protocol entries, through its stamp, is COMPILED — not prose.

    This fixture is a false positive this gate nearly shipped. Before it read the compiler stamp it
    reported nine real, correctly compiled pages as `page-uncited`, because they quote entries
    rather than source files and carry no citations table at all. The measurement that caught it:

        could not run: check_wiki_citations — 15 page(s) examined but 0 citation(s) checked
        ... 15 page(s) carry NO citation

    Nine of those fifteen were correct pages. A gate whose loudest finding is wrong about the
    majority of its population does not get believed about the minority it is right about.
    """
    _clean(root)
    contract.write(
        root / "wiki" / "core" / "stamped.md",
        _STAMP + "\n# Stamped\n\nQuotes an entry, points at no source file, and that is correct.\n",
    )


def _mp_section_by_slug(root: Path) -> None:
    """A decision section addressed by its heading rather than its number. Numbers get renumbered."""
    _clean(root)
    contract.write(
        root / "wiki" / "core" / "by-slug.md",
        "# By slug\n\n[[cite: decisions/2026-09-13_fixture-record.md#the-fixture-section]]\n",
    )


# --- extras: (established, claimed), never a no-op --------------------------------------------------


def _x_uncited_wiki_refuses(base: Path) -> tuple[int, int]:
    """A wiki of pages that cite nothing must REFUSE, and must not lose its findings doing so."""
    root = base / "_x_uncited"
    contract.write(root / "wiki" / "core" / "a.md", "# A\n\nProse.\n")
    contract.write(root / "wiki" / "core" / "b.md", "# B\n\nMore prose.\n")
    line, code = verdict_of(root)
    established = 0
    if code == 2 and "missing yardstick" in line:
        established += 1
    if "2 finding(s) held, unjudged" in line and "2 page(s) carry NO citation" in line:
        established += 1
    return established, 2


def _x_wrapping_forgiven_word_is_not(base: Path) -> tuple[int, int]:
    """THE crux property, proved in both directions over the same source file.

    The whole gate rests on one judgement: which differences between a page and its source are
    typography and which are falsehood. Asserting only the first half would license a gate that
    normalised until everything matched; asserting only the second would license one nobody can use.
    """
    established = 0

    rewrapped = base / "_x_wrap_ok"
    _clean(rewrapped)  # the clean page's quote is deliberately rewrapped at a different column
    if not judge(rewrapped).found:
        established += 1

    reworded = base / "_x_wrap_bad"
    _clean(reworded)
    contract.write(
        reworded / "wiki" / "core" / "reworded.md",
        "# One word\n\n"
        "> VERBATIM OR NOTHING. A span quoted on a compiled page should still appear at the\n"
        "> address the page gives.\n\n"
        "[[cite: src/mod.py:3]]\n",
    )
    if {cls for cls, _ in judge(reworded).found} == {"span-changed"}:
        established += 1

    return established, 2


def _x_denominator_is_printed(base: Path) -> tuple[int, int]:
    """The requested sentence, asserted on the PASS path where nothing else checks it.

    `expect_line` covers the mutants. The green line is the one a reader quotes in a status report,
    and a denominator nobody asserts is a denominator the next refactor deletes.
    """
    root = base / "_x_denominator"
    _clean(root)
    line, code = verdict_of(root)
    ok = code == 0 and "citation(s) across" in line and "page(s) resolved" in line
    return (1 if ok else 0), 1


def build() -> "contract.GateContract":
    return contract.GateContract(
        name=NAME,
        clean=_clean,
        mutants=_MUTANTS,
        run=lambda r: outcome(judge(r)),
        must_pass={
            "an elided quote resolves against the span it brackets": _mp_elision,
            "a citation inside a fenced block is an example, not a use": _mp_fenced,
            "a decision section addressed by heading slug resolves": _mp_section_by_slug,
            "a page cited only through its compiler stamp is compiled, not prose": (
                _mp_stamp_only_page
            ),
        },
        expect_line=_EXPECT_LINE,
        main=lambda r: main([str(r)]),
        # Stated, not inferred. The day someone deletes `classes=` from `outcome()` to quiet a
        # failure, this is what turns that into a red self-test instead of a silent downgrade to
        # "rejected by finding count only".
        attributes_classes=True,
        extra={
            "a wiki whose pages cite nothing refuses rather than passing": _x_uncited_wiki_refuses,
            "rewrapping is forgiven, a changed word is not": _x_wrapping_forgiven_word_is_not,
            "the PASS line carries the requested denominator": _x_denominator_is_printed,
        },
    )


if __name__ == "__main__":
    sys.exit(main())
