"""sdk.project.sme_questions — ONE list of the questions a bundle puts to subject-matter experts:
the projected catalogue joined with the bundle's SME question ledger, AT READ TIME.

    catalogue = ontology/ontology_quality.json  sme_questions      (register + concept fields)
              ∪ acceptance/sme_needs.json       needs              (test oracles flagged needs-SME)
    ledger    = governance/sme-questions.yaml   (format mac.sme-questions/1, when present)
    rows      = ledger entries (plane ontology), filed, with derived fields
              ∪ catalogue candidates no entry files (a group: its unfiled members), status draft

WHY A READ-TIME VIEW AND NOT A PROJECTED FILE. Three reasons, each sufficient:
  1. The projection ships in the served artifact and is hashed with it; the ledger is dialogue and
     changes whenever anyone posts. Writing one into the other would make every message a model
     change — the platform's boundaries exclude dialogue records from projectors for this reason.
  2. OVERDUE DEPENDS ON "NOW". A stored overdue flag is stale from the moment it is written.
  3. A message posted in the console must show on the next read, not after the next projection.
So this module reads, derives and prints; it writes nothing into the bundle. The console calls it
the way it already calls the questions projector: `python -m sdk.project.sme_questions --bundle`.

WHAT IS DERIVED HERE, AND WHAT IS NOT. Everything that needs only the ledger, the catalogue and the
clock: filed, entered_at, days_in_status (with its bound), overdue / overdue_possible /
days_overdue, awaiting, asked, follow_ups, next_action_effective, seen_by_sme, origins[].present,
chase order, counts and the coherence findings. NOT derived here: `allowed_actions` and anything
else that depends on WHO is asking — identity is the platform's, never the framework's.

BACKWARD COMPATIBLE. With no ledger every catalogue row is listed `filed: false` and the ledger's
state says `absent`: an absent ledger is never mistakable for a clean one. A register projected
before the catalogue format existed is reported `legacy` and contributes no candidates — its rows
are the free-text fragments the format replaced, and listing them would reinstate them.

CLI:
  python3 -m sdk.project.sme_questions --bundle <bundle> [--as-of 2026-03-20T14:02:00Z]
          [--catalogue-root <served root>] [--schema <sme-questions.schema.json>]
          [--no-thread] [--out <file outside the model>]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

import yaml

from sdk.project import ontology_quality as _oq

FORMAT = "mac.sme-overview/1"
LEDGER = "governance/sme-questions.yaml"
LEDGER_FORMAT = "mac.sme-questions/1"
DEFAULT_OVERDUE_DAYS = 14
STATUSES = ("draft", "out_for_discussion", "answered", "applied", "withdrawn", "blocked")
OPEN_STATUSES = ("draft", "out_for_discussion", "answered", "blocked")
ARTIFACT_TAGS = {"register", "oracle", "concept-field"}
SME_ACTS = {"answer", "clarification_request", "unable_to_answer"}
ANY_DEVELOPER = {"side": "developer", "role_title": "any developer"}
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


# ── reading ─────────────────────────────────────────────────────────────────────────────────────
class _StringDatesLoader(yaml.SafeLoader):
    """SafeLoader without the timestamp resolver. WHY: an unquoted `2026-01-05` would load as a
    date object, fail the ledger schema's string type, and not serialise to JSON — while the same
    file with quotes passes. A reader must not change a value's type behind the schema's back."""


_StringDatesLoader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _structural_errors(doc) -> list[str]:
    """The checks this view needs in order to join safely. The full schema lives with the ledger
    store (the platform); pass `schema=` to validate against it as well."""
    if not isinstance(doc, dict):
        return ["the ledger is not a mapping"]
    errs = []
    if doc.get("format") != LEDGER_FORMAT:
        errs.append(f"format is {doc.get('format')!r}, expected {LEDGER_FORMAT!r}")
    for field in ("participants", "entries"):
        if not isinstance(doc.get(field), list):
            errs.append(f"{field} is not a list")
    for i, e in enumerate(doc.get("entries") or [] if isinstance(doc.get("entries"), list) else []):
        where = f"entries[{i}]"
        if not isinstance(e, dict):
            errs.append(f"{where} is not a mapping")
            continue
        where = f"entries[{i}] ({e.get('id')})"
        if not isinstance(e.get("id"), str):
            errs.append(f"{where}: no id")
        if e.get("kind") not in _oq.SME_KINDS:
            errs.append(f"{where}: kind {e.get('kind')!r}")
        if e.get("status") not in STATUSES:
            errs.append(f"{where}: status {e.get('status')!r}")
        hist = e.get("status_history")
        if not isinstance(hist, list) or not hist:
            errs.append(f"{where}: status_history is empty")
        elif not isinstance(hist[-1], dict) or hist[-1].get("to") != e.get("status"):
            errs.append(f"{where}: status is not the last status event's `to`")
        for field in ("origins", "thread"):
            if not isinstance(e.get(field), list):
                errs.append(f"{where}: {field} is not a list")
    return errs


def load_ledger(root, schema=None) -> dict:
    """{state: absent | invalid | present, doc, errors, validated, fingerprint}."""
    path = Path(root) / LEDGER
    if not path.exists():
        return {"state": "absent", "doc": None, "errors": [], "validated": None, "fingerprint": None}
    raw = path.read_bytes()
    fp = hashlib.sha256(raw).hexdigest()
    try:
        doc = yaml.load(raw.decode("utf-8"), Loader=_StringDatesLoader)  # noqa: S506 — a SafeLoader
    except Exception as e:  # noqa: BLE001 — an unreadable ledger is a state, reported
        return {"state": "invalid", "doc": None, "errors": [f"{type(e).__name__}: {e}"], "validated": "parse", "fingerprint": fp}
    errors = _structural_errors(doc)
    validated = "structural"
    if schema is not None:
        try:
            import jsonschema

            spec = json.loads(Path(schema).read_text(encoding="utf-8"))
            v = jsonschema.Draft202012Validator(spec)
            for err in sorted(v.iter_errors(doc), key=lambda x: list(x.absolute_path)):
                errors.append("/".join(str(p) for p in err.absolute_path) + ": " + err.message)
            validated = "schema"
        except Exception as e:  # noqa: BLE001
            errors.append(f"schema validation could not run: {type(e).__name__}: {e}")
    return {
        "state": "invalid" if errors else "present",
        "doc": None if errors else doc,
        "errors": errors[:20],
        "validated": validated,
        "fingerprint": fp,
    }


def load_catalogue(root) -> dict:
    """The projected catalogue, read from the served root. Each half reports its own state, because
    `origins[].present` can only be answered for a half that was actually read."""
    root = Path(root)
    out = {"register": "absent", "oracle_needs": "absent", "rows": [], "findings": [], "operator_items": [], "keys": {}}
    reg = root / "ontology" / "ontology_quality.json"
    if reg.exists():
        try:
            doc = json.loads(reg.read_text(encoding="utf-8"))
            if doc.get("sme_catalogue_format") != _oq.SME_CATALOGUE_FORMAT:
                out["register"] = "legacy"
            else:
                out["register"] = "present"
                out["rows"] += list(doc.get("sme_questions") or [])
                out["findings"] += [f for f in doc.get("findings") or [] if f.get("category") == _oq.SME_FINDING_CATEGORY]
                out["operator_items"] = list(doc.get("sme_operator_items") or [])
        except Exception as e:  # noqa: BLE001
            out["register"] = f"unreadable: {type(e).__name__}"
    needs = root / "acceptance" / "sme_needs.json"
    if needs.exists():
        try:
            doc = json.loads(needs.read_text(encoding="utf-8"))
            out["oracle_needs"] = "present"
            out["rows"] += list(doc.get("needs") or [])
            out["findings"] += list(doc.get("findings") or [])
        except Exception as e:  # noqa: BLE001
            out["oracle_needs"] = f"unreadable: {type(e).__name__}"
    # keys by the tag of the half that produced them: a missing half answers "unknown", not "absent"
    for r in out["rows"]:
        for k in r.get("members") or [r.get("key")]:
            out["keys"][k] = r.get("origin")
    return out


# ── dates and ages ──────────────────────────────────────────────────────────────────────────────
def parse_at(value) -> _dt.datetime | None:
    """A date or datetime as an aware UTC datetime. A date-only value counts from 00:00 UTC."""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=_dt.timezone.utc)
    if isinstance(value, _dt.date):
        return _dt.datetime(value.year, value.month, value.day, tzinfo=_dt.timezone.utc)
    s = str(value).strip()
    try:
        if len(s) == 10:
            d = _dt.date.fromisoformat(s)
            return _dt.datetime(d.year, d.month, d.day, tzinfo=_dt.timezone.utc)
        t = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def _days(earlier: _dt.datetime, as_of: _dt.datetime) -> int:
    return int((as_of - earlier).total_seconds() // 86400)


def age(stamp, as_of: _dt.datetime) -> dict:
    """How long ago a date stamp's event happened, honest about its bound.

    exact         min = max
    on_or_before  the event may be older: `min` is a lower bound, no max
    on_or_after   the event may be newer: `max` is an upper bound, no min
    between       the age lies from (as_of - until) to (as_of - at)
    """
    stamp = stamp or {}
    at = parse_at(stamp.get("at"))
    if at is None:
        return {"min": None, "max": None, "bound": "unknown"}
    d = _days(at, as_of)
    bound = stamp.get("bound") or "exact"
    if bound == "on_or_before":
        return {"min": d, "max": None, "bound": "at_least"}
    if bound == "on_or_after":
        return {"min": None, "max": d, "bound": "at_most"}
    if bound == "between":
        until = parse_at(stamp.get("until"))
        return {"min": _days(until, as_of) if until else None, "max": d, "bound": "range"}
    return {"min": d, "max": d, "bound": "exact"}


def overdue(status: str, a: dict, threshold: int) -> tuple[bool, bool, int | None]:
    """(overdue, overdue_possible, days_overdue). Only out_for_discussion can be overdue, and
    overdue is ASSERTED only when the smallest possible age exceeds the threshold. A bounded date
    whose larger age exceeds it is `possible`, never `overdue` — a false OVERDUE sends someone to
    chase an SME who may have been asked yesterday."""
    if status != "out_for_discussion" or not a:
        return False, False, None
    if a.get("min") is not None and a["min"] > threshold:
        return True, False, a["min"] - threshold
    if a.get("max") is not None and a["max"] > threshold:
        return False, True, None
    return False, False, None


# ── derivation per entry ────────────────────────────────────────────────────────────────────────
def _party(ref, parts: dict) -> dict | None:
    """An owner / addressee reference with the label a page shows: display name when the bundle
    records one, else the role title. Never a guessed person."""
    if not isinstance(ref, dict):
        return None
    pid = ref.get("participant")
    if pid:
        p = parts.get(pid)
        if not p:
            return {"participant": pid, "label": f"unknown participant {pid}"}
        out = {"participant": pid, "side": p.get("side"), "role_title": p.get("role_title")}
        if p.get("display_name"):
            out["display_name"] = p["display_name"]
        out["label"] = p.get("display_name") or p.get("role_title")
        return out
    return {"side": ref.get("side"), "role_title": ref.get("role_title"), "label": ref.get("role_title")}


def _delivery(m: dict) -> str:
    return m.get("delivery") or "evidenced"


def _msg_at(m: dict):
    return parse_at((m.get("at") or {}).get("at"))


def derive_entry(e: dict, as_of: _dt.datetime, threshold: int, parts: dict, catalogue: dict | None, include_thread=True) -> dict:
    status = e.get("status")
    hist = [h for h in e.get("status_history") or [] if isinstance(h, dict)]
    thread = [m for m in e.get("thread") or [] if isinstance(m, dict)]
    entered = next((h.get("at") for h in reversed(hist) if h.get("to") == status), None)
    a = age(entered, as_of) if entered else {"min": None, "max": None, "bound": "unknown"}
    is_over, possible, days_over = overdue(status, a, threshold)
    entered_dt = parse_at((entered or {}).get("at"))

    asks = [m for m in thread if m.get("kind") == "ask" and _delivery(m) in ("evidenced", "inferred")]
    first_ask = asks[0] if asks else None
    asked = None
    if first_ask:
        asked = {
            "message": first_ask.get("id"),
            "by": _party({"participant": first_ask.get("author")}, parts),
            "to": [_party(t, parts) for t in first_ask.get("to") or []],
            "channel": first_ask.get("channel"),
            "channel_basis": first_ask.get("channel_basis") or "recorded",
            "delivery": _delivery(first_ask),
            "at": first_ask.get("at"),
        }
    follow_ups = []
    for m in thread:
        is_reask = m.get("kind") == "ask" and m is not first_ask
        if m.get("kind") == "follow_up" or is_reask or (m.get("kind") == "reply" and m.get("role") == "developer"):
            follow_ups.append(
                {
                    "message": m.get("id"),
                    "kind": m.get("kind"),
                    "at": m.get("at"),
                    "by": _party({"participant": m.get("author")}, parts),
                    "delivery": _delivery(m),
                    "note": m.get("body"),
                }
            )

    awaiting = None
    if status in ("draft", "answered"):
        awaiting = "developer"
    elif status == "out_for_discussion":
        since = [
            (i, m)
            for i, m in enumerate(thread)
            if m.get("kind") != "note"
            and _delivery(m) != "not_evidenced"
            and (entered_dt is None or (_msg_at(m) or entered_dt) >= entered_dt)
        ]
        last = max(since, key=lambda im: (_msg_at(im[1]) or _dt.datetime.min.replace(tzinfo=_dt.timezone.utc), im[0]))[1] if since else None
        if last is None or last.get("kind") in ("ask", "follow_up") or (last.get("kind") == "reply" and last.get("role") == "developer"):
            awaiting = "sme"
        else:
            awaiting = "developer"
    elif status == "blocked":
        owner = (e.get("next_action") or {}).get("owner") or {}
        p = _party(owner, parts) or {}
        awaiting = p.get("side") or "developer"

    shepherd = e.get("shepherd")
    dev_owner = {"participant": shepherd} if shepherd else ANY_DEVELOPER
    if e.get("next_action"):
        na = {k: v for k, v in e["next_action"].items() if k != "recorded"}
        na["owner"] = _party(na.get("owner"), parts)
        na["derived"] = False
    elif status == "draft":
        na = {"action": "send", "owner": _party(dev_owner, parts), "derived": True}
    elif status == "out_for_discussion" and awaiting == "sme":
        owner = e.get("owner") or {"side": "sme", "role_title": "SME (owner not recorded)"}
        na = {"action": "answer", "owner": _party(owner, parts), "derived": True}
    elif status == "out_for_discussion":
        na = {"action": "reply", "owner": _party(dev_owner, parts), "derived": True}
    elif status == "answered":
        na = {"action": "apply", "owner": _party(dev_owner, parts), "derived": True}
    elif status == "blocked":
        na = {"action": "unblock", "owner": _party(ANY_DEVELOPER, parts), "derived": True}
    else:
        na = None

    seen = None
    if asks:
        latest = max((_msg_at(m) for m in asks if _msg_at(m)), default=None)
        seen = any(
            r.get("side") == "sme" and latest is not None and (parse_at(r.get("first_seen_at")) or latest) >= latest
            for r in e.get("receipts") or []
            if isinstance(r, dict)
        )

    dated = [(m, _msg_at(m)) for m in thread if _msg_at(m)]
    last_activity = None
    if dated:
        m, _ = max(dated, key=lambda md: md[1])
        last_activity = {"at": m.get("at"), "by_side": m.get("role"), "kind": m.get("kind"), "message": m.get("id")}

    origins = []
    for o in e.get("origins") or []:
        if not isinstance(o, dict):
            continue
        item = {k: o.get(k) for k in ("key", "tag", "match", "note") if o.get(k) is not None}
        if o.get("tag") in ARTIFACT_TAGS:
            item["present"] = _present(o.get("key"), o.get("tag"), catalogue)
        origins.append(item)

    row = {
        "id": e.get("id"),
        "filed": True,
        "kind": e.get("kind"),
        "plane": e.get("plane"),
        "title": e.get("title"),
        "question": e.get("question"),
        "context": e.get("context"),
        "subject": e.get("subject"),
        "priority": e.get("priority"),
        "owner": _party(e.get("owner"), parts),
        "shepherd": _party({"participant": shepherd}, parts) if shepherd else None,
        "status": status,
        "status_detail": e.get("status_detail"),
        "entered_at": entered,
        "days_in_status": a["min"],
        "days_in_status_max": a["max"],
        "age_bound": a["bound"],
        "overdue": is_over,
        "overdue_possible": possible,
        "days_overdue": days_over,
        "awaiting": awaiting,
        "origins": origins,
        "asked": asked,
        "asks_not_evidenced": sum(1 for m in thread if m.get("kind") == "ask" and _delivery(m) == "not_evidenced"),
        "follow_ups": follow_ups,
        "answer": e.get("answer"),
        "references": e.get("references") or [],
        "outcome": e.get("outcome"),
        "next_action_effective": na,
        "interim_rulings": e.get("interim_rulings") or [],
        "conflicts": e.get("conflicts") or [],
        "open_conflicts": sum(1 for c in e.get("conflicts") or [] if isinstance(c, dict) and not c.get("resolved")),
        "last_activity": last_activity,
        "messages": len(thread),
        "seen_by_sme": seen,
        "rev": e.get("rev"),
        "status_history": hist,
    }
    if include_thread:
        row["thread"] = thread
    return row


def _present(key, tag, catalogue):
    """True / False when the half that projects this tag was read; None ("unknown") otherwise."""
    if catalogue is None:
        return None
    half = "oracle_needs" if tag == "oracle" else "register"
    if catalogue.get(half) != "present":
        return None
    return key in catalogue["keys"]


# ── order ───────────────────────────────────────────────────────────────────────────────────────
def _bucket(r: dict) -> tuple:
    """Chase order: overdue first, then the replies the team owes, then the rest (DESIGN §6.4)."""
    st = r.get("status")
    if r.get("filed") is not True:
        return (7, 0)
    if r.get("overdue"):
        return (1, -(r.get("days_overdue") or 0))
    if r.get("overdue_possible"):
        return (1.5, -(r.get("days_in_status_max") or 0))
    if st == "out_for_discussion" and r.get("awaiting") == "developer":
        la = parse_at(((r.get("last_activity") or {}).get("at") or {}).get("at"))
        return (2, la.timestamp() if la else 0)
    if st == "answered":
        return (3, -(r.get("days_in_status") or 0))
    if st == "out_for_discussion":
        return (4, -(r.get("days_in_status") or 0))
    if st == "blocked":
        return (5, 0)
    if st == "draft":
        return (6, 0)
    if st == "applied":
        at = parse_at(((r.get("entered_at") or {}).get("at")))
        return (8, -(at.timestamp() if at else 0))
    return (9, 0)


def _order_key(r: dict):
    return (*_bucket(r), _PRIORITY_RANK.get(r.get("priority") or r.get("declared_priority") or "", 3), str(r.get("id")))


# ── the join ────────────────────────────────────────────────────────────────────────────────────
def _title(text: str) -> str:
    first = str(text or "").strip().splitlines()[0] if str(text or "").strip() else ""
    return first if len(first) <= 160 else first[:159].rstrip() + "…"


def _unfiled_row(r: dict, members: list | None, filed_members: int, filing_known: bool) -> dict:
    keys = members if members is not None else [r.get("key")]
    return {
        "id": r.get("key"),
        "filed": False if filing_known else None,
        "filing_state": "not_filed" if filing_known else "unknown",
        "kind": r.get("kind"),
        "plane": r.get("plane") or "ontology",
        # A list title; the full text travels beside it, so nothing is lost to the cut.
        "title": _title(r.get("text")),
        "text": r.get("text"),
        "status": "draft",
        "priority": None,
        "declared_priority": r.get("declared_priority"),
        "declared_status": r.get("declared_status"),
        "owner_role": r.get("owner_role"),
        "subject": r.get("subject"),
        "members": members,
        "members_filed": filed_members,
        "variants": r.get("variants"),
        "origins": [{"key": k, "tag": r.get("origin"), "present": True} for k in keys],
        "source": r.get("source"),
        "fileable": all(_oq.ORIGIN_KEY_RE.match(k or "") for k in keys),
        "overdue": False,
        "overdue_possible": False,
        "awaiting": "developer",
        "next_action_effective": {"action": "file", "owner": dict(ANY_DEVELOPER, label="any developer"), "derived": True},
    }


def overview(root, *, as_of=None, schema=None, catalogue_root=None, include_thread=True) -> dict:
    root = Path(root)
    as_of = parse_at(as_of) if as_of is not None else _dt.datetime.now(_dt.timezone.utc)
    ledger = load_ledger(root, schema=schema)
    cat = load_catalogue(Path(catalogue_root) if catalogue_root else root)
    doc = ledger["doc"] or {}

    raw_policy = (doc.get("policy") or {}).get("overdue_after_days")
    if isinstance(raw_policy, int) and not isinstance(raw_policy, bool) and 1 <= raw_policy <= 365:
        policy = {"overdue_after_days": raw_policy, "source": "ledger"}
    else:
        policy = {"overdue_after_days": DEFAULT_OVERDUE_DAYS, "source": "default"}
        if raw_policy is not None:
            policy["note"] = f"policy.overdue_after_days {raw_policy!r} is not a whole number of days from 1 to 365"
    threshold = policy["overdue_after_days"]

    parts = {p.get("id"): p for p in doc.get("participants") or [] if isinstance(p, dict)}
    entries = [e for e in doc.get("entries") or [] if isinstance(e, dict)]
    filing_known = ledger["state"] != "invalid"
    catalogue_read = cat if cat["register"] == "present" or cat["oracle_needs"] == "present" else None

    filed_by_key: dict[str, list[str]] = {}
    for e in entries:
        for o in e.get("origins") or []:
            if isinstance(o, dict) and o.get("key"):
                filed_by_key.setdefault(o["key"], []).append(e.get("id"))

    rows, excluded = [], 0
    for e in entries:
        if e.get("plane") != "ontology":
            excluded += 1  # Model conditions lists the ontology plane; the data plane has its own page
            continue
        rows.append(derive_entry(e, as_of, threshold, parts, catalogue_read, include_thread))

    for r in cat["rows"]:
        members = r.get("members")
        if members:
            unfiled = [k for k in members if k not in filed_by_key]
            if unfiled:
                rows.append(_unfiled_row(r, unfiled, len(members) - len(unfiled), filing_known))
        elif r.get("key") not in filed_by_key:
            rows.append(_unfiled_row(r, None, 0, filing_known))

    rows.sort(key=_order_key)

    coherence = []

    def finding(code, severity, entry, title, key=None):
        coherence.append({"code": code, "severity": severity, "entry": entry, "key": key, "title": title})

    for k, ids in sorted(filed_by_key.items()):
        if len(ids) > 1:
            finding("origin-filed-twice", "error", ", ".join(map(str, ids)), "one artifact question cannot have two conversations", k)
    for r in rows:
        if r.get("filed") is not True:
            continue
        art = [o for o in r["origins"] if o.get("tag") in ARTIFACT_TAGS]
        if r["status"] in ("applied", "withdrawn"):
            for o in art:
                if o.get("present") is True:
                    finding("closed-but-still-asked", "warning", r["id"], "the artifact still asks this: clear the oracle flag, the concept open question or the change-record block", o["key"])
        if r["status"] in ("draft", "out_for_discussion", "blocked") and art and all(o.get("present") is False for o in art):
            finding("open-but-origin-gone", "info", r["id"], "nothing in the model asks this any more: withdraw it or re-anchor it")
        entered = parse_at((r.get("entered_at") or {}).get("at"))
        if r["status"] == "out_for_discussion":
            for m in r.get("thread") or next((e.get("thread") for e in entries if e.get("id") == r["id"]), []) or []:
                if m.get("kind") == "answer" and m.get("role") == "sme" and (entered is None or (_msg_at(m) or entered) >= entered):
                    finding("answer-not-marked", "info", r["id"], "an SME answered, but the status was not moved")
                    break
    for e in entries:
        acts = [m.get("recorded") for m in e.get("thread") or [] if isinstance(m, dict) and m.get("role") == "sme" and m.get("kind") in SME_ACTS]
        acts += [h.get("recorded") for h in e.get("status_history") or [] if isinstance(h, dict) and (h.get("recorded") or {}).get("role") == "sme"]
        if any((st or {}).get("identity_basis") == "local-declared" for st in acts):
            finding("sme-act-local-declared", "warning", e.get("id"), "recorded under a declared local identity: not evidence of an SME act")

    counts = {
        "rows": len(rows),
        "filed": sum(1 for r in rows if r.get("filed") is True),
        "not_filed": sum(1 for r in rows if r.get("filed") is False),
        "filing_unknown": sum(1 for r in rows if r.get("filed") is None),
        "by_status": {s: sum(1 for r in rows if r.get("status") == s) for s in STATUSES},
        "overdue": sum(1 for r in rows if r.get("overdue")),
        "overdue_possible": sum(1 for r in rows if r.get("overdue_possible")),
        "awaiting_developer_out_for_discussion": sum(
            1 for r in rows if r.get("status") == "out_for_discussion" and r.get("awaiting") == "developer"
        ),
        "by_kind": {k: sum(1 for r in rows if r.get("kind") == k) for k in _oq.SME_KINDS},
        "by_origin": {},
        "excluded_other_plane": excluded,
        "operator_items": len(cat["operator_items"]),
    }
    counts["open"] = sum(counts["by_status"][s] for s in OPEN_STATUSES)
    for r in rows:
        for tag in sorted({o.get("tag") for o in r.get("origins") or [] if o.get("tag")}):
            counts["by_origin"][tag] = counts["by_origin"].get(tag, 0) + 1

    triage = [t for t in doc.get("historic_triage") or [] if isinstance(t, dict)]
    by_disp: dict[str, int] = {}
    for t in triage:
        by_disp[t.get("disposition")] = by_disp.get(t.get("disposition"), 0) + 1

    return {
        "format": FORMAT,
        "as_of": as_of.isoformat().replace("+00:00", "Z"),
        "ledger": {
            "state": ledger["state"],
            "path": LEDGER,
            "validated": ledger["validated"],
            "errors": ledger["errors"],
            "fingerprint": ledger["fingerprint"],
        },
        "catalogue": {"register": cat["register"], "oracle_needs": cat["oracle_needs"]},
        "policy": policy,
        "counts": counts,
        "rows": rows,
        "coherence": coherence,
        "projector_findings": cat["findings"],
        "operator_items": cat["operator_items"],
        "triage": {
            "items": len(triage),
            "by_disposition": dict(sorted(by_disp.items(), key=lambda kv: str(kv[0]))),
            "clarification_owed": [
                {"key": t.get("key"), "title": t.get("title"), "promoted_to": t.get("promoted_to")}
                for t in triage
                if t.get("disposition") == "clarification_owed"
            ],
        },
        "documents": len([d for d in doc.get("documents") or [] if isinstance(d, dict)]),
        "participants": [
            {k: p.get(k) for k in ("id", "side", "role_title", "display_name", "historic_only") if p.get(k) is not None}
            for p in parts.values()
        ],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SME questions: the catalogue joined with the ledger, at read time.")
    ap.add_argument("--bundle", required=True, help="the bundle's live root (the ledger is read here)")
    ap.add_argument("--catalogue-root", help="where the projected catalogue is read (default: the bundle)")
    ap.add_argument("--as-of", help="ISO date or datetime to derive ages against (default: now, UTC)")
    ap.add_argument("--schema", help="also validate the ledger against this JSON Schema")
    ap.add_argument("--no-thread", action="store_true", help="omit each entry's messages")
    ap.add_argument("--out", help="write the overview here instead of printing it")
    a = ap.parse_args(argv)
    root = Path(a.bundle)
    if not root.is_dir():
        print(f"sme_questions: no bundle at {root}", file=sys.stderr)
        return 2
    if a.as_of and parse_at(a.as_of) is None:
        print(f"sme_questions: --as-of {a.as_of!r} is not an ISO date or datetime", file=sys.stderr)
        return 2
    if a.out:
        target = Path(a.out).resolve()
        # A read-time view written into the model or over the ledger would be exactly the stale,
        # hashed copy of dialogue this module exists to avoid.
        for forbidden in (root / "ontology", root / "data", root / "governance"):
            if target == forbidden.resolve() or forbidden.resolve() in target.parents:
                print(f"sme_questions: refusing to write inside {forbidden}", file=sys.stderr)
                return 2
    ov = overview(root, as_of=a.as_of, schema=a.schema, catalogue_root=a.catalogue_root, include_thread=not a.no_thread)
    text = json.dumps(ov, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        c = ov["counts"]
        print(
            f"sme_questions: {c['rows']} row(s) ({c['filed']} filed, {c['not_filed']} not filed); "
            f"ledger {ov['ledger']['state']}; wrote {a.out}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
