#!/usr/bin/env python3
"""
test_canon.py — "the canons run". Executes each canon library UDF (tools/canon) on the demo from its
reference_manual/canon/*.md entry and asserts the documented result. This is the canon library's own
execution validation (reference_manual/04_discipline.md §4.4: "a canon that doesn't run is prose in a
code costume").

Pure canons are asserted to their exact documented output. The sqlglot-backed canons
(composite_key_guard, additivity_guard, exclusion_filter, axis_default) are asserted on robust
properties (a guard fires / stays silent; a rewrite binds the right params) and are SKIPPED with a
notice when sqlglot is not installed — the manual flags them "reference, not finished — needs a parser".

Usage:  python3 tests/test_canon.py
Exit:   0 = all run canons behaved as documented · 1 = a canon misbehaved · 2 = setup error
"""
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

try:
    import canon
except Exception as e:  # noqa: BLE001
    print(f"[setup] cannot import canon library: {e}", file=sys.stderr)
    sys.exit(2)

passed, failed, skipped = 0, 0, 0


def check(name, got, want):
    global passed, failed
    if got == want:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}\n      got:  {got!r}\n      want: {want!r}")


def expect(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}   {detail}")


# ----------------------------------------------------------------- pure canons (exact output)

check("densify",
      canon.densify("daily_sales", "units",
                    keys=["sale_date", "store_id", "product_id"],
                    grid="SELECT d.sale_date, sp.store_id, sp.product_id FROM calendar d CROSS JOIN store_product sp"),
      ("SELECT g.sale_date, g.store_id, g.product_id, COALESCE(f.units, 0) AS units "
       "FROM (SELECT d.sale_date, sp.store_id, sp.product_id FROM calendar d CROSS JOIN store_product sp) g "
       "LEFT JOIN daily_sales f ON g.sale_date = f.sale_date AND g.store_id = f.store_id "
       "AND g.product_id = f.product_id", []))

check("scoped_latest (scoped)",
      canon.scoped_latest("sales_fact", "month", scope={"scenario": "ACTUAL"}),
      ("(SELECT MAX(month) FROM sales_fact WHERE scenario = ?)", ["ACTUAL"]))

check("scoped_latest (whole table)",
      canon.scoped_latest("sales_fact", "month"),
      ("(SELECT MAX(month) FROM sales_fact)", []))

check("closure_anomaly_check (closed → check)",
      canon.closure_anomaly_check("orders", "status", closure="closed",
                                  known_values=["PLACED", "PAID", "SHIPPED", "DELIVERED", "RETURNED", "CANCELLED"]),
      ("SELECT DISTINCT status FROM orders WHERE status NOT IN (?, ?, ?, ?, ?, ?)",
       ["PLACED", "PAID", "SHIPPED", "DELIVERED", "RETURNED", "CANCELLED"]))

check("closure_anomaly_check (open → no check)",
      canon.closure_anomaly_check("orders", "payment_method", closure="open",
                                  known_values=["CARD", "PAYPAL", "INVOICE"]),
      None)

check("hierarchy_rollup",
      canon.hierarchy_rollup("category", id_col="category_id", parent_col="parent_id", root="C1"),
      ("WITH RECURSIVE subtree(category_id) AS (SELECT category_id FROM category WHERE category_id = ? "
       "UNION ALL SELECT c.category_id FROM category c JOIN subtree s ON c.parent_id = s.category_id) "
       "SELECT category_id FROM subtree", ["C1"]))

check("snapshot_collapse (current)",
      canon.snapshot_collapse("dim_product", natural_key="product_id", order_by="valid_from"),
      ("(SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY valid_from DESC) "
       "AS _rn FROM dim_product) WHERE _rn = 1)", []))

check("snapshot_collapse (as-of)",
      canon.snapshot_collapse("dim_product", natural_key="product_id", order_by="valid_from",
                              valid_from="valid_from", valid_to="valid_to", as_of="2026-01-15"),
      ("(SELECT * FROM dim_product WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to > ?))",
       ["2026-01-15", "2026-01-15"]))

d_ask = canon.ambiguity_gate("Europe", candidates=["continent_europe", "eu_members", "eu_sales_region"])
expect("ambiguity_gate (>1 unpinned → ask)", d_ask.action == "ask" and d_ask.chosen is None)
d_pin = canon.ambiguity_gate("Europe", candidates=["continent_europe", "eu_members", "eu_sales_region"],
                             pinned="eu_members")
expect("ambiguity_gate (pinned → resolve)", d_pin.action == "resolve" and d_pin.chosen == "eu_members")
d_one = canon.ambiguity_gate("DACH", candidates=["dach_region"])
expect("ambiguity_gate (single → resolve)", d_one.action == "resolve" and d_one.chosen == "dach_region")


# ----------------------------------------------------------------- sqlglot-backed canons (skip if absent)

if canon.sqlglot is None:
    skipped = len(canon.NEEDS_SQLGLOT)
    print(f"\n  ⚠ sqlglot not installed — skipping {skipped} SQL-parsing canon(s): "
          f"{sorted(canon.NEEDS_SQLGLOT)}")
else:
    rej = canon.composite_key_guard("SELECT count(*) FROM product WHERE size_code='M'",
                                    code_column="size_code", scope_columns=["brand_id"])
    expect("composite_key_guard (bare code → reject)", len(rej) == 1, f"got {rej!r}")
    ok = canon.composite_key_guard("SELECT count(*) FROM product WHERE brand_id='BR-NORD' AND size_code='M'",
                                   code_column="size_code", scope_columns=["brand_id"])
    expect("composite_key_guard (scoped → pass)", ok == [], f"got {ok!r}")

    a = canon.additivity_guard("SELECT SUM(units_sold) FROM sales WHERE month BETWEEN '2026-01' AND '2026-03'",
                               measure_column="units_sold",
                               axis_effects={"month": "additive", "product_id": "additive"})
    expect("additivity_guard (additive → pass)", a == [], f"got {a!r}")
    b = canon.additivity_guard("SELECT SUM(units_on_hand) FROM inventory_snapshot "
                               "WHERE snapshot_date BETWEEN '2026-01-01' AND '2026-03-31'",
                               measure_column="units_on_hand",
                               axis_effects={"snapshot_date": "point_in_time", "warehouse_id": "additive"})
    expect("additivity_guard (stock summed over time → reject)", len(b) == 1, f"got {b!r}")
    bp = canon.additivity_guard("SELECT SUM(units_on_hand) FROM inventory_snapshot WHERE snapshot_date = DATE '2026-03-31'",
                                measure_column="units_on_hand",
                                axis_effects={"snapshot_date": "point_in_time", "warehouse_id": "additive"})
    expect("additivity_guard (time pinned → pass)", bp == [], f"got {bp!r}")

    sql, params = canon.exclusion_filter("SELECT count(*) FROM product", column="product_id",
                                         not_like=["P-TEST-%"])
    expect("exclusion_filter (not_like binds)", params == ["P-TEST-%"] and "NOT LIKE" in sql.upper(),
           f"got {(sql, params)!r}")

    sql2, params2 = canon.axis_default("SELECT SUM(amount) FROM sales_fact WHERE month = '2026-03'",
                                       axis_column="scenario", default_value="ACTUAL")
    expect("axis_default (unpinned → inject default)", params2 == ["ACTUAL"] and "scenario" in sql2,
           f"got {(sql2, params2)!r}")
    sql3, params3 = canon.axis_default("SELECT SUM(amount) FROM sales_fact WHERE scenario = 'PLAN'",
                                       axis_column="scenario", default_value="ACTUAL")
    expect("axis_default (already pinned → untouched)", params3 == [], f"got {(sql3, params3)!r}")


# ----------------------------------------------------------------- summary

print(f"\nCANON TESTS: {passed} passed, {failed} failed, {skipped} skipped "
      f"(of {len(canon.CANON_NAMES)} registered canons)")
sys.exit(1 if failed else 0)
