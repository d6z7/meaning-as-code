#!/usr/bin/env python3
"""check_delivery_consistency.py — are the delivered components CONSISTENT WITH EACH OTHER?

WHY PRESENCE CHECKS ARE NOT ENOUGH, which is the whole argument for this file.
`mac_import` prints a 20-row state report and `check_first_run` asserts a bundle against a declared
contract. Both answer "is D10 present". Neither answers the operator's actual question, put on
2026-09-27: "i need quality checklist if all components of delivery ... like FKs have been delivered
and if they are consistent".

THE DIFFERENCE IS NOT ACADEMIC. Every defect found by hand that day was TWO DELIVERABLES
CONTRADICTING EACH OTHER while both were reported present:

  * D10 held 56 measured references and D4b held 0 edges           -> invariant FK-EDGE
  * the ER diagram drew 12 foreign keys and the ontology had none  -> invariant FK-EDGE
  * 19 concepts carried 141 field-role tokens resolving to nothing
    and `validate_schema` reported 80 of 80 files clean            -> invariant ROLE-VOCAB
  * 16 descriptors produced 8 profiles, unnoticed for hours        -> invariant PLANE-COUNTS
  * 21 concept samples drawn at ROW grain for 11 concepts that
    declare members, so a sample showed products instead of brands -> invariant MEMBER-GRAIN

A COMPLETE SET OF MUTUALLY CONTRADICTORY ARTIFACTS PASSES EVERY OTHER GATE THIS FRAMEWORK SHIPS.
That is the hole. Presence is reported separately from consistency below, because "all 20 present" and
"the 20 agree" are different claims and conflating them is how the above survived.

EVERY LINE CARRIES ITS DENOMINATOR. A verdict without one is this estate's own named defect — a PASS
over zero files. So each invariant prints what it examined, not merely that it passed.

EXIT 0 every invariant held · 1 at least one pair of deliverables disagrees · 2 could not run (no
bundle, no yaml). A could-not-run is never a verdict.

    python3 check_delivery_consistency.py <bundle-root> [--self-test]
"""

from __future__ import annotations

import argparse
import glob
import pathlib
import re
import sys

ACCEPTED_SHAPE = """\
This gate reads a bundle's DELIVERED artifacts and compares them with each other:

  data/sources/*.yaml            data/datasets/*.yaml         data/profiles/*.yaml
  data/references*/*.yaml        data/lookups/*.csv           ontology/concepts/**/*.yaml
  ontology/edges.yaml            ontology/samples/*.csv       acceptance/register_membership_runs.json

It needs no warehouse and no connector: every fact it compares has already been measured and written.
Run the import first — a bundle with no data plane has nothing to be consistent about.
"""


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE STATE — every artifact fact this gate compares, read once. PURE DATA, so every invariant below
# is a pure function of it and every reject class is reachable from the self-test with no bundle.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
def load(root: pathlib.Path, yaml) -> dict:
    def docs(pattern):
        out = {}
        for f in sorted(glob.glob(str(root / pattern), recursive=True)):
            p = pathlib.Path(f)
            try:
                out[p.stem] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except Exception:  # noqa: BLE001 - an unparsable artifact is a finding elsewhere
                out[p.stem] = {}
        return out

    served, sources = docs("data/datasets/*.yaml"), docs("data/sources/*.yaml")
    concepts = docs("ontology/concepts/**/*.yaml")
    refs = {}
    for plane in ("references_served", "references"):
        refs.update(docs(f"data/{plane}/*.yaml"))
    edges_doc = {}
    ef = root / "ontology" / "edges.yaml"
    if ef.is_file():
        try:
            edges_doc = yaml.safe_load(ef.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            edges_doc = {}

    # THE MEASURED FOREIGN KEYS, from the descriptors that carry them — both shapes, because the data
    # layer currently states them two ways and this gate must not prefer one (backlog item 2).
    fks = []
    for stem, d in {**served, **sources}.items():
        for c in d.get("columns") or []:
            tgt = str(c.get("references") or "").strip()
            if tgt and c.get("role") == "foreign_key":
                fks.append((stem, str(c.get("name")), tgt.split(".")[-1]))
        for fk in d.get("foreign_keys") or []:
            if isinstance(fk, dict) and fk.get("to_table"):
                fks.append((stem, str(fk.get("from_column")), str(fk["to_table"]).split(".")[-1]))

    return {
        "served": served, "sources": sources, "profiles": docs("data/profiles/*.yaml"),
        "concepts": concepts, "refs": refs,
        "edges": list(edges_doc.get("edges") or []),
        "fks": sorted(set(fks)),
        "registers": sorted(pathlib.Path(f).name
                            for f in glob.glob(str(root / "data" / "lookups" / "*.lookup.csv"))),
        "monitor": (root / "acceptance" / "register_membership_runs.json").is_file(),
        "concept_samples": sorted(pathlib.Path(f).stem.replace(".sample", "")
                                  for f in glob.glob(str(root / "ontology" / "samples" / "*.csv"))),
        "sample_run": (root / "ontology" / "samples" / "samples.run.json").is_file(),
        "vocab_ns": _declared_namespaces(root, yaml),
        # A DECLINE IS A DECISION, AND IT IS DELIVERED IN THE REGISTER. `DQ-UNCLAIMED-*` is raised for
        # a served relation no concept claims; once an operator rules it, the relation HAS been decided
        # about and this gate must stop asking. Without this the invariant is unsatisfiable: declining
        # is a legitimate answer and there would be nowhere to record it.
        "ruled_unclaimed": _ruled_unclaimed(root, yaml),
    }


def _ruled_unclaimed(root: pathlib.Path, yaml) -> set[str]:
    f = root / "data" / "quality" / "data_quality_register.yaml"
    if not f.is_file():
        return set()
    try:
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return set()
    out = set()
    for it in doc.get("issues") or []:
        if not str(it.get("id", "")).startswith("DQ-UNCLAIMED-"):
            continue
        if str(it.get("status") or "open") != "open" and it.get("ruled_by"):
            out.add(str(it["id"])[len("DQ-UNCLAIMED-"):].lower())
    return out


def _declared_namespaces(root: pathlib.Path, yaml) -> set[str]:
    """The application vocabularies this bundle DECLARES, from any vocabulary.yaml it carries.

    The resolver checks a `<ns>.<vocab>.<term>` reference only when `<ns>` is declared, so a bundle
    that declares nothing has every such token pass as an opaque string. Measured: 141 of them.
    """
    out = set()
    for f in glob.glob(str(root / "**" / "vocabulary.yaml"), recursive=True):
        try:
            doc = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        for key in ("namespace", "namespaces"):
            v = doc.get(key)
            if isinstance(v, str):
                out.add(v.lower())
            elif isinstance(v, (list, tuple)):
                out |= {str(x).lower() for x in v}
            elif isinstance(v, dict):
                out |= {str(k).lower() for k in v}
        out |= {str(k).lower() for k in doc if str(k).endswith("field_role")}
    return out


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE INVARIANTS. Each returns (examined, violations) — the DENOMINATOR first, because a verdict
# without one is a PASS over nothing.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
def inv_fk_edge(st: dict) -> tuple[int, list[str]]:
    """Every measured foreign key is an edge between concepts, or is stated as not one.

    THE DEFECT THIS CATCHES, MEASURED: 12 foreign keys on the descriptors, 0 edges in the ontology, and
    an ER diagram drawing all 12 because it reads the DATA plane. Both deliverables present, both
    internally correct, contradicting each other about whether the relations are related.
    """
    if not st["concepts"]:
        return 0, []          # no ontology plane: an edge cannot be owed yet
    ground = {}
    for name, d in st["concepts"].items():
        for s in (d.get("grounding") or {}).get("sources") or []:
            r = str(s.get("relation") or "").split(".")[-1]
            if r:
                ground.setdefault(r, set()).add(name)
    edged = set()
    for e in st["edges"]:
        eps = e.get("endpoints") or {}
        pair = (str(eps.get("from") or e.get("from") or ""), str(eps.get("to") or e.get("to") or ""))
        edged.add(pair)
        edged.add(str(e.get("edge_id") or ""))
    bad = []
    examined = 0
    for rel, col, tgt in st["fks"]:
        if rel not in ground or tgt not in ground:
            continue          # one end is not modelled; that is invariant CONCEPT-RELATION's business
        examined += 1
        token = f"{rel}__{col}__to__{tgt}"
        if token in edged:
            continue
        if any(token in str(x) for x in edged):
            continue
        bad.append(f"{rel}.{col} -> {tgt} is a MEASURED foreign key between two modelled concepts "
                   f"and no edge in ontology/edges.yaml joins them")
    return examined, bad


def inv_concept_relation(st: dict) -> tuple[int, list[str]]:
    """Every concept grounds on a relation the data plane describes, and every served relation is
    either claimed by a concept or declined in writing."""
    if not st["concepts"]:
        return 0, []
    known = set(st["served"]) | set(st["sources"])
    bad, examined = [], 0
    claimed = set()
    for name, d in st["concepts"].items():
        for s in (d.get("grounding") or {}).get("sources") or []:
            r = str(s.get("relation") or "").split(".")[-1]
            if not r:
                continue
            examined += 1
            claimed.add(r)
            if r not in known:
                bad.append(f"concept {name!r} grounds on {r!r}, which no descriptor in data/datasets "
                           f"or data/sources describes")
    for r in sorted(set(st["served"]) - claimed):
        examined += 1
        if r.lower() in st.get("ruled_unclaimed", set()):
            continue          # declined in writing, with a ruling: a decision, not a gap
        bad.append(f"served relation {r!r} is claimed by no concept and declined by nothing — a "
                   f"relation nobody decided about. Rule DQ-UNCLAIMED-{r.upper()} in the data-quality "
                   f"register to record the decision, declining included")
    return examined, bad


def inv_role_vocab(st: dict) -> tuple[int, list[str]]:
    """Every namespaced field_role resolves in a vocabulary this bundle DECLARES.

    THE DEFECT THIS CATCHES, MEASURED: 141 `CONTOSO4.field_role.*` tokens in 19 concepts, resolving to
    nothing, because no vocabulary.yaml declared the namespace — and the resolver only checks DECLARED
    namespaces, so `check_references` reported 0 errors and `validate_schema` 80 of 80 files clean. An
    undeclared namespace must be an ERROR, never silence.
    """
    bad, examined = [], 0
    pat = re.compile(r"^([A-Za-z0-9_]+)\.field_role\.[A-Za-z0-9_]+$")
    for name, d in st["concepts"].items():
        for col, role in ((d.get("grounding") or {}).get("field_roles") or {}).items():
            examined += 1
            m = pat.match(str(role))
            if not m:
                continue
            ns = m.group(1).lower()
            if ns == "mac":
                continue      # the projection's own default namespace
            if ns not in st["vocab_ns"]:
                bad.append(f"concept {name!r} column {col!r} carries role {role!r}, and namespace "
                           f"{ns!r} is declared by no vocabulary.yaml — the token resolves to nothing "
                           f"and no resolver will say so")
    return examined, bad


def inv_member_grain(st: dict) -> tuple[int, list[str]]:
    """A concept whose extension is a SET OF VALUES has a sample at member grain, not row grain.

    THE DEFECT THIS CATCHES, MEASURED: 11 of 19 concepts declared `values:`/`members:` and drew at ROW
    grain because the canonical key was on the column and the sampler read `concept.identity`. Brand's
    sample came out as 40 product rows. The DNA calls this artifact "the only artifact that shows what a
    concept CONTAINS"; a sample of host rows shows what it sits ON.
    """
    bad, examined = [], 0
    for name, d in st["concepts"].items():
        declares = bool(d.get("values") or d.get("members"))
        if not declares:
            continue
        examined += 1
        ident = str(((d.get("concept") or {}).get("identity") or {}).get("canonical_key") or "").strip()
        if not ident:
            for s in (d.get("grounding") or {}).get("sources") or []:
                cols = s.get("columns")
                if isinstance(cols, dict):
                    for cn, body in cols.items():
                        if isinstance(body, dict) and str(body.get("identity") or "") == "canonical":
                            ident = str(cn)
                            break
                if ident:
                    break
        if not ident:
            bad.append(f"concept {name!r} declares its extension as a SET (values/members) and names "
                       f"no canonical key anywhere — neither concept.identity.canonical_key nor a "
                       f"column with `identity: canonical` — so its sample can only be drawn at ROW "
                       f"grain and will show its host's rows instead of its own members")
    return examined, bad


def inv_register_monitor(st: dict) -> tuple[int, list[str]]:
    """Every register has a monitor result, and every descriptor pointer names a register that exists."""
    bad, examined = [], 0
    if st["registers"]:
        examined += 1
        if not st["monitor"]:
            bad.append(f"{len(st['registers'])} register(s) are delivered and "
                       f"acceptance/register_membership_runs.json does not exist — a closed set with no "
                       f"monitor is a claim nothing re-measures (DNA 1.8)")
    have = set(st["registers"])
    for stem, d in {**st["served"], **st["sources"]}.items():
        for c in d.get("columns") or []:
            reg = str(c.get("register") or "").strip()
            if not reg:
                continue
            examined += 1
            if pathlib.Path(reg).name not in have:
                bad.append(f"{stem}.{c.get('name')} points at register {reg!r}, which is not in "
                           f"data/lookups — the pointer resolves to nothing")
    return examined, bad


def inv_plane_counts(st: dict) -> tuple[int, list[str]]:
    """A descriptor has a profile. Measured once at 16 descriptors and 8 profiles, for hours."""
    desc = len(st["served"]) + len(st["sources"])
    if not desc:
        return 0, []
    prof = len(st["profiles"])
    if prof == desc:
        return desc, []
    return desc, [f"{desc} descriptor(s) across both planes and {prof} profile(s): every described "
                  f"relation is supposed to be measured, and {desc - prof} "
                  f"{'is' if desc - prof == 1 else 'are'} not. A shared stem across the two planes "
                  f"makes the profile ambiguous and the shortfall silent"]


def inv_register_orphan(st: dict) -> tuple[int, list[str]]:
    """Every delivered register is pointed at by at least one descriptor column.

    THE DEFECT THIS CATCHES, MEASURED: 23 registers on disk and 0 `register:` pointers, because
    re-running `mac_descriptors` regenerated the descriptors and wiped the enrichment `mac_lookups` had
    added. Both deliverables present — 23 registers, 16 descriptors — and nothing connects them, so
    nothing can resolve a code to a label through a register that exists.

    It is the inverse of REGISTER-MONITOR's pointer check: that one catches a pointer with no file,
    this one a file with no pointer. A register nobody points at is a file, not a register.
    """
    if not st["registers"]:
        return 0, []
    pointed = set()
    for d in {**st["served"], **st["sources"]}.values():
        for c in d.get("columns") or []:
            reg = str(c.get("register") or "").strip()
            if reg:
                pointed.add(pathlib.Path(reg).name)
    orphans = sorted(set(st["registers"]) - pointed)
    if not orphans:
        return len(st["registers"]), []
    shown = ", ".join(orphans[:4]) + (f" … and {len(orphans) - 4} more" if len(orphans) > 4 else "")
    return len(st["registers"]), [
        f"{len(orphans)} of {len(st['registers'])} register(s) are pointed at by no descriptor column, "
        f"so nothing can resolve a code through them: {shown}"
        + ("  — ALL of them, which is what a descriptor regeneration looks like: it rewrites the file "
           "and drops the register pointers a later stage had added" if len(orphans) == len(st["registers"])
           else "")]


INVARIANTS = (
    ("FK-EDGE", "a measured foreign key between modelled concepts is an edge", inv_fk_edge),
    ("CONCEPT-RELATION", "a concept grounds on a described relation; a served relation is decided about",
     inv_concept_relation),
    ("ROLE-VOCAB", "a namespaced field_role resolves in a declared vocabulary", inv_role_vocab),
    ("MEMBER-GRAIN", "a concept whose extension is a set names a canonical key", inv_member_grain),
    ("REGISTER-MONITOR", "a register has a monitor; a register pointer resolves", inv_register_monitor),
    ("PLANE-COUNTS", "a described relation is a measured relation", inv_plane_counts),
    ("REGISTER-ORPHAN", "a delivered register is pointed at by a descriptor", inv_register_orphan),
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    try:
        import yaml
    except ImportError as exc:
        print(f"COULD NOT RUN: {exc}\n\n{ACCEPTED_SHAPE}")
        return 2
    if not (root / "data").is_dir():
        print(f"COULD NOT RUN: {root.name} has no data/ plane, so there is nothing to be consistent "
              f"about. This is not a pass.\n\n{ACCEPTED_SHAPE}")
        return 2

    st = load(root, yaml)
    print(f"  DELIVERY CONSISTENCY — {root.name}\n"
          f"  presence is not consistency: {len(st['served'])} served + {len(st['sources'])} raw "
          f"descriptor(s), {len(st['profiles'])} profile(s), {len(st['concepts'])} concept(s), "
          f"{len(st['edges'])} edge(s), {len(st['fks'])} measured FK(s), "
          f"{len(st['registers'])} register(s)\n")
    total_bad, checked = 0, 0
    for code, what, fn in INVARIANTS:
        examined, bad = fn(st)
        checked += 1
        mark = "ok  " if not bad else "FAIL"
        over = f"over {examined}" if examined else "NOTHING TO CHECK"
        print(f"  [{mark}] {code:17} {what:58} {over}")
        for b in bad[:6]:
            print(f"         - {b}")
        if len(bad) > 6:
            print(f"         … and {len(bad) - 6} more")
        total_bad += len(bad)

    if total_bad:
        print(f"\nFAIL: check_delivery_consistency — {total_bad} inconsistenc"
              f"{'y' if total_bad == 1 else 'ies'} across {checked} invariant(s): deliverables that "
              f"are PRESENT and disagree with each other")
        return 1
    print(f"\nPASS: check_delivery_consistency — {checked} invariant(s) hold; the delivered "
          f"components agree with one another")
    return 0


def _self_test() -> int:
    """One mutant per invariant plus a clean fixture (CORE.md §2), every case a pure dict."""
    def base() -> dict:
        return {
            "served": {"v_s": {"columns": [{"name": "CK", "role": "foreign_key",
                                            "references": "v_c"}]},
                       "v_c": {"columns": [{"name": "CK", "role": "primary_key"},
                                            {"name": "B", "role": "value",
                                             "register": "data/lookups/b_x.lookup.csv"}]}},
            "sources": {},
            "profiles": {"v_s": {}, "v_c": {}},
            "concepts": {
                "line": {"grounding": {"sources": [{"relation": "v_s", "columns": {"CK": {"role": "key"}}}],
                                       "field_roles": {"CK": "mac.field_role.key"}}},
                "cust": {"grounding": {"sources": [{"relation": "v_c"}]}},
            },
            "refs": {}, "edges": [{"edge_id": "v_s__CK__to__v_c"}],
            "fks": [("v_s", "CK", "v_c")],
            "registers": ["b_x.lookup.csv"], "monitor": True,
            "concept_samples": ["line"], "sample_run": True, "vocab_ns": set(),
            "ruled_unclaimed": set(),
        }
    cases = []

    def case(label, mutate, expect_code):
        st = base()
        mutate(st)
        got = {c: fn(st)[1] for c, _w, fn in INVARIANTS}
        failing = sorted(c for c, v in got.items() if v)
        cases.append((label, failing == ([expect_code] if expect_code else []), failing, expect_code))

    case("CLEAN FIXTURE must hold every invariant", lambda st: None, None)
    case("MUTANT a measured FK with no edge", lambda st: st.update(edges=[]), "FK-EDGE")
    case("CLEAN a served relation declined BY A RULING is decided about, not a gap",
         lambda st: (st["concepts"].pop("cust"),
                     st.update(ruled_unclaimed={"v_c"})), None)
    case("MUTANT a served relation with no concept and no ruling",
         lambda st: st["concepts"].pop("cust"), "CONCEPT-RELATION")
    case("MUTANT a concept grounds on an undescribed relation",
         lambda st: st["concepts"].__setitem__(
             "ghost", {"grounding": {"sources": [{"relation": "nope"}]}}), "CONCEPT-RELATION")
    case("MUTANT an undeclared vocabulary namespace",
         lambda st: st["concepts"]["line"]["grounding"]["field_roles"].__setitem__(
             "CK", "CONTOSO4.field_role.key"), "ROLE-VOCAB")
    case("MUTANT a set-extension concept with no canonical key",
         lambda st: st["concepts"]["cust"].update(values={"closure": "closed", "items": []}),
         "MEMBER-GRAIN")
    case("MUTANT registers with no monitor result", lambda st: st.update(monitor=False),
         "REGISTER-MONITOR")
    case("MUTANT a register pointer that resolves to nothing",
         lambda st: st["served"]["v_c"]["columns"].append(
             {"name": "X", "role": "value", "register": "data/lookups/missing.lookup.csv"}),
         "REGISTER-MONITOR")
    case("MUTANT a descriptor with no profile", lambda st: st["profiles"].pop("v_c"),
         "PLANE-COUNTS")
    # THE INVERSE OF THE POINTER CHECK: a register file nobody points at. Measured at 23 of 23.
    case("MUTANT a register nobody points at",
         lambda st: st["served"]["v_c"].__setitem__(
             "columns", [c for c in st["served"]["v_c"]["columns"] if not c.get("register")]),
         "REGISTER-ORPHAN")
    # THE COMBINATION IS THE REAL CASE: today's bundle broke three at once, and a gate that stops at
    # the first would have reported one third of the truth.
    st = base()
    st["edges"] = []
    st["profiles"].pop("v_c")
    st["concepts"]["line"]["grounding"]["field_roles"]["CK"] = "CONTOSO4.field_role.key"
    failing = sorted(c for c, _w, fn in INVARIANTS if fn(st)[1])
    cases.append(("MUTANT three disagreements are reported as THREE, not one",
                  failing == ["FK-EDGE", "PLANE-COUNTS", "ROLE-VOCAB"], failing,
                  "FK-EDGE+PLANE-COUNTS+ROLE-VOCAB"))

    bad = [(lbl, got, want) for lbl, ok, got, want in cases if not ok]
    for lbl, got, want in bad:
        print(f"  FAIL  {lbl}\n        expected {want!r}, got {got!r}")
    n = len(cases)
    if bad:
        print(f"\nFAIL: check_delivery_consistency self-test — {len(bad)} of {n} case(s) failed")
        return 1
    print(f"PASS: check_delivery_consistency self-test — {n}/{n} case(s): one mutant per invariant "
          f"({', '.join(c for c, _w, _f in INVARIANTS)}), a register pointer that resolves to nothing, "
          f"three simultaneous disagreements reported as three, and a clean fixture that must hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
