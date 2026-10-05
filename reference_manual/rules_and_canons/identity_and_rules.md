---
title: Rules — how a concept says what must happen
status: >-
  ENFORCED (2026-10-05) — `contract.rules[].kind` is closed by a pattern in mac.schema.json that
  enumerates this vocabulary's six terms, held to it by check_vocabulary_parity. Rule bodies are
  enforced and `binds` is read.
audience: ontology authors
companions: [column_specification.md, rules_and_canons/README.md]
---

# Rules

The vocabulary a concept declares to say **what the engine must do**.

> **The kind is CLOSED as of 2026-10-05, and was not before.** `contract.rules[].kind` was
> `{"type": "string"}` — these six terms appeared in the schema only inside that slot's description,
> as prose, pipe-separated. **Any string validated.** An author, or a model generating a concept,
> could invent `mac.concept.rule.validation` and nothing refused it; a delivered bundle had to carry
> its own shape (`fplclean-rule-kind-closed`) to close what the schema left open. The slot now
> carries `^mac\.concept\.rule\.(aggregation|ambiguity|default|exclusion|guarantee|resolution)$`,
> generated from the terms below, and `check_vocabulary_parity` fails if the two ever disagree.

> **Identity moved, 2026-10-05.** This page also carried `mac.concept.identity` — a six-term
> vocabulary for HOW a concept's identity was established. It is retired: identity is a fact about
> COLUMNS, so it is declared on them (`identity: canonical` / `part` / `reference`, and `counts` for
> what one instance is) and nowhere else. See
> [`mac.concept.column.identity`](../column_specification.md). Operator ruling: *"declare on concept
> level only what belongs to the concept level … identity of the concept is given by column
> combination and it belongs there."*

---

## `mac.concept.rule` — what a behavioural rule governs

<!-- BEGIN GENERATED:vocabulary-terms:concept.rule (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> What a behavioural rule governs — the rule's type.

*`mac.concept.rule` · 6 terms · closed — these are all of them*

#### `mac.concept.rule.resolution`

Identity / matching / scoping of an entity from the question (name, code, key, definition).

#### `mac.concept.rule.aggregation`

Measure math — additivity, period bounds, grain (how a measure may be summed/read).

#### `mac.concept.rule.default`

What to assume when an axis is unspecified but a safe default exists.

#### `mac.concept.rule.ambiguity`

An underspecified REQUIRED dimension — ASK, never guess.

#### `mac.concept.rule.exclusion`

What to filter out / never include (pseudo-entries, unmapped rows, stale vintages).

#### `mac.concept.rule.guarantee`

A fact the consumer INHERITS from the serving view (relied on, not re-derived).
<!-- END GENERATED:vocabulary-terms:concept.rule -->

### The shape of a rule

```yaml
- id: continent.side.customer_only
  kind: mac.concept.rule.resolution
  when:  "a question groups or filters sales by continent"
  then:  read Continent from the customer dimension
  never: deriving a store continent by mapping CountryCode through the customer dimension
  why:   this is the one geography level at which the two roles are not symmetrical
  binds: [Continent, Country]
  confidence: P
```

| field | what it does |
|---|---|
| `when` · `then` | the behaviour, in the bundle's own words |
| `never` | **quoted verbatim into a refusal.** This is the field a reader actually meets. |
| `why` | the reason, so the refusal teaches rather than blocks |
| `binds` | which columns the rule governs — how the planner knows the rule applies |
| `realized_by` | the [canon](../README.md) that makes it deterministic, if one exists |

### What each kind is for

| kind | contoso | the question it answers |
|---|---|---|
| `resolution` | 16 | which instance did they mean? |
| `aggregation` | 8 | may this measure be folded this way? |
| `exclusion` | 6 | what must never be included? |
| `guarantee` | 4 | what may a consumer rely on without re-deriving? |
| `ambiguity` | 4 | what must be ASKED rather than guessed? |
| `default` | 1 | what is safe to assume when unspecified? |

**`ambiguity` and `default` are opposites and the choice between them is the interesting one.** Both
handle an unspecified axis. `default` says *"assume this and disclose it"*; `ambiguity` says
*"ASK — there is no safe assumption."* Getting it wrong either interrogates a person who did not
need asking, or answers a question they did not ask. Contoso chooses `ambiguity` four times and
`default` once, which is the conservative ratio.

### Prose and params

A rule's **prose** (`when`/`then`/`never`/`why`) is usually cross-column and stays at concept level.
Its **params** under `realized_by` are mechanics about one column and belong on that column — see
[the column specification](../column_specification.md). *Prose stays, params descend.*
