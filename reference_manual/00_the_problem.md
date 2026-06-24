---
title: "Ch.00 — The problem, and the shape of the answer"
part_of: reference_manual
status: written
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/ (a synthetic online shop).
---

# Ch.00 — The problem, and the shape of the answer

*Read this first. It does two things: it makes the problem concrete (so the rest of the manual reads as an
answer to a question you have felt, not an answer to nothing), and it defines the **anatomy of a pattern** —
the units this manual is built from and how they relate, so that in every later assertion you can see
exactly what is the question and what is the answer.*

## 0.1 A demonstration

You connected a capable LLM to the shop's warehouse and asked it one question:

> *"What was revenue last quarter?"*

It wrote valid SQL, ran it in 200 ms, and returned **€4.2M**. Everyone nodded.

The number was wrong — three independent ways at once:

- it summed `gross_amount`, but revenue is **net of refunds** (that rule lives inside one transformation
  model's `CASE` expression, which the agent never saw);
- it summed the `order_items` table, which is **one row per shipment line**, so a split shipment
  double-counted its order's revenue;
- it included orders still in `CANCELLED` status, because nothing told it the order book excludes them.

None of it was visible. The query looked right, the number looked right, and there was **no signal** that it
wasn't. A junior analyst makes the same three mistakes — except a senior one nearby catches it ("you know
revenue is net of refunds, right?"). The agent has no senior analyst. It has the **data**, the **schema**,
and its **priors** — and *none of those three contain the facts it needed.*

That is the problem. Not that the agent is unintelligent — it is that the meaning it needed **was never
written down anywhere it could read it.** "Revenue is net of refunds," "this table is one-row-per-shipment,"
"the order book excludes cancellations" — these facts are real, load-bearing, and **homeless**. They live in
people's heads, in one tool's configuration, in a buried `CASE` statement. You cannot link to them, test
them, diff them, or hand them to a machine.

For thirty years the workaround was tribal knowledge and a person who "just knows." That does not scale to
machines asking thousands of questions a day, and it never scaled to the new analyst on their first week.
The fix is not a smarter agent; it is **writing the meaning down — once — in a place the agent, the next
analyst, and the next tool can all read.** The rest of this manual is how.

## 0.2 What we want to change

| Today | What we want to change it to |
| --- | --- |
| meaning lives in heads, `CASE` statements, one tool's config | one versioned, readable artifact |
| the agent **guesses** the missing facts, plausibly and wrongly | the agent **reads** them and cannot silently guess |
| "revenue is net of refunds" is tribal knowledge | a stated, single-homed, **testable** fact |
| each tool re-encodes the same rule slightly differently | the rule is written **once** and projected to every tool |
| a wrong answer looks exactly like a right one | a missing fact is **visible**; abstention is possible |

## 0.3 The anatomy of a pattern

Everything in Chapter 03 is a **pattern**, and this section defines exactly what a pattern *is*, so that you
never again read an answer without seeing its question.

### The core claim

> **Every pattern is a Question → Answer pair, and the question is always a fact the data structurally
> cannot contain.**

In the demonstration above you could *see* that `order_items` has one row per shipment line. You could
**not** see whether summing its revenue across those lines is correct — that is a fact about *what the rows
mean*, not about the rows. **That absent fact is the question.** A pattern's answer is the modelling move
that *supplies* the fact, built from the closed vocabulary in Chapter 02. Every assertion this manual makes
is one of two moves: **naming a gap**, or **filling it**.

### The units (the particles)

A pattern has two sides — a question side and an answer side — and each is built from its own elementary
particle.

| Intuition | Unit | What it is | In *semi-additive balance* |
| --- | --- | --- | --- |
| elementary particle | **Observation** | a directly-readable fact about the raw data | "`units_on_hand` is a number"; "one row per date × product × warehouse" |
| *the missing bond* | **Latent fact — the QUESTION** | the load-bearing fact the observations do **not** determine | *"is this additive over time?"* |
| atom | **Constellation** | a recurring, named bundle of observations that signals a specific latent fact | "a level, measured repeatedly over time and across entities" |
| elementary particle *(other charge)* | **Construct** | one primitive from the Chapter-02 vocabulary | `class: measure` · `MeasureType` · an additivity declaration |
| molecule | **Response — the ANSWER** | the bonded assembly of constructs that *supplies* the latent fact | measure + `Stock` + (time → point_in_time, entity → additive) |
| named compound | **Pattern** | one constellation ↔ its latent question ↔ its canonical response | "semi-additive balance" |
| bulk material | **Model / Ontology** | many instantiated patterns applied over a real domain | the whole shop ontology |

### The bonds (what stands in what relationship to what)

The grammar is just six relationships:

- a **constellation** *is composed of* **observations**;
- a **constellation** *leaves open* a **latent fact** — this is the **question** being raised;
- a **response** *supplies* that latent fact — this is the **answer**;
- a **response** *is composed of* **constructs**;
- a **pattern** *bonds* one constellation to one response;
- a **model** *is composed of* instantiated patterns.

```
   observations ──compose──▶ CONSTELLATION ──leaves open──▶ LATENT FACT  (the QUESTION)
                                   │                              │
                                   │         a PATTERN            │ supplied by
                                   │     bonds the two sides      ▼
   constructs (Ch.02) ──compose──▶ RESPONSE ───────────────────answers it
```

### Why this is also the manual's architecture

The two elementary particles are not symmetric by accident — they are the two halves of the book:

- **Chapter 02 is the periodic table of the *answer* particles** — the closed, finite set of constructs
  every response is built from.
- **Chapter 03's constellations are the periodic table of the *question* particles** — the recurring data
  shapes that raise latent-fact gaps.
- **A pattern is a bond between the two tables**: a question the world keeps posing, tied to the canonical
  answer the vocabulary allows. Chapter 03 is therefore not a pile of recipes — it is the **bonding rules**
  between questions and answers.

This is why every pattern entry in Chapter 03 is laid out the same way (the template is in §3.1):

1. **Initial state — what you're handed** — the observations, and *why the raw state is dangerous*.
2. **The question, and the answer** — the latent fact named as a question, and the fact we supply in reply.
3. **The pattern** — the answer in full (prior art, the response in Chapter-02 constructs, why it is better).
4. **The footgun, concretely** — the guess an agent makes against the raw state, beside the grounded result.

Read top to bottom, each pattern is: *here is what you see → here is what you can't see but must → here is
how we supply it → here is the cost of not.*
