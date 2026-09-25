---
title: Identity and rules — how a concept says what it IS and what must happen
status: both vocabularies are read; rule bodies are enforced, `binds` is read
audience: ontology authors
companions: [column_specification.md, canon_library.md]
---

# Identity and rules

Two vocabularies a concept declares once: **what makes one instance one instance**, and **what the
engine must do**.

---

## `mac.identity_kind` — how identity is established

Per **concept**, not per column. (For which *column* plays which part, see
[`mac.identity_role`](column_specification.md).)

<!-- BEGIN GENERATED:vocabulary-terms:identity_kind (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> How a concept's canonical identity is established (declared once per concept).

*`mac.identity_kind` · 7 terms · closed — these are all of them*

#### `mac.identity_kind.iso`

A universal external standard code (e.g. an ISO country code). Identity = the standard code;
local names/labels are aliases.

#### `mac.identity_kind.code`

A closed internal code set (e.g. a fuel or segment code). Identity = the code; surface spellings
are aliases.

#### `mac.identity_kind.namespace_code`

A code that only means something within a scope — identity = (namespace, code); the bare code
collides across scopes. Guarded by mac.canon.composite_key_guard.

#### `mac.identity_kind.fk_name`

An opaque but stable key carrying a resolved human name (e.g. a model code + name). Identity =
the key; the name is a joined attribute, not the identity.

#### `mac.identity_kind.composite`

Identity is a TUPLE of columns (a fact grain, or a parent+member pair). Keyless-by-design: no
single-column key.

#### `mac.identity_kind.resolved_axis`

An axis the serving view PINS or collapses (e.g. reporting role, firmness). Keyless-by-design:
not exposed as a filterable key on the default view (grounding columns: []).

#### `mac.identity_kind.sme_pending`

Identity not yet known — carried as '__sme__', never invented; graduates to another kind once an
SME rules.
<!-- END GENERATED:vocabulary-terms:identity_kind -->

### Choosing

```
1. Is identity a TUPLE of columns?                          → composite
2. Is it pinned or collapsed by the serving view?           → resolved_axis
3. Is it an external standard code?                         → iso
4. Does the bare code collide across scopes?                → namespace_code
5. Is it a stable key carrying a resolved human name?       → fk_name
6. Is it a closed internal code set?                        → code
7. Not yet known?                                           → sme_pending, never invented
```

**Steps 1 and 2 are the keyless-by-design cases**, and they come first deliberately. A concept that
legitimately has no single-column key must say so rather than nominate a column that does not
identify — which is the failure `composite` and `resolved_axis` exist to prevent.

**Step 4 is `scoped_by` in its concept-level form.** `namespace_code` is the same fact the
[`context_dependent_meaning`](patterns/context_dependent_meaning.md) pattern describes and
[`composite_key_guard`](canon/composite_key_guard.md) enforces — a `State` code that means Corse in
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

## `mac.rule_kind` — what a behavioural rule governs

<!-- BEGIN GENERATED:vocabulary-terms:rule_kind (tools/gen_vocabulary_terms.py — do not edit inside this block) -->

> What a behavioural rule governs — the rule's type.

*`mac.rule_kind` · 6 terms · closed — these are all of them*

#### `mac.rule_kind.resolution`

Identity / matching / scoping of an entity from the question (name, code, key, definition).

#### `mac.rule_kind.aggregation`

Measure math — additivity, period bounds, grain (how a measure may be summed/read).

#### `mac.rule_kind.default`

What to assume when an axis is unspecified but a safe default exists.

#### `mac.rule_kind.ambiguity`

An underspecified REQUIRED dimension — ASK, never guess.

#### `mac.rule_kind.exclusion`

What to filter out / never include (pseudo-entries, unmapped rows, stale vintages).

#### `mac.rule_kind.guarantee`

A fact the consumer INHERITS from the serving view (relied on, not re-derived).
<!-- END GENERATED:vocabulary-terms:rule_kind -->

### The shape of a rule

```yaml
- id: continent.side.customer_only
  kind: mac.rule_kind.resolution
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
| `realized_by` | the [canon](canon_library.md) that makes it deterministic, if one exists |

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
[the column specification](column_specification.md). *Prose stays, params descend.*
