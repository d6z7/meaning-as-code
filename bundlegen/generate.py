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


def read_schema_sqlite(con, tier: str) -> dict[str, Table]:
    """The same three passes, against SQLite's PRAGMAs.

    WHY A SECOND READER EXISTS. `duckdb_constraints()` is DuckDB's, and the benchmark corpora ship
    SQLite. It is worth the second path for one reason: **SQLite DECLARES ITS KEYS.** The worked
    bundle's landing declares zero constraints -- 0 rows from `duckdb_constraints()` -- so every
    key and every edge there had to be INFERRED from names and profiles. A BIRD database states
    its primary and foreign keys outright, which is the first chance this generator has had to be
    told rather than to guess.
    """
    tables: dict[str, Table] = {}
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY 1"
    ).fetchall()]
    for t in names:
        cols = con.execute(f'PRAGMA table_info("{t}")').fetchall()
        # PRAGMA table_info -> (cid, name, type, notnull, dflt_value, pk)
        tab = Table(name=t, columns=[Column(name=c[1], type=str(c[2] or "")) for c in cols])
        for c in cols:
            if c[5]:  # pk ordinal, 0 when not part of the primary key
                col = tab.col(c[1])
                if col:
                    col.declared_pk = True
        tables[t] = tab

    # DECLARED FOREIGN KEYS, which is the point of coming here. `Column.declared_fk` has existed
    # on the dataclass since the generator was written and NOTHING EVER SET IT -- every edge the
    # generator has ever emitted was a name match, including on schemas that declared the real
    # thing. PRAGMA foreign_key_list -> (id, seq, table, from, to, on_update, on_delete, match).
    for t, tab in tables.items():
        try:
            for fk in con.execute(f'PRAGMA foreign_key_list("{t}")').fetchall():
                target, from_col, to_col = fk[2], fk[3], fk[4]
                col = tab.col(from_col) if from_col else None
                if col is None or target not in tables:
                    continue
                # `to` is NULL when the FK targets the parent's primary key implicitly
                if not to_col:
                    to_col = next(
                        (c.name for c in tables[target].columns if c.declared_pk), to_col
                    )
                if to_col:
                    col.declared_fk = (target, to_col)
        except Exception:  # noqa: BLE001 - a table with no FK pragma is simply not one
            continue

    if tier == "L1":
        _profile_sqlite(con, tables)
        _infer_keys(tables)
    return tables


def _profile_sqlite(con, tables: dict[str, Table]) -> None:
    """L1 over SQLite: the same measurements, the same refusal to assume any of them."""
    for t in tables.values():
        try:
            t.rows = con.execute(f'SELECT count(*) FROM "{t.name}"').fetchone()[0]
        except Exception:  # noqa: BLE001
            continue
        if not t.rows:
            continue
        for c in t.columns:
            try:
                d, n = con.execute(
                    f'SELECT count(DISTINCT "{c.name}"), count(*) - count("{c.name}") '
                    f'FROM "{t.name}"'
                ).fetchone()
                c.distinct, c.nulls = int(d), int(n)
                # UNIQUENESS IS MEASURED, NOT NAMED. The same rule the DuckDB path uses: a column
                # is a candidate key only if it has no nulls AND as many distinct values as rows.
                c.unique = (c.nulls == 0 and c.distinct == t.rows)
            except Exception:  # noqa: BLE001 - an unreadable column is simply unprofiled
                continue


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


def measure_concept_name(table: str, column: str) -> str:
    """A business-ish name for a measure column, WITHOUT its table qualifier.

    BIRD and Spider columns are usually already business words -- `Enrollment (K-12)`,
    `AvgScrRead`, `FreeMealCount`. Punctuation and spaces go; the words stay. The table is NOT
    prefixed: the prompt must name a MEASURE, not a location, and `FrpmEnrollment` would be the
    warehouse leaking through a concept name.
    """
    import re as _re

    cleaned = _re.sub(r"[^A-Za-z0-9]+", " ", column).strip()
    parts = [w[:1].upper() + w[1:] for w in cleaned.split()]
    name = "".join(parts) or concept_name(table)
    # a name that starts with a digit is not an identifier anywhere downstream
    return name if not name[:1].isdigit() else f"M{name}"


def emit_measure_concept(t: Table, col: Column, ns: str, schema: str, tier: str) -> str:
    """One measure column, as its own `class: measure` concept.

    WHY THIS EXISTS, and it is the difference between a bundle that loads and a bundle that can
    ANSWER. The generator emitted one concept per TABLE and filed every number as a
    `field_role: measure` on it. `Vocabulary.from_index` counts a measure only when a CONCEPT's
    class is `measure` -- so `california_schools` declared **23 measure columns and offered the
    model 0 measures**. It could be asked to count schools; it could never be asked to total
    enrolment, which is most of what that database is for.

    THE HAND-AUTHORED BUNDLE HAS THE ANSWER AND THE GENERATOR WAS NOT COPYING IT. Contoso models
    `NetSalesAmount` as its own `class: measure` concept over the fact relation. Emitting the same
    shape here is also what makes L1 and L2 COMPARABLE, which is the entire point of the tier
    curve: two bundles that disagree about what a measure IS cannot be two points on one line.

    AND IT KEEPS 04 §4. The prompt names `Enrollment`, never `frpm."Enrollment (K-12)"`. The
    column appears only in `grounding`, which the model is never shown -- the planner reads it.
    """
    cn = measure_concept_name(t.name, col.name)
    return "\n".join([
        f"# GENERATED by bundlegen at tier {tier} — NOT AUTHORED. This concept exists because the",
        "# column carries a number; NOTHING here says what the number MEANS, whether it is",
        "# additive, or over what grain it may be summed. A hand-authored measure declares all",
        "# three; this declares none of them and says so.",
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
        "  class: measure",
        "  definition: >-",
        f"    The number carried by one column of {schema}.{t.name}, named after the column",
        f"    because nothing authored a better name. Type {col.type or 'unknown'}.",
        "    ADDITIVITY IS UNDECLARED: nothing here says whether summing it across rows is",
        "    meaningful, and the fold gate has no declaration to consult.",
        "grounding:",
        "  kind: sql_table",
        f"  table: {t.name}",
        f"  schema: {schema}",
        "  field_roles:",
        f"    {_y(col.name)}: {ns}.field_role.measure",
        "  note: >-",
        "    INFERRED: this column is numeric and not key-shaped. A person would call some of",
        "    these flags, codes or identifiers instead — a 0/1 column reads as a measure to a",
        "    profiler and as a dimension to anyone who knows the business.",
        "governance:",
        "  owner: generated",
        f"  last_reviewed: {_dt.datetime.now(_dt.UTC).date().isoformat()}",
    ]) + "\n"


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
        f"  last_reviewed: {_dt.datetime.now(_dt.UTC).date().isoformat()}",
    ]
    return "\n".join(lines) + "\n"


def emit_edges(tables: dict[str, Table], pk_of: dict[str, str], ns: str) -> str:
    """Candidate joins, in the shape the loader actually reads.

    BUILT AS DATA AND DUMPED, NOT ASSEMBLED AS TEXT. The first version composed the file line by
    line, and a note containing "unverified: a declared key" -- a bare colon inside an unquoted
    scalar -- made all 11 generated bundles fail to parse. The generator reported success on
    every one of them, because nothing in it ever LOADED what it wrote. `yaml.safe_dump` makes
    that impossible instead of unlikely; `emit_edges_is_loadable` in the self-test keeps it so.

    `endpoints.from/to` is required — an edge written as a flat from/to pair loads as
    "missing required key 'endpoints'", which is the loader telling a generator that a shape it
    invented is not the shape that is declared.

    CONTAINMENT IS NOT CHECKED, declared or inferred. A catalogue's foreign key says the
    relationship is INTENDED; it does not say every value is present. L2 authoring is where a
    join earns `0 fan-out measured`.
    """
    import yaml as _y

    header = (
        "# GENERATED by bundlegen. Each edge says whether the catalogue DECLARED it or whether\n"
        "# it was inferred from a name match — the two are not the same evidence and a bundle\n"
        "# must not blur them. Containment is unverified either way.\n"
    )
    edges = []
    for t in tables.values():
        for c in t.columns:
            # DECLARED BEATS INFERRED. The order used to be `inferred or declared`, which on a
            # schema that states its keys preferred the GUESS over the statement.
            fk = c.declared_fk or c.inferred_fk
            if not fk:
                continue
            target, tcol = fk
            note = (
                f"DECLARED — the catalogue states {t.name}.{c.name} references {target}.{tcol}. "
                f"Containment is still unverified; a declared key says the relationship is "
                f"INTENDED, not that every value is present."
                if c.declared_fk is not None else
                f"INFERRED — {t.name}.{c.name} matches {target}.{tcol} by NAME only. Nothing "
                f"declares this and containment is unverified, so it is a place to look and "
                f"not a measured join."
            )
            edges.append({
                "edge_id": f"{t.name.lower()}__references__{target.lower()}__{c.name.lower()}",
                "level": "physical",
                "type": "foreign_key",
                "endpoints": {
                    "from": {"source": ns.upper(), "concept": concept_name(t.name),
                             "cardinality": "0..N"},
                    "to": {"source": ns.upper(), "concept": concept_name(target),
                           "cardinality": "1"},
                },
                "realized_by": f"{t.name}.{c.name}",
                "notes": note,
            })
    if not edges:
        return header + "edges: []\n"
    return header + _y.safe_dump(
        {"edges": edges}, sort_keys=False, allow_unicode=True, width=10**9, default_flow_style=False
    )

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--schema", default="main")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tier", choices=("L0", "L1"), default="L1")
    ap.add_argument("--namespace", default="gen")
    a = ap.parse_args(argv)

    # WHICH ENGINE, decided by the file rather than by a flag the caller has to remember. A
    # SQLite database opened as DuckDB reads as an empty catalogue -- no tables, no error, and a
    # bundle of zero concepts that looks like a successful run.
    import pathlib as _pl

    _is_sqlite = False
    try:
        with open(a.db, "rb") as fh:
            _is_sqlite = fh.read(16).startswith(b"SQLite format 3")
    except OSError:
        pass
    if _is_sqlite or _pl.Path(a.db).suffix.lower() in (".sqlite", ".sqlite3", ".db"):
        import sqlite3

        # READ-ONLY, AND IT HAS TO FALL BACK. `mode=ro` refuses a database in WAL mode, because
        # opening one may require recovering its -wal companion -- which is a write. Measured:
        # 1 of BIRD's 11 dev databases (card_games, 262 MB) failed exactly there, and a generator
        # that skips a database because of how it was last closed is silently measuring 10 of 11.
        #
        # `immutable=1` is the honest second choice: it PROMISES the file will not change under
        # us, which is true of a benchmark corpus, and it never writes. Only if both refuse does
        # this open normally -- and nothing on this path ever issues a write.
        con = None
        for uri in (f"file:{a.db}?mode=ro", f"file:{a.db}?immutable=1"):
            try:
                con = sqlite3.connect(uri, uri=True)
                con.execute("SELECT count(*) FROM sqlite_master").fetchone()
                break
            except sqlite3.Error:
                con = None
        if con is None:
            con = sqlite3.connect(a.db)
        tables = read_schema_sqlite(con, a.tier)
        return _emit(a, tables)

    import duckdb

    con = duckdb.connect(a.db, read_only=True)
    tables = read_schema(con, a.schema, a.tier)
    return _emit(a, tables)


def _verify_loads(out: pathlib.Path) -> str | None:
    """Load the bundle we just wrote. Returns the failure, or None.

    THE GATE THAT WAS MISSING, and its absence cost 11 invalid bundles that all reported success.
    A generator that never loads its own output can only tell you it finished, never that it
    produced anything usable -- and YAML fails on punctuation, so "it wrote files" and "it wrote
    a bundle" are genuinely different claims.

    Import is LOCAL and failure is TOLERATED: the generator must still run where mac-runtime is
    not installed. It says so rather than passing silently, because "could not check" and
    "checked and fine" are not the same result.
    """
    try:
        from mac_runtime.ontology import OntologyIndex
    except ImportError:
        return "NOT CHECKED — mac_runtime is not importable here, so the bundle was not loaded"
    try:
        idx = OntologyIndex.from_directory(str(out))
    except Exception as exc:  # noqa: BLE001 - any load failure is the finding
        return f"{type(exc).__name__}: {str(exc)[:200]}"
    if not idx.concepts:
        return "loads, but declares ZERO concepts"
    return None


def _emit(a, tables: dict[str, Table]) -> int:
    """Write the bundle. SHARED BY BOTH ENGINES -- a second copy of this is a second bundle
    SHAPE, and the loader would start refusing one of them."""
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
    # A REGENERATION REPLACES, IT DOES NOT ACCUMULATE. Writing into an existing directory left
    # every file the generator no longer produces sitting beside the ones it does -- so renaming
    # a concept left its corpse behind and the bundle then declared the name TWICE. Measured: the
    # rename that disambiguated `Account` produced exactly that, and the load gate caught it.
    #
    # Only this directory is cleared, and only of `.yaml`: it is generated output, wholly
    # reproducible from the database, and nothing a person authored is ever in it.
    concepts_dir = out / "ontology" / "concepts"
    if concepts_dir.is_dir():
        for stale in concepts_dir.glob("*.yaml"):
            stale.unlink()
    concepts_dir.mkdir(parents=True, exist_ok=True)
    # ONE CONCEPT PER TABLE, AND ONE PER MEASURE COLUMN. The second half was missing, and it is
    # what decides whether the bundle can be ASKED anything: `Vocabulary.from_index` counts a
    # measure only when a CONCEPT's class is `measure`, so a bundle with 23 measure COLUMNS
    # offered the model ZERO measures.
    # EVERY NAME ALREADY TAKEN, before a single measure is named. The first version guarded
    # measure-against-measure only, and `financial` has a column that cleans to `Account` while a
    # TABLE concept of that name already exists -- caught by the generator's own load gate, which
    # is what that gate is for.
    taken: set[str] = {concept_name(t.name) for t in tables.values()}
    for t in tables.values():
        klass = classify(t, tables)
        (out / "ontology" / "concepts" / f"{t.name}.yaml").write_text(
            emit_concept(t, pk_of.get(t.name), klass, a.namespace, a.schema, a.tier)
        )
        for col in t.columns:
            if field_roles(t, pk_of.get(t.name), a.namespace).get(col.name, "").endswith(
                ".measure"
            ):
                base = measure_concept_name(t.name, col.name)
                # A NAME COLLISION IS NOT SILENTLY RESOLVED. Two tables can both carry `Total`,
                # and a column can clean to the same word as a table -- one concept overwriting
                # the other loses a measure with no symptom at all. The loser gets its table's
                # name, which is ugly and honest; if THAT is taken too it gets a counter, because
                # a generator that cannot name a thing must still not drop it.
                cn, n = base, 1
                if cn in taken:
                    cn = f"{concept_name(t.name)}{base}"
                while cn in taken:
                    n += 1
                    cn = f"{concept_name(t.name)}{base}{n}"
                taken.add(cn)
                (out / "ontology" / "concepts" / f"measure_{cn}.yaml").write_text(
                    emit_measure_concept(t, col, a.namespace, a.schema, a.tier)
                    .replace(f"concept: {measure_concept_name(t.name, col.name)}\n",
                             f"concept: {cn}\n")
                    .replace(f"  name: {measure_concept_name(t.name, col.name)}\n",
                             f"  name: {cn}\n")
                    .replace(f"  label: {measure_concept_name(t.name, col.name)}\n",
                             f"  label: {cn}\n")
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

    problem = _verify_loads(out)
    if problem is None:
        print("  ✓ loads: the runtime parsed this bundle and found its concepts")
        return 0
    if problem.startswith("NOT CHECKED"):
        print(f"  ? {problem}")
        return 0
    print(f"  ✗ WROTE AN UNLOADABLE BUNDLE — {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
