"""The gate contract, in one place: a verdict line, a denominator, and a mutant per reject class.

WHY THIS EXISTS. A review of this estate measured its 41 gates against the contract CORE.md §2
states. The eight in this package scored: **0 with a `--self-test`, 0 with any exit-2 path**, three
printing no denominator, two with no `argparse` at all. A gate with no mutant is a gate nobody has
tested; a gate that prints a numerator with no denominator cannot be read; and a gate with no
could-not-run path must express "I could not judge" as either PASS or FAIL, both of which are lies.

"Did not run" is the one verdict a gate must never be able to give silently.

THE ONE CONSTRAINT THAT SHAPES THIS MODULE. Four of these gates are called as IN-PROCESS FUNCTIONS
by `sdk/cli/publish.py`:

    publish.py:82   if check_rule_lock.check(content_root / "ontology") != 0:
    publish.py:85   wp, _ = check_write_paths.check(repo)
    publish.py:88   if annotation_isolation.check(repo):
    publish.py:113  leaks = check_bundle_secrets.check(stage)

So a `check()` that returned 2 for "could not run" would be read by those callers as a FINDING:
"no lock armed yet" would arrive as "the lock has drifted". The reserved code is a property of the
PROCESS, so `could_not_run()` belongs to `main()` alone and `check()` keeps its existing return
shape. That is why this module offers `verdict()` and `could_not_run()` separately rather than one
wrapper that does both.

Each gate keeps its own `check()`. What it gains here is a uniform way to SAY what it found.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Outcome:
    """What a gate found, and over what. The denominator is not optional."""

    findings: int
    examined: int
    unit: str = "file(s)"

    @property
    def clean(self) -> bool:
        return self.findings == 0


def verdict(name: str, outcome: Outcome, *, detail: str = "") -> tuple[str, int]:
    """The one line a gate prints, and the code it exits with.

    An examined count of zero is NOT a pass. A gate that measured nothing has not established that
    the tree is clean, it has established that it could not look -- which is exit 2's job.
    """
    tail = f" — {detail}" if detail else ""
    if outcome.examined == 0:
        return (
            f"could not run: {name} examined 0 {outcome.unit}, which is not the same as "
            f"clean{tail}",
            2,
        )
    if outcome.clean:
        return (
            f"PASS: {name} — 0 violation(s) over {outcome.examined} {outcome.unit} examined{tail}",
            0,
        )
    return (
        f"FAIL: {name} — {outcome.findings} violation(s) over {outcome.examined} "
        f"{outcome.unit} examined{tail}",
        1,
    )


def could_not_run(name: str, why: str) -> int:
    """Exit 2, from `main()` only. Never from `check()` -- see the module docstring."""
    print(f"could not run: {name} — {why}", file=sys.stderr)
    return 2


# -------------------------------------------------------------------------------------------------
# the self-test harness
# -------------------------------------------------------------------------------------------------

#: A seeder writes one reject class into a fixture tree. It returns the path it wrote, so the
#: harness can assert the mutant ACTUALLY MUTATED -- a self-test in this estate once passed because
#: the token it planted was already absent, which is a pass for the wrong reason.
Seeder = Callable[[Path], Path]


@dataclass
class GateContract:
    """Everything needed to prove one gate rejects what it claims to reject."""

    name: str
    #: builds the clean fixture; must produce a tree the gate examines and finds nothing in
    clean: Callable[[Path], None]
    #: reject class -> seeder
    mutants: Mapping[str, Seeder]
    #: runs the gate over a fixture root and reports what it found
    run: Callable[[Path], Outcome]
    #: optional: extra assertions that must hold, name -> callable returning an error string or ""
    extra: Mapping[str, Callable[[Path], str]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.extra is None:
            object.__setattr__(self, "extra", {})


def _git_init(root: Path) -> bool:
    if shutil.which("git") is None:
        return False
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
    return True


def run_self_test(contract: GateContract, *, needs_git: bool = False) -> int:
    """Seed the clean fixture and every mutant; assert each is rejected AS ITS OWN CLASS."""
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        if needs_git and not _git_init(base):
            print(f"could not run: {contract.name} self-test — git is required", file=sys.stderr)
            return 2

        # 1 - the clean fixture must pass, over a NON-ZERO denominator.
        clean_root = base / "clean"
        clean_root.mkdir(parents=True, exist_ok=True)
        contract.clean(clean_root)
        if needs_git:
            _git_init(clean_root)
            subprocess.run(["git", "-C", str(clean_root), "add", "-A"], check=True)
        out = contract.run(clean_root)
        if out.examined == 0:
            failures.append("clean fixture examined 0 — a pass over nothing")
        if not out.clean:
            failures.append(f"clean fixture produced {out.findings} finding(s)")

        # 2 - every mutant must be rejected, and must really have been written.
        for cls, seed in contract.mutants.items():
            root = base / cls
            root.mkdir(parents=True, exist_ok=True)
            contract.clean(root)
            written = seed(root)
            if not Path(written).exists():
                failures.append(f"mutant {cls!r} did not write {written} — it did not mutate")
                continue
            if needs_git:
                _git_init(root)
                subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            out = contract.run(root)
            if out.clean:
                failures.append(f"mutant not caught: {cls}")

        # 3 - any extra property the gate claims.
        for label, assertion in contract.extra.items():
            err = assertion(base)
            if err:
                failures.append(f"{label}: {err}")

    total = 2 + len(contract.mutants) + len(contract.extra)
    if failures:
        print(f"FAIL: {contract.name} self-test — {len(failures)} of {total} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    print(
        f"PASS: {contract.name} self-test — {total}/{total} "
        f"({len(contract.mutants)} mutant(s) rejected as their own class, clean fixture passes "
        f"over a non-zero denominator, every mutant proved to have mutated)"
    )
    return 0


def write(path: Path, text: str) -> Path:
    """Seeder helper: write a file, creating parents. Returns the path, for the mutation assertion."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def env_root(var: str, default: Path) -> Path:
    v = os.environ.get(var)
    return Path(v) if v else default
