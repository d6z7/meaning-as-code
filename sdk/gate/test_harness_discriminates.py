"""The stage A0 repair, pinned. Runs both demo arms and asserts the DIFFERENCE between them.

WHY THIS FILE IS A PYTEST FILE AND NOT A GATE. `sdk/gate/run_gates.sh` carries a hand-written
GATES list and stage A0 does not own that file, so a tenth `check_*.py` here would be a gate nobody
runs -- which is the exact complaint that opened this whole record. `python3 -m pytest sdk -q` is
already a baseline gate for this repo and `sdk/gate/test_*.py` is already how this package wires
fixtures into it. So the two demo arms run on every commit from the day they land, with no edit to
a file another stage owns.

WHAT IS PINNED HERE, and why each one:

* The DIFFERENCE. `demo_wrong_gate` and `demo_right_gate` share their mutant seeders and their
  `expect_line` fragments BY IDENTITY -- the same dict values, imported, not copied. One implements
  the three classes; one does not. If the harness ever stops telling them apart, exactly one of
  these tests goes red and it says which direction the regression ran.
* The BACKWARDS-COMPATIBILITY LINE, byte for byte. Eight gates in this package print through
  `verdict()` and were not touched by A0. Their three output shapes are asserted as literal strings
  here, because "additive" is a claim, and a claim about printed output is checked by comparing
  printed output.
* The TWO DENOMINATOR RULES: a no-op extra cannot inflate the score, and a legacy string extra
  cannot either. Both were live defects, both are one refactor away from coming back.
"""

from __future__ import annotations

from pathlib import Path

from sdk.gate import contract, demo_right_gate, demo_wrong_gate

# ------------------------------------------------------------------------------------------------
# the difference between a declared class and an implemented one
# ------------------------------------------------------------------------------------------------


def test_the_two_arms_declare_the_same_classes(capsys):
    """Same seeders, same fragments, same fixture. Only `run()` differs."""
    wrong = demo_wrong_gate.build(contract)
    right = demo_right_gate.build(contract)
    assert set(wrong.mutants) == set(right.mutants) == set(demo_wrong_gate._EXPECT_LINE)
    assert wrong.expect_line == right.expect_line
    assert wrong.clean is right.clean
    for cls, seeder in wrong.mutants.items():
        assert right.mutants[cls] is seeder, f"{cls}: the two arms must share one seeder"


def test_a_gate_implementing_none_of_its_declared_classes_fails(capsys):
    """The named check of stage A0. This gate printed `PASS: demo-gate self-test — 7/7` before it."""
    code = contract.run_self_test(demo_wrong_gate.build(contract))
    out = capsys.readouterr()
    text = out.out + out.err

    assert code == 1, "a gate implementing none of three declared classes must not pass"
    assert "FAIL: demo-gate self-test" in text

    # Every declared class must be named as unattributed -- not just "something failed". A failure
    # report that does not say WHICH class was never implemented leaves the author guessing, and a
    # guessing author re-runs until it is green.
    for cls in demo_wrong_gate._MUTANTS:
        assert f"mutant '{cls}': gate reported" in text, f"{cls} was not named as unattributed"
        assert f"mutant '{cls}': the verdict does not disclose" in text

    # And both non-negotiable properties must be named, as fixtures rather than as lambdas.
    assert f"must_pass '{demo_wrong_gate._P1}'" in text
    assert f"must_pass '{demo_wrong_gate._P2}'" in text


def test_the_same_declarations_implemented_pass(capsys):
    """The control arm. Without this, "the harness fails it" would prove only that it fails."""
    code = contract.run_self_test(demo_right_gate.build(contract))
    out = capsys.readouterr()

    assert code == 0, out.out + out.err
    assert "PASS: demo-right-gate self-test" in out.out
    assert "AS THEIR OWN CLASS" not in out.out  # the wording is about what was ASSERTED...
    assert "attribution to their own class" in out.out  # ...not a claim of success


def test_each_mutant_trips_exactly_its_own_class(tmp_path):
    """The predicate-per-label rule, at the level of the Outcome rather than the self-test line.

    `../../outside/creds.yaml` does not exist EITHER, so a gate that tested existence before
    containment would report it as `declared-missing` and look just as green. This asserts the
    ordering that makes the two labels two predicates.
    """
    for cls, seeder in demo_wrong_gate._MUTANTS.items():
        root = tmp_path / cls
        root.mkdir(parents=True, exist_ok=True)
        demo_wrong_gate._clean(root)
        seeder(root)
        out = demo_right_gate._run(contract, root)
        assert out.classes == frozenset({cls}), f"{cls} produced {sorted(out.classes)}"


# ------------------------------------------------------------------------------------------------
# the backwards-compatibility guarantee, as literal strings
# ------------------------------------------------------------------------------------------------


def test_verdict_is_byte_identical_for_a_pre_a0_outcome():
    """An Outcome that declares neither classes nor a secondary prints what it printed before A0."""
    assert contract.verdict("g", contract.Outcome(0, 5)) == (
        "PASS: g — 0 violation(s) over 5 file(s) examined",
        0,
    )
    assert contract.verdict("g", contract.Outcome(2, 5)) == (
        "FAIL: g — 2 violation(s) over 5 file(s) examined",
        1,
    )
    assert contract.verdict("g", contract.Outcome(0, 0)) == (
        "could not run: g examined 0 file(s), which is not the same as clean",
        2,
    )
    assert contract.verdict("g", contract.Outcome(0, 5), detail="d") == (
        "PASS: g — 0 violation(s) over 5 file(s) examined — d",
        0,
    )


def test_a_declared_secondary_of_zero_refuses_and_keeps_its_findings():
    line, code = contract.verdict(
        "g", contract.Outcome(3, 5, "bundle(s)", secondary=(0, "document(s) validated"))
    )
    assert code == 2
    assert "missing yardstick" in line
    assert "3 finding(s) held, unjudged" in line, "a refusal must not swallow real findings"

    line, code = contract.verdict(
        "g", contract.Outcome(0, 5, "bundle(s)", secondary=(2, "document(s) validated"))
    )
    assert (code, line) == (
        0,
        "PASS: g — 0 violation(s) over 5 bundle(s) examined, 2 document(s) validated",
    )


def test_a_fail_line_names_the_classes_that_fired():
    line, code = contract.verdict("g", contract.Outcome(2, 5, classes={"b", "a"}))
    assert code == 1
    assert line.endswith("[class(es): a, b]"), line


# ------------------------------------------------------------------------------------------------
# the denominator rules — neither shape of no-op may inflate a score
# ------------------------------------------------------------------------------------------------


def _trivial(root: Path) -> None:
    (root / "f.txt").write_text("clean\n", encoding="utf-8")


def _trivial_run(root: Path) -> contract.Outcome:
    files = sorted(root.rglob("*.txt"))
    return contract.Outcome(sum(1 for p in files if "bad" in p.read_text()), len(files))


def _base(**kw) -> contract.GateContract:
    return contract.GateContract(
        name="tiny",
        clean=_trivial,
        mutants={"seeded": lambda r: contract.write(r / "bad.txt", "bad\n")},
        run=_trivial_run,
        **kw,
    )


def _score(text: str) -> tuple[int, int]:
    head = text.split("—", 1)[1].strip().split()[0]
    got, total = head.split("/")
    return int(got), int(total)


def test_a_no_op_extra_cannot_inflate_the_denominator(capsys):
    """`lambda base: (0, 0)` claims nothing, so it adds nothing and is printed by name instead."""
    bare = contract.run_self_test(_base())
    baseline = _score(capsys.readouterr().out)

    code = contract.run_self_test(_base(extra={"claims nothing": lambda base: (0, 0)}))
    out = capsys.readouterr().out
    assert (code, _score(out)) == (bare, baseline), "a no-op extra moved the score"
    assert "1 extra(s) claimed nothing: claims nothing" in out


def test_an_extra_that_claims_and_fails_to_establish_is_a_failure(capsys):
    code = contract.run_self_test(_base(extra={"claims one": lambda base: (0, 1)}))
    out = capsys.readouterr()
    assert code == 1
    assert "established 0 of 1 claimed assertion(s)" in out.err


def test_a_legacy_string_extra_still_runs_but_stays_out_of_the_denominator(capsys):
    """Five of the eight gates use this shape and stage A0 was not allowed to touch them.

    It can still FAIL the self-test -- a non-empty return is a finding -- but it can never add to
    the score, because `lambda base: ""` cannot prove it examined anything.
    """
    bare = contract.run_self_test(_base())
    baseline = _score(capsys.readouterr().out)

    code = contract.run_self_test(_base(extra={"legacy no-op": lambda base: ""}))
    out = capsys.readouterr().out
    assert (code, _score(out)) == (bare, baseline)
    assert "1 legacy extra(s), outside the denominator" in out

    assert contract.run_self_test(_base(extra={"legacy real": lambda base: "it broke"})) == 1
    assert "legacy real: it broke" in capsys.readouterr().err


def test_expect_line_without_a_main_is_could_not_run(capsys):
    """Not a FAIL. A gate that cannot be judged has not been judged -- that is exit 2's job."""
    code = contract.run_self_test(_base(expect_line={"seeded": "anything"}))
    assert code == 2
    assert "supplies no main()" in capsys.readouterr().err


def test_a_gate_that_says_it_attributes_and_does_not_fails(capsys):
    """The explicit form. `attributes_classes=True` is how a gate keeps its attribution through a
    refactor: delete `classes=` from `run()` and this is red, rather than quietly downgrading to
    "rejected by finding count only"."""
    assert contract.run_self_test(_base(attributes_classes=True)) == 1
    assert "attributed NO class" in capsys.readouterr().err

    # ...and the same contract without the declaration passes, printing the truth instead.
    assert contract.run_self_test(_base()) == 0
    assert "BY FINDING COUNT ONLY" in capsys.readouterr().out
