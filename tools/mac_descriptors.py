#!/usr/bin/env python3
"""mac_descriptors.py — write a bundle's data-plane descriptors BY MEASURING THE WAREHOUSE.

D1 + D2 of DELIVERABLES-2026-09-26_first-run-state.md, produced by MEASUREMENT rather than by a
model. `harvest --mode data` authors the same two planes through Bedrock+Athena and is BILLED; the
columns, their types, the row counts and which columns identify a row are not opinions, so nothing
needs to be asked of a model to know them.

WHY IT IS A FRAMEWORK TOOL AND NOT A BUNDLE SCRIPT. It was written inside one bundle first, which is
exactly the mistake this estate keeps paying for: the next bundle needs it, copies it, and the two
drift. A descriptor's shape is the framework's (`mac.schema.json`), so its producer is too.

WHAT IT MEASURES, per relation, and nothing else:
  * the columns and their types, from information_schema, in ordinal order
  * the row count
  * `role: primary_key` where ONE column is unique and non-null over every row
  * `role: primary_key` + `key_position: n` where a declared key TUPLE is unique and no single member is
  * `role: foreign_key` where the column is the measured primary key of another relation in scope
  * `role: value` otherwise — the neutral physical role, which is not a ruling about meaning

WHAT IT DOES NOT DO. It states no default reading, no grain ruling, no "what one store is". Those are
ONTOLOGY decisions and they live in ontology/concepts/, where a person argues for them. A descriptor
that decided them would put the argument in the one file nobody reviews.

THE KEY IS MEASURED, NOT GUESSED — and that matters downstream: `mac_references.py` READS the
declared key and will not re-derive one, so a relation whose descriptor marks no key is not a parent
endpoint, and the ER model comes back with 0 entities. Measured 2026-09-26: that is exactly how an
empty ER diagram happens.

    python3 mac_descriptors.py <bundle-root> [--schema S] [--raw-schema S] [--check]
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _plugin  # noqa: E402  - same directory; the seam that owns the connection

GENERATOR = "mac_descriptors.py/1"
MAC_RUNTIME_SRC = "/Users/<operator>/dev/mac-platform/packages/mac-runtime/src"

#: The literal fallback, for an environment without the runtime importable. A FALLBACK, not a second
#: source of truth — `meaning_plane_tables` prefers the runtime's own definition.
_MEANING_PLANE_FALLBACK = frozenset({
    "meta_concept", "meta_field_role", "meta_contract_rule", "meta_rule_binding",
    "meta_edge", "meta_open_question", "meta_constraint", "meta_dataset",
})


def meaning_plane_tables() -> frozenset[str]:
    """THE FRAMEWORK'S OWN MEANING PLANE — the relations an ontology PROJECTS ITSELF into, which a
    bundle must never import as data.

    THE DEFECT THIS PREVENTS, caught by the operator 2026-09-26: "you meta classes are populated from
    WHICH ontology?!?!?! this cannot be." A bundle bound to a warehouse that already carried another
    ontology's meaning plane imported all eight of those relations as if they were business data — 32
    artifacts across descriptors, profiles, references and SAMPLES, the last of which held rows like
    `('AgeBand','enumeration')`: another bundle's CONCEPT NAMES presented as this one's data.
    `meta_concept` was measured at 21 rows, `meta_field_role` at 137.
    And left in, the billed concept stage would have seen `meta_concept` in the relation inventory
    and could have authored an ontology ABOUT an ontology.

    ONE HOME, DERIVED. The names come from `mac_runtime.meaning_plane._META_DEFS`, which is what
    EMITS them — so a ninth relation is excluded the day it is added, with nothing to remember.
    """
    try:
        if MAC_RUNTIME_SRC not in sys.path:
            sys.path.insert(0, MAC_RUNTIME_SRC)
        from mac_runtime.meaning_plane import _META_DEFS
        return frozenset(_META_DEFS)
    except Exception:  # noqa: BLE001 - no runtime on the path is not a reason to import the plane
        return _MEANING_PLANE_FALLBACK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--schema", help="the SERVED schema (default: connection.yaml#view_schema)")
    ap.add_argument("--raw-schema", default="main", help="the landing schema (default: main)")
    ap.add_argument("--check", action="store_true", help="report drift; write nothing")
    a = ap.parse_args(argv)

    root = pathlib.Path(a.root).resolve()
    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: {exc}")
        return 2
    try:
        athena = _plugin.required(str(root), "Athena")
    except Exception as exc:  # noqa: BLE001 - could-not-run is the honest answer, never a finding
        print(f"COULD NOT RUN: {exc}")
        return 2

    served = a.schema or _view_schema(root, yaml)
    con = athena(root=str(root))
    observed = datetime.now(UTC).date().isoformat()

    # ---- measure EVERY relation once, so the foreign-key pass can see the others -------------
    plane = meaning_plane_tables()
    measured: dict[tuple[str, str], dict] = {}
    excluded: list[str] = []
    for schema in (served, a.raw_schema):
        if not schema:
            continue
        for table in _tables(con, schema):
            # THE MEANING PLANE IS NEVER THIS BUNDLE'S DATA. See `meaning_plane_tables`.
            if table in plane:
                excluded.append(table)
                continue
            m = _measure(con, schema, table)
            if m:
                measured[(schema, table)] = m
    if excluded:
        print(f"  EXCLUDED {len(excluded)} meaning-plane relation(s) — an ontology's own "
              f"declarations projected into this warehouse, not this bundle's data:")
        print(f"    {', '.join(sorted(set(excluded)))}")
    if not measured:
        print(f"NOTHING TO MEASURE: no relation in {served!r} or {a.raw_schema!r}")
        return 1

    singles = {k: m["single_key"] for k, m in measured.items() if m.get("single_key")}
    drift, wrote = [], 0
    for (schema, table), m in sorted(measured.items()):
        is_served = schema == served
        body = _render(m, schema, table, is_served, singles, observed)
        out = root / "data" / ("datasets" if is_served else "sources") / f"{table}.yaml"
        if a.check:
            now = out.read_text(encoding="utf-8") if out.is_file() else ""
            if _without_date(now) != _without_date(body):
                drift.append(str(out.relative_to(root)))
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(body, encoding="utf-8")
            wrote += 1
            key = m["single_key"] or ", ".join(m["composite_key"]) or "NO KEY MEASURED"
            print(f"  {out.relative_to(root)}  {m['rows']:,} rows · "
                  f"{len(m['columns'])} columns · key: {key}")
    con.close()

    keyless = [t for (s, t), m in measured.items()
               if not m.get("single_key") and not m.get("composite_key")]
    if a.check:
        if drift:
            print(f"DRIFT — {len(drift)} descriptor(s) no longer match the warehouse:")
            for d in drift:
                print(f"  {d}")
            return 1
        print(f"OK — {len(measured)} descriptors match the warehouse.")
        return 0
    if keyless:
        print(f"\n  {len(keyless)} relation(s) carry NO measured key: {', '.join(sorted(keyless))}")
        print("  mac_references.py READS the key and will not derive one, so these are not parent "
              "endpoints and the ER model will not draw them.")
    print(f"\nwrote {wrote} descriptors, measured {observed}")
    return 0


def _view_schema(root: pathlib.Path, yaml) -> str:
    conn = root / "connection.yaml"
    if not conn.is_file():
        return "main"
    doc = yaml.safe_load(conn.read_text(encoding="utf-8")) or {}
    return str(doc.get("view_schema") or "main")


def _tables(con, schema: str) -> list[str]:
    rows, _ = con.query(
        "select table_name as d0 from information_schema.tables "
        f"where table_schema = '{schema}' order by 1"
    )
    return [r["d0"] for r in rows]


def _measure(con, schema: str, table: str) -> dict | None:
    rows, _ = con.query(
        "select column_name as d0, data_type as d1 from information_schema.columns "
        f"where table_schema = '{schema}' and table_name = '{table}' order by ordinal_position"
    )
    if not rows:
        return None
    cols = [(r["d0"], r["d1"]) for r in rows]
    n, _ = con.query(f'select count(*) as d0 from "{schema}"."{table}"')
    total = int(n[0]["d0"]) if n else 0

    single = next(
        (c for c, _ in cols if _is_unique(con, schema, table, [c], total)), None
    )
    composite: list[str] = []
    if not single:
        # THE SMALLEST TUPLE THAT IS UNIQUE, tried left to right over the first few columns. A key
        # is measured here because `mac_references.py` will not derive one, and a relation with no
        # declared key is invisible to the ER model.
        head = [c for c, _ in cols[:4]]
        for size in (2, 3, 4):
            for i in range(len(head) - size + 1):
                cand = head[i:i + size]
                if _is_unique(con, schema, table, cand, total):
                    composite = cand
                    break
            if composite:
                break
    return {"columns": cols, "rows": total, "single_key": single, "composite_key": composite}


def _is_unique(con, schema: str, table: str, cols: list[str], rows: int) -> bool:
    """Unique AND non-null over every row — a key that is null somewhere identifies nothing."""
    if not rows:
        return False
    quoted = ", ".join(f'"{c}"' for c in cols)
    nulls = " or ".join(f'"{c}" is null' for c in cols)
    try:
        nn, _ = con.query(f'select count(*) as d0 from "{schema}"."{table}" where {nulls}')
        if int(nn[0]["d0"]):
            return False
        d, _ = con.query(
            f'select count(*) as d0 from (select {quoted} from "{schema}"."{table}" '
            f"group by {quoted})"
        )
    except Exception:  # noqa: BLE001 - a column that cannot group is not a key
        return False
    return int(d[0]["d0"]) == rows


def _render(m: dict, schema: str, table: str, served: bool, singles: dict, observed: str) -> str:
    # A REFERENCE STAYS IN ITS OWN PLANE, and this comprehension used to pick by luck.
    #
    # `singles` is keyed by (schema, table) and the comprehension re-keys it by COLUMN, so when the same
    # single-column key exists on both a landing and the served view over it — which a 1:1 passthrough
    # guarantees — whichever iterated LAST won. It won `main.customer`, so every SERVED descriptor's
    # foreign key pointed at a RAW landing.
    #
    # THE COST WAS THE WHOLE ONTOLOGY GRAPH. The edge lift resolves a FK target through
    # `concept_of[bare(to_table)]`, and the concepts ground on the served relations, so
    # `concept_of["customer"]` missed and the lift wrote 0 physical edges over 19 concepts. The ER
    # diagram looked right the entire time because it is built from the DATA plane's measured keys —
    # 10 primary keys, 14 composite parts, 12 foreign keys, all present and all correct — which is why
    # the operator could see PKs and FKs on a diagram while the ontology had no edges at all.
    #
    # Same-plane targets win; a cross-plane one is kept only where the plane has no candidate of its own,
    # because a reference that resolves nowhere is worse than one that crosses a boundary.
    same = {c: t for (s_, t), c in singles.items() if t != table and s_ == schema}
    other = {c: t for (s_, t), c in singles.items() if t != table and s_ != schema}
    fks = {**other, **same}
    lines = [
        f"# GENERATED by {GENERATOR} from the warehouse — do not edit; re-run the generator.",
        "#",
        "# A descriptor states what the relation CONTAINS. What it MEANS is in ontology/concepts/,",
        "# where a person argues for it: no default reading, no grain ruling, no 'what one X is'.",
        "",
        "metadata:",
        f"  table: {table}",
        "  schema_version: 0.1.15",
        # STATUS IS A LIFECYCLE FACT ABOUT THE FILE, NOT A GRADE OF THE MEASUREMENT. Every generated
        # descriptor used to be born `draft`, which no reader consumed and which is not true of a
        # measurement: it either happened or it did not. The one real consumer of this field is
        # check_datasets_are_grounded, which skips a descriptor marked `retired` because the relation it
        # describes is gone. v0.1.15 closes `metadata` and constrains the field to [measured|retired].
        "  status: measured",
        f"  kind: {'served_dataset' if served else 'raw_source'}",
    ]
    if not served:
        lines.append("  external: true")
    lines += [
        f"  observed: '{observed}'",
        f"  generated_by: {GENERATOR}",
        "",
        "table:",
        f"  name: {table}",
        f"  schema: {schema}",
        f"  type: {'view' if served else 'table'}",
        f"  rows_measured: {m['rows']}",
        "",
        "columns:",
    ]
    # ONE ROLE FOR A KEY COLUMN, AND THE ORDER AS A NUMBER. `composite_key_part` was retired by
    # operator ruling 2026-09-27: it carried membership and no order, so a consumer asking "what is this
    # relation's key" had to remember two terms — and two did not, leaving the fact table with NO key in
    # the graph and SHACL projections. `key_position` is the order, on the column, comparable.
    ckey = list(m["composite_key"] or [])
    for col, typ in m["columns"]:
        pos = None
        if col == m["single_key"]:
            role = "primary_key"
        elif col in ckey:
            role, pos = "primary_key", ckey.index(col) + 1
        elif col in fks:
            role = "foreign_key"
        else:
            role = "value"
        lines += [f"- name: {col}", f"  type: {_simple(typ)}", f"  role: {role}"]
        if pos is not None:
            lines.append(f"  key_position: {pos}")
        if role == "foreign_key":
            # QUALIFIED: `relation.column`, which the schema has required since v0.1.15 ("The
            # parent this foreign_key column points at, as `relation.column`") and which this
            # producer did not write — it emitted the relation alone, so "what column do I join
            # to" was unanswerable from the declaration and every consumer had to assume the
            # name matched. The PARENT KEY COLUMN is `col` itself: `singles` is keyed by
            # (schema, table) -> that relation's single key column, and this branch fires
            # because the referencing column carries the SAME NAME. So the join is stated, not
            # inferred. Operator, 2026-09-28: "reference to tables and columns where FKs are
            # pointing to".
            lines.append(f"  references: {fks[col]}.{col}")
        # NO `confidence: I` — a column read out of information_schema was not INFERRED, and the key
        # was read by nothing. It sat on 224 column entries across two planes in one bundle. Removed
        # from the core in v0.1.15 on CONFORMANCE.md §2's own test: "a key nothing consumes is a note,
        # and a note belongs in prose." The operator put it plainly: nothing in the data plane needs a
        # status like inferred — it is 1:1 from the source and it is pretty clear.
    return "\n".join(lines) + "\n"


def _simple(sql_type: str) -> str:
    t = str(sql_type).upper()
    for frag, out in (
        ("CHAR", "string"), ("TEXT", "string"), ("INT", "integer"), ("DECIMAL", "decimal"),
        ("NUMERIC", "decimal"), ("DOUBLE", "double"), ("REAL", "double"),
        ("TIMESTAMP", "timestamp"), ("DATE", "date"), ("BOOL", "boolean"),
    ):
        if frag in t:
            return out
    return str(sql_type).lower()


#: Keys LATER STAGES add to a column. `mac_profile` captures a value domain; `mac_lookups` replaces it
#: with `distinct:` + `register:` when the members move to their register. None of them is this
#: generator's output, and comparing against them made `--check` report drift on all 14 descriptors of
#: a bundle nothing had changed — a check that always fails is a check nobody can use (DNA law 12).
_ENRICHED_BY_LATER_STAGES = ("values", "distinct", "register", "domain")


def _comparable(text: str) -> object:
    """The descriptor's SHAPE, structurally, with the date and every downstream enrichment removed.

    STRUCTURAL AND NOT TEXTUAL, because a value domain is a LIST and a text filter cannot drop a
    list's items without knowing where the list ends — a half-stripped domain then reads as a
    difference. Parsing makes "what did this generator claim" answerable exactly.
    """
    import yaml as _y
    try:
        doc = _y.safe_load(text) or {}
    except Exception:  # noqa: BLE001 - an unparseable file IS a difference
        return text
    if isinstance(doc, dict):
        (doc.get("metadata") or {}).pop("observed", None)
        for c in doc.get("columns") or []:
            for k in _ENRICHED_BY_LATER_STAGES:
                c.pop(k, None)
    return doc


def _without_date(text: str) -> object:
    """Kept as the name the call sites use; the comparison is structural — see `_comparable`."""
    return _comparable(text)


if __name__ == "__main__":
    sys.exit(main())
