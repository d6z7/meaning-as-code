#!/usr/bin/env python3
"""duckdb_seam.py — THE FRAMEWORK'S OWN ENGINE SEAM FOR A DUCKDB BUNDLE.

WHY IT EXISTS — defect B1 of DELIVERABLES-2026-09-26_first-run-state.md. `_plugin.py` requires the
BUNDLE to supply `tools/run_properties.py`, and the framework shipped no default. So a brand-new
bundle could not be MEASURED at all: `mac_profile.py` answered

    this check needs tools/run_properties.py to supply 'Athena', and the bundle declares none

and the operator's way past it was to hand-copy a 157-line shim out of another bundle. That is not a
first run delivering the full state; it is a first run that stops until someone remembers where the
shim lives. And the measurement plane is what D7 (data-quality tests), D9 (profiles), D10 (the
referential structure) and therefore D3 (the ER model) are all built from.

WHAT IT DOES NOT CHANGE. `_plugin.py`'s rule stands exactly as written: a bundle that DECLARES a
plugin and cannot supply it is UNRUNNABLE, and nothing a plugin does at import time may set the
caller's exit code. This is the documented fallback for a bundle that declares NONE — and only when
its own manifest says its connector is DuckDB, so the fallback can never quietly answer for a
warehouse it is not looking at.

WHICH DATABASE, AND FROM WHERE. `mac.project.yaml#runtime.connection` -> `connection.yaml#config`.
The four labels the framework passes (profile, region, workgroup, database) are RECORDED in the
evidence and decide nothing: an engine string in two files is how a measurement ends up naming a
different warehouse than the one it read.

READ-ONLY, ALWAYS. A measurement that can write is not a measurement. `config.read_only` is honoured
when it is true and forced when it is absent, so a bundle cannot be mutated by being profiled.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

#: TRINO ARRAY IDIOMS -> DUCKDB — defect B2. The framework's SQL is written for the Athena/Trino
#: seam and no caller passes a dialect, so the seam that OWNS the connection is where a dialect
#: difference belongs.
#:
#: MEASURED 2026-09-26: `mac_profile.py`'s value-domain capture emits
#:     array_join(array_sort(array_agg(DISTINCT expr)), chr(31))
#: and DuckDB answers `Did you mean "array_position"?`, killing the run before any profile is
#: written. `example/contoso` never hits it only because its domains were already captured, so the
#: path never fires there — latent, not absent.
#:
#: `string_agg(DISTINCT expr, sep ORDER BY expr)` keeps BOTH guarantees the Trino form gives:
#: DISTINCT members and a SORTED result, so a captured domain is deterministic and re-measuring it
#: does not churn the descriptor.
#:
#: The separator may itself be a call — `chr(31)` is the one the profiler uses — so the pattern
#: allows one level of nesting. A first version used `[^)]+?`, which stopped at the inner paren and
#: produced `string_agg(... , chr(31 ORDER BY ...))`: DuckDB then said "chr is a Scalar Function,
#: ORDER BY is only applicable to aggregate functions", which is a translation bug wearing an
#: engine error's clothes.
_SEP = r"(?:[^()]|\([^()]*\))+?"
_ARRAY_JOIN_AGG = re.compile(
    rf"array_join\(\s*array_sort\(\s*array_agg\(\s*DISTINCT\s+(?P<expr>.+?)\)\s*\)\s*,"
    rf"\s*(?P<sep>{_SEP})\s*\)",
    re.IGNORECASE | re.DOTALL,
)
_ARRAY_JOIN_SORT = re.compile(
    rf"array_join\(\s*array_sort\(\s*(?P<expr>[^()]+?)\s*\)\s*,\s*(?P<sep>{_SEP})\s*\)",
    re.IGNORECASE | re.DOTALL,
)


def to_duckdb(sql: str) -> str:
    """Rewrite the framework's Trino array idioms into DuckDB; leave everything else untouched."""
    sql = _ARRAY_JOIN_AGG.sub(
        lambda m: f"string_agg(DISTINCT {m['expr']}, {m['sep']} ORDER BY {m['expr']})", sql
    )
    return _ARRAY_JOIN_SORT.sub(
        lambda m: f"string_agg({m['expr']}, {m['sep']} ORDER BY {m['expr']})", sql
    )


class _Meta(dict):
    """A query's engine metadata. A MAPPING, because the framework accumulates fields across passes
    with `meta["bytes_scanned"] = (meta.get(...) or 0) + ...`.

    MEASURED 2026-09-26: written as a frozen dataclass, `mac_profile.py` died with
    `AttributeError: '_Meta' object has no attribute 'get'` two passes into a profile. The seam's
    job is to satisfy the contract the framework already has, not a tidier one.

    AND IT REFUSES `bytes_scanned`. An embedded engine reports nothing, and the accumulation above
    would turn two absent readings into a confident `0`. Dropping the write keeps the field ABSENT,
    which is what "not measurable here" honestly looks like in the artifact — a zero would read as
    "this scanned no data", which is a claim.
    """

    _REFUSED = ("bytes_scanned",)

    def __setitem__(self, key, value):
        if key in self._REFUSED:
            return
        super().__setitem__(key, value)


def connection_of(root: pathlib.Path) -> tuple[pathlib.Path, bool, str] | None:
    """`(database file, read_only, view_schema)` when this bundle is a DuckDB bundle, else None.

    None is the answer that keeps the fallback honest: a bundle whose connector is Athena, Trino or
    anything else must NOT be answered for by a DuckDB reader that happens to be importable.
    """
    import yaml

    manifest = root / "mac.project.yaml"
    if not manifest.is_file():
        return None
    doc = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    runtime = doc.get("runtime") or {}
    connector = str(runtime.get("connector") or "")
    if "duckdb" not in connector.lower():
        return None
    conn_path = root / str(runtime.get("connection") or "connection.yaml")
    if not conn_path.is_file():
        return None
    cdoc = yaml.safe_load(conn_path.read_text(encoding="utf-8")) or {}
    cfg = cdoc.get("config") or {}
    db = cfg.get("database")
    if not db:
        return None
    return (root / str(db)).resolve(), True, str(cdoc.get("view_schema") or "main")


class Athena:
    """The symbol the framework asks for, over DuckDB.

    NAMED `Athena` BECAUSE THE SEAM IS, and renaming it is a cross-tool break for a string nobody
    reads: seven framework tools ask `required(root, "Athena")`. What it actually opens is whatever
    `connection.yaml` names, which is the point of the seam.
    """

    def __init__(self, profile: Any = None, region: Any = None, workgroup: Any = None,
                 database: Any = None, root: Any = None, **_: Any) -> None:
        import duckdb

        self.labels = {"profile": profile, "region": region,
                       "workgroup": workgroup, "database": database}
        self.root = pathlib.Path(root or ".").resolve()
        resolved = connection_of(self.root)
        if resolved is None:
            raise RuntimeError(
                f"{self.root} does not declare a DuckDB connection "
                f"(mac.project.yaml#runtime.connector + connection.yaml#config.database), so the "
                f"framework's DuckDB seam must not answer for it"
            )
        self.path, self.read_only, self.view_schema = resolved
        if not self.path.exists():
            raise RuntimeError(
                f"{self.path} does not exist — the warehouse has not been built yet"
            )
        self._con = duckdb.connect(str(self.path), read_only=self.read_only)

    def query(self, sql: str) -> tuple[list[dict], _Meta]:
        """One statement, rows as dicts keyed by the names the engine returns, unaltered.

        Every framework caller reads results positionally by generated alias (`d0`, `z0`, `v3`), so
        the keys must not be normalised.
        """
        cur = self._con.execute(to_duckdb(sql))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row, strict=False)) for row in cur.fetchall()], _Meta()

    def close(self) -> None:
        self._con.close()


def resolve_declared(text: str) -> str:
    """The documented identity fallback: a bundle with no namespacing resolves to itself."""
    return text


def source_watermark(ath: "Athena", relations: list[str]) -> dict[str, dict]:
    """The high-water mark of each relation, DERIVED from the descriptors — never from a name list.

    A write timestamp is something a descriptor already states: `role: audit` on a time-typed
    column. A relation whose descriptor marks none has NO watermark, and this returns None for it
    rather than guessing at a column by its name.
    """
    import yaml

    descriptors: dict[str, dict] = {}
    for plane in ("sources", "datasets"):
        for path in sorted((ath.root / "data" / plane).glob("*.yaml")):
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            tbl = doc.get("table") or {}
            key = ".".join(x for x in (tbl.get("schema"), tbl.get("name")) if x)
            if key:
                descriptors[key] = doc

    out: dict[str, dict] = {}
    for rel in relations:
        doc = descriptors.get(rel) or {}
        audit = [
            c for c in (doc.get("columns") or [])
            if c.get("role") == "audit"
            and any(str(c.get("type", "")).lower().startswith(k) for k in ("timestamp", "date"))
        ]
        if not audit:
            out[rel] = {"column": None, "newest": None}
            continue
        col = str(audit[0]["name"]).replace('"', "")
        rows, _ = ath.query(f'SELECT max("{col}") AS d0 FROM {rel}')
        out[rel] = {"column": col, "newest": (rows[0].get("d0") if rows else None)}
    return out


if __name__ == "__main__":
    import sys

    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    got = connection_of(root)
    if got is None:
        print(f"{root.name}: NOT a DuckDB bundle — this seam declines it")
        raise SystemExit(0)
    db, ro, schema = got
    print(f"{root.name}: duckdb {db} read_only={ro} view_schema={schema} "
          f"exists={db.is_file()}")
    print("\ntranslation self-test:")
    probe = "SELECT array_join(array_sort(array_agg(DISTINCT CAST(x AS varchar))), chr(31)) AS v0"
    out = to_duckdb(probe)
    ok = "string_agg(DISTINCT CAST(x AS varchar), chr(31) ORDER BY CAST(x AS varchar))" in out
    print(f"  {'OK  ' if ok else 'FAIL'} {out}")
    raise SystemExit(0 if ok else 1)
