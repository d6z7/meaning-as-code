---
when: 2026-09-12T23:54:45
what: described the undescribed legacy grounding key, and fixed the readers and the gate that saw nothing in a bundle filing concepts by domain
topics: [grammar, projections, denominators, gates]
kind: defect
track: ontology
repo: meaning-as-code
---

## WHAT FORCED IT

Two assumptions, each invisible when wrong.

**An undescribed key.** `grounding.sources[]` is the v0.5 binding; `grounding.table` predates it and
carried NO description for five minor versions. Six readers in this estate consequently disagreed
about which to read — one saw 22 of 22 concepts as ungrounded, another drew an empty lineage graph —
and each was defensible against a schema that said nothing.

**A flat glob.** Six readers assumed `ontology/concepts/*.yaml` was flat. A bundle that files
concepts by domain projected ZERO of them — 13 and 8 concepts respectively — and the console drew an
empty ontology. Nothing errored: an empty index is indistinguishable from an empty ontology.

The same flat glob was in a gate. `check_common_rules` read `concepts/*.yaml` while nine other
concept readers in the same directory use `rglob`, so any bundle filing concepts by domain gave it
nothing to look at — and a check over zero subjects passes. That is the zero-denominator pass, inside
a gate whose whole job is to catch concepts restating one refusal law.

## EVIDENCE

`git show -s 4421dc3 a4f823f` (meaning-as-code) and `4333501` (mac-platform).

> Reading one shape linked a legacy-keyed bundle to NOTHING — which key the author happened to use
> decided whether datasets and concepts appeared related at all.

> Nested concepts were also INDEXED at a path that does not exist (`ontology/concepts/{stem}.yaml`),
> so the console answered "no such source file" for a concept it had just listed.

`make check: all green (neutrality 251/257 floor)`.

## WHAT CHANGED

The rule is now written where a reader looks, in `mac.schema.json` and the shape reference: accept
both, prefer `sources[]` when both are present, because the legacy sibling may be stale.
`grounded_relations()` became a named function rather than a seventh inline fallback. The readers
recurse. `open_container` accepts a resource-description path and resolves it to the directory holding
it, so the file a user can SEE in a file dialog is the file they can open.

## WHAT IT DOES NOT PROVE

The schema now DESCRIBES the legacy key; it does not retire it. Two shapes for one fact remain in the
grammar, and "prefer `sources[]`, the legacy sibling may be stale" is a reading rule enforced by
convention in each reader, not by a gate. The next reader written against this schema can still pick
one shape and be silently wrong for a bundle that uses the other.
