"""The oracle collector: which test oracles wait on an SME, grouped so one question asked of fifteen
tests is one row. Offline; every corpus is a temporary directory in a neutral retail domain.

WHY THESE CASES. Measured on a real corpus: 26 oracles carried needs-SME fields and none reached any
list of SME questions; 3 of them had the question text without the flag; one class of 15 oracles
worded its question two ways. Each rule below has a negative control.
"""

from __future__ import annotations

import json

import yaml

from sdk.acceptance import sme_needs as N

WEST = "Which regional scheme does West name?"


def _oracle(root, qid, **fields):
    d = root / "acceptance" / "oracle"
    d.mkdir(parents=True, exist_ok=True)
    doc = {"question": {"id": qid, "text": f"How much did stores sell in {qid}?"}}
    doc.update(fields)
    (d / f"{qid}.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))


def _codes(out):
    return sorted(f["code"] for f in out["findings"])


def test_absent_oracle_directory_is_a_stated_absence(tmp_path):
    out = N.build(tmp_path)
    assert out["state"] == "absent" and out["needs"] == [] and out["counts"]["oracle_files"] == 0


def test_a_class_groups_its_members_and_two_wordings_are_a_finding(tmp_path):
    for q in ("Q1", "Q2", "Q3"):
        _oracle(tmp_path, q, needs_sme=True, needs_sme_class="region.scheme", needs_sme_question=WEST)
    _oracle(tmp_path, "Q4", needs_sme=True, needs_sme_class="region.scheme", needs_sme_question="Which scheme is West in?")
    _oracle(tmp_path, "Q5", needs_sme=False)  # negative control: explicitly not needing an SME
    out = N.build(tmp_path)
    assert len(out["needs"]) == 1
    g = out["needs"][0]
    assert g["key"] == "oracle-group:class:region.scheme" and g["fileable"] is False  # a group is never filed
    assert g["members"] == [f"oracle:Q{i}#needs_sme" for i in (1, 2, 3, 4)]
    assert g["text"] == WEST and g["variants"] == 1  # the most frequent wording, and how many others
    assert g["origin"] == "oracle" and g["kind"] == "question"
    assert _codes(out) == ["oracle-sme-class-texts"]
    assert out["counts"] == {"oracle_files": 5, "with_sme_fields": 5, "candidates": 4, "rows": 1, "groups": 1, "findings": 1}


def test_without_a_class_identical_texts_group_and_a_single_oracle_is_a_plain_row(tmp_path):
    _oracle(tmp_path, "Q1", needs_sme=True, needs_sme_question=WEST)
    _oracle(tmp_path, "Q2", needs_sme=True, needs_sme_question="  which regional scheme does   WEST name?")
    _oracle(tmp_path, "Q3", needs_sme=True, needs_sme_question="Is a pop-up store a store?")
    out = N.build(tmp_path)
    keys = {r["key"]: r for r in out["needs"]}
    group = next(r for k, r in keys.items() if k.startswith("oracle-group:text:"))
    assert group["members"] == ["oracle:Q1#needs_sme", "oracle:Q2#needs_sme"] and group["variants"] == 0
    single = keys["oracle:Q3#needs_sme"]
    assert single["members"] is None and single["fileable"] is True and single["questions"] == ["Q3"]
    assert _codes(out) == []


def test_text_without_the_flag_is_a_candidate_and_a_finding(tmp_path):
    _oracle(tmp_path, "Q1", needs_sme_question=WEST)
    out = N.build(tmp_path)
    assert [r["key"] for r in out["needs"]] == ["oracle:Q1#needs_sme"]
    assert _codes(out) == ["oracle-sme-flag-missing"]


def test_a_flag_without_text_or_a_false_flag_with_text_is_a_finding_only(tmp_path):
    _oracle(tmp_path, "Q1", needs_sme=True)
    _oracle(tmp_path, "Q2", needs_sme=False, needs_sme_question=WEST)
    _oracle(tmp_path, "Q3", needs_sme="yes", needs_sme_question=WEST)
    out = N.build(tmp_path)
    # Q3's malformed flag reads as unflagged, so its text makes it a candidate with a missing flag
    assert [r["key"] for r in out["needs"]] == ["oracle:Q3#needs_sme"]
    assert _codes(out) == [
        "oracle-sme-flag-false-with-text",
        "oracle-sme-flag-malformed",
        "oracle-sme-flag-missing",
        "oracle-sme-flag-no-text",
    ]


def test_an_unreadable_oracle_is_a_high_finding_not_a_shorter_list(tmp_path):
    _oracle(tmp_path, "Q1", needs_sme=True, needs_sme_question=WEST)
    (tmp_path / "acceptance" / "oracle" / "Q2.yaml").write_text("question: [unclosed\n")
    out = N.build(tmp_path)
    assert len(out["needs"]) == 1
    bad = [f for f in out["findings"] if f["code"] == "sme-source-unreadable"]
    assert len(bad) == 1 and bad[0]["severity"] == "high" and bad[0]["concept_title"].endswith("Q2.yaml")


def test_an_id_that_breaks_the_key_grammar_is_shown_and_flagged(tmp_path):
    _oracle(tmp_path, "Q 1", needs_sme=True, needs_sme_question=WEST)
    out = N.build(tmp_path)
    assert out["needs"][0]["key"] == "oracle:Q%201#needs_sme"  # a space is encoded, so it still files
    _oracle(tmp_path, "Q<2>", needs_sme=True, needs_sme_question="Is a pop-up store a store?")
    out = N.build(tmp_path)
    assert "sme-key-unfileable" in _codes(out)


def test_two_oracles_with_one_question_id_are_a_duplicate_key_finding(tmp_path):
    _oracle(tmp_path, "Q1", needs_sme=True, needs_sme_question=WEST)
    d = tmp_path / "acceptance" / "oracle"
    (d / "Q1_copy.yaml").write_text(yaml.safe_dump({"question": {"id": "Q1"}, "needs_sme": True, "needs_sme_question": "Is a pop-up store a store?"}))
    _oracle(tmp_path, "Q2", needs_sme=True, needs_sme_question="Is a kiosk a store?")  # negative control
    out = N.build(tmp_path)
    dup = [f for f in out["findings"] if f["code"] == "sme-key-duplicate"]
    assert len(dup) == 1 and dup[0]["concept_title"] == "oracle:Q1#needs_sme"


def test_write_is_deterministic(tmp_path):
    _oracle(tmp_path, "Q1", needs_sme=True, needs_sme_question=WEST)
    p = N.write(tmp_path)
    first = p.read_bytes()
    N.write(tmp_path)
    assert p.read_bytes() == first
    assert json.loads(first)["format"] == N.FORMAT
