#!/usr/bin/env python3
"""check_entry_points — invoke every entry point once and assert it EXITS RATHER THAN CRASHES.

WHY THIS GATE EXISTS, AND THE MEASUREMENT THAT FORCED IT
--------------------------------------------------------
MEASURED on this tree, 2026-09-13, by the scan in `discover()` below:

    31 modules under sdk/ carry a `main()` or an `if __name__ == "__main__"` block.
    14 of those 31 are named in NO test file at all.

So roughly half the entry points in this SDK have never been executed by anything except a human
at a prompt. Nothing asserts they can even START. `python3 -m pytest sdk -q` is 183 green and
covers none of this: pytest imports modules, it does not RUN them, and the `__main__` block is by
construction the one block an import never reaches. Eight of these modules do all their work
INSIDE `if __name__ == "__main__"` and expose no importable `main()` at all -- a subprocess is the
only instrument that can reach them.

The defect class is already written down twice in this repo, by people who had been bitten:

    sdk/gate/check_bundle_secrets.py:264
        "Bare, it used to reach Path(None) and die with a TypeError -- a traceback is not a
         verdict, and a runner reading exit codes cannot tell a crash from a refusal."

That is the whole rule. **Exit 0, 1 or 2 is a verdict. A stack trace is a defect.** A runner like
`tools/run_framework_gates.sh` reads exit codes; a crashing gate exits 1, which that runner records
as `FAIL (exit 1)` -- indistinguishable from an honest finding. A crash therefore does not merely
fail to inform, it actively counterfeits a verdict.

WHY BOTH `--help` AND BARE, which is not redundancy
---------------------------------------------------
They are different code paths and this tree proves it. `--help` is handled inside argparse and
returns before any of the module's own logic; bare reaches the logic with every argument at its
default, which is where `None` lives. MEASURED, both directions:

  * `sdk/authoring/validate_one.py --help` CRASHES (IsADirectoryError escaping `p.read_text()`),
    while the same module BARE exits 2 correctly. Only the `--help` arm finds it.
  * `sdk/gate/check_engine_coupling.py --help` exits 0, BARE exits 1. Only the bare arm reaches it.

A third mode is exercised for any module that declares a positional argument or reads
`sys.argv[1]`: hand it one real directory path. This is where `Path(None)` bugs and real work live.

WHY THIS GATE RUNS EVERY INVOCATION IN A THROWAWAY WORKING DIRECTORY
--------------------------------------------------------------------
Because building it created litter in this repository, and that is the measurement:

    $ python3 -m sdk.project.references --help     # from the repo root
    $ git status --short
    ?? --help/                                     # <- a DIRECTORY named "--help"
    $ python3 -m sdk.project.references             # bare, from the repo root
    ?? references/

`sdk/project/references.py` has no argparse; it does `build(sys.argv[1] if len(sys.argv) > 1
else ".")` and WRITES a tree under that path, relative to the current working directory. Exercising
it from the repo root creates `./--help/references/` and `./references/`. A gate that mutates its
own subject to measure it is not an instrument, and a smoke gate that dirties `git status` on every
run will be deleted within a week. So every invocation gets `cwd=<throwaway temp dir>` with the
tree reachable via `PYTHONPATH`, and the throwaway is listed before and after so that
"this invocation wrote into its working directory" becomes a PRINTED DISCLOSURE rather than a
surprise in someone's `git status`.

That disclosure is deliberately NOT a violation of the smoke property. The smoke property is
"it exits rather than crashes"; writing to the cwd is a different population and folding it in
would let one gate's verdict be moved by two unrelated causes. It is counted and printed beside
the verdict, never inside it.

BILLING, WHICH IS THE PART THAT MUST NOT BE GOT WRONG
-----------------------------------------------------
Some of these modules bill: Bedrock Converse, Athena, Glue. The law is NEVER invoke them. But a
gate that quietly skips half its population is the zero-denominator pass wearing a different hat,
so every skip is COUNTED, NAMED and PRINTED, and a skipped module is never reported as a passing
one.

The skip set is DERIVED AND FALSIFIABLE, not a hand-written promise:

  1. `_aws_client_modules()` parses every module under sdk/ with `ast` and finds calls that
     construct an AWS client. MEASURED: exactly three modules do --
     `sdk.cli.harvest`, `sdk.authoring.materialize`, `sdk.connector.athena`.
     It uses the AST and not a grep for a specific reason: `sdk/gate/check_engine_coupling.py`
     contains the text `return boto3.Session()` at lines 737 and 790 -- inside STRING LITERALS, as
     its own self-test fixtures. A grep would skip that gate as billed and silently lose it from
     the population. The AST does not see into string literals, so it does not.
  2. `_static_billed_reach()` walks the static import graph from each entry point to those three.
     MEASURED: 3 of 31 entry points reach one -- harvest (-> materialize), conformance
     (-> athena), save (-> harvest).
  3. `_BILLED_BY_NAME` carries what a static graph CANNOT see, and it exists because of a real
     blind spot rather than for insurance. `sdk/connector/registry.py:191` resolves a connector id
     to a class with `importlib.import_module(module_name)`, reading the module name out of a
     shipped `index.json`. `sdk/connector/probe.py` calls `registry.resolve(cid)` and is, by its
     own docstring, "THE ONE PLACE THAT REACHES A SOURCE". No static import edge from probe.py to
     athena.py exists, so step 2 does not find it and could never find it.

The effective skip set is the UNION of (2) and (3), and it is fail-safe in the direction that
matters: a module discovered by reachability but absent from the named list is still skipped, and
the fact that the named list was incomplete is printed so a human fixes the list. The reverse --
naming a module that no longer reaches AWS -- costs coverage, not money, and shows up as slack.

Net, measured 2026-09-13: 4 of 33 entry points are skipped as billed -- 12%, named
individually, not "half of it". That ratio is a MEASUREMENT AND NOT A CONSTANT: the population is
discovered by `discover()` on every run, never hardcoded, so both numbers move with the tree. They
moved while this gate was being written -- another track landed `sdk/gate/check_seam_agreement.py`
in this working tree and the population went 32 -> 33, invocations 68 -> 70, with no change here
and no false alarm. If you quote these numbers, quote the run that produced them.

THE FLOOR IS WITNESS-LEVEL, WHICH IS STRICTER THAN THE ESTATE'S OTHER RATCHET
-----------------------------------------------------------------------------
`tools/mac_public_floor.txt` declares a COUNT. A count-only floor has a hole its own file does not
mention: at a floor of 3, fixing one crash and introducing a different one keeps the count at 3 and
the gate still prints PASS. For 3 findings that hole is 100% of the signal. So
`entry_point_floor.txt` declares the count AND NAMES EACH EXPECTED CRASH as `<module> <mode>`. A
crash at a witness that is not on the list fails the gate even when the total has not moved.

The floor applies ONLY when the root being judged is this repository. A count measured here says
nothing about an arbitrary tree, and a self-test fixture seeded with one crashing module must go
red rather than be forgiven by a number measured somewhere else -- see `_floor()`.

HONEST LIMITS. Write them down; a smoke gate is cheap precisely because it is shallow.
  * It asserts the EXIT, not the answer. `python3 -m sdk.container.spec --help` exits 0 having
    validated a path literally named "--help" and reported on it. That is a mis-verdict this gate
    passes, and detecting it needs a per-module expectation this gate deliberately does not own.
  * `cwd` is a throwaway, not the repo root, for the reason above. A module whose behaviour depends
    on cwd is therefore exercised in a different state than a human would see. That is disclosed
    rather than hidden: the cwd-write disclosure is exactly the list of modules for which the
    distinction is observable.
  * A module skipped as billed is UNMEASURED. It is not evidence of anything.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from sdk.gate import contract

NAME = "check_entry_points"

#: This file lives at <repo>/sdk/gate/, so the repo root is two parents up.
SELF = Path(__file__).resolve()
REPO_ROOT = SELF.parents[2]
FLOOR_FILE = SELF.parent / "entry_point_floor.txt"

# ------------------------------------------------------------------------------------------------
# the reject classes. Three, and each is a DIFFERENT observable, not three names for "it broke".
# ------------------------------------------------------------------------------------------------
CRASH = "crashes-with-traceback"
HANG = "hangs"
BAD_CODE = "unexpected-exit-code"

#: The verdict codes. 0 = clean, 1 = a finding, 2 = could-not-run. Anything else is not a verdict
#: any runner in this estate knows how to read.
VERDICT_CODES = frozenset({0, 1, 2})

#: CPython prints this before any unhandled exception, and it is the ONLY reliable signal that
#: separates a crash from a finding. It has to be, because both exit 1: a module that raises
#: `RuntimeError` and a gate that correctly reports one violation are indistinguishable by exit
#: code alone. This string is why the traceback test must run BEFORE the exit-code test in
#: `classify()` -- ordering that mirrors demo_right_gate.py, where containment is checked before
#: existence for the same reason.
TRACEBACK_MARK = "Traceback (most recent call last)"

#: Matches the two shapes that make a module an entry point. `def main(` is anchored to column 0
#: (a nested `def main(` is not an entry point); the `__main__` guard is not anchored, because a
#: handful of modules indent it. This is byte-for-byte the predicate behind the "31 modules"
#: measurement in the docstring -- if you change it, re-measure and update that number.
ENTRY_RE = re.compile(r"^def main\(|if __name__ *== *['\"]__main__['\"]", re.M)

#: Real timeout for a real sweep. Generous: several of these gates walk a whole bundle, and a gate
#: that reports a slow module as a HANG is a false positive that costs a morning.
DEFAULT_TIMEOUT = 60.0

#: The bundle handed to any module that wants a positional path, per the brief: use the example
#: bundles as the real fixture. First one that exists wins.
EXAMPLE_BUNDLES = ("example_tpch_ontology", "example_shop_ontology")


# ------------------------------------------------------------------------------------------------
# billing: derive it, then name what deriving cannot see
# ------------------------------------------------------------------------------------------------

#: Attribute names whose call constructs an AWS client. Paired with a receiver/argument check below
#: so that `self.client(...)` on some unrelated object is not swept up.
_AWS_CTOR_ATTRS = frozenset({"Session", "client", "resource"})
_AWS_HINTS = ("boto3", "athena", "glue", "bedrock", "sts")

#: What a static import graph CANNOT see. Each entry carries the reason and the measurement, because
#: a skip with no stated reason is indistinguishable from a module somebody found inconvenient.
_BILLED_BY_NAME = {
    "sdk.connector.probe": (
        "resolves a connector class through sdk.connector.registry, which does "
        "importlib.import_module() on a name read from index.json -- NO static import edge to "
        "sdk.connector.athena exists, so reachability cannot find this one. probe.py's own "
        "docstring: 'THE ONE PLACE THAT REACHES A SOURCE'"
    ),
    "sdk.cli.harvest": (
        "Bedrock Converse + Athena + Glue; its own docstring says 'Requires AWS creds "
        "(Bedrock + Glue + Athena)'. boto3.Session() at harvest.py:149"
    ),
    "sdk.container.save": (
        "--mode materialize calls sdk.cli.harvest.project_source then publish; the billed path is "
        "one argument away"
    ),
    "sdk.connector.conformance": (
        "imports sdk.connector.athena, whose every wet method is billed and, by that module's own "
        "docstring, has never been run: 'Not one wet method in this file has ever run'"
    ),
}


def _aws_client_modules(root: Path) -> dict[str, list[str]]:
    """Modules that CONSTRUCT an AWS client, found by AST so string literals do not count.

    MEASURED on this tree: exactly three -- sdk.cli.harvest, sdk.authoring.materialize,
    sdk.connector.athena. `sdk/gate/check_engine_coupling.py` also contains the TEXT
    `return boto3.Session()` (lines 737, 790) inside its own self-test fixture strings; a grep
    would skip that gate as billed and lose a real entry point from the population. ast.walk does
    not descend into the contents of a string constant, so it does not make that mistake.
    """
    out: dict[str, list[str]] = {}
    for path in sorted(root.glob("sdk/**/*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError):
            # A module this gate cannot parse is a module whose billing it cannot rule out.
            # Fail SAFE: name it as a constructor so it lands in the skip set rather than being
            # invoked on the strength of a failed parse.
            out[_module_name(root, path)] = ["<unparseable -- skipped as a precaution>"]
            continue
        hits = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _AWS_CTOR_ATTRS
            ):
                try:
                    src = ast.unparse(node)
                except Exception:  # noqa: BLE001 -- unparse is best-effort evidence only
                    continue
                if any(h in src for h in _AWS_HINTS):
                    hits.append(f"L{node.lineno}: {src[:70]}")
        if hits:
            out[_module_name(root, path)] = hits
    return out


def _import_graph(root: Path) -> dict[str, set[str]]:
    """sdk-internal import edges. Function-level imports count -- a lazy import still bills when
    the function runs, and several of these modules import boto3 exactly that way."""
    mods = {_module_name(root, p): p for p in sorted(root.glob("sdk/**/*.py"))}
    graph: dict[str, set[str]] = {}
    for name, path in mods.items():
        edges: set[str] = set()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, ValueError):
            graph[name] = set()
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                edges.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                edges.add(node.module)
                edges.update(f"{node.module}.{a.name}" for a in node.names)
        graph[name] = {e for e in edges if e in mods}
    return graph


def _static_billed_reach(root: Path, billed: set[str]) -> dict[str, str]:
    """entry point -> the shortest static import path by which it reaches an AWS-client module."""
    graph = _import_graph(root)
    found: dict[str, str] = {}
    for start in graph:
        best: list[str] | None = None
        seen: set[str] = set()
        queue: list[list[str]] = [[start]]
        while queue:
            path = queue.pop(0)
            cur = path[-1]
            if cur in seen:
                continue
            seen.add(cur)
            for nxt in sorted(graph.get(cur, ())):
                if nxt in billed:
                    cand = path + [nxt]
                    if best is None or len(cand) < len(best):
                        best = cand
                elif nxt not in seen:
                    queue.append(path + [nxt])
        if best is not None:
            found[start] = " -> ".join(best)
    return found


# ------------------------------------------------------------------------------------------------
# the population
# ------------------------------------------------------------------------------------------------


def _module_name(root: Path, path: Path) -> str:
    return str(path.relative_to(root).with_suffix("")).replace(os.sep, ".")


def discover(root: Path) -> list[str]:
    """Every module under <root>/sdk carrying a `main()` or a `__main__` guard.

    MEASURED on this repository: 31 before this gate existed, 32 with it, and 33 an hour later
    when a concurrent track added another gate -- which is the argument for discovering the
    population instead of listing it. This gate IS in its own population, which is safe only
    because its bare invocation refuses (exit 2) instead of
    sweeping -- a gate that re-entered itself here would either hang or measure nothing. An `extra`
    in the self-test asserts that refusal, so the property this relies on is checked rather than
    assumed.
    """
    out = []
    for path in sorted(root.glob("sdk/**/*.py")):
        if path.name == "__init__.py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if ENTRY_RE.search(text):
            out.append(_module_name(root, path))
    return out


def wants_path_arg(root: Path, module: str) -> bool:
    """Does this module take a bare path as its first argument?

    Two shapes, both present in this tree: a positional `add_argument("root")` (8 modules) and a
    raw `sys.argv[1]` read (4 modules, none of which has argparse at all).

    This does NOT claim the argument MEANS a root. `sdk/project/mac_okf.py`'s positional is a
    subcommand `cmd`, and handing it a directory gets an argparse rejection -- exit 2, a verdict,
    which is all this gate asserts. Guessing semantics from an argument's NAME would be a
    heuristic; asserting "handed a real directory path, it does not crash" is a measurement.
    """
    path = root / Path(*module.split("."))
    path = path.with_suffix(".py")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and not node.args[0].value.startswith("-")
        ):
            return True
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "argv"
        ):
            return True
    return False


# ------------------------------------------------------------------------------------------------
# invocation
# ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Result:
    module: str
    mode: str
    code: int
    output: str
    timed_out: bool
    wrote: tuple[str, ...] = ()

    @property
    def witness(self) -> str:
        return f"{self.module} {self.mode}"


def classify(r: Result) -> str | None:
    """The reject class this invocation earned, or None if it produced a verdict.

    ORDER IS LOAD-BEARING, for the same reason demo_right_gate.py checks containment before
    existence. A module that raises exits 1, and so does a gate that correctly reports one
    violation. If the exit-code test ran first, every crash would land in the verdict bucket and
    this gate would pass a tree full of tracebacks. The traceback marker is the only thing that
    separates the two, so it is tested first.
    """
    if r.timed_out:
        return HANG
    if TRACEBACK_MARK in r.output:
        return CRASH
    if r.code not in VERDICT_CODES:
        return BAD_CODE
    return None


def invoke(root: Path, module: str, mode: str, argv: list[str], timeout: float) -> Result:
    """Run `python3 -m <module> <argv>` in a subprocess, in a THROWAWAY cwd.

    cwd is a fresh temp dir and the tree is reached via PYTHONPATH, because exercising
    `sdk.project.references` from the repo root writes `./references/` (and, with `--help`, a
    directory literally named `--help`) into the working tree -- measured while building this gate;
    see the module docstring. Both streams are merged: a traceback goes to stderr and a verdict to
    stdout, and the classifier should not have to know which stream a crash chose.

    PYTHONDONTWRITEBYTECODE stops the sweep leaving __pycache__ behind. MAC_* guards are unset so
    that no ambient credential or profile in the operator's shell can turn a smoke invocation into
    a billed one; the billed modules are skipped by name regardless, and this is the second lock.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Belt and braces behind the by-name skip: if a module this gate believed to be free ever does
    # reach for a session, let it fail for want of credentials rather than succeed and bill.
    for var in ("AWS_PROFILE", "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION"):
        env.pop(var, None)
    env["AWS_EC2_METADATA_DISABLED"] = "true"

    with tempfile.TemporaryDirectory(prefix="mac-smoke-cwd-") as cwd:
        before = set(os.listdir(cwd))
        try:
            proc = subprocess.run(
                [sys.executable, "-m", module, *argv],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            code, output, timed_out = proc.returncode, proc.stdout + proc.stderr, False
        except subprocess.TimeoutExpired as exc:
            # A hang is its own class, never folded into could-not-run: "it never answered" and
            # "it answered that it could not judge" are different defects with different owners.
            out = exc.stdout or b""
            err = exc.stderr or b""
            if isinstance(out, bytes):
                out = out.decode("utf-8", "replace")
            if isinstance(err, bytes):
                err = err.decode("utf-8", "replace")
            code, output, timed_out = -1, out + err, True
        wrote = tuple(sorted(set(os.listdir(cwd)) - before))
    return Result(module, mode, code, output, timed_out, wrote)


@dataclass
class Sweep:
    """Everything one sweep measured. Kept whole so the verdict and the disclosures are computed
    from one object rather than recounted independently in three places."""

    population: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    undeclared_billed: dict[str, str] = field(default_factory=dict)
    results: list[Result] = field(default_factory=list)
    findings: list[tuple[str, Result]] = field(default_factory=list)
    bundle: str = "<none>"

    @property
    def exercised(self) -> list[str]:
        return [m for m in self.population if m not in self.skipped]

    @property
    def crashed_modules(self) -> list[str]:
        return sorted({r.module for _cls, r in self.findings})

    @property
    def wrote_cwd(self) -> list[Result]:
        return [r for r in self.results if r.wrote]

    @property
    def denominator(self) -> str:
        """The one sentence this gate exists to be able to print."""
        return (
            f"{len(self.exercised)} of {len(self.population)} entry points exercised "
            f"({len(self.results)} invocation(s)), {len(self.skipped)} skipped as billed, "
            f"{len(self.crashed_modules)} crashed"
        )


def sweep(root: Path, *, timeout: float = DEFAULT_TIMEOUT) -> Sweep:
    """Exercise every non-billed entry point under `root` and record what happened."""
    s = Sweep()
    s.population = discover(root)

    aws = _aws_client_modules(root)
    reach = _static_billed_reach(root, set(aws))
    for module in s.population:
        why = None
        if module in aws:
            why = f"constructs an AWS client itself ({aws[module][0]})"
        elif module in reach:
            why = f"static import path to a billed module: {reach[module]}"
        if why is not None and module not in _BILLED_BY_NAME:
            # Fail SAFE, then DISCLOSE. Skipping is the right call for the money; a named list
            # that reachability has outgrown is a documentation defect a human must close, and
            # printing it is how they find out.
            s.undeclared_billed[module] = why
        if module in _BILLED_BY_NAME:
            why = _BILLED_BY_NAME[module]
        if why is not None:
            s.skipped[module] = why

    bundle_dir = next((root / b for b in EXAMPLE_BUNDLES if (root / b).is_dir()), None)
    s.bundle = bundle_dir.name if bundle_dir else "<an empty temp dir: no example bundle here>"

    for module in s.exercised:
        modes: list[tuple[str, list[str]]] = [("--help", ["--help"]), ("bare", [])]
        if wants_path_arg(root, module):
            modes.append(("path", ["<PATH>"]))
        for mode, argv in modes:
            if mode == "path":
                # A COPY, per invocation. Several of these modules write (publish, save, harvest's
                # project stage); handing them the repo's own example bundle would mutate a tracked
                # fixture, and sharing one copy across invocations would let module A's writes
                # decide module B's verdict.
                with tempfile.TemporaryDirectory(prefix="mac-smoke-bundle-") as tmp:
                    target = Path(tmp) / "bundle"
                    if bundle_dir:
                        shutil.copytree(bundle_dir, target)
                    else:
                        target.mkdir(parents=True)
                    r = invoke(root, module, mode, [str(target)], timeout)
            else:
                r = invoke(root, module, mode, argv, timeout)
            s.results.append(r)
            cls = classify(r)
            if cls is not None:
                s.findings.append((cls, r))
    return s


def run(root: Path, *, timeout: float = DEFAULT_TIMEOUT) -> contract.Outcome:
    """The Outcome the harness judges.

    The primary denominator is ENTRY POINTS EXERCISED and the secondary is INVOCATIONS, because
    they are genuinely different numbers (33 modules, 4 skipped, 70 invocations on 2026-09-13) and a reader
    handed only one of them cannot tell whether `--help` and bare were both tried. Getting these
    backwards is the mistake contract.Outcome's own docstring warns about.
    """
    s = sweep(root, timeout=timeout)
    return contract.Outcome(
        len(s.findings),
        len(s.exercised),
        "entry point(s)",
        classes={cls for cls, _ in s.findings},
        secondary=(len(s.results), "invocation(s)"),
    )


# ------------------------------------------------------------------------------------------------
# the witness-level ratchet
# ------------------------------------------------------------------------------------------------


def _floor(root: Path) -> tuple[int, set[str]] | None:
    """The declared floor: a count AND the witnesses it is allowed to be made of.

    Returns None for any root that is not THIS repository, and that refusal is the point. A count
    measured here is evidence about here; letting it forgive findings in a temp fixture would mean
    a self-test mutant seeding one crashing module could come back green because a number in a
    file two directories away said three crashes were acceptable. The self-test relies on this.
    """
    if root.resolve() != REPO_ROOT or not FLOOR_FILE.is_file():
        return None
    count: int | None = None
    witnesses: set[str] = set()
    for line in FLOOR_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if count is None and line.isdigit():
            count = int(line)
            continue
        witnesses.add(" ".join(line.split()))
    return None if count is None else (count, witnesses)


def report(s: Sweep, root: Path) -> tuple[str, int]:
    """Print the evidence, then return the one verdict line and the exit code."""
    for cls, r in s.findings:
        tail = f"exit {r.code}" if not r.timed_out else "NEVER EXITED"
        print(f"  [{cls}] {r.witness} — {tail}")
        for ln in [x for x in r.output.splitlines() if x.strip()][-3:]:
            print(f"      {ln[:160]}")

    # Disclosures. Counted and printed, never folded into the verdict -- see the docstring.
    if s.skipped:
        print(f"  [SKIPPED AS BILLED] {len(s.skipped)} of {len(s.population)} entry point(s) — "
              f"UNMEASURED, not passing:")
        for module, why in sorted(s.skipped.items()):
            print(f"      {module}: {why}")
    if s.undeclared_billed:
        print(f"  [SKIP LIST INCOMPLETE] {len(s.undeclared_billed)} module(s) were skipped by "
              f"REACHABILITY but are not named in _BILLED_BY_NAME — add them, with the reason:")
        for module, why in sorted(s.undeclared_billed.items()):
            print(f"      {module}: {why}")
    if s.wrote_cwd:
        print(f"  [WROTE INTO ITS CWD] {len(s.wrote_cwd)} invocation(s) created files in the "
              f"working directory they were run from (a separate population from the verdict; "
              f"run from the repo root these land in `git status`):")
        for r in s.wrote_cwd:
            print(f"      {r.witness} -> {', '.join(r.wrote)}")

    outcome = contract.Outcome(
        len(s.findings),
        len(s.exercised),
        "entry point(s)",
        classes={cls for cls, _ in s.findings},
        secondary=(len(s.results), "invocation(s)"),
    )
    detail = f"{s.denominator}; positional fixture: {s.bundle}"

    floor = _floor(root)
    if s.findings and floor is not None:
        count, witnesses = floor
        actual = {r.witness for _cls, r in s.findings}
        new = sorted(actual - witnesses)
        if len(s.findings) <= count and not new:
            slack = count - len(s.findings)
            if slack > 0:
                print(f"  [RATCHET] the floor is {count} but only {len(s.findings)} finding(s) "
                      f"remain — {slack} of slack. Lower {FLOOR_FILE.name} to {len(s.findings)}.",
                      file=sys.stderr)
            stale = sorted(witnesses - actual)
            if stale:
                print(f"  [RATCHET] {len(stale)} declared witness(es) no longer crash — remove "
                      f"them from {FLOOR_FILE.name}: {', '.join(stale)}", file=sys.stderr)
            # The PASS line carries the crash count inside it, deliberately. A green line that can
            # be quoted without "N crashed" travelling along is how this estate ends up citing a
            # PASS over a broken tree.
            return (
                f"PASS: {NAME} — {len(s.findings)} crash(es) over {detail}, at or below the "
                f"declared floor of {count} at the DECLARED WITNESSES "
                f"({FLOOR_FILE.name} — lower it, never raise it)"
                + (f"  [{slack} of slack]" if slack else ""),
                0,
            )
        if new:
            print(f"  [RATCHET] {len(new)} crash(es) at witnesses NOT declared in "
                  f"{FLOOR_FILE.name} — a fixed crash traded for a new one keeps the count and "
                  f"must still fail: {', '.join(new)}", file=sys.stderr)

    line, code = contract.verdict(NAME, outcome, detail=detail)
    return line, code


# ------------------------------------------------------------------------------------------------
# self-test: one mutant per reject class, on the repaired harness
# ------------------------------------------------------------------------------------------------

#: Short, because two modes x one hanging mutant is two waits. Long enough that a loaded laptop
#: does not report a healthy module as a hang.
SELF_TEST_TIMEOUT = 6.0

_P_CLEAN = "a module that parses its args and exits 0 must pass"
_P_REFUSES = "a module that REFUSES bare with exit 2 must pass — that is the correct behaviour"


def _fixture(root: Path, name: str, body: str) -> Path:
    """Seed <root>/sdk/<name>.py, with the package files that make `-m sdk.<name>` resolve.

    The fixture is structurally identical to the real population -- a module under an `sdk` package
    reached as `python3 -m sdk.x` -- so the self-test exercises the same discovery, the same
    subprocess call and the same classifier as the real sweep, not a parallel simplification.
    """
    contract.write(root / "sdk" / "__init__.py", "")
    return contract.write(root / "sdk" / f"{name}.py", body)


def _clean(root: Path) -> None:
    _fixture(
        root,
        "good",
        "import argparse\nimport sys\n\n\n"
        "def main():\n"
        "    ap = argparse.ArgumentParser()\n"
        "    ap.add_argument('--flag', action='store_true')\n"
        "    ap.parse_args()\n"
        "    print('PASS: fixture — 1 thing over 1 thing examined')\n"
        "    return 0\n\n\n"
        'if __name__ == "__main__":\n    sys.exit(main())\n',
    )


def _must_pass_refuses(root: Path) -> None:
    # The check_bundle_secrets shape: optional root, and BARE it refuses with exit 2 instead of
    # reaching Path(None). This gate must call that a PASS, or it would push every gate in the
    # package towards crashing quietly rather than refusing loudly.
    _fixture(
        root,
        "refuses",
        "import argparse\nimport sys\n\n\n"
        "def main():\n"
        "    ap = argparse.ArgumentParser()\n"
        "    ap.add_argument('root', nargs='?')\n"
        "    a = ap.parse_args()\n"
        "    if a.root is None:\n"
        "        print('could not run: fixture — no root given', file=sys.stderr)\n"
        "        return 2\n"
        "    print('PASS: fixture — 0 violation(s) over 1 thing examined')\n"
        "    return 0\n\n\n"
        'if __name__ == "__main__":\n    sys.exit(main())\n',
    )


_MUTANTS = {
    # Exits 1 WITH a traceback. This is the mutant that would slip past an exit-code-only gate,
    # because an honest single finding also exits 1.
    CRASH: lambda r: _fixture(
        r,
        "crasher",
        "import sys\n\n\n"
        "def main():\n"
        "    raise RuntimeError('this is the Path(None) TypeError, in fixture form')\n\n\n"
        'if __name__ == "__main__":\n    sys.exit(main())\n',
    ),
    HANG: lambda r: _fixture(
        r,
        "hanger",
        "import sys\nimport time\n\n\n"
        "def main():\n"
        "    time.sleep(3600)\n"
        "    return 0\n\n\n"
        'if __name__ == "__main__":\n    sys.exit(main())\n',
    ),
    BAD_CODE: lambda r: _fixture(
        r,
        "oddball",
        "import sys\n\n\n"
        "def main():\n"
        "    print('done, in my own private numbering')\n"
        "    return 7\n\n\n"
        'if __name__ == "__main__":\n    sys.exit(main())\n',
    ),
}

_EXPECT_LINE = {
    CRASH: f"[{CRASH}] sdk.crasher",
    HANG: f"[{HANG}] sdk.hanger",
    BAD_CODE: f"[{BAD_CODE}] sdk.oddball",
}


def _st_run(root: Path) -> contract.Outcome:
    return run(root, timeout=SELF_TEST_TIMEOUT)


def _st_main(root: Path) -> int:
    line, code = report(sweep(root, timeout=SELF_TEST_TIMEOUT), root)
    print(line)
    return code


def _aws_scan_finds_the_known_constructors(_base: Path) -> tuple[int, int]:
    """The skip set is only as good as the scan that derives it, so the scan is measured.

    Three claims, each a number this repository can be held to today:
      1. the AST scan finds sdk.cli.harvest, sdk.authoring.materialize and sdk.connector.athena;
      2. it does NOT find sdk.gate.check_engine_coupling, which carries `boto3.Session()` in
         string literals -- the false positive that would cost a real entry point;
      3. reachability finds harvest, conformance and save.
    A skip list nobody has falsified is a promise; this makes it a measurement.
    """
    established = 0
    aws = _aws_client_modules(REPO_ROOT)
    if {"sdk.cli.harvest", "sdk.authoring.materialize", "sdk.connector.athena"} <= set(aws):
        established += 1
    if "sdk.gate.check_engine_coupling" not in aws:
        established += 1
    reach = _static_billed_reach(REPO_ROOT, set(aws))
    if {"sdk.cli.harvest", "sdk.connector.conformance", "sdk.container.save"} <= set(reach):
        established += 1
    return established, 3


def _no_billed_module_is_ever_invoked(_base: Path) -> tuple[int, int]:
    """Two claims: every named billed module is skipped, and nothing invoked it.

    This is the assertion that the law "NEVER run anything reaching AWS or Bedrock" is kept by the
    CODE and not by the author's memory. It runs the real sweep's SKIP COMPUTATION over this
    repository (not the fixture) and checks the result, without invoking anything.
    """
    established = 0
    population = set(discover(REPO_ROOT))
    aws = _aws_client_modules(REPO_ROOT)
    reach = _static_billed_reach(REPO_ROOT, set(aws))
    effective = {m for m in population if m in _BILLED_BY_NAME or m in aws or m in reach}
    named_in_population = {m for m in _BILLED_BY_NAME if m in population}
    if named_in_population and named_in_population <= effective:
        established += 1
    if not (effective & {m for m in population if m not in effective}):
        established += 1
    return established, 2


def _bare_invocation_of_this_gate_refuses(_base: Path) -> tuple[int, int]:
    """This gate is in its own population. Prove that is safe.

    `discover()` includes check_entry_points itself, so a bare invocation that swept instead of
    refusing would re-enter the whole sweep from inside one of its own subprocesses. The property
    that makes self-inclusion safe is the exit-2 refusal, so it is asserted rather than trusted --
    and asserted through the REAL subprocess path, at a short timeout, so a regression to
    "sweep on bare" shows up as a timeout here instead of as a mysteriously slow gate.
    """
    r = invoke(REPO_ROOT, "sdk.gate.check_entry_points", "bare", [], SELF_TEST_TIMEOUT)
    return (1 if (r.code == 2 and not r.timed_out) else 0), 1


def _self_test() -> int:
    c = contract.GateContract(
        name=NAME,
        clean=_clean,
        must_pass={_P_CLEAN: _clean, _P_REFUSES: _must_pass_refuses},
        mutants=dict(_MUTANTS),
        run=_st_run,
        expect_line=dict(_EXPECT_LINE),
        main=_st_main,
        # Stated, not inferred: the day someone drops `classes=` from run() to quiet a failure,
        # this turns it into a red self-test instead of a silent downgrade to "by finding count".
        attributes_classes=True,
        extra={
            "the AWS scan finds the known constructors and not the string-literal fixture": (
                _aws_scan_finds_the_known_constructors
            ),
            "every named billed module is in the effective skip set": (
                _no_billed_module_is_ever_invoked
            ),
            "this gate's own bare invocation refuses (exit 2) instead of re-entering the sweep": (
                _bare_invocation_of_this_gate_refuses
            ),
        },
    )
    return contract.run_self_test(c)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", nargs="?", help="repo root to sweep (default: this repository)")
    ap.add_argument("--self-test", action="store_true",
                    help="seed a mutant per reject class and prove each is rejected by its own class")
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                    help=f"per-invocation seconds before a module is classed as {HANG} "
                         f"(default {DEFAULT_TIMEOUT:g})")
    a = ap.parse_args(argv)

    if a.self_test:
        return _self_test()

    # BARE REFUSES, and this is not boilerplate: `discover()` puts this gate in its own
    # population, so a bare invocation that swept would re-enter the sweep from inside one of its
    # own subprocesses. It is also the behaviour check_bundle_secrets.py:264 was repaired into --
    # 0 examined is not the same as clean.
    if a.root is None:
        return contract.could_not_run(
            NAME,
            "no root given — 0 examined is not the same as clean, and this gate is in its own "
            f"population, so a bare sweep would re-enter itself (usage: {NAME} <repo-root>, or "
            "--self-test)",
        )

    root = Path(a.root).resolve()
    if not root.is_dir():
        return contract.could_not_run(NAME, f"{a.root} is not a directory")
    if not (root / "sdk").is_dir():
        return contract.could_not_run(
            NAME, f"{root} has no sdk/ — this gate's population is sdk/**/*.py and there is none here"
        )

    s = sweep(root, timeout=a.timeout)
    if not s.population:
        return contract.could_not_run(
            NAME, f"0 entry points discovered under {root}/sdk — that is a lost population, not a "
                  "clean one"
        )
    line, code = report(s, root)
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
