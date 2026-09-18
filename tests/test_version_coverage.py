#!/usr/bin/env python3
"""THE BUMP TRAP, as a test.

Measured on this tree, 2026-09-18, with only `CURRENT` moved to the next generation:

    a consuming bundle      32/32 checked file(s) clean, 0 skipped   ->   4/4 checked file(s) clean, 28 skipped
    example_tpch_ontology   40/40 checked file(s) clean, 0 skipped   ->  26/26 checked file(s) clean, 14 skipped  (exit 0 BOTH times)

Coverage collapses, the headline error count does not move, and BOTH lines end in "clean".
The defect is not the skip — it is the SELF-NORMALISING DENOMINATOR: `checked = routed - skipped`
removes a file from the numerator AND the denominator at once, so the fraction re-normalises to
N/N at the exact moment it stops meaning anything.

These tests assert the two facts that make that unarmable:
  1. the CHECKED-FILE COUNT NEVER DROPS when CURRENT is bumped (the derivation is monotone), and
  2. every routed file accounts for itself (the partition), so the denominator cannot shrink silently.

They assert on COUNTS and VERDICTS, never on printed text — except the one test that exists to
prove the summary line carries its real denominator.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import validate_schema as VS  # noqa: E402
import version as V  # noqa: E402

LADDER = os.path.join(ROOT, 'tests', 'fixtures', 'version_ladder')

# The four rungs the fixture pins, and why each one is there.
LADDER_STAMPS = {
    '0.1.14-develop': 'the PRE-RELEASE spelling of CURRENT — the first thing a bump evicts',
    '0.1.14': 'the RELEASED spelling of CURRENT — what bundle files carry',
    '0.1.13': 'one generation behind CURRENT — the largest cohort on disk',
    '0.1.9': 'the declared FLOOR — falls out first if a derivation miscomputes its base',
}

# The ladder of hypothetical bumps. A patch-only ladder is not enough: a derivation can be monotone
# within a line and still lose the whole 0.1.x line at 0.2.0, which is where 0.1.13's cohort lives.
BUMPS = ['0.1.14', '0.1.15-develop', '0.1.15', '0.1.19-develop', '0.2.0-develop', '1.0.0']


def _recognized_at(current):
    """The recognized set the gate WOULD hold if CURRENT were `current`.

    The `getattr` fallback is deliberate and permanent: it reproduces, exactly, the hand-typed
    literal this file was written to kill —

        RECOGNIZED = {CURRENT, CURRENT.split('-')[0], '0.1.13', '0.1.12', '0.1.11', '0.1.10', '0.1.9'}

    so this test is REPRODUCIBLY BORN RED against the pre-derivation code rather than merely
    erroring with AttributeError. Delete the fallback only when the literal can no longer return.
    """
    fn = getattr(VS, 'recognized_for', None)
    if fn is None:
        return {current, current.split('-')[0], '0.1.13', '0.1.12', '0.1.11', '0.1.10', '0.1.9'}
    return fn(current)


def _checked(root, current=None):
    """(checked_count, {path: stamp} for every routed file that was NOT checked).

    `checked` counts files the validator actually put through jsonschema. It is computed from the
    verdicts, never from a printed fraction.
    """
    enum = VS.enumerate_bundle(root)
    schema = VS.load_schema()
    saved_cur, saved_rec = VS.CURRENT, VS.RECOGNIZED
    try:
        if current is not None:
            VS.CURRENT, VS.RECOGNIZED = current, _recognized_at(current)
        verdicts = VS.validate_files(enum, schema)
    finally:
        VS.CURRENT, VS.RECOGNIZED = saved_cur, saved_rec
    unchecked = {v.path: v.schema_version for v in verdicts if v.skipped}
    checked = sum(1 for v in verdicts if not v.skipped and not v.parse_error)
    return checked, unchecked, enum, verdicts


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# 1. THE TEST THAT DEFINES DONE — the checked-file count must not drop on a bump.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def test_fixture_is_relevant():
    """The fixture must actually hold the rungs a bump evicts, or the bump test is vacuous.

    A uniform-0.1.13 bundle does not fall under a bump at all (measured: example_shop 21 -> 21), so
    a test fixtured on one would be born GREEN on broken code and prove nothing.
    """
    checked, unchecked, enum, verdicts = _checked(LADDER)
    assert checked > 0, 'empty denominator: the ladder fixture routed nothing'
    assert not unchecked, f'the ladder must be fully checked TODAY; unchecked: {unchecked}'
    stamps = {v.schema_version for v in verdicts}
    missing = set(LADDER_STAMPS) - stamps
    assert not missing, (
        f'the ladder fixture has drifted out of relevance — no routed file carries {sorted(missing)}.\n'
        + '\n'.join(f'  {s}: {why}' for s, why in LADDER_STAMPS.items()))


@pytest.mark.parametrize('bumped', BUMPS)
def test_checked_count_does_not_drop_on_a_bump(bumped):
    """THE assertion. Bump CURRENT; the number of files actually validated must not fall."""
    before, _, _, _ = _checked(LADDER)
    assert before > 0, 'non-vacuous denominator required'
    after, evicted, _, _ = _checked(LADDER, current=bumped)
    assert after >= before, (
        f'BUMP TRAP: CURRENT {VS.CURRENT} -> {bumped} evicted {before - after} of {before} '
        f'routed file(s) from validation, and the printed fraction would re-normalise to '
        f'{after}/{after} "clean".\n  evicted:\n'
        + '\n'.join(f'    {stamp!r:18} {os.path.relpath(p, LADDER)}'
                    for p, stamp in sorted(evicted.items(), key=lambda kv: kv[1])))


def test_the_pre_release_and_base_pair_both_resolve_across_a_bump():
    """CONFORMANCE's own incident: "63 files silently skipped, which is worse than a red."

    While develop is open on 0.1.14-develop, bundle files carry the RELEASED number 0.1.14. Both
    spellings must be recognized, and must STAY recognized after the next generation opens.
    """
    for current in (VS.CURRENT, '0.1.15-develop', '0.2.0-develop'):
        rec = _recognized_at(current)
        assert '0.1.14' in rec, f'released spelling 0.1.14 lost at CURRENT={current}'
        assert '0.1.14-develop' in rec, f'pre-release spelling 0.1.14-develop lost at CURRENT={current}'


def test_derived_set_is_a_superset_of_the_hand_typed_literal():
    """The floor is load-bearing: 0.1.13 carries the largest cohort on disk. Whatever replaces the
    literal must recognize everything the literal did, or files change state at the moment of the fix."""
    literal = {VS.CURRENT, VS.CURRENT.split('-')[0],
               '0.1.13', '0.1.12', '0.1.11', '0.1.10', '0.1.9'}
    rec = _recognized_at(VS.CURRENT)
    missing = {v for v in literal if v not in rec}
    assert not missing, f'the derivation NARROWS the recognized set — lost: {sorted(missing)}'


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# 2. AN UNRECOGNIZED VERSION IS A FINDING, NOT A SILENT SKIP.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _bundle(tmp_path, name, stamp):
    d = tmp_path / 'concepts' / name
    d.mkdir(parents=True, exist_ok=True)
    sv = f", schema_version: '{stamp}'" if stamp is not None else ''
    (d / f'{name}.yaml').write_text(
        f"metadata: {{ concept: {name.title()}, source: T, version: '1.0'{sv},"
        f" status: production, owner: t }}\n"
        f"concept:\n  name: {name.title()}\n  label: {name.title()}\n  class: entity\n"
        f"  definition: \"synthetic\"\n"
        f"grounding: {{ kind: sql_table, table: {name}_rows, schema: s, key_column: {name}_id }}\n")
    return str(tmp_path)


def test_an_unrecognized_stamp_is_a_counted_finding(tmp_path):
    """Today it degrades to a skip that the summary mentions mid-sentence. It must become a
    distinct, counted, named class."""
    root = _bundle(tmp_path, 'alpha', '0.1.6')
    _, _, enum, verdicts = _checked(root)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.skipped, 'a below-floor stamp must not be validated as if it conformed'
    assert getattr(v, 'unchecked_reason', None) == 'stamp-not-recognized', (
        f'the finding must NAME its reason, not just set a boolean; got '
        f'{getattr(v, "unchecked_reason", "<no such field>")!r}')


def test_a_missing_stamp_is_its_own_finding_class(tmp_path):
    """A MISSING stamp and an OLD stamp want different remedies (add the stamp / fix the routing,
    versus reconform the file). Today `sv not in RECOGNIZED` catches '' by accident and throws the
    distinction away. Measured: one such file was hiding six real schema errors."""
    root = _bundle(tmp_path, 'beta', None)
    _, _, _, verdicts = _checked(root)
    assert getattr(verdicts[0], 'unchecked_reason', None) == 'no-stamp', (
        f'got {getattr(verdicts[0], "unchecked_reason", "<no such field>")!r}')


def test_every_routed_file_produces_exactly_one_verdict(tmp_path):
    """THE PARTITION. A routed file that yields no verdict vanishes from both terms of the fraction
    — the same self-normalising defect one layer down. Today `if not isinstance(doc, dict): continue`
    drops such a file silently; measured, one live file in the estate does exactly this."""
    root = _bundle(tmp_path, 'gamma', '0.1.13')
    (tmp_path / 'concepts' / 'gamma' / 'listy.yaml').write_text('- one\n- two\n')
    enum = VS.enumerate_bundle(root)
    verdicts = VS.validate_files(enum, VS.load_schema())
    assert len(verdicts) == len(enum.routed), (
        f'{len(enum.routed) - len(verdicts)} routed file(s) produced NO verdict and are invisible to '
        f'every count the gate prints:\n  '
        + '\n  '.join(sorted(set(os.path.relpath(f, root) for f in enum.routed)
                             - set(os.path.relpath(v.path, root) for v in verdicts))))
    reasons = {os.path.basename(v.path): getattr(v, 'unchecked_reason', None) for v in verdicts}
    assert reasons.get('listy.yaml') == 'not-a-mapping', f'got {reasons!r}'


def test_an_exempt_register_may_omit_a_stamp_but_not_carry_a_wrong_one(tmp_path):
    """Registers are exempt from the version gate — which today means a register carrying a stamp
    the framework does not recognize is never looked at. Measured: one live file stamps '0.1',
    a version MAC has never had, and nothing anywhere says so."""
    (tmp_path / 'interventions').mkdir(parents=True)
    (tmp_path / 'interventions' / 'vanilla_delta.yaml').write_text(
        "metadata: { register: vanilla_delta, source: T, schema_version: '0.1' }\nentries: []\n")
    enum = VS.enumerate_bundle(str(tmp_path))
    verdicts = VS.validate_files(enum, VS.load_schema())
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.definition == 'VanillaDeltaFile'
    assert not v.skipped, 'an exempt file is still VALIDATED — the exemption is from the version gate only'
    assert getattr(v, 'stamp_error', None), (
        "a register carrying an unrecognized stamp must be a finding; registers may OMIT the stamp, "
        "they may not carry a wrong one")


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# 3. THE SUMMARY PRINTS THE REAL DENOMINATOR.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _run_gate(root, current=None, floor=None):
    """Render a run the way the gate renders it, in-process.

    Deliberately NOT a subprocess with an environment override: an env var that moves CURRENT is a
    back door into a gate, and a gate with a back door is not a gate. `report()` is a pure function
    over (enumeration, verdicts) precisely so this can be asserted without one.
    """
    enum = VS.enumerate_bundle(root)
    saved = VS.CURRENT, VS.RECOGNIZED
    try:
        if current is not None:
            VS.CURRENT = current
            VS.RECOGNIZED = (V.recognized(current, floor) if floor
                             else _recognized_at(current))
        verdicts = VS.validate_files(enum, VS.load_schema())
        return VS.report(enum, verdicts)[::-1]        # (exit_code, lines)
    finally:
        VS.CURRENT, VS.RECOGNIZED = saved


def test_summary_denominator_is_routed_and_does_not_renormalise():
    """"4 of 32", never "4/4". The denominator must be `routed`, which the recognized set cannot move."""
    rc_before, out_before = _run_gate(LADDER)
    rc_after, out_after = _run_gate(LADDER, current='0.1.15-develop')
    tail_before, tail_after = out_before[-1], out_after[-1]
    routed = len(VS.enumerate_bundle(LADDER).routed)
    assert f'of {routed} routed' in tail_before, f'no real denominator in:\n  {tail_before}'
    assert f'of {routed} routed' in tail_after, (
        f'the denominator MOVED under a bump — it re-normalised:\n  before: {tail_before}\n'
        f'  after:  {tail_after}')


def test_unchecked_is_a_block_not_a_clause():
    """"make the skipped count impossible to miss rather than a clause mid-sentence" (operator)."""
    # Floor AND ceiling pinned below every rung: nothing in the ladder is recognized any more.
    rc, out = _run_gate(LADDER, current='0.1.6', floor='0.1.6')
    assert rc != 0, 'a bundle where nothing was validated must never exit 0'
    assert any(line.startswith('UNCHECKED') for line in out), (
        'the unchecked count must open its own block:\n  ' + '\n  '.join(out[-6:]))


def test_verdict_token_carries_its_denominator():
    """Estate rule: never a PASS without its denominator."""
    rc, out = _run_gate(LADDER)
    tail = out[-1]
    assert tail.split(':')[0] in ('PASS', 'FAIL', 'EMPTY'), f'no verdict token in:\n  {tail}'


def test_zero_routed_files_is_never_a_pass(tmp_path):
    """"0/0 checked file(s) clean" over a repo with a yaml file in it — the estate's own
    PASS-on-zero-files failure mode, printed by this very gate today. N of N stops
    self-normalising only when N cannot be zero."""
    (tmp_path / 'notes.yaml').write_text('a: 1\n')
    rc, out = _run_gate(str(tmp_path))
    assert rc != 0, f'exit 0 over zero routed files:\n  ' + '\n  '.join(out[-3:])


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# 4. THE DERIVATION'S OWN GUARDS.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def test_current_below_floor_raises_and_never_returns_an_empty_set():
    """`range(floor, current+1)` is EMPTY when current < floor, with no exception — an empty
    recognized set validates nothing while printing a perfect fraction. The literal had no such
    failure mode, so the derivation must not introduce one."""
    with pytest.raises(V.VersionLineError):
        V.recognized('0.1.8-develop', floor='0.1.9')


def test_recognized_requires_current_and_never_reads_it_from_disk():
    """VERSION-vs-claims disagreement is exactly what `version.py --check` polices, and it is RED
    today. A defaulted `current` would make the recognized ceiling depend on a file already known
    to disagree — a new silent path for the ceiling to move."""
    with pytest.raises(TypeError):
        V.recognized()


def test_the_prerelease_alphabet_and_the_grammar_cannot_disagree():
    """The suffix alphabet is DERIVED from one declaration, not scraped out of a compiled regex:
    a scrape yields a bogus member on `(-develop|-rc)?`, an unenumerable one on `(-[a-z]+)?`, and
    the WRONG GROUP on `(-develop)?(\\+\\w+)?` — that last one drops '-develop' entirely."""
    for suffix in V.PRERELEASE:
        assert V.SEMVER.match(f'0.1.9{suffix}'), f'PRERELEASE member {suffix!r} is not in the grammar'
    assert not V.SEMVER.match('0.1.9-rc1'), 'the grammar admits a suffix outside PRERELEASE'
    for suffix in V.PRERELEASE:
        assert f'0.1.9{suffix}' in V.recognized('0.1.9', floor='0.1.9')


def test_a_line_migration_does_not_drop_the_closed_line():
    """0.2.0 must not convert every 0.1.x file into a finding in one commit. Membership is an
    ORDER, not an enumeration, so a closed line stays inside the range for free."""
    rec = V.recognized('0.2.0-develop', floor='0.1.9')
    for v in ('0.1.9', '0.1.13', '0.1.14', '0.1.14-develop', '0.2.0', '0.2.0-develop'):
        assert v in rec, f'{v} fell out of the recognized range at a minor-line bump'
    assert '0.1.8' not in rec, 'the floor stopped holding'


def test_a_malformed_stamp_is_not_recognized():
    """A bare '0.1' is neither an old generation nor inside the range — it does not parse. It must
    be unrecognized rather than quietly admitted by a loose comparison."""
    rec = V.recognized(VS.CURRENT, floor='0.1.9')
    assert '0.1' not in rec
    assert 'latest' not in rec
    assert '' not in rec
