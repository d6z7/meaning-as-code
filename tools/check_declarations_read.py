#!/usr/bin/env python3
"""check_declarations_read.py — every declaration the framework admits has a READER in the runtime, or it is named.

Operator, 2026-09-29: "make something READ all these properties and grammar. can you make sure this
happens." A declaration nobody reads is prose with a colon after it (the runtime's own ColumnSpec
doctrine), and the estate has the receipts: `attribute` lived for two days after its retirement
because six surfaces restated it and none read the vocabulary; the platform's `test_declared_but_
unread` found 19 model fields read by nothing in the change meant to cure that. That gate is the
RUNTIME-SIDE half (a model field is read somewhere). This is the FRAMEWORK-SIDE half: start from what
the STANDARD declares — the schema's keys on a concept, an edge, a register, a transform; the
vocabularies' terms; the common rules; the query grammar's operations and declaration states; the
canon — and ask, for each, where the runtime reads it.

THE METHOD IS A TRACE OF THE SOURCE, not a claim. For a schema key the reader is a dict lookup or an
attribute access by that name in mac-platform/packages/mac-runtime/src; for a term, a rule id, an
operation or a canon it is the literal in the source. That is crude (a common name like `note` reads
as READ wherever any `.note` exists) and it errs toward READ, so an UNREAD here is a hard finding: no
line of the runtime spells the name. The reader named beside a READ is the FIRST line found; a person
judges whether it acts on the value.

Exit 0 when nothing is UNREAD; 1 when something is (the list is the work); 2 when the runtime or the
declarations cannot be found. `--json` for a machine; `--family` to narrow.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNTIME = ROOT.parent / "mac-platform" / "packages" / "mac-runtime" / "src" / "mac_runtime"
FILES = ("ConceptFile", "EdgesFile", "ValueRegisterFile", "RulesFile", "TransformFile")
#: WHO IS EXPECTED TO READ WHAT. A concept's keys, the concept vocabularies, the common rules, the
#: grammar and the canon are read at ANSWER TIME — by the runtime. A gate vocabulary (diagnostic
#: codes, the data-plane gate, DQ status, credential modes, test status) is read at FRAMEWORK TIME —
#: by mac's own tools and sdk. An UNREAD counts only against the side expected to read it; the other
#: side's reader is still shown, because a declaration the wrong side reads is a different finding.
FRAMEWORK_SIDE = {"diagnostic_code", "data_plane_gate", "dq_status", "credential_mode", "test_status",
                  "test_kind", "connector", "transform.driven_by", "relation.column.role",
                  "concept.column.ruling"}  # ruling TERMS are read as flags (schema keys), not as literals
FRAMEWORK_FILES = ("TransformFile",)
#: keys that are METADATA about the declaration rather than a declaration the runtime acts on
META_KEYS = {"metadata", "governance", "version", "schema_version", "status", "owner", "provenance",
             "last_reviewed", "change_log", "generated_by", "observed", "source", "label", "definition",
             "doc", "description", "note", "notes", "purpose", "x-", "$comment", "why", "examples",
             "measured_at", "measured_by", "date", "by", "change", "change_type",
             # FOR PEOPLE, NOT THE RUNTIME (ruled 2026-09-29 with the v0.5 retirement): a member's meaning, a
             # closure's why, a change's rationale, an approval status, an open question's priority and
             # cross-references, a lifecycle's phases and boundary — read by the SME and the projector.
             "meaning", "closure_why", "rationale", "approval_status", "priority", "cross_references", "boundary",
             "phases", "profiled_via", "lifecycle", "enforced_by",
             # FRAMEWORK-SIDE by design: evidence pointers and edge planning are what gates read
             "verified_by", "blocked_by", "becomes_an_edge_when", "business_relation_minted_as", "measured_reference",
             "reference_id", "planned_edges"}
#: acceptance-side terms of a runtime vocabulary, and the one authoring-side common rule
FRAMEWORK_TERMS = {"outcome_class.COMMIT_PENDING", "outcome_class.ENUMERATE", "outcome_class.MODEL_PROPERTY",
                   "outcome_class.DEFER", "outcome_class.ENGINE_ERR", "mac.authoring.reference_markup"}


# ── the declarations ──────────────────────────────────────────────────────────────────────────
NODE_TEXT: dict[str, str] = {}   # declaration path -> the node's own description/$comment (its provenance)


def _walk(schema: dict, defs: dict, path: str, out: list, seen: set) -> None:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        if (name, path) in seen:
            return
        seen.add((name, path))
        return _walk(defs.get(name, {}), defs, path, out, seen)
    for branch in ("oneOf", "anyOf", "allOf"):
        for alt in schema.get(branch) or []:
            _walk(alt, defs, path, out, seen)
    props = schema.get("properties") or {}
    for k, v in props.items():
        p = f"{path}.{k}" if path else k
        out.append(p)
        if isinstance(v, dict):
            NODE_TEXT[p] = " ".join(str(v.get(x, "")) for x in ("description", "$comment", "title"))
        _walk(v, defs, p, out, seen)
    ap = schema.get("additionalProperties")
    if isinstance(ap, dict):
        _walk(ap, defs, f"{path}.*", out, seen)
    items = schema.get("items")
    if isinstance(items, dict):
        _walk(items, defs, f"{path}[]", out, seen)


def schema_keys(schema: dict, which: tuple[str, ...]) -> dict[str, list[str]]:
    defs = schema.get("$defs") or {}
    out: dict[str, list[str]] = {}
    for f in which:
        paths: list[str] = []
        _walk(defs.get(f, {}), defs, "", paths, set())
        out[f] = sorted(set(paths))
    return out


def vocabulary_terms(v: dict) -> dict[str, list[str]]:
    out = {}
    for ns, blk in v.items():
        if not isinstance(blk, dict):
            continue
        terms = blk.get("terms") or blk.get("members")
        if isinstance(terms, dict):
            out[ns] = [t for t, body in terms.items()
                       if not (isinstance(body, dict) and str(body.get("status", "")).lower() in ("retired", "deprecated"))]
        elif isinstance(terms, list):
            out[ns] = [str(t) for t in terms]
    return out


# ── the trace ─────────────────────────────────────────────────────────────────────────────────
def load_runtime(runtime: pathlib.Path, label: str = "runtime") -> list[tuple[str, list[str]]]:
    files = []
    for p in sorted(runtime.rglob("*.py")):
        if "__pycache__" in p.parts or p.name.startswith("test_") or p.name in ("check_declarations_read.py",):
            continue
        files.append((f"{label}:{p.relative_to(runtime).as_posix()}", p.read_text(encoding="utf-8", errors="replace").splitlines()))
    return files


def find(files, patterns: list[re.Pattern]) -> str | None:
    for rel, lines in files:
        for i, ln in enumerate(lines, 1):
            s = ln.split("#", 1)[0]
            for rx in patterns:
                if rx.search(s):
                    return f"{rel}:{i}"
    return None


def key_readers(name: str) -> list[re.Pattern]:
    esc = re.escape(name)
    return [re.compile(rf"""["']{esc}["']"""), re.compile(rf"\.{esc}\b")]


def literal_readers(name: str) -> list[re.Pattern]:
    esc = re.escape(name)
    return [re.compile(rf"(?<![\w.]){esc}(?![\w])")]


def audit(runtime: pathlib.Path, family: str | None = None) -> dict:
    files = load_runtime(runtime, "runtime")
    fw_files = load_runtime(ROOT / "tools", "mac/tools") + load_runtime(ROOT / "sdk", "mac/sdk")
    schema = json.loads((ROOT / "mac.schema.json").read_text(encoding="utf-8"))
    vocab = yaml.safe_load((ROOT / "mac_vocabulary.yaml").read_text(encoding="utf-8")) or {}
    rules = yaml.safe_load((ROOT / "mac_rules.yaml").read_text(encoding="utf-8")) or {}
    grammar = yaml.safe_load((ROOT / "grammar" / "query_grammar.yaml").read_text(encoding="utf-8")) or {}
    report: dict[str, list[dict]] = {}

    def want(f: str) -> bool:
        return family is None or f == family

    # 1. schema keys, per file kind — the leaf key name is what a reader spells
    for fk, paths in schema_keys(schema, FILES).items():
        if not want("schema"):
            break
        rows = []
        side = fw_files if fk in FRAMEWORK_FILES else files
        for p in paths:
            leaf = p.replace("[]", "").rsplit(".", 1)[-1]
            if leaf in ("*", "") or leaf in META_KEYS or leaf.startswith("x-"):
                continue
            hit = find(side, key_readers(leaf))
            other = None if hit else find(fw_files if side is files else files, key_readers(leaf))
            rows.append({"family": "schema", "kind": fk, "declaration": p, "key": leaf, "reader": hit, "other_side": other})
        report[f"schema:{fk}"] = rows
    # 2. vocabulary terms
    if want("vocabulary"):
        for ns, terms in vocabulary_terms(vocab).items():
            if ns == "canon":
                continue  # audited below, by the canon's own family
            rows = []
            for t in terms:
                side = fw_files if (ns in FRAMEWORK_SIDE or f"{ns}.{t}" in FRAMEWORK_TERMS) else files
                pats = literal_readers(t) if len(t) > 2 else [re.compile(rf"""["']{re.escape(t)}["']""")]
                hit = find(side, pats)
                other = None if hit else find(fw_files if side is files else files, pats)
                rows.append({"family": "vocabulary", "kind": ns, "declaration": f"{ns}.{t}", "key": t, "reader": hit, "other_side": other})
            report[f"vocabulary:{ns}"] = rows
    # 3. common rules
    if want("rules"):
        rows = []
        for r in rules.get("rules") or []:
            rid = str(r.get("id"))
            fam = rid.rsplit(".", 1)[0]
            side = fw_files if rid in FRAMEWORK_TERMS else files
            hit = find(side, literal_readers(rid)) or find(side, literal_readers(fam))
            rows.append({"family": "rules", "kind": "mac_rules.yaml", "declaration": rid, "key": rid, "reader": hit})
        report["rules:mac_rules.yaml"] = rows
    # 4. the query grammar: operations and declaration states
    if want("grammar"):
        for section in ("operations", "declaration_states", "projection", "not_expressible"):
            blk = grammar.get(section)
            rows = []
            if section == "declaration_states":
                # a state's reader is the refusal code its effect names (`refuse no_join_path`) or, for a
                # capability, the word the runtime spells for it (countable, foldable, plannable, binds)
                for x in blk or []:
                    if not isinstance(x, dict):
                        continue
                    eff = str(x.get("effect", ""))
                    m = re.search(r"refuse\s+([a-z_]+)", eff)
                    key = m.group(1) if m else (re.match(r"([a-z]+)", eff).group(1) if re.match(r"([a-z]+)", eff) else eff[:20])
                    hit = find(files, literal_readers(key))
                    rows.append({"family": "grammar", "kind": section, "declaration": f"{section}: {x.get('state')} -> {eff[:60]}", "key": key, "reader": hit})
            else:
                names = list(blk.keys()) if isinstance(blk, dict) else [str(x.get("id") or x.get("name") or x) if isinstance(x, dict) else str(x) for x in (blk or [])]
                for n in names:
                    hit = find(files, key_readers(n) + literal_readers(n))
                    rows.append({"family": "grammar", "kind": section, "declaration": f"{section}.{n}", "key": n, "reader": hit})
            report[f"grammar:{section}"] = rows
    # 5. the canon
    if want("canon"):
        rows = []
        for t in (vocabulary_terms(vocab).get("canon") or []):
            hit = find(files, literal_readers(t))
            rows.append({"family": "canon", "kind": "mac_vocabulary.yaml#canon", "declaration": f"mac.canon.{t}", "key": t, "reader": hit})
        report["canon"] = rows
    return report


# ── provenance: where an unread declaration came from, and which grammar it belongs to ────────
import subprocess

VERSION_RX = re.compile(r"\b(?:v)?(0\.(?:[1-9]\d?)(?:\.\d+)?)\b")
NEW_GRAMMAR_FLOOR = (0, 1, 14)     # the nine artifacts + the column standard: 0.1.14 .. 0.1.16
OLD_MARK = re.compile(r"\b(legacy|retired|superseded|deprecated|no longer|pre-0\.1|v0\.[45]\b)", re.I)


def _first_commit(needle: str, path: str) -> tuple[str, str, str]:
    """(sha, date, subject) of the commit that first introduced `needle` into `path`, or blanks."""
    try:
        out = subprocess.run(["git", "log", "--reverse", "--date=short", "--format=%h\t%ad\t%s", "-S", needle, "--", path],
                             cwd=ROOT, capture_output=True, text=True, timeout=60).stdout.strip().splitlines()
    except (subprocess.SubprocessError, OSError):
        return "", "", ""
    if not out:
        return "", "", ""
    sha, date, subj = (out[0].split("\t") + ["", "", ""])[:3]
    return sha, date, subj


INITIAL_RELEASE = "2026-06-29"   # the v0.5 content model landed whole on this day


def _era(family: str, markers: list[str], text: str, date: str) -> str:
    """WHICH GRAMMAR a declaration belongs to, by ORIGIN — not by a date floor.

    The estate has had four grammars: the v0.5 CONTENT MODEL of the initial release (attributes,
    instances, individual_kpis, lifecycle states, members definitions, multilingual aliases —
    2026-06-29); the COMMON RULES of 2026-08-19 (mac_rules.yaml, the laws every bundle answers
    under); the QUERY GRAMMAR of 2026-09-23/24 (what a question can and cannot express); and the
    COLUMN STANDARD of 0.1.14..0.1.16 (2026-09-26..29). The canon spans all of them: declared in
    the initial release, extended since, mostly never implemented. A rule or a grammar clause with
    no reader is NOT old — it is the current law unread; a v0.5 key with no reader is the old
    content model still in the schema."""
    if OLD_MARK.search(text or ""):
        return "1 RETIRED/LEGACY — the schema says so"
    if family == "rules":
        return "3 COMMON RULES (current grammar, 2026-08-19) — unread"
    if family == "grammar":
        return "4 QUERY GRAMMAR (current grammar, 2026-09-23) — unread"
    if family == "canon":
        return "5 CANON (current grammar; declared, not implemented)"
    vers = []
    for m in markers:
        try:
            vers.append(tuple(int(x) for x in m.split(".")))
        except ValueError:
            pass
    if vers and max(vers) >= NEW_GRAMMAR_FLOOR or (date and date >= "2026-09-26"):
        return "6 COLUMN STANDARD (new grammar, 0.1.14+)"
    if date == INITIAL_RELEASE:
        # after the 2026-09-29 retirement, what remains from the initial release is CURRENT grammar
        # that has always lacked a reader (the fold law's own terms; a grounding's snapshot rule)
        return "2 INITIAL RELEASE, STILL CURRENT — unread"
    return "7 MID-ERA (0.1.6..0.1.13, field-anchoring / two-plane)"


def provenance(report: dict) -> list[dict]:
    rows = []
    owning = {"schema": "mac.schema.json", "vocabulary": "mac_vocabulary.yaml", "rules": "mac_rules.yaml",
              "grammar": "grammar/query_grammar.yaml", "canon": "mac_vocabulary.yaml"}
    for sec, items in report.items():
        for r in items:
            if r["reader"]:
                continue
            fam = r["family"]
            text = NODE_TEXT.get(r["declaration"], "") if fam == "schema" else ""
            needle = r["key"] if fam != "grammar" else r["key"]
            sha, date, subj = _first_commit(f'"{needle}"' if fam == "schema" else needle, owning[fam])
            markers = VERSION_RX.findall(text)
            rows.append({**r, "markers": sorted(set(markers)), "first_commit": sha, "first_date": date,
                         "first_subject": subj[:70], "era": _era(fam, markers, text, date),
                         "note": (text[:140] + "…") if len(text) > 140 else text})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provenance", action="store_true",
                    help="for every UNREAD declaration: its version marker, first commit, and era (old grammar / new grammar / retired)")
    ap.add_argument("--runtime", default=str(RUNTIME))
    ap.add_argument("--family", choices=("schema", "vocabulary", "rules", "grammar", "canon"))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-read", action="store_true", help="also list what IS read, with the first reader")
    a = ap.parse_args(argv)
    runtime = pathlib.Path(a.runtime)
    if not runtime.is_dir():
        print(f"could not run: no runtime at {runtime}")
        return 2
    report = audit(runtime, a.family)
    if a.provenance:
        rows = provenance(report)
        if a.json:
            print(json.dumps(rows, indent=1))
            return 0
        by_era: dict[str, list[dict]] = {}
        for r in rows:
            by_era.setdefault(r["era"], []).append(r)
        for era, rs in sorted(by_era.items()):
            print(f"\n== {era}: {len(rs)}")
            for r in sorted(rs, key=lambda x: (x["family"], x["first_date"], x["declaration"])):
                side = " (gates only)" if r.get("other_side") else " (nobody)"
                print(f"  {r['family']:<10} {r['declaration'][:58]:<58} {r['first_date'] or '—':<10} {(','.join(r['markers']) or '—'):<12}{side}  {r['first_subject'][:50]}")
        return 0
    if a.json:
        print(json.dumps(report, indent=1))
        return 0
    total = unread_total = 0
    for section, rows in report.items():
        if not rows:
            continue
        unread = [r for r in rows if not r["reader"]]
        total += len(rows); unread_total += len(unread)
        print(f"{section:<44} {len(rows) - len(unread):>3} read · {len(unread):>3} UNREAD")
        for r in unread:
            print(f"    UNREAD  {r['declaration']}" + (f"   (read only by {r['other_side']})" if r.get("other_side") else ""))
        if a.list_read:
            for r in rows:
                if r["reader"]:
                    print(f"    read    {r['declaration']:<60} {r['reader']}")
    print()
    if unread_total:
        print(f"FAIL: check_declarations_read — {unread_total} of {total} declaration(s) have NO reader in the runtime "
              f"({runtime.parent.parent.name}); a declaration nobody reads is prose with a colon after it")
        return 1
    print(f"PASS: check_declarations_read — {total} of {total} declaration(s) are spelled by a reader in the runtime")
    return 0


if __name__ == "__main__":
    sys.exit(main())
