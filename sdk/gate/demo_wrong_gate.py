"""demo_wrong_gate — the gate the harness could not catch. A FIXTURE OF A DEFECT, not a gate.

WHY THIS FILE EXISTS, AND WHY IT IS COMMITTED RATHER THAN THROWN AWAY.

An adversarial review of this estate asked one question of `sdk/gate/contract.py`: *can the harness
tell the difference between a gate that implements three reject classes and a gate that implements
one catch-all?* It answered by building this gate and running it. Measured, on the harness at
`HEAD~` of stage A0:

    PASS: demo-gate self-test — 7/7 (3 mutant(s) rejected as their own class, clean fixture passes
    over a non-zero denominator, every mutant proved to have mutated)

Every word after the dash is false. This gate implements NONE of the three classes it declares. Its
`run()` compares each YAML file against a digest allowlist — "did anything change?" — which fires for
all three mutants for the same reason, and for a fourth reason its author never considered: a bundle
that legitimately carries NO connection document at all. The old harness's per-mutant assertion was
`if out.clean: fail`, i.e. *at least one finding, for any reason*, so a tautology scored full marks.

The 7 came apart as 2 + 3 + 2: two clean-fixture assertions, three mutants, and **two no-op lambdas**
carrying the labels of the two properties this estate calls non-negotiable. `extra` accepted
`lambda base: ""` and counted it into the printed denominator, so two assertions that assert nothing
took the score from 5/5 to 7/7. The property that outranks everything else in the connector record —
*a bundle with no connection must still PASS* — was the one property the harness could not express.

THIS FILE IS THE REGRESSION TEST FOR THAT REPAIR. It runs against ANY harness, old or new:

    python3 -m sdk.gate.demo_wrong_gate --self-test
        the repaired harness -> FAIL (exit 1), naming every unimplemented class

    git show <rev>:sdk/gate/contract.py > /tmp/old_contract.py
    python3 -m sdk.gate.demo_wrong_gate --self-test --harness /tmp/old_contract.py
        the harness as it stood -> PASS 7/7 (exit 0)

Two verdicts over the SAME wrong gate is the only honest way to state what stage A0 bought. If a
later refactor of `contract.py` ever makes this file pass again, the repair has been undone, and
this file says so in one line.

It is named `demo_*`, not `check_*`, on purpose: `tools/run_framework_gates.sh` globs `check_*.py`
and `sdk/gate/run_gates.sh` carries a hand-written GATES list. A deliberately-failing fixture must
not be able to drift into either suite.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from sdk.gate import contract as _live_harness

NAME = "demo-gate"

# ------------------------------------------------------------------------------------------------
# the fixture bundle: two documents, deliberately unremarkable
# ------------------------------------------------------------------------------------------------
# Generic on purpose. No source, no brand, no warehouse, no estate path -- this file is in a public
# repository and a fixture is not an exemption from that.

_PROJECT = "runtime:\n  connector: mac.connector.demo\n  connection: connection.yaml\n"
_CONNECTION = (
    "spec_version: mac.connector/1\n"
    "credentials: {mode: named_profile, ref: demo-profile}\n"
    "config: {database: demo.db, read_only: true}\n"
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_KNOWN = {_sha(_PROJECT), _sha(_CONNECTION)}


def _clean(root: Path) -> None:
    """The positive fixture: a bundle that declares a connection and points at a file that exists."""
    (root / "bundle").mkdir(parents=True, exist_ok=True)
    (root / "bundle" / "mac.project.yaml").write_text(_PROJECT, encoding="utf-8")
    (root / "bundle" / "connection.yaml").write_text(_CONNECTION, encoding="utf-8")


# ------------------------------------------------------------------------------------------------
# THE DEFECT ITSELF — one catch-all predicate wearing three class names
# ------------------------------------------------------------------------------------------------


def _run(harness: ModuleType, root: Path):
    """Count YAML files whose digest is not on the allowlist. That is the whole implementation.

    Not one of the three declared classes is computed here. There is no realpath containment check,
    so `config-path-escapes-bundle` is not implemented. There is no resolution of the declared path,
    so `declared-missing` is not implemented. There is no schema, so `credentials-third-key` is not
    implemented. Every mutant trips the SAME predicate -- "this document is not the one I was
    shown" -- and the old harness reported three classes rejected as their own class.

    Note what is returned: `Outcome(findings, examined)` with no `classes`. Under the repaired
    harness that is the finding, and this is why the auto-detect rule in `run_self_test` is not
    allowed to be "enforce attribution only where classes happen to be reported".
    """
    yamls = sorted(root.rglob("*.yaml"))
    findings = sum(1 for p in yamls if _sha(p.read_text(encoding="utf-8")) not in _KNOWN)
    return harness.Outcome(findings, len(yamls), "yaml file(s)")


def _main_over(harness: ModuleType, root: Path) -> int:
    """The gate's own `main()`, adapted to take a fixture root.

    It prints the shared verdict line and nothing else -- which is precisely why it cannot satisfy
    a single `expect_line` fragment. Seven disclosures in the connector record are entirely about
    what a gate PRINTS; a gate that prints only its own scoreboard has disclosed none of them.
    """
    line, code = harness.verdict(NAME, _run(harness, root))
    print(line)
    return code


# ------------------------------------------------------------------------------------------------
# the three classes it declares, and the mutants that are supposed to prove them
# ------------------------------------------------------------------------------------------------

_MUTANTS = {
    # `runtime.connection` names a file that is not there. The declared path is never resolved.
    "declared-missing": lambda r: _write(
        r / "bundle" / "mac.project.yaml",
        "runtime:\n  connector: mac.connector.demo\n  connection: deploy/prod.yaml\n",
    ),
    # The classic escape. Containment is never checked, so this trips for the same reason as the
    # class above -- which is the exact false green the record names: one predicate, two labels.
    "config-path-escapes-bundle": lambda r: _write(
        r / "bundle" / "mac.project.yaml",
        "runtime:\n  connector: mac.connector.demo\n  connection: ../../outside/creds.yaml\n",
    ),
    # A third key beside {mode, ref}, which the credential grammar gives no legal slot. There is no
    # schema in this gate, so nothing here is validated.
    "credentials-third-key": lambda r: _write(
        r / "bundle" / "connection.yaml",
        "spec_version: mac.connector/1\n"
        "credentials: {mode: named_profile, ref: demo-profile, password: PLACEHOLDER}\n"
        "config: {database: demo.db, read_only: true}\n",
    ),
}

_EXPECT_LINE = {
    "declared-missing": "declared but missing",
    "config-path-escapes-bundle": "escapes the bundle root",
    "credentials-third-key": "additionalProperties",
}


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------------------------------------------
# the two non-negotiable properties — expressed twice, once per harness
# ------------------------------------------------------------------------------------------------
# These are the same two claims in both modes. The OLD harness had exactly one place to put them,
# `extra`, which accepted a lambda returning "" and counted it as an assertion. The repaired harness
# has `must_pass`, where the claim is seeded, run, and judged. Same words, same file; one of the two
# is checkable. That difference is the whole of stage A0.

_P1 = "a bundle with no connection at all must still PASS"
_P2 = "an absent optional key must not be rejected"


def _no_connection_at_all(root: Path) -> None:
    """The regression test for the DuckDB-shaped bundle that declares no connection.

    Readable, not answerable, and that is a correct state -- not a violation. The digest allowlist
    calls it a violation, because a project file it has not been shown is the only thing it knows
    how to fail.
    """
    (root / "bundle").mkdir(parents=True, exist_ok=True)
    (root / "bundle" / "mac.project.yaml").write_text(
        "runtime:\n  connector: mac.connector.demo\n", encoding="utf-8"
    )


def _optional_key_absent(root: Path) -> None:
    """`config.read_only` is optional. Leaving it out is a legal document, not a finding."""
    (root / "bundle").mkdir(parents=True, exist_ok=True)
    (root / "bundle" / "mac.project.yaml").write_text(_PROJECT, encoding="utf-8")
    (root / "bundle" / "connection.yaml").write_text(
        "spec_version: mac.connector/1\n"
        "credentials: {mode: named_profile, ref: demo-profile}\n"
        "config: {database: demo.db}\n",
        encoding="utf-8",
    )


# ------------------------------------------------------------------------------------------------
# the contract, built against whichever harness it was handed
# ------------------------------------------------------------------------------------------------


def build(harness: ModuleType):
    """Assemble this gate's contract for `harness`, using only the fields that harness has.

    The shape sniff is deliberate and it is the demonstration. Against the pre-A0 harness the two
    non-negotiable properties CANNOT be expressed as fixtures -- `mutants` requires rejection and
    `clean` is a single callable -- so they land in `extra` as the no-op lambdas that were actually
    written, and the printed score is 7/7. Against the repaired harness the same two properties are
    real `must_pass` fixtures and both fail.
    """
    repaired = {f.name for f in dataclasses.fields(harness.GateContract)}
    new_shape = "must_pass" in repaired

    kwargs = {
        "name": NAME,
        "clean": _clean,
        "mutants": dict(_MUTANTS),
        "run": lambda r: _run(harness, r),
    }

    if new_shape:
        kwargs["must_pass"] = {_P1: _no_connection_at_all, _P2: _optional_key_absent}
        kwargs["expect_line"] = dict(_EXPECT_LINE)
        kwargs["main"] = lambda r: _main_over(harness, r)
        # Rule 4: the same two no-ops, now returning (checked, total). They report `checked 0` and
        # are excluded from the denominator instead of inflating it.
        kwargs["extra"] = {
            f"{_P1} (as the no-op it always was)": lambda base: (0, 1),
            f"{_P2} (as the no-op it always was)": lambda base: (0, 1),
        }
    else:
        kwargs["extra"] = {_P1: lambda base: "", _P2: lambda base: ""}

    return harness.GateContract(**kwargs)


def _load_harness(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("demo_harness_under_test", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"could not load a harness from {path}")
    mod = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: @dataclass resolves its annotations through
    # `sys.modules[cls.__module__]`, so a module executed outside sys.modules dies on its
    # first dataclass. The old harness is all dataclasses.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument(
        "--harness",
        metavar="PATH",
        help="run this gate's self-test against another copy of contract.py "
        "(e.g. one dumped out of git) instead of the installed one",
    )
    a = ap.parse_args(argv)

    if not a.self_test:
        # This is a fixture of a defect. There is no tree it should ever be allowed to judge, and
        # "did not run" must never be silent -- so it says so and exits 2 rather than printing a
        # verdict some suite could later mistake for evidence.
        print(
            f"could not run: {NAME} — this is a FIXTURE of a defective gate, not a gate. "
            "Run it with --self-test; it is expected to FAIL against the repaired harness.",
            file=sys.stderr,
        )
        return 2

    harness = _load_harness(Path(a.harness)) if a.harness else _live_harness
    return harness.run_self_test(build(harness))


if __name__ == "__main__":
    sys.exit(main())
