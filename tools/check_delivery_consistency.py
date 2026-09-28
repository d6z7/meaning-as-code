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
def ref_relation(ref: str) -> str:
    """The RELATION a `columns[].references` points at, from `relation.column`.

    THE SEGMENT MATTERS. The schema has required `relation.column` since v0.1.15 and the producer wrote
    the relation alone until 2026-09-28, so every consumer used `.split(".")[-1]` to strip a schema
    prefix — which on a correctly qualified value returns the COLUMN and silently points the reference
    at a relation that does not exist. Second-to-last segment: `customer.CustomerKey` and
    `main.customer.CustomerKey` both give `customer`, and a legacy unqualified `customer` still does.
    """
    parts = [p for p in str(ref or "").split(".") if p]
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else "")


def ref_column(ref: str) -> str:
    """The COLUMN a reference lands on — empty when the value is unqualified (legacy)."""
    parts = [p for p in str(ref or "").split(".") if p]
    return parts[-1] if len(parts) >= 2 else ""


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

    # THE MEASURED FOREIGN KEYS, from `columns[].references` AND NOWHERE ELSE. Operator ruling
    # 2026-09-27: "i think columns block is better" — so that is the one home and the top-level
    # `foreign_keys:` block is RETIRED. This gate used to read both "because the data layer currently
    # states them two ways", which was true before the ruling and stale after it: measured, 0 of 16
    # descriptors carry the block, so the second loop was dead code keeping a retired shape alive.
    # Enforced below by the RETIRED-SHAPE invariant, so it cannot come back unnoticed.
    fks = []
    for stem, d in {**served, **sources}.items():
        for c in d.get("columns") or []:
            tgt = str(c.get("references") or "").strip()
            if tgt and c.get("role") == "foreign_key":
                fks.append((stem, str(c.get("name")), ref_relation(tgt)))

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


#: SHAPES A RULING RETIRED. Each must appear in ZERO delivered artifacts; a producer still writing one
#: keeps a dead dialect alive, and a consumer still reading it is how `physical_edges` came to lift a
#: key nobody wrote. `field_roles` is NOT here — it is LEGACY, still read on purpose so an older bundle
#: stays checked rather than silently skipped.
RETIRED_SHAPES = (
    ("foreign_keys", "data/{sources,datasets}/*.yaml",
     "the top-level `foreign_keys:` block. Operator ruling 2026-09-27: `columns[].references` is the "
     "one home for a foreign key. Measured that day: 0 of 8 served descriptors carried this block while "
     "`physical_edges` read it exclusively — which is why the edge lift wrote 0 edges over 19 concepts"),
)


def inv_retired_shape(st: dict) -> list[dict]:
    """A shape a ruling retired appears in NO delivered artifact.

    WHY THIS IS AN INVARIANT AND NOT A NOTE. Three times in two days the framework read a shape nothing
    wrote: `foreign_keys:` (0 of 8 descriptors, and the edge lift read only it), `grounding.field_roles`
    (0 of 19 concepts, and ROLE-VOCAB read only it), and `measure_type.terms` (the key was `members`, so
    a generator silently got nothing). Each cost real output and none of them errored, because reading
    an absent key returns an empty collection and an empty collection is a valid answer everywhere.
    """
    out = []
    for key, where, why in RETIRED_SHAPES:
        carriers = sorted(stem for stem, d in {**st["served"], **st["sources"]}.items() if d.get(key))
        total = len(st["served"]) + len(st["sources"])
        if not carriers:
            out.append(_i(key, OK, f"no artifact carries the retired `{key}:` ({total} descriptor(s) "
                                   f"checked in {where})"))
        else:
            out.append(_i(key, VIOLATION,
                          f"{len(carriers)} of {total} descriptor(s) still carry the RETIRED `{key}:` "
                          f"— {', '.join(carriers[:4])}. {why}"))
    return out


def inv_fk_qualified(st: dict) -> list[dict]:
    """A foreign key names the COLUMN it lands on, not just the relation.

    THE SCHEMA HAS REQUIRED THIS SINCE v0.1.15 — `references` is documented as "The parent this
    foreign_key column points at, as `relation.column`" — and `mac_descriptors` wrote the relation ALONE
    until 2026-09-28. So "what column do I join to" was unanswerable from the declaration, and every
    consumer assumed the parent's key carried the same name as the referencing column. That assumption
    happens to hold in this warehouse and is nowhere stated, which is the definition of a fact the
    delivery does not carry. Operator, 2026-09-28: "reference to tables and columns where FKs are
    pointing to".

    IT ALSO CATCHES THE READING BUG the qualification introduced: a consumer stripping a schema prefix
    with `.split(".")[-1]` now gets the COLUMN and points the reference at a relation that does not
    exist. That is checked here by resolving the named relation against the delivered descriptors.
    """
    out = []
    known = set(st["served"]) | set(st["sources"])
    for plane, table in (("served", st["served"]), ("raw", st["sources"])):
        for stem in sorted(table):
            for c in (table[stem].get("columns") or []):
                if not isinstance(c, dict) or str(c.get("role")) != "foreign_key":
                    continue
                ref = str(c.get("references") or "").strip()
                subject = f"{plane}:{stem}.{c.get('name')}"
                if not ref:
                    out.append(_i(subject, VIOLATION,
                                  f"{stem}.{c.get('name')} is `role: foreign_key` and declares no "
                                  f"`references` at all — a reference to nothing"))
                elif not ref_column(ref):
                    out.append(_i(subject, VIOLATION,
                                  f"{stem}.{c.get('name')} references {ref!r} — the RELATION only. The "
                                  f"schema requires `relation.column`, so the join column is left to be "
                                  f"guessed from a name coincidence"))
                elif ref_relation(ref) not in known:
                    out.append(_i(subject, VIOLATION,
                                  f"{stem}.{c.get('name')} references {ref!r}, whose relation "
                                  f"{ref_relation(ref)!r} is described by no descriptor in this bundle"))
                else:
                    out.append(_i(subject, OK,
                                  f"{stem}.{c.get('name')} -> {ref_relation(ref)}.{ref_column(ref)}, "
                                  f"relation and column both named"))
    return out


def inv_key_position(st: dict) -> list[dict]:
    """A relation's composite key positions are exactly 1..n — no gaps, no repeats, none off a key.

    THE GUARD THE RETIRED TERM DID NOT NEED AND THE NUMBER DOES. `composite_key_part` was
    self-consistent by construction: membership was the term, and a set of terms cannot have a gap. An
    ORDINAL can — two columns both `key_position: 1`, or a 2 with no 1 — so the ruling that moved the
    order onto the column (operator, 2026-09-27) owes this check. Stated when the ruling was accepted
    and built here.

    IT ALSO CATCHES THE INVERSE: a `key_position` on a column that is not a key at all, which is a
    number claiming an order in a sequence it does not belong to.
    """
    out = []
    for plane, table in (("served", st["served"]), ("raw", st["sources"])):
        for stem in sorted(table):
            cols = [c for c in (table[stem].get("columns") or []) if isinstance(c, dict)]
            pos = {str(c.get("name")): c["key_position"] for c in cols if c.get("key_position") is not None}
            keys = {str(c.get("name")) for c in cols if str(c.get("role")) == "primary_key"}
            subject = f"{plane}:{stem}"
            off = sorted(n for n in pos if n not in keys)
            if off:
                out.append(_i(subject, VIOLATION,
                              f"{stem}: {', '.join(off)} carr{'ies' if len(off) == 1 else 'y'} a "
                              f"key_position but {'is' if len(off) == 1 else 'are'} not `role: "
                              f"primary_key` — an order in a sequence it does not belong to"))
                continue
            if not pos:
                out.append(_i(subject, NA,
                              f"{stem} declares no key_position — a single-column key ({len(keys)} key "
                              f"column) needs none" if len(keys) <= 1 else
                              f"{stem} has {len(keys)} key columns and NO key_position on any of them, "
                              f"so the composite key has no declared order"))
                continue
            want = list(range(1, len(pos) + 1))
            got = sorted(pos.values())
            if got != want:
                out.append(_i(subject, VIOLATION,
                              f"{stem} key positions are {got} over {len(pos)} column(s); they must be "
                              f"exactly {want} — no gaps, no repeats. Declared: "
                              f"{', '.join(f'{n}={v}' for n, v in sorted(pos.items(), key=lambda x: x[1]))}"))
            elif len(pos) != len(keys):
                out.append(_i(subject, VIOLATION,
                              f"{stem} has {len(keys)} key column(s) and {len(pos)} position(s) — every "
                              f"part of a composite key carries one, or the order is incomplete"))
            else:
                out.append(_i(subject, OK,
                              f"{stem} composite key is ordered 1..{len(pos)}: " +
                              " + ".join(n for n, _v in sorted(pos.items(), key=lambda x: x[1]))))
    return out


def inv_key_backed(st: dict) -> list[dict]:
    """A concept's `key:` list and its column map agree about which columns are the identity.

    FOUND BY MEASUREMENT 2026-09-28, and it was already drifting: `Currency` on `currencyexchange`
    declares `key: [FromCurrency]` and marks NO column `identity`, and `Region` on `customer` does the
    same with `key: [State]`. Two of sixteen concept/relation pairings already disagree WITH THEMSELVES,
    and all ten prior invariants passed — ONE-HOME compares concept-to-column and MEMBER-GRAIN only
    fires on set-extension concepts, so nothing looked here.

    `key:` is a second home for membership, which is §2.1's defect one slot over. This does not retire
    it — that is the operator's call — it makes the two agree, which is the weaker claim a gate can hold
    without pre-empting a ruling.
    """
    out = []
    for name, d in sorted(st["concepts"].items()):
        for src in ((d.get("grounding") or {}).get("sources") or []):
            rel = str(src.get("relation") or "?").split(".")[-1]
            listed = [str(x) for x in (src.get("key") or [])]
            cm = src.get("columns")
            marked = sorted(cn for cn, b in (cm or {}).items()
                            if isinstance(b, dict) and b.get("identity") in ("canonical", "part")) \
                if isinstance(cm, dict) else []
            subject = f"{name} on {rel}"
            if not listed and not marked:
                out.append(_i(subject, NA, f"{subject} declares no key either way"))
            elif not listed:
                # THE COLUMN MAP ALONE IS CORRECT AND IS THE POINT. Requiring a `key:` list would
                # enforce the second home §2.1 exists to remove — the first version of this invariant
                # did exactly that and failed the clean fixture, which is the gate teaching the defect.
                out.append(_i(subject, OK,
                              f"{subject}: the key is declared on the column map only "
                              f"({', '.join(marked)}), which is its home"))
            elif sorted(listed) == marked:
                out.append(_i(subject, OK, f"{subject}: `key:` and the column map agree on "
                                           f"{', '.join(marked)}"))
            else:
                out.append(_i(subject, VIOLATION,
                              f"{subject}: `key: {listed or '[]'}` and the column map's identity "
                              f"columns {marked or '[]'} disagree — one fact, two homes, already "
                              f"drifted. The column is where a key is declared"))
    return out


def inv_one_home(st: dict) -> list[dict]:
    """The canonical key is declared ONCE — on the column, not also on the concept.

    CONFORMANCE §2.1 states this and until now NOTHING ENFORCED IT, which is the shape of defect this
    whole checklist exists to find: a law written in prose beside a framework that cannot check it.

    THE SCHEMA HAS SAID IT ALL ALONG, in the column map's own `identity` description: "the key is a
    COLUMN fact, so declaring it here AND under concept.identity gives it two homes that can disagree."
    Measured 2026-09-27: 15 of 19 concepts in the reference bundle carried it only on the column, and
    the ONLY two carrying both were the two I had authored that day — while writing the law. A
    composite key settles the argument outright: `canonical_key` is one string, and `identity: part`
    marks as many columns as the key has.
    """
    out = []
    for name, d in sorted(st["concepts"].items()):
        declared = str((((d.get("concept") or {}).get("identity") or {}).get("canonical_key") or "")).strip()
        cols = []
        for src in ((d.get("grounding") or {}).get("sources") or []):
            cm = src.get("columns")
            if isinstance(cm, dict):
                cols += [cn for cn, b in cm.items()
                         if isinstance(b, dict) and b.get("identity") in ("canonical", "part")]
        if declared and cols:
            out.append(_i(name, VIOLATION,
                          f"concept {name!r} declares canonical_key {declared!r} AND marks "
                          f"{', '.join(cols)} on the column map — two homes for one fact, which can "
                          f"disagree. The column is the home; remove the concept-level key"))
        elif declared:
            out.append(_i(name, VIOLATION,
                          f"concept {name!r} declares canonical_key {declared!r} at CONCEPT level with "
                          f"no column marked `identity: canonical` — the key is a column fact and must "
                          f"be declared on the column"))
        elif cols:
            out.append(_i(name, OK, f"concept {name!r} declares its key only on the column map "
                                    f"({', '.join(cols)})"))
        else:
            out.append(_i(name, NA, f"concept {name!r} marks no key column, so there is no key to "
                                    f"have two homes for"))
    return out


def inv_measure_unit(st: dict) -> list[dict]:
    """A COMPOSED measure states its own unit; a single one may project it.

    THE DEFECT THIS CATCHES, AND IT IS THE HALF THAT WAS MISSING. `mac.schema.json` said "Only ONE
    column per concept may carry `measure`" for the reason "semantics.unit is singular" — and NOTHING
    ENFORCED IT. Not JSON Schema (it cannot count keys of a map), not any tool. So the rule forbade a
    harmless thing in prose while the hazard it feared went unguarded: a concept could carry five
    measure columns in five units and pass every gate.

    THE COST WAS MEASURED ON 2026-09-27. Revenue on an order line is `Quantity x NetPrice` — two
    columns, ONE amount in USD. contoso1 declared exactly that (under the retired `field_roles` shape,
    which had no limit) for GrossSalesAmount and NetSalesAmount, and answered "the ratio of gross to
    net revenue" as 1.063008040065774. contoso4, on the column standard, could not state gross revenue
    at all — the new shape was LESS EXPRESSIVE than the one it replaced, and its own SalesAmount
    concept said so: "IT IS NOT A COLUMN ... the figure must be composed."

    SO THE RULE IS NOW ABOUT THE UNIT: several columns may carry `measure`; with more than one, the
    concept MUST declare `semantics.unit`, because the projection cannot choose between two factor
    units and taking the first would make an answer's unit depend on YAML key order. That last clause
    is the original reason, kept — solved by requiring the author to say rather than by forbidding the
    composition.
    """
    out = []
    for name, d in sorted(st["concepts"].items()):
        cols = []
        for src in ((d.get("grounding") or {}).get("sources") or []):
            cm = src.get("columns")
            if isinstance(cm, dict):
                for cn, b in cm.items():
                    if isinstance(b, dict) and (b.get("role") == "measure" or b.get("measure")):
                        cols.append((cn, ((b.get("measure") or {}).get("unit") or "")))
        if not cols:
            out.append(_i(name, NA, f"concept {name!r} carries no measure column, so no unit is owed"))
            continue
        declared = str((((d.get("concept") or {}).get("semantics") or {}).get("unit") or "")).strip()
        units = sorted({u for _c, u in cols if u})
        if len(cols) == 1:
            out.append(_i(name, OK,
                          f"concept {name!r} has ONE measure column ({cols[0][0]}), so its unit "
                          f"projects from the column" + (f" ({units[0]})" if units else "")))
            continue
        shown = ", ".join(f"{c}={u or '—'}" for c, u in cols)
        if declared:
            out.append(_i(name, OK,
                          f"concept {name!r} composes {len(cols)} measure column(s) ({shown}) and "
                          f"declares the composed unit {declared!r} on the concept"))
        else:
            out.append(_i(name, VIOLATION,
                          f"concept {name!r} carries {len(cols)} measure columns ({shown}) and declares "
                          f"NO concept.semantics.unit — so the composed unit is whichever factor a "
                          f"reader happens to take first, which is YAML key order. State the unit of "
                          f"the composition"))
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
    ("ONE-HOME", "the canonical key is declared on the column, not also on the concept", inv_one_home),
    ("FK-QUALIFIED", "a foreign key names the relation AND the column it lands on", inv_fk_qualified),
    ("KEY-POSITION", "a composite key's positions are exactly 1..n on its key columns", inv_key_position),
    ("KEY-BACKED", "a concept's `key:` list and its column map agree", inv_key_backed),
    ("RETIRED-SHAPE", "a shape a ruling retired appears in no delivered artifact", inv_retired_shape),
    ("MEMBER-GRAIN", "a concept whose extension is a set names a canonical key", inv_member_grain),
    ("MEASURE-UNIT", "a composed measure states its own unit; a single one projects it", inv_measure_unit),
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
                                            "references": "v_c.CK"}]},
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
    # ── FK-QUALIFIED: the relation alone is not a join ────────────────────────────────────────────
    case("MUTANT a reference naming the relation but not the column",
         lambda st: st["served"]["v_s"]["columns"][0].__setitem__("references", "v_c"), "FK-QUALIFIED")
    case("MUTANT a reference whose relation no descriptor describes",
         lambda st: st["served"]["v_s"]["columns"][0].__setitem__("references", "nope.CK"),
         "FK-QUALIFIED")
    case("MUTANT a foreign_key column with no reference at all",
         lambda st: st["served"]["v_s"]["columns"][0].pop("references"), "FK-QUALIFIED")

    # ── KEY-POSITION / KEY-BACKED: the guards the ordinal and the second home need ─────────────────
    def _ck(st, a=1, b=2):
        """ADD a composite key rather than repurposing the fixture's FK column. A mutator that changes a
        column another invariant depends on trips several at once, and a case that fails four gates
        proves nothing about the one it names — measured: the first version of this broke 20 of 53."""
        st["served"]["v_s"]["columns"] += [
            {"name": "K1", "role": "primary_key", "key_position": a},
            {"name": "K2", "role": "primary_key", "key_position": b}]
    case("CLEAN a composite key ordered 1,2", lambda st: _ck(st, 1, 2), None)
    case("MUTANT a repeated key position", lambda st: _ck(st, 1, 1), "KEY-POSITION")
    case("MUTANT a gap in the key positions", lambda st: _ck(st, 1, 3), "KEY-POSITION")
    case("MUTANT a key_position on a column that is not a key",
         lambda st: st["served"]["v_c"]["columns"].append(
             {"name": "Z", "role": "value", "key_position": 1}), "KEY-POSITION")
    case("MUTANT a `key:` list no column backs",
         lambda st: st["concepts"]["cust"]["grounding"]["sources"][0].__setitem__("key", ["NOPE"]),
         "KEY-BACKED")

    # ── RETIRED-SHAPE: the ruled-away `foreign_keys:` block coming back ───────────────────────────
    case("MUTANT a descriptor still carrying the retired `foreign_keys:` block",
         lambda st: st["served"]["v_s"].__setitem__(
             "foreign_keys", [{"from_column": "CK", "to_table": "v_c"}]), "RETIRED-SHAPE")

    # ── ONE-HOME: CONFORMANCE §2.1, unenforced until now ──────────────────────────────────────────
    case("MUTANT the canonical key declared on the concept AS WELL as the column",
         lambda st: st["concepts"]["cust"].setdefault("concept", {}).setdefault(
             "identity", {}).__setitem__("canonical_key", "CK"), "ONE-HOME")

    case("MUTANT a set-extension concept with no canonical key",
         lambda st: st["concepts"]["line"].update(values={"closure": "closed", "items": []}),
         "MEMBER-GRAIN")
    # ── MEASURE-UNIT: the composed measure, which the old `only ONE column` rule forbade ──────────
    def _compose(st, unit=None):
        """Make `line` a composed measure: Quantity x CK, two factor units, one amount."""
        cols = st["concepts"]["line"]["grounding"]["sources"][0]["columns"]
        cols["CK"] = {"role": "measure", "measure": {"type": "mac.concept.column.measure_type.flow",
                                                     "unit": "USD"}}
        cols["Qty"] = {"role": "measure", "measure": {"type": "mac.concept.column.measure_type.flow",
                                                      "unit": "units"}}
        if unit:
            st["concepts"]["line"].setdefault("concept", {}).setdefault("semantics", {})["unit"] = unit
    case("MUTANT two measure columns and NO concept unit — the composed unit would be key order",
         lambda st: _compose(st), "MEASURE-UNIT")
    case("CLEAN two measure columns WITH the composed unit declared is legitimate",
         lambda st: _compose(st, "USD"), None)

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
