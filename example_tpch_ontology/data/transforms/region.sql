-- TPC-H (example) — tpch.region: a passthrough load of the generated raw table.
-- Every column descends 1:1; no cleaning, no renaming, no filtering.
SELECT
    r_regionkey,
    r_name,
    r_comment
FROM tpch_raw.region_raw
