# DELIVERABLES — WHAT ONE IMPORT RUN MUST HAND THE OPERATOR

**Status:** the contract. Written 2026-09-26 from the operator's own list, with the measured state of
each producer beside it.

---

## THE EXPECTATION, IN THE OPERATOR'S WORDS

> our FIRST DELIVERABLE is PLATFORM and not ontology. platform must deliver as much as possible of
> sound ontology in the first run!!! thus in order to continue ... an operator will need:
>
> - all data sources
> - all data assets
> - ER diagrams for actual state
> - all concepts
> - all questions for SME for data and ontology
> - all diagrams
> - all data quality tests executed
> - all ontology quality tests executed
>
> **EXPECTATION: FULL STATE FROM WHICH OPERATOR CAN CONTINUE TUNING ONTOLOGY**
>
> so dont give me this shit over and over where i have to ask for functionality here and there

**That last sentence is the acceptance criterion, not a complaint.** A deliverable an operator has to
ask for was not delivered. The measure of this document is that nothing in it is requested twice.

---

## WHY THE LIST WAS NEEDED — THE MEASURED CAUSE

The platform has **~30 producers and 63 gates, and nothing that runs them in order.** Grepping the
import pipeline (`sdk/cli/harvest.py`, whose `--mode onboard` was scaffold → data → reconcile →
*concepts deliberately skipped* → project, until that last instruction was deleted — see R1) for the
tools that make the list above:

| producer | references in the pipeline |
|---|---|
| `mac_profile.py` — the measurement plane everything else reads | **0** |
| `mac_sample.py` | **0** |
| `mac_references.py` — what the ER model is built FROM | **0** |
| `mac_generate_sanity.py` — the DQ suite | **0** |
| `mac_generate_ontology_tests.py` — the ontology suite | **0** |
| `run_suite.py` — the thing that EXECUTES either | **0** |
| `mac_resources.py` — the SME question ledger | **0** |

Every one of them exists and works. None is wired into a run. `example/contoso`'s
`mac.project.yaml` records them as `reproduction.stages` — a list of commands a **person** ran, one
at a time — which is exactly why each artifact surfaced as a request instead of arriving.

---

## D1..D8 — THE OPERATOR'S LIST

Status is measured, not estimated. `IN` = produced by one existing run. `WIRED` = producer exists and
no run calls it. `GAP` = no producer.

| | deliverable | artifact | producer | status |
|---|---|---|---|---|
| **D1** | all data sources | `data/sources/*.yaml` | `harvest --mode data` (billed) **or `mac_descriptors.py` (measured, free)** | **IN** |
| **D2** | all data assets | `data/datasets/*.yaml` | as D1 | **IN** — measured 22 descriptors on a bundle holding only a manifest and a connection, every relation keyed |
| **D3** | ER diagram, actual state | `objects.json#er_model`, `#er_model_served` | `project` ← **`mac_references.py`** | **WIRED** — `project` writes the key, and it comes back with **0 entities** until references are measured |
| **D4** | all concepts | `ontology/concepts/**/*.yaml`, `ontology/edges.yaml` | `harvest --mode concepts` | **IN** since 2026-09-26 — the instruction that withheld it is deleted; it authors over the WHOLE inventory (M:N, never per table) as `status: draft`, enforced by `check_concepts_not_per_table.py`. See R1. |
| **D5** | SME questions, both planes | `governance/sme-questions.yaml`, `ontology/SME-QUESTIONS.md` | `mac_resources.py` | **WIRED** |
| **D6** | all diagrams | Mermaid; property graph; ER (D3); lineage (D15) | `mac_to_mermaid.py`, `mac_to_graph.py` | **WIRED** |
| **D15** | **lineage** | `objects.json#lineage_graph` (table level) + the column-level model | `project`; `lineage_project.py` | **IN** at table level — *added 2026-09-26 on the operator's instruction. It was folded into "all diagrams", which is wrong: a diagram is a rendering, lineage is a MEASURED claim about where a column came from, and it is what an operator follows when a number is wrong.* |
| **D7a** | DQ **test cases** | `acceptance/data_sanity_generated.yaml` | `mac_generate_sanity.py` | **IN** |
| **D7b** | DQ tests **executed** | `acceptance/data_sanity_generated_runs.json` | `run_suite.py` | **IN** |
| **D7c** | DQ **results** | the record's `results[]` + `tally`; `data/quality/data_quality_register.yaml`; `dq_dashboard.json` | `run_suite.py`; `project` | **PART IN** — *split out 2026-09-26: the old single D7 was satisfied by the FILE EXISTING, which is the defect it exists to prevent. Measured on contoso: the record carries **71 per-case results** and a tally, and a report that says "1 file" while 3 cases fail has told the operator nothing.* |
| **D8a** | ontology **test cases** | `acceptance/ontology_generated.yaml` | `mac_generate_ontology_tests.py` | **IN** |
| **D8b** | ontology tests **executed + results** | `acceptance/ontology_generated_runs.json` | `run_suite.py` | **IN** |

---

**GENERATING IS NOT TESTING, AND EXECUTING IS NOT REPORTING.** Three artifacts, three
deliverables — a generated suite has asserted nothing, a run record proves it ran, and only the
`results[]` and `tally` say what it FOUND. Collapsing them is how a green dashboard gets published
over three failing cases.

---

## D9..D14 — WHAT THE OTHERS CANNOT EXIST WITHOUT

Not additions to the operator's list. Each one is a prerequisite discovered by trying to produce the
list and failing.

| | deliverable | artifact | producer | why it is on the list |
|---|---|---|---|---|
| **D9** | the measurement plane | `data/profiles/*.yaml` | `mac_profile.py` | **D7 is GENERATED FROM IT** — "generate the data-sanity suite FROM the profile. Nobody authors these." No profile, no DQ suite. |
| **D10** | referential structure | `data/references/*.yaml`, `data/references_served/*.yaml` | `mac_references.py` | **D3 IS BUILT FROM IT.** Measured on a bundle without it: `er_model` returns `entities=0, relationships=0, references_measured=0` — the ER view is empty and says nothing about why. |
| **D11** | a sample per CONCEPT | `data/samples/concepts/*.sample.csv` | `mac_sample.py --plane concepts` | DNA law 8 / P9. Per concept, not per relation: `Store` and `StoreStatus` read the same 74 rows and declare 12 and 2 columns, and the subset is what is under review. Three wrong declarations on 2026-09-26 were each visible in four rows. |
| **D12** | value registers | `data/lookups/*.lookup.csv` | `harvest --mode lookups` | A closed domain resolves a WORD to a CODE offline. Without it a question probes the warehouse and reads "no rows" as "no such thing". |
| **D13** | the resource description | `<name>.mac` | `mac_resources.py` | How a host OPENS the bundle at all — the console's file dialog resolves a bundle by the identity this file carries. |
| **D14** | the state report | stdout + `.harvest_manifest.yaml` | **the import run** | **The deliverable that makes the other thirteen checkable.** It must name, per deliverable, what was produced, what was not, and WHY — so "the operator had to ask" becomes impossible: the run already said. |

---

## FOUR DEFECTS THAT BLOCKED A FRESH IMPORT OUTRIGHT — ALL FIXED 2026-09-26

All four were hit importing one bundle. Any first run on a DuckDB bundle hit all four.

| | defect | evidence | state |
|---|---|---|---|
| **B1** | **no framework engine seam.** `_plugin.py` requires the bundle to supply `tools/run_properties.py`, and the framework ships no default. A brand-new bundle cannot be MEASURED until someone hand-copies a 157-line shim. | `mac_profile.py` answers *"this check needs tools/run_properties.py to supply 'Athena', and the bundle declares none"* | **fixed** — `duckdb_seam.py` is the framework default, offered by `_plugin.required` only when the bundle's own manifest declares DuckDB, so it can never answer for another engine. Self-test 21/21. |
| **B2** | **`mac_profile.py` emits Trino-only SQL.** Its value-domain capture uses `array_join(array_sort(array_agg(DISTINCT …)))`; DuckDB answers *"Did you mean array_position?"* and the run dies before writing a profile. `example/contoso` never hits it only because its domains were already captured — latent, not absent. | the run dies with `_duckdb.CatalogException` | **fixed** — translated in the seam that owns the connection: `string_agg(DISTINCT expr, sep ORDER BY expr)`, which keeps DISTINCT and SORTED so a captured domain stays deterministic |
| **B3** | **`mac_references.py` crashed instead of reporting.** With zero candidate pairs it raised `ZeroDivisionError` on its own summary line, losing the finding that explains it. | now prints `0 pair(s) considered … NOTHING TO MEASURE: 0 of 6 relation(s) carry a key` | **fixed 2026-09-26** |

| **B4** | **`mac_profile.py` died over LABELS.** It read `acceptance/properties.yaml` unguarded, and a fresh bundle has none, so a first run ended in a bare `FileNotFoundError` traceback. | the four engine keys are RECORDED in the evidence and decide nothing — which warehouse is opened is `connection.yaml`'s job | **fixed** — an absent file means unlabelled, not unrunnable |

B1 + B2 + B4 together meant **the measurement plane could not be built on a DuckDB bundle at all**,
and D3, D7, D9 and D10 all sit downstream of it. **Proven after the fix:** a bundle holding only
`mac.project.yaml` and `connection.yaml` — no `tools/`, no `acceptance/`, no shim — measures 22
descriptors and profiles a relation.

---

## R1 — SETTLED: CONCEPTS RUN IN THE FIRST RUN, AND ARE NEVER 1:1 WITH DATASETS

**This section used to present three options and quote a withheld-stage instruction as if it were a
legitimate ruling. The operator deleted both, 2026-09-26:**

> this is all wrong: *"estate/estate is exactly 20 concepts from 20 datasets — what the chained stage
> produces when nobody is looking."*
>
> **datasets DO NEVER MATCH CONCEPTS 1:1**
>
> concepts must SEARCH for business LOGIC in data and create it independent of physical layer
> objects. please DELETE misleading instruction

**Why the deleted instruction was wrong, and it is worth stating precisely because I had accepted
it.** It withheld the concept stage from the one run an operator actually performs, and justified
that with an outcome — a bundle came out at exactly 20 concepts over 20 datasets. That number is
real, and it is evidence of a DEFECT IN THE DRIVER, not evidence that authoring must be withheld:
the old loop called the model ONCE PER DATASET and named each file after the dataset stem, so 1:1
was true by construction. A caller that asks *"what is the concept for THIS table"* can only be
answered with one concept per table.

Withholding the stage left that driver unfixed and moved the cost onto the operator, who then has
to ask for concepts — the exact pattern the pipeline exists to end.

**What is true instead, and it was already in the code.** `sdk/authoring` PASS 1 plans over the
WHOLE relation inventory in one call, and its prompt already says what the deleted comment denied:

> A CONCEPT IS A BUSINESS NOTION, NOT A TABLE. The mapping between concepts and relations is M:N …
> A relation may back NO concept at all: a pure mapping/bridge table is not a notion, it dissolves
> into a rule or an edge. A notion may exist with NO backing table of its own.

So D4 **runs in the first run**. It remains a judgement, and that is handled by MARKING rather than
by absence: what it writes is `status: draft`, and the operator tunes it. An unmarked guess and a
withheld stage are both worse than a labelled draft — the first hides that a decision was made, the
second hides that one is needed.

**ENFORCED, because a shape a loop can produce must be refused by a check and not requested by a
paragraph** — the prompt asked for M:N and the loop produced 1:1 anyway.
`check_concepts_not_per_table.py` fails a bundle only when all four hold at once: as many concepts
as datasets, every concept on exactly one relation, no relation shared, no relation declined. Any
one of them absent means a judgement was made. It never demands a particular number — a source
whose notions genuinely align with its relations is legitimate; arriving there without looking is
not.

Measured on the two real bundles: contoso 21 concepts over 6 datasets with 4 relations backing
several notions; estate2 22 over 13 with 3 shared and 13 relations declined. Both pass.

---

## THE ACCEPTANCE TEST

One command against an **empty directory with a connection**, and afterwards:

1. every artifact in D1..D13 exists, or the state report names it and says why not;
2. both suites have a **run record**, not just a generated file;
3. the ER model reports `entities > 0` — if it is empty, the report says which reference measurement
   was missing;
4. the gates that hold this document's own laws pass: `check_concept_samples.py` (D11),
   `check_er_projection.py` (D3), `check_artifact_has_producer.py` (D14);
5. **the operator asks for nothing that is on this list.**

Measured on `example/contoso` for scale, as the thing a first run is compared against: 6 served
relations, 8 raw landings, 21 concepts, 24 edges, 19 registers, 34 constraints, 29 SME questions and
45 sign-off requests.
