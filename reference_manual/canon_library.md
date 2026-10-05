---
title: "Moved — canon_library.md"
part_of: reference_manual
status: redirect   # a stub, not a page; the chapter is the front page of its own directory
scope: none
---

# canon_library — moved

## Moved

The chapter is now [**`rules_and_canons/README.md`**](rules_and_canons/README.md), the front page of
the directory it describes.

On 2026-10-05 it was renamed *Rules and their canons* and moved inside its own tree, so that opening
`rules_and_canons/` gives you the overarching description first — what a rule is, where its body
fires, what crosses into the answer, how it is tested — and then the twelve pattern groups.

## Why this stub exists and will not move again

Two references to the old path live in **archive** documents:

| | |
|---|---|
| `decisions/PROTOCOL-2026-10-01_rule-engine.md:346` | finding 7, that the chapter did not list `population_select` |
| `decisions/PROTOCOL-2026-10-01_rule-engine.md:347` | the generated block's line range on that date |

`guardrails/semantic_currency.yaml` names `decisions/` an archive alongside `protocol/`: *"Append-only.
Entries are never edited."* A record citing this path was TRUE on its date — the chapter genuinely did
not list that canon then, which is the finding — and editing the citation would make the record claim
a layout that did not exist when it was written. `check_dangling_references` judges an owned-root path
like `reference_manual/canon_library.md`, and `tools/dangling_floor.txt` is a one-way ratchet that
refuses a new waiver, so the reference cannot be set aside either.

Its sibling stub, [`rules_and_canons/competing_definitions/population_select.md`](rules_and_canons/competing_definitions/population_select.md), exists for the same
reason and cites the same guardrail.
