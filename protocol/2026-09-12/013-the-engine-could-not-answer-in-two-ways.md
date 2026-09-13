---
when: 2026-09-12T17:23:30
what: fixed both defects that stopped the compliant answering engine being usable — it grounded nothing, and with no rule it silently dropped the requested period
topics: [grammar, capabilities, gates]
kind: defect
track: platform
repo: mac-platform
---

## WHAT FORCED IT

The review's §6.1 found the compliant engine unable to ground ANY served bundle. The parser read
`grounding.table`; every bundle authored against the current grammar declares
`grounding.sources[].relation`, which the schema calls "the agnostic source binding" and for which
`table` carries no description at all.

Measured, concepts ungrounded:

```
reference bundle      22/22   ->  0/22
example_shop_ontology  0/8    ->   0/8   (legacy key, unchanged)
```

So `ask()` over a served bundle answered `ontology_gap` for everything. That reads as "the ontology
does not cover this" when it meant "the runtime cannot read the ontology" — a false absence, the same
class of defect as a fabricated identifier: nothing found looks exactly like nothing there.

The second defect made the first unsafe to ship alone. With no derivation rule the assembler took a
branch that emits `SUM(<measure>)` over the whole relation with `where_clauses = []` and
`params = {}`. A period the caller asked for was DROPPED SILENTLY and the answer came back as a
confident figure for all of history.

## EVIDENCE

`git show -s c694f05 dcde1a0` (mac-platform). The second commit states the sequencing reason:

> That is why the console rewire could not simply proceed: it would have swapped a model that
> fabricates for an engine that ignores the period — a different defect producing the same class of
> false business fact.

```
make check: all green
279 passed, 2 skipped · coverage back to 100% · neutrality 137 files 0 ·
sql-invariant 0 over 43 runtime files · self-test 13/13
```

## WHAT CHANGED

Binding order pinned by seven cases: `sources[]` wins; the legacy `table` is still honoured (breaking
older packs to fix the others moves the defect rather than removing it); a stale legacy sibling loses
to `sources[]`; malformed entries are skipped without crashing; a concept with neither key is
UNGROUNDED rather than half-grounded.

The unbindable period is REFUSED, not defaulted. Binding a period needs the column that carries it,
and that is exactly what a rule declares; the planner may not introspect the warehouse to find one.
So the honest answer is the one the contract already names — `ontology_gap`, with the missing thing
stated as `<Measure>.period` and the human reason saying what answering anyway would have done.

Two tests, because one would not have distinguished the properties: the period case refuses, and a
ruleless measure with NO period still plans.

## WHAT IT DOES NOT PROVE

That anything answers. §6.1 is cleared on both defects; what remained of that packet was the console
rewire, the advisor extraction and the stopgap delete. The measured state of the answering path on
this date was that `POST /ask` returns 500 unconditionally and the agent modules cannot import at all
(`2026-09-12/021`), so this fixes a path nothing currently walks.
