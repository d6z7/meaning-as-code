---
title: "Pattern — Explicit closure (is this value set closed, open, or unknown?)"
part_of: reference_manual/patterns
status: prototype
scope: GENERIC — domain-neutral. Example from example_shop_ontology/ (OrderStatus, PaymentMethod).
---

# Pattern — Explicit closure

## Initial state — what you're handed

Two code columns on the `orders` table. You probe their distinct values:

```sql
SELECT DISTINCT status        FROM orders;
-- PLACED, PAID, SHIPPED, DELIVERED, RETURNED, CANCELLED

SELECT DISTINCT payment_method FROM orders;
-- CARD, PAYPAL, INVOICE          (… and APPLEPAY first appeared last month)
```

| column | distinct values seen | is the set complete? |
| --- | --- | --- |
| `status` | 6 lifecycle states | **yes** — fixed by the order state machine |
| `payment_method` | 3 (was 2 last quarter) | **no** — providers are onboarded over time |

**Why this is dangerous.** From the data alone the two columns look identical — "a small set of short
codes." But one set is *complete and fixed* (a new `status` value is a bug) and the other is *growing* (a new
`payment_method` is just Tuesday). That distinction is a fact about the **world**, not about the rows — no
`SELECT` can recover it — yet every data-quality check and every "did we miss a case?" question depends on
knowing which world you are in.

## The question, and the answer

> **The question** (what the data can't tell you): *Is this value set complete — an unseen value is a bug —
> or open — an unseen value is expected?*
>
> **The answer** (the fact we supply): *`status` is **closed**; `payment_method` is **open**. This is a fact
> about the world, not the rows; supplied as `closure: closed|open` stated with the value set and forced at
> authoring time.*

## The pattern (the structured entry)

```yaml
pattern: explicit_closure
also_known_as: [open-world vs closed-world assumption, closed/open value set, owl:oneOf vs open class]
tradition: rdf   # RDF's home turf — but its default is the opposite of what you usually want
constellation: >
  A value set, and the unavoidable question: is it CLOSED (every member is known; an unseen value is a
  data error) or OPEN (new members appear over time; an unseen value is expected)? OrderStatus is closed —
  the lifecycle has a fixed set of states. PaymentMethod is open — a new wallet or provider can be added
  next quarter. The two demand opposite handling, and the difference is invisible in the data itself.
prior_art:
  relational: >
    Maybe a CHECK constraint (asserts closed) or a FK to a reference table (asserts membership) — but most
    code columns have neither, and "is this set closed?" is nowhere recorded. The closed-world assumption is
    implicit, and usually wrong for any set that evolves.
  dimensional: >
    A dimension table lists the values seen so far; whether the set is closed is not a stated property of
    the dimension. You cannot tell a complete reference list from a snapshot of "values so far."
  rdf: >
    THIS is RDF's domain — `owl:oneOf` for a closed set, an open class otherwise. But RDF's global default
    is the OPEN-world assumption, and the OWL machinery to say "closed" is expressive yet rarely authored;
    the modeller must deliberately opt in, and usually doesn't.
mac_expression: >
  An `enumeration` concept MUST carry `closure: closed | open | unknown` (+ `closure_why`), living WITH the
  value set — not in `semantics`, not omitted. The framework FORCES the choice at authoring time. `unknown`
  is itself a first-class, honest state ("we have not yet confirmed whether this set is closed").
why_better: >
  The open/closed-world question — which RDF leaves to an unused OWL feature and which relational/BI leave
  undocumented — is made a MANDATORY, single-homed, agent-readable fact. The agent can now correctly answer
  "are there orders in a status we don't recognise?" (a valid data-quality check ONLY because OrderStatus
  is closed) and knows NOT to raise that alarm for a newly added PaymentMethod. Closure stops being a
  guess.
projects_to:
  rdf: "owl:oneOf (closed) / an open class with no oneOf (open)"
  graph: "an enumerated value set (closed) / an open value set (open)"
  relational: "a complete reference table + CHECK (closed) / an extensible reference table (open)"
antipattern: >
  Assuming closed (and rejecting legitimate new values) or assuming open (and missing real anomalies);
  putting `closure` in `semantics:` instead of with the value set (COOKBOOK C5).
status: clean   # closure (open/closed/unknown) + closure_why is a required, validator-checked part of an enumeration
canon_ref: [CONCEPT_SPEC.md §6 (values/closure), MODELLERS_COOKBOOK.md A3/C5, FRAMEWORK.md §11 (oneOf projection)]
```

## The determinism border

Per [AUTHORING.md](../AUTHORING.md) A4 — here a skeleton flag *decides whether a behaviour exists at all*:

| Behaviour | Kind | How |
| --- | --- | --- |
| Whether an "unknown value" check should exist | **skeleton** | the `closure` flag (closed → yes; open → no) |
| The anomaly query for a closed set | **canon-backed** | [`closure_anomaly_check`](../canon/closure_anomaly_check.md) |
| Declining the check for an open set (no false alarms) | **canon-backed** | the *same* canon returns `None` for open/unknown |
| interpretative remainder | **none** | the closure flag decides deterministically |

```yaml
# OrderStatus — closed: the check exists
realized_by: { udf: closure_anomaly_check,
               params: { table: orders, column: status, closure: closed,
                         known_values: [PLACED, PAID, SHIPPED, DELIVERED, RETURNED, CANCELLED] } }

# PaymentMethod — open: the SAME canon returns None → no check
realized_by: { udf: closure_anomaly_check,
               params: { table: orders, column: payment_method, closure: open,
                         known_values: [CARD, PAYPAL, INVOICE] } }
```

The whole point of the pattern, now mechanical: the *same* check is emitted for `status` and **declined**
for `payment_method`, decided solely by the skeleton `closure` flag — no model judgement in the loop.

## The footgun, concretely

Two enumerations from the shop, opposite closures:

```yaml
# OrderStatus — closed: the lifecycle states are fixed and complete
closure: closed
closure_why: "the order lifecycle is a fixed state machine (PLACED…CANCELLED); any other value is a defect"

# PaymentMethod — open: new providers are onboarded over time
closure: open
closure_why: "payment providers are added as the business integrates them; new codes are expected, not errors"
```

Now the *same* data-quality question routes correctly:

- *"Flag any order whose status is not a known value."* → **valid** against OrderStatus (closed): an unknown
  status is a genuine anomaly worth surfacing.
- The identical check against PaymentMethod (open) would **false-alarm on every newly added method** — so a
  grounded agent does not run it, because the model says the set is expected to grow.

Without the closure fact, an agent has to guess which world it is in — and either guess produces a wrong
answer for half the value sets in any real system. Forcing the choice at authoring time is the cheapest
place to settle it.
