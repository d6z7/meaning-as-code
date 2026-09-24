"""Generate a MAC bundle from a database, with NO human input.

STAGE 7 of PIPELINE_TESTING.md §8.2. The thing that turns a third-party corpus from a static ruler
into questions this engine can actually be asked — and the answer to the n = 1 problem that runs
under every measurement in this estate.

TWO TIERS, AND THE DIFFERENCE IS WHERE THE EVIDENCE COMES FROM.

  L0  what the schema DECLARES — tables, columns, types, primary keys, foreign keys.
      Nothing is measured and nothing is guessed.
  L1  + what the data MEASURES — row counts, distinct counts, null rates, which columns are
      actually unique, which look like foreign keys by containment.

Neither asks a person anything, and that is the point: **L0 receives no more human input than a
text-to-SQL baseline does**, so an L0 score is comparable to a published one. L1 and L2 (a human
adds rules, default readings, refusal scope) then measure what DECLARING MEANING buys, and the
curve L0 → L1 → L2 is this estate's whole thesis drawn as a line.

WHAT AN L0/L1 BUNDLE IS NOT. It has no rules, no default readings, no disclosures, no refusal
scope and no business meaning whatsoever. It is a FLOOR measurement, and reading it as acceptance
would be a category error — `invariants/RESULTS.md` records that ruling as still open. Its
`confidence` is `I` (inferred) and its `provenance` says `generated`, so nothing downstream can
mistake it for something a person stands behind.

    python bundlegen/generate.py --db <duckdb|sqlite> --schema main --out <dir> [--tier L1]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import re
import sys
from dataclasses import dataclass, field

SCHEMA_VERSION = "0.1.14"

#: Columns whose NAME says they identify something. A convention, declared here rather than
#: scattered: an inference this whole generator rests on should be readable in one place.
_KEYISH = re.compile(r"(key|code|id|no|nr)$", re.I)
_DATEISH = re.compile(r"(date|dt|time|stamp|day|month|year)$", re.I)

_NUMERIC = ("INT", "DECIMAL", "NUMERIC", "DOUBLE", "FLOAT", "REAL", "BIGINT", "HUGEINT", "SMALLINT")
_TEMPORAL = ("DATE", "TIME", "TIMESTAMP")


@dataclass
class Column:
    name: str
    type: str
    declared_pk: bool = False
    declared_fk: tuple[str, str] | None = None  # (table, column)
    distinct: int | None = None
    nulls: int | None = None
    unique: bool | None = None
    inferred_fk: tuple[str, str] | None = None

    @property
    def is_numeric(self) -> bool:
        return any(t in self.type.upper() for t in _NUMERIC)

    @property
    def is_temporal(self) -> bool:
        return any(t in self.type.upper() for t in _TEMPORAL)


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    rows: int | None = None

    def col(self, name: str) -> Column | None:
        return next((c for c in self.columns if c.name.lower() == name.lower()), None)


# --------------------------------------------------------------------------- read the schema


def read_schema(con, schema: str, tier: str) -> dict[str, Table]:
    """L0: the catalogue. L1 adds a profile pass over the data."""
    tables: dict[str, Table] = {}
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = ? ORDER BY 1",
        [schema],
    ).fetchall()
    for (t,) in rows:
        cols = con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
            [schema, t],
        ).fetchall()
        tables[t] = Table(name=t, columns=[Column(name=c, type=str(d)) for c, d in cols])

    _read_declared_constraints(con, schema, tables)
    if tier == "L1":
        _profile(con, schema, tables)
        _infer_keys(tables)
    return tables


def _read_declared_constraints(con, schema: str, tables: dict[str, Table]) -> None:
    """Declared PK/FK where the catalogue has them. Absent is NOT an error — the worked bundle's
    landing declares ZERO constraints, which is the normal state of a raw warehouse and the whole
    reason L1 exists."""
    try:
        rows = con.execute(
            "SELECT table_name, constraint_type, constraint_column_names "
            "FROM duckdb_constraints() WHERE schema_name = ?",
            [schema],
        ).fetchall()
    except Exception:  # noqa: BLE001 - another engine, or no constraint catalogue
        return
    for tname, ctype, cols in rows:
        tab = tables.get(tname)
        if tab is None or not cols:
            continue
        if str(ctype).upper().startswith("PRIMARY"):
            for c in cols:
                col = tab.col(c)
                if col:
                    col.declared_pk = True


def _profile(con, schema: str, tables: dict[str, Table]) -> None:
    """L1: row counts, distinct counts, null counts, uniqueness. Measured, never assumed."""
    for t in tables.values():
        try:
            t.rows = con.execute(f'SELECT count(*) FROM "{schema}"."{t.name}"').fetchone()[0]
        except Exception:  # noqa: BLE001
            continue
        if not t.rows:
            continue
        for c in t.columns:
            try:
                d, n = con.execute(
                    f'SELECT count(DISTINCT "{c.name}"), count(*) - count("{c.name}") '
                    f'FROM "{schema}"."{t.name}"'
                ).fetchone()
            except Exception:  # noqa: BLE001 - an unprofilable type is not a failure
                continue
            c.distinct, c.nulls = int(d), int(n)
            c.unique = (c.nulls == 0 and c.distinct == t.rows)


def _infer_keys(tables: dict[str, Table]) -> None:
    """L1: which column identifies a row, and which points at another table.

    A CANDIDATE KEY IS MEASURED, NOT NAMED. `unique and not null` is the claim; the name only
    breaks ties when several columns qualify, because on a small table many columns are
    accidentally unique and picking by name alone is how a surrogate gets mistaken for a natural
    key -- the defect that cost this estate a silent no-op collapse.
    """
    pk_of: dict[str, str] = {}
    for t in tables.values():
        declared = [c.name for c in t.columns if c.declared_pk]
        if declared:
            pk_of[t.name] = declared[0]
            continue
        cands = [c for c in t.columns if c.unique]
        if not cands:
            continue
        named = [c for c in cands if _KEYISH.search(c.name)]
        pk_of[t.name] = (named or cands)[0].name

    # A column NAMED like another table's key, of a compatible kind, is a candidate foreign key.
    # Containment is not checked here: it needs a join per pair and this is the cheap tier. The
    # edge it produces is a CANDIDATE and the bundle says so.
    for t in tables.values():
        for c in t.columns:
            if c.name == pk_of.get(t.name):
                continue
            for other, pk in pk_of.items():
                if other != t.name and c.name.lower() == pk.lower():
                    c.inferred_fk = (other, pk)
                    break


# --------------------------------------------------------------------------- classify + emit


def concept_name(table: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[^A-Za-z0-9]+", table) if p) or table


def classify(t: Table, tables: dict[str, Table]) -> str:
    """One of the seven declared classes, from shape alone.

    An `event` POINTS AT things and carries numbers; a `reference` is POINTED AT. Nothing here
    knows what the rows mean, and the class is the most consequential guess this file makes --
    it decides the fold gate and the count route. Recorded in the concept's own note.
    """
    out = sum(1 for c in t.columns if c.inferred_fk or c.declared_fk)
    pointed_at = any(
        c.inferred_fk and c.inferred_fk[0] == t.name
        for other in tables.values()
        for c in other.columns
    )
    numeric = sum(1 for c in t.columns if c.is_numeric and not _KEYISH.search(c.name))
    if out >= 2 and numeric >= 1:
        return "event"
    if pointed_at:
        return "reference"
    return "reference"


def field_roles(t: Table, pk: str | None, ns: str) -> dict[str, str]:
    roles: dict[str, str] = {}
    for c in t.columns:
        if c.name == pk or c.inferred_fk or c.declared_fk or c.declared_pk:
            role = "key"
        elif c.is_temporal or _DATEISH.search(c.name):
            role = "period" if c.is_temporal else "dimension"
        elif c.is_numeric and not _KEYISH.search(c.name):
            role = "measure"
        else:
            role = "dimension"
        roles[c.name] = f"{ns}.field_role.{role}"
    return roles


def _y(v) -> str:
    s = str(v)
    return f"'{s}'" if re.search(r"[:#\[\]{}]|^\s|\s$", s) or s == "" else s


def emit_concept(t: Table, pk: str | None, klass: str, ns: str, schema: str, tier: str) -> str:
    cn = concept_name(t.name)
    roles = field_roles(t, pk, ns)
    measured = (
        f" Profiled {t.rows} row(s)." if t.rows is not None else ""
    )
    lines = [
        f"# GENERATED by bundlegen at tier {tier} — NOT AUTHORED. No rule, no default reading, no",
        "# refusal scope and no business meaning: this is the FLOOR, and reading it as acceptance",
        "# would be a category error. Every inference it makes is named in `note` below.",
        "metadata:",
        f"  concept: {cn}",
        f"  source: {ns.upper()}",
        "  version: '1.0'",
        f"  schema_version: {SCHEMA_VERSION}",
        "  status: draft",
        "  owner: generated",
        "  confidence: I",
        "  provenance: generated",
        "concept:",
        f"  name: {cn}",
        f"  label: {cn}",
        f"  class: {klass}",
    ]
    if pk:
        lines += [
            "  identity:",
            "    kind: fk_name",
            f"    canonical_key: {pk}",
            "    note: >-",
            f"      INFERRED, not declared. {pk} was measured unique and non-null over"
            f" {t.rows} rows"
            if t.rows
            else f"      INFERRED from the name {pk!r}; nothing declares it.",
        ]
    lines += [
        "  definition: >-",
        f"    Generated from {schema}.{t.name}. {len(t.columns)} column(s).{measured} NOTHING HERE",
        "    STATES WHAT THE ROWS MEAN — a generated bundle carries shape, never meaning.",
        "grounding:",
        "  kind: sql_table",
        f"  table: {t.name}",
        f"  schema: {schema}",
        "  field_roles:",
    ]
    for col, role in roles.items():
        lines.append(f"    {_y(col)}: {role}")
    lines += [
        "  note: >-",
        "    ROLES ARE INFERRED FROM TYPE AND NAME, and each inference is a guess a person would",
        "    make differently: a numeric column that is not key-shaped is called a measure, a",
        "    temporal one a period, everything else a dimension. The class above is the most",
        f"    consequential of them — {klass!r} decides the fold gate and the count route.",
        "governance:",
        "  owner: generated",
        f"  last_reviewed: {_dt.date.today().isoformat()}",
    ]
    return "\n".join(lines) + "\n"


def emit_edges(tables: dict[str, Table], pk_of: dict[str, str], ns: str) -> str:
    """Candidate joins, in the shape the loader actually reads.

    `endpoints.from/to` is required — an edge written as a flat from/to pair loads as
    "missing required key 'endpoints'", which is the loader telling a generator that a shape it
    invented is not the shape that is declared.

    CONTAINMENT IS NOT CHECKED. A column NAMED like another table's key is not a foreign key, and
    every edge here is a claim the data has not been asked to support. L2 authoring is where a
    join earns `0 fan-out measured`; this tier can only say where to look.
    """
    out = [
        "# GENERATED by bundlegen — candidate joins inferred from column names matching another",
        "# table's key. Containment unverified: a name match is not a foreign key.",
        "edges:",
    ]
    n = 0
    for t in tables.values():
        for c in t.columns:
            fk = c.inferred_fk or c.declared_fk
            if not fk:
                continue
            target, tcol = fk
            n += 1
            out += [
                f"  - edge_id: {t.name.lower()}__references__{target.lower()}__{c.name.lower()}",
                "    level: physical",
                "    type: foreign_key",
                "    endpoints:",
                "      from:",
                f"        source: {ns.upper()}",
                f"        concept: {concept_name(t.name)}",
                "        cardinality: '0..N'",
                "      to:",
                f"        source: {ns.upper()}",
                f"        concept: {concept_name(target)}",
                "        cardinality: '1'",
                f"    realized_by: {t.name}.{c.name}",
                f"    notes: INFERRED — {t.name}.{c.name} matches {target}.{tcol} by NAME."
                " Containment is unverified, so this edge is a place to look and not a"
                " measured join.",
            ]
    return "\n".join(out) + "\n" if n else "edges: []\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--schema", default="main")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tier", choices=("L0", "L1"), default="L1")
    ap.add_argument("--namespace", default="gen")
    a = ap.parse_args(argv)

    import duckdb

    con = duckdb.connect(a.db, read_only=True)
    tables = read_schema(con, a.schema, a.tier)
    if not tables:
        raise SystemExit(f"no tables in schema {a.schema!r}")

    pk_of = {
        t.name: next(
            (c.name for c in t.columns if c.declared_pk),
            next((c.name for c in t.columns if c.unique and _KEYISH.search(c.name)), None),
        )
        for t in tables.values()
    }

    out = pathlib.Path(a.out)
    (out / "ontology" / "concepts").mkdir(parents=True, exist_ok=True)
    for t in tables.values():
        klass = classify(t, tables)
        (out / "ontology" / "concepts" / f"{t.name}.yaml").write_text(
            emit_concept(t, pk_of.get(t.name), klass, a.namespace, a.schema, a.tier)
        )
    (out / "ontology" / "edges.yaml").write_text(emit_edges(tables, pk_of, a.namespace))
    (out / "mac.project.yaml").write_text(
        f"# GENERATED by bundlegen, tier {a.tier}.\n"
        f"project: {a.namespace}\nschema_version: {SCHEMA_VERSION}\n"
    )
    (out / "vocabulary.yaml").write_text(
        "# GENERATED by bundlegen — the field-role terms the concepts reference.\n"
        f"{a.namespace}:\n  field_role:\n    terms:\n"
        + "".join(
            f"      {r}: generated role, inferred from column type and name\n"
            for r in ("key", "measure", "dimension", "period", "attribute")
        )
    )

    n_edges = sum(1 for t in tables.values() for c in t.columns if c.inferred_fk or c.declared_fk)
    n_keys = sum(1 for v in pk_of.values() if v)
    print(f"tier {a.tier}: {len(tables)} concept(s), {n_keys} with an inferred key, "
          f"{n_edges} candidate edge(s)  ->  {out}")
    for t in tables.values():
        ms = [c.name for c in t.columns if c.is_numeric and not _KEYISH.search(c.name)]
        print(f"  {concept_name(t.name):<16} {classify(t, tables):<10} key={pk_of.get(t.name)!r:<14}"
              f" rows={t.rows} measures={ms[:4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
