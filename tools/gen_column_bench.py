#!/usr/bin/env python3
"""
gen_column_bench.py — render reference_manual/column_bench.html: every configuration possibility of
the column standard, and the effect each one has.

THE THIRD GENERATOR OF THE REFERENCE MANUAL, and it composes the other two's sources rather than
adding a source of its own. gen_schema_shapes.py renders STRUCTURE from mac.schema.json (which keys
exist); gen_vocabulary_terms.py renders MEANING from mac_vocabulary.yaml (what their values mean);
this one renders EFFECT — what a question does differently because a key was set.

FOUR INPUTS, EACH ALREADY THE HOME OF WHAT IT SUPPLIES. Nothing is retyped here:

  column_specification.md    the "Every key" table -> required, default, legal values, decides.
                             The manual owns the shape, so the page reads it rather than restating it.
                             A registry entry that ALSO declares one of those four is a second home
                             and --check fails on it.
  column_effects.yaml        plane, status, reader, effect, frontier notes, and the bench scenarios.
                             The genuinely NEW facts: which plane a key lands on, which outcome
                             classes it can produce, and whether anything reads it.
  mac_vocabulary.yaml        every closed term list, and measure_type's 10-cell additivity matrix.
                             The measure panel computes its outcomes FROM that matrix, so the page
                             cannot drift from the fold law it illustrates.
  <bundle>/data/profiles/    the measured cardinalities. `{ZipCode.distinct}` in the bench resolves
                             here, so a number on the page is a measurement with a timestamp. An
                             unresolvable placeholder is a hard error, never a blank.

WHY THE NUMBERS COME FROM A BUNDLE AND THE PAGE STILL SHIPS IN THE FRAMEWORK. The reference manual
already argues the column standard from contoso's measurements — 104 990 customers, 29 193 postcodes
held by one person each. This page renders the same evidence interactively, and it names the profile
and its measured_at beside every panel, which the prose tables do not.

Usage:
  python3 tools/gen_column_bench.py --bundle ../mac-ontology-contoso
  python3 tools/gen_column_bench.py --bundle ../mac-ontology-contoso --check   # drift + parity gate
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
VOCAB = ROOT / "mac_vocabulary.yaml"
EFFECTS = ROOT / "reference_manual" / "column_effects.yaml"
SPEC_MD = ROOT / "reference_manual" / "column_specification.md"
TEMPLATE = ROOT / "tools" / "column_bench_template.html"
OUT = ROOT / "reference_manual" / "column_bench.html"

#: The four canonical grading terms plus the two planes that are NOT gradings of an answer. A load
#: refusal and a red gate happen before any question exists, so they must not wear an outcome_class
#: chip — mac.outcome_class records what the engine DID about a question.
NON_ANSWER_OUTCOMES = {"LOAD_ERROR", "GATE_RED"}

PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?:\.([a-z_]+))?\}")


class Fail(SystemExit):
    def __init__(self, msg: str) -> None:
        super().__init__(f"gen_column_bench: {msg}")


# --------------------------------------------------------------------------- inputs


def load_vocabulary() -> dict:
    """Every closed list the page needs, in the two shapes mac_vocabulary.yaml uses.

    `terms:` (a map of name -> string or map) and `members:` (a map of name -> map with attributes).
    Both appear in the file; reading only one is how a generator silently renders an empty list,
    which is what measure_type would have done here.
    """
    raw = yaml.safe_load(VOCAB.read_text(encoding="utf-8")) or {}
    out: dict[str, dict] = {}
    for ns, spec in raw.items():
        if not isinstance(spec, dict) or spec.get("kind") not in ("vocabulary", "value_domain"):
            continue
        body = spec.get("terms") or spec.get("members") or {}
        terms = {}
        if isinstance(body, dict):
            for name, val in body.items():
                if isinstance(val, dict):
                    desc = val.get("description") or val.get("definition") or ""
                    terms[name] = {
                        "description": " ".join(str(desc).split()),
                        **{k: v for k, v in val.items() if k not in ("description", "definition")},
                    }
                else:
                    terms[name] = {"description": " ".join(str(val).split())}
        out[ns] = {
            "closed": bool(spec.get("closed")),
            "description": " ".join(str(spec.get("description") or "").split()),
            "terms": terms,
        }
    if not out.get("measure_type", {}).get("terms"):
        raise Fail("measure_type rendered empty — the value_domain `members:` shape was not read")
    return out


def parse_key_table() -> dict[str, dict]:
    """`## Every key` in column_specification.md -> the shape facts, keyed by key name.

    The manual owns required/default/legal/decides. Parsing them keeps ONE home for the table an
    author actually reads, at the cost of a regex — and a regex that finds zero rows fails loudly
    below rather than rendering a page with no keys in it.
    """
    text = SPEC_MD.read_text(encoding="utf-8")
    start = text.find("## Every key")
    if start < 0:
        raise Fail(f"'## Every key' not found in {SPEC_MD.name}")
    rows: dict[str, dict] = {}
    for line in text[start:].splitlines():
        if line.startswith("##") and "Every key" not in line:
            break
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in ("key", "---") or set(cells[0]) <= {"-", ":"}:
            continue
        key = cells[0].strip("`*")
        rows[key] = {
            "required": _plain(cells[1]),
            "default": _plain(cells[2]),
            "legal": _plain(cells[3]),
            "decides": _plain(cells[4]),
        }
    if len(rows) < 20:
        raise Fail(f"parsed only {len(rows)} rows from the 'Every key' table — the shape changed")
    return rows


def _plain(cell: str) -> str:
    """Markdown cell -> the text a chip shows. Keeps `·` as the separator the manual chose."""
    return re.sub(r"\s+", " ", cell.replace("`", "").replace("**", "")).strip()


def load_profiles(bundle: pathlib.Path, relations: set[str]) -> dict[str, dict]:
    """The measured plane, per relation named by the bench. Missing is fatal: a bench that invented
    its cardinalities would be arguing the standard from figures nobody measured."""
    out: dict[str, dict] = {}
    for rel in sorted(relations):
        path = bundle / "data" / "profiles" / f"{rel}.yaml"
        if not path.exists():
            raise Fail(f"no profile for relation {rel!r} at {path} — measure it or drop it from the bench")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        prof = raw.get("profile") or {}
        out[rel] = {
            "relation": raw.get("relation") or rel,
            "rows": prof.get("rows"),
            "measured_at": prof.get("measured_at"),
            "engine": prof.get("engine"),
            "method": prof.get("method"),
            "columns": {c["name"]: c for c in (raw.get("columns") or []) if c.get("name")},
        }
    return out


# --------------------------------------------------------------------------- substitution


def substitute(obj, prof: dict, where: str):
    """Resolve `{rows}` and `{Column.field}` against ONE relation's profile, everywhere in a subtree.

    An unresolved placeholder raises. The alternative — leaving the braces in, or emptying them — is
    how a page ends up stating a number that is a remembered figure rather than a measurement.
    """
    if isinstance(obj, dict):
        return {k: substitute(v, prof, f"{where}.{k}") for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, prof, f"{where}[{i}]") for i, v in enumerate(obj)]
    if not isinstance(obj, str):
        return obj

    def repl(m: re.Match) -> str:
        name, field = m.group(1), m.group(2)
        if name == "rows" and not field:
            return f"{prof['rows']:,}".replace(",", " ")
        col = prof["columns"].get(name)
        if col is None:
            raise Fail(f"{where}: no column {name!r} in the profile of {prof['relation']}")
        if not field:
            raise Fail(f"{where}: {{{name}}} needs a field — distinct, nulls, min or max")
        if field not in col:
            raise Fail(f"{where}: {prof['relation']}.{name} has no measured {field!r}")
        val = col[field]
        return f"{val:,}".replace(",", " ") if isinstance(val, int) else str(val)

    return PLACEHOLDER.sub(repl, obj)


# --------------------------------------------------------------------------- gates


def check_parity(effects: dict, table: dict[str, dict], vocab: dict) -> list[str]:
    """Every parity a stale page would hide. Returns findings; empty means PASS over 29 keys."""
    findings: list[str] = []
    keys = {k["key"]: k for k in effects["keys"]}
    authored = {name: k for name, k in keys.items() if k.get("block") != "measured"}

    for name in sorted(set(table) - set(keys)):
        findings.append(f"column_specification.md declares {name!r} and column_effects.yaml does not")
    for name in sorted(set(authored) - set(table)):
        findings.append(f"column_effects.yaml declares {name!r} and the manual's key table does not")

    for name, k in keys.items():
        dupes = [f for f in ("required", "default", "legal", "decides") if f in k and name in table]
        if dupes:
            findings.append(f"{name}: {', '.join(dupes)} declared in BOTH the manual's table and the registry")
        for oc in k.get("outcomes") or []:
            if oc not in (vocab.get("outcome_class", {}).get("terms") or {}):
                findings.append(f"{name}: outcome {oc!r} is not a mac.outcome_class term")
        for plane in k.get("plane") or []:
            if plane not in ("load", "check", "answer"):
                findings.append(f"{name}: unknown plane {plane!r}")
        if k.get("status") not in ("enforced", "designed", "measured"):
            findings.append(f"{name}: unknown status {k.get('status')!r}")
        if k.get("status") == "enforced" and not (k.get("reader") or "").strip():
            findings.append(f"{name}: status enforced with no reader named")
        legal = k.get("legal") or table.get(name, {}).get("legal") or ""
        for ref in re.findall(r"mac\.([A-Za-z_]+)", str(legal)):
            if ref not in vocab:
                findings.append(f"{name}: legal values cite mac.{ref}, which mac_vocabulary.yaml does not define")

    allowed = set(vocab.get("outcome_class", {}).get("terms") or {}) | NON_ANSWER_OUTCOMES
    for concept in effects["bench"]:
        for col in concept["columns"]:
            for t in col.get("toggles") or []:
                if t["key"] not in keys:
                    findings.append(f"bench {concept['concept']}.{col['column']}: toggles {t['key']!r}, not a declared key")
            for q in col.get("questions") or []:
                for case in q.get("cases") or []:
                    if case.get("outcome") not in allowed:
                        findings.append(
                            f"bench {concept['concept']}.{col['column']} / {q['ask']!r}: "
                            f"outcome {case.get('outcome')!r} is neither a mac.outcome_class term nor a plane outcome"
                        )
                    for wk in (case.get("when") or {}):
                        if wk not in keys:
                            findings.append(f"bench {concept['concept']}.{col['column']}: when names {wk!r}, not a declared key")
    return findings


# --------------------------------------------------------------------------- build


def build(bundle: pathlib.Path) -> tuple[dict, list[str]]:
    vocab = load_vocabulary()
    effects = yaml.safe_load(EFFECTS.read_text(encoding="utf-8")) or {}
    table = parse_key_table()
    findings = check_parity(effects, table, vocab)

    relations = {c["relation"] for c in effects["bench"]}
    profiles = load_profiles(bundle, relations)

    bench = []
    for concept in effects["bench"]:
        prof = profiles[concept["relation"]]
        entry = substitute({k: v for k, v in concept.items() if k != "columns"}, prof, concept["concept"])
        entry["profile"] = {k: prof[k] for k in ("relation", "rows", "measured_at", "engine", "method")}
        entry["columns"] = [
            substitute(col, prof, f"{concept['concept']}.{col['column']}") for col in concept["columns"]
        ]
        bench.append(entry)

    keys = []
    for k in effects["keys"]:
        merged = dict(table.get(k["key"], {}))
        merged.update(k)
        keys.append(merged)

    counts = {s: sum(1 for k in keys if k["status"] == s) for s in ("enforced", "designed", "measured")}
    data = {
        "generated_by": "tools/gen_column_bench.py",
        "metadata": effects.get("metadata", {}),
        "modes": effects["modes"],
        "keys": keys,
        "bench": bench,
        "vocabulary": vocab,
        "counts": {**counts, "total": len(keys)},
        "bundle": bundle.name,
    }
    return data, findings


def render(data: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if "/*__DATA__*/" not in tpl:
        raise Fail(f"{TEMPLATE.name} has no /*__DATA__*/ slot")
    payload = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False)
    return tpl.replace("/*__DATA__*/", payload)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True, help="an applied ontology with data/profiles/")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true", help="gate: parity + staleness, write nothing")
    args = ap.parse_args()

    bundle = pathlib.Path(args.bundle).expanduser().resolve()
    if not bundle.exists():
        raise Fail(f"--bundle {bundle} does not exist")

    data, findings = build(bundle)
    html = render(data)
    out = pathlib.Path(args.out)

    if args.check:
        stale = (not out.exists()) or out.read_text(encoding="utf-8") != html
        if stale:
            findings.append(f"{out.name} is stale — regenerate with tools/gen_column_bench.py")
        verdict = "FAIL" if findings else "PASS"
        print(f"check_column_bench: {verdict} — {len(data['keys'])} keys, "
              f"{sum(len(c['columns']) for c in data['bench'])} bench columns, "
              f"{len(findings)} findings")
        for f in findings:
            print(f"  - {f}")
        return 1 if findings else 0

    if findings:
        print("gen_column_bench: parity findings (page written anyway; --check gates them)")
        for f in findings:
            print(f"  - {f}")
    out.write_text(html, encoding="utf-8")
    print(f"gen_column_bench: wrote {out} — {len(data['keys'])} keys "
          f"({data['counts']['enforced']} enforced / {data['counts']['designed']} designed / "
          f"{data['counts']['measured']} measured), "
          f"{sum(len(c['columns']) for c in data['bench'])} bench columns, {len(html):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
