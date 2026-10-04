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
import _neighbours  # noqa: E402  — ONE home for the sibling runtime's location
import _plugin  # noqa: E402  - same directory; the seam that owns the connection

GENERATOR = "mac_descriptors.py/1"

#: The literal fallback, for an environment without the runtime importable. A FALLBACK, not a second
#: source of truth — `meaning_plane_tables` prefers the runtime's own definition.
_MEANING_PLANE_FALLBACK = frozenset({
    "meta_concept", "meta_field_role", "meta_contract_rule", "meta_rule_binding",
    "meta_edge", "meta_constraint", "meta_dataset",
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
        _neighbours.ensure_runtime_on_path()
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
    # THE TWO PLANES ARE TWO DELIVERIES, and this tool wrote both in one call. The operator ruled the
    # split on 2026-09-28: "split data plane delivery in two parts: data sources and datasets". They
    # are not two halves of one job — a SOURCE descriptor describes what was landed and its roles are
    # neutral until a measurement rules them, while a DATASET descriptor describes what a transform
    # LEFT and its roles are the promotion's contract. Delivering them together means neither can be
    # signed off on its own, and a checklist that covers both at once cannot say which half is short.
    ap.add_argument("--plane", choices=("sources", "datasets", "both"), default="both",
                    help="which plane to write (default: both). `sources` = the landing schema -> "
                         "data/sources/; `datasets` = the served schema -> data/datasets/")
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
    wanted = {"sources": (a.raw_schema,), "datasets": (served,), "both": (served, a.raw_schema)}[a.plane]
    for schema in wanted:
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
    # THE TWO ENRICHMENTS, RE-DERIVED so a re-run rebuilds them instead of wiping them. Foreign keys come
    # from the MEASUREMENT (data/references*/) and never from a name coincidence; register pointers come
    # from the registers already cut (data/lookups/). Both are absent on a first run, which is honest —
    # neither can be known before the stage that measures it — and the import pipeline re-runs this after.
    fk_served, fk_raw = measured_fks(root, True), measured_fks(root, False)
    regs = cut_registers(root)
    dist = profiled_distinct(root)
    drift, wrote = [], 0
    for (schema, table), m in sorted(measured.items()):
        is_served = schema == served
        body = _render(m, schema, table, is_served, singles, observed,
                       fk_served if is_served else fk_raw, regs, dist)
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


def measured_fks(root: pathlib.Path, served: bool) -> dict:
    """`{(relation, column): "parent.column"}` — FOREIGN KEYS AS MEASURED, not as guessed from a name.

    WHY THIS REPLACES THE NAME MATCH, in the operator's words 2026-09-28: "foreign keys between tables
    can have fully DIFFERENT column names. and since you don't have original data model is reverse
    engineering through measurement and profiling the only safe way to establish relationships between
    tables."

    That is not a preference, it is structural. The old rule declared a foreign key only where the child
    column's NAME equalled the parent's key column name, and a name coincidence is neither necessary nor
    sufficient. MEASURED ON contoso4: 28 real references per plane, 6 declared. Of the 22 missed, 7 were
    textbook many:one references into a single-column identity — including EVERY join to the date
    dimension (`sales.OrderDate -> date.Date`, `sales.DeliveryDate -> date.Date`, `orders.DT ->
    date.Date`), because the child column is named for what the date MEANS and the parent key is just
    `Date`. The single most important join in the warehouse for any time question, undeclared, because two
    strings differed.

    THE TEST IS THE MEASUREMENT'S OWN VERDICT: `parent_key_role: identity` (the parent side is a whole
    single-column key, not one part of a composite) and cardinality `many:one`. A reference into a
    key_part is a shared value domain, not an identifying join — 15 of contoso4's 28 are those, all
    many:many, and they stay out.

    IT IS A SECOND PASS AND THAT IS HONEST. A first run has no references artifact yet and declares no
    foreign keys; the import pipeline measures references and re-runs this, which REBUILDS them. Rebuild
    rather than enrich is the whole point — see the register note below for what enrichment costs.
    """
    import yaml as _yaml
    sub = "references_served" if served else "references"
    out: dict = {}
    d = root / "data" / sub
    if not d.is_dir():
        return out
    import glob as _g
    for f in sorted(_g.glob(str(d / "*.yaml"))):
        try:
            doc = _yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8")) or {}
        except _yaml.YAMLError:
            continue
        for r in (doc.get("references") or []):
            if not isinstance(r, dict) or r.get("verdict") != "real":
                continue
            if str(r.get("parent_key_role")) != "identity":
                continue
            card = r.get("cardinality") or {}
            if (card.get("child"), card.get("parent")) != ("many", "one"):
                continue
            fr, to = r.get("from") or {}, r.get("to") or {}
            if fr.get("relation") and fr.get("column") and to.get("relation") and to.get("column"):
                # THE TARGET PLUS THE CROW'S FEET, and nothing else. Cardinality and participation are
                # what makes the drawing an ER diagram rather than boxes and lines, and they are the
                # half a key cannot supply. The EVIDENCE stays in data/references*/ where it was
                # measured — see mac_project.column_reference for why copying it here is two copies.
                card = r.get("cardinality") if isinstance(r.get("cardinality"), dict) else {}
                part = r.get("participation") if isinstance(r.get("participation"), dict) else {}
                out[(str(fr["relation"]), str(fr["column"]))] = {
                    "to": f"{to['relation']}.{to['column']}",
                    "cardinality": {"child": card.get("child"), "parent": card.get("parent")},
                    "participation": {"child": part.get("child"), "parent": part.get("parent")},
                }
    return out


def profiled_distinct(root: pathlib.Path) -> dict:
    """`{(stem, column): distinct}` — the measured cardinality, from the PROFILE, its one home.

    WHY THIS PRODUCER NEEDS IT. `mac_lookups` writes `distinct: <n>` onto a column as the REPLACEMENT
    for the member list it just moved into a register — the count survives, the list does not. That made
    this producer unable to run last: regenerating a descriptor dropped the count, so the pipeline could
    only ever run descriptors FIRST, which is exactly why a measured foreign key never reached the
    declaration (references are measured after descriptors, and nothing re-ran them).

    Re-deriving it here from `data/profiles/` closes the last gap: roles and keys come from the
    warehouse, foreign keys from `data/references*/`, register pointers from `data/lookups/`, and the
    cardinality from the profile. Every fact this file states is now re-derivable from its own home, so
    the producer is IDEMPOTENT and may run as the LAST stage of a part — which is what makes the part
    repeatable rather than order-dependent.

    ONLY FOR A COLUMN THAT CARRIES A REGISTER, deliberately: that is the set `mac_lookups` annotated,
    and emitting a count for every column would change the delivered shape of every descriptor in the
    estate while this change is about not LOSING one.
    """
    import yaml as _yaml
    out: dict = {}
    d = root / "data" / "profiles"
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.yaml")):
        try:
            doc = _yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except _yaml.YAMLError:
            continue
        stem = str(doc.get("of") or f.stem)
        for c in (doc.get("columns") or []):
            if isinstance(c, dict) and c.get("name") is not None and c.get("distinct") is not None:
                out[(stem, str(c["name"]))] = int(c["distinct"])
    return out


def cut_registers(root: pathlib.Path) -> dict:
    """`{(relation, column): "data/lookups/<file>"}` for every register already cut from a column.

    WHY THIS IS HERE AND NOT LEFT TO THE ENRICHING STAGE. `mac_lookups` used to add the `register:`
    pointer AFTER this producer ran, and a re-run of this producer WIPED ALL 23 OF THEM — caught by
    REGISTER-ORPHAN reporting "23 of 23 registers are pointed at by no descriptor column". An enrichment
    a regeneration destroys is not a pipeline, it is an ordering everyone has to remember. Deriving it
    here instead makes this producer IDEMPOTENT: run it twice and the second run rebuilds the same file.

    THE COLUMN COMES FROM THE FILE'S FIRST HEADER FIELD, not from its name. That is not a nicety: the
    register loader itself infers a register's source column from exactly that field, so reading it any
    other way here would attach the pointer by a rule the runtime does not use. It also removes a
    dependency on the filename convention `<source>_<column>.lookup.csv`, which cannot be parsed
    unambiguously when a source label contains an underscore.

    THE RELATION COMES FROM `source_view` AND THE KEY IS THE PAIR. Keying on the column alone was wrong
    and measurably so: it attached the 67-member register cut from `v_contoso4_store.State` to
    `v_contoso4_customer.State`, a column with 565 distinct values, because the two columns share a name.
    That is the SAME name-coincidence defect `measured_fks` exists to remove, committed one field over —
    a register is a value set cut from ONE relation's column, and every row of the file records which.
    A register is claimed only where it was cut: not on a same-named column of another relation, and not
    on the raw table behind the view, whose row set is a superset the cut never looked at.
    """
    out: dict = {}
    d = root / "data" / "lookups"
    if not d.is_dir():
        return out
    import csv as _csv

    # THE DECLARATION BEATS THE HEURISTIC, where there is one. Everything above describes inferring
    # the attach point from `(source_view, header[0])`, which was the only way to know it while a
    # register WAS one column's values. The operator ruled otherwise on 2026-09-29 — one register
    # per value set, attached to many columns — and `mac_lookups` now writes that attach list into
    # `<stem>.lookup.yaml`. Under the old inference a shared register would be claimed by its OWNER
    # alone and the other seven columns would silently lose their `register:` pointer on the next
    # regeneration, which is the same class of loss the paragraph above was written about.
    #
    # The CSV path below still runs for every register with no descriptor beside it, so a bundle cut
    # before this change keeps working exactly as it did.
    claimed: set = set()
    try:
        import yaml as _yaml
        for y in sorted(d.glob("*.lookup.yaml")):
            doc = _yaml.safe_load(y.read_text(encoding="utf-8")) or {}
            csv_rel = ((doc.get("register") or {}).get("csv")
                       or f"data/lookups/{y.stem.replace('.lookup', '')}.lookup.csv")
            # THE DESCRIPTOR POINTS AT THE REGISTER'S DECLARATION, NOT AT ITS DATA FILE.
            # Operator ruling, 2026-10-03. Every binding in the estate named the .csv, so the 17
            # `.lookup.yaml` descriptors had NO inbound declaration anywhere — `eg_v_orphan`
            # reported 17 of 17 — while seven tools including the runtime resolver read them. The
            # register declaration is the authority on the value set (`attached` is, in the
            # runtime's own words, "the one home of which columns carry this set"); the .csv is
            # what it describes. A declaration depending on a data file inverts that.
            #
            # `csv_rel` is still read above and still fills `claimed` below: that set dedupes the
            # raw CSV scan, which keys on the file name.
            yaml_rel = f"data/lookups/{y.name}"
            for att in doc.get("attached") or []:
                rel, col = (att or {}).get("relation"), (att or {}).get("column")
                if rel and col:
                    out[(str(rel), str(col))] = yaml_rel
            claimed.add(pathlib.Path(csv_rel).name)
    except Exception as exc:  # noqa: BLE001 - an unreadable descriptor falls back to the CSV scan
        print(f"  register descriptors unreadable, falling back to source_view: {exc}")

    for f in sorted(d.glob("*.lookup.csv")):
        if f.name in claimed:
            continue
        try:
            with f.open(encoding="utf-8", newline="") as fh:
                rows = list(_csv.reader(fh))
        except (OSError, UnicodeDecodeError) as exc:
            print(f"  register unreadable, skipped: {f.name}: {exc}")
            continue
        if not rows:
            continue
        header = [str(h).strip() for h in rows[0]]
        col = header[0] if header else ""
        if not col or "source_view" not in header:
            continue
        i = header.index("source_view")
        for r in rows[1:]:
            if len(r) > i and str(r[i]).strip():
                out[(str(r[i]).strip(), col)] = f"data/lookups/{f.name}"
    return out


def _render(m: dict, schema: str, table: str, served: bool, singles: dict, observed: str,
            fks_measured: dict | None = None, registers: dict | None = None,
            distincts: dict | None = None) -> str:
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
    # THE NAME MATCH IS GONE. What stood here built `{parent_key_column_name: parent_table}` and declared
    # a foreign key wherever a child column happened to share that name — see `measured_fks` for why that
    # is structurally wrong and what it cost. `singles` is still read, but only to keep the same-plane
    # preference for a MEASURED reference; the measurement decides whether there is a reference at all.
    fks = dict(fks_measured or {})
    regs = dict(registers or {})
    dists = dict(distincts or {})
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
        ref = fks.get((table, col))
        if col == m["single_key"]:
            role = "primary_key"
        elif col in ckey:
            role, pos = "primary_key", ckey.index(col) + 1
        elif ref:
            role = "foreign_key"
        else:
            role = "value"
        lines += [f"- name: {col}", f"  type: {_simple(typ)}", f"  role: {role}"]
        if pos is not None:
            lines.append(f"  key_position: {pos}")
        # A COLUMN CAN BE A KEY *AND* POINT SOMEWHERE, and `references` is a sibling of `role` rather than
        # a property of it — so no grammar change was needed to say both. `sales.OrderKey` is PK1 of its
        # own relation and a measured many:one reference to `orders.OrderKey`; `role` says what it IS
        # here, `references` says what it POINTS AT. Writing the reference only for `role: foreign_key`
        # was the reason that join went undeclared.
        if ref:
            lines.append("  references:")
            lines.append(f"    to: {ref['to']}")
            _c, _p = ref.get("cardinality") or {}, ref.get("participation") or {}
            if _c.get("child") and _c.get("parent"):
                lines.append(f"    cardinality: {{child: {_c['child']}, parent: {_c['parent']}}}")
            if _p.get("child") and _p.get("parent"):
                lines.append(f"    participation: {{child: {_p['child']}, parent: {_p['parent']}}}")
        if (table, col) in regs:
            if (table, col) in dists:
                lines.append(f"  distinct: {dists[(table, col)]}")
            lines.append(f"  register: {regs[(table, col)]}")
        # NOT EVERYTHING IS A REGISTER (operator, 2026-09-29): "one huge table where the search
        # criteria is text cannot be converted into lookup. it should just be declared later to be
        # searchebal with like."
        #
        # This says so, on the column, where a reader of the descriptor will see it. Until now an
        # open-text column carried NOTHING to distinguish it from a column nobody had got round to
        # profiling: contoso5 held 16 of them — `dim_customer.customer_name` at 99 200 distinct of
        # 104 990 rows, `customer.StreetAddress` at 95 854, `product.ProductName` at 2 517 of
        # 2 517 — every one of them silent.
        #
        # THE RULE IS NOT distinct/rows ALONE. That hypothesis is killed by the most canonical
        # register in the estate: `dim_currency.currency_code` is 5 values over 5 rows, ratio 1.0,
        # because a dimension table IS its own register. It is only consulted HERE, below the
        # register branch, where the column already has no register — so the dimension-key case
        # cannot reach it.
        # ONE HOME FOR THE RULE. This branch first carried its own copy — `distinct > 100 and
        # distinct/rows > 0.05` — and it disagreed with the planner within the hour: `Occupation`
        # (2 571 distinct over 104 990 rows) and `Company` (1 031) have a LOW ratio and are still
        # far past the point a person names them, so the plan called them searchable and the
        # descriptor called them nothing. Two homes for one rule is the defect this estate keeps
        # paying for, so the rule is imported from where it is tested rather than restated here.
        elif (_simple(typ) == "string" and not ref
              and (table, col) in dists and m["rows"]
              and _searchable(dists[(table, col)], m["rows"])):
            lines.append(f"  distinct: {dists[(table, col)]}")
            lines.append("  searchable: like")
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
def _searchable(distinct: int, rows: int) -> bool:
    """Is this column open TEXT rather than a value set? The planner's rule, not a copy of it.

    `mac_register_plan.classify` is where the rule is written and where its mutants are held — the
    plain distinct/rows hypothesis is killed there by `dim_currency.currency_code`, 5 values over 5
    rows. `referenced=False` is correct at this call site and not a simplification: this branch runs
    only where the column has NO register, and a dimension key other relations point at would have
    one.
    """
    try:
        from mac_register_plan import classify
    except Exception:  # noqa: BLE001 - no planner on the path: declare nothing rather than guess
        return False
    return classify(int(distinct), int(rows), False)[0] == "searchable"


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
