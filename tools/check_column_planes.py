#!/usr/bin/env python3
"""check_column_planes.py — every column placed in BOTH planes, and the slots that crossed them.

THE OPERATOR'S TWO-PLANE MAP, 2026-09-27, turned into a gate. The map says which closed vocabulary
governs which slot, and separates them by PLANE:

    DATA PLANE     data/sources/*.yaml · data/datasets/*.yaml
                   columns[].role -> mac.dataset.column.role (6)   the PHYSICAL shape in the relation
    CONCEPT PLANE  ontology/concepts/**/*.yaml
                   the column map's slots (column_declaration.md rev 5, 2026-10-07):
                     offers       -> mac.concept.column.offers (5)   what a QUESTION may do with it
                     offers.axis  -> mac.concept.axis (2)            which kind of axis, when claimed
                     aggregate.type -> mac.concept.column.measure_type (5)  which folds are legal
                     rulings      -> mac.concept.column.ruling (5)   what a PERSON decided
                                     naming -> mac.name_register (5)
                   `references` LEFT THIS MAP ENTIRELY: it used to be `roles.identity: reference`, a
                   concept-plane ROLE sharing the slot this gate exists to keep separate from the
                   data plane's `role:`; it is now the column's own top-level `references:` key
                   (the concept it points at), which is not a "what may a question do with me" use
                   and so is not part of `offers` or this gate's R2 census at all.

WHY THE SPLIT IS WHAT MAKES THE GATE POSSIBLE. Both planes spell a slot `role`-shaped. The data plane
takes `mac.dataset.column.role`; the concept plane's uses live under `offers`, and the two sets SHARE
NO TERM — so a term from the wrong side is detectable, and is detectable only once the planes are
named. Measured on contoso the day this gate was written: `dim_contoso_store.Channel` declares
`role: dimension` in the DATA plane, which is a column.role term in a storage_role slot. Read as one
undifferentiated "role", it looks correct.

WHAT IT REDS ON
  R1  a data-plane role outside mac.dataset.column.role
  R2  a concept-plane USE outside mac.concept.column.offers, or a term within a use outside that
      use's own vocabulary (`axis`'s term outside mac.concept.axis) — this is where a RETIRED term
      surfaces: `identity` was a role sharing this slot until 2026-10-07 and the vocabulary no
      longer defines it as a use at all
  R3  a concept binds a column the data plane does not measure — the ontology serving a column
      nothing profiled

WHAT IT REPORTS BUT DOES NOT RED ON
  the cross-tab of storage_role x column.role, the four column-map slots' coverage, and the pairs
  the reference manual warns about (a foreign_key used as a dimension: "that is a pointer, not a
  category, even though its cardinality looks dimension-sized"). A warning is not a breach — the
  pair can be correct, and a gate that failed on it would be ruling rather than checking.

Contract: one PASS/FAIL line, exit 0 or 1, a printed denominator, exit 2 when it could not run,
and --self-test with a mutant per reject class.

Usage:
  python3 tools/check_column_planes.py <bundle> [--census]
  python3 tools/check_column_planes.py --self-test
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys

import yaml

#: THE FOLD-AGNOSTIC VOCABULARY READER. `mac_vocabulary.yaml` nests its dotted blocks
#: (`concept: column: measure_type:`); every lookup here indexes them by their DOTTED identity,
#: and `mac_vocab.flatten` is the one converter between the two shapes.
import mac_vocab as _mv  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parents[1]
VOCAB = ROOT / "mac_vocabulary.yaml"
NAME = "check_column_planes"

#: The reference manual's own warnings. Reported, never failed — see the docstring.
SUSPICIOUS = {
    ("foreign_key", "axis"):
        "a pointer used as a category — 'that is a pointer, not a category, even though its "
        "cardinality looks dimension-sized' (column_roles.md §1). NOT a breach: a reference key "
        "that is also a legitimate axis is 18 of contoso5's columns, which is why this reports",
    ("value", "identity"):
        "a payload column doing identity duty — the data plane measured no key shape here",
    ("primary_key", "aggregate"):
        "the relation's own identity offered as a quantity to fold",
}


def load_terms() -> dict[str, list[str]]:
    raw = _mv.flatten(yaml.safe_load(VOCAB.read_text(encoding="utf-8")) or {})
    out = {}
    # `measure_type`, NOT `MeasureType`: the namespace is lower_snake in mac_vocabulary.yaml and
    # its members are lowercase (flow, stock, intensive, precomputed, target). The capitalised
    # spelling survives in 8 framework files and in the runtime's fold-law drift test, where it
    # raises KeyError instead of comparing a cell. Asking for the wrong name here returned an
    # empty list in silence, which is the same defect one layer up.
    # `concept.column.roles` -> `concept.column.offers` 2026-10-07 (the `roles:` -> `offers:` rename);
    # `concept.column.identity` and `concept.identity` are GONE, not renamed — `identity` left the
    # offers set for the top-level `references:` key, and `concept.identity.kind` left the schema
    # 2026-10-05. Asking for either now would silently return `[]` and no caller would see why.
    for ns in ("dataset.column.role", "concept.column.offers", "concept.axis",
               "concept.column.measure_type", "concept.column.ruling", "name_register"):
        spec = raw.get(ns) or {}
        out[ns] = list((spec.get("terms") or spec.get("members") or {}))
    if not out["dataset.column.role"] or not out["concept.column.offers"]:
        raise RuntimeError(
            "mac_vocabulary.yaml did not yield dataset.column.role and concept.column.offers"
        )
    return out


def read_planes(bundle: pathlib.Path) -> tuple[dict, list[dict], dict]:
    """(data plane, concept bindings, form counts). Raises if a plane is absent."""
    # THE TWO SUB-PLANES ARE NOT ONE POPULATION, and conflating them makes a meaningless
    # denominator. `datasets/` is the SERVED layer, which is what a concept binds; `sources/` is the
    # raw landing, which a concept is not supposed to bind. An unbound served column is a finding;
    # an unbound landing column is the serving layer doing its job.
    storage: dict[tuple[str, str], str] = {}
    origin: dict[tuple[str, str], str] = {}
    for sub in ("datasets", "sources"):
        for p in sorted((bundle / "data" / sub).glob("*.yaml")):
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            rel = (d.get("table") or {}).get("name") or d.get("relation") or p.stem
            for c in (d.get("columns") or []):
                if c.get("name") and (str(rel), str(c["name"])) not in storage:
                    storage[(str(rel), str(c["name"]))] = c.get("role")
                    origin[(str(rel), str(c["name"]))] = "served" if sub == "datasets" else "landing"

    # THE RELATION PLANE, v0.1.20 — `ontology/relations/<relation>.yaml` keyed by relation name.
    #
    # WHY THIS GATE HAD TO LEARN IT, measured the hour the first relation was migrated: this
    # census read `grounding.source.columns` only, so the seven concepts that moved off it took
    # 64 of the bundle's 112 concept bindings out of the gate's sight — and it reported
    # "PASS, 48 concept bindings" without a word. A gate whose DENOMINATOR silently shrinks by
    # 57 % while its verdict stays green is the exact failure this estate names "PASS on zero
    # files": the population has to be enumerated, never inferred from the survivors.
    relations: dict[str, dict] = {}
    rdir = bundle / "ontology" / "relations"
    if rdir.is_dir():
        for p in sorted(rdir.rglob("*.yaml")):
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            name = ((d.get("relation") or {}).get("name")) or p.stem
            relations[str(name)] = d.get("columns") or {}

    rows: list[dict] = []
    forms = {"map": 0, "flat": 0, "binding": 0}
    cdir = bundle / "ontology" / "concepts"
    for p in sorted(cdir.rglob("*.yaml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        con, g = d.get("concept") or {}, d.get("grounding") or {}
        # `concept.identity.kind` LEFT THE SCHEMA 2026-10-05 — there is no second census of it to
        # take here any more than there was a column to print it from.
        fr = g.get("field_roles") or {}
        # `grounding.source` IS SINGULAR since 2026-10-07 (`sources:` as a list is now `not: {}` in
        # mac.schema.json — a load error, not a second relation to loop over).
        src = g.get("source") or {}
        rel, cols = src.get("relation"), src.get("columns")
        # A RELATION-OWNED CONCEPT names its relation and the columns of it it serves; the facts
        # live on the relation. Resolved here so one census covers BOTH forms and the denominator
        # is the bundle's real population either way.
        if not src and isinstance(g.get("bindings"), list) and g["bindings"]:
            binding = g["bindings"][0] or {}
            rel = binding.get("relation")
            declared = relations.get(str(rel), {})
            serves = binding.get("serves") or []
            cols = {name: declared.get(name) for name in serves if name in declared}
            forms["binding"] += 1
        if isinstance(cols, dict):          # THE COLUMN MAP — the standard's own form
            forms["map"] += 1
            for name, body in cols.items():
                body = body or {}
                # THE SLOT IS `offers`, A MAP, since 2026-10-07 (it was `roles` for one day, and
                # `role`/`query_use` before that). `offers` is the set of USE names the column
                # claims, each of which must be a declared member; the terms within them are
                # checked against their own vocabularies below. `references` is NOT a use — it
                # moved to its own top-level key the same revision — so it is read separately and
                # never folded into this census.
                of = body.get("offers") if isinstance(body.get("offers"), dict) else {}
                rows.append(dict(concept=con.get("name"), rel=rel, col=name,
                                 form="binding" if not src else "map",
                                 offers=sorted(of), references=body.get("references"),
                                 axis=of.get("axis"),
                                 mtype=((of.get("aggregate") or {}).get("type")),
                                 rulings=sorted(body.get("rulings") or {})))
        elif isinstance(cols, list):        # the flat list: names only, role in a second home
            forms["flat"] += 1
            for name in cols:
                rows.append(dict(concept=con.get("name"), rel=rel, col=name, form="flat",
                                 offers=[], references=None, axis=None, mtype=None, rulings=[],
                                 legacy_role=(fr.get(name) or "").rsplit(".", 1)[-1] or None))
    if not storage:
        raise RuntimeError(f"no data plane under {bundle/'data'} — nothing to place columns against")
    if not rows:
        raise RuntimeError(f"no concept bindings under {cdir}")
    return storage, rows, {**forms, "_origin": origin}


#: Which closed vocabulary governs each use's TERM. `period_binding` and `suppressed` are a bare
#: flag and a free DQ-finding id, neither of which is a mac vocabulary — the use's own membership
#: is all there is to check for those, and claiming otherwise would invent a namespace. `identity`
#: LEFT THIS TABLE WITH THE USE SET: it is no longer a key under `offers` at all, so there is no
#: term of it left to check here — a column that still writes `offers: {identity: ...}` (the
#: pre-rev-5 habit) is caught by the membership check below, as an offered use outside the set.
_ROLE_TERM_VOCAB = {
    "axis": "concept.axis",
}


def check(storage: dict, rows: list[dict], terms: dict) -> list[str]:
    bad: list[str] = []
    for (rel, col), role in sorted(storage.items()):
        if role is not None and role not in terms["dataset.column.role"]:
            bad.append(f"R1 {rel}.{col} declares data-plane role {role!r}, "
                       f"not a mac.dataset.column.role term")
    # THE COLLISION THIS GATE WAS BUILT FOR IS STRUCTURALLY GONE. The data plane spells its slot
    # `role:`; the concept plane's uses live under `offers:`, a map, so the two can no longer be
    # confused by spelling. What is still checkable, and still worth checking at the BUNDLE level
    # without loading the runtime, is that each use a column claims is a declared member of
    # `mac.concept.column.offers` and each term within it comes from that use's own vocabulary. The
    # runtime refuses the same thing at load; this says it over a bundle on disk, which is where a
    # generator writes.
    seen = set()
    for r in rows:
        for offered in r.get("offers") or []:
            if offered not in terms["concept.column.offers"] and offered not in seen:
                seen.add(offered)
                n = sum(1 for x in rows if offered in (x.get("offers") or []))
                bad.append(
                    f"R2 concept-plane use {offered!r} is not a mac.concept.column.offers member "
                    f"({n} binding(s); the closed set is {terms['concept.column.offers']})"
                )
            vocab = _ROLE_TERM_VOCAB.get(offered)
            value = r.get(offered)
            if vocab and value is not None:
                term = str(value).rsplit(".", 1)[-1]
                if term not in terms[vocab] and (offered, term) not in seen:
                    seen.add((offered, term))
                    bad.append(
                        f"R2 {r['concept']}.{r['col']} declares {offered}: {term!r}, not a "
                        f"mac.{vocab} term (the closed set is {terms[vocab]})"
                    )
        if (r["rel"], r["col"]) not in storage:
            bad.append(f"R3 {r['concept']} binds {r['rel']}.{r['col']}, which the data plane "
                       f"does not measure")
    return bad


def census(storage: dict, rows: list[dict], forms: dict, terms: dict) -> None:
    print(f"\n── the two planes ──")
    print(f"  DATA PLANE     {len(storage)} columns measured over "
          f"{len({r for r, _ in storage})} relations")
    print(f"  CONCEPT PLANE  {len(rows)} column bindings over "
          f"{len({r['concept'] for r in rows})} concepts")
    print(f"  source form    {forms['map']} column-map / {forms['flat']} flat list")

    print(f"\n── the five uses a column may offer, over {len(rows)} bindings ──")
    for role in terms["concept.column.offers"]:
        n = sum(1 for r in rows if role in (r.get("offers") or []))
        note = "" if n else "   <- declared by no column here"
        print(f"  {role:16} {n:4} of {len(rows)}{note}")
    n = sum(1 for r in rows if r.get("rulings"))
    print(f"  {'rulings':16} {n:4} of {len(rows)}"
          f"{'' if n else '   <- no column carries a ruling here'}")
    n = sum(1 for r in rows if r.get("references"))
    print(f"  {'references':16} {n:4} of {len(rows)}"
          f"{'' if n else '   <- no column points at a concept here'}"
          f"  (not a use — the top-level `references:` key, outside `offers`)")

    # `concept.identity.kind` AND ITS CENSUS ARE RETIRED (2026-10-05): the block is gone from the
    # schema, so this counted `None` once per concept and told a reader nothing. What a column
    # points at is `references` (table above); what makes a row unique is `source.key`, which this
    # gate does not census because `check_concept_columns_exist` already measures it against the
    # relation it names.

    # THE CROSS-TAB IS PER USE OFFERED, not per use name. A column may offer several — 21 of
    # contoso5's 112 are a join key you also group by — so one binding contributes a row per use
    # it claims, and the denominator says so rather than pretending each column has one.
    xt = collections.Counter()
    offered = 0
    for r in rows:
        s = storage.get((r["rel"], r["col"]))
        for role in (r.get("offers") or [None]):
            xt[(s, role)] += 1
            offered += 1
    print(f"\n── storage_role x use offered, the two planes crossed "
          f"({len(xt)} of {len(terms['dataset.column.role']) * len(terms['concept.column.offers'])} "
          f"possible pairs occur over {offered} offer(s)) ──")
    for (s, c), n in sorted(xt.items(), key=lambda x: -x[1]):
        flag = ""
        if (s, c) in SUSPICIOUS:
            flag = "  <- " + SUSPICIOUS[(s, c)]
        elif s is not None and s not in terms["dataset.column.role"]:
            flag = "  <- illegal storage_role"
        elif c is not None and c not in terms["concept.column.offers"]:
            flag = "  <- a use the vocabulary does not declare"
        print(f"  {str(s):20} {str(c or '(offered to nothing)'):22} {n:4}{flag}")

    bound = {(r["rel"], r["col"]) for r in rows}
    origin = forms.get("_origin") or {}
    for plane_name, note in (("served", "a served column nothing binds — a real gap"),
                             ("landing", "raw landing, which a concept is NOT meant to bind")):
        pop = [k for k in storage if origin.get(k) == plane_name]
        orphan = [k for k in pop if k not in bound]
        print(f"\n── {plane_name}: bound by no concept, {len(orphan)} of {len(pop)} ── {note}")
        for rel, col in sorted(orphan)[:6]:
            print(f"  {rel}.{col}")
        if len(orphan) > 6:
            print(f"  … and {len(orphan) - 6} more")


def self_test() -> int:
    """One mutant per reject class. A gate that cannot go red is the zero-denominator pass."""
    terms = {"dataset.column.role": ["value", "primary_key"],
             "concept.column.offers": ["axis", "aggregate", "period_binding", "extremum", "suppressed"],
             "concept.axis": ["time", "categorical"], "concept.column.measure_type": [],
             "concept.column.ruling": [], "name_register": []}
    ok_store = {("t", "a"): "value"}
    # BARE TERMS, not `mac.concept.axis.categorical` — `offers.axis` has been a closed enum of bare
    # strings since 2026-10-07 (column_declaration.md rev 5), and a fixture declaring the dotted
    # spelling would be testing a shape no bundle can write any more.
    ok_rows = [dict(concept="C", rel="t", col="a", form="map", offers=["axis"],
                    axis="categorical", references=None, mtype=None, rulings=[])]
    cases = [
        ("clean", ok_store, ok_rows, 0),
        ("R1 a column_role term in the storage slot", {("t", "a"): "dimension"}, ok_rows, 1),
        ("R1 an invented storage_role", {("t", "a"): "nonsense"}, ok_rows, 1),
        # THE RETIRED SCALAR IS NOW A USE NAME NOBODY DECLARED. `role: attribute` was the old
        # mutant; its successor is a column claiming a USE outside the closed set, which is the
        # same defect one level in.
        ("R2 a use outside the closed set", ok_store,
         [{**ok_rows[0], "offers": ["attribute"]}], 1),
        # RE-POINTED 2026-10-07: the old mutant wrote `offers: {identity: part}` — `identity` was a
        # USE sharing this slot. `identity` LEFT THE SET ENTIRELY (it is the top-level `references:`
        # key now), so the mutation that still exercises this reject class is an author keeping the
        # pre-rev-5 habit of writing it AS a use — `offers: [identity]` — which R2's membership
        # check catches the same way it catches `attribute`: the dead address is now unreachable
        # (there is no `identity` TERM left to validate inside `offers`), so this mutant moved one
        # level up, to the use name itself, rather than being dropped.
        ("R2 `identity` written as a use (the pre-rev-5 habit)", ok_store,
         [{**ok_rows[0], "offers": ["identity"]}], 1),
        ("R2 an axis kind nobody declared", ok_store,
         [{**ok_rows[0], "axis": "none"}], 1),
        ("R3 a binding the data plane does not measure", ok_store,
         [{**ok_rows[0], "col": "ghost"}], 1),
    ]
    fails = 0
    for label, st, rw, want in cases:
        got = 1 if check(st, rw, terms) else 0
        ok = got == want
        print(("  ok   " if ok else "  FAIL ") + label)
        fails += 0 if ok else 1
    print(f"\n{NAME} --self-test: {'passed' if not fails else str(fails) + ' FAILED'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", nargs="?")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        print(f"── {NAME} --self-test ──")
        return self_test()
    if not a.bundle:
        print(f"{NAME}: exit 2 — no bundle given", file=sys.stderr)
        return 2

    b = pathlib.Path(a.bundle).expanduser().resolve()
    try:
        terms = load_terms()
        storage, rows, forms = read_planes(b)
    except Exception as e:                                  # noqa: BLE001 — exit 2 is the contract
        print(f"{NAME}: exit 2 — could not run: {e}", file=sys.stderr)
        return 2

    bad = check(storage, rows, terms)
    print(f"{NAME}: {'FAIL' if bad else 'PASS'} — {len(storage)} measured columns, "
          f"{len(rows)} concept bindings, {len(bad)} finding(s) [{b.name}]")
    for f in bad:
        print(f"  - {f}")
    if a.census:
        census(storage, rows, forms, terms)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
