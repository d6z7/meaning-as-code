# TPC-H — a second worked MAC example (the decision-support benchmark)

A complete, **synthetic** MAC ontology over the well-known **TPC-H** schema (the TPC decision-support
benchmark — public, precisely specified, not real data). It complements `example_shop_ontology/` with a
*richer* shape: a geography **hierarchy**, an **associative entity**, a **composite-key fact**, and a
**derived measure** — the framework applied end-to-end on a dataset most data people already know.

## What it models (the 8 TPC-H tables)

```
            Region ──< Nation ──< Customer ──< Orders ──< LineItem >── PartSupp >── Part
                                  Supplier ──────────────────────────^   │              ^
                                       ^─────────────────────────────────┘──────────────┘
```

- **Region, Nation** (`entity`) — the geography hierarchy (`nation__in__region`); customers and
  suppliers roll up through their nation to a region.
- **Customer, Supplier** (`entity`) — the demand and supply parties, each `from__nation`.
- **Part** (`entity`) — the catalogue item; **PartSupp** (`entity`) — the **associative entity** reifying
  the part↔supplier many-to-many *with attributes* (availqty, supplycost). It is an entity, not an edge,
  precisely because an edge cannot carry data.
- **Orders** (`entity`) — the order header, `placed_by` a customer.
- **LineItem** (`event`) — the central fact (composite key order + line), with a fulfilment **lifecycle**
  (shipped → received → returned); `part_of` an order and `supplied_via` a PartSupp (composite join).
- **Revenue** (`measure`, derived) — net revenue `SUM(l_extendedprice × (1 − l_discount))`, a `Flow`
  referencing `mac.MeasureType.Flow`; computed by the rule, never stored.

## The four layers, all present

| Layer | Files | Shows |
|---|---|---|
| **Concept** | `concepts/**` (9) | the `entity` / `event` / `measure` classes; a hierarchy; an associative entity; a derived measure |
| **Physical** | `tables/**` (8) | grounding targets, column roles (incl. `composite_key_part`), FKs |
| **Edges** | `edges.yaml` (8) | every relation between concepts, incl. a **composite** join (`lineitem → partsupp`) |
| **Rules** | `rules.yaml` (1) | `net_revenue` — a derivation with a renderable SQL template |
| **Field-anchoring** | `LineItem.contract.rules` (2) | typed behavioural rules **`binds`**-ed to the columns they govern (e.g. revenue → `l_extendedprice`, `l_discount`); the `rule-binds-grounded` shape verifies, cross-file, that each bind is a real grounded column |

## Validate

```bash
./validate.sh        # runs all three MAC gates against this example (from anywhere)
```

It runs, in order, the three data-free **L1** gates — structural (`validate_schema.py` → `mac.schema.json`,
19/19 clean), referential (`check_references.py` → 0 orphans), and constraint (`check_shapes.py` → the
built-in shapes, incl. the cross-file `rule-binds-grounded` invariant) — and exits non-zero if any fails.
L1 proves *conformance*, not correctness (it does not assert a column exists in a warehouse); L2/L3 remain
(see [../CONFORMANCE.md](../CONFORMANCE.md)).

Synthetic example — TPC-H is a benchmark schema, not real data.
