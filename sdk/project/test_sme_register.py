"""The SME catalogue half of the register projector, and its markdown renderer. Offline: every
bundle is a temporary directory built here, in a neutral retail domain.

WHY THESE CASES. Each is a defect the register shipped, measured on a real bundle: a free-text owner
sentence split at its first dash published its tail as a question; an owner with no dash published a
placeholder sentence as a question; withdrawn and superseded change-record entries posed as open
questions; every measure that declared its type was asked how it aggregates; a change record that
failed to parse removed all of its rows without a word; and the markdown cut questions at 150
characters, broke on newlines and labelled every row a sign-off. Every case has a negative control
where one exists, so a rule that fires on everything cannot pass.
"""

from __future__ import annotations

import json

import pytest
import yaml

from sdk.project import objects as O
from sdk.project import ontology_quality as Q

ALIASES = ("id", "question", "concept", "concept_title")


def _concept(name, klass="reference", **extra):
    doc = {"metadata": {"confidence": "C"}, "concept": {"name": name, "label": name.title(), "class": klass}}
    for k, v in extra.items():
        if k in ("semantics", "identity"):
            doc["concept"][k] = v
        else:
            doc[k] = v
    return doc


def _bundle(tmp_path, concepts=None, interventions=None, raw_ledger=None):
    cdir = tmp_path / "ontology" / "concepts"
    cdir.mkdir(parents=True)
    for stem, doc in (concepts or {}).items():
        (cdir / f"{stem}.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    if interventions is not None or raw_ledger is not None:
        (tmp_path / "interventions").mkdir()
        text = raw_ledger if raw_ledger is not None else yaml.safe_dump({"interventions": interventions}, sort_keys=False)
        (tmp_path / "interventions" / "ledger.yaml").write_text(text)
    return tmp_path


def _build(root, concepts=None):
    return Q.build(concepts or {}, {}, [], root=root)


def _codes(out):
    return [f["code"] for f in out["findings"] if f.get("category") == Q.SME_FINDING_CATEGORY]


def _entry(eid, **kw):
    e = {"id": eid, "what": "w", "why": "y", "status": "applied", "objects": ["concept:store"]}
    e.update(kw)
    return e


# --- the change record: structured asks only ------------------------------------------------------


def test_owner_string_with_a_dash_inside_a_parenthesis_is_a_finding_never_a_question(tmp_path):
    root = _bundle(tmp_path, interventions=[_entry("INT-0001", sme_owner="none required (nothing changed — only wording).")])
    out = _build(root)
    assert out["sme_questions"] == []
    assert _codes(out) == ["sme-ask-unstructured"]
    # the tail of the owner sentence appears nowhere as question text
    assert "only wording" not in json.dumps(out["sme_questions"])


def test_owner_string_without_a_dash_is_a_finding_never_a_placeholder_question(tmp_path):
    root = _bundle(tmp_path, interventions=[_entry("INT-0002", sme_owner="domain owner")])
    out = _build(root)
    assert out["sme_questions"] == []
    assert "UNSPECIFIED" not in json.dumps(out)
    assert _codes(out) == ["sme-ask-unstructured"]


@pytest.mark.parametrize(
    "extra",
    [
        {"status": "withdrawn"},
        {"status": "Superseded"},
        {"status": "ratified"},
        {"status": "closed"},
        {"withdrawn_by": "operator"},
        {"superseded_by": "INT-0009"},
        {"ratified_by": "sme-1"},
    ],
)
def test_closed_entries_emit_nothing_at_all(tmp_path, extra):
    sme = {"ask_kind": "question", "owner_role": "domain owner", "ask": "Is the store master the source of opening dates?"}
    root = _bundle(tmp_path, interventions=[_entry("INT-0003", sme=sme, sme_owner="domain owner", **extra)])
    out = _build(root)
    assert out["sme_questions"] == [] and _codes(out) == []


def test_an_entry_named_by_another_entrys_supersedes_emits_nothing(tmp_path):
    ask = {"ask_kind": "sign_off", "owner_role": "domain owner", "ask": "Do weekly net sales add up to the month?"}
    root = _bundle(
        tmp_path,
        interventions=[
            _entry("INT-0010", sme=ask),  # the OLDER entry records nothing about its supersession
            _entry("INT-0011", sme=dict(ask, ask="Do weekly net sales add up to the quarter?"), supersedes="INT-0010"),
        ],
    )
    keys = [r["key"] for r in _build(root)["sme_questions"]]
    assert keys == ["intervention:INT-0011#sme"]


def test_a_structured_sign_off_and_question_are_distinct_kinds_with_verbatim_text(tmp_path):
    long_ask = "Is net sales a flow that adds up over weeks and stores? " + "Context sentence. " * 60
    root = _bundle(
        tmp_path,
        interventions=[
            _entry("INT-0020", sme={"ask_kind": "sign_off", "owner_role": "finance SME", "ask": long_ask}),
            _entry("INT-0021", status="proposed", sme={"ask_kind": "question", "owner_role": "store planning", "ask": "Which calendar does a store week follow?"}),
        ],
    )
    out = _build(root)
    by_key = {r["key"]: r for r in out["sme_questions"]}
    assert by_key["intervention:INT-0020#sme"]["kind"] == "sign_off"
    assert by_key["intervention:INT-0021#sme"]["kind"] == "question"
    assert by_key["intervention:INT-0020#sme"]["text"] == long_ask.strip()  # never cut
    assert out["counts"]["sme_questions_by_kind"] == {"question": 1, "sign_off": 1}


def test_a_fragment_in_a_structured_ask_is_a_finding_not_a_question(tmp_path):
    root = _bundle(tmp_path, interventions=[_entry("INT-0030", sme={"ask_kind": "question", "owner_role": "x", "ask": "only the notation for naming the model)."})])
    out = _build(root)
    assert out["sme_questions"] == [] and _codes(out) == ["sme-ask-incomplete"]


def test_ask_kind_none_is_silent_and_an_unknown_ask_kind_is_a_finding(tmp_path):
    root = _bundle(
        tmp_path,
        interventions=[
            _entry("INT-0040", sme_owner="none required", sme={"ask_kind": "none"}),
            _entry("INT-0041", sme={"ask_kind": "maybe", "ask": "Is this a question?"}),
        ],
    )
    out = _build(root)
    assert out["sme_questions"] == []
    assert _codes(out) == ["sme-block-invalid"]


def test_a_data_plane_ask_is_routed_and_an_operator_ask_is_an_operator_item(tmp_path):
    ask = "Which source column carries the store's opening date?"
    root = _bundle(
        tmp_path,
        interventions=[
            _entry("INT-0050", objects=["dataset:stores", "transform:t_stores"], dq_ids=["DQ-STORE-01"], sme={"ask_kind": "question", "owner_role": "data owner", "ask": ask}),
            _entry("INT-0051", sme={"ask_kind": "question", "owner_role": "data owner", "ask": ask, "plane": "data"}),
            _entry("INT-0052", sme={"ask_kind": "operator", "ask": "Should the reach measure be served at all?"}),
            # negative control: a mixed entry touches a concept, so it stays on the ontology list
            _entry("INT-0053", objects=["dataset:stores", "concept:store"], sme={"ask_kind": "question", "owner_role": "data owner", "ask": ask}),
        ],
    )
    out = _build(root)
    assert [r["key"] for r in out["sme_questions"]] == ["intervention:INT-0053#sme"]
    assert [r["key"] for r in out["sme_routed_to_data"]] == ["intervention:INT-0050#sme", "intervention:INT-0051#sme"]
    assert out["sme_routed_to_data"][0]["dq_ids"] == ["DQ-STORE-01"]
    assert [o["key"] for o in out["sme_operator_items"]] == ["intervention:INT-0052#sme"]
    assert out["counts"]["sme_operator_items"] == 1 and out["counts"]["sme_routed_to_data"] == 2


def test_an_unreadable_change_record_is_a_high_finding_never_an_empty_list(tmp_path):
    root = _bundle(tmp_path, raw_ledger="interventions: [unclosed\n  - id: :")
    out = _build(root)
    f = [x for x in out["findings"] if x.get("code") == "sme-source-unreadable"]
    assert len(f) == 1 and f[0]["severity"] == "high" and f[0]["concept_title"] == "interventions/ledger.yaml"


def test_an_unreadable_concept_file_is_a_finding(tmp_path):
    root = _bundle(tmp_path)
    (root / "ontology" / "concepts" / "broken.yaml").write_text("concept: [unclosed\n")
    out = Q.build({"broken": {}}, {}, [], root=root)
    assert "sme-source-unreadable" in _codes(out)


# --- the detectors ------------------------------------------------------------------------------


def test_a_measure_with_a_declared_measure_type_is_not_asked_how_it_aggregates(tmp_path):
    concepts = {"net_sales": _concept("net_sales", "measure", semantics={"measure_type": "mac.MeasureType.Flow"})}
    out = _build(_bundle(tmp_path, concepts), concepts)
    assert out["sme_questions"] == []
    assert not [f for f in out["findings"] if f["id"] == "noagg.net_sales"]  # the finding twin agrees


@pytest.mark.parametrize("semantics", [{}, {"measure_type": "mac.MeasureType.NoSuchType"}, {"measure_type": "Flow"}])
def test_a_measure_without_a_resolvable_measure_type_is_asked(tmp_path, semantics):
    concepts = {"net_sales": _concept("net_sales", "measure", semantics=semantics)}
    out = _build(_bundle(tmp_path, concepts), concepts)
    assert [r["key"] for r in out["sme_questions"]] == ["concept:net_sales#measure_type"]
    assert [f for f in out["findings"] if f["id"] == "noagg.net_sales"]


def test_an_enumeration_read_from_a_register_is_not_asked_whether_it_is_closed(tmp_path):
    realized = _concept("carrier", "enumeration", values={"closure": "closed", "realized_by": {"udf": "mac.canon.enum_from_register"}})
    unknown = _concept("channel", "enumeration", values={"closure": "unknown", "items": [{"code": "WEB"}]})
    concepts = {"carrier": realized, "channel": unknown}
    out = _build(_bundle(tmp_path, concepts), concepts)
    assert [r["key"] for r in out["sme_questions"]] == ["concept:channel#enumeration"]


def test_confidence_rules_and_identity_keep_their_kinds(tmp_path):
    doubtful = _concept("region", contract={"rules": [{"id": "region.resolve.by_name", "confidence": "P", "subject": "name to code"}]})
    doubtful["metadata"]["confidence"] = "I"
    stub = _concept("sales_district", identity={"kind": "sme_pending"})
    stub["metadata"]["confidence"] = "I"  # a refuse-stub: no confidence sign-off, only its identity question
    concepts = {"region": doubtful, "sales_district": stub}
    out = _build(_bundle(tmp_path, concepts), concepts)
    kinds = {r["key"]: r["kind"] for r in out["sme_questions"]}
    assert kinds == {
        "concept:region#confidence": "sign_off",
        "rule:region.resolve.by_name#confidence": "sign_off",
        "concept:sales_district#identity": "question",
    }


def test_both_concept_open_question_forms_are_emitted_verbatim(tmp_path):
    multi = "Does FLAG mean a flagship store?\nOr a store with a flag on its sign?"
    concept = _concept(
        "store",
        "enumeration",
        values={
            "closure": "closed",
            "items": [
                {"code": "FLAG", "confidence": "Q", "open_question": multi},
                {"code": "Pop up", "confidence": "Q", "open_question": "Is a pop-up store counted as a store?"},
                {"code": "OUTLET", "confidence": "I"},  # doubtful and unasked: a finding, not a question
                {"code": "MALL", "confidence": "C"},
            ],
        },
        open_questions=[
            {"id": "oq1", "question": "Is a store's opening date its first sale?", "status": "OPEN", "owner_for_resolution": "store planning", "priority": "medium"},
            {"id": "oq2", "question": "Settled already?", "status": "RESOLVED"},
        ],
    )
    concepts = {"store": concept}
    out = _build(_bundle(tmp_path, concepts), concepts)
    rows = {r["key"]: r for r in out["sme_questions"]}
    assert set(rows) == {
        "concept:store#open_questions[oq1]",
        "concept:store#values[FLAG].open_question",
        "concept:store#values[Pop%20up].open_question",  # a space is encoded, so the key stays one token
    }
    assert rows["concept:store#values[FLAG].open_question"]["text"] == multi
    oq1 = rows["concept:store#open_questions[oq1]"]
    assert (oq1["origin"], oq1["owner_role"], oq1["declared_priority"], oq1["declared_status"]) == ("concept-field", "store planning", "medium", "OPEN")
    assert all(r["fileable"] for r in rows.values())
    unasked = [f for f in out["findings"] if f.get("code") == "sme-value-unasked"]
    assert len(unasked) == 1 and "OUTLET" in unasked[0]["detail"] and "MALL" not in unasked[0]["detail"]


# --- the row contract ---------------------------------------------------------------------------


def test_every_row_carries_the_transition_aliases_and_no_conversation_fields(tmp_path):
    concepts = {"store": _concept("store", open_questions=[{"id": "oq1", "question": "Is a store open on its handover date?"}])}
    root = _bundle(tmp_path, concepts, interventions=[_entry("INT-0060", sme={"ask_kind": "question", "owner_role": "store planning", "ask": "Which stores count as comparable?"})])
    out = _build(root, concepts)
    assert out["sme_questions"] and out["sme_catalogue_format"] == Q.SME_CATALOGUE_FORMAT
    for r in out["sme_questions"]:
        for a in ALIASES:
            assert a in r
        assert r["id"] == r["key"] and r["question"] == r["text"]
        assert not {"status", "current", "priority", "owner", "why"} & set(r)
    by_key = {r["key"]: r for r in out["sme_questions"]}
    assert by_key["concept:store#open_questions[oq1]"]["concept"] == "store"
    assert by_key["concept:store#open_questions[oq1]"]["concept_title"] == "Store"


def test_the_projector_never_reads_the_sme_ledger(tmp_path):
    concepts = {"store": _concept("store", open_questions=[{"id": "oq1", "question": "Is a store open on its handover date?"}])}
    root = _bundle(tmp_path, concepts)
    before = json.dumps(_build(root, concepts), sort_keys=True)
    (root / "governance").mkdir()
    (root / "governance" / "sme-questions.yaml").write_text("format: mac.sme-questions/1\nentries: [{status: applied}]\n")
    assert json.dumps(_build(root, concepts), sort_keys=True) == before


def test_complete_sentence_guard():
    assert Q.complete_sentence("Is a store open on its handover date?")
    assert Q.complete_sentence("“West” names which scheme?")
    # a sentence that opens with a lower-case identifier is whole, not a cut-off tail
    assert Q.complete_sentence("price_tier 3 is the list price; is tier 1 a staff price?")
    assert Q.complete_sentence("store.opening_date is read from the store master. Is that right?")
    for bad in (
        "only the notation for naming the model).",
        "two items. (1) Ratify the terms.",  # a lower-case word that is not an identifier
        "price_tier 3 is the list price (tier 1 is not.",  # an identifier does not excuse a torn parenthesis
        "domain owner",
        "",
        None,
        "Why?",
        "Is it (open?",
    ):
        assert not Q.complete_sentence(bad)


# --- the renderer -------------------------------------------------------------------------------


def _render(tmp_path, register, needs=None):
    O._emit_ontology_sme_md(register, needs or {"needs": [], "findings": []}, tmp_path, "RETAIL")
    return (tmp_path / "SME-QUESTIONS.md").read_text()


def test_renderer_has_two_counted_sections_full_text_and_no_status_column(tmp_path):
    long_text = "Is net sales additive over weeks? " + ("x" * 2000)
    multi = "First line of the question?\n\n| not | a | table |\n## not a heading"
    register = {
        "sme_questions": [
            Q.sme_row(key="concept:store#open_questions[oq1]", origin="concept-field", kind="question", text=multi, concepts=["store"]),
            Q.sme_row(key="intervention:INT-0001#sme", origin="register", kind="sign_off", text=long_text),
        ],
        "findings": [Q.sme_finding("sme-ask-unstructured", "low", "INT-0002", "names an SME owner but carries no structured ask", "d")],
        "sme_operator_items": [],
    }
    needs = {
        "needs": [Q.sme_row(key="oracle-group:class:region", origin="oracle", kind="question", text="Which scheme does West name?", members=["oracle:Q1#needs_sme", "oracle:Q2#needs_sme"], variants=1)],
        "findings": [],
    }
    md = _render(tmp_path, register, needs)
    assert "## Questions — 2" in md and "## Sign-offs — 1" in md
    assert "Conversation status is not part of this projection" in md
    assert "| status |" not in md and "priority —" not in md.lower()
    # full text round-trips out of its quote block, 2,000 characters and all
    quoted = "\n".join(ln[2:] if ln.startswith("> ") else "" for ln in md.splitlines() if ln.startswith(">"))
    assert long_text in quoted
    # a multi-line text stays inside its block: every one of its lines is quoted, none is live markdown
    for ln in multi.splitlines():
        assert (f"> {ln}" if ln.strip() else ">") in md.splitlines()
    assert "## not a heading" not in [ln for ln in md.splitlines()]
    assert "`oracle:Q1#needs_sme`" in md and "1 other wording(s)" in md
    assert "## Findings — 1 (not questions)" in md and "sme-ask-unstructured" in md
    assert "1 change-record entry names an SME owner" in md


def test_renderer_names_an_oracle_collection_failure(tmp_path):
    md = _render(tmp_path, {"sme_questions": [], "findings": []}, {"needs": [], "findings": [], "error": "ImportError: boom"})
    assert "Oracle needs were not collected:** ImportError: boom" in md
    assert "## Questions — 0" in md
