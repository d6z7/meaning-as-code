---
title: Identity and rules — how a concept says what it IS and what must happen
status: both vocabularies are read; rule bodies are enforced, `binds` is read
audience: ontology authors
companions: [column_specification.md, rules_and_canons/README.md]
---

# Identity and rules

Two vocabularies a concept declares once: **what makes one instance one instance**, and **what the
engine must do**.

---

## `mac.concept.identity` — how identity is established

Per **concept**, not per column. (For which *column* plays which part, see
[`mac.concept.column.identity`](../column_specification.md).)

<!-- BEGIN GENERATED:vocabulary-terms:concept.identity (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> How a concept's canonical identity is established (declared once per concept).

*`mac.concept.identity` · 6 terms · closed — these are all of them*

#### `mac.concept.identity.iso`

A universal external standard code (e.g. an ISO country code). Identity = the standard code;
local names/labels are aliases.

#### `mac.concept.identity.code`

A closed internal code set (e.g. a fuel or segment code). Identity = the code; surface spellings
are aliases.

#### `mac.concept.identity.namespace_code`

A code that only means something within a scope — identity = (namespace, code); the bare code
collides across scopes. Guarded by mac.canon.composite_key_guard.

#### `mac.concept.identity.fk_name`

An opaque but stable key carrying a resolved human name (e.g. a model code + name). Identity =
the key; the name is a joined attribute, not the identity.

#### `mac.concept.identity.composite`

Identity is a TUPLE of columns (a fact grain, or a parent+member pair). Keyless-by-design: no
single-column key.

#### `mac.concept.identity.sme_pending`

Identity not yet known — carried as '__sme__', never invented; graduates to another kind once an
SME rules.
<!-- END GENERATED:vocabulary-terms:concept.identity -->

### Choosing

```
1. Is identity a TUPLE of columns?                          → composite
2. Is it an external standard code?                         → iso
3. Does the bare code collide across scopes?                → namespace_code
4. Is it a stable key carrying a resolved human name?       → fk_name
5. Is it a closed internal code set?                        → code
6. Not yet known?                                           → sme_pending, never invented
```

**Steps 1 and 6 are the keyless-by-design cases**, and step 1 comes first deliberately. A concept that
legitimately has no single-column key must say so rather than nominate a column that does not
identify — which is the failure `composite` exists to prevent. (A third keyless kind, `resolved_axis` —
"the serving view pins or collapses this axis" — was retired 2026-09-28 by operator ruling: 0 of 62
concepts across four bundles used it. The schema enum still lists it; that is an open parity gap.)

**Step 3 is `scoped_by` in its concept-level form.** `namespace_code` is the same fact the
[`context_dependent_meaning`](../patterns/context_dependent_meaning.md) pattern describes and
[`composite_key_guard`](context_dependent_meaning/composite_key_guard.md) enforces — a `State` code that means Corse in
France and Colorado in the United States.

### Worked — contoso

| concept | kind | why |
|---|---|---|
| `Country` | `iso` | two-letter codes, ISO 3166-1 alpha-2 in shape |
| `Customer` | `fk_name` | an opaque `CustomerKey` with the geography resolved onto the row |
| `StoreStatus` | `fk_name` | the stored value **is** the code — 'Closed', 'Restructured' |
| `OrderLine` | `composite` | `(OrderKey, RowNumber)`; neither identifies alone |

Fourteen of contoso's twenty-one concepts are `fk_name`, four `code`, two `iso`, one `composite`.

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
