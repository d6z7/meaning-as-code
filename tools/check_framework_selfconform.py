#!/usr/bin/env python3
"""check_framework_selfconform — MAC holds ITSELF to the standard it enforces on bundles.

WHY
---
The framework governs bundle files strictly: every artifact needs a definition (MAC001), unknown keys
fail `additionalProperties: false`, an undeclared `x-` key is MAC009. Its OWN files had almost none of
that:

    mac_shapes.yaml       -> mac.shapes.schema.json      governed
    mac_vocabulary.yaml   -> nothing
    mac_rules.yaml        -> nothing

Measured, on this toolchain, in one session. Every construct invented by an assistant went into a file
nothing validated:

    conformance.out_of_scope   into mac.project.yaml, which HAD NO DEFINITION — and was then
                               exempted from the undefined-artifact check by a hardcoded basename
    applies_to                 into mac_rules.yaml, created minutes earlier without a schema
    params_from_concept        same file, same absence
    bundle_may_supply          same file, same absence

All four were caught by a human reading them, which is not a control. `additionalProperties: false`
on a schema this gate runs would have rejected three of them at the moment of writing, and the fourth
the moment the manifest got a definition.

A framework that enforces single-homing, closed vocabularies and no-undeclared-keys on its customers
while exempting itself is not strict — it is strict about other people.

WHAT IT WOULD FALSELY FIRE ON, and the legitimate case that must not fire
------------------------------------------------------------------------
* A framework file that legitimately grows a new key. That is the POINT: growth goes through the
  schema, in the same commit, which is the rule this gate exists to enforce ("invent under x-, prove
  it, promote it" — CONFORMANCE §2). It is an error, not a warning, because the alternative is what
  happened above.
* A schema that is missing entirely. Reported as UNGOVERNED rather than silently passing — an absent
  schema is exactly how mac_rules.yaml grew three invented keys.
"""
from __future__ import annotations

import sys
from pathlib import Path

import mac_diag as D

_ROOT = Path(__file__).resolve().parent.parent
GOVERNED = {
    "mac_shapes.yaml": "mac.shapes.schema.json",
    "mac_vocabulary.yaml": "mac.vocabulary.schema.json",
    "mac_rules.yaml": "mac.rules.schema.json",
}


def check_framework_selfconform(root=None) -> list:
    import json
    import yaml
    import jsonschema.validators as jsv
    ungoverned, invalid = [], []
    for fname, sname in sorted(GOVERNED.items()):
        f, s = _ROOT / fname, _ROOT / sname
        if not f.exists():
            continue
        if not s.exists():
            ungoverned.append(D.Witness(file=fname, detail=f"no schema ({sname} absent) — any key "
                                                           f"may be invented here unchallenged"))
            continue
        try:
            schema = json.loads(s.read_text(encoding="utf-8"))
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
            for e in sorted(jsv.validator_for(schema)(schema).iter_errors(doc),
                            key=lambda x: list(x.path)):
                invalid.append(D.Witness(file=fname, path="/".join(map(str, e.path)) or "(root)",
                                         detail=e.message[:150]))
        except Exception as exc:                                        # noqa: BLE001
            invalid.append(D.Witness(file=fname, detail=f"could not be validated: {exc!r}"))
    out = []
    if ungoverned:
        out.append(D.Diagnostic(
            code="MAC001", severity=D.ERROR, source="check_framework_selfconform",
            summary=f"{len(ungoverned)} framework file(s) carry no schema — the framework is not "
                    f"holding itself to the rule it enforces on every bundle",
            witnesses=ungoverned))
    if invalid:
        out.append(D.Diagnostic(
            code="MAC002", severity=D.ERROR, source="check_framework_selfconform",
            summary=f"{len(invalid)} violation(s) of the framework's own schemas",
            note="A key the schema does not define is an INVENTION. Add it to the schema in the same "
                 "change, or do not write it — CONFORMANCE §2: invent under x-, prove it, promote it.",
            witnesses=invalid))
    return out


def main() -> int:                                                      # pragma: no cover
    d = check_framework_selfconform()
    print(D.render(d, str(_ROOT), show=D.INFO) or "check_framework_selfconform: no findings")
    return 1 if any(x.severity == D.ERROR for x in d) else 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
