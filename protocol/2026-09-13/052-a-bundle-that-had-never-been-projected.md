---
when: 2026-09-13T00:22:08
what: made the public demo bundle openable — it had no container identity, and the derived layer a host actually reads had never been produced at all
topics: [containers, projections, the-public-boundary]
kind: defect
track: ontology
repo: mac-ontology-contoso
commits: [mac-ontology-contoso:28c9a77, mac-ontology-contoso:dc47f4f, mac-ontology-contoso:86e1ecb, mac-ontology-contoso:750052f]
---

## WHAT FORCED IT

The console refused the bundle outright: `POST /open` answered "container manifest missing
domain/dataset". The console addresses a container as `{data_domain}/{dataset}` and reads both from
the project manifest; this manifest predates the container spec and carried neither.

Once it opened, it showed NOTHING. The bundle had never been projected: `objects.json`,
`lineage_graph.json`, `index.md`, `vocabulary.json`, `diagnostics.json` and every read-view page were
absent. **The bundle was complete; the derived layer that a host actually reads did not exist.**

## EVIDENCE

`git show -s 28c9a77 dc47f4f 86e1ecb 750052f` (mac-ontology-contoso). Projected offline (no AWS, no
Bedrock):

```
28 objects — 8 concepts, 6 datasets, 2 lookups, 8 rules
lineage graph of 14 nodes and 8 edges
```

> This bundle files concepts by domain, which is the layout that projected ZERO concepts before the
> readers were fixed to recurse. All 8 now resolve to their real nested paths rather than to a flat
> path that does not exist.

That is the same nested-layout defect measured the previous evening (`2026-09-12/024`), landing on
its first real subject.

The generated resource description was then WRONG and had to be regenerated, because it was produced
before the projection existed:

> It recorded `derived: []` — an ontology with no derived layer at all. It now describes the six
> derived artifact families with their producers.

It also records `flat: true` on the concept read-views, "which is the honest state: the SSOT `*.yaml`
are filed by domain while the projector writes the `*.md` beside them flat."

A fourth commit added `references/` — the guardrails page and the known-issues index, produced by the
same projection run and left untracked.

## WHAT CHANGED

The manifest declares the container identity. The read view is projected and tracked. `compile.json`
is now gitignored, matching the framework: it is derived, regenerated on every projection, and
machine-specific — it carries the operator who ran it and the raw stdout of wrapped gates, absolute
paths included.

## WHAT IT DOES NOT PROVE

Projected through `--project-anyway`, with the reason recorded in the compile record. Three
pre-existing error classes remain and are untouched: one file the grammar does not define, six
datasets with no declared transform, and answer-path steps no declaration supplies. A projected read
view is not a conforming bundle; it is a bundle a host can now read AND still refuse.

The description's `flat: true` is a recorded inconsistency, not a fixed one — the source of truth and
its own read-view disagree about layout, and the honest field is the only thing catching it.
