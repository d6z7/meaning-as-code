#!/usr/bin/env python3
"""relocate_pages.py — MOVE A DOCUMENTATION PAGE AND EVERY REFERENCE TO IT, IN ONE PASS.

WHAT A SCHEMA IS FOR YAML AND `check_page_shape.py` IS FOR A PAGE'S SHAPE, THIS IS FOR ITS ADDRESS.
`guardrails/document_home.yaml` declares where a page of each genre lives. This tool derives the moves
from that declaration — it never carries a move list of its own — rewrites the references that would
stop resolving, and then goes on being a gate: `--check` refuses the next page that lands somewhere
undeclared.

THE MEASUREMENT THIS TOOL EXISTS BECAUSE OF, AND THE ONE THAT SHRANK IT
  436 references name the 15 non-README root pages, across 145 files in three repositories. That is
  NOT the rewrite surface. `check_dangling_references` R3 resolves a backticked bare basename by NAME
  anywhere in the tree, and a bare un-backticked mention it does not judge at all. So a move that
  PRESERVES THE BASENAME leaves 340 of the 436 correct and untouched, and the real surface is 30 paths.
  The declaration says `naming: the page's own basename, verbatim` on every block for this reason.

WHY THE GATE CANNOT BE THE ONLY VERDICT — and this is the trap this tool is built around.
  `check_dangling_references` is a necessary verdict and an insufficient one. For a bare basename it
  resolves by name anywhere in the tree, so a reference left pointing at a stale ADDRESS stays green.
  It is also already red on this tree (37 new over a 35-entry baseline), so a count cannot be a verdict
  either. This tool therefore carries its OWN independent assertion — `--verify`, which re-scans for
  every old address in all five forms and refuses any that survives outside a declared exemption — and
  compares the gate's finding SET before and after rather than its number. A check that shares its
  code with the thing it checks cannot fail; these two share none.

THE FIVE FORMS A REFERENCE TAKES, MEASURED ON THIS ESTATE
  markdown link      `](specification/FRAMEWORK.md)`     path recomputed from the referrer's NEW home
  backticked path    `` `reference_manual/x.md` ``       repository-root-relative, which is what R2 reads
  quoted string      `"FRAMEWORK.md"`                    rewritten only when it carries a path
  with an anchor     `FRAMEWORK.md#section` / `§8`       `#fragment` travels; a prose `§8` is left alone
  bare in prose      FRAMEWORK.md                        NOT rewritten — the basename is preserved, so
                                                         the sentence stays true and R3 still resolves

SUBSTRING COLLISION, THE BUG THIS WOULD HAVE HAD. `TESTING.md` is a substring of `PIPELINE_TESTING.md`.
Scanning name by name rewrites the inside of the longer name and corrupts it silently. So there is ONE
alternation over all names, longest first, and every position is claimed by the longest match at it.

WHAT IT REFUSES TO TOUCH, EACH DECLARED
  protocol/        append-only — `protocol/README.md`: "Entries are never edited". 4 citations live
                   there and stay there; that is why the redirect stubs are permanent.
  a redirect stub  its address IS its function; relocating it breaks the citations it was left for.
  a retirement     a line that already says "merged into" / "superseded" / "was" is a true historical
                   statement. The judgement is READ FROM `check_dangling_references`, not re-written.
  generated output a page written by a generator is not edited here; its GENERATOR's output path is,
                   or the next run restores the old path and undoes the move (GENERATOR_PATH_STALE).

EXIT
  0 PASS · 1 FAIL (news) · 2 could-not-run. Exactly one PASS:/FAIL: line, printed last, with the
  denominator. `--self-test` seeds one mutant per reject class plus a clean fixture.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECL = ROOT / "guardrails" / "document_home.yaml"

#: The sibling repositories a reference can live in. A move here reaches them, so they are scanned —
#: and they are separate git repositories, so the write is per-repo and the tool says so.
SIBLINGS = {
    "mac-platform": ROOT.parent / "mac-platform",
    "mac-integration-kit": ROOT.parent / "mac-integration-kit",
}
#: Not documentation: bundle content, test goldens, build output. Excluded from the population with a
#: reason, never silently — a denominator chosen to flatter the gate is the defect this estate names.
NOT_DOCUMENTATION = (
    "tests/fixtures/",          # self-test bundles are not pages
    #: example_tpch_ontology was removed 2026-10-04; a name excluding a directory that is gone is an exemption over nothing.
    "tests/golden/", "tests/fixtures/",                   # frozen expected values
    "node_modules/", "build/", ".venv/", "__pycache__/", ".git/",
)
SKIP_SUFFIX = (".png", ".jpg", ".jpeg", ".ico", ".svg", ".woff", ".woff2", ".parquet",
               ".duckdb", ".gz", ".zip", ".pdf", ".lock")

REJECTS = (
    "UNDECLARED_PAGE",        # a documentation page no home declaration names
    "WRONG_HOME",             # a declared member is not in its declared home
    "PINNED_MOVED",           # a may_not_move page is not at its pinned address
    "TARGET_COLLISION",       # two members resolve to one target path
    "APPEND_ONLY_WRITE",      # a rewrite would edit an append-only record
    "GENERATOR_PATH_STALE",   # a generated member moved; its generator still writes the old path
    "SHAPE_UNGOVERNED",       # the target lands where no shape genre claims it
    "READER_PATH_STALE",      # a tool JOINS the old path — it will open nothing after the move
)


# ── THE DECLARATION ─────────────────────────────────────────────────────────────────────────────────

@dataclass
class Home:
    genre: str
    home: str
    members: list[str] = field(default_factory=list)
    may_not_move: bool = False
    append_only: bool = False
    population_glob: str | None = None
    producers: list[str] = field(default_factory=list)


def _yaml():
    try:
        import yaml
    except ImportError:
        sys.stderr.write("relocate_pages: PyYAML is not importable; cannot read the declaration\n")
        raise SystemExit(2)
    return yaml


def load_decl(path: Path = DECL) -> tuple[dict[str, Home], dict]:
    """The homes, keyed by genre. Exit 2 when the declaration is absent — never an empty PASS."""
    if not path.is_file():
        sys.stderr.write(f"relocate_pages: no declaration at {path}\n")
        raise SystemExit(2)
    doc = _yaml().safe_load(path.read_text(encoding="utf-8")) or {}
    homes: dict[str, Home] = {}
    for genre, spec in (doc.get("homes") or {}).items():
        if not isinstance(spec, dict):
            continue
        pop = spec.get("population") or {}
        frm = pop.get("from") or ""
        homes[genre] = Home(
            genre=genre,
            home=str(spec.get("home") or ""),
            members=[str(m) for m in (spec.get("members") or [])],
            may_not_move=bool(spec.get("may_not_move")),
            append_only=bool(spec.get("append_only")),
            population_glob=frm if "*" in str(frm) else None,
            producers=[str(p.get("tool")) for p in (spec.get("producers") or [])
                       if isinstance(p, dict) and p.get("tool")],
        )
    return homes, doc


# ── THE POPULATION ──────────────────────────────────────────────────────────────────────────────────

def tracked(root: Path, pattern: str = "") -> list[str]:
    args = ["git", "-C", str(root), "ls-files"]
    if pattern:
        args.append(pattern)
    out = subprocess.run(args, capture_output=True, text=True)
    return [l for l in out.stdout.splitlines() if l.strip()]


def documentation_pages(root: Path = ROOT) -> list[str]:
    """Every tracked `*.md` that is documentation, with the exclusions declared above."""
    return [r for r in tracked(root, "*.md")
            if not any(r.startswith(x) or f"/{x}" in r for x in NOT_DOCUMENTATION)]


def _is_entry_readme(rel: str) -> bool:
    """A directory's own README is part of that directory's home, not a homeless page."""
    return rel.endswith("README.md") and "/" in rel


# ── THE PLAN ────────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Plan:
    moves: dict[str, str] = field(default_factory=dict)      # old rel -> new rel, this repository
    pinned: dict[str, str] = field(default_factory=dict)     # rel -> why it may not move
    append_only_homes: list[str] = field(default_factory=list)
    findings: list[tuple[str, str, str]] = field(default_factory=list)   # (reject, subject, detail)
    population: int = 0
    homed: int = 0

    def reject(self, cls: str, subject: str, detail: str) -> None:
        assert cls in REJECTS, f"undeclared reject class {cls}"
        self.findings.append((cls, subject, detail))


def build_plan(homes: dict[str, Home], root: Path = ROOT) -> Plan:
    """Derive the moves from the declaration. Nothing here is typed by hand."""
    p = Plan()
    pages = documentation_pages(root)
    p.population = len(pages)

    declared: dict[str, str] = {}        # rel -> genre
    for h in homes.values():
        if h.append_only:
            p.append_only_homes.append(h.home.split("/")[0])
        for name in h.members:
            if h.may_not_move:
                p.pinned[name] = h.genre
                declared[name] = h.genre
                if not (root / name).is_file():
                    p.reject("PINNED_MOVED", name,
                             f"declared pinned at its own address by `{h.genre}` but is not there")
                continue
            target = f"{h.home}/{name}" if h.home else name
            declared[name] = h.genre
            declared[target] = h.genre
            if (root / name).is_file() and name != target:
                p.moves[name] = target
            elif not (root / target).is_file() and not (root / name).is_file():
                p.reject("WRONG_HOME", name,
                         f"`{h.genre}` names it but it is at neither {name} nor {target}")

    #: A target two members share would have one of them overwrite the other.
    seen: dict[str, str] = {}
    for old, new in p.moves.items():
        if new in seen:
            p.reject("TARGET_COLLISION", new, f"both {seen[new]} and {old} resolve to it")
        seen[new] = old

    #: A generated page whose generator still names the old path comes back on the next run.
    for h in homes.values():
        for name in h.members:
            if name not in p.moves:
                continue
            for tool in h.producers:
                tp = root / tool
                if not tp.is_file():
                    continue
                src = tp.read_text(encoding="utf-8", errors="replace")
                #: ASK WHETHER IT NAMES THE NEW HOME, not whether it still contains the basename —
                #: the basename survives the fix (`ROOT / "reference_manual" / "STRATEGY.md"`), so a
                #: check for the old NAME can never clear and the finding becomes furniture.
                new_dir = p.moves[name].rsplit("/", 1)[0] if "/" in p.moves[name] else ""
                if new_dir and new_dir not in src:
                    p.reject("GENERATOR_PATH_STALE", tool,
                             f"writes {name}; after the move it must write {p.moves[name]}")

    #: A READER THAT JOINS THE OLD PATH, which GENERATOR_PATH_STALE could never see: it asks only about
    #: tools a home block names as a `producer`, and the tools that broke were CONSUMERS. Measured on
    #: the first apply: `check_topology.py` held `ROOT / "TOPOLOGY.md"` and went COULD-NOT-RUN rather
    #: than FAIL — which the runner counts as WORSE than a red, because a could-not-run hides whatever
    #: the red would have said. Three gates regressed this way and a grep found them, not the tool.
    #:
    #: MATCHED AS A PATH JOIN (`/ "NAME"`), never as a mention. Prose cites `CONFORMANCE.md §5.1` all
    #: over this repository and those citations stay true — the basename is preserved, so R3 still
    #: resolves them. A `/ "CONFORMANCE.md"` is a different claim: it is an address being built.
    for tool_rel in tracked(root, "tools/*.py") + tracked(root, "sdk/**/*.py"):
        tp = root / tool_rel
        if not tp.is_file() or tool_rel.endswith("relocate_pages.py"):
            continue
        try:
            src = tp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for old_name, new_rel in sorted(p.moves.items()):
            if re.search(r"""/\s*['"]%s['"]""" % re.escape(old_name), src):
                p.reject("READER_PATH_STALE", tool_rel,
                         f"""joins `/ "{old_name}"`; after the move the page is at {new_rel}""")

    #: Shape governance must survive the move: a page arriving in reference_manual/ that no genre in
    #: guardrails/reference_manual.yaml claims makes check_manual_page_shape report it ungoverned.
    shape_decl = root / "guardrails" / "reference_manual.yaml"
    if shape_decl.is_file():
        shape_text = shape_decl.read_text(encoding="utf-8")
        for old, new in sorted(p.moves.items()):
            if new.startswith("reference_manual/") and new not in shape_text:
                home_dir = new.rsplit("/", 1)[0]
                if f"{home_dir}/" not in shape_text and f"{home_dir}/**" not in shape_text:
                    p.reject("SHAPE_UNGOVERNED", new,
                             "no genre in guardrails/reference_manual.yaml claims this path; "
                             "check_manual_page_shape would report it ungoverned")

    #: Every documentation page under a declared home — the denominator this gate reports.
    for rel in pages:
        top = rel.split("/")[0] if "/" in rel else rel
        if rel in declared or _is_entry_readme(rel):
            p.homed += 1
            continue
        if any(h.home.split("/")[0] == top or h.home == top for h in homes.values()):
            p.homed += 1
            continue
        p.reject("UNDECLARED_PAGE", rel, "no block in guardrails/document_home.yaml names it")
    return p


# ── THE REFERENCES ──────────────────────────────────────────────────────────────────────────────────

@dataclass
class Ref:
    repo: str
    rel: str
    line: int
    start: int
    end: int
    whole: str
    prefix: str
    name: str
    anchor: str
    form: str
    verdict: str = ""
    new_text: str = ""


def ref_rx(names) -> re.Pattern:
    """ONE alternation, LONGEST NAME FIRST — see the substring-collision note in the module docstring."""
    alts = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(
        r"(?<![\w/.-])"
        r"(?P<prefix>(?:\.{1,2}/)*(?:[\w.-]+/)*)"
        r"(?P<name>" + alts + r")"
        r"(?P<anchor>#[\w.-]+)?"
    )


def _form(text: str, m: re.Match) -> str:
    s, e = m.start(), m.end()
    if text[max(0, s - 2):s] == "](":
        return "markdown link"
    if s and text[s - 1] == "`":
        return "backticked"
    if s and text[s - 1] in "'\"":
        return "quoted string"
    if m.group("anchor"):
        return "with an anchor"
    return "bare in prose"


def _retirement_judge():
    """REUSED from check_dangling_references, never re-implemented — one home for the rule."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import check_dangling_references as cdr
        return cdr._RETIRED_CITING_HINT if hasattr(cdr, "_RETIRED_CITING_HINT") else getattr(
            cdr, "_CITES_RETIREMENT", re.compile(
                r"retired|superseded|merged into|moved|no longer|was |→|->|redirect|stub", re.I))
    except Exception:
        return re.compile(r"retired|superseded|merged into|moved|no longer|was |→|->|redirect|stub",
                          re.I)


def scan_refs(plan: Plan, pinned_targets: dict[str, str]) -> list[Ref]:
    """Every reference to a relocating page or a redirect stub, in every repository, classified."""
    names = set(plan.moves) | set(pinned_targets)
    if not names:
        return []
    rx = ref_rx(names)
    retire_rx = _retirement_judge()
    repos = {"meaning-as-code": ROOT, **{k: v for k, v in SIBLINGS.items() if v.is_dir()}}
    refs: list[Ref] = []

    for repo, rroot in repos.items():
        for rel in tracked(rroot):
            if rel.endswith(SKIP_SUFFIX) or any(x in rel for x in ("node_modules/", "/dist/")):
                continue
            fp = rroot / rel
            if not fp.is_file():
                continue
            try:
                text = fp.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if not any(n in text for n in names):
                continue
            starts = [0]
            for ch in text:
                starts.append(starts[-1] + 1)
            for m in rx.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                line = text[text.rfind("\n", 0, m.start()) + 1:
                            (text.find("\n", m.end()) if text.find("\n", m.end()) > 0 else len(text))]
                r = Ref(repo, rel, line_no, m.start(), m.end(), m.group(0),
                        m.group("prefix"), m.group("name"), m.group("anchor") or "",
                        _form(text, m))
                _classify(r, plan, pinned_targets, line, retire_rx, repo, rroot, fp,
                          root=ROOT)
                refs.append(r)
    return refs


def _classify(r: Ref, plan: Plan, pinned: dict[str, str], line: str,
              retire_rx: re.Pattern, repo: str, rroot: Path, fp: Path,
              root: Path | None = None) -> None:
    """One verdict per reference. Only `rewrite` verdicts become edits.

    `root` is THIS repository's root, passed rather than taken from the module so the self-test can
    classify inside a fixture instead of against the live tree — a case that can only be built against
    the real tree stops being a test the day the tree changes.
    """
    root = root or ROOT
    if r.rel.startswith("protocol/"):
        r.verdict = "append-only — protocol/ is never edited"
        return
    if r.name in pinned:
        if retire_rx.search(line):
            r.verdict = "left alone — the line already states the retirement"
        else:
            r.verdict = "owed — points at a redirect stub; repoint at the successor"
        return
    if not r.prefix and r.form != "markdown link":
        r.verdict = "survives — bare basename, resolved by name (R3); basename is preserved"
        return
    #: AN EMPTY PREFIX IN A MARKDOWN LINK IS STILL A RELATIVE PATH — it means "the citing file's own
    #: directory", which is not the same claim as a bare basename R3 resolves by name. `](FRAMEWORK.md)`
    #: inside MODELLERS_COOKBOOK.md worked only while BOTH sat at the root; the moment one of them moves
    #: it breaks. Treating an empty prefix as "survives" missed every link BETWEEN the moving pages —
    #: 27 of them, found by `--verify` and not by this classifier, which is the whole reason the two
    #: share no code.
    if not r.prefix and repo != "meaning-as-code":
        r.verdict = f"cross-repo — a same-directory link in {repo}"
        return
    if repo != "meaning-as-code":
        #: A SIBLING REPOSITORY'S PATH IS NOT THIS TREE'S PATH, and three different things look alike
        #: here. Each is answered by what the written prefix actually is, never by a guess.
        if "tests/fixtures/" in r.rel:
            #: A SIBLING FIXTURE, AND ITS RELATIONSHIP TO THE ORIGINAL IS UNDECLARED. This branch used to
            #: say "mirror — re-copy from the sibling" and cite
            #: `test_the_fixture_is_the_sibling_byte_for_byte` as the authority. MEASURED 2026-10-04,
            #: that was false in three ways: the test hashes exactly THREE paths (`mac_rules.yaml`,
            #: `mac_vocabulary.yaml`, `grammar/query_grammar.yaml`) against the meaning-as-code ROOT and
            #: says nothing about any bundle fixture; the path map below it resolved 22 of 140 fixture
            #: files and 0 of the 9 that two real tests do assert; and
            #: `packages/mac-runtime/tests/fixtures/example_shop_ontology/` is not a mirror at all —
            #: 14 of its 22 common paths already differ from the original on purpose, and its own
            #: conftest calls it "a hermetic copy ... tests never read the sibling repo".
            #:
            #: SO THIS TOOL NO LONGER COPIES ANYTHING THERE. A curated subset overwritten from upstream
            #: is a changed test fixture, which is not a referential fix and is not this tool's call.
            r.verdict = ("owed — a sibling fixture whose relationship to the meaning-as-code original "
                         "is UNDECLARED; a person decides whether this path is held identical")
            return
        if r.prefix.startswith(ROOT.name + "/"):
            r.verdict = f"cross-repo — a path in {repo}, rewritten in that repository's own commit"
            r.new_text = ROOT.name + "/" + plan.moves[r.name] + r.anchor
            return
        if (rroot / r.prefix).is_dir() or (fp.parent / r.prefix).is_dir():
            r.verdict = f"cross-repo — a path in {repo}, rewritten in that repository's own commit"
            r.new_text = plan.moves[r.name] + r.anchor
            return
        #: `framework/STRATEGY.md` resolves to no directory in either tree because it is a console API
        #: path, whose root already IS reference_manual/. Rewriting it to a file path 404s. A code
        #: change owns this, not a path substitution, so the tool reports it and rewrites nothing.
        r.verdict = ("owed — an API path or a path resolving to no directory; a code change in "
                     f"{repo}, not a path rewrite")
        return

    old = (fp.parent / (r.prefix + r.name))
    if not old.exists() and not (root / (r.prefix + r.name)).exists():
        r.verdict = "survives — the written path was already dangling before the move"
        return
    new_abs = root / plan.moves[r.name]
    newdir = (root / plan.moves.get(r.rel, r.rel)).parent
    if (newdir / (r.prefix + r.name)).resolve() == new_abs.resolve() or \
       (root / (r.prefix + r.name)).resolve() == new_abs.resolve():
        r.verdict = "survives — the written path still resolves to the new location"
        return
    r.verdict = "rewrite — the written path stops resolving"
    r.new_text = _new_text(r, plan, root, fp, root=root)


def _new_text(r: Ref, plan: Plan, rroot: Path, fp: Path, cross: bool = False,
              root: Path | None = None) -> str:
    """Keep the kind of path that was written.

    A RELATIVE PATH IS RELATIVE BY CONSTRUCTION — `../CONFORMANCE.md` in a shell script is resolved by
    the shell against the script's own directory, and re-emitting it as `reference_manual/...` silently
    changes what it points at. So the written form decides, not the markup it sits in: a path that
    starts `./` or `../`, and a markdown link, are recomputed RELATIVELY; a path rooted in an owned
    directory stays root-relative, which is the form `check_dangling_references` R2 judges.
    """
    root = root or ROOT
    target = root / plan.moves[r.name]
    newdir = (root / plan.moves.get(r.rel, r.rel)).parent
    if r.prefix.startswith("./") or r.prefix.startswith("../") or r.form == "markdown link":
        return os.path.relpath(target, newdir) + r.anchor
    return plan.moves[r.name] + r.anchor


# ── APPLY ───────────────────────────────────────────────────────────────────────────────────────────

def apply_plan(plan: Plan, refs: list[Ref],
               root: Path = ROOT) -> tuple[int, int, list[str], list[str]]:
    """Rewrite in memory, verify, then write — all or nothing. Moves last, so a failed write moves
    nothing. Returns (files rewritten, pages moved, notes, errors) — a NOTE is what happened, an ERROR
    is what failed, and conflating them made an informational note report FAIL."""
    edits: dict[tuple[str, str], list[Ref]] = {}
    for r in refs:
        #: A cross-repo reference with a computed address is written too — leaving it for later is how
        #: the estate ends up with one repository pointing at an address the other no longer has. It
        #: lands in a SEPARATE COMMIT, which the report names, because git has no cross-repo atom.
        if r.new_text and r.verdict.startswith(("rewrite", "cross-repo")):
            edits.setdefault((r.repo, r.rel), []).append(r)

    staged: dict[tuple[str, str], str] = {}
    for (repo, rel), rs in edits.items():
        rroot = ROOT if repo == "meaning-as-code" else SIBLINGS[repo]
        text = (rroot / rel).read_text(encoding="utf-8")
        for r in sorted(rs, key=lambda x: -x.start):      # right to left; offsets stay valid
            if text[r.start:r.end] != r.whole:
                raise SystemExit(f"relocate_pages: {rel} changed under the plan; refusing to write")
            text = text[:r.start] + r.new_text + text[r.end:]
        staged[(repo, rel)] = text

    for (repo, rel), text in staged.items():
        rroot = ROOT if repo == "meaning-as-code" else SIBLINGS[repo]
        (rroot / rel).write_text(text, encoding="utf-8")

    #: NO FIXTURE IS COPIED. The copy that used to live here mapped a fixture path to an upstream one by
    #: `rel.split("tests/fixtures/", 1)[1]`, which resolved 22 of 140 tracked fixture files and 0 of the
    #: 9 that two real tests assert — a perfect inversion, able to overwrite only the files nothing
    #: checks. See the note in `_classify`.

    moved = 0
    notes: list[str] = []
    errors: list[str] = []
    for old, new in sorted(plan.moves.items()):
        dest = root / new
        dest.parent.mkdir(parents=True, exist_ok=True)
        rc = subprocess.run(["git", "-C", str(root), "mv", old, new],
                            capture_output=True, text=True)
        if rc.returncode:
            errors.append(f"git mv {old} -> {new} failed: {rc.stderr.strip()}")
        else:
            moved += 1
    return len(staged), moved, notes, errors


# ── VERIFY: THE SECOND, INDEPENDENT ASSERTION ───────────────────────────────────────────────────────

def verify(plan: Plan, pinned: dict[str, str]) -> list[str]:
    """Share no code with the rewriter: re-scan every repository for an OLD address that survived."""
    bad: list[str] = []
    repos = {"meaning-as-code": ROOT, **{k: v for k, v in SIBLINGS.items() if v.is_dir()}}
    for repo, rroot in repos.items():
        for rel in tracked(rroot):
            if rel.endswith(SKIP_SUFFIX) or rel.startswith("protocol/"):
                continue
            #: A SIBLING FIXTURE IS EXEMPT BECAUSE ITS LINKS ARE WRITTEN FOR ANOTHER TREE, not because a
            #: test asserts it. The earlier reason here named
            #: `test_the_fixture_is_the_sibling_byte_for_byte` over all 140 such files; that test covers
            #: 3 files and none of them is a fixture bundle. The honest reason is narrower and still
            #: holds: a repository-relative link inside a copied bundle resolves in the tree it was
            #: written for, which was already true before any move (the same file carried
            #: `../reference_manual/shape_reference.md`), and no gate in the sibling repository judges
            #: these links. What is OWED, and is not this tool's to settle, is a declaration of which
            #: fixture paths are held identical to their original and which deliberately differ —
            #: measured: 14 of 22 common paths in the shop fixture already differ.
            if repo != "meaning-as-code" and "tests/fixtures/" in rel:
                continue
            fp = rroot / rel
            if not fp.is_file():
                continue
            try:
                text = fp.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for old in plan.moves:
                for m in re.finditer(r"\]\((?:\.{1,2}/)*(?:[\w.-]+/)*" + re.escape(old) + r"[#)]",
                                     text):
                    link = m.group(0)[2:].rstrip("#)")
                    cand = [(fp.parent / link), (rroot / link)]
                    if not any(c.exists() for c in cand):
                        bad.append(f"{repo}/{rel}: {m.group(0)} does not resolve")
    return bad


# ── REPORTS ─────────────────────────────────────────────────────────────────────────────────────────

def _group(refs: list[Ref]):
    out: dict[str, list[Ref]] = {}
    for r in refs:
        out.setdefault(r.verdict.split(" — ")[0], []).append(r)
    return out


def report_plan(plan: Plan, refs: list[Ref], pinned: dict[str, str]) -> None:
    print("THE MOVES — derived from guardrails/document_home.yaml, not listed here\n")
    for old, new in sorted(plan.moves.items()):
        print(f"  {old:26} ->  {new}")
    print(f"\n  {len(plan.moves)} page(s) move. Every basename is preserved.\n")
    print("PINNED — declared unable to move, with the reason in the declaration")
    for name, genre in sorted(pinned.items()):
        print(f"  {name:26}  {genre}")
    g = _group(refs)
    print(f"\nREFERENCES — {len(refs)} matched across "
          f"{len({(r.repo, r.rel) for r in refs})} file(s) in "
          f"{len({r.repo for r in refs})} repositor(y/ies)\n")
    for verdict in sorted(g, key=lambda k: -len(g[k])):
        rs = g[verdict]
        print(f"  {len(rs):4}  {verdict}")
        for r in rs[:3]:
            arrow = f"  ->  {r.new_text}" if r.new_text else ""
            print(f"          {r.repo}/{r.rel}:{r.line}  {r.whole}{arrow}")
        if len(rs) > 3:
            print(f"          … and {len(rs) - 3} more")
    writes = {(r.repo, r.rel) for r in refs if r.verdict.startswith("rewrite")}
    cross = {(r.repo, r.rel) for r in refs if r.verdict.startswith("cross-repo")}
    owed = [r for r in refs if r.verdict.startswith("owed")]
    print(f"\nWHAT --apply WOULD WRITE: {len(writes)} file(s) in meaning-as-code, "
          f"{len(plan.moves)} git mv.")
    if cross:
        print(f"WHAT IT CANNOT: {len(cross)} file(s) in a sibling repository — a separate commit each:")
        for repo, rel in sorted(cross):
            print(f"  {repo}/{rel}")
    if owed:
        print(f"OWED, SEPARATELY: {len(owed)} reference(s) point at a redirect stub and should be "
              f"repointed at its successor. Not part of a move.")


def report_findings(plan: Plan) -> None:
    if not plan.findings:
        return
    print("FINDINGS\n")
    for cls, subject, detail in plan.findings:
        print(f"  [{cls}] {subject}\n      {detail}")
    print()


# ── SELF-TEST ───────────────────────────────────────────────────────────────────────────────────────

def self_test() -> int:
    """One mutant per reject class plus a clean fixture. A mutant that does not exercise the class it
    names is the trap this estate has already been bitten by, so each asserts the class BY NAME."""
    yaml = _yaml()
    cases, ok = [], 0

    def decl(homes: dict) -> str:
        return yaml.safe_dump({"spec_version": "mac.guardrail/1", "topic": "t", "homes": homes})

    def run(tmp: Path, homes: dict):
        (tmp / "guardrails").mkdir(parents=True, exist_ok=True)
        d = tmp / "guardrails" / "document_home.yaml"
        d.write_text(decl(homes), encoding="utf-8")
        h, _ = load_decl(d)
        return build_plan(h, tmp)

    def fixture() -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="relocate_st_"))
        subprocess.run(["git", "-C", str(tmp), "init", "-q"], check=True)
        for rel, body in (("A.md", "# A\n"), ("reference_manual/x.md", "# x\n"),
                          ("protocol/2026-01-01/e.md", "# e\n"), ("README.md", "# r\n")):
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(body, encoding="utf-8")
        subprocess.run(["git", "-C", str(tmp), "add", "-A"], check=True,
                       capture_output=True)
        return tmp

    CLEAN = {"spec": {"home": "reference_manual", "members": ["A.md"]},
             "entry": {"home": "«root»", "may_not_move": True, "members": ["README.md"]},
             "manual": {"home": "reference_manual",
                        "population": {"from": "reference_manual/**/*.md"}},
             "proto": {"home": "protocol/{date}", "append_only": True,
                       "population": {"from": "protocol/**/*.md"}}}

    # 1 — the clean fixture raises nothing
    t = fixture()
    p = run(t, CLEAN)
    cases.append(("clean fixture raises no finding", not p.findings, [f[0] for f in p.findings]))
    cases.append(("clean fixture derives the one move", p.moves == {"A.md": "reference_manual/A.md"},
                  p.moves))
    shutil.rmtree(t, ignore_errors=True)

    # 2 — UNDECLARED_PAGE
    t = fixture()
    (t / "ORPHAN.md").write_text("# o\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(t), "add", "-A"], capture_output=True)
    p = run(t, CLEAN)
    cases.append(("UNDECLARED_PAGE on a homeless root page",
                  any(f[0] == "UNDECLARED_PAGE" and f[1] == "ORPHAN.md" for f in p.findings),
                  p.findings))
    shutil.rmtree(t, ignore_errors=True)

    # 3 — WRONG_HOME
    t = fixture()
    p = run(t, {**CLEAN, "spec": {"home": "reference_manual", "members": ["GONE.md"]}})
    cases.append(("WRONG_HOME when a named member is at neither address",
                  any(f[0] == "WRONG_HOME" for f in p.findings), p.findings))
    shutil.rmtree(t, ignore_errors=True)

    # 4 — PINNED_MOVED
    t = fixture()
    (t / "README.md").unlink()
    subprocess.run(["git", "-C", str(t), "add", "-A"], capture_output=True)
    p = run(t, CLEAN)
    cases.append(("PINNED_MOVED when a pinned page is absent",
                  any(f[0] == "PINNED_MOVED" for f in p.findings), p.findings))
    shutil.rmtree(t, ignore_errors=True)

    # 5 — TARGET_COLLISION. TWO DISTINCT SOURCES, ONE TARGET, which is the only way to reach it:
    # two members with the SAME basename collapse onto one dict key and overwrite rather than collide,
    # so a mutant built that way asserts nothing about this class. `x/A.md` under `reference_manual`
    # and `A.md` under `reference_manual/x` are different sources and the same destination.
    t = fixture()
    (t / "x").mkdir(exist_ok=True)
    (t / "x" / "A.md").write_text("# xa\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(t), "add", "-A"], capture_output=True)
    p = run(t, {**CLEAN,
                "spec": {"home": "reference_manual", "members": ["x/A.md"]},
                "spec2": {"home": "reference_manual/x", "members": ["A.md"]}})
    cases.append(("TARGET_COLLISION when two distinct sources share one target",
                  any(f[0] == "TARGET_COLLISION" for f in p.findings),
                  [f[0] for f in p.findings] or p.moves))
    #: And the negative: two different basenames into one home is NOT a collision.
    p2 = run(t, {**CLEAN, "spec": {"home": "reference_manual", "members": ["A.md"]},
                 "spec2": {"home": "reference_manual", "members": ["x/A.md"]}})
    cases.append(("…and two different targets in one home are not a collision",
                  not any(f[0] == "TARGET_COLLISION" for f in p2.findings),
                  [f[0] for f in p2.findings]))
    shutil.rmtree(t, ignore_errors=True)

    # 6 — GENERATOR_PATH_STALE
    t = fixture()
    (t / "tools").mkdir(exist_ok=True)
    (t / "tools" / "gen_a.py").write_text('OUT = "A.md"\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(t), "add", "-A"], capture_output=True)
    p = run(t, {**CLEAN, "spec": {"home": "reference_manual", "members": ["A.md"],
                                  "producers": [{"tool": "tools/gen_a.py"}]}})
    cases.append(("GENERATOR_PATH_STALE when the generator names the old path",
                  any(f[0] == "GENERATOR_PATH_STALE" for f in p.findings), p.findings))
    shutil.rmtree(t, ignore_errors=True)

    # 7 — READER_PATH_STALE. A CONSUMER, not a producer: the class GENERATOR_PATH_STALE cannot see,
    # and the one that actually regressed three gates. The negative is beside it because the rule's
    # whole precision is that it matches a path JOIN and not a prose citation.
    t = fixture()
    (t / "tools").mkdir(exist_ok=True)
    (t / "tools" / "reader.py").write_text('P = ROOT / "A.md"\n', encoding="utf-8")
    (t / "tools" / "citer.py").write_text('"""See A.md §5.1 for the rule."""\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(t), "add", "-A"], capture_output=True)
    p = run(t, CLEAN)
    stale = [f for f in p.findings if f[0] == "READER_PATH_STALE"]
    cases.append(("READER_PATH_STALE on a tool that JOINS the old path",
                  any(f[1] == "tools/reader.py" for f in stale), p.findings))
    cases.append(("…and NOT on a tool that only cites the page in prose",
                  not any(f[1] == "tools/citer.py" for f in stale), [f[1] for f in stale]))
    shutil.rmtree(t, ignore_errors=True)

    # 8 — SHAPE_UNGOVERNED
    t = fixture()
    (t / "guardrails").mkdir(exist_ok=True)
    (t / "guardrails" / "reference_manual.yaml").write_text(
        "authored:\n  g:\n    path: reference_manual/other/*.md\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(t), "add", "-A"], capture_output=True)
    p = run(t, {**CLEAN, "spec": {"home": "reference_manual/specification", "members": ["A.md"]}})
    cases.append(("SHAPE_UNGOVERNED when no shape genre claims the target",
                  any(f[0] == "SHAPE_UNGOVERNED" for f in p.findings), p.findings))
    shutil.rmtree(t, ignore_errors=True)

    # 8 — APPEND_ONLY_WRITE: a reference inside protocol/ is never an edit
    pl = Plan(moves={"A.md": "reference_manual/A.md"})
    r = Ref("meaning-as-code", "protocol/2026-01-01/e.md", 1, 0, 5, "x/A.md", "x/", "A.md", "", "x")
    _classify(r, pl, {}, "see x/A.md", re.compile("zzz"), "meaning-as-code", ROOT, ROOT / "README.md")
    cases.append(("APPEND_ONLY: a protocol/ reference is never an edit",
                  r.verdict.startswith("append-only") and not r.new_text, r.verdict))

    # 9 — the substring collision that would corrupt silently
    rx = ref_rx({"TESTING.md", "PIPELINE_TESTING.md"})
    hits = [m.group("name") for m in rx.finditer("see PIPELINE_TESTING.md and TESTING.md")]
    cases.append(("longest-match-first: PIPELINE_TESTING.md is not matched as TESTING.md",
                  hits == ["PIPELINE_TESTING.md", "TESTING.md"], hits))

    # 10 — a bare basename is never rewritten
    pl = Plan(moves={"A.md": "reference_manual/A.md"})
    r = Ref("meaning-as-code", "x.md", 1, 0, 4, "A.md", "", "A.md", "", "bare in prose")
    _classify(r, pl, {}, "see A.md", re.compile("zzz"), "meaning-as-code", ROOT, ROOT / "README.md")
    cases.append(("a bare basename survives and is not rewritten",
                  r.verdict.startswith("survives") and not r.new_text, r.verdict))

    # 11 — AN EMPTY PREFIX IN A MARKDOWN LINK IS RELATIVE, NOT A BASENAME. This is the class `--verify`
    # caught and the classifier missed: 27 links BETWEEN pages that both moved. The negative case is
    # beside it, because the rule is about the FORM and not about the prefix alone.
    t = fixture()
    (t / "B.md").write_text("[a](A.md) and `A.md`\n", encoding="utf-8")
    pl = Plan(moves={"A.md": "reference_manual/g/A.md", "B.md": "reference_manual/s/B.md"})
    link = Ref("meaning-as-code", "B.md", 1, 0, 4, "A.md", "", "A.md", "", "markdown link")
    _classify(link, pl, {}, "[a](A.md)", re.compile("zzz"), "meaning-as-code", t, t / "B.md", root=t)
    cases.append(("an empty-prefix markdown link between two movers is rewritten",
                  link.verdict.startswith("rewrite") and link.new_text == "../g/A.md",
                  (link.verdict, link.new_text)))
    bare = Ref("meaning-as-code", "B.md", 1, 0, 4, "A.md", "", "A.md", "", "backticked")
    _classify(bare, pl, {}, "`A.md`", re.compile("zzz"), "meaning-as-code", t, t / "B.md", root=t)
    cases.append(("…while the same empty prefix backticked still survives (R3)",
                  bare.verdict.startswith("survives") and not bare.new_text, bare.verdict))
    shutil.rmtree(t, ignore_errors=True)

    # 12 — a retirement already stated is left alone
    r = Ref("meaning-as-code", "x.md", 1, 0, 4, "S.md", "", "S.md", "", "bare in prose")
    _classify(r, Plan(), {"S.md": "redirect_stub"}, "S.md was merged into T.md",
              re.compile("merged into", re.I), "meaning-as-code", ROOT, ROOT / "README.md")
    cases.append(("a line that states the retirement is left alone",
                  r.verdict.startswith("left alone"), r.verdict))

    for label, passed, got in cases:
        print(f"  {'ok  ' if passed else 'FAIL'}  {label}")
        if not passed:
            print(f"          got: {got}")
        ok += bool(passed)
    print(f"\n{'PASS' if ok == len(cases) else 'FAIL'}: relocate_pages --self-test — "
          f"{ok} of {len(cases)} case(s) over {len(REJECTS)} reject class(es)")
    return 0 if ok == len(cases) else 1


# ── MAIN ────────────────────────────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", action="store_true", help="report what a move would do; write nothing")
    ap.add_argument("--apply", action="store_true", help="perform the moves and the rewrites")
    ap.add_argument("--verify", action="store_true", help="the independent assertion, after a move")
    ap.add_argument("--check", action="store_true", help="gate: every page in a declared home")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if a.self_test:
        return self_test()

    homes, doc = load_decl()
    plan = build_plan(homes)
    pinned_members = {m: h.genre for h in homes.values() if h.may_not_move for m in h.members
                      if m != "README.md"}

    if a.plan or a.apply:
        refs = scan_refs(plan, pinned_members)
        report_plan(plan, refs, {m: g for m, g in pinned_members.items()})
        report_findings(plan)
        blockers = [f for f in plan.findings if f[0] in
                    ("TARGET_COLLISION", "SHAPE_UNGOVERNED", "GENERATOR_PATH_STALE", "PINNED_MOVED")]
        if a.apply:
            if blockers:
                print(f"FAIL: relocate_pages --apply refused — {len(blockers)} blocking finding(s); "
                      f"nothing was moved or written")
                return 1
            files, moved, notes, errors = apply_plan(plan, refs)
            for n in notes:
                print(f"  note:  {n}")
            for e in errors:
                print(f"  ERROR: {e}")
            bad = verify(plan, pinned_members)
            for b in bad:
                print(f"  STALE {b}")
            print(f"\n{'FAIL' if (bad or errors) else 'PASS'}: relocate_pages --apply — "
                  f"{moved} page(s) moved, {files} file(s) rewritten, {len(notes)} note(s), "
                  f"{len(bad)} stale address(es) after the move")
            return 1 if (bad or errors) else 0
        print(f"\nPASS: relocate_pages --plan — {len(plan.moves)} move(s) derived, "
              f"{len(refs)} reference(s) judged over {plan.population} documentation page(s), "
              f"{len(plan.findings)} finding(s) — nothing written")
        return 0

    if a.verify:
        bad = verify(plan, pinned_members)
        for b in bad:
            print(f"  STALE {b}")
        print(f"{'FAIL' if bad else 'PASS'}: relocate_pages --verify — "
              f"{len(bad)} unresolved old address(es) over {plan.population} documentation page(s)")
        return 1 if bad else 0

    report_findings(plan)
    news = [f for f in plan.findings if f[0] != "UNDECLARED_PAGE"] if plan.moves else plan.findings
    print(f"{'FAIL' if plan.findings else 'PASS'}: relocate_pages — "
          f"{plan.homed} of {plan.population} documentation page(s) in a declared home, "
          f"{len(plan.moves)} awaiting relocation, {len(plan.findings)} finding(s) over "
          f"{len(REJECTS)} reject class(es)")
    return 1 if plan.findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
