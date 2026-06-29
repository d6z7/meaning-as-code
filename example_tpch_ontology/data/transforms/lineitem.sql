-- TPC-H (example) — data/transforms/lineitem.sql
-- Realizes data/transforms/lineitem.yaml: raw tpch_raw.lineitem_raw, enriched from the orders dataset,
-- into the clean tpch.lineitem fact the LineItem concept binds to. Synthetic; illustrative only.
CREATE OR REPLACE VIEW tpch.lineitem AS
SELECT
    r.l_orderkey,
    r.l_linenumber,
    r.l_partkey,
    r.l_suppkey,
    r.l_quantity,
    r.l_extendedprice,
    -- discount-basis-points-to-fraction: 700 (bps) -> 0.07, the [0,1] fraction Revenue expects
    cast(r.l_discount_bps AS decimal(6, 4)) / 10000  AS l_discount,
    r.l_returnflag,
    r.l_linestatus,
    r.l_shipdate
FROM tpch_raw.lineitem_raw r
-- view-on-view enrichment (kind: dataset): join the produced orders relation, not a raw table
JOIN tpch.orders o ON o.o_orderkey = r.l_orderkey;
