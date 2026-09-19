#!/usr/bin/env python3
"""mac_sample.py — cut the preview of a relation, and DRAW a concept's members, FROM THE LIVE DATA.

    python3 tools/mac_sample.py <root> [stem ...] [--plane sources|datasets|both|concepts|all]
                                [--limit 20] [--concept-limit 40] [--seed <text>]
                                [--dry-run] [--verify] [--json] [--self-test]

TWO DRAWS, AND A BUNDLE MUST BE ABLE TO REPRODUCE EITHER. `--plane sources|datasets|both` (the
DEFAULT, unchanged) cuts the relation preview described below: a total order over every declared
column, the lexicographically smallest rows, byte-identical on re-run. `--plane concepts` draws a
SEEDED RANDOM sample of A CONCEPT'S OWN MEMBERS at the columns that concept declares — a different
population, a different column set and a different window, all three for reasons written out above
`THE CONCEPT DRAW` further down. `--plane all` does both. Neither draw can reach the other's files.

WHY THIS FILE EXISTS. `data/samples/<stem>[.src].sample.csv` is the only artifact family in the data
plane with no producer, no instruction and no gate. It was the one family a human typed: the plane
doc's own entry said "authored — NOT derived — no tool in meaning-as-code/tools writes data/samples
... in practice an agent runs SELECT * FROM <relation> LIMIT 20 and dumps the CSV by hand." Measured
on the reference bundle, 3 of its 25 hand-cut previews had rotted against their descriptors — one
missing TEN of 22 columns while a decision record cited that exact file as proof a register was
built. A preview nobody derives is a preview nobody can re-derive, and it still reads as evidence.

THE ONE RULE THIS FILE IS BUILT AROUND: a sample is DERIVED FROM THE RELATION or it is not evidence.
Nothing here invents a row, a column or a value. Every failure path writes NOTHING and says why.

HOW THE HEADER CANNOT DRIFT. The projection is rendered FROM THE DESCRIPTOR — one explicitly quoted
column per `columns[]` entry, in document order — so the header is the descriptor's column list BY
CONSTRUCTION. `SELECT *` is forbidden here: it would let the engine decide the header, which is the
exact defect above. A declared column the relation does not have, or a relation column the
descriptor does not declare, is a REFUSAL that names the disagreement (both directions: an explicit
projection makes an undeclared engine column invisible, so the catalog is compared as a set).

HOW A SECOND RUN IS BYTE-IDENTICAL. `SELECT ... LIMIT 20` has no defined row order, so a bare cut
churns on every re-run and operators stop re-cutting — which is how the rot came back last time.
Three rules, in increasing strength:
  1. the header comes from the descriptor, so it cannot move with physical column order;
  2. the row WINDOW is `ORDER BY <every declared column, in descriptor order> ASC NULLS LAST` —
     a TOTAL order over the declared columns, so it does not depend on a declared key actually being
     unique (that is a claim this tool cannot verify) and needs no profile (`identity_evidence` is
     written by a later step than the first cut, so a cut that consulted it would use one order
     before that step and another after);
  3. the RENDERED rows are sorted lexicographically in Python before writing, so the file is a
     function of the row SET and the render rather than of the engine's return order, and tied rows
     are byte-identical and cannot churn.
`ASC NULLS LAST` is spelled on every key rather than inherited: a bare `ORDER BY col` is moved by a
session's default null ordering, which no gate can see.

THE PRICE, STATED RATHER THAN HIDDEN: the file is the 20 lexicographically smallest rows of the
declared projection. That is a BIASED window, not a random sample, and it is the right price —
reproducibility is what makes a future diff mean "the data moved". The plane doc already forbids
reading an enumeration off a sample; this window owes SHAPE, not coverage.

WHAT IS PROVEN AND WHAT IS NOT. The value renderer dispatches on the RUNTIME Python type, because
the two descriptor type vocabularies disagree about the same types. One engine in this estate hands
back native objects (int/str/datetime/Decimal/None); another hands every cell back as a string. So
the honest claim is PER-ENGINE byte-idempotence, never cross-engine byte-equality: re-cutting the
same relation through a different engine can legitimately change the text of a timestamp's
sub-second tail. The run record therefore names the engine that wrote each file.

'' AND NULL COLLAPSE, and the contract cannot separate them: `Shape` says "empty cell for NULL", and
an empty string renders to an empty field too. Both occur in one measured relation. A reader who
infers nullability from an empty cell will be wrong; the sample is a preview, not evidence about
nulls. Nothing here rewrites one into the other.

EXIT CODES. 0 every requested preview was derived · 1 a finding about the bundle (drift, a relation
that is not there, a zero-row relation, a stem nobody declares) · 2 could not run (no connector,
unresolvable, driver absent, a non-SQL source, an empty population). A genuine finding outranks a
could-not-run. Every verdict line carries its DENOMINATOR.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

import yaml

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:                                                        # noqa: E402
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mac_diag as D                                                             # noqa: E402

NAME = "mac_sample"
CONTRACT = "mac.sample/1"          # the render + dialect contract version, recorded per file

#: The fractional-second width for a rendered timestamp. THREE DIGITS, and it is INHERITED rather
#: than chosen: it is the only fractional width in the 25 checked-in previews of the reference
#: bundle, so any other choice rewrites all of them on the first machine cut. A value with
#: sub-millisecond precision is REFUSED rather than truncated — a truncation that can make two
#: distinct values identical is the fabrication this whole tool exists to prevent.
FRACTION_DIGITS = 3

#: Written beside the previews. JSON and not YAML on purpose: the compiler's undefined-artifact
#: check enumerates YAML, so a YAML run record would need a schema definition before the bundle
#: could compile, and the console's sample globs key on `.csv`.
RUN_RECORD = "samples.run.json"

SUFFIX = {"sources": ".src.sample.csv", "datasets": ".sample.csv"}

#: Leading SQL line comments, and the `CREATE [OR REPLACE] VIEW|TABLE <name> AS` deployment wrapper.
_LEADING_COMMENTS = re.compile(r"\A(?:\s*--[^\n]*\n)+")
_VIEW_HEAD = re.compile(r"\Acreate\s+(?:or\s+replace\s+)?(?:view|table)\s+[^\s(]+\s+as\s+",
                        re.IGNORECASE)

#: EXPLICIT, per-process connector injection for the offline self-test — the same shape the
#: contract's own `client=` parameter has ("the injection seam the offline tests use"), one level up.
#: It is passed through to `registry.resolve(extra=...)`, which REFUSES to let it shadow a
#: first-party `mac.*` id, so a fixture cannot impersonate a shipped connector.
EXTRA_CONNECTORS = {}


class SampleRefused(Exception):
    """This preview cannot be derived. Carries the exit code the refusal deserves."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class SampleRenderError(SampleRefused):
    """A value the pinned render table has no rule for. Never rendered by a blanket str()."""


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE RENDER TABLE — pure. No engine, no driver, no file. This is the half a fixture can mutate.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _fraction(micro: int, where: str) -> str:
    if micro % 1000:
        raise SampleRenderError(
            f"{where}: the value carries sub-millisecond precision ({micro} microseconds) and the "
            f"pinned preview shape has {FRACTION_DIGITS} fractional digits. Truncating it could "
            f"make two distinct values identical in the file, so this relation is NOT cut",
            1)
    return ".%03d" % (micro // 1000)


def cell(v, where: str = "") -> str:
    """ONE value -> its pinned text. Dispatches on the RUNTIME type, never on a declared type name.

    Declared type names cannot drive this: the two bundles in scope spell the same types differently
    (`string`/`varchar`, `int`/`integer`, `array(string)`/`varchar[]`), so a renderer keyed on them
    would be keyed on a vocabulary neither engine owns.
    """
    if v is None:
        return ""
    # bool BEFORE int: isinstance(True, int) is True, and `1` is not `true`.
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, Decimal):
        # format(..., "f") and never float(): the engine's scale is part of the value
        # (`375.97600` stays `375.97600`) and a float round-trip is a silent loss.
        return format(v, "f")
    if isinstance(v, float):
        return repr(v)                      # shortest round-tripping since 3.1; per-bit stable
    if isinstance(v, datetime.datetime):    # BEFORE date: a datetime IS a date
        out = ("%04d-%02d-%02d %02d:%02d:%02d" % (v.year, v.month, v.day, v.hour, v.minute,
                                                  v.second)) + _fraction(v.microsecond, where)
        return out + (v.strftime("%z") if v.tzinfo is not None else "")
    if isinstance(v, datetime.date):
        return "%04d-%02d-%02d" % (v.year, v.month, v.day)
    if isinstance(v, datetime.time):
        out = ("%02d:%02d:%02d" % (v.hour, v.minute, v.second)) + _fraction(v.microsecond, where)
        return out + (v.strftime("%z") if v.tzinfo is not None else "")
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(cell(m, where) for m in v) + "]"
    if isinstance(v, (bytes, bytearray, memoryview)):
        # hex, never decode(errors="replace") — a replacement character is an invented value.
        return "0x" + bytes(v).hex()
    if isinstance(v, str):
        return v                            # verbatim; the dialect handles , " and newlines
    raise SampleRenderError(
        f"{where}: no render rule for a value of type {type(v).__name__}. A blanket str() is how "
        f"'<Row object at 0x...>' lands in a committed file and churns on every run",
        1)


def render_sample(columns, rows) -> bytes:
    """(header, positional rows) -> the preview's exact bytes. PURE.

    THE DIALECT IS PINNED and it is Python's `excel` dialect in UTF-8 with no BOM: delimiter `,`,
    quotechar `"`, doublequote, QUOTE_MINIMAL, CRLF after EVERY record including the last. Measured:
    re-emitting each of the reference bundle's 25 checked-in previews from its own parsed records
    reproduces it byte-for-byte, 25/25 — so the pinned dialect costs ZERO churn on the files that
    are already sound. Deliberately NOT the engine's own CSV writer: one engine's COPY emits LF and
    renders the empty string as `""`, so delegating would rewrite every file and re-diverge per
    engine.

    ROWS ARE KEYED BY POSITION, never by the descriptor's spelling of a column: the projection was
    rendered from `columns` in order, so result column i IS descriptor column i on every engine,
    while identifier folding differs between engines and the descriptors are mixed case.
    """
    out = []
    for r_i, row in enumerate(rows):
        vals = list(row)
        if len(vals) != len(columns):
            raise SampleRefused(
                f"row {r_i} carries {len(vals)} value(s) for a header of {len(columns)}; the file "
                f"would not be the shape it claims", 1)
        out.append(tuple(cell(v, f"row {r_i}, column {columns[i]!r}") for i, v in enumerate(vals)))
    # SORTED AFTER RENDERING, never before: sorting native values needs cross-type comparison
    # (None vs str, Decimal vs int) and raises, while sorting rendered text always compares — and
    # the text is what the byte guarantee is about.
    out.sort()
    buf = io.StringIO(newline="")
    w = csv.writer(buf, dialect="excel")
    w.writerow(list(columns))
    for r in out:
        w.writerow(list(r))
    return buf.getvalue().encode("utf-8", "strict")


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE PLAN — pure. Reads the bundle's YAML and nothing else. No engine, no network, no write.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

class SampleTarget:
    """One preview to cut. Every field is a function of the bundle's declarations."""

    # `ref` and `select_body_used` are set by the seam just before the statement is rendered: the
    # PLAN cannot know whether the relation exists, and the RENDERER must not go and find out.
    __slots__ = ("kind", "stem", "out_path", "columns", "schema", "relation_name", "relation",
                 "select_body", "order_by", "notes", "ref", "select_body_used")

    def __init__(self, kind, stem, out_path, columns, schema, relation_name, relation,
                 select_body, order_by, notes):
        self.kind = kind                      # "sources" | "datasets"
        self.stem = stem                      # the DESCRIPTOR FILE stem — the only name the file is keyed by
        self.out_path = out_path              # data/samples/<stem>[.src].sample.csv
        self.columns = tuple(columns)         # descriptor columns[] in document order == the header
        self.schema = schema
        self.relation_name = relation_name
        self.relation = relation              # "<schema>.<name>"
        self.select_body = select_body        # a dataset's transform body, when it has one
        self.order_by = tuple(order_by)
        self.notes = tuple(notes)
        self.ref = None
        self.select_body_used = False

    def as_dict(self) -> dict:
        return {"kind": self.kind, "stem": self.stem, "file": self.out_path,
                "relation": self.relation, "columns": list(self.columns),
                "order_by": list(self.order_by), "notes": list(self.notes)}


def columns_of(descriptor) -> list:
    """`columns[].name` in document order, or a refusal. The header's identity is derived HERE.

    Case-insensitive on the duplicate check because an engine may normalise an output name to the
    RELATION's case, so ['A','a'] can come back as ('A','A') and a positional header would then
    claim two columns that are one.
    """
    raw = descriptor.get("columns") or []
    names = [c.get("name") if isinstance(c, dict) else c for c in raw]
    if not names or any(not isinstance(n, str) or not n.strip() for n in names):
        raise SampleRefused("descriptor columns[] is empty or has an entry with no name; the "
                            "expected header would be [] and every measured column would read as "
                            "EXTRA", 1)
    dup = [n for n, k in Counter(n.lower() for n in names).items() if k > 1]
    if dup:
        raise SampleRefused(
            f"descriptor declares {sorted(dup)} more than once (case-insensitively); a header with "
            f"a repeated name is not the descriptor's columns[]", 1)
    return [str(n) for n in names]


def _table_of(descriptor, stem: str):
    t = descriptor.get("table") or {}
    name, schema = t.get("name"), t.get("schema")
    if not name:
        raise SampleRefused(f"{stem}: descriptor declares no table.name", 1)
    if not schema:
        raise SampleRefused(
            f"{stem}: descriptor table.name={name!r} declares no table.schema. An unqualified read "
            f"resolves through the engine's search path and would attribute real rows to a relation "
            f"the descriptor never named — the one shape of fabricated evidence this tool must not "
            f"be able to produce", 1)
    return str(schema), str(name)


def _strip_view_wrapper(sql: str) -> str:
    """A transform's `.sql` body with its `CREATE OR REPLACE VIEW <x> AS` head and trailing `;` off.

    The DDL head is the transform's DEPLOYMENT wrapper; the SELECT under it is what the view would
    serve. Leading line comments are dropped first, for the same reason `SqlConnector.head_verb`
    drops them — a statement that begins `-- built by ...\nCREATE ...` is a CREATE, and a check that
    called it `--` would reject the correct pattern (measured: every transform in the bundle this
    landed against opens with a comment block).

    It REFUSES rather than guesses: a body that is neither a CREATE ... AS nor a SELECT/WITH is not
    something to wrap in a subquery, and wrapping it anyway is how a preview ends up previewing
    something nobody declared.
    """
    text = _LEADING_COMMENTS.sub("", sql).strip()
    m = _VIEW_HEAD.match(text)
    if m:
        text = text[m.end():].strip()
    while text.endswith(";"):
        text = text[:-1].rstrip()
    if not _LEADING_COMMENTS.sub("", text).strip().lower().lstrip("( \n").startswith(
            ("select", "with")):
        raise SampleRefused("the transform body is not a SELECT (or WITH) after the view wrapper "
                            "was cut; refusing to wrap it as a subquery", 1)
    return text


def plan_samples(root: Path, *, planes=("sources", "datasets"), stems=None):
    """(targets, findings). PURE: reads only the bundle's YAML. Nothing is opened and nothing written.

    A SOURCE's relation is `table.schema`.`table.name` and NOTHING ELSE — in particular never
    `metadata.table`, which on 9 of the reference bundle's 13 dataset descriptors holds the UPSTREAM
    RAW name. A deriver that read it would sample the raw relation and write the bytes under the
    served stem: a fabrication that looks entirely plausible in the console.

    A DATASET's relation is the TRANSFORM's `produces.relation`; on disagreement with
    `table.schema`.`table.name` this FAILS with a finding rather than choosing a winner. The
    transform is reached through `derived_from.pipeline` when declared and through the descriptor
    stem otherwise — which is the normal path (it is absent on all 6 datasets of the bundle this
    landed against), so the stem fallback is stated rather than silent.
    """
    targets, findings = [], []
    dirs = {"sources": root / "data" / "sources", "datasets": root / "data" / "datasets"}
    wanted = set(stems) if stems else None
    seen_stems = set()
    for kind in planes:
        d = dirs[kind]
        for f in sorted(glob.glob(str(d / "*.yaml"))):
            p = Path(f)
            stem = p.stem
            if wanted is not None and stem not in wanted:
                continue
            seen_stems.add(stem)
            notes = []
            try:
                doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                cols = columns_of(doc)
                schema, rel_name = _table_of(doc, stem)
                relation = f"{schema}.{rel_name}"
                body = None
                if kind == "datasets":
                    body, relation, extra = _dataset_relation(root, stem, doc, relation)
                    notes.extend(extra)
                    schema, _, rel_name = relation.partition(".")
                meta_tbl = (doc.get("metadata") or {}).get("table")
                if meta_tbl and str(meta_tbl) != rel_name:
                    notes.append(f"metadata.table={meta_tbl!r} differs from table.name={rel_name!r}; "
                                 f"the relation read is table.name, never metadata.table")
            except SampleRefused as exc:
                findings.append({"kind": kind, "stem": stem, "file": str(p.relative_to(root)),
                                 "class": "PLAN_REFUSED", "detail": str(exc),
                                 "exit": exc.exit_code})
                continue
            targets.append(SampleTarget(
                kind=kind, stem=stem,
                out_path=f"data/samples/{stem}{SUFFIX[kind]}",
                columns=cols, schema=schema, relation_name=rel_name, relation=relation,
                select_body=body,
                # THE TOTAL ORDER: every declared column, in descriptor order. Not the declared key:
                # its uniqueness is a CLAIM this tool cannot verify, and a declared-but-non-unique
                # key leaves the 20/21 boundary engine-arbitrary while the Python re-sort HIDES the
                # churn instead of showing it. Appending the rest costs nothing and removes the
                # dependency.
                order_by=cols, notes=notes))
    if wanted is not None:
        for miss in sorted(wanted - seen_stems):
            findings.append({"kind": "?", "stem": miss, "file": "", "class": "NO_SUCH_STEM",
                             "detail": f"--stems named {miss!r}, which no descriptor under "
                                       f"{', '.join(str(dirs[k]) for k in planes)} declares",
                             "exit": 1})
    return tuple(targets), findings


def _dataset_relation(root: Path, stem: str, doc, from_table: str):
    """(select_body, relation, notes) for a dataset. The transform is the authority on the relation."""
    notes = []
    pipeline = ((doc.get("derived_from") or {}).get("pipeline")) if isinstance(
        doc.get("derived_from"), dict) else None
    tpath = root / "data" / "transforms" / f"{pipeline or stem}.yaml"
    if not pipeline:
        notes.append("transform reached by descriptor stem (derived_from.pipeline is not declared)")
    if not tpath.is_file():
        return None, from_table, notes + ["no transform descriptor; relation read from table.*"]
    tdoc = yaml.safe_load(tpath.read_text(encoding="utf-8")) or {}
    produces = tdoc.get("produces") or {}
    declared = produces.get("relation")
    if declared and str(declared) != from_table:
        raise SampleRefused(
            f"{stem}: the transform declares produces.relation={declared!r} and the descriptor "
            f"declares table.schema.table.name={from_table!r}. Two homes for one relation name "
            f"disagree — this tool will not choose which is the served relation", 1)
    relation = str(declared or from_table)
    if relation.rpartition(".")[2] != stem:
        notes.append(f"produces.relation tail {relation.rpartition('.')[2]!r} is not the descriptor "
                     f"stem {stem!r}; the preview file is keyed by the STEM")
    body = None
    sql_rel = produces.get("sql_file")
    if sql_rel:
        sp = root / str(sql_rel)
        if sp.is_file():
            body = _strip_view_wrapper(sp.read_text(encoding="utf-8"))
        else:
            notes.append(f"produces.sql_file names {sql_rel!r}, which is not there")
    return body, relation, notes


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE SEAM — bundle root -> a constructed connector -> one read. The one place anything is opened.
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def open_reader(root: Path, *, extra=None, client=None):
    """bundle root -> a constructed Connector. Constructs nothing else and opens nothing.

    This is the probe subprocess's own sequence with `.probe()` removed — read
    `mac.project.yaml#runtime.connector` + `runtime.connection`, resolve through the registry,
    split `validate_config` findings into BLOCKING and ADVISORY, and ask
    `inspect.signature(cls.__init__)` whether the connector takes a `base_dir` before passing one
    (passing it to a connector that does not take it is a TypeError at construction). It is NOT a
    second, divergent opener, and it deliberately does NOT use `yaml.safe_load` on connection.yaml:
    the overlay chain ($DEPLOYMENT_CONFIG, connection.local.yaml) is where a gitignored credential
    handle lives, and a bare load would hand the connector a config missing the one load-bearing
    key. Measured harmless where no overlay exists: the same mapping, 0 config findings either way.

    It does NOT go through the harvest CLI, which is hardwired to one cloud catalog and cannot reach
    a local-file bundle at all. That defect is the reason this whole family had no producer.
    """
    import inspect

    from sdk.connector import registry
    from sdk.connector.base import ConnectorError

    mf = root / "mac.project.yaml"
    if not mf.is_file():
        raise SampleRefused(f"no mac.project.yaml at {root}", 2)
    m = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
    rt = m.get("runtime") or {}
    cid = rt.get("connector")
    if not cid:
        raise SampleRefused(f"{root.name}: the bundle declares no runtime.connector, so there is "
                            f"nothing to derive a preview FROM", 2)
    conn_rel = rt.get("connection")
    if not conn_rel:
        raise SampleRefused(f"{cid} is declared but no runtime.connection names its config", 1)
    if not (root / str(conn_rel)).is_file():
        raise SampleRefused(f"runtime.connection names {conn_rel!r}, which is not there", 1)
    from sdk.authoring.connection import load_connection

    conn = load_connection(root)
    try:
        cls = registry.resolve(cid, extra=extra or EXTRA_CONNECTORS or None)
    except ConnectorError as exc:
        from sdk.connector.base import exit_code_for
        raise SampleRefused(f"{cid}: {exc}", exit_code_for(exc)) from exc
    if cls is None:
        raise SampleRefused(f"{cid} is not installed on this host", 2)
    findings = list(cls.validate_config(conn)) if hasattr(cls, "validate_config") else []
    blocking = [e for e in findings if getattr(e, "blocking", True)]
    advisories = [str(e) for e in findings if not getattr(e, "blocking", True)]
    if blocking:
        raise SampleRefused(f"{cid}: the config does not validate: "
                            + "; ".join(getattr(e, "message", str(e)) for e in blocking[:3]), 1)
    kwargs = {}
    try:
        if "base_dir" in inspect.signature(cls.__init__).parameters:
            kwargs["base_dir"] = root
    except (TypeError, ValueError):                                             # pragma: no cover
        pass
    if client is not None:
        kwargs["client"] = client
    return cls(conn, **kwargs), advisories


def render_body(conn, target: SampleTarget, *, limit: int = 20) -> str:
    """The exact statement this tool would run. PURE — no driver, no socket. Printed by --dry-run.

    `LIMIT limit + 1` is in the STATEMENT so the ENGINE bounds the scan (one connector applies
    ReadRequest.limit client-side, after paging a completed query, so the statement itself would be
    unbounded), and `ReadRequest.limit` is set too so `truncated` is decided by a fetched row rather
    than guessed from `len(rows) == limit`. Both, or one of the two facts is wrong.
    """
    sel = ", ".join(conn.quote_identifier(c) for c in target.columns)
    ordr = ", ".join(conn.quote_identifier(c) + " ASC NULLS LAST" for c in target.order_by)
    if not ordr:
        raise SampleRefused(f"{target.relation}: no ordering columns, so the window would be "
                            f"whatever the engine returned; a churning file is worse than none", 1)
    src = f"({target.select_body}) t" if target.select_body_used else conn.qualify(target.ref)
    return f"SELECT {sel} FROM {src} ORDER BY {ordr} LIMIT {limit + 1}"


def _ref(target: SampleTarget):
    from sdk.connector import RelationRef
    return RelationRef(namespace=(target.schema,), name=target.relation_name)


def relation_exists(conn, target: SampleTarget):
    """(exists, measured_columns_or_None). Uses the catalog verb only when the connector has one."""
    from sdk.connector.base import AdapterError

    if "describe_relation" not in conn.supports:
        return None, None
    try:
        schema = conn.describe_relation(_ref(target))
    except AdapterError:
        return False, None
    measured = [c.name for c in schema.columns]
    if not measured:
        # A catalog that answers with ZERO columns has not measured the descriptor; it is a catalog
        # holding no column metadata. Judging the bundle on an empty denominator is the same defect
        # as a PASS over zero files, so this is could-not-run and NOT a finding about the bundle.
        raise SampleRefused(
            f"{target.relation}: {conn.id}'s catalog returned ZERO columns for this relation. That "
            f"is not a measurement of the descriptor — refusing to judge the bundle on an empty "
            f"denominator", 2)
    return True, measured


def fetch_sample(conn, target: SampleTarget, *, limit: int = 20):
    """<=limit REAL rows of the declared projection. Returns (ReadResult, statement, provenance).

    Refuses rather than handing back anything a wrong file could be built from.
    """
    from sdk.connector import bind
    from sdk.connector.base import ConnectorError, exit_code_for
    from sdk.connector.sql import SqlConnector

    if not isinstance(conn, SqlConnector):
        raise SampleRefused(
            f"{conn.id}: a preview body is the connector's to render and this contract has no "
            f"preview verb for a non-statement source; no preview derived", 2)

    exists, measured = relation_exists(conn, target)
    provenance = "relation"
    if exists is False:
        if not target.select_body:
            raise SampleRefused(
                f"{target.relation}: the relation does not exist and the bundle declares no "
                f"transform body to read instead. NOT cut. This tool reads the relation the "
                f"descriptor NAMES and never a similarly-named one — sampling a leftover view and "
                f"labelling it with this descriptor's stem is the fabrication it exists to prevent",
                1)
        provenance = "transform-body"
    elif exists is True:
        folded = set(m.casefold() for m in measured)
        unknown = [c for c in target.columns if c.casefold() not in folded]
        declared = set(c.casefold() for c in target.columns)
        extra = [m for m in measured if m.casefold() not in declared]
        if unknown or extra:
            bits = []
            if unknown:
                bits.append(f"the descriptor declares {unknown} which the relation does not have")
            if extra:
                bits.append(f"the relation has {extra} which the descriptor does not declare")
            raise SampleRefused(
                f"{target.relation}: " + "; and ".join(bits)
                + f" (measured {len(measured)} column(s) over namespace {target.schema!r}, declared "
                  f"{len(target.columns)}). NOT cut: a disagreement between a descriptor and its "
                  f"relation is a finding, not something to paper over", 1)

    target.select_body_used = provenance == "transform-body"
    target.ref = _ref(target)
    body = render_body(conn, target, limit=limit)
    try:
        res = conn.read(bind(body, params={}, user_values=(), limit=limit, purpose="sample"))
    except ConnectorError as exc:
        raise SampleRefused(f"{target.relation}: {exc}", exit_code_for(exc)) from exc
    if [c.casefold() for c in res.columns] != [c.casefold() for c in target.columns]:
        raise SampleRefused(
            f"{target.relation}: the engine returned columns {list(res.columns)} for a projection "
            f"of {list(target.columns)}; the header would not be the descriptor's", 1)
    if res.row_count == 0:
        raise SampleRefused(
            f"{target.relation}: the relation returned 0 rows. A zero-row preview is a header with "
            f"no evidence under it — NOT cut", 1)
    return res, body, provenance


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE CONCEPT DRAW — a SEEDED RANDOM sample of A CONCEPT'S OWN MEMBERS, at the columns it declares
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# WHY A SECOND DRAW RATHER THAN A SECOND TOOL. Everything above previews a RELATION: the descriptor
# names the columns, the whole table is the population, and the window is the lexicographically
# smallest rows so the file is reproducible. A concept page needs something the relation preview
# cannot be, on two counts measured on a live bundle of 17 concepts:
#
#   1. THE POPULATION IS NOT THE RELATION. 4 of those 17 concepts co-inhabit ONE host relation; a
#      window of that table is the HOST's preview under four different titles. A concept already
#      declares which rows are its own — `grounding.discriminator`, or `grounding.value_filter`
#      where declared — and that declaration is read here through the SAME function the ontology
#      test generator narrows its identity family with (`member_population`), imported rather than
#      restated, because two spellings of "which rows are this concept's" is how they come to
#      disagree.
#   2. THE COLUMNS ARE NOT THE RELATION'S. A concept page's Fields table is the UNION of
#      `grounding.sources[].columns` and `grounding.field_roles` — measured on that bundle, 116
#      field_role assignments against 117 union rows, the one difference being a grounded column
#      that carries no role. Narrowing a sample to `field_roles` would drop that column while the
#      table directly above it still lists it: two surfaces of one page disagreeing about what the
#      concept declares. So the columns come from `_grounding_fields` — the FUNCTION the page builds
#      its table from — and never from a second derivation of the same set.
#
# AND THE WINDOW IS NOT THE LEXICOGRAPHIC HEAD. The relation preview's total order is right for a
# header-drift check and wrong for a reader: measured, one bundle's store preview is its two
# lowest-numbered keys and never a null and never the tail. The operator's ruling was SEEDED RANDOM
# — statistically representative AND reproducible — so a page diffs only when the DATA moves.
#
# HOW THE SEED BUYS REPRODUCIBILITY WITHOUT AN RNG. An engine's `setseed`/`USING SAMPLE` is NOT a
# contract: it is not promised stable across engine versions, it is not promised across engines, and
# nothing in this estate can check it. So the draw is NOT an RNG. It is a stable pseudo-random TOTAL
# ORDER over the row's own declared values:
#
#     ORDER BY md5('<seed>' || '|' || coalesce(CAST(c1 AS VARCHAR),'') || '|' || ...) ASC,
#              c1 ASC NULLS LAST, ..., cn ASC NULLS LAST
#
# — a pure function of (seed, the row's declared cells), with the relation preview's own total order
# appended so that two rows identical across every declared column cannot leave the boundary
# engine-arbitrary. THE HONEST LIMIT, stated rather than hidden: `md5` is a fixed function and its
# input here is not — `CAST(x AS VARCHAR)` is the engine's rendering, and two engines may spell one
# timestamp's sub-second tail differently. So the claim is the same one the relation preview already
# makes about its bytes: REPRODUCIBLE PER ENGINE ACROSS RUNS AND VERSIONS, and cross-engine only
# where the cast agrees. That is strictly stronger than an RNG, which is reproducible across
# neither, and the run record names the engine that drew each file.
#
# WHAT A MEMBER IS, AND WHY IT IS DECLARED AND NOT GUESSED. Two shapes, told apart by the concept's
# OWN declaration and recorded per sample:
#   · ROW GRAIN (the default) — a member is a row of the host that the concept claims. An
#     enumeration held inside a dimension is this shape: its sample is the rows carrying a value,
#     measured on that bundle at 15 of a 74-row host.
#   · KEY GRAIN — a concept that declares a `members:` block declares that its members ARE the
#     distinct values of its canonical key, so a window of host rows would again be the host's
#     preview. Its sample is ONE REPRESENTATIVE ROW PER MEMBER, the representative chosen by the
#     same seeded order. Measured: 4 of 17 concepts, one at 11 members over 2 517 host rows.
# A key-grain draw needs the canonical key AMONG the columns the page shows, or the collapse is
# invisible to the reader; where it is not, the draw falls back to row grain AND SAYS SO.
#
# ONE BLOCK PER GROUNDING SOURCE, AND EVERY SOURCE IS DRAWN, because 3 of those 17 concepts ground
# on TWO relations and their Fields table spans both — the second relation's columns are not columns
# of the first, so no single projection can carry the table's rows. Each block carries that source's
# share of the table, in the TABLE'S OWN ORDER, with its OWN population, its OWN predicate and its
# OWN denominators; the blocks' columns concatenated and deduplicated are the table exactly.
# A Fields row belonging to NO source (a `field_roles` key under no `sources[].columns`) would break
# that identity, so it is a REFUSAL naming the column — measured 0 of 117 on that bundle.
#
# DRAWING EVERY SOURCE IS NOT MERELY COMPLETENESS. Measured on one bundle: a Country concept whose
# two sources carry 8 and 9 distinct country values, the ninth being a sentinel one relation has and
# the other does not. One block plus a note saying "2 columns cannot be in a projection of this one"
# states a fact about the PROJECTION and hides a fact about the DATA. Two blocks side by side state
# both. Nothing here editorialises that difference: each block is drawn truthfully and the reader
# sees the two populations next to each other.
#
# DISCLOSURE IS THE BUNDLE'S CALL AND IT FAILS CLOSED. `publish.samples.disclosure: published` in
# the manifest is the ONLY thing that lets rows reach disk; absent, unreadable or misspelled means
# WITHHELD. A withheld concept is still MEASURED and still recorded — predicate, grain, population,
# denominators — so the page can say a sample exists, is withheld, and how many members it has,
# which is the one thing a silently absent section cannot say.

#: THE PLANE LABEL in the run record's `samples[]`, and NOT a directory any more. Kept as the word
#: `concepts` because it is the CONSUMER's key (the console filters `kind === "concepts"`), and
#: renaming a wire field to match a filesystem move would break a reader to tidy a producer.
CONCEPT_KIND = "concepts"

#: WHERE A CONCEPT SAMPLE LIVES: `<ontology plane>/samples/<stem>.sample.csv`, and the operator's
#: ruling is structural rather than cosmetic. `data/` is the DATA plane — parquet, sources, datasets,
#: profiles, transforms, references, lookups, quality, and the RELATION previews this same tool cuts
#: at `data/samples/<stem>.sample.csv`, which do not move. A CONCEPT sample is an ONTOLOGY artifact:
#: its population is defined by the concept's `grounding.discriminator` / `value_filter` and its
#: columns by the concept's own declarations, so nothing in the data plane can say what it is.
#: The old home was `data/samples/concepts/` — a SUBDIRECTORY chosen only so the descriptor gate,
#: which globs `data/samples/*.csv`, would not read a concept sample as an ORPHAN preview of no
#: descriptor. That was a workaround for being in the wrong plane; out of `data/` the problem is
#: gone rather than dodged.
CONCEPT_SAMPLE_DIR = "samples"           # relative to the ontology plane the manifest declares
CONCEPT_SUFFIX = ".sample.csv"
DEFAULT_CONCEPT_LIMIT = 40
DEFAULT_SEED = "mac.sample.concept/1"
PUBLISHED, WITHHELD = "published", "withheld"
_RN = "mac_member_rn"
_MK = "mac_member_key"

#: THE CEILING ON MATERIALISING THE DATA'S OWN MEMBER LIST, which is read ONLY to answer one
#: question: which DECLARED member has no row? A concept that declares members declares a SET — a
#: register or an enumeration — so this is measured in tens on every concept in the estate (2 to 32
#: over 7 member-declaring concepts). The ceiling exists because `members:` on a high-cardinality
#: key is legal and would otherwise pull a column of the warehouse into memory to answer a question
#: about absence. Past it the list is NOT materialised and NO member is called absent — the record
#: says so, in those words, rather than reporting an empty absence it did not measure.
MEMBER_LIST_MAX = 10_000

#: The seed reaches the statement as a SQL literal, so its charset is closed rather than escaped.
#: A closed charset removes the question a quote-doubling escape only answers by argument.
_SEED_OK = re.compile(r"\A[A-Za-z0-9._:/+@-]{1,64}\Z")


def _ontology_plane(root: Path) -> Path:
    """The ontology plane's directory, from the manifest's own `planes.ontology`.

    Through the shared resolver, so the concept draw reads the plane from the SAME place every
    other tool does; the literal fallback is only for a bundle the resolver cannot read, and it is
    the conventional path rather than a second declaration."""
    try:
        from mac_project import resolve
        onto = getattr(resolve(str(root)), "ontology", None)
        if onto:
            return Path(onto)
    except Exception:                                                          # pragma: no cover
        pass
    return root / "ontology"


def concept_sample_dir(root: Path, ontology: Path | None = None) -> str:
    """`<ontology plane>/samples`, POSIX, RELATIVE TO THE BUNDLE ROOT — one home for the path.

    Through the plane the MANIFEST declares and never the literal `ontology/`: a bundle may move
    its ontology plane, and a writer that hard-coded the conventional spelling would drop the cuts
    beside a directory that is not the ontology. `relative_to` is the only step that can fail (a
    plane outside the root, which nothing in the estate does); the conventional path is the
    fallback so a writer still has somewhere honest to put the file.
    """
    onto = ontology if ontology is not None else _ontology_plane(root)
    try:
        rel = Path(onto).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:                                                         # pragma: no cover
        rel = "ontology"
    rel = "" if rel == "." else rel
    return f"{rel}/{CONCEPT_SAMPLE_DIR}" if rel else CONCEPT_SAMPLE_DIR


def _lookups_dir(root: Path) -> Path:
    """`<data plane>/lookups` — where a register binding's BARE filename resolves.

    Through the manifest's own `planes.data` and not the literal `data/`, for the reason
    `_ontology_plane` gives above: a bundle may move its planes, and a reader that hard-coded the
    conventional spelling would look for the register beside a directory that is not the data.
    """
    try:
        m = yaml.safe_load((root / "mac.project.yaml").read_text(encoding="utf-8")) or {}
        data = ((m or {}).get("planes") or {}).get("data") or "data"
    except (OSError, yaml.YAMLError, AttributeError):                          # pragma: no cover
        data = "data"
    return root / str(data) / "lookups"


def _register_rows(root: Path, spec: str):
    """(rows, path) for the register a `realized_by` binding names, or (None, the paths tried).

    TWO SPELLINGS ARE IN USE IN ONE BUNDLE and neither is wrong: an enumeration binds
    `register: contoso_currency.lookup.csv` (a bare filename, resolved in the lookups directory) and
    a grouping binds `register: data/lookups/dim_contoso_product.lookup.csv` (a path from the bundle
    root). Both are tried, root-relative first, and the failure names both so a reader is not left
    guessing which spelling this reader wanted.
    """
    tried = [root / spec, _lookups_dir(root) / Path(spec).name]
    for p in tried:
        try:
            if p.is_file():
                with p.open(newline="", encoding="utf-8") as fh:
                    return list(csv.DictReader(fh)), p
        except OSError:                                                        # pragma: no cover
            continue
    return None, tried


def declared_members(root: Path, doc: dict):
    """THE MEMBER LIST THE CONCEPT DECLARES — the LEFT side of the outer join — or WHY there is none.

    (codes, basis) in DECLARATION order, or (None, why). This is the half of the draw that the data
    cannot supply: a register may declare a code the warehouse never carries, and the whole reason
    the draw is an outer join rather than a `GROUP BY` is that such a member must be VISIBLE rather
    than silently absent. Without this list "every member appears" degenerates to "every member the
    data already has appears", which is not a claim about the ontology at all.

    FOUR DECLARATION SHAPES, all of them already in use, read in the order a concept means them:
      · `values.items[].code` — an enumeration that lists its members inline. Measured: 1 of 7.
      · `members.definitions[].code` — a grouping that names its member sets inline. Measured: 0 of
        7 in this estate, and deliberately so (every grouping delegates), but it is the schema's
        own shape and a reader that skipped it would drop a legal declaration.
      · `values.realized_by` with a register + `key_column` — an enumeration that delegates, so the
        codes have ONE home. Measured: 2 of 7.
      · `members.realized_by` with a register + `group_key` — a grouping whose member sets are the
        distinct groups of an already-exploded register. Measured: 4 of 7.

    A BLANK IS NOT A MEMBER and is dropped: one register in this estate carries a sentinel row whose
    group key is empty (a store version with no continent), and minting `''` as a sixteenth member
    would put a value in the ontology that the concept never declared.

    THE FAILURE IS NAMED, NEVER SWALLOWED. A binding whose register is missing, or whose column the
    register does not carry, returns (None, why) — and a None member list makes absence UNDECIDABLE
    rather than empty. "No member is absent" and "I could not check" are different sentences and
    this tool exists to keep them apart.
    """
    vals = doc.get("values") if isinstance(doc.get("values"), dict) else {}
    mems = doc.get("members") if isinstance(doc.get("members"), dict) else {}
    for blk, where, key in ((vals, "values.items", "items"),
                            (mems, "members.definitions", "definitions")):
        rows = blk.get(key)
        if not isinstance(rows, list) or not rows:
            continue
        codes = [r.get("code") for r in rows
                 if isinstance(r, dict) and r.get("code") not in (None, "")]
        if codes:
            return tuple(codes), f"{where} — {len(codes)} member(s) enumerated in the concept itself"
    for blk, where, cols in ((vals, "values.realized_by", ("key_column", "code_column", "column")),
                             (mems, "members.realized_by", ("group_key", "key_column", "column"))):
        rb = blk.get("realized_by")
        rb = rb[0] if isinstance(rb, list) and rb else rb
        if not isinstance(rb, dict):
            continue
        params = rb.get("params") if isinstance(rb.get("params"), dict) else {}
        spec = str(params.get("register") or "").strip()
        col = next((str(params[k]) for k in cols if params.get(k)), "")
        if not spec or not col:
            continue
        rows, tried = _register_rows(root, spec)
        if rows is None:
            return None, (f"{where}.params.register names {spec!r}, which is not a file — tried "
                          f"{', '.join(str(x) for x in tried)}. The declared member list could not "
                          f"be read, so NO member can be called absent")
        if rows and col not in rows[0]:
            return None, (f"{where}.params names the column {col!r}, which {spec} does not carry "
                          f"(it has {sorted(rows[0])}). The declared member list could not be read, "
                          f"so NO member can be called absent")
        seen, codes = set(), []
        for rw in rows:
            v = str(rw.get(col) or "").strip()
            if v and v not in seen:
                seen.add(v)
                codes.append(v)
        if codes:
            return tuple(codes), (f"{where} ({rb.get('udf') or 'a register binding'}) — "
                                  f"{len(codes)} distinct `{col}` over {len(rows)} row(s) of "
                                  f"{spec}")
    return None, ("the concept declares members but ENUMERATES none of them — no values.items, no "
                  "members.definitions and no register binding — so the member list is whatever "
                  "the data carries and no declared member can be missing from it")


def _mkey(v) -> str:
    """ONE member value's comparison key — the declaration's spelling folded onto the engine's.

    Through `cell` and not `str`, so the two sides are compared in the SAME rendering the CSV uses:
    a register holds the text `20` and DuckDB returns the integer `20`, and `str(Decimal('20'))` and
    `str(20)` are already two answers. Casefolded and stripped because a register's `Closed` and an
    engine's `CLOSED` are one member — a case difference would report a member both PRESENT and
    ABSENT, which is the one answer that is certainly wrong.
    """
    return cell(v).strip().casefold()


def disclosure_of(root: Path):
    """(mode, declared_seed, basis) — `disclosure.samples` from the manifest, FAIL-CLOSED.

    ONE HOME, AND IT IS NOT THIS FILE. The key, its `publish is True` strictness and its default
    are the PAGE's (`sdk/project/mac_okf.py#disclosure_samples`), which is where the rows actually
    become public; this reader exists so the tool that goes to the warehouse obeys the same line
    rather than drawing under a second policy of its own. `is True` and not truthiness is copied
    deliberately: `publish: "no"` is a truthy string, and a disclosure gate a typo can open is not
    a gate.
    """
    mf = root / "mac.project.yaml"
    try:
        m = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return WITHHELD, None, (f"mac.project.yaml could not be read "
                                f"({exc.__class__.__name__}); a bundle that cannot say withholds")
    d = (m or {}).get("disclosure")
    blk = d.get("samples") if isinstance(d, dict) else None
    if not isinstance(blk, dict):
        return WITHHELD, None, ("the manifest declares no disclosure.samples.publish, and the "
                                "default is WITHHELD — a bundle that says nothing withholds")
    seed = blk.get("seed")
    seed = str(seed) if seed not in (None, "") else None
    if blk.get("publish") is True:
        if not str(blk.get("reason") or "").strip():
            return WITHHELD, seed, ("disclosure.samples.publish is true but carries no `reason`; "
                                    "the schema requires a basis for publishing and an unargued "
                                    "opt-in withholds")
        return PUBLISHED, seed, "disclosure.samples.publish: true"
    return WITHHELD, seed, (f"disclosure.samples.publish is {blk.get('publish')!r}, and only the "
                            f"boolean true publishes")


class ConceptBlock:
    """One concept's sample over ONE of its grounding sources. Every field is a declaration."""

    __slots__ = ("stem", "concept", "klass", "relation", "schema", "relation_name", "columns",
                 "select_body", "member_where", "member_basis", "grain", "grain_basis",
                 "member_key", "count_key", "notes", "out_path", "ref", "select_body_used",
                 "source_index", "source_count", "fields_total", "fields_undrawn",
                 "declared", "declared_from")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))
        self.columns = tuple(self.columns or ())
        self.notes = list(self.notes or [])
        self.ref = None
        self.select_body_used = False


def concept_docs(root: Path, ontology: Path):
    """[(path, doc)] for every concept under the ontology plane, and the files that would not load.

    A file is a CONCEPT when it carries both a `concept:` mapping and a `grounding:` — the same two
    keys the page reads. Anything else under the directory (rule files, a register, an index) is not
    a concept and is not counted in any denominator here.
    """
    docs, bad = [], []
    for f in sorted(glob.glob(str(ontology / "concepts" / "**" / "*.yaml"), recursive=True)):
        p = Path(f)
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            bad.append((p, f"{exc.__class__.__name__}: {exc}"))
            continue
        if isinstance(doc, dict) and isinstance(doc.get("concept"), dict) and doc.get("grounding"):
            docs.append((p, doc))
    return docs, bad


def plan_concept_samples(root: Path, ontology: Path, dataset_targets, *, stems=None):
    """(blocks, findings). PURE: reads the bundle's YAML. Nothing is opened and nothing is written.

    The column set is `_grounding_fields(grounding)` — the concept page's OWN Fields-table builder,
    imported from the projection and never re-derived. The membership predicate is
    `member_population(...)` — the ontology test generator's OWN narrowing, likewise imported. Both
    are single-homed deliberately: a sample whose columns or whose population were computed a second
    time is a second opinion about what the concept declares, which is the defect class this whole
    family exists to remove.

    ONE BLOCK PER DECLARED GROUNDING SOURCE. A refusal on one source is a refusal of THAT SOURCE
    and not of the concept: the sources that can be drawn are still drawn, and the Fields-table
    rows the refused source owned are then reported as belonging to NO block, which is the only
    case in which `fields_undrawn` can be non-empty once every source is attempted.
    """
    from mac_generate_ontology_tests import column_types, member_population
    from sdk.project.mac_okf import _grounding_fields

    by_rel = {}
    for t in dataset_targets:
        by_rel.setdefault(t.relation.rpartition(".")[2].casefold(), t)
        by_rel.setdefault(t.stem.casefold(), t)
    out_dir = concept_sample_dir(root, ontology)

    blocks, findings = [], []
    docs, bad = concept_docs(root, ontology)
    for p, why in bad:
        findings.append({"stem": p.stem, "file": str(p.relative_to(root)), "class": "UNREADABLE",
                         "detail": why, "exit": 1})
    wanted = set(stems) if stems else None
    seen = set()
    for p, doc in docs:
        stem = p.stem
        seen.add(stem)
        if wanted is not None and stem not in wanted:
            continue
        c = doc.get("concept") or {}
        g = doc.get("grounding") or {}
        name = str(c.get("name") or stem)
        fields = _grounding_fields(g)
        if not fields:
            findings.append({"stem": stem, "file": str(p.relative_to(root)), "class": "NO_FIELDS",
                             "detail": f"{name}: the concept's Fields table would be EMPTY — "
                                       f"grounding declares neither sources[].columns nor "
                                       f"field_roles, so there is no column set to sample",
                             "exit": 1})
            continue
        homeless = [f["column"] for f in fields if not f["sources"]]
        if homeless:
            findings.append({
                "stem": stem, "file": str(p.relative_to(root)), "class": "UNPLACEABLE_FIELD",
                "detail": f"{name}: {len(homeless)} of {len(fields)} Fields-table row(s) "
                          f"{sorted(homeless)} carry a field_role but appear under no "
                          f"grounding.sources[].columns, so no source's sample can show them and "
                          f"the samples' columns could not be the table's rows. NOT drawn",
                "exit": 1})
            continue
        rel_order = []
        for s in g.get("sources") or []:
            if not isinstance(s, dict):
                continue
            rb = str(s.get("relation") or "").split(".")[-1]
            if rb and rb not in rel_order:
                rel_order.append(rb)
        ident = str((c.get("identity") or {}).get("canonical_key") or "").strip()
        # AN ONTOLOGY DECLARES MEMBERSHIP TWO WAYS AND THIS READ ONLY ONE OF THEM.
        #
        # A `members:` block is how a GROUPING says what it is a grouping OF — `over` the parent,
        # with the member source named. An `values:` block is how an ENUMERATION says the same
        # thing in its own idiom: a closure, and either the items inline or a register binding
        # (`mac.canon.enum_from_register`) so the member list has ONE home instead of two.
        # Different words, identical claim: THE EXTENSION OF THIS CONCEPT IS A SET OF VALUES, NOT
        # A SET OF ROWS.
        #
        # Reading only `members:` sent every enumeration to ROW grain, and the result was a sample
        # that answered a question nobody asked. Measured on one bundle: a 5-member currency code
        # set rendered 40 rows of the host fact table — every one of them the same pair — and a
        # 15-band age set rendered 40 customers. Both concepts declared a `canonical_key` the whole
        # time, so the member key was never missing; it was never looked for.
        #
        # CLOSURE IS NOT THE TEST. An `open` value set is still a value set: openness says the
        # enumerated list may be incomplete, not that the members are rows. One of the three
        # measured enumerations is open and it collapses like the other two.
        declares_members = isinstance(doc.get("members"), dict) or isinstance(doc.get("values"), dict)
        # THE DECLARED MEMBER LIST IS READ ONCE PER CONCEPT, not once per block: it is a property
        # of the CONCEPT (its values.items, its register binding), and the same list is the left
        # side of every one of its key-grain blocks. Read at PLAN time, from YAML and CSV only —
        # this half of the outer join costs no engine.
        c_declared, c_declared_from = ((None, "") if not declares_members
                                       else declared_members(root, doc))
        # ONE BLOCK PER GROUNDING SOURCE, ALL OF THEM. This loop used to be `rel_order[:1]` — one
        # block, from source 1, and a NOTE on the page naming the columns that "cannot be in a
        # projection of this one". The note was true and it hid the thing worth seeing: measured on
        # one bundle, a concept whose two sources carry 8 and 9 distinct values of the same
        # business idea, the ninth a sentinel only one relation has. A note about a projection
        # cannot say that; two blocks with their own counts say it without anyone editorialising.
        #
        # THE BLOCKS ARE PLANNED FIRST AND THE CONCEPT-LEVEL FACT IS COMPUTED AFTER, because
        # `fields_undrawn` is a statement about the WHOLE concept ("this Fields row is in no
        # block") and no single source can know it.
        planned, drawn_rels = [], []
        for i, rel_bare in enumerate(rel_order):
            cols = [f["column"] for f in fields
                    if any(r == rel_bare for r, _ in f["sources"])]
            host = by_rel.get(rel_bare.casefold())
            if host is None:
                findings.append({
                    "stem": stem, "file": str(p.relative_to(root)), "class": "NO_HOST_DATASET",
                    "detail": f"{name} grounds on {rel_bare!r}, which no dataset descriptor "
                              f"declares (searched {len(dataset_targets)} served relation(s)). A "
                              f"sample can only be drawn from a relation the data plane names",
                    "exit": 1})
                continue
            have = {h.casefold() for h in host.columns}
            missing = [x for x in cols if x.casefold() not in have]
            if missing:
                findings.append({
                    "stem": stem, "file": str(p.relative_to(root)), "class": "FIELD_NOT_IN_HOST",
                    "detail": f"{name}: {len(missing)} of {len(cols)} declared field(s) {missing} "
                              f"are not columns of {host.relation} (which declares "
                              f"{len(host.columns)}). The Fields table and the host relation "
                              f"disagree — a finding, not something to sample around",
                    "exit": 1})
                continue
            coltypes = column_types(root, rel_bare)
            where, basis, _fixed = member_population(g, ident, coltypes)
            notes = []
            disc = str(g.get("discriminator") or "").strip()
            if where and disc and not g.get("value_filter") and disc.casefold() not in have:
                notes.append(f"the membership declaration (grounding.discriminator: {disc}) names "
                             f"a column {host.relation} does not have, so THIS block is the whole "
                             f"relation and is narrowed by nothing; the narrowing applies to the "
                             f"source(s) that carry the column")
                where, basis = None, ""
            grain, member_key = "row", None
            if declares_members and ident and ident in cols:
                grain, member_key = "key", ident
                grain_basis = (f"the concept declares a members: block, so its members are the "
                               f"distinct values of its canonical key `{ident}`; the window is "
                               f"drawn STRATIFIED over those members rather than collapsed to one "
                               f"row each — every member gets a row, and the rest of the budget "
                               f"goes back to the data")
            elif declares_members and ident:
                grain_basis = (f"the concept declares a members: block, but its canonical key "
                               f"`{ident}` is not one of the columns this block shows, so a draw "
                               f"stratified on it would be invisible to the reader — nothing on "
                               f"the page would say which member a row stands for; drawn at ROW "
                               f"grain instead")
                notes.append(grain_basis)
            elif declares_members:
                grain_basis = ("the concept declares a members: block but no identity."
                               "canonical_key, so there is no member to collapse to; ROW grain")
                notes.append(grain_basis)
            else:
                grain_basis = ("the concept declares no members: block, so a member is a ROW of "
                               "the host relation that the concept claims as its own")
            # ONE FILE PER BLOCK, and the name says which block. A single-source concept keeps the
            # bare `<stem>.sample.csv` it has always had — 14 of 17 on the measured bundle, whose
            # bytes must not move for a change that does not concern them. A concept with more
            # than one DECLARED source qualifies every one of its cuts by the relation it was
            # drawn from, so two blocks can never write over each other and the filename alone
            # says which population a reader is holding. The qualifier keys on the DECLARED source
            # count, not on how many blocks survived planning: a name that changed when one source
            # temporarily failed would churn the other source's file for an unrelated reason.
            out_name = (f"{stem}{CONCEPT_SUFFIX}" if len(rel_order) == 1
                        else f"{stem}.{rel_bare}{CONCEPT_SUFFIX}")
            planned.append(ConceptBlock(
                stem=stem, concept=name, klass=str(c.get("class") or ""),
                relation=host.relation, schema=host.schema, relation_name=host.relation_name,
                columns=cols, select_body=host.select_body,
                member_where=where, member_basis=basis,
                grain=grain, grain_basis=grain_basis, member_key=member_key,
                count_key=(ident if ident in cols else None), notes=notes,
                # THE DECLARED LIST RIDES ONLY ON THE BLOCKS THAT CAN USE IT. A concept's second
                # grounding source often does not carry the canonical key at all (Currency's fx
                # relation is the measured case), so it draws at ROW grain — and hanging a member
                # list on a block with no member column would invite a reader to compare a list of
                # codes against a population that was never keyed on them.
                declared=(c_declared if grain == "key" else None),
                declared_from=(c_declared_from if grain == "key" else ""),
                out_path=f"{out_dir}/{out_name}",
                fields_total=len(fields), fields_undrawn=[],
                source_index=i + 1, source_count=len(rel_order)))
            drawn_rels.append(rel_bare)
        # THE ONE CASE `fields_undrawn` STILL HAS, now that every source is attempted: a source
        # that could NOT be planned (no host descriptor, or a Fields row its relation does not
        # carry). Its columns are then in no block, and a reader who is shown N blocks has no way
        # to notice the absence — so it is stated on every block of the concept, as a fact about
        # the concept and not about any one projection. Where all sources were planned this list
        # is empty and no note is written, which is the whole of the 14 single-source concepts and
        # now also of the 3 that span two relations.
        in_a_block = {col for b in planned for col in b.columns}
        undrawn = [f["column"] for f in fields if f["column"] not in in_a_block]
        skipped = [r for r in rel_order if r not in drawn_rels]
        for b in planned:
            b.fields_undrawn = list(undrawn)
            if undrawn:
                b.notes.append(
                    f"the Fields table spans {len(rel_order)} relation(s) and {len(drawn_rels)} "
                    f"of them could be drawn; {len(undrawn)} of its {len(fields)} row(s) "
                    f"({sorted(undrawn)}) are columns only of {', '.join(skipped)}, which is in "
                    f"NO block — see the finding above for why that source was not drawn")
        blocks.extend(planned)
    if wanted is not None:
        for miss in sorted(wanted - seen):
            findings.append({"stem": miss, "file": "", "class": "NO_SUCH_CONCEPT",
                             "detail": f"--stems named {miss!r}, which no concept under "
                                       f"{ontology / 'concepts'} declares", "exit": 1})
    return tuple(blocks), findings


def _hash_order(conn, seed: str, columns) -> str:
    """The stable pseudo-random key: md5 over the seed and every declared cell, in column order.

    NULL and the empty string collapse here, exactly as they already collapse in the rendered CSV.
    That is a tie, not a value, and the declared-column total order below breaks every tie — so the
    collapse cannot make the draw arbitrary, only make two indistinguishable rows adjacent.
    """
    if not _SEED_OK.match(seed or ""):
        raise SampleRefused(
            f"seed {seed!r} is not 1-64 characters of [A-Za-z0-9._:/+@-]. The seed reaches the "
            f"statement as a SQL literal and its charset is CLOSED rather than escaped", 2)
    parts = " || '|' || ".join(
        f"coalesce(CAST({conn.quote_identifier(c)} AS VARCHAR), '')" for c in columns)
    return f"md5('{seed}' || '|' || {parts})"


def _total_order(conn, columns) -> str:
    return ", ".join(conn.quote_identifier(c) + " ASC NULLS LAST" for c in columns)


def _concept_src(conn, b: ConceptBlock) -> str:
    return f"({b.select_body}) t" if b.select_body_used else conn.qualify(b.ref)


def render_concept_body(conn, b: ConceptBlock, *, seed: str, limit: int) -> str:
    """The exact draw statement. PURE — no driver, no socket. Printed by --dry-run."""
    sel = ", ".join(conn.quote_identifier(c) for c in b.columns)
    order = f"{_hash_order(conn, seed, b.columns)} ASC, {_total_order(conn, b.columns)}"
    where = f" WHERE {b.member_where}" if b.member_where else ""
    src = _concept_src(conn, b)
    if b.grain == "key":
        # THE STRATIFICATION, AND IT IS ONE CLAUSE. `row_number()` numbers each member's rows in
        # the seeded order, so rank 1 is that member's representative; ordering the window by RANK
        # FIRST and the seeded order second lays the whole population out as "every member's 1st
        # row, then every member's 2nd, ...". A LIMIT over that order therefore takes every member
        # before it takes any member twice — which is exactly "at least one row per member, the
        # remainder spread across members in the existing seeded order", with no second pass and
        # no arithmetic done outside the engine.
        #
        # WHAT IT REPLACES AND WHY. The clause here was `WHERE mac_member_rn = 1` — one
        # representative row per member and nothing else. It answered the earlier complaint (40
        # rows of one currency pair) by throwing the data away, and it MISLED: a 15-row AgeBand cut
        # showing `CustomerKey 1175412 | 20` reads as though that customer defines the band, when
        # it is an arbitrary representative of some seven thousand. Ranking instead of filtering
        # keeps the guarantee and gives the rows back.
        rn = conn.quote_identifier(_RN)
        inner = (f"SELECT {sel}, row_number() OVER (PARTITION BY "
                 f"{conn.quote_identifier(b.member_key)} ORDER BY {order}) AS {rn} "
                 f"FROM {src}{where}")
        return (f"SELECT {sel} FROM ({inner}) {conn.quote_identifier('mac_members')} "
                f"ORDER BY {rn} ASC, {order} LIMIT {limit + 1}")
    return f"SELECT {sel} FROM {src}{where} ORDER BY {order} LIMIT {limit}"


def render_member_keys_body(conn, b: ConceptBlock, *, cap: int) -> str:
    """THE DATA'S OWN MEMBER LIST — the RIGHT side of the outer join. PURE.

    Read for one question only: which DECLARED member has no row here? So it is asked only where a
    declared list exists to compare against, and it is capped — `cap + 1` so "exactly cap" and
    "more than cap" are distinguishable, exactly as the draw's own `limit + 1` is.
    """
    src = _concept_src(conn, b)
    where = f" WHERE {b.member_where}" if b.member_where else ""
    k = conn.quote_identifier(b.member_key)
    return (f"SELECT DISTINCT {k} AS {conn.quote_identifier(_MK)} FROM {src}{where} "
            f"ORDER BY 1 ASC LIMIT {cap + 1}")


def render_population_body(conn, b: ConceptBlock) -> str:
    """EVERY DENOMINATOR THIS SAMPLE OWES, in one statement: members, distinct members, host rows.

    Run for a WITHHELD concept too. A withheld section that cannot say how many members it withheld
    is indistinguishable from a section that has nothing to show.
    """
    src = _concept_src(conn, b)
    where = f" WHERE {b.member_where}" if b.member_where else ""
    dk = (f"count(DISTINCT {conn.quote_identifier(b.count_key)})" if b.count_key
          else "CAST(NULL AS BIGINT)")
    return (f"SELECT count(*) AS member_rows, {dk} AS distinct_members, "
            f"(SELECT count(*) FROM {src}) AS host_relation_rows FROM {src}{where}")


def _concept_exists(conn, b: ConceptBlock):
    """(exists, measured). A concept declares a SUBSET of its host's columns, so an EXTRA relation
    column is NORMAL here and is not a finding — the opposite of the relation preview, where an
    undeclared column means the descriptor has drifted."""
    exists, measured = relation_exists(conn, b)
    if exists is True:
        folded = {m.casefold() for m in measured}
        unknown = [c for c in b.columns if c.casefold() not in folded]
        if unknown:
            raise SampleRefused(
                f"{b.concept} on {b.relation}: the concept declares {unknown}, which the relation "
                f"does not have (measured {len(measured)} column(s), the concept declares "
                f"{len(b.columns)}). NOT drawn", 1)
    return exists, measured


def _population_rule(blk: ConceptBlock, *, limit: int) -> str:
    """ONE LINE saying what a member IS AND HOW THE WINDOW WAS FILLED — the sentence the page prints.

    Written here and not on the page because the page did not choose the population: the predicate
    and the grain are this tool's reading of the concept's own declarations, and a page that
    restated them in its own words would be a second, unverifiable home for the claim.

    IT SAYS WHAT WAS DONE, and that is the whole requirement on this string. It used to read "one
    row per distinct X — a seeded random representative row drawn from inside each group", which
    described a draw this tool no longer makes; a sentence that survives the behaviour it describes
    is worse than none, because a reader has no way to tell it went stale.
    """
    if blk.grain == "key":
        left = (f"the {len(blk.declared)} member(s) the concept DECLARES" if blk.declared
                else f"the distinct `{blk.member_key}` values the data carries")
        who = (f"a STRATIFIED window of up to {limit} row(s) over the member rows, outer-joined "
               f"onto {left}: EVERY member appears at least once — each member's first row, in the "
               f"seeded order, before any member's second — and the budget that remains is spent "
               f"going round the members again in that same order. A declared member with NO row "
               f"in the data still appears, carrying its `{blk.member_key}` and empty cells; where "
               f"the members outnumber the window it is one row per member as far as the limit "
               f"reaches, and the record states both counts")
    else:
        who = "a row of the host relation that the concept claims as its own"
    if blk.member_basis:
        return f"{who}, over the rows where {blk.member_where} ({blk.member_basis})"
    return f"{who}; the concept declares no membership predicate, so every row of the host qualifies"


def derive_concepts(root: Path, blocks, conn, *, seed: str, limit: int, disclosure: str,
                    dry_run: bool = False, verify: bool = False):
    """Block by block. One block's refusal never stops another's draw."""
    from sdk.connector import bind
    from sdk.connector.base import ConnectorError, exit_code_for

    results = []
    for blk in blocks:
        rec = {"kind": CONCEPT_KIND, "stem": blk.stem, "concept": blk.concept, "class": blk.klass,
               "relation": blk.relation,
               "file": blk.out_path, "columns": list(blk.columns),
               "fields_declared": blk.fields_total, "fields_undrawn": list(blk.fields_undrawn),
               "population_rule": _population_rule(blk, limit=limit),
               # THE SHAPE OF THE DRAW, as a word the consumer can branch on rather than a
               # sentence it would have to parse. `stratified` is the member-declaring draw
               # described above; `window` is the plain seeded window a concept with no members
               # has always had and still has.
               "draw": "stratified" if blk.grain == "key" else "window",
               "members_declared": (len(blk.declared) if blk.declared else None),
               "members_declared_from": blk.declared_from or None,
               "columns_from": "sdk/project/mac_okf.py#_grounding_fields — the concept page's own "
                               "Fields table, in its order",
               "member_predicate": blk.member_where, "member_basis": blk.member_basis,
               "member_grain": blk.grain, "member_grain_basis": blk.grain_basis,
               "member_key": blk.member_key,
               # WHICH COLUMN `distinct_members` IS A COUNT OF, or null when no count was taken.
               # A denominator that does not say what it counts is the defect this whole family
               # exists to remove, and with ONE BLOCK PER SOURCE the answer differs between the
               # blocks of ONE concept: a concept's canonical key is a column of the source it was
               # named from and often not of its siblings, so block 1 can count distinct members
               # and block 2 cannot. That absence is a DECLARED fact — "the canonical key is not a
               # column here" — and stating it is how a reader sees the two sources are not the
               # same shape. Inventing a substitute (the other relation's spelling of what looks
               # like the same idea) would be this tool deciding a semantic equivalence the
               # concept did not declare.
               "count_key": blk.count_key, "seed": seed, "disclosure": disclosure,
               # WHICH OF THE CONCEPT'S SOURCES THIS BLOCK IS, as two integers rather than the
               # sentence "1 of 2": the console groups blocks and must compare the numbers, and a
               # string it had to parse back would be a second, weaker home for the same fact.
               # `source_count` is the DECLARED source count, so `source_index of source_count`
               # also says how many blocks are MISSING when a source could not be drawn.
               "source_index": blk.source_index, "source_count": blk.source_count,
               "notes": list(blk.notes)}
        try:
            blk.ref = _ref(blk)
            if dry_run:
                blk.select_body_used = bool(blk.select_body)
                rec.update(state="DRY", statement=render_concept_body(conn, blk, seed=seed,
                                                                      limit=limit),
                           population_statement=render_population_body(conn, blk))
                # EVERY STATEMENT THE RUN WOULD MAKE, including the member-list read a declared
                # member list adds. A --dry-run that showed two of three reads would understate
                # what the tool does to the warehouse, which is the one thing it exists to show.
                if blk.grain == "key" and blk.declared:
                    rec["member_list_statement"] = render_member_keys_body(
                        conn, blk, cap=MEMBER_LIST_MAX)
                results.append(rec)
                continue
            exists, _measured = _concept_exists(conn, blk)
            if exists is False:
                if not blk.select_body:
                    raise SampleRefused(
                        f"{blk.concept}: {blk.relation} does not exist and the bundle declares no "
                        f"transform body to read instead. NOT drawn", 1)
                blk.select_body_used = True
                rec["notes"].append("drawn from the transform's SQL body: the relation the concept "
                                    "grounds on does not exist yet, so this previews a PROPOSAL")
            pop_body = render_population_body(conn, blk)
            pres = conn.read(bind(pop_body, params={}, user_values=(), limit=2,
                                  purpose="sample-population"))
            prow = _rows_positional(pres)[0]
            member_rows, distinct_members, host_rows = int(prow[0]), prow[1], int(prow[2])
            distinct_members = None if distinct_members is None else int(distinct_members)
            # THE POPULATION IS THE MEMBER ROWS AT BOTH GRAINS, and it was not before: a
            # member-declaring block took `distinct_members` as its population, because a draw that
            # collapsed to one row per member really did have the members as its population. The
            # stratified window draws ROWS — 40 of AgeBand's 104 990, not 15 of 15 — so the
            # denominator `truncated` is measured against has to be the rows, or a 40-of-104 990
            # window would report itself complete. The member counts do not disappear; they move
            # into their own fields below, each with its own denominator.
            population = member_rows
            rec.update(member_rows=member_rows, distinct_members=distinct_members,
                       host_relation_rows=host_rows, relation_rows=host_rows,
                       population=population, population_unit="member row",
                       population_statement=pop_body)

            # ── THE OUTER JOIN'S LEFT SIDE, MEASURED AGAINST THE DATA ──────────────────────────
            # Asked only where a declared list exists to ask ABOUT. Where none does, absence is
            # undecidable and is recorded as null rather than as an empty list: "no member is
            # missing" is a measurement and "there was nothing to measure against" is not.
            in_data, absent, members_total = None, (), None
            if blk.grain == "key" and blk.declared:
                mk_body = render_member_keys_body(conn, blk, cap=MEMBER_LIST_MAX)
                mres = conn.read(bind(mk_body, params={}, user_values=(),
                                      limit=MEMBER_LIST_MAX, purpose="sample-members"))
                rec["member_list_statement"] = mk_body
                if mres.truncated:
                    rec["notes"].append(
                        f"the data carries more than {MEMBER_LIST_MAX} distinct "
                        f"`{blk.member_key}` value(s), so the member list was NOT materialised and "
                        f"no declared member could be checked for absence")
                else:
                    in_data = {_mkey(v) for (v,) in _rows_positional(mres)}
                    absent = tuple(d for d in blk.declared if _mkey(d) not in in_data)
                    members_total = len(in_data | {_mkey(d) for d in blk.declared})
            elif blk.grain == "key":
                members_total = distinct_members
            # A MEMBER WITH NO ROWS COSTS A ROW OF THE WINDOW, because it IS one of the rows the
            # reader came for. Reserved before the data draw and capped at the limit, so a register
            # declaring more absent codes than the window holds truncates like anything else
            # instead of overrunning it.
            absent_shown = absent[:limit]
            budget = max(0, limit - len(absent_shown))
            rec.update(members_total=members_total,
                       members_absent=([cell(a) for a in absent] if in_data is not None else None),
                       members_undeclared=(len(in_data - {_mkey(d) for d in blk.declared})
                                           if in_data is not None else None))

            if population == 0 and not absent_shown:
                raise SampleRefused(
                    f"{blk.concept} on {blk.relation}: the concept claims 0 of the relation's "
                    f"{host_rows} row(s) as its members, so a sample would be a header with no "
                    f"evidence under it — NOT drawn", 1)
            if disclosure != PUBLISHED:
                rec.update(state="WITHHELD", rows=None, sha256=None,
                           statement=None, engine=conn.id)
                results.append(rec)
                continue
            # THE DATA HALF. `budget` and not `limit`: the window is the limit, and the declared
            # members with no rows are already holding their seats in it.
            body, drawn, fetch_trunc = None, [], False
            if budget > 0:
                body = render_concept_body(conn, blk, seed=seed, limit=budget)
                res = conn.read(bind(body, params={}, user_values=(), limit=budget,
                                     purpose="sample"))
                if [c.casefold() for c in res.columns] != [c.casefold() for c in blk.columns]:
                    raise SampleRefused(
                        f"{blk.concept}: the engine returned columns {list(res.columns)} for a "
                        f"projection of {list(blk.columns)}; the header would not be the Fields "
                        f"table's", 1)
                drawn = _rows_positional(res)
                fetch_trunc = bool(res.truncated)
            else:
                rec["notes"].append(
                    f"{len(absent_shown)} declared member(s) with no row in the data fill the "
                    f"whole window of {limit}, so NO row was drawn from the data")
            # THE OUTER JOIN'S UNMATCHED HALF, RENDERED. The key cell carries the declared code and
            # every other cell is empty — which is the truth: the data has nothing to put there.
            # It is NOT marked with an extra column: the header is the concept's Fields table and
            # refusing anything else is a rule this tool already enforces, so the marking lives in
            # the record (`members_absent`) and on the page, where a marking can live without the
            # file ceasing to be what it claims to be.
            ki = list(blk.columns).index(blk.member_key) if blk.member_key else 0
            holes = [tuple(m if i == ki else None for i in range(len(blk.columns)))
                     for m in absent_shown]
            data = render_sample(blk.columns, list(drawn) + holes)
            # TRUNCATED IS A WINDOW QUESTION, NOT A FETCH QUESTION, AND THE CONNECTOR ANSWERS THE
            # OTHER ONE. `res.truncated` reports whether the READ was cut short — and it never is
            # here, because the LIMIT is inside the statement, so the engine returns exactly what
            # was asked for and truthfully says it truncated nothing. Recording that answer under
            # this name made 12 of 17 concept entries claim `truncated: false` while showing 40
            # rows of a population of 223 974, and a reader of the console's Sample view was told
            # the draw was complete when it was a window onto five thousand times more.
            #
            # The concept draw KNOWS its population — it measured it — so the window is decidable
            # exactly: this is a window iff fewer rows were drawn than exist. The relation preview
            # above keeps the connector's flag, because there the whole relation IS the population
            # and no second count was taken.
            #
            # AND IT IS ASKED OF THE DATA ROWS, NOT OF THE FILE'S ROWS. A declared member with no
            # row is a row of the FILE that is not a row of the POPULATION, so counting it here
            # would make a complete draw look like a window — and, where the placeholders push the
            # file past the population, would trip the disagreement refusal below on two counts
            # that were never counting the same thing.
            windowed = len(drawn) < population
            rec.update(state="WROTE", rows=len(drawn) + len(holes),
                       rows_from_data=len(drawn), rows_declared_only=len(holes),
                       truncated=windowed, fetch_truncated=fetch_trunc,
                       engine=conn.id, statement=body,
                       sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            # HOW MANY MEMBERS ACTUALLY MADE IT ONTO THE PAGE, against how many there are. This is
            # the number the whole change exists to guarantee, so it is MEASURED off the rendered
            # rows rather than asserted from the statement: a draw that says it stratifies and a
            # file that holds every member are two claims, and only the second one is evidence.
            if blk.grain == "key" and blk.member_key:
                present = {_mkey(r[ki]) for r in drawn} | {_mkey(m) for m in absent_shown}
                total = members_total if members_total is not None else len(present)
                rec.update(members_present=len(present), members_total=total,
                           members_unshown=max(0, total - len(present)),
                           members_truncated=len(present) < total)
            if len(drawn) > population:
                raise SampleRefused(
                    f"{blk.concept}: the draw returned {len(drawn)} row(s) over a population "
                    f"measured at {population}; the two reads disagree and neither is evidence", 1)
            path = root / blk.out_path
            if verify:
                old = path.read_bytes() if path.exists() else b""
                rec["state"] = "IDENTICAL" if old == data else "DIFFERS"
                if old != data:
                    rec["detail"] = _first_diff(old, data)
                results.append(rec)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            results.append(rec)
        except SampleRefused as exc:
            rec.update(state="REFUSED", detail=str(exc), exit=exc.exit_code)
            results.append(rec)
        except ConnectorError as exc:                                          # pragma: no cover
            rec.update(state="REFUSED", detail=f"{blk.relation}: {exc}",
                       exit=exit_code_for(exc))
            results.append(rec)
    return results


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# THE COMMAND
# ══════════════════════════════════════════════════════════════════════════════════════════════════

def _rows_positional(res):
    """ReadResult.rows -> positional tuples, read through res.columns.

    Through `res.columns` and never by iterating a row's own keys: one connector materialises a row
    as `dict(zip(columns, values))`, which DROPS trailing keys whose cell was NULL, and a key
    iteration would also lose the column ORDER.
    """
    return [tuple(r.get(c) for c in res.columns) for r in res.rows]


def derive(root: Path, targets, conn, *, limit: int = 20, dry_run: bool = False,
           verify: bool = False):
    """Relation by relation. One target's refusal never stops another's cut."""
    results = []
    for t in targets:
        rec = {"stem": t.stem, "kind": t.kind, "file": t.out_path, "relation": t.relation,
               "notes": list(t.notes)}
        try:
            if dry_run:
                t.select_body_used = bool(t.select_body)
                t.ref = _ref(t)
                rec.update(state="DRY", statement=render_body(conn, t, limit=limit))
                results.append(rec)
                continue
            res, body, provenance = fetch_sample(conn, t, limit=limit)
            data = render_sample(t.columns, _rows_positional(res))
            path = root / t.out_path
            rec.update(state="WROTE", rows=res.row_count, truncated=bool(res.truncated),
                       derived_from=provenance, engine=conn.id, statement=body,
                       sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            if provenance == "transform-body":
                rec["notes"].append("derived from the transform's SQL body: the relation the "
                                    "descriptor names does not exist yet, so this previews a "
                                    "PROPOSAL and must be re-cut once the view is deployed")
            if verify:
                old = path.read_bytes() if path.exists() else b""
                if old == data:
                    rec["state"] = "IDENTICAL"
                else:
                    rec["state"] = "DIFFERS"
                    rec["detail"] = _first_diff(old, data)
                results.append(rec)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            results.append(rec)
        except SampleRefused as exc:
            rec.update(state="REFUSED", detail=str(exc), exit=exc.exit_code)
            results.append(rec)
    return results


def _first_diff(old: bytes, new: bytes) -> str:
    o = old.decode("utf-8", "replace").splitlines()
    n = new.decode("utf-8", "replace").splitlines()
    for i in range(max(len(o), len(n))):
        a = o[i] if i < len(o) else "<absent>"
        b = n[i] if i < len(n) else "<absent>"
        if a != b:
            return f"line {i + 1}: on disk {a!r} · re-cut {b!r}"
    return "the files differ only in length"


#: ONE ENTRY PER CONCEPT, IN `samples[]`, UNDER `kind: "concepts"` — the shape the CONSUMER reads
#: (`sdk/project/mac_okf.py#load_sample_index`), not a shape invented here. The first ten keys are
#: the page's; the rest are this tool's provenance, which the page ignores and a reader of the
#: record needs: WHICH rows were claimed as members, by WHICH declaration, at WHICH grain, and
#: every denominator the counts are counts of.
CONCEPT_RECORD_KEYS = ("kind", "stem", "concept", "file", "relation",
                       # WHICH BLOCK OF THE CONCEPT, for a concept that grounds on more than one
                       # relation. Two integers and not a sentence — see derive_concepts.
                       "source_index", "source_count", "columns", "rows",
                       # THE THREE ROW COUNTS, because the file's rows are no longer one thing:
                       # `rows` is what is IN the file, `rows_from_data` is what was drawn from the
                       # population (the number `truncated` is about), and `rows_declared_only` is
                       # the outer join's unmatched half — declared members the data has no row
                       # for, rendered with their key and empty cells. Measured 0 on this bundle
                       # and the reason the shape exists anyway.
                       "rows_from_data", "rows_declared_only",
                       "population", "relation_rows", "population_rule", "truncated",
                       # BOTH ANSWERS, because conflating them is what went wrong: `truncated` is
                       # the WINDOW (were fewer rows drawn than exist), `fetch_truncated` is the
                       # CONNECTOR's (was the read itself cut short). The second is normally False
                       # here — the LIMIT lives in the statement — and recording it keeps that
                       # visible instead of leaving a reader to wonder which question was asked.
                       "fetch_truncated", "seed",
                       "class", "columns_from", "fields_declared", "fields_undrawn",
                       "member_predicate", "member_basis", "member_grain", "member_grain_basis",
                       "member_key", "count_key", "member_rows", "distinct_members",
                       "host_relation_rows",
                       # THE MEMBER COVERAGE, EVERY COUNT WITH ITS DENOMINATOR. `members_present`
                       # of `members_total` is the guarantee this draw makes, measured off the
                       # rendered rows; `members_declared` is how many the CONCEPT declares and
                       # `members_declared_from` names the declaration that was read, so a reader
                       # can tell a register's 5 from the data's 5. `members_absent` lists the
                       # declared members the data carries no row for (the outer join's point) and
                       # is null — never [] — where no declared list existed to compare against.
                       # `members_undeclared` is its mirror: values the data carries that the
                       # declaration does not. `members_truncated` says a member did not fit.
                       "draw", "members_declared", "members_declared_from", "members_total",
                       "members_present", "members_unshown", "members_truncated",
                       "members_absent", "members_undeclared",
                       "population_unit", "disclosure", "sha256", "notes")


#: TWO RECORDS, ONE PER DRAW, EACH BESIDE ITS OWN CUTS — and the fact that decided it is not
#: tidiness, it is that ONE record for TWO draws was already stating things that were not true.
#:
#: It was one file, `data/samples/samples.run.json`, holding both sections; a run that drew one
#: section CARRIED FORWARD the other. The carry-forward copied the ENTRIES and could not carry
#: their stamps, because the stamps are at the top level and there is only one of each:
#:   · `engine` — a `--plane concepts` run relabelled every carried relation preview with the
#:     engine of a run that never touched it. The one thing the record exists to say about a
#:     preview ("which engine rendered these bytes") was overwritten by a different run's answer.
#:   · `limit` — the RELATION limit, rewritten to the concepts run's default 20 whatever the
#:     previews were actually cut at.
#:   · `order` / `value_domain` — written in the relation preview's terms ("the lexicographically
#:     smallest rows", "a BIASED preview"), which is false of the concept draw; the concept draw
#:     already had to carry its own parallel pair inside `concept_draw`.
#: And one more, measured in the consumer: `check_sample_matches_descriptor` builds its map as
#: `run[s["stem"]] = s` with NO kind filter, so on the live bundle the CONCEPT entries for
#: `product`, `customer` and `store` overwrite the SOURCE previews of the same stem and mask that
#: gate's PROPOSAL_PREVIEW check on three files. Two arrays in one key, collide.
#:
#: SPLITTING IS NOT DUPLICATING, and the rule that keeps it so: NO FACT IS WRITTEN TWICE. The
#: relation record holds the relation previews and the relation draw's stamps; the concept record
#: holds the concept blocks and the concept draw's stamps. Neither copies a value from the other —
#: each carries a POINTER at the other's path, so a reader who finds one can find both, and there
#: is nothing for the two to disagree ABOUT. The carry-forward machinery is gone with the problem
#: it patched: a run that does not draw a plane does not open, read or rewrite that plane's record.
RELATION_RECORD_DIR = "data/samples"


def _record_path(root: Path, rel_dir: str) -> Path:
    return root / rel_dir / RUN_RECORD


def write_run_record(root: Path, results, *, engine: str, limit: int, advisories,
                     concept_record: str | None = None) -> str:
    """The RELATION previews' record, beside them at `data/samples/samples.run.json`.

    A machine cut and a hand-typed file are byte-indistinguishable on disk — the shape is a header
    and rows and nothing else — so WHERE a preview's rows came from has to be written down beside
    it or it is unknowable. This is that record, and the gate reads it.
    """
    rec = {
        "contract": CONTRACT, "generated_by": f"{NAME}.py", "engine": engine, "limit": limit,
        "advisories": list(advisories),
        "order": "every declared column in descriptor order, ASC NULLS LAST, then the rendered "
                 "rows sorted lexicographically; the window is the lexicographically smallest rows "
                 "and is a BIASED preview, not a random sample",
        "value_domain": "rendered from the engine's native Python values; PER-ENGINE byte-identical "
                        "on unchanged data, NEVER cross-engine (one engine returns every cell as "
                        "text and another returns typed objects)",
        "draw": "RELATION previews only. The CONCEPT member draw is a different population at a "
                "different column set on a different schedule, and it is recorded beside its own "
                "cuts under the ontology plane — see `concept_record`, which is a POINTER and "
                "never a copy: no fact appears in both records",
        "concept_record": concept_record,
        "samples": [], "refused": [],
    }
    for r in results:
        if r.get("state") in ("WROTE", "IDENTICAL", "DIFFERS"):
            rec["samples"].append({k: r[k] for k in
                                   ("stem", "kind", "file", "relation", "rows", "truncated",
                                    "derived_from", "sha256", "notes") if k in r})
        elif r.get("state") == "REFUSED":
            rec["refused"].append({"stem": r["stem"], "kind": r["kind"], "relation": r["relation"],
                                   "reason": r["detail"]})
    p = _record_path(root, RELATION_RECORD_DIR)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
                 encoding="utf-8")
    return str(p.relative_to(root))


def write_concept_run_record(root: Path, out_dir: str, concept_results, *, engine: str,
                             advisories, concept_draw) -> str:
    """The CONCEPT draw's record, beside the concept cuts at `<ontology>/samples/samples.run.json`.

    ONE ENTRY PER BLOCK, not per concept: a concept that grounds on two relations has two
    populations, two predicates and two sets of denominators, and one entry could only state one
    of them. `stem` is therefore NOT unique in `samples[]` and `stem + source_index` is — the
    consumer groups by stem and renders the blocks side by side, which is the whole point.
    """
    rec = {
        "contract": CONTRACT, "generated_by": f"{NAME}.py", "engine": engine,
        "advisories": list(advisories),
        "draw": "CONCEPT member draws only. The RELATION previews are a different population at a "
                "different column set on a different schedule, and they are recorded beside their "
                "own cuts in the data plane — see `relation_record`, which is a POINTER and never "
                "a copy: no fact appears in both records",
        "relation_record": f"{RELATION_RECORD_DIR}/{RUN_RECORD}",
        "blocks_per_concept": "ONE ENTRY PER GROUNDING SOURCE. `stem` repeats for a concept that "
                              "grounds on more than one relation; the unique key is "
                              "(stem, source_index) and `source_count` is how many the concept "
                              "DECLARES, so a stem with fewer entries than its source_count has a "
                              "source that could not be drawn — see `concept_refused`",
        "seed": (concept_draw or {}).get("seed"),
        "concept_draw": concept_draw,
        "samples": [], "concept_refused": [],
    }
    for r in concept_results or ():
        if r.get("state") in ("WROTE", "IDENTICAL", "DIFFERS", "WITHHELD"):
            entry = {k: r[k] for k in CONCEPT_RECORD_KEYS if k in r}
            entry["state"] = r["state"]
            if r["state"] == "WITHHELD":
                entry["file"] = None
            rec["samples"].append(entry)
        elif r.get("state") == "REFUSED":
            rec["concept_refused"].append({"stem": r["stem"], "concept": r.get("concept"),
                                           "relation": r.get("relation"),
                                           "source": f"{r.get('source_index')} of "
                                                     f"{r.get('source_count')}",
                                           "reason": r["detail"]})
    p = _record_path(root, out_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
                 encoding="utf-8")
    return str(p.relative_to(root))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", help="the bundle root (REQUIRED; this command writes files)")
    ap.add_argument("stems", nargs="*", help="descriptor stems; default every declared relation")
    ap.add_argument("--plane", choices=("sources", "datasets", "both", "concepts", "all"),
                    default="both",
                    help="which draw to run. `both` (the DEFAULT, unchanged) is the relation "
                         "preview over sources + datasets; `concepts` is the seeded member draw; "
                         "`all` is both")
    ap.add_argument("--limit", type=int, default=20,
                    help="rows per preview (default 20; must be >= 1)")
    ap.add_argument("--concept-limit", type=int, default=DEFAULT_CONCEPT_LIMIT,
                    help=f"rows per concept sample (default {DEFAULT_CONCEPT_LIMIT}; must be >= 1). "
                         f"A concept with FEWER members than this shows all of them and the run "
                         f"record carries both numbers")
    ap.add_argument("--seed", default=None,
                    help="the draw's seed, 1-64 of [A-Za-z0-9._:/+@-]. Default: the bundle's "
                         f"publish.samples.seed, else {DEFAULT_SEED!r}. The SAME seed over the "
                         f"same data returns the same rows")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the exact statement each preview WOULD run; needs no driver")
    ap.add_argument("--verify", action="store_true",
                    help="re-cut in memory and compare bytes with the file on disk; writes nothing")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if not a.root:
        ap.error("a bundle root is required")           # exit 2: a writer must not default to cwd
    if a.limit < 1:
        ap.error("--limit must be >= 1 (a limit of 0 yields 0 rows with truncated=True, a result "
                 "that claims there was more while showing nothing)")
    if a.concept_limit < 1:
        ap.error("--concept-limit must be >= 1 (a limit of 0 draws no member while still claiming "
                 "a population)")

    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    do_concepts = a.plane in ("concepts", "all")
    planes = {"both": ("sources", "datasets"), "all": ("sources", "datasets"),
              "concepts": ()}.get(a.plane, (a.plane,))

    targets, plan_findings = plan_samples(root, planes=planes, stems=a.stems or None)
    declared = {k: len(glob.glob(str(root / "data" / k / "*.yaml"))) for k in planes}
    if do_concepts:
        # THE CONCEPT DRAW NEEDS THE DATASET PLAN EVEN WHEN THE RELATION PREVIEW IS NOT RUN: a
        # concept grounds on a BARE relation name and only the dataset descriptor + its transform
        # say which schema serves it. Planned, never derived — nothing here cuts a relation preview.
        hosts = targets if "datasets" in planes else plan_samples(root, planes=("datasets",))[0]
        onto = _ontology_plane(root)
        blocks, concept_findings = plan_concept_samples(root, onto, hosts,
                                                        stems=a.stems or None)
        n_concepts = len(concept_docs(root, onto)[0])
    else:
        blocks, concept_findings, n_concepts = (), [], 0
    if not any(declared.values()) and not do_concepts:
        if a.json:
            print(json.dumps({"targets": 0, "wrote": 0, "measured_nothing": True,
                              "state": "no-descriptors", "results": []}, indent=1))
            return D.EMPTY_EXIT
        # Restated here, with mac_diag as its single home, because tools/ and the gate package have
        # no import edge; a CI script recognises a not-run by this verbatim phrase.
        return D.refuse_empty(NAME, ", ".join(str(root / "data" / k) for k in planes),
                              unit="descriptor")
    if do_concepts and n_concepts == 0 and not any(declared.values()):
        if a.json:
            print(json.dumps({"targets": 0, "wrote": 0, "measured_nothing": True,
                              "state": "no-concepts", "results": []}, indent=1))
            return D.EMPTY_EXIT
        return D.refuse_empty(NAME, str(_ontology_plane(root) / "concepts"), unit="concept")

    try:
        conn, advisories = open_reader(root)
    except SampleRefused as exc:
        if a.json:
            print(json.dumps({"targets": len(targets), "wrote": 0, "state": "no-reader",
                              "detail": str(exc)}, indent=1))
        else:
            print(f"✗ could not open a reader: {exc}")
        return exc.exit_code
    for adv in advisories:
        print(f"  [advisory] {adv}")

    results = derive(root, targets, conn, limit=a.limit, dry_run=a.dry_run, verify=a.verify)

    c_results, c_draw, disclosure, seed = [], None, None, None
    if do_concepts:
        disclosure, bundle_seed, basis = disclosure_of(root)
        seed = a.seed or bundle_seed or DEFAULT_SEED
        seed_from = ("--seed" if a.seed else
                     ("publish.samples.seed" if bundle_seed else f"the default {DEFAULT_SEED!r}"))
        print(f"  [disclosure] {disclosure.upper()} — {basis}")
        print(f"  [seed] {seed!r} (from {seed_from})")
        c_results = derive_concepts(root, blocks, conn, seed=seed, limit=a.concept_limit,
                                    disclosure=disclosure, dry_run=a.dry_run, verify=a.verify)
        c_draw = {
            "limit": a.concept_limit, "seed": seed, "seed_from": seed_from,
            "disclosure": disclosure, "disclosure_basis": basis,
            "columns": "exactly the concept page's Fields table, in its order, from "
                       "sdk/project/mac_okf.py#_grounding_fields — the sample shows ONLY the "
                       "columns the concept declares",
            "population": "the concept's OWN members: grounding.value_filter where declared, else "
                          "grounding.discriminator IS NOT NULL, else the whole host relation — "
                          "read through tools/mac_generate_ontology_tests.py#member_population, "
                          "the same function the identity family is narrowed by",
            "order": "md5('<seed>' || '|' || every declared cell CAST to text, in column order) "
                     "ASC, then every declared column ASC NULLS LAST as the tie-break; the "
                     "rendered rows are then sorted lexicographically for the file's bytes",
            "reproducibility": "the draw is a pure function of (seed, the row's declared cells) "
                               "and NOT an engine RNG: no engine promises setseed/USING SAMPLE is "
                               "stable across its own versions. Same seed + same data => same "
                               "rows, per engine, across runs and versions; cross-engine only "
                               "where CAST(x AS VARCHAR) agrees",
        }

    wrote = [r for r in results if r.get("state") in ("WROTE", "IDENTICAL")]
    differs = [r for r in results if r.get("state") == "DIFFERS"]
    refused = [r for r in results if r.get("state") == "REFUSED"]
    dry = [r for r in results if r.get("state") == "DRY"]
    c_wrote = [r for r in c_results if r.get("state") in ("WROTE", "IDENTICAL")]
    c_held = [r for r in c_results if r.get("state") == "WITHHELD"]
    c_differs = [r for r in c_results if r.get("state") == "DIFFERS"]
    c_refused = [r for r in c_results if r.get("state") == "REFUSED"]
    c_dry = [r for r in c_results if r.get("state") == "DRY"]
    codes = [r.get("exit", 1) for r in refused] + [f["exit"] for f in plan_findings] \
        + [1] * len(differs) + [r.get("exit", 1) for r in c_refused] \
        + [f["exit"] for f in concept_findings] + [1] * len(c_differs)

    # EACH DRAW WRITES ITS OWN RECORD AND ONLY ITS OWN. A relations-only run never opens the
    # concept record; a concepts-only run never opens the relation one. That is what replaces the
    # carry-forward: there is nothing to carry, because nothing this run did not do is in the file
    # this run rewrites.
    record, c_record = "", ""
    if not a.dry_run and not a.verify:
        if planes:
            record = write_run_record(root, results, engine=conn.id, limit=a.limit,
                                      advisories=advisories,
                                      concept_record=f"{concept_sample_dir(root)}/{RUN_RECORD}")
        if do_concepts:
            c_record = write_concept_run_record(root, concept_sample_dir(root), c_results,
                                                engine=conn.id, advisories=advisories,
                                                concept_draw=c_draw)

    if a.json:
        print(json.dumps({"targets": len(targets), "declared": declared,
                          "wrote": len(wrote), "refused": len(refused) + len(plan_findings),
                          "differs": len(differs), "engine": conn.id, "run_record": record,
                          "concept_run_record": c_record,
                          "results": results, "plan_findings": plan_findings,
                          "concepts_declared": n_concepts, "concept_blocks": len(blocks),
                          "concept_draw": c_draw, "concept_results": c_results,
                          "concept_findings": concept_findings},
                         indent=1, ensure_ascii=False))
        return _verdict_code(codes)

    for r in dry:
        print(f"  [dry] {r['relation']:<44} {r.get('statement', '')}")
    for r in wrote:
        src = "" if r.get("derived_from") == "relation" else "  (from the transform body)"
        print(f"  [{r['state'].lower():<9}] {r['file']:<52} {r.get('rows')} row(s), "
              f"truncated={r.get('truncated')}{src}")
    for r in differs:
        print(f"  [DIFFERS  ] {r['file']}\n          {r.get('detail')}")
    for r in refused:
        print(f"  [REFUSED  ] {r['relation']}\n          {r['detail']}")
    for f in plan_findings:
        print(f"  [{f['class']}] {f['stem']}\n          {f['detail']}")
    for r in results:
        for n in r.get("notes") or []:
            print(f"  [note] {r['stem']}: {n}")

    for r in c_dry:
        print(f"  [dry] {r['concept']:<24} {r.get('statement', '')}")
    for r in c_wrote + c_held + c_differs:
        print(f"  [{r['state'].lower():<9}] {r['concept']:<22} {_member_line(r)}")
    for r in c_differs:
        print(f"          {r.get('detail')}")
    for r in c_refused:
        print(f"  [REFUSED  ] {r['concept']} on {r['relation']}\n          {r['detail']}")
    for f in concept_findings:
        print(f"  [{f['class']}] {f['stem']}\n          {f['detail']}")
    for r in c_results:
        for n in r.get("notes") or []:
            print(f"  [note] {r['concept']}: {n}")

    total = len(targets) + len(plan_findings)
    per_plane = "; ".join(f"{len([r for r in wrote if r['kind'] == k])} of {declared.get(k, 0)} "
                          f"{k[:-1]}(s)" for k in planes)
    order = "every declared column ASC NULLS LAST, rendered rows sorted"
    code = _verdict_code(codes)
    if a.dry_run:
        dry_plane = "; ".join(f"{len([r for r in dry if r['kind'] == k])} of {declared.get(k, 0)} "
                              f"{k[:-1]}(s)" for k in planes)
        stuck = plan_findings + concept_findings
        head = "PASS" if not stuck else "FAIL"
        c_bit = (f"; plus {len(c_dry)} of {len(blocks) + len(concept_findings)} concept block(s) "
                 f"over {n_concepts} declared concept(s)" if do_concepts else "")
        print(f"{head}: {NAME} --dry-run — {len(dry) + len(c_dry)} of {total + len(blocks)} "
              f"statement(s) rendered ({dry_plane}{c_bit}); engine {conn.id}; nothing was read "
              f"and nothing was written"
              + (f"; {len(stuck)} could not be planned" if stuck else ""))
        return 1 if stuck else 0
    verb = "verified" if a.verify else "wrote"
    head = "PASS" if code == 0 else ("FAIL" if code == 1 else "INCOMPLETE")
    tail = ""
    if refused or plan_findings:
        tail += f"; {len(refused) + len(plan_findings)} refused"
    if differs:
        tail += f"; {len(differs)} DIFFER from the file on disk (the data moved, or the file was " \
                f"authored)"
    if planes:
        print(f"{head}: {NAME} — {verb} {len(wrote)} of {total} preview(s) ({per_plane}); "
              f"engine {conn.id}; order: {order}{tail}"
              + (f"; run record {record}" if record else ""))
    if do_concepts:
        c_total = len(blocks) + len(concept_findings)
        c_tail = ""
        if c_refused or concept_findings:
            c_tail += f"; {len(c_refused) + len(concept_findings)} refused"
        if c_differs:
            c_tail += f"; {len(c_differs)} DIFFER from the file on disk"
        c_head = "PASS" if code == 0 else ("FAIL" if code == 1 else "INCOMPLETE")
        c_stems = len({b.stem for b in blocks})
        print(f"{c_head}: {NAME} --plane concepts — drew {len(c_wrote)} and WITHHELD "
              f"{len(c_held)} of {c_total} block(s) over {c_stems} grounded concept(s) of "
              f"{n_concepts} declared; disclosure {disclosure}; seed {seed!r}; engine {conn.id}; "
              f"order: seeded md5 over every declared cell, ties broken by the declared-column "
              f"total order{c_tail}"
              + (f"; run record {c_record}" if c_record else ""))
    return code


def _member_line(r) -> str:
    """One sample's counts, EACH WITH ITS DENOMINATOR. A count that does not say what it is a
    count OF is the defect this whole family exists to remove."""
    unit = r.get("population_unit") or "member"
    pop = r.get("population")
    # THE ROWS DRAWN FROM THE POPULATION, which is the number `of pop` is about: a declared member
    # with no row in the data is a row of the FILE and was never a row of the population.
    rows = r.get("rows_from_data", r.get("rows"))
    shown = "withheld" if r.get("state") == "WITHHELD" else f"{rows}"
    bits = [f"{shown} of {pop} {unit}(s)"]
    if r.get("member_grain") == "key":
        # THE MEMBER GUARANTEE, WITH ITS DENOMINATOR, and never the row count standing in for it:
        # the draw is stratified, so "40 rows" says nothing at all about how many members are on
        # the page. It used to print "one row per <key>", which described the collapse this draw
        # replaced and would now be simply false.
        bits.append(f"{r.get('members_present')} of {r.get('members_total')} "
                    f"{r.get('member_key')} member(s), stratified")
        if r.get("rows_declared_only"):
            bits.append(f"+{r.get('rows_declared_only')} declared member(s) with NO row in the "
                        f"data ({', '.join(r.get('members_absent') or ())})")
        if r.get("members_truncated"):
            bits.append(f"{r.get('members_unshown')} member(s) did NOT fit the window")
    bits.append(f"host {r.get('host_relation_rows')} row(s)")
    bits.append(f"{len(r.get('columns') or ())} declared column(s)")
    if (r.get("source_count") or 1) > 1:
        bits.append(f"source {r.get('source_index')} of {r.get('source_count')} "
                    f"({r.get('relation')})")
    return " · ".join(bits)


def _verdict_code(codes) -> int:
    if 1 in codes:
        return 1
    if 2 in codes:
        return 2
    return 0


# ══════════════════════════════════════════════════════════════════════════════════════════════════
# --self-test — one mutant per reject class, plus the negative controls. Domain-neutral fixtures.
# ══════════════════════════════════════════════════════════════════════════════════════════════════
# The wet half runs against an in-module FIXTURE connector, not a driver: the fixture returns its
# canned rows in a DELIBERATELY SCRAMBLED order, which is what lets the byte-idempotence case be a
# real relayout test (two different return orders, one expected file) instead of "ran it twice in
# one session", and it lets the whole suite run on an interpreter with no database driver.

_FIXTURE_ID = "fixture.connector.rows"


def _fixture_class(rows_by_relation, catalog=None, scramble=0):
    from sdk.connector.base import (AdapterError, AdapterErrorReason, ColumnSpec, ConfigProblem,
                                    ReadResult, RelationSchema)
    from sdk.connector.sql import SqlConnector

    class RowsConnector(SqlConnector):
        id = _FIXTURE_ID
        # `profile_relation` is a SHARED implementation every SqlConnector inherits (`explain` is only a
        # raising backstop), so the contract's drift check ("supports declares a verb IFF the class
        # overrides it") requires it declared here even though this fixture never wrote it.
        supports = frozenset({"describe_relation", "profile_relation"})
        credential_modes = frozenset({"none"})
        permissions = frozenset({"read"})
        probe_cost = "free"
        param_style = ":name"

        @classmethod
        def config_schema(cls):
            return {"type": "object"}

        @classmethod
        def validate_config(cls, conn):
            return []

        @classmethod
        def credential_plan(cls, conn):
            from sdk.connector.base import CredentialPlan
            return CredentialPlan(mode="none", ref=None, detail="fixture")

        def orderable(self, engine_type):
            return True

        def describe_relation(self, ref):
            key = ".".join(ref.segments)
            cols = (catalog or {}).get(key)
            if cols is None:
                raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                                   f"{self.id}: no such relation {key}")
            return RelationSchema(ref=ref, columns=tuple(ColumnSpec(name=c, type="text")
                                                         for c in cols))

        def _execute(self, body, params, *, limit=None, timeout_s=None):
            # The fixture does not parse SQL. It finds which relation the body names, hands back the
            # canned rows ROTATED by `scramble`, and reports its columns in the projection's order.
            for key, (cols, rows) in rows_by_relation.items():
                quoted = ".".join('"%s"' % seg for seg in key.split("."))
                if quoted in body or key in body:
                    rot = list(rows)
                    if rot and scramble:
                        k = scramble % len(rot)
                        rot = rot[k:] + rot[:k]
                    take = rot if limit is None else rot[:limit]
                    return ReadResult(columns=tuple(cols),
                                      rows=tuple(dict(zip(cols, r)) for r in take),
                                      row_count=len(take),
                                      truncated=limit is not None and len(rot) > limit)
            raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                               f"{self.id}: the body names no fixture relation")

    _ = ConfigProblem
    return RowsConnector


_MANIFEST = ("planes:\n  data: data\n  ontology: ontology\ndescriptors: data/datasets\n"
             "sources: data/sources\ntransforms: data/transforms\n"
             "runtime:\n  connector: %s\n  connection: connection.yaml\n")


def _seed(root: Path, *, kind="sources", stem="alpha", columns=("gamma_code", "beta_count"),
          schema="alpha_schema", connector=_FIXTURE_ID, table=None, transform=None):
    (root / "data" / kind).mkdir(parents=True, exist_ok=True)
    (root / "mac.project.yaml").write_text(_MANIFEST % connector, encoding="utf-8")
    (root / "connection.yaml").write_text("spec_version: mac.connector/1\nconfig: {}\n",
                                          encoding="utf-8")
    doc = {"table": table if table is not None else {"name": stem, "schema": schema},
           "columns": [{"name": c, "role": "value"} for c in columns]}
    (root / "data" / kind / f"{stem}.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    if transform is not None:
        (root / "data" / "transforms").mkdir(parents=True, exist_ok=True)
        (root / "data" / "transforms" / f"{stem}.yaml").write_text(
            yaml.safe_dump({"produces": transform}), encoding="utf-8")
    return root


def _run(root, *args, rows=None, catalog=None, scramble=0):
    """main() with a fixture connector injected through the registry's `extra` seam."""
    import contextlib

    global EXTRA_CONNECTORS
    if rows is not None:
        EXTRA_CONNECTORS = {_FIXTURE_ID: _fixture_class(rows, catalog, scramble)}
    buf = io.StringIO()
    argv = ["mac_sample.py", str(root)] + list(args)
    old, sys.argv = sys.argv, argv
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = main(argv[1:])
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 2
    finally:
        sys.argv = old
    return rc, buf.getvalue()


_CONCEPT_FIXTURE_ID = "fixture.connector.concept"

_PROJ = re.compile(r'\ASELECT ((?:"[^"]+", )*"[^"]+") FROM ')
_SEED_IN = re.compile(r"md5\('([^']*)'")
_PART = re.compile(r'PARTITION BY "([^"]+)"')
_NOTNULL = re.compile(r'WHERE "([^"]+)" IS NOT NULL')
_EQ = re.compile(r"WHERE \(\"?(\w+)\"? = '([^']*)'\)")
_LIM = re.compile(r"LIMIT (\d+)\Z")
_DISTINCT = re.compile(r'count\(DISTINCT "([^"]+)"\)')
_MKSEL = re.compile(r'\ASELECT DISTINCT "([^"]+)" AS ')


def _concept_fixture_class(rows_by_relation, catalog=None):
    """A connector that READS THE TOOL'S OWN STATEMENT and performs the draw in Python.

    The seed, the projection, the membership predicate, the partition column and the limit are all
    parsed OUT of the emitted SQL rather than handed in by the test — so a case that passes here is
    a case about what this tool ASKED THE ENGINE FOR. It emulates `md5(seed || '|' || cells)` with
    hashlib, which is the claim the SQL makes; that the ENGINE's md5 agrees is the one thing a
    fixture cannot prove and a live run can (and did).
    """
    from sdk.connector.base import (AdapterError, AdapterErrorReason, ColumnSpec, ReadResult,
                                    RelationSchema)
    from sdk.connector.sql import SqlConnector

    class ConceptRowsConnector(SqlConnector):
        id = _CONCEPT_FIXTURE_ID
        supports = frozenset({"describe_relation", "profile_relation"})
        credential_modes = frozenset({"none"})
        permissions = frozenset({"read"})
        probe_cost = "free"
        param_style = ":name"

        @classmethod
        def config_schema(cls):
            return {"type": "object"}

        @classmethod
        def validate_config(cls, conn):
            return []

        @classmethod
        def credential_plan(cls, conn):
            from sdk.connector.base import CredentialPlan
            return CredentialPlan(mode="none", ref=None, detail="fixture")

        def orderable(self, engine_type):
            return True

        def describe_relation(self, ref):
            key = ".".join(ref.segments)
            cols = (catalog or {}).get(key)
            if cols is None:
                raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                                   f"{self.id}: no such relation {key}")
            return RelationSchema(ref=ref, columns=tuple(ColumnSpec(name=c, type="text")
                                                         for c in cols))

        def _execute(self, body, params, *, limit=None, timeout_s=None):
            for key, (cols, rows) in rows_by_relation.items():
                quoted = ".".join('"%s"' % s for s in key.split("."))
                if quoted not in body and key not in body:
                    continue
                keep = list(rows)
                m = _NOTNULL.search(body)
                if m:
                    i = cols.index(m.group(1))
                    keep = [r for r in keep if r[i] is not None and r[i] != ""]
                m = _EQ.search(body)
                if m:
                    i = cols.index(m.group(1))
                    keep = [r for r in keep if str(r[i]) == m.group(2)]
                if " AS member_rows" in body:
                    dk = _DISTINCT.search(body)
                    n = (len({r[cols.index(dk.group(1))] for r in keep}) if dk else None)
                    return ReadResult(
                        columns=("member_rows", "distinct_members", "host_relation_rows"),
                        rows=({"member_rows": len(keep), "distinct_members": n,
                               "host_relation_rows": len(rows)},),
                        row_count=1, truncated=False)
                # THE DATA'S OWN MEMBER LIST — the outer join's right side, parsed out of the
                # tool's statement like everything else here, so a case that passes is a case
                # about what this tool ASKED FOR.
                mk = _MKSEL.match(body)
                if mk:
                    i = cols.index(mk.group(1))
                    vals = sorted({r[i] for r in keep if r[i] is not None}, key=str)
                    n = int(_LIM.search(body.strip()).group(1))
                    out = [{_MK: v} for v in vals[:n]]
                    if limit is not None:
                        out = out[:limit]
                    return ReadResult(columns=(_MK,), rows=tuple(out), row_count=len(out),
                                      truncated=len(vals) > len(out))
                proj = _PROJ.match(body)
                want = [x.strip('"') for x in proj.group(1).split(", ")]
                sm = _SEED_IN.search(body)
                seed = sm.group(1) if sm else None

                def order_key(r):
                    tie = [("" if r[cols.index(c)] is None else str(r[cols.index(c)]))
                           for c in want]
                    if seed is None:      # the RELATION preview: the declared-column total order
                        return ("", tie)
                    return (hashlib.md5(f"{seed}|{'|'.join(tie)}".encode()).hexdigest(), tie)

                keep.sort(key=order_key)
                part = _PART.search(body)
                if part:
                    # THE RANK IS COMPUTED FROM `PARTITION BY`; WHAT IS DONE WITH IT IS READ OFF
                    # THE OUTER CLAUSE, and the difference is the whole point of this fixture.
                    # Emulating stratification on the mere PRESENCE of a window function would
                    # make this connector, not the tool, the thing that guarantees coverage — and
                    # every mutant of the ORDER BY would pass. Measured: it did. So the three
                    # shapes the outer query can take are told apart by what it SAYS:
                    #   · ORDER BY rn ASC, <seeded>  — stratified. Stable sort by rank alone, so
                    #     the seeded order survives inside each rank.
                    #   · WHERE rn = 1               — the collapse this draw replaced.
                    #   · neither                    — a plain seeded window; the rank is unused.
                    pi, rank, ranked = cols.index(part.group(1)), {}, []
                    for r in keep:
                        n_k = rank.get(r[pi], 0) + 1
                        rank[r[pi]] = n_k
                        ranked.append((n_k, r))
                    if f'ORDER BY "{_RN}" ASC' in body:
                        ranked.sort(key=lambda t: t[0])
                        keep = [r for _n, r in ranked]
                    elif f'WHERE "{_RN}" = 1' in body:
                        keep = [r for n, r in ranked if n == 1]
                n = int(_LIM.search(body.strip()).group(1))
                take = keep[:n]
                out = [{c: r[cols.index(c)] for c in want} for r in take]
                if limit is not None:
                    out = out[:limit]
                return ReadResult(columns=tuple(want), rows=tuple(out), row_count=len(out),
                                  truncated=len(keep) > len(out))
            raise AdapterError(AdapterErrorReason.QUERY_FAILED,
                               f"{self.id}: the body names no fixture relation")

    return ConceptRowsConnector


_CONCEPT_MANIFEST = (
    "planes:\n  data: data\n  ontology: ontology\ndescriptors: data/datasets\n"
    "sources: data/sources\ntransforms: data/transforms\n"
    "runtime:\n  connector: %s\n  connection: connection.yaml\n%s")


def _seed_concept(root: Path, *, host="alpha", schema="alpha_schema",
                  host_columns=("gamma_code", "beta_count", "delta_tag"),
                  stem="alpha_concept", name="Alpha", klass="grouping",
                  identity_key="delta_tag", grounding=None, members=True, declared=None,
                  disclosure="publish", connector=_CONCEPT_FIXTURE_ID, extra_hosts=()):
    """A one-concept bundle: a dataset descriptor, a manifest and one concept YAML.

    `extra_hosts` is [(stem, columns)] — the SECOND and further relations a multi-source concept
    grounds on, each with its own dataset descriptor, so the two-relation case is built out of the
    same parts a real bundle is rather than faked in the planner.
    """
    _seed(root, kind="datasets", stem=host, columns=host_columns, schema=schema,
          connector=connector)
    for xstem, xcols in extra_hosts:
        _seed(root, kind="datasets", stem=xstem, columns=xcols, schema=schema,
              connector=connector)
    body = {"publish": ("disclosure:\n  samples:\n    publish: true\n    reason: fixture data\n"),
            "no-reason": "disclosure:\n  samples:\n    publish: true\n",
            # A REASON IS GIVEN HERE ON PURPOSE, so the only thing that can withhold this fixture
            # is the `is True` check — a case that leaned on the missing-reason guard would go
            # green with truthiness restored.
            "string": "disclosure:\n  samples:\n    publish: 'true'\n    reason: fixture data\n",
            "absent": ""}[disclosure]
    (root / "mac.project.yaml").write_text(_CONCEPT_MANIFEST % (connector, body), encoding="utf-8")
    doc = {
        "concept": {"name": name, "class": klass,
                    "identity": {"kind": "code", "canonical_key": identity_key}},
        "grounding": grounding if grounding is not None else {
            "sources": [{"relation": host, "key": "gamma_code",
                         "columns": ["gamma_code", "delta_tag"]}],
            "discriminator": "delta_tag",
            # gamma_code carries NO field_role on purpose: the union must still show it.
            "field_roles": {"delta_tag": "fixture.role.dimension"}},
    }
    if members:
        doc["members"] = {"over": "Host"}
    # AN ENUMERATION THAT LISTS ITS MEMBERS — the outer join's left side, declared. A code here
    # that the fixture data does not carry is the ABSENT member the whole shape exists for.
    if declared is not None:
        doc["values"] = {"closure": "open", "items": [{"code": c} for c in declared]}
    d = root / "ontology" / "concepts"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return root


def _run_concepts(root, *args, rows=None, catalog=None, plane="concepts"):
    import contextlib

    global EXTRA_CONNECTORS
    if rows is not None:
        EXTRA_CONNECTORS = {_CONCEPT_FIXTURE_ID: _concept_fixture_class(rows, catalog)}
    buf = io.StringIO()
    argv = ["mac_sample.py", str(root), "--plane", plane] + list(args)
    old, sys.argv = sys.argv, argv
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = main(argv[1:])
    except SystemExit as exc:
        rc = exc.code if isinstance(exc.code, int) else 2
    finally:
        sys.argv = old
    return rc, buf.getvalue()


def _record(root):
    """The RELATION previews' record, in the data plane."""
    return json.loads((root / "data" / "samples" / RUN_RECORD).read_text(encoding="utf-8"))


def _c_record(root):
    """The CONCEPT draw's record, beside the concept cuts under the ontology plane."""
    p = root / concept_sample_dir(Path(root)) / RUN_RECORD
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _cuts(root):
    """Every concept cut on disk, by filename. The move's population, and the collision's."""
    d = Path(root) / concept_sample_dir(Path(root))
    return sorted(p.name for p in d.glob("*.csv")) if d.is_dir() else []


def _cut(root, name="alpha_concept.sample.csv"):
    return Path(root) / concept_sample_dir(Path(root)) / name


def _cut_bytes(root, name="alpha_concept.sample.csv"):
    """The cut's bytes, or b'' when it is not there. NEVER an exception: a mutant that writes the
    file somewhere else must fail the case that names the rule, not crash the run before the
    remaining cases are reached — a suite that dies is a suite with no denominator."""
    p = _cut(root, name)
    return p.read_bytes() if p.is_file() else b""


def _cut_text(root, name="alpha_concept.sample.csv"):
    return _cut_bytes(root, name).decode("utf-8")


def _entries(root, stem="alpha_concept"):
    """EVERY block of one concept, in record order — the shape a multi-source concept has."""
    return [e for e in (_c_record(root).get("samples") or [])
            if e.get("kind") == CONCEPT_KIND and e.get("stem") == stem]


def _entry(root, stem="alpha_concept", source=1):
    for e in _entries(root, stem):
        if (e.get("source_index") or 1) == source:
            return e
    return {}


def _self_test() -> int:                                                        # noqa: C901
    import tempfile

    bad, cases = [], []

    def case(label, ok, why):
        cases.append((label, ok, why))
        if not ok:
            bad.append(f"{label}: {why}")

    # ── the PURE render table: a mutant per rule, and the refusals ────────────────────────────────
    case("render None -> empty", cell(None) == "", "None must render as an empty field")
    case("render bool before int", (cell(True), cell(False)) == ("true", "false"),
         "a bool must render true/false and never True/1")
    case("render int", cell(7) == "7", "int")
    case("render Decimal keeps scale", cell(Decimal("375.97600")) == "375.97600",
         "a Decimal's scale is part of the value")
    case("render datetime pins 3 digits",
         cell(datetime.datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02 03:04:05.000",
         "the fractional width is inherited from the corpus, not chosen")
    case("render date", cell(datetime.date(2026, 1, 2)) == "2026-01-02", "date")
    case("render array", cell(["a", "b"]) == "[a, b]", "arrays render as [a, b]")
    case("render bytes", cell(b"\x00\xff") == "0x00ff", "bytes render as hex, never replaced text")
    ok = False
    try:
        cell(datetime.datetime(2026, 1, 2, 3, 4, 5, 514321))
    except SampleRenderError:
        ok = True
    case("MUTANT sub-millisecond refuses", ok,
         "truncating a sub-millisecond value could make two distinct values identical")
    ok = False
    try:
        cell(object())
    except SampleRenderError:
        ok = True
    case("MUTANT unrenderable type refuses", ok, "a blanket str() is how a repr lands in a file")

    data = render_sample(["a", "b"], [("2", "x"), ("1", "y")])
    case("dialect: CRLF after every record, header first",
         data == b"a,b\r\n1,y\r\n2,x\r\n", f"got {data!r}")
    case("rows sorted AFTER rendering", data.index(b"1,y") < data.index(b"2,x"),
         "the file must be a function of the row SET, not of the return order")
    ok = False
    try:
        render_sample(["a", "b"], [("1",)])
    except SampleRefused:
        ok = True
    case("MUTANT ragged row refuses", ok, "a row shorter than the header is not the claimed shape")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        rows = {"alpha_schema.alpha": (("gamma_code", "beta_count"),
                                       [("c3", 3), ("c1", 1), ("c2", 2)])}
        cat = {"alpha_schema.alpha": ["gamma_code", "beta_count"]}

        # ── the ORDER BY text: the session-default trap has no other guard ───────────────────────
        r = _seed(base / "order", kind="sources")
        tgts, _f = plan_samples(base / "order")
        cls = _fixture_class(rows, cat)
        conn = cls({})
        tgts[0].select_body_used = False
        tgts[0].ref = _ref(tgts[0])
        body = render_body(conn, tgts[0], limit=20)
        case("ORDER BY names every declared column ASC NULLS LAST",
             body.count("ASC NULLS LAST") == len(tgts[0].columns) and "LIMIT 21" in body,
             f"got {body!r}")
        case("projection is explicit, never SELECT *", "*" not in body,
             "SELECT * lets the engine decide the header")

        # ── RELAYOUT: the same rows returned in a different order must give the same bytes ───────
        def derive_bytes(scramble):
            root = _seed(base / f"relayout{scramble}", kind="sources")
            c = _fixture_class(rows, cat, scramble=scramble)({})
            ts, _ = plan_samples(root)
            res = derive(root, ts, c, limit=20)
            return (root / ts[0].out_path).read_bytes(), res

        b0, res0 = derive_bytes(0)
        b1, _ = derive_bytes(1)
        b2, _ = derive_bytes(2)
        case("NEGATIVE CONTROL byte-identical across three engine return orders",
             b0 == b1 == b2 and b0.startswith(b"gamma_code,beta_count\r\n"),
             f"relayout changed the bytes: {b0!r} vs {b1!r} vs {b2!r}")
        case("NEGATIVE CONTROL a clean cut writes the declared header verbatim",
             res0[0]["state"] == "WROTE" and res0[0]["rows"] == 3, str(res0[0]))

        # ── the bundle-level reject classes ──────────────────────────────────────────────────────
        # Every case below drives main() end to end with the fixture connector injected, so the
        # verdict, the exit code and the refusal TEXT are all exercised — a mutant that is rejected
        # without being ATTRIBUTED to its class proves only that something went wrong.
        wet = {"alpha_schema.alpha": (("gamma_code", "beta_count"),
                                      [("c3", 3), ("c1", 1), ("c2", 2)]),
               "alpha_schema.omega": (("gamma_code", "beta_count"), [])}
        wet_cat = {"alpha_schema.alpha": ["gamma_code", "beta_count"],
                   "alpha_schema.omega": ["gamma_code", "beta_count"]}

        def expect(label, root, want, marker=None, args=(), catalog=None):
            rc, out = _run(root, *args, rows=wet, catalog=wet_cat if catalog is None else catalog)
            ok_ = rc == want and (marker is None or marker in out)
            case(label, ok_, f"exit {rc} (wanted {want})"
                             + ("" if marker is None or marker in out
                                else f", marker {marker!r} absent from output")
                             + f" :: {out.strip().splitlines()[-1] if out.strip() else ''}")
            return out

        good = _seed(base / "good", kind="sources")
        expect("NEGATIVE CONTROL clean bundle exits 0", good, 0, "PASS: mac_sample")
        expect("NEGATIVE CONTROL --verify on an unchanged file exits 0", good, 0, "identical",
               args=("--verify",))
        (good / "data" / "samples" / "alpha.src.sample.csv").write_text(
            "gamma_code,beta_count\r\n", encoding="utf-8")
        expect("MUTANT --verify sees a hand-edited file", good, 1, "DIFFERS", args=("--verify",))

        expect("MUTANT declared column the relation lacks",
               _seed(base / "short", kind="sources",
                     columns=("gamma_code", "beta_count", "delta_flag")),
               1, "which the relation does not have")
        expect("MUTANT relation column the descriptor lacks",
               _seed(base / "xtra", kind="sources", columns=("gamma_code",)),
               1, "which the descriptor does not declare")
        expect("MUTANT relation does not exist and no transform body",
               _seed(base / "gone", kind="sources", stem="zeta"),
               1, "does not exist")
        expect("MUTANT zero rows refuses and writes nothing",
               _seed(base / "empty0", kind="sources", stem="omega"), 1, "returned 0 rows")
        case("MUTANT zero rows wrote no file",
             not (base / "empty0" / "data" / "samples" / "omega.src.sample.csv").exists(),
             "a zero-row preview is a header with no evidence under it and must not reach disk")
        expect("MUTANT no table.schema",
               _seed(base / "noschema", kind="sources", table={"name": "alpha"}),
               1, "declares no table.schema")
        expect("MUTANT duplicate declared columns (case-insensitively)",
               _seed(base / "dup", kind="sources", columns=("gamma_code", "GAMMA_CODE")),
               1, "more than once")
        expect("MUTANT descriptor declares no columns",
               _seed(base / "nocols", kind="sources", columns=()), 1, "columns[] is empty")
        expect("MUTANT --stems names no descriptor", good, 1, "which no descriptor",
               args=("nosuchstem",))
        bare = base / "bare"
        bare.mkdir()
        (bare / "data").mkdir()
        expect("MUTANT empty population refuses (exit 2), verbatim marker", bare, 2,
               D.empty_mark("descriptor"))
        expect("MUTANT no runtime.connector", _no_connector(base / "noconn"), 2,
               "no runtime.connector")
        expect("MUTANT unresolvable connector id",
               _seed(base / "badid", kind="sources", connector="acme.connector.nope"), 2,
               "acme.connector.nope")
        expect("MUTANT transform and descriptor disagree about the relation",
               _seed(base / "twohomes", kind="datasets", stem="beta", schema="served",
                     transform={"relation": "other_schema.beta"}),
               1, "disagree")
        rc, out = _run(good, "--limit", "0", rows=wet, catalog=wet_cat)
        case("MUTANT --limit 0 is rejected by the parser", rc == 2, f"exit {rc}")
        rc, out = _run(good, "--dry-run", rows=wet, catalog=wet_cat)
        case("NEGATIVE CONTROL --dry-run renders a statement and reads nothing",
             rc == 0 and "LIMIT 21" in out and "nothing was written" in out,
             f"exit {rc}: {out[-300:]}")

        # ── the transform-body route: a dataset whose relation is not materialised yet ───────────
        ds = _seed(base / "body", kind="datasets", stem="beta", schema="served",
                   columns=("gamma_code", "beta_count"),
                   transform={"relation": "served.beta", "sql_file": "data/transforms/beta.sql"})
        (ds / "data" / "transforms" / "beta.sql").write_text(
            'CREATE OR REPLACE VIEW served.beta AS\nSELECT * FROM alpha_schema.alpha;\n',
            encoding="utf-8")
        # The catalog is EMPTY, so served.beta does not exist; the fixture's rows are keyed at the
        # relation the transform body reads, which is the point of the route.
        rowsb = {"alpha_schema.alpha": (("gamma_code", "beta_count"), [("c1", 1)])}
        c = _fixture_class(rowsb, {})({})
        ts, _ = plan_samples(ds, planes=("datasets",))
        res = derive(ds, ts, c, limit=20)
        case("NEGATIVE CONTROL a dataset with no live relation is cut from its transform body",
             res[0]["state"] == "WROTE" and res[0]["derived_from"] == "transform-body"
             and any("PROPOSAL" in n for n in res[0]["notes"]), str(res[0]))

        # ══ THE CONCEPT DRAW ══════════════════════════════════════════════════════════════════
        # Every case below drives main() with a fixture connector that PARSES THE EMITTED SQL and
        # performs the draw in Python, so the seed, the projection, the membership predicate, the
        # partition and the limit are all read back out of the statement this tool actually wrote.
        crows = {"alpha_schema.alpha": (
            ("gamma_code", "beta_count", "delta_tag"),
            [("c1", 1, "t1"), ("c2", 2, "t1"), ("c3", 3, "t2"),
             ("c4", 4, "t2"), ("c5", 5, "t3"), ("c6", 6, None)]),
            # THE SECOND GROUNDING RELATION, and it DISAGREES with the first on purpose: three
            # rows where the first has six, and a `--` sentinel the first does not carry. That is
            # the measured shape a single-block draw hid — one relation's value set standing in
            # for a concept that spans two.
            "alpha_schema.zeta": (
                ("zeta_code", "delta_tag"),
                [("c1", "t1"), ("c7", "t4"), ("--", None)])}
        ccat = {"alpha_schema.alpha": ["gamma_code", "beta_count", "delta_tag"],
                "alpha_schema.zeta": ["zeta_code", "delta_tag"]}

        def concept_run(sub, *args, **kw):
            root = _seed_concept(base / sub, **kw)
            return root, _run_concepts(root, *args, rows=crows, catalog=ccat)

        r, (rc, out) = concept_run("c_ok")
        e = _entry(r)
        case("NEGATIVE CONTROL a concept draw exits 0 and writes one file per concept",
             rc == 0 and e.get("state") == "WROTE" and _cut(r).is_file(),
             f"exit {rc}: {out.strip().splitlines()[-1] if out.strip() else ''}")
        header = (_cut_text(r).splitlines() or [""])[0]
        case("MUTANT the sample's columns are the Fields table's UNION, not field_roles",
             e.get("columns") == ["gamma_code", "delta_tag"] and header == "gamma_code,delta_tag",
             f"columns {e.get('columns')} header {header!r} — `gamma_code` is a "
             f"grounding.sources[].columns entry carrying NO field_role; a sample keyed on "
             f"field_roles alone would drop it while the Fields table above still lists it")
        # ALL FOUR DENOMINATORS AT ONCE, because they are four different numbers over one block:
        # 6 host rows, 5 of them claimed as member rows, 3 distinct members among those 5, and the
        # POPULATION the window is measured against is the member rows. A mutant that takes the
        # host as the population reads 6; one that keeps the old member-grain population reads 3.
        case("MUTANT the population is the concept's MEMBER ROWS, not the host relation",
             (e.get("population"), e.get("member_rows"), e.get("distinct_members"),
              e.get("relation_rows")) == (5, 5, 3, 6)
             and e.get("member_predicate") == '"delta_tag" IS NOT NULL'
             and e.get("population_unit") == "member row",
             f"population {e.get('population')} member_rows {e.get('member_rows')} distinct "
             f"{e.get('distinct_members')} relation_rows {e.get('relation_rows')} predicate "
             f"{e.get('member_predicate')!r} unit {e.get('population_unit')!r}")
        case("MUTANT a members: block draws STRATIFIED, not ONE REPRESENTATIVE ROW per member",
             e.get("member_grain") == "key" and e.get("draw") == "stratified"
             and e.get("rows") == 5 and e.get("rows_from_data") == 5
             and e.get("members_present") == e.get("members_total") == 3
             and e.get("truncated") is False,
             f"grain {e.get('member_grain')} draw {e.get('draw')} rows {e.get('rows')} "
             f"members {e.get('members_present')} of {e.get('members_total')} — collapsing to one "
             f"row per member throws the data away and reads as though the representative row "
             f"DEFINES the member")
        case("NEGATIVE CONTROL a population below the limit shows ALL of it, with every number",
             e.get("rows") == e.get("rows_from_data") == e.get("population")
             == e.get("member_rows") == 5 and e.get("distinct_members") == 3
             and e.get("truncated") is False,
             f"{e.get('rows')} of {e.get('population')} member row(s) carrying "
             f"{e.get('distinct_members')} member(s)")
        case("NEGATIVE CONTROL the record carries the seed, the grain and the basis",
             e.get("seed") == DEFAULT_SEED and e.get("member_basis").startswith(
                 "grounding.discriminator:") and "members:" in (e.get("member_grain_basis") or ""),
             str({k: e.get(k) for k in ("seed", "member_basis", "member_grain_basis")})[:200])
        case("NEGATIVE CONTROL the record names WHERE the column set came from",
             "_grounding_fields" in (e.get("columns_from") or ""), str(e.get("columns_from")))
        rcd, outd = _run_concepts(base / "c_ok", "--dry-run", rows=crows, catalog=ccat)
        case("MUTANT the draw asks the ENGINE for limit+1 and projects explicitly",
             rcd == 0 and "LIMIT 41" in outd and "SELECT *" not in outd
             and "PARTITION BY \"delta_tag\"" in outd, f"exit {rcd}: {outd[-200:]}")

        # ── REPRODUCIBILITY: the same seed returns the same rows, a different seed does not ─────
        b_a = _cut_bytes(r)
        _run_concepts(r, rows=crows, catalog=ccat)
        b_a2 = _cut_bytes(r)
        case("NEGATIVE CONTROL the SAME seed over the same data returns the same rows twice",
             b_a == b_a2, "a second run at one seed moved the bytes, so a page would churn on "
                          "data that did not")
        rs1, (rcs1, _o) = concept_run("c_seed1", "--concept-limit", "2", members=False)
        rs2, (rcs2, _o) = concept_run("c_seed2", "--concept-limit", "2", members=False)
        # THE SAME LIMIT ON BOTH SIDES, deliberately: a second run at a different LIMIT would
        # differ for the trivial reason and the case would pass with the seed removed entirely.
        _run_concepts(rs2, "--concept-limit", "2", "--seed", "a-second-seed",
                      rows=crows, catalog=ccat)
        s1 = _cut_bytes(rs1)
        s2 = _cut_bytes(rs2)
        case("MUTANT a DIFFERENT seed draws a different subset of the same population",
             rcs1 == rcs2 == 0 and s1 != s2,
             f"two seeds drew the same 2 of 5 rows ({s1!r}), so the seed is not reaching the draw")
        rc3, out3 = _run_concepts(r, "--seed", "not a legal seed!", rows=crows, catalog=ccat)
        case("MUTANT a seed outside the closed charset is refused, never escaped",
             rc3 == 2 and "CLOSED rather than escaped" in out3, f"exit {rc3}: {out3[-160:]}")

        # ══ THE STRATIFIED DRAW: EVERY MEMBER APPEARS, AND THE WINDOW IS STILL FULL ═══════════
        # A DELIBERATELY SKEWED POPULATION, because a balanced one cannot tell the two draws
        # apart: 19 rows carrying `t1` and exactly ONE carrying `t2`. A plain seeded window of 3
        # rows over that takes the rare member about three times in twenty; the stratified window
        # takes it every time, and "every time" is the entire claim being made.
        srows = {"alpha_schema.alpha": (
            ("gamma_code", "beta_count", "delta_tag"),
            [(f"s{i:02d}", i, "t1") for i in range(19)] + [("rare", 99, "t2")])}
        scat = {"alpha_schema.alpha": ["gamma_code", "beta_count", "delta_tag"]}

        def strat_run(sub, *args, rows=srows, **kw):
            root = _seed_concept(base / sub, **kw)
            return root, _run_concepts(root, *args, rows=rows, catalog=scat)

        rS, (rcS, outS) = strat_run("c_strat", "--concept-limit", "3")
        eS, tS = _entry(rS), _cut_text(rS)
        case("MUTANT a member the data HAS is dropped when the window is smaller than the rows",
             rcS == 0 and eS.get("rows") == eS.get("rows_from_data") == 3
             and eS.get("members_present") == eS.get("members_total") == 2
             and ",t2\r\n" in tS and ",t1\r\n" in tS,
             f"{eS.get('rows')} row(s) carrying {eS.get('members_present')} of "
             f"{eS.get('members_total')} member(s): {tS!r} — 19 rows of one member and 1 of "
             f"another, and a plain window of 3 takes the rare one about three times in twenty. "
             f"Stratified, the guarantee is EVERY time")
        case("NEGATIVE CONTROL the window is still FULL — every member costs one row, not the rest",
             eS.get("rows") == 3 and eS.get("population") == 20
             and eS.get("truncated") is True and eS.get("rows_declared_only") == 0,
             f"{eS.get('rows')} of {eS.get('population')} — a draw that guaranteed coverage by "
             f"collapsing to one row per member would show 2 here, which is the 15-row AgeBand "
             f"cut that threw the data away")

        # ── THE OUTER JOIN'S UNMATCHED HALF: a DECLARED member the data never carries ──────────
        # Measured 0 of 7 on the live bundle, and that is exactly why it is seeded here: a shape
        # nothing in the estate currently exercises is a shape that rots unless a mutant guards it.
        rA, (rcA, outA) = strat_run("c_absent_member", members=False,
                                    declared=("t1", "t2", "t9"))
        eA, tA = _entry(rA), _cut_text(rA)
        case("MUTANT a DECLARED member with NO row in the data is dropped from the cut",
             rcA == 0 and eA.get("members_absent") == ["t9"]
             and eA.get("rows_declared_only") == 1 and eA.get("rows_from_data") == 20
             and eA.get("rows") == 21
             and eA.get("members_present") == eA.get("members_total") == 3
             and "\r\n,t9\r\n" in tA,
             f"absent {eA.get('members_absent')} · {eA.get('rows_from_data')} data row(s) + "
             f"{eA.get('rows_declared_only')} declared-only · members "
             f"{eA.get('members_present')} of {eA.get('members_total')} · {tA[-40:]!r} — a "
             f"register declaring a code the warehouse never carries must be VISIBLE, with its "
             f"key and empty cells, not silently absent")
        case("NEGATIVE CONTROL the declared list is read from the concept and NAMED in the record",
             eA.get("members_declared") == 3
             and "values.items" in (eA.get("members_declared_from") or "")
             and eA.get("members_undeclared") == 0 and eA.get("distinct_members") == 2,
             f"declared {eA.get('members_declared')} from "
             f"{eA.get('members_declared_from')!r}, data carries "
             f"{eA.get('distinct_members')} — 'no member is absent' and 'there was nothing to "
             f"compare against' must not render as the same answer")

        # ── MEMBERS > LIMIT: one row per member as far as the window reaches, and SAY SO ───────
        mrows = {"alpha_schema.alpha": (
            ("gamma_code", "beta_count", "delta_tag"),
            [(f"m{i}", i, f"t{i % 5}") for i in range(10)])}
        rM, (rcM, outM) = strat_run("c_manymembers", "--concept-limit", "3", rows=mrows)
        eM = _entry(rM)
        case("MUTANT members OUTNUMBER the limit and the truncation is not disclosed",
             rcM == 0 and eM.get("rows") == 3 and eM.get("members_present") == 3
             and eM.get("members_total") == 5 and eM.get("members_unshown") == 2
             and eM.get("members_truncated") is True and eM.get("truncated") is True,
             f"{eM.get('members_present')} of {eM.get('members_total')} member(s) shown, "
             f"{eM.get('members_unshown')} unshown, members_truncated="
             f"{eM.get('members_truncated')} — cutting silently at the limit is the same defect "
             f"as a gate reporting PASS over a denominator it did not print")

        # ── REPRODUCIBILITY OF THE STRATIFIED DRAW, in both directions at once ─────────────────
        b_s1 = _cut_bytes(rS)
        _run_concepts(rS, "--concept-limit", "3", rows=srows, catalog=scat)
        b_s2 = _cut_bytes(rS)
        _run_concepts(rS, "--concept-limit", "3", "--seed", "a-second-seed",
                      rows=srows, catalog=scat)
        b_s3 = _cut_bytes(rS)
        e_s3 = _entry(rS)
        case("MUTANT the SAME seed draws a DIFFERENT set of stratified rows on a second run",
             b_s1 == b_s2 and b_s1 != b"",
             f"{b_s1!r} then {b_s2!r} — stratifying must not cost determinism: two runs at one "
             f"seed over one population that moved not at all churned the file")
        case("NEGATIVE CONTROL a different seed moves the ROWS and never the MEMBER COVERAGE",
             b_s3 != b_s1 and e_s3.get("members_present") == e_s3.get("members_total") == 2,
             f"{b_s1!r} vs {b_s3!r} at {e_s3.get('members_present')} of "
             f"{e_s3.get('members_total')} member(s) — the seed chooses WHICH rows represent a "
             f"member; it has no vote on WHETHER the member appears")

        # ── the grain is DECLARED: no members: block means a member is a ROW ────────────────────
        r4, (rc4, _o) = concept_run("c_row", members=False)
        e4 = _entry(r4)
        case("MUTANT no members: block draws at ROW grain — every member row, not one per key",
             rc4 == 0 and e4.get("member_grain") == "row" and e4.get("rows") == 5
             and e4.get("population") == 5,
             f"grain {e4.get('member_grain')} rows {e4.get('rows')} pop {e4.get('population')}")
        r5, (rc5, _o) = concept_run("c_hidden", identity_key="beta_count")
        e5 = _entry(r5)
        case("MUTANT a members: block whose key the sample does not SHOW falls back to row grain",
             rc5 == 0 and e5.get("member_grain") == "row"
             and any("invisible to the reader" in n for n in e5.get("notes") or []),
             f"grain {e5.get('member_grain')} notes {e5.get('notes')}")

        # ── the limit, and the two numbers a truncated draw owes ────────────────────────────────
        r6, (rc6, _o) = concept_run("c_lim", "--concept-limit", "2", members=False)
        e6 = _entry(r6)
        case("MUTANT a limit below the population truncates AND records both numbers",
             rc6 == 0 and e6.get("rows") == 2 and e6.get("population") == 5
             and e6.get("truncated") is True,
             f"{e6.get('rows')} of {e6.get('population')}, truncated={e6.get('truncated')}")

        # ── DISCLOSURE, and it fails closed ─────────────────────────────────────────────────────
        for sub, mode, why in (("c_absent", "absent", "no declaration at all"),
                               ("c_string", "string", "publish: 'true' as a STRING"),
                               ("c_noreason", "no-reason", "publish: true with no reason")):
            r7, (rc7, out7) = concept_run(sub, disclosure=mode)
            e7 = _entry(r7)
            case(f"MUTANT disclosure withholds — {why}",
                 rc7 == 0 and e7.get("state") == "WITHHELD" and e7.get("file") is None
                 and not _cuts(r7),
                 f"exit {rc7} state {e7.get('state')} file {e7.get('file')!r}")
            case(f"NEGATIVE CONTROL a withheld sample still records its population — {why}",
                 e7.get("population") == 5 and e7.get("member_rows") == 5
                 and e7.get("relation_rows") == 6,
                 f"a withheld section that cannot state its denominator is indistinguishable "
                 f"from one with nothing to show: {e7.get('population')} / "
                 f"{e7.get('member_rows')} / {e7.get('relation_rows')}")

        # ── the reject classes the PLAN can see with no engine ──────────────────────────────────
        r8, (rc8, out8) = concept_run(
            "c_homeless", grounding={"sources": [{"relation": "alpha", "key": "gamma_code",
                                                  "columns": ["gamma_code"]}],
                                     "field_roles": {"zeta_extra": "fixture.role.dimension"}})
        case("MUTANT a field_role column under NO source is refused, named and counted",
             rc8 == 1 and "UNPLACEABLE_FIELD" in out8 and "zeta_extra" in out8, f"exit {rc8}")
        r9, (rc9, out9) = concept_run(
            "c_nocol", grounding={"sources": [{"relation": "alpha", "key": "gamma_code",
                                               "columns": ["gamma_code", "omega_absent"]}],
                                  "field_roles": {"gamma_code": "fixture.role.key"}})
        case("MUTANT a declared field the host relation does not have is a finding",
             rc9 == 1 and "FIELD_NOT_IN_HOST" in out9, f"exit {rc9}")
        r10, (rc10, out10) = concept_run(
            "c_nohost", grounding={"sources": [{"relation": "nosuchrelation", "key": "x",
                                                "columns": ["gamma_code"]}],
                                   "field_roles": {"gamma_code": "fixture.role.key"}})
        case("MUTANT a concept grounding on a relation no descriptor declares is a finding",
             rc10 == 1 and "NO_HOST_DATASET" in out10, f"exit {rc10}")
        r11, (rc11, out11) = concept_run(
            "c_zero", grounding={"sources": [{"relation": "alpha", "key": "gamma_code",
                                              "columns": ["gamma_code", "delta_tag"]}],
                                 "value_filter": "delta_tag = 'nobody'",
                                 "discriminator": "delta_tag",
                                 "field_roles": {"delta_tag": "fixture.role.dimension"}})
        case("MUTANT a concept claiming ZERO members refuses and writes no file",
             rc11 == 1 and "claims 0 of" in out11
             and not _cuts(r11), f"exit {rc11}: {out11[-200:]}")
        zb, _zf = plan_concept_samples(r11, _ontology_plane(r11),
                                       plan_samples(r11, planes=("datasets",))[0])
        case("NEGATIVE CONTROL value_filter OUTRANKS the discriminator, as the generator rules",
             len(zb) == 1 and zb[0].member_where == "(delta_tag = 'nobody')"
             and zb[0].member_basis.startswith("grounding.value_filter:"),
             f"{[ (x.member_where, x.member_basis) for x in zb ]} — the membership predicate must "
             f"be mac_generate_ontology_tests.member_population's, not a second rule written here")

        # ══ THE PLANE: A CONCEPT SAMPLE IS AN ONTOLOGY ARTIFACT ═══════════════════════════════
        # The operator's ruling, and it is structural: `data/` is the DATA plane and the concept
        # draw's population is defined by the CONCEPT (grounding.discriminator / value_filter) at
        # the CONCEPT's own columns, so nothing in the data plane can say what the file is.
        case("MUTANT the concept cut lands under the ONTOLOGY plane, not the data plane",
             e.get("file") == "ontology/samples/alpha_concept.sample.csv"
             and (r / "ontology" / "samples" / "alpha_concept.sample.csv").is_file()
             and not (r / "data" / "samples" / "concepts").exists(),
             f"file {e.get('file')!r}; a concept sample under data/ is the data plane claiming an "
             f"artifact only the ontology can define")
        case("MUTANT the RELATION preview does NOT move with it — the two draws stay apart",
             _seed_concept(base / "c_planes") is not None
             and _run_concepts(base / "c_planes", rows=crows, catalog=ccat,
                               plane="datasets")[0] == 0
             and (base / "c_planes" / "data" / "samples" / "alpha.sample.csv").is_file()
             and not (base / "c_planes" / "ontology" / "samples").exists(),
             "the relation preview belongs to the data plane and must be untouched by the move")
        case("MUTANT the ontology plane is read from the MANIFEST, never hard-coded",
             concept_sample_dir(Path("/nowhere"),
                                Path("/nowhere/semantics")) == "semantics/samples",
             "a bundle that declares planes.ontology elsewhere must get its cuts there")

        # ══ ONE BLOCK PER GROUNDING SOURCE ════════════════════════════════════════════════════
        # The two-relation concept: `alpha` carries gamma_code + delta_tag, `zeta` carries
        # zeta_code. The discriminator (delta_tag) is a column of alpha and NOT of zeta's
        # descriptor, so the two blocks have different populations — which is the point.
        _TWO = {"sources": [{"relation": "alpha", "key": "gamma_code",
                             "columns": ["gamma_code", "delta_tag"]},
                            {"relation": "zeta", "key": "zeta_code",
                             "columns": ["zeta_code"]}],
                "discriminator": "delta_tag",
                "field_roles": {"delta_tag": "fixture.role.dimension",
                                "zeta_code": "fixture.role.key"}}
        # zeta's DESCRIPTOR declares only `zeta_code` — the discriminator is not a column of it,
        # which is the measured shape (a concept's discriminator lives on one of its relations and
        # the others are narrowed by nothing). The fixture relation carries a second column the
        # descriptor does not declare, and that is normal here: a concept declares a SUBSET.
        r13, (rc13, out13) = concept_run("c_two", members=False, grounding=_TWO,
                                         extra_hosts=(("zeta", ("zeta_code",)),))
        two = _entries(r13)
        b1 = _entry(r13, source=1)
        b2 = _entry(r13, source=2)
        case("MUTANT a concept grounding on TWO relations draws TWO blocks, not one",
             rc13 == 0 and len(two) == 2
             and [x.get("relation") for x in two] == ["alpha_schema.alpha", "alpha_schema.zeta"]
             and [x.get("source_index") for x in two] == [1, 2]
             and {x.get("source_count") for x in two} == {2},
             f"{len(two)} block(s): {[(x.get('relation'), x.get('source_index')) for x in two]} — "
             f"drawing only sources[0] states one relation's answer for a concept that spans two")
        case("MUTANT each block carries ITS OWN columns, population and denominators",
             b1.get("columns") == ["gamma_code", "delta_tag"]
             and b2.get("columns") == ["zeta_code"]
             and (b1.get("population"), b1.get("relation_rows")) == (5, 6)
             and (b2.get("population"), b2.get("relation_rows")) == (3, 3)
             and b1.get("member_predicate") == '"delta_tag" IS NOT NULL'
             and b2.get("member_predicate") is None,
             f"block 1 {b1.get('columns')} {b1.get('population')} of {b1.get('relation_rows')} · "
             f"block 2 {b2.get('columns')} {b2.get('population')} of {b2.get('relation_rows')} — "
             f"two blocks sharing one count is one relation's answer printed twice")
        case("NEGATIVE CONTROL the two blocks DISAGREE and both are drawn truthfully",
             b1.get("population") != b2.get("population")
             and "--" in _cut_text(r13, "alpha_concept.zeta.sample.csv")
             and "--" not in _cut_text(r13, "alpha_concept.alpha.sample.csv")
             and _cut_text(r13, "alpha_concept.zeta.sample.csv") != "",
             "the sentinel one source carries and the other does not is the fact a single block "
             "plus a note hid; nothing here editorialises it, the reader sees both value sets")
        case("MUTANT two blocks of one concept CANNOT write over each other",
             sorted(_cuts(r13)) == ["alpha_concept.alpha.sample.csv",
                                    "alpha_concept.zeta.sample.csv"]
             and b1.get("file") != b2.get("file")
             and {b1.get("file"), b2.get("file")} == {f"ontology/samples/{n}" for n in _cuts(r13)},
             f"{_cuts(r13)} — one filename for two populations leaves whichever ran last on disk "
             f"under a name that claims to be both")
        case("NEGATIVE CONTROL the blocks' columns ARE the Fields table, concatenated",
             [col for x in two for col in x["columns"]] == ["gamma_code", "delta_tag", "zeta_code"]
             and {x.get("fields_declared") for x in two} == {3},
             f"{[x['columns'] for x in two]} of {b1.get('fields_declared')} Fields row(s)")
        case("MUTANT a source whose relation lacks the discriminator says so and is NOT narrowed",
             b2.get("member_basis") == ""
             and any("narrowed by nothing" in n for n in b2.get("notes") or []),
             f"block 2 basis {b2.get('member_basis')!r} notes {b2.get('notes')}")
        case("MUTANT the distinct count NAMES its column, and is absent where none was counted",
             b1.get("count_key") == "delta_tag" and b1.get("distinct_members") == 3
             and b2.get("count_key") is None and b2.get("distinct_members") is None,
             f"block 1 counts {b1.get('distinct_members')} distinct "
             f"{b1.get('count_key')!r} · block 2 counts {b2.get('distinct_members')} distinct "
             f"{b2.get('count_key')!r} — the canonical key is a column of source 1 and not of "
             f"source 2, so one block CAN count members and the other cannot. A count with no "
             f"named column, or a column silently substituted from the other relation, both "
             f"state something the concept did not declare")
        case("MUTANT with EVERY source drawn, nothing is left undrawn and no note claims it is",
             [x.get("fields_undrawn") for x in two] == [[], []]
             and not any("NO block" in n for x in two for n in x.get("notes") or []),
             f"{[x.get('fields_undrawn') for x in two]} — the old one-block draw named these "
             f"columns as unreachable; they are drawn now and the note must go with them")
        r1s, (rc1s, _o) = concept_run("c_single")
        one = _entries(r1s)
        case("NEGATIVE CONTROL a single-source concept is UNCHANGED: one block, the bare name",
             rc1s == 0 and len(one) == 1 and one[0].get("source_index") == 1
             and one[0].get("source_count") == 1
             and _cuts(r1s) == ["alpha_concept.sample.csv"]
             and _cut_bytes(r1s) == b_a and b_a != b"",
             f"{len(one)} block(s), cuts {_cuts(r1s)} — 14 of 17 concepts on the measured bundle "
             f"are this shape, and the move owes them the same BYTES at a new path")

        # ── AND THE CASE THAT SURVIVES: a Fields column in NO block, because ONE source failed ──
        _HALF = {"sources": [{"relation": "alpha", "key": "gamma_code",
                              "columns": ["gamma_code", "delta_tag"]},
                             {"relation": "nosuchrelation", "key": "x",
                              "columns": ["omega_absent"]}],
                 "discriminator": "delta_tag",
                 "field_roles": {"delta_tag": "fixture.role.dimension",
                                 "omega_absent": "fixture.role.key"}}
        r14, (rc14, out14) = concept_run("c_half", members=False, grounding=_HALF)
        h1 = _entry(r14)
        case("MUTANT one source refused does NOT refuse the concept — the other still draws",
             rc14 == 1 and len(_entries(r14)) == 1 and h1.get("relation") == "alpha_schema.alpha"
             and "NO_HOST_DATASET" in out14,
             f"exit {rc14}, {len(_entries(r14))} block(s) — a finding about source 2 must not "
             f"delete source 1's evidence")
        case("MUTANT a Fields column in NO block is STILL disclosed, on every block",
             h1.get("fields_undrawn") == ["omega_absent"]
             and h1.get("fields_declared") == 3
             and any("NO block" in n for n in h1.get("notes") or []),
             f"undrawn {h1.get('fields_undrawn')} of {h1.get('fields_declared')} notes "
             f"{h1.get('notes')} — this is the case the note still has to cover, and it is the "
             f"only one: a source that could not be drawn at all")

        # ══ TWO RECORDS, ONE PER DRAW, NEITHER RESTAMPING THE OTHER ═══════════════════════════
        r12 = _seed_concept(base / "c_both")
        _run_concepts(r12, "--limit", "7", rows=crows, catalog=ccat, plane="datasets")
        rel_before = (root_rec := _record(r12)) and list(root_rec.get("samples") or [])
        rel_bytes = (r12 / "data" / "samples" / RUN_RECORD).read_bytes()
        case("NEGATIVE CONTROL a relations-only run writes NO concept record at all",
             not (r12 / "ontology" / "samples" / RUN_RECORD).is_file()
             and not (r12 / "ontology" / "samples").exists(),
             "a run that drew no concept must not leave a record claiming it did")
        _run_concepts(r12, rows=crows, catalog=ccat)
        case("MUTANT a concept run does not TOUCH the relation record — not one byte",
             (r12 / "data" / "samples" / RUN_RECORD).read_bytes() == rel_bytes,
             f"the shared record re-stamped every carried preview with the concept run's own "
             f"`engine` and `limit`; {len(rel_before)} relation entr(ies) were cut at --limit 7 "
             f"and a rewrite puts this run's limit over them")
        case("MUTANT the relation record still holds ONLY relations, the concept record ONLY "
             "concepts",
             all(x.get("kind") != CONCEPT_KIND for x in _record(r12).get("samples") or [])
             and all(x.get("kind") == CONCEPT_KIND for x in _c_record(r12).get("samples") or [])
             and len(_c_record(r12).get("samples") or []) == 1,
             f"relation kinds {[x.get('kind') for x in _record(r12).get('samples') or []]} · "
             f"concept kinds {[x.get('kind') for x in _c_record(r12).get('samples') or []]} — "
             f"one `samples[]` holding both is what let a concept entry shadow a source preview "
             f"of the same stem in check_sample_matches_descriptor's stem-keyed map")
        case("NEGATIVE CONTROL neither record copies the other; each POINTS at it",
             _record(r12).get("concept_record") == f"ontology/samples/{RUN_RECORD}"
             and _c_record(r12).get("relation_record") == f"data/samples/{RUN_RECORD}"
             and "concept_draw" not in _record(r12) and "seed" not in _record(r12)
             and "limit" not in _c_record(r12) and "order" not in _c_record(r12),
             f"a split that copied a fact into both files would be one record in two places that "
             f"can disagree: {sorted(_record(r12))} · {sorted(_c_record(r12))}")
        case("NEGATIVE CONTROL each record's stamps are ITS OWN run's, never the other's",
             _record(r12).get("limit") == 7
             and (_c_record(r12).get("concept_draw") or {}).get("limit")
             == DEFAULT_CONCEPT_LIMIT
             and _c_record(r12).get("engine") == _CONCEPT_FIXTURE_ID,
             f"relation limit {_record(r12).get('limit')} (cut at 7) · concept limit "
             f"{(_c_record(r12).get('concept_draw') or {}).get('limit')} — one `limit` key for "
             f"two draws could only ever be true of one of them")

    total = len(cases)
    if bad:
        print(f"FAIL: {NAME} self-test — {len(bad)} of {total} case(s) failed")
        for b in bad:
            print(f"  ✗ {b}", file=sys.stderr)
        return 1
    mutants = len([c for c in cases if c[0].startswith("MUTANT")])
    controls = len([c for c in cases if "NEGATIVE CONTROL" in c[0]])
    print(f"PASS: {NAME} self-test — {total}/{total} case(s): {mutants} mutant(s) of the rule "
          f"(short header, extra relation column, absent relation, zero rows and no file on disk, "
          f"no table.schema, duplicate columns, no columns, unknown stem, empty population, no "
          f"connector, unresolvable connector, two homes for one relation name, --limit 0, a "
          f"hand-edited file, sub-millisecond precision, an unrenderable type, a ragged row; and "
          f"for the CONCEPT draw — a column set narrowed to field_roles, a population taken as the "
          f"host relation, a members: block ignored, a members: block whose key the sample does "
          f"not show, a seed that does not reach the draw, a seed outside the closed charset, a "
          f"limit below the population, three disclosure spellings that must withhold, a "
          f"field_role under no source, a declared field the host lacks, a host no descriptor "
          f"declares, a concept claiming zero members, a distinct count with no named column; "
          f"for the PLANE — a cut written under data/ "
          f"instead of the ontology, a relation preview dragged along with it, a hard-coded "
          f"ontology directory; for the PER-SOURCE BLOCKS — only sources[0] drawn, one count "
          f"reused across two blocks, two blocks on one filename, a source lacking the "
          f"discriminator silently narrowed, an undrawn-columns note kept after the columns were "
          f"drawn, one source's refusal deleting another source's block, a Fields column in no "
          f"block left undisclosed; for the STRATIFIED DRAW — a member the data has dropped from "
          f"a window smaller than the rows, a DECLARED member with no row in the data dropped "
          f"from the cut, members outnumbering the limit with the truncation undisclosed, the "
          f"same seed drawing a different set on a second run; and for the SPLIT RECORD — a "
          f"concept run rewriting the relation record, one samples[] holding both planes) and "
          f"{controls} negative "
          f"control(s) (byte-identity across three engine return orders, a clean cut, --verify on "
          f"an unchanged file, --dry-run with no read, a dataset cut from its transform body; and "
          f"for the CONCEPT draw — a clean draw, the union column set, all three denominators, the "
          f"seed and grain recorded, the column set's provenance named, the same seed twice, a "
          f"population below the limit shown whole, a withheld sample that still states its "
          f"population, value_filter outranking the discriminator, two sources disagreeing and "
          f"both drawn, the blocks' columns being the Fields table concatenated, a single-source "
          f"concept unchanged at the new path, a relations-only run writing no concept record, "
          f"neither record copying the other, each record's stamps being its own run's, the "
          f"stratified window staying FULL rather than collapsing to one row per member, the "
          f"declared member list read from the concept and named in the record, and a different "
          f"seed moving the rows while never moving the member coverage)")
    return 0


def _no_connector(root: Path) -> Path:
    _seed(root, kind="sources")
    (root / "mac.project.yaml").write_text(
        "planes:\n  data: data\ndescriptors: data/datasets\nsources: data/sources\n",
        encoding="utf-8")
    return root


if __name__ == "__main__":
    raise SystemExit(main())
