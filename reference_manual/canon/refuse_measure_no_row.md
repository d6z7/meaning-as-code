---
title: "Canon — refuse_measure_no_row"
part_of: reference_manual/canon
status: DECLARED BUT NOT IMPLEMENTED — two measures in the worked bundle bind it
scope: GENERIC — domain-neutral
---

# Canon — `mac.canon.refuse_measure_no_row`

> The runtime does not implement this canon. `GrossSalesAmount` and `NetSalesAmount` declare it and
> get no behaviour.

## Serves

`exclusion_no_evidence` — the question that must not be answered **0** when the truth is
*"there is no row"*.

## Contract

A **RENDER canon**: it produces refusal text, not SQL.

| param | read from |
|---|---|
| `label` | `concept.label` |
| `null_is_real` | `concept.semantics.null_semantics` |

`params_from` means these are **not authored on the binding** — they are read from declarations that
already exist. A binding restating one is asserting a fact with a home: it agrees (harmless
duplication) or it disagrees (a contradiction nothing arbitrates).

**Intended guarantee:** when a measure has no row for the resolved scope, emit a refusal saying so,
rather than letting `SUM` over an empty set return `0` or `NULL`.

## The distinction it protects

Three different things, one number:

| the truth | what a bare SUM returns |
|---|---|
| the rows exist and total zero | `0` — **correct** |
| no row matched the scope | `0` or `NULL` — **a fabrication** |
| the measure is null on matched rows | depends on the engine |

Only the first deserves `0`. `null_semantics` is what distinguishes them, and it is declared on 20
of 21 contoso concepts and **read by nothing** — which is why this canon has a job and no
implementation.

## Limits

- **Not implemented.**
- A render canon cannot tell the three cases apart on its own: it needs the planner to say *whether
  a row matched*, which is a fact about execution, not about the ontology.
