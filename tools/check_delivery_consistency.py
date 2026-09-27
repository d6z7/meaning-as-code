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
import json
import pathlib
import re
import sys
from datetime import UTC, datetime

#: THE RUN RECORD, bundle-relative. ONE HOME for this path: the gate writes here, the console route
#: reads here, and a scheduled job looks here. Three copies of a filename is three chances to drift.
RUNS_REL = "acceptance/delivery_consistency_runs.json"

# ONE RESOLVER, NOT TWO. FK-EDGE must know which concept claims which column, and so must the edge
# PRODUCER. Two implementations of that would drift — which is the defect class this whole checklist
# exists to find, and which produced three edges reading `Currency -> Region` — so the gate imports the
# producer's own function. Unavailable, it REFUSES (exit 2); a gate that cannot resolve must not pass.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
try:
    from sdk.authoring.edges import concept_index as _concept_index
except ImportError:  # pragma: no cover - reported by main(), never guessed around
    _concept_index = None

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
# --------------------------------------------------------------------------------------------- #
# THE ENUMERATION CONTRACT. Every invariant returns a LIST OF ITEMS — one per subject it looked at —
# and the counts are derived from that list rather than tallied beside it.
#
# THE DEFECT THIS REPAIRS, IN THE OPERATOR'S OWN WORDS (2026-09-27), reading the console:
#
#     "test if FK is over 3 ... this is not satisfying ... i expect you to enumerate all and then
#      check if passing"
#
# They were right, and the row they were looking at was the proof. contoso4 carries TWELVE measured
# foreign keys. FK-EDGE reported "over 3" and passed, because its loop did `continue` on any key whose
# ends were not both modelled and counted only the survivors. Nine of twelve were dropped BEFORE the
# denominator was formed, so the number on screen was a slice of the population presented as the
# population — the same defect as a gate reporting PASS over zero files, one level in. Two more rows
# did it too: MEMBER-GRAIN narrowed 19 concepts to 10, ROLE-VOCAB narrowed every concept to nothing.
#
# SO A SUBJECT MAY BE EXCLUDED, BUT NOT SILENTLY. `n/a` is a verdict, it is counted, and it carries the
# REASON it did not apply — which means the reader can audit the exclusion instead of taking it on
# trust. An invariant can no longer shrink its own population off-screen: the denominator IS the list.
#
#   ok         the subject was checked and it held
#   violation  the subject was checked and two delivered components disagree about it
#   n/a        the subject was enumerated and NOT checked, and `note` says why
# --------------------------------------------------------------------------------------------- #

OK, VIOLATION, NA = "ok", "violation", "n/a"


def _i(subject: str, verdict: str, note: str = "") -> dict:
    """One enumerated subject. `subject` is a name a human can look up in the bundle, never an index."""
    return {"subject": subject, "verdict": verdict, "note": note}


def violations(items: list[dict]) -> list[str]:
    """The notes of the failing items, in enumeration order — what the CLI prints and the record carries."""
    return [i["note"] for i in items if i["verdict"] == VIOLATION]


def counts(items: list[dict]) -> tuple[int, int, int, int]:
    """(enumerated, held, failed, not_applicable). `held` is the REMAINDER, so the four can never sum
    to anything but the list's own length — the arithmetic cannot drift from the enumeration."""
    failed = sum(1 for i in items if i["verdict"] == VIOLATION)
    na = sum(1 for i in items if i["verdict"] == NA)
    return len(items), len(items) - failed - na, failed, na


def inv_fk_edge(st: dict) -> list[dict]:
    """Every measured foreign key that a modelled concept references through is an edge.

    THE DEFECT THIS CATCHES, MEASURED: 12 foreign keys on the descriptors, 0 edges in the ontology, and
    an ER diagram drawing all 12 because it reads the DATA plane. Both deliverables present, both
    internally correct, contradicting each other about whether the relations are related.

    AND THE DEFECT THIS INVARIANT ITSELF HAD, found 2026-09-27. It matched a token built from the
    RELATION and COLUMN (`sales__CustomerKey__to__customer`) against the edge ids, and so it passed on
    three edges whose endpoint CONCEPTS were `Currency -> Region`, `Currency -> Region` and
    `Currency -> ProductColor` — nonsense produced by a lift that kept one concept per relation while
    four ground on the sales relation. A structural match on a name is not a check on a claim: the
    edges were present, grammar-clean, and said nothing true. It now resolves the CONCEPTS on both
    ends and requires an edge between THOSE.

    IT ENUMERATES PER (CONCEPT, FOREIGN KEY) PAIR, not per foreign key, because one FK legitimately
    fans out: OrderLine, Order and SalesAmount all reference Customer through sales.CustomerKey and all
    three are true. An FK whose relation backs no concept is listed as STRUCTURAL rather than dropped —
    "9 of these were not checked, and here is why" is a fact about ontology coverage.
    """
    if not st["fks"]:
        return []
    idx = st.get("concept_index") or {}
    if not st["concepts"]:
        return [_i(f"{rel}.{col} -> {tgt}", NA,
                   f"{rel}.{col} -> {tgt} is measured, and this bundle has no ontology plane yet, so no "
                   f"edge can be owed. Authoring concepts is what makes this checkable")
                for rel, col, tgt in st["fks"]]
    # An edge is identified by the PAIR OF CONCEPTS it joins, never by its id — the id is a convenience
    # and the previous version's whole failure was trusting it.
    joined = set()
    for e in st["edges"]:
        eps = e.get("endpoints") or {}
        f = str((eps.get("from") or {}).get("concept") or e.get("from") or "")
        t = str((eps.get("to") or {}).get("concept") or e.get("to") or "")
        if f and t:
            joined.add((f, t))
    ruled = st.get("ruled_unclaimed") or set()
    out = []
    for rel, col, tgt in st["fks"]:
        subject = f"{rel}.{col} -> {tgt}"
        here, there = idx.get(rel) or [], idx.get(tgt) or []
        if not here or not there:
            loose = [r for r, c in ((rel, here), (tgt, there)) if not c]
            why = []
            for r in loose:
                if r in st["sources"] and r not in st["served"]:
                    why.append(f"{r!r} is a RAW landing and concepts ground on the served plane, so a "
                               f"raw foreign key can never be an edge between concepts (structural)")
                elif r.lower() in ruled:
                    why.append(f"{r!r} backs no concept and is DECLINED BY A RULING — a decision on "
                               f"the record, so no edge is owed")
                else:
                    why.append(f"{r!r} backs no concept AND is declined by nothing — a coverage gap, "
                               f"which invariant CONCEPT-RELATION reports as a violation")
            out.append(_i(subject, NA, f"{subject} owes no edge: " + "; ".join(why)))
            continue
        claimants = sorted(c["name"] for c in here if col in c["references"])
        # THE REFERENCED COLUMN IS THE REFERRING COLUMN'S NAME — this warehouse's convention, and what
        # `mac_references` measured. A concept on the target keyed on that name is the destination.
        targets = sorted(c["name"] for c in there if c["canonical_key"] == col)
        if not claimants:
            out.append(_i(subject, NA,
                          f"{subject} is measured and no concept on {rel!r} declares {col!r} with "
                          f"`identity: reference`, so no notion references through it and no edge is "
                          f"owed. The concepts on {rel!r} are "
                          f"{', '.join(sorted(c['name'] for c in here))}"))
            continue
        if len(targets) != 1:
            out.append(_i(subject, VIOLATION,
                          f"{subject} is referenced by {', '.join(claimants)}, and the target relation "
                          f"{tgt!r} has {len(targets)} concept(s) taking the referenced column as a "
                          f"canonical key ({', '.join(targets) or 'none'}) — so the edge has no single "
                          f"destination and the reference resolves to nothing"))
            continue
        to = targets[0]
        for frm in claimants:
            pair = f"{frm} -> {to}"
            if frm == to:
                continue
            if (frm, to) in joined:
                out.append(_i(pair, OK, f"{pair} is joined by an edge in ontology/edges.yaml "
                                        f"(measured through {rel}.{col})"))
            else:
                out.append(_i(pair, VIOLATION,
                              f"{frm!r} references {to!r} through the MEASURED foreign key "
                              f"{rel}.{col} and no edge in ontology/edges.yaml joins those two "
                              f"concepts"))
    return out


def inv_concept_relation(st: dict) -> list[dict]:
    """Every concept grounds on a relation the data plane describes, and every served relation is
    either claimed by a concept or declined in writing."""
    if not st["concepts"]:
        return []
    known = set(st["served"]) | set(st["sources"])
    out, claimed = [], set()
    for name, d in st["concepts"].items():
        for src in (d.get("grounding") or {}).get("sources") or []:
            r = str(src.get("relation") or "").split(".")[-1]
            if not r:
                continue
            claimed.add(r)
            subject = f"{name} grounds on {r}"
            if r in known:
                out.append(_i(subject, OK, f"concept {name!r} grounds on {r!r}, which a descriptor describes"))
            else:
                out.append(_i(subject, VIOLATION,
                              f"concept {name!r} grounds on {r!r}, which no descriptor in data/datasets "
                              f"or data/sources describes"))
    for r in sorted(set(st["served"]) - claimed):
        subject = f"served relation {r}"
        if r.lower() in st.get("ruled_unclaimed", set()):
            out.append(_i(subject, OK,
                          f"served relation {r!r} is claimed by no concept and DECLINED BY A RULING — "
                          f"a decision on the record, not a gap"))
        else:
            out.append(_i(subject, VIOLATION,
                          f"served relation {r!r} is claimed by no concept and declined by nothing — a "
                          f"relation nobody decided about. Rule DQ-UNCLAIMED-{r.upper()} in the "
                          f"data-quality register to record the decision, declining included"))
    return out


#: THE CONCEPT COLUMN MAP'S CLOSED ROLE SET, mirroring mac.schema.json's enum for the same slot. Two
#: homes for one vocabulary is a risk, and the alternative is worse: this module would have to load and
#: walk the JSON schema to check a four-member set. The SELF-TEST pins them together instead, so a change
#: to either side that is not made to both goes red rather than silent.
COLUMN_ROLES = ("key", "dimension", "measure", "attribute")

_ROLE_TOKEN = re.compile(r"^([A-Za-z0-9_]+)\.field_role\.[A-Za-z0-9_]+$")
_NS_TOKEN = re.compile(r"^([A-Za-z0-9_]+)\.[A-Za-z0-9_.]+$")


def _ns_ok(ns: str, st: dict) -> bool:
    """`mac` is the projection's own namespace and always resolves; anything else must be DECLARED."""
    return ns.lower() == "mac" or ns.lower() in st["vocab_ns"]


def inv_role_vocab(st: dict) -> list[dict]:
    """Every role declaration resolves — a namespaced token in a DECLARED vocabulary, a bare role in the
    closed set.

    THE DEFECT THIS WAS BUILT FOR, MEASURED: 141 `CONTOSO4.field_role.*` tokens in 19 concepts resolving
    to nothing, because no vocabulary.yaml declared the namespace — and the resolver only checks DECLARED
    namespaces, so `check_references` reported 0 errors and `validate_schema` 80 of 80 files clean. An
    undeclared namespace must be an ERROR, never silence.

    AND THE DEFECT IT ITSELF HAD, found 2026-09-27 the moment the verdict line stopped overstating: it
    read ONLY `grounding.field_roles`, which **0 of 19** concepts write on the current standard, while 19
    carry the column map with **142** `role:` declarations. So the invariant built to catch that class of
    silence had gone permanently vacuous — a consumer reading a shape no producer writes, which is the
    same defect as the `foreign_keys:` block the operator ruled on the same day, inside the checker.

    IT READS BOTH SHAPES NOW. `field_roles` is still enumerated, because a legacy bundle must stay
    checked rather than silently skipped — that is how coverage collapses behind a perfect fraction.
    """
    out = []
    for name, d in sorted(st["concepts"].items()):
        g = d.get("grounding") or {}
        # ── the LEGACY shape: a projected, namespaced token ──────────────────────────────────────
        for col, role in (g.get("field_roles") or {}).items():
            subject = f"{name}.{col} field_role"
            m = _ROLE_TOKEN.match(str(role))
            if not m:
                out.append(_i(subject, NA,
                              f"concept {name!r} column {col!r} carries field_role {role!r}, which names "
                              f"no namespace, so there is no vocabulary for it to resolve in"))
            elif _ns_ok(m.group(1), st):
                out.append(_i(subject, OK, f"{subject} carries {role!r} in a declared namespace"))
            else:
                out.append(_i(subject, VIOLATION,
                              f"concept {name!r} column {col!r} carries role {role!r}, and namespace "
                              f"{m.group(1).lower()!r} is declared by no vocabulary.yaml — the token "
                              f"resolves to nothing and no resolver will say so"))
        # ── the CURRENT shape: the column map ───────────────────────────────────────────────────
        for src in g.get("sources") or []:
            cols = src.get("columns")
            if not isinstance(cols, dict):
                continue      # the array form carries no flags; MEMBER-GRAIN and FK-EDGE cover it
            rel = str(src.get("relation") or "?").split(".")[-1]
            for col, body in cols.items():
                if not isinstance(body, dict):
                    continue  # `null` means "serve it and say nothing more" — a declaration of silence
                subject = f"{name}.{rel}.{col} role"
                role = body.get("role")
                if role is None:
                    out.append(_i(subject, NA,
                                  f"concept {name!r} column {col!r} on {rel!r} declares flags but no "
                                  f"`role`, so there is no role token to resolve"))
                    continue
                token = str(role)
                if "." in token:
                    m = _NS_TOKEN.match(token)
                    if m and _ns_ok(m.group(1), st):
                        out.append(_i(subject, OK, f"{subject} carries {token!r} in a declared namespace"))
                    else:
                        ns = m.group(1).lower() if m else token
                        out.append(_i(subject, VIOLATION,
                                      f"concept {name!r} column {col!r} on {rel!r} carries role {token!r} "
                                      f"and namespace {ns!r} is declared by no vocabulary.yaml — the "
                                      f"token resolves to nothing and no resolver will say so"))
                elif token in COLUMN_ROLES:
                    out.append(_i(subject, OK, f"{subject} is {token!r}, a member of the closed set"))
                else:
                    out.append(_i(subject, VIOLATION,
                                  f"concept {name!r} column {col!r} on {rel!r} carries role {token!r}, "
                                  f"which is in neither the closed column-role set "
                                  f"({', '.join(COLUMN_ROLES)}) nor any declared namespace. A role "
                                  f"nothing recognises places no predicate and no resolver will say so"))
    return out


def inv_member_grain(st: dict) -> list[dict]:
    """A concept whose extension is a SET OF VALUES has a canonical key, so its sample can be drawn at
    member grain rather than row grain.

    THE DEFECT THIS CATCHES, MEASURED: 11 of 19 concepts declared `values:`/`members:` and drew at ROW
    grain because the canonical key was on the column and the sampler read `concept.identity`. Brand's
    sample came out as 40 product rows. The DNA calls this artifact "the only artifact that shows what a
    concept CONTAINS"; a sample of host rows shows what it sits ON.

    EVERY CONCEPT IS ENUMERATED, not only the ones that declare a set — so "10 of 19 were checked" is
    on the page instead of a bare 10, and a reader can see which nine were excluded and why.
    """
    out = []
    for name, d in st["concepts"].items():
        if not (d.get("values") or d.get("members")):
            out.append(_i(name, NA,
                          f"concept {name!r} does not declare its extension as a set (no values/members), "
                          f"so no member-grain sample is owed and no canonical key is required here"))
            continue
        ident = str(((d.get("concept") or {}).get("identity") or {}).get("canonical_key") or "").strip()
        if not ident:
            for src in (d.get("grounding") or {}).get("sources") or []:
                cols = src.get("columns")
                if isinstance(cols, dict):
                    for cn, body in cols.items():
                        if isinstance(body, dict) and str(body.get("identity") or "") == "canonical":
                            ident = str(cn)
                            break
                if ident:
                    break
        if ident:
            out.append(_i(name, OK, f"concept {name!r} declares a set extension and names {ident!r} as "
                                    f"its canonical key, so its sample can be drawn at member grain"))
        else:
            out.append(_i(name, VIOLATION,
                          f"concept {name!r} declares its extension as a SET (values/members) and names "
                          f"no canonical key anywhere — neither concept.identity.canonical_key nor a "
                          f"column with `identity: canonical` — so its sample can only be drawn at ROW "
                          f"grain and will show its host's rows instead of its own members"))
    return out


def inv_register_monitor(st: dict) -> list[dict]:
    """Every register has a monitor result, and every descriptor pointer names a register that exists."""
    out = []
    if st["registers"]:
        if st["monitor"]:
            out.append(_i("the monitor result itself", OK,
                          f"{len(st['registers'])} register(s) are delivered and "
                          f"acceptance/register_membership_runs.json exists to re-measure their closure"))
        else:
            out.append(_i("the monitor result itself", VIOLATION,
                          f"{len(st['registers'])} register(s) are delivered and "
                          f"acceptance/register_membership_runs.json does not exist — a closed set with no "
                          f"monitor is a claim nothing re-measures (DNA 1.8)"))
    have = set(st["registers"])
    for stem, d in {**st["served"], **st["sources"]}.items():
        for c in d.get("columns") or []:
            reg = str(c.get("register") or "").strip()
            if not reg:
                continue
            subject = f"{stem}.{c.get('name')} -> {pathlib.Path(reg).name}"
            if pathlib.Path(reg).name in have:
                out.append(_i(subject, OK, f"{stem}.{c.get('name')} points at register {reg!r}, which is "
                                           f"in data/lookups"))
            else:
                out.append(_i(subject, VIOLATION,
                              f"{stem}.{c.get('name')} points at register {reg!r}, which is not in "
                              f"data/lookups — the pointer resolves to nothing"))
    return out


def inv_plane_counts(st: dict) -> list[dict]:
    """A descriptor has a profile. Measured once at 16 descriptors and 8 profiles, for hours.

    ENUMERATED PER DESCRIPTOR, and that is a straight improvement on the count comparison it replaces:
    `16 described and 8 measured` told an operator a number was wrong without telling them WHICH, so
    the shortfall stayed abstract. Each descriptor now names itself, and the stem shared across both
    planes — the thing that makes one profile answer for two descriptors — is its own enumerated item
    rather than a sentence appended to an aggregate.
    """
    out = []
    prof = set(st["profiles"])
    shared = set(st["served"]) & set(st["sources"])
    for plane, table in (("served", st["served"]), ("raw", st["sources"])):
        for stem in sorted(table):
            subject = f"{plane}:{stem}"
            if stem not in prof:
                out.append(_i(subject, VIOLATION,
                              f"{plane} descriptor {stem!r} describes a relation and data/profiles has no "
                              f"profile for it: every described relation is supposed to be measured"))
            elif stem in shared:
                out.append(_i(subject, VIOLATION,
                              f"stem {stem!r} is described on BOTH planes, so one profile answers for two "
                              f"descriptors — the profile is ambiguous and any shortfall it hides is "
                              f"silent. Rename one plane's relation so each descriptor has its own"))
            else:
                out.append(_i(subject, OK, f"{plane} descriptor {stem!r} has a profile in data/profiles"))
    return out


def inv_register_orphan(st: dict) -> list[dict]:
    """Every delivered register is pointed at by at least one descriptor column.

    THE DEFECT THIS CATCHES, MEASURED: 23 registers on disk and 0 `register:` pointers, because
    re-running `mac_descriptors` regenerated the descriptors and wiped the enrichment `mac_lookups` had
    added. Both deliverables present — 23 registers, 16 descriptors — and nothing connects them, so
    nothing can resolve a code to a label through a register that exists.

    It is the inverse of REGISTER-MONITOR's pointer check: that one catches a pointer with no file,
    this one a file with no pointer. A register nobody points at is a file, not a register.

    EACH REGISTER NAMES ITSELF. The previous version printed four orphans and "… and 19 more", which is
    the one thing a reader cannot act on: the 19 unnamed ones are exactly the work.
    """
    pointed = set()
    for d in {**st["served"], **st["sources"]}.values():
        for c in d.get("columns") or []:
            reg = str(c.get("register") or "").strip()
            if reg:
                pointed.add(pathlib.Path(reg).name)
    total = len(st["registers"])
    out = []
    for reg in sorted(st["registers"]):
        if reg in pointed:
            out.append(_i(reg, OK, f"register {reg!r} is pointed at by at least one descriptor column"))
        else:
            out.append(_i(reg, VIOLATION,
                          f"register {reg!r} is pointed at by no descriptor column, so nothing can "
                          f"resolve a code through it"
                          + (f" — and NONE of the {total} registers is pointed at, which is what a "
                             f"descriptor regeneration looks like: it rewrites the file and drops the "
                             f"register pointers a later stage had added" if not pointed else "")))
    return out


INVARIANTS = (
    # The wording follows the invariant: it checks a (CONCEPT, foreign key) pair, not a foreign key,
    # because one FK fans out to every concept that references through it.
    ("FK-EDGE", "a concept referencing through a measured FK has an edge to its target", inv_fk_edge),
    ("CONCEPT-RELATION", "a concept grounds on a described relation; a served relation is decided about",
     inv_concept_relation),
    # The wording widened with the invariant: it read only `field_roles` and now reads the column map
    # too, where most roles are BARE words checked against a closed set rather than namespaced tokens.
    # A row that describes less than it checks is how a reader comes to trust the wrong denominator.
    ("ROLE-VOCAB", "every column role resolves: closed set, or a declared namespace", inv_role_vocab),
    ("MEMBER-GRAIN", "a concept whose extension is a set names a canonical key", inv_member_grain),
    ("REGISTER-MONITOR", "a register has a monitor; a register pointer resolves", inv_register_monitor),
    ("PLANE-COUNTS", "a described relation is a measured relation", inv_plane_counts),
    ("REGISTER-ORPHAN", "a delivered register is pointed at by a descriptor", inv_register_orphan),
)


def _summary(invariants: int, vacuous: int, total_bad: int) -> str:
    """THE LAST LINE, AND IT MAY NOT OVERSTATE. Operator ruling 2026-09-27 on backlog item 8.

    THE DEFECT: `PASS: 7 invariant(s) hold` was printed on contoso2 and contoso3, where FOUR of the
    seven had nothing to check — neither bundle has an ontology plane, so "does every concept ground on
    a described relation" has no concepts to ask about. Nothing was broken and nothing was hidden: the
    four genuinely had no subject. But it was the IDENTICAL SENTENCE contoso4 gets, where all seven ran
    against 12 foreign keys, 19 concepts and 23 registers, so the verdict line could not tell a full
    pass from a hollow one. The console already drew those rows as unchecked and never green; the CLI
    and the record were the halves that lagged.

    THE RULING WAS THE SOFTEST OF THE THREE OPTIONS, and deliberately: name it in the line, keep exit 0.
    A bundle halfway through an ingestion legitimately has nothing to check yet, and a gate that refused
    by default would be unusable exactly when an operator most wants to run it.
    """
    ran = invariants - vacuous
    tail = (f"; {vacuous} of {invariants} had NOTHING TO CHECK and therefore proved nothing — this is "
            f"not a full pass, and the rows say which" if vacuous else "")
    if total_bad:
        return (f"FAIL: check_delivery_consistency — {total_bad} inconsistenc"
                f"{'y' if total_bad == 1 else 'ies'} across {invariants} invariant(s): deliverables "
                f"that are PRESENT and disagree with each other{tail}")
    if vacuous:
        return (f"PASS: check_delivery_consistency — {ran} of {invariants} invariant(s) held over a "
                f"population that exists{tail}")
    return (f"PASS: check_delivery_consistency — {invariants} of {invariants} invariant(s) hold; the "
            f"delivered components agree with one another")


def _record(root: pathlib.Path, out: str, st: dict, rows: list[dict],
            checked: int, total_bad: int) -> None:
    """THE RUN RECORD — the checklist AS DATA, so a surface other than a terminal can show it.

    THE DEFECT THIS REPAIRS. The operator asked for two things on 2026-09-27, and only the first was
    built: "i need quality checklist if all components of delivery ... have been delivered and if they
    are consistent" and "this checkbox list must appear on the console". A verdict that exists only on
    stdout cannot reach a console, and asking the console to re-run the gate would make the page a
    SECOND producer of the same verdict — two producers of one claim is how two answers to one
    question begin. So the gate stays the only thing that decides, and writes down what it decided.

    EVERY ROW CARRIES ITS DENOMINATOR, and that is the load-bearing part of this shape. `examined` is
    not decoration: an invariant that held over nothing has proven nothing, and a board that paints it
    the same green as one that held over 23 teaches an operator to trust a blank check. `vacuous` says
    so in one boolean rather than leaving a renderer to infer it from a zero it may not look at.

    IT IS A SNAPSHOT, NOT A HISTORY. One run, overwritten — the same choice `check_register_membership`
    makes, for the same reason: the question a board asks is "do the delivered components agree NOW",
    and a bundle's git history already holds every earlier answer with the commit that caused it.
    """
    path = root / out
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "generated_by": "check_delivery_consistency.py/1",
        "executed": datetime.now(UTC).isoformat(timespec="seconds"),
        "bundle": root.name,
        "verdict": "FAIL" if total_bad else "PASS",
        "invariants": checked,
        # BESIDE THE VERDICT, not buried in the rows: a reader (or a CI job) must be able to tell a
        # full pass from a hollow one without walking seven rows. Operator ruling, backlog item 8.
        "invariants_checked": checked - sum(1 for r in rows if r.get("vacuous")),
        "invariants_vacuous": sum(1 for r in rows if r.get("vacuous")),
        "inconsistencies": total_bad,
        # The header line's denominators, as data. A verdict is only as good as the plane it read:
        # "7 invariants hold" over 0 concepts is a different claim from the same words over 19.
        "examined": {k: len(st[k]) for k in
                     ("served", "sources", "profiles", "concepts", "edges", "fks", "registers")},
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--enumerate", dest="enumerate_all", action="store_true",
                    help="print every enumerated subject, not only the failing ones")
    ap.add_argument("--out", default=RUNS_REL,
                    help="where to write the run record, bundle-relative; \"\" writes nothing")
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

    if _concept_index is None:
        print(f"COULD NOT RUN: sdk.authoring.edges is unavailable, so FK-EDGE cannot resolve a concept "
              f"endpoint. A gate that cannot resolve must refuse, not pass.\n\n{ACCEPTED_SHAPE}")
        return 2
    st = load(root, yaml)
    st["concept_index"] = _concept_index(list(st["concepts"].values()))
    print(f"  DELIVERY CONSISTENCY — {root.name}\n"
          f"  presence is not consistency: {len(st['served'])} served + {len(st['sources'])} raw "
          f"descriptor(s), {len(st['profiles'])} profile(s), {len(st['concepts'])} concept(s), "
          f"{len(st['edges'])} edge(s), {len(st['fks'])} measured FK(s), "
          f"{len(st['registers'])} register(s)\n")
    total_bad, checked, rows = 0, 0, []
    for code, what, fn in INVARIANTS:
        items = fn(st)
        enumerated, held, failed, na = counts(items)
        bad = violations(items)
        checked += 1
        mark = "ok  " if not bad else "FAIL"
        # THE WHOLE POPULATION, THEN THE SPLIT. The operator's words on the first version, which
        # printed only the second number: "test if FK is over 3 ... i expect you to enumerate all and
        # then check if passing". `enumerated` is the list's own length, so it cannot be a slice of
        # anything, and `n/a` is visible rather than subtracted off-screen.
        over = (f"{enumerated} enumerated · {held} held · {failed} failed · {na} n/a"
                if enumerated else "NOTHING TO ENUMERATE")
        print(f"  [{mark}] {code:17} {what:56} {over}")
        for b in bad[:6]:
            print(f"         - {b}")
        if len(bad) > 6:
            print(f"         … and {len(bad) - 6} more")
        # --enumerate PRINTS EVERY SUBJECT, held and n/a included. Off by default because seven full
        # enumerations is a screenful; on, it is the audit trail — and the console shows it always,
        # because a checklist read on a page has room the terminal does not.
        if a.enumerate_all:
            for it in items:
                glyph = {"ok": "ok ", "violation": "!! ", "n/a": "-- "}[it["verdict"]]
                print(f"         {glyph} {it['subject']}")
                if it["verdict"] != "ok":
                    print(f"              {it['note']}")
        total_bad += len(bad)
        rows.append({
            "code": code, "checks": what,
            # `examined` IS WHAT WAS ACTUALLY CHECKED — held + failed — and `enumerated` is everything
            # the invariant looked at. Both are carried because a reader needs the ratio, not either
            # number alone: "3 of 12" is the honest form of what once read "over 3".
            "enumerated": enumerated, "examined": held + failed,
            "held": held, "failed": failed, "not_applicable": na,
            "verdict": "FAIL" if bad else "ok",
            # VACUOUS IS NOW "NOTHING WAS CHECKED", not "nothing was enumerated" — an invariant that
            # listed twelve subjects and checked none of them has proved exactly as little as one that
            # listed none, and the board must not paint either green.
            "vacuous": (held + failed) == 0 and not bad,
            "violations": bad,
            "items": items,
        })

    if a.out:
        _record(root, a.out, st, rows, checked, total_bad)

    print("\n" + _summary(checked, sum(1 for r in rows if r["vacuous"]), total_bad))
    return 1 if total_bad else 0


def _self_test() -> int:
    """One mutant per invariant plus a clean fixture (CORE.md §2), every case a pure dict."""
    def _base() -> dict:
        return {
            "served": {"v_s": {"columns": [{"name": "CK", "role": "foreign_key",
                                            "references": "v_c"}]},
                       "v_c": {"columns": [{"name": "CK", "role": "primary_key"},
                                            {"name": "B", "role": "value",
                                             "register": "data/lookups/b_x.lookup.csv"}]}},
            "sources": {},
            "profiles": {"v_s": {}, "v_c": {}},
            # THE CONCEPTS CARRY THEIR NAME AND THEIR IDENTITY FLAGS, because FK-EDGE now resolves an
            # endpoint through `concept.name` and `identity: reference` / `identity: canonical`. The
            # fixture used to carry neither and its edge carried no `endpoints` — which is precisely how
            # it certified an invariant that matched an id STRING while three real edges said
            # `Currency -> Region`. A fixture thinner than the artifact proves nothing about it.
            "concepts": {
                "line": {"concept": {"name": "Line"},
                         "grounding": {"sources": [{"relation": "v_s", "columns": {
                             "CK": {"role": "key", "identity": "reference"}}}],
                                       "field_roles": {"CK": "mac.field_role.key"}}},
                "cust": {"concept": {"name": "Cust"},
                         "grounding": {"sources": [{"relation": "v_c", "columns": {
                             "CK": {"role": "key", "identity": "canonical"}}}]}},
            },
            "refs": {},
            "edges": [{"edge_id": "Line__CK__to__Cust",
                       "endpoints": {"from": {"concept": "Line"}, "to": {"concept": "Cust"}}}],
            "fks": [("v_s", "CK", "v_c")],
            "registers": ["b_x.lookup.csv"], "monitor": True,
            "concept_samples": ["line"], "sample_run": True, "vocab_ns": set(),
            "ruled_unclaimed": set(),
        }

    def base() -> dict:
        """The fixture, WITH its concept index built by the same resolver the gate uses — so a fixture
        can never be checkable in a way a real bundle is not."""
        st = _base()
        st["concept_index"] = _concept_index(list(st["concepts"].values())) if _concept_index else {}
        return st
    cases = []

    def case(label, mutate, expect_code):
        st = base()
        mutate(st)
        got = {c: violations(fn(st)) for c, _w, fn in INVARIANTS}
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
         lambda st: st["concepts"]["line"].update(values={"closure": "closed", "items": []}),
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
    failing = sorted(c for c, _w, fn in INVARIANTS if violations(fn(st)))
    cases.append(("MUTANT three disagreements are reported as THREE, not one",
                  failing == ["FK-EDGE", "PLANE-COUNTS", "ROLE-VOCAB"], failing,
                  "FK-EDGE+PLANE-COUNTS+ROLE-VOCAB"))

    # ── THE ENUMERATION CONTRACT ────────────────────────────────────────────────────────────────
    # These do not test a VERDICT; they test that the population reported is the whole population.
    # The defect they pin was on screen and passing: FK-EDGE said "over 3" on a bundle with twelve
    # measured foreign keys, because nine were `continue`d before the denominator was formed. A gate
    # that narrows its own population and reports the narrowed count cannot be audited at all.
    def check(label, cond):
        cases.append((label, bool(cond), cond, True))

    st = base()
    # Two FKs, one of them reaching a relation no concept claims. The old code examined 1 and said so;
    # the contract now requires BOTH to be listed, with the excluded one carrying its reason.
    st["sources"] = {"raw_x": {"columns": []}}
    st["fks"] = [("v_s", "CK", "v_c"), ("v_s", "XK", "raw_x")]
    fk = inv_fk_edge(st)
    enumerated, held, failed, na = counts(fk)
    check("ENUMERATION FK-EDGE lists the unmodelled key instead of dropping it",
          enumerated == 2 and held == 1 and failed == 0 and na == 1)
    check("ENUMERATION the excluded item names WHY, and names the raw plane as structural",
          any(i["verdict"] == "n/a" and "RAW landing" in i["note"] for i in fk))
    check("ENUMERATION every item carries a subject a human can look up",
          all(i["subject"] and isinstance(i["subject"], str) for i in fk))

    # MEMBER-GRAIN enumerated only set-extension concepts before; the base fixture has two concepts
    # and neither declares a set, so the honest report is "2 enumerated, 0 checked" — NOT "0".
    mg = counts(inv_member_grain(base()))
    check("ENUMERATION MEMBER-GRAIN lists every concept, not only the set-extension ones",
          mg[0] == 2 and mg[1] + mg[2] == 0 and mg[3] == 2)

    # THE ARITHMETIC CANNOT DRIFT FROM THE LIST. held is the remainder, so the four always partition.
    st = base()
    st["edges"] = []
    for _c, _w, fn in INVARIANTS:
        items = fn(st)
        e, h, f, na_ = counts(items)
        check(f"ENUMERATION counts partition the list exactly ({_c})", e == h + f + na_ == len(items))

    # A ROW WHERE EVERYTHING IS n/a IS NOT A PASS. It is the "over 3" defect at its limit: twelve
    # subjects listed, none checked, and nothing on the page may read as an all-clear.
    st = base()
    st["concepts"] = {}
    st["fks"] = [("a", "K", "b")]
    e, h, f, na_ = counts(inv_fk_edge(st))
    check("ENUMERATION an all-n/a row enumerates its subjects and checks none of them",
          e == 1 and h == 0 and f == 0 and na_ == 1)

    # ── ROLE-VOCAB READS THE SHAPE THAT IS ACTUALLY WRITTEN (backlog item 10) ───────────────────
    # It read only `field_roles` and had gone PERMANENTLY VACUOUS: 0 of 19 concepts write that, 19
    # write the column map with 142 role declarations. A consumer reading a shape no producer writes
    # — inside the checker whose job is to find exactly that.
    st = base()
    st["concepts"]["line"]["grounding"]["field_roles"] = {}
    rv = inv_role_vocab(st)
    # TWO column declarations in the fixture (line.CK and cust.CK) and zero field_roles: the point is
    # that the count comes from the COLUMN MAP at all, which it did not before.
    check("ROLE-VOCAB enumerates the COLUMN MAP, not only field_roles",
          counts(rv)[0] == 2 and counts(rv)[1] == 2)
    check("ROLE-VOCAB accepts a bare role from the closed set",
          all(i["verdict"] == "ok" for i in rv))

    st = base()
    st["concepts"]["line"]["grounding"]["sources"][0]["columns"]["CK"]["role"] = "dimensio"
    check("MUTANT a misspelled column role is a VIOLATION, not silence",
          [c for c, _w, fn in INVARIANTS if violations(fn(st))] == ["ROLE-VOCAB"])

    st = base()
    st["concepts"]["line"]["grounding"]["sources"][0]["columns"]["CK"]["role"] = "CONTOSO4.field_role.key"
    check("MUTANT an undeclared namespace on a COLUMN role is a violation",
          [c for c, _w, fn in INVARIANTS if violations(fn(st))] == ["ROLE-VOCAB"])

    st = base()
    st["vocab_ns"] = {"contoso4"}
    st["concepts"]["line"]["grounding"]["sources"][0]["columns"]["CK"]["role"] = "CONTOSO4.field_role.key"
    check("CLEAN a namespaced column role RESOLVES once the vocabulary declares it",
          not violations(inv_role_vocab(st)))

    st = base()
    st["concepts"]["line"]["grounding"]["field_roles"] = {}      # isolate the column map
    st["concepts"]["line"]["grounding"]["sources"][0]["columns"]["CK"] = None
    # `null` means "serve it and say nothing more" -- a declaration of silence, so NO item for that
    # column. The fixture's other concept still contributes its own, which is why this asserts the
    # absence of the null column rather than an empty list.
    check("a column declared `null` says nothing and is not graded",
          not any(i["subject"].startswith("line.") for i in inv_role_vocab(st)))

    st = base()
    st["concepts"]["line"]["grounding"]["field_roles"] = {}      # isolate the column map
    st["concepts"]["line"]["grounding"]["sources"][0]["columns"]["CK"] = {"identity": "part"}
    # EXACTLY ONE n/a, not a list equality: the fixture's other concept contributes a real role, and a
    # test that pins the whole list breaks whenever the fixture grows a column — which is a test
    # measuring the fixture rather than the behaviour.
    check("a column with flags but no role is n/a, and SAYS SO rather than passing",
          [i["verdict"] for i in inv_role_vocab(st)].count("n/a") == 1)

    # BOTH SHAPES AT ONCE, which is the state a bundle mid-migration is in: the legacy token and the
    # column map must BOTH be enumerated, or migrating silently halves the coverage.
    st = base()
    # line carries a field_role AND a column role; cust carries a column role. Three declarations, and
    # the legacy shape must still be among them or migrating a bundle halves its coverage in silence.
    rv = inv_role_vocab(st)
    check("a concept carrying BOTH shapes has both enumerated",
          counts(rv)[0] == 3 and any("field_role" in i["subject"] for i in rv)
          and any(i["subject"].endswith(" role") for i in rv))

    # THE TWO HOMES ARE PINNED TOGETHER. COLUMN_ROLES mirrors mac.schema.json's enum for the same slot;
    # a change to one and not the other is exactly the drift this estate keeps paying for, so it goes
    # RED here instead of going quiet. Skipped, not failed, when the schema is not beside us — a
    # self-test must not depend on a file layout.
    try:
        import json as _json
        _sp = pathlib.Path(__file__).resolve().parent.parent / "mac.schema.json"
        _e = (_json.loads(_sp.read_text(encoding="utf-8"))["$defs"]["grounding"]["properties"]["sources"]
              ["items"]["properties"]["columns"]["oneOf"][1]["additionalProperties"]["properties"]
              ["role"].get("enum"))
        check("COLUMN_ROLES agrees with mac.schema.json's enum for the same slot",
              _e is not None and tuple(_e) == COLUMN_ROLES)
    except (OSError, KeyError, IndexError, ValueError):
        pass

    # ── THE VERDICT LINE (operator ruling, backlog item 8) ──────────────────────────────────────
    # A sentence, tested, because the defect WAS the sentence: `PASS: 7 invariant(s) hold` on a bundle
    # where four of the seven had no subject to check.
    check("SUMMARY a full pass says so and claims no more", "7 of 7 invariant(s) hold" in _summary(7, 0, 0))
    check("SUMMARY a hollow pass NAMES the invariants that checked nothing",
          "3 of 7 invariant(s) held" in _summary(7, 4, 0) and "NOTHING TO CHECK" in _summary(7, 4, 0))
    check("SUMMARY a hollow pass never claims all of them held",
          "7 of 7 invariant(s) hold" not in _summary(7, 4, 0))
    check("SUMMARY a FAIL still carries the unchecked count",
          _summary(7, 4, 2).startswith("FAIL") and "NOTHING TO CHECK" in _summary(7, 4, 2))
    check("SUMMARY a clean FAIL does not invent an unchecked clause",
          "NOTHING TO CHECK" not in _summary(7, 0, 1) and "1 inconsistency" in _summary(7, 0, 1))
    check("SUMMARY every invariant vacuous is not reported as a pass over anything",
          "0 of 7 invariant(s) held" in _summary(7, 7, 0))

    bad = [(lbl, got, want) for lbl, ok, got, want in cases if not ok]
    for lbl, got, want in bad:
        print(f"  FAIL  {lbl}\n        expected {want!r}, got {got!r}")
    n = len(cases)
    if bad:
        print(f"\nFAIL: check_delivery_consistency self-test — {len(bad)} of {n} case(s) failed")
        return 1
    print(f"PASS: check_delivery_consistency self-test — {n}/{n} case(s): one mutant per invariant "
          f"({', '.join(c for c, _w, _f in INVARIANTS)}), a register pointer that resolves to nothing, "
          f"three simultaneous disagreements reported as three, a clean fixture that must hold, and the "
          f"ENUMERATION contract — the whole population is listed, every exclusion names its reason, the "
          f"counts partition the list on all {len(INVARIANTS)} invariants, and an all-n/a row is not a pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
