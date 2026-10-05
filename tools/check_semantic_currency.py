#!/usr/bin/env python3
"""check_semantic_currency.py — A DOCUMENT MUST NOT CLAIM SOMETHING THAT IS NO LONGER TRUE.

`check_dangling_references.py` answers REFERENTIAL currency: does the pointer resolve. Nothing in this
estate answered SEMANTIC currency — the pointer resolves and the CLAIM is dead. A page that presents
`concept.semantics.unit` as a key you may write is referentially perfect and lying: the whole
concept-wide `semantics:` block was removed from the schema. Operator, 2026-10-04: "many things have
changed ... or EVOLVED and it is misleading if we keep them in although they are long retired".

THE DISTINCTION THE WHOLE GATE TURNS ON. Two sentences a grep cannot separate, both from CONFORMANCE:

    "the constraint gate is new in v0.1.6"          LEGITIMATE — past tense about a past version
    "it rides on the CURRENT `0.1.12` generation"   MISLEADING — present tense, four releases stale
    "would go out under the NEXT number, `0.1.13`"  MISLEADING — a future that already happened

So the question is never "is this thing current" — it is "does the sentence claim it IS current". A
document describing the PRESENT that names a dead thing is the defect. A document recording the PAST is
the archive, and rewriting it would falsify the record: `protocol/` is append-only by its own README.

WHAT THE FIRST DRAFT GOT WRONG, each class now an exemption with a reason. A rule that cries wolf gets
switched off, so these are the gate, not footnotes to it:

  RELATIVE KEY PATHS     The estate writes keys relative at every depth: a page says
                         `identity.canonical_key` for the schema's
                         `concept.concept.identity.canonical_key` (there is a `concept:` key inside
                         ConceptFile, so the real path doubles the word). Trying ONE `concept.` prefix
                         called 3 current pages dead. Matched by SUFFIX, which under-reports — the
                         right direction for this rule.
  `CURRENT` THE CONSTANT  `CURRENT` is the validator's name. Inside backticks it is an identifier, not
                         a claim about currency; it made CONFORMANCE's release procedure read as four
                         stale assertions. Backticked spans are blanked before the tense test.
  THE DELIBERATE NON-EXAMPLE  `mac.connector.athna` is named as "the typo it exists to catch";
                         `mac.connector.postgres` as "a HYPOTHETICAL". A page is allowed to name a
                         thing in order to say it is not real.
  THE PARAGRAPH, NOT THE LINE  41 dead keys are listed over six lines and the verb that retires them
                         ("were read by no line of the runtime") is on the seventh. The tense test
                         reads the enclosing PARAGRAPH.
  A GENERATED PAGE       is not a claim its author made; the fix belongs in the generator. Detected by
                         its stamp anywhere in the head — a 600-character window missed the wiki's,
                         whose stamp comment is longer than that, and counted a report ABOUT stale
                         versions as four stale versions.

ONE HOME PER FACT. The canon's implemented set comes from `mac_runtime.canon.IMPLEMENTED`, the key set
from `gen_structure_reference`'s own walk, the version from `mac.schema.json`. Nothing here is typed. The
"a canon the runtime honours has no page" question is NOT asked here: `check_canon_documented.py`
already owns it, and a second home for it is the defect this estate names most.

ONLY NEWS EXITS 1. The measured non-conformances are declared in `guardrails/semantic_currency.yaml`
with an owner and a reason; they are counted and NAMED on every run and exit 0. One that has started
conforming is STANDING_STALE and exits 1, so the list cannot rot into an excuse.

    python3 tools/check_semantic_currency.py              # judge this repository
    python3 tools/check_semantic_currency.py --page       # write reference_manual/CURRENCY.md
    python3 tools/check_semantic_currency.py --self-test
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DECL = ROOT / "guardrails" / "semantic_currency.yaml"
PAGE = ROOT / "reference_manual" / "CURRENCY.md"

REJECTS = (
    "CANON_STATUS_CONTRADICTS_RUNTIME",   # the page says NOT IMPLEMENTED; the runtime honours it
    "STALE_FRONTMATTER_VERSION",          # the page declares a schema version that is not the schema's
    "STALE_VERSION_CLAIMED_CURRENT",      # prose calls a past version "current" or "next"
    "DEAD_KEY_PRESENTED_AS_LIVE",         # a key path the schema no longer carries, stated as live
    "STANDING_STALE",                     # a declared standing entry that now conforms
)

#: A record of the past. `protocol/README.md`: "Append-only. Entries are never edited."
ARCHIVE = ("protocol/", "decisions/")
#: Not this repository's prose: an applied ontology's own files, and frozen expected values.
#: example_tpch_ontology was removed 2026-10-04; a name excluding a directory that is gone is an exemption over nothing.
NOT_PROSE = ("example_shop_ontology/", "tests/")

PRESENT = re.compile(r"\b(current|currently|today|now|the next|latest|at present|as it stands|"
                     r"you (?:may|can|should|must) (?:write|declare|use))\b", re.I)
PAST = re.compile(r"\b(was|were|used to|no longer|retired|removed|deleted|superseded|replaced|"
                  r"deprecated|merged into|dropped|new in|added in|since|introduced|obsolete|"
                  r"historical|history|changelog|prior to|former|legacy|withdrawn|withdrew|"
                  r"typo|hypothetical|does not exist|no such|never|would be|promote|drop)\b", re.I)
TOK = re.compile(r"`([a-z_][a-z0-9_]*(?:\.[a-z0-9_<>]+){1,8})`")
VER = re.compile(r"\bv?(0\.1\.\d{1,2})\b")
#: How close a currency word must sit to the version it is claimed about. 40 characters admits
#: "the current `0.1.12` generation" and "the next additive number, `0.1.13`" and rejects a label
#: like "(v0.1.8)" that happens to share a sentence with an unrelated "now".
VER_CLAIM_WINDOW = 40
KEY_ROOTS = ("concept.", "mac.concept.", "column.", "semantics.", "grounding.", "contract.",
             "identity.", "projection.", "produces.", "lifecycle.")
FILE_SUFFIX = (".md", ".py", ".yaml", ".yml", ".json", ".sql", ".txt", ".html", ".sh", ".jsx",
               ".js", ".csv", ".okf", ".duckdb", ".parquet", ".toml", ".example", ".lock", ".cfg")


class CouldNotRun(Exception):
    """Exit 2. A gate that cannot ask its question must never answer it."""


# ── THE TRUTH, read from the declarations and the code ───────────────────────────────────────────
def schema_version() -> str:
    return json.loads((ROOT / "mac.schema.json").read_text(encoding="utf-8"))["version"]


def key_universe() -> set[str]:
    """Every key path and vocabulary name, from the generator's OWN walk — one home for the set."""
    try:
        import gen_structure_reference as gkr
    except ImportError as exc:
        raise CouldNotRun(f"gen_structure_reference is not importable ({exc})") from exc
    schema, vocab = gkr.load(ROOT)
    _notions, dotted = gkr.harvest_vocabulary(vocab)
    w = gkr.Walker(schema, dotted)
    w.walk(w.defs["ConceptFile"], "concept")
    w.prune_children()
    out = set(w.levels)
    for path, lvl in w.levels.items():
        for form in lvl["forms"]:
            for k in form["keys"]:
                out.add(f"{path}.{k['key']}")
    #: FLATTENED FIRST. This iterated the vocabulary's TOP-LEVEL keys, which worked only while every
    #: vocabulary WAS a top-level key spelled with dots. `mac_vocabulary.yaml` now nests them, so the top
    #: level is `concept` / `relation` / `transform` — containers with no `terms` of their own — and every
    #: term fell out of the universe. The gate then reported 6 pages as naming dead keys when nothing had
    #: changed but the file's indentation. `mac_vocab.flatten` is the one reader of that shape.
    import mac_vocab
    for name, body in mac_vocab.flatten(vocab or {}).items():
        if not isinstance(body, dict):
            continue
        out |= {name, f"mac.{name}"}
        for t in (body.get("terms") or {}):
            out |= {f"{name}.{t}", f"mac.{name}.{t}"}
    out |= {re.sub(r"<[a-z_]+>", "<name>", k) for k in out}
    return out


def honoured_canons() -> set[str]:
    """What the runtime actually does, asked of the runtime."""
    for cand in (ROOT.parent / "mac-platform" / "packages" / "mac-runtime" / "src",):
        if cand.is_dir() and str(cand) not in sys.path:
            sys.path.insert(0, str(cand))
    try:
        from mac_runtime.canon import IMPLEMENTED
    except ImportError as exc:
        raise CouldNotRun(
            f"mac_runtime.canon is not importable ({exc}). A gate that cannot ask the runtime what it "
            f"honours must not report on what the manual claims.") from exc
    return {n.rsplit(".", 1)[-1] for n in IMPLEMENTED}


def known(tok: str, universe: set[str]) -> bool:
    """Is this token a key or term the estate still carries, in ANY of its spellings?"""
    cands = {tok, re.sub(r"<[a-z_]+>", "<name>", tok), re.sub(r"\.<[a-z_]+>$", "", tok)}
    if tok.startswith("mac."):
        cands |= {tok[4:], re.sub(r"<[a-z_]+>", "<name>", tok[4:])}
    for c in cands:
        if c in universe or any(k.endswith("." + c) for k in universe):
            return True
    return False


def paragraph(text: str, pos: int) -> str:
    """The enclosing paragraph — see THE PARAGRAPH, NOT THE LINE in the module docstring."""
    a = text.rfind("\n\n", 0, pos)
    b = text.find("\n\n", pos)
    return text[(a + 2 if a >= 0 else 0):(b if b > 0 else len(text))]


def sentence(text: str, pos: int) -> str:
    """The clause the token sits in — bounded by a line break or a sentence end."""
    a = max(text.rfind("\n", 0, pos), text.rfind(". ", 0, pos), text.rfind("; ", 0, pos))
    b = text.find("\n", pos)
    return text[(a if a > 0 else 0):(b if b > 0 else len(text))]


def mask_code(text: str) -> str:
    """The text with every backticked span's CONTENT replaced by spaces, length preserved.

    MASKED ONCE OVER THE WHOLE TEXT, AND THE LENGTH IS WHY. Blanking inside a 40-character window
    starts the regex mid-span: the window `ma_version`**; it rides on the current `0.1.12` gener`
    begins with the CLOSING backtick of `schema_version`, so the pair matched runs from there to the
    OPENING backtick of `0.1.12` and swallowed "it rides on the current" — the exact words the test
    had to see. Three real defects read as `past`. Masking the whole text keeps the pairs correct, and
    keeping the length keeps every offset and line number valid.
    """
    out = list(text)
    for m in re.finditer(r"`[^`\n]*`", text):
        for i in range(m.start() + 1, m.end() - 1):
            out[i] = " "
    return "".join(out)


def tense(sent: str, para: str | None = None) -> str:
    """`present` / `past` / `unqualified`, with backticked identifiers blanked first.

    THE TWO TESTS HAVE DIFFERENT SCOPES, and collapsing them to one cost accuracy in both directions.
    A PRESENT claim is judged on the SENTENCE: CONFORMANCE's "it rides on the current `0.1.12`
    generation" sits in a paragraph that also explains a past bump, and a paragraph-wide PAST test
    exempted three real defects. A PAST qualification is judged on the PARAGRAPH: 41 retired keys are
    listed over six lines and the verb that retires them is on the seventh, so a sentence-wide test
    called them all live. So: present wins on the sentence, past exempts on the paragraph.
    """
    #: Both spans arrive ALREADY MASKED — see mask_code. Masking here would repeat the bug it fixes.
    if PRESENT.search(sent):
        return "present"
    if PAST.search(para if para is not None else sent):
        return "past"
    return "unqualified"


def is_generated(text: str) -> bool:
    head = "\n".join(text.splitlines()[:12])
    return bool(re.search(r"GENERATED by|do not edit", head, re.I))


# ── THE DECLARATION ──────────────────────────────────────────────────────────────────────────────
def load_standing() -> dict[tuple[str, str], dict]:
    if not DECL.is_file():
        return {}
    try:
        import yaml
    except ImportError as exc:
        raise CouldNotRun(f"PyYAML is not importable ({exc})") from exc
    doc = yaml.safe_load(DECL.read_text(encoding="utf-8")) or {}
    out = {}
    for e in (doc.get("standing") or []):
        if isinstance(e, dict) and e.get("file") and e.get("reject"):
            out[(str(e["file"]), str(e["reject"]))] = e
    return out


# ── THE RUN ──────────────────────────────────────────────────────────────────────────────────────
def pages():
    rels = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.md"],
                          capture_output=True, text=True).stdout.split()
    for rel in rels:
        if rel.startswith(NOT_PROSE):
            continue
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            yield rel, p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def run() -> tuple[list[dict], dict]:
    version = schema_version()
    universe = key_universe()
    honoured = honoured_canons()
    findings: list[dict] = []
    census = {"pages": 0, "archive": 0, "generated": 0, "judged": 0, "version": version,
              "keys": len(universe), "canons": len(honoured), "exempt": collections.Counter()}

    def add(cls, subject, detail, where="", file=""):
        findings.append({"reject": cls, "subject": subject, "detail": detail, "where": where,
                         "file": file or subject.split(":")[0]})

    #: 1 — THE CANON'S CLAIM AGAINST THE RUNTIME'S BEHAVIOUR.
    canon_dir = ROOT / "reference_manual" / "rules_and_canons"
    for f in sorted(canon_dir.glob("*.md")) if canon_dir.is_dir() else []:
        text = f.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^status:\s*(.*)$", text[:2000], re.M)
        st = (m.group(1) if m else "").strip()
        rel = f.relative_to(ROOT).as_posix()
        if re.match(r"(NOT IMPLEMENTED|DECLARED BUT NOT IMPLEMENTED)", st, re.I) \
                and f.stem in honoured:
            add("CANON_STATUS_CONTRADICTS_RUNTIME", rel,
                f"status says {st[:70]!r} and mac_runtime.canon.IMPLEMENTED honours `{f.stem}`")

    for rel, text in pages():
        census["pages"] += 1
        if rel.startswith(ARCHIVE):
            census["archive"] += 1
            census["exempt"]["archive — a record of the past, append-only"] += 1
            continue
        if is_generated(text):
            census["generated"] += 1
            census["exempt"]["generated — the fix belongs in its generator"] += 1
            continue
        census["judged"] += 1
        masked = mask_code(text)

        #: 2 — THE PAGE'S OWN DECLARED VERSION.
        if text.startswith("---\n"):
            end = text.find("\n---", 4)
            head = text[: end if end > 0 else 400]
            m = re.search(r"^version:\s*'?\"?(0\.1\.\d{1,2})", head, re.M)
            if m and m.group(1) != version:
                add("STALE_FRONTMATTER_VERSION", rel,
                    f"declares `version: {m.group(1)}` and the schema is {version}",
                    f"{rel}:{text[:m.start()].count(chr(10)) + 1}")

        #: 3 — PROSE CALLING A PAST VERSION CURRENT.
        for m in VER.finditer(text):
            if m.group(1) == version:
                continue
            #: PROXIMITY, NOT JUST THE SENTENCE. "The data-plane transform construct (v0.1.8). The
            #: two-plane layout's data plane is NOW fully typed" has a present marker and a stale
            #: version in one sentence and asserts nothing about currency: the `(v0.1.8)` labels when
            #: the construct ARRIVED and `now` describes the data plane. The real defects put the two
            #: words next to each other — "the current `0.1.12` generation" (9 characters apart),
            #: "the next additive number, `0.1.13`" (24). So the claim must be WITHIN REACH of the
            #: version it is about.
            near = masked[max(0, m.start() - VER_CLAIM_WINDOW): m.end() + VER_CLAIM_WINDOW]
            if tense(near, paragraph(masked, m.start())) == "present":
                line = text[:m.start()].count("\n") + 1
                add("STALE_VERSION_CLAIMED_CURRENT", f"{rel}:{line}",
                    f"calls {m.group(0)} current or next; the schema is {version}",
                    f"{rel}:{line}", file=rel)

        #: 4 — A KEY THE SCHEMA NO LONGER CARRIES, STATED AS LIVE.
        for m in TOK.finditer(text):
            tok = m.group(1)
            if tok.endswith(FILE_SUFFIX) or not tok.startswith(KEY_ROOTS):
                continue
            if known(tok, universe):
                continue
            if tense(sentence(masked, m.start()), paragraph(masked, m.start())) == "past":
                census["exempt"]["the page already places the key in the past"] += 1
                continue
            line = text[:m.start()].count("\n") + 1
            add("DEAD_KEY_PRESENTED_AS_LIVE", f"{rel}:{line}",
                f"`{tok}` is in neither the schema nor the vocabulary, and the paragraph does not "
                f"say it is gone", f"{rel}:{line}", file=rel)
    return findings, census


def judge(findings, standing):
    """(news, declared, slack) — a COUNT PER (file, class) that may only go down.

    A RATCHET, NOT A LINE LIST, and the first draft's line-keyed entries are why. `CONFORMANCE.md:662`
    as a standing subject means inserting one paragraph above it turns a quiet, declared, owned entry
    into a red — the gate failing for a line shift rather than for a claim. So the declaration carries
    a count per (file, class): MORE than declared is news; FEWER prints its own slack and asks for the
    floor to come down, because "a floor above the measurement is not a ratchet, it is headroom".
    """
    got = collections.Counter((f["file"], f["reject"]) for f in findings)
    news, declared, slack = [], [], []
    #: ONE NEWS ROW PER (file, class) THAT IS OVER ITS FLOOR, never one per finding. With a floor of 2
    #: and 3 measured, the regression is ONE — and nothing can say WHICH of the three, because they are
    #: indistinguishable. Reporting all three as news would triple a single regression; reporting the
    #: counts says exactly what is true.
    over = {k for k, n in got.items() if n > standing.get(k, {}).get("count", 0)}
    for k in sorted(over):
        fl, cls = k
        floor = standing.get(k, {}).get("count", 0)
        news.append({"reject": cls, "subject": fl, "file": fl, "where": fl,
                     "detail": f"{got[k]} occurrence(s) and the declared floor is {floor}"})
    for f in findings:
        if (f["file"], f["reject"]) not in over:
            declared.append(f)
    for k, e in standing.items():
        floor = e.get("count", 0)
        if got.get(k, 0) < floor:
            slack.append((k, floor, got.get(k, 0)))
    return news, declared, slack


# ── THE ONE PAGE ─────────────────────────────────────────────────────────────────────────────────
def render(findings, census, standing) -> str:
    news, declared, stale = judge(findings, standing)
    by = collections.defaultdict(list)
    for f in findings:
        by[f["reject"]].append(f)
    L = ["<!-- GENERATED by tools/check_semantic_currency.py — do not edit; regenerate. -->",
         "---", "title: Semantic currency — every claim this repository makes that is no longer true",
         "part_of: reference_manual",
         "status: GENERATED by tools/check_semantic_currency.py from the declarations and the runtime",
         "scope: GENERIC — the framework's own documents, judged against its own schema, vocabulary "
         "and runtime", "---", "",
         "# Semantic currency", "",
         "**What this page is.** `check_dangling_references.py` asks whether a pointer RESOLVES. This "
         "asks whether a claim is still TRUE — the defect you cannot see by following links, because "
         "the link works and the sentence is wrong. Every row is read from the declaration or the "
         "code it contradicts; nothing here is typed by a person.", "",
         f"**Measured** against schema `{census['version']}`, {census['keys']} key path and "
         f"vocabulary name(s), and the {census['canons']} canon(s) "
         f"`mac_runtime.canon.IMPLEMENTED` names.", "",
         "| population | pages |", "|---|---|",
         f"| documents in this repository | {census['pages']} |",
         f"| judged | {census['judged']} |",
         f"| exempt — an archive of the past (`protocol/`, `decisions/`) | {census['archive']} |",
         f"| exempt — generated, so the fix belongs in its generator | {census['generated']} |", "",
         "## Why an archive is exempt", "",
         "`protocol/README.md` says it: \"Append-only. Entries are never edited.\" A record that said "
         "`0.1.9` was current was TRUE when it was written, and editing it would falsify the record "
         "rather than correct it. The same holds for a decision record: it states what was decided, "
         "not what is now the case. So an archive is never judged for currency — only a document "
         "describing the PRESENT is.", ""]

    if not findings:
        L += ["## Nothing is stale", "", "No document in this repository makes a claim that "
              "contradicts the schema, the vocabulary or the runtime.", ""]
    for cls in REJECTS:
        rows = by.get(cls, [])
        if not rows:
            continue
        L += [f"## {cls} — {len(rows)}", ""]
        L += {
            "CANON_STATUS_CONTRADICTS_RUNTIME":
                ["A canon page's `status:` says the behaviour is not implemented, and "
                 "`mac_runtime.canon.IMPLEMENTED` honours it. A reader is told a working feature does "
                 "not exist.", ""],
            "STALE_FRONTMATTER_VERSION":
                ["The page declares its own `version:` and that is not the schema's. A reader "
                 "checking which generation the page describes is told the wrong one.", ""],
            "STALE_VERSION_CLAIMED_CURRENT":
                ["Prose calls a past version *current*, or names an already-released version as the "
                 "*next* one. Past tense about a past version is fine and is not listed here.", ""],
            "DEAD_KEY_PRESENTED_AS_LIVE":
                ["A key path in neither the schema nor the vocabulary, in a paragraph that does not "
                 "say it is gone.", ""],
            "STANDING_STALE": ["A declared standing entry that now conforms; remove the entry.", ""],
        }.get(cls, [])
        L += ["| where | what contradicts what | declared |", "|---|---|---|"]
        for f in sorted(rows, key=lambda r: r["subject"]):
            d = "yes" if (f["subject"], f["reject"]) in standing else "**NEW**"
            L.append(f"| `{f['subject']}` | {f['detail'].replace('|', chr(92) + '|')} | {d} |")
        L.append("")
    if stale:
        L += ["## Declared, and no longer found — remove these entries", ""]
        for subj, cls in sorted(stale):
            L.append(f"* `{subj}` — {cls}")
        L.append("")
    L += ["## What holds this page", "",
          "`tools/check_semantic_currency.py`, which writes it and judges it. "
          "`guardrails/semantic_currency.yaml` declares the standing entries, each with an owner and "
          "a reason; only NEWS exits 1. A canon the runtime honours that has no page at all is a "
          "different question and `tools/check_canon_documented.py` owns it — it reports "
          "`ratio_select` today.", ""]
    return "\n".join(L) + "\n"


# ── SELF-TEST ────────────────────────────────────────────────────────────────────────────────────
def self_test() -> int:
    cases = []

    def ok(label, cond, got=None):
        cases.append((label, bool(cond), got))

    U = {"concept.contract.rules", "concept.concept.identity.canonical_key",
         "concept.column.role", "mac.concept.column.role"}
    #: One case per exemption that the FIRST DRAFT got wrong — these are the gate, not footnotes.
    ok("a relative key path is known by suffix (`contract.rules`)", known("contract.rules", U))
    ok("…at any depth (`identity.canonical_key`)", known("identity.canonical_key", U))
    ok("a truly absent key is not known", not known("semantics.unit", U))
    ok("`CURRENT` in backticks is not a currency claim",
       tense(mask_code("every example moves to `CURRENT` together")) != "present",
       tense(mask_code("every example moves to `CURRENT` together")))
    ok("…while the bare word is",
       tense(mask_code("it rides on the current generation")) == "present")
    #: THE MID-SPAN WINDOW BUG, asserted directly: masking the whole text keeps the backtick pairs
    #: right, so a window that begins inside a span still sees the prose around it.
    whole = "a `schema_version`**; it rides on the current `0.1.12` generation. (It mirrors `x` /"
    mw = mask_code(whole)
    i = whole.index("0.1.12")
    ok("a window starting mid-backtick-span still reads the prose",
       tense(mw[max(0, i - VER_CLAIM_WINDOW): i + VER_CLAIM_WINDOW]) == "present",
       repr(mw[max(0, i - VER_CLAIM_WINDOW): i + VER_CLAIM_WINDOW]))
    ok("mask_code preserves length so offsets stay valid", len(mw) == len(whole))
    ok("a typo named as a typo reads as past",
       tense(mask_code("the typo it exists to catch (`mac.connector.athna`) stayed invisible")) == "past")
    ok("a hypothetical reads as past",
       tense(mask_code("any docstring narrating a hypothetical `mac.connector.postgres`")) == "past")
    ok("'new in v0.1.6' reads as past", tense("the constraint gate is new in v0.1.6") == "past")
    ok("'the next additive number' reads as present",
       tense("it would go out under the next additive number") == "present")
    para = "a, b,\nc, d,\ne, f\n— were read by no line of the runtime."
    i = para.index("c, d")
    ok("PAST is judged on the PARAGRAPH, so a list retired on its last line is exempt",
       tense(sentence(para, i), paragraph(para, i)) == "past",
       tense(sentence(para, i), paragraph(para, i)))
    mixed = ("The bump happened in v0.1.9 and was additive.\n"
             "It does not move the schema_version; it rides on the current 0.1.12 generation.")
    j = mixed.index("0.1.12")
    ok("…but PRESENT is judged on the SENTENCE, so a live claim beside a history note is still news",
       tense(sentence(mixed, j), paragraph(mixed, j)) == "present",
       tense(sentence(mixed, j), paragraph(mixed, j)))
    ok("a wiki stamp longer than 600 chars is still detected as generated",
       is_generated("<!-- mac-wiki-stamp " + "x" * 2000 + " -->\n"
                    "<!-- GENERATED by mac_wiki.py/1 — do not edit; recompile. -->\n"))
    ok("a currency word NEAR the version is a claim",
       tense("it rides on the current 0.1.12 generation"[:80], "") == "present")
    ok("…and one 50 characters away is not",
       tense("construct (v0.1.8). The data plane is now fully typed"[0:40], "") != "present",
       tense("construct (v0.1.8). The data plane is now fully typed"[0:40], ""))
    ok("every reject class is declared", set(REJECTS) >= {
        "CANON_STATUS_CONTRADICTS_RUNTIME", "STALE_FRONTMATTER_VERSION",
        "STALE_VERSION_CLAIMED_CURRENT", "DEAD_KEY_PRESENTED_AS_LIVE", "STANDING_STALE"})
    #: STANDING_STALE in both directions — a declared entry that is found stays quiet; one that is
    #: not found is news, which is what stops the list rotting into an excuse.
    def F(fl, cls="STALE_VERSION_CLAIMED_CURRENT"):
        return {"subject": f"{fl}:1", "reject": cls, "detail": "", "where": "", "file": fl}
    st = {("a.md", "STALE_VERSION_CLAIMED_CURRENT"): {"owner": "x", "count": 2}}
    n, d, sl = judge([F("a.md"), F("a.md")], st)
    ok("at the floor: declared, not news, no slack", not n and len(d) == 2 and not sl)
    n, d, sl = judge([F("a.md"), F("a.md"), F("a.md")], st)
    ok("above the floor: ONE news row for the file, not one per finding",
       len(n) == 1 and "3 occurrence(s)" in n[0]["detail"] and not d, (len(n), len(d)))
    n, d, sl = judge([F("a.md")], st)
    ok("below the floor: not news, and the SLACK is printed",
       not n and sl == [(("a.md", "STALE_VERSION_CLAIMED_CURRENT"), 2, 1)], sl)
    n, _d, _sl = judge([F("b.md")], st)
    ok("an undeclared file is news", len(n) == 1)

    good = sum(1 for _l, c, _g in cases if c)
    for label, c, got in cases:
        print(f"  {'ok  ' if c else 'FAIL'}  {label}")
        if not c:
            print(f"          got: {got}")
    print(f"\n{'PASS' if good == len(cases) else 'FAIL'}: check_semantic_currency self-test — "
          f"{good} of {len(cases)} case(s) over {len(REJECTS)} reject class(es)")
    return 0 if good == len(cases) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bundle", nargs="?", help="accepted and ignored: the runner's convention")
    ap.add_argument("--page", action="store_true", help=f"write {PAGE.relative_to(ROOT)}")
    ap.add_argument("--check-page", action="store_true", help="the page is what this renders")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    try:
        findings, census = run()
        standing = load_standing()
    except CouldNotRun as exc:
        print(f"could not run: check_semantic_currency — {exc}")
        return 2

    news, declared, slack = judge(findings, standing)
    for f in sorted(news, key=lambda r: (r["reject"], r["subject"])):
        print(f"  ✗ {f['subject']}  [{f['reject']}]\n      {f['detail']}")
    for f in sorted(declared, key=lambda r: (r["reject"], r["subject"])):
        e = standing[(f["file"], f["reject"])]
        print(f"  ~ {f['subject']}  [{f['reject']}]  DECLARED standing, owner "
              f"{e.get('owner', '?')}, since {e.get('since', '?')}")
    for (fl, cls), floor, now in sorted(slack):
        print(f"  ! {fl}  [{cls}]  SLACK: the floor declares {floor} and {now} remain — lower it to "
              f"{now} in guardrails/semantic_currency.yaml")

    if a.page:
        PAGE.parent.mkdir(parents=True, exist_ok=True)
        PAGE.write_text(render(findings, census, standing), encoding="utf-8")
        print(f"  wrote {PAGE.relative_to(ROOT)}")
    if a.check_page:
        want = render(findings, census, standing)
        if not PAGE.is_file() or PAGE.read_text(encoding="utf-8") != want:
            news = news + [{"reject": "STALE_PAGE", "subject": str(PAGE.relative_to(ROOT)),
                            "detail": "not what this tool renders; run --page", "where": ""}]
            print(f"  ✗ {PAGE.relative_to(ROOT)}  [STALE_PAGE]\n      run "
                  f"`python3 tools/check_semantic_currency.py --page`")

    bad = len(news)
    print(f"\n{'FAIL' if bad else 'PASS'}: check_semantic_currency — {bad} new finding(s), "
          f"{len(declared)} declared standing, {len(slack)} with slack, over {census['judged']} judged page(s) of "
          f"{census['pages']} ({census['archive']} archive, {census['generated']} generated) against "
          f"schema {census['version']}, {census['keys']} key/term name(s) and {census['canons']} "
          f"honoured canon(s), {len(REJECTS)} reject class(es)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
