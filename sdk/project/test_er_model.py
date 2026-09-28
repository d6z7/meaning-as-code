"""Unit tests for the PHYSICAL ER projector — connected components, the crow's-foot mapping, and
the refusal to fall back to the ontology. No warehouse; the bundle fixtures are written to tmp_path.

Every rule gets a mutant per way it can be wrong AND a negative control per correctly-modelled shape
that must NOT trip it — the discipline the framework's gates use, because a rule that only ever sees
the happy case cannot be shown to work.
"""

from sdk.project import er_model as E


# --- connected components ----------------------------------------------------------------------
# THE DEFECT. `isolated_entities` counts entities of degree ZERO. It read 0 — truthfully — while an
# operator was looking at three disconnected groups, because an island of six has no degree-zero
# member. The metric could not see the thing being reported.


def _ents(*ids):
    return [{"id": i} for i in ids]


def _rel(a, b):
    return {"from": {"entity": a}, "to": {"entity": b}}


def test_three_islands_are_reported_as_three():
    comps = E._components(
        _ents("f1", "f2", "d1", "m", "a1", "a2", "c1", "c2"),
        [_rel("f1", "d1"), _rel("f2", "d1"), _rel("m", "a1"), _rel("m", "a2"), _rel("c1", "c2")],
    )
    assert len(comps) == 3
    assert [len(c) for c in comps] == [3, 3, 2]  # largest first, so the main body reads first


def test_a_fully_connected_graph_is_one_component():
    # NEGATIVE CONTROL — the metric must not manufacture islands out of a connected graph.
    comps = E._components(_ents("a", "b", "c"), [_rel("a", "b"), _rel("b", "c")])
    assert len(comps) == 1 and comps[0] == ["a", "b", "c"]


def test_every_entity_lands_in_exactly_one_component():
    ents = _ents("a", "b", "c", "d")
    comps = E._components(ents, [_rel("a", "b")])
    flat = [i for c in comps for i in c]
    assert sorted(flat) == ["a", "b", "c", "d"] and len(flat) == len(set(flat))


def test_a_dangling_endpoint_cannot_invent_an_entity():
    # A relationship may name a table that is not a projected entity (`dangling` on the
    # relationship). Union-find over it used to KeyError; it must be skipped, not crash the model.
    comps = E._components(_ents("a", "b"), [_rel("a", "not_projected")])
    assert len(comps) == 2 and sorted(i for c in comps for i in c) == ["a", "b"]


# --- the fixture bundle -------------------------------------------------------------------------
# Synthetic relations only (alpha/beta/gamma/delta). The whole physical builder is a pure function of
# three local file families, so a bundle on tmp_path is a complete input — no engine, no warehouse.

import yaml


def _ref(child, ccol, parent, pcol, *, card=("many", "one"),
         part=("mandatory", "optional"), unreferenced=3, **extra):
    return {
        "id": f"{child}.{ccol}__{parent}.{pcol}",
        "from": {"relation": child, "column": ccol},
        "to": {"relation": parent, "column": pcol},
        "parent_key_role": "identity", "verdict": "real", "drawn": True,
        "cardinality": {"child": card[0], "parent": card[1]},
        "participation": {"child": part[0], "parent": part[1],
                          "parent_unreferenced": unreferenced},
        "evidence": {"child_rows": 100, "child_nonnull": 100, "orphan_rows": 0,
                     "orphan_distinct": 0, "parent_rows": 10, "parent_distinct": 10,
                     "parent_used": 7, "inclusion": 1.0},
        "name_match": ccol == pcol,
        **extra,
    }


def _bundle(root, *, references=None, dangling=None, sources=None, keys=None, edges_yaml=False):
    (root / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (root / "data" / "profiles").mkdir(parents=True, exist_ok=True)
    srcs = sources if sources is not None else {
        "alpha": ["AlphaRef", "GammaRef", "DeltaRef"], "gamma": ["GammaRef", "Label"]}
    ks = keys if keys is not None else {"alpha": ["AlphaRef"], "gamma": ["GammaRef"]}
    # THE REFERENCES GO ON THE DESCRIPTOR, because that is where the model reads them now. They used
    # to be seeded only into data/references/, which is the artifact the ER no longer reads: the page
    # and the diagram must be built from ONE source or they can disagree, and they did — 17 drawn
    # against 6 listed on a live bundle. The `references=` fixture API is unchanged; only where it
    # lands has moved.
    _decl = {}
    for r in references or []:
        _decl.setdefault(r["from"]["relation"], {})[r["from"]["column"]] = {
            "to": f"{r['to']['relation']}.{r['to']['column']}",
            **({"cardinality": r["cardinality"]} if r.get("cardinality") else {}),
            **({"participation": {k: v for k, v in (r.get("participation") or {}).items()
                                  if k in ("child", "parent")}} if r.get("participation") else {}),
        }
    for stem, cols in srcs.items():
        _d = _decl.get(stem, {})
        (root / "data" / "sources" / f"{stem}.yaml").write_text(yaml.safe_dump(
            {"of": stem, "table": {"name": stem, "schema": "alpha_schema"},
             "columns": [{"name": c, "type": "bigint", "role": "value",
                          **({"references": _d[c]} if c in _d else {})} for c in cols]}))
        (root / "data" / "profiles" / f"{stem}.yaml").write_text(yaml.safe_dump(
            {"of": stem, "profile": {"rows": 10},
             "identity_evidence": {"key": ks.get(stem, [])}}))
    if references is not None or dangling is not None:
        (root / "data" / "references").mkdir(parents=True, exist_ok=True)
        by_child = {stem: {"of": stem, "relation": f"alpha_schema.{stem}",
                           "admission": {"inclusion_required": 1.0},
                           "references": [], "references_dangling": [],
                           "candidates_rejected": []}
                    for stem in srcs}
        for r in references or []:
            by_child.setdefault(r["from"]["relation"], {"of": r["from"]["relation"],
                                                        "references": [],
                                                        "references_dangling": []})
            by_child[r["from"]["relation"]]["references"].append(r)
        for d in dangling or []:
            by_child[d["from"]["relation"]]["references_dangling"].append(d)
        for stem, doc in by_child.items():
            (root / "data" / "references" / f"{stem}.yaml").write_text(
                yaml.safe_dump(doc, sort_keys=False))
    if edges_yaml:
        (root / "ontology").mkdir(parents=True, exist_ok=True)
        (root / "ontology" / "edges.yaml").write_text(yaml.safe_dump({"edges": [
            {"edge_id": "alpha__of_gamma", "level": "physical", "type": "foreign_key",
             "join_rule": "alpha.GammaRef = gamma.GammaRef",
             "endpoints": {"from": {"concept": "Alpha", "cardinality": "0..N"},
                           "to": {"concept": "Gamma", "cardinality": "1"}}}]}))
    return root


# --- IT MUST NOT FALL BACK TO THE ONTOLOGY ------------------------------------------------------
# THE DEFECT THIS GUARDS. "Use the measured artifact if present, else the ontology" looks like it
# works — every bundle that has an ontology keeps its lines — and it IS the conflation being removed.


def test_a_bundle_whose_columns_DECLARE_nothing_draws_boxes_and_no_lines(tmp_path):
    # CHANGED DELIBERATELY, 2026-09-28. This model is now built from the DESCRIPTORS — the same file
    # the page reads — so a relation that exists HAS a box whether or not anything references it.
    # Drawing the boxes is the honest answer to "what is on this plane": the old empty page could not
    # distinguish "no relations" from "no relationships", and those are different facts.
    m = E.build(root=_bundle(tmp_path))
    assert [e["id"] for e in m["entities"]] == ["alpha", "gamma"]
    assert m["relationships"] == []


def test_the_empty_state_NAMES_what_is_missing_and_how_to_produce_it(tmp_path):
    # THE DENOMINATOR IS STILL THE POINT, only the subject moved: this model is built from the
    # DESCRIPTORS, so the state it cannot draw from is "no descriptor", not "no measured artifact".
    (tmp_path / "data" / "sources").mkdir(parents=True, exist_ok=True)
    m = E.build(root=tmp_path)
    u = m["unavailable"]
    assert "data/sources/ holds no descriptor" in u["reason"]
    assert "will not borrow another plane" in u["reason"]
    assert m["entities"] == [] and m["relationships"] == []


def _served_bundle(root, *, references=None, measured=True):
    """A bundle whose SERVED plane is authored: data/datasets + data/references_served."""
    _bundle(root)                                        # the sources plane, unmeasured
    (root / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    cols = {"v_fact": [("FactKey", "primary_key"), ("DimKey", "foreign_key"), ("Amount", "value")],
            "v_dim": [("DimKey", "primary_key"), ("Label", "discriminator")]}
    refs_for_descriptor = references if references is not None else [{
        "from": {"relation": "v_fact", "column": "DimKey"},
        "to": {"relation": "v_dim", "column": "DimKey"},
        "cardinality": {"child": "many", "parent": "one"},
        "participation": {"child": "mandatory", "parent": "mandatory"},
    }] if measured else []
    _decl = {}
    for r in refs_for_descriptor:
        _decl.setdefault(r["from"]["relation"], {})[r["from"]["column"]] = {
            "to": f"{r['to']['relation']}.{r['to']['column']}",
            **({"cardinality": r["cardinality"]} if r.get("cardinality") else {}),
            **({"participation": {k: v for k, v in (r.get("participation") or {}).items()
                                  if k in ("child", "parent")}} if r.get("participation") else {}),
        }
    for stem, cs in cols.items():
        _d = _decl.get(stem, {})
        (root / "data" / "datasets" / f"{stem}.yaml").write_text(yaml.safe_dump(
            {"of": stem, "table": {"name": stem, "schema": "own_schema"},
             "columns": [{"name": c, "type": "bigint", "role": r,
                          **({"references": _d[c]} if c in _d else {})} for c, r in cs]}))
    if not measured:
        return root
    (root / "data" / "references_served").mkdir(parents=True, exist_ok=True)
    refs = references if references is not None else [{
        "id": "v_fact.DimKey__v_dim.DimKey",
        "from": {"relation": "v_fact", "column": "DimKey"},
        "to": {"relation": "v_dim", "column": "DimKey"},
        "parent_key_role": "identity", "verdict": "real", "drawn": True,
        "cardinality": {"child": "many", "parent": "one"},
        "participation": {"child": "mandatory", "parent": "mandatory",
                          "parent_unreferenced": 0},
        "evidence": {"child_nonnull": 9, "orphan_rows": 0, "orphan_distinct": 0,
                     "parent_distinct": 3},
        "name_match": True,
    }]
    by_child = {stem: {"of": stem, "relation": f"own_schema.{stem}",
                       "admission": {"inclusion_required": 1.0},
                       "references": [], "references_dangling": [], "candidates_rejected": []}
                for stem in cols}
    for r in refs:
        by_child[r["from"]["relation"]]["references"].append(r)
    for stem, doc in by_child.items():
        (root / "data" / "references_served" / f"{stem}.yaml").write_text(yaml.safe_dump(doc))
    return root


def test_the_served_plane_draws_its_own_population_not_the_sources_one(tmp_path):
    m = E.build(root=_served_bundle(tmp_path), plane="served")
    assert [e["id"] for e in m["entities"]] == ["v_dim", "v_fact"]
    assert "alpha" not in str([e["id"] for e in m["entities"]])
    assert m["counts"]["relationships"] == 1 and m["counts"]["proved"] == 1
    assert m["physical_plane"] == "served"
    # IT NAMES WHAT IT READ. This asserted `data/references_served` while the model was built from
    # that artifact; it is built from the descriptors now, and a self-report naming the wrong file is
    # how "the ER and the page disagree" stayed unexplained — both claimed to be reading the bundle.
    assert m["artifact_directory"] == "data/datasets"
    assert m["descriptor_plane"] == "data/datasets"
    assert m["evidence_artifact"] == "data/references_served"


def test_both_planes_still_say_plane_physical(tmp_path):
    # NEGATIVE CONTROL. `plane` is the PHYSICAL-vs-ontology discriminator the client branches on to
    # decide whether it may say the word "concept". Neither physical plane may change it — a client
    # that saw "served" there would fall through to the ontology wording.
    root = _served_bundle(tmp_path)
    assert E.build(root=root, plane="sources")["plane"] == "physical"
    assert E.build(root=root, plane="served")["plane"] == "physical"
    assert E.build(root=root, plane="served")["counts"]["concept_edges_total"] == 0


def test_the_served_plane_takes_its_key_from_the_DECLARED_role(tmp_path):
    # MUTANT-shaped: the served bundle has NO identity_evidence for its datasets at all (the profile
    # plane carries none for them). A projector reading the profile would badge no primary key and
    # the diagram would lose the one thing a key badge is for.
    m = E.build(root=_served_bundle(tmp_path), plane="served")
    dim = next(e for e in m["entities"] if e["id"] == "v_dim")
    fact = next(e for e in m["entities"] if e["id"] == "v_fact")
    assert dim["keys"] == ["DimKey"]
    assert [c["role"] for c in dim["columns"]] == ["primary_key", "discriminator"]
    assert [c["role"] for c in fact["columns"]] == ["primary_key", "foreign_key", "value"]


def test_an_unmeasured_served_plane_is_EMPTY_WITH_A_REASON_not_the_sources_lines(tmp_path):
    # THE DEFECT THIS FORBIDS: falling back to the other physical plane is exactly as wrong as
    # falling back to the ontology, and far easier to do by accident because both are "physical".
    # THE PROPERTY IS UNCHANGED and it is the important one: a plane with nothing of its own draws
    # NOTHING, and never the other plane's lines. Only the trigger moved — from "no measured
    # artifact" to "no descriptor", because the descriptor is what this model reads.
    root = tmp_path / "b"
    _bundle(root, references=[{"id": "a__g", "from": {"relation": "alpha", "column": "GammaRef"},
                               "to": {"relation": "gamma", "column": "GammaRef"},
                               "cardinality": {"child": "many", "parent": "one"},
                               "participation": {"child": "mandatory", "parent": "mandatory"}}])
    m = E.build(root=root, plane="served")                # sources is fully declared; served is empty
    assert m["entities"] == [] and m["relationships"] == []
    assert "data/datasets/ holds no descriptor" in m["unavailable"]["reason"]
    assert "alpha" not in str(m["entities"]) and "alpha" not in str(m["relationships"])
    assert m["physical_plane"] == "served"


def test_an_unknown_plane_refuses_rather_than_defaulting(tmp_path):
    m = E.build(root=_served_bundle(tmp_path), plane="ontology")
    assert m["entities"] == [] and "unknown physical plane" in m["unavailable"]["reason"]


def test_the_plane_table_pairs_each_descriptor_dir_with_its_own_artifact_dir():
    # NEGATIVE CONTROL for the ONE HOME rule: two planes must not share a directory on either side,
    # or one plane's measurement would overwrite the other's and the pair of tabs would show the
    # same picture twice.
    outs = [v["out"] for v in E.PLANES.values()]
    descs = [v["descriptors"] for v in E.PLANES.values()]
    assert len(set(outs)) == len(outs) and len(set(descs)) == len(descs)
    assert E.REFS_DIR == E.PLANES[E.DEFAULT_PLANE]["out"]


def test_an_ontology_present_does_NOT_become_the_physical_diagram(tmp_path):
    # MUTANT: the bundle has a perfectly good physical-looking edge in ontology/edges.yaml and no
    # measured artifact. A fallback would draw it. It must draw nothing and say why.
    m = E.build(root=_bundle(tmp_path, edges_yaml=True))
    # The boxes come from the descriptors now, so the page is not empty — but NOT ONE LINE may come
    # from ontology/edges.yaml, which is the property this test exists for and which is unchanged.
    assert m["relationships"] == []
    assert not any("Alpha" in str(v) for v in m["relationships"])
    assert "alpha__of_gamma" not in str(m)


def test_the_empty_state_still_carries_the_counts_the_header_reads(tmp_path):
    # An omitted `not_proved` paints "proof state unknown"; an omitted `unrealised_edges` paints
    # "undrawable edges unknown". Both over a page that is honestly empty.
    m = E.build(root=_bundle(tmp_path))
    assert m["unrealised_edges"] == [] and isinstance(m["unrealised_edges"], list)
    for k in ("proved", "not_proved", "disproved"):
        assert isinstance(m["counts"][k], int)


def test_no_root_at_all_is_ALSO_an_explicit_empty_and_not_a_crash():
    m = E.build(root=None)
    assert m["entities"] == [] and "no bundle root" in m["unavailable"]["reason"]


# --- CARDINALITY AND PARTICIPATION --------------------------------------------------------------
# THE DEFECT. Keys alone draw every relationship mandatory. Participation is the measured half a key
# cannot supply, and it belongs in `crow.min` at the OTHER end from the one people expect.


def test_an_unreferenced_parent_row_makes_the_CHILD_end_optional(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef", part=("mandatory", "optional"))]))
    r = m["relationships"][0]
    assert r["from"]["cardinality"] == "0..N" and r["from"]["crow"]["min"] == "zero"
    assert r["from"]["crow"]["max"] == "many"


def test_a_fully_referenced_parent_makes_the_CHILD_end_mandatory(tmp_path):
    # NEGATIVE CONTROL for the case above: the SAME cardinality, a DIFFERENT participation, and the
    # inner mark must change. Without it the two draw identically, which is the whole defect.
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef", part=("mandatory", "mandatory"),
             unreferenced=0)]))
    r = m["relationships"][0]
    assert r["from"]["cardinality"] == "1..N" and r["from"]["crow"]["min"] == "one"


def test_the_MANY_terminal_is_at_the_child_and_the_ONE_terminal_at_the_parent(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef")]))
    r = m["relationships"][0]
    assert r["from"]["entity"] == "alpha" and r["from"]["crow"]["max"] == "many"
    assert r["to"]["entity"] == "gamma" and r["to"]["crow"]["max"] == "one"


def test_a_key_PART_parent_draws_MANY_at_the_parent_end_too(tmp_path):
    # A reference into one column of a composite key names a VALUE SET, not a row. Drawing "1" there
    # would assert something the measurement explicitly did not find.
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef", card=("many", "many"),
             part=("mandatory", "mandatory"), unreferenced=0)]))
    r = m["relationships"][0]
    assert r["to"]["cardinality"] == "1..N" and r["to"]["crow"]["max"] == "many"


def test_a_child_row_with_no_parent_makes_the_PARENT_end_optional(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef", part=("optional", "mandatory"),
             unreferenced=0)]))
    assert m["relationships"][0]["to"]["cardinality"] == "0..1"


def test_every_drawn_line_has_a_terminal_at_BOTH_ends(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef")]))
    assert m["counts"]["with_cardinality"] == m["counts"]["relationships"] == 1
    assert m["unknown_cardinalities"] == []


def test_a_cardinality_outside_the_closed_set_is_REPORTED_not_swallowed(tmp_path):
    # MUTANT: an artifact that says something the closed vocabulary has no terminal for draws a line
    # with no crow's foot at all. That must surface as a number, not as a quietly plain line.
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef", card=("several", "one"))]))
    assert m["unknown_cardinalities"] and m["counts"]["with_cardinality"] == 0


# --- IDS, ENDPOINTS AND THE SILENT DROP ---------------------------------------------------------


def test_two_references_joining_one_PAIR_keep_different_ids_and_both_draw(tmp_path):
    # THE MEASURED REGRESSION. Two date-like columns of one relation pointing at one calendar. An id
    # derived from the relation pair alone collides and one line stops responding to selection.
    m = E.build(root=_bundle(
        tmp_path,
        sources={"alpha": ["AlphaRef", "First", "Second"], "gamma": ["GammaRef"]},
        references=[_ref("alpha", "First", "gamma", "GammaRef"),
                    _ref("alpha", "Second", "gamma", "GammaRef")]))
    assert len(m["relationships"]) == 2
    assert m["duplicate_ids"] == []
    assert {r["id"] for r in m["relationships"]} == {
        "alpha.First__gamma.GammaRef", "alpha.Second__gamma.GammaRef"}


def test_a_reference_to_an_unmeasured_relation_is_DISCLOSED_never_emitted_as_a_line(tmp_path):
    # THE HEADLINE RISK. The renderer returns null for an edge whose endpoint is not a node, with no
    # error and no callback — so emitting it would make it VANISH, which is worse than wrong.
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "omega", "OmegaRef")]))
    assert m["relationships"] == []
    assert [u["verdict"] for u in m["unrealised_edges"]] == ["unresolved_endpoint"]
    assert m["accounting_error"] == ""


def test_a_dangling_column_is_NOT_drawn_here_because_the_DQ_register_reports_it(tmp_path):
    # CHANGED DELIBERATELY, 2026-09-28, on the operator's instruction: "we must start to remove
    # redundant versions of the same ... lets agree on having one chain of events with SSOT."
    #
    # A dangling column — key-shaped, referencing nothing — WAS disclosed twice: here, as an
    # undrawable entry, and in the data-quality register as a finding with an id, a severity and a
    # page. CHECKED on contoso4 before removing it: references_dangling holds 4 entries
    # (product.CategoryKey, product.SubCategoryKey, customer.GeoAreaKey, store.GeoAreaKey) and the
    # register carries DQ-DANGLINGKEY-CATEGORYKEY, -SUBCATEGORYKEY and -GEOAREAKEY covering all of
    # them. The register is the better home: it has an owner and a lifecycle; this had neither.
    #
    # So the fact is NOT lost — it is single-homed. This test holds that the diagram no longer
    # carries a second copy, and it would fail if one came back.
    root = _bundle(tmp_path, references=[{
        "from": {"relation": "alpha", "column": "GammaRef"},
        "to": {"relation": "gamma", "column": "GammaRef"},
        "cardinality": {"child": "many", "parent": "one"},
        "participation": {"child": "mandatory", "parent": "mandatory"}}])
    m = E.build(root=root)
    # `alpha` also carries DeltaRef, which declares no reference at all — the dangling case.
    assert m["counts"]["relationships"] == 1
    assert m["unrealised_edges"] == []
    assert "DeltaRef" not in str(m["relationships"])
    # and the column is still THERE, on its box, as a plain column — not hidden
    alpha = next(e for e in m["entities"] if e["id"] == "alpha")
    assert "DeltaRef" in [c["name"] for c in alpha["columns"]]


def test_the_measured_key_becomes_the_PK_badge_without_editing_the_descriptor(tmp_path):
    root = _bundle(tmp_path, references=[_ref("alpha", "GammaRef", "gamma", "GammaRef")])
    m = E.build(root=root)
    alpha = next(e for e in m["entities"] if e["id"] == "alpha")
    assert alpha["keys"] == ["AlphaRef"]
    assert next(c for c in alpha["columns"] if c["name"] == "AlphaRef")["role"] == "primary_key"
    # and the descriptor on disk is UNTOUCHED — the role is overlaid, never written back
    on_disk = yaml.safe_load((root / "data" / "sources" / "alpha.yaml").read_text())
    assert all(c["role"] == "value" for c in on_disk["columns"])


def test_a_referencing_column_gets_the_FK_badge(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef")]))
    alpha = next(e for e in m["entities"] if e["id"] == "alpha")
    assert next(c for c in alpha["columns"] if c["name"] == "GammaRef")["role"] == "foreign_key"
    assert next(c for c in alpha["columns"] if c["name"] == "DeltaRef")["role"] == "value"


def test_a_composite_key_badges_EVERY_part(tmp_path):
    m = E.build(root=_bundle(
        tmp_path, references=[_ref("alpha", "GammaRef", "gamma", "GammaRef")],
        keys={"alpha": ["AlphaRef", "DeltaRef"], "gamma": ["GammaRef"]}))
    alpha = next(e for e in m["entities"] if e["id"] == "alpha")
    roles = {c["name"]: c["role"] for c in alpha["columns"]}
    pos = {c["name"]: c.get("key_position") for c in alpha["columns"]}
    # BOTH PARTS ARE `primary_key` NOW (ruling 2026-09-27) and the ORDER is a number beside them. The
    # old assertion expected `composite_key_part`, which is exactly why `role == "primary_key"` found no
    # key at all for a composite-keyed relation in mac_to_graph and mac_to_shacl.
    assert roles["AlphaRef"] == roles["DeltaRef"] == "primary_key"
    assert (pos["AlphaRef"], pos["DeltaRef"]) == (1, 2), pos


def test_a_relation_with_no_reference_still_gets_a_BOX(tmp_path):
    # It was MEASURED and found to carry none. That is a different fact from "not measured", and a
    # diagram that hid it would be reporting an absence as an absence of evidence.
    m = E.build(root=_bundle(tmp_path, references=[]))
    assert sorted(e["id"] for e in m["entities"]) == ["alpha", "gamma"]
    assert m["counts"]["components"] == 2


# --- PROOF, PLANE AND THE COUNTS THE HEADER READS -----------------------------------------------


def test_a_declared_reference_is_PROVED_and_its_why_names_the_declaration(tmp_path):
    # The `why` used to carry the row denominators, because the model read the measurement. It reads
    # the DESCRIPTOR now, which carries the measured cardinality and participation but not the
    # counters — those stay in data/references*/ where they were measured, and the model NAMES that
    # artifact (`evidence_artifact`) without reading it.
    #
    # PROVED, NOT UNPROVED, and the distinction matters: a declared reference exists only because
    # mac_descriptors promoted a measurement whose verdict was `real`, whose parent side was a whole
    # single-column identity and whose cardinality was many:one. Reporting that as "a number is
    # missing" would libel a relationship that passed a STRICTER bar than the counters alone.
    root = _bundle(tmp_path, references=[{
        "from": {"relation": "alpha", "column": "GammaRef"},
        "to": {"relation": "gamma", "column": "GammaRef"},
        "cardinality": {"child": "many", "parent": "one"},
        "participation": {"child": "mandatory", "parent": "optional"}}])
    m = E.build(root=root)
    pf = m["relationships"][0]["proof"]
    assert pf["state"] == "proved" and pf["members"] == pf["members_proved"] == 1
    assert "cardinality many:one" in pf["why"]
    assert "data/sources/alpha.yaml" in pf["ref"]
    assert m["evidence_artifact"] == "data/references"


def test_participation_is_spelled_out_in_the_proof_sentence(tmp_path):
    # Participation is the half a key cannot supply — whether some parent rows are referenced by NO
    # child — so it must reach the reader, and the crow's feet alone do not say it in words. It
    # travels on the DECLARATION now rather than as a `parent_unreferenced` count, because the count
    # is evidence and stays in data/references*/ with the rest of the evidence.
    root = _bundle(tmp_path, references=[{
        "from": {"relation": "alpha", "column": "GammaRef"},
        "to": {"relation": "gamma", "column": "GammaRef"},
        "cardinality": {"child": "many", "parent": "one"},
        "participation": {"child": "mandatory", "parent": "optional"}}])
    why = E.build(root=root)["relationships"][0]["proof"]["why"]
    assert "participation child mandatory / parent optional" in why
    # and the OPPOSITE case must read differently, or the sentence is a constant
    root2 = _bundle(tmp_path / "b", references=[{
        "from": {"relation": "alpha", "column": "GammaRef"},
        "to": {"relation": "gamma", "column": "GammaRef"},
        "cardinality": {"child": "many", "parent": "one"},
        "participation": {"child": "mandatory", "parent": "mandatory"}}])
    assert "parent mandatory" in E.build(root=root2)["relationships"][0]["proof"]["why"]


def test_an_ambiguous_reference_is_reported_by_the_DQ_register_not_twice_here(tmp_path):
    # Same de-duplication as the dangling case, and CHECKED the same way before removing it: on
    # contoso4 the register carries DQ-AMBIGREF-CURRENCYCODE at severity HIGH — "`CurrencyCode`
    # includes perfectly into 2 different keys — which is THE reference?". `ambiguous_with` was a
    # field of the MEASUREMENT; the descriptor declares one target or none, because a promotion that
    # cannot choose does not declare. So an ambiguous pair reaches the reader as a data-quality
    # finding with an owner, and this diagram draws only what was actually declared.
    root = _bundle(tmp_path, references=[{
        "from": {"relation": "alpha", "column": "GammaRef"},
        "to": {"relation": "gamma", "column": "GammaRef"},
        "cardinality": {"child": "many", "parent": "one"},
        "participation": {"child": "mandatory", "parent": "mandatory"}}])
    m = E.build(root=root)
    assert m["counts"]["ambiguous"] == 0
    assert m["counts"]["relationships"] == 1


def test_the_payload_declares_its_PLANE_and_claims_no_ontology_edges(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef")]))
    assert m["plane"] == "physical"
    assert m["counts"]["concept_edges"] == 0 and m["counts"]["concept_edges_total"] == 0
    assert m["counts"]["business"] == 0
    assert all(r["level"] == "physical" for r in m["relationships"])


def test_the_join_columns_travel_as_FIELDS_and_the_sentence_is_only_rendered(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef")]))
    r = m["relationships"][0]
    assert r["from"]["columns"] == ["GammaRef"] and r["to"]["columns"] == ["GammaRef"]
    assert r["join_rule"] == "alpha.GammaRef = gamma.GammaRef"
