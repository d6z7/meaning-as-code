#!/usr/bin/env python3
"""MAC — a document may not cite a file that is not there.

THE INCIDENT, MEASURED 2026-09-29. A read-only inventory of this repository's prose found 142 hard
findings across 110 documents. Four of them show the shape of the defect:

  README.md:126           sold CONCEPT_SPEC.md as "the exhaustive key-by-key reference" — a 27-line
                          RETIRED redirect stub. Twenty-five documents cited it as the key reference,
                          including every pattern page's `canon_ref:` line.
  MODELLERS_COOKBOOK.md   linked five worked examples into example_shop_ontology/concepts/, rules.yaml,
                          tables/orders.yaml — the layout BEFORE the two-plane reorg.
                          Every link was dead; the cookbook is the document an author opens first.
  RELEASING.md:63         named tools/check_projections.py as the freshness gate. It was never written.
  boundaries.yaml         cited by TOPOLOGY.md, SEAM_CONTRACT.md and sdk/README.md as if it were here.
                          It is at the HOST repository's root (mac-platform/), enforced by a gate in
                          sdk/gate/ — true, and unfindable from any of the three sentences.

None of these was a lie when written. Files moved, a proposal was retired, a plan was not built, and
the sentences that pointed at them kept reading well. Prose does not rot visibly, so this turns a
citation check on every document in the tree: every *.md, the module docstring of every tool and SDK
module, and the prose fields of the
guardrails. A pointer that resolves to nothing is a defect with a predicate, so it gets a gate.

WHAT IT SCANS
  * every `*.md` under the root, except .git/ build/ node_modules/ .venv/ __pycache__/ .pytest_cache/
    (pytest writes its own README there) and protocol/ (append-only: an old entry may name a file
    that has since moved, and that is history);
  * the MODULE DOCSTRING of tools/**/*.py and sdk/**/*.py — the paragraph a reader is sent to;
  * the PROSE FIELDS of guardrails/**/*.yaml, the same fields `check_retired_terms.PROSE_FIELDS` names.

THE REFERENCE FORMS, AND WHAT EACH SEVERITY MEANS
  R1  a markdown link `[text](relative/target)`             -> ERROR when the target does not exist
  R2  a backticked path rooted in an OWNED directory        -> ERROR when it does not exist
      (tools/ decisions/ reference_manual/ guardrails/ sdk/ grammar/ registers/ benchmark/ bundlegen/
       invariants/ recognition/ tests/ protocol/ articles/) — a path under one of these is a claim about THIS repository and is judged as one
  R3  a backticked bare basename (foo.py, x.yaml)           -> ERROR when no file of that name exists
                                                              anywhere in the tree; WARNING when several
                                                              do and the sentence does not say which
  R4  a link or owned path that RESOLVES, to a document whose front-matter `status:` (or a bold first
      line) says RETIRED / SUPERSEDED                       -> ERROR unless the citing line says so
                                                              itself ("retired", "superseded", "was",
                                                              or a "→")
  Resolution: relative to the citing file first, then the repository root. A link ending in "/" must
  be a directory. WARNINGs are printed and counted; only ERRORs decide the exit code.

EXEMPTIONS — each declared, each with its reason, none silent
  cross-repo       a target under mac-platform/ mac-console/ mac-integration-kit/ mac-ontology-*/
                   packages/ mac_runtime/ okf_core/ foldplane/ platform/skills/ lives in another
                   repository this gate cannot see. Listed as UNLOCATED, never failed: a sentence that
                   names the other repo has done the honest thing.
  bundle-relative  a file whose front-matter or first ten lines declare `paths: bundle-relative`
                   describes an APPLIED ontology's files (data/…, acceptance/…, master.yaml).
                   Its bundle-rooted paths and bare basenames are UNLOCATED (bundle); its links and
                   its owned-root paths are still judged.
  templated        a target holding any of < > { } * $ | … ( is a shape or a code reference, not a file;
                   a `path::symbol` suffix and `:12,15` line lists are stripped before judging.
  root-anchored    `/guardrails/ontology/` is read from the repository root — that is what the slash means
                   in this tree's prose.
  module path      `sdk.connector.duckdb` looks like a basename with a .duckdb extension and is a Python
                   module; a dotted target that maps to an existing .py under the root is not judged.
  docstrings and   a tool's docstring names the BUNDLE files it reads (master.yaml, d_customer.yaml,
  guardrail prose  contoso.duckdb) far more often than files of this repo, so their bare basenames are
                   UNLOCATED (bundle) by default; their owned-root paths and links are still judged.
  designed, not    a document whose first twelve lines carry a DESIGNED, NOT ENFORCED banner has already
  enforced         told the reader that nothing in it is guaranteed to exist; its owned-root paths and
                   bare basenames are UNLOCATED (design). Its links are still judged.
  leading-dot      `.lookup.csv`, `.venv` — a fragment or a dotfile; not judged (cost accepted).
  fenced code      inside ``` or ~~~ — example text, not a citation.
  self-quoting     a line that itself says the target is gone or hypothetical: "does not exist",
                   "no longer exists", "never written", "never existed", "MISSING", "would be",
                   "proposed", "retired", "superseded", "former", "not shipped", "not committed",
                   "never shipped", "not built", "scratch", "there is no", "no separate". The sentence
                   has already told the reader; failing it would punish honesty.
  not judged       bare un-backticked mentions ("see RECORD: decisions/x.md") and backticked paths
                   whose first segment is NOT an owned directory (`data/x.yaml`, `canon/x.md`) — the
                   first would flag every sentence that mentions a directory, the second is usually a
                   bundle path or a path relative to a parent that only a human can place.

ROLLOUT — A RATCHET
  tools/dangling_floor.txt lists the findings that were still open the day the gate shipped, one
  per line as `file:line:target`. Exit 1 on any ERROR not in that file. The file may only SHRINK: an
  entry that no longer fires is STALE and also exits 1, so the floor tracks the tree. An entry matches
  on FILE and TARGET; the line is where the finding was when recorded, kept for the reader, because a
  paragraph inserted above it must not turn one accepted finding into one STALE plus one NEW.
  `--write-baseline` rewrites the file and REFUSES if that would add an entry (first creation excepted).

Contract: one PASS:/FAIL: line, exit 0 or 1, exit 2 when it could not run, denominators printed,
and `--self-test` with one mutant per reject class.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_retired_terms import PROSE_FIELDS, _walk  # noqa: E402  (one home for "where a person reads prose")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path(__file__).resolve().parent / "dangling_floor.txt"

SKIP_DIRS = {".git", "build", "node_modules", ".venv", "__pycache__", ".pytest_cache", "protocol",
             ".harvest_cache", "evidence"}
OWNED = ("tools", "decisions", "reference_manual", "guardrails", "sdk", "grammar", "registers", "benchmark",
         "bundlegen", "invariants", "recognition", "tests",
         "protocol", "articles")
CROSS_REPO = ("mac-platform/", "mac-console/", "mac-integration-kit/", "mac-ontology-", "packages/",
              "mac_runtime/", "okf_core/", "foldplane/", "platform/skills/")
BUNDLE_ROOTS = ("data", "ontology", "acceptance", "governance", "projections", "quality", "transforms",
                "profiles", "lookups", "datasets", "samples", "sources", "concepts", "references", "lineage")
TEMPLATED = set("<>{}*$|…(")
EXTS = ("md", "py", "yaml", "yml", "json", "sh", "txt", "csv", "sql", "html", "js", "mmd", "svg", "drawio",
        "duckdb", "zip", "xlsx", "jsx", "ts", "tsx", "css", "toml", "cfg", "ini", "lock")

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
TICK_RE = re.compile(r"`([^`\n]+)`")
BASENAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(%s)$" % "|".join(EXTS))
FENCE_RE = re.compile(r"^\s*(```|~~~)")
SELF_QUOTING_RE = re.compile(
    r"does not exist|no longer exists?|never written|never existed|MISSING|would be|proposed|retired|"
    r"superseded|former|not shipped|not committed|never shipped|not built|scratch|there is no|no separate", re.I)
MARKED_RE = re.compile(r"retired|superseded|\bwas\b|→", re.I)
BUNDLE_DECL_RE = re.compile(r"paths:\s*bundle-relative", re.I)
DESIGN_DECL_RE = re.compile(r"designed,?\s+not\s+enforced", re.I)
RETIRED_STATUS_RE = re.compile(r"^(?:status:\s*|\*\*(?:status:\s*)?)(?:RETIRED|SUPERSEDED)\b", re.I | re.M)


class Finding:
    __slots__ = ("file", "line", "target", "rule", "severity", "note")

    def __init__(self, file, line, target, rule, severity, note=""):
        self.file, self.line, self.target, self.rule, self.severity, self.note = file, line, target, rule, severity, note

    def key(self):
        return f"{self.file}:{self.target}"

    def __str__(self):
        return f"{self.file}:{self.line}:{self.target}"


# ---------------------------------------------------------------- the population
def _md_files(root: Path):
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            if fn.endswith(".md"):
                yield Path(dp) / fn


def _py_files(root: Path):
    for sub in ("tools", "sdk"):
        base = root / sub
        if not base.is_dir():
            continue
        for dp, dns, fns in os.walk(base):
            dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
            for fn in sorted(fns):
                if fn.endswith(".py"):
                    yield Path(dp) / fn


def _guardrail_files(root: Path):
    base = root / "guardrails"
    if not base.is_dir():
        return
    for dp, dns, fns in os.walk(base):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            if fn.endswith((".yaml", ".yml")):
                yield Path(dp) / fn


def _lines_md(path: Path):
    """(lineno, text) for every prose line of a markdown file, fenced blocks removed."""
    fenced = False
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            yield i, line


def _lines_docstring(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return
    doc = ast.get_docstring(tree, clean=False)
    if not doc or not tree.body:
        return
    start = getattr(tree.body[0], "lineno", 1)
    fenced = False
    for i, line in enumerate(doc.splitlines()):
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            yield start + i, line


def _lines_guardrail(path: Path):
    import yaml
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return
    raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for where, text in _walk(doc):
        for t in text.splitlines():
            lineno = next((i for i, r in enumerate(raw, 1) if t.strip() and t.strip()[:40] in r), 0)
            yield lineno, t


# ---------------------------------------------------------------- the judgement
def _head(path: Path, n: int) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[:n])
    except OSError:
        return ""


def _declares_bundle_relative(path: Path) -> bool:
    return bool(BUNDLE_DECL_RE.search(_head(path, 10)))


def _declares_design(path: Path) -> bool:
    return bool(DESIGN_DECL_RE.search(_head(path, 12)))


def _is_retired(path: Path) -> bool:
    if path.suffix != ".md" or not path.is_file():
        return False
    head = "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[:12])
    return bool(RETIRED_STATUS_RE.search(head))


def _clean(target: str) -> str:
    t = target.strip().split()[0] if target.strip() else ""
    t = t.split("#", 1)[0].split("§", 1)[0].split("::", 1)[0]
    t = re.sub(r":\d+(?:[-,]\d+)*$", "", t)      # `tools/x.py:12` / `:12-40` / `:68,75,77`
    t = t.rstrip(".,;:)'\"")
    return t


def _is_module_path(root: Path, target: str) -> bool:
    parts = target.split(".")
    return len(parts) >= 2 and (root / "/".join(parts)).with_suffix(".py").is_file()


def _resolve(root: Path, citing: Path, target: str) -> Path | None:
    if target.startswith("/"):
        cand = root / target.lstrip("/")
        return cand if cand.exists() else None
    for base in (citing.parent, root):
        cand = (base / target)
        if cand.exists():
            return cand
    return None


_PER_CONTAINER: set[str] = set()


def scan(root: Path, index: dict[str, list[Path]] | None = None):
    """Returns (findings, unlocated, counts). `index` maps basename -> every file with that name."""
    global _PER_CONTAINER
    if not _PER_CONTAINER:
        _PER_CONTAINER = _per_container_names()
    if index is None:
        index = defaultdict(list)
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in {".git", "node_modules", ".venv", "__pycache__", "build"}]
            for fn in fns:
                index[fn].append(Path(dp) / fn)
    findings: list[Finding] = []
    unlocated: list[Finding] = []
    counts = {"md": 0, "py": 0, "guardrails": 0, "refs": 0}

    def judge(path: Path, lines, kind: str):
        rel = path.relative_to(root).as_posix()
        bundle_rel = _declares_bundle_relative(path)
        design = _declares_design(path)
        loose_basenames = bundle_rel or kind != "md"   # docstrings/guardrail prose name bundle files
        for lineno, text in lines:
            self_quoting = bool(SELF_QUOTING_RE.search(text))
            marked = bool(MARKED_RE.search(text))
            seen = set()
            # R1 links
            for m in LINK_RE.finditer(text):
                raw = m.group(1)
                if "://" in raw or raw.startswith(("#", "mailto:", "/")):
                    continue
                want_dir = raw.rstrip().endswith("/")
                t = _clean(raw)
                if not t or t in seen or set(t) & TEMPLATED or (t.startswith(".") and not t.startswith(("./", "../"))):
                    continue
                seen.add(t)
                counts["refs"] += 1
                if t.startswith(CROSS_REPO):
                    unlocated.append(Finding(rel, lineno, t, "R1", "UNLOCATED", "cross-repo"))
                    continue
                if self_quoting:
                    continue
                r = _resolve(root, path, t)
                if r is None or (want_dir and not r.is_dir()):
                    if bundle_rel and (t.split("/")[0] in BUNDLE_ROOTS or "/" not in t):
                        unlocated.append(Finding(rel, lineno, t, "R1", "UNLOCATED", "bundle"))
                    else:
                        findings.append(Finding(rel, lineno, t, "R1", "ERROR", "link target does not exist"))
                elif _is_retired(r) and not marked:
                    findings.append(Finding(rel, lineno, t, "R4", "ERROR", "target is RETIRED/SUPERSEDED and the line does not say so"))
            # R2 / R3 backticked
            for m in TICK_RE.finditer(text):
                t = _clean(m.group(1))
                if not t or t in seen or set(t) & TEMPLATED or " " in m.group(1).strip():
                    continue
                if t.startswith(".") and not t.startswith(("./", "../")):
                    continue
                if t.startswith(CROSS_REPO):
                    seen.add(t)
                    counts["refs"] += 1
                    unlocated.append(Finding(rel, lineno, t, "R2", "UNLOCATED", "cross-repo"))
                    continue
                first = t.lstrip("./").split("/")[0]
                if "/" in t and first in OWNED and not t.startswith("../"):
                    seen.add(t)
                    counts["refs"] += 1
                    if self_quoting:
                        continue
                    r = _resolve(root, path, t)
                    if r is None:
                        if design:
                            unlocated.append(Finding(rel, lineno, t, "R2", "UNLOCATED", "design"))
                        else:
                            findings.append(Finding(rel, lineno, t, "R2", "ERROR", "owned-root path does not exist"))
                    elif _is_retired(r) and not marked:
                        findings.append(Finding(rel, lineno, t, "R4", "ERROR", "target is RETIRED/SUPERSEDED and the line does not say so"))
                elif "/" not in t and BASENAME_RE.match(t) and not _is_module_path(root, t):
                    seen.add(t)
                    counts["refs"] += 1
                    if self_quoting:
                        continue
                    if _resolve(root, path, t) is not None:
                        continue
                    hits = index.get(t, [])
                    if not hits:
                        if loose_basenames or design:
                            unlocated.append(Finding(rel, lineno, t, "R3", "UNLOCATED", "bundle" if loose_basenames else "design"))
                        else:
                            findings.append(Finding(rel, lineno, t, "R3", "ERROR", "no file of this name anywhere in the tree"))
                    elif len(hits) > 1:
                        if t in _PER_CONTAINER:
                            unlocated.append(Finding(
                                rel, lineno, t, "R3", "UNLOCATED",
                                f"per-container — {len(hits)} containers each carry one, declared by "
                                f"tools/mac_resources.py or sdk/container/spec.py"))
                        else:
                            findings.append(Finding(rel, lineno, t, "R3", "WARNING",
                                                    f"ambiguous — {len(hits)} files carry this name"))
        counts[kind] += 1

    for p in _md_files(root):
        judge(p, _lines_md(p), "md")
    for p in _py_files(root):
        judge(p, _lines_docstring(p), "py")
    for p in _guardrail_files(root):
        judge(p, _lines_guardrail(p), "guardrails")
    return findings, unlocated, counts


# ---------------------------------------------------------------- per-container resources, DECLARED
#: A FILE EVERY CONTAINER HAS ONE OF IS NOT AN AMBIGUOUS REFERENCE. MEASURED 2026-10-04: of 141
#: WARNINGs, 76 named such a file — 32 `mac.project.yaml` (which `sdk/container/spec.py` DEFINES as
#: "a directory whose root `mac.project.yaml` is the manifest", so every container has exactly one) and
#: 44 a resource `tools/mac_resources.py` already declares as produced per bundle. Over the in-scope
#: trees `mac.project.yaml` resolved to 20 files with 20 distinct contents: 11 generated BIRD bundles,
#: 2 exemplars, 1 authoring exemplar, 5 platform fixtures and contoso5. Nothing is redundant there and
#: no sentence can be made less ambiguous — "the bundle's manifest" is what the citation means.
#:
#: READ FROM THE REGISTER, NEVER LISTED HERE. `mac_resources` already says which files a bundle carries
#: and who produces them; a second list in this gate would be a second home for that fact and would go
#: stale the first time a resource is added. The container manifest comes from the container spec for
#: the same reason.
_CONTAINER_MANIFEST = "mac.project.yaml"


def _per_container_names() -> set[str]:
    """Basenames a container/bundle has ONE of, from the declarations that already say so."""
    names = {_CONTAINER_MANIFEST}
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import mac_resources as mr
        for block in ("DERIVED", "AUTHORED", "NOT_DECLARED"):
            for item in getattr(mr, block, ()) or ():
                g = (item or {}).get("glob") or ""
                base = g.rsplit("/", 1)[-1]
                if base and "*" not in base:
                    names.add(base)
        #: PLANES is a tuple of (plane, glob, kind) TRIPLES, not dicts — reading only the dict blocks
        #: missed `ontology/rules.yaml` and `ontology/edges.yaml`, which are the plane-level declarations
        #: a bundle has exactly one of, and left 16 warnings standing about them.
        for row in getattr(mr, "PLANES", ()) or ():
            g = row[1] if len(row) > 1 else ""
            base = str(g).rsplit("/", 1)[-1]
            if base and "*" not in base:
                names.add(base)
    except Exception:                                                     # noqa: BLE001
        #: A register that cannot be imported must not silently shrink the exemption: the gate then
        #: warns as it did before, which is the honest degradation.
        pass
    try:
        #: `mac_manifest.NOT_DELIVERED` is the third register that already says "one per bundle, and the
        #: bundle AUTHORS it": `connection.yaml` is listed there as "authored input; the connector seam
        #: reads it", one line above the `mac.project.yaml` entry. That one line accounts for 27 of the
        #: remaining warnings. Only CONCRETE basenames are taken — the block also holds `*.duckdb`,
        #: `data/*.parquet` and `**/.*`, and a wildcard says nothing about how many a bundle has.
        import mac_manifest as mm
        for pattern, _reason in getattr(mm, "NOT_DELIVERED", ()) or ():
            base = str(pattern).rsplit("/", 1)[-1]
            if base and "*" not in base and "?" not in base:
                names.add(base)
    except Exception:                                                     # noqa: BLE001
        pass
    try:
        import yaml
        doc = yaml.safe_load((ROOT / "mac_artifacts.yaml").read_text(encoding="utf-8")) or {}

        def walk(n):
            if isinstance(n, dict):
                for k, v in n.items():
                    if k in ("path", "glob") and isinstance(v, str) and "*" not in v:
                        names.add(v.rsplit("/", 1)[-1])
                    walk(v)
            elif isinstance(n, list):
                for x in n:
                    walk(x)
        walk(doc)
    except Exception:                                                     # noqa: BLE001
        pass
    return names


# ---------------------------------------------------------------- the baseline
def read_baseline(path: Path) -> dict[str, str]:
    """key `file:target` -> the recorded `file:line:target`."""
    out = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":", 2)
        if len(parts) == 3:
            out[f"{parts[0]}:{parts[2]}"] = line
    return out


def write_baseline(path: Path, errors: list[Finding], measured: str):
    seen = set()
    rows = []
    for f in sorted(errors, key=lambda f: (f.file, f.line, f.target)):
        if f.key() in seen:
            continue
        seen.add(f.key())
        rows.append(str(f))
    head = [
        "# tools/dangling_floor.txt — the dangling references still open when check_dangling_references.py shipped.",
        "# RATCHET: this file may only shrink. One entry per line, `file:line:target`; an entry matches on file and",
        "# target (the line is where it was when recorded). Fix the sentence, then delete its line here.",
        f"# Written {measured}: {len(rows)} entries.",
    ]
    path.write_text("\n".join(head + rows) + "\n", encoding="utf-8")
    return len(rows)


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    """One mutant per reject class, each asserted individually; one pass per exemption."""
    import textwrap
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "tools").mkdir(); (root / "sdk").mkdir(); (root / "guardrails").mkdir()
        (root / "decisions").mkdir(); (root / "a").mkdir(); (root / "b").mkdir()
        (root / "ok.md").write_text("# ok\n", encoding="utf-8")
        (root / "a" / "base.py").write_text("", encoding="utf-8")
        (root / "b" / "base.py").write_text("", encoding="utf-8")
        (root / "decisions" / "old.md").write_text("---\nstatus: RETIRED — moved\n---\n# old\n", encoding="utf-8")
        (root / "decisions" / "sup.md").write_text("**SUPERSEDED 2026-09-29 by x** \n# sup\n", encoding="utf-8")
        (root / "doc.md").write_text(textwrap.dedent("""\
            # doc
            M1 [broken](nope.md)
            M2 see `tools/nope.py`
            M3 see `ghost.yaml`
            M4 see `base.py`
            M5 [old](decisions/old.md)
            M5b `decisions/sup.md` is the record
            P1 `decisions/old.md` was retired → see ok.md
            P2 lives in `mac-platform/packages/x/y.py`
            P3 `tools/nope3.py` does not exist
            P4 the `.lookup.csv` fragment
            M6 [dir](nodir/)
            P5 [good](ok.md) and `ok.md` and [dir](decisions/)
            P9 `/decisions/old.md` was retired; `tools/t.py::main` and `a/base.py:3,7` and `sdk.connector.duckdb`
            ```
            P6 `tools/nope2.py` inside a fence
            ```
            """), encoding="utf-8")
        (root / "bundle.md").write_text("# b\n\nPaths: bundle-relative.\n\nP7 `master.yaml` and `data/x.yaml` and [x](acceptance/q.yaml)\nM7 `tools/nope6.py`\n", encoding="utf-8")
        (root / "tools" / "t.py").write_text('"""M8 see `tools/nope4.py` and [l](ok.md); P10 `master.yaml`"""\n', encoding="utf-8")
        (root / "sdk" / "connector").mkdir(); (root / "sdk" / "connector" / "duckdb.py").write_text("", encoding="utf-8")
        (root / "design.md").write_text("# d\n\n**DESIGNED, NOT ENFORCED.**\n\nP11 `tools/nope7.py` and `ghost2.yaml`\nM10 [x](nope8.md)\n", encoding="utf-8")
        (root / "guardrails" / "g.yaml").write_text("items:\n  - statement: M9 see `tools/nope5.py`\n    key: not-prose `tools/ignored.py`\n", encoding="utf-8")

        findings, unlocated, counts = scan(root)
        got = {(f.file, f.target, f.severity) for f in findings}
        unl = {(f.file, f.target, f.note) for f in unlocated}
        expect_err = [
            ("doc.md", "nope.md", "ERROR", "M1 broken link"),
            ("doc.md", "tools/nope.py", "ERROR", "M2 owned-root path"),
            ("doc.md", "ghost.yaml", "ERROR", "M3 unresolvable basename"),
            ("doc.md", "base.py", "WARNING", "M4 ambiguous basename"),
            ("doc.md", "decisions/old.md", "ERROR", "M5 retired target, unmarked link"),
            ("doc.md", "decisions/sup.md", "ERROR", "M5b superseded target, unmarked path"),
            ("doc.md", "nodir/", "ERROR", "M6 directory link"),
            ("bundle.md", "tools/nope6.py", "ERROR", "M7 owned-root path still judged in a bundle-relative file"),
            ("tools/t.py", "tools/nope4.py", "ERROR", "M8 tool docstring"),
            ("guardrails/g.yaml", "tools/nope5.py", "ERROR", "M9 guardrail prose field"),
            ("design.md", "nope8.md", "ERROR", "M10 a link is judged even under a designed-not-enforced banner"),
        ]
        expect_pass = [
            ("doc.md", "decisions/old.md", "P1 retired target on a line that says 'retired'/'was'/'→'"),
            ("doc.md", "mac-platform/packages/x/y.py", "P2 cross-repo"),
            ("doc.md", "tools/nope3.py", "P3 self-quoting"),
            ("doc.md", ".lookup.csv", "P4 leading-dot fragment"),
            ("doc.md", "ok.md", "P5 resolving link / basename / directory"),
            ("doc.md", "decisions/", "P5 directory link that exists"),
            ("doc.md", "tools/nope2.py", "P6 fenced"),
            ("bundle.md", "master.yaml", "P7 bundle-relative basename"),
            ("bundle.md", "acceptance/q.yaml", "P7 bundle-relative link"),
            ("guardrails/g.yaml", "tools/ignored.py", "P8 non-prose yaml field not judged"),
            ("doc.md", "/decisions/old.md", "P9 root-anchored path resolves from the root (and the line says 'retired')"),
            ("doc.md", "tools/t.py", "P9 ::symbol suffix stripped"),
            ("doc.md", "a/base.py", "P9 line list stripped"),
            ("doc.md", "sdk.connector.duckdb", "P9 module path not judged"),
            ("tools/t.py", "master.yaml", "P10 bare basename in a docstring is UNLOCATED (bundle)"),
            ("design.md", "tools/nope7.py", "P11 owned path under a designed-not-enforced banner is UNLOCATED (design)"),
            ("design.md", "ghost2.yaml", "P11 basename under a designed-not-enforced banner is UNLOCATED (design)"),
        ]
        bad = []
        for file, target, sev, why in expect_err:
            if (file, target, sev) not in got:
                bad.append(f"mutant NOT caught: {why} ({file} -> {target} expected {sev})")
        # P1 shares its target with M5 (different lines): assert the R4 error fires exactly once for old.md
        n_old = sum(1 for f in findings if f.file == "doc.md" and f.target == "decisions/old.md")
        if n_old != 1:
            bad.append(f"P1 marked retired citation was judged ({n_old} findings for decisions/old.md, expected 1 = M5 only)")
        for file, target, why in expect_pass:
            if target == "decisions/old.md":
                continue
            if any(f.file == file and f.target == target for f in findings):
                bad.append(f"exemption FAILED: {why} ({file} -> {target} was reported)")
        if ("doc.md", "mac-platform/packages/x/y.py", "cross-repo") not in unl:
            bad.append("P2 cross-repo target not listed as UNLOCATED")
        if ("bundle.md", "master.yaml", "bundle") not in unl:
            bad.append("P7 bundle basename not listed as UNLOCATED (bundle)")
        if ("tools/t.py", "master.yaml", "bundle") not in unl:
            bad.append("P10 docstring basename not listed as UNLOCATED (bundle)")
        if ("design.md", "tools/nope7.py", "design") not in unl or ("design.md", "ghost2.yaml", "design") not in unl:
            bad.append("P11 design-banner targets not listed as UNLOCATED (design)")
        # the ratchet: a baseline entry that no longer fires is STALE; a finding not in it is NEW
        bl = root / "floor.txt"
        errs = [f for f in findings if f.severity == "ERROR"]
        write_baseline(bl, errs, "self-test")
        base = read_baseline(bl)
        if set(base) != {f.key() for f in errs}:
            bad.append("baseline round-trip lost entries")
        base["doc.md:gone.md"] = "doc.md:1:gone.md"
        stale = [k for k in base if k not in {f.key() for f in errs}]
        if stale != ["doc.md:gone.md"]:
            bad.append("STALE detection failed")
        if bad:
            print("self-test FAILED:")
            for b in bad:
                print("  " + b)
            return 1
        print(f"self-test passed: {len(expect_err)} mutants caught (one per reject class), "
              f"{len(expect_pass)} exemptions honoured, ratchet STALE/NEW round-trip ok; "
              f"{counts['md']} md + {counts['py']} py + {counts['guardrails']} guardrail files, {counts['refs']} refs judged")
        return 0


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=str(ROOT))
    ap.add_argument("--baseline", default=str(BASELINE))
    ap.add_argument("--write-baseline", action="store_true", help="rewrite the floor; refuses to grow it")
    ap.add_argument("--list-unlocated", action="store_true", help="also print cross-repo / bundle targets")
    ap.add_argument("--all", action="store_true", help="print every finding, baseline included")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory")
        return 2
    findings, unlocated, counts = scan(root)
    if counts["md"] == 0:
        print(f"could not run: no markdown under {root} — nothing to judge is not a pass")
        return 2
    errors = [f for f in findings if f.severity == "ERROR"]
    warnings = [f for f in findings if f.severity == "WARNING"]
    denom = (f"{counts['md']} md + {counts['py']} py docstrings + {counts['guardrails']} guardrail files, "
             f"{counts['refs']} reference(s) judged")

    bl_path = Path(a.baseline)
    if a.write_baseline:
        old = read_baseline(bl_path)
        new_keys = {f.key() for f in errors}
        grown = sorted(new_keys - set(old)) if old else []
        if grown:
            print(f"REFUSED: --write-baseline would ADD {len(grown)} entr(y/ies); the floor only shrinks. Fix these first:")
            for k in grown:
                print("  " + k)
            return 1
        n = write_baseline(bl_path, errors, "2026-09-29" if not old else "ratchet")
        print(f"wrote {bl_path.relative_to(root) if bl_path.is_relative_to(root) else bl_path}: {n} entries ({denom})")
        return 0

    base = read_baseline(bl_path)
    current = defaultdict(list)
    for f in errors:
        current[f.key()].append(f)
    new = [fs[0] for k, fs in sorted(current.items()) if k not in base]
    stale = sorted(k for k in base if k not in current)

    for f in (errors if a.all else new):
        print(f"  [{f.severity}] {f}  ({f.rule}: {f.note})")
    for k in stale:
        print(f"  [STALE] {base[k]}  — no longer fires; delete it from {bl_path.name}")
    for w in warnings:
        print(f"  [WARNING] {w}  ({w.note})")
    if a.list_unlocated:
        for u in unlocated:
            print(f"  [UNLOCATED:{u.note}] {u}")

    accepted = len(current) - len(new)
    if new or stale:
        print(f"FAIL: check_dangling_references — {len(new)} new dangling reference(s) and {len(stale)} stale baseline entr(y/ies) "
              f"over {denom}; {accepted} of {len(base)} baseline entries still open, {len(warnings)} warning(s), "
              f"{len(unlocated)} unlocated (cross-repo/bundle)")
        return 1
    print(f"PASS: check_dangling_references — 0 new dangling reference(s) over {denom}; "
          f"baseline {len(base)} entr(y/ies) all still open (fix one, delete its line), {len(warnings)} warning(s), "
          f"{len(unlocated)} unlocated (cross-repo/bundle)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
