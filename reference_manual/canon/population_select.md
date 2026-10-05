---
title: "Moved — canon/population_select.md"
part_of: reference_manual/canon
status: redirect   # a stub, not a page; the content is one directory down
scope: none
---

# population_select — moved

## Moved

`population_select`'s page is now
[**`canon/competing_definitions/population_select.md`**](competing_definitions/population_select.md).

On 2026-10-05 the canon pages were grouped by the pattern each one serves — the `serves` field every
canon term already declared — so a page now sits under the pattern it realizes. Basenames were
preserved through the move, which is why every other reference needed only a group segment inserted.

## Why this stub exists and will not move again

Two references to the old path live in **archive** documents:

| | |
|---|---|
| `decisions/DNA-2026-09-25_ontology-design-requirements.md:463` | the canon's contract page, cited by law 16 |
| `decisions/PROTOCOL-2026-10-01_rule-engine.md:19` | the record that commissioned the canon |

`guardrails/semantic_currency.yaml` names `decisions/` an archive alongside `protocol/`: *"Append-only.
Entries are never edited."* A record citing this path was TRUE on its date, and editing it would make
the record claim a layout that did not exist when it was written. `check_dangling_references` judges an
owned-root path like `reference_manual/canon/population_select.md`, and its floor
(`tools/dangling_floor.txt`) is a one-way ratchet that refuses new entries — so the reference cannot be
waived either.

A stub is therefore the only form that keeps all three true at once: the archive stays unedited, the
link resolves, and the floor does not grow. It stays at this path for as long as those records do.
