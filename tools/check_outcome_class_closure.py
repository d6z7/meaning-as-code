#!/usr/bin/env python3
"""Every outcome a bundle declares must be a member of the closed outcome-class vocabulary.

THE OUTCOME CLASSES WERE THE ONE AXIS NOTHING GOVERNED. `COMMIT · ASK · REFUSE · BLOCK` is the
grading axis the whole estate reasons in — oracles, dashboards, the console's route column — and it
was declared in prose in the integration kit's testing plane and nowhere a machine could reach.

WHAT THAT COST, MEASURED over every structurally parsed declaration on an outcome-carrying key in
the applied estate: 16.292 declarations, in TEN spellings, not four.

    COMMIT 13.957 · ASK 4.206 · REFUSE 1.347 · BLOCK 1.223 · DECLINE 1.049
    COMMIT_PENDING 247 · ENUMERATE 119 · MODEL_PROPERTY 74 · DEFER 59 · ENGINE_ERR 3

`DECLINE` is a synonym of `REFUSE` holding 1.049 declarations across 68 files, so a reader who
searches for either word sees well under half the population. A population that cannot be enumerated
cannot have a denominator — which is what this gate prints.

THE KEY NAME IS NOT ENOUGH TO KNOW THE AXIS, and this is why the carrier list lives here rather than
in the vocabulary. `oracle_class` holds THIS vocabulary in one bundle's run records and a question-
FAMILY code (`C1`…`C11`, `META`, `N`) in another bundle's dashboard — the same key, two axes. So a
carrier key is judged in a bundle only once at least one of its values is a declared term of the
vocabulary; a key whose values are all foreign to the vocabulary is a different axis wearing the same
name, and is SKIPPED and disclosed rather than reported as 96 unknown outcomes.

THE LAW IS READ, NEVER RESTATED. Membership comes from mac_vocabulary.yaml#outcome_class, whose terms
carry a `status` — `canonical` (the four), `deprecated` (a synonym, with the canonical form in `use`),
`provisional`, `non_grading`. The path is a parameter so the self-test can prove the refusal fires
without touching the framework's own vocabulary.

Offline: reads the bundle's declarations and the framework vocabulary, touches no warehouse.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mac_diag as D          # noqa: E402

NAME = "check_outcome_class_closure"
VOCAB_DEFAULT = pathlib.Path(__file__).resolve().parent.parent / "mac_vocabulary.yaml"
SUFFIXES = (".yaml", ".yml", ".json", ".mac")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv"}

# THE OUTCOME-CARRYING KEYS, from the estate census rather than from taste. Each of these was
# measured carrying at least one of the four canonical classes. Deliberately EXCLUDED are the generic
# comparison and label keys a canonical token merely passes through — `expected`, `got`, `from`, `to`,
# `disposition`, `resolver_family` — where the token is coincidental and judging it would invent
# findings out of a diff's left-hand side.
CARRIER_KEYS = (
    "outcome", "outcomes", "expected_outcome", "oracle_outcome", "route_outcome",
    "resolver_outcome", "composer_outcome", "oracle", "oracle_class", "route", "b_route",
    "decision", "acceptable_outcomes",
)

# the reject classes, named so a rejection is ATTRIBUTED rather than merely counted
UNKNOWN, CASE, DEPRECATED = "unknown-spelling", "case-variant", "deprecated-spelling"


class LawUnavailable(Exception):
    """The vocabulary could not be read. A gate with no law has not passed; it has not run."""


def outcome_law(vocab_path: pathlib.Path) -> dict:
    """{TERM: {status, use, ...}} from mac_vocabulary.yaml#outcome_class.

    Takes the PATH as a parameter, rather than reaching for the framework's own file directly, so a
    self-test can prove the refusal fires without touching the real vocabulary — the same principle
    check_measure_additivity_registry uses for the MeasureType law.
    """
    if not vocab_path.is_file():
        raise LawUnavailable(f"framework vocabulary not found at {vocab_path.name}")
    try:
        doc = yaml.safe_load(vocab_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:                                            # noqa: BLE001
        raise LawUnavailable(f"{vocab_path.name} did not parse: {exc}") from None
    block = doc.get("outcome_class") or {}
    terms = block.get("terms") or {}
    if not terms:
        raise LawUnavailable(f"{vocab_path.name}#outcome_class declares no terms — the outcome axis "
                             f"has no home, so no declaration can be classified")
    if not block.get("closed"):
        raise LawUnavailable(f"{vocab_path.name}#outcome_class is not marked closed — this gate "
                             f"enforces a CLOSED set and must not invent one")
    return {str(k): (v if isinstance(v, dict) else {}) for k, v in terms.items()}


def _files(root: pathlib.Path):
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in SUFFIXES:
            continue
        if SKIP_DIRS & set(f.parts):
            continue
        yield f


def _walk(node, key, sink):
    """Collect (key -> value) for every scalar sitting under an outcome-carrying key."""
    if isinstance(node, dict):
        for k, v in node.items():
            _walk(v, k, sink)
    elif isinstance(node, list):
        for v in node:
            _walk(v, key, sink)
    elif key in CARRIER_KEYS:
        sink.append((key, node))


def scan(root: pathlib.Path, law: dict) -> dict:
    """Enumerate every declared outcome in the bundle and classify each against the closed set."""
    declared = law.keys()
    ci = {t.upper(): t for t in declared}
    per_key: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    # (key, value) -> {file: n}, so a finding collapses its fanout instead of printing per line
    sites: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    unset = 0
    files_seen = 0
    for f in _files(root):
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
            docs = [json.loads(txt)] if f.suffix.lower() == ".json" else list(yaml.safe_load_all(txt))
        except Exception:                                               # noqa: BLE001
            continue                    # not this gate's business: the parse gates own malformed files
        found = []
        for d in docs:
            _walk(d, None, found)
        if not found:
            continue
        files_seen += 1
        for k, v in found:
            if v is None or (isinstance(v, str) and not v.strip()):
                unset += 1
                continue
            if not isinstance(v, str):
                continue
            t = v.strip()
            per_key[k][t] += 1
            sites[(k, t)][str(f.relative_to(root))] += 1

    # AXIS CONFIRMATION, PER KEY, PER BUNDLE. A carrier key is this vocabulary's only once one of its
    # values is a declared term. Otherwise it is a different axis wearing the same name.
    judged, skipped = {}, {}
    for k, vc in per_key.items():
        if any(v.upper() in ci for v in vc):
            judged[k] = vc
        else:
            skipped[k] = vc

    findings = []
    counts = collections.Counter()
    total = 0
    for k, vc in judged.items():
        for v, n in vc.items():
            total += n
            if v in declared:
                st = str(law[v].get("status") or "")
                counts[st or "unstated"] += n
                if st == "deprecated":
                    findings.append({
                        "cls": DEPRECATED, "key": k, "value": v, "n": n,
                        "use": str(law[v].get("use") or ""),
                        "files": dict(sites[(k, v)]),
                    })
            elif v.upper() in ci:
                findings.append({
                    "cls": CASE, "key": k, "value": v, "n": n, "use": ci[v.upper()],
                    "files": dict(sites[(k, v)]),
                })
            else:
                findings.append({
                    "cls": UNKNOWN, "key": k, "value": v, "n": n, "use": "",
                    "files": dict(sites[(k, v)]),
                })
    return {"findings": findings, "total": total, "by_status": dict(counts),
            "judged": {k: dict(v) for k, v in judged.items()},
            "skipped": {k: dict(v) for k, v in skipped.items()},
            "unset": unset, "files": files_seen}


def _census_phrase(by_status: dict) -> str:
    order = ("canonical", "provisional", "non_grading", "deprecated", "unstated")
    bits = [f"{by_status[s]} {s}" for s in order if by_status.get(s)]
    return " · ".join(bits) or "none classified"


def report(res: dict, root: pathlib.Path) -> int:
    findings, total = res["findings"], res["total"]
    # ZERO IS NOT A SCORE. A bundle with no outcome corpus has not been judged clean by this gate; it
    # has not been measured at all, and must never render as a pass.
    if not total:
        return D.refuse_empty(NAME, root, unit="outcome declaration")

    for cls in (UNKNOWN, CASE, DEPRECATED):
        for x in sorted((f for f in findings if f["cls"] == cls), key=lambda y: -y["n"]):
            print(f"  [ERROR] {cls}: {x['value']!r} on `{x['key']}` — {x['n']} declaration(s)")
            if cls == DEPRECATED:
                print(f"          declared, but deprecated in favour of {x['use']!r}. NOT migrated "
                      f"by this gate; it is reported so the debt is countable.")
            elif cls == CASE:
                print(f"          differs from the declared term {x['use']!r} by case alone, so an "
                      f"exact search for the class does not find it")
            else:
                print("          not a member of the closed outcome-class vocabulary")
            wit = sorted(x["files"].items(), key=lambda kv: -kv[1])
            for fn, n in wit[:6]:
                print(f"            {fn}  ×{n}")
            if len(wit) > 6:
                print(f"            … and {len(wit) - 6} more file(s)")

    if res["skipped"]:
        print("\n  DISCLOSURE — carrier key(s) skipped as a DIFFERENT axis (no value of theirs is a")
        print("  declared outcome term, so judging them would invent findings):")
        for k, vc in res["skipped"].items():
            shown = ", ".join(sorted(vc)[:8])
            print(f"    `{k}` — {sum(vc.values())} value(s): {shown}{' …' if len(vc) > 8 else ''}")

    keys = len(res["judged"])
    census = _census_phrase(res["by_status"])
    unset = f", {res['unset']} unset" if res["unset"] else ""
    if findings:
        bad = sum(f["n"] for f in findings)
        classes = sorted({f["cls"] for f in findings})
        print(f"\nFAIL: {NAME} — {bad} of {total} outcome declaration(s) are not a canonical member "
              f"of the closed set, over {res['files']} file(s) on {keys} outcome-carrying key(s)"
              f"{unset} [{census}] — reject class(es): {', '.join(classes)}")
        return 1
    print(f"\nPASS: {NAME} — {total} outcome declaration(s) over {res['files']} file(s) on {keys} "
          f"outcome-carrying key(s){unset}, every one a member of the closed set [{census}]")
    return 0


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# SELF-TEST — a clean bundle that must pass, an empty one that must REFUSE, and one mutant per reject
# class, each attributed by its CLASS NAME in the output.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# Written as its own harness rather than through mac_project.selftest_discovery, whose discovery
# property asserts on the CONCEPT denominator ("found no concept under"). This gate's population is
# an outcome corpus, not a concept plane, so borrowing that harness would have measured the wrong
# denominator and scored fixtures it never judged — the exact defect that harness exists to catch.
#
# The fixture's outcome values are READ FROM THE VOCABULARY, never typed, so the corpus cannot drift
# from the law it exercises.

def _fixture(root: pathlib.Path, law: dict, extra: dict | None = None) -> None:
    """Seed an acceptance corpus whose outcomes are the vocabulary's own canonical terms."""
    canon = sorted(t for t, m in law.items() if m.get("status") == "canonical")
    d = root / "acceptance"
    d.mkdir(parents=True, exist_ok=True)
    corpus = {"questions": [{"id": f"Q{i}", "expected_outcome": t, "route": t}
                            for i, t in enumerate(canon, 1)]}
    if extra:
        corpus["questions"].append(extra)
    (d / "corpus.yaml").write_text(yaml.safe_dump(corpus, sort_keys=False), encoding="utf-8")


def _deprecated_term(law: dict) -> str:
    for t, m in law.items():
        if m.get("status") == "deprecated":
            return t
    raise RuntimeError("the vocabulary declares no deprecated term to mutate with")


def _self_test() -> int:
    import subprocess
    import tempfile

    law = outcome_law(VOCAB_DEFAULT)
    canon = sorted(t for t, m in law.items() if m.get("status") == "canonical")
    dep = _deprecated_term(law)

    def run(r):
        p = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()), str(r)],
                           capture_output=True, text=True, timeout=300)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    # (name, seed, expected_exit, marker that must appear, why)
    cases = []
    cases.append(("clean", lambda r: _fixture(r, law), 0, None,
                  "a corpus of nothing but canonical terms is a real measurement, not a refusal"))
    cases.append(("empty-corpus", lambda r: (r / "acceptance").mkdir(parents=True, exist_ok=True),
                  D.EMPTY_EXIT, D.empty_mark("outcome declaration"),
                  "a bundle with no outcome corpus is COULD-NOT-RUN — zero is not a score"))
    # one mutant per reject class
    mutants = (
        (UNKNOWN,
         lambda r: _fixture(r, law, {"id": "QX", "expected_outcome": "DENIED"}),
         "a spelling outside the closed set — the class the whole gate exists for"),
        (CASE,
         lambda r: _fixture(r, law, {"id": "QX", "expected_outcome": canon[0].lower()}),
         "a declared term differing by case alone, which an exact search for the class misses"),
        (DEPRECATED,
         lambda r: _fixture(r, law, {"id": "QX", "expected_outcome": dep}),
         "a declared-but-deprecated synonym — reported as countable debt, never migrated here"),
    )

    bad = 0
    clean_out = ""
    with tempfile.TemporaryDirectory() as tmp:
        for i, (name, seed, want_rc, marker, why) in enumerate(cases):
            r = pathlib.Path(tmp) / f"case_{i}"
            r.mkdir()
            seed(r)
            rc, out = run(r)
            ok = rc == want_rc and (marker is None or marker in out)
            if name == "clean":
                clean_out = out
                # a class marker on the clean run would attribute nothing later
                ok = ok and not any(c in out for c in (UNKNOWN, CASE, DEPRECATED))
            if "Traceback (most recent call last)" in out:
                ok = False
            bad += 0 if ok else 1
            print(f"  {'✓' if ok else '✗'} {name:<18} exit {rc:<2} expected {want_rc} — {why}")

        for i, (cls, seed, why) in enumerate(mutants):
            r = pathlib.Path(tmp) / f"mutant_{i}"
            r.mkdir()
            seed(r)
            rc, out = run(r)
            rejected = rc == 1
            attributed = cls in out
            discriminates = cls not in clean_out
            ok = rejected and attributed and discriminates
            bad += 0 if ok else 1
            if ok:
                detail = f"rejected as its own class (exit 1, {cls!r})"
            else:
                bits = [f"exit {rc}"]
                if not rejected:
                    bits.append("NOT a finding (only exit 1 rejects here)")
                if not attributed:
                    bits.append(f"class name {cls!r} absent — rejection unattributed")
                if not discriminates:
                    bits.append(f"class name {cls!r} also fires on the clean fixture")
                detail = ", ".join(bits)
            print(f"  {'✓' if ok else '✗'} {('MUTANT ' + cls):<18} {detail} — {why}")

    n = len(cases) + len(mutants)
    if bad:
        print(f"FAIL: {NAME} self-test — {bad} of {n} assertion(s) failed "
              f"({len(cases)} corpus fixture(s) + {len(mutants)} rule mutant(s))")
        return 1
    print(f"PASS: {NAME} self-test — {n}/{n}: {len(cases)} corpus fixture(s) "
          f"(clean passes, an empty corpus refuses on exit {D.EMPTY_EXIT}) + "
          f"{len(mutants)} mutant(s) of its own rule, each rejected as its own class "
          f"({', '.join(c for c, _, _ in mutants)}), read from "
          f"{VOCAB_DEFAULT.name}#outcome_class ({len(law)} declared term(s))")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--vocabulary", default=str(VOCAB_DEFAULT),
                    help="path to mac_vocabulary.yaml (the closed outcome_class law)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return D.EMPTY_EXIT
    try:
        law = outcome_law(pathlib.Path(a.vocabulary))
    except LawUnavailable as exc:
        print(f"could not run: {exc}", file=sys.stderr)
        return D.EMPTY_EXIT

    res = scan(root, law)
    if a.json:
        print(json.dumps({**res, "measured_nothing": not res["total"]}, indent=1, ensure_ascii=False))
        return D.EMPTY_EXIT if not res["total"] else (1 if res["findings"] else 0)
    print(f"── outcome-class closure gate ── the law lives in {pathlib.Path(a.vocabulary).name}"
          f"#outcome_class ({len(law)} declared term(s)) ── {root} ──\n")
    return report(res, root)


if __name__ == "__main__":
    raise SystemExit(main())
