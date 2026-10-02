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
src0 = (exo.get("grounding") or {}).get("sources", [{}])[0]
check("exemplar: columns in MAP form", isinstance(src0.get("columns"), dict))
check("exemplar: no field_roles block", "field_roles" not in (exo.get("grounding") or {}))
canon_cols = [c for c, b in (src0.get("columns") or {}).items() if isinstance(b, dict) and b.get("identity") == "canonical"]
check("exemplar: canonical key on the column, not also on the concept",
      bool(canon_cols) and "canonical_key" not in ((exo.get("concept") or {}).get("identity") or {}))
check("exemplar: schema_version is the schema's generation",
      str(exo["metadata"]["schema_version"]) == authoring.schema_generation(),
      f"{exo['metadata']['schema_version']} vs {authoring.schema_generation()}")

# 4. only vocabulary tokens
check("check_vocabulary_tokens: clean", VT.main([BUNDLE]) == 0)

# 5. the prompt's lists are the vocabulary's, and carry no retired term
P = authoring.SYS_PROMPT
for ns, sep in (("concept.identity", "|"), ("concept.rule", "|"), ("concept.column.role", " | "),
                ("concept.column.measure_type", "|")):
    terms = authoring.vocabulary_terms(ns)
    check(f"prompt lists every {ns} term", sep.join(terms) in P, sep.join(terms))
for retired in ("resolved_axis", "role: attribute", "mac.MeasureType", "non-additive", "Only ONE column per concept"):
    check(f"prompt carries no retired token: {retired!r}", retired not in P)

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
              and p.grounding.spec("manufacturer").rulings.naming_register == "legal")
        check("runtime: Product composed unit USD", p.semantics.unit == "USD")
        n = cs["NetRevenue"]
        check("runtime: NetRevenue composed unit and two measure carriers",
              n.semantics.unit == "USD" and n.grounding.field_roles["net_price"].endswith(".measure"))
        check("runtime: Sale order_date is period", cs["Sale"].grounding.field_roles["order_date"].endswith(".period"))
        d = cs["CalendarDay"]
        check("runtime: CalendarDay date_key is housekeeping; year_quarter finer_than year",
              d.grounding.field_roles["date_key"].endswith(".housekeeping")
              and d.grounding.spec("year_quarter").rulings.finer_than == "year")
    except ImportError as e:  # the platform's deps are not this repo's
        print(f"  runtime half skipped: {e}")
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
