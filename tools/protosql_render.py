#!/usr/bin/env python3
"""Render a protosql fragment — the collapse you cannot type wrong, because you do not type it.

THE FRAGMENT WAS ALREADY WRITTEN. <domain>/<dataset> authored ontology/protosql/snapshot.pin_latest_per_cell
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
    @frag:x             another fragment, inlined        fragment:<id>
    @join:x             a JOIN PREDICATE, dereferenced   edge:<edge_id>

WHAT MAKES IT A FIX RATHER THAN A CONVENIENCE — it refuses, loudly, in the four cases where a
hand-written collapse silently produces a wrong number:

  · the relation is not in `binds_for`         — no verified cell key, so no partition is defensible
  · the descriptor declares no cell_key        — same, stated by absence rather than by list
  · a @col: slot names a column the relation   — the tie-break vanishes and ROW_NUMBER breaks ties by
    does not have                                scan order, which is unstable rather than merely wrong
  · a slot in the fragment has no binding      — a silently-empty substitution is how a PARTITION BY
                                                 loses columns

THE GRAMMAR TYPED THE COLUMNS AND NOT THE JOIN (@join:, decision 0018 S3, 2026-09-16). A second
fragment — `grouping.additive_rollup` — composed with the pinning fragment above, resolved every slot,
was refused by nothing, produced valid SQL, and RETURNED ZERO ROWS. Its predicate was free SQL text
reading `f.market = m.territory_code`. Measured that day against the live warehouse:

    seller_territory -> dim_seller_territory   578 / 578 resolve   (the right column)
    market                 -> dim_territory_register     0 / 206 resolve     (the one that was typed)
    item_key         -> dim_territory_register     0 / 1106 resolve

Both columns exist on the fact. Both are correctly typed. They are in different namespaces, and a
predicate that resolves NOTHING is indistinguishable at render time from one that resolves
everything — until someone counts. So the join stops being free text: `@join:` dereferences the
edge, and the edge carries the predicate plus the measurement that proves it.

NO NEW YAML. Reads `rule.fragment`, `rule.slots`, `rule.binds_for` — all authored already — and, for
`@join:`, the bundle's `ontology/edges.yaml`, which S1/S2 of 0018 already made authoritative.
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

SLOT = re.compile(r"@@[A-Za-z_][A-Za-z0-9_]*|@(?:cols|col|rel|frag|join):[A-Za-z_][A-Za-z0-9_]*")

# Every qualified column reference in a predicate: group(1) the qualifier chain with its trailing
# dot ("v_fact_kpi." or "warehouse.v_fact_kpi."), group(2) the column. Scanned rather than matched against
# one `a.x = b.y` shape so a compound predicate (`... AND ...`) still has EVERY side checked — a
# predicate whose second clause names an unbound relation is exactly as silent as one whose first
# does, and a shape-matcher would wave it through.
QUALIFIED_COL = re.compile(r"\b((?:[A-Za-z_]\w*\.)+)([A-Za-z_]\w*)\b")

# Reject classes for the @join: judge. Named so a self-test can seed one mutant per class and a
# refusal message can be traced back to the rule that produced it.
JOIN_ABSENT = "edge-not-found"
JOIN_NOT_A_JOIN = "realisation-is-not-a-join"
JOIN_UNREALISED = "edge-declares-no-realisation"
JOIN_UNVERIFIED = "join-predicate-unmeasured"
JOIN_SHAPELESS = "predicate-names-no-two-relations"
JOIN_UNBOUND = "join-over-unbound-relation"


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


def _edges(root: str) -> dict:
    """edge_id -> edge, read from the bundle's ontology/edges.yaml."""
    f = pathlib.Path(root) / "ontology" / "edges.yaml"
    if not f.exists():
        raise RefusedToRender(
            f"@join: dereferences {f}, which does not exist. A join predicate is a measured claim "
            f"about two relations; with no edges file there is nothing to dereference and the "
            f"fragment would be back to free SQL text, which is the defect @join: exists to end")
    doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return {str(e.get("edge_id")): e for e in (doc.get("edges") or []) if e.get("edge_id")}


def judge_join(edge_id: str, edge: dict | None, bound: set[str]) -> tuple[str, str] | None:
    """PURE: (edge_id, edge-or-None, the relation names the fragment bound) -> (class, why) or None.

    Free of the filesystem so every branch can be exercised offline with a seeded edge — the rule
    that decides whether a join may be emitted must be testable without a bundle and without a
    warehouse, the same way check_edge_joins_measured's judge is.
    """
    if edge is None:
        return (JOIN_ABSENT,
                f"no edge {edge_id!r} in ontology/edges.yaml. A join that names no edge is free SQL "
                f"text wearing a slot's clothes, and free SQL text is what returned zero rows")

    # join_rule WINS when an edge declares more than one realisation — item__has_tier
    # carries both a join_rule and a resolved_by, because the transform conforms the label while the
    # canonical id travels with it. That is the same precedence ontology/edges.json projects into its
    # `realisation` field, and disagreeing with the estate's own index here would mean an edge reads
    # as joinable in one file and as a category error in another.
    pred = edge.get("join_rule")
    if not (isinstance(pred, str) and pred.strip()):
        # THE CATEGORY ERROR — 0018 S3-AC2, and the criterion the whole decision exists for. An
        # edge realised by a RULE (`resolved_by`) or by a COLUMN ON THE FACT (`realized_by`) is
        # fully declared; it simply is not reached by a join. `child__of_group` says in its own
        # notes "there is no grouping key". The spike asked it for a join anyway, was refused by
        # nothing, and returned an empty result. Naming the realisation and quoting the edge's own
        # note is the point: the caller is not missing a predicate, the caller is asking the wrong
        # question, and only the edge's prose says what the right one is.
        via = [(k, edge[k]) for k in ("resolved_by", "realized_by") if edge.get(k)]
        if via:
            k, v = via[0]
            note = " ".join(str(edge.get("notes") or "").split())
            return (JOIN_NOT_A_JOIN,
                    f"edge {edge_id!r} is NOT realised by a join — it is realised by {k}: {v!r}. "
                    f"Asking for a join predicate here is a CATEGORY ERROR: there is no key to join "
                    f"on, so any predicate you write instead will be valid SQL that matches nothing"
                    + (f'. The edge says so itself: "{note}"' if note else ""))
        # BACKSTOP, NOT THE LIVE CASE. Schema v0.1.18 makes a realisation-less physical edge
        # unauthorable, so this cannot be reached from a conforming bundle — it is here because a
        # renderer that falls through on an unexpected shape emits nothing, and emitting nothing
        # into a predicate is how a join silently becomes a cross product.
        return (JOIN_UNREALISED,
                f"edge {edge_id!r} declares NO realisation at all — not a join, not a rule, not a "
                f"column. Nobody has said how this relationship is reached")

    if not edge.get("verified_by"):
        # 0018 S3-AC3. A declared predicate is a CLAIM, and the spike proved a claim can be
        # confidently wrong while reading as correct: both candidate columns existed and were
        # correctly typed, one resolved 578/578 and the other 0/206. Nothing about the text
        # distinguishes them. Only the measurement does, so rendering across an unmeasured
        # predicate is refused rather than gambled on.
        return (JOIN_UNVERIFIED,
                f"edge {edge_id!r} declares a join predicate but carries no `verified_by` — nobody "
                f"has counted whether its keys resolve or how far they fan out. A predicate that "
                f"resolves nothing is indistinguishable from one that resolves everything until "
                f"someone measures it; run mac_measure_edges.py rather than rendering on faith")

    sides = {q[:-1] for q, _ in QUALIFIED_COL.findall(pred)}
    if len(sides) < 2:
        return (JOIN_SHAPELESS,
                f"edge {edge_id!r} join_rule {pred!r} does not name two qualified relations, so "
                f"which relations it joins cannot be established — and a predicate whose sides "
                f"cannot be established cannot be checked against what the fragment bound")

    unbound = sorted(s for s in sides if s not in bound)
    if unbound:
        # WHY BOUNDNESS IS A REFUSAL AND NOT A WARNING. v1 emits the predicate VERBATIM (see the
        # render branch), so every relation it names must be a relation the fragment actually put in
        # its FROM/JOIN through @rel:. Substituting `dim_territory_register.territory_code = ...` into a
        # fragment that never joined dim_territory_register does not error in SQL — the planner is
        # free to resolve the name itself and the join silently targets something the fragment never
        # declared. That is the same class of silence as the zero-row spike.
        return (JOIN_UNBOUND,
                f"edge {edge_id!r} join_rule {pred!r} names relation(s) {unbound} which this "
                f"fragment has not bound via @rel: (bound: {sorted(bound)}). v1 emits the predicate "
                f"verbatim, so an unbound side is a join against a relation the fragment never put "
                f"in its FROM — valid SQL aimed at the wrong thing")
    return None


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
    bound_names: set[str] = set()
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
        # BINDS_FOR CONSTRAINS THE RELATION BEING COLLAPSED, NOT EVERY RELATION IN THE FRAGMENT.
        # It means "this relation's cell key is verified, so a partition over it is defensible".
        # Applied to all slots it also rejects a DIMENSION being joined, which has no cell key to
        # verify and is not being collapsed — so the first rule that joined one was refused for a
        # property it was never claiming. A fragment with one relation is unaffected; one that
        # names its collapse subject has the guard applied there and only there.
        subject = rule.get("collapse_subject")
        stem = os.path.basename(d["__file__"])[:-5]
        guarded = (slot == subject) if subject else True
        if guarded and binds_for and not ({given, stem, (d.get("table") or {}).get("name")} & set(binds_for)):
            raise RefusedToRender(
                f"{slot}={given!r} is not in {frag_id}.binds_for {binds_for} — a relation with no "
                f"verified cell key cannot bind this collapse, and improvising a partition over data "
                f"with no unique cell is the defect this fragment exists to prevent")
        tbl = d.get("table") or {}
        phys = ".".join(p for p in (tbl.get("schema"), tbl.get("name")) if p) or given
        rels[name] = (phys, d)
        # EVERY NAME THIS BOUND RELATION ANSWERS TO, for @join:'s boundness check. edges.yaml states
        # in its own header that a join_rule's relation names are the data/datasets FILE STEMS and
        # NOT the physical view names, while this renderer substitutes the physical name — so a
        # boundness check that accepted only one of the two would refuse every correct predicate in
        # the bundle and teach the next author that the slot is broken.
        bound_names |= {n for n in (given, stem, tbl.get("name"), phys) if n}
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

        if slot.startswith("@frag:"):
            # COMPOSITION. A rule that reduces a fact must first pin it, and pinning is already a
            # fragment. Without this the only way to write the second rule is to RE-TYPE the first
            # one at the call site — which is the precise defect this whole file exists to stop, so
            # a grammar with no composition guarantees the thing it was built to prevent.
            #
            # The sub-fragment is rendered with the SAME bindings and inlined as a named CTE. It is
            # rendered, never copied: change snapshot.as_of_cycle and every rule built on it follows.
            if not spec.startswith("fragment:"):
                raise RefusedToRender(f"{slot}: expected 'fragment:<id>', got {spec!r}")
            sub_id = spec.split(":", 1)[1]
            if sub_id == frag_id:
                raise RefusedToRender(f"{slot}: {frag_id} composes itself")
            sub_sql, sub_prov = render(root, sub_id, bindings)
            body = "\n".join("    " + ln for ln in sub_sql.strip().splitlines())
            resolved[slot] = f"{slot[len('@frag:'):]} AS (\n{body}\n  )"
            prov["sources"].append({"slot": slot, "from": f"fragment:{sub_id}",
                                    "composed": sub_prov.get("sources", [])})

        elif slot.startswith("@join:"):
            # THE JOIN IS WHERE THE MEANING IS. Every other slot in this grammar types a COLUMN, and
            # the spike proved that is not enough: `f.market = m.territory_code` type-checks, renders,
            # refuses nothing and matches 0 of 206 values, while `seller_territory` matches
            # 578 of 578. So the predicate is no longer written at the call site at all — it is
            # dereferenced from the edge that owns it, and only from an edge whose keys were counted.
            if not spec.startswith("edge:"):
                raise RefusedToRender(f"{slot}: expected 'edge:<edge_id>', got {spec!r}")
            eid = spec.split(":", 1)[1]
            edge = _edges(root).get(eid)
            bad = judge_join(eid, edge, bound_names)
            if bad:
                raise RefusedToRender(f"{slot}: [{bad[0]}] {bad[1]}")
            pred = str(edge["join_rule"]).strip()
            # V1 EMITS THE PREDICATE VERBATIM — the limitation, named rather than discovered later
            # (0018 S3 amendment, 2026-09-16). An edge's predicate names PHYSICAL relations
            # (`v_fact_kpi.x = dim_seller_territory.y`). Composed with the pinning fragment the left
            # side is no longer that table, it is a CTE, and this v1 does NOT rewrite either side to
            # the caller's alias or CTE name. It therefore refuses (JOIN_UNBOUND above) rather than
            # emitting a predicate over a relation the fragment did not bind. A fragment that wants
            # to join a pinned CTE must, for now, alias that CTE to the physical relation name or
            # join the physical relation directly. Whether verbatim is sufficient is what building
            # the first composed join will settle; the refusal is what stops it being settled by a
            # wrong number.
            resolved[slot] = pred
            prov["sources"].append({"slot": slot, "from": f"ontology/edges.yaml#{eid}",
                                    "value": pred, "verified_by": edge.get("verified_by")})

        elif slot.startswith("@@"):
            resolved[slot] = spec.split(":", 1)[1] if spec.startswith("cte:") else slot[2:]

        elif slot.startswith("@cols:"):
            # TWO SOURCES since v0.1.14. `descriptor:` reads the meaning plane; `profile:` reads the
            # MEASUREMENT plane, data/profiles/<stem>.yaml, which is where a DERIVED key lives. The
            # collapse partition is the one thing that must never be typed by hand — it was, as
            # x-grain.cell_key, and two of the four declarations were false against the warehouse
            # while still reading as VERIFIED.
            if not spec.startswith(("descriptor:", "profile:", "concept:")):
                raise RefusedToRender(f"{slot}: only `descriptor:`, `profile:` or `concept:` column "
                                      f"lists are supported, got {spec!r}")
            src = ("profile" if spec.startswith("profile:")
                   else "concept" if spec.startswith("concept:") else "descriptor")
            ref, _, path = spec[len(src) + 1:].partition("#")
            # A concept reference is NOT a relation — resolving it through rel_of read `plan_stage`
            # as an unbound relation and refused. Only the descriptor and profile planes key on the
            # bound fact.
            d = None
            if src != "concept":
                _, phys, d = rel_of(ref)
            if src == "concept":
                # A fragment may need a VALUE SET, not a column list — the as-of collapse restricts
                # to the plan stages the concept still admits. Reading it here means the fragment
                # carries no literal: withdraw a label in plan_stage and the collapse follows.
                cf = pathlib.Path(root) / "ontology" / "concepts" / f"{ref}.yaml"
                if not cf.exists():
                    raise RefusedToRender(f"{slot}: no concept at {cf}")
                cdoc = yaml.safe_load(cf.read_text(encoding="utf-8")) or {}
                if path.endswith("values.served_items"):
                    cols = ["'" + str(i["code"]).replace("'", "''") + "'"
                            for i in ((cdoc.get("values") or {}).get("items") or [])
                            if isinstance(i, dict) and i.get("served") is not False and i.get("code")]
                else:
                    cols = _dig(cdoc, path)
                srcfile = str(cf)
                have = None            # value sets are not columns of the relation
            elif src == "profile":
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
            if src != "concept":
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
    # its own words, and until now nothing enforced it. Caught <source>_reach_kpi on the first run:
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


def self_test() -> int:
    """One seeded mutant per way `@join:` can be asked for something it must not emit, and the
    negative controls that stop it refusing predicates which are in fact fine."""
    BOUND = {"v_fact_kpi", "warehouse.v_fact_kpi", "dim_seller_territory"}

    def edge(**kw):
        base = {"edge_id": "measure__of_territory",
                "join_rule": "v_fact_kpi.seller_territory_id = "
                             "dim_seller_territory.seller_territory_id",
                "verified_by": "evidence/edge_measurements.json#measure__of_territory"}
        base.update(kw)
        return {k: v for k, v in base.items() if v is not None}

    cases = [
        # NEGATIVE CONTROLS FIRST — a measured, bound predicate must render, or the slot is merely
        # an elaborate way of never joining anything.
        ("a verified predicate over bound relations renders", "measure__of_territory", edge(), BOUND, None),
        ("the schema-qualified side of the predicate is accepted", "measure__of_territory",
         edge(join_rule="warehouse.v_fact_kpi.a = dim_seller_territory.b"), BOUND, None),
        ("a compound predicate whose every side is bound renders", "measure__of_territory",
         edge(join_rule="v_fact_kpi.a = dim_seller_territory.b AND "
                        "v_fact_kpi.c = dim_seller_territory.d"), BOUND, None),
        # join_rule WINS over a second realisation — item__has_tier is real and
        # carries both. Refusing it would make a measured join unusable.
        ("join_rule wins when the edge also declares resolved_by", "vm__has_brand_group",
         edge(resolved_by="data/transforms/dim_item.yaml#conform"), BOUND, None),
        # MUTANTS — one per refusal the five branches of 0018 S3 require.
        ("an edge id nobody declares", "market__of_narnia", None, BOUND, JOIN_ABSENT),
        # THE CRITERION THE DECISION EXISTS FOR: the spike asked child__of_group for a join, was
        # refused by nothing, and returned zero rows.
        ("a rule-realised edge asked for a join", "child__of_group",
         {"edge_id": "child__of_group",
          "resolved_by": "ontology/concepts/grouping.yaml#...brand_invariant_column",
          "notes": "there is no grouping key"}, BOUND, JOIN_NOT_A_JOIN),
        ("a column-realised edge asked for a join", "measure__of_seller",
         {"edge_id": "measure__of_seller", "realized_by": "v_fact_kpi.seller_code"}, BOUND,
         JOIN_NOT_A_JOIN),
        ("a predicate nobody measured", "measure__of_territory", edge(verified_by=None), BOUND,
         JOIN_UNVERIFIED),
        ("an empty predicate string is not a predicate", "measure__of_territory",
         {"edge_id": "x", "join_rule": "   ", "realized_by": "a.b"}, BOUND, JOIN_NOT_A_JOIN),
        ("a predicate naming only one relation", "measure__of_territory",
         edge(join_rule="v_fact_kpi.a = 1"), BOUND, JOIN_SHAPELESS),
        # THE SPIKE'S OWN SHAPE: the dimension side was never put in the fragment's FROM.
        ("a predicate whose far side the fragment never bound", "child__of_place",
         edge(join_rule="v_fact_kpi.market = dim_territory_register.territory_code"), BOUND,
         JOIN_UNBOUND),
        ("a predicate whose near side the fragment never bound", "measure__of_territory",
         edge(join_rule="v_fact_tm_kpi.a = dim_seller_territory.b"), BOUND, JOIN_UNBOUND),
        ("a compound predicate with one unbound clause still refuses", "measure__of_territory",
         edge(join_rule="v_fact_kpi.a = dim_seller_territory.b AND "
                        "dim_territory_register.c = dim_seller_territory.d"), BOUND, JOIN_UNBOUND),
        ("nothing bound refuses even a perfect predicate", "measure__of_territory", edge(), set(),
         JOIN_UNBOUND),
        # The backstop v0.1.18 makes unauthorable — kept because falling through would emit nothing.
        ("an edge declaring no realisation at all", "orphan", {"edge_id": "orphan"}, BOUND,
         JOIN_UNREALISED),
    ]
    bad = 0
    for name, eid, e, bound, want in cases:
        got = judge_join(eid, e, bound)
        cls = got[0] if got else None
        if cls != want:
            bad += 1
            print(f"  [SELF-TEST FAIL] {name}: got {cls!r}, expected {want!r}")
        # A REFUSAL THAT DOES NOT NAME THE EDGE is a refusal nobody can act on — the spike's whole
        # cost was an outcome that said nothing about why.
        if got and eid not in got[1]:
            bad += 1
            print(f"  [SELF-TEST FAIL] {name}: refusal does not name {eid!r}")
    # S3-AC2 demands more than a refusal: it must say what the edge IS realised by and quote the
    # edge's own words. Asserted on the exact edge that produced the zero rows.
    r = judge_join("child__of_group",
                   {"edge_id": "child__of_group", "resolved_by": "grouping.yaml#resolve",
                    "notes": "there is no grouping key and no pre-aggregated grouping row"}, BOUND)
    for must in ("resolved_by", "grouping.yaml#resolve", "there is no grouping key"):
        if not r or must not in r[1]:
            bad += 1
            print(f"  [SELF-TEST FAIL] category-error refusal omits {must!r}")
    n = len(cases) + 3
    print(f"{'PASS' if not bad else 'FAIL'}: protosql_render @join: self-test — {n - bad}/{n} "
          f"assertion(s): 11 mutant(s) of the rule (unknown edge, rule-realised, column-realised, "
          f"unmeasured, blank predicate, one-sided predicate, far side unbound, near side unbound, "
          f"compound with an unbound clause, nothing bound, no realisation) and 4 negative "
          f"control(s) (verified+bound renders, schema-qualified side, compound all-bound, "
          f"join_rule wins over a second realisation)")
    return 1 if bad else 0


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return self_test()
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
