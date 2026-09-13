#!/usr/bin/env python3
"""check_engine_coupling.py — the ENGINE-COUPLING RATCHET. It lands RED, on purpose.

WHY THIS GATE EXISTS, AND WHY IT IS NOT ALLOWED TO BE A NUMBER
--------------------------------------------------------------------------------------------------
The connector record (PROPOSED-2026-09-13, §10.4) asks for a ratchet over the coupling between this
framework and the warehouse engine it happens to answer from. The obvious instrument is a count with
a floor -- the idiom `tools/check_mac_public.py` already uses. That idiom was measured before it was
copied, and it does not hold:

  * `check_mac_public._floor()` returns the first `isdigit()` line as an **int**, and `:176` passes
    on `len(hits) <= floor`. "Lower it, never raise it" is a STRING INSIDE THE PASS LINE, enforced
    by nobody -- `grep -rn mac_public_floor` returns exactly one hit, the gate reading its own file.
  * A numeric floor is IDENTITY-BLIND. Fix one driver import and add another elsewhere in the same
    commit and the count is unchanged, so the gate is green over a tree that got no better.
  * That is not hypothetical here. The record's own staging **schedules exactly that move**: the
    `botocore` import is to be relocated out of `data_plane.py` into `harvest_model.py` on the model
    axis. Under a count, that is a free reduction. Under this gate it is a RELOCATION, and it fails.

So the floor is a **SET OF PATHS**, compared by identity, and moving coupling from a declared path to
an undeclared one is its own reject class: `coupling-relocated`.

WHY ONE UNIT IS NOT ENOUGH
--------------------------------------------------------------------------------------------------
Four import-shaped reject classes would have printed `4 -> 0` one day, and that `0` would have been
quoted as "MAC no longer knows the warehouse". Measured on this tree, on 2026-09-13, that quote would
have been false by thirteen files: **17 files under `sdk/` and `tools/` carry an engine noun** -- a
vendor product name in a string literal, in a model prompt, or as a PERSISTED EVIDENCE KEY written
into every acceptance document. The import-shaped gate imports none of them and would have seen none
of them.

A gate that reports one unit and lets a reader infer the other is the zero-denominator pass wearing a
different hat. So this gate carries TWO units, prints BOTH denominators in one verdict line, and
declares a separate path-set floor for each. They are lowered independently. They are two files for
that reason: one file with two sections invites lowering the cheap half and quoting the total.

WHAT WAS ACTUALLY MEASURED HERE, 2026-09-13 -- AND WHERE IT DISAGREES WITH THE RECORD
--------------------------------------------------------------------------------------------------
§10.4 predicts the false green as "a top-level-only import scan ... reports 2 today". Re-measured on
this tree with an AST walk that records nesting depth:

    module-level driver imports ................ 0
    function-local driver imports .............. 7   (sdk/cli/harvest.py:147, materialize.py:290,
                                                      materialize.py:312, data_plane.py:221,
                                                      data_plane.py:340, authoring.py:194,:335)
    distinct modules carrying them ............. 4   <- the floor set

**A module-level scan of this tree reports 0, not 2.** Every single driver import in this repository
is already inside a function. The record understated the defect: there is no top-level coupling left
to find, which is precisely why a scan that only reads `^import` would have shipped a clean bill of
health over seven live couplings. That measurement is the reason this gate walks the AST and counts
an import at ANY nesting depth.

The second unit reproduces the record's number exactly: **17 files**.

WHY THE VENDOR NOUNS ARE CONSTANTS IN THIS FILE AND NOT A GITIGNORED REGISTER
--------------------------------------------------------------------------------------------------
`sdk/registers.py` keeps `source_tokens` and `infra_handles` out of this public repository, because a
detector that names what it forbids is a register of those names, and those names are THE OPERATOR'S
IDENTITY -- one estate's dataset, one estate's bucket, one estate's SSO profile.

An engine product name is not that. It is the industry's, it is identical in every estate, and it is
already tracked in this repository in seventeen files. Two further reasons decide it:

  * **A floor set is only meaningful if it is reproducible.** Both floors are path sets measured
    against this vocabulary. Put the vocabulary in a gitignored file and a fresh clone measures a
    different set, which makes the ratchet unfalsifiable.
  * **The precedent is already here.** `check_host_coupling._is_gate_or_test` states the rule
    outright: "gates + tests legitimately NAME source tokens/handles (denylists, markers, fixtures)
    -- not host coupling." `tools/check_no_fabricated_identifiers.py` carries a dialect literal;
    `tools/_plugin.py` names an engine in its own fixture.

The consequence is that `sdk/gate/` is EXCLUDED from both units -- otherwise this file would be the
densest engine-noun concentration in the tree and would flag itself. That exclusion is a hole, so the
verdict line PRINTS it with its size rather than leaving a reader to discover it.

AND A PATH SET ALONE WAS STILL NOT ENOUGH -- MEASURED, NOT ARGUED
--------------------------------------------------------------------------------------------------
The first working version of this gate defined a relocation as "a declared path CLEARED and an
undeclared path APPEARED". That predicate was run against the exact move §10.4 schedules -- the
`botocore` import out of `data_plane.py` into `harvest_model.py` -- on a copy of this repository. It
FAILED the tree, correctly, and it labelled the finding `lazy-import-evasion`, because
`data_plane.py` does not clear: it still carries `chat.sql` at :221. A ratchet that catches the move
under the wrong name has lost most of what the name was for.

So each floor also declares a `STANDING:` count, and a relocation is "the path set GREW and the
total did NOT". That is the only form that sees a path giving up one of its two couplings. The
weaker predicate was then seeded back in as a mutation of this gate and it SURVIVED the self-test
until the clean fixture was rebuilt with two couplings in one file -- which is why the fixture has
that shape and why this paragraph exists.

MODES -- and why the default is the red one
--------------------------------------------------------------------------------------------------
  --mode debt (DEFAULT)  findings = EVERY driver coupling in the tree. Exit 1 while any exists.
                         This is the number that has to reach 0, and it is red today: 7 over 4 paths.
                         A gate that goes green on the day it lands has never been shown to reject
                         anything real (the `check_boundaries --mode legacy` precedent, :175).
  --mode ratchet         findings = REGRESSIONS ONLY -- coupling on a path outside the declared set,
                         a relocation, a shell-out, a dynamic import, a new engine-noun file. Exit 0
                         while the declared debt is merely unchanged. This is the mode CI can gate on
                         without pinning the build red forever, and it is the mode whose six reject
                         classes have seeded mutants.

The two modes print DIFFERENT NAMES in their verdict line -- `engine-coupling` and
`engine-coupling-ratchet` -- so that a green from the second can never be quoted as a green from the
first. Both modes print both units.

Offline, stdlib + AST only. Reaches no network and costs nothing.
Usage:  python3 -m sdk.gate.check_engine_coupling [ROOT] [--mode debt|ratchet]
        python3 -m sdk.gate.check_engine_coupling --self-test
Exit 0 = clean ; 1 = a finding ; 2 = could not run (no floor file, no owner, nothing examined).
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sdk.gate import contract  # noqa: E402

# --------------------------------------------------------------------------------------------------
# the vocabulary
# --------------------------------------------------------------------------------------------------

#: Importable driver / engine-client modules. Matched as a module name or a dotted PREFIX of one, so
#: `botocore.config` matches `botocore` and `chat.sql` matches itself. Prefix and not substring:
#: a substring rule would match `duckdb_fixtures` and the false positives would be argued about
#: instead of the coupling.
DRIVER_MODULES = (
    "boto3",
    "botocore",
    "duckdb",
    "pyathena",
    "trino",
    "presto",
    "snowflake",
    "psycopg2",
    "pymysql",
    "databricks",
    "google.cloud.bigquery",
    "sqlalchemy",
    # NOT a third-party driver: it is this estate's own engine CLIENT (`AthenaSQL`), living at
    # repo-root `services/chat/src`, imported lazily in two places. §10.4 counts both of those as
    # driver coupling and it is right to: an engine client built from a bundle's connection is the
    # same dependency as the SDK that builds it, and leaving it out would drop HALF the floor set.
    "chat.sql",
)

#: Binaries that are an engine reached WITHOUT an import. §10.4's live instance of this class is in
#: another repo -- `subprocess.run(["duckdb", ...])` -- and an import-only gate is blind to it, which
#: is the whole reason the class exists.
DRIVER_CLIS = ("duckdb", "athena", "trino", "snowsql", "psql", "sqlite3", "bq", "aws")

#: SECOND UNIT. Vendor product nouns, matched as case-insensitive SUBSTRINGS of the file text.
#:
#: Substring, and over the whole text rather than string literals only, for a measured reason: this
#: population includes `athena_ddl` (a function NAME), `botocore_config` (a PARAMETER name) and
#: `_new_athena_client`. A literal-only scan of this tree reports 13 files and calls the other four
#: clean; a `\b`-bounded scan cannot see `v_<engine>_kpi`. The trade is false positives on ordinary
#: English, which is why a noun-floor line may carry an inline `# why`.
ENGINE_NOUNS = (
    "athena",
    "trino",
    "presto",
    "duckdb",
    "redshift",
    "snowflake",
    "bigquery",
    "databricks",
    "boto3",
    "botocore",
    # An ordinary English word as well as a vendor service. Measured 2026-09-13: it adds ZERO files
    # to the population -- every file it matches is already matched by another noun -- so it is kept
    # for the day a file names only this one, and the inline-comment column on a floor line is where
    # a `glue code` false positive gets recorded WITH ITS REASON rather than argued away.
    "glue",
    "sqlite",
    "spark",
    "clickhouse",
    "teradata",
    "synapse",
)

_NOUN_RE = re.compile("|".join(re.escape(n) for n in ENGINE_NOUNS), re.IGNORECASE)

#: Where the two floors live, relative to the tree being judged -- NOT beside this module. A fixture
#: root seeds its own floor exactly the way the repository does, so the self-test exercises the real
#: loader instead of a stub, including its refusals.
DRIVER_FLOOR = "sdk/gate/engine_coupling_floor.txt"
NOUN_FLOOR = "sdk/gate/engine_noun_floor.txt"

#: Scanned for neither unit.
#:  * `sdk/connector/` is where a driver import is the POINT (§5). Forbidding it there would make the
#:    gate refuse the very deliverable the record is staging.
#:  * `sdk/gate/` is this gate's own home, and this gate names what it forbids. Its size is printed.
EXEMPT_PREFIXES = ("sdk/connector/", "sdk/gate/")

_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache", ".ruff_cache",
              "build", "dist", ".venv", "venv"}


def _is_gate_or_test(rel: str) -> bool:
    """A gate or a test may NAME an engine: that is the instrument, not the coupling.

    Same predicate as `check_host_coupling._is_gate_or_test`, restated rather than imported because
    that one takes a basename and this one has to see `tools/canon/__init__.py` as ordinary code.
    """
    base = rel.rsplit("/", 1)[-1]
    return (
        base.startswith(("check_", "test_"))
        or base.endswith("_test.py")
        or base == "conftest.py"
    )


# --------------------------------------------------------------------------------------------------
# the floor files
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Floor:
    paths: frozenset[str]
    why: dict[str, str]
    declared: str
    owner: str
    review_by: str
    #: How many couplings stood on those paths on the day the floor was declared. -1 = not declared.
    #:
    #: A PATH SET ALONE CANNOT SEE THE RELOCATION THE RECORD ACTUALLY SCHEDULES. Measured here, on
    #: this tree: move `botocore` out of `data_plane.py` into `harvest_model.py` and the source path
    #: does NOT clear -- it still carries `chat.sql` at :221 -- so a set-difference in both
    #: directions reports "one path added" and nothing lost. The gate still fails, but it fails as a
    #: NEW import rather than as the relocation it is, and the label is the whole point of the class.
    #: The standing count closes that: a path set that GREW while the total did NOT is a move.
    standing: int = -1


def load_floor(path: Path, *, requires_standing: bool = False) -> Floor | str:
    """The declared path set, or a string saying why this gate cannot judge.

    A FLOOR WITHOUT A DATE AND AN OWNER IS A PERMANENT EXEMPTION (§10.4, Risk 8). Every ratchet in
    this estate that lost its owner stopped being lowered; `mac_public_floor.txt`'s own comment block
    records a floor of 146 standing over a measurement of 4 -- "141 findings of silent headroom".
    So a floor file missing either header is refused with exit 2, not read with a shrug. Refusing to
    judge is a verdict; reading an ownerless exemption as a licence is not.
    """
    if not path.is_file():
        return f"no floor file at {path} — a ratchet with no declared set has nothing to ratchet"
    declared = owner = review = ""
    standing = -1
    paths: set[str] = set()
    why: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            body = line.lstrip("#").strip()
            for key, setter in (("DECLARED:", "declared"), ("OWNER:", "owner"),
                                ("REVIEW BY:", "review"), ("STANDING:", "standing")):
                if body.upper().startswith(key):
                    value = body[len(key):].strip()
                    if setter == "declared":
                        declared = value
                    elif setter == "owner":
                        owner = value
                    elif setter == "review":
                        review = value
                    elif value.split(" ")[0].isdigit():
                        standing = int(value.split(" ")[0])
            continue
        if not line:
            continue
        # `path  # why` — the inline column exists so a known false positive is recorded with its
        # reason, the way check_source_coupling.ALLOW does, instead of being silently tolerated.
        rel, _, reason = line.partition("#")
        rel = rel.strip()
        if rel:
            paths.add(rel)
            if reason.strip():
                why[rel] = reason.strip()
    if not declared or not owner:
        return (
            f"{path.name} declares "
            f"{'no DECLARED: date' if not declared else ''}"
            f"{' and ' if not declared and not owner else ''}"
            f"{'no OWNER:' if not owner else ''} — a floor with no date and no named owner is a "
            f"permanent exemption, and this gate will not enforce one (§10.4, Risk 8)"
        )
    if requires_standing and standing < 0:
        # Without it the gate cannot tell a MOVE from a GROWTH, and `coupling-relocated` -- the one
        # class this whole instrument was redesigned around -- silently degrades into the class
        # beneath it. Refusing is the only honest answer: the gate cannot make the distinction it
        # advertises.
        return (
            f"{path.name} declares no STANDING: count — without it a relocation is "
            f"indistinguishable from a new import, and `coupling-relocated` cannot be attributed"
        )
    return Floor(frozenset(paths), why, declared, owner, review, standing)


# --------------------------------------------------------------------------------------------------
# the scan
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    kind: str  # module-level | function-local | shell-out | dynamic
    path: str
    line: int
    what: str


@dataclass(frozen=True)
class Regression:
    cls: str
    line: str  # the printed witness, verbatim


def _candidates(root: Path) -> tuple[list[str], str]:
    """The files this gate is entitled to judge, and HOW it got the list.

    `git ls-files` first, for the same reason `check_mac_public._candidates` switched to it: a
    filesystem walk over this repository once put 311 of 611 findings in `build/`, half the reported
    debt being the gate reading its own build output. The fallback is disclosed in the verdict,
    because a gate that silently changes its denominator is worse than one with the wrong
    denominator.
    """
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files"],
                             capture_output=True, text=True, timeout=120)
        tracked = [ln for ln in out.stdout.splitlines() if ln.strip().endswith(".py")]
    except Exception:
        tracked = []
    if tracked:
        return sorted(tracked), "git ls-files"
    walked = sorted(
        str(p.relative_to(root)).replace("\\", "/")
        for p in root.rglob("*.py")
        if not (_SKIP_DIRS & set(p.relative_to(root).parts))
    )
    return walked, "filesystem walk (git listed nothing)"


def _in_scope(rel: str) -> bool:
    return (rel.startswith(("sdk/", "tools/"))
            and not rel.startswith(EXEMPT_PREFIXES))


def _driver_for(module: str) -> str | None:
    for d in DRIVER_MODULES:
        if module == d or module.startswith(d + "."):
            return d
    return None


def _const_str(node: ast.AST) -> str | None:
    """Fold a string expression built from constants -- `"bo" + "to3"` included.

    §10.4's `dynamic-import` mutant is exactly that concatenation, and a gate reading only
    `ast.Constant` would call it clean. Anything not constant-foldable returns None: this gate
    reports what it can prove, and an unprovable dynamic import is a blind spot, not a finding.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _const_str(node.left), _const_str(node.right)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):  # f-string of constants only
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                return None
        return "".join(parts)
    return None


def _first_word(node: ast.AST) -> str | None:
    """The command a subprocess call actually runs: argv[0] of a list, or word 0 of a string."""
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        return _const_str(node.elts[0])
    text = _const_str(node)
    if text:
        return text.strip().split()[0].rsplit("/", 1)[-1] if text.strip() else None
    return None


def _scan_file(rel: str, src: str) -> list[Finding]:
    """Every driver coupling in one module, with the nesting depth that makes it visible or not."""
    found: list[Finding] = []
    tree = ast.parse(src)

    # Nesting is FUNCTION/CLASS scope only. An import inside a module-level `try: ... except
    # ImportError:` is still module level -- a `^import` regex can see it, and calling it "lazy"
    # would put the two classes on one predicate.
    stack: list[tuple[ast.AST, int]] = [(tree, 0)]
    while stack:
        node, depth = stack.pop()
        child_depth = depth + 1 if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) else depth
        for child in ast.iter_child_nodes(node):
            stack.append((child, child_depth))
        if node is tree:
            continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                drv = _driver_for(alias.name)
                if drv:
                    found.append(Finding(
                        "module-level" if depth == 0 else "function-local", rel, node.lineno, drv))
        elif isinstance(node, ast.ImportFrom):
            drv = _driver_for(node.module or "")
            if drv:
                found.append(Finding(
                    "module-level" if depth == 0 else "function-local", rel, node.lineno, drv))
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name in ("import_module", "__import__") and node.args:
                target = _const_str(node.args[0])
                drv = _driver_for(target) if target else None
                if drv:
                    found.append(Finding("dynamic", rel, node.lineno, drv))
            elif name in ("run", "Popen", "call", "check_output", "check_call", "system") and node.args:
                cmd = _first_word(node.args[0])
                if cmd in DRIVER_CLIS:
                    found.append(Finding("shell-out", rel, node.lineno, cmd))
    return found


@dataclass
class Report:
    findings: list[Finding]
    driver_paths: frozenset[str]
    driver_examined: int
    unparsable: list[str]
    noun_files: dict[str, list[str]]
    noun_examined: int
    exempt: int
    source: str


def scan(root: Path) -> Report:
    rels, source = _candidates(root)
    findings: list[Finding] = []
    unparsable: list[str] = []
    driver_examined = 0
    noun_files: dict[str, list[str]] = {}
    noun_examined = 0
    exempt = 0

    for rel in rels:
        if rel.startswith(EXEMPT_PREFIXES):
            exempt += 1
            continue
        if not _in_scope(rel):
            continue
        try:
            src = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            unparsable.append(rel)
            continue

        # UNIT 1 keeps tests IN. A test that constructs a live engine client is coupling that costs
        # real money; measured on this tree, none do (they stub via `sys.modules`), so including
        # them costs nothing and closes the obvious hiding place.
        try:
            findings.extend(_scan_file(rel, src))
            driver_examined += 1
        except SyntaxError:
            unparsable.append(rel)
            continue

        # UNIT 2 leaves gates and tests OUT -- naming an engine is what a fixture and a denylist are
        # FOR. Different exclusions from unit 1, which is why both denominators are printed: read
        # them as one population and the second unit looks 47 files smaller than it is.
        if _is_gate_or_test(rel):
            continue
        noun_examined += 1
        hits = sorted({m.group(0).lower() for m in _NOUN_RE.finditer(src)})
        if hits:
            noun_files[rel] = hits

    return Report(
        findings=findings,
        driver_paths=frozenset(f.path for f in findings),
        driver_examined=driver_examined,
        unparsable=unparsable,
        noun_files=noun_files,
        noun_examined=noun_examined,
        exempt=exempt,
        source=source,
    )


# --------------------------------------------------------------------------------------------------
# attribution: which findings are a REGRESSION, and under which class
# --------------------------------------------------------------------------------------------------

_KIND_CLASS = {
    "module-level": "engine-import-outside-connector",
    "function-local": "lazy-import-evasion",
    "shell-out": "shell-out",
    "dynamic": "dynamic-import",
}

_KIND_NOTE = {
    "module-level": "at module level — outside the declared floor set",
    "function-local": "inside a function — invisible to a module-level scan, and counted here anyway",
    "shell-out": "as a subprocess — coupling with no import at all",
    "dynamic": "under a name assembled at runtime",
}


def regressions(rep: Report, floor: Floor, noun_floor: Floor) -> list[Regression]:
    """The findings that are NEW, each attributed to exactly one class.

    PRECEDENCE IS DELIBERATE AND IT IS THE POINT OF THE A0 HARNESS. Three of these classes overlap
    on the same file if they are written as independent predicates, and the harness now refuses that
    ("one mutation must trip one class, or two labels are sharing one predicate"):

      1. A RELOCATION is also a new file carrying an import. If both fired, a relocation would be
         reported twice and the `coupling-relocated` mutant would fail attribution. The relocation
         label wins, because it is the one that refuses the false green: the coupling MOVED, and a
         count cannot tell that from progress.

         A relocation is "the path set grew and the TOTAL did not". The first draft of this function
         asked instead for a path to have CLEARED, and that was measured wrong on this very tree:
         relocating `botocore` out of `data_plane.py` leaves `chat.sql` behind at :221, so nothing
         clears and the record's own scheduled move was labelled `lazy-import-evasion`. It still
         failed -- but with the wrong name on it, which for a ratchet is most of the damage.
      2. A file carrying a driver import almost always carries the driver's NAME, so the noun unit
         would double-report every driver regression. The noun class is therefore suppressed for a
         path already attributed to a driver class -- in the CLASS only. The printed COUNT of engine
         -noun files still includes them, because 17 is the honest size of that population.

    A path that DROPS out of a floor set with nothing gaining it is not a finding at all. It is a
    win, and it is printed as a ratchet instruction to lower the file.
    """
    out: list[Regression] = []
    cleared = sorted(floor.paths - rep.driver_paths)
    added = sorted(rep.driver_paths - floor.paths)
    relocating = bool(added) and len(rep.findings) <= floor.standing

    for path in added:
        for f in sorted((x for x in rep.findings if x.path == path), key=lambda x: x.line):
            if relocating:
                lost = ", ".join(cleared) if cleared else "no path cleared"
                out.append(Regression("coupling-relocated", (
                    f"  [coupling-relocated] {f.path}:{f.line} now imports `{f.what}`, while the "
                    f"total stands at {len(rep.findings)} against a declared {floor.standing} "
                    f"({lost}) — a relocation is not a reduction")))
            else:
                out.append(Regression(_KIND_CLASS[f.kind], (
                    f"  [{_KIND_CLASS[f.kind]}] {f.path}:{f.line} reaches `{f.what}` "
                    f"{_KIND_NOTE[f.kind]}")))

    driver_regressed = {r.line.split("] ", 1)[1].split(":", 1)[0] for r in out}
    for path in sorted(set(rep.noun_files) - noun_floor.paths):
        if path in driver_regressed:
            continue  # see precedence rule 2
        out.append(Regression("engine-noun-in-the-instrument", (
            f"  [engine-noun-in-the-instrument] {path} names "
            f"{', '.join('`' + n + '`' for n in rep.noun_files[path])} and is not in the noun "
            f"floor set")))
    return out


# --------------------------------------------------------------------------------------------------
# the verdict
# --------------------------------------------------------------------------------------------------


def check(root: Path, mode: str = "debt") -> tuple[contract.Outcome, str, list[str]]:
    """(outcome, detail, printed witnesses). Never returns 2 — see contract.py's module docstring."""
    rep = scan(root)
    floor = load_floor(root / DRIVER_FLOOR, requires_standing=True)
    # Unit 2 needs no STANDING: its unit IS the file, and a file is in the set or out of it. Stated
    # rather than left as an asymmetry a reader has to work out.
    noun_floor = load_floor(root / NOUN_FLOOR)
    if isinstance(floor, str) or isinstance(noun_floor, str):
        why = floor if isinstance(floor, str) else noun_floor
        return contract.Outcome(0, 0, "tracked .py file(s)"), why, []

    regs = regressions(rep, floor, noun_floor)
    lines = [r.line for r in regs]

    counts = {k: 0 for k in _KIND_CLASS}
    for f in rep.findings:
        counts[f.kind] += 1
    n_reloc = sum(1 for r in regs if r.cls == "coupling-relocated")

    cleared = sorted(floor.paths - rep.driver_paths)
    added = sorted(rep.driver_paths - floor.paths)

    # THE WITNESSES TRAVEL WITH THE VERDICT. `check_mac_public` printed its under-floor count alone
    # for months, so the debt the floor existed to make visible was the one thing the gate hid: a
    # reader had to import `scan()` to see what was still leaking. In debt mode the subject IS the
    # standing coupling, so every line of it is named.
    if mode == "debt":
        for f in sorted(rep.findings, key=lambda x: (x.path, x.line)):
            where = "AT FLOOR" if f.path in floor.paths else "OFF FLOOR"
            lines.append(f"  [{where}] {f.path}:{f.line} reaches `{f.what}` "
                         f"{_KIND_NOTE[f.kind]}")

    # THE DELTA, BETWEEN TWO SETS, never between two integers. §10.4 is explicit that the bare count
    # is what the record refuses: `4 -> 3 -> 1 -> 0` is only readable if each step names which path.
    lines.append(
        f"  DELTA vs the declared floor SET: {len(floor.paths)} → {len(rep.driver_paths)} path(s) "
        f"({len(cleared)} cleared, {len(added)} added); "
        f"STANDING {floor.standing} → {len(rep.findings)} coupling(s)")
    # Both floors' provenance, both printed. An exemption whose date and owner are not on screen
    # beside the verdict is an exemption nobody is going to go and read.
    lines.append(f"    unit 1 floor — declared {floor.declared}, review by "
                 f"{floor.review_by or 'NEVER (no expiry declared)'}, owner: {floor.owner}")
    lines.append(f"    unit 2 floor — declared {noun_floor.declared}, review by "
                 f"{noun_floor.review_by or 'NEVER (no expiry declared)'}, owner: "
                 f"{noun_floor.owner}")
    for path in cleared:
        lines.append(f"    [RATCHET] {path} no longer carries driver coupling — remove it from "
                     f"{Path(DRIVER_FLOOR).name}. Lower it, never raise it.")
    if len(rep.findings) < floor.standing:
        lines.append(f"    [RATCHET] {floor.standing - len(rep.findings)} coupling(s) gone since the "
                     f"floor was declared — lower STANDING in {Path(DRIVER_FLOOR).name} to "
                     f"{len(rep.findings)}. A floor above the measurement is silent headroom.")
    noun_cleared = sorted(noun_floor.paths - set(rep.noun_files))
    for path in noun_cleared:
        lines.append(f"    [RATCHET] {path} no longer names an engine — remove it from "
                     f"{Path(NOUN_FLOOR).name}. Lower it, never raise it.")
    if rep.unparsable:
        lines.append(f"    NOTE: {len(rep.unparsable)} file(s) could not be parsed — this gate is "
                     f"BLIND to them: {', '.join(rep.unparsable[:5])}")

    at_floor = sum(1 for f in rep.findings if f.path in floor.paths)
    head = (
        f"floor set of {len(floor.paths)} path(s) carrying {at_floor} driver coupling(s)\n"
        f"      — {counts['module-level']} module-level, {counts['function-local']} function-local, "
        f"{counts['shell-out']} shell-out, {counts['dynamic']} dynamic, {n_reloc} relocated\n"
        f"      — SECOND UNIT: {len(rep.noun_files)} file(s) carry an engine noun (string literal / "
        f"prompt / persisted key) over {rep.noun_examined} instrument file(s), noun floor set of "
        f"{len(noun_floor.paths)}\n"
        f"      — {rep.exempt} file(s) exempt ({', '.join(EXEMPT_PREFIXES)}) and never examined; "
        f"population from {rep.source}"
    )

    if mode == "debt":
        # RED ON PURPOSE. The subject is every coupling that exists, not merely the new ones.
        return (
            contract.Outcome(
                findings=len(rep.findings),
                examined=rep.driver_examined,
                unit="tracked .py file(s)",
                classes=frozenset(r.cls for r in regs),
                secondary=(rep.noun_examined, "instrument file(s) judged for an engine noun"),
            ),
            head,
            lines,
        )
    # RATCHET. A PASS here means "no WORSE", and the detail says so in the same breath, because a
    # bare `PASS: engine-coupling` is the exact sentence §10.4 exists to make unquotable.
    standing = (
        f"NO NEW coupling — the standing debt is UNCHANGED and it is NOT zero: "
        if not regs else ""
    )
    return (
        contract.Outcome(
            findings=len(regs),
            examined=rep.driver_examined,
            unit="tracked .py file(s)",
            classes=frozenset(r.cls for r in regs),
            secondary=(rep.noun_examined, "instrument file(s) judged for an engine noun"),
        ),
        standing + head,
        lines,
    )


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="the engine-coupling ratchet (§10.4)")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--mode", choices=["debt", "ratchet"], default="debt")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv[1:])
    if a.self_test:
        return _self_test()

    root = Path(a.root).resolve()
    name = "engine-coupling" if a.mode == "debt" else "engine-coupling-ratchet"
    if not root.is_dir():
        return contract.could_not_run(name, f"{root} is not a directory")

    outcome, detail, lines = check(root, a.mode)
    if outcome.examined == 0:
        # Either the floor file is missing/ownerless (detail says which) or nothing was examined.
        # Both are exit 2 and both are stated, because "did not run" is the one verdict a gate must
        # never be able to give silently.
        return contract.could_not_run(name, detail or "0 file(s) examined, which is not clean")
    for line in lines:
        print(line)
    text, code = contract.verdict(name, outcome, detail=detail)
    print(text)
    return code


# --------------------------------------------------------------------------------------------------
# self-test
# --------------------------------------------------------------------------------------------------

_HDR = "# DECLARED: 2026-09-13\n# OWNER: the self-test fixture\n# STANDING: 2\n"

#: The fixture's own coupled module. TWO function-local driver imports in ONE file, and both
#: decisions were forced by a measurement rather than chosen for realism:
#:
#:  * FUNCTION-LOCAL, because that is the only shape this repository actually has. A fixture built
#:    from module-level imports would never have walked a nested scope, and the false green §10.4
#:    names -- a top-level-only scan -- would have passed this gate's own self-test.
#:  * TWO OF THEM, because with one, `_relocate` empties the path, and a relocation predicate that
#:    only asks "did a path clear?" passes the self-test while being blind to the move the record
#:    actually schedules. That weaker predicate was seeded against this file and SURVIVED, until the
#:    fixture was changed to the shape that kills it: relocate one of two and nothing clears.
_FIXTURE_COUPLED = (
    "def client():\n"
    "    import boto3\n"
    "\n"
    "    return boto3.Session()\n"
    "\n"
    "\n"
    "def reader():\n"
    "    import duckdb\n"
    "\n"
    "    return duckdb.connect()\n"
)


def _clean(root: Path) -> None:
    """A tree AT ITS DECLARED FLOOR: real coupling, real engine nouns, all of it declared.

    This is the property that a mutant cannot express and that the whole ratchet rests on -- the
    declared debt, unchanged, is not a new violation. It is the clean fixture rather than a
    must_pass because `coupling-relocated` can only be seeded from a NON-EMPTY floor set: you cannot
    relocate coupling out of a tree that has none.
    """
    contract.write(root / "sdk/cli/engine_client.py", _FIXTURE_COUPLED)
    contract.write(root / "sdk/project/evidence.py", 'KEY = {"athena": True}\n')
    contract.write(root / "sdk/project/plain.py", "def add(a, b):\n    return a + b\n")
    contract.write(root / DRIVER_FLOOR, _HDR + "sdk/cli/engine_client.py\n")
    contract.write(root / NOUN_FLOOR,
                   _HDR + "sdk/cli/engine_client.py\nsdk/project/evidence.py\n")


def _run(root: Path) -> contract.Outcome:
    return check(root, "ratchet")[0]


def _main_ratchet(root: Path) -> int:
    return main(["check_engine_coupling", str(root), "--mode", "ratchet"])


def _relocate(root: Path) -> Path:
    """THE CLASS THIS GATE EXISTS FOR, seeded in the shape that is hardest to see.

    ONE of the declared path's TWO couplings leaves; it reappears in a file the floor does not name.
    The source path therefore does NOT clear -- it still carries the other one -- and the total is
    unchanged at 2. Both halves of the false green are live in that one mutation: a numeric floor
    calls it progress, and a set-difference floor calls it a new import under the wrong class.

    This is not a hypothetical shape. It is exactly what §10.4's staging schedules for `botocore`,
    and when it was run against this repository, `sdk/authoring/data_plane.py` kept `chat.sql` at
    :221 and did not clear.
    """
    (root / "sdk/cli/engine_client.py").write_text(
        "def client():\n    return None  # the import moved\n"
        "\n"
        "\n"
        "def reader():\n    import duckdb\n\n    return duckdb.connect()\n",
        encoding="utf-8")
    return contract.write(root / "sdk/authoring/moved.py",
                          "def client():\n    import boto3\n\n    return boto3.Session()\n")


def _connector_may(root: Path) -> None:
    """A driver import inside the connector package is the DELIVERABLE, not a violation (§5).

    Inexpressible as a mutant -- a mutant must be rejected -- and the clean fixture is already spoken
    for by the at-floor tree. A gate that rejected this would refuse the very package the record is
    staging, and it would be found out only after the package existed.
    """
    _clean(root)
    contract.write(root / "sdk/connector/duck.py", "import duckdb\n")


def _gate_and_test_may(root: Path) -> None:
    """A gate and a test may NAME an engine: a denylist and a fixture have to.

    This is the exclusion that lets THIS file exist. If it ever stops holding, this gate becomes the
    densest engine-noun file in the tree and flags itself, so it is asserted rather than assumed.
    """
    _clean(root)
    contract.write(root / "sdk/gate/check_thing.py", 'N = ("athena", "duckdb")\n')
    contract.write(root / "sdk/project/test_thing.py", 'ENG = "athena"\n')


def _debt_mode_is_red(base: Path) -> tuple[int, int]:
    """RED ON PURPOSE, asserted rather than claimed.

    Over the very fixture that the ratchet calls clean, the default mode must still exit 1 and must
    still name the standing debt. Without this, "it lands RED on purpose" is a sentence in a
    docstring that no test would notice the deletion of.
    """
    root = base / "clean"
    established = 0
    code, text = contract._capture(
        lambda r: main(["check_engine_coupling", str(r), "--mode", "debt"]), root)
    if code == 1:
        established += 1
    if "FAIL: engine-coupling —" in text and "floor set of 1 path(s)" in text and (
            "2 violation(s)" in text):
        established += 1
    return established, 2


def _ownerless_floor_is_refused(base: Path) -> tuple[int, int]:
    """A floor with no OWNER is a permanent exemption, and the gate must REFUSE it with exit 2.

    Exit 2 is not a formality here: a gate that reads an ownerless floor and enforces it has turned
    an undated exemption into a permanent one, which is Risk 8 in one line.
    """
    root = base / "_ownerless"
    root.mkdir(parents=True, exist_ok=True)
    _clean(root)
    contract.write(root / DRIVER_FLOOR,
                   "# DECLARED: 2026-09-13\n# STANDING: 1\nsdk/cli/engine_client.py\n")
    established = 0
    code, text = contract._capture(_main_ratchet, root)
    if code == 2:
        established += 1
    if "permanent exemption" in text:
        established += 1
    return established, 2


def _standingless_floor_is_refused(base: Path) -> tuple[int, int]:
    """A floor with a date and an owner but NO STANDING count must also be refused with exit 2.

    Seeded because the ownerless fixture did not cover it: dropping the STANDING requirement left
    this gate's self-test fully green while `coupling-relocated` silently degraded into the class
    beneath it. A requirement with no mutant is a requirement nobody has tested.
    """
    root = base / "_standingless"
    root.mkdir(parents=True, exist_ok=True)
    _clean(root)
    contract.write(root / DRIVER_FLOOR,
                   "# DECLARED: 2026-09-13\n# OWNER: the self-test fixture\n"
                   "sdk/cli/engine_client.py\n")
    established = 0
    code, text = contract._capture(_main_ratchet, root)
    if code == 2:
        established += 1
    if "cannot be attributed" in text:
        established += 1
    return established, 2


def _self_test() -> int:
    c = contract.GateContract(
        name="check_engine_coupling",
        clean=_clean,
        must_pass={
            "a driver import inside sdk/connector/ is the package's whole job": _connector_may,
            "a gate and a test may NAME an engine": _gate_and_test_may,
        },
        mutants={
            "engine-import-outside-connector": lambda r: contract.write(
                r / "sdk/cli/newmod.py", "import boto3\n\n\ndef s():\n    return boto3\n"),
            "lazy-import-evasion": lambda r: contract.write(
                r / "sdk/cli/lazymod.py", "def q():\n    import duckdb\n\n    return duckdb\n"),
            "shell-out": lambda r: contract.write(
                r / "sdk/cli/shellmod.py",
                "import subprocess\n\n\ndef q(sql):\n"
                "    return subprocess.run(['duckdb', '-c', sql])\n"),
            "dynamic-import": lambda r: contract.write(
                r / "sdk/cli/dynmod.py",
                "import importlib\n\n\ndef d():\n"
                "    return importlib.import_module('bo' + 'to3')\n"),
            "coupling-relocated": _relocate,
            "engine-noun-in-the-instrument": lambda r: contract.write(
                r / "sdk/project/newnoun.py", 'DIALECT = "trino"\n'),
        },
        run=_run,
        main=_main_ratchet,
        # Each fragment is the DISCLOSURE, never the class label: the label is already in the FAIL
        # line for free, so asserting it would assert nothing. These assert the sentence a reader
        # needs in order to act — which path lost the coupling, and why a count could not see it.
        expect_line={
            "engine-import-outside-connector": "at module level — outside the declared floor set",
            "lazy-import-evasion": "invisible to a module-level scan",
            "shell-out": "coupling with no import at all",
            "dynamic-import": "under a name assembled at runtime",
            "coupling-relocated": "a relocation is not a reduction",
            "engine-noun-in-the-instrument": "is not in the noun floor set",
        },
        extra={
            "the default mode lands RED over the very tree the ratchet calls clean":
                _debt_mode_is_red,
            "a floor with no OWNER is refused with exit 2": _ownerless_floor_is_refused,
            "a floor with no STANDING count is refused with exit 2":
                _standingless_floor_is_refused,
        },
        # Stated, not inferred: the day someone refactors `regressions()` and drops attribution,
        # this gate FAILS its own self-test instead of quietly scoring by finding count.
        attributes_classes=True,
    )
    return contract.run_self_test(c)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
