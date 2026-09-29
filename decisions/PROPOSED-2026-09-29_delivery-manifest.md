# DELIVERY MANIFEST — ONE DECLARATION PER DELIVERED ITEM

**Status: SUPERSEDED 2026-09-29 by `PROPOSED-2026-09-29_guardrails.md`.** Its four rulings stand and
were carried forward verbatim (scope, severity, SME, the failing vocabulary gate). Its PACKAGING did
not survive contact with the operator: this proposed ONE registry carrying every artifact kind, and
the operator replaced it the same day with per-topic files under `guardrails/`, the way ontology
concepts work. The measurement and diagnosis below remain the record of WHY any of this exists and
are not restated in the successor.

**What survived, and is now in the successor:** `consumers[].reads` (the one genuinely new fact);
`phase`; `lifecycle`; `population` as a stated denominator; the `CONSUMED` / `PHASED` / `COVERED`
invariants; and the meta-rule that an invariant must be shown to reject a mutant or it is not an
invariant.

**What was wrong with it, measured within a day:**

1. **One big file.** 492 lines, 23 kinds, and a topic buried in it could not be approved, revised or
   retired on its own. Operator: *"instead of building one BIG FILE you should have topic related
   set of small ones ... similar to ontology concepts."*
2. **It reported; it did not refuse.** Every invariant here produces a finding AFTER the fact.
   `conformance` printed FAIL and the delivery ran to completion; this very file's registry was
   committed unparseable because nothing stood between writing it and committing it.
3. **Its item list came from the checklist, not the census.** It declared what somebody had already
   written down. Measured on a phase-1 delivery: 30 artifact classes written, 8 declared — the whole
   data-quality family, the SME questions, the register pages and the lineage artifact absent from
   it, which is the same omission it was written to end.

Originally written 2026-09-29. Written after five re-ingests of contoso5 in one day, each of
which lost a different deliverable and each of which reported itself complete.

---

## THE EXPECTATION, IN THE OPERATOR'S WORDS

> how many times did we try to reingest contoso in 5? 4-5 time today ... right? every new time you
> have managed to forget someting. when i remind you that someting is missing ... you started to
> reinvent exising things and you were doing it in different way ever time. this is maximal
> unreliability and it is unacceptable
>
> you can make miracles if you have right guidline and the guideline and right instructions is
> exactly what is missing here ... establish the guardrails so that you time gets streamlined into
> right direction ... in my opinion you need enumerated list of items that need to be delivererd /
> for each item you can create list of instruction like expected naming conventions for files and
> items ... and the convention needs an overvierw of who is creator of artifact ... who is
> consumer(s) ... who and what is checking the item

Four facts per item: **creator · consumer · checker · convention.** That is the whole ask.

---

## WHAT WAS LOST, AND WHY EACH LOSS WAS INVISIBLE

Five deliveries of contoso5 on 2026-09-28. Every one exited 0 and reported its checklist complete.

| # | what went missing | why nothing objected |
|---|---|---|
| 1 | `data/lineage/lineage.json` | the `lineage` stage carried no `part`, so BOTH `--part sources` and `--part datasets` held it |
| 2 | the whole DQ assessment | same defect: `dq-suite`, `dq-run`, `dq-findings` carried no `part` |
| 3 | DQ over the served plane | once tagged, the stages RESUMED on phase 1's output: 0 of 8 served relations assessed, and the register still said eight landings were "consumed by no transformation" — eight transformations later |
| 4 | the SME questions | the renderer read `issue["sme_owner"]`; no finding has ever carried that key. 7 open questions rendered with a blank ask column, and the console pane stated "Every condition has been ruled" |
| 5 | contoso1 + estate2 lineage | `objects.json#lineage_graph` was retired and those bundles cannot re-project; the view went blank on two bundles that had worked for months |

**None of these is a forgotten step.** Every one is a missing declaration:

* 1, 2 — nothing declared which PHASE owes the artifact
* 3 — nothing declared whether the artifact is RE-DERIVED or resumable
* 4, 5 — nothing declared who CONSUMES the artifact, so a reader on a dead key is invisible

---

## THE MEASURED STATE (2026-09-29)

**contoso5 holds 45 artifact classes / 278 files.** Against that population:

| mechanism | covers | reads it |
|---|---|---|
| `mac_import.py#CHECKLISTS` | **14 of 45** (31 %) | the import report |
| `mac_artifacts.yaml` | **13 kinds** | `check_artifact_conformance.py`, nothing else |
| `mac_resources.py` DERIVED/AUTHORED/NOT_DECLARED/PLANES | ~48 globs | `check_artifact_has_producer.py` — **which is in no runner** |
| `planes/*.md` `**Accepted by.**` | 86 records — the only per-artifact CHECKER declaration in the estate | **nothing; it is prose** |

**Nine mechanisms declare part of this. None carries all four facts.**

* **producer** is declared FOUR times and they contradict each other on the four largest families.
  `mac_artifacts.yaml` names three tools for `data/sources/*.yaml`; `mac_resources.AUTHORED` says of
  the same glob "a human or a model wrote them and NO tool reproduces them"; `mac_import` runs the
  tool. Same for `data/transforms/*.yaml`, `data/quality/*.yaml`, `data/lookups/*.csv`.
* **checker** is declared once, in prose nothing reads.
* **phase** and **population** are declared once, as 15 hand-written Python lambdas.
* **consumer is declared NOWHERE, at any grain.** `grep -c "Consumed by" ontology/planes/*.md` = 0.

That last line is the finding. Every loss above was a consumer question, and the estate has no
place to write the answer down.

### The gate that cannot fail

`check_artifact_conformance.py#NAME-MATCHES` enumerates files with a glob derived from `path`, then
judges them with a regex derived from the same `path`. Every file it selects matches by
construction. Measured with two mutants on 2026-09-29:

```
data/sources/THIS_IS_NOT_A_RELATION NAME!!.yaml     <- a landing descriptor named nonsense
data/lookups/country.lookup.csv                      <- a register that DROPS the relation, the exact
                                                        collision the registry documents itself as
                                                        existing to prevent
PASS: check_artifact_conformance — 4 of 4 invariant(s) hold over 12 declared kind(s).
```

Both survive. It reported `12 enumerated · 2 held · 10 n/a` and called that PASS. For nine of twelve
kinds the regex reduces to `^data/<dir>/[^/]+\.(yaml|csv|md)$` — any filename at all.

This is the estate's standing lesson one level deeper. Not "a gate reporting PASS over zero files",
but a gate whose predicate is a TAUTOLOGY over the files it chooses to look at.

### Related measured facts

* `mac_artifacts.yaml#name:` — the human sentence describing each naming rule — **is read by nothing.**
  `inv_name` derives its regex from `path` and never opens `name`.
* `mac_artifacts.yaml#vocabulary:` and `#columns:` are read by nothing.
* `mac_artifacts.yaml` has **no schema**. `spec_version: mac.artifacts/1` is validated by nothing.
* The framework **fails its own vocabulary gate**: `check_vocabulary_tokens` reports 12 of 37 tokens
  resolve to nothing, including `mac.name.served_relation` — a namespace invented inside
  `mac_artifacts.yaml`, the file whose job is to stop exactly that.
* `data/lookups/*.lookup.md` — 48 files, 17 % of the bundle — has **no checker of any kind**.
* `references/usage_guardrails.md`, the FIRST document the ask agent is told to read, has no gate
  asserting it exists, is current, or is non-empty.
* `data/lookups/0-registers-overview.md` exists in `mac-ontology-contoso` and **no producer for it
  exists in the framework today**. The register plane lost its index page and nothing noticed.
* `acceptance/suite_history.json` (the projected form the console reads) has no stage that writes
  it, so contoso5's history panel is empty by construction.
* Four stages — `concepts`, `concept-samples`, `ontology-suite`, `ontology-run` — carry no `part`.
  Under the operator's sequential delivery rule **phase 3 is currently unreachable**: it runs only
  under `--part all`, which the rule forbids.

---

## THE RULE THIS PROPOSES

> **An item is delivered when a declared producer has written it, a declared consumer can read the
> fields it carries, and a checker that can be shown to fail has passed over its declared
> population.**

Four clauses, one per failure above. Nothing is delivered on the strength of a stage exiting 0.

---

## THE DESIGN — EXTEND, DO NOT INVENT

`mac_artifacts.yaml` becomes the manifest. It is the only mechanism that is machine-readable,
versioned, one-record-per-kind, already gated, and built on "reference, never copy". Every field
below **already exists somewhere in the estate** and is MOVED, not minted.

```yaml
kinds:
  reference_measurement:
    what:     the measured referential structure of one relation
    phase:    [sources, datasets]          # <- _stages().part      vocabulary: sources|datasets|both
    deliverable: D4                        # <- DELIVERABLES.id     the join to the state report
    path:     data/references/{relation}.yaml | data/references_served/{relation}.yaml
    name:     mac.name.relation_stem       # <- MUST resolve in mac_vocabulary.yaml (see O4)
    shape:    mac.schema.json#/$defs/ReferenceFile
    origin:   derived                      # <- BLUEPRINT.md        derived|authored|hybrid
    who:      agent-autonomous             # <- BLUEPRINT.md
    lifecycle: re-derived                  # <- NEW, see below
    population:                            # <- CHECKLISTS.probe, as DATA not a lambda
      of: every relation of this plane
      from: data/{plane}/*.yaml
      empty_is: EMPTY                      # 0 of 0 is never a pass
    producers:
      - {tool: tools/mac_references.py, role: measures, args: "--plane {plane}"}
    consumers:                             # <- THE NEW FACT
      - {tool: tools/mac_descriptors.py,  role: promotes measured FKs, reads: [verdict, parent_key_role, cardinality]}
      - {tool: sdk/project/er_model.py,   role: draws the crow's feet,  reads: [to, cardinality, participation]}
    checkers:
      - {tool: tools/check_physical_references.py,
         rejects: [ENDPOINT_UNRESOLVED, COLUMN_UNDECLARED, ID_COLLISION, ONTOLOGY_VOCABULARY,
                   EVIDENCE_MISSING, ADMISSION_MISSING, DANGLING_INVENTED, VOCABULARY_CLOSED,
                   PARTICIPATION_MISSING, AMBIGUITY_HIDDEN, UNMEASURED_RELATION]}
      - {tool: tools/mac_import.py#T4, role: coverage over the population}
```

### `lifecycle` — the field that would have caught loss #3

Closed vocabulary, three terms:

* `re-derived` — a pure function of the warehouse or of other artifacts. **Must carry `always: true`
  on its stage.** A stale one is indistinguishable from a fresh one by its presence.
* `resumable` — expensive and idempotent; skipping when present is legitimate.
* `authored-once` — a person or a model wrote it; no tool reproduces it, and a reproduction record
  must not claim to.

`lifecycle: re-derived` + a stage without `always` is a **manifest violation**, checkable statically.
That single rule catches both the DQ resume and the lineage resume, before either runs.

### `consumers[].reads` — the field that would have caught losses #4 and #5

Naming the FIELDS a consumer reads, not just the file, is what makes the reader/writer agreement
checkable. `sme_owner` vs `ruling.question` was invisible for exactly as long as nobody could write
down that a reader wanted a field.

---

## THE THREE CHECKS — AND THE META-RULE

**C1 · CONSUMED** — every declared kind has ≥ 1 consumer, and every field a consumer `reads` is a
field some producer writes (against `shape`). *Catches losses 4 and 5. Deletion candidates fall out
of it: today `data/references*/references.run.json` and `data/samples/samples.run.json` have no
reader in either repo.*

**C2 · COVERED** — every glob in `mac_resources.{DERIVED,AUTHORED,PLANES}` is claimed by exactly one
kind. *Today `mac_artifacts.yaml` covers 12 of ~48 families while reading as complete. Catches
`data/lookups/*.lookup.md`, everything under `references/`, everything under `acceptance/`.*

**C3 · PHASED** — every kind declares a phase; every stage's `produces` is a declared kind; a
`re-derived` kind's stage carries `always`. *Catches losses 1, 2, 3, and the four unreachable
ontology stages. Also catches the `conformance` stage's false claim to produce
`data/datasets/*.yaml` — it is read-only.*

**META · every invariant must be shown to REJECT a mutant, or it is not an invariant.**
Had this rule existed, `NAME-MATCHES` would never have shipped. It is the rule that makes the other
three worth anything, and it is the one the estate already believes in and did not apply here.

### And the checklist stops being hand-written

`CHECKLISTS` becomes a PROJECTION of the manifest, keyed on `phase` + `population`. An item cannot
then be missing from the checklist without being missing from the manifest — which is precisely how
DQ reported `6 of 6` while absent.

---

## WHAT THIS COLLAPSES

Thirteen overlaps become one home. The largest:

* `data/samples/*` is declared in **six** places with four different patterns
  (`mac_artifacts.path`, `mac_resources.DERIVED`, `DELIVERABLES[D11b]`, `CHECKLISTS.S3`+`T3`,
  `_stages().produces`, each bundle's manifest). `mac_import`'s own comments record **three separate
  resume bugs** caused by them disagreeing.
* producer, declared four times and contradicting on four families (above).
* `origin`, declared three times, with `hybrid` existing in `BLUEPRINT.md` and having no
  representation in any machine registry — which is *why* C1–C3 read as contradictions rather than
  as "tool-seeded, model-completed".
* `who`/`authoring`, declared twice with incompatible vocabularies
  (`agent-autonomous|agent-with-human|human-only` vs `tool|model|hand|model-then-hand`), and a third
  spelling for the human case: the literal string `«a person»`.

---

## WHAT THIS DOES NOT CHANGE

* `mac.schema.json` remains the single home for SHAPE. The manifest references it.
* `mac_vocabulary.yaml` remains the single home for TERMS. Every closed field above resolves there.
* `check_served_name_distinct.py` remains the single home for the served-name SPELLING. The manifest
  names the rule; it does not restate it. *"Do not copy that convention into a skill, a bundle README
  or a decision record — a copy is a second home and it does not move when the gate moves."*

---

## OPEN — THE OPERATOR RULES THESE

**O1 · SCOPE — RULED: all four phases.** `sources · datasets · ontology · tuning`. The phase
vocabulary is declared in full from the start. Phase 3/4 entries may stay sparse and be filled when
those deliveries are designed; what matters now is that phase 3 stops being unreachable.

**O2 · SEVERITY — RULED: ERROR.** An artifact on disk that no kind declares REFUSES the delivery.
The escape is the one the estate already has: declare the kind, or list it under
`mac.project.yaml#conformance.out_of_scope` with a reason (CONFORMANCE §5.3). No third path, and no
warning tier — a warning is exactly how the DQ assessment went missing while every surface read green.

**O3 · SME — RULED: separate job, after this.** The existing design
(`mac-platform/temp/sme-questions/DESIGN.md`, PROPOSED 2026-09-17, schema mutant-tested 47 of 47) and
its implementation (`sdk/project/sme_questions.py`) are built and unwired
(`grep -c sme_questions console_api.py` = 0). A competing store, `data/quality/sme_threads.json`,
came from the 2026-09-22 console ruling with a different lifecycle. TWO OPERATOR RULINGS ARE IN
CONFLICT and only the operator reconciles them. Not in this work. Nothing here may invent a seventh
SME vocabulary; the estate already carries six.

**O4 · THE FRAMEWORK'S OWN FAILING GATE — RULED: fix mine, report the rest.**
`check_vocabulary_tokens` fails on 12 of 37 tokens. ONE of them is mine and is fixed here:
`mac.name.served_relation`, invented inside `mac_artifacts.yaml` on 2026-09-28. The other eleven —
`mac.guarantee.*` (4), `mac.resolve.*` (3), `mac.vocabulary.schema.json` and three more, all in
`mac_rules.yaml` — predate this work and are REPORTED, not guessed at: declaring a namespace whose
semantics I did not author would be the same defect one level up. They remain open.

---

## WHY THIS IS NOT A TENTH MECHANISM

Every field is moved from somewhere it already lives. No new file, no new format, no new vocabulary.
The one genuinely new fact is `consumers[]` — and its absence is the single thing that all five of
2026-09-28's losses have in common.
