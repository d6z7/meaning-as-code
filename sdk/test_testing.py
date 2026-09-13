"""The denominator assertions must themselves refuse a zero denominator.

A helper that exists to catch vacuous passes is worthless if IT can pass vacuously, so each refusal
is exercised directly rather than assumed.
"""

import pytest

from sdk.testing import assert_absent_from, assert_clean_over


def test_clean_over_a_real_denominator_passes():
    assert_clean_over([], examined=7, what="file")


def test_clean_over_zero_is_refused_even_though_findings_are_empty():
    with pytest.raises(AssertionError, match="ZERO-DENOMINATOR"):
        assert_clean_over([], examined=0, what="file")


def test_clean_over_reports_the_findings_it_got():
    with pytest.raises(AssertionError, match="2 finding"):
        assert_clean_over(["a", "b"], examined=5, what="file")


def test_absent_from_an_empty_set_is_refused():
    with pytest.raises(AssertionError, match="ZERO-DENOMINATOR"):
        assert_absent_from("x", [])


def test_absent_from_a_real_set_passes_and_catches_presence():
    assert_absent_from("x", ["a", "b"])
    with pytest.raises(AssertionError, match="is present"):
        assert_absent_from("a", ["a", "b"])
