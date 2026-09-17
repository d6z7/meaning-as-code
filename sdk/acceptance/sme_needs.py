"""sdk.acceptance.sme_needs — the test oracles that wait on a subject-matter expert.

Reads ``acceptance/oracle/**/*.yaml`` — the fields ``needs_sme`` (flag), ``needs_sme_question``
(text) and ``needs_sme_class`` (label) — and emits ``acceptance/sme_needs.json``, format
``mac.sme-needs/1``: ``{needs: [...], findings: [...], counts: {...}}``.

WHY IT LIVES ON THE ACCEPTANCE SIDE. The oracles are the question corpus, not the model; the
register projector (sdk.project.ontology_quality) projects the model. The two outputs share one row
shape (``ontology_quality.sme_row``) and are unioned into one catalogue at read time
(sdk.project.sme_questions), so a reader sees ONE list with an origin tag per row.

WHAT MAKES AN ORACLE A CANDIDATE
    needs_sme: true  + text     a candidate
    text, no flag at all        a candidate, and a finding: the flag is missing
    needs_sme: true, no text    a FINDING only. Nobody wrote the question; inventing its text is
                                the defect the catalogue exists to remove.
    needs_sme: false + text     a FINDING only: the text says "ask", the flag says "don't"
    a flag that is not a bool   a FINDING; the oracle is read as unflagged

GROUPING. Many oracles wait on the same answer (one question asked of every test in a family).
Members group by ``needs_sme_class``, else by their normalised text. A group of one is a plain row
keyed ``oracle:<question>#needs_sme``; a larger group is one row keyed ``oracle-group:...`` listing
its member keys. A group key is never filed — its members are. The group's text is its most
frequent member text, and ``variants`` counts the other texts; a class whose members disagree is a
finding ("one class, N texts").

WHAT IT DOES NOT DO. It does not judge whether a flag is stale: only the ledger knows whether the
question was answered, and that judgement is made where the two meet (the read-time join).

CLI:
  python3 -m sdk.acceptance.sme_needs <bundle>            # writes acceptance/sme_needs.json
  python3 -m sdk.acceptance.sme_needs <bundle> --print    # also prints it
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from sdk.acceptance import bundleio as _io
from sdk.project import ontology_quality as _oq

FORMAT = "mac.sme-needs/1"
OUTPUT = "acceptance/sme_needs.json"


def _norm(text: str) -> str:
    """Whitespace- and case-insensitive text identity. Punctuation stays: "is it X?" and "it is X."
    are different sentences."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _slug(label: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", label.strip()).strip("-") or "unnamed"
    # A slug can merge two labels that differ only in punctuation; the hash keeps them apart.
    return slug if slug == label.strip() else f"{slug}~{hashlib.sha1(label.encode()).hexdigest()[:6]}"


def build(bundle) -> dict:
    """Collect needs-SME candidates from a bundle's oracles. Never raises on a bad file: an
    unreadable oracle is a finding naming the file, so the list never shrinks in silence."""
    bundle = Path(bundle)
    odir = bundle / "acceptance" / "oracle"
    out = {"format": FORMAT, "needs": [], "findings": [], "counts": {}}
    if not odir.is_dir():
        out["state"] = "absent"
        out["counts"] = {"oracle_files": 0, "with_sme_fields": 0, "candidates": 0, "rows": 0, "groups": 0}
        return out
    out["state"] = "present"
    findings = out["findings"]

    def finding(code, severity, subject, title, detail, rel):
        findings.append(
            _oq.sme_finding(code, severity, subject, title, detail, source={"path": rel, "pointer": "needs_sme"})
        )

    files = sorted(odir.rglob("*.yaml"))
    members, with_fields = [], 0
    for f in files:
        rel = f.relative_to(bundle).as_posix()
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001 — reported, never swallowed
            findings.append(_oq._unreadable(rel, e))
            continue
        if doc is None:
            continue
        if not isinstance(doc, dict):
            findings.append(_oq._unreadable(rel, f"the oracle is a {type(doc).__name__}, not a mapping"))
            continue
        flag = doc.get("needs_sme")
        text = doc.get("needs_sme_question")
        klass = doc.get("needs_sme_class")
        has_text = isinstance(text, str) and bool(text.strip())
        if flag is None and not has_text and klass is None:
            continue
        with_fields += 1
        q = doc.get("question") if isinstance(doc.get("question"), dict) else {}
        qid = str(q.get("id") or f.stem)
        key = f"oracle:{_oq.key_fragment(qid)}#needs_sme"
        if flag is not None and not isinstance(flag, bool):
            finding(
                "oracle-sme-flag-malformed",
                "low",
                qid,
                "needs_sme is not true or false; the oracle is read as unflagged",
                f"needs_sme = {flag!r}.",
                rel,
            )
            flag = None
        if flag is True and not has_text:
            finding(
                "oracle-sme-flag-no-text",
                "low",
                qid,
                "flagged needs-SME, but no question is written",
                "Nothing is invented in its place; write `needs_sme_question`.",
                rel,
            )
            continue
        if flag is False:
            if has_text:
                finding(
                    "oracle-sme-flag-false-with-text",
                    "low",
                    qid,
                    "needs_sme is false, yet a needs-SME question is written",
                    "Either the question is settled (remove the text) or it is not (set the flag).",
                    rel,
                )
            continue
        if not has_text:
            continue  # a class label alone asks nothing
        if flag is None:
            finding(
                "oracle-sme-flag-missing",
                "low",
                qid,
                "a needs-SME question is written, but the flag is not set",
                "Listed as a candidate; set `needs_sme: true` so the oracle says what its text says.",
                rel,
            )
        members.append(
            {
                "key": key,
                "qid": qid,
                "text": text.strip(),
                "class": klass.strip() if isinstance(klass, str) and klass.strip() else None,
                "rel": rel,
            }
        )

    # ONE KEY, ONE QUESTION. Two oracle files carrying the same question id produce the same key, and a
    # ledger can file only one of them — the register half reports the same defect as sme-key-duplicate.
    for k, n in sorted(Counter(m["key"] for m in members).items()):
        if n > 1:
            finding(
                "sme-key-duplicate",
                "medium",
                k,
                f"{n} oracles share one origin key",
                "A key must name one question; a ledger could file only one of them. Give each oracle "
                "its own `question.id`.",
                "acceptance/oracle",
            )

    groups: dict[tuple, list] = {}
    for m in members:
        gk = ("class", m["class"]) if m["class"] else ("text", _norm(m["text"]))
        groups.setdefault(gk, []).append(m)

    rows, n_groups = [], 0
    for (by, label), ms in sorted(groups.items()):
        ms.sort(key=lambda m: m["key"])
        norm_texts = Counter(_norm(m["text"]) for m in ms)
        top_norm = sorted(norm_texts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        raw_top = Counter(m["text"] for m in ms if _norm(m["text"]) == top_norm)
        text = sorted(raw_top.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        if by == "class" and len(norm_texts) > 1:
            finding(
                "oracle-sme-class-texts",
                "low",
                label,
                f"one class, {len(norm_texts)} texts",
                f"{len(ms)} oracles share needs_sme_class {label!r} but word the question "
                f"{len(norm_texts)} ways; the group shows the most frequent wording.",
                "acceptance/oracle",
            )
        if len(ms) == 1:
            m = ms[0]
            rows.append(
                _oq.sme_row(
                    key=m["key"],
                    origin="oracle",
                    kind="question",
                    text=m["text"],
                    source={"path": m["rel"], "pointer": "needs_sme_question"},
                    questions=[m["qid"]],
                    sme_class=m["class"],
                    variants=0,
                )
            )
            continue
        n_groups += 1
        gkey = (
            f"oracle-group:class:{_slug(label)}"
            if by == "class"
            else f"oracle-group:text:{hashlib.sha1(label.encode()).hexdigest()[:12]}"
        )
        rows.append(
            _oq.sme_row(
                key=gkey,
                origin="oracle",
                kind="question",
                text=text,
                members=[m["key"] for m in ms],
                source={"path": "acceptance/oracle", "pointer": "needs_sme_question"},
                questions=[m["qid"] for m in ms],
                sme_class=label if by == "class" else None,
                variants=len(norm_texts) - 1,
                grouped_by=by,
            )
        )
    for r in rows:
        for mk in r["members"] or [r["key"]]:
            if not _oq.ORIGIN_KEY_RE.match(mk):
                finding(
                    "sme-key-unfileable",
                    "medium",
                    mk,
                    "the origin key breaks the key grammar, so this question cannot be filed",
                    "Question ids inside a key may use letters, digits and _ . : / - only.",
                    "acceptance/oracle",
                )
    out["needs"] = sorted(rows, key=lambda r: r["key"])
    out["counts"] = {
        "oracle_files": len(files),
        "with_sme_fields": with_fields,
        "candidates": len(members),
        "rows": len(rows),
        "groups": n_groups,
        "findings": len(findings),
    }
    return out


def write(bundle, doc: dict | None = None) -> Path:
    """Build (unless given) and write acceptance/sme_needs.json atomically. Deterministic: no
    timestamp, sorted keys, so re-projecting an unchanged corpus leaves the file byte-identical."""
    bundle = Path(bundle)
    doc = build(bundle) if doc is None else doc
    target = bundle / OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    _io.atomic_write(target, json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("bundle", nargs="?")
    ap.add_argument("--bundle", dest="bundle_opt")
    ap.add_argument("--print", action="store_true", help="also print the collected needs as JSON")
    a = ap.parse_args(argv)
    root = Path(a.bundle_opt or a.bundle or "")
    if not (a.bundle_opt or a.bundle) or not root.is_dir():
        print("sme_needs: give a bundle directory", file=sys.stderr)
        return 2
    doc = build(root)
    path = write(root, doc)
    c = doc["counts"]
    print(
        f"sme_needs: {c['candidates']} candidate oracle(s) of {c['oracle_files']} oracle file(s) "
        f"-> {c['rows']} row(s), {c['groups']} group(s), {len(doc['findings'])} finding(s); wrote {path}",
        file=sys.stderr,
    )
    if a.print:
        print(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
