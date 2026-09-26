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
import pipeline (`sdk/cli/harvest.py`, whose `--mode onboard` is scaffold → data → reconcile →
*concepts deliberately skipped* → project) for the tools that make the list above:

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
| **D1** | all data sources | `data/sources/*.yaml` | `harvest --mode data` | **IN** |
| **D2** | all data assets | `data/datasets/*.yaml` | `harvest --mode data` | **IN** |
| **D3** | ER diagram, actual state | `objects.json#er_model`, `#er_model_served` | `project` ← **`mac_references.py`** | **WIRED** — `project` writes the key, and it comes back with **0 entities** until references are measured |
| **D4** | all concepts | `ontology/concepts/**/*.yaml`, `ontology/edges.yaml` | `harvest --mode concepts` | **WIRED, deliberately** — excluded from onboard by a 2026-08-18 ruling: *"the concept stage is not merely billed, it is a JUDGEMENT"*. See R1 below. |
| **D5** | SME questions, both planes | `governance/sme-questions.yaml`, `ontology/SME-QUESTIONS.md` | `mac_resources.py` | **WIRED** |
| **D6** | all diagrams | `#lineage_graph`; Mermaid; property graph | `project` (lineage **IN**); `mac_to_mermaid.py`, `mac_to_graph.py` | **PART IN** — lineage only |
| **D7** | data quality tests **executed** | `acceptance/data_sanity_generated.yaml` **+ `_runs.json`** | `mac_generate_sanity.py` **+ `run_suite.py`** | **WIRED** — and generating is not testing: the suite and the RUN RECORD are two artifacts |
| **D8** | ontology quality tests **executed** | `acceptance/ontology_generated.yaml` **+ `_runs.json`** | `mac_generate_ontology_tests.py` **+ `run_suite.py`** | **WIRED** |

---

## D9..D14 — WHAT D1..D8 CANNOT EXIST WITHOUT

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

## THREE DEFECTS THAT BLOCK A FRESH IMPORT OUTRIGHT

All three were hit on 2026-09-26 importing one bundle. Any first run on a DuckDB bundle hits all
three.

| | defect | evidence | state |
|---|---|---|---|
| **B1** | **no framework engine seam.** `_plugin.py` requires the bundle to supply `tools/run_properties.py`, and the framework ships no default. A brand-new bundle cannot be MEASURED until someone hand-copies a 157-line shim. | `mac_profile.py` answers *"this check needs tools/run_properties.py to supply 'Athena', and the bundle declares none"* | **open** |
| **B2** | **`mac_profile.py` emits Trino-only SQL.** Its value-domain capture uses `array_join(array_sort(array_agg(DISTINCT …)))`; DuckDB answers *"Did you mean array_position?"* and the run dies before writing a profile. `example/contoso` never hits it only because its domains were already captured — latent, not absent. | the run dies with `_duckdb.CatalogException` | **open** |
| **B3** | **`mac_references.py` crashed instead of reporting.** With zero candidate pairs it raised `ZeroDivisionError` on its own summary line, losing the finding that explains it. | now prints `0 pair(s) considered … NOTHING TO MEASURE: 0 of 6 relation(s) carry a key` | **fixed 2026-09-26** |

B1 and B2 together mean: **the measurement plane cannot be built on a DuckDB bundle today**, and D7,
D9, D10 and D3 all sit downstream of it.

---

## R1 — THE ONE RULING THIS LIST NEEDS

**D4, concepts, is excluded from the one-run pipeline BY A DELIBERATE RULING**, recorded in
`harvest.py` on 2026-08-18:

> It used to run automatically on a NEW source … `--accept` is exactly what an operator passes to
> onboard a source, which made the most convenient command the one that produced the failure mode:
> concepts authored from the table list before a single business document had been read. … The
> concept stage is not merely billed, it is a JUDGEMENT.
>
> (Removed 2026-08-18. `estate/estate` is exactly 20 concepts from 20 datasets — what the chained stage
> produces when nobody is looking.)

That ruling and "all concepts in the first run" are in direct conflict, and the conflict is real
rather than verbal: one concept per relation is what an unsupervised stage produces, and it is worse
than nothing because it looks finished.

**Three ways to settle it, and this is the operator's call:**

| | | consequence |
|---|---|---|
| **a** | run it, marked | concepts arrive `status: draft, confidence: Q, provenance: machine`, every one carrying the open question "is this a business notion?" — the first run is complete and honestly labelled |
| **b** | keep it out | the run stops at the data plane; D4 is a second, explicit command, and the state report says so in one line |
| **c** | run it only where the DATA argues for it | a relation with a measured key and inbound references becomes a concept; a bridge or a staging table does not — fewer concepts, each with a reason |

Nothing else in D1..D14 is in question; this is the only item where the platform disagrees with the
list on purpose.

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
