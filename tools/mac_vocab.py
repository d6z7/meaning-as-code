#!/usr/bin/env python3
"""mac_vocab.py — THE ONE READER OF `mac_vocabulary.yaml`, and the reason its shape is free.

Operator, 2026-10-04, asked three times: "why cannot it be folded like concept?!?!?" — why is the
vocabulary a flat list of DOTTED keys (`concept.column.role:`) when a concept is nested? The answer was
never "it cannot be". It is that nothing stood between the file and its readers:

  MEASURED 2026-10-04. 25 top-level keys, 11 of them dotted (`concept.aggregation_effect`,
  `concept.axis_kind`, `concept.column.{query_use,role,identity,ruling,measure_type}`,
  `concept.{identity,rule}`, `relation.column.role`, `transform.driven_by`) folding under three roots,
  and 14 already single-segment. 9 modules load the file with their own `yaml.safe_load`, there was NO
  canonical loader, and ~30 sites index the result by the LITERAL dotted string — `vocab["concept.column.role"]`
  in check_vocabulary_parity, check_column_planes, gen_grammar_map, project_model, mac_model and more.
  So folding the file would have broken 30 lookups in 10 modules, one at a time, at a distance.

  And `gen_structure_reference`'s walker ALREADY joins nested keys —
  `walk(v, f"{path}.{k}" if path else str(k))` — so the generator would not have noticed the fold at
  all. The blocker was never the hard part; it was the thirty dict indexes nobody had a reader for.

SO THIS IS THAT READER. It accepts the file FOLDED or FLAT and always returns vocabularies keyed by
their DOTTED path, which is what every existing caller already expects. A folded `concept: column: role:`
and a flat `concept.column.role:` load to the same dict, so the file's shape becomes an authoring
decision instead of an API.

WHY DOTTED IS THE RETURNED FORM and not nested: a vocabulary's NAME is dotted everywhere it is used —
`mac.concept.column.role.measure` is how a concept spells a value, `check_vocabulary_parity.PAIRS` names
its slots that way, and the generated pages are addressed that way. The dotted path is the identity; the
nesting is how a person reads it. A reader should hand back the identity.
"""
from __future__ import annotations

import pathlib

#: A node with a `terms:` mapping IS a vocabulary. Anything above it is a path segment.
TERMS = "terms"


def _framework_root(explicit=None) -> pathlib.Path:
    if explicit is not None:
        return pathlib.Path(explicit)
    return pathlib.Path(__file__).resolve().parent.parent


def flatten(doc: dict) -> dict:
    """{dotted name -> the vocabulary node}, from a folded OR flat document.

    A node carrying `terms` is a vocabulary and its walk stops there — a term called `concept` must
    never be mistaken for a path segment. A top-level key that yields no vocabulary at all is passed
    through unchanged, so `metadata:` survives for the readers that want it.
    """
    out: dict = {}
    produced: set = set()

    def walk(node, path: str, root: str):
        if not isinstance(node, dict):
            return
        if isinstance(node.get(TERMS), dict):
            out[path] = node
            produced.add(root)
            return
        for k, v in node.items():
            if k == TERMS:
                continue
            walk(v, f"{path}.{k}" if path else str(k), root)

    for key, val in (doc or {}).items():
        walk(val, str(key), str(key).split(".")[0])
    for key, val in (doc or {}).items():
        if str(key).split(".")[0] not in produced:
            out.setdefault(str(key), val)
    return out


def load(framework=None) -> dict:
    """The vocabularies of `mac_vocabulary.yaml`, keyed by dotted name. Fold-agnostic."""
    try:
        import yaml
    except ImportError as exc:                                            # pragma: no cover
        raise RuntimeError(f"PyYAML is not importable: {exc}") from exc
    path = _framework_root(framework) / "mac_vocabulary.yaml"
    return flatten(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def notion(name: str, framework=None) -> dict | None:
    """One vocabulary by its dotted name, or None. `mac.` prefix tolerated."""
    v = load(framework)
    return v.get(name) or v.get(name[4:] if name.startswith("mac.") else f"mac.{name}")


def terms(name: str, framework=None) -> dict:
    """{term -> its body} for one vocabulary, or {} — never a KeyError at a call site."""
    return ((notion(name, framework) or {}).get(TERMS)) or {}


def self_test() -> int:
    """A FOLDED and a FLAT document must load identically. That is the whole contract."""
    flat = {
        "metadata": {"spec": "x"},
        "concept.column.role": {"closed": True, "terms": {"key": "a", "measure": "b"}},
        "concept.column.identity": {"terms": {"canonical": "c"}},
        "concept.identity": {"terms": {"code": "d"}},
        "relation.column.role": {"terms": {"value": "e"}},
        "canon": {"terms": {"densify": "f"}},
    }
    folded = {
        "metadata": {"spec": "x"},
        "concept": {"column": {"role": {"closed": True, "terms": {"key": "a", "measure": "b"}},
                               "identity": {"terms": {"canonical": "c"}}},
                    "identity": {"terms": {"code": "d"}}},
        "relation": {"column": {"role": {"terms": {"value": "e"}}}},
        "canon": {"terms": {"densify": "f"}},
    }
    cases = []
    a, b = flatten(flat), flatten(folded)
    cases.append(("a folded and a flat document load identically", a == b, {"flat": sorted(a), "folded": sorted(b)}))
    cases.append(("every vocabulary is keyed by its DOTTED name",
                  "concept.column.role" in a and "concept.identity" in a and "relation.column.role" in a,
                  sorted(a)))
    cases.append(("a non-vocabulary top-level key survives", a.get("metadata") == {"spec": "x"}, a.get("metadata")))
    cases.append(("a single-segment vocabulary is untouched", "canon" in a and "densify" in a["canon"]["terms"], None))
    #: THE TRAP: a TERM named like a path segment must not be walked into. `concept.identity` has a term
    #: `code`; if the walk did not stop at `terms`, it would also emit `concept.identity.code` as a
    #: vocabulary and the 7-wrong-definitions class would come back by another route.
    cases.append(("the walk STOPS at `terms` — a term is never a path segment",
                  "concept.identity.code" not in a and "concept.column.role.measure" not in a, sorted(a)))
    cases.append(("terms() never raises at a call site", terms_of_dict(a, "nope.missing") == {}, None))
    good = sum(1 for _l, c, _g in cases if c)
    for label, c, got in cases:
        print(f"  {'ok  ' if c else 'FAIL'}  {label}")
        if not c:
            print(f"          got: {got}")
    print(f"\n{'PASS' if good == len(cases) else 'FAIL'}: mac_vocab self-test — {good} of {len(cases)} case(s)")
    return 0 if good == len(cases) else 1


def terms_of_dict(flat_doc: dict, name: str) -> dict:
    """`terms()` against an already-flattened dict — used by the self-test without touching disk."""
    return ((flat_doc.get(name) or {}).get(TERMS)) or {}


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    v = load()
    print(f"{len(v)} top-level entr(y/ies); "
          f"{sum(1 for x in v.values() if isinstance(x, dict) and TERMS in x)} vocabular(y/ies), "
          f"{sum(len(x.get(TERMS) or {}) for x in v.values() if isinstance(x, dict))} term(s)")
    for k in sorted(v):
        n = len((v[k].get(TERMS) or {})) if isinstance(v[k], dict) else 0
        print(f"  {k:34} {n:3} term(s)" if n else f"  {k:34}   (not a vocabulary)")
