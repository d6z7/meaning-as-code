#!/usr/bin/env python3
"""Render a protosql fragment — the collapse you cannot type wrong, because you do not type it.

THE FRAGMENT WAS ALREADY WRITTEN. gaps/fpl2 authored ontology/protosql/snapshot.pin_latest_per_cell
on 2026-08-16, with `PARTITION BY @cols:cell_key` and a slot that dereferences the relation's own
declared key. Its header explains itself:

    "this same collapse was got WRONG FOUR TIMES IN ONE DAY by careful parties ... Every one of those
     was a correct instruction, correctly read, and then re-implemented from memory at the call site."

Three days later the assistant re-implemented it from memory at the call site — twice, in the two
properties whose job is to guard the grain (P-GRAIN-01, P-VINT-01: five columns against a declared
seven). It could not have done otherwise: `grep -rln "@cols:"` over the framework returned NOTHING.
The fragment had no renderer. It was a fix that was designed, documented, cited as authority in three
separate files, and never made executable — so ~50 files in the bundle hand-write the collapse.

This is the renderer. It resolves the slot grammar the fragment already declares:

    @@name              a CTE name                       cte:<name>
    @rel:x              a relation, from the caller      register:<path>
    @cols:x             a COLUMN LIST, dereferenced      descriptor:@rel:x#<yaml.path>
    @col:x              one column of a bound relation   @rel:x.<column>

WHAT MAKES IT A FIX RATHER THAN A CONVENIENCE — it refuses, loudly, in the four cases where a
hand-written collapse silently produces a wrong number:

  · the relation is not in `binds_for`         — no verified cell key, so no partition is defensible
  · the descriptor declares no cell_key        — same, stated by absence rather than by list
  · a @col: slot names a column the relation   — the tie-break vanishes and ROW_NUMBER breaks ties by
    does not have                                scan order, which is unstable rather than merely wrong
  · a slot in the fragment has no binding      — a silently-empty substitution is how a PARTITION BY
                                                 loses columns

NO NEW YAML. Reads `rule.fragment`, `rule.slots`, `rule.binds_for` — all authored already.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import pathlib
import re
import sys

import yaml

SLOT = re.compile(r"@@[A-Za-z_][A-Za-z0-9_]*|@(?:cols|col|rel):[A-Za-z_][A-Za-z0-9_]*")


class RefusedToRender(Exception):
    """A collapse that cannot be rendered correctly is REFUSED, never approximated."""


def _descriptors(root: str) -> dict:
    """relation name (bare and schema-qualified) -> parsed dataset descriptor."""
    out = {}
    for f in sorted(glob.glob(os.path.join(root, "data", "datasets", "*.yaml"))):
        doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
        tbl = (doc.get("table") or {})
        stem = os.path.basename(f)[:-5]
        doc["__file__"] = os.path.relpath(f, root)
        for n in {stem, tbl.get("name"), f"{tbl.get('schema')}.{tbl.get('name')}"}:
            if n:
                out[n] = doc
    return out


def _dig(doc: dict, path: str):
    """Walk a dotted yaml path — 'x-grain.cell_key' — returning None at the first missing step."""
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def load_fragment(root: str, frag_id: str) -> dict:
    for f in sorted(glob.glob(os.path.join(root, "**", "protosql", "*.yaml"), recursive=True)):
        doc = yaml.safe_load(open(f, encoding="utf-8")) or {}
        rule = doc.get("rule") or {}
        if rule.get("id") == frag_id or os.path.basename(f)[:-5] == frag_id:
            rule["__file__"] = os.path.relpath(f, root)
            return rule
    raise RefusedToRender(f"no protosql fragment with id {frag_id!r} under {root}")


def render(root: str, frag_id: str, bindings: dict[str, str]) -> tuple[str, dict]:
    """Render `frag_id` with `bindings` ({register name -> relation}). Returns (sql, provenance)."""
    rule = load_fragment(root, frag_id)
    frag, slots = rule.get("fragment") or "", rule.get("slots") or {}
    if not frag:
        raise RefusedToRender(f"{frag_id} declares no `fragment`")

    desc = _descriptors(root)
    rels: dict[str, tuple[str, dict]] = {}
    resolved: dict[str, str] = {}
    prov: dict = {"fragment": rule["__file__"], "id": frag_id, "sources": []}

    # PASS 1 — relations, because every other slot dereferences through one.
    for slot, spec in slots.items():
        if not slot.startswith("@rel:"):
            continue
        name = slot[len("@rel:"):]
        given = bindings.get(name)
        if not given:
            raise RefusedToRender(
                f"slot {slot} is bound from {spec!r} and no binding was supplied for {name!r}")
        d = desc.get(given)
        if d is None:
            raise RefusedToRender(f"{slot}={given!r} — no dataset descriptor declares that relation")
        binds_for = rule.get("binds_for") or []
        stem = os.path.basename(d["__file__"])[:-5]
        if binds_for and not ({given, stem, (d.get("table") or {}).get("name")} & set(binds_for)):
            raise RefusedToRender(
                f"{slot}={given!r} is not in {frag_id}.binds_for {binds_for} — a relation with no "
                f"verified cell key cannot bind this collapse, and improvising a partition over data "
                f"with no unique cell is the defect this fragment exists to prevent")
        tbl = d.get("table") or {}
        phys = ".".join(p for p in (tbl.get("schema"), tbl.get("name")) if p) or given
        rels[name] = (phys, d)
        resolved[slot] = phys
        prov["sources"].append({"slot": slot, "from": d["__file__"], "value": phys})

    def rel_of(ref: str) -> tuple[str, str, dict]:
        m = re.match(r"@rel:([A-Za-z_][A-Za-z0-9_]*)", ref)
        if not m or m.group(1) not in rels:
            raise RefusedToRender(f"slot spec {ref!r} references an unbound relation")
        phys, d = rels[m.group(1)]
        return m.group(1), phys, d

    # PASS 2 — everything else.
    for slot, spec in slots.items():
        if slot in resolved:
            continue
        spec = str(spec)

        if slot.startswith("@@"):
            resolved[slot] = spec.split(":", 1)[1] if spec.startswith("cte:") else slot[2:]

        elif slot.startswith("@cols:"):
            # TWO SOURCES since v0.1.14. `descriptor:` reads the meaning plane; `profile:` reads the
            # MEASUREMENT plane, data/profiles/<stem>.yaml, which is where a DERIVED key lives. The
            # collapse partition is the one thing that must never be typed by hand — it was, as
            # x-grain.cell_key, and two of the four declarations were false against the warehouse
            # while still reading as VERIFIED.
            if not spec.startswith(("descriptor:", "profile:")):
                raise RefusedToRender(f"{slot}: only `descriptor:` or `profile:` column lists are "
                                      f"supported, got {spec!r}")
            src = "profile" if spec.startswith("profile:") else "descriptor"
            ref, _, path = spec[len(src) + 1:].partition("#")
            _, phys, d = rel_of(ref)
            if src == "profile":
                # `__file__` is stored RELATIVE to the bundle root (line 62), so it must be joined
                # back onto root — resolving it against the cwd finds nothing unless you happen to be
                # standing in the bundle, which is exactly the kind of works-on-my-machine path bug
                # a REFUSED message makes look like a missing measurement.
                stem = pathlib.Path(d["__file__"]).stem
                pf = pathlib.Path(root) / "data" / "profiles" / f"{stem}.yaml"
                if not pf.exists():
                    raise RefusedToRender(
                        f"{slot}: no measurement for {stem} at {pf} — run mac_admit_identity.py. The "
                        f"collapse is REFUSED rather than rendered over a key nobody measured")
                pdoc = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
                pdoc["__file__"] = str(pf)
                cols = _dig(pdoc, path)
                srcfile = str(pf)
            else:
                cols = _dig(d, path)
                srcfile = d["__file__"]
            # A COLLAPSE PARTITION IS THE GRAIN MINUS WHAT IT COLLAPSES OVER. The grain identifies a
            # row; the partition identifies the thing being reduced to one row. Subtracting is not
            # optional: partition on the axis you are collapsing and every value becomes its own
            # group, so the collapse does nothing — the fragment's own never_2 clause says exactly
            # that about config_key.
            over = [str(x) for x in (rule.get("collapses_over") or [])]
            if over and isinstance(cols, list):
                cols = [c for c in cols if c not in over]
            if not cols:
                raise RefusedToRender(
                    f"{slot}: {srcfile} declares no {path} — the collapse is REFUSED rather "
                    f"than rendered over an undeclared key")
            if not isinstance(cols, list) or not all(isinstance(c, str) for c in cols):
                raise RefusedToRender(f"{slot}: {srcfile}#{path} is not a list of column names")
            have = {c.get("name") for c in (d.get("columns") or []) if isinstance(c, dict)}
            missing = [c for c in cols if have and c not in have]
            if missing:
                raise RefusedToRender(
                    f"{slot}: {srcfile}#{path} names {missing}, which the relation does not have")
            resolved[slot] = ", ".join(cols)
            prov["sources"].append({"slot": slot, "from": f"{srcfile}#{path}",
                                    "value": cols, "n": len(cols)})

        elif slot.startswith("@col:"):
            m = re.match(r"(@rel:[A-Za-z_][A-Za-z0-9_]*)\.(.+)$", spec)
            if not m:
                raise RefusedToRender(f"{slot}: expected '@rel:x.column', got {spec!r}")
            _, phys, d = rel_of(m.group(1))
            col = m.group(2)
            have = {c.get("name") for c in (d.get("columns") or []) if isinstance(c, dict)}
            if have and col not in have:
                raise RefusedToRender(
                    f"{slot}: {d['__file__']} has no column {col!r}. For a tie-break column this is "
                    f"not cosmetic — without it ROW_NUMBER breaks ties by scan order and the same "
                    f"SQL returns different numbers on different runs")
            resolved[slot] = col
            prov["sources"].append({"slot": slot, "from": d["__file__"], "value": col})

    # THE never_2 GUARD, self-detecting: the fragment binds both the key and the vintage column, so
    # the renderer never needs telling which column is the vintage. If the key CONTAINS it, every
    # vintage becomes its own partition and the collapse collapses nothing — the fragment says so in
    # its own words, and until now nothing enforced it. Caught fpl_ob_reach_kpi on the first run:
    # its descriptor declares `excludes_vintage: true` AND lists config_reporting_month in cell_key.
    vintage = resolved.get("@col:vintage")
    for slot, spec in slots.items():
        if not slot.startswith("@cols:") or slot not in resolved or not vintage:
            continue
        cols = [c.strip() for c in resolved[slot].split(",")]
        if vintage in cols:
            src = next((s0["from"] for s0 in prov["sources"] if s0["slot"] == slot), "?")
            raise RefusedToRender(
                f"{slot}: {src} includes {vintage!r}, which is the VINTAGE this fragment orders by. "
                f"Partition on it and every vintage becomes its own group — the collapse does nothing "
                f"at all, and every read returns one row per republication instead of one per cell. "
                f"({frag_id}.never_2). Fix the declared key, not this call site.")

    used = set(SLOT.findall(frag))
    unbound = sorted(used - set(resolved))
    if unbound:
        raise RefusedToRender(
            f"{frag_id}: fragment uses {unbound} which `slots` does not define — an unbound slot "
            f"substitutes to nothing, which is exactly how a PARTITION BY loses columns")

    sql = frag
    for slot in sorted(resolved, key=len, reverse=True):
        sql = sql.replace(slot, resolved[slot])
    if SLOT.search(sql):
        raise RefusedToRender(f"{frag_id}: unsubstituted slot(s) remain: {SLOT.findall(sql)}")
    prov["disclose"] = rule.get("disclose")
    return sql.rstrip() + "\n", prov


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("fragment")
    ap.add_argument("--bind", action="append", default=[], metavar="NAME=RELATION")
    ap.add_argument("--all", action="store_true", help="render once per relation in binds_for")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    binds = dict(b.split("=", 1) for b in a.bind if "=" in b)
    try:
        if a.all:
            rule = load_fragment(a.root, a.fragment)
            reg = next((s[len("@rel:"):] for s in (rule.get("slots") or {}) if s.startswith("@rel:")), None)
            out = []
            for rel in (rule.get("binds_for") or []):
                sql, prov = render(a.root, a.fragment, {**binds, reg: rel})
                out.append({"relation": rel, "sql": sql, "provenance": prov})
                if not a.json:
                    n = next((s["n"] for s in prov["sources"] if s.get("n")), "?")
                    print(f"── {rel}  ({n} key column(s), read from "
                          f"{next(s['from'] for s in prov['sources'] if s.get('n'))})")
                    print(sql)
            if a.json:
                print(json.dumps(out, indent=1))
            return 0
        sql, prov = render(a.root, a.fragment, binds)
        print(json.dumps({"sql": sql, "provenance": prov}, indent=1) if a.json else sql)
        return 0
    except RefusedToRender as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
