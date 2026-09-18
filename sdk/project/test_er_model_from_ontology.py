"""Unit tests for the ONTOLOGY relationship builder's PURE rules — the proof roll-up and the
undrawable-edge reasons. No filesystem, no warehouse, no bundle on disk.

THIS MODULE IS NOT WIRED TO THE ER DIAGRAM ANY MORE. It is the ontology plane's machinery and its
rules are still worth keeping honest, so the tests moved with it rather than being deleted.
`_components` is plane-neutral and stayed in `er_model`; its tests are in test_er_model.py.

WHY THESE THREE AND NOT `build`. Each one encodes a defect the projector actually shipped, and each
is a pure function of its inputs, so each can be mutated. `build` is the wiring around them.

Every rule gets a mutant per way it can be wrong AND a negative control per correctly-modelled
shape that must NOT trip it — the discipline the framework's gates use, because a rule that only
ever sees the happy case cannot be shown to work.
"""

from sdk.project import er_model_from_ontology as E

# --- the proof roll-up: WEAKEST WINS ----------------------------------------------------------
# THE DEFECT. One drawn line realises several concept edges (seven, measured). The projector carried
# `cardinality` and dropped `verified_by`/`confidence`, so the view drew a proved relationship and an
# unproved one identically. Rolling up to the BEST member would have re-created that lie with the
# evidence present — which is the trap this estate has fallen into repeatedly.


def _m(edge, state, confidence="C"):
    return {"edge_id": edge, "confidence": confidence, "proof": {"state": state, "ref": "r"}}


def test_a_line_of_proved_members_is_proved():
    proof, conf = E._roll_up([_m("a", E.PROVED), _m("b", E.PROVED)])
    assert proof["state"] == E.PROVED
    assert (proof["members_proved"], proof["members"]) == (2, 2)  # the denominator travels
    assert conf == "C"


def test_one_unproved_member_makes_the_whole_line_unproved():
    # MUTANT: six of seven measured. A line drawn as fully proved here is the estate's defect.
    members = [_m(f"e{i}", E.PROVED) for i in range(6)] + [_m("weak", E.UNPROVED)]
    proof, _ = E._roll_up(members)
    assert proof["state"] == E.UNPROVED
    assert proof["from_edge"] == "weak"  # and it NAMES which of the seven is weak
    assert (proof["members_proved"], proof["members"]) == (6, 7)


def test_disproved_outranks_every_other_weakness():
    # A member whose own evidence CONTRADICTS it is the worst state; nothing may mask it.
    proof, _ = E._roll_up([_m("a", E.PROVED), _m("b", E.UNPROVED), _m("c", E.DISPROVED)])
    assert proof["state"] == E.DISPROVED


def test_a_recorded_deferral_does_not_draw_as_a_proof():
    proof, _ = E._roll_up([_m("a", E.PROVED), _m("b", E.DEFERRED)])
    assert proof["state"] == E.DEFERRED and proof["state"] != E.PROVED


def test_unresolved_is_weaker_than_unproved():
    # "the citation is broken" is a worse state than "there is no citation": one is a repair to make,
    # the other is an honest absence.
    proof, _ = E._roll_up([_m("a", E.UNPROVED), _m("b", E.UNRESOLVED)])
    assert proof["state"] == E.UNRESOLVED


def test_confidence_rolls_up_to_the_weakest_tier_too():
    # MEASURED: one business line realises market__of_country (C) and market__of_region (I). Printing
    # C over it would assert SME confirmation of an inferred relationship.
    _, conf = E._roll_up([_m("a", E.PROVED, "C"), _m("b", E.PROVED, "I")])
    assert conf == "I"
    _, conf = E._roll_up([_m("a", E.PROVED, "I"), _m("b", E.PROVED, "Q")])
    assert conf == "Q"


def test_an_absent_confidence_tier_is_weaker_than_Q():
    # Unknown trust is not a middling amount of trust.
    _, conf = E._roll_up([_m("a", E.PROVED, "Q"), _m("b", E.PROVED, None)])
    assert conf is None


# --- why an edge cannot be drawn: THREE STATES, NEVER ONE COUNT -------------------------------
# THE DEFECT. Eight of thirty-two concept edges yielded no line and the projector `continue`d past
# all of them, so the diagram showed 24 relationships and was silent about the rest.


def test_realised_without_a_join_says_so_and_quotes_the_realisation():
    why = E._why_undrawable(
        {"realized_by": "v_fact_kpi.seller_code - carried on the fact; a GROUP BY, not a join"}
    )
    assert "seller_code" in why and "no key equality" in why


def test_a_resolution_rule_is_also_a_realisation():
    why = E._why_undrawable({"resolved_by": "ontology/concepts/region.yaml#contract.rules.x"})
    assert "region.yaml" in why and "NO realisation" not in why


def test_no_realisation_at_all_is_a_DIFFERENT_finding_from_no_join():
    # The only real hole, and it must not read like the two states above: one is correct modelling,
    # this one is nobody having worked the relationship out.
    assert "NO realisation at all" in E._why_undrawable({"edge_id": "x"})


def test_an_unparseable_join_rule_is_reported_as_unparseable():
    # NEGATIVE CONTROL for the two above: a rule IS declared, so neither "realised without a join"
    # nor "no realisation" is the truth.
    why = E._why_undrawable({"join_rule": "SOMETHING THE PARSER CANNOT READ"})
    assert "cannot read" in why and "no realisation" not in why.lower()


