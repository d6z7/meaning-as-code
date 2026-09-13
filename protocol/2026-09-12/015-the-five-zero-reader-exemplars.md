---
when: 2026-09-12T17:50:37
what: deleted the five authoring exemplars with zero readers, after two wrong measurements
topics: [consolidation, method, the-public-boundary]
kind: build
track: platform
repo: mac-platform
---

## WHAT FORCED IT

The exemplar directory carried real customer geography inside a repository slated to be public, and
the neutrality gate's largest single population was those files. Deleting them needed evidence that
nothing read them.

## EVIDENCE

`git show -s 9b1cdfa` (mac-platform). The first two attempts at the measurement were wrong, and the
commit records why:

> grepping for the file STEM matched common words ("country", "region") estate-wide, and grepping the
> basename matched DIFFERENT files of the same name in other bundles. The correct query is the path —
> a reader of an exemplar must name `exemplars/` to reach one.

> Result: exactly ONE code reference exists to any exemplar file, `sdk/cli/harvest.py:83` ->
> `geography/country.yaml`. Every other hit is prose (two READMEs, `authoring/__init__.py`, two
> decision records).

`78 passed · harvest still resolves its seed`.

## WHAT CHANGED

Five of six files deleted. `country.yaml` stays, because it is read, and its replacement is NOT ready:
regenerating from the public example bundle covers 61% of shape paths and misses eleven, including
the multi-relation grounding form the writer's own prompt demands.

## WHAT IT DOES NOT PROVE

This is the whole of the deletable set, and it is small. The five rule-lock forks were already ruled
undeletable — three sit behind an armed freeze hook and/or the ontology guard, and one is invoked by
a live repository's own check script. A claim of "two ADR-retired packages" made in the plan was
unsubstantiated and was struck rather than acted on. So the neutrality count moved by content that
nobody read; the content that IS read still carries the customer's geography.
