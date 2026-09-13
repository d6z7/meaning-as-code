#!/usr/bin/env python3
"""Assertions that refuse to pass over nothing.

WHY THIS EXISTS. `assert gate.check(tree) == []` reads as "the gate found no leaks". It also passes
when the gate examined ZERO files, matched ZERO declared patterns, or was pointed at an empty
directory -- and those are indistinguishable from clean in the assertion. That is the estate's
dominant defect, the zero-denominator pass, reproduced inside the test suite meant to catch it.

It was not hypothetical here. `test_onboard` asserted a source-tree scan stayed clean "even though
the sidecar names a denylisted handle". When the handle register moved out of the repository, the
handle stopped being declared anywhere a test could see -- so the assertion held whether or not the
skip logic worked. The test would have passed with the feature deleted.

THE RULE: an emptiness assertion must state what was examined, and that number must be non-zero.

    assert_clean_over(gate.check(tree), examined=gate.examined(tree), what="text file")
    assert_clean_over(findings, examined=len(declared), what="declared handle")

Use `assert_absent_from` when the point is that ONE thing is missing from a NON-empty result -- the
denominator is then the result itself, and an empty result is a failure, not a pass.
"""

from __future__ import annotations

from typing import Iterable, Sized


def assert_clean_over(findings: Sized, *, examined: int, what: str = "item") -> None:
    """`findings` is empty AND `examined` is non-zero. Fails loudly when nothing was examined."""
    if examined <= 0:
        raise AssertionError(
            f"ZERO-DENOMINATOR PASS: 0 {what}(s) examined, so 'no findings' means 'nothing was "
            f"looked at'. The assertion would hold with the feature under test deleted."
        )
    n = len(findings)
    if n:
        raise AssertionError(f"expected clean over {examined} {what}(s); got {n} finding(s): {findings!r}")


def assert_absent_from(needle, haystack: Iterable, *, what: str = "result") -> None:
    """`needle` is not in `haystack`, and `haystack` is NOT empty.

    An empty haystack makes "not present" vacuous: it is absent from everything.
    """
    items = list(haystack)
    if not items:
        raise AssertionError(
            f"ZERO-DENOMINATOR PASS: the {what} set is empty, so '{needle!r} is absent' is vacuous."
        )
    if needle in items:
        raise AssertionError(f"expected {needle!r} absent from {len(items)} {what}(s); it is present")
