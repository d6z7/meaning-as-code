---
title: "Meaning-as-Code in the loop: from a question to a provenance-backed answer"
date: 2026-06-17
status: article — architecture companion to meaning-as-code.md
scope: GENERIC — domain-neutral. A concrete deployment (role-agents, access policy) is left to the application.
---

# Meaning-as-Code in the loop

Where does MAC actually *sit*? Between two worlds that don't speak the same language: a **relational
database**, which holds values, and an **LLM agent**, which holds language. The database knows that
`l_extendedprice` is `4500.00`; it does not know that figure is gross, that revenue is net of discount, or
that "Europe" is a roll-up reached through four joins. The agent knows what a person *means* by "European
revenue last year"; it does not know your columns. **MAC is the layer that carries the meaning between
them** — the knowledge the agent reads to turn an intent into the right query, and to explain the answer.

## One probabilistic step, then deterministic execution

The single idea the loop is built on:

> Turning a question into an **intent** — which measure, which slice, which period — is probabilistic.
> Everything after is **deterministic execution against the encoded model**: resolve the entities to
> codes, choose the columns, pick the join path, assemble the SQL, run it, read the result, cite the
> source.

Most of an agent's failures come from leaving the deterministic half *implicit* — letting the model guess
the revenue formula or the join. MAC pulls every deterministic decision out of the model's head and into a
file it reads. The guess shrinks to one step; the rest is execution you can audit.

## The loop

```
   ❶ QUESTION  (natural language)
        │
        │   PROBABILISTIC — the one guess
        ▼
   ❷ INTERPRET → INTENT            ┌───────────────────────────┐
        │   measure? slice?        │   MEANING-AS-CODE          │
        │   period? grain?         │   (the four levels)        │
        ▼                          │                            │
   ┌─────────────────┐  reads      │  Meaning   → concept defs  │
   │   LLM AGENT     │◀───────────▶│  Ontology  → edges (joins) │
   │  (orchestrator) │             │  Semantic  → rules         │
   └───────┬─────────┘             │  Physical  → grounding     │
           │   DETERMINISTIC EXECUTION └────────────────────────┘
           │   ❸ resolve intent → entities→codes · column · join path
           │   ❹ generate SQL    SELECT←rule · JOIN←edge · table/col←grounding · binds
           ▼
   ┌─────────────────┐   ❺ execute (run SQL) ───────────▶  ┌──────────────────┐
   │  RELATIONAL DB  │                                      │   LLM AGENT      │
   │ structured data │   ❻ rows ──────────────────────────▶│                  │
   └─────────────────┘                                      └────────┬─────────┘
           ❼ interpret results  (plausible? additivity honoured? grain right?)
           ❽ EXPLAIN PROVENANCE  ◀──────────────────────────────────┘
              every clause cites a concept · an edge · a rule — and the rows it ran on
```

## Each stage, and what MAC contributes

| Stage | Probabilistic? | What MAC supplies |
|---|---|---|
| ❷ **Interpret** → intent | **yes** (the only guess) | the closed vocabulary of concepts/measures the intent can name — so the guess lands on real things |
| ❸ **Resolve** intent → codes/columns | no | concept `grounding` + enumerations: an entity resolves to its codes, a label to its column |
| ❹ **Generate SQL** | no | the **Rules** (the `SELECT` formula), the **Edges** (`JOIN … ON …`), the **Physical** layer (tables/columns), `binds` (which columns a rule may touch) |
| ❺ **Execute** | no | — (the warehouse runs it) |
| ❻–❼ **Interpret results** | partly | measure `semantics` (additivity, grain) tell the agent whether a SUM is even legal, and what a sane magnitude is |
| ❽ **Explain provenance** | no | every clause already traces to a cited model element — provenance is read off, not reconstructed |

The four **levels** from [positioning.md](positioning.md) line up with the loop: *Meaning* scopes the
interpretation, *Ontology* and *Semantic* and *Physical* drive generation, and *Semantic* (additivity,
grain) guards the reading of the result.

## Provenance is a byproduct, not a feature

This is the part worth dwelling on. Because every clause of the generated query traces to a specific model
element — the `SELECT` to a rule's formula, each `JOIN` to an edge's `join_rule`, each table/column to the
Physical layer (exactly what the worked examples' `QUERIES.md` demonstrate) — the agent can **explain why
an answer is what it is by citing the model**, not by post-hoc rationalization. "This is net revenue
(rule `net_revenue`), summed over lines joined to region through these four edges, for orders in 1995."
The lineage from number → SQL → meaning is mechanical.

The same property lets the agent **refuse honestly**. Ask for something the edges don't connect — "revenue
by a dimension no join reaches" — and a correct generator reports the missing edge instead of fabricating
a column (see the shop's unanswerable case in [its QUERIES.md](../example_shop_ontology/QUERIES.md)). A
model that knows the boundary of what it can answer is worth more than one that always answers.

## Where this fits in the bigger picture

This loop is the **open-components route to the capability the all-in-one platforms sell** — semantics,
lineage, and governance over a warehouse — without buying the platform or surrendering your meaning to its
format. MAC is the meaning + lineage layer; the database is whatever you already run; the agent is whatever
model you choose. The gates (structural · referential · constraint) keep the model trustworthy at **L1**;
execution (**L2**) and SME confirmation (**L3**) close the rest of the trust gradient.

A real deployment adds things this domain-neutral picture leaves out: the agent is usually **several
role-agents** (one interprets, one executes, one judges plausibility), and it runs **inside the user's
access envelope** so the warehouse's own permissions still bind. Those are application concerns. The
framework's job is the layer in the middle — the written-down meaning that turns a guessing agent into one
that executes against a model and shows its work.

---

*Companions: [meaning-as-code.md](meaning-as-code.md) (the idea) · [positioning.md](positioning.md) (why
this over OSI / platforms) · the worked [shop](../example_shop_ontology/QUERIES.md) and
[TPC-H](../example_tpch_ontology/QUERIES.md) question→SQL demos.*
