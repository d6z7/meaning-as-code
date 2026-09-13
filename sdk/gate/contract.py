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

--------------------------------------------------------------------------------------------------
STAGE A0 — WHAT THE HARNESS COULD NOT DO, MEASURED, AND WHAT WAS ADDED
--------------------------------------------------------------------------------------------------

An adversarial review built a passing-but-wrong gate on this tree and ran it. That gate declared
three reject classes, implemented NONE of them, and printed:

    PASS: demo-gate self-test — 7/7 (3 mutant(s) rejected as their own class, ...)

It is committed, at `sdk/gate/demo_wrong_gate.py`, and it now fails. Three defects produced that
line, and each addition below answers exactly one of them.

**Defect 1 — the harness could not attribute a finding to a reject class.** `Outcome` was
`(findings, examined, unit)` and the per-mutant assertion was `if out.clean: fail` — at least one
finding, FOR ANY REASON. Three mutants tripping one catch-all predicate scored three classes. The
concrete false green this permits: a gate with no realpath containment check still "passes"
`config-path-escapes-bundle`, because `../../outside/creds.yaml` also fails the `declared-missing`
predicate. -> `Outcome.classes`, and `run_self_test` asserts `cls in out.classes` AND that no other
class fired. Class attribution is what FORCES two labels to be two predicates.

**Defect 2 — a must-PASS fixture was structurally inexpressible.** `mutants` requires every entry to
be rejected, so "a bundle with no connection must still PASS" could not be a mutant; `clean` is a
single callable, so a gate's second clean fixture had nowhere to live. The overflow landed in
`extra`, checked as `err = assertion(base); if err: fail` — so **`lambda base: ""` passed** — and
counted into the printed denominator. Two no-op lambdas labelled with this estate's two
non-negotiable properties took that demo from 5/5 to 7/7. -> `must_pass`, seeded and judged like a
mutant but asserted clean; and `extra` now returns `(checked, total)` so a no-op reads as
`established 0 of 1` rather than as an assertion.

**Defect 3 — nothing read a gate's printed line or its exit code.** `run_self_test` called
`contract.run(root)` and read an `Outcome`. It never invoked `main()`, never captured stdout, never
checked an exit code — while at least seven guarantees in the connector record are ENTIRELY about
what gets printed: `profiled 0 of 14 relation(s)`; `SHOW TABLES: unavailable — collision check NOT
performed`; `[legacy basename allowlist ...]`; which permission default the host used; the coupling
delta; `class 4 examined 0 connector(s)`. Each is the difference between a disclosed degradation and
a silent one. -> `expect_line` (class -> required stdout fragment) and `GateContract.main`, with
stdout and the exit code captured per mutant.

EVERY ADDITION IS ADDITIVE AND EVERY NEW FIELD DEFAULTS EMPTY. The eight gates in this package were
not touched by stage A0 and all nine self-tests stay green. What changed for them is the PRINTED
LINE: a gate that attributes no class can no longer be described as rejecting "3 mutant(s) as their
own class", because that sentence was false for all eight. It now says `BY FINDING COUNT ONLY` and
names how many class labels are unverified. A harness that cannot check a property must say so
rather than print it.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Callable, Mapping
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Outcome:
    """What a gate found, and over what. The denominator is not optional.

    `classes` is the field that makes a self-test mean something: WHICH reject class fired, not
    merely that something did. It is empty by default, which is the honest report for the eight
    gates that predate stage A0 -- they detect, they do not attribute, and the self-test now prints
    that rather than claiming otherwise.

    `secondary` is the second denominator, for gates whose primary population and whose YARDSTICK
    are different things. The connection gate examines BUNDLES (primary, >= 1) but judges by
    CONNECTION DOCUMENTS VALIDATED (secondary). Getting these backwards turns a bundle that
    correctly declares no connection into a could-not-run.
    """

    findings: int
    examined: int
    unit: str = "file(s)"
    classes: frozenset[str] = frozenset()
    secondary: tuple[int, str] | None = None

    def __post_init__(self) -> None:
        # Gates will naturally hand this a set, a list or a single-class tuple. Normalising here
        # rather than at every call site keeps `classes` comparable with `==` in the harness, which
        # is how "no OTHER class fired" is asserted.
        if not isinstance(self.classes, frozenset):
            object.__setattr__(self, "classes", frozenset(self.classes or ()))

    @property
    def clean(self) -> bool:
        return self.findings == 0


def verdict(name: str, outcome: Outcome, *, detail: str = "") -> tuple[str, int]:
    """The one line a gate prints, and the code it exits with.

    An examined count of zero is NOT a pass. A gate that measured nothing has not established that
    the tree is clean, it has established that it could not look -- which is exit 2's job.

    A DECLARED SECONDARY OF ZERO IS ALSO NOT A PASS. If a gate says it judges by documents
    validated and validated none, it had no yardstick, whatever it did to the primary population.
    This rule is only safe because the population is arranged so the secondary can never be zero
    for a legitimate reason -- built-in fixtures are always in it -- and it is therefore zero
    exactly when the fixtures themselves are lost, which is precisely when exit 2 is right.

    Findings are never swallowed by that refusal: the count is carried into the exit-2 line, so a
    gate cannot lose a real violation by also losing its yardstick.

    The line is byte-identical to the pre-A0 line for any gate that declares neither `classes` nor
    `secondary`, which is all eight of the gates in this package.
    """
    tail = f" — {detail}" if detail else ""
    if outcome.examined == 0:
        return (
            f"could not run: {name} examined 0 {outcome.unit}, which is not the same as "
            f"clean{tail}",
            2,
        )
    second = ""
    if outcome.secondary is not None:
        n2, unit2 = outcome.secondary
        if n2 == 0:
            held = f" ({outcome.findings} finding(s) held, unjudged)" if outcome.findings else ""
            return (
                f"could not run: {name} — {outcome.examined} {outcome.unit} examined but 0 "
                f"{unit2}: the gate declared {unit2} as what it judges BY, so zero of them is a "
                f"missing yardstick, not a clean tree{held}{tail}",
                2,
            )
        second = f", {n2} {unit2}"
    if outcome.clean:
        return (
            f"PASS: {name} — 0 violation(s) over {outcome.examined} {outcome.unit} "
            f"examined{second}{tail}",
            0,
        )
    fired = f" [class(es): {', '.join(sorted(outcome.classes))}]" if outcome.classes else ""
    return (
        f"FAIL: {name} — {outcome.findings} violation(s) over {outcome.examined} "
        f"{outcome.unit} examined{second}{fired}{tail}",
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

#: An extra assertion, in one of two shapes. NEW: return `(established, claimed)` -- how many
#: properties it actually proved, out of how many it set out to prove. LEGACY: return an error
#: string, or "" for held. The legacy shape is still read because five of the eight gates in this
#: package use it and stage A0 was not allowed to touch them; it is never counted INTO the
#: denominator, because a `lambda base: ""` cannot prove it examined anything.
Extra = Callable[[Path], "tuple[int, int] | str"]


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
    #: optional: extra assertions; see `Extra` for the two shapes
    extra: Mapping[str, Extra] = None  # type: ignore[assignment]
    #: NEW: label -> fixture builder for trees that must come back CLEAN over a non-zero
    #: denominator. A mutant cannot express this (it requires rejection) and `clean` is a single
    #: callable, so before A0 these properties had nowhere to live but a no-op lambda in `extra`.
    must_pass: Mapping[str, Callable[[Path], None]] = None  # type: ignore[assignment]
    #: NEW: reject class -> a fragment that MUST appear in the gate's own stdout for that mutant.
    #: A disclosure nobody asserts is a disclosure that will be deleted by the next refactor.
    expect_line: Mapping[str, str] = None  # type: ignore[assignment]
    #: NEW: the gate's own `main()`, adapted to take a fixture root and return an exit code.
    #: Required whenever `expect_line` is declared -- you cannot assert a printed line without
    #: running the thing that prints it.
    main: Callable[[Path], int] | None = None
    #: NEW: force class attribution on (True) or off (False). Default None auto-detects; see
    #: `_attribution_enforced`. Set it to True in a new gate to make the requirement explicit and
    #: to fail loudly the day someone deletes the attribution from `run()`.
    attributes_classes: bool | None = None

    def __post_init__(self) -> None:
        for field in ("extra", "must_pass", "expect_line"):
            if getattr(self, field) is None:
                object.__setattr__(self, field, {})


def _git_init(root: Path) -> bool:
    if shutil.which("git") is None:
        return False
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
    return True


def _capture(entry: Callable[[Path], int], root: Path) -> tuple[int, str]:
    """Run a gate's `main()` over a fixture root; return its exit code and everything it printed.

    Both streams are captured into one buffer on purpose: `could_not_run()` writes to stderr and
    the verdict to stdout, and an `expect_line` assertion should not have to know which stream a
    given disclosure chose.

    A `main()` that raises is a self-test failure, not a harness crash -- it is reported as exit
    code -1 with its traceback, so one broken gate cannot take the suite down with it.
    """
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            code = entry(root)
    except SystemExit as exc:  # main() may raise rather than return
        code = exc.code if isinstance(exc.code, int) else 1
    except Exception:  # noqa: BLE001 -- deliberately broad; see the docstring
        return -1, buf.getvalue() + traceback.format_exc()
    return (0 if code is None else int(code)), buf.getvalue()


def _first_verdict(text: str) -> str:
    for ln in text.splitlines():
        if ln.startswith(("PASS:", "FAIL:", "could not run:")):
            return ln
    return (text.strip().splitlines() or ["<printed nothing>"])[-1]


def _attribution_enforced(contract: GateContract, outcomes: list[Outcome]) -> bool:
    """Does this gate have to attribute every mutant to its own class?

    Three inputs, in priority order:

    1. `attributes_classes`, when the gate states it. An explicit True is the strongest form: a
       gate that says it attributes and then returns no classes FAILS, which is what makes this
       requirement survive a later refactor of `run()`.
    2. `expect_line`, which IS a per-class declaration -- you cannot promise a per-class disclosure
       and then not know which class fired.
    3. Any class actually reported. This catches PARTIAL attribution, the likeliest regression: a
       gate that attributes four of its five classes is now a failure rather than a rounding error.

    WHAT THIS DELIBERATELY DOES NOT DO, and it is the residual hole in stage A0: a gate that
    declares nothing new and reports no class at all is treated as pre-A0 and PASSES. It has to be
    -- the eight gates in this package are exactly that shape and A0 may not touch them. The
    mitigation is disclosure, not silence: such a gate's self-test line now reads `BY FINDING COUNT
    ONLY` and names how many class labels went unverified, so the claim the old line made for free
    now has to be earned. Stage A3's gates all declare `expect_line`, so they are all enforced.
    """
    if contract.attributes_classes is not None:
        return contract.attributes_classes
    return bool(contract.expect_line) or any(o.classes for o in outcomes)


def run_self_test(contract: GateContract, *, needs_git: bool = False) -> int:
    """Seed every fixture and every mutant; assert each mutant is rejected AS ITS OWN CLASS.

    The denominator this prints counts ASSERTIONS ACTUALLY MADE. Nothing is added to it for a
    property the harness merely hoped held: an extra that establishes nothing contributes nothing,
    a class that cannot be attributed is counted as unverified in words rather than as a pass in
    the numerator.
    """
    checks = 0
    failures: list[str] = []

    def assert_(cond: object, msg: str) -> bool:
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(msg)
        return bool(cond)

    # --- contract sanity, before any fixture is built --------------------------------------------
    # Declaring a printed disclosure with no way to capture what was printed is not a gate that
    # fails, it is a gate that cannot be judged. That is exit 2's job, and stating it up front
    # beats discovering it after thirty seconds of fixture-building.
    if contract.expect_line and contract.main is None:
        print(
            f"could not run: {contract.name} self-test — it declares expect_line for "
            f"{len(contract.expect_line)} class(es) but supplies no main(); a printed line cannot "
            f"be asserted without running the thing that prints it",
            file=sys.stderr,
        )
        return 2

    mutant_outcomes: dict[str, Outcome] = {}
    mutant_roots: dict[str, Path] = {}
    must_pass_outcomes: dict[str, Outcome] = {}

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        if needs_git and not _git_init(base):
            print(f"could not run: {contract.name} self-test — git is required", file=sys.stderr)
            return 2

        def seed(name: str, build: Callable[[Path], None]) -> Path:
            root = base / name
            root.mkdir(parents=True, exist_ok=True)
            build(root)
            if needs_git:
                _git_init(root)
                subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            return root

        # 1 - the clean fixture must pass, over a NON-ZERO denominator.
        clean_root = seed("clean", contract.clean)
        clean_out = contract.run(clean_root)
        assert_(clean_out.examined > 0, "clean fixture examined 0 — a pass over nothing")
        assert_(clean_out.clean, f"clean fixture produced {clean_out.findings} finding(s)")

        # 2 - every must_pass fixture must ALSO come back clean, over a non-zero denominator.
        # This is where "readable, not answerable, and that is a correct state" becomes checkable.
        # A gate that rejects the absence of an optional thing is the most expensive kind of wrong:
        # it forces edits to bundles that were already correct.
        must_pass_roots: dict[str, Path] = {}
        for i, (label, build) in enumerate(contract.must_pass.items()):
            must_pass_roots[label] = seed(f"must_pass_{i}", build)
            out = contract.run(must_pass_roots[label])
            must_pass_outcomes[label] = out
            assert_(
                out.examined > 0,
                f"must_pass {label!r}: examined 0 — the fixture proved nothing",
            )
            assert_(
                out.clean,
                f"must_pass {label!r}: {out.findings} finding(s) — this fixture MUST NOT be "
                f"rejected"
                + (f" [class(es): {', '.join(sorted(out.classes))}]" if out.classes else ""),
            )

        # 3 - every mutant must be rejected, and must really have been written.
        for cls, seeder in contract.mutants.items():
            root = base / cls
            root.mkdir(parents=True, exist_ok=True)
            contract.clean(root)
            written = seeder(root)
            if not assert_(
                Path(written).exists(), f"mutant {cls!r} did not write {written} — it did not mutate"
            ):
                continue
            if needs_git:
                _git_init(root)
                subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            out = contract.run(root)
            mutant_outcomes[cls] = out
            mutant_roots[cls] = root
            assert_(not out.clean, f"mutant not caught: {cls}")

        # 4 - CLASS ATTRIBUTION. The assertion stage A0 exists for.
        enforced = _attribution_enforced(
            contract, [clean_out, *must_pass_outcomes.values(), *mutant_outcomes.values()]
        )
        if enforced:
            assert_(
                not clean_out.classes,
                f"clean fixture attributed {sorted(clean_out.classes)} over "
                f"{clean_out.findings} finding(s)",
            )
            for label, out in must_pass_outcomes.items():
                assert_(
                    not out.classes,
                    f"must_pass {label!r} attributed {sorted(out.classes)}",
                )
            for cls, out in mutant_outcomes.items():
                assert_(
                    cls in out.classes,
                    f"mutant {cls!r}: gate reported {out.findings} finding(s) but attributed "
                    f"{sorted(out.classes) or 'NO class'} — a finding of the wrong kind is not "
                    f"coverage for this class",
                )
                others = out.classes - {cls}
                assert_(
                    not others,
                    f"mutant {cls!r}: {sorted(others)} also fired — one mutation must trip one "
                    f"class, or two labels are sharing one predicate",
                )

        # 5 - THE PRINTED LINE AND THE EXIT CODE. A gate is read by what it prints.
        verdicts = 0
        if contract.main is not None:
            code, text = _capture(contract.main, clean_root)
            verdicts += 1
            assert_(
                code == 0,
                f"clean fixture: main() exited {code}, expected 0 — {_first_verdict(text)}",
            )
            assert_(
                text.lstrip().startswith("PASS:") or "\nPASS:" in text,
                f"clean fixture: main() printed no PASS: line — {_first_verdict(text)}",
            )
            for label, root in must_pass_roots.items():
                code, text = _capture(contract.main, root)
                verdicts += 1
                assert_(
                    code == 0,
                    f"must_pass {label!r}: main() exited {code}, expected 0 — {_first_verdict(text)}",
                )
            for cls, root in mutant_roots.items():
                code, text = _capture(contract.main, root)
                verdicts += 1
                assert_(
                    code == 1,
                    f"mutant {cls!r}: main() exited {code}, expected 1 (a FAIL verdict) — "
                    f"{_first_verdict(text)}",
                )
                fragment = contract.expect_line.get(cls)
                if fragment is not None:
                    assert_(
                        fragment in text,
                        f"mutant {cls!r}: the verdict does not disclose {fragment!r} — "
                        f"{_first_verdict(text)}",
                    )

        # 6 - any extra property the gate claims, in whichever shape it claims it.
        established = claimed = 0
        legacy_extras = 0
        silent_extras: list[str] = []
        for label, assertion in contract.extra.items():
            try:
                result = assertion(base)
            except Exception as exc:  # noqa: BLE001 -- one bad extra must not take down the suite
                checks += 1
                failures.append(f"{label}: raised {type(exc).__name__}: {exc}")
                continue
            if isinstance(result, tuple):
                got, want = int(result[0]), int(result[1])
                established += got
                claimed += want
                if want == 0:
                    # Rule 4 made visible: an extra that claims nothing is not an assertion. It is
                    # printed by label instead of being counted, which is what a no-op deserves.
                    silent_extras.append(label)
                    continue
                checks += want
                if got < want:
                    failures.append(
                        f"{label}: established {got} of {want} claimed assertion(s)"
                    )
            else:
                # Legacy string shape. It can subtract from the score but never add to it: it
                # cannot prove it examined anything, and a denominator it inflates is exactly the
                # defect stage A0 was opened to kill.
                legacy_extras += 1
                if result:
                    checks += 1
                    failures.append(f"{label}: {result}")

    # --- the printed line -------------------------------------------------------------------------
    # The parenthetical names WHAT WAS ASSERTED, never what held -- it is printed on the failure
    # path too, and a detail line that reads like a success claim beside a FAIL is how a reader
    # ends up quoting the wrong half of a gate's output.
    parts = ["1 clean fixture, for a non-zero denominator and no findings"]
    if contract.must_pass:
        parts.append(
            f"{len(contract.must_pass)} must-pass fixture(s), for clean over a non-zero denominator"
        )
    if enforced:
        parts.append(
            f"{len(contract.mutants)} mutant(s), for mutation, rejection AND attribution to their "
            f"own class with no other class firing"
        )
    else:
        parts.append(
            f"{len(contract.mutants)} mutant(s), for mutation and rejection BY FINDING COUNT "
            f"ONLY — this gate attributes no reject class, so {len(contract.mutants)} class "
            f"name(s) are UNVERIFIED"
        )
    parts.append(
        f"{verdicts} main() invocation(s), for the verdict line and the exit code"
        if contract.main is not None
        else "main() not exercised (no entry point declared)"
    )
    if claimed:
        parts.append(f"extras: established {established} of {claimed} claimed")
    if silent_extras:
        parts.append(f"{len(silent_extras)} extra(s) claimed nothing: {', '.join(silent_extras)}")
    if legacy_extras:
        parts.append(f"{legacy_extras} legacy extra(s), outside the denominator")
    detail = "; ".join(parts)

    if failures:
        print(f"FAIL: {contract.name} self-test — {len(failures)} of {checks} assertions failed")
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        print(f"  asserted: {detail}", file=sys.stderr)
        return 1
    print(f"PASS: {contract.name} self-test — {checks}/{checks} asserted: {detail}")
    return 0


def write(path: Path, text: str) -> Path:
    """Seeder helper: write a file, creating parents. Returns the path, for the mutation assertion."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def env_root(var: str, default: Path) -> Path:
    v = os.environ.get(var)
    return Path(v) if v else default
