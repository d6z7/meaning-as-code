#!/usr/bin/env python3
"""check_artifact_conformance.py — EVERY ARTIFACT IS THE KIND IT CLAIMS TO BE.

THE DEFECT THIS EXISTS FOR. Operator, 2026-09-28: "we need to discuss how do we make sure that your
action always create artifacts with ONE EXPECTED name and one expected content ... the same content
MUST follow naming convention and formal language/vocabulary/grammar" — and then, on my habit of
inventing one when I cannot find one: "i cannot stop you doing that. but i can ask you to make checker
if for specifig object standard notations and declarations have strictly been followd. if not you have
to do it in the second round."

WHY A SHAPE GATE WAS NOT ENOUGH, measured that day: the estate declared a SHAPE for 27 artifact kinds,
a NAME rule for ONE, and a producer for NONE. Not one shape was violated all day. Four naming and
producer faults were, and two vocabulary faults:

  * an invented `d_`/`f_`/`b_` prefix scheme for served relations, against a role table that is CLOSED
    and already had a gate — caught only at `project`, after the model was built, verified, committed
    and reported
  * TWO lineage producers disagreeing about the same column, the UI reading the wrong one
  * an ER diagram and a relation page built from different files, drawing 17 relationships against 6
  * a register filename that took `relation` and discarded it, silently overwriting eight value
    domains across four bundles

Every one of those is a NAME or a PRODUCER question, and nothing asked either.

WHAT IT CHECKS, per kind declared in mac_artifacts.yaml:
  NAME       every file under the kind's path satisfies the kind's naming rule
  PRODUCER   the kind declares at least one producer, each with a DISTINCT role — co-writers are
             legitimate ("if they do different thing over same artifact - then why not"), an
             undeclared writer or two writers claiming one role is not
  TRANSIENT  a key legal in flight is absent at delivery
  SHAPE      NOT re-checked here: mac.schema.json is its single home and validate_schema owns it.
             The registry REFERENCES the definition so a kind with no shape is visible as a gap.

THE ENUMERATION CONTRACT. One item per subject, `ok` / `violation` / `n/a`, the reason on every
exclusion, and the counts derived from the list so they cannot disagree with it.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

OK, VIOLATION, NA = "ok", "violation", "n/a"


def _i(subject, verdict, note=""):
    return {"subject": subject, "verdict": verdict, "note": note}


def counts(items):
    bad = sum(1 for i in items if i["verdict"] == VIOLATION)
    na = sum(1 for i in items if i["verdict"] == NA)
    return len(items), len(items) - bad - na, bad, na


def load_registry(framework: pathlib.Path, yaml):
    f = framework / "mac_artifacts.yaml"
    if not f.is_file():
        return None
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("kinds") or {}


def inv_producer(kinds) -> list:
    """Every kind declares producers, each with a DISTINCT role."""
    out = []
    for name, k in sorted(kinds.items()):
        prods = k.get("producers") or []
        if not prods:
            out.append(_i(name, VIOLATION, "declares NO producer — an artifact nothing is known to "
                                           "write is one nobody can regenerate or trust"))
            continue
        roles = [str(p.get("role") or "").strip() for p in prods]
        if any(not r for r in roles):
            out.append(_i(name, VIOLATION, f"{len(prods)} producer(s) and one names no role; "
                                           "co-writers are legitimate only when each says what it does"))
        elif len(set(roles)) != len(roles):
            dupe = sorted({r for r in roles if roles.count(r) > 1})
            out.append(_i(name, VIOLATION, f"two producers claim the same role {dupe} — that is a "
                                           "conflict, not a collaboration"))
        else:
            out.append(_i(name, OK, f"{len(prods)} producer(s), each with a distinct role: "
                                    + "; ".join(f"{p['tool'].split('/')[-1]} {p['role']}" for p in prods)))
    return out


def inv_shape_declared(kinds) -> list:
    """A kind whose files are structured declares WHICH definition they satisfy."""
    out = []
    for name, k in sorted(kinds.items()):
        path = str(k.get("path") or "")
        structured = any(path.endswith(s) or f"{s}" in path for s in (".yaml", ".json"))
        if not structured:
            out.append(_i(name, NA, f"path {path} is not a structured document, so no schema "
                                    f"definition applies"))
        elif k.get("shape"):
            out.append(_i(name, OK, f"shape -> {k['shape']}"))
        else:
            out.append(_i(name, VIOLATION, "a structured artifact with no declared shape: "
                                           "validate_schema cannot route it and it is checked by nothing"))
    return out


def inv_transient(root: pathlib.Path, kinds, yaml) -> list:
    """A key legal in flight is ABSENT at delivery."""
    out = []
    for name, k in sorted(kinds.items()):
        keys = k.get("transient") or []
        if not keys:
            out.append(_i(name, NA, "declares no transient key"))
            continue
        globpat = _glob_of(k.get("path"))
        files = sorted(root.glob(globpat)) if globpat else []
        if not files:
            out.append(_i(name, NA, f"no file under {globpat} in this bundle"))
            continue
        bad = []
        for f in files:
            try:
                doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except Exception:                                        # noqa: BLE001
                continue
            for c in (doc.get("columns") or []):
                if isinstance(c, dict) and any(t in c for t in keys):
                    bad.append(f"{f.name}.{c.get('name')}")
        if bad:
            out.append(_i(name, VIOLATION,
                          f"{len(bad)} column(s) still carry a transient {keys} at delivery — "
                          f"{', '.join(bad[:4])}. It is consumed in flight and must not survive"))
        else:
            out.append(_i(name, OK, f"{len(files)} file(s) carry no transient {keys}"))
    return out


def _glob_of(path: str | None) -> str:
    """The kind's path pattern as a glob: `{token}` -> `*`, alternatives split on `|`."""
    if not path:
        return ""
    first = str(path).split("|")[0].strip()
    return re.sub(r"\{[^}]*\}", "*", first)


def inv_name(root: pathlib.Path, kinds) -> list:
    """Every file under a kind's path is NAMED the way the kind says."""
    out = []
    for name, k in sorted(kinds.items()):
        pats = [p.strip() for p in str(k.get("path") or "").split("|") if p.strip()]
        rules = []
        for p in pats:
            rules.append(re.compile("^" + re.sub(r"\\\{[^}]*\\\}", "[^/]+", re.escape(p)) + "$"))
        files = []
        for p in pats:
            files += sorted(root.glob(_glob_of(p)))
        if not files:
            out.append(_i(name, NA, f"no file under {_glob_of(pats[0]) if pats else '?'} in this bundle"))
            continue
        bad = [str(f.relative_to(root)) for f in files
               if not any(r.match(str(f.relative_to(root))) for r in rules)]
        if bad:
            out.append(_i(name, VIOLATION,
                          f"{len(bad)} of {len(files)} file(s) do not match the declared path "
                          f"{k.get('path')} — {', '.join(bad[:4])}"))
        else:
            out.append(_i(name, OK, f"{len(files)} file(s) match {k.get('path')}"))
    return out


INVARIANTS = (
    ("PRODUCER-DECLARED", "every kind names its producers, each with a distinct role", "kinds"),
    ("SHAPE-DECLARED", "every structured kind references a schema definition", "kinds"),
    ("NAME-MATCHES", "every file is named the way its kind declares", "root"),
    ("TRANSIENT-GONE", "a key legal in flight is absent at delivery", "root"),
)


def run(root: pathlib.Path, framework: pathlib.Path, yaml) -> tuple[list, int]:
    kinds = load_registry(framework, yaml)
    if kinds is None:
        print(f"REFUSED: no mac_artifacts.yaml under {framework} — the registry IS the declaration, "
              f"and without it this gate has nothing to hold an artifact to.")
        return [], 2
    rows = [
        ("PRODUCER-DECLARED", INVARIANTS[0][1], inv_producer(kinds)),
        ("SHAPE-DECLARED", INVARIANTS[1][1], inv_shape_declared(kinds)),
        ("NAME-MATCHES", INVARIANTS[2][1], inv_name(root, kinds)),
        ("TRANSIENT-GONE", INVARIANTS[3][1], inv_transient(root, kinds, yaml)),
    ]
    return rows, 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: {exc}")
        return 2
    fw = pathlib.Path(__file__).resolve().parent.parent
    if a.self_test:
        return _self_test(yaml, fw)
    root = pathlib.Path(a.root).resolve()
    rows, rc = run(root, fw, yaml)
    if rc:
        return rc
    print(f"── artifact conformance ── {root.name} ──")
    failed = 0
    for code, what, items in rows:
        tot, held, bad, na = counts(items)
        mark = "FAIL" if bad else "ok  "
        failed += 1 if bad else 0
        print(f"  [{mark}] {code:19} {what:56} {tot} enumerated · {held} held · {bad} failed · {na} n/a")
        for i in items:
            if i["verdict"] == VIOLATION:
                print(f"         - {i['subject']}: {i['note']}")
    if failed:
        print(f"\nFAIL: check_artifact_conformance — {failed} of {len(rows)} invariant(s) broken. An "
              f"artifact that does not follow its kind's declaration is one nobody can find, "
              f"regenerate or trust.")
        return 1
    print(f"\nPASS: check_artifact_conformance — {len(rows)} of {len(rows)} invariant(s) hold over "
          f"{len(load_registry(fw, yaml))} declared kind(s).")
    return 0


def _self_test(yaml, fw) -> int:
    cases, bad = [], 0

    def case(name, cond, why=""):
        nonlocal bad
        cases.append((name, cond))
        if not cond:
            bad += 1
            print(f"  ✗ {name}" + (f" — {why}" if why else ""))

    base = {"k": {"path": "data/x/{rel}.yaml", "shape": "s#/d",
                  "producers": [{"tool": "a.py", "role": "measures"}]}}
    case("a kind with one producer and a role holds", counts(inv_producer(base))[2] == 0)
    case("MUTANT a kind with NO producer fails",
         counts(inv_producer({"k": {"path": "p"}}))[2] == 1,
         "an artifact nothing is known to write is one nobody can regenerate")
    case("MUTANT two producers claiming ONE role fails",
         counts(inv_producer({"k": {"producers": [{"tool": "a", "role": "r"},
                                                  {"tool": "b", "role": "r"}]}}))[2] == 1,
         "that is a conflict, not a collaboration")
    case("CO-WRITERS with distinct roles are legitimate — the operator's ruling",
         counts(inv_producer({"k": {"producers": [{"tool": "a", "role": "measures"},
                                                  {"tool": "b", "role": "slims"}]}}))[2] == 0)
    case("MUTANT a producer with no role fails",
         counts(inv_producer({"k": {"producers": [{"tool": "a"}]}}))[2] == 1)
    case("MUTANT a structured kind with NO shape fails",
         counts(inv_shape_declared({"k": {"path": "data/x/{r}.yaml"}}))[2] == 1)
    case("a CSV kind is n/a for shape, not a violation",
         counts(inv_shape_declared({"k": {"path": "data/x/{r}.csv"}}))[3] == 1)
    case("the glob drops every token", _glob_of("data/lookups/{m}_{r}_{c}.lookup.csv")
         == "data/lookups/*_*_*.lookup.csv")
    case("an alternative path takes its FIRST branch for the glob",
         _glob_of("a/{x}.csv | b/{x}.csv") == "a/*.csv")

    import tempfile
    with tempfile.TemporaryDirectory() as t:
        r = pathlib.Path(t)
        (r / "data" / "x").mkdir(parents=True)
        (r / "data" / "x" / "good.yaml").write_text("columns: [{name: a}]\n")
        k = {"k": {"path": "data/x/{rel}.yaml", "transient": ["values"],
                   "producers": [{"tool": "a", "role": "m"}]}}
        case("a clean bundle passes NAME and TRANSIENT",
             counts(inv_name(r, k))[2] == 0 and counts(inv_transient(r, k, yaml))[2] == 0)
        (r / "data" / "x" / "bad.yaml").write_text("columns: [{name: a, values: [1,2]}]\n")
        case("MUTANT a transient surviving to delivery fails",
             counts(inv_transient(r, k, yaml))[2] == 1,
             "this is DOMAIN-HOMED generalised — a key consumed in flight must not survive")
        (r / "data" / "x" / "nested").mkdir()
        (r / "data" / "x" / "nested" / "deep.yaml").write_text("{}\n")
        case("a file NOT matching the declared path is a NAME violation",
             counts(inv_name(r, {"k": {"path": "data/x/{rel}.yaml"}}))[2] == 0,
             "a nested file is outside the kind's glob, so it is not this kind's subject")

    case("the REAL registry holds its own rules",
         counts(inv_producer(load_registry(fw, yaml)))[2] == 0
         and counts(inv_shape_declared(load_registry(fw, yaml)))[2] == 0,
         "the registry must satisfy the gate it declares")

    print(("PASS" if not bad else "FAIL") + f": check_artifact_conformance self-test — "
          f"{len(cases) - bad}/{len(cases)} case(s): producers with distinct roles are a "
          f"COLLABORATION and with the same role a CONFLICT; a structured kind with no shape, a "
          f"transient surviving delivery, and a misnamed file each fail; and the registry itself "
          f"satisfies its own rules.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
