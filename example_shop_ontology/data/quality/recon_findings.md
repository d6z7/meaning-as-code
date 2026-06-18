# SHOP (example) — reconnaissance findings

Synthetic example. Illustrates the **execution-validation loop**: a structurally valid model can still
be wrong about the data, and running a query against the warehouse corrects it. Not real data.

---

## FIND-SHOP-001 — "Revenue" was modelled as gross; the data has refunds, so gross overstates earnings

**Date:** 2026-06-05
**Severity:** correctness (silent overstatement)
**Status:** RESOLVED (model corrected)

### Documented claim (the first draft of the model)

The initial `Revenue` concept defined revenue as `SUM(orders.gross_amount)` — the order total at
checkout. The YAML validated cleanly: well-formed `measure`, additivity declared, grounding present.
Structurally perfect.

### Discovery query + observed result

Running the model's implied query and sanity-checking against a second source (the `refunds` table the
first draft ignored):

```sql
SELECT SUM(gross_amount)                              AS gross_revenue,        -- 1,000,000
       SUM(gross_amount) - (SELECT SUM(refund_amount) FROM refunds) AS net_revenue   -- 920,000
FROM orders
WHERE paid_at IS NOT NULL;
```

Gross revenue = 1,000,000; net of refunds = 920,000. The model's "revenue" was **8% too high** — it
ignored that returned orders generate refunds.

### The gap

The concept was *well-formed* but *wrong about the business*: "revenue" in this shop means NET (after
returns), and returns are material (~8%). A pretty YAML passed structural validation and still
misrepresented the headline number. Only running it against the data surfaced the refund volume.

### Resolution

- `Revenue` redefined: net = gross − refunds; `Revenue` defaults to NET (a constraint now asserts this).
- The computation moved to the **rules layer** as `net_revenue` (a derivation with a renderable SQL
  form joining `orders` to `refunds`) — not inlined in the concept.
- This is the framework's point: **structure ≠ correctness**; execution validation is part of authoring.

### Cross-references

- `concepts/finance/revenue.yaml` (corrected concept)
- `rules.yaml > net_revenue` (the derivation)
