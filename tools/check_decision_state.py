#!/usr/bin/env python3
"""check_decision_state.py — a decision record declares its STATE as data, and the body agrees.

WHY THIS GATE EXISTS, measured 2026-10-04 over `decisions/`. Seventeen records, and the only thing
that told a reader whether one was still true was the FILENAME PREFIX. Measured, the prefix was
wrong about seven of them:

  * Of the nine files whose name says `PROPOSED-`, FOUR were implemented — `guard-scope` (all three
    predicates installed in the hook), `guardrails` (eight topic files plus `check_guardrails.py`),
    `ontology-idiom` (five proposals landed in `guardrails/ontology/concepts.yaml`) and
    `register-policy` (`check_one_register_per_dimension.py` counts by value set and prints the
    record by name). One more, `column-first-declarations`, shipped the same day it was written.
    One, `delivery-manifest`, was superseded. One, `public-brand-examples`, was DONE and said so in
    its own H1 — `# RECORDED 2026-10-02` — while its filename said PROPOSED, so one file carried
    both answers. Exactly ONE, `one-revenue-concept`, was genuinely awaiting a ruling.
  * `REQ-2026-09-13_console-connection-page.md` said `Status: PROPOSED` with all six of its
    requirements built in the console.
  * `PROPOSED-2026-09-29_ontology-idiom.md` asserted "No gate checks anything this record asks for"
    on the day its asks landed in a guardrail a gate reads.

AND THE PREFIX SLOT CRUSHED TWO ORTHOGONAL AXES INTO ONE. `PROPOSED`/`RULED` are LIFECYCLE;
`PROTOCOL`/`DNA`/`DELIVERABLES`/`REQ` are GENRE and declare no state at all, so five of seventeen
records told a reader nothing about whether they were still true. Seven state spellings were in use
— `ACCEPTED`, `the contract`, `PROPOSED`, `SUPERSEDED`, `PROPOSED — designed, not enforced`,
`RECORDED`, `RULED BY THE OPERATOR` — and `check_dangling_references.RETIRED_STATUS_RE`, the one
mechanical reader of any of them, matched exactly ONE file in the directory.

SO STATE BECAME DATA, AND THE FILENAME DID NOT MOVE. The two axes are two keys, from two closed
vocabularies, in front matter — the form this repository already uses for `FRAMEWORK.md`,
`CONFORMANCE.md` and `reference_manual/*.md`.

THE FILENAME CARRIES IDENTITY; THE BODY CARRIES STATE. Renaming a record on ratification is not an
option and that is not a style preference — live readers cite these files BY NAME, and every one of
them would break silently:

    tools/check_one_register_per_dimension.py:186   PRINTS decisions/PROPOSED-2026-09-29_register-policy.md
                                                    to its operator inside a FAIL verdict
    sdk/connector/__init__.py, sdk/connector/base.py            carry one as `RECORD:`
    sdk/gate/engine_noun_floor.txt, engine_coupling_floor.txt   carry the same one as `RECORD:`
    tools/framework_gate_failures.yaml:29                       names PROTOCOL-2026-09-29_guardrails.md
    tools/check_guard_scope.py:6,342                            names the record it holds under test
    guardrails/data/sources.yaml:150                            names register-policy step (c)
    mac-platform  console_api.py, ConnectionView.jsx, test_connection_page_connector.py,
                  and four mac_runtime modules citing column-first-declarations

THE KEYS
  state:            REQUIRED, closed. The LIFECYCLE axis — proposed · ruled · implemented ·
                    superseded · recorded. `recorded` is for a document that was never a proposal
                    (a protocol, the DNA checklist, a deliverables contract): the question "is it
                    still awaiting a ruling?" does not apply to it, and saying `proposed` would be
                    a lie in the other direction.
  genre:            REQUIRED, closed. The GENRE axis, which is what the old prefixes actually were
                    once the lifecycle words are taken out of them — adr · proposal · requirement ·
                    ruling · protocol · dna · deliverables.
  ruled:            the date a ruling was taken. SEPARATE from `state:` on purpose: a record that
                    was ruled AND built is `state: implemented`, and the ratification is not lost.
  supersedes:       the record this one replaces.
  superseded_by:    the record that replaced this one.
  implemented_by:   the artifacts that exist BECAUSE this record was acted on — the evidence for
                    any state past `proposed`. A repo-relative path MUST exist. A cross-repo entry
                    is written `<repo>#<path>` — the `#` is REQUIRED and is the whole test — and is
                    UNLOCATED: counted and printed, never failed, the same honest treatment
                    `check_dangling_references` gives a cross-repo target. A bare path that names
                    another repository is reported as dangling, not silently excused.
  cited_by:         machine readers that name this file — code, floors, registers, not prose. This
                    is the rename hazard, written down where the next author will see it.
  enforcement:      optional, closed — `designed, not enforced` or `enforced`. A third axis, and
                    not a synonym for either of the first two: `ontology-idiom` is IMPLEMENTED (its
                    five asks are declared) and NOT ENFORCED (nothing refuses on them).

THE REJECT CLASSES — each proven by a mutant in `--self-test`
  state-not-in-vocabulary     a `state:` token outside the closed set, or a record with no `state:`
                              at all (no front matter is this class, not a separate one)
  genre-not-in-vocabulary     same, for `genre:`. Here because the brief that ordered this gate
                              required `genre:` to come from a closed vocabulary, and a vocabulary
                              nothing checks is not closed.
  proposed-but-implemented    `state: proposed` while EVERY repo-relative path in `implemented_by:`
                              exists. THIS IS THE CLASS THE DIRECTORY FAILED: it catches four of
                              the six records mislabelled on 2026-10-04 — guard-scope, guardrails,
                              ontology-idiom, register-policy. It needs at least one repo-relative
                              path to fire: a record whose evidence is entirely cross-repo cannot
                              be judged from here and is reported as unjudged rather than guessed.
  body-contradicts-front-matter
                              a STATE CLAIM in the body disagrees with `state:`. Only two positions
                              count as a claim — the H1's leading word, and the value of a
                              `Status:` line — plus the literal phrase "acted on instead". Prose is
                              NOT scanned: `one-revenue-concept` says "an agent may only write
                              `PROPOSED`" as a sentence about CORE §3, which is a true sentence and
                              not a status claim, and a gate that read it as one would be the
                              false-positive that gets gates switched off. This class catches
                              `public-brand-examples`, whose H1 and filename disagreed inside one
                              file.
  dangling-implemented-by     a repo-relative path in `implemented_by:` that does not exist
  dangling-record-reference   `supersedes:`/`superseded_by:` naming a record that is not in
                              decisions/. The pointer between delivery-manifest and guardrails is
                              the only machine link between the two; an unchecked pointer is the
                              defect this whole change exists to end.

THE SUBJECT IS THIS REPOSITORY, NOT A BUNDLE, so this gate REFUSES a positional path argument
rather than mis-reading one. The precedent and the reason are `tools/check_structure_reference.py`: a
gate that mis-read that argument once judged 7 commits against a floor measured over 38 and printed
PASS. It is declared in the runner's REPO_SUBJECT_GATES for the same reason.

decisions/README.md is the directory's INDEX, not a record. It is excluded BY NAME and the
exclusion is printed with the denominator, because a denominator that silently drops a file is the
defect `check_mac_public` reporting PASS on zero files is named after.

    python3 tools/check_decision_state.py              # the verdict over decisions/
    python3 tools/check_decision_state.py --self-test  # one mutant per reject class, plus a clean fixture

Contract: one PASS:/FAIL: line printed LAST, exit 0 or 1, exit 2 when it could not run, the
denominator printed, and `--self-test` with one mutant per reject class.
"""
from __future__ import annotations

import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDS_DIR = ROOT / "decisions"

# decisions/README.md is the directory's index, not a record. Named, never pattern-guessed.
NOT_A_RECORD = frozenset({"README.md"})

STATES = ("proposed", "ruled", "implemented", "superseded", "recorded")
GENRES = ("adr", "proposal", "requirement", "ruling", "protocol", "dna", "deliverables")
ENFORCEMENTS = ("designed, not enforced", "enforced")

# A cross-repo entry is `<repo>#<path>`. These prefixes are also honoured bare, because a path that
# starts with another repository's name is a claim about that repository however it is punctuated.
# A CROSS-REPO ENTRY IS `<repo>#<path>`, AND THAT IS THE WHOLE TEST — there is no list of sibling
# repository names here. The first draft of this file carried one, and two things were wrong with it:
# it was a second home for a fact `check_dangling_references.CROSS_REPO` already owns, and the
# hand-typed copy pulled in a programme prefix from the private token register, which
# `check_mac_public` caught at its floor of 0. Requiring the `#` makes the convention ENFORCED
# instead of guessed: a bare `mac-platform/...` is reported as dangling, which is the right feedback
# ("write it in the cross-repo form"), and no name of any repository is written down here at all.

# A body STATE WORD and the `state:` values it is consistent with. ACCEPTED and RULED both mean "a
# ruling was taken", which is true of a record that has since been built, so both admit
# `implemented`. RECORDED admits it for the same reason: `public-brand-examples` was asked for as a
# proposal and acted on instead, so RECORDED and implemented are one event seen twice.
BODY_WORDS = {
    "PROPOSED": frozenset({"proposed"}),
    "ACCEPTED": frozenset({"ruled", "implemented"}),
    "RULED": frozenset({"ruled", "implemented"}),
    "IMPLEMENTED": frozenset({"implemented"}),
    "RECORDED": frozenset({"recorded", "implemented"}),
    "SUPERSEDED": frozenset({"superseded"}),
    "RETIRED": frozenset({"superseded"}),
}
ACTED_ON_INSTEAD = frozenset({"recorded", "implemented"})

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
# `**Status: X**`, `**Status:** X`, `STATUS: X` — the value runs to the end of the line or the first
# full stop, whichever comes first. Only this span is read as a claim.
STATUS_RE = re.compile(r"^\**\s*status:\s*\**\s*([^.\n]*)", re.I | re.M)
WORD_RE = re.compile(r"[A-Z]{4,}")

# A FILENAME IS NOT A STATE CLAIM, and this is the one place the distinction could have been lost.
# `delivery-manifest` reads "**Status: SUPERSEDED 2026-09-29 by `PROPOSED-2026-09-29_guardrails.md`.**"
# — two state words in one status line, one of them the OLD PREFIX of a file it points at. Reading
# that as a claim made the gate reject the one record whose state was never in doubt, which is the
# filename-is-identity confusion this whole change exists to end, reappearing inside its own gate.
# So a backticked span is removed before the line is read, and a word glued to a date
# (`PROPOSED-2026-09-29`) is removed whether it was backticked or not.
TICKED_RE = re.compile(r"`[^`\n]*`")
PREFIXED_NAME_RE = re.compile(r"[A-Z]{4,}-\d{4}-\d{2}-\d{2}\S*")


class Reject:
    __slots__ = ("record", "cls", "detail")

    def __init__(self, record: str, cls: str, detail: str):
        self.record, self.cls, self.detail = record, cls, detail


def split_front_matter(text: str) -> tuple[str | None, str]:
    """(front matter block, body). A file that does not open with `---` has no front matter."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 3)
    if end == -1:
        return None, text
    return text[4:end + 1], text[end + 5:]


def parse_front_matter(block: str) -> dict:
    """The six keys this gate reads, from a flat block with `- ` lists. No parser is imported.

    PyYAML WOULD DO THIS AND IS DELIBERATELY NOT USED. This gate's whole job is to be the thing that
    still runs when something else is broken, and `check_guardrails` records what an unparseable
    declaration costs: `mac_artifacts.yaml` was committed unparseable and four commits later every
    run of the gate was a traceback rather than a verdict. The front matter here is six scalars and
    three lists; a reader for exactly that cannot raise.
    """
    out: dict = {}
    key = None
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if key is not None:
                out.setdefault(key, []).append(line.split("- ", 1)[1].strip())
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        key = k.strip().lower()
        v = v.strip()
        out[key] = v if v else []
    return out


def body_claims(body: str) -> list[tuple[str, frozenset]]:
    """Every STATE CLAIM in the body, as (the word as written, the states it admits).

    TWO POSITIONS ONLY, and the narrowness is the point. The H1's leading word is a claim because
    this directory's convention put the state there. A `Status:` line's value is a claim because it
    says so. Everything else is prose, and prose that happens to contain a state word in capitals is
    not a declaration — scanning it would reject `one-revenue-concept` for the true sentence "an
    agent may only write `PROPOSED`".
    """
    claims = []
    for m in H1_RE.finditer(body):
        first = m.group(1).split()[0].strip("*_`#") if m.group(1).split() else ""
        if first.upper() in BODY_WORDS:
            claims.append((first.upper(), BODY_WORDS[first.upper()]))
    for m in STATUS_RE.finditer(body):
        span = PREFIXED_NAME_RE.sub(" ", TICKED_RE.sub(" ", m.group(1)))
        for w in WORD_RE.findall(span):
            if w in BODY_WORDS:
                claims.append((w, BODY_WORDS[w]))
    if "acted on instead" in body.lower():
        claims.append(("acted on instead", ACTED_ON_INSTEAD))
    return claims


def is_cross_repo(p: str) -> bool:
    """`<repo>#<path>` and nothing else. See the note at CROSS-REPO above for why there is no list."""
    return "#" in p


def audit(records_dir: pathlib.Path, repo_root: pathlib.Path) -> tuple:
    """(rejects, examined, existing, excluded, verified, unlocated, unjudged)."""
    if not records_dir.is_dir():
        return None, 0, 0, [], 0, 0, []
    everything = sorted(p for p in records_dir.glob("*.md") if p.is_file())
    excluded = [p.name for p in everything if p.name in NOT_A_RECORD]
    records = [p for p in everything if p.name not in NOT_A_RECORD]

    rejects: list[Reject] = []
    verified = unlocated = 0
    unjudged: list[str] = []

    for p in records:
        name = p.name
        fm_block, body = split_front_matter(p.read_text(encoding="utf-8", errors="replace"))
        fm = parse_front_matter(fm_block) if fm_block is not None else {}

        state = fm.get("state")
        state = state.strip().lower() if isinstance(state, str) and state.strip() else None
        if state is None:
            rejects.append(Reject(name, "state-not-in-vocabulary",
                                  "no `state:` in front matter" if fm_block is None
                                  else "`state:` is absent or empty"))
        elif state not in STATES:
            rejects.append(Reject(name, "state-not-in-vocabulary",
                                  f"state: {state!r} is outside the closed set {list(STATES)}"))
            state = None

        genre = fm.get("genre")
        genre = genre.strip().lower() if isinstance(genre, str) and genre.strip() else None
        if genre is None:
            rejects.append(Reject(name, "genre-not-in-vocabulary", "`genre:` is absent or empty"))
        elif genre not in GENRES:
            rejects.append(Reject(name, "genre-not-in-vocabulary",
                                  f"genre: {genre!r} is outside the closed set {list(GENRES)}"))

        enf = fm.get("enforcement")
        if isinstance(enf, str) and enf.strip() and enf.strip().lower() not in ENFORCEMENTS:
            rejects.append(Reject(name, "genre-not-in-vocabulary",
                                  f"enforcement: {enf.strip()!r} is outside {list(ENFORCEMENTS)}"))

        impl = fm.get("implemented_by") or []
        impl = [impl] if isinstance(impl, str) and impl.strip() else list(impl)
        local = [q for q in impl if not is_cross_repo(q)]
        unlocated += len(impl) - len(local)
        missing = [q for q in local if not (repo_root / q).exists()]
        verified += len(local) - len(missing)
        for q in missing:
            rejects.append(Reject(name, "dangling-implemented-by",
                                  f"implemented_by names {q!r}, which does not exist"))

        if state == "proposed" and impl:
            if not local:
                unjudged.append(f"{name} — {len(impl)} implemented_by entr(y/ies), all cross-repo")
            elif not missing:
                rejects.append(Reject(
                    name, "proposed-but-implemented",
                    f"state: proposed, yet all {len(local)} repo-relative implemented_by path(s) "
                    f"exist: {', '.join(local)}"))

        for k in ("supersedes", "superseded_by"):
            v = fm.get(k)
            for target in ([v] if isinstance(v, str) and v.strip() else list(v or [])):
                if not (records_dir / target).is_file():
                    rejects.append(Reject(name, "dangling-record-reference",
                                          f"{k} names {target!r}, which is not in decisions/"))

        if state is not None:
            # DEDUPED BY THE WORD, because one disagreement is one defect however many times the
            # record repeats it. `column-first-declarations` says IMPLEMENTED in its H1 AND on its
            # Status: line, which is one fact in two true places, and reporting it twice would
            # inflate a count the verdict line publishes.
            for word in sorted({w for w, admits in body_claims(body) if state not in admits}):
                admits = BODY_WORDS.get(word, ACTED_ON_INSTEAD)
                rejects.append(Reject(
                    name, "body-contradicts-front-matter",
                    f"the body claims {word!r} (admits {sorted(admits)}) "
                    f"while state: is {state!r}"))

    return rejects, len(records), len(everything), excluded, verified, unlocated, unjudged


def report(records_dir: pathlib.Path, repo_root: pathlib.Path) -> int:
    res = audit(records_dir, repo_root)
    if res[0] is None:
        print(f"could not run: no records directory at {records_dir}", file=sys.stderr)
        return 2
    rejects, examined, existing, excluded, verified, unlocated, unjudged = res
    if examined == 0:
        print(f"could not run: {records_dir} holds no records "
              f"({existing} file(s), {len(excluded)} excluded by name)", file=sys.stderr)
        return 2

    if rejects:
        by_cls: dict[str, list[Reject]] = {}
        for r in rejects:
            by_cls.setdefault(r.cls, []).append(r)
        for cls in sorted(by_cls):
            print(f"\n{cls} — {len(by_cls[cls])}")
            for r in by_cls[cls]:
                print(f"  decisions/{r.record}")
                print(f"      {r.detail}")

    if unjudged:
        print(f"\nUNJUDGED — {len(unjudged)}: state: proposed with evidence this gate cannot see.")
        print("  Reported, never counted as clean: a cross-repo path is a claim about another")
        print("  repository, and guessing it exists is how a gate gets to look green for free.")
        for u in unjudged:
            print(f"  {u}")

    excl = (f"; {len(excluded)} excluded by name ({', '.join('decisions/' + e for e in excluded)}): "
            f"the directory's index, not a record" if excluded else "")
    tail = (f"; {verified} repo-relative implemented_by path(s) verified, "
            f"{unlocated} unlocated (cross-repo), {len(unjudged)} record(s) unjudged")
    print()
    if rejects:
        print(f"FAIL: check_decision_state — {len(rejects)} reject(s) in "
              f"{len({r.record for r in rejects})} record(s), over {examined} record(s) examined "
              f"of {existing} file(s) in decisions/{excl}{tail}")
        return 1
    print(f"PASS: check_decision_state — 0 reject(s) over {examined} record(s) examined "
          f"of {existing} file(s) in decisions/{excl}{tail}")
    return 0


# ══════════════════════════════════════════════════════════════════════════════════════════════
# THE SELF-TEST — one mutant per reject class, and a clean fixture that must PASS.
# ══════════════════════════════════════════════════════════════════════════════════════════════

# THE CLEAN FIXTURE IS CUT FROM THE REAL DIRECTORY, not invented: a superseded record and the one
# that replaced it, a `recorded` genre document, and an implemented proposal whose evidence is
# partly cross-repo. If a clean fixture cannot hold these four shapes, the vocabulary is wrong.
CLEAN = {
    "PROPOSED-2026-09-29_delivery-manifest.md": (
        "---\nstate: superseded\ngenre: proposal\n"
        "superseded_by: PROPOSED-2026-09-29_guardrails.md\n---\n"
        "**SUPERSEDED 2026-09-29 by `PROPOSED-2026-09-29_guardrails.md`.**\n\n"
        "# DELIVERY MANIFEST — ONE DECLARATION PER DELIVERED ITEM\n\n"
        # THE REAL LINE, VERBATIM, because it carries TWO state words and the second one is the old
        # prefix of a FILENAME. An earlier version of this gate rejected this record for it.
        "**Status: SUPERSEDED 2026-09-29 by `PROPOSED-2026-09-29_guardrails.md`.** Its four rulings "
        "stand and were carried forward verbatim.\n"),
    "PROPOSED-2026-09-29_guardrails.md": (
        "---\nstate: implemented\ngenre: proposal\nruled: 2026-09-29\n"
        "supersedes: PROPOSED-2026-09-29_delivery-manifest.md\n"
        "implemented_by:\n  - real_a.py\n  - mac-platform#packages/x/y.py\n---\n"
        "# GUARDRAILS — ONE SMALL FILE PER TOPIC\n\n"
        "**Status: IMPLEMENTED 2026-09-29** — acted on the same day.\n"),
    "PROTOCOL-2026-10-01_rule-engine.md": (
        "---\nstate: recorded\ngenre: protocol\n---\n"
        "# PROTOCOL — 2026-10-01 · the rule engine\n\nEverything below is measured.\n"),
    "PROPOSED-2026-10-02_one-revenue-concept.md": (
        "---\nstate: proposed\ngenre: proposal\n---\n"
        "# PROPOSED — 2026-10-02 · ONE Revenue concept\n\n"
        "**Status: PROPOSED.** Per CORE §3 an agent may only write `PROPOSED`; adding a concept is\n"
        "the operator's act. Nothing here has been applied.\n"),
    "README.md": "# decisions/ — the record\n\nAn index, not a record. Must not be examined.\n",
}

# One mutant per reject class. Each is the SMALLEST edit to CLEAN that should turn it red, and the
# `proposed-but-implemented` and `body-contradicts-front-matter` mutants are the two defects the
# real directory actually carried on 2026-10-04 — guard-scope/guardrails/ontology-idiom/
# register-policy declaring PROPOSED over artifacts that exist, and public-brand-examples' H1
# saying RECORDED while its filename said PROPOSED.
MUTANTS = {
    "state-not-in-vocabulary": (
        "RULED-2026-01-01_no-state.md",
        "---\ngenre: ruling\n---\n# RULED — 2026-01-01 · a record with no state at all\n"),
    "genre-not-in-vocabulary": (
        "RULED-2026-01-02_bad-genre.md",
        "---\nstate: ruled\ngenre: memo\n---\n# RULED — 2026-01-02 · a genre nobody closed\n"),
    "proposed-but-implemented": (
        "PROPOSED-2026-09-29_guard-scope.md",
        "---\nstate: proposed\ngenre: proposal\nimplemented_by:\n  - real_a.py\n  - real_b.py\n---\n"
        "# PROPOSED 2026-09-29 — what the ontology guard should ask\n\n"
        "The real directory declared exactly this over artifacts that already existed.\n"),
    "body-contradicts-front-matter": (
        "PROPOSED-2026-10-02_public-brand-examples.md",
        "---\nstate: proposed\ngenre: proposal\n---\n"
        "# RECORDED 2026-10-02 — the `label_of` worked example uses fictional marques\n\n"
        "Asked for as a proposal; **acted on instead**, on the coordinator's ruling.\n"),
    "dangling-implemented-by": (
        "RULED-2026-01-03_dangling.md",
        "---\nstate: implemented\ngenre: ruling\nimplemented_by:\n  - tools/never_written.py\n---\n"
        "# RULED — 2026-01-03 · evidence that is not there\n"),
    "dangling-record-reference": (
        "RULED-2026-01-04_bad-pointer.md",
        "---\nstate: superseded\ngenre: ruling\nsuperseded_by: PROPOSED-2026-01-01_ghost.md\n---\n"
        "# SUPERSEDED — 2026-01-04 · a pointer to nothing\n"),
}


def _seed(repo: pathlib.Path, extra: tuple | None = None) -> pathlib.Path:
    d = repo / "decisions"
    d.mkdir(parents=True, exist_ok=True)
    for n, body in CLEAN.items():
        (d / n).write_text(body, encoding="utf-8")
    (repo / "real_a.py").write_text("# an artifact that exists\n", encoding="utf-8")
    (repo / "real_b.py").write_text("# an artifact that exists\n", encoding="utf-8")
    if extra:
        (d / extra[0]).write_text(extra[1], encoding="utf-8")
    return d


def _quiet_report(records_dir: pathlib.Path, repo_root: pathlib.Path) -> int:
    """`report` with its output swallowed — the self-test asserts the EXIT CODE, not the prose.

    WHY IT IS SWALLOWED. The contract is ONE `PASS:`/`FAIL:` line, printed LAST. A self-test that
    let eight fixture verdicts through would print nine, and the runner reads the last line of a
    gate's output to decide what happened: a stray verdict is how a gate comes to report somebody
    else's fixture as its own finding.
    """
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        return report(records_dir, repo_root)


def _self_test() -> int:
    results = []

    def case(label: str, ok: bool, note: str = ""):
        results.append((label, ok, note))

    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td) / "clean"
        d = _seed(repo)
        rejects, examined, existing, excluded, verified, unlocated, unjudged = audit(repo / "decisions", repo)
        case("the CLEAN fixture passes", not rejects,
             "; ".join(f"{r.cls}/{r.record}" for r in rejects))
        case("README.md is excluded from the numerator, by name",
             examined == 4 and existing == 5 and excluded == ["README.md"],
             f"examined={examined} existing={existing} excluded={excluded}")
        case("a cross-repo implemented_by entry is UNLOCATED, never failed",
             verified == 1 and unlocated == 1, f"verified={verified} unlocated={unlocated}")
        case("a true sentence about CORE §3 is not read as a status claim",
             not any(r.cls == "body-contradicts-front-matter" for r in rejects))
        case("an OLD PREFIX inside a cited filename is not read as a status claim",
             not any(r.record == "PROPOSED-2026-09-29_delivery-manifest.md" for r in rejects),
             "the real 'SUPERSEDED ... by `PROPOSED-...md`' line must not reject")
        case("the clean run exits 0", _quiet_report(d, repo) == 0)

    for cls, extra in sorted(MUTANTS.items()):
        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td) / "mutant"
            d = _seed(repo, extra)
            rejects, *_ = audit(d, repo)
            got = sorted({r.cls for r in rejects})
            case(f"MUTANT {cls} is rejected", cls in got, f"got {got}")
            case(f"MUTANT {cls} rejects ONLY its own class", got == [cls], f"got {got}")
            case(f"MUTANT {cls} exits 1", _quiet_report(d, repo) == 1)

    # A records directory that is empty, or absent, must REFUSE — never PASS on zero files.
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        (repo / "decisions").mkdir()
        case("an EMPTY decisions/ could-not-run (exit 2), never PASS",
             _quiet_report(repo / "decisions", repo) == 2)
        case("an ABSENT decisions/ could-not-run (exit 2)",
             _quiet_report(repo / "nowhere", repo) == 2)

    bad = [(lab, note) for lab, ok, note in results if not ok]
    print()
    for lab, ok, note in results:
        print(f"  {'ok  ' if ok else 'FAIL'}  {lab}{(' — ' + note) if note and not ok else ''}")
    n = len(results)
    print()
    if bad:
        print(f"FAIL: check_decision_state self-test — {len(bad)} of {n} case(s) failed over "
              f"{len(MUTANTS)} mutant(s), one per reject class, plus the clean fixture")
        return 1
    print(f"PASS: check_decision_state self-test — {n}/{n} case(s) over {len(MUTANTS)} mutant(s), "
          f"one per reject class ({', '.join(sorted(MUTANTS))}), plus the clean fixture")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv:
        return _self_test()

    # THE BUNDLE ROOT IS NOT ARGV[1] HERE. This gate's subject is THIS repository's decisions/; a
    # bundle has none. It is declared in the runner's REPO_SUBJECT_GATES for that reason, and
    # refusing a positional argument is what keeps a calling-convention miss from reading as a
    # finding — the defect that once had a gate judge 7 commits against a floor measured over 38
    # and print PASS. See tools/check_structure_reference.py, which sets this precedent.
    positional = [a for a in argv if not a.startswith("-")]
    if positional:
        print(f"could not run: this gate takes no path argument (got {positional[0]!r}); "
              f"its subject is this repository's decisions/", file=sys.stderr)
        return 2

    records_dir = RECORDS_DIR
    for a in argv:
        if a.startswith("--records-dir="):
            records_dir = pathlib.Path(a.split("=", 1)[1]).expanduser().resolve()
        elif a not in ("--self-test",):
            print(f"could not run: unknown option {a!r}", file=sys.stderr)
            return 2
    return report(records_dir, ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
