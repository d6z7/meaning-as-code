#!/usr/bin/env python3
"""
test_column_roundtrip.py — WHAT THE COMPOSER EMITS, THE READER LOADS.

Measured 2026-09-29: the composer's own exemplar was on a retired shape its prompt forbids; the
prompt hand-listed a vocabulary term retired the day before; the schema admitted `rulings:` and
composed measures that the platform's reader refused; and the first bundle written on the standard
could not load. Schema, composer and reader disagreed, and nothing had ever put them in one test.

ONE FIXTURE, HELD TO EVERY SIDE: sdk/authoring/exemplars/bundle/ (four concepts on the column
standard) must (1) validate under mac.schema.json, (2) pass the composer's own gates UNCHANGED —
`_errors`, `_autofix`, `check_instruction_compliance` — (3) be the exemplar the composer shows the
model, (4) carry only vocabulary tokens, (5) be described by a prompt whose vocabulary lists are
the vocabulary's, and (6) when the platform sits beside this repo, LOAD in its runtime parser with
the facts intact. The platform holds the hermetic half (packages/mac-runtime/tests/
test_column_roundtrip.py) against a byte-identical copy.

Usage:  python3 tests/test_column_roundtrip.py
Exit:   0 = the round trip holds · 1 = a side disagrees (named) · 2 = setup error
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

try:
    import yaml
    from sdk.authoring import authoring
    import validate_schema as VS
    import check_vocabulary_tokens as VT
except ImportError as e:  # pragma: no cover
    print(f"[setup] missing '{e.name}': pip install jsonschema pyyaml", file=sys.stderr)
    sys.exit(2)

BUNDLE = str(authoring.EXEMPLAR_BUNDLE)
CONCEPTS = sorted(
    os.path.join(BUNDLE, "ontology", "concepts", f)
    for f in os.listdir(os.path.join(BUNDLE, "ontology", "concepts")) if f.endswith(".yaml")
)
fails: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    if not cond:
        fails.append(f"{label}" + (f" — {detail}" if detail else ""))


# 1. the schema
enum = VS.enumerate_bundle(BUNDLE)
verdicts = VS.validate_files(enum)
bad = [v for v in verdicts if getattr(v, "findings", None)]
check("validate_schema: 0 findings", not bad, "; ".join(f"{v.path}: {v.findings[:1]}" for v in bad[:3]))
routed = len(enum.routed)
check("validate_schema routed every concept plus the project file", routed == len(CONCEPTS) + 1, f"routed {routed}")

# 2. the composer's own gates accept a standard-conformant file unchanged
for path in CONCEPTS:
    obj = yaml.safe_load(open(path, encoding="utf-8"))
    name = os.path.basename(path)
    errs = authoring._errors(obj)
    check(f"{name}: schema-valid for the composer", not errs, "; ".join(e.message[:80] for e in errs[:2]))
    fixes = authoring._autofix(obj)
    check(f"{name}: nothing for autofix to change", not fixes, "; ".join(fixes[:2]))
    corr, fail = authoring.check_instruction_compliance(obj)
    check(f"{name}: compliant as written", not corr and not fail, "; ".join((corr + fail)[:2]))

# 3. the exemplar IS the fixture, and is on the standard
ex = str(authoring.EXEMPLAR)
check("the exemplar lives in the fixture bundle", ex.startswith(BUNDLE) and os.path.isfile(ex), ex)
exo = yaml.safe_load(open(ex, encoding="utf-8"))
_grounding = exo.get("grounding") or {}
# `source` IS SINGULAR (2026-10-07). The list spelling is a load error, so the exemplar asserting
# the singular key is also the assertion that it is not on the retired one -- read through
# `.get("source")` and nothing else, because a reader that falls back to `sources` here would let
# the exemplar teach the shape the schema refuses.
check("exemplar: `source:` is singular and `sources:` is absent",
      isinstance(_grounding.get("source"), dict) and "sources" not in _grounding,
      f"grounding keys {sorted(_grounding)}")
src0 = _grounding.get("source") or {}
check("exemplar: columns in MAP form", isinstance(src0.get("columns"), dict))
check("exemplar: no field_roles block", "field_roles" not in _grounding)
# THE KEY IS ON THE SOURCE, in one ordered list (2026-10-07). Three things must hold together: the
# source states it, the columns do NOT repeat it, and the retired `concept.identity` block is absent.
_key = src0.get("key")
_key = [_key] if isinstance(_key, str) else list(_key or [])
# EVERY COLUMN DECLARES `offers:` AND NOTHING ELSE FROM THE RETIRED SET. `roles:` was the container
# until 2026-10-07 and `identity:` was a use inside it; both are `additionalProperties: false`
# violations now, and a column still carrying one is a column whose key the loader cannot see.
_retired_cols = [
    f"{c}.{k}" for c, b in (src0.get("columns") or {}).items() if isinstance(b, dict)
    for k in ("roles", "identity", "register", "counts") if k in b
]
_unclassified = [
    c for c, b in (src0.get("columns") or {}).items()
    if not isinstance(b, dict) or "offers" not in b
]
check("exemplar: the key is declared on the source", bool(_key), f"key={_key!r}")
check("exemplar: every key column is a column of the map",
      all(c in (src0.get("columns") or {}) for c in _key), f"key={_key!r}")
check("exemplar: no column carries a retired flag", not _retired_cols, f"{_retired_cols}")
check("exemplar: every column declares `offers:`", not _unclassified,
      f"a missing `offers` is a column nobody classified: {_unclassified}")
check("exemplar: no `concept.identity` block at all",
      "identity" not in (exo.get("concept") or {}), f"concept keys {sorted(exo.get('concept') or {})}")
check("exemplar: schema_version is the schema's generation",
      str(exo["metadata"]["schema_version"]) == authoring.schema_generation(),
      f"{exo['metadata']['schema_version']} vs {authoring.schema_generation()}")

# 4. only vocabulary tokens
check("check_vocabulary_tokens: clean", VT.main([BUNDLE]) == 0)

# 5. the prompt's lists are the vocabulary's, and carry no retired term
P = authoring.SYS_PROMPT
# AN EMPTY LIST PASSED THIS VACUOUSLY. `vocabulary_terms` answered `[]` for every nested namespace
# (mac_vocabulary.yaml folds its blocks; the lookup asked for the dotted name), so `sep.join([])`
# was `""` and `"" in P` is true of any prompt — four assertions that could not fail. The terms are
# asserted non-empty FIRST, which is what makes the membership check mean something.
# `concept.column.roles` BECAME `concept.column.offers` and `concept.column.identity` IS GONE
# ENTIRELY -- a foreign key's declaration is the CONCEPT IT POINTS AT, which is a name and not a
# term from a closed set, so there is no term list left to render. Asking for the retired namespace
# would resolve to `[]` and pass vacuously, which is the defect the non-empty check below exists
# for; it is asserted ABSENT instead.
check("the retired `concept.column.identity` vocabulary is gone",
      not authoring.vocabulary_terms("concept.column.identity"),
      "it still resolves to terms — the use set moved to `references:`, which takes a concept name")
for ns, sep in (("concept.rule", "|"), ("concept.column.offers", " | "),
                ("concept.axis", "|"), ("concept.column.measure_type", "|")):
    terms = authoring.vocabulary_terms(ns)
    check(f"{ns} resolves to terms at all", bool(terms))
    check(f"prompt lists every {ns} term", bool(terms) and sep.join(terms) in P, sep.join(terms))
for retired in ("resolved_axis", "role: attribute", "mac.MeasureType", "non-additive",
                "Only ONE column per concept", "identity: part", "{role: key", "{role: dimension",
                "mac.concept.column.role", "mac.concept.column.query_use",
                # RETIRED 2026-10-07, and every one of them is a key an author would otherwise
                # copy straight out of the prompt into a file the loader refuses. `roles:` is
                # checked separately, with a word boundary: `field_roles:` legitimately appears
                # inside a prohibition, and a plain substring would fire on the prohibition.
                "sources:", "identity: reference", "identity: canonical", "identity: composite",
                "never_axis", "mac.concept.column.roles", "mac.concept.column.identity"):
    check(f"prompt carries no retired token: {retired!r}", retired not in P)

# A PROHIBITION MUST NAME WHAT IT PROHIBITS, so these may appear — and ONLY inside one. A model
# that is told "do not write a `lifecycle:` block" needs to read the word; a blunt "the token is
# absent" check would force the instruction to be vague instead. Each occurrence must sit within
# 160 characters after a DO-NOT, which is where the prohibition's own sentence is.
#
# `roles:` BELONGS HERE, not in the blunt list above, and a word-boundary check alone was not
# enough: the prompt forbids the container by name ("DO NOT WRITE A SCALAR `role:` OR A `roles:`
# MAP"), so both of its occurrences are bare `roles:` inside a prohibition. Banning the substring
# outright would force the one instruction an author most needs to be vague.
_DONT = [i for i in range(len(P)) if P.startswith("DO NOT", i)]
for named in ("lifecycle:", "field_roles:", "`grain:`", "additivity:", "`identity:` BLOCK",
              "`roles:`", "roles:"):
    hits = [i for i in range(len(P)) if P.startswith(named, i)]
    loose = [i for i in hits if not any(0 <= i - d <= 160 for d in _DONT)]
    check(f"prompt names {named!r} only inside a prohibition",
          not loose, f"{len(loose)} of {len(hits)} occurrence(s) outside one")

# 6. the reader, when it is beside us
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location
if _neighbours.runtime_src() is not None:
    _neighbours.ensure_runtime_on_path()
    try:
        from mac_runtime.ontology import OntologyIndex  # type: ignore
        ix = OntologyIndex.from_directory(BUNDLE)
        cs = {c.name: c for c in ix.concepts.values()} if isinstance(ix.concepts, dict) else {c.name: c for c in ix.concepts}
        check("runtime loads all concepts", len(cs) == len(CONCEPTS), f"{len(cs)} of {len(CONCEPTS)}")
        p = cs["Product"]
        check("runtime: Product manufacturer label_of brand (legal)",
              p.grounding.spec("manufacturer").rulings.label_of == "brand"
              # `naming`, not `register`: ONE word named this closed five-term enum AND the file
              # whose rows are a column's values, one nesting level apart.
              and p.grounding.spec("manufacturer").rulings.naming == "legal")
        check("runtime: Product composed unit USD", p.semantics.unit == "USD")
        n = cs["NetRevenue"]
        check("runtime: NetRevenue composed unit and two measure carriers",
              n.semantics.unit == "USD" and n.grounding.field_roles["net_price"].endswith(".measure"))
        check("runtime: Sale order_date is period", cs["Sale"].grounding.field_roles["order_date"].endswith(".period"))
        d = cs["CalendarDay"]
        check("runtime: CalendarDay date_key is housekeeping; year_quarter finer_than year",
              d.grounding.field_roles["date_key"].endswith(".housekeeping")
              and d.grounding.spec("year_quarter").rulings.finer_than == "year")

        # THE ONE-LINE LAW, PINNED ACROSS THE TWO REPOS. `ColumnSpec.role` derives the five role
        # names from `roles` and is the authority; `mac_project.column_role` is this repo's reader
        # of the same law, because `mac_runtime` is not importable from the SDK and three modules
        # here need the answer. A second copy is only safe while something compares it, and nothing
        # did: the comparison is this check, over every column of every concept in the fixture.
        import glob as _g
        import mac_project as _MP
        import yaml as _y

        # OVER EVERY BUNDLE BESIDE US, because this fixture alone cannot exercise the law.
        # Measured: 0 of its 35 columns are `identity: canonical` AND an axis -- the branch whose
        # absence made the derivation reproduce 109 of 112 instead of 112 -- while contoso5 has 3.
        # A pin over a population that cannot contain the case is a pin that cannot go red, so the
        # denominator is asserted below rather than printed and trusted.
        _roots = [BUNDLE] + [
            r for r in (os.path.join(ROOT, "..", "cap-ontology-sources", "example", "contoso5"),)
            if os.path.isdir(os.path.join(r, "ontology", "concepts"))
        ]
        disagree, pinned, canonical_axes = [], 0, 0
        for _root in _roots:
            _ix = OntologyIndex.from_directory(_root)
            _cs = {c.name: c for c in (_ix.concepts.values() if isinstance(_ix.concepts, dict)
                                       else _ix.concepts)}
            for _f in sorted(_g.glob(os.path.join(_root, "ontology", "concepts", "**", "*.yaml"),
                                     recursive=True)):
                _doc = _y.safe_load(open(_f, encoding="utf-8")) or {}
                _c = _cs.get((_doc.get("concept") or {}).get("name"))
                if _c is None or _c.grounding is None:
                    continue
                _cols = ((_doc.get("grounding") or {}).get("source") or {}).get("columns") or {}
                for _spec in _c.grounding.columns:
                    _authored = _cols.get(_spec.name) or {}
                    # THE BRANCH WHOSE ABSENCE COST 3 OF 112: a one-column key whose column is
                    # ALSO an axis derives `dimension`, not `key` (brand.brand, color.color,
                    # category_name). The shape is now "the source's key holds one name and that
                    # column declares an axis" — the per-column `canonical` it used to be read from
                    # retired with the key's move.
                    _sk = ((_doc.get("grounding") or {}).get("source") or {}).get("key")
                    _sk = [_sk] if isinstance(_sk, str) else list(_sk or [])
                    if len(_sk) == 1 and _spec.name in _sk and (_authored.get("offers") or {}).get("axis"):
                        canonical_axes += 1
                    pinned += 1
                    # BOTH SIDES SEE THE KEY, or the comparison is vacuous: `_spec.role` calls
                    # `role_within(())` with an EMPTY key, so the platform half never consulted it
                    # and the two agreed trivially — measured by mutation, which passed.
                    _mine = _MP.column_role({**_authored, "name": _spec.name}, _sk)
                    _theirs = _spec.role_within(tuple(_sk))
                    if _mine != _theirs:
                        disagree.append(
                            f"{_c.name}.{_spec.name}: mac {_mine!r} vs runtime {_theirs!r}")
        check("mac_project.column_role agrees with the runtime's ColumnSpec.role on every column",
              not disagree, "; ".join(disagree[:3]))
        check("and the population is big enough to disagree",
              pinned > 100 and canonical_axes > 0,
              f"{pinned} column(s) pinned, {canonical_axes} of them canonical-and-an-axis")
    except ImportError as e:  # the platform's deps are not this repo's
        print(f"  runtime half skipped: {e}")
    except Exception as e:  # noqa: BLE001
        # A REFUSAL IS A DISAGREEMENT, NOT A CRASH. The reader raising on the exemplar is exactly
        # what this file exists to catch -- "the first bundle written on the standard could not
        # load" is its opening measurement -- and it must arrive as a NAMED check among the others,
        # not as a traceback that hides the five sides already checked above it.
        check("the runtime reader loads the exemplar at all", False, f"{type(e).__name__}: {e}")
else:
    print("  runtime half skipped: mac-platform is not beside this repo")

digest = hashlib.sha256(b"".join(open(p, "rb").read() for p in CONCEPTS)).hexdigest()[:16]
if fails:
    print("FAIL: test_column_roundtrip — " + f"{len(fails)} disagreement(s) over {len(CONCEPTS)} concept(s) (fixture {digest}):")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print(f"PASS: test_column_roundtrip — schema, composer gates, exemplar, tokens, prompt and reader agree "
      f"over {len(CONCEPTS)} concept(s), {routed} routed file(s) (fixture {digest})")
