<!-- STATUS: PROPOSED. Not ratified. This describes `grammar/query_grammar.yaml`, which the runtime
     does NOT read — it is checked against the runtime by tools/check_query_grammar.py and reds on
     disagreement. Every number below was measured on 2026-09-23 against the landed planner and a
     70-question corpus; where something is unhandled it says so in the same voice.
     Companion to FOLD_GRAMMAR.md, which is the other axis and is separately unratified. -->

# THE QUERY GRAMMAR
### How a question becomes SQL, in words a reviewer can check

> **New to this? Read [QUERY_WALKTHROUGH.md](QUERY_WALKTHROUGH.md) first.** It follows seven real
> questions end to end with traced output from the landed planner. This file is the reference
> behind it, and a reference only answers questions you already know to ask.

The fold grammar answers *what may be done to this number*. This one answers a different question:
*what does a question contribute to a SELECT, and what must be declared before it can.* They are
orthogonal and neither contains the other.

---

## 1. THE GRAMMAR IN ONE PAGE

### The three sentences

There are three places a fact about a query can live, and each answers exactly one question.

1. **The INTENT says what was asked.** One operation from nine, a subject, and the terms it names.
   This is the only thing a model produces, and everything after it is deterministic.
2. **The ONTOLOGY says what can be reached.** Which concepts carry a number, which carry a key,
   which edges join them, which registers turn a name into a code. Nobody writes this per question.
3. **The FRAMEWORK says what each operation contributes to the skeleton.** Nine rows, and it ships
   with the runtime. This document is that table written down.

### The one word that is not what it looks like: **operation**

**The operation does not decide the SQL.** This is the finding that shapes the whole grammar, and
it is measured, not asserted.

Of the nine members of the operation vocabulary, **four are tested for by name anywhere in the
planner**, and between them they make three decisions:

| the branch | what it does |
|---|---|
| `_NON_FOLD_OPS = {count, list, define, exists}` | lets a subject that is not a measure past the fold gate |
| `list` | `SELECT DISTINCT` |
| `exists` | an anti-join, and the period gate is skipped because the period belongs to the subquery |

`sum`, `average`, `rank`, `compare` and `ratio` are **never branched on**. They are not code paths.
They emerge:

- `sum` and `average` from what the subject declares — a measure column, or a derivation rule
- `rank` from `ordering` and `limit` being filled; set those and the SQL is the same whatever the
  operation says
- `ratio` from `denominator` being filled
- `compare` from nothing at all — it desugars to a slice plus an `IN` filter, and no code reads the
  word

So an operation-by-shape matrix cannot describe this grammar. The second axis is not the shape of
the question. It is **what the ontology declares**, and the same question over the same data is
three different plans — or a refusal — depending only on that.

### The decision procedure — four steps, with a pencil

For one question:

**Step 1 — Name the subject.** Which concept or rule is the question *about*? If nothing in the
vocabulary matches, the answer is a refusal and no amount of grammar helps.

**Step 2 — Name the operation.** One word from nine. §2 has the give-aways. When you are unsure,
leave it out: the planner infers from the subject's class, which is the legacy path and still works.

**Step 3 — Name the terms.** Which dimensions are preserved (`slices`) and which are pinned
(`filters`). Everything else folds — the fold grammar's sentence applies here unchanged.

**Step 4 — Fill the optional fields, and notice that this is where the shape actually comes from.**
`ordering` + `limit` make it a ranking. `denominator` makes it a ratio. `period` binds a date range.
`join_filters` compares a column to another column rather than to a literal.

Then the planner does seven things in a fixed order — subject resolution, anchor selection, term
resolution, join resolution, predicate placement, aggregate selection, SQL assembly — and you can
follow it with the same pencil. None of the seven reads the question's English words.

---

## 2. THE NINE WORDS

Each is given with what it **requires declared**, what it **contributes**, and whether the runtime
branches on it. The machine-readable form is `grammar/query_grammar.yaml`; this is the same table
in prose, and `tools/check_query_grammar.py` reds if they drift apart.

| word | asks | requires declared | contributes | branched |
|---|---|---|---|---|
| `count` | how many distinct instances | `identity.canonical_key` | `COUNT(DISTINCT key)` | yes |
| `sum` | the total of a number | a measure column or a rule | `SUM(…)` | no |
| `average` | the mean | a measure column or a rule | `AVG(…)` | no |
| `list` | which members exist | a column to list | `SELECT DISTINCT` | yes |
| `rank` | the top or bottom N | something to order by | `ORDER BY … LIMIT` | no |
| `compare` | members side by side | a dimension they share | `GROUP BY` + `IN` | no |
| `ratio` | a share or a per-something | `denominator` | `x / NULLIF(y, 0)` | no |
| `define` | what a declaration says | the meaning plane | a `meta_` relation | yes |
| `exists` | whether an instance is absent | a key and an event carrying it | `NOT IN (SELECT …)` | yes |

**`count` is the one to read twice.** The key does the work, not the word. This was proved in the
worked bundle's own record (`decisions/0005 §2`) by giving each concept a rule of
`COUNT(DISTINCT <the key it already declares>)` and planning it through the real planner unchanged.
The operator's claim — *"to figure out # of customers a system needs to know a key and enumerate it
by the key, it is as easy as that"* — is the grammar's, too.

### Two words carry an open question, and they are marked in the YAML

**`average` does not say which mean.** A plain mean does not *compose*: a breakdown and a grand
total disagree. The fold grammar names `weighted_mean` as the operator that does compose. Which one
`average` selects is a fold-plane question, and this grammar deliberately does not answer it —
stating it here would be a second home for a fact that belongs there.

**`compare` desugars, and it is not obvious that it should.** "Germany versus France" becomes one
grouped result with two rows. A reader asking to *compare* may mean a difference, a ratio, or two
columns side by side, and none of those is what comes out. Measured on the corpus, compare
questions plan — which says the SQL is valid, not that it answers the question.

---

## 3. WHAT DO I ACTUALLY TYPE?

Nothing, for the grammar. It ships with the runtime.

What a **bundle** types is the second axis — and this is the part that decides whether a question
can be answered at all. Each row is a refusal, and each refusal names the declaration that clears
it:

| when the bundle declares | the question | when it does not |
|---|---|---|
| `identity.canonical_key` | is countable | `unsupported_intent` — nothing declares a number it carries |
| a measure column or a rule | is foldable | the same refusal |
| an **edge** between subject and every named term | is plannable | `no_join_path` — the hop is undeclared, *not* absent from the data |
| a **register** or an inline value domain | resolves a name to a code offline | `ontology_gap` — no register, so a name cannot become a code |
| a **period column** on the anchor's relation | can be filtered by date | `ontology_gap` — a period bound to nothing would label a total it did not take |

**The most expensive of these is the edge, and it is the easiest to leave out.** In the worked
bundle, one grouping concept described its own reachability in prose — *"the brand reaches the fact
through the product and only through it"* — and declared no edge. Seven of seventy corpus questions
refused `no_join_path`. One edge declaration, and all seven planned. The prose was right and no
planner could walk it.

---

## 4. THE SITUATIONS, MEASURED

A 70-question corpus, each question given the Intent a perfect interpreter would emit — hand
written, no model involved — and replayed through the real planner. What came back:

| | of 70 | what it means |
|---|---|---|
| planned | 55 | the grammar and the declarations were both sufficient |
| bundle declaration gap | 7 | the planner refused **correctly**; the ontology is thin |
| SME modelling question | 2 | the question asks about a grain no concept models |
| framework gap | 3 | the generated meaning plane gives some concepts no countable identity |
| **grammar gap** | **1** | the Intent could not express it |
| correctly refused | 2 | the value is not in the data, or the question is declared unanswerable |

**Every one of the seventy ENCODED.** Not one question failed to become a valid Intent. That is the
claim this grammar is making and the measurement that supports it: the transformation space spans
the corpus, and the one exception is named in §6.

**The split is the point.** Before this replay existed, a wrong answer could not be attributed to
the interpreter or to the planner, and the same question was fixed repeatedly in the wrong layer.
A hand-written intent that plans proves the planner was never the problem.

---

## 5. WHY THIS IS NOT A TENTH DECLARATION

The worked bundle's governing record is blunt about the failure mode this document could easily be:

> *The estate's defect is not a model that lacks declarations. It is a runtime that does not read
> the declarations it has. Every time this session met one of those, it proposed a NEW declaration
> instead of wiring the existing one.*

So the question has to be asked of this file too. The answer:

**The operation vocabulary already existed. It had two homes, and neither could be reviewed.** One
is a Python `StrEnum`. The other is a prose paragraph inside the interpreter's prompt, teaching the
nine words by their English trigger words. Nothing could compare them, and nothing could tell a
reader which of the nine changes the SQL. `grammar/query_grammar.yaml` is that same closed
vocabulary moved somewhere a person can read it beside what it does.

**And it is born with a reader.** `tools/check_query_grammar.py` checks three ways the grammar and
the runtime can drift — the vocabularies disagreeing, a branch claim being false, the fold-gate set
differing — and reds on any of them. It carries `--self-test`, which seeds one mutant per reject
class, because a gate that cannot go red is the zero-denominator pass wearing a green tick.

It caught a mistake in this file on its first run: `list` and `exists` were recorded with their own
branch and not also as members of the fold gate, which they are.

**What the gate does not check** is that the *contributions* are right — that `list` really emits
`SELECT DISTINCT`. That is the corpus replay's job, and duplicating it here would be a gate
re-deriving its own subject, which cannot fail.

---

## 6. CONSISTENCY — WHAT THIS AGREES WITH, AND WHAT IS NOW WRONG ELSEWHERE

This grammar was written against the landed code, so where an older document disagrees with it, the
older document is the one that has drifted. Recorded rather than silently corrected.

### It agrees with

- **`decisions/0005`** (worked bundle) — the governing record. Its finding *is* this grammar's
  second axis: the declarations are mostly there and the runtime does not read them. §4's 7
  declaration gaps and 3 framework gaps are the same finding, re-measured from a different
  direction.
- **`FOLD_GRAMMAR.md`** — the other axis, and deliberately not restated here. Where the two touch
  (`average`, and what "fold" means) this document defers.
- **The DSQP design** (`ADR-006`'s companion) — its seven deterministic steps are the skeleton in
  §1, unchanged.

### Where existing documents are now wrong

| document | what it says | what is true |
|---|---|---|
| `04-SPEC-semantic-runtime.md` §4 | `Intent.measure: str`, no `operation` | renamed to `subject` with an explicit `operation`; `measure` survives only as a back-compat alias |
| `ADR-006` §7 | "the chat agent remains as the free-form fallback" | that endpoint was retired; it answers 410 |
| `ADR-006` Phase 3 | the system-ontology concepts live in the framework repo | they are generated in memory by the platform's `meaning_plane.py`; that directory does not exist |
| `ADR-006` Phase 5 | a "quality refactor", pass rate unchanged | the corpus's one anti-join question is blocked on it, so it is a feature dependency |
| `ADR-006` §8 criterion 4 | "a new bundle works without planner changes" | not met — the interpreter's prompt carries 23 worked examples naming one bundle's concepts and values |
| `ADR-006`, `ADR-007` | `Status: PROPOSED` | four of ADR-006's five phases are merged. **ADR-005 was listed here in error and is ADOPTED** — it carries the operator's own ruling in its status line |
| `FOLD_GRAMMAR.md` header | describes an unratified decision | true, but that decision is also **superseded in approach** by `0005`, which the header does not say |

**The last row is the one to fix first**, because it is the same defect in documentation form: a
record that is accurate about itself and silent about the record that overtook it.

### The one thing this grammar cannot express

`HAVING` — a predicate on an aggregate rather than on a row. *"Countries where the average order
value exceeds 500"* is the corpus's single un-encodable question. Every filter the Intent can carry
lands in `WHERE`. A second, related gap: `exists` contributes one subquery and the Intent cannot
qualify what is *inside* it, which is why an anti-join with a cross-table filter is unreachable.

Both are recorded in `grammar/query_grammar.yaml#not_expressible`, so the gap is visible rather
than rediscovered.
