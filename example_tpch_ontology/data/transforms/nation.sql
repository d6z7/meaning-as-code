-- TPC-H (example) — tpch.nation: a passthrough load of the generated raw table.
-- Every column descends 1:1; no cleaning, no renaming, no filtering.
SELECT
    n_nationkey,
    n_name,
    n_regionkey,
    n_comment
FROM tpch_raw.nation_raw
