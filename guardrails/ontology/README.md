# guardrails/ontology/ — EMPTY, DELIBERATELY.

No topic here yet. Under the one rule this directory tree rests on — **UNSPECIFIED IS NOT RULED** —
that means the ontology plane is currently unruled, and writing to it is allowed.

That is a statement, not an oversight. It is recorded here so a reader can tell "nothing constrains
this yet" from "somebody forgot", which are different facts and only one of them is a bug.

## What will live here

One file per subject, the way `../data/` is split:

| likely topic | what it would rule |
|---|---|
| `concepts.yaml` | one business notion per file, its grounding, its rules, its identity |
| `edges.yaml` | the declared relationships between concepts, and what proves each |
| `vocabulary.yaml` | which terms are closed, and who owns each closed set |

## What is already waiting for it

`../unfiled.yaml` holds two artifacts the data deliveries write that belong to this plane, each
carrying `belongs_to: ontology`:

* `semantic_diagnostics` — `ontology/diagnostics.json`
* `ontology_conformance_suite` — `acceptance/ontology_generated.yaml`

When a topic here claims them, they MOVE. Never a copy: a kind belongs to exactly one declaration,
which is why no precedence rule exists anywhere in this tree and why `bom.conflicts` must stay empty.
