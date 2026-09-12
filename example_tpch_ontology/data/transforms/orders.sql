-- TPC-H (example) — tpch.orders: a passthrough load of the generated raw table.
-- Every column descends 1:1; no cleaning, no renaming, no filtering.
SELECT
    o_orderkey,
    o_custkey,
    o_orderstatus,
    o_totalprice,
    o_orderdate,
    o_orderpriority,
    o_comment
FROM tpch_raw.orders_raw
