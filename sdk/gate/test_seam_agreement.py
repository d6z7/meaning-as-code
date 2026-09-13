"""Unit tests for the seam inventory — the gate whose reason for existing is that 131 unit tests
caught 0 of 14 seam defects in one day.

THE POINT OF THIS FILE, given that sentence. A unit test cannot catch a seam defect, because it
asserts one side of the seam against a literal its author typed — the same act as writing the seam
wrong. So these tests do NOT assert what any seam in this repository contains. They assert that the
INSTRUMENT works:

  * its self-test rejects a mutant per enforced reject class (`--self-test`, via the harness);
  * each detector, in isolation, fires on its own defect and on nothing else;
  * every EXCLUDED class is still enumerated, so an exclusion cannot quietly become a deletion;
  * the four must-pass shapes stay PASSes, because a gate that rejects correct code gets deleted;
  * the population never silently shrinks to zero (`examined 0` is exit 2, not a green);
  * and the ratchet holds: the live disagreement set may only ever get SMALLER.

The one live-tree assertion is the last of those, and it is a SUBSET check on purpose. Fixing
`tools/mac_to_meta.py:193` empties the set and this file stays green; adding a second disagreement
anywhere fails it. A test that asserted the current count instead would punish the fix, which is
how `tools/mac_public_floor.txt` came to declare 146 while the real count was 4.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pytest

from sdk.gate import check_seam_agreement as g
from sdk.gate import contract


@functools.lru_cache(maxsize=1)
def _live():
    """The live-tree inventory, measured ONCE for this module.

    Six assertions below need it and the walk costs ~3s over 170 modules and 122 config files.
    Re-measuring per test took this file from 4s to 21s against a 5.4s whole-suite baseline — a
    gate that makes the suite slow enough to skip has a cost that outlives its findings. Callers
    only READ the inventory; nothing here mutates it.
    """
    return g.check(g.ROOT)


# ------------------------------------------------------------------------------------------------
# the harness contract
# ------------------------------------------------------------------------------------------------


def test_the_self_test_rejects_a_mutant_per_enforced_class():
    """`--self-test` is the gate's own proof. Exit 0 here means every enforced class has a mutant,
    each mutant is attributed to its OWN class with no other class firing, and each prints its
    disclosure. Verified to discriminate: blanking the sql-column predicate takes this to 4 failed
    assertions, and dropping `classes=` from `run()` takes it to 3."""
    assert g.main(["--self-test"]) == 0


def test_every_enforced_class_has_a_mutant():
    """A reject class with no mutant is a class nobody has tested. This is asserted here as well as
    inside the harness so ADDING an enforced class without a seeder is a failure at collection
    time, rather than a class that silently rides along unproven."""
    built = g.build()
    assert set(built.mutants) == set(g.ENFORCED)
    assert set(built.expect_line) == set(g.ENFORCED)


def test_the_floor_is_zero_owned_and_dated():
    """An undated, unowned floor is a permanent exemption. The gate refuses to enforce one, and
    the floor for a gate on its first day has no history to justify headroom."""
    assert g._ENFORCED_FLOOR == 0
    assert g._FLOOR_OWNER and g._FLOOR_DECLARED and g._FLOOR_REVIEW_BY


# ------------------------------------------------------------------------------------------------
# one detector at a time: it fires on its own defect, and on nothing else
# ------------------------------------------------------------------------------------------------


def _classes(root: Path) -> set[str]:
    return {f.cls for f in g.check(root).enforced_findings}


@pytest.mark.parametrize(
    "cls,seed",
    [
        ("closed-vocabulary-divergence", g._m_vocabulary),
        ("subprocess-argv-divergence", g._m_argv),
        ("sql-column-not-emitted", g._m_sql_column),
    ],
)
def test_each_detector_fires_on_its_own_defect_alone(tmp_path, cls, seed):
    """One mutation must trip ONE class. Two labels sharing one predicate is how a self-test scores
    three classes having implemented one — the defect `sdk/gate/demo_wrong_gate.py` is kept as a
    fixture for."""
    g._clean(tmp_path)
    assert _classes(tmp_path) == set(), "the clean fixture must carry no disagreement"
    seed(tmp_path)
    assert _classes(tmp_path) == {cls}


@pytest.mark.parametrize(
    "label,build",
    [
        ("orphan dict-key read", g._p_orphan_dict_key),
        ("placeholder default beside a config key", g._p_config_placeholder_default),
        ("a connector supporting a subset of the grammar", g._p_subset_is_legal),
        ("a shared English word with no shared member", g._p_homonym_is_not_a_seam),
    ],
)
def test_the_exclusions_are_real_not_merely_claimed(tmp_path, label, build):
    """Each of these four shapes is CORRECT CODE that a looser detector rejected during
    development: 194, 35, 0 and 7 findings of noise respectively. A gate that rejects correct code
    is the expensive kind of wrong — it forces edits to files that were already right."""
    build(tmp_path)
    assert _classes(tmp_path) == set(), f"{label} must not be scored"


def test_a_homonym_is_not_a_seam_but_is_still_queued(tmp_path):
    """The disclosed blind spot, asserted rather than described. A name that pairs with NO shared
    member is not scored — and it is not dropped either, because an end-to-end misspelling looks
    exactly the same and a human has to look."""
    g._p_homonym_is_not_a_seam(tmp_path)
    inv = g.check(tmp_path)
    assert inv.population["vocabulary-name-collision"] >= 1
    assert not inv.enforced_findings
    assert any("[queue]" in n for n in inv.notes)


def test_a_subset_is_legal_but_an_invented_spelling_is_not(tmp_path):
    """The rule `test_credential_vocabulary.py` states, generalised: SUBSET, never equality. This is
    the pair of assertions that makes the predicate's direction load-bearing."""
    g._p_subset_is_legal(tmp_path)
    assert not g.check(tmp_path).enforced_findings
    g._m_vocabulary(tmp_path)
    assert _classes(tmp_path) == {"closed-vocabulary-divergence"}


def test_argparse_builtin_flags_are_not_a_divergence(tmp_path):
    """`--help` cost this detector two of its first three findings: `ArgumentParser` installs it
    with no `add_argument` call, so a smoke-test caller that runs `-m mod --help` over every entry
    point was reported as passing an undefined flag."""
    g._clean(tmp_path)
    (tmp_path / "caller.py").write_text(
        'import subprocess, sys\n'
        'subprocess.run([sys.executable, "-m", "pkg.callee", "--help"], check=True)\n',
        encoding="utf-8",
    )
    assert _classes(tmp_path) == set()


# ------------------------------------------------------------------------------------------------
# the denominator, and the refusal that protects it
# ------------------------------------------------------------------------------------------------


def test_every_class_reports_a_population_even_when_excluded():
    """An exclusion that also stops counting is indistinguishable from a detector someone deleted.
    Every class is keyed into the population up front for exactly this reason."""
    inv = _live()
    for cls in (*g.ENFORCED, *g.EXCLUDED):
        assert cls in inv.population
    assert inv.enforced_population > 0
    assert inv.excluded_population > 0
    assert inv.total_population == inv.enforced_population + inv.excluded_population


def test_a_tree_with_no_checkable_seam_refuses_rather_than_passing(tmp_path):
    """The whole reason `run()` declares a SECONDARY denominator. A tree where seams were
    enumerated but none was checkable has no yardstick, and 'I could not judge' must not be
    expressed as PASS. This estate's dominant defect is a check that passes having examined
    nothing."""
    (tmp_path / "reader.py").write_text(
        'def f(d):\n    return d["only_an_orphan_read"]\n', encoding="utf-8")
    inv = g.check(tmp_path)
    assert inv.total_population > 0 and inv.enforced_population == 0
    line, code = contract.verdict(g.NAME, g.run(tmp_path))
    assert code == 2 and "missing yardstick" in line


def test_the_verdict_line_prints_both_denominators(tmp_path):
    """A numerator with no denominator cannot be read. Both numbers are asserted because both are
    load-bearing: the population is the number nobody knew, the checked count is the yardstick."""
    g._clean(tmp_path)
    line, code = contract.verdict(g.NAME, g.run(tmp_path))
    assert code == 0
    assert "seam(s) enumerated examined" in line and "seam(s) checked" in line


def test_generated_trees_are_not_counted_twice(tmp_path):
    """`build/` holds COPIES of `tools/`, and counting a copy doubles every seam in it."""
    g._clean(tmp_path)
    before = g.check(tmp_path).total_population
    for skipped in ("build", "__pycache__", ".git"):
        (tmp_path / skipped).mkdir(parents=True, exist_ok=True)
        (tmp_path / skipped / "emitter.py").write_text(
            (tmp_path / "emitter.py").read_text(encoding="utf-8"), encoding="utf-8")
    assert g.check(tmp_path).total_population == before


# ------------------------------------------------------------------------------------------------
# the name-folding bug that made the detector report a population of 2
# ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "declared,folded",
    [
        ("credentialMode", "credential_mode"),
        ("credential_modes", "credential_mode"),
        ("CREDENTIAL_MODES", "credential_mode"),
        # The regression. Camel-splitting an all-caps name yields `p_r_o_v_e_n_a_n_c_e`, and since
        # every code-side vocabulary home in this estate is a module-level CONSTANT, that one bug
        # silently reduced the closed-vocabulary population from 11 pairings to 2.
        ("PROVENANCE", "provenance"),
        ("STATUSES", "status"),
        ("RULE_KINDS", "rule_kind"),
    ],
)
def test_a_declaration_name_folds_across_casing_conventions(declared, folded):
    assert g._norm(declared) == folded


def test_the_grammar_side_is_read_by_property_name(tmp_path):
    """The grammar home is found by the name of the property the enum constrains, not by its JSON
    pointer — `$defs/credentialMode` and a nested `properties/mode` are different homes and only
    the first is named after the fact it closes."""
    (tmp_path / "mac.schema.json").write_text(g._GRAMMAR, encoding="utf-8")
    enums = g._grammar_enums(tmp_path)
    assert "credential_mode" in enums
    assert "named_profile" in enums["credential_mode"][0][1]


def test_a_missing_grammar_is_an_empty_population_not_a_crash(tmp_path):
    """`sdk/gate/` is the home of gates that must run with nothing installed and nothing staged.
    A class whose home file is absent reports zero, and the SECONDARY refusal then does its job."""
    assert g._grammar_enums(tmp_path) == {}
    assert g._vocabulary_namespaces(tmp_path) == {}


# ------------------------------------------------------------------------------------------------
# THE RATCHET, over the live tree
# ------------------------------------------------------------------------------------------------

#: The disagreement this gate was RED on the day it landed, by (class, site). Recorded here so a
#: SECOND disagreement fails this suite while FIXING this one keeps it green. It is not an
#: exemption: `python3 -m sdk.gate.check_seam_agreement` exits 1 today and is meant to.
_RED_ON_ARRIVAL = {
    ("sql-column-not-emitted", "tools/mac_to_meta.py:193"),
}


def test_the_live_disagreement_set_may_only_shrink():
    live = {(f.cls, f.site) for f in _live().enforced_findings}
    new = live - _RED_ON_ARRIVAL
    assert not new, (
        "a NEW seam disagreement landed: "
        + "; ".join(f"{c} at {s}" for c, s in sorted(new))
        + " — the enforced floor is 0. Fix the seam; do not add it to _RED_ON_ARRIVAL."
    )


def test_the_gate_exits_one_exactly_when_it_has_a_finding():
    """The verdict and the exit code must agree. A gate that prints FAIL and exits 0 is worse than
    no gate, because the suite that wraps it reports green."""
    inv = _live()
    _line, code = contract.verdict(g.NAME, g.run(g.ROOT))
    assert code == (1 if inv.enforced_findings else 0)


def test_the_excluded_populations_are_declared_and_the_declaration_is_read():
    """The excluded classes get a ratchet of their own because they are where a new seam can HIDE:
    if `dict-key-orphan-read` climbs by 60, the enforced verdict does not move. Growth is DISCLOSED
    with its delta rather than failing, because these counts move with ordinary authoring — but the
    declaration has to exist and has to cover every excluded class, or the disclosure is vacuous."""
    assert set(g._EXCLUDED_STANDING) == set(g.EXCLUDED)
    inv = _live()
    for cls in g.EXCLUDED:
        assert inv.population[cls] > 0, f"{cls} enumerated nothing — detector deleted?"


def test_the_printed_line_discloses_every_exclusion(capsys):
    """An exclusion nobody sees is a silent exemption. Every excluded class, and the words NOT
    SCORED, must reach stdout on every run."""
    g._main_over(g.ROOT)
    out = capsys.readouterr().out
    for cls in g.EXCLUDED:
        assert cls in out
    assert out.count("NOT SCORED") >= len(g.EXCLUDED)
    assert "enumerated" in out
