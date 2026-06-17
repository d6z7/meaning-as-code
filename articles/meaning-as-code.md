---
title: "Meaning as Code: a version-controlled score for what your data means"
date: 2026-06-17
status: article — narrative companion to FRAMEWORK.md (the normative spec)
audience: data/AI engineers, ontology architects, anyone wiring an LLM to a warehouse
scope: GENERIC — domain-neutral. Examples are the synthetic shop and TPC-H ontologies in this repo.
---

# Meaning as Code

> Write down what your data *means* — once, as plain-text YAML, in layers — so the same artifact can be
> read by an AI agent to answer a question correctly, ingested by any platform to become its ontology,
> and checked by a machine before anyone trusts it. No vendor owns your meaning; a diff shows when it
> changes; a gate fails when it breaks.

This is the story of the idea, why it takes the shape it does, and how it sits next to the standards that
solve neighbouring problems. The normative details live in [FRAMEWORK.md](../FRAMEWORK.md) and
[CONFORMANCE.md](../CONFORMANCE.md); this is the part you read first.

## 1. The problem: meaning has no home

A data warehouse stores values. What those values *mean* — that `l_extendedprice` is gross and revenue is
net of discount; that a line counts as "received" only once a receipt date exists; that "Europe" is a
roll-up reached through four joins, not a column — lives somewhere else. In people's heads. In a BI tool's
semantic layer. In the tribal knowledge of whoever wrote last quarter's query. In a vendor console you
can't diff, can't grep, and can't take with you.

This was tolerable when a human with that context wrote every query. It stops being tolerable the moment
an LLM is asked to. An agent that doesn't *have* the meaning will reconstruct it from priors — guess that
a column called `revenue` is net, that "Europe" is a value somewhere, that summing a stock level over time
is sensible. The query runs. The number is wrong. Nobody can see why, because the meaning it used was
never written down anywhere you could inspect.

## 2. The thesis: one guess, then execution

Here is the line the whole framework is built on:

> Turning a natural-language question into an **intent** — which measure, which slice, which period — is
> probabilistic. Everything after that is **not**. Resolving an entity to its codes, choosing the column,
> picking the join path, assembling the SQL — that is *deterministic execution against an encoded model.*

If you accept that line, the engineering follows. The probabilistic step is irreducible; language is
ambiguous. But you do not want a second, third, and fourth guess stacked behind it. You want the model —
the formula for revenue, the join that defines "Europe", the rule that defines "received" — to be **data
the agent reads**, not knowledge it approximates. Pull every deterministic decision out of the model's
head and into a file. The guess shrinks to exactly one step, and that step is followed by execution you
can audit.

So the job is to *write the model down* — completely enough that the deterministic half really is
deterministic — in a form that is at once legible to a human, readable by an agent, ingestible by a
platform, and checkable by a machine. That form is the subject of this article.

## 3. Why "as code"

Plain-text YAML in a git repo, governed by a **closed schema**. Three consequences, each load-bearing:

- **A human can diff it.** Meaning becomes a reviewable pull request. When the definition of revenue
  changes, that change has an author, a date, a reviewer, and a line in the history — like any other code.
- **A platform can ingest it.** The model is vendor-neutral by construction. It projects onto a graph DB,
  a semantic layer, a SQL view — *your meaning is not trapped in the tool that happens to run it today.*
- **An LLM can author it safely — and cannot hallucinate it.** This is the subtle one. The core
  vocabulary is **closed**: a file may use only the keys the schema defines, plus declared `x-` extensions.
  An LLM writing a concept cannot invent a plausible-but-wrong key, because the schema rejects it. The same
  closure that makes the model legible makes it *safely machine-authorable.*

The metaphor that fits: a **musical score**. A symphony is not "stored" in a conductor's memory; it is
written, note by note, in a notation any orchestra can read and any critic can mark up. Meaning-as-Code is
that score for data — every note of meaning written down, in a notation that doesn't belong to one
performer.

## 4. The shape of the model

Meaning is written in **four layers**, each a different *kind* of fact, so each can be checked and
projected on its own terms:

| Layer | What it holds | Example |
|---|---|---|
| **Concept** | what a thing *means* — its class, semantics, the rules for using it | `Revenue` is a `measure`, a `Flow`, net of discount |
| **Physical** | where the data lives — tables, columns, keys; **single source of truth for columns** | `lineitem` has `l_extendedprice`, `l_discount`, … |
| **Edges** | the relations *between* concepts — joins, as data | `lineitem → orders` on `l_orderkey = o_orderkey` |
| **Rules** | derivations and directives — the formula, the guarantee | `net_revenue = SUM(l_extendedprice × (1 − l_discount))` |

Every concept declares one of **six closed classes** — `entity`, `event`, `measure`, `enumeration`,
`reference`, `grouping`. Six, not sixty: the point of a closed set is that an author (human or model)
chooses from a short menu, and a reader always knows what kind of thing they are looking at.

One discipline ties it together: **single-homing**. A fact is written in exactly one place. Columns live
in the Physical layer — a concept does not restate them, an edge does not redefine them. This sounds
fussy until it earns its keep in §5, where it becomes the difference between a binding check that means
something and one that doesn't.

## 5. The teeth: three gates, and rules bound to fields

A model nobody checks rots. Meaning-as-Code reaches its trust bar (conformance level **L1**) through
**three data-free gates**, run in sequence:

1. **Structural** — every file validates against `mac.schema.json`: closed keys, required keys, the closed
   class/type vocabularies, naming. *Is it a well-formed MAC file?*
2. **Referential** — every cross-file reference resolves: no concept points at a missing table, no edge at
   a missing concept, every `mac.*` term exists. *Is the model internally whole?*
3. **Constraint (shapes)** — the invariants the schema *structurally cannot* express, declared as **data**
   and run by one generic engine. *Does it obey the rules a tree-validator can't see?*

That third gate is where the interesting work is. A JSON Schema validates one file's tree; it cannot say
"the value at path A in file X must be a column listed in file Y." Those **relational, cross-file**
invariants are exactly the ones that matter, and they are written as shapes — `target`, `path`,
`constraint`, `severity` — SHACL-shaped, but YAML-native over MAC files, no RDF (see [§7](#7-where-this-sits)).

The headline shape is **field-anchoring**. A concept's behavioural rules are typed (`kind`, `when`,
`then`, `why`) and each is **bound to the field(s) it governs** via `binds:`. The built-in
`rule-binds-grounded` shape enforces, cross-file, that every bound field is a real column of the table the
concept grounds to:

```yaml
# example_tpch_ontology — LineItem
contract:
  rules:
    - id: lineitem.revenue.net_of_discount
      kind: mac.rule_kind.aggregation
      then: "use l_extendedprice * (1 - l_discount); a NULL discount counts as 0"
      binds: [l_extendedprice, l_discount]     # ← must be columns of the grounded `lineitem` table
```

This is why single-homing matters. Because columns live once, in the Physical layer, the shape resolves
`binds` against *the actual table*, not against a list the concept conveniently restated about itself. A
rule **cannot claim to govern a field the concept does not ground** — and if it tries, the gate says so:

```
[ERROR] lineitem.yaml :: rule-binds-grounded: rule binds "l_discont" — not a column of the grounded table
```

A real anecdote from building this: promoting `rule-binds-grounded` to the canonical, single-homed check
immediately surfaced **two genuine gaps** in a mature application's model — rules bound to columns the
deployed serving view did not actually expose. A looser, per-application check (resolving against the
concept's *own* restated columns) had been passing them silently for months. One strict definition,
applied everywhere, found what the convenient definitions hid. That is the argument for the gate in a
sentence.

## 6. The payoff: the model writes the SQL

If the deterministic half is really deterministic, you should be able to *watch* it happen. You can. Each
worked example ships a `QUERIES.md` that turns plain questions into SQL **by reading the ontology** —
nothing recalled from memory:

| SQL clause | comes from |
|---|---|
| `FROM` / column names | a concept's grounding → the Physical-layer table doc |
| `JOIN … ON …` | an **edge**'s `join_rule` |
| the measure expression in `SELECT` | a **rule**'s `template` |
| which columns a rule may touch | the rule's `binds` |

"Net revenue by region" ([TPC-H](../example_tpch_ontology/QUERIES.md)) is not answered from priors: the
`SELECT` is the `net_revenue` rule's formula, the four `JOIN`s are four edges' `join_rule`s verbatim, the
label is a column with role `value`. The composite join through an associative entity, the lifecycle rule
that defines "received" — each clause traces to a cited file.

And the model knows the **boundary of what it can answer**. Ask the [shop](../example_shop_ontology/QUERIES.md)
for "net revenue by product category" and a correct generator *refuses*: Revenue grounds on orders;
Category is reachable only through products; **no edge connects them.** Because the joins are data, the gap
is reported as a missing edge to add — not papered over with a fabricated `orders.sku`. A model that can
say "I can't get there from here" is worth more than one that always answers.

## 7. Where this sits

Meaning-as-Code is not the first attempt to formalize meaning, and it does not pretend to replace the
standards that own neighbouring problems. Its stance is **"formalize the closed, govern the open"**: a
strict, closed core for the constructs that recur everywhere, and a disciplined `x-` extension namespace
for what a domain adds — never a free-for-all, never ossified.

- **SHACL** (W3C) — constraints as shapes over a graph, as data. MAC's constraint gate is deliberately
  SHACL-*shaped* (target · path · constraint · severity) but runs over plain YAML files, so a team gets
  the "constraints are data" win without adopting RDF. *Borrowed: shapes. Dropped: the triple store.*
- **SBVR** (OMG) — business vocabulary and rules with modality and verbalization. MAC's typed
  `contract.rules` are a lighter, executable-adjacent cousin: fewer linguistics, but bound to real columns
  and run by a gate.
- **SKOS** (W3C) — concept schemes and closed vocabularies. MAC's `mac.rule_kind`, `mac.MeasureType`, and
  enumerations are exactly this discipline, kept small and closed.
- **OSI** (Open Semantic Interchange, 2025) — an interchange format for datasets, measures, dimensions,
  relationships. It overlaps MAC's measure/grounding layer and is a natural **export target**: MAC can
  speak OSI for the part OSI covers, while keeping the layers (edges-as-data, typed rules-bound-to-fields,
  shapes) that OSI does not reach.

What MAC adds that none of these gives you in one artifact: the **four layers as a single, version-
controlled, vendor-neutral file set**, a **closed core an LLM can author without hallucinating**, and
**rules bound to the fields they govern, enforced cross-file.** It is less expressive than OWL, less
linguistic than SBVR, less universal than SHACL — and more *operational* than all three for the specific
job of letting an agent generate correct SQL from meaning alone.

## 8. What it is not

Honesty, because the framework insists on it. The gates prove **L1** — well-formed and conformant. They do
**not** prove correctness: a green model can still ground a column that doesn't exist in the warehouse, or
label a measure wrong. That is what **L2** (the query runs and the number is sane) and **L3** (an expert
ratifies the meaning) are for, and they remain mandatory and human. A clean schema is the *start* of
trust, not the end. Meaning-as-Code makes the deterministic half inspectable and enforceable; it does not
abolish the need to check the model against the world.

## 9. The point

Meaning is an asset. Today most organizations treat it like folklore — unwritten, unversioned,
unenforced, and quietly re-guessed by every new tool and every new model. Write it as code, in layers,
behind gates, and it becomes what it should have been all along: diffable, reviewable, projectable,
checkable, and *yours.* The agent stops guessing what your data means, because someone wrote down the
score.

---

*Worked examples in this repo: [example_shop_ontology](../example_shop_ontology/) (a small neutral
domain) and [example_tpch_ontology](../example_tpch_ontology/) (the TPC-H benchmark — a richer shape:
hierarchy, associative entity, composite-key fact, derived measure). Each has a `validate.sh` that runs
all three gates and a `QUERIES.md` that generates SQL from the model.*
