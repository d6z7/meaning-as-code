#!/usr/bin/env python3
"""check_canon_documented.py — the canon's THREE LISTS must agree.

A canon exists in three places and nothing has ever compared them:

  1. mac_vocabulary.yaml#canon.terms      — what the framework DEFINES
  2. reference_manual/rules_and_canons/**/*.md — what the manual DESCRIBES
  3. mac_runtime.canon.IMPLEMENTED        — what the runtime HONOURS

Measured 2026-09-25, and no two of the three agreed:

  in the vocabulary with NO page (7)   alias_resolve · enum_from_register · grouping_from_register
                                        refuse_measure_no_row · refuse_unresolvable_name
                                        relation_alias_resolve · resolve_by_register
  a page NOT in the vocabulary (2)     array_membership_guard · opaque_code_guard
  IMPLEMENTED with no page (2)         resolve_by_register · enum_from_register

THE LAST LINE IS THE ONE THAT MATTERS. `resolve_by_register` is what makes every name in every
bundle resolve — six concepts in contoso declare it — and it had no page, while ten canons nothing
implements had one. A reader looking for how resolution works found entries for behaviour that does
not exist and nothing for the behaviour that does.

WHAT IT CHECKS
  * every vocabulary member has a page                     (defined but undescribed)
  * every page is a vocabulary member                      (described but undefined)
  * every IMPLEMENTED canon is in both                     (shipped but unfindable)

Exit 0 when the three agree, 1 on any disagreement, 2 when a list cannot be read (REFUSED — a gate
that cannot see its subject must not report success).
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: PyYAML is not importable ({exc})")
        return 2

    vocab_file = ROOT / "mac_vocabulary.yaml"
    pages_dir = ROOT / "reference_manual" / "rules_and_canons"
    if not vocab_file.is_file() or not pages_dir.is_dir():
        print(f"REFUSED: need {vocab_file.name} and {pages_dir}")
        return 2

    block = (yaml.safe_load(vocab_file.read_text(encoding="utf-8")) or {}).get("canon") or {}
    # `terms:` is the vocabulary's key; `members:` is the older spelling some checkouts still carry.
    # Reading only `members` is how this gate reported "0 undescribed, 19 undefined" on a tree where
    # all 19 are defined — a wrong key reads as an empty vocabulary, which reads as a manual full of
    # canons nobody defined.
    defined = set(block.get("terms") if block.get("terms") is not None else block.get("members") or {})
    # ONE LEVEL DOWN, BY PATTERN. The pages moved to `canon/<serves>/<name>.md` on 2026-10-05 —
    # the directory now carries the same grouping the generated tree reads, so a canon's page sits
    # under the pattern it serves. A FLAT glob here measured ZERO described against 21 undescribed
    # the moment they moved, which is the shape of gate that reports on a population it cannot see.
    # `rglob` finds them at any depth, so this does not care if the grouping is re-cut later.
    #
    # README.md IS EXCLUDED BY NAME. A sub-index would otherwise be counted as a canon called
    # "README" and reported as a page the vocabulary does not define.
    # EXACTLY THE CANON PAGES: `<pattern>/<canon>.md`, one level down and no deeper. The directory
    # also carries the chapter (`README.md`) and, since 2026-10-05, the four other pages whose subject
    # is rules rather than one canon -- rule_engine, identity_and_rules, column_rulings,
    # refusals_and_findings, the_content_model. An rglob swept all six in and reported their stems as
    # canons the vocabulary does not define ("5 undefined"), which is the mirror of the flat glob that
    # reported 21 undescribed: both measured the wrong population and said so confidently. The
    # one-level glob IS the guardrail's declared population for manual_canon_page.
    # A PAGE MARKED `status: retired` DESCRIBES NOTHING, and that is how a canon leaves the standard.
    # RETIRED 2026-10-07: five terms were deleted from `mac_vocabulary.yaml#canon.terms` and from the
    # runtime registry — ambiguity_gate, closure_anomaly_check, exclusion_filter,
    # grouping_from_register, relation_alias_resolve. Deleting the term IS the enforcement:
    # `check_references` resolves every `realized_by.udf` against that namespace and an unknown canon is
    # an ERROR, so a binding to a retired canon refuses at the gate instead of parsing and deciding
    # nothing. But the PAGES had to stay exactly where they are: 28 pages link to those five, and a
    # moved page is a broken link (the estate's own rule — preserve the basename). So without this
    # filter the five would read as "described but undefined" forever, and the gate that proves the three
    # lists agree would be permanently red over a retirement it is supposed to be able to express.
    retired = set()
    described = set()
    for p in pages_dir.glob("*/*.md"):
        if p.stem == "README":
            continue
        head = p.read_text(encoding="utf-8", errors="replace")[:600]
        if re.search(r"^status: *retired\b", head, re.M | re.I):
            retired.add(p.stem)
        else:
            described.add(p.stem)

    try:
        _neighbours.ensure_runtime_on_path()
        from mac_runtime.canon import IMPLEMENTED
        honoured = {name.rsplit(".", 1)[-1] for name in IMPLEMENTED}
    except ImportError as exc:
        print(f"REFUSED: mac_runtime.canon is not importable ({exc}). A gate that cannot ask the "
              f"runtime what it honours must not report PASS.")
        return 2

    undescribed = sorted(defined - described)
    undefined = sorted(described - defined)
    unfindable = sorted(honoured - described)

    # THE RETIRED COUNT IS PRINTED, always. A canon that left the standard is not nothing: its page is
    # still on disk and still linked, and a reader who cannot see how many were retired cannot tell a
    # shrinking canon from a gate measuring the wrong population.
    print(f"canon: defined {len(defined)}   described {len(described)}   "
          f"implemented {len(honoured)}" + (f"   retired {len(retired)}" if retired else ""))

    if undescribed:
        print(f"\nDEFINED, NO PAGE ({len(undescribed)}) — the vocabulary promises a canon the manual")
        print("never explains, so an author meets the name with nowhere to read what it does.\n")
        for c in undescribed:
            mark = "  <-- AND IT IS IMPLEMENTED" if c in honoured else ""
            print(f"  {c}{mark}")

    if undefined:
        print(f"\nPAGE, NOT DEFINED ({len(undefined)}) — the manual describes a canon the framework")
        print("does not define. A concept naming it would not resolve as a reference.\n")
        for c in undefined:
            print(f"  {c}")

    if unfindable:
        print(f"\nIMPLEMENTED BUT UNDESCRIBED ({len(unfindable)}) — the runtime honours these TODAY and")
        print("the manual is silent. This is the worst of the three: working behaviour nobody can find.\n")
        for c in unfindable:
            print(f"  {c}")

    if not (undescribed or undefined or unfindable):
        print("OK — vocabulary, manual and runtime agree on every canon.")
        return 0
    print(f"\nFAIL — {len(undescribed)} undescribed, {len(undefined)} undefined, "
          f"{len(unfindable)} implemented-but-undescribed.")
    return 1


def _self_test() -> int:
    """The gate must catch each disagreement separately, and pass when the three lists agree."""
    def classify(defined: set[str], described: set[str], honoured: set[str]):
        return (len(defined - described), len(described - defined), len(honoured - described))

    cases = [
        ("all three agree", {"a"}, {"a"}, {"a"}, (0, 0, 0), 0),
        ("defined, no page", {"a", "b"}, {"a"}, set(), (1, 0, 0), 1),
        ("page, not defined", {"a"}, {"a", "b"}, set(), (0, 1, 0), 1),
        ("implemented, no page", {"a", "b"}, {"a"}, {"b"}, (1, 0, 1), 1),
        ("all three disagreements at once", {"a", "b"}, {"a", "c"}, {"b"}, (1, 1, 1), 1),
        ("empty everywhere", set(), set(), set(), (0, 0, 0), 0),
    ]
    bad = 0
    for label, d, p, h, want, want_exit in cases:
        got = classify(d, p, h)
        got_exit = 1 if any(got) else 0
        if got != want or got_exit != want_exit:
            bad += 1
            print(f"  FAIL  {label}: wanted {want} exit {want_exit}, got {got} exit {got_exit}")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
