#!/usr/bin/env python3
"""
mac_project.py — resolve a MAC project's layout (flat, or the two-plane data/ontology split).

A MAC project either is FLAT (today's default — concepts/ tables/ edges.yaml rules.yaml at the root) or
declares a TWO-PLANE layout in `mac.project.yaml` (data plane + ontology plane, see reference_manual/data_plane.md).
This one resolver is the single place that knows the difference, so every gate and projector asks it for two
roots instead of hardcoding `concepts/` / `tables/`:

    from mac_project import resolve
    L = resolve(root)
    L.ontology     # dir holding concepts/, edges.yaml, rules.yaml   (flat: root; two-plane: root/ontology)
    L.descriptors  # dir holding TableFile descriptors                (flat: root/tables; two-plane: root/data/datasets)
    L.transforms   # dir holding TransformFile descriptors            (None unless declared: two-plane data/transforms)
    L.sources      # dir holding raw-input TableFile descriptors      (None unless declared: two-plane data/sources)
    L.planes       # {} when flat; {"data": "...", "ontology": "..."} when two-plane

The model already binds a concept to its descriptor by RELATION NAME, not by path, so nothing in the YAML
changes between layouts — only where the tools look.
"""
from pathlib import Path
from types import SimpleNamespace

try:
    import yaml
except ImportError:                      # resolver must not hard-depend on yaml for the flat default
    yaml = None

MANIFEST = "mac.project.yaml"


def resolve(root):
    """Return a layout for `root`. No manifest ⇒ flat (back-compatible)."""
    root = Path(root)
    mf = root / MANIFEST
    if mf.exists() and yaml is not None:
        m = yaml.safe_load(mf.read_text()) or {}
        planes = m.get("planes") or {}
        onto = root / (planes.get("ontology") or ".")
        desc = root / (m.get("descriptors") or "tables")
        # data-plane descriptor dirs — present only when declared (transforms + raw sources)
        tfm = (root / m["transforms"]).resolve() if m.get("transforms") else None
        srcs = (root / m["sources"]).resolve() if m.get("sources") else None
        # the MEASUREMENT plane. Defaults beside the descriptors rather than requiring a manifest
        # entry, so an existing bundle gains it without editing anything.
        profs = (root / (m.get("profiles") or "data/profiles")).resolve()
        return SimpleNamespace(root=root, ontology=onto.resolve(), descriptors=desc.resolve(),
                               transforms=tfm, sources=srcs, profiles=profs,
                               planes=planes, two_plane=bool(planes))
    return SimpleNamespace(root=root.resolve(), ontology=root.resolve(), descriptors=(root / "tables").resolve(),
                           transforms=None, sources=None, profiles=None, planes={}, two_plane=False)


def field_meaning(concept_doc):
    """Option B: a column's MEANING lives in the ontology, bound to the column via the concept's
    field-anchored contract.rules (not in the data-plane descriptor). Return {column -> directive text}
    for one concept, drawn from each rule's `then` (fallback `why`), keyed by the columns it `binds`."""
    c = concept_doc.get("contract") if isinstance(concept_doc, dict) else None
    rules = c.get("rules") if isinstance(c, dict) else None
    out = {}
    for r in (rules or []):
        if not isinstance(r, dict):
            continue
        txt = " ".join(str(r.get("then") or r.get("why") or "").split())
        if not txt:
            continue
        for col in (r.get("binds") or []):
            out.setdefault(col, []).append(txt)
    return {col: " ".join(txts) for col, txts in out.items()}


def meaning_by_table(concept_docs, ground_table_fn):
    """Aggregate field_meaning across ALL concepts, keyed by (table, column) — so a column's meaning is
    found wherever the column is emitted, even when the rule lives on a different concept grounding the
    same table (e.g. Revenue's rule on orders.gross_amount surfaces under the Order node)."""
    out = {}
    for d in concept_docs:
        tbl = ground_table_fn(d)
        if not tbl:
            continue
        for col, txt in field_meaning(d).items():
            out.setdefault((tbl, col), []).append(txt)
    return {k: " ".join(v) for k, v in out.items()}


def plane_prefixes(root):
    """The plane directory names to treat as transparent when deriving a single-source key
    (e.g. ['ontology', 'data'] so ontology/concepts/… and data/datasets/… share source '')."""
    L = resolve(root)
    return [str(v).strip("/").split("/")[0] for v in L.planes.values()] if L.two_plane else []


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# CONCEPT DISCOVERY — the one home for "where the concepts are"
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# A bundle's concepts live under <ontology-plane>/concepts/, and the framework has ALWAYS allowed them
# to be grouped into sub-directories: reference_manual and both worked examples ship
# concepts/<group>/<name>.yaml, while other bundles keep them flat.
#
# MEASURED 2026-09-10 on the framework's OWN example_shop_ontology (8 concepts, foldered): eight gates
# globbed `concepts/*.yaml` — depth 0 only — found ZERO files and printed a clean verdict.
# check_answerability said "every answer path derives — 0 of 0 concept(s) measured". Three operators
# read that green independently; one rated it blocking. The same eight gates also hardcoded the
# two-plane path `<root>/ontology/concepts`, so they measured zero on a FLAT-layout project too,
# without ever asking this resolver where the ontology plane is.
#
# Both mistakes are the same mistake: a second, private answer to a question this module already
# answers. Discovery is therefore expressed ONCE, here, and every gate reads it.

def concepts_dir(root):
    """The concepts directory for `root`, in whichever layout the project declares."""
    return Path(resolve(root).ontology) / "concepts"


def concept_files(root):
    """Every concept document in `root` — flat (`concepts/x.yaml`) AND foldered
    (`concepts/<group>/x.yaml`, any depth), in one stable order. Empty when there is no plane.

    An EMPTY result is a fact the caller must act on, not a clean measurement: see
    mac_diag.empty_denominator / mac_diag.refuse_empty."""
    d = concepts_dir(root)
    return sorted(d.rglob("*.yaml")) if d.is_dir() else []


def rel(root, path) -> str:
    """`path` as a reader should see it: relative to the project root when it lies inside it.

    Discovery returns RESOLVED paths (the resolver resolves the plane), so a caller that was handed a
    relative root cannot call `Path.relative_to` on the result. One helper, because every gate that
    reports a witness needs exactly this and each one getting it wrong differently is how witness
    addresses stopped being clickable."""
    r, f = Path(root).resolve(), Path(path).resolve()
    try:
        return str(f.relative_to(r))
    except ValueError:
        return str(f)


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# the self-test every layout-reading gate ships
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# ONE harness, because the property is one property: a gate must see a concept wherever the framework
# permits one to be, and must REFUSE — visibly, on a distinct exit code — when it sees none. Written
# here rather than copied into each gate for the reason this whole module exists.

_CONCEPT_DOC = """concept:
  name: Widget
  label: Widget
  class: reference
  identity:
    canonical_key: widget_code
  semantics:
    definition: A fixture object. Domain-neutral on purpose - it names nothing real.
grounding:
  sources:
    - relation: widget_register
      key: widget_code
      columns: [widget_code, widget_name]
"""

# (name, expect_refusal, what it proves). A fixture that cannot fail is not a fixture: the three
# CLEAN layouts each caught a real defect when this was first run, and the two EMPTY ones are the
# reject classes the false green came from.
_SELFTEST_CASES = (
    ("flat_concepts",     False, "two-plane layout, concepts at depth 0"),
    ("foldered_concepts", False, "two-plane layout, concepts under a group folder (the false green)"),
    ("flat_layout",       False, "no manifest at all — concepts/ at the project root"),
    ("empty_plane",       True,  "MUTANT: the concepts directory exists and holds nothing"),
    ("no_plane",          True,  "MUTANT: there is no concepts directory"),
)


def _seed(tmp, case):
    """Write one fixture bundle and return its root."""
    root = Path(tmp) / case
    manifest = "planes:\n  data: data\n  ontology: ontology\ndescriptors: data/datasets\n"
    if case == "flat_concepts":
        (root / "ontology" / "concepts").mkdir(parents=True)
        (root / "mac.project.yaml").write_text(manifest, encoding="utf-8")
        (root / "ontology" / "concepts" / "widget.yaml").write_text(_CONCEPT_DOC, encoding="utf-8")
    elif case == "foldered_concepts":
        (root / "ontology" / "concepts" / "catalog").mkdir(parents=True)
        (root / "mac.project.yaml").write_text(manifest, encoding="utf-8")
        (root / "ontology" / "concepts" / "catalog" / "widget.yaml").write_text(_CONCEPT_DOC,
                                                                               encoding="utf-8")
    elif case == "flat_layout":
        (root / "concepts").mkdir(parents=True)
        (root / "concepts" / "widget.yaml").write_text(_CONCEPT_DOC, encoding="utf-8")
    elif case == "empty_plane":
        (root / "ontology" / "concepts").mkdir(parents=True)
        (root / "mac.project.yaml").write_text(manifest, encoding="utf-8")
    elif case == "no_plane":
        (root / "ontology").mkdir(parents=True)
        (root / "mac.project.yaml").write_text(manifest, encoding="utf-8")
    else:                                                                # pragma: no cover
        raise ValueError(case)
    return root


def selftest_discovery(script) -> int:
    """Run `script` against each fixture and check it sees what the framework says is there.

    A gate is free to FAIL a fixture on content (exit 1) — these bundles are deliberately minimal.
    What it may not do is (a) miss a concept that is present, or (b) report a verdict when it found
    none. Prints one PASS:/FAIL: line. Exit 0 = the gate reads both layouts and refuses on empty."""
    import subprocess
    import sys
    import tempfile
    from mac_diag import EMPTY_EXIT, empty_mark

    script = Path(script).resolve()
    name, bad = script.stem, 0
    with tempfile.TemporaryDirectory() as tmp:
        for case, expect_refusal, why in _SELFTEST_CASES:
            root = _seed(tmp, case)
            p = subprocess.run([sys.executable, str(script), str(root)],
                               capture_output=True, text=True, timeout=300)
            out = (p.stdout or "") + (p.stderr or "")
            # The assertion is about THE CONCEPT DENOMINATOR specifically. A gate may legitimately
            # refuse one of its OTHER populations on these deliberately minimal fixtures (no
            # acceptance corpus, no datasets); that is not this property, and matching the generic
            # outage marker would have conflated the two.
            refused = empty_mark("concept") in out
            ok = (refused == expect_refusal) and (not expect_refusal or p.returncode == EMPTY_EXIT)
            # A traceback is not a verdict. Without this, a gate that crashed on every bundle would
            # score full marks on the three clean cases by never printing a refusal.
            if not expect_refusal and "Traceback (most recent call last)" in out:
                ok = False
                why += "  [crashed]"
            bad += 0 if ok else 1
            verdict = ("refused (exit 2)" if refused else
                       ("ran (exit 2 — another population empty)" if p.returncode == EMPTY_EXIT
                        else f"ran (exit {p.returncode})"))
            print(f"  {'✓' if ok else '✗'} {case:<18} {verdict:<16} expected "
                  f"{'refusal' if expect_refusal else 'a real measurement'} — {why}")
    line = (f"PASS: {name} discovers concepts in every permitted layout and refuses an empty "
            f"denominator ({len(_SELFTEST_CASES)} fixtures)" if not bad else
            f"FAIL: {name} failed {bad} of {len(_SELFTEST_CASES)} layout fixtures")
    print(line)
    return 1 if bad else 0
