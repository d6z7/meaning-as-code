#!/usr/bin/env python3
"""mac_sample.py — cut the 20-row preview of a relation FROM THE LIVE DATA, through the connector.

    python3 tools/mac_sample.py <root> [stem ...] [--plane sources|datasets|both]
                                [--limit 20] [--dry-run] [--verify] [--json] [--self-test]

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


def write_run_record(root: Path, results, *, engine: str, limit: int, advisories) -> str:
    """One JSON record beside the previews. The only provenance a header-and-rows CSV can carry.

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
    p = root / "data" / "samples" / RUN_RECORD
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
                 encoding="utf-8")
    return str(p.relative_to(root))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", help="the bundle root (REQUIRED; this command writes files)")
    ap.add_argument("stems", nargs="*", help="descriptor stems; default every declared relation")
    ap.add_argument("--plane", choices=("sources", "datasets", "both"), default="both")
    ap.add_argument("--limit", type=int, default=20,
                    help="rows per preview (default 20; must be >= 1)")
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

    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 2
    planes = ("sources", "datasets") if a.plane == "both" else (a.plane,)

    targets, plan_findings = plan_samples(root, planes=planes, stems=a.stems or None)
    declared = {k: len(glob.glob(str(root / "data" / k / "*.yaml"))) for k in planes}
    if not any(declared.values()):
        if a.json:
            print(json.dumps({"targets": 0, "wrote": 0, "measured_nothing": True,
                              "state": "no-descriptors", "results": []}, indent=1))
            return D.EMPTY_EXIT
        # Restated here, with mac_diag as its single home, because tools/ and the gate package have
        # no import edge; a CI script recognises a not-run by this verbatim phrase.
        return D.refuse_empty(NAME, ", ".join(str(root / "data" / k) for k in planes),
                              unit="descriptor")

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
    wrote = [r for r in results if r.get("state") in ("WROTE", "IDENTICAL")]
    differs = [r for r in results if r.get("state") == "DIFFERS"]
    refused = [r for r in results if r.get("state") == "REFUSED"]
    dry = [r for r in results if r.get("state") == "DRY"]
    codes = [r.get("exit", 1) for r in refused] + [f["exit"] for f in plan_findings] \
        + [1] * len(differs)

    record = ""
    if not a.dry_run and not a.verify:
        record = write_run_record(root, results, engine=conn.id, limit=a.limit,
                                  advisories=advisories)

    if a.json:
        print(json.dumps({"targets": len(targets), "declared": declared,
                          "wrote": len(wrote), "refused": len(refused) + len(plan_findings),
                          "differs": len(differs), "engine": conn.id, "run_record": record,
                          "results": results, "plan_findings": plan_findings},
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

    total = len(targets) + len(plan_findings)
    per_plane = "; ".join(f"{len([r for r in wrote if r['kind'] == k])} of {declared.get(k, 0)} "
                          f"{k[:-1]}(s)" for k in planes)
    order = "every declared column ASC NULLS LAST, rendered rows sorted"
    code = _verdict_code(codes)
    if a.dry_run:
        dry_plane = "; ".join(f"{len([r for r in dry if r['kind'] == k])} of {declared.get(k, 0)} "
                              f"{k[:-1]}(s)" for k in planes)
        head = "PASS" if not plan_findings else "FAIL"
        print(f"{head}: {NAME} --dry-run — {len(dry)} of {total} statement(s) rendered "
              f"({dry_plane}); engine {conn.id}; nothing was read and nothing was written"
              + (f"; {len(plan_findings)} could not be planned" if plan_findings else ""))
        return 1 if plan_findings else 0
    verb = "verified" if a.verify else "wrote"
    head = "PASS" if code == 0 else ("FAIL" if code == 1 else "INCOMPLETE")
    tail = ""
    if refused or plan_findings:
        tail += f"; {len(refused) + len(plan_findings)} refused"
    if differs:
        tail += f"; {len(differs)} DIFFER from the file on disk (the data moved, or the file was " \
                f"authored)"
    print(f"{head}: {NAME} — {verb} {len(wrote)} of {total} preview(s) ({per_plane}); "
          f"engine {conn.id}; order: {order}{tail}"
          + (f"; run record {record}" if record else ""))
    return code


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

    total = len(cases)
    if bad:
        print(f"FAIL: {NAME} self-test — {len(bad)} of {total} case(s) failed")
        for b in bad:
            print(f"  ✗ {b}", file=sys.stderr)
        return 1
    mutants = len([c for c in cases if c[0].startswith("MUTANT")])
    controls = len([c for c in cases if "NEGATIVE CONTROL" in c[0]])
    print(f"PASS: {NAME} self-test — {total}/{total} case(s): {mutants} mutant(s) of the rule "
          f"(short header, extra relation column, absent relation, zero rows and no file on disk, no table.schema, "
          f"duplicate columns, no columns, unknown stem, empty population, no connector, "
          f"unresolvable connector, two homes for one relation name, --limit 0, a hand-edited file, "
          f"sub-millisecond precision, an unrenderable type, a ragged row) and {controls} negative "
          f"control(s) (byte-identity across three engine return orders, a clean cut, --verify on "
          f"an unchanged file, --dry-run with no read, and a dataset cut from its transform body)")
    return 0


def _no_connector(root: Path) -> Path:
    _seed(root, kind="sources")
    (root / "mac.project.yaml").write_text(
        "planes:\n  data: data\ndescriptors: data/datasets\nsources: data/sources\n",
        encoding="utf-8")
    return root


if __name__ == "__main__":
    raise SystemExit(main())
