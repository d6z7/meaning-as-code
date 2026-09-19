#!/usr/bin/env python3
"""Run an acceptance suite WITHOUT SPENDING MONEY, and persist the run properly.

── WHY THIS EXISTS ────────────────────────────────────────────────────────────────────────────

All seven live suites declare an `engine:` block naming an AWS profile, region, workgroup and
Athena database. There is NO declared offline tier — `mac.test_tier` is prose and nothing
machine-readable carries it — and the one runner in the estate constructs an Athena client
unconditionally, before it has looked at a single property:

    ath = Athena(profile, eng["region"], eng["workgroup"], eng["database"])   # run_properties.py:490

So the engine is WELDED TO THE SUITE, and "run the tests" and "spend money" are the same act. That
is the reason the write path could never be exercised for free, and therefore the reason a broken
write path survived: every rehearsal of it cost a bill.

THIS RUNNER CANNOT BILL. It imports no boto3 and constructs no cloud client; `--engine` accepts
only `dry-run`, `sqlite` and `duckdb`, all local, and anything else exits 3 before a property is
read. A suite's declared cloud `engine:` block is RECORDED in the run record as `declared_engine`
and never acted on — the record says which engine actually answered, which is a fact no existing
record carries.

It is not a replacement for the billed runner. It is the free half: the same suite data, the same
seven assertion kinds, the same record shape — so the write path can be proven against a fixture,
and the next paid run is the first one that keeps its answer.

── THREE WAYS TO BE FREE ──────────────────────────────────────────────────────────────────────

  --engine dry-run   NO ENGINE AT ALL. Rows are synthesised from each assertion's own expectation,
                     which exercises the ENTIRE write path — header, fingerprint, denominator,
                     carry-forward, both files, the history row — with zero infrastructure. The
                     record is stamped `engine.synthetic: true` and the gate reports it as such,
                     because a synthetic record is proof about the PLUMBING and about nothing else.
  --engine sqlite    a real SQL engine, in the Python standard library, on every machine. Real
                     rows, real assertions, real failures. `--schema X` becomes an ATTACH.
  --engine duckdb    the same against DuckDB when it is installed; `--schema X` becomes a SCHEMA.

── USAGE ──────────────────────────────────────────────────────────────────────────────────────

    python3 tools/run_suite.py --bundle example_shop_ontology \\
        --suite acceptance/properties.yaml --engine sqlite --schema shop_warehouse \\
        --seed /tmp/shop_seed.sql

    python3 tools/run_suite.py --bundle <b> --suite <s> --engine dry-run          # no engine
    python3 tools/run_suite.py --bundle <b> --suite <s> --engine dry-run --fail ID  # seed a red
    python3 tools/run_suite.py --bundle <b> --suite <s> --engine sqlite --id P-X-01 # filtered

Exit code (the billed runner's contract, unchanged so a caller can swap engines):
    0  every executed property passed        2  only minor/info properties failed
    1  a blocker/major property failed       3  could not run (bad engine, bad suite, query error)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from decimal import Decimal, InvalidOperation
import pathlib
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_record as _rec  # noqa: E402
from mac_resolve_declared import resolve_declared  # noqa: E402

LOCAL_ENGINES = ("dry-run", "sqlite", "duckdb")
HARD_FAIL = {"blocker", "major"}
SEVERITY_ORDER = {"blocker": 0, "major": 1, "minor": 2, "info": 3}

#: A schema-qualified relation in a property's SQL. Qualified only, deliberately: an unqualified
#: name in this estate is a defect (see `mac_generate_ontology_tests._rel`), and counting rows of
#: something resolved by a search path would watermark a relation the property may not have read.
_RELATION = re.compile(r"\bFROM\s+([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)", re.IGNORECASE)


def relations_read(props) -> set:
    """Every qualified relation this run's properties touch, `information_schema` excluded."""
    out: set = set()
    for p in props:
        out |= {m.group(1) for m in _RELATION.finditer(p.get("sql") or "")}
    return {r for r in out if "information_schema" not in r.lower()}


def watermark(eng, props) -> dict:
    """One cheap row count per relation this run read, recorded beside the results.

    `source_watermark` HAD BEEN A KEY WITH NOTHING IN IT. Measured on a live two-plane bundle: both run
    records carried `source_watermark: {}` — present, empty, and therefore unable to mark anything
    stale. The field exists because of a recorded incident: an operator quoted a figure off a dashboard
    that was an ORDER OF MAGNITUDE low, because the source had loaded overnight and "the run record
    carried {suite, version, engine} and nothing else, so nothing on the page could say the number
    predates the data it describes."

    A key present and empty is worse than absent: a reader takes it for a watermark. So the free
    runner populates it. Row count only, and no newest-write: a local DuckDB bundle has no
    estate-wide write-timestamp column, and inventing one per relation is how a watermark starts
    lying. A relation that cannot be counted records its error rather than being omitted — omission
    reads as "nothing to report"."""
    marks: dict = {}
    for rel in sorted(relations_read(props)):
        try:
            rows, _ = eng.query(f"SELECT count(*) AS rows FROM {rel}")
            marks[rel] = {"rows": rows[0]["rows"], "newest_write": None,
                          "note": "row count only — no write-timestamp column is declared for this "
                                  "relation, so freshness is not measurable from here"}
        except Exception as exc:
            marks[rel] = {"error": str(exc)[:160]}
    return marks


def _num(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


# ── engines ──────────────────────────────────────────────────────────────────────────────────
class LocalSQL:
    """A local SQL engine. READ-ONLY for suite SQL, by the same rule as the billed runner.

    The seed is the ONLY place DDL is allowed, and it is a file the operator names. Suite SQL must
    start with SELECT or WITH and may not contain a mutating keyword — the property is evidence
    about the data, so a property that can change the data is not evidence.
    """

    BANNED = ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "DROP ",
              "ALTER ", "MERGE ", "GRANT ", "ATTACH ", "PRAGMA ")

    def __init__(self, kind: str, db: str, schema: str | None):
        self.kind, self.target = kind, db
        if kind == "duckdb":
            try:
                import duckdb
            except ImportError as exc:
                raise RuntimeError(f"--engine duckdb needs the duckdb package: {exc}") from exc
            self.con = duckdb.connect(db)
            if schema:
                self.con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        else:
            self.con = sqlite3.connect(db)
            self.con.row_factory = sqlite3.Row
            # SQLite has no CREATE SCHEMA. A schema-qualified name resolves against an ATTACHed
            # database, so the suite's `shop_warehouse.orders` works unchanged — which matters:
            # the point is to run the AUTHORED sql, not a rewritten copy of it.
            if schema:
                self.con.execute(f"ATTACH DATABASE ':memory:' AS {schema}")

    def seed(self, sql_text: str) -> None:
        if self.kind == "duckdb":
            self.con.execute(sql_text)
        else:
            self.con.executescript(sql_text)

    def query(self, sql: str):
        head = sql.lstrip().upper()
        if not head.startswith(("SELECT", "WITH")):
            raise ValueError("read-only runner: SELECT/WITH only")
        for b in self.BANNED:
            if b in head:
                raise ValueError(f"read-only runner: refused statement containing {b.strip()}")
        if self.kind == "duckdb":
            cur = self.con.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        else:
            cur = self.con.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
        return rows, {"kind": self.kind, "rows_returned": len(rows), "bytes_scanned": 0}


def synth_rows(prop: dict, force_fail: bool) -> list[dict]:
    """Rows a dry run hands the evaluator, derived from the assertion's OWN expectation.

    This is deliberately circular and says so: a dry run proves the write path, not the data. It is
    the cheapest possible exercise of the thing that was broken, and `engine.synthetic: true` keeps
    the record from ever being read as a measurement. `--fail ID` inverts one property so the proof
    includes a persisted RED — the original writer threw every failing run away (`set -e` killed
    the script before the merge), so "it persists" had to be demonstrated on a failure, not a pass.
    """
    spec = prop.get("assertion") or {}
    kind = spec.get("type")
    bump = (lambda v: (_num(v) or Decimal(0)) + 1) if force_fail else (lambda v: v)
    if kind == "must_be_empty":
        return [{"synthetic_violation": 1}] if force_fail else []
    if kind == "must_be_nonempty":
        return [] if force_fail else [{"synthetic_row": 1}]
    if kind == "must_be_zero":
        return [{c: (1 if force_fail else 0) for c in spec.get("columns") or []}]
    if kind == "equals":
        return [{c: bump(v) for c, v in (spec.get("expect") or {}).items()}]
    if kind in ("min_value", "max_value"):
        sign = -1 if kind == "min_value" else 1
        return [{c: ((_num(v) or Decimal(0)) + sign) if force_fail else v
                 for c, v in (spec.get("expect") or {}).items()}]
    if kind == "max_abs_diff":
        a, b = (spec.get("columns") or ["a", "b"])[:2]
        tol = _num(spec.get("tolerance", prop.get("tolerance", 0))) or Decimal(0)
        return [{a: Decimal(100), b: Decimal(100) + (tol + 1 if force_fail else 0)}]
    return []


# ── the seven assertion kinds ────────────────────────────────────────────────────────────────
def evaluate(prop: dict, rows: list[dict]) -> tuple[bool, list[str]]:
    """The billed runner's seven kinds, same semantics, so a free run and a paid run of the same
    suite are comparable. Divergence here would make the free tier a different test wearing the
    same id — which is the drift that the assertion-vocabulary finding (4 terms vs 7) is about."""
    spec = prop.get("assertion") or {}
    kind = spec.get("type")
    tol = _num(spec.get("tolerance", prop.get("tolerance", 0))) or Decimal(0)
    notes: list[str] = []
    ok = True

    if kind is None:
        return False, ["no assertion declared — a property with no assertion cannot fail"]
    if kind == "must_be_empty":
        return (not rows, [f"expected 0 rows, got {len(rows)}" if rows else "0 rows, as required"])
    if kind == "must_be_nonempty":
        return (bool(rows), ["expected at least 1 row, got 0"] if not rows
                else [f"{len(rows)} row(s) returned"])
    if not rows:
        return False, ["query returned NO ROWS — a property cannot be satisfied vacuously"]

    for row in rows:
        if kind == "must_be_zero":
            for col in spec.get("columns") or []:
                v = _num(row.get(col))
                if v is None:
                    ok = False
                    notes.append(f"column '{col}' missing/null")
                elif abs(v) > tol:
                    ok = False
                    notes.append(f"{col} = {v} (must be 0)")
        elif kind == "equals":
            for col, want in (spec.get("expect") or {}).items():
                raw = row.get(col)
                if raw is None or raw == "":
                    ok = False
                    notes.append(f"column '{col}' missing/null")
                    continue
                got, exp = _num(raw), _num(want)
                if got is not None and exp is not None:
                    if abs(got - exp) > tol:
                        ok = False
                        notes.append(f"{col} = {got} (expected {want})")
                elif str(raw).strip() != str(want).strip():
                    ok = False
                    notes.append(f"{col} = '{raw}' (expected '{want}')")
        elif kind in ("min_value", "max_value"):
            for col, want in (spec.get("expect") or {}).items():
                got, exp = _num(row.get(col)), _num(want)
                if got is None or exp is None:
                    ok = False
                    notes.append(f"column '{col}' missing/non-numeric")
                elif (kind == "min_value" and got < exp) or (kind == "max_value" and got > exp):
                    ok = False
                    notes.append(f"{col} = {got} ({'min' if kind == 'min_value' else 'max'} {want})")
        elif kind == "max_abs_diff":
            a, b = (spec.get("columns") or [None, None])[:2]
            va, vb = _num(row.get(a)), _num(row.get(b))
            if va is None or vb is None:
                ok = False
                notes.append(f"columns '{a}'/'{b}' missing/non-numeric")
            elif abs(va - vb) > tol:
                ok = False
                notes.append(f"|{a} - {b}| = {abs(va - vb)} (max {tol})")
        else:
            return False, [f"unknown assertion type '{kind}'"]
    if ok:
        notes.append(f"satisfied over {len(rows)} row(s)")
    return ok, notes


# ── main ─────────────────────────────────────────────────────────────────────────────────────
def _relative_target(db: str | None, root) -> str | None:
    """The warehouse path as the RECORD should carry it: bundle-relative when it is inside the
    bundle, unchanged when it is not.

    A run record is evidence and it is committed, so any absolute path in it is the operator's
    home directory published to whoever reads the repo. Measured after the fact by the public
    leak gate: 16 findings over 8 records, every one this single field. Scrubbing the records is
    not the fix — the producer reintroduces it on the next run, which is exactly what happened.

    Only the SPELLING changes; the target is the same file. A path outside the bundle is left
    alone rather than made relative with `..`, which would be neither readable nor portable —
    that case is a real disclosure and belongs in front of a person, not silently rewritten.
    """
    if not db:
        return None
    try:
        return pathlib.Path(db).resolve().relative_to(pathlib.Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return db


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="free (local) acceptance-suite runner + run-record writer")
    ap.add_argument("--bundle", required=True, help="bundle root")
    ap.add_argument("--suite", required=True, help="suite yaml, bundle-relative or absolute")
    ap.add_argument("--engine", required=True, choices=LOCAL_ENGINES)
    ap.add_argument("--db", help="engine file (default :memory: / a temp duckdb)")
    ap.add_argument("--schema", help="schema the suite's SQL qualifies its tables with")
    ap.add_argument("--seed", help="SQL file creating + filling the fixture tables")
    ap.add_argument("--id", action="append", default=[], help="run only these ids (repeatable)")
    ap.add_argument("--fail", action="append", default=[],
                    help="dry-run only: force these ids RED, to prove a red persists")
    ap.add_argument("--runs", help="override the runs path (default: the reader's map)")
    ap.add_argument("--no-write", action="store_true", help="run, print, persist nothing")
    a = ap.parse_args(argv)

    root = Path(a.bundle).resolve()
    if not root.is_dir():
        print(f"could not run: {root} is not a directory", file=sys.stderr)
        return 3
    suite_file = Path(a.suite) if Path(a.suite).is_absolute() else root / a.suite
    if not suite_file.exists():
        print(f"could not run: no suite at {suite_file}", file=sys.stderr)
        return 3
    suite = yaml.safe_load(suite_file.read_text(encoding="utf-8")) or {}
    props = suite.get("properties") or []
    if not props:
        # A SUITE THAT DECLARES NOTHING IS NOT A GREEN SUITE. 0 declared is the PASS-on-zero
        # defect, and it is the state three shipped example bundles are in.
        print(f"could not run: {suite_file} declares 0 properties — 0 declared is not 0 failures",
              file=sys.stderr)
        return 3

    declared_ids = [p["id"] for p in props]
    selected = [p for p in props if not a.id or p["id"] in a.id]
    if a.id and not selected:
        print(f"could not run: none of {a.id} is declared in {suite_file.name}", file=sys.stderr)
        return 3

    # The suite's own engine block is CARRIED, never constructed. This is the line that makes the
    # runner unable to bill, and it is deliberately the first thing done with `engine:`.
    declared_engine = suite.get("engine") or {}
    engine = {"kind": a.engine, "billed": False, "synthetic": a.engine == "dry-run",
              # BUNDLE-RELATIVE WHERE IT CAN BE, because this string is COMMITTED. A run record is
              # evidence and lives in the repo, so `--db ./contoso.duckdb` resolving to an absolute
              # path puts the operator's home directory into every record the suite writes. Caught
              # by the public-repo leak gate after the fact: 16 findings over 8 records, all one
              # line, and hand-scrubbing two of them earlier only proved the producer keeps
              # reintroducing it. The target is the same file either way; only the spelling moves.
              "target": _relative_target(a.db, root) or (":memory:" if a.engine != "dry-run" else None),
              "declared_engine": declared_engine or None}

    eng = None
    if a.engine != "dry-run":
        try:
            eng = LocalSQL(a.engine, a.db or ":memory:", a.schema)
            if a.seed:
                eng.seed(Path(a.seed).read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"could not run: {a.engine}: {exc}", file=sys.stderr)
            return 3

    print(f"── {suite.get('suite')} v{suite.get('version')}  engine={a.engine}"
          f"{' (SYNTHETIC — proves the write path, not the data)' if a.engine == 'dry-run' else ''}")
    print(f"   {len(selected)} of {len(declared_ids)} declared propert{'y' if len(selected) == 1 else 'ies'}\n")

    fresh, errors = [], 0
    for p in selected:
        # `source` AND `assertion` ARE CARRIED, NOT DROPPED. The record used to be
        # {id, family, severity, statement} plus the verdict, and the two fields that say WHAT THE
        # CHECK WAS MEASURED AGAINST and WHAT IT ASSERTED never left the suite file — 67 of 67
        # properties in the measured bundle declare both, 0 of 67 results carried either.
        #
        # A CONSUMER MEASURED THE COST. The console derives a check's PLANE from `source` alone
        # (data/… is a claim about the data, ontology/… a claim about the model, and a red means a
        # different desk), so every result on both boards fell into "Unclassified — the source line
        # names neither plane", and the coverage tab's relation list, derived from the same string,
        # was empty by construction rather than by absence of coverage. The fact existed in the
        # suite and was discarded in transit.
        #
        # ADDITIVE AND SAFE: the record's readers key on `id` and `status`
        # (check_cards_match_runs, check_run_records, suite_history), and no gate asserts a closed
        # key set. `sql` is deliberately NOT copied — the query's home on the console is the card
        # projection (test_card_project.py), and duplicating it per result would put two copies of
        # every statement in a file that is diffed on every run.
        rec = {"id": p["id"], "family": p.get("family", ""), "severity": p.get("severity", "info"),
               "statement": " ".join((p.get("statement") or "").split()),
               "source": p.get("source") or "", "assertion": p.get("assertion")}
        try:
            if a.engine == "dry-run":
                rows = synth_rows(p, p["id"] in a.fail)
                meta = {"kind": "dry-run", "rows_returned": len(rows), "synthetic": True}
            else:
                # RENDER THE DECLARATION BEFORE THE ENGINE SEES IT. A `conformance` property MUST
                # read every asserted value out of the declaration at run time — that is the whole
                # difference between the two test kinds — so its SQL arrives carrying `@cols:` /
                # `@n:` / `@frag:` markers and is not SQL yet.
                #
                # MEASURED, and this line is the fix: without it the marker text reached DuckDB and
                # 20 of a live two-plane bundle's 33 generated conformance properties died as
                # `Parser Error: syntax error at or near ":"`, examined 0, while the estate's gates
                # all read PASS. The framework EMITTED a marker grammar its own free runner could
                # not execute; the only resolver in the estate lived inside one bundle.
                #
                # It REFUSES rather than substituting nothing: `Unresolved` is caught by the same
                # handler below and recorded as an ERROR on that property, naming the marker and the
                # file it looked in. Rendering a blank would partition on five columns while
                # reporting six, and both halves would agree with each other and with nothing else.
                rows, meta = eng.query(resolve_declared(root, p["sql"]))
            passed, notes = evaluate(p, rows)
            acc, frz = p.get("accepted"), p.get("frozen")
            rec.update(status="PASS" if passed else
                       ("ACCEPTED" if acc else "FROZEN" if frz else "FAIL"),
                       rows=rows, notes=notes, engine=meta)
            if not passed and acc:
                rec["accepted"] = acc
        except Exception as exc:
            errors += 1
            # rows=None, NOT []. An empty grid means "the query ran and returned nothing", which is
            # evidence; None means nothing was examined. `recount` counts evidence, so conflating
            # the two would let a suite of pure errors report itself as fully examined.
            rec.update(status="ERROR", rows=None, notes=[str(exc)], engine={"kind": a.engine})
        fresh.append(rec)
        print(f"  {rec['id']:<28} {rec['status']:<9} {rec['notes'][0][:88] if rec['notes'] else ''}")

    runs_rel = a.runs or _rec.runs_path(suite_file)
    prev = None
    prev_path = root / runs_rel
    if prev_path.exists():
        try:
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = None
    results = _rec.carry_forward(prev, fresh, declared_ids)
    doc = _rec.build(suite=suite, suite_file=suite_file, root=root, engine=engine,
                     results=results, declared_ids=declared_ids,
                     source_watermark=watermark(eng, selected) if eng else None)

    c = _rec.recount(doc)
    print(f"\n── SUMMARY  declared {doc['declared']} · examined {c['examined']} · "
          f"skipped {c['skipped']} · " + " · ".join(f"{k.lower()} {v}" for k, v in c["tally"].items() if v))
    if doc["commit"] is None:
        print("   commit: NONE — this bundle is not in a git repository, so the record cannot be "
              "fingerprinted against a commit; ontology_fingerprint is the only staleness handle")
    else:
        print(f"   commit: {doc['commit']}{' (DIRTY WORKING TREE)' if doc['commit_dirty'] else ''}"
              f" · ontology {doc['ontology_fingerprint']}")

    if a.no_write:
        print("\n   --no-write: nothing persisted")
    else:
        cur, dated = _rec.write(root, doc, runs_rel)
        hist = root / "acceptance" / "suite_history.jsonl"
        row = _rec.history_row(doc)
        seen = set()
        if hist.exists():
            for line in hist.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    seen.add((r.get("suite"), r.get("run_at"), r.get("commit")))
        added = (row["suite"], row["run_at"], row["commit"]) not in seen
        if added:
            with hist.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\n   current  -> {cur}")
        print(f"   dated    -> {dated}")
        print(f"   history  -> {hist}{'' if added else '  (already recorded)'}")

    if errors:
        return 3
    hard = [r for r in fresh if r["status"] == "FAIL" and r["severity"] in HARD_FAIL]
    if hard:
        return 1
    if any(r["status"] == "FAIL" for r in fresh):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
