-- TPC-H (example) — tpch.supplier: a passthrough load of the generated raw table.
-- Every column descends 1:1; no cleaning, no renaming, no filtering.
SELECT
    s_suppkey,
    s_name,
    s_nationkey,
    s_phone,
    s_acctbal,
    s_comment
FROM tpch_raw.supplier_raw
