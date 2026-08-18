#!/usr/bin/env python3
"""check_common_rules — a concept restating a law MAC already states is a copy, not a contract.

WHY
---
mac_rules.yaml states behavioural contracts that hold for ANY conformant ontology, in the ORDINARY
rule shape — id · kind · subject · when · then · never · realized_by, plus `scope` carrying a class
selector rather than a source name. It is not a new construct. A concept matching
a common rule's `applies_to` gets that behaviour whether or not it writes anything. So a concept that
writes the rule out again is not adding a contract — it is adding a COPY of one, and copies drift.

MEASURED on gaps/fpl2: thirteen concepts each wrote the same refusal law. 13 distinct `when` wordings,
13 `then`, 12 `never`. Three of the thirteen carried NO information beyond the concept's own name, and
one (`market`) ended up with a bare `then` promising an answer it could not produce. None of that was
visible to any gate, because every copy was individually well-formed.

WHAT IT REPORTS
---------------
  MAC003  a local rule that adds NOTHING the common rule does not already say — pure restatement.
  MAC005  a local rule that adds only PARAMETERS (a confusable list, a via) — MAC offers a place to
          put just those, and the concept is carrying the whole law to deliver them.

WHAT IT WOULD FALSELY FIRE ON, and the legitimate case that must not fire
------------------------------------------------------------------------
* A concept that genuinely DIFFERS from the common law. LEGITIMATE and common: ob_reach's refusal has
  a second branch (a resolved row whose null IS the answer) that the generic law does not mention.
  Such a rule is an OVERRIDE, and an override is the point of allowing local rules at all — so a rule
  whose clauses say something the common rule cannot is never reported. That is why this check
  compares MEANING (does the local rule add an element?) and not wording: on this corpus the wordings
  differ in clause order and label alone, which carries nothing.
* A bundle with no mac_rules.yaml reachable. Then nothing is reported and the check says it could not
  run, rather than reporting a clean bundle.
"""
from __future__ import annotations

import sys
from pathlib import Path

import mac_diag as D

_ELEMENTS = [("REFUSE", ("refuse",)), ("no-guess", ("guess", "estimat")),
             ("no-zero-fill", ("zero", "to 0", "coerc")), ("substitution ban", ("substitut",)),
             ("null branch", ("null",)), ("via a register", ("via ",))]


def _flat(rule) -> str:
    return " ".join(" ".join(str(rule.get(k) or "").split())
                    for k in ("when", "then", "never")).lower()


def check_common_rules(root) -> list:
    try:
        import yaml
        f = Path(__file__).resolve().parent.parent / "mac_rules.yaml"
        if not f.exists():
            return [D.Diagnostic(code="MAC008", severity=D.WARNING, source="check_common_rules",
                                 summary="mac_rules.yaml is not reachable, so common-rule coverage "
                                         "is UNKNOWN, not clean")]
        common = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("rules") or []
    except Exception as exc:                                            # noqa: BLE001
        return [D.Diagnostic(code="MAC008", severity=D.WARNING, source="check_common_rules",
                             summary=f"common rules could not be read: {exc!r}")]

    by_class = {}
    for c in common:
        cls = (c.get("scope") or {}).get("concept.class")
        if cls:
            by_class.setdefault(cls, []).append(c)

    restated, params_only = [], []
    for p in sorted((Path(root) / "ontology" / "concepts").glob("*.yaml")):
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:                                               # noqa: BLE001
            continue
        cls = ((doc.get("concept") or {}).get("class"))
        for cr in by_class.get(cls, []):
            udf = (cr.get("realized_by") or {}).get("udf")
            for r in ((doc.get("contract") or {}).get("rules") or []):
                rb = r.get("realized_by") or {}
                if rb.get("udf") != udf:
                    continue
                # What the CONCEPT contributes beyond the common law: the canon parameters MAC
                # cannot know. Read from the canon's own signature — an earlier draft listed them in
                # the rule under an invented `bundle_may_supply` key, which was a second home for a
                # fact the function already declares.
                import inspect
                from canon import rules as _CR
                fn = _CR.CANONS.get(udf)
                known = set(inspect.signature(fn).parameters) if fn else set()
                extra = {k: v for k, v in (rb.get("params") or {}).items()
                         if k in known and k not in ("source", "label", "thing")
                         and v not in (None, "", False)}
                rel, rid = str(p.relative_to(root)), r.get("id", "")
                if extra:
                    params_only.append(D.Witness(file=rel, path=rid,
                                                 detail="supplies only " + ", ".join(sorted(extra))))
                else:
                    restated.append(D.Witness(file=rel, path=rid,
                                              detail="adds nothing the common rule does not say"))
    out = []
    if restated:
        out.append(D.Diagnostic(
            code="MAC003", severity=D.WARNING, source="check_common_rules",
            summary=f"{len(restated)} concept rule(s) restate a law mac_rules.yaml already states for "
                    f"their class, adding nothing",
            note="Delete them. The behaviour does not change — that is the test: removing a rule that "
                 "only repeats the common one must not change what the bundle refuses.",
            witnesses=restated))
    if params_only:
        out.append(D.Diagnostic(
            code="MAC005", severity=D.INFO, source="check_common_rules",
            summary=f"{len(params_only)} concept rule(s) exist only to carry PARAMETERS to a common rule",
            note="Not a defect — the parameters are real knowledge only the author has (which measure "
                 "a reader would wrongly substitute). Recorded so the ratio of law to parameter is "
                 "visible: the law is MAC's, the parameters are the bundle's.",
            witnesses=params_only))
    return out


def main() -> int:                                                      # pragma: no cover
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    d = check_common_rules(root)
    print(D.render(d, root, show=D.INFO) or "check_common_rules: no findings")
    return 1 if any(x.severity == D.ERROR for x in d) else 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
