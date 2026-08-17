#!/usr/bin/env python3
"""
test_mac_model.py — the shared bundle model (tools/mac_model.py).

Proves the four properties the model is judged on:

  1. LAYOUT TOLERANCE — flat and foldered concept trees, the flat default (no manifest) and a
     two-plane manifest, and planes that are NOT named data/ontology, all load through one resolver.
  2. NEVER RAISES ON CONTENT — a malformed file lands as Doc.parse_error and the load continues; a
     dangling reference lands as a falsy Unresolved AT the referring field. Only programmer error
     (an unknown scope, an unknown fact family) raises.
  3. PROVENANCE ON EVERY FACT — a Site on every interpreted value, exact line numbers on demand, and
     ONE provenance reader.
  4. THE FACT FAMILY — measure.additivity finds the concept↔law contradiction, and does NOT fire on
     a measure-selector axis (without that derivation the family over-fires 7x on the live corpus)
     nor on two legitimate different statements the coarser fact key would collapse.

Self-contained: the repo's own fixtures plus synthetic bundles built in a temp dir. No private
bundle, no network, no AWS.

Usage:  python3 tests/test_mac_model.py     ·     Exit: 0 = ok · 1 = an assertion failed
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import mac_model as M                                            # noqa: E402

REPO = Path(HERE).resolve().parent
fails = 0


def check(cond, msg):
    global fails
    print(("✓ " if cond else "✗ ") + msg)
    fails += 0 if cond else 1


def eq(got, want, msg):
    check(got == want, f"{msg}  (got {got!r}, want {want!r})")


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ===================================================================================================
# synthetic bundles — a domain-neutral widget/gadget vocabulary supplied entirely by the bundle
# ===================================================================================================

MANIFEST = """\
planes:
  data: {data}
  ontology: {ontology}
descriptors: {data}/datasets
transforms: {data}/transforms
sources: {data}/sources
"""

DATASET = """\
metadata:
  provenance: harvested
table:
  name: {physical}
  schema: mart
columns:
- name: widget_code
  type: string
  role: key
  description: the widget's code
- name: amount
  type: double
  role: measure
foreign_keys:
- name: fk_widget
  from_column: widget_code
  to_table: dim_widget
  to_column: widget_code
"""

MEASURE_CONCEPT = """\
metadata:
  provenance: {provenance}
concept:
  name: {name}
  class: measure
  semantics:
    additivity:
{additivity}
    axis_kinds:
{axis_kinds}
{measure_type}
    unit: widgets
grounding:
  sources:
    - relation: {relation}
      key: [widget_code]
      columns: [widget_code, amount]
"""

ENUM_CONCEPT = """\
metadata:
  provenance: authored
concept:
  name: WidgetKind
  class: enumeration
values:
  closure: closed
  realized_by:
    udf: mac.canon.enum_from_register
    params:
      register: {register}
  items:
    - code: alpha
      label: Alpha
      confidence: C
"""

EDGES = """\
metadata:
  scope: intra_source
edges:
  - edge_id: fact__of_widget
    level: physical
    endpoints:
      from: {{ concept: {left}, ref: "x" }}
      to:   {{ concept: {right}, ref: "y" }}
    join_rule: "fact_widget.widget_code = dim_widget.widget_code"
"""

# A measure register: the three law columns, plus columns that say WHICH measure a row is. `unit` is
# constant down the file, so it distinguishes nothing and is NOT a discriminator.
MEASURE_REGISTER = """\
metric_code,family,flavour,unit,measure_type,additivity_time,additivity_categorical
count_actual,count,actual,widgets,mac.MeasureType.Flow,mac.aggregation_effect.additive,mac.aggregation_effect.additive
count_plan,count,plan,widgets,mac.MeasureType.Flow,mac.aggregation_effect.additive,mac.aggregation_effect.additive
level_actual,level,actual,widgets,mac.MeasureType.Stock,mac.aggregation_effect.point_in_time,mac.aggregation_effect.additive
level_plan,level,plan,widgets,mac.MeasureType.Stock,mac.aggregation_effect.point_in_time,mac.aggregation_effect.additive
"""


def block(mapping, indent="      "):
    return "\n".join(f"{indent}{k}: {v}" for k, v in mapping.items())


def build_bundle(root: Path, *, foldered: bool, data="data", ontology="ontology",
                 with_register=True, extras=True) -> Path:
    """A complete two-plane bundle. `foldered` nests concepts one level, mirroring the two concept
    layouts the live corpus uses (both must load through one expression)."""
    write(root / "mac.project.yaml", MANIFEST.format(data=data, ontology=ontology))
    write(root / data / "datasets" / "fact_widget.yaml",
          DATASET.format(physical="fact_widget_v2"))
    write(root / data / "datasets" / "dim_widget.yaml", DATASET.format(physical="dim_widget"))
    write(root / data / "sources" / "raw_widget.yaml", DATASET.format(physical="raw_widget"))
    write(root / data / "transforms" / "fact_widget.yaml",
          "metadata:\n  provenance: tuned\nproduces: fact_widget\n")

    cdir = root / ontology / "concepts"
    sub = (lambda n: cdir / n.lower() / f"{n.lower()}.yaml") if foldered else (
        lambda n: cdir / f"{n.lower()}.yaml")

    # a Flow measure whose `flavour` axis is a MEASURE SELECTOR (it is a register discriminator)
    write(sub("WidgetCount"), MEASURE_CONCEPT.format(
        name="WidgetCount", provenance="Harvested", relation="mart.fact_widget",
        additivity=block({"period": "additive", "place": "additive", "flavour": "non-additive"}),
        axis_kinds=block({"period": "mac.axis_kind.time", "place": "mac.axis_kind.categorical",
                          "flavour": "mac.axis_kind.categorical"}),
        measure_type="    measure_type: mac.MeasureType.Flow"))

    # a Target measure claiming a categorical axis is additive — the law says a Target is not
    write(sub("WidgetTarget"), MEASURE_CONCEPT.format(
        name="WidgetTarget", provenance="tuned", relation="fact_widget",
        additivity=block({"place": "additive"}),
        axis_kinds=block({"place": "mac.axis_kind.categorical"}),
        measure_type="    measure_type: mac.MeasureType.Target"))

    if extras:
        # NO measure_type: two categorical axes stating DIFFERENT, both legitimate, values. A fact
        # key of (measure, axis_KIND) would collapse them and fire a false positive.
        write(sub("WidgetSpread"), MEASURE_CONCEPT.format(
            name="WidgetSpread", provenance="authored", relation="fact_widget",
            additivity=block({"place": "additive", "shape": "non-additive"}),
            axis_kinds=block({"place": "mac.axis_kind.categorical",
                              "shape": "mac.axis_kind.categorical"}),
            measure_type=""))
        # a value outside the closed comparison domain: the statement must be DROPPED, not compared
        write(sub("WidgetRate"), MEASURE_CONCEPT.format(
            name="WidgetRate", provenance="authored", relation="fact_widget",
            additivity=block({"place": "averageable"}),
            axis_kinds=block({"place": "mac.axis_kind.categorical"}),
            measure_type="    measure_type: mac.MeasureType.Flow"))
        write(sub("WidgetKind"), ENUM_CONCEPT.format(register="widget_kind.lookup"))
        write(cdir / "unnamed.yaml", "metadata:\n  provenance: authored\nnote: no concept block\n")
        write(root / ontology / "edges.yaml", EDGES.format(left="WidgetCount", right="NoSuchConcept"))
        write(root / data / "lookups" / "widget_kind.lookup.csv", "code,label\nalpha,Alpha\n")

    if with_register:
        write(root / data / "lookups" / "metric.lookup.csv", MEASURE_REGISTER)
    return root


TMP = Path(tempfile.mkdtemp(prefix="mac_model_test_"))
try:
    # ===============================================================================================
    # 1. layout tolerance
    # ===============================================================================================
    print("\n-- layout tolerance ------------------------------------------------------------------")

    flat_repo = REPO / "tests" / "fixtures" / "flat_project"
    B = M.load(flat_repo)
    check(not B.layout.two_plane, "flat project (no manifest) loads")
    eq(len(B.concepts()), 1, "flat project: one concept file (nested one level under concepts/)")
    eq(B.concepts()[0].name, "Widget", "flat project: concept name read")
    eq(B.relation("widgets").name, "widgets", "flat project: descriptors resolve under tables/")

    shop = REPO / "example_shop_ontology"
    S = M.load(shop)
    check(S.layout.two_plane, "two-plane example loads")
    eq(len(S.concepts()), 8, "shop: 8 concept files, foldered by domain")
    eq(len(S.docs("dataset")), 7, "shop: 7 dataset descriptors")
    eq(len(S.docs("source")), 1, "shop: 1 raw-source descriptor")
    eq(len(S.docs("transform")), 1, "shop: 1 transform descriptor")
    check(len(S.edges()) > 0, f"shop: edges loaded ({len(S.edges())})")
    check(all(not d.relpath.startswith("projections/") for d in S.docs()),
          "planes scope excludes projections/ (generated exports are not model source)")

    foldered = build_bundle(TMP / "foldered", foldered=True)
    flat = build_bundle(TMP / "flat", foldered=False)
    Bf, Bl = M.load(foldered), M.load(flat)
    eq([c.name for c in Bf.concepts()], [c.name for c in Bl.concepts()],
       "foldered and flat concept trees yield the same concepts, in the same order")
    eq(len(Bf.concepts()), 6, "synthetic bundle: 6 concept FILES (one declares no concept.name)")
    eq(sum(1 for c in Bf.concepts() if c.name), 5, "synthetic bundle: 5 of them are named")

    named_planes = build_bundle(TMP / "named", foldered=True, data="warehouse", ontology="model")
    N = M.load(named_planes)
    eq(len(N.concepts()), 6, "planes named model/warehouse: concepts still found via the resolver")
    eq(len(N.docs("dataset")), 2, "planes named model/warehouse: descriptors still found")
    eq(len(N.registers()), 0,
       "planes named model/warehouse: registers NOT found — data/lookups is conventional, not a "
       "manifest key (a reported limitation, not a silent one)")

    # ===============================================================================================
    # 2. never raises on content
    # ===============================================================================================
    print("\n-- never raises on content -----------------------------------------------------------")

    broken = build_bundle(TMP / "broken", foldered=False)
    write(broken / "ontology" / "concepts" / "malformed.yaml", "concept:\n  name: [unclosed\n")
    write(broken / "data" / "datasets" / "not_a_mapping.yaml", "- just\n- a list\n")
    M.clear_cache()
    Bb = M.load(broken)
    bad = [d for d in Bb.docs() if d.parse_error]
    eq(len(bad), 1, "a malformed YAML file is recorded, not raised")
    check(bad[0].relpath.endswith("malformed.yaml"), f"the recorded file is the malformed one ({bad[0].relpath})")
    check("unclosed" in bad[0].parse_error or "expected" in bad[0].parse_error.lower(),
          "the parse error text is kept VERBATIM for the gate to print")
    eq(bad[0].data, {}, "a malformed document's data is an empty mapping")
    eq(len(Bb.concepts()), 7, "the rest of the bundle still loads (6 + the malformed file)")
    eq(Bb.doc("data/datasets/not_a_mapping.yaml").data, {},
       "a non-mapping document is {} with NO parse error")
    eq(Bb.doc("data/datasets/not_a_mapping.yaml").parse_error, None,
       "a non-mapping document is not an error")

    dangling = build_bundle(TMP / "dangling", foldered=False)
    write(dangling / "ontology" / "concepts" / "orphan.yaml", MEASURE_CONCEPT.format(
        name="Orphan", provenance="authored", relation="mart.no_such_relation",
        additivity=block({"place": "additive"}),
        axis_kinds=block({"place": "mac.axis_kind.categorical"}), measure_type=""))
    write(dangling / "ontology" / "concepts" / "badenum.yaml",
          ENUM_CONCEPT.format(register="no_such_register"))
    M.clear_cache()
    Bd = M.load(dangling)
    orphan = Bd.concept("Orphan")
    u = orphan.groundings[0].relation
    check(isinstance(u, M.Unresolved), "a grounding to a missing relation is an Unresolved value")
    check(not u, "Unresolved is FALSY, so `if not rel:` is the idiom")
    eq(u.kind, "relation", "Unresolved carries what was expected")
    eq(u.ref, "mart.no_such_relation", "Unresolved carries the reference AS WRITTEN")
    check("datasets" in " ".join(u.searched),
          f"Unresolved carries the dirs actually searched {u.searched} — that is how a gate "
          f"reproduces its own wording")
    eq(u.site.path, "grounding.sources[0].relation", "Unresolved carries the referring SITE")

    ve = [c for c in Bd.concepts() if c.stem == "badenum"][0]
    check(isinstance(ve.values.register, M.Unresolved), "a missing register resolves to Unresolved")
    eq(ve.values.register.kind, "register", "the missing register's expected kind")
    check(isinstance(Bd.edges()[0].concepts[1], M.Unresolved),
          "an edge endpoint naming no concept resolves to Unresolved")
    check(bool(Bd.edges()[0].concepts[0]), "the resolvable endpoint of the same edge resolves")
    check(isinstance(Bd.object("dataset:nope"), M.Unresolved), "an unknown object ref is Unresolved")
    check(isinstance(Bd.object("nonsense"), M.Unresolved), "a malformed object ref is Unresolved")
    check(isinstance(Bd.object("wrongkind:x"), M.Unresolved), "an unknown object KIND is Unresolved")
    check(isinstance(Bd.doc("nope.yaml"), M.Unresolved), "an unknown document is Unresolved")

    raised = None
    try:
        M.load(dangling, scope="whatever")
    except ValueError as e:
        raised = str(e)
    check(raised is not None and "scope" in raised, "an unknown SCOPE raises (programmer error)")
    raised = None
    try:
        Bd.facts("no.such.family")
    except ValueError as e:
        raised = str(e)
    check(raised is not None and "family" in raised, "an unknown FACT FAMILY raises (programmer error)")

    # ===============================================================================================
    # 3. provenance on every fact
    # ===============================================================================================
    print("\n-- provenance on every fact ----------------------------------------------------------")

    M.clear_cache()
    Bf = M.load(foldered)
    target = Bf.concept("WidgetTarget")
    st = target.measure.axes["place"].additivity
    eq(st.value, "additive", "an interpreted value is a Stated carrying the value AS WRITTEN")
    eq(st.site.path, "concept.semantics.additivity.place", "the Stated carries its YAML path")
    eq(st.kind, "authored", "an ontology-plane statement is `authored`")
    doc = Bf.doc(st.site.file)
    src_line = doc.abspath.read_text().splitlines().index("      place: additive") + 1
    eq(doc.line_of(st.site.path), src_line, "line_of() is EXACT (checked against the file's own text)")
    eq(doc.line_of("concept.name"), 4, "line_of() resolves a nested path to its KEY line")
    eq(doc.line_of("no.such.path"), None, "line_of() of an unknown path is None, not an error")

    dcol = Bf.relation("fact_widget").columns["amount"]
    eq(dcol.site.path, "columns[1]", "a descriptor column carries its own Site")
    eq(Bf.relation("fact_widget").doc.kind, "dataset", "a descriptor's doc kind comes from LOCATION")

    law_stated = Bf.law.additivity("mac.MeasureType.Target", "mac.axis_kind.categorical")
    eq(law_stated.value, "mac.aggregation_effect.non_aggregable", "the law is read as a Stated")
    check(law_stated.site.file.startswith(M.FRAMEWORK),
          f"the law's Site names the framework, not a bundle ({law_stated.site.file})")
    check(law_stated.site.line is not None, "the law's Site carries a real line number")

    o = Bf.objects()["concept:widgetcount"]
    eq(o.provenance.value, "Harvested", "Object.provenance holds the RAW value, unnormalized")
    eq(M.provenance_of(o), "harvested", "provenance_of() case-folds — ONE reader, no second one")
    eq(M.provenance_of(Bf.objects()["lookup:metric"]), None, "a register carries no provenance stamp")
    eq(M.provenance_of(None), None, "provenance_of(None) is None, never an error")
    eq(M.provenance_of(Bf.doc("ontology/concepts/widgetkind.yaml")
                       if not isinstance(Bf.doc("ontology/concepts/widgetkind.yaml"), M.Unresolved)
                       else Bf.objects()["concept:widgetkind"]), "authored",
       "provenance_of() reads a Doc as well as an Object")

    # ===============================================================================================
    # 4. objects, registers, relations
    # ===============================================================================================
    print("\n-- objects · registers · relations ---------------------------------------------------")

    all_objs = Bf.objects()
    eq(len(all_objs), 12, "12 objects: 6 concepts + 2 datasets + 1 source + 1 transform + 2 lookups")
    eq(len(Bf.objects(kinds=("source", "transform", "dataset", "concept"))), 10,
       "the caller's kinds decide the scope — the two change-protocol gates print DIFFERENT counts "
       "and the difference is exactly the registers")
    eq(Bf.object("concept:widgettarget").kind, "concept", "an object ref resolves")
    eq(Bf.object("lookup:metric").stem, "metric", "a register object's stem strips the .lookup suffix")
    eq(Bf.object("lookup:metric").raw_stem, "metric.lookup", "…and keeps the on-disk stem too")

    reg = Bf._registers["metric"]
    eq(reg.stem, "metric", "Register.stem is the stripped identity — ONE identity, everywhere")
    eq(reg.rows[0].lineno, 2, "the first register row is line 2 (the header is line 1)")
    eq(reg.rows[0].site("measure_type").line, 2, "a register cell's Site carries its file line")
    eq(reg.columns[0], "metric_code", "the register header is kept in order")
    check(reg.is_measure_register, "a lookup carrying the law's three columns IS a measure register")
    eq(sorted(reg.discriminators), ["family", "flavour", "metric_code"],
       "discriminators = the header columns that are not the law's three and that VARY down the file")
    check("unit" not in reg.discriminators,
          "a column that is CONSTANT down the register distinguishes no measure, so it is not one")
    check(not Bf._registers["widget_kind"].is_measure_register,
          "a plain lookup is not a measure register")
    eq(Bf.register("metric.lookup").stem, "metric", "a register pointer resolves by on-disk stem")
    eq(Bf.register("metric").stem, "metric", "…and by stripped stem")
    eq(Bf.register("metric.lookup.csv").stem, "metric", "…and with a .csv suffix")

    r = Bf.relation("mart.fact_widget")
    eq(r.name, "fact_widget", "a schema-qualified reference resolves by BARE name")
    eq(r.physical, "fact_widget_v2", "table.name is kept when it differs from the descriptor stem")
    eq(Bf.relation("fact_widget_v2").name, "fact_widget",
       "the physical name is a secondary key onto the same relation")
    eq(len(r.foreign_keys), 1, "foreign keys are read")
    eq(r.foreign_keys[0].to_table, "dim_widget", "…with their target")
    eq(Bf.relation("raw_widget").role, "raw_source", "a raw-source descriptor is role=raw_source")
    eq(list(r.columns), ["widget_code", "amount"], "columns keep declaration order")

    grounding = Bf.concept("WidgetCount").groundings[0]
    check(bool(grounding.relation), "a grounding resolves to its Relation")
    eq(grounding.columns, ("widget_code", "amount"),
       "grounding.sources[].columns is carried as a SELECTION, not folded into the descriptor")

    # ===============================================================================================
    # 5. scopes + caching
    # ===============================================================================================
    print("\n-- scopes · caching ------------------------------------------------------------------")

    scoped = build_bundle(TMP / "scoped", foldered=False)
    write(scoped / "acceptance" / "questions.yaml", "questions: []\n")
    write(scoped / "ontology" / "deployment.local.yaml", "secret: no\n")
    write(scoped / "ontology" / "projections" / "export.yaml", "generated: yes\n")
    M.clear_cache()
    P = M.load(scoped, "planes")
    T = M.load(scoped, "tree")
    names = {d.relpath for d in P.docs()}
    check("acceptance/questions.yaml" not in names, "planes scope stops at the declared planes")
    check("ontology/deployment.local.yaml" not in names, "planes scope drops *.local.* manifests")
    check("ontology/projections/export.yaml" not in names, "planes scope drops projections/")
    tnames = {d.relpath for d in T.docs()}
    check("acceptance/questions.yaml" in tnames, "tree scope is WIDER — it reaches outside the planes")
    check("mac.project.yaml" in tnames, "tree scope reaches the root manifest")
    check(len(T.docs()) > len(P.docs()), f"tree {len(T.docs())} > planes {len(P.docs())} documents")

    check(M.load(scoped, "planes") is P, "load() is memoized per (root, scope) — 8 gates, 1 parse")
    check(M.load(scoped, "tree") is not P, "…and the two scopes are separate populations")

    # ===============================================================================================
    # 6. the fact family
    # ===============================================================================================
    print("\n-- fact family: measure.additivity ---------------------------------------------------")

    eq(M.families(), ("measure.additivity",), "one family ships; adding one is a function + a dict line")
    facts = Bf.facts("measure.additivity")
    by_key = {f.key: f for f in facts}
    eq(len(facts), 7, "7 axis-facts: 3 (WidgetCount) + 1 (WidgetTarget) + 2 (WidgetSpread) + 1 (WidgetRate)")

    bad = [f for f in facts if not f.agrees()]
    eq([f.key for f in bad], [("WidgetTarget", "place")],
       "exactly ONE contradiction — the Target measure claiming a categorical axis is additive")
    contradiction = bad[0]
    eq(len(contradiction.statements), 2, "the contradiction holds BOTH statements")
    eq(set(contradiction.normalized), {"additive", "non-additive"}, "…folded into one closed domain")
    check(contradiction.home().site.file.startswith(M.FRAMEWORK),
          "home() names the LAW — the site that should hold the fact once")
    check(any(s.site.path == "concept.semantics.additivity.place" for s in contradiction.statements),
          "…and the other statement points at the exact authored line")

    sel = by_key[("WidgetCount", "flavour")]
    eq(Bf.concept("WidgetCount").measure.axes["flavour"].role, "measure_selector",
       "an axis whose name is a register discriminator is a MEASURE SELECTOR, not a data axis")
    eq(len(sel.statements), 1,
       "a measure-selector axis gets NO law statement: changing it selects a DIFFERENT measure, so "
       "the law has nothing to say about it (without this, the family over-fires 7x on the corpus)")
    eq(Bf.concept("WidgetCount").measure.axes["place"].role, "aggregation_axis",
       "every other axis is an aggregation axis")
    eq(len(by_key[("WidgetCount", "place")].statements), 2,
       "…and an aggregation axis DOES get the law's statement")

    noreg = build_bundle(TMP / "noreg", foldered=False, with_register=False)
    M.clear_cache()
    Bn = M.load(noreg)
    over = [f.key for f in Bn.facts("measure.additivity") if not f.agrees()]
    eq(sorted(over), [("WidgetCount", "flavour"), ("WidgetTarget", "place")],
       "PROOF the derivation is load-bearing: with no measure register there are no discriminators, "
       "so the same bundle reports the selector axis as a contradiction too")

    eq(len(by_key[("WidgetSpread", "place")].statements), 1,
       "a measure declaring no measure_type produces no law statement…")
    check(by_key[("WidgetSpread", "place")].agrees() and by_key[("WidgetSpread", "shape")].agrees(),
          "…so its two categorical axes stating DIFFERENT values are two facts of one statement "
          "each — the false positive a (measure, axis_KIND) key would produce")

    rate = by_key[("WidgetRate", "place")]
    eq(len(rate.statements), 1,
       "a declared value outside the closed comparison domain is DROPPED, not compared "
       "(a statement the model cannot fold is not evidence of anything)")
    eq(rate.statements[0].site.file, f"{M.FRAMEWORK}/{M.VOCABULARY}",
       "…leaving only the law's statement standing")

    # ===============================================================================================
    # 7. house numbers
    # ===============================================================================================
    print("\n-- number formatting -----------------------------------------------------------------")
    eq(M.de(1234567), "1.234.567", "numbers for humans are de-DE")
    eq(M.de(33.08, 2), "33,08", "…decimals too")
    eq(M.de(0), "0", "…and small ones")
    eq(M.de("n/a"), "n/a", "a non-number passes through unchanged")

finally:
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n{'all mac_model assertions passed' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
