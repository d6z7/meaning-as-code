#!/usr/bin/env python3
"""check_column_planes.py — every column placed in BOTH planes, and the slots that crossed them.

THE OPERATOR'S TWO-PLANE MAP, 2026-09-27, turned into a gate. The map says which closed vocabulary
governs which slot, and separates them by PLANE:

    DATA PLANE     data/sources/*.yaml · data/datasets/*.yaml
                   columns[].role -> mac.dataset.column.role (5)   the PHYSICAL shape in the relation
    CONCEPT PLANE  ontology/concepts/**/*.yaml
                   concept.identity.kind -> mac.concept.identity (7)      per CONCEPT
                   the column map's four slots:
                     role         -> mac.concept.column.role   (5)   where a QUERY may use it
                     identity     -> mac.concept.column.identity (3)   its part in identity
                     measure.type -> mac.MeasureType   (5)   which folds are legal
                     rulings      -> mac.concept.column.ruling (4)   what a PERSON decided
                                     register -> mac.name_register (5)

WHY THE SPLIT IS WHAT MAKES THE GATE POSSIBLE. Both planes spell the slot `role:`. One takes
`mac.dataset.column.role`, the other `mac.concept.column.role`, and the two sets SHARE NO TERM — so a term from
the wrong side is detectable, and is detectable ONLY once the planes are named. Measured on contoso
the day this gate was written: `dim_contoso_store.Channel` declares `role: dimension` in the DATA
plane, which is a column.role term in a storage_role slot. Read as one undifferentiated "role", it
looks correct.

WHAT IT REDS ON
  R1  a data-plane role outside mac.dataset.column.role
  R2  a concept-plane role outside mac.concept.column.role — this is where a RETIRED term surfaces:
      `attribute` was replaced by `housekeeping` and the vocabulary no longer defines it
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
    ("foreign_key", "dimension"):
        "a pointer used as a category — 'that is a pointer, not a category, even though its "
        "cardinality looks dimension-sized' (column_roles.md §1)",
    ("value", "key"):
        "a payload column doing identity duty — the data plane measured no key shape here",
    ("primary_key", "dimension"):
        "the relation's own identity offered as an axis",
}


def load_terms() -> dict[str, list[str]]:
    raw = _mv.flatten(yaml.safe_load(VOCAB.read_text(encoding="utf-8")) or {})
    out = {}
    # `measure_type`, NOT `MeasureType`: the namespace is lower_snake in mac_vocabulary.yaml and
    # its members are lowercase (flow, stock, intensive, precomputed, target). The capitalised
    # spelling survives in 8 framework files and in the runtime's fold-law drift test, where it
    # raises KeyError instead of comparing a cell. Asking for the wrong name here returned an
    # empty list in silence, which is the same defect one layer up.
    for ns in ("dataset.column.role", "concept.column.role", "concept.column.identity", "concept.identity",
               "concept.column.measure_type", "concept.column.ruling", "name_register"):
        spec = raw.get(ns) or {}
        out[ns] = list((spec.get("terms") or spec.get("members") or {}))
    if not out["dataset.column.role"] or not out["concept.column.role"]:
        raise RuntimeError("mac_vocabulary.yaml did not yield the two role vocabularies")
    return out


def read_planes(bundle: pathlib.Path) -> tuple[dict, list[dict], collections.Counter, dict]:
    """(data plane, concept bindings, identity kinds, form counts). Raises if a plane is absent."""
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

    rows: list[dict] = []
    kinds: collections.Counter = collections.Counter()
    forms = {"map": 0, "flat": 0}
    cdir = bundle / "ontology" / "concepts"
    for p in sorted(cdir.rglob("*.yaml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        con, g = d.get("concept") or {}, d.get("grounding") or {}
        kinds[(con.get("identity") or {}).get("kind")] += 1
        fr = g.get("field_roles") or {}
        for src in (g.get("sources") or []):
            rel, cols = src.get("relation"), src.get("columns")
            if isinstance(cols, dict):          # THE COLUMN MAP — the standard's own form
                forms["map"] += 1
                for name, body in cols.items():
                    body = body or {}
                    rows.append(dict(concept=con.get("name"), rel=rel, col=name, form="map",
                                     role=body.get("role"), identity=body.get("identity"),
                                     mtype=((body.get("measure") or {}).get("type")),
                                     rulings=sorted(body.get("rulings") or {})))
            elif isinstance(cols, list):        # the flat list: names only, role in a second home
                forms["flat"] += 1
                for name in cols:
                    rows.append(dict(concept=con.get("name"), rel=rel, col=name, form="flat",
                                     role=(fr.get(name) or "").rsplit(".", 1)[-1] or None,
                                     identity=None, mtype=None, rulings=[]))
    if not storage:
        raise RuntimeError(f"no data plane under {bundle/'data'} — nothing to place columns against")
    if not rows:
        raise RuntimeError(f"no concept bindings under {cdir}")
    return storage, rows, kinds, {**forms, "_origin": origin}


def check(storage: dict, rows: list[dict], terms: dict) -> list[str]:
    bad: list[str] = []
    for (rel, col), role in sorted(storage.items()):
        if role is not None and role not in terms["dataset.column.role"]:
            other = " — a mac.concept.column.role term in a mac.dataset.column.role slot" \
                if role in terms["concept.column.role"] else ""
            bad.append(f"R1 {rel}.{col} declares data-plane role {role!r}, "
                       f"not a mac.dataset.column.role term{other}")
    seen = set()
    for r in rows:
        role = r["role"]
        if role is not None and role not in terms["concept.column.role"] and role not in seen:
            seen.add(role)
            n = sum(1 for x in rows if x["role"] == role)
            bad.append(f"R2 concept-plane role {role!r} is not a mac.concept.column.role term "
                       f"({n} binding(s); the closed set is {terms['concept.column.role']})")
        if (r["rel"], r["col"]) not in storage:
            bad.append(f"R3 {r['concept']} binds {r['rel']}.{r['col']}, which the data plane "
                       f"does not measure")
    return bad


def census(storage: dict, rows: list[dict], kinds: collections.Counter,
           forms: dict, terms: dict) -> None:
    print(f"\n── the two planes ──")
    print(f"  DATA PLANE     {len(storage)} columns measured over "
          f"{len({r for r, _ in storage})} relations")
    print(f"  CONCEPT PLANE  {len(rows)} column bindings over "
          f"{len({r['concept'] for r in rows})} concepts")
    print(f"  source form    {forms['map']} column-map / {forms['flat']} flat list")

    print(f"\n── the four column-map slots, over {len(rows)} bindings ──")
    for slot, f in (("role", lambda r: r["role"]), ("identity", lambda r: r["identity"]),
                    ("measure.type", lambda r: r["mtype"]), ("rulings", lambda r: r["rulings"])):
        n = sum(1 for r in rows if f(r))
        note = "" if n else "   <- the standard's own form is unused here"
        print(f"  {slot:14} {n:4} of {len(rows)}{note}")

    print(f"\n── identity.kind, over {sum(kinds.values())} concepts "
          f"({len([k for k in kinds if k])} of {len(terms['concept.identity'])} terms used) ──")
    for k, n in kinds.most_common():
        print(f"  {str(k):16} {n}")
    unused = [t for t in terms["concept.identity"] if t not in kinds]
    if unused:
        print(f"  unused: {', '.join(unused)}")

    xt = collections.Counter()
    for r in rows:
        s = storage.get((r["rel"], r["col"]))
        xt[(s, r["role"])] += 1
    print(f"\n── storage_role x column.role, the two planes crossed "
          f"({len(xt)} of {len(terms['dataset.column.role']) * len(terms['concept.column.role'])} possible pairs occur) ──")
    for (s, c), n in sorted(xt.items(), key=lambda x: -x[1]):
        flag = ""
        if (s, c) in SUSPICIOUS:
            flag = "  <- " + SUSPICIOUS[(s, c)]
        elif s is not None and s not in terms["dataset.column.role"]:
            flag = "  <- illegal storage_role"
        elif c is not None and c not in terms["concept.column.role"]:
            flag = "  <- retired/illegal column_role"
        print(f"  {str(s):20} {str(c):16} {n:4}{flag}")

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
    terms = {"dataset.column.role": ["value", "primary_key"], "concept.column.role": ["key", "dimension"],
             "concept.identity": [], "concept.column.identity": [], "measure_type": [],
             "concept.column.ruling": [], "name_register": []}
    ok_store = {("t", "a"): "value"}
    ok_rows = [dict(concept="C", rel="t", col="a", role="dimension", identity=None,
                    mtype=None, rulings=[], form="flat")]
    cases = [
        ("clean", ok_store, ok_rows, 0),
        ("R1 a column_role term in the storage slot", {("t", "a"): "dimension"}, ok_rows, 1),
        ("R1 an invented storage_role", {("t", "a"): "nonsense"}, ok_rows, 1),
        ("R2 a retired column_role", ok_store,
         [{**ok_rows[0], "role": "attribute"}], 1),
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
        storage, rows, kinds, forms = read_planes(b)
    except Exception as e:                                  # noqa: BLE001 — exit 2 is the contract
        print(f"{NAME}: exit 2 — could not run: {e}", file=sys.stderr)
        return 2

    bad = check(storage, rows, terms)
    print(f"{NAME}: {'FAIL' if bad else 'PASS'} — {len(storage)} measured columns, "
          f"{len(rows)} concept bindings, {len(bad)} finding(s) [{b.name}]")
    for f in bad:
        print(f"  - {f}")
    if a.census:
        census(storage, rows, kinds, forms, terms)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
