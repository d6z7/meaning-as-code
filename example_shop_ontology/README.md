# The Shop Ontology — a worked example of the framework

A tiny, **synthetic** e-commerce ontology that applies the four-layer YAML framework end to end.
It exists to make the framework concrete: every construct the framework defines appears here, on a
neutral domain (an online shop), with no real data. It is the canonical worked example for
[`../FRAMEWORK.md`](../FRAMEWORK.md) and the key reference [`../CONCEPT_SPEC.md`](../CONCEPT_SPEC.md) —
read those for the *why* and the *what*, then read these files to see the framework applied.

## What it demonstrates

**All six concept classes, one each:**

| concept | class | file | shows |
| --- | --- | --- | --- |
| Customer | **entity** | `concepts/customer/customer.yaml` | a structured thing with identity |
| Order | **event** | `concepts/order/order.yaml` | the `lifecycle:` block (placed→…→returned, phases) |
| OrderStatus | **enumeration** | `concepts/order/order_status.yaml` | a closed `value_set:` |
| Product | **reference** | `concepts/catalog/product.yaml` | a dimension facts point at |
| Category | **grouping** | `concepts/catalog/category.yaml` | roll-up above the leaf (nested) |
| Revenue | **measure** | `concepts/finance/revenue.yaml` | additivity, unit, a derivation |

**All four layers:**

- **Concept** — the six files above (`concepts/`).
- **Rules** — `rules.yaml` → `net_revenue` (gross − refunds), the one derivation. Computation lives
  here, not inlined in `Revenue`.
- **Edges** — `edges.yaml` → `order__placed_by__customer`, `product__belongs_to__category`. Relations
  live here, not as properties of the concepts.
- **Physical** — `tables/orders.yaml`, the grounding target the concepts point at.

**The execution-validation loop** — `recon_findings.md` → FIND-SHOP-001: the first draft modelled
revenue as gross; it validated structurally but was 8% wrong because the data has refunds. Running the
query caught it; the model was corrected. *Structure ≠ correctness.*

## How to read it

1. Start with `concepts/order/order.yaml` — the richest concept (an event with a lifecycle).
2. See how `Revenue` (`concepts/finance/revenue.yaml`) points at a rule rather than inlining a formula
   — then read that rule in `rules.yaml`.
3. Note that `Order placed_by Customer` is in `edges.yaml`, not as a property on either — relations are
   their own layer.
4. Read `recon_findings.md` for why a clean-validating model still needed execution to be correct.

## Note on validation

These files follow the canonical v0.1.6 shape and pass all three MAC gates. Run them together:

```sh
./validate.sh        # structural + referential + constraint, against this example (from anywhere)
```

It runs `validate_schema.py` (structural — closed vocabulary, required keys), `check_references.py`
(referential — internally whole, every `mac.*` term resolves), and `check_shapes.py` (constraint — the
built-in shapes) in order, and exits non-zero if any fails. A clean run means *well-formed and conformant*
(L1) — correctness of the data claims is a separate, execution-validation step (L2; see `recon_findings.md`).

*Synthetic data. No connection to any real shop or any real business data — the example is entirely
fabricated so it can be published and reused freely.*
