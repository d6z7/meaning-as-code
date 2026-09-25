#!/usr/bin/env python3
"""Cut a register for every low-cardinality dimension column that has none.

THE OPERATOR, on a question that refused `Continent = 'Europe'`:

    "whith gender ?!?!?! you do have dimiension for GENDER and for COUNTRY. gender is closed list
     country is closed list ... so this is really TRIVIAL and i do not undestand WTF is your
     problem with such trivial mapping ?!?!?!?!?!!?!? everyhing is on the table ... just have to
     take it"

He is right, and the measurement is embarrassing: `Europe` is LITERALLY A VALUE IN THE COLUMN --
`SELECT DISTINCT Continent` returns Australia, Europe, North America. The question refused a word
that was sitting in the data, because no lookup file happened to have been cut for that column.

Measured on the worked bundle: **~20 dimension columns with 40 or fewer distinct values had no
resolvable values at all** -- Brand (11 in the data), Color (16), Continent (3), Status (2),
CurrencyCode (5), CategoryName (8). Every one of them refuses a word that exists.

WHY A CUTTER AND NOT A RESOLVER CHANGE. The values live in the warehouse; reading them is
DERIVING an enumeration, which is what this estate says to do. A register file is the form the
estate already uses for that, it is already content-addressed, already read by the loader, and
already carried into the prompt. Nothing new has to be invented -- the files simply were never
cut. One commit created 17 of them and none since.

WHAT IT REFUSES TO DO. It never writes a register for a column whose cardinality is above the
limit: those are IDENTITIES (products, customers), they grow with the data, and resolving a name
against them is exactly what the resolver's own tiers are for. It never overwrites a file that
exists -- a hand-corrected register must survive a re-cut.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

#: Above this a domain is an identity, not an enumeration. Mirrors `Vocabulary.VALUE_LIMIT`.
MAX_MEMBERS = 40
#: A column with one value tells a question nothing and costs prompt space.
MIN_MEMBERS = 2


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle")
    ap.add_argument("--db", help="the warehouse (default: the bundle's connection.yaml)")
    ap.add_argument("--schema", default="contoso_served")
    ap.add_argument("--apply", action="store_true", help="write the files (default: dry run)")
    a = ap.parse_args(argv)

    root = pathlib.Path(a.bundle).resolve()
    sys.path.insert(0, "/Users/<operator>/dev/mac-platform/packages/mac-runtime/src")
    import duckdb
    import yaml

    from mac_runtime.ontology import OntologyIndex
    from mac_runtime.resolver.registers import load_registers

    db = a.db
    if not db:
        conn = yaml.safe_load((root / "connection.yaml").read_text())
        db = str(root / (conn.get("config") or {}).get("database", ""))

    index = OntologyIndex.from_directory(str(root))
    load = load_registers(str(root), index)
    # A concept HAS values when something already resolves a non-self value for it.
    has_values = {e.concept for e in load.entries if e.identity != e.concept}
    con = duckdb.connect(db, read_only=True)
    lookups = root / "data" / "lookups"

    cut, skipped = [], []
    for name, concept in sorted(index.concepts.items()):
        if name in has_values:
            continue
        table = concept.grounding.table
        if not table:
            continue
        for column, role in (concept.grounding.field_roles or {}).items():
            if role.rsplit(".", 1)[-1] != "dimension":
                continue
            try:
                rows = con.execute(
                    f'SELECT DISTINCT "{column}" FROM "{a.schema}"."{table}" '
                    f'WHERE "{column}" IS NOT NULL ORDER BY 1'
                ).fetchall()
            except Exception:  # noqa: BLE001 - a column we cannot read is simply not cut
                continue
            values = [str(r[0]).strip() for r in rows if str(r[0]).strip()]
            if not (MIN_MEMBERS <= len(values) <= MAX_MEMBERS):
                skipped.append((name, column, len(values)))
                continue
            path = lookups / f"{_slug(name)}_{_slug(column)}.lookup.csv"
            if path.exists():
                continue
            # THE SAME SHAPE THE EXISTING REGISTERS USE, so the loader needs no change: the code
            # column is named after the ontology column, then label and search_key.
            # WRITTEN THROUGH THE CSV MODULE, not by joining strings. The first version quoted
            # the value but left `search_key` bare, so "Music, Movies and Audio Books" produced a
            # row with more fields than the header and the loader handed back a LIST where a
            # string was expected. A value containing a comma is not exotic; it is a product
            # category.
            import csv as _csv
            import io as _io

            buf = _io.StringIO()
            writer = _csv.writer(buf, lineterminator="\n")
            writer.writerow([column, "label", "search_key", "source_view", "confidence", "note"])
            for v in values:
                writer.writerow(
                    [v, v, v.casefold(), table, "I",
                     f"cut from {a.schema}.{table}.{column}"]
                )
            cut.append((path, len(values), buf.getvalue()))
            has_values.add(name)
            break  # one register per concept: the first dimension column that qualifies

    print(f"{'concept register':<46}{'members':>8}")
    for path, n, _ in cut:
        print(f"  {path.name:<44}{n:>8}")
    if not cut:
        print("  (nothing to cut — every low-cardinality dimension already resolves)")
    if a.apply:
        for path, _n, text in cut:
            path.write_text(text, encoding="utf-8")
        print(f"\nWROTE {len(cut)} register(s) to {lookups}")
    else:
        print(f"\nDRY RUN — {len(cut)} register(s) would be written. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
