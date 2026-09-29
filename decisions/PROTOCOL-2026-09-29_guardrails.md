# PROTOCOL — 2026-09-29 · guardrails: the concluding structure, and what it is owed

**Written because the operator asked for it: "protocol last state of the art and concluding
structure".** Everything below is measured or quoted, not remembered. Where a number appears, the
command that produced it is nameable.

---

## PART 1 — THE DAY'S VERDICT, IN THE OPERATOR'S WORDS

> how many times did we try to reingest contoso in 5? 4-5 time today ... right? every new time you
> have managed to forget someting. when i remind you that someting is missing ... you started to
> reinvent exising things and you were doing it in different way ever time. **this is maximal
> unreliability and it is unacceptable**

Correct, and the count was five. Each run lost a different deliverable — the lineage artifact, then
the entire data-quality assessment, then the SME questions — and **each run reported itself
complete**.

It was never forgetting. What is not written down as a durable artifact is **RE-INFERRED** on the
next run, and re-inference is stochastic. That is the whole diagnosis, and the community's
independent finding is the same one: *"your AI agent may behave like it had never seen your system
before — most teams describe this as forgetfulness. However, the AI didn't actually forget; it
re-inferred."*

The answer is therefore not a better instruction. It is a declaration a deterministic check can
hold the work to, and a refusal that fires **at the action** rather than a finding that arrives
after it.

---

## PART 2 — THE CONCLUDING STRUCTURE

```
meaning-as-code/
  guardrails/
    README.md                   what a guardrail is · UNSPECIFIED IS NOT RULED
    common.yaml                 rules everywhere; delivers NOTHING              3 refusals
    unfiled.yaml                delivered, filed under no subject yet            5 items
    data/
      sources.yaml              what is THERE                                   13 items
      quality.yaml              what is WRONG                                    7 items
      sme_questions.yaml        what must be DECIDED                             2 items
      transformation.yaml       what we decided to SERVE — consumes the above   11 items
    ontology/
      README.md                 EMPTY, and saying so is the statement
  mac_artifacts.yaml            6 kinds no topic claims yet (was 23)
```

**44 declarations · 0 conflicts.**

### The four axes, and why they are four

| axis | answers | lives on |
|---|---|---|
| **topic** | what is this artifact ABOUT | the file it is declared in |
| **phase** | which DELIVERY owes it | the item |
| **lifecycle** | may a present file be trusted, or must it be re-derived | the item |
| **population** | what is the DENOMINATOR — n of what | the item |

Topic and phase are **not** the same axis, and conflating them is the error that named a file
`data-ingestion` while it declared `phase: sources` over a set of items mostly written by both
deliveries. Measured: **4 of 25 items are landing-plane-specific; 21 are written or re-derived by
both.** A split by delivery would have left 17 items homeless or duplicated.

### The three parts of a topic

1. **`delivers`** — the cookbook. Per item: `path`, `naming`, `population`, `lifecycle`,
   `producers`, `consumers` **with the fields each reads**, `checkers` with their reject classes.
2. **`refuses`** — blocked AT THE ACTION by a hook, each carrying `why` and `instead`.
3. **`watch`** — where the measurement is written and what a person looks at.

A topic may declare refusals and no items — `common.yaml` does, because three refusals are about
writing anything at all and repeating them per topic would be four homes for one rule.

### The laws this tree rests on

* **UNSPECIFIED IS NOT RULED.** A guardrail constrains exactly what it declares. No rule by
  omission. An empty `ontology/` is therefore a statement, not an oversight, and it says so in its
  own README.
* **A KIND BELONGS TO EXACTLY ONE FILE.** Moving between topics is a MOVE, never a copy — which is
  why **no precedence rule exists anywhere in this tree**. `bom.conflicts` is the gate. I made that
  mistake twice today; it caught both.
* **A LOADER MUST RECURSE.** Measured the hour the tree was grouped: a flat `guardrails/*.yaml`
  found **2 topics instead of 6**, which would have reported a complete delivery as entirely
  undeclared.
* **AN INVARIANT MUST BE SHOWN TO REJECT A MUTANT**, or it is not an invariant.

---

## PART 3 — THE BILL OF MATERIALS

`mac_resources` emits it into `<bundle>.mac`, per phase. **Three outcomes, not two:**

```
present      declared, and found
absent       declared for THIS phase, and NOT found      <- the completeness answer
undeclared   found, and claimed by no declaration        <- the gap in the DECLARATION
```

The third is what makes it an answer rather than an inventory. The block it replaced came from nine
hand-written patterns and saw **41 of the 138 files a phase-1 delivery writes** — every DQ page,
every register page, the SME questions and the lineage artifact invisible to it. **A BOM that cannot
see a thing cannot report it missing**, so its absence list read clean over sixty-six undeclared
files.

**PRESENCE AND NAMING ONLY, deliberately.** Operator: *"this could also cover SME and DQ ... not
from the content accuracy but at least from the formal side."* It is the one question askable of
every artifact regardless of form.

Measured on a full two-phase delivery of contoso5:

```
PHASE SOURCES    complete=True    29/29 items    181 files
PHASE DATASETS   complete=True    34/34 items    215 files
absent 0 · undeclared 0 · conflicts 0
```

---

## PART 4 — WHAT REFUSES, AND THE EVENT BEHIND EACH

Nine refusals across three topics. Every one is something that actually happened, and every one was
proven to fire against a seeded mutant: **5 of 5 refused, a legitimate write still allowed.**

| refusal | the event |
|---|---|
| `UNDECLARED-ARTIFACT` | a delivery reporting 6 of 6 complete with its entire DQ assessment missing |
| `INVENTED-VOCABULARY` | `mac.name.served_relation` invented inside the registry whose job is to stop that — then written AGAIN into the comment explaining its removal |
| `UNPARSEABLE-SPEC` | `mac_artifacts.yaml` committed unparseable; four commits of tracebacks instead of verdicts |
| `RENAMED-LANDING` | a `d_`/`f_`/`b_` prefix scheme against a CLOSED role table, surviving design, build, measurement, commit and report |
| `INVENTED-COLUMN-ROLE` | a closed vocabulary treated as a suggestion |
| `TRANSIENT-AT-DELIVERY` | a value domain left inline instead of cut to a register |
| `INVENTED-SERVED-ROLE` | the same prefix scheme, on the served plane |
| `SERVED-NAME-COLLIDES-WITH-A-LANDING` | lineage rendering `source -> dataset` as a self-loop |
| `TRANSFORM-WITHOUT-A-FINDING` | a guarantee with no finding behind it |

**`RENAMED-LANDING` escaped on its first run** and the escape is the most instructive result of the
day: it compared `table.name` to the file stem, and `d_customer.yaml` declaring
`table.name: d_customer` is perfectly self-consistent and entirely invented. **INTERNAL CONSISTENCY
IS NOT CONFORMANCE.** It now holds the name against what the warehouse actually landed, and no
evidence available means NO VERDICT, never a pass.

---

## PART 5 — HOW FAR THIS REACHES

Operator: *"you already are doing exactly the same thing with yaml vocabulary from mac - for six
months by now. the question is ... how far reaching and universal this framework might be now?"*

Four rule classes. **Only one is tied to file form.**

| class | needs | generalises? |
|---|---|---|
| **token** — a `mac.*` must resolve | grep + a vocabulary | **yes, today** — `check_vocabulary_tokens` scans raw text and caught a token inside a COMMENT; only its glob is YAML-shaped |
| **identity** — the five homes of a name agree | string equality across files | **yes** |
| **membership** — a closed set equals what the source holds | the warehouse | **yes** — CSV registers are re-measured against it |
| **shape** — the document is well-formed | a parser per form | **no** — and all three acceptors already exist: `validate_schema` (yaml), `check_sample_matches_descriptor` (csv header), `check_pages_current` (re-render, byte-compare) |

They have never been named as the same kind of thing. That naming is the cheapest remaining win.

---

## PART 6 — WHAT IS OWED

Ordered by what I would do next.

1. **NOTHING CALLS THE HOOK.** `check_guardrails.py --propose` answers allow/deny and is invoked by
   nothing. By this protocol's own argument that makes it a note, not a guard. **This is the item
   that matters most**; everything else is bookkeeping beside it.
2. **`guardrail_runs.json` is declared and not written.** `watch.record` names it in five topics;
   `check_guardrails` mentions it zero times. `--inspect` already computes everything it needs.
3. **47 of 76 checkers are reachable from no runner.** Seven of them run clean today and cover
   declared items — and one, `check_pages_current`, reports **4 stale pages on contoso2 right now**.
   Wiring them is a stage-table edit, and it will turn the delivery red. That is the point.
4. **13 of 38 items declare no checker**, among them `register_page` (24 files, 17 % of a
   delivery), `sme_questions_page`, and `usage_guardrails` — which is measured EMPTY on one bundle,
   30 lines against 645, because `references.py` globs concepts flat.
5. **No phase-1 enforcer for the column-role rule.** `check_column_planes` exits 2 without an
   ontology and phase 1 has none by design.
6. **CSV and Markdown have no write-time refusal.** Eight of nine refusals need YAML.
7. **`check_artifact_conformance`'s self-test is 26/27**, failing on *"the registry itself satisfies
   its own rules"*. **Left red deliberately** — it is telling the truth, and a self-test adjusted to
   pass over a real gap is the defect removed earlier the same day.
8. **`mac_artifacts.yaml` still holds 6 kinds** with no topic. It should reach zero and be deleted.
9. **The ontology plane is unruled.** Deliberate, recorded, and the two artifacts waiting for it
   carry `belongs_to: ontology` in `unfiled.yaml`.

---

## PART 7 — THE RULINGS THAT STAND

From the superseded delivery-manifest record, unchanged:

| | |
|---|---|
| **scope** | all four phases declared: `sources · datasets · ontology · tuning` |
| **severity** | an artifact no kind declares is an **ERROR** — the delivery is refused. No warning tier: a warning is how the DQ assessment went missing while every surface read green |
| **SME** | reconciling `governance/sme-questions.yaml` with `data/quality/sme_threads.json` is a **separate job**. Two operator rulings are in conflict and only the operator reconciles them |
| **vocabulary gate** | fix my token, report the other eleven — declaring a namespace whose semantics I did not author would be the same defect one level up |

And from this day:

| | |
|---|---|
| **packaging** | topic files under `guardrails/`, grouped by plane. Never one big file |
| **the BOM** | presence and naming; content accuracy is the per-item checker's job |
| **first, validate what you have** | applying it to the operator's own proposal found that the BOM already existed and needed fixing, not building |

---

## PART 8 — THE RECORD

Eleven commits on `meaning-as-code`, `a5b6dc6` through `1cd0109`. The design rationale is
`PROPOSED-2026-09-29_guardrails.md`; the diagnosis and the measured cost of not having any of this
is `PROPOSED-2026-09-29_delivery-manifest.md`, superseded but kept for exactly that.

**Twelve defects were found by building this, not by looking for them.** The ones worth carrying:

* `always` was honoured on one resume branch and ignored on the other — five stages flagged
  `always: True` resumed anyway on the very next run. **A flag that is set, reported and not read is
  worse than an absent one: everything says the fix is in.**
* A self-test was pinning a tautology. `NAME-MATCHES` could not fail, and a green case asserted the
  narrow selector that made it so. **A self-test that ratifies the defect is the defect with a
  certificate.**
* `column_table.py` held two functions thirty lines apart that disagreed about one field's shape, so
  a delivered page rendered a Python dict at a reader. Invisible for as long as nothing could record
  that a consumer wanted `references.to`.
