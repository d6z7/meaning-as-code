# GUARDRAILS — ONE SMALL FILE PER TOPIC, AND SOMETHING THAT CAN SAY NO

**Status: PROPOSED.** Written by an agent; an agent may only write PROPOSED. The design is the
operator's; the measurement is mine. Supersedes `PROPOSED-2026-09-29_delivery-manifest.md`, whose
four rulings are carried forward unchanged and whose diagnosis is not restated here.

---

## THE SHAPE, IN THE OPERATOR'S WORDS

> i thinks you should have the description part ... as you started in mac / instead of building one
> BIG FILE you should have topic related set of small ones - my opinion - similar to ontology
> concepts / all spec files shoujld be in the subdirectory "guardrails" being direct under mac root.
> so you would have something like "data-ingestion" file for this first part. / **the unspecified
> parts are simply not ruleld.**

and, on what it is for:

> i would like to see it in small action ... **to refuse action if you start inventing new world**

and, on how to build it:

> **this way you should first validate what you have before inventing**

---

## THE THREE PARTS

A topic file settles three things and nothing else.

**1 · THE COOKBOOK — `delivers`.** One entry per item the topic owes: `path`, `naming`,
`population` (the denominator), `lifecycle`, `producers`, `consumers` with the FIELDS each reads,
`checkers` with their reject classes. `consumers[].reads` is the field that makes a reader/producer
disagreement checkable, and it is the only genuinely new fact in any of this.

**2 · THE ENFORCEMENT — `refuses`.** Blocked AT THE ACTION, by a hook, not reported afterwards by a
gate. Each refusal carries `why` and `instead`, because a block with no way forward is a wall.

**3 · THE DIAL — `watch`.** Where the measurement is written and what a person looks at. Written
whatever the verdict: a gate that records only its passes leaves a display that goes blank exactly
when something is wrong.

## THE ONE RULE ABOUT RULES

**UNSPECIFIED IS NOT RULED.** A guardrail constrains exactly what it declares. No rule by omission,
no implicit convention, no "it should have been obvious". If a thing is not in a guardrail, doing it
is allowed — and if that turns out wrong, the fix is to write the rule down, not to expect it to
have been inferred.

This is what makes starting with one topic safe. `data-ingestion` rules the landing plane and says
nothing about datasets, the ontology or the console.

## MOVED, NOT COPIED

A kind belongs to exactly one declaration. When the eight phase-1 kinds moved into
`guardrails/data-ingestion.yaml` they LEFT `mac_artifacts.yaml` (23 → 15). **There is therefore no
precedence rule anywhere**, and `bom.conflicts` is the gate that keeps it that way.

My first attempt copied them instead, and within minutes four of eight disagreed on their paths —
the two-homes defect, reproduced inside the file written to end it. The operator stopped it:
*"it makes no sense to continue if you made wrong turn."* That is why this section exists.

---

## REPORTING IS NOT REFUSING

This is the difference between the guardrails and every gate that preceded them.

| | when it speaks | what it can do |
|---|---|---|
| a gate | after the artifact exists | record a mistake |
| a guardrail | at the action | prevent one |

Measured, 2026-09-28/29, across one day:

* `conformance` printed FAIL and the delivery ran to completion, twice.
* `mac_artifacts.yaml` was committed unparseable — the write happened before the line that
  validated it — and for four commits every run of the gate was a traceback, not a verdict.
* `NAME-MATCHES` reported PASS over a descriptor named `THIS_IS_NOT_A_RELATION NAME!!.yaml`,
  because its selector and its judge were derived from the same string.

The community's finding is the same one: the layer that works is *"controls that are code the agent
runs inside but cannot change"*, injected *"right before the decision point where it would otherwise
go wrong"*. What an agent forgets it does not forget — it **re-infers**, and re-inference is
stochastic. A durable declaration plus a deterministic refusal is the answer; a better instruction
is not.

### The refusals, and the evidence for each

Each is something that actually happened, and each was proven to fire against a seeded mutant.

| id | the event it exists for |
|---|---|
| `RENAMED-LANDING` | a `d_`/`f_`/`b_` prefix scheme invented against a CLOSED role table, caught only after it was built, measured, committed and reported |
| `INVENTED-VOCABULARY` | `mac.name.served_relation` — a namespace no vocabulary declares — invented INSIDE the registry whose job is to stop that, then written again into the comment explaining its removal |
| `INVENTED-COLUMN-ROLE` | a closed vocabulary treated as a suggestion |
| `TRANSIENT-AT-DELIVERY` | a value domain left inline on a descriptor instead of cut to a register |
| `UNPARSEABLE-SPEC` | the unparseable commit above |
| `UNDECLARED-ARTIFACT` | a delivery reporting `6 of 6` complete with its entire data-quality assessment missing |

**5 of 5 mutants refused; a legitimate write still allowed.** `RENAMED-LANDING` escaped on the first
run — it compared `table.name` to the file stem, and `d_customer.yaml` declaring
`table.name: d_customer` is perfectly self-consistent and entirely invented. **Internal consistency
is not conformance.** It now holds the name against what the warehouse actually landed, and no
evidence available means NO VERDICT, never a pass.

---

## THE BILL OF MATERIALS

`mac_resources` emits it into `<bundle>.mac`, per phase. **Three outcomes, not two:**

```
present      declared, and found
absent       declared for THIS phase, and NOT found     <- the completeness answer
undeclared   found, and claimed by no declaration       <- the gap in the declaration itself
```

The third is what makes it an answer rather than an inventory. The block it replaced came from a
nine-pattern hand-written table and saw **41 of the 138 files a phase-1 delivery writes** — every
data-quality page, every register page, the SME questions and the lineage artifact invisible to it.
A BOM that cannot see a thing cannot report it missing, so its absence list read clean over
sixty-six undeclared files.

**PRESENCE AND NAMING ONLY, deliberately.** It says nothing about whether content is correct — the
per-item checkers own that. It is the one question askable of every artifact regardless of form, and
it is what covers the data-quality pages and the SME questions formally. Operator: *"this could also
cover SME and DQ ... not from the content accuracy but at least from the formal side."*

`absent` is SCOPED TO A PHASE and honours `empty_is: OK`. Unscoped, a landing-only delivery reported
nine served-plane items missing, and "incomplete" then means nothing because the delivery was never
asked for them.

---

## HOW FAR THIS REACHES

Four rule classes. Only one is tied to file form, which is why the YAML-shaped machinery of the last
six months generalises further than it looks.

| class | needs | form-agnostic? |
|---|---|---|
| **token** — a `mac.*` must resolve | grep + a vocabulary | **yes** — `check_vocabulary_tokens` already scans raw text and caught a token inside a COMMENT; only its glob is YAML-shaped |
| **identity** — the five homes of a name agree | string equality across files | **yes** |
| **membership** — a closed set equals what the source holds | the warehouse | **yes** — CSV registers are re-measured against it today |
| **shape** — the document is well-formed | a parser per form | **no** — and all three acceptors already exist: `validate_schema` (yaml), `check_sample_matches_descriptor` (csv header), `check_pages_current` (re-render, byte-compare) |

They have simply never been named as the same kind of thing.

---

## VALIDATE BEFORE INVENTING

The operator's instruction, and applying it to the operator's own proposal changed the plan:

* a BOM for the dynamic payload **already existed** — `*.mac`, `mac.resources/1`, with an `absent`
  block. It was under-declared, not missing. **Fixed, not rebuilt.**
* four naming checkers **already exist**, each scoped to one plane; the universal rule the operator
  asked for is the hole between them, not a replacement for them.
* **76 checkers exist and 47 are reachable from no runner** — including seven that run clean today
  and one, `check_pages_current`, that reports four stale pages on a delivered bundle right now.

That last number is the standing argument for this whole discipline: the estate's problem is not
too few checks. It is that nothing knows what it has.

---

## OPEN

1. **Nothing calls the hook.** `check_guardrails.py --propose` answers allow/deny and is invoked by
   nothing, which by this document's own argument makes it a note.
2. **14 classes / 64 files still undeclared** — the DQ pages, the register pages, the SME questions,
   `usage_guardrails.md`.
3. **Seven orphaned checkers unwired.**
4. **No phase-1 enforcer for the column-role rule** — `check_column_planes` exits 2 without an
   ontology, and phase 1 has none by design.
5. **CSV and Markdown have no write-time refusal** — five of six refusals need YAML.
6. **`check_artifact_conformance`'s self-test is 26/27**, failing on *"the registry itself satisfies
   its own rules"*. It is left red because it is telling the truth; a self-test adjusted to pass over
   a real gap is the defect removed two commits earlier.

## STILL RULED, FROM THE SUPERSEDED RECORD

`all four phases declared` · `undeclared artifact = ERROR` · `SME questions are a separate job` ·
`fix my vocabulary token, report the other eleven`.
