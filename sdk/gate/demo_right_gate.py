"""demo_right_gate — the same three declarations as `demo_wrong_gate`, actually implemented.

WHY THIS FILE EXISTS. "The repaired harness fails the wrong gate" proves nothing on its own: a
harness that fails everything is not a repair, it is a brick. The claim stage A0 makes is a
DIFFERENCE, and a difference needs two arms.

So this file imports its fixture, its three mutant seeders and its three `expect_line` fragments
FROM `demo_wrong_gate` -- the same objects, not copies. The declaration table is identical by
construction. The only thing that differs between the two files is whether `run()` computes the
three classes it named.

    python3 -m sdk.gate.demo_wrong_gate  --self-test   -> FAIL, 12 of 33 assertions
    python3 -m sdk.gate.demo_right_gate  --self-test   -> PASS

If a change to `contract.py` ever makes those two agree, the harness has stopped discriminating and
one of these two files is lying. That is the property worth having a fixture for.

WHAT ELSE THIS ARM EXERCISES, because nothing else in the tree does yet:

* `Outcome.classes` on the happy path -- three mutants, three DIFFERENT classes, each alone.
* `Outcome.secondary` and `verdict()`'s new refusal: a gate that declares a second denominator and
  finds zero of it exits 2 rather than PASS.
* The trap that refusal sets, and the escape. This gate's yardstick is CONNECTION DOCUMENTS
  VALIDATED, but its population is BUNDLES. A bundle that correctly declares no connection
  validates no document -- and a bare "secondary zero -> exit 2" rule would turn the single most
  important property in the connector record ("readable, not answerable, and that is a correct
  state") into a could-not-run. The escape is structural and it is the one the record specifies: a
  BUILT-IN FIXTURE DOCUMENT is always in the population, so the secondary is zero only when the
  fixtures themselves are lost -- which is exactly when exit 2 is the right answer. `_run` carries
  that fixture; one `extra` proves the refusal fires without it.

Named `demo_*`, not `check_*`: neither suite runner may sweep up a fixture.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import ModuleType

from sdk.gate import contract as _live_harness
from sdk.gate.demo_wrong_gate import (
    _CONNECTION,
    _EXPECT_LINE,
    _MUTANTS,
    _clean,
    _no_connection_at_all,
    _optional_key_absent,
    _P1,
    _P2,
)

NAME = "demo-right-gate"

#: The credential grammar's whole legal key set for the inline form. A third key has no slot.
_CREDENTIAL_KEYS = {"mode", "ref"}


# ------------------------------------------------------------------------------------------------
# three predicates, because three classes were declared
# ------------------------------------------------------------------------------------------------
# Deliberately hand-parsed rather than pulled through pyyaml: `sdk/gate/` is the home of gates that
# must run with nothing installed, and these fixtures are four lines of fixed-shape YAML. A real
# gate gets a schema; a demo gets to stay dependency-free and obvious.


def _declared_connection(project_text: str) -> str | None:
    for line in project_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("connection:"):
            return stripped.split(":", 1)[1].strip()
    return None  # no declaration is not a finding -- see `_no_connection_at_all`


def _credential_keys(connection_text: str) -> list[str]:
    for line in connection_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("credentials:"):
            body = stripped.split(":", 1)[1].strip().strip("{}")
            return [kv.split(":", 1)[0].strip() for kv in body.split(",") if kv.strip()]
    return []


def _findings(root: Path) -> tuple[list[tuple[str, str]], int, int]:
    """Return [(reject class, message)], bundles examined, documents validated."""
    found: list[tuple[str, str]] = []
    bundles = sorted(p.parent for p in root.rglob("mac.project.yaml"))
    validated = 0

    for bundle in bundles:
        declared = _declared_connection((bundle / "mac.project.yaml").read_text(encoding="utf-8"))
        if declared is None:
            continue
        target = bundle / declared

        # CONTAINMENT IS CHECKED FIRST, AND THAT ORDER IS THE POINT. `../../outside/creds.yaml`
        # also fails to exist, so a gate that tested existence first would report every escape as
        # `declared-missing` and its self-test would still look green -- under the old harness.
        # Class attribution is what forces these two labels to be two predicates.
        if not target.resolve().is_relative_to(bundle.resolve()):
            found.append(
                ("config-path-escapes-bundle", f"{declared!r} escapes the bundle root")
            )
            continue
        if not target.exists():
            found.append(("declared-missing", f"{declared!r} is declared but missing"))
            continue

        validated += 1
        surplus = [k for k in _credential_keys(target.read_text(encoding="utf-8"))
                   if k not in _CREDENTIAL_KEYS]
        if surplus:
            found.append(
                (
                    "credentials-third-key",
                    f"credentials.{surplus[0]}: additionalProperties — the grammar gives no legal "
                    f"slot beside {sorted(_CREDENTIAL_KEYS)}",
                )
            )
    return found, len(bundles), validated


def _run(harness: ModuleType, root: Path, *, built_in_fixture: bool = True):
    found, bundles, validated = _findings(root)
    if built_in_fixture:
        # The fixture document that keeps the yardstick non-zero. It is validated on every run, in
        # every environment, so `documents validated == 0` can only mean the fixtures are gone.
        assert _CONNECTION  # the shipped document this stands in for
        validated += 1
    return harness.Outcome(
        len(found),
        bundles,
        "bundle(s)",
        classes={cls for cls, _ in found},
        secondary=(validated, "document(s) validated [1 built-in fixture]"),
    )


def _main_over(harness: ModuleType, root: Path) -> int:
    """Print what was found, per finding, THEN the verdict.

    The per-finding lines are not decoration: `expect_line` asserts that the reason a document was
    rejected reaches the reader. A gate whose only output is its own scoreboard has disclosed
    nothing a person could act on.
    """
    found, _bundles, _validated = _findings(root)
    for cls, message in found:
        print(f"  [{cls}] {message}")
    line, code = harness.verdict(NAME, _run(harness, root))
    print(line)
    return code


# ------------------------------------------------------------------------------------------------
# extras that actually establish something — (established, claimed), never a no-op
# ------------------------------------------------------------------------------------------------


def _secondary_zero_refuses(harness: ModuleType) -> tuple[int, int]:
    """The new refusal in `verdict()`, and its complement. Two claims, two establishments."""
    established = 0

    zero = harness.Outcome(0, 1, "bundle(s)", secondary=(0, "document(s) validated"))
    line, code = harness.verdict(NAME, zero)
    if code == 2 and "missing yardstick" in line:
        established += 1

    one = harness.Outcome(0, 1, "bundle(s)", secondary=(1, "document(s) validated"))
    line, code = harness.verdict(NAME, one)
    if code == 0 and "1 document(s) validated" in line:
        established += 1

    return established, 2


def _fixture_keeps_contoso_answerable_as_a_pass(harness: ModuleType, base: Path) -> tuple[int, int]:
    """The trap, proved in both directions over the no-connection bundle.

    WITH the built-in fixture the yardstick is 1 and the bundle PASSES. WITHOUT it the yardstick is
    0 and the gate refuses. Same tree, same predicates -- the whole difference is whether the
    fixture population is there, which is why the record makes it structural rather than advisory.
    """
    root = base / "_secondary_probe"
    root.mkdir(parents=True, exist_ok=True)
    _no_connection_at_all(root)

    established = 0
    _line, code = harness.verdict(NAME, _run(harness, root, built_in_fixture=True))
    if code == 0:
        established += 1
    _line, code = harness.verdict(NAME, _run(harness, root, built_in_fixture=False))
    if code == 2:
        established += 1
    return established, 2


# ------------------------------------------------------------------------------------------------


def build(harness: ModuleType):
    return harness.GateContract(
        name=NAME,
        clean=_clean,
        mutants=dict(_MUTANTS),  # the SAME seeders the wrong gate declares
        run=lambda r: _run(harness, r),
        must_pass={_P1: _no_connection_at_all, _P2: _optional_key_absent},
        expect_line=dict(_EXPECT_LINE),  # the SAME fragments
        main=lambda r: _main_over(harness, r),
        # Stated, not inferred. The day someone deletes `classes=` from `_run` to quiet a failure,
        # this line is what turns that into a red self-test instead of a silent downgrade to
        # "rejected by finding count only".
        attributes_classes=True,
        extra={
            "a declared secondary of zero refuses instead of passing": lambda base: (
                _secondary_zero_refuses(harness)
            ),
            "the built-in fixture keeps a no-connection bundle a PASS, not a could-not-run": (
                lambda base: _fixture_keeps_contoso_answerable_as_a_pass(harness, base)
            ),
        },
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)

    if not a.self_test:
        print(
            f"could not run: {NAME} — this is the CONTROL ARM of the stage A0 harness repair, not "
            "a gate over this tree. Run it with --self-test.",
            file=sys.stderr,
        )
        return 2

    if "secondary" not in _live_harness.Outcome.__dataclass_fields__:
        # The pre-A0 harness cannot express half of what this arm asserts, and a control arm that
        # silently degrades proves the opposite of what it exists to prove.
        print(
            f"could not run: {NAME} — the installed harness has no Outcome.secondary, so this "
            "control arm cannot be expressed on it",
            file=sys.stderr,
        )
        return 2

    return _live_harness.run_self_test(build(_live_harness))


if __name__ == "__main__":
    sys.exit(main())
