"""The read-time join: catalogue ∪ ledger, with the derived fields a page renders verbatim. Offline;
every bundle is a temporary directory in a neutral retail domain.

WHY THESE CASES. Overdue is the one number a person acts on without reading further, so its
boundary, its threshold source and its behaviour on bounded dates are pinned exactly. The one-list
rule (unfiled candidates are rows, filing one keeps the row count) is what makes the list
consolidated rather than two lists side by side. And an absent or broken ledger must read as absent
or broken, never as a clean one.
"""

from __future__ import annotations

import json

import pytest
import yaml

from sdk.project import ontology_quality as Q
from sdk.project import sme_questions as S

AS_OF = "2026-03-20T12:00:00Z"
STAMP = {"rev": 1, "at": "2026-03-01T09:00:00Z", "by": "dev-1", "role": "developer", "identity_basis": "verified", "submitted_via": "human"}
PARTICIPANTS = [
    {"id": "dev-1", "side": "developer", "role_title": "ontology developer"},
    {"id": "sme-1", "side": "sme", "role_title": "business SME, store planning"},
]


def _catalogue(root, register_rows=(), needs_rows=()):
    (root / "ontology").mkdir(parents=True, exist_ok=True)
    (root / "acceptance").mkdir(parents=True, exist_ok=True)
    reg = {"sme_catalogue_format": Q.SME_CATALOGUE_FORMAT, "sme_questions": list(register_rows), "findings": [], "sme_operator_items": []}
    (root / "ontology" / "ontology_quality.json").write_text(json.dumps(reg))
    (root / "acceptance" / "sme_needs.json").write_text(json.dumps({"format": "mac.sme-needs/1", "needs": list(needs_rows), "findings": []}))


def _row(key, origin="concept-field", text="Is a store open on its handover date?", **kw):
    return Q.sme_row(key=key, origin=origin, kind="question", text=text, **kw)


def _event(frm, to, at, **kw):
    return dict({"from": frm, "to": to, "at": at, "recorded": STAMP}, **kw)


def _ask(mid="msg_ask000000001", at=None, delivery="evidenced", **kw):
    m = {"id": mid, "kind": "ask", "author": "dev-1", "role": "developer", "to": [{"participant": "sme-1"}], "channel": "mail",
         "channel_basis": "recorded", "delivery": delivery, "at": at or {"at": "2026-03-01", "basis": "recorded"},
         "body": "Is a store open on its handover date?", "recorded": STAMP}
    m.update(kw)
    return m


def _entry(eid="q.store.opening", status="out_for_discussion", entered=None, thread=None, origins=None, **kw):
    entered = entered or {"at": "2026-03-01", "basis": "recorded"}
    hist = [_event(None, "draft", {"at": "2026-02-20", "basis": "recorded"})]
    if status != "draft":
        hist.append(_event("draft", status, entered))
    e = {
        "id": eid, "kind": "question", "plane": "ontology", "title": "When does a store count as open?",
        "question": "Is a store open on its handover date?", "priority": "medium", "status": status,
        "status_history": hist, "thread": thread if thread is not None else ([_ask()] if status != "draft" else []),
        "origins": origins if origins is not None else [{"key": "concept:store#open_questions[oq1]", "tag": "concept-field", "recorded": STAMP}],
        "rev": 2, "created": STAMP, "owner": {"participant": "sme-1"}, "shepherd": "dev-1",
    }
    e.update(kw)
    return e


def _ledger(root, entries, policy=None, **extra):
    (root / "governance").mkdir(parents=True, exist_ok=True)
    doc = {"format": "mac.sme-questions/1", "participants": PARTICIPANTS, "entries": entries}
    if policy is not None:
        doc["policy"] = policy
    doc.update(extra)
    (root / "governance" / "sme-questions.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))


def _rows(ov):
    return {r["id"]: r for r in ov["rows"]}


# --- backward compatible: no ledger -------------------------------------------------------------


def test_without_a_ledger_every_candidate_is_an_unfiled_draft_and_the_absence_is_stated(tmp_path):
    _catalogue(tmp_path, [_row("concept:store#open_questions[oq1]")], [_row("oracle:Q1#needs_sme", origin="oracle")])
    ov = S.overview(tmp_path, as_of=AS_OF)
    assert ov["ledger"]["state"] == "absent"
    assert ov["counts"]["rows"] == 2 and ov["counts"]["not_filed"] == 2 and ov["counts"]["by_status"]["draft"] == 2
    for r in ov["rows"]:
        assert r["filed"] is False and r["status"] == "draft"
        assert r["next_action_effective"] == {"action": "file", "owner": {"side": "developer", "role_title": "any developer", "label": "any developer"}, "derived": True}
    assert ov["counts"]["by_origin"] == {"concept-field": 1, "oracle": 1}


def test_a_register_from_before_the_catalogue_format_contributes_no_candidates(tmp_path):
    (tmp_path / "ontology").mkdir()
    legacy = {"sme_questions": [{"id": "ledger.INT-1", "kind": "ratification", "question": "only wording)."}]}
    (tmp_path / "ontology" / "ontology_quality.json").write_text(json.dumps(legacy))
    ov = S.overview(tmp_path, as_of=AS_OF)
    assert ov["catalogue"]["register"] == "legacy" and ov["rows"] == []


# --- overdue ------------------------------------------------------------------------------------


@pytest.mark.parametrize("days,expect", [(14, False), (15, True)])
def test_overdue_boundary_with_the_default_threshold(tmp_path, days, expect):
    entered = {"at": "2026-03-06" if days == 14 else "2026-03-05", "basis": "recorded"}
    _ledger(tmp_path, [_entry(entered=entered, thread=[_ask(at=entered)])])
    r = _rows(S.overview(tmp_path, as_of="2026-03-20"))["q.store.opening"]
    assert r["days_in_status"] == days and r["overdue"] is expect and r["overdue_possible"] is False
    assert r["days_overdue"] == (1 if expect else None)


def test_the_threshold_comes_from_the_ledger_policy(tmp_path):
    _ledger(tmp_path, [_entry(entered={"at": "2026-03-10", "basis": "recorded"})], policy={"overdue_after_days": 7})
    ov = S.overview(tmp_path, as_of="2026-03-20")
    assert ov["policy"] == {"overdue_after_days": 7, "source": "ledger"}
    assert _rows(ov)["q.store.opening"]["overdue"] is True and _rows(ov)["q.store.opening"]["days_overdue"] == 3


def test_an_invalid_policy_falls_back_to_the_default_and_says_so(tmp_path):
    _ledger(tmp_path, [_entry()], policy={"overdue_after_days": 0})
    p = S.overview(tmp_path, as_of=AS_OF)["policy"]
    assert p["overdue_after_days"] == 14 and p["source"] == "default" and "note" in p


def test_on_or_before_is_a_lower_bound_and_overdue_when_it_exceeds(tmp_path):
    _ledger(tmp_path, [_entry(entered={"at": "2026-03-01", "basis": "inferred", "bound": "on_or_before", "note": "quoted by a later note"})])
    r = _rows(S.overview(tmp_path, as_of="2026-03-20"))["q.store.opening"]
    assert (r["days_in_status"], r["age_bound"], r["overdue"]) == (19, "at_least", True)


def test_a_range_is_overdue_only_when_its_smallest_age_exceeds(tmp_path):
    maybe = {"at": "2026-03-01", "basis": "inferred", "bound": "between", "until": "2026-03-10", "note": "sent between two files"}
    surely = {"at": "2026-02-01", "basis": "inferred", "bound": "between", "until": "2026-03-01", "note": "sent between two files"}
    _ledger(tmp_path, [_entry("q.maybe", entered=maybe), _entry("q.surely", entered=surely)])
    rows = _rows(S.overview(tmp_path, as_of="2026-03-20"))
    assert (rows["q.maybe"]["overdue"], rows["q.maybe"]["overdue_possible"]) == (False, True)
    assert (rows["q.maybe"]["days_in_status"], rows["q.maybe"]["days_in_status_max"]) == (10, 19)
    assert (rows["q.surely"]["overdue"], rows["q.surely"]["days_overdue"]) == (True, 5)


def test_on_or_after_can_only_be_possibly_overdue(tmp_path):
    _ledger(tmp_path, [_entry(entered={"at": "2026-01-01", "basis": "inferred", "bound": "on_or_after", "note": "not before the file date"})])
    r = _rows(S.overview(tmp_path, as_of="2026-03-20"))["q.store.opening"]
    assert (r["overdue"], r["overdue_possible"], r["days_in_status"], r["age_bound"]) == (False, True, None, "at_most")


def test_a_follow_up_does_not_reset_the_clock_and_a_reopen_does(tmp_path):
    follow = {"id": "msg_fu0000000001", "kind": "follow_up", "author": "dev-1", "role": "developer", "channel": "mail",
              "channel_basis": "recorded", "at": {"at": "2026-03-18", "basis": "recorded"}, "body": "Any news?", "recorded": STAMP}
    chased = _entry("q.chased", entered={"at": "2026-03-01", "basis": "recorded"}, thread=[_ask(), follow])
    reopened = _entry("q.reopened", entered={"at": "2026-03-01", "basis": "recorded"})
    reopened["status_history"] += [
        _event("out_for_discussion", "answered", {"at": "2026-03-05", "basis": "recorded"}),
        _event("answered", "out_for_discussion", {"at": "2026-03-15", "basis": "recorded"}, reason="the answer does not cover outlets"),
    ]
    _ledger(tmp_path, [chased, reopened])
    rows = _rows(S.overview(tmp_path, as_of="2026-03-20"))
    assert rows["q.chased"]["overdue"] is True and len(rows["q.chased"]["follow_ups"]) == 1
    assert rows["q.chased"]["follow_ups"][0]["note"] == "Any news?"
    assert rows["q.reopened"]["days_in_status"] == 5 and rows["q.reopened"]["overdue"] is False


@pytest.mark.parametrize("status", ["draft", "answered", "blocked", "applied", "withdrawn"])
def test_only_out_for_discussion_can_be_overdue(tmp_path, status):
    kw = {}
    if status == "blocked":
        kw["next_action"] = {"action": "measure the join", "owner": {"participant": "dev-1"}, "recorded": STAMP}
    _ledger(tmp_path, [_entry(status=status, entered={"at": "2025-01-01", "basis": "recorded"}, **kw)])
    r = _rows(S.overview(tmp_path, as_of=AS_OF))["q.store.opening"]
    assert r["overdue"] is False and r["overdue_possible"] is False


# --- the record: asked, awaiting, next action, seen ---------------------------------------------


def test_the_record_derives_asked_awaiting_and_the_next_action(tmp_path):
    clar = {"id": "msg_cl0000000001", "kind": "clarification_request", "author": "sme-1", "role": "sme", "channel": "console",
            "at": {"at": "2026-03-03T10:02:11Z", "basis": "live"}, "body": "Sales region or logistics region?", "recorded": STAMP}
    inferred_ask = _ask(delivery="inferred", channel="chat", channel_basis="inferred", at={"at": "2026-03-01", "basis": "file-mtime"})
    prepared = _ask("msg_ask000000000", delivery="not_evidenced", channel="document")
    e = _entry(thread=[prepared, inferred_ask, clar], receipts=[{"participant": "sme-1", "side": "sme", "first_seen_at": "2026-03-02T08:00:00Z", "rev": 1}])
    _ledger(tmp_path, [e])
    r = _rows(S.overview(tmp_path, as_of=AS_OF))["q.store.opening"]
    # the prepared, never-evidenced document is not "asked"; the inferred upload is, and says so
    assert r["asked"]["message"] == "msg_ask000000001"
    assert (r["asked"]["channel_basis"], r["asked"]["delivery"]) == ("inferred", "inferred")
    assert r["asked"]["by"]["label"] == "ontology developer"
    assert r["asked"]["to"] == [{"participant": "sme-1", "side": "sme", "role_title": "business SME, store planning", "label": "business SME, store planning"}]
    assert r["asks_not_evidenced"] == 1
    assert r["awaiting"] == "developer"  # the SME asked back: the team owes the reply
    assert r["next_action_effective"]["action"] == "reply" and r["next_action_effective"]["derived"] is True
    assert r["next_action_effective"]["owner"]["participant"] == "dev-1"
    assert r["seen_by_sme"] is True
    assert r["last_activity"]["kind"] == "clarification_request"
    assert len(r["thread"]) == 3


def test_every_open_row_names_a_next_action_with_an_owner(tmp_path):
    blocked = _entry("q.blocked", status="blocked", next_action={"action": "lift the model lock", "owner": {"side": "developer", "role_title": "operator"}, "recorded": STAMP})
    answered = _entry("q.answered", status="answered", answer={"summary": "Handover date.", "from": "sme-1", "at": {"at": "2026-03-02", "basis": "recorded"}, "completeness": "full", "evidence": "reference_only", "recorded": STAMP})
    draft = _entry("q.draft", status="draft", origins=[{"key": "manual:q.draft", "tag": "manual", "recorded": STAMP}])
    ofd = _entry("q.ofd", origins=[{"key": "manual:q.ofd", "tag": "manual", "recorded": STAMP}])
    _catalogue(tmp_path, [_row("concept:store#identity", origin="register")])
    _ledger(tmp_path, [blocked, answered, draft, ofd])
    ov = S.overview(tmp_path, as_of=AS_OF)
    for r in ov["rows"]:
        if r["status"] in S.OPEN_STATUSES:
            na = r["next_action_effective"]
            assert na and na["action"] and na["owner"] and na["owner"].get("label"), r["id"]
    rows = _rows(ov)
    assert rows["q.blocked"]["next_action_effective"]["derived"] is False
    assert rows["q.ofd"]["next_action_effective"]["action"] == "answer"
    assert rows["q.ofd"]["next_action_effective"]["owner"]["participant"] == "sme-1"


# --- one list -----------------------------------------------------------------------------------


def test_filing_a_candidate_replaces_its_unfiled_row_and_keeps_the_count(tmp_path):
    rows = [_row("concept:store#open_questions[oq1]"), _row("concept:store#identity", origin="register")]
    _catalogue(tmp_path, rows)
    before = S.overview(tmp_path, as_of=AS_OF)
    _ledger(tmp_path, [_entry(status="draft")])  # files concept:store#open_questions[oq1]
    after = S.overview(tmp_path, as_of=AS_OF)
    assert before["counts"]["rows"] == after["counts"]["rows"] == 2
    assert (after["counts"]["filed"], after["counts"]["not_filed"]) == (1, 1)
    assert "concept:store#open_questions[oq1]" not in _rows(after)
    assert _rows(after)["q.store.opening"]["origins"][0]["present"] is True


def test_a_partly_filed_group_lists_only_its_unfiled_members(tmp_path):
    group = _row("oracle-group:class:region", origin="oracle", members=["oracle:Q1#needs_sme", "oracle:Q2#needs_sme", "oracle:Q3#needs_sme"])
    _catalogue(tmp_path, needs_rows=[group])
    _ledger(tmp_path, [_entry(origins=[{"key": "oracle:Q1#needs_sme", "tag": "oracle", "recorded": STAMP}])])
    r = _rows(S.overview(tmp_path, as_of=AS_OF))["oracle-group:class:region"]
    assert r["members"] == ["oracle:Q2#needs_sme", "oracle:Q3#needs_sme"] and r["members_filed"] == 1


def test_data_plane_entries_are_counted_but_not_listed(tmp_path):
    _ledger(tmp_path, [_entry(), _entry("q.data.column", plane="data")])
    ov = S.overview(tmp_path, as_of=AS_OF)
    assert list(_rows(ov)) == ["q.store.opening"] and ov["counts"]["excluded_other_plane"] == 1


# --- broken states are loud ---------------------------------------------------------------------


def test_an_invalid_ledger_lists_candidates_with_filing_state_unknown(tmp_path):
    _catalogue(tmp_path, [_row("concept:store#open_questions[oq1]")])
    bad = _entry()
    bad["status"] = "answered"  # no longer the last event's `to`
    _ledger(tmp_path, [bad])
    ov = S.overview(tmp_path, as_of=AS_OF)
    assert ov["ledger"]["state"] == "invalid" and ov["ledger"]["errors"]
    (r,) = ov["rows"]
    assert r["filed"] is None and r["filing_state"] == "unknown"


def test_an_unparseable_ledger_is_invalid_not_absent(tmp_path):
    (tmp_path / "governance").mkdir()
    (tmp_path / "governance" / "sme-questions.yaml").write_text("entries: [unclosed\n")
    assert S.overview(tmp_path, as_of=AS_OF)["ledger"]["state"] == "invalid"


def test_unquoted_dates_are_read_as_the_strings_they_are(tmp_path):
    _ledger(tmp_path, [_entry()])
    p = tmp_path / "governance" / "sme-questions.yaml"
    p.write_text(p.read_text().replace("'2026-03-01'", "2026-03-01"))
    assert "at: 2026-03-01\n" in p.read_text()
    ov = S.overview(tmp_path, as_of="2026-03-20")
    assert _rows(ov)["q.store.opening"]["days_in_status"] == 19
    json.dumps(ov)  # serialisable: nothing was turned into a date object


def test_an_explicit_schema_is_applied(tmp_path):
    _ledger(tmp_path, [_entry()])
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps({"type": "object", "required": ["policy"]}))
    ov = S.overview(tmp_path, as_of=AS_OF, schema=schema)
    assert ov["ledger"]["state"] == "invalid" and ov["ledger"]["validated"] == "schema"


# --- coherence ----------------------------------------------------------------------------------


def test_coherence_findings(tmp_path):
    _catalogue(tmp_path, [_row("concept:store#open_questions[oq1]"), _row("concept:store#identity", origin="register")])
    answer = {"id": "msg_an0000000001", "kind": "answer", "author": "sme-1", "role": "sme", "channel": "console",
              "at": {"at": "2026-03-05T10:00:00Z", "basis": "live"}, "body": "Handover date.",
              "recorded": dict(STAMP, by="sme-1", role="sme", identity_basis="local-declared")}
    applied = _entry("q.applied", status="applied", outcome={"kind": "no_change_needed", "summary": "s", "refs": [{"path": "x"}], "at": {"at": "2026-03-05", "basis": "recorded"}, "recorded": STAMP})
    gone = _entry("q.gone", origins=[{"key": "concept:store#values[OLD].open_question", "tag": "concept-field", "recorded": STAMP}], thread=[_ask(), answer])
    twice = _entry("q.twice", status="draft", origins=[{"key": "concept:store#identity", "tag": "register", "recorded": STAMP}])
    twice2 = _entry("q.twice.again", status="draft", origins=[{"key": "concept:store#identity", "tag": "register", "recorded": STAMP}])
    _ledger(tmp_path, [applied, gone, twice, twice2])
    codes = sorted((f["code"], f["entry"]) for f in S.overview(tmp_path, as_of=AS_OF)["coherence"])
    assert codes == [
        ("answer-not-marked", "q.gone"),
        ("closed-but-still-asked", "q.applied"),
        ("open-but-origin-gone", "q.gone"),
        ("origin-filed-twice", "q.twice, q.twice.again"),
        ("sme-act-local-declared", "q.gone"),
    ]


def test_origin_presence_is_unknown_when_the_catalogue_was_not_read(tmp_path):
    _ledger(tmp_path, [_entry()])
    ov = S.overview(tmp_path, as_of=AS_OF)
    assert ov["catalogue"] == {"register": "absent", "oracle_needs": "absent"}
    assert _rows(ov)["q.store.opening"]["origins"][0]["present"] is None
    assert not [f for f in ov["coherence"] if f["code"] == "open-but-origin-gone"]


# --- order and the command line -----------------------------------------------------------------


def test_chase_order_puts_overdue_first_then_replies_owed_then_unfiled_before_closed(tmp_path):
    clar = {"id": "msg_cl0000000001", "kind": "clarification_request", "author": "sme-1", "role": "sme", "channel": "console",
            "at": {"at": "2026-03-19T10:00:00Z", "basis": "live"}, "body": "Which region?", "recorded": STAMP}
    _catalogue(tmp_path, [_row("concept:store#identity", origin="register")])
    _ledger(
        tmp_path,
        [
            _entry("q.withdrawn", status="withdrawn", origins=[]),
            _entry("q.fresh", entered={"at": "2026-03-19", "basis": "recorded"}, origins=[]),
            _entry("q.reply.owed", entered={"at": "2026-03-18", "basis": "recorded"}, thread=[_ask(at={"at": "2026-03-18", "basis": "recorded"}), clar], origins=[]),
            _entry("q.late", entered={"at": "2026-01-01", "basis": "recorded"}, origins=[]),
            _entry("q.draft", status="draft", origins=[]),
        ],
    )
    ids = [r["id"] for r in S.overview(tmp_path, as_of=AS_OF)["rows"]]
    assert ids == ["q.late", "q.reply.owed", "q.fresh", "q.draft", "concept:store#identity", "q.withdrawn"]


def test_cli_prints_json_and_refuses_to_write_into_the_model(tmp_path, capsys):
    _ledger(tmp_path, [_entry()])
    assert S.main(["--bundle", str(tmp_path), "--as-of", AS_OF]) == 0
    assert json.loads(capsys.readouterr().out)["format"] == S.FORMAT
    (tmp_path / "ontology").mkdir()
    assert S.main(["--bundle", str(tmp_path), "--out", str(tmp_path / "ontology" / "sme.json")]) == 2
    assert not (tmp_path / "ontology" / "sme.json").exists()
    assert S.main(["--bundle", str(tmp_path), "--as-of", "yesterday"]) == 2
