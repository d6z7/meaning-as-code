#!/usr/bin/env python3
"""sdk.project.ontology_quality — the ONTOLOGY-QUALITY projection: the model's own quality /
completeness dashboard, the twin of the data-quality dashboard. DETERMINISTIC + IDEMPOTENT (no LLM,
no AWS) — derived purely from the authored concepts + edges + the data grounding.

It measures three things the data-quality dashboard cannot:
  - MATURITY      — how much is SME-CONFIRMED (confidence C) vs machine-inferred (I) / needs-SME (Q),
                    and confirmed (C) vs proposed (P) for rules. The direct analog of DQ's resolved/gap.
  - CONNECTIVITY  — how many concepts are related to another concept, whether by an ontology EDGE or
                    by a contract RULE that binds another concept's canonical key. Refuse-stubs
                    (identity.kind = sme_pending, no key) are excluded: they are authored to be
                    unlinked, so counting them as a shortfall argues for asserting a false relationship.
  - DOCUMENTATION / COVERAGE — column descriptions, rule-kind coverage, edge depth.
  - EXECUTION VALIDATION — FRAMEWORK.md §8's THIRD rung. MATURITY above measures the fourth
                    (SME-confirmed vs inferred); nothing measured the third. A concept can be authored,
                    structurally valid, and never once checked against the warehouse — and the dashboard
                    reported it at 95 % confirmed. Read from acceptance/*.yaml `validates`, the field
                    that attributes L2 evidence to the concepts it holds to account.
  - ANSWERABILITY — whether each concept's answer path DERIVES from its declarations, or is only
                    sworn to in a hand-written no_probe_guarantee. Read from the compiler's own
                    check_answerability (compile.json), never recomputed here: the logic has ONE home
                    in meaning-as-code/tools, and a dashboard that re-derived it would be a second.
And it emits the SME CATALOGUE: what the model asks a subject-matter expert (`sme_questions`).

THE SME CATALOGUE (format mac.sme-catalogue/1)
-----------------------------------------------
A catalogue row is a CANDIDATE: a question or a sign-off request that an artifact of the bundle
poses. It is not a conversation. The rows carry NO status, NO invented priority and NO people:
whether a question was asked, answered or applied lives in the bundle's SME question ledger
(`governance/sme-questions.yaml`), which this projector never reads. WHY: the projection is
compiled into the served artifact and hashed with it, while the ledger changes whenever anyone
posts a message; and "overdue" depends on the moment it is read. The join of catalogue and ledger
is a read-time view (`sdk.project.sme_questions`), never a projected file.

    {"key": "concept:store#open_questions[oq1]",   the ORIGIN KEY (below) — what a ledger files
     "origin": "concept-field",                     register | concept-field | oracle
     "kind": "question",                            question | sign_off — counted apart everywhere
     "plane": "ontology",
     "subject": {"concepts": ["store"]},
     "text": "<verbatim, never cut>",
     "owner_role": <as the artifact declares it, or null>,
     "declared_priority": <as declared, or null>,   copied, never derived from the kind
     "declared_status": <as declared, or null>,     e.g. an open question's own OPEN / PARTIAL
     "members": null,                               a grouped oracle row lists its member keys
     "source": {"path": "...", "pointer": "..."},
     "fileable": true,                              false when the key breaks the grammar
     "id", "question", "concept", "concept_title"}  TRANSITION ALIASES (see sme_row)

ORIGIN KEYS — ids only, never file paths, so moving a file orphans nothing:

    concept:<concept>#open_questions[<id>]          a concept's open_questions[] entry
    concept:<concept>#values[<code>].open_question  a value-level open question
    concept:<concept>#enumerations[<name>].values[<code>].open_question
    concept:<concept>#constraints[<i>].open_question
    concept:<concept>#identity                      identity awaiting an SME (no key)
    concept:<concept>#confidence                    concept confidence below confirmed   sign_off
    concept:<concept>#enumeration                   the value set is not resolved
    concept:<concept>#measure_type                  a measure declares no resolvable type
    rule:<rule>#confidence                          a rule at confidence P               sign_off
    intervention:<entry>#sme                        a change-record entry's `sme` block
    oracle:<question>#needs_sme                     a test oracle flagged needs-SME (sdk.acceptance.sme_needs)

Whitespace and `%` inside a fragment id are percent-encoded, so a code with a space still yields
one token.

THE CHANGE-RECORD `sme` BLOCK. An entry of interventions/ledger.yaml poses an SME ask ONLY through
a structured block; its free-text `sme_owner` is history and is never parsed for a question:

    sme:
      ask_kind: sign_off        # question | sign_off | operator | none
      owner_role: domain owner  # required for question and sign_off
      ask: Is each store's opening date read from the store master rather than the first sale?
      plane: ontology           # ontology | data; absent = derived from the entry's objects

An entry that names an `sme_owner` and carries no block is a FINDING (`sme-ask-unstructured`), not
a question. `ask_kind: operator` lands in `sme_operator_items` (not an SME question); a data-plane
ask lands in `sme_routed_to_data` (the data register carries it).
"""

from __future__ import annotations

RULE_KINDS = ["resolution", "aggregation", "default", "ambiguity", "exclusion", "guarantee"]
_SEV = {"high": 0, "medium": 1, "low": 2}

import re as _re
from collections import Counter as _Counter
from pathlib import Path

# ── SME catalogue vocabulary. Each set is closed and lives here once; the collector and the
#    read-time join import it rather than restating it. ────────────────────────────────────────
SME_CATALOGUE_FORMAT = "mac.sme-catalogue/1"
SME_FINDING_CATEGORY = "sme-questions"
SME_KINDS = ("question", "sign_off")
# The ledger's origin-key grammar. A candidate whose key does not match can be SHOWN but not FILED,
# so the row says so (`fileable: false`) and a finding names it, instead of a filing failing later.
ORIGIN_KEY_RE = _re.compile(
    r"^(concept|rule|intervention|oracle|annotation|historic|manual):[A-Za-z0-9_.:/-]+(#\S+)?$"
)
ASK_KINDS = ("question", "sign_off", "operator", "none")
SME_BLOCK_KEYS = {"ask_kind", "owner_role", "ask", "plane"}
# A change-record entry in any of these states asks nothing any more. Seen in real change records:
# none of these statuses is ever used, and supersession is recorded only on the NEWER entry, as
# `supersedes` — so the older entry is recognised by being named there, not by its own fields.
CLOSED_CHANGE_STATUSES = {"withdrawn", "superseded", "ratified", "closed"}
CLOSING_MARKERS = ("withdrawn_by", "superseded_by", "ratified_by")
DATA_PLANE_OBJECT_KINDS = {"dataset", "transform", "lookup", "source"}
RESOLVED_OPEN_QUESTION = {"resolved", "closed", "withdrawn"}
DOUBTFUL_CONFIDENCE = {"I", "Q"}
CHANGE_RECORD = "interventions/ledger.yaml"


def _pct(num, den, what: str):
    """A percentage, or NOTHING — never a percentage over an empty denominator.

    `round(100 * num / max(1, den))` appeared six times in this file and is the defect it looks
    like a defence against. It guards the ZeroDivisionError and, in doing so, converts "there was
    nothing to measure" into a confident 0 %. A reader cannot tell those apart, and a scorecard
    that says 0 % when it means "I did not measure" is worse than one that says nothing: the first
    is acted on.

    This estate refuses an empty denominator everywhere it MEASURES — mac_diag.refuse_empty, the
    console render gate's population guard, every check_*.py — and did not refuse it anywhere it
    PROJECTS. That asymmetry is how `execution_validation` published `covered: 0, pct: 0` over 267
    properties whose join had simply not resolved.

    Returns (pct, note). `pct` is None when nothing could be measured, and `note` says why, so the
    caller publishes an absence rather than a number.
    """
    if den <= 0:
        return None, f"not measured — no {what} to measure ({den} in the denominator)"
    return round(100 * num / den), None


# ════════════════════════════════════════════════════════════════════════════════════════════════
# SME CATALOGUE — the rows, the keys, and the findings that stand where a fake question used to
# ════════════════════════════════════════════════════════════════════════════════════════════════


def key_fragment(ident) -> str:
    """An id placed inside a key fragment, with `%` and whitespace percent-encoded.

    WHY: the grammar's fragment is `\\S+`. A value code such as "Plug in" would otherwise produce a
    key the ledger refuses, and the question could be seen but never filed."""
    out = []
    for ch in str(ident):
        out.append(f"%{ord(ch):02X}" if ch == "%" or ch.isspace() else ch)
    return "".join(out)


def sme_row(
    *,
    key: str,
    origin: str,
    kind: str,
    text: str,
    concepts=(),
    title_of: dict | None = None,
    owner_role=None,
    declared_priority=None,
    declared_status=None,
    members=None,
    source: dict | None = None,
    **extra,
) -> dict:
    """One catalogue row, in the one shape every origin shares.

    TRANSITION ALIASES. Two console views read these rows today and cannot change until their
    integration packet lands: the model-conditions tab reads `kind` and the count, and the objects
    view's SME pane reads `id`, `question`, `concept` and `concept_title` — without them it renders
    rows with no text and no link. So each row also carries `id` (= key), `question` (= text),
    `concept` and `concept_title` (the first subject concept). `current` is gone: it was the
    artifact's confidence letter shown as if it were a conversation status, and the pane already
    tolerates its absence. test_sme_register pins the aliases; the integration packet removes them.
    """
    concepts = [str(c) for c in concepts if c]
    first = concepts[0] if concepts else None
    row = {
        "key": key,
        "origin": origin,
        "kind": kind,
        "plane": "ontology",
        "subject": {"concepts": concepts},
        "text": text,
        "owner_role": owner_role if isinstance(owner_role, str) and owner_role.strip() else None,
        "declared_priority": declared_priority if isinstance(declared_priority, str) else None,
        "declared_status": declared_status if isinstance(declared_status, str) else None,
        "members": members,
        "source": source,
        "fileable": bool(ORIGIN_KEY_RE.match(key)),
        "id": key,
        "question": text,
        "concept": first,
        "concept_title": ((title_of or {}).get(first) or first) if first else None,
    }
    row.update(extra)
    return row


def sme_finding(code: str, severity: str, subject, title: str, detail: str, *, concept=None, source=None):
    """A finding about the SME catalogue, in the register's finding shape (the model-conditions tab
    already renders that shape, so a finding is visible where the fake question used to be)."""
    return {
        "id": f"{code}.{subject}",
        "category": SME_FINDING_CATEGORY,
        "code": code,
        "severity": severity,
        "concept": concept,
        "concept_title": str(subject),
        "title": title,
        "detail": detail,
        "source": source,
    }


def _unreadable(path: str, error) -> dict:
    # WHY HIGH: the old lift sat in `except Exception: pass`, so a change record that failed to parse
    # removed every one of its rows and the register looked cleaner for it.
    return sme_finding(
        "sme-source-unreadable",
        "high",
        path,
        "cannot be read, so the SME questions it poses are unknown",
        f"{type(error).__name__ if isinstance(error, Exception) else 'Error'}: {error}",
        source={"path": path, "pointer": None},
    )


def complete_sentence(text) -> bool:
    """Is `text` a whole sentence a person could be asked? Not a proof of meaning — a guard against
    the two shapes that posed as questions: a tail cut out of a longer sentence (starts lower-case,
    closes a parenthesis it never opened) and an empty or one-word stub."""
    if not isinstance(text, str):
        return False
    t = text.strip()
    if len(t.split()) < 2:
        return False
    # A sentence may open with a lower-case IDENTIFIER (`price_tier 3 is the list price.`,
    # `store.opening_date is read from the store master.`): its first token joins parts with `_` or
    # `.`, which a cut-off tail of prose ("only the notation ...") never does. Without this, a whole
    # structured ask was published as a finding, and the ledger entry filed on it read "origin gone".
    ident = _re.fullmatch(r"[a-z][A-Za-z0-9]*(?:[_.][A-Za-z0-9]+)+[,:;]?", t.split()[0]) is not None
    if not (t[0].isupper() or t[0].isdigit() or t[0] in "\"'“‘([`" or ident):
        return False
    if t.rstrip("\"'”’)]`")[-1:] not in ("?", ".", "!"):
        return False
    return t.count("(") == t.count(")") and t.count("[") == t.count("]")


def measure_type_members(repo_root: Path | None = None):
    """The members of mac.MeasureType, read from the framework's vocabulary (their one home), or
    None when the vocabulary cannot be read."""
    try:
        import yaml as _yaml

        vocab = (repo_root or Path(__file__).resolve().parents[2]) / "mac_vocabulary.yaml"
        doc = _yaml.safe_load(vocab.read_text(encoding="utf-8")) or {}
        members = (doc.get("MeasureType") or {}).get("members") or {}
        return set(members) if members else None
    except Exception:  # noqa: BLE001 — reported by the caller as sme-source-unreadable
        return None


def measure_type_declared(concept_doc: dict, members) -> bool:
    """Does a measure declare how it adds up, the way the answerability check reads it
    (`concept.semantics.measure_type`), resolvable in mac.MeasureType?

    WHY THIS AND NOT "has an aggregation rule": per-concept aggregation rules were retired in
    favour of the declared type, after which the old detector asked "how does it aggregate?" of
    every measure in a bundle that had answered it for every measure."""
    mt = ((concept_doc.get("concept") or {}).get("semantics") or {}).get("measure_type")
    if not isinstance(mt, str) or not mt.startswith("mac.MeasureType."):
        return False
    if members is None:
        # The vocabulary is unreadable: say so once (the caller does) instead of manufacturing a
        # question for every measure that did declare a type.
        return True
    return mt.split(".")[-1] in members


def value_set_unresolved(doc: dict) -> bool:
    """An enumeration whose value set nobody has settled: closure `unknown`, or no members and
    nothing that realizes them.

    WHY `realized_by` COUNTS: a closed value set read from a register deliberately has no inline
    `items`; asking "is it closed, and what are its values?" of it asks what the file answers."""
    v = doc.get("values") if isinstance(doc.get("values"), dict) else {}
    if str(v.get("closure") or "").strip().lower() == "unknown":
        return True
    if v.get("items") or v.get("realized_by"):
        return False
    for en in doc.get("enumerations") or []:
        if isinstance(en, dict) and (en.get("values") or en.get("items") or en.get("realized_by")):
            return False
    return True


def _value_items(doc: dict):
    """(key fragment, pointer, item) for every value item, in both value-set shapes."""
    v = doc.get("values")
    if isinstance(v, dict):
        for i, it in enumerate(v.get("items") or []):
            if isinstance(it, dict):
                code = it.get("code", it.get("value"))
                ident = key_fragment(code if code is not None else f"@{i}")
                yield f"values[{ident}]", f"values.items[{i}]", it
    for j, en in enumerate(doc.get("enumerations") or []):
        if not isinstance(en, dict):
            continue
        name = key_fragment(en.get("name") or en.get("id") or f"@{j}")
        for i, it in enumerate(en.get("values") or en.get("items") or []):
            if isinstance(it, dict):
                code = it.get("code", it.get("value"))
                ident = key_fragment(code if code is not None else f"@{i}")
                yield (
                    f"enumerations[{name}].values[{ident}]",
                    f"enumerations[{j}].values[{i}]",
                    it,
                )


def concept_sme(stem: str, doc: dict, title_of: dict, members, rel_path: str) -> tuple[list, list]:
    """The rows and findings one concept file contributes to the SME catalogue."""
    rows, findings = [], []
    con = doc.get("concept") or {}
    meta = doc.get("metadata") or {}
    klass = con.get("class")
    title = title_of.get(stem) or stem
    ident = con.get("identity") or {}
    refuse_stub = ident.get("kind") == "sme_pending" and not ident.get("canonical_key")

    def src(pointer):
        return {"path": rel_path, "pointer": pointer}

    def add(key, kind, text, pointer, origin="register", **kw):
        rows.append(
            sme_row(
                key=key,
                origin=origin,
                kind=kind,
                text=text,
                concepts=[stem],
                title_of=title_of,
                source=src(pointer),
                **kw,
            )
        )

    mc = meta.get("confidence")
    # A refuse-stub is authored unconfirmed on purpose; its real question is its identity (below).
    if mc in DOUBTFUL_CONFIDENCE and not refuse_stub:
        add(
            f"concept:{key_fragment(stem)}#confidence",
            "sign_off",
            f"Is the concept “{title}” ({klass}) defined correctly? It is recorded at confidence "
            f"{mc} ({'needs an SME' if mc == 'Q' else 'inferred'}), not confirmed.",
            "metadata.confidence",
        )

    for r in (doc.get("contract") or {}).get("rules") or []:
        if not isinstance(r, dict) or r.get("confidence") != "P":
            continue
        if not r.get("id"):
            findings.append(
                sme_finding(
                    "sme-block-invalid",
                    "low",
                    stem,
                    "a proposed rule has no id, so its sign-off cannot be keyed",
                    "contract.rules[] entry at confidence P without an `id`.",
                    concept=stem,
                    source=src("contract.rules"),
                )
            )
            continue
        subj = r.get("subject") or r.get("id")
        add(
            f"rule:{key_fragment(r['id'])}#confidence",
            "sign_off",
            f"Is the rule “{subj}” on “{title}” correct? It is recorded as proposed, not confirmed.",
            f"contract.rules[id={r['id']}]",
        )

    if ident.get("kind") == "sme_pending":
        add(
            f"concept:{key_fragment(stem)}#identity",
            "question",
            f"What is the canonical identity (the key) of “{title}”?",
            "concept.identity",
        )

    if klass == "enumeration" and value_set_unresolved(doc):
        add(
            f"concept:{key_fragment(stem)}#enumeration",
            "question",
            f"Is “{title}” a closed set of values? If it is, what are all of its valid values?",
            "values",
        )

    if klass == "measure" and not measure_type_declared(doc, members):
        add(
            f"concept:{key_fragment(stem)}#measure_type",
            "question",
            f"How does the measure “{title}” add up across its axes? It declares no measure type "
            f"that mac.MeasureType resolves.",
            "concept.semantics.measure_type",
        )

    oqs = doc.get("open_questions")
    if oqs is not None and not isinstance(oqs, list):
        findings.append(
            sme_finding(
                "sme-block-invalid",
                "medium",
                stem,
                "open_questions is not a list, so its questions cannot be read",
                f"open_questions is a {type(oqs).__name__}.",
                concept=stem,
                source=src("open_questions"),
            )
        )
        oqs = []
    for i, oq in enumerate(oqs or []):
        oid = str((oq or {}).get("id") or "").strip() if isinstance(oq, dict) else ""
        text = (oq or {}).get("question") if isinstance(oq, dict) else None
        if not oid or not isinstance(text, str) or not text.strip():
            findings.append(
                sme_finding(
                    "sme-block-invalid",
                    "medium",
                    f"{stem}.open_questions[{i}]",
                    "an open question without an id or without text",
                    "Nothing is invented in its place; give the entry an `id` and its `question`.",
                    concept=stem,
                    source=src(f"open_questions[{i}]"),
                )
            )
            continue
        status = str(oq.get("status") or "").strip()
        if status.lower() in RESOLVED_OPEN_QUESTION:
            continue
        add(
            f"concept:{key_fragment(stem)}#open_questions[{key_fragment(oid)}]",
            "question",
            text.strip(),
            f"open_questions[id={oid}]",
            origin="concept-field",
            owner_role=oq.get("owner_for_resolution"),
            declared_priority=oq.get("priority"),
            declared_status=status or None,
        )

    unasked = []
    for frag, pointer, it in _value_items(doc):
        oq = it.get("open_question")
        if isinstance(oq, str) and oq.strip():
            add(
                f"concept:{key_fragment(stem)}#{frag}.open_question",
                "question",
                oq.strip(),
                f"{pointer}.open_question",
                origin="concept-field",
            )
        elif it.get("confidence") in DOUBTFUL_CONFIDENCE:
            unasked.append(str(it.get("code", it.get("value"))))
    if unasked:
        # WHY A FINDING AND NOT A QUESTION: nobody wrote the question. Inventing its text is the
        # defect this catalogue exists to remove.
        findings.append(
            sme_finding(
                "sme-value-unasked",
                "low",
                stem,
                f"{len(unasked)} value(s) not confirmed and no question recorded",
                "Values at confidence I or Q with no `open_question`: " + ", ".join(unasked) + ".",
                concept=stem,
                source=src("values"),
            )
        )

    for i, c in enumerate(doc.get("constraints") or []):
        oq = c.get("open_question") if isinstance(c, dict) else None
        if isinstance(oq, str) and oq.strip():
            # Keyed by position: a constraint has no id. Reordering constraints re-keys the question.
            add(
                f"concept:{key_fragment(stem)}#constraints[{i}].open_question",
                "question",
                oq.strip(),
                f"constraints[{i}].open_question",
                origin="concept-field",
            )
    return rows, findings


def _objects_plane(objects) -> str:
    """`data` when every object an entry touched is a data-plane object, else `ontology`."""
    kinds = {str(o).split(":", 1)[0] for o in objects or [] if ":" in str(o)}
    return "data" if kinds and kinds <= DATA_PLANE_OBJECT_KINDS else "ontology"


def change_record_sme(root, title_of: dict) -> dict:
    """The change record's contribution: rows from structured `sme` blocks, operator items, asks
    routed to the data plane, and a finding for every entry that names an owner without a block.

    NEVER PARSES FREE TEXT. The previous lift split `sme_owner` at its first em dash, so an owner
    string with a dash inside a parenthesis published its tail as a question, and one without a dash
    published a placeholder sentence as a question. Neither was ever asked by anyone."""
    out = {"rows": [], "operator_items": [], "routed_to_data": [], "findings": []}
    if root is None:
        return out
    path = Path(root) / CHANGE_RECORD
    if not path.exists():
        return out
    try:
        import yaml as _yaml

        doc = _yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — reported, never swallowed
        out["findings"].append(_unreadable(CHANGE_RECORD, e))
        return out
    entries = doc.get("interventions") if isinstance(doc, dict) else None
    if not isinstance(entries, list):
        out["findings"].append(_unreadable(CHANGE_RECORD, "no `interventions` list at the top level"))
        return out

    superseded = set()
    for e in entries:
        if isinstance(e, dict):
            s = e.get("supersedes")
            for x in s if isinstance(s, list) else [s]:
                if x:
                    superseded.add(str(x).strip())

    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            out["findings"].append(_unreadable(f"{CHANGE_RECORD}#interventions[{i}]", "not a mapping"))
            continue
        eid = str(e.get("id") or "").strip()
        has_sme = e.get("sme") is not None or str(e.get("sme_owner") or "").strip()
        if not eid:
            if has_sme:
                out["findings"].append(
                    _unreadable(f"{CHANGE_RECORD}#interventions[{i}]", "an SME ask on an entry with no id")
                )
            continue
        status = str(e.get("status") or "").strip().lower()
        if (
            status in CLOSED_CHANGE_STATUSES
            or any(e.get(m) for m in CLOSING_MARKERS)
            or eid in superseded
        ):
            continue
        src = {"path": CHANGE_RECORD, "pointer": f"interventions[id={eid}].sme"}
        sme = e.get("sme")
        if sme is None:
            if str(e.get("sme_owner") or "").strip():
                out["findings"].append(
                    sme_finding(
                        "sme-ask-unstructured",
                        "low",
                        eid,
                        "names an SME owner but carries no structured ask",
                        f"Change-record entry {eid} (status {status or 'unset'}) has a free-text "
                        "`sme_owner` and no `sme` block. Free text is not read as a question. Add "
                        "`sme: {ask_kind: question | sign_off | operator | none, owner_role, ask}`.",
                        source={"path": CHANGE_RECORD, "pointer": f"interventions[id={eid}].sme_owner"},
                    )
                )
            continue

        def invalid(why, severity="medium"):
            out["findings"].append(
                sme_finding(
                    "sme-block-invalid",
                    severity,
                    eid,
                    "the `sme` block cannot be read as an ask",
                    why,
                    source=src,
                )
            )

        if not isinstance(sme, dict):
            invalid(f"`sme` is a {type(sme).__name__}, not a mapping.")
            continue
        extra = sorted(set(sme) - SME_BLOCK_KEYS)
        if extra:
            invalid(f"unknown key(s) {', '.join(extra)}; the block holds {sorted(SME_BLOCK_KEYS)}.", "low")
        ask_kind = str(sme.get("ask_kind") or "").strip()
        if ask_kind not in ASK_KINDS:
            invalid(f"ask_kind {ask_kind!r} is not one of {', '.join(ASK_KINDS)}.")
            continue
        if ask_kind == "none":
            continue
        key = f"intervention:{key_fragment(eid)}#sme"
        ask = sme.get("ask")
        if not complete_sentence(ask):
            out["findings"].append(
                sme_finding(
                    "sme-ask-incomplete",
                    "medium",
                    eid,
                    "the structured ask is not a complete sentence",
                    "An ask must be a whole sentence a person can answer; a fragment is not published "
                    "as a question. Rewrite `sme.ask`.",
                    source=src,
                )
            )
            continue
        ask = ask.strip()
        objects = e.get("objects") or []
        concepts = [str(o).split(":", 1)[1] for o in objects if str(o).startswith("concept:")]
        if ask_kind == "operator":
            out["operator_items"].append(
                {
                    "key": key,
                    "entry": eid,
                    "text": ask,
                    "owner_role": sme.get("owner_role"),
                    "subject": {"concepts": concepts},
                    "source": src,
                }
            )
            continue
        plane = str(sme.get("plane") or "").strip() or _objects_plane(objects)
        if plane not in ("ontology", "data"):
            invalid(f"plane {plane!r} is not ontology or data.")
            continue
        if plane == "data":
            out["routed_to_data"].append(
                {
                    "key": key,
                    "entry": eid,
                    "kind": ask_kind,
                    "dq_ids": [str(x) for x in e.get("dq_ids") or []],
                    "reason": "sme.plane is data"
                    if sme.get("plane")
                    else "every object the entry touched is a data-plane object",
                }
            )
            continue
        if not (isinstance(sme.get("owner_role"), str) and sme["owner_role"].strip()):
            invalid("names no owner_role; the ask is listed, but nobody is named to answer it.", "low")
        out["rows"].append(
            sme_row(
                key=key,
                origin="register",
                kind=ask_kind,
                text=ask,
                concepts=concepts,
                title_of=title_of,
                owner_role=sme.get("owner_role"),
                source=src,
                entry=eid,
            )
        )
    return out


_UNREAD = object()


def sme_catalogue(concepts: dict, root=None, concept_paths: dict | None = None, members=_UNREAD) -> dict:
    """The whole register-side SME catalogue: rows sorted by key, plus findings, operator items and
    data-plane routes. Pure over its inputs apart from reading the change record and, unless the
    caller already holds them, the MeasureType members."""
    title_of = {}
    for stem, c in concepts.items():
        con = (c or {}).get("concept") or {}
        title_of[stem] = con.get("label") or con.get("name") or stem
    rows, findings = [], []

    if members is _UNREAD:
        members = measure_type_members()
    if members is None and any(((c or {}).get("concept") or {}).get("class") == "measure" for c in concepts.values()):
        findings.append(_unreadable("mac_vocabulary.yaml#MeasureType", "the MeasureType members could not be read"))

    paths = dict(concept_paths or {})
    if root is not None and not paths:
        cdir = Path(root) / "ontology" / "concepts"
        if cdir.is_dir():
            paths = {p.stem: p.relative_to(Path(root)).as_posix() for p in sorted(cdir.rglob("*.yaml"))}
    # NO SILENT DROP. A concept file that fails to parse arrives here as an empty document, and an
    # empty document asks nothing — so the parse failure itself is reported.
    if root is not None:
        import yaml as _yaml

        for stem, rel in sorted(paths.items()):
            try:
                _yaml.safe_load((Path(root) / rel).read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                findings.append(_unreadable(rel, e))

    for stem in sorted(concepts):
        r, f = concept_sme(
            stem,
            concepts[stem] or {},
            title_of,
            members,
            paths.get(stem) or f"ontology/concepts/{stem}.yaml",
        )
        rows += r
        findings += f

    cr = change_record_sme(root, title_of)
    rows += cr["rows"]
    findings += cr["findings"]

    seen = _Counter(r["key"] for r in rows)
    for k, n in sorted(seen.items()):
        if n > 1:
            findings.append(
                sme_finding(
                    "sme-key-duplicate",
                    "medium",
                    k,
                    f"{n} catalogue rows share one origin key",
                    "A key must name one question; a ledger could file only one of them.",
                )
            )
    for r in rows:
        if not r["fileable"]:
            findings.append(
                sme_finding(
                    "sme-key-unfileable",
                    "medium",
                    r["key"],
                    "the origin key breaks the key grammar, so this question cannot be filed",
                    "Ids inside a key may use letters, digits and _ . : / - only.",
                    concept=r.get("concept"),
                    source=r.get("source"),
                )
            )
    rows.sort(key=lambda r: r["key"])
    return {
        "rows": rows,
        "findings": findings,
        "operator_items": sorted(cr["operator_items"], key=lambda x: x["key"]),
        "routed_to_data": sorted(cr["routed_to_data"], key=lambda x: x["key"]),
    }


def build(concepts: dict, datasets: dict, ont_edges: list, root=None, concept_paths=None) -> dict:
    title_of, name_of = {}, {}
    for stem, c in concepts.items():
        con = c.get("concept") or {}
        title_of[stem] = con.get("label") or con.get("name") or stem
        name_of[stem] = con.get("name") or stem

    _mt_members = measure_type_members()
    touched, edge_levels = set(), {}
    for e in ont_edges or []:
        ep = e.get("endpoints") or {}
        touched.add((ep.get("from") or {}).get("concept"))
        touched.add((ep.get("to") or {}).get("concept"))
        edge_levels[e.get("level", "?")] = edge_levels.get(e.get("level", "?"), 0) + 1

    # ── CONNECTED BY RULE ────────────────────────────────────────────────────────────────────────
    # An edge asserts THAT two concepts relate. A contract rule that binds another concept's canonical
    # key asserts WHAT GOES WRONG if you ignore the relationship — a stronger statement, and the one an
    # answering engine actually executes. Counting only edges made this metric report a concept as
    # "isolated" while eight measures were pinning it by rule, and the only way to satisfy it was to
    # restate in edges what the rules already said (2026-08-16, acme2 `perspective`). So relationships
    # expressed as rules count too, in both directions: the rule connects its subject AND its object.
    key_owner: dict[str, set[str]] = {}
    for stem, c in concepts.items():
        ck = ((c.get("concept") or {}).get("identity") or {}).get("canonical_key")
        if ck:
            key_owner.setdefault(ck, set()).add((c.get("concept") or {}).get("name") or stem)

    bound, rule_links = set(), []
    for stem, c in concepts.items():
        me = (c.get("concept") or {}).get("name") or stem
        for r in (c.get("contract") or {}).get("rules") or []:
            for col in r.get("binds") or []:
                others = key_owner.get(col, set()) - {me}
                if not others:
                    continue  # binds its own key — not a relationship
                bound.add(me)
                bound |= others
                rule_links.append(
                    {"from": me, "to": sorted(others), "via": r.get("id"), "binds": col}
                )

    findings, refuse_stubs = [], []
    conf_c = {"C": 0, "I": 0, "Q": 0}
    rule_c = {"C": 0, "P": 0, "R": 0}
    kinds_present = set()
    by_edge = by_rule = 0

    for stem, c in concepts.items():
        con = c.get("concept") or {}
        meta = c.get("metadata") or {}
        title, nm, klass = title_of[stem], name_of[stem], con.get("class")
        # A REFUSE-STUB is a concept authored precisely so the engine can say "this source has no
        # information about X" instead of inventing one: identity.kind = sme_pending, no canonical key.
        # It is SUPPOSED to be unlinked and unconfirmed, so neither is a defect — reporting them as
        # findings argues for wiring a relationship that does not exist. The open question is still
        # real, so it stays in the SME backlog below; only the FINDINGS are suppressed.
        is_refuse_stub = (con.get("identity") or {}).get("kind") == "sme_pending" and not (
            con.get("identity") or {}
        ).get("canonical_key")
        if is_refuse_stub:
            refuse_stubs.append(stem)
        mc = meta.get("confidence", "?")
        if mc in conf_c:
            conf_c[mc] += 1
        if mc in ("I", "Q") and not is_refuse_stub:
            findings.append(
                {
                    "id": f"maturity.{stem}",
                    "category": "maturity",
                    "severity": "medium" if mc == "Q" else "low",
                    "concept": stem,
                    "concept_title": title,
                    "title": f"{title} is {'needs-SME' if mc == 'Q' else 'inferred'}, not confirmed",
                    "detail": f"metadata.confidence = {mc} — machine-authored, awaiting SME confirmation.",
                }
            )

        if nm in touched:
            by_edge += 1
        elif nm in bound:
            by_rule += 1
        elif not is_refuse_stub:
            findings.append(
                {
                    "id": f"isolated.{stem}",
                    "category": "connectivity",
                    "severity": "medium",
                    "concept": stem,
                    "concept_title": title,
                    "title": f"{title} has no relationships",
                    "detail": "Neither an ontology edge nor a contract rule relates it to another "
                    "concept — it stands alone in the model.",
                }
            )

        rules = (c.get("contract") or {}).get("rules") or []
        for r in rules:
            rc = r.get("confidence", "?")
            if rc in rule_c:
                rule_c[rc] += 1
            kinds_present.add(str(r.get("kind", "")).split(".")[-1])
            if rc == "P":
                subj = r.get("subject") or r.get("id")
                findings.append(
                    {
                        "id": f"proposed.{r.get('id')}",
                        "category": "maturity",
                        "severity": "low",
                        "concept": stem,
                        "concept_title": title,
                        "title": f"Proposed rule on {title}: {subj}",
                        "detail": f"Rule {r.get('id')} is confidence P (proposed) — not SME-confirmed.",
                    }
                )

        # ONE PREDICATE PER CONDITION, shared with the SME catalogue. The finding and the question
        # used to be computed by two copies of the same test; both copies were false alarms on a
        # measure that declares its type and on a value set read from a register.
        if klass == "measure" and not measure_type_declared(c, _mt_members):
            findings.append(
                {
                    "id": f"noagg.{stem}",
                    "category": "rule-coverage",
                    "severity": "medium",
                    "concept": stem,
                    "concept_title": title,
                    "title": f"Measure {title} declares no measure type",
                    "detail": "No `concept.semantics.measure_type` that mac.MeasureType resolves, so "
                    "how it rolls up across its axes is unspecified.",
                }
            )

        if klass == "enumeration" and value_set_unresolved(c):
            v = c.get("values") or {}
            findings.append(
                {
                    "id": f"enum.{stem}",
                    "category": "completeness",
                    "severity": "medium",
                    "concept": stem,
                    "concept_title": title,
                    "title": f"{title} value set is not fully enumerated",
                    "detail": f"closure = {v.get('closure')} — the full valid-value set is not captured.",
                }
            )

    # ---- THE SME CATALOGUE. What the model asks an SME, from the concept files and the change
    # record's structured `sme` blocks. See the module docstring for the row and the key grammar.
    # THE PROTOCOL IT SERVES (operator, 2026-08-18): a contested reading is never left broken and
    # never silently guessed. A consistent view is ADOPTED, the reason is RECORDED, and the question
    # is RAISED. Raising it now means a structured ask; an owner's name in free text is a finding.
    catalogue = sme_catalogue(concepts, root, concept_paths, members=_mt_members)
    findings += catalogue["findings"]

    cols_total = sum(len(d.get("columns") or []) for d in datasets.values())
    cols_desc = sum(
        1 for d in datasets.values() for col in (d.get("columns") or []) if col.get("description")
    )

    kinds_absent = [k for k in RULE_KINDS if k not in kinds_present]
    if kinds_absent:
        findings.append(
            {
                "id": "rulekinds.absent",
                "category": "rule-coverage",
                "severity": "low",
                "concept": None,
                "concept_title": None,
                "title": f"Rule kinds never used: {', '.join(kinds_absent)}",
                "detail": "These contract-rule kinds appear on no concept — an ontology-wide coverage gap.",
            }
        )
    if edge_levels and not any(lvl in edge_levels for lvl in ("business", "federation")):
        findings.append(
            {
                "id": "edges.physicalonly",
                "category": "relationship-depth",
                "severity": "low",
                "concept": None,
                "concept_title": None,
                "title": "All edges are physical (no business / federation)",
                "detail": "Only foreign-key relationships are modelled; semantic (identity / "
                "shared_attribute) and cross-source (federation) edges are absent.",
            }
        )

    # ── ANSWERABILITY, read from the compiler rather than recomputed ──────────────────────────────
    # mac.schema.json on no_probe_guarantee: "if more is needed, the concept is INCOMPLETE (fix it,
    # don't probe)". That is a completeness test, and until 2026-08-19 every bundle answered it by
    # hand — one prose block per concept, each reciting steps its own declarations already hold, each
    # drifting silently whenever a declaration moved. The compiler now DERIVES the path and reports
    # the steps it cannot; this surfaces that verdict beside the other dimensions.
    answerable = {"derives": 0, "total": 0, "gaps": [], "exempt": [], "measured": False}
    try:
        import json as _json

        cj = Path(root or ".") / "compile.json"
        if cj.exists():
            diags = (_json.loads(cj.read_text(encoding="utf-8")) or {}).get("diagnostics") or []
            ans = [d for d in diags if d.get("source") == "check_answerability"]
            answerable["measured"] = True
            for d in ans:
                for w in d.get("witnesses") or []:
                    answerable["gaps"].append(
                        {
                            "concept": (w.get("detail") or "").split(":")[0],
                            "step": (w.get("path") or "").split(".")[-1],
                            "detail": w.get("detail"),
                        }
                    )
                m = _re.search(r"refuse-stubs: ([^.]+)", d.get("note") or "")
                if m:
                    answerable["exempt"] = [s.strip() for s in m.group(1).split(",")]
            short = {g["concept"] for g in answerable["gaps"]}
            answerable["total"] = len(concepts) - len(answerable["exempt"])
            answerable["derives"] = answerable["total"] - len(short)
            for g in answerable["gaps"]:
                findings.append(
                    {
                        "id": f"answerpath.{g['concept']}.{g['step']}",
                        "category": "answerability",
                        "severity": "high",
                        "concept": g["concept"],
                        "concept_title": g["concept"],
                        "title": f"{g['concept']}: the `{g['step']}` step of the answer path is not declared",
                        "detail": "An agent cannot reach this step without probing, and no declaration "
                        "supplies it. A no_probe_guarantee asserting otherwise is a promise "
                        "nothing keeps — supply the declaration instead.",
                    }
                )
    except Exception:
        pass

    # ── EXECUTION VALIDATION — which concepts a warehouse property actually holds to account ──────
    # mac.schema.json calls PropertiesFile "the L2 (execution-validated) evidence", and FRAMEWORK.md §8
    # makes execution validation the third rung of the trust gradient. Until 2026-08-19 a property
    # carried no link to a concept, so the evidence existed and could not be attributed: the suite
    # proved the warehouse satisfied an assumption while nothing recorded WHICH part of the model was
    # thereby validated. `validates` is that link; this counts it.
    execval = {
        "covered": 0,
        "total": len(concepts),
        "uncovered": [],
        "properties": 0,
        "measured": False,
        "run": None,
    }
    try:
        import yaml as _yaml

        acc = Path(root or ".") / "acceptance"
        claimed: set = set()
        nprop = 0
        for f in sorted(acc.glob("*.yaml")) if acc.is_dir() else []:
            doc = _yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            for pr in (doc.get("properties") or []) if isinstance(doc, dict) else []:
                nprop += 1
                for c in pr.get("validates") or []:
                    claimed.add(str(c))
        if nprop:
            execval["measured"] = True
            execval["properties"] = nprop
            # JOIN ON THE DECLARED NAME, NOT ON THE FILE STEM. `validates` carries a concept's
            # TITLE, as authored in concept.name — "OrderLine" — while `concepts` is keyed by FILE
            # STEM — "order_line". `claimed & set(concepts)` intersected two different vocabularies
            # and was therefore EMPTY BY CONSTRUCTION, for every bundle, always. Not stale, not
            # drifted: it could never have matched.
            #
            # MEASURED on a live bundle the day this was found: 267 properties claiming 22 concepts
            # produced `covered: 0, pct: 0` and 22 findings reading "<concept> has never been
            # checked against the warehouse" — while a blocker-severity property naming one of those
            # very concepts had PASSED against the warehouse hours earlier. The artifact stated the
            # opposite of the evidence beside it, legibly, next to a 100/100/100 scorecard, and no
            # gate, register or ledger knew.
            by_name = {}
            for stem, doc in concepts.items():
                nm = ((doc or {}).get("concept") or {}).get("name")
                by_name[str(nm) if nm else stem] = stem
            covered = {by_name[c] for c in claimed if c in by_name}
            # A JOIN THAT MATCHES NOTHING IS A BROKEN JOIN, NOT A SCORE OF ZERO. Every measurement
            # gate in this framework refuses an empty denominator; this projector had no such guard
            # and so reported a confident 0%. If properties make claims and NONE of them resolve to
            # a concept, the vocabularies do not line up — say so instead of grading it.
            if nprop and claimed and not covered:
                execval["measured"] = False
                execval["refused"] = (
                    f"{len(claimed)} concept name(s) claimed by {nprop} propert(ies) matched NONE "
                    f"of {len(concepts)} concepts. The join did not resolve; this is not 0% "
                    f"coverage. Claimed: {sorted(claimed)[:5]}; known: {sorted(concepts)[:5]}"
                )
                execval["covered"] = None
                execval["uncovered"] = []
            else:
                execval["covered"] = len(covered)
                execval["uncovered"] = sorted(set(concepts) - covered)
            for c in execval["uncovered"]:
                findings.append(
                    {
                        "id": f"execval.{c}",
                        "category": "execution-validation",
                        "severity": "medium",
                        "concept": c,
                        "concept_title": c,
                        "title": f"{c} has never been checked against the warehouse",
                        "detail": "No property in acceptance/ names this concept in `validates`. It may be "
                        "authored and structurally valid and still wrong about the data — "
                        "FRAMEWORK.md §8: structure is not correctness.",
                    }
                )
        # ── THE RUN, not just the suite. A property that exists and has never been executed is a
        # claim, and until this read the only place a result lived was a JSON file nobody opens and a
        # terminal nobody keeps. Written by tools/run_properties.py --json.
        runs = Path(root or ".") / "acceptance" / "property_runs.json"
        if runs.exists():
            import json as _j

            rr = (_j.loads(runs.read_text(encoding="utf-8")) or {}).get("results") or []
            tally = {"pass": 0, "fail": 0, "accepted": 0}
            for r in rr:
                st = str(r.get("status") or "").upper()
                tally["pass" if st == "PASS" else "accepted" if st == "ACCEPTED" else "fail"] += 1
            execval["run"] = dict(tally, total=len(rr))
            for r in rr:
                if str(r.get("status") or "").upper() != "FAIL":
                    continue
                findings.append(
                    {
                        "id": f"propfail.{r.get('id')}",
                        "category": "property-failure",
                        # a blocker property that FAILS is the strongest signal this dashboard carries:
                        # the warehouse contradicts an assumption the ontology's rules are written on.
                        "severity": "high" if r.get("severity") == "blocker" else "medium",
                        "concept": None,
                        "concept_title": r.get("family"),
                        "title": f"{r.get('id')} FAILED — {r.get('family')}",
                        "detail": " ".join(str(r.get("statement") or "").split())[:400],
                    }
                )
    except Exception:
        pass

    nconc = len(concepts)
    total_r = sum(rule_c.values())
    findings.sort(
        key=lambda f: (_SEV.get(f.get("severity"), 3), f.get("category"), f.get("concept") or "")
    )
    return {
        "score": {
            "maturity": {
                "concepts": conf_c,
                "rules": rule_c,
                "concept_confirmed_pct": _pct(conf_c["C"], nconc, "concept")[0],
                "rule_confirmed_pct": _pct(rule_c["C"], total_r, "rule")[0],
            },
            # `total` excludes refuse-stubs: a concept authored to be unlinked cannot be a shortfall.
            "connectivity": {
                "linked": by_edge + by_rule,
                "by_edge": by_edge,
                "by_rule": by_rule,
                "total": nconc - len(refuse_stubs),
                "refuse_stubs": sorted(refuse_stubs),
                "pct": _pct(by_edge + by_rule, nconc - len(refuse_stubs), "linkable concept")[0],
                "edges": edge_levels,
                "rule_links": len(rule_links),
            },
            "documentation": {
                "cols_described": cols_desc,
                "cols_total": cols_total,
                "pct": _pct(cols_desc, cols_total, "column")[0],
            },
            "rule_kinds": {
                "present": sorted(kinds_present),
                "absent": kinds_absent,
                "total": len(RULE_KINDS),
            },
            # UNMEASURED is not CLEAN: with no compile.json the dashboard says it does not know,
            # rather than reporting 100 % and inventing an assurance nobody computed.
            "execution_validation": (
                dict(execval, pct=_pct(execval["covered"], execval["total"], "concept")[0])
                if execval["measured"]
                else {"measured": False}
            ),
            "answerability": (
                dict(
                    answerable, pct=_pct(answerable["derives"], answerable["total"], "concept")[0]
                )
                if answerable["measured"]
                else {"measured": False}
            ),
        },
        "counts": {
            "concepts": nconc,
            "rules": total_r,
            "findings": len(findings),
            "sme_questions": len(catalogue["rows"]),
            "sme_questions_by_kind": {
                k: sum(1 for r in catalogue["rows"] if r["kind"] == k) for k in SME_KINDS
            },
            "sme_questions_by_origin": dict(sorted(_Counter(r["origin"] for r in catalogue["rows"]).items())),
            "sme_operator_items": len(catalogue["operator_items"]),
            "sme_routed_to_data": len(catalogue["routed_to_data"]),
            "sme_findings": sum(1 for f in findings if f.get("category") == SME_FINDING_CATEGORY),
        },
        "findings": findings,
        "sme_catalogue_format": SME_CATALOGUE_FORMAT,
        "sme_questions": catalogue["rows"],
        "sme_operator_items": catalogue["operator_items"],
        "sme_routed_to_data": catalogue["routed_to_data"],
        "rule_links": rule_links,
    }
