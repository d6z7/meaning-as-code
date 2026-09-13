---
when: 2026-09-13T15:00:00
what: adopted the existing runtime vocabulary as the survivor once the consolidation ruling closed, and refused six merges because a shared name standing for two shapes is worse than two honest names
topics: [seams, connector, vocabulary, topology]
kind: refactor
track: core
repo: meaning-as-code
commits: [49e7be1]
---

## WHAT FORCED IT

The operator ruled that the runtime folds into this repo — one repo, several distributions — rather
than staying a separate home. That closes Ruling 12, and **my forward-declared renames existed only
because it was open.** My own `base.py:157` had already written the debt down: "§4.6 says
`SourceErrorReason` IS `mac_runtime.adapters.base.AdapterErrorReason` extended in place (not
duplicated)". The operator's instruction was to do what was most convenient and expect healthy code
to migrate.

## EVIDENCE

Six pairs adopted, each checked for SAMENESS rather than similarity — `AdapterError`'s `__init__`
signature was AST-verified identical, and all four adopted enum members agree on **name AND wire
value**. `param_style` needed no rename: its default was already `":name"`, and that convention is
pinned in **three independent places** in the runtime (planner templates, adapter safety, the Athena
token regex), not one.

**SIX REFUSALS, and refusing is the point.** A wrong merge publishes one name standing for two
shapes, which is strictly worse than two honest names. The decisive ones:

    id != kind          kind's shipped values are "athena"/"fake" and _ID_RE REJECTS BOTH.
                        A name whose grammar rejects the other's data is not one name.
    ReadResult != ExecutionResult   ReadResult carries `columns` — column ORDER, which
                        ExecutionResult loses — and `truncated`, which has no counterpart.
    ReadRequest != ExecutablePlan   3 of 5 fields are ontology provenance: the one thing
                        this seam must not know.
    explain() != validate()   the closest call, refused because DEGRADATION is written in
                        terms of the distinction, and `validate` would sit beside
                        `validate_config` meaning the opposite (wet/raises vs offline/returns).

Each refusal is argued at its own site in the code, not only in the commit message.

## WHAT CHANGED

`ADAPTER_REASON_ALIASES` stops being a rename table and becomes a **total disposition over all six**
runtime members: four adopted — **identity rows kept deliberately, because "unchanged" and "never
looked at" are different claims** — and two retired to exception classes, with the reason stated: a
reason field carrying an exit-1 case inside an exit-2 class is how a could-not-run becomes a FAIL.

**No blanket replace.** That has already broken two modules in this estate by renaming English words
inside strings. Renames were identifier-specific, word-boundary, longest-token-first, with per-token
site counts printed. `CANCELLED`/`cancelled` were never touched bare — only via the qualified enum
form — and the Athena state literals and the prose "...and was cancelled" were verified intact
afterwards.

## WHAT IT DOES NOT PROVE

**A live functional gap, found while renaming, and it is not a naming problem:** a plan the runtime's
planner emits in `:name` form **cannot be bound** by the DuckDB connector, which declares `$name`
(measured against duckdb 1.5.5). A consolidated runtime must re-spell at the seam.

**The wet paths carry no execution coverage and cannot here** — the duckdb driver is absent on this
host and every Athena wet method BILLS. The 21 renamed raise/factory sites are proven by import and
AST only: 7 modules import cleanly, 112 references walked, all 6 reasons construct and map to an exit
code. And the connector-architecture decision record still carries the retired spelling in three
places; that record has an owner and it is not this commit.
