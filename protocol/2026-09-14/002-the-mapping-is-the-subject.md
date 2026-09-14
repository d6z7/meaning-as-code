---
when: 2026-09-14T11:15:00
what: the operator dissolved my claim that "understanding the functionality" blocks generation — the subject is the MAPPING, its justification is already largely structured, and the boundary of machine knowledge is a countable number
topics: [method, denominators, gates, harness]
kind: build
track: core
repo: meaning-as-code
commits: []
---

## WHAT FORCED IT

I had reported that the first of the three questions — *understand the functionality that is
implemented* — FAILS, citing rule coverage ceilinged at 8 of 31 because 23 rules state their
directive in prose. The operator refused the conclusion and reframed the subject:

> *"what we do in a nutshell is replacing an application from a multi-tier system where data lays in
> a db. So instead of having an application manage all communication between user and db, we expect
> an ontology-defined set of rules to take over this responsibility. ... first you derive business
> objects encoded in the data; then you establish mapping/grounding between db objects and business
> objects. OUR TEST MUST ADDRESS QUALITY OF THIS MAPPING. This includes and probes the logic. We
> might argue about the amount, but most if not 95% of all the value is in the mapping/grounding
> between ontology and data + some rules."*

**I had measured a ceiling on the wrong population and reported it as a limit on the whole.** Prose
rules are the minority half; the mapping is the thing every answer passes through.

## EVIDENCE — the justification is ALREADY in the declaration

One reference concept, read in full. **Structured today:** `concept.class: reference`,
`identity: {kind: code, canonical_key: <KEY>}`, and two `grounding.sources[]` each with
`{relation, key, columns[]}` — where the two keys are spelled DIFFERENTLY, prefixed on the dimension
and bare on the fact. **Prose today, but stating testable claims:**

> *grain:* "one row per (`<OBJECT>` × `<SCOPE>`) — the key repeats per `<SCOPE>`. On the fact, it is a
> DISCRIMINATOR column on each row."
> *note:* "The dimension names it prefixed; the fact names the SAME value unprefixed. Both are the
> stored identity — read directly, NEVER re-derived."

**Every clause is a testable claim, and four of the five are machine-readable already:**

    identity.kind=code + canonical_key   -> unique at grain · non-null · cardinality stable vs profile
    two sources, keys named differently  -> the two value sets are EQUAL IN BOTH DIRECTIONS
    grain "repeats per <SCOPE>"          -> one row per (<OBJECT> × <SCOPE>); a fan-out is a failure
    "discriminator on each fact row"     -> value present on the fact, subset non-empty
    "never re-derived"                   -> PROSE ONLY: nothing parses it from a composite code

A ratio-measure concept confirms the taxonomy is not wishful: `identity.kind: composite`,
`class: measure`, and a definition stating *"a derived RATIO — the sum or average of stored values
does NOT equal the value recomputed from inputs."* **A non-additivity claim with a direct mechanical
test, authored as prose.**

## THE GENERALISATION

> **A MAPPING IS A CLAIM THAT THIS PHYSICAL THING MEANS THAT BUSINESS THING, AND EVERY SUCH CLAIM
> RESTS ON EVIDENCE THAT IS ITSELF MACHINE-READABLE. The test is always the same shape: DOES THE
> EVIDENCE STILL SUPPORT THE CLAIM?**

The justification kinds are a small closed set, readable from fields that already exist:

    IDENTITY            this column IS the object       unique at grain · non-null · stable cardinality
    COMPOSITE IDENTITY  the TUPLE is the object         tuple unique · no proper subset is
    CO-REFERENCE        two sources, one value          value sets equal BOTH ways
    DISCRIMINATOR       this value selects the subset   present · subset non-empty
    ATTRIBUTE           a property of the object        exists · type · domain
    GRAIN               one row per declared tuple      no fan-out
    MEASURE BEHAVIOUR   the declared MeasureType        additive iff declared additive

## THE BOUNDARY OF KNOWLEDGE, AND IT IS A NUMBER

| | who |
|---|---|
| compute the evidence — cardinality, nulls, uniqueness, overlap, fan-out, additivity | **machine, always** |
| propose the justification class from declared fields | **machine, usually** — `identity.kind` and `class` already say it |
| rule that a key MEANS this business object and not a neighbouring one | **only the operator** |
| rule whether a measure SHOULD be additive when the data says it is not | **the operator** — the machine can only report the disagreement |

So the coordination the operator asked for — *"explore the boundary of knowledge on your own and
coordinate this with an operator"* — has a concrete shape. **At the moment a mapping is created, emit
a JUSTIFICATION RECORD in three parts: EVIDENCE (machine), CLASS (machine proposes), MEANING
(operator ratifies).** The test generates from evidence + class. The ratification is a one-time act
per mapping, and — the part that makes it work — **it is countable**: *"N sources, M classified, K
awaiting a ruling"* is a number, not a feeling. The machine goes as far as the evidence carries it
and then **stops at a named question** instead of guessing or falling silent.

## WHAT THIS CORRECTS

**Question (1) does not fail for mappings.** It fails for prose rules only. The grounding plane is 22
concepts / 30 sources in the bundle measured, every answer passes through it, and its justification
is already largely structured. PROSE RULES ARE DEFERRED by operator ruling — *"we can defer dealing
with prose rules for later"* — which makes the 8-of-31 ceiling a parked problem rather than a
blocking one.

## WHAT IT DOES NOT PROVE

That generated mapping tests are USEFUL. Feasible and useful are different claims and the operator
said so: *"lets see how far this is feasible — AND HELPFUL."* A generator that emits hundreds of true,
unfalsifiable, duplicate statements would satisfy the first and fail the second, and this estate
already carries 59 vacuous assertions over 29 properties plus 65 duplicate generated assertions in
one suite — so that failure mode is demonstrated here, not hypothetical. A spike is running to
answer it; its honest result may be no.

Nor does it settle the 95% claim. That is the operator's estimate of where value sits, and it is
being tested rather than assumed.

## A PROCESS NOTE, BECAUSE IT PAID OFF IMMEDIATELY

Protocol entry 001 recorded that `check_mac_public` reads `git ls-files` and therefore cannot see an
unstaged file, so the gate must be run AFTER `git add`, never before. The first draft of THIS entry
was staged and then checked, and the gate returned **9 leaks** — instance concept names, column names
and relation names quoted from the worked example. Under the old order they would have been committed
to a public repository behind a green line, exactly as two tokens were the previous morning. The
example above is the same argument with placeholders; nothing in it is weaker for being generic.
