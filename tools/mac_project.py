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
    L.references         # dir holding the SOURCES plane's measured ReferenceFiles  (data/references)
    L.references_served  # dir holding the SERVED plane's measured ReferenceFiles   (data/references_served)
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
        # the PREVIEW plane — the measurement plane's twin, defaulted on the same precedent and for
        # the same reason: neither of the estate's two bundles declares it, and an existing bundle
        # must gain it without editing its manifest.
        samps = (root / (m.get("samples") or "data/samples")).resolve()
        # the REFERENCE plane — how the relations point at each other, MEASURED. Defaulted on the
        # same precedent as the two above, and for the same reason: a bundle must gain it without
        # editing its manifest. It is the DATA plane's own relationship family and has nothing to do
        # with the ontology's: the ontology relates business objects, this relates relations.
        refs = (root / (m.get("references") or "data/references")).resolve()
        # THE SECOND PHYSICAL PLANE'S reference family. `references` above measures how the LANDED
        # relations point at each other; this measures the SERVED ones. Two directories because they
        # are two populations measured against two descriptor planes, and one directory would mean
        # one plane's measurement overwriting the other's. Defaulted on the same precedent as its
        # three siblings: a bundle gains it without editing its manifest. The pairing
        # (descriptor plane <-> artifact directory) is declared in sdk/project/er_model.py#PLANES,
        # which the measurer and the gate both read; these two keys are where a bundle may MOVE
        # either directory, exactly as it may move data/references.
        refs_served = (root / (m.get("references_served") or "data/references_served")).resolve()
        return SimpleNamespace(root=root, ontology=onto.resolve(), descriptors=desc.resolve(),
                               transforms=tfm, sources=srcs, profiles=profs, samples=samps,
                               references=refs, references_served=refs_served,
                               planes=planes, two_plane=bool(planes))
    # THE FLAT BRANCH MUST CARRY THE ATTRIBUTE TOO, even as None. It returns `sources=None` and
    # `profiles=None`, so a consumer that only read the manifest branch AttributeErrors here and
    # then TypeErrors globbing a None plane — and every fixture in every gate's self-test carries a
    # manifest, so nothing would ever have caught it.
    return SimpleNamespace(root=root.resolve(), ontology=root.resolve(), descriptors=(root / "tables").resolve(),
                           transforms=None, sources=None, profiles=None, samples=None,
                           references=None, references_served=None, planes={}, two_plane=False)


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


def selftest_discovery(script, *, subject=None, mutants=()) -> int:
    """Run `script` against each fixture and check it sees what the framework says is there.

    TWO PROPERTIES, TWO DENOMINATORS, AND THE SECOND ONE WAS MISSING.
    -----------------------------------------------------------------
    (1) DISCOVERY — the 5 `_SELFTEST_CASES` below. A gate must see a concept wherever the framework
        permits one to be, and must REFUSE — visibly, on a distinct exit code — when it sees none.
        `empty_plane` and `no_plane` are mutants OF THIS property and always ran.

    (2) THE GATE'S OWN RULE — `mutants`, and until 2026-09-13 there were none, for any of the nine
        gates that delegate here. MEASURED on `check_concept_columns_exist`, whose rule is "every
        column a concept names must be a column of the relation it grounds on": the shared fixture
        seeds a concept and NO DESCRIPTOR, so `columns_of()` returns None, `scan()` does
        `if not have: continue`, and the gate printed

            ✓ OK — every column named by 1 concept(s) exists on the relation it grounds on

        having checked ZERO columns. Three clean fixtures scored three ticks for a rule whose
        population was empty. That is this module's own docstring concession — "A gate is free to
        FAIL a fixture on content" — read the other way round: it is also free to PASS on content it
        never had, and 5/5 green said nothing about whether the rule can still reject.

    So a caller may now hand in:

      subject(root) -> None
          Seed whatever the gate's OWN rule needs as a subject, on top of the concept fixture — a
          descriptor with columns, a profile, an acceptance property. Applied to the three CLEAN
          layouts (so the rule is exercised over a NON-ZERO population there, and those three must
          then exit 0, not merely avoid refusing) and to each mutant's base.

      mutants = ((name, mutate, marker, why), ...)
          `mutate(root)` breaks the gate's own rule on an otherwise-clean fixture. The gate must
          then exit 1 — a FINDING, not a refusal (2) and not a pass (0) — and `marker` must appear
          in its output, so the rejection is ATTRIBUTED to the class it was seeded for instead of
          merely counted. `marker` is additionally asserted ABSENT from the clean run, because a
          marker that is always present proves nothing. This is the property the three fully
          attributed sdk gates have (check_engine_coupling 55/55, check_entry_points 37/37,
          check_seam_agreement 45/45) and that "BY FINDING COUNT ONLY" gates do not.

    Prints one PASS:/FAIL: line carrying BOTH denominators, and states `0 mutants of its own rule`
    explicitly when a caller passes none — a gate with no rule mutant must not be able to borrow the
    discovery fixtures' green as evidence that it can still reject."""
    import subprocess
    import sys
    import tempfile
    from mac_diag import EMPTY_EXIT, empty_mark

    script = Path(script).resolve()
    name, bad = script.stem, 0

    def _run(root):
        p = subprocess.run([sys.executable, str(script), str(root)],
                           capture_output=True, text=True, timeout=300)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    clean_output = ""
    with tempfile.TemporaryDirectory() as tmp:
        for case, expect_refusal, why in _SELFTEST_CASES:
            root = _seed(tmp, case)
            # The gate's own rule needs a subject, and only the gate knows what that is. Seeded on
            # the CLEAN layouts only: an empty plane must stay empty, or the refusal mutants stop
            # being mutants.
            if subject is not None and not expect_refusal:
                subject(root)
            rc, out = _run(root)
            # The assertion is about THE CONCEPT DENOMINATOR specifically. A gate may legitimately
            # refuse one of its OTHER populations on these deliberately minimal fixtures (no
            # acceptance corpus, no datasets); that is not this property, and matching the generic
            # outage marker would have conflated the two.
            refused = empty_mark("concept") in out
            ok = (refused == expect_refusal) and (not expect_refusal or rc == EMPTY_EXIT)
            # A traceback is not a verdict. Without this, a gate that crashed on every bundle would
            # score full marks on the three clean cases by never printing a refusal.
            if not expect_refusal and "Traceback (most recent call last)" in out:
                ok = False
                why += "  [crashed]"
            # A SEEDED SUBJECT RAISES THE BAR on the clean layouts. Without a subject, "did not
            # refuse" is all that can be asked. With one, the rule has a real population and a
            # clean fixture that goes red means the fixture — not the tree — is wrong, and every
            # mutant built on it would be proving nothing.
            if subject is not None and not expect_refusal and rc != 0:
                ok = False
                why += f"  [clean fixture + seeded subject exited {rc}, expected 0]"
            if not expect_refusal and not clean_output:
                clean_output = out
            bad += 0 if ok else 1
            verdict = ("refused (exit 2)" if refused else
                       ("ran (exit 2 — another population empty)" if rc == EMPTY_EXIT
                        else f"ran (exit {rc})"))
            print(f"  {'✓' if ok else '✗'} {case:<18} {verdict:<16} expected "
                  f"{'refusal' if expect_refusal else 'a real measurement'} — {why}")

        # ── mutants of the gate's OWN rule ──────────────────────────────────────────────────────
        for i, (mname, mutate, marker, mwhy) in enumerate(mutants):
            # A FRESH BUNDLE PER MUTANT, in its own parent dir. Sharing one fixture would let
            # mutant A's writes decide mutant B's verdict, and `flat_layout` is already on disk
            # from the discovery loop above.
            parent = Path(tmp) / f"mutant_{i}"
            parent.mkdir()
            base = _seed(str(parent), "flat_layout")
            if subject is not None:
                subject(base)
            mutate(base)
            rc, out = _run(base)
            rejected = rc == 1
            attributed = marker in out
            # A marker present on the clean run attributes nothing — it would fire on anything.
            discriminates = marker not in clean_output
            ok = rejected and attributed and discriminates
            bad += 0 if ok else 1
            if ok:
                detail = f"rejected as its own class (exit 1, {marker!r})"
            else:
                bits = [f"exit {rc}"]
                if not rejected:
                    bits.append("NOT a finding (only exit 1 rejects here)")
                if not attributed:
                    bits.append(f"marker {marker!r} absent — rejection unattributed")
                if not discriminates:
                    bits.append(f"marker {marker!r} also fires on the clean fixture")
                detail = ", ".join(bits)
            print(f"  {'✓' if ok else '✗'} {('MUTANT ' + mname):<18} {detail:<16} expected "
                  f"rejection attributed to this class — {mwhy}")

    layouts, muts = len(_SELFTEST_CASES), len(mutants)
    # THE MUTANT DENOMINATOR IS PRINTED EVEN WHEN IT IS ZERO. A gate that passes none says so on its
    # own verdict line, so no reader can mistake five layout ticks for proof that its rule rejects.
    mut_phrase = (f"{muts} mutant(s) of its own rule, each rejected as its own class"
                  if muts else
                  "0 mutants of its own rule — NOTHING HERE PROVES THIS GATE CAN STILL REJECT")
    line = (f"PASS: {name} discovers concepts in every permitted layout and refuses an empty "
            f"denominator ({layouts} fixtures); {mut_phrase}" if not bad else
            f"FAIL: {name} failed {bad} of {layouts + muts} assertion(s) "
            f"({layouts} layout fixtures + {muts} rule mutant(s))")
    print(line)
    return 1 if bad else 0
