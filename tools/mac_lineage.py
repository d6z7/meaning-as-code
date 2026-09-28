#!/usr/bin/env python3
"""mac_lineage.py — MEASURE lineage from the WAREHOUSE'S OWN view definitions.

D15 of DELIVERABLES-2026-09-26_first-run-state.md, and it is its own deliverable rather than a member
of "all diagrams": a diagram is a RENDERING, lineage is a measured claim about where a column came
from, and it is the thing an operator follows when a number is wrong.

WHY THE EXISTING PROJECTORS COULD NOT DO IT. Both read the BUNDLE:
  * `project` writes `objects.json#lineage_graph` and refuses a bundle with no ontology plane — so
    on a first run, before any concept exists, there is no lineage at all.
  * `lineage_project.py` reads `data/transforms/*.sql`, and a bundle that BINDS to an existing
    warehouse authors no transforms. Measured 2026-09-26 on such a bundle: "0 flows, kinds=[]".

But the warehouse knows. `information_schema.views.view_definition` carries the SQL that produced
each served relation — six of six on the bundle this was built against — so the dependency is
MEASURABLE from the engine and needs neither a transform file nor a concept.

WHAT IT MEASURES, and nothing more:
  * for each served VIEW, the relations its own definition references  -> the edges
  * for each such reference, whether that relation is another view (an intermediate) or a base
    table (a landing)                                                  -> the node kinds
  * for each column of the view, its origin — in THREE outcomes, not two:

        plain    `d.DateKey AS DateKey`           source stated, no transformation
        TRACED   `CAST(d.Date AS DATE) AS Date`   exactly ONE column inside the expression, so the
                                                  source is known AND a transform was applied
        derived  a CASE over two columns          several inputs or none; the source stays NULL

WHAT IT REFUSES TO GUESS is the last row: a MULTI-input expression is never attributed to the first
identifier in it, because that lineage gets followed and trusted. What it refuses to THROW AWAY is
the middle row — a first version collapsed it into "derived, source null" and lost the traceable
origin of 10 of 72 columns on one bundle, every date among them. "Transformed" and "untraceable" are
different answers, and an operator chasing a wrong number needs to tell them apart.

    python3 mac_lineage.py <bundle-root> [--check]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
_REPO = str(pathlib.Path(__file__).resolve().parent.parent)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
import _plugin  # noqa: E402

# THE SHAPE, THE ID SCHEME AND THE MERGE ALL LIVE IN ONE MODULE. This tool used to write its own
# document with its own node ids (`main.sales`), while the projector wrote the same graph with
# different ids (`src:sales`) into two other files. Three homes for one fact, and the id schemes
# were why nobody had folded them: the same relation had two names. Importing the shape is what
# makes "one artifact, two producers" a mechanism rather than an intention.
from sdk.project import lineage_graph as _lg  # noqa: E402

GENERATOR = "mac_lineage.py"
OUT = _lg.ARTIFACT

#: `FROM x` and `JOIN x` — the relations a definition reads. Deliberately not a SQL parser: this
#: reads DECLARED dependencies out of a CREATE VIEW the engine itself stored, and every name it
#: finds is checked against the catalog, so a false positive cannot survive into the output.
_FROM = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w.]*)", re.IGNORECASE)
#: `<alias>.<column> AS <name>` — a column whose source is stated PLAINLY, no transformation.
_AS = re.compile(r"\b([A-Za-z_]\w*)\s*\.\s*(\"?[A-Za-z_]\w*\"?)\s+AS\s+(\"?[A-Za-z_]\w*\"?)",
                 re.IGNORECASE)
#: ONE SELECT ITEM, whatever its shape, ending in `AS <name>` — used to find the expression behind a
#: column that is not a plain reference, so a CAST can still be TRACED.
_ITEM = re.compile(r"(?P<expr>[^,]+?)\s+AS\s+(?P<out>\"?[A-Za-z_]\w*\"?)\s*(?=,|\bFROM\b)",
                   re.IGNORECASE | re.DOTALL)
#: every `alias.column` inside an expression.
_REF = re.compile(r"\b([A-Za-z_]\w*)\s*\.\s*(\"?[A-Za-z_]\w*\"?)")
_ALIAS = re.compile(r"\b([A-Za-z_][\w.]*)\s+(?:AS\s+)?([a-z]\w?)\b(?=\s*(?:,|\)|$|\bON\b|\bWHERE\b))",
                    re.IGNORECASE)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")

    # `--flows` EMITS THE ADAPTER'S OUTPUT ON STDOUT, because the console may not IMPORT the

    # framework — boundaries.yaml gives that tree `may_not_import: [sdk]` and

    # `may_sys_path_mutate: false`, so it reaches a tool only by running it. Without this the

    # console would need its own copy of `flows()`, which is the second home this whole change

    # exists to remove.

    ap.add_argument("--flows", action="store_true",

                    help="print the measured lineage in the FLOW shape consumers speak")
    ap.add_argument("--check", action="store_true", help="report drift; write nothing")
    a = ap.parse_args(argv)
    if getattr(a, "flows", False):
        import json as _j
        print(_j.dumps({"flows": flows(a.root)}))
        return 0

    root = pathlib.Path(a.root).resolve()
    try:
        athena = _plugin.required(str(root), "Athena")
    except Exception as exc:  # noqa: BLE001 - could-not-run is honest, never a finding
        print(f"COULD NOT RUN: {exc}")
        return 2
    con = athena(root=str(root))
    schema = getattr(con, "view_schema", None) or "main"

    catalog = _catalog(con)
    views = _views(con, schema)
    if not views:
        print(f"NOTHING TO MEASURE: no view in {schema!r} carries a definition. A bundle whose "
              f"served relations are base TABLES has no lineage to read from the engine — its "
              f"lineage lives in the transforms that built them.")
        return 1

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    columns: list[dict] = []
    for view, sql in views.items():
        me = _node(nodes, f"{schema}.{view}", "view")
        for ref in sorted(_refs(sql, catalog, schema, view)):
            kind = catalog.get(ref, "table")
            n = _node(nodes, ref, kind)
            # `feeds` from a LANDING, `derives_from` from another VIEW. One relation-level fact,
            # two kinds, because a reader following a wrong number needs to know whether the next
            # hop up is raw or already transformed.
            edges.append({"from": n["id"], "to": me["id"],
                          "kind": "derives_from" if kind == "view" else "feeds"})
        columns.extend(_columns(con, schema, view, sql))

    # THE CENSUS, NOT JUST WHAT A VIEW HAPPENED TO REFERENCE. Without this the graph held only the
    # relations some view reads, and an orphan register cannot report a source that feeds nothing
    # if that source is not in the graph at all. Measured on contoso5 before this block: 7 source
    # nodes for 8 declared landings — `orderrows` was absent, `orders` appeared only as a ghost
    # cited by a value register, and `sources_feeding_nothing` came back `[]` over a bundle where
    # two landings deliberately feed nothing. A census of ZERO is the only honest empty.
    for plane, kind in (("sources", "table"), ("datasets", "view")):
        for desc in sorted((root / "data" / plane).glob("*.yaml")):
            _node(nodes, f"{schema if kind == 'view' else 'main'}.{desc.stem}", kind)

    stated = sum(1 for c in columns if c["source_column"])
    traced = sum(1 for c in columns if c["source_column"] and c.get("transform"))
    # MERGE, NEVER OVERWRITE. The projector's half — the registers, the concepts, the issue counts —
    # lives in this same file and this tool does not own it. `_lg.merge` replaces exactly the node
    # kinds and edge kinds declared in `_lg.OWNERSHIP` for this producer and preserves everything
    # else, so re-measuring a warehouse cannot silently delete a bundle's ontology chain.
    doc = _lg.merge(
        _lg.load(root), GENERATOR,
        sorted(nodes.values(), key=lambda n: n["id"]),
        sorted(edges, key=lambda e: (e["to"], e["from"])),
        columns=columns, schema=schema, observed=datetime.now(UTC).date().isoformat(),
    )
    body = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out = root / OUT
    if a.check:
        now = out.read_text(encoding="utf-8") if out.is_file() else ""
        if _without_date(now) != _without_date(body):
            print(f"DRIFT — {OUT} no longer matches the warehouse. Re-run without --check.")
            return 1
        print(f"OK — {OUT} matches the warehouse.")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(f"  {OUT}: {len(nodes)} relation node(s), {len(edges)} relation edge(s), "
          f"{stated} of {len(columns)} column(s) traced "
          f"({traced} through a transform, {len(columns) - stated} derived from several or none)")
    for e in doc["edges"]:
        if e["kind"] in _lg.OWNERSHIP[GENERATOR]["edges"]:
            print(f"    {e['from']:44} --{e['kind']}-> {e['to']}")
    kept = [n for n in doc["nodes"] if n["kind"] not in _lg.OWNERSHIP[GENERATOR]["nodes"]]
    if kept:
        print(f"    (kept {len(kept)} node(s) this tool does not own: "
              f"{', '.join(sorted({n['kind'] for n in kept}))})")
    con.close()
    return 0


def _node(nodes: dict, relation: str, kind: str) -> dict:
    """One relation, in the ONE id scheme — `src:<name>` for a landing, `ds:<name>` for a served
    view. The bundle's descriptors name their objects by bare relation name and the projector keys
    on that, so resolving here is what lets both producers write the same node."""
    bare = relation.split(".")[-1]
    node_kind = "dataset" if kind == "view" else "source"
    nid = f"{_lg._PREFIX[node_kind]}:{bare}"
    return nodes.setdefault(nid, {"id": nid, "ref": bare, "kind": node_kind, "title": bare,
                                  "relation": relation, "issues": 0})


def _catalog(con) -> dict[str, str]:
    """Every relation the engine knows, and whether it is a view or a base table."""
    rows, _ = con.query(
        "select table_schema as d0, table_name as d1, table_type as d2 "
        "from information_schema.tables"
    )
    out: dict[str, str] = {}
    for r in rows:
        kind = "view" if "VIEW" in str(r["d2"]).upper() else "table"
        out[f"{r['d0']}.{r['d1']}"] = kind
        out.setdefault(str(r["d1"]), kind)
    return out


def _views(con, schema: str) -> dict[str, str]:
    rows, _ = con.query(
        "select table_name as d0, view_definition as d1 from information_schema.views "
        f"where table_schema = '{schema}' order by 1"
    )
    return {r["d0"]: r["d1"] for r in rows if r["d1"]}


def _refs(sql: str, catalog: dict[str, str], schema: str, itself: str) -> set[str]:
    """The relations this definition reads, CHECKED AGAINST THE CATALOG.

    Every candidate the regex finds must be a relation the engine actually knows, which is what
    makes a loose pattern safe here: an alias, a CTE name or a function call is not in the catalog
    and is dropped. A view is also excluded from its own dependency list.
    """
    found: set[str] = set()
    for raw in _FROM.findall(sql or ""):
        name = raw.strip('"')
        for cand in (name, f"{schema}.{name}", f"main.{name}"):
            if cand in catalog and catalog[cand] and "." in cand:
                if cand != f"{schema}.{itself}":
                    found.add(cand)
                break
    return found


def _columns(con, schema: str, view: str, sql: str) -> list[dict]:
    """Each column of the view, with its source column WHEN THE DEFINITION STATES ONE.

    THREE OUTCOMES, not two, and the middle one is why this was rewritten:

        plain      `d.DateKey AS DateKey`            -> source stated, no transformation
        TRACED     `CAST(d.Date AS DATE) AS Date`     -> exactly ONE column inside the expression, so
                                                        the source IS known and a transformation was
                                                        applied. Both facts are recorded.
        DERIVED    a CASE over two columns, a concat  -> several inputs or none; source stays NULL.

    The first version collapsed the middle case into DERIVED with a null source, and measured on one
    bundle that lost the traceable origin of 10 of 72 columns — every date (a CAST) and an age band.
    A null source reads as "cannot be traced"; these can. What is still refused is attributing a
    MULTI-input expression to the first identifier in it: that lineage gets followed and trusted.
    """
    rows, _ = con.query(
        "select column_name as d0 from information_schema.columns "
        f"where table_schema = '{schema}' and table_name = '{view}' order by ordinal_position"
    )
    stated = {out.strip('"'): (al, col.strip('"')) for al, col, out in _AS.findall(sql or "")}
    # A bare `a.Col` with no AS carries its own name through.
    for al, col in re.findall(r"\b([A-Za-z_]\w*)\s*\.\s*(\"?[A-Za-z_]\w*\"?)(?!\s+AS)", sql or ""):
        stated.setdefault(col.strip('"'), (al, col.strip('"')))
    aliases = _alias_map(sql or "")
    # THE EXPRESSION BEHIND EACH OUTPUT COLUMN, for the ones that are not a plain reference.
    exprs = {m.group("out").strip('"'): " ".join(m.group("expr").split())
             for m in _ITEM.finditer(sql or "")}
    out = []
    for r in rows:
        name = r["d0"]
        src = stated.get(name)
        expr = exprs.get(name)
        transform = None
        if src is None and expr:
            refs = {(al, col.strip('"')) for al, col in _REF.findall(expr)}
            if len(refs) == 1:
                src = next(iter(refs))
                transform = expr[:160]
        out.append({
            "view": f"{schema}.{view}",
            "column": name,
            "source_relation": aliases.get(src[0]) if src else None,
            "source_column": src[1] if src else None,
            # TRANSFORMED is not the same as UNTRACEABLE: a CAST has one source and a CASE over two
            # columns has none, and an operator following a wrong number needs to tell them apart.
            "transform": transform,
            "derived": src is None,
            "expression": expr[:160] if (src is None and expr) else None,
        })
    return out


def _alias_map(sql: str) -> dict[str, str]:
    """`FROM main.store s` -> {"s": "main.store"} — so a column's alias resolves to a relation."""
    out: dict[str, str] = {}
    for m in re.finditer(r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w.]*)\s+(?:AS\s+)?([A-Za-z_]\w{0,3})\b",
                         sql, re.IGNORECASE):
        rel, alias = m.group(1), m.group(2)
        if alias.upper() not in ("ON", "AS", "WHERE", "LEFT", "JOIN", "INNER", "FULL", "GROUP"):
            out[alias] = rel
    return out


def _without_date(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if '"observed"' not in ln)



def flows(root) -> list:
    """`data/lineage/lineage.json` in the FLOW shape every consumer already speaks.

    ONE LINEAGE ARTIFACT. Operator, 2026-09-28: "why there are two lineage artfifacts? there should be
    only one --- SSOT" — and then, on being shown the two: "its one too many !!!".

    There were two producers and they DISAGREED. This tool parses the view SQL and records that
    `dim_product.product_key` comes from `main.product.ProductKey`. `lineage_project.py` built a second
    set of flows from `data/transforms/*.yaml#inputs[].consumes` — a map `mac_transforms` DOES NOT
    GENERATE — so it found no edges and fell back to calling every column a derived CONSTANT, "via:
    literal per branch", for `p."ProductKey" AS product_key`. The pages rendered that, the console's
    Lineage view rendered "column edges: 0, derived: 12, kind: const" over a view whose every column has
    a named source, and check_lineage_coverage scored the bundle 0 % using the same broken model.

    IT WAS KNOWN AND PATCHED RATHER THAN FIXED: project_data._lineage_cols_md carries the comment
    "(lineage_project mislabels the un-raw-sourced cols 'const'; the real provenance is upstream)". A
    renderer compensating for a producer it does not trust is two homes with a patch between them —
    and the console, having no patch, showed what the data actually said.

    THE ADAPTER BELONGS TO THE PRODUCER, not to each consumer, or the third copy starts here. Both the
    projection (sdk/cli/harvest) and the coverage gate call this.
    """
    import json as _json
    f = pathlib.Path(root) / "data" / "lineage" / "lineage.json"
    if not f.is_file():
        return []
    doc = _json.loads(f.read_text(encoding="utf-8"))
    by_view: dict = {}
    for c in (doc.get("columns") or []):
        if isinstance(c, dict) and c.get("view"):
            by_view.setdefault(str(c["view"]), []).append(c)
    out = []
    for view, cols in sorted(by_view.items()):
        edges, derived, srcs = [], [], {}
        for c in cols:
            rel, col = c.get("source_relation"), c.get("source_column")
            if rel and col:
                edges.append({"to_col": c.get("column"), "src_table": str(rel).split(".")[-1],
                              "src_col": col, "rule_id": "", "kind": "passthrough"})
                srcs.setdefault(str(rel), []).append(str(col))
            else:
                # DERIVED MEANS COMPUTED and the expression is the whole answer. A derived column with
                # NO expression is the one case worth flagging rather than labelling `const`.
                derived.append({"to_col": c.get("column"),
                                "via": c.get("expression") or "derived — no expression recorded",
                                "kind": "computed" if c.get("expression") else "unexplained"})
        out.append({
            "transform": view,
            "kindl": "passthrough" if edges and not derived else (
                "computed" if derived and not edges else "passthrough + computed"),
            # `columns` IS A LIST OF OBJECTS, NOT OF STRINGS, and that is a contract, not a
            # preference. The renderer does `(s.columns || []).map((c) => ({ name: c.name }))`
            # (LineageView.jsx#buildModel) and the downstream branch keys a Map on `c.name`. This
            # adapter shipped `sorted(set(cs))` — bare strings — so every row resolved to
            # `undefined` and the SOURCE BOX RENDERED WITH NO COLUMNS while the header still said
            # "sources: 1 · column edges: 12 · kind: passthrough". Twelve edges converged on an
            # empty box. The header was right and the picture was empty, which is the worst of the
            # two failure modes: nothing looked broken enough to disbelieve.
            #
            # `badge` is carried because the shape it replaces carried it; a renderer reading an
            # absent key gets undefined either way, but a producer that silently narrows a shape is
            # how this happened in the first place.
            "sources": [{"rel": r, "short": r.split(".")[-1], "schema": r.split(".")[0],
                         "columns": [{"name": c, "badge": None} for c in sorted(set(cs))],
                         "extra": 0, "role": None}
                        for r, cs in sorted(srcs.items())],
            "dataset": {"name": view, "columns": [{"name": c.get("column")} for c in cols]},
            "edges": edges, "derived": derived, "seeds": [], "rules": [], "predicates": [],
            "grain": None,
        })
    return out

if __name__ == "__main__":
    sys.exit(main())
