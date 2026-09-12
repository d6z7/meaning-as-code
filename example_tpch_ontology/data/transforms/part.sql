-- TPC-H (example) — tpch.part: a passthrough load of the generated raw table.
-- Every column descends 1:1; no cleaning, no renaming, no filtering.
SELECT
    p_partkey,
    p_name,
    p_mfgr,
    p_brand,
    p_type,
    p_size,
    p_retailprice,
    p_comment
FROM tpch_raw.part_raw
