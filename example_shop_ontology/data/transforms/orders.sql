-- SHOP (example) — data/transforms/orders.sql
-- The executable realization of data/transforms/orders.yaml: raw shop_raw.orders_raw -> the clean
-- shop_warehouse.orders relation the Order concept binds to. Synthetic; illustrative only.
CREATE OR REPLACE VIEW shop_warehouse.orders AS
SELECT
    order_id,
    customer_id,
    -- status-canonicalize: collapse mixed casing/synonyms to the canonical OrderStatus token set
    CASE lower(trim(status))
        WHEN 'paid'      THEN 'paid'
        WHEN 'placed'    THEN 'placed'
        WHEN 'shipped'   THEN 'shipped'
        WHEN 'delivered' THEN 'delivered'
        WHEN 'cancelled' THEN 'cancelled'
        WHEN 'canceled'  THEN 'cancelled'
    END                                   AS status,
    placed_at,
    -- amount-to-decimal: integer cents -> decimal currency, so currency math never truncates
    cast(gross_cents AS decimal(12, 2)) / 100  AS gross_amount
FROM shop_raw.orders_raw;
