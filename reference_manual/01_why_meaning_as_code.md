---
title: "Ch.01 — Why model meaning as code"
part_of: reference_manual
status: written
scope: GENERIC — domain-neutral. Examples from example_shop_ontology/.
---

# Ch.01 — Why model meaning as code

*Read this to decide whether the idea is worth your time. It is the honest case for the framework,
measured against the four things you already use.*

## 1. The problem nobody owns

In any organisation past a certain size, the *meaning* of data has no home. "Revenue is net of refunds,"
"the order book excludes cancelled orders," "this stock figure must never be summed across months" — these
facts live in people's heads, in one BI tool's report definitions, and in the `CASE` statements of
transformation SQL. They are real, load-bearing, and **un-addressable**: you cannot link to them, diff
them, test them, or hand them to a machine.

Two modern pressures turn that latent cost into an acute one:

1. **AI agents now write the queries.** Ask an LLM "what was revenue in Q3?" and it will produce SQL. It
   does not know revenue is net of refunds, that one table double-counts across a reporting dimension, or
   that a stock measure is non-additive over time. It guesses — and it guesses **plausibly and wrongly**,
   returning a clean number with no signal that the number is wrong. The cost of un-homed meaning used to
   be a slow analyst; now it is a confident, automated mistake.
2. **Every place you could put the meaning locks it in.** Encode it in a BI tool's semantic layer and only
   that tool can read it. Encode it in a platform ontology and you have coupled your meaning to that
   vendor's primitives and licence. The meaning should outlive the tool that happens to query it this year.

## 2. The four things you use today — and why each falls short for *this* job

This framework is not better at everything. It is better at one specific job: **being the single,
authoritative, tool-neutral home for meaning, readable by humans, machines, and AI agents.** Measured
against *that* job, here is the honest standing of the alternatives.

### 2.1 Transformation code (SQL / dbt / Spark)
The business rules really do live here — buried inside `CASE` expressions, `WHERE` filters, and join
conditions. But code states **how to compute**, never **what the thing means**. The rule "revenue is net of
refunds" is *implied* by a subtraction in one model and nowhere stated; the next model re-implements it
slightly differently. It is procedural, not declarative; duplicated, not single-homed; unreadable to a
non-engineer and only accidentally readable to an agent. *Meaning is a side-effect of the code, not a
first-class artifact.*

### 2.2 BI semantic layers / dimensional models (LookML, cubes, the warehouse star schema)
This is the closest prior art for *analytics* meaning, and dimensional modeling (Kimball) is a genuine,
hard-won pattern language — facts, dimensions, conformed keys, slowly-changing dimensions. Two limits for
this job: it is **tool-bound** (LookML is Looker's; a cube is the cube engine's — the meaning does not
travel), and it models *measures and dimensions*, not the full range of meaning (lifecycles, controlled
vocabularies with explicit closure, cross-source identity, the reasoning facts an agent needs). It is a
semantic layer **for a BI tool**, not a semantic layer **for everything that will consume the data**.

### 2.3 RDF / OWL / triple stores (the W3C standard)
The most expressive and the only *standardised* option — and the right target when a triple store is the
destination. But for *authoring and maintaining* meaning it is heavy: verbose to write and read, its
tooling assumes a triple store, and its headline feature — formal inference (OWL entailment) — is mostly
**unused** by the job an LLM agent actually does, which is *shaping a correct query*, not deriving new
triples. It is also not what a model reads and writes fluently. We keep a **projection path to RDF** (so a
triple store can still be a target) without paying RDF's authoring cost up front.

### 2.4 Platform ontologies (Palantir Foundry and the like)
Technically often the best single-vendor fit: a runtime, a UI, an object model, governance. The cost is
structural — your meaning becomes expressed in **that platform's primitives**, under **that platform's
licence**, and the next migration is a rewrite. The platform decision then **gates** the semantics work and
gets **locked in by** it. (For many organisations the platform is also ruled out for reasons that have
nothing to do with its merits.) You want to capture meaning *now*, vendor-neutral, and *project it into*
whichever platform is chosen later — so the two decisions are decoupled.

## 3. The bet

Capture meaning as **plain-text YAML, version-controlled in Git**, structured by a small **closed** schema.
One artifact, **two consumers**:

- an **AI agent** reads the relevant concepts + grounding + rules into context and composes a correct query;
- a **target platform** ingests the same YAML and casts it into its own primitives (RDF classes, graph
  node/edge types, semantic-layer metrics, a platform object model).

Because the artifact is **declarative** — it states what things *mean*, not how one engine executes them —
each consumer maps it to its own world. **Write once; project anywhere.** Five properties make it work, and
each is a direct answer to a failing in §2:

| Property | Answers the failing of… | What it buys |
| --- | --- | --- |
| **Declarative** (states meaning, not computation) | transformation code (§2.1) | meaning is the artifact, not a side-effect |
| **Tool-neutral, projectable to all three target families** | BI layers (§2.2), platforms (§2.4) | the meaning outlives the tool; no lock-in |
| **Closed, small vocabulary** (4 layers, 6 classes) | RDF's open zoo (§2.3) | one word tells a reader — or a projector — the shape of a thing |
| **Single-homed** (every fact in exactly one place) | code & BI duplication (§2.1–2.2) | diffs don't lie; drift is checkable; review is legible |
| **Execution-validated** (run the implied query; let data correct the model) | all of them | structure ≠ correctness; a fact earns trust by surviving the data |

And — decisively for the agent consumer — the framework makes the classic **footguns explicit** that the
alternatives leave to tribal knowledge: a measure's per-axis **additivity** (a stock is non-additive over
time), a value set's **closure** (closed / open / unknown), what an **absent row** means
(`null_semantics`). These are exactly the facts that make an LLM guess plausibly-wrong, and here they are
*written down, single-homed, and enforced*.

## 4. What it is honestly NOT

(Credibility depends on this section.) It is **not a runtime** — it describes, it does not execute; you
still need a warehouse, graph, or semantic layer. It is **not a reasoner** — there is no built-in
inference; reasoning is supplied by the consumer (an agent, or the target platform). It is
**discipline-dependent** — the legibility and projectability exist only while the contracts (single-homing,
the naming contract, the closed vocabulary) are actually enforced; without the validator it rots into the
mess it replaced. And it is **validated only as far as it has been executed** — a green validator means
*well-formed*, not *correct*. It earns its keep when meaning must **outlive a tool, be shared across
sources, and serve both humans and AI agents**. If a single team owns a single tool forever, that tool's
native semantic layer may be enough.

---

*This chapter consolidates and re-frames FRAMEWORK §1–§2, §9 as a comparative argument. Pending the open
architectural decision (see [README](README.md)), it is either the canonical home for that argument or a
projection of it.*
