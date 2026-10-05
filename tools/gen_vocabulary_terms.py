#!/usr/bin/env python3
"""gen_vocabulary_terms.py — the TERM DEFINITION chapters of the reference manual, from
mac_vocabulary.yaml.

The value-side companion to gen_schema_shapes.py. That one renders STRUCTURE from mac.schema.json
(which keys exist, where they nest); this one renders MEANING from mac_vocabulary.yaml (what the
values of those keys mean). Same marker convention, same --check gate, same rule: it writes ONLY
between the markers, so the hand-written guidance around each chapter survives regeneration.

WHY IT EXISTS. A manual that retypes its definitions is a second home for them, and a second home
drifts. Measured 2026-09-25: twenty files in this estate defined what `dimension` means — seven
verbatim copies and eleven generated ones giving five different terms the same placeholder sentence.
check_references.py scans only *.yaml/*.yml, so no markdown in this repo has ever been checked
against the vocabulary it cites.

THE FALSE STATEMENT THIS FILE PRINTED, MEASURED 2026-10-04. Run bare it said

    notions defined: 24   documented: 20   UNDOCUMENTED: 4
    no chapter yet: calendar_vocabulary, column_type, concept.column.query_use, transform.driven_by
    OK — every generated block matches mac_vocabulary.yaml.

AND EXITED 0. `reference_manual/README.md` described this gate as failing "if a notion has no
chapter" and recorded "It is green: 20 of 20". The gate did not fail, and the denominator was not 20
— it was 24. CAUSE, at the old `main()`: `missing` was COMPUTED (`sorted(n for n in notions if n not
in seen)`), PRINTED, and then never consulted by either return statement; only `unknown` (a chapter
citing a notion the vocabulary does not define) and `updates` (a stale block) could reach `return 1`.
A measurement with no consequence is a comment. It now rejects, and the verdict carries the
denominator the README guessed at.

AND --check COULD NOT HAVE SEEN A DROPPED TERM, because the comparator and the renderer were the
same code: it re-rendered each block and compared, so a renderer that drops or mangles a member
writes a block that is dropped or mangled identically, and the comparison is clean. Agreement by
construction is not evidence. `--check` now asks a SECOND question of the SOURCE — every term the
vocabulary declares for a documented notion, and the opening words of its meaning, must appear in
that notion's block ON DISK — and refuses a Python container repr anywhere in a block, which is what
this generator printed before it learned to read a member's `definition`.

    python3 tools/gen_vocabulary_terms.py            # inject into reference_manual/*.md
    python3 tools/gen_vocabulary_terms.py --check    # exit 1 if stale, undocumented or incomplete
    python3 tools/gen_vocabulary_terms.py --self-test  # one mutant per reject class + a clean fixture
"""
from __future__ import annotations

import argparse
import pathlib

import mac_vocab  # noqa: E402  — ONE reader of mac_vocabulary.yaml, fold-agnostic
import re
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
VOCAB = ROOT / "mac_vocabulary.yaml"
DOCS = ROOT / "reference_manual"

#: THE NOTION KINDS THIS GENERATOR OWNS. One home for the population, so a verdict's denominator and
#: the undocumented-notion reject are measured over the same set.
KINDS = ("vocabulary", "value_domain", "registry")

BLOCK = re.compile(
    r"(?P<open><!-- BEGIN GENERATED:vocabulary-terms:(?P<notion>[A-Za-z_.]+) "
    r"\(tools/gen_vocabulary_terms\.py — do not edit inside this block\) -->\n)"
    r"(?P<body>.*?)"
    r"(?P<close><!-- END GENERATED:vocabulary-terms:(?P=notion) -->)",
    re.DOTALL,
)

#: A PYTHON CONTAINER REPR, which a reference manual never means to print — the shape `str()` on a
#: dict or a list of dicts produces. This generator used to emit them: `canon.composite_key_guard`
#: carries structured fields and reading the member as a string printed `{'serves': …}`.
REPR_RE = re.compile(r"\{'[^']*':|\[\{'|OrderedDict\(")

#: THE FIELDS THAT HOLD A MEMBER'S PROSE, in priority order. One home for "where a term's meaning is".
PROSE_FIELDS = ("definition", "doc", "description")


def _wrap(text: str, width: int = 96) -> str:
    out = []
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        words, line, lines = para.split(), "", []
        for w in words:
            if line and len(line) + 1 + len(w) > width:
                lines.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            lines.append(line)
        out.append("\n".join(lines))
    return "\n\n".join(out)


def _flat(v) -> str:
    """A structured field as a table cell. AN EMPTY CONTAINER IS A FACT, NOT A BLANK:
    `concept.column.role.housekeeping` declares `query_use: []`, which means a query may use it
    NOWHERE. Rendering it as an empty cell — which is what column_roles.md carried — reads as a field
    the vocabulary forgot to fill."""
    if isinstance(v, dict):
        return " · ".join(f"{k}: {_flat(x)}" for k, x in v.items()) if v else "none"
    if isinstance(v, (list, tuple)):
        return ", ".join(_flat(x) for x in v) if v else "none"
    return str(v)


def entries_of(spec: dict) -> dict:
    return spec.get("terms") or spec.get("members") or {}


def meaning_of(body) -> str:
    """One member's prose, whichever of the two shapes it is written in."""
    if isinstance(body, dict):
        return str(next((body[k] for k in PROSE_FIELDS if body.get(k)), "") or "")
    return str(body or "")


def render(notion: str, spec: dict) -> str:
    """Render one notion, whichever of the three shapes it is written in.

    THREE SHAPES, and this used to read only the first:
      * `kind: vocabulary`  + `terms:`   -- name -> a sentence            (17 notions)
      * `kind: value_domain` + `terms:` -- name -> a RECORD of fields    (measure_type, canon)
      * `kind: registry`    + neither     -- nothing term-shaped           (connector)

    The second shape is not merely spelled differently: a member carries structured fields, and
    they are the useful part. `canon.composite_key_guard` records `serves: context_dependent_meaning`
    -- the pattern it implements -- so the cross-reference the manual needs is already data and does
    not have to be written by hand. Reading it as a string printed a Python dict repr.
    """
    entries = entries_of(spec)
    word = "terms" if spec.get("terms") else "members"
    closed = "closed — these are all of them" if spec.get("closed") else "open — a bundle may add its own"
    lines = ["", f"> {_wrap(str(spec.get('description') or '')).strip()}", ""]
    if not entries:
        lines += [f"*`mac.{notion}` · {spec.get('kind', 'vocabulary')} · no enumerated members*", ""]
        return "\n".join(lines)
    lines += [f"*`mac.{notion}` · {len(entries)} {word} · {closed}*", ""]
    for name, body in entries.items():
        lines += [f"#### `mac.{notion}.{name}`", ""]
        if isinstance(body, dict):
            # A RECORD. Its main prose field leads; the rest becomes a small table, because the
            # fields are what distinguish one member from another.
            main = meaning_of(body)
            if main:
                lines += [_wrap(main), ""]
            rest = {k: v for k, v in body.items() if k not in PROSE_FIELDS and v is not None}
            if rest:
                lines += ["| field | value |", "|---|---|"]
                for k, v in rest.items():
                    lines += [f"| `{k}` | {_flat(v).replace('|', chr(92) + '|')} |"]
                lines += [""]
        else:
            lines += [_wrap(str(body)), ""]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# reading the manual
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def notions_of(vocab: dict) -> dict:
    return {k: v for k, v in vocab.items()
            if isinstance(v, dict) and v.get("kind") in KINDS}


#: THE PAGES THIS GENERATOR MAY WRITE, READ FROM THE DECLARATION THAT NAMES THEM.
#: It used to be `sorted(docs.glob("*.md"))`. MEASURED 2026-10-04: that glob returns 27 pages and TWO
#: of them — `column_map.generated.md` and `relation_column.generated.md` — are owned by
#: `tools/gen_slot_reference.py`. Nothing declared that boundary; this generator refrained from writing
#: them only because its injector is marker-driven and those two carry 0 `BEGIN GENERATED:
#: vocabulary-terms:` markers. So the one thing standing between two producers and one file was an
#: ABSENT MARKER, which is one line a person could add in good faith.
#:
#: Now the population comes from `guardrails/reference_manual.yaml` — the same declaration that names
#: this tool as their producer. Measured: the 10 pages actually carrying a marker are all inside the
#: `manual_topic_page` + `manual_argument_page` path lists (23 pages), and no marker-carrying page is
#: outside them, so this is exact and not a narrowing of what is governed.
_DECL = pathlib.Path(__file__).resolve().parent.parent / "guardrails" / "reference_manual.yaml"
_GENRES = ("manual_topic_page", "manual_argument_page")


def declared_pages(decl: pathlib.Path = _DECL) -> list[str] | None:
    """Manual-relative PATHS the guardrail declares for the genres this tool injects into, or None.

    PATHS, NOT BASENAMES, and it was basenames until 2026-10-05. Every declared page sat at the
    manual root, so `rsplit("/", 1)[-1]` was lossless and the flattening was invisible. When the canon
    chapter moved to `rules_and_canons/README.md` the declaration still named it correctly and this
    reader turned it into `README.md`, which resolves to the GENERATED INDEX at the manual root -- a
    different page, carrying no `vocabulary-terms:` marker. The gate then reported `mac.canon` as a
    notion the vocabulary defines and no page documents, which was true of the page it was looking at.
    """
    try:
        import yaml
        doc = yaml.safe_load(decl.read_text(encoding="utf-8")) or {}
    except Exception:                                                     # noqa: BLE001
        return None
    out: list[str] = []
    for genre in _GENRES:
        item = (doc.get("authored") or {}).get(genre) or {}
        for branch in str(item.get("path") or "").split("|"):
            b = branch.strip()
            if b.startswith("reference_manual/") and b.endswith(".md"):
                out.append(b[len("reference_manual/"):])
    return sorted(set(out)) or None


def pages_of(docs: pathlib.Path) -> list[pathlib.Path]:
    names = declared_pages()
    if names is not None:
        return [docs / n for n in names if (docs / n).is_file()]
    #: THE DECLARATION IS UNREADABLE. Fall back to the glob, but never to a page whose name says
    #: another generator renders it — a degraded population must not be a wider one.
    return [p for p in sorted(docs.glob("*.md")) if not p.name.endswith(".generated.md")]


def chapters_of(docs: pathlib.Path) -> dict[str, list[tuple[pathlib.Path, str]]]:
    """{notion -> [(page, the block's body AS IT IS ON DISK)]}. Read, never rendered."""
    out: dict[str, list[tuple[pathlib.Path, str]]] = {}
    for page in pages_of(docs):
        for m in BLOCK.finditer(page.read_text(encoding="utf-8")):
            out.setdefault(m.group("notion"), []).append((page, m.group("body")))
    return out


def inject(vocab: dict, docs: pathlib.Path) -> dict[pathlib.Path, str]:
    """{page -> its text with every known block re-rendered}, for pages that would change."""
    notions = notions_of(vocab)
    updates: dict[pathlib.Path, str] = {}

    def sub(m: re.Match[str]) -> str:
        notion = m.group("notion")
        if notion not in notions:
            return m.group(0)
        return m.group("open") + render(notion, notions[notion]) + m.group("close")

    for page in pages_of(docs):
        text = page.read_text(encoding="utf-8")
        rendered = BLOCK.sub(sub, text)
        if rendered != text:
            updates[page] = rendered
    return updates


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# the check — five reject classes, and only the first re-renders
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def _opening(meaning: str, words: int = 6) -> str:
    return " ".join(" ".join(str(meaning or "").split()).split()[:words])


def check(vocab: dict, docs: pathlib.Path) -> list[str]:
    rejects: list[str] = []
    notions = notions_of(vocab)
    chapters = chapters_of(docs)

    # QUESTION ONE — did a chapter drift from the vocabulary? (re-render and compare)
    for page in sorted(inject(vocab, docs)):
        rejects.append(f"[stale-block] {page.name} — the vocabulary moved and the chapter did not; "
                       f"run `python3 tools/gen_vocabulary_terms.py`")

    # THE CONTRACT THE README CLAIMED AND THE GATE DID NOT HOLD. `missing` was computed, printed and
    # never consulted by a return statement, so 4 notions had no chapter and the gate exited 0.
    for notion in sorted(n for n in notions if n not in chapters):
        rejects.append(f"[undocumented-notion] mac.{notion} — the vocabulary defines it "
                       f"({notions[notion].get('kind')}, {len(entries_of(notions[notion]))} term(s)) "
                       f"and no page in {docs.name}/ carries a chapter for it")

    for notion in sorted(n for n in chapters if n not in notions):
        where = ", ".join(sorted({p.name for p, _ in chapters[notion]}))
        rejects.append(f"[unknown-notion] mac.{notion} — {where} carries a chapter for a notion "
                       f"mac_vocabulary.yaml does not define")

    # QUESTION TWO — does the chapter ON DISK say what the vocabulary says? Nothing below re-renders.
    for notion, spec in sorted(notions.items()):
        for page, body in chapters.get(notion, []):
            m = REPR_RE.search(body)
            if m:
                rejects.append(f"[container-repr] {page.name} — mac.{notion}'s chapter contains a "
                               f"Python container repr ({body[m.start():m.start() + 28]!r}); a "
                               f"structured member was str()'d instead of read")
            for name, member in entries_of(spec).items():
                flat = " ".join(body.split())
                if f"`mac.{notion}.{name}`" not in body:
                    rejects.append(f"[uncovered-term] {page.name} — mac_vocabulary.yaml declares "
                                   f"mac.{notion}.{name} and the chapter does not define it")
                elif meaning_of(member) and _opening(meaning_of(member)) not in flat:
                    rejects.append(f"[uncovered-term] {page.name} — mac.{notion}.{name} is listed "
                                   f"but its meaning is not: the vocabulary opens "
                                   f"{_opening(meaning_of(member))!r} and the chapter does not say it")
    return rejects


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# self-test — one mutant per reject class, plus a clean fixture that must pass
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def self_test(vocab: dict) -> int:
    checks = 0
    failures: list[str] = []

    def expect(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(msg)

    notions = notions_of(vocab)
    with tempfile.TemporaryDirectory() as tmp:
        docs = pathlib.Path(tmp) / "reference_manual"
        docs.mkdir(parents=True)
        #: COPIED AT ITS RELATIVE PATH, not flattened to its basename. This was `docs / page.name`
        #: and it was lossless only while every declared page sat at the manual root -- the same
        #: latent flattening `declared_pages` carried. When three chapters moved into
        #: `rules_and_canons/` on 2026-10-05, their declared paths could no longer resolve inside the
        #: fixture, so the self-test's FIRST assertion -- "the manual as committed must be clean" --
        #: reported mac.concept.rule, mac.concept.identity and mac.concept.column.ruling as notions
        #: no page documents, while the real run over the real tree was clean at 24 of 24. A fixture
        #: that cannot represent the tree it copies tests a manual that does not exist.
        for page in pages_of(DOCS):
            dest = docs / page.relative_to(DOCS)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(page, dest)
        for page, text in inject(vocab, docs).items():
            page.write_text(text, encoding="utf-8")

        expect(check(vocab, docs) == [],
               f"the manual as committed must be clean (got: {check(vocab, docs)[:3]})")

        # The chapter the mutants operate on. Chosen from the manual rather than typed, so a page
        # rename cannot turn this self-test into a no-op.
        chapters = chapters_of(docs)
        host, body = chapters["concept.column.role"][0]
        clean_all = {p: p.read_text(encoding="utf-8") for p in pages_of(docs)}

        def restore():
            for p, t in clean_all.items():
                if not p.is_file() or p.read_text(encoding="utf-8") != t:
                    p.write_text(t, encoding="utf-8")

        def mutate(page: pathlib.Path, new_text: str, cls: str, why: str):
            """Seed one mutant, assert it REJECTS — and assert it CHANGED THE PAGE.

            THE SECOND ASSERTION IS NOT CEREMONY. gen_structure_reference.py's `uncovered-key` mutant
            deleted a TABLE ROW; when the emitter stopped emitting tables the mutant deleted
            nothing, every check stayed clean, and the self-test still reported 6/6 — green over a
            reject class it was no longer testing.
            """
            expect(new_text != clean_all[page], f"the {cls} mutant must actually change {page.name} ({why})")
            page.write_text(new_text, encoding="utf-8")
            rs = check(vocab, docs)
            expect(any(r.startswith(f"[{cls}]") for r in rs),
                   f"{why} must reject as {cls} (got: {[r.split(']')[0] + ']' for r in rs] or 'clean'})")
            restore()

        # stale-block — a hand edit inside the markers
        mutate(host, clean_all[host].replace("#### `mac.concept.column.role.key`",
                                            "#### `mac.concept.column.role.key` EDITED", 1),
               "stale-block", "a hand-edited generated block")

        # undocumented-notion — THE contract: a notion the vocabulary defines with no chapter.
        # Removing the chapter's markers, not the file, so only the chapter goes missing.
        gone = BLOCK.sub(lambda m: "" if m.group("notion") == "concept.column.role" else m.group(0),
                         clean_all[host])
        mutate(host, gone, "undocumented-notion", "a notion the vocabulary defines with no chapter")

        # unknown-notion — a chapter for a notion the vocabulary does not define
        mutate(host, clean_all[host].replace("vocabulary-terms:concept.column.role",
                                            "vocabulary-terms:no_such_notion"),
               "unknown-notion", "a chapter citing a notion the vocabulary does not define")

        # uncovered-term — the renderer dropping a term the vocabulary closes. The mutant deletes the
        # term's own HEADING, which is what the assertion looks for.
        drop = re.compile(r"^#### `mac\.concept\.column\.role\.housekeeping`$")
        mutate(host, "\n".join(ln for ln in clean_all[host].splitlines() if not drop.match(ln)) + "\n",
               "uncovered-term", "a term the vocabulary closes and the chapter omits")

        # container-repr — a structured member str()'d into the manual
        mutate(host, clean_all[host].replace(
            "#### `mac.concept.column.role.key`",
            "#### `mac.concept.column.role.key`\n\n{'query_use': ['identity'], 'definition': 'x'}", 1),
            "container-repr", "a Python container repr inside a chapter")

        expect(check(vocab, docs) == [], "restoring every mutant must return to clean")

    if failures:
        for f in failures:
            print(f"  [SELF-TEST] {f}")
        print(f"FAIL: gen_vocabulary_terms self-test — {len(failures)} of {checks} check(s) failed "
              f"over 5 reject class(es)")
        return 1
    print(f"PASS: gen_vocabulary_terms self-test — {checks}/{checks} check(s) over "
          f"5 reject class(es), {len(notions)} notion(s) in the register")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if a chapter is stale, a notion has none, or a term is missing")
    ap.add_argument("--self-test", action="store_true",
                    help="one mutant per reject class, plus a clean fixture that must pass")
    a = ap.parse_args(argv)

    try:
        import yaml
    except ImportError as exc:
        print(f"COULD NOT RUN: PyYAML is not importable ({exc})", file=sys.stderr)
        return 2
    if not VOCAB.is_file() or not DOCS.is_dir():
        print(f"COULD NOT RUN: need {VOCAB.name} and {DOCS}", file=sys.stderr)
        return 2

    #: FOLD-AGNOSTIC. `mac_vocab.flatten` returns vocabularies keyed by their DOTTED name whether the
    #: file nests them (`concept: column: role:`) or spells them flat (`concept.column.role:`), so every
    #: lookup below keeps working and the file's shape stays an authoring choice. Measured 2026-10-04:
    #: folding the file broke exactly 3 gates of 14, all of them at a dotted-key dict index — 35 modules
    #: parse this file with their own `yaml.safe_load` and none of them had a reader in between.
    vocab = mac_vocab.flatten(yaml.safe_load(VOCAB.read_text(encoding="utf-8")) or {})
    notions = notions_of(vocab)
    if not notions:
        print(f"COULD NOT RUN: {VOCAB.name} declares no notion of kind {'/'.join(KINDS)}",
              file=sys.stderr)
        return 2

    if a.self_test:
        return self_test(vocab)

    terms = sum(len(entries_of(s)) for s in notions.values())
    pages = pages_of(DOCS)

    if a.check:
        rejects = check(vocab, DOCS)
        documented = len(set(chapters_of(DOCS)) & set(notions))
        if rejects:
            for r in rejects[:40]:
                print(f"  {r}")
            if len(rejects) > 40:
                print(f"  … and {len(rejects) - 40} more")
            print(f"FAIL: gen_vocabulary_terms — {len(rejects)} reject(s); {documented} of "
                  f"{len(notions)} notion(s) have a chapter across {len(pages)} page(s) in "
                  f"{DOCS.name}/, {terms} term(s) declared")
            return 1
        print(f"PASS: gen_vocabulary_terms — {documented}/{len(notions)} notion(s) have a chapter "
              f"across {len(pages)} page(s) in {DOCS.name}/, every one of {terms} declared term(s) "
              f"present and current against {VOCAB.name}")
        return 0

    updates = inject(vocab, DOCS)
    for page, rendered in updates.items():
        page.write_text(rendered, encoding="utf-8")
    missing = sorted(n for n in notions if n not in chapters_of(DOCS))
    if missing:
        print("  no chapter yet: " + ", ".join(missing))
    print(f"{'FAIL' if missing else 'PASS'}: gen_vocabulary_terms — rewrote {len(updates)} of "
          f"{len(pages)} page(s); {len(notions) - len(missing)} of {len(notions)} notion(s) have a "
          f"chapter, {terms} term(s) declared")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
