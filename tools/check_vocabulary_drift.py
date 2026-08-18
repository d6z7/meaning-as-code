#!/usr/bin/env python3
"""check_vocabulary_drift — a CLOSED vocabulary may not have its members re-listed in code.

WHY THIS EXISTS, measured 2026-08-18
------------------------------------
`mac_vocabulary.yaml#aggregation_effect` is declared `closed: true`, and its four members were
hand-copied into three separate Python files. One of those copies had drifted:

    vocabulary  : additive · point_in_time · averageable · non_aggregable
    project_model.py EFFECT map : ... + `semi_additive`   <- NEVER a member of the closed set

A ghost term, in the map that renders the wiki, invisible because nothing compared a code-side list
against the vocabulary it claims to implement. Four homes for one fact drift exactly the way copied
rules drift — and `closed: true` is a promise the toolchain was not keeping about itself.

WHAT IT CHECKS. Every `mac.<vocabulary>.<term>` literal appearing in tools/**.py must be a real member
of that vocabulary in mac_vocabulary.yaml. A literal naming a term the vocabulary does not define is
MAC008 (reference-unresolved): a reference that resolves to nothing.

WHAT IT WOULD FALSELY FIRE ON, and the legitimate case that must not fire
------------------------------------------------------------------------
* PROSE. A docstring narrating a RETIRED term — "v0.1.15 replaced point_in_time" — is documentation,
  not a reference, and it is exactly how a rename is explained to the next reader. LEGITIMATE CASE:
  the migration notes in this very commit. Hence only `mac.<vocab>.<term>` QUALIFIED literals count;
  a bare word in prose is invisible to this check by construction.
* A vocabulary this file cannot parse. Then the check reports that it could not run, and never that
  the bundle is clean — a checker that dies quietly reports a green tree.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import mac_diag as D

_ROOT = Path(__file__).resolve().parent.parent
_LITERAL = re.compile(r"\bmac\.([a-z_]+)\.([a-z_][a-z0-9_]*)\b")
# Diagnostic codes are written BARE — `MAC007`, never `mac.diagnostic_code.MAC007` — so the qualified
# pattern above cannot see them. They are a closed vocabulary like any other and drift the same way:
# a check emitting a code the taxonomy does not define produces a finding nobody can suppress, count
# or argue with by class.
_CODE = re.compile(r"\b(MAC\d{3})\b")


def _vocabularies() -> dict:
    import yaml
    doc = yaml.safe_load((_ROOT / "mac_vocabulary.yaml").read_text(encoding="utf-8")) or {}
    out = {}
    for name, block in doc.items():
        if not isinstance(block, dict):
            continue
        if block.get("kind") == "vocabulary" and isinstance(block.get("terms"), dict):
            out[name] = set(block["terms"])
        elif block.get("kind") == "value_domain" and isinstance(block.get("members"), dict):
            out[name] = set(block["members"])
    return out


def check_vocabulary_drift(root=None) -> list:
    try:
        vocab = _vocabularies()
    except Exception as exc:                                          # noqa: BLE001
        return [D.Diagnostic(code="MAC008", severity=D.WARNING, source="check_vocabulary_drift",
                             summary=f"could not read mac_vocabulary.yaml, so vocabulary drift is "
                                     f"UNKNOWN, not clean: {exc!r}")]
    bad = []
    for f in sorted((_ROOT / "tools").rglob("*.py")):
        if f.name == Path(__file__).name:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:                                             # noqa: BLE001
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for voc, term in _LITERAL.findall(line):
                if voc in vocab and term not in vocab[voc]:
                    bad.append(D.Witness(file=str(f.relative_to(_ROOT)), line=i,
                                         detail=f"mac.{voc}.{term} — `{voc}` has no member `{term}`"))
            for code in _CODE.findall(line):
                if "diagnostic_code" in vocab and code not in vocab["diagnostic_code"]:
                    bad.append(D.Witness(file=str(f.relative_to(_ROOT)), line=i,
                                         detail=f"{code} — diagnostic_code has no such member"))
    if not bad:
        return []
    return [D.Diagnostic(
        code="MAC008", severity=D.ERROR, source="check_vocabulary_drift",
        summary=f"{len(bad)} code literal(s) name a term their CLOSED vocabulary does not define",
        note="A closed vocabulary whose members are re-listed in code has N homes for one fact. Read "
             "the members from mac_vocabulary.yaml instead of copying them.",
        witnesses=bad)]


def main() -> int:                                                    # pragma: no cover
    diags = check_vocabulary_drift()
    print(D.render(diags, str(_ROOT), show=D.INFO) or "check_vocabulary_drift: no findings")
    return 1 if any(d.severity == D.ERROR for d in diags) else 0


if __name__ == "__main__":                                            # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
