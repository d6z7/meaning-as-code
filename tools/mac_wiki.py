#!/usr/bin/env python3
"""mac_wiki.py — compile the protocol into the wiki. A page is DERIVED, never authored.

WHY THIS EXISTS. `protocol/` is the raw record: one file per entry, append-only, written when the
work happens, and nobody reads it end to end. `wiki/` is what people actually read. Between those
two sits exactly one dangerous step — the step where someone SUMMARISES. This tool removes that
step by never taking it: a compiled page is a REARRANGEMENT of verbatim spans (grouped by topic,
ordered by time, routed by audience) plus a stamp of what it was compiled from. It generates
structure and it generates counts. It never generates a sentence about what an entry said.

THE PRINCIPLE, borrowed from `sdk/project/knowledge.py`, which states it for ontology sources:

    VERBATIM OR NOTHING. Every span rendered here is quoted from the extraction, never paraphrased.
    That is not stylistic: it makes the register mechanically verifiable — a gate can assert that
    each span still appears in the source, which is impossible once someone has summarised it.

    Judgement about WHICH statements are normative belongs in a separate claims layer, so that
    extraction and interpretation never blur.

Turned on ourselves: the protocol is extraction, the wiki is interpretation, and `--check` is the
gate that asserts the interpretation still quotes something real. The measurement this protects is
the one people paraphrase first. If an entry says `0 leak(s) over 488 tracked file(s)`, the page
says that. It must never be able to say "the repository is clean", because that sentence has no
denominator and this estate has already been burned by a gate that reported PASS over zero files.

THE STAMP, and why it is the whole design. `tools/mac_resources.py` states the defect:

    A description maintained by hand drifts from the tree it describes, and there is nothing to
    catch it.

So every page carries `source_hash` — sha256 over each compiled entry's id and bytes, exactly as
`mac_resources.tree_hash` covers the source tree a description was derived from — plus the entry
ids themselves. `--check` re-derives and refuses on any difference. A page that has drifted is
worse than no page: it is a confident wrong answer with a citation attached.

WHERE THIS FILE LIVES, and why it is not `check_wiki.py`. In `tools/`, `check_*.py` means "gate,
swept by run_framework_gates.sh"; `mac_*.py` means "generator, invoked deliberately". This is a
generator whose output happens to be checkable — the same shape as `mac_resources.py`, which
writes a description and re-derives it under `--check`. Naming it `check_*` would sweep a WRITER
into a suite of read-only gates. The gate arm is still contract-conformant and is meant to be run
in CI as `python3 tools/mac_wiki.py --check`.

THE CLAIMS LAYER, and the measurement that forced it. Compiled first, this tool produced 15 pages
of perfectly verbatim, perfectly checkable CHRONOLOGY — and read as a list of things that went
wrong, in the order they went wrong. On `wiki/core/connectors.md` the sentence that says what a
connector IS sat in entry 3 of 6, under a heading about a brief being overturned; a reader who was
not in the conversation met five defects before one definition. Time order is not a semantic, and
the operator asked for pages that "actually disect and compile these aspects based on semantic of
the subject". The fix is the one `sdk/project/knowledge.py` already names — "Judgement about WHICH
statements are normative belongs in a separate claims layer" — so `protocol/claims.yaml` marks
spans `rule` or `boundary` and this tool lifts THOSE SAME BYTES to the top of the page under a
heading from a two-word closed vocabulary. It is still rearrangement: nothing is reworded, every
marked span keeps its `q` anchor and its verifiable address, and both gates check it exactly as
they check the body. A page with no marked span says so, in the shape a denominator is said in.

THE INDEX, and the measurement that forced it. `wiki/README.md` promises three homes; the routing
rule sends any topic two audiences touched to `wiki/core/`. Measured on the real protocol that put
13 of 15 pages in core, leaving `wiki/platform-builder/` with ONE page while twelve topics carried
platform entries. Moving files would be a lie in the other direction — a topic a platform builder
needs is not thereby not shared law — so `wiki/index.md` compiles the CROSS-CUT instead: per
audience, every page carrying at least one entry of that track, with that audience's count beside
the page's own. The front door is derived like everything else, and `stale-index` is the class that
stops it becoming the one hand-maintained file in a compiled tree.

WHAT IT DELIBERATELY DOES NOT DO. It does not compile an ontology's OWN documentation. That is
instance knowledge, it lives in that bundle, and `wiki/README.md` says why. It does not index the
`file:line` references an entry makes, and `render()` records what that index cost when it existed:
a page is a pure function of the entries it names, and anything measured against the wider tree
breaks that. Every reference is still on the page, inside the span that quotes it.

    python3 tools/mac_wiki.py                 # compile: write/refresh every topic page + index
    python3 tools/mac_wiki.py --check         # gate:    are the pages still true?
    python3 tools/mac_wiki.py --self-test     # mutant per reject class
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # the repaired harness: class attribution, must-pass fixtures, printed-line assertions
    from sdk.gate import contract as gate
except Exception:  # pragma: no cover - reported as could-not-run by main(), never as a verdict
    gate = None  # type: ignore[assignment]

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

NAME = "mac-wiki"
SPEC = "mac.wiki/1"
GENERATOR = "mac_wiki.py/1"

#: CLOSED VOCABULARY. A track is the AUDIENCE, and `wiki/README.md` names exactly three homes.
#: An unrecognised value is not routed to a default — see `unknown-track` in the reject classes.
TRACK_DIR: dict[str, str] = {
    "core": "core",
    "ontology": "ontology-builder",
    "platform": "platform-builder",
}

#: A topic becomes a FILENAME. An unvalidated string becoming a path is the oldest escape there is,
#: so the shape is closed and a violation is a finding rather than a `Path` join.
TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

#: The four section names `protocol/README.md` specifies, in the order it specifies them, "because
#: it is the order that makes a claim checkable".
SECTIONS = ("WHAT FORCED IT", "EVIDENCE", "WHAT CHANGED", "WHAT IT DOES NOT PROVE")
_SECTION_RE = re.compile(
    r"^\s*(?:[*\-]\s*)?(?:#{1,6}\s*)?\*{0,2}(" + "|".join(SECTIONS) + r")\*{0,2}\s*(?:[—:\-]\s*)?(.*)$"
)

#: Anchors the checker reads. `q` marks a verbatim block and names the entry and section it came
#: from, so a quote can be verified WITHOUT re-deriving the whole page — which is what lets
#: `paraphrased-quote` and `hand-edited-page` be two predicates instead of one diff.
_Q_OPEN = "<!-- q "
_Q_RE = re.compile(r"^<!-- q (\S+)#(.*?) -->$")
_STAMP_RE = re.compile(r"^<!-- mac-wiki-stamp (\{.*\}) -->$", re.M)

#: THE CLAIMS LAYER, and it is a SEPARATE FILE for two reasons that both come from this estate.
#:
#: `sdk/project/knowledge.py` names the seam: *"Judgement about WHICH statements are normative
#: belongs in a separate claims layer, so that extraction and interpretation never blur."* Without
#: one, a compiled page can only be a time-ordered anthology — every span it carries is equally
#: weighted, so a reader who was not in the conversation meets six defects before the sentence that
#: says what the thing IS. The claims layer is where a human says "this span is the rule" WITHOUT
#: rewording it, which is the only way to gain structure and keep VERBATIM OR NOTHING.
#:
#: And it cannot live in the entries, because `protocol/README.md` says *"Entries are never edited,
#: only superseded by later ones that say so."* Marking a span normative six weeks later is an edit
#: to the raw record. So the mark lives beside the record and points INTO it.
CLAIMS_FILE = "protocol/claims.yaml"

#: CLOSED VOCABULARY, deliberately two words wide. `rule` is a span that still governs; `boundary`
#: is a limit that is still open. A third role for "measurement" was considered and refused: every
#: EVIDENCE section is a measurement, so the role would mark nearly everything and mark nothing.
CLAIM_ROLES: dict[str, str] = {
    "rule": "What holds",
    "boundary": "What is not settled",
}
_CLAIM_SPAN_RE = re.compile(r"^(?P<eid>\d{4}-\d{2}-\d{2}/[^#]+?)(?:\.md)?#(?P<section>.+)$")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@dataclass
class Claim:
    """One human judgement: THIS span, of THIS entry, is normative in THIS role.

    It carries no prose of its own. A claim that could restate the span would be a summary with a
    citation stapled to it, which is the failure mode the whole instrument exists to remove.
    """

    eid: str
    section: str
    role: str
    #: Topics this claim is compiled onto. Empty means "every topic the entry carries" — a claim
    #: narrowed to a topic the entry does not carry is a finding, never a silent no-op.
    topics: list[str]
    by: str
    ratified: bool
    where: str
    #: Position in `claims.yaml`. READING ORDER IS PART OF THE JUDGEMENT: on the connectors page the
    #: span that says what a connector IS was written third in time, and sorting the marked spans by
    #: entry date put the definition below two corrections of it. The claims layer is where a human
    #: says what to read first, so the file's own order is preserved and never re-sorted.
    order: int = 0

    @property
    def key(self) -> str:
        return f"{self.role}:{self.eid}#{self.section}"


def load_claims(root: Path) -> tuple[list[Claim], list[tuple[str, str]]]:
    """(claims, findings). A malformed claims file is REPORTED, never partially believed."""
    p = root / CLAIMS_FILE
    if not p.is_file():
        return [], []
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # a broken YAML file is a finding with a denominator of one
        return [], [("malformed-claims", f"`{CLAIMS_FILE}` did not parse: {exc}")]
    if not isinstance(doc, dict) or not isinstance(doc.get("claims") or [], list):
        return [], [("malformed-claims", f"`{CLAIMS_FILE}` carries no `claims:` list")]
    out: list[Claim] = []
    found: list[tuple[str, str]] = []
    for i, raw in enumerate(doc.get("claims") or []):
        where = f"{CLAIMS_FILE}#claims[{i}]"
        if not isinstance(raw, dict):
            found.append(("malformed-claims", f"`{where}` is not a mapping"))
            continue
        span = str(raw.get("span") or "").strip()
        m = _CLAIM_SPAN_RE.match(span)
        if not m:
            found.append(
                (
                    "malformed-claims",
                    f"`{where}`: span {span!r} is not `YYYY-MM-DD/entry-slug#SECTION NAME`",
                )
            )
            continue
        role = str(raw.get("holds") or "").strip()
        if role not in CLAIM_ROLES:
            found.append(
                (
                    "unknown-claim-role",
                    f"`{where}`: holds: {role!r} is not one of {sorted(CLAIM_ROLES)} — the "
                    f"compiler will not invent a role, because an unrecognised one rendered under "
                    f"a default heading is interpretation nobody wrote",
                )
            )
            continue
        topics_raw = raw.get("topics") or []
        if isinstance(topics_raw, str):
            topics_raw = [topics_raw]
        out.append(
            Claim(
                eid=m.group("eid"),
                section=m.group("section").strip(),
                role=role,
                topics=[str(t).strip() for t in topics_raw if str(t).strip()],
                by=str(raw.get("by") or "").strip(),
                ratified=bool(raw.get("ratified") or False),
                where=where,
                order=i,
            )
        )
    return out, found


def resolve_claims(
    claims: list[Claim], by_id: dict[str, Entry], quarantined: set[str] | None = None
) -> tuple[dict[str, list[Claim]], list[tuple[str, str]], set[str]]:
    """(claims by topic, findings, topics a broken claim makes unjudgeable).

    A claim that does not resolve QUARANTINES the topics it touches, exactly as an unplaceable
    entry does. Rendering the page without it and then reporting the page as hand-edited would name
    the wrong defect, and for a ratchet a wrong name is most of the damage.
    """
    by_topic: dict[str, list[Claim]] = {}
    found: list[tuple[str, str]] = []
    skipped: set[str] = set()
    quarantined = quarantined or set()
    for c in claims:
        e = by_id.get(c.eid)
        if e is not None and c.eid in quarantined:
            # The ENTRY could not be placed, and that is already a finding with its own class. A
            # second one saying its claim landed nowhere is the same situation reported twice; the
            # entry's quarantine has already made this topic unjudgeable.
            continue
        if e is None:
            found.append(
                (
                    "dangling-claim",
                    f"`{c.where}`: names entry `{c.eid}`, which no protocol file provides",
                )
            )
            skipped.update(c.topics)
            continue
        if c.section not in e.section_lines():
            found.append(
                (
                    "dangling-claim",
                    f"`{c.where}`: names section `{c.section}` of `{c.eid}`, which that entry does "
                    f"not have — it has {sorted(e.section_lines())}",
                )
            )
            skipped.update(c.topics or e.topics)
            continue
        stray = [t for t in c.topics if t not in e.topics]
        if stray:
            found.append(
                (
                    "claim-topic-mismatch",
                    f"`{c.where}`: narrowed to topic `{stray[0]}`, which `{c.eid}` does not carry "
                    f"(it carries {e.topics}) — the claim would compile onto no page and read as "
                    f"filed rather than lost",
                )
            )
            skipped.update(c.topics)
            skipped.update(e.topics)
            continue
        for t in c.topics or e.topics:
            by_topic.setdefault(t, []).append(c)
    return by_topic, found, skipped


# -------------------------------------------------------------------------------------------------
# reading the raw record
# -------------------------------------------------------------------------------------------------


@dataclass
class Entry:
    eid: str
    path: Path
    sha: str
    when: str
    what: str
    kind: str
    topics: list[str]
    track: str | None
    supersedes: str | None
    body: str
    #: WHY the compiler refuses to place this entry, or "" when it can. A quarantined entry is not
    #: routed to a default; see `plan()`.
    quarantine: str = ""
    bad_topics: list[str] = field(default_factory=list)

    #: 0-based line index at which `body` starts inside the entry FILE. Front matter is not body,
    #: and a citation that is off by the size of the front matter is a citation to the wrong thing.
    body_offset: int = 0

    def sections(self) -> list[tuple[str, list[str], int, int]]:
        """(name, lines, first line, last line) — line numbers 1-based, into the entry file."""
        return [
            (n, lines, self.body_offset + a + 1, self.body_offset + b + 1)
            for n, lines, a, b in split_sections(self.body)
        ]

    def section_lines(self) -> dict[str, list[str]]:
        return {n: lines for n, lines, _a, _b in self.sections()}


def split_sections(body: str) -> list[tuple[str, list[str], int, int]]:
    """Split an entry body on its four declared section markers. NOTHING IS DROPPED.

    Text before the first marker (or a body with no markers at all) is kept under the name
    `(unsectioned)` rather than discarded — a compiler that silently loses a paragraph is a
    summariser with extra steps. `--self-test` asserts, over the whole fixture corpus, that every
    non-empty line of every compiled entry survives onto a page.

    Markers are recognised as either `## EVIDENCE` or the bulleted `* **EVIDENCE** —` form the
    README specifies. Fenced regions are skipped so a marker quoted inside evidence stays evidence.
    """
    out: list[tuple[str, list[tuple[int, str]]]] = []
    name = "(unsectioned)"
    buf: list[tuple[int, str]] = []
    fenced = False
    for i, line in enumerate(body.splitlines()):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        m = None if fenced else _SECTION_RE.match(line)
        if m:
            if any(x.strip() for _i, x in buf) or out:
                out.append((name, buf))
            name, buf = m.group(1), []
            rest = m.group(2).strip()
            if rest:
                # The bulleted form carries its first words on the marker line itself, so the span
                # begins mid-line. That is why the address is a RANGE and the reader of it checks
                # the span BEGINS within the line rather than at its first column.
                buf.append((i, rest))
            continue
        buf.append((i, line))
    out.append((name, buf))
    # Blank lines at the EDGES of a section are an artefact of the marker, not content. They are
    # trimmed HERE, in the extractor both the renderer and the verifier read, so the two can never
    # disagree about what the span is. Interior blank lines are untouched.
    trimmed = []
    for n, b in out:
        while b and not b[0][1].strip():
            b = b[1:]
        while b and not b[-1][1].strip():
            b = b[:-1]
        if b:
            trimmed.append((n, [x for _i, x in b], b[0][0], b[-1][0]))
    return trimmed


def load_entries(root: Path) -> list[Entry]:
    """Every `protocol/**/*.md` except the README, parsed. Front matter absent is not fatal here —
    it surfaces as no topic and no track, which is DISCLOSED in the verdict rather than swallowed."""
    proot = root / "protocol"
    if not proot.is_dir():
        return []
    entries: list[Entry] = []
    for p in sorted(proot.rglob("*.md")):
        if p.name == "README.md":
            continue
        raw = p.read_bytes()
        text = raw.decode("utf-8", "replace")
        fm: dict = {}
        body = text
        offset = 0
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                head = text[3:end]
                body = text[end + 4 :].lstrip("\n")
                offset = text[: len(text) - len(body)].count("\n")
                if yaml is not None:
                    try:
                        fm = yaml.safe_load(head) or {}
                    except Exception:
                        fm = {}
                if not isinstance(fm, dict):
                    fm = {}
        topics_raw = fm.get("topics") or []
        if isinstance(topics_raw, str):
            topics_raw = [topics_raw]
        topics = [str(t).strip() for t in topics_raw if str(t).strip()]
        bad = [t for t in topics if not TOPIC_RE.match(t)]
        track = fm.get("track")
        track = str(track).strip() if track not in (None, "") else None
        e = Entry(
            eid=str(p.relative_to(proot).with_suffix("")),
            path=p,
            sha=_sha(raw),
            when=str(fm.get("when") or ""),
            what=str(fm.get("what") or "").strip(),
            kind=str(fm.get("kind") or "").strip(),
            topics=[t for t in topics if t not in bad],
            track=track,
            supersedes=(str(fm["supersedes"]).strip() if fm.get("supersedes") else None),
            body=body,
            body_offset=offset,
            bad_topics=bad,
        )
        if bad:
            e.quarantine = (
                f"topic {bad[0]!r} is not a legal topic token (a topic becomes a filename; "
                f"the shape is {TOPIC_RE.pattern})"
            )
        elif track is not None and track not in TRACK_DIR:
            e.quarantine = (
                f"track: {track!r} is not one of {sorted(TRACK_DIR)} — the compiler will not guess "
                f"an audience, and filing it under a default would be a confident wrong answer"
            )
        entries.append(e)
    return entries


# -------------------------------------------------------------------------------------------------
# planning: which topic becomes which page, in which audience directory
# -------------------------------------------------------------------------------------------------


@dataclass
class Page:
    topic: str
    track: str
    basis: str
    entries: list[Entry]
    untracked: int
    #: Resolved claims for this topic, in page order. They are an INPUT to the page, so they are
    #: inside `source_hash`: marking a span normative changes what the page says, and a change to
    #: the claims layer must read as `stale-stamp` (recompile) rather than `hand-edited-page`.
    claims: list[Claim] = field(default_factory=list)

    @property
    def rel(self) -> str:
        return f"wiki/{TRACK_DIR[self.track]}/{self.topic}.md"

    @property
    def source_hash(self) -> str:
        body = "\n".join(f"{e.eid}:{e.sha}" for e in self.entries)
        marks = "\n".join(c.key for c in self.claims)
        return _sha((body + "\n--claims--\n" + marks).encode())

    def claims_for(self, role: str) -> list[Claim]:
        return sorted((c for c in self.claims if c.role == role), key=lambda c: c.order)

    @property
    def ids(self) -> list[str]:
        return [e.eid for e in self.entries]


@dataclass
class Plan:
    pages: dict[str, Page]
    entries: list[Entry]
    no_topic: list[Entry]
    untracked: list[Entry]
    quarantined: list[Entry]
    claims: list[Claim] = field(default_factory=list)
    claim_findings: list[tuple[str, str]] = field(default_factory=list)
    claim_skips: set[str] = field(default_factory=set)

    @property
    def skipped_topics(self) -> set[str]:
        """Topics the gate will NOT judge this run, because an entry that belongs to them could not
        be placed. Reporting a stale page downstream of an unreadable entry is reporting a symptom;
        the harness also forbids it, since one mutation must trip one class."""
        return {t for e in self.quarantined for t in e.topics} | set(self.claim_skips)

    @property
    def claimed_entries(self) -> set[str]:
        return {c.eid for p in self.pages.values() for c in p.claims}


def plan(entries: list[Entry], claims: list[Claim] | None = None) -> Plan:
    """Group by `topics:`, route by `track:`.

    THE ROUTING RULE, and it is a derivation rather than a default:

    * every entry on the topic that declares a track declares the SAME one -> that audience;
    * two or more different tracks -> `wiki/core/`, because a topic BOTH audiences touch is shared
      law by definition, and the page discloses the split;
    * nobody declared one -> `wiki/core/`, disclosed in the stamp as exactly that, so a missing
      `track:` reads as "nobody said" and never as "we decided".
    """
    by_topic: dict[str, list[Entry]] = {}
    no_topic, untracked, quarantined = [], [], []
    for e in entries:
        if e.quarantine:
            quarantined.append(e)
            continue
        if e.track is None:
            untracked.append(e)
        if not e.topics:
            no_topic.append(e)
            continue
        for t in e.topics:
            by_topic.setdefault(t, []).append(e)

    pages: dict[str, Page] = {}
    for topic, es in sorted(by_topic.items()):
        es = sorted(es, key=lambda x: (x.when, x.eid))
        declared = sorted({e.track for e in es if e.track})
        silent = sum(1 for e in es if not e.track)
        if len(declared) == 1:
            track, basis = declared[0], f"every entry declaring a track declared `{declared[0]}`"
        elif len(declared) > 1:
            counts = ", ".join(f"{t} {sum(1 for e in es if e.track == t)}" for t in declared)
            track = "core"
            basis = (
                f"entries declare {len(declared)} different tracks ({counts}) — a topic both "
                f"audiences touch is shared law"
            )
        else:
            track = "core"
            basis = (
                "no entry on this topic declared a `track:` — filed as shared law and disclosed; "
                "declare one to route it"
            )
        pages[topic] = Page(topic, track, basis, es, silent)

    claims = list(claims or [])
    by_topic, cfound, cskip = resolve_claims(
        claims,
        {e.eid: e for e in entries},
        {e.eid for e in entries if e.quarantine},
    )
    for topic, cs in by_topic.items():
        if topic in pages:
            pages[topic].claims = cs
        else:
            # A claim on a topic no entry carries is not silently dropped: it names a page that
            # does not exist, which is the same defect as a dangling entry id and reads the same.
            cfound.append(
                (
                    "dangling-claim",
                    f"`{cs[0].where}`: compiled onto topic `{topic}`, which no entry carries — "
                    f"there is no page for this claim to land on",
                )
            )
    return Plan(pages, entries, no_topic, untracked, quarantined, claims, cfound, cskip)


# -------------------------------------------------------------------------------------------------
# rendering: verbatim spans, one declared transform, one stamp
# -------------------------------------------------------------------------------------------------
# THE ONLY TRANSFORM applied to a quoted span is the blockquote prefix, and it is reversible:
# `> ` is added to every line, a line that is empty after that becomes `>`, and the checker strips
# exactly one prefix before comparing. Comparison is line-by-line with trailing whitespace removed,
# and that tolerance is the ONLY one. Everything else is bytes.


def _quote(lines: list[str]) -> list[str]:
    return [("> " + ln).rstrip() for ln in lines]


def _unquote(lines: list[str]) -> list[str]:
    out = []
    for ln in lines:
        if ln.startswith("> "):
            out.append(ln[2:])
        elif ln == ">":
            out.append("")
        elif ln.startswith(">"):
            out.append(ln[1:])
        else:
            out.append(ln)
    return out


def _same(a: list[str], b: list[str]) -> bool:
    return [x.rstrip() for x in a] == [y.rstrip() for y in b]


def _title(topic: str) -> str:
    words = topic.replace("-", " ")
    return words[:1].upper() + words[1:]


def _render_claims(page: Page, out: list[str]) -> None:
    """The compiled cross-cut: the spans a human marked normative, lifted to the top of the page.

    WHAT FORCED THIS SECTION. Without it a page is a time-ordered anthology — correct, verbatim,
    checkable, and still unreadable to someone who was not in the conversation, because the
    sentence that says what the subject IS sits in the third of six entries, under a heading about
    what went wrong. The operator asked for pages that "actually disect and compile these aspects
    based on semantic of the subject"; chronology is not a semantic.

    WHAT IT REFUSES TO DO. It does not write a sentence. Every line below is the same verbatim span
    the entry carries, with the same `q` anchor and the same verifiable address, so both gates check
    these blocks exactly as they check the body. The ONLY thing added is the ORDER and the HEADING,
    and the heading comes from a closed vocabulary of two words.
    """
    if not page.claims:
        # The honest zero. A page with no claims says so, in the shape a denominator is said in,
        # because "this page has not been interpreted yet" is information and silence is not.
        out.append("## What holds — NOT YET COMPILED")
        out.append("")
        out.append(
            f"> **No span on this page has been marked normative.** `{CLAIMS_FILE}` carries no "
            f"claim for topic `{page.topic}`, so what follows is the raw record in time order and "
            f"nothing on it has been judged to still hold. Mark spans in the claims layer to "
            f"compile this section; it is deliberately empty rather than guessed."
        )
        out.append("")
        return
    unratified = sum(1 for c in page.claims if not c.ratified)
    out.append(
        f"> **THE CLAIMS LAYER — interpretation, not extraction.** Which spans are normative is a "
        f"judgement, and it lives in `{CLAIMS_FILE}` so that it never touches the append-only "
        f"record it points at. The {len(page.claims)} span(s) in the next two sections are quoted "
        f"VERBATIM from the entries below and verified by the same two gates as the body; only "
        f"their SELECTION and their ORDER are authored."
        + (
            f" **{unratified} of {len(page.claims)} UNRATIFIED** — proposed by an agent, not signed "
            f"off: `2026-09-12/008` records that ratification is the operator's act."
            if unratified
            else ""
        )
    )
    out.append("")
    for role, heading in CLAIM_ROLES.items():
        cs = page.claims_for(role)
        if not cs:
            continue
        out.append(f"## {heading}")
        out.append("")
        for c in cs:
            e = next(x for x in page.entries if x.eid == c.eid)
            src = {n: (lines, a, b) for n, lines, a, b in e.sections()}[c.section]
            lines, first, last = src
            mark = "" if c.ratified else " · UNRATIFIED"
            out.append(f"**{role.upper()}** · `{c.eid}` · from *{c.section}*{mark}")
            out.append("")
            out.append(f"{_Q_OPEN}{c.eid}#{c.section} -->")
            out.extend(_quote(lines))
            out.append("")
            out.append(f"[[cite: protocol/{c.eid}.md:{first}-{last}]]")
            out.append("")


def render(page: Page) -> str:
    stamp = {
        "spec": SPEC,
        "generator": GENERATOR,
        "topic": page.topic,
        "track": page.track,
        "track_basis": page.basis,
        "entries": page.ids,
        "untracked_entries": page.untracked,
        "claims": [c.key for c in page.claims],
        "source_hash": page.source_hash,
    }
    superseded_by: dict[str, str] = {}
    for e in page.entries:
        if e.supersedes:
            superseded_by[e.supersedes] = e.eid

    out: list[str] = []
    out.append("<!-- mac-wiki-stamp " + json.dumps(stamp, sort_keys=True) + " -->")
    out.append(f"<!-- GENERATED by {GENERATOR} — do not edit; recompile. -->")
    out.append("")
    out.append(f"# {_title(page.topic)}")
    out.append("")
    out.append(
        f"> **COMPILED PAGE — derived, never authored.** Every block below is quoted VERBATIM from "
        f"the protocol entry it cites. Nothing on this page is summarised, and no measurement is "
        f"restated in words. `python3 tools/mac_wiki.py --check` fails if a quoted block stops "
        f"matching its source, if this file is edited by hand, or if the protocol moves under it."
    )
    out.append("")
    out.append("| | |")
    out.append("|---|---|")
    out.append(f"| topic | `{page.topic}` |")
    out.append(f"| audience | `wiki/{TRACK_DIR[page.track]}/` — {page.basis} |")
    out.append(f"| entries compiled | {len(page.entries)} |")
    if page.untracked:
        out.append(
            f"| entries declaring no track | {page.untracked} of {len(page.entries)} |"
        )
    n_rule = len(page.claims_for("rule"))
    n_bound = len(page.claims_for("boundary"))
    out.append(
        f"| normative spans | {len(page.claims)} marked over {len({c.eid for c in page.claims})} "
        f"of {len(page.entries)} entry(ies) — {n_rule} rule, {n_bound} boundary |"
        if page.claims
        else f"| normative spans | **0** — nothing on this page has been marked as still holding |"
    )
    out.append(
        f"| source_hash | `{page.source_hash[:16]}…` (sha256 over each entry's id and bytes, and "
        f"over the claims marked on them) |"
    )
    out.append(f"| generated by | `{GENERATOR}` |")
    out.append("")
    _render_claims(page, out)
    out.append("## What this page was compiled from")
    out.append("")
    kinds = {}
    for e in page.entries:
        kinds[e.kind or "—"] = kinds.get(e.kind or "—", 0) + 1
    out.append(
        f"{len(page.entries)} entry(ies), in time order: "
        + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0])))
        + "."
    )
    out.append("")
    out.append("| entry | when | kind | what |")
    out.append("|---|---|---|---|")
    for e in page.entries:
        mark = " **[SUPERSEDED]**" if e.eid in superseded_by else ""
        out.append(
            f"| `{e.eid}`{mark} | {e.when or '—'} | {e.kind or '—'} | {e.what or '—'} |"
        )
    out.append("")

    for e in page.entries:
        out.append(f"## {e.what or e.eid}")
        out.append("")
        meta = [f"`{e.eid}`"]
        if e.kind:
            meta.append(e.kind)
        if e.when:
            meta.append(e.when)
        out.append(" · ".join(meta))
        out.append("")
        if e.eid in superseded_by:
            out.append(
                f"> **SUPERSEDED by `{superseded_by[e.eid]}`.** Kept because the protocol is "
                f"append-only: an entry is never edited, only superseded by a later one that says "
                f"so. Read it as history, not as current practice."
            )
            out.append("")
        if e.supersedes:
            out.append(f"*Supersedes `{e.supersedes}`.*")
            out.append("")
        for sname, lines, first, last in e.sections():
            out.append(f"### {sname}")
            out.append("")
            out.append(f"{_Q_OPEN}{e.eid}#{sname} -->")
            out.extend(_quote(lines))
            out.append("")
            # The address form `tools/check_wiki_citations.py` resolves. It is deliberately the
            # ADDRESS and not the bare entry id: an id asserts only that the entry exists, while an
            # address makes that gate re-verify this span against the entry's literal lines. Two
            # independent verifiers of one property — this tool checks the span against the parsed
            # section, that one against the bytes at those line numbers — and they can disagree,
            # which is the only reason a second checker is worth having.
            out.append(f"[[cite: protocol/{e.eid}.md:{first}-{last}]]")
            out.append("")

    # NO CITATION INDEX HERE, and the reason is worth more than the table was.
    #
    # An earlier version ended each page with "Sources these entries cite" — every `file:line` an
    # entry mentioned, lifted out of its quoted span and listed as an address. That table was the
    # ONE element of the page that was not a verbatim quotation, and it broke in both directions:
    #
    #   * It re-presented quoted testimony as a live claim. One entry wrote the bare basename
    #     `materialize.py:232`; inside a quoted span that is a true record of what someone wrote,
    #     but in an address table it is a citation that does not resolve, and the citation gate
    #     reported it on three pages that had quoted it faithfully.
    #   * Fixing it by MEASURING resolution would have been worse. The status of a cited file is a
    #     fact about the tree, not about the entries — folding it in would make a page's text change
    #     when a file moved, so `--check` would report `hand-edited-page` for a refactor nobody made
    #     by hand. A page is a pure function of the entries it names, and `source_hash` covers
    #     exactly those inputs. That property is worth more than an index.
    #
    # Every reference an entry makes is still on the page, inside the span that quotes it, which is
    # where it is testimony rather than an assertion. An index that RESOLVES belongs in a gate that
    # measures resolution, not in a page body that cannot.
    return "\n".join(out).rstrip() + "\n"


# -------------------------------------------------------------------------------------------------
# the compile arm
# -------------------------------------------------------------------------------------------------


def _stamp_of(text: str) -> dict | None:
    m = _STAMP_RE.search(text)
    if not m:
        return None
    try:
        s = json.loads(m.group(1))
    except Exception:
        return None
    return s if isinstance(s, dict) and s.get("topic") else None


def _wiki_pages_on_disk(root: Path) -> list[Path]:
    """Every `*.md` in the three audience directories. Those directories belong to this compiler;
    an explainer lives at `wiki/README.md`, outside them."""
    out = []
    for d in TRACK_DIR.values():
        p = root / "wiki" / d
        if p.is_dir():
            out.extend(sorted(q for q in p.glob("*.md") if q.name != "README.md"))
    return out


INDEX_REL = "wiki/index.md"


def render_index(pl: Plan) -> str:
    """The front door, and it is compiled for the same reason every other page is.

    IT IS ALSO THE AUDIENCE FIX. `wiki/README.md` promises three homes, and the routing rule sends
    any topic two audiences touched to `wiki/core/`. Measured on the real protocol that put 13 of
    15 pages in core, so `wiki/platform-builder/` listed ONE page while 12 topics carried platform
    entries. The directory was true and useless: a door onto a corridor whose rooms are elsewhere.
    Moving the files would be worse — a topic a platform builder needs is not thereby not shared
    law. So the index compiles the CROSS-CUT instead: per audience, every page carrying at least
    one entry of that track, with that audience's entry count as the denominator of the page's.
    """
    pages = sorted(pl.pages.values(), key=lambda p: (list(TRACK_DIR).index(p.track), p.topic))
    all_ids = sorted({e.eid for p in pages for e in p.entries})
    stamp = {
        "spec": SPEC,
        "generator": GENERATOR,
        "topic": None,
        "index": True,
        "pages": [p.rel for p in pages],
        "entries": all_ids,
        "source_hash": _sha(
            "\n".join(f"{p.rel}:{p.source_hash}" for p in pages).encode()
        ),
    }
    claimed = pl.claimed_entries
    o: list[str] = []
    o.append("<!-- mac-wiki-stamp " + json.dumps(stamp, sort_keys=True) + " -->")
    o.append(f"<!-- GENERATED by {GENERATOR} — do not edit; recompile. -->")
    o.append("")
    o.append("# The wiki")
    o.append("")
    o.append(
        "> **COMPILED FRONT DOOR — derived, never authored.** Every row below is counted from "
        "`protocol/`, not maintained by hand. `python3 tools/mac_wiki.py --check` fails if this "
        "file stops matching the pages it lists. Read `wiki/README.md` for what the three "
        "directories mean and `protocol/README.md` for how an entry is written."
    )
    o.append("")
    o.append("| | |")
    o.append("|---|---|")
    o.append(f"| pages | {len(pages)} |")
    o.append(
        f"| entries compiled | {len(all_ids)} of {len(pl.entries)} in `protocol/` |"
    )
    o.append(
        f"| entries on no page | {len(pl.no_topic)} (carry no `topics:`) |"
    )
    o.append(
        f"| entries declaring no audience | {len(pl.untracked)} of {len(pl.entries)} |"
    )
    o.append(
        f"| normative spans | {len(pl.claims)} marked over {len(claimed)} of {len(pl.entries)} "
        f"entry(ies) — `{CLAIMS_FILE}` |"
    )
    o.append(f"| source_hash | `{stamp['source_hash'][:16]}…` (over every page's own hash) |")
    o.append(f"| generated by | `{GENERATOR}` |")
    o.append("")
    o.append("## Every page")
    o.append("")
    o.append("| page | topic | audience | entries | normative spans | compile stamp |")
    o.append("|---|---|---|---|---|---|")
    for p in pages:
        link = p.rel[len("wiki/") :]
        o.append(
            f"| [{p.topic}]({link}) | {p.topic} | {TRACK_DIR[p.track]} | {len(p.entries)} | "
            f"{len(p.claims)} | `{p.source_hash[:16]}…` |"
        )
    o.append("")
    o.append("## By audience")
    o.append("")
    o.append(
        "A page lives in ONE directory. An entry declares ONE audience. A topic both audiences "
        "touched is filed as shared law, so the table below is the cross-cut: what each audience "
        "wrote about, wherever it was filed."
    )
    o.append("")
    for track, dirname in TRACK_DIR.items():
        own = [p for p in pages if p.track == track]
        elsewhere = [
            (p, sum(1 for e in p.entries if e.track == track))
            for p in pages
            if p.track != track and any(e.track == track for e in p.entries)
        ]
        total = sum(1 for e in pl.entries if e.track == track)
        o.append(f"### `wiki/{dirname}/` — {len(own)} page(s) filed here, {total} entry(ies) declared this audience")
        o.append("")
        if own:
            o.append("| page | entries | normative spans |")
            o.append("|---|---|---|")
            for p in own:
                o.append(
                    f"| [{p.topic}]({p.rel[len('wiki/'):]}) | {len(p.entries)} | {len(p.claims)} |"
                )
        else:
            o.append(
                f"*No page is filed here.* Every topic this audience touched is also touched by "
                f"another, so it compiled to shared law — see below."
            )
        o.append("")
        if elsewhere:
            o.append(f"**Filed elsewhere, carrying `{track}` entries:**")
            o.append("")
            o.append(f"| page | filed under | `{track}` entries | of |")
            o.append("|---|---|---|---|")
            for p, n in sorted(elsewhere, key=lambda x: -x[1]):
                o.append(
                    f"| [{p.topic}]({p.rel[len('wiki/'):]}) | {TRACK_DIR[p.track]} | {n} | "
                    f"{len(p.entries)} |"
                )
            o.append("")
    return "\n".join(o).rstrip() + "\n"


def compile_wiki(root: Path) -> dict:
    """Write every topic page. Returns a report; writes nothing when there is nothing to compile."""
    entries = load_entries(root)
    claims, claim_load = load_claims(root)
    pl = plan(entries, claims)
    written, moved, orphans = [], [], []

    on_disk = {}
    for p in _wiki_pages_on_disk(root):
        s = _stamp_of(p.read_text(encoding="utf-8"))
        if s:
            on_disk[str(p.relative_to(root))] = s

    for topic, page in sorted(pl.pages.items()):
        target = root / page.rel
        target.parent.mkdir(parents=True, exist_ok=True)
        text = render(page)
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            target.write_text(text, encoding="utf-8")
            written.append(page.rel)
        # A page whose TRACK changed has a new home. Moving it is derivable, so the compiler does
        # it; only a file carrying this compiler's own stamp is ever removed.
        for rel, s in on_disk.items():
            if s.get("topic") == topic and rel != page.rel:
                (root / rel).unlink()
                moved.append(f"{rel} -> {page.rel}")

    for rel, s in on_disk.items():
        if s.get("topic") not in pl.pages and not any(rel in m for m in moved):
            orphans.append(rel)

    if pl.pages:
        idx = root / INDEX_REL
        idx.parent.mkdir(parents=True, exist_ok=True)
        text = render_index(pl)
        if not idx.is_file() or idx.read_text(encoding="utf-8") != text:
            idx.write_text(text, encoding="utf-8")
            written.append(INDEX_REL)

    return {
        "entries": len(entries),
        "pages": len(pl.pages),
        "written": written,
        "moved": moved,
        "orphans": orphans,
        "no_topic": [e.eid for e in pl.no_topic],
        "untracked": [e.eid for e in pl.untracked],
        "quarantined": [(e.eid, e.quarantine) for e in pl.quarantined],
        "claims": len(pl.claims),
        "claimed_entries": len(pl.claimed_entries),
        "claim_findings": claim_load + pl.claim_findings,
        "by_track": {
            t: sum(1 for p in pl.pages.values() if p.track == t) for t in sorted(TRACK_DIR)
        },
    }


# -------------------------------------------------------------------------------------------------
# the gate arm — ten reject classes, evaluated first-match per page
# -------------------------------------------------------------------------------------------------
# ORDER IS THE DESIGN, exactly as containment-before-existence is in `sdk/gate/demo_right_gate.py`.
# A hand-edit that corrupts a quote ALSO changes the page text; a stale stamp ALSO makes the text
# differ. Evaluating in order and stopping at the first finding for a page is what forces eight
# labels to be ten predicates rather than one diff wearing ten hats.


_ADDR_RE = re.compile(r"^\[\[cite: protocol/(?P<eid>\S+)\.md:(?P<a>\d+)-(?P<b>\d+)\]\]$")


def _verify_address(e: Entry, span: list[str], a: int, b: int) -> str:
    """Is the printed address true? The span must be exactly the entry file's lines a..b.

    TOLERANCE, and there is exactly one: the FIRST line may begin mid-line, because the bulleted
    section form (`* **EVIDENCE** — the first words`) puts the marker and the first words of the
    span on one line. Every other line is compared whole. Printing an address nothing verifies is
    the confident wrong answer this estate exists to remove, and it was introduced the moment this
    page started carrying line numbers.
    """
    file_lines = e.path.read_text(encoding="utf-8").splitlines()
    if a < 1 or b > len(file_lines):
        return f"cites lines {a}-{b} but the entry has {len(file_lines)} line(s)"
    window = [x.rstrip() for x in file_lines[a - 1 : b]]
    want = [x.rstrip() for x in span]
    if len(window) != len(want):
        return f"cites {len(window)} line(s) at {a}-{b} for a span of {len(want)}"
    if window[0] != want[0] and not window[0].endswith(want[0]):
        return f"the span does not begin at line {a} — the quote may be right, the address is not"
    if window[1:] != want[1:]:
        return f"the span is not the text at lines {a}-{b} — the address points somewhere else"
    return ""


def _verify_quotes(text: str, by_id: dict[str, Entry]) -> tuple[list[tuple[str, str]], int]:
    """(problems, spans verified). A span is verified when the page's block, un-prefixed, is
    line-for-line identical to the section it names AND to the line range it cites."""
    problems: list[tuple[str, str]] = []
    verified = 0
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _Q_RE.match(lines[i])
        if not m:
            i += 1
            continue
        eid, sname = m.group(1), m.group(2)
        block = []
        i += 1
        while i < len(lines) and (lines[i].startswith(">") or lines[i] == ""):
            if lines[i] == "":
                break
            block.append(lines[i])
            i += 1
        e = by_id.get(eid)
        if e is None:
            problems.append(
                ("paraphrased-quote", f"cites entry `{eid}`, which no protocol file provides")
            )
            continue
        src = e.section_lines().get(sname)
        if src is None:
            problems.append(
                ("paraphrased-quote", f"cites `{eid}#{sname}`, a section that entry does not have")
            )
            continue
        if not _same(_unquote(block), src):
            problems.append(
                (
                    "paraphrased-quote",
                    f"the block citing `{eid}#{sname}` is NOT verbatim in that entry — a compiled "
                    f"page may rearrange spans, never reword them",
                )
            )
            continue
        # the address printed under the block
        j = i
        while j < len(lines) and not lines[j].startswith("[[cite:"):
            if lines[j].strip() and not lines[j].startswith(">"):
                break
            j += 1
        am = _ADDR_RE.match(lines[j]) if j < len(lines) else None
        if am is None:
            problems.append(
                (
                    "bad-address",
                    f"the block citing `{eid}#{sname}` carries no resolvable `[[cite: ...]]` "
                    f"address — a quote nobody can look up is not a citation",
                )
            )
            continue
        why = _verify_address(e, _unquote(block), int(am.group("a")), int(am.group("b")))
        if why:
            problems.append(("bad-address", f"`{eid}#{sname}`: {why}"))
            continue
        verified += 1
    return problems, verified


def check(root: Path) -> tuple[list[tuple[str, str]], int, int, Plan, dict]:
    """(findings, pages examined, spans verified, plan, report). Never exits; see `_check_main`."""
    entries = load_entries(root)
    claims, claim_load = load_claims(root)
    pl = plan(entries, claims)
    by_id = {e.eid: e for e in entries}
    found: list[tuple[str, str]] = []
    verified = 0
    skipped = pl.skipped_topics

    for e in pl.quarantined:
        cls = "malformed-topic" if e.bad_topics else "unknown-track"
        found.append((cls, f"`{e.eid}`: {e.quarantine}"))

    # The claims layer is judged BEFORE any page, and a broken claim quarantines the topics it
    # touches (see `resolve_claims`). The claims file is one file, so its findings are reported
    # whole rather than first-match: three malformed claims are three defects, not one page.
    found.extend(claim_load)
    found.extend(pl.claim_findings)

    # A stamped page whose TOPIC is still derived but whose PATH is not the derived one has not
    # been orphaned — its track changed and nobody recompiled. Saying "no entry carries this topic"
    # about it would be false, and a finding that states something untrue is worse than no finding.
    misfiled: dict[str, str] = {}
    for p in _wiki_pages_on_disk(root):
        rel = str(p.relative_to(root))
        s = _stamp_of(p.read_text(encoding="utf-8"))
        if s and s.get("topic") in pl.pages and rel != pl.pages[s["topic"]].rel:
            misfiled.setdefault(s["topic"], rel)

    seen_paths: set[str] = set()
    examined = 0
    for topic, page in sorted(pl.pages.items()):
        if topic in skipped:
            # Refusing to judge a page whose input could not be read. The finding is on the entry.
            continue
        examined += 1
        seen_paths.add(page.rel)
        target = root / page.rel
        if not target.is_file():
            if topic in misfiled:
                # The finding is on the misfiled file, below. Reporting both is reporting one
                # situation twice, and one recompile answers both.
                continue
            found.append(
                (
                    "missing-page",
                    f"topic `{topic}` has {len(page.entries)} entry(ies) but no page on disk at "
                    f"`{page.rel}` — the protocol moved ahead of the wiki; recompile",
                )
            )
            continue
        text = target.read_text(encoding="utf-8")
        stamp = _stamp_of(text)
        if stamp is None:
            found.append(
                (
                    "unstamped-page",
                    f"`{page.rel}` carries no stamp — a page in an audience directory is compiled "
                    f"output; an authored one has nothing to check it against",
                )
            )
            continue
        if stamp.get("source_hash") != page.source_hash:
            found.append(
                (
                    "stale-stamp",
                    f"`{page.rel}`: source_hash `{str(stamp.get('source_hash'))[:16]}…` was "
                    f"compiled from {len(stamp.get('entries') or [])} entry(ies); the protocol now "
                    f"gives {len(page.entries)} with hash `{page.source_hash[:16]}…` — the protocol "
                    f"moved under this page",
                )
            )
            continue
        problems, n = _verify_quotes(text, by_id)
        if problems:
            cls, msg = problems[0]
            found.append((cls, f"`{page.rel}`: {msg}"))
            continue
        if text != render(page):
            found.append(
                (
                    "hand-edited-page",
                    f"`{page.rel}` differs from the derived page though every quote is still "
                    f"verbatim and the stamp is current — something was authored into generated "
                    f"output",
                )
            )
            continue
        verified += n

    for p in _wiki_pages_on_disk(root):
        rel = str(p.relative_to(root))
        if rel in seen_paths:
            continue
        text = p.read_text(encoding="utf-8")
        stamp = _stamp_of(text)
        if stamp is None:
            examined += 1
            found.append(
                (
                    "unstamped-page",
                    f"`{rel}` carries no stamp — a page in an audience directory is compiled "
                    f"output; an authored one has nothing to check it against",
                )
            )
            continue
        topic = stamp.get("topic")
        if topic in skipped:
            continue
        examined += 1
        if topic in pl.pages:
            found.append(
                (
                    "misfiled-page",
                    f"`{rel}` is stamped as topic `{topic}`, which now compiles to "
                    f"`{pl.pages[topic].rel}` — the topic's track changed and this page was never "
                    f"moved; recompile and the compiler will move it, because a move IS derivable",
                )
            )
            continue
        found.append(
            (
                "orphan-page",
                f"`{rel}` is stamped as topic `{topic}`, and no entry carries topic `{topic}` — "
                f"this page is derived from nothing. Restore the entry or delete the page; the "
                f"compiler will not delete it for you, because a disappearance is not derivable "
                f"the way a move is",
            )
        )

    # THE FRONT DOOR IS A PAGE TOO, and it is checked like one. It carries no quoted span — it is
    # pure derived structure — so the only predicate that applies is "is it still what the pages
    # say it is". Without this, the one page a reader opens first is the one page nothing guards.
    # ORDER, and it is the same argument the rest of this gate makes: the index is derived from
    # the pages, so ANY finding above already changes what the index should say. Judging it anyway
    # would report one situation twice under two class names, and one recompile answers both.
    idx = root / INDEX_REL
    if pl.pages and not skipped and not found:
        examined += 1
        if not idx.is_file():
            found.append(
                (
                    "stale-index",
                    f"`{INDEX_REL}` does not exist though {len(pl.pages)} page(s) compile — the "
                    f"wiki has no front door; recompile",
                )
            )
        elif idx.read_text(encoding="utf-8") != render_index(pl):
            found.append(
                (
                    "stale-index",
                    f"`{INDEX_REL}` is not what the {len(pl.pages)} compiled page(s) derive — it "
                    f"was edited by hand or the protocol moved under it; recompile",
                )
            )

    report = {
        "entries": len(entries),
        "pages": len(pl.pages),
        "no_topic": [e.eid for e in pl.no_topic],
        "untracked": [e.eid for e in pl.untracked],
        "skipped": sorted(skipped),
        "claims": len(pl.claims),
        "claimed_entries": len(pl.claimed_entries),
        "by_track": {
            t: sum(1 for p in pl.pages.values() if p.track == t) for t in sorted(TRACK_DIR)
        },
    }
    return found, examined, verified, pl, report


def _detail(report: dict) -> str:
    bt = ", ".join(f"{TRACK_DIR[t]} {n}" for t, n in report["by_track"].items())
    parts = [
        f"{report['entries']} entry(ies) -> {report['pages']} page(s) ({bt})",
        f"{len(report['no_topic'])} entry(ies) carried NO topic and are on no page",
        f"{len(report['untracked'])} entry(ies) declared no track",
        # The claims-layer denominator. A wiki whose pages are all verbatim and all uninterpreted
        # is a correct anthology, and this is the number that says so out loud.
        f"{report['claims']} normative span(s) marked over {report['claimed_entries']} of "
        f"{report['entries']} entry(ies)",
    ]
    if report["skipped"]:
        parts.append(f"{len(report['skipped'])} topic(s) NOT judged: {', '.join(report['skipped'])}")
    return "; ".join(parts)


def _outcome(root: Path):
    found, examined, verified, _pl, report = check(root)
    return gate.Outcome(
        len(found),
        examined,
        "page(s)",
        classes={c for c, _ in found},
        secondary=(verified, "span(s) verified verbatim"),
    ), report


def _check_main(root: Path) -> int:
    entries = load_entries(root)
    if not entries:
        return gate.could_not_run(
            NAME,
            f"{root / 'protocol'} carries 0 entry file(s). An empty protocol compiles to an empty "
            f"wiki, and 0 page(s) verified is not a clean wiki — it is a wiki nobody has written "
            f"the raw record for",
        )
    outcome, report = _outcome(root)
    found, _e, _v, _pl, _r = check(root)
    for cls, msg in found:
        print(f"  [{cls}] {msg}")
    for eid in report["no_topic"]:
        print(f"  [no-topic] `{eid}` carries no `topics:` — it is in the protocol and on no page")
    line, code = gate.verdict(NAME, outcome, detail=_detail(report))
    print(line)
    return code


# -------------------------------------------------------------------------------------------------
# the self-test: one mutant per reject class, two must-pass fixtures, five extras
# -------------------------------------------------------------------------------------------------
# The fixture protocol is GENERIC by construction — no source, no brand, no warehouse, no estate
# path. A fixture is not an exemption from the public-repo rule, and its numbers are deliberately
# small and obviously synthetic so nothing here can be mistaken for a real measurement.

_E1 = (
    "2026-01-02/001-denominator.md",
    """---
when: 2026-01-02T09:00:00
what: made the example gate print how many files it examined
topics: [gates]
track: core
kind: measurement
---

* **WHAT FORCED IT** — a gate reported PASS while examining nothing at all.

* **EVIDENCE** —

  ```
  $ example-gate
  PASS: example-gate — 0 finding(s) over 0 file(s) examined
  ```

* **WHAT CHANGED** — the verdict line now carries its denominator, at `sdk/gate/contract.py:141`.

* **WHAT IT DOES NOT PROVE** — nothing about the gates that were never invoked.
""",
)

_E2 = (
    "2026-01-02/002-grain.md",
    """---
when: 2026-01-02T14:30:00
what: declared what one row of a served dataset means
topics: [grain]
track: ontology
kind: decision
---

* **WHAT FORCED IT** — two concepts bound the same relation at two different grains.

* **EVIDENCE** — `decisions/2026-01-02_grain.md` §3 records the count: 2 of 7 concept(s).

* **WHAT CHANGED** — the cell key is declared beside the evidence that it is unique.

* **WHAT IT DOES NOT PROVE** — that the remaining 5 concept(s) were re-measured.
""",
)

_E3 = (
    "2026-01-03/001-page-shape.md",
    """---
when: 2026-01-03T10:00:00
what: gave the compiled page a stamp of what it was compiled from
topics: [pages]
track: platform
kind: build
---

* **WHAT FORCED IT** — a page said something the record no longer did, and nothing caught it.

* **EVIDENCE** — `tools/mac_resources.py:31` states the defect for bundle descriptions.

* **WHAT CHANGED** — every page carries `source_hash` over its entries' bytes.

* **WHAT IT DOES NOT PROVE** — that a cited `file:line` still exists.
""",
)

_E4 = (
    "2026-01-04/001-page-shape-revised.md",
    """---
when: 2026-01-04T08:15:00
what: replaced the stamp's file list with a hash over the entries themselves
topics: [pages]
track: platform
kind: build
supersedes: 2026-01-03/001-page-shape
---

* **WHAT FORCED IT** — a file list compares equal while the bytes underneath move.

* **EVIDENCE** —

  ```
  $ example-check
  FAIL: example-check — 1 violation(s) over 3 page(s) examined
  ```

* **WHAT CHANGED** — the stamp hashes each entry's id and bytes.

* **WHAT IT DOES NOT PROVE** — that a reader agrees with how the spans were grouped.
""",
)

_UNTOPICED = (
    "2026-01-05/001-no-topic.md",
    """---
when: 2026-01-05T09:00:00
what: did a thing nobody filed under a topic
topics: []
track: core
kind: build
---

* **WHAT FORCED IT** — an entry was written in a hurry.

* **EVIDENCE** — this fixture.

* **WHAT CHANGED** — nothing; it exists to be counted.

* **WHAT IT DOES NOT PROVE** — that anyone will ever read it.
""",
)

_CROSS_TRACK = (
    "2026-01-06/001-grain-for-the-platform.md",
    """---
when: 2026-01-06T09:00:00
what: made the platform read the declared grain instead of inferring one
topics: [grain]
track: platform
kind: build
---

* **WHAT FORCED IT** — the platform inferred a grain the ontology had already declared.

* **EVIDENCE** — 1 of 1 inference site(s) removed.

* **WHAT CHANGED** — the declared grain is read.

* **WHAT IT DOES NOT PROVE** — that every consumer reads it.
""",
)


#: The fixture CLAIMS LAYER. Two roles, one narrowed topic, one unratified — enough shape for the
#: four claim-facing reject classes to be mutated independently of each other.
_CLAIMS = """# fixture claims layer
claims:
  - span: 2026-01-02/001-denominator#WHAT CHANGED
    holds: rule
    by: fixture
    ratified: true
  - span: 2026-01-02/001-denominator#WHAT IT DOES NOT PROVE
    holds: boundary
    by: fixture
  - span: 2026-01-02/002-grain#WHAT CHANGED
    holds: rule
    topics: [grain]
    by: fixture
"""


def _seed(root: Path, *pairs) -> None:
    for rel, text in pairs:
        p = root / "protocol" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _clean(root: Path) -> None:
    _seed(root, _E1, _E2, _E3, _E4)
    (root / "protocol" / "README.md").write_text("# fixture protocol\n", encoding="utf-8")
    (root / CLAIMS_FILE).write_text(_CLAIMS, encoding="utf-8")
    compile_wiki(root)


def _mp_untopiced(root: Path) -> None:
    _clean(root)
    _seed(root, _UNTOPICED)
    compile_wiki(root)


def _mp_no_claims(root: Path) -> None:
    """THE CLAIMS LAYER IS OPTIONAL, and this fixture is what stops it becoming compulsory by
    accident. A repository that has written the raw record and not yet interpreted it is in a
    correct state. `sdk/gate/contract.py` names the cost of getting this wrong: "A gate that
    rejects the absence of an optional thing is the most expensive kind of wrong." Here it would
    buy invented normativity on every page, which is the one thing this instrument must never
    produce."""
    _seed(root, _E1, _E2, _E3, _E4)
    (root / "protocol" / "README.md").write_text("# fixture protocol\n", encoding="utf-8")
    compile_wiki(root)


def _mp_cross_track(root: Path) -> None:
    _clean(root)
    _seed(root, _CROSS_TRACK)
    compile_wiki(root)


def _m_missing_page(root: Path) -> Path:
    # A NEW topic with no page yet. Deleting a page cannot express this: the harness asserts the
    # seeder wrote a path that exists, which is how it catches a mutant that did not mutate.
    return gate.write(
        root / "protocol" / "2026-01-07/001-new-topic.md",
        "---\nwhen: 2026-01-07T09:00:00\nwhat: opened a topic nobody has compiled yet\n"
        "topics: [connectors]\ntrack: platform\nkind: build\n---\n\n"
        "* **EVIDENCE** — 1 of 1 fixture(s).\n",
    )


def _m_stale_stamp(root: Path) -> Path:
    # An EXISTING topic, so the page set is unchanged and only its source_hash moves.
    return gate.write(
        root / "protocol" / "2026-01-07/002-more-gates.md",
        "---\nwhen: 2026-01-07T10:00:00\nwhat: added one more gate to the suite\n"
        "topics: [gates]\ntrack: core\nkind: build\n---\n\n"
        "* **EVIDENCE** — 9 of 9 self-test(s) green.\n",
    )


def _m_unstamped_page(root: Path) -> Path:
    return gate.write(
        root / "wiki" / "core" / "hand-authored.md",
        "# Hand authored\n\nSomebody wrote this straight into the wiki.\n",
    )


def _m_orphan_page(root: Path) -> Path:
    stamp = {
        "spec": SPEC,
        "generator": GENERATOR,
        "topic": "retired",
        "track": "platform",
        "entries": ["2025-12-31/001-gone"],
        "source_hash": "0" * 64,
    }
    return gate.write(
        root / "wiki" / "platform-builder" / "retired.md",
        "<!-- mac-wiki-stamp " + json.dumps(stamp, sort_keys=True) + " -->\n\n# Retired\n",
    )


def _rewrite(p: Path, old: str, new: str) -> Path:
    """Substitute, and REFUSE to be a no-op.

    A seeder that writes a file without changing it still passes the harness's "did it write?"
    assertion, and the mutant then fails for the right reason with the wrong explanation. This
    estate has already shipped a self-test that passed because the token it planted was absent, so
    every substitution here proves it landed.
    """
    before = p.read_text(encoding="utf-8")
    if old not in before:
        raise AssertionError(f"seeder found no {old!r} in {p.name} — the mutant would not mutate")
    p.write_text(before.replace(old, new, 1), encoding="utf-8")
    return p


def _m_paraphrased_quote(root: Path) -> Path:
    # The exact defect the whole instrument exists to stop: a measurement restated as a mood.
    return _rewrite(
        root / "wiki" / "core" / "gates.md",
        "PASS: example-gate — 0 finding(s) over 0 file(s) examined",
        "the gate was clean",
    )


def _m_hand_edited_page(root: Path) -> Path:
    p = root / "wiki" / "platform-builder" / "pages.md"
    p.write_text(
        p.read_text(encoding="utf-8") + "\nOne of us also thinks this, and no entry says it.\n",
        encoding="utf-8",
    )
    return p


def _m_unknown_track(root: Path) -> Path:
    return _rewrite(root / "protocol" / _E2[0], "track: ontology", "track: ontologyy")


def _m_malformed_topic(root: Path) -> Path:
    # ADDED, not substituted: the entry keeps `pages`, so that page is quarantined rather than
    # orphaned, and exactly one class fires.
    return _rewrite(root / "protocol" / _E3[0], "topics: [pages]", "topics: [pages, ../escape]")


def _m_misfiled_page(root: Path) -> Path:
    """The page stays, its topic stays, only its home is wrong — the state a track change leaves
    behind when nobody recompiles."""
    src = root / "wiki" / "ontology-builder" / "grain.md"
    dst = root / "wiki" / "core" / "grain.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    src.unlink()
    return dst


def _m_bad_address(root: Path) -> Path:
    """The quote stays verbatim; only the line numbers under it lie. Nothing but an address check
    can see this — which is exactly why an unverified address must not be printed."""
    p = root / "wiki" / "core" / "gates.md"
    text = p.read_text(encoding="utf-8")
    for ln in text.splitlines():
        am = _ADDR_RE.match(ln)
        if am:
            a, b = int(am.group("a")), int(am.group("b"))
            return _rewrite(p, ln, f"[[cite: protocol/{am.group('eid')}.md:{a + 1}-{b + 1}]]")
    raise AssertionError("no citation address on the fixture page — the mutant would not mutate")


def _add_claim(root: Path, block: str) -> Path:
    """Append one claim to the fixture claims layer, and REFUSE to be a no-op.

    WHY EVERY CLAIM MUTANT ADDS RATHER THAN CORRUPTS. Rewriting an existing claim removes a span
    from a page that carried it, so the page on disk stops matching the derived one and a SECOND
    class fires — the mutant would be rejected for two reasons and attributed to neither. Adding a
    broken claim leaves every page byte-identical, so exactly one predicate can see it. It is also
    the realistic defect: claims are written after the fact, one at a time.
    """
    p = root / CLAIMS_FILE
    before = p.read_text(encoding="utf-8")
    p.write_text(before + block, encoding="utf-8")
    if p.read_text(encoding="utf-8") == before:
        raise AssertionError("claim seeder wrote nothing — the mutant would not mutate")
    return p


def _m_malformed_claims(root: Path) -> Path:
    """A span that is not `entry#SECTION`. It names nothing, so it can quarantine nothing, which is
    exactly why it has to be reported rather than dropped."""
    return _add_claim(root, "  - span: the bit about denominators\n    holds: rule\n")


def _m_unknown_claim_role(root: Path) -> Path:
    """A role outside the closed vocabulary. Rendering it under a default heading would be
    interpretation nobody wrote, so the compiler refuses to place it."""
    return _add_claim(
        root, "  - span: 2026-01-03/001-page-shape#WHAT CHANGED\n    holds: important\n"
    )


def _m_dangling_claim(root: Path) -> Path:
    """The entry exists; the SECTION does not. This is the drift that actually happens — a claim
    written against a section name that the entry never had, or no longer has."""
    return _add_claim(
        root, "  - span: 2026-01-03/001-page-shape#WHAT WE FELT\n    holds: rule\n"
    )


def _m_claim_topic_mismatch(root: Path) -> Path:
    """Narrowed to a topic its entry does not carry: the claim compiles onto no page at all, and a
    claims file that reads as filed while landing nowhere is worse than an empty one."""
    return _add_claim(
        root,
        "  - span: 2026-01-02/001-denominator#EVIDENCE\n    holds: rule\n    topics: [grain]\n",
    )


def _m_stale_index(root: Path) -> Path:
    """The front door, edited by hand. Nothing else on the tree moves — which is the point: before
    this class the one page a reader opens first was the one page nothing checked."""
    p = root / INDEX_REL
    p.write_text(
        p.read_text(encoding="utf-8") + "\nSomebody added a page to the list by hand.\n",
        encoding="utf-8",
    )
    return p


_MUTANTS = {
    "missing-page": _m_missing_page,
    "malformed-claims": _m_malformed_claims,
    "unknown-claim-role": _m_unknown_claim_role,
    "dangling-claim": _m_dangling_claim,
    "claim-topic-mismatch": _m_claim_topic_mismatch,
    "stale-index": _m_stale_index,
    "stale-stamp": _m_stale_stamp,
    "unstamped-page": _m_unstamped_page,
    "orphan-page": _m_orphan_page,
    "paraphrased-quote": _m_paraphrased_quote,
    "hand-edited-page": _m_hand_edited_page,
    "unknown-track": _m_unknown_track,
    "malformed-topic": _m_malformed_topic,
    "misfiled-page": _m_misfiled_page,
    "bad-address": _m_bad_address,
}

_EXPECT_LINE = {
    "missing-page": "no page on disk",
    "malformed-claims": "is not `YYYY-MM-DD/entry-slug#SECTION NAME`",
    "unknown-claim-role": "is not one of ['boundary', 'rule']",
    "dangling-claim": "which that entry does not have",
    "claim-topic-mismatch": "would compile onto no page",
    "stale-index": "edited by hand or the protocol moved under it",
    "stale-stamp": "moved under this page",
    "unstamped-page": "carries no stamp",
    "orphan-page": "derived from nothing",
    "paraphrased-quote": "NOT verbatim in that entry",
    "hand-edited-page": "differs from the derived page",
    "unknown-track": "is not one of",
    "malformed-topic": "is not a legal topic token",
    "misfiled-page": "was never moved; recompile",
    "bad-address": "the address is not",
}


def _x_no_entries_refuses(base: Path) -> tuple[int, int]:
    """No protocol at all is a could-not-run. It is the live state of a repository that has just
    adopted this instrument, and calling it PASS would be the estate's dominant defect."""
    root = base / "_x_empty"
    (root / "protocol").mkdir(parents=True, exist_ok=True)
    code, text = gate._capture(_check_main, root)
    got = 0
    if code == 2:
        got += 1
    if "0 entry file(s)" in text:
        got += 1
    return got, 2


def _x_all_untopiced_refuses(base: Path) -> tuple[int, int]:
    """Entries exist, none carries a topic -> zero pages. Also exit 2, and the line must say how
    many entries went nowhere, because that is the number a reader would otherwise never see."""
    root = base / "_x_untopiced"
    root.mkdir(parents=True, exist_ok=True)
    _seed(root, _UNTOPICED)
    code, text = gate._capture(_check_main, root)
    got = 0
    if code == 2:
        got += 1
    if "1 entry(ies) carried NO topic" in text:
        got += 1
    return got, 2


def _x_no_topic_is_disclosed_not_dropped(base: Path) -> tuple[int, int]:
    """The number people skip, printed on a PASSING run — disclosed, never fatal. Making it fatal
    buys an invented topic on every entry, which is worse than an honest zero."""
    root = base / "_x_disclosed"
    root.mkdir(parents=True, exist_ok=True)
    _mp_untopiced(root)
    code, text = gate._capture(_check_main, root)
    got = 0
    if code == 0:
        got += 1
    if "1 entry(ies) carried NO topic and are on no page" in text:
        got += 1
    if "[no-topic] `2026-01-05/001-no-topic`" in text:
        got += 1
    return got, 3


def _x_pass_line_carries_both_denominators(base: Path) -> tuple[int, int]:
    """A PASS with no denominator is unquotable. This asserts both of them survive a refactor."""
    root = base / "_x_denoms"
    root.mkdir(parents=True, exist_ok=True)
    _clean(root)
    code, text = gate._capture(_check_main, root)
    got = 0
    if code == 0:
        got += 1
    if "page(s) examined" in text:
        got += 1
    if "span(s) verified verbatim" in text:
        got += 1
    if "entry(ies) ->" in text:
        got += 1
    return got, 4


def _x_nothing_is_dropped(base: Path) -> tuple[int, int]:
    """Every non-empty line of every compiled entry appears on a page. A compiler that loses a
    paragraph is a summariser with extra steps, and the loss would be invisible."""
    root = base / "_x_lossless"
    root.mkdir(parents=True, exist_ok=True)
    _clean(root)
    pl = plan(load_entries(root), load_claims(root)[0])
    pages = {t: (root / p.rel).read_text(encoding="utf-8") for t, p in pl.pages.items()}
    missing = 0
    total = 0
    for topic, page in pl.pages.items():
        rendered = [ln.rstrip() for ln in _unquote(pages[topic].splitlines())]
        for e in page.entries:
            for _s, lines, _a, _b in e.sections():
                for ln in lines:
                    if not ln.strip():
                        continue
                    total += 1
                    if ln.rstrip() not in rendered:
                        missing += 1
    return (1 if (missing == 0 and total > 0) else 0), 1


def _x_unclaimed_page_declares_it(base: Path) -> tuple[int, int]:
    """A page nobody has interpreted says so IN THE PAGE, and the verdict carries the denominator.
    Silence here would let an anthology be read as compiled knowledge, which is the precise failure
    the claims layer was added to remove."""
    root = base / "_x_unclaimed"
    root.mkdir(parents=True, exist_ok=True)
    _mp_no_claims(root)
    text = (root / "wiki" / "core" / "gates.md").read_text(encoding="utf-8")
    code, out = gate._capture(_check_main, root)
    got = 0
    if "## What holds — NOT YET COMPILED" in text:
        got += 1
    if "No span on this page has been marked normative" in text:
        got += 1
    if code == 0:
        got += 1
    if "0 normative span(s) marked over 0 of 4 entry(ies)" in out:
        got += 1
    return got, 4


def _x_claims_are_verbatim_and_first(base: Path) -> tuple[int, int]:
    """A marked span is rendered ABOVE the chronology and is still the entry's own bytes. Both
    halves matter: first is what makes the page readable, verbatim is what makes it checkable."""
    root = base / "_x_claims"
    root.mkdir(parents=True, exist_ok=True)
    _clean(root)
    text = (root / "wiki" / "core" / "gates.md").read_text(encoding="utf-8")
    e = {x.eid: x for x in load_entries(root)}["2026-01-02/001-denominator"]
    quoted = [ln[2:].rstrip() for ln in text.splitlines() if ln.startswith("> ")]
    want = [ln.rstrip() for ln in e.section_lines()["WHAT CHANGED"] if ln.strip()]
    got = 0
    if "## What holds" in text and "## What is not settled" in text:
        got += 1
    if "## What holds" in text and text.index("## What holds") < text.index(
        "## What this page was compiled from"
    ):
        got += 1
    if want and all(w in quoted for w in want):
        got += 1
    if "UNRATIFIED" in text:
        got += 1
    return got, 4


def _x_index_is_derived_from_every_page(base: Path) -> tuple[int, int]:
    """The front door names every page, its topic, its audience, its entry count and its stamp —
    and it is re-derived, so it cannot be the one hand-maintained file in a compiled tree."""
    root = base / "_x_front_door"
    root.mkdir(parents=True, exist_ok=True)
    _clean(root)
    idx = (root / INDEX_REL).read_text(encoding="utf-8")
    pl = plan(load_entries(root), load_claims(root)[0])
    got = 0
    if pl.pages and all(p.source_hash[:16] in idx for p in pl.pages.values()):
        got += 1
    if all(f"]({p.rel[len('wiki/'):]})" in idx for p in pl.pages.values()):
        got += 1
    if all(f"`wiki/{d}/`" in idx for d in TRACK_DIR.values()):
        got += 1
    if idx == render_index(pl):
        got += 1
    return got, 4


def _contract():
    return gate.GateContract(
        name=NAME,
        clean=_clean,
        mutants=dict(_MUTANTS),
        run=lambda r: _outcome(r)[0],
        must_pass={
            "an entry with no topic is disclosed, never rejected": _mp_untopiced,
            "a protocol with NO claims layer compiles and passes — interpretation is optional": (
                _mp_no_claims
            ),
            "a topic both tracks touch compiles to core, and the old page is MOVED not orphaned": (
                _mp_cross_track
            ),
        },
        expect_line=dict(_EXPECT_LINE),
        main=_check_main,
        # Stated rather than inferred: the day someone deletes `classes=` from `_outcome` to quiet
        # a failure, this is what turns it red instead of silently downgrading the self-test to
        # "rejected by finding count only".
        attributes_classes=True,
        extra={
            "no protocol entries at all is a could-not-run": _x_no_entries_refuses,
            "entries but no topics is a could-not-run, with the count printed": (
                _x_all_untopiced_refuses
            ),
            "an untopiced entry is printed by id on a PASSING run": (
                _x_no_topic_is_disclosed_not_dropped
            ),
            "the PASS line carries both denominators": _x_pass_line_carries_both_denominators,
            "every line of every compiled entry survives onto a page": _x_nothing_is_dropped,
            "a page with no marked span declares it, and the verdict prints the denominator": (
                _x_unclaimed_page_declares_it
            ),
            "a marked span is rendered first and is still the entry's own bytes": (
                _x_claims_are_verbatim_and_first
            ),
            "the index is derived from every page it lists": _x_index_is_derived_from_every_page,
        },
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("root", nargs="?", default=str(ROOT), help="repository root (has protocol/, wiki/)")
    ap.add_argument("--check", action="store_true", help="re-derive and refuse if a page has drifted")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if gate is None:
        print(
            f"could not run: {NAME} — `sdk.gate.contract` did not import, so this tool cannot say "
            f"PASS or FAIL in the estate's one contract. Run from the repository root.",
            file=sys.stderr,
        )
        return 2
    if yaml is None:
        print(f"could not run: {NAME} — PyYAML is required to read entry front matter", file=sys.stderr)
        return 2

    if a.self_test:
        return gate.run_self_test(_contract())

    root = Path(a.root).resolve()
    if not root.is_dir():
        return gate.could_not_run(NAME, f"{root} is not a directory")

    if a.check:
        return _check_main(root)

    entries = load_entries(root)
    if not entries:
        return gate.could_not_run(
            NAME,
            f"{root / 'protocol'} carries 0 entry file(s) — there is nothing to compile, and an "
            f"empty wiki written confidently is worse than none",
        )
    rep = compile_wiki(root)
    if rep["pages"] == 0:
        return gate.could_not_run(
            NAME,
            f"{rep['entries']} entry(ies) carry no `topics:` between them, so 0 page(s) would be "
            f"written — a wiki of nothing is not a compiled wiki",
        )
    for rel in rep["written"]:
        print(f"  wrote   {rel}")
    for mv in rep["moved"]:
        print(f"  moved   {mv}  (its topic's track changed)")
    for eid in rep["no_topic"]:
        print(f"  [no-topic] `{eid}` carries no `topics:` — it is in the protocol and on no page")
    for eid, why in rep["quarantined"]:
        print(f"  [not placed] `{eid}`: {why}")
    for rel in rep["orphans"]:
        print(f"  [orphan] {rel} — no entry carries its topic; --check will fail on it")
    for cls, msg in rep["claim_findings"]:
        print(f"  [{cls}] {msg}")
    bt = ", ".join(f"{TRACK_DIR[t]} {n}" for t, n in rep["by_track"].items())
    print(
        f"compiled {rep['entries']} entry(ies) -> {rep['pages']} page(s) ({bt}); "
        f"{len(rep['written'])} written, {len(rep['moved'])} moved, "
        f"{len(rep['no_topic'])} entry(ies) carried NO topic and are on no page, "
        f"{len(rep['untracked'])} declared no track, {len(rep['quarantined'])} could not be placed; "
        f"{rep['claims']} normative span(s) marked over {rep['claimed_entries']} of "
        f"{rep['entries']} entry(ies), {len(rep['claim_findings'])} claim(s) rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
