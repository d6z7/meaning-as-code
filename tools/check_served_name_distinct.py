#!/usr/bin/env python3
"""check_served_name_distinct.py — the SERVED-NAME-DISTINCT gate.

WHAT IT ENFORCES
----------------
A served/curated dataset (``data/datasets/*``) must carry a name DISTINCT from every raw source
(``data/sources/*``). When a served view is named the same as its raw source, the lineage's source
node and dataset node collapse into one — the ``source -> dataset`` (A->B) transformation renders as
a SELF-LOOP and reads as flawed. This gate makes shipping that impossible.

THE CONVENTION IS PART OF THE GATE, NOT PART OF THE FOLKLORE
------------------------------------------------------------
This gate publishes the naming convention in its FAILURE MESSAGE. An operator must never have to
read this source file to learn what an acceptable name looks like. Measured reason: in a controlled
two-operator experiment, the operators who converged on served names did so because they read a
gate's worked example — the convention travelled through the gate, not through any method document.
A gate that refuses a name without saying what would be accepted transmits nothing; it just blocks.

  Accepted shape (the DEFAULT convention, when a bundle declares nothing):

      <role>_<marker>_<business noun>          e.g. raw `shipments`  ->  served `v_acme_shipments`

  where <role> is the relation's role prefix (``v`` for a view, ``dim`` for a dimension, …),
  <marker> is the bundle's own source key (``metadata.source`` on its descriptors, lowercased),
  and <business noun> is the clean noun — the raw name with the source-system infix removed
  (raw `acme_lm_shipments` -> noun `shipments`).

THE ALREADY-CLEAN-NOUN CASE (the defect this file was rewritten to fix)
-----------------------------------------------------------------------
"Rename to a clean name" is UNSATISFIABLE when the raw relation is ALREADY a clean business noun:
raw `shipments` has no source-system infix to strip, so the only "clean name" is `shipments`, which
is exactly the name being refused. The gate used to emit that literal absurdity — it printed
``rename ... to a distinct clean name (e.g. 'shipments')`` while refusing `shipments`. Two operators
hit it independently and both asked the same question: *what do I do when the raw name is already
the business noun?*

Answer, now stated by the gate itself, in two layers:

  1. DECLARED — a bundle MAY declare its own convention in ``mac.project.yaml`` (preferred), and
     then the gate checks conformance to THAT rather than to a convention MAC invented:

         x-serving-naming:                      # or, equivalently, `serving: {naming: {...}}`
           pattern:  '^v_acme_[a-z0-9_]+$'      # REQUIRED — every served table.name must match
           template: 'v_acme_{noun}'            # optional — how to BUILD one; {noun} = clean noun
           example:  "raw `shipments` -> served `v_acme_shipments`"   # optional — quoted verbatim

     Declared wins because the convention is the BUNDLE's fact, not the framework's: MAC owns the
     invariant (served node != raw node), the bundle owns the spelling. A declared block with no
     ``pattern`` is a SETUP error (exit 2), not a pass — a convention the gate cannot check is worse
     than none, because the manifest then claims a guarantee nothing enforces.

  2. FALLBACK — undeclared bundles are NOT retro-legislated: the gate still fails only on the
     invariant (collision), never on convention conformance, but the refusal message STATES the
     default convention above and suggests a concrete conforming name built from this bundle's own
     marker. Enforcing an unpublished convention against bundles authored before it existed would
     red the estate for a rule nobody was told; publishing it in the one place an operator is
     already looking — the failure — is what actually converges them.

Both suggestion paths are DERIVED, never hardcoded: the source-system infix is inferred from tokens
the raw namespace repeats, and the marker from the bundle's own ``metadata.source``. An earlier
version hardcoded two literal infixes, so its "worked example" suggested the very name it refused
for every bundle but the one those literals came from.

The suggested rename covers the FILE STEM and ``table.name`` TOGETHER — ``check_relation_identity.py``
requires stem == table.name, so renaming only one of them trades this gate's red for that one's.

OFFLINE + pure-structural (files on disk, no AWS).

Usage:  python3 tools/check_served_name_distinct.py <bundle-root>
        python3 tools/check_served_name_distinct.py --self-test
Exit:   0 = PASS ; 1 = FAIL (a collision, or a violation of a DECLARED convention)
        2 = SETUP failure (bad usage / unreadable or incoherent declaration) — by this toolchain's
            convention exit 2 means "the gate did not judge the bundle", which mac_compile.py maps to
            a WARNING rather than an error. Never returned for a bundle defect.
Output: exactly one ``PASS:``/``FAIL:`` line (the last line), for exit 0 and 1. Exit 2 prints
        neither — a gate that did not judge must not emit a verdict.
"""
from __future__ import annotations

import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import yaml

# Role/structural tokens: they say what KIND of relation this is, so they are never the
# source-system infix and never the bundle marker. Kept small and generic on purpose.
_STRUCTURAL = {"dim", "fact", "facts", "f", "d", "v", "vw", "view", "stg", "stage", "raw", "src",
               "tbl", "t", "tmp", "base", "curated", "clean"}

_DEFAULT_ROLE = "v"


def _slug(text: str) -> str:
    """A name token safe to paste into a relation name."""
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(text or "").lower())).strip("_")


def _descriptors(d: Path) -> dict:
    """{stem: {"name": table.name, "source": metadata.source, "path": <repo-relative>}} for a plane dir.

    The stem is the fallback name: a descriptor with no ``table.name`` still materialises to something,
    and that something is its stem.
    """
    out = {}
    if not d.exists():
        return out
    for p in sorted(d.glob("*.yaml")):
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            doc = {}
        if not isinstance(doc, dict):
            doc = {}
        tbl = doc.get("table") or {}
        meta = doc.get("metadata") or {}
        out[p.stem] = {
            "name": str((tbl.get("name") if isinstance(tbl, dict) else None) or p.stem),
            "source": str((meta.get("source") if isinstance(meta, dict) else "") or ""),
            "path": f"data/{d.name}/{p.name}",
        }
    return out


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# the convention: declared by the bundle, or derived and published by the gate
# ──────────────────────────────────────────────────────────────────────────────────────────────────

class SetupError(Exception):
    """The gate cannot judge — a declaration it was asked to enforce is unusable. Exit 2, not 1."""


def _declared_convention(root: Path) -> dict | None:
    """The bundle's own convention from ``mac.project.yaml``, or None.

    Accepts ``x-serving-naming`` (the MAC-conformant extension spelling: the core is CLOSED, so a
    bundle-owned key lives under ``x-`` and is declared in the manifest's profile) and the plain
    ``serving.naming`` block, which reads better in manifests whose core already carries it.
    """
    manifest = root / "mac.project.yaml"
    if not manifest.exists():
        return None
    try:
        doc = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        raise SetupError(f"{manifest.name} is not readable YAML ({exc!r}) — the gate cannot tell "
                         f"whether this bundle declares a serving-name convention") from exc
    if not isinstance(doc, dict):
        return None
    block = doc.get("x-serving-naming")
    if block is None:
        serving = doc.get("serving")
        block = (serving or {}).get("naming") if isinstance(serving, dict) else None
    if block is None:
        return None
    if not isinstance(block, dict):
        raise SetupError("the serving-name convention in mac.project.yaml is not a mapping — expected "
                         "keys `pattern` (required), `template`, `example`")
    pattern = block.get("pattern")
    if not pattern:
        raise SetupError(
            "mac.project.yaml declares a serving-name convention with no `pattern`. A declared "
            "convention the gate cannot check is worse than none: the manifest claims a guarantee "
            "nothing enforces. Add the regex every served table.name must match, e.g.\n"
            "    x-serving-naming:\n"
            "      pattern:  '^v_acme_[a-z0-9_]+$'\n"
            "      template: 'v_acme_{noun}'\n"
            "      example:  \"raw `shipments` -> served `v_acme_shipments`\"")
    try:
        rx = re.compile(str(pattern))
    except re.error as exc:
        raise SetupError(f"the declared serving-name `pattern` is not a valid regex: {pattern!r} "
                         f"({exc})") from exc
    return {"pattern": str(pattern), "regex": rx,
            "template": str(block.get("template") or ""),
            "example": str(block.get("example") or "")}


def _system_tokens(raw_names: list) -> list:
    """Tokens the RAW namespace REPEATS — the source-system infix, derived rather than hardcoded.

    A token carried by at least half the raw relations (and by at least two of them) is naming the
    SYSTEM, not the subject; the business noun is what survives its removal. Used for SUGGESTIONS
    only — a mis-derived token can never fail a bundle, only make one hint less apt.
    """
    if len(raw_names) < 2:
        return []
    counts = Counter()
    for n in raw_names:
        for tok in set(str(n).split("_")):
            if tok and tok not in _STRUCTURAL and not tok.isdigit():
                counts[tok] += 1
    threshold = max(2, (len(raw_names) + 1) // 2)
    return [t for t, c in counts.items() if c >= threshold]


def _business_noun(name: str, system_tokens: list) -> str:
    """The clean noun inside a raw relation name: its tokens, less the source-system ones."""
    toks = [t for t in name.split("_") if t and t not in system_tokens]
    keep = [t for t in toks if t not in _STRUCTURAL] or toks
    return "_".join(keep) or name


def _marker(served: dict, root: Path) -> str:
    """The bundle's serving marker — what makes ITS relations addressable as its own.

    Taken from the descriptors' own ``metadata.source`` (a declared MAC field, present on every
    served descriptor in every bundle in the estate), falling back to the manifest's dataset/project
    metadata and finally to the bundle directory name. Derived from the bundle, never assumed.
    """
    votes = Counter(_slug(d.get("source")) for d in served.values() if _slug(d.get("source")))
    if votes:
        return votes.most_common(1)[0][0]
    manifest = root / "mac.project.yaml"
    if manifest.exists():
        try:
            doc = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            meta = doc.get("metadata") or {} if isinstance(doc, dict) else {}
            for key in ("dataset", "project", "label"):
                cand = _slug(str(meta.get(key) or "").split("/")[-1])
                if cand:
                    return cand
        except Exception:  # noqa: BLE001
            pass
    return _slug(root.name)


def _role_of(name: str) -> str:
    """The relation's role prefix, kept when suggesting a rename (a dimension stays a dimension)."""
    head = name.split("_", 1)[0]
    return head if head in _STRUCTURAL and head not in {"raw", "src", "stg", "stage", "tmp"} else _DEFAULT_ROLE


def _suggest(name: str, taken: set, conv: dict | None, system_tokens: list, marker: str) -> tuple:
    """(suggested name, why-this-shape) for a refused served name. Never returns `name` itself.

    Two shapes, and which one applies is the whole already-clean-noun question:
      * the raw name CARRIES a source-system infix  -> the suggestion is the infix stripped off;
      * the raw name is ALREADY the business noun   -> nothing to strip, so the suggestion carries
        the bundle's serving marker instead. This is the branch that used to echo the refused name.
    """
    noun = _business_noun(name, system_tokens)
    if conv and conv.get("template"):
        cand = conv["template"].replace("{noun}", noun)
        if cand and cand != name:
            return cand, "the shape this bundle declares in mac.project.yaml"
    stripped = noun
    if stripped and stripped != name and stripped not in taken:
        return stripped, ("the same relation with the source-system infix removed — the raw name "
                          "carries one, so the business noun alone is already distinct")
    role = _role_of(name)
    base = noun if noun else name
    cand = f"{role}_{marker}_{base}" if marker else f"{role}_{base}"
    n = 2
    while cand in taken or cand == name:                 # pathological, but never hand back the refusal
        cand = f"{role}_{marker}_{base}_{n}" if marker else f"{role}_{base}_{n}"
        n += 1
    return cand, ("the raw name is ALREADY the clean business noun — there is no infix to strip, so "
                  "the served relation takes the bundle's serving marker to become its own node")


def _accepted_line(conv: dict | None, marker: str) -> str:
    """The convention on ONE line, with a worked example — carried by EVERY [ERROR].

    Deliberately redundant with the convention block below: operators grep single ``[ERROR]`` lines
    and read their neighbours, and a rule that only appears in a trailing block is a rule half the
    readers never see.
    """
    if conv:
        shown = conv.get("example") or conv.get("template") or ""
        return (f"names matching this bundle's declared pattern {conv['pattern']}"
                + (f", e.g. {shown}" if shown else ""))
    mk = marker or "acme"
    return (f"`<role>_<marker>_<business noun>` with marker `{mk}` — e.g. raw `shipments` -> served "
            f"`v_{mk}_shipments`; or the business noun ALONE when the raw name carries a "
            f"source-system infix — e.g. raw `{mk}_lm_shipments` -> served `shipments`")


def _convention_block(conv: dict | None, marker: str, worked: str) -> list:
    """The convention, as the operator should read it — printed with every refusal."""
    lines = ["  ── the convention ──────────────────────────────────────────────────────────────"]
    if conv:
        lines += [f"  DECLARED by this bundle in mac.project.yaml — the gate checks conformance to it,",
                  f"  not to any MAC default:",
                  f"      pattern : {conv['pattern']}"]
        if conv.get("template"):
            lines.append(f"      template: {conv['template']}   ({{noun}} = the clean business noun)")
        lines.append(f"      example : {conv['example'] or worked}")
    else:
        mk = marker or "<source-key>"
        lines += ["  This bundle declares no convention, so the DEFAULT applies — an acceptable served",
                  "  name looks like:",
                  f"      <role>_<marker>_<business noun>        role: v | dim | fact   marker: {mk}",
                  f"      worked example: {worked}",
                  "  To have the gate enforce YOUR spelling instead, declare it in mac.project.yaml:",
                  "      x-serving-naming:",
                  f"        pattern:  '^v_{mk}_[a-z0-9_]+$'",
                  f"        template: 'v_{mk}_{{noun}}'",
                  f"        example:  \"raw `shipments` -> served `v_{mk}_shipments`\""]
    lines += ["  Rename the FILE STEM and table.name TOGETHER — check_relation_identity.py requires",
              "  stem == table.name, so renaming one of them only moves the red.",
              "  ────────────────────────────────────────────────────────────────────────────────"]
    return lines


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# the gate
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def run(root: Path, out=None) -> int:
    """The gate proper. Returns 0 (PASS), 1 (FAIL) or 2 (SETUP — no verdict printed)."""
    emit = (lambda s="": print(s, file=out)) if out is not None else (lambda s="": print(s))
    try:
        conv = _declared_convention(root)
    except SetupError as exc:
        emit(f"── served-name-distinct gate ── SETUP ── {root} ──\n")
        emit(f"  [ERROR] {exc}")
        return 2

    data = root / "data"
    sources = _descriptors(data / "sources")
    served = _descriptors(data / "datasets")
    emit(f"── served-name-distinct gate ── {len(served)} served dataset(s) vs {len(sources)} raw "
         f"source(s) under {root} ──\n")
    if not served:
        emit("PASS: served-name-distinct — no served datasets under data/datasets, nothing to judge")
        return 0

    # The lineage self-loops when the served view's PHYSICAL name (table.name — the relation it
    # materialises to) equals a raw source's physical name OR its descriptor stem, since a raw
    # descriptor with no table.name still materialises to its stem.
    raw_tokens = {d["name"] for d in sources.values()} | set(sources.keys())
    marker = _marker(served, root)
    system_tokens = _system_tokens(sorted(raw_tokens))
    taken = raw_tokens | {d["name"] for d in served.values()}
    worked_marker = marker or "acme"
    worked = f"raw `shipments` -> served `v_{worked_marker}_shipments`"
    accepted = _accepted_line(conv, marker)

    errors = []
    for stem, d in served.items():
        name, path = d["name"], d["path"]
        if name in raw_tokens:
            fix, why = _suggest(name, taken, conv, system_tokens, marker)
            errors.append([
                f"{path} — served name '{name}' EQUALS a raw source name -> rename to '{fix}'",
                f"      why      : the source node and the dataset node collapse into one, so the "
                f"source -> dataset edge renders as a self-loop",
                f"      accepted : {accepted}",
                f"      rename to: '{fix}'",
                f"                 ({why})",
            ])
            continue
        if conv and not conv["regex"].search(name):
            fix, why = _suggest(name, taken - {name}, conv, system_tokens, marker)
            errors.append([
                f"{path} — served name '{name}' does not match the convention THIS BUNDLE "
                f"declares -> rename to '{fix}'",
                f"      why      : mac.project.yaml declares pattern {conv['pattern']}; a served name "
                f"outside it is a convention the manifest claims and the bundle does not keep",
                f"      accepted : {accepted}",
                f"      rename to: '{fix}'",
                f"                 ({why})",
            ])

    for e in errors:
        emit(f"  [ERROR] {e[0]}")
        for line in e[1:]:
            emit(line)
        emit("")
    if errors:
        for line in _convention_block(conv, marker, worked):
            emit(line)
        emit("")
        emit(f"FAIL: served-name-distinct — {len(errors)} served relation(s) refused; each refusal "
             f"above names the accepted shape and a conforming rename")
        return 1
    emit(f"PASS: served-name-distinct — {len(served)} served relation(s) distinct from "
         f"{len(sources)} raw source(s)"
         + (" and conforming to the declared convention" if conv else ""))
    return 0


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# --self-test : one mutant per reject class + a clean fixture that must pass
# ──────────────────────────────────────────────────────────────────────────────────────────────────

def _fixture(base: Path, name: str, raws: list, dsets: list, manifest: str = "") -> Path:
    root = base / name
    (root / "data" / "sources").mkdir(parents=True, exist_ok=True)
    (root / "data" / "datasets").mkdir(parents=True, exist_ok=True)
    if manifest:
        (root / "mac.project.yaml").write_text(manifest, encoding="utf-8")
    for n in raws:
        (root / "data" / "sources" / f"{n}.yaml").write_text(
            f"metadata:\n  table: {n}\n  kind: raw_source\n  source: ACME\ntable:\n  name: {n}\n",
            encoding="utf-8")
    for n in dsets:
        (root / "data" / "datasets" / f"{n}.yaml").write_text(
            f"metadata:\n  table: {n}\n  source: ACME\ntable:\n  name: {n}\n", encoding="utf-8")
    return root


def self_test() -> int:
    import io

    cases, failures = [], []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # ── CLEAN FIXTURES — must PASS, or the gate rejects work that is correct ─────────────────
        cases.append(("clean/infix-stripped", _fixture(
            base, "clean_infix", ["acme_lm_shipments", "acme_lm_orders"], ["shipments", "orders"]), 0, []))
        # the already-clean case, SATISFIED direction: raw names are clean nouns, served names carry
        # the bundle's serving marker. This is the resolution the failure message prescribes — if it
        # did not pass, the gate would be publishing advice it then refuses.
        cases.append(("clean/already-clean-noun-satisfied", _fixture(
            base, "clean_marker", ["shipments", "orders"], ["v_acme_shipments", "v_acme_orders"]), 0, []))
        cases.append(("clean/no-datasets", _fixture(base, "clean_empty", ["shipments"], []), 0, []))
        declared = ("planes: {data: data, ontology: ontology}\n"
                    "x-serving-naming:\n"
                    "  pattern: '^v_acme_[a-z0-9_]+$'\n"
                    "  template: 'v_acme_{noun}'\n"
                    "  example: \"raw `shipments` -> served `v_acme_shipments`\"\n")
        cases.append(("clean/declared-convention-conforming", _fixture(
            base, "clean_declared", ["shipments"], ["v_acme_shipments"], declared), 0, []))

        # ── MUTANTS — one per reject class ───────────────────────────────────────────────────────
        # 1. collision where the raw name carries a source-system infix
        cases.append(("mutant/collision-with-infix", _fixture(
            base, "m_infix", ["acme_lm_shipments", "acme_lm_orders"], ["acme_lm_shipments"]), 1,
            ["EQUALS a raw source name", "rename to: 'shipments'"]))
        # 2. collision where the raw name is ALREADY the clean business noun — the fixed defect.
        #    The suggestion must NOT be the refused name, and must carry the published convention.
        cases.append(("mutant/collision-already-clean-noun", _fixture(
            base, "m_clean", ["shipments", "orders"], ["shipments"]), 1,
            ["EQUALS a raw source name", "rename to: 'v_acme_shipments'",
             "ALREADY the clean business noun", "<role>_<marker>_<business noun>",
             "x-serving-naming:"]))
        # 3. collision with a raw descriptor STEM that declares no table.name
        stem_root = _fixture(base, "m_stem", [], ["shipments"])
        (stem_root / "data" / "sources" / "shipments.yaml").write_text(
            "metadata:\n  kind: raw_source\n", encoding="utf-8")
        cases.append(("mutant/collision-with-raw-stem", stem_root, 1, ["EQUALS a raw source name"]))
        # 4. declared convention VIOLATED (name is distinct from raw, but off-convention)
        cases.append(("mutant/declared-convention-violated", _fixture(
            base, "m_declared", ["shipments"], ["dim_shipments"], declared), 1,
            ["does not match the convention THIS BUNDLE ", "rename to: 'v_acme_shipments'"]))
        # 5. declared convention with no pattern -> SETUP (exit 2), never a silent pass
        cases.append(("mutant/declared-without-pattern", _fixture(
            base, "m_nopattern", ["shipments"], ["v_acme_shipments"],
            "x-serving-naming:\n  example: \"raw `shipments` -> served `v_acme_shipments`\"\n"), 2,
            ["declares a serving-name convention with no `pattern`"]))
        # 6. declared convention with an uncompilable pattern -> SETUP
        cases.append(("mutant/declared-pattern-not-a-regex", _fixture(
            base, "m_badregex", ["shipments"], ["v_acme_shipments"],
            "x-serving-naming:\n  pattern: '^v_acme_([a-z'\n"), 2, ["not a valid regex"]))

        for label, root, want_rc, want_text in cases:
            buf = io.StringIO()
            rc = run(root, out=buf)
            text = buf.getvalue()
            verdicts = [ln for ln in text.splitlines()
                        if ln.startswith("PASS:") or ln.startswith("FAIL:")]
            ok, notes = True, []
            if rc != want_rc:
                ok, _ = False, notes.append(f"exit {rc}, expected {want_rc}")
            # contract: exactly one verdict line for a judgement; none for a setup failure
            want_verdicts = 0 if want_rc == 2 else 1
            if len(verdicts) != want_verdicts:
                ok, _ = False, notes.append(f"{len(verdicts)} PASS:/FAIL: line(s), expected {want_verdicts}")
            if want_rc == 1 and verdicts and not verdicts[0].startswith("FAIL:"):
                ok, _ = False, notes.append("verdict line is not a FAIL:")
            if want_rc == 0 and verdicts and not verdicts[0].startswith("PASS:"):
                ok, _ = False, notes.append("verdict line is not a PASS:")
            for frag in want_text:
                if frag not in text:
                    ok, _ = False, notes.append(f"message never says {frag!r}")
            # the standing regression guard: a refusal must never hand back the name it refused
            for line in text.splitlines():
                m = re.search(r"served name '([^']+)' EQUALS", line)
                if m:
                    refused = m.group(1)
                    if re.search(rf"rename to:? '{re.escape(refused)}'", text):
                        ok, _ = False, notes.append(
                            f"suggests the refused name back to the operator ({refused!r})")
            print(f"  {'ok  ' if ok else 'FAIL'}  {label}"
                  + ("" if ok else "  <- " + "; ".join(notes)))
            if not ok:
                failures.append(label)

    print()
    if failures:
        print(f"FAIL: served-name-distinct self-test — {len(failures)} of {len(cases)} case(s) wrong: "
              f"{', '.join(failures)}")
        return 1
    print(f"PASS: served-name-distinct self-test — {len(cases)} case(s): every mutant refused with a "
          f"conforming rename, every clean fixture accepted")
    return 0


def main(argv) -> int:
    if len(argv) == 2 and argv[1] == "--self-test":
        return self_test()
    if len(argv) != 2 or argv[1].startswith("-"):
        print("usage: check_served_name_distinct.py <bundle-root>\n"
              "       check_served_name_distinct.py --self-test", file=sys.stderr)
        return 2                     # SETUP, not a verdict: the gate judged nothing
    return run(Path(argv[1]).resolve())


if __name__ == "__main__":
    sys.exit(main(sys.argv))
