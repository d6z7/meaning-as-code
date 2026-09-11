#!/usr/bin/env python3
"""MAC012 — an `x-` extension key is prohibited, and this is what makes the prohibition real.

OPERATOR, after having to say it more than once:
  "i have ruled them out - but agents like you are keeping bringing them in over and over again"
  "they are not easily verifiable. they are weak poing in the chain and we need better solution for
   them ... even if it means that if you want to have them then you have to design algebra and
   grammar how you want to enforce them and you are only allowed to move on if you have proof that
   this enforcement is implemented"
  "a check that does not block is not enforcement"

So this file IS the proof, and it exits non-zero. Ruling it out in prose is what failed: `x-grain`
was declared on 2026-08-18 and had already been READ by the collapse fragment since 08-16.

── WHY THE EXTENSION IS THE DEFECT, not merely untidy ────────────────────────────────────────────
MAC closes every structural plane and validates it. An `x-` key is BY CONSTRUCTION outside that, so
nothing checks it — and the thing it held was the grain, the single most consequential fact about a
relation. Measured the day it was retired, with the core schema untouched around it:

    v_fpl_kpi          declared 0 multi-row (VERIFIED 2026-08-16)  ->  11.689.530 multi-row
    v_fpl_tm_kpi       declared 0 multi-row, 0 divergent           ->  176.279 multi-row (99,96 %)
    fpl_ob_reach_kpi   declared 0 ambiguous                        ->  0. HOLDS.
    v_fpl_kpi_current  declared 15.483.849 cells                   ->  15.483.965 (+116). HOLDS.

Two of four false — and WHICH two is the interesting half. Both survivors are views that ENFORCE the
key: fpl_ob_reach_kpi withholds ambiguous cells, and v_fpl_kpi_current collapses to one row per cell,
so its key is true by construction. The two that rotted are the pass-through facts, where the
declaration was the only thing standing between the reader and a doubled number.

So the argument is not that anyone was careless. The field was unreachable by every gate in the
system, so being wrong cost nothing and stayed invisible. An extension is not a small schema, it is
an UNCHECKED one.

── THE THREE PREDICATES (C6) ─────────────────────────────────────────────────────────────────────
Every `x-` key is an error. When it also DUPLICATES a core field, the message says which one, so the
finding carries its own fix rather than a rule number. Duplication is mechanical, not a judgement:

    SAME SUBJECT        both attach to the same node (the same relation, the same column)
    SAME VALUE SHAPE    both hold the same kind of value (a list of column names, a scalar, a date)
    OVERLAPPING DOMAIN  drawn from the same closed set with a non-empty intersection — for a column
                        list, the relation's own columns

x-grain.cell_key met all three against `grounding.sources[].key` and against `grounding.grain`, and
the duplicate DISAGREED with the core it duplicated: 4 columns in the ontology, 7 in the extension,
"SEVEN" in the concept prose. Three numbers for one fact is what N places for one fact buys you.

── WHY THIS GATE IS NOW THE ONLY VOICE ON `x-` (the contradiction it replaces) ───────────────────
Until this revision the framework carried TWO OPPOSITE POLICIES on one construct, and the second one
was the one bundles actually heard:

  * THIS gate (MAC012) said prohibited — and was not wired into `mac_compile.py` at all, neither as a
    native phase nor as a wrapped gate, so it never ran on any bundle the compiler judged.
  * `mac_checks_structure.check_undeclared_extensions` (MAC009) said "undeclared debt, not license"
    and handed back the remedy DECLARE IT in `mac.project.yaml#profile`.
  * CONFORMANCE.md §2 taught the namespace as "the ONLY legal way to add a key" across ten sites,
    including a promotion path ("invent under x-, prove it, promote it").

MEASURED before the fix, on a 15-site example bundle: the compiler emitted THREE diagnostics under TWO
codes about the same fifteen keys — one MAC002 (the schema rejecting them, since v0.1.14 closed the
`^x-` hatch in 58 places), and two MAC009 saying declare them. Two of the three pointed at a remedy the
third had already made impossible. MAC012 was silent.

MAC009 is now WITHDRAWN (CONFORMANCE.md §5.1), not re-pointed. Re-pointing would have carried its
remedy — "declare it" — under the prohibition's code, which is the contradiction wearing a new number.
Its subject was a strict SUBSET of this gate's (it read schema-routed files only; this walks every YAML
in the bundle), so the withdrawal loses no coverage. A bundle carrying an `x-` key now receives exactly
ONE diagnostic about it, and that diagnostic says it is prohibited.

── THE GATE CONTRACT ────────────────────────────────────────────────────────────────────────────
Usage:  python3 tools/check_extension_keys.py <bundle-root>
        python3 tools/check_extension_keys.py --self-test
Exit:   0 = PASS ; 1 = FAIL (one or more `x-` keys) ; 2 = SETUP failure (bad usage, unreadable root) —
        by this toolchain's convention exit 2 means "the gate did not judge the bundle", which
        mac_compile.py maps to a WARNING rather than an error. Never returned for a bundle defect.
Output: exactly one ``PASS:``/``FAIL:`` line (the last line), for exit 0 and 1. Exit 2 prints neither —
        a gate that did not judge must not emit a verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

CODE = "MAC012"

# The core homes an extension most often reinvents. Named so a finding can point AT the replacement
# instead of only away from the offence.
CORE = {
    "cell_key":      "TableFile.identity_evidence.key (measured) / grounding.sources[].key (bound)",
    "natural_key":   "TableFile.identity_evidence.key",
    "grain":         "TableFile.identity_evidence + grounding.grain",
    "key":           "grounding.sources[].key",
    "columns":       "TableFile.columns[]",
    "profile":       "TableFile.profile / columns[].profile",
    "distinct":      "columns[].profile.distinct",
    "nulls":         "columns[].profile.nulls",
    "determined_by": "columns[].profile.determined_by",
    "role":          "columns[].role",
    "measured_at":   "TableFile.profile.measured_at",
    "watermark":     "TableFile.identity_evidence.source_watermark",
}

SKIP_DIRS = {".git", "node_modules", ".venv", ".harvest_cache", "dist", "build", "__pycache__"}


def de(n, dp: int = 0) -> str:
    """de-DE grouping, so this gate's counts read like every other number in the estate."""
    s = f"{n:,.{dp}f}"
    return s.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")


def _hits(node, path=""):
    """Every `x-`-prefixed key anywhere in a document, with the path that reaches it."""
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}.{k}" if path else str(k)
            if isinstance(k, str) and k.startswith("x-"):
                yield here, k, v
            yield from _hits(v, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _hits(v, f"{path}[{i}]")


def duplicates(key: str, value) -> list[str]:
    """Which core field this extension is standing in for. Mechanical: name, then value shape."""
    out = []
    leaf = key[2:].split(".")[-1].lower()
    for name, home in CORE.items():
        if name in leaf or leaf in name:
            out.append(home)
    if not out and isinstance(value, dict):
        for sub in value:
            for name, home in CORE.items():
                if isinstance(sub, str) and (name in sub.lower() or sub.lower() in name):
                    out.append(f"{home}   (via `{key}.{sub}`)")
    return sorted(set(out))


# ── the reject classes ────────────────────────────────────────────────────────────────────────────
# Every one of them is the SAME verdict — prohibited — and a DIFFERENT next action. A gate that emits
# one undifferentiated refusal for four situations makes the operator do the classification, and the
# classification is the only part of this that needs judgement.
R_MANIFEST  = "declared-in-manifest"
R_DUPLICATE = "duplicates-core"
R_SCHEMA    = "private-sub-schema"
R_GAP       = "no-core-equivalent"

MANIFEST = "mac.project.yaml"


def classify(rel: str, key: str, value, dups: list[str]) -> str:
    """Which of the four, in precedence order. Precedence is by REMEDY, not by shape: the most
    specific available instruction wins, so a key that both duplicates core and holds a block is
    reported against the core field it duplicates — that is the sentence that ends the argument."""
    if os.path.basename(rel) == MANIFEST:
        return R_MANIFEST
    if dups:
        return R_DUPLICATE
    if isinstance(value, (dict, list)):
        return R_SCHEMA
    return R_GAP


# The remedy per class. Single-homed here so the gate, its self-test and CONFORMANCE.md §2 cannot
# drift into three wordings of one rule — which is the defect (MAC003) this toolchain exists to name.
REMEDY = {
    R_MANIFEST: [
        "DECLARING IS NOT A DEFENCE. This key sits in the manifest, in the extension `profile` that",
        "CONFORMANCE.md §2 used to offer as the way to legitimise an `x-` key. That construct is",
        "WITHDRAWN and the diagnostic that rewarded it (MAC009, undeclared-extension) is retired with",
        "it. A declaration never made the key checkable; it only bought silence. Delete the profile",
        "block along with the keys it names.",
    ],
    R_DUPLICATE: [
        "REMOVE IT AND USE THE CORE FIELD NAMED ABOVE. This is not a missing feature — MAC already",
        "has a home for this fact, inside the schema, where a gate can reach it. Two homes for one",
        "fact drift, and the unchecked one is always the copy that rots.",
    ],
    R_SCHEMA: [
        "THIS IS NOT A KEY, IT IS A PRIVATE SCHEMA — a whole nested shape that nothing validates.",
        "Nobody will notice when it goes stale, because there is nothing to notice with. Take it",
        "through §2's proposal path: name the wall, show it recurs, show it projects, land it in",
        "mac.schema.json as typed core with a schema_version bump.",
    ],
    R_GAP: [
        "NO CORE EQUIVALENT — so this is a MAC GAP, not a shortcut. Say what the wall is and change",
        "MAC, rather than declaring beside it: §2's proposal path is name the wall, show it recurs,",
        "show it projects onto all three target families, land it as a core key. Until it lands, the",
        "model says it in prose or does not say it.",
    ],
}


def scan(root: str) -> tuple[list[dict], int]:
    """Every `x-` key under `root`, with the file count that was actually READ.

    The read count is returned, not just the findings: zero YAML read is an OUTAGE, not a clean
    bundle. A gate whose denominator is zero has not judged the bundle, it has failed to find it —
    and historically that printed the same shape as a pass, which is the loudest possible way to be
    silent."""
    found, read = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith((".yaml", ".yml")):
                continue
            p = os.path.join(dirpath, fn)
            try:
                doc = yaml.safe_load(open(p, encoding="utf-8"))
            except Exception:
                continue
            read += 1
            rel = os.path.relpath(p, root)
            for where, key, value in _hits(doc):
                dups = duplicates(key, value)
                found.append({
                    "code": CODE, "file": rel, "path": where, "key": key,
                    "duplicates": dups,
                    "reject_class": classify(rel, key, value, dups),
                    "shape": type(value).__name__,
                })
    return found, read


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# the gate
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def run(root: str, out=None, as_json: bool = False) -> int:
    """The gate proper. Returns 0 (PASS), 1 (FAIL) or 2 (SETUP — no verdict printed)."""
    emit = (lambda s="": print(s, file=out)) if out is not None else (lambda s="": print(s))

    if not os.path.isdir(root):
        emit(f"  [ERROR] root is not a directory: {root}")
        return 2

    found, read = scan(root)

    if as_json:
        emit(json.dumps({"code": CODE, "files_read": read, "findings": found},
                        indent=1, ensure_ascii=False))
        return 2 if not read else (1 if found else 0)

    if not read:
        # EMPTY DENOMINATOR = OUTAGE. No verdict line: the gate judged nothing.
        emit(f"  [ERROR] found no YAML under {root}, so this gate measured NOTHING — its verdict is "
             f"UNKNOWN, not clean")
        return 2

    emit(f"── extension-key gate ── {de(read)} YAML file(s) under {root} ──\n")

    if not found:
        emit(f"PASS: extension-keys — no `x-` key in {de(read)} file(s) "
             f"({len(CORE)} core homes known)")
        return 0

    # FANOUT IS COLLAPSED. One block per (class, key), carrying its sites — never one block per site.
    by_class: dict[str, dict[str, list]] = {}
    for f in found:
        by_class.setdefault(f["reject_class"], {}).setdefault(f["key"], []).append(f)

    for klass in (R_MANIFEST, R_DUPLICATE, R_SCHEMA, R_GAP):
        keys = by_class.get(klass)
        if not keys:
            continue
        n = sum(len(v) for v in keys.values())
        emit(f"  {klass.upper()} — {de(len(keys))} key(s), {de(n)} site(s)")
        for key in sorted(keys):
            sites = keys[key]
            emit(f"    `{key}`")
            for f in sites[:12]:
                emit(f"      [ERROR] {f['file']}  {f['path']}  — `{f['key']}` is prohibited ({klass})")
            if len(sites) > 12:
                emit(f"      [ERROR] … {de(len(sites) - 12)} further site(s) of `{key}` not listed")
            for home in sites[0]["duplicates"]:
                emit(f"      duplicates core: {home}")
        for line in REMEDY[klass]:
            emit(f"      {line}")
        emit("")

    files = len({f["file"] for f in found})
    keys = len({f["key"] for f in found})
    emit(f"  An `x-` key is outside every gate MAC has, so nothing can check what it holds — which is")
    emit(f"  how two of four declared cell keys came to be false, both of them on the relations where")
    emit(f"  nothing enforced the key. CONFORMANCE.md §2: the core is closed and there is no hatch.")
    emit("")
    emit(f"FAIL: extension-keys — {de(len(found))} prohibited `x-` site(s), {de(keys)} distinct key(s) "
         f"in {de(files)} file(s) of {de(read)} read")
    return 1


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# --self-test : one mutant per reject class + clean fixtures that must pass
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def _fixture(base, name: str, files: dict) -> str:
    root = os.path.join(base, name)
    for rel, text in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
    os.makedirs(root, exist_ok=True)
    return root


def self_test() -> int:
    import io
    import tempfile

    _DS = "metadata:\n  table: shipments\ntable:\n  name: shipments\n  columns:\n    - name: id\n"
    cases, failures = [], []

    with tempfile.TemporaryDirectory() as tmp:
        # ── CLEAN FIXTURES — must PASS, or the gate refuses work that is correct ─────────────────
        cases.append(("clean/no-extension-keys", _fixture(tmp, "c_none", {
            "data/datasets/shipments.yaml": _DS}), 0, ["PASS: extension-keys"]))
        # OVER-FIRING GUARD: `x-` is a PREFIX rule. A key that merely CONTAINS the two characters, or
        # spells the same idea with an underscore, is a core-vocabulary question and not this gate's.
        cases.append(("clean/lookalike-keys-not-prefixed", _fixture(tmp, "c_look", {
            "data/datasets/shipments.yaml":
                "metadata:\n  table: shipments\n  max-rows: 10\n  prefix-x-thing: yes\n"
                "  x_subrole: value\n  xtra: 1\ntable:\n  name: shipments\n"}), 0, ["PASS: extension-keys"]))
        # A bundle that already took the remedy: the fact moved into a CORE field. Must pass, or the
        # gate is refusing the very resolution it prescribes.
        cases.append(("clean/fact-moved-into-core", _fixture(tmp, "c_core", {
            "data/datasets/shipments.yaml":
                "metadata:\n  table: shipments\ntable:\n  name: shipments\n"
                "identity_evidence:\n  key: [id]\n"}), 0, ["PASS: extension-keys"]))

        # ── MUTANTS — one per reject class ───────────────────────────────────────────────────────
        # 1. duplicates a core field -> the finding must NAME the core home, not just the rule
        cases.append(("mutant/duplicates-core", _fixture(tmp, "m_dup", {
            "data/datasets/shipments.yaml": _DS + "x-natural_key: [id]\n"}), 1,
            ["DUPLICATES-CORE", "duplicates core: TableFile.identity_evidence.key",
             "USE THE CORE FIELD", "FAIL: extension-keys"]))
        # 2. no core equivalent -> a MAC GAP, routed to §2's proposal path (never to a namespace)
        cases.append(("mutant/no-core-equivalent", _fixture(tmp, "m_gap", {
            "data/datasets/shipments.yaml": _DS + "x-steward: a-team\n"}), 1,
            ["NO-CORE-EQUIVALENT", "MAC GAP", "proposal path", "FAIL: extension-keys"]))
        # 3. a whole nested block -> a private schema nothing validates
        cases.append(("mutant/private-sub-schema", _fixture(tmp, "m_block", {
            "data/datasets/shipments.yaml": _DS + "x-policy:\n  retention: 30\n  owner: a-team\n"}), 1,
            ["PRIVATE-SUB-SCHEMA", "NOT A KEY, IT IS A PRIVATE SCHEMA", "FAIL: extension-keys"]))
        # 4. DECLARED in the manifest profile -> the retired MAC009 remedy, refused on sight. This is
        #    the regression that matters most: the previous framework told bundles to do exactly this.
        cases.append(("mutant/declared-in-manifest-profile", _fixture(tmp, "m_manifest", {
            "mac.project.yaml":
                "planes:\n  data: data\nprofile:\n  extensions:\n    x-steward:\n"
                "      description: who owns the field\n",
            "data/datasets/shipments.yaml": _DS}), 1,
            ["DECLARED-IN-MANIFEST", "DECLARING IS NOT A DEFENCE", "MAC009", "FAIL: extension-keys"]))
        # 5. reached where MAC009 could NOT reach: a file MAC routes to no definition. MAC009 scoped
        #    itself to schema-routed files, so withdrawing it only loses coverage if this misses.
        cases.append(("mutant/unrouted-file-still-reached", _fixture(tmp, "m_unrouted", {
            "acceptance/notes.yaml": "x-probe: something\n"}), 1,
            ["acceptance/notes.yaml", "FAIL: extension-keys"]))

        # ── SETUP (exit 2) — the gate did not judge, and must not print a verdict ────────────────
        cases.append(("setup/no-yaml-found", _fixture(tmp, "s_empty", {"README.md": "nothing\n"}), 2,
                      ["measured NOTHING", "UNKNOWN, not clean"]))
        cases.append(("setup/root-missing", os.path.join(tmp, "does_not_exist"), 2,
                      ["root is not a directory"]))

        for label, root, want_rc, want_text in cases:
            buf = io.StringIO()
            rc = run(root, out=buf)
            text = buf.getvalue()
            verdicts = [ln for ln in text.splitlines()
                        if ln.startswith("PASS:") or ln.startswith("FAIL:")]
            ok, notes = True, []
            if rc != want_rc:
                ok, _ = False, notes.append(f"exit {rc}, expected {want_rc}")
            want_verdicts = 0 if want_rc == 2 else 1
            if len(verdicts) != want_verdicts:
                ok, _ = False, notes.append(
                    f"{len(verdicts)} PASS:/FAIL: line(s), expected {want_verdicts}")
            if verdicts and verdicts[-1] != text.rstrip().splitlines()[-1]:
                ok, _ = False, notes.append("verdict is not the LAST line")
            if want_rc == 1 and verdicts and not verdicts[0].startswith("FAIL:"):
                ok, _ = False, notes.append("verdict line is not a FAIL:")
            if want_rc == 0 and verdicts and not verdicts[0].startswith("PASS:"):
                ok, _ = False, notes.append("verdict line is not a PASS:")
            for frag in want_text:
                if frag not in text:
                    ok, _ = False, notes.append(f"message never says {frag!r}")
            # THE STANDING GUARD: no refusal may ever route the operator back to a namespace or to a
            # declaration. That is the contradiction this revision removed, and a reworded message is
            # exactly how it would come back.
            if want_rc == 1:
                low = text.lower()
                for banned in ("declare each in", "profile.x_keys", "invent under",
                               "promotion candidate", "undeclared debt"):
                    if banned in low:
                        ok, _ = False, notes.append(f"refusal points back at the namespace ({banned!r})")
            print(f"  {'ok  ' if ok else 'FAIL'}  {label}" + ("" if ok else "  <- " + "; ".join(notes)))
            if not ok:
                failures.append(label)

    print()
    if failures:
        print(f"FAIL: extension-keys self-test — {len(failures)} of {len(cases)} case(s) wrong: "
              f"{', '.join(failures)}")
        return 1
    print(f"PASS: extension-keys self-test — {len(cases)} case(s): every mutant refused with the "
          f"remedy for its class, every clean fixture accepted, no refusal routed back to a namespace")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true",
                    help="one mutant per reject class + clean fixtures that must pass")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    return run(os.path.abspath(a.root), as_json=a.json)


if __name__ == "__main__":
    raise SystemExit(main())
