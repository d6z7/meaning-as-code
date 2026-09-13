---
when: 2026-09-12T23:55:16
what: stopped three projectors writing one instance's identity — and one author's home directory — into the artifacts a public repo commits
topics: [the-public-boundary, projections, containers]
kind: defect
track: ontology
repo: meaning-as-code
---

## WHAT FORCED IT

Three hardcoded tokens travelled from the estate they were written in into artifacts this PUBLIC repo
commits:

* the concept index was TITLED after one specific bundle, so every ontology this projector touched
  got an index naming a bundle it has nothing to do with;
* the vocabulary glossary hardcoded one source's field-role namespace, while its own note said "every
  source defines its own";
* `diagnostics.json` recorded `str(root)` — an ABSOLUTE path on whoever ran the projection. It put an
  author's home directory in a committed artifact.

The lineage heading's instance name went with them. It had been kept deliberately as a methodology
reference rather than a source identity, and that held while projections stayed in one private
estate. **It stopped holding the moment this projector wrote into a public example.**

## EVIDENCE

`git show -s 2f0b0ec` (meaning-as-code). The glossary namespace is now MEASURED from the ontology
being projected, falling back to a `<source>.` placeholder only when the ontology declares no field
role — which is what one of the example bundles honestly does. `diagnostics.json` records the bundle
NAME, "which is the identity a reader needs; the path is the operator's, not the bundle's".

Both bundles were re-projected OFFLINE (no AWS, no Bedrock) through `--project-anyway`, whose stated
reason is recorded in each compile record. Framework gates, measured against develop:

```
tpch  29/34 -> 30/34 green   (one failure cleared)
shop  30/34 -> 30/34 green   (unchanged)
```

## WHAT CHANGED

116 files, +9058 lines — the projected read-views of both example bundles, now free of the instance
name, plus the three projectors that produce them.

## WHAT IT DOES NOT PROVE

The bundles' own conformance debt is pre-existing and was neither introduced nor cleared here; that
is why the projection ran through `--project-anyway`, and the reason is recorded in the compile
record rather than in a changelog. A 30/34 is not a clean bundle. The same absolute-path defect
survived in a SECOND producer and was found the next morning (`2026-09-13/050`), which is the
strongest argument that this class is found by grep and not by a gate.
