#!/usr/bin/env python3
"""check_cookbook_smells — the MODELLERS_COOKBOOK anti-patterns, enforced instead of described.

WHY THIS EXISTS
---------------
MAC has diagnosed these for months, in prose, in MODELLERS_COOKBOOK.md Part C. Nothing checked them.
Measured on gaps/fpl2 over one working session, every substantive finding was already an entry:

    13 copies of ONE refusal law              -> C6  exploding rule-count
    15 rules restating what measure_type says -> C2  a rule for a stored value
    additivity in concept + registry + law    -> C1  the same fact in two layers
    17 concepts stamped C, none reviewed      -> C7  "validates cleanly" treated as correct

C7 became MAC006 and C1 became MAC003. C2 and C6 stayed prose, and they are the two that produced the
most work: a reader found them one at a time, by hand, each time from scratch.

A cookbook is not a guardrail. This is the guardrail.

C6 — EXPLODING RULE-COUNT
  The same rule SHAPE (the id after the concept prefix) written on many concepts is the smell. The
  cookbook's own words: "a rising exception-count is a failing test for the data model", and "one
  genuine foundational rule is fine; a PILE of them is the signal."

  Reported at >= 5 concepts. Not 2 or 3: a shape on two concepts is a coincidence, on three a pattern,
  and by five it is a law nobody has stated. fpl2's shapes at the time this shipped: 13, 8, 7, 5, 5.

C2 — A RULE FOR A STORED VALUE
  A rule whose `then` only READS something already declared — no derivation, no computation. The
  cookbook: "stored values that are merely filtered/aggregated need NO rule; the rules layer is for
  computed things only." Detected by a `then` that cites a slot the concept itself declares
  (measure_type, additivity, grain, closure) while its verb is only read/filter/select.

WHAT THESE WOULD FALSELY FIRE ON, and the legitimate case that must not fire
---------------------------------------------------------------------------
* C6 on a shape that is genuinely per-concept every time. LEGITIMATE: `resolve.kpi_code` looked like
  one until its parts were separated — and turned out to be derivable after all. The check reports a
  CANDIDATE and says what to do with it; it never asserts the rules are wrong. Warning, never error.
* C6 on rules already bound to a canon: those ARE the single-homed form, so a bound shape is exempt.
  Without that exemption fpl2's 13 exclusion rules would be reported forever after being fixed.
* C2 on a rule that reads a stored value AND adds a real constraint (a default, a disambiguation).
  Hence the verb test: a `then` containing derive/compute/sum/collapse/refuse is never reported.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

import mac_diag as D

SHAPE_THRESHOLD = 5
_DECLARED_SLOTS = ("measure_type", "additivity", "grain", "closure", "axis_kind")
_COMPUTE_VERBS = ("derive", "comput", "sum ", "collapse", "refuse", "rollup", "roll up",
                  "average", "ratio", "divide", "pivot")


def _rules(root):
    import yaml
    for f in sorted((Path(root) / "ontology" / "concepts").glob("*.yaml")):
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:                                               # noqa: BLE001
            continue
        for r in ((doc.get("contract") or {}).get("rules") or []):
            if isinstance(r, dict) and r.get("id"):
                yield str(f.relative_to(root)), doc, r


def check_cookbook_smells(root) -> list:
    out, shapes, stored = [], collections.defaultdict(list), []
    for rel, doc, r in _rules(root):
        rid = str(r["id"])
        shape = ".".join(rid.split(".")[1:]) or rid
        if not r.get("realized_by"):        # a bound shape is already single-homed — exempt (see above)
            shapes[shape].append(D.Witness(file=rel, path=rid))
        then = " ".join(str(r.get("then") or "").split()).lower()
        if then and not any(v in then for v in _COMPUTE_VERBS):
            cited = [s for s in _DECLARED_SLOTS if s in then]
            if cited:
                stored.append(D.Witness(file=rel, path=rid,
                                        detail=f"`then` only reads {', '.join(cited)}, which the "
                                               f"concept already declares"))

    for shape, ws in sorted(shapes.items(), key=lambda kv: -len(kv[1])):
        if len(ws) < SHAPE_THRESHOLD:
            continue
        out.append(D.Diagnostic(
            code="MAC003", severity=D.WARNING, source="check_cookbook_smells",
            summary=f"rule shape `{shape}` is written on {len(ws)} concepts — COOKBOOK C6, a law "
                    f"nobody has stated",
            note="Either bind them to a canon so the law lives once (realized_by), or lift the law to "
                 "mac_rules.yaml if it holds for every ontology. The cookbook's test: a rising "
                 "exception-count is a failing test for the data model, not business logic.",
            witnesses=ws))
    if stored:
        out.append(D.Diagnostic(
            code="MAC003", severity=D.WARNING, source="check_cookbook_smells",
            summary=f"{len(stored)} rule(s) only READ a fact the concept already declares — COOKBOOK C2",
            note="The rules layer is for COMPUTED things. A rule that restates measure_type, "
                 "additivity, grain or closure adds a second home for a fact and can drift from it — "
                 "which is how eight fpl2 rules came to guard on a token no register held.",
            witnesses=stored))
    return out


def main() -> int:                                                      # pragma: no cover
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    d = check_cookbook_smells(root)
    print(D.render(d, root, show=D.INFO) or "check_cookbook_smells: no findings")
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
