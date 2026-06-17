---
type: Index
title: TPCH knowledge bundle
description: OKF bundle projected from the TPCH MAC ontology.
---


# TPCH knowledge bundle

Projected from the **TPCH** MAC ontology by `mac_to_okf.py`. 9 concepts.

| concept | type | description |
|---|---|---|
| [Customer](/Customer.md) | Entity | A party that places orders. |
| [Nation](/Nation.md) | Entity | A country (TPC-H has 25). |
| [Order](/Orders.md) | Entity | The header of a customer order: who placed it (one Customer), when, its total price and status. |
| [Order Line](/LineItem.md) | Event | A single line of an order — one part, supplied by one supplier, in some quantity at some price. |
| [Part](/Part.md) | Entity | A catalogue item that can be ordered. |
| [Part-Supplier](/PartSupp.md) | Entity | The supply of a Part by a Supplier — a reified many-to-many relationship with its own attributes (available quantity, supply cost). |
| [Region](/Region.md) | Entity | A top-level geographic grouping of nations (TPC-H regions: AFRICA, AMERICA, ASIA, EUROPE, MIDDLE EAST). |
| [Revenue](/Revenue.md) | Metric | The monetary value of sales, net of discount: per order line, l_extendedprice × (1 − l_discount). |
| [Supplier](/Supplier.md) | Entity | A party that supplies parts. |
