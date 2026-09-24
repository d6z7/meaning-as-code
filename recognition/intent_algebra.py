"""Canonical form, equivalence and a per-field diff for ``Intent``.

CATEGORY **RECOGNITION** (TESTING.md §2), and the foundation everything in that category rests on.
PIPELINE_TESTING.md §3.0.

WHY IT IS NEEDED AT ALL. Two intents can MEAN the same query and not be equal: filters in a
different order, a slice list permuted, `operation` left for the planner to infer, `subject`
spelled through its `measure` alias, a period given as a phrase instead of a range. Comparing them
with `==` measures formatting.

WHAT IS DROPPED, AND WHY EACH. `utterance` is bookkeeping — the phrase the model says it matched,
which by construction differs between two PHRASINGS of one question and is exactly what a
stability check must not be sensitive to. `confidence` is the model's self-score, not part of what
was asked; two intents that ask the same thing with different certainty are the same intent (the
calibration instrument grades confidence separately, and that is the right home for it).

WHAT IS KEPT AND ORDERED. Filters and slices are SETS in meaning and lists in the model, so they
are sorted. Everything else is compared as given.

THE PER-FIELD DIFF IS THE POINT. A bare agreement rate says "the interpreter is 82 % stable" and
tells nobody what to fix. `diff()` names the field — subject, operation, filters, period — which
turns a rate into a confusion matrix. Spider's exact-set-match scores its clauses separately for
the same reason.

    python recognition/intent_algebra.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from typing import Any

#: Fields compared, in report order. `confidence` and every `utterance` are deliberately absent.
FIELDS = (
    "subject",
    "operation",
    "slices",
    "filters",
    "join_filters",
    "period",
    "ordering",
    "limit",
    "denominator",
)


def _scalar(v: Any) -> Any:
    """A value as it MEANS, not as it is typed. `5`, `5.0` and `"5"` are one filter value."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        try:
            return float(s)
        except ValueError:
            return s.casefold()
    if isinstance(v, (list, tuple)):
        return sorted((_scalar(x) for x in v), key=repr)
    return v


def _term(d: Any, keys: tuple[str, ...]) -> tuple:
    """One term as a comparable tuple, from EITHER the model's mapping or an already-canonical
    tuple. Accepting both is what makes `canon` idempotent — and idempotence is not decoration:
    without it nothing downstream can cache a canonical form, or canonicalise a stored one."""
    if not isinstance(d, Mapping):
        return tuple(_scalar(x) for x in d)
    return tuple(_scalar(d.get(k)) for k in keys)


def canon(intent: Any) -> dict[str, Any]:
    """The canonical form: a plain dict, order-normalised, bookkeeping removed."""
    d = intent if isinstance(intent, Mapping) else intent.model_dump(mode="json")
    subject = d.get("subject") or d.get("measure")
    op = d.get("operation")

    out: dict[str, Any] = {
        "subject": _scalar(subject) if subject is not None else None,
        "operation": _scalar(op) if op else None,
        "slices": sorted(
            (_term(s, ("term", "column")) for s in (d.get("slices") or [])), key=repr
        ),
        "filters": sorted(
            (_term(f, ("term", "op", "value")) for f in (d.get("filters") or [])), key=repr
        ),
        "join_filters": sorted(
            (
                _term(j, ("left_term", "op", "right_term", "right_column"))
                for j in (d.get("join_filters") or [])
            ),
            key=repr,
        ),
        "period": None,
        "ordering": None,
        "limit": d.get("limit"),
        "denominator": _scalar(d.get("denominator")) if d.get("denominator") else None,
    }
    period = d.get("period")
    if isinstance(period, (tuple, list)) and len(period) == 2:
        out["period"] = (str(period[0]), str(period[1]))
    elif isinstance(period, Mapping):
        # `raw` is the phrase the model echoed; the RANGE is what the query means. A period given
        # as "2024" and one given as [2024-01-01, 2025-01-01) are the same period.
        out["period"] = (str(period.get("start")), str(period.get("end")))
    ordering = d.get("ordering")
    if isinstance(ordering, (tuple, list)) and len(ordering) == 2:
        out["ordering"] = (_scalar(ordering[0]), _scalar(ordering[1]))
    elif isinstance(ordering, Mapping):
        out["ordering"] = (_scalar(ordering.get("by")), _scalar(ordering.get("direction")))
    return out


def equivalent(a: Any, b: Any) -> bool:
    return canon(a) == canon(b)


def diff(a: Any, b: Any) -> tuple[str, ...]:
    """The FIELDS on which two intents disagree. Empty means equivalent."""
    ca, cb = canon(a), canon(b)
    return tuple(f for f in FIELDS if ca.get(f) != cb.get(f))


def agreement(intents: list[Any]) -> tuple[bool, dict[str, int]]:
    """(all equivalent, field -> how many of the rest disagree with the first on that field).

    The FIRST intent is the reference on purpose: with k paraphrasings of one question there is no
    privileged reading, so any choice is arbitrary — but a fixed one keeps the per-field counts
    interpretable instead of quadratic.
    """
    if not intents:
        return True, {}
    counts: dict[str, int] = {}
    for other in intents[1:]:
        for f in diff(intents[0], other):
            counts[f] = counts.get(f, 0) + 1
    return (not counts), counts


# --------------------------------------------------------------------------- #
# The instrument's own test. Seeded pairs, one per thing canon must and must not ignore.
# --------------------------------------------------------------------------- #

_BASE = {
    "subject": "Store",
    "operation": "count",
    "filters": [{"term": "StoreStatus", "op": "ne", "value": "Closed", "utterance": "not closed"}],
    "slices": [],
    "confidence": 0.9,
}

_SELF_TEST: list[tuple[str, dict, dict, bool]] = [
    ("identical", _BASE, dict(_BASE), True),
    (
        "utterance differs — the whole point of a paraphrase",
        _BASE,
        {**_BASE, "filters": [{**_BASE["filters"][0], "utterance": "still trading"}]},
        True,
    ),
    ("confidence differs — a self-score, not a meaning", _BASE, {**_BASE, "confidence": 0.4}, True),
    (
        "`measure` alias spells `subject`",
        _BASE,
        {k: v for k, v in _BASE.items() if k != "subject"} | {"measure": "Store"},
        True,
    ),
    (
        "filter ORDER — a set in meaning, a list in the model",
        {**_BASE, "filters": [
            {"term": "A", "op": "eq", "value": "1", "utterance": ""},
            {"term": "B", "op": "eq", "value": "2", "utterance": ""}]},
        {**_BASE, "filters": [
            {"term": "B", "op": "eq", "value": "2", "utterance": ""},
            {"term": "A", "op": "eq", "value": "1", "utterance": ""}]},
        True,
    ),
    (
        "value TYPE — 5 and '5' are one filter value",
        {**_BASE, "filters": [{"term": "A", "op": "eq", "value": 5, "utterance": ""}]},
        {**_BASE, "filters": [{"term": "A", "op": "eq", "value": "5", "utterance": ""}]},
        True,
    ),
    (
        "period phrase vs range — same range, different `raw`",
        {**_BASE, "period": {"start": "2024-01-01", "end": "2025-01-01", "raw": "2024"}},
        {**_BASE, "period": {"start": "2024-01-01", "end": "2025-01-01", "raw": "last year"}},
        True,
    ),
    # --- and what it must NOT wave through -------------------------------------------------
    ("different subject", _BASE, {**_BASE, "subject": "Customer"}, False),
    ("different operation", _BASE, {**_BASE, "operation": "sum"}, False),
    (
        "operation ABSENT is not the same as stated — the planner may infer, but we cannot know",
        _BASE,
        {k: v for k, v in _BASE.items() if k != "operation"},
        False,
    ),
    (
        "different filter OPERATOR — eq and ne are the 58-vs-59 distinction",
        _BASE,
        {**_BASE, "filters": [{**_BASE["filters"][0], "op": "eq"}]},
        False,
    ),
    ("different filter value", _BASE, {**_BASE, "filters": [
        {**_BASE["filters"][0], "value": "Restructured"}]}, False),
    ("an extra filter narrows the question", _BASE, {**_BASE, "filters": [
        _BASE["filters"][0], {"term": "Country", "op": "eq", "value": "DE", "utterance": ""}]},
        False),
    ("a slice changes the shape of the answer", _BASE, {**_BASE, "slices": [
        {"term": "Country", "utterance": "by country"}]}, False),
    ("different period", {**_BASE, "period": {"start": "2024-01-01", "end": "2025-01-01"}},
     {**_BASE, "period": {"start": "2023-01-01", "end": "2024-01-01"}}, False),
    ("different limit", {**_BASE, "limit": 5}, {**_BASE, "limit": 10}, False),
]


def _self_test() -> int:
    bad = 0
    for label, a, b, want_same in _SELF_TEST:
        got = equivalent(a, b)
        if got != want_same:
            bad += 1
            print(f"  FAIL  {label}")
            print(f"        wanted equivalent={want_same}, got {got}; diff={diff(a, b)}")
    # canon must be idempotent, or nothing downstream can cache or compare
    if canon(canon(_BASE)) != canon(_BASE):
        bad += 1
        print("  FAIL  canon is not idempotent")
    n = len(_SELF_TEST) + 1
    print(f"\n{'FAIL' if bad else 'OK'} — intent algebra self-test: {n - bad} of {n} behaved")
    print("  (one seeded case per thing canon must ignore, and per thing it must not)")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--canon", help="a JSON intent to print in canonical form")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if a.canon:
        print(json.dumps(canon(json.loads(a.canon)), indent=2, default=repr))
        return 0
    ap.error("nothing to do: pass --self-test or --canon")


if __name__ == "__main__":
    sys.exit(main())
