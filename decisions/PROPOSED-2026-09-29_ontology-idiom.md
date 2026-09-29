# PROPOSED 2026-09-29 — the ontology has a procedure, and nothing makes it reachable

**Status: PROPOSED — designed, not enforced.** No gate checks anything this record asks for; the
procedure it names is the DNA checklist (`DNA-2026-09-25_ontology-design-requirements.md`) and the
ontology skills, and no tool today refuses a draft that skipped them.

Operator, after seeing the first draft beside the curated one: *"what is your strategy in creating
ontology? every time you do it it looks different!?!?!?!?!"*

Correct, and the honest answer is that I had none. The procedure exists. Nothing put it in the path
of the work, and nothing refused the drift, so which idiom a draft lands in depends on which file
the author happened to open first.

---

## 1. What actually happened

My procedure was: read the data plane → open the neighbouring bundle for file shape → author from
intuition → run gates until green. Every gate passed. The model was still wrong in ways no gate
looks at.

**The neighbour I copied was the wrong one.** `contoso4` sits next to `contoso5` in the same
directory. The curated reference is `mac-ontology-contoso`, a separate repository — 21 concepts,
28 edges. contoso4 has 20 concepts, 8 edges, mechanical edge names, and an
`ontology_generated.yaml` with **no runs record beside it**: its suite was generated and never
executed. I inherited its habits from a bundle nothing had ever tested.

**The procedure was written down and I did not read it.** `MODELLERS_COOKBOOK.md`, 470 lines: A1
decides concept/edge/rule/physical, A2 decides the class, B1 authors a concept, B5 connects two,
C1–C6 are the antipatterns. B5 even names the file I should have copied —

> *"**Worked diff:** `edges.yaml` — `order__placed_by__customer` and
> `product__belongs_to__category`."*

## 2. The measured divergence

| | curated (`mac-ontology-contoso`) | my draft |
|---|---|---|
| edge id | `order_line__sells__product` | `SalesLine__product_key__to__Product` |
| edges | 28 | **43** |
| concepts | 21 | 15 |
| classes wrong | — | **6 of 15** |

**Edge naming.** `subject__verb__object` against `subject__column__to__object`. Theirs names the
RELATIONSHIP; mine names the JOIN — and the join was already in the data plane. The verb is the
ontology's entire contribution at that point, and I omitted it.

**Edge count.** 43 is a cartesian product: 5 concepts grounded on the sales relation × 6 foreign
key columns. `NetRevenue__store_key__to__Store` and `UnitsSold__store_key__to__Store` are not two
relationships; they are one relationship emitted twice because two concepts share a relation.

**Classes.** A2 is a closed six-term decision procedure and I ran none of it:

| concept | I wrote | A2 says | why |
|---|---|---|---|
| Product, Store, CalendarDay, Location | `entity` | **`reference`** | a keyed dimension facts point at |
| Brand, ProductCategory | `enumeration` | **`grouping`** | a roll-up ABOVE the leaf, not a code list |
| ExchangeRate | `event` | **`measure`** | a number you aggregate, not a state machine |

A2's own words: *"entity is the residual, deliberately narrow ... most 'objects' you'll meet are
actually reference/measure/event in disguise — check those first."* I reached for the residual six
times.

**Missing concepts.** The curated model lifts `color`, `channel`, `age_band`, `store_status`,
`continent`, `product_subcategory` into concepts. I left them as `role: dimension` columns inside
Customer, Product and Store — so a question naming a colour or a continent has nothing to resolve
against.

## 3. Why no gate caught any of it

Every gate here checks SHAPE and none checks IDIOM:

```
validate_schema            the document is well-formed          PASS
check_concepts_not_per_table   the mapping is M:N               PASS
check_concept_columns_exist    every column is real             PASS
check_grain_declaration        the key holds                    PASS
check_datasets_are_grounded    8 of 8 bound                     PASS
ontology suite                 12 of 12 against the warehouse   PASS
```

A structurally perfect model in the wrong idiom goes green. That is the same defect class as
`check_one_register_per_dimension` reporting `DUPLICATED: 0` over 23 copies — a gate that is true
about the wrong thing.

---

## THE PROPOSAL

### P1 — name the procedure and the reference on the kind

`guardrails/ontology/concepts.yaml` declares producers, consumers and checkers. It says nothing
about HOW. Two lines fix the cheapest half of this and would have prevented today entirely:

```yaml
  concept_definition:
    procedure: MODELLERS_COOKBOOK.md#A1-A2-B1
    reference: mac-ontology-contoso        # the worked example — 21 concepts, 28 edges
```

A delivery rule that names its method is reachable from the work; a method in a file at the repo
root is reachable only by someone who already knows to look.

### P2 — convention: an edge id is `subject__verb__object`

Owner `tools/check_edge_definition.py`. The verb is the ontology's contribution; a column name
there means the edge restates the foreign key the data plane already measured, which is the
single-homing law (FW §3.2) broken one layer up.

### P3 — refusal: ONE RELATIONSHIP, ONE EDGE

Two concepts grounded on the same relation, pointing at the same target through the same column,
are one relationship. Emitting it per grounded concept is what turned 28 into 43.

### P4 — refusal: a dimension a question would NAME belongs in a concept

`color`, `continent`, `channel`, `store_status` are things people say. Left as a `role: dimension`
column they resolve against nothing. This is the one refusal here that needs judgement to apply,
so it should REPORT rather than deny — a list of candidate columns, not a block.

### P5 — run A2, and record the answer

Six of fifteen classes were wrong because nothing asked. A concept could carry the A2 branch it
took: `class_basis: "a keyed dimension facts point at"`. Cheap, and it makes a wrong class visible
in review instead of only in a graph six hours later.

---

## What this does NOT propose

- Not a generator. The classes and the verbs are judgements; the point is to make the judgement
  **procedural and reviewable**, not to automate it away.
- Not a new document. The cookbook is good and was already right. The defect is that nothing put
  it in the path of the work.
- Not blaming the gates. They check what they claim to check. The hole is that nothing claimed to
  check idiom, and under UNSPECIFIED IS NOT RULED that is permission, not oversight — which is
  exactly why it needs declaring rather than assuming.
