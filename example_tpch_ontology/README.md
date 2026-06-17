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
python3 tools/validate_schema.py example_tpch_ontology   # structural (L1) — 19/19 clean
python3 tools/check_references.py example_tpch_ontology   # referential — 0 orphans
python3 tools/check_shapes.py    example_tpch_ontology   # constraint (v0.1.6) — built-in MAC invariants
```

(The first two are data-free L1 gates. The shapes gate is satisfied inherently: the schema already
enforces what the universal built-ins check — `concept.class` ∈ the closed six, and a `measure` declares
its additivity.)

Synthetic example — TPC-H is a benchmark schema, not real data.
