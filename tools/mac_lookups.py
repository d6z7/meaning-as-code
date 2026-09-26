#!/usr/bin/env python3
"""mac_lookups.py — cut the VALUE REGISTERS from the domains already measured on the descriptors.

D12 of DELIVERABLES-2026-09-26_first-run-state.md. The operator: "no lookups in console".

WHY THE EXISTING CUTTER COULD NOT DO IT. `harvest --mode lookups` profiles through AWS: on a bundle
whose warehouse is a local DuckDB file it fails with `botocore.exceptions.NoCredentialsError: Unable
to locate credentials`. The framework HAS a connector seam — `_plugin.required(root, "Athena")`, which
`duckdb_seam` now answers for any DuckDB bundle — and the lookup cutter predates it. So a DuckDB
bundle could not cut a register at all, and D12 was empty on every run.

AND NOTHING NEEDS RE-PROFILING. `mac_profile` already captures a column's value domain onto its
descriptor for every column that is BOUNDED and ENUMERABLE — measured on one bundle: 28 of 72 served
columns. The register is a PROJECTION of that domain, not a new measurement, so this reads what is on
disk and writes the CSV the resolver expects.

WHAT A REGISTER IS FOR. A question names a WORD; the warehouse stores a CODE. A register maps one to
the other OFFLINE, so a question about "Germany" resolves without probing the warehouse and reading
"no rows" as "no such thing". Its first column is the CODE — the loader infers the source column from
exactly that — and `search_key` is what a person types.

THE SHAPE, unchanged from what the resolver already reads:

    <CodeColumn>,label,search_key,source_view,confidence,note
    DE,Germany,germany,dim_contoso_customer,I,"measured: 8 members"

WHERE THE LABEL COMES FROM, and this is the one inference here. A code column often has a sibling
carrying the human name — `Country`/`CountryFull`, `CategoryKey`/`CategoryName` — and when the two
have the SAME number of members and the same row-by-row pairing, the sibling IS the label. When there
is no such sibling the code is its own label, which is correct for `Gender` (`female`) and for
`Status` (`Closed`). A pairing that does not hold one-to-one is NOT used: a label that is right for
most rows is worse than no label.

ONE REGISTER PER DIMENSION (DNA premise P4): a column already covered by a register is skipped rather
than cut twice under a second name.

    python3 mac_lookups.py <bundle-root> [--max-members N] [--check]
"""

from __future__ import annotations

import argparse
import csv
import io
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _plugin  # noqa: E402

GENERATOR = "mac_lookups.py/1"
#: Above this a column is not a register: it is data. 608 GeoAreaKeys is a dimension to join, not a
#: word list to resolve against, and a prompt cannot carry it.
MAX_MEMBERS = 200
#: A column whose members ARE the words needs no label sibling.
_SELF_LABELLING = ("gender", "status", "channel", "continent", "brand", "color", "colour",
                   "manufacturer", "weightunit", "currencycode", "fromcurrency", "tocurrency")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--max-members", type=int, default=MAX_MEMBERS)
    ap.add_argument("--check", action="store_true", help="report drift; write nothing")
    a = ap.parse_args(argv)

    root = pathlib.Path(a.root).resolve()
    try:
        import yaml
    except ImportError as exc:
        print(f"REFUSED: {exc}")
        return 2

    # The connection is opened ONLY to verify a label pairing; the domains are read from disk.
    con = None
    try:
        con = _plugin.required(str(root), "Athena")(root=str(root))
    except Exception as exc:  # noqa: BLE001
        print(f"  (no engine: {str(exc)[:70]} — labels will fall back to the code)")

    marker = _marker(root, yaml)
    wrote, skipped, drift = 0, [], []
    seen_columns: set[tuple[str, str]] = set()
    for desc in sorted((root / "data" / "datasets").glob("*.yaml")):
        doc = yaml.safe_load(desc.read_text(encoding="utf-8")) or {}
        relation = (doc.get("table") or {}).get("name") or desc.stem
        schema = (doc.get("table") or {}).get("schema")
        columns = doc.get("columns") or []
        names = {c.get("name") for c in columns}
        for col in columns:
            name, members = col.get("name"), col.get("values")
            if not name or not members:
                continue
            if len(members) > a.max_members:
                skipped.append(f"{relation}.{name} ({len(members)} members — data, not a register)")
                continue
            if (relation, name) in seen_columns:
                continue
            label_col = _label_column(name, names, con, schema, relation, members)
            # WHICH HALF OF A BIJECTIVE PAIR IS THE CODE. `DE` is the code, `Germany` the label —
            # and iterating in descriptor order got it backwards, keying the register on
            # `CountryFull` because that column comes first. The code is the TERSER half: a code set
            # is short by construction, and the register's first column is what the loader reads as
            # the column the warehouse stores.
            if label_col and _terser(col.get("values"), _values_of(columns, label_col)) is False:
                name, label_col = label_col, name
                members = _values_of(columns, name) or members
            # ONE REGISTER PER DIMENSION (DNA P4). A bijective pair is ONE dimension under two
            # spellings — `Country`/`CountryFull` — so the label half is claimed here and never cut
            # as a register of its own. Without this the bundle got two registers for one notion,
            # each naming the other as its label.
            if label_col:
                # BOTH HALVES CLAIMED, and after any swap — a first version added the pre-swap name
                # only, so the label half came round again and wrote the same register a second time.
                seen_columns.add((relation, label_col))
                seen_columns.add((relation, name))
            body = _render(relation, name, members, label_col, con, schema, marker)
            out = root / "data" / "lookups" / f"{_stem(marker, relation, name)}.lookup.csv"
            if a.check:
                if out.read_text(encoding="utf-8") if out.is_file() else "" != body:
                    drift.append(str(out.relative_to(root)))
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(body, encoding="utf-8")
                wrote += 1
                lab = f" label<-{label_col}" if label_col else " (code is its own label)"
                print(f"  {out.name:44} {len(members):>4} member(s){lab}")
    if con is not None:
        con.close()

    if a.check:
        if drift:
            print(f"DRIFT — {len(drift)} register(s) no longer match the measured domains.")
            return 1
        print("OK — every register matches the measured domains.")
        return 0
    for s in skipped:
        print(f"  NOT A REGISTER  {s}")
    if not wrote:
        print("  no column is both bounded and enumerable — nothing to resolve offline. A register "
              "is cut from a domain `mac_profile` captured; if none was, there is none to project.")
    print(f"\nwrote {wrote} register(s) from domains already measured on the descriptors")
    return 0


def _values_of(columns: list, name: str) -> list:
    return next((c.get("values") or [] for c in columns if c.get("name") == name), [])


def _terser(mine: list | None, theirs: list | None) -> bool:
    """Is my half of the pair the shorter-valued one? `DE` over `Germany`."""
    def avg(vals):
        vals = [str(v) for v in (vals or []) if v is not None]
        return sum(len(v) for v in vals) / len(vals) if vals else 0.0
    a, b = avg(mine), avg(theirs)
    return a <= b if (a and b) else True


def _marker(root: pathlib.Path, yaml) -> str:
    """The bundle's own naming marker, so a register is addressable as THIS source's."""
    f = root / "mac.project.yaml"
    if not f.is_file():
        return ""
    doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return str(((doc.get("serving") or {}).get("naming") or {}).get("marker")
               or (doc.get("metadata") or {}).get("dataset") or "")


def _stem(marker: str, relation: str, column: str) -> str:
    """`contoso_gender`, from the marker and the column — the shape the loader's tie-break reads."""
    base = column.lower()
    return f"{marker}_{base}" if marker and not base.startswith(marker) else base


def _label_column(code: str, names: set, con, schema, relation: str, members: list) -> str | None:
    """The sibling column carrying the human name, when the pairing is ONE-TO-ONE and measured.

    BIJECTIVE, BOTH WAYS, and the first version tested only one — which is the same defect this
    session already paid for with `finer_than`. Checking "each code maps to ONE value of the
    candidate" is FUNCTIONAL DEPENDENCE, and a PARENT satisfies it: every `YearQuarter` maps to
    exactly one `Year`, so `Year` was accepted as the LABEL of `YearQuarter`. It is not a label, it
    is a coarser axis, and a register built on it would resolve "2024" to one quarter of four.

    So both directions are measured: each code to one label AND each label to one code. `Country`
    <-> `CountryFull` holds; `YearQuarter` -> `Year` does not.

    A label that is right for most rows is worse than none: it resolves a word to a code that is
    wrong on the remainder, silently. So the pairing is VERIFIED against the warehouse, and a
    candidate that does not hold exactly is dropped.
    """
    if code.lower() in _SELF_LABELLING or con is None or not schema:
        return None
    stem = code[:-3] if code.lower().endswith("key") else code
    candidates = [n for n in names
                  if n != code and (n.startswith(stem) or stem.startswith(n.rstrip("Name")))
                  and n.lower() not in ("", code.lower())]
    for cand in sorted(candidates, key=len):
        if _bijective(con, schema, relation, code, cand):
            return cand
    return None


def _bijective(con, schema: str, relation: str, a: str, b: str) -> bool:
    """One `a` per `b` AND one `b` per `a`. Either direction alone admits a parent."""
    for left, right in ((a, b), (b, a)):
        try:
            rows, _ = con.query(
                f'SELECT count(*) AS d0 FROM (SELECT "{left}" FROM "{schema}"."{relation}" '
                f'GROUP BY "{left}" HAVING count(DISTINCT "{right}") > 1)'
            )
        except Exception:  # noqa: BLE001 - a column that cannot group is not a label
            return False
        if not rows or int(rows[0]["d0"]) != 0:
            return False
    return True


def _render(relation: str, code: str, members: list, label_col: str | None,
            con, schema, marker: str) -> str:
    labels: dict[str, str] = {}
    if label_col and con is not None and schema:
        try:
            rows, _ = con.query(
                f'SELECT "{code}" AS d0, min("{label_col}") AS d1 FROM "{schema}"."{relation}" '
                f'GROUP BY "{code}"'
            )
            labels = {str(r["d0"]): ("" if r["d1"] is None else str(r["d1"])) for r in rows}
        except Exception:  # noqa: BLE001
            labels = {}

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([code, "label", "search_key", "source_view", "confidence", "note"])
    for m in members:
        val = "" if m is None else str(m)
        label = labels.get(val) or val
        w.writerow([val, label, label.strip().lower(), relation, "I",
                    f"measured: {len(members)} members in {relation}.{code}"])
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
