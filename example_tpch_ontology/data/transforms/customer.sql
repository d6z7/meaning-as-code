-- TPC-H (example) — tpch.customer: a passthrough load of the generated raw table.
-- Every column descends 1:1; no cleaning, no renaming, no filtering.
SELECT
    c_custkey,
    c_name,
    c_nationkey,
    c_phone,
    c_acctbal,
    c_mktsegment,
    c_comment
FROM tpch_raw.customer_raw
