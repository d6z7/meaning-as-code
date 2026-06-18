# TPC-H — from question to SQL, generated *from the ontology*

This is the payoff of MAC. Each question below becomes SQL **mechanically**, by reading the model — not
from memory of TPC-H. Every clause traces to a specific piece of the ontology:

| SQL clause | comes from | layer |
|---|---|---|
| `FROM <table>` / column names | a concept's `grounding` → `data/datasets/<t>.yaml#columns` | Physical |
| `JOIN … ON …` | an **edge**'s `join_rule` | Edges |
| the measure expression in `SELECT` | a **rule**'s `template` (e.g. `net_revenue`) | Rules |
| which columns a rule may touch | the rule's `binds` (field-anchoring) | Concept `contract.rules` |

The split MAC insists on: turning the *question* into an *intent* (which measure, which slice) is the
one probabilistic step. Everything after — resolving the measure to its formula, the slice to a join
path, the entities to tables and columns — is **deterministic execution against the encoded model**. No
identifier here is invented; each is read from a file cited inline. (TPC-H is a synthetic benchmark; these
queries are illustrative and not run against data.)

Schema: `tpch`. Joins available (from `ontology/edges.yaml`, every `join_rule` verbatim):

```
lineitem.l_orderkey  = orders.o_orderkey         (lineitem__part_of__orders)
orders.o_custkey     = customer.c_custkey         (orders__placed_by__customer)
customer.c_nationkey = nation.n_nationkey         (customer__from__nation)
nation.n_regionkey   = region.r_regionkey         (nation__in__region)
(lineitem.l_partkey, l_suppkey) = (partsupp.ps_partkey, ps_suppkey)   (lineitem__supplied_via__partsupp, composite)
partsupp.ps_partkey  = part.p_partkey             (partsupp__of__part)
partsupp.ps_suppkey  = supplier.s_suppkey         (partsupp__from__supplier)
supplier.s_nationkey = nation.n_nationkey         (supplier__from__nation)
```

---

## Q1. "What is net revenue by region?"

**Intent → ontology.** Measure = **Revenue** (`ontology/concepts/finance/revenue.yaml`, a `Flow`), derived by rule
**`net_revenue`** → `SELECT` expression. Slice = region, so traverse `lineitem → orders → customer →
nation → region` (four edges). Label = `region.r_name` (role `value`).

```sql
SELECT r.r_name AS region,
       SUM(l.l_extendedprice * (1 - l.l_discount)) AS net_revenue   -- rule net_revenue.template; binds l_extendedprice, l_discount
FROM tpch.lineitem l
  JOIN tpch.orders   o ON l.l_orderkey  = o.o_orderkey      -- edge lineitem__part_of__orders
  JOIN tpch.customer c ON o.o_custkey   = c.c_custkey       -- edge orders__placed_by__customer
  JOIN tpch.nation   n ON c.c_nationkey = n.n_nationkey     -- edge customer__from__nation
  JOIN tpch.region   r ON n.n_regionkey = r.r_regionkey     -- edge nation__in__region
GROUP BY r.r_name
ORDER BY net_revenue DESC;
```

No fan-out: every edge on the path is many-to-one outward from `lineitem`, so each line contributes its
revenue exactly once — the SUM is sound at the line grain (`data/datasets/lineitem.yaml`: one row per order line).

---

## Q2. "How many order lines have been received, by nation?"

**Intent → ontology.** "Received" is **not** a column — it is a typed rule on LineItem:
`lineitem.state.received_iff_receiptdate` (`binds: [l_receiptdate, l_linestatus]`), which says *a line is
received iff `l_receiptdate IS NOT NULL`*. That rule **is** the `WHERE`. Slice = nation
(`lineitem → orders → customer → nation`).

```sql
SELECT n.n_name AS nation,
       COUNT(*) AS lines_received
FROM tpch.lineitem l
  JOIN tpch.orders   o ON l.l_orderkey  = o.o_orderkey      -- edge lineitem__part_of__orders
  JOIN tpch.customer c ON o.o_custkey   = c.c_custkey       -- edge orders__placed_by__customer
  JOIN tpch.nation   n ON c.c_nationkey = n.n_nationkey     -- edge customer__from__nation
WHERE l.l_receiptdate IS NOT NULL                           -- rule lineitem.state.received_iff_receiptdate
GROUP BY n.n_name
ORDER BY lines_received DESC;
```

The `binds` is what lets this be generated *and checked*: the rule may only reference `l_receiptdate` /
`l_linestatus`, and the `rule-binds-grounded` shape proves both are real `lineitem` columns. A rule can't
silently come to depend on a field the concept doesn't ground.

---

## Q3. "Net revenue from European customers, in 1995."

**Intent → ontology.** Same Revenue rule; two filters — region = `'EUROPE'` (the `nation__in__region`
path) and a calendar year on `orders.o_orderdate` (role `value`, `x-subrole: temporal`).

```sql
SELECT SUM(l.l_extendedprice * (1 - l.l_discount)) AS net_revenue   -- rule net_revenue
FROM tpch.lineitem l
  JOIN tpch.orders   o ON l.l_orderkey  = o.o_orderkey
  JOIN tpch.customer c ON o.o_custkey   = c.c_custkey
  JOIN tpch.nation   n ON c.c_nationkey = n.n_nationkey
  JOIN tpch.region   r ON n.n_regionkey = r.r_regionkey
WHERE r.r_name = 'EUROPE'
  AND o.o_orderdate >= DATE '1995-01-01'
  AND o.o_orderdate <  DATE '1996-01-01';                   -- half-open year window on the temporal column
```

---

## Q4. "Net revenue by part brand, for parts supplied from ASIA." *(the composite join)*

**Intent → ontology.** This exercises the **associative entity**. The path from a line to *both* its part
and its supplier goes through **PartSupp** via the **composite** edge `lineitem__supplied_via__partsupp`
(`(l_partkey, l_suppkey) = (ps_partkey, ps_suppkey)`), then out to `part` (brand) and to `supplier →
nation → region` (the "supplied from ASIA" filter).

```sql
SELECT p.p_brand,
       SUM(l.l_extendedprice * (1 - l.l_discount)) AS net_revenue   -- rule net_revenue
FROM tpch.lineitem l
  JOIN tpch.partsupp ps ON l.l_partkey = ps.ps_partkey
                       AND l.l_suppkey = ps.ps_suppkey         -- edge lineitem__supplied_via__partsupp (COMPOSITE)
  JOIN tpch.part     p  ON ps.ps_partkey = p.p_partkey         -- edge partsupp__of__part
  JOIN tpch.supplier s  ON ps.ps_suppkey = s.s_suppkey         -- edge partsupp__from__supplier
  JOIN tpch.nation   n  ON s.s_nationkey = n.n_nationkey       -- edge supplier__from__nation
  JOIN tpch.region   r  ON n.n_regionkey = r.r_regionkey       -- edge nation__in__region
WHERE r.r_name = 'ASIA'
GROUP BY p.p_brand
ORDER BY net_revenue DESC;
```

PartSupp is an `entity`, not an edge, precisely so the model can route a two-key join through it — and the
generator follows the declared edges rather than guessing that `l_partkey`/`l_suppkey` happen to be FKs.
