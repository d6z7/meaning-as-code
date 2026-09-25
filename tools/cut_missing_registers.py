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
    # A concept HAS values when ANYTHING can resolve a non-self value for it — and that is two
    # populations, not one.
    #
    # THE BUG THIS FIXES, and it is the root of the whole 2026-09-25 duplicate episode. This read
    # only `load.entries`, which holds self-entries plus registers DERIVED from the data. A
    # register the bundle DECLARES resolves through `RegisterResolver` and never appears in
    # `entries` at all — so every concept with a working declared register looked valueless, and
    # this tool cheerfully cut a second register for it. Thirteen duplicates, each worse than the
    # file it shadowed, all from asking the wrong question.
    has_values = {e.concept for e in load.entries if e.identity != e.concept}
    has_values |= {d.concept for d in load.declarations if d.status == "loaded"}
    con = duckdb.connect(db, read_only=True)
    lookups = root / "data" / "lookups"

    # WHAT IS ALREADY COVERED, BY COLUMN. The old guard was `if path.exists(): continue`, which
    # is a guard on the FILENAME and let this tool write `country_country.lookup.csv` beside
    # `contoso_country.lookup.csv`: two registers over `dim_contoso_customer.Country`, the new one
    # labelling DE as 'DE' where the old one says 'Germany' and carries the continent roll-up and
    # the '--' sentinel. Thirteen such duplicates were written on 2026-09-25 and every one was
    # strictly worse than the file it shadowed.
    #
    # A REGISTER'S IDENTITY IS THE COLUMN IT WAS CUT FROM, never its name.
    covered: dict[tuple[str, str], str] = {}
    for existing in sorted(lookups.glob("*.lookup.csv")):
        try:
            import csv as _c
            with existing.open(encoding="utf-8-sig", newline="") as fh:
                existing_rows = list(_c.DictReader(fh))
        except Exception:  # noqa: BLE001, S112 - an unreadable register cannot claim a column
            continue
        if not existing_rows:
            continue
        head = list(existing_rows[0])
        if not head:
            continue
        views = {(r.get("source_view") or "").strip() for r in existing_rows if isinstance(r, dict)}
        for view in views - {""}:
            covered.setdefault((view, head[0]), existing.name)

    cut, skipped, shadowed = [], [], []
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
            except Exception:  # noqa: BLE001, S112 - a column we cannot read is simply not cut
                continue
            values = [str(r[0]).strip() for r in rows if str(r[0]).strip()]
            if not (MIN_MEMBERS <= len(values) <= MAX_MEMBERS):
                skipped.append((name, column, len(values)))
                continue
            path = lookups / f"{_slug(name)}_{_slug(column)}.lookup.csv"
            if path.exists():
                continue
            owner = covered.get((table, column))
            if owner is not None:
                # NOT A SKIP TO BE COUNTED AND FORGOTTEN. This column already has a register, so
                # the reason its values do not resolve is upstream -- an undeclared register, or a
                # canon the runtime does not implement. Cutting a second file would hide that and
                # leave two registers disagreeing.
                shadowed.append((name, column, owner))
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
    if shadowed:
        print(
            f"\nREFUSED TO SHADOW {len(shadowed)} column(s). Each already has a register, so a "
            f"value that will not resolve is NOT a missing register — look upstream, at whether "
            f"the register is DECLARED and whether its canon is implemented "
            f"(check_canon_implemented.py):"
        )
        for concept, column, owner in shadowed:
            print(f"  {concept + chr(46) + column:<40} already covered by {owner}")
    if a.apply:
        for path, _n, text in cut:
            path.write_text(text, encoding="utf-8")
        print(f"\nWROTE {len(cut)} register(s) to {lookups}")
    else:
        print(f"\nDRY RUN — {len(cut)} register(s) would be written. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
