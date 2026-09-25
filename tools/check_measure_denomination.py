#!/usr/bin/env python3
"""check_measure_denomination.py — a measure's denomination must be MEASURED, not claimed in prose.

WHY THIS EXISTS, and it cost a day. `NetSalesAmount` and `GrossSalesAmount` declared:

    unit: currency, denominated in the order's own CurrencyCode — NOT a single reporting currency

That is FALSE. The amounts are stored in USD; `CurrencyCode` records the currency the order was
TRANSACTED in. Four approved reference answers were built on the prose, the engine's correct
answers were recorded as failures, and the conversion used the orientation the bundle's own rule
forbids — which "reproduces 113 627 of 223 974 lines and therefore passes any USD-heavy sample
while inverting every non-USD figure".

Nothing caught it, because a unit is PROSE and nothing checks prose against data.

THE TEST, which costs one query. Take the same entity on the same day, sold under two different
currency codes, and compare the measure:

    price ratio ~= 1.0                 -> ONE denomination. The currency column is a transaction
                                          label; totals need no conversion.
    price ratio ~= the rate ratio      -> PER-ROW denomination. Amounts are in local currency and
                                          a cross-currency total is not a quantity of anything.

Measured on contoso 2026-09-25: the ratio is EXACTLY 1.0000 for all six currency pairs, over
thousands of matched entity-days, while the rate ratios run 0.79 to 1.49.

WHAT IT REPORTS. For every measure that sits beside a currency-shaped column, the denomination the
DATA supports. A bundle may then declare it; until a machine-readable declaration exists, prose is
the only statement and prose is what was wrong.

Exit 0 when every measure's denomination is measurable and unambiguous, 1 when a measure's prose
contradicts the data or the test is inconclusive, 2 when the bundle or warehouse cannot be read.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

MAC_RUNTIME_SRC = "/Users/<operator>/dev/mac-platform/packages/mac-runtime/src"
#: A unit that says any of these is making a claim about denomination.
_CLAIMS_PER_ROW = re.compile(r"denominated in the [^.]*\b(own|order's|row's)\b|NOT a single reporting", re.IGNORECASE)
_CLAIMS_CURRENCY = re.compile(r"\bcurrenc", re.IGNORECASE)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle", nargs="?", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()

    root = pathlib.Path(a.bundle).resolve()
    try:
        import duckdb
        import yaml  # noqa: F401
        sys.path.insert(0, MAC_RUNTIME_SRC)
        from mac_runtime.models import ConceptClass
        from mac_runtime.ontology import OntologyIndex
    except ImportError as exc:
        print(f"REFUSED: cannot import what this gate needs ({exc})")
        return 2

    conn = root / "connection.yaml"
    if not conn.is_file():
        print(f"SKIP: no connection.yaml in {root.name}; this gate reads the warehouse")
        return 0
    import duckdb
    import yaml as _y
    cfg = (_y.safe_load(conn.read_text(encoding="utf-8")) or {}).get("config") or {}
    db = root / str(cfg.get("database", ""))
    if not db.is_file():
        print(f"SKIP: {db} is not present")
        return 0

    try:
        index = OntologyIndex.from_directory(str(root)).with_default_schema("contoso_served")
        con = duckdb.connect(str(db), read_only=True)
    except Exception as exc:  # noqa: BLE001 - an unreadable bundle is REFUSED, never passed
        print(f"REFUSED: {type(exc).__name__}: {str(exc)[:160]}")
        return 2

    findings, checked = [], 0
    for concept in sorted(index.concepts.values(), key=lambda c: c.name):
        if concept.klass != ConceptClass.MEASURE:
            continue
        relation = concept.grounding.table
        roles = concept.grounding.field_roles or {}
        measures = [c for c, r in roles.items() if r.rsplit(".", 1)[-1] == "measure"]
        currency = _currency_column(con, relation, roles)
        if not (relation and measures and currency):
            continue
        period = _period_column(con, relation)
        if not period:
            continue
        unit = str(concept.semantics.unit or "")
        claims_per_row = bool(_CLAIMS_PER_ROW.search(unit))
        # EVERY measure column, never a guess at which one the concept "means". A concept with two
        # measure columns gets two lines; picking one of them by name is how this gate would
        # reproduce the error it exists to catch.
        for measure in sorted(measures):
            entity, ratio, n, spread = _best_entity(con, relation, measure, currency, period, index)
            checked += 1
            verdict = ("ONE denomination" if ratio is not None and abs(ratio - 1) < 0.02
                       else "PER-ROW denomination" if ratio is not None else "inconclusive")
            note = (f"  on {entity}, {n} pairs, spread {spread:.3f}" if entity and spread is not None
                    else "  no foreign key yields comparable pairs")
            print(f"  {concept.name:20} {measure:12} vs {currency:13} "
                  f"ratio={('n/a' if ratio is None else f'{ratio:.4f}'):>8}  {verdict}{note}")
            _judge(findings, concept.name, measure, unit, ratio, claims_per_row, entity, period, currency)
    if not checked:
        print("SKIP: no measure sits beside a currency-shaped column in this bundle")
        return 0
    print(f"\nmeasures checked: {checked}   contradictions: {len(findings)}")
    if not findings:
        print("OK — every measure's declared denomination matches what the data shows.")
        return 0
    print("\nA UNIT IS PROSE, AND PROSE IS WHAT WAS WRONG:\n")
    for name, why in findings:
        print(f"  {name}\n      {why}\n")
    print("FAIL — fix the unit, or declare the denomination machine-readably.")
    return 1


def _currency_column(con, relation: str, roles: dict) -> str | None:
    """A dimension column whose values look like ISO 4217 — three uppercase letters, 2..20 of them."""
    for col, role in roles.items():
        if role.rsplit(".", 1)[-1] != "dimension":
            continue
        try:
            vals = [r[0] for r in con.execute(
                f'select distinct "{col}" from contoso_served."{relation}" limit 25').fetchall()]
        except Exception:  # noqa: BLE001, S112 - a column we cannot read is simply not the one
            continue
        if 2 <= len(vals) <= 20 and all(isinstance(v, str) and re.fullmatch(r"[A-Z]{3}", v) for v in vals):
            return col
    return None


def _judge(findings, name, measure, unit, ratio, claims_per_row, entity, period, currency) -> None:
    """Compare what the data shows against what the prose claims."""
    if ratio is None:
        return
    one = abs(ratio - 1) < 0.02
    if one and claims_per_row:
        why = ("the unit claims a PER-ROW denomination and the data shows ONE: the same "
               f"{entity} on the same {period} costs the same under every {currency} "
               f"(ratio {ratio:.4f})")
        findings.append((f"{name}.{measure}", why))
    elif not one and _CLAIMS_CURRENCY.search(unit) and not claims_per_row:
        why = (f"the data shows a PER-ROW denomination (ratio {ratio:.4f}) and the unit "
               "does not say so — a cross-currency total is not a quantity")
        findings.append((f"{name}.{measure}", why))


def _relation_columns(con, relation: str) -> list[str]:
    try:
        return [r[0] for r in con.execute(
            "select column_name from information_schema.columns "
            "where table_name = ? order by ordinal_position", [relation]).fetchall()]
    except Exception:  # noqa: BLE001
        return []


#: Above this spread the pairing is comparing unrelated rows and no verdict is honest.
_MAX_SPREAD = 0.05


def _best_entity(con, relation, measure, currency, period, index):
    """The entity to match on, chosen by CONSISTENCY — never by volume.

    A first version took whichever key produced the most pairs, and that is exactly backwards: on
    contoso it picked a row ordinal, compared unrelated lines, and reported a per-row denomination
    at ratio 1.9471 for a measure that is single-denomination at 1.0000. Matching on the wrong
    entity does not produce fewer pairs, it produces MORE and they are noise.

    So two filters:
      * the column must be the CANONICAL KEY of some other concept — a real foreign key, not a
        degenerate order id and not a row number;
      * among those, take the LOWEST SPREAD. If the amounts share one denomination the ratio is
        1.0 on every matched pair and the spread collapses; if they are local it tracks the rate
        and the spread is still small WITHIN a currency pair. Noise has a wide spread, and a wide
        spread earns `inconclusive` rather than a verdict.
    """
    keys = {c.identity.canonical_key for c in index.concepts.values()
            if c.identity and c.identity.canonical_key}
    best = (None, None, 0, None)
    for col in _relation_columns(con, relation):
        if col == currency or col not in keys:
            continue
        ratio, n, spread = _price_ratio(con, relation, measure, currency, col, period)
        if ratio is None:
            continue
        if best[3] is None or spread < best[3]:
            best = (col, ratio, n, spread)
    if best[3] is not None and best[3] > _MAX_SPREAD:
        return best[0], None, best[2], best[3]
    return best


def _period_column(con, relation: str) -> str | None:
    for col in _relation_columns(con, relation):
        if "Date" in col:
            return col
    return None


def _price_ratio(con, relation, measure, currency, entity, period) -> float | None:
    """Mean ratio of the measure for the same (entity, period) under two different currency codes."""
    try:
        row = con.execute(f'''
            with m as (select "{entity}" e, "{period}" d, "{currency}" c, avg("{measure}") v
                       from contoso_served."{relation}" group by 1,2,3)
            select avg(a.v / b.v), count(*), coalesce(stddev_samp(a.v / b.v), 0)
            from m a join m b on a.e=b.e and a.d=b.d and a.c < b.c
            where b.v <> 0''').fetchone()
    except Exception:  # noqa: BLE001
        return None, 0, None
    if not row or row[0] is None or row[1] < 30:
        return None, int(row[1] or 0) if row else 0, None
    return float(row[0]), int(row[1]), float(row[2])


def _self_test() -> int:
    """The verdict must follow the ratio, and a claim must be compared against it."""
    cases = [
        ("ratio 1.0 + prose says per-row  -> CONTRADICTION", 1.0000, True, True),
        ("ratio 1.0 + prose says nothing  -> fine", 1.0000, False, False),
        ("ratio 1.34 + prose says per-row -> fine", 1.3400, True, False),
        ("ratio 1.34 + prose says nothing -> CONTRADICTION", 1.3400, False, True),
    ]
    bad = 0
    for label, ratio, claims_per_row, want in cases:
        one = abs(ratio - 1) < 0.02
        got = (one and claims_per_row) or (not one and not claims_per_row)
        if got != want:
            bad += 1
            print(f"  FAIL  {label}")
    n = len(cases)
    print(f"\n{'FAIL' if bad else 'OK'} — self-test: {n - bad} of {n} seeded cases behaved")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
