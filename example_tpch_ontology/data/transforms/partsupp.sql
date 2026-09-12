-- TPC-H (example) — tpch.partsupp: a passthrough load of the generated raw table.
-- Every column descends 1:1; no cleaning, no renaming, no filtering.
SELECT
    ps_partkey,
    ps_suppkey,
    ps_availqty,
    ps_supplycost,
    ps_comment
FROM tpch_raw.partsupp_raw
