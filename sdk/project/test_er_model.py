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
    for stem, cols in srcs.items():
        (root / "data" / "sources" / f"{stem}.yaml").write_text(yaml.safe_dump(
            {"of": stem, "table": {"name": stem, "schema": "alpha_schema"},
             "columns": [{"name": c, "type": "bigint", "role": "value"} for c in cols]}))
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


def test_a_bundle_with_no_measured_artifact_draws_NOTHING(tmp_path):
    m = E.build(root=_bundle(tmp_path))
    assert m["entities"] == [] and m["relationships"] == []


def test_the_empty_state_NAMES_what_is_missing_and_how_to_produce_it(tmp_path):
    m = E.build(root=_bundle(tmp_path))
    u = m["unavailable"]
    assert "data/references" in u["reason"] and "2 declared source relation(s)" in u["reason"]
    assert "mac_references.py" in u["how"]
    assert "ontology/edges.yaml" in u["note"]


def test_an_ontology_present_does_NOT_become_the_physical_diagram(tmp_path):
    # MUTANT: the bundle has a perfectly good physical-looking edge in ontology/edges.yaml and no
    # measured artifact. A fallback would draw it. It must draw nothing and say why.
    m = E.build(root=_bundle(tmp_path, edges_yaml=True))
    assert m["relationships"] == [] and "unavailable" in m
    assert not any("Alpha" in str(v) for v in m["relationships"])


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


def test_a_dangling_column_becomes_a_disclosure_with_NO_far_side(tmp_path):
    m = E.build(root=_bundle(
        tmp_path,
        references=[_ref("alpha", "GammaRef", "gamma", "GammaRef")],
        dangling=[{"id": "alpha.DeltaRef__?",
                   "from": {"relation": "alpha", "column": "DeltaRef"}, "to": None,
                   "verdict": "dangling", "basis": "key_naming_convention",
                   "basis_detail": "self-calibrated from this bundle's own measured key names",
                   "evidence": {"child_distinct": 3}}]))
    u = m["unrealised_edges"][0]
    assert u["to_relation"] is None and u["from_relation"] == "alpha"
    assert u["from_columns"] == ["DeltaRef"]
    assert "NO relation in this bundle has it as a key column" in u["reason"]
    assert u["proof"]["state"] == "unproved"     # weaker evidence, and it must not draw as proved
    assert m["counts"]["dangling"] == 1


# --- THE BOXES: COLUMNS, KEYS AND THE ROLE OVERLAY ----------------------------------------------


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
    assert roles["AlphaRef"] == roles["DeltaRef"] == "composite_key_part"


def test_a_relation_with_no_reference_still_gets_a_BOX(tmp_path):
    # It was MEASURED and found to carry none. That is a different fact from "not measured", and a
    # diagram that hid it would be reporting an absence as an absence of evidence.
    m = E.build(root=_bundle(tmp_path, references=[]))
    assert sorted(e["id"] for e in m["entities"]) == ["alpha", "gamma"]
    assert m["counts"]["components"] == 2


# --- PROOF, PLANE AND THE COUNTS THE HEADER READS -----------------------------------------------


def test_a_measured_reference_is_PROVED_and_its_why_carries_the_denominator(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef")]))
    p = m["relationships"][0]["proof"]
    assert p["state"] == "proved" and p["members"] == p["members_proved"] == 1
    assert "100 of 100 row(s) matched" in p["why"] and "0 orphan row(s)" in p["why"]
    assert "data/references/alpha.yaml#" in p["ref"]


def test_participation_is_spelled_out_in_the_proof_sentence(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef", unreferenced=3)]))
    why = m["relationships"][0]["proof"]["why"]
    assert "participation, not cardinality" in why and "3 of 10 parent key value(s)" in why


def test_an_ambiguous_reference_says_so_and_is_still_drawn(tmp_path):
    m = E.build(root=_bundle(tmp_path, references=[
        _ref("alpha", "GammaRef", "gamma", "GammaRef",
             ambiguous_with=["gamma.Other"], needs_ruling="value inclusion cannot separate them")]))
    r = m["relationships"][0]
    assert r["ambiguous_with"] == ["gamma.Other"]
    assert "AMBIGUOUS" in r["proof"]["why"] and "needs a ruling" in r["proof"]["why"]
    assert m["counts"]["ambiguous"] == 1


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
