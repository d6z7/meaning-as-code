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

# ── snapshot_collapse: the three defects that put a workaround in an applied bundle ───────────────
# gaps/fpl2 carries ontology/protosql/snapshot.pin_latest_per_cell.yaml because this canon could not do
# the job. mac.schema.json on ProtoSqlFile: "usually a workaround for a canon that is missing or
# broken, and the better fix is upstream." These three are that fix, each with its witness.

# 1. A COMPOSITE key. Shipped broken on 2026-08-19 and reverted the same day: the canon interpolated
#    the parameter raw, so a perfectly ordinary YAML list rendered as a Python list repr —
#    PARTITION BY ['fpl_brand_country_code', ...] — which is not SQL at all.
check("snapshot_collapse (composite key renders as a column list)",
      canon.snapshot_collapse("fpl2.v_fpl_kpi",
                              natural_key=["role", "brand_letter", "fpl_brand_country_code"],
                              order_by="config_reporting_month"),
      ("(SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY role, brand_letter, "
       "fpl_brand_country_code ORDER BY config_reporting_month DESC) AS _rn "
       "FROM fpl2.v_fpl_kpi) WHERE _rn = 1)", []))

# 2. A TIE-BREAK. fpl2's protosql states "fpl_created_at DESC is not optional" beside the vintage; the
#    old signature took a single order_by and could not say it.
check("snapshot_collapse (ordered tie-break)",
      canon.snapshot_collapse("fpl2.v_fpl_kpi", natural_key=["role", "kpi"],
                              order_by=["config_reporting_month", "fpl_created_at"]),
      ("(SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY role, kpi "
       "ORDER BY config_reporting_month DESC, fpl_created_at DESC) AS _rn "
       "FROM fpl2.v_fpl_kpi) WHERE _rn = 1)", []))

# 3. AN UNRESOLVED REFERENCE must fail loudly. A binding may name its key by dereference rather than by
#    retyping it, and check_references proves the anchor resolves — but resolving it needs bundle
#    context this library deliberately lacks. Rendering it would emit the anchor as a column name.
def _raises(fn):
    """Refusing is refusing: a bad partition may surface as a ValueError (a value we reject) or a
    TypeError (a parameter neither the binding nor the descriptor supplied). Both are the canon
    declining to guess, which is the property under test."""
    try:
        fn()
    except (ValueError, TypeError):
        return True
    return False

expect("snapshot_collapse (unresolved descriptor anchor → refuses)",
       _raises(lambda: canon.snapshot_collapse(
           "fpl2.v_fpl_kpi", natural_key="data/datasets/v_fpl_kpi.yaml#x-grain.cell_key",
           order_by="config_reporting_month")))
expect("snapshot_collapse (empty partition → refuses)",
       _raises(lambda: canon.snapshot_collapse("t", natural_key=[], order_by="v")))

# ── the dereference: a binding names WHERE its key lives instead of copying it ────────────────────
# The defect this closes, from gaps/fpl2's own protosql header: the same latest-vintage collapse "got
# WRONG FOUR TIMES IN ONE DAY by careful parties", every time by re-implementing a correct instruction
# from memory at the call site — once moving a figure by 25 %. A seven-column partition copied into
# eight concept files is eight chances to drop one, and dropping `role` folds six reporting
# perspectives into one arbitrary row, silently.
import tempfile as _tf, os as _os
_root = _tf.mkdtemp()
_os.makedirs(_os.path.join(_root, "data", "datasets"))
with open(_os.path.join(_root, "data", "datasets", "sales_fact.yaml"), "w") as _fh:
    _fh.write("table:\n  name: sales_fact\nx-grain:\n  cell_key: [region, product, day]\n")
_concept = {"grounding": {"sources": [{"relation": "warehouse.sales_fact"}]}}

check("render_sql (natural_key READ from the descriptor, not retyped)",
      canon.render_sql("mac.canon.snapshot_collapse",
                       {"table": "warehouse.sales_fact", "order_by": ["loaded_at", "written_at"]},
                       concept=_concept, root=_root),
      ("(SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY region, product, day "
       "ORDER BY loaded_at DESC, written_at DESC) AS _rn FROM warehouse.sales_fact) WHERE _rn = 1)",
       []))

expect("render_sql (no declared cell_key → refuses, never guesses a partition)",
       _raises(lambda: canon.render_sql(
           "mac.canon.snapshot_collapse", {"table": "warehouse.other", "order_by": "loaded_at"},
           concept={"grounding": {"sources": [{"relation": "warehouse.other"}]}}, root=_root)))

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
                               axis_effects={"snapshot_date": "none", "warehouse_id": "additive"})
    expect("additivity_guard (stock summed over time → reject)", len(b) == 1, f"got {b!r}")
    bp = canon.additivity_guard("SELECT SUM(units_on_hand) FROM inventory_snapshot WHERE snapshot_date = DATE '2026-03-31'",
                                measure_column="units_on_hand",
                                axis_effects={"snapshot_date": "none", "warehouse_id": "additive"})
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
