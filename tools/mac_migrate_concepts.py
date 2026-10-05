#!/usr/bin/env python3
"""mac_migrate_concepts.py — a concept on the legacy shape becomes a concept on the column standard.

WHAT MOVES. `grounding.table` / `schema` / `key_column` / `field_roles` become `grounding.sources[]`
with a `columns:` MAP (role on the column); `concept.identity.canonical_key` becomes `identity:
canonical` on that column and is removed from the concept (one home); the retired namespaces are
renamed in place — `mac.MeasureType.Flow` -> `mac.concept.column.measure_type.flow`,
`mac.rule_kind.` -> `mac.concept.rule.`, `mac.axis_kind.` -> `mac.concept.axis_kind.`,
`mac.identity_kind.` -> `mac.concept.identity.`; a single measure column receives the concept's
`semantics.measure_type` / `unit` as its `measure:` block; `schema_version` is lifted to the
schema's generation. Only the `grounding:` block is re-rendered (its comments do not survive);
every other line of the file is left exactly as it was.

WHAT DOES NOT MOVE WITHOUT A PERSON. `attribute` was never a role: it was several judgements
filed in one slot (mac_vocabulary.yaml#concept.column.role) — pipeline bookkeeping, a label of
another column, a column that may never be an axis for a measured reason. None of those is a
rename, so this tool REFUSES to migrate an `attribute` column unless a decisions file names it:

    # migration_decisions.yaml — one entry per <Concept>.<column> a person must decide
    Customer.StartDT:    {role: housekeeping}
    Customer.Comment:    {exclude: true, because: free text; the concept does not serve it}   # a RATIFIED narrowing
    LineItem.l_orderkey: {role: key, identity: part}                                         # a decision beats the canonical inference
    Customer.ZipCode:    {role: dimension, rulings: {never_axis: "29 193 of 40 639 postcodes are held by exactly one customer", evidence: DQ-CUSTOMER-02}}
    Customer.CountryFull: {role: dimension, rulings: {label_of: Country, register: long}}

A key-role column that is not the canonical key is emitted `identity: reference` (the join
column) unless the decisions file says otherwise (`<Concept>.<column>: {identity: part}` for a
composite). `resolved_axis` as an identity kind is refused: it was retired and its replacement is a
judgement.

THE SERVED SET MUST NOT NARROW SILENTLY. The legacy `field_roles` was a whitelist of ROLES while the
concept went on serving every column its descriptor listed; the map form serves exactly what it
names. So every descriptor column the whitelist did not name needs a decided role too, or the
migration changes what the concept serves — measured: a display column (`email`) vanished from a
plan. `--propose-decisions FILE` writes a proposal for every such column and every `attribute`,
derived from the descriptor's relation-plane role and subrole (primary_key -> key canonical,
foreign_key -> key reference, subrole temporal -> period, everything else -> dimension) with a
`because:` line each — AI proposes; a person ratifies by passing the file back as --decisions.

Usage:  mac_migrate_concepts.py <bundle> [--decisions FILE] [--write]      (default: report only)
        mac_migrate_concepts.py <bundle> --propose-decisions OUT.yaml
        mac_migrate_concepts.py --self-test
Exit:   0 nothing left on the legacy shape · 1 something is (listed; with --write, what was refused)
        · 2 the bundle or the decisions could not be read
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
RENAMES = [
    (re.compile(r"mac\.MeasureType\.([A-Za-z]+)"), lambda m: "mac.concept.column.measure_type." + m.group(1).lower()),
    (re.compile(r"mac\.rule_kind\."), lambda m: "mac.concept.rule."),
    (re.compile(r"mac\.axis_kind\."), lambda m: "mac.concept.axis_kind."),
    (re.compile(r"mac\.identity_kind\."), lambda m: "mac.concept.identity."),
    (re.compile(r"mac\.aggregation_effect\."), lambda m: "mac.concept.aggregation_effect."),
]
GROUNDING_KEEP = ("kind", "schema", "grain", "note", "notes", "realized_by", "join_rule", "value_filter",
                  "grounds_column", "code_column", "discriminator", "tables", "primary_tables", "used_in",
                  "serves_from", "snapshot_rule", "family_resolution", "row_count")


def schema_generation() -> str:
    return str(json.loads((ROOT / "mac.schema.json").read_text(encoding="utf-8")).get("version") or "0.1.16")


class Refused(Exception):
    """A judgement this tool will not make."""


def _top_block(text: str, key: str) -> tuple[int, int] | None:
    """(start, end) character offsets of a top-level `key:` block, end exclusive."""
    m = re.search(rf"^{key}:[^\n]*\n", text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    n = re.search(r"^(?=[A-Za-z_])", rest, re.M)
    return m.start(), (m.end() + n.start()) if n else len(text)


def _dump(key: str, value, indent: int) -> str:
    body = yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=True, width=100, default_flow_style=False)
    return "\n".join((" " * indent + ln) if ln else ln for ln in body.rstrip("\n").split("\n")) + "\n"


def descriptor_columns(root: pathlib.Path | None, table: str | None) -> list[dict]:
    """The relation's descriptor columns, if the bundle carries one (datasets first, then sources)."""
    if root is None or not table:
        return []
    for sub in ("datasets", "sources", "tables"):
        for cand in (root / "data" / sub / f"{table}.yaml", root / sub / f"{table}.yaml"):
            if cand.is_file():
                try:
                    return list((yaml.safe_load(cand.read_text(encoding="utf-8")) or {}).get("columns") or [])
                except yaml.YAMLError:
                    return []
    return []


def propose(concept: str, col: dict, legacy_role: str | None, canonical: str | None) -> dict:
    """A proposed decision for one column, from the relation plane's own facts — never a ruling."""
    # NO `x-subrole`: the `x-` namespace is BANNED (2026-10-05); only the bare key is read.
    name, role, sub = str(col.get("name")), str(col.get("role") or ""), str(col.get("subrole") or "")
    if name == canonical or role == "primary_key":
        return {"role": "key", "identity": "canonical" if name == canonical else "reference",
                "because": f"descriptor role {role or 'n/a'}; {'the canonical key' if name == canonical else 'a key that is not the canonical one'}"}
    if role == "foreign_key":
        return {"role": "key", "identity": "reference", "because": "descriptor role foreign_key"}
    if sub == "temporal":
        return {"role": "period", "because": "descriptor subrole temporal — CONFIRM this is THE reporting date; a second one is a dimension"}
    if legacy_role == "attribute":
        return {"role": "dimension", "because": "was `attribute` (display-only) — CONFIRM: housekeeping? label_of another column (register)? never_axis with a DQ id?"}
    return {"role": "dimension", "because": f"descriptor role {role or 'n/a'}{(' / ' + sub) if sub else ''}"}


def _measure(m) -> dict:
    """A decision's measure block, with a short type (`flow`) spelled out to the vocabulary token."""
    m = dict(m or {})
    t = m.get("type")
    if isinstance(t, str) and "." not in t:
        m["type"] = f"mac.concept.column.measure_type.{t}"
    return m


def migrate_text(text: str, *, decisions: dict, generation: str, path: str = "<concept>",
                 root: pathlib.Path | None = None) -> tuple[str, list[str]]:
    """(new text, list of changes). Raises Refused for a judgement."""
    doc = yaml.safe_load(text) or {}
    changes: list[str] = []
    concept = (doc.get("concept") or {}).get("name") or path
    g = doc.get("grounding") or {}
    ident = (doc.get("concept") or {}).get("identity") or {}
    if str(ident.get("kind", "")).endswith("resolved_axis"):
        raise Refused(f"{concept}: identity.kind resolved_axis was retired 2026-09-28; its replacement is a judgement")
    out = text
    for rx, fn in RENAMES:
        out, n = rx.subn(fn, out)
        if n:
            changes.append(f"{n} retired token(s) renamed via {rx.pattern}")

    legacy = isinstance(g, dict) and "sources" not in g and ("table" in g or "field_roles" in g)
    if legacy:
        roles = dict(g.get("field_roles") or {})
        canonical = ident.get("canonical_key")
        sem = (doc.get("concept") or {}).get("semantics") or {}
        mtype = sem.get("measure_type")
        if isinstance(mtype, str):
            for rx, fn in RENAMES:
                mtype = rx.sub(fn, mtype)
        unit = sem.get("unit")
        measure_cols = [c for c, r in roles.items() if str(r).rsplit(".", 1)[-1] == "measure"]
        columns: dict = {}
        refused: list[str] = []
        for col, raw_role in roles.items():
            role = str(raw_role).rsplit(".", 1)[-1]
            dec = decisions.get(f"{concept}.{col}") or {}
            if dec.get("exclude"):
                changes.append(f"{col} excluded by decision")
                continue
            spec: dict = {}
            if role == "attribute":
                if not dec.get("role"):
                    refused.append(f"{concept}.{col}")
                    continue
                spec["role"] = dec["role"]
            elif role in ("key", "dimension", "measure", "period", "housekeeping"):
                spec["role"] = dec.get("role", role)
            else:
                raise Refused(f"{concept}.{col}: role {role!r} is not a role this tool knows")
            if dec.get("identity"):
                spec["identity"] = dec["identity"]          # a decision beats every inference
            elif col == canonical:
                spec["identity"] = "canonical"
            elif spec["role"] == "key":
                spec["identity"] = "reference"
            if spec["role"] == "measure":
                m = _measure(dec.get("measure"))
                if len(measure_cols) == 1:
                    if mtype and "type" not in m:
                        m["type"] = mtype
                    if unit and "unit" not in m:
                        m["unit"] = unit
                if m:
                    spec["measure"] = m
            if dec.get("rulings"):
                spec["rulings"] = dict(dec["rulings"])
            columns[col] = spec
        if canonical and canonical not in columns:
            columns = {canonical: {"role": "key", "identity": "canonical"}, **columns}
            changes.append(f"canonical key {canonical} was not in field_roles; declared")
        # every descriptor column the whitelist did not name: decided, or refused
        uncovered = []
        for dc in descriptor_columns(root, g.get("table")):
            name = str(dc.get("name"))
            if name in columns or name in roles:
                continue
            dec = decisions.get(f"{concept}.{name}")
            if dec and dec.get("exclude"):
                changes.append(f"{name} excluded by decision")
                continue
            if not dec or not dec.get("role"):
                uncovered.append(name)
                continue
            spec = {"role": dec["role"]}
            if dec.get("identity"):
                spec["identity"] = dec["identity"]
            elif dec["role"] == "key":
                spec["identity"] = "canonical" if name == canonical else "reference"
            if dec.get("measure"):
                spec["measure"] = _measure(dec["measure"])
            if dec.get("rulings"):
                spec["rulings"] = dict(dec["rulings"])
            columns[name] = spec
        if uncovered:
            refused.append(f"served-but-unnamed: {', '.join(uncovered)}")
        if refused:
            raise Refused(f"{concept}: {len(refused)} `attribute` column(s) need a decision (role, and any ruling): "
                          + ", ".join(refused))
        if len(measure_cols) > 1 and not unit:
            raise Refused(f"{concept}: {len(measure_cols)} measure columns and no semantics.unit — a composed measure states its unit")
        src: dict = {"relation": g.get("table")}
        if g.get("key_column"):
            src["key"] = [g["key_column"]]
        src["columns"] = columns
        new_g: dict = {}
        for k in GROUNDING_KEEP:
            if k in g:
                new_g[k] = g[k]
        new_g["sources"] = [src]
        # render: kind/schema first, then sources, then the rest in the order kept
        block = "grounding:\n"
        for k in ("kind", "schema"):
            if k in new_g:
                block += _dump(k, new_g.pop(k), 2)
        block += _dump("sources", new_g.pop("sources"), 2)
        for k, v in new_g.items():
            block += _dump(k, v, 2)
        span = _top_block(out, "grounding")
        assert span, "grounding block not found in text"
        out = out[:span[0]] + block + out[span[1]:]
        changes.append(f"grounding: {len(columns)} column(s) on the map form, key {src.get('key')}, relation {src['relation']}")
        if canonical:
            out2, n = re.subn(r"^(\s+)canonical_key:[^\n]*\n", "", out, count=1, flags=re.M)
            if n:
                out = out2
                changes.append(f"identity.canonical_key {canonical} moved onto the column")
    out2, n = re.subn(r"^(\s+schema_version:\s*)['\"]?[0-9.]+['\"]?", rf"\g<1>'{generation}'", out, count=1, flags=re.M)
    if n and out2 != out:
        out = out2
        changes.append(f"schema_version -> {generation}")
    return out, changes


def concept_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in (root / "ontology" / "concepts").rglob("*.yaml"))


def propose_decisions(root: pathlib.Path) -> dict:
    """Every column a person must decide on, with a proposal each: attribute columns and descriptor
    columns the whitelist never named. Keyed <Concept>.<column>; `because` is the proposal's basis."""
    out: dict = {}
    for p in concept_files(root):
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        g = doc.get("grounding") or {}
        if not isinstance(g, dict) or "sources" in g or not ("table" in g or "field_roles" in g):
            continue
        concept = (doc.get("concept") or {}).get("name") or p.stem
        canonical = ((doc.get("concept") or {}).get("identity") or {}).get("canonical_key")
        roles = {c: str(r).rsplit(".", 1)[-1] for c, r in (g.get("field_roles") or {}).items()}
        desc = {str(c.get("name")): c for c in descriptor_columns(root, g.get("table"))}
        for col, role in roles.items():
            if role == "attribute":
                out[f"{concept}.{col}"] = propose(concept, desc.get(col, {"name": col}), "attribute", canonical)
        for name, c in desc.items():
            if name not in roles:
                out[f"{concept}.{name}"] = propose(concept, c, None, canonical)
    return out


def run(root: pathlib.Path, decisions: dict, write: bool) -> int:
    gen = schema_generation()
    still, moved, refused = [], [], []
    for p in concept_files(root):
        text = p.read_text(encoding="utf-8")
        try:
            new, changes = migrate_text(text, decisions=decisions, generation=gen, path=str(p), root=root)
        except Refused as exc:
            refused.append(str(exc))
            continue
        if new != text:
            if write:
                p.write_text(new, encoding="utf-8")
                moved.append((p, changes))
            else:
                still.append((p, changes))
    rel = lambda p: p.relative_to(root).as_posix()  # noqa: E731
    for p, ch in moved:
        print(f"  migrated {rel(p)}: " + "; ".join(ch))
    for p, ch in still:
        print(f"  legacy   {rel(p)}: " + "; ".join(ch))
    for r in refused:
        print(f"  REFUSED  {r}")
    total = len(concept_files(root))
    if refused or still:
        print(f"FAIL: mac_migrate_concepts — {len(still)} concept(s) still on the legacy shape, {len(refused)} refused "
              f"(a judgement is owed: --decisions), {len(moved)} migrated, over {total}")
        return 1
    print(f"PASS: mac_migrate_concepts — {total} concept(s) on the column standard ({len(moved)} migrated this run)")
    return 0


def _self_test() -> int:
    import tempfile
    fails: list[str] = []

    def case(label, cond):
        if not cond:
            fails.append(label)

    legacy = """metadata:
  concept: Order
  source: SHOP
  version: '1.0'
  schema_version: '0.1.9'
  status: draft
  owner: t
  confidence: I
concept:
  name: Order
  label: Order
  class: measure
  identity:
    kind: fk_name
    canonical_key: order_id
  definition: an order
  semantics:
    measure_type: mac.MeasureType.Flow
    unit: USD
grounding:
  kind: sql_table
  table: orders
  schema: shop
  key_column: order_id
  # a comment inside grounding does not survive; everything outside does
  field_roles:
    order_id: shop.field_role.key
    customer_id: shop.field_role.key
    status: shop.field_role.dimension
    surname: shop.field_role.attribute
    gross_amount: shop.field_role.measure
  grain: one row per order
contract:
  rules:
    - id: order.x
      kind: mac.rule_kind.aggregation   # keep this comment
"""
    try:
        migrate_text(legacy, decisions={}, generation="0.1.16")
        case("an attribute column without a decision is REFUSED", False)
    except Refused as exc:
        case("the refusal names the column", "Order.surname" in str(exc))
    dec = {"Order.surname": {"role": "dimension", "rulings": {"label_of": "customer_id", "register": "common"}}}
    new, ch = migrate_text(legacy, decisions=dec, generation="0.1.16")
    d = yaml.safe_load(new)
    src = d["grounding"]["sources"][0]
    case("sources[] with the relation and key", src["relation"] == "orders" and src["key"] == ["order_id"])
    case("canonical key on the column", src["columns"]["order_id"] == {"role": "key", "identity": "canonical"})
    case("the other key is a reference", src["columns"]["customer_id"] == {"role": "key", "identity": "reference"})
    case("the measure carries type and unit from semantics", src["columns"]["gross_amount"]["measure"] == {"type": "mac.concept.column.measure_type.flow", "unit": "USD"})
    case("the decided attribute carries its ruling", src["columns"]["surname"]["rulings"]["label_of"] == "customer_id")
    case("canonical_key left the concept", "canonical_key" not in d["concept"]["identity"])
    case("no field_roles remain", "field_roles" not in d["grounding"])
    case("grain kept", d["grounding"]["grain"] == "one row per order")
    case("retired tokens renamed", d["contract"]["rules"][0]["kind"] == "mac.concept.rule.aggregation" and d["concept"]["semantics"]["measure_type"] == "mac.concept.column.measure_type.flow")
    case("a comment OUTSIDE the grounding block survives", "# keep this comment" in new)
    case("schema_version lifted", d["metadata"]["schema_version"] == "0.1.16")
    new2, ch2 = migrate_text(new, decisions=dec, generation="0.1.16")
    case("a second run changes nothing", new2 == new and not ch2)
    bad = legacy.replace("kind: fk_name", "kind: resolved_axis")
    try:
        migrate_text(bad, decisions=dec, generation="0.1.16")
        case("resolved_axis is refused", False)
    except Refused:
        pass
    with tempfile.TemporaryDirectory() as td:
        b = pathlib.Path(td); (b / "ontology" / "concepts").mkdir(parents=True); (b / "data" / "datasets").mkdir(parents=True)
        (b / "ontology" / "concepts" / "order.yaml").write_text(legacy, encoding="utf-8")
        (b / "data" / "datasets" / "orders.yaml").write_text(
            "table: {name: orders}\ncolumns:\n  - {name: order_id, role: primary_key}\n  - {name: customer_id, role: foreign_key}\n"
            "  - {name: status, role: value}\n  - {name: surname, role: value, subrole: attribute}\n  - {name: gross_amount, role: value}\n"
            "  - {name: placed_at, role: value, subrole: temporal}\n  - {name: email, role: value, subrole: attribute}\n", encoding="utf-8")
        case("a bundle with a legacy concept fails --check", run(b, {}, write=False) == 1)
        try:
            migrate_text(legacy, decisions=dec, generation="0.1.16", root=b)
            case("a descriptor column the whitelist never named is REFUSED (the served set must not narrow)", False)
        except Refused as exc:
            case("the refusal names the unnamed columns", "placed_at" in str(exc) and "email" in str(exc))
        prop = propose_decisions(b)
        case("proposals cover the attribute and the unnamed columns", set(prop) == {"Order.surname", "Order.placed_at", "Order.email"})
        case("a temporal column is proposed as period, an attribute as dimension", prop["Order.placed_at"]["role"] == "period" and prop["Order.surname"]["role"] == "dimension")
        full = {**dec, "Order.placed_at": {"role": "period"}, "Order.email": {"role": "dimension"}}
        case("with every decision and --write it migrates", run(b, full, write=True) == 0)
        case("and then --check passes", run(b, full, write=False) == 0)
        case("the decided unnamed columns are served", "placed_at" in yaml.safe_load((b / "ontology" / "concepts" / "order.yaml").read_text())["grounding"]["sources"][0]["columns"])
    n = 21
    if fails:
        print("FAIL: mac_migrate_concepts self-test — " + "; ".join(fails))
        return 1
    print(f"PASS: mac_migrate_concepts self-test — {n}/{n} case(s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?")
    ap.add_argument("--decisions", help="YAML: <Concept>.<column> -> {role, identity?, measure?, rulings?}")
    ap.add_argument("--propose-decisions", metavar="OUT", help="write a proposed decisions file for every column a person must decide")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.root:
        ap.print_help()
        return 2
    root = pathlib.Path(a.root).resolve()
    if not (root / "ontology" / "concepts").is_dir():
        print(f"could not run: no ontology/concepts under {root}")
        return 2
    if a.propose_decisions:
        prop = propose_decisions(root)
        pathlib.Path(a.propose_decisions).write_text(
            "# PROPOSED by mac_migrate_concepts.py — a person ratifies by editing and passing --decisions.\n"
            "# `because` is the proposal's basis, from the relation plane; it is not a ruling.\n"
            + yaml.safe_dump(prop, sort_keys=True, allow_unicode=True, width=120), encoding="utf-8")
        print(f"proposed {len(prop)} decision(s) -> {a.propose_decisions}")
        return 0
    decisions = {}
    if a.decisions:
        try:
            decisions = yaml.safe_load(pathlib.Path(a.decisions).read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            print(f"could not run: decisions — {exc}")
            return 2
    return run(root, decisions, a.write)


if __name__ == "__main__":
    sys.exit(main())
